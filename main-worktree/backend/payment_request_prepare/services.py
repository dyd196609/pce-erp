import time
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from payable_confirmation_prepare.models import PayableConfirmationPrepare
from payable_confirmation_prepare.services import (
    build_payment_request_prepare_eligibility as build_source_eligibility,
)
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
    PaymentRequestDataSnapshot,
    PaymentRequestPrepare,
    PaymentRequestPrepareSourceRelation,
    PaymentRequestPrepareSourceSnapshot,
    PaymentRequestPrepareValidationExecution,
    PaymentRequestPrepareValidationIssue,
)
from .providers import read_all_payment_authorities


VERSION = "V1.14.2.8.4.7.55"
CANONICAL_NAME = "付款申请准备"
SOURCE_DOCUMENT_TYPE = "payableConfirmationPrepare"
DOCUMENT_TYPE = "payment_request_prepare"
GENERATE_ACTION = "GENERATE_PAYMENT_REQUEST_PREPARE"
SAVE_ACTION = "SAVE_PAYMENT_REQUEST_PREPARE_DATA"
VALIDATE_ACTION = "VALIDATE_PAYMENT_REQUEST_PREPARE"
NUMBER_POLICY_VERSION = "payment-request-prepare-sequence-v1"
VALIDATION_POLICY_VERSION = "payment-request-prepare-validation-v1"
TRANSACTION_PLAN_ID = "payment-request-prepare-atomic-v1"
ALLOWED_STATE_TRANSITIONS = (("draft", "prepared"),)
EXPECTED_STATE_TRANSITIONS = {
    "draft": (),
    "prepared": (("draft", "prepared", VALIDATE_ACTION),),
}

GENERATE_FAILURE_STEPS = (
    "after_authorization",
    "after_business_gate",
    "after_idempotency_registration",
    "after_persistent_lock",
    "after_source_reload",
    "after_version_check",
    "after_target_check",
    "after_number_reservation",
    "after_target_insert",
    "after_source_snapshot_insert",
    "after_source_relation_insert",
    "after_audit_insert",
    "after_idempotency_committed",
    "after_number_consumed",
    "before_database_commit",
    "before_response",
)
SAVE_FAILURE_STEPS = (
    "after_authorization",
    "after_idempotency_registration",
    "after_persistent_lock",
    "after_prepare_reload",
    "after_provider_read",
    "after_version_check",
    "after_payment_data_snapshot_insert",
    "after_prepare_update",
    "after_audit_insert",
    "after_idempotency_committed",
    "before_database_commit",
    "before_response",
)
VALIDATE_FAILURE_STEPS = (
    "after_authorization",
    "after_idempotency_registration",
    "after_persistent_lock",
    "after_prepare_reload",
    "after_payment_data_reload",
    "after_source_reload",
    "after_provider_read",
    "after_version_check",
    "after_validation_execution_insert",
    "after_issue_insert",
    "after_prepared_update",
    "after_audit_insert",
    "after_idempotency_committed",
    "before_database_commit",
    "before_response",
)


def _decimal(value, field_name):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReconciliationError(
            "PRP_DATA_PAYMENT_AMOUNT_INVALID",
            f"{field_name} must be a valid decimal",
            400,
        ) from exc


def _date(value, field_name):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ReconciliationError(
            "PRP_DATA_PAYMENT_DATE_REQUIRED",
            f"{field_name} must use YYYY-MM-DD",
            400,
        ) from exc


def _require_explicit(explicit_user_action):
    if explicit_user_action is not True:
        raise ReconciliationError(
            "PRP_EXPLICIT_USER_ACTION_REQUIRED",
            "An explicit user action is required",
            400,
        )


def _authorize(user, source, permission):
    if not user or not user.is_authenticated:
        raise ReconciliationError("PRP_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not (user.is_superuser or user.has_perm(permission)):
        raise ReconciliationError("PRP_AUTH_PERMISSION_DENIED", "Permission required", 403)
    if not user.is_superuser and user.company_id != source.company_id:
        raise ReconciliationError("PRP_AUTH_SCOPE_DENIED", "Source is outside actor scope", 403)
    if not settings.PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED:
        raise ReconciliationError("PRP_AUTH_FEATURE_DISABLED", "Server feature flag is disabled", 403)
    if (
        source.tenant_id not in settings.PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS
        and not settings.PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED
    ):
        raise ReconciliationError(
            "PRP_AUTH_PRODUCTION_ROLLOUT_DISABLED",
            "Production rollout is disabled",
            403,
        )


def _inject(step, requested):
    if step != requested:
        return
    if not settings.PCE_PAYMENT_REQUEST_PREPARE_FAILURE_INJECTION_ENABLED:
        raise ReconciliationError("PRP_FAILURE_INJECTION_DISABLED", "Failure injection disabled", 403)
    if step == "before_response":
        raise ReconciliationError(
            "PRP_COMMIT_UNKNOWN",
            "Response lost after commit; recover by idempotency key",
            503,
            True,
        )
    raise ReconciliationError(
        f"PRP_INJECTED_{step.upper()}",
        f"Injected failure at {step}",
        503,
        True,
    )


def _source_chain(source):
    draft = source.source_purchase_accounts_payable_draft
    invoice_prepare = draft.source_purchase_invoice_prepare
    reconciliation = draft.source_purchase_reconciliation
    return draft, invoice_prepare, reconciliation


def _source_confirmation_hash(source):
    return canonical_hash({
        "id": source.pk,
        "prepareNo": source.prepare_no,
        "version": source.version,
        "status": source.status,
        "accountingDataVersion": source.accounting_data_version,
        "validationVersion": source.validation_version,
        "validationStatus": source.validation_status,
        "validationResultCode": source.validation_result_code,
        "validationIssueCount": source.validation_issue_count,
        "payableAmount": str(source.payable_amount),
    })


def _validate_source_gate(source, *, check_existing=True):
    draft, invoice_prepare, reconciliation = _source_chain(source)
    issues = []

    def add(code, actual, expected, field):
        issues.append({
            "code": code,
            "category": "source_gate",
            "status": "failed",
            "severity": "error",
            "blocking": True,
            "actual": str(actual),
            "expected": str(expected),
            "message": code,
            "sourceField": field,
        })

    if source.status != "prepared":
        add("PRP_GATE_CONFIRMATION_PREPARED", source.status, "prepared", "source.status")
    if not getattr(source, "accounting_snapshot", None):
        add("PRP_GATE_ACCOUNTING_DATA_COMPLETE", "missing", "complete", "source.accounting_snapshot")
    if (
        source.validation_status != "passed"
        or source.validation_result_code not in {"validated", "PCP_VALIDATED"}
        or source.validation_issue_count != 0
    ):
        add(
            "PRP_GATE_CONFIRMATION_VALIDATED",
            f"{source.validation_status}/{source.validation_result_code}/{source.validation_issue_count}",
            "passed/validated/0",
            "source.validation",
        )
    snapshot = getattr(source, "accounting_snapshot", None)
    if snapshot and snapshot.period_status != "open":
        add("PRP_GATE_ACCOUNTING_PERIOD_OPEN", snapshot.period_status, "open", "accounting.periodStatus")
    if source.debit_total != source.credit_total:
        add(
            "PRP_GATE_DEBIT_CREDIT_BALANCED",
            f"{source.debit_total}/{source.credit_total}",
            "equal",
            "source.debitCredit",
        )
    if draft.status != "draft":
        add("PRP_GATE_SOURCE_VERSIONS_CURRENT", draft.status, "draft", "apDraft.status")
    if invoice_prepare.status != "prepared":
        add("PRP_GATE_SOURCE_VERSIONS_CURRENT", invoice_prepare.status, "prepared", "invoicePrepare.status")
    if reconciliation.status != "matched":
        add("PRP_GATE_SOURCE_VERSIONS_CURRENT", reconciliation.status, "matched", "reconciliation.status")
    if not source.audit_record_id or source.audit_record.result != "committed":
        add("PRP_GATE_AUDIT_COMPLETE", "missing", "committed", "source.audit")
    if check_existing and PaymentRequestPrepare.objects.filter(
        source_payable_confirmation_prepare=source
    ).exists():
        add("PRP_GATE_NO_EXISTING_TARGET", "existing", "none", "target")
    eligibility = build_source_eligibility(source)
    if not eligibility["eligible"]:
        add("PRP_GATE_SOURCE_VERSIONS_CURRENT", "blocked", "eligible", "source.eligibility")
    return issues


def _reserve_number(source, idempotency_key):
    _, _, reconciliation = _source_chain(source)
    scope = ":".join((
        DOCUMENT_TYPE,
        source.legal_entity_id,
        source.ledger_book_id,
        reconciliation.accounting_period,
    ))
    sequence, _ = BusinessDocumentNumberSequence.objects.get_or_create(number_scope=scope)
    sequence.current_value += 1
    number = f"PRP{reconciliation.accounting_period.replace('-', '')}{sequence.current_value:08d}"
    while BusinessDocumentNumberReservation.objects.filter(reserved_number=number).exists():
        sequence.current_value += 1
        number = f"PRP{reconciliation.accounting_period.replace('-', '')}{sequence.current_value:08d}"
    sequence.save(update_fields=["current_value", "updated_at"])
    return BusinessDocumentNumberReservation.objects.create(
        document_type=DOCUMENT_TYPE,
        number_policy_version=NUMBER_POLICY_VERSION,
        number_scope=scope,
        legal_entity_id=source.legal_entity_id,
        ledger_book_id=source.ledger_book_id,
        reserved_number=number,
        tenant_id=source.tenant_id,
        accounting_period=reconciliation.accounting_period,
        idempotency_key=idempotency_key,
        status=BusinessDocumentNumberReservation.Status.RESERVED,
        target=reconciliation,
        reusable=False,
    )


def _create_tx(action_code, idempotency_key, source, source_key, review_hash):
    _, _, reconciliation = _source_chain(source)
    return BusinessActionTransaction.objects.create(
        transaction_id=f"PRPTX-{uuid.uuid4().hex}",
        action_code=action_code,
        idempotency_key=idempotency_key,
        tenant_id=source.tenant_id,
        source_key=source_key,
        command_id=f"PRP-CMD-{uuid.uuid4().hex}",
        transaction_plan_id=TRANSACTION_PLAN_ID,
        review_id=f"PRP-REVIEW-{review_hash[:16]}",
        review_hash=review_hash,
        status=BusinessActionTransaction.Status.IN_PROGRESS,
        outcome="pending",
        commit_status="in_progress",
        recovery_status="not_required",
        reconciliation=reconciliation,
    )


def _create_audit(*, tx, action_code, idempotency_key, source, user, target, evidence):
    _, _, reconciliation = _source_chain(source)
    return BusinessActionAuditRecord.objects.create(
        transaction=tx,
        action_code=action_code,
        tenant_id=source.tenant_id,
        actor=user,
        source_key=target.source_key,
        reconciliation=reconciliation,
        result="committed",
        target_type=DOCUMENT_TYPE,
        target_id=target.pk,
        target_no=target.prepare_no,
        review_id=tx.review_id,
        review_hash=tx.review_hash,
        command_id=tx.command_id,
        idempotency_key=idempotency_key,
        actor_name=user.username,
        tenant_or_scope=f"{source.tenant_id}:{source.company_id}",
        evidence_hash=canonical_hash(evidence),
        evidence=evidence,
    )


def _commit_tx_and_idem(tx, idem, target, outcome):
    tx.status = BusinessActionTransaction.Status.COMMITTED
    tx.outcome = outcome
    tx.commit_status = "committed"
    tx.result_hash = canonical_hash({
        "targetId": target.pk,
        "targetNo": target.prepare_no,
        "targetVersion": target.version,
        "outcome": outcome,
    })
    tx.save(update_fields=["status", "outcome", "commit_status", "result_hash", "updated_at"])
    idem.status = BusinessActionIdempotency.Status.COMMITTED
    idem.target_type = DOCUMENT_TYPE
    idem.target_id = target.pk
    idem.target_no = target.prepare_no
    idem.result_reference = f"{DOCUMENT_TYPE}:{target.pk}"
    idem.save(update_fields=[
        "status", "target_type", "target_id", "target_no", "result_reference", "updated_at",
    ])


def build_payment_request_eligibility(obj):
    reasons = []
    state_facts = business_state_transition_facts(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        expected_transitions=EXPECTED_STATE_TRANSITIONS,
        audit_target_type=DOCUMENT_TYPE,
    )
    if not state_facts["stateMachineConsistent"]:
        reasons.append("PRP_STATE_MACHINE_FACTS_INCONSISTENT")
    if obj.status != "prepared":
        reasons.append("PRP_NOT_PREPARED")
    if obj.payment_data_status != "complete":
        reasons.append("PRP_PAYMENT_DATA_INCOMPLETE")
    if obj.validation_status != "passed":
        reasons.append("PRP_VALIDATION_NOT_PASSED")
    if obj.validation_result_code != "validated":
        reasons.append("PRP_VALIDATION_RESULT_NOT_VALIDATED")
    if obj.validation_issue_count != 0:
        reasons.append("PRP_VALIDATION_HAS_ISSUES")
    if obj.payment_amount != obj.payable_amount:
        reasons.append("PRP_PAYMENT_AMOUNT_MISMATCH")
    if obj.current_payment_data_version < 1 or obj.current_validation_version < 1:
        reasons.append("PRP_VERSION_NOT_READY")
    eligible = not reasons
    return {
        "eligible": eligible,
        "nextStepReadiness": "ready_for_payment_request" if eligible else "blocked",
        "status": obj.status,
        "paymentDataStatus": obj.payment_data_status,
        "validationStatus": obj.validation_status,
        "validationResultCode": obj.validation_result_code,
        "issueCount": obj.validation_issue_count,
        "paymentAmount": str(obj.payment_amount or "0.00"),
        "sourcePayableAmount": str(obj.payable_amount),
        "paymentHold": False if eligible else None,
        "blockingReasons": reasons,
        "stateMachineConsistent": state_facts["stateMachineConsistent"],
        "source": "server",
        "serverRevalidationRequired": True,
        "paymentRequestCreated": False,
    }


def serialize_prepare(obj, include_issues=True):
    data = obj.payment_data_snapshots.filter(
        payment_data_version=obj.current_payment_data_version
    ).first()
    execution = obj.validation_executions.filter(
        payment_data_version=obj.current_payment_data_version
    ).first()
    issues = []
    if include_issues and execution:
        issues = [{
            "ruleCode": issue.rule_code,
            "dimension": issue.dimension,
            "expected": issue.expected,
            "actual": issue.actual,
            "severity": issue.severity,
            "blocking": issue.blocking,
            "message": issue.message,
            "sourceField": issue.source_field,
        } for issue in execution.issues.order_by("rule_code")]
    payment_data = None
    if data:
        payment_data = {
            "paymentDataVersion": data.payment_data_version,
            "payeeBankAccountId": data.payee_bank_account_id,
            "payeeAccountName": data.payee_account_name,
            "payeeAccountNoMasked": data.payee_account_no_masked,
            "payeeBankName": data.payee_bank_name,
            "payerBankAccountId": data.payer_bank_account_id,
            "payerAccountName": data.payer_account_name,
            "payerAccountNoMasked": data.payer_account_no_masked,
            "payerBankName": data.payer_bank_name,
            "paymentMethodCode": data.payment_method_code,
            "plannedPaymentDate": data.planned_payment_date.isoformat(),
            "currency": data.currency,
            "paymentAmount": str(data.payment_amount),
            "paymentPurpose": data.payment_purpose,
            "paymentSummary": data.payment_summary,
            "dataHash": data.data_hash,
            "authorityEvidence": data.authority_evidence,
        }
    state_facts = business_state_transition_facts(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        expected_transitions=EXPECTED_STATE_TRANSITIONS,
        audit_target_type=DOCUMENT_TYPE,
    )
    return {
        "id": obj.pk,
        "prepareNo": obj.prepare_no,
        "status": obj.status,
        "sourceDocumentType": obj.source_document_type,
        "sourcePayableConfirmationPrepareId": obj.source_payable_confirmation_prepare_id,
        "sourcePayableConfirmationPrepareNo": obj.source_payable_confirmation_prepare_no,
        "sourceConfirmationVersion": obj.source_confirmation_version,
        "sourceAccountingDataVersion": obj.source_accounting_data_version,
        "sourceValidationVersion": obj.source_validation_version,
        "sourceApDraftId": obj.source_ap_draft_id,
        "sourceApDraftNo": obj.source_ap_draft_no,
        "sourceInvoicePrepareId": obj.source_invoice_prepare_id,
        "sourceInvoicePrepareNo": obj.source_invoice_prepare_no,
        "sourceReconciliationId": obj.source_reconciliation_id,
        "sourceReconciliationNo": obj.source_reconciliation_no,
        "supplierId": obj.supplier_id,
        "supplierName": obj.supplier_name,
        "legalEntityId": obj.legal_entity_id,
        "legalEntityName": obj.legal_entity_name,
        "ledgerBookId": obj.ledger_book_id,
        "currency": obj.currency,
        "payableAmount": str(obj.payable_amount),
        "paymentAmount": str(obj.payment_amount or "0.00"),
        "paymentDataStatus": obj.payment_data_status,
        "validationStatus": obj.validation_status,
        "validationResultCode": obj.validation_result_code,
        "validationIssueCount": obj.validation_issue_count,
        "currentPaymentDataVersion": obj.current_payment_data_version,
        "currentValidationVersion": obj.current_validation_version,
        "preparedAt": obj.prepared_at.isoformat() if obj.prepared_at else None,
        "idempotencyKey": obj.idempotency_key,
        "numberReservationStatus": obj.number_reservation.status,
        "transactionId": obj.business_transaction.transaction_id,
        "transactionStatus": obj.business_transaction.commit_status,
        "auditRecordId": obj.audit_record_id,
        "auditStatus": obj.audit_record.result if obj.audit_record else "missing",
        "version": obj.version,
        "paymentData": payment_data,
        "validation": {
            "ruleCount": 12,
            "passedCount": 12 - len(issues),
            "blockedCount": sum(1 for issue in issues if issue["blocking"]),
            "issueCount": len(issues),
            "issues": issues,
            "executionId": execution.pk if execution else None,
        },
        "eligibility": build_payment_request_eligibility(obj),
        **state_facts,
        "currentStateSource": "server",
    }


def build_current_state(source):
    target = PaymentRequestPrepare.objects.filter(
        source_payable_confirmation_prepare=source
    ).select_related(
        "number_reservation", "business_transaction", "audit_record"
    ).first()
    if not target:
        return {
            "currentStateSource": "server",
            "targetExistenceStatus": "no_target",
            "targetCount": 0,
            "generationAllowed": not _validate_source_gate(source, check_existing=False),
            "generationStatus": "not_started",
            "idempotencyStatus": "not_started",
            "numberReservationStatus": "not_allocated",
            "transactionStatus": "not_started",
            "paymentRequestPrepare": None,
        }
    return {
        "currentStateSource": "server",
        "targetExistenceStatus": "single_target",
        "targetCount": 1,
        "generationAllowed": False,
        "generationStatus": "existing_target",
        "idempotencyStatus": "committed",
        "numberReservationStatus": target.number_reservation.status,
        "transactionStatus": target.business_transaction.commit_status,
        "auditStatus": target.audit_record.result if target.audit_record else "missing",
        "paymentRequestPrepare": serialize_prepare(target),
    }


def _existing_result(obj, classification="existing_result"):
    return {
        "classification": classification,
        "created": False,
        "data": serialize_prepare(obj),
        "currentState": build_current_state(obj.source_payable_confirmation_prepare),
    }


def _idempotent_existing(action_code, idempotency_key, request_hash):
    prior = BusinessActionIdempotency.objects.filter(
        action_code=action_code, idempotency_key=idempotency_key
    ).first()
    if not prior:
        return None
    if prior.request_hash != request_hash:
        raise ReconciliationError(
            "PRP_IDEMPOTENCY_PAYLOAD_CONFLICT",
            "Idempotency key belongs to another request",
            409,
        )
    if prior.target_id:
        return PaymentRequestPrepare.objects.get(pk=prior.target_id)
    raise ReconciliationError("PRP_IN_PROGRESS", "Request is in progress", 409, True)


def _with_retry(call):
    retries = getattr(settings, "PCE_PAYMENT_REQUEST_PREPARE_SQLITE_RETRY_COUNT", 3)
    interval = getattr(
        settings, "PCE_PAYMENT_REQUEST_PREPARE_SQLITE_RETRY_INTERVAL_MS", 50
    ) / 1000
    for attempt in range(retries + 1):
        try:
            return call()
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= retries:
                raise
            time.sleep(interval * (attempt + 1))


def generate_payment_request_prepare(
    *,
    user,
    source,
    idempotency_key,
    expected_source_version,
    explicit_user_action,
    failure_step="",
):
    _require_explicit(explicit_user_action)
    _authorize(
        user,
        source,
        "payment_request_prepare.generate_payment_request_prepare",
    )
    _inject("after_authorization", failure_step)
    gate_issues = _validate_source_gate(source, check_existing=False)
    if gate_issues:
        raise ReconciliationError(gate_issues[0]["code"], gate_issues[0]["message"], 409)
    _inject("after_business_gate", failure_step)
    request_hash = canonical_hash({
        "sourceId": source.pk,
        "expectedSourceVersion": expected_source_version,
        "explicitUserAction": True,
    })
    prior_target = _idempotent_existing(GENERATE_ACTION, idempotency_key, request_hash)
    if prior_target:
        return _existing_result(prior_target)

    def work():
        with transaction.atomic():
            transaction_id = f"PRPTX-{uuid.uuid4().hex}"
            lock, created = BusinessActionSourceLock.objects.get_or_create(
                lock_key=f"payment_request_prepare_generation:{source.pk}",
                defaults={"owner_transaction_id": transaction_id, "state": "acquired"},
            )
            if not created and lock.state == "acquired" and lock.owner_transaction_id != transaction_id:
                raise ReconciliationError("PRP_IN_PROGRESS", "Source generation is in progress", 409, True)
            lock.owner_transaction_id = transaction_id
            lock.state = "acquired"
            lock.released_at = None
            lock.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
            _inject("after_persistent_lock", failure_step)
            locked_source = PayableConfirmationPrepare.objects.select_related(
                "source_purchase_accounts_payable_draft__source_purchase_invoice_prepare",
                "source_purchase_accounts_payable_draft__source_purchase_reconciliation",
                "accounting_snapshot",
                "audit_record",
            ).get(pk=source.pk)
            _inject("after_source_reload", failure_step)
            if locked_source.version != expected_source_version:
                raise ReconciliationError("PRP_GATE_SOURCE_VERSIONS_CURRENT", "Source version changed", 409)
            _inject("after_version_check", failure_step)
            existing = PaymentRequestPrepare.objects.filter(
                source_payable_confirmation_prepare=locked_source
            ).first()
            if existing:
                return _existing_result(existing)
            _inject("after_target_check", failure_step)
            source_key = f"payableConfirmationPrepare:{locked_source.pk}"
            idem = BusinessActionIdempotency.objects.create(
                action_code=GENERATE_ACTION,
                idempotency_key=idempotency_key,
                tenant_id=locked_source.tenant_id,
                source_key=source_key,
                request_hash=request_hash,
                status=BusinessActionIdempotency.Status.IN_PROGRESS,
                transaction_id=transaction_id,
            )
            _inject("after_idempotency_registration", failure_step)
            reservation = _reserve_number(locked_source, idempotency_key)
            _inject("after_number_reservation", failure_step)
            source_hash = _source_confirmation_hash(locked_source)
            source_eligibility = build_source_eligibility(locked_source)
            source_eligibility_hash = canonical_hash(source_eligibility)
            tx = _create_tx(GENERATE_ACTION, idempotency_key, locked_source, source_key, source_hash)
            draft, invoice_prepare, reconciliation = _source_chain(locked_source)
            obj = create_business_object_with_initial_state(
                model=PaymentRequestPrepare,
                initial_state="draft",
                prepare_no=reservation.reserved_number,
                source_payable_confirmation_prepare=locked_source,
                source_payable_confirmation_prepare_no=locked_source.prepare_no,
                source_confirmation_version=locked_source.version,
                source_accounting_data_version=locked_source.accounting_data_version,
                source_validation_version=locked_source.validation_version,
                source_ap_draft_id=draft.pk,
                source_ap_draft_no=draft.draft_no,
                source_invoice_prepare_id=invoice_prepare.pk,
                source_invoice_prepare_no=invoice_prepare.prepare_no,
                source_reconciliation_id=reconciliation.pk,
                source_reconciliation_no=reconciliation.reconciliation_no,
                source_key=source_key,
                tenant_id=locked_source.tenant_id,
                company_id=locked_source.company_id,
                supplier_id=locked_source.supplier_id,
                supplier_name=locked_source.supplier_name,
                legal_entity_id=locked_source.legal_entity_id,
                legal_entity_name=locked_source.legal_entity_name,
                ledger_book_id=locked_source.ledger_book_id,
                currency=locked_source.currency,
                payable_amount=locked_source.payable_amount,
                idempotency_key=idempotency_key,
                number_reservation=reservation,
                business_transaction=tx,
                created_by=user,
            )
            _inject("after_target_insert", failure_step)
            source_validation = locked_source.validation_executions.get(
                validation_version=locked_source.validation_version
            )
            PaymentRequestPrepareSourceSnapshot.objects.create(
                payment_request_prepare=obj,
                source_payable_confirmation_prepare_id=locked_source.pk,
                source_confirmation_version=locked_source.version,
                source_accounting_snapshot_id=locked_source.accounting_snapshot.pk,
                source_accounting_data_version=locked_source.accounting_data_version,
                source_confirmation_validation_execution_id=source_validation.pk,
                source_validation_version=locked_source.validation_version,
                source_ap_draft_id=draft.pk,
                source_invoice_prepare_id=invoice_prepare.pk,
                source_reconciliation_id=reconciliation.pk,
                source_confirmation_hash=source_hash,
                source_accounting_hash=locked_source.accounting_snapshot.snapshot_hash,
                source_validation_hash=source_validation.result_hash,
                source_eligibility_hash=source_eligibility_hash,
            )
            _inject("after_source_snapshot_insert", failure_step)
            PaymentRequestPrepareSourceRelation.objects.create(
                payment_request_prepare=obj,
                source_id=locked_source.pk,
                source_no=locked_source.prepare_no,
                source_version=locked_source.version,
                source_hash=source_hash,
            )
            _inject("after_source_relation_insert", failure_step)
            evidence = {
                "version": VERSION,
                "canonicalName": CANONICAL_NAME,
                "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
                "sourceConfirmationHash": source_hash,
                "sourceEligibilityHash": source_eligibility_hash,
                "paymentRequestCreated": False,
                "sqliteConcurrency": {
                    "transactionAtomic": True,
                    "hardUniqueConstraint": True,
                    "optimisticSourceVersion": True,
                    "persistentSourceLock": True,
                    "rowLockClaimed": False,
                },
            }
            audit = _create_audit(
                tx=tx,
                action_code=GENERATE_ACTION,
                idempotency_key=idempotency_key,
                source=locked_source,
                user=user,
                target=obj,
                evidence=evidence,
            )
            obj.audit_record = audit
            obj.save(update_fields=["audit_record", "updated_at"])
            _inject("after_audit_insert", failure_step)
            _commit_tx_and_idem(tx, idem, obj, "created")
            _inject("after_idempotency_committed", failure_step)
            reservation.status = BusinessDocumentNumberReservation.Status.CONSUMED
            reservation.consumed_at = timezone.now()
            reservation.save(update_fields=["status", "consumed_at"])
            _inject("after_number_consumed", failure_step)
            lock.state = "released"
            lock.released_at = timezone.now()
            lock.save(update_fields=["state", "released_at", "acquired_at"])
            _inject("before_database_commit", failure_step)
        _inject("before_response", failure_step)
        return {
            "classification": "created",
            "created": True,
            "data": serialize_prepare(obj),
            "currentState": build_current_state(locked_source),
        }

    try:
        return _with_retry(work)
    except IntegrityError:
        existing = PaymentRequestPrepare.objects.filter(
            source_payable_confirmation_prepare=source
        ).first()
        if existing:
            return _existing_result(existing)
        raise


def _authority_dict(evidence):
    if not evidence:
        return None
    return {
        "provider": evidence.provider,
        "repository": evidence.repository,
        "authorityObject": evidence.authority_object,
        "authorityId": evidence.authority_id,
        "version": evidence.version,
        "businessHash": evidence.business_hash,
        "payload": evidence.payload,
    }


def save_payment_request_prepare_data(
    *,
    user,
    obj,
    payload,
    idempotency_key,
    expected_version,
    expected_payment_data_version,
    explicit_user_action,
    failure_step="",
):
    _require_explicit(explicit_user_action)
    source = obj.source_payable_confirmation_prepare
    _authorize(user, source, "payment_request_prepare.edit_payment_request_prepare_data")
    _inject("after_authorization", failure_step)
    if obj.status == "prepared":
        raise ReconciliationError(
            "PAYMENT_REQUEST_PREPARE_PREPARED_IMMUTABLE",
            "Prepared payment request prepare data is immutable",
            409,
        )
    planned_date = _date(payload.get("plannedPaymentDate"), "plannedPaymentDate")
    payment_amount = _decimal(payload.get("paymentAmount"), "paymentAmount")
    normalized = {
        "payeeBankAccountId": str(payload.get("payeeBankAccountId") or "").strip(),
        "payerBankAccountId": str(payload.get("payerBankAccountId") or "").strip(),
        "paymentMethodCode": str(payload.get("paymentMethodCode") or "").strip(),
        "plannedPaymentDate": planned_date,
        "paymentAmount": payment_amount,
        "paymentPurpose": str(payload.get("paymentPurpose") or "").strip(),
        "paymentSummary": str(payload.get("paymentSummary") or "").strip(),
    }
    request_hash = canonical_hash({
        **{key: value.isoformat() if isinstance(value, date) else str(value) for key, value in normalized.items()},
        "prepareId": obj.pk,
        "expectedVersion": expected_version,
        "expectedPaymentDataVersion": expected_payment_data_version,
    })
    prior = _idempotent_existing(SAVE_ACTION, idempotency_key, request_hash)
    if prior:
        return {"classification": "existing_result", "saved": False, "data": serialize_prepare(prior)}

    def work():
        with transaction.atomic():
            tx_id = f"PRPTX-{uuid.uuid4().hex}"
            lock, created = BusinessActionSourceLock.objects.get_or_create(
                lock_key=f"payment_request_prepare_data:{obj.pk}",
                defaults={"owner_transaction_id": tx_id, "state": "acquired"},
            )
            if not created and lock.state == "acquired" and lock.owner_transaction_id != tx_id:
                raise ReconciliationError("PRP_IN_PROGRESS", "Prepare data is being edited", 409, True)
            lock.owner_transaction_id = tx_id
            lock.state = "acquired"
            lock.released_at = None
            lock.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
            _inject("after_persistent_lock", failure_step)
            locked = PaymentRequestPrepare.objects.select_related(
                "source_payable_confirmation_prepare"
            ).get(pk=obj.pk)
            _inject("after_prepare_reload", failure_step)
            if locked.status == "prepared":
                raise ReconciliationError(
                    "PAYMENT_REQUEST_PREPARE_PREPARED_IMMUTABLE",
                    "Prepared payment request prepare data is immutable",
                    409,
                )
            if locked.version != expected_version or locked.current_payment_data_version != expected_payment_data_version:
                raise ReconciliationError("PRP_SOURCE_VERSION_CONFLICT", "Prepare version changed", 409)
            next_version = locked.current_payment_data_version + 1
            authorities = read_all_payment_authorities(
                payee_bank_account_id=normalized["payeeBankAccountId"],
                payer_bank_account_id=normalized["payerBankAccountId"],
                payment_method_code=normalized["paymentMethodCode"],
                planned_payment_date=planned_date,
                source_object_id=locked.source_payable_confirmation_prepare_id,
            )
            _inject("after_provider_read", failure_step)
            missing = [name for name in ("payee", "payer", "method", "calendar", "hold") if not authorities[name]]
            if missing:
                raise ReconciliationError(
                    f"PRP_DATA_{missing[0].upper()}_AUTHORITY_MISSING",
                    f"Missing authority: {missing[0]}",
                    409,
                )
            _inject("after_version_check", failure_step)
            authority_payload = {key: _authority_dict(value) for key, value in authorities.items()}
            data_hash = canonical_hash({
                "prepareId": locked.pk,
                "paymentDataVersion": next_version,
                "payeeBankAccountId": normalized["payeeBankAccountId"],
                "payerBankAccountId": normalized["payerBankAccountId"],
                "paymentMethodCode": normalized["paymentMethodCode"],
                "plannedPaymentDate": planned_date.isoformat(),
                "currency": locked.currency,
                "paymentAmount": str(payment_amount),
                "paymentPurpose": normalized["paymentPurpose"],
                "paymentSummary": normalized["paymentSummary"],
                "authorityEvidence": authority_payload,
            })
            data_snapshot = PaymentRequestDataSnapshot.objects.create(
                payment_request_prepare=locked,
                payment_data_version=next_version,
                payee_bank_account_id=normalized["payeeBankAccountId"],
                payee_account_name=authorities["payee"].payload["accountName"],
                payee_account_no_masked=authorities["payee"].payload["maskedAccountNo"],
                payee_bank_name=authorities["payee"].payload["bankName"],
                payer_bank_account_id=normalized["payerBankAccountId"],
                payer_account_name=authorities["payer"].payload["accountName"],
                payer_account_no_masked=authorities["payer"].payload["maskedAccountNo"],
                payer_bank_name=authorities["payer"].payload["bankName"],
                payment_method_code=normalized["paymentMethodCode"],
                planned_payment_date=planned_date,
                currency=locked.currency,
                payment_amount=payment_amount,
                payment_purpose=normalized["paymentPurpose"],
                payment_summary=normalized["paymentSummary"],
                authority_evidence=authority_payload,
                data_hash=data_hash,
                created_by=user,
            )
            _inject("after_payment_data_snapshot_insert", failure_step)
            locked.payment_amount = payment_amount
            locked.payment_data_status = (
                "complete"
                if all([
                    normalized["payeeBankAccountId"],
                    normalized["payerBankAccountId"],
                    normalized["paymentMethodCode"],
                    normalized["paymentPurpose"],
                    normalized["paymentSummary"],
                    payment_amount > 0,
                ])
                else "incomplete"
            )
            locked.validation_status = "not_validated"
            locked.validation_result_code = "not_validated"
            locked.validation_issue_count = 0
            locked.current_payment_data_version = next_version
            locked.version += 1
            locked.save(update_fields=[
                "payment_amount", "payment_data_status", "validation_status",
                "validation_result_code", "validation_issue_count",
                "current_payment_data_version", "version", "updated_at",
            ])
            _inject("after_prepare_update", failure_step)
            idem = BusinessActionIdempotency.objects.create(
                action_code=SAVE_ACTION,
                idempotency_key=idempotency_key,
                tenant_id=locked.tenant_id,
                source_key=locked.source_key,
                request_hash=request_hash,
                status=BusinessActionIdempotency.Status.IN_PROGRESS,
                transaction_id=tx_id,
            )
            _inject("after_idempotency_registration", failure_step)
            tx = _create_tx(SAVE_ACTION, idempotency_key, source, locked.source_key, data_hash)
            audit = _create_audit(
                tx=tx,
                action_code=SAVE_ACTION,
                idempotency_key=idempotency_key,
                source=source,
                user=user,
                target=locked,
                evidence={
                    "version": VERSION,
                    "action": SAVE_ACTION,
                    "paymentDataVersion": next_version,
                    "dataHash": data_hash,
                    "authorityProviders": [
                        evidence.provider for evidence in authorities.values()
                    ],
                    "maskedAccountNumbersOnly": True,
                    "paymentRequestCreated": False,
                },
            )
            _inject("after_audit_insert", failure_step)
            _commit_tx_and_idem(tx, idem, locked, "payment_data_saved")
            _inject("after_idempotency_committed", failure_step)
            lock.state = "released"
            lock.released_at = timezone.now()
            lock.save(update_fields=["state", "released_at", "acquired_at"])
            _inject("before_database_commit", failure_step)
        _inject("before_response", failure_step)
        return {
            "classification": "saved",
            "saved": True,
            "paymentDataSnapshotId": data_snapshot.pk,
            "data": serialize_prepare(locked),
        }

    return _with_retry(work)


def _rule(code, status, actual, expected, field, message=None):
    return {
        "code": code,
        "category": "payment_validation",
        "status": "passed" if status else "failed",
        "severity": "info" if status else "error",
        "blocking": not status,
        "actual": str(actual),
        "expected": str(expected),
        "message": message or code,
        "sourceField": field,
    }


def validate_payment_elements(obj, data_snapshot, authorities):
    payee = authorities["payee"].payload if authorities["payee"] else {}
    payer = authorities["payer"].payload if authorities["payer"] else {}
    method = authorities["method"].payload if authorities["method"] else {}
    calendar = authorities["calendar"].payload if authorities["calendar"] else {}
    hold = authorities["hold"].payload if authorities["hold"] else {}
    rules = [
        _rule("PRP_VALIDATE_PAYEE_ACCOUNT_ACTIVE", bool(payee.get("active") and payee.get("paymentEnabled")), payee.get("active"), True, "payeeBankAccountId"),
        _rule("PRP_VALIDATE_PAYEE_OWNER_MATCH", payee.get("supplierId") == obj.supplier_id, payee.get("supplierId"), obj.supplier_id, "payeeBankAccountId"),
        _rule("PRP_VALIDATE_PAYER_ACCOUNT_ACTIVE", bool(payer.get("active") and payer.get("availableForPayment")), payer.get("active"), True, "payerBankAccountId"),
        _rule("PRP_VALIDATE_PAYER_SCOPE_MATCH", payer.get("legalEntityId") == obj.legal_entity_id and payer.get("ledgerBookId") == obj.ledger_book_id, f"{payer.get('legalEntityId')}/{payer.get('ledgerBookId')}", f"{obj.legal_entity_id}/{obj.ledger_book_id}", "payerBankAccountId"),
        _rule("PRP_VALIDATE_ACCOUNT_CURRENCY", payee.get("currency") == obj.currency and payer.get("currency") == obj.currency, f"{payee.get('currency')}/{payer.get('currency')}", obj.currency, "currency"),
        _rule("PRP_VALIDATE_PAYMENT_METHOD", bool(method.get("active") and obj.currency in method.get("supportedCurrency", [])), method.get("active"), True, "paymentMethodCode"),
        _rule("PRP_VALIDATE_PAYMENT_DATE", bool(calendar.get("businessDay") and calendar.get("paymentAllowed")), calendar.get("paymentAllowed"), True, "plannedPaymentDate"),
        _rule("PRP_VALIDATE_PAYMENT_HOLD", hold.get("holdStatus") != "active" and not hold.get("releaseRequired"), hold.get("holdStatus"), "released", "sourcePayableConfirmationPrepareId"),
        _rule("PRP_VALIDATE_AMOUNT", data_snapshot.payment_amount > 0 and data_snapshot.payment_amount == obj.payable_amount, data_snapshot.payment_amount, obj.payable_amount, "paymentAmount"),
        _rule("PRP_VALIDATE_CURRENCY", data_snapshot.currency == obj.currency, data_snapshot.currency, obj.currency, "currency"),
        _rule("PRP_VALIDATE_SOURCE_CURRENT", not _validate_source_gate(obj.source_payable_confirmation_prepare, check_existing=False), "current", "current", "sourceVersions"),
    ]
    fatal = any(rule["blocking"] for rule in rules)
    rules.append(_rule("PRP_VALIDATE_NO_FATAL_ISSUE", not fatal, fatal, False, "validationIssues"))
    return rules


def validate_payment_request_prepare(
    *,
    user,
    obj,
    idempotency_key,
    expected_version,
    expected_payment_data_version,
    expected_confirmation_version,
    expected_accounting_data_version,
    expected_confirmation_validation_version,
    explicit_user_action,
    failure_step="",
):
    _require_explicit(explicit_user_action)
    source = obj.source_payable_confirmation_prepare
    _authorize(user, source, "payment_request_prepare.validate_payment_request_prepare")
    _inject("after_authorization", failure_step)
    request_hash = canonical_hash({
        "prepareId": obj.pk,
        "expectedVersion": expected_version,
        "expectedPaymentDataVersion": expected_payment_data_version,
        "expectedConfirmationVersion": expected_confirmation_version,
        "expectedAccountingDataVersion": expected_accounting_data_version,
        "expectedConfirmationValidationVersion": expected_confirmation_validation_version,
    })
    prior = _idempotent_existing(VALIDATE_ACTION, idempotency_key, request_hash)
    if prior:
        return {"classification": "existing_result", "validated": False, "data": serialize_prepare(prior)}

    def work():
        with transaction.atomic():
            tx_id = f"PRPTX-{uuid.uuid4().hex}"
            lock, created = BusinessActionSourceLock.objects.get_or_create(
                lock_key=f"payment_request_prepare_validation:{obj.pk}",
                defaults={"owner_transaction_id": tx_id, "state": "acquired"},
            )
            if not created and lock.state == "acquired" and lock.owner_transaction_id != tx_id:
                raise ReconciliationError("PRP_IN_PROGRESS", "Prepare validation is in progress", 409, True)
            lock.owner_transaction_id = tx_id
            lock.state = "acquired"
            lock.released_at = None
            lock.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
            _inject("after_persistent_lock", failure_step)
            locked = PaymentRequestPrepare.objects.select_related(
                "source_payable_confirmation_prepare__accounting_snapshot"
            ).get(pk=obj.pk)
            _inject("after_prepare_reload", failure_step)
            if locked.status == "prepared":
                raise ReconciliationError(
                    "PAYMENT_REQUEST_PREPARE_PREPARED_IMMUTABLE",
                    "Prepared payment request prepare is immutable",
                    409,
                )
            data_snapshot = locked.payment_data_snapshots.get(
                payment_data_version=locked.current_payment_data_version
            )
            _inject("after_payment_data_reload", failure_step)
            source_locked = PayableConfirmationPrepare.objects.select_related(
                "source_purchase_accounts_payable_draft__source_purchase_invoice_prepare",
                "source_purchase_accounts_payable_draft__source_purchase_reconciliation",
                "accounting_snapshot",
                "audit_record",
            ).get(pk=locked.source_payable_confirmation_prepare_id)
            _inject("after_source_reload", failure_step)
            expected = (
                expected_version,
                expected_payment_data_version,
                expected_confirmation_version,
                expected_accounting_data_version,
                expected_confirmation_validation_version,
            )
            actual = (
                locked.version,
                locked.current_payment_data_version,
                source_locked.version,
                source_locked.accounting_data_version,
                source_locked.validation_version,
            )
            if actual != expected:
                raise ReconciliationError("PRP_SOURCE_VERSION_CONFLICT", "Source or prepare version changed", 409)
            authorities = read_all_payment_authorities(
                payee_bank_account_id=data_snapshot.payee_bank_account_id,
                payer_bank_account_id=data_snapshot.payer_bank_account_id,
                payment_method_code=data_snapshot.payment_method_code,
                planned_payment_date=data_snapshot.planned_payment_date,
                source_object_id=source_locked.pk,
            )
            _inject("after_provider_read", failure_step)
            _inject("after_version_check", failure_step)
            rules = validate_payment_elements(locked, data_snapshot, authorities)
            issues = [rule for rule in rules if rule["blocking"]]
            result_code = "validated" if not issues else (
                issues[0]["code"].lower() if len(issues) == 1 else "multiple_errors"
            )
            result_status = "passed" if not issues else "failed"
            input_hash = canonical_hash({
                "paymentDataHash": data_snapshot.data_hash,
                "sourceConfirmationHash": _source_confirmation_hash(source_locked),
                "authorityHashes": {
                    key: evidence.business_hash if evidence else "missing"
                    for key, evidence in authorities.items()
                },
            })
            result_hash = canonical_hash({
                "status": result_status,
                "resultCode": result_code,
                "rules": rules,
                "inputHash": input_hash,
            })
            execution = PaymentRequestPrepareValidationExecution.objects.create(
                payment_request_prepare=locked,
                action_id=VALIDATE_ACTION,
                idempotency_key=idempotency_key,
                payment_data_version=locked.current_payment_data_version,
                source_confirmation_version=source_locked.version,
                source_accounting_data_version=source_locked.accounting_data_version,
                source_validation_version=source_locked.validation_version,
                validation_policy_version=VALIDATION_POLICY_VERSION,
                status=result_status,
                result_code=result_code,
                input_hash=input_hash,
                result_hash=result_hash,
                issue_count=len(issues),
                actor=user,
                completed_at=timezone.now(),
            )
            _inject("after_validation_execution_insert", failure_step)
            for issue in issues:
                PaymentRequestPrepareValidationIssue.objects.create(
                    validation_execution=execution,
                    rule_code=issue["code"],
                    dimension=issue["category"],
                    expected=issue["expected"],
                    actual=issue["actual"],
                    severity=issue["severity"],
                    blocking=issue["blocking"],
                    message=issue["message"],
                    source_field=issue["sourceField"],
                )
            _inject("after_issue_insert", failure_step)
            locked.current_validation_version += 1
            locked.validation_status = result_status
            locked.validation_result_code = result_code
            locked.validation_issue_count = len(issues)
            if not issues:
                locked.prepared_at = timezone.now()
                locked.prepared_by = user
            else:
                locked.version += 1
            locked.save(update_fields=[
                "current_validation_version", "validation_status",
                "validation_result_code", "validation_issue_count", "version",
                "prepared_at", "prepared_by", "updated_at",
            ])
            _inject("after_prepared_update", failure_step)
            idem = BusinessActionIdempotency.objects.create(
                action_code=VALIDATE_ACTION,
                idempotency_key=idempotency_key,
                tenant_id=locked.tenant_id,
                source_key=locked.source_key,
                request_hash=request_hash,
                status=BusinessActionIdempotency.Status.IN_PROGRESS,
                transaction_id=tx_id,
            )
            _inject("after_idempotency_registration", failure_step)
            tx = _create_tx(VALIDATE_ACTION, idempotency_key, source_locked, locked.source_key, result_hash)
            audit = _create_audit(
                tx=tx,
                action_code=VALIDATE_ACTION,
                idempotency_key=idempotency_key,
                source=source_locked,
                user=user,
                target=locked,
                evidence={
                    "version": VERSION,
                    "action": VALIDATE_ACTION,
                    "validationPolicyVersion": VALIDATION_POLICY_VERSION,
                    "ruleCount": len(rules),
                    "issueCount": len(issues),
                    "resultCode": result_code,
                    "resultHash": result_hash,
                    "paymentRequestEligibility": {
                        "nextStepReadiness": "ready_for_payment_request" if not issues else "blocked",
                        "serverDerived": True,
                    },
                    "paymentRequestCreated": False,
                },
            )
            if not issues:
                transition_business_object(
                    business_object=locked,
                    object_type=DOCUMENT_TYPE,
                    source_state="draft",
                    target_state="prepared",
                    action_code=VALIDATE_ACTION,
                    operator=user,
                    reason="Payment request preparation validation passed",
                    audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                    allowed_transitions=ALLOWED_STATE_TRANSITIONS,
                )
            _inject("after_audit_insert", failure_step)
            _commit_tx_and_idem(tx, idem, locked, "validated" if not issues else "validation_failed")
            _inject("after_idempotency_committed", failure_step)
            lock.state = "released"
            lock.released_at = timezone.now()
            lock.save(update_fields=["state", "released_at", "acquired_at"])
            _inject("before_database_commit", failure_step)
        _inject("before_response", failure_step)
        return {
            "classification": "validated" if not issues else "validation_failed",
            "validated": not issues,
            "rules": rules,
            "data": serialize_prepare(locked),
        }

    return _with_retry(work)


def recover_action_result(action_code, idempotency_key):
    idem = BusinessActionIdempotency.objects.filter(
        action_code=action_code,
        idempotency_key=idempotency_key,
    ).first()
    if not idem or not idem.target_id:
        raise ReconciliationError("PRP_IDEMPOTENCY_NOT_FOUND", "Result not found", 404)
    return {
        "classification": "existing_result",
        "actionCode": action_code,
        "data": serialize_prepare(PaymentRequestPrepare.objects.get(pk=idem.target_id)),
    }
