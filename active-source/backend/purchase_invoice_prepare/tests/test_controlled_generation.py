import hashlib
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
    PurchaseReconciliation,
    PurchaseReconciliationCheckExecution,
    PurchaseReconciliationEvidence,
)
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)
from reconciliation.services import ReconciliationError
from reconciliation.tests.test_production_persistence import make_user

from purchase_invoice_prepare.models import (
    PurchaseInvoicePrepare,
    PurchaseInvoicePrepareSourceRelation,
)
from purchase_invoice_prepare.services import (
    ACTION_CODE,
    FAILURE_STEPS,
    build_business_gate,
    generate_purchase_invoice_prepare,
    recover_generation_result,
)


ACTIVE = override_settings(
    PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS={"tenant-v43"},
    PCE_PURCHASE_INVOICE_PREPARE_FAILURE_INJECTION_ENABLED=True,
)


def make_matched_reconciliation(user, suffix="a", **overrides):
    values = {
        "reconciliation_no": f"PRC-V43-{suffix}",
        "tenant_id": "tenant-v43",
        "company_id": 43,
        "source_key": f"supplier-settlement:tenant-v43:{suffix}",
        "source_supplier_settlement_no": f"SET-{suffix}",
        "source_payable_check_no": f"PAY-{suffix}",
        "source_payable_prepare_no": f"PAY-PREP-{suffix}",
        "purchase_order_no": f"PO-{suffix}",
        "price_approval_no": f"PRICE-{suffix}",
        "supplier_id": "SUP-43",
        "supplier_name": "V43 Canary Supplier",
        "legal_entity_id": "LEGAL-43",
        "ledger_book_id": "LEDGER-43",
        "currency": "CNY",
        "exchange_rate": Decimal("1.00000000"),
        "accounting_period": "2026-07",
        "settlement_amount": Decimal("100.00"),
        "quantity": Decimal("10.0000"),
        "unit": "EA",
        "source_candidate_id": f"candidate-{suffix}",
        "simulation_request_id": f"request-{suffix}",
        "simulation_result_id": f"result-{suffix}",
        "status": "matched",
        "source_snapshot_hash": hashlib.sha256(f"source:{suffix}".encode()).hexdigest(),
        "review_id": f"review-{suffix}",
        "review_hash": hashlib.sha256(f"review:{suffix}".encode()).hexdigest(),
        "command_id": f"command-{suffix}",
        "transaction_plan_id": "purchase-reconciliation-atomic-v1",
        "idempotency_key": f"generate-reconciliation-{suffix}",
        "created_by": user,
        "check_result_code": "PRC_CHECK_MATCHED",
        "difference_count": 0,
        "checked_at": timezone.now(),
        "checked_by": user,
        "version": 2,
    }
    values.update(overrides)
    target_status = values.pop("status", PurchaseReconciliation.Status.DRAFT)
    values["version"] = 1
    obj = create_business_object_with_initial_state(
        model=PurchaseReconciliation,
        initial_state=PurchaseReconciliation.Status.DRAFT,
        **values,
    )
    if target_status != PurchaseReconciliation.Status.DRAFT:
        evidence_hash = hashlib.sha256(
            f"{obj.pk}:draft:{target_status}".encode()
        ).hexdigest()
        tx = BusinessActionTransaction.objects.create(
            transaction_id=f"PRC-TEST-{suffix}",
            action_code="complete_purchase_reconciliation",
            idempotency_key=f"check-{suffix}",
            tenant_id=obj.tenant_id,
            source_key=obj.source_key,
            command_id=f"PRC-TEST-CMD-{suffix}",
            transaction_plan_id="purchase-reconciliation-check-atomic-v1",
            review_id=f"check-review-{suffix}",
            review_hash=evidence_hash,
            status=BusinessActionTransaction.Status.COMMITTED,
            outcome="checked",
            commit_status="committed",
            recovery_status="not_required",
            result_hash=evidence_hash,
            reconciliation=obj,
        )
        audit = BusinessActionAuditRecord.objects.create(
            transaction=tx,
            action_code="complete_purchase_reconciliation",
            tenant_id=obj.tenant_id,
            actor=user,
            source_key=obj.source_key,
            reconciliation=obj,
            result="committed",
            target_type="purchase_reconciliation",
            target_id=obj.pk,
            target_no=obj.reconciliation_no,
            review_id=tx.review_id,
            review_hash=evidence_hash,
            command_id=tx.command_id,
            idempotency_key=f"check-{suffix}",
            actor_name=user.get_username(),
            tenant_or_scope=f"{obj.tenant_id}:company:{obj.company_id}",
            evidence_hash=evidence_hash,
            evidence={"sourceStatus": "draft", "targetStatus": target_status},
        )
        transition_business_object(
            business_object=obj,
            object_type="purchase_reconciliation",
            source_state=PurchaseReconciliation.Status.DRAFT,
            target_state=target_status,
            action_code="complete_purchase_reconciliation",
            operator=user,
            reason="Test fixture uses the governed reconciliation check transition",
            audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
            allowed_transitions={
                (
                    PurchaseReconciliation.Status.DRAFT,
                    PurchaseReconciliation.Status.MATCHED,
                ),
                (
                    PurchaseReconciliation.Status.DRAFT,
                    PurchaseReconciliation.Status.DIFFERENCE_FOUND,
                ),
                (
                    PurchaseReconciliation.Status.DRAFT,
                    PurchaseReconciliation.Status.SOURCE_MISSING,
                ),
            },
        )
    for authority_type, provider, repository in (
        ("supplier_settlement", "SupplierSettlementEvidenceProvider", "SupplierSettlementAuthorityRepository"),
        ("payable_check", "PayableCheckEvidenceProvider", "PayableCheckAuthorityRepository"),
    ):
        PurchaseReconciliationEvidence.objects.create(
            reconciliation=obj,
            provider_code=provider,
            repository_code=repository,
            authority_type=authority_type,
            authority_object_id=f"{authority_type}-{suffix}",
            authority_object_no=f"{authority_type}-NO-{suffix}",
            authority_version=1,
            business_hash=hashlib.sha256(f"{authority_type}:{suffix}".encode()).hexdigest(),
            evidence={"source": authority_type},
        )
    PurchaseReconciliationCheckExecution.objects.create(
        reconciliation=obj,
        idempotency_key=f"check-{suffix}",
        request_hash=hashlib.sha256(f"check:{suffix}".encode()).hexdigest(),
        expected_version=1,
        result_status=obj.status,
        check_result_code=obj.check_result_code,
        difference_count=obj.difference_count,
        actor=user,
        result_payload={"result": "matched"},
    )
    return obj


def generate(user, source, key="pip-a", **kwargs):
    return generate_purchase_invoice_prepare(
        user=user,
        reconciliation_id=source.pk,
        idempotency_key=key,
        expected_reconciliation_version=source.version,
        expected_check_version=source.version,
        explicit_user_action=True,
        **kwargs,
    )


@ACTIVE
class ControlledGenerationTests(TestCase):
    def setUp(self):
        self.user = make_user("v43-generator", company_id=43)

    def test_success_persists_one_draft_relation_audit_number_and_idempotency(self):
        source = make_matched_reconciliation(self.user)
        result = generate(self.user, source)
        obj = PurchaseInvoicePrepare.objects.get()
        self.assertEqual(result["classification"], "created")
        self.assertEqual(obj.status, "draft")
        self.assertEqual(obj.invoice_data_status, "not_collected")
        self.assertEqual(obj.source_document_type, "purchaseReconciliation")
        self.assertEqual(PurchaseInvoicePrepareSourceRelation.objects.count(), 1)
        self.assertEqual(BusinessActionAuditRecord.objects.filter(action_code=ACTION_CODE).count(), 1)
        self.assertEqual(BusinessActionIdempotency.objects.get(action_code=ACTION_CODE).status, "committed")
        self.assertEqual(BusinessDocumentNumberReservation.objects.get(document_type="purchase_invoice_prepare").status, "consumed")
        self.assertEqual(source.status, "matched")

    def test_same_idempotency_and_same_source_never_duplicate(self):
        source = make_matched_reconciliation(self.user, "idem")
        first = generate(self.user, source, "pip-idem")
        replay = generate(self.user, source, "pip-idem")
        other_key = generate(self.user, source, "pip-other")
        self.assertTrue(first["created"])
        self.assertEqual(replay["classification"], "existing_result")
        self.assertEqual(other_key["classification"], "existing_target")
        self.assertEqual(PurchaseInvoicePrepare.objects.count(), 1)
        self.assertEqual(BusinessActionAuditRecord.objects.filter(action_code=ACTION_CODE).count(), 1)

    def test_gate_blocks_non_matched_difference_and_incomplete_evidence(self):
        for index, override in enumerate((
            {"status": "draft"},
            {"status": "difference_found"},
            {"status": "source_missing"},
            {"check_result_code": "PRC_CHECK_DIFFERENCE_FOUND"},
            {"difference_count": 1},
        )):
            source = make_matched_reconciliation(self.user, f"gate-{index}", **override)
            with self.assertRaises(ReconciliationError) as caught:
                generate(self.user, source, f"pip-gate-{index}")
            self.assertEqual(caught.exception.code, "PIP_BUSINESS_GATE_BLOCKED")
        source = make_matched_reconciliation(self.user, "evidence")
        source.evidence_records.filter(authority_type="payable_check").delete()
        self.assertFalse(build_business_gate(source, 2, 2)["passed"])

    def test_source_and_check_versions_are_server_checked(self):
        source = make_matched_reconciliation(self.user, "version")
        with self.assertRaises(ReconciliationError) as caught:
            generate_purchase_invoice_prepare(
                user=self.user,
                reconciliation_id=source.pk,
                idempotency_key="pip-version",
                expected_reconciliation_version=1,
                expected_check_version=2,
                explicit_user_action=True,
            )
        self.assertEqual(caught.exception.code, "PIP_SOURCE_VERSION_CONFLICT")
        with self.assertRaises(ReconciliationError) as caught:
            generate_purchase_invoice_prepare(
                user=self.user,
                reconciliation_id=source.pk,
                idempotency_key="pip-check-version",
                expected_reconciliation_version=2,
                expected_check_version=1,
                explicit_user_action=True,
            )
        self.assertEqual(caught.exception.code, "PIP_CHECK_VERSION_CONFLICT")

    def test_parameterized_failure_matrix_rolls_back_all_atomic_writes(self):
        number_allocation_index = FAILURE_STEPS.index("after_number_reservation")
        for index, step in enumerate(FAILURE_STEPS):
            with self.subTest(step=step):
                source = make_matched_reconciliation(self.user, f"failure-{index}")
                with self.assertRaises(ReconciliationError):
                    generate(self.user, source, f"pip-failure-{index}", failure_step=step)
                self.assertFalse(PurchaseInvoicePrepare.objects.filter(source_purchase_reconciliation=source).exists())
                self.assertFalse(PurchaseInvoicePrepareSourceRelation.objects.filter(source_id=source.pk).exists())
                self.assertFalse(BusinessActionAuditRecord.objects.filter(action_code=ACTION_CODE, reconciliation=source).exists())
                self.assertFalse(BusinessActionTransaction.objects.filter(action_code=ACTION_CODE, reconciliation=source).exists())
                self.assertFalse(BusinessActionIdempotency.objects.filter(action_code=ACTION_CODE, source_key=f"purchaseReconciliation:{source.pk}").exists())
                reservations = BusinessDocumentNumberReservation.objects.filter(
                    document_type="purchase_invoice_prepare",
                    target=source,
                )
                if index < number_allocation_index:
                    self.assertFalse(reservations.exists())
                else:
                    self.assertEqual(reservations.count(), 1)
                    reservation = reservations.get()
                    self.assertEqual(reservation.status, "aborted")
                    self.assertIsNotNone(reservation.aborted_at)
                    self.assertTrue(reservation.abort_reason.startswith("PIP_INJECTED_"))

    def test_retry_after_aborted_number_never_reuses_failed_number(self):
        source = make_matched_reconciliation(self.user, "aborted-number")
        with self.assertRaises(ReconciliationError):
            generate(
                self.user,
                source,
                "pip-aborted-number",
                failure_step="after_number_reservation",
            )
        aborted = BusinessDocumentNumberReservation.objects.get(
            document_type="purchase_invoice_prepare",
            target=source,
            status="aborted",
        )
        result = generate(self.user, source, "pip-aborted-number")
        consumed = BusinessDocumentNumberReservation.objects.get(
            document_type="purchase_invoice_prepare",
            target=source,
            status="consumed",
        )
        self.assertNotEqual(aborted.reserved_number, consumed.reserved_number)
        self.assertEqual(result["data"]["prepareNo"], consumed.reserved_number)

    def test_recovery_reads_committed_server_result(self):
        source = make_matched_reconciliation(self.user, "recover")
        generate(self.user, source, "pip-recover")
        recovered = recover_generation_result("pip-recover")
        self.assertEqual(recovered["classification"], "existing_result")
        self.assertEqual(recovered["data"]["sourcePurchaseReconciliationId"], source.pk)

    def test_response_loss_is_commit_unknown_and_recovers_committed_result(self):
        source = make_matched_reconciliation(self.user, "commit-unknown")
        with self.assertRaises(ReconciliationError) as caught:
            generate(self.user, source, "pip-commit-unknown", failure_step="after_response_send")
        self.assertEqual(caught.exception.code, "PIP_COMMIT_UNKNOWN")
        recovered = recover_generation_result("pip-commit-unknown")
        self.assertEqual(recovered["classification"], "existing_result")
        self.assertEqual(PurchaseInvoicePrepare.objects.filter(source_purchase_reconciliation=source).count(), 1)


@ACTIVE
class ControlledGenerationApiTests(TestCase):
    def setUp(self):
        self.user = make_user("v43-api", company_id=43)
        self.source = make_matched_reconciliation(self.user, "api")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_api_contract_list_detail_by_source_generate_and_result(self):
        before = self.client.get(
            f"/api/scm/purchase-invoice-prepares/by-source/{self.source.pk}"
        ).data["data"]
        self.assertEqual(before["targetExistenceStatus"], "no_target")
        self.assertEqual(before["targetCount"], 0)
        self.assertTrue(before["generationAllowed"])
        self.assertEqual(before["generationStatus"], "not_started")
        self.assertEqual(before["currentIdempotencyStatus"], "not_started")
        self.assertEqual(before["currentNumberReservationStatus"], "not_allocated")
        self.assertEqual(before["currentTransactionStatus"], "not_started")
        self.assertEqual(before["currentStateSource"], "server")
        payload = {
            "sourcePurchaseReconciliationId": self.source.pk,
            "idempotencyKey": "pip-api",
            "expectedReconciliationVersion": 2,
            "expectedCheckVersion": 2,
            "explicitUserAction": True,
        }
        created = self.client.post("/api/scm/purchase-invoice-prepares/generate", payload, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["classification"], "created")
        obj_id = created.data["data"]["id"]
        self.assertEqual(self.client.get("/api/scm/purchase-invoice-prepares/").data["data"]["count"], 1)
        detail = self.client.get(
            f"/api/scm/purchase-invoice-prepares/{obj_id}"
        ).data["data"]
        self.assertEqual(detail["status"], "draft")
        self.assertEqual(detail["currentState"]["generationStatus"], "existing_target")
        after = self.client.get(
            f"/api/scm/purchase-invoice-prepares/by-source/{self.source.pk}"
        ).data["data"]
        self.assertEqual(after["count"], 1)
        self.assertEqual(after["targetExistenceStatus"], "single_target")
        self.assertFalse(after["generationAllowed"])
        self.assertEqual(after["generationStatus"], "existing_target")
        self.assertEqual(after["currentIdempotencyStatus"], "committed")
        self.assertEqual(after["currentNumberReservationStatus"], "consumed")
        self.assertEqual(after["currentTransactionStatus"], "committed")
        self.assertEqual(after["currentAuditStatus"], "committed")
        self.assertEqual(after["currentSourceRelationStatus"], "generated_from")
        recovered = self.client.get(
            "/api/scm/purchase-invoice-prepares/generation-results/pip-api"
        ).data
        self.assertEqual(recovered["classification"], "existing_result")
        self.assertEqual(recovered["currentState"]["targetCount"], 1)
        self.assertEqual(recovered["currentState"]["currentStateSource"], "server")

    def test_client_cannot_submit_server_derived_fields(self):
        response = self.client.post(
            "/api/scm/purchase-invoice-prepares/generate",
            {
                "sourcePurchaseReconciliationId": self.source.pk,
                "idempotencyKey": "pip-forbidden",
                "expectedReconciliationVersion": 2,
                "expectedCheckVersion": 2,
                "explicitUserAction": True,
                "status": "draft",
                "eligible": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "PIP_CLIENT_DERIVED_FIELD_FORBIDDEN")

    @override_settings(PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED=False)
    def test_feature_flag_is_server_enforced(self):
        response = self.client.post(
            "/api/scm/purchase-invoice-prepares/generate",
            {
                "sourcePurchaseReconciliationId": self.source.pk,
                "idempotencyKey": "pip-disabled",
                "expectedReconciliationVersion": 2,
                "expectedCheckVersion": 2,
                "explicitUserAction": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["classification"], "feature_disabled")
