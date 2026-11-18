import time
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft
from purchase_accounts_payable_draft.services import (
    build_purchase_accounts_payable_draft_state_facts,
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
from workflow_runtime.facts import (
    business_state_transition_facts_from_allowed_transitions,
)
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
)

from .models import (
    PayableConfirmationAccountingSnapshot,
    PayableConfirmationCanaryScenario,
    PayableConfirmationPrepare,
    PayableConfirmationPrepareSourceRelation,
    PayableConfirmationValidationExecution,
    PayableConfirmationValidationIssue,
)

ACTION_CODE = "generate_payable_confirmation_prepare"
DOCUMENT_TYPE = "payable_confirmation_prepare"
SOURCE_DOCUMENT_TYPE = "purchaseAccountsPayableDraft"
NUMBER_POLICY_VERSION = "payable-confirmation-prepare-sequence-v1"
TRANSACTION_PLAN_ID = "payable-confirmation-prepare-atomic-v1"
RULE_SET_VERSION = "payable-confirmation-accounting-rules-v1"
FAILURE_STEPS = (
    "after_authorization",
    "after_idempotency_registration",
    "after_persistent_lock",
    "after_locked_source_reload",
    "after_source_version_check",
    "after_accounting_validation",
    "after_number_reservation",
    "after_target_insert",
    "after_accounting_snapshot_insert",
    "after_validation_execution_insert",
    "after_source_relation_insert",
    "after_audit_insert",
    "after_idempotency_committed",
    "after_number_consumed",
    "before_database_commit",
    "before_response",
)


def _decimal(value, field_name):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReconciliationError(
            "PCP_ACCOUNTING_VALUE_INVALID",
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
            "PCP_ACCOUNTING_DATE_INVALID",
            f"{field_name} must use YYYY-MM-DD",
            400,
        ) from exc


def _authorize(user, source):
    if not user or not user.is_authenticated:
        raise ReconciliationError("PCP_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not (
        user.is_superuser
        or user.has_perm(
            "payable_confirmation_prepare.generate_payable_confirmation_prepare"
        )
    ):
        raise ReconciliationError(
            "PCP_AUTH_PERMISSION_DENIED", "Generation permission required", 403
        )
    if not user.is_superuser and user.company_id != source.company_id:
        raise ReconciliationError(
            "PCP_AUTH_SCOPE_DENIED", "Source is outside actor scope", 403
        )
    if not settings.PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED:
        raise ReconciliationError(
            "PCP_AUTH_FEATURE_DISABLED", "Server feature flag is disabled", 403
        )
    if (
        source.tenant_id
        not in settings.PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS
        and not settings.PCE_PAYABLE_CONFIRMATION_PREPARE_PRODUCTION_ROLLOUT_ENABLED
    ):
        raise ReconciliationError(
            "PCP_AUTH_PRODUCTION_ROLLOUT_DISABLED",
            "Production rollout is disabled",
            403,
        )


def _inject(step, requested):
    if step != requested:
        return
    if not settings.PCE_PAYABLE_CONFIRMATION_PREPARE_FAILURE_INJECTION_ENABLED:
        raise ReconciliationError(
            "PCP_FAILURE_INJECTION_DISABLED",
            "Failure injection is disabled",
            403,
        )
    if step == "before_response":
        raise ReconciliationError(
            "PCP_COMMIT_UNKNOWN",
            "Response was lost after commit; recover by idempotency key",
            503,
            True,
        )
    raise ReconciliationError(
        f"PCP_INJECTED_{step.upper()}",
        f"Injected failure at {step}",
        503,
        True,
    )


def normalize_accounting_data(source, accounting_data):
    payload = dict(accounting_data or {})
    accounting_date = _date(payload.get("accountingDate"), "accountingDate")
    payment_terms_days = int(payload.get("paymentTermsDays", -1))
    due_date = _date(payload.get("dueDate"), "dueDate")
    debit_total = _decimal(payload.get("debitTotal"), "debitTotal")
    credit_total = _decimal(payload.get("creditTotal"), "creditTotal")
    return {
        "accountsPayableAccount": str(payload.get("accountsPayableAccount") or "").strip(),
        "inputTaxAccount": str(payload.get("inputTaxAccount") or "").strip(),
        "counterpartyAccount": str(payload.get("counterpartyAccount") or "").strip(),
        "supplierAuxiliaryId": str(payload.get("supplierAuxiliaryId") or "").strip(),
        "departmentId": str(payload.get("departmentId") or "").strip(),
        "costCenterId": str(payload.get("costCenterId") or "").strip(),
        "projectId": str(payload.get("projectId") or "").strip(),
        "paymentTermsCode": str(payload.get("paymentTermsCode") or "").strip(),
        "paymentTermsDays": payment_terms_days,
        "dueDate": due_date,
        "accountingDate": accounting_date,
        "accountingPeriod": str(payload.get("accountingPeriod") or "").strip(),
        "periodStatus": str(payload.get("periodStatus") or "").strip(),
        "debitTotal": debit_total,
        "creditTotal": credit_total,
        "sourceDraftVersion": int(payload.get("sourceDraftVersion", source.version)),
    }


def _issue(code, field, message, actual, expected):
    return {
        "ruleCode": code,
        "fieldName": field,
        "severity": "error",
        "message": message,
        "actualValue": str(actual),
        "expectedValue": str(expected),
    }


def validate_accounting_data(source, accounting_data):
    data = normalize_accounting_data(source, accounting_data)
    issues = []
    source_state_facts = build_purchase_accounts_payable_draft_state_facts(source)
    if not source_state_facts["stateMachineConsistent"]:
        issues.append(_issue(
            "PCP_SOURCE_STATE_MACHINE_INCONSISTENT",
            "sourceStateFacts",
            "来源采购应付账款草稿状态事实不一致",
            source_state_facts["statusTransitionCount"],
            "consistent",
        ))
    required_accounts = (
        ("accountsPayableAccount", "PCP_AP_ACCOUNT_REQUIRED", "应付科目"),
        ("inputTaxAccount", "PCP_INPUT_TAX_ACCOUNT_REQUIRED", "税额科目"),
        ("counterpartyAccount", "PCP_COUNTERPARTY_ACCOUNT_REQUIRED", "对方科目"),
    )
    for field, code, label in required_accounts:
        if not data[field]:
            issues.append(_issue(code, field, f"{label}不能为空", "", "non_empty"))
    if data["accountsPayableAccount"] and not data["accountsPayableAccount"].startswith("2202"):
        issues.append(_issue(
            "PCP_AP_ACCOUNT_INVALID",
            "accountsPayableAccount",
            "应付科目必须属于2202应付账款",
            data["accountsPayableAccount"],
            "2202*",
        ))
    if data["inputTaxAccount"] and not data["inputTaxAccount"].startswith("222101"):
        issues.append(_issue(
            "PCP_INPUT_TAX_ACCOUNT_INVALID",
            "inputTaxAccount",
            "税额科目必须属于进项税额科目",
            data["inputTaxAccount"],
            "222101*",
        ))
    if not data["supplierAuxiliaryId"]:
        issues.append(_issue(
            "PCP_SUPPLIER_AUXILIARY_REQUIRED",
            "supplierAuxiliaryId",
            "供应商辅助核算不能为空",
            "",
            source.supplier_id,
        ))
    elif data["supplierAuxiliaryId"] != source.supplier_id:
        issues.append(_issue(
            "PCP_SUPPLIER_AUXILIARY_MISMATCH",
            "supplierAuxiliaryId",
            "供应商辅助核算必须与来源草稿一致",
            data["supplierAuxiliaryId"],
            source.supplier_id,
        ))
    for field, code, label in (
        ("departmentId", "PCP_DEPARTMENT_REQUIRED", "部门"),
        ("costCenterId", "PCP_COST_CENTER_REQUIRED", "成本中心"),
        ("projectId", "PCP_PROJECT_REQUIRED", "项目"),
    ):
        if not data[field]:
            issues.append(_issue(code, field, f"{label}维度不能为空", "", "non_empty"))
    if not data["paymentTermsCode"]:
        issues.append(_issue(
            "PCP_PAYMENT_TERMS_REQUIRED",
            "paymentTermsCode",
            "付款条件不能为空",
            "",
            "non_empty",
        ))
    if data["paymentTermsDays"] < 0:
        issues.append(_issue(
            "PCP_PAYMENT_TERMS_DAYS_INVALID",
            "paymentTermsDays",
            "付款账期天数不能小于零",
            data["paymentTermsDays"],
            ">=0",
        ))
    expected_due_date = source.invoice_date + timedelta(days=max(data["paymentTermsDays"], 0))
    if data["dueDate"] != expected_due_date:
        issues.append(_issue(
            "PCP_DUE_DATE_MISMATCH",
            "dueDate",
            "到期日必须由发票日期和付款条件派生",
            data["dueDate"],
            expected_due_date,
        ))
    expected_period = source.source_purchase_reconciliation.accounting_period
    if data["accountingPeriod"] != expected_period:
        issues.append(_issue(
            "PCP_ACCOUNTING_PERIOD_MISMATCH",
            "accountingPeriod",
            "会计期间必须与来源采购对账一致",
            data["accountingPeriod"],
            expected_period,
        ))
    if data["accountingDate"].strftime("%Y-%m") != expected_period:
        issues.append(_issue(
            "PCP_ACCOUNTING_DATE_PERIOD_MISMATCH",
            "accountingDate",
            "会计日期必须位于来源会计期间",
            data["accountingDate"],
            expected_period,
        ))
    if data["periodStatus"] != "open":
        issues.append(_issue(
            "PCP_ACCOUNTING_PERIOD_CLOSED",
            "periodStatus",
            "会计期间必须开放",
            data["periodStatus"],
            "open",
        ))
    if data["sourceDraftVersion"] != source.version:
        issues.append(_issue(
            "PCP_SOURCE_VERSION_CONFLICT",
            "sourceDraftVersion",
            "来源采购应付账款草稿版本已变化",
            data["sourceDraftVersion"],
            source.version,
        ))
    expected_debit = (source.amount_excluding_tax + source.tax_amount).quantize(
        Decimal("0.01")
    )
    expected_credit = source.payable_amount.quantize(Decimal("0.01"))
    if data["debitTotal"] != expected_debit:
        issues.append(_issue(
            "PCP_DEBIT_TOTAL_MISMATCH",
            "debitTotal",
            "借方合计必须等于不含税金额与税额之和",
            data["debitTotal"],
            expected_debit,
        ))
    if data["creditTotal"] != expected_credit:
        issues.append(_issue(
            "PCP_CREDIT_TOTAL_MISMATCH",
            "creditTotal",
            "贷方合计必须等于应付金额",
            data["creditTotal"],
            expected_credit,
        ))
    if data["debitTotal"] != data["creditTotal"]:
        issues.append(_issue(
            "PCP_DEBIT_CREDIT_UNBALANCED",
            "debitTotal,creditTotal",
            "借贷必须平衡",
            f"{data['debitTotal']}/{data['creditTotal']}",
            "equal",
        ))
    normalized_for_hash = {
        key: value.isoformat() if isinstance(value, date) else str(value)
        for key, value in data.items()
    }
    input_hash = canonical_hash(normalized_for_hash)
    result = {
        "passed": not issues,
        "status": "passed" if not issues else "failed",
        "resultCode": "PCP_VALIDATED" if not issues else "PCP_VALIDATION_FAILED",
        "issueCount": len(issues),
        "issues": issues,
        "ruleSetVersion": RULE_SET_VERSION,
        "inputHash": input_hash,
    }
    result["resultHash"] = canonical_hash({
        "status": result["status"],
        "resultCode": result["resultCode"],
        "issues": issues,
        "inputHash": input_hash,
    })
    return data, result


def build_payment_request_prepare_eligibility(obj):
    reasons = []
    state_facts = business_state_transition_facts_from_allowed_transitions(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        allowed_transitions=(),
        audit_target_types=(DOCUMENT_TYPE,),
        initial_states=(PayableConfirmationPrepare.Status.PREPARED,),
    )
    if not state_facts["stateMachineConsistent"]:
        reasons.append("PCP_STATE_MACHINE_FACTS_INCONSISTENT")
    if obj.status != PayableConfirmationPrepare.Status.PREPARED:
        reasons.append("PCP_NOT_PREPARED")
    if obj.validation_status != "passed":
        reasons.append("PCP_VALIDATION_NOT_PASSED")
    if obj.validation_issue_count != 0:
        reasons.append("PCP_VALIDATION_HAS_ISSUES")
    if obj.debit_total != obj.credit_total:
        reasons.append("PCP_DEBIT_CREDIT_UNBALANCED")
    eligible = not reasons
    return {
        "eligible": eligible,
        "nextStepReadiness": (
            "ready_for_payment_request_prepare" if eligible else "blocked"
        ),
        "status": obj.status,
        "validationStatus": obj.validation_status,
        "validationIssueCount": obj.validation_issue_count,
        "debitCreditBalanced": obj.debit_total == obj.credit_total,
        "blockingReasonCodes": reasons,
        "source": "server",
        "serverRevalidationRequired": True,
        "paymentRequestPrepareCreated": False,
        "currentStateSource": "server",
        **state_facts,
    }


def _source_hash(source):
    return canonical_hash({
        "id": source.pk,
        "draftNo": source.draft_no,
        "version": source.version,
        "tenantId": source.tenant_id,
        "supplierId": source.supplier_id,
        "payableAmount": str(source.payable_amount),
        "sourceInvoiceIdentityKey": source.source_invoice_identity_key,
    })


def _reserve_number(source, idempotency_key):
    reconciliation = source.source_purchase_reconciliation
    scope = ":".join((
        DOCUMENT_TYPE,
        source.legal_entity_id,
        source.ledger_book_id,
        reconciliation.accounting_period,
    ))
    sequence, _ = BusinessDocumentNumberSequence.objects.get_or_create(
        number_scope=scope
    )
    sequence.current_value += 1
    number = (
        f"PCP{reconciliation.accounting_period.replace('-', '')}"
        f"{sequence.current_value:08d}"
    )
    while BusinessDocumentNumberReservation.objects.filter(
        reserved_number=number
    ).exists():
        sequence.current_value += 1
        number = (
            f"PCP{reconciliation.accounting_period.replace('-', '')}"
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
    return reservation


def serialize_prepare(obj):
    snapshot = getattr(obj, "accounting_snapshot", None)
    eligibility = build_payment_request_prepare_eligibility(obj)
    state_facts = business_state_transition_facts_from_allowed_transitions(
        business_object=obj,
        object_type=DOCUMENT_TYPE,
        allowed_transitions=(),
        audit_target_types=(DOCUMENT_TYPE,),
        initial_states=(PayableConfirmationPrepare.Status.PREPARED,),
    )
    return {
        "id": obj.pk,
        "prepareNo": obj.prepare_no,
        "status": obj.status,
        "sourceDocumentType": obj.source_document_type,
        "sourcePurchaseAccountsPayableDraftId": (
            obj.source_purchase_accounts_payable_draft_id
        ),
        "sourceDraftNo": obj.source_draft_no,
        "sourceDraftVersion": obj.source_draft_version,
        "sourceKey": obj.source_key,
        "tenantId": obj.tenant_id,
        "supplierId": obj.supplier_id,
        "supplierName": obj.supplier_name,
        "legalEntityId": obj.legal_entity_id,
        "legalEntityName": obj.legal_entity_name,
        "ledgerBookId": obj.ledger_book_id,
        "currency": obj.currency,
        "amountExcludingTax": str(obj.amount_excluding_tax),
        "taxAmount": str(obj.tax_amount),
        "payableAmount": str(obj.payable_amount),
        "accountingDataVersion": obj.accounting_data_version,
        "validationVersion": obj.validation_version,
        "validationStatus": obj.validation_status,
        "validationResultCode": obj.validation_result_code,
        "validationIssueCount": obj.validation_issue_count,
        "paymentTermsCode": obj.payment_terms_code,
        "paymentTermsDays": obj.payment_terms_days,
        "dueDate": obj.due_date.isoformat(),
        "accountingDate": obj.accounting_date.isoformat(),
        "accountingPeriod": obj.accounting_period,
        "debitTotal": str(obj.debit_total),
        "creditTotal": str(obj.credit_total),
        "idempotencyKey": obj.idempotency_key,
        "numberReservationStatus": obj.number_reservation.status,
        "transactionId": obj.business_transaction.transaction_id,
        "transactionStatus": obj.business_transaction.commit_status,
        "auditRecordId": obj.audit_record_id,
        "auditStatus": obj.audit_record.result if obj.audit_record else "missing",
        "version": obj.version,
        "createdAt": obj.created_at.isoformat(),
        "accountingSnapshot": {
            "id": snapshot.pk,
            "version": snapshot.version,
            "accountsPayableAccount": snapshot.accounts_payable_account,
            "inputTaxAccount": snapshot.input_tax_account,
            "counterpartyAccount": snapshot.counterparty_account,
            "supplierAuxiliaryId": snapshot.supplier_auxiliary_id,
            "departmentId": snapshot.department_id,
            "costCenterId": snapshot.cost_center_id,
            "projectId": snapshot.project_id,
            "periodStatus": snapshot.period_status,
            "snapshotHash": snapshot.snapshot_hash,
        } if snapshot else None,
        "eligibility": eligibility,
        "currentStateSource": "server",
        **state_facts,
        "strictFacts": {
            "currentStateSource": "server",
            **state_facts,
        },
    }


def build_current_state(source):
    targets = list(
        PayableConfirmationPrepare.objects.filter(
            source_purchase_accounts_payable_draft=source
        ).select_related(
            "number_reservation", "business_transaction", "audit_record",
            "accounting_snapshot",
        )
    )
    if not targets:
        return {
            "targetExistenceStatus": "no_target",
            "targetCount": 0,
            "generationAllowed": (
                source.tenant_id
                in settings.PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS
            ),
            "generationStatus": "not_started",
            "idempotencyStatus": "not_started",
            "numberReservationStatus": "not_allocated",
            "transactionStatus": "not_started",
            "currentStateSource": "server",
            "payableConfirmationPrepare": None,
            "eligibility": {
                "eligible": False,
                "nextStepReadiness": "not_prepared",
                "source": "server",
                "paymentRequestPrepareCreated": False,
            },
        }
    if len(targets) > 1:
        return {
            "targetExistenceStatus": "conflict",
            "targetCount": len(targets),
            "generationAllowed": False,
            "generationStatus": "conflict",
            "currentStateSource": "server",
        }
    obj = targets[0]
    idem = BusinessActionIdempotency.objects.filter(
        action_code=ACTION_CODE, target_id=obj.pk
    ).order_by("-updated_at").first()
    return {
        "targetExistenceStatus": "single_target",
        "targetCount": 1,
        "generationAllowed": False,
        "generationStatus": "existing_target",
        "idempotencyStatus": idem.status if idem else "inconsistent",
        "numberReservationStatus": obj.number_reservation.status,
        "transactionStatus": obj.business_transaction.commit_status,
        "auditStatus": obj.audit_record.result if obj.audit_record else "inconsistent",
        "currentStateSource": "server",
        "payableConfirmationPrepare": serialize_prepare(obj),
        "eligibility": build_payment_request_prepare_eligibility(obj),
    }


def _existing_result(obj):
    return {
        "classification": "existing_result",
        "created": False,
        "data": serialize_prepare(obj),
        "currentState": build_current_state(
            obj.source_purchase_accounts_payable_draft
        ),
    }


def _generate_once(
    *,
    user,
    source,
    accounting_data,
    idempotency_key,
    expected_source_version,
    failure_step="",
):
    _authorize(user, source)
    _inject("after_authorization", failure_step)
    data, validation = validate_accounting_data(source, accounting_data)
    if not validation["passed"]:
        raise ReconciliationError(
            "PCP_VALIDATION_FAILED",
            ",".join(issue["ruleCode"] for issue in validation["issues"]),
            409,
        )
    source_key = f"purchaseAccountsPayableDraft:{source.pk}"
    request_hash = canonical_hash({
        "sourceKey": source_key,
        "expectedSourceVersion": expected_source_version,
        "accountingInputHash": validation["inputHash"],
    })
    prior = BusinessActionIdempotency.objects.filter(
        action_code=ACTION_CODE, idempotency_key=idempotency_key
    ).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ReconciliationError(
                "PCP_IDEMPOTENCY_PAYLOAD_CONFLICT",
                "Idempotency key belongs to a different request",
                409,
            )
        if prior.target_id:
            return _existing_result(
                PayableConfirmationPrepare.objects.get(pk=prior.target_id)
            )
    transaction_id = f"PCPTX-{uuid.uuid4().hex}"
    committed = None
    with transaction.atomic():
        lock, created = BusinessActionSourceLock.objects.get_or_create(
            lock_key=f"payable_confirmation_prepare_generation:{source.pk}",
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
                "PCP_IN_PROGRESS", "Source generation is in progress", 409, True
            )
        lock.owner_transaction_id = transaction_id
        lock.state = "acquired"
        lock.released_at = None
        lock.save(update_fields=[
            "owner_transaction_id", "state", "released_at", "acquired_at"
        ])
        _inject("after_persistent_lock", failure_step)
        source = PurchaseAccountsPayableDraft.objects.select_related(
            "source_purchase_reconciliation"
        ).get(pk=source.pk)
        _inject("after_locked_source_reload", failure_step)
        if source.version != expected_source_version:
            raise ReconciliationError(
                "PCP_SOURCE_VERSION_CONFLICT",
                "Source purchase accounts payable draft version changed",
                409,
            )
        _inject("after_source_version_check", failure_step)
        existing = PayableConfirmationPrepare.objects.filter(
            source_purchase_accounts_payable_draft=source
        ).first()
        if existing:
            return _existing_result(existing)
        data, validation = validate_accounting_data(source, accounting_data)
        if not validation["passed"]:
            raise ReconciliationError(
                "PCP_VALIDATION_FAILED",
                ",".join(issue["ruleCode"] for issue in validation["issues"]),
                409,
            )
        _inject("after_accounting_validation", failure_step)
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
                    "PCP_IDEMPOTENCY_PAYLOAD_CONFLICT",
                    "Idempotency key belongs to a different request",
                    409,
                )
            if idem.target_id:
                return _existing_result(
                    PayableConfirmationPrepare.objects.get(pk=idem.target_id)
                )
            raise ReconciliationError(
                "PCP_IN_PROGRESS", "Idempotent request is in progress", 409, True
            )
        _inject("after_idempotency_registration", failure_step)
        reservation = _reserve_number(source, idempotency_key)
        _inject("after_number_reservation", failure_step)
        tx = BusinessActionTransaction.objects.create(
            transaction_id=transaction_id,
            action_code=ACTION_CODE,
            idempotency_key=idempotency_key,
            tenant_id=source.tenant_id,
            source_key=source_key,
            command_id=f"PCP-CMD-{uuid.uuid4().hex}",
            transaction_plan_id=TRANSACTION_PLAN_ID,
            review_id=f"PCP-VALIDATION-{validation['inputHash'][:16]}",
            review_hash=validation["resultHash"],
            status=BusinessActionTransaction.Status.IN_PROGRESS,
            outcome="pending",
            commit_status="in_progress",
            recovery_status="not_required",
            reconciliation=source.source_purchase_reconciliation,
        )
        source_hash = _source_hash(source)
        obj = create_business_object_with_initial_state(
            model=PayableConfirmationPrepare,
            initial_state=PayableConfirmationPrepare.Status.PREPARED,
            prepare_no=reservation.reserved_number,
            source_purchase_accounts_payable_draft=source,
            source_draft_no=source.draft_no,
            source_draft_version=source.version,
            source_key=source_key,
            source_snapshot_hash=source_hash,
            tenant_id=source.tenant_id,
            company_id=source.company_id,
            supplier_id=source.supplier_id,
            supplier_name=source.supplier_name,
            legal_entity_id=source.legal_entity_id,
            legal_entity_name=source.legal_entity_name,
            ledger_book_id=source.ledger_book_id,
            currency=source.currency,
            amount_excluding_tax=source.amount_excluding_tax,
            tax_amount=source.tax_amount,
            payable_amount=source.payable_amount,
            accounting_data_version=1,
            validation_version=1,
            validation_status="passed",
            validation_result_code=validation["resultCode"],
            validation_issue_count=0,
            payment_terms_code=data["paymentTermsCode"],
            payment_terms_days=data["paymentTermsDays"],
            due_date=data["dueDate"],
            accounting_date=data["accountingDate"],
            accounting_period=data["accountingPeriod"],
            debit_total=data["debitTotal"],
            credit_total=data["creditTotal"],
            idempotency_key=idempotency_key,
            number_reservation=reservation,
            business_transaction=tx,
            created_by=user,
        )
        _inject("after_target_insert", failure_step)
        snapshot_payload = {
            key: value.isoformat() if isinstance(value, date) else str(value)
            for key, value in data.items()
        }
        snapshot_hash = canonical_hash({
            "sourceHash": source_hash,
            "accountingData": snapshot_payload,
            "version": 1,
        })
        PayableConfirmationAccountingSnapshot.objects.create(
            payable_confirmation_prepare=obj,
            version=1,
            accounts_payable_account=data["accountsPayableAccount"],
            input_tax_account=data["inputTaxAccount"],
            counterparty_account=data["counterpartyAccount"],
            supplier_auxiliary_id=data["supplierAuxiliaryId"],
            department_id=data["departmentId"],
            cost_center_id=data["costCenterId"],
            project_id=data["projectId"],
            payment_terms_code=data["paymentTermsCode"],
            payment_terms_days=data["paymentTermsDays"],
            due_date=data["dueDate"],
            accounting_date=data["accountingDate"],
            accounting_period=data["accountingPeriod"],
            period_status=data["periodStatus"],
            debit_total=data["debitTotal"],
            credit_total=data["creditTotal"],
            source_payload_hash=source_hash,
            snapshot_hash=snapshot_hash,
        )
        _inject("after_accounting_snapshot_insert", failure_step)
        execution = PayableConfirmationValidationExecution.objects.create(
            payable_confirmation_prepare=obj,
            validation_version=1,
            status="passed",
            result_code=validation["resultCode"],
            issue_count=0,
            rule_set_version=RULE_SET_VERSION,
            input_hash=validation["inputHash"],
            result_hash=validation["resultHash"],
        )
        _inject("after_validation_execution_insert", failure_step)
        PayableConfirmationPrepareSourceRelation.objects.create(
            payable_confirmation_prepare=obj,
            source_id=source.pk,
            source_no=source.draft_no,
            source_version=source.version,
            source_hash=source_hash,
        )
        _inject("after_source_relation_insert", failure_step)
        evidence = {
            "version": "V1.14.2.8.4.7.46",
            "canonicalName": "应付确认准备",
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "sourceDraftNo": source.draft_no,
            "sourceDraftVersion": source.version,
            "sourceSnapshotHash": source_hash,
            "accountingSnapshotHash": snapshot_hash,
            "validationExecutionId": execution.pk,
            "validationResultHash": validation["resultHash"],
            "eligibility": {
                "nextStepReadiness": "ready_for_payment_request_prepare",
                "serverDerived": True,
            },
            "paymentRequestPrepareCreated": False,
            "sqliteConcurrency": {
                "transactionAtomic": True,
                "hardUniqueConstraint": True,
                "optimisticSourceVersion": True,
                "persistentSourceLock": True,
                "rowLockClaimed": False,
            },
        }
        audit = BusinessActionAuditRecord.objects.create(
            transaction=tx,
            action_code=ACTION_CODE,
            tenant_id=source.tenant_id,
            actor=user,
            source_key=source_key,
            reconciliation=source.source_purchase_reconciliation,
            result="committed",
            target_type=DOCUMENT_TYPE,
            target_id=obj.pk,
            target_no=obj.prepare_no,
            review_id=tx.review_id,
            review_hash=tx.review_hash,
            command_id=tx.command_id,
            idempotency_key=idempotency_key,
            actor_name=user.username,
            tenant_or_scope=f"{source.tenant_id}:{source.company_id}",
            evidence_hash=canonical_hash(evidence),
            evidence=evidence,
        )
        obj.audit_record = audit
        obj.save(update_fields=["audit_record", "updated_at"])
        _inject("after_audit_insert", failure_step)
        idem.status = BusinessActionIdempotency.Status.COMMITTED
        idem.target_type = DOCUMENT_TYPE
        idem.target_id = obj.pk
        idem.target_no = obj.prepare_no
        idem.result_reference = f"{DOCUMENT_TYPE}:{obj.pk}"
        idem.save(update_fields=[
            "status", "target_type", "target_id", "target_no",
            "result_reference", "updated_at",
        ])
        _inject("after_idempotency_committed", failure_step)
        reservation.status = BusinessDocumentNumberReservation.Status.CONSUMED
        reservation.consumed_at = timezone.now()
        reservation.save(update_fields=["status", "consumed_at"])
        _inject("after_number_consumed", failure_step)
        tx.status = BusinessActionTransaction.Status.COMMITTED
        tx.outcome = "created"
        tx.commit_status = "committed"
        tx.result_hash = canonical_hash({
            "targetId": obj.pk,
            "targetNo": obj.prepare_no,
            "snapshotHash": snapshot_hash,
        })
        tx.save(update_fields=[
            "status", "outcome", "commit_status", "result_hash", "updated_at"
        ])
        lock.state = "released"
        lock.released_at = timezone.now()
        lock.save(update_fields=["state", "released_at", "acquired_at"])
        _inject("before_database_commit", failure_step)
        committed = obj
    _inject("before_response", failure_step)
    return {
        "classification": "created",
        "created": True,
        "data": serialize_prepare(committed),
        "currentState": build_current_state(
            committed.source_purchase_accounts_payable_draft
        ),
    }


def generate_payable_confirmation_prepare(
    *,
    user,
    source,
    accounting_data,
    idempotency_key,
    expected_source_version,
    failure_step="",
):
    retries = getattr(
        settings, "PCE_PAYABLE_CONFIRMATION_PREPARE_SQLITE_RETRY_COUNT", 3
    )
    interval = getattr(
        settings,
        "PCE_PAYABLE_CONFIRMATION_PREPARE_SQLITE_RETRY_INTERVAL_MS",
        50,
    ) / 1000
    for attempt in range(retries + 1):
        try:
            return _generate_once(
                user=user,
                source=source,
                accounting_data=accounting_data,
                idempotency_key=idempotency_key,
                expected_source_version=expected_source_version,
                failure_step=failure_step,
            )
        except IntegrityError:
            existing = PayableConfirmationPrepare.objects.filter(
                source_purchase_accounts_payable_draft=source
            ).first()
            if existing:
                return _existing_result(existing)
            raise
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= retries:
                raise
            time.sleep(interval * (attempt + 1))
    raise ReconciliationError("PCP_RETRY_EXHAUSTED", "SQLite retry exhausted", 503, True)


def recover_generation_result(idempotency_key):
    idem = BusinessActionIdempotency.objects.filter(
        action_code=ACTION_CODE, idempotency_key=idempotency_key
    ).first()
    if not idem:
        raise ReconciliationError(
            "PCP_IDEMPOTENCY_NOT_FOUND", "Idempotency result not found", 404
        )
    if idem.target_id:
        return _existing_result(
            PayableConfirmationPrepare.objects.get(pk=idem.target_id)
        )
    raise ReconciliationError(
        "PCP_RECOVERY_REQUIRED",
        f"Idempotency state is {idem.status}",
        409,
        True,
    )


def serialize_blocked_scenario(row):
    return {
        "scenarioCode": row.scenario_code,
        "scenarioClass": row.scenario_class,
        "scenarioRole": row.scenario_role,
        "currentModuleCode": "payable-confirmation-prepare",
        "currentObjectNo": row.current_last_valid_object_no,
        "currentStatus": "blocked",
        "formalPayableConfirmationPrepareCreated": False,
        "formalObjectCount": row.formal_object_count,
        "downstreamEligible": False,
        "nextStepAllowed": row.next_step_allowed,
        "blockingModule": row.blocking_module,
        "blockingRuleCode": row.blocking_rule_code,
        "blockingReason": row.blocking_reason,
        "scenarioHash": row.scenario_hash,
    }
