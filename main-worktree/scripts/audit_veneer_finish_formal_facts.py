"""Read-only VENEER_FINISH fact and applicability audit for Calculation 3.

The audit deliberately enables SQLite ``query_only`` before ORM reads.  It is
evidence tooling only: it never creates Material, Mapping, Requirement, or BOM
records and it verifies that the formal database file hash is unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def database_checks(path: Path) -> dict:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return {
            "integrityCheck": connection.execute("PRAGMA integrity_check").fetchall(),
            "foreignKeyCheck": connection.execute("PRAGMA foreign_key_check").fetchall(),
        }
    finally:
        connection.close()


def relevant_values(value, *, path: str = "") -> dict:
    """Return only Material/appearance/process-related source values."""
    keywords = (
        "material", "specification", "finish", "color", "veneer", "surface",
        "paint", "process", "routing", "lc-m045", "清水", "柚木", "饰面", "木皮",
    )
    rows = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if any(token in str(key).casefold() for token in keywords):
                rows[child_path] = child
            elif isinstance(child, (dict, list)):
                rows.update(relevant_values(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.update(relevant_values(child, path=f"{path}[{index}]"))
    elif any(token in str(value).casefold() for token in keywords):
        rows[path] = value
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument(
        "--ensure-ascii", action="store_true",
        help="Escape non-ASCII characters for terminals with a legacy code page.",
    )
    parser.add_argument(
        "--compact", action="store_true",
        help="Emit the decision-grade subset used by the consolidated report.",
    )
    parser.add_argument(
        "--decision", action="store_true",
        help="Emit only the final applicability/closure and zero-write evidence.",
    )
    args = parser.parse_args()
    database = args.database.resolve()
    if not database.is_file():
        raise RuntimeError("DATABASE_NOT_FOUND")

    start_sha = sha256(database)

    # Reuse the existing acceptance isolation/bootstrap contract.
    from edge_banding_requirement_workflow import (
        MATERIAL_ACTOR,
        REQUIREMENT_ACTOR,
        actor_preflight,
        configure,
    )

    configure(database)

    from django.db import connection
    from masterdata.models import Material
    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from pde.models import (
        BOMCompletenessRule,
        EngineeringCalculationRecord,
        EngineeringDerivedFact,
        EngineeringMaterialRequirement,
        OrderConfiguredProduct,
        ProductDesignItem,
        ProductTemplateStructureNode,
        StructureRole,
    )
    from system.models import User

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA query_only = ON")

    calculation = EngineeringCalculationRecord.objects.select_related(
        "company", "sales_order_item__sales_order", "engineering_instance", "source_record",
    ).get(pk=3)
    if calculation.sales_order_item.sales_order.order_no != "SO202609180003":
        raise RuntimeError("CALCULATION_ORDER_MISMATCH")
    if calculation.sales_order_item.line_no != 1:
        raise RuntimeError("CALCULATION_LINE_MISMATCH")

    trace = calculation.trace if isinstance(calculation.trace, dict) else {}
    input_snapshots = {
        int(row["designItemId"]): row
        for row in trace.get("objectInputSnapshot", [])
        if row.get("designItemId") is not None
    }
    result_snapshots = trace.get("resultSnapshot", [])
    facts_by_item = {}
    for row in result_snapshots:
        design_item_id = row.get("designItemId")
        if design_item_id is None:
            continue
        facts_by_item.setdefault(int(design_item_id), []).append({
            "canonicalField": row.get("canonicalField"),
            "outputName": row.get("outputName"),
            "value": row.get("value"),
            "uom": row.get("uom"),
            "sourceDetailId": row.get("sourceDetailId"),
            "sourcePath": row.get("sourcePath"),
        })

    requirements = list(
        EngineeringMaterialRequirement.objects.select_related(
            "material__category", "material__base_uom", "uom", "source_detail",
        ).filter(calculation=calculation).order_by("pk")
    )
    requirement_roles = Counter()
    requirement_rows = []
    for row in requirements:
        specification = row.order_specification if isinstance(row.order_specification, dict) else {}
        row_trace = row.trace if isinstance(row.trace, dict) else {}
        role = str(specification.get("structureRole") or row_trace.get("structureRole") or "").upper()
        requirement_roles[role or "UNSPECIFIED"] += 1
        requirement_rows.append({
            "id": row.pk,
            "designItemId": row_trace.get("designItemId"),
            "designItemNo": row_trace.get("designItemNo"),
            "role": role,
            "materialId": row.material_id,
            "materialCode": row.material.code,
            "materialName": row.material.name,
            "quantity": str(row.gross_quantity or row.net_quantity),
            "uom": row.uom.code,
            "sourceDetailId": row.source_detail_id,
        })

    items = ProductDesignItem.objects.select_related(
        "source_record", "source_attribute", "product_category",
    ).filter(
        sales_order_item=calculation.sales_order_item,
        source_record=calculation.source_record,
    ).order_by("pk")
    object_rows = []
    for item in items:
        revision = item.design_revisions.select_related(
            "material__category", "material__base_uom", "material_process_type",
            "paint_process_type", "edge_method", "created_by",
        ).order_by("-revision", "-pk").first()
        snapshot = input_snapshots.get(item.pk) or {}
        snapshot_input = snapshot.get("input") if isinstance(snapshot.get("input"), dict) else {}
        item_requirements = [row for row in requirement_rows if row["designItemId"] == item.pk]
        related_facts = facts_by_item.get(item.pk, [])
        object_rows.append({
            "designItemId": item.pk,
            "designObject": item.item_no,
            "designItemName": item.item_name,
            "designDataNature": item.design_data_nature,
            "productCategory": {
                "id": item.product_category_id,
                "code": item.product_category.code if item.product_category_id else None,
                "name": item.product_category.name if item.product_category_id else None,
            },
            "productDefinitionId": item.product_definition_id,
            "physicalQuantity": str(item.physical_quantity),
            "sourceRecord": {
                "id": item.source_record_id,
                "sourceNo": item.source_record.source_no,
                "sourceVersion": item.source_record.source_version,
            },
            "sourceAttribute": {
                "id": item.source_attribute_id,
                "sequence": item.source_attribute.sequence,
                "rawSource": item.source_attribute.raw_source,
                "rawSheet": item.source_attribute.raw_sheet,
                "externalSource": item.source_attribute.external_source,
                "rawField": item.source_attribute.raw_field,
                "canonicalField": item.source_attribute.canonical_field,
                "relevantRawValues": relevant_values(item.source_attribute.raw_value),
            },
            "existingDesignRelevantValues": relevant_values(item.existing_design_data),
            "matchResultRelevantValues": relevant_values(item.match_results),
            "calculationInput": {
                "designItemNo": snapshot.get("designItemNo"),
                "finishOrColor": snapshot_input.get("finishOrColor"),
                "materialId": snapshot_input.get("materialId"),
                "materialCode": snapshot_input.get("materialCode"),
                "materialName": snapshot_input.get("materialName"),
                "materialSpecification": snapshot_input.get("materialSpecification"),
                "paintProcess": snapshot_input.get("paintProcess"),
                "processConfiguration": snapshot_input.get("processConfiguration"),
            },
            "latestDesignRevision": None if revision is None else {
                "id": revision.pk,
                "revision": revision.revision,
                "designNature": revision.design_nature,
                "materialId": revision.material_id,
                "material": None if not revision.material_id else {
                    "code": revision.material.code,
                    "name": revision.material.name,
                    "categoryId": revision.material.category_id,
                    "categoryCode": revision.material.category.code if revision.material.category_id else None,
                    "specification": revision.material.specification,
                    "baseUom": revision.material.base_uom.code if revision.material.base_uom_id else None,
                    "purpose": revision.material.purpose,
                },
                "materialProcessType": None if not revision.material_process_type_id else {
                    "id": revision.material_process_type_id,
                    "code": revision.material_process_type.code,
                    "name": revision.material_process_type.name,
                },
                "paintProcessType": None if not revision.paint_process_type_id else {
                    "id": revision.paint_process_type_id,
                    "code": revision.paint_process_type.code,
                    "name": revision.paint_process_type.name,
                },
                "edgeMethod": None if not revision.edge_method_id else {
                    "id": revision.edge_method_id,
                    "code": revision.edge_method.code,
                    "name": revision.edge_method.name,
                },
                "designDataRelevantValues": relevant_values(revision.design_data),
                "sourceProvenanceRelevantValues": relevant_values(revision.source_provenance),
                "masterMatchRelevantValues": relevant_values(revision.master_match_results),
                "createdBy": revision.created_by.username,
            },
            "savedDerivedFactCodes": sorted({
                str(row.get("canonicalField") or "") for row in related_facts
            }),
            "veneerFinishSavedDerivedFacts": [
                row for row in related_facts
                if any(token in str(row).casefold() for token in ("veneer", "finish", "饰面", "木皮"))
            ],
            "requirements": item_requirements,
            "veneerFinishRequirements": [
                row for row in item_requirements
                if row["role"] in {"VENEER", "VENEER_FINISH", "FINISH_MATERIAL"}
            ],
        })

    material_130 = Material.objects.select_related("category", "base_uom").get(pk=130)
    material_actor = actor_preflight(MATERIAL_ACTOR, material_actor=True)
    requirement_actor = actor_preflight(REQUIREMENT_ACTOR, material_actor=False)
    actor = User.objects.select_related(
        "employee_profile__department_ref", "employee_profile__position_ref",
    ).get(pk=requirement_actor["user"].pk)
    preview = OrderEngineeringClosureService.preview_bom(
        user=actor, calculation_id=calculation.pk,
    )

    derived_rows = list(EngineeringDerivedFact.objects.filter(
        calculation=calculation,
    ).values("id", "fact_code", "canonical_field", "source_detail_id", "source_path"))
    result = {
        "status": "PASS_READ_ONLY",
        "database": {
            "path": str(database),
            "size": database.stat().st_size,
            "startSha256": start_sha,
            **database_checks(database),
        },
        "calculation": {
            "id": calculation.pk,
            "calculationNo": calculation.calculation_no,
            "orderNo": calculation.sales_order_item.sales_order.order_no,
            "lineNo": calculation.sales_order_item.line_no,
            "salesOrderItemId": calculation.sales_order_item_id,
            "orderEngineeringInstanceId": calculation.engineering_instance_id,
            "sourceRecordId": calculation.source_record_id,
            "status": calculation.status,
        },
        "objects": object_rows,
        "requirementRoleCounts": dict(sorted(requirement_roles.items())),
        "requirementIds": [row.pk for row in requirements],
        "historicalCompanyVeneerFinishRequirements": list(
            EngineeringMaterialRequirement.objects.filter(
                calculation__company_id=calculation.company_id,
            ).filter(
                trace__structureRole__in=("VENEER", "VENEER_FINISH", "FINISH_MATERIAL"),
            ).values_list("pk", flat=True)
        ),
        "derivedFactCount": len(derived_rows),
        "veneerFinishDerivedFacts": [
            row for row in derived_rows
            if any(token in str(row).casefold() for token in ("veneer", "finish", "饰面", "木皮"))
        ],
        "material130": {
            "id": material_130.pk,
            "code": material_130.code,
            "name": material_130.name,
            "categoryId": material_130.category_id,
            "categoryCode": material_130.category.code if material_130.category_id else None,
            "specification": material_130.specification,
            "baseUom": material_130.base_uom.code if material_130.base_uom_id else None,
            "purpose": material_130.purpose,
            "requirementIds": [
                row.pk for row in requirements if row.material_id == material_130.pk
            ],
        },
        "applicabilityModel": {
            "structureRoleCount": StructureRole.objects.filter(
                company_id=calculation.company_id,
            ).count(),
            "veneerFinishStructureRoles": list(StructureRole.objects.filter(
                company_id=calculation.company_id,
                role_code__in=("VENEER", "VENEER_FINISH", "FINISH_MATERIAL"),
            ).values("id", "role_code", "role_name", "applicability", "is_active")),
            "bomCompletenessRuleCount": BOMCompletenessRule.objects.filter(
                template__company_id=calculation.company_id,
            ).count(),
            "veneerFinishTemplateNodes": list(ProductTemplateStructureNode.objects.filter(
                template__company_id=calculation.company_id,
                structure_role__role_code__in=("VENEER", "VENEER_FINISH", "FINISH_MATERIAL"),
            ).values("id", "template_id", "node_code", "slot_requirement", "condition_schema")),
            "orderConfiguredProducts": list(OrderConfiguredProduct.objects.filter(
                sales_order=calculation.sales_order_item.sales_order,
            ).values("id", "definition_mode", "template_id", "configuration_id", "status")),
        },
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
        "actors": {
            key: {
                **row["readback"],
                "roles": list(row["user"].role_scope_assignments.select_related("role").filter(
                    active=True,
                ).values(
                    "role_id", "role__code", "role__name", "scope_code",
                    "organization_id", "department_id", "active",
                )),
            }
            for key, row in (
                ("materialMaster", material_actor),
                ("requirement", requirement_actor),
            )
        },
        "businessWriteCount": 0,
        "bomGenerated": False,
    }
    result["database"]["endSha256"] = sha256(database)
    result["database"]["hashUnchanged"] = (
        result["database"]["startSha256"] == result["database"]["endSha256"]
    )
    if not result["database"]["hashUnchanged"]:
        raise RuntimeError("FORMAL_DATABASE_CHANGED_DURING_READ_ONLY_AUDIT")
    if args.decision:
        result = {
            "status": result["status"],
            "database": result["database"],
            "calculation": result["calculation"],
            "objects": [{
                "designItemId": row["designItemId"],
                "designObject": row["designObject"],
                "finishOrColor": row["calculationInput"]["finishOrColor"],
                "paintProcess": row["calculationInput"]["paintProcess"],
                "latestMaterialId": (
                    row["latestDesignRevision"]["materialId"]
                    if row["latestDesignRevision"] else None
                ),
                "veneerFinishDerivedFactCount": len(row["veneerFinishSavedDerivedFacts"]),
                "veneerFinishRequirementCount": len(row["veneerFinishRequirements"]),
            } for row in result["objects"]],
            "requirementRoleCounts": result["requirementRoleCounts"],
            "requirementIds": result["requirementIds"],
            "historicalCompanyVeneerFinishRequirements": result["historicalCompanyVeneerFinishRequirements"],
            "material130": result["material130"],
            "applicabilityModel": result["applicabilityModel"],
            "preview": result["preview"],
            "businessWriteCount": result["businessWriteCount"],
            "bomGenerated": result["bomGenerated"],
        }
    elif args.compact:
        result = {
            "status": result["status"],
            "database": result["database"],
            "calculation": result["calculation"],
            "objects": [{
                "designItemId": row["designItemId"],
                "designObject": row["designObject"],
                "sourceAttributeId": row["sourceAttribute"]["id"],
                "sourceSequence": row["sourceAttribute"]["sequence"],
                "externalSource": row["sourceAttribute"]["externalSource"],
                "rawMaterialName": row["sourceAttribute"]["relevantRawValues"].get("materialName"),
                "rawMaterialCode": row["sourceAttribute"]["relevantRawValues"].get("materialCode"),
                "rawSpecification": row["sourceAttribute"]["relevantRawValues"].get("specification"),
                "sourceMaterialProcessCode": row["existingDesignRelevantValues"].get("materialProcessCode"),
                "sourceRoutingProcessCode": row["existingDesignRelevantValues"].get("routingProcessCode"),
                "sourcePaintProcess": row["existingDesignRelevantValues"].get("paintProcess"),
                "sourceFinishOrColor": row["existingDesignRelevantValues"].get("finishOrColor"),
                "calculationInput": row["calculationInput"],
                "latestDesignRevision": row["latestDesignRevision"],
                "savedDerivedFactCodes": row["savedDerivedFactCodes"],
                "veneerFinishSavedDerivedFacts": row["veneerFinishSavedDerivedFacts"],
                "requirementIds": [item["id"] for item in row["requirements"]],
                "veneerFinishRequirements": row["veneerFinishRequirements"],
            } for row in result["objects"]],
            "requirementRoleCounts": result["requirementRoleCounts"],
            "requirementIds": result["requirementIds"],
            "historicalCompanyVeneerFinishRequirements": result["historicalCompanyVeneerFinishRequirements"],
            "derivedFactCount": result["derivedFactCount"],
            "veneerFinishDerivedFacts": result["veneerFinishDerivedFacts"],
            "material130": result["material130"],
            "applicabilityModel": result["applicabilityModel"],
            "preview": result["preview"],
            "actors": result["actors"],
            "businessWriteCount": result["businessWriteCount"],
            "bomGenerated": result["bomGenerated"],
        }
    print(json.dumps(
        result, ensure_ascii=args.ensure_ascii, indent=2, default=str,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
