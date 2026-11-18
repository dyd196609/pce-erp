"""Execute the authorized formal release of SO202609180003 Item4 BOMVersion4.

The default mode is read-only. A write requires the explicit execution flag,
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

from django.db import connection
from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
from planning.models import Demand, PlanningRequirement
from sales.models import SalesOrderItem
from system.models import OrganizationOperatingAuditRecord, User
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    WorkflowInstance,
)

from pde.bom_version_control_service import (
    APPROVED_PROJECTION,
    DOCUMENT_TYPE,
    RELEASE_ACTION,
    WORKFLOW_DOCUMENT_TYPES,
    control_chain_readiness,
    release_readback,
    transition_bom_version,
)
from pde.bom_version_release_preflight import project_bom_version_release_preflight
from pde.manufacturing_output_generation_service import ManufacturingOutputError, resolve_sources
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
)
from pde.product_bom_detail_projection import project_product_bom_material_detail


DATABASE = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
ORDER_NO = "SO202609180003"
ITEM_ID = 4
INSTANCE_ID = 3
BASELINE_ID = 2
CALCULATION_ID = 4
PRODUCT_BOM_ID = 4
BOM_VERSION_ID = 4
BOM_ITEM_ID = 8
MATERIAL_ID = 130
EXTERNAL_IDENTITY_ID = 51
REQUIREMENT_IDS = (28, 29, 30)
REVIEWER_ID = 24
RELEASER_ID = 21
RELEASER_USERNAME = "pce_emp104"
REVIEW_WORKFLOW_ID = 10
REVIEW_TASK_ID = 10
REVIEW_DECISION_ID = 10
REVIEW_AUDIT_ID = 2968
REVIEW_TRANSITION_ID = 61
CONTROL_IDENTITY_ID = 2152
IDEMPOTENCY_KEY = "so202609180003-item4-bomversion4-formal-release-20261012-v1"
REASON = (
    "《SO202609180003 Item4 BOMVersion4正式发布实施指令》：由正式发布责任人吴刚升"
    "（User21 / pce_emp104）对已完成正式评审的BOMVersion4 / CALC-4 Revision1"
    "执行reviewed到released正式发布；不创建或修改任何下游业务对象。"
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
        "productBom4": model_snapshot(ProductBOM, PRODUCT_BOM_ID),
        "bomItem8": model_snapshot(BOMItem, BOM_ITEM_ID),
        "oei3": model_snapshot(OrderEngineeringInstance, INSTANCE_ID),
        "baseline2": model_snapshot(OrderEngineeringBaseline, BASELINE_ID),
        "calculation4": model_snapshot(EngineeringCalculationRecord, CALCULATION_ID),
        "material130": model_snapshot(Material, MATERIAL_ID),
        "externalIdentity51": model_snapshot(ExternalIdentity, EXTERNAL_IDENTITY_ID),
        "reviewWorkflow10": model_snapshot(WorkflowInstance, REVIEW_WORKFLOW_ID),
        "reviewTask10": model_snapshot(ApprovalTask, REVIEW_TASK_ID),
        "reviewDecision10": model_snapshot(ApprovalDecision, REVIEW_DECISION_ID),
        "reviewAudit2968": model_snapshot(OrganizationOperatingAuditRecord, REVIEW_AUDIT_ID),
        "reviewTransition61": model_snapshot(BusinessStateTransition, REVIEW_TRANSITION_ID),
        **{
            f"engineeringMaterialRequirement{pk}": model_snapshot(EngineeringMaterialRequirement, pk)
            for pk in REQUIREMENT_IDS
        },
    }


def forbidden_counts() -> dict:
    return {
        "engineeringDocument": EngineeringDocument.objects.count(),
        "engineeringDocumentVersion": EngineeringDocumentVersion.objects.count(),
        "demand": Demand.objects.count(),
        "planningRequirement": PlanningRequirement.objects.count(),
        "manufacturingOutput": ProductManufacturingOutput.objects.count(),
        "workflowInstance": WorkflowInstance.objects.count(),
        "approvalTask": ApprovalTask.objects.count(),
        "approvalDecision": ApprovalDecision.objects.count(),
    }


def release_facts() -> dict:
    transitions = list(
        BusinessStateTransition.objects.filter(
            object_type__in=WORKFLOW_DOCUMENT_TYPES,
            object_id=BOM_VERSION_ID,
            action_code=RELEASE_ACTION,
            target_state="released",
        ).order_by("pk")
    )
    audits = list(
        OrganizationOperatingAuditRecord.objects.filter(
            target_type=DOCUMENT_TYPE,
            target_id=BOM_VERSION_ID,
            action_code=RELEASE_ACTION,
        ).order_by("pk")
    )
    requests = list(
        MasterDataWriteRequest.objects.filter(
            organization_id=1,
            action_code=RELEASE_ACTION,
            entity_type=DOCUMENT_TYPE,
            target_entity_id=str(BOM_VERSION_ID),
        ).order_by("pk")
    )
    key_requests = list(
        MasterDataWriteRequest.objects.filter(
            organization_id=1,
            action_code=RELEASE_ACTION,
            idempotency_key=IDEMPOTENCY_KEY,
        ).order_by("pk")
    )
    identities = list(
        ExternalIdentity.objects.filter(
            organization_id=1,
            source_system="PCE_BOM_VERSION_CONTROL",
            source_object_type=DOCUMENT_TYPE,
            external_id=f"BOMVersion:{BOM_VERSION_ID}",
        ).order_by("pk")
    )
    return {
        "businessStateTransitions": transitions,
        "releaseAudits": audits,
        "writeRequests": requests,
        "keyRequests": key_requests,
        "externalIdentities": identities,
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


APPEND_DELTAS = {
    BusinessStateTransition._meta.db_table: 1,
    OrganizationOperatingAuditRecord._meta.db_table: 1,
    MasterDataWriteRequest._meta.db_table: 1,
}
UPDATED_TABLE = BOMVersion._meta.db_table


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
                    assert name in APPEND_DELTAS, f"protected_sequence_changed:{name}"
                    assert delta == APPEND_DELTAS[name], f"unexpected_sequence_delta:{name}:{delta}"
                    sequence_changes[name] = delta
            continue
        if table == UPDATED_TABLE:
            removed = rows - current
            added = current - rows
            assert sum(removed.values()) == 1 and sum(added.values()) == 1, "bom_version_update_not_exactly_one_row"
            removed_row = json.loads(next(iter(removed)))
            added_row = json.loads(next(iter(added)))
            assert removed_row[0] == BOM_VERSION_ID and added_row[0] == BOM_VERSION_ID, "wrong_bom_version_updated"
            changes[table] = {
                "before": sum(rows.values()),
                "after": sum(current.values()),
                "updatedRows": 1,
                "updatedPrimaryKey": BOM_VERSION_ID,
            }
            continue
        assert table in APPEND_DELTAS, f"protected_table_changed:{table}"
        assert not (rows - current), f"existing_row_changed_or_removed:{table}"
        delta = sum(current.values()) - sum(rows.values())
        assert delta == APPEND_DELTAS[table], f"unexpected_append_count:{table}:{delta}"
        changes[table] = {
            "before": sum(rows.values()),
            "after": sum(current.values()),
            "added": delta,
        }
    assert set(changes) == set(APPEND_DELTAS) | {UPDATED_TABLE}, "unexpected_write_set"
    return {
        "schemaSha256": old_schema,
        "physicalTableCount": len(old_rows),
        "allNonTargetExistingRowsPreserved": True,
        "changes": changes,
        "sequenceChanges": sequence_changes,
    }


def review_chain_readback() -> dict:
    workflow = WorkflowInstance.objects.get(pk=REVIEW_WORKFLOW_ID)
    task = ApprovalTask.objects.get(pk=REVIEW_TASK_ID)
    decision = ApprovalDecision.objects.get(pk=REVIEW_DECISION_ID)
    audit = OrganizationOperatingAuditRecord.objects.get(pk=REVIEW_AUDIT_ID)
    transition = BusinessStateTransition.objects.get(pk=REVIEW_TRANSITION_ID)
    assert workflow.document_type in WORKFLOW_DOCUMENT_TYPES and workflow.document_id == BOM_VERSION_ID
    assert workflow.status == "approved" and task.workflow_instance_id == workflow.pk
    assert task.status == "approved" and decision.task_id == task.pk
    assert decision.actor_id == REVIEWER_ID and decision.decision == "approved"
    assert decision.action_id == "pde.bom_version.review"
    assert audit.action_code == "pde.bom_version.review" and audit.target_id == BOM_VERSION_ID
    assert transition.source_state == "draft" and transition.target_state == "reviewed"
    assert transition.action_code == "pde.bom_version.review"
    assert transition.audit_reference == f"OrganizationOperatingAuditRecord:{audit.pk}"
    return {
        "workflow": {"id": workflow.pk, "instanceNo": workflow.instance_no, "status": workflow.status},
        "task": {"id": task.pk, "taskNo": task.task_no, "status": task.status},
        "decision": {
            "id": decision.pk,
            "actorId": decision.actor_id,
            "decision": decision.decision,
            "actionId": decision.action_id,
            "completedAt": decision.completed_at,
        },
        "audit": {"id": audit.pk, "actionCode": audit.action_code, "actorId": audit.actor_id},
        "transition": {
            "id": transition.pk,
            "sourceState": transition.source_state,
            "targetState": transition.target_state,
            "actionCode": transition.action_code,
            "operatorId": transition.operator_id,
        },
    }


def serialize_release_facts(facts: dict) -> dict:
    return {
        "businessStateTransitions": [
            {
                "id": row.pk,
                "objectType": row.object_type,
                "objectId": row.object_id,
                "sourceState": row.source_state,
                "targetState": row.target_state,
                "actionCode": row.action_code,
                "workflowInstanceId": row.workflow_instance_id,
                "operatorId": row.operator_id,
                "reason": row.reason,
                "auditReference": row.audit_reference,
                "timestamp": row.timestamp,
            }
            for row in facts["businessStateTransitions"]
        ],
        "releaseAudits": [
            {
                "id": row.pk,
                "actionCode": row.action_code,
                "actorId": row.actor_id,
                "organizationId": row.organization_id,
                "targetType": row.target_type,
                "targetId": row.target_id,
                "reason": row.reason,
                "createdAt": row.created_at,
            }
            for row in facts["releaseAudits"]
        ],
        "writeRequests": [
            {
                "id": row.pk,
                "actionCode": row.action_code,
                "idempotencyKey": row.idempotency_key,
                "status": row.status,
                "targetEntityId": row.target_entity_id,
            }
            for row in facts["writeRequests"]
        ],
        "externalIdentities": [
            {
                "id": row.pk,
                "sourceSystem": row.source_system,
                "externalId": row.external_id,
                "mappingStatus": row.mapping_status,
                "targetEntityType": row.target_entity_type,
                "targetEntityId": row.target_entity_id,
            }
            for row in facts["externalIdentities"]
        ],
    }


def next_downstream_blocker(item) -> dict:
    try:
        resolve_sources(item)
    except ManufacturingOutputError as exc:
        return {"code": exc.code, "message": exc.message, "details": exc.details}
    return {"code": "MANUFACTURING_OUTPUT_SOURCE_READY", "message": "制造输出来源已满足。", "details": {}}


def precheck() -> dict:
    version = BOMVersion.objects.select_related(
        "bom__company",
        "order_engineering_instance__sales_order_item__sales_order",
        "source_calculation",
    ).get(pk=BOM_VERSION_ID)
    item = version.order_engineering_instance.sales_order_item
    releaser = User.objects.get(pk=RELEASER_ID, username=RELEASER_USERNAME)
    details = project_product_bom_material_detail(
        bom=version.bom,
        bom_version=version,
        order_item=item,
    )
    readiness = control_chain_readiness(version)
    preflight = project_bom_version_release_preflight(version, material_details=details)
    review_chain = review_chain_readback()
    facts = release_facts()
    authoritative_release = release_readback(version)

    assert item.pk == ITEM_ID and item.sales_order.order_no == ORDER_NO
    assert version.pk == BOM_VERSION_ID and version.bom_id == PRODUCT_BOM_ID
    assert version.bom_version == "CALC-4" and version.revision == 1
    assert version.status == "reviewed" and version.approval_state == APPROVED_PROJECTION
    assert version.order_engineering_instance_id == INSTANCE_ID
    assert version.source_calculation_id == CALCULATION_ID
    assert releaser.is_active and not releaser.is_superuser and releaser.company_id == version.bom.company_id
    assert readiness["formalExecutionReady"] is True
    release_candidates = readiness["segregationOfDuties"]["releaseActors"]
    actor = next((row for row in release_candidates if row["userId"] == RELEASER_ID), None)
    assert actor is not None, "configured_releaser_not_eligible"
    assert "BOM_VERSION_FORMAL_RELEASE" in actor["responsibilityCodes"]
    assert actor["authorizationDecisionCode"] == "ALLOWED"
    assert actor["userId"] != review_chain["decision"]["actorId"]
    assert preflight["decisionCode"] == "PASS_FORMAL_REVIEW_COMPLETE_READY_FOR_EXPLICIT_RELEASE"
    assert preflight["firstBlockerCode"] == "EXPLICIT_RELEASE_AUTHORIZATION_REQUIRED"
    assert not facts["businessStateTransitions"]
    assert not facts["releaseAudits"] and not facts["writeRequests"] and not facts["keyRequests"]
    assert len(facts["externalIdentities"]) == 1
    assert facts["externalIdentities"][0].pk == CONTROL_IDENTITY_ID
    assert authoritative_release["released"] is False
    assert len(details) == 1 and details[0]["bomItemId"] == BOM_ITEM_ID
    return {
        "bomVersion": {
            "id": version.pk,
            "bomVersion": version.bom_version,
            "revision": version.revision,
            "status": version.status,
            "approvalState": version.approval_state,
            "productBomId": version.bom_id,
            "orderEngineeringInstanceId": version.order_engineering_instance_id,
            "sourceCalculationId": version.source_calculation_id,
        },
        "reviewChain": review_chain,
        "duplicateReleaseFacts": {
            "businessStateTransitions": len(facts["businessStateTransitions"]),
            "releaseAudits": len(facts["releaseAudits"]),
            "writeRequests": len(facts["writeRequests"]),
            "keyRequests": len(facts["keyRequests"]),
        },
        "releaser": actor,
        "segregationOfDuties": readiness["segregationOfDuties"],
        "preflight": {
            "decisionCode": preflight["decisionCode"],
            "firstBlockerCode": preflight["firstBlockerCode"],
            "currentStateCode": preflight["stateMachine"]["currentStateCode"],
            "nextLegalStateCode": preflight["stateMachine"]["nextLegalStateCode"],
            "releaseAllowed": preflight["releaseAllowed"],
            "gatePassCount": preflight["gatePassCount"],
            "gateFailCount": preflight["gateFailCount"],
            "gateNotRequiredCount": preflight["gateNotRequiredCount"],
        },
        "authoritativeReleaseReadback": authoritative_release,
    }


def final_readback() -> dict:
    version = BOMVersion.objects.select_related(
        "bom", "order_engineering_instance__sales_order_item", "source_calculation",
    ).get(pk=BOM_VERSION_ID)
    item = version.order_engineering_instance.sales_order_item
    facts = release_facts()
    details = project_product_bom_material_detail(
        bom=version.bom,
        bom_version=version,
        order_item=item,
    )
    readiness = control_chain_readiness(version)
    preflight = project_bom_version_release_preflight(version, material_details=details)
    authoritative_release = release_readback(version)
    review_chain = review_chain_readback()

    assert version.status == "released" and version.approval_state == APPROVED_PROJECTION
    assert len(facts["businessStateTransitions"]) == 1
    assert len(facts["releaseAudits"]) == 1
    assert len(facts["writeRequests"]) == 1 and len(facts["keyRequests"]) == 1
    assert len(facts["externalIdentities"]) == 1
    transition = facts["businessStateTransitions"][0]
    audit = facts["releaseAudits"][0]
    request = facts["writeRequests"][0]
    assert transition.source_state == "reviewed" and transition.target_state == "released"
    assert transition.action_code == RELEASE_ACTION and transition.operator_id == RELEASER_ID
    assert transition.workflow_instance_id == REVIEW_WORKFLOW_ID
    assert transition.audit_reference == f"OrganizationOperatingAuditRecord:{audit.pk}"
    assert audit.actor_id == RELEASER_ID and audit.reason == REASON
    assert request.status == MasterDataWriteRequest.Status.COMMITTED
    assert request.idempotency_key == IDEMPOTENCY_KEY
    assert authoritative_release["released"] is True
    assert authoritative_release["actorId"] == RELEASER_ID
    assert authoritative_release["actorUsername"] == RELEASER_USERNAME
    assert authoritative_release["requestIdentity"] == IDEMPOTENCY_KEY
    assert preflight["decisionCode"] == "PASS_FORMAL_RELEASE_COMPLETE"
    assert preflight["firstBlockerCode"] == "FORMAL_RELEASE_ALREADY_COMPLETED"
    assert preflight["stateMachine"]["currentStateCode"] == "released"
    return {
        "bomVersion": {
            "id": version.pk,
            "bomVersion": version.bom_version,
            "revision": version.revision,
            "status": version.status,
            "approvalState": version.approval_state,
            "updatedAt": version.updated_at,
        },
        "reviewChain": review_chain,
        "releaseFacts": serialize_release_facts(facts),
        "authoritativeReleaseReadback": authoritative_release,
        "readback": {
            "decisionCode": preflight["decisionCode"],
            "firstBlockerCode": preflight["firstBlockerCode"],
            "currentStateCode": preflight["stateMachine"]["currentStateCode"],
            "nextLegalStateCode": preflight["stateMachine"]["nextLegalStateCode"],
            "releaseAllowed": preflight["releaseAllowed"],
            "currentBusinessAction": readiness["currentBusinessAction"],
            "projectionConsistent": preflight["approval"]["projectionConsistent"],
            "gatePassCount": preflight["gatePassCount"],
            "gateFailCount": preflight["gateFailCount"],
            "gateNotRequiredCount": preflight["gateNotRequiredCount"],
        },
        "nextDownstreamBlocker": next_downstream_blocker(item),
    }


def validate_runtime():
    assert Path(connection.settings_dict["NAME"]).resolve() == DATABASE.resolve(), "wrong_database"
    assert os.environ.get("PCE_RUNTIME_PROFILE") == "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    assert os.environ.get("PCE_DATABASE_IDENTITY") == "PDE-OPERABLE-ACCEPTANCE-20260912"
    assert os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") == "1"
    connection.ensure_connection()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized-release", action="store_true")
    parser.add_argument("--final-readback", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--backup")
    args = parser.parse_args()

    validate_runtime()
    database_sha = sha256(DATABASE)
    if args.final_readback:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]
            cursor.execute("PRAGMA foreign_key_check")
            foreign_key_violations = cursor.fetchall()
        print(json.dumps({
            "mode": "FINAL_READBACK",
            "database": {
                "identity": "PDE-OPERABLE-ACCEPTANCE-20260912",
                "path": str(DATABASE),
                "sha256": database_sha,
                "lengthBytes": DATABASE.stat().st_size,
                "integrityCheck": integrity,
                "foreignKeyCheck": foreign_key_violations,
            },
            "after": final_readback(),
            "protectedObjectHashes": {
                key: value["sha256"] for key, value in frozen_snapshot().items()
            },
            "forbiddenCounts": forbidden_counts(),
        }, ensure_ascii=False, indent=2, default=str))
        return

    if args.execute_authorized_release:
        assert args.expected_sha256 and args.backup, "write_requires_expected_sha_and_backup"
        assert database_sha == args.expected_sha256.upper(), "database_sha_changed_before_write"
        backup = Path(args.backup).resolve()
        assert backup.is_file() and backup.parent.is_relative_to(DATABASE.parent), "invalid_backup"
        assert sha256(backup) == database_sha, "backup_sha_mismatch"

    releaser = User.objects.get(pk=RELEASER_ID, username=RELEASER_USERNAME)
    physical_before = physical_snapshot()
    frozen_before = frozen_snapshot()
    forbidden_before = forbidden_counts()
    before = precheck()

    if not args.execute_authorized_release:
        print(json.dumps({
            "mode": "READ_ONLY",
            "database": str(DATABASE),
            "databaseSha256": database_sha,
            "before": before,
            "protectedObjectHashes": {
                key: value["sha256"] for key, value in frozen_before.items()
            },
            "forbiddenCounts": forbidden_before,
        }, ensure_ascii=False, indent=2, default=str))
        return

    first = transition_bom_version(
        object_id=BOM_VERSION_ID,
        target_status="released",
        action=RELEASE_ACTION,
        user=releaser,
        reason=REASON,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    assert first["idempotentReplay"] is False
    readback = final_readback()
    assert frozen_snapshot() == frozen_before, "protected_object_changed"
    assert forbidden_counts() == forbidden_before, "forbidden_object_created"
    physical_after_first = physical_snapshot()
    physical_delta = compare_physical(physical_before, physical_after_first)
    connection.close()
    after_first_sha = sha256(DATABASE)

    replay = transition_bom_version(
        object_id=BOM_VERSION_ID,
        target_status="released",
        action=RELEASE_ACTION,
        user=releaser,
        reason=REASON,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    assert replay["idempotentReplay"] is True
    assert replay["auditId"] == first["auditId"]
    assert replay["businessStateTransition"]["id"] == first["businessStateTransition"]["id"]
    physical_after_replay = physical_snapshot()
    assert physical_after_replay == physical_after_first, "idempotent_replay_wrote_database"
    assert frozen_snapshot() == frozen_before, "protected_object_changed_after_replay"
    assert forbidden_counts() == forbidden_before, "forbidden_object_created_after_replay"
    replay_readback = final_readback()
    assert replay_readback == readback, "idempotent_replay_changed_readback"
    connection.close()
    after_replay_sha = sha256(DATABASE)
    assert after_replay_sha == after_first_sha, "idempotent_replay_changed_database_sha"

    print(json.dumps({
        "mode": "EXECUTED",
        "database": {
            "identity": "PDE-OPERABLE-ACCEPTANCE-20260912",
            "path": str(DATABASE),
            "beforeSha256": database_sha,
            "afterFirstExecutionSha256": after_first_sha,
            "afterIdempotentReplaySha256": after_replay_sha,
        },
        "backup": {"path": str(Path(args.backup).resolve()), "sha256": database_sha},
        "before": before,
        "firstExecution": first,
        "after": readback,
        "physicalDelta": physical_delta,
        "idempotency": {
            "key": IDEMPOTENCY_KEY,
            "firstExecutionReplay": first["idempotentReplay"],
            "secondExecutionReplay": replay["idempotentReplay"],
            "replayBusinessWriteCount": 0,
            "databaseShaUnchangedOnReplay": after_replay_sha == after_first_sha,
            "physicalSnapshotUnchangedOnReplay": physical_after_replay == physical_after_first,
        },
        "preservation": {
            "protectedObjectHashesBeforeAndAfterEqual": frozen_snapshot() == frozen_before,
            "protectedObjectHashes": {
                key: value["sha256"] for key, value in frozen_before.items()
            },
            "forbiddenCountsBeforeAndAfterEqual": forbidden_counts() == forbidden_before,
            "forbiddenCounts": forbidden_before,
        },
    }, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
