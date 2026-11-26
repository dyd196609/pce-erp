import hashlib
import json
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
)
from workflow_runtime.facts import (
    business_state_transition_facts_from_allowed_transitions,
)

from .models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionSourceLock,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
    BusinessDocumentNumberSequence,
    PurchaseReconciliation,
    PurchaseReconciliationReview,
    PurchaseReconciliationSourceRelation,
    PurchaseReconciliationSourceSnapshot,
)

ACTION_CODE = "generate_purchase_reconciliation"
DOCUMENT_TYPE = "purchase_reconciliation"
NUMBER_POLICY_VERSION = "prc-sequence-v1"
TRANSACTION_PLAN_ID = "purchase-reconciliation-atomic-v1"


@dataclass
class ReconciliationError(Exception):
    code: str
    message: str
    http_status: int = 409
    retryable: bool = False

    def __str__(self):
        return self.message


def canonical_hash(value):
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def authorize(user, source):
    if not user or not user.is_authenticated:
        raise ReconciliationError("PRC_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not (user.is_superuser or user.has_perm("reconciliation.generate_purchase_reconciliation")):
        raise ReconciliationError("PRC_AUTH_PERMISSION_DENIED", "Generation permission required", 403)
    if user.company_id != source.company_id:
        raise ReconciliationError("PRC_AUTH_SCOPE_DENIED", "Source is outside actor company scope", 403)
    if not settings.PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED:
        raise ReconciliationError("PRC_AUTH_FEATURE_DISABLED", "Server feature flag is disabled", 403)
    if source.tenant_id not in settings.PCE_PURCHASE_RECONCILIATION_TEST_TENANTS and not settings.PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED:
        raise ReconciliationError("PRC_AUTH_PRODUCTION_ROLLOUT_DISABLED", "Production rollout is disabled", 403)


def validate_business_gate(source, review):
    checks = {
        "source_state": source.lifecycle_state == "reconciling",
        "payable_prepared": source.payable_status == "payable_prepared",
        "simulation_integrity": source.simulation_integrity == "passed" and review.simulation_integrity == "passed",
        "review_state": review.state == "review_passed" and review.decision == "approved",
        "review_audit": review.audit_complete and review.fatal_risk_count == 0,
        "snapshot": review.source_snapshot_hash == source.snapshot_hash,
        "supplier": review.supplier_id == source.supplier_id,
        "legal_entity": review.legal_entity_id == source.legal_entity_id,
        "ledger_book": review.ledger_book_id == source.ledger_book_id,
        "currency": review.currency == source.currency,
        "amount": review.amount == source.amount,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ReconciliationError("PRC_BUSINESS_GATE_REJECTED", f"Business gate rejected: {','.join(failed)}", 409)


def allocate_number(source):
    number_scope = "|".join([DOCUMENT_TYPE, source.legal_entity_id, source.ledger_book_id, source.accounting_period])
    sequence, _ = BusinessDocumentNumberSequence.objects.select_for_update().get_or_create(number_scope=number_scope)
    sequence.current_value += 1
    sequence.save(update_fields=["current_value", "updated_at"])
    number = f"PRC{source.accounting_period.replace('-', '')}{sequence.current_value:08d}"
    return {"number": number, "scope": number_scope, "sequence": sequence.current_value}


def _inject(step, requested):
    if requested == step:
        if not settings.PCE_PURCHASE_RECONCILIATION_FAILURE_INJECTION_ENABLED:
            raise ReconciliationError("PRC_FAILURE_INJECTION_DISABLED", "Failure injection is disabled", 403)
        raise ReconciliationError(f"PRC_INJECTED_{step.upper()}", f"Injected failure at {step}", 503, True)


def _persist_failure(source, review, idempotency_key, request_hash, transaction_id, command_id, number_info, error):
    with transaction.atomic():
        BusinessActionIdempotency.objects.update_or_create(
            action_code=ACTION_CODE, idempotency_key=idempotency_key,
            defaults={
                "tenant_id": source.tenant_id, "source_key": source.source_key, "request_hash": request_hash,
                "status": "failed_retryable" if error.retryable else "failed_terminal", "transaction_id": transaction_id,
                "error_code": error.code, "result_reference": "",
            },
        )
        if number_info:
            sequence, _ = BusinessDocumentNumberSequence.objects.select_for_update().get_or_create(number_scope=number_info["scope"])
            if sequence.current_value < number_info["sequence"]:
                sequence.current_value = number_info["sequence"]
                sequence.save(update_fields=["current_value", "updated_at"])
            BusinessDocumentNumberReservation.objects.get_or_create(
                reserved_number=number_info["number"],
                defaults={
                    "document_type": DOCUMENT_TYPE, "number_policy_version": NUMBER_POLICY_VERSION,
                    "number_scope": number_info["scope"], "legal_entity_id": source.legal_entity_id,
                    "ledger_book_id": source.ledger_book_id, "tenant_id": source.tenant_id,
                    "accounting_period": source.accounting_period, "idempotency_key": idempotency_key,
                    "status": "aborted", "aborted_at": timezone.now(), "abort_reason": error.code,
                },
            )
        BusinessActionTransaction.objects.update_or_create(
            transaction_id=transaction_id,
            defaults={
                "action_code": ACTION_CODE, "source_key": source.source_key, "idempotency_key": idempotency_key,
                "tenant_id": source.tenant_id, "command_id": command_id, "transaction_plan_id": TRANSACTION_PLAN_ID,
                "review_id": review.review_id, "review_hash": review.business_hash, "status": "failed",
                "outcome": "rejected", "commit_status": "rolled_back", "recovery_status": "not_committed_safe_to_retry",
                "requires_recovery": error.retryable, "requires_manual_intervention": False, "error_code": error.code,
            },
        )


def _existing_result(obj, idempotency_key, kind):
    result = serialize_result(obj, replayed=True)
    result["resultKind"] = kind
    result["idempotencyKey"] = idempotency_key
    return result


def generate_purchase_reconciliation(*, user, source_key, final_review_id, idempotency_key, explicit_user_action=True, failure_step=""):
    if not explicit_user_action:
        raise ReconciliationError("PRC_EXPLICIT_USER_ACTION_REQUIRED", "Explicit user action is required", 400)
    if not idempotency_key or len(idempotency_key) > 120:
        raise ReconciliationError("PRC_IDEMPOTENCY_KEY_INVALID", "A valid idempotency key is required", 400)
    try:
        source = PurchaseReconciliationSourceSnapshot.objects.get(source_key=source_key)
        review = PurchaseReconciliationReview.objects.select_related("source").get(review_id=final_review_id, source=source)
    except (PurchaseReconciliationSourceSnapshot.DoesNotExist, PurchaseReconciliationReview.DoesNotExist):
        raise ReconciliationError("PRC_SOURCE_OR_REVIEW_NOT_FOUND", "Source or final review not found", 404)
    authorize(user, source)
    _inject("after_authorization", failure_step)
    request_hash = canonical_hash({"sourceKey": source_key, "finalReviewId": final_review_id})
    prior = BusinessActionIdempotency.objects.filter(action_code=ACTION_CODE, idempotency_key=idempotency_key).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ReconciliationError("PRC_IDEMPOTENCY_CONFLICT", "Idempotency key payload conflict", 409)
        if prior.status == "committed":
            return _existing_result(PurchaseReconciliation.objects.get(pk=prior.target_id), idempotency_key, "existing_result")
        if prior.status == "failed_retryable":
            raise ReconciliationError("PRC_RECOVERY_REQUIRED", "Previous attempt requires fact recovery", 409, True)
    validate_business_gate(source, review)
    _inject("after_business_gate", failure_step)
    transaction_id = f"PRCTX-{uuid.uuid4().hex}"
    command_id = f"PRCCMD-{uuid.uuid4().hex}"
    number_info = None
    try:
        with transaction.atomic():
            lock, _ = BusinessActionSourceLock.objects.select_for_update().get_or_create(
                lock_key=f"purchase_reconciliation_generation::{source.source_key}",
                defaults={"owner_transaction_id": transaction_id, "state": "acquired"},
            )
            if lock.state == "acquired" and lock.owner_transaction_id != transaction_id:
                raise ReconciliationError("PRC_SOURCE_LOCKED", "Source is locked", 409, True)
            lock.owner_transaction_id = transaction_id; lock.state = "acquired"; lock.released_at = None; lock.save()
            _inject("after_source_lock", failure_step)
            source = PurchaseReconciliationSourceSnapshot.objects.select_for_update().get(pk=source.pk)
            review = PurchaseReconciliationReview.objects.select_for_update().get(pk=review.pk)
            _inject("before_source_reload", failure_step)
            validate_business_gate(source, review)
            _inject("after_revalidation", failure_step)
            idem = BusinessActionIdempotency.objects.select_for_update().filter(action_code=ACTION_CODE, idempotency_key=idempotency_key).first()
            if idem:
                if idem.request_hash != request_hash:
                    raise ReconciliationError("PRC_IDEMPOTENCY_CONFLICT", "Idempotency key payload conflict", 409)
                if idem.status == "committed":
                    lock.state = "released"; lock.released_at = timezone.now(); lock.save()
                    return _existing_result(PurchaseReconciliation.objects.get(pk=idem.target_id), idempotency_key, "existing_result")
                raise ReconciliationError("PRC_ACTION_IN_PROGRESS", "Action is already processing", 409, True)
            relation = PurchaseReconciliationSourceRelation.objects.select_for_update().filter(source_key=source.source_key).select_related("reconciliation").first()
            if relation:
                lock.state = "released"; lock.released_at = timezone.now(); lock.save()
                return _existing_result(relation.reconciliation, idempotency_key, "existing_target")
            idem = BusinessActionIdempotency.objects.create(
                action_code=ACTION_CODE, idempotency_key=idempotency_key, tenant_id=source.tenant_id,
                source_key=source.source_key, request_hash=request_hash, status="in_progress", transaction_id=transaction_id,
            )
            _inject("after_idempotency", failure_step)
            number_info = allocate_number(source)
            reservation = BusinessDocumentNumberReservation.objects.create(
                document_type=DOCUMENT_TYPE, number_policy_version=NUMBER_POLICY_VERSION, number_scope=number_info["scope"],
                legal_entity_id=source.legal_entity_id, ledger_book_id=source.ledger_book_id,
                reserved_number=number_info["number"], tenant_id=source.tenant_id, accounting_period=source.accounting_period,
                idempotency_key=idempotency_key, status="reserved",
            )
            _inject("after_number_reservation", failure_step)
            obj = create_business_object_with_initial_state(
                model=PurchaseReconciliation,
                initial_state=PurchaseReconciliation.Status.DRAFT,
                reconciliation_no=number_info["number"], tenant_id=source.tenant_id, company_id=source.company_id,
                source_key=source.source_key, source_supplier_settlement_no=source.supplier_settlement_no,
                source_payable_check_no=source.source_payable_check_no, source_payable_prepare_no=source.source_payable_prepare_no,
                purchase_order_no=source.purchase_order_no, price_approval_no=source.price_approval_no,
                supplier_id=source.supplier_id, supplier_name=source.supplier_name, legal_entity_id=source.legal_entity_id,
                ledger_book_id=source.ledger_book_id, currency=source.currency, exchange_rate=source.exchange_rate,
                accounting_period=source.accounting_period, settlement_amount=source.amount, quantity=source.quantity, unit=source.unit,
                source_candidate_id=source.source_candidate_id, simulation_request_id=source.simulation_request_id,
                simulation_result_id=source.simulation_result_id, source_snapshot_hash=source.snapshot_hash,
                review_id=review.review_id, review_hash=review.business_hash, command_id=command_id,
                transaction_plan_id=TRANSACTION_PLAN_ID, idempotency_key=idempotency_key, number_reservation_id=reservation.pk,
                created_by=user,
            )
            _inject("after_target_insert", failure_step)
            relation = PurchaseReconciliationSourceRelation.objects.create(
                reconciliation=obj, source_type="supplier_settlement", source_key=source.source_key,
                source_document_no=source.supplier_settlement_no, source_supplier_settlement_no=source.supplier_settlement_no,
                relationship_type="source_of", source_snapshot_hash=source.snapshot_hash,
            )
            _inject("after_relation_insert", failure_step)
            _inject("after_reverse_relation", failure_step)
            tx = BusinessActionTransaction.objects.create(
                transaction_id=transaction_id, action_code=ACTION_CODE, source_key=source.source_key,
                idempotency_key=idempotency_key, tenant_id=source.tenant_id, command_id=command_id,
                transaction_plan_id=TRANSACTION_PLAN_ID, review_id=review.review_id, review_hash=review.business_hash,
                status="committing", outcome="pending", commit_status="pending", recovery_status="not_required",
                reconciliation=obj,
            )
            evidence = {"reviewId": review.review_id, "sourceSnapshotHash": source.snapshot_hash, "relationId": relation.pk}
            audit = BusinessActionAuditRecord.objects.create(
                transaction=tx, action_code=ACTION_CODE, tenant_id=source.tenant_id, actor=user, actor_name=user.real_name,
                source_key=source.source_key, reconciliation=obj, result="committed", target_type="purchase_reconciliation",
                target_id=obj.pk, target_no=obj.reconciliation_no, review_id=review.review_id, review_hash=review.business_hash,
                command_id=command_id, idempotency_key=idempotency_key, tenant_or_scope=f"{source.tenant_id}:company:{source.company_id}",
                evidence_hash=canonical_hash(evidence), evidence=evidence,
            )
            _inject("after_audit", failure_step)
            now = timezone.now()
            reservation.status = "consumed"; reservation.target = obj; reservation.consumed_at = now; reservation.save(update_fields=["status", "target", "consumed_at"])
            _inject("after_number_consumed", failure_step)
            result_hash = canonical_hash({"targetId": obj.pk, "targetNo": obj.reconciliation_no, "reviewHash": review.business_hash})
            idem.status = "committed"; idem.target_type = "purchase_reconciliation"; idem.target_id = obj.pk
            idem.target_no = obj.reconciliation_no; idem.result_reference = str(obj.pk); idem.error_code = ""; idem.save()
            tx.status = "committed"; tx.outcome = "created"; tx.commit_status = "committed"; tx.result_hash = result_hash; tx.save()
            obj.audit_record_id = audit.pk; obj.save(update_fields=["audit_record_id", "updated_at"])
            _inject("after_status_update", failure_step)
            lock.state = "released"; lock.released_at = now; lock.save()
            _inject("before_commit", failure_step)
        if failure_step == "after_commit_before_response":
            raise ReconciliationError("PRC_COMMIT_UNKNOWN", "Commit outcome is unknown; recover by idempotency key", 503, True)
        return serialize_result(obj, idem, replayed=False)
    except IntegrityError as exc:
        error = ReconciliationError("PRC_UNIQUE_CONSTRAINT", "A database uniqueness constraint rejected the write", 409)
        _persist_failure(source, review, idempotency_key, request_hash, transaction_id, command_id, number_info, error)
        raise error from exc
    except ReconciliationError as error:
        if error.code != "PRC_COMMIT_UNKNOWN":
            _persist_failure(source, review, idempotency_key, request_hash, transaction_id, command_id, number_info, error)
        raise


def serialize_result(obj, idem=None, replayed=False):
    states = (
        PurchaseReconciliation.Status.DRAFT,
        PurchaseReconciliation.Status.MATCHED,
        PurchaseReconciliation.Status.DIFFERENCE_FOUND,
        PurchaseReconciliation.Status.SOURCE_MISSING,
    )
    targets = (
        PurchaseReconciliation.Status.MATCHED,
        PurchaseReconciliation.Status.DIFFERENCE_FOUND,
        PurchaseReconciliation.Status.SOURCE_MISSING,
    )
    state_facts = business_state_transition_facts_from_allowed_transitions(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        allowed_transitions={
            (source, target, "complete_purchase_reconciliation")
            for source in states
            for target in targets
        },
        audit_target_types=(DOCUMENT_TYPE,),
        initial_states=(PurchaseReconciliation.Status.DRAFT,),
    )
    return {
        "id": obj.pk, "reconciliationNo": obj.reconciliation_no, "sourceKey": obj.source_key,
        "supplierSettlementNo": obj.source_supplier_settlement_no, "status": obj.status,
        "amount": str(obj.settlement_amount), "quantity": str(obj.quantity), "unit": obj.unit,
        "currency": obj.currency, "accountingPeriod": obj.accounting_period, "sourcePayableCheckNo": obj.source_payable_check_no,
        "idempotencyKey": idem.idempotency_key if idem else obj.idempotency_key, "replayed": replayed,
        "sourceSnapshotHash": obj.source_snapshot_hash, "finalReviewId": obj.review_id,
        "finalReviewBusinessHash": obj.review_hash, "commandId": obj.command_id,
        "currentStateSource": "server",
        **state_facts,
        "strictFacts": {
            "currentStateSource": "server",
            **state_facts,
        },
    }


def recover_by_idempotency(idempotency_key):
    idem = BusinessActionIdempotency.objects.filter(action_code=ACTION_CODE, idempotency_key=idempotency_key).first()
    if not idem:
        return {"classification": "not_committed_safe_to_retry"}
    if idem.status == "committed" and idem.target_id:
        obj = PurchaseReconciliation.objects.get(pk=idem.target_id)
        return {"classification": "committed", "result": serialize_result(obj, idem, replayed=True), "transactionId": idem.transaction_id}
    return {"classification": idem.status, "failureCode": idem.error_code, "transactionId": idem.transaction_id}
