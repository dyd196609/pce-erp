import io

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings

from bank_send_execution_simulation.isolation import (
    AUDIT_TYPE_LABELS,
    create_production_isolation_gate,
    ensure_all_simulation_audits,
    evaluate_isolation_checks,
    isolation_gate_facts,
    serialize_audit,
    serialize_isolation_gate,
    simulation_audit_facts,
)
from bank_send_execution_simulation.models import (
    BankSendExecutionRecovery,
    BankSendExecutionSimulation,
    BankSendProductionIsolationGate,
    BankSendSimulationAudit,
)
from bank_send_execution_simulation.services import (
    create_execution_simulation,
    resolve_execution_recovery,
)
from bank_send_request.models import BankSendRequest
from system.models import User
from workflow_runtime.models import BusinessStateTransition

from .test_contract_v64 import SETTINGS


V65_SETTINGS = {
    **SETTINGS,
    "PCE_CANARY_USERNAME": "v552-operator",
    "PCE_BANK_PRODUCTION_API_URL": "",
    "PCE_BANK_PRODUCTION_SECRET_AVAILABLE": False,
    "PCE_BANK_PRODUCTION_SEND_ALLOWED": False,
    "PCE_PAYMENT_EXECUTION_ALLOWED": False,
}


@override_settings(**V65_SETTINGS)
class BankSendSimulationIsolationV65Tests(TestCase):
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
        cls.requests = list(BankSendRequest.objects.order_by("id")[:2])
        cls.operator = User.objects.get(username="v552-operator")

    def setUp(self):
        success = create_execution_simulation(
            user=self.operator,
            request_object=BankSendRequest.objects.get(pk=self.requests[0].pk),
            idempotency_key="V65-SUCCESS",
        )
        failure = create_execution_simulation(
            user=self.operator,
            request_object=BankSendRequest.objects.get(pk=self.requests[1].pk),
            idempotency_key="V65-FAILURE",
            simulate_failure=True,
        )
        recovery = BankSendExecutionRecovery.objects.get(
            simulation_id=failure["data"]["id"]
        )
        resolve_execution_recovery(
            user=self.operator,
            recovery=recovery,
            resolution_note="人工确认模拟失败已恢复，不触发重试",
        )
        ensure_all_simulation_audits()
        self.gate = create_production_isolation_gate(
            user=self.operator,
            tenant_id="tenant-canary-demo",
            batch_id="PURCHASE-FLOW-DEMO-V1",
        )
        self.success = BankSendExecutionSimulation.objects.get(
            pk=success["data"]["id"]
        )

    def test_01_full_audit_count(self):
        self.assertEqual(BankSendSimulationAudit.objects.count(), 9)

    def test_02_success_audit_chain(self):
        values = list(self.success.independent_audits.order_by(
            "occurred_at", "pk"
        ).values_list(
            "audit_type", flat=True
        ))
        self.assertEqual(values, [
            "simulation_created", "simulation_validated",
            "simulation_started", "simulation_completed",
        ])

    def test_03_failure_recovery_audit_chain(self):
        failed = BankSendExecutionSimulation.objects.get(
            status="simulation_failed"
        )
        values = set(failed.independent_audits.values_list(
            "audit_type", flat=True
        ))
        self.assertEqual(values, {
            "simulation_created", "simulation_validated",
            "simulation_started", "simulation_failed",
            "simulation_recovered",
        })

    def test_04_audit_operator_reason_reference_complete(self):
        self.assertTrue(all(
            row.operator_id and row.reason and row.audit_reference
            for row in BankSendSimulationAudit.objects.all()
        ))

    def test_05_audit_idempotent(self):
        ensure_all_simulation_audits()
        self.assertEqual(BankSendSimulationAudit.objects.count(), 9)

    def test_06_audit_labels_complete(self):
        self.assertEqual(set(AUDIT_TYPE_LABELS), set(
            dict(BankSendSimulationAudit.AuditType.choices)
        ))

    def test_07_audit_serialization_server_fact(self):
        row = serialize_audit(BankSendSimulationAudit.objects.first())
        self.assertEqual(row["factSource"], "server")

    def test_08_isolation_checks_pass(self):
        self.assertTrue(evaluate_isolation_checks()["passed"])

    def test_09_production_api_absent(self):
        self.assertTrue(self.gate.checks["ISOLATION-001"])

    def test_10_production_secret_absent(self):
        self.assertTrue(self.gate.checks["ISOLATION-002"])

    def test_11_simulation_environment(self):
        self.assertTrue(self.gate.simulation_environment)

    def test_12_production_send_forbidden(self):
        self.assertFalse(self.gate.production_send_allowed)

    def test_13_payment_execution_forbidden(self):
        self.assertFalse(self.gate.payment_execution_allowed)

    def test_14_isolation_state(self):
        self.assertEqual(self.gate.status, "isolated")

    def test_15_isolation_state_chain(self):
        history = BusinessStateTransition.objects.filter(
            object_type="bank_send_production_isolation_gate",
            object_id=self.gate.pk,
        ).values_list("source_state", "target_state")
        self.assertEqual(list(history), [
            ("created", "checked"), ("checked", "isolated")
        ])

    def test_16_isolation_state_consistent(self):
        self.assertTrue(
            serialize_isolation_gate(self.gate)["stateMachineConsistent"]
        )

    def test_17_direct_isolation_status_update_blocked(self):
        with self.assertRaises(ValidationError):
            BankSendProductionIsolationGate.objects.update(status="sent")

    def test_18_forbidden_gate_states_absent(self):
        values = dict(BankSendProductionIsolationGate.Status.choices)
        self.assertNotIn("approved_for_send", values)
        self.assertNotIn("sent", values)

    def test_19_audit_five_surface_facts(self):
        rows = [
            serialize_audit(row)
            for row in BankSendSimulationAudit.objects.select_related(
                "operator"
            )
        ]
        facts = simulation_audit_facts(
            rows, api_url="/api/test", tenant_id="tenant-canary-demo",
            batch_id="PURCHASE-FLOW-DEMO-V1",
        )
        self.assertEqual(facts["recordCount"], 9)
        self.assertEqual(facts["factSource"], "server")

    def test_20_isolation_five_surface_facts(self):
        rows = [serialize_isolation_gate(self.gate)]
        facts = isolation_gate_facts(
            rows, api_url="/api/test", tenant_id="tenant-canary-demo",
            batch_id="PURCHASE-FLOW-DEMO-V1",
        )
        self.assertEqual(facts["gateCount"], 1)
        self.assertEqual(facts["productionSendAllowedCount"], 0)

    def test_21_audit_api(self):
        response = self.client.get(
            "/api/finance/bank-send-simulation-audits/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["recordCount"], 9)

    def test_22_isolation_api(self):
        response = self.client.get(
            "/api/finance/bank-send-isolation-gates/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["isolatedCount"], 1)

    def test_23_acceptance_contract_v2(self):
        response = self.client.get(
            "/api/finance/bank-send-isolation-gates/"
        ).json()
        facts = response["data"]["acceptanceFacts"]
        self.assertEqual(
            facts["pageAcceptanceContractVersion"],
            "PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0",
        )
        self.assertEqual(facts["acceptanceStatus"], "PASS")

    def test_24_danger_action_count_zero(self):
        response = self.client.get(
            "/api/finance/bank-send-simulation-audits/"
        ).json()
        self.assertEqual(
            response["data"]["acceptanceFacts"]["dangerActionCount"], 0
        )

    def test_25_protection_writes_zero(self):
        response = self.client.get(
            "/api/finance/bank-send-isolation-gates/"
        ).json()["data"]
        self.assertEqual(response["bankMessageSendWriteCount"], 0)
        self.assertEqual(response["paymentExecutionWriteCount"], 0)
        self.assertEqual(response["businessProgressWriteCount"], 0)
