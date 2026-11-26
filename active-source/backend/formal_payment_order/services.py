import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from payment_risk_review.models import PaymentRiskReview
from payment_risk_review.services import eligibility as risk_review_eligibility
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
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    ProcessDefinition,
    WorkflowInstance,
)
from workflow_runtime.providers import (
    ApprovalPolicyProvider,
    ApprovalRouteProvider,
    SegregationOfDutiesProvider,
    UserOrganizationRoleProvider,
)
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .authority import assert_generate_authorized
from .facts import (
    build_execution_gate_facts,
    execution_snapshot_hash,
    execution_snapshot_payload,
)
from .models import (
    FormalPaymentOrder,
    FormalPaymentOrderApproval,
    FormalPaymentOrderEvidenceSnapshot,
    FormalPaymentOrderFreezeSnapshot,
    FormalPaymentOrderSourceRelation,
    FormalPaymentOrderSourceSnapshot,
)
from .providers import PaymentRiskReviewAuthorityProvider
from .repositories import FormalPaymentOrderRepository


VERSION = "V1.14.2.8.4.7.54.3"
CANONICAL_NAME = "正式付款单"
MODULE_CODE = "formal-payment-order"
SOURCE_DOCUMENT_TYPE = "paymentRiskReview"
PREVIOUS_MODULE_CODE = "payment-risk-review"
NEXT_MODULE_CODE = "bank-send-task"
GENERATE_ACTION = "generate-formal-payment-order"
SUBMIT_ACTION = "submit-formal-payment-order"
APPROVE_ACTION = "approve-formal-payment-order"
FREEZE_ACTION = "freeze-formal-payment-order"
DOCUMENT_TYPE = "formal_payment_order"
PROCESS_DEFINITION_CODE = "FORMAL_PAYMENT_ORDER_APPROVAL"
APPROVAL_ROLES = ("payment_checker", "payment_authorizer")
SEND_GATE_BATCH_ID = "PURCHASE-FLOW-DEMO-V1-V54-SEND-GATE"
NUMBER_POLICY_VERSION = "formal-payment-order-number-v1"
ALLOWED_STATE_TRANSITIONS = (
    (FormalPaymentOrder.Status.PREPARED, FormalPaymentOrder.Status.SUBMITTED),
    (FormalPaymentOrder.Status.SUBMITTED, FormalPaymentOrder.Status.APPROVED),
    (
        FormalPaymentOrder.Status.APPROVED,
        FormalPaymentOrder.Status.FROZEN_FOR_EXECUTION,
    ),
)


def source_hash(authority):
    return canonical_hash({
        "provider": authority["provider"],
        "repository": authority["repository"],
        "source": authority["source"],
        "payment": authority["payment"],
    })


def source_gate(source, authority=None, check_existing=True):
    authority = authority or PaymentRiskReviewAuthorityProvider().read(source.pk)
    if not authority:
        return ["SOURCE_MISSING"]
    source_data = authority["source"]
    allowed = source_data["eligibility"]
    reasons = []
    if source.status != "passed":
        reasons.append("RISK_NOT_PASSED")
    if source.risk_result != "passed":
        reasons.append("RISK_RESULT_NOT_PASSED")
    if source.risk_level != "low":
        reasons.append("RISK_LEVEL_NOT_LOW")
    if not allowed.get("eligible"):
        reasons.append("SOURCE_NOT_ELIGIBLE")
    if allowed.get("nextStepReadiness") != "ready_for_formal_payment_order":
        reasons.append("READINESS_NOT_RELEASED")
    if source.version != source_data["version"] or source.review_version != source_data["reviewVersion"]:
        reasons.append("SOURCE_STALE")
    if not source_data["ruleVersion"] or not source_data["resultHash"]:
        reasons.append("RISK_EVIDENCE_MISSING")
    evidence = authority["evidence"]
    if not evidence["funds"]:
        reasons.append("FUNDS_EVIDENCE_MISSING")
    if not evidence["bankInterface"]:
        reasons.append("BANK_INTERFACE_EVIDENCE_MISSING")
    if not evidence["account"].get("payer") or not evidence["account"].get("payee"):
        reasons.append("ACCOUNT_EVIDENCE_MISSING")
    if not evidence["riskReview"]:
        reasons.append("RISK_REVIEW_EVIDENCE_MISSING")
    if not evidence["segregation"]:
        reasons.append("SEGREGATION_EVIDENCE_MISSING")
    if check_existing and FormalPaymentOrder.objects.filter(source_risk_review=source).exists():
        reasons.append("EXISTING_ORDER")
    return list(dict.fromkeys(reasons))


def _inject(step, requested):
    if not requested or requested != step:
        return
    if not getattr(settings, "PCE_FORMAL_PAYMENT_ORDER_FAILURE_INJECTION_ENABLED", False):
        raise ReconciliationError("FPO_FAILURE_INJECTION_DISABLED", "Failure injection disabled", 403)
    raise ReconciliationError("FPO_INJECTED_FAILURE", f"Injected failure at {step}", 409, True)


def _register(key, source, request_hash):
    existing = BusinessActionIdempotency.objects.select_for_update().filter(
        action_code=GENERATE_ACTION,
        idempotency_key=key,
    ).first()
    if existing:
        if existing.request_hash != request_hash or existing.source_key != f"paymentRiskReview:{source.pk}":
            raise ReconciliationError("FPO_IDEMPOTENCY_CONFLICT", "Idempotency payload conflict", 409)
        if existing.status == BusinessActionIdempotency.Status.COMMITTED and existing.target_id:
            return existing, True
        raise ReconciliationError("FPO_IN_PROGRESS", "Action is already in progress", 409, True)
    return BusinessActionIdempotency.objects.create(
        action_code=GENERATE_ACTION,
        idempotency_key=key,
        tenant_id=source.tenant_id,
        source_key=f"paymentRiskReview:{source.pk}",
        request_hash=request_hash,
        status=BusinessActionIdempotency.Status.IN_PROGRESS,
    ), False


def _reserve_number(source, key, planned_date):
    period = planned_date.strftime("%Y-%m")
    scope = f"FPO:{source.tenant_id}:{period}"
    sequence, _ = BusinessDocumentNumberSequence.objects.select_for_update().get_or_create(
        number_scope=scope,
        defaults={"current_value": 0},
    )
    sequence.current_value += 1
    sequence.save(update_fields=["current_value", "updated_at"])
    number = f"FPO{planned_date.strftime('%Y%m')}{sequence.current_value:08d}"
    return BusinessDocumentNumberReservation.objects.create(
        document_type="formalPaymentOrder",
        number_policy_version=NUMBER_POLICY_VERSION,
        number_scope=scope,
        legal_entity_id=str(source.company_id),
        ledger_book_id="",
        reserved_number=number,
        tenant_id=source.tenant_id,
        accounting_period=period,
        idempotency_key=key,
        status=BusinessDocumentNumberReservation.Status.RESERVED,
    )


def _create_transaction(source, key, request_hash):
    draft = source.source_payment_order_draft
    reconciliation = PurchaseReconciliation.objects.get(pk=draft.source_reconciliation_id)
    return BusinessActionTransaction.objects.create(
        transaction_id=f"FPO-TX-{uuid.uuid4().hex.upper()}",
        action_code=GENERATE_ACTION,
        idempotency_key=key,
        tenant_id=source.tenant_id,
        source_key=f"paymentRiskReview:{source.pk}",
        command_id=f"FPO-CMD-{uuid.uuid4().hex.upper()}",
        transaction_plan_id="formal-payment-order-generation-v1",
        review_id=source.review_no,
        review_hash=source.source_draft_hash,
        status=BusinessActionTransaction.Status.IN_PROGRESS,
        outcome="pending",
        commit_status="not_started",
        recovery_status="not_required",
        reconciliation=reconciliation,
    )


def generate_formal_payment_order(
    *,
    user,
    source,
    idempotency_key,
    expected_source_version,
    explicit_user_action,
    failure_step="",
):
    if explicit_user_action is not True:
        raise ReconciliationError("FPO_EXPLICIT_ACTION_REQUIRED", "Explicit user action required", 400)
    if not idempotency_key:
        raise ReconciliationError("FPO_IDEMPOTENCY_KEY_REQUIRED", "Idempotency key required", 400)
    assert_generate_authorized(user, source.tenant_id)
    _inject("after_authorization", failure_step)
    request_hash = canonical_hash({
        "action": GENERATE_ACTION,
        "sourceId": source.pk,
        "expectedSourceVersion": expected_source_version,
    })
    try:
        with transaction.atomic():
            idem, replay = _register(idempotency_key, source, request_hash)
            if replay:
                return {
                    "classification": "existing_result",
                    "created": False,
                    "data": serialize_order(FormalPaymentOrderRepository().get(idem.target_id)),
                }
            _inject("after_idempotency_registration", failure_step)
            tx = _create_transaction(source, idempotency_key, request_hash)
            lock, lock_created = BusinessActionSourceLock.objects.select_for_update().get_or_create(
                lock_key=f"paymentRiskReview:{source.pk}",
                defaults={
                    "owner_transaction_id": tx.transaction_id,
                    "state": "active",
                },
            )
            if not lock_created and lock.state == "active":
                raise ReconciliationError("FPO_SOURCE_LOCKED", "Source is locked", 409, True)
            lock.owner_transaction_id = tx.transaction_id
            lock.state = "active"
            lock.released_at = None
            lock.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
            current = (
                PaymentRiskReview.objects.select_for_update()
                .select_related("source_payment_order_draft")
                .get(pk=source.pk)
            )
            authority = PaymentRiskReviewAuthorityProvider().read(current.pk)
            _inject("after_source_reload", failure_step)
            if current.version != expected_source_version:
                raise ReconciliationError("FPO_VERSION_CONFLICT", "Source version conflict", 409)
            reasons = source_gate(current, authority)
            if reasons:
                raise ReconciliationError(f"FPO_{reasons[0]}", ",".join(reasons), 409)
            payment = authority["payment"]
            reservation = _reserve_number(current, idempotency_key, current.source_payment_order_draft.planned_execution_date)
            _inject("after_number_reservation", failure_step)
            target = create_business_object_with_initial_state(
                model=FormalPaymentOrder,
                initial_state=FormalPaymentOrder.Status.PREPARED,
                order_no=reservation.reserved_number,
                source_risk_review=current,
                source_risk_review_no=current.review_no,
                source_risk_review_version=current.review_version,
                source_risk_rule_version=authority["source"]["ruleVersion"],
                source_risk_review_hash=source_hash(authority),
                source_scenario_code=current.scenario_code,
                tenant_id=current.tenant_id,
                company_id=current.company_id,
                supplier_id=payment["supplierId"],
                supplier_name=payment["supplierName"],
                legal_entity=payment["legalEntity"],
                ledger_book=payment["ledgerBook"],
                currency=payment["currency"],
                amount=payment["amount"],
                planned_execution_date=payment["plannedExecutionDate"],
                idempotency_key=idempotency_key,
                number_reservation=reservation,
                business_transaction=tx,
                created_by=user,
            )
            _inject("after_target_creation", failure_step)
            source_snapshot = FormalPaymentOrderSourceSnapshot.objects.create(
                formal_payment_order=target,
                source_risk_review_id=current.pk,
                source_risk_review_no=current.review_no,
                risk_review_version=current.review_version,
                risk_rule_version=authority["source"]["ruleVersion"],
                source_hash=source_hash(authority),
                draft_version=payment["draftVersion"],
                source_payment_order_draft_id=payment["draftId"],
                source_payment_order_draft_no=payment["draftNo"],
                eligibility_hash=canonical_hash(authority["source"]["eligibility"]),
            )
            evidence_hash = canonical_hash(authority["evidence"])
            FormalPaymentOrderEvidenceSnapshot.objects.create(
                formal_payment_order=target,
                funds_evidence=authority["evidence"]["funds"],
                bank_interface_evidence=authority["evidence"]["bankInterface"],
                account_evidence=authority["evidence"]["account"],
                risk_review_evidence=authority["evidence"]["riskReview"],
                segregation_evidence=authority["evidence"]["segregation"],
                evidence_hash=evidence_hash,
            )
            FormalPaymentOrderSourceRelation.objects.create(
                formal_payment_order=target,
                source_document_type=SOURCE_DOCUMENT_TYPE,
                source_object_id=current.pk,
                source_object_no=current.review_no,
                relation_hash=canonical_hash({
                    "source": f"paymentRiskReview:{current.pk}",
                    "target": f"formalPaymentOrder:{target.pk}",
                    "snapshot": source_snapshot.source_hash,
                }),
            )
            _inject("after_snapshots", failure_step)
            audit = BusinessActionAuditRecord.objects.create(
                transaction=tx,
                action_code=GENERATE_ACTION,
                tenant_id=current.tenant_id,
                actor=user,
                source_key=f"paymentRiskReview:{current.pk}",
                reconciliation=tx.reconciliation,
                result="committed",
                target_type="formalPaymentOrder",
                target_id=target.pk,
                target_no=target.order_no,
                review_id=current.review_no,
                review_hash=current.source_draft_hash,
                command_id=tx.command_id,
                idempotency_key=idempotency_key,
                actor_name=user.get_username(),
                tenant_or_scope=current.tenant_id,
                evidence_hash=evidence_hash,
                evidence={
                    "sourceSnapshotId": source_snapshot.pk,
                    "sourceRiskReviewNo": current.review_no,
                    "status": "prepared",
                },
            )
            target.audit_record = audit
            target.save(update_fields=["audit_record", "updated_at"])
            _inject("after_audit", failure_step)
            now = timezone.now()
            reservation.status = BusinessDocumentNumberReservation.Status.CONSUMED
            reservation.consumed_at = now
            reservation.save(update_fields=["status", "consumed_at"])
            result_hash = canonical_hash({
                "id": target.pk,
                "orderNo": target.order_no,
                "status": target.status,
                "sourceRiskReviewNo": current.review_no,
            })
            tx.status = BusinessActionTransaction.Status.COMMITTED
            tx.outcome = "created"
            tx.commit_status = "committed"
            tx.result_hash = result_hash
            tx.save(update_fields=["status", "outcome", "commit_status", "result_hash", "updated_at"])
            idem.status = BusinessActionIdempotency.Status.COMMITTED
            idem.target_type = "formalPaymentOrder"
            idem.target_id = target.pk
            idem.target_no = target.order_no
            idem.transaction_id = tx.transaction_id
            idem.result_reference = f"formalPaymentOrder:{target.pk}"
            idem.save(update_fields=[
                "status", "target_type", "target_id", "target_no",
                "transaction_id", "result_reference", "updated_at",
            ])
            lock.state = "released"
            lock.released_at = now
            lock.save(update_fields=["state", "released_at", "acquired_at"])
            return {
                "classification": "created",
                "created": True,
                "data": serialize_order(FormalPaymentOrderRepository().get(target.pk)),
            }
    except IntegrityError:
        existing = FormalPaymentOrderRepository().by_source(source.pk)
        if existing:
            return {
                "classification": "existing_result",
                "created": False,
                "data": serialize_order(existing),
            }
        raise


def _assert_action_authorized(user, order, permission):
    assert_generate_authorized(user, order.tenant_id)
    if (
        order.tenant_id
        not in getattr(settings, "PCE_FORMAL_PAYMENT_ORDER_TEST_TENANTS", set())
        and not user.is_superuser
        and not user.has_perm(permission)
    ):
        raise ReconciliationError("FPO_PERMISSION_DENIED", "Permission denied", 403)


def _require_explicit_action(value):
    if value is not True:
        raise ReconciliationError(
            "FPO_EXPLICIT_ACTION_REQUIRED",
            "Explicit user action required",
            400,
        )


def _gate_existing(action_code, idempotency_key, request_hash):
    existing = BusinessActionIdempotency.objects.filter(
        action_code=action_code,
        idempotency_key=idempotency_key,
    ).first()
    if not existing:
        return None
    if existing.request_hash != request_hash:
        raise ReconciliationError(
            "FPO_IDEMPOTENCY_CONFLICT",
            "Idempotency payload conflict",
            409,
        )
    if (
        existing.status == BusinessActionIdempotency.Status.COMMITTED
        and existing.target_id
    ):
        return FormalPaymentOrderRepository().get(existing.target_id)
    raise ReconciliationError("FPO_IN_PROGRESS", "Action is already in progress", 409, True)


def _gate_transaction(order, action_code, idempotency_key):
    source = order.source_risk_review
    reconciliation = PurchaseReconciliation.objects.get(
        pk=source.source_payment_order_draft.source_reconciliation_id
    )
    return BusinessActionTransaction.objects.create(
        transaction_id=f"FPO-GATE-TX-{uuid.uuid4().hex.upper()}",
        action_code=action_code,
        idempotency_key=idempotency_key,
        tenant_id=order.tenant_id,
        source_key=f"formalPaymentOrder:{order.pk}",
        command_id=f"FPO-GATE-CMD-{uuid.uuid4().hex.upper()}",
        transaction_plan_id="formal-payment-order-execution-gate-v1",
        review_id=order.order_no,
        review_hash=order.source_risk_review_hash,
        status=BusinessActionTransaction.Status.IN_PROGRESS,
        outcome="pending",
        commit_status="not_committed",
        recovery_status="not_required",
        reconciliation=reconciliation,
    )


def _gate_audit(transaction_row, action_code, idempotency_key, actor, order, evidence):
    return BusinessActionAuditRecord.objects.create(
        transaction=transaction_row,
        action_code=action_code,
        tenant_id=order.tenant_id,
        actor=actor,
        source_key=f"formalPaymentOrder:{order.pk}",
        reconciliation=transaction_row.reconciliation,
        result="committed",
        target_type="formalPaymentOrder",
        target_id=order.pk,
        target_no=order.order_no,
        review_id=transaction_row.review_id,
        review_hash=transaction_row.review_hash,
        command_id=transaction_row.command_id,
        idempotency_key=idempotency_key,
        actor_name=actor.get_username(),
        tenant_or_scope=f"{order.tenant_id}:{order.legal_entity}",
        evidence_hash=canonical_hash(evidence),
        evidence=evidence,
    )


def _gate_commit(transaction_row, idempotency_row, order, outcome):
    result_hash = canonical_hash(
        {
            "orderNo": order.order_no,
            "status": order.status,
            "version": order.version,
            "outcome": outcome,
        }
    )
    transaction_row.status = BusinessActionTransaction.Status.COMMITTED
    transaction_row.outcome = outcome
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
    idempotency_row.status = BusinessActionIdempotency.Status.COMMITTED
    idempotency_row.target_type = "formalPaymentOrder"
    idempotency_row.target_id = order.pk
    idempotency_row.target_no = order.order_no
    idempotency_row.transaction_id = transaction_row.transaction_id
    idempotency_row.result_reference = f"formalPaymentOrder:{order.pk}"
    idempotency_row.save(
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


def _acquire_gate_lock(order, transaction_row):
    lock, created = BusinessActionSourceLock.objects.select_for_update().get_or_create(
        lock_key=f"formalPaymentOrder:{order.pk}",
        defaults={
            "owner_transaction_id": transaction_row.transaction_id,
            "state": "active",
        },
    )
    if not created and lock.state == "active":
        raise ReconciliationError("FPO_SOURCE_LOCKED", "Formal payment order is locked", 409, True)
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
    return lock


def _release_gate_lock(lock):
    lock.state = "released"
    lock.released_at = timezone.now()
    lock.save(update_fields=["state", "released_at", "acquired_at"])


def submit_formal_payment_order(
    *,
    user,
    order,
    idempotency_key,
    expected_version,
    explicit_user_action,
):
    _require_explicit_action(explicit_user_action)
    _assert_action_authorized(
        user,
        order,
        "formal_payment_order.submit_formal_payment_order",
    )
    request_hash = canonical_hash(
        {
            "orderId": order.pk,
            "expectedVersion": expected_version,
            "action": SUBMIT_ACTION,
        }
    )
    prior = _gate_existing(SUBMIT_ACTION, idempotency_key, request_hash)
    if prior:
        return {
            "classification": "existing_result",
            "submitted": False,
            "data": serialize_order(prior),
        }
    with transaction.atomic():
        current = (
            FormalPaymentOrderRepository()
            .queryset()
            .select_for_update()
            .get(pk=order.pk)
        )
        if current.status != FormalPaymentOrder.Status.PREPARED:
            raise ReconciliationError(
                "FPO_SUBMIT_STATE_INVALID",
                "Only prepared formal payment orders can be submitted",
                409,
            )
        if current.version != expected_version:
            raise ReconciliationError("FPO_VERSION_CONFLICT", "Version conflict", 409)
        policy = ApprovalPolicyProvider().read(
            DOCUMENT_TYPE,
            current.legal_entity,
            current.amount,
            current.currency,
        )
        route = ApprovalRouteProvider().read(policy.payload["policyId"]) if policy else None
        sod = SegregationOfDutiesProvider().read(DOCUMENT_TYPE)
        steps = route.payload.get("steps", []) if route else []
        if not policy or not route or [step.get("roleCode") for step in steps] != list(APPROVAL_ROLES):
            raise ReconciliationError(
                "FPO_APPROVAL_ROUTE_INVALID",
                "Formal payment order approval route must use checker and authorizer",
                409,
            )
        if not sod or not sod.payload.get("applicantCannotApprove"):
            raise ReconciliationError(
                "FPO_SEGREGATION_POLICY_MISSING",
                "Segregation of duties policy is missing",
                409,
            )
        idempotency = BusinessActionIdempotency.objects.create(
            action_code=SUBMIT_ACTION,
            idempotency_key=idempotency_key,
            tenant_id=current.tenant_id,
            source_key=f"formalPaymentOrder:{current.pk}",
            request_hash=request_hash,
            status=BusinessActionIdempotency.Status.IN_PROGRESS,
        )
        transaction_row = _gate_transaction(current, SUBMIT_ACTION, idempotency_key)
        lock = _acquire_gate_lock(current, transaction_row)
        definition, _ = ProcessDefinition.objects.get_or_create(
            definition_code=PROCESS_DEFINITION_CODE,
            document_type=DOCUMENT_TYPE,
            version=1,
            defaults={
                "active": True,
                "definition_hash": canonical_hash(
                    {
                        "definitionCode": PROCESS_DEFINITION_CODE,
                        "documentType": DOCUMENT_TYPE,
                        "roles": APPROVAL_ROLES,
                    }
                ),
            },
        )
        workflow = WorkflowInstance.objects.create(
            instance_no=f"WFI-FPO-{current.order_no}",
            process_definition=definition,
            document_type=DOCUMENT_TYPE,
            document_id=current.pk,
            status=WorkflowInstance.Status.PENDING,
            current_step=1,
            total_steps=2,
        )
        ApprovalTask.objects.create(
            task_no=f"APT-FPO-{current.order_no}-01",
            workflow_instance=workflow,
            step_no=1,
            required_role_code=APPROVAL_ROLES[0],
            minimum_approvals=1,
            allow_parallel=False,
            status=ApprovalTask.Status.PENDING,
        )
        approval = FormalPaymentOrderApproval.objects.create(
            formal_payment_order=current,
            workflow_instance=workflow,
            approval_status=FormalPaymentOrderApproval.Status.PENDING,
            submitted_at=timezone.now(),
        )
        audit = _gate_audit(
            transaction_row,
            SUBMIT_ACTION,
            idempotency_key,
            user,
            current,
            {
                "version": VERSION,
                "workflowInstanceId": workflow.pk,
                "approvalId": approval.pk,
                "approvalRoles": list(APPROVAL_ROLES),
                "stateTransition": "prepared->submitted",
            },
        )
        transition_business_object(
            business_object=current,
            object_type=DOCUMENT_TYPE,
            source_state=FormalPaymentOrder.Status.PREPARED,
            target_state=FormalPaymentOrder.Status.SUBMITTED,
            action_code=SUBMIT_ACTION,
            operator=user,
            reason="approval_submission",
            audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
            workflow_instance=workflow,
            allowed_transitions=ALLOWED_STATE_TRANSITIONS,
        )
        _gate_commit(transaction_row, idempotency, current, "submitted")
        _release_gate_lock(lock)
    return {
        "classification": "submitted",
        "submitted": True,
        "data": serialize_order(FormalPaymentOrderRepository().get(order.pk)),
    }


def approve_formal_payment_order(
    *,
    user,
    order,
    task_id,
    idempotency_key,
    expected_order_version,
    expected_workflow_version,
    expected_task_version,
    explicit_user_action,
    comment="",
):
    _require_explicit_action(explicit_user_action)
    _assert_action_authorized(
        user,
        order,
        "formal_payment_order.approve_formal_payment_order",
    )
    request_hash = canonical_hash(
        {
            "orderId": order.pk,
            "taskId": task_id,
            "expectedOrderVersion": expected_order_version,
            "expectedWorkflowVersion": expected_workflow_version,
            "expectedTaskVersion": expected_task_version,
            "comment": comment,
        }
    )
    prior = _gate_existing(APPROVE_ACTION, idempotency_key, request_hash)
    if prior:
        return {
            "classification": "existing_result",
            "approved": False,
            "data": serialize_order(prior),
        }
    with transaction.atomic():
        current = (
            FormalPaymentOrderRepository()
            .queryset()
            .select_for_update()
            .get(pk=order.pk)
        )
        if current.status != FormalPaymentOrder.Status.SUBMITTED:
            raise ReconciliationError(
                "FPO_APPROVAL_STATE_INVALID",
                "Only submitted formal payment orders can be approved",
                409,
            )
        approval = current.approval
        workflow = WorkflowInstance.objects.select_for_update().get(
            pk=approval.workflow_instance_id
        )
        task = ApprovalTask.objects.select_for_update().filter(
            pk=task_id,
            workflow_instance=workflow,
        ).first()
        if not task or task.status != ApprovalTask.Status.PENDING:
            raise ReconciliationError(
                "FPO_APPROVAL_TASK_INVALID",
                "Approval task is missing or not pending",
                409,
            )
        if (
            current.version != expected_order_version
            or workflow.version != expected_workflow_version
            or task.version != expected_task_version
        ):
            raise ReconciliationError("FPO_VERSION_CONFLICT", "Version conflict", 409)
        roles = UserOrganizationRoleProvider().read(user.pk, current.legal_entity)
        sod = SegregationOfDutiesProvider().read(DOCUMENT_TYPE)
        prior_actor_ids = list(
            ApprovalDecision.objects.filter(
                task__workflow_instance=workflow,
                decision="approved",
            ).values_list("actor_id", flat=True)
        )
        segregation_valid = bool(
            sod
            and task.required_role_code in roles.payload.get("roleCodes", [])
            and current.legal_entity in roles.payload.get("legalEntityIds", [])
            and user.pk != current.created_by_id
            and user.pk not in prior_actor_ids
        )
        if not segregation_valid:
            raise ReconciliationError(
                "FPO_APPROVAL_SEGREGATION_INVALID",
                "Maker, checker and final authorizer must be different authorized users",
                409,
            )
        idempotency = BusinessActionIdempotency.objects.create(
            action_code=APPROVE_ACTION,
            idempotency_key=idempotency_key,
            tenant_id=current.tenant_id,
            source_key=f"formalPaymentOrder:{current.pk}",
            request_hash=request_hash,
            status=BusinessActionIdempotency.Status.IN_PROGRESS,
        )
        transaction_row = _gate_transaction(current, APPROVE_ACTION, idempotency_key)
        lock = _acquire_gate_lock(current, transaction_row)
        decision = ApprovalDecision.objects.create(
            task=task,
            actor=user,
            decision="approved",
            comment=str(comment or ""),
            action_id=APPROVE_ACTION,
            idempotency_key=idempotency_key,
            decision_hash=canonical_hash(
                {
                    "orderId": current.pk,
                    "taskId": task.pk,
                    "actorId": user.pk,
                    "role": task.required_role_code,
                    "decision": "approved",
                }
            ),
        )
        task.status = ApprovalTask.Status.APPROVED
        task.version += 1
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "version", "completed_at"])
        approval.version += 1
        if task.step_no == 1:
            workflow.current_step = 2
            ApprovalTask.objects.create(
                task_no=f"APT-FPO-{current.order_no}-02",
                workflow_instance=workflow,
                step_no=2,
                required_role_code=APPROVAL_ROLES[1],
                minimum_approvals=1,
                allow_parallel=False,
                status=ApprovalTask.Status.PENDING,
            )
            outcome = "checker_approved"
        elif task.step_no == 2:
            workflow.status = WorkflowInstance.Status.APPROVED
            workflow.completed_at = timezone.now()
            approval.approval_status = FormalPaymentOrderApproval.Status.APPROVED
            approval.approved_at = timezone.now()
            approval.approved_by = user
            outcome = "approved"
        else:
            raise ReconciliationError(
                "FPO_APPROVAL_TASK_INVALID",
                "Unexpected approval step",
                409,
            )
        workflow.version += 1
        workflow.save()
        approval.save()
        if task.step_no != 2:
            current.version += 1
            current.save(update_fields=["version", "updated_at"])
        audit = _gate_audit(
            transaction_row,
            APPROVE_ACTION,
            idempotency_key,
            user,
            current,
            {
                "version": VERSION,
                "workflowInstanceId": workflow.pk,
                "approvalDecisionId": decision.pk,
                "stepNo": task.step_no,
                "roleCode": task.required_role_code,
                "segregationValid": True,
                "stateTransition": (
                    "submitted->approved" if task.step_no == 2 else "submitted->submitted"
                ),
            },
        )
        if task.step_no == 2:
            transition_business_object(
                business_object=current,
                object_type=DOCUMENT_TYPE,
                source_state=FormalPaymentOrder.Status.SUBMITTED,
                target_state=FormalPaymentOrder.Status.APPROVED,
                action_code=APPROVE_ACTION,
                operator=user,
                reason="final_approval_completed",
                audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                workflow_instance=workflow,
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
        _gate_commit(transaction_row, idempotency, current, outcome)
        _release_gate_lock(lock)
    return {
        "classification": outcome,
        "approved": outcome == "approved",
        "data": serialize_order(FormalPaymentOrderRepository().get(order.pk)),
    }


def freeze_formal_payment_order(
    *,
    user,
    order,
    idempotency_key,
    expected_order_version,
    expected_approval_version,
    explicit_user_action,
):
    _require_explicit_action(explicit_user_action)
    _assert_action_authorized(
        user,
        order,
        "formal_payment_order.freeze_formal_payment_order",
    )
    request_hash = canonical_hash(
        {
            "orderId": order.pk,
            "expectedOrderVersion": expected_order_version,
            "expectedApprovalVersion": expected_approval_version,
            "action": FREEZE_ACTION,
        }
    )
    prior = _gate_existing(FREEZE_ACTION, idempotency_key, request_hash)
    if prior:
        return {
            "classification": "existing_result",
            "frozen": False,
            "data": serialize_order(prior),
        }
    with transaction.atomic():
        current = (
            FormalPaymentOrderRepository()
            .queryset()
            .select_for_update()
            .get(pk=order.pk)
        )
        if current.status != FormalPaymentOrder.Status.APPROVED:
            raise ReconciliationError(
                "FPO_FREEZE_REQUIRES_APPROVED_STATUS",
                "Only approved formal payment orders can be frozen",
                409,
            )
        approval = current.approval
        if (
            approval.approval_status != FormalPaymentOrderApproval.Status.APPROVED
            or current.version != expected_order_version
            or approval.version != expected_approval_version
        ):
            raise ReconciliationError(
                "FPO_FREEZE_APPROVAL_INVALID",
                "Approved status and current versions are required",
                409,
            )
        pre_freeze = build_execution_gate_facts(current).bank_send_eligibility
        if not all(
            [
                pre_freeze.state_machine_passed,
                pre_freeze.risk_passed,
                pre_freeze.approval_passed,
                pre_freeze.funds_passed,
                pre_freeze.bank_passed,
                pre_freeze.signature_passed,
                pre_freeze.segregation_passed,
            ]
        ):
            raise ReconciliationError(
                "FPO_FREEZE_GATE_BLOCKED",
                "Execution gate prerequisites are not satisfied",
                409,
            )
        idempotency = BusinessActionIdempotency.objects.create(
            action_code=FREEZE_ACTION,
            idempotency_key=idempotency_key,
            tenant_id=current.tenant_id,
            source_key=f"formalPaymentOrder:{current.pk}",
            request_hash=request_hash,
            status=BusinessActionIdempotency.Status.IN_PROGRESS,
        )
        transaction_row = _gate_transaction(current, FREEZE_ACTION, idempotency_key)
        lock = _acquire_gate_lock(current, transaction_row)
        payload = execution_snapshot_payload(current, approval)
        freeze = FormalPaymentOrderFreezeSnapshot.objects.create(
            formal_payment_order=current,
            amount=current.amount,
            currency=current.currency,
            payer_account_id=payload["payerAccountId"],
            payee_account_id=payload["payeeAccountId"],
            bank_route=payload["bankRoute"],
            execution_date=current.planned_execution_date,
            risk_version=payload["riskVersion"],
            approval_version=payload["approvalVersion"],
            freeze_hash=execution_snapshot_hash(current, approval),
            frozen_by=user,
        )
        audit = _gate_audit(
            transaction_row,
            FREEZE_ACTION,
            idempotency_key,
            user,
            current,
            {
                "version": VERSION,
                "freezeId": freeze.pk,
                "freezeHash": freeze.freeze_hash,
                "approvalVersion": approval.version,
                "riskVersion": current.source_risk_review.review_version,
                "stateTransition": "approved->frozen_for_execution",
                "bankMessageCreated": False,
                "paymentExecuted": False,
            },
        )
        transition_business_object(
            business_object=current,
            object_type=DOCUMENT_TYPE,
            source_state=FormalPaymentOrder.Status.APPROVED,
            target_state=FormalPaymentOrder.Status.FROZEN_FOR_EXECUTION,
            action_code=FREEZE_ACTION,
            operator=user,
            reason="execution_facts_frozen",
            audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
            workflow_instance=approval.workflow_instance,
            allowed_transitions=ALLOWED_STATE_TRANSITIONS,
        )
        _gate_commit(transaction_row, idempotency, current, "frozen_for_execution")
        _release_gate_lock(lock)
    return {
        "classification": "frozen_for_execution",
        "frozen": True,
        "data": serialize_order(FormalPaymentOrderRepository().get(order.pk)),
    }


def serialize_order(order):
    source = order.source_risk_review
    draft = source.source_payment_order_draft
    source_snapshot = order.source_snapshot
    evidence = order.evidence_snapshot
    tx = order.business_transaction
    reservation = order.number_reservation
    execution_gate = build_execution_gate_facts(order).as_dict()
    approval = getattr(order, "approval", None)
    workflow = approval.workflow_instance if approval else None
    approval_tasks = list(workflow.tasks.order_by("step_no")) if workflow else []
    bank_eligibility = execution_gate["bankSendEligibility"]
    return {
        "id": order.pk,
        "orderNo": order.order_no,
        "sourceDocumentType": order.source_document_type,
        "sourceRiskReviewId": source.pk,
        "sourceRiskReviewNo": order.source_risk_review_no,
        "sourceRiskReviewVersion": order.source_risk_review_version,
        "sourceRiskRuleVersion": order.source_risk_rule_version,
        "sourceScenarioCode": order.source_scenario_code,
        "sourcePaymentOrderDraftNo": draft.draft_no,
        "supplierId": order.supplier_id,
        "supplierName": order.supplier_name,
        "legalEntity": order.legal_entity,
        "ledgerBook": order.ledger_book,
        "currency": order.currency,
        "amount": str(order.amount),
        "plannedExecutionDate": order.planned_execution_date.isoformat(),
        "status": order.status,
        "version": order.version,
        "createdAt": order.created_at.isoformat(),
        "idempotencyStatus": "committed",
        "numberReservationStatus": reservation.status,
        "transactionStatus": tx.status,
        "auditStatus": "committed" if order.audit_record_id else "missing",
        "approvalStatus": execution_gate["approvalStatus"],
        "statusTransitionHistory": execution_gate["statusTransitionHistory"],
        "statusTransitionCount": execution_gate["statusTransitionCount"],
        "stateMachineConsistent": execution_gate["stateMachineConsistent"],
        "workflowInstance": execution_gate["workflowInstance"],
        "approvalHistory": execution_gate["approvalHistory"],
        "approvalTasks": [
            {
                "id": task.pk,
                "taskNo": task.task_no,
                "stepNo": task.step_no,
                "roleCode": task.required_role_code,
                "status": task.status,
                "version": task.version,
            }
            for task in approval_tasks
        ],
        "freezeStatus": execution_gate["freezeStatus"],
        "freezeHash": execution_gate["freezeHash"],
        "freezeSnapshot": execution_gate["freezeSnapshot"],
        "bankSendEligibility": bank_eligibility,
        "downstreamCounts": execution_gate["downstreamCounts"],
        "executionGateFacts": execution_gate,
        "sourceSnapshot": {
            "riskReviewVersion": source_snapshot.risk_review_version,
            "riskRuleVersion": source_snapshot.risk_rule_version,
            "sourceHash": source_snapshot.source_hash,
            "draftVersion": source_snapshot.draft_version,
            "eligibilityHash": source_snapshot.eligibility_hash,
        },
        "evidence": {
            "funds": evidence.funds_evidence,
            "bankInterface": evidence.bank_interface_evidence,
            "account": evidence.account_evidence,
            "riskReview": evidence.risk_review_evidence,
            "segregation": evidence.segregation_evidence,
            "evidenceHash": evidence.evidence_hash,
        },
        "preview": {
            "readonly": True,
            "signed": False,
            "sent": False,
            "executed": False,
        },
        "eligibility": {
            "eligible": bank_eligibility["readyForBankSend"],
            "nextStepReadiness": bank_eligibility["nextStepReadiness"],
            "blockingReasons": bank_eligibility["blockingReasons"],
            "serverDerived": True,
        },
        "businessActions": {
            "canSubmit": order.status == FormalPaymentOrder.Status.PREPARED,
            "canApprove": order.status == FormalPaymentOrder.Status.SUBMITTED,
            "canFreeze": order.status == FormalPaymentOrder.Status.APPROVED,
            "canSendBank": False,
        },
        "currentStateSource": "server",
    }


def recover_generation_result(idempotency_key):
    idem = BusinessActionIdempotency.objects.filter(
        action_code=GENERATE_ACTION,
        idempotency_key=idempotency_key,
    ).first()
    if not idem:
        raise ReconciliationError("FPO_RESULT_NOT_FOUND", "Generation result not found", 404)
    if idem.status != BusinessActionIdempotency.Status.COMMITTED or not idem.target_id:
        raise ReconciliationError("FPO_RESULT_NOT_COMMITTED", "Generation result is not committed", 409)
    return {
        "classification": "existing_result",
        "created": False,
        "data": serialize_order(FormalPaymentOrderRepository().get(idem.target_id)),
    }
