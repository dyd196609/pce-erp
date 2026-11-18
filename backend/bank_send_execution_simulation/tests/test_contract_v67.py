import hashlib

from django.core.exceptions import ValidationError
from django.test import override_settings

from system.models import User
from workflow_runtime.models import UserOrganizationRoleAuthority
from workflow_runtime.state_transitions import transition_business_object

from bank_send_execution_simulation.models import (
    BankSendChainTrace,
    BankSendExecutionSimulation,
    BankSendDualIsolationCheck,
    BankSendProductionReleaseDecision,
    BankSendProductionReleaseReview,
)
from bank_send_execution_simulation.v66 import (
    BUSINESS_REVIEWER_ROLE,
    FUND_OWNER_ROLE as FINAL_FUND_OWNER_ROLE,
    create_final_approval,
    ensure_chain_traces,
    submit_first_approval,
    submit_second_approval,
)
from bank_send_execution_simulation.v67 import (
    BUSINESS_OWNER_ROLE,
    FUND_OWNER_ROLE,
    REVIEW_TRANSITIONS,
    SECURITY_OWNER_ROLE,
    create_dual_isolation_check,
    create_release_review,
    dual_isolation_facts,
    evaluate_dual_isolation,
    evaluate_release_checks,
    protection_counts,
    release_review_facts,
    serialize_isolation_check,
    serialize_release_review,
    submit_release_decision,
)

from .test_contract_v65 import (
    BankSendSimulationIsolationV65Tests,
    V65_SETTINGS,
)


@override_settings(**V65_SETTINGS)
class BankSendProductionReleaseV67Tests(
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
            username="v67-final-reviewer",
            real_name="V67 Final Reviewer",
            company_id=self.operator.company_id,
        )
        self.fund_owner = User.objects.create_user(
            username="v67-final-fund-owner",
            real_name="V67 Final Fund Owner",
            company_id=self.operator.company_id,
        )
        for user, role in (
            (self.reviewer, BUSINESS_REVIEWER_ROLE),
            (self.fund_owner, FINAL_FUND_OWNER_ROLE),
        ):
            UserOrganizationRoleAuthority.objects.create(
                user=user,
                role_code=role,
                legal_entity_id=legal_entity,
                department_id="V67-FINAL",
                active=True,
                version=1,
                business_hash=hashlib.sha256(
                    f"{user.pk}:{role}:final".encode()
                ).hexdigest(),
            )
        self.approval = submit_first_approval(
            approval=self.approval,
            user=self.reviewer,
            reason="business approved",
        )
        self.approval = submit_second_approval(
            approval=self.approval,
            user=self.fund_owner,
            reason="fund approved",
        )
        self.isolation_check = create_dual_isolation_check(
            approval=self.approval, user=self.operator
        )
        self.review = create_release_review(
            approval=self.approval,
            isolation_check=self.isolation_check,
            user=self.operator,
        )
        self.release_users = {}
        for stage, role in (
            ("business", BUSINESS_OWNER_ROLE),
            ("fund", FUND_OWNER_ROLE),
            ("security", SECURITY_OWNER_ROLE),
        ):
            user = User.objects.create_user(
                username=f"v67-{stage}",
                real_name=f"V67 {stage}",
                company_id=self.operator.company_id,
            )
            UserOrganizationRoleAuthority.objects.create(
                user=user,
                role_code=role,
                legal_entity_id=legal_entity,
                department_id="V67",
                active=True,
                version=1,
                business_hash=hashlib.sha256(
                    f"{user.pk}:{role}".encode()
                ).hexdigest(),
            )
            self.release_users[stage] = user

    def _lock_review(self):
        row = self.review
        for stage in ("business", "fund", "security"):
            row = submit_release_decision(
                review=row,
                user=self.release_users[stage],
                stage=stage,
                reason=f"{stage} confirmed",
            )
        return row

    def test_51_dual_isolation_passes(self):
        self.assertTrue(evaluate_dual_isolation(self.approval)["passed"])

    def test_52_dual_isolation_is_idempotent(self):
        self.assertEqual(
            create_dual_isolation_check(
                approval=self.approval, user=self.operator
            ).pk,
            self.isolation_check.pk,
        )

    def test_53_isolation_categories_all_pass(self):
        row = serialize_isolation_check(self.isolation_check)
        self.assertTrue(all(
            row[key] for key in (
                "environmentCheck",
                "credentialCheck",
                "permissionCheck",
                "interfaceCheck",
            )
        ))

    def test_54_release_checks_all_pass(self):
        checks = evaluate_release_checks(
            self.approval, self.isolation_check
        )
        self.assertTrue(checks["passed"])
        self.assertTrue(all(
            checks[f"RELEASE-{index:03d}"] for index in range(1, 11)
        ))

    def test_55_review_starts_draft(self):
        self.assertEqual(self.review.status, "draft")

    def test_56_review_is_idempotent(self):
        self.assertEqual(
            create_release_review(
                approval=self.approval,
                isolation_check=self.isolation_check,
                user=self.operator,
            ).pk,
            self.review.pk,
        )

    def test_57_business_role_required(self):
        with self.assertRaises(PermissionError):
            submit_release_decision(
                review=self.review,
                user=self.operator,
                stage="business",
                reason="denied",
            )

    def test_58_business_review_moves_to_reviewing(self):
        row = submit_release_decision(
            review=self.review,
            user=self.release_users["business"],
            stage="business",
            reason="confirmed",
        )
        self.assertEqual(row.status, "reviewing")

    def test_59_fund_review_moves_to_review_passed(self):
        row = submit_release_decision(
            review=self.review,
            user=self.release_users["business"],
            stage="business",
            reason="confirmed",
        )
        row = submit_release_decision(
            review=row,
            user=self.release_users["fund"],
            stage="fund",
            reason="confirmed",
        )
        self.assertEqual(row.status, "review_passed")

    def test_60_security_review_locks(self):
        self.assertEqual(self._lock_review().status, "locked")

    def test_61_three_users_three_roles(self):
        self._lock_review()
        rows = BankSendProductionReleaseDecision.objects.all()
        self.assertEqual(len(set(rows.values_list("operator_id", flat=True))), 3)
        self.assertEqual(len(set(rows.values_list("role", flat=True))), 3)

    def test_62_same_user_is_blocked(self):
        row = submit_release_decision(
            review=self.review,
            user=self.release_users["business"],
            stage="business",
            reason="confirmed",
        )
        with self.assertRaises(PermissionError):
            submit_release_decision(
                review=row,
                user=self.release_users["business"],
                stage="fund",
                reason="conflict",
            )

    def test_63_state_jump_blocked(self):
        with self.assertRaises(ValueError):
            transition_business_object(
                business_object=self.review,
                object_type="bank_send_production_release_review",
                source_state="draft",
                target_state="locked",
                action_code="invalid",
                operator=self.release_users["business"],
                reason="invalid",
                audit_reference="invalid",
                allowed_transitions=REVIEW_TRANSITIONS,
            )

    def test_64_direct_status_save_blocked(self):
        self.review.status = "locked"
        with self.assertRaises(ValidationError):
            self.review.save()

    def test_65_bulk_status_update_blocked(self):
        with self.assertRaises(ValidationError):
            BankSendProductionReleaseReview.objects.filter(
                pk=self.review.pk
            ).update(status="locked")

    def test_66_locked_is_not_sent(self):
        row = serialize_release_review(self._lock_review())
        self.assertFalse(row["productionReviewMeansSent"])
        self.assertFalse(row["bankSent"])

    def test_67_transition_history_complete(self):
        row = serialize_release_review(self._lock_review())
        self.assertTrue(row["stateMachineConsistent"])
        self.assertEqual(row["statusTransitionCount"], 3)

    def test_68_five_surface_fact_counts(self):
        isolation = dual_isolation_facts(
            [serialize_isolation_check(self.isolation_check)],
            tenant_id="tenant-canary-demo",
            batch_id="PURCHASE-FLOW-DEMO-V1",
        )
        review = release_review_facts(
            [serialize_release_review(self.review)],
            tenant_id="tenant-canary-demo",
            batch_id="PURCHASE-FLOW-DEMO-V1",
        )
        self.assertEqual(isolation["recordCount"], 1)
        self.assertEqual(review["recordCount"], 1)

    def test_69_protection_counts_zero(self):
        facts = protection_counts()
        self.assertEqual(facts["bankMessageSendWriteCount"], 0)
        self.assertEqual(facts["paymentExecutionWriteCount"], 0)
        self.assertEqual(facts["financialImpactWriteCount"], 0)
        self.assertEqual(facts["businessProgressWriteCount"], 0)

    def test_70_apis_are_five_surface_consistent(self):
        for url, key in (
            (
                "/api/finance/bank-send-dual-isolation-checks/",
                "isolationFacts",
            ),
            (
                "/api/finance/bank-send-production-release-reviews/",
                "reviewFacts",
            ),
        ):
            data = self.client.get(url).json()["data"]
            expected = data[key]["recordCount"]
            self.assertEqual(data["diagnosticFacts"]["recordCount"], expected)
            self.assertEqual(data["strictFacts"]["recordCount"], expected)
            self.assertEqual(data["acceptanceFacts"]["recordCount"], expected)
            self.assertEqual(
                data["acceptanceFacts"]["acceptanceStatus"], "PASS"
            )
