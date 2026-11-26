import uuid
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    BusinessActionAuditRecord,
    BusinessActionSourceLock,
    BusinessActionTransaction,
    PurchaseReconciliation,
    PurchaseReconciliationCheckExecution,
    PurchaseReconciliationDifference,
    PurchaseReconciliationEvidence,
)
from .providers import PayableCheckEvidenceProvider, SupplierSettlementEvidenceProvider
from .services import ReconciliationError, canonical_hash
from workflow_runtime.facts import (
    business_state_transition_facts_from_allowed_transitions,
)
from workflow_runtime.state_transitions import transition_business_object

CHECK_ACTION_CODE = "complete_purchase_reconciliation"
READY = "ready_for_invoice_prepare"
BLOCKED = "blocked"
RECONCILIATION_STATES = (
    PurchaseReconciliation.Status.DRAFT,
    PurchaseReconciliation.Status.MATCHED,
    PurchaseReconciliation.Status.DIFFERENCE_FOUND,
    PurchaseReconciliation.Status.SOURCE_MISSING,
)
RECONCILIATION_CHECK_TARGET_STATES = (
    PurchaseReconciliation.Status.MATCHED,
    PurchaseReconciliation.Status.DIFFERENCE_FOUND,
    PurchaseReconciliation.Status.SOURCE_MISSING,
)
RECONCILIATION_CHECK_TRANSITIONS = {
    (source, target)
    for source in RECONCILIATION_STATES
    for target in RECONCILIATION_CHECK_TARGET_STATES
}
RECONCILIATION_FACT_TRANSITIONS = {
    (source, target, CHECK_ACTION_CODE)
    for source, target in RECONCILIATION_CHECK_TRANSITIONS
}


def authorize_read(user, reconciliation=None):
    if not user or not user.is_authenticated:
        raise ReconciliationError("PRC_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if reconciliation is not None and not user.is_superuser and user.company_id != reconciliation.company_id:
        raise ReconciliationError("PRC_AUTH_SCOPE_DENIED", "Reconciliation is outside actor company scope", 403)


def authorize_check(user, reconciliation):
    authorize_read(user, reconciliation)
    if not (user.is_superuser or user.has_perm("reconciliation.complete_purchase_reconciliation")):
        raise ReconciliationError("PRC_AUTH_PERMISSION_DENIED", "Reconciliation check permission required", 403)
    if not settings.PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED:
        raise ReconciliationError("PRC_AUTH_FEATURE_DISABLED", "Server feature flag is disabled", 403)
    if (
        reconciliation.tenant_id not in settings.PCE_PURCHASE_RECONCILIATION_TEST_TENANTS
        and not settings.PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED
    ):
        raise ReconciliationError("PRC_AUTH_PRODUCTION_ROLLOUT_DISABLED", "Production rollout is disabled", 403)


def derive_next_step_readiness(reconciliation):
    return READY if reconciliation.status == PurchaseReconciliation.Status.MATCHED and reconciliation.difference_count == 0 else BLOCKED


def build_reconciliation_state_facts(reconciliation):
    return business_state_transition_facts_from_allowed_transitions(
        business_object=reconciliation,
        object_type="purchase_reconciliation",
        allowed_transitions=RECONCILIATION_FACT_TRANSITIONS,
        audit_target_types=("purchase_reconciliation",),
        initial_states=(PurchaseReconciliation.Status.DRAFT,),
    )


def build_invoice_prepare_eligibility(reconciliation):
    evidence = list(reconciliation.evidence_records.all())
    provider_codes = {item.provider_code for item in evidence}
    repository_codes = {item.repository_code for item in evidence}
    authority_types = {item.authority_type for item in evidence}
    authority_ids = {f"{item.authority_type}:{item.authority_object_id}" for item in evidence}
    independent = (
        len(evidence) == 2
        and len(provider_codes) == 2
        and len(repository_codes) == 2
        and authority_types == {"supplier_settlement", "payable_check"}
        and len(authority_ids) == 2
    )
    readiness = derive_next_step_readiness(reconciliation)
    eligible = readiness == READY and independent
    state_facts = build_reconciliation_state_facts(reconciliation)
    eligible = eligible and state_facts["stateMachineConsistent"]
    reasons = []
    if reconciliation.status != PurchaseReconciliation.Status.MATCHED:
        reasons.append("PRC_STATUS_NOT_MATCHED")
    if reconciliation.difference_count:
        reasons.append("PRC_DIFFERENCE_PRESENT")
    if not independent:
        reasons.append("PRC_EVIDENCE_NOT_INDEPENDENT")
    if not state_facts["stateMachineConsistent"]:
        reasons.append("PRC_STATE_MACHINE_FACTS_INCONSISTENT")
    return {
        "eligible": eligible,
        "eligibilityCode": "PRC_INVOICE_PREPARE_ELIGIBLE" if eligible else "PRC_INVOICE_PREPARE_BLOCKED",
        "reconciliationId": reconciliation.pk,
        "reconciliationNo": reconciliation.reconciliation_no,
        "status": reconciliation.status,
        "checkResultCode": reconciliation.check_result_code,
        "differenceCount": reconciliation.difference_count,
        "nextStepReadiness": readiness,
        "evidenceIntegrity": "passed" if independent else "failed",
        "evidenceSourceCount": len(evidence),
        "evidenceSourcesIndependent": independent,
        "reconciliationVersion": reconciliation.version,
        "checkVersion": reconciliation.version if reconciliation.checked_at else 0,
        "evaluatedAt": timezone.now().isoformat(),
        "blockingReasons": reasons,
        "currentStateSource": "server",
        **state_facts,
    }


def serialize_reconciliation(reconciliation):
    state_facts = build_reconciliation_state_facts(reconciliation)
    return {
        "id": reconciliation.pk,
        "reconciliationNo": reconciliation.reconciliation_no,
        "sourceKey": reconciliation.source_key,
        "sourceSettlementNo": reconciliation.source_supplier_settlement_no,
        "sourcePayableCheckNo": reconciliation.source_payable_check_no,
        "purchaseOrderNo": reconciliation.purchase_order_no,
        "supplierId": reconciliation.supplier_id,
        "supplierName": reconciliation.supplier_name,
        "currency": reconciliation.currency,
        "settlementAmount": str(reconciliation.settlement_amount),
        "quantity": str(reconciliation.quantity),
        "status": reconciliation.status,
        "checkResultCode": reconciliation.check_result_code,
        "differenceCount": reconciliation.difference_count,
        "version": reconciliation.version,
        "checkedAt": reconciliation.checked_at.isoformat() if reconciliation.checked_at else None,
        "nextStepReadiness": derive_next_step_readiness(reconciliation),
        "invoicePrepareEligibility": build_invoice_prepare_eligibility(reconciliation),
        "currentStateSource": "server",
        **state_facts,
        "strictFacts": {
            "currentStateSource": "server",
            **state_facts,
        },
    }


def _difference(code, field, expected, actual):
    return {
        "differenceCode": code,
        "fieldName": field,
        "expectedValue": str(expected),
        "actualValue": str(actual),
    }


def compare_authority_evidence(settlement, payable):
    differences = []
    comparisons = [
        ("PRC_SUPPLIER_DIFFERENCE", "supplierId", settlement["supplierId"], payable["supplierId"]),
        ("PRC_LEGAL_ENTITY_DIFFERENCE", "legalEntityId", settlement["legalEntityId"], payable["legalEntityId"]),
        ("PRC_LEDGER_BOOK_DIFFERENCE", "ledgerBookId", settlement["ledgerBookId"], payable["ledgerBookId"]),
        ("PRC_CURRENCY_DIFFERENCE", "currency", settlement["currency"], payable["currency"]),
        ("PRC_AMOUNT_DIFFERENCE", "amount", Decimal(settlement["amount"]), Decimal(payable["amount"])),
        ("PRC_QUANTITY_DIFFERENCE", "quantity", Decimal(settlement["quantity"]), Decimal(payable["quantity"])),
    ]
    for code, field, expected, actual in comparisons:
        if expected != actual:
            differences.append(_difference(code, field, expected, actual))
    if settlement["businessStatus"] not in {"reconciling", "ready_for_reconciliation"}:
        differences.append(_difference("PRC_SETTLEMENT_STATUS_INVALID", "supplierSettlementStatus", "reconciling", settlement["businessStatus"]))
    if payable["businessStatus"] != "payable_prepared":
        differences.append(_difference("PRC_PAYABLE_STATUS_INVALID", "payableCheckStatus", "payable_prepared", payable["businessStatus"]))
    return differences


def _inject(step, requested):
    if step == requested:
        if not settings.PCE_PURCHASE_RECONCILIATION_FAILURE_INJECTION_ENABLED:
            raise ReconciliationError("PRC_FAILURE_INJECTION_DISABLED", "Failure injection is disabled", 403)
        raise ReconciliationError(f"PRC_CHECK_INJECTED_{step.upper()}", f"Injected check failure at {step}", 503, True)


def complete_reconciliation_check(
    *,
    user,
    reconciliation_id,
    idempotency_key,
    expected_version,
    explicit_user_action,
    failure_step="",
    settlement_provider=None,
    payable_provider=None,
):
    if not explicit_user_action:
        raise ReconciliationError("PRC_EXPLICIT_USER_ACTION_REQUIRED", "Explicit user action is required", 400)
    if not idempotency_key:
        raise ReconciliationError("PRC_IDEMPOTENCY_KEY_INVALID", "Idempotency key is required", 400)
    request_hash = canonical_hash({"reconciliationId": reconciliation_id, "expectedVersion": expected_version})
    prior = PurchaseReconciliationCheckExecution.objects.filter(idempotency_key=idempotency_key).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ReconciliationError("PRC_IDEMPOTENCY_CONFLICT", "Idempotency key payload conflict", 409)
        return {**prior.result_payload, "replayed": True}
    settlement_provider = settlement_provider or SupplierSettlementEvidenceProvider()
    payable_provider = payable_provider or PayableCheckEvidenceProvider()
    if settlement_provider.provider_code == payable_provider.provider_code:
        raise ReconciliationError("PRC_EVIDENCE_PROVIDER_COLLISION", "Evidence providers must be independent", 409)
    if settlement_provider.repository.repository_code == payable_provider.repository.repository_code:
        raise ReconciliationError("PRC_EVIDENCE_REPOSITORY_COLLISION", "Evidence repositories must be independent", 409)

    try:
        with transaction.atomic():
            reconciliation = PurchaseReconciliation.objects.get(pk=reconciliation_id)
            authorize_check(user, reconciliation)
            _inject("after_authorization", failure_step)
            lock_key = f"purchase_reconciliation_check:{reconciliation.pk}"
            lock, created = BusinessActionSourceLock.objects.get_or_create(
                lock_key=lock_key,
                defaults={
                    "owner_transaction_id": idempotency_key,
                    "state": "acquired",
                },
            )
            if not created:
                if lock.state == "acquired" and lock.owner_transaction_id != idempotency_key:
                    raise ReconciliationError("PRC_CHECK_LOCK_BUSY", "Reconciliation check is already in progress", 409, True)
                lock.owner_transaction_id = idempotency_key
                lock.state = "acquired"
                lock.released_at = None
                lock.save(update_fields=["owner_transaction_id", "state", "released_at", "acquired_at"])
            _inject("after_persistent_lock", failure_step)
            if reconciliation.version != expected_version:
                raise ReconciliationError("PRC_VERSION_CONFLICT", "Reconciliation version changed", 409)
            _inject("after_version_check", failure_step)
            settlement = settlement_provider.load(reconciliation)
            _inject("after_settlement_evidence", failure_step)
            payable = payable_provider.load(reconciliation)
            _inject("after_payable_evidence", failure_step)
            next_version = reconciliation.version + 1
            PurchaseReconciliationDifference.objects.filter(reconciliation=reconciliation).delete()
            PurchaseReconciliationEvidence.objects.filter(reconciliation=reconciliation).delete()
            _inject("after_cleanup", failure_step)

            if not settlement or not payable:
                status = PurchaseReconciliation.Status.SOURCE_MISSING
                check_result_code = "PRC_CHECK_SOURCE_MISSING"
                differences = [_difference(
                    "PRC_AUTHORITY_SOURCE_MISSING",
                    "authoritySource",
                    "supplier_settlement,payable_check",
                    ",".join(name for name, value in (("supplier_settlement", settlement), ("payable_check", payable)) if value),
                )]
                evidence_items = [item for item in (settlement, payable) if item]
            else:
                if settlement["authorityType"] == payable["authorityType"]:
                    raise ReconciliationError("PRC_EVIDENCE_AUTHORITY_COLLISION", "Authority objects must have different types", 409)
                evidence_items = [settlement, payable]
                differences = compare_authority_evidence(settlement, payable)
                status = PurchaseReconciliation.Status.DIFFERENCE_FOUND if differences else PurchaseReconciliation.Status.MATCHED
                check_result_code = "PRC_CHECK_DIFFERENCE_FOUND" if differences else "PRC_CHECK_MATCHED"

            for item in evidence_items:
                PurchaseReconciliationEvidence.objects.create(
                    reconciliation=reconciliation,
                    provider_code=item["providerCode"],
                    repository_code=item["repositoryCode"],
                    authority_type=item["authorityType"],
                    authority_object_id=item["authorityObjectId"],
                    authority_object_no=item["authorityObjectNo"],
                    authority_version=item["authorityVersion"],
                    business_hash=item["businessHash"],
                    evidence=item,
                )
            _inject("after_evidence_write", failure_step)
            for item in differences:
                PurchaseReconciliationDifference.objects.create(
                    reconciliation=reconciliation,
                    check_version=next_version,
                    difference_code=item["differenceCode"],
                    field_name=item["fieldName"],
                    expected_value=item["expectedValue"],
                    actual_value=item["actualValue"],
                )
            _inject("after_difference_write", failure_step)

            source_status = reconciliation.status
            reconciliation.check_result_code = check_result_code
            reconciliation.difference_count = len(differences)
            reconciliation.checked_at = timezone.now()
            reconciliation.checked_by = user
            reconciliation.save(update_fields=[
                "check_result_code",
                "difference_count",
                "checked_at",
                "checked_by",
                "updated_at",
            ])
            transition_evidence = {
                "reconciliationId": reconciliation.pk,
                "sourceStatus": source_status,
                "targetStatus": status,
                "checkResultCode": check_result_code,
                "differenceCount": len(differences),
                "expectedVersion": expected_version,
            }
            transition_hash = canonical_hash(transition_evidence)
            transition_tx = BusinessActionTransaction.objects.create(
                transaction_id=f"PRC-CHECK-{uuid.uuid4().hex}",
                action_code=CHECK_ACTION_CODE,
                idempotency_key=idempotency_key,
                tenant_id=reconciliation.tenant_id,
                source_key=reconciliation.source_key,
                command_id=f"PRC-CHECK-CMD-{uuid.uuid4().hex}",
                transaction_plan_id="purchase-reconciliation-check-atomic-v1",
                review_id=f"reconciliation-check:{reconciliation.pk}:{next_version}",
                review_hash=transition_hash,
                status=BusinessActionTransaction.Status.COMMITTED,
                outcome="checked",
                commit_status="committed",
                recovery_status="not_required",
                result_hash=transition_hash,
                reconciliation=reconciliation,
            )
            transition_audit = BusinessActionAuditRecord.objects.create(
                transaction=transition_tx,
                action_code=CHECK_ACTION_CODE,
                tenant_id=reconciliation.tenant_id,
                actor=user,
                source_key=reconciliation.source_key,
                reconciliation=reconciliation,
                result="committed",
                target_type="purchase_reconciliation",
                target_id=reconciliation.pk,
                target_no=reconciliation.reconciliation_no,
                review_id=transition_tx.review_id,
                review_hash=transition_hash,
                command_id=transition_tx.command_id,
                idempotency_key=idempotency_key,
                actor_name=user.get_username(),
                tenant_or_scope=(
                    f"{reconciliation.tenant_id}:company:{reconciliation.company_id}"
                ),
                evidence_hash=transition_hash,
                evidence=transition_evidence,
            )
            transition_business_object(
                business_object=reconciliation,
                object_type="purchase_reconciliation",
                source_state=source_status,
                target_state=status,
                action_code=CHECK_ACTION_CODE,
                operator=user,
                reason="Purchase reconciliation check completed",
                audit_reference=(
                    f"BusinessActionAuditRecord:{transition_audit.pk}"
                ),
                allowed_transitions=RECONCILIATION_CHECK_TRANSITIONS,
            )
            _inject("after_status_write", failure_step)
            result = {
                "reconciliation": serialize_reconciliation(reconciliation),
                "differences": differences,
                "replayed": False,
            }
            PurchaseReconciliationCheckExecution.objects.create(
                reconciliation=reconciliation,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                expected_version=expected_version,
                result_status=status,
                check_result_code=check_result_code,
                difference_count=len(differences),
                actor=user,
                result_payload=result,
            )
            _inject("after_execution_write", failure_step)
            lock.state = "released"
            lock.released_at = timezone.now()
            lock.save(update_fields=["state", "released_at"])
            _inject("after_lock_release", failure_step)
            return result
    except PurchaseReconciliation.DoesNotExist as exc:
        raise ReconciliationError("PRC_RECONCILIATION_NOT_FOUND", "Purchase reconciliation not found", 404) from exc
    except IntegrityError as exc:
        raise ReconciliationError("PRC_CHECK_CONCURRENCY_CONFLICT", "Concurrent check was rejected by a database constraint", 409) from exc
