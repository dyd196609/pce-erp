"""R11 Legacy identity mapping design.

Pure design helpers only. This module performs no ORM, file, localStorage,
Provider, or business-state write and creates no missing business object.
"""

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping

from .scm_stable_business_trace_design import (
    build_decision_batch_no,
    build_gate_no,
    build_price_approval_preparation_no,
    build_quote_comparison_no,
)


LEGACY_IDENTITY_RELATION_TYPES = (
    "LEGACY_OF",
    "ALIAS_TO",
    "TRACE_TO",
    "MISSING_SOURCE",
    "VERIFIED_BY_HUMAN",
)


def _text(value):
    return str(value or "").strip()


def _canonical(values):
    return tuple(sorted({_text(value) for value in values if _text(value)}))


def _id(prefix, *parts):
    payload = "|".join(_text(part) for part in parts)
    return f"{prefix}-{sha256(payload.encode('utf-8')).hexdigest()[:24].upper()}"


@dataclass(frozen=True)
class BusinessTraceAlias:
    alias_id: str
    legacy_object_type: str
    legacy_object_no: str
    canonical_object_type: str
    canonical_object_no: str
    relation_type: str
    verification_status: str
    source_evidence: Mapping
    created_at: str

    def __post_init__(self):
        if self.relation_type not in LEGACY_IDENTITY_RELATION_TYPES:
            raise ValueError("LEGACY_IDENTITY_RELATION_TYPE_INVALID")


@dataclass(frozen=True)
class MissingBusinessEvidence:
    missing_object_type: str
    expected_object_no: str
    source_reference: Mapping
    reason: str
    verification_status: str


def create_alias(*, legacy_type, legacy_no, canonical_type, canonical_no,
                 relation_type="ALIAS_TO", verification_status="evidence_verified",
                 source_evidence=None, created_at=""):
    return BusinessTraceAlias(
        alias_id=_id("BTA", legacy_type, legacy_no, canonical_type, canonical_no, relation_type),
        legacy_object_type=_text(legacy_type),
        legacy_object_no=_text(legacy_no),
        canonical_object_type=_text(canonical_type),
        canonical_object_no=_text(canonical_no),
        relation_type=relation_type,
        verification_status=verification_status,
        source_evidence=dict(source_evidence or {}),
        created_at=_text(created_at),
    )


def create_missing_evidence(*, object_type, expected_no, source_reference,
                            reason="SERVER_OBJECT_NOT_FOUND",
                            verification_status="missing_verified"):
    return MissingBusinessEvidence(
        missing_object_type=_text(object_type),
        expected_object_no=_text(expected_no),
        source_reference=dict(source_reference or {}),
        reason=_text(reason),
        verification_status=_text(verification_status),
    )


def build_legacy_identity_mapping(records, *, source_sha256, created_at):
    """Create an in-memory mapping proposal; never persist or mutate inputs."""
    values = tuple(dict(record) for record in records)
    canonical_pap_by_qc = {}
    for record in values:
        canonical_qc = build_quote_comparison_no(record["sourceInquiryNo"], record["materialCode"])
        canonical_pap_by_qc[record["quoteComparisonNo"]] = build_price_approval_preparation_no(canonical_qc)
    global_batch = build_decision_batch_no(canonical_pap_by_qc.values())
    inquiry_batches = {}
    for inquiry_no in _canonical(record["sourceInquiryNo"] for record in values):
        inquiry_paps = [canonical_pap_by_qc[record["quoteComparisonNo"]]
                        for record in values if record["sourceInquiryNo"] == inquiry_no]
        inquiry_batches[inquiry_no] = build_decision_batch_no(inquiry_paps)

    mappings = []
    aliases = []
    missing = {}
    evidence_root = {"sourceType": "R9_LEGACY_EXPORT", "sourceSha256": source_sha256}
    for index, record in enumerate(values, start=1):
        qc_no = record["quoteComparisonNo"]
        canonical_qc = build_quote_comparison_no(record["sourceInquiryNo"], record["materialCode"])
        canonical_pap = canonical_pap_by_qc[qc_no]
        legacy_reference = record.get("downstreamReference") or {}
        legacy_batches = _canonical(legacy_reference.get("decisionBatchNos") or ())
        canonical_batches = tuple(
            inquiry_batches[record["sourceInquiryNo"]] if "SRDB-SRB-" in legacy else global_batch
            for legacy in legacy_batches
        )
        aliases.append(create_alias(legacy_type="QuoteComparison", legacy_no=qc_no,
            canonical_type="QuoteComparisonFact", canonical_no=canonical_qc, relation_type="LEGACY_OF",
            source_evidence=evidence_root, created_at=created_at))
        for legacy_pap in _canonical(legacy_reference.get("priceApprovalPreparationNos") or ()):
            aliases.append(create_alias(legacy_type="PriceApprovalPreparationContext", legacy_no=legacy_pap,
                canonical_type="PriceApprovalPreparationContext", canonical_no=canonical_pap,
                source_evidence=evidence_root, created_at=created_at))
        for legacy_batch, canonical_batch in zip(legacy_batches, canonical_batches):
            aliases.append(create_alias(legacy_type="SupplierRecommendationDecisionBatch", legacy_no=legacy_batch,
                canonical_type="SupplierRecommendationDecisionBatch", canonical_no=canonical_batch,
                source_evidence=evidence_root, created_at=created_at))
        for legacy_gate in _canonical(legacy_reference.get("gateNos") or ()):
            aliases.append(create_alias(legacy_type="PurchaseOrderGateDecision", legacy_no=legacy_gate,
                canonical_type="PurchaseOrderGateDecision", canonical_no=build_gate_no(global_batch),
                source_evidence=evidence_root, created_at=created_at))
        missing[("PurchaseInquiry", record["sourceInquiryNo"])] = create_missing_evidence(
            object_type="PurchaseInquiry", expected_no=record["sourceInquiryNo"],
            source_reference={"purchaseRequestNo": record.get("purchaseRequestNo"), "quoteComparisonNo": qc_no})
        for quotation_no in record.get("sourceQuotationNo") or ():
            missing[("SupplierQuotation", quotation_no)] = create_missing_evidence(
                object_type="SupplierQuotation", expected_no=quotation_no,
                source_reference={"sourceInquiryNo": record["sourceInquiryNo"], "quoteComparisonNo": qc_no})
        mappings.append({
            "factNo": f"{index:02d}", "legacyQuoteComparisonNo": qc_no,
            "canonicalQuoteComparisonNo": canonical_qc,
            "purchaseRequestNo": record.get("purchaseRequestNo"),
            "purchaseInquiryNo": record["sourceInquiryNo"],
            "supplierQuotationNos": tuple(record.get("sourceQuotationNo") or ()),
            "legacyPaps": _canonical(legacy_reference.get("priceApprovalPreparationNos") or ()),
            "canonicalPap": canonical_pap,
            "legacyBatches": legacy_batches, "canonicalBatches": canonical_batches,
            "legacyGates": _canonical(legacy_reference.get("gateNos") or ()),
            "canonicalGate": build_gate_no(global_batch),
            "mappingStatus": "MISSING_SOURCE",
        })
    return {
        "mappings": tuple(mappings),
        "aliases": tuple(aliases),
        "missingEvidence": tuple(missing[key] for key in sorted(missing)),
        "summary": {
            "mappingCount": len(mappings), "completeCount": 0, "partialCount": 0,
            "missingSourceCount": len(mappings), "missingPurchaseInquiryCount":
                sum(1 for key in missing if key[0] == "PurchaseInquiry"),
            "missingSupplierQuotationCount":
                sum(1 for key in missing if key[0] == "SupplierQuotation"),
            "productionUserDataWritten": False,
        },
    }
