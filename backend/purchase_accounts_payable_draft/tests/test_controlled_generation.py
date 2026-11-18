import hashlib
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from purchase_invoice_prepare.models import (
    LegalEntityInvoiceAuthorityRecord,
    PurchaseInvoiceIdentityClaim,
    PurchaseInvoicePrepare,
    SupplierInvoiceAuthorityRecord,
)
from purchase_invoice_prepare.services import generate_purchase_invoice_prepare
from purchase_invoice_prepare.tests.test_controlled_generation import (
    make_matched_reconciliation,
)
from purchase_invoice_prepare.tests.test_invoice_validation import valid_invoice_data
from purchase_invoice_prepare.v44_services import save_invoice_data, validate_invoice_data
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from reconciliation.services import ReconciliationError
from reconciliation.tests.test_production_persistence import make_user

from purchase_accounts_payable_draft.models import (
    PurchaseAccountsPayableDraft,
    PurchaseAccountsPayableDraftSourceRelation,
    PurchaseAccountsPayableDraftSourceSnapshot,
)
from purchase_accounts_payable_draft.services import (
    ACTION_CODE,
    FAILURE_STEPS,
    RULE_DEFINITIONS,
    build_business_gate,
    build_current_state,
    generate_purchase_accounts_payable_draft,
    recover_generation_result,
)
from purchase_accounts_payable_draft.views import DraftBySourceView, GenerateView


ACTIVE = override_settings(
    PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS={"tenant-v45"},
    PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_VALIDATION_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS={"tenant-v45"},
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FEATURE_ENABLED=True,
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_TEST_TENANTS={"tenant-v45"},
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FAILURE_INJECTION_ENABLED=True,
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_SQLITE_RETRY_COUNT=2,
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_SQLITE_RETRY_INTERVAL_MS=1,
)


def make_prepared_source(user, tag="a"):
    suffix = tag.replace("-", "")[-12:]
    source = make_matched_reconciliation(
        user,
        f"v45-{tag}",
        tenant_id="tenant-v45",
        company_id=45,
        source_key=f"supplier-settlement:tenant-v45:{tag}",
        supplier_id=f"SUP-{suffix}",
        supplier_name=f"V45 Supplier {tag}",
        legal_entity_id="LEGAL-45",
        ledger_book_id="LEDGER-45",
        settlement_amount=Decimal("113.00"),
    )
    generated = generate_purchase_invoice_prepare(
        user=user,
        reconciliation_id=source.pk,
        idempotency_key=f"pip-generate-{tag}",
        expected_reconciliation_version=2,
        expected_check_version=2,
        explicit_user_action=True,
    )
    prepare = PurchaseInvoicePrepare.objects.get(pk=generated["data"]["id"])
    seller_tax_id = f"91310000{suffix:0>8}"[-18:]
    buyer_tax_id = f"91410000{suffix:0>8}"[-18:]
    SupplierInvoiceAuthorityRecord.objects.create(
        tenant_id="tenant-v45",
        company_id=45,
        supplier_id=prepare.supplier_id,
        supplier_name=prepare.supplier_name,
        seller_tax_id=seller_tax_id,
        status="active",
        authority_version=1,
        business_hash=hashlib.sha256(f"supplier-{tag}".encode()).hexdigest(),
    )
    LegalEntityInvoiceAuthorityRecord.objects.get_or_create(
        tenant_id="tenant-v45",
        legal_entity_id="LEGAL-45",
        defaults={
            "company_id": 45,
            "legal_entity_name": "V45 Legal Entity",
            "buyer_tax_id": "914100000000000045",
            "ledger_book_id": "LEDGER-45",
            "currency": "CNY",
            "status": "active",
            "authority_version": 1,
            "business_hash": hashlib.sha256(b"legal-v45").hexdigest(),
        },
    )
    payload = valid_invoice_data(f"V45{suffix:0>8}"[-12:])
    payload.update({
        "sellerName": prepare.supplier_name,
        "sellerTaxId": seller_tax_id,
        "buyerName": "V45 Legal Entity",
        "buyerTaxId": "914100000000000045",
    })
    save_invoice_data(
        user=user,
        prepare_id=prepare.pk,
        idempotency_key=f"pip-save-{tag}",
        expected_version=1,
        expected_data_version=0,
        explicit_user_action=True,
        invoice_data=payload,
    )
    prepare.refresh_from_db()
    validate_invoice_data(
        user=user,
        prepare_id=prepare.pk,
        idempotency_key=f"pip-validate-{tag}",
        expected_version=prepare.version,
        expected_data_version=1,
        expected_reconciliation_version=2,
        expected_check_version=2,
        explicit_user_action=True,
    )
    prepare.refresh_from_db()
    return prepare


def generation_kwargs(user, prepare, key, **overrides):
    values = {
        "user": user,
        "source_prepare_id": prepare.pk,
        "idempotency_key": key,
        "expected_prepare_version": prepare.version,
        "expected_invoice_data_version": prepare.current_data_version,
        "expected_validation_version": prepare.current_validation_version,
        "expected_reconciliation_version": prepare.source_purchase_reconciliation.version,
        "expected_check_version": prepare.source_check_version,
        "explicit_user_action": True,
        "failure_step": "",
    }
    values.update(overrides)
    return values


@ACTIVE
class PurchaseAccountsPayableDraftTests(TestCase):
    def setUp(self):
        self.user = make_user("v45-generator", company_id=45)
        self.prepare = make_prepared_source(self.user, "main")

    def test_a_prepared_source_generates_zero_to_one_to_one_without_source_mutation(self):
        original = {
            "status": self.prepare.status,
            "invoice_data_status": self.prepare.invoice_data_status,
            "validation_status": self.prepare.validation_status,
            "validation_result_code": self.prepare.validation_result_code,
            "version": self.prepare.version,
        }
        before = build_current_state(self.prepare)
        first = generate_purchase_accounts_payable_draft(
            **generation_kwargs(self.user, self.prepare, "papd-main")
        )
        replay = generate_purchase_accounts_payable_draft(
            **generation_kwargs(self.user, self.prepare, "papd-main")
        )
        recovered = recover_generation_result("papd-main", self.user)
        self.prepare.refresh_from_db()
        self.assertEqual(before["targetCount"], 0)
        self.assertTrue(before["generationAllowed"])
        self.assertEqual(first["classification"], "created")
        self.assertEqual(replay["classification"], "existing_result")
        self.assertEqual(recovered["classification"], "existing_result")
        self.assertEqual(PurchaseAccountsPayableDraft.objects.count(), 1)
        self.assertEqual(PurchaseAccountsPayableDraftSourceSnapshot.objects.count(), 1)
        self.assertEqual(PurchaseAccountsPayableDraftSourceRelation.objects.count(), 1)
        draft = PurchaseAccountsPayableDraft.objects.get()
        self.assertEqual(draft.status, "draft")
        self.assertEqual(draft.payable_amount, draft.amount_including_tax)
        self.assertEqual(draft.source_document_type, "purchaseInvoicePrepare")
        self.assertEqual(
            {
                "status": self.prepare.status,
                "invoice_data_status": self.prepare.invoice_data_status,
                "validation_status": self.prepare.validation_status,
                "validation_result_code": self.prepare.validation_result_code,
                "version": self.prepare.version,
            },
            original,
        )
        self.assertEqual(
            self.prepare.invoice_identity_claims.get().status, "active"
        )
        state = build_current_state(self.prepare, [draft])
        self.assertEqual(state["targetCount"], 1)
        self.assertFalse(state["generationAllowed"])
        self.assertEqual(state["idempotencyStatus"], "committed")
        self.assertEqual(state["numberReservationStatus"], "consumed")
        self.assertEqual(state["transactionStatus"], "committed")
        self.assertFalse(state["nextModuleAllowed"])

    def test_gate_codes_order_and_rich_contract_are_stable(self):
        gate = build_business_gate(
            self.prepare,
            expected_prepare_version=3,
            expected_invoice_data_version=1,
            expected_validation_version=1,
            expected_reconciliation_version=2,
            expected_check_version=2,
        )
        self.assertTrue(gate["passed"])
        self.assertEqual(
            [rule["code"] for rule in gate["rules"]],
            [definition[0] for definition in RULE_DEFINITIONS],
        )
        self.assertEqual(gate["ruleCount"], 20)
        for rule in gate["rules"]:
            self.assertEqual(
                set(rule),
                {
                    "code", "category", "status", "severity", "blocking",
                    "actual", "expected", "message", "sourceField",
                },
            )

    def test_c_to_l_source_state_validation_identity_and_reconciliation_are_blocked(self):
        mutations = (
            ("status", "draft", "APD_SOURCE_NOT_PREPARED"),
            ("invoice_data_status", "incomplete", "APD_SOURCE_STALE"),
            ("validation_status", "failed", "APD_SOURCE_VALIDATION_INVALID"),
            ("validation_result_code", "invalid", "APD_SOURCE_VALIDATION_INVALID"),
            ("validation_issue_count", 1, "APD_SOURCE_VALIDATION_INVALID"),
        )
        for field, value, code in mutations:
            with self.subTest(field=field):
                original = getattr(self.prepare, field)
                setattr(self.prepare, field, value)
                if field == "status":
                    self.prepare._business_state_transition_authorized = True
                try:
                    self.prepare.save(update_fields=[field])
                finally:
                    self.prepare._business_state_transition_authorized = False
                with self.assertRaises(ReconciliationError) as raised:
                    generate_purchase_accounts_payable_draft(
                        **generation_kwargs(self.user, self.prepare, f"blocked-{field}")
                    )
                self.assertEqual(raised.exception.code, code)
                setattr(self.prepare, field, original)
                if field == "status":
                    self.prepare._business_state_transition_authorized = True
                try:
                    self.prepare.save(update_fields=[field])
                finally:
                    self.prepare._business_state_transition_authorized = False
        claim = self.prepare.invoice_identity_claims.get()
        claim.status = "inactive"
        claim.save(update_fields=["status"])
        with self.assertRaises(ReconciliationError) as raised:
            generate_purchase_accounts_payable_draft(
                **generation_kwargs(self.user, self.prepare, "identity-inactive")
            )
        self.assertEqual(raised.exception.code, "APD_SOURCE_IDENTITY_INVALID")
        claim.status = "active"
        claim.save(update_fields=["status"])
        reconciliation = self.prepare.source_purchase_reconciliation
        reconciliation.status = "difference_found"
        reconciliation._business_state_transition_authorized = True
        try:
            reconciliation.save(update_fields=["status"])
        finally:
            reconciliation._business_state_transition_authorized = False
        with self.assertRaises(ReconciliationError):
            generate_purchase_accounts_payable_draft(
                **generation_kwargs(self.user, self.prepare, "reconciliation-invalid")
            )
        self.assertEqual(PurchaseAccountsPayableDraft.objects.count(), 0)

    def test_m_to_p_all_expected_versions_are_server_checked(self):
        cases = (
            {"expected_prepare_version": 999},
            {"expected_invoice_data_version": 999},
            {"expected_validation_version": 999},
            {"expected_reconciliation_version": 999},
            {"expected_check_version": 999},
        )
        for index, override in enumerate(cases):
            with self.subTest(override=override):
                with self.assertRaises(ReconciliationError) as raised:
                    generate_purchase_accounts_payable_draft(
                        **generation_kwargs(
                            self.user, self.prepare, f"version-{index}", **override
                        )
                    )
                self.assertEqual(raised.exception.code, "APD_VERSION_CONFLICT")
        self.assertEqual(PurchaseAccountsPayableDraft.objects.count(), 0)
        self.assertEqual(
            BusinessDocumentNumberReservation.objects.filter(
                document_type="purchase_accounts_payable_draft"
            ).count(),
            0,
        )

    def test_r_existing_target_and_s_conflict_are_explicit(self):
        result = generate_purchase_accounts_payable_draft(
            **generation_kwargs(self.user, self.prepare, "existing-first")
        )
        existing = generate_purchase_accounts_payable_draft(
            **generation_kwargs(self.user, self.prepare, "different-key")
        )
        self.assertEqual(result["classification"], "created")
        self.assertEqual(existing["classification"], "existing_target")
        draft = PurchaseAccountsPayableDraft.objects.get()
        conflict = build_current_state(self.prepare, [draft, draft])
        self.assertEqual(conflict["targetExistenceStatus"], "conflict")
        self.assertEqual(conflict["generationStatus"], "conflict")

    def test_w_auth_scope_feature_production_and_explicit_action_are_denied(self):
        with override_settings(PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FEATURE_ENABLED=False):
            with self.assertRaises(ReconciliationError) as raised:
                generate_purchase_accounts_payable_draft(
                    **generation_kwargs(self.user, self.prepare, "feature-off")
                )
            self.assertEqual(raised.exception.code, "APD_AUTH_FEATURE_DISABLED")
        other = make_user("v45-other-company", company_id=999)
        other.is_superuser = False
        other.is_staff = False
        other.save(update_fields=["is_superuser", "is_staff"])
        with self.assertRaises(ReconciliationError) as raised:
            generate_purchase_accounts_payable_draft(
                **generation_kwargs(other, self.prepare, "scope-denied")
            )
        self.assertIn(
            raised.exception.code,
            {"APD_AUTH_PERMISSION_DENIED", "APD_AUTH_SCOPE_DENIED"},
        )
        with self.assertRaises(ReconciliationError) as raised:
            generate_purchase_accounts_payable_draft(
                **generation_kwargs(
                    self.user, self.prepare, "not-explicit", explicit_user_action=False
                )
            )
        self.assertEqual(raised.exception.code, "APD_EXPLICIT_USER_ACTION_REQUIRED")

    def test_client_cannot_submit_server_derived_fields(self):
        factory = APIRequestFactory()
        for field in GenerateView.forbidden:
            request = factory.post(
                "/api/scm/purchase-accounts-payable-drafts/generate",
                {
                    "sourcePurchaseInvoicePrepareId": self.prepare.pk,
                    "idempotencyKey": f"forbidden-{field}",
                    "explicitUserAction": True,
                    field: "client-value",
                },
                format="json",
            )
            force_authenticate(request, self.user)
            response = GenerateView.as_view()(request)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data["error"]["code"],
                "APD_CLIENT_DERIVED_FIELD_FORBIDDEN",
            )

    def test_database_hard_constraints_and_protected_delete_are_real(self):
        generate_purchase_accounts_payable_draft(
            **generation_kwargs(self.user, self.prepare, "constraints")
        )
        draft = PurchaseAccountsPayableDraft.objects.get()
        constraints = connection.introspection.get_constraints(
            connection.cursor(), PurchaseAccountsPayableDraft._meta.db_table
        )
        unique_columns = {
            tuple(value["columns"])
            for value in constraints.values()
            if value.get("unique")
        }
        self.assertIn(("draft_no",), unique_columns)
        self.assertIn(("source_key",), unique_columns)
        self.assertIn(("source_purchase_invoice_prepare_id",), unique_columns)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PurchaseAccountsPayableDraftSourceRelation.objects.create(
                purchase_accounts_payable_draft=draft,
                source_id=self.prepare.pk,
                source_no=self.prepare.prepare_no,
                source_version=self.prepare.version,
                source_hash="x" * 64,
            )
        with self.assertRaises(Exception):
            self.prepare.delete()

    def test_source_snapshot_is_immutable(self):
        generate_purchase_accounts_payable_draft(
            **generation_kwargs(self.user, self.prepare, "immutable")
        )
        snapshot = PurchaseAccountsPayableDraftSourceSnapshot.objects.get()
        snapshot.source_prepare_hash = "x" * 64
        with self.assertRaisesMessage(ValueError, "immutable"):
            snapshot.save()

    def test_by_source_read_model_is_server_only_and_current_after_creation(self):
        factory = APIRequestFactory()
        request = factory.get(
            f"/api/scm/purchase-accounts-payable-drafts/by-source/{self.prepare.pk}"
        )
        force_authenticate(request, self.user)
        response = DraftBySourceView.as_view()(request, prepare_id=self.prepare.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["currentStateSource"], "server")
        self.assertEqual(response.data["data"]["targetCount"], 0)
        generate_purchase_accounts_payable_draft(
            **generation_kwargs(self.user, self.prepare, "read-model")
        )
        request = factory.get(
            f"/api/scm/purchase-accounts-payable-drafts/by-source/{self.prepare.pk}"
        )
        force_authenticate(request, self.user)
        response = DraftBySourceView.as_view()(request, prepare_id=self.prepare.pk)
        data = response.data["data"]
        self.assertEqual(data["targetCount"], 1)
        self.assertEqual(data["idempotencyStatus"], "committed")
        self.assertEqual(data["numberReservationStatus"], "consumed")
        self.assertEqual(data["transactionStatus"], "committed")
        self.assertFalse(data["generationAllowed"])
        self.assertTrue(data["preActionBusinessGate"]["passed"])


@ACTIVE
class PurchaseAccountsPayableDraftFaultMatrixTests(TestCase):
    def setUp(self):
        self.user = make_user("v45-faults", company_id=45)

    def test_x_all_parameterized_failures_rollback_or_recover_after_response_loss(self):
        results = []
        for index, step in enumerate(FAILURE_STEPS):
            prepare = make_prepared_source(self.user, f"fault-{index}")
            key = f"papd-fault-{index}"
            before_source = {
                "status": prepare.status,
                "validation_status": prepare.validation_status,
                "validation_result_code": prepare.validation_result_code,
            }
            with self.assertRaises(ReconciliationError) as raised:
                generate_purchase_accounts_payable_draft(
                    **generation_kwargs(
                        self.user, prepare, key, failure_step=step
                    )
                )
            prepare.refresh_from_db()
            if step == "before_response":
                self.assertEqual(raised.exception.code, "APD_COMMIT_UNKNOWN")
                recovered = recover_generation_result(key, self.user)
                self.assertEqual(recovered["classification"], "existing_result")
                self.assertEqual(
                    PurchaseAccountsPayableDraft.objects.filter(
                        source_purchase_invoice_prepare=prepare
                    ).count(),
                    1,
                )
            else:
                self.assertEqual(
                    PurchaseAccountsPayableDraft.objects.filter(
                        source_purchase_invoice_prepare=prepare
                    ).count(),
                    0,
                )
                self.assertEqual(
                    PurchaseAccountsPayableDraftSourceSnapshot.objects.filter(
                        source_purchase_invoice_prepare_id=prepare.pk
                    ).count(),
                    0,
                )
                self.assertEqual(
                    PurchaseAccountsPayableDraftSourceRelation.objects.filter(
                        source_id=prepare.pk
                    ).count(),
                    0,
                )
                self.assertEqual(
                    BusinessActionIdempotency.objects.filter(
                        action_code=ACTION_CODE,
                        source_key=f"purchaseInvoicePrepare:{prepare.pk}",
                    ).count(),
                    0,
                )
            self.assertEqual(
                {
                    "status": prepare.status,
                    "validation_status": prepare.validation_status,
                    "validation_result_code": prepare.validation_result_code,
                },
                before_source,
            )
            self.assertEqual(prepare.invoice_identity_claims.get().status, "active")
            results.append((step, raised.exception.code))
        self.assertEqual(len(results), 21)
        aborted = BusinessDocumentNumberReservation.objects.filter(
            document_type="purchase_accounts_payable_draft",
            status="aborted",
        )
        self.assertTrue(all(not item.reusable for item in aborted))
        self.assertEqual(
            BusinessActionTransaction.objects.filter(
                action_code=ACTION_CODE,
                status="failed",
            ).count(),
            0,
        )
        self.assertEqual(
            BusinessActionAuditRecord.objects.filter(
                action_code=ACTION_CODE,
                result="failed",
            ).count(),
            0,
        )
