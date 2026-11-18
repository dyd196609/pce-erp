import uuid

from django.conf import settings
from django.db import IntegrityError, transaction

from bank_send_task.models import BankSendTask
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionTransaction,
    PurchaseReconciliation,
)
from reconciliation.services import ReconciliationError, canonical_hash
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.fact_loads import build_fact_load_facts
from workflow_runtime.facts import (
    BankSendExecutionGateFacts,
    business_state_transition_facts,
)
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)
from workflow_runtime.write_intents import (
    build_bank_send_execution_gate_write_intent_facts,
)

from .models import BankSendExecutionGate
from .repositories import BankSendExecutionGateRepository


VERSION = "V1.14.2.8.4.7.60"
CANONICAL_NAME = "银行发送执行授权"
MODULE_CODE = "bank-send-execution-gate"
OBJECT_TYPE = "bank_send_execution_gate"
CREATE_ACTION = "submit-bank-send-final-authorization-review"
APPROVE_ACTION = "approve-bank-send-final-authorization"
READY_ACTION = "mark-bank-send-execution-gate-ready"
ALLOWED_STATE_TRANSITIONS = (
    (
        BankSendExecutionGate.Status.PENDING_REVIEW,
        BankSendExecutionGate.Status.APPROVED,
    ),
    (
        BankSendExecutionGate.Status.APPROVED,
        BankSendExecutionGate.Status.READY_FOR_EXECUTION,
    ),
)
EXPECTED_TRANSITIONS = {
    BankSendExecutionGate.Status.PENDING_REVIEW: (),
    BankSendExecutionGate.Status.APPROVED: (
        (
            BankSendExecutionGate.Status.PENDING_REVIEW,
            BankSendExecutionGate.Status.APPROVED,
            APPROVE_ACTION,
        ),
    ),
    BankSendExecutionGate.Status.READY_FOR_EXECUTION: (
        (
            BankSendExecutionGate.Status.PENDING_REVIEW,
            BankSendExecutionGate.Status.APPROVED,
            APPROVE_ACTION,
        ),
        (
            BankSendExecutionGate.Status.APPROVED,
            BankSendExecutionGate.Status.READY_FOR_EXECUTION,
            READY_ACTION,
        ),
    ),
}
STATUS_LABELS = {
    "pending_review": "待最终授权审核",
    "approved": "授权审核通过",
    "ready_for_execution": "执行前就绪",
}


def downstream_counts():
    return {
        "bankMessages": 0,
        "paymentExecutions": 0,
        "fundsDebits": 0,
        "bankTransactions": 0,
        "paymentVouchers": 0,
        "ledgerEntries": 0,
        "postings": 0,
    }


def _reconciliation_for_task(task):
    reconciliation_id = (
        task.source_preparation.source_formal_payment_order
        .source_risk_review.source_payment_order_draft.source_reconciliation_id
    )
    return PurchaseReconciliation.objects.get(pk=reconciliation_id)


def evaluate_execution_authorization(task):
    preparation = task.source_preparation
    order = preparation.source_formal_payment_order
    send_gate = preparation.send_gate
    preview = task.message_preview
    checks = {
        "bankSendTaskReadyToSend":
            task.status == BankSendTask.Status.READY_TO_SEND,
        "formalPaymentOrderFreezeConsistent": bool(
            order.status == "frozen_for_execution"
            and send_gate.freeze_hash_passed is True
            and send_gate.source_freeze_hash
            == send_gate.current_freeze_hash
            == preparation.source_freeze_hash
        ),
        "approvalApproved": send_gate.approval_passed is True,
        "riskReviewPassed": send_gate.risk_review_passed is True,
        "fundsAvailable": send_gate.funds_available is True,
        "segregationOfDutiesPassed":
            send_gate.segregation_valid is True,
        "bankInterfaceAvailable":
            send_gate.bank_interface_available is True,
        "messagePreviewHashConsistent": bool(
            preview.status == "preview_only"
            and preview.payload_hash == task.message_preview_hash
            and preview.preview_no == task.message_preview_no
        ),
        "bankSendTaskNotSent": bool(
            preview.sanitized_payload.get("sent") is False
            and task.status != "sent"
        ),
        "bankTransactionAbsent":
            downstream_counts()["bankTransactions"] == 0,
    }
    reason_codes = {
        "bankSendTaskReadyToSend": "BANK_SEND_TASK_NOT_READY",
        "formalPaymentOrderFreezeConsistent":
            "FORMAL_PAYMENT_ORDER_FREEZE_INCONSISTENT",
        "approvalApproved": "APPROVAL_NOT_APPROVED",
        "riskReviewPassed": "RISK_REVIEW_NOT_PASSED",
        "fundsAvailable": "FUNDS_NOT_AVAILABLE",
        "segregationOfDutiesPassed":
            "SEGREGATION_OF_DUTIES_NOT_PASSED",
        "bankInterfaceAvailable": "BANK_INTERFACE_NOT_AVAILABLE",
        "messagePreviewHashConsistent":
            "MESSAGE_PREVIEW_HASH_MISMATCH",
        "bankSendTaskNotSent": "BANK_SEND_TASK_ALREADY_SENT",
        "bankTransactionAbsent": "BANK_TRANSACTION_ALREADY_EXISTS",
    }
    blocking = [
        reason_codes[key] for key, passed in checks.items() if not passed
    ]
    snapshot = {
        **checks,
        "eligible": not blocking,
        "blockingReasons": blocking,
        "bankSendTaskNo": task.task_no,
        "formalPaymentOrderNo": task.source_formal_payment_order_no,
        "messagePreviewNo": task.message_preview_no,
        "messagePreviewHash": task.message_preview_hash,
        "serverDerived": True,
        "currentStateSource": "server",
    }
    return {
        **snapshot,
        "authorizationHash": canonical_hash(snapshot),
    }


def _assert_feature_enabled(task):
    if not getattr(
        settings,
        "PCE_BANK_SEND_EXECUTION_GATE_FEATURE_ENABLED",
        False,
    ):
        raise ReconciliationError(
            "BSEG_FEATURE_DISABLED",
            "Bank send execution gate is disabled",
            403,
        )
    trusted = getattr(
        settings,
        "PCE_BANK_SEND_EXECUTION_GATE_TEST_TENANTS",
        set(),
    )
    if (
        task.tenant_id not in trusted
        and not getattr(
            settings,
            "PCE_BANK_SEND_EXECUTION_GATE_PRODUCTION_ROLLOUT_ENABLED",
            False,
        )
    ):
        raise ReconciliationError(
            "BSEG_PRODUCTION_DISABLED",
            "Final authorization is limited to isolated test tenants",
            403,
        )


def _create_transaction(task, key, request_hash):
    return BusinessActionTransaction.objects.create(
        transaction_id=f"BSEG-TX-{uuid.uuid4().hex.upper()}",
        action_code=CREATE_ACTION,
        idempotency_key=key,
        tenant_id=task.tenant_id,
        source_key=f"bankSendTask:{task.pk}",
        command_id=f"BSEG-CMD-{uuid.uuid4().hex.upper()}",
        transaction_plan_id="bank-send-final-authorization-v1",
        review_id=task.task_no,
        review_hash=request_hash,
        status=BusinessActionTransaction.Status.IN_PROGRESS,
        outcome="pending_review",
        commit_status="not_committed",
        recovery_status="not_required",
        reconciliation=_reconciliation_for_task(task),
    )


def _create_audit(*, transaction_row, action_code, key, actor, task, gate, evidence):
    return BusinessActionAuditRecord.objects.create(
        transaction=transaction_row,
        action_code=action_code,
        tenant_id=task.tenant_id,
        actor=actor,
        source_key=f"bankSendTask:{task.pk}",
        reconciliation=transaction_row.reconciliation,
        result="committed",
        target_type="bankSendExecutionGate",
        target_id=gate.pk,
        target_no=gate.gate_no,
        review_id=task.task_no,
        review_hash=transaction_row.review_hash,
        command_id=transaction_row.command_id,
        idempotency_key=key,
        actor_name=actor.get_username(),
        tenant_or_scope=f"{task.tenant_id}:{task.legal_entity_id}",
        evidence_hash=canonical_hash(evidence),
        evidence=evidence,
    )


def _existing_result(gate):
    return {
        "classification": "existing_result",
        "created": False,
        "data": serialize_gate(gate),
    }


def create_bank_send_execution_gate(
    *,
    user,
    task,
    idempotency_key,
    expected_source_version,
    explicit_user_action,
):
    if explicit_user_action is not True:
        raise ReconciliationError(
            "BSEG_EXPLICIT_ACTION_REQUIRED",
            "Explicit final authorization action is required",
            400,
        )
    if not str(idempotency_key or "").strip():
        raise ReconciliationError(
            "BSEG_IDEMPOTENCY_KEY_REQUIRED",
            "Idempotency key is required",
            400,
        )
    _assert_feature_enabled(task)
    decision = ActionPermissionValidator().evaluate(
        user=user,
        module_code=MODULE_CODE,
        action_code=CREATE_ACTION,
        object_ids=[task.pk],
        selection_count=1,
    )
    if not decision["granted"]:
        raise ReconciliationError(
            "BSEG_PERMISSION_DENIED",
            decision["reason"],
            403,
        )
    existing = BankSendExecutionGateRepository().by_source(task.pk)
    if existing:
        return _existing_result(existing)
    authorization = evaluate_execution_authorization(task)
    if not authorization["eligible"]:
        raise ReconciliationError(
            "BSEG_GATE_BLOCKED",
            ",".join(authorization["blockingReasons"]),
            409,
        )
    request_hash = canonical_hash(
        {
            "action": CREATE_ACTION,
            "taskId": task.pk,
            "taskVersion": expected_source_version,
            "authorizationHash": authorization["authorizationHash"],
        }
    )
    prior = BusinessActionIdempotency.objects.filter(
        action_code=CREATE_ACTION,
        idempotency_key=idempotency_key,
    ).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ReconciliationError(
                "BSEG_IDEMPOTENCY_CONFLICT",
                "Idempotency payload conflict",
                409,
            )
        target = (
            BankSendExecutionGateRepository().get(prior.target_id)
            if prior.target_id
            else None
        )
        if target:
            return _existing_result(target)
        raise ReconciliationError(
            "BSEG_ACTION_IN_PROGRESS",
            "Final authorization is in progress",
            409,
            True,
        )
    try:
        with transaction.atomic():
            current = (
                BankSendTask.objects.select_for_update()
                .select_related(
                    "source_preparation__source_formal_payment_order",
                    "source_preparation__source_formal_payment_order"
                    "__source_risk_review__source_payment_order_draft",
                    "source_preparation__send_gate",
                    "message_preview",
                )
                .get(pk=task.pk)
            )
            existing = BankSendExecutionGateRepository().by_source(
                current.pk
            )
            if existing:
                return _existing_result(existing)
            if current.version != expected_source_version:
                raise ReconciliationError(
                    "BSEG_VERSION_CONFLICT",
                    "Bank send task version conflict",
                    409,
                )
            fresh = evaluate_execution_authorization(current)
            if (
                not fresh["eligible"]
                or fresh["authorizationHash"]
                != authorization["authorizationHash"]
            ):
                raise ReconciliationError(
                    "BSEG_GATE_CHANGED",
                    "Final authorization facts changed",
                    409,
                )
            idempotency = BusinessActionIdempotency.objects.create(
                action_code=CREATE_ACTION,
                idempotency_key=idempotency_key,
                tenant_id=current.tenant_id,
                source_key=f"bankSendTask:{current.pk}",
                request_hash=request_hash,
                status=BusinessActionIdempotency.Status.IN_PROGRESS,
            )
            transaction_row = _create_transaction(
                current,
                idempotency_key,
                request_hash,
            )
            gate = create_business_object_with_initial_state(
                model=BankSendExecutionGate,
                initial_state=BankSendExecutionGate.Status.PENDING_REVIEW,
                gate_no=f"BSEG-{current.task_no}",
                tenant_id=current.tenant_id,
                batch_id=current.batch_id,
                source_task=current,
                bank_send_task_no=current.task_no,
                formal_payment_order_no=
                    current.source_formal_payment_order_no,
                company_id=current.company_id,
                legal_entity_id=current.legal_entity_id,
                authorization_snapshot=fresh,
                authorization_hash=fresh["authorizationHash"],
                idempotency_key=idempotency_key,
                business_transaction=transaction_row,
                created_by=user,
            )
            creation_audit = _create_audit(
                transaction_row=transaction_row,
                action_code=CREATE_ACTION,
                key=idempotency_key,
                actor=user,
                task=current,
                gate=gate,
                evidence={
                    "status": "pending_review",
                    "externalSend": False,
                },
            )
            gate.audit_record = creation_audit
            gate.save(update_fields=["audit_record", "updated_at"])
            approve_audit = _create_audit(
                transaction_row=transaction_row,
                action_code=APPROVE_ACTION,
                key=f"{idempotency_key}:approve",
                actor=user,
                task=current,
                gate=gate,
                evidence={
                    "transition": "pending_review->approved",
                    "externalSend": False,
                },
            )
            transition_business_object(
                business_object=gate,
                object_type=OBJECT_TYPE,
                source_state=BankSendExecutionGate.Status.PENDING_REVIEW,
                target_state=BankSendExecutionGate.Status.APPROVED,
                action_code=APPROVE_ACTION,
                operator=user,
                reason="final_bank_send_authorization_approved",
                audit_reference=
                    f"BusinessActionAuditRecord:{approve_audit.pk}",
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
            ready_audit = _create_audit(
                transaction_row=transaction_row,
                action_code=READY_ACTION,
                key=f"{idempotency_key}:ready",
                actor=user,
                task=current,
                gate=gate,
                evidence={
                    "transition": "approved->ready_for_execution",
                    "bankSendExecuted": False,
                },
            )
            transition_business_object(
                business_object=gate,
                object_type=OBJECT_TYPE,
                source_state=BankSendExecutionGate.Status.APPROVED,
                target_state=
                    BankSendExecutionGate.Status.READY_FOR_EXECUTION,
                action_code=READY_ACTION,
                operator=user,
                reason="authorization_ready_without_bank_send",
                audit_reference=
                    f"BusinessActionAuditRecord:{ready_audit.pk}",
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
            transaction_row.status = (
                BusinessActionTransaction.Status.COMMITTED
            )
            transaction_row.outcome = "ready_for_execution"
            transaction_row.commit_status = "committed"
            transaction_row.result_hash = canonical_hash(
                {"gateId": gate.pk, "status": gate.status}
            )
            transaction_row.save(
                update_fields=[
                    "status",
                    "outcome",
                    "commit_status",
                    "result_hash",
                    "updated_at",
                ]
            )
            idempotency.status = BusinessActionIdempotency.Status.COMMITTED
            idempotency.target_type = "bankSendExecutionGate"
            idempotency.target_id = gate.pk
            idempotency.target_no = gate.gate_no
            idempotency.transaction_id = transaction_row.transaction_id
            idempotency.result_reference = (
                f"bankSendExecutionGate:{gate.pk}"
            )
            idempotency.save(
                update_fields=[
                    "status",
                    "target_type",
                    "target_id",
                    "target_no",
                    "transaction_id",
                    "result_reference",
                    "updated_at",
                ]
            )
        return {
            "classification": "created",
            "created": True,
            "data": serialize_gate(
                BankSendExecutionGateRepository().get(gate.pk)
            ),
        }
    except IntegrityError:
        existing = BankSendExecutionGateRepository().by_source(task.pk)
        if existing:
            return _existing_result(existing)
        raise


def bank_send_execution_gate_state_guard(gate, *, transition_facts=None):
    facts = transition_facts or business_state_transition_facts(
        business_object=gate,
        object_type=OBJECT_TYPE,
        expected_transitions=EXPECTED_TRANSITIONS,
        audit_target_type="bankSendExecutionGate",
    )
    history = facts["statusTransitionHistory"]
    allowed = set(ALLOWED_STATE_TRANSITIONS)
    checks = {
        "unifiedStateService": all(
            row["objectType"] == OBJECT_TYPE
            and row["actionCode"] in {APPROVE_ACTION, READY_ACTION}
            for row in history
        ),
        "noSkippedState": all(
            (row["sourceState"], row["targetState"]) in allowed
            for row in history
        ),
        "historyLengthMatchesCount":
            len(history) == facts["statusTransitionCount"],
        "auditReferenceComplete": all(
            row["auditReference"].startswith(
                "BusinessActionAuditRecord:"
            )
            for row in history
        ),
        "stateMachineConsistent": facts["stateMachineConsistent"] is True,
    }
    return {
        "guardCode": "bank_send_execution_gate_state_guard",
        **checks,
        "passed": all(checks.values()),
    }


def serialize_gate(gate):
    transition_facts = business_state_transition_facts(
        business_object=gate,
        object_type=OBJECT_TYPE,
        expected_transitions=EXPECTED_TRANSITIONS,
        audit_target_type="bankSendExecutionGate",
    )
    guard = bank_send_execution_gate_state_guard(
        gate,
        transition_facts=transition_facts,
    )
    if not guard["passed"]:
        raise ValueError("bank send execution gate state guard failed")
    write_facts = build_bank_send_execution_gate_write_intent_facts(
        execution_gate_preparation_write_count=1,
        audit_write_count=1 + transition_facts["statusTransitionCount"],
        bank_send_execution_counts=downstream_counts(),
    )
    return {
        "id": gate.pk,
        "gateNo": gate.gate_no,
        "tenantId": gate.tenant_id,
        "batchId": gate.batch_id,
        "sourceTaskId": gate.source_task_id,
        "bankSendTaskNo": gate.bank_send_task_no,
        "formalPaymentOrderNo": gate.formal_payment_order_no,
        "legalEntityId": gate.legal_entity_id,
        "status": gate.status,
        "statusCode": gate.status,
        "statusLabel": STATUS_LABELS[gate.status],
        "version": gate.version,
        **transition_facts,
        "stateTransitionGuard": guard,
        "authorizationChecks": dict(gate.authorization_snapshot),
        "authorizationHash": gate.authorization_hash,
        "writeIntentFacts": write_facts,
        "downstreamCounts": downstream_counts(),
        "bankSendExecuted": False,
        "bankMessageSent": False,
        "paymentExecuted": False,
        "fundsDebited": False,
        "bankTransactionCreated": False,
        "currentStateSource": "server",
    }


def bank_send_execution_gate_facts_for_rows(
    *,
    rows,
    canary_pool_facts,
    api_url="/api/finance/bank-send-execution-gates/",
    tenant_id=None,
    batch_id=None,
    request=None,
):
    audit_count = sum(
        row["writeIntentFacts"]["auditWriteCount"] for row in rows
    )
    write_facts = build_bank_send_execution_gate_write_intent_facts(
        execution_gate_preparation_write_count=len(rows),
        audit_write_count=audit_count,
        bank_send_execution_counts=downstream_counts(),
    )
    facts = BankSendExecutionGateFacts.from_serialized_rows(
        serialized_rows=rows,
        write_intent_facts=write_facts,
    ).as_dict()
    fact_load_facts = build_fact_load_facts(
        fact_load_status="success",
        api_url=api_url,
        http_status=200,
        tenant_id=tenant_id,
        batch_id=batch_id,
        request=request,
    )
    canary_counts = {
        key: canary_pool_facts[key]
        for key in (
            "normalPoolCount",
            "blockedPoolCount",
            "reservePoolCount",
            "createdGateCount",
            "blockedGateCount",
            "availablePoolCount",
        )
    }
    return {
        **facts,
        **canary_counts,
        **fact_load_facts,
        "factLoadFacts": fact_load_facts,
    }


__all__ = [
    "ALLOWED_STATE_TRANSITIONS",
    "CANONICAL_NAME",
    "CREATE_ACTION",
    "MODULE_CODE",
    "OBJECT_TYPE",
    "STATUS_LABELS",
    "VERSION",
    "bank_send_execution_gate_facts_for_rows",
    "bank_send_execution_gate_state_guard",
    "create_bank_send_execution_gate",
    "downstream_counts",
    "evaluate_execution_authorization",
    "serialize_gate",
]
