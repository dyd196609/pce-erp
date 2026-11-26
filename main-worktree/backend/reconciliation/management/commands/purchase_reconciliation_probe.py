import hashlib
import json
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessDocumentNumberReservation,
    PurchaseReconciliation,
    PurchaseReconciliationReview,
    PurchaseReconciliationSourceRelation,
    PurchaseReconciliationSourceSnapshot,
)
from reconciliation.services import ReconciliationError, generate_purchase_reconciliation, recover_by_idempotency
from system.models import User


class Command(BaseCommand):
    help = "Isolated-database probe for purchase reconciliation persistence"

    def add_arguments(self, parser):
        parser.add_argument("mode", choices=["seed", "generate", "inspect", "recover"])
        parser.add_argument("--suffix", default="concurrent")
        parser.add_argument("--idempotency-key", default="idem-concurrent")

    def handle(self, *args, **options):
        suffix = options["suffix"]
        source_key = f"supplier-settlement:tenant-v41:PCE-REG-{suffix}"
        review_id = f"review-{suffix}"
        idempotency_key = options["idempotency_key"]
        if options["mode"] == "seed":
            user, _ = User.objects.get_or_create(
                username="v41-canary-operator",
                defaults={"real_name": "V41 Canary Operator", "company_id": 41, "is_active": True, "is_superuser": True},
            )
            snapshot_hash = hashlib.sha256(source_key.encode()).hexdigest()
            source, _ = PurchaseReconciliationSourceSnapshot.objects.get_or_create(
                source_key=source_key,
                defaults={"supplier_settlement_no": f"PCE-REG-{suffix}", "tenant_id": "tenant-v41", "company_id": 41, "supplier_id": "SUP-41", "supplier_name": "Test Supplier 41", "legal_entity_id": "LEGAL-TEST-41", "ledger_book_id": "LEDGER-TEST-41", "currency": "CNY", "exchange_rate": Decimal("1.00000000"), "accounting_period": "2026-07", "amount": Decimal("100.00"), "quantity": Decimal("10.0000"), "unit": "EA", "source_payable_check_no": f"PAYABLE-{suffix}", "source_payable_prepare_no": f"PREPARE-{suffix}", "purchase_order_no": f"PO-{suffix}", "price_approval_no": f"PRICE-{suffix}", "source_candidate_id": f"candidate-{suffix}", "simulation_request_id": f"simulation-request-{suffix}", "simulation_result_id": f"simulation-result-{suffix}", "lifecycle_state": "reconciling", "payable_status": "payable_prepared", "simulation_integrity": "passed", "snapshot_hash": snapshot_hash},
            )
            PurchaseReconciliationReview.objects.get_or_create(
                review_id=review_id,
                defaults={"source": source, "state": "review_passed", "decision": "approved", "simulation_integrity": "passed", "audit_complete": True, "fatal_risk_count": 0, "source_snapshot_hash": snapshot_hash, "business_hash": hashlib.sha256(review_id.encode()).hexdigest(), "supplier_id": "SUP-41", "legal_entity_id": "LEGAL-TEST-41", "ledger_book_id": "LEDGER-TEST-41", "currency": "CNY", "amount": Decimal("100.00"), "reviewed_at": timezone.now()},
            )
            self.stdout.write(json.dumps({"mode": "seed", "userId": user.pk, "sourceKey": source_key, "reviewId": review_id}))
            return
        if options["mode"] == "generate":
            user = User.objects.get(username="v41-canary-operator")
            try:
                result = generate_purchase_reconciliation(user=user, source_key=source_key, final_review_id=review_id, idempotency_key=idempotency_key)
                self.stdout.write(json.dumps({"mode": "generate", "result": "passed", "data": result}))
            except ReconciliationError as error:
                self.stdout.write(json.dumps({"mode": "generate", "result": "rejected", "errorCode": error.code}))
            return
        if options["mode"] == "recover":
            self.stdout.write(json.dumps({"mode": "recover", **recover_by_idempotency(idempotency_key)}))
            return
        obj = PurchaseReconciliation.objects.filter(source_key=source_key).first()
        self.stdout.write(json.dumps({
            "mode": "inspect", "objectCount": PurchaseReconciliation.objects.filter(source_key=source_key).count(),
            "relationCount": PurchaseReconciliationSourceRelation.objects.filter(source_key=source_key).count(),
            "auditCount": BusinessActionAuditRecord.objects.filter(source_key=source_key).count(),
            "idempotencyCount": BusinessActionIdempotency.objects.filter(idempotency_key=idempotency_key).count(),
            "numberReservationCount": BusinessDocumentNumberReservation.objects.filter(idempotency_key=idempotency_key).count(),
            "reconciliationNo": obj.reconciliation_no if obj else None, "targetId": obj.pk if obj else None, "status": obj.status if obj else None, "sourceKey": source_key,
        }))
