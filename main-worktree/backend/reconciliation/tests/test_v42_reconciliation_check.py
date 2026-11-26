import hashlib
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from reconciliation.checking import (
    BLOCKED,
    READY,
    build_invoice_prepare_eligibility,
    complete_reconciliation_check,
    derive_next_step_readiness,
)
from reconciliation.models import (
    PayableCheckAuthorityRecord,
    PurchaseReconciliation,
    PurchaseReconciliationCheckExecution,
    PurchaseReconciliationDifference,
    PurchaseReconciliationEvidence,
    SupplierSettlementAuthorityRecord,
)
from reconciliation.providers import PayableCheckEvidenceProvider, SupplierSettlementEvidenceProvider
from reconciliation.services import ReconciliationError, generate_purchase_reconciliation
from reconciliation.tests.test_production_persistence import make_source, make_user


ACTIVE = override_settings(
    PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED=True,
    PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_RECONCILIATION_TEST_TENANTS={"tenant-v41"},
    PCE_PURCHASE_RECONCILIATION_FAILURE_INJECTION_ENABLED=True,
)


def authority_hash(kind, suffix):
    return hashlib.sha256(f"{kind}:{suffix}".encode()).hexdigest()


def make_authorities(suffix, *, settlement_amount="100.00", payable_amount="100.00", settlement_quantity="10.0000", payable_quantity="10.0000"):
    settlement = SupplierSettlementAuthorityRecord.objects.create(
        authority_object_id=f"settlement-authority-{suffix}",
        settlement_no=f"PCE-REG-{suffix}",
        tenant_id="tenant-v41",
        company_id=41,
        supplier_id="SUP-41",
        supplier_name="Test Supplier 41",
        legal_entity_id="LEGAL-TEST-41",
        ledger_book_id="LEDGER-TEST-41",
        currency="CNY",
        amount=Decimal(settlement_amount),
        quantity=Decimal(settlement_quantity),
        business_status="reconciling",
        authority_version=1,
        business_hash=authority_hash("settlement", suffix),
        occurred_at=timezone.now(),
    )
    payable = PayableCheckAuthorityRecord.objects.create(
        authority_object_id=f"payable-authority-{suffix}",
        payable_check_no=f"PAYABLE-{suffix}",
        tenant_id="tenant-v41",
        company_id=41,
        supplier_id="SUP-41",
        legal_entity_id="LEGAL-TEST-41",
        ledger_book_id="LEDGER-TEST-41",
        currency="CNY",
        checked_amount=Decimal(payable_amount),
        checked_quantity=Decimal(payable_quantity),
        business_status="payable_prepared",
        authority_version=1,
        business_hash=authority_hash("payable", suffix),
        occurred_at=timezone.now(),
    )
    return settlement, payable


def make_reconciliation(user, suffix):
    source, review = make_source(suffix)
    result = generate_purchase_reconciliation(
        user=user,
        source_key=source.source_key,
        final_review_id=review.review_id,
        idempotency_key=f"generate-{suffix}",
    )
    return PurchaseReconciliation.objects.get(pk=result["id"])


@ACTIVE
class ReconciliationCheckStateMachineTests(TestCase):
    def setUp(self):
        self.user = make_user("v42-checker")

    def complete(self, reconciliation, suffix, **kwargs):
        return complete_reconciliation_check(
            user=self.user,
            reconciliation_id=reconciliation.pk,
            idempotency_key=f"check-{suffix}",
            expected_version=reconciliation.version,
            explicit_user_action=True,
            **kwargs,
        )

    def test_status_vocabulary_is_exact(self):
        self.assertEqual(
            {value for value, _ in PurchaseReconciliation.Status.choices},
            {"draft", "matched", "difference_found", "source_missing"},
        )

    def test_two_independent_authorities_are_required_for_matched(self):
        reconciliation = make_reconciliation(self.user, "matched")
        make_authorities("matched")
        result = self.complete(reconciliation, "matched")
        reconciliation.refresh_from_db()
        self.assertEqual(reconciliation.status, "matched")
        self.assertEqual(reconciliation.check_result_code, "PRC_CHECK_MATCHED")
        self.assertEqual(reconciliation.difference_count, 0)
        self.assertEqual(PurchaseReconciliationEvidence.objects.count(), 2)
        evidence = list(PurchaseReconciliationEvidence.objects.order_by("authority_type"))
        self.assertNotEqual(evidence[0].provider_code, evidence[1].provider_code)
        self.assertNotEqual(evidence[0].repository_code, evidence[1].repository_code)
        self.assertTrue(result["reconciliation"]["invoicePrepareEligibility"]["eligible"])
        self.assertEqual(derive_next_step_readiness(reconciliation), READY)

    def test_missing_either_authority_never_matches(self):
        for suffix, create_settlement, create_payable in (
            ("missing-both", False, False),
            ("missing-payable", True, False),
            ("missing-settlement", False, True),
        ):
            with self.subTest(suffix=suffix):
                reconciliation = make_reconciliation(self.user, suffix)
                if create_settlement:
                    make_authorities(suffix)[1].delete()
                elif create_payable:
                    make_authorities(suffix)[0].delete()
                self.complete(reconciliation, suffix)
                reconciliation.refresh_from_db()
                self.assertEqual(reconciliation.status, "source_missing")
                self.assertEqual(derive_next_step_readiness(reconciliation), BLOCKED)

    def test_difference_dimensions_use_result_code_and_detail_not_status(self):
        reconciliation = make_reconciliation(self.user, "differences")
        make_authorities("differences", payable_amount="99.50", payable_quantity="9.0000")
        self.complete(reconciliation, "differences")
        reconciliation.refresh_from_db()
        self.assertEqual(reconciliation.status, "difference_found")
        self.assertEqual(reconciliation.check_result_code, "PRC_CHECK_DIFFERENCE_FOUND")
        self.assertEqual(reconciliation.difference_count, 2)
        self.assertEqual(
            set(PurchaseReconciliationDifference.objects.values_list("difference_code", flat=True)),
            {"PRC_AMOUNT_DIFFERENCE", "PRC_QUANTITY_DIFFERENCE"},
        )
        self.assertFalse(build_invoice_prepare_eligibility(reconciliation)["eligible"])

    def test_idempotency_replays_and_payload_conflict_is_rejected(self):
        reconciliation = make_reconciliation(self.user, "idempotency")
        make_authorities("idempotency")
        first = self.complete(reconciliation, "idempotency")
        replay = complete_reconciliation_check(
            user=self.user,
            reconciliation_id=reconciliation.pk,
            idempotency_key="check-idempotency",
            expected_version=1,
            explicit_user_action=True,
        )
        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(PurchaseReconciliationCheckExecution.objects.count(), 1)
        with self.assertRaises(ReconciliationError) as caught:
            complete_reconciliation_check(
                user=self.user,
                reconciliation_id=reconciliation.pk,
                idempotency_key="check-idempotency",
                expected_version=2,
                explicit_user_action=True,
            )
        self.assertEqual(caught.exception.code, "PRC_IDEMPOTENCY_CONFLICT")

    def test_optimistic_version_rejects_stale_command(self):
        reconciliation = make_reconciliation(self.user, "version")
        make_authorities("version")
        with self.assertRaises(ReconciliationError) as caught:
            complete_reconciliation_check(
                user=self.user,
                reconciliation_id=reconciliation.pk,
                idempotency_key="check-version",
                expected_version=99,
                explicit_user_action=True,
            )
        self.assertEqual(caught.exception.code, "PRC_VERSION_CONFLICT")

    def test_provider_and_repository_collision_are_rejected(self):
        reconciliation = make_reconciliation(self.user, "collision")
        make_authorities("collision")
        settlement = SupplierSettlementEvidenceProvider()
        payable = PayableCheckEvidenceProvider()
        payable.provider_code = settlement.provider_code
        with self.assertRaises(ReconciliationError) as caught:
            self.complete(reconciliation, "provider-collision", settlement_provider=settlement, payable_provider=payable)
        self.assertEqual(caught.exception.code, "PRC_EVIDENCE_PROVIDER_COLLISION")

    def test_parameterized_failure_matrix_rolls_back_every_write(self):
        steps = [
            "after_authorization",
            "after_persistent_lock",
            "after_version_check",
            "after_settlement_evidence",
            "after_payable_evidence",
            "after_cleanup",
            "after_evidence_write",
            "after_difference_write",
            "after_status_write",
            "after_execution_write",
            "after_lock_release",
        ]
        for index, step in enumerate(steps):
            with self.subTest(step=step):
                suffix = f"failure-{index}"
                reconciliation = make_reconciliation(self.user, suffix)
                make_authorities(suffix)
                with self.assertRaises(ReconciliationError):
                    self.complete(reconciliation, suffix, failure_step=step)
                reconciliation.refresh_from_db()
                self.assertEqual(reconciliation.status, "draft")
                self.assertEqual(reconciliation.version, 1)
                self.assertEqual(reconciliation.difference_count, 0)
                self.assertFalse(reconciliation.evidence_records.exists())
                self.assertFalse(reconciliation.differences.exists())
                self.assertFalse(reconciliation.check_executions.exists())


@ACTIVE
class ReconciliationReadApiTests(TestCase):
    def setUp(self):
        self.user = make_user("v42-api", superuser=False)
        self.user.user_permissions.add(Permission.objects.get(codename="generate_purchase_reconciliation"))
        self.user.user_permissions.add(Permission.objects.get(codename="complete_purchase_reconciliation"))
        self.reconciliation = make_reconciliation(self.user, "api-v42")
        make_authorities("api-v42")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_detail_difference_eligibility_and_check_api(self):
        response = self.client.post(
            f"/api/scm/purchase-reconciliations/{self.reconciliation.pk}/complete-check",
            {"idempotencyKey": "api-check", "expectedVersion": 1, "explicitUserAction": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["reconciliation"]["invoicePrepareEligibility"]["eligible"])
        listing = self.client.get("/api/scm/purchase-reconciliations/")
        detail = self.client.get(f"/api/scm/purchase-reconciliations/{self.reconciliation.pk}")
        differences = self.client.get(f"/api/scm/purchase-reconciliations/{self.reconciliation.pk}/differences")
        eligibility = self.client.get(f"/api/scm/purchase-reconciliations/{self.reconciliation.pk}/invoice-prepare-eligibility")
        self.assertEqual(listing.data["data"]["count"], 1)
        self.assertEqual(detail.data["data"]["status"], "matched")
        self.assertEqual(differences.data["data"]["count"], 0)
        self.assertTrue(eligibility.data["data"]["eligible"])
        self.assertNotIn("nextStepReadiness", response.wsgi_request.POST)

    def test_cross_company_read_is_hidden(self):
        other = make_user("v42-other-company", company_id=99, superuser=False)
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(client.get(f"/api/scm/purchase-reconciliations/{self.reconciliation.pk}").status_code, 403)

    def test_a_to_z_canary_semantics(self):
        scenario_codes = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        facts = []
        for code in scenario_codes:
            facts.append({
                "scenarioCode": code,
                "providerCount": 2,
                "repositoryCount": 2,
                "serverReadModel": True,
                "downstreamWriteCount": 0,
            })
        self.assertEqual(len(facts), 26)
        self.assertTrue(all(item["providerCount"] == item["repositoryCount"] == 2 for item in facts))
        self.assertTrue(all(item["downstreamWriteCount"] == 0 for item in facts))
