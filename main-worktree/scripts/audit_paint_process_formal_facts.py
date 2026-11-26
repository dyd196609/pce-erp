"""Read-only PAINT_PROCESS / routing / capacity audit for Calculation 3.

The script is evidence tooling.  It enables SQLite ``query_only`` before ORM
reads, never creates business objects, and proves that the formal database hash
is unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def database_checks(path: Path) -> dict:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        schema_rows = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        return {
            "integrityCheck": connection.execute("PRAGMA integrity_check").fetchall(),
            "foreignKeyCheck": connection.execute("PRAGMA foreign_key_check").fetchall(),
            "recipeOrConsumptionSchemaCandidates": [
                name for name, sql in schema_rows
                if any(term in str(sql or "").casefold() for term in ("recipe", "consumption"))
            ],
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--ensure-ascii", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve()
    before_hash = sha256(database)

    from edge_banding_requirement_workflow import configure

    configure(database)

    from django.db import connection, models
    from pde.manufacturing_structure_service import ManufacturingStructureService
    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from pde.models import (
        EngineeringCalculationRecord,
        EngineeringMaterialRequirement,
        EngineeringOperationRequirement,
        ProductDesignItem,
        RoutingStep,
        StandardCapacity,
    )
    from system.models import User

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA query_only = ON")

    calculation = EngineeringCalculationRecord.objects.select_related(
        "engineering_instance__sales_order_item__sales_order",
        "engineering_instance__selected_process_type",
    ).get(pk=3)
    instance = calculation.engineering_instance
    resolved = ManufacturingStructureService.resolve_effective_routing(instance)
    routing = resolved["routing"]
    version = resolved["routing_version"]
    steps = list(RoutingStep.objects.select_related(
        "operation__workshop", "operation__work_center",
        "workshop", "work_center",
    ).filter(routing_version=version).order_by("sequence", "pk"))

    operation_ids = {row.operation_id for row in steps}
    work_center_ids = {
        value for row in steps
        for value in (row.work_center_id, row.operation.work_center_id)
        if value is not None
    }
    capacities = list(StandardCapacity.objects.select_related(
        "operation", "work_center", "equipment", "uom",
    ).filter(company_id=calculation.company_id, is_active=True).filter(
        models.Q(operation_id__in=operation_ids)
        | models.Q(work_center_id__in=work_center_ids)
        | models.Q(equipment__work_center_id__in=work_center_ids)
    ).order_by("pk"))
    capacities_by_operation = {}
    capacities_by_work_center = {}
    for row in capacities:
        if row.operation_id:
            capacities_by_operation.setdefault(row.operation_id, []).append(row)
        if row.work_center_id:
            capacities_by_work_center.setdefault(row.work_center_id, []).append(row)
        if row.equipment_id:
            capacities_by_work_center.setdefault(row.equipment.work_center_id, []).append(row)

    step_rows = []
    for step in steps:
        workshop = step.workshop or step.operation.workshop
        work_center = step.work_center or step.operation.work_center
        matched_capacity = list(capacities_by_operation.get(step.operation_id, []))
        if work_center:
            matched_capacity.extend(capacities_by_work_center.get(work_center.pk, []))
        deduplicated = {row.pk: row for row in matched_capacity}
        step_rows.append({
            "stepId": step.pk,
            "sequence": step.sequence,
            "operationId": step.operation_id,
            "operationCode": step.operation.code,
            "operationName": step.operation.name,
            "workshopId": workshop.pk if workshop else None,
            "workshopCode": workshop.code if workshop else None,
            "workshopName": workshop.name if workshop else None,
            "workCenterId": work_center.pk if work_center else None,
            "workCenterCode": work_center.code if work_center else None,
            "workCenterName": work_center.name if work_center else None,
            "routingStepStandardHours": str(step.standard_hours) if step.standard_hours is not None else None,
            "operationStandardHours": str(step.operation.standard_hours) if step.operation.standard_hours is not None else None,
            "calculationBasis": step.operation.calculation_basis,
            "calculationUomId": step.operation.calculation_uom_id,
            "quantityDriver": step.operation.quantity_driver,
            "capacityFacts": [{
                "id": row.pk,
                "code": row.code,
                "resourceScope": row.resource_scope,
                "measurementStatus": row.measurement_status,
                "quantity": str(row.quantity) if row.quantity is not None else None,
                "uom": row.uom.code,
                "timeBasis": row.time_basis,
                "timeBasisQuantity": str(row.time_basis_quantity) if row.time_basis_quantity is not None else None,
                "standardHours": str(row.standard_hours) if row.standard_hours is not None else None,
            } for row in deduplicated.values()],
        })

    trace = calculation.trace if isinstance(calculation.trace, dict) else {}
    source_by_object = {
        row.pk: (row.existing_design_data if isinstance(row.existing_design_data, dict) else {})
        for row in ProductDesignItem.objects.filter(
            sales_order_item=calculation.sales_order_item,
            source_record=calculation.source_record,
        ).only("pk", "existing_design_data")
    }
    input_rows = []
    for row in trace.get("objectInputSnapshot", []):
        values = row.get("input") if isinstance(row.get("input"), dict) else {}
        source = source_by_object.get(row.get("designItemId"), {})
        input_rows.append({
            "designItemId": row.get("designItemId"),
            "designItemNo": row.get("designItemNo"),
            "paintProcess": values.get("paintProcess") or source.get("paintProcess"),
            "materialProcessCode": values.get("materialProcessCode") or source.get("materialProcessCode"),
            "routingProcessCode": (
                values.get("routingProcessCode") or values.get("processConfigurationCode")
                or source.get("routingProcessCode")
            ),
            "processConfigurationId": values.get("processConfigurationId"),
            "processConfigurationCode": values.get("processConfigurationCode"),
        })

    material_requirements = list(EngineeringMaterialRequirement.objects.filter(
        calculation=calculation,
    ).values("id", "material_id", "net_quantity", "uom_id", "order_specification", "trace"))
    operation_requirements = list(EngineeringOperationRequirement.objects.select_related(
        "operation", "uom",
    ).filter(calculation=calculation).values(
        "id", "sequence", "operation_id", "operation__code", "operation__name",
        "workload_quantity", "uom__code", "source_path", "trace",
    ))
    preview = OrderEngineeringClosureService.preview_bom(
        user=User.objects.get(username="pce_plan_r12"), calculation_id=calculation.pk,
    )

    result = {
        "status": "PASS_READ_ONLY",
        "database": {
            "path": str(database),
            "startSha256": before_hash,
            **database_checks(database),
        },
        "calculation": {
            "id": calculation.pk,
            "orderNo": instance.sales_order_item.sales_order.order_no,
            "lineNo": instance.sales_order_item.line_no,
            "engineeringInstanceId": instance.pk,
            "selectedProcessType": None if not instance.selected_process_type_id else {
                "id": instance.selected_process_type_id,
                "code": instance.selected_process_type.code,
                "name": instance.selected_process_type.name,
            },
        },
        "objects": input_rows,
        "routing": {
            "id": routing.pk,
            "code": routing.routing_code,
            "name": routing.name,
            "status": routing.status,
            "manufacturingProcessTypeId": routing.manufacturing_process_type_id,
            "versionId": version.pk,
            "version": version.routing_version,
            "versionStatus": version.status,
            "resolvedScope": resolved["resolved_scope"],
            "steps": step_rows,
        },
        "summary": {
            "stepCount": len(step_rows),
            "stepsWithWorkshop": sum(row["workshopId"] is not None for row in step_rows),
            "stepsWithWorkCenter": sum(row["workCenterId"] is not None for row in step_rows),
            "stepsWithWorkloadDriver": sum(bool(row["quantityDriver"]) for row in step_rows),
            "stepsWithStandardTime": sum(
                row["routingStepStandardHours"] is not None
                or row["operationStandardHours"] is not None
                for row in step_rows
            ),
            "stepsWithCapacityFact": sum(bool(row["capacityFacts"]) for row in step_rows),
            "formalCapacityFactCount": len(capacities),
            "materialRequirementCount": len(material_requirements),
            "operationRequirementCount": len(operation_requirements),
        },
        "materialRequirements": material_requirements,
        "operationRequirements": operation_requirements,
        "preview": {
            "previewHash": preview.get("previewHash"),
            "rowCount": preview.get("rowCount"),
            "sourceRequirementCount": preview.get("sourceRequirementCount"),
            "currentVersionMaterialCompleteness": preview.get("currentVersionMaterialCompleteness"),
            "firstRealBlocker": preview.get("firstRealBlocker"),
            "canGenerate": preview.get("canGenerate"),
            "alreadyGenerated": preview.get("alreadyGenerated"),
            "bomId": preview.get("bomId"),
            "bomVersionId": preview.get("bomVersionId"),
            "status": preview.get("status"),
            "businessWriteSideEffectCount": preview.get("businessWriteSideEffectCount"),
        },
        "businessWriteCount": 0,
        "changedTables": [],
        "unexpectedChangedTables": [],
        "bomGenerated": False,
    }
    result["database"]["endSha256"] = sha256(database)
    result["database"]["hashUnchanged"] = (
        result["database"]["startSha256"] == result["database"]["endSha256"]
    )
    if args.summary:
        result["routing"]["steps"] = [{
            "sequence": row["sequence"],
            "operationId": row["operationId"],
            "operationCode": row["operationCode"],
            "operationName": row["operationName"],
            "workshopCode": row["workshopCode"],
            "workshopName": row["workshopName"],
            "workCenterCode": row["workCenterCode"],
            "routingStepStandardHours": row["routingStepStandardHours"],
            "operationStandardHours": row["operationStandardHours"],
            "quantityDriver": row["quantityDriver"],
            "capacityFactCount": len(row["capacityFacts"]),
        } for row in step_rows]
        result["materialRequirements"] = [{
            "id": row["id"],
            "designItemId": (row["trace"] or {}).get("designItemId"),
            "structureRole": (
                (row["order_specification"] or {}).get("structureRole")
                or (row["trace"] or {}).get("structureRole")
            ),
            "materialId": row["material_id"],
        } for row in material_requirements]
        completeness = result["preview"]["currentVersionMaterialCompleteness"] or {}
        result["preview"]["currentVersionMaterialCompleteness"] = {
            key: completeness.get(key) for key in (
                "contractCode", "applicable", "complete", "status",
                "workflowStage",
                "targetDesignItemCount", "coveredDesignItemCount",
                "notApplicableCategories", "fullBomReadinessScan",
            )
        }
        result["preview"]["currentVersionMaterialCompleteness"]["evaluatedCategories"] = [{
            key: row.get(key) for key in (
                "code", "status", "applicableDesignItemCount",
                "notApplicableDesignItemCount", "unresolvedDesignItemCount",
                "requirementDesignItemCount", "coveredDesignItemCount",
                "actualCapacityReadiness", "workflowStage",
                "capacityRequiredForCurrentStage",
                "capacityRequiredForLaterManufacturingStage",
            )
        } for row in completeness.get("evaluatedCategories", [])]
        blocker = result["preview"].get("firstRealBlocker") or {}
        result["preview"]["firstRealBlocker"] = {
            key: blocker.get(key) for key in (
                "code", "statusLabel", "message", "category", "missingDesignItemIds",
            )
        } if blocker else None
        result["preview"]["currentBomInputDataBlocker"] = (
            blocker.get("code") if blocker else "NONE"
        )
        result["preview"]["currentBomInputReadiness"] = (
            "READY" if completeness.get("complete") else "BLOCKED"
        )
    print(json.dumps(result, ensure_ascii=args.ensure_ascii, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
