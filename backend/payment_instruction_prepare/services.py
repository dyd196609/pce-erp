import uuid
from datetime import date, time
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from payment_request.models import PaymentRequest
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
    PaymentInstructionDataSnapshot,
    PaymentInstructionPrepare,
    PaymentInstructionPrepareSourceRelation,
    PaymentInstructionPrepareSourceSnapshot,
    PaymentInstructionPrepareValidationExecution,
    PaymentInstructionPrepareValidationIssue,
    PaymentInstructionPreview,
)
from .providers import read_authorities


VERSION = "V1.14.2.8.4.7.55"
CANONICAL_NAME = "付款指令准备"
SOURCE_DOCUMENT_TYPE = "paymentRequest"
DOCUMENT_TYPE = "payment_instruction_prepare"
GENERATE_ACTION = "GENERATE_PAYMENT_INSTRUCTION_PREPARE"
SAVE_ACTION = "SAVE_PAYMENT_INSTRUCTION_PREPARE_DATA"
VALIDATE_ACTION = "VALIDATE_PAYMENT_INSTRUCTION_PREPARE"
NEXT_MODULE_CODE = "payment_order_prepare"
NEXT_CANONICAL_NAME = "正式付款单预备"
NEXT_ROUTE = "/finance/payment-prepares"
NUMBER_POLICY_VERSION = "payment-instruction-prepare-sequence-v1"
VALIDATION_POLICY_VERSION = "payment-instruction-prepare-validation-v1"
TRANSACTION_PLAN_ID = "payment-instruction-prepare-atomic-v1"
ALLOWED_STATE_TRANSITIONS = (("prepared", "validated"),)
EXPECTED_STATE_TRANSITIONS = {
    "prepared": (),
    "validated": (("prepared", "validated", VALIDATE_ACTION),),
}


def _decimal(value, field):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReconciliationError("PIP_AMOUNT_INVALID", f"{field} is invalid", 400) from exc


def _date(value, field):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ReconciliationError("PIP_DATE_INVALID", f"{field} must be YYYY-MM-DD", 400) from exc


def _time(value, field):
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ReconciliationError("PIP_TIME_INVALID", f"{field} must be HH:MM", 400) from exc


def _explicit(value):
    if value is not True:
        raise ReconciliationError(
            "PIP_EXPLICIT_USER_ACTION_REQUIRED", "Explicit user action required", 400
        )


def _authorize(user, source, permission):
    if not user or not user.is_authenticated:
        raise ReconciliationError("PIP_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not (user.is_superuser or user.has_perm(permission)):
        raise ReconciliationError("PIP_AUTH_PERMISSION_DENIED", "Permission denied", 403)
    if not user.is_superuser and user.company_id != source.company_id:
        raise ReconciliationError("PIP_AUTH_SCOPE_DENIED", "Scope denied", 403)
    if not settings.PCE_PAYMENT_INSTRUCTION_PREPARE_FEATURE_ENABLED:
        raise ReconciliationError("PIP_AUTH_FEATURE_DISABLED", "Feature disabled", 403)
    if (
        source.tenant_id not in settings.PCE_PAYMENT_INSTRUCTION_PREPARE_TEST_TENANTS
        and not settings.PCE_PAYMENT_INSTRUCTION_PREPARE_PRODUCTION_ROLLOUT_ENABLED
    ):
        raise ReconciliationError(
            "PIP_AUTH_PRODUCTION_ROLLOUT_DISABLED", "Production rollout disabled", 403
        )


def _inject(step, requested):
    if step != requested:
        return
    if not settings.PCE_PAYMENT_INSTRUCTION_PREPARE_FAILURE_INJECTION_ENABLED:
        raise ReconciliationError("PIP_FAILURE_INJECTION_DISABLED", "Injection disabled", 403)
    if step == "before_response":
        raise ReconciliationError(
            "PIP_COMMIT_UNKNOWN", "Committed result must be recovered by idempotency", 503, True
        )
    raise ReconciliationError(f"PIP_INJECTED_{step.upper()}", f"Injected at {step}", 503, True)


def _source_reconciliation(source):
    return (
        source.source_payment_request_prepare
        .source_payable_confirmation_prepare
        .source_purchase_accounts_payable_draft
        .source_purchase_reconciliation
    )


def _approval_evidence(source):
    workflow = source.workflow_instance
    decisions = list(
        workflow.tasks.values_list("status", flat=True)
    ) if workflow else []
    return canonical_hash({
        "requestId": source.pk,
        "requestNo": source.request_no,
        "requestVersion": source.version,
        "status": source.status,
        "approvalStatus": source.approval_status,
        "approvalResultCode": source.approval_result_code,
        "workflowId": workflow.pk if workflow else None,
        "workflowVersion": workflow.version if workflow else None,
        "taskStatuses": decisions,
    })


def source_hash(source):
    return canonical_hash({
        "id": source.pk, "requestNo": source.request_no,
        "version": source.version, "status": source.status,
        "approvalStatus": source.approval_status,
        "approvalResultCode": source.approval_result_code,
        "paymentAmount": str(source.payment_amount),
        "currency": source.currency,
        "plannedPaymentDate": source.planned_payment_date.isoformat(),
        "paymentMethodCode": source.payment_method_code,
        "payerBankAccountId": source.payer_bank_account_id,
        "payeeBankAccountId": source.payee_bank_account_id,
        "approvalEvidenceHash": _approval_evidence(source),
    })


def source_gate(source, check_existing=True):
    reasons = []
    if source.status != "approved":
        reasons.append("SOURCE_NOT_APPROVED")
    if source.approval_status != "approved" or source.approval_result_code != "approved":
        reasons.append("APPROVAL_EVIDENCE_INCOMPLETE")
    workflow = source.workflow_instance
    if not workflow or workflow.status != "approved":
        reasons.append("APPROVAL_EVIDENCE_INCOMPLETE")
    elif workflow.tasks.exclude(status="approved").exists():
        reasons.append("APPROVAL_EVIDENCE_INCOMPLETE")
    upstream = source.source_payment_request_prepare
    if (
        upstream.status != "prepared"
        or upstream.payment_data_status != "complete"
        or upstream.validation_status != "passed"
    ):
        reasons.append("SOURCE_STALE")
    if source.payment_amount <= 0:
        reasons.append("AMOUNT_MISMATCH")
    if check_existing and PaymentInstructionPrepare.objects.filter(
        source_payment_request=source
    ).exists():
        reasons.append("EXISTING_TARGET")
    return list(dict.fromkeys(reasons))


def _register(action, key, source_key, request_hash, tenant_id):
    existing = BusinessActionIdempotency.objects.filter(
        action_code=action, idempotency_key=key
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise ReconciliationError("PIP_IDEMPOTENCY_PAYLOAD_CONFLICT", "Payload conflict", 409)
        if existing.status == "committed" and existing.target_id:
            return existing, True
        raise ReconciliationError("PIP_IN_PROGRESS", "Action is in progress", 409, True)
    return BusinessActionIdempotency.objects.create(
        action_code=action, idempotency_key=key, tenant_id=tenant_id,
        source_key=source_key, request_hash=request_hash, status="in_progress",
    ), False


def _lock(source_key, txid):
    row, created = BusinessActionSourceLock.objects.get_or_create(
        lock_key=f"payment-instruction-prepare:{source_key}",
        defaults={"owner_transaction_id": txid, "state": "acquired"},
    )
    if not created and row.state == "acquired" and row.owner_transaction_id != txid:
        raise ReconciliationError("PIP_SOURCE_LOCKED", "Source is locked", 409, True)
    row.owner_transaction_id = txid
    row.state = "acquired"
    row.released_at = None
    row.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
    return row


def _tx(action, key, source, source_key, request_hash):
    txid = f"PIP-TX-{uuid.uuid4().hex[:24]}"
    return BusinessActionTransaction.objects.create(
        transaction_id=txid, action_code=action, idempotency_key=key,
        tenant_id=source.tenant_id, source_key=source_key,
        command_id=f"PIP-CMD-{uuid.uuid4().hex[:20]}",
        transaction_plan_id=TRANSACTION_PLAN_ID,
        review_id=f"PIP-REVIEW-{source.pk}", review_hash=request_hash,
        status="in_progress", outcome="pending", commit_status="not_committed",
        recovery_status="not_required",
    )


def _audit(tx, action, key, user, source, target, evidence):
    reconciliation = _source_reconciliation(source)
    return BusinessActionAuditRecord.objects.create(
        transaction=tx, action_code=action, tenant_id=source.tenant_id,
        actor=user, source_key=target.source_key, reconciliation=reconciliation,
        result="committed", target_type="paymentInstructionPrepare",
        target_id=target.pk, target_no=target.prepare_no,
        review_id=tx.review_id, review_hash=tx.review_hash,
        command_id=tx.command_id, idempotency_key=key,
        actor_name=getattr(user, "username", str(user.pk)),
        tenant_or_scope=source.tenant_id,
        evidence_hash=canonical_hash(evidence), evidence=evidence,
    )


def _commit(tx, idem, target, classification):
    result_hash = canonical_hash({
        "id": target.pk, "prepareNo": target.prepare_no,
        "version": target.version, "status": target.status,
        "classification": classification,
    })
    tx.status = "committed"
    tx.outcome = "success"
    tx.commit_status = "committed"
    tx.result_hash = result_hash
    tx.save()
    idem.status = "committed"
    idem.target_type = "paymentInstructionPrepare"
    idem.target_id = target.pk
    idem.target_no = target.prepare_no
    idem.transaction_id = tx.transaction_id
    idem.result_reference = f"paymentInstructionPrepare:{target.pk}"
    idem.save()


def _reserve_number(source, key):
    period = source.planned_payment_date.strftime("%Y-%m")
    scope = f"{DOCUMENT_TYPE}:{source.legal_entity_id}:{source.ledger_book_id}:{period}"
    sequence, _ = BusinessDocumentNumberSequence.objects.get_or_create(number_scope=scope)
    sequence.current_value += 1
    number = f"PIP{period.replace('-', '')}{sequence.current_value:08d}"
    while BusinessDocumentNumberReservation.objects.filter(reserved_number=number).exists():
        sequence.current_value += 1
        number = f"PIP{period.replace('-', '')}{sequence.current_value:08d}"
    sequence.save(update_fields=["current_value", "updated_at"])
    return BusinessDocumentNumberReservation.objects.create(
        document_type=DOCUMENT_TYPE, number_policy_version=NUMBER_POLICY_VERSION,
        number_scope=scope, legal_entity_id=source.legal_entity_id,
        ledger_book_id=source.ledger_book_id, reserved_number=number,
        tenant_id=source.tenant_id, accounting_period=period,
        idempotency_key=key, status="reserved",
        target=_source_reconciliation(source), reusable=False,
    )


def generate_payment_instruction_prepare(
    *, user, source, idempotency_key, expected_source_version,
    explicit_user_action, failure_step=""
):
    _explicit(explicit_user_action)
    _authorize(user, source, "payment_instruction_prepare.generate_payment_instruction_prepare")
    _inject("after_authorization", failure_step)
    if not idempotency_key:
        raise ReconciliationError("PIP_IDEMPOTENCY_KEY_REQUIRED", "Idempotency key required", 400)
    request_hash = canonical_hash({
        "sourceId": source.pk, "expectedSourceVersion": expected_source_version,
        "action": GENERATE_ACTION,
    })
    with transaction.atomic():
        idem, replay = _register(
            GENERATE_ACTION, idempotency_key, f"paymentRequest:{source.pk}",
            request_hash, source.tenant_id,
        )
        if replay:
            return {
                "classification": "existing_result", "created": False,
                "data": serialize_prepare(PaymentInstructionPrepare.objects.get(pk=idem.target_id)),
            }
        tx = _tx(
            GENERATE_ACTION, idempotency_key, source,
            f"paymentRequest:{source.pk}", request_hash,
        )
        _inject("after_idempotency_registration", failure_step)
        lock = _lock(f"paymentRequest:{source.pk}", tx.transaction_id)
        current = PaymentRequest.objects.select_for_update().get(pk=source.pk)
        _inject("after_source_reload", failure_step)
        if current.version != expected_source_version:
            raise ReconciliationError("VERSION_CONFLICT", "Source version conflict", 409)
        reasons = source_gate(current)
        if reasons:
            raise ReconciliationError(f"PIP_{reasons[0]}", ",".join(reasons), 409)
        reservation = _reserve_number(current, idempotency_key)
        _inject("after_number_reservation", failure_step)
        upstream = current.source_payment_request_prepare
        confirmation = upstream.source_payable_confirmation_prepare
        draft = confirmation.source_purchase_accounts_payable_draft
        reconciliation = draft.source_purchase_reconciliation
        target = create_business_object_with_initial_state(
            model=PaymentInstructionPrepare,
            initial_state="prepared",
            prepare_no=reservation.reserved_number, source_payment_request=current,
            source_payment_request_no=current.request_no,
            source_payment_request_version=current.version,
            source_approval_workflow_id=current.workflow_instance_id,
            source_approval_evidence_hash=_approval_evidence(current),
            source_payment_request_prepare_id=upstream.pk,
            source_payment_request_prepare_no=upstream.prepare_no,
            source_payable_confirmation_prepare_id=confirmation.pk,
            source_payable_confirmation_prepare_no=confirmation.prepare_no,
            source_ap_draft_id=draft.pk, source_ap_draft_no=draft.draft_no,
            source_invoice_prepare_id=draft.source_purchase_invoice_prepare_id,
            source_invoice_prepare_no=draft.source_purchase_invoice_prepare.prepare_no,
            source_reconciliation_id=reconciliation.pk,
            source_reconciliation_no=reconciliation.reconciliation_no,
            source_key=f"paymentRequest:{current.pk}", tenant_id=current.tenant_id,
            company_id=current.company_id, supplier_id=current.supplier_id,
            supplier_name=current.supplier_name, legal_entity_id=current.legal_entity_id,
            legal_entity_name=current.legal_entity_name,
            ledger_book_id=current.ledger_book_id, currency=current.currency,
            payment_amount=current.payment_amount,
            planned_execution_date=current.planned_payment_date,
            payment_method_code=current.payment_method_code,
            payer_bank_account_id=current.payer_bank_account_id,
            payee_bank_account_id=current.payee_bank_account_id,
            idempotency_key=idempotency_key, number_reservation=reservation,
            business_transaction=tx, created_by=user,
        )
        _inject("after_target_insert", failure_step)
        submission = current.submission_snapshots.order_by("-submission_version").first()
        relation = current.workflow_relations.select_related("approval_route").first()
        payment_data = upstream.payment_data_snapshots.order_by("-payment_data_version").first()
        validation = upstream.validation_executions.order_by("-pk").first()
        eligibility_hash = canonical_hash({
            "eligible": True, "nextStepReadiness": "ready_for_payment_instruction_prepare"
        })
        PaymentInstructionPrepareSourceSnapshot.objects.create(
            payment_instruction_prepare=target,
            source_payment_request_id=current.pk, source_payment_request_no=current.request_no,
            source_payment_request_version=current.version,
            source_submission_snapshot_id=submission.pk if submission else 0,
            source_approval_workflow_id=current.workflow_instance_id,
            source_approval_policy_id=current.approval_policy_id or 0,
            source_approval_policy_version=current.approval_policy_version,
            source_approval_route_hash=relation.approval_route.business_hash if relation else "",
            source_approval_evidence_hash=_approval_evidence(current),
            source_payment_request_prepare_id=upstream.pk,
            source_payment_data_snapshot_id=payment_data.pk if payment_data else 0,
            source_validation_execution_id=validation.pk if validation else 0,
            source_payment_request_hash=source_hash(current),
            source_approval_hash=_approval_evidence(current),
            source_eligibility_hash=eligibility_hash,
        )
        PaymentInstructionPrepareSourceRelation.objects.create(
            payment_instruction_prepare=target, source_id=current.pk,
            source_no=current.request_no, source_version=current.version,
            source_hash=source_hash(current),
        )
        audit = _audit(tx, GENERATE_ACTION, idempotency_key, user, current, target, {
            "version": VERSION, "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "sourceHash": source_hash(current), "approvalEvidenceHash": _approval_evidence(current),
        })
        target.audit_record = audit
        target.save(update_fields=["audit_record", "updated_at"])
        reservation.status = "consumed"
        reservation.consumed_at = timezone.now()
        reservation.save(update_fields=["status", "consumed_at"])
        _commit(tx, idem, target, "created")
        lock.state = "released"
        lock.released_at = timezone.now()
        lock.save(update_fields=["state", "released_at", "acquired_at"])
        _inject("before_database_commit", failure_step)
    _inject("before_response", failure_step)
    return {"classification": "created", "created": True, "data": serialize_prepare(target)}


def _evidence_dict(authorities):
    return {
        key: {
            "provider": value.provider, "repository": value.repository,
            "authorityObject": value.authority_object,
            "authorityId": value.authority_id, "version": value.version,
            "businessHash": value.business_hash, "payload": value.payload,
        } if value else None
        for key, value in authorities.items()
    }


def save_instruction_data(
    *, user, obj, payload, idempotency_key, expected_version,
    explicit_user_action, failure_step=""
):
    _explicit(explicit_user_action)
    _authorize(user, obj.source_payment_request, "payment_instruction_prepare.edit_payment_instruction_prepare_data")
    if obj.status == "validated":
        raise ReconciliationError(
            "PAYMENT_INSTRUCTION_PREPARE_PREPARED_IMMUTABLE",
            "Prepared instruction data is immutable", 409,
        )
    planned_date = _date(payload.get("plannedExecutionDate"), "plannedExecutionDate")
    planned_time = _time(payload.get("plannedExecutionTime", "10:00"), "plannedExecutionTime")
    amount = _decimal(payload.get("paymentAmount"), "paymentAmount")
    request_hash = canonical_hash({
        "id": obj.pk, "version": expected_version,
        "date": planned_date.isoformat(), "time": planned_time.isoformat(),
        "amount": str(amount), "currency": payload.get("currency"),
        "purpose": payload.get("paymentPurpose"), "summary": payload.get("paymentSummary"),
    })
    with transaction.atomic():
        idem, replay = _register(
            SAVE_ACTION, idempotency_key, obj.source_key, request_hash, obj.tenant_id
        )
        if replay:
            return {"classification": "existing_result", "saved": True, "data": serialize_prepare(
                PaymentInstructionPrepare.objects.get(pk=idem.target_id)
            )}
        tx = _tx(SAVE_ACTION, idempotency_key, obj.source_payment_request, obj.source_key, request_hash)
        lock = _lock(obj.source_key, tx.transaction_id)
        current = PaymentInstructionPrepare.objects.select_for_update().get(pk=obj.pk)
        if current.version != expected_version:
            raise ReconciliationError("VERSION_CONFLICT", "Object version conflict", 409)
        if amount != current.payment_amount or payload.get("currency") != current.currency:
            raise ReconciliationError("AMOUNT_MISMATCH", "Amount or currency mismatch", 409)
        authorities = read_authorities(current, planned_date)
        _inject("after_provider_read", failure_step)
        if not authorities["payer"]:
            raise ReconciliationError("PAYER_BANK_ACCOUNT_MISSING", "Payer account missing", 409)
        if not authorities["payee"]:
            raise ReconciliationError("PAYEE_BANK_ACCOUNT_MISSING", "Payee account missing", 409)
        if not authorities["route"]:
            raise ReconciliationError("PAYMENT_ROUTE_MISSING", "Payment route missing", 409)
        if not authorities["interface"]:
            raise ReconciliationError("BANK_INTERFACE_MISSING", "Bank interface missing", 409)
        if not authorities["calendar"]:
            raise ReconciliationError("BANK_BUSINESS_DAY_INVALID", "Bank calendar missing", 409)
        if not authorities["limit"]:
            raise ReconciliationError("PAYMENT_LIMIT_MISSING", "Payment limit missing", 409)
        version = current.current_instruction_data_version + 1
        evidence = _evidence_dict(authorities)
        data_hash = canonical_hash({
            "prepareId": current.pk, "version": version,
            "payer": current.payer_bank_account_id, "payee": current.payee_bank_account_id,
            "route": authorities["route"].authority_id,
            "interface": authorities["interface"].authority_id,
            "date": planned_date.isoformat(), "time": planned_time.isoformat(),
            "currency": current.currency, "amount": str(amount),
            "purpose": payload.get("paymentPurpose", current.source_payment_request.payment_purpose),
            "summary": payload.get("paymentSummary", current.source_payment_request.payment_summary),
            "priority": payload.get("priority", "normal"),
        })
        snapshot = PaymentInstructionDataSnapshot.objects.create(
            payment_instruction_prepare=current, instruction_data_version=version,
            payer_bank_account_id=current.payer_bank_account_id,
            payer_account_no_masked=authorities["payer"].payload["maskedAccountNo"],
            payee_bank_account_id=current.payee_bank_account_id,
            payee_account_no_masked=authorities["payee"].payload["maskedAccountNo"],
            payment_route_id=authorities["route"].payload["routeId"],
            payment_route_code=authorities["route"].payload["routeCode"],
            bank_interface_profile_id=authorities["interface"].payload["interfaceProfileId"],
            channel_code=authorities["interface"].payload["channelCode"],
            message_format=authorities["interface"].payload["messageFormat"],
            payment_method_code=current.payment_method_code,
            planned_execution_date=planned_date, planned_execution_time=planned_time,
            currency=current.currency, payment_amount=amount,
            payment_purpose=payload.get("paymentPurpose", current.source_payment_request.payment_purpose),
            payment_summary=payload.get("paymentSummary", current.source_payment_request.payment_summary),
            priority=payload.get("priority", "normal"),
            instruction_reference=payload.get("instructionReference", current.prepare_no),
            authority_evidence=evidence, data_hash=data_hash, created_by=user,
        )
        preview_hash = canonical_hash({
            "snapshot": snapshot.pk, "dataHash": data_hash, "sentExternally": False
        })
        PaymentInstructionPreview.objects.create(
            instruction_data_snapshot=snapshot, preview_version=1,
            debtor_name=authorities["payer"].payload["accountName"],
            debtor_account_masked=authorities["payer"].payload["maskedAccountNo"],
            creditor_name=authorities["payee"].payload["accountName"],
            creditor_account_masked=authorities["payee"].payload["maskedAccountNo"],
            currency=current.currency, amount=amount,
            payment_method_code=current.payment_method_code,
            route_code=authorities["route"].payload["routeCode"],
            channel_code=authorities["interface"].payload["channelCode"],
            execution_date=planned_date,
            payment_reference=snapshot.instruction_reference,
            purpose=snapshot.payment_purpose, preview_hash=preview_hash,
        )
        current.planned_execution_date = planned_date
        current.payment_route_id = snapshot.payment_route_id
        current.bank_interface_profile_id = snapshot.bank_interface_profile_id
        current.priority = snapshot.priority
        current.instruction_data_status = "complete"
        current.validation_status = "not_validated"
        current.validation_result_code = "not_validated"
        current.validation_issue_count = 0
        current.current_instruction_data_version = version
        current.version += 1
        current.save()
        audit = _audit(tx, SAVE_ACTION, idempotency_key, user, current.source_payment_request, current, {
            "version": VERSION, "instructionDataVersion": version,
            "dataHash": data_hash, "authorityEvidence": evidence,
            "instructionPreviewSentExternally": False,
        })
        current.audit_record = audit
        current.save(update_fields=["audit_record", "updated_at"])
        _commit(tx, idem, current, "saved")
        lock.state = "released"
        lock.released_at = timezone.now()
        lock.save(update_fields=["state", "released_at", "acquired_at"])
        _inject("before_database_commit", failure_step)
    _inject("before_response", failure_step)
    return {"classification": "saved", "saved": True, "data": serialize_prepare(current)}


def _validation_issues(obj, snapshot, authorities):
    issues = []

    def add(code, dimension, expected, actual, field):
        issues.append({
            "ruleCode": code, "dimension": dimension,
            "expected": str(expected), "actual": str(actual),
            "message": code, "sourceField": field,
        })

    payer = authorities["payer"]
    payee = authorities["payee"]
    route = authorities["route"]
    interface = authorities["interface"]
    calendar = authorities["calendar"]
    limit = authorities["limit"]
    hold = authorities["hold"]
    if not payer or not payer.payload["active"] or not payer.payload["availableForPayment"]:
        add("payer_bank_account_inactive", "payer", "active/payment-enabled", "inactive", "payerBankAccountId")
    if not payee or not payee.payload["active"] or not payee.payload["paymentEnabled"]:
        add("payee_bank_account_inactive", "payee", "active/payment-enabled", "inactive", "payeeBankAccountId")
    elif payee.payload["supplierId"] != obj.supplier_id:
        add("account_owner_mismatch", "payee", obj.supplier_id, payee.payload["supplierId"], "supplierId")
    if payer and payer.payload["currency"] != obj.currency:
        add("currency_mismatch", "payer", obj.currency, payer.payload["currency"], "currency")
    if payee and payee.payload["currency"] != obj.currency:
        add("currency_mismatch", "payee", obj.currency, payee.payload["currency"], "currency")
    if not route:
        add("payment_route_missing", "route", "selected", "missing", "paymentRouteId")
    elif not route.payload["active"]:
        add("payment_route_inactive", "route", "active", "inactive", "paymentRouteId")
    if not interface:
        add("bank_interface_missing", "interface", "configured", "missing", "bankInterfaceProfileId")
    elif (
        not interface.payload["active"]
        or not interface.payload["paymentEnabled"]
        or interface.payload["connectionStatus"] != "available"
    ):
        add("bank_interface_not_available", "interface", "available", interface.payload["connectionStatus"], "connectionStatus")
    elif (
        obj.currency not in interface.payload["supportedCurrencies"]
        or obj.payment_method_code not in interface.payload["supportedPaymentMethods"]
    ):
        add("payment_route_not_supported", "interface", "currency/method supported", "unsupported", "supportedPaymentMethods")
    if not calendar or not calendar.payload["businessDay"] or not calendar.payload["paymentAllowed"]:
        add("bank_business_day_invalid", "calendar", "business/payment day", "invalid", "plannedExecutionDate")
    elif snapshot.planned_execution_time > time.fromisoformat(calendar.payload["cutoffTime"]):
        add("cutoff_time_exceeded", "calendar", calendar.payload["cutoffTime"], snapshot.planned_execution_time, "plannedExecutionTime")
    if not limit or not limit.payload["active"]:
        add("single_payment_limit_exceeded", "limit", "active limit", "missing/inactive", "paymentAmount")
    else:
        single = Decimal(limit.payload["singlePaymentLimit"])
        daily = Decimal(limit.payload["dailyPaymentLimit"])
        committed = Decimal(limit.payload["currentDailyCommittedAmount"])
        if obj.payment_amount > single:
            add("single_payment_limit_exceeded", "limit", single, obj.payment_amount, "paymentAmount")
        if committed + obj.payment_amount > daily:
            add("daily_payment_limit_exceeded", "limit", daily, committed + obj.payment_amount, "paymentAmount")
    if hold and hold.payload["holdStatus"] == "active":
        add("payment_hold_active", "hold", "released", "active", "sourcePaymentRequestId")
    duplicate = PaymentInstructionPrepare.objects.filter(
        source_payment_request_id=obj.source_payment_request_id,
        supplier_id=obj.supplier_id,
        payee_bank_account_id=obj.payee_bank_account_id,
        currency=obj.currency,
        payment_amount=obj.payment_amount,
        planned_execution_date=obj.planned_execution_date,
        status="prepared",
    ).exclude(pk=obj.pk).exists()
    if duplicate:
        add("duplicate_payment_risk", "duplicate", "none", "matched", "paymentIdentity")
    return issues


def validate_instruction_prepare(
    *, user, obj, idempotency_key, expected_version,
    expected_instruction_data_version, expected_source_version,
    explicit_user_action, failure_step=""
):
    _explicit(explicit_user_action)
    _authorize(user, obj.source_payment_request, "payment_instruction_prepare.validate_payment_instruction_prepare")
    request_hash = canonical_hash({
        "id": obj.pk, "version": expected_version,
        "dataVersion": expected_instruction_data_version,
        "sourceVersion": expected_source_version, "action": VALIDATE_ACTION,
    })
    with transaction.atomic():
        idem, replay = _register(
            VALIDATE_ACTION, idempotency_key, obj.source_key, request_hash, obj.tenant_id
        )
        if replay:
            current = PaymentInstructionPrepare.objects.get(pk=idem.target_id)
            return {"classification": "existing_result", "validated": current.status == "validated", "data": serialize_prepare(current)}
        tx = _tx(VALIDATE_ACTION, idempotency_key, obj.source_payment_request, obj.source_key, request_hash)
        lock = _lock(obj.source_key, tx.transaction_id)
        current = PaymentInstructionPrepare.objects.select_for_update().get(pk=obj.pk)
        if current.version != expected_version:
            raise ReconciliationError("VERSION_CONFLICT", "Object version conflict", 409)
        if current.current_instruction_data_version != expected_instruction_data_version:
            raise ReconciliationError("SOURCE_STALE", "Instruction data version conflict", 409)
        if current.status != "prepared":
            raise ReconciliationError(
                "PAYMENT_INSTRUCTION_PREPARE_VALIDATED_IMMUTABLE",
                "Validated target is immutable",
                409,
            )
        source = PaymentRequest.objects.select_for_update().get(pk=current.source_payment_request_id)
        if source.version != expected_source_version or source_hash(source) != current.source_snapshot.source_payment_request_hash:
            raise ReconciliationError("SOURCE_STALE", "Payment request changed", 409)
        snapshot = current.instruction_data_snapshots.get(
            instruction_data_version=current.current_instruction_data_version
        )
        authorities = read_authorities(current, snapshot.planned_execution_date)
        issues = _validation_issues(current, snapshot, authorities)
        execution = PaymentInstructionPrepareValidationExecution.objects.create(
            payment_instruction_prepare=current,
            action_id=f"PIP-VALIDATE-{uuid.uuid4().hex[:20]}",
            idempotency_key=idempotency_key,
            instruction_data_version=snapshot.instruction_data_version,
            source_payment_request_version=source.version,
            source_workflow_version=source.workflow_instance.version,
            source_approval_evidence_hash=_approval_evidence(source),
            validation_policy_version=VALIDATION_POLICY_VERSION,
            status="failed" if issues else "passed",
            result_code="multiple_errors" if len(issues) > 1 else (
                issues[0]["ruleCode"] if issues else "validated"
            ),
            input_hash=request_hash, result_hash=canonical_hash(issues),
            issue_count=len(issues), actor=user, completed_at=timezone.now(),
        )
        for issue in issues:
            PaymentInstructionPrepareValidationIssue.objects.create(
                validation_execution=execution, rule_code=issue["ruleCode"],
                dimension=issue["dimension"], expected=issue["expected"],
                actual=issue["actual"], message=issue["message"],
                source_field=issue["sourceField"],
            )
        current.current_validation_version += 1
        current.validation_issue_count = len(issues)
        current.validation_status = "failed" if issues else "passed"
        current.validation_result_code = execution.result_code
        if not issues:
            current.prepared_at = timezone.now()
            current.prepared_by = user
        else:
            current.version += 1
        current.save(update_fields=[
            "current_validation_version",
            "validation_issue_count",
            "validation_status",
            "validation_result_code",
            "prepared_at",
            "prepared_by",
            "version",
            "updated_at",
        ])
        audit = _audit(tx, VALIDATE_ACTION, idempotency_key, user, source, current, {
            "version": VERSION, "validationPolicyVersion": VALIDATION_POLICY_VERSION,
            "validationExecutionId": execution.pk,
            "resultCode": execution.result_code, "issues": issues,
        })
        if not issues:
            transition_business_object(
                business_object=current,
                object_type=DOCUMENT_TYPE,
                source_state="prepared",
                target_state="validated",
                action_code=VALIDATE_ACTION,
                operator=user,
                reason="Payment instruction preparation validation passed",
                audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
        current.audit_record = audit
        current.save(update_fields=["audit_record", "updated_at"])
        _commit(tx, idem, current, "validated" if not issues else "failed")
        lock.state = "released"
        lock.released_at = timezone.now()
        lock.save(update_fields=["state", "released_at", "acquired_at"])
        _inject("before_database_commit", failure_step)
    _inject("before_response", failure_step)
    return {
        "classification": "validated" if not issues else "blocked",
        "validated": not issues, "data": serialize_prepare(current),
    }


def eligibility(obj):
    latest = obj.instruction_data_snapshots.order_by("-instruction_data_version").first()
    evidence = latest.authority_evidence if latest else {}
    payer = evidence.get("payer", {}).get("payload", {}) if evidence else {}
    payee = evidence.get("payee", {}).get("payload", {}) if evidence else {}
    route = evidence.get("route", {}).get("payload", {}) if evidence else {}
    interface = evidence.get("interface", {}).get("payload", {}) if evidence else {}
    calendar = evidence.get("calendar", {}).get("payload", {}) if evidence else {}
    limit = evidence.get("limit", {}).get("payload", {}) if evidence else {}
    hold = evidence.get("hold", {}).get("payload", {}) if evidence else {}
    state_facts = business_state_transition_facts(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        expected_transitions=EXPECTED_STATE_TRANSITIONS,
        audit_target_type="paymentInstructionPrepare",
    )
    reasons = []
    if not state_facts["stateMachineConsistent"]:
        reasons.append("PIP_STATE_MACHINE_FACTS_INCONSISTENT")
    if obj.status != "validated": reasons.append("PIP_ELIGIBILITY_VALIDATED")
    if obj.instruction_data_status != "complete": reasons.append("PIP_ELIGIBILITY_DATA_COMPLETE")
    if obj.validation_status != "passed" or obj.validation_issue_count:
        reasons.append("PIP_ELIGIBILITY_VALIDATED")
    return {
        "status": obj.status,
        "instructionDataStatus": obj.instruction_data_status,
        "validationStatus": obj.validation_status,
        "routeValid": bool(route.get("active")),
        "bankInterfaceAvailable": bool(
            interface.get("active") and interface.get("paymentEnabled")
            and interface.get("connectionStatus") == "available"
        ),
        "payerAccountValid": bool(payer.get("active") and payer.get("availableForPayment")),
        "payeeAccountValid": bool(payee.get("active") and payee.get("paymentEnabled")),
        "businessDayValid": bool(calendar.get("businessDay") and calendar.get("paymentAllowed")),
        "cutoffValid": not reasons and bool(calendar),
        "singleLimitPassed": bool(limit),
        "dailyLimitPassed": bool(limit),
        "paymentHold": hold.get("holdStatus") == "active",
        "duplicatePaymentRisk": False,
        "nextStepReadiness": f"ready_for_{NEXT_MODULE_CODE}" if not reasons else "blocked",
        "eligible": not reasons,
        "blockingReasons": reasons,
        "serverRevalidationRequired": True,
        "serverDerived": True,
        "stateMachineConsistent": state_facts["stateMachineConsistent"],
        "nextModuleCode": NEXT_MODULE_CODE,
        "nextCanonicalName": NEXT_CANONICAL_NAME,
        "nextRoute": NEXT_ROUTE,
    }


def serialize_prepare(obj, include_issues=True):
    snapshot = obj.instruction_data_snapshots.order_by("-instruction_data_version").first()
    preview = snapshot.previews.order_by("-preview_version").first() if snapshot else None
    validation = obj.validation_executions.order_by("-pk").first()
    issues = []
    if include_issues and validation:
        issues = [{
            "ruleCode": row.rule_code, "dimension": row.dimension,
            "expected": row.expected, "actual": row.actual,
            "severity": row.severity, "blocking": row.blocking,
            "message": row.message, "sourceField": row.source_field,
        } for row in validation.issues.order_by("rule_code")]
    route = snapshot.authority_evidence.get("route") if snapshot else None
    interface = snapshot.authority_evidence.get("interface") if snapshot else None
    state_facts = business_state_transition_facts(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        expected_transitions=EXPECTED_STATE_TRANSITIONS,
        audit_target_type="paymentInstructionPrepare",
    )
    return {
        "id": obj.pk, "prepareNo": obj.prepare_no, "status": obj.status,
        "sourceDocumentType": obj.source_document_type,
        "sourcePaymentRequestId": obj.source_payment_request_id,
        "sourcePaymentRequestNo": obj.source_payment_request_no,
        "sourcePaymentRequestVersion": obj.source_payment_request_version,
        "sourcePaymentRequestPrepareNo": obj.source_payment_request_prepare_no,
        "sourcePayableConfirmationPrepareNo": obj.source_payable_confirmation_prepare_no,
        "sourceApDraftNo": obj.source_ap_draft_no,
        "sourceInvoicePrepareNo": obj.source_invoice_prepare_no,
        "sourceReconciliationNo": obj.source_reconciliation_no,
        "supplierId": obj.supplier_id, "supplierName": obj.supplier_name,
        "legalEntityId": obj.legal_entity_id, "legalEntityName": obj.legal_entity_name,
        "ledgerBookId": obj.ledger_book_id, "currency": obj.currency,
        "paymentAmount": str(obj.payment_amount),
        "plannedExecutionDate": obj.planned_execution_date.isoformat(),
        "paymentMethodCode": obj.payment_method_code,
        "payerBankAccountId": obj.payer_bank_account_id,
        "payeeBankAccountId": obj.payee_bank_account_id,
        "paymentRouteId": obj.payment_route_id,
        "bankInterfaceProfileId": obj.bank_interface_profile_id,
        "priority": obj.priority,
        "instructionDataStatus": obj.instruction_data_status,
        "validationStatus": obj.validation_status,
        "validationResultCode": obj.validation_result_code,
        "validationIssueCount": obj.validation_issue_count,
        "currentInstructionDataVersion": obj.current_instruction_data_version,
        "currentValidationVersion": obj.current_validation_version,
        "version": obj.version,
        "route": {
            **route["payload"],
            "routeStatus": "active" if route["payload"].get("active") else "inactive",
            "authorityVersion": route.get("version"),
        } if route else None,
        "bankInterface": {
            **interface["payload"],
            "authorityVersion": interface.get("version"),
        } if interface else None,
        "instructionData": {
            "plannedExecutionDate": snapshot.planned_execution_date.isoformat(),
            "plannedExecutionTime": snapshot.planned_execution_time.isoformat(),
            "paymentPurpose": snapshot.payment_purpose,
            "paymentSummary": snapshot.payment_summary,
            "instructionReference": snapshot.instruction_reference,
            "dataHash": snapshot.data_hash,
        } if snapshot else None,
        "preview": {
            "debtorName": preview.debtor_name,
            "debtorAccountMasked": preview.debtor_account_masked,
            "creditorName": preview.creditor_name,
            "creditorAccountMasked": preview.creditor_account_masked,
            "currency": preview.currency, "amount": str(preview.amount),
            "paymentMethodCode": preview.payment_method_code,
            "routeCode": preview.route_code, "channelCode": preview.channel_code,
            "executionDate": preview.execution_date.isoformat(),
            "paymentReference": preview.payment_reference,
            "purpose": preview.purpose, "previewHash": preview.preview_hash,
            "readOnly": True, "sentExternally": False,
            "formalPaymentInstructionCreated": False,
        } if preview else None,
        "validation": {
            "executionId": validation.pk if validation else None,
            "status": validation.status if validation else "not_validated",
            "resultCode": validation.result_code if validation else "not_validated",
            "ruleCount": 16, "passedCount": 16 - len(issues),
            "blockedCount": len(issues), "issueCount": len(issues),
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
        raise ReconciliationError("PIP_IDEMPOTENCY_NOT_FOUND", "Result not found", 404)
    return {
        "classification": "existing_result", "actionCode": action_code,
        "data": serialize_prepare(PaymentInstructionPrepare.objects.get(pk=idem.target_id)),
    }
