"""QuoteComparisonFact固化候选预检；本模块故意不提供写入或迁移函数。"""

from decimal import Decimal, InvalidOperation


REQUIRED_DOWNSTREAM_TYPES = {
    "PriceApprovalPreparationContext",
    "SupplierRecommendationDecisionBatchResult",
    "PurchaseOrderGateDecision",
}
REQUIRED_EVIDENCE_FIELDS = {
    "supplierId", "supplierName", "quotationNo", "quotationAmount",
    "quotationStatus", "receivedAt",
}


def _text(value):
    return str(value or "").strip()


def _positive_decimal(value):
    try:
        return Decimal(str(value)) > 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def assess_quote_comparison_fact_candidate(candidate=None, downstream_references=None,
                                               manual_confirmation=None):
    candidate = candidate or {}
    downstream_references = downstream_references or []
    manual_confirmation = manual_confirmation or {}
    evidence = candidate.get("supplierQuoteEvidence") or []
    source_quotation_ids = candidate.get("sourceQuotationIds") or []
    reference_types = {_text(item.get("targetType")) for item in downstream_references}

    checks = {
        "sourceInquiryExists": bool(_text(candidate.get("sourceInquiryNo"))),
        "supplierQuotationExists": bool(source_quotation_ids) and bool(evidence),
        "materialExists": bool(_text(candidate.get("materialCode")))
            and bool(_text(candidate.get("materialName"))),
        "amountExists": bool(evidence) and all(
            _positive_decimal(item.get("quotationAmount")) for item in evidence
        ),
        "comparisonResultExists": bool(candidate.get("comparisonResult"))
            and _positive_decimal(candidate.get("lowestPrice")),
        "sourceEvidenceComplete": bool(evidence) and all(
            REQUIRED_EVIDENCE_FIELDS.issubset(item)
            and all(item.get(field) not in (None, "") for field in REQUIRED_EVIDENCE_FIELDS)
            for item in evidence
        ),
        "generatedAtExists": bool(_text(candidate.get("generatedAt"))),
        "downstreamReferenceComplete": REQUIRED_DOWNSTREAM_TYPES.issubset(reference_types),
        "manualConfirmation": bool(_text(manual_confirmation.get("confirmedBy")))
            and bool(_text(manual_confirmation.get("confirmedAt")))
            and manual_confirmation.get("confirmed") is True,
    }
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "comparisonNo": _text(candidate.get("comparisonNo")),
        "sourceType": _text(candidate.get("sourceType") or "runtime_fact"),
        "checks": checks,
        "missingChecks": missing,
        "eligibleForSolidification": not missing,
        "migrationExecuted": False,
        "productionUserDataWritten": False,
    }


def build_legacy_fact_assessment(candidates=None, downstream_reference_map=None,
                                 manual_confirmation_map=None):
    candidates = candidates or []
    downstream_reference_map = downstream_reference_map or {}
    manual_confirmation_map = manual_confirmation_map or {}
    return [
        assess_quote_comparison_fact_candidate(
            candidate,
            downstream_reference_map.get(_text(candidate.get("comparisonNo")), []),
            manual_confirmation_map.get(_text(candidate.get("comparisonNo")), {}),
        )
        for candidate in candidates
    ]
