import io

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings

from bank_send_execution_simulation.models import (
    BankSendExecutionRecovery,
    BankSendExecutionSimulation,
)
from bank_send_execution_simulation.services import (
    SIMULATION_TRANSITIONS,
    STATUS_LABELS,
    create_execution_simulation,
    evaluate_simulation_checks,
    protection_counts,
    resolve_execution_recovery,
    serialize_simulation,
    simulation_facts,
    simulation_state_guard,
)
from bank_send_request.models import BankSendRequest
from reconciliation.services import ReconciliationError
from system.models import User


SETTINGS = {
    "PCE_CANARY_DEMO_MODE": True,
    "PCE_CANARY_TENANT_ID": "tenant-canary-demo",
    "PCE_CANARY_BATCH_ID": "PURCHASE-FLOW-DEMO-V1",
    "PCE_BANK_SEND_SIMULATION_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_SIMULATION_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_BANK_SEND_SIMULATION_PRODUCTION_ROLLOUT_ENABLED": False,
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
    "PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED": True,
    "PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_ACTION_PERMISSION_ENFORCED": True,
}


@override_settings(**SETTINGS)
class BankSendExecutionSimulationV64Tests(TestCase):
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
            "ensure_bank_send_request_canary_v61",
        ):
            call_command(command, stdout=out)
        cls.requests = list(BankSendRequest.objects.order_by("id")[:8])
        cls.operator = User.objects.get(username="v552-operator")

    def setUp(self):
        self.request_object = BankSendRequest.objects.get(pk=self.requests[0].pk)

    def create(self, *, failure=False, key="V64-TEST"):
        return create_execution_simulation(
            user=self.operator, request_object=self.request_object,
            idempotency_key=key, simulate_failure=failure,
        )

    def test_01_request_ready(self):
        self.assertTrue(evaluate_simulation_checks(self.request_object)["requestReadyToDispatch"])

    def test_02_authorization_ready(self):
        self.assertTrue(evaluate_simulation_checks(self.request_object)["authorizationReadyForExecution"])

    def test_03_authorization_hash(self):
        self.assertTrue(evaluate_simulation_checks(self.request_object)["authorizationHashConsistent"])

    def test_04_request_hash(self):
        self.assertTrue(evaluate_simulation_checks(self.request_object)["requestHashConsistent"])

    def test_05_amount(self):
        self.assertTrue(evaluate_simulation_checks(self.request_object)["paymentAmountConsistent"])

    def test_06_account(self):
        self.assertTrue(evaluate_simulation_checks(self.request_object)["beneficiaryAccountConsistent"])

    def test_07_message_digest(self):
        self.assertTrue(evaluate_simulation_checks(self.request_object)["messageDigestConsistent"])

    def test_08_simulated_interface(self):
        self.assertTrue(evaluate_simulation_checks(self.request_object)["simulatedBankInterfaceAvailable"])

    def test_09_success(self):
        row = self.create()["data"]
        self.assertEqual(row["status"], "simulation_success")

    def test_10_failure(self):
        row = self.create(failure=True)["data"]
        self.assertEqual(row["status"], "simulation_failed")

    def test_11_failure_creates_recovery(self):
        self.create(failure=True)
        self.assertEqual(BankSendExecutionRecovery.objects.get().recovery_status, "pending")

    def test_12_recovery_resolves_without_retry(self):
        row = self.create(failure=True)["data"]
        recovery = BankSendExecutionRecovery.objects.get(simulation_id=row["id"])
        result = resolve_execution_recovery(
            user=self.operator, recovery=recovery, resolution_note="人工恢复"
        )
        self.assertEqual(result["recoveryStatus"], "resolved")
        self.assertEqual(BankSendExecutionSimulation.objects.get(pk=row["id"]).status, "simulation_failed")

    def test_13_idempotent_by_request_and_version(self):
        first = self.create()
        second = self.create(key="V64-OTHER")
        self.assertEqual(first["data"]["id"], second["data"]["id"])
        self.assertFalse(second["created"])

    def test_14_key_required(self):
        with self.assertRaises(ReconciliationError):
            self.create(key="")

    def test_15_state_chain_success(self):
        row = self.create()["data"]
        chain = [(item["sourceState"], item["targetState"]) for item in row["statusTransitionHistory"]]
        self.assertEqual(chain, list(SIMULATION_TRANSITIONS[:3]))

    def test_16_state_chain_failure(self):
        row = self.create(failure=True)["data"]
        chain = [(item["sourceState"], item["targetState"]) for item in row["statusTransitionHistory"]]
        self.assertEqual(chain, [SIMULATION_TRANSITIONS[0], SIMULATION_TRANSITIONS[1], SIMULATION_TRANSITIONS[3]])

    def test_17_guard(self):
        self.create()
        self.assertTrue(simulation_state_guard(BankSendExecutionSimulation.objects.get())["passed"])

    def test_18_history_count(self):
        row = self.create()["data"]
        self.assertEqual(row["statusTransitionCount"], len(row["statusTransitionHistory"]))

    def test_19_audit_references(self):
        row = self.create()["data"]
        self.assertTrue(all(item["auditReference"] for item in row["statusTransitionHistory"]))

    def test_20_direct_update_blocked(self):
        self.create()
        with self.assertRaises(ValidationError):
            BankSendExecutionSimulation.objects.update(status="sent")

    def test_21_forbidden_statuses_absent(self):
        self.assertNotIn("sent", dict(BankSendExecutionSimulation.Status.choices))
        self.assertNotIn("executed", dict(BankSendExecutionSimulation.Status.choices))

    def test_22_chinese_labels(self):
        self.assertEqual(STATUS_LABELS["simulation_success"], "模拟成功")
        self.assertEqual(STATUS_LABELS["simulation_failed"], "模拟失败")

    def test_23_facts(self):
        rows = [serialize_simulation(BankSendExecutionSimulation.objects.get(pk=self.create()["data"]["id"]))]
        facts = simulation_facts(rows, api_url="/api/test", tenant_id="tenant-canary-demo", batch_id="batch")
        self.assertEqual(facts["simulationCount"], 1)
        self.assertEqual(facts["successCount"], 1)
        self.assertEqual(facts["factSource"], "server")

    def test_24_protection_counts(self):
        self.assertEqual(set(protection_counts().values()), {0})

    def test_25_failure_does_not_auto_retry(self):
        row = self.create(failure=True)["data"]
        self.assertEqual(row["status"], "simulation_failed")
        self.assertEqual(BankSendExecutionSimulation.objects.count(), 1)

