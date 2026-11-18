import uuid
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from payment_request_prepare.models import PaymentHoldAuthority, PaymentRequestPrepare
from payment_request_prepare.providers import read_all_payment_authorities
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
from workflow_runtime.facts import business_state_transition_facts
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .models import (
    PaymentRequest,
    PaymentRequestSourceRelation,
    PaymentRequestSourceSnapshot,
    PaymentRequestSubmissionSnapshot,
    PaymentRequestWorkflowRelation,
)


VERSION = "V1.14.2.8.4.7.55"
CANONICAL_NAME = "付款申请"
SOURCE_DOCUMENT_TYPE = "paymentRequestPrepare"
DOCUMENT_TYPE = "payment_request"
GENERATE_ACTION = "GENERATE_PAYMENT_REQUEST"
SUBMIT_ACTION = "SUBMIT_PAYMENT_REQUEST"
APPROVE_ACTION = "APPROVE_PAYMENT_REQUEST"
REJECT_ACTION = "REJECT_PAYMENT_REQUEST"
NUMBER_POLICY_VERSION = "payment-request-sequence-v1"
TRANSACTION_PLAN_ID = "payment-request-atomic-v1"
ALLOWED_STATE_TRANSITIONS = (
    ("prepared", "submitted"),
    ("submitted", "approved"),
    ("submitted", "rejected"),
)
EXPECTED_STATE_TRANSITIONS = {
    "prepared": (),
    "submitted": (("prepared", "submitted", SUBMIT_ACTION),),
    "approved": (
        ("prepared", "submitted", SUBMIT_ACTION),
        ("submitted", "approved", APPROVE_ACTION),
    ),
    "rejected": (
        ("prepared", "submitted", SUBMIT_ACTION),
        ("submitted", "rejected", REJECT_ACTION),
    ),
}

GENERATE_FAILURE_STEPS = (
    "authentication", "business_gate", "idempotency", "persistent_lock",
    "source_reload", "version_check", "target_check", "number_reservation",
    "target_insert", "source_snapshot", "source_relation", "transaction_status",
    "audit", "idempotency_committed", "number_consumed", "database_commit",
    "response_lost",
)
SUBMIT_FAILURE_STEPS = (
    "authentication", "permission", "object_read", "version_check", "idempotency",
    "persistent_lock", "source_reload", "provider_read", "approval_policy",
    "approval_route", "submission_snapshot", "workflow_instance", "first_tasks",
    "status_update", "audit", "database_commit", "response_lost",
)
APPROVAL_FAILURE_STEPS = (
    "authentication", "approval_permission", "segregation", "task_read",
    "step_check", "version_check", "persistent_lock", "locked_reload",
    "source_reload", "decision_insert", "task_complete", "next_task",
    "approved_update", "audit", "idempotency_committed", "database_commit",
    "response_lost",
)
REJECTION_FAILURE_STEPS = (
    "authentication", "task_read", "reject_decision", "remaining_tasks_close",
    "rejected_update", "audit", "idempotency_committed", "database_commit",
    "response_lost",
)


def _inject(step, failure_step):
    if step == failure_step:
        raise ReconciliationError("PAYREQ_INJECTED_FAILURE", f"Injected failure at {step}", 409)


def _require_explicit(value):
    if value is not True:
        raise ReconciliationError(
            "PAYREQ_EXPLICIT_USER_ACTION_REQUIRED", "Explicit user action is required", 400
        )


def _authorize(user, permission):
    if not user or not user.is_authenticated:
        raise ReconciliationError("PAYREQ_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not user.is_superuser and not user.has_perm(permission):
        raise ReconciliationError("PAYREQ_AUTH_PERMISSION_DENIED", "Permission denied", 403)


def _feature_gate(tenant_id):
    if not getattr(settings, "PCE_PAYMENT_REQUEST_FEATURE_ENABLED", False):
        raise ReconciliationError("PAYREQ_AUTH_FEATURE_DISABLED", "Feature disabled", 403)
    allowed = getattr(settings, "PCE_PAYMENT_REQUEST_TEST_TENANTS", set())
    if tenant_id not in allowed:
        if not getattr(settings, "PCE_PAYMENT_REQUEST_PRODUCTION_ROLLOUT_ENABLED", False):
            raise ReconciliationError(
                "PAYREQ_AUTH_PRODUCTION_ROLLOUT_DISABLED", "Production rollout disabled", 403
            )


def _source_hash(source):
    data = source.payment_data_snapshots.get(
        payment_data_version=source.current_payment_data_version
    )
    validation = source.validation_executions.get(
        payment_data_version=source.current_payment_data_version
    )
    return canonical_hash({
        "id": source.pk, "prepareNo": source.prepare_no, "version": source.version,
        "status": source.status, "paymentDataVersion": source.current_payment_data_version,
        "validationVersion": source.current_validation_version,
        "paymentDataHash": data.data_hash, "validationHash": validation.result_hash,
    })


def _rule(code, passed, actual, expected, source_field, *, category="business_gate"):
    return {
        "code": code,
        "category": category,
        "status": "passed" if passed else "blocked",
        "severity": "info" if passed else "error",
        "blocking": not passed,
        "actual": str(actual),
        "expected": str(expected),
        "message": f"{code}: {'passed' if passed else 'blocked'}",
        "sourceField": source_field,
        "taskId": None,
        "stepNo": None,
    }


def generation_rules(source, *, check_existing=True):
    data = source.payment_data_snapshots.filter(
        payment_data_version=source.current_payment_data_version
    ).first()
    validation = source.validation_executions.filter(
        payment_data_version=source.current_payment_data_version
    ).first()
    authorities = read_all_payment_authorities(
        payee_bank_account_id=data.payee_bank_account_id if data else "",
        payer_bank_account_id=data.payer_bank_account_id if data else "",
        payment_method_code=data.payment_method_code if data else "",
        planned_payment_date=data.planned_payment_date if data else timezone.now().date(),
        source_object_id=source.source_payable_confirmation_prepare_id,
    ) if data else {}
    hold = authorities.get("hold").payload if authorities.get("hold") else {}
    rules = [
        _rule("PAYREQ_GATE_SOURCE_EXISTS", bool(source), bool(source), True, "sourcePaymentRequestPrepareId"),
        _rule("PAYREQ_GATE_SOURCE_TYPE_VALID", source.source_document_type == "payableConfirmationPrepare", source.source_document_type, "payableConfirmationPrepare", "sourceDocumentType"),
        _rule("PAYREQ_GATE_PREPARE_PREPARED", source.status == "prepared", source.status, "prepared", "status"),
        _rule("PAYREQ_GATE_PAYMENT_DATA_COMPLETE", source.payment_data_status == "complete", source.payment_data_status, "complete", "paymentDataStatus"),
        _rule("PAYREQ_GATE_PREPARE_VALIDATED", source.validation_status == "passed" and source.validation_result_code == "validated" and source.validation_issue_count == 0, f"{source.validation_status}/{source.validation_result_code}/{source.validation_issue_count}", "passed/validated/0", "validationStatus"),
        _rule("PAYREQ_GATE_AMOUNT_MATCH", bool(data and data.payment_amount == source.payable_amount and data.payment_amount > 0), data.payment_amount if data else None, source.payable_amount, "paymentAmount"),
        _rule("PAYREQ_GATE_CURRENCY_MATCH", bool(data and data.currency == source.currency), data.currency if data else None, source.currency, "currency"),
        _rule("PAYREQ_GATE_BANK_ACCOUNTS_CURRENT", bool(authorities.get("payee") and authorities.get("payer") and authorities["payee"].payload["active"] and authorities["payer"].payload["active"]), "current" if authorities.get("payee") and authorities.get("payer") else "missing", "current", "bankAccounts"),
        _rule("PAYREQ_GATE_PAYMENT_METHOD_CURRENT", bool(authorities.get("method") and authorities["method"].payload["active"]), bool(authorities.get("method")), True, "paymentMethodCode"),
        _rule("PAYREQ_GATE_PAYMENT_DATE_CURRENT", bool(authorities.get("calendar") and authorities["calendar"].payload["paymentAllowed"]), bool(authorities.get("calendar")), True, "plannedPaymentDate"),
        _rule("PAYREQ_GATE_NO_PAYMENT_HOLD", hold.get("holdStatus") != "active" and not hold.get("releaseRequired"), hold.get("holdStatus", "missing"), "released", "paymentHold"),
        _rule("PAYREQ_GATE_SOURCE_VERSIONS_CURRENT", bool(validation and validation.payment_data_version == source.current_payment_data_version and validation.source_confirmation_version == source.source_payable_confirmation_prepare.version), "current" if validation else "missing", "current", "sourceVersions"),
        _rule("PAYREQ_GATE_NO_EXISTING_TARGET", not (check_existing and hasattr(source, "payment_request")), hasattr(source, "payment_request"), False, "existingTarget"),
        _rule("PAYREQ_GATE_AUDIT_COMPLETE", bool(source.audit_record_id and source.business_transaction_id), bool(source.audit_record_id), True, "auditRecord"),
    ]
    return rules, data, validation, authorities


def _existing(action_code, idempotency_key, request_hash):
    idem = BusinessActionIdempotency.objects.filter(
        action_code=action_code, idempotency_key=idempotency_key
    ).first()
    if not idem:
        return None
    if idem.request_hash != request_hash:
        raise ReconciliationError("PAYREQ_IDEMPOTENCY_PAYLOAD_CONFLICT", "Payload conflict", 409)
    if idem.status == BusinessActionIdempotency.Status.COMMITTED and idem.target_id:
        return PaymentRequest.objects.get(pk=idem.target_id)
    raise ReconciliationError("PAYREQ_IN_PROGRESS", "Action in progress", 409, True)


def _number(source, idempotency_key):
    period = timezone.now().date().strftime("%Y%m")
    # The reservation table enforces global number uniqueness. The sequence
    # scope is therefore tenant-wide for this document type and period; legal
    # entity and ledger remain immutable reservation attributes.
    scope = f"{DOCUMENT_TYPE}:{source.tenant_id}:{period}"
    sequence, _ = BusinessDocumentNumberSequence.objects.select_for_update().get_or_create(
        number_scope=scope, defaults={"current_value": 0}
    )
    sequence.current_value += 1
    sequence.save(update_fields=["current_value", "updated_at"])
    number = f"PRQ{period}{sequence.current_value:08d}"
    reservation = BusinessDocumentNumberReservation.objects.create(
        document_type=DOCUMENT_TYPE, number_policy_version=NUMBER_POLICY_VERSION,
        number_scope=scope, legal_entity_id=source.legal_entity_id,
        ledger_book_id=source.ledger_book_id, reserved_number=number,
        tenant_id=source.tenant_id, accounting_period=period[:4] + "-" + period[4:],
        idempotency_key=idempotency_key,
        status=BusinessDocumentNumberReservation.Status.RESERVED,
        reusable=False,
    )
    return number, reservation


def _transaction(action, key, source_key, tenant_id, result_hash=""):
    return BusinessActionTransaction.objects.create(
        transaction_id=f"PAYREQTX-{uuid.uuid4().hex}", action_code=action,
        idempotency_key=key, tenant_id=tenant_id, source_key=source_key,
        command_id=f"PAYREQCMD-{uuid.uuid4().hex}", transaction_plan_id=TRANSACTION_PLAN_ID,
        review_id=f"PAYREQ-REVIEW-{uuid.uuid4().hex[:12]}", review_hash=canonical_hash({"action": action, "key": key}),
        status=BusinessActionTransaction.Status.IN_PROGRESS, outcome="pending",
        commit_status="not_committed", recovery_status="not_required",
        result_hash=result_hash,
    )


def _audit(tx, action, key, actor, obj, evidence):
    reconciliation = PurchaseReconciliation.objects.get(pk=obj.source_reconciliation_id)
    return BusinessActionAuditRecord.objects.create(
        transaction=tx, action_code=action, tenant_id=obj.tenant_id, actor=actor,
        source_key=obj.source_key, reconciliation=reconciliation, result="committed",
        target_type="PaymentRequest", target_id=obj.pk, target_no=obj.request_no,
        review_id=tx.review_id, review_hash=tx.review_hash, command_id=tx.command_id,
        idempotency_key=key, actor_name=getattr(actor, "username", str(actor.pk)),
        tenant_or_scope=f"{obj.tenant_id}:{obj.legal_entity_id}",
        evidence_hash=canonical_hash(evidence), evidence=evidence,
    )


def _commit(tx, idem, obj, outcome):
    result_hash = canonical_hash({
        "requestNo": obj.request_no, "status": obj.status,
        "approvalStatus": obj.approval_status, "version": obj.version,
    })
    tx.status = BusinessActionTransaction.Status.COMMITTED
    tx.outcome = outcome
    tx.commit_status = "committed"
    tx.result_hash = result_hash
    tx.save(update_fields=["status", "outcome", "commit_status", "result_hash", "updated_at"])
    idem.status = BusinessActionIdempotency.Status.COMMITTED
    idem.target_type = "PaymentRequest"
    idem.target_id = obj.pk
    idem.target_no = obj.request_no
    idem.result_reference = f"payment_request:{obj.pk}"
    idem.transaction_id = tx.transaction_id
    idem.save(update_fields=[
        "status", "target_type", "target_id", "target_no",
        "result_reference", "transaction_id", "updated_at",
    ])


def generate_payment_request(*, user, source, idempotency_key, expected_source_version, explicit_user_action, failure_step=""):
    _require_explicit(explicit_user_action)
    _authorize(user, "payment_request.generate_payment_request")
    _feature_gate(source.tenant_id)
    _inject("authentication", failure_step)
    request_hash = canonical_hash({
        "sourceId": source.pk, "expectedSourceVersion": expected_source_version
    })
    prior = _existing(GENERATE_ACTION, idempotency_key, request_hash)
    if prior:
        return {"classification": "existing_result", "created": False, "data": serialize_payment_request(prior)}
    with transaction.atomic():
        rules, data, validation, _ = generation_rules(source)
        blocked = [rule for rule in rules if rule["blocking"]]
        if blocked:
            raise ReconciliationError(blocked[0]["code"], blocked[0]["message"], 409)
        _inject("business_gate", failure_step)
        if source.version != expected_source_version:
            raise ReconciliationError("PAYREQ_GATE_SOURCE_VERSIONS_CURRENT", "Source version changed", 409)
        idem = BusinessActionIdempotency.objects.create(
            action_code=GENERATE_ACTION, idempotency_key=idempotency_key,
            tenant_id=source.tenant_id, source_key=f"paymentRequestPrepare:{source.pk}",
            request_hash=request_hash, status=BusinessActionIdempotency.Status.IN_PROGRESS,
        )
        _inject("idempotency", failure_step)
        lock, _ = BusinessActionSourceLock.objects.get_or_create(
            lock_key=f"payment_request:{source.pk}",
            defaults={"owner_transaction_id": f"LOCK-{uuid.uuid4().hex}", "state": "released"},
        )
        lock.owner_transaction_id = f"PAYREQLOCK-{uuid.uuid4().hex}"
        lock.state = "acquired"
        lock.released_at = None
        lock.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
        _inject("persistent_lock", failure_step)
        source = PaymentRequestPrepare.objects.select_related(
            "source_payable_confirmation_prepare", "business_transaction", "audit_record"
        ).get(pk=source.pk)
        data = source.payment_data_snapshots.get(payment_data_version=source.current_payment_data_version)
        validation = source.validation_executions.get(payment_data_version=source.current_payment_data_version)
        _inject("source_reload", failure_step)
        if source.version != expected_source_version:
            raise ReconciliationError("PAYREQ_GATE_SOURCE_VERSIONS_CURRENT", "Source version changed", 409)
        _inject("version_check", failure_step)
        if PaymentRequest.objects.filter(source_payment_request_prepare=source).exists():
            raise ReconciliationError("PAYREQ_GATE_NO_EXISTING_TARGET", "Target exists", 409)
        _inject("target_check", failure_step)
        request_no, reservation = _number(source, idempotency_key)
        _inject("number_reservation", failure_step)
        source_key = f"paymentRequestPrepare:{source.pk}"
        tx = _transaction(GENERATE_ACTION, idempotency_key, source_key, source.tenant_id)
        _inject("transaction_status", failure_step)
        obj = create_business_object_with_initial_state(
            model=PaymentRequest,
            initial_state="prepared",
            request_no=request_no, source_payment_request_prepare=source,
            source_payment_request_prepare_no=source.prepare_no,
            source_prepare_version=source.version,
            source_payment_data_version=source.current_payment_data_version,
            source_validation_version=source.current_validation_version,
            source_payable_confirmation_prepare_id=source.source_payable_confirmation_prepare_id,
            source_payable_confirmation_prepare_no=source.source_payable_confirmation_prepare_no,
            source_ap_draft_id=source.source_ap_draft_id, source_ap_draft_no=source.source_ap_draft_no,
            source_invoice_prepare_id=source.source_invoice_prepare_id,
            source_invoice_prepare_no=source.source_invoice_prepare_no,
            source_reconciliation_id=source.source_reconciliation_id,
            source_reconciliation_no=source.source_reconciliation_no,
            source_key=source_key, tenant_id=source.tenant_id, company_id=source.company_id,
            supplier_id=source.supplier_id, supplier_name=source.supplier_name,
            legal_entity_id=source.legal_entity_id, legal_entity_name=source.legal_entity_name,
            ledger_book_id=source.ledger_book_id, currency=source.currency,
            payment_amount=data.payment_amount, planned_payment_date=data.planned_payment_date,
            payment_method_code=data.payment_method_code,
            payee_bank_account_id=data.payee_bank_account_id,
            payer_bank_account_id=data.payer_bank_account_id,
            payment_purpose=data.payment_purpose, payment_summary=data.payment_summary,
            applicant=user, applicant_name=getattr(user, "username", str(user.pk)),
            applicant_department_id=str(getattr(user, "department_id", "") or ""),
            idempotency_key=idempotency_key, number_reservation=reservation,
            business_transaction=tx, created_by=user,
        )
        _inject("target_insert", failure_step)
        PaymentRequestSourceSnapshot.objects.create(
            payment_request=obj, source_payment_request_prepare_id=source.pk,
            source_payment_request_prepare_no=source.prepare_no,
            source_prepare_version=source.version, source_payment_data_snapshot_id=data.pk,
            source_payment_data_version=source.current_payment_data_version,
            source_validation_execution_id=validation.pk,
            source_validation_version=source.current_validation_version,
            source_payable_confirmation_prepare_id=source.source_payable_confirmation_prepare_id,
            source_ap_draft_id=source.source_ap_draft_id,
            source_invoice_prepare_id=source.source_invoice_prepare_id,
            source_reconciliation_id=source.source_reconciliation_id,
            source_prepare_hash=_source_hash(source), source_payment_data_hash=data.data_hash,
            source_validation_hash=validation.result_hash,
            source_eligibility_hash=canonical_hash(serialize_source_eligibility(source)),
        )
        _inject("source_snapshot", failure_step)
        PaymentRequestSourceRelation.objects.create(
            payment_request=obj, source_id=source.pk, source_no=source.prepare_no,
            source_version=source.version, source_hash=_source_hash(source),
        )
        _inject("source_relation", failure_step)
        audit = _audit(tx, GENERATE_ACTION, idempotency_key, user, obj, {
            "version": VERSION, "action": GENERATE_ACTION, "rules": rules,
            "sourceBusinessStatusUnchanged": source.status == "prepared",
        })
        obj.audit_record = audit
        obj.save(update_fields=["audit_record", "updated_at"])
        _inject("audit", failure_step)
        reservation.status = BusinessDocumentNumberReservation.Status.CONSUMED
        reservation.consumed_at = timezone.now()
        reservation.save(update_fields=["status", "consumed_at"])
        _inject("number_consumed", failure_step)
        _commit(tx, idem, obj, "generated")
        _inject("idempotency_committed", failure_step)
        lock.state = "released"
        lock.released_at = timezone.now()
        lock.save(update_fields=["state", "released_at", "acquired_at"])
        _inject("database_commit", failure_step)
    _inject("response_lost", failure_step)
    return {"classification": "generated", "created": True, "data": serialize_payment_request(obj)}


def _submission_rules(obj, policy, route, sod):
    return [
        _rule("PAYREQ_SUBMIT_APPLICATION_REASON_REQUIRED", bool(obj.application_reason.strip()), bool(obj.application_reason.strip()), True, "applicationReason", category="submission"),
        _rule("PAYREQ_SUBMIT_APPROVAL_POLICY_FOUND", bool(policy), bool(policy), True, "approvalPolicy", category="submission"),
        _rule("PAYREQ_SUBMIT_APPROVAL_ROUTE_VALID", bool(route and route.payload.get("steps") and len(route.payload["steps"]) == policy.payload["stepCount"] if policy and route else False), len(route.payload["steps"]) if route else 0, policy.payload["stepCount"] if policy else 0, "approvalRoute", category="submission"),
        _rule("PAYREQ_SUBMIT_SEGREGATION_VALID", bool(sod and sod.payload["applicantCannotApprove"]), bool(sod), True, "segregationOfDuties", category="submission"),
        _rule("PAYREQ_SUBMIT_SOURCE_CURRENT", source_is_current(obj), source_is_current(obj), True, "sourceVersions", category="submission"),
        _rule("PAYREQ_SUBMIT_NO_FATAL_ISSUE", True, False, False, "fatalIssues", category="submission"),
    ]


def source_is_current(obj):
    source = obj.source_payment_request_prepare
    return (
        source.status == "prepared"
        and source.version == obj.source_prepare_version
        and source.current_payment_data_version == obj.source_payment_data_version
        and source.current_validation_version == obj.source_validation_version
    )


def submit_payment_request(*, user, obj, idempotency_key, expected_version, expected_source_prepare_version, expected_payment_data_version, expected_source_validation_version, explicit_user_action, application_reason, failure_step=""):
    _require_explicit(explicit_user_action)
    _authorize(user, "payment_request.submit_payment_request")
    _feature_gate(obj.tenant_id)
    _inject("authentication", failure_step)
    _inject("permission", failure_step)
    request_hash = canonical_hash({
        "id": obj.pk, "expectedVersion": expected_version,
        "expectedSourcePrepareVersion": expected_source_prepare_version,
        "expectedPaymentDataVersion": expected_payment_data_version,
        "expectedSourceValidationVersion": expected_source_validation_version,
        "applicationReason": application_reason,
    })
    prior = _existing(SUBMIT_ACTION, idempotency_key, request_hash)
    if prior:
        return {"classification": "existing_result", "submitted": False, "data": serialize_payment_request(prior)}
    with transaction.atomic():
        obj = PaymentRequest.objects.select_related(
            "source_payment_request_prepare"
        ).get(pk=obj.pk)
        _inject("object_read", failure_step)
        if obj.status != "prepared" or obj.approval_status != "not_started":
            raise ReconciliationError("PAYREQ_SUBMIT_STATE_INVALID", "Only prepared can be submitted", 409)
        if obj.version != expected_version:
            raise ReconciliationError("PAYREQ_SUBMIT_VERSION_CONFLICT", "Version conflict", 409)
        _inject("version_check", failure_step)
        source = obj.source_payment_request_prepare
        if (
            source.version != expected_source_prepare_version
            or source.current_payment_data_version != expected_payment_data_version
            or source.current_validation_version != expected_source_validation_version
        ):
            raise ReconciliationError("PAYREQ_SUBMIT_SOURCE_CURRENT", "Source changed", 409)
        _inject("source_reload", failure_step)
        obj.application_reason = str(application_reason or "").strip()
        policy = ApprovalPolicyProvider().read(DOCUMENT_TYPE, obj.legal_entity_id, obj.payment_amount, obj.currency)
        _inject("provider_read", failure_step)
        if not policy:
            raise ReconciliationError("PAYREQ_SUBMIT_APPROVAL_POLICY_FOUND", "Approval policy missing", 409)
        _inject("approval_policy", failure_step)
        route = ApprovalRouteProvider().read(policy.payload["policyId"])
        sod = SegregationOfDutiesProvider().read(DOCUMENT_TYPE)
        _inject("approval_route", failure_step)
        rules = _submission_rules(obj, policy, route, sod)
        blocked = [rule for rule in rules if rule["blocking"]]
        if blocked:
            raise ReconciliationError(blocked[0]["code"], blocked[0]["message"], 409)
        idem = BusinessActionIdempotency.objects.create(
            action_code=SUBMIT_ACTION, idempotency_key=idempotency_key,
            tenant_id=obj.tenant_id, source_key=obj.source_key,
            request_hash=request_hash, status=BusinessActionIdempotency.Status.IN_PROGRESS,
        )
        _inject("idempotency", failure_step)
        lock, _ = BusinessActionSourceLock.objects.get_or_create(
            lock_key=f"payment_request_submit:{obj.pk}",
            defaults={"owner_transaction_id": f"LOCK-{uuid.uuid4().hex}", "state": "released"},
        )
        lock.owner_transaction_id = f"PAYREQSUBMIT-{uuid.uuid4().hex}"
        lock.state = "acquired"
        lock.released_at = None
        lock.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
        _inject("persistent_lock", failure_step)
        tx = _transaction(SUBMIT_ACTION, idempotency_key, obj.source_key, obj.tenant_id)
        definition, _ = ProcessDefinition.objects.get_or_create(
            definition_code="PAYMENT_REQUEST_APPROVAL", document_type=DOCUMENT_TYPE, version=1,
            defaults={"active": True, "definition_hash": canonical_hash({"documentType": DOCUMENT_TYPE, "version": 1})},
        )
        workflow = WorkflowInstance.objects.create(
            instance_no=f"WFI-PAYREQ-{obj.request_no}", process_definition=definition,
            document_type=DOCUMENT_TYPE, document_id=obj.pk, status="pending",
            current_step=1, total_steps=policy.payload["stepCount"],
        )
        _inject("workflow_instance", failure_step)
        steps = route.payload["steps"]
        first = steps[0]
        ApprovalTask.objects.create(
            task_no=f"APT-{obj.request_no}-{first['stepNo']:02d}",
            workflow_instance=workflow, step_no=first["stepNo"],
            required_role_code=first["roleCode"],
            minimum_approvals=first.get("minimumApprovals", 1),
            allow_parallel=first.get("allowParallel", False), status="pending",
        )
        _inject("first_tasks", failure_step)
        source_hash = _source_hash(source)
        submission_hash = canonical_hash({
            "requestNo": obj.request_no, "version": obj.version,
            "applicationReason": obj.application_reason, "routeHash": route.business_hash,
            "sourceHash": source_hash,
        })
        PaymentRequestSubmissionSnapshot.objects.create(
            payment_request=obj, submission_version=1, applicant_user_id=user.pk,
            applicant_department_id=obj.applicant_department_id,
            application_reason=obj.application_reason, payment_purpose=obj.payment_purpose,
            payment_summary=obj.payment_summary, payment_amount=obj.payment_amount,
            currency=obj.currency, planned_payment_date=obj.planned_payment_date,
            approval_policy_id=policy.payload["policyId"],
            approval_policy_version=policy.version,
            approval_route_hash=route.business_hash, source_state_hash=source_hash,
            submission_hash=submission_hash,
        )
        _inject("submission_snapshot", failure_step)
        PaymentRequestWorkflowRelation.objects.create(
            payment_request=obj, workflow_instance=workflow,
            process_definition=definition, process_definition_version=definition.version,
            approval_policy_id=policy.payload["policyId"],
            approval_route_id=route.payload["routeId"],
        )
        obj.approval_status = "pending"
        obj.approval_result_code = "pending"
        obj.submission_readiness = "blocked"
        obj.approval_policy_id = policy.payload["policyId"]
        obj.approval_policy_version = policy.version
        obj.workflow_instance = workflow
        obj.current_approval_step = 1
        obj.total_approval_steps = policy.payload["stepCount"]
        obj.submitted_at = timezone.now()
        obj.submitted_by = user
        obj.save(update_fields=[
            "application_reason",
            "approval_status",
            "approval_result_code",
            "submission_readiness",
            "approval_policy",
            "approval_policy_version",
            "workflow_instance",
            "current_approval_step",
            "total_approval_steps",
            "submitted_at",
            "submitted_by",
            "updated_at",
        ])
        _inject("status_update", failure_step)
        audit = _audit(tx, SUBMIT_ACTION, idempotency_key, user, obj, {
            "version": VERSION, "action": SUBMIT_ACTION, "rules": rules,
            "policy": policy.payload, "route": route.payload,
        })
        transition_business_object(
            business_object=obj,
            object_type=DOCUMENT_TYPE,
            source_state="prepared",
            target_state="submitted",
            action_code=SUBMIT_ACTION,
            operator=user,
            reason="Payment request submitted for approval",
            audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
            workflow_instance=workflow,
            allowed_transitions=ALLOWED_STATE_TRANSITIONS,
        )
        obj.audit_record = audit
        obj.save(update_fields=["audit_record", "updated_at"])
        _inject("audit", failure_step)
        _commit(tx, idem, obj, "submitted")
        lock.state = "released"
        lock.released_at = timezone.now()
        lock.save(update_fields=["state", "released_at", "acquired_at"])
        _inject("database_commit", failure_step)
    _inject("response_lost", failure_step)
    return {"classification": "submitted", "submitted": True, "data": serialize_payment_request(obj)}


def _approval_rules(obj, task, actor, roles, sod):
    rules = [
        _rule("PAYREQ_APPROVE_TASK_EXISTS", bool(task), bool(task), True, "taskId", category="approval"),
        _rule("PAYREQ_APPROVE_TASK_PENDING", task.status == "pending", task.status, "pending", "taskStatus", category="approval"),
        _rule("PAYREQ_APPROVE_STEP_CURRENT", task.step_no == obj.current_approval_step, task.step_no, obj.current_approval_step, "stepNo", category="approval"),
        _rule("PAYREQ_APPROVE_ACTOR_AUTHORIZED", task.required_role_code in roles.payload["roleCodes"], roles.payload["roleCodes"], task.required_role_code, "actorRole", category="approval"),
        _rule("PAYREQ_APPROVE_ACTOR_SCOPE_VALID", obj.legal_entity_id in roles.payload["legalEntityIds"], roles.payload["legalEntityIds"], obj.legal_entity_id, "legalEntityId", category="approval"),
        _rule("PAYREQ_APPROVE_SELF_APPROVAL_BLOCKED", not (sod and sod.payload["applicantCannotApprove"] and actor.pk == obj.applicant_id), actor.pk, f"not {obj.applicant_id}", "actorId", category="approval"),
        _rule("PAYREQ_APPROVE_SOURCE_CURRENT", source_is_current(obj), source_is_current(obj), True, "sourceVersions", category="approval"),
        _rule("PAYREQ_APPROVE_NO_PAYMENT_HOLD", not PaymentHoldAuthority.objects.filter(source_object_id=str(obj.source_payable_confirmation_prepare_id), hold_status="active").exists(), False, False, "paymentHold", category="approval"),
        _rule("PAYREQ_APPROVE_VERSION_CURRENT", True, True, True, "version", category="approval"),
    ]
    for rule in rules:
        rule["taskId"] = task.pk if task else None
        rule["stepNo"] = task.step_no if task else None
    return rules


def decide_payment_request(*, user, obj, task, decision, idempotency_key, expected_payment_request_version, expected_workflow_version, expected_task_version, explicit_user_action, decision_comment, failure_step=""):
    _require_explicit(explicit_user_action)
    permission = "payment_request.approve_payment_request" if decision == "approved" else "payment_request.reject_payment_request"
    action = APPROVE_ACTION if decision == "approved" else REJECT_ACTION
    _authorize(user, permission)
    _feature_gate(obj.tenant_id)
    _inject("authentication", failure_step)
    if decision == "approved":
        _inject("approval_permission", failure_step)
    request_hash = canonical_hash({
        "id": obj.pk, "taskId": task.pk, "decision": decision,
        "expectedPaymentRequestVersion": expected_payment_request_version,
        "expectedWorkflowVersion": expected_workflow_version,
        "expectedTaskVersion": expected_task_version, "comment": decision_comment,
    })
    prior = _existing(action, idempotency_key, request_hash)
    if prior:
        return {"classification": "existing_result", "decided": False, "data": serialize_payment_request(prior)}
    with transaction.atomic():
        obj = PaymentRequest.objects.select_related(
            "workflow_instance", "source_payment_request_prepare"
        ).get(pk=obj.pk)
        task = ApprovalTask.objects.select_related("workflow_instance").get(pk=task.pk)
        _inject("task_read", failure_step)
        if obj.status != "submitted" or obj.approval_status != "pending":
            raise ReconciliationError("PAYREQ_APPROVE_STATE_INVALID", "Request is not pending", 409)
        if (
            obj.version != expected_payment_request_version
            or obj.workflow_instance.version != expected_workflow_version
            or task.version != expected_task_version
        ):
            raise ReconciliationError("PAYREQ_APPROVE_VERSION_CURRENT", "Version conflict", 409)
        _inject("version_check", failure_step)
        roles = UserOrganizationRoleProvider().read(user.pk, obj.legal_entity_id)
        sod = SegregationOfDutiesProvider().read(DOCUMENT_TYPE)
        rules = _approval_rules(obj, task, user, roles, sod)
        if decision == "approved":
            _inject("segregation", failure_step)
            _inject("step_check", failure_step)
        blocked = [rule for rule in rules if rule["blocking"]]
        if blocked:
            raise ReconciliationError(blocked[0]["code"], blocked[0]["message"], 409)
        idem = BusinessActionIdempotency.objects.create(
            action_code=action, idempotency_key=idempotency_key,
            tenant_id=obj.tenant_id, source_key=obj.source_key,
            request_hash=request_hash, status=BusinessActionIdempotency.Status.IN_PROGRESS,
        )
        lock, _ = BusinessActionSourceLock.objects.get_or_create(
            lock_key=f"payment_request_decide:{obj.pk}",
            defaults={"owner_transaction_id": f"LOCK-{uuid.uuid4().hex}", "state": "released"},
        )
        lock.owner_transaction_id = f"PAYREQDECIDE-{uuid.uuid4().hex}"
        lock.state = "acquired"
        lock.released_at = None
        lock.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
        _inject("persistent_lock", failure_step)
        _inject("locked_reload", failure_step)
        _inject("source_reload", failure_step)
        tx = _transaction(action, idempotency_key, obj.source_key, obj.tenant_id)
        decision_row = ApprovalDecision.objects.create(
            task=task, actor=user, decision=decision, comment=decision_comment,
            action_id=action, idempotency_key=idempotency_key,
            decision_hash=canonical_hash({
                "taskId": task.pk, "actorId": user.pk, "decision": decision,
                "comment": decision_comment,
            }),
        )
        _inject("reject_decision" if decision == "rejected" else "decision_insert", failure_step)
        task.status = decision
        task.version += 1
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "version", "completed_at"])
        if decision == "approved":
            _inject("task_complete", failure_step)
        workflow = obj.workflow_instance
        target_status = None
        if decision == "rejected":
            ApprovalTask.objects.filter(
                workflow_instance=workflow, status="pending"
            ).exclude(pk=task.pk).update(status="closed", completed_at=timezone.now())
            _inject("remaining_tasks_close", failure_step)
            target_status = "rejected"
            obj.approval_status = "rejected"
            obj.approval_result_code = "rejected"
            obj.rejected_at = timezone.now()
            obj.final_decision_by = user
            workflow.status = "rejected"
            workflow.completed_at = timezone.now()
            _inject("rejected_update", failure_step)
        elif task.step_no >= workflow.total_steps:
            target_status = "approved"
            obj.approval_status = "approved"
            obj.approval_result_code = "approved"
            obj.approved_at = timezone.now()
            obj.final_decision_by = user
            obj.submission_readiness = "ready"
            workflow.status = "approved"
            workflow.completed_at = timezone.now()
            _inject("approved_update", failure_step)
        else:
            relation = obj.workflow_relations.select_related("approval_route").get()
            next_step = relation.approval_route.steps[task.step_no]
            workflow.current_step = task.step_no + 1
            obj.current_approval_step = workflow.current_step
            ApprovalTask.objects.create(
                task_no=f"APT-{obj.request_no}-{workflow.current_step:02d}",
                workflow_instance=workflow, step_no=workflow.current_step,
                required_role_code=next_step["roleCode"],
                minimum_approvals=next_step.get("minimumApprovals", 1),
                allow_parallel=next_step.get("allowParallel", False), status="pending",
            )
            _inject("next_task", failure_step)
        workflow.version += 1
        workflow.save()
        if target_status is None:
            obj.version += 1
        obj.save()
        audit = _audit(tx, action, idempotency_key, user, obj, {
            "version": VERSION, "action": action, "rules": rules,
            "decisionId": decision_row.pk, "decision": decision,
        })
        if target_status is not None:
            transition_business_object(
                business_object=obj,
                object_type=DOCUMENT_TYPE,
                source_state="submitted",
                target_state=target_status,
                action_code=action,
                operator=user,
                reason=(
                    "Payment request approval completed"
                    if target_status == "approved"
                    else "Payment request rejected"
                ),
                audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                workflow_instance=workflow,
                allowed_transitions=ALLOWED_STATE_TRANSITIONS,
            )
        obj.audit_record = audit
        obj.save(update_fields=["audit_record", "updated_at"])
        _inject("audit", failure_step)
        _commit(tx, idem, obj, decision)
        _inject("idempotency_committed", failure_step)
        lock.state = "released"
        lock.released_at = timezone.now()
        lock.save(update_fields=["state", "released_at", "acquired_at"])
        _inject("database_commit", failure_step)
    _inject("response_lost", failure_step)
    return {"classification": decision, "decided": True, "data": serialize_payment_request(obj)}


def serialize_source_eligibility(source):
    rules, _, _, _ = generation_rules(source, check_existing=False)
    return {
        "eligible": not any(rule["blocking"] for rule in rules),
        "nextStepReadiness": "ready_for_payment_request" if not any(rule["blocking"] for rule in rules) else "blocked",
        "blockingReasons": [rule["code"] for rule in rules if rule["blocking"]],
        "rules": rules,
        "serverDerived": True,
    }


def build_instruction_prepare_eligibility(obj):
    workflow = obj.workflow_instance
    pending = workflow.tasks.filter(status="pending").count() if workflow else 0
    source_current = source_is_current(obj)
    payment_hold = PaymentHoldAuthority.objects.filter(
        source_object_id=str(obj.source_payable_confirmation_prepare_id),
        hold_status="active",
    ).exists()
    state_facts = business_state_transition_facts(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        expected_transitions=EXPECTED_STATE_TRANSITIONS,
        audit_target_type="PaymentRequest",
        expected_workflow_instance_id=(
            obj.workflow_instance_id if obj.status != "prepared" else None
        ),
    )
    reasons = []
    if not state_facts["stateMachineConsistent"]:
        reasons.append("PAYREQ_STATE_MACHINE_FACTS_INCONSISTENT")
    if obj.status != "approved": reasons.append("PAYREQ_ELIGIBILITY_STATUS_APPROVED")
    if obj.approval_status != "approved": reasons.append("PAYREQ_ELIGIBILITY_APPROVAL_APPROVED")
    if obj.approval_result_code != "approved": reasons.append("PAYREQ_ELIGIBILITY_RESULT_APPROVED")
    if pending: reasons.append("PAYREQ_ELIGIBILITY_TASKS_COMPLETE")
    if not source_current: reasons.append("PAYREQ_ELIGIBILITY_SOURCE_CURRENT")
    if payment_hold: reasons.append("PAYREQ_ELIGIBILITY_NO_PAYMENT_HOLD")
    return {
        "status": obj.status, "approvalStatus": obj.approval_status,
        "approvalResultCode": obj.approval_result_code,
        "completedApprovalSteps": workflow.tasks.filter(status="approved").count() if workflow else 0,
        "totalApprovalSteps": obj.total_approval_steps,
        "paymentHold": payment_hold, "sourceCurrent": source_current,
        "nextStepReadiness": "ready_for_payment_instruction_prepare" if not reasons else "blocked",
        "eligible": not reasons, "blockingReasons": reasons, "serverDerived": True,
        "stateMachineConsistent": state_facts["stateMachineConsistent"],
        "paymentInstructionPrepareCreated": False,
    }


def serialize_payment_request(obj):
    workflow = obj.workflow_instance
    tasks = list(workflow.tasks.order_by("step_no")) if workflow else []
    decisions = list(
        ApprovalDecision.objects.filter(task__workflow_instance=workflow)
        .select_related("actor", "task").order_by("created_at")
    ) if workflow else []
    route = obj.workflow_relations.select_related("approval_route").first()
    state_facts = business_state_transition_facts(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        expected_transitions=EXPECTED_STATE_TRANSITIONS,
        audit_target_type="PaymentRequest",
        expected_workflow_instance_id=(
            obj.workflow_instance_id if obj.status != "prepared" else None
        ),
    )
    return {
        "id": obj.pk, "requestNo": obj.request_no, "status": obj.status,
        "approvalStatus": obj.approval_status,
        "approvalResultCode": obj.approval_result_code,
        "submissionReadiness": obj.submission_readiness,
        "sourceDocumentType": obj.source_document_type,
        "sourcePaymentRequestPrepareId": obj.source_payment_request_prepare_id,
        "sourcePaymentRequestPrepareNo": obj.source_payment_request_prepare_no,
        "sourcePrepareVersion": obj.source_prepare_version,
        "sourcePaymentDataVersion": obj.source_payment_data_version,
        "sourceValidationVersion": obj.source_validation_version,
        "sourcePayableConfirmationPrepareNo": obj.source_payable_confirmation_prepare_no,
        "sourceApDraftNo": obj.source_ap_draft_no,
        "sourceInvoicePrepareNo": obj.source_invoice_prepare_no,
        "sourceReconciliationNo": obj.source_reconciliation_no,
        "sourceKey": obj.source_key, "supplierId": obj.supplier_id,
        "supplierName": obj.supplier_name, "legalEntityId": obj.legal_entity_id,
        "legalEntityName": obj.legal_entity_name, "ledgerBookId": obj.ledger_book_id,
        "currency": obj.currency, "paymentAmount": str(obj.payment_amount),
        "plannedPaymentDate": obj.planned_payment_date.isoformat(),
        "paymentMethodCode": obj.payment_method_code,
        "paymentPurpose": obj.payment_purpose, "paymentSummary": obj.payment_summary,
        "applicantUserId": obj.applicant_id, "applicantName": obj.applicant_name,
        "applicantDepartmentId": obj.applicant_department_id,
        "applicationReason": obj.application_reason,
        "approvalPolicyId": obj.approval_policy_id,
        "approvalPolicyVersion": obj.approval_policy_version,
        "workflowInstanceId": workflow.pk if workflow else None,
        "workflowVersion": workflow.version if workflow else None,
        "currentApprovalStep": obj.current_approval_step,
        "totalApprovalSteps": obj.total_approval_steps, "version": obj.version,
        "idempotencyStatus": "committed",
        "numberReservationStatus": obj.number_reservation.status,
        "transactionStatus": obj.business_transaction.status,
        "auditStatus": "committed" if obj.audit_record_id else "missing",
        "approvalRoute": route.approval_route.steps if route else [],
        "approvalTasks": [{
            "id": task.pk, "taskNo": task.task_no, "stepNo": task.step_no,
            "requiredRoleCode": task.required_role_code, "status": task.status,
            "version": task.version,
        } for task in tasks],
        "approvalHistory": [{
            "actorId": row.actor_id, "actorName": row.actor.username,
            "decision": row.decision, "comment": row.comment,
            "stepNo": row.task.step_no, "taskNo": row.task.task_no,
            "createdAt": row.created_at.isoformat(),
        } for row in decisions],
        "eligibility": build_instruction_prepare_eligibility(obj),
        **state_facts,
        "currentStateSource": "server",
    }


def recover_action_result(action_code, idempotency_key):
    idem = BusinessActionIdempotency.objects.filter(
        action_code=action_code, idempotency_key=idempotency_key
    ).first()
    if not idem or not idem.target_id:
        raise ReconciliationError("PAYREQ_IDEMPOTENCY_NOT_FOUND", "Result not found", 404)
    return {
        "classification": "existing_result", "actionCode": action_code,
        "data": serialize_payment_request(PaymentRequest.objects.get(pk=idem.target_id)),
    }
