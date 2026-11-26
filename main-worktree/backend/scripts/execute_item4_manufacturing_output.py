"""Create the one authorized Item4 manufacturing output through the formal service.

The default mode is read-only. Formal execution requires the exact current
database SHA-256 and a byte-identical recoverable backup. The activation scope
is limited to COMP001 / SO202609180003 / line 2 (SalesOrderItem ID4) for this
process only; the service default and Item3 scope are not changed.
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

from django.db import connection
from django.test import override_settings

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
from planning.models import Demand, PlanningRequirement
from sales.models import SalesOrder, SalesOrderItem
from sales.services import engineering_readiness_facts
from system.models import OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition

from pde.engineering_document_version_release_service import (
    project_release_content_integrity,
    project_release_source_completeness,
    release_readback,
)
from pde.manufacturing_output_generation_service import (
    ACTION,
    OBJECT,
    candidate_projection,
    eligible_executors,
    generate_manufacturing_output,
    generation_readback,
    output_snapshot,
    resolve_sources,
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

ORDER_ID = 3
ORDER_NO = "SO202609180003"
ITEM_ID = 4
LINE_NO = 2
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

EXECUTOR_ID = 23
EXECUTOR_USERNAME = "pce_emp107"
IDEMPOTENCY_KEY = "so202609180003-item4-manufacturing-output-generate-20261012-v1"
REASON = (
    "《SO202609180003 Item4 ProductManufacturingOutput正式承接实施指令》：由正式制造输出"
    "责任人赵盛世（User23 / pce_emp107）确认Item4/OEI3唯一已发布工程来源链并生成draft"
    "制造输出；不发布制造输出，不创建Demand、PlanningRequirement，不进入MRP或生产计划。"
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


def protected_snapshot() -> dict:
    values = {
        "salesOrderItem3": model_snapshot(SalesOrderItem, 3),
        "salesOrderItem4": model_snapshot(SalesOrderItem, ITEM_ID),
        "item3ManufacturingOutput1": model_snapshot(ProductManufacturingOutput, 1),
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
        "engineeringDocumentReviewAudit2972": model_snapshot(
            OrganizationOperatingAuditRecord, 2972
        ),
        "engineeringDocumentReleaseAudit2973": model_snapshot(
            OrganizationOperatingAuditRecord, 2973
        ),
        "engineeringDocumentReviewTransition63": model_snapshot(
            BusinessStateTransition, 63
        ),
        "engineeringDocumentReleaseTransition64": model_snapshot(
            BusinessStateTransition, 64
        ),
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
    return {
        "productBom": ProductBOM.objects.count(),
        "bomVersion": BOMVersion.objects.count(),
        "bomItem": BOMItem.objects.count(),
        "routingVersion": RoutingVersion.objects.count(),
        "engineeringCalculation": EngineeringCalculationRecord.objects.count(),
        "engineeringDocument": EngineeringDocument.objects.count(),
        "engineeringDocumentVersion": EngineeringDocumentVersion.objects.count(),
        "engineeringMaterialRequirement": EngineeringMaterialRequirement.objects.count(),
        "demand": Demand.objects.count(),
        "planningRequirement": PlanningRequirement.objects.count(),
    }


def lifecycle_counts() -> dict:
    return {
        "productManufacturingOutput": ProductManufacturingOutput.objects.count(),
        "audit": OrganizationOperatingAuditRecord.objects.count(),
        "businessStateTransition": BusinessStateTransition.objects.count(),
        "externalIdentity": ExternalIdentity.objects.count(),
        "masterDataWriteRequest": MasterDataWriteRequest.objects.count(),
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


EXPECTED_DELTAS = {
    ProductManufacturingOutput._meta.db_table: 1,
    ExternalIdentity._meta.db_table: 1,
    MasterDataWriteRequest._meta.db_table: 1,
    OrganizationOperatingAuditRecord._meta.db_table: 1,
    BusinessStateTransition._meta.db_table: 1,
}


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
                    assert name in EXPECTED_DELTAS, f"protected_sequence_changed:{name}"
                    assert delta == EXPECTED_DELTAS[name], (
                        f"unexpected_sequence_delta:{name}:{delta}"
                    )
                    sequence_changes[name] = delta
            continue
        assert table in EXPECTED_DELTAS, f"protected_table_changed:{table}"
        assert not (rows - current), f"existing_row_changed_or_removed:{table}"
        delta = sum(current.values()) - sum(rows.values())
        assert delta == EXPECTED_DELTAS[table], (
            f"unexpected_append_count:{table}:{delta}"
        )
        changes[table] = {
            "before": sum(rows.values()),
            "after": sum(current.values()),
            "added": delta,
        }
    assert set(changes) == set(EXPECTED_DELTAS), "unexpected_write_set"
    return {
        "schemaSha256": old_schema,
        "physicalTableCount": len(old_rows),
        "allExistingRowsPreserved": True,
        "changes": changes,
        "sequenceChanges": sequence_changes,
    }


def executor() -> User:
    user = User.objects.get(
        pk=EXECUTOR_ID,
        username=EXECUTOR_USERNAME,
        is_active=True,
        is_superuser=False,
    )
    assert user.company_id == 1
    actors = eligible_executors(user.company_id)
    assert len(actors) == 1, "manufacturing_output_executor_not_unique"
    assert actors[0]["userId"] == user.pk, "configured_executor_not_formal_actor"
    return user


def exact_chain() -> tuple[SalesOrderItem, OrderEngineeringInstance, EngineeringDocumentVersion, dict, str]:
    item = SalesOrderItem.objects.select_related("sales_order").get(pk=ITEM_ID)
    assert item.sales_order_id == ORDER_ID
    assert item.sales_order.order_no == ORDER_NO
    assert item.line_no == LINE_NO

    instances = list(
        OrderEngineeringInstance.objects.filter(sales_order_item=item)
        .exclude(status="inactive")[:2]
    )
    assert len(instances) == 1, "item4_oei_candidate_count_not_one"
    assert instances[0].pk == INSTANCE_ID

    documents = list(
        EngineeringDocumentVersion.objects.filter(
            order_engineering_instance=instances[0],
            release_subject_type="ORDER_ENGINEERED_PRODUCT",
        )
        .exclude(status="obsolete")[:2]
    )
    assert len(documents) == 1, "item4_document_candidate_count_not_one"
    assert documents[0].pk == ENGINEERING_DOCUMENT_VERSION_ID

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
    assert document.status == "released"
    assert document.related_bom.status == "released"
    assert document.related_routing.status == "released"
    assert document.engineering_calculation_id == CALCULATION_ID
    assert document.order_engineering_baseline_id == BASELINE_ID
    document.full_clean()
    return item, instance, document, fields, fingerprint


def duplicate_facts(instance_id: int) -> dict:
    return {
        "outputsForItem4Oei3": ProductManufacturingOutput.objects.filter(
            order_engineering_instance_id=instance_id
        ).count(),
        "sourceIdentityCandidates": ExternalIdentity.objects.filter(
            organization_id=1,
            source_system="PCE",
            source_type="FORMAL_ORDER_ENGINEERING",
            source_object_type=OBJECT,
            external_id=f"OEI:{instance_id}:MANUFACTURING_OUTPUT",
        ).count(),
        "item4GenerationAudits": OrganizationOperatingAuditRecord.objects.filter(
            action_code=ACTION,
            target_type=OBJECT,
            target_id__in=ProductManufacturingOutput.objects.filter(
                order_engineering_instance_id=instance_id
            ).values("pk"),
        ).count(),
        "item4GenerationTransitions": BusinessStateTransition.objects.filter(
            action_code=ACTION,
            object_type=OBJECT,
            object_id__in=ProductManufacturingOutput.objects.filter(
                order_engineering_instance_id=instance_id
            ).values("pk"),
        ).count(),
    }


def precheck(user: User) -> dict:
    item, instance, document, fields, fingerprint = exact_chain()
    projection = candidate_projection(user)
    assert projection["salesOrderItemId"] == ITEM_ID
    assert projection["lineNo"] == LINE_NO
    assert projection["sourceReady"] is True
    assert projection["generationAllowed"] is True
    assert projection["outputCount"] == 0
    assert projection["sourceIds"] == fields
    assert projection["sourceFingerprint"] == fingerprint

    source_counts = {
        "item4ProductManufacturingOutputCount": ProductManufacturingOutput.objects.filter(
            order_engineering_instance__sales_order_item=item
        ).count(),
        "oei3ManufacturingOutputCount": ProductManufacturingOutput.objects.filter(
            order_engineering_instance=instance
        ).count(),
        "activeOeiCandidateCount": OrderEngineeringInstance.objects.filter(
            sales_order_item=item
        )
        .exclude(status="inactive")
        .count(),
        "releasedDocumentCandidateCount": EngineeringDocumentVersion.objects.filter(
            order_engineering_instance=instance,
            release_subject_type="ORDER_ENGINEERED_PRODUCT",
        )
        .exclude(status="obsolete")
        .count(),
        "resolvedManufacturingOutputCandidateCount": 1,
    }
    assert source_counts == {
        "item4ProductManufacturingOutputCount": 0,
        "oei3ManufacturingOutputCount": 0,
        "activeOeiCandidateCount": 1,
        "releasedDocumentCandidateCount": 1,
        "resolvedManufacturingOutputCandidateCount": 1,
    }, "BLOCKED_BEFORE_WRITE:candidateCount_not_one_or_existing_output"

    completeness = project_release_source_completeness(document)
    integrity = project_release_content_integrity(document)
    publication = release_readback(document)
    assert completeness["complete"] is True
    assert integrity["valid"] is True
    assert publication["completed"] is True
    duplicates = duplicate_facts(instance.pk)
    assert duplicates == {
        "outputsForItem4Oei3": 0,
        "sourceIdentityCandidates": 0,
        "item4GenerationAudits": 0,
        "item4GenerationTransitions": 0,
    }, "BLOCKED_BEFORE_WRITE:duplicate_output_candidate"
    return {
        "scope": SCOPE,
        "item": {"id": item.pk, "lineNo": item.line_no, "orderNo": ORDER_NO},
        "counts": source_counts,
        "sourceChain": {
            "salesOrderId": item.sales_order_id,
            "salesOrderItemId": item.pk,
            "orderEngineeringInstanceId": instance.pk,
            "engineeringBaselineId": fields["order_engineering_baseline_id"],
            "engineeringCalculationId": fields["engineering_calculation_id"],
            "bomVersionId": fields["bom_version_id"],
            "engineeringDocumentVersionId": fields[
                "engineering_document_version_id"
            ],
            "routingVersionId": fields["routing_version_id"],
            "sourceFingerprint": fingerprint,
            "allPass": True,
        },
        "sourceCompleteness": completeness,
        "contentIntegrity": integrity,
        "engineeringDocumentReleaseReadback": publication,
        "responsibility": {
            "eligibleExecutors": eligible_executors(user.company_id),
            "selectedExecutorId": user.pk,
            "selectedUsername": user.username,
            "permissionCode": projection["permissionCode"],
            "responsibilityCode": projection["currentActor"]["responsibilityCode"],
            "authorizationResult": "ALLOWED",
        },
        "duplicateFacts": duplicates,
        "candidateProjection": projection,
    }


def final_readback(output_id: int) -> dict:
    item, instance, document, fields, fingerprint = exact_chain()
    outputs = list(
        ProductManufacturingOutput.objects.filter(
            order_engineering_instance=instance
        )[:2]
    )
    assert len(outputs) == 1, "item4_manufacturing_output_not_unique"
    output = outputs[0]
    assert output.pk == output_id
    assert output.release_status == "draft"
    assert output.release_status != "released_to_manufacturing"
    for field, value in fields.items():
        assert getattr(output, field) == value, f"source_field_mismatch:{field}"
    output.full_clean()
    proof = generation_readback(output)
    assert proof["completed"] is True

    order = SalesOrder.objects.get(pk=ORDER_ID)
    readiness = engineering_readiness_facts(order)
    line = next(
        row for row in readiness["lines"] if row["salesOrderItemId"] == ITEM_ID
    )
    assert line["engineeringBlockerCode"] != "ORDER_ENGINEERING_OUTPUT_NOT_UNIQUE"
    assert line["engineeringBlockerCode"] == "ORDER_ENGINEERING_OUTPUT_NOT_RELEASED"
    assert line["manufacturingReady"] is False
    assert line["planningDemandEligible"] is False

    return {
        "productManufacturingOutput": output_snapshot(output),
        "uniqueCount": len(outputs),
        "sourceChain": {
            "orderNo": item.sales_order.order_no,
            "salesOrderItemId": item.pk,
            "orderEngineeringInstanceId": instance.pk,
            "engineeringBaselineId": output.order_engineering_baseline_id,
            "engineeringCalculationId": output.engineering_calculation_id,
            "bomVersionId": output.bom_version_id,
            "engineeringDocumentVersionId": output.engineering_document_version_id,
            "routingVersionId": output.routing_version_id,
            "sourceFingerprint": fingerprint,
            "allPass": True,
        },
        "generationReadback": proof,
        "targetGate": {
            "code": "ORDER_ENGINEERING_OUTPUT_NOT_UNIQUE",
            "result": "CLEARED",
        },
        "demandAdmission": {
            "code": "ORDER_DEMAND_MANUFACTURING_NOT_READY",
            "manufacturingReady": line["manufacturingReady"],
            "planningDemandEligible": line["planningDemandEligible"],
            "firstEngineeringBlockerCode": line["engineeringBlockerCode"],
            "blockers": line["blockers"],
        },
        "manufacturingReleaseExecuted": False,
        "demandCreated": False,
        "planningRequirementCreated": False,
    }


def json_ready(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized-item4", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--backup")
    parser.add_argument("--output")
    args = parser.parse_args()

    assert Path(connection.settings_dict["NAME"]).resolve() == DATABASE.resolve(), (
        "wrong_database"
    )
    assert os.environ.get("PCE_RUNTIME_PROFILE") == "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    assert os.environ.get("PCE_DATABASE_IDENTITY") == DATABASE_IDENTITY
    assert os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") == "1"
    connection.ensure_connection()
    before_sha = sha256(DATABASE)

    if args.execute_authorized_item4:
        assert args.expected_sha256 and args.backup, (
            "write_requires_expected_sha_and_backup"
        )
        assert before_sha == args.expected_sha256.upper(), (
            "database_sha_changed_before_write"
        )
        backup = Path(args.backup).resolve()
        assert backup.is_file() and backup.parent.is_relative_to(DATABASE.parent), (
            "invalid_backup"
        )
        assert sha256(backup) == before_sha, "backup_sha_mismatch"

    with override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE):
        user = executor()

        if args.verify_existing:
            outputs = list(
                ProductManufacturingOutput.objects.filter(
                    order_engineering_instance_id=INSTANCE_ID
                )[:2]
            )
            assert len(outputs) == 1, "item4_manufacturing_output_not_unique"
            output = {
                "mode": "READ_ONLY_FINAL",
                "database": {
                    "identity": DATABASE_IDENTITY,
                    "path": str(DATABASE),
                    "sha256": before_sha,
                },
                "finalReadback": final_readback(outputs[0].pk),
                "lifecycleCounts": lifecycle_counts(),
                "protectedCounts": protected_counts(),
                "protectedObjectHashes": {
                    key: value["sha256"]
                    for key, value in protected_snapshot().items()
                },
            }
        else:
            physical_before = physical_snapshot()
            protected_before = protected_snapshot()
            counts_before = protected_counts()
            lifecycle_before = lifecycle_counts()
            before = precheck(user)

            if not args.execute_authorized_item4:
                output = {
                    "mode": "READ_ONLY",
                    "database": {
                        "identity": DATABASE_IDENTITY,
                        "path": str(DATABASE),
                        "sha256": before_sha,
                    },
                    "before": before,
                    "lifecycleCounts": lifecycle_before,
                    "protectedCounts": counts_before,
                    "protectedObjectHashes": {
                        key: value["sha256"]
                        for key, value in protected_before.items()
                    },
                }
            else:
                projection = before["candidateProjection"]
                payload = {
                    "salesOrderItemId": projection["salesOrderItemId"],
                    "sourceFingerprint": projection["sourceFingerprint"],
                    "action": ACTION,
                    "reason": REASON,
                }
                first = generate_manufacturing_output(
                    user=user,
                    payload=payload,
                    idempotency_key=IDEMPOTENCY_KEY,
                )
                assert first["idempotentReplay"] is False
                assert first["manufacturingReleaseExecuted"] is False
                first_readback = final_readback(first["row"]["id"])

                physical_after_first = physical_snapshot()
                physical_delta = compare_physical(
                    physical_before, physical_after_first
                )
                assert protected_snapshot() == protected_before, (
                    "protected_object_changed"
                )
                assert protected_counts() == counts_before, (
                    "forbidden_object_count_changed"
                )
                connection.close()
                after_first_sha = sha256(DATABASE)

                replay = generate_manufacturing_output(
                    user=user,
                    payload=payload,
                    idempotency_key=IDEMPOTENCY_KEY,
                )
                assert replay["idempotentReplay"] is True
                assert replay["row"]["id"] == first["row"]["id"]
                physical_after_replay = physical_snapshot()
                assert physical_after_replay == physical_after_first, (
                    "idempotent_replay_wrote_database"
                )
                assert protected_snapshot() == protected_before
                assert protected_counts() == counts_before
                final = final_readback(first["row"]["id"])
                lifecycle_after = lifecycle_counts()
                connection.close()
                after_replay_sha = sha256(DATABASE)
                assert after_replay_sha == after_first_sha, (
                    "idempotent_replay_changed_database_sha"
                )

                output = {
                    "mode": "EXECUTED",
                    "database": {
                        "identity": DATABASE_IDENTITY,
                        "path": str(DATABASE),
                        "beforeSha256": before_sha,
                        "afterFirstExecutionSha256": after_first_sha,
                        "afterIdempotentReplaySha256": after_replay_sha,
                    },
                    "backup": {
                        "path": str(Path(args.backup).resolve()),
                        "sha256": before_sha,
                    },
                    "before": before,
                    "firstExecution": first,
                    "firstReadback": first_readback,
                    "finalReadback": final,
                    "physicalDelta": physical_delta,
                    "lifecycleCounts": {
                        "before": lifecycle_before,
                        "after": lifecycle_after,
                    },
                    "idempotency": {
                        "key": IDEMPOTENCY_KEY,
                        "replay": replay,
                        "replayBusinessWriteCount": 0,
                        "databaseShaUnchangedOnReplay": (
                            after_replay_sha == after_first_sha
                        ),
                        "physicalSnapshotUnchangedOnReplay": (
                            physical_after_replay == physical_after_first
                        ),
                    },
                    "preservation": {
                        "allPreExistingDatabaseRowsPreserved": physical_delta[
                            "allExistingRowsPreserved"
                        ],
                        "protectedObjectHashesBeforeAndAfterEqual": (
                            protected_snapshot() == protected_before
                        ),
                        "protectedCountsBeforeAndAfterEqual": (
                            protected_counts() == counts_before
                        ),
                        "protectedObjectHashes": {
                            key: value["sha256"]
                            for key, value in protected_before.items()
                        },
                        "protectedCounts": counts_before,
                    },
                }

    serialized = json.dumps(json_ready(output), ensure_ascii=False, indent=2)
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
