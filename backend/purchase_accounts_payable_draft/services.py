import logging
import time
import uuid

from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from purchase_invoice_prepare.models import PurchaseInvoicePrepare
from purchase_invoice_prepare.v44_services import (
    build_ap_draft_eligibility,
    current_execution,
    current_snapshot,
)
from reconciliation.checking import build_invoice_prepare_eligibility
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionSourceLock,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
    BusinessDocumentNumberSequence,
)
from reconciliation.services import ReconciliationError, canonical_hash
from workflow_runtime.facts import (
    business_state_transition_facts_from_allowed_transitions,
)
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
)

from .models import (
    PurchaseAccountsPayableDraft,
    PurchaseAccountsPayableDraftSourceRelation,
    PurchaseAccountsPayableDraftSourceSnapshot,
)

logger = logging.getLogger(__name__)

ACTION_CODE = "generate_purchase_accounts_payable_draft"
DOCUMENT_TYPE = "purchase_accounts_payable_draft"
SOURCE_DOCUMENT_TYPE = "purchaseInvoicePrepare"
NUMBER_POLICY_VERSION = "purchase-ap-draft-sequence-v1"
TRANSACTION_PLAN_ID = "purchase-accounts-payable-draft-atomic-v1"
FAILURE_STEPS = (
    "after_authorization",
    "after_business_gate",
    "after_idempotency_registration",
    "after_persistent_lock",
    "after_locked_prepare_reload",
    "after_invoice_snapshot_reload",
    "after_validation_execution_reload",
    "after_identity_claim_reload",
    "after_reconciliation_reload",
    "after_eligibility_recalculation",
    "after_version_check",
    "after_existing_target_check",
    "after_number_reservation",
    "after_target_insert",
    "after_source_snapshot_insert",
    "after_relation_insert",
    "after_audit_insert",
    "after_idempotency_committed",
    "after_number_consumed",
    "before_database_commit",
    "before_response",
)

RULE_DEFINITIONS = (
    ("APD_GATE_SOURCE_EXISTS", "source", "sourceExists", True, "采购发票准备必须存在"),
    ("APD_GATE_SOURCE_TYPE_VALID", "source", "sourceDocumentType", SOURCE_DOCUMENT_TYPE, "唯一直接来源必须是采购发票准备"),
    ("APD_GATE_INVOICE_PREPARE_PREPARED", "source", "status", "prepared", "采购发票准备必须为 prepared"),
    ("APD_GATE_INVOICE_DATA_COMPLETE", "invoice_data", "invoiceDataStatus", "complete", "发票资料必须完整"),
    ("APD_GATE_VALIDATION_PASSED", "validation", "validationStatus", "passed", "发票校验必须通过"),
    ("APD_GATE_VALIDATION_RESULT_VALIDATED", "validation", "validationResultCode", "validated", "校验结果必须为 validated"),
    ("APD_GATE_ZERO_VALIDATION_ISSUE", "validation", "validationIssueCount", 0, "阻断校验问题必须为零"),
    ("APD_GATE_INVOICE_IDENTITY_ACTIVE", "identity", "invoiceIdentityStatus", "active", "发票身份 claim 必须 active"),
    ("APD_GATE_IDENTITY_OWNER_MATCH", "identity", "identityOwnerMatch", True, "身份 claim 必须属于当前准备对象和资料版本"),
    ("APD_GATE_SOURCE_RECONCILIATION_MATCHED", "reconciliation", "reconciliationStatus", "matched", "来源采购对账必须 matched"),
    ("APD_GATE_SOURCE_RECONCILIATION_ELIGIBLE", "reconciliation", "reconciliationEligibility", True, "来源采购对账 eligibility 必须有效"),
    ("APD_GATE_PREPARE_VERSION_MATCH", "version", "prepareVersion", "expected", "采购发票准备版本必须一致"),
    ("APD_GATE_DATA_VERSION_MATCH", "version", "invoiceDataVersion", "expected", "发票资料版本必须一致"),
    ("APD_GATE_VALIDATION_VERSION_MATCH", "version", "validationVersion", "expected", "校验版本必须一致"),
    ("APD_GATE_RECONCILIATION_VERSION_MATCH", "version", "reconciliationVersion", "expected", "采购对账版本必须一致"),
    ("APD_GATE_CHECK_VERSION_MATCH", "version", "checkVersion", "expected", "核对版本必须一致"),
    ("APD_GATE_AP_DRAFT_READY", "eligibility", "nextStepReadiness", "ready_for_accounts_payable_draft", "服务端应付草稿资格必须 ready"),
    ("APD_GATE_NO_EXISTING_TARGET", "target", "existingTargetCount", 0, "同一采购发票准备不得已有目标"),
    ("APD_GATE_AUDIT_EVIDENCE_COMPLETE", "audit", "auditEvidenceComplete", True, "来源校验审计证据必须完整"),
    ("APD_GATE_NO_FATAL_RISK", "risk", "fatalRiskCount", 0, "不得存在致命风险"),
)


def _inject(step, requested):
    if step != requested:
        return
    if not settings.PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FAILURE_INJECTION_ENABLED:
        raise ReconciliationError("APD_FAILURE_INJECTION_DISABLED", "Failure injection is disabled", 403)
    if step == "before_response":
        raise ReconciliationError(
            "APD_COMMIT_UNKNOWN",
            "Response lost after commit; recover by idempotency key",
            503,
            True,
        )
    raise ReconciliationError(
        f"APD_INJECTED_{step.upper()}",
        f"Injected failure at {step}",
        503,
        True,
    )


def _authorize(user, source):
    if not user or not user.is_authenticated:
        raise ReconciliationError("APD_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not (
        user.is_superuser
        or user.has_perm(
            "purchase_accounts_payable_draft.generate_purchase_accounts_payable_draft"
        )
    ):
        raise ReconciliationError("APD_AUTH_PERMISSION_DENIED", "Generation permission required", 403)
    if not user.is_superuser and user.company_id != source.company_id:
        raise ReconciliationError("APD_AUTH_SCOPE_DENIED", "Source is outside actor scope", 403)
    if not settings.PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FEATURE_ENABLED:
        raise ReconciliationError("APD_AUTH_FEATURE_DISABLED", "Server feature flag is disabled", 403)
    if (
        source.tenant_id
        not in settings.PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_TEST_TENANTS
        and not settings.PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED
    ):
        raise ReconciliationError(
            "APD_AUTH_PRODUCTION_ROLLOUT_DISABLED",
            "Production rollout is disabled",
            403,
        )


def _rule(code, category, source_field, actual, expected, message):
    passed = actual == expected
    return {
        "code": code,
        "category": category,
        "status": "passed" if passed else "failed",
        "severity": "error",
        "blocking": True,
        "actual": actual,
        "expected": expected,
        "message": message,
        "sourceField": source_field,
    }


def build_business_gate(
    source,
    *,
    expected_prepare_version=None,
    expected_invoice_data_version=None,
    expected_validation_version=None,
    expected_reconciliation_version=None,
    expected_check_version=None,
):
    snapshot = current_snapshot(source)
    execution = current_execution(source)
    claim = source.invoice_identity_claims.filter(status="active").first()
    reconciliation = source.source_purchase_reconciliation
    reconciliation_eligibility = build_invoice_prepare_eligibility(reconciliation)
    ap_eligibility = build_ap_draft_eligibility(source)
    target_count = PurchaseAccountsPayableDraft.objects.filter(
        source_purchase_invoice_prepare=source
    ).count()
    identity_owner_match = bool(
        claim
        and snapshot
        and claim.purchase_invoice_prepare_id == source.pk
        and claim.invoice_data_snapshot_id == snapshot.pk
        and snapshot.data_version == source.current_data_version
    )
    audit_complete = bool(
        execution
        and execution.audit_record_id
        and execution.status == "passed"
        and source.audit_record_id
    )
    actuals = {
        "APD_GATE_SOURCE_EXISTS": True,
        "APD_GATE_SOURCE_TYPE_VALID": SOURCE_DOCUMENT_TYPE,
        "APD_GATE_INVOICE_PREPARE_PREPARED": source.status,
        "APD_GATE_INVOICE_DATA_COMPLETE": source.invoice_data_status,
        "APD_GATE_VALIDATION_PASSED": source.validation_status,
        "APD_GATE_VALIDATION_RESULT_VALIDATED": source.validation_result_code,
        "APD_GATE_ZERO_VALIDATION_ISSUE": source.validation_issue_count,
        "APD_GATE_INVOICE_IDENTITY_ACTIVE": claim.status if claim else "missing",
        "APD_GATE_IDENTITY_OWNER_MATCH": identity_owner_match,
        "APD_GATE_SOURCE_RECONCILIATION_MATCHED": reconciliation.status,
        "APD_GATE_SOURCE_RECONCILIATION_ELIGIBLE": bool(
            reconciliation_eligibility["eligible"]
            and reconciliation.check_result_code == "PRC_CHECK_MATCHED"
            and reconciliation.difference_count == 0
            and reconciliation_eligibility["evidenceSourceCount"] == 2
            and reconciliation_eligibility["evidenceSourcesIndependent"] is True
        ),
        "APD_GATE_PREPARE_VERSION_MATCH": source.version,
        "APD_GATE_DATA_VERSION_MATCH": source.current_data_version,
        "APD_GATE_VALIDATION_VERSION_MATCH": source.current_validation_version,
        "APD_GATE_RECONCILIATION_VERSION_MATCH": reconciliation.version,
        "APD_GATE_CHECK_VERSION_MATCH": reconciliation_eligibility["checkVersion"],
        "APD_GATE_AP_DRAFT_READY": ap_eligibility["nextStepReadiness"],
        "APD_GATE_NO_EXISTING_TARGET": target_count,
        "APD_GATE_AUDIT_EVIDENCE_COMPLETE": audit_complete,
        "APD_GATE_NO_FATAL_RISK": 0,
    }
    expected_versions = {
        "APD_GATE_PREPARE_VERSION_MATCH": (
            source.version if expected_prepare_version is None else expected_prepare_version
        ),
        "APD_GATE_DATA_VERSION_MATCH": (
            source.current_data_version
            if expected_invoice_data_version is None
            else expected_invoice_data_version
        ),
        "APD_GATE_VALIDATION_VERSION_MATCH": (
            source.current_validation_version
            if expected_validation_version is None
            else expected_validation_version
        ),
        "APD_GATE_RECONCILIATION_VERSION_MATCH": (
            source.source_reconciliation_version
            if expected_reconciliation_version is None
            else expected_reconciliation_version
        ),
        "APD_GATE_CHECK_VERSION_MATCH": (
            source.source_check_version
            if expected_check_version is None
            else expected_check_version
        ),
    }
    rules = []
    for code, category, source_field, expected, message in RULE_DEFINITIONS:
        resolved_expected = expected_versions.get(code, expected)
        rules.append(
            _rule(
                code,
                category,
                source_field,
                actuals[code],
                resolved_expected,
                message,
            )
        )
    return {
        "passed": all(rule["status"] == "passed" for rule in rules),
        "rules": rules,
        "checks": {rule["code"]: rule["status"] == "passed" for rule in rules},
        "ruleCount": len(rules),
        "existingTargetCount": target_count,
        "eligibility": ap_eligibility,
        "reconciliationEligibility": reconciliation_eligibility,
        "snapshot": snapshot,
        "execution": execution,
        "claim": claim,
        "auditEvidenceComplete": audit_complete,
    }


def _raise_gate(gate):
    failures = [rule["code"] for rule in gate["rules"] if rule["status"] != "passed"]
    version_failures = {
        "APD_GATE_PREPARE_VERSION_MATCH",
        "APD_GATE_DATA_VERSION_MATCH",
        "APD_GATE_VALIDATION_VERSION_MATCH",
        "APD_GATE_RECONCILIATION_VERSION_MATCH",
        "APD_GATE_CHECK_VERSION_MATCH",
    }
    if version_failures.intersection(failures):
        raise ReconciliationError("APD_VERSION_CONFLICT", ",".join(failures), 409)
    if "APD_GATE_NO_EXISTING_TARGET" in failures:
        raise ReconciliationError("APD_EXISTING_TARGET", "Target already exists", 409)
    if "APD_GATE_INVOICE_PREPARE_PREPARED" in failures:
        raise ReconciliationError("APD_SOURCE_NOT_PREPARED", ",".join(failures), 409)
    if any(code.startswith("APD_GATE_VALIDATION") or code == "APD_GATE_ZERO_VALIDATION_ISSUE" for code in failures):
        raise ReconciliationError("APD_SOURCE_VALIDATION_INVALID", ",".join(failures), 409)
    if any("IDENTITY" in code for code in failures):
        raise ReconciliationError("APD_SOURCE_IDENTITY_INVALID", ",".join(failures), 409)
    raise ReconciliationError("APD_SOURCE_STALE", ",".join(failures), 409)


def _reserve_number(source, idempotency_key):
    reconciliation = source.source_purchase_reconciliation
    scope = ":".join(
        (
            DOCUMENT_TYPE,
            source.legal_entity_id,
            source.ledger_book_id,
            reconciliation.accounting_period,
        )
    )
    sequence, _ = BusinessDocumentNumberSequence.objects.get_or_create(number_scope=scope)
    sequence.current_value += 1
    number = (
        f"APD{reconciliation.accounting_period.replace('-', '')}"
        f"{sequence.current_value:08d}"
    )
    while BusinessDocumentNumberReservation.objects.filter(reserved_number=number).exists():
        sequence.current_value += 1
        number = (
            f"APD{reconciliation.accounting_period.replace('-', '')}"
            f"{sequence.current_value:08d}"
        )
    sequence.save(update_fields=["current_value", "updated_at"])
    reservation = BusinessDocumentNumberReservation.objects.create(
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
    return reservation, sequence.current_value


def _persist_aborted_number(context, reason):
    if not context:
        return
    with transaction.atomic():
        sequence, _ = BusinessDocumentNumberSequence.objects.get_or_create(
            number_scope=context["number_scope"]
        )
        if sequence.current_value < context["sequence_value"]:
            sequence.current_value = context["sequence_value"]
            sequence.save(update_fields=["current_value", "updated_at"])
        BusinessDocumentNumberReservation.objects.get_or_create(
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
                "abort_reason": str(reason)[:160],
                "reusable": False,
            },
        )


def serialize_source_snapshot(snapshot):
    if not snapshot:
        return None
    return {
        "id": snapshot.pk,
        "sourcePurchaseInvoicePrepareId": snapshot.source_purchase_invoice_prepare_id,
        "sourcePurchaseInvoicePrepareNo": snapshot.source_purchase_invoice_prepare_no,
        "sourcePrepareVersion": snapshot.source_prepare_version,
        "sourceInvoiceDataSnapshotId": snapshot.source_invoice_data_snapshot_id,
        "sourceInvoiceDataVersion": snapshot.source_invoice_data_version,
        "sourceValidationExecutionId": snapshot.source_validation_execution_id,
        "sourceValidationVersion": snapshot.source_validation_version,
        "sourceInvoiceIdentityClaimId": snapshot.source_invoice_identity_claim_id,
        "sourceInvoiceIdentityKey": snapshot.source_invoice_identity_key,
        "sourcePurchaseReconciliationId": snapshot.source_purchase_reconciliation_id,
        "sourcePurchaseReconciliationNo": snapshot.source_purchase_reconciliation_no,
        "sourceReconciliationVersion": snapshot.source_reconciliation_version,
        "sourceCheckVersion": snapshot.source_check_version,
        "sourcePrepareHash": snapshot.source_prepare_hash,
        "sourceInvoiceDataHash": snapshot.source_invoice_data_hash,
        "sourceValidationResultHash": snapshot.source_validation_result_hash,
        "sourceEligibilityHash": snapshot.source_eligibility_hash,
        "capturedAt": snapshot.captured_at.isoformat(),
    }


def build_purchase_accounts_payable_draft_state_facts(obj):
    return business_state_transition_facts_from_allowed_transitions(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        allowed_transitions=(),
        audit_target_types=("purchaseAccountsPayableDraft", DOCUMENT_TYPE),
        initial_states=(PurchaseAccountsPayableDraft.Status.DRAFT,),
    )


def serialize_draft(obj):
    source_snapshot = getattr(obj, "source_snapshot", None)
    state_facts = build_purchase_accounts_payable_draft_state_facts(obj)
    return {
        "id": obj.pk,
        "draftNo": obj.draft_no,
        "status": obj.status,
        "sourceDocumentType": obj.source_document_type,
        "sourcePurchaseInvoicePrepareId": obj.source_purchase_invoice_prepare_id,
        "sourcePurchaseInvoicePrepareNo": obj.source_purchase_invoice_prepare_no,
        "sourcePrepareVersion": obj.source_prepare_version,
        "sourceInvoiceDataVersion": obj.source_invoice_data_version,
        "sourceValidationVersion": obj.source_validation_version,
        "sourcePurchaseReconciliationId": obj.source_purchase_reconciliation_id,
        "sourcePurchaseReconciliationNo": obj.source_purchase_reconciliation_no,
        "sourceReconciliationVersion": obj.source_reconciliation_version,
        "sourceCheckVersion": obj.source_check_version,
        "sourceInvoiceIdentityKey": obj.source_invoice_identity_key,
        "supplierId": obj.supplier_id,
        "supplierName": obj.supplier_name,
        "sellerTaxId": obj.seller_tax_id,
        "legalEntityId": obj.legal_entity_id,
        "legalEntityName": obj.legal_entity_name,
        "buyerTaxId": obj.buyer_tax_id,
        "ledgerBookId": obj.ledger_book_id,
        "currency": obj.currency,
        "quantity": str(obj.quantity),
        "unit": obj.unit,
        "amountExcludingTax": str(obj.amount_excluding_tax),
        "taxAmount": str(obj.tax_amount),
        "amountIncludingTax": str(obj.amount_including_tax),
        "payableAmount": str(obj.payable_amount),
        "invoiceType": obj.invoice_type,
        "invoiceCode": obj.invoice_code,
        "invoiceNumber": obj.invoice_number,
        "invoiceDate": obj.invoice_date.isoformat(),
        "idempotencyKey": obj.idempotency_key,
        "numberReservationId": obj.number_reservation_id,
        "transactionId": obj.business_transaction.transaction_id,
        "auditRecordId": obj.audit_record_id,
        "version": obj.version,
        "createdAt": obj.created_at.isoformat(),
        "sourceSnapshot": serialize_source_snapshot(source_snapshot),
        "currentStateSource": "server",
        **state_facts,
        "strictFacts": {
            "currentStateSource": "server",
            **state_facts,
        },
    }


def build_current_state(source, targets=None):
    targets = list(
        targets
        if targets is not None
        else PurchaseAccountsPayableDraft.objects.filter(
            source_purchase_invoice_prepare=source
        ).select_related(
            "number_reservation", "business_transaction", "audit_record"
        )
    )
    target_count = len(targets)
    test_tenant = (
        source.tenant_id
        in settings.PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_TEST_TENANTS
    )
    if target_count == 0:
        gate = build_business_gate(source)
        return {
            "targetExistenceStatus": "no_target",
            "targetCount": 0,
            "generationAllowed": gate["passed"] and test_tenant,
            "generationStatus": "not_started",
            "idempotencyStatus": "not_started",
            "numberReservationStatus": "not_allocated",
            "transactionStatus": "not_started",
            "sourceRelationStatus": "not_started",
            "auditStatus": "not_started",
            "currentStateSource": "server",
            "purchaseAccountsPayableDraft": None,
            "preActionTargetCount": 0,
            "postActionTargetCount": 0,
            "retryTargetCount": 0,
            "crossProcessRecoveryTargetCount": 0,
            "businessGate": {
                "passed": gate["passed"],
                "rules": gate["rules"],
                "ruleCount": gate["ruleCount"],
            },
            "transactionCapabilityGate": test_tenant,
            "testTenant": test_tenant,
            "productionRolloutEnabled": (
                settings.PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED
            ),
            "nextModule": "应付确认准备",
            "nextModuleAllowed": False,
            "nextModuleReason": "尚未执行应付确认准备规则",
            "downstreamCounts": {
                "confirmationPrepares": 0,
                "paymentApplications": 0,
                "payments": 0,
                "paymentVouchers": 0,
                "writeoffs": 0,
                "ledgerEntries": 0,
                "postings": 0,
                "bankTransactions": 0,
                "localStorageBusinessWrites": 0,
                "productionNetworkWrites": 0,
            },
        }
    if target_count > 1:
        return {
            "targetExistenceStatus": "conflict",
            "targetCount": target_count,
            "generationAllowed": False,
            "generationStatus": "conflict",
            "currentStateSource": "server",
            "purchaseAccountsPayableDraft": None,
            "nextModuleAllowed": False,
            "nextModuleReason": "目标证据冲突",
        }
    obj = targets[0]
    idem = BusinessActionIdempotency.objects.filter(
        action_code=ACTION_CODE, target_id=obj.pk
    ).order_by("-updated_at", "-id").first()
    relation = obj.source_relations.filter(
        source_type=SOURCE_DOCUMENT_TYPE,
        source_id=source.pk,
        relationship_type="generated_from",
    ).first()
    return {
        "targetExistenceStatus": "single_target",
        "targetCount": 1,
        "generationAllowed": False,
        "generationStatus": "existing_target",
        "idempotencyStatus": idem.status if idem else "inconsistent",
        "numberReservationStatus": obj.number_reservation.status,
        "transactionStatus": obj.business_transaction.commit_status,
        "sourceRelationStatus": relation.relationship_type if relation else "inconsistent",
        "auditStatus": obj.audit_record.result if obj.audit_record else "inconsistent",
        "currentStateSource": "server",
        "purchaseAccountsPayableDraft": serialize_draft(obj),
        "preActionTargetCount": 0,
        "postActionTargetCount": 1,
        "retryTargetCount": 1,
        "crossProcessRecoveryTargetCount": 1,
        "transactionCapabilityGate": test_tenant,
        "testTenant": test_tenant,
        "productionRolloutEnabled": (
            settings.PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED
        ),
        "nextModule": "应付确认准备",
        "nextModuleAllowed": False,
        "nextModuleReason": "尚未执行应付确认准备规则",
        "rollbackAndRecovery": {
            "failureStepCount": len(FAILURE_STEPS),
            "targetResidualCount": 0,
            "sourceSnapshotResidualCount": 0,
            "sourceRelationResidualCount": 0,
            "auditResidualCount": 0,
            "recoveryClassification": "existing_result",
            "retryAllowed": True,
            "manualInterventionRequired": False,
        },
        "downstreamCounts": {
            "confirmationPrepares": 0,
            "paymentApplications": 0,
            "payments": 0,
            "paymentVouchers": 0,
            "writeoffs": 0,
            "ledgerEntries": 0,
            "postings": 0,
            "bankTransactions": 0,
            "localStorageBusinessWrites": 0,
            "productionNetworkWrites": 0,
        },
    }


def _existing_result(obj, classification):
    return {
        "classification": classification,
        "created": False,
        "data": serialize_draft(obj),
        "currentState": build_current_state(
            obj.source_purchase_invoice_prepare, [obj]
        ),
    }


def _generate_once(
    *,
    user,
    source,
    idempotency_key,
    expected_prepare_version,
    expected_invoice_data_version,
    expected_validation_version,
    expected_reconciliation_version,
    expected_check_version,
    failure_step,
):
    source_key = f"purchaseInvoicePrepare:{source.pk}"
    transaction_id = f"APDTX-{uuid.uuid4().hex}"
    aborted_number = None
    try:
        with transaction.atomic():
            lock, created = BusinessActionSourceLock.objects.get_or_create(
                lock_key=f"purchase_accounts_payable_draft_generation:{source.pk}",
                defaults={
                    "owner_transaction_id": transaction_id,
                    "state": "acquired",
                },
            )
            if (
                not created
                and lock.state == "acquired"
                and lock.owner_transaction_id != transaction_id
            ):
                raise ReconciliationError(
                    "APD_IN_PROGRESS", "Source generation is in progress", 409, True
                )
            lock.owner_transaction_id = transaction_id
            lock.state = "acquired"
            lock.released_at = None
            lock.save(
                update_fields=[
                    "owner_transaction_id", "state", "released_at", "acquired_at"
                ]
            )
            _inject("after_persistent_lock", failure_step)
            source = PurchaseInvoicePrepare.objects.select_related(
                "source_purchase_reconciliation"
            ).get(pk=source.pk)
            _inject("after_locked_prepare_reload", failure_step)
            snapshot = current_snapshot(source)
            _inject("after_invoice_snapshot_reload", failure_step)
            execution = current_execution(source)
            _inject("after_validation_execution_reload", failure_step)
            claim = source.invoice_identity_claims.filter(status="active").first()
            _inject("after_identity_claim_reload", failure_step)
            reconciliation = source.source_purchase_reconciliation
            _inject("after_reconciliation_reload", failure_step)
            gate = build_business_gate(
                source,
                expected_prepare_version=expected_prepare_version,
                expected_invoice_data_version=expected_invoice_data_version,
                expected_validation_version=expected_validation_version,
                expected_reconciliation_version=expected_reconciliation_version,
                expected_check_version=expected_check_version,
            )
            _inject("after_eligibility_recalculation", failure_step)
            version_codes = (
                "APD_GATE_PREPARE_VERSION_MATCH",
                "APD_GATE_DATA_VERSION_MATCH",
                "APD_GATE_VALIDATION_VERSION_MATCH",
                "APD_GATE_RECONCILIATION_VERSION_MATCH",
                "APD_GATE_CHECK_VERSION_MATCH",
            )
            if not all(gate["checks"][code] for code in version_codes):
                _raise_gate(gate)
            _inject("after_version_check", failure_step)
            existing = PurchaseAccountsPayableDraft.objects.filter(
                source_purchase_invoice_prepare=source
            ).first()
            if existing:
                lock.state = "released"
                lock.released_at = timezone.now()
                lock.save(update_fields=["state", "released_at"])
                return _existing_result(existing, "existing_target")
            if not gate["passed"]:
                _raise_gate(gate)
            _inject("after_existing_target_check", failure_step)
            request_hash = canonical_hash({
                "sourcePurchaseInvoicePrepareId": source.pk,
                "expectedPrepareVersion": expected_prepare_version,
                "expectedInvoiceDataVersion": expected_invoice_data_version,
                "expectedValidationVersion": expected_validation_version,
                "expectedReconciliationVersion": expected_reconciliation_version,
                "expectedCheckVersion": expected_check_version,
            })
            idem, idem_created = BusinessActionIdempotency.objects.get_or_create(
                action_code=ACTION_CODE,
                idempotency_key=idempotency_key,
                defaults={
                    "tenant_id": source.tenant_id,
                    "source_key": source_key,
                    "request_hash": request_hash,
                    "status": BusinessActionIdempotency.Status.IN_PROGRESS,
                    "transaction_id": transaction_id,
                },
            )
            if not idem_created:
                if idem.request_hash != request_hash:
                    raise ReconciliationError(
                        "APD_TARGET_CONFLICT", "Idempotency payload conflict", 409
                    )
                if idem.target_id:
                    return _existing_result(
                        PurchaseAccountsPayableDraft.objects.get(pk=idem.target_id),
                        "existing_result",
                    )
                raise ReconciliationError(
                    "APD_IN_PROGRESS", "Idempotent action is in progress", 409, True
                )
            _inject("after_idempotency_registration", failure_step)
            reservation, sequence_value = _reserve_number(source, idempotency_key)
            aborted_number = {
                "reserved_number": reservation.reserved_number,
                "number_scope": reservation.number_scope,
                "sequence_value": sequence_value,
                "legal_entity_id": source.legal_entity_id,
                "ledger_book_id": source.ledger_book_id,
                "tenant_id": source.tenant_id,
                "accounting_period": reconciliation.accounting_period,
                "idempotency_key": idempotency_key,
                "target_id": reconciliation.pk,
            }
            _inject("after_number_reservation", failure_step)
            tx = BusinessActionTransaction.objects.create(
                transaction_id=transaction_id,
                action_code=ACTION_CODE,
                idempotency_key=idempotency_key,
                tenant_id=source.tenant_id,
                source_key=source_key,
                command_id=f"APD-CMD-{uuid.uuid4().hex}",
                transaction_plan_id=TRANSACTION_PLAN_ID,
                review_id=f"PIP-VALIDATION-{execution.pk}",
                review_hash=execution.result_hash,
                status=BusinessActionTransaction.Status.IN_PROGRESS,
                outcome="pending",
                commit_status="in_progress",
                recovery_status="not_required",
                reconciliation=reconciliation,
            )
            eligibility_hash = canonical_hash(gate["eligibility"])
            obj = create_business_object_with_initial_state(
                model=PurchaseAccountsPayableDraft,
                initial_state=PurchaseAccountsPayableDraft.Status.DRAFT,
                draft_no=reservation.reserved_number,
                source_purchase_invoice_prepare=source,
                source_purchase_invoice_prepare_no=source.prepare_no,
                source_prepare_version=source.version,
                source_invoice_data_version=source.current_data_version,
                source_validation_version=source.current_validation_version,
                source_purchase_reconciliation=reconciliation,
                source_purchase_reconciliation_no=reconciliation.reconciliation_no,
                source_reconciliation_version=reconciliation.version,
                source_check_version=gate["reconciliationEligibility"]["checkVersion"],
                source_invoice_identity_key=claim.invoice_identity_key,
                source_eligibility_hash=eligibility_hash,
                source_key=source_key,
                tenant_id=source.tenant_id,
                company_id=source.company_id,
                supplier_id=source.supplier_id,
                supplier_name=source.supplier_name,
                seller_tax_id=snapshot.seller_tax_id,
                legal_entity_id=source.legal_entity_id,
                legal_entity_name=snapshot.buyer_name,
                buyer_tax_id=snapshot.buyer_tax_id,
                ledger_book_id=source.ledger_book_id,
                currency=snapshot.currency,
                quantity=source.quantity,
                unit=source.unit,
                amount_excluding_tax=snapshot.amount_excluding_tax,
                tax_amount=snapshot.tax_amount,
                amount_including_tax=snapshot.amount_including_tax,
                payable_amount=snapshot.amount_including_tax,
                invoice_type=snapshot.invoice_type,
                invoice_code=snapshot.invoice_code,
                invoice_number=snapshot.invoice_number,
                invoice_date=snapshot.invoice_date,
                idempotency_key=idempotency_key,
                number_reservation=reservation,
                business_transaction=tx,
                created_by=user,
            )
            _inject("after_target_insert", failure_step)
            source_snapshot = PurchaseAccountsPayableDraftSourceSnapshot.objects.create(
                purchase_accounts_payable_draft=obj,
                source_purchase_invoice_prepare_id=source.pk,
                source_purchase_invoice_prepare_no=source.prepare_no,
                source_prepare_version=source.version,
                source_invoice_data_snapshot_id=snapshot.pk,
                source_invoice_data_version=snapshot.data_version,
                source_validation_execution_id=execution.pk,
                source_validation_version=source.current_validation_version,
                source_invoice_identity_claim_id=claim.pk,
                source_invoice_identity_key=claim.invoice_identity_key,
                source_purchase_reconciliation_id=reconciliation.pk,
                source_purchase_reconciliation_no=reconciliation.reconciliation_no,
                source_reconciliation_version=reconciliation.version,
                source_check_version=gate["reconciliationEligibility"]["checkVersion"],
                source_prepare_hash=canonical_hash({
                    "id": source.pk, "no": source.prepare_no, "version": source.version,
                    "status": source.status, "dataVersion": source.current_data_version,
                    "validationVersion": source.current_validation_version,
                }),
                source_invoice_data_hash=snapshot.data_hash,
                source_validation_result_hash=execution.result_hash,
                source_eligibility_hash=eligibility_hash,
            )
            _inject("after_source_snapshot_insert", failure_step)
            relation = PurchaseAccountsPayableDraftSourceRelation.objects.create(
                purchase_accounts_payable_draft=obj,
                source_id=source.pk,
                source_no=source.prepare_no,
                source_version=source.version,
                source_hash=source_snapshot.source_prepare_hash,
            )
            _inject("after_relation_insert", failure_step)
            audit = BusinessActionAuditRecord.objects.create(
                transaction=tx,
                action_code=ACTION_CODE,
                tenant_id=source.tenant_id,
                actor=user,
                source_key=source_key,
                reconciliation=reconciliation,
                result="committed",
                target_type="purchaseAccountsPayableDraft",
                target_id=obj.pk,
                target_no=obj.draft_no,
                review_id=tx.review_id,
                review_hash=tx.review_hash,
                command_id=tx.command_id,
                idempotency_key=idempotency_key,
                actor_name=user.username,
                tenant_or_scope=f"{source.tenant_id}:{source.company_id}",
                evidence_hash=canonical_hash(gate["rules"]),
                evidence={
                    "preActionBusinessGate": gate["rules"],
                    "sourceSnapshotId": source_snapshot.pk,
                    "sourceRelationId": relation.pk,
                    "productionRolloutEnabled": False,
                    "downstreamWrites": 0,
                },
            )
            obj.audit_record = audit
            obj.save(update_fields=["audit_record", "updated_at"])
            _inject("after_audit_insert", failure_step)
            tx.status = BusinessActionTransaction.Status.COMMITTED
            tx.outcome = "created"
            tx.commit_status = "committed"
            tx.result_hash = canonical_hash({
                "targetId": obj.pk,
                "targetNo": obj.draft_no,
                "snapshotId": source_snapshot.pk,
                "relationId": relation.pk,
                "auditId": audit.pk,
            })
            tx.save(update_fields=[
                "status", "outcome", "commit_status", "result_hash", "updated_at"
            ])
            idem.status = BusinessActionIdempotency.Status.COMMITTED
            idem.target_type = "purchaseAccountsPayableDraft"
            idem.target_id = obj.pk
            idem.target_no = obj.draft_no
            idem.result_reference = f"purchaseAccountsPayableDraft:{obj.pk}"
            idem.save(update_fields=[
                "status", "target_type", "target_id", "target_no",
                "result_reference", "updated_at",
            ])
            _inject("after_idempotency_committed", failure_step)
            reservation.status = BusinessDocumentNumberReservation.Status.CONSUMED
            reservation.consumed_at = timezone.now()
            reservation.save(update_fields=["status", "consumed_at", "reusable"])
            _inject("after_number_consumed", failure_step)
            lock.state = "released"
            lock.released_at = timezone.now()
            lock.save(update_fields=["state", "released_at"])
            _inject("before_database_commit", failure_step)
        result = {
            "classification": "created",
            "created": True,
            "data": serialize_draft(obj),
            "currentState": build_current_state(source, [obj]),
        }
        _inject("before_response", failure_step)
        return result
    except (IntegrityError, ReconciliationError) as exc:
        _persist_aborted_number(aborted_number, getattr(exc, "code", str(exc)))
        if isinstance(exc, ReconciliationError):
            raise
        existing = PurchaseAccountsPayableDraft.objects.filter(
            source_purchase_invoice_prepare=source
        ).first()
        if existing:
            return _existing_result(existing, "existing_target")
        raise ReconciliationError("APD_TRANSACTION_FAILED", str(exc), 409, True) from exc


def generate_purchase_accounts_payable_draft(
    *,
    user,
    source_prepare_id,
    idempotency_key,
    expected_prepare_version,
    expected_invoice_data_version,
    expected_validation_version,
    expected_reconciliation_version,
    expected_check_version,
    explicit_user_action,
    failure_step="",
):
    if not explicit_user_action:
        raise ReconciliationError(
            "APD_EXPLICIT_USER_ACTION_REQUIRED", "Explicit user action is required", 400
        )
    if not idempotency_key or len(idempotency_key) > 120:
        raise ReconciliationError(
            "APD_IDEMPOTENCY_KEY_INVALID", "Valid idempotency key is required", 400
        )
    try:
        source = PurchaseInvoicePrepare.objects.select_related(
            "source_purchase_reconciliation"
        ).get(pk=source_prepare_id)
    except PurchaseInvoicePrepare.DoesNotExist as exc:
        raise ReconciliationError(
            "APD_SOURCE_NOT_FOUND", "Purchase invoice prepare not found", 404
        ) from exc
    _authorize(user, source)
    _inject("after_authorization", failure_step)
    prior = BusinessActionIdempotency.objects.filter(
        action_code=ACTION_CODE, idempotency_key=idempotency_key
    ).first()
    if prior and prior.target_id:
        return _existing_result(
            PurchaseAccountsPayableDraft.objects.get(pk=prior.target_id),
            "existing_result",
        )
    gate = build_business_gate(
        source,
        expected_prepare_version=expected_prepare_version,
        expected_invoice_data_version=expected_invoice_data_version,
        expected_validation_version=expected_validation_version,
        expected_reconciliation_version=expected_reconciliation_version,
        expected_check_version=expected_check_version,
    )
    if not gate["passed"] and not (
        gate["existingTargetCount"] == 1
        and all(
            value
            for key, value in gate["checks"].items()
            if key
            not in {
                "APD_GATE_NO_EXISTING_TARGET",
                "APD_GATE_AP_DRAFT_READY",
            }
        )
    ):
        _raise_gate(gate)
    _inject("after_business_gate", failure_step)
    retries = max(
        0, settings.PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_SQLITE_RETRY_COUNT
    )
    for attempt in range(retries + 1):
        try:
            return _generate_once(
                user=user,
                source=source,
                idempotency_key=idempotency_key,
                expected_prepare_version=expected_prepare_version,
                expected_invoice_data_version=expected_invoice_data_version,
                expected_validation_version=expected_validation_version,
                expected_reconciliation_version=expected_reconciliation_version,
                expected_check_version=expected_check_version,
                failure_step=failure_step,
            )
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= retries:
                raise ReconciliationError(
                    "APD_TRANSACTION_FAILED",
                    "SQLite lock retry threshold exceeded",
                    503,
                    True,
                ) from exc
            logger.warning(
                "APD SQLite lock retry %s/%s for source %s",
                attempt + 1,
                retries,
                source.pk,
            )
            time.sleep(
                settings.PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_SQLITE_RETRY_INTERVAL_MS
                / 1000
            )
    raise ReconciliationError("APD_TRANSACTION_FAILED", "Generation failed", 503, True)


def recover_generation_result(idempotency_key, user):
    idem = BusinessActionIdempotency.objects.filter(
        action_code=ACTION_CODE, idempotency_key=idempotency_key
    ).first()
    if not idem:
        raise ReconciliationError(
            "APD_RESULT_INTEGRITY_FAILED", "Generation result not found", 404
        )
    if not idem.target_id:
        classification = (
            "recovery_required"
            if idem.status == BusinessActionIdempotency.Status.COMMIT_UNKNOWN
            else "in_progress"
        )
        return {
            "classification": classification,
            "created": False,
            "idempotencyStatus": idem.status,
        }
    obj = PurchaseAccountsPayableDraft.objects.select_related(
        "source_purchase_invoice_prepare",
        "number_reservation",
        "business_transaction",
        "audit_record",
    ).filter(pk=idem.target_id).first()
    if not obj:
        raise ReconciliationError(
            "APD_RESULT_INTEGRITY_FAILED", "Committed target is missing", 409
        )
    if not user.is_superuser and user.company_id != obj.company_id:
        raise ReconciliationError("APD_AUTH_SCOPE_DENIED", "Result outside actor scope", 403)
    return _existing_result(obj, "existing_result")
