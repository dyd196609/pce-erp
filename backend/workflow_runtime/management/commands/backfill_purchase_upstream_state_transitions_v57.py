import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from purchase_invoice_prepare.models import PurchaseInvoicePrepare
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    PurchaseReconciliation,
)
from reconciliation.services import canonical_hash
from workflow_runtime.models import BusinessStateTransition


class Command(BaseCommand):
    help = "Backfill V57 transition evidence in the isolated acceptance copy only."

    def handle(self, *args, **options):
        database = Path(settings.DATABASES["default"]["NAME"]).resolve()
        if (
            not getattr(settings, "PCE_V57_ISOLATED_ACCEPTANCE", False)
            or database.name
            != "pce-purchase-upstream-governance-v57-iab.sqlite3"
        ):
            raise CommandError(
                "V57 backfill is restricted to the isolated acceptance database"
            )
        with transaction.atomic():
            invoice_count = self._backfill_invoice_prepares()
            reconciliation_count = self._backfill_reconciliations()
        self.stdout.write(self.style.SUCCESS(
            f"V57 isolated backfill passed: invoice={invoice_count}, "
            f"reconciliation={reconciliation_count}"
        ))

    def _backfill_invoice_prepares(self):
        count = 0
        for prepare in PurchaseInvoicePrepare.objects.filter(
            status=PurchaseInvoicePrepare.Status.PREPARED
        ):
            if BusinessStateTransition.objects.filter(
                object_type="purchase_invoice_prepare",
                object_id=prepare.pk,
            ).exists():
                continue
            audit = BusinessActionAuditRecord.objects.filter(
                action_code="VALIDATE_PURCHASE_INVOICE_PREPARE",
                target_type="purchaseInvoicePrepare",
                target_id=prepare.pk,
                result="committed",
            ).order_by("-created_at", "-id").first()
            if not audit:
                raise CommandError(
                    f"Authoritative invoice validation audit missing: {prepare.pk}"
                )
            BusinessStateTransition.objects.create(
                object_type="purchase_invoice_prepare",
                object_id=prepare.pk,
                source_state=PurchaseInvoicePrepare.Status.DRAFT,
                target_state=PurchaseInvoicePrepare.Status.PREPARED,
                action_code="VALIDATE_PURCHASE_INVOICE_PREPARE",
                operator=audit.actor,
                reason="Historical validation evidence backfill",
                audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                version=1,
            )
            count += 1
        return count

    def _backfill_reconciliations(self):
        count = 0
        for reconciliation in PurchaseReconciliation.objects.exclude(
            status=PurchaseReconciliation.Status.DRAFT
        ):
            if BusinessStateTransition.objects.filter(
                object_type="purchase_reconciliation",
                object_id=reconciliation.pk,
            ).exists():
                continue
            execution = reconciliation.check_executions.order_by(
                "-created_at",
                "-id",
            ).first()
            if not execution:
                raise CommandError(
                    f"Authoritative reconciliation check missing: "
                    f"{reconciliation.pk}"
                )
            evidence = {
                "historicalBackfill": True,
                "checkExecutionId": execution.pk,
                "resultStatus": execution.result_status,
                "checkResultCode": execution.check_result_code,
                "differenceCount": execution.difference_count,
            }
            evidence_hash = canonical_hash(evidence)
            idempotency_key = f"v57-prc-backfill-{reconciliation.pk}"
            action_code = "complete_purchase_reconciliation"
            action_tx = BusinessActionTransaction.objects.create(
                transaction_id=f"V57-PRC-{uuid.uuid4().hex}",
                action_code=action_code,
                idempotency_key=idempotency_key,
                tenant_id=reconciliation.tenant_id,
                source_key=reconciliation.source_key,
                command_id=f"V57-PRC-CMD-{uuid.uuid4().hex}",
                transaction_plan_id="v57-historical-evidence-backfill",
                review_id=f"v57-check:{execution.pk}",
                review_hash=evidence_hash,
                status=BusinessActionTransaction.Status.COMMITTED,
                outcome="historical_evidence_backfill",
                commit_status="committed",
                recovery_status="not_required",
                result_hash=evidence_hash,
                reconciliation=reconciliation,
            )
            audit = BusinessActionAuditRecord.objects.create(
                transaction=action_tx,
                action_code=action_code,
                tenant_id=reconciliation.tenant_id,
                actor=execution.actor,
                source_key=reconciliation.source_key,
                reconciliation=reconciliation,
                result="committed",
                target_type="purchase_reconciliation",
                target_id=reconciliation.pk,
                target_no=reconciliation.reconciliation_no,
                review_id=action_tx.review_id,
                review_hash=evidence_hash,
                command_id=action_tx.command_id,
                idempotency_key=idempotency_key,
                actor_name=execution.actor.get_username(),
                tenant_or_scope=(
                    f"{reconciliation.tenant_id}:company:"
                    f"{reconciliation.company_id}"
                ),
                evidence_hash=evidence_hash,
                evidence=evidence,
            )
            BusinessStateTransition.objects.create(
                object_type="purchase_reconciliation",
                object_id=reconciliation.pk,
                source_state=PurchaseReconciliation.Status.DRAFT,
                target_state=reconciliation.status,
                action_code=action_code,
                operator=execution.actor,
                reason="Historical reconciliation check evidence backfill",
                audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                version=1,
            )
            count += 1
        return count
