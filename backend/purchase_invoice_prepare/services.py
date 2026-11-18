import time
import uuid

from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from reconciliation.checking import build_invoice_prepare_eligibility
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
from workflow_runtime.facts import (
    business_state_transition_facts_from_allowed_transitions,
)
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
)

from .models import PurchaseInvoicePrepare, PurchaseInvoicePrepareSourceRelation

ACTION_CODE = "generate_purchase_invoice_prepare"
DOCUMENT_TYPE = "purchase_invoice_prepare"
SOURCE_DOCUMENT_TYPE = "purchaseReconciliation"
NUMBER_POLICY_VERSION = "pip-sequence-v1"
TRANSACTION_PLAN_ID = "purchase-invoice-prepare-atomic-v1"
FAILURE_STEPS = (
    "after_authorization",
    "after_business_gate",
    "after_idempotency_registration",
    "after_persistent_lock",
    "after_locked_source_reload",
    "after_eligibility_revalidation",
    "after_version_check",
    "after_existing_target_check",
    "after_number_reservation",
    "after_target_insert",
    "after_relation_insert",
    "after_reverse_reference",
    "after_audit_insert",
    "after_idempotency_committed",
    "after_number_consumed",
    "before_database_commit",
)


def _inject(step, requested):
    if step != requested:
        return
    if not settings.PCE_PURCHASE_INVOICE_PREPARE_FAILURE_INJECTION_ENABLED:
        raise ReconciliationError("PIP_FAILURE_INJECTION_DISABLED", "Failure injection is disabled", 403)
    raise ReconciliationError(f"PIP_INJECTED_{step.upper()}", f"Injected failure at {step}", 503, True)


def _authorize(user, reconciliation):
    if not user or not user.is_authenticated:
        raise ReconciliationError("PIP_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not (user.is_superuser or user.has_perm("purchase_invoice_prepare.generate_purchase_invoice_prepare")):
        raise ReconciliationError("PIP_AUTH_PERMISSION_DENIED", "Generation permission required", 403)
    if not user.is_superuser and user.company_id != reconciliation.company_id:
        raise ReconciliationError("PIP_AUTH_SCOPE_DENIED", "Source is outside actor company scope", 403)
    if not settings.PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED:
        raise ReconciliationError("PIP_AUTH_FEATURE_DISABLED", "Server feature flag is disabled", 403)
    if (
        reconciliation.tenant_id not in settings.PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS
        and not settings.PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED
    ):
        raise ReconciliationError(
            "PIP_AUTH_PRODUCTION_ROLLOUT_DISABLED",
            "Production rollout is disabled",
            403,
        )


def build_business_gate(reconciliation, expected_reconciliation_version=None, expected_check_version=None):
    eligibility = build_invoice_prepare_eligibility(reconciliation)
    target_count = PurchaseInvoicePrepare.objects.filter(
        source_purchase_reconciliation_id=reconciliation.pk
    ).count()
    audit_complete = (
        reconciliation.checked_by_id is not None
        and reconciliation.checked_at is not None
        and reconciliation.check_executions.exists()
    )
    checks = {
        "PIP_GATE_SOURCE_EXISTS": True,
        "PIP_GATE_SOURCE_TYPE_VALID": SOURCE_DOCUMENT_TYPE == "purchaseReconciliation",
        "PIP_GATE_RECONCILIATION_MATCHED": reconciliation.status == "matched",
        "PIP_GATE_CHECK_RESULT_MATCHED": reconciliation.check_result_code == "PRC_CHECK_MATCHED",
        "PIP_GATE_ZERO_DIFFERENCE": reconciliation.difference_count == 0,
        "PIP_GATE_EVIDENCE_INTEGRITY_VALID": eligibility["evidenceIntegrity"] == "passed",
        "PIP_GATE_TWO_AUTHORITY_SOURCES": eligibility["evidenceSourceCount"] == 2,
        "PIP_GATE_EVIDENCE_SOURCES_INDEPENDENT": eligibility["evidenceSourcesIndependent"] is True,
        "PIP_GATE_INVOICE_PREPARE_READY": eligibility["nextStepReadiness"] == "ready_for_invoice_prepare",
        "PIP_GATE_SOURCE_VERSION_MATCH": (
            expected_reconciliation_version is None
            or reconciliation.version == expected_reconciliation_version
        ),
        "PIP_GATE_CHECK_VERSION_MATCH": (
            expected_check_version is None
            or eligibility["checkVersion"] == expected_check_version
        ),
        "PIP_GATE_NO_EXISTING_TARGET": target_count == 0,
        "PIP_GATE_AUDIT_EVIDENCE_COMPLETE": audit_complete,
        "PIP_GATE_NO_FATAL_RISK": True,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "eligibility": eligibility,
        "existingTargetCount": target_count,
        "auditEvidenceComplete": audit_complete,
    }


def _raise_gate(gate):
    failures = [code for code, passed in gate["checks"].items() if not passed]
    if "PIP_GATE_SOURCE_VERSION_MATCH" in failures:
        raise ReconciliationError("PIP_SOURCE_VERSION_CONFLICT", "Reconciliation version changed", 409)
    if "PIP_GATE_CHECK_VERSION_MATCH" in failures:
        raise ReconciliationError("PIP_CHECK_VERSION_CONFLICT", "Check version changed", 409)
    if "PIP_GATE_NO_EXISTING_TARGET" in failures:
        raise ReconciliationError("PIP_EXISTING_TARGET", "Invoice prepare already exists", 409)
    raise ReconciliationError("PIP_BUSINESS_GATE_BLOCKED", ",".join(failures), 409)


def _reserve_number(reconciliation, idempotency_key):
    scope = ":".join(
        (
            DOCUMENT_TYPE,
            reconciliation.legal_entity_id,
            reconciliation.ledger_book_id,
            reconciliation.accounting_period,
        )
    )
    sequence, _ = BusinessDocumentNumberSequence.objects.get_or_create(number_scope=scope)
    sequence.current_value += 1
    period = reconciliation.accounting_period.replace("-", "")
    number = f"PIP{period}{sequence.current_value:08d}"
    while BusinessDocumentNumberReservation.objects.filter(reserved_number=number).exists():
        sequence.current_value += 1
        number = f"PIP{period}{sequence.current_value:08d}"
    sequence.save(update_fields=["current_value", "updated_at"])
    reservation = BusinessDocumentNumberReservation.objects.create(
        document_type=DOCUMENT_TYPE,
        number_policy_version=NUMBER_POLICY_VERSION,
        number_scope=scope,
        legal_entity_id=reconciliation.legal_entity_id,
        ledger_book_id=reconciliation.ledger_book_id,
        reserved_number=number,
        tenant_id=reconciliation.tenant_id,
        accounting_period=reconciliation.accounting_period,
        idempotency_key=idempotency_key,
        status=BusinessDocumentNumberReservation.Status.RESERVED,
        target=reconciliation,
    )
    return reservation, sequence.current_value


def _persist_aborted_number(context, abort_reason):
    """Keep an allocated number as a permanent, non-reusable audit record after rollback."""
    if not context:
        return
    with transaction.atomic():
        sequence, _ = BusinessDocumentNumberSequence.objects.get_or_create(
            number_scope=context["number_scope"]
        )
        if sequence.current_value < context["sequence_value"]:
            sequence.current_value = context["sequence_value"]
            sequence.save(update_fields=["current_value", "updated_at"])
        reservation, created = BusinessDocumentNumberReservation.objects.get_or_create(
            reserved_number=context["reserved_number"],
            defaults={
                "document_type": DOCUMENT_TYPE,
                "number_policy_version": NUMBER_POLICY_VERSION,
                "number_scope": context["number_scope"],
                "legal_entity_id": context["legal_entity_id"],
                "ledger_book_id": context["ledger_book_id"],
                "tenant_id": context["tenant_id"],
                "accounting_period": context["accounting_period"],
                "idempotency_key": context["idempotency_key"],
                "status": BusinessDocumentNumberReservation.Status.ABORTED,
                "target_id": context["target_id"],
                "aborted_at": timezone.now(),
                "abort_reason": str(abort_reason)[:160],
            },
        )
        if not created and reservation.status == BusinessDocumentNumberReservation.Status.RESERVED:
            reservation.status = BusinessDocumentNumberReservation.Status.ABORTED
            reservation.aborted_at = timezone.now()
            reservation.abort_reason = str(abort_reason)[:160]
            reservation.save(update_fields=["status", "aborted_at", "abort_reason"])


def build_purchase_invoice_prepare_state_facts(obj):
    return business_state_transition_facts_from_allowed_transitions(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        allowed_transitions=(
            (
                PurchaseInvoicePrepare.Status.DRAFT,
                PurchaseInvoicePrepare.Status.PREPARED,
                "VALIDATE_PURCHASE_INVOICE_PREPARE",
            ),
        ),
        audit_target_types=("purchaseInvoicePrepare", DOCUMENT_TYPE),
        initial_states=(PurchaseInvoicePrepare.Status.DRAFT,),
    )


def serialize_prepare(obj):
    state_facts = build_purchase_invoice_prepare_state_facts(obj)
    return {
        "id": obj.pk,
        "prepareNo": obj.prepare_no,
        "status": obj.status,
        "sourceDocumentType": obj.source_document_type,
        "sourcePurchaseReconciliationId": obj.source_purchase_reconciliation_id,
        "sourcePurchaseReconciliationNo": obj.source_purchase_reconciliation_no,
        "sourceReconciliationVersion": obj.source_reconciliation_version,
        "sourceCheckVersion": obj.source_check_version,
        "supplierId": obj.supplier_id,
        "supplierName": obj.supplier_name,
        "legalEntityId": obj.legal_entity_id,
        "ledgerBookId": obj.ledger_book_id,
        "currency": obj.currency,
        "exchangeRate": str(obj.exchange_rate),
        "quantity": str(obj.quantity),
        "unit": obj.unit,
        "settlementAmount": str(obj.settlement_amount),
        "invoiceDataStatus": obj.invoice_data_status,
        "validationStatus": obj.validation_status,
        "validationResultCode": obj.validation_result_code,
        "currentDataVersion": obj.current_data_version,
        "currentValidationVersion": obj.current_validation_version,
        "validationIssueCount": obj.validation_issue_count,
        "preparedAt": obj.prepared_at.isoformat() if obj.prepared_at else None,
        "idempotencyKey": obj.idempotency_key,
        "numberReservationId": obj.number_reservation_id,
        "transactionId": obj.transaction_id,
        "auditRecordId": obj.audit_record_id,
        "version": obj.version,
        "createdAt": obj.created_at.isoformat(),
        "currentStateSource": "server",
        **state_facts,
        "strictFacts": {
            "currentStateSource": "server",
            **state_facts,
        },
    }


def build_current_generation_state(reconciliation, targets=None):
    targets = list(
        targets
        if targets is not None
        else PurchaseInvoicePrepare.objects.filter(source_purchase_reconciliation=reconciliation)
    )
    target_count = len(targets)
    test_tenant = reconciliation.tenant_id in settings.PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS
    if target_count == 0:
        gate = build_business_gate(reconciliation)
        return {
            "currentStateSource": "server",
            "targetExistenceStatus": "no_target",
            "targetCount": 0,
            "preActionTargetCount": 0,
            "generationAllowed": gate["passed"] and test_tenant,
            "generationStatus": "not_started",
            "preActionBusinessGateResult": "passed" if gate["passed"] else "blocked",
            "currentIdempotencyStatus": "not_started",
            "currentNumberReservationStatus": "not_allocated",
            "currentTransactionStatus": "not_started",
            "currentAuditStatus": "not_started",
            "currentSourceRelationStatus": "not_started",
            "generationResultIdempotencyKey": None,
            "testTenant": test_tenant,
            "productionRolloutEnabled": settings.PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED,
            "purchaseInvoicePrepare": None,
        }
    if target_count > 1:
        return {
            "currentStateSource": "server",
            "targetExistenceStatus": "conflict",
            "targetCount": target_count,
            "preActionTargetCount": None,
            "generationAllowed": False,
            "generationStatus": "conflict",
            "preActionBusinessGateResult": "unknown",
            "currentIdempotencyStatus": "conflict",
            "currentNumberReservationStatus": "conflict",
            "currentTransactionStatus": "conflict",
            "currentAuditStatus": "conflict",
            "currentSourceRelationStatus": "conflict",
            "generationResultIdempotencyKey": None,
            "testTenant": test_tenant,
            "productionRolloutEnabled": settings.PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED,
            "purchaseInvoicePrepare": None,
        }

    obj = targets[0]
    idempotency = BusinessActionIdempotency.objects.filter(
        action_code=ACTION_CODE,
        target_id=obj.pk,
    ).order_by("-updated_at", "-id").first()
    reservation = BusinessDocumentNumberReservation.objects.filter(pk=obj.number_reservation_id).first()
    transaction_record = BusinessActionTransaction.objects.filter(
        transaction_id=obj.transaction_id,
        action_code=ACTION_CODE,
    ).first()
    audit = BusinessActionAuditRecord.objects.filter(
        pk=obj.audit_record_id,
        action_code=ACTION_CODE,
    ).first()
    relation_exists = PurchaseInvoicePrepareSourceRelation.objects.filter(
        purchase_invoice_prepare=obj,
        source_id=reconciliation.pk,
        relationship_type="generated_from",
    ).exists()
    pre_action_gate = (audit.evidence or {}).get("businessGate", {}) if audit else {}
    return {
        "currentStateSource": "server",
        "targetExistenceStatus": "single_target",
        "targetCount": 1,
        "preActionTargetCount": 0,
        "generationAllowed": False,
        "generationStatus": "existing_target",
        "preActionBusinessGateResult": (
            "passed" if pre_action_gate and all(pre_action_gate.values()) else "unknown"
        ),
        "currentIdempotencyStatus": idempotency.status if idempotency else "inconsistent",
        "currentNumberReservationStatus": reservation.status if reservation else "inconsistent",
        "currentTransactionStatus": (
            transaction_record.commit_status if transaction_record else "inconsistent"
        ),
        "currentAuditStatus": audit.result if audit else "inconsistent",
        "currentSourceRelationStatus": "generated_from" if relation_exists else "inconsistent",
        "generationResultIdempotencyKey": obj.idempotency_key,
        "testTenant": test_tenant,
        "productionRolloutEnabled": settings.PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED,
        "purchaseInvoicePrepare": serialize_prepare(obj),
    }


def _existing_result(obj, classification):
    return {
        "classification": classification,
        "created": False,
        "data": serialize_prepare(obj),
        "currentState": build_current_generation_state(
            obj.source_purchase_reconciliation,
            [obj],
        ),
    }


def generate_purchase_invoice_prepare(
    *,
    user,
    reconciliation_id,
    idempotency_key,
    expected_reconciliation_version,
    expected_check_version,
    explicit_user_action,
    failure_step="",
):
    if not explicit_user_action:
        raise ReconciliationError("PIP_EXPLICIT_USER_ACTION_REQUIRED", "Explicit user action is required", 400)
    if not idempotency_key or len(idempotency_key) > 120:
        raise ReconciliationError("PIP_IDEMPOTENCY_KEY_INVALID", "Valid idempotency key is required", 400)
    try:
        source = PurchaseReconciliation.objects.get(pk=reconciliation_id)
    except PurchaseReconciliation.DoesNotExist as exc:
        raise ReconciliationError("PIP_SOURCE_NOT_FOUND", "Purchase reconciliation not found", 404) from exc
    _authorize(user, source)
    _inject("after_authorization", failure_step)
    pre_gate = build_business_gate(source, expected_reconciliation_version, expected_check_version)
    if not pre_gate["passed"] and not (
        pre_gate["existingTargetCount"] == 1
        and all(value for key, value in pre_gate["checks"].items() if key != "PIP_GATE_NO_EXISTING_TARGET")
    ):
        _raise_gate(pre_gate)
    _inject("after_business_gate", failure_step)

    request_hash = canonical_hash({
        "sourcePurchaseReconciliationId": reconciliation_id,
        "expectedReconciliationVersion": expected_reconciliation_version,
        "expectedCheckVersion": expected_check_version,
    })
    prior = BusinessActionIdempotency.objects.filter(
        action_code=ACTION_CODE, idempotency_key=idempotency_key
    ).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ReconciliationError("PIP_IDEMPOTENCY_CONFLICT", "Idempotency payload conflict", 409)
        if prior.target_id:
            return _existing_result(PurchaseInvoicePrepare.objects.get(pk=prior.target_id), "existing_result")
        return {"classification": prior.status, "created": False, "idempotencyStatus": prior.status}

    transaction_id = f"PIPTX-{uuid.uuid4().hex}"
    source_key = f"purchaseReconciliation:{source.pk}"
    aborted_number_context = None
    try:
        with transaction.atomic():
            idem = BusinessActionIdempotency.objects.create(
                action_code=ACTION_CODE,
                idempotency_key=idempotency_key,
                tenant_id=source.tenant_id,
                source_key=source_key,
                request_hash=request_hash,
                status=BusinessActionIdempotency.Status.IN_PROGRESS,
                transaction_id=transaction_id,
            )
            _inject("after_idempotency_registration", failure_step)
            lock, created = BusinessActionSourceLock.objects.get_or_create(
                lock_key=f"purchase_invoice_prepare_generation:{source.pk}",
                defaults={"owner_transaction_id": transaction_id, "state": "acquired"},
            )
            if not created and lock.state == "acquired" and lock.owner_transaction_id != transaction_id:
                raise ReconciliationError("PIP_SOURCE_LOCK_BUSY", "Source generation is in progress", 409, True)
            lock.owner_transaction_id = transaction_id
            lock.state = "acquired"
            lock.released_at = None
            lock.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
            _inject("after_persistent_lock", failure_step)
            source = PurchaseReconciliation.objects.get(pk=reconciliation_id)
            _inject("after_locked_source_reload", failure_step)
            gate = build_business_gate(source, expected_reconciliation_version, expected_check_version)
            _inject("after_eligibility_revalidation", failure_step)
            if not gate["checks"]["PIP_GATE_SOURCE_VERSION_MATCH"]:
                _raise_gate(gate)
            if not gate["checks"]["PIP_GATE_CHECK_VERSION_MATCH"]:
                _raise_gate(gate)
            _inject("after_version_check", failure_step)
            existing = PurchaseInvoicePrepare.objects.filter(
                source_purchase_reconciliation=source
            ).first()
            if existing:
                lock.state = "released"
                lock.released_at = timezone.now()
                lock.save(update_fields=["state", "released_at"])
                return _existing_result(existing, "existing_target")
            if not gate["passed"]:
                _raise_gate(gate)
            _inject("after_existing_target_check", failure_step)
            reservation, sequence_value = _reserve_number(source, idempotency_key)
            aborted_number_context = {
                "reserved_number": reservation.reserved_number,
                "number_scope": reservation.number_scope,
                "sequence_value": sequence_value,
                "legal_entity_id": source.legal_entity_id,
                "ledger_book_id": source.ledger_book_id,
                "tenant_id": source.tenant_id,
                "accounting_period": source.accounting_period,
                "idempotency_key": idempotency_key,
                "target_id": source.pk,
            }
            _inject("after_number_reservation", failure_step)
            eligibility_hash = canonical_hash(gate["eligibility"])
            obj = create_business_object_with_initial_state(
                model=PurchaseInvoicePrepare,
                initial_state=PurchaseInvoicePrepare.Status.DRAFT,
                prepare_no=reservation.reserved_number,
                source_purchase_reconciliation=source,
                source_purchase_reconciliation_no=source.reconciliation_no,
                source_reconciliation_version=source.version,
                source_check_version=gate["eligibility"]["checkVersion"],
                source_eligibility_hash=eligibility_hash,
                source_key=source_key,
                tenant_id=source.tenant_id,
                company_id=source.company_id,
                supplier_id=source.supplier_id,
                supplier_name=source.supplier_name,
                legal_entity_id=source.legal_entity_id,
                ledger_book_id=source.ledger_book_id,
                currency=source.currency,
                exchange_rate=source.exchange_rate,
                quantity=source.quantity,
                unit=source.unit,
                settlement_amount=source.settlement_amount,
                idempotency_key=idempotency_key,
                number_reservation_id=reservation.pk,
                transaction_id=transaction_id,
                created_by=user,
            )
            _inject("after_target_insert", failure_step)
            relation = PurchaseInvoicePrepareSourceRelation.objects.create(
                purchase_invoice_prepare=obj,
                source_id=source.pk,
                source_no=source.reconciliation_no,
                source_version=source.version,
                source_hash=eligibility_hash,
            )
            _inject("after_relation_insert", failure_step)
            _inject("after_reverse_reference", failure_step)
            tx = BusinessActionTransaction.objects.create(
                transaction_id=transaction_id,
                action_code=ACTION_CODE,
                idempotency_key=idempotency_key,
                tenant_id=source.tenant_id,
                source_key=source_key,
                command_id=f"PIPCMD-{uuid.uuid4().hex}",
                transaction_plan_id=TRANSACTION_PLAN_ID,
                review_id=f"reconciliation-check:{source.pk}:{source.version}",
                review_hash=eligibility_hash,
                status=BusinessActionTransaction.Status.COMMITTED,
                outcome="created",
                commit_status="committed",
                recovery_status="not_required",
                reconciliation=source,
            )
            audit = BusinessActionAuditRecord.objects.create(
                transaction=tx,
                action_code=ACTION_CODE,
                tenant_id=source.tenant_id,
                actor=user,
                source_key=source_key,
                reconciliation=source,
                result="committed",
                target_type=DOCUMENT_TYPE,
                target_id=obj.pk,
                target_no=obj.prepare_no,
                review_id=tx.review_id,
                review_hash=eligibility_hash,
                command_id=tx.command_id,
                idempotency_key=idempotency_key,
                actor_name=user.username,
                tenant_or_scope=f"{source.tenant_id}:{source.company_id}",
                evidence_hash=eligibility_hash,
                evidence={"eligibility": gate["eligibility"], "businessGate": gate["checks"]},
            )
            obj.audit_record_id = audit.pk
            obj.save(update_fields=["audit_record_id", "updated_at"])
            _inject("after_audit_insert", failure_step)
            idem.status = BusinessActionIdempotency.Status.COMMITTED
            idem.target_type = DOCUMENT_TYPE
            idem.target_id = obj.pk
            idem.target_no = obj.prepare_no
            idem.result_reference = str(obj.pk)
            idem.save(update_fields=[
                "status", "target_type", "target_id", "target_no", "result_reference", "updated_at"
            ])
            _inject("after_idempotency_committed", failure_step)
            reservation.status = BusinessDocumentNumberReservation.Status.CONSUMED
            reservation.consumed_at = timezone.now()
            reservation.save(update_fields=["status", "consumed_at"])
            _inject("after_number_consumed", failure_step)
            lock.state = "released"
            lock.released_at = timezone.now()
            lock.save(update_fields=["state", "released_at"])
            _inject("before_database_commit", failure_step)
            committed_result = {
                "classification": "created",
                "created": True,
                "data": serialize_prepare(obj),
                "businessGate": gate["checks"],
                "transactionGate": {
                    "atomicTransaction": True,
                    "idempotencyUnique": True,
                    "sourceUnique": True,
                    "numberUnique": True,
                    "persistentLock": True,
                    "commitRecovery": True,
                    "atomicAudit": True,
                    "serverAuthorization": True,
                    "productionRolloutEnabled": settings.PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED,
                },
                "sourceRelationId": relation.pk,
                "auditRecordId": audit.pk,
            }
        if failure_step == "after_response_send":
            raise ReconciliationError(
                "PIP_COMMIT_UNKNOWN",
                "Commit succeeded but the response was not delivered",
                503,
                True,
            )
        return committed_result
    except ReconciliationError as exc:
        _persist_aborted_number(aborted_number_context, exc.code)
        raise
    except IntegrityError as exc:
        _persist_aborted_number(aborted_number_context, "PIP_DATABASE_UNIQUENESS_CONFLICT")
        existing = PurchaseInvoicePrepare.objects.filter(
            source_purchase_reconciliation_id=reconciliation_id
        ).first()
        if existing:
            return _existing_result(existing, "existing_target")
        raise ReconciliationError("PIP_CONFLICT", "Database uniqueness conflict", 409) from exc


def recover_generation_result(idempotency_key, user=None):
    idem = BusinessActionIdempotency.objects.filter(
        action_code=ACTION_CODE,
        idempotency_key=idempotency_key,
    ).first()
    if not idem:
        raise ReconciliationError("PIP_GENERATION_RESULT_NOT_FOUND", "Generation result not found", 404)
    if idem.target_id:
        obj = PurchaseInvoicePrepare.objects.get(pk=idem.target_id)
        if user is not None and not user.is_superuser and user.company_id != obj.company_id:
            raise ReconciliationError("PIP_AUTH_SCOPE_DENIED", "Generation result is outside actor company scope", 403)
        return _existing_result(
            obj,
            "existing_result",
        )
    return {
        "classification": "recovery_required" if idem.status == "commit_unknown" else idem.status,
        "created": False,
        "idempotencyStatus": idem.status,
    }


def retry_on_sqlite_lock(callable_, attempts=3, interval_seconds=0.05):
    for attempt in range(attempts):
        try:
            return callable_()
        except OperationalError as exc:
            if "database is locked" not in str(exc).lower() or attempt + 1 >= attempts:
                raise ReconciliationError(
                    "PIP_DATABASE_LOCK_RETRY_EXHAUSTED",
                    "SQLite lock retry threshold exceeded",
                    503,
                    True,
                ) from exc
            time.sleep(interval_seconds)
