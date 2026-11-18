"""Generic, evidence-led applicability for independently managed material roles.

Appearance and process descriptions are intentionally kept separate from physical
material identity.  Callers must provide saved, server-side evidence; this module
does not inspect display text, query mutable masters, or create business facts.
"""

from __future__ import annotations


APPLICABLE = "APPLICABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNRESOLVED = "UNRESOLVED"

CONFIRMED_EVIDENCE_STATUSES = {"APPLICABLE", "CONFIRMED", "PRESENT", "RESOLVED"}
NEGATIVE_EVIDENCE_STATUSES = {"NOT_APPLICABLE", "ABSENT", "DISABLED"}
UNRESOLVED_EVIDENCE_STATUSES = {
    "AMBIGUOUS", "CONFLICT", "CONFLICTING", "INCOMPLETE", "UNKNOWN", "UNRESOLVED",
}


def _normalized_evidence(entries, *, evidence_type):
    normalized = []
    for entry in entries or []:
        if isinstance(entry, dict):
            row = {str(key): value for key, value in entry.items()}
        else:
            row = {"value": entry}
        row["evidenceType"] = evidence_type
        row["status"] = str(row.get("status") or "UNRESOLVED").strip().upper()
        normalized.append(row)
    return normalized


def _has_status(entries, statuses):
    return any(row["status"] in statuses for row in entries)


def resolve_material_role_applicability(
    *,
    role_code,
    material_evidence=None,
    template_evidence=None,
    configuration_evidence=None,
    appearance_evidence=None,
    process_evidence=None,
    quantity_evidence=None,
    rule_evidence=None,
):
    """Resolve APPLICABLE / NOT_APPLICABLE / UNRESOLVED from explicit evidence.

    Positive precedence is configuration, template, independent Material plus
    quantity, then a governed rule.  Any ambiguity inside those material-bearing
    evidence groups fails closed.  Appearance/process-only evidence can never
    promote a physical material role to APPLICABLE.
    """
    role_code = str(role_code or "").strip().upper()
    buckets = {
        "materialEvidence": _normalized_evidence(
            material_evidence, evidence_type="MATERIAL_IDENTITY",
        ),
        "templateEvidence": _normalized_evidence(
            template_evidence, evidence_type="TEMPLATE_STRUCTURE_ROLE",
        ),
        "configurationEvidence": _normalized_evidence(
            configuration_evidence, evidence_type="ORDER_PRODUCT_CONFIGURATION_ROLE",
        ),
        "appearanceEvidence": _normalized_evidence(
            appearance_evidence, evidence_type="APPEARANCE_ATTRIBUTE",
        ),
        "processEvidence": _normalized_evidence(
            process_evidence, evidence_type="PROCESS_ATTRIBUTE",
        ),
        "quantityEvidence": _normalized_evidence(
            quantity_evidence, evidence_type="MATERIAL_QUANTITY",
        ),
        "ruleEvidence": _normalized_evidence(
            rule_evidence, evidence_type="RELEASED_APPLICABILITY_RULE",
        ),
    }

    explicit_groups = (
        buckets["configurationEvidence"], buckets["templateEvidence"],
        buckets["materialEvidence"], buckets["quantityEvidence"],
        buckets["ruleEvidence"],
    )
    explicit_rows = [row for group in explicit_groups for row in group]
    has_unresolved = _has_status(explicit_rows, UNRESOLVED_EVIDENCE_STATUSES)
    has_explicit_negative = _has_status(explicit_rows, NEGATIVE_EVIDENCE_STATUSES)

    configuration_positive = _has_status(
        buckets["configurationEvidence"], CONFIRMED_EVIDENCE_STATUSES,
    )
    template_positive = _has_status(
        buckets["templateEvidence"], CONFIRMED_EVIDENCE_STATUSES,
    )
    material_positive = _has_status(
        buckets["materialEvidence"], CONFIRMED_EVIDENCE_STATUSES,
    )
    quantity_positive = _has_status(
        buckets["quantityEvidence"], CONFIRMED_EVIDENCE_STATUSES,
    )
    rule_positive = _has_status(
        buckets["ruleEvidence"], CONFIRMED_EVIDENCE_STATUSES,
    )
    material_quantity_positive = material_positive and quantity_positive
    partial_material_identity = material_positive != quantity_positive
    any_positive = (
        configuration_positive or template_positive
        or material_quantity_positive or rule_positive
    )

    if has_unresolved or partial_material_identity:
        status = UNRESOLVED
        reason_code = (
            "INDEPENDENT_MATERIAL_IDENTITY_QUANTITY_INCOMPLETE"
            if partial_material_identity and not has_unresolved
            else "APPLICABILITY_EVIDENCE_UNRESOLVED"
        )
    elif any_positive and has_explicit_negative:
        status = UNRESOLVED
        reason_code = "CONFLICTING_APPLICABILITY_EVIDENCE"
    elif configuration_positive:
        status = APPLICABLE
        reason_code = "EXPLICIT_ORDER_PRODUCT_CONFIGURATION_ROLE"
    elif template_positive:
        status = APPLICABLE
        reason_code = "EXPLICIT_PRODUCT_TEMPLATE_STRUCTURE_ROLE"
    elif material_quantity_positive:
        status = APPLICABLE
        reason_code = "INDEPENDENT_MATERIAL_IDENTITY_AND_QUANTITY"
    elif rule_positive:
        status = APPLICABLE
        reason_code = "RELEASED_APPLICABILITY_RULE"
    else:
        status = NOT_APPLICABLE
        reason_code = (
            "APPEARANCE_PROCESS_ONLY_NO_INDEPENDENT_MATERIAL"
            if buckets["appearanceEvidence"] or buckets["processEvidence"]
            else "NO_INDEPENDENT_MATERIAL_EVIDENCE"
        )

    return {
        "roleCode": role_code,
        "status": status,
        "reasonCode": reason_code,
        "materialRequirementExpected": status == APPLICABLE,
        **buckets,
    }
