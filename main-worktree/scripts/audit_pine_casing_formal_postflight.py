"""Formal postflight for the pine/casing continuation against its backup."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pine_casing_requirement_workflow import compact_result, configure, readback  # noqa: E402


ALLOWED_CHANGED_TABLES = {
    "material", "code_rule", "masterdata_external_identity",
    "masterdata_write_request", "system_organization_operating_audits",
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
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
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
    deltas = {
        name: after[name]["count"] - before[name]["count"]
        for name in sorted(changed)
    }
    protected = {
        "surfaceRequirements3to7": (
            selected_rows(backup, "pde_engineering_material_requirement", "id IN (3,4,5,6,7)")
            == selected_rows(database, "pde_engineering_material_requirement", "id IN (3,4,5,6,7)")
        ),
        "materials130And136to138": (
            selected_rows(backup, "material", "id IN (130,136,137,138)")
            == selected_rows(database, "material", "id IN (130,136,137,138)")
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
        "bomHeaders": before["pde_product_bom"] == after["pde_product_bom"],
        "bomVersions": before["pde_bom_version"] == after["pde_bom_version"],
        "bomItems": before["pde_bom_item"] == after["pde_bom_item"],
        "bomRequirementLinks": (
            before["pde_bom_item_source_requirement"] == after["pde_bom_item_source_requirement"]
        ),
        "migrationLedger": before["django_migrations"] == after["django_migrations"],
    }
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    configure(database)
    from masterdata.models import Material
    from pde.models import EngineeringCalculationDetail, EngineeringDerivedFact, OrderEngineeringInstance, ProductBOM, ProductDesignItem
    from sales.models import SalesOrder

    compact = compact_result(readback())
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
        "node11CandidateCount": 0,
    }
    expected_deltas = {
        "material": 1,
        "code_rule": 0,
        "masterdata_external_identity": 11,
        "masterdata_write_request": 11,
        "system_organization_operating_audits": 21,
        "pde_engineering_rule_definition": 5,
        "pde_engineering_material_requirement": 5,
    }
    result = {
        "status": "PASS" if (
            changed <= ALLOWED_CHANGED_TABLES
            and deltas == expected_deltas
            and all(protected.values())
            and integrity == [("ok",)] and foreign_keys == []
            and compact["bomPreview"]["canGenerate"] is False
            and compact["bomPreview"]["firstRealBlocker"]["code"] == "CASING_TRIM_REQUIREMENT_MISSING"
            and cancelled_state == {
                "status": "cancelled", "currentSourceCount": 0,
                "pdeCandidateCount": 0, "activeOeiCount": 0,
                "bomCandidateCount": 0, "node11CandidateCount": 0,
            }
            and EngineeringCalculationDetail.objects.count() == 396
            and EngineeringDerivedFact.objects.count() == 396
            and EngineeringCalculationDetail.objects.filter(calculation_id__in=(3,4,5,6)).count() == 388
            and EngineeringDerivedFact.objects.filter(calculation_id__in=(3,4,5,6)).count() == 388
            and Material.objects.filter(pk__in=(136,137,138), is_active=False).count() == 3
        ) else "FAIL",
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
        "savedFacts": {
            "globalDetails": EngineeringCalculationDetail.objects.count(),
            "globalFacts": EngineeringDerivedFact.objects.count(),
            "calculation3to6Details": EngineeringCalculationDetail.objects.filter(calculation_id__in=(3,4,5,6)).count(),
            "calculation3to6Facts": EngineeringDerivedFact.objects.filter(calculation_id__in=(3,4,5,6)).count(),
        },
        "cancelledOrder": cancelled_state,
        "formalReadback": compact,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
