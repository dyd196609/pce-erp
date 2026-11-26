"""Evidence-led PAINT_PROCESS applicability and readiness semantics.

Process/routing/capacity facts are deliberately separate from physical
consumable Material Requirements.  Display names and appearance text never
become a material identity or consumption rule.
"""

from __future__ import annotations


APPLICABLE = "APPLICABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNRESOLVED = "UNRESOLVED"
READY = "READY"
INCOMPLETE = "INCOMPLETE"
BLOCKED = "BLOCKED"
DEFERRED = "DEFERRED_TO_LATER_STAGE"

MATERIAL_BOM_GENERATION_STAGE = "MATERIAL_BOM_GENERATION"
CAPACITY_REQUIRED_STAGES = frozenset({
    "ROUTING_VERSION_CONFIRMATION",
    "PRODUCTION_PLANNING",
    "SCHEDULING",
    "CAPACITY_PLANNING",
    "WORK_CENTER_LOADING",
    "MANUFACTURING_EXECUTION",
})

PAINT_MATERIAL_ROLE_CODES = {
    "PAINT_MATERIAL",
    "PAINT_PROCESS_MATERIAL",
    "SURFACE_PROCESS_MATERIAL",
}


def _status(value) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("status") or "").strip().upper()


def resolve_process_applicability(*, process_fact=None, routing_fact=None) -> dict:
    """A formal active process or released route proves process applicability."""
    process_status = _status(process_fact)
    routing_status = _status(routing_fact)
    ambiguous = {"AMBIGUOUS", "CONFLICT", "CONFLICTING", UNRESOLVED}
    if process_status in ambiguous:
        status = UNRESOLVED
        reason = "FORMAL_PROCESS_CONFLICT"
    elif process_status in {"CONFIRMED", "ACTIVE", "RELEASED", READY}:
        status = APPLICABLE
        reason = "FORMAL_PROCESS_EXISTS"
    elif routing_status in ambiguous:
        status = UNRESOLVED
        reason = "FORMAL_ROUTING_PROCESS_EVIDENCE_CONFLICT"
    elif routing_status in {"CONFIRMED", "ACTIVE", "RELEASED", READY}:
        status = APPLICABLE
        reason = "FORMAL_ROUTING_EXISTS"
    else:
        status = NOT_APPLICABLE
        reason = "NO_FORMAL_PROCESS_OR_ROUTING"
    return {
        "status": status,
        "reasonCode": reason,
        "processFact": process_fact or {},
        "routingFact": routing_fact or {},
    }


def resolve_routing_readiness(*, process_status: str, routing_fact=None) -> dict:
    if process_status == NOT_APPLICABLE:
        return {"status": NOT_APPLICABLE, "reasonCode": "PROCESS_NOT_APPLICABLE"}
    if process_status == UNRESOLVED:
        return {"status": UNRESOLVED, "reasonCode": "PROCESS_APPLICABILITY_UNRESOLVED"}
    status = _status(routing_fact)
    operation_count = int((routing_fact or {}).get("operationCount") or 0)
    if status in {"CONFIRMED", "RELEASED", READY} and operation_count > 0:
        return {
            "status": READY,
            "reasonCode": "RELEASED_ROUTING_WITH_OPERATIONS",
            "operationCount": operation_count,
        }
    return {
        "status": INCOMPLETE,
        "reasonCode": "FORMAL_ROUTING_OR_OPERATIONS_MISSING",
        "operationCount": operation_count,
    }


def _capacity_dimensions_complete(fact: dict) -> tuple[bool, list[str]]:
    """Validate persisted capacity dimensions when the fact exposes them.

    The formal routing envelope exposes per-operation dimension counts.  Keep
    this validation independent from workflow-stage policy so an incomplete
    capacity model is never mislabeled READY merely because the current stage
    does not require it.
    """
    dimension_keys = {
        "stepCount", "stepsWithWorkshop", "stepsWithWorkCenter",
        "stepsWithWorkloadDriver", "stepsWithStandardTime",
        "stepsWithReadyCapacityFact", "stepsWithCapacityFact",
        "standardCapacityFactCount", "operationRequirementCount",
    }
    if not dimension_keys.intersection(fact):
        complete = fact.get("complete") is True or _status(fact) == READY
        return complete, [] if complete else ["CAPACITY_FACT"]

    step_count = int(fact.get("stepCount") or 0)
    ready_capacity_steps = int(
        fact.get("stepsWithReadyCapacityFact")
        if fact.get("stepsWithReadyCapacityFact") is not None
        else fact.get("stepsWithCapacityFact") or 0
    )
    checks = {
        "ROUTING_OPERATION": step_count > 0,
        "WORKSHOP": int(fact.get("stepsWithWorkshop") or 0) == step_count,
        "WORK_CENTER": int(fact.get("stepsWithWorkCenter") or 0) == step_count,
        "WORKLOAD_DRIVER": int(fact.get("stepsWithWorkloadDriver") or 0) == step_count,
        "STANDARD_TIME": int(fact.get("stepsWithStandardTime") or 0) == step_count,
        "STANDARD_CAPACITY": (
            ready_capacity_steps == step_count
            and int(fact.get("standardCapacityFactCount") or 0) > 0
        ),
        "OPERATION_REQUIREMENT": int(fact.get("operationRequirementCount") or 0) > 0,
    }
    missing = [code for code, present in checks.items() if not present]
    return not missing, missing


def resolve_capacity_readiness(*, process_status: str, routing_status: str, capacity_fact=None) -> dict:
    if process_status == NOT_APPLICABLE:
        return {"status": NOT_APPLICABLE, "reasonCode": "PROCESS_NOT_APPLICABLE"}
    if process_status == UNRESOLVED or routing_status != READY:
        return {"status": UNRESOLVED, "reasonCode": "PROCESS_ROUTING_NOT_READY"}
    fact = capacity_fact if isinstance(capacity_fact, dict) else {}
    complete, missing_dimensions = _capacity_dimensions_complete(fact)
    if complete:
        return {
            **fact,
            "status": READY,
            "complete": True,
            "reasonCode": "FORMAL_CAPACITY_FACTS_COMPLETE",
            "missingDimensions": [],
        }
    return {
        **fact,
        "status": INCOMPLETE,
        "complete": False,
        "reasonCode": "FORMAL_CAPACITY_FACTS_INCOMPLETE",
        "missingDimensions": missing_dimensions,
    }


def resolve_capacity_stage_gate(
    *, process_status: str, routing_status: str, capacity_readiness=None,
    workflow_stage: str,
) -> dict:
    """Apply capacity responsibility at a workflow stage without hiding debt."""
    stage = str(workflow_stage or "").strip().upper()
    readiness = capacity_readiness if isinstance(capacity_readiness, dict) else {}
    actual_status = _status(readiness)
    capacity_applicable = process_status == APPLICABLE
    required_now = stage in CAPACITY_REQUIRED_STAGES

    base = {
        "workflowStage": stage,
        "capacityRequiredForCurrentStage": required_now,
        "capacityRequiredForLaterManufacturingStage": capacity_applicable,
        "actualCapacityReadiness": actual_status or UNRESOLVED,
        "capacityReadiness": readiness,
    }
    if process_status == NOT_APPLICABLE:
        return {
            **base,
            "status": NOT_APPLICABLE,
            "capacityRequiredForCurrentStage": False,
            "capacityRequiredForLaterManufacturingStage": False,
            "reasonCode": "PROCESS_NOT_APPLICABLE",
        }
    if process_status == UNRESOLVED or routing_status != READY:
        return {
            **base,
            "status": BLOCKED,
            "reasonCode": "PROCESS_ROUTING_NOT_READY",
        }
    if actual_status == READY:
        return {
            **base,
            "status": READY,
            "reasonCode": "FORMAL_CAPACITY_FACTS_COMPLETE",
        }
    if stage == MATERIAL_BOM_GENERATION_STAGE:
        return {
            **base,
            "status": DEFERRED,
            "reasonCode": "CAPACITY_NOT_REQUIRED_FOR_MATERIAL_BOM_GENERATION",
        }
    return {
        **base,
        "status": BLOCKED,
        "capacityRequiredForCurrentStage": True,
        "reasonCode": "CAPACITY_FACTS_REQUIRED_FOR_WORKFLOW_STAGE",
    }


def resolve_paint_material_applicability(
    *, material_evidence=None, recipe_evidence=None, consumption_evidence=None,
) -> dict:
    """Resolve a physical paint consumable without interpreting process names.

    A complete positive fact needs all three independent dimensions: Material
    identity, a formal recipe/rule, and a quantity/UOM basis.  No evidence is
    ``NOT_APPLICABLE`` at this closure stage; partial/conflicting evidence is
    ``UNRESOLVED`` and blocks.
    """
    materials = list(material_evidence or [])
    recipes = list(recipe_evidence or [])
    consumption = list(consumption_evidence or [])
    all_rows = materials + recipes + consumption
    ambiguous = {
        "AMBIGUOUS", "CONFLICT", "CONFLICTING", "PARTIAL", "MISSING", UNRESOLVED,
    }
    if any(_status(row) in ambiguous for row in all_rows):
        status = UNRESOLVED
        reason = "PAINT_MATERIAL_RECIPE_OR_CONSUMPTION_CONFLICT"
    elif not all_rows:
        status = NOT_APPLICABLE
        reason = "NO_FORMAL_PAINT_MATERIAL_RECIPE"
    else:
        material_ready = any(
            _status(row) in {"CONFIRMED", READY}
            and (row.get("materialId") or row.get("materialCode"))
            for row in materials if isinstance(row, dict)
        )
        recipe_ready = any(
            _status(row) in {"CONFIRMED", READY}
            and (row.get("recipeId") or row.get("ruleId") or row.get("requirementId"))
            for row in recipes if isinstance(row, dict)
        )
        consumption_ready = any(
            _status(row) in {"CONFIRMED", READY}
            and (row.get("quantity") or row.get("formula") or row.get("quantityBasis"))
            and (row.get("uomId") or row.get("uomCode"))
            for row in consumption if isinstance(row, dict)
        )
        if material_ready and recipe_ready and consumption_ready:
            status = APPLICABLE
            reason = "FORMAL_MATERIAL_RECIPE_AND_CONSUMPTION_COMPLETE"
        else:
            status = UNRESOLVED
            reason = "PAINT_MATERIAL_RECIPE_OR_CONSUMPTION_INCOMPLETE"
    return {
        "status": status,
        "reasonCode": reason,
        "materialEvidence": materials,
        "recipeEvidence": recipes,
        "consumptionEvidence": consumption,
    }
