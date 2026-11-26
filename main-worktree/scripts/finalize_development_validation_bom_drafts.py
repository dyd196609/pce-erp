"""Create only the two authorized DEVELOPMENT_VALIDATION OEI BOM drafts.

Run against an isolated copy first.  The formal acceptance database additionally
requires --allow-formal-write and is backed up before the first transaction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from verify_engineering_runtime_closure_strict_gate import (
    ROOT,
    database_snapshot,
    protected_formal_order_facts,
    target_facts,
)
from verify_so202609180003_representative_material_requirements_strict_gate import configure_target


FORMAL_DATABASE = (
    ROOT.parent / "Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3"
).resolve()
EXPECTED = {
    5: {"oeiId": 4, "requirementId": 1, "materialId": 117, "quantity": "0.031200"},
    6: {"oeiId": 5, "requirementId": 2, "materialId": 140, "quantity": "1.860000"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def fail(message: str) -> None:
    raise RuntimeError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def serialize_versions(order):
    from pde.models import BOMVersion
    from pde.formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService

    rows = []
    versions = BOMVersion.objects.filter(
        source_calculation_id__in=EXPECTED,
        source_calculation__sales_order_item__sales_order=order,
    ).select_related(
        "bom__order_engineering_instance__sales_order_item__sales_order",
        "order_engineering_instance", "source_calculation",
    ).prefetch_related(
        "items__material", "items__uom",
        "items__source_requirements__material_requirement",
    ).order_by("source_calculation_id")
    for version in versions:
        items = []
        for item in version.items.order_by("line_no"):
            links = list(item.source_requirements.order_by("pk"))
            items.append({
                "id": item.pk,
                "materialId": item.material_id,
                "materialCode": item.material.code,
                "quantity": f"{item.quantity:.6f}",
                "uom": item.uom.code,
                "scrapRate": str(item.scrap_rate) if item.scrap_rate is not None else None,
                "scrapRateStatus": item.scrap_rate_status,
                "sourceRequirementIds": [link.material_requirement_id for link in links],
                "contributedQuantities": [f"{link.contributed_quantity:.6f}" for link in links],
            })
        rows.append({
            "bomId": version.bom_id,
            "bomCode": version.bom.bom_code,
            "oeiId": version.order_engineering_instance_id,
            "versionId": version.pk,
            "version": version.bom_version,
            "calculationId": version.source_calculation_id,
            "status": version.status,
            "items": items,
            "eligibility": FormalManufacturingEligibilityService.resolve(version),
        })
    return rows


def verify_rows(rows) -> None:
    require(len(rows) == 2, "exactly two representative BOM versions are required")
    require(len({row["bomId"] for row in rows}) == 2, "representatives must use two ProductBOM headers")
    require(len({row["oeiId"] for row in rows}) == 2, "representatives must use two OEIs")
    for row in rows:
        expected = EXPECTED.get(row["calculationId"])
        require(expected is not None, f"unexpected source calculation {row['calculationId']}")
        require(row["oeiId"] == expected["oeiId"], "BOM/OEI binding mismatch")
        require(row["status"] == "draft", "representative BOM version must remain draft")
        require(len(row["items"]) == 1, "each representative version must have one BOM item")
        item = row["items"][0]
        require(item["materialId"] == expected["materialId"], "representative material mismatch")
        require(item["quantity"] == expected["quantity"], "representative quantity mismatch")
        require(item["uom"] == "m2", "representative UOM mismatch")
        require(item["scrapRate"] is None and item["scrapRateStatus"] == "not_maintained",
                "unknown scrap semantics drift")
        require(item["sourceRequirementIds"] == [expected["requirementId"]],
                "requirement provenance mismatch")
        require(item["contributedQuantities"] == [expected["quantity"]],
                "requirement contribution mismatch")
        eligibility = row["eligibility"]
        require(eligibility["businessPurposeCode"] == "DEVELOPMENT_VALIDATION",
                "representative business purpose drift")
        require(eligibility["formalManufacturingEligible"] is False,
                "development validation unexpectedly became formally eligible")
        require(eligibility["decisionCode"] == "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN",
                "development validation decision code drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--allow-formal-write", action="store_true")
    parser.add_argument(
        "--backup-directory",
        type=Path,
        default=ROOT / "backups/pce-development-validation-bom-guard-20261004",
    )
    args = parser.parse_args()
    database = args.database.resolve()
    require(database.is_file(), "target database is missing")
    is_formal = database == FORMAL_DATABASE
    require(not is_formal or args.allow_formal_write,
            "formal acceptance write requires --allow-formal-write")

    hash_before = sha256(database)
    backup_path = None
    if is_formal:
        backup_directory = args.backup_directory.resolve()
        backup_directory.mkdir(parents=True, exist_ok=True)
        backup_path = backup_directory / (
            f"pde-operable-acceptance.before-dev-validation-bom-"
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"
        )
        require(backup_path.parent == backup_directory, "backup path escaped the approved directory")
        shutil.copy2(database, backup_path)
        require(sha256(backup_path) == hash_before, "backup hash mismatch")

    configure_target(database)
    from django.db import connections, transaction
    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from pde.formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
    from pde.models import (
        BOMItem,
        BOMItemSourceRequirement,
        BOMVersion,
        EngineeringCalculationRecord,
        EngineeringMaterialRequirement,
        ProductBOM,
        ProductManufacturingOutput,
    )
    from pde.order_bom_handoff_service import order_bom_handoff
    from pde.production_foundation_service import EngineeringLifecycleService, ProductionFoundationError
    from sales.models import SalesOrder
    from system.models import OrganizationOperatingAuditRecord, User

    operator = User.objects.filter(username="pce_plan_r12", is_active=True).first()
    admin = User.objects.filter(username="admin", is_active=True).first()
    require(operator is not None, "authorized existing employee operator is missing")
    require(admin is not None, "acceptance admin reader is missing")
    order = SalesOrder.objects.get(order_no="SO202609180003")
    before_counts = database_snapshot()
    target_before = target_facts()
    require(target_before.get("calculationCount") == 4, "completed calculation baseline drift")
    require(target_before.get("detailCount") == 388 and target_before.get("derivedFactCount") == 388,
            "388 saved facts drift")
    require(target_before.get("materialRequirementCount") == 2, "representative requirement count drift")
    existing_before = {
        "productBom": ProductBOM.objects.filter(
            order_engineering_instance__sales_order_item__sales_order=order,
        ).count(),
        "bomVersion": BOMVersion.objects.filter(
            source_calculation__sales_order_item__sales_order=order,
        ).count(),
        "bomItem": BOMItem.objects.filter(
            bom_version__source_calculation__sales_order_item__sales_order=order,
        ).count(),
        "sourceRequirementLink": BOMItemSourceRequirement.objects.filter(
            bom_item__bom_version__source_calculation__sales_order_item__sales_order=order,
        ).count(),
    }
    require(existing_before in (
        {"productBom": 0, "bomVersion": 0, "bomItem": 0, "sourceRequirementLink": 0},
        {"productBom": 2, "bomVersion": 2, "bomItem": 2, "sourceRequirementLink": 2},
    ), "unexpected pre-existing BOM scope")
    requirements = list(EngineeringMaterialRequirement.objects.filter(
        calculation_id__in=EXPECTED,
        calculation__sales_order_item__sales_order=order,
    ).order_by("calculation_id"))
    require([row.pk for row in requirements] == [1, 2], "requirement identity drift")
    calculations = list(EngineeringCalculationRecord.objects.filter(
        pk__in=EXPECTED,
        sales_order_item__sales_order=order,
        status="completed",
    ).order_by("pk"))
    require([row.pk for row in calculations] == [5, 6], "representative calculation identity drift")
    for calculation in calculations:
        eligibility = FormalManufacturingEligibilityService.resolve(calculation)
        require(eligibility["decisionCode"] == "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN",
                "pre-write development-validation eligibility drift")

    audit_before = OrganizationOperatingAuditRecord.objects.filter(
        action_code="production.master_data.bom.maintain",
    ).count()
    first_results = []
    # Treat the two explicitly authorized representative drafts as one write
    # unit, so an unexpected second-row failure cannot retain a partial result.
    with transaction.atomic():
        for calculation in calculations:
            preview = OrderEngineeringClosureService.preview_bom(
                user=operator, calculation_id=calculation.pk,
            )
            result = OrderEngineeringClosureService.generate_bom(
                user=operator,
                calculation_id=calculation.pk,
                preview_hash=preview["previewHash"],
                reason=(
                    "USER_AUTHORIZATION:DEVELOPMENT_VALIDATION正式制造资格最小门禁实施"
                    f";CALCULATION:{calculation.pk};DRAFT_ONLY"
                ),
            )
            first_results.append({
                "calculationId": calculation.pk,
                "bomId": result["bomId"],
                "bomVersionId": result["bomVersionId"],
                "idempotent": result["idempotent"],
                "auditId": result.get("auditId"),
            })
    connections.close_all()
    hash_after_initial = sha256(database)

    rows_after_initial = serialize_versions(order)
    verify_rows(rows_after_initial)
    audit_after_initial = OrganizationOperatingAuditRecord.objects.filter(
        action_code="production.master_data.bom.maintain",
    ).count()
    expected_new_audits = 0 if existing_before["bomVersion"] == 2 else 2
    require(audit_after_initial - audit_before == expected_new_audits,
            "initial BOM audit count drift")

    replay_results = []
    for calculation in calculations:
        preview = OrderEngineeringClosureService.preview_bom(
            user=operator, calculation_id=calculation.pk,
        )
        result = OrderEngineeringClosureService.generate_bom(
            user=operator,
            calculation_id=calculation.pk,
            preview_hash=preview["previewHash"],
            reason="IDEMPOTENT_REPLAY_MUST_WRITE_ZERO",
        )
        replay_results.append({
            "calculationId": calculation.pk,
            "bomId": result["bomId"],
            "bomVersionId": result["bomVersionId"],
            "idempotent": result["idempotent"],
            "auditId": result.get("auditId"),
        })
    connections.close_all()
    hash_after_replay = sha256(database)
    audit_after_replay = OrganizationOperatingAuditRecord.objects.filter(
        action_code="production.master_data.bom.maintain",
    ).count()
    require(hash_after_replay == hash_after_initial, "idempotent replay changed the database")
    require(audit_after_replay == audit_after_initial, "idempotent replay created an audit")
    require(all(row["idempotent"] is True and row["auditId"] is None for row in replay_results),
            "generate_bom replay was not idempotent")

    lifecycle_blocks = []
    for row in serialize_versions(order):
        version = BOMVersion.objects.get(pk=row["versionId"])
        for target_status in ("reviewed", "released"):
            try:
                if target_status == "reviewed":
                    EngineeringLifecycleService.transition(
                        "bom-versions", object_id=version.pk,
                        target_status=target_status, user=admin,
                        reason="DEVELOPMENT_VALIDATION guard verification",
                    )
                else:
                    EngineeringLifecycleService._formal_manufacturing_eligibility(
                        "bom-versions", version, target_status,
                    )
                fail(f"BOMVersion {version.pk} unexpectedly entered {target_status}")
            except ProductionFoundationError as error:
                require(error.code == "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN",
                        "BOMVersion guard returned the wrong error")
                lifecycle_blocks.append({
                    "versionId": version.pk,
                    "targetStatus": target_status,
                    "code": error.code,
                    "message": error.message,
                })

    representative_version = BOMVersion.objects.get(source_calculation_id=5)
    unsaved_output = ProductManufacturingOutput(
        definition_mode="order_specific",
        order_engineering_instance=representative_version.order_engineering_instance,
        bom_version=representative_version,
    )
    output_blocks = []
    for target_status in ("engineering_review", "released_to_manufacturing"):
        try:
            EngineeringLifecycleService._formal_manufacturing_eligibility(
                "manufacturing-outputs", unsaved_output, target_status,
            )
            fail(f"ManufacturingOutput unexpectedly entered {target_status}")
        except ProductionFoundationError as error:
            require(error.code == "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN",
                    "ManufacturingOutput guard returned the wrong error")
            output_blocks.append({
                "targetStatus": target_status,
                "code": error.code,
                "message": error.message,
            })

    handoff = order_bom_handoff(user=admin, order_id=order.pk)
    gate = handoff["bomHandoffStatus"]
    require(gate["productBomCount"] == 2 and gate["bomVersionCount"] == 2
            and gate["bomItemCount"] == 2, "BOM read model count drift")
    require(gate["formalRequirementObjectCount"] == 2
            and gate["remainingObjectCount"] == 69
            and gate["orderCoverageComplete"] is False
            and gate["coverageStatus"] == "PARTIAL", "partial coverage drift")
    require(gate["formalManufacturingEligible"] is False, "BOM read model eligibility drift")

    final_rows = serialize_versions(order)
    verify_rows(final_rows)
    target_after = target_facts()
    require(target_after.get("detailCount") == 388 and target_after.get("derivedFactCount") == 388,
            "388 facts changed during BOM generation")
    require(target_after.get("materialRequirementCount") == 2,
            "other material requirements were generated")
    protected_order = protected_formal_order_facts()
    require(protected_order.get("businessPurpose") == "FORMAL_SALE"
            and protected_order.get("currentValidCrmSourceCount") == 0
            and protected_order.get("crmAdmission") == "BLOCKED",
            "SO202610020004 protection drift")
    connections.close_all()
    hash_final = sha256(database)
    require(hash_final == hash_after_initial, "post-write validation changed the database")

    after_counts = database_snapshot()
    result = {
        "status": "PASS",
        "database": str(database),
        "formalAcceptanceDatabase": is_formal,
        "backup": str(backup_path) if backup_path else None,
        "backupSha256": sha256(backup_path) if backup_path else None,
        "databaseSha256Before": hash_before,
        "databaseSha256AfterInitialWrite": hash_after_initial,
        "databaseSha256AfterIdempotentReplay": hash_after_replay,
        "databaseSha256Final": hash_final,
        "firstExecution": first_results,
        "idempotentReplay": replay_results,
        "initialAuthorizedObjectWrites": {
            "productBom": 0 if existing_before["productBom"] == 2 else 2,
            "bomVersion": 0 if existing_before["bomVersion"] == 2 else 2,
            "bomItem": 0 if existing_before["bomItem"] == 2 else 2,
            "sourceRequirementLink": 0 if existing_before["sourceRequirementLink"] == 2 else 2,
            "audit": expected_new_audits,
        },
        "postInitialBusinessWriteCount": 0,
        "lifecycleBlocks": lifecycle_blocks,
        "manufacturingOutputBlocks": output_blocks,
        "bomRows": final_rows,
        "coverage": {
            key: gate[key] for key in (
                "formalEngineeringMaterialRequirementCount", "formalRequirementObjectCount",
                "remainingObjectCount", "orderCoverageComplete", "coverageStatus",
                "productBomCount", "bomVersionCount", "bomItemCount",
                "formalManufacturingEligible", "formalManufacturingDecisionCode",
            )
        },
        "targetFactsBefore": target_before,
        "targetFactsAfter": target_after,
        "databaseSnapshotBefore": before_counts,
        "databaseSnapshotAfter": after_counts,
        "protectedFormalOrderFacts": protected_order,
        "schemaChange": False,
        "migration": False,
        "routingPlanningMrpProcurementWrites": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

