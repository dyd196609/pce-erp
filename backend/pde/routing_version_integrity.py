"""Stable content identity for formal RoutingVersion review and release.

Lifecycle status, approval projection and timestamps are deliberately excluded:
they change as the same immutable version moves through review and release.  The
snapshot contains the version business identity, every governed step field and
the exact applicability/readiness projection used by formal review.
"""

from __future__ import annotations

from hashlib import sha256
import json


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def content_hash(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def review_fact_snapshot(completeness):
    """Keep only deterministic review facts needed to detect invalidation."""

    completeness = completeness if isinstance(completeness, dict) else {}
    rows = completeness.get("applicabilityRows") or []
    return {
        "complete": bool(completeness.get("complete")),
        "stepCount": completeness.get("stepCount"),
        "contextCount": completeness.get("contextCount"),
        "sourceRoutingVersionId": completeness.get("sourceRoutingVersionId"),
        "applicabilityRows": [
            {
                "stepId": row.get("stepId"),
                "sequence": row.get("sequence"),
                "operationCode": row.get("operationCode"),
                "mode": row.get("mode"),
                "result": row.get("result"),
                "formalApplicabilityValidated": row.get("formalApplicabilityValidated"),
                "manualDecision": row.get("manualDecision"),
                "manualDecisionAuditId": row.get("manualDecisionAuditId"),
            }
            for row in rows
        ],
    }


def routing_version_content_snapshot(version, completeness):
    steps = version.steps.select_related(
        "operation", "workshop", "work_center", "applies_to_item",
    ).order_by("sequence", "pk")
    snapshot = {
        "routingVersion": {
            "id": version.pk,
            "routingId": version.routing_id,
            "productId": version.product_id,
            "productVersionId": version.product_version_id,
            "routingVersionNo": version.routing_version,
            "revision": version.revision,
            "effectiveDate": version.effective_date.isoformat() if version.effective_date else None,
            "expireDate": version.expire_date.isoformat() if version.expire_date else None,
            "applicability": version.applicability,
        },
        "steps": [
            {
                "id": step.pk,
                "sequence": step.sequence,
                "operationId": step.operation_id,
                "workshopId": step.workshop_id,
                "workCenterId": step.work_center_id,
                "appliesToItemId": step.applies_to_item_id,
                "standardHours": step.standard_hours,
                "setupHours": step.setup_hours,
                "transferHours": step.transfer_hours,
                "qualityCheckpoint": step.quality_checkpoint,
                "instruction": step.instruction,
                "operationParameters": step.operation_parameters,
                "predecessorSequences": step.predecessor_sequences,
                "effectiveTransitionMode": step.effective_transition_mode,
                "resourceSelectionRule": step.resource_selection_rule,
                "active": step.is_active,
            }
            for step in steps
        ],
        "reviewFacts": review_fact_snapshot(completeness),
    }
    # Use the exact existing canonical representation for both persistence
    # and hashing. Decimal hours must not break the native review audit save;
    # canonical content hashes remain byte-for-byte unchanged.
    return json.loads(_canonical(snapshot))


__all__ = [
    "content_hash",
    "review_fact_snapshot",
    "routing_version_content_snapshot",
]
