import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from bank_send_preparation.models import BankSendPreparation
from bank_send_preparation.repositories import BankSendPreparationRepository
from bank_send_preparation.services import serialize_preparation
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionSourceLock,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
    BusinessDocumentNumberSequence,
    PurchaseReconciliation,
)
from reconciliation.services import ReconciliationError, canonical_hash
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.facts import (
    BankSendTaskFactError,
    BankSendTaskFacts,
    business_state_transition_facts,
)
from workflow_runtime.fact_loads import build_fact_load_facts
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)
from workflow_runtime.write_intents import (
    build_bank_send_task_write_intent_facts,
)

from .models import BankSendTask
from .repositories import BankSendTaskRepository


VERSION = "V1.14.2.8.4.7.59.1.1"
CANONICAL_NAME = "银行发送任务"
MODULE_CODE = "bank-send-task"
SOURCE_DOCUMENT_TYPE = "bankSendPreparation"
CREATE_ACTION = "create-bank-send-task"
QUEUE_ACTION = "queue-bank-send-task"
READY_ACTION = "mark-bank-send-task-ready"
OBJECT_TYPE = "bank_send_task"
NUMBER_POLICY_VERSION = "bank-send-task-sequence-v1"
ALLOWED_STATE_TRANSITIONS = (
    (BankSendTask.Status.PREPARED, BankSendTask.Status.QUEUED),
    (BankSendTask.Status.QUEUED, BankSendTask.Status.READY_TO_SEND),
)
EXPECTED_TRANSITIONS = {
    BankSendTask.Status.PREPARED: (),
    BankSendTask.Status.QUEUED: (
        (BankSendTask.Status.PREPARED, BankSendTask.Status.QUEUED, QUEUE_ACTION),
    ),
    BankSendTask.Status.READY_TO_SEND: (
        (BankSendTask.Status.PREPARED, BankSendTask.Status.QUEUED, QUEUE_ACTION),
        (
            BankSendTask.Status.QUEUED,
            BankSendTask.Status.READY_TO_SEND,
            READY_ACTION,
        ),
    ),
}
STATUS_LABELS = {
    BankSendTask.Status.PREPARED: "已准备",
    BankSendTask.Status.QUEUED: "已进入发送队列",
    BankSendTask.Status.READY_TO_SEND: "发送前就绪",
}


def bank_send_task_status_label(status_code):
    try:
        return STATUS_LABELS[status_code]
    except KeyError as exc:
        raise BankSendTaskFactError(
            f"unsupported bank-send task status: {status_code}"
        ) from exc


def downstream_counts():
    return {
        "bankMessages": 0,
        "paymentExecutions": 0,
        "fundsDebits": 0,
        "bankTransactions": 0,
        "paymentVouchers": 0,
        "writeoffs": 0,
        "ledgerEntries": 0,
        "postings": 0,
    }


def _reconciliation_for_preparation(preparation):
    reconciliation_id = (
        preparation.source_formal_payment_order
        .source_risk_review.source_payment_order_draft.source_reconciliation_id
    )
    return PurchaseReconciliation.objects.get(pk=reconciliation_id)


def _assert_feature_enabled(preparation):
    if not getattr(settings, "PCE_BANK_SEND_TASK_FEATURE_ENABLED", False):
        raise ReconciliationError(
            "BST_FEATURE_DISABLED",
            "Bank send task is disabled",
            403,
        )
    trusted_tenants = getattr(
        settings,
        "PCE_BANK_SEND_TASK_TEST_TENANTS",
        set(),
    )
    if (
        preparation.tenant_id not in trusted_tenants
        and not getattr(
            settings,
            "PCE_BANK_SEND_TASK_PRODUCTION_ROLLOUT_ENABLED",
            False,
        )
    ):
        raise ReconciliationError(
            "BST_PRODUCTION_DISABLED",
            "Bank send task is limited to trusted test tenants",
            403,
        )


def evaluate_task_creation_gate(preparation):
    serialized = serialize_preparation(preparation)
    order = preparation.source_formal_payment_order
    approval = getattr(order, "approval", None)
    preview = getattr(preparation, "message_preview", None)
    send_gate = getattr(preparation, "send_gate", None)
    write_facts = serialized["writeIntentFacts"]
    checks = {
        "bankSendGatePassed": bool(
            send_gate and send_gate.eligible is True
        ),
        "formalPaymentOrderFrozen": order.status == "frozen_for_execution",
        "formalPaymentOrderFreezeConsistent": bool(
            send_gate
            and send_gate.freeze_hash_passed is True
            and send_gate.source_freeze_hash == preparation.source_freeze_hash
            and send_gate.current_freeze_hash == preparation.source_freeze_hash
        ),
        "approvalApproved": bool(
            send_gate
            and send_gate.approval_passed is True
            and approval
            and approval.approval_status == "approved"
        ),
        "riskReviewPassed": bool(
            send_gate and send_gate.risk_review_passed is True
        ),
        "fundsAvailable": bool(
            send_gate and send_gate.funds_available is True
        ),
        "segregationOfDutiesPassed": bool(
            send_gate and send_gate.segregation_valid is True
        ),
        "bankSendPreparationPrepared":
            preparation.status == BankSendPreparation.Status.PREPARED,
        "bankMessagePreviewExists": bool(
            preview
            and preview.status == "preview_only"
            and preview.sanitized_payload.get("sent") is False
            and preview.sanitized_payload.get("executed") is False
        ),
        "forbiddenBusinessProgressWriteCountZero":
            write_facts["forbiddenBusinessProgressWriteCount"] == 0,
    }
    reason_codes = {
        "bankSendGatePassed": "BANK_SEND_GATE_NOT_PASSED",
        "formalPaymentOrderFrozen": "FORMAL_PAYMENT_ORDER_NOT_FROZEN",
        "formalPaymentOrderFreezeConsistent":
            "FORMAL_PAYMENT_ORDER_FREEZE_INCONSISTENT",
        "approvalApproved": "APPROVAL_NOT_APPROVED",
        "riskReviewPassed": "RISK_REVIEW_NOT_PASSED",
        "fundsAvailable": "FUNDS_NOT_AVAILABLE",
        "segregationOfDutiesPassed": "SEGREGATION_OF_DUTIES_NOT_PASSED",
        "bankSendPreparationPrepared": "BANK_SEND_PREPARATION_NOT_PREPARED",
        "bankMessagePreviewExists": "BANK_MESSAGE_PREVIEW_MISSING",
        "forbiddenBusinessProgressWriteCountZero":
            "FORBIDDEN_BUSINESS_PROGRESS_WRITE_FOUND",
    }
    blocking_reasons = [
        reason_codes[key] for key, passed in checks.items() if not passed
    ]
    snapshot = {
        **checks,
        "eligible": not blocking_reasons,
        "blockingReasons": blocking_reasons,
        "formalPaymentOrderNo": order.order_no,
        "formalPaymentOrderVersion": order.version,
        "bankSendPreparationNo": preparation.prepare_no,
        "bankSendPreparationVersion": preparation.version,
        "bankMessagePreviewNo": preview.preview_no if preview else "",
        "bankMessagePreviewHash": preview.payload_hash if preview else "",
        "forbiddenBusinessProgressWriteCount":
            write_facts["forbiddenBusinessProgressWriteCount"],
        "serverDerived": True,
        "currentStateSource": "server",
    }
    return {
        **snapshot,
        "validationHash": canonical_hash(snapshot),
    }


def _batch_id_for_preparation(preparation):
    batch_id = str(
        getattr(settings, "PCE_BANK_SEND_TASK_BATCH_ID", "")
        or getattr(settings, "PCE_CANARY_BATCH_ID", "")
    ).strip()
    if not batch_id:
        raise ReconciliationError(
            "BST_BATCH_ID_REQUIRED",
            "Bank send task batch id is required",
            409,
        )
    return batch_id


def _reserve_number(preparation, idempotency_key):
    period = preparation.planned_execution_date.strftime("%Y-%m")
    scope = f"BST:{preparation.tenant_id}:{period}"
    sequence, _ = (
        BusinessDocumentNumberSequence.objects.select_for_update()
        .get_or_create(number_scope=scope, defaults={"current_value": 0})
    )
    sequence.current_value += 1
    sequence.save(update_fields=["current_value", "updated_at"])
    number = (
        f"BST{preparation.planned_execution_date.strftime('%Y%m')}"
        f"{sequence.current_value:08d}"
    )
    return BusinessDocumentNumberReservation.objects.create(
        document_type="bankSendTask",
        number_policy_version=NUMBER_POLICY_VERSION,
        number_scope=scope,
        legal_entity_id=preparation.legal_entity_id,
        ledger_book_id="",
        reserved_number=number,
        tenant_id=preparation.tenant_id,
        accounting_period=period,
        idempotency_key=idempotency_key,
        status=BusinessDocumentNumberReservation.Status.RESERVED,
    )


def _create_transaction(preparation, idempotency_key, request_hash):
    return BusinessActionTransaction.objects.create(
        transaction_id=f"BST-TX-{uuid.uuid4().hex.upper()}",
        action_code=CREATE_ACTION,
        idempotency_key=idempotency_key,
        tenant_id=preparation.tenant_id,
        source_key=f"bankSendPreparation:{preparation.pk}",
        command_id=f"BST-CMD-{uuid.uuid4().hex.upper()}",
        transaction_plan_id="bank-send-task-creation-v1",
        review_id=preparation.prepare_no,
        review_hash=request_hash,
        status=BusinessActionTransaction.Status.IN_PROGRESS,
        outcome="pending",
        commit_status="not_committed",
        recovery_status="not_required",
        reconciliation=_reconciliation_for_preparation(preparation),
    )


def _create_audit(
    *,
    transaction_row,
    action_code,
    idempotency_key,
    actor,
    preparation,
    task,
    evidence,
):
    return BusinessActionAuditRecord.objects.create(
        transaction=transaction_row,
        action_code=action_code,
        tenant_id=preparation.tenant_id,
        actor=actor,
        source_key=f"bankSendPreparation:{preparation.pk}",
        reconciliation=transaction_row.reconciliation,
        result="committed",
        target_type="bankSendTask",
        target_id=task.pk,
        target_no=task.task_no,
        review_id=preparation.prepare_no,
        review_hash=transaction_row.review_hash,
        command_id=transaction_row.command_id,
        idempotency_key=idempotency_key,
        actor_name=actor.get_username(),
        tenant_or_scope=f"{preparation.tenant_id}:{preparation.legal_entity_id}",
        evidence_hash=canonical_hash(evidence),
        evidence=evidence,
    )


def _existing_result(task):
    return {
        "classification": "existing_result",
        "created": False,
        "data": serialize_task(task),
    }


def create_bank_send_task(
    *,
    user,
    preparation,
    idempotency_key,
    expected_source_version,
    explicit_user_action,
):
    if explicit_user_action is not True:
        raise ReconciliationError(
            "BST_EXPLICIT_ACTION_REQUIRED",
            "Explicit user action is required",
            400,
        )
    if not idempotency_key:
        raise ReconciliationError(
            "BST_IDEMPOTENCY_KEY_REQUIRED",
            "Idempotency key is required",
            400,
        )
    _assert_feature_enabled(preparation)
    decision = ActionPermissionValidator().evaluate(
        user=user,
        module_code=MODULE_CODE,
        action_code=CREATE_ACTION,
        object_ids=[preparation.pk],
        selection_count=1,
    )
    if not decision["granted"]:
        raise ReconciliationError(
            "BST_PERMISSION_DENIED",
            decision["reason"],
            403,
        )
    existing = BankSendTaskRepository().by_source(preparation.pk)
    if existing:
        return _existing_result(existing)
    gate = evaluate_task_creation_gate(preparation)
    if not gate["eligible"]:
        raise ReconciliationError(
            "BST_GATE_BLOCKED",
            ",".join(gate["blockingReasons"]),
            409,
        )
    request_hash = canonical_hash(
        {
            "action": CREATE_ACTION,
            "sourcePreparationId": preparation.pk,
            "sourcePreparationVersion": expected_source_version,
            "messagePreviewHash": gate["bankMessagePreviewHash"],
            "validationHash": gate["validationHash"],
        }
    )
    prior = BusinessActionIdempotency.objects.filter(
        action_code=CREATE_ACTION,
        idempotency_key=idempotency_key,
    ).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ReconciliationError(
                "BST_IDEMPOTENCY_CONFLICT",
                "Idempotency payload conflict",
                409,
            )
        target = (
            BankSendTaskRepository().get(prior.target_id)
            if prior.target_id
            else None
        )
        if target:
            return _existing_result(target)
        raise ReconciliationError(
            "BST_ACTION_IN_PROGRESS",
            "Bank send task creation is in progress",
            409,
            True,
        )
    try:
        with transaction.atomic():
            current = (
                BankSendPreparationRepository()
                .queryset()
                .select_for_update()
                .get(pk=preparation.pk)
            )
            existing = BankSendTaskRepository().by_source(current.pk)
            if existing:
                return _existing_result(existing)
            if current.version != expected_source_version:
                raise ReconciliationError(
                    "BST_VERSION_CONFLICT",
                    "Bank send preparation version conflict",
                    409,
                )
            fresh_gate = evaluate_task_creation_gate(current)
            if (
                not fresh_gate["eligible"]
                or fresh_gate["validationHash"] != gate["validationHash"]
            ):
                raise ReconciliationError(
                    "BST_GATE_CHANGED",
                    "Bank send task gate changed during transaction",
                    409,
                )
            idempotency = BusinessActionIdempotency.objects.create(
                action_code=CREATE_ACTION,
                idempotency_key=idempotency_key,
                tenant_id=current.tenant_id,
                source_key=f"bankSendPreparation:{current.pk}",
                request_hash=request_hash,
                status=BusinessActionIdempotency.Status.IN_PROGRESS,
            )
            transaction_row = _create_transaction(
                current,
                idempotency_key,
                request_hash,
            )
            lock, lock_created = (
                BusinessActionSourceLock.objects.select_for_update()
                .get_or_create(
                    lock_key=f"bankSendPreparation:{current.pk}",
                    defaults={
                        "owner_transaction_id":
                            transaction_row.transaction_id,
                        "state": "active",
                    },
                )
            )
            if not lock_created and lock.state == "active":
                raise ReconciliationError(
                    "BST_SOURCE_LOCKED",
                    "Bank send preparation is locked",
                    409,
                    True,
                )
            lock.owner_transaction_id = transaction_row.transaction_id
            lock.state = "active"
            lock.released_at = None
            lock.save(
                update_fields=[
                    "owner_transaction_id",
                    "state",
                    "released_at",
                    "acquired_at",
                ]
            )
            reservation = _reserve_number(current, idempotency_key)
            preview = current.message_preview
            task = create_business_object_with_initial_state(
                model=BankSendTask,
                initial_state=BankSendTask.Status.PREPARED,
                task_no=reservation.reserved_number,
                source_document_type=SOURCE_DOCUMENT_TYPE,
                source_preparation=current,
                source_preparation_no=current.prepare_no,
                source_preparation_version=current.version,
                source_formal_payment_order_no=(
                    current.source_formal_payment_order_no
                ),
                message_preview=preview,
                message_preview_no=preview.preview_no,
                message_preview_hash=preview.payload_hash,
                tenant_id=current.tenant_id,
                batch_id=_batch_id_for_preparation(current),
                company_id=current.company_id,
                legal_entity_id=current.legal_entity_id,
                supplier_id=current.supplier_id,
                supplier_name=current.supplier_name,
                currency=current.currency,
                amount=current.amount,
                planned_execution_date=current.planned_execution_date,
                validation_snapshot=fresh_gate,
                validation_hash=fresh_gate["validationHash"],
                idempotency_key=idempotency_key,
                number_reservation=reservation,
                business_transaction=transaction_row,
                created_by=user,
            )
            creation_audit = _create_audit(
                transaction_row=transaction_row,
                action_code=CREATE_ACTION,
                idempotency_key=idempotency_key,
                actor=user,
                preparation=current,
                task=task,
                evidence={
                    "version": VERSION,
                    "status": "prepared",
                    "validationHash": fresh_gate["validationHash"],
                    "bankSendExecutionWrite": False,
                },
            )
            task.audit_record = creation_audit
            task.save(update_fields=["audit_record", "updated_at"])
            queue_audit = _create_audit(
                transaction_row=transaction_row,
                action_code=QUEUE_ACTION,
                idempotency_key=f"{idempotency_key}:queue",
                actor=user,
                preparation=current,
                task=task,
                evidence={
                    "version": VERSION,
                    "stateTransition": "prepared->queued",
                    "externalSend": False,
                },
            )
            transition_business_object(
                business_object=task,
                object_type=OBJECT_TYPE,
                source_state=BankSendTask.Status.PREPARED,
                target_state=BankSendTask.Status.QUEUED,
                action_code=QUEUE_ACTION,
                operator=user,
                reason="bank_send_task_queued_without_external_send",
                audit_reference=f"BusinessActionAuditRecord:{queue_audit.pk}",
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
            ready_audit = _create_audit(
                transaction_row=transaction_row,
                action_code=READY_ACTION,
                idempotency_key=f"{idempotency_key}:ready",
                actor=user,
                preparation=current,
                task=task,
                evidence={
                    "version": VERSION,
                    "stateTransition": "queued->ready_to_send",
                    "externalSend": False,
                },
            )
            transition_business_object(
                business_object=task,
                object_type=OBJECT_TYPE,
                source_state=BankSendTask.Status.QUEUED,
                target_state=BankSendTask.Status.READY_TO_SEND,
                action_code=READY_ACTION,
                operator=user,
                reason="bank_send_task_ready_but_not_sent",
                audit_reference=f"BusinessActionAuditRecord:{ready_audit.pk}",
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
            now = timezone.now()
            reservation.status = (
                BusinessDocumentNumberReservation.Status.CONSUMED
            )
            reservation.consumed_at = now
            reservation.save(update_fields=["status", "consumed_at"])
            result_hash = canonical_hash(
                {
                    "taskId": task.pk,
                    "taskNo": task.task_no,
                    "status": task.status,
                    "sourcePreparationNo": current.prepare_no,
                }
            )
            transaction_row.status = (
                BusinessActionTransaction.Status.COMMITTED
            )
            transaction_row.outcome = "ready_to_send"
            transaction_row.commit_status = "committed"
            transaction_row.result_hash = result_hash
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
            idempotency.target_type = "bankSendTask"
            idempotency.target_id = task.pk
            idempotency.target_no = task.task_no
            idempotency.transaction_id = transaction_row.transaction_id
            idempotency.result_reference = f"bankSendTask:{task.pk}"
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
            lock.state = "released"
            lock.released_at = now
            lock.save(
                update_fields=["state", "released_at", "acquired_at"]
            )
        return {
            "classification": "created",
            "created": True,
            "data": serialize_task(
                BankSendTaskRepository().get(task.pk)
            ),
        }
    except IntegrityError:
        existing = BankSendTaskRepository().by_source(preparation.pk)
        if existing:
            return _existing_result(existing)
        raise


def serialize_task(task):
    status_label = bank_send_task_status_label(task.status)
    transition_facts = business_state_transition_facts(
        business_object=task,
        object_type=OBJECT_TYPE,
        expected_transitions=EXPECTED_TRANSITIONS,
        audit_target_type="bankSendTask",
    )
    state_transition_guard = bank_send_task_state_transition_guard(
        task,
        transition_facts=transition_facts,
    )
    if not state_transition_guard["passed"]:
        raise BankSendTaskFactError(
            "bank-send task state transition guard failed"
        )
    audit_write_count = (
        (1 if task.audit_record_id else 0)
        + transition_facts["statusTransitionCount"]
    )
    write_intent_facts = build_bank_send_task_write_intent_facts(
        send_task_preparation_write_count=1,
        audit_write_count=audit_write_count,
        bank_send_execution_counts=downstream_counts(),
    )
    return {
        "id": task.pk,
        "taskNo": task.task_no,
        "sourceDocumentType": task.source_document_type,
        "sourcePreparationId": task.source_preparation_id,
        "sourcePreparationNo": task.source_preparation_no,
        "sourcePreparationVersion": task.source_preparation_version,
        "sourceFormalPaymentOrderNo": task.source_formal_payment_order_no,
        "messagePreview": {
            "id": task.message_preview_id,
            "previewNo": task.message_preview_no,
            "payloadHash": task.message_preview_hash,
            "status": task.message_preview.status,
            "readonly": True,
            "sent": False,
        },
        "tenantId": task.tenant_id,
        "batchId": task.batch_id,
        "companyId": task.company_id,
        "legalEntityId": task.legal_entity_id,
        "supplierId": task.supplier_id,
        "supplierName": task.supplier_name,
        "currency": task.currency,
        "amount": str(task.amount),
        "plannedExecutionDate": task.planned_execution_date.isoformat(),
        "status": task.status,
        "statusCode": task.status,
        "statusLabel": status_label,
        "version": task.version,
        **transition_facts,
        "stateTransitionGuard": state_transition_guard,
        "validationSnapshot": dict(task.validation_snapshot),
        "validationHash": task.validation_hash,
        "idempotencyStatus": "committed",
        "numberReservationStatus": task.number_reservation.status,
        "transactionStatus": task.business_transaction.status,
        "auditStatus": "committed" if task.audit_record_id else "missing",
        "writeIntentFacts": write_intent_facts,
        "downstreamCounts": downstream_counts(),
        "businessActions": {
            "canViewTask": True,
            "canViewTaskStatus": True,
            "canViewMessageBinding": True,
            "canCreateTask": False,
            "canSendBank": False,
            "canExecutePayment": False,
        },
        "bankSendExecuted": False,
        "paymentExecuted": False,
        "currentStateSource": "server",
    }


def bank_send_task_state_transition_guard(
    task,
    *,
    transition_facts=None,
):
    facts = transition_facts or business_state_transition_facts(
        business_object=task,
        object_type=OBJECT_TYPE,
        expected_transitions=EXPECTED_TRANSITIONS,
        audit_target_type="bankSendTask",
    )
    history = facts["statusTransitionHistory"]
    allowed = set(ALLOWED_STATE_TRANSITIONS)
    checks = {
        "unifiedStateService": all(
            row["objectType"] == OBJECT_TYPE
            and row["actionCode"] in {QUEUE_ACTION, READY_ACTION}
            for row in history
        ),
        "noSkippedState": all(
            (row["sourceState"], row["targetState"]) in allowed
            for row in history
        ),
        "historyLengthMatchesCount":
            len(history) == facts["statusTransitionCount"],
        "auditReferenceComplete": all(
            bool(row["auditReference"])
            and row["auditReference"].startswith(
                "BusinessActionAuditRecord:"
            )
            for row in history
        ),
        "stateMachineConsistent": facts["stateMachineConsistent"] is True,
    }
    return {
        "guardCode": "bank_send_task_state_transition_guard",
        **checks,
        "passed": all(checks.values()),
    }


def bank_send_task_facts_for_rows(
    *,
    sources,
    rows,
    canary_pool_facts,
    api_url="/api/finance/bank-send-tasks/",
    tenant_id=None,
    batch_id=None,
    request=None,
):
    facts = BankSendTaskFacts.from_serialized_rows(
        serialized_sources=sources,
        serialized_rows=rows,
        bank_send_execution_counts=downstream_counts(),
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
            "createdTaskCount",
            "blockedTaskCount",
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
    "CANONICAL_NAME",
    "CREATE_ACTION",
    "MODULE_CODE",
    "SOURCE_DOCUMENT_TYPE",
    "VERSION",
    "bank_send_task_facts_for_rows",
    "bank_send_task_status_label",
    "bank_send_task_state_transition_guard",
    "create_bank_send_task",
    "downstream_counts",
    "evaluate_task_creation_gate",
    "serialize_task",
]
