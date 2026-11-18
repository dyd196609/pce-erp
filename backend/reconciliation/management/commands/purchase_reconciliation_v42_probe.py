import hashlib
import json
import time
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import OperationalError
from django.utils import timezone

from reconciliation.checking import build_invoice_prepare_eligibility, complete_reconciliation_check
from reconciliation.models import (
    PayableCheckAuthorityRecord,
    PurchaseReconciliation,
    PurchaseReconciliationCheckExecution,
    PurchaseReconciliationDifference,
    PurchaseReconciliationEvidence,
    PurchaseReconciliationReview,
    PurchaseReconciliationSourceSnapshot,
    SupplierSettlementAuthorityRecord,
)
from reconciliation.services import ReconciliationError, generate_purchase_reconciliation
from system.models import User


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("operation", choices=["seed", "generate", "check", "inspect"])
        parser.add_argument("--suffix", required=True)
        parser.add_argument("--idempotency-key", default="")
        parser.add_argument("--expected-version", type=int, default=1)
        parser.add_argument("--payable-amount", default="100.00")
        parser.add_argument("--omit-source", choices=["", "settlement", "payable"], default="")
        parser.add_argument("--failure-step", default="")

    def handle(self, *args, **options):
        suffix = options["suffix"]
        operation = options["operation"]
        if operation == "seed":
            self.seed(suffix, options)
            self.write({"operation": operation, "suffix": suffix, "result": "passed"})
            return
        if operation == "generate":
            user = self.user()
            source = PurchaseReconciliationSourceSnapshot.objects.get(source_key=f"supplier-settlement:tenant-v41:PCE-REG-{suffix}")
            review = PurchaseReconciliationReview.objects.get(review_id=f"review-{suffix}")
            result = generate_purchase_reconciliation(
                user=user,
                source_key=source.source_key,
                final_review_id=review.review_id,
                idempotency_key=options["idempotency_key"] or f"generate-{suffix}",
            )
            self.write(result)
            return
        if operation == "check":
            self.run_check(suffix, options)
            return
        obj = PurchaseReconciliation.objects.get(source_supplier_settlement_no=f"PCE-REG-{suffix}")
        eligibility = build_invoice_prepare_eligibility(obj)
        self.write({
            "operation": operation,
            "id": obj.pk,
            "reconciliationNo": obj.reconciliation_no,
            "status": obj.status,
            "checkResultCode": obj.check_result_code,
            "differenceCount": obj.difference_count,
            "version": obj.version,
            "evidenceCount": PurchaseReconciliationEvidence.objects.filter(reconciliation=obj).count(),
            "differenceRowCount": PurchaseReconciliationDifference.objects.filter(reconciliation=obj).count(),
            "checkExecutionCount": PurchaseReconciliationCheckExecution.objects.filter(reconciliation=obj).count(),
            "eligibility": eligibility,
            "invoicePrepareCount": 0,
            "accountPayableCount": 0,
            "paymentCount": 0,
            "voucherCount": 0,
            "writeoffCount": 0,
            "ledgerCount": 0,
            "postingCount": 0,
            "bankTransactionCount": 0,
        })

    def seed(self, suffix, options):
        source_key = f"supplier-settlement:tenant-v41:PCE-REG-{suffix}"
        snapshot_hash = digest(source_key)
        source, _ = PurchaseReconciliationSourceSnapshot.objects.update_or_create(
            source_key=source_key,
            defaults={
                "supplier_settlement_no": f"PCE-REG-{suffix}", "tenant_id": "tenant-v41", "company_id": 41,
                "supplier_id": "SUP-42", "supplier_name": "V42 Canary Supplier", "legal_entity_id": "LEGAL-42",
                "ledger_book_id": "LEDGER-42", "currency": "CNY", "exchange_rate": Decimal("1"),
                "accounting_period": "2026-07", "amount": Decimal("100.00"), "quantity": Decimal("10"),
                "source_payable_check_no": f"PAYABLE-{suffix}", "source_payable_prepare_no": f"PREPARE-{suffix}",
                "purchase_order_no": f"PO-{suffix}", "price_approval_no": f"PRICE-{suffix}", "unit": "EA",
                "source_candidate_id": f"candidate-{suffix}", "simulation_request_id": f"simulation-request-{suffix}",
                "simulation_result_id": f"simulation-result-{suffix}", "lifecycle_state": "reconciling",
                "payable_status": "payable_prepared", "simulation_integrity": "passed", "snapshot_hash": snapshot_hash,
            },
        )
        PurchaseReconciliationReview.objects.update_or_create(
            review_id=f"review-{suffix}",
            defaults={
                "source": source, "state": "review_passed", "decision": "approved", "simulation_integrity": "passed",
                "audit_complete": True, "fatal_risk_count": 0, "source_snapshot_hash": snapshot_hash,
                "business_hash": digest(f"review:{suffix}"), "supplier_id": "SUP-42", "legal_entity_id": "LEGAL-42",
                "ledger_book_id": "LEDGER-42", "currency": "CNY", "amount": Decimal("100.00"), "reviewed_at": timezone.now(),
            },
        )
        if options["omit_source"] != "settlement":
            SupplierSettlementAuthorityRecord.objects.update_or_create(
                settlement_no=f"PCE-REG-{suffix}",
                defaults={
                    "authority_object_id": f"SCM-SETTLEMENT-{suffix}", "tenant_id": "tenant-v41", "company_id": 41,
                    "supplier_id": "SUP-42", "supplier_name": "V42 Canary Supplier", "legal_entity_id": "LEGAL-42",
                    "ledger_book_id": "LEDGER-42", "currency": "CNY", "amount": Decimal("100.00"),
                    "quantity": Decimal("10"), "business_status": "reconciling", "authority_version": 1,
                    "business_hash": digest(f"scm:{suffix}"), "occurred_at": timezone.now(),
                },
            )
        if options["omit_source"] != "payable":
            PayableCheckAuthorityRecord.objects.update_or_create(
                payable_check_no=f"PAYABLE-{suffix}",
                defaults={
                    "authority_object_id": f"FIN-PAYABLE-{suffix}", "tenant_id": "tenant-v41", "company_id": 41,
                    "supplier_id": "SUP-42", "legal_entity_id": "LEGAL-42", "ledger_book_id": "LEDGER-42",
                    "currency": "CNY", "checked_amount": Decimal(options["payable_amount"]), "checked_quantity": Decimal("10"),
                    "business_status": "payable_prepared", "authority_version": 1,
                    "business_hash": digest(f"finance:{suffix}"), "occurred_at": timezone.now(),
                },
            )

    def user(self):
        user, _ = User.objects.get_or_create(
            username="v42-canary",
            defaults={"real_name": "V42 Canary", "company_id": 41, "is_active": True, "is_superuser": False},
        )
        permissions = Permission.objects.filter(codename__in=["generate_purchase_reconciliation", "complete_purchase_reconciliation"])
        user.user_permissions.add(*permissions)
        return user

    def run_check(self, suffix, options):
        obj = PurchaseReconciliation.objects.get(source_supplier_settlement_no=f"PCE-REG-{suffix}")
        last_error = None
        for _ in range(20):
            try:
                result = complete_reconciliation_check(
                    user=self.user(),
                    reconciliation_id=obj.pk,
                    idempotency_key=options["idempotency_key"] or f"check-{suffix}",
                    expected_version=options["expected_version"],
                    explicit_user_action=True,
                    failure_step=options["failure_step"],
                )
                self.write(result)
                return
            except OperationalError as error:
                last_error = error
                time.sleep(0.05)
            except ReconciliationError as error:
                self.write({"result": "rejected", "errorCode": error.code, "retryable": error.retryable})
                return
        raise last_error

    def write(self, value):
        self.stdout.write(json.dumps(value, ensure_ascii=True, separators=(",", ":")))
