"""Create the authorized Item4 order-specific BOM through the formal service.

The default mode is read-only.  A write requires the explicit execution flag,
the exact current database SHA-256, and a byte-identical recoverable backup.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django

django.setup()

from django.db import connection, transaction
from masterdata.models import ExternalIdentity, Material
from planning.models import Demand, PlanningRequirement
from sales.models import SalesOrderItem
from system.models import OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition

from pde.engineering_calculation_service import OrderEngineeringClosureService
from pde.models import (
    BOMItem,
    BOMItemSourceRequirement,
    BOMVersion,
    EngineeringCalculationRecord,
    EngineeringDocumentVersion,
    EngineeringMaterialRequirement,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
    ProductBOM,
    ProductManufacturingOutput,
)


DATABASE = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
ACTOR = "pce_plan_r12"
ORDER_NO = "SO202609180003"
ITEM_ID = 4
INSTANCE_ID = 3
CALCULATION_ID = 4
BASELINE_ID = 2
MATERIAL_ID = 130
EXTERNAL_IDENTITY_ID = 51
REQUIREMENT_IDS = (28, 29, 30)
PREVIEW_HASH = "da32ff54b42a1ba6b5e9bd7cd105dd78d5f73085df06c1d823b9368474b1735a"
REASON = (
    "《SO202609180003 Item4按单BOMVersion承接实施指令》：仅将Item4/OEI3/"
    "Calculation4及已确认EngineeringMaterialRequirement28/29/30承接为按单BOM草稿；"
    "不重算工程事实，不创建工程资料、Demand、PlanningRequirement或ManufacturingOutput。"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest().upper()


def model_snapshot(model, pk: int) -> dict:
    row = model.objects.filter(pk=pk).values().first()
    assert row is not None, f"protected_object_missing:{model.__name__}:{pk}"
    return {"values": row, "sha256": payload_hash(row)}


def frozen_snapshot() -> dict:
    return {
        "salesOrderItem3": model_snapshot(SalesOrderItem, 3),
        "salesOrderItem4": model_snapshot(SalesOrderItem, ITEM_ID),
        "bomVersion3": model_snapshot(BOMVersion, 3),
        "oei3": model_snapshot(OrderEngineeringInstance, INSTANCE_ID),
        "baseline2": model_snapshot(OrderEngineeringBaseline, BASELINE_ID),
        "calculation4": model_snapshot(EngineeringCalculationRecord, CALCULATION_ID),
        "material130": model_snapshot(Material, MATERIAL_ID),
        "externalIdentity51": model_snapshot(ExternalIdentity, EXTERNAL_IDENTITY_ID),
        **{
            f"engineeringMaterialRequirement{pk}": model_snapshot(EngineeringMaterialRequirement, pk)
            for pk in REQUIREMENT_IDS
        },
    }


def protected_counts() -> dict:
    return {
        "demand": Demand.objects.count(),
        "planningRequirement": PlanningRequirement.objects.count(),
        "engineeringDocumentVersion": EngineeringDocumentVersion.objects.count(),
        "manufacturingOutput": ProductManufacturingOutput.objects.count(),
        "businessStateTransition": BusinessStateTransition.objects.count(),
    }


def physical_snapshot():
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
        rows = {}
        for name in names:
            cursor.execute(f"SELECT * FROM {connection.ops.quote_name(name)}")
            rows[name] = Counter(
                json.dumps(row, ensure_ascii=False, default=str) for row in cursor.fetchall()
            )
        cursor.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        schema_hash = hashlib.sha256(canonical(cursor.fetchall()).encode("utf-8")).hexdigest().upper()
    return rows, schema_hash


EXPECTED_DELTAS = {
    ProductBOM._meta.db_table: 1,
    BOMVersion._meta.db_table: 1,
    BOMItem._meta.db_table: 1,
    BOMItemSourceRequirement._meta.db_table: 3,
    OrganizationOperatingAuditRecord._meta.db_table: 1,
}


def compare_physical(before, after, *, expected_deltas) -> dict:
    old_rows, old_schema = before
    new_rows, new_schema = after
    assert old_schema == new_schema, "schema_changed"
    assert old_rows.keys() == new_rows.keys(), "table_set_changed"
    changes = {}
    sequence_changes = {}
    for table, rows in old_rows.items():
        current = new_rows[table]
        if current == rows:
            continue
        if table == "sqlite_sequence":
            old = {json.loads(row)[0]: json.loads(row)[1] for row in rows}
            new = {json.loads(row)[0]: json.loads(row)[1] for row in current}
            assert old.keys() == new.keys(), "sequence_table_set_changed"
            for name, old_value in old.items():
                delta = new[name] - old_value
                if delta:
                    assert name in expected_deltas, f"protected_sequence_changed:{name}"
                    assert delta == expected_deltas[name], f"unexpected_sequence_delta:{name}:{delta}"
                    sequence_changes[name] = delta
            continue
        assert table in expected_deltas, f"protected_table_changed:{table}"
        assert not (rows - current), f"existing_row_changed_or_removed:{table}"
        delta = sum(current.values()) - sum(rows.values())
        assert delta == expected_deltas[table], f"unexpected_append_count:{table}:{delta}"
        changes[table] = {
            "before": sum(rows.values()),
            "after": sum(current.values()),
            "added": delta,
        }
    assert set(changes) == set(expected_deltas), "unexpected_write_set"
    return {
        "schemaSha256": old_schema,
        "physicalTableCount": len(old_rows),
        "allExistingRowsPreserved": True,
        "changes": changes,
        "sequenceChanges": sequence_changes,
    }


def precheck(user) -> dict:
    item = SalesOrderItem.objects.select_related("sales_order").get(pk=ITEM_ID)
    calculation = EngineeringCalculationRecord.objects.select_related(
        "engineering_instance", "source_record",
    ).get(pk=CALCULATION_ID)
    exact_calculation_count = EngineeringCalculationRecord.objects.filter(
        pk=CALCULATION_ID,
        status="completed",
        sales_order_item_id=ITEM_ID,
        engineering_instance_id=INSTANCE_ID,
    ).count()
    active_instance_count = OrderEngineeringInstance.objects.filter(
        pk=INSTANCE_ID, sales_order_item_id=ITEM_ID,
    ).exclude(status__in={"cancelled", "superseded"}).count()
    product_bom_count = ProductBOM.objects.filter(order_engineering_instance_id=INSTANCE_ID).count()
    bom_version_count = BOMVersion.objects.filter(
        order_engineering_instance_id=INSTANCE_ID,
    ).count()
    source_version_count = BOMVersion.objects.filter(source_calculation_id=CALCULATION_ID).count()
    preview = OrderEngineeringClosureService.preview_bom(user=user, calculation_id=CALCULATION_ID)
    assert item.sales_order.order_no == ORDER_NO and item.line_no == 2
    assert calculation.engineering_instance_id == INSTANCE_ID
    assert calculation.sales_order_item_id == ITEM_ID
    assert exact_calculation_count == active_instance_count == 1
    assert product_bom_count == bom_version_count == source_version_count == 0
    assert preview["previewHash"] == PREVIEW_HASH
    assert preview["canGenerate"] is True and preview["firstRealBlocker"] is None
    assert preview["targetScope"]["coverageGate"] == "PASS"
    assert preview["rowCount"] == 1 and preview["sourceRequirementCount"] == 3
    row = preview["rows"][0]
    assert row["materialId"] == MATERIAL_ID
    assert row["sourceRequirementIds"] == list(REQUIREMENT_IDS)
    assert row["quantity"] == "1.939650" and row["uomCode"] == "m2"
    return {
        "productBomCount": product_bom_count,
        "bomVersionCount": bom_version_count,
        "sourceCalculationBomVersionCount": source_version_count,
        "exactCalculationCandidateCount": exact_calculation_count,
        "activeEngineeringInstanceCandidateCount": active_instance_count,
        "calculation": {
            "id": calculation.pk,
            "calculationNo": calculation.calculation_no,
            "status": calculation.status,
            "salesOrderItemId": calculation.sales_order_item_id,
            "orderEngineeringInstanceId": calculation.engineering_instance_id,
            "sourceRecordId": calculation.source_record_id,
            "resultHash": calculation.result_hash,
        },
        "preview": {
            "previewHash": preview["previewHash"],
            "canGenerate": preview["canGenerate"],
            "firstRealBlocker": preview["firstRealBlocker"],
            "targetScope": preview["targetScope"],
            "rowCount": preview["rowCount"],
            "sourceRequirementCount": preview["sourceRequirementCount"],
            "row": row,
        },
    }


def created_readback(audit_id: int) -> dict:
    versions = list(BOMVersion.objects.filter(
        source_calculation_id=CALCULATION_ID,
        order_engineering_instance_id=INSTANCE_ID,
        bom__order_engineering_instance_id=INSTANCE_ID,
        bom__company_id=1,
    ).select_related("bom", "source_calculation", "order_engineering_instance"))
    assert len(versions) == 1, "item4_bom_version_not_unique"
    version = versions[0]
    items = list(version.items.select_related("material", "uom").order_by("line_no", "pk"))
    assert len(items) == 1
    item = items[0]
    links = list(item.source_requirements.order_by("material_requirement_id"))
    assert [link.material_requirement_id for link in links] == list(REQUIREMENT_IDS)
    assert version.bom.bom_code == "OBOM-OEI202609000002"
    assert version.bom_version == "CALC-4" and version.revision == 1
    assert version.status == "draft" and version.bom_scope == "order_specific"
    assert version.applicability == {
        "salesOrderItemId": ITEM_ID,
        "sourceRecordId": 11,
        "calculationId": CALCULATION_ID,
    }
    assert item.material_id == MATERIAL_ID and item.uom.code == "m2"
    assert str(item.quantity) == "1.939650"
    assert item.item_role == "material" and item.supply_type == "MAKE"
    audit = OrganizationOperatingAuditRecord.objects.get(
        pk=audit_id,
        action_code="production.master_data.bom.maintain",
        target_type="BOMVersion",
        target_id=version.pk,
    )
    return {
        "productBom": {
            "id": version.bom_id,
            "bomCode": version.bom.bom_code,
            "status": version.bom.status,
            "orderEngineeringInstanceId": version.bom.order_engineering_instance_id,
        },
        "bomVersion": {
            "id": version.pk,
            "bomVersion": version.bom_version,
            "revision": version.revision,
            "status": version.status,
            "bomScope": version.bom_scope,
            "orderEngineeringInstanceId": version.order_engineering_instance_id,
            "sourceCalculationId": version.source_calculation_id,
            "previewHash": version.preview_hash,
            "generationKey": version.generation_key,
            "applicability": version.applicability,
        },
        "bomItem": {
            "id": item.pk,
            "lineNo": item.line_no,
            "materialId": item.material_id,
            "quantity": str(item.quantity),
            "uomId": item.uom_id,
            "uomCode": item.uom.code,
            "itemRole": item.item_role,
            "requirementType": item.requirement_type,
            "supplyType": item.supply_type,
            "scrapRateStatus": item.scrap_rate_status,
            "scrapRate": str(item.scrap_rate) if item.scrap_rate is not None else None,
            "sourceRequirementIds": [link.material_requirement_id for link in links],
            "contributedQuantities": [str(link.contributed_quantity) for link in links],
        },
        "audit": {
            "id": audit.pk,
            "actionCode": audit.action_code,
            "actorId": audit.actor_id,
            "organizationId": audit.organization_id,
            "targetType": audit.target_type,
            "targetId": audit.target_id,
            "reason": audit.reason,
            "before": audit.before_snapshot,
            "after": audit.after_snapshot,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized-item4", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--backup")
    args = parser.parse_args()

    assert Path(connection.settings_dict["NAME"]).resolve() == DATABASE.resolve(), "wrong_database"
    assert os.environ.get("PCE_RUNTIME_PROFILE") == "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    assert os.environ.get("PCE_DATABASE_IDENTITY") == "PDE-OPERABLE-ACCEPTANCE-20260912"
    assert os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") == "1"
    connection.ensure_connection()

    before_sha = sha256(DATABASE)
    if args.execute_authorized_item4:
        assert args.expected_sha256 and args.backup, "write_requires_expected_sha_and_backup"
        assert before_sha == args.expected_sha256.upper(), "database_sha_changed_before_write"
        backup = Path(args.backup).resolve()
        assert backup.is_file() and backup.parent.is_relative_to(DATABASE.parent), "invalid_backup"
        assert sha256(backup) == before_sha, "backup_sha_mismatch"

    user = User.objects.get(username=ACTOR, is_active=True, is_superuser=False)
    physical_before = physical_snapshot()
    frozen_before = frozen_snapshot()
    protected_counts_before = protected_counts()
    before = precheck(user)

    if not args.execute_authorized_item4:
        print(json.dumps({
            "mode": "READ_ONLY",
            "databaseSha256": before_sha,
            "before": before,
            "frozen": {key: value["sha256"] for key, value in frozen_before.items()},
            "protectedCounts": protected_counts_before,
        }, ensure_ascii=False, indent=2, default=str))
        return

    with transaction.atomic():
        result = OrderEngineeringClosureService.generate_bom(
            user=user,
            calculation_id=CALCULATION_ID,
            preview_hash=PREVIEW_HASH,
            reason=REASON,
        )
        assert result["idempotent"] is False
        assert result["auditId"]
        created = created_readback(result["auditId"])
        assert frozen_snapshot() == frozen_before, "protected_object_changed"
        assert protected_counts() == protected_counts_before, "forbidden_object_created"

    physical_after_first = physical_snapshot()
    physical_delta = compare_physical(
        physical_before, physical_after_first, expected_deltas=EXPECTED_DELTAS,
    )
    connection.close()
    after_first_sha = sha256(DATABASE)

    replay = OrderEngineeringClosureService.generate_bom(
        user=user,
        calculation_id=CALCULATION_ID,
        preview_hash=PREVIEW_HASH,
        reason=REASON,
    )
    assert replay["idempotent"] is True
    assert replay["alreadyGenerated"] is True
    physical_after_replay = physical_snapshot()
    assert physical_after_replay == physical_after_first, "idempotent_replay_wrote_database"
    assert frozen_snapshot() == frozen_before, "protected_object_changed_after_replay"
    assert protected_counts() == protected_counts_before, "forbidden_object_created_after_replay"
    connection.close()
    after_replay_sha = sha256(DATABASE)
    assert after_replay_sha == after_first_sha, "idempotent_replay_changed_database_sha"

    transition_ids = list(BusinessStateTransition.objects.order_by("pk").values_list("pk", flat=True))
    assert len(transition_ids) == protected_counts_before["businessStateTransition"]
    output = {
        "mode": "EXECUTED",
        "database": str(DATABASE),
        "databaseSha256": {
            "before": before_sha,
            "afterFirstExecution": after_first_sha,
            "afterIdempotentReplay": after_replay_sha,
        },
        "backup": {"path": str(Path(args.backup).resolve()), "sha256": before_sha},
        "before": before,
        "created": created,
        "businessStateTransition": {
            "createdCount": 0,
            "reason": "Initial draft creation is not a lifecycle state transition in the reused formal service.",
            "count": len(transition_ids),
        },
        "physicalDelta": physical_delta,
        "idempotency": {
            "firstExecutionIdempotent": result["idempotent"],
            "replayIdempotent": replay["idempotent"],
            "replayBusinessWriteCount": 0,
            "databaseShaUnchangedOnReplay": after_replay_sha == after_first_sha,
            "physicalSnapshotUnchangedOnReplay": physical_after_replay == physical_after_first,
        },
        "preservation": {
            "protectedObjectHashesBeforeAndAfterEqual": frozen_snapshot() == frozen_before,
            "protectedCountsBeforeAndAfterEqual": protected_counts() == protected_counts_before,
            "protectedObjectHashes": {
                key: value["sha256"] for key, value in frozen_before.items()
            },
            "protectedCounts": protected_counts_before,
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
