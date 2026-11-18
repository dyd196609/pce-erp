import hashlib
import json
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

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

from purchase_invoice_prepare.models import (
    LegalEntityInvoiceAuthorityRecord,
    PurchaseInvoiceDataLine,
    PurchaseInvoiceDataSnapshot,
    PurchaseInvoiceIdentityClaim,
    PurchaseInvoicePrepare,
    PurchaseInvoiceValidationExecution,
    PurchaseInvoiceValidationIssue,
    SupplierInvoiceAuthorityRecord,
)
from purchase_invoice_prepare.services import generate_purchase_invoice_prepare
from purchase_invoice_prepare.v44_services import (
    SAVE_ACTION,
    VALIDATE_ACTION,
    build_ap_draft_eligibility,
    build_validation_read_model,
    recover_validation_result,
    save_invoice_data,
    validate_invoice_data,
)


class Command(BaseCommand):
    help = "V44 isolated purchase-invoice validation probe"

    def add_arguments(self, parser):
        parser.add_argument("operation", choices=("seed", "save", "validate", "recover", "inspect"))
        parser.add_argument("--prepare-id", type=int)
        parser.add_argument("--idempotency-key", default="")

    def handle(self, *args, **options):
        operation = options["operation"]
        if operation == "seed":
            payload = self.seed()
        elif operation == "save":
            payload = self.save(options["prepare_id"], options["idempotency_key"])
        elif operation == "validate":
            payload = self.validate(options["prepare_id"], options["idempotency_key"])
        elif operation == "recover":
            payload = recover_validation_result(options["idempotency_key"], self.user())
        else:
            payload = self.inspect(options["prepare_id"])
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def user(self):
        user, _ = User.objects.get_or_create(
            username="v44-cross-process",
            defaults={
                "real_name": "V44 Cross Process", "company_id": 44,
                "is_superuser": True, "is_staff": True, "is_active": True,
            },
        )
        user.set_password("V44-Canary-Only!")
        user.save(update_fields=["password"])
        return user

    def seed(self):
        user = self.user()
        source, _ = PurchaseReconciliation.objects.get_or_create(
            reconciliation_no="PRC-V44-A",
            defaults={
                "id": 44, "tenant_id": "tenant-v44", "company_id": 44,
                "source_key": "supplier-settlement:tenant-v44:a",
                "source_supplier_settlement_no": "SET-V44-A",
                "source_payable_check_no": "PAY-V44-A",
                "source_payable_prepare_no": "PAY-PREP-V44-A",
                "purchase_order_no": "PO-V44-A", "price_approval_no": "PRICE-V44-A",
                "supplier_id": "SUP-44", "supplier_name": "V44 Supplier",
                "legal_entity_id": "LEGAL-44", "ledger_book_id": "LEDGER-44",
                "currency": "CNY", "exchange_rate": Decimal("1.00000000"),
                "accounting_period": "2026-07", "settlement_amount": Decimal("113.00"),
                "quantity": Decimal("10.0000"), "unit": "EA",
                "source_candidate_id": "candidate-v44", "simulation_request_id": "request-v44",
                "simulation_result_id": "result-v44", "status": "matched",
                "source_snapshot_hash": hashlib.sha256(b"source-v44").hexdigest(),
                "review_id": "review-v44", "review_hash": hashlib.sha256(b"review-v44").hexdigest(),
                "command_id": "command-v44",
                "transaction_plan_id": "purchase-reconciliation-atomic-v1",
                "idempotency_key": "generate-reconciliation-v44", "created_by": user,
                "check_result_code": "PRC_CHECK_MATCHED", "difference_count": 0,
                "checked_at": timezone.now(), "checked_by": user, "version": 2,
            },
        )
        if not source.evidence_records.exists():
            for authority_type, provider, repository in (
                ("supplier_settlement", "SupplierSettlementEvidenceProvider", "SupplierSettlementAuthorityRepository"),
                ("payable_check", "PayableCheckEvidenceProvider", "PayableCheckAuthorityRepository"),
            ):
                PurchaseReconciliationEvidence.objects.create(
                    reconciliation=source, provider_code=provider, repository_code=repository,
                    authority_type=authority_type, authority_object_id=f"{authority_type}-v44",
                    authority_object_no=f"{authority_type}-NO-v44", authority_version=1,
                    business_hash=hashlib.sha256(authority_type.encode()).hexdigest(),
                    evidence={"source": authority_type},
                )
        if not source.check_executions.exists():
            PurchaseReconciliationCheckExecution.objects.create(
                reconciliation=source, idempotency_key="check-v44",
                request_hash=hashlib.sha256(b"check-v44").hexdigest(), expected_version=1,
                result_status="matched", check_result_code="PRC_CHECK_MATCHED",
                difference_count=0, actor=user, result_payload={"result": "matched"},
            )
        SupplierInvoiceAuthorityRecord.objects.get_or_create(
            tenant_id="tenant-v44", supplier_id="SUP-44",
            defaults={
                "company_id": 44, "supplier_name": "V44 Supplier",
                "seller_tax_id": "91310000V44SELLER", "status": "active",
                "authority_version": 1, "business_hash": hashlib.sha256(b"supplier-v44").hexdigest(),
            },
        )
        LegalEntityInvoiceAuthorityRecord.objects.get_or_create(
            tenant_id="tenant-v44", legal_entity_id="LEGAL-44",
            defaults={
                "company_id": 44, "legal_entity_name": "V44 Legal Entity",
                "buyer_tax_id": "91310000V44BUYER", "ledger_book_id": "LEDGER-44",
                "currency": "CNY", "status": "active", "authority_version": 1,
                "business_hash": hashlib.sha256(b"legal-v44").hexdigest(),
            },
        )
        result = generate_purchase_invoice_prepare(
            user=user, reconciliation_id=source.pk, idempotency_key="pip-v44-generate",
            expected_reconciliation_version=2, expected_check_version=2, explicit_user_action=True,
        )
        return {
            "operation": "seed", "sourceId": source.pk, "prepareId": result["data"]["id"],
            "prepareNo": result["data"]["prepareNo"], "sourceNo": source.reconciliation_no,
        }

    def invoice_data(self):
        return {
            "invoiceType": "vat_special", "invoiceCode": "V44CODE001",
            "invoiceNumber": "V44INV000001", "invoiceDate": "2026-07-23",
            "sellerName": "V44 Supplier", "sellerTaxId": "91310000V44SELLER",
            "buyerName": "V44 Legal Entity", "buyerTaxId": "91310000V44BUYER",
            "currency": "CNY", "amountExcludingTax": "100.00",
            "taxAmount": "13.00", "amountIncludingTax": "113.00",
            "lines": [{
                "lineNo": 1, "itemCode": "MAT-V44", "itemName": "V44 Material",
                "specification": "STD", "quantity": "10.0000", "unit": "EA",
                "unitPrice": "10.000000", "amountExcludingTax": "100.00",
                "taxRate": "0.130000", "taxAmount": "13.00", "amountIncludingTax": "113.00",
            }],
        }

    def prepare(self, prepare_id):
        if not prepare_id:
            raise CommandError("--prepare-id is required")
        return PurchaseInvoicePrepare.objects.get(pk=prepare_id)

    def save(self, prepare_id, key):
        prepare = self.prepare(prepare_id)
        return save_invoice_data(
            user=self.user(), prepare_id=prepare.pk, idempotency_key=key,
            expected_version=1, expected_data_version=0,
            explicit_user_action=True, invoice_data=self.invoice_data(),
        )

    def validate(self, prepare_id, key):
        prepare = self.prepare(prepare_id)
        source = prepare.source_purchase_reconciliation
        return validate_invoice_data(
            user=self.user(), prepare_id=prepare.pk, idempotency_key=key,
            expected_version=2, expected_data_version=1,
            expected_reconciliation_version=source.version, expected_check_version=source.version,
            explicit_user_action=True,
        )

    def inspect(self, prepare_id):
        prepare = self.prepare(prepare_id)
        read_model = build_validation_read_model(prepare)
        return {
            "operation": "inspect", "prepare": read_model["purchaseInvoicePrepare"],
            "invoiceData": read_model["invoiceData"], "validation": read_model["validation"],
            "invoiceIdentity": read_model["invoiceIdentity"],
            "eligibility": build_ap_draft_eligibility(prepare),
            "counts": {
                "prepares": PurchaseInvoicePrepare.objects.count(),
                "snapshots": PurchaseInvoiceDataSnapshot.objects.count(),
                "lines": PurchaseInvoiceDataLine.objects.count(),
                "executions": PurchaseInvoiceValidationExecution.objects.count(),
                "issues": PurchaseInvoiceValidationIssue.objects.count(),
                "claims": PurchaseInvoiceIdentityClaim.objects.count(),
                "saveIdempotency": BusinessActionIdempotency.objects.filter(action_code=SAVE_ACTION).count(),
                "validationIdempotency": BusinessActionIdempotency.objects.filter(action_code=VALIDATE_ACTION).count(),
                "transactions": BusinessActionTransaction.objects.filter(
                    action_code__in=[SAVE_ACTION, VALIDATE_ACTION]
                ).count(),
                "audits": BusinessActionAuditRecord.objects.filter(
                    action_code__in=[SAVE_ACTION, VALIDATE_ACTION]
                ).count(),
            },
            "downstreamCounts": read_model["downstreamCounts"],
        }
