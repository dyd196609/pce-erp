"""Read-only STRICT Gate for the engineering-calculation runtime closure.

This gate intentionally protects only the four dependencies named by the
remediation instruction plus the three explicitly frozen sources.  It also
runs the server-authoritative readiness builder between two database
fingerprints so a read path cannot be reported as zero-write without proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import site
import sys
from pathlib import Path

try:
    from engineering_runtime_closure_contract import (
        assess_purpose_contract,
        assess_requirement_contract,
    )
except ModuleNotFoundError:  # Package import used by read-only audit wrappers.
    from scripts.engineering_runtime_closure_contract import (
        assess_purpose_contract,
        assess_requirement_contract,
    )

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SITE_PACKAGES = BACKEND / "venv" / "Lib" / "site-packages"
MANIFEST_PATH = ROOT / "docs/governance/evidence/PCE_ENGINEERING_RUNTIME_CLOSURE_SOURCE_BASELINE_V1.json"
SIDECAR_PATH = MANIFEST_PATH.with_suffix(MANIFEST_PATH.suffix + ".sha256")
REGISTRY_PATH = ROOT / "docs/governance/completed_module_registry.v1.json"
ACCEPTED_DIFFERENCE_PROFILE_PATH = ROOT / "docs/governance/evidence/PCE_SO202609180003_ENGINEERING_ACCEPTED_DIFFERENCES_V1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require(condition: bool, message: str, risks: list[str]) -> None:
    if not condition:
        risks.append(message)


def compact_hash(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest().upper()


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


def database_snapshot() -> dict[str, int]:
    from pde.models import (
        EngineeringCalculationDetail,
        EngineeringCalculationRecord,
        EngineeringDerivedFact,
        EngineeringMaterialRequirement,
        EngineeringOperationRequirement,
        OrderEngineeringBaseline,
        OrderEngineeringBaselineItem,
        OrderEngineeringInstance,
    )
    from sales.models import SalesOrder, SalesOrderItem
    from system.models import Permission, Role, RolePermission, UserRoleScopeAssignment

    return {
        "orders": SalesOrder.objects.count(),
        "orderItems": SalesOrderItem.objects.count(),
        "instances": OrderEngineeringInstance.objects.count(),
        "calculations": EngineeringCalculationRecord.objects.count(),
        "details": EngineeringCalculationDetail.objects.count(),
        "facts": EngineeringDerivedFact.objects.count(),
        "baselines": OrderEngineeringBaseline.objects.count(),
        "baselineItems": OrderEngineeringBaselineItem.objects.count(),
        "materials": EngineeringMaterialRequirement.objects.count(),
        "operations": EngineeringOperationRequirement.objects.count(),
        "permissions": Permission.objects.count(),
        "roles": Role.objects.count(),
        "rolePermissions": RolePermission.objects.count(),
        "userRoleScopes": UserRoleScopeAssignment.objects.count(),
    }


def target_facts() -> dict[str, object]:
    from django.db import connection
    from pde.models import (
        EngineeringCalculationDetail,
        EngineeringCalculationRecord,
        EngineeringDerivedFact,
        EngineeringMaterialRequirement,
        EngineeringOperationRequirement,
        OrderEngineeringBaseline,
        OrderEngineeringBaselineItem,
    )
    from sales.models import SalesOrder

    order = SalesOrder.objects.get(order_no="SO202609180003")
    with connection.cursor() as cursor:
        cursor.execute("SELECT business_purpose FROM sales_order WHERE id = %s", [order.id])
        business_purpose = cursor.fetchone()[0]
    calculations = EngineeringCalculationRecord.objects.filter(
        sales_order_item__sales_order=order,
    ).order_by("calculation_no")
    baselines = OrderEngineeringBaseline.objects.filter(sales_order=order)
    calculation_ids = list(calculations.values_list("id", flat=True))
    baseline_ids = list(baselines.values_list("id", flat=True))
    return {
        "orderId": order.id,
        "orderNo": order.order_no,
        "businessPurpose": business_purpose,
        "calculationCount": calculations.count(),
        "completedCalculationCount": calculations.filter(status="completed").count(),
        "calculationNos": list(calculations.values_list("calculation_no", flat=True)),
        "detailCount": EngineeringCalculationDetail.objects.filter(calculation_id__in=calculation_ids).count(),
        "derivedFactCount": EngineeringDerivedFact.objects.filter(calculation_id__in=calculation_ids).count(),
        "baselineCount": len(baseline_ids),
        "baselineItemCount": OrderEngineeringBaselineItem.objects.filter(baseline_id__in=baseline_ids).count(),
        "materialRequirementCount": EngineeringMaterialRequirement.objects.filter(calculation_id__in=calculation_ids).count(),
        "operationRequirementCount": EngineeringOperationRequirement.objects.filter(calculation_id__in=calculation_ids).count(),
    }


def protected_formal_order_facts() -> dict[str, object]:
    """Read the separately protected formal-sale order without mutating it."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, order_no, business_purpose FROM sales_order WHERE order_no = %s",
            ["SO202610020004"],
        )
        order_row = cursor.fetchone()
        cursor.execute(
            """
            SELECT instance.id, instance.instance_no, instance.status
            FROM pde_order_engineering_instance AS instance
            INNER JOIN sales_order_item AS item ON item.id = instance.sales_order_item_id
            INNER JOIN sales_order AS sales_order ON sales_order.id = item.sales_order_id
            WHERE sales_order.order_no = %s
            ORDER BY instance.id
            """,
            ["SO202610020004"],
        )
        instances = [
            {"id": row[0], "instanceNo": row[1], "status": row[2]}
            for row in cursor.fetchall()
        ]
        current_valid_source_count = 0
        revocation_rows: list[dict[str, object]] = []
        if order_row:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM pde_order_review_sales_order_relation AS relation
                WHERE relation.sales_order_id = %s
                  AND NOT EXISTS (
                    SELECT 1
                    FROM pde_admission_chain_revocation AS revocation
                    WHERE revocation.crm_order_relation_id = relation.id
                  )
                """,
                [order_row[0]],
            )
            current_valid_source_count = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT revocation.id, revocation.revocation_no, revocation.reason_code,
                       revocation.engineering_instance_id
                FROM pde_admission_chain_revocation AS revocation
                INNER JOIN pde_order_engineering_instance AS instance
                        ON instance.id = revocation.engineering_instance_id
                INNER JOIN sales_order_item AS item
                        ON item.id = instance.sales_order_item_id
                WHERE item.sales_order_id = %s
                ORDER BY revocation.id
                """,
                [order_row[0]],
            )
            revocation_rows = [
                {
                    "id": row[0], "revocationNo": row[1],
                    "reasonCode": row[2], "engineeringInstanceId": row[3],
                }
                for row in cursor.fetchall()
            ]
    return {
        "orderId": order_row[0] if order_row else None,
        "orderNo": order_row[1] if order_row else None,
        "businessPurpose": order_row[2] if order_row else None,
        "currentValidCrmSourceCount": current_valid_source_count,
        "crmAdmission": "BLOCKED" if current_valid_source_count == 0 else "ELIGIBLE",
        "revocations": revocation_rows,
        "engineeringInstances": instances,
    }


def purpose_runtime_contract_facts(order_no: str) -> dict[str, object]:
    """Read the unique governed purpose correction for one SalesOrder."""
    from sales.models import SalesOrder, SalesOrderActionRequest
    from system.models import OrganizationOperatingAuditRecord

    order = SalesOrder.objects.get(order_no=order_no)
    actions = list(
        SalesOrderActionRequest.objects.select_related("actor", "audit_record")
        .filter(
            sales_order=order,
            action_code="sales.order.correct_business_identity",
        )
        .order_by("pk")
    )
    action = actions[0] if len(actions) == 1 else None
    audit = action.audit_record if action else None
    actor = action.actor if action else None
    employee = getattr(actor, "employee_profile", None) if actor else None
    before_snapshot = (audit.before_snapshot or {}) if audit else {}
    after_snapshot = (audit.after_snapshot or {}) if audit else {}
    prior_audits = list(
        OrganizationOperatingAuditRecord.objects.filter(
            target_type="SalesOrder",
            target_id=order.pk,
            action_code="sales.order.business_purpose.confirm",
        ).order_by("pk").values(
            "id", "action_code", "reason", "created_at", "actor_id",
            "before_snapshot", "after_snapshot",
        )
    )
    compact_prior = [{
        "id": row["id"],
        "actionCode": row["action_code"],
        "reason": row["reason"],
        "createdAt": row["created_at"].isoformat(),
        "actorId": row["actor_id"],
        "beforePurpose": (row["before_snapshot"] or {}).get("businessPurpose"),
        "afterPurpose": (row["after_snapshot"] or {}).get("businessPurpose"),
        "confirmation": (row["after_snapshot"] or {}).get("businessPurposeConfirmation") or {},
    } for row in prior_audits]
    return {
        "object": "sales.SalesOrder",
        "table": "sales_order",
        "field": "business_purpose",
        "scope": "SALES_ORDER",
        "orderId": order.pk,
        "orderNo": order.order_no,
        "companyId": order.company_id,
        "orderVersion": order.version,
        "currentPurpose": order.business_purpose,
        "priorPurposeAudits": compact_prior,
        "correctionActionCount": len(actions),
        "correctionAction": {
            "id": action.pk if action else None,
            "actionCode": action.action_code if action else None,
            "createdAt": action.created_at.isoformat() if action else None,
            "actorId": action.actor_id if action else None,
            "source": action.source if action else None,
            "idempotencyKey": action.idempotency_key if action else None,
            "requestId": action.request_id if action else None,
            "auditRecordId": action.audit_record_id if action else None,
            "auditId": audit.pk if audit else None,
            "auditActionCode": audit.action_code if audit else None,
            "auditTargetId": audit.target_id if audit else None,
            "auditActorId": audit.actor_id if audit else None,
            "auditCreatedAt": audit.created_at.isoformat() if audit else None,
            "audit": {
                "reason": audit.reason if audit else None,
                "beforeIdentity": before_snapshot.get("currentIdentity") or {},
                "afterIdentity": after_snapshot.get("currentIdentity") or {},
                "protectedIdentityBefore": before_snapshot.get("protectedIdentity") or {},
                "protectedIdentityAfter": after_snapshot.get("protectedIdentity") or {},
                "actor": {
                    **(before_snapshot.get("actor") or {}),
                    "isSuperuser": bool(actor.is_superuser) if actor else None,
                    "isActive": bool(actor.is_active) if actor else None,
                    "employeeStatus": getattr(employee, "status", None),
                },
                "authorization": before_snapshot.get("authorization") or {},
                "workflowResponsibility": before_snapshot.get("workflowResponsibility") or {},
                "orderWriteCount": after_snapshot.get("orderWriteCount"),
                "businessStateTransitionCount": after_snapshot.get("businessStateTransitionCount"),
                "downstreamWriteCount": after_snapshot.get("downstreamWriteCount"),
            },
        },
    }


def requirement_runtime_contract_facts(order_no: str) -> dict[str, object]:
    """Read the order-scoped mapping/requirement/audit integrity contract."""
    from masterdata.models import ExternalIdentity, MasterDataWriteRequest
    from pde.engineering_rule_foundation import specification_hash
    from pde.models import (
        BOMItemSourceRequirement,
        EngineeringMaterialRequirement,
        EngineeringRuleDefinition,
    )
    from sales.models import SalesOrder
    from system.models import OrganizationOperatingAuditRecord

    order = SalesOrder.objects.get(order_no=order_no)
    queryset = EngineeringMaterialRequirement.objects.select_related(
        "calculation__sales_order_item__sales_order",
        "source_detail", "material", "uom",
    ).filter(
        calculation__sales_order_item__sales_order=order,
    ).order_by("pk")
    requirement_rows = list(queryset)
    released_mappings = list(
        EngineeringRuleDefinition.objects.filter(
            company_id=order.company_id,
            rule_kind="mapping",
            status="released",
            rule_code__startswith=f"MRM.{order.order_no}.",
        ).order_by("pk")
    )
    mappings_by_id = {row.pk: row for row in released_mappings}
    rows: list[dict[str, object]] = []
    for requirement in requirement_rows:
        trace = requirement.trace or {}
        mapping = mappings_by_id.get(trace.get("mappingRuleId"))
        audits = list(
            OrganizationOperatingAuditRecord.objects.select_related("actor")
            .filter(target_type="EngineeringMaterialRequirement", target_id=requirement.pk)
            .order_by("pk")
        )
        audit = audits[0] if len(audits) == 1 else None
        audit_after = (audit.after_snapshot or {}) if audit else {}
        audit_actor = audit.actor if audit else None
        audit_employee = getattr(audit_actor, "employee_profile", None) if audit_actor else None
        authorization_container = (
            audit_after.get("authorizations") or audit_after.get("authorization") or {}
        )
        authorization_decisions = [
            value for value in authorization_container.values()
            if isinstance(value, dict) and "allowed" in value
        ] if isinstance(authorization_container, dict) else []
        audit_request = audit_after.get("request") or {}
        source_links = list(
            BOMItemSourceRequirement.objects.select_related(
                "bom_item__bom_version", "bom_item__material", "bom_item__uom",
            ).filter(
                material_requirement_id=requirement.pk,
            ).order_by("pk")
        )
        rows.append({
            "id": requirement.pk,
            "companyId": requirement.calculation.company_id,
            "salesOrderId": requirement.calculation.sales_order_item.sales_order_id,
            "lineNo": requirement.calculation.sales_order_item.line_no,
            "calculationId": requirement.calculation_id,
            "calculationNo": requirement.calculation.calculation_no,
            "sourceDetailCalculationId": requirement.source_detail.calculation_id,
            "sourceDetailId": requirement.source_detail_id,
            "materialId": requirement.material_id,
            "materialCode": requirement.material.code,
            "calculatedQuantity": str(requirement.calculated_quantity),
            "netQuantity": str(requirement.net_quantity),
            "uomCode": requirement.uom.code,
            "uomSymbol": requirement.uom.symbol,
            "createdAt": requirement.created_at.isoformat(),
            "trace": {
                key: trace.get(key) for key in (
                    "serviceCode", "authorizationReference", "mappingNo",
                    "mappingRuleId", "mappingRuleCode", "mappingSpecificationHash",
                    "sourceFactId", "sourceDetailId", "designItemNo",
                    "calculationReexecuted", "structureRole",
                )
            },
            "mapping": {
                "id": mapping.pk if mapping else None,
                "ruleCode": mapping.rule_code if mapping else None,
                "status": mapping.status if mapping else None,
                "companyId": mapping.company_id if mapping else None,
                "specificationHash": specification_hash(mapping.specification) if mapping else None,
            },
            "audit": {
                "count": len(audits),
                "id": audit.pk if audit else None,
                "targetId": audit.target_id if audit else None,
                "actionCode": audit.action_code if audit else None,
                "reason": audit.reason if audit else None,
                "createdAt": audit.created_at.isoformat() if audit else None,
                "actor": {
                    "id": audit.actor_id if audit else None,
                    "username": audit_actor.username if audit_actor else None,
                    "isSuperuser": bool(audit_actor.is_superuser) if audit_actor else None,
                    "isActive": bool(audit_actor.is_active) if audit_actor else None,
                    "employeeId": getattr(audit_employee, "pk", None),
                    "employeeNo": getattr(audit_employee, "employee_no", None),
                    "employeeStatus": getattr(audit_employee, "status", None),
                },
                "authorizationAllowed": bool(authorization_decisions) and all(
                    decision.get("allowed") is True for decision in authorization_decisions
                ),
                "after": {
                    key: audit_after.get(key) for key in (
                        "requirementId", "mappingRuleId", "sourceDetailId",
                        "materialId", "netQuantity", "uom",
                        "calculationReexecuted", "bomGenerated",
                    )
                } | {
                    "request": {
                        key: audit_request.get(key) for key in (
                            "serviceCode", "mappingRuleId", "calculationId",
                            "materialId", "quantity", "uom",
                            "authorizationReference",
                        )
                    } if audit_request else {},
                },
            },
            "writeRequestCount": MasterDataWriteRequest.objects.filter(
                organization_id=order.company_id,
                entity_type="EngineeringMaterialRequirement",
                target_entity_id=str(requirement.pk),
                action_code="production.engineering.material_requirement.create",
            ).count(),
            "externalIdentityCount": ExternalIdentity.objects.filter(
                organization_id=order.company_id,
                target_entity_type="engineering-material-requirements",
                target_entity_id=str(requirement.pk),
            ).count(),
            "bomSourceLinkCount": len(source_links),
            "bomSourceLinks": [
                {
                    "id": link.pk,
                    "requirementId": link.material_requirement_id,
                    "bomItemId": link.bom_item_id,
                    "bomVersionId": link.bom_item.bom_version_id,
                    "sourceCalculationId": link.bom_item.bom_version.source_calculation_id,
                    "materialId": link.bom_item.material_id,
                    "uomCode": link.bom_item.uom.code,
                    "bomItemQuantity": str(link.bom_item.quantity),
                    "contributedQuantity": str(link.contributed_quantity),
                }
                for link in source_links
            ],
        })

    all_ids = list(EngineeringMaterialRequirement.objects.order_by("pk").values_list("pk", flat=True))
    company_ids = list(
        EngineeringMaterialRequirement.objects.filter(
            calculation__company_id=order.company_id,
        ).order_by("pk").values_list("pk", flat=True)
    )
    line_scopes: dict[str, list[int]] = {}
    calculation_scopes: dict[str, dict[str, object]] = {}
    for row in rows:
        line_scopes.setdefault(str(row["lineNo"]), []).append(row["id"])
        calculation_scopes.setdefault(str(row["calculationId"]), {
            "calculationNo": row["calculationNo"], "requirementIds": [],
        })["requirementIds"].append(row["id"])
    return {
        "model": "pde.EngineeringMaterialRequirement",
        "table": "pde_engineering_material_requirement",
        "scopeType": "SALES_ORDER",
        "filter": "calculation__sales_order_item__sales_order=SO202609180003",
        "orderId": order.pk,
        "orderNo": order.order_no,
        "companyId": order.company_id,
        "allDatabase": {"count": len(all_ids), "ids": all_ids},
        "company": {"count": len(company_ids), "ids": company_ids},
        "salesOrder": {"count": len(rows), "ids": [row["id"] for row in rows]},
        "lines": {
            key: {"count": len(value), "ids": value}
            for key, value in sorted(line_scopes.items())
        },
        "calculations": {
            key: {**value, "count": len(value["requirementIds"])}
            for key, value in sorted(calculation_scopes.items())
        },
        "inactiveHistoricalFilter": {
            "supportedByModel": False,
            "count": 0,
            "ids": [],
            "reason": "EngineeringMaterialRequirement has no active/status/history field",
        },
        "releasedMappingRuleIds": [row.pk for row in released_mappings],
        "requirements": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    database_path = args.database.resolve()
    risks: list[str] = []

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    accepted_profile = json.loads(ACCEPTED_DIFFERENCE_PROFILE_PATH.read_text(encoding="utf-8")) if ACCEPTED_DIFFERENCE_PROFILE_PATH.is_file() else {}
    page_path = ROOT / "frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue"
    service_path = ROOT / "backend/pde/engineering_calculation_service.py"
    projection_path = ROOT / "backend/pde/calculation_batch_reuse.py"
    material_preview_service_path = ROOT / "backend/pde/order_bom_handoff_service.py"
    r1_handoff_service_path = ROOT / "backend/pde/r1_material_requirement_handoff_service.py"
    bom_foundation_page_path = ROOT / "frontend/src/meta/pages/PdeFoundationPage.vue"
    bom_handoff_component_path = ROOT / "frontend/src/meta/pages/components/OrderBomHandoffPreview.vue"
    process_path = ROOT / "frontend/src/meta/process/businessProcessRegistry.js"
    router_path = ROOT / "frontend/src/router/index.js"
    page = page_path.read_text(encoding="utf-8")
    process = process_path.read_text(encoding="utf-8")
    router = router_path.read_text(encoding="utf-8")

    manifest_hash = sha256(MANIFEST_PATH)
    require(SIDECAR_PATH.exists(), "source baseline sidecar is missing", risks)
    if SIDECAR_PATH.exists():
        require(SIDECAR_PATH.read_text(encoding="utf-8").split()[0].upper() == manifest_hash,
                "source baseline sidecar hash mismatch", risks)
    require(compact_hash(manifest["protectedSources"]) == manifest["baselineHash"],
            "protectedSources aggregate hash mismatch", risks)
    require(bool(accepted_profile), "accepted design-change difference profile is missing", risks)
    require(manifest["protectedSources"].get("acceptedDifferenceProfile")
            == (sha256(ACCEPTED_DIFFERENCE_PROFILE_PATH) if ACCEPTED_DIFFERENCE_PROFILE_PATH.is_file() else None),
            "accepted design-change difference profile protected hash mismatch", risks)
    require(len(accepted_profile.get("confirmedDifferences", [])) == 11,
            "accepted design-change difference profile does not contain 11 rows", risks)
    require((ROOT / str(accepted_profile.get("formalReportPath") or "")).is_file(),
            "historical acceptance report referenced by the difference profile is missing", risks)
    require(sha256(page_path) == manifest["protectedSources"]["page"],
            "formal page protected source mismatch", risks)
    require(sha256(service_path) == manifest["protectedSources"]["service"],
            "readiness service protected source mismatch", risks)
    require(sha256(projection_path) == manifest["protectedSources"]["projection"],
            "whole-order projection protected source mismatch", risks)
    require(sha256(material_preview_service_path)
            == manifest["protectedSources"]["materialRequirementPreviewService"],
            "material requirement preview protected source mismatch", risks)
    require(sha256(r1_handoff_service_path)
            == manifest["protectedSources"]["r1MaterialRequirementHandoffService"],
            "R1 material requirement handoff protected source mismatch", risks)
    require(sha256(bom_foundation_page_path)
            == manifest["protectedSources"]["bomFoundationPage"],
            "BOM foundation page protected source mismatch", risks)
    require(sha256(bom_handoff_component_path)
            == manifest["protectedSources"]["bomHandoffComponent"],
            "BOM handoff component protected source mismatch", risks)

    forbidden_order = manifest["protectedBehavior"]["forbiddenOrderLiteral"]
    require(forbidden_order not in page, "fixed business sample remains in formal page", risks)
    require("stableDesignContext" not in page, "development/stable fallback selector remains", risks)
    require(not re.search(r"orders\.value\s*\[\s*0\s*\]", page),
            "first-order fallback selector remains", risks)
    require("selection.salesOrderItemId = null" in page,
            "no-context selection does not remain empty", risks)
    for token in ("route.query.sourceRecord", "route.query.order", "route.query.orderNo"):
        require(token in page, f"generic context source is missing: {token}", risks)

    process_tokens = (
        "['engineering-material-calculation', '工程核算 / 物料核算', 'pde-order-engineering-calculation', '/pde/engineering-calculations'",
        "pageStatus: 'active'",
        "acceptanceStatus: 'PASS'",
    )
    for token in process_tokens:
        require(token in process, f"localized process Registry contract missing: {token}", risks)
    router_tokens = (
        "path: 'pde/engineering-calculations'",
        "name: 'PdeOrderEngineeringCalculation'",
        "PdeOrderEngineeringCalculationPage.vue",
        "wrapPdeOrderEngineeringCalculationPage",
        "pageCode: 'pde-order-engineering-calculation'",
        "businessObject: 'EngineeringCalculationRecord'",
    )
    for token in router_tokens:
        require(token in router, f"localized Router contract missing: {token}", risks)

    module = next((row for row in registry["modules"] if row["moduleId"] == manifest["moduleId"]), None)
    require(module is not None, "completed module Registry entry is missing", risks)
    if module:
        require(module.get("sourceBaselineReference") == str(MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
                "completed module Registry does not reference the source baseline", risks)
        protection = module.get("dependencyProtection", {})
        require(set(protection.get("directImplementation", [])) == {
            "frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue",
            "backend/pde/engineering_calculation_service.py",
            "backend/pde/calculation_batch_reuse.py",
            "backend/pde/order_bom_handoff_service.py",
            "backend/pde/r1_material_requirement_handoff_service.py",
            "frontend/src/meta/pages/PdeFoundationPage.vue",
            "frontend/src/meta/pages/components/OrderBomHandoffPreview.vue",
        }, "direct implementation dependency registration mismatch", risks)
        require(set(protection.get("sharedLocalizedContracts", [])) == {
            "frontend/src/meta/process/businessProcessRegistry.js#PDE.engineering-material-calculation",
            "frontend/src/router/index.js#PdeOrderEngineeringCalculation",
            "frontend/src/api/pde.js#orderBomHandoff",
            "backend/pde/views.py#ProductBomListView.handoff",
        }, "shared localized dependency registration mismatch", risks)

    frozen_hashes = {
        "backend/pde/manufacturing_structure_service.py": "2D52D54563C1D176E81059AABFCB8B94D725DAD57CE673C802F4D127F055101B",
        "backend/masterdata/group3_comparison_runtime.py": "3A863701F5593F6053EBD359E4ACF2A106E9BA1F064F02F4F0B08D05A81B5AC1",
        "backend/masterdata/group3_comparison_source.json": "3CB672466DFF7347CE09696BB4B82AFA3A6B0DDFEABE77ACE36C778B1C13C580",
    }
    for relative, expected in frozen_hashes.items():
        require(sha256(ROOT / relative) == expected, f"frozen source changed: {relative}", risks)

    require(database_path.is_file(), "acceptance database is missing", risks)
    database_before_hash = sha256(database_path) if database_path.is_file() else ""
    readiness: dict[str, object] = {}
    before: dict[str, int] = {}
    after: dict[str, int] = {}
    facts: dict[str, object] = {}
    whole_order_projection: dict[str, object] = {}
    routing_facts: dict[str, object] = {}
    protected_formal_order: dict[str, object] = {}
    purpose_contract: dict[str, object] = {}
    requirement_contract: dict[str, object] = {}
    database_diagnostics: dict[str, object] = {}
    if not risks:
        configure_django(database_path)
        from django.db import connection, connections
        from pde.engineering_calculation_service import EngineeringCalculationReadinessService
        from pde.calculation_batch_reuse import design_calculation_context
        from system.models import User

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA query_only=ON")
            cursor.execute("PRAGMA query_only")
            query_only = cursor.fetchone()[0]
            cursor.execute("PRAGMA integrity_check")
            integrity_check = cursor.fetchone()[0]
            cursor.execute("PRAGMA foreign_key_check")
            foreign_key_check = cursor.fetchall()
        database_diagnostics = {
            "queryOnly": query_only,
            "integrityCheck": integrity_check,
            "foreignKeyCheck": foreign_key_check,
        }
        require(query_only == 1, "formal database query_only is not enabled", risks)
        require(integrity_check == "ok", "formal database integrity_check failed", risks)
        require(foreign_key_check == [], "formal database foreign_key_check failed", risks)

        admin = User.objects.filter(username="admin").first()
        require(admin is not None, "acceptance admin user is missing", risks)
        if admin is not None:
            before = database_snapshot()
            readiness = EngineeringCalculationReadinessService.build(user=admin)
            routing_facts = {
                key: {
                    "routingCode": row.get("routingCode"),
                    "routingVersionId": row.get("routingVersionId"),
                    "routingVersion": row.get("routingVersion"),
                    "operationCount": len(row.get("rows") or []),
                    "planId": row.get("planId"),
                }
                for key, row in (readiness.get("productionPlanByOrder") or {}).items()
                if key in {"3", "4", "5", "6"}
            }
            after = database_snapshot()
            facts = target_facts()
            projection = design_calculation_context(admin, 11)
            draft = projection.get("draft") or {}
            design_inputs = draft.get("currentDesignInputs") or []
            work_order_rows = draft.get("workOrderRows") or []
            current_calculation = draft.get("currentInputCalculation") or {}
            current_rows = current_calculation.get("rows") or []
            historical_rows = (draft.get("sourceCalculation") or {}).get("rows") or []
            line_counts: dict[str, int] = {}
            for row in design_inputs:
                key = str(row.get("salesOrderItemId"))
                line_counts[key] = line_counts.get(key, 0) + 1
            required_fields = {
                "orderNo", "orderLineNo", "projectReference", "space",
                "installationPosition", "product", "component", "quantity", "unit",
                "dimensionSemantics", "materialCode", "materialName", "specification",
                "edgeMode", "visibleCondition", "colorVersion",
                "processConfigurationLabel", "paintProcess", "processingNote",
                "hardware", "glass",
            }
            whole_order_projection = {
                "sourceRecordId": projection.get("sourceRecordId"),
                "designInputCount": len(design_inputs),
                "workOrderRowCount": len(work_order_rows),
                "currentResultCount": len(current_rows),
                "historicalResultCount": len(historical_rows),
                "lineCountsBySalesOrderItemId": line_counts,
                "orderNos": sorted({row.get("orderNo") for row in work_order_rows}),
                "missingRequiredProjectionFields": sorted(
                    field for field in required_fields
                    if any(field not in row for row in work_order_rows)
                ),
                "businessWriteSideEffectCount": projection.get("businessWriteSideEffectCount"),
                "comparisonSummary": current_calculation.get("comparisonSummary") or {},
                "historicalAcceptanceRegression": current_calculation.get("historicalAcceptanceRegression") or {},
                "confirmedDifferenceFacts": [{
                    "id": row.get("id"),
                    "designItemNo": (row.get("historicalAcceptance") or {}).get("designItemNo"),
                    "project": row.get("project"),
                    "currentValue": row.get("value"),
                    "independentValue": row.get("expected"),
                    "difference": row.get("difference"),
                    "sourceCell": row.get("sourceCell"),
                    "expression": row.get("expression"),
                    "ruleVersion": row.get("ruleVersion"),
                    "decision": (row.get("historicalAcceptance") or {}).get("decision"),
                } for row in current_rows if row.get("comparisonClassification") == "SAME_CONFIRMED_DESIGN_CHANGE"],
            }
            protected_formal_order = protected_formal_order_facts()
            purpose_contract = purpose_runtime_contract_facts("SO202609180003")
            requirement_contract = requirement_runtime_contract_facts("SO202609180003")
        connections.close_all()

    database_after_hash = sha256(database_path) if database_path.is_file() else ""
    require(before == after, "database model counts changed during readiness", risks)
    require(database_before_hash == database_after_hash, "database file changed during read-only STRICT Gate", risks)
    require(readiness.get("businessWriteSideEffectCount") == 0,
            "readiness reported a business write side effect", risks)
    for contract_risk in assess_purpose_contract(purpose_contract):
        risks.append(f"purpose runtime contract: {contract_risk}")
    require(facts.get("calculationCount") == 4 and facts.get("completedCalculationCount") == 4,
            "target completed calculation count drift", risks)
    require(facts.get("calculationNos") == [
        "EC202609000002", "EC202609000003", "EC202609000004", "EC202609000005",
    ], "target calculation identities drift", risks)
    require(facts.get("detailCount") == 388, "target calculation detail count drift", risks)
    require(facts.get("derivedFactCount") == 388, "target derived-fact count drift", risks)
    require(facts.get("baselineCount") == 2 and facts.get("baselineItemCount") == 142,
            "target engineering baseline facts drift", risks)
    for contract_risk in assess_requirement_contract(requirement_contract):
        risks.append(f"material requirement runtime contract: {contract_risk}")
    require(facts.get("operationRequirementCount") == 0, "operation requirement count drift", risks)
    require(whole_order_projection.get("sourceRecordId") == 11,
            "formal whole-order source record drift", risks)
    require(whole_order_projection.get("designInputCount") == 71
            and whole_order_projection.get("workOrderRowCount") == 71,
            "formal whole-order 71-item projection drift", risks)
    require(whole_order_projection.get("currentResultCount") == 388
            and whole_order_projection.get("historicalResultCount") == 388,
            "formal whole-order 388-result projection drift", risks)
    require(whole_order_projection.get("lineCountsBySalesOrderItemId") == {
        "3": 5, "4": 3, "5": 62, "6": 1,
    }, "formal whole-order line-scope counts drift", risks)
    require(whole_order_projection.get("orderNos") == ["SO202609180003"],
            "formal whole-order projection order identity drift", risks)
    require(not whole_order_projection.get("missingRequiredProjectionFields"),
            "workshop-operable projection field contract drift", risks)
    require(whole_order_projection.get("businessWriteSideEffectCount") == 0,
            "whole-order projection reported a business write side effect", risks)
    require(whole_order_projection.get("comparisonSummary") == {
        "total": 388, "numeric": 388, "consistent": 309,
        "noIndependentComparison": 68, "confirmedDesignChangeDifferences": 11,
        "unexplainedDifferences": 0, "missing": 0, "notApplicable": 0,
        "errors": 0, "closureTotal": 388,
    }, "current 388-result five-way classification drift", risks)
    historical_regression = whole_order_projection.get("historicalAcceptanceRegression") or {}
    require(historical_regression.get("statusCode") == "HISTORICAL_ACCEPTED_RESULT_MATCH"
            and historical_regression.get("match") is True,
            "current differences do not exactly match historical accepted differences", risks)
    require(historical_regression.get("missingAcceptedIds") == []
            and historical_regression.get("mismatchedAcceptedRows") == []
            and historical_regression.get("newUnexplainedIds") == [],
            "historical accepted difference identity/value/basis regression detected", risks)
    expected_difference_facts = [{
        "id": row.get("id"), "designItemNo": row.get("designItemNo"),
        "project": row.get("project"), "currentValue": row.get("currentValue"),
        "independentValue": row.get("independentValue"), "difference": row.get("difference"),
        "sourceCell": row.get("sourceCell"), "expression": row.get("expression"),
        "ruleVersion": row.get("ruleVersion"), "decision": "SAME_CONFIRMED_DESIGN_CHANGE",
    } for row in accepted_profile.get("confirmedDifferences", [])]
    require(whole_order_projection.get("confirmedDifferenceFacts") == expected_difference_facts,
            "the 11 current difference facts no longer match the formal acceptance profile", risks)
    require(routing_facts == {
        "3": {"routingCode": "QSFB/FM", "routingVersionId": 31,
              "routingVersion": "SYSTEM_INITIAL_VERSION", "operationCount": 28, "planId": None},
        "4": {"routingCode": "QSFB/FM", "routingVersionId": 31,
              "routingVersion": "SYSTEM_INITIAL_VERSION", "operationCount": 28, "planId": None},
        "5": {"routingCode": "BTKF/GT", "routingVersionId": 5,
              "routingVersion": "SYSTEM_INITIAL_VERSION", "operationCount": 30, "planId": None},
        "6": {"routingCode": "BTKF/SM", "routingVersionId": 6,
              "routingVersion": "SYSTEM_INITIAL_VERSION", "operationCount": 30, "planId": None},
    }, "target routing or unplanned-state facts drift", risks)
    require(protected_formal_order.get("businessPurpose") == "FORMAL_SALE",
            "protected formal-sale order purpose drift", risks)
    require(protected_formal_order.get("currentValidCrmSourceCount") == 0,
            "protected formal-sale order regained a current CRM source", risks)
    require(protected_formal_order.get("crmAdmission") == "BLOCKED",
            "protected formal-sale order CRM admission drift", risks)
    require([row.get("id") for row in protected_formal_order.get("revocations", [])] == [1],
            "protected formal-sale order revocation drift", risks)
    require(protected_formal_order.get("engineeringInstances") == [{
        "id": 6, "instanceNo": "OEI202610000005", "status": "inactive",
    }], "protected formal-sale order engineering instance drift", risks)

    result = {
        "gate": "Completed Work STRICT Gate",
        "status": "PASS" if not risks else "FAIL",
        "riskTotal": len(risks),
        "protectedSourceMismatch": sum("protected source mismatch" in row or "frozen source changed" in row for row in risks),
        "fixedBusinessSample": sum("fixed business sample" in row for row in risks),
        "databaseGate": "PASS" if before == after and database_before_hash == database_after_hash else "FAIL",
        "databaseBusinessWrite": readiness.get("businessWriteSideEffectCount"),
        "permissionMutation": (after.get("permissions", 0) - before.get("permissions", 0)) if before and after else None,
        "roleMutation": (
            (after.get("roles", 0) - before.get("roles", 0))
            + (after.get("rolePermissions", 0) - before.get("rolePermissions", 0))
            + (after.get("userRoleScopes", 0) - before.get("userRoleScopes", 0))
        ) if before and after else None,
        "migrationExecuted": False,
        "sourceBaselineManifestSha256": manifest_hash,
        "acceptedDifferenceProfileSha256": sha256(ACCEPTED_DIFFERENCE_PROFILE_PATH) if ACCEPTED_DIFFERENCE_PROFILE_PATH.is_file() else None,
        "databaseSha256Before": database_before_hash,
        "databaseSha256After": database_after_hash,
        "databaseCountsBefore": before,
        "databaseCountsAfter": after,
        "targetFacts": facts,
        "purposeRuntimeContract": purpose_contract,
        "materialRequirementRuntimeContract": requirement_contract,
        "databaseDiagnostics": database_diagnostics,
        "wholeOrderProjection": whole_order_projection,
        "routingFacts": routing_facts,
        "protectedFormalOrderFacts": protected_formal_order,
        "risks": risks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not risks else 1


if __name__ == "__main__":
    raise SystemExit(main())
