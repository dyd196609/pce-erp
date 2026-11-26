"""Read-only gate for PDE node-9 Routing Version traceability.

The gate reads the formal acceptance database, exercises the same serializer
used by ``/api/pde/routings/``, and proves that no database or permission fact
changes while Definition -> Version -> Step and downstream resolver facts are
inspected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import site
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SITE_PACKAGES = BACKEND / "venv" / "Lib" / "site-packages"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require(condition: bool, message: str, risks: list[str]) -> None:
    if not condition:
        risks.append(message)


def configure_django(database_path: Path) -> None:
    site.addsitedir(str(SITE_PACKAGES))
    sys.path.insert(0, str(BACKEND))
    os.environ["PCE_DATABASE_PATH"] = str(database_path)
    os.environ["PCE_DATABASE_IDENTITY"] = "PDE-OPERABLE-ACCEPTANCE-20260912"
    os.environ["PCE_RUNTIME_PROFILE"] = "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    os.environ["PCE_NON_PRODUCTION_ACCEPTANCE"] = "1"
    os.environ["PCE_RUNTIME_LAUNCHER_VERIFIED"] = "1"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
    import django

    django.setup()


def protected_snapshot() -> dict[str, int]:
    from pde.models import (
        BOMVersion,
        EngineeringCalculationDetail,
        EngineeringDerivedFact,
        EngineeringMaterialRequirement,
        EngineeringOperationRequirement,
        ProductBOM,
        Routing,
        RoutingStep,
        RoutingVersion,
        WorkCenter,
    )
    from system.models import (
        Permission,
        Process,
        Role,
        RolePermission,
        UserRoleScopeAssignment,
        Workshop,
    )

    return {
        "routingDefinitions": Routing.objects.count(),
        "routingVersions": RoutingVersion.objects.count(),
        "routingSteps": RoutingStep.objects.count(),
        "operations": Process.objects.count(),
        "workshops": Workshop.objects.count(),
        "workCenters": WorkCenter.objects.count(),
        "materialRequirements": EngineeringMaterialRequirement.objects.count(),
        "operationRequirements": EngineeringOperationRequirement.objects.count(),
        "calculationDetails": EngineeringCalculationDetail.objects.count(),
        "derivedFacts": EngineeringDerivedFact.objects.count(),
        "productBoms": ProductBOM.objects.count(),
        "bomVersions": BOMVersion.objects.count(),
        "permissions": Permission.objects.count(),
        "roles": Role.objects.count(),
        "rolePermissions": RolePermission.objects.count(),
        "userRoleScopes": UserRoleScopeAssignment.objects.count(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    database_path = args.database.resolve()
    risks: list[str] = []

    require(database_path.is_file(), "formal acceptance database is missing", risks)
    before_hash = sha256(database_path) if database_path.is_file() else ""
    if risks:
        print(json.dumps({"gate": "PDE NODE9 ROUTING VERSION TRACEABILITY", "status": "FAIL", "risks": risks}, ensure_ascii=False, indent=2))
        return 1

    configure_django(database_path)

    from pde.formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
    from pde.manufacturing_structure_service import ManufacturingStructureService
    from pde.models import (
        BOMVersion,
        EngineeringCalculationDetail,
        EngineeringDerivedFact,
        EngineeringMaterialRequirement,
        EngineeringOperationRequirement,
        OrderEngineeringInstance,
        ProductBOM,
        Routing,
    )
    from pde.order_bom_handoff_service import order_bom_handoff
    from pde.views import RoutingListView
    from sales.models import SalesOrder
    from system.models import Process, User, Workshop
    from pde.models import WorkCenter

    before = protected_snapshot()
    order = SalesOrder.objects.get(order_no="SO202609180003")
    admin = User.objects.get(username="admin")
    expected = {
        "QSFB/FM": {"definitionId": 31, "versionId": 31, "stepCount": 28},
        "BTKF/GT": {"definitionId": 5, "versionId": 5, "stepCount": 30},
        "BTKF/SM": {"definitionId": 6, "versionId": 6, "stepCount": 30},
    }
    target_rows: dict[str, dict[str, object]] = {}
    for code, contract in expected.items():
        definitions = list(Routing.objects.filter(routing_code=code))
        require(len(definitions) == 1, f"{code} is not a unique Routing Definition", risks)
        if len(definitions) != 1:
            continue
        routing = definitions[0]
        projected = RoutingListView().serialize(routing)
        versions = projected.get("routingVersions") or []
        require(routing.pk == contract["definitionId"], f"{code} Definition ID drift", risks)
        require(projected.get("definitionStatusLabel") == "已发布", f"{code} Definition status is not released", risks)
        require(projected.get("versionCount") == 1 and len(versions) == 1, f"{code} does not have exactly one FK-projected Version", risks)
        if len(versions) != 1:
            continue
        version = versions[0]
        steps = version.get("steps") or []
        sequences = [row.get("sequence") for row in steps]
        require(version.get("id") == contract["versionId"], f"{code} Version ID drift", risks)
        require(version.get("routingVersionNo") == "SYSTEM_INITIAL_VERSION", f"{code} Version number drift", risks)
        require(version.get("revision") == 1, f"{code} Version revision drift", risks)
        require(version.get("statusLabel") == "已发布" and version.get("isReleased") is True, f"{code} Version status drift", risks)
        require(version.get("isCurrentlyEffective") is True, f"{code} Version is not currently effective", risks)
        require(version.get("stepCount") == contract["stepCount"] == len(steps), f"{code} Step count drift", risks)
        require(sequences == list(range(1, contract["stepCount"] + 1)), f"{code} Step sequence is missing or duplicated", risks)
        require(all(row.get("statusLabel") == "有效" for row in steps), f"{code} has inactive Routing Steps", risks)
        require(all(row.get("operationId") and row.get("operationCode") and row.get("operationName") for row in steps), f"{code} Step Operation identity is incomplete", risks)
        require(all(row.get("operationSourceLabel") == "system.Process（RoutingStep.operation正式FK）" for row in steps), f"{code} Operation source is not the formal FK", risks)
        require(all(row.get("workshopId") for row in steps), f"{code} cannot resolve Workshop through Step/Operation", risks)
        require(all(not row.get("workCenterId") for row in steps), f"{code} unexpected WorkCenter facts appeared", risks)
        target_rows[code] = {
            "definitionId": routing.pk,
            "routingName": routing.name,
            "definitionStatus": projected.get("definitionStatusLabel"),
            "applicabilityScope": projected.get("applicabilityScope"),
            "versionId": version.get("id"),
            "versionNo": version.get("routingVersionNo"),
            "revision": version.get("revision"),
            "versionStatus": version.get("statusLabel"),
            "effectiveStatus": version.get("effectiveStatusLabel"),
            "releaseTime": version.get("releaseTime"),
            "releaseTimeEvidence": version.get("releaseTimeLabel"),
            "stepCount": version.get("stepCount"),
            "sequenceRange": [sequences[0], sequences[-1]] if sequences else [],
            "sourceIdentity": version.get("sourceIdentity"),
            "relation": version.get("relationLabel"),
            "updatedAt": version.get("updatedAt"),
            "versionCount": projected.get("versionCount"),
        }

    resolutions: dict[str, dict[str, object]] = {}
    instances = OrderEngineeringInstance.objects.filter(
        sales_order_item__sales_order=order,
    ).select_related("sales_order_item").order_by("sales_order_item_id")
    for instance in instances:
        resolved = ManufacturingStructureService.resolve_effective_routing(instance)
        resolutions[str(instance.sales_order_item_id)] = {
            "orderEngineeringInstanceId": instance.pk,
            "instanceNo": instance.instance_no,
            "routingDefinitionId": resolved["routing"].pk,
            "routingCode": resolved["routing"].routing_code,
            "routingVersionId": resolved["routing_version"].pk,
            "routingVersion": resolved["routing_version"].routing_version,
            "resolvedScope": resolved["resolved_scope"],
            "relationship": "UNIQUE_RESOLVER_RESULT_NOT_PERSISTED_BINDING",
        }
    require(resolutions.get("3", {}).get("routingVersionId") == 31, "SalesOrderItem 3 routing resolution drift", risks)
    require(resolutions.get("4", {}).get("routingVersionId") == 31, "SalesOrderItem 4 routing resolution drift", risks)
    require(resolutions.get("5", {}).get("routingVersionId") == 5, "SalesOrderItem 5 routing resolution drift", risks)
    require(resolutions.get("6", {}).get("routingVersionId") == 6, "SalesOrderItem 6 routing resolution drift", risks)

    bom_contract = {
        "OBOM-OEI202609000003": {"version": "CALC-5", "instanceId": 4, "routingVersionId": 5},
        "OBOM-OEI202609000004": {"version": "CALC-6", "instanceId": 5, "routingVersionId": 6},
    }
    bom_facts: dict[str, dict[str, object]] = {}
    for code, contract in bom_contract.items():
        bom = ProductBOM.objects.get(bom_code=code)
        versions = list(bom.versions.select_related("source_calculation").order_by("pk"))
        resolved = ManufacturingStructureService.resolve_effective_routing(bom.order_engineering_instance)
        eligibility = FormalManufacturingEligibilityService.resolve(bom)
        require(bom.order_engineering_instance_id == contract["instanceId"], f"{code} OEI drift", risks)
        require(len(versions) == 1 and versions[0].bom_version == contract["version"], f"{code} BOM Version drift", risks)
        require(all(version.status == "draft" for version in versions), f"{code} BOM Version is not draft", risks)
        require(resolved["routing_version"].pk == contract["routingVersionId"], f"{code} routing resolver drift", risks)
        require(eligibility.get("formalManufacturingEligible") is False, f"{code} formal manufacturing eligibility drift", risks)
        bom_facts[code] = {
            "productBomId": bom.pk,
            "orderEngineeringInstanceId": bom.order_engineering_instance_id,
            "bomVersionId": versions[0].pk,
            "bomVersion": versions[0].bom_version,
            "bomVersionStatus": versions[0].get_status_display(),
            "sourceCalculationId": versions[0].source_calculation_id,
            "productBomDirectRoutingFk": False,
            "bomVersionDirectRoutingFk": False,
            "oeiDirectRoutingFk": False,
            "routingRelationship": "UNIQUE_RESOLVER_RESULT_NOT_PERSISTED_BINDING",
            "resolvedRoutingVersionId": resolved["routing_version"].pk,
            "formalManufacturingEligible": eligibility.get("formalManufacturingEligible"),
        }

    handoff = order_bom_handoff(user=admin, order_id=order.pk)
    bom_gate = handoff.get("bomHandoffStatus") or {}
    require(bom_gate.get("remainingObjectCount") == 69, "remainingObjectCount drift", risks)

    target_counts = {
        "calculationDetails": EngineeringCalculationDetail.objects.filter(
            calculation__sales_order_item__sales_order=order,
        ).count(),
        "derivedFacts": EngineeringDerivedFact.objects.filter(
            calculation__sales_order_item__sales_order=order,
        ).count(),
        "materialRequirements": EngineeringMaterialRequirement.objects.filter(
            calculation__sales_order_item__sales_order=order,
        ).count(),
        "operationRequirements": EngineeringOperationRequirement.objects.filter(
            calculation__sales_order_item__sales_order=order,
        ).count(),
        "productBoms": ProductBOM.objects.filter(order_engineering_instance__sales_order_item__sales_order=order).count(),
        "bomVersions": BOMVersion.objects.filter(order_engineering_instance__sales_order_item__sales_order=order).count(),
        "remainingObjects": bom_gate.get("remainingObjectCount"),
    }
    require(target_counts == {
        "calculationDetails": 388,
        "derivedFacts": 388,
        "materialRequirements": 2,
        "operationRequirements": 0,
        "productBoms": 2,
        "bomVersions": 2,
        "remainingObjects": 69,
    }, "protected SO202609180003 counts drift", risks)
    require(Process.objects.count() == 33, "formal Operation count drift", risks)
    require(Workshop.objects.count() == 3, "formal Workshop count drift", risks)
    require(WorkCenter.objects.count() == 0, "formal WorkCenter count drift", risks)
    require(Routing.objects.count() == 42, "Routing Definition count drift", risks)

    after = protected_snapshot()
    after_hash = sha256(database_path)
    require(before == after, "read-only gate changed protected database counts", risks)
    require(before_hash == after_hash, "read-only gate changed formal database bytes", risks)

    result = {
        "gate": "PDE NODE9 ROUTING VERSION TRACEABILITY",
        "status": "PASS" if not risks else "FAIL",
        "riskTotal": len(risks),
        "databaseBusinessWrite": 0 if before == after and before_hash == after_hash else None,
        "databaseSha256Before": before_hash,
        "databaseSha256After": after_hash,
        "routingDefinitionCount": Routing.objects.count(),
        "routingVersionCount": before["routingVersions"],
        "routingStepCount": before["routingSteps"],
        "operationCount": Process.objects.count(),
        "operationSource": "system.Process via RoutingStep.operation FK",
        "workshopCount": Workshop.objects.count(),
        "workCenterCount": WorkCenter.objects.count(),
        "workCenterAssessment": "NOT_MAINTAINED; not a node-9 Routing failure; required before resource-specific scheduling",
        "targets": target_rows,
        "orderRoutingResolution": resolutions,
        "bomRoutingFacts": bom_facts,
        "targetProtectedCounts": target_counts,
        "permissionMutation": after["permissions"] - before["permissions"],
        "roleMutation": (
            after["roles"] - before["roles"]
            + after["rolePermissions"] - before["rolePermissions"]
            + after["userRoleScopes"] - before["userRoleScopes"]
        ),
        "risks": risks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not risks else 1


if __name__ == "__main__":
    raise SystemExit(main())

