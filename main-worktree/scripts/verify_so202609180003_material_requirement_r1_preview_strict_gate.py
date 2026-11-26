"""Completed Work STRICT Gate for the R1 no-recalc material requirement preview."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

from verify_engineering_runtime_closure_strict_gate import (
    configure_django,
    database_snapshot,
    protected_formal_order_facts,
    target_facts,
)


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require(condition: bool, message: str, risks: list[str]) -> None:
    if not condition:
        risks.append(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    database_path = args.database.resolve()
    risks: list[str] = []
    require(database_path.is_file(), "acceptance database is missing", risks)
    before_hash = sha256(database_path) if database_path.is_file() else ""

    page_path = ROOT / "frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue"
    api_path = ROOT / "frontend/src/api/pde.js"
    service_path = ROOT / "backend/pde/order_bom_handoff_service.py"
    page = page_path.read_text(encoding="utf-8")
    api = api_path.read_text(encoding="utf-8")
    service_source = service_path.read_text(encoding="utf-8")
    tree = ast.parse(service_source)
    mutating_calls = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    } & {"save", "create", "update", "delete", "bulk_create", "get_or_create", "execute", "generate_bom", "next_code"}
    require(not mutating_calls, f"preview service contains prohibited mutating calls: {sorted(mutating_calls)}", risks)
    for token in (
        'data-section="material-requirement-handoff-preview"',
        'data-preview-mode="r1-no-recalc-zero-write"',
        'data-section="material-mapping-business-confirmation-package"',
        'data-confirmation-only="true"',
        "19个业务材料组",
        "没有保存、确认、批准或发布动作",
        "Preview候选不替代EngineeringMaterialRequirement",
        "materialRequirementHandoff: materialRequirementHandoff.value",
    ):
        require(token in page, f"formal material page preview contract missing: {token}", risks)
    require("orderBomHandoff(params = {})" in api and "params: { handoff: 1, ...params }" in api,
            "frontend read-only handoff API contract missing", risks)

    before_counts: dict[str, int] = {}
    after_counts: dict[str, int] = {}
    target: dict[str, object] = {}
    preview: dict[str, object] = {}
    confirmation: dict[str, object] = {}
    current_comparison: dict[str, object] = {}
    protected_order: dict[str, object] = {}
    target_bom = {}
    released_rule_domains = []
    if not risks:
        configure_django(database_path)
        from django.db import connection, connections
        from pde.calculation_batch_reuse import design_calculation_context
        from pde.models import BOMItem, BOMVersion, EngineeringRuleDefinition, ProductBOM
        from pde.order_bom_handoff_service import order_bom_handoff
        from sales.models import SalesOrder
        from system.models import User

        connection.cursor().execute("PRAGMA query_only = ON")
        admin = User.objects.filter(username="admin").first()
        require(admin is not None, "acceptance admin user is missing", risks)
        if admin:
            before_counts = database_snapshot()
            target = target_facts()
            order = SalesOrder.objects.get(order_no="SO202609180003")
            response = order_bom_handoff(user=admin, order_id=order.pk)
            preview = response["materialRequirementPreview"]
            confirmation = preview.get("businessConfirmationPackage") or {}
            projection = design_calculation_context(admin, 11)
            calculation = (projection.get("draft") or {}).get("currentInputCalculation") or {}
            current_comparison = {
                "comparisonSummary": calculation.get("comparisonSummary"),
                "historicalAcceptanceRegression": calculation.get("historicalAcceptanceRegression"),
            }
            target_bom = {
                "productBom": ProductBOM.objects.filter(
                    order_engineering_instance__sales_order_item__sales_order=order,
                ).count(),
                "bomVersion": BOMVersion.objects.filter(
                    bom__order_engineering_instance__sales_order_item__sales_order=order,
                ).count(),
                "bomItem": BOMItem.objects.filter(
                    bom_version__bom__order_engineering_instance__sales_order_item__sales_order=order,
                ).count(),
            }
            for rule in EngineeringRuleDefinition.objects.filter(company_id=order.company_id, status="released"):
                released_rule_domains.append({
                    "id": rule.pk, "code": rule.rule_code,
                    "domains": sorted({
                        output.get("resultDomain", "DERIVED_FACT")
                        for output in (rule.specification or {}).get("outputs", [])
                    }),
                })
            protected_order = protected_formal_order_facts()
            after_counts = database_snapshot()
        connections.close_all()

    after_hash = sha256(database_path) if database_path.is_file() else ""
    require(before_hash == after_hash, "acceptance database hash changed", risks)
    require(before_counts == after_counts, "database model counts changed", risks)
    require(target.get("businessPurpose") == "DEVELOPMENT_VALIDATION", "target business purpose drift", risks)
    require(target.get("calculationCount") == 4 and target.get("completedCalculationCount") == 4,
            "completed calculation count drift", risks)
    require(target.get("detailCount") == 388 and target.get("derivedFactCount") == 388,
            "388 saved calculation facts drift", risks)
    require(target.get("materialRequirementCount") == 0 and target.get("operationRequirementCount") == 0,
            "formal requirement count drift", risks)
    require(target_bom == {"productBom": 0, "bomVersion": 0, "bomItem": 0}, "target BOM count drift", risks)
    require(preview.get("objectCount") == 71 and preview.get("classificationClosed") is True,
            "71-object preview does not close", risks)
    require(preview.get("classificationCounts") == {
        "READY_FOR_REQUIREMENT": 0,
        "MISSING_MATERIAL": 67,
        "MISSING_MAPPING": 4,
        "MISSING_UOM": 0,
        "AMBIGUOUS_MATERIAL": 0,
        "MISSING_QUANTITY_CONTRACT": 0,
        "NOT_APPLICABLE": 0,
    }, "material preview classification drift", risks)
    require(preview.get("metrics") == {
        "formalMaterialReferencedCount": 4,
        "missingMaterialCount": 67,
        "physicalUomCompleteCount": 70,
        "physicalUomMissingCount": 1,
        "sourceMaterialAnalysisCounts": {
            "UNIQUE_EXISTING_REQUIRES_CONFIRMATION": 0,
            "AMBIGUOUS_MATERIAL": 0,
            "NO_FORMAL_MATERIAL": 0,
            "NON_PURE_MATERIAL_CODE": 67,
            "FORMAL_MATERIAL_BOUND": 4,
        },
    }, "material/UOM/source-code metrics drift", risks)
    direct = {
        row["objectNo"]: row["material"]["code"]
        for row in preview.get("classifications", []) if row.get("material")
    }
    require(direct == {
        "SO202609180003-DES-01-SRC-0003": "MAT202608000048",
        "SO202609180003-DES-01-SRC-0004": "MAT202608000029",
        "SO202609180003-DES-03-SRC-0014": "MAT202608000035",
        "SO202609180003-DES-04-SRC-0073": "MAT202608000058",
    }, "four formal Material identities drift", risks)
    missing_uom = [row["objectNo"] for row in preview.get("classifications", []) if not row.get("physicalUnit")]
    require(missing_uom == ["SO202609180003-DES-03-SRC-0038"], "unique physical UOM gap drift", risks)
    require(preview.get("approvedMappingCount") == 0 and preview.get("candidateCount") == 0,
            "unapproved material candidates were emitted", risks)
    require(preview.get("databaseBusinessWriteCount") == 0
            and preview.get("calculationReexecuted") is False
            and preview.get("implicitUomConversionCount") == 0,
            "preview zero-write/no-recalc/no-conversion contract drift", risks)
    require(preview.get("formalEngineeringMaterialRequirementCount") == 0,
            "preview was confused with formal EngineeringMaterialRequirement", risks)
    bom_gate = preview.get("bomGate") or {}
    require({key: bom_gate.get(key) for key in (
        "code", "statusLabel", "message", "blocked", "canPreview", "canGenerate",
        "formalEngineeringMaterialRequirementCount", "productBomCount",
        "businessWriteSideEffectCount", "evidence",
    )} == {
        "code": "MATERIAL_REQUIREMENT_REQUIRED",
        "statusLabel": "工程材料需求尚未形成",
        "message": "该核算没有形成物料需求，不能生成空BOM草稿。",
        "blocked": True, "canPreview": True, "canGenerate": False,
        "formalEngineeringMaterialRequirementCount": 0, "productBomCount": 0,
        "businessWriteSideEffectCount": 0,
        "evidence": "Preview候选不作为正式EngineeringMaterialRequirement；原BOM服务只消费正式需求。",
    }, "BOM gate no longer exposes the formal requirement blocker as an operable read-only preview", risks)
    require(len(released_rule_domains) == 6
            and all(row["domains"] == ["DERIVED_FACT"] for row in released_rule_domains),
            "released rule output-domain baseline drift", risks)
    require({key: confirmation.get(key) for key in (
        "objectCount", "missingMaterialObjectCount", "missingMaterialBusinessGroupCount",
        "formalMaterialMappingCardCount", "decisionUnitCount", "coverageClosed",
    )} == {
        "objectCount": 71, "missingMaterialObjectCount": 67,
        "missingMaterialBusinessGroupCount": 19, "formalMaterialMappingCardCount": 4,
        "decisionUnitCount": 23, "coverageClosed": True,
    }, "business confirmation pack 71/67/19/4/23 closure drift", risks)
    require(confirmation.get("materialDecisionCounts") == {
        "EXACT_EXISTING_MATERIAL_CANDIDATE": 0,
        "MULTIPLE_EXISTING_CANDIDATES": 1,
        "NO_EXISTING_MATERIAL_CONFIRMED": 0,
        "INSUFFICIENT_BUSINESS_FACTS": 18,
    }, "19-group Material identity decisions drift", risks)
    require(confirmation.get("confirmationStatusCounts") == {
        "READY_FOR_BUSINESS_CONFIRMATION": 2,
        "MATERIAL_IDENTITY_REQUIRED": 1,
        "QUANTITY_RULE_REQUIRED": 2,
        "UOM_DEFINITION_REQUIRED": 1,
        "BUSINESS_FACT_REQUIRED": 17,
    }, "23-item business confirmation status closure drift", risks)
    groups = confirmation.get("groups") or []
    require(sorted((row.get("objectCount") for row in groups), reverse=True) == [
        12, 10, 8, 6, 5, 3, 3, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1,
    ], "67 missing-Material objects are not covered exactly once by 19 groups", risks)
    multiple = [row for row in groups if row.get("materialDecision") == "MULTIPLE_EXISTING_CANDIDATES"]
    require(len(multiple) == 1
            and multiple[0].get("objectNos") == [
                "SO202609180003-DES-01-SRC-0005",
                "SO202609180003-DES-01-SRC-0006",
                "SO202609180003-DES-01-SRC-0007",
            ]
            and {row.get("code") for row in multiple[0].get("existingMaterialCandidates", [])}
            == {"MAT202608000048", "MAT202608000029"},
            "single-door multiple-Material candidate group drift", risks)
    cards = confirmation.get("mappingCards") or []
    require([(row.get("designItem") or {}).get("objectNo") for row in cards] == [
        "SO202609180003-DES-01-SRC-0003",
        "SO202609180003-DES-01-SRC-0004",
        "SO202609180003-DES-03-SRC-0014",
        "SO202609180003-DES-04-SRC-0073",
    ], "four Mapping confirmation card identities drift", risks)
    require([((row.get("recommendedQuantitySource") or {}).get("sourceFactCode"),
              row.get("recommendedQuantityBasis"), row.get("salesItemMultiplier"),
              row.get("currentStatus")) for row in cards] == [
        ("W", "PER_SALES_ITEM_UNIT", "APPLY_ONCE", "QUANTITY_RULE_REQUIRED"),
        ("W", "PER_SALES_ITEM_UNIT", "APPLY_ONCE", "QUANTITY_RULE_REQUIRED"),
        ("S", "PER_SALES_ITEM_UNIT", "APPLY_ONCE", "READY_FOR_BUSINESS_CONFIRMATION"),
        ("S", "PER_SALES_ITEM_UNIT", "APPLY_ONCE", "READY_FOR_BUSINESS_CONFIRMATION"),
    ], "four Mapping card quantity recommendations drift", risks)
    require(all(row.get("scrapRate") is None for row in cards),
            "a Mapping card guessed a scrap rate", risks)
    require((confirmation.get("uomQuestion") or {}) == {
        "objectNo": "SO202609180003-DES-03-SRC-0038",
        "sourceKey": "三合一生产单:36", "sourceTextUom": "组",
        "formalUomExists": False, "question": "这里的‘1组’在企业业务中具体表示什么？",
        "boundary": "‘组’是设计对象物理单位，不等于材料需求单位；即使以后建立‘组’，材料需求仍按Material自身正式UOM计算。",
    }, "group-UOM business question drift", risks)
    hardware_glass = confirmation.get("hardwareAndGlass") or {}
    require({key: hardware_glass.get(key) for key in (
        "structuredHardwareObjectCount", "structuredGlassObjectCount", "glassNamedObjectCount",
        "formalMaterialReferenceCount", "structuredQuantityCount", "structuredUomCount",
    )} == {
        "structuredHardwareObjectCount": 0, "structuredGlassObjectCount": 0,
        "glassNamedObjectCount": 3, "formalMaterialReferenceCount": 0,
        "structuredQuantityCount": 0, "structuredUomCount": 0,
    }, "hardware/glass structured fact boundary drift", risks)
    require((confirmation.get("materialMasterSearch") or {}).get("activeMaterialCount") == 274
            and (confirmation.get("materialMasterSearch") or {}).get("activeConfirmedMaterialCount") == 274,
            "formal Material master-data readback drift", risks)
    require(confirmation.get("automaticMaterialBindingCount") == 0
            and confirmation.get("mappingWriteCount") == 0
            and confirmation.get("requirementWriteCount") == 0
            and confirmation.get("databaseBusinessWriteCount") == 0,
            "business confirmation pack crossed its zero-write boundary", risks)
    require(current_comparison.get("comparisonSummary") == {
        "total": 388, "numeric": 388, "consistent": 309,
        "noIndependentComparison": 68, "confirmedDesignChangeDifferences": 11,
        "unexplainedDifferences": 0, "missing": 0, "notApplicable": 0,
        "errors": 0, "closureTotal": 388,
    }, "309/68/11/0/0 comparison baseline drift", risks)
    regression = current_comparison.get("historicalAcceptanceRegression") or {}
    require(regression.get("match") is True
            and regression.get("missingAcceptedIds") == []
            and regression.get("mismatchedAcceptedRows") == []
            and regression.get("newUnexplainedIds") == [],
            "11 accepted design-change differences drift", risks)
    require(protected_order.get("businessPurpose") == "FORMAL_SALE"
            and protected_order.get("currentValidCrmSourceCount") == 0
            and protected_order.get("crmAdmission") == "BLOCKED",
            "SO202610020004 CRM/busines-purpose protection drift", risks)
    require([row.get("id") for row in protected_order.get("revocations", [])] == [1],
            "SO202610020004 revocation protection drift", risks)
    require(protected_order.get("engineeringInstances") == [{
        "id": 6, "instanceNo": "OEI202610000005", "status": "inactive",
    }], "SO202610020004 OEI protection drift", risks)

    result = {
        "gate": "SO202609180003 Material Requirement Mapping / R1 Preview Completed Work STRICT Gate",
        "status": "PASS" if not risks else "FAIL",
        "riskTotal": len(risks),
        "databaseSha256Before": before_hash,
        "databaseSha256After": after_hash,
        "databaseBusinessWrite": preview.get("databaseBusinessWriteCount"),
        "schemaChange": False,
        "migrationExecuted": False,
        "permissionMutation": 0 if before_counts == after_counts else None,
        "targetFacts": target,
        "previewFacts": {
            key: preview.get(key) for key in (
                "previewCode", "approvedMappingCount", "objectCount", "candidateCount",
                "classificationCounts", "classificationClosed", "metrics",
                "calculationReexecuted", "implicitUomConversionCount",
                "databaseBusinessWriteCount", "formalEngineeringMaterialRequirementCount", "bomGate",
            )
        },
        "businessConfirmationFacts": {
            key: confirmation.get(key) for key in (
                "packageCode", "objectCount", "missingMaterialObjectCount",
                "missingMaterialBusinessGroupCount", "formalMaterialMappingCardCount",
                "decisionUnitCount", "coverageClosed", "materialDecisionCounts",
                "confirmationStatusCounts", "automaticMaterialBindingCount",
                "mappingWriteCount", "requirementWriteCount", "databaseBusinessWriteCount",
            )
        },
        "targetBomFacts": target_bom,
        "currentComparison": current_comparison,
        "releasedRuleDomains": released_rule_domains,
        "protectedFormalOrderFacts": protected_order,
        "sourceHashes": {
            "page": sha256(page_path), "api": sha256(api_path), "service": sha256(service_path),
        },
        "risks": risks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if not risks else 1


if __name__ == "__main__":
    from verify_so202609180003_representative_material_requirements_strict_gate import main as successor_main
    raise SystemExit(successor_main())
