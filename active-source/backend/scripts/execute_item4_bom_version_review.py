"""Execute the authorized formal review of SO202609180003 Item4 BOMVersion4.

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
    REVIEW_ACTION,
    WORKFLOW_DOCUMENT_TYPES,
    control_chain_readiness,
    transition_bom_version,
)
from pde.bom_version_release_preflight import project_bom_version_release_preflight
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
REVIEWER_USERNAME = "pce_emp106"
IDEMPOTENCY_KEY = "so202609180003-item4-bomversion4-formal-review-20261012-v1"
REASON = (
    "《SO202609180003 Item4 BOMVersion4正式评审实施指令》：BOMVersion4 / CALC-4 "
    "Revision1工程与材料来源事实复核通过，仅执行draft到reviewed正式评审，不执行发布。"
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
    }


def target_facts() -> dict:
    workflows = list(
        WorkflowInstance.objects.filter(
            document_type__in=WORKFLOW_DOCUMENT_TYPES,
            document_id=BOM_VERSION_ID,
        ).order_by("pk")
    )
    workflow_ids = [row.pk for row in workflows]
    tasks = list(ApprovalTask.objects.filter(workflow_instance_id__in=workflow_ids).order_by("pk"))
    task_ids = [row.pk for row in tasks]
    decisions = list(ApprovalDecision.objects.filter(task_id__in=task_ids).order_by("pk"))
    transitions = list(
        BusinessStateTransition.objects.filter(
            object_type__in=WORKFLOW_DOCUMENT_TYPES,
            object_id=BOM_VERSION_ID,
        ).order_by("pk")
    )
    audits = list(
        OrganizationOperatingAuditRecord.objects.filter(
            target_type=DOCUMENT_TYPE,
            target_id=BOM_VERSION_ID,
            action_code=REVIEW_ACTION,
        ).order_by("pk")
    )
    requests = list(
        MasterDataWriteRequest.objects.filter(
            organization_id=1,
            action_code=REVIEW_ACTION,
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
        "workflowInstances": workflows,
        "approvalTasks": tasks,
        "approvalDecisions": decisions,
        "businessStateTransitions": transitions,
        "reviewAudits": audits,
        "writeRequests": requests,
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
    WorkflowInstance._meta.db_table: 1,
    ApprovalTask._meta.db_table: 1,
    ApprovalDecision._meta.db_table: 1,
    BusinessStateTransition._meta.db_table: 1,
    OrganizationOperatingAuditRecord._meta.db_table: 1,
    MasterDataWriteRequest._meta.db_table: 1,
    ExternalIdentity._meta.db_table: 1,
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


def serialize_facts(facts: dict) -> dict:
    return {
        "workflowInstances": [
            {
                "id": row.pk,
                "instanceNo": row.instance_no,
                "definitionId": row.process_definition_id,
                "documentType": row.document_type,
                "documentId": row.document_id,
                "status": row.status,
                "currentStep": row.current_step,
                "totalSteps": row.total_steps,
                "version": row.version,
                "completedAt": row.completed_at,
            }
            for row in facts["workflowInstances"]
        ],
        "approvalTasks": [
            {
                "id": row.pk,
                "taskNo": row.task_no,
                "workflowInstanceId": row.workflow_instance_id,
                "requiredRoleCode": row.required_role_code,
                "status": row.status,
                "version": row.version,
                "completedAt": row.completed_at,
            }
            for row in facts["approvalTasks"]
        ],
        "approvalDecisions": [
            {
                "id": row.pk,
                "taskId": row.task_id,
                "actorId": row.actor_id,
                "decision": row.decision,
                "comment": row.comment,
                "actionId": row.action_id,
                "idempotencyKey": row.idempotency_key,
                "completedAt": row.completed_at,
            }
            for row in facts["approvalDecisions"]
        ],
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
        "reviewAudits": [
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
            for row in facts["reviewAudits"]
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
                "sourceObjectType": row.source_object_type,
                "externalId": row.external_id,
                "mappingStatus": row.mapping_status,
                "targetEntityType": row.target_entity_type,
                "targetEntityId": row.target_entity_id,
            }
            for row in facts["externalIdentities"]
        ],
    }


def precheck() -> dict:
    version = BOMVersion.objects.select_related(
        "bom__company",
        "order_engineering_instance__sales_order_item__sales_order",
        "source_calculation",
    ).get(pk=BOM_VERSION_ID)
    item = version.order_engineering_instance.sales_order_item
    reviewer = User.objects.get(pk=REVIEWER_ID, username=REVIEWER_USERNAME)
    details = project_product_bom_material_detail(
        bom=version.bom,
        bom_version=version,
        order_item=item,
    )
    readiness = control_chain_readiness(version)
    preflight = project_bom_version_release_preflight(version, material_details=details)
    facts = target_facts()

    assert item.pk == ITEM_ID and item.sales_order.order_no == ORDER_NO
    assert version.pk == BOM_VERSION_ID and version.bom_id == PRODUCT_BOM_ID
    assert version.bom_version == "CALC-4" and version.revision == 1
    assert version.status == "draft" and version.approval_state == "not_submitted"
    assert version.order_engineering_instance_id == INSTANCE_ID
    assert version.source_calculation_id == CALCULATION_ID
    assert reviewer.is_active and not reviewer.is_superuser and reviewer.company_id == version.bom.company_id
    assert readiness["formalExecutionReady"] is True
    review_candidates = readiness["segregationOfDuties"]["reviewActors"]
    actor = next((row for row in review_candidates if row["userId"] == REVIEWER_ID), None)
    assert actor is not None, "configured_reviewer_not_eligible"
    assert "BOM_VERSION_FORMAL_REVIEW" in actor["responsibilityCodes"]
    assert actor["authorizationDecisionCode"] == "ALLOWED"
    assert preflight["decisionCode"] == "PASS_CONTROL_CHAIN_READY_FOR_FORMAL_REVIEW"
    assert preflight["firstBlockerCode"] == "FORMAL_REVIEW_NOT_EXECUTED"
    assert all(not rows for rows in facts.values()), "duplicate_formal_review_fact_exists"
    assert len(details) == 1 and details[0]["materialId"] == MATERIAL_ID
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
        "duplicateFacts": {key: len(rows) for key, rows in facts.items()},
        "reviewer": actor,
        "workflow": readiness["workflowRuntime"],
        "segregationOfDuties": readiness["segregationOfDuties"],
        "preflight": {
            "decisionCode": preflight["decisionCode"],
            "firstBlockerCode": preflight["firstBlockerCode"],
            "currentStateCode": preflight["stateMachine"]["currentStateCode"],
            "nextLegalStateCode": preflight["stateMachine"]["nextLegalStateCode"],
            "gatePassCount": preflight["gatePassCount"],
            "gateFailCount": preflight["gateFailCount"],
            "gateNotRequiredCount": preflight["gateNotRequiredCount"],
        },
        "materialDetails": details,
    }


def final_readback() -> dict:
    version = BOMVersion.objects.select_related(
        "bom", "order_engineering_instance", "source_calculation",
    ).get(pk=BOM_VERSION_ID)
    facts = target_facts()
    serialized = serialize_facts(facts)
    details = project_product_bom_material_detail(
        bom=version.bom,
        bom_version=version,
        order_item=version.order_engineering_instance.sales_order_item,
    )
    readiness = control_chain_readiness(version)
    preflight = project_bom_version_release_preflight(version, material_details=details)

    assert version.status == "reviewed" and version.approval_state == APPROVED_PROJECTION
    assert all(len(facts[key]) == 1 for key in facts)
    decision = facts["approvalDecisions"][0]
    transition = facts["businessStateTransitions"][0]
    audit = facts["reviewAudits"][0]
    request = facts["writeRequests"][0]
    assert decision.actor_id == REVIEWER_ID and decision.decision == "approved"
    assert decision.action_id == REVIEW_ACTION and decision.comment == REASON
    assert transition.source_state == "draft" and transition.target_state == "reviewed"
    assert transition.action_code == REVIEW_ACTION and transition.operator_id == REVIEWER_ID
    assert transition.audit_reference == f"OrganizationOperatingAuditRecord:{audit.pk}"
    assert request.status == MasterDataWriteRequest.Status.COMMITTED
    assert preflight["decisionCode"] == "PASS_FORMAL_REVIEW_COMPLETE_READY_FOR_EXPLICIT_RELEASE"
    assert preflight["firstBlockerCode"] == "EXPLICIT_RELEASE_AUTHORIZATION_REQUIRED"
    assert preflight["stateMachine"]["currentStateCode"] == "reviewed"
    assert preflight["stateMachine"]["nextLegalStateCode"] == "released"
    assert BusinessStateTransition.objects.filter(
        object_type__in=WORKFLOW_DOCUMENT_TYPES,
        object_id=BOM_VERSION_ID,
        target_state="released",
    ).count() == 0
    assert OrganizationOperatingAuditRecord.objects.filter(
        target_type=DOCUMENT_TYPE,
        target_id=BOM_VERSION_ID,
        action_code="pde.bom_version.release",
    ).count() == 0
    return {
        "bomVersion": {
            "id": version.pk,
            "bomVersion": version.bom_version,
            "revision": version.revision,
            "status": version.status,
            "approvalState": version.approval_state,
            "updatedAt": version.updated_at,
        },
        "formalFacts": serialized,
        "readback": {
            "decisionCode": preflight["decisionCode"],
            "firstBlockerCode": preflight["firstBlockerCode"],
            "firstBlockerLabel": preflight["firstBlockerLabel"],
            "currentStateCode": preflight["stateMachine"]["currentStateCode"],
            "nextLegalStateCode": preflight["stateMachine"]["nextLegalStateCode"],
            "releaseAllowed": preflight["releaseAllowed"],
            "currentBusinessAction": readiness["currentBusinessAction"],
            "projectionConsistent": preflight["approval"]["projectionConsistent"],
            "gatePassCount": preflight["gatePassCount"],
            "gateFailCount": preflight["gateFailCount"],
            "gateNotRequiredCount": preflight["gateNotRequiredCount"],
        },
        "releaseProtection": {
            "releaseTransitionCount": 0,
            "releaseAuditCount": 0,
        },
    }


def validate_runtime():
    assert Path(connection.settings_dict["NAME"]).resolve() == DATABASE.resolve(), "wrong_database"
    assert os.environ.get("PCE_RUNTIME_PROFILE") == "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    assert os.environ.get("PCE_DATABASE_IDENTITY") == "PDE-OPERABLE-ACCEPTANCE-20260912"
    assert os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") == "1"
    connection.ensure_connection()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized-review", action="store_true")
    parser.add_argument("--final-readback", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--backup")
    args = parser.parse_args()

    validate_runtime()
    before_sha = sha256(DATABASE)
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
                "sha256": before_sha,
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
    if args.execute_authorized_review:
        assert args.expected_sha256 and args.backup, "write_requires_expected_sha_and_backup"
        assert before_sha == args.expected_sha256.upper(), "database_sha_changed_before_write"
        backup = Path(args.backup).resolve()
        assert backup.is_file() and backup.parent.is_relative_to(DATABASE.parent), "invalid_backup"
        assert sha256(backup) == before_sha, "backup_sha_mismatch"

    reviewer = User.objects.get(pk=REVIEWER_ID, username=REVIEWER_USERNAME)
    physical_before = physical_snapshot()
    frozen_before = frozen_snapshot()
    forbidden_before = forbidden_counts()
    before = precheck()

    if not args.execute_authorized_review:
        print(json.dumps({
            "mode": "READ_ONLY",
            "database": str(DATABASE),
            "databaseSha256": before_sha,
            "before": before,
            "protectedObjectHashes": {
                key: value["sha256"] for key, value in frozen_before.items()
            },
            "forbiddenCounts": forbidden_before,
        }, ensure_ascii=False, indent=2, default=str))
        return

    first = transition_bom_version(
        object_id=BOM_VERSION_ID,
        target_status="reviewed",
        action=REVIEW_ACTION,
        user=reviewer,
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
        target_status="reviewed",
        action=REVIEW_ACTION,
        user=reviewer,
        reason=REASON,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    assert replay["idempotentReplay"] is True
    assert replay["auditId"] == first["auditId"]
    assert replay["businessStateTransition"]["id"] == first["businessStateTransition"]["id"]
    assert replay["workflow"]["decisionId"] == first["workflow"]["decisionId"]
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
            "beforeSha256": before_sha,
            "afterFirstExecutionSha256": after_first_sha,
            "afterIdempotentReplaySha256": after_replay_sha,
        },
        "backup": {"path": str(Path(args.backup).resolve()), "sha256": before_sha},
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
