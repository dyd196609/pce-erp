"""Completed Work STRICT Gate for the formal BOM page read-only preview semantics."""

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

    foundation_path = ROOT / "frontend/src/meta/pages/PdeFoundationPage.vue"
    component_path = ROOT / "frontend/src/meta/pages/components/OrderBomHandoffPreview.vue"
    api_path = ROOT / "frontend/src/api/pde.js"
    router_path = ROOT / "frontend/src/router/index.js"
    view_path = ROOT / "backend/pde/views.py"
    service_path = ROOT / "backend/pde/order_bom_handoff_service.py"
    foundation = foundation_path.read_text(encoding="utf-8")
    component = component_path.read_text(encoding="utf-8")
    api = api_path.read_text(encoding="utf-8")
    router = router_path.read_text(encoding="utf-8")
    view = view_path.read_text(encoding="utf-8")
    service_source = service_path.read_text(encoding="utf-8")

    tree = ast.parse(service_source)
    mutating_calls = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    } & {"save", "create", "update", "delete", "bulk_create", "get_or_create", "execute", "generate_bom", "next_code"}
    require(not mutating_calls, f"handoff service contains prohibited mutating calls: {sorted(mutating_calls)}", risks)
    for token in (
        "path: 'pde/product-boms'",
        "name: 'PdeProductBoms'",
    ):
        require(token in router, f"formal BOM route contract missing: {token}", risks)
    for token in (
        "Business Purpose", "bomHandoffStatus?.code", 'data-acceptance-id="preview-bom-conditions"',
        'data-acceptance-id="generate-bom-draft-disabled"', 'data-acceptance-id="bom-preview-gate-detail"',
        "缺Material业务组", "Mapping确认卡", "READY_FOR_REQUIREMENT", "正式材料需求", "ProductBOM",
        "不生成材料需求、不创建BOM草稿、不占用BOM编号、不发布BOM", "不进入Routing或Planning",
    ):
        require(token in component, f"formal BOM gate UI contract missing: {token}", risks)
    require("pdeApi.previewOrderBom(record.calculationId)" in foundation,
            "formal BOM page does not call the existing preview API for each calculation", risks)
    require("generateOrderBom(" not in foundation + component,
            "formal BOM handoff page must not expose the BOM generation write API", risks)
    require("method: 'GET'" in api and "bom-preview/" in api,
            "existing GET BOM preview API contract missing", risks)
    require("OrderEngineeringClosureService.preview_bom" in view,
            "BOM preview endpoint no longer delegates to the authoritative service", risks)

    before_counts: dict[str, int] = {}
    after_counts: dict[str, int] = {}
    target: dict[str, object] = {}
    handoff: dict[str, object] = {}
    preview_calls: list[dict[str, object]] = []
    protected_order: dict[str, object] = {}
    target_bom: dict[str, int] = {}
    if not risks:
        configure_django(database_path)
        from django.db import connection, connections
        from pde.engineering_calculation_service import EngineeringCalculationError, OrderEngineeringClosureService
        from pde.models import BOMItem, BOMVersion, EngineeringCalculationRecord, ProductBOM
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
            handoff = order_bom_handoff(user=admin, order_id=order.pk)
            calculations = EngineeringCalculationRecord.objects.filter(
                sales_order_item__sales_order=order,
                scope="order_engineering",
                status="completed",
            ).order_by("sales_order_item__line_no", "pk")
            for calculation in calculations:
                try:
                    payload = OrderEngineeringClosureService.preview_bom(
                        user=admin, calculation_id=calculation.pk,
                    )
                    preview_calls.append({
                        "calculationId": calculation.pk,
                        "calculationNo": calculation.calculation_no,
                        "code": payload.get("status"),
                        "businessWriteSideEffectCount": payload.get("businessWriteSideEffectCount"),
                    })
                except EngineeringCalculationError as error:
                    preview_calls.append({
                        "calculationId": calculation.pk,
                        "calculationNo": calculation.calculation_no,
                        "code": error.code,
                        "message": error.message,
                        "businessWriteSideEffectCount": 0,
                    })
            target_bom = {
                "productBom": ProductBOM.objects.filter(
                    order_engineering_instance__sales_order_item__sales_order=order,
                ).count(),
                "bomVersion": BOMVersion.objects.filter(
                    source_calculation__sales_order_item__sales_order=order,
                ).count(),
                "bomItem": BOMItem.objects.filter(
                    bom_version__source_calculation__sales_order_item__sales_order=order,
                ).count(),
            }
            protected_order = protected_formal_order_facts()
            after_counts = database_snapshot()
        connections.close_all()

    after_hash = sha256(database_path) if database_path.is_file() else ""
    preview = handoff.get("materialRequirementPreview") or {}
    confirmation = preview.get("businessConfirmationPackage") or {}
    gate = handoff.get("bomHandoffStatus") or {}
    purpose = (handoff.get("selectedOrder") or {}).get("businessPurpose") or {}
    require(before_hash == after_hash, "acceptance database hash changed", risks)
    require(before_counts == after_counts, "database model counts changed", risks)
    require(target.get("businessPurpose") == "DEVELOPMENT_VALIDATION", "target business purpose drift", risks)
    require(target.get("calculationCount") == 4 and target.get("completedCalculationCount") == 4,
            "4 completed calculations drift", risks)
    require(target.get("detailCount") == 388 and target.get("derivedFactCount") == 388,
            "388 saved facts drift", risks)
    require(handoff.get("objectCount") == 71 and handoff.get("factCount") == 388,
            "71-object / 388-fact handoff drift", risks)
    require(purpose.get("code") == "DEVELOPMENT_VALIDATION"
            and purpose.get("statusLabel") == "开发验证订单"
            and "不自动取得制造BOM发布" in str(purpose.get("boundary")),
            "server Business Purpose projection drift", risks)
    require(confirmation.get("missingMaterialBusinessGroupCount") == 19
            and confirmation.get("formalMaterialMappingCardCount") == 4,
            "19 missing-Material groups / 4 Mapping cards drift", risks)
    require((preview.get("classificationCounts") or {}).get("READY_FOR_REQUIREMENT") == 0,
            "READY_FOR_REQUIREMENT must remain zero", risks)
    require(gate.get("code") == "MATERIAL_REQUIREMENT_REQUIRED"
            and gate.get("statusLabel") == "工程材料需求尚未形成"
            and gate.get("message") == "该核算没有形成物料需求，不能生成空BOM草稿。",
            "BOM business gate semantics drift", risks)
    require(gate.get("canPreview") is True and gate.get("canGenerate") is False,
            "preview/generate server action flags drift", risks)
    require(gate.get("formalEngineeringMaterialRequirementCount") == 0
            and gate.get("productBomCount") == 0
            and gate.get("businessWriteSideEffectCount") == 0,
            "formal requirement/BOM/write counts drift", risks)
    require(target_bom == {"productBom": 0, "bomVersion": 0, "bomItem": 0},
            "target BOM persisted counts drift", risks)
    require(len(preview_calls) == 4
            and all(row.get("code") == "MATERIAL_REQUIREMENT_REQUIRED" for row in preview_calls)
            and all(row.get("message") == "该核算没有形成物料需求，不能生成空BOM草稿。" for row in preview_calls)
            and all(row.get("businessWriteSideEffectCount") == 0 for row in preview_calls),
            "existing preview_bom did not return the expected business blocker for all 4 calculations", risks)
    require(protected_order.get("businessPurpose") == "FORMAL_SALE"
            and protected_order.get("currentValidCrmSourceCount") == 0
            and protected_order.get("crmAdmission") == "BLOCKED",
            "SO202610020004 protection drift", risks)
    require([row.get("id") for row in protected_order.get("revocations", [])] == [1]
            and protected_order.get("engineeringInstances") == [{
                "id": 6, "instanceNo": "OEI202610000005", "status": "inactive",
            }], "SO202610020004 revocation/OEI protection drift", risks)

    result = {
        "gate": "SO202609180003 BOM Management Gate / Read-only Preview Completed Work STRICT Gate",
        "status": "PASS" if not risks else "FAIL",
        "riskTotal": len(risks),
        "databaseSha256Before": before_hash,
        "databaseSha256After": after_hash,
        "databaseBusinessWrite": 0 if before_hash == after_hash and before_counts == after_counts else None,
        "targetFacts": target,
        "handoffFacts": {
            "calculationCount": len(handoff.get("records") or []),
            "objectCount": handoff.get("objectCount"),
            "factCount": handoff.get("factCount"),
            "businessPurpose": purpose,
            "missingMaterialBusinessGroupCount": confirmation.get("missingMaterialBusinessGroupCount"),
            "formalMaterialMappingCardCount": confirmation.get("formalMaterialMappingCardCount"),
            "readyForRequirement": (preview.get("classificationCounts") or {}).get("READY_FOR_REQUIREMENT"),
            "bomHandoffStatus": gate,
        },
        "previewCalls": preview_calls,
        "targetBomFacts": target_bom,
        "protectedFormalOrderFacts": protected_order,
        "sourceHashes": {
            "foundationPage": sha256(foundation_path),
            "handoffComponent": sha256(component_path),
            "handoffService": sha256(service_path),
        },
        "risks": risks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if not risks else 1


if __name__ == "__main__":
    from verify_so202609180003_representative_material_requirements_strict_gate import main as successor_main
    raise SystemExit(successor_main())
