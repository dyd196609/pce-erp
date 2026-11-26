import hashlib

from django.core.exceptions import ValidationError
from django.test import override_settings

from system.models import User
from workflow_runtime.models import (
    BusinessStateTransition,
    UserOrganizationRoleAuthority,
)
from workflow_runtime.state_transitions import transition_business_object

from bank_send_execution_simulation.models import (
    BankSendChainTrace,
    BankSendExecutionSimulation,
    BankSendFinalApproval,
    BankSendFinalApprovalDecision,
)
from bank_send_execution_simulation.v66 import (
    APPROVAL_TRANSITIONS,
    BUSINESS_REVIEWER_ROLE,
    FUND_OWNER_ROLE,
    build_chain_trace,
    chain_trace_facts,
    create_final_approval,
    ensure_chain_traces,
    evaluate_final_checks,
    final_approval_facts,
    protection_counts,
    serialize_approval,
    serialize_trace,
    submit_first_approval,
    submit_second_approval,
)

from .test_contract_v65 import (
    BankSendSimulationIsolationV65Tests,
    V65_SETTINGS,
)


@override_settings(**V65_SETTINGS)
class BankSendChainFinalApprovalV66Tests(
    BankSendSimulationIsolationV65Tests
):
    def setUp(self):
        super().setUp()
        ensure_chain_traces(
            user=self.operator,
            queryset=BankSendExecutionSimulation.objects.order_by("pk"),
        )
        self.success_trace = BankSendChainTrace.objects.get(
            source_simulation=self.success
        )
        self.approval = create_final_approval(
            trace=self.success_trace, user=self.operator
        )
        legal_entity = self.success.source_request.legal_entity_id
        self.reviewer = User.objects.create_user(
            username="v66-reviewer",
            real_name="V66 Reviewer",
            company_id=self.operator.company_id,
        )
        self.fund_owner = User.objects.create_user(
            username="v66-fund-owner",
            real_name="V66 Fund Owner",
            company_id=self.operator.company_id,
        )
        for user, role in (
            (self.reviewer, BUSINESS_REVIEWER_ROLE),
            (self.fund_owner, FUND_OWNER_ROLE),
        ):
            UserOrganizationRoleAuthority.objects.create(
                user=user,
                role_code=role,
                legal_entity_id=legal_entity,
                department_id="V66",
                active=True,
                version=1,
                business_hash=hashlib.sha256(
                    f"{user.pk}:{role}".encode()
                ).hexdigest(),
            )

    def test_26_trace_count(self):
        self.assertEqual(BankSendChainTrace.objects.count(), 2)

    def test_27_trace_has_eight_nodes(self):
        self.assertEqual(len(self.success_trace.node_snapshot), 8)

    def test_28_trace_node_order_is_fixed(self):
        self.assertEqual(
            [row["order"] for row in self.success_trace.node_snapshot],
            list(range(1, 9)),
        )

    def test_29_trace_sources_are_server(self):
        self.assertTrue(all(
            row["source"] == "server"
            for row in self.success_trace.node_snapshot
        ))

    def test_30_trace_relations_are_complete(self):
        row = serialize_trace(self.success_trace)
        self.assertTrue(row["traceComplete"])
        self.assertEqual(row["missingNodeCount"], 0)

    def test_31_trace_is_idempotent(self):
        self.assertEqual(
            build_chain_trace(
                simulation=self.success, user=self.operator
            ).pk,
            self.success_trace.pk,
        )

    def test_32_failed_simulation_cannot_create_final_approval(self):
        failed_trace = BankSendChainTrace.objects.exclude(
            pk=self.success_trace.pk
        ).get()
        with self.assertRaises(ValueError):
            create_final_approval(
                trace=failed_trace, user=self.operator
            )

    def test_33_final_checks_pass_for_success(self):
        checks = evaluate_final_checks(self.success_trace)
        self.assertTrue(checks["passed"])
        self.assertTrue(all(checks[f"FINAL-{index:03d}"] for index in range(1, 9)))

    def test_34_approval_starts_pending(self):
        self.assertEqual(self.approval.status, "pending")

    def test_35_first_approval_requires_role(self):
        with self.assertRaises(PermissionError):
            submit_first_approval(
                approval=self.approval,
                user=self.operator,
                reason="no role",
            )

    def test_36_first_approval(self):
        approval = submit_first_approval(
            approval=self.approval,
            user=self.reviewer,
            reason="business approved",
        )
        self.assertEqual(approval.status, "first_approved")

    def test_37_same_user_cannot_approve_twice(self):
        approval = submit_first_approval(
            approval=self.approval,
            user=self.reviewer,
            reason="business approved",
        )
        with self.assertRaises(PermissionError):
            submit_second_approval(
                approval=approval,
                user=self.reviewer,
                reason="same user",
            )

    def test_38_second_approval_locks(self):
        approval = submit_first_approval(
            approval=self.approval,
            user=self.reviewer,
            reason="business approved",
        )
        approval = submit_second_approval(
            approval=approval,
            user=self.fund_owner,
            reason="fund approved",
        )
        self.assertEqual(approval.status, "final_locked")

    def test_39_decisions_are_two_users_two_roles(self):
        approval = submit_first_approval(
            approval=self.approval,
            user=self.reviewer,
            reason="business approved",
        )
        submit_second_approval(
            approval=approval,
            user=self.fund_owner,
            reason="fund approved",
        )
        decisions = list(
            BankSendFinalApprovalDecision.objects.order_by("pk")
        )
        self.assertEqual(len({row.operator_id for row in decisions}), 2)
        self.assertEqual(len({row.role for row in decisions}), 2)

    def test_40_decision_audit_fields_complete(self):
        submit_first_approval(
            approval=self.approval,
            user=self.reviewer,
            reason="business approved",
        )
        row = BankSendFinalApprovalDecision.objects.get()
        self.assertTrue(
            row.operator_id
            and row.role
            and row.occurred_at
            and row.reason
            and row.audit_reference
        )

    def test_41_direct_status_save_is_blocked(self):
        self.approval.status = "final_locked"
        with self.assertRaises(ValidationError):
            self.approval.save()

    def test_42_bulk_status_update_is_blocked(self):
        with self.assertRaises(ValidationError):
            BankSendFinalApproval.objects.filter(
                pk=self.approval.pk
            ).update(status="final_locked")

    def test_43_state_jump_is_blocked(self):
        with self.assertRaises(ValueError):
            with self.captureOnCommitCallbacks(execute=True):
                transition_business_object(
                    business_object=self.approval,
                    object_type="bank_send_final_approval",
                    source_state="pending",
                    target_state="final_locked",
                    action_code="invalid-jump",
                    operator=self.reviewer,
                    reason="invalid",
                    audit_reference="invalid",
                    allowed_transitions=APPROVAL_TRANSITIONS,
                )

    def test_44_transition_history_complete(self):
        approval = submit_first_approval(
            approval=self.approval,
            user=self.reviewer,
            reason="business approved",
        )
        approval = submit_second_approval(
            approval=approval,
            user=self.fund_owner,
            reason="fund approved",
        )
        row = serialize_approval(approval)
        self.assertTrue(row["stateMachineConsistent"])
        self.assertEqual(row["statusTransitionCount"], 3)

    def test_45_trace_five_surface_fact_value(self):
        rows = [serialize_trace(row) for row in BankSendChainTrace.objects.all()]
        facts = chain_trace_facts(
            rows,
            tenant_id="tenant-canary-demo",
            batch_id="PURCHASE-FLOW-DEMO-V1",
        )
        self.assertEqual(facts["traceCount"], 2)
        self.assertEqual(facts["nodeCount"], 8)

    def test_46_approval_five_surface_fact_value(self):
        rows = [serialize_approval(self.approval)]
        facts = final_approval_facts(
            rows,
            tenant_id="tenant-canary-demo",
            batch_id="PURCHASE-FLOW-DEMO-V1",
        )
        self.assertEqual(facts["approvalCount"], 1)
        self.assertEqual(facts["bankSentCount"], 0)

    def test_47_protection_counts_are_zero(self):
        facts = protection_counts()
        self.assertEqual(facts["bankMessageSendWriteCount"], 0)
        self.assertEqual(facts["paymentExecutionWriteCount"], 0)
        self.assertEqual(facts["businessProgressWriteCount"], 0)

    def test_48_final_locked_is_not_sent(self):
        approval = submit_first_approval(
            approval=self.approval,
            user=self.reviewer,
            reason="business approved",
        )
        approval = submit_second_approval(
            approval=approval,
            user=self.fund_owner,
            reason="fund approved",
        )
        row = serialize_approval(approval)
        self.assertFalse(row["finalApprovalMeansSent"])
        self.assertFalse(row["bankSent"])

    def test_49_trace_api_five_surfaces(self):
        response = self.client.get(
            "/api/finance/bank-send-chain-traces/"
        ).json()["data"]
        expected = response["traceFacts"]["recordCount"]
        self.assertEqual(response["diagnosticFacts"]["recordCount"], expected)
        self.assertEqual(response["strictFacts"]["recordCount"], expected)
        self.assertEqual(response["acceptanceFacts"]["recordCount"], expected)

    def test_50_approval_api_five_surfaces(self):
        response = self.client.get(
            "/api/finance/bank-send-final-approvals/"
        ).json()["data"]
        expected = response["approvalFacts"]["recordCount"]
        self.assertEqual(response["diagnosticFacts"]["recordCount"], expected)
        self.assertEqual(response["strictFacts"]["recordCount"], expected)
        self.assertEqual(response["acceptanceFacts"]["recordCount"], expected)
        self.assertEqual(response["acceptanceFacts"]["acceptanceStatus"], "PASS")
