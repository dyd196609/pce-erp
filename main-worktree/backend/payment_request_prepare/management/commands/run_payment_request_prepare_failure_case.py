import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from payable_confirmation_prepare.models import PayableConfirmationPrepare
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionSourceLock,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from reconciliation.services import ReconciliationError

from payment_request_prepare.management.commands.ensure_payment_request_prepare_canary import (
    authority_defaults,
)
from payment_request_prepare.models import (
    PaymentRequestDataSnapshot,
    PaymentRequestPrepare,
    PaymentRequestPrepareSourceRelation,
    PaymentRequestPrepareSourceSnapshot,
    PaymentRequestPrepareValidationExecution,
    PaymentRequestPrepareValidationIssue,
)
from payment_request_prepare.services import (
    GENERATE_ACTION,
    GENERATE_FAILURE_STEPS,
    SAVE_ACTION,
    SAVE_FAILURE_STEPS,
    VALIDATE_ACTION,
    VALIDATE_FAILURE_STEPS,
    generate_payment_request_prepare,
    recover_action_result,
    save_payment_request_prepare_data,
    validate_payment_request_prepare,
)


class Command(BaseCommand):
    help = "Run one V47 injected failure case in an isolated database clone"

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["generate", "save", "validate"])
        parser.add_argument("failure_step")

    def handle(self, *args, **options):
        action = options["action"]
        step = options["failure_step"]
        allowed = {
            "generate": GENERATE_FAILURE_STEPS,
            "save": SAVE_FAILURE_STEPS,
            "validate": VALIDATE_FAILURE_STEPS,
        }[action]
        if step not in allowed:
            raise CommandError(f"Unsupported {action} failure step: {step}")

        original = PaymentRequestPrepare.objects.order_by("prepare_no").first()
        if not original:
            raise CommandError("Persistent clone has no V47 target")
        source_id = original.source_payable_confirmation_prepare_id
        action_codes = [GENERATE_ACTION, SAVE_ACTION, VALIDATE_ACTION]
        transaction_ids = list(
            BusinessActionTransaction.objects.filter(
                action_code__in=action_codes,
                source_key=original.source_key,
            ).values_list("id", flat=True)
        )
        reservation_id = original.number_reservation_id
        with transaction.atomic():
            executions = PaymentRequestPrepareValidationExecution.objects.filter(
                payment_request_prepare=original
            )
            PaymentRequestPrepareValidationIssue.objects.filter(
                validation_execution__in=executions
            ).delete()
            executions.delete()
            PaymentRequestDataSnapshot.objects.filter(
                payment_request_prepare=original
            ).delete()
            PaymentRequestPrepareSourceRelation.objects.filter(
                payment_request_prepare=original
            ).delete()
            PaymentRequestPrepareSourceSnapshot.objects.filter(
                payment_request_prepare=original
            ).delete()
            original.delete()
            BusinessActionAuditRecord.objects.filter(
                transaction_id__in=transaction_ids
            ).delete()
            BusinessActionTransaction.objects.filter(id__in=transaction_ids).delete()
            BusinessActionIdempotency.objects.filter(
                action_code__in=action_codes,
                source_key=f"payableConfirmationPrepare:{source_id}",
            ).delete()
            BusinessDocumentNumberReservation.objects.filter(pk=reservation_id).delete()
            BusinessActionSourceLock.objects.filter(
                lock_key__contains=f":{source_id}"
            ).delete()

        source = PayableConfirmationPrepare.objects.select_related(
            "source_purchase_accounts_payable_draft__source_purchase_invoice_prepare",
            "source_purchase_accounts_payable_draft__source_purchase_reconciliation",
            "accounting_snapshot",
            "audit_record",
        ).get(pk=source_id)
        actor = get_user_model().objects.get(username="pce-v47-canary")
        planned_date = source.due_date
        payee_id, payer_id = authority_defaults(source, planned_date, 99)
        prefix = f"fault-{action}-{step}"

        target = None
        if action in {"save", "validate"}:
            target = PaymentRequestPrepare.objects.get(pk=generate_payment_request_prepare(
                user=actor,
                source=source,
                idempotency_key=f"{prefix}-setup-generate",
                expected_source_version=source.version,
                explicit_user_action=True,
            )["data"]["id"])
        if action == "validate":
            save_payment_request_prepare_data(
                user=actor,
                obj=target,
                payload={
                    "payeeBankAccountId": payee_id,
                    "payerBankAccountId": payer_id,
                    "paymentMethodCode": "BANK_TRANSFER",
                    "plannedPaymentDate": planned_date.isoformat(),
                    "paymentAmount": str(source.payable_amount),
                    "paymentPurpose": "故障矩阵隔离测试",
                    "paymentSummary": source.prepare_no,
                },
                idempotency_key=f"{prefix}-setup-save",
                expected_version=target.version,
                expected_payment_data_version=0,
                explicit_user_action=True,
            )
            target.refresh_from_db()

        before = {
            "targets": PaymentRequestPrepare.objects.count(),
            "paymentData": PaymentRequestDataSnapshot.objects.count(),
            "validations": PaymentRequestPrepareValidationExecution.objects.count(),
            "numbers": BusinessDocumentNumberReservation.objects.filter(
                document_type="payment_request_prepare"
            ).count(),
            "idempotencies": BusinessActionIdempotency.objects.filter(
                action_code__in=action_codes
            ).count(),
            "transactions": BusinessActionTransaction.objects.filter(
                action_code__in=action_codes
            ).count(),
            "audits": BusinessActionAuditRecord.objects.filter(
                action_code__in=action_codes
            ).count(),
        }
        error_code = ""
        classification = "rollback"
        try:
            if action == "generate":
                generate_payment_request_prepare(
                    user=actor,
                    source=source,
                    idempotency_key=prefix,
                    expected_source_version=source.version,
                    explicit_user_action=True,
                    failure_step=step,
                )
            elif action == "save":
                save_payment_request_prepare_data(
                    user=actor,
                    obj=target,
                    payload={
                        "payeeBankAccountId": payee_id,
                        "payerBankAccountId": payer_id,
                        "paymentMethodCode": "BANK_TRANSFER",
                        "plannedPaymentDate": planned_date.isoformat(),
                        "paymentAmount": str(source.payable_amount),
                        "paymentPurpose": "故障矩阵隔离测试",
                        "paymentSummary": source.prepare_no,
                    },
                    idempotency_key=prefix,
                    expected_version=target.version,
                    expected_payment_data_version=0,
                    explicit_user_action=True,
                    failure_step=step,
                )
            else:
                validate_payment_request_prepare(
                    user=actor,
                    obj=target,
                    idempotency_key=prefix,
                    expected_version=target.version,
                    expected_payment_data_version=target.current_payment_data_version,
                    expected_confirmation_version=source.version,
                    expected_accounting_data_version=source.accounting_data_version,
                    expected_confirmation_validation_version=source.validation_version,
                    explicit_user_action=True,
                    failure_step=step,
                )
        except ReconciliationError as exc:
            error_code = exc.code
            if step == "before_response" and exc.code == "PRP_COMMIT_UNKNOWN":
                classification = "commit_unknown_recoverable"
                recovered = recover_action_result(
                    {"generate": GENERATE_ACTION, "save": SAVE_ACTION, "validate": VALIDATE_ACTION}[action],
                    prefix,
                )
                if recovered["classification"] != "existing_result":
                    raise CommandError("Commit-unknown result was not recoverable")
        else:
            raise CommandError("Injected failure did not raise")

        after = {
            "targets": PaymentRequestPrepare.objects.count(),
            "paymentData": PaymentRequestDataSnapshot.objects.count(),
            "validations": PaymentRequestPrepareValidationExecution.objects.count(),
            "numbers": BusinessDocumentNumberReservation.objects.filter(
                document_type="payment_request_prepare"
            ).count(),
            "idempotencies": BusinessActionIdempotency.objects.filter(
                action_code__in=action_codes
            ).count(),
            "transactions": BusinessActionTransaction.objects.filter(
                action_code__in=action_codes
            ).count(),
            "audits": BusinessActionAuditRecord.objects.filter(
                action_code__in=action_codes
            ).count(),
        }
        zero_residual = before == after
        passed = (
            zero_residual
            if classification == "rollback"
            else after["targets"] == before["targets"] + (
                1 if action == "generate" else 0
            )
        )
        payload = {
            "result": "passed" if passed else "failed",
            "version": "V1.14.2.8.4.7.47",
            "action": action,
            "failureStep": step,
            "classification": classification,
            "errorCode": error_code,
            "before": before,
            "after": after,
            "zeroResidual": zero_residual,
            "paymentRequestCreated": False,
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        if not passed:
            raise CommandError(json.dumps(payload, ensure_ascii=False))
