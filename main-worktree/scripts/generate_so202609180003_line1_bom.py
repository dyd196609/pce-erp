"""Controlled generation/readback binder for SO202609180003 line 1.

This is governance evidence tooling.  It does not implement BOM business
logic: the only write path is the existing transactional
``OrderEngineeringClosureService.generate_bom`` service.  The three phases
separate input locking, the explicitly authorized write, and read-only
post-generation reconciliation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


ORDER_NO = "SO202609180003"
CALCULATION_ID = 3
SALES_ORDER_ITEM_ID = 3
ENGINEERING_INSTANCE_ID = 2
ACTOR = "pce_plan_r12"
EXPECTED_REQUIREMENT_IDS = list(range(3, 28))
EXPECTED_MATERIAL_TOTALS = {
    130: ("15.951578", "m2"),
    249: ("25.000000", "支"),
    279: ("24.602000", "m"),
    280: ("49.204000", "m"),
    281: ("28.844000", "m"),
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_hash(value) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def configure(database: Path, *, query_only: bool) -> None:
    from edge_banding_requirement_workflow import configure as configure_django

    configure_django(database)
    if query_only:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA query_only = ON")


def database_diagnostics(path: Path) -> dict:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return {
            "path": str(path),
            "size": path.stat().st_size,
            "sha256": sha256(path),
            "integrityCheck": connection.execute("PRAGMA integrity_check").fetchall(),
            "foreignKeyCheck": connection.execute("PRAGMA foreign_key_check").fetchall(),
        }
    finally:
        connection.close()


def requirement_contract() -> dict:
    from pde.models import EngineeringCalculationRecord, EngineeringRuleDefinition

    calculation = EngineeringCalculationRecord.objects.select_related(
        "engineering_instance__sales_order_item__sales_order",
    ).get(pk=CALCULATION_ID)
    requirements = list(
        calculation.material_requirements.select_related("material", "uom", "source_detail")
        .order_by("pk")
    )
    rows = []
    totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    mapping_ids = []
    for row in requirements:
        quantity = row.gross_quantity if row.scrap_rate_status == "maintained" else row.net_quantity
        mapping_id = int((row.trace or {}).get("mappingRuleId") or 0)
        mapping_ids.append(mapping_id)
        totals[row.material_id] += quantity
        rows.append({
            "id": row.pk,
            "calculationId": row.calculation_id,
            "sourceDetailId": row.source_detail_id,
            "sourceDetailCalculationId": row.source_detail.calculation_id,
            "materialId": row.material_id,
            "materialCode": row.material.code,
            "materialName": row.material.name,
            "quantity": str(quantity),
            "netQuantity": str(row.net_quantity),
            "grossQuantity": None if row.gross_quantity is None else str(row.gross_quantity),
            "scrapRateStatus": row.scrap_rate_status,
            "uomId": row.uom_id,
            "uomCode": row.uom.code,
            "uomSymbol": row.uom.symbol,
            "mappingRuleId": mapping_id,
            "trace": row.trace,
            "orderSpecification": row.order_specification,
            "createdAt": row.created_at.isoformat(),
        })
    mappings = list(
        EngineeringRuleDefinition.objects.filter(pk__in=mapping_ids).order_by("pk").values(
            "id", "company_id", "rule_code", "version", "status", "specification",
        )
    )
    payload = {
        "calculation": {
            "id": calculation.pk,
            "calculationNo": calculation.calculation_no,
            "revision": calculation.revision,
            "status": calculation.status,
            "resultHash": calculation.result_hash,
            "engineeringInstanceId": calculation.engineering_instance_id,
            "salesOrderItemId": calculation.sales_order_item_id,
            "sourceRecordId": calculation.source_record_id,
            "orderNo": calculation.engineering_instance.sales_order_item.sales_order.order_no,
            "lineNo": calculation.engineering_instance.sales_order_item.line_no,
        },
        "requirementIds": [row["id"] for row in rows],
        "requirements": rows,
        "mappings": mappings,
        "totals": {
            str(material_id): str(quantity.quantize(Decimal("0.000001")))
            for material_id, quantity in sorted(totals.items())
        },
    }
    payload["inputContractHash"] = canonical_hash(payload)
    return payload


def actor_contract() -> dict:
    from pfm.models import Employee
    from pde.engineering_calculation_service import EngineeringCalculationService
    from pde.models import EngineeringCalculationRecord
    from system.models import RolePermission, User, UserRoleScopeAssignment

    user = User.objects.get(username=ACTOR)
    employee = Employee.objects.select_related("department_ref", "position_ref").get(user=user)
    calculation = EngineeringCalculationRecord.objects.get(pk=CALCULATION_ID)
    authorization = EngineeringCalculationService._authorize(
        user=user,
        action_code="production.master_data.bom.maintain",
        company_id=calculation.company_id,
        object_id=calculation.engineering_instance_id,
    )
    assignments = list(
        UserRoleScopeAssignment.objects.filter(user=user, active=True)
        .select_related("role", "organization")
        .order_by("pk")
        .values(
            "id", "role__code", "role__name", "organization_id", "scope_code", "active",
        )
    )
    role_ids = list(
        UserRoleScopeAssignment.objects.filter(user=user, active=True).values_list("role_id", flat=True)
    )
    permission_codes = list(
        RolePermission.objects.filter(role_id__in=role_ids)
        .order_by("permission__code")
        .values_list("permission__code", flat=True)
        .distinct()
    )
    return {
        "user": {
            "id": user.pk,
            "username": user.username,
            "companyId": user.company_id,
            "isActive": user.is_active,
            "isSuperuser": user.is_superuser,
        },
        "employee": {
            "id": employee.pk,
            "employeeNo": employee.employee_no,
            "name": employee.full_name,
            "status": employee.status,
            "departmentId": employee.department_ref_id,
            "departmentCode": employee.department_ref.code,
            "departmentName": employee.department_ref.name,
            "positionId": employee.position_ref_id,
            "positionCode": employee.position_ref.code,
            "positionName": employee.position_ref.name,
        },
        "assignments": assignments,
        "permissionCodes": permission_codes,
        "requiredPermission": "production.master_data.bom.maintain",
        "requiredPermissionPresent": "production.master_data.bom.maintain" in permission_codes,
        "authorization": authorization,
    }


def validate_contract(contract: dict) -> None:
    calculation = contract["calculation"]
    if calculation != {
        **calculation,
        "id": CALCULATION_ID,
        "engineeringInstanceId": ENGINEERING_INSTANCE_ID,
        "salesOrderItemId": SALES_ORDER_ITEM_ID,
        "orderNo": ORDER_NO,
        "lineNo": 1,
    }:
        raise RuntimeError("TARGET_SCOPE_DRIFT")
    if contract["requirementIds"] != EXPECTED_REQUIREMENT_IDS:
        raise RuntimeError("REQUIREMENT_ID_SET_DRIFT")
    if len(contract["mappings"]) != len(EXPECTED_REQUIREMENT_IDS):
        raise RuntimeError("RELEASED_MAPPING_CARDINALITY_DRIFT")
    if any(row["status"] != "released" for row in contract["mappings"]):
        raise RuntimeError("MAPPING_NOT_RELEASED")
    if len(set(row["mappingRuleId"] for row in contract["requirements"])) != 25:
        raise RuntimeError("REQUIREMENT_MAPPING_NOT_ONE_TO_ONE")
    expected_totals = {str(key): value[0] for key, value in EXPECTED_MATERIAL_TOTALS.items()}
    if contract["totals"] != expected_totals:
        raise RuntimeError(f"MATERIAL_TOTAL_DRIFT:{contract['totals']}")
    uom_by_material = {
        row["materialId"]: row["uomCode"] for row in contract["requirements"]
    }
    expected_uom = {key: value[1] for key, value in EXPECTED_MATERIAL_TOTALS.items()}
    if uom_by_material != expected_uom:
        raise RuntimeError(f"MATERIAL_UOM_DRIFT:{uom_by_material}")


def table_snapshot(path: Path) -> dict[str, dict]:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        result = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            rows = [dict(row) for row in connection.execute(f"SELECT * FROM {quoted} ORDER BY rowid")]
            result[table] = {
                "count": len(rows),
                "hash": canonical_hash(rows),
                "rows": rows,
            }
        return result
    finally:
        connection.close()


def table_diff(before_path: Path, after_path: Path) -> dict:
    before = table_snapshot(before_path)
    after = table_snapshot(after_path)
    changed = []
    for table in sorted(set(before) | set(after)):
        old = before.get(table, {"count": 0, "hash": "", "rows": []})
        new = after.get(table, {"count": 0, "hash": "", "rows": []})
        if old["hash"] == new["hash"]:
            continue
        old_rows = {row.get("id", index): row for index, row in enumerate(old["rows"])}
        new_rows = {row.get("id", index): row for index, row in enumerate(new["rows"])}
        added = sorted(set(new_rows) - set(old_rows))
        deleted = sorted(set(old_rows) - set(new_rows))
        updated = []
        for row_id in sorted(set(old_rows) & set(new_rows)):
            if old_rows[row_id] == new_rows[row_id]:
                continue
            fields = [
                field for field in sorted(set(old_rows[row_id]) | set(new_rows[row_id]))
                if old_rows[row_id].get(field) != new_rows[row_id].get(field)
            ]
            updated.append({
                "id": row_id,
                "changedFields": fields,
                "before": {field: old_rows[row_id].get(field) for field in fields},
                "after": {field: new_rows[row_id].get(field) for field in fields},
            })
        changed.append({
            "table": table,
            "beforeCount": old["count"],
            "afterCount": new["count"],
            "delta": new["count"] - old["count"],
            "addedIds": added,
            "deletedIds": deleted,
            "updatedRows": updated,
        })
    return {"changedTables": [row["table"] for row in changed], "tables": changed}


def phase_preflight(database: Path) -> dict:
    configure(database, query_only=True)
    contract = requirement_contract()
    validate_contract(contract)
    actor = actor_contract()
    if actor["user"]["isSuperuser"] or not actor["user"]["isActive"]:
        raise RuntimeError("FORMAL_ACTOR_INVALID")
    if actor["employee"]["status"] != "active" or not actor["requiredPermissionPresent"]:
        raise RuntimeError("FORMAL_ACTOR_PERMISSION_INVALID")
    return {
        "phase": "PRE_GENERATE_INPUT_LOCK",
        "status": "PASS",
        "database": database_diagnostics(database),
        "contract": contract,
        "actor": actor,
        "businessWriteCount": 0,
    }


def phase_generate(
    database: Path,
    *,
    backup: Path,
    expected_database_sha: str,
    expected_input_hash: str,
    preview_hash: str,
) -> dict:
    if sha256(database) != expected_database_sha.upper():
        raise RuntimeError("FORMAL_DATABASE_CHANGED_AFTER_BACKUP")
    if not backup.is_file() or sha256(backup) != expected_database_sha.upper():
        raise RuntimeError("BYTE_IDENTICAL_BACKUP_REQUIRED")
    configure(database, query_only=False)
    contract = requirement_contract()
    validate_contract(contract)
    if contract["inputContractHash"] != expected_input_hash.upper():
        raise RuntimeError("PREVIEW_TO_GENERATE_INPUT_CHANGED")

    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from system.models import User

    user = User.objects.get(username=ACTOR)
    result = OrderEngineeringClosureService.generate_bom(
        user=user,
        calculation_id=CALCULATION_ID,
        preview_hash=preview_hash,
        reason=(
            "USER_INSTRUCTION:SO202609180003:LINE1:FORMAL_BOM_GENERATION:2026-10-06; "
            "STRICT Gate PASS; PRE-GENERATE READY; byte-identical backup verified"
        ),
    )
    return {
        "phase": "FORMAL_GENERATE_BOM",
        "status": "PASS",
        "databaseShaBefore": expected_database_sha.upper(),
        "databaseShaAfter": sha256(database),
        "inputContractHash": contract["inputContractHash"],
        "previewHash": preview_hash,
        "result": result,
    }


def phase_postscan(database: Path, *, backup: Path) -> dict:
    configure(database, query_only=True)

    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from pde.models import BOMItemSourceRequirement, BOMVersion, ProductBOM
    from system.models import OrganizationOperatingAuditRecord, User

    preview = OrderEngineeringClosureService.preview_bom(
        user=User.objects.get(username=ACTOR), calculation_id=CALCULATION_ID,
    )
    version = (
        BOMVersion.objects.select_related(
            "bom__order_engineering_instance__sales_order_item__sales_order",
            "source_calculation",
        )
        .prefetch_related("items__material", "items__uom", "items__source_requirements__material_requirement")
        .get(source_calculation_id=CALCULATION_ID)
    )
    bom = version.bom
    items = []
    trace = []
    for item in version.items.select_related("material", "uom").order_by("line_no", "pk"):
        requirement_ids = list(
            item.source_requirements.order_by("material_requirement_id")
            .values_list("material_requirement_id", flat=True)
        )
        items.append({
            "id": item.pk,
            "lineNo": item.line_no,
            "materialId": item.material_id,
            "materialCode": item.material.code,
            "materialName": item.material.name,
            "quantity": str(item.quantity),
            "uomId": item.uom_id,
            "uomCode": item.uom.code,
            "uomSymbol": item.uom.symbol,
            "itemRole": item.item_role,
            "requirementType": item.requirement_type,
            "supplyType": item.supply_type,
            "sourceRequirementIds": requirement_ids,
        })
        trace.extend({"requirementId": row, "bomItemId": item.pk} for row in requirement_ids)

    audit = (
        OrganizationOperatingAuditRecord.objects.filter(
            action_code="production.master_data.bom.maintain",
            target_id=str(version.pk),
        )
        .order_by("-pk")
        .first()
    )
    diff = table_diff(backup, database)
    expected_tables = sorted({
        ProductBOM._meta.db_table,
        BOMVersion._meta.db_table,
        version.items.model._meta.db_table,
        BOMItemSourceRequirement._meta.db_table,
        OrganizationOperatingAuditRecord._meta.db_table,
    })
    unexpected = sorted(set(diff["changedTables"]) - set(expected_tables))
    missing_expected = sorted(set(expected_tables) - set(diff["changedTables"]))
    expected_deltas = {
        ProductBOM._meta.db_table: 1,
        BOMVersion._meta.db_table: 1,
        version.items.model._meta.db_table: 5,
        BOMItemSourceRequirement._meta.db_table: 25,
        OrganizationOperatingAuditRecord._meta.db_table: 1,
    }

    requirements = requirement_contract()
    validate_contract(requirements)
    item_totals = {
        str(row["materialId"]): str(Decimal(row["quantity"]).quantize(Decimal("0.000001")))
        for row in items
    }
    expected_totals = {str(key): value[0] for key, value in EXPECTED_MATERIAL_TOTALS.items()}
    trace_ids = sorted(row["requirementId"] for row in trace)

    order_boms = ProductBOM.objects.filter(
        order_engineering_instance__sales_order_item__sales_order__order_no=ORDER_NO,
        is_active=True,
    )
    line_summary = []
    for line_no in (1, 2, 3, 4):
        line_boms = order_boms.filter(
            order_engineering_instance__sales_order_item__line_no=line_no,
        )
        line_summary.append({
            "lineNo": line_no,
            "bomCount": line_boms.count(),
            "bomIds": list(line_boms.order_by("pk").values_list("pk", flat=True)),
            "versionIds": list(
                BOMVersion.objects.filter(bom__in=line_boms).order_by("pk").values_list("pk", flat=True)
            ),
        })

    failures = []
    if unexpected:
        failures.append(f"UNEXPECTED_CHANGED_TABLES:{unexpected}")
    if missing_expected:
        failures.append(f"EXPECTED_CHANGED_TABLES_MISSING:{missing_expected}")
    for table_row in diff["tables"]:
        table = table_row["table"]
        expected_delta = expected_deltas.get(table)
        if table_row["deletedIds"] or table_row["updatedRows"]:
            failures.append(f"EXISTING_ROW_CHANGED:{table}")
        if expected_delta is not None and (
            table_row["delta"] != expected_delta
            or len(table_row["addedIds"]) != expected_delta
        ):
            failures.append(
                f"EXPECTED_INSERT_DELTA_MISMATCH:{table}:{table_row['delta']}"
            )
    if len(items) != 5:
        failures.append(f"BOM_ITEM_COUNT:{len(items)}")
    if item_totals != expected_totals:
        failures.append(f"BOM_QUANTITY_RECONCILIATION:{item_totals}")
    if trace_ids != EXPECTED_REQUIREMENT_IDS or len(trace) != 25:
        failures.append(f"SOURCE_REQUIREMENT_TRACE:{trace_ids}")
    if {row["materialId"] for row in items} != set(EXPECTED_MATERIAL_TOTALS):
        failures.append("FALSE_BOM_MATERIAL_ROW")
    if not preview["alreadyGenerated"] or preview["bomId"] != bom.pk or preview["bomVersionId"] != version.pk:
        failures.append("POST_GENERATION_PREVIEW_READBACK")
    if version.status != "draft" or bom.status != "draft":
        failures.append("BOM_OR_VERSION_STATUS_ADVANCED")
    if line_summary[1]["bomCount"] != 0:
        failures.append("ORDER_LINE2_ENTERED")

    return {
        "phase": "FULL_READ_ONLY_POST_GENERATION_SCAN",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "database": database_diagnostics(database),
        "backup": database_diagnostics(backup),
        "bom": {
            "id": bom.pk,
            "bomNo": bom.bom_code,
            "name": bom.name,
            "status": bom.status,
            "isActive": bom.is_active,
            "salesOrderId": bom.order_engineering_instance.sales_order_item.sales_order_id,
            "salesOrderNo": bom.order_engineering_instance.sales_order_item.sales_order.order_no,
            "salesOrderItemId": bom.order_engineering_instance.sales_order_item_id,
            "lineNo": bom.order_engineering_instance.sales_order_item.line_no,
            "engineeringInstanceId": bom.order_engineering_instance_id,
            "createdAt": bom.created_at.isoformat(),
        },
        "version": {
            "id": version.pk,
            "version": version.bom_version,
            "revision": version.revision,
            "status": version.status,
            "approvalState": version.approval_state,
            "sourceCalculationId": version.source_calculation_id,
            "previewHash": version.preview_hash,
            "generationKey": version.generation_key,
            "createdAt": version.created_at.isoformat(),
            "published": version.status == "released",
        },
        "actorAudit": None if audit is None else {
            "id": audit.pk,
            "actorId": audit.actor_id,
            "actionCode": audit.action_code,
            "reason": audit.reason,
            "createdAt": audit.created_at.isoformat(),
            "afterSnapshot": audit.after_snapshot,
        },
        "itemCount": len(items),
        "items": items,
        "sourceRequirementLinkCount": len(trace),
        "sourceRequirementTrace": trace,
        "requirementContractHash": requirements["inputContractHash"],
        "quantityReconciliation": {
            "expected": expected_totals,
            "actual": item_totals,
            "pass": item_totals == expected_totals,
        },
        "falseMaterialRows": [
            row for row in items if row["materialId"] not in EXPECTED_MATERIAL_TOTALS
        ],
        "postGenerationPreview": {
            key: preview.get(key) for key in (
                "status", "previewHash", "rowCount", "sourceRequirementCount",
                "canGenerate", "alreadyGenerated", "bomId", "bomVersionId",
                "bomVersion", "firstRealBlocker", "businessWriteSideEffectCount",
            )
        },
        "idempotency": {
            "sourceCalculationVersionCount": BOMVersion.objects.filter(
                source_calculation_id=CALCULATION_ID,
            ).count(),
            "generationKeyVersionCount": BOMVersion.objects.filter(
                generation_key=version.generation_key,
            ).count(),
            "activeOrderEngineeringBomCount": ProductBOM.objects.filter(
                company_id=bom.company_id,
                order_engineering_instance_id=ENGINEERING_INSTANCE_ID,
                bom_type="manufacturing",
                is_active=True,
            ).count(),
            "proof": "READ_ONLY_UNIQUENESS_AND_ALREADY_GENERATED",
            "formalReplayExecuted": False,
        },
        "lineSummary": line_summary,
        "bomCompletion": {
            "completed": sum(1 for row in line_summary if row["bomCount"] > 0),
            "total": len(line_summary),
        },
        "tableDiff": diff,
        "expectedChangedTables": expected_tables,
        "unexpectedChangedTables": unexpected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("check", "preflight", "generate", "postscan"))
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--expected-database-sha", default="")
    parser.add_argument("--expected-input-hash", default="")
    parser.add_argument("--preview-hash", default="")
    args = parser.parse_args()
    database = args.database.resolve()
    if not database.is_file():
        raise SystemExit("FORMAL_DATABASE_NOT_FOUND")

    if args.phase == "check":
        diagnostics = database_diagnostics(database)
        result = {
            "phase": "DATABASE_CHECK",
            "status": "PASS" if diagnostics["integrityCheck"] == [("ok",)] and not diagnostics["foreignKeyCheck"] else "FAIL",
            "database": diagnostics,
        }
    elif args.phase == "preflight":
        result = phase_preflight(database)
    elif args.phase == "generate":
        if not all((args.backup, args.expected_database_sha, args.expected_input_hash, args.preview_hash)):
            raise SystemExit("GENERATE_ARGUMENTS_REQUIRED")
        result = phase_generate(
            database,
            backup=args.backup.resolve(),
            expected_database_sha=args.expected_database_sha,
            expected_input_hash=args.expected_input_hash,
            preview_hash=args.preview_hash,
        )
    else:
        if not args.backup:
            raise SystemExit("POSTSCAN_BACKUP_REQUIRED")
        result = phase_postscan(database, backup=args.backup.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
