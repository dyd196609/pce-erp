import io
from decimal import Decimal

from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from payable_confirmation_prepare.models import PayableConfirmationPrepare
from purchase_canary.models import PurchaseCanaryLineage
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionSourceLock,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)

from payment_request_prepare.models import (
    PayeeBankAccountAuthority,
    PayerBankAccountAuthority,
    PaymentCalendarAuthority,
    PaymentHoldAuthority,
    PaymentMethodAuthority,
    PaymentRequestDataSnapshot,
    PaymentRequestPrepare,
    PaymentRequestPrepareCanaryScenario,
    PaymentRequestPrepareSourceRelation,
    PaymentRequestPrepareSourceSnapshot,
    PaymentRequestPrepareValidationExecution,
)
from payment_request_prepare.services import (
    GENERATE_ACTION,
    SAVE_ACTION,
    VALIDATE_ACTION,
    build_current_state,
    build_payment_request_eligibility,
    recover_action_result,
    save_payment_request_prepare_data,
    validate_payment_elements,
)
from workflow_runtime.state_transitions import create_business_object_with_initial_state
from payment_request_prepare.views import PrepareListView


@override_settings(
    PCE_CANARY_DEMO_MODE=True,
    PCE_CANARY_TENANT_ID="tenant-canary-demo",
    PCE_CANARY_BATCH_ID="PURCHASE-FLOW-DEMO-V1",
    PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED=True,
    PCE_PURCHASE_RECONCILIATION_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FEATURE_ENABLED=True,
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED=True,
    PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED=True,
    PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
)
class PaymentRequestPrepareV47Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("ensure_purchase_canary_formal_domain", stdout=io.StringIO())
        call_command("ensure_payable_confirmation_prepare_canary", stdout=io.StringIO())
        call_command("ensure_payment_request_prepare_canary", stdout=io.StringIO())
        cls.target = PaymentRequestPrepare.objects.order_by("prepare_no").first()
        cls.source = cls.target.source_payable_confirmation_prepare
        cls.data = cls.target.payment_data_snapshots.get(
            payment_data_version=cls.target.current_payment_data_version
        )

    def test_a_h_eight_independent_success_chains_are_prepared(self):
        self.assertEqual(PaymentRequestPrepare.objects.count(), 8)
        self.assertFalse(PaymentRequestPrepare.objects.exclude(
            status="prepared",
            payment_data_status="complete",
            validation_status="passed",
            validation_result_code="validated",
            validation_issue_count=0,
        ).exists())

    def test_i_unique_direct_source_is_payable_confirmation_prepare(self):
        self.assertFalse(PaymentRequestPrepare.objects.exclude(
            source_document_type="payableConfirmationPrepare"
        ).exists())
        self.assertEqual(
            PaymentRequestPrepare.objects.values(
                "source_payable_confirmation_prepare_id"
            ).distinct().count(),
            8,
        )

    def test_j_source_snapshot_is_immutable_and_complete(self):
        self.assertEqual(PaymentRequestPrepareSourceSnapshot.objects.count(), 8)
        snapshot = self.target.source_snapshot
        self.assertEqual(len(snapshot.source_confirmation_hash), 64)
        with self.assertRaises(ValueError):
            snapshot.save()

    def test_k_payment_data_snapshot_is_versioned_masked_and_immutable(self):
        self.assertEqual(PaymentRequestDataSnapshot.objects.count(), 8)
        self.assertIn("****", self.data.payee_account_no_masked)
        self.assertIn("****", self.data.payer_account_no_masked)
        self.assertNotRegex(self.data.payee_account_no_masked, r"^\d{12,}$")
        with self.assertRaises(ValueError):
            self.data.save()

    def test_l_independent_authority_providers_are_persisted(self):
        self.assertGreaterEqual(PayeeBankAccountAuthority.objects.count(), 1)
        self.assertGreaterEqual(PayerBankAccountAuthority.objects.count(), 1)
        self.assertEqual(PaymentMethodAuthority.objects.count(), 1)
        self.assertGreaterEqual(PaymentCalendarAuthority.objects.count(), 1)
        self.assertEqual(PaymentHoldAuthority.objects.count(), 8)
        evidence = self.data.authority_evidence
        self.assertEqual(len({row["provider"] for row in evidence.values()}), 5)
        self.assertEqual(len({row["repository"] for row in evidence.values()}), 5)

    def test_m_decimal_amount_equals_source_payable_amount(self):
        self.assertIsInstance(self.target.payment_amount, Decimal)
        self.assertEqual(self.target.payment_amount, self.target.payable_amount)
        self.assertGreater(self.target.payment_amount, 0)

    def test_n_validation_rules_are_stable_and_pass(self):
        evidence = self.data.authority_evidence

        class E:
            def __init__(self, row):
                self.payload = row["payload"]

        rules = validate_payment_elements(
            self.target,
            self.data,
            {key: E(row) for key, row in evidence.items()},
        )
        self.assertEqual(len(rules), 12)
        self.assertTrue(all(rule["status"] == "passed" for rule in rules))

    def test_o_validation_execution_and_zero_issues_are_persisted(self):
        self.assertEqual(PaymentRequestPrepareValidationExecution.objects.count(), 8)
        self.assertFalse(
            PaymentRequestPrepareValidationExecution.objects.exclude(
                status="passed", result_code="validated", issue_count=0
            ).exists()
        )

    def test_p_prepared_is_only_release_status(self):
        eligibility = build_payment_request_eligibility(self.target)
        self.assertTrue(eligibility["eligible"])
        self.assertEqual(
            eligibility["nextStepReadiness"],
            "ready_for_payment_request",
        )
        self.assertEqual(eligibility["source"], "server")
        self.assertFalse(eligibility["paymentRequestCreated"])

    def test_q_prepared_data_is_immutable(self):
        with self.assertRaisesMessage(
            Exception,
            "Prepared payment request prepare data is immutable",
        ):
            save_payment_request_prepare_data(
                user=self.target.created_by,
                obj=self.target,
                payload={
                    "payeeBankAccountId": self.data.payee_bank_account_id,
                    "payerBankAccountId": self.data.payer_bank_account_id,
                    "paymentMethodCode": self.data.payment_method_code,
                    "plannedPaymentDate": self.data.planned_payment_date.isoformat(),
                    "paymentAmount": str(self.data.payment_amount),
                    "paymentPurpose": self.data.payment_purpose,
                    "paymentSummary": self.data.payment_summary,
                },
                idempotency_key="immutable-attempt",
                expected_version=self.target.version,
                expected_payment_data_version=self.target.current_payment_data_version,
                explicit_user_action=True,
            )

    def test_r_database_hard_unique_source_constraint_fires(self):
        original = self.target
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_business_object_with_initial_state(
                model=PaymentRequestPrepare,
                initial_state="draft",
                prepare_no="PRP-DUPLICATE",
                source_payable_confirmation_prepare=original.source_payable_confirmation_prepare,
                source_payable_confirmation_prepare_no=original.source_payable_confirmation_prepare_no,
                source_confirmation_version=original.source_confirmation_version,
                source_accounting_data_version=original.source_accounting_data_version,
                source_validation_version=original.source_validation_version,
                source_ap_draft_id=original.source_ap_draft_id,
                source_ap_draft_no=original.source_ap_draft_no,
                source_invoice_prepare_id=original.source_invoice_prepare_id,
                source_invoice_prepare_no=original.source_invoice_prepare_no,
                source_reconciliation_id=original.source_reconciliation_id,
                source_reconciliation_no=original.source_reconciliation_no,
                source_key="duplicate-source-key",
                tenant_id=original.tenant_id,
                company_id=original.company_id,
                supplier_id=original.supplier_id,
                supplier_name=original.supplier_name,
                legal_entity_id=original.legal_entity_id,
                legal_entity_name=original.legal_entity_name,
                ledger_book_id=original.ledger_book_id,
                currency=original.currency,
                payable_amount=original.payable_amount,
                idempotency_key="duplicate",
                number_reservation=original.number_reservation,
                business_transaction=original.business_transaction,
                created_by=original.created_by,
            )

    def test_s_source_relation_constraints_are_present(self):
        self.assertEqual(PaymentRequestPrepareSourceRelation.objects.count(), 8)
        names = {item.name for item in PaymentRequestPrepareSourceRelation._meta.constraints}
        self.assertIn("uniq_prp_target_source", names)
        self.assertIn("uniq_prp_source_generated", names)

    def test_t_shared_idempotency_number_transaction_and_audit_are_committed(self):
        self.assertEqual(BusinessActionIdempotency.objects.filter(
            action_code=GENERATE_ACTION, status="committed"
        ).count(), 8)
        self.assertEqual(BusinessActionIdempotency.objects.filter(
            action_code=SAVE_ACTION, status="committed"
        ).count(), 8)
        self.assertEqual(BusinessActionIdempotency.objects.filter(
            action_code=VALIDATE_ACTION, status="committed"
        ).count(), 8)
        self.assertEqual(BusinessDocumentNumberReservation.objects.filter(
            document_type="payment_request_prepare", status="consumed"
        ).count(), 8)
        self.assertEqual(BusinessActionTransaction.objects.filter(
            action_code__in=[GENERATE_ACTION, SAVE_ACTION, VALIDATE_ACTION],
            commit_status="committed",
        ).count(), 24)
        self.assertEqual(BusinessActionAuditRecord.objects.filter(
            action_code__in=[GENERATE_ACTION, SAVE_ACTION, VALIDATE_ACTION],
            result="committed",
        ).count(), 24)

    def test_u_idempotency_recovery_returns_existing_result(self):
        recovered = recover_action_result(GENERATE_ACTION, self.target.idempotency_key)
        self.assertEqual(recovered["classification"], "existing_result")
        self.assertEqual(recovered["data"]["prepareNo"], self.target.prepare_no)

    def test_v_sqlite_concurrency_claim_is_accurate(self):
        self.assertEqual(connection.vendor, "sqlite")
        self.assertTrue(BusinessActionSourceLock.objects.filter(
            lock_key__startswith="payment_request_prepare_"
        ).exists())
        evidence = self.target.audit_record.evidence["sqliteConcurrency"]
        self.assertTrue(evidence["transactionAtomic"])
        self.assertTrue(evidence["hardUniqueConstraint"])
        self.assertTrue(evidence["optimisticSourceVersion"])
        self.assertTrue(evidence["persistentSourceLock"])
        self.assertFalse(evidence["rowLockClaimed"])

    def test_w_normal_page_api_uses_server_read_model(self):
        response = PrepareListView.as_view()(
            APIRequestFactory().get("/api/finance/payment-request-prepares/")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["version"], "V1.14.2.8.4.7.55")
        self.assertEqual(response.data["canonicalName"], "付款申请准备")
        self.assertEqual(response.data["sourceDocumentType"], "payableConfirmationPrepare")
        self.assertEqual(response.data["currentStateSource"], "server")
        self.assertEqual(response.data["data"]["count"], 8)

    def test_w2_historical_formal_objects_remain_visible_after_chain_advances(self):
        prepares = list(PaymentRequestPrepare.objects.order_by("prepare_no"))
        lineages = list(PurchaseCanaryLineage.objects.order_by("scenario_code"))
        self.assertEqual(len(prepares), 8)
        self.assertEqual(len(lineages), 8)
        for index, (prepare, lineage) in enumerate(
            zip(prepares, lineages, strict=True),
            1,
        ):
            upstream = list(lineage.upstream_object_nos or [])
            if prepare.prepare_no not in upstream:
                upstream.append(prepare.prepare_no)
            lineage.upstream_object_nos = upstream
            lineage.current_module_code = "payment-order-draft"
            lineage.current_object_no = f"POD-V5511-{index:02d}"
            lineage.downstream_eligible = True
            lineage.save(update_fields=[
                "upstream_object_nos",
                "current_module_code",
                "current_object_no",
                "downstream_eligible",
                "updated_at",
            ])

        response = PrepareListView.as_view()(
            APIRequestFactory().get("/api/finance/payment-request-prepares/")
        )
        rows = response.data["data"]["results"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 8)
        self.assertTrue(all(row["lineagePosition"] == "historical" for row in rows))
        self.assertTrue(all(row["nextStageConsumed"] for row in rows))

    def test_x_blocked_scenarios_are_independent_and_not_capacity(self):
        self.assertEqual(PaymentRequestPrepareCanaryScenario.objects.count(), 12)
        self.assertFalse(PaymentRequestPrepareCanaryScenario.objects.exclude(
            formal_object_count=0,
            next_step_allowed=False,
            blocking_module="payment-request-prepare",
        ).exists())

    def test_y_refresh_state_is_server_derived(self):
        state = build_current_state(self.source)
        self.assertEqual(state["currentStateSource"], "server")
        self.assertEqual(state["targetCount"], 1)
        self.assertEqual(state["paymentRequestPrepare"]["status"], "prepared")

    def test_z_payment_request_and_all_downstream_objects_are_zero(self):
        response = PrepareListView.as_view()(
            APIRequestFactory().get("/api/finance/payment-request-prepares/")
        )
        self.assertFalse(response.data["data"]["paymentRequestCreated"])
        self.assertTrue(all(
            count == 0
            for count in response.data["data"]["downstreamCounts"].values()
        ))
        lineages = PurchaseCanaryLineage.objects.filter(
            current_module_code="payment-request-prepare"
        )
        self.assertEqual(lineages.count(), 8)
        self.assertFalse(lineages.exclude(
            downstream_eligible=True,
            reserved_for_next_module="payment_request",
            next_stage_consumed=False,
        ).exists())
