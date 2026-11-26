"""Database-level postflight for the wood-category/CASING_TRIM workflow."""

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

from wood_material_casing_trim_workflow import (  # noqa: E402
    CATEGORY_SPECS,
    MATERIAL_CODE,
    MATERIAL_ID,
    MATERIAL_PURPOSE,
    MATERIAL_SPECIFICATION,
    compact_result,
    configure,
    readback,
)


ALLOWED_CHANGED_TABLES = {
    "material_category",
    "material",
    "masterdata_external_identity",
    "masterdata_write_request",
    "system_organization_operating_audits",
    "pde_engineering_rule_definition",
    "pde_engineering_material_requirement",
}

EXPECTED_ROW_COUNT_DELTAS = {
    "material_category": 3,
    "material": 0,
    "masterdata_external_identity": 15,
    "masterdata_write_request": 15,
    "system_organization_operating_audits": 25,
    "pde_engineering_rule_definition": 5,
    "pde_engineering_material_requirement": 5,
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


def equal_except(before: list, after: list, ignored: set[str]) -> bool:
    def normalized(rows):
        return [{key: value for key, value in row.items() if key not in ignored} for row in rows]

    return normalized(before) == normalized(after)


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
    deltas = {
        name: after[name]["count"] - before[name]["count"]
        for name in sorted(changed)
    }

    category_before_1_10 = selected_rows(backup, "material_category", "id BETWEEN 1 AND 10")
    category_after_1_10 = selected_rows(database, "material_category", "id BETWEEN 1 AND 10")
    solid_before = selected_rows(backup, "material_category", "id = 11")
    solid_after = selected_rows(database, "material_category", "id = 11")
    material_249_before = selected_rows(backup, "material", "id = 249")
    material_249_after = selected_rows(database, "material", "id = 249")

    protected = {
        "categoryIds1to10": category_before_1_10 == category_after_1_10,
        "solidWoodIdentityExceptParentAndTimestamp": equal_except(
            solid_before, solid_after, {"parent_id", "updated_at"},
        ),
        "surfaceAndCasingRequirements3to12": (
            selected_rows(backup, "pde_engineering_material_requirement", "id BETWEEN 3 AND 12")
            == selected_rows(database, "pde_engineering_material_requirement", "id BETWEEN 3 AND 12")
        ),
        "materials130_136to138_279": (
            selected_rows(backup, "material", "id IN (130,136,137,138,279)")
            == selected_rows(database, "material", "id IN (130,136,137,138,279)")
        ),
        "material247And250": (
            selected_rows(backup, "material", "id IN (247,250)")
            == selected_rows(database, "material", "id IN (247,250)")
        ),
        "material249OnlyAuthorizedFields": equal_except(
            material_249_before,
            material_249_after,
            {"category_id", "specification", "purpose", "updated_at"},
        ),
        "calculations3to6": (
            selected_rows(backup, "pde_engineering_calculation_record", "id IN (3,4,5,6)")
            == selected_rows(database, "pde_engineering_calculation_record", "id IN (3,4,5,6)")
        ),
        "details3to6": (
            selected_rows(backup, "pde_engineering_calculation_detail", "calculation_id IN (3,4,5,6)")
            == selected_rows(database, "pde_engineering_calculation_detail", "calculation_id IN (3,4,5,6)")
        ),
        "facts3to6": (
            selected_rows(backup, "pde_engineering_derived_fact", "calculation_id IN (3,4,5,6)")
            == selected_rows(database, "pde_engineering_derived_fact", "calculation_id IN (3,4,5,6)")
        ),
        "facts64to93": (
            selected_rows(backup, "pde_engineering_derived_fact", "id BETWEEN 64 AND 93")
            == selected_rows(database, "pde_engineering_derived_fact", "id BETWEEN 64 AND 93")
        ),
        "bomHeaders": before["pde_product_bom"] == after["pde_product_bom"],
        "bomVersions": before["pde_bom_version"] == after["pde_bom_version"],
        "bomItems": before["pde_bom_item"] == after["pde_bom_item"],
        "bomRequirementLinks": (
            before["pde_bom_item_source_requirement"]
            == after["pde_bom_item_source_requirement"]
        ),
        "cancelledOrder": (
            selected_rows(backup, "sales_order", "order_no = 'SO202610020004'")
            == selected_rows(database, "sales_order", "order_no = 'SO202610020004'")
        ),
        "globalUom": before["unit_of_measure"] == after["unit_of_measure"],
        "organization": before["system_company"] == after["system_company"],
        "department": before["system_department"] == after["system_department"],
        "position": before["system_position"] == after["system_position"],
        "roles": before["system_role"] == after["system_role"],
        "permissions": before["system_permission"] == after["system_permission"],
        "rolePermissions": before["system_rolepermission"] == after["system_rolepermission"],
        "migrationLedger": before["django_migrations"] == after["django_migrations"],
    }

    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()

    configure(database)
    from masterdata.models import Material, MaterialCategory, UnitOfMeasure
    from pde.models import EngineeringMaterialRequirement

    compact = compact_result(readback())
    target_categories = {
        key: MaterialCategory.objects.select_related("parent").get(code=spec["code"])
        for key, spec in CATEGORY_SPECS.items()
    }
    categories_ok = (
        target_categories["wood"].parent_id is None
        and target_categories["solid"].pk == 11
        and target_categories["solid"].parent_id == target_categories["wood"].pk
        and target_categories["wood_based"].parent_id == target_categories["wood"].pk
        and target_categories["multilayer"].parent_id == target_categories["wood_based"].pk
        and all(row.is_active and row.company_id == 1 for row in target_categories.values())
        and all(
            MaterialCategory.objects.filter(company_id=1, code=spec["code"]).count() == 1
            and MaterialCategory.objects.filter(company_id=1, name=spec["name"]).count() == 1
            for spec in CATEGORY_SPECS.values()
        )
    )
    material = Material.objects.select_related("category", "base_uom").get(pk=MATERIAL_ID)
    material_ok = (
        material.code == MATERIAL_CODE
        and material.category_id == target_categories["multilayer"].pk
        and material.specification == MATERIAL_SPECIFICATION
        and material.purpose == MATERIAL_PURPOSE
        and material.base_uom.code == "支"
        and material.is_active and material.is_purchased and not material.is_produced
    )
    requirements = compact["requirements"]
    requirements_ok = (
        len(requirements) == 5
        and {row["designItemNo"][-4:] for row in requirements} == {"0003", "0004", "0005", "0006", "0007"}
        and all(
            row["materialId"] == 249
            and row["calculatedQuantity"] == "5.000000"
            and row["netQuantity"] == "5.000000"
            and row["uom"] == "支"
            and row["scrapRate"] == "0.000000"
            and row["structureRole"] == "CASING_TRIM"
            and row["quantityExpression"] == "AW+AY"
            and row["orderQuantityMultiplierApplied"] is False
            and row["provenance"]["qAlreadyApplied"] is True
            and row["provenance"]["globalUomConversionCreated"] is False
            and row["provenance"]["currentRequirementUnitMapping"] == "1条=1支"
            for row in requirements
        )
        and sum(Decimal(row["netQuantity"]) for row in requirements) == Decimal("25.000000")
    )
    preview = compact["bomPreview"]
    category_statuses = {
        row["code"]: row["status"]
        for row in preview["currentVersionMaterialCompleteness"]["evaluatedCategories"]
    }
    preview_ok = (
        preview["rowCount"] == 3
        and preview["sourceRequirementCount"] == 15
        and category_statuses == {
            "DOOR_LEAF_SURFACE_PANEL": "COMPLETE",
            "CASING_MATERIAL": "COMPLETE",
            "CASING_TRIM": "COMPLETE",
            "EDGE_BANDING": "MISSING_REQUIREMENT",
        }
        and preview["firstRealBlocker"]["code"] == "EDGE_BANDING_REQUIREMENT_MISSING"
        and preview["canGenerate"] is False
        and preview["alreadyGenerated"] is False
        and preview["bomId"] is None
        and preview["bomVersionId"] is None
        and preview["businessWriteSideEffectCount"] == 0
    )
    exact_deltas_ok = (
        changed == ALLOWED_CHANGED_TABLES
        and deltas == EXPECTED_ROW_COUNT_DELTAS
    )
    passed = (
        exact_deltas_ok
        and all(protected.values())
        and integrity == [("ok",)]
        and foreign_keys == []
        and categories_ok
        and material_ok
        and requirements_ok
        and preview_ok
        and compact["businessWriteCount"] == 0
        and compact["bomGenerated"] is False
        and EngineeringMaterialRequirement.objects.filter(pk__range=(3, 12)).count() == 10
        and UnitOfMeasure.objects.count() == before["unit_of_measure"]["count"]
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
        "expectedRowCountDeltas": EXPECTED_ROW_COUNT_DELTAS,
        "protected": protected,
        "categoryCanonical": {
            "passed": categories_ok,
            "tree": compact["categoryHierarchy"]["tree"],
        },
        "material249": {
            "passed": material_ok,
            "id": material.pk, "code": material.code,
            "categoryId": material.category_id,
            "specification": material.specification,
            "purpose": material.purpose,
            "uom": material.base_uom.code,
        },
        "requirements": {
            "passed": requirements_ok,
            "count": len(requirements),
            "ids": [row["requirementId"] for row in requirements],
            "mappingIds": [row["mappingId"] for row in requirements],
            "totalQuantity": str(sum(Decimal(row["netQuantity"]) for row in requirements)),
        },
        "preview": {
            "passed": preview_ok,
            "previewHash": preview["previewHash"],
            "rowCount": preview["rowCount"],
            "sourceRequirementCount": preview["sourceRequirementCount"],
            "categoryStatuses": category_statuses,
            "firstRealBlocker": preview["firstRealBlocker"],
            "canGenerate": preview["canGenerate"],
            "alreadyGenerated": preview["alreadyGenerated"],
            "businessWriteSideEffectCount": preview["businessWriteSideEffectCount"],
        },
        "formalReadback": compact,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
