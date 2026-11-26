import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionSourceLock,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from reconciliation.services import ReconciliationError

from payable_confirmation_prepare.models import (
    PayableConfirmationAccountingSnapshot,
    PayableConfirmationPrepare,
    PayableConfirmationPrepareSourceRelation,
    PayableConfirmationValidationExecution,
)
from payable_confirmation_prepare.services import (
    ACTION_CODE,
    FAILURE_STEPS,
    generate_payable_confirmation_prepare,
    recover_generation_result,
)


def snapshot_payload(snapshot, source):
    return {
        "accountsPayableAccount": snapshot.accounts_payable_account,
        "inputTaxAccount": snapshot.input_tax_account,
        "counterpartyAccount": snapshot.counterparty_account,
        "supplierAuxiliaryId": snapshot.supplier_auxiliary_id,
        "departmentId": snapshot.department_id,
        "costCenterId": snapshot.cost_center_id,
        "projectId": snapshot.project_id,
        "paymentTermsCode": snapshot.payment_terms_code,
        "paymentTermsDays": snapshot.payment_terms_days,
        "dueDate": snapshot.due_date.isoformat(),
        "accountingDate": snapshot.accounting_date.isoformat(),
        "accountingPeriod": snapshot.accounting_period,
        "periodStatus": snapshot.period_status,
        "debitTotal": str(snapshot.debit_total),
        "creditTotal": str(snapshot.credit_total),
        "sourceDraftVersion": source.version,
    }


class Command(BaseCommand):
    help = "Run one V46 failure injection against an isolated regression clone"

    def add_arguments(self, parser):
        parser.add_argument("failure_step", choices=FAILURE_STEPS)

    def handle(self, *args, **options):
        step = options["failure_step"]
        source = PurchaseAccountsPayableDraft.objects.order_by("draft_no").first()
        if not source:
            raise CommandError("Regression clone has no AP draft source")
        original = PayableConfirmationPrepare.objects.select_related(
            "accounting_snapshot", "audit_record", "business_transaction",
            "number_reservation", "created_by",
        ).get(source_purchase_accounts_payable_draft=source)
        actor = original.created_by
        payload = snapshot_payload(original.accounting_snapshot, source)
        old_idem_key = original.idempotency_key
        old_tx_id = original.business_transaction_id
        old_number_id = original.number_reservation_id
        old_audit_id = original.audit_record_id
        with transaction.atomic():
            PayableConfirmationPrepareSourceRelation.objects.filter(
                payable_confirmation_prepare=original
            ).delete()
            for execution in PayableConfirmationValidationExecution.objects.filter(
                payable_confirmation_prepare=original
            ):
                execution.issues.all().delete()
                execution.delete()
            PayableConfirmationAccountingSnapshot.objects.filter(
                payable_confirmation_prepare=original
            ).delete()
            original.audit_record = None
            original.save(update_fields=["audit_record", "updated_at"])
            original.delete()
            BusinessActionAuditRecord.objects.filter(pk=old_audit_id).delete()
            BusinessActionTransaction.objects.filter(pk=old_tx_id).delete()
            BusinessDocumentNumberReservation.objects.filter(pk=old_number_id).delete()
            BusinessActionIdempotency.objects.filter(
                action_code=ACTION_CODE, idempotency_key=old_idem_key
            ).delete()
            BusinessActionSourceLock.objects.filter(
                lock_key=f"payable_confirmation_prepare_generation:{source.pk}"
            ).delete()
        idempotency_key = f"pcp-v46-fault-{step}"
        caught = None
        try:
            generate_payable_confirmation_prepare(
                user=actor,
                source=source,
                accounting_data=payload,
                idempotency_key=idempotency_key,
                expected_source_version=source.version,
                failure_step=step,
            )
        except ReconciliationError as exc:
            caught = exc
        if not caught:
            raise CommandError(f"Failure step did not fail: {step}")
        target_count = PayableConfirmationPrepare.objects.filter(
            source_purchase_accounts_payable_draft=source
        ).count()
        idem = BusinessActionIdempotency.objects.filter(
            action_code=ACTION_CODE, idempotency_key=idempotency_key
        ).first()
        if step == "before_response":
            recovered = recover_generation_result(idempotency_key)
            passed = (
                caught.code == "PCP_COMMIT_UNKNOWN"
                and target_count == 1
                and idem is not None
                and idem.status == BusinessActionIdempotency.Status.COMMITTED
                and recovered["classification"] == "existing_result"
            )
            expected_classification = "commit_unknown_recoverable"
        else:
            residual = {
                "target": target_count,
                "idempotency": BusinessActionIdempotency.objects.filter(
                    action_code=ACTION_CODE, idempotency_key=idempotency_key
                ).count(),
                "number": BusinessDocumentNumberReservation.objects.filter(
                    document_type="payable_confirmation_prepare",
                    idempotency_key=idempotency_key,
                ).count(),
                "transaction": BusinessActionTransaction.objects.filter(
                    action_code=ACTION_CODE,
                    idempotency_key=idempotency_key,
                ).count(),
                "audit": BusinessActionAuditRecord.objects.filter(
                    action_code=ACTION_CODE,
                    idempotency_key=idempotency_key,
                ).count(),
            }
            passed = all(value == 0 for value in residual.values())
            expected_classification = "rolled_back_zero_residual"
        result = {
            "result": "passed" if passed else "failed",
            "version": "V1.14.2.8.4.7.46",
            "failureStep": step,
            "errorCode": caught.code,
            "expectedClassification": expected_classification,
            "targetCount": target_count,
            "paymentRequestPrepareCreated": False,
            "passed": passed,
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if not passed:
            raise CommandError(json.dumps(result))
