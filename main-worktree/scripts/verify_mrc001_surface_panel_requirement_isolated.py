"""Isolated-write gate for SO202609180003 MRC-001.

The source database is never opened by Django.  It is copied to a temporary
directory, and every preview/apply/readback assertion runs against that copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import site
import sys
import tempfile
from dataclasses import replace
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def configure(database: Path) -> None:
    site.addsitedir(str(BACKEND / "venv/Lib/site-packages"))
    sys.path.insert(0, str(BACKEND))
    os.environ["PCE_DATABASE_PATH"] = str(database)
    for key in (
        "PCE_DATABASE_IDENTITY",
        "PCE_RUNTIME_PROFILE",
        "PCE_NON_PRODUCTION_ACCEPTANCE",
        "PCE_RUNTIME_LAUNCHER_VERIFIED",
    ):
        os.environ.pop(key, None)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
    import django

    django.setup()


def expect_error(callable_, accepted_codes: set[str]):
    from pde.saved_fact_material_requirement_service import SavedFactMaterialRequirementError

    try:
        callable_()
    except SavedFactMaterialRequirementError as exc:
        if exc.code not in accepted_codes:
            raise AssertionError(f"unexpected error {exc.code}; expected {sorted(accepted_codes)}") from exc
        return {"code": exc.code, "message": exc.message}
    raise AssertionError(f"expected one of {sorted(accepted_codes)}")


def snapshot_scope():
    from pde.models import (
        BOMItem,
        BOMItemSourceRequirement,
        BOMVersion,
        EngineeringCalculationDetail,
        EngineeringCalculationRecord,
        EngineeringDerivedFact,
        EngineeringMaterialRequirement,
        ProductBOM,
        ProductDesignCompletionRecord,
        ProductDesignItem,
    )
    from sales.models import SalesOrder

    order = SalesOrder.objects.get(order_no="SO202609180003")
    calculations = list(EngineeringCalculationRecord.objects.filter(pk__in=(3, 4, 5, 6)).order_by("pk"))
    calculation_rows = [{
        "id": row.pk,
        "status": row.status,
        "resultHash": row.result_hash,
        "calculationNo": row.calculation_no,
        "salesOrderItemId": row.sales_order_item_id,
        "engineeringInstanceId": row.engineering_instance_id,
    } for row in calculations]
    target_ids = [row.pk for row in calculations]
    facts = list(EngineeringDerivedFact.objects.filter(
        calculation_id__in=target_ids,
    ).values(
        "id", "calculation_id", "source_detail_id", "fact_code", "canonical_field",
        "value", "uom_id", "status", "source_path", "trace",
    ).order_by("id"))
    details = list(EngineeringCalculationDetail.objects.filter(
        calculation_id__in=target_ids,
    ).values(
        "id", "calculation_id", "sequence", "output_name", "output_value",
        "uom_id", "rule_id", "rule_code", "rule_version", "status",
        "input_snapshot", "expression_snapshot", "dependency_snapshot",
        "precision", "rounding", "error_code", "error_message",
    ).order_by("id"))
    requirements_34 = list(EngineeringMaterialRequirement.objects.filter(
        calculation_id__in=(5, 6),
    ).values(
        "id", "calculation_id", "source_detail_id", "sequence", "material_id",
        "quantity_basis", "calculated_quantity", "order_quantity", "net_quantity",
        "gross_quantity", "uom_id", "scrap_rate", "scrap_rate_status", "source_path", "trace",
    ).order_by("id"))
    bom_headers = list(ProductBOM.objects.filter(
        order_engineering_instance__sales_order_item__sales_order=order,
    ).values("id", "bom_code", "order_engineering_instance_id").order_by("id"))
    versions = list(BOMVersion.objects.filter(
        source_calculation_id__in=(5, 6),
    ).values(
        "id", "bom_id", "bom_version", "status", "order_engineering_instance_id",
        "source_calculation_id",
    ).order_by("id"))
    version_ids = [row["id"] for row in versions]
    items = list(BOMItem.objects.filter(bom_version_id__in=version_ids).values(
        "id", "bom_version_id", "line_no", "material_id", "quantity", "uom_id",
        "scrap_rate", "scrap_rate_status",
    ).order_by("id"))
    item_ids = [row["id"] for row in items]
    links = list(BOMItemSourceRequirement.objects.filter(bom_item_id__in=item_ids).values(
        "id", "bom_item_id", "material_requirement_id", "contributed_quantity",
    ).order_by("id"))
    return {
        "calculationRows": calculation_rows,
        "detailCount": len(details),
        "detailHash": hashlib.sha256(canonical(details).encode("utf-8")).hexdigest(),
        "factCount": len(facts),
        "factHash": hashlib.sha256(canonical(facts).encode("utf-8")).hexdigest(),
        "productDesignItemCount": ProductDesignItem.objects.count(),
        "productDesignCompletionCount": ProductDesignCompletionRecord.objects.count(),
        "line34Requirements": requirements_34,
        "line34Boms": {
            "headers": bom_headers,
            "versions": versions,
            "items": items,
            "links": links,
        },
    }


def protected_order_snapshot():
    from pde.models import EngineeringCalculationRecord, OrderEngineeringInstance
    from sales.models import SalesOrder

    order = SalesOrder.objects.get(order_no="SO202610020004")
    return {
        "id": order.pk,
        "status": order.status,
        "businessPurpose": order.business_purpose,
        "instances": list(OrderEngineeringInstance.objects.filter(
            sales_order_item__sales_order=order,
        ).values("id", "instance_no", "status").order_by("id")),
        "calculations": list(EngineeringCalculationRecord.objects.filter(
            sales_order_item__sales_order=order,
        ).values("id", "calculation_no", "status", "result_hash").order_by("id")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    args = parser.parse_args()
    source = args.database.resolve()
    contract_path = args.contract.resolve()
    if not source.is_file() or not contract_path.is_file():
        raise RuntimeError("database or contract is missing")
    source_hash_before = sha256(source)
    contract_payload = json.loads(contract_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(
        prefix="pce-mrc001-isolated-", ignore_cleanup_errors=True,
    ) as directory:
        isolated = Path(directory) / "mrc001-isolated.sqlite3"
        shutil.copy2(source, isolated)
        if sha256(isolated) != source_hash_before:
            raise RuntimeError("isolated database copy hash mismatch")
        configure(isolated)

        from django.db import connections
        from django.db.migrations.recorder import MigrationRecorder
        from pde.management.commands.apply_saved_fact_material_requirement import _contract
        from pde.models import (
            BOMItem,
            BOMItemSourceRequirement,
            BOMVersion,
            EngineeringDerivedFact,
            EngineeringMaterialRequirement,
            ProductBOM,
        )
        from pde.saved_fact_material_requirement_service import (
            _resolve_context,
            apply_saved_fact_material_requirement,
            evaluate_contract_formula,
            preview_saved_fact_material_requirement,
            readback_saved_fact_material_requirement,
        )
        from pde.engineering_calculation_service import OrderEngineeringClosureService
        from pde.order_bom_handoff_service import order_bom_handoff
        from sales.models import SalesOrder
        from system.models import User

        contract = _contract(contract_payload)
        actor = User.objects.get(username="pce_plan_r12", is_active=True)
        order = SalesOrder.objects.get(order_no=contract.order_no)
        tests: list[dict] = []

        def check(name: str, condition: bool, evidence=None):
            if not condition:
                raise AssertionError(name)
            tests.append({"name": name, "status": "PASS", "evidence": evidence})

        initial = snapshot_scope()
        protected_before = protected_order_snapshot()
        migration_before = sorted(MigrationRecorder.Migration.objects.values_list("app", "name"))
        migration_files_before = sorted(
            str(path.relative_to(ROOT)) for path in ROOT.glob("backend/*/migrations/*.py")
        )
        db_hash_before_preview = sha256(isolated)
        preview = preview_saved_fact_material_requirement(user=actor, contract=contract)
        connections.close_all()
        check("01 preview is zero-write", sha256(isolated) == db_hash_before_preview and preview["databaseBusinessWriteCount"] == 0)
        check("02 formula quantity", preview["quantity"] == "3.475472", preview["quantity"])
        check("03 exact saved facts R/S/U", preview["factCodesUsed"] == ["R", "S", "U"], preview["facts"])
        check("04 W is preserved but unused", "W" not in preview["factCodesUsed"])
        check("05 X is preserved but unused", "X" not in preview["factCodesUsed"])
        check("06 sales-line quantity multiplier is absent", Decimal(preview["salesOrderItem"]["quantity"]) == Decimal("5") and preview["salesOrderItem"]["quantityMultiplierApplied"] is False)
        check("07 formal material and UOM", preview["material"]["id"] == 130 and preview["material"]["code"] == "MAT202608000048" and preview["material"]["uom"] == "m2")
        check("08 exact design/OEI/calculation lineage", preview["designItem"]["itemNo"] == contract.design_item_no and preview["oei"]["id"] == 2 and preview["calculation"]["id"] == 3)

        context = _resolve_context(user=actor, contract=contract, lock=False)
        missing_r = dict(context["inputValues"])
        missing_r.pop("R")
        missing_s = dict(context["inputValues"])
        missing_s.pop("S")
        invalid_u_zero = {key: dict(value) for key, value in context["inputValues"].items()}
        invalid_u_zero["U"]["value"] = "0"
        invalid_u_fraction = {key: dict(value) for key, value in context["inputValues"].items()}
        invalid_u_fraction["U"]["value"] = "1.5"
        check("09 missing R is blocked", expect_error(
            lambda: evaluate_contract_formula(contract, mapping_specification=context["mappingSpecification"], input_values=missing_r),
            {"SAVED_FACT_INPUT_MISSING"},
        )["code"] == "SAVED_FACT_INPUT_MISSING")
        check("10 missing S is blocked", expect_error(
            lambda: evaluate_contract_formula(contract, mapping_specification=context["mappingSpecification"], input_values=missing_s),
            {"SAVED_FACT_INPUT_MISSING"},
        )["code"] == "SAVED_FACT_INPUT_MISSING")
        check("11 invalid U zero is blocked", expect_error(
            lambda: evaluate_contract_formula(contract, mapping_specification=context["mappingSpecification"], input_values=invalid_u_zero),
            {"SAVED_FACT_INPUT_MUST_BE_POSITIVE"},
        )["code"] == "SAVED_FACT_INPUT_MUST_BE_POSITIVE")
        check("12 invalid U fraction is blocked", expect_error(
            lambda: evaluate_contract_formula(contract, mapping_specification=context["mappingSpecification"], input_values=invalid_u_fraction),
            {"SAVED_FACT_INPUT_MUST_BE_INTEGER"},
        )["code"] == "SAVED_FACT_INPUT_MUST_BE_INTEGER")
        check("13 missing or mismatched material is blocked", expect_error(
            lambda: preview_saved_fact_material_requirement(
                user=actor,
                contract=replace(contract, material_id=999999, material_code="MISSING"),
            ),
            {"DESIGN_MATERIAL_REFERENCE_MISMATCH", "MATERIAL_NOT_FOUND"},
        )["code"] in {"DESIGN_MATERIAL_REFERENCE_MISMATCH", "MATERIAL_NOT_FOUND"})
        check("14 material UOM mismatch is blocked", expect_error(
            lambda: preview_saved_fact_material_requirement(
                user=actor,
                contract=replace(contract, output_uom_code="mm"),
            ),
            {"MATERIAL_UOM_MISMATCH"},
        )["code"] == "MATERIAL_UOM_MISMATCH")
        check("15 calculation outside the adopted target scope is blocked", expect_error(
            lambda: preview_saved_fact_material_requirement(
                user=actor,
                contract=replace(contract, calculation_id=2),
            ),
            {
                "LEGACY_ADOPTION_SCOPE_MISMATCH", "CRM_ORDER_ADMISSION_REQUIRED",
                "CURRENT_CRM_ORDER_ADMISSION_REQUIRED", "LEGACY_INPUT_ADOPTION_SCOPE_MISMATCH",
                "CALCULATION_NOT_FOUND",
            },
        )["code"] in {
            "LEGACY_ADOPTION_SCOPE_MISMATCH", "CRM_ORDER_ADMISSION_REQUIRED",
            "CURRENT_CRM_ORDER_ADMISSION_REQUIRED", "LEGACY_INPUT_ADOPTION_SCOPE_MISMATCH",
            "CALCULATION_NOT_FOUND",
        })

        bom_before = {
            "headers": ProductBOM.objects.filter(order_engineering_instance__sales_order_item__sales_order=order).count(),
            "versions": BOMVersion.objects.filter(source_calculation__sales_order_item__sales_order=order).count(),
            "items": BOMItem.objects.filter(bom_version__source_calculation__sales_order_item__sales_order=order).count(),
            "links": BOMItemSourceRequirement.objects.filter(bom_item__bom_version__source_calculation__sales_order_item__sales_order=order).count(),
        }
        first = apply_saved_fact_material_requirement(user=actor, contract=contract)
        requirement = EngineeringMaterialRequirement.objects.get(pk=first["requirement"]["requirementId"])
        check("16 requirement persisted with exact quantity", requirement.net_quantity == contract.expected_quantity and requirement.calculated_quantity == contract.expected_quantity and requirement.gross_quantity == contract.expected_quantity)
        check("17 zero-loss and ORDER_TOTAL semantics", requirement.scrap_rate == 0 and requirement.scrap_rate_status == "maintained" and requirement.quantity_basis == "ORDER_TOTAL" and requirement.order_quantity == 5)
        check("18 released Mapping and full provenance", first["requirement"]["mapping"]["status"] == "released" and [row["factCode"] for row in requirement.trace["sourceFacts"]] == ["R", "S", "U"] and requirement.trace["orderQuantityMultiplierApplied"] is False)
        direct_bom_preview = OrderEngineeringClosureService.preview_bom(
            user=actor, calculation_id=contract.calculation_id,
        )
        check("19 no BOM was generated", first["bomGenerated"] is False and direct_bom_preview["rowCount"] == 1 and direct_bom_preview["rows"][0]["sourceRequirementIds"] == [requirement.pk] and bom_before == {
            "headers": ProductBOM.objects.filter(order_engineering_instance__sales_order_item__sales_order=order).count(),
            "versions": BOMVersion.objects.filter(source_calculation__sales_order_item__sales_order=order).count(),
            "items": BOMItem.objects.filter(bom_version__source_calculation__sales_order_item__sales_order=order).count(),
            "links": BOMItemSourceRequirement.objects.filter(bom_item__bom_version__source_calculation__sales_order_item__sales_order=order).count(),
        })
        readback = readback_saved_fact_material_requirement(user=actor, contract=contract)
        connections.close_all()
        hash_after_first = sha256(isolated)
        replay = apply_saved_fact_material_requirement(user=actor, contract=contract)
        connections.close_all()
        check("20 idempotent replay is byte-for-byte zero-write", replay["idempotent"] is True and replay["businessWriteCount"] == 0 and sha256(isolated) == hash_after_first)
        check("21 readback matches formal identity", readback["requirement"]["requirementId"] == requirement.pk and readback["requirement"]["mapping"]["ruleCode"] == contract.mapping_rule_code)

        final = snapshot_scope()
        check("22 71 objects / 388 facts and calculations are unchanged", initial["productDesignItemCount"] == final["productDesignItemCount"] == 71 and initial["productDesignCompletionCount"] == final["productDesignCompletionCount"] == 71 and initial["detailCount"] == final["detailCount"] == 388 and initial["factCount"] == final["factCount"] == 388 and initial["detailHash"] == final["detailHash"] and initial["factHash"] == final["factHash"] and initial["calculationRows"] == final["calculationRows"])
        migration_after = sorted(MigrationRecorder.Migration.objects.values_list("app", "name"))
        migration_files_after = sorted(
            str(path.relative_to(ROOT)) for path in ROOT.glob("backend/*/migrations/*.py")
        )
        handoff = order_bom_handoff(user=actor, order_id=order.pk)
        line1 = next(row for row in handoff["records"] if row["lineNo"] == 1)
        line1_missing = [
            obj["objectNo"] for obj in line1["objects"]
            if not obj["formalMaterialRequirementCount"]
        ]
        mrc001_projection = next(
            row for row in handoff["materialRequirementPreview"]["mappingCandidates"]
            if row["code"] == contract.mapping_rule_code
        )
        mrc001_card = next(
            row for row in handoff["materialRequirementPreview"]["businessConfirmationPackage"]["mappingCards"]
            if row["designItem"]["objectNo"] == contract.design_item_no
        )
        check("23 line3/4, protected order, schema, and next-blocker projection are correct", initial["line34Requirements"] == final["line34Requirements"] and initial["line34Boms"] == final["line34Boms"] and protected_before == protected_order_snapshot() and migration_before == migration_after and migration_files_before == migration_files_after and sum(bool(obj["formalMaterialRequirementCount"]) for obj in line1["objects"]) == 1 and line1_missing[0] == "SO202609180003-DES-01-SRC-0004" and mrc001_projection["contractStatus"] == "READY" and mrc001_card["currentStatus"] == "CONFIRMED")

        final_facts = list(EngineeringDerivedFact.objects.filter(
            calculation_id=3,
            canonical_field__in=("R", "S", "U", "W", "X"),
        ).values("id", "canonical_field", "value", "uom_id").order_by("id"))
        connections.close_all()
        source_hash_after = sha256(source)
        result = {
            "gate": "MRC-001 surface-panel saved-fact requirement isolated gate",
            "status": "PASS",
            "testCount": len(tests),
            "tests": tests,
            "sourceDatabase": str(source),
            "sourceDatabaseSha256Before": source_hash_before,
            "sourceDatabaseSha256After": source_hash_after,
            "sourceDatabaseUnchanged": source_hash_before == source_hash_after,
            "isolatedDatabaseSha256Before": db_hash_before_preview,
            "isolatedDatabaseSha256AfterWrite": hash_after_first,
            "firstApply": first,
            "readback": readback,
            "directBomPreview": direct_bom_preview,
            "line1Coverage": {
                "objectCount": line1["objectCount"],
                "coveredObjectCount": sum(bool(obj["formalMaterialRequirementCount"]) for obj in line1["objects"]),
                "missingObjectNos": line1_missing,
                "firstRealBlocker": line1_missing[0],
                "mrc001MappingProjection": mrc001_projection["contractStatus"],
                "mrc001ConfirmationProjection": mrc001_card["currentStatus"],
            },
            "idempotentReplay": replay,
            "finalFacts": final_facts,
            "protectedScope": {
                "line34Requirements": final["line34Requirements"],
                "line34Boms": final["line34Boms"],
                "SO202610020004": protected_order_snapshot(),
            },
            "schemaChange": False,
            "migrationExecuted": False,
            "bomGenerated": False,
        }
        if source_hash_before != source_hash_after:
            raise AssertionError("source database changed during isolated gate")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
