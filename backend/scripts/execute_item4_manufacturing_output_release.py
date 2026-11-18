"""Release Item4 ProductManufacturingOutput 2 through the formal service.

The default mode is read-only.  The authorized mode is guarded by the exact
acceptance database identity and SHA-256, creates a byte-identical backup,
limits the service scope to Item4 for this process, proves the physical write
set, and replays the request to prove idempotency.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django

django.setup()

from django.db import connection
from django.test import override_settings

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
from planning.models import (
    Demand,
    MasterProductionScheduleLine,
    MasterProductionScheduleRun,
    MaterialRequirementsPlanningRun,
    PlanningRequirement,
    ProductionPlan,
)
from sales.models import SalesOrder, SalesOrderItem
from sales.services import engineering_readiness_facts, order_stage_readiness_facts
from system.models import OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition

from pde.manufacturing_output_generation_service import (
    OBJECT,
    generation_readback,
    output_snapshot,
    resolve_sources,
)
from pde.manufacturing_output_release_service import (
    ACTION,
    CONTRACT,
    RELEASE_RESPONSIBILITY,
    eligible_publishers,
    release_manufacturing_output,
    release_preflight,
    release_readback,
)
from pde.models import (
    BOMItem,
    BOMVersion,
    EngineeringCalculationRecord,
    EngineeringDocument,
    EngineeringDocumentVersion,
    EngineeringMaterialRequirement,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
    ProductBOM,
    ProductManufacturingOutput,
    RoutingVersion,
)


DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
)
DATABASE_IDENTITY = "PDE-OPERABLE-ACCEPTANCE-20260912"
SCOPE = {"companyCode": "COMP001", "orderNo": "SO202609180003", "lineNo": 2}
EXPECTED_SOURCE_FINGERPRINT = (
    "f7164ece32b75d60d8965adbe03d5df3297b3511444649a6bf74047236be4559"
)

ORDER_ID = 3
ORDER_NO = "SO202609180003"
ITEM_ID = 4
LINE_NO = 2
OUTPUT_ID = 2
INSTANCE_ID = 3
BASELINE_ID = 2
CALCULATION_ID = 4
PRODUCT_BOM_ID = 4
BOM_VERSION_ID = 4
BOM_ITEM_ID = 8
ROUTING_VERSION_ID = 31
ENGINEERING_DOCUMENT_ID = 2
ENGINEERING_DOCUMENT_VERSION_ID = 2
MATERIAL_ID = 130
REQUIREMENT_IDS = (28, 29, 30)

PUBLISHER_ID = 23
PUBLISHER_USERNAME = "pce_emp107"
FORBIDDEN_PUBLISHER_IDS = (24, 21, 10, 1)
IDEMPOTENCY_KEY = (
    "so202609180003-item4-manufacturing-output-release-20261012-v1"
)
REASON = (
    "《SO202609180003 Item4 ProductManufacturingOutput正式制造发布实施指令》："
    "由唯一正式制造输出发布责任人赵盛世（User23 / pce_emp107 / "
    "RESP_PROD_PLAN_001）确认PMO2冻结工程来源链完整，将draft正式发布为"
    "released_to_manufacturing；不创建Demand、PlanningRequirement，不进入MRP，"
    "不生成生产计划，不变更任何工程来源关系。"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def payload_hash(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest().upper()


def model_snapshot(model, pk: int) -> dict:
    row = model.objects.filter(pk=pk).values().first()
    assert row is not None, f"protected_object_missing:{model.__name__}:{pk}"
    return {"values": row, "sha256": payload_hash(row)}


def output_source_snapshot() -> dict:
    row = ProductManufacturingOutput.objects.filter(pk=OUTPUT_ID).values().get()
    allowed_to_change = {"release_status", "updated_at"}
    stable = {key: value for key, value in row.items() if key not in allowed_to_change}
    return {"values": stable, "sha256": payload_hash(stable)}


def protected_snapshot() -> dict:
    values = {
        "salesOrderItem3": model_snapshot(SalesOrderItem, 3),
        "salesOrderItem4": model_snapshot(SalesOrderItem, ITEM_ID),
        "item3ManufacturingOutput1": model_snapshot(ProductManufacturingOutput, 1),
        "item4ManufacturingOutput2StableSource": output_source_snapshot(),
        "productBom4": model_snapshot(ProductBOM, PRODUCT_BOM_ID),
        "bomVersion4": model_snapshot(BOMVersion, BOM_VERSION_ID),
        "bomItem8": model_snapshot(BOMItem, BOM_ITEM_ID),
        "routingVersion31": model_snapshot(RoutingVersion, ROUTING_VERSION_ID),
        "oei3": model_snapshot(OrderEngineeringInstance, INSTANCE_ID),
        "baseline2": model_snapshot(OrderEngineeringBaseline, BASELINE_ID),
        "calculation4": model_snapshot(EngineeringCalculationRecord, CALCULATION_ID),
        "engineeringDocument2": model_snapshot(
            EngineeringDocument, ENGINEERING_DOCUMENT_ID
        ),
        "engineeringDocumentVersion2": model_snapshot(
            EngineeringDocumentVersion, ENGINEERING_DOCUMENT_VERSION_ID
        ),
        "material130": model_snapshot(Material, MATERIAL_ID),
        "generationAudit2974": model_snapshot(
            OrganizationOperatingAuditRecord, 2974
        ),
        "generationTransition65": model_snapshot(BusinessStateTransition, 65),
        "generationWriteRequest2164": model_snapshot(MasterDataWriteRequest, 2164),
        "generationExternalIdentity2157": model_snapshot(ExternalIdentity, 2157),
    }
    values.update(
        {
            f"engineeringMaterialRequirement{pk}": model_snapshot(
                EngineeringMaterialRequirement, pk
            )
            for pk in REQUIREMENT_IDS
        }
    )
    return values


def protected_counts() -> dict:
    deployed_tables = set(connection.introspection.table_names())

    def count_if_deployed(model):
        if model._meta.db_table not in deployed_tables:
            return "TABLE_NOT_PRESENT"
        return model.objects.count()

    return {
        "productManufacturingOutput": ProductManufacturingOutput.objects.count(),
        "productBom": ProductBOM.objects.count(),
        "bomVersion": BOMVersion.objects.count(),
        "bomItem": BOMItem.objects.count(),
        "routingVersion": RoutingVersion.objects.count(),
        "engineeringCalculation": EngineeringCalculationRecord.objects.count(),
        "engineeringDocument": EngineeringDocument.objects.count(),
        "engineeringDocumentVersion": EngineeringDocumentVersion.objects.count(),
        "engineeringMaterialRequirement": EngineeringMaterialRequirement.objects.count(),
        "externalIdentity": ExternalIdentity.objects.count(),
        "demand": Demand.objects.count(),
        "planningRequirement": PlanningRequirement.objects.count(),
        "mpsRun": count_if_deployed(MasterProductionScheduleRun),
        "mpsLine": count_if_deployed(MasterProductionScheduleLine),
        "mrpRun": count_if_deployed(MaterialRequirementsPlanningRun),
        "productionPlan": count_if_deployed(ProductionPlan),
    }


def lifecycle_counts() -> dict:
    return {
        "productManufacturingOutput": ProductManufacturingOutput.objects.count(),
        "audit": OrganizationOperatingAuditRecord.objects.count(),
        "businessStateTransition": BusinessStateTransition.objects.count(),
        "masterDataWriteRequest": MasterDataWriteRequest.objects.count(),
        "externalIdentity": ExternalIdentity.objects.count(),
    }


def physical_snapshot():
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
        rows = {}
        for name in names:
            cursor.execute(f"SELECT * FROM {connection.ops.quote_name(name)}")
            rows[name] = Counter(
                json.dumps(row, ensure_ascii=False, default=str)
                for row in cursor.fetchall()
            )
        cursor.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        schema_hash = hashlib.sha256(
            canonical(cursor.fetchall()).encode("utf-8")
        ).hexdigest().upper()
    return rows, schema_hash


EXPECTED_APPENDS = {
    MasterDataWriteRequest._meta.db_table: 1,
    OrganizationOperatingAuditRecord._meta.db_table: 1,
    BusinessStateTransition._meta.db_table: 1,
}
OUTPUT_TABLE = ProductManufacturingOutput._meta.db_table


def compare_physical(before, after) -> dict:
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
                    assert name in EXPECTED_APPENDS, f"protected_sequence_changed:{name}"
                    assert delta == EXPECTED_APPENDS[name], (
                        f"unexpected_sequence_delta:{name}:{delta}"
                    )
                    sequence_changes[name] = delta
            continue
        if table == OUTPUT_TABLE:
            assert sum(rows.values()) == sum(current.values()), "output_count_changed"
            assert sum((rows - current).values()) == 1, "output_old_row_delta_not_one"
            assert sum((current - rows).values()) == 1, "output_new_row_delta_not_one"
            changes[table] = {
                "before": sum(rows.values()),
                "after": sum(current.values()),
                "updatedRows": 1,
            }
            continue
        assert table in EXPECTED_APPENDS, f"protected_table_changed:{table}"
        assert not (rows - current), f"existing_row_changed_or_removed:{table}"
        delta = sum(current.values()) - sum(rows.values())
        assert delta == EXPECTED_APPENDS[table], (
            f"unexpected_append_count:{table}:{delta}"
        )
        changes[table] = {
            "before": sum(rows.values()),
            "after": sum(current.values()),
            "added": delta,
        }
    assert set(changes) == set(EXPECTED_APPENDS) | {OUTPUT_TABLE}, (
        f"unexpected_write_set:{set(changes)}"
    )
    return {
        "schemaSha256": old_schema,
        "physicalTableCount": len(old_rows),
        "allExistingRowsPreservedExceptAuthorizedOutputLifecycleFields": True,
        "changes": changes,
        "sequenceChanges": sequence_changes,
    }


def publisher() -> User:
    user = User.objects.get(
        pk=PUBLISHER_ID,
        username=PUBLISHER_USERNAME,
        is_active=True,
        is_superuser=False,
    )
    assert user.company_id == 1
    actors = eligible_publishers(user.company_id)
    assert len(actors) == 1, "manufacturing_release_publisher_not_unique"
    assert actors[0]["userId"] == user.pk, "configured_publisher_not_formal_actor"
    assert actors[0]["releaseResponsibilityCode"] == RELEASE_RESPONSIBILITY
    return user


def exact_chain() -> tuple[SalesOrderItem, ProductManufacturingOutput, dict, str]:
    item = SalesOrderItem.objects.select_related("sales_order").get(pk=ITEM_ID)
    assert item.sales_order_id == ORDER_ID
    assert item.sales_order.order_no == ORDER_NO
    assert item.line_no == LINE_NO

    outputs = list(
        ProductManufacturingOutput.objects.filter(
            order_engineering_instance__sales_order_item=item
        )[:2]
    )
    assert len(outputs) == 1, "item4_manufacturing_output_count_not_one"
    output = outputs[0]
    assert output.pk == OUTPUT_ID

    instance, document, fields, fingerprint = resolve_sources(item)
    expected_fields = {
        "release_subject_type": "ORDER_ENGINEERED_PRODUCT",
        "definition_mode": "order_specific",
        "order_engineering_instance_id": INSTANCE_ID,
        "order_engineering_baseline_id": BASELINE_ID,
        "engineering_calculation_id": CALCULATION_ID,
        "bom_version_id": BOM_VERSION_ID,
        "routing_version_id": ROUTING_VERSION_ID,
        "engineering_document_version_id": ENGINEERING_DOCUMENT_VERSION_ID,
        "engineering_status": "ready",
    }
    assert instance.pk == INSTANCE_ID
    assert document.pk == ENGINEERING_DOCUMENT_VERSION_ID
    assert fields == expected_fields, f"unexpected_source_chain:{fields}"
    assert fingerprint == EXPECTED_SOURCE_FINGERPRINT
    for field, value in fields.items():
        assert getattr(output, field) == value, f"output_source_mismatch:{field}"
    assert BOMVersion.objects.get(pk=BOM_VERSION_ID).status == "released"
    assert RoutingVersion.objects.get(pk=ROUTING_VERSION_ID).status == "released"
    assert document.status == "released"
    assert document.related_bom_id == BOM_VERSION_ID
    assert document.related_routing_id == ROUTING_VERSION_ID
    assert document.engineering_calculation_id == CALCULATION_ID
    output.full_clean()
    return item, output, fields, fingerprint


def duplicate_release_facts() -> dict:
    return {
        "audits": OrganizationOperatingAuditRecord.objects.filter(
            action_code=ACTION, target_type=OBJECT, target_id=OUTPUT_ID
        ).count(),
        "transitions": BusinessStateTransition.objects.filter(
            action_code=ACTION, object_type=OBJECT, object_id=OUTPUT_ID
        ).count(),
        "writeRequests": MasterDataWriteRequest.objects.filter(
            action_code=ACTION,
            entity_type=OBJECT,
            target_entity_id=str(OUTPUT_ID),
        ).count(),
    }


def item4_downstream_counts() -> dict:
    return {
        "demand": Demand.objects.filter(sales_order_item_id=ITEM_ID).count(),
        "planningRequirement": PlanningRequirement.objects.filter(
            demand__sales_order_item_id=ITEM_ID
        ).count(),
    }


def precheck(user: User) -> dict:
    item, output, fields, fingerprint = exact_chain()
    assert output.release_status == "draft", "BLOCKED_BEFORE_WRITE:not_draft"
    assert generation_readback(output) == {
        "completed": True,
        "auditId": 2974,
        "writeRequestId": 2164,
        "initializationTransitionId": 65,
        "actorId": 23,
        "actorUsername": "pce_emp107",
        "createdAt": generation_readback(output)["createdAt"],
    }
    assert release_readback(output)["completed"] is False
    duplicates = duplicate_release_facts()
    assert duplicates == {"audits": 0, "transitions": 0, "writeRequests": 0}, (
        "BLOCKED_BEFORE_WRITE:duplicate_release_fact"
    )

    selected = release_preflight(output, user)
    assert selected["releaseAllowed"] is True
    assert selected["sourceReady"] is True
    assert selected["sourceFingerprint"] == fingerprint
    assert selected["currentPublisher"]["userId"] == user.pk
    assert selected["businessWriteCount"] == 0

    denied = []
    for user_id in FORBIDDEN_PUBLISHER_IDS:
        actor = User.objects.get(pk=user_id)
        projection = release_preflight(output, actor)
        assert projection["releaseAllowed"] is False
        assert projection["firstBlockerCode"] == "MANUFACTURING_RELEASE_PUBLISHER_DENIED"
        denied.append(
            {
                "userId": actor.pk,
                "username": actor.username,
                "releaseAllowed": False,
                "firstBlockerCode": projection["firstBlockerCode"],
            }
        )

    readiness = engineering_readiness_facts(SalesOrder.objects.get(pk=ORDER_ID))
    line = next(row for row in readiness["lines"] if row["salesOrderItemId"] == ITEM_ID)
    assert line["engineeringBlockerCode"] == "ORDER_ENGINEERING_OUTPUT_NOT_RELEASED"
    assert line["manufacturingReady"] is False
    assert line["planningDemandEligible"] is False
    assert item4_downstream_counts() == {"demand": 0, "planningRequirement": 0}

    return {
        "contractVersion": CONTRACT,
        "scope": SCOPE,
        "orderNo": item.sales_order.order_no,
        "salesOrderItemId": item.pk,
        "productManufacturingOutputCount": ProductManufacturingOutput.objects.filter(
            order_engineering_instance__sales_order_item_id=ITEM_ID
        ).count(),
        "productManufacturingOutput": output_snapshot(output),
        "sourceChain": {
            "salesOrderItemId": item.pk,
            "orderEngineeringInstanceId": output.order_engineering_instance_id,
            "engineeringBaselineId": output.order_engineering_baseline_id,
            "engineeringCalculationId": output.engineering_calculation_id,
            "bomVersionId": output.bom_version_id,
            "bomVersionStatus": "released",
            "engineeringDocumentVersionId": output.engineering_document_version_id,
            "engineeringDocumentVersionStatus": "released",
            "routingVersionId": output.routing_version_id,
            "routingVersionStatus": "released",
            "sourceSnapshot": fields,
            "sourceFingerprint": fingerprint,
            "allPass": True,
        },
        "generationReadback": generation_readback(output),
        "releaseReadback": release_readback(output),
        "duplicateReleaseFacts": duplicates,
        "responsibility": {
            "eligiblePublishers": eligible_publishers(user.company_id),
            "selectedPublisherId": user.pk,
            "selectedUsername": user.username,
            "permissionCode": selected["actionContract"]["requiredPermission"],
            "responsibilityCode": RELEASE_RESPONSIBILITY,
            "scopeCode": selected["currentPublisher"]["scopeCode"],
            "authorizationResult": "ALLOWED",
            "forbiddenPublishers": denied,
        },
        "releasePreflight": selected,
        "targetGateBefore": {
            "code": "ORDER_ENGINEERING_OUTPUT_NOT_RELEASED",
            "result": "BLOCKING",
        },
        "downstreamCounts": item4_downstream_counts(),
    }


def final_readback() -> dict:
    item, output, fields, fingerprint = exact_chain()
    assert output.release_status == "released_to_manufacturing"
    generation = generation_readback(output)
    publication = release_readback(output)
    assert generation["completed"] is True
    assert generation["auditId"] == 2974
    assert generation["writeRequestId"] == 2164
    assert generation["initializationTransitionId"] == 65
    assert publication["completed"] is True
    assert publication["actorId"] == PUBLISHER_ID
    assert publication["actorUsername"] == PUBLISHER_USERNAME

    readiness = engineering_readiness_facts(SalesOrder.objects.get(pk=ORDER_ID))
    line = next(row for row in readiness["lines"] if row["salesOrderItemId"] == ITEM_ID)
    assert line["engineeringBlockerCode"] is None
    assert line["manufacturingReady"] is True
    assert line["planningDemandEligible"] is True
    assert line["blockers"] == []
    assert line["manufacturingOutputId"] == OUTPUT_ID
    downstream = item4_downstream_counts()
    assert downstream == {"demand": 0, "planningRequirement": 0}

    stages = order_stage_readiness_facts(SalesOrder.objects.get(pk=ORDER_ID))
    unresolved = [
        row
        for row in readiness["lines"]
        if row["supplyBranch"] == "UNRESOLVED"
    ]
    next_blocker = (
        {
            "salesOrderItemId": unresolved[0]["salesOrderItemId"],
            "lineNo": unresolved[0]["lineNo"],
            "fact": unresolved[0]["supplyAdmission"]["reason"],
            "businessAction": "确认该订单行的 MAKE / BUY 供应承接事实",
        }
        if unresolved
        else None
    )
    return {
        "productManufacturingOutput": output_snapshot(output),
        "productManufacturingOutputCount": ProductManufacturingOutput.objects.filter(
            order_engineering_instance__sales_order_item_id=ITEM_ID
        ).count(),
        "sourceChain": {
            "orderNo": item.sales_order.order_no,
            "salesOrderItemId": item.pk,
            "orderEngineeringInstanceId": output.order_engineering_instance_id,
            "engineeringBaselineId": output.order_engineering_baseline_id,
            "engineeringCalculationId": output.engineering_calculation_id,
            "bomVersionId": output.bom_version_id,
            "engineeringDocumentVersionId": output.engineering_document_version_id,
            "routingVersionId": output.routing_version_id,
            "sourceSnapshot": fields,
            "sourceFingerprint": fingerprint,
            "allPass": True,
        },
        "generationReadback": generation,
        "releaseReadback": publication,
        "targetGate": {
            "code": "ORDER_ENGINEERING_OUTPUT_NOT_RELEASED",
            "result": "CLEARED",
        },
        "item4DemandAdmission": {
            "manufacturingReady": line["manufacturingReady"],
            "planningDemandEligible": line["planningDemandEligible"],
            "firstEngineeringBlockerCode": line["engineeringBlockerCode"],
            "blockers": line["blockers"],
        },
        "orderStageReadiness": stages,
        "nextRealBlocker": next_blocker,
        "downstreamCounts": downstream,
        "demandCreated": False,
        "planningRequirementCreated": False,
        "mrpEntered": False,
        "productionPlanCreated": False,
    }


def json_ready(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def validate_runtime() -> None:
    assert Path(connection.settings_dict["NAME"]).resolve() == DATABASE.resolve(), (
        "wrong_database"
    )
    assert os.environ.get("PCE_RUNTIME_PROFILE") == "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    assert os.environ.get("PCE_DATABASE_IDENTITY") == DATABASE_IDENTITY
    assert os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") == "1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized-item4", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--backup")
    parser.add_argument("--output")
    args = parser.parse_args()

    validate_runtime()
    before_sha = sha256(DATABASE)
    if args.expected_sha256:
        assert before_sha == args.expected_sha256.upper(), "database_sha_mismatch"

    with override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE):
        user = publisher()
        if args.verify_existing:
            final = final_readback()
            publication = final["releaseReadback"]
            result = {
                "mode": "VERIFY_EXISTING_READ_ONLY",
                "database": {
                    "identity": DATABASE_IDENTITY,
                    "path": str(DATABASE),
                    "sha256": before_sha,
                },
                "finalReadback": final,
                "formalFacts": {
                    "audit": model_snapshot(
                        OrganizationOperatingAuditRecord, publication["auditId"]
                    ),
                    "businessStateTransition": model_snapshot(
                        BusinessStateTransition,
                        publication["businessStateTransitionId"],
                    ),
                    "masterDataWriteRequest": model_snapshot(
                        MasterDataWriteRequest, publication["writeRequestId"]
                    ),
                },
                "lifecycleCounts": lifecycle_counts(),
                "protectedCounts": protected_counts(),
                "protectedObjectHashes": {
                    key: value["sha256"]
                    for key, value in protected_snapshot().items()
                },
            }
            serialized = json.dumps(json_ready(result), ensure_ascii=False, indent=2)
            if args.output:
                target = Path(args.output).resolve()
                assert target.is_relative_to(Path(__file__).resolve().parents[2]), (
                    "output_outside_source"
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(serialized + "\n", encoding="utf-8")
            print(serialized)
            return
        before = precheck(user)
        if not args.execute_authorized_item4:
            result = {
                "mode": "READ_ONLY",
                "database": {
                    "identity": DATABASE_IDENTITY,
                    "path": str(DATABASE),
                    "sha256": before_sha,
                },
                "before": before,
                "lifecycleCounts": lifecycle_counts(),
                "protectedCounts": protected_counts(),
            }
        else:
            assert args.expected_sha256, "expected_sha256_required"
            assert args.backup, "backup_required"
            backup = Path(args.backup).resolve()
            assert backup != DATABASE.resolve(), "backup_must_be_distinct"
            assert not backup.exists(), "backup_already_exists"
            backup.parent.mkdir(parents=True, exist_ok=True)
            connection.close()
            shutil.copy2(DATABASE, backup)
            assert sha256(backup) == before_sha, "backup_sha_mismatch"

            protected_before = protected_snapshot()
            counts_before = protected_counts()
            lifecycle_before = lifecycle_counts()
            physical_before = physical_snapshot()

            payload = {
                "action": ACTION,
                "sourceFingerprint": before["sourceChain"]["sourceFingerprint"],
                "reason": REASON,
            }
            first = release_manufacturing_output(
                user=user,
                output_id=OUTPUT_ID,
                payload=payload,
                idempotency_key=IDEMPOTENCY_KEY,
            )
            assert first["idempotentReplay"] is False
            assert first["row"]["statusCode"] == "released_to_manufacturing"
            first_readback = final_readback()

            physical_after_first = physical_snapshot()
            physical_delta = compare_physical(physical_before, physical_after_first)
            assert protected_snapshot() == protected_before, "protected_object_changed"
            assert protected_counts() == counts_before, "forbidden_object_count_changed"
            lifecycle_after_first = lifecycle_counts()
            assert lifecycle_after_first["productManufacturingOutput"] == lifecycle_before[
                "productManufacturingOutput"
            ]
            assert lifecycle_after_first["audit"] == lifecycle_before["audit"] + 1
            assert lifecycle_after_first["businessStateTransition"] == lifecycle_before[
                "businessStateTransition"
            ] + 1
            assert lifecycle_after_first["masterDataWriteRequest"] == lifecycle_before[
                "masterDataWriteRequest"
            ] + 1
            assert lifecycle_after_first["externalIdentity"] == lifecycle_before[
                "externalIdentity"
            ]
            connection.close()
            after_first_sha = sha256(DATABASE)

            replay = release_manufacturing_output(
                user=user,
                output_id=OUTPUT_ID,
                payload=payload,
                idempotency_key=IDEMPOTENCY_KEY,
            )
            assert replay["idempotentReplay"] is True
            assert replay["row"]["id"] == OUTPUT_ID
            physical_after_replay = physical_snapshot()
            assert physical_after_replay == physical_after_first, (
                "idempotent_replay_wrote_database"
            )
            assert protected_snapshot() == protected_before
            assert protected_counts() == counts_before
            final = final_readback()
            lifecycle_after_replay = lifecycle_counts()
            assert lifecycle_after_replay == lifecycle_after_first
            connection.close()
            after_replay_sha = sha256(DATABASE)
            assert after_replay_sha == after_first_sha, (
                "idempotent_replay_changed_database_sha"
            )

            result = {
                "mode": "EXECUTED",
                "database": {
                    "identity": DATABASE_IDENTITY,
                    "path": str(DATABASE),
                    "beforeSha256": before_sha,
                    "afterFirstExecutionSha256": after_first_sha,
                    "afterIdempotentReplaySha256": after_replay_sha,
                },
                "backup": {"path": str(backup), "sha256": sha256(backup)},
                "before": before,
                "firstExecution": first,
                "firstReadback": first_readback,
                "finalReadback": final,
                "physicalDelta": physical_delta,
                "lifecycleCounts": {
                    "before": lifecycle_before,
                    "afterFirstExecution": lifecycle_after_first,
                    "afterReplay": lifecycle_after_replay,
                },
                "idempotency": {
                    "key": IDEMPOTENCY_KEY,
                    "replay": replay,
                    "replayBusinessWriteCount": 0,
                    "databaseShaUnchangedOnReplay": after_replay_sha
                    == after_first_sha,
                    "physicalSnapshotUnchangedOnReplay": physical_after_replay
                    == physical_after_first,
                },
                "preservation": {
                    "protectedObjectHashesBeforeAndAfterEqual": protected_snapshot()
                    == protected_before,
                    "protectedCountsBeforeAndAfterEqual": protected_counts()
                    == counts_before,
                    "protectedObjectHashes": {
                        key: value["sha256"]
                        for key, value in protected_before.items()
                    },
                    "protectedCounts": counts_before,
                },
            }

    serialized = json.dumps(json_ready(result), ensure_ascii=False, indent=2)
    if args.output:
        target = Path(args.output).resolve()
        assert target.is_relative_to(Path(__file__).resolve().parents[2]), (
            "output_outside_source"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
