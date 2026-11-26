import uuid
from datetime import time
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from payment_order_draft.services import eligibility as draft_eligibility
from reconciliation.services import ReconciliationError, canonical_hash

from .authority import assert_execute_authorized
from .models import (
    PaymentRiskReview,
    RiskEvidenceSnapshot,
    RiskIssue,
    RiskReviewExecution,
)
from .providers import PaymentOrderDraftRiskEvidenceProvider
from .repositories import PaymentOrderDraftRepository


VERSION = "V1.14.2.8.4.7.52"
CANONICAL_NAME = "真实付款风险评审"
SOURCE_DOCUMENT_TYPE = "paymentOrderDraft"
MODULE_CODE = "payment-risk-review"
NEXT_MODULE_CODE = "formal-payment-order"
NEXT_CANONICAL_NAME = "正式付款单"
NEXT_ROUTE = "/finance/formal-payment-orders"
RULE_VERSION = "payment-risk-review-rules-v1"
RULES = (
    ("PRR_SOURCE_REVIEWED", "来源草稿已复核", "source"),
    ("PRR_SOURCE_DATA_COMPLETE", "来源草稿资料完整", "source"),
    ("PRR_SOURCE_ELIGIBLE", "来源草稿可进入风险评审", "source"),
    ("PRR_SOURCE_VERSION_CURRENT", "来源草稿版本一致", "source"),
    ("PRR_FUNDS_AUTHORITY_PRESENT", "资金权威证据存在", "funds"),
    ("PRR_FUNDS_AVAILABLE", "可用资金充足", "funds"),
    ("PRR_SINGLE_LIMIT", "单笔限额通过", "funds"),
    ("PRR_DAILY_LIMIT", "日累计限额通过", "funds"),
    ("PRR_DUPLICATE_PAYMENT", "不存在重复付款风险", "duplicate"),
    ("PRR_BANK_INTERFACE", "银行接口可用", "bank"),
    ("PRR_PAYMENT_ROUTE", "支付路线有效", "bank"),
    ("PRR_PAYEE_ACCOUNT", "收款账户有效", "bank"),
    ("PRR_SUPPLIER_ACTIVE", "供应商有效且未冻结", "supplier"),
    ("PRR_PAYMENT_DATE", "付款日期为有效工作日", "time"),
    ("PRR_CUTOFF_TIME", "付款时间未超过截止时间", "time"),
    ("PRR_PAYMENT_HOLD", "不存在付款冻结", "supplier"),
    ("PRR_MAKER_CHECKER", "制单复核授权职责分离", "segregation"),
    ("PRR_SIGNING_POLICY", "签署策略有效", "segregation"),
    ("PRR_AUTHORIZATION_ROUTE", "授权路线有效", "segregation"),
    ("PRR_SIGNING_CAPABILITY", "签署能力就绪", "segregation"),
)


def source_hash(draft):
    return canonical_hash({
        "id": draft.pk,
        "draftNo": draft.draft_no,
        "version": draft.version,
        "reviewVersion": draft.current_review_version,
        "status": draft.status,
        "reviewStatus": draft.review_status,
        "reviewResultCode": draft.review_result_code,
        "amount": str(draft.payment_amount),
        "currency": draft.currency,
        "plannedExecutionDate": draft.planned_execution_date.isoformat(),
    })


def ensure_review_for_source(*, user, source, scenario_code):
    allowed = draft_eligibility(source)
    if not allowed.get("eligible"):
        raise ReconciliationError("PRR_SOURCE_NOT_ELIGIBLE", "Source draft is not eligible", 409)
    normalized_scenario_code = str(scenario_code or "").strip()
    if not normalized_scenario_code:
        raise ReconciliationError(
            "PRR_SERVER_SCENARIO_REQUIRED",
            "Server-derived scenario code is required",
            409,
        )
    review_no = source.draft_no.replace("POD", "PRR", 1)
    defaults = {
        "review_no": review_no,
        "source_document_type": SOURCE_DOCUMENT_TYPE,
        "source_payment_order_draft_no": source.draft_no,
        "source_draft_version": source.version,
        "source_draft_review_version": source.current_review_version,
        "source_draft_hash": source_hash(source),
        "scenario_code": normalized_scenario_code,
        "tenant_id": source.tenant_id,
        "company_id": source.company_id,
        "created_by": user,
    }
    try:
        review, created = PaymentRiskReview.objects.get_or_create(
            source_payment_order_draft=source,
            defaults=defaults,
        )
    except IntegrityError:
        review = PaymentRiskReview.objects.get(source_payment_order_draft=source)
        created = False
    return review, created


def _evaluate(review, evidence):
    source = evidence["source"]
    funds = evidence["funds"]
    bank = evidence["bank"]
    supplier = evidence["supplier"]
    duplicate = evidence["duplicatePayment"]
    segregation = evidence["segregation"]
    amount = Decimal(source["paymentAmount"])
    limit = bank.get("limit") or {}
    calendar = bank.get("calendar") or {}
    interface = bank.get("interface") or {}
    route = bank.get("route") or {}
    payee = bank.get("payee") or {}
    hold = bank.get("hold") or {}
    signing = bank.get("signingPolicy") or {}
    authorization = bank.get("authorizationRoute") or {}
    capability = bank.get("signingCapability") or {}
    planned_time = time.fromisoformat(source["plannedExecutionTime"] or "00:00:00")
    cutoff = time.fromisoformat(calendar.get("cutoffTime") or "00:00:00")
    available = Decimal(funds.get("availableForNewPayment") or "0")
    single = Decimal(limit.get("singlePaymentLimit") or "0")
    daily = Decimal(limit.get("dailyPaymentLimit") or "0")
    committed = Decimal(limit.get("currentDailyCommittedAmount") or "0")
    source_obj = PaymentOrderDraftRepository().get(source["draftId"])
    checks = {
        "PRR_SOURCE_REVIEWED": source["status"] == "reviewed" and source["reviewStatus"] == "passed",
        "PRR_SOURCE_DATA_COMPLETE": source["draftDataStatus"] == "complete",
        "PRR_SOURCE_ELIGIBLE": bool(draft_eligibility(source_obj).get("eligible")),
        "PRR_SOURCE_VERSION_CURRENT": (
            source["version"] == review.source_draft_version
            and source["reviewVersion"] == review.source_draft_review_version
            and source_hash(source_obj) == review.source_draft_hash
        ),
        "PRR_FUNDS_AUTHORITY_PRESENT": bool(funds.get("fundsEvidenceId") and funds.get("active")),
        "PRR_FUNDS_AVAILABLE": bool(funds.get("sufficient") and available >= amount),
        "PRR_SINGLE_LIMIT": bool(limit.get("active") and amount <= single),
        "PRR_DAILY_LIMIT": bool(limit.get("active") and committed + amount <= daily),
        "PRR_DUPLICATE_PAYMENT": not duplicate.get("duplicate"),
        "PRR_BANK_INTERFACE": bool(interface.get("active") and interface.get("paymentEnabled") and interface.get("connectionStatus") == "available"),
        "PRR_PAYMENT_ROUTE": bool(route.get("active")),
        "PRR_PAYEE_ACCOUNT": bool(payee.get("active") and payee.get("paymentEnabled")),
        "PRR_SUPPLIER_ACTIVE": bool(supplier.get("active") and not supplier.get("blocked") and supplier.get("accountActive")),
        "PRR_PAYMENT_DATE": bool(calendar.get("businessDay") and calendar.get("paymentAllowed")),
        "PRR_CUTOFF_TIME": bool(calendar and planned_time <= cutoff),
        "PRR_PAYMENT_HOLD": hold.get("holdStatus") != "active",
        "PRR_MAKER_CHECKER": bool(segregation.get("active") and segregation.get("segregationValid")),
        "PRR_SIGNING_POLICY": bool(signing.get("active")),
        "PRR_AUTHORIZATION_ROUTE": bool(authorization.get("active") and authorization.get("steps")),
        "PRR_SIGNING_CAPABILITY": bool(
            capability.get("active")
            and capability.get("credentialStatus") == "ready"
            and capability.get("certificateStatus") == "valid"
            and capability.get("signingServiceStatus") == "available"
        ),
    }
    meta = {code: (description, dimension) for code, description, dimension in RULES}
    return [
        {
            "riskCode": code,
            "riskLevel": "high" if meta[code][1] in {"funds", "duplicate", "bank", "supplier"} else "medium",
            "description": meta[code][0],
            "dimension": meta[code][1],
            "passed": passed,
            "expected": "passed",
            "actual": "passed" if passed else "blocked",
        }
        for code, passed in checks.items()
    ]


def execute_risk_review(*, user, review, idempotency_key, expected_version, explicit_user_action):
    assert_execute_authorized(user, review.tenant_id)
    if not explicit_user_action:
        raise ReconciliationError("PRR_EXPLICIT_ACTION_REQUIRED", "Explicit user action is required", 409)
    if not idempotency_key:
        raise ReconciliationError("PRR_IDEMPOTENCY_REQUIRED", "Idempotency key is required", 400)
    existing = RiskReviewExecution.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.review_id != review.pk:
            raise ReconciliationError("PRR_IDEMPOTENCY_CONFLICT", "Idempotency key conflict", 409)
        return {"classification": "existing_result", "executed": False, "data": serialize_review(review)}
    if review.status == "passed":
        return {"classification": "existing_result", "executed": False, "data": serialize_review(review)}
    provider = PaymentOrderDraftRiskEvidenceProvider()
    with transaction.atomic():
        current = PaymentRiskReview.objects.select_for_update().get(pk=review.pk)
        if current.version != expected_version:
            raise ReconciliationError("VERSION_CONFLICT", "Risk review version conflict", 409)
        source = PaymentOrderDraftRepository().get(current.source_payment_order_draft_id)
        if not source:
            raise ReconciliationError("PRR_SOURCE_MISSING", "Source draft is missing", 409)
        current.status = "reviewing"
        current.transaction_status = "in_progress"
        current.save(update_fields=["status", "transaction_status", "updated_at"])
        evidence = provider.read(source.pk)
        results = _evaluate(current, evidence)
        failures = [row for row in results if not row["passed"]]
        review_version = current.review_version + 1
        input_hash = canonical_hash({
            "reviewId": current.pk,
            "sourceHash": current.source_draft_hash,
            "ruleVersion": RULE_VERSION,
            "evidence": evidence,
        })
        execution = RiskReviewExecution.objects.create(
            review=current,
            execution_id=f"PRRX-{uuid.uuid4().hex}",
            rule_version=RULE_VERSION,
            review_version=review_version,
            passed_count=len(results) - len(failures),
            blocked_count=len(failures),
            failed_count=0,
            idempotency_key=idempotency_key,
            input_hash=input_hash,
            result_hash=canonical_hash(results),
            status="blocked" if failures else "passed",
            actor=user,
            completed_at=timezone.now(),
        )
        for row in failures:
            RiskIssue.objects.create(
                review=current,
                execution=execution,
                risk_code=row["riskCode"],
                risk_level=row["riskLevel"],
                description=row["description"],
                expected=row["expected"],
                actual=row["actual"],
            )
        RiskEvidenceSnapshot.objects.create(
            review=current,
            execution=execution,
            evidence_version=review_version,
            funds_evidence=evidence["funds"],
            bank_evidence=evidence["bank"],
            supplier_evidence=evidence["supplier"],
            duplicate_payment_evidence=evidence["duplicatePayment"],
            segregation_evidence=evidence["segregation"],
            source_draft_evidence=evidence["source"],
            evidence_hash=canonical_hash(evidence),
        )
        current.status = "blocked" if failures else "passed"
        current.risk_result = current.status
        current.risk_level = max(
            (row["riskLevel"] for row in failures),
            default=("medium" if source.payment_amount >= Decimal("100000") else "low"),
        )
        current.review_version = review_version
        current.issue_count = len(failures)
        current.transaction_status = "committed"
        current.audit_status = "committed"
        current.version += 1
        current.save(update_fields=[
            "status", "risk_result", "risk_level", "review_version", "issue_count",
            "transaction_status", "audit_status", "version", "updated_at",
        ])
    return {"classification": "committed", "executed": True, "data": serialize_review(current)}


def eligibility(review):
    issues = list(review.issues.order_by("risk_code"))
    eligible = review.status == "passed" and review.risk_result == "passed" and not issues
    return {
        "status": review.status,
        "riskResult": review.risk_result,
        "riskLevel": review.risk_level,
        "eligible": eligible,
        "blockingReasons": [row.risk_code for row in issues],
        "nextStepReadiness": "ready_for_formal_payment_order" if eligible else "blocked",
        "serverDerived": True,
        "serverRereviewRequired": True,
        "nextModuleCode": NEXT_MODULE_CODE,
        "nextCanonicalName": NEXT_CANONICAL_NAME,
        "nextRoute": NEXT_ROUTE,
    }


def serialize_review(review):
    execution = review.executions.order_by("-review_version").first()
    issues = [
        {
            "riskCode": row.risk_code,
            "riskLevel": row.risk_level,
            "description": row.description,
            "expected": row.expected,
            "actual": row.actual,
        }
        for row in review.issues.order_by("risk_code")
    ]
    source = review.source_payment_order_draft
    return {
        "id": review.pk,
        "reviewNo": review.review_no,
        "sourceDocumentType": review.source_document_type,
        "sourcePaymentOrderDraftId": source.pk,
        "sourcePaymentOrderDraftNo": source.draft_no,
        "scenarioCode": review.scenario_code,
        "supplierId": source.supplier_id,
        "supplierName": source.supplier_name,
        "currency": source.currency,
        "paymentAmount": str(source.payment_amount),
        "plannedExecutionDate": source.planned_execution_date.isoformat(),
        "status": review.status,
        "riskResult": review.risk_result,
        "riskLevel": review.risk_level,
        "reviewVersion": review.review_version,
        "version": review.version,
        "issueCount": review.issue_count,
        "ruleExecution": {
            "executionId": execution.execution_id if execution else None,
            "ruleVersion": execution.rule_version if execution else RULE_VERSION,
            "ruleCount": len(RULES),
            "passedCount": execution.passed_count if execution else 0,
            "blockedCount": execution.blocked_count if execution else 0,
            "failedCount": execution.failed_count if execution else 0,
            "status": execution.status if execution else "not_started",
        },
        "riskIssues": issues,
        "eligibility": eligibility(review),
        "idempotencyStatus": "committed" if execution else "not_started",
        "transactionStatus": review.transaction_status,
        "auditStatus": review.audit_status,
        "currentStateSource": "server",
        "formalPaymentOrderCreated": False,
        "paymentExecuted": False,
    }
