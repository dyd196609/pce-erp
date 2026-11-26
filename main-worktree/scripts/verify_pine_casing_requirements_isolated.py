"""Isolated formal-write gate for pine 30×40 and five casing Requirements."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pine_casing_requirement_workflow import (  # noqa: E402
    CALCULATION_ID,
    DESIGN_SUFFIXES,
    FORMULA_CODE,
    FORMULA_EXPRESSION,
    MATERIAL_APPLICATION_NOTES,
    MATERIAL_NAME,
    MATERIAL_PURPOSE,
    MATERIAL_SPECIFICATION,
    PineCasingWorkflowError,
    STRUCTURE_ROLE,
    canonical_material_state,
    configure,
    ensure_canonical_material,
    execute,
)


ALLOWED_CHANGED_TABLES = {
    "material",
    "code_rule",
    "masterdata_external_identity",
    "masterdata_write_request",
    "system_organization_operating_audits",
    "pde_engineering_rule_definition",
    "pde_engineering_material_requirement",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def rows(model, *, where=None):
    query = model.objects.all()
    if where:
        query = query.filter(**where)
    fields = [field.attname for field in model._meta.concrete_fields]
    return list(query.order_by("pk").values(*fields))


def table_fingerprints(database: Path) -> dict:
    connection = sqlite3.connect(database)
    try:
        tables = [
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        result = {}
        for table in tables:
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            records = connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            payload = [dict(zip(columns, record)) for record in records]
            result[table] = {
                "count": len(payload),
                "hash": hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest(),
            }
        return result
    finally:
        connection.close()


def changed_tables(before: dict, after: dict) -> set[str]:
    return {name for name in set(before) | set(after) if before.get(name) != after.get(name)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    source = args.database.resolve()
    if not source.is_file():
        raise RuntimeError("SOURCE_DATABASE_NOT_FOUND")
    source_hash_before = sha256(source)

    with tempfile.TemporaryDirectory(
        prefix="pce-pine-casing-isolated-", ignore_cleanup_errors=True,
    ) as directory:
        isolated = Path(directory) / "pine-casing-isolated.sqlite3"
        shutil.copy2(source, isolated)
        if sha256(isolated) != source_hash_before:
            raise RuntimeError("ISOLATED_DATABASE_COPY_HASH_MISMATCH")
        configure(isolated)

        from django.db import connection, connections, transaction
        from django.db.migrations.recorder import MigrationRecorder
        from masterdata.models import Material
        from pde.models import (
            BOMItem,
            BOMItemSourceRequirement,
            BOMVersion,
            EngineeringCalculationDetail,
            EngineeringCalculationRecord,
            EngineeringDerivedFact,
            EngineeringMaterialRequirement,
            EngineeringRuleDefinition,
            OrderEngineeringInstance,
            ProductBOM,
            ProductDesignItem,
        )
        from sales.models import SalesOrder
        from system.models import User

        tests = []

        def check(name: str, condition: bool, evidence=None):
            if not condition:
                raise AssertionError(name)
            tests.append({"name": name, "status": "PASS", "evidence": evidence})

        def protected_cancelled_order():
            order = SalesOrder.objects.get(order_no="SO202610020004")
            return {
                "id": order.pk,
                "status": order.status,
                "sourceCount": ProductDesignItem.objects.filter(
                    sales_order_item__sales_order=order,
                ).values("source_record_id").distinct().count(),
                "designCount": ProductDesignItem.objects.filter(
                    sales_order_item__sales_order=order,
                ).count(),
                "activeInstanceCount": OrderEngineeringInstance.objects.filter(
                    sales_order_item__sales_order=order,
                ).exclude(status="inactive").count(),
                "instances": list(OrderEngineeringInstance.objects.filter(
                    sales_order_item__sales_order=order,
                ).values("id", "instance_no", "status").order_by("id")),
                "calculationCount": EngineeringCalculationRecord.objects.filter(
                    sales_order_item__sales_order=order,
                ).count(),
                "bomCount": ProductBOM.objects.filter(
                    order_engineering_instance__sales_order_item__sales_order=order,
                ).count(),
            }

        initial_tables = table_fingerprints(isolated)
        initial_requirements = rows(
            EngineeringMaterialRequirement, where={"pk__in": (3, 4, 5, 6, 7)},
        )
        initial_materials = rows(Material, where={"pk__in": (130, 136, 137, 138)})
        initial_calculations = rows(
            EngineeringCalculationRecord, where={"pk__in": (3, 4, 5, 6)},
        )
        detail_rows = rows(
            EngineeringCalculationDetail, where={"calculation_id__in": (3, 4, 5, 6)},
        )
        fact_rows = rows(
            EngineeringDerivedFact, where={"calculation_id__in": (3, 4, 5, 6)},
        )
        initial_saved_facts = {
            "globalDetails": EngineeringCalculationDetail.objects.count(),
            "globalFacts": EngineeringDerivedFact.objects.count(),
            "calculationDetails": len(detail_rows),
            "calculationFacts": len(fact_rows),
            "detailHash": hashlib.sha256(canonical(detail_rows).encode("utf-8")).hexdigest(),
            "factHash": hashlib.sha256(canonical(fact_rows).encode("utf-8")).hexdigest(),
        }
        initial_bom = {
            "headers": rows(ProductBOM),
            "versions": rows(BOMVersion),
            "items": rows(BOMItem),
            "links": rows(BOMItemSourceRequirement),
        }
        initial_cancelled = protected_cancelled_order()
        initial_migrations = list(
            MigrationRecorder.Migration.objects.order_by("app", "name").values_list("app", "name")
        )
        initial_migration_files = sorted(
            str(path.relative_to(ROOT)) for path in ROOT.glob("backend/*/migrations/*.py")
        )
        initial_pine = canonical_material_state()
        check(
            "01 pine 30x40 canonical lookup starts empty",
            not initial_pine["active"] and not initial_pine["inactive"],
        )

        first = execute(create=True, apply=True, allow_generate_if_ready=False)
        material_id = first["material"]["readback"]["id"]
        material = Material.objects.select_related("category", "base_uom").get(pk=material_id)
        check(
            "02 exact active canonical is created once",
            first["material"]["decision"] == "CREATED"
            and first["material"]["canonicalActiveCount"] == 1,
            first["material"],
        )
        connections.close_all()
        hash_before_active_reuse = sha256(isolated)
        actor = User.objects.get(username="emd_emp047")
        active_reuse = ensure_canonical_material(user=actor, create=True)
        connections.close_all()
        check(
            "03 active canonical replay creates no duplicate",
            active_reuse["decision"] == "REUSE_ACTIVE_CANONICAL"
            and active_reuse["businessWriteCount"] == 0
            and sha256(isolated) == hash_before_active_reuse,
        )
        with transaction.atomic():
            Material.objects.filter(pk=material_id).update(is_active=False)
            try:
                ensure_canonical_material(user=actor, create=True)
            except PineCasingWorkflowError as exc:
                inactive_code = exc.code
            else:  # pragma: no cover - must fail closed
                inactive_code = None
            transaction.set_rollback(True)
        check(
            "04 inactive exact candidate fails closed",
            inactive_code == "INACTIVE_MATERIAL_CANDIDATE_REQUIRES_DECISION",
            inactive_code,
        )
        material.refresh_from_db()
        check(
            "05 category is MATCAT-SOLID-WOOD / 实木",
            material.category.code == "MATCAT-SOLID-WOOD" and material.category.name == "实木",
        )
        check("06 purpose is 木方 / 骨架材料", material.purpose == MATERIAL_PURPOSE)
        check(
            "07 specification and application notes are exact",
            material.name == MATERIAL_NAME
            and material.specification == MATERIAL_SPECIFICATION
            and material.application_notes == MATERIAL_APPLICATION_NOTES,
        )
        check(
            "08 base UOM is m / 米 and supply is pending",
            material.base_uom.code == "m" and material.base_uom.name == "米"
            and not material.is_purchased and not material.is_produced
            and material.supply_type == "pending_confirmation",
        )

        expected_quantities = {
            3: "4.990000", 4: "4.910000", 5: "4.935000",
            6: "4.870000", 7: "4.897000",
        }
        for index, row in enumerate(first["facts"], 9):
            suffix = int(row["object"][-4:])
            check(
                f"{index:02d} object {suffix:04d} reads N/O/Q and formula quantity",
                row["quantity"] == expected_quantities[suffix]
                and Decimal(row["Q"]) == Decimal("1"),
                row,
            )
        requirement_payloads = [row["requirement"] for row in first["readbacks"]]
        traces = [row["trace"] for row in requirement_payloads]
        check(
            "14 P is excluded from every formula and provenance",
            all("P" not in row["sourceFactCodes"] and row["provenance"]["P"].startswith("PRESERVED_NOT_USED") for row in traces),
        )
        check(
            "15 X is excluded from every formula and provenance",
            all("X" not in row["sourceFactCodes"] and row["provenance"]["X"].startswith("PRESERVED_NOT_USED") for row in traces),
        )
        check(
            "16 casing trim is not used",
            all(row["provenance"]["casingTrim"] == "OUT_OF_SCOPE_NOT_USED" for row in traces),
        )
        check(
            "17 edge banding is not used",
            all(row["provenance"]["edgeBanding"] == "OUT_OF_SCOPE_NOT_USED" for row in traces),
        )
        check(
            "18 sales order quantity five is never multiplied",
            all(
                row["salesOrderItemQuantity"] == "5.0000"
                and row["orderQuantityMultiplierApplied"] is False
                and row["salesItemMultiplier"] == "NOT_APPLIED"
                for row in traces
            ),
        )
        requirement_ids = [row["requirementId"] for row in requirement_payloads]
        mapping_ids = [row["mapping"]["id"] for row in requirement_payloads]
        check(
            "19 five Requirements and five mappings are independent",
            len(requirement_ids) == len(set(requirement_ids)) == 5
            and len(mapping_ids) == len(set(mapping_ids)) == 5
            and EngineeringMaterialRequirement.objects.filter(pk__in=requirement_ids).count() == 5
            and EngineeringRuleDefinition.objects.filter(pk__in=mapping_ids, status="released").count() == 5,
        )
        preview = first["bomPreview"]
        pine_row = next(row for row in preview["rows"] if row["materialId"] == material_id)
        check(
            "20 exact-compatible casing Requirements aggregate to 24.602 m",
            Decimal(pine_row["quantity"]) == Decimal("24.602000")
            and pine_row["sourceRequirementIds"] == requirement_ids
            and len(pine_row["sourceDesignItemNos"]) == 5,
            pine_row,
        )
        check(
            "21 Legacy Adoption scope is exact on all five",
            all(
                row["legacyAdoptionId"] == 1
                and row["calculationId"] == CALCULATION_ID
                and row["orderEngineeringInstanceId"] == 2
                for row in traces
            ),
        )
        check(
            "22 surface-panel Requirements 3-7 are byte-for-byte protected",
            rows(EngineeringMaterialRequirement, where={"pk__in": (3, 4, 5, 6, 7)}) == initial_requirements,
        )
        check(
            "23 line-3/4 BOM objects and links are byte-for-byte protected",
            {
                "headers": rows(ProductBOM), "versions": rows(BOMVersion),
                "items": rows(BOMItem), "links": rows(BOMItemSourceRequirement),
            } == initial_bom,
        )
        check(
            "24 blocked Preview does not generate BOM",
            preview["canGenerate"] is False
            and preview["firstRealBlocker"] is not None
            and first["bomGenerated"] is False
            and first["bomGeneration"] is None,
            {
                "canGenerate": preview["canGenerate"],
                "firstRealBlocker": preview["firstRealBlocker"],
                "completeness": preview["currentVersionMaterialCompleteness"],
            },
        )
        check(
            "25 cancelled SO202610020004 remains isolated",
            protected_cancelled_order() == initial_cancelled
            and initial_cancelled["status"] == "cancelled"
            and all(initial_cancelled[key] == 0 for key in (
                "sourceCount", "designCount", "activeInstanceCount", "calculationCount", "bomCount",
            )),
            initial_cancelled,
        )
        connections.close_all()
        isolated_hash_after_first = sha256(isolated)
        replay = execute(create=True, apply=True, allow_generate_if_ready=False)
        connections.close_all()
        check(
            "26 full workflow replay is byte-for-byte idempotent",
            replay["businessWriteCount"] == 0
            and all(row["idempotent"] for row in replay["applies"])
            and sha256(isolated) == isolated_hash_after_first,
        )
        check(
            "27 Material 130 and inactive 136-138 are protected",
            rows(Material, where={"pk__in": (130, 136, 137, 138)}) == initial_materials
            and not Material.objects.get(pk=136).is_active
            and not Material.objects.get(pk=137).is_active
            and not Material.objects.get(pk=138).is_active,
        )
        final_detail_rows = rows(
            EngineeringCalculationDetail, where={"calculation_id__in": (3, 4, 5, 6)},
        )
        final_fact_rows = rows(
            EngineeringDerivedFact, where={"calculation_id__in": (3, 4, 5, 6)},
        )
        check(
            "28 calculations and all 396/388 Detail-Fact facts are protected",
            initial_saved_facts["globalDetails"] == EngineeringCalculationDetail.objects.count() == 396
            and initial_saved_facts["globalFacts"] == EngineeringDerivedFact.objects.count() == 396
            and initial_saved_facts["calculationDetails"] == len(final_detail_rows) == 388
            and initial_saved_facts["calculationFacts"] == len(final_fact_rows) == 388
            and initial_saved_facts["detailHash"] == hashlib.sha256(canonical(final_detail_rows).encode("utf-8")).hexdigest()
            and initial_saved_facts["factHash"] == hashlib.sha256(canonical(final_fact_rows).encode("utf-8")).hexdigest()
            and rows(EngineeringCalculationRecord, where={"pk__in": (3, 4, 5, 6)}) == initial_calculations,
        )
        check(
            "29 migration ledger and files are unchanged",
            list(MigrationRecorder.Migration.objects.order_by("app", "name").values_list("app", "name")) == initial_migrations
            and sorted(str(path.relative_to(ROOT)) for path in ROOT.glob("backend/*/migrations/*.py")) == initial_migration_files,
        )
        connections.close_all()
        final_tables = table_fingerprints(isolated)
        changed = changed_tables(initial_tables, final_tables)
        check(
            "30 all changed tables are inside the formal write allowlist",
            changed <= ALLOWED_CHANGED_TABLES,
            {"changedTables": sorted(changed), "unexpected": sorted(changed - ALLOWED_CHANGED_TABLES)},
        )
        with sqlite3.connect(isolated) as raw:
            integrity = raw.execute("PRAGMA integrity_check").fetchall()
            foreign_keys = raw.execute("PRAGMA foreign_key_check").fetchall()
        check(
            "31 isolated database integrity and foreign keys pass",
            integrity == [("ok",)] and foreign_keys == [],
            {"integrity": integrity, "foreignKeys": foreign_keys},
        )
        source_hash_after = sha256(source)
        check(
            "32 source formal database stays byte-for-byte unchanged",
            source_hash_after == source_hash_before,
            {"before": source_hash_before, "after": source_hash_after},
        )
        result = {
            "gate": "pine 30x40 material and casing requirement isolated gate",
            "status": "PASS",
            "testCount": len(tests),
            "tests": tests,
            "sourceDatabase": str(source),
            "sourceDatabaseSha256Before": source_hash_before,
            "sourceDatabaseSha256After": source_hash_after,
            "sourceDatabaseUnchanged": source_hash_before == source_hash_after,
            "isolatedDatabaseSha256AfterFirstApply": isolated_hash_after_first,
            "material": first["material"],
            "requirements": requirement_payloads,
            "aggregatedCasingRow": pine_row,
            "bomPreview": preview,
            "changedTables": sorted(changed),
            "schemaChange": False,
            "migrationExecuted": False,
            "bomGenerated": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
