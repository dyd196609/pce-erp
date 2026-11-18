import uuid
from datetime import date, time
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from payment_order_prepare.models import PaymentOrderPrepare
from payment_order_prepare.services import eligibility as order_eligibility
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionSourceLock,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
    BusinessDocumentNumberSequence,
)
from reconciliation.services import ReconciliationError, canonical_hash
from workflow_runtime.facts import business_state_transition_facts
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .models import (
    PaymentOrderDraft,
    PaymentOrderDraftAuthoritySnapshot,
    PaymentOrderDraftDataSnapshot,
    PaymentOrderDraftCreationPreview,
    PaymentOrderDraftSourceRelation,
    PaymentOrderDraftSourceSnapshot,
    PaymentOrderDraftReviewExecution,
    PaymentOrderDraftReviewIssue,
)
from .providers import evidence_dict, read_order_authorities


VERSION = "V1.14.2.8.4.7.55"
CANONICAL_NAME = "正式付款单草稿"
SOURCE_DOCUMENT_TYPE = "paymentOrderPrepare"
DOCUMENT_TYPE = "payment_order_draft"
GENERATE_ACTION = "GENERATE_PAYMENT_ORDER_DRAFT"
SAVE_ACTION = "SAVE_PAYMENT_ORDER_DRAFT_DATA"
REVIEW_ACTION = "REVIEW_PAYMENT_ORDER_DRAFT"
NEXT_MODULE_CODE = "payment-risk-review"
NEXT_CANONICAL_NAME = "真实付款风险评审"
NEXT_ROUTE = "/finance/payment-risk-reviews"
NUMBER_POLICY_VERSION = "payment-order-draft-sequence-v1"
REVIEW_POLICY_VERSION = "payment-order-draft-review-v1"
TRANSACTION_PLAN_ID = "payment-order-draft-atomic-v1"
ALLOWED_STATE_TRANSITIONS = (("created", "reviewed"),)
EXPECTED_STATE_TRANSITIONS = {
    "created": (),
    "reviewed": (("created", "reviewed", REVIEW_ACTION),),
}
RULE_CODES = (
    "POD_GATE_SOURCE_EXISTS",
    "POD_GATE_SOURCE_TYPE_VALID",
    "POD_GATE_ORDER_PREPARE_PREPARED",
    "POD_GATE_ORDER_DATA_COMPLETE",
    "POD_GATE_ORDER_PREPARE_VALIDATED",
    "POD_GATE_PAYMENT_REQUEST_APPROVED",
    "POD_GATE_APPROVAL_EVIDENCE_COMPLETE",
    "POD_GATE_SOURCE_VERSIONS_CURRENT",
    "POD_GATE_NO_EXISTING_TARGET",
    "POD_GATE_NO_PAYMENT_HOLD",
    "POD_GATE_AUDIT_COMPLETE",
    "POD_DATA_PAYMENT_REFERENCE_REQUIRED",
    "POD_DATA_PAYMENT_PURPOSE_REQUIRED",
    "POD_DATA_DRAFT_PAYLOAD_COMPLETE",
    "POD_REVIEW_PAYER_ACCOUNT_ACTIVE",
    "POD_REVIEW_PAYEE_ACCOUNT_ACTIVE",
    "POD_REVIEW_ACCOUNT_OWNER",
    "POD_REVIEW_CURRENCY",
    "POD_REVIEW_AMOUNT",
    "POD_REVIEW_EXECUTION_DATE",
    "POD_REVIEW_PAYMENT_ROUTE",
    "POD_REVIEW_BANK_INTERFACE",
    "POD_REVIEW_BANK_BUSINESS_DAY",
    "POD_REVIEW_CUTOFF_TIME",
    "POD_REVIEW_SINGLE_LIMIT",
    "POD_REVIEW_DAILY_LIMIT",
    "POD_REVIEW_PAYMENT_HOLD",
    "POD_REVIEW_DUPLICATE_PAYMENT_RISK",
    "POD_REVIEW_AVAILABLE_BALANCE",
    "POD_REVIEW_FUNDS_AUTHORITY",
    "POD_REVIEW_SIGNING_POLICY",
    "POD_REVIEW_AUTHORIZATION_ROUTE",
    "POD_REVIEW_SIGNING_CAPABILITY",
    "POD_REVIEW_SIGNING_CREDENTIAL",
    "POD_REVIEW_MAKER_CHECKER_SEGREGATION",
    "POD_REVIEW_SOURCE_CURRENT",
    "POD_REVIEW_DRAFT_PAYLOAD_INTEGRITY",
    "POD_REVIEW_SOURCE_PREVIEW_INTEGRITY",
    "POD_REVIEW_CREATION_PREVIEW_INTEGRITY",
    "POD_REVIEW_NO_FATAL_ISSUE",
    "POD_REVIEW_NEXT_MODULE_READINESS",
)


def _decimal(value, field):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReconciliationError("POD_AMOUNT_INVALID", f"{field} is invalid", 400) from exc


def _date(value, field):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ReconciliationError("POD_DATE_INVALID", f"{field} must be YYYY-MM-DD", 400) from exc


def _time(value, field):
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ReconciliationError("POD_TIME_INVALID", f"{field} must be HH:MM", 400) from exc


def _explicit(value):
    if value is not True:
        raise ReconciliationError(
            "POD_EXPLICIT_USER_ACTION_REQUIRED", "Explicit user action required", 400
        )


def _authorize(user, source, permission):
    if not user or not user.is_authenticated:
        raise ReconciliationError("POD_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not (user.is_superuser or user.has_perm(permission)):
        raise ReconciliationError("POD_AUTH_PERMISSION_DENIED", "Permission denied", 403)
    if not user.is_superuser and user.company_id != source.company_id:
        raise ReconciliationError("POD_AUTH_SCOPE_DENIED", "Scope denied", 403)
    if not settings.PCE_PAYMENT_ORDER_DRAFT_FEATURE_ENABLED:
        raise ReconciliationError("POD_AUTH_FEATURE_DISABLED", "Feature disabled", 403)
    if (
        source.tenant_id not in settings.PCE_PAYMENT_ORDER_DRAFT_TEST_TENANTS
        and not settings.PCE_PAYMENT_ORDER_DRAFT_PRODUCTION_ROLLOUT_ENABLED
    ):
        raise ReconciliationError(
            "POD_AUTH_PRODUCTION_ROLLOUT_DISABLED", "Production rollout disabled", 403
        )


def _inject(step, requested):
    if step != requested:
        return
    if not settings.PCE_PAYMENT_ORDER_DRAFT_FAILURE_INJECTION_ENABLED:
        raise ReconciliationError("POD_FAILURE_INJECTION_DISABLED", "Injection disabled", 403)
    if step == "before_response":
        raise ReconciliationError(
            "POD_COMMIT_UNKNOWN", "Committed result must be recovered by idempotency", 503, True
        )
    raise ReconciliationError(f"POD_INJECTED_{step.upper()}", f"Injected at {step}", 503, True)


def _source_reconciliation(source):
    return (
        source.source_payment_instruction_prepare.source_payment_request
        .source_payment_request_prepare
        .source_payable_confirmation_prepare
        .source_purchase_accounts_payable_draft
        .source_purchase_reconciliation
    )


def _source_snapshot_parts(source):
    data = source.order_data_snapshots.order_by("-order_data_version").first()
    review = source.validation_executions.order_by("-pk").first()
    preview = data.previews.order_by("-preview_version").first() if data else None
    return data, review, preview


def source_hash(source):
    data, review, preview = _source_snapshot_parts(source)
    return canonical_hash({
        "id": source.pk,
        "prepareNo": source.prepare_no,
        "version": source.version,
        "status": source.status,
        "orderDataStatus": source.order_data_status,
        "validationStatus": source.validation_status,
        "validationResultCode": source.validation_result_code,
        "validationIssueCount": source.validation_issue_count,
        "orderDataVersion": source.current_order_data_version,
        "validationVersion": source.current_validation_version,
        "orderDataHash": data.data_hash if data else "",
        "validationHash": review.result_hash if review else "",
        "previewHash": preview.preview_hash if preview else "",
        "paymentAmount": str(source.payment_amount),
        "currency": source.currency,
    })


def source_gate(source, check_existing=True):
    reasons = []
    data, review, preview = _source_snapshot_parts(source)
    if source.status != "submitted":
        reasons.append("SOURCE_NOT_PREPARED")
    if source.order_data_status != "complete":
        reasons.append("SOURCE_VALIDATION_FAILED")
    if (
        source.validation_status != "passed"
        or source.validation_result_code != "validated"
        or source.validation_issue_count != 0
    ):
        reasons.append("SOURCE_VALIDATION_FAILED")
    if not data or not review or not preview:
        reasons.append("SOURCE_STALE")
    if source.payment_amount <= 0:
        reasons.append("AMOUNT_MISMATCH")
    eligibility = order_eligibility(source)
    if not eligibility["eligible"]:
        reasons.append("SOURCE_STALE")
    request = source.source_payment_instruction_prepare.source_payment_request
    if (
        request.status != "approved"
        or request.approval_status != "approved"
        or request.approval_result_code != "approved"
        or not request.workflow_instance_id
    ):
        reasons.append("APPROVAL_EVIDENCE_INCOMPLETE")
    if check_existing and PaymentOrderDraft.objects.filter(
        source_payment_order_prepare=source
    ).exists():
        reasons.append("EXISTING_TARGET")
    return list(dict.fromkeys(reasons))


def _register(action, key, source_key, request_hash, tenant_id):
    existing = BusinessActionIdempotency.objects.filter(
        action_code=action, idempotency_key=key
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise ReconciliationError("POD_IDEMPOTENCY_PAYLOAD_CONFLICT", "Payload conflict", 409)
        if existing.status == "committed" and existing.target_id:
            return existing, True
        raise ReconciliationError("POD_IN_PROGRESS", "Action is in progress", 409, True)
    return BusinessActionIdempotency.objects.create(
        action_code=action,
        idempotency_key=key,
        tenant_id=tenant_id,
        source_key=source_key,
        request_hash=request_hash,
        status="in_progress",
    ), False


def _lock(source_key, transaction_id):
    row, created = BusinessActionSourceLock.objects.get_or_create(
        lock_key=f"payment-order-draft:{source_key}",
        defaults={"owner_transaction_id": transaction_id, "state": "acquired"},
    )
    if not created and row.state == "acquired" and row.owner_transaction_id != transaction_id:
        raise ReconciliationError("POD_SOURCE_LOCKED", "Source is locked", 409, True)
    row.owner_transaction_id = transaction_id
    row.state = "acquired"
    row.released_at = None
    row.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
    return row


def _transaction(action, key, source, source_key, request_hash):
    return BusinessActionTransaction.objects.create(
        transaction_id=f"POD-TX-{uuid.uuid4().hex[:24]}",
        action_code=action,
        idempotency_key=key,
        tenant_id=source.tenant_id,
        source_key=source_key,
        command_id=f"POD-CMD-{uuid.uuid4().hex[:20]}",
        transaction_plan_id=TRANSACTION_PLAN_ID,
        review_id=f"POD-REVIEW-{source.pk}",
        review_hash=request_hash,
        status="in_progress",
        outcome="pending",
        commit_status="not_committed",
        recovery_status="not_required",
    )


def _audit(tx, action, key, user, source, target, evidence):
    return BusinessActionAuditRecord.objects.create(
        transaction=tx,
        action_code=action,
        tenant_id=source.tenant_id,
        actor=user,
        source_key=target.source_key,
        reconciliation=_source_reconciliation(source),
        result="committed",
        target_type="paymentOrderDraft",
        target_id=target.pk,
        target_no=target.draft_no,
        review_id=tx.review_id,
        review_hash=tx.review_hash,
        command_id=tx.command_id,
        idempotency_key=key,
        actor_name=getattr(user, "username", str(user.pk)),
        tenant_or_scope=source.tenant_id,
        evidence_hash=canonical_hash(evidence),
        evidence=evidence,
    )


def _commit(tx, idem, target, classification):
    result_hash = canonical_hash({
        "id": target.pk,
        "draftNo": target.draft_no,
        "version": target.version,
        "status": target.status,
        "classification": classification,
    })
    tx.status = "committed"
    tx.outcome = "success"
    tx.commit_status = "committed"
    tx.result_hash = result_hash
    tx.save()
    idem.status = "committed"
    idem.target_type = "paymentOrderDraft"
    idem.target_id = target.pk
    idem.target_no = target.draft_no
    idem.transaction_id = tx.transaction_id
    idem.result_reference = f"paymentOrderDraft:{target.pk}"
    idem.save()


def _release(lock):
    lock.state = "released"
    lock.released_at = timezone.now()
    lock.save(update_fields=["state", "released_at", "acquired_at"])


def _reserve_number(source, key):
    period = source.planned_execution_date.strftime("%Y-%m")
    scope = f"{DOCUMENT_TYPE}:{source.legal_entity_id}:{source.ledger_book_id}:{period}"
    sequence, _ = BusinessDocumentNumberSequence.objects.get_or_create(number_scope=scope)
    sequence.current_value += 1
    number = f"POD{period.replace('-', '')}{sequence.current_value:08d}"
    while BusinessDocumentNumberReservation.objects.filter(reserved_number=number).exists():
        sequence.current_value += 1
        number = f"POD{period.replace('-', '')}{sequence.current_value:08d}"
    sequence.save(update_fields=["current_value", "updated_at"])
    return BusinessDocumentNumberReservation.objects.create(
        document_type=DOCUMENT_TYPE,
        number_policy_version=NUMBER_POLICY_VERSION,
        number_scope=scope,
        legal_entity_id=source.legal_entity_id,
        ledger_book_id=source.ledger_book_id,
        reserved_number=number,
        tenant_id=source.tenant_id,
        accounting_period=period,
        idempotency_key=key,
        status="reserved",
        target=_source_reconciliation(source),
        reusable=False,
    )


def generate_payment_order_draft(
    *, user, source, idempotency_key, expected_source_version,
    explicit_user_action, failure_step=""
):
    _explicit(explicit_user_action)
    _authorize(user, source, "payment_order_draft.generate_payment_order_draft")
    _inject("after_authorization", failure_step)
    if not idempotency_key:
        raise ReconciliationError("POD_IDEMPOTENCY_KEY_REQUIRED", "Idempotency key required", 400)
    request_hash = canonical_hash({
        "sourceId": source.pk,
        "expectedSourceVersion": expected_source_version,
        "action": GENERATE_ACTION,
    })
    with transaction.atomic():
        idem, replay = _register(
            GENERATE_ACTION,
            idempotency_key,
            f"paymentOrderPrepare:{source.pk}",
            request_hash,
            source.tenant_id,
        )
        if replay:
            return {
                "classification": "existing_result",
                "created": False,
                "data": serialize_draft(PaymentOrderDraft.objects.get(pk=idem.target_id)),
            }
        tx = _transaction(
            GENERATE_ACTION,
            idempotency_key,
            source,
            f"paymentOrderPrepare:{source.pk}",
            request_hash,
        )
        _inject("after_idempotency_registration", failure_step)
        lock = _lock(f"paymentOrderPrepare:{source.pk}", tx.transaction_id)
        current = (
            PaymentOrderPrepare.objects.select_for_update()
            .select_related(
                "source_payment_instruction_prepare__source_payment_request__workflow_instance",
                "source_snapshot",
            )
            .get(pk=source.pk)
        )
        _inject("after_source_reload", failure_step)
        if current.version != expected_source_version:
            raise ReconciliationError("VERSION_CONFLICT", "Source version conflict", 409)
        reasons = source_gate(current)
        if reasons:
            raise ReconciliationError(f"POD_{reasons[0]}", ",".join(reasons), 409)
        source_data, source_review, source_preview = _source_snapshot_parts(current)
        request = current.source_payment_instruction_prepare.source_payment_request
        request_submission = request.submission_snapshots.order_by(
            "-submission_version"
        ).first()
        reservation = _reserve_number(current, idempotency_key)
        _inject("after_number_reservation", failure_step)
        target = create_business_object_with_initial_state(
            model=PaymentOrderDraft,
            initial_state="created",
            draft_no=reservation.reserved_number,
            source_payment_order_prepare=current,
            source_payment_order_prepare_no=current.prepare_no,
            source_order_prepare_version=current.version,
            source_order_data_version=current.current_order_data_version,
            source_order_validation_version=current.current_validation_version,
            source_order_preview_hash=source_preview.preview_hash,
            source_payment_request_id=current.source_payment_request_id,
            source_payment_request_no=current.source_payment_request_no,
            source_payment_request_version=current.source_payment_request_version,
            source_approval_workflow_id=current.source_approval_workflow_id,
            source_approval_evidence_hash=current.source_approval_evidence_hash,
            source_payment_request_prepare_id=current.source_payment_request_prepare_id,
            source_payable_confirmation_prepare_id=current.source_payable_confirmation_prepare_id,
            source_ap_draft_id=current.source_ap_draft_id,
            source_invoice_prepare_id=current.source_invoice_prepare_id,
            source_reconciliation_id=current.source_reconciliation_id,
            source_key=f"paymentOrderPrepare:{current.pk}",
            tenant_id=current.tenant_id,
            company_id=current.company_id,
            supplier_id=current.supplier_id,
            supplier_name=current.supplier_name,
            legal_entity_id=current.legal_entity_id,
            legal_entity_name=current.legal_entity_name,
            ledger_book_id=current.ledger_book_id,
            currency=current.currency,
            payment_amount=current.payment_amount,
            planned_execution_date=current.planned_execution_date,
            planned_execution_time=source_data.planned_execution_time,
            payment_method_code=current.payment_method_code,
            payer_bank_account_id=current.payer_bank_account_id,
            payee_bank_account_id=current.payee_bank_account_id,
            payment_route_id=current.payment_route_id,
            bank_interface_profile_id=current.bank_interface_profile_id,
            priority=current.priority,
            idempotency_key=idempotency_key,
            number_reservation=reservation,
            business_transaction=tx,
            created_by=user,
        )
        _inject("after_target_insert", failure_step)
        PaymentOrderDraftSourceSnapshot.objects.create(
            payment_order_draft=target,
            source_payment_order_prepare_id=current.pk,
            source_payment_order_prepare_no=current.prepare_no,
            source_order_prepare_version=current.version,
            source_order_data_snapshot_id=source_data.pk,
            source_order_data_version=source_data.order_data_version,
            source_order_validation_execution_id=source_review.pk,
            source_order_validation_version=current.current_validation_version,
            source_order_preview_hash=source_preview.preview_hash,
            source_payment_request_id=request.pk,
            source_payment_request_version=request.version,
            source_submission_snapshot_id=(
                request_submission.pk if request_submission else 0
            ),
            source_approval_workflow_id=request.workflow_instance_id,
            source_approval_evidence_hash=current.source_approval_evidence_hash,
            source_order_prepare_hash=source_hash(current),
            source_validation_hash=source_review.result_hash,
            source_eligibility_hash=canonical_hash(order_eligibility(current)),
        )
        PaymentOrderDraftSourceRelation.objects.create(
            payment_order_draft=target,
            source_id=current.pk,
            source_no=current.prepare_no,
            source_version=current.version,
            source_hash=source_hash(current),
        )
        _inject("after_source_snapshot", failure_step)
        audit = _audit(tx, GENERATE_ACTION, idempotency_key, user, current, target, {
            "version": VERSION,
            "sourceType": SOURCE_DOCUMENT_TYPE,
            "sourceNo": current.prepare_no,
            "sourceHash": source_hash(current),
            "formalPaymentOrderCreated": False,
        })
        target.audit_record = audit
        target.save(update_fields=["audit_record", "updated_at"])
        reservation.status = "consumed"
        reservation.consumed_at = timezone.now()
        reservation.save(update_fields=["status", "consumed_at"])
        _commit(tx, idem, target, "created")
        _release(lock)
        _inject("before_database_commit", failure_step)
    _inject("before_response", failure_step)
    return {"classification": "created", "created": True, "data": serialize_draft(target)}


def save_draft_data(
    *, user, obj, payload, idempotency_key, expected_version,
    expected_draft_data_version, expected_payment_order_prepare_version,
    explicit_user_action, failure_step=""
):
    _explicit(explicit_user_action)
    _authorize(user, obj.source_payment_order_prepare, "payment_order_draft.edit_payment_order_draft_data")
    if obj.status == "reviewed":
        raise ReconciliationError(
            "PAYMENT_ORDER_DRAFT_REVIEWED_IMMUTABLE",
            "Reviewed payment order draft is immutable",
            409,
        )
    planned_date = _date(payload.get("plannedExecutionDate"), "plannedExecutionDate")
    planned_time = _time(payload.get("plannedExecutionTime"), "plannedExecutionTime")
    request_hash = canonical_hash({
        "id": obj.pk,
        "version": expected_version,
        "draftDataVersion": expected_draft_data_version,
        "paymentOrderPrepareVersion": expected_payment_order_prepare_version,
        "plannedExecutionDate": planned_date.isoformat(),
        "plannedExecutionTime": planned_time.isoformat(),
        "priority": payload.get("priority", "normal"),
        "paymentPurpose": payload.get("paymentPurpose", ""),
        "paymentSummary": payload.get("paymentSummary", ""),
    })
    with transaction.atomic():
        idem, replay = _register(SAVE_ACTION, idempotency_key, obj.source_key, request_hash, obj.tenant_id)
        if replay:
            current = PaymentOrderDraft.objects.get(pk=idem.target_id)
            return {"classification": "existing_result", "saved": False, "data": serialize_draft(current)}
        tx = _transaction(SAVE_ACTION, idempotency_key, obj.source_payment_order_prepare, obj.source_key, request_hash)
        lock = _lock(obj.source_key, tx.transaction_id)
        current = PaymentOrderDraft.objects.select_for_update().get(pk=obj.pk)
        if current.version != expected_version or current.current_draft_data_version != expected_draft_data_version:
            raise ReconciliationError("VERSION_CONFLICT", "Object or data version conflict", 409)
        source = PaymentOrderPrepare.objects.select_for_update().get(
            pk=current.source_payment_order_prepare_id
        )
        if source.version != expected_payment_order_prepare_version:
            raise ReconciliationError("SOURCE_STALE", "Payment order prepare version conflict", 409)
        if source_hash(source) != current.source_snapshot.source_order_prepare_hash:
            raise ReconciliationError("SOURCE_STALE", "Instruction prepare changed", 409)
        source_order_data = source.order_data_snapshots.order_by(
            "-order_data_version"
        ).first()
        current.planned_execution_date = planned_date
        current.planned_execution_time = planned_time
        authorities = read_order_authorities(current, user.pk)
        evidence = evidence_dict(authorities)
        signing = evidence.get("signingPolicy") or {}
        authorization = evidence.get("authorizationRoute") or {}
        capability = evidence.get("signingCapability") or {}
        payer = evidence.get("payer") or {}
        payee = evidence.get("payee") or {}
        route = evidence.get("route") or {}
        interface = evidence.get("interface") or {}
        if not all([payer, payee, route, interface, signing, authorization, capability]):
            raise ReconciliationError("POD_REQUIRED_AUTHORITY_MISSING", "Required authority missing", 409)
        version = current.current_draft_data_version + 1
        data_hash = canonical_hash({
            "targetId": current.pk,
            "version": version,
            "plannedExecutionDate": planned_date.isoformat(),
            "plannedExecutionTime": planned_time.isoformat(),
            "amount": str(current.payment_amount),
            "currency": current.currency,
            "authorityEvidence": evidence,
        })
        snapshot = PaymentOrderDraftDataSnapshot.objects.create(
            payment_order_draft=current,
            draft_data_version=version,
            payer_bank_account_id=current.payer_bank_account_id,
            payer_account_no_masked=payer["payload"]["maskedAccountNo"],
            payee_bank_account_id=current.payee_bank_account_id,
            payee_account_no_masked=payee["payload"]["maskedAccountNo"],
            payment_route_id=route["payload"]["routeId"],
            payment_route_code=route["payload"]["routeCode"],
            bank_interface_profile_id=interface["payload"]["interfaceProfileId"],
            channel_code=interface["payload"]["channelCode"],
            message_format=interface["payload"]["messageFormat"],
            payment_method_code=current.payment_method_code,
            planned_execution_date=planned_date,
            planned_execution_time=planned_time,
            currency=current.currency,
            payment_amount=current.payment_amount,
            payment_purpose=payload.get("paymentPurpose", "供应商采购款"),
            payment_summary=payload.get("paymentSummary", current.source_payment_request_no),
            priority=payload.get("priority", current.priority),
            payment_reference=f"PAY-{current.draft_no}",
            maker_user_id=(
                source_order_data.maker_user_id
                if source_order_data
                else str(user.pk)
            ),
            signing_policy_id=signing["payload"]["signingPolicyId"],
            authorization_route_id=authorization["payload"]["authorizationRouteId"],
            signing_capability_id=capability["payload"]["signingCapabilityId"],
            draft_payload_hash=data_hash,
            created_by=user,
        )
        authority_hash = canonical_hash(evidence)
        PaymentOrderDraftAuthoritySnapshot.objects.create(
            payment_order_draft=current,
            draft_data_version=version,
            evidence=evidence,
            authority_snapshot_hash=authority_hash,
        )
        preview_hash = canonical_hash({
            "dataHash": data_hash,
            "authorityHash": authority_hash,
            "signed": False,
            "sent": False,
            "formalOrder": False,
        })
        PaymentOrderDraftCreationPreview.objects.create(
            draft_data_snapshot=snapshot,
            creation_preview_version=1,
            proposed_formal_order_reference=f"DRAFT-{current.draft_no}",
            debtor_name=payer["payload"]["accountName"],
            debtor_account_masked=payer["payload"]["maskedAccountNo"],
            creditor_name=payee["payload"]["accountName"],
            creditor_account_masked=payee["payload"]["maskedAccountNo"],
            currency=current.currency,
            amount=current.payment_amount,
            payment_method_code=current.payment_method_code,
            route_code=route["payload"]["routeCode"],
            channel_code=interface["payload"]["channelCode"],
            execution_date=planned_date,
            execution_time=planned_time,
            payment_reference=snapshot.payment_reference,
            payment_purpose=snapshot.payment_purpose,
            signing_policy_code=signing["payload"]["policyCode"],
            required_signature_count=signing["payload"]["requiredSignatures"],
            authorization_step_count=authorization["payload"]["stepCount"],
            creation_preview_hash=preview_hash,
        )
        current.payment_route_id = snapshot.payment_route_id
        current.bank_interface_profile_id = snapshot.bank_interface_profile_id
        current.signing_policy_id = snapshot.signing_policy_id
        current.authorization_route_id = snapshot.authorization_route_id
        current.signing_capability_id = snapshot.signing_capability_id
        current.priority = snapshot.priority
        current.draft_data_status = "complete"
        current.review_status = "not_reviewed"
        current.review_result_code = "not_reviewed"
        current.review_issue_count = 0
        current.current_draft_data_version = version
        current.version += 1
        current.save()
        audit = _audit(tx, SAVE_ACTION, idempotency_key, user, source, current, {
            "version": VERSION,
            "draftDataVersion": version,
            "dataHash": data_hash,
            "authoritySnapshotHash": authority_hash,
            "orderPreviewSigned": False,
            "orderPreviewSentExternally": False,
        })
        current.audit_record = audit
        current.save(update_fields=["audit_record", "updated_at"])
        _commit(tx, idem, current, "saved")
        _release(lock)
        _inject("before_database_commit", failure_step)
    _inject("before_response", failure_step)
    return {"classification": "saved", "saved": True, "data": serialize_draft(current)}


def _review_issues(obj, snapshot, evidence, preview):
    issues = []

    def add(code, dimension, expected, actual, field):
        rule_code = code if code.startswith("POD_") else f"POD_REVIEW_{code.upper()}"
        issues.append({
            "ruleCode": rule_code,
            "dimension": dimension,
            "expected": str(expected),
            "actual": str(actual),
            "severity": "error",
            "blocking": True,
            "message": rule_code,
            "sourceField": field,
        })

    def payload(name):
        return (evidence.get(name) or {}).get("payload", {})

    payer = payload("payer")
    payee = payload("payee")
    route = payload("route")
    interface = payload("interface")
    calendar = payload("calendar")
    limit = payload("limit")
    hold = payload("hold")
    funds = payload("funds")
    signing = payload("signingPolicy")
    authorization = payload("authorizationRoute")
    capability = payload("signingCapability")
    segregation = payload("segregation")
    if not payer.get("active") or not payer.get("availableForPayment"):
        add("payer_bank_account_inactive", "payer", "active", "inactive", "payerBankAccountId")
    if not payee.get("active") or not payee.get("paymentEnabled"):
        add("payee_bank_account_inactive", "payee", "active", "inactive", "payeeBankAccountId")
    elif payee.get("supplierId") != obj.supplier_id:
        add("account_owner_mismatch", "payee", obj.supplier_id, payee.get("supplierId"), "supplierId")
    if payer.get("currency") != obj.currency or payee.get("currency") != obj.currency:
        add("currency_mismatch", "currency", obj.currency, f"{payer.get('currency')}/{payee.get('currency')}", "currency")
    if snapshot.payment_amount != obj.payment_amount:
        add("amount_mismatch", "amount", obj.payment_amount, snapshot.payment_amount, "paymentAmount")
    if not route.get("active"):
        add("payment_route_inactive", "route", "active", "inactive", "paymentRouteId")
    if not (
        interface.get("active")
        and interface.get("paymentEnabled")
        and interface.get("connectionStatus") == "available"
    ):
        add("bank_interface_unavailable", "interface", "available", interface.get("connectionStatus"), "bankInterfaceProfileId")
    if not calendar.get("businessDay") or not calendar.get("paymentAllowed"):
        add("bank_business_day_invalid", "calendar", "business day", "invalid", "plannedExecutionDate")
    if calendar.get("cutoffTime") and snapshot.planned_execution_time > time.fromisoformat(calendar["cutoffTime"]):
        add("cutoff_time_exceeded", "calendar", calendar["cutoffTime"], snapshot.planned_execution_time, "plannedExecutionTime")
    if not limit:
        add("single_payment_limit_exceeded", "limit", "authority", "missing", "paymentAmount")
    else:
        if obj.payment_amount > Decimal(limit["singlePaymentLimit"]):
            add("single_payment_limit_exceeded", "limit", limit["singlePaymentLimit"], obj.payment_amount, "paymentAmount")
        if Decimal(limit["currentDailyCommittedAmount"]) + obj.payment_amount > Decimal(limit["dailyPaymentLimit"]):
            add("daily_payment_limit_exceeded", "limit", limit["dailyPaymentLimit"], obj.payment_amount, "paymentAmount")
    if hold.get("holdStatus") == "active":
        add("payment_hold_active", "hold", "released", "active", "sourcePaymentRequestId")
    if evidence.get("duplicateRisk"):
        add("duplicate_payment_risk", "duplicate", "false", "true", "paymentIdentity")
    if not funds or not funds.get("active"):
        add("funds_authority_unavailable", "funds", "active", "missing", "fundsEvidenceId")
    elif not funds.get("sufficient"):
        add("available_balance_insufficient", "funds", obj.payment_amount, funds.get("availableForNewPayment"), "availableBalance")
    if not signing or not signing.get("active"):
        add("signing_policy_missing", "signing", "active", "missing", "signingPolicyId")
    if not authorization or not authorization.get("active") or not authorization.get("steps"):
        add("authorization_route_invalid", "authorization", "active steps", "invalid", "authorizationRouteId")
    if not capability or not capability.get("active") or capability.get("signingServiceStatus") != "available":
        add("signing_capability_unavailable", "signing", "available", capability.get("signingServiceStatus"), "signingCapabilityId")
    if capability.get("credentialStatus") != "ready" or capability.get("certificateStatus") != "valid":
        add("signing_credential_not_ready", "credential", "ready/valid", f"{capability.get('credentialStatus')}/{capability.get('certificateStatus')}", "credentialStatus")
    if not segregation.get("segregationValid"):
        add("maker_checker_conflict", "segregation", "valid", "invalid", "makerUserId")
    expected_preview_hash = canonical_hash({
        "dataHash": snapshot.draft_payload_hash,
        "authorityHash": obj.authority_snapshots.get(draft_data_version=snapshot.draft_data_version).authority_snapshot_hash,
        "signed": False,
        "sent": False,
        "formalOrder": False,
    })
    if not preview or preview.creation_preview_hash != expected_preview_hash:
        add(
            "creation_preview_integrity_failed",
            "preview",
            expected_preview_hash,
            getattr(preview, "creation_preview_hash", ""),
            "previewHash",
        )
    return issues


def review_payment_order_draft(
    *, user, obj, idempotency_key, expected_version, expected_draft_data_version,
    expected_payment_order_prepare_version, explicit_user_action, failure_step=""
):
    _explicit(explicit_user_action)
    _authorize(user, obj.source_payment_order_prepare, "payment_order_draft.review_payment_order_draft")
    request_hash = canonical_hash({
        "id": obj.pk,
        "version": expected_version,
        "draftDataVersion": expected_draft_data_version,
        "paymentOrderPrepareVersion": expected_payment_order_prepare_version,
        "action": REVIEW_ACTION,
    })
    with transaction.atomic():
        idem, replay = _register(REVIEW_ACTION, idempotency_key, obj.source_key, request_hash, obj.tenant_id)
        if replay:
            current = PaymentOrderDraft.objects.get(pk=idem.target_id)
            return {"classification": "existing_result", "validated": current.status == "reviewed", "data": serialize_draft(current)}
        tx = _transaction(REVIEW_ACTION, idempotency_key, obj.source_payment_order_prepare, obj.source_key, request_hash)
        lock = _lock(obj.source_key, tx.transaction_id)
        current = PaymentOrderDraft.objects.select_for_update().get(pk=obj.pk)
        if current.version != expected_version or current.current_draft_data_version != expected_draft_data_version:
            raise ReconciliationError("VERSION_CONFLICT", "Object or data version conflict", 409)
        if current.status != "created":
            raise ReconciliationError("PAYMENT_ORDER_DRAFT_REVIEWED_IMMUTABLE", "Reviewed target is immutable", 409)
        source = PaymentOrderPrepare.objects.select_for_update().get(
            pk=current.source_payment_order_prepare_id
        )
        if source.version != expected_payment_order_prepare_version:
            raise ReconciliationError("SOURCE_STALE", "Payment order prepare version conflict", 409)
        if source_hash(source) != current.source_snapshot.source_order_prepare_hash:
            raise ReconciliationError("SOURCE_STALE", "Instruction prepare changed", 409)
        snapshot = current.draft_data_snapshots.get(
            draft_data_version=current.current_draft_data_version
        )
        authority = current.authority_snapshots.get(
            draft_data_version=current.current_draft_data_version
        )
        preview = snapshot.creation_previews.order_by("-creation_preview_version").first()
        current_evidence = evidence_dict(read_order_authorities(current, user.pk))
        if canonical_hash(current_evidence) != authority.authority_snapshot_hash:
            raise ReconciliationError("SOURCE_STALE", "Authority evidence changed", 409)
        issues = _review_issues(current, snapshot, current_evidence, preview)
        result_code = "multiple_errors" if len(issues) > 1 else (
            issues[0]["ruleCode"].replace("POD_REVIEW_", "").lower() if issues else "reviewed"
        )
        execution = PaymentOrderDraftReviewExecution.objects.create(
            payment_order_draft=current,
            action_id=f"POD-REVIEW-{uuid.uuid4().hex[:20]}",
            idempotency_key=idempotency_key,
            draft_data_version=snapshot.draft_data_version,
            source_order_prepare_version=source.version,
            source_order_validation_version=source.current_validation_version,
            source_payment_request_version=source.source_payment_request_version,
            source_workflow_version=(
                source.source_payment_instruction_prepare.source_payment_request.workflow_instance.version
            ),
            source_approval_evidence_hash=source.source_approval_evidence_hash,
            review_policy_version=REVIEW_POLICY_VERSION,
            status="failed" if issues else "passed",
            result_code=result_code,
            input_hash=request_hash,
            result_hash=canonical_hash(issues),
            issue_count=len(issues),
            actor=user,
            completed_at=timezone.now(),
        )
        for issue in issues:
            PaymentOrderDraftReviewIssue.objects.create(
                review_execution=execution,
                rule_code=issue["ruleCode"],
                dimension=issue["dimension"],
                expected=issue["expected"],
                actual=issue["actual"],
                severity=issue["severity"],
                blocking=issue["blocking"],
                message=issue["message"],
                source_field=issue["sourceField"],
            )
        current.current_review_version += 1
        current.review_issue_count = len(issues)
        current.review_status = "failed" if issues else "passed"
        current.review_result_code = result_code
        if not issues:
            current.reviewed_at = timezone.now()
            current.reviewed_by = user
        else:
            current.version += 1
        current.save(update_fields=[
            "current_review_version",
            "review_issue_count",
            "review_status",
            "review_result_code",
            "reviewed_at",
            "reviewed_by",
            "version",
            "updated_at",
        ])
        audit = _audit(tx, REVIEW_ACTION, idempotency_key, user, source, current, {
            "version": VERSION,
            "reviewPolicyVersion": REVIEW_POLICY_VERSION,
            "reviewExecutionId": execution.pk,
            "resultCode": result_code,
            "issues": issues,
            "fundsReserved": False,
            "bankBalanceDebited": False,
            "orderPreviewSigned": False,
            "orderPreviewSentExternally": False,
        })
        if not issues:
            transition_business_object(
                business_object=current,
                object_type=DOCUMENT_TYPE,
                source_state="created",
                target_state="reviewed",
                action_code=REVIEW_ACTION,
                operator=user,
                reason="Payment order draft review passed",
                audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
        current.audit_record = audit
        current.save(update_fields=["audit_record", "updated_at"])
        _commit(tx, idem, current, "reviewed" if not issues else "failed")
        _release(lock)
        _inject("before_database_commit", failure_step)
    _inject("before_response", failure_step)
    return {
        "classification": "reviewed" if not issues else "blocked",
        "reviewed": not issues,
        "data": serialize_draft(current),
    }


def eligibility(obj):
    snapshot = obj.draft_data_snapshots.order_by("-draft_data_version").first()
    authority = obj.authority_snapshots.order_by("-draft_data_version").first()
    evidence = authority.evidence if authority else {}

    def payload(name):
        return (evidence.get(name) or {}).get("payload", {})

    funds = payload("funds")
    signing = payload("signingPolicy")
    authorization = payload("authorizationRoute")
    capability = payload("signingCapability")
    segregation = payload("segregation")
    route = payload("route")
    interface = payload("interface")
    calendar = payload("calendar")
    limit = payload("limit")
    hold = payload("hold")
    preview = (
        snapshot.creation_previews.order_by("-creation_preview_version").first()
        if snapshot
        else None
    )
    state_facts = business_state_transition_facts(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        expected_transitions=EXPECTED_STATE_TRANSITIONS,
        audit_target_type="paymentOrderDraft",
    )
    checks = {
        "stateMachineConsistent": state_facts["stateMachineConsistent"],
        "statusReviewed": obj.status == "reviewed",
        "draftDataComplete": obj.draft_data_status == "complete",
        "reviewPassed": obj.review_status == "passed" and obj.review_result_code == "reviewed" and obj.review_issue_count == 0,
        "fundsAvailable": bool(funds.get("active") and funds.get("sufficient")),
        "signingPolicyValid": bool(signing.get("active")),
        "authorizationRouteValid": bool(authorization.get("active") and authorization.get("steps")),
        "signingCapabilityReady": bool(
            capability.get("active")
            and capability.get("signingServiceStatus") == "available"
            and capability.get("credentialStatus") == "ready"
            and capability.get("certificateStatus") == "valid"
        ),
        "makerCheckerSegregationValid": bool(segregation.get("segregationValid")),
        "routeValid": bool(route.get("active")),
        "bankInterfaceAvailable": bool(
            interface.get("active")
            and interface.get("paymentEnabled")
            and interface.get("connectionStatus") == "available"
        ),
        "businessDayValid": bool(calendar.get("businessDay") and calendar.get("paymentAllowed")),
        "cutoffValid": bool(calendar),
        "singleLimitPassed": bool(limit),
        "dailyLimitPassed": bool(limit),
        "paymentHold": hold.get("holdStatus") == "active",
        "duplicatePaymentRisk": bool(evidence.get("duplicateRisk")),
        "previewIntegrityValid": bool(preview),
    }
    blocking = [key for key, value in checks.items() if (
        (key in {"paymentHold", "duplicatePaymentRisk"} and value)
        or (key not in {"paymentHold", "duplicatePaymentRisk"} and not value)
    )]
    eligible = not blocking
    return {
        "status": obj.status,
        "draftDataStatus": obj.draft_data_status,
        "reviewStatus": obj.review_status,
        **{key: value for key, value in checks.items() if key not in {"statusReviewed", "draftDataComplete", "reviewPassed", "previewIntegrityValid"}},
        "nextStepReadiness": "ready_for_payment_risk_review" if eligible else "blocked",
        "eligible": eligible,
        "blockingReasons": blocking,
        "serverDerived": True,
        "serverRereviewRequired": True,
        "nextModuleCode": NEXT_MODULE_CODE,
        "nextCanonicalName": NEXT_CANONICAL_NAME,
        "nextRoute": NEXT_ROUTE,
    }


def serialize_draft(obj, include_issues=True):
    snapshot = obj.draft_data_snapshots.order_by("-draft_data_version").first()
    authority = obj.authority_snapshots.order_by("-draft_data_version").first()
    preview = (
        snapshot.creation_previews.order_by("-creation_preview_version").first()
        if snapshot
        else None
    )
    review = obj.review_executions.order_by("-pk").first()
    evidence = authority.evidence if authority else {}
    issues = []
    if include_issues and review:
        issues = [{
            "ruleCode": row.rule_code,
            "dimension": row.dimension,
            "expected": row.expected,
            "actual": row.actual,
            "severity": row.severity,
            "blocking": row.blocking,
            "message": row.message,
            "sourceField": row.source_field,
        } for row in review.issues.order_by("rule_code")]
    state_facts = business_state_transition_facts(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        expected_transitions=EXPECTED_STATE_TRANSITIONS,
        audit_target_type="paymentOrderDraft",
    )
    return {
        "id": obj.pk,
        "draftNo": obj.draft_no,
        "status": obj.status,
        "sourceDocumentType": obj.source_document_type,
        "sourcePaymentOrderPrepareId": obj.source_payment_order_prepare_id,
        "sourcePaymentOrderPrepareNo": obj.source_payment_order_prepare_no,
        "sourcePaymentRequestId": obj.source_payment_request_id,
        "sourcePaymentRequestNo": obj.source_payment_request_no,
        "sourceOrderPrepareVersion": obj.source_order_prepare_version,
        "sourceOrderDataVersion": obj.source_order_data_version,
        "sourceOrderValidationVersion": obj.source_order_validation_version,
        "sourceOrderPreviewHash": obj.source_order_preview_hash,
        "supplierId": obj.supplier_id,
        "supplierName": obj.supplier_name,
        "legalEntityId": obj.legal_entity_id,
        "legalEntityName": obj.legal_entity_name,
        "ledgerBookId": obj.ledger_book_id,
        "currency": obj.currency,
        "paymentAmount": str(obj.payment_amount),
        "plannedExecutionDate": obj.planned_execution_date.isoformat(),
        "plannedExecutionTime": obj.planned_execution_time.isoformat() if obj.planned_execution_time else None,
        "paymentMethodCode": obj.payment_method_code,
        "payerBankAccountId": obj.payer_bank_account_id,
        "payeeBankAccountId": obj.payee_bank_account_id,
        "paymentRouteId": obj.payment_route_id,
        "bankInterfaceProfileId": obj.bank_interface_profile_id,
        "signingPolicyId": obj.signing_policy_id,
        "authorizationRouteId": obj.authorization_route_id,
        "signingCapabilityId": obj.signing_capability_id,
        "priority": obj.priority,
        "draftDataStatus": obj.draft_data_status,
        "reviewStatus": obj.review_status,
        "reviewResultCode": obj.review_result_code,
        "reviewIssueCount": obj.review_issue_count,
        "currentDraftDataVersion": obj.current_draft_data_version,
        "currentReviewVersion": obj.current_review_version,
        "version": obj.version,
        "source": {
            "status": obj.source_payment_order_prepare.status,
            "validationStatus": obj.source_payment_order_prepare.validation_status,
            "nextStepReadiness": order_eligibility(obj.source_payment_order_prepare)["nextStepReadiness"],
        },
        "draftData": {
            "paymentPurpose": snapshot.payment_purpose,
            "paymentSummary": snapshot.payment_summary,
            "paymentReference": snapshot.payment_reference,
            "makerUserId": snapshot.maker_user_id,
            "draftPayloadHash": snapshot.draft_payload_hash,
        } if snapshot else None,
        "authorities": evidence,
        "preview": {
            "proposedFormalOrderReference": preview.proposed_formal_order_reference,
            "debtorName": preview.debtor_name,
            "debtorAccountMasked": preview.debtor_account_masked,
            "creditorName": preview.creditor_name,
            "creditorAccountMasked": preview.creditor_account_masked,
            "currency": preview.currency,
            "amount": str(preview.amount),
            "routeCode": preview.route_code,
            "channelCode": preview.channel_code,
            "executionDate": preview.execution_date.isoformat(),
            "executionTime": preview.execution_time.isoformat(),
            "paymentReference": preview.payment_reference,
            "signingPolicyCode": preview.signing_policy_code,
            "requiredSignatureCount": preview.required_signature_count,
            "authorizationStepCount": preview.authorization_step_count,
            "previewHash": preview.creation_preview_hash,
            "readOnly": True,
            "formalPaymentOrderCreated": False,
            "signed": False,
            "sentExternally": False,
            "paymentExecuted": False,
        } if preview else None,
        "review": {
            "executionId": review.pk if review else None,
            "status": review.status if review else "not_reviewed",
            "resultCode": review.result_code if review else "not_reviewed",
            "ruleCount": len(RULE_CODES),
            "passedCount": len(RULE_CODES) - len(issues),
            "blockedCount": len(issues),
            "issueCount": len(issues),
            "issues": issues,
        },
        "eligibility": eligibility(obj),
        **state_facts,
        "idempotencyStatus": "committed",
        "numberReservationStatus": obj.number_reservation.status,
        "transactionStatus": obj.business_transaction.status,
        "auditStatus": "committed" if obj.audit_record_id else "missing",
        "currentStateSource": "server",
    }


def recover_action_result(action_code, idempotency_key):
    idem = BusinessActionIdempotency.objects.filter(
        action_code=action_code, idempotency_key=idempotency_key
    ).first()
    if not idem or not idem.target_id:
        raise ReconciliationError("POD_IDEMPOTENCY_NOT_FOUND", "Result not found", 404)
    return {
        "classification": "existing_result",
        "actionCode": action_code,
        "data": serialize_draft(PaymentOrderDraft.objects.get(pk=idem.target_id)),
    }
