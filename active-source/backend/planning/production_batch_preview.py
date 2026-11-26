"""Production-batch and transition-policy preview domain.

This module is deliberately persistence-free.  It defines the contract and
the deterministic V1 preview rules without enabling production planning or
writing any planning/master-data rows.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Iterable


class DataProvenance(str, Enum):
    REAL = "REAL"
    SIMULATED_FOR_TEST = "SIMULATED_FOR_TEST"
    SYSTEM_DERIVED = "SYSTEM_DERIVED"
    UNKNOWN = "UNKNOWN"


class TransitionMode(str, Enum):
    GENERAL = "GENERAL"
    KITTING = "KITTING"


PRODUCTION_BATCH_SCHEMA = {
    "persistenceStatus": "SCHEMA_CONTRACT_ONLY_NOT_DEPLOYED",
    "productionEnabled": False,
    "productionBatch": [
        "company", "batch_no", "sales_order", "status",
        "planned_quantity", "planned_release_date",
        "required_completion_date", "source", "created_by", "created_at",
    ],
    "productionBatchItem": [
        "production_batch", "sales_order_item", "product_definition",
        "product_version", "manufacturing_output", "allocated_quantity",
        "uom", "source_sales_order_id", "source_sales_order_item_id",
    ],
    "downstreamRequiredLineage": [
        "production_batch_id", "production_batch_no", "sales_order_id",
        "sales_order_item_id",
    ],
    "constraints": [
        "One ProductionBatch belongs to exactly one SalesOrder",
        "One SalesOrder may be split into multiple ProductionBatch rows",
        "A SalesOrderItem may be allocated across batches",
        "Cumulative allocation may not exceed order demand without an explicit override explanation",
    ],
}


def resolve_transition_mode(operation_default, routing_step_override=None):
    """Resolve mode from configured values only; names/codes are never inspected."""
    configured = routing_step_override or operation_default
    try:
        return TransitionMode(configured)
    except (TypeError, ValueError) as exc:
        raise ValueError("GENERAL/KITTING 转序方式必须由正式配置明确提供") from exc


def validate_batch_allocations(order_demands, batches):
    """Validate Order -> Batch -> Batch Item quantity and lineage rules."""
    demand = {str(key): Decimal(str(value)) for key, value in order_demands.items()}
    allocated = {key: Decimal("0") for key in demand}
    errors = []
    seen_batches = set()
    for batch in batches:
        batch_no = str(batch.get("batchNo") or "").strip()
        order_id = str(batch.get("salesOrderId") or "").strip()
        if not batch_no or batch_no in seen_batches:
            errors.append({"code": "BATCH_NO_INVALID", "batchNo": batch_no})
        seen_batches.add(batch_no)
        item_order_ids = {str(item.get("salesOrderId") or order_id) for item in batch.get("items", [])}
        if len(item_order_ids) != 1 or (item_order_ids and order_id not in item_order_ids):
            errors.append({"code": "CROSS_ORDER_BATCH_NOT_ALLOWED", "batchNo": batch_no})
        for item in batch.get("items", []):
            item_id = str(item.get("salesOrderItemId") or "")
            quantity = Decimal(str(item.get("allocatedQuantity") or "0"))
            if item_id not in demand:
                errors.append({"code": "ORDER_ITEM_NOT_FOUND", "batchNo": batch_no, "salesOrderItemId": item_id})
                continue
            if quantity <= 0:
                errors.append({"code": "ALLOCATION_MUST_BE_POSITIVE", "batchNo": batch_no, "salesOrderItemId": item_id})
                continue
            allocated[item_id] += quantity
            if allocated[item_id] > demand[item_id] and not str(item.get("overAllocationExplanation") or "").strip():
                errors.append({
                    "code": "UNEXPLAINED_OVER_ALLOCATION", "batchNo": batch_no,
                    "salesOrderItemId": item_id, "demandQuantity": str(demand[item_id]),
                    "allocatedQuantity": str(allocated[item_id]),
                })
    return {
        "valid": not errors,
        "errors": errors,
        "items": [{
            "salesOrderItemId": item_id,
            "demandQuantity": str(demand_qty),
            "allocatedQuantity": str(allocated[item_id]),
            "remainingQuantity": str(demand_qty - allocated[item_id]),
        } for item_id, demand_qty in demand.items()],
    }


@dataclass(frozen=True)
class MemberInput:
    member_id: str
    quantity: Decimal
    capacity_per_hour: Decimal | None
    earliest_start: datetime
    daily_working_hours: Decimal | None
    staffing_factor: Decimal | None = Decimal("1")
    participates_in_step: bool = True


def _calculate_member(member: MemberInput):
    missing = []
    if member.capacity_per_hour is None or member.capacity_per_hour <= 0:
        missing.append("STANDARD_CAPACITY")
    if member.daily_working_hours is None or member.daily_working_hours <= 0:
        missing.append("WORKING_CALENDAR")
    if member.staffing_factor is None or member.staffing_factor <= 0:
        missing.append("STAFFING")
    if missing:
        return None, missing
    duration_hours = member.quantity / (member.capacity_per_hour * member.staffing_factor)
    # V1 preview is intentionally non-APS.  Calendar presence is a hard gate;
    # detailed breaks/holidays/resource contention are future production work.
    completion = member.earliest_start + timedelta(hours=float(duration_hours))
    return {
        "memberId": member.member_id,
        "quantity": str(member.quantity),
        "durationHours": str(duration_hours.normalize()),
        "earliestStartTime": member.earliest_start.isoformat(),
        "calculatedCompletionTime": completion.isoformat(),
        "nextEarliestStartTime": completion.isoformat(),
        "dataProvenance": DataProvenance.SYSTEM_DERIVED.value,
    }, []


def preview_transition(*, production_batch_no, operation_code, operation_default,
                       routing_step_override, members: Iterable[MemberInput],
                       required_member_ids=None):
    mode = resolve_transition_mode(operation_default, routing_step_override)
    supplied = {member.member_id: member for member in members if member.participates_in_step}
    required = list(required_member_ids) if required_member_ids is not None else list(supplied)
    absent = [member_id for member_id in required if member_id not in supplied]
    rows = []
    missing_data = []
    for member_id in required:
        member = supplied.get(member_id)
        if member is None:
            continue
        result, missing = _calculate_member(member)
        if missing:
            missing_data.extend(f"{member_id}:{field}" for field in missing)
        else:
            rows.append(result)
    if absent:
        missing_data.extend(f"{member_id}:REQUIRED_MEMBER" for member_id in absent)
    if missing_data:
        return {
            "productionBatchNo": production_batch_no,
            "operationCode": operation_code,
            "effectiveTransitionMode": mode.value,
            "planningStatus": "PLANNING_BLOCKED",
            "missingRequiredData": missing_data,
            "members": rows,
            "kittingStatus": "WAITING_FOR_KITTING" if mode is TransitionMode.KITTING else "NOT_APPLICABLE",
            "blockReason": "必需齐套成员或真实产能/日历/人员配置不完整；未生成推测日期。",
        }

    if mode is TransitionMode.GENERAL:
        return {
            "productionBatchNo": production_batch_no,
            "operationCode": operation_code,
            "effectiveTransitionMode": mode.value,
            "planningStatus": "PREVIEW_READY",
            "members": rows,
            "kittingStatus": "NOT_APPLICABLE",
            "batchKittingCompletionTime": None,
            "requiredCount": len(rows), "completedCount": len(rows), "missingCount": 0,
        }

    slowest = max(rows, key=lambda row: row["calculatedCompletionTime"])
    gate_time = slowest["calculatedCompletionTime"]
    gated_rows = [{**row, "nextEarliestStartTime": gate_time} for row in rows]
    return {
        "productionBatchNo": production_batch_no,
        "operationCode": operation_code,
        "effectiveTransitionMode": mode.value,
        "planningStatus": "PREVIEW_READY",
        "members": gated_rows,
        "kittingStatus": "READY",
        "requiredCount": len(required), "completedCount": len(rows), "missingCount": 0,
        "slowestMember": slowest["memberId"],
        "slowestCompletionTime": gate_time,
        "batchKittingCompletionTime": gate_time,
        "missingProductOrComponent": [],
        "blockingOperation": None,
        "blockReason": "",
    }


def build_foundation_preview():
    start = datetime.fromisoformat("2026-09-08T08:00:00")
    members = [
        MemberInput("A", Decimal("8"), Decimal("8"), start, Decimal("8")),
        MemberInput("B", Decimal("16"), Decimal("8"), start, Decimal("8")),
        MemberInput("C", Decimal("24"), Decimal("8"), start, Decimal("8")),
        MemberInput("D-NOT-IN-SCOPE", Decimal("99"), Decimal("1"), start, Decimal("8"), participates_in_step=False),
    ]
    general = preview_transition(
        production_batch_no="B001", operation_code="OP-CONFIGURED",
        operation_default="GENERAL", routing_step_override=None,
        members=members, required_member_ids=["A", "B", "C"],
    )
    kitting = preview_transition(
        production_batch_no="B001", operation_code="OP-CONFIGURED",
        operation_default="GENERAL", routing_step_override="KITTING",
        members=members, required_member_ids=["A", "B", "C"],
    )
    blocked = preview_transition(
        production_batch_no="B-BLOCKED", operation_code="OP-MISSING-DATA",
        operation_default="KITTING", routing_step_override=None,
        members=[MemberInput("A", Decimal("8"), None, start, None)],
        required_member_ids=["A", "B"],
    )
    allocations = validate_batch_allocations(
        {"SOI-1": "100"},
        [
            {"batchNo": "B001", "salesOrderId": "SO-1", "items": [{"salesOrderItemId": "SOI-1", "allocatedQuantity": "30"}]},
            {"batchNo": "B002", "salesOrderId": "SO-1", "items": [{"salesOrderItemId": "SOI-1", "allocatedQuantity": "30"}]},
            {"batchNo": "B003", "salesOrderId": "SO-1", "items": [{"salesOrderItemId": "SOI-1", "allocatedQuantity": "40"}]},
        ],
    )
    return {
        "previewOnly": True,
        "productionEnabled": False,
        "planningMigration0005AppliedByThisFeature": False,
        "productionBusinessWriteCount": 0,
        "schema": PRODUCTION_BATCH_SCHEMA,
        "allocationPreview": allocations,
        "generalPreview": general,
        "kittingPreview": kitting,
        "blockedPreview": blocked,
        "configurationAuthority": "RoutingStep override → Operation default; no name/code inference",
    }
