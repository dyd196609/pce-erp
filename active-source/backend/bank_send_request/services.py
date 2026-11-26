import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max

from bank_send_execution_gate.models import BankSendExecutionGate
from bank_send_execution_gate.services import evaluate_execution_authorization
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    PurchaseReconciliation,
)
from reconciliation.services import ReconciliationError, canonical_hash
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.fact_loads import build_fact_load_facts
from workflow_runtime.facts import (
    BankSendRequestFacts,
    business_state_transition_facts,
)
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)
from workflow_runtime.write_intents import build_bank_send_request_write_intent_facts

from .models import BankSendPreDispatchValidation, BankSendRequest
from .repositories import BankSendRequestRepository


VERSION = "V1.14.2.8.4.7.61"
CANONICAL_NAME = "银行发送请求准备"
MODULE_CODE = "bank-send-request"
OBJECT_TYPE = "bank_send_request"
CREATE_ACTION = "create-bank-send-request"
VALIDATE_ACTION = "validate-bank-send-request"
READY_ACTION = "mark-bank-send-request-ready-to-dispatch"
RERUN_ACTION = "rerun-bank-send-pre-dispatch-validation"
ALLOWED_STATE_TRANSITIONS = (
    (BankSendRequest.Status.DRAFT, BankSendRequest.Status.VALIDATED),
    (BankSendRequest.Status.VALIDATED, BankSendRequest.Status.READY_TO_DISPATCH),
)
EXPECTED_TRANSITIONS = {
    BankSendRequest.Status.DRAFT: (),
    BankSendRequest.Status.VALIDATED: (
        ("draft", "validated", VALIDATE_ACTION),
    ),
    BankSendRequest.Status.READY_TO_DISPATCH: (
        ("draft", "validated", VALIDATE_ACTION),
        ("validated", "ready_to_dispatch", READY_ACTION),
    ),
}
STATUS_LABELS = {
    "draft": "草稿",
    "validated": "校验通过",
    "ready_to_dispatch": "发送前待分发",
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


def _source_parts(gate):
    task = gate.source_task
    preparation = task.source_preparation
    order = preparation.source_formal_payment_order
    freeze = order.execution_freeze
    return task, preparation, order, freeze


def evaluate_pre_dispatch_validation(gate, request_object=None):
    task, preparation, order, freeze = _source_parts(gate)
    authorization = evaluate_execution_authorization(task)
    baseline = request_object
    checks = {
        "authorizationGateStillValid":
            gate.status == BankSendExecutionGate.Status.READY_FOR_EXECUTION,
        "authorizationHashUnchanged": (
            authorization["eligible"] is True
            and authorization["authorizationHash"] == gate.authorization_hash
        ),
        "bankSendTaskUnchanged": (
            task.status == "ready_to_send"
            and (baseline is None or task.version == baseline.source_task_version)
        ),
        "formalPaymentOrderUnchanged": (
            order.status == "frozen_for_execution"
            and (baseline is None or order.version == baseline.source_order_version)
        ),
        "amountUnchanged": (
            str(task.amount) == str(order.amount) == str(preparation.amount)
            and (baseline is None or str(task.amount) == baseline.amount_snapshot)
        ),
        "beneficiaryAccountUnchanged": (
            bool(freeze.payee_account_id)
            and (
                baseline is None
                or freeze.payee_account_id == baseline.beneficiary_account_snapshot
            )
        ),
        "messagePreviewHashUnchanged": (
            task.message_preview.payload_hash == task.message_preview_hash
            and (
                baseline is None
                or task.message_preview_hash == baseline.message_preview_hash_snapshot
            )
        ),
        "bankInterfaceAvailable":
            preparation.send_gate.bank_interface_available is True,
        "bankTransactionAbsent": downstream_counts()["bankTransactions"] == 0,
        "paymentExecutionAbsent": downstream_counts()["paymentExecutions"] == 0,
        "segregationOfDutiesPassed":
            preparation.send_gate.segregation_valid is True,
    }
    reason_codes = {
        "authorizationGateStillValid": "AUTHORIZATION_INVALIDATED",
        "authorizationHashUnchanged": "AUTHORIZATION_HASH_CHANGED",
        "bankSendTaskUnchanged": "BANK_SEND_TASK_CHANGED",
        "formalPaymentOrderUnchanged": "FORMAL_ORDER_FREEZE_CHANGED",
        "amountUnchanged": "AMOUNT_CHANGED",
        "beneficiaryAccountUnchanged": "BENEFICIARY_ACCOUNT_CHANGED",
        "messagePreviewHashUnchanged": "PREVIEW_HASH_CHANGED",
        "bankInterfaceAvailable": "INTERFACE_UNAVAILABLE",
        "bankTransactionAbsent": "BANK_TRANSACTION_EXISTS",
        "paymentExecutionAbsent": "PAYMENT_EXECUTION_EXISTS",
        "segregationOfDutiesPassed": "SEGREGATION_FAILED",
    }
    blocking = [reason_codes[key] for key, passed in checks.items() if not passed]
    snapshot = {
        **checks,
        "result": "passed" if not blocking else "blocked",
        "eligible": not blocking,
        "blockingReasons": blocking,
        "gateNo": gate.gate_no,
        "taskNo": task.task_no,
        "formalPaymentOrderNo": order.order_no,
        "amount": str(task.amount),
        "beneficiaryAccountId": freeze.payee_account_id,
        "messagePreviewHash": task.message_preview_hash,
        "authorizationHash": gate.authorization_hash,
        "gateVersion": gate.version,
        "taskVersion": task.version,
        "orderVersion": order.version,
        "serverDerived": True,
        "currentStateSource": "server",
    }
    return {**snapshot, "validationHash": canonical_hash(snapshot)}


def _reconciliation(gate):
    source_id = (
        gate.source_task.source_preparation.source_formal_payment_order
        .source_risk_review.source_payment_order_draft.source_reconciliation_id
    )
    return PurchaseReconciliation.objects.get(pk=source_id)


def _transaction(gate, key, request_hash):
    return BusinessActionTransaction.objects.create(
        transaction_id=f"BSR-TX-{uuid.uuid4().hex.upper()}",
        action_code=CREATE_ACTION,
        idempotency_key=key,
        tenant_id=gate.tenant_id,
        source_key=f"bankSendExecutionGate:{gate.pk}",
        command_id=f"BSR-CMD-{uuid.uuid4().hex.upper()}",
        transaction_plan_id="bank-send-request-pre-dispatch-v1",
        review_id=gate.gate_no,
        review_hash=request_hash,
        status=BusinessActionTransaction.Status.IN_PROGRESS,
        outcome="draft",
        commit_status="not_committed",
        recovery_status="not_required",
        reconciliation=_reconciliation(gate),
    )


def _audit(tx, action, key, actor, request_object, evidence):
    gate = request_object.source_gate
    return BusinessActionAuditRecord.objects.create(
        transaction=tx,
        action_code=action,
        tenant_id=gate.tenant_id,
        actor=actor,
        source_key=f"bankSendExecutionGate:{gate.pk}",
        reconciliation=tx.reconciliation,
        result="committed",
        target_type="bankSendRequest",
        target_id=request_object.pk,
        target_no=request_object.request_no,
        review_id=gate.gate_no,
        review_hash=tx.review_hash,
        command_id=tx.command_id,
        idempotency_key=key,
        actor_name=actor.get_username(),
        tenant_or_scope=f"{gate.tenant_id}:{gate.legal_entity_id}",
        evidence_hash=canonical_hash(evidence),
        evidence=evidence,
    )


def _assert_feature_enabled(gate):
    if not getattr(settings, "PCE_BANK_SEND_REQUEST_FEATURE_ENABLED", False):
        raise ReconciliationError("BSR_FEATURE_DISABLED", "Bank send request is disabled", 403)
    trusted = getattr(settings, "PCE_BANK_SEND_REQUEST_TEST_TENANTS", set())
    if gate.tenant_id not in trusted and not getattr(
        settings, "PCE_BANK_SEND_REQUEST_PRODUCTION_ROLLOUT_ENABLED", False
    ):
        raise ReconciliationError(
            "BSR_PRODUCTION_DISABLED",
            "Bank send request preparation is limited to isolated test tenants",
            403,
        )


def create_bank_send_request(
    *, user, gate, idempotency_key, expected_source_version, explicit_user_action
):
    if explicit_user_action is not True:
        raise ReconciliationError(
            "BSR_EXPLICIT_ACTION_REQUIRED", "Explicit create action is required", 400
        )
    if not str(idempotency_key or "").strip():
        raise ReconciliationError(
            "BSR_IDEMPOTENCY_KEY_REQUIRED", "Idempotency key is required", 400
        )
    _assert_feature_enabled(gate)
    decision = ActionPermissionValidator().evaluate(
        user=user, module_code=MODULE_CODE, action_code=CREATE_ACTION,
        object_ids=[gate.pk], selection_count=1,
    )
    if not decision["granted"]:
        raise ReconciliationError("BSR_PERMISSION_DENIED", decision["reason"], 403)
    existing = BankSendRequestRepository().by_source(gate.pk)
    if existing:
        return {"classification": "existing_result", "created": False, "data": serialize_request(existing)}
    initial = evaluate_pre_dispatch_validation(gate)
    if not initial["eligible"]:
        raise ReconciliationError(
            "BSR_PRE_DISPATCH_BLOCKED", ",".join(initial["blockingReasons"]), 409
        )
    try:
        with transaction.atomic():
            current = BankSendExecutionGate.objects.select_for_update().select_related(
                "source_task__source_preparation__source_formal_payment_order__execution_freeze",
                "source_task__source_preparation__source_formal_payment_order__source_risk_review__source_payment_order_draft",
                "source_task__source_preparation__send_gate",
                "source_task__message_preview",
            ).get(pk=gate.pk)
            if current.version != expected_source_version:
                raise ReconciliationError("BSR_VERSION_CONFLICT", "Execution gate version conflict", 409)
            fresh = evaluate_pre_dispatch_validation(current)
            if not fresh["eligible"] or fresh["validationHash"] != initial["validationHash"]:
                raise ReconciliationError("BSR_SOURCE_CHANGED", "Pre-dispatch facts changed", 409)
            task, _, order, freeze = _source_parts(current)
            request_hash = canonical_hash({
                "gateId": current.pk, "gateVersion": current.version,
                "validationHash": fresh["validationHash"],
            })
            tx = _transaction(current, idempotency_key, request_hash)
            obj = create_business_object_with_initial_state(
                model=BankSendRequest, initial_state="draft",
                request_no=f"BSR-{current.gate_no}",
                tenant_id=current.tenant_id, batch_id=current.batch_id,
                source_gate=current,
                bank_send_execution_gate_no=current.gate_no,
                bank_send_task_no=task.task_no,
                formal_payment_order_no=order.order_no,
                company_id=current.company_id, legal_entity_id=current.legal_entity_id,
                source_gate_version=current.version, source_task_version=task.version,
                source_order_version=order.version, amount_snapshot=str(task.amount),
                beneficiary_account_snapshot=freeze.payee_account_id,
                message_preview_hash_snapshot=task.message_preview_hash,
                authorization_hash_snapshot=current.authorization_hash,
                validation_snapshot=fresh, validation_hash=fresh["validationHash"],
                idempotency_key=idempotency_key, business_transaction=tx,
                created_by=user,
            )
            creation_audit = _audit(tx, CREATE_ACTION, idempotency_key, user, obj, {
                "status": "draft", "externalSend": False,
            })
            obj.audit_record = creation_audit
            obj.save(update_fields=["audit_record", "updated_at"])
            BankSendPreDispatchValidation.objects.create(
                validation_no=f"{obj.request_no}-VAL-001", request=obj, attempt_no=1,
                result="passed", checks=fresh, source_snapshot=fresh,
                validation_hash=fresh["validationHash"], audit_record=creation_audit,
                operator=user,
            )
            validate_audit = _audit(
                tx, VALIDATE_ACTION, f"{idempotency_key}:validate", user, obj,
                {"transition": "draft->validated", "validationHash": fresh["validationHash"]},
            )
            transition_business_object(
                business_object=obj, object_type=OBJECT_TYPE, source_state="draft",
                target_state="validated", action_code=VALIDATE_ACTION, operator=user,
                reason="pre_dispatch_secondary_validation_passed",
                audit_reference=f"BusinessActionAuditRecord:{validate_audit.pk}",
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
            ready_audit = _audit(
                tx, READY_ACTION, f"{idempotency_key}:ready", user, obj,
                {"transition": "validated->ready_to_dispatch", "bankMessageSent": False},
            )
            transition_business_object(
                business_object=obj, object_type=OBJECT_TYPE, source_state="validated",
                target_state="ready_to_dispatch", action_code=READY_ACTION, operator=user,
                reason="request_ready_to_dispatch_without_bank_send",
                audit_reference=f"BusinessActionAuditRecord:{ready_audit.pk}",
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
            tx.status = BusinessActionTransaction.Status.COMMITTED
            tx.outcome = "ready_to_dispatch"
            tx.commit_status = "committed"
            tx.result_hash = canonical_hash({"requestId": obj.pk, "status": obj.status})
            tx.save(update_fields=["status", "outcome", "commit_status", "result_hash", "updated_at"])
        return {
            "classification": "created", "created": True,
            "data": serialize_request(BankSendRequestRepository().get(obj.pk)),
        }
    except IntegrityError:
        existing = BankSendRequestRepository().by_source(gate.pk)
        if existing:
            return {"classification": "existing_result", "created": False, "data": serialize_request(existing)}
        raise


def rerun_pre_dispatch_validation(*, user, request_object):
    fresh = evaluate_pre_dispatch_validation(request_object.source_gate, request_object)
    with transaction.atomic():
        current = BankSendRequestRepository().get(request_object.pk)
        attempt = (
            current.pre_dispatch_validations.aggregate(value=Max("attempt_no"))["value"] or 0
        ) + 1
        audit = _audit(
            current.business_transaction, RERUN_ACTION,
            f"{current.idempotency_key}:rerun:{attempt}", user, current,
            {"result": fresh["result"], "validationHash": fresh["validationHash"]},
        )
        BankSendPreDispatchValidation.objects.create(
            validation_no=f"{current.request_no}-VAL-{attempt:03d}",
            request=current, attempt_no=attempt, result=fresh["result"],
            checks=fresh, source_snapshot=fresh,
            validation_hash=fresh["validationHash"], audit_record=audit, operator=user,
        )
    return {"result": fresh["result"], "validation": fresh}


def bank_send_request_state_guard(request_object, transition_facts=None):
    facts = transition_facts or business_state_transition_facts(
        business_object=request_object, object_type=OBJECT_TYPE,
        expected_transitions=EXPECTED_TRANSITIONS, audit_target_type="bankSendRequest",
    )
    history = facts["statusTransitionHistory"]
    checks = {
        "unifiedStateService": all(
            row["objectType"] == OBJECT_TYPE
            and row["actionCode"] in {VALIDATE_ACTION, READY_ACTION}
            for row in history
        ),
        "noSkippedState": all(
            (row["sourceState"], row["targetState"]) in set(ALLOWED_STATE_TRANSITIONS)
            for row in history
        ),
        "historyLengthMatchesCount": len(history) == facts["statusTransitionCount"],
        "auditReferenceComplete": all(
            row["auditReference"].startswith("BusinessActionAuditRecord:")
            for row in history
        ),
        "stateMachineConsistent": facts["stateMachineConsistent"] is True,
    }
    return {"guardCode": "bank_send_request_state_guard", **checks, "passed": all(checks.values())}


def serialize_request(obj):
    transition_facts = business_state_transition_facts(
        business_object=obj, object_type=OBJECT_TYPE,
        expected_transitions=EXPECTED_TRANSITIONS, audit_target_type="bankSendRequest",
    )
    guard = bank_send_request_state_guard(obj, transition_facts)
    if not guard["passed"]:
        raise ValueError("bank send request state guard failed")
    validations = [{
        "validationNo": row.validation_no,
        "attemptNo": row.attempt_no,
        "result": row.result,
        "checks": dict(row.checks),
        "validationHash": row.validation_hash,
        "auditReference": f"BusinessActionAuditRecord:{row.audit_record_id}",
        "createdAt": row.created_at.isoformat(),
    } for row in obj.pre_dispatch_validations.all()]
    writes = build_bank_send_request_write_intent_facts(
        send_request_preparation_write_count=1,
        audit_write_count=1 + len(transition_facts["statusTransitionHistory"]) + len(validations),
        bank_send_execution_counts=downstream_counts(),
    )
    return {
        "id": obj.pk, "requestNo": obj.request_no,
        "tenantId": obj.tenant_id, "batchId": obj.batch_id,
        "bankSendExecutionGateNo": obj.bank_send_execution_gate_no,
        "bankSendTaskNo": obj.bank_send_task_no,
        "formalPaymentOrderNo": obj.formal_payment_order_no,
        "status": obj.status, "statusCode": obj.status,
        "statusLabel": STATUS_LABELS[obj.status], "version": obj.version,
        **transition_facts, "stateTransitionGuard": guard,
        "preDispatchValidation": dict(obj.validation_snapshot),
        "validationHistory": validations,
        "writeIntentFacts": writes, "downstreamCounts": downstream_counts(),
        "bankMessageSent": False, "paymentExecuted": False, "fundsDebited": False,
        "currentStateSource": "server",
    }


def bank_send_request_facts_for_rows(
    *, rows, canary_pool_facts, tenant_id=None, batch_id=None, request=None
):
    audit_count = sum(row["writeIntentFacts"]["auditWriteCount"] for row in rows)
    writes = build_bank_send_request_write_intent_facts(
        send_request_preparation_write_count=len(rows),
        audit_write_count=audit_count,
        bank_send_execution_counts=downstream_counts(),
    )
    facts = BankSendRequestFacts.from_serialized_rows(
        serialized_rows=rows, write_intent_facts=writes
    ).as_dict()
    load = build_fact_load_facts(
        fact_load_status="success", api_url="/api/finance/bank-send-requests/",
        http_status=200, tenant_id=tenant_id, batch_id=batch_id, request=request,
    )
    return {**canary_pool_facts, **facts, **load, "factLoadFacts": load}
