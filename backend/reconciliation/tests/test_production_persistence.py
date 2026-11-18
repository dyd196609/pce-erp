import hashlib
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
    PurchaseReconciliation,
    PurchaseReconciliationReview,
    PurchaseReconciliationSourceRelation,
    PurchaseReconciliationSourceSnapshot,
)
from reconciliation.services import ReconciliationError, generate_purchase_reconciliation, recover_by_idempotency
from system.models import User


ACTIVE = override_settings(
    PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED=True,
    PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_RECONCILIATION_TEST_TENANTS={"tenant-v41"},
    PCE_PURCHASE_RECONCILIATION_FAILURE_INJECTION_ENABLED=True,
)


def make_source(suffix="base", company_id=41, tenant_id="tenant-v41"):
    source_key = f"supplier-settlement:{tenant_id}:PCE-REG-{suffix}"
    snapshot_hash = hashlib.sha256(source_key.encode()).hexdigest()
    source = PurchaseReconciliationSourceSnapshot.objects.create(
        source_key=source_key, supplier_settlement_no=f"PCE-REG-{suffix}", tenant_id=tenant_id,
        company_id=company_id, supplier_id="SUP-41", supplier_name="Test Supplier 41", legal_entity_id="LEGAL-TEST-41", ledger_book_id="LEDGER-TEST-41", currency="CNY", exchange_rate=Decimal("1.00000000"),
        accounting_period="2026-07", amount=Decimal("100.00"), quantity=Decimal("10.0000"), unit="EA",
        source_payable_check_no=f"PAYABLE-{suffix}", source_payable_prepare_no=f"PREPARE-{suffix}", purchase_order_no=f"PO-{suffix}", price_approval_no=f"PRICE-{suffix}",
        source_candidate_id=f"candidate-{suffix}", simulation_request_id=f"simulation-request-{suffix}", simulation_result_id=f"simulation-result-{suffix}", lifecycle_state="reconciling",
        payable_status="payable_prepared", simulation_integrity="passed", snapshot_hash=snapshot_hash,
    )
    review = PurchaseReconciliationReview.objects.create(
        review_id=f"review-{suffix}", source=source, state="review_passed", decision="approved",
        simulation_integrity="passed", audit_complete=True, fatal_risk_count=0,
        source_snapshot_hash=snapshot_hash, business_hash=hashlib.sha256(f"review-{suffix}".encode()).hexdigest(),
        supplier_id="SUP-41", legal_entity_id="LEGAL-TEST-41", ledger_book_id="LEDGER-TEST-41", currency="CNY", amount=Decimal("100.00"),
        reviewed_at=timezone.now(),
    )
    return source, review


def make_user(username="operator", company_id=41, superuser=True):
    return User.objects.create_user(username=username, password="test", real_name=username, company_id=company_id, is_superuser=superuser, is_active=True)


@ACTIVE
class PersistenceServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_success_persists_object_relation_audit_and_committed_metadata(self):
        source, review = make_source()
        result = generate_purchase_reconciliation(user=self.user, source_key=source.source_key, final_review_id=review.review_id, idempotency_key="idem-success")
        self.assertFalse(result["replayed"])
        self.assertEqual(PurchaseReconciliation.objects.count(), 1)
        self.assertEqual(PurchaseReconciliationSourceRelation.objects.count(), 1)
        self.assertEqual(BusinessActionAuditRecord.objects.count(), 1)
        self.assertEqual(BusinessActionIdempotency.objects.get().status, "committed")
        self.assertEqual(BusinessDocumentNumberReservation.objects.get().status, "consumed")
        self.assertEqual(BusinessActionTransaction.objects.get().status, "committed")

    def test_same_idempotency_returns_same_object(self):
        source, review = make_source("idem")
        first = generate_purchase_reconciliation(user=self.user, source_key=source.source_key, final_review_id=review.review_id, idempotency_key="idem-repeat")
        second = generate_purchase_reconciliation(user=self.user, source_key=source.source_key, final_review_id=review.review_id, idempotency_key="idem-repeat")
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["replayed"])
        self.assertEqual(PurchaseReconciliation.objects.count(), 1)

    def test_idempotency_payload_conflict_rejected(self):
        first_source, first_review = make_source("conflict-a")
        second_source, second_review = make_source("conflict-b")
        generate_purchase_reconciliation(user=self.user, source_key=first_source.source_key, final_review_id=first_review.review_id, idempotency_key="idem-conflict")
        with self.assertRaises(ReconciliationError) as caught:
            generate_purchase_reconciliation(user=self.user, source_key=second_source.source_key, final_review_id=second_review.review_id, idempotency_key="idem-conflict")
        self.assertEqual(caught.exception.code, "PRC_IDEMPOTENCY_CONFLICT")

    def test_commit_unknown_is_recovered_as_committed_without_retry(self):
        source, review = make_source("unknown")
        with self.assertRaises(ReconciliationError) as caught:
            generate_purchase_reconciliation(user=self.user, source_key=source.source_key, final_review_id=review.review_id, idempotency_key="idem-unknown", failure_step="after_commit_before_response")
        self.assertEqual(caught.exception.code, "PRC_COMMIT_UNKNOWN")
        recovered = recover_by_idempotency("idem-unknown")
        self.assertEqual(recovered["classification"], "committed")
        self.assertEqual(PurchaseReconciliation.objects.count(), 1)

    def test_aborted_number_is_not_reused(self):
        failed_source, failed_review = make_source("aborted-number")
        with self.assertRaises(ReconciliationError):
            generate_purchase_reconciliation(user=self.user, source_key=failed_source.source_key, final_review_id=failed_review.review_id, idempotency_key="idem-aborted-number", failure_step="after_number_reservation")
        aborted = BusinessDocumentNumberReservation.objects.get(idempotency_key="idem-aborted-number")
        self.assertEqual(aborted.status, "aborted")
        next_source, next_review = make_source("number-after-abort")
        result = generate_purchase_reconciliation(user=self.user, source_key=next_source.source_key, final_review_id=next_review.review_id, idempotency_key="idem-number-after-abort")
        self.assertNotEqual(result["reconciliationNo"], aborted.reserved_number)

    def test_business_gate_reloads_server_state_and_rejects_stale_review(self):
        source, review = make_source("stale")
        review.source_snapshot_hash = "0" * 64; review.save(update_fields=["source_snapshot_hash"])
        with self.assertRaises(ReconciliationError) as caught:
            generate_purchase_reconciliation(user=self.user, source_key=source.source_key, final_review_id=review.review_id, idempotency_key="idem-stale")
        self.assertEqual(caught.exception.code, "PRC_BUSINESS_GATE_REJECTED")
        self.assertEqual(PurchaseReconciliation.objects.count(), 0)

    def test_fifteen_injected_failures_cover_transaction_and_commit_unknown(self):
        steps = [
            "after_authorization", "after_business_gate", "after_idempotency", "after_source_lock",
            "before_source_reload", "after_revalidation", "after_number_reservation", "after_target_insert",
            "after_relation_insert", "after_reverse_relation", "after_audit", "after_status_update",
            "after_number_consumed", "before_commit", "after_commit_before_response",
        ]
        for index, step in enumerate(steps):
            with self.subTest(step=step):
                source, review = make_source(f"failure-{index}")
                with self.assertRaises(ReconciliationError):
                    generate_purchase_reconciliation(user=self.user, source_key=source.source_key, final_review_id=review.review_id, idempotency_key=f"idem-failure-{index}", failure_step=step)
                committed = step == "after_commit_before_response"
                self.assertEqual(PurchaseReconciliation.objects.filter(source_key=source.source_key).count(), 1 if committed else 0)
                self.assertEqual(PurchaseReconciliationSourceRelation.objects.filter(source_key=source.source_key).count(), 1 if committed else 0)
                self.assertEqual(BusinessActionAuditRecord.objects.filter(source_key=source.source_key).count(), 1 if committed else 0)
                reservation = BusinessDocumentNumberReservation.objects.filter(idempotency_key=f"idem-failure-{index}").first()
                if reservation:
                    self.assertEqual(reservation.status, "consumed" if committed else "aborted")


@ACTIVE
class AuthorizationApiTests(TestCase):
    def setUp(self):
        self.source, self.review = make_source("api")
        self.url = "/api/scm/purchase-reconciliations/generate"
        self.payload = {"sourceKey": self.source.source_key, "finalReviewId": self.review.review_id, "idempotencyKey": "idem-api", "explicitUserAction": True}

    def test_unauthenticated(self):
        response = APIClient().post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["errorCode"], "PRC_AUTH_UNAUTHENTICATED")

    def test_permission_denied(self):
        user = make_user("no-permission", superuser=False)
        client = APIClient(); client.force_authenticate(user)
        response = client.post(self.url, self.payload, format="json")
        self.assertEqual(response.data["errorCode"], "PRC_AUTH_PERMISSION_DENIED")

    def test_scope_denied(self):
        user = make_user("wrong-company", company_id=99)
        client = APIClient(); client.force_authenticate(user)
        response = client.post(self.url, self.payload, format="json")
        self.assertEqual(response.data["errorCode"], "PRC_AUTH_SCOPE_DENIED")

    @override_settings(PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED=False)
    def test_feature_disabled(self):
        user = make_user("feature-user")
        client = APIClient(); client.force_authenticate(user)
        response = client.post(self.url, self.payload, format="json")
        self.assertEqual(response.data["errorCode"], "PRC_AUTH_FEATURE_DISABLED")

    def test_production_rollout_disabled(self):
        source, review = make_source("prod", tenant_id="production")
        payload = {"sourceKey": source.source_key, "finalReviewId": review.review_id, "idempotencyKey": "idem-prod", "explicitUserAction": True}
        user = make_user("prod-user")
        client = APIClient(); client.force_authenticate(user)
        response = client.post(self.url, payload, format="json")
        self.assertEqual(response.data["errorCode"], "PRC_AUTH_PRODUCTION_ROLLOUT_DISABLED")

    def test_authorized_test_tenant_succeeds_and_read_apis_return_fact(self):
        user = make_user("api-authorized", superuser=False)
        user.user_permissions.add(Permission.objects.get(codename="generate_purchase_reconciliation"))
        client = APIClient(); client.force_authenticate(user)
        response = client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 201)
        result = client.get("/api/scm/purchase-reconciliations/generation-results/idem-api")
        by_source = client.get(f"/api/scm/purchase-reconciliations/by-source/{self.source.source_key}")
        self.assertEqual(result.data["data"]["classification"], "committed")
        self.assertEqual(by_source.data["data"]["sourceKey"], self.source.source_key)


@ACTIVE
class DatabaseConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user("constraint-user")
        self.source, self.review = make_source("constraints")
        generate_purchase_reconciliation(user=self.user, source_key=self.source.source_key, final_review_id=self.review.review_id, idempotency_key="idem-constraints")

    def test_hard_unique_idempotency(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BusinessActionIdempotency.objects.create(action_code="generate_purchase_reconciliation", idempotency_key="idem-constraints", tenant_id="tenant-v41", source_key="other", request_hash="x", status="in_progress")

    def test_hard_unique_source_relation(self):
        obj = PurchaseReconciliation.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PurchaseReconciliationSourceRelation.objects.create(reconciliation=obj, source_key=self.source.source_key, source_snapshot_hash=self.source.snapshot_hash)

    def test_hard_unique_number(self):
        reservation = BusinessDocumentNumberReservation.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BusinessDocumentNumberReservation.objects.create(document_type="purchase_reconciliation", number_policy_version="prc-sequence-v1", number_scope=reservation.number_scope, legal_entity_id="LEGAL-TEST-41", ledger_book_id="LEDGER-TEST-41", reserved_number=reservation.reserved_number, tenant_id="tenant-v41", accounting_period="2026-07", idempotency_key="other", status="reserved")

    def test_hard_unique_formal_reconciliation_number(self):
        obj = PurchaseReconciliation.objects.get()
        obj.pk = None
        obj.idempotency_key = "other-formal-number"
        with self.assertRaises(IntegrityError), transaction.atomic():
            obj._business_state_initialization_authorized = True
            obj.save(force_insert=True)

    def test_required_foreign_keys_protect_audit_chain(self):
        obj = PurchaseReconciliation.objects.get()
        with self.assertRaises(Exception), transaction.atomic():
            obj.delete()
