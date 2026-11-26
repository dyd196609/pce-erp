import io

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings

from bank_send_execution_gate.models import BankSendExecutionGate
from bank_send_request.canary import BLOCKED_SCENARIOS, bank_send_request_canary_facts, seed_bank_send_request_canary_pool
from bank_send_request.models import BankSendPreDispatchValidation, BankSendRequest
from bank_send_request.services import (
    ALLOWED_STATE_TRANSITIONS, STATUS_LABELS, bank_send_request_facts_for_rows,
    bank_send_request_state_guard, create_bank_send_request, downstream_counts,
    evaluate_pre_dispatch_validation, rerun_pre_dispatch_validation, serialize_request,
)
from reconciliation.services import ReconciliationError
from system.models import User
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.write_intents import build_bank_send_request_write_intent_facts


SETTINGS = {
    "PCE_CANARY_DEMO_MODE": True,
    "PCE_CANARY_TENANT_ID": "tenant-canary-demo",
    "PCE_CANARY_BATCH_ID": "PURCHASE-FLOW-DEMO-V1",
    "PCE_BANK_SEND_REQUEST_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_REQUEST_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_BANK_SEND_REQUEST_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_BANK_SEND_EXECUTION_GATE_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_EXECUTION_GATE_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_BANK_SEND_EXECUTION_GATE_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_BANK_SEND_TASK_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_TASK_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_BANK_SEND_PREPARATION_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_PREPARATION_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED": True,
    "PCE_PAYABLE_CONFIRMATION_PREPARE_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED": True,
    "PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_ACTION_PERMISSION_ENFORCED": True,
}


@override_settings(**SETTINGS)
class BankSendRequestV61Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        out = io.StringIO()
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
            "ensure_bank_send_execution_gate_canary_v60",
        ):
            call_command(command, stdout=out)
        cls.gates = list(BankSendExecutionGate.objects.order_by("gate_no")[:8])
        seed_bank_send_request_canary_pool(cls.gates)
        cls.operator = User.objects.get(username="v552-operator")
        cls.viewer = User.objects.get(username="v552-viewer")

    def setUp(self):
        self.gate = BankSendExecutionGate.objects.get(pk=self.gates[0].pk)

    def create(self, key="V61-TEST"):
        return create_bank_send_request(
            user=self.operator, gate=self.gate, idempotency_key=key,
            expected_source_version=self.gate.version, explicit_user_action=True,
        )

    def test_01_precheck_passes(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["eligible"])
    def test_02_gate_valid(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["authorizationGateStillValid"])
    def test_03_authorization_hash_matches(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["authorizationHashUnchanged"])
    def test_04_task_unchanged(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["bankSendTaskUnchanged"])
    def test_05_order_unchanged(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["formalPaymentOrderUnchanged"])
    def test_06_amount_unchanged(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["amountUnchanged"])
    def test_07_beneficiary_unchanged(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["beneficiaryAccountUnchanged"])
    def test_08_preview_hash_unchanged(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["messagePreviewHashUnchanged"])
    def test_09_interface_available(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["bankInterfaceAvailable"])
    def test_10_no_transaction(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["bankTransactionAbsent"])
    def test_11_no_payment_execution(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["paymentExecutionAbsent"])
    def test_12_segregation_passes(self): self.assertTrue(evaluate_pre_dispatch_validation(self.gate)["segregationOfDutiesPassed"])

    def test_13_create_success(self):
        result = self.create()
        self.assertTrue(result["created"])
        self.assertEqual(result["data"]["status"], "ready_to_dispatch")

    def test_14_idempotent_by_source(self):
        first = self.create()
        second = self.create("V61-OTHER")
        self.assertEqual(first["data"]["id"], second["data"]["id"])
        self.assertFalse(second["created"])

    def test_15_explicit_action_required(self):
        with self.assertRaises(ReconciliationError):
            create_bank_send_request(
                user=self.operator, gate=self.gate, idempotency_key="x",
                expected_source_version=self.gate.version, explicit_user_action=False,
            )

    def test_16_key_required(self):
        with self.assertRaises(ReconciliationError):
            create_bank_send_request(
                user=self.operator, gate=self.gate, idempotency_key="",
                expected_source_version=self.gate.version, explicit_user_action=True,
            )

    def test_17_version_conflict(self):
        with self.assertRaises(ReconciliationError):
            create_bank_send_request(
                user=self.operator, gate=self.gate, idempotency_key="x",
                expected_source_version=99, explicit_user_action=True,
            )

    def test_18_state_chain(self):
        row = self.create()["data"]
        self.assertEqual([(x["sourceState"], x["targetState"]) for x in row["statusTransitionHistory"]], list(ALLOWED_STATE_TRANSITIONS))

    def test_19_guard_passes(self):
        self.create()
        self.assertTrue(bank_send_request_state_guard(BankSendRequest.objects.get(source_gate=self.gate))["passed"])

    def test_20_history_count(self):
        row = self.create()["data"]
        self.assertEqual(row["statusTransitionCount"], len(row["statusTransitionHistory"]))

    def test_21_audit_references(self):
        row = self.create()["data"]
        self.assertTrue(all(x["auditReference"].startswith("BusinessActionAuditRecord:") for x in row["statusTransitionHistory"]))

    def test_22_direct_status_update_blocked(self):
        self.create()
        with self.assertRaises(ValidationError):
            BankSendRequest.objects.update(status="sent")

    def test_23_sent_not_in_choices(self):
        self.assertNotIn("sent", dict(BankSendRequest.Status.choices))

    def test_24_status_labels(self):
        self.assertEqual(STATUS_LABELS, {"draft": "草稿", "validated": "校验通过", "ready_to_dispatch": "发送前待分发"})

    def test_25_validation_record(self):
        self.create()
        self.assertEqual(BankSendPreDispatchValidation.objects.get().result, "passed")

    def test_26_revalidation_appends(self):
        self.create()
        obj = BankSendRequest.objects.get(source_gate=self.gate)
        self.assertEqual(rerun_pre_dispatch_validation(user=self.operator, request_object=obj)["result"], "passed")
        self.assertEqual(obj.pre_dispatch_validations.count(), 2)

    def test_27_canary_pool_counts(self):
        facts = bank_send_request_canary_facts()
        self.assertEqual((facts["normalPoolCount"], facts["blockedPoolCount"], facts["reservePoolCount"]), (8, 8, 20))

    def test_28_blocked_scenarios_exact(self):
        self.assertEqual(len(BLOCKED_SCENARIOS), 8)
        self.assertEqual(BLOCKED_SCENARIOS[0][0], "authorization_hash_changed")

    def test_29_write_boundary_zero(self):
        facts = build_bank_send_request_write_intent_facts(
            send_request_preparation_write_count=1, audit_write_count=4,
            bank_send_execution_counts=downstream_counts(),
        )
        self.assertEqual(facts["businessProgressWriteCount"], 0)
        self.assertTrue(facts["bankMessageSendWriteBlocked"])

    def test_30_server_facts(self):
        rows = [serialize_request(BankSendRequest.objects.get(pk=self.create()["data"]["id"]))]
        pool = bank_send_request_canary_facts()
        facts = bank_send_request_facts_for_rows(
            rows=rows, canary_pool_facts=pool,
            tenant_id="tenant-canary-demo", batch_id="PURCHASE-FLOW-DEMO-V1",
        )
        self.assertEqual(facts["requestCount"], 1)
        self.assertEqual(facts["readyToDispatchCount"], 1)
        self.assertEqual(facts["bankMessageSentCount"], 0)
