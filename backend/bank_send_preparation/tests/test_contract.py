import io

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from bank_send_preparation.models import BankMessagePreview, BankSendPreparation
from bank_send_preparation.services import (
    generate_bank_message_preview,
    serialize_preparation,
)
from bank_send_preparation.views import BankSendPreparationListView
from reconciliation.services import ReconciliationError
from system.models import User
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.facts import (
    BankSendPreparationFactError,
    BankSendPreparationFacts,
)
from workflow_runtime.write_intents import WriteIntentCategory


@override_settings(
    PCE_CANARY_DEMO_MODE=True,
    PCE_CANARY_TENANT_ID="tenant-canary-demo",
    PCE_CANARY_BATCH_ID="PURCHASE-FLOW-DEMO-V1",
    PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED=True,
    PCE_PAYABLE_CONFIRMATION_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS={
        "tenant-canary-demo"
    },
    PCE_PAYABLE_CONFIRMATION_PREPARE_FAILURE_INJECTION_ENABLED=False,
    PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED=True,
    PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PAYMENT_REQUEST_PREPARE_FAILURE_INJECTION_ENABLED=False,
    PCE_BANK_SEND_PREPARATION_FEATURE_ENABLED=True,
    PCE_BANK_SEND_PREPARATION_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_BANK_SEND_PREPARATION_TEST_TENANTS={"tenant-canary-demo"},
    PCE_ACTION_PERMISSION_ENFORCED=True,
)
class BankSendPreparationContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        output = io.StringIO()
        call_command("ensure_purchase_canary_formal_domain", stdout=output)
        call_command("ensure_payable_confirmation_prepare_canary", stdout=output)
        call_command("ensure_payment_request_prepare_canary", stdout=output)
        call_command("ensure_payment_request_canary", stdout=output)
        call_command("ensure_payment_instruction_prepare_canary", stdout=output)
        call_command("ensure_payment_order_prepare_canary", stdout=output)
        call_command("ensure_payment_order_draft_canary", stdout=output)
        call_command("ensure_payment_risk_review_canary", stdout=output)
        call_command("ensure_formal_payment_order_canary", stdout=output)
        call_command("ensure_formal_payment_order_send_gate_v54", stdout=output)
        call_command("ensure_bank_send_preparation_canary", stdout=output)
        call_command(
            "ensure_business_action_permission_canary_v552",
            stdout=output,
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.operator = User.objects.get(username="v552-operator")
        self.viewer = User.objects.get(username="v552-viewer")
        self.outscope = User.objects.get(username="v552-outscope")
        self.preparation = BankSendPreparation.objects.order_by(
            "prepare_no"
        ).first()

    def test_eight_preparations_use_real_frozen_formal_payment_orders(self):
        preparations = list(
            BankSendPreparation.objects.select_related(
                "source_formal_payment_order",
                "send_gate",
            ).order_by("prepare_no")
        )
        self.assertEqual(len(preparations), 8)
        self.assertTrue(
            all(
                row.status == "prepared"
                and row.source_formal_payment_order.status
                == "frozen_for_execution"
                and row.send_gate.eligible
                and row.source_freeze_hash
                == row.source_formal_payment_order.execution_freeze.freeze_hash
                for row in preparations
            )
        )

    def test_prepared_state_has_real_transition_and_audit(self):
        serialized = serialize_preparation(self.preparation)
        self.assertEqual(serialized["status"], "prepared")
        self.assertEqual(serialized["statusTransitionCount"], 1)
        self.assertTrue(serialized["stateMachineConsistent"])
        transition = BusinessStateTransition.objects.get(
            object_type="bank_send_preparation",
            object_id=self.preparation.pk,
        )
        self.assertEqual(transition.source_state, "draft")
        self.assertEqual(transition.target_state, "prepared")
        self.assertTrue(
            transition.audit_reference.startswith(
                "BusinessActionAuditRecord:"
            )
        )

    def test_operator_generates_preview_only_and_repeat_is_idempotent(self):
        first = generate_bank_message_preview(
            user=self.operator,
            preparation=self.preparation,
            idempotency_key="V58-TEST-PREVIEW-01",
            expected_version=self.preparation.version,
            explicit_user_action=True,
        )
        self.assertTrue(first["created"])
        preview = BankMessagePreview.objects.get(
            preparation=self.preparation
        )
        self.assertEqual(preview.status, "preview_only")
        self.assertFalse(preview.sanitized_payload["sent"])
        self.assertFalse(preview.sanitized_payload["executed"])
        second = generate_bank_message_preview(
            user=self.operator,
            preparation=self.preparation,
            idempotency_key="V58-TEST-PREVIEW-01",
            expected_version=self.preparation.version,
            explicit_user_action=True,
        )
        self.assertFalse(second["created"])
        self.assertEqual(second["classification"], "existing_result")
        self.assertEqual(BankMessagePreview.objects.count(), 1)

    def test_viewer_and_outscope_permissions_are_server_enforced(self):
        with self.assertRaises(ReconciliationError) as raised:
            generate_bank_message_preview(
                user=self.viewer,
                preparation=self.preparation,
                idempotency_key="V58-VIEWER-DENIED",
                expected_version=self.preparation.version,
                explicit_user_action=True,
            )
        self.assertEqual(raised.exception.code, "BSP_PERMISSION_DENIED")
        request = self.factory.get("/api/finance/bank-send-prepares/")
        force_authenticate(request, user=self.outscope)
        response = BankSendPreparationListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 0)

    def test_list_exposes_only_server_facts_and_zero_downstream(self):
        request = self.factory.get("/api/finance/bank-send-prepares/")
        force_authenticate(request, user=self.viewer)
        response = BankSendPreparationListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["currentStateSource"], "server")
        self.assertEqual(response.data["data"]["count"], 8)
        fact_load = response.data["data"]["factLoadFacts"]
        self.assertEqual(
            fact_load["factLoadContractVersion"],
            "PCE-FACT-LOAD-CONTRACT-V1.0",
        )
        self.assertEqual(fact_load["factLoadStatus"], "loaded")
        self.assertEqual(
            fact_load["apiUrl"],
            "/api/finance/bank-send-prepares/",
        )
        self.assertEqual(fact_load["httpStatus"], 200)
        self.assertEqual(fact_load["tenantId"], "tenant-canary-demo")
        self.assertEqual(fact_load["batchId"], "PURCHASE-FLOW-DEMO-V1")
        self.assertEqual(response.data["data"]["factLoadStatus"], "loaded")
        self.assertTrue(
            all(
                value == 0
                for value in response.data["data"]["downstreamCounts"].values()
            )
        )
        self.assertFalse(response.data["data"]["bankSendEnabled"])
        write_facts = response.data["data"]["writeIntentFacts"]
        self.assertEqual(write_facts["previewPreparationWriteCount"], 0)
        self.assertEqual(write_facts["forbiddenBusinessProgressWriteCount"], 0)
        self.assertTrue(write_facts["businessProgressWriteBlocked"])
        self.assertTrue(write_facts["previewOnlyEnforced"])
        self.assertIn(
            WriteIntentCategory.PREVIEW_PREPARATION_WRITE.value,
            write_facts["categories"],
        )

    def test_authorized_empty_scope_is_empty_valid_not_read_failed(self):
        request = self.factory.get("/api/finance/bank-send-prepares/")
        force_authenticate(request, user=self.outscope)
        response = BankSendPreparationListView.as_view()(request)
        data = response.data["data"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["factLoadStatus"], "empty_valid")
        self.assertEqual(data["factLoadFacts"]["factLoadStatus"], "empty_valid")

    def test_preview_write_is_classified_without_business_progress(self):
        generate_bank_message_preview(
            user=self.operator,
            preparation=self.preparation,
            idempotency_key="V581-TEST-WRITE-INTENT-01",
            expected_version=self.preparation.version,
            explicit_user_action=True,
        )
        request = self.factory.get("/api/finance/bank-send-prepares/")
        force_authenticate(request, user=self.operator)
        response = BankSendPreparationListView.as_view()(request)
        write_facts = response.data["data"]["writeIntentFacts"]
        self.assertEqual(write_facts["previewPreparationWriteCount"], 1)
        self.assertGreaterEqual(write_facts["auditWriteCount"], 9)
        self.assertEqual(write_facts["forbiddenBusinessProgressWriteCount"], 0)
        self.assertTrue(write_facts["previewWriteAllowed"])
        self.assertTrue(write_facts["businessProgressWriteBlocked"])
        self.assertTrue(write_facts["previewOnlyEnforced"])

    def test_list_exposes_one_authoritative_bank_send_fact_payload(self):
        request = self.factory.get("/api/finance/bank-send-prepares/")
        force_authenticate(request, user=self.viewer)
        response = BankSendPreparationListView.as_view()(request)
        data = response.data["data"]
        facts = data["bankSendPreparationFacts"]
        self.assertEqual(facts["factType"], "BankSendPreparationFacts")
        self.assertEqual(facts["currentStateSource"], "server")
        for field in (
            "sourceFormalPaymentOrderCount",
            "bankSendPreparationCount",
            "preparedCount",
            "eligibleCount",
            "previewCount",
        ):
            self.assertEqual(data[field], facts[field])
            self.assertEqual(data["capacity"][field], facts[field])
        self.assertEqual(data["writeIntentFacts"], facts["writeIntentFacts"])
        self.assertEqual(data["count"], facts["bankSendPreparationCount"])

    def test_bank_send_facts_reject_non_preview_only_status(self):
        serialized = serialize_preparation(self.preparation)
        serialized["messagePreview"] = {
            "exists": True,
            "status": "sent",
            "sent": True,
            "bankSecretExposed": False,
        }
        with self.assertRaises(BankSendPreparationFactError):
            BankSendPreparationFacts.from_serialized_rows(
                serialized_rows=[serialized],
                source_formal_payment_order_count=1,
                business_progress_counts={},
            )
