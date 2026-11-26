from django.db import transaction
from django.utils import timezone

from .legacy_quote_comparison_adapter import LegacyQuoteComparisonAdapter
from .models import PriceApprovalPreparation, QuoteComparisonFact


ALLOWED_TRANSITIONS = {
    "draft": {"reviewing"},
    "reviewing": {"completed"},
    "completed": {"reviewing"},
    "approved": set(),
    "rejected": set(),
}

PRICE_APPROVAL_STATUS_LABELS = {
    "draft": "草稿",
    "reviewing": "核价中",
    "completed": "已完成",
}

REVIEW_RESULT_LABELS = {
    "pass": "通过",
    "reject": "不同意",
    "adjust": "调整后重新核价",
}

QUOTATION_STATUS_LABELS = {
    "supplier_quote_collecting": "供应商报价收集中",
    "quotation_received": "报价已接收",
    "received": "报价已接收",
}


def _text(value):
    return str(value or "").strip()


def _candidate_from_evidence(item):
    return {
        "supplierId": item.get("supplierId"),
        "supplierCode": item.get("supplierCode") or item.get("supplierId"),
        "supplierName": item.get("supplierName"),
        "quotationNo": item.get("quotationNo"),
        "quotationAmount": item.get("quotationAmount"),
        "quotationStatus": item.get("quotationStatus"),
        "receivedAt": item.get("receivedAt"),
    }


def _serialize_quotation_evidence(items):
    evidence = []
    for source in items or []:
        item = dict(source)
        status_code = item.get("quotationStatusCode") or item.get("quotationStatus") or ""
        item["quotationStatusCode"] = status_code
        status_label = (
            QUOTATION_STATUS_LABELS.get(status_code)
            or item.get("quotationStatusLabel")
            or status_code
        )
        item["quotationStatusLabel"] = (
            f"{status_code}（{status_label}）" if status_code else status_label
        )
        evidence.append(item)
    return evidence


def resolve_price_approval_review_result(preparation):
    if preparation.review_result in REVIEW_RESULT_LABELS:
        return preparation.review_result
    opinion = _text(preparation.approval_opinion).lower()
    if opinion in {"同意", "通过", "approve", "approved", "pass"}:
        return "pass"
    if opinion in {"不同意", "拒绝", "驳回", "reject", "rejected"}:
        return "reject"
    if "调整" in opinion or "重新核价" in opinion:
        return "adjust"
    return ""


def resolve_price_approval_process_status(preparation):
    return "completed" if preparation.status in {"approved", "rejected"} else preparation.status


def has_received_quotation_evidence(preparation):
    evidence = preparation.source_quotation_evidence or []
    return bool(evidence) and all(
        _text(item.get("quotationStatusCode") or item.get("quotationStatus")) == "quotation_received"
        for item in evidence
    )


def resolve_supplier_recommendation_blocked_reason(preparation):
    if (resolve_price_approval_process_status(preparation) != "completed"
            or resolve_price_approval_review_result(preparation) != "pass"):
        return "当前核价结果未通过，不允许进入供应商推荐。"
    if not has_received_quotation_evidence(preparation):
        return "当前供应商报价尚未全部接收，不允许进入供应商推荐。"
    from masterdata.supplier_master_runtime import SupplierBusinessMapping

    candidates = [item for item in preparation.supplier_candidates or [] if isinstance(item, dict)]
    selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
    formal_recommendation_suppliers = [*candidates, *([selected] if selected else [])]
    if any(SupplierBusinessMapping._resolve(
        supplier_id=item.get("supplierId"),
        supplier_code=item.get("supplierCode", ""),
        supplier_name=item.get("supplierName", ""),
    ) is None for item in formal_recommendation_suppliers):
        return "正式推荐候选供应商无法全部解析到SupplierMaster（供应商主数据），不允许进入正式供应商推荐。"
    return ""


def is_supplier_recommendation_eligible(preparation):
    return not resolve_supplier_recommendation_blocked_reason(preparation)


def serialize_quote_comparison_candidate(comparison):
    evidence = [dict(item) for item in comparison.supplier_quote_evidence]
    return {
        "factId": str(comparison.fact_id),
        "quoteComparisonNo": comparison.comparison_no,
        "sourceInquiryNo": comparison.source_inquiry_no,
        "sourceQuotationIds": comparison.source_quotation_ids,
        "supplierQuoteEvidence": evidence,
        "supplierCount": len(evidence),
        "materialCode": comparison.material_code,
        "materialName": comparison.material_name,
        "quantity": str(comparison.quantity),
        "quotationAmount": comparison.quotation_amount,
        "lowestPrice": str(comparison.lowest_price),
        "comparisonResult": comparison.comparison_result,
        "factVersion": comparison.fact_version,
        "verifiedStatus": comparison.verified_status,
        "generatedAt": comparison.generated_at.isoformat(),
        "factSource": "QuoteComparisonFact",
        "factOrigin": "production_fact",
        "sourceConfidence": "A",
        "projectionId": None,
        "priceApprovalPreparationCreated": False,
    }


def serialize_legacy_projection_candidate(projection):
    payload = projection.to_dict()
    return {
        **payload,
        "quoteComparisonNo": projection.legacyQuoteComparisonNo,
        "supplierQuoteEvidence": list(projection.supplierEvidence),
        "supplierCount": len(projection.supplierEvidence),
        "materialCode": projection.materialLines[0].get("materialCode"),
        "materialName": projection.materialLines[0].get("materialName"),
        "factSource": "QuoteComparisonFactProjection",
        "priceApprovalPreparationCreated": False,
    }


def serialize_price_approval_preparation(preparation):
    source = preparation.source_comparison
    comparison_no = (source.comparison_no if source else preparation.source_legacy_comparison_no)
    process_status = resolve_price_approval_process_status(preparation)
    review_result = resolve_price_approval_review_result(preparation)
    recommendation_blocked_reason = resolve_supplier_recommendation_blocked_reason(preparation)
    return {
        "id": preparation.pk,
        "objectType": "PriceApprovalPreparation",
        "approvalPrepareNo": preparation.approval_prepare_no,
        "sourceComparisonNo": comparison_no,
        "sourceComparisonFactId": str(source.fact_id) if source else None,
        "sourceProjectionId": preparation.source_projection_id,
        "sourceTraceAliasId": preparation.source_trace_alias_id,
        "sourceInquiryNo": (source.source_inquiry_no if source
            else preparation.source_projection_snapshot.get("sourceInquiryNo", "")),
        "sourceProjectionSnapshot": preparation.source_projection_snapshot,
        "factOrigin": preparation.fact_origin,
        "sourceConfidence": preparation.source_confidence,
        "sourceQuotationEvidence": _serialize_quotation_evidence(preparation.source_quotation_evidence),
        "supplierCandidates": preparation.supplier_candidates,
        "materialLines": preparation.material_lines,
        "comparisonBasis": preparation.comparison_basis,
        "historicalPriceReference": preparation.historical_price_reference,
        "selectedSupplier": preparation.selected_supplier,
        "reviewOpinion": preparation.review_opinion,
        "exceptionNote": preparation.exception_note,
        "approvalOpinion": preparation.approval_opinion,
        "status": process_status,
        "statusCode": process_status,
        "storedStatusCode": preparation.status,
        "statusLabel": PRICE_APPROVAL_STATUS_LABELS.get(process_status, preparation.get_status_display()),
        "reviewResult": review_result,
        "reviewResultLabel": REVIEW_RESULT_LABELS.get(review_result, "待确认"),
        "supplierRecommendationEligible": not recommendation_blocked_reason,
        "supplierRecommendationBlockedReason": recommendation_blocked_reason,
        "decisionVersion": preparation.decision_version,
        "reviewer": preparation.reviewer,
        "reviewedAt": preparation.reviewed_at.isoformat() if preparation.reviewed_at else None,
        "createdAt": preparation.created_at.isoformat(),
        "dataMode": "production",
        "factSource": "QuoteComparisonFact" if source else "QuoteComparisonFactProjection",
        "automaticLowestQuoteSelected": False,
        "supplierRecommendationCreated": False,
        "purchaseOrderCreated": False,
    }


@transaction.atomic
def create_price_approval_preparation(comparison_no):
    comparison = QuoteComparisonFact.objects.select_for_update().get(comparison_no=comparison_no)
    evidence = [dict(item) for item in comparison.supplier_quote_evidence]
    candidates = [_candidate_from_evidence(item) for item in evidence]
    material_lines = [{
        "materialCode": comparison.material_code,
        "materialName": comparison.material_name,
        "quantity": str(comparison.quantity),
    }]
    preparation, created = PriceApprovalPreparation.objects.get_or_create(
        source_comparison=comparison,
        defaults={
            "approval_prepare_no": f"PAP-{comparison.comparison_no}",
            "fact_origin": "production_fact",
            "source_confidence": "A",
            "source_quotation_evidence": evidence,
            "supplier_candidates": candidates,
            "material_lines": material_lines,
            "comparison_basis": dict(comparison.comparison_result),
            "historical_price_reference": [],
        },
    )
    return preparation, created


@transaction.atomic
def create_price_approval_preparation_from_projection(projection_id):
    projection = LegacyQuoteComparisonAdapter().get_projection(projection_id)
    if projection is None:
        raise ValueError("LEGACY_QUOTE_COMPARISON_PROJECTION_NOT_FOUND")
    evidence = [dict(item) for item in projection.supplierEvidence]
    candidates = [_candidate_from_evidence(item) for item in evidence]
    preparation, created = PriceApprovalPreparation.objects.get_or_create(
        source_projection_id=projection.projectionId,
        defaults={
            "approval_prepare_no": f"PAP-{projection.legacyQuoteComparisonNo}",
            "source_legacy_comparison_no": projection.legacyQuoteComparisonNo,
            "source_trace_alias_id": projection.traceAliasId,
            "source_projection_snapshot": projection.to_dict(),
            "fact_origin": "legacy_verified_fact",
            "source_confidence": projection.sourceConfidence,
            "source_quotation_evidence": evidence,
            "supplier_candidates": candidates,
            "material_lines": [dict(item) for item in projection.materialLines],
            "comparison_basis": projection.comparisonResult,
            "historical_price_reference": [],
        },
    )
    return preparation, created


@transaction.atomic
def transition_price_approval_preparation(preparation_id, target_status, payload, actor):
    preparation = PriceApprovalPreparation.objects.select_for_update().select_related("source_comparison").get(pk=preparation_id)
    legacy_result = {"approved": "pass", "rejected": "reject"}.get(target_status)
    if legacy_result:
        target_status = "completed"
        payload = {**payload, "reviewResult": payload.get("reviewResult") or legacy_result}
    current_status = resolve_price_approval_process_status(preparation)
    if current_status == "completed" and target_status == "reviewing":
        if resolve_price_approval_review_result(preparation) != "adjust":
            raise ValueError("PRICE_APPROVAL_REVIEW_REOPEN_NOT_ALLOWED")
        preparation.status = "reviewing"
        preparation.full_clean()
        preparation.save()
        return preparation
    if target_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise ValueError("PRICE_APPROVAL_STATUS_TRANSITION_NOT_ALLOWED")
    if target_status == "reviewing":
        preparation.status = "reviewing"
    else:
        supplier_code = _text(payload.get("selectedSupplierCode"))
        candidate = next((item for item in preparation.supplier_candidates
            if _text(item.get("supplierCode") or item.get("supplierId")) == supplier_code), None)
        review_result = _text(payload.get("reviewResult"))
        if review_result not in REVIEW_RESULT_LABELS:
            raise ValueError("PRICE_APPROVAL_REVIEW_RESULT_REQUIRED")
        if review_result == "pass" and candidate is None:
            raise ValueError("PRICE_APPROVAL_SELECTED_SUPPLIER_REQUIRED")
        if (not _text(payload.get("reviewOpinion"))
                or not _text(payload.get("approvalOpinion"))
                or not _text(actor)):
            raise ValueError("PRICE_APPROVAL_MANUAL_DECISION_INCOMPLETE")
        preparation.selected_supplier = dict(candidate or {})
        preparation.review_opinion = _text(payload.get("reviewOpinion"))
        preparation.exception_note = _text(payload.get("exceptionNote"))
        preparation.approval_opinion = _text(payload.get("approvalOpinion"))
        preparation.review_result = review_result
        preparation.reviewer = _text(actor)
        preparation.reviewed_at = timezone.now()
        preparation.decision_version += 1
        preparation.status = target_status
    preparation.full_clean()
    preparation.save()
    return preparation


def build_supplier_recommendation_context(preparation):
    blocked_reason = resolve_supplier_recommendation_blocked_reason(preparation)
    if blocked_reason:
        raise ValueError(blocked_reason)
    from masterdata.supplier_master_runtime import SupplierBusinessMapping

    def master_reference(candidate):
        candidate = dict(candidate) if isinstance(candidate, dict) else {}
        supplier = SupplierBusinessMapping._resolve(
            supplier_id=candidate.get("supplierId"), supplier_code=candidate.get("supplierCode", ""),
            supplier_name=candidate.get("supplierName", ""),
        )
        return {
            **candidate,
            "supplierMasterId": supplier.pk if supplier else None,
            "supplierMasterCode": supplier.code if supplier else "",
            "supplierMasterName": supplier.name if supplier else "",
            "sourceReference": candidate.get("supplierCode") or candidate.get("supplierId") or "",
        }

    return {
        "objectType": "SupplierRecommendationDecisionContext",
        "sourcePriceApprovalPreparationNo": preparation.approval_prepare_no,
        "sourceComparisonNo": (preparation.source_comparison.comparison_no
            if preparation.source_comparison_id else preparation.source_legacy_comparison_no),
        "factOrigin": preparation.fact_origin,
        "sourceProjectionId": preparation.source_projection_id,
        "sourceTraceAliasId": preparation.source_trace_alias_id,
        "materialLines": preparation.material_lines,
        "supplierCandidates": [master_reference(item) for item in preparation.supplier_candidates or []],
        "selectedSupplier": master_reference(preparation.selected_supplier),
        "reviewResult": resolve_price_approval_review_result(preparation),
        "reviewResultLabel": REVIEW_RESULT_LABELS[resolve_price_approval_review_result(preparation)],
        "priceEvidence": preparation.source_quotation_evidence,
        "historicalPriceEvidence": preparation.historical_price_reference,
        "manualAssessment": {
            "reviewOpinion": preparation.review_opinion,
            "exceptionNote": preparation.exception_note,
            "approvalOpinion": preparation.approval_opinion,
            "reviewer": preparation.reviewer,
            "reviewedAt": preparation.reviewed_at.isoformat() if preparation.reviewed_at else None,
            "decisionVersion": preparation.decision_version,
        },
        "status": "context_ready",
        "purchaseOrderCreated": False,
    }
