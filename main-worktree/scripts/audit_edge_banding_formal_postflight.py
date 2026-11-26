"""Postflight protection audit for the line-1 EDGE_BANDING continuation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from edge_banding_requirement_workflow import compact_result, configure, readback  # noqa: E402


ALLOWED_CHANGED_TABLES = {
    "material_category", "material", "code_rule",
    "masterdata_external_identity", "masterdata_write_request",
    "system_organization_operating_audits",
    "pde_engineering_rule_definition", "pde_engineering_material_requirement",
}


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def snapshot(path: Path) -> dict:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        tables = [
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        result = {}
        for table in tables:
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            rows = connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            payload = [dict(zip(columns, row)) for row in rows]
            result[table] = {
                "count": len(payload),
                "hash": hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest(),
            }
        return result
    finally:
        connection.close()


def selected_rows(path: Path, table: str, where: str) -> list:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(
            f'SELECT * FROM "{table}" WHERE {where} ORDER BY id'
        )]
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    args = parser.parse_args()
    database, backup = args.database.resolve(), args.backup.resolve()
    if not database.is_file() or not backup.is_file():
        raise RuntimeError("DATABASE_OR_BACKUP_MISSING")

    before, after = snapshot(backup), snapshot(database)
    changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
    deltas = {name: after[name]["count"] - before[name]["count"] for name in sorted(changed)}
    expected_deltas = {
        "code_rule": 0,
        "masterdata_external_identity": 24,
        "masterdata_write_request": 24,
        "material": 2,
        "material_category": 2,
        "pde_engineering_material_requirement": 10,
        "pde_engineering_rule_definition": 10,
        "system_organization_operating_audits": 44,
    }
    protected = {
        "requirements3to17": (
            selected_rows(backup, "pde_engineering_material_requirement", "id BETWEEN 3 AND 17")
            == selected_rows(database, "pde_engineering_material_requirement", "id BETWEEN 3 AND 17")
        ),
        "mappings20to29": (
            selected_rows(backup, "pde_engineering_rule_definition", "id BETWEEN 20 AND 29")
            == selected_rows(database, "pde_engineering_rule_definition", "id BETWEEN 20 AND 29")
        ),
        "materialsProtected": (
            selected_rows(backup, "material", "id IN (130,136,137,138,185,249,265,266,279)")
            == selected_rows(database, "material", "id IN (130,136,137,138,185,249,265,266,279)")
        ),
        "categories11to14": (
            selected_rows(backup, "material_category", "id BETWEEN 11 AND 14")
            == selected_rows(database, "material_category", "id BETWEEN 11 AND 14")
        ),
        "calculations3to6": (
            selected_rows(backup, "pde_engineering_calculation_record", "id BETWEEN 3 AND 6")
            == selected_rows(database, "pde_engineering_calculation_record", "id BETWEEN 3 AND 6")
        ),
        "calculationDetails3to6": (
            selected_rows(backup, "pde_engineering_calculation_detail", "calculation_id BETWEEN 3 AND 6")
            == selected_rows(database, "pde_engineering_calculation_detail", "calculation_id BETWEEN 3 AND 6")
        ),
        "derivedFacts3to6": (
            selected_rows(backup, "pde_engineering_derived_fact", "calculation_id BETWEEN 3 AND 6")
            == selected_rows(database, "pde_engineering_derived_fact", "calculation_id BETWEEN 3 AND 6")
        ),
        "bomHeaders": before["pde_product_bom"] == after["pde_product_bom"],
        "bomVersions": before["pde_bom_version"] == after["pde_bom_version"],
        "bomItems": before["pde_bom_item"] == after["pde_bom_item"],
        "bomRequirementLinks": (
            before["pde_bom_item_source_requirement"]
            == after["pde_bom_item_source_requirement"]
        ),
        "migrationLedger": before["django_migrations"] == after["django_migrations"],
    }

    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        connection.close()

    configure(database)
    from masterdata.models import CodeRule, Material, MaterialCategory
    from pde.models import (
        EngineeringCalculationDetail, EngineeringDerivedFact,
        EngineeringMaterialRequirement, EngineeringRuleDefinition,
        OrderEngineeringInstance, ProductBOM, ProductDesignItem,
    )
    from sales.models import SalesOrder

    compact = compact_result(readback())
    requirements = compact["requirements"]
    preview = compact["bomPreview"]
    edge_complete = next(
        row for row in preview["currentVersionMaterialCompleteness"]["evaluatedCategories"]
        if row["code"] == "EDGE_BANDING"
    )
    edge_rows = [row for row in preview["rows"] if row["materialId"] in {280, 281}]
    totals = {row["materialId"]: row["quantity"] for row in edge_rows}
    trace_contract = all(
        row["trace"]["structureRole"] == "EDGE_BANDING"
        and row["trace"]["scrapRate"] == "0.000000"
        and row["trace"]["orderQuantityMultiplierApplied"] is False
        and row["trace"]["provenance"]["quantityBasis"] == "NET_LENGTH"
        and row["trace"]["provenance"]["allowanceApplied"] is False
        and row["trace"]["provenance"]["qAlreadyApplied"] is True
        and row["trace"]["provenance"]["salesOrderItemQuantityMultiplierApplied"] is False
        and row["trace"]["provenance"]["appearanceReference"] == "LC-M045"
        and row["grossQuantity"] == row["netQuantity"]
        and row["scrapRate"] == "0.000000"
        and row["uom"] == "m"
        for row in requirements
    )
    target_categories = list(MaterialCategory.objects.select_related("parent").filter(
        company_id=1,
        code__in=("MATCAT-SURFACE-EDGE-MATERIAL", "MATCAT-EDGE-BANDING"),
    ).order_by("pk"))
    target_materials = list(Material.objects.select_related("category", "base_uom").filter(
        company_id=1, name__in=("封边条25mm", "封边条50mm"),
    ).order_by("pk"))
    target_mappings = list(EngineeringRuleDefinition.objects.filter(
        company_id=1, rule_code__startswith=f"MRM.SO202609180003.EDGE-",
    ).order_by("pk"))
    cancelled = SalesOrder.objects.get(order_no="SO202610020004")
    cancelled_state = {
        "status": cancelled.status,
        "currentSourceCount": ProductDesignItem.objects.filter(
            sales_order_item__sales_order=cancelled,
        ).values("source_record_id").distinct().count(),
        "pdeCandidateCount": ProductDesignItem.objects.filter(
            sales_order_item__sales_order=cancelled,
        ).count(),
        "activeOeiCount": OrderEngineeringInstance.objects.filter(
            sales_order_item__sales_order=cancelled,
        ).exclude(status="inactive").count(),
        "bomCandidateCount": ProductBOM.objects.filter(
            order_engineering_instance__sales_order_item__sales_order=cancelled,
        ).count(),
    }
    data_contract = (
        len(target_categories) == 2
        and target_categories[0].code == "MATCAT-SURFACE-EDGE-MATERIAL"
        and target_categories[0].parent_id is None
        and target_categories[1].code == "MATCAT-EDGE-BANDING"
        and target_categories[1].parent_id == target_categories[0].pk
        and len(target_materials) == 2
        and {row.specification for row in target_materials} == {"宽25 mm", "宽50 mm"}
        and all(
            row.category_id == target_categories[1].pk
            and row.purpose == "封边"
            and row.base_uom.code == "m"
            and not row.is_purchased and not row.is_produced and row.is_active
            for row in target_materials
        )
        and len(target_mappings) == 10
        and all(row.status == "released" for row in target_mappings)
        and len(requirements) == 10
        and len({row["sourceDetailId"] for row in requirements}) == 10
        and totals == {280: "49.204000", 281: "28.844000"}
        and trace_contract
        and edge_complete["status"] == "COMPLETE"
        and edge_complete["applicableDesignItemCount"] == 5
        and edge_complete["coveredDesignItemCount"] == 5
        and preview["sourceRequirementCount"] == 25
        and preview["rowCount"] == 5
        and preview["firstRealBlocker"]["code"] == "VENEER_FINISH_REQUIREMENT_MISSING"
        and preview["canGenerate"] is False
        and preview["alreadyGenerated"] is False
        and preview["bomId"] is None and preview["bomVersionId"] is None
        and preview["businessWriteSideEffectCount"] == 0
        and compact["bomGenerated"] is False
    )
    baseline_counts = {
        "globalDetails": EngineeringCalculationDetail.objects.count(),
        "globalFacts": EngineeringDerivedFact.objects.count(),
        "calculation3to6Details": EngineeringCalculationDetail.objects.filter(
            calculation_id__in=(3, 4, 5, 6),
        ).count(),
        "calculation3to6Facts": EngineeringDerivedFact.objects.filter(
            calculation_id__in=(3, 4, 5, 6),
        ).count(),
        "requirements": EngineeringMaterialRequirement.objects.count(),
        "codeRuleCurrentSequence": CodeRule.objects.get(
            company_id=1, entity_type="production_material",
        ).current_seq,
    }
    passed = (
        changed == ALLOWED_CHANGED_TABLES
        and deltas == expected_deltas
        and all(protected.values())
        and integrity == [("ok",)] and foreign_keys == []
        and data_contract
        and cancelled_state == {
            "status": "cancelled", "currentSourceCount": 0,
            "pdeCandidateCount": 0, "activeOeiCount": 0,
            "bomCandidateCount": 0,
        }
        and baseline_counts == {
            "globalDetails": 396, "globalFacts": 396,
            "calculation3to6Details": 388, "calculation3to6Facts": 388,
            "requirements": 27, "codeRuleCurrentSequence": 193,
        }
    )
    result = {
        "status": "PASS" if passed else "FAIL",
        "database": {
            "path": str(database), "size": database.stat().st_size,
            "sha256": sha256(database), "integrityCheck": integrity,
            "foreignKeyCheck": foreign_keys,
        },
        "backup": {
            "path": str(backup), "size": backup.stat().st_size,
            "sha256": sha256(backup),
        },
        "changedTables": sorted(changed),
        "unexpectedChangedTables": sorted(changed - ALLOWED_CHANGED_TABLES),
        "rowCountDeltas": deltas,
        "expectedRowCountDeltas": expected_deltas,
        "protected": protected,
        "dataContract": data_contract,
        "traceContract": trace_contract,
        "targetCategories": [{
            "id": row.pk, "code": row.code, "name": row.name,
            "parentId": row.parent_id,
        } for row in target_categories],
        "targetMaterials": [{
            "id": row.pk, "code": row.code, "name": row.name,
            "specification": row.specification, "purpose": row.purpose,
            "categoryId": row.category_id, "uom": row.base_uom.code,
            "supplyType": row.supply_type,
        } for row in target_materials],
        "mappingIds": [row.pk for row in target_mappings],
        "mappingRuleCodes": [row.rule_code for row in target_mappings],
        "requirementIds": [row["requirementId"] for row in requirements],
        "edgeTotals": totals,
        "baselineCounts": baseline_counts,
        "cancelledOrder": cancelled_state,
        "bomPreview": preview,
        "formalReadback": compact,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
