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
    PurchaseInvoicePrepare,
    PurchaseInvoicePrepareSourceRelation,
)
from purchase_invoice_prepare.services import (
    ACTION_CODE,
    generate_purchase_invoice_prepare,
    recover_generation_result,
)


class Command(BaseCommand):
    help = "V43 cross-process seed/generate/inspect probe"

    def add_arguments(self, parser):
        parser.add_argument("operation", choices=("seed", "generate", "recover", "inspect"))
        parser.add_argument("--suffix", default="a")
        parser.add_argument("--source-id", type=int)
        parser.add_argument("--idempotency-key", default="")

    def handle(self, *args, **options):
        operation = options["operation"]
        if operation == "seed":
            payload = self.seed(options["suffix"])
        elif operation == "generate":
            payload = self.generate(options["source_id"], options["idempotency_key"])
        elif operation == "recover":
            payload = recover_generation_result(options["idempotency_key"])
        else:
            payload = self.inspect(options["source_id"])
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def user(self):
        user, _ = User.objects.get_or_create(
            username="v43-cross-process",
            defaults={
                "real_name": "V43 Cross Process",
                "company_id": 43,
                "is_superuser": True,
                "is_staff": True,
                "is_active": True,
            },
        )
        user.set_password("V43-Canary-Only!")
        user.save(update_fields=["password"])
        return user

    def seed(self, suffix):
        user = self.user()
        no = f"PRC-V43-{suffix.upper()}"
        obj, _ = PurchaseReconciliation.objects.get_or_create(
            reconciliation_no=no,
            defaults={
                "id": 43,
                "tenant_id": "tenant-v43",
                "company_id": 43,
                "source_key": f"supplier-settlement:tenant-v43:{suffix}",
                "source_supplier_settlement_no": f"SET-V43-{suffix}",
                "source_payable_check_no": f"PAY-V43-{suffix}",
                "source_payable_prepare_no": f"PAY-PREP-V43-{suffix}",
                "purchase_order_no": f"PO-V43-{suffix}",
                "price_approval_no": f"PRICE-V43-{suffix}",
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
            },
        )
        if not obj.evidence_records.exists():
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
        if not obj.check_executions.exists():
            PurchaseReconciliationCheckExecution.objects.create(
                reconciliation=obj,
                idempotency_key=f"check-{suffix}",
                request_hash=hashlib.sha256(f"check:{suffix}".encode()).hexdigest(),
                expected_version=1,
                result_status="matched",
                check_result_code="PRC_CHECK_MATCHED",
                difference_count=0,
                actor=user,
                result_payload={"result": "matched"},
            )
        return {
            "operation": "seed",
            "sourceId": obj.pk,
            "reconciliationNo": obj.reconciliation_no,
            "status": obj.status,
            "version": obj.version,
            "checkVersion": obj.version,
        }

    def generate(self, source_id, idempotency_key):
        if not source_id:
            raise CommandError("--source-id is required")
        source = PurchaseReconciliation.objects.get(pk=source_id)
        return generate_purchase_invoice_prepare(
            user=self.user(),
            reconciliation_id=source.pk,
            idempotency_key=idempotency_key,
            expected_reconciliation_version=source.version,
            expected_check_version=source.version,
            explicit_user_action=True,
        )

    def inspect(self, source_id):
        source = PurchaseReconciliation.objects.get(pk=source_id)
        targets = PurchaseInvoicePrepare.objects.filter(source_purchase_reconciliation=source)
        obj = targets.first()
        return {
            "operation": "inspect",
            "sourceId": source.pk,
            "reconciliationNo": source.reconciliation_no,
            "sourceStatus": source.status,
            "sourceCheckResultCode": source.check_result_code,
            "sourceDifferenceCount": source.difference_count,
            "sourceVersion": source.version,
            "checkVersion": source.version,
            "evidenceCount": source.evidence_records.count(),
            "targetCount": targets.count(),
            "prepare": {
                "id": obj.pk,
                "prepareNo": obj.prepare_no,
                "status": obj.status,
                "invoiceDataStatus": obj.invoice_data_status,
                "sourceDocumentType": obj.source_document_type,
                "sourcePurchaseReconciliationNo": obj.source_purchase_reconciliation_no,
                "idempotencyKey": obj.idempotency_key,
                "transactionId": obj.transaction_id,
                "auditRecordId": obj.audit_record_id,
            } if obj else None,
            "relationCount": PurchaseInvoicePrepareSourceRelation.objects.filter(source_id=source.pk).count(),
            "auditCount": BusinessActionAuditRecord.objects.filter(action_code=ACTION_CODE, reconciliation=source).count(),
            "transactionCount": BusinessActionTransaction.objects.filter(action_code=ACTION_CODE, reconciliation=source).count(),
            "idempotencyCount": BusinessActionIdempotency.objects.filter(action_code=ACTION_CODE, source_key=f"purchaseReconciliation:{source.pk}").count(),
            "numberCount": BusinessDocumentNumberReservation.objects.filter(document_type="purchase_invoice_prepare", target=source).count(),
            "downstreamCounts": {
                "accountPayableDrafts": 0,
                "paymentApplications": 0,
                "payments": 0,
                "paymentVouchers": 0,
                "writeoffs": 0,
                "ledgerEntries": 0,
                "postings": 0,
                "bankTransactions": 0,
            },
        }
