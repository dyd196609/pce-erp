import io

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from bank_send_preparation.models import (
    BankMessagePreview,
    BankSendGate,
    BankSendPreparation,
)
from bank_send_preparation.services import generate_bank_message_preview
from bank_send_task.models import BankSendTask
from bank_send_task.services import (
    create_bank_send_task,
    bank_send_task_state_transition_guard,
    evaluate_task_creation_gate,
    serialize_task,
)
from bank_send_task.views import BankSendTaskListView
from reconciliation.models import (
    BusinessActionIdempotency,
    BusinessDocumentNumberReservation,
)
from reconciliation.services import ReconciliationError
from system.models import User
from workflow_runtime.models import BusinessStateTransition


@override_settings(
    PCE_CANARY_DEMO_MODE=True,
    PCE_CANARY_TENANT_ID="tenant-canary-demo",
    PCE_CANARY_BATCH_ID="PURCHASE-FLOW-DEMO-V1",
    PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED=True,
    PCE_PAYABLE_CONFIRMATION_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED=True,
    PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_BANK_SEND_PREPARATION_FEATURE_ENABLED=True,
    PCE_BANK_SEND_PREPARATION_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_BANK_SEND_PREPARATION_TEST_TENANTS={"tenant-canary-demo"},
    PCE_BANK_SEND_TASK_FEATURE_ENABLED=True,
    PCE_BANK_SEND_TASK_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_BANK_SEND_TASK_TEST_TENANTS={"tenant-canary-demo"},
    PCE_ACTION_PERMISSION_ENFORCED=True,
)
class BankSendTaskContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        output = io.StringIO()
        for command in (
            "ensure_purchase_canary_formal_domain",
            "ensure_payable_confirmation_prepare_canary",
            "ensure_payment_request_prepare_canary",
            "ensure_payment_request_canary",
            "ensure_payment_instruction_prepare_canary",
            "ensure_payment_order_prepare_canary",
            "ensure_payment_order_draft_canary",
            "ensure_payment_risk_review_canary",
            "ensure_formal_payment_order_canary",
            "ensure_formal_payment_order_send_gate_v54",
            "ensure_bank_send_preparation_canary",
            "ensure_business_action_permission_canary_v552",
        ):
            call_command(command, stdout=output)
        cls.preparation = BankSendPreparation.objects.order_by(
            "prepare_no"
        ).first()
        cls.operator = User.objects.get(username="v552-operator")
        cls.viewer = User.objects.get(username="v552-viewer")
        cls.outscope = User.objects.get(username="v552-outscope")
        cls.bank_operator = User.objects.get(username="v59-bank-operator")
        generate_bank_message_preview(
            user=cls.operator,
            preparation=cls.preparation,
            idempotency_key="V59-TEST-PREVIEW",
            expected_version=cls.preparation.version,
            explicit_user_action=True,
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.preparation = BankSendPreparation.objects.get(
            pk=self.preparation.pk
        )

    def create_task(self, key="V59-TEST-CREATE"):
        return create_bank_send_task(
            user=self.operator,
            preparation=self.preparation,
            idempotency_key=key,
            expected_source_version=self.preparation.version,
            explicit_user_action=True,
        )

    def test_gate_revalidates_all_authoritative_conditions(self):
        gate = evaluate_task_creation_gate(self.preparation)
        self.assertTrue(gate["formalPaymentOrderFrozen"])
        self.assertTrue(gate["formalPaymentOrderFreezeConsistent"])
        self.assertTrue(gate["approvalApproved"])
        self.assertTrue(gate["riskReviewPassed"])
        self.assertTrue(gate["fundsAvailable"])
        self.assertTrue(gate["segregationOfDutiesPassed"])
        self.assertTrue(gate["bankSendGatePassed"])
        self.assertTrue(gate["bankSendPreparationPrepared"])
        self.assertTrue(gate["bankMessagePreviewExists"])
        self.assertTrue(
            gate["forbiddenBusinessProgressWriteCountZero"]
        )
        self.assertTrue(gate["eligible"])

    def test_create_uses_number_idempotency_transaction_and_audit(self):
        outcome = self.create_task()
        self.assertTrue(outcome["created"])
        task = BankSendTask.objects.get()
        self.assertRegex(task.task_no, r"^BST\d{6}\d{8}$")
        self.assertEqual(task.status, "ready_to_send")
        self.assertEqual(task.number_reservation.status, "consumed")
        self.assertEqual(task.business_transaction.status, "committed")
        self.assertEqual(
            BusinessActionIdempotency.objects.get(
                action_code="create-bank-send-task"
            ).status,
            "committed",
        )
        self.assertEqual(
            BusinessDocumentNumberReservation.objects.filter(
                document_type="bankSendTask"
            ).count(),
            1,
        )

    def test_state_machine_is_prepared_queued_ready_to_send(self):
        self.create_task("V59-TEST-STATE")
        task = BankSendTask.objects.get()
        serialized = serialize_task(task)
        self.assertEqual(serialized["status"], "ready_to_send")
        self.assertEqual(serialized["statusTransitionCount"], 2)
        self.assertTrue(serialized["stateMachineConsistent"])
        transitions = list(
            BusinessStateTransition.objects.filter(
                object_type="bank_send_task",
                object_id=task.pk,
            ).order_by("version")
        )
        self.assertEqual(
            [(row.source_state, row.target_state) for row in transitions],
            [
                ("prepared", "queued"),
                ("queued", "ready_to_send"),
            ],
        )

    def test_repeat_is_existing_result_and_single_target(self):
        first = self.create_task("V59-TEST-IDEMPOTENT")
        second = self.create_task("V59-TEST-IDEMPOTENT")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(second["classification"], "existing_result")
        self.assertEqual(BankSendTask.objects.count(), 1)

    def test_viewer_is_denied_and_bank_operator_is_allowed(self):
        with self.assertRaises(ReconciliationError) as raised:
            create_bank_send_task(
                user=self.viewer,
                preparation=self.preparation,
                idempotency_key="V59-VIEWER-DENIED",
                expected_source_version=self.preparation.version,
                explicit_user_action=True,
            )
        self.assertEqual(raised.exception.code, "BST_PERMISSION_DENIED")
        outcome = create_bank_send_task(
            user=self.bank_operator,
            preparation=self.preparation,
            idempotency_key="V59-BANK-OPERATOR",
            expected_source_version=self.preparation.version,
            explicit_user_action=True,
        )
        self.assertTrue(outcome["created"])

    def test_outscope_list_is_empty(self):
        request = self.factory.get("/api/finance/bank-send-tasks/")
        force_authenticate(request, user=self.outscope)
        response = BankSendTaskListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 0)
        self.assertEqual(len(response.data["data"]["sources"]), 0)

    def test_list_exposes_server_facts_and_zero_execution(self):
        self.create_task("V59-TEST-LIST")
        request = self.factory.get("/api/finance/bank-send-tasks/")
        force_authenticate(request, user=self.viewer)
        response = BankSendTaskListView.as_view()(request)
        data = response.data["data"]
        facts = data["bankSendTaskFacts"]
        self.assertEqual(facts["factType"], "BankSendTaskFacts")
        self.assertEqual(facts["currentStateSource"], "server")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["count"], facts["bankSendTaskCount"])
        self.assertEqual(facts["readyToSendCount"], 1)
        self.assertEqual(
            facts["writeIntentFacts"]["sendTaskPreparationWriteCount"],
            1,
        )
        self.assertEqual(
            facts["writeIntentFacts"]["bankSendExecutionWriteCount"],
            0,
        )
        self.assertTrue(
            facts["writeIntentFacts"]["bankSendExecutionWriteBlocked"]
        )
        self.assertTrue(
            all(value == 0 for value in data["downstreamCounts"].values())
        )

    def test_source_without_preview_is_blocked(self):
        source = BankSendPreparation.objects.exclude(
            pk=self.preparation.pk
        ).order_by("prepare_no").first()
        self.assertFalse(hasattr(source, "message_preview"))
        with self.assertRaises(ReconciliationError) as raised:
            create_bank_send_task(
                user=self.operator,
                preparation=source,
                idempotency_key="V59-NO-PREVIEW",
                expected_source_version=source.version,
                explicit_user_action=True,
            )
        self.assertEqual(raised.exception.code, "BST_GATE_BLOCKED")
        self.assertEqual(BankMessagePreview.objects.count(), 1)

    def test_gate_blocks_when_bank_send_gate_is_not_passed(self):
        BankSendGate.objects.filter(
            preparation=self.preparation
        ).update(eligible=False)
        gate = evaluate_task_creation_gate(self.preparation)
        self.assertFalse(gate["eligible"])
        self.assertIn("BANK_SEND_GATE_NOT_PASSED", gate["blockingReasons"])

    def test_gate_blocks_when_funds_are_not_available(self):
        BankSendGate.objects.filter(
            preparation=self.preparation
        ).update(funds_available=False)
        gate = evaluate_task_creation_gate(self.preparation)
        self.assertFalse(gate["fundsAvailable"])
        self.assertIn("FUNDS_NOT_AVAILABLE", gate["blockingReasons"])

    def test_gate_blocks_when_segregation_of_duties_fails(self):
        BankSendGate.objects.filter(
            preparation=self.preparation
        ).update(segregation_valid=False)
        gate = evaluate_task_creation_gate(self.preparation)
        self.assertFalse(gate["segregationOfDutiesPassed"])
        self.assertIn(
            "SEGREGATION_OF_DUTIES_NOT_PASSED",
            gate["blockingReasons"],
        )

    def test_gate_blocks_when_freeze_hash_is_inconsistent(self):
        BankSendGate.objects.filter(
            preparation=self.preparation
        ).update(current_freeze_hash="0" * 64)
        gate = evaluate_task_creation_gate(self.preparation)
        self.assertFalse(gate["formalPaymentOrderFreezeConsistent"])
        self.assertIn(
            "FORMAL_PAYMENT_ORDER_FREEZE_INCONSISTENT",
            gate["blockingReasons"],
        )

    def test_initial_status_cannot_be_written_directly(self):
        task = BankSendTask(
            task_no="BST-DIRECT-INITIAL-STATUS",
            status=BankSendTask.Status.PREPARED,
        )
        with self.assertRaises(ValidationError):
            task.save()

    def test_queryset_status_update_is_blocked(self):
        self.create_task("V59-TEST-QUERYSET-STATUS")
        with self.assertRaises(ValidationError):
            BankSendTask.objects.update(status="queued")

    def test_transition_guard_checks_history_count_and_audit(self):
        self.create_task("V59-TEST-TRANSITION-GUARD")
        task = BankSendTask.objects.get()
        guard = bank_send_task_state_transition_guard(task)
        self.assertEqual(
            guard["guardCode"],
            "bank_send_task_state_transition_guard",
        )
        self.assertTrue(guard["unifiedStateService"])
        self.assertTrue(guard["noSkippedState"])
        self.assertTrue(guard["historyLengthMatchesCount"])
        self.assertTrue(guard["auditReferenceComplete"])
        self.assertTrue(guard["passed"])

    def test_task_facts_include_required_zero_execution_counts(self):
        self.create_task("V59-TEST-FACT-ALIASES")
        request = self.factory.get("/api/finance/bank-send-tasks/")
        force_authenticate(request, user=self.viewer)
        response = BankSendTaskListView.as_view()(request)
        facts = response.data["data"]["bankSendTaskFacts"]
        self.assertEqual(facts["taskCount"], facts["bankSendTaskCount"])
        self.assertEqual(facts["sentCount"], 0)
        self.assertEqual(facts["executionCount"], 0)

    def test_task_persists_tenant_batch_and_sources(self):
        self.create_task("V59-TEST-BATCH")
        task = BankSendTask.objects.get()
        self.assertEqual(task.tenant_id, "tenant-canary-demo")
        self.assertEqual(task.batch_id, "PURCHASE-FLOW-DEMO-V1")
        self.assertEqual(
            task.source_preparation_no,
            self.preparation.prepare_no,
        )
        self.assertEqual(
            task.source_formal_payment_order_no,
            self.preparation.source_formal_payment_order_no,
        )

    def test_explicit_user_action_is_required(self):
        with self.assertRaises(ReconciliationError) as raised:
            create_bank_send_task(
                user=self.operator,
                preparation=self.preparation,
                idempotency_key="V59-EXPLICIT-REQUIRED",
                expected_source_version=self.preparation.version,
                explicit_user_action=False,
            )
        self.assertEqual(
            raised.exception.code,
            "BST_EXPLICIT_ACTION_REQUIRED",
        )

    def test_same_source_with_different_key_returns_existing_task(self):
        first = self.create_task("V59-FIRST-KEY")
        second = self.create_task("V59-SECOND-KEY")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["data"]["id"], second["data"]["id"])
        self.assertEqual(BankSendTask.objects.count(), 1)
