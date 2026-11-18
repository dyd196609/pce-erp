import hashlib
from copy import deepcopy
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from reconciliation.models import BusinessActionAuditRecord, BusinessActionIdempotency
from reconciliation.services import ReconciliationError
from reconciliation.tests.test_production_persistence import make_user

from purchase_invoice_prepare.models import (
    LegalEntityInvoiceAuthorityRecord,
    PurchaseInvoiceDataSnapshot,
    PurchaseInvoiceIdentityClaim,
    PurchaseInvoicePrepare,
    PurchaseInvoiceValidationExecution,
    SupplierInvoiceAuthorityRecord,
)
from purchase_invoice_prepare.services import generate_purchase_invoice_prepare
from purchase_invoice_prepare.tests.test_controlled_generation import make_matched_reconciliation
from purchase_invoice_prepare.v44_services import (
    SAVE_ACTION,
    SAVE_FAILURE_STEPS,
    VALIDATE_ACTION,
    VALIDATION_FAILURE_STEPS,
    build_ap_draft_eligibility,
    build_validation_read_model,
    save_invoice_data,
    validate_invoice_data,
)


ACTIVE = override_settings(
    PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS={"tenant-v44"},
    PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_VALIDATION_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS={"tenant-v44"},
    PCE_PURCHASE_INVOICE_VALIDATION_FAILURE_INJECTION_ENABLED=True,
)


def valid_invoice_data(number="V44INV000001"):
    return {
        "invoiceType": "vat_special",
        "invoiceCode": "V44CODE001",
        "invoiceNumber": number,
        "invoiceDate": "2026-07-23",
        "sellerName": "V44 Supplier",
        "sellerTaxId": "91310000V44SELLER",
        "buyerName": "V44 Legal Entity",
        "buyerTaxId": "91310000V44BUYER",
        "currency": "CNY",
        "amountExcludingTax": "100.00",
        "taxAmount": "13.00",
        "amountIncludingTax": "113.00",
        "lines": [{
            "lineNo": 1, "itemCode": "MAT-V44", "itemName": "V44 Material",
            "specification": "STD", "quantity": "10.0000", "unit": "EA",
            "unitPrice": "10.000000", "amountExcludingTax": "100.00",
            "taxRate": "0.130000", "taxAmount": "13.00", "amountIncludingTax": "113.00",
        }],
    }


@ACTIVE
class InvoiceValidationTests(TestCase):
    def setUp(self):
        self.user = make_user("v44-validator", company_id=44)
        self.source = make_matched_reconciliation(
            self.user, "v44",
            tenant_id="tenant-v44", company_id=44,
            source_key="supplier-settlement:tenant-v44:v44",
            supplier_id="SUP-44", supplier_name="V44 Supplier",
            legal_entity_id="LEGAL-44", ledger_book_id="LEDGER-44",
            settlement_amount=Decimal("113.00"),
        )
        result = generate_purchase_invoice_prepare(
            user=self.user, reconciliation_id=self.source.pk, idempotency_key="pip-v44-generate",
            expected_reconciliation_version=2, expected_check_version=2, explicit_user_action=True,
        )
        self.prepare = PurchaseInvoicePrepare.objects.get(pk=result["data"]["id"])
        SupplierInvoiceAuthorityRecord.objects.create(
            tenant_id="tenant-v44", company_id=44, supplier_id="SUP-44",
            supplier_name="V44 Supplier", seller_tax_id="91310000V44SELLER",
            status="active", authority_version=1, business_hash=hashlib.sha256(b"supplier-v44").hexdigest(),
        )
        LegalEntityInvoiceAuthorityRecord.objects.create(
            tenant_id="tenant-v44", company_id=44, legal_entity_id="LEGAL-44",
            legal_entity_name="V44 Legal Entity", buyer_tax_id="91310000V44BUYER",
            ledger_book_id="LEDGER-44", currency="CNY", status="active",
            authority_version=1, business_hash=hashlib.sha256(b"legal-v44").hexdigest(),
        )

    def save(self, payload=None, key="save-v44", **kwargs):
        return save_invoice_data(
            user=self.user, prepare_id=self.prepare.pk, idempotency_key=key,
            expected_version=kwargs.pop("expected_version", self.prepare.version),
            expected_data_version=kwargs.pop("expected_data_version", self.prepare.current_data_version),
            explicit_user_action=True, invoice_data=payload or valid_invoice_data(), **kwargs,
        )

    def validate(self, key="validate-v44", **kwargs):
        self.prepare.refresh_from_db()
        return validate_invoice_data(
            user=self.user, prepare_id=self.prepare.pk, idempotency_key=key,
            expected_version=kwargs.pop("expected_version", self.prepare.version),
            expected_data_version=kwargs.pop("expected_data_version", self.prepare.current_data_version),
            expected_reconciliation_version=2, expected_check_version=2,
            explicit_user_action=True, **kwargs,
        )

    def test_valid_data_transitions_draft_to_prepared_and_releases_navigation_only(self):
        saved = self.save()
        self.prepare.refresh_from_db()
        self.assertEqual(saved["invoiceData"]["dataVersion"], 1)
        self.assertEqual(self.prepare.invoice_data_status, "complete")
        result = self.validate()
        self.prepare.refresh_from_db()
        eligibility = build_ap_draft_eligibility(self.prepare)
        self.assertEqual(result["classification"], "validated")
        self.assertEqual(self.prepare.status, "prepared")
        self.assertEqual(self.prepare.validation_status, "passed")
        self.assertEqual(self.prepare.validation_result_code, "validated")
        self.assertEqual(PurchaseInvoiceIdentityClaim.objects.count(), 1)
        self.assertTrue(eligibility["eligible"])
        self.assertEqual(eligibility["nextStepReadiness"], "ready_for_accounts_payable_draft")
        self.assertEqual(eligibility["accountsPayableDraftCount"], 0)

    def test_incomplete_data_is_versioned_but_cannot_validate(self):
        payload = valid_invoice_data()
        payload["invoiceNumber"] = ""
        self.save(payload)
        self.prepare.refresh_from_db()
        self.assertEqual(self.prepare.invoice_data_status, "incomplete")
        with self.assertRaisesMessage(ReconciliationError, "Invoice data incomplete"):
            self.validate()
        self.assertEqual(PurchaseInvoiceValidationExecution.objects.count(), 0)

    def test_decimal_tax_line_header_amount_quantity_and_authority_failures_are_server_derived(self):
        mutations = (
            ("sellerTaxId", "WRONG"),
            ("buyerTaxId", "WRONG"),
            ("currency", "USD"),
            ("amountIncludingTax", "114.00"),
        )
        for index, (field, value) in enumerate(mutations):
            prepare = self.prepare
            payload = valid_invoice_data(f"V44INV{index:06d}")
            payload[field] = value
            self.save(payload, key=f"save-fail-{index}")
            result = self.validate(key=f"validate-fail-{index}")
            prepare.refresh_from_db()
            self.assertEqual(result["classification"], "validation_failed")
            self.assertEqual(prepare.status, "draft")
            self.assertEqual(prepare.validation_status, "failed")
            if index < len(mutations) - 1:
                prepare.validation_status = "not_validated"
                prepare.validation_result_code = "not_validated"
                prepare.save(update_fields=["validation_status", "validation_result_code"])
                self.prepare.refresh_from_db()

    def test_save_and_validation_idempotency_do_not_duplicate(self):
        first = self.save()
        replay = self.save(key="save-v44", expected_version=1, expected_data_version=0)
        self.prepare.refresh_from_db()
        self.assertEqual(first["classification"], "saved")
        self.assertEqual(replay["classification"], "existing_result")
        self.assertEqual(PurchaseInvoiceDataSnapshot.objects.count(), 1)
        first_validation = self.validate()
        replay_validation = validate_invoice_data(
            user=self.user, prepare_id=self.prepare.pk, idempotency_key="validate-v44",
            expected_version=2, expected_data_version=1,
            expected_reconciliation_version=2, expected_check_version=2,
            explicit_user_action=True,
        )
        self.assertEqual(first_validation["classification"], "validated")
        self.assertEqual(replay_validation["classification"], "existing_result")
        self.assertEqual(PurchaseInvoiceValidationExecution.objects.count(), 1)
        self.assertEqual(PurchaseInvoiceIdentityClaim.objects.count(), 1)
        self.assertEqual(BusinessActionAuditRecord.objects.filter(action_code=VALIDATE_ACTION).count(), 1)

    def test_active_invoice_identity_has_database_hard_unique_constraint(self):
        self.save()
        self.validate()
        claim = PurchaseInvoiceIdentityClaim.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PurchaseInvoiceIdentityClaim.objects.create(
                tenant_id=claim.tenant_id, legal_entity_id=claim.legal_entity_id,
                invoice_identity_key=claim.invoice_identity_key,
                purchase_invoice_prepare=claim.purchase_invoice_prepare,
                invoice_data_snapshot=claim.invoice_data_snapshot, status="active",
            )

    def test_prepared_is_immutable(self):
        self.save()
        self.validate()
        self.prepare.refresh_from_db()
        with self.assertRaisesMessage(ReconciliationError, "Prepared data is immutable"):
            self.save(key="save-after-prepared")

    def test_source_and_optimistic_versions_are_revalidated(self):
        self.save()
        with self.assertRaises(ReconciliationError):
            self.validate(expected_version=1)
        self.source.version = 3
        self.source.save(update_fields=["version"])
        with self.assertRaisesMessage(ReconciliationError, "Source version changed"):
            self.validate()

    def test_read_model_is_complete_and_server_derived(self):
        self.save()
        self.validate()
        model = build_validation_read_model(PurchaseInvoicePrepare.objects.get(pk=self.prepare.pk))
        self.assertEqual(model["currentStateSource"], "server")
        self.assertEqual(model["validation"]["status"], "passed")
        self.assertEqual(model["versionsAndAudit"]["saveIdempotencyStatus"], "committed")
        self.assertEqual(model["versionsAndAudit"]["validationIdempotencyStatus"], "committed")
        self.assertEqual(sum(model["downstreamCounts"].values()), 0)

    def test_save_failure_matrix_rolls_back(self):
        for index, step in enumerate(SAVE_FAILURE_STEPS[:-1]):
            before = PurchaseInvoiceDataSnapshot.objects.count()
            with self.assertRaises(ReconciliationError):
                self.save(key=f"save-inject-{index}", failure_step=step)
            self.prepare.refresh_from_db()
            self.assertEqual(self.prepare.current_data_version, 0)
            self.assertEqual(PurchaseInvoiceDataSnapshot.objects.count(), before)
            self.assertFalse(BusinessActionIdempotency.objects.filter(
                action_code=SAVE_ACTION, idempotency_key=f"save-inject-{index}"
            ).exists())

    def test_save_response_loss_recovers_committed_result(self):
        with self.assertRaises(ReconciliationError):
            self.save(key="save-before-response", failure_step="before_response")
        self.prepare.refresh_from_db()
        self.assertEqual(self.prepare.current_data_version, 1)
        replay = self.save(
            key="save-before-response",
            expected_version=1,
            expected_data_version=0,
        )
        self.assertEqual(replay["classification"], "existing_result")
        self.assertEqual(PurchaseInvoiceDataSnapshot.objects.count(), 1)

    def test_validation_failure_matrix_rolls_back(self):
        self.save()
        self.prepare.refresh_from_db()
        for index, step in enumerate(VALIDATION_FAILURE_STEPS[:-1]):
            with self.assertRaises(ReconciliationError):
                self.validate(key=f"validate-inject-{index}", failure_step=step)
            self.prepare.refresh_from_db()
            self.assertEqual(self.prepare.status, "draft")
            self.assertEqual(self.prepare.current_validation_version, 0)
            self.assertFalse(PurchaseInvoiceValidationExecution.objects.filter(
                idempotency_key=f"validate-inject-{index}"
            ).exists())
            self.assertEqual(PurchaseInvoiceIdentityClaim.objects.count(), 0)

    def test_validation_response_loss_recovers_committed_result(self):
        self.save()
        with self.assertRaises(ReconciliationError):
            self.validate(key="validate-before-response", failure_step="before_response")
        self.prepare.refresh_from_db()
        self.assertEqual(self.prepare.status, "prepared")
        replay = validate_invoice_data(
            user=self.user, prepare_id=self.prepare.pk, idempotency_key="validate-before-response",
            expected_version=2, expected_data_version=1,
            expected_reconciliation_version=2, expected_check_version=2,
            explicit_user_action=True,
        )
        self.assertEqual(replay["classification"], "existing_result")
        self.assertEqual(PurchaseInvoiceValidationExecution.objects.count(), 1)
        self.assertEqual(PurchaseInvoiceIdentityClaim.objects.count(), 1)
