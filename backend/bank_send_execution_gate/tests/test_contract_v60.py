import io

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from bank_send_execution_gate.canary import (
    BLOCKED_SCENARIOS,
    bank_send_execution_gate_canary_facts,
    seed_bank_send_execution_gate_canary_pool,
)
from bank_send_execution_gate.models import BankSendExecutionGate
from bank_send_execution_gate.services import (
    ALLOWED_STATE_TRANSITIONS,
    STATUS_LABELS,
    bank_send_execution_gate_state_guard,
    create_bank_send_execution_gate,
    evaluate_execution_authorization,
    serialize_gate,
)
from bank_send_execution_gate.views import (
    BankSendExecutionGateCanaryBlockedAttemptView,
    BankSendExecutionGateListView,
)
from bank_send_task.models import BankSendTask
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
)
from reconciliation.services import ReconciliationError
from system.models import User
from workflow_runtime.models import BusinessStateTransition


V60_SETTINGS = {
    "PCE_CANARY_DEMO_MODE": True,
    "PCE_CANARY_TENANT_ID": "tenant-canary-demo",
    "PCE_CANARY_BATCH_ID": "PURCHASE-FLOW-DEMO-V1",
    "PCE_BANK_SEND_EXECUTION_GATE_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_EXECUTION_GATE_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_BANK_SEND_EXECUTION_GATE_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED": True,
    "PCE_PAYABLE_CONFIRMATION_PREPARE_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS":
        {"tenant-canary-demo"},
    "PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED": True,
    "PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_BANK_SEND_PREPARATION_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_PREPARATION_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_BANK_SEND_PREPARATION_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_BANK_SEND_TASK_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_TASK_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_BANK_SEND_TASK_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_ACTION_PERMISSION_ENFORCED": True,
}


@override_settings(**V60_SETTINGS)
class BankSendExecutionGateV60Tests(TestCase):
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
            "ensure_bank_send_task_canary_v591",
        ):
            call_command(command, stdout=output)
        cls.tasks = list(BankSendTask.objects.order_by("task_no")[:8])
        seed_bank_send_execution_gate_canary_pool(cls.tasks)
        cls.operator = User.objects.get(username="v552-operator")
        cls.viewer = User.objects.get(username="v552-viewer")

    def setUp(self):
        self.factory = APIRequestFactory()
        self.task = BankSendTask.objects.get(pk=self.tasks[0].pk)

    def create_gate(self, key="V60-TEST-GATE"):
        return create_bank_send_execution_gate(
            user=self.operator,
            task=self.task,
            idempotency_key=key,
            expected_source_version=self.task.version,
            explicit_user_action=True,
        )

    def test_01_authorization_is_eligible(self):
        self.assertTrue(evaluate_execution_authorization(self.task)["eligible"])

    def test_02_task_must_be_ready_to_send(self):
        self.task.status = "queued"
        result = evaluate_execution_authorization(self.task)
        self.assertFalse(result["bankSendTaskReadyToSend"])

    def test_03_freeze_is_revalidated(self):
        gate = self.task.source_preparation.send_gate
        gate.freeze_hash_passed = False
        self.assertFalse(
            evaluate_execution_authorization(self.task)[
                "formalPaymentOrderFreezeConsistent"
            ]
        )

    def test_04_approval_is_revalidated(self):
        gate = self.task.source_preparation.send_gate
        gate.approval_passed = False
        self.assertFalse(
            evaluate_execution_authorization(self.task)["approvalApproved"]
        )

    def test_05_risk_is_revalidated(self):
        gate = self.task.source_preparation.send_gate
        gate.risk_review_passed = False
        self.assertFalse(
            evaluate_execution_authorization(self.task)["riskReviewPassed"]
        )

    def test_06_funds_are_revalidated(self):
        gate = self.task.source_preparation.send_gate
        gate.funds_available = False
        self.assertFalse(
            evaluate_execution_authorization(self.task)["fundsAvailable"]
        )

    def test_07_segregation_is_revalidated(self):
        gate = self.task.source_preparation.send_gate
        gate.segregation_valid = False
        self.assertFalse(
            evaluate_execution_authorization(self.task)[
                "segregationOfDutiesPassed"
            ]
        )

    def test_08_bank_interface_is_revalidated(self):
        gate = self.task.source_preparation.send_gate
        gate.bank_interface_available = False
        self.assertFalse(
            evaluate_execution_authorization(self.task)[
                "bankInterfaceAvailable"
            ]
        )

    def test_09_preview_hash_is_revalidated(self):
        self.task.message_preview_hash = "changed"
        self.assertFalse(
            evaluate_execution_authorization(self.task)[
                "messagePreviewHashConsistent"
            ]
        )

    def test_10_gate_creation_rejects_missing_explicit_action(self):
        with self.assertRaises(ReconciliationError):
            create_bank_send_execution_gate(
                user=self.operator,
                task=self.task,
                idempotency_key="V60-NO-EXPLICIT",
                expected_source_version=self.task.version,
                explicit_user_action=False,
            )

    def test_11_gate_creation_rejects_missing_idempotency_key(self):
        with self.assertRaises(ReconciliationError):
            create_bank_send_execution_gate(
                user=self.operator,
                task=self.task,
                idempotency_key="",
                expected_source_version=self.task.version,
                explicit_user_action=True,
            )

    def test_12_gate_creation_rejects_version_conflict(self):
        with self.assertRaises(ReconciliationError) as error:
            create_bank_send_execution_gate(
                user=self.operator,
                task=self.task,
                idempotency_key="V60-VERSION",
                expected_source_version=999,
                explicit_user_action=True,
            )
        self.assertEqual(error.exception.code, "BSEG_VERSION_CONFLICT")

    def test_13_gate_creation_rejects_viewer(self):
        with self.assertRaises(ReconciliationError) as error:
            create_bank_send_execution_gate(
                user=self.viewer,
                task=self.task,
                idempotency_key="V60-VIEWER",
                expected_source_version=self.task.version,
                explicit_user_action=True,
            )
        self.assertEqual(error.exception.code, "BSEG_PERMISSION_DENIED")

    def test_14_creation_reaches_ready_for_execution(self):
        result = self.create_gate()
        self.assertTrue(result["created"])
        self.assertEqual(result["data"]["status"], "ready_for_execution")

    def test_15_state_path_is_complete(self):
        self.create_gate("V60-STATE")
        history = BusinessStateTransition.objects.filter(
            object_type="bank_send_execution_gate"
        ).order_by("version")
        self.assertEqual(
            [(row.source_state, row.target_state) for row in history],
            [
                ("pending_review", "approved"),
                ("approved", "ready_for_execution"),
            ],
        )

    def test_16_skip_transition_is_not_allowed(self):
        self.assertNotIn(
            ("pending_review", "ready_for_execution"),
            ALLOWED_STATE_TRANSITIONS,
        )

    def test_17_sent_and_executed_are_not_states(self):
        values = {value for value, _ in BankSendExecutionGate.Status.choices}
        self.assertNotIn("sent", values)
        self.assertNotIn("executed", values)

    def test_18_direct_status_update_is_blocked(self):
        self.create_gate("V60-DIRECT")
        with self.assertRaises(ValidationError):
            BankSendExecutionGate.objects.update(status="approved")

    def test_19_repeat_returns_existing_gate(self):
        first = self.create_gate("V60-IDEMPOTENT")
        second = self.create_gate("V60-IDEMPOTENT")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(BankSendExecutionGate.objects.count(), 1)

    def test_20_idempotency_record_committed(self):
        self.create_gate("V60-IDEMPOTENCY-ROW")
        row = BusinessActionIdempotency.objects.get(
            action_code="submit-bank-send-final-authorization-review"
        )
        self.assertEqual(row.status, "committed")

    def test_21_audit_references_complete(self):
        self.create_gate("V60-AUDIT")
        serialized = serialize_gate(BankSendExecutionGate.objects.get())
        self.assertTrue(serialized["stateTransitionGuard"]["auditReferenceComplete"])
        self.assertEqual(
            BusinessActionAuditRecord.objects.filter(
                target_type="bankSendExecutionGate"
            ).count(),
            3,
        )

    def test_22_guard_passes(self):
        self.create_gate("V60-GUARD")
        self.assertTrue(
            bank_send_execution_gate_state_guard(
                BankSendExecutionGate.objects.get()
            )["passed"]
        )

    def test_23_status_labels_are_chinese(self):
        self.assertEqual(STATUS_LABELS["pending_review"], "待最终授权审核")
        self.assertEqual(STATUS_LABELS["approved"], "授权审核通过")
        self.assertEqual(STATUS_LABELS["ready_for_execution"], "执行前就绪")

    def test_24_serialized_downstream_is_zero(self):
        self.create_gate("V60-ZERO")
        data = serialize_gate(BankSendExecutionGate.objects.get())
        self.assertFalse(data["bankSendExecuted"])
        self.assertFalse(data["paymentExecuted"])
        self.assertTrue(all(value == 0 for value in data["downstreamCounts"].values()))

    def test_25_write_intent_classification_is_safe(self):
        self.create_gate("V60-WRITE")
        facts = serialize_gate(BankSendExecutionGate.objects.get())[
            "writeIntentFacts"
        ]
        self.assertEqual(facts["executionGatePreparationWriteCount"], 1)
        self.assertEqual(facts["bankSendExecutionWriteCount"], 0)
        self.assertEqual(facts["paymentExecutionWriteCount"], 0)
        self.assertEqual(facts["businessProgressWriteCount"], 0)

    def test_26_canary_pool_is_8_6_20(self):
        facts = bank_send_execution_gate_canary_facts()
        self.assertEqual(facts["normalPoolCount"], 8)
        self.assertEqual(facts["blockedPoolCount"], 6)
        self.assertEqual(facts["reservePoolCount"], 20)

    def test_27_blocked_scenarios_are_complete(self):
        self.assertEqual(
            {code for code, _ in BLOCKED_SCENARIOS},
            {
                "freeze_failed",
                "approval_failed",
                "risk_failed",
                "funds_insufficient",
                "segregation_failed",
                "message_hash_changed",
            },
        )

    def test_28_blocked_canary_api_rejects(self):
        request = self.factory.post("/blocked/freeze_failed")
        force_authenticate(request, user=self.operator)
        response = BankSendExecutionGateCanaryBlockedAttemptView.as_view()(
            request,
            scenario_code="freeze_failed",
        )
        self.assertEqual(response.status_code, 409)

    def test_29_list_api_uses_server_facts(self):
        self.create_gate("V60-LIST")
        request = self.factory.get("/api/finance/bank-send-execution-gates/")
        response = BankSendExecutionGateListView.as_view()(request)
        data = response.data["data"]
        self.assertEqual(data["factLoadStatus"], "success")
        self.assertEqual(data["count"], 1)
        self.assertEqual(
            data["bankSendExecutionGateFacts"]["gateCount"],
            data["capacity"]["gateCount"],
        )

    def test_30_list_api_protects_execution_boundary(self):
        request = self.factory.get("/api/finance/bank-send-execution-gates/")
        response = BankSendExecutionGateListView.as_view()(request)
        facts = response.data["data"]["bankSendExecutionGateFacts"]
        self.assertEqual(facts["executedCount"], 0)
        self.assertEqual(facts["bankSendExecutionCount"], 0)
        self.assertEqual(facts["bankMessageSentCount"], 0)
        self.assertEqual(facts["paymentExecutionCount"], 0)
