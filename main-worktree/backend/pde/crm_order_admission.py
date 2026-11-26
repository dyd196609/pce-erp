"""Single server-authoritative CRM order admission gate for downstream writes."""

from __future__ import annotations

from dataclasses import dataclass

from sales.crm_source_establishment import (
    SalesOrderCRMSourceEstablishmentError,
    resolve_current_crm_source,
)
from sales.models import SalesOrder
from sales.order_business_purpose_service import (
    PERSISTED_FACT,
    resolve_order_business_purpose,
)
from workflow_runtime.models import ApprovalDecision, WorkflowInstance

from .crm_sales_order_identity import assess_relation_identity
from .legacy_inflight_order_adoption import (
    ADMISSION_MODE as LEGACY_ADMISSION_MODE,
    LegacyInFlightOrderAdoptionError,
    require_active_legacy_adoption,
)
from .models import (
    EngineeringSourceRecord,
    OrderCrossFunctionalReview,
    OrderReviewSalesOrderRelation,
    PDEAdmissionChainRevocation,
)


@dataclass(frozen=True)
class CRMOrderAdmissionResult:
    source_record_id: int
    source_order_no: str
    source_version: str
    source_content_hash: str
    review_id: int
    review_version: int
    workflow_instance_id: int
    approval_decision_id: int

    def as_dict(self):
        return {
            "sourceRecordId": self.source_record_id,
            "sourceOrderNo": self.source_order_no,
            "sourceVersion": self.source_version,
            "sourceContentHash": self.source_content_hash,
            "reviewId": self.review_id,
            "reviewVersion": self.review_version,
            "workflowInstanceId": self.workflow_instance_id,
            "approvalDecisionId": self.approval_decision_id,
            "admitted": True,
        }


@dataclass(frozen=True)
class CRMCurrentOrderAdmissionResult:
    """Current, relation-backed admission for one existing SalesOrder."""

    admission: CRMOrderAdmissionResult
    relation_id: int
    scope_mode: str
    identity: dict

    def as_dict(self):
        return {
            **self.admission.as_dict(),
            "admissionMode": "STANDARD_ADMISSION",
            "legacyAdoptionId": None,
            "relationId": self.relation_id,
            "scopeMode": self.scope_mode,
            "businessIdentity": self.identity,
            "currentPredecessor": None,
            "currentAuthorization": None,
            "historicalReviewException": None,
        }


class CRMOrderAdmissionError(ValueError):
    def __init__(self, code, message, *, details=None, http_status=409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status


def _one_identity(value, field_name):
    if isinstance(value, (list, tuple, set, frozenset)):
        normalized = {str(item).strip() for item in value if str(item).strip()}
    else:
        normalized = {str(value).strip()} if value is not None and str(value).strip() else set()
    if len(normalized) != 1:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_SOURCE_CONTEXT_AMBIGUOUS",
            "CRM订单来源上下文无法唯一确认，已按失败关闭策略阻断下游写入。",
            details={field_name: sorted(normalized)},
        )
    return next(iter(normalized))


def require_crm_order_admission(
    *, company_id, source_record_id, source_order_no, source_version,
    source_content_hash=None, lock=False, review_id=None,
):
    """Return immutable admission facts or raise a fail-closed domain error.

    Explicit legacy ``REJECT`` is evaluated before workflow approval so an
    approval decision can never override the historical business conclusion.
    The itemized flow leaves ``conclusion`` blank and is therefore governed by
    its final workflow decision.
    """

    source_record_id = _one_identity(source_record_id, "sourceRecordIds")
    source_order_no = _one_identity(source_order_no, "sourceOrderNos")
    source_version = _one_identity(source_version, "sourceVersions")
    if source_content_hash not in (None, ""):
        source_content_hash = _one_identity(source_content_hash, "sourceContentHashes")
    try:
        source_record_id = int(source_record_id)
    except (TypeError, ValueError) as exc:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_SOURCE_CONTEXT_AMBIGUOUS",
            "CRM订单来源记录标识无效，已按失败关闭策略阻断下游写入。",
            details={"sourceRecordId": source_record_id},
        ) from exc

    sources = EngineeringSourceRecord.objects
    if lock:
        sources = sources.select_for_update()
    source = sources.filter(
        pk=source_record_id, company_id=company_id, source_version=source_version,
    ).first()
    if not source:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_SOURCE_CONTEXT_NOT_FOUND",
            "CRM订单来源记录、来源版本与企业上下文不一致，已阻断下游写入。",
            details={
                "sourceRecordId": source_record_id,
                "sourceOrderNo": source_order_no,
                "sourceVersion": source_version,
            },
        )
    if source.status != "confirmed":
        raise CRMOrderAdmissionError(
            "CRM_ORDER_SOURCE_NOT_CURRENT",
            "CRM业务来源不是当前已确认版本，不能作为当前订单评审依据。",
            details={
                "sourceRecordId": source.pk,
                "sourceVersion": source.source_version,
                "sourceStatus": source.status,
            },
        )
    current_source_ids = list(
        EngineeringSourceRecord.objects.filter(
            company_id=company_id,
            source_no=source.source_no,
            status="confirmed",
        ).values_list("pk", flat=True)[:3]
    )
    if current_source_ids != [source.pk]:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_SOURCE_CURRENT_VERSION_AMBIGUOUS",
            "CRM业务来源存在多个当前已确认版本，已按失败关闭策略阻断下游写入。",
            details={"sourceRecordIds": current_source_ids},
        )
    if source_content_hash and source_content_hash != source.content_hash:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_SOURCE_HASH_MISMATCH",
            "CRM订单来源内容Hash已变化，已按失败关闭策略阻断下游写入。",
            details={
                "sourceRecordId": source.pk,
                "expectedSourceContentHash": source_content_hash,
                "actualSourceContentHash": source.content_hash,
            },
        )

    reviews = OrderCrossFunctionalReview.objects
    if lock:
        reviews = reviews.select_for_update()
    review = reviews.filter(
        company_id=company_id,
        source_record_id=source_record_id,
        source_order_no=source_order_no,
        source_version=source_version,
        review_type="CRM_ORDER_REVIEW",
        record_status="SUBMITTED",
    )
    if review_id is not None:
        review = review.filter(pk=review_id)
    review = review.order_by("-review_version", "-pk").first()
    if not review:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_REVIEW_MISSING",
            "未找到与唯一来源上下文一致的已提交CRM订单评审，已阻断下游写入。",
        )
    if review.source_content_hash != source.content_hash:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_SOURCE_HASH_MISMATCH",
            "CRM评审依据Hash与当前正式来源Hash不一致，已阻断下游写入。",
            details={
                "reviewId": review.pk,
                "reviewSourceContentHash": review.source_content_hash,
                "actualSourceContentHash": source.content_hash,
            },
        )

    if review.conclusion == "REJECT":
        raise CRMOrderAdmissionError(
            "CRM_ORDER_REVIEW_EXPLICITLY_REJECTED",
            "CRM订单评审已有明确REJECT结论，禁止进入销售订单与PDE下游。",
            details={"reviewId": review.pk, "reviewVersion": review.review_version},
        )
    if review.conclusion == "RETURN_FOR_COMPLETION":
        raise CRMOrderAdmissionError(
            "CRM_ORDER_REVIEW_RETURNED",
            "CRM订单评审已退回补充，禁止进入销售订单与PDE下游。",
            details={"reviewId": review.pk, "reviewVersion": review.review_version},
        )

    workflow = WorkflowInstance.objects.filter(
        document_type="CRMOrderReview", document_id=review.pk,
    ).first()
    if not workflow or workflow.status != WorkflowInstance.Status.APPROVED:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_FINAL_APPROVAL_REQUIRED",
            "CRM订单评审尚未形成最终批准，禁止进入销售订单与PDE下游。",
            details={
                "reviewId": review.pk,
                "workflowStatus": workflow.status if workflow else "missing",
            },
        )
    decision = ApprovalDecision.objects.filter(
        task__workflow_instance=workflow,
    ).order_by("-completed_at", "-pk").first()
    if not decision or decision.decision != "approved":
        raise CRMOrderAdmissionError(
            "CRM_ORDER_FINAL_APPROVAL_REQUIRED",
            "CRM订单评审最终决定不是approved，禁止进入销售订单与PDE下游。",
            details={
                "reviewId": review.pk,
                "decision": decision.decision if decision else "missing",
            },
        )

    return CRMOrderAdmissionResult(
        source_record_id=source.pk,
        source_order_no=source_order_no,
        source_version=source_version,
        source_content_hash=source.content_hash,
        review_id=review.pk,
        review_version=review.review_version,
        workflow_instance_id=workflow.pk,
        approval_decision_id=decision.pk,
    )


def _require_persisted_crm_business_purpose(order):
    try:
        resolution = resolve_order_business_purpose(order)
    except ValueError as exc:
        raise CRMOrderAdmissionError(
            "BUSINESS_PURPOSE_INVALID",
            "订单正式Business Purpose无效，CRM准入已失败关闭。",
            details={"salesOrderId": order.pk},
        ) from exc
    facts = resolution.as_dict()
    facts["admissionEnforcementEnabled"] = True
    if resolution.fact_source != PERSISTED_FACT:
        raise CRMOrderAdmissionError(
            "BUSINESS_PURPOSE_REQUIRED",
            "订单尚未确认正式业务用途，不能进入CRM正式订单评审。",
            details={
                "salesOrderId": order.pk,
                "factSource": resolution.fact_source,
                "legacyMappingIsFormalFact": False,
                "businessPurpose": facts,
            },
        )
    if resolution.business_purpose == SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_FORMAL_REVIEW_NOT_APPLICABLE",
            "开发验证订单不进入正式CRM订单评审链，可继续其合法开发验证流程。",
            details={
                "salesOrderId": order.pk,
                "formalReviewApplicable": False,
                "developmentValidationAllowed": True,
                "businessPurpose": facts,
            },
        )
    if resolution.business_purpose == SalesOrder.BusinessPurpose.SYSTEM_TEST:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_SYSTEM_TEST_ISOLATED",
            "系统测试订单必须保持隔离，不进入CRM正式订单评审链。",
            details={
                "salesOrderId": order.pk,
                "formalReviewApplicable": False,
                "developmentValidationAllowed": False,
                "businessPurpose": facts,
            },
        )
    if resolution.business_purpose != SalesOrder.BusinessPurpose.FORMAL_SALE:
        raise CRMOrderAdmissionError(
            "BUSINESS_PURPOSE_NOT_SUPPORTED_BY_CRM_ADMISSION",
            "当前Business Purpose不允许进入CRM正式订单评审。",
            details={"salesOrderId": order.pk, "businessPurpose": facts},
        )
    return facts


def _require_current_crm_relation_admission(*, order, lock=False):
    """Resolve admission only through an unrevoked formal relation.

    Legacy ``external_source_no`` and ``delivery_information`` are deliberately
    not source-resolution inputs.  They remain identity facts only after the
    formal relation has selected the Source and Review.
    """
    relations = OrderReviewSalesOrderRelation.objects.select_related(
        "review__source_record", "sales_order__customer",
    ).filter(
        company_id=order.company_id,
        sales_order_id=order.pk,
    )
    if lock:
        relations = relations.select_for_update()
    active_relations = list(
        relations.filter(admission_chain_revocation__isnull=True)
        .order_by("review__review_version", "pk")[:3]
    )
    if len(active_relations) > 1:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_CURRENT_RELATION_AMBIGUOUS",
            "当前订单存在多个未撤销CRM正式关系，无法唯一确认当前来源，已失败关闭。",
            details={
                "salesOrderId": order.pk,
                "relationIds": [relation.pk for relation in active_relations],
            },
        )
    if not active_relations:
        revoked = PDEAdmissionChainRevocation.objects.filter(
            crm_order_relation__company_id=order.company_id,
            crm_order_relation__sales_order_id=order.pk,
        ).order_by("-effective_at", "-pk").first()
        if revoked:
            raise CRMOrderAdmissionError(
                "CRM_ORDER_RELATION_REVOKED",
                "当前没有有效CRM业务来源，不能提交订单评审；历史来源已撤销，不作为当前订单评审依据。",
                details={
                    "salesOrderId": order.pk,
                    "revocationId": revoked.pk,
                    "revocationNo": revoked.revocation_no,
                    "revokedRelationId": revoked.crm_order_relation_id,
                },
            )
        try:
            source_binding = resolve_current_crm_source(order=order, lock=lock)
        except SalesOrderCRMSourceEstablishmentError as exc:
            raise CRMOrderAdmissionError(
                exc.code, exc.message, details=exc.details,
            ) from exc
        if not source_binding:
            raise CRMOrderAdmissionError(
                "CRM_ORDER_CURRENT_SOURCE_REQUIRED",
                "当前没有有效CRM业务来源，不能提交订单评审。",
                details={"salesOrderId": order.pk},
            )

        current_source = source_binding.as_dict()
        reviews = OrderCrossFunctionalReview.objects.filter(
            company_id=order.company_id,
            source_record_id=source_binding.source.pk,
            source_order_no=current_source["sourceOrderNo"],
            source_version=source_binding.source.source_version,
            review_type="CRM_ORDER_REVIEW",
            record_status="SUBMITTED",
            created_at__gte=source_binding.identity.first_seen,
            sales_order_relation__isnull=True,
        ).order_by("-review_version", "-pk")
        if lock:
            reviews = reviews.select_for_update()
        review = reviews.first()
        if not review:
            raise CRMOrderAdmissionError(
                "CRM_ORDER_REVIEW_MISSING",
                "当前正式CRM来源已建立，但尚未形成该订单的新CRM订单评审。",
                details={
                    "salesOrderId": order.pk,
                    "currentSource": current_source,
                    "currentReview": None,
                    "currentRelation": None,
                },
            )
        current_review = {
            "reviewId": review.pk,
            "reviewVersion": review.review_version,
            "recordStatus": review.record_status,
            "conclusion": review.conclusion,
        }
        try:
            admission = require_crm_order_admission(
                company_id=order.company_id,
                source_record_id=source_binding.source.pk,
                source_order_no=current_source["sourceOrderNo"],
                source_version=source_binding.source.source_version,
                source_content_hash=source_binding.source.content_hash,
                lock=lock,
                review_id=review.pk,
            )
        except CRMOrderAdmissionError as exc:
            raise CRMOrderAdmissionError(
                exc.code,
                exc.message,
                details={
                    **exc.details,
                    "salesOrderId": order.pk,
                    "currentSource": current_source,
                    "currentReview": current_review,
                    "currentRelation": None,
                },
                http_status=exc.http_status,
            ) from exc
        raise CRMOrderAdmissionError(
            "CRM_ORDER_CURRENT_RELATION_REQUIRED",
            "CRM来源和订单评审已具备，但尚未形成该订单的0032正式范围关系。",
            details={
                "salesOrderId": order.pk,
                "currentSource": current_source,
                "currentReview": {
                    **current_review,
                    "workflowInstanceId": admission.workflow_instance_id,
                    "approvalDecisionId": admission.approval_decision_id,
                },
                "currentRelation": None,
            },
        )

    relation = active_relations[0]
    review = relation.review
    source = review.source_record
    admission = require_crm_order_admission(
        company_id=order.company_id,
        source_record_id=source.pk,
        source_order_no=review.source_order_no,
        source_version=review.source_version,
        source_content_hash=relation.source_content_hash_snapshot,
        lock=lock,
    )
    if admission.review_id != relation.review_id:
        raise CRMOrderAdmissionError(
            "CRM_ORDER_HISTORICAL_REVIEW_NOT_CURRENT",
            "历史CRM订单评审不是当前正式关系的有效评审版本，已失败关闭。",
            details={
                "relationId": relation.pk,
                "relationReviewId": relation.review_id,
                "currentReviewId": admission.review_id,
            },
        )

    scope_item_ids = set(
        relation.scope_items.values_list("sales_order_item_id", flat=True)
    )
    current_item_ids = set(order.items.values_list("pk", flat=True))
    if (
        not scope_item_ids
        or not scope_item_ids.issubset(current_item_ids)
        or (
            relation.scope_mode == "WHOLE_ORDER"
            and scope_item_ids != current_item_ids
        )
    ):
        raise CRMOrderAdmissionError(
            "CRM_ORDER_CURRENT_SCOPE_MISMATCH",
            "CRM正式关系未精确覆盖当前销售订单行范围，已失败关闭。",
            details={
                "relationId": relation.pk,
                "scopeMode": relation.scope_mode,
                "relationItemIds": sorted(scope_item_ids),
                "currentOrderItemIds": sorted(current_item_ids),
            },
        )

    identity = assess_relation_identity(relation)
    if not identity["allowed"]:
        raise CRMOrderAdmissionError(
            (
                "CRM_SALES_ORDER_BUSINESS_IDENTITY_CONFLICT"
                if identity["statusCode"] == "CONFLICT"
                else "CRM_SALES_ORDER_BUSINESS_IDENTITY_NOT_PROVEN"
            ),
            "CRM来源与当前销售订单的客户、项目、合同或订单行范围不一致，已失败关闭。",
            details={
                "relationId": relation.pk,
                "businessIdentity": identity,
            },
        )

    return CRMCurrentOrderAdmissionResult(
        admission=admission,
        relation_id=relation.pk,
        scope_mode=relation.scope_mode,
        identity=identity,
    )


def require_current_order_admission(
    *, order, lock=False, sales_order_item_id=None,
    engineering_instance_id=None, calculation_id=None,
):
    """Central current-order admission resolver.

    Standard admissions keep the existing CRM -> 0032 contract.  A persisted
    legacy adoption is resolved as its own explicit mode and only for the
    immutable historical item/OEI/calculation scope saved in that fact.
    """

    _require_persisted_crm_business_purpose(order)
    try:
        legacy = require_active_legacy_adoption(
            order=order,
            sales_order_item_id=sales_order_item_id,
            engineering_instance_id=engineering_instance_id,
            calculation_id=calculation_id,
            lock=lock,
        )
    except LegacyInFlightOrderAdoptionError as exc:
        raise CRMOrderAdmissionError(
            exc.code, exc.message, details=exc.details,
        ) from exc
    if legacy:
        return legacy
    return _require_current_crm_relation_admission(order=order, lock=lock)


def require_current_crm_sales_order_admission(*, order, lock=False):
    """Compatibility name for the unified current-order admission resolver."""

    return require_current_order_admission(order=order, lock=lock)


def _require_candidate_analysis_crm_admission(*, order, lock=False):
    """Preserve analyzer V1 semantics without authorizing a formal action.

    This compatibility path exists only so an already-issued candidate
    fingerprint can be re-evaluated after the formal CRM policy switches to
    persisted Business Purpose.  No action service calls this function.
    """

    marker = str(getattr(order, "acceptance_marker", "") or "").strip()
    if marker:
        raise CRMOrderAdmissionError(
            (
                "CRM_ORDER_DEVELOPMENT_ONLY"
                if marker == "DEVELOPMENT_ONLY"
                else "CRM_ORDER_NON_BUSINESS_SAMPLE"
            ),
            "开发或验收样本订单不具备正式CRM订单评审准入资格。",
            details={"salesOrderId": order.pk, "acceptanceMarker": marker},
        )
    return _require_current_crm_relation_admission(order=order, lock=lock)


def _current_crm_sales_order_admission_facts(order, *, resolver, include_purpose):
    """Build a projection from one selected server-side admission resolver."""

    admitted = None
    error = None
    try:
        admitted = resolver(order=order)
    except CRMOrderAdmissionError as exc:
        error = exc

    historical_sources = []
    relations = OrderReviewSalesOrderRelation.objects.select_related(
        "review__source_record",
    ).filter(
        company_id=order.company_id,
        sales_order_id=order.pk,
    ).order_by("review__review_version", "pk")
    revocations = {
        row.crm_order_relation_id: row
        for row in PDEAdmissionChainRevocation.objects.filter(
            crm_order_relation__in=relations,
        )
    }
    for relation in relations:
        review = relation.review
        source = review.source_record
        revocation = revocations.get(relation.pk)
        historical_sources.append({
            "sourceRecordId": source.pk,
            "sourceNo": source.source_no,
            "sourceVersion": source.source_version,
            "sourceStatus": source.status,
            "reviewId": review.pk,
            "reviewVersion": review.review_version,
            "relationId": relation.pk,
            "relationStatus": "REVOKED" if revocation else "ACTIVE",
            "revocationId": revocation.pk if revocation else None,
            "revocationNo": revocation.revocation_no if revocation else "",
            "currentAdmissible": bool(
                admitted and admitted.relation_id == relation.pk
            ),
            "statusLabel": (
                "历史来源已撤销，不具备当前准入资格"
                if revocation else
                "当前正式CRM来源" if admitted and admitted.relation_id == relation.pk
                else "历史来源，不具备当前准入资格"
            ),
        })

    error_current_source = (error.details or {}).get("currentSource") if error else None
    if error_current_source and not any(
        row["sourceRecordId"] == error_current_source["sourceRecordId"]
        for row in historical_sources
    ):
        historical_sources.append({
            "sourceRecordId": error_current_source["sourceRecordId"],
            "sourceNo": error_current_source["sourceNo"],
            "sourceVersion": error_current_source["sourceVersion"],
            "sourceStatus": error_current_source["sourceStatus"],
            "reviewId": None,
            "reviewVersion": None,
            "relationId": None,
            "relationStatus": "SOURCE_ESTABLISHED",
            "revocationId": None,
            "revocationNo": "",
            "currentAdmissible": False,
            "statusLabel": "当前正式CRM来源；订单评审尚未完成",
        })

    if admitted:
        data = admitted.as_dict()
        legacy_mode = data.get("admissionMode") == LEGACY_ADMISSION_MODE
        projection = {
            **data,
            "statusCode": (
                data.get("statusCode")
                if legacy_mode else "CRM_ORDER_CURRENT_SOURCE_VALID"
            ),
            "statusLabel": (
                data.get("statusLabel")
                if legacy_mode else "当前CRM来源有效"
            ),
            "message": (
                "历史在制订单已通过独立Legacy Adoption承接；标准Admission对象未伪造。"
                if legacy_mode else
                "当前CRM来源、评审、正式关系及订单行范围校验通过。"
            ),
            "currentSource": {
                "sourceRecordId": data["sourceRecordId"],
                "sourceIdentityId": data.get("sourceIdentityId"),
                "sourceOrderNo": data["sourceOrderNo"],
                "sourceVersion": data["sourceVersion"],
                "reviewId": data.get("reviewId"),
                "relationId": data.get("relationId"),
            },
            "currentSourceId": data["sourceRecordId"],
            "currentSourceVersion": data["sourceVersion"],
            "currentReview": (
                None if legacy_mode else {
                    "reviewId": data["reviewId"],
                    "reviewVersion": data["reviewVersion"],
                    "workflowInstanceId": data["workflowInstanceId"],
                    "approvalDecisionId": data["approvalDecisionId"],
                }
            ),
            "currentRelation": (
                None if legacy_mode else {"relationId": data["relationId"]}
            ),
            "currentPredecessor": data.get("currentPredecessor"),
            "currentAuthorization": data.get("currentAuthorization"),
            "historicalReviewException": data.get("historicalReviewException"),
            "historicalSources": historical_sources,
            "submitAllowed": False if legacy_mode else order.status == "draft",
        }
        if include_purpose:
            purpose = resolve_order_business_purpose(order).as_dict()
            purpose["admissionEnforcementEnabled"] = True
            projection.update({
                "businessPurpose": purpose,
                "businessPurposeSource": purpose["factSource"],
                "formalReviewApplicable": True,
                "developmentValidationAllowed": False,
            })
        return projection
    projection = {
        "admitted": False,
        "statusCode": error.code,
        "statusLabel": (
            "正式CRM订单评审不适用"
            if error.code in {
                "CRM_ORDER_FORMAL_REVIEW_NOT_APPLICABLE",
                "CRM_ORDER_SYSTEM_TEST_ISOLATED",
            }
            else "订单业务用途待确认"
            if error.code == "BUSINESS_PURPOSE_REQUIRED"
            else "当前正式CRM来源已建立，订单评审待建立"
            if error.code == "CRM_ORDER_REVIEW_MISSING"
            else "当前CRM来源未建立"
        ),
        "message": error.message,
        "details": error.details,
        "currentSource": (error.details or {}).get("currentSource"),
        "currentSourceId": (
            ((error.details or {}).get("currentSource") or {}).get("sourceRecordId")
        ),
        "currentSourceVersion": (
            ((error.details or {}).get("currentSource") or {}).get("sourceVersion")
        ),
        "currentReview": (error.details or {}).get("currentReview"),
        "currentRelation": (error.details or {}).get("currentRelation"),
        "historicalSources": historical_sources,
        "submitAllowed": False,
    }
    if include_purpose:
        purpose = (error.details or {}).get("businessPurpose")
        if not purpose:
            try:
                purpose = resolve_order_business_purpose(order).as_dict()
            except ValueError:
                purpose = {
                    "businessPurpose": None,
                    "businessPurposeLabel": "无效",
                    "factSource": "INVALID",
                    "isPersisted": False,
                    "isLegacyMapping": False,
                }
        purpose["admissionEnforcementEnabled"] = True
        projection.update({
            "businessPurpose": purpose,
            "businessPurposeSource": purpose["factSource"],
            "formalReviewApplicable": bool(
                error.code not in {
                    "CRM_ORDER_FORMAL_REVIEW_NOT_APPLICABLE",
                    "CRM_ORDER_SYSTEM_TEST_ISOLATED",
                }
            ),
            "developmentValidationAllowed": bool(
                (error.details or {}).get("developmentValidationAllowed")
            ),
        })
    return projection


def current_crm_sales_order_admission_facts(order):
    """Formal server-owned projection shared by API, page and actions."""

    return _current_crm_sales_order_admission_facts(
        order,
        resolver=require_current_crm_sales_order_admission,
        include_purpose=True,
    )


def candidate_analysis_crm_sales_order_admission_facts(order):
    """Read-only analyzer V1 projection; never valid for a formal action."""

    return _current_crm_sales_order_admission_facts(
        order,
        resolver=_require_candidate_analysis_crm_admission,
        include_purpose=False,
    )
