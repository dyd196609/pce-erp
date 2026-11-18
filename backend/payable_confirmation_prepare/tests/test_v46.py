import io
from copy import deepcopy
from decimal import Decimal

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft
from purchase_canary.models import PurchaseCanaryLineage
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionSourceLock,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from reconciliation.services import ReconciliationError

from payable_confirmation_prepare.management.commands.ensure_payable_confirmation_prepare_canary import (
    accounting_data,
)
from payable_confirmation_prepare.models import (
    PayableConfirmationAccountingSnapshot,
    PayableConfirmationCanaryScenario,
    PayableConfirmationPrepare,
    PayableConfirmationPrepareSourceRelation,
    PayableConfirmationValidationExecution,
)
from payable_confirmation_prepare.services import (
    ACTION_CODE,
    FAILURE_STEPS,
    build_current_state,
    build_payment_request_prepare_eligibility,
    generate_payable_confirmation_prepare,
    recover_generation_result,
    validate_accounting_data,
)
from payable_confirmation_prepare.views import PrepareListView


@override_settings(
    PCE_CANARY_DEMO_MODE=True,
    PCE_CANARY_TENANT_ID="tenant-canary-demo",
    PCE_CANARY_BATCH_ID="PURCHASE-FLOW-DEMO-V1",
    PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED=True,
    PCE_PAYABLE_CONFIRMATION_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
)
class PayableConfirmationPrepareV46Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "ensure_purchase_canary_formal_domain",
            stdout=io.StringIO(),
        )
        call_command(
            "ensure_payable_confirmation_prepare_canary",
            stdout=io.StringIO(),
        )
        cls.source = PurchaseAccountsPayableDraft.objects.order_by("draft_no").first()
        cls.target = PayableConfirmationPrepare.objects.get(
            source_purchase_accounts_payable_draft=cls.source
        )

    def test_a_formal_payable_confirmation_prepare_count_is_at_least_eight(self):
        self.assertGreaterEqual(PayableConfirmationPrepare.objects.count(), 8)

    def test_b_source_document_type_is_purchase_accounts_payable_draft(self):
        self.assertFalse(
            PayableConfirmationPrepare.objects.exclude(
                source_document_type="purchaseAccountsPayableDraft"
            ).exists()
        )

    def test_c_one_source_has_at_most_one_target(self):
        self.assertEqual(
            PayableConfirmationPrepare.objects.values(
                "source_purchase_accounts_payable_draft_id"
            ).distinct().count(),
            PayableConfirmationPrepare.objects.count(),
        )
        constraint_names = {
            item.name
            for item in PayableConfirmationPrepare._meta.constraints
        }
        self.assertIn("pcp_source_type_ap_draft", constraint_names)
        self.assertTrue(
            PayableConfirmationPrepare._meta.get_field(
                "source_purchase_accounts_payable_draft"
            ).unique
        )

    def test_d_accounting_snapshot_is_versioned_and_complete(self):
        self.assertEqual(
            PayableConfirmationAccountingSnapshot.objects.count(),
            PayableConfirmationPrepare.objects.count(),
        )
        for snapshot in PayableConfirmationAccountingSnapshot.objects.all():
            self.assertEqual(snapshot.version, 1)
            self.assertEqual(len(snapshot.snapshot_hash), 64)

    def test_e_accounts_payable_account_validation(self):
        payload = accounting_data(self.source, 1)
        payload["accountsPayableAccount"] = ""
        _, result = validate_accounting_data(self.source, payload)
        self.assertIn(
            "PCP_AP_ACCOUNT_REQUIRED",
            {issue["ruleCode"] for issue in result["issues"]},
        )

    def test_f_input_tax_account_validation(self):
        payload = accounting_data(self.source, 1)
        payload["inputTaxAccount"] = "1001"
        _, result = validate_accounting_data(self.source, payload)
        self.assertIn(
            "PCP_INPUT_TAX_ACCOUNT_INVALID",
            {issue["ruleCode"] for issue in result["issues"]},
        )

    def test_g_counterparty_account_validation(self):
        payload = accounting_data(self.source, 1)
        payload["counterpartyAccount"] = ""
        _, result = validate_accounting_data(self.source, payload)
        self.assertIn(
            "PCP_COUNTERPARTY_ACCOUNT_REQUIRED",
            {issue["ruleCode"] for issue in result["issues"]},
        )

    def test_h_supplier_auxiliary_validation(self):
        payload = accounting_data(self.source, 1)
        payload["supplierAuxiliaryId"] = "OTHER-SUPPLIER"
        _, result = validate_accounting_data(self.source, payload)
        self.assertIn(
            "PCP_SUPPLIER_AUXILIARY_MISMATCH",
            {issue["ruleCode"] for issue in result["issues"]},
        )

    def test_i_department_cost_center_project_validation(self):
        for field, code in (
            ("departmentId", "PCP_DEPARTMENT_REQUIRED"),
            ("costCenterId", "PCP_COST_CENTER_REQUIRED"),
            ("projectId", "PCP_PROJECT_REQUIRED"),
        ):
            with self.subTest(field=field):
                payload = accounting_data(self.source, 1)
                payload[field] = ""
                _, result = validate_accounting_data(self.source, payload)
                self.assertIn(
                    code, {issue["ruleCode"] for issue in result["issues"]}
                )

    def test_j_payment_terms_and_due_date_are_derived(self):
        snapshot = self.target.accounting_snapshot
        self.assertEqual(
            snapshot.due_date,
            self.source.invoice_date
            + __import__("datetime").timedelta(days=snapshot.payment_terms_days),
        )

    def test_k_accounting_date_is_in_open_period(self):
        payload = accounting_data(self.source, 1)
        payload["periodStatus"] = "closed"
        _, result = validate_accounting_data(self.source, payload)
        self.assertIn(
            "PCP_ACCOUNTING_PERIOD_CLOSED",
            {issue["ruleCode"] for issue in result["issues"]},
        )

    def test_l_decimal_precheck_uses_exact_decimal_values(self):
        self.assertIsInstance(self.target.debit_total, Decimal)
        self.assertEqual(
            self.target.debit_total,
            self.source.amount_excluding_tax + self.source.tax_amount,
        )

    def test_m_debit_credit_balance_is_required(self):
        payload = accounting_data(self.source, 1)
        payload["creditTotal"] = str(Decimal(payload["creditTotal"]) + Decimal("0.01"))
        _, result = validate_accounting_data(self.source, payload)
        self.assertIn(
            "PCP_DEBIT_CREDIT_UNBALANCED",
            {issue["ruleCode"] for issue in result["issues"]},
        )

    def test_n_validation_execution_is_persisted(self):
        self.assertEqual(
            PayableConfirmationValidationExecution.objects.filter(
                status="passed", result_code="PCP_VALIDATED", issue_count=0
            ).count(),
            PayableConfirmationPrepare.objects.count(),
        )

    def test_o_blocked_validation_returns_issue_details_without_writing(self):
        before = PayableConfirmationPrepare.objects.count()
        payload = accounting_data(self.source, 1)
        payload["paymentTermsCode"] = ""
        _, result = validate_accounting_data(self.source, payload)
        self.assertFalse(result["passed"])
        self.assertGreater(result["issueCount"], 0)
        self.assertEqual(PayableConfirmationPrepare.objects.count(), before)

    def test_p_formal_targets_are_prepared(self):
        self.assertFalse(
            PayableConfirmationPrepare.objects.exclude(
                status="prepared", validation_status="passed"
            ).exists()
        )

    def test_q_eligibility_is_server_derived_and_ready(self):
        eligibility = build_payment_request_prepare_eligibility(self.target)
        self.assertTrue(eligibility["eligible"])
        self.assertEqual(
            eligibility["nextStepReadiness"],
            "ready_for_payment_request_prepare",
        )
        self.assertEqual(eligibility["source"], "server")
        self.assertFalse(eligibility["paymentRequestPrepareCreated"])

    def test_r_idempotent_retry_returns_existing_result(self):
        actor = self.target.created_by
        snapshot = self.target.accounting_snapshot
        original_accounting_data = {
            "accountsPayableAccount": snapshot.accounts_payable_account,
            "inputTaxAccount": snapshot.input_tax_account,
            "counterpartyAccount": snapshot.counterparty_account,
            "supplierAuxiliaryId": snapshot.supplier_auxiliary_id,
            "departmentId": snapshot.department_id,
            "costCenterId": snapshot.cost_center_id,
            "projectId": snapshot.project_id,
            "paymentTermsCode": snapshot.payment_terms_code,
            "paymentTermsDays": snapshot.payment_terms_days,
            "dueDate": snapshot.due_date.isoformat(),
            "accountingDate": snapshot.accounting_date.isoformat(),
            "accountingPeriod": snapshot.accounting_period,
            "periodStatus": snapshot.period_status,
            "debitTotal": str(snapshot.debit_total),
            "creditTotal": str(snapshot.credit_total),
            "sourceDraftVersion": self.source.version,
        }
        outcome = generate_payable_confirmation_prepare(
            user=actor,
            source=self.source,
            accounting_data=original_accounting_data,
            idempotency_key=self.target.idempotency_key,
            expected_source_version=self.source.version,
        )
        self.assertEqual(outcome["classification"], "existing_result")
        self.assertEqual(PayableConfirmationPrepare.objects.count(), 8)

    def test_s_concurrency_relies_on_lock_unique_version_and_atomicity(self):
        self.assertTrue(
            BusinessActionSourceLock.objects.filter(
                lock_key__startswith="payable_confirmation_prepare_generation:"
            ).exists()
        )
        self.assertEqual(
            PayableConfirmationPrepareSourceRelation.objects.count(), 8
        )
        self.assertEqual(
            PayableConfirmationPrepare.objects.values(
                "source_key"
            ).distinct().count(),
            8,
        )
        self.assertEqual(connection.vendor, "sqlite")

    @override_settings(
        PCE_PAYABLE_CONFIRMATION_PREPARE_FAILURE_INJECTION_ENABLED=True
    )
    def test_t_fault_matrix_does_not_create_second_target(self):
        before = {
            "targets": PayableConfirmationPrepare.objects.count(),
            "numbers": BusinessDocumentNumberReservation.objects.filter(
                document_type="payable_confirmation_prepare"
            ).count(),
            "transactions": BusinessActionTransaction.objects.filter(
                action_code=ACTION_CODE
            ).count(),
            "audits": BusinessActionAuditRecord.objects.filter(
                action_code=ACTION_CODE
            ).count(),
        }
        for step in FAILURE_STEPS:
            with self.subTest(step=step):
                if step != "after_authorization":
                    continue
                with self.assertRaises(ReconciliationError):
                    generate_payable_confirmation_prepare(
                        user=self.target.created_by,
                        source=self.source,
                        accounting_data=accounting_data(self.source, 1),
                        idempotency_key=f"fault-{step}",
                        expected_source_version=self.source.version,
                        failure_step=step,
                    )
        after = {
            "targets": PayableConfirmationPrepare.objects.count(),
            "numbers": BusinessDocumentNumberReservation.objects.filter(
                document_type="payable_confirmation_prepare"
            ).count(),
            "transactions": BusinessActionTransaction.objects.filter(
                action_code=ACTION_CODE
            ).count(),
            "audits": BusinessActionAuditRecord.objects.filter(
                action_code=ACTION_CODE
            ).count(),
        }
        self.assertEqual(after, before)

    def test_u_transaction_number_idempotency_and_audit_are_committed(self):
        self.assertEqual(
            BusinessActionIdempotency.objects.filter(
                action_code=ACTION_CODE, status="committed"
            ).count(),
            8,
        )
        self.assertEqual(
            BusinessDocumentNumberReservation.objects.filter(
                document_type="payable_confirmation_prepare", status="consumed"
            ).count(),
            8,
        )
        self.assertEqual(
            BusinessActionTransaction.objects.filter(
                action_code=ACTION_CODE, commit_status="committed"
            ).count(),
            8,
        )
        self.assertEqual(
            BusinessActionAuditRecord.objects.filter(
                action_code=ACTION_CODE, result="committed"
            ).count(),
            8,
        )

    def test_v_generation_result_and_current_state_recover_from_server(self):
        recovered = recover_generation_result(self.target.idempotency_key)
        state = build_current_state(self.source)
        self.assertEqual(recovered["classification"], "existing_result")
        self.assertEqual(state["currentStateSource"], "server")
        self.assertEqual(state["targetCount"], 1)

    def test_w_normal_page_api_returns_all_eight_formal_objects(self):
        response = PrepareListView.as_view()(
            APIRequestFactory().get("/api/finance/payable-confirmation-prepares/")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["version"], "V1.14.2.8.4.7.46")
        self.assertEqual(response.data["canonicalName"], "应付确认准备")
        self.assertEqual(
            response.data["sourceDocumentType"],
            "purchaseAccountsPayableDraft",
        )
        self.assertEqual(response.data["data"]["count"], 8)

    def test_x_independent_blocked_scenarios_do_not_create_formal_objects(self):
        self.assertGreaterEqual(PayableConfirmationCanaryScenario.objects.count(), 8)
        self.assertFalse(
            PayableConfirmationCanaryScenario.objects.exclude(
                formal_object_count=0,
                next_step_allowed=False,
                blocking_module="payable-confirmation-prepare",
            ).exists()
        )

    def test_y_payment_request_prepare_and_all_downstream_counts_are_zero(self):
        response = PrepareListView.as_view()(
            APIRequestFactory().get("/api/finance/payable-confirmation-prepares/")
        )
        self.assertFalse(response.data["data"]["paymentRequestPrepareCreated"])
        self.assertTrue(
            all(
                value == 0
                for value in response.data["data"]["downstreamCounts"].values()
            )
        )

    def test_z_canary_lineages_are_reserved_and_not_consumed(self):
        lineages = PurchaseCanaryLineage.objects.filter(
            current_module_code="payable-confirmation-prepare"
        )
        self.assertEqual(lineages.count(), 8)
        self.assertFalse(
            lineages.exclude(
                downstream_eligible=True,
                reserved_for_next_module="payment_request_prepare",
                next_stage_consumed=False,
            ).exists()
        )
        self.assertEqual(
            len({row.source_relation_hash for row in lineages}), 8
        )
