import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from payment_request.management.commands.ensure_payment_request_canary import (
    ensure_policy,
    ensure_role,
    ensure_user,
)
from payment_request.models import (
    PaymentRequest,
    PaymentRequestSourceRelation,
    PaymentRequestSourceSnapshot,
    PaymentRequestSubmissionSnapshot,
    PaymentRequestWorkflowRelation,
)
from payment_request.services import (
    APPROVAL_FAILURE_STEPS,
    GENERATE_FAILURE_STEPS,
    REJECTION_FAILURE_STEPS,
    SUBMIT_FAILURE_STEPS,
    ReconciliationError,
    decide_payment_request,
    generate_payment_request,
    submit_payment_request,
)
from payment_request_prepare.models import PaymentRequestPrepare
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
    BusinessActionSourceLock,
)
from workflow_runtime.models import ApprovalDecision, ApprovalTask, WorkflowInstance


FAILURE_STEPS = {
    "generate": GENERATE_FAILURE_STEPS,
    "submit": SUBMIT_FAILURE_STEPS,
    "approve": APPROVAL_FAILURE_STEPS,
    "reject": REJECTION_FAILURE_STEPS,
}


def counts():
    return {
        "requests": PaymentRequest.objects.count(),
        "transactions": BusinessActionTransaction.objects.filter(
            action_code__in=[
                "GENERATE_PAYMENT_REQUEST",
                "SUBMIT_PAYMENT_REQUEST",
                "APPROVE_PAYMENT_REQUEST",
                "REJECT_PAYMENT_REQUEST",
            ]
        ).count(),
        "audits": BusinessActionAuditRecord.objects.filter(
            action_code__in=[
                "GENERATE_PAYMENT_REQUEST",
                "SUBMIT_PAYMENT_REQUEST",
                "APPROVE_PAYMENT_REQUEST",
                "REJECT_PAYMENT_REQUEST",
            ]
        ).count(),
        "idempotency": BusinessActionIdempotency.objects.filter(
            action_code__in=[
                "GENERATE_PAYMENT_REQUEST",
                "SUBMIT_PAYMENT_REQUEST",
                "APPROVE_PAYMENT_REQUEST",
                "REJECT_PAYMENT_REQUEST",
            ]
        ).count(),
        "numbers": BusinessDocumentNumberReservation.objects.filter(
            document_type="payment_request"
        ).count(),
        "workflows": WorkflowInstance.objects.filter(
            document_type="payment_request"
        ).count(),
        "tasks": ApprovalTask.objects.filter(
            workflow_instance__document_type="payment_request"
        ).count(),
        "decisions": ApprovalDecision.objects.filter(
            task__workflow_instance__document_type="payment_request"
        ).count(),
    }


class Command(BaseCommand):
    help = "Exercise one V48 injected failure against an isolated regression database clone"

    def add_arguments(self, parser):
        parser.add_argument("--action", choices=FAILURE_STEPS, required=True)
        parser.add_argument("--step", required=True)

    def handle(self, *args, **options):
        action = options["action"]
        step = options["step"]
        if step not in FAILURE_STEPS[action]:
            raise CommandError(f"unsupported failure step: {action}/{step}")
        database_name = str(connection.settings_dict["NAME"]).lower()
        if "regression" not in database_name and "fault" not in database_name:
            raise CommandError("failure injection is only allowed on a regression/fault clone")

        action_codes = [
            "GENERATE_PAYMENT_REQUEST",
            "SUBMIT_PAYMENT_REQUEST",
            "APPROVE_PAYMENT_REQUEST",
            "REJECT_PAYMENT_REQUEST",
        ]
        PaymentRequestSourceRelation.objects.all().delete()
        PaymentRequestSubmissionSnapshot.objects.all().delete()
        PaymentRequestSourceSnapshot.objects.all().delete()
        PaymentRequestWorkflowRelation.objects.all().delete()
        PaymentRequest.objects.all().delete()
        ApprovalDecision.objects.filter(
            task__workflow_instance__document_type="payment_request"
        ).delete()
        ApprovalTask.objects.filter(
            workflow_instance__document_type="payment_request"
        ).delete()
        WorkflowInstance.objects.filter(document_type="payment_request").delete()
        BusinessActionIdempotency.objects.filter(action_code__in=action_codes).delete()
        BusinessActionAuditRecord.objects.filter(action_code__in=action_codes).delete()
        BusinessActionTransaction.objects.filter(action_code__in=action_codes).delete()
        BusinessDocumentNumberReservation.objects.filter(document_type="payment_request").delete()
        BusinessActionSourceLock.objects.filter(lock_key__startswith="payment_request").delete()

        source_index = 2 if action == "reject" or step == "next_task" else 1
        source = PaymentRequestPrepare.objects.filter(
            prepare_no=f"PRP2026070000000{source_index}"
        ).first()
        if not source:
            raise CommandError("V47 source missing in regression clone")
        applicant = ensure_user(f"pce-v48-fault-applicant-{source_index}", source.company_id)
        _, route_steps = ensure_policy(source, source_index)
        approvers = []
        for route_step in route_steps:
            actor = ensure_user(
                f"pce-v48-fault-approver-l{route_step['stepNo']}-{source_index}",
                source.company_id,
            )
            ensure_role(actor, route_step["roleCode"], source.legal_entity_id)
            approvers.append(actor)

        request = None
        if action != "generate":
            request = PaymentRequest.objects.filter(
                source_payment_request_prepare=source
            ).first()
            if not request:
                outcome = generate_payment_request(
                    user=applicant,
                    source=source,
                    idempotency_key=f"fault-setup-generate-{action}-{step}",
                    expected_source_version=source.version,
                    explicit_user_action=True,
                )
                request = PaymentRequest.objects.get(pk=outcome["data"]["id"])
        if action in {"approve", "reject"} and request.status == "draft":
            submit_payment_request(
                user=applicant,
                obj=request,
                idempotency_key=f"fault-setup-submit-{action}-{step}",
                expected_version=request.version,
                expected_source_prepare_version=source.version,
                expected_payment_data_version=source.current_payment_data_version,
                expected_source_validation_version=source.current_validation_version,
                explicit_user_action=True,
                application_reason="V48 failure matrix setup",
            )
            request.refresh_from_db()

        before = counts()
        key = f"fault-{action}-{step}"
        try:
            if action == "generate":
                generate_payment_request(
                    user=applicant,
                    source=source,
                    idempotency_key=key,
                    expected_source_version=source.version,
                    explicit_user_action=True,
                    failure_step=step,
                )
            elif action == "submit":
                submit_payment_request(
                    user=applicant,
                    obj=request,
                    idempotency_key=key,
                    expected_version=request.version,
                    expected_source_prepare_version=source.version,
                    expected_payment_data_version=source.current_payment_data_version,
                    expected_source_validation_version=source.current_validation_version,
                    explicit_user_action=True,
                    application_reason="V48 failure matrix",
                    failure_step=step,
                )
            else:
                task = request.workflow_instance.tasks.get(status="pending")
                actor = approvers[task.step_no - 1]
                decide_payment_request(
                    user=actor,
                    obj=request,
                    task=task,
                    decision="approved" if action == "approve" else "rejected",
                    idempotency_key=key,
                    expected_payment_request_version=request.version,
                    expected_workflow_version=request.workflow_instance.version,
                    expected_task_version=task.version,
                    explicit_user_action=True,
                    decision_comment="V48 failure matrix",
                    failure_step=step,
                )
        except ReconciliationError as error:
            if error.code != "PAYREQ_INJECTED_FAILURE":
                raise
        else:
            raise CommandError(f"injected failure did not fire: {action}/{step}")

        after = counts()
        committed_recovery = step == "response_lost"
        passed = after != before if committed_recovery else after == before
        if not passed:
            raise CommandError(
                f"failure residue mismatch: {action}/{step}: before={before}, after={after}"
            )
        self.stdout.write(json.dumps({
            "result": "passed",
            "action": action,
            "step": step,
            "expected": "committed_recovery" if committed_recovery else "zero_residue",
            "before": before,
            "after": after,
            "regressionCloneOnly": True,
        }, ensure_ascii=False))
