from decimal import Decimal


EFFECTIVE_PLAN_STATUSES = frozenset({"confirmed", "released"})


def _decimal(value, default=Decimal("0")):
    if value is None or value == "":
        return default
    return Decimal(str(value))


def _recorded_plan_quantity(plan):
    if plan is None:
        return Decimal("0")
    if hasattr(plan, "net_required_qty"):
        return _decimal(plan.net_required_qty)
    return _decimal(getattr(plan, "planned_qty", 0))


def planning_quantity_facts(*, demand_qty, requirement=None, plan=None):
    """Build the single server-side quantity interpretation used by Sales/Planning.

    PlanningRequirement.available_qty is a stored aggregate inventory snapshot.  It
    is not an order allocation.  Only an explicit allocation fact may be described
    as effective inventory coverage for one demand.
    """

    demand = _decimal(demand_qty)
    if requirement is None:
        return {
            "orderDemandQty": str(demand),
            "inventorySnapshotQty": None,
            "inventorySnapshotSource": None,
            "inventoryAllocationStatus": "NOT_CALCULATED",
            "inventoryAllocationProofStatus": "NOT_CALCULATED",
            "effectiveInventoryCoverageQty": None,
            "netRequiredQty": None,
            "recordedPlanQty": str(_recorded_plan_quantity(plan)),
            "effectivePlanQty": "0",
            "pendingNetPlanQty": None,
            "uncoveredDemandQty": None,
            "overPlannedQty": "0",
            "netRequirementPlanCoverageStatus": "NOT_CALCULATED",
            "orderCoverageStatus": "NOT_CALCULATED",
        }

    calculation = requirement.calculation_facts if isinstance(requirement.calculation_facts, dict) else {}
    snapshot = _decimal(requirement.available_qty)
    net_required = _decimal(requirement.net_required_qty)
    recorded_plan = _recorded_plan_quantity(plan)
    effective_plan = recorded_plan if plan and plan.status in EFFECTIVE_PLAN_STATUSES else Decimal("0")
    pending_net = max(net_required - effective_plan, Decimal("0"))
    over_planned = max(effective_plan - net_required, Decimal("0"))

    # calculation_facts records the net-requirement calculation, not a native
    # stock allocation. No order-line/lot allocation and release authority is
    # persisted by that calculation. Preserve legacy assertions for diagnosis,
    # but never promote their status/quantity to an effective coverage proof.
    asserted_status = str(calculation.get("inventoryAllocationStatus") or "UNALLOCATED_SNAPSHOT")
    allocation_status = "ALLOCATION_PROOF_UNVERIFIED" if asserted_status == "ALLOCATED" else asserted_status
    allocated = None
    uncovered = None if allocated is None else max(demand - allocated - effective_plan, Decimal("0"))

    if over_planned > 0:
        plan_coverage = "OVER_PLANNED"
    elif pending_net == 0:
        plan_coverage = "NET_REQUIREMENT_FULLY_PLANNED"
    else:
        plan_coverage = "NET_REQUIREMENT_PENDING_PLAN"

    return {
        "orderDemandQty": str(demand),
        "inventorySnapshotQty": str(snapshot),
        "inventorySnapshotSource": calculation.get("inventorySource") or "procurement.InventoryBalance",
        "inventorySnapshotCapturedAt": calculation.get("inventorySnapshotCapturedAt"),
        "inventoryAllocationStatus": allocation_status,
        "inventoryAllocationProofStatus": "UNPROVEN" if asserted_status == "ALLOCATED" else "NOT_CHECKED",
        "inventoryAllocationAuthority": "Planning calculation snapshot only; current order-line coverage is supplied by native M09 supplyCoverage",
        "effectiveInventoryCoverageQty": str(allocated) if allocated is not None else None,
        "netRequiredQty": str(net_required),
        "netRequirementCalculatedAt": calculation.get("calculatedAt"),
        "recordedPlanQty": str(recorded_plan),
        "effectivePlanQty": str(effective_plan),
        "effectivePlanStatus": plan.status if plan and plan.status in EFFECTIVE_PLAN_STATUSES else None,
        "pendingNetPlanQty": str(pending_net),
        "uncoveredDemandQty": str(uncovered) if uncovered is not None else None,
        "overPlannedQty": str(over_planned),
        "netRequirementPlanCoverageStatus": plan_coverage,
        "orderCoverageStatus": (
            "FULLY_COVERED" if uncovered == 0
            else "UNCOVERED" if uncovered is not None
            else "INVENTORY_ALLOCATION_UNCONFIRMED"
        ),
    }
