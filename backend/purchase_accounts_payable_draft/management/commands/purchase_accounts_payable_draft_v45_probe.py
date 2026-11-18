import hashlib
import json
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from purchase_invoice_prepare.models import (
    LegalEntityInvoiceAuthorityRecord,
    PurchaseInvoicePrepare,
    SupplierInvoiceAuthorityRecord,
)
from purchase_invoice_prepare.services import generate_purchase_invoice_prepare
from purchase_invoice_prepare.v44_services import save_invoice_data, validate_invoice_data
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
    PurchaseReconciliation,
    PurchaseReconciliationCheckExecution,
    PurchaseReconciliationEvidence,
)
from system.models import User

from purchase_accounts_payable_draft.models import (
    PurchaseAccountsPayableDraft,
    PurchaseAccountsPayableDraftSourceRelation,
    PurchaseAccountsPayableDraftSourceSnapshot,
)
from purchase_accounts_payable_draft.services import (
    ACTION_CODE,
    build_business_gate,
    build_current_state,
    generate_purchase_accounts_payable_draft,
    recover_generation_result,
)


class Command(BaseCommand):
    help = "V45 isolated purchase accounts payable draft probe"

    def add_arguments(self, parser):
        parser.add_argument(
            "operation", choices=("seed", "generate", "recover", "inspect")
        )
        parser.add_argument("--prepare-id", type=int)
        parser.add_argument("--idempotency-key", default="papd-v45-controlled-generate")

    def handle(self, *args, **options):
        operation = options["operation"]
        if operation == "seed":
            payload = self.seed()
        elif operation == "generate":
            payload = self.generate(
                options["prepare_id"], options["idempotency_key"]
            )
        elif operation == "recover":
            payload = recover_generation_result(
                options["idempotency_key"], self.user()
            )
        else:
            payload = self.inspect(options["prepare_id"])
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def user(self):
        user, _ = User.objects.get_or_create(
            username="v45-cross-process",
            defaults={
                "real_name": "V45 Cross Process",
                "company_id": 45,
                "is_superuser": True,
                "is_staff": True,
                "is_active": True,
            },
        )
        user.company_id = 45
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.set_password("V45-Canary-Only!")
        user.save()
        return user

    def seed(self):
        user = self.user()
        source, _ = PurchaseReconciliation.objects.get_or_create(
            reconciliation_no="PRC-V45-A",
            defaults={
                "id": 45,
                "tenant_id": "tenant-v45",
                "company_id": 45,
                "source_key": "supplier-settlement:tenant-v45:a",
                "source_supplier_settlement_no": "SET-V45-A",
                "source_payable_check_no": "PAY-V45-A",
                "source_payable_prepare_no": "PAY-PREP-V45-A",
                "purchase_order_no": "PO-V45-A",
                "price_approval_no": "PRICE-V45-A",
                "supplier_id": "SUP-45",
                "supplier_name": "V45 Supplier",
                "legal_entity_id": "LEGAL-45",
                "ledger_book_id": "LEDGER-45",
                "currency": "CNY",
                "exchange_rate": Decimal("1.00000000"),
                "accounting_period": "2026-07",
                "settlement_amount": Decimal("113.00"),
                "quantity": Decimal("10.0000"),
                "unit": "EA",
                "source_candidate_id": "candidate-v45",
                "simulation_request_id": "request-v45",
                "simulation_result_id": "result-v45",
                "status": "matched",
                "source_snapshot_hash": hashlib.sha256(b"source-v45").hexdigest(),
                "review_id": "review-v45",
                "review_hash": hashlib.sha256(b"review-v45").hexdigest(),
                "command_id": "command-v45",
                "transaction_plan_id": "purchase-reconciliation-atomic-v1",
                "idempotency_key": "generate-reconciliation-v45",
                "created_by": user,
                "check_result_code": "PRC_CHECK_MATCHED",
                "difference_count": 0,
                "checked_at": timezone.now(),
                "checked_by": user,
                "version": 2,
            },
        )
        if not source.evidence_records.exists():
            for authority_type, provider, repository in (
                (
                    "supplier_settlement",
                    "SupplierSettlementEvidenceProvider",
                    "SupplierSettlementAuthorityRepository",
                ),
                (
                    "payable_check",
                    "PayableCheckEvidenceProvider",
                    "PayableCheckAuthorityRepository",
                ),
            ):
                PurchaseReconciliationEvidence.objects.create(
                    reconciliation=source,
                    provider_code=provider,
                    repository_code=repository,
                    authority_type=authority_type,
                    authority_object_id=f"{authority_type}-v45",
                    authority_object_no=f"{authority_type}-NO-v45",
                    authority_version=1,
                    business_hash=hashlib.sha256(
                        f"{authority_type}-v45".encode()
                    ).hexdigest(),
                    evidence={"source": authority_type},
                )
        if not source.check_executions.exists():
            PurchaseReconciliationCheckExecution.objects.create(
                reconciliation=source,
                idempotency_key="check-v45",
                request_hash=hashlib.sha256(b"check-v45").hexdigest(),
                expected_version=1,
                result_status="matched",
                check_result_code="PRC_CHECK_MATCHED",
                difference_count=0,
                actor=user,
                result_payload={"result": "matched"},
            )
        SupplierInvoiceAuthorityRecord.objects.get_or_create(
            tenant_id="tenant-v45",
            supplier_id="SUP-45",
            defaults={
                "company_id": 45,
                "supplier_name": "V45 Supplier",
                "seller_tax_id": "913100000000000045",
                "status": "active",
                "authority_version": 1,
                "business_hash": hashlib.sha256(b"supplier-v45").hexdigest(),
            },
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
        generated = generate_purchase_invoice_prepare(
            user=user,
            reconciliation_id=source.pk,
            idempotency_key="pip-v45-generate",
            expected_reconciliation_version=2,
            expected_check_version=2,
            explicit_user_action=True,
        )
        prepare = PurchaseInvoicePrepare.objects.get(pk=generated["data"]["id"])
        if prepare.current_data_version == 0:
            save_invoice_data(
                user=user,
                prepare_id=prepare.pk,
                idempotency_key="pip-v45-save",
                expected_version=prepare.version,
                expected_data_version=0,
                explicit_user_action=True,
                invoice_data={
                    "invoiceType": "vat_special",
                    "invoiceCode": "V45CODE001",
                    "invoiceNumber": "V45INV000001",
                    "invoiceDate": "2026-07-23",
                    "sellerName": "V45 Supplier",
                    "sellerTaxId": "913100000000000045",
                    "buyerName": "V45 Legal Entity",
                    "buyerTaxId": "914100000000000045",
                    "currency": "CNY",
                    "amountExcludingTax": "100.00",
                    "taxAmount": "13.00",
                    "amountIncludingTax": "113.00",
                    "lines": [{
                        "lineNo": 1,
                        "itemCode": "MAT-V45",
                        "itemName": "V45 Material",
                        "specification": "STD",
                        "quantity": "10.0000",
                        "unit": "EA",
                        "unitPrice": "10.000000",
                        "amountExcludingTax": "100.00",
                        "taxRate": "0.130000",
                        "taxAmount": "13.00",
                        "amountIncludingTax": "113.00",
                    }],
                },
            )
            prepare.refresh_from_db()
        if prepare.validation_status != "passed":
            validate_invoice_data(
                user=user,
                prepare_id=prepare.pk,
                idempotency_key="pip-v45-validate",
                expected_version=prepare.version,
                expected_data_version=prepare.current_data_version,
                expected_reconciliation_version=source.version,
                expected_check_version=prepare.source_check_version,
                explicit_user_action=True,
            )
            prepare.refresh_from_db()
        return {
            "operation": "seed",
            "sourceId": source.pk,
            "sourceNo": source.reconciliation_no,
            "prepareId": prepare.pk,
            "prepareNo": prepare.prepare_no,
            "prepareVersion": prepare.version,
            "invoiceDataVersion": prepare.current_data_version,
            "validationVersion": prepare.current_validation_version,
            "reconciliationVersion": source.version,
            "checkVersion": prepare.source_check_version,
            "targetCount": PurchaseAccountsPayableDraft.objects.filter(
                source_purchase_invoice_prepare=prepare
            ).count(),
        }

    def prepare(self, prepare_id):
        if not prepare_id:
            raise CommandError("--prepare-id is required")
        return PurchaseInvoicePrepare.objects.get(pk=prepare_id)

    def generate(self, prepare_id, key):
        prepare = self.prepare(prepare_id)
        source = prepare.source_purchase_reconciliation
        return generate_purchase_accounts_payable_draft(
            user=self.user(),
            source_prepare_id=prepare.pk,
            idempotency_key=key,
            expected_prepare_version=prepare.version,
            expected_invoice_data_version=prepare.current_data_version,
            expected_validation_version=prepare.current_validation_version,
            expected_reconciliation_version=source.version,
            expected_check_version=prepare.source_check_version,
            explicit_user_action=True,
        )

    def inspect(self, prepare_id):
        prepare = self.prepare(prepare_id)
        targets = list(
            PurchaseAccountsPayableDraft.objects.filter(
                source_purchase_invoice_prepare=prepare
            ).select_related(
                "number_reservation", "business_transaction", "audit_record"
            )
        )
        gate = build_business_gate(prepare)
        state = build_current_state(prepare, targets)
        if len(targets) == 1 and targets[0].audit_record:
            audit_rules = (
                targets[0].audit_record.evidence or {}
            ).get("preActionBusinessGate", [])
            pre_action_gate = {
                "passed": bool(audit_rules)
                and all(rule.get("status") == "passed" for rule in audit_rules),
                "ruleCount": len(audit_rules),
                "rules": audit_rules,
            }
        else:
            pre_action_gate = {
                "passed": gate["passed"],
                "ruleCount": gate["ruleCount"],
                "rules": gate["rules"],
            }
        return {
            "operation": "inspect",
            "source": {
                "id": prepare.pk,
                "prepareNo": prepare.prepare_no,
                "status": prepare.status,
                "invoiceDataStatus": prepare.invoice_data_status,
                "validationStatus": prepare.validation_status,
                "validationResultCode": prepare.validation_result_code,
                "validationIssueCount": prepare.validation_issue_count,
                "invoiceIdentityStatus": prepare.invoice_identity_claims.get().status,
                "prepareVersion": prepare.version,
                "invoiceDataVersion": prepare.current_data_version,
                "validationVersion": prepare.current_validation_version,
                "reconciliationVersion": prepare.source_purchase_reconciliation.version,
                "checkVersion": prepare.source_check_version,
            },
            "preActionGate": pre_action_gate,
            "currentState": state,
            "counts": {
                "drafts": PurchaseAccountsPayableDraft.objects.count(),
                "sourceSnapshots": PurchaseAccountsPayableDraftSourceSnapshot.objects.count(),
                "sourceRelations": PurchaseAccountsPayableDraftSourceRelation.objects.count(),
                "idempotency": BusinessActionIdempotency.objects.filter(
                    action_code=ACTION_CODE
                ).count(),
                "transactions": BusinessActionTransaction.objects.filter(
                    action_code=ACTION_CODE
                ).count(),
                "audits": BusinessActionAuditRecord.objects.filter(
                    action_code=ACTION_CODE
                ).count(),
                "numbers": BusinessDocumentNumberReservation.objects.filter(
                    document_type="purchase_accounts_payable_draft"
                ).count(),
                "productionTenantDrafts": PurchaseAccountsPayableDraft.objects.exclude(
                    tenant_id="tenant-v45"
                ).count(),
            },
            "downstreamCounts": state["downstreamCounts"],
        }
