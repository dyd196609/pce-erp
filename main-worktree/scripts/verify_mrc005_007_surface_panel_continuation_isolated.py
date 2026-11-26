"""Independent isolated gate for DES-01-SRC-0005..0007 Requirement continuation.

The formal database is copied before Django is configured.  Every simulated
write runs against the temporary ``*-isolated.sqlite3`` copy.  The protected
source database is hash checked before and after the gate.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import site
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PROTECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
ORDER_NO = "SO202609180003"
CALCULATION_ID = 3
ACTOR = "pce_plan_r12"
TARGETS = (
    {
        "suffix": "0005", "mapping": "MRC-005", "itemNo": f"{ORDER_NO}-DES-01-SRC-0005",
        "facts": ("2002.000000", "813.000000", "1.000000"),
        "quantity": Decimal("3.255252"), "priorRevision": 2,
        "contract": "PCE_SO202609180003_MRC005_SURFACE_PANEL_MAPPING_CONTRACT_V1.json",
    },
    {
        "suffix": "0006", "mapping": "MRC-006", "itemNo": f"{ORDER_NO}-DES-01-SRC-0006",
        "facts": ("2002.000000", "748.000000", "1.000000"),
        "quantity": Decimal("2.994992"), "priorRevision": 3,
        "contract": "PCE_SO202609180003_MRC006_SURFACE_PANEL_MAPPING_CONTRACT_V1.json",
    },
    {
        "suffix": "0007", "mapping": "MRC-007", "itemNo": f"{ORDER_NO}-DES-01-SRC-0007",
        "facts": ("2007.000000", "765.000000", "1.000000"),
        "quantity": Decimal("3.070710"), "priorRevision": 3,
        "contract": "PCE_SO202609180003_MRC007_SURFACE_PANEL_MAPPING_CONTRACT_V1.json",
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def configure(database: Path) -> None:
    if database == PROTECTED_DATABASE or not database.name.endswith("isolated.sqlite3"):
        raise RuntimeError("Django may only open an explicit isolated database copy")
    site.addsitedir(str(BACKEND / "venv/Lib/site-packages"))
    sys.path.insert(0, str(BACKEND))
    os.environ["PCE_DATABASE_PATH"] = str(database)
    for key in (
        "PCE_DATABASE_IDENTITY", "PCE_RUNTIME_PROFILE", "PCE_NON_PRODUCTION_ACCEPTANCE",
        "PCE_RUNTIME_LAUNCHER_VERIFIED",
    ):
        os.environ.pop(key, None)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
    import django

    django.setup()


def model_rows(model, queryset=None):
    queryset = queryset if queryset is not None else model.objects.all()
    fields = [field.attname for field in model._meta.concrete_fields]
    return list(queryset.values(*fields).order_by("pk"))


def protected_anchor_snapshot():
    from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
    from pde.models import EngineeringMaterialRequirement, EngineeringRuleDefinition, ProductDesignRevision
    from system.models import OrganizationOperatingAuditRecord

    return {
        "material130": model_rows(Material, Material.objects.filter(pk=130)),
        "rules15and16": model_rows(EngineeringRuleDefinition, EngineeringRuleDefinition.objects.filter(pk__in=(15, 16))),
        "requirements3and4": model_rows(EngineeringMaterialRequirement, EngineeringMaterialRequirement.objects.filter(pk__in=(3, 4))),
        "revision9": model_rows(ProductDesignRevision, ProductDesignRevision.objects.filter(pk=27)),
        "audits": model_rows(OrganizationOperatingAuditRecord, OrganizationOperatingAuditRecord.objects.filter(pk__range=(2706, 2717))),
        "actionRequests": model_rows(MasterDataWriteRequest, MasterDataWriteRequest.objects.filter(pk__range=(2040, 2047))),
        "externalIdentities": model_rows(ExternalIdentity, ExternalIdentity.objects.filter(pk__range=(2041, 2044))),
    }


def calculation_snapshot():
    from pde.models import EngineeringCalculationDetail, EngineeringCalculationRecord, EngineeringDerivedFact

    records = model_rows(EngineeringCalculationRecord, EngineeringCalculationRecord.objects.filter(pk__in=(1, 2, 3, 4, 5, 6)))
    details = model_rows(EngineeringCalculationDetail)
    facts = model_rows(EngineeringDerivedFact)
    return {
        "recordHash": hashlib.sha256(canonical(records).encode()).hexdigest(),
        "detailCount": len(details), "detailHash": hashlib.sha256(canonical(details).encode()).hexdigest(),
        "factCount": len(facts), "factHash": hashlib.sha256(canonical(facts).encode()).hexdigest(),
        "detailCounts3to6": {str(pk): sum(row["calculation_id"] == pk for row in details) for pk in (3, 4, 5, 6)},
        "factCounts3to6": {str(pk): sum(row["calculation_id"] == pk for row in facts) for pk in (3, 4, 5, 6)},
    }


def design_history(item):
    from pde.models import ProductDesignRevision

    return model_rows(ProductDesignRevision, ProductDesignRevision.objects.filter(design_item=item))


def protected_design_shape(revision):
    matches = dict(revision.master_match_results or {})
    matches.pop("material", None)
    return {
        "nature": revision.design_nature,
        "length": str(revision.design_length), "width": str(revision.design_width),
        "thickness": str(revision.design_thickness), "uomId": revision.design_uom_id,
        "materialProcessId": revision.material_process_type_id,
        "paintProcessId": revision.paint_process_type_id, "edgeMethodId": revision.edge_method_id,
        "designData": revision.design_data, "sourceProvenance": revision.source_provenance,
        "masterMatchesExceptMaterial": matches, "legacySourceRecordId": revision.legacy_source_record_id,
    }


def protected_bom_snapshot():
    from pde.models import BOMItem, BOMItemSourceRequirement, BOMVersion, ProductBOM

    versions = BOMVersion.objects.filter(source_calculation_id__in=(5, 6))
    return {
        "headers": model_rows(ProductBOM, ProductBOM.objects.filter(pk__in=(1, 2))),
        "versions": model_rows(BOMVersion, versions),
        "items": model_rows(BOMItem, BOMItem.objects.filter(bom_version__in=versions)),
        "links": model_rows(BOMItemSourceRequirement, BOMItemSourceRequirement.objects.filter(bom_item__bom_version__in=versions)),
    }


def cancelled_order_snapshot():
    from pde.models import EngineeringCalculationRecord, OrderEngineeringInstance, ProductBOM, ProductDesignItem
    from sales.models import SalesOrder

    order = SalesOrder.objects.get(order_no="SO202610020004")
    return {
        "id": order.pk, "status": order.status,
        "sourceCount": ProductDesignItem.objects.filter(sales_order_item__sales_order=order).values("source_record_id").distinct().count(),
        "designCount": ProductDesignItem.objects.filter(sales_order_item__sales_order=order).count(),
        "instances": list(OrderEngineeringInstance.objects.filter(sales_order_item__sales_order=order).values("id", "instance_no", "status").order_by("id")),
        "calculations": list(EngineeringCalculationRecord.objects.filter(sales_order_item__sales_order=order).values("id", "calculation_no", "status").order_by("id")),
        "boms": list(ProductBOM.objects.filter(order_engineering_instance__sales_order_item__sales_order=order).values("id", "bom_code").order_by("id")),
    }


def line1_coverage(user, order):
    from pde.order_bom_handoff_service import order_bom_handoff

    handoff = order_bom_handoff(
        user=user, order_id=order.pk, calculation_id=CALCULATION_ID,
    )
    line1 = next(row for row in handoff["records"] if row["lineNo"] == 1)
    covered = sum(bool(row["formalMaterialRequirementCount"]) for row in line1["objects"])
    missing = [row["objectNo"] for row in line1["objects"] if not row["formalMaterialRequirementCount"]]
    return handoff, line1, covered, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    source = args.database.resolve()
    if not source.is_file():
        raise RuntimeError("database is missing")
    source_hash_before = sha256(source)

    with tempfile.TemporaryDirectory(prefix="pce-mrc005-007-", ignore_cleanup_errors=True) as directory:
        isolated = Path(directory) / "mrc005-007-isolated.sqlite3"
        shutil.copy2(source, isolated)
        if sha256(isolated) != source_hash_before:
            raise RuntimeError("isolated database copy hash mismatch")
        configure(isolated)

        from django.db import connection, connections
        from django.db.migrations.recorder import MigrationRecorder
        from masterdata.models import Material
        from pde.engineering_calculation_service import OrderEngineeringClosureService
        from pde.management.commands.apply_saved_fact_material_requirement import _contract
        from pde.models import (
            BOMItem, BOMItemSourceRequirement, BOMVersion, EngineeringDerivedFact,
            EngineeringMaterialRequirement, EngineeringRuleDefinition, LegacyInFlightOrderAdoption,
            ProductBOM, ProductDesignItem,
        )
        from pde.product_design_service import ACTION_DESIGN_SAVE, _authorize as design_authorize, save_design_content
        from pde.saved_fact_material_requirement_service import (
            _actor_context, apply_saved_fact_material_requirement,
            preview_saved_fact_material_requirement, readback_saved_fact_material_requirement,
        )
        from sales.models import SalesOrder
        from system.models import Permission, RolePermission, User, UserRoleScopeAssignment

        tests = []

        def check(name, condition, evidence=None):
            if not condition:
                raise AssertionError(f"{name}: {canonical(evidence)}")
            tests.append({"name": name, "status": "PASS", "evidence": evidence})

        order = SalesOrder.objects.get(order_no=ORDER_NO)
        actor = User.objects.get(username=ACTOR, is_active=True)
        contracts = []
        for target in TARGETS:
            path = ROOT / "docs/governance/evidence" / target["contract"]
            contracts.append(_contract(json.loads(path.read_text(encoding="utf-8"))))

        initial_anchors = protected_anchor_snapshot()
        initial_calculations = calculation_snapshot()
        initial_boms = protected_bom_snapshot()
        initial_cancelled = cancelled_order_snapshot()
        initial_adoption = model_rows(LegacyInFlightOrderAdoption)
        initial_permissions = {
            "permissions": model_rows(Permission), "rolePermissions": model_rows(RolePermission),
            "roleScopes": model_rows(UserRoleScopeAssignment),
        }
        initial_migrations = sorted(MigrationRecorder.Migration.objects.values_list("app", "name"))
        initial_migration_files = sorted(str(path.relative_to(ROOT)) for path in ROOT.glob("backend/*/migrations/*.py"))
        initial_bom_counts = (ProductBOM.objects.count(), BOMVersion.objects.count(), BOMItem.objects.count(), BOMItemSourceRequirement.objects.count())

        check("01 isolated copy matches protected source", sha256(isolated) == source_hash_before)
        check(
            "02 global 396 and order Calculation 3-6 388 scopes are intact",
            initial_calculations["detailCount"] == 396 and initial_calculations["factCount"] == 396
            and initial_calculations["detailCounts3to6"] == {"3": 85, "4": 51, "5": 248, "6": 4}
            and initial_calculations["factCounts3to6"] == {"3": 85, "4": 51, "5": 248, "6": 4},
            initial_calculations,
        )
        materials = list(Material.objects.filter(pk__in=(130, 136, 137, 138)).values("id", "code", "is_active", "base_uom_id"))
        check(
            "03 Material 130 is the only active canonical identity",
            next(row for row in materials if row["id"] == 130)["is_active"] is True
            and all(not row["is_active"] for row in materials if row["id"] != 130), materials,
        )
        occupied = set(EngineeringRuleDefinition.objects.filter(rule_code__startswith=f"MRM.{ORDER_NO}.MRC-").values_list("rule_code", flat=True))
        check(
            "04 historical MRC-003 and MRC-004 stay occupied; MRC-005..007 are free",
            {f"MRM.{ORDER_NO}.MRC-003", f"MRM.{ORDER_NO}.MRC-004"}.issubset(occupied)
            and not {f"MRM.{ORDER_NO}.MRC-005", f"MRM.{ORDER_NO}.MRC-006", f"MRM.{ORDER_NO}.MRC-007"} & occupied,
            sorted(occupied),
        )
        check(
            "05 MRC-001, MRC-002, Material 130, and Revision 9 anchors exist",
            [row["id"] for row in initial_anchors["rules15and16"]] == [15, 16]
            and [row["id"] for row in initial_anchors["requirements3and4"]] == [3, 4]
            and initial_anchors["requirements3and4"][0]["net_quantity"] == Decimal("3.475472")
            and initial_anchors["requirements3and4"][1]["net_quantity"] == Decimal("3.155152")
            and initial_anchors["revision9"][0]["id"] == 27,
        )

        actor_decision = design_authorize(actor, ACTION_DESIGN_SAVE)
        actor_context = _actor_context(user=actor, order=order)
        check(
            "06 pce_plan_r12 is an authorized non-admin active formal employee",
            not actor.is_superuser and actor_decision["allowed"] is True
            and actor_context["employeeId"] == 107 and actor_context["positionId"] == 31
            and actor_context["departmentId"] == 15
            and actor_context["workflowResponsibility"]["responsibilityCode"] == "RESP_PMC_PLAN_001",
            {"authorization": actor_decision, "actor": actor_context},
        )

        initial_histories = {}
        for index, target in enumerate(TARGETS, 7):
            item = ProductDesignItem.objects.get(item_no=target["itemNo"])
            latest = item.design_revisions.order_by("-revision", "-pk").first()
            facts = list(EngineeringDerivedFact.objects.filter(
                calculation_id=CALCULATION_ID, trace__designItemNo=item.item_no,
                canonical_field__in=("R", "S", "U", "W", "X"),
            ).select_related("uom").order_by("sequence"))
            values = {row.canonical_field: str((row.value or {}).get("decimal")) for row in facts}
            initial_histories[item.item_no] = design_history(item)
            check(
                f"{index:02d} {target['suffix']} owns its R/S/U and has no conflicting Material fact",
                item.sales_order_item_id == 3 and item.source_record_id == 11
                and latest.revision == target["priorRevision"] and latest.material_id is None
                and (values["R"], values["S"], values["U"]) == target["facts"]
                and values["W"] and values["X"],
                {"itemId": item.pk, "revisionId": latest.pk, "values": values},
            )

        operation_results = []
        expected_missing = [target["itemNo"] for target in TARGETS]
        for offset, (target, contract) in enumerate(zip(TARGETS, contracts), 10):
            item = ProductDesignItem.objects.get(item_no=target["itemNo"])
            old_latest = item.design_revisions.order_by("-revision", "-pk").first()
            old_shape = protected_design_shape(old_latest)
            reason = (
                f"用户已确认当前门板正式材料为唯一Canonical Material 130；{target['itemNo']}"
                "属于行1门扇表面板材范围，历史Material为空且无另一条显式冲突材料事实。"
                "本次仅新增正式Revision补齐Material引用，保留QSFB/FM、清水封闭、LC-M045及其他设计事实。"
            )
            design_key = f"{ORDER_NO}:DES{target['suffix']}:MATERIAL-NULL-TO-130:V1"
            _, replayed = save_design_content(
                user=actor,
                payload={
                    "designItemIds": [item.pk], "expectedVersions": {str(item.pk): item.version},
                    "designNature": "FORMAL", "reason": reason, "designData": {"materialId": 130},
                },
                idempotency_key=design_key,
            )
            item.refresh_from_db()
            new_latest = item.design_revisions.order_by("-revision", "-pk").first()
            check(
                f"{offset:02d} {target['suffix']} appends a Material-only formal Revision with the non-admin actor",
                replayed is False and new_latest.revision == old_latest.revision + 1
                and new_latest.material_id == 130 and new_latest.created_by_id == actor.pk
                and design_history(item)[:len(initial_histories[item.item_no])] == initial_histories[item.item_no]
                and protected_design_shape(new_latest) == old_shape,
                {"oldRevisionId": old_latest.pk, "newRevisionId": new_latest.pk, "newRevision": new_latest.revision},
            )

            preview = preview_saved_fact_material_requirement(user=actor, contract=contract)
            check(
                f"{offset + 1:02d} {target['mapping']} preview uses only R/S/U, no W/X and no sales-line multiplier",
                tuple(row["value"] for row in preview["facts"]) == target["facts"]
                and preview["factCodesUsed"] == ["R", "S", "U"]
                and Decimal(preview["quantity"]) == target["quantity"]
                and preview["material"]["id"] == 130 and preview["material"]["uom"] == "m2"
                and preview["salesOrderItem"]["quantityMultiplierApplied"] is False
                and preview["legacyAdoption"]["id"] == 1,
                preview,
            )

            first = apply_saved_fact_material_requirement(user=actor, contract=contract)
            readback = readback_saved_fact_material_requirement(user=actor, contract=contract)
            connections.close_all()
            isolated_hash_after_first = sha256(isolated)
            replay = apply_saved_fact_material_requirement(user=actor, contract=contract)
            connections.close_all()
            requirement = EngineeringMaterialRequirement.objects.get(pk=first["requirement"]["requirementId"])
            mapping = EngineeringRuleDefinition.objects.get(pk=first["requirement"]["mapping"]["id"])
            check(
                f"{offset + 2:02d} {target['mapping']} persists an independent released Mapping/Requirement and replays at zero write",
                mapping.rule_code == f"MRM.{ORDER_NO}.{target['mapping']}" and mapping.status == "released"
                and requirement.material_id == 130 and requirement.net_quantity == target["quantity"]
                and requirement.gross_quantity == target["quantity"] and requirement.scrap_rate == 0
                and requirement.trace["designItemNo"] == target["itemNo"]
                and requirement.trace["structureRole"] == "DOOR_LEAF_SURFACE_PANEL"
                and requirement.trace["wUsedAsQuantityBasis"] is False
                and requirement.trace["xUsedAsMaterialQuantityBasis"] is False
                and requirement.trace["orderQuantityMultiplierApplied"] is False
                and readback["readbackMatch"] is True and replay["idempotent"] is True
                and replay["businessWriteCount"] == 0 and sha256(isolated) == isolated_hash_after_first,
                {"first": first, "readback": readback, "replay": replay},
            )

            direct = OrderEngineeringClosureService.preview_bom(user=actor, calculation_id=CALCULATION_ID)
            handoff, line1, covered, missing = line1_coverage(actor, order)
            expected_missing = expected_missing[1:]
            check(
                f"{offset + 3:02d} post-{target['suffix']} readback gives sequential line-1 coverage {covered}/5",
                line1["objectCount"] == 5 and covered == (offset - 7)
                and missing == expected_missing and direct["sourceRequirementCount"] == covered,
                {"covered": covered, "missing": missing, "previewHash": direct["previewHash"]},
            )
            operation_results.append({
                "target": target, "designRevisionId": new_latest.pk, "mappingId": mapping.pk,
                "requirementId": requirement.pk, "preview": preview, "apply": first,
                "readback": readback, "replay": replay, "bomPreview": direct,
                "line1Coverage": covered, "missing": missing,
                "handoffGate": handoff["bomHandoffStatus"],
            })

        final_preview = OrderEngineeringClosureService.preview_bom(user=actor, calculation_id=CALCULATION_ID)
        final_handoff, final_line1, final_covered, final_missing = line1_coverage(actor, order)
        final_gate = final_handoff["bomHandoffStatus"]
        check(
            "22 five independent Requirements aggregate exactly with full provenance",
            final_preview["sourceRequirementCount"] == 5 and final_preview["rowCount"] == 1
            and final_preview["rows"][0]["sourceRequirementIds"] == [3, 4, 5, 6, 7]
            and final_preview["rows"][0]["sourceDesignItemNos"] == [
                f"{ORDER_NO}-DES-01-SRC-{suffix:04d}" for suffix in range(3, 8)
            ]
            and Decimal(final_preview["rows"][0]["quantity"]) == Decimal("15.951578"),
            final_preview,
        )
        check(
            "23 target coverage is 5/5, order 7/71 is informational, and casing is the real blocker",
            final_line1["objectCount"] == 5 and final_covered == 5 and not final_missing
            and final_gate["canGenerate"] is False
            and final_gate["targetCoverageGate"] == "PASS"
            and final_gate["targetScope"]["coveredDesignItemCount"] == 5
            and final_gate["targetScope"]["designItemCount"] == 5
            and final_gate["code"] == "CASING_MATERIAL_REQUIREMENT_MISSING"
            and final_gate["formalRequirementObjectCount"] == 7
            and final_gate["remainingObjectCount"] == 64
            and final_gate["orderScope"]["totalCoveredCount"] == 7
            and final_gate["orderScope"]["totalDesignItemCount"] == 71
            and final_gate["orderScope"]["gateRole"] == "INFORMATIONAL"
            and final_gate["missingConditions"][0]["code"] == "CASING_MATERIAL_REQUIREMENT_MISSING",
            final_gate,
        )
        check(
            "24 BOM generation is not invoked unless 5/5, READY, and canGenerate are all true",
            final_covered == 5 and final_gate["canGenerate"] is False
            and (ProductBOM.objects.count(), BOMVersion.objects.count(), BOMItem.objects.count(), BOMItemSourceRequirement.objects.count()) == initial_bom_counts,
            {"predicates": {"coverage5of5": True, "bomInputReadiness": "BLOCKED", "canGenerate": False}},
        )
        check("25 MRC-001/MRC-002, Material 130 and Revision 9 remain byte-for-byte protected", protected_anchor_snapshot() == initial_anchors)
        check("26 completed calculations and all 396 saved Detail/Fact rows remain byte-for-byte protected", calculation_snapshot() == initial_calculations)
        check("27 line-3/4 BOM IDs, statuses, items, quantities and Requirement links remain protected", protected_bom_snapshot() == initial_boms)
        check(
            "28 Legacy Adoption 1 and cancelled SO202610020004 isolation remain protected",
            model_rows(LegacyInFlightOrderAdoption) == initial_adoption
            and cancelled_order_snapshot() == initial_cancelled
            and initial_cancelled["status"] == "cancelled" and initial_cancelled["sourceCount"] == 0
            and initial_cancelled["designCount"] == 0 and not initial_cancelled["calculations"] and not initial_cancelled["boms"],
            initial_cancelled,
        )
        final_permissions = {
            "permissions": model_rows(Permission), "rolePermissions": model_rows(RolePermission),
            "roleScopes": model_rows(UserRoleScopeAssignment),
        }
        check(
            "29 permissions, migration ledger and migration files remain unchanged",
            final_permissions == initial_permissions
            and sorted(MigrationRecorder.Migration.objects.values_list("app", "name")) == initial_migrations
            and sorted(str(path.relative_to(ROOT)) for path in ROOT.glob("backend/*/migrations/*.py")) == initial_migration_files,
        )
        with connection.cursor() as cursor:
            integrity = cursor.execute("PRAGMA integrity_check").fetchall()
            foreign_keys = cursor.execute("PRAGMA foreign_key_check").fetchall()
        check("30 isolated database integrity and foreign keys pass", integrity == [("ok",)] and foreign_keys == [], {"integrity": integrity, "foreignKeys": foreign_keys})
        source_hash_after = sha256(source)
        check("31 protected source database stays byte-for-byte unchanged", source_hash_after == source_hash_before, {"before": source_hash_before, "after": source_hash_after})

        result = {
            "gate": "MRC-005..007 surface-panel continuation isolated gate",
            "status": "PASS", "testCount": len(tests), "tests": tests,
            "sourceDatabase": str(source), "sourceDatabaseSha256Before": source_hash_before,
            "sourceDatabaseSha256After": source_hash_after, "sourceDatabaseUnchanged": source_hash_before == source_hash_after,
            "actor": {"username": actor.username, "authorization": actor_decision, "context": actor_context},
            "operations": operation_results,
            "finalPreview": final_preview, "finalHandoffGate": final_gate,
            "line1Coverage": {"covered": final_covered, "total": final_line1["objectCount"], "missing": final_missing},
            "bomGenerated": False,
            "firstRealBomBlocker": {
                "code": final_gate["missingConditions"][0]["code"],
                "serviceCode": final_gate["code"], "canGenerate": final_gate["canGenerate"],
                "reason": final_gate["missingConditions"][0]["message"],
            },
            "calculationBaseline": initial_calculations,
            "schemaChange": False, "migrationExecuted": False, "permissionChanged": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
