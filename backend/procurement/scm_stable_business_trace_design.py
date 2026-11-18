"""R7 stable SCM trace design reference.

This module is deliberately pure: it imports no Django model and performs no
database, browser storage, provider, or business-state write.
"""

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, Mapping


TRACE_RELATION_TYPES = (
    "SOURCE_FROM",
    "GENERATED_FROM",
    "DECISION_BASED_ON",
    "REFERENCED_BY",
)


def _required(value, field):
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"STABLE_TRACE_{field.upper()}_REQUIRED")
    return normalized


def _canonical(values: Iterable[str]):
    return tuple(sorted({_required(value, "source") for value in values}))


def _source_hash(*parts, length=24):
    canonical = "|".join(_required(part, "hash_part") for part in parts)
    return sha256(canonical.encode("utf-8")).hexdigest()[:length].upper()


def build_quote_comparison_no(source_inquiry_no, material_code):
    """Stable QC identity; quote ordering and comparison version are excluded."""
    return f"QC-{_source_hash('QuoteComparison', source_inquiry_no, material_code)}"


def build_price_approval_preparation_no(comparison_no):
    return f"PAP-{_required(comparison_no, 'comparison_no')}"


def build_decision_batch_no(pap_nos):
    """Single source follows DB-{PAPNo}; multi-source uses a canonical PAP set."""
    sources = _canonical(pap_nos)
    if not sources:
        raise ValueError("STABLE_TRACE_PAP_SOURCE_REQUIRED")
    return f"DB-{sources[0]}" if len(sources) == 1 else f"DB-{_source_hash('DecisionBatch', *sources)}"


def build_gate_no(decision_batch_no):
    return f"GATE-{_required(decision_batch_no, 'decision_batch_no')}"


@dataclass(frozen=True)
class ServerControlledQuoteComparisonFactDesign:
    fact_id: str
    comparison_no: str
    source_quotation_ids: tuple[str, ...]
    source_inquiry_no: str
    material_code: str
    supplier_evidence: tuple[Mapping, ...]
    comparison_version: int
    source_fingerprint: str


def design_quote_comparison_fact(
    *, source_inquiry_no, material_code, source_quotation_ids,
    supplier_evidence, comparison_version,
):
    inquiry_no = _required(source_inquiry_no, "source_inquiry_no")
    material = _required(material_code, "material_code")
    quotation_ids = _canonical(source_quotation_ids)
    if not quotation_ids:
        raise ValueError("STABLE_TRACE_SOURCE_QUOTATION_REQUIRED")
    version = int(comparison_version)
    if version < 1:
        raise ValueError("STABLE_TRACE_COMPARISON_VERSION_INVALID")
    evidence = tuple(sorted(
        (dict(item) for item in supplier_evidence),
        key=lambda item: (
            str(item.get("quotationNo") or ""),
            str(item.get("supplierId") or ""),
        ),
    ))
    if not evidence:
        raise ValueError("STABLE_TRACE_SUPPLIER_EVIDENCE_REQUIRED")
    comparison_no = build_quote_comparison_no(inquiry_no, material)
    evidence_identity = tuple(
        f"{item.get('quotationNo', '')}:{item.get('supplierId', '')}:{item.get('quotationAmount', '')}"
        for item in evidence
    )
    fingerprint = _source_hash(
        "QuoteComparisonFact", inquiry_no, material, *quotation_ids,
        *evidence_identity, str(version), length=64,
    )
    return ServerControlledQuoteComparisonFactDesign(
        fact_id=f"QCF-{fingerprint[:24]}",
        comparison_no=comparison_no,
        source_quotation_ids=quotation_ids,
        source_inquiry_no=inquiry_no,
        material_code=material,
        supplier_evidence=evidence,
        comparison_version=version,
        source_fingerprint=fingerprint,
    )


@dataclass(frozen=True)
class BusinessTraceNode:
    node_id: str
    object_type: str
    object_no: str
    source_node_id: str
    source_object_type: str
    source_object_no: str
    relation_type: str
    created_at: str
    version: int

    def __post_init__(self):
        if self.relation_type not in TRACE_RELATION_TYPES:
            raise ValueError("STABLE_TRACE_RELATION_TYPE_INVALID")


def stable_numbering_self_check():
    quotations_a = ("SQ-003", "SQ-001", "SQ-002")
    quotations_b = tuple(reversed(quotations_a))
    evidence_a = (
        {"quotationNo": "SQ-003", "supplierId": "S3", "quotationAmount": "103"},
        {"quotationNo": "SQ-001", "supplierId": "S1", "quotationAmount": "101"},
        {"quotationNo": "SQ-002", "supplierId": "S2", "quotationAmount": "102"},
    )
    fact_a = design_quote_comparison_fact(
        source_inquiry_no="PI-202608050001", material_code="MT001",
        source_quotation_ids=quotations_a, supplier_evidence=evidence_a,
        comparison_version=1,
    )
    fact_b = design_quote_comparison_fact(
        source_inquiry_no="PI-202608050001", material_code="MT001",
        source_quotation_ids=quotations_b, supplier_evidence=reversed(evidence_a),
        comparison_version=1,
    )
    pap_a = build_price_approval_preparation_no(fact_a.comparison_no)
    pap_b = build_price_approval_preparation_no(fact_b.comparison_no)
    batch_a = build_decision_batch_no((pap_a, "PAP-QC-SECOND"))
    batch_b = build_decision_batch_no(("PAP-QC-SECOND", pap_b))
    return {
        "quoteComparisonStable": fact_a.comparison_no == fact_b.comparison_no,
        "factFingerprintStable": fact_a.source_fingerprint == fact_b.source_fingerprint,
        "priceApprovalPreparationStable": pap_a == pap_b,
        "decisionBatchStable": batch_a == batch_b,
        "gateStable": build_gate_no(batch_a) == build_gate_no(batch_b),
        "productionUserDataWritten": False,
    }
