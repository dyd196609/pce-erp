"""Strict, read-only gate for SO202609180003 line 1 / BOMVersion 3 / CALC-3."""

import inspect
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django  # noqa: E402

django.setup()

from pde.bom_version_release_preflight import (  # noqa: E402
    FINAL_DECISION_BLOCKED,
    project_bom_version_release_preflight,
)
from pde.models import (  # noqa: E402
    BOMItemSourceRequirement,
    BOMVersion,
    EngineeringChangeNotice,
    EngineeringDocument,
    EngineeringDocumentVersion,
    ProductManufacturingOutput,
    RoutingVersion,
)
from pde.product_bom_detail_projection import project_product_bom_material_detail  # noqa: E402
from pde.production_foundation_service import EngineeringLifecycleService  # noqa: E402


def check(name, condition, evidence):
    return {"name": name, "status": "PASS" if condition else "FAIL", "evidence": evidence}


def main():
    version = BOMVersion.objects.select_related(
        "bom__company",
        "order_engineering_instance__sales_order_item__sales_order",
        "source_calculation",
    ).get(pk=3)
    order_item = version.order_engineering_instance.sales_order_item
    material_details = project_product_bom_material_detail(
        bom=version.bom,
        bom_version=version,
        order_item=order_item,
    )
    preflight = project_bom_version_release_preflight(
        version,
        material_details=material_details,
    )
    source_count = BOMItemSourceRequirement.objects.filter(
        bom_item__bom_version_id=version.pk,
    ).count()
    signature = inspect.signature(EngineeringLifecycleService.transition)
    frontend_page = (ROOT / "frontend/src/meta/pages/PdeFoundationPage.vue").read_text(encoding="utf-8")
    frontend_component = (
        ROOT / "frontend/src/meta/pages/components/BomVersionReleasePreflightReadback.vue"
    ).read_text(encoding="utf-8")
    gates = {row["code"]: row for row in preflight["gates"]}
    false_side_effects = [
        value for key, value in preflight["downstreamEffects"].items()
        if key not in {"organizationOperatingAuditCreation", "currentManufacturingOutputCount"}
    ]

    checks = [
        check("01_identity", version.bom_version == "CALC-3" and version.pk == 3, f"{version.pk}/{version.bom_version}"),
        check("02_scope", version.bom_id == 3 and order_item.sales_order.order_no == "SO202609180003" and order_item.line_no == 1, f"BOM {version.bom_id}; {order_item.sales_order.order_no} line {order_item.line_no}"),
        check("03_current_state", version.status == "draft" and version.approval_state == "not_submitted", f"{version.status}/{version.approval_state}"),
        check("04_lifecycle", preflight["stateMachine"]["legalTransitions"] == ["draft → reviewed", "reviewed → released", "released → obsolete"], preflight["stateMachine"]["legalTransitions"]),
        check("05_no_direct_release", not preflight["stateMachine"]["directDraftToReleasedAllowed"], "draft direct to released denied"),
        check("06_permission", preflight["permission"]["eligibleActorCount"] == 1 and preflight["permission"]["eligibleActors"][0]["username"] == "pce_plan_r12", preflight["permission"]["eligibleActors"]),
        check("07_bom_items", len(material_details) == 5 and gates["BOM_ITEMS_COMPLETE"]["statusCode"] == "PASS", len(material_details)),
        check("08_sources", source_count == 25 and gates["SOURCE_REQUIREMENTS_COMPLETE"]["statusCode"] == "PASS", source_count),
        check("09_baseline", preflight["baseline"]["id"] == 2 and preflight["baseline"]["isCurrent"], preflight["baseline"]),
        check("10_calculation", preflight["calculation"]["id"] == 3 and preflight["calculation"]["isCurrent"], preflight["calculation"]),
        check("11_competing_versions", not preflight["versionConflicts"]["competingVersions"], preflight["versionConflicts"]),
        check("12_released_conflict", not preflight["versionConflicts"]["conflictingReleasedVersions"], preflight["versionConflicts"]),
        check("13_effective_date_rule", not preflight["releaseControl"]["effectiveDateRequired"] and version.effective_date is None, "not required / currently null"),
        check("14_audit_rule", preflight["releaseControl"]["businessAuditImplemented"], "OrganizationOperatingAuditRecord is mandatory in the controlled service"),
        check("15_idempotency_integrated", "idempotency_key" in signature.parameters and gates["IDEMPOTENT_RELEASE"]["statusCode"] == "PASS" and preflight["releaseControl"]["requestIdentityRequired"], str(signature)),
        check("16_side_effects", all(value is False for value in false_side_effects) and preflight["downstreamEffects"]["organizationOperatingAuditCreation"], preflight["downstreamEffects"]),
        check("17_no_document_cycle", not preflight["documentDependency"]["cycleDetected"] and not preflight["documentDependency"]["blocksBomRelease"], preflight["documentDependency"]),
        check("18_frontend_visibility", "BomVersionReleasePreflightReadback" in frontend_page and "pde-bom-version-control-chain-readiness" in frontend_component and 'data-write-action-count="0"' in frontend_component and "等待正式评审授权" in frontend_component, "read-only control-chain component registered"),
        check("19_control_chain_integration", gates["BUSINESS_STATE_TRANSITION"]["statusCode"] == "PASS" and preflight["releaseControl"]["workflowApprovalEnforced"] and preflight["releaseControl"]["businessStateTransitionEnforced"] and preflight["releaseControl"]["idempotencyLedgerImplemented"], preflight["controlChainReadiness"]),
        check("20_existing_workflow_configuration_blocker", preflight["decisionCode"] == FINAL_DECISION_BLOCKED and preflight["controlChainReadiness"]["workflowRuntime"]["statusCode"] == "BLOCKED" and preflight["firstBlockerCode"] == "BOM_VERSION_WORKFLOW_TEMPLATE_MISSING" and not preflight["releaseAllowed"], preflight["decisionCode"]),
        check("21_protected_counts", EngineeringDocument.objects.count() == 1 and EngineeringDocumentVersion.objects.count() == 1 and ProductManufacturingOutput.objects.count() == 0 and RoutingVersion.objects.filter(pk=31, status="released").count() == 1 and EngineeringChangeNotice.objects.count() == 0, {"engineeringDocument": EngineeringDocument.objects.count(), "engineeringDocumentVersion": EngineeringDocumentVersion.objects.count(), "productManufacturingOutput": ProductManufacturingOutput.objects.count(), "routing31Released": RoutingVersion.objects.filter(pk=31, status="released").count(), "ecn": EngineeringChangeNotice.objects.count()}),
    ]
    failed = [row for row in checks if row["status"] != "PASS"]
    result = {
        "gate": "PDE-CALC3-BOM-RELEASE-PREFLIGHT-STRICT",
        "status": "PASS" if not failed else "FAIL",
        "businessDecision": preflight["decisionCode"],
        "releaseExecuted": False,
        "checks": checks,
        "databaseBusinessWriteCount": 0,
    }
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
