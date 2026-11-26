import uuid

from django.conf import settings
from django.db import IntegrityError, transaction

from formal_payment_order.facts import build_execution_gate_facts
from formal_payment_order.models import FormalPaymentOrder
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionTransaction,
    PurchaseReconciliation,
)
from reconciliation.services import ReconciliationError, canonical_hash
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.fact_loads import successful_fact_load_facts
from workflow_runtime.facts import (
    assert_status_transition_count_matches_history,
    status_transition_facts,
)
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.facts import BankSendPreparationFacts
from workflow_runtime.write_intents import build_write_intent_facts
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .models import BankMessagePreview, BankSendGate, BankSendPreparation
from .repositories import BankSendPreparationRepository


VERSION = "V1.14.2.8.4.7.58.1.4"
CANONICAL_NAME = "银行发送准备"
MODULE_CODE = "bank-send-preparation"
SOURCE_DOCUMENT_TYPE = "formalPaymentOrder"
PREPARE_ACTION = "prepare-bank-send-gate"
PREVIEW_ACTION = "generate-bank-message-preview"
OBJECT_TYPE = "bank_send_preparation"
ALLOWED_STATE_TRANSITIONS = (("draft", "prepared"),)


def downstream_counts(*, tenant_id=None, preparation_id=None):
    from bank_send_task.models import BankSendTask

    tasks = BankSendTask.objects.all()
    if tenant_id:
        tasks = tasks.filter(tenant_id=tenant_id)
    if preparation_id:
        tasks = tasks.filter(source_preparation_id=preparation_id)
    return {
        "bankSendTasks": tasks.count(),
        "bankMessages": 0,
        "paymentExecutions": 0,
        "fundsDebits": 0,
        "bankTransactions": 0,
        "paymentVouchers": 0,
        "writeoffs": 0,
        "ledgerEntries": 0,
        "postings": 0,
    }


def bank_send_preparation_facts_for_rows(
    rows,
    *,
    source_formal_payment_order_count,
    counts=None,
    api_url="/api/finance/bank-send-prepares/",
    tenant_id=None,
    batch_id=None,
    request=None,
):
    facts = BankSendPreparationFacts.from_serialized_rows(
        serialized_rows=rows,
        source_formal_payment_order_count=source_formal_payment_order_count,
        business_progress_counts=counts or downstream_counts(),
    ).as_dict()
    fact_load_facts = successful_fact_load_facts(
        result_count=facts["bankSendPreparationCount"],
        api_url=api_url,
        tenant_id=tenant_id,
        batch_id=batch_id,
        request=request,
    )
    return {
        **facts,
        **fact_load_facts,
        "factLoadFacts": fact_load_facts,
    }


def _safe_bank_interface(order):
    evidence = getattr(order, "evidence_snapshot", None)
    raw = evidence.bank_interface_evidence if evidence else {}
    return {
        "interfaceCode": str(
            raw.get("interfaceCode")
            or raw.get("interfaceId")
            or raw.get("profileId")
            or raw.get("code")
            or ""
        ),
        "active": bool(raw.get("active")),
        "paymentEnabled": bool(raw.get("paymentEnabled")),
        "connectionStatus": str(raw.get("connectionStatus") or ""),
    }


def evaluate_bank_send_gate(order):
    facts = build_execution_gate_facts(order).as_dict()
    eligibility = facts["bankSendEligibility"]
    interface = _safe_bank_interface(order)
    source_status_passed = order.status == FormalPaymentOrder.Status.FROZEN_FOR_EXECUTION
    approval_passed = bool(
        facts["approvalStatus"] == "approved"
        and eligibility["approvalPassed"]
    )
    freeze_hash_passed = bool(
        facts["freezeStatus"] == "frozen"
        and facts["freezeHash"]
        and eligibility["freezePassed"]
    )
    evaluated = {
        "sourceStatusPassed": source_status_passed,
        "approvalPassed": approval_passed,
        "freezeHashPassed": freeze_hash_passed,
        "riskReviewPassed": bool(eligibility["riskPassed"]),
        "fundsAvailable": bool(eligibility["fundsPassed"]),
        "bankInterfaceAvailable": bool(eligibility["bankPassed"]),
        "signingCapabilityReady": bool(eligibility["signaturePassed"]),
        "segregationValid": bool(eligibility["segregationPassed"]),
    }
    reason_codes = {
        "sourceStatusPassed": "FORMAL_PAYMENT_ORDER_NOT_FROZEN",
        "approvalPassed": "APPROVAL_NOT_APPROVED",
        "freezeHashPassed": "FREEZE_SNAPSHOT_HASH_MISMATCH",
        "riskReviewPassed": "RISK_REVIEW_NOT_PASSED",
        "fundsAvailable": "FUNDS_NOT_AVAILABLE",
        "bankInterfaceAvailable": "BANK_INTERFACE_NOT_AVAILABLE",
        "signingCapabilityReady": "SIGNING_CAPABILITY_NOT_READY",
        "segregationValid": "SEGREGATION_NOT_VALID",
    }
    blocking_reasons = [
        reason_codes[key] for key, passed in evaluated.items() if not passed
    ]
    payload = {
        **evaluated,
        "eligible": not blocking_reasons,
        "blockingReasons": blocking_reasons,
        "sourceFreezeHash": str(facts["freezeHash"] or ""),
        "currentFreezeHash": str(facts["freezeHash"] or ""),
        "bankInterface": interface,
        "serverDerived": True,
        "currentStateSource": "server",
        "bankSendCreated": False,
        "paymentExecuted": False,
    }
    return {
        **payload,
        "gateHash": canonical_hash(payload),
    }


def _reconciliation_for_order(order):
    reconciliation_id = (
        order.source_risk_review.source_payment_order_draft.source_reconciliation_id
    )
    return PurchaseReconciliation.objects.get(pk=reconciliation_id)


def _create_transaction(*, order, action_code, idempotency_key, request_hash):
    return BusinessActionTransaction.objects.create(
        transaction_id=f"BSP-TX-{uuid.uuid4().hex.upper()}",
        action_code=action_code,
        idempotency_key=idempotency_key,
        tenant_id=order.tenant_id,
        source_key=f"formalPaymentOrder:{order.pk}",
        command_id=f"BSP-CMD-{uuid.uuid4().hex.upper()}",
        transaction_plan_id="bank-send-preparation-v1",
        review_id=order.order_no,
        review_hash=request_hash,
        status=BusinessActionTransaction.Status.IN_PROGRESS,
        outcome="pending",
        commit_status="not_committed",
        recovery_status="not_required",
        reconciliation=_reconciliation_for_order(order),
    )


def _create_audit(
    *,
    transaction_row,
    action_code,
    idempotency_key,
    actor,
    order,
    target_type,
    target_id,
    target_no,
    evidence,
):
    return BusinessActionAuditRecord.objects.create(
        transaction=transaction_row,
        action_code=action_code,
        tenant_id=order.tenant_id,
        actor=actor,
        source_key=f"formalPaymentOrder:{order.pk}",
        reconciliation=transaction_row.reconciliation,
        result="committed",
        target_type=target_type,
        target_id=target_id,
        target_no=target_no,
        review_id=transaction_row.review_id,
        review_hash=transaction_row.review_hash,
        command_id=transaction_row.command_id,
        idempotency_key=idempotency_key,
        actor_name=actor.get_username(),
        tenant_or_scope=f"{order.tenant_id}:{order.legal_entity}",
        evidence_hash=canonical_hash(evidence),
        evidence=evidence,
    )


def _commit_action(
    *,
    transaction_row,
    idempotency_row,
    target_type,
    target_id,
    target_no,
    outcome,
):
    result_hash = canonical_hash(
        {
            "targetType": target_type,
            "targetId": target_id,
            "targetNo": target_no,
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
    idempotency_row.target_type = target_type
    idempotency_row.target_id = target_id
    idempotency_row.target_no = target_no
    idempotency_row.transaction_id = transaction_row.transaction_id
    idempotency_row.result_reference = f"{target_type}:{target_id}"
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


def _assert_feature_enabled(order):
    if not getattr(settings, "PCE_BANK_SEND_PREPARATION_FEATURE_ENABLED", False):
        raise ReconciliationError(
            "BSP_FEATURE_DISABLED",
            "Bank send preparation is disabled",
            403,
        )
    test_tenants = getattr(
        settings,
        "PCE_BANK_SEND_PREPARATION_TEST_TENANTS",
        set(),
    )
    if (
        order.tenant_id not in test_tenants
        and not getattr(
            settings,
            "PCE_BANK_SEND_PREPARATION_PRODUCTION_ROLLOUT_ENABLED",
            False,
        )
    ):
        raise ReconciliationError(
            "BSP_PRODUCTION_DISABLED",
            "Bank send preparation is limited to trusted test tenants",
            403,
        )


def create_bank_send_preparation(*, user, order, idempotency_key):
    _assert_feature_enabled(order)
    if not user or not user.is_authenticated:
        raise ReconciliationError("BSP_AUTH_REQUIRED", "Authentication required", 401)
    if not user.is_superuser:
        raise ReconciliationError(
            "BSP_INTERNAL_PREPARATION_ONLY",
            "Bank send preparation creation is an internal controlled operation",
            403,
        )
    existing = BankSendPreparationRepository().by_source(order.pk)
    if existing:
        return {
            "classification": "existing_result",
            "created": False,
            "data": serialize_preparation(existing),
        }
    gate = evaluate_bank_send_gate(order)
    if not gate["eligible"]:
        raise ReconciliationError(
            "BSP_GATE_BLOCKED",
            "Bank send preparation gate is blocked",
            409,
        )
    request_hash = canonical_hash(
        {
            "action": PREPARE_ACTION,
            "formalPaymentOrderId": order.pk,
            "formalPaymentOrderVersion": order.version,
            "freezeHash": gate["sourceFreezeHash"],
        }
    )
    prior = BusinessActionIdempotency.objects.filter(
        action_code=PREPARE_ACTION,
        idempotency_key=idempotency_key,
    ).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ReconciliationError(
                "BSP_IDEMPOTENCY_CONFLICT",
                "Idempotency payload conflict",
                409,
            )
        target = (
            BankSendPreparationRepository().get(prior.target_id)
            if prior.target_id
            else None
        )
        if target:
            return {
                "classification": "existing_result",
                "created": False,
                "data": serialize_preparation(target),
            }
        raise ReconciliationError(
            "BSP_ACTION_IN_PROGRESS",
            "Bank send preparation is in progress",
            409,
            True,
        )
    try:
        with transaction.atomic():
            current = FormalPaymentOrder.objects.select_for_update().get(pk=order.pk)
            fresh_gate = evaluate_bank_send_gate(current)
            if not fresh_gate["eligible"] or fresh_gate["gateHash"] != gate["gateHash"]:
                raise ReconciliationError(
                    "BSP_GATE_CHANGED",
                    "Bank send preparation gate changed during transaction",
                    409,
                )
            idempotency = BusinessActionIdempotency.objects.create(
                action_code=PREPARE_ACTION,
                idempotency_key=idempotency_key,
                tenant_id=current.tenant_id,
                source_key=f"formalPaymentOrder:{current.pk}",
                request_hash=request_hash,
                status=BusinessActionIdempotency.Status.IN_PROGRESS,
            )
            transaction_row = _create_transaction(
                order=current,
                action_code=PREPARE_ACTION,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            preparation = create_business_object_with_initial_state(
                model=BankSendPreparation,
                initial_state=BankSendPreparation.Status.DRAFT,
                prepare_no=f"BSP{current.order_no.removeprefix('FPO')}",
                source_document_type=SOURCE_DOCUMENT_TYPE,
                source_formal_payment_order=current,
                source_formal_payment_order_no=current.order_no,
                source_formal_payment_order_version=current.version,
                source_freeze_hash=fresh_gate["sourceFreezeHash"],
                tenant_id=current.tenant_id,
                company_id=current.company_id,
                legal_entity_id=(
                    current.source_risk_review
                    .source_payment_order_draft
                    .legal_entity_id
                ),
                supplier_id=current.supplier_id,
                supplier_name=current.supplier_name,
                currency=current.currency,
                amount=current.amount,
                planned_execution_date=current.planned_execution_date,
                gate_hash=fresh_gate["gateHash"],
                created_by=user,
            )
            BankSendGate.objects.create(
                preparation=preparation,
                source_status_passed=fresh_gate["sourceStatusPassed"],
                approval_passed=fresh_gate["approvalPassed"],
                freeze_hash_passed=fresh_gate["freezeHashPassed"],
                risk_review_passed=fresh_gate["riskReviewPassed"],
                funds_available=fresh_gate["fundsAvailable"],
                bank_interface_available=fresh_gate["bankInterfaceAvailable"],
                signing_capability_ready=fresh_gate["signingCapabilityReady"],
                segregation_valid=fresh_gate["segregationValid"],
                eligible=fresh_gate["eligible"],
                blocking_reasons=fresh_gate["blockingReasons"],
                source_freeze_hash=fresh_gate["sourceFreezeHash"],
                current_freeze_hash=fresh_gate["currentFreezeHash"],
                bank_interface_code=fresh_gate["bankInterface"]["interfaceCode"],
                bank_interface_status=fresh_gate["bankInterface"]["connectionStatus"],
                gate_hash=fresh_gate["gateHash"],
            )
            audit = _create_audit(
                transaction_row=transaction_row,
                action_code=PREPARE_ACTION,
                idempotency_key=idempotency_key,
                actor=user,
                order=current,
                target_type="bankSendPreparation",
                target_id=preparation.pk,
                target_no=preparation.prepare_no,
                evidence={
                    "version": VERSION,
                    "gateHash": fresh_gate["gateHash"],
                    "sourceFreezeHash": fresh_gate["sourceFreezeHash"],
                    "stateTransition": "draft->prepared",
                    "bankMessageCreated": False,
                    "bankSendTaskCreated": False,
                    "paymentExecuted": False,
                },
            )
            transition_business_object(
                business_object=preparation,
                object_type=OBJECT_TYPE,
                source_state=BankSendPreparation.Status.DRAFT,
                target_state=BankSendPreparation.Status.PREPARED,
                action_code=PREPARE_ACTION,
                operator=user,
                reason="bank_send_gate_validated",
                audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
            preparation.audit_record = audit
            preparation.save(update_fields=["audit_record", "updated_at"])
            _commit_action(
                transaction_row=transaction_row,
                idempotency_row=idempotency,
                target_type="bankSendPreparation",
                target_id=preparation.pk,
                target_no=preparation.prepare_no,
                outcome="prepared",
            )
        return {
            "classification": "created",
            "created": True,
            "data": serialize_preparation(
                BankSendPreparationRepository().get(preparation.pk)
            ),
        }
    except IntegrityError:
        existing = BankSendPreparationRepository().by_source(order.pk)
        if existing:
            return {
                "classification": "existing_result",
                "created": False,
                "data": serialize_preparation(existing),
            }
        raise


def _preview_payload(preparation, gate):
    order = preparation.source_formal_payment_order
    freeze = order.execution_freeze
    return {
        "messagePurpose": "bank_send_preview_only",
        "formalPaymentOrderNo": order.order_no,
        "bankSendPreparationNo": preparation.prepare_no,
        "amount": str(preparation.amount),
        "currency": preparation.currency,
        "plannedExecutionDate": preparation.planned_execution_date.isoformat(),
        "payerAccountMasked": (
            f"***{freeze.payer_account_id[-4:]}" if freeze.payer_account_id else ""
        ),
        "payeeAccountMasked": (
            f"***{freeze.payee_account_id[-4:]}" if freeze.payee_account_id else ""
        ),
        "bankRoute": freeze.bank_route,
        "bankInterfaceCode": gate.bank_interface_code,
        "freezeHash": preparation.source_freeze_hash,
        "signed": False,
        "sent": False,
        "executed": False,
    }


def generate_bank_message_preview(
    *,
    user,
    preparation,
    idempotency_key,
    expected_version,
    explicit_user_action,
):
    if explicit_user_action is not True:
        raise ReconciliationError(
            "BSP_EXPLICIT_ACTION_REQUIRED",
            "Explicit user action is required",
            400,
        )
    order = preparation.source_formal_payment_order
    _assert_feature_enabled(order)
    decision = ActionPermissionValidator().evaluate(
        user=user,
        module_code=MODULE_CODE,
        action_code=PREVIEW_ACTION,
        object_ids=[preparation.pk],
        selection_count=1,
    )
    if not decision["granted"]:
        raise ReconciliationError(
            "BSP_PERMISSION_DENIED",
            decision["reason"],
            403,
        )
    existing_preview = getattr(preparation, "message_preview", None)
    if existing_preview:
        return {
            "classification": "existing_result",
            "created": False,
            "data": serialize_preparation(
                BankSendPreparationRepository().get(preparation.pk)
            ),
        }
    request_hash = canonical_hash(
        {
            "action": PREVIEW_ACTION,
            "preparationId": preparation.pk,
            "expectedVersion": expected_version,
            "gateHash": preparation.gate_hash,
        }
    )
    prior = BusinessActionIdempotency.objects.filter(
        action_code=PREVIEW_ACTION,
        idempotency_key=idempotency_key,
    ).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ReconciliationError(
                "BSP_IDEMPOTENCY_CONFLICT",
                "Idempotency payload conflict",
                409,
            )
        target = (
            BankSendPreparationRepository().get(preparation.pk)
            if prior.target_id
            else None
        )
        if target and getattr(target, "message_preview", None):
            return {
                "classification": "existing_result",
                "created": False,
                "data": serialize_preparation(target),
            }
    with transaction.atomic():
        current = (
            BankSendPreparationRepository()
            .queryset()
            .select_for_update()
            .get(pk=preparation.pk)
        )
        if current.status != BankSendPreparation.Status.PREPARED:
            raise ReconciliationError(
                "BSP_STATUS_INVALID",
                "Only prepared bank send preparations can generate previews",
                409,
            )
        if current.version != expected_version:
            raise ReconciliationError(
                "BSP_VERSION_CONFLICT",
                "Bank send preparation version conflict",
                409,
            )
        fresh_gate = evaluate_bank_send_gate(current.source_formal_payment_order)
        if (
            not fresh_gate["eligible"]
            or fresh_gate["gateHash"] != current.gate_hash
            or fresh_gate["sourceFreezeHash"] != current.source_freeze_hash
        ):
            raise ReconciliationError(
                "BSP_GATE_CHANGED",
                "Bank send gate is no longer valid",
                409,
            )
        existing_preview = getattr(current, "message_preview", None)
        if existing_preview:
            return {
                "classification": "existing_result",
                "created": False,
                "data": serialize_preparation(current),
            }
        idempotency = BusinessActionIdempotency.objects.create(
            action_code=PREVIEW_ACTION,
            idempotency_key=idempotency_key,
            tenant_id=current.tenant_id,
            source_key=f"bankSendPreparation:{current.pk}",
            request_hash=request_hash,
            status=BusinessActionIdempotency.Status.IN_PROGRESS,
        )
        transaction_row = _create_transaction(
            order=current.source_formal_payment_order,
            action_code=PREVIEW_ACTION,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        payload = _preview_payload(current, current.send_gate)
        preview = BankMessagePreview.objects.create(
            preparation=current,
            preview_no=f"BMP-{current.prepare_no}",
            status=BankMessagePreview.Status.PREVIEW_ONLY,
            message_type="payment_instruction_preview",
            sanitized_payload=payload,
            payload_hash=canonical_hash(payload),
            created_by=user,
        )
        audit = _create_audit(
            transaction_row=transaction_row,
            action_code=PREVIEW_ACTION,
            idempotency_key=idempotency_key,
            actor=user,
            order=current.source_formal_payment_order,
            target_type="bankMessagePreview",
            target_id=preview.pk,
            target_no=preview.preview_no,
            evidence={
                "version": VERSION,
                "previewStatus": "preview_only",
                "payloadHash": preview.payload_hash,
                "bankSecretExposed": False,
                "bankMessageSent": False,
                "paymentExecuted": False,
            },
        )
        preview.audit_record = audit
        preview._audit_binding_authorized = True
        try:
            preview.save(update_fields=["audit_record"])
        finally:
            preview._audit_binding_authorized = False
        _commit_action(
            transaction_row=transaction_row,
            idempotency_row=idempotency,
            target_type="bankMessagePreview",
            target_id=preview.pk,
            target_no=preview.preview_no,
            outcome="preview_only",
        )
    return {
        "classification": "created",
        "created": True,
        "data": serialize_preparation(
            BankSendPreparationRepository().get(preparation.pk)
        ),
    }


def _transition_history(preparation):
    rows = (
        BusinessStateTransition.objects.filter(
            object_type=OBJECT_TYPE,
            object_id=preparation.pk,
        )
        .select_related("operator")
        .order_by("version", "timestamp")
    )
    return [
        {
            "sourceState": row.source_state,
            "targetState": row.target_state,
            "actionCode": row.action_code,
            "operator": row.operator.get_username(),
            "timestamp": row.timestamp.isoformat(),
            "reason": row.reason,
            "version": row.version,
            "auditReference": row.audit_reference,
        }
        for row in rows
    ]


def serialize_gate(gate):
    return {
        "sourceStatusPassed": gate.source_status_passed,
        "approvalPassed": gate.approval_passed,
        "freezeHashPassed": gate.freeze_hash_passed,
        "riskReviewPassed": gate.risk_review_passed,
        "fundsAvailable": gate.funds_available,
        "bankInterfaceAvailable": gate.bank_interface_available,
        "signingCapabilityReady": gate.signing_capability_ready,
        "segregationValid": gate.segregation_valid,
        "eligible": gate.eligible,
        "blockingReasons": list(gate.blocking_reasons),
        "sourceFreezeHash": gate.source_freeze_hash,
        "currentFreezeHash": gate.current_freeze_hash,
        "bankInterface": {
            "interfaceCode": gate.bank_interface_code,
            "connectionStatus": gate.bank_interface_status,
            "secretExposed": False,
        },
        "gateHash": gate.gate_hash,
        "evaluatedAt": gate.evaluated_at.isoformat(),
        "serverDerived": True,
        "currentStateSource": "server",
    }


def serialize_preview(preview):
    if not preview:
        return {
            "exists": False,
            "status": "not_generated",
            "readonly": True,
            "sent": False,
            "bankSecretExposed": False,
        }
    return {
        "exists": True,
        "id": preview.pk,
        "previewNo": preview.preview_no,
        "status": preview.status,
        "messageType": preview.message_type,
        "payload": dict(preview.sanitized_payload),
        "payloadHash": preview.payload_hash,
        "readonly": True,
        "sent": False,
        "bankSecretExposed": False,
        "auditStatus": "committed" if preview.audit_record_id else "missing",
        "createdAt": preview.created_at.isoformat(),
    }


def serialize_preparation(preparation):
    history = _transition_history(preparation)
    state_machine_consistent = bool(
        preparation.status == "prepared"
        and len(history) == 1
        and history[0]["sourceState"] == "draft"
        and history[0]["targetState"] == "prepared"
        and history[0]["actionCode"] == PREPARE_ACTION
        and history[0]["auditReference"].startswith(
            "BusinessActionAuditRecord:"
        )
    )
    transition_facts = status_transition_facts(
        history=history,
        state_machine_consistent=state_machine_consistent,
    )
    preview = getattr(preparation, "message_preview", None)
    serialized_preview = serialize_preview(preview)
    payload = {
        "id": preparation.pk,
        "prepareNo": preparation.prepare_no,
        "sourceDocumentType": preparation.source_document_type,
        "sourceFormalPaymentOrderId": preparation.source_formal_payment_order_id,
        "sourceFormalPaymentOrderNo": preparation.source_formal_payment_order_no,
        "sourceFormalPaymentOrderVersion": preparation.source_formal_payment_order_version,
        "sourceFreezeHash": preparation.source_freeze_hash,
        "tenantId": preparation.tenant_id,
        "companyId": preparation.company_id,
        "legalEntityId": preparation.legal_entity_id,
        "supplierId": preparation.supplier_id,
        "supplierName": preparation.supplier_name,
        "currency": preparation.currency,
        "amount": str(preparation.amount),
        "plannedExecutionDate": preparation.planned_execution_date.isoformat(),
        "status": preparation.status,
        "version": preparation.version,
        **transition_facts,
        "gate": serialize_gate(preparation.send_gate),
        "eligibility": {
            "eligible": preparation.send_gate.eligible,
            "nextStepReadiness": (
                "ready_for_bank_send_task"
                if preview is not None
                and preparation.send_gate.eligible
                and not hasattr(preparation, "send_task")
                else "ready_for_bank_message_preview"
                if preparation.send_gate.eligible and preview is None
                else "existing_bank_send_task"
                if hasattr(preparation, "send_task")
                else "blocked"
            ),
            "blockingReasons": list(preparation.send_gate.blocking_reasons),
            "serverDerived": True,
        },
        "bankInterface": {
            "interfaceCode": preparation.send_gate.bank_interface_code,
            "connectionStatus": preparation.send_gate.bank_interface_status,
            "secretExposed": False,
        },
        "messagePreview": serialized_preview,
        "auditStatus": "committed" if preparation.audit_record_id else "missing",
        "businessActions": {
            "canViewEligibility": True,
            "canViewGate": True,
            "canGeneratePreview": (
                preparation.status == "prepared"
                and preparation.send_gate.eligible
                and preview is None
            ),
            "canCreateBankSendTask": (
                preparation.status == "prepared"
                and preparation.send_gate.eligible
                and preview is not None
                and not hasattr(preparation, "send_task")
            ),
            "canSendBank": False,
            "canExecutePayment": False,
        },
        "downstreamCounts": downstream_counts(
            preparation_id=preparation.pk,
        ),
        "currentStateSource": "server",
    }
    payload["writeIntentFacts"] = build_write_intent_facts(
        preview_preparation_write_count=(
            1 if serialized_preview["exists"] else 0
        ),
        audit_write_count=(
            (1 if payload["auditStatus"] == "committed" else 0)
            + (
                1
                if serialized_preview.get("auditStatus") == "committed"
                else 0
            )
        ),
        business_progress_counts=payload["downstreamCounts"],
        preview_only_enforced=(
            (
                serialized_preview["exists"] is not True
                or serialized_preview["status"] == "preview_only"
            )
            and serialized_preview["sent"] is False
            and serialized_preview["bankSecretExposed"] is False
        ),
    )
    return assert_status_transition_count_matches_history(payload)


__all__ = [
    "CANONICAL_NAME",
    "MODULE_CODE",
    "SOURCE_DOCUMENT_TYPE",
    "VERSION",
    "create_bank_send_preparation",
    "downstream_counts",
    "evaluate_bank_send_gate",
    "generate_bank_message_preview",
    "serialize_preparation",
    "bank_send_preparation_facts_for_rows",
]
