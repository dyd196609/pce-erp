"""Register, review, and release the authorized Item4 engineering document.

The default mode is read-only.  Formal execution requires the exact current
database SHA-256 and a byte-identical recoverable backup.  The orchestration is
idempotent across the complete lifecycle: a later replay of the same exact
released source chain performs readback only and writes nothing.
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
from sales.models import SalesOrder, SalesOrderItem
from sales.services import engineering_readiness_facts
from system.models import OrganizationOperatingAuditRecord, User
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    WorkflowInstance,
)

from pde.engineering_document_version_release_service import (
    RELEASE_ACTION,
    eligible_release_actors,
    project_release_content_integrity,
    project_release_preflight,
    project_release_source_completeness,
    release_engineering_document_version,
    release_readback,
)
from pde.engineering_document_version_review_service import (
    REVIEW_ACTION,
    eligible_review_actors,
    project_review_preflight,
    review_engineering_document_version,
    review_readback,
    resolve_workflow_template,
)
from pde.manufacturing_output_generation_service import (
    ManufacturingOutputError,
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
)
from pde.order_engineering_document_registration_service import (
    OrderEngineeringDocumentRegistrationService,
)


DATABASE = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
DATABASE_IDENTITY = "PDE-OPERABLE-ACCEPTANCE-20260912"
ORDER_NO = "SO202609180003"
ORDER_ID = 3
ITEM_ID = 4
LINE_NO = 2
INSTANCE_ID = 3
BASELINE_ID = 2
CALCULATION_ID = 4
PRODUCT_BOM_ID = 4
BOM_VERSION_ID = 4
BOM_ITEM_ID = 8
MATERIAL_ID = 130
EXTERNAL_IDENTITY_ID = 51
REQUIREMENT_IDS = (28, 29, 30)

MAINTAINER_ID = 10
MAINTAINER_USERNAME = "pce_plan_r12"
REVIEWER_ID = 24
REVIEWER_USERNAME = "pce_emp106"
PUBLISHER_ID = 21
PUBLISHER_USERNAME = "pce_emp104"

DOCUMENT_NO = "ED-SO202609180003-L02-001"
DOCUMENT_NAME = "清水封闭房门工艺技术资料"
DOCUMENT_TYPE = "technical"
REGISTRATION_KEY = "so202609180003-item4-engineering-document-registration-20261012-v1"
REVIEW_KEY = "so202609180003-item4-engineering-document-review-20261012-v1"
RELEASE_KEY = "so202609180003-item4-engineering-document-release-20261012-v1"
REGISTRATION_REASON = (
    "《SO202609180003 Item4工程资料版本登记、评审与发布实施指令》：由正式工程资料"
    "维护责任人登记Item4/OEI3/Calculation4/BOMVersion4准确来源链的工程资料主表及V1.0草稿；"
    "不重算或修改任何既有工程事实。"
)
REVIEW_REASON = (
    "《SO202609180003 Item4工程资料版本登记、评审与发布实施指令》：由工程资料正式评审"
    "责任人王天一（User24 / pce_emp106）确认V1.0准确来源链及内容，执行draft到reviewed。"
)
RELEASE_REASON = (
    "《SO202609180003 Item4工程资料版本登记、评审与发布实施指令》：由独立工程资料正式"
    "发布责任人吴刚升（User21 / pce_emp104）对已评审V1.0执行reviewed到released；"
    "不创建Demand、PlanningRequirement或ManufacturingOutput。"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
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
        "productBom4": model_snapshot(ProductBOM, PRODUCT_BOM_ID),
        "bomVersion3": model_snapshot(BOMVersion, 3),
        "bomVersion4": model_snapshot(BOMVersion, BOM_VERSION_ID),
        "bomItem8": model_snapshot(BOMItem, BOM_ITEM_ID),
        "oei3": model_snapshot(OrderEngineeringInstance, INSTANCE_ID),
        "baseline2": model_snapshot(OrderEngineeringBaseline, BASELINE_ID),
        "calculation4": model_snapshot(EngineeringCalculationRecord, CALCULATION_ID),
        "material130": model_snapshot(Material, MATERIAL_ID),
        "externalIdentity51": model_snapshot(ExternalIdentity, EXTERNAL_IDENTITY_ID),
        "existingEngineeringDocument1": model_snapshot(EngineeringDocument, 1),
        "existingEngineeringDocumentVersion1": model_snapshot(EngineeringDocumentVersion, 1),
        "bomReviewWorkflow10": model_snapshot(WorkflowInstance, 10),
        "bomReviewTask10": model_snapshot(ApprovalTask, 10),
        "bomReviewDecision10": model_snapshot(ApprovalDecision, 10),
        "bomReviewAudit2968": model_snapshot(OrganizationOperatingAuditRecord, 2968),
        "bomReleaseAudit2969": model_snapshot(OrganizationOperatingAuditRecord, 2969),
        "bomReviewTransition61": model_snapshot(BusinessStateTransition, 61),
        "bomReleaseTransition62": model_snapshot(BusinessStateTransition, 62),
    }
    values.update({
        f"engineeringMaterialRequirement{pk}": model_snapshot(
            EngineeringMaterialRequirement, pk,
        )
        for pk in REQUIREMENT_IDS
    })
    return values


def protected_counts() -> dict:
    return {
        "productBom": ProductBOM.objects.count(),
        "bomVersion": BOMVersion.objects.count(),
        "bomItem": BOMItem.objects.count(),
        "engineeringCalculation": EngineeringCalculationRecord.objects.count(),
        "engineeringMaterialRequirement": EngineeringMaterialRequirement.objects.count(),
        "demand": Demand.objects.count(),
        "planningRequirement": PlanningRequirement.objects.count(),
        "manufacturingOutput": ProductManufacturingOutput.objects.count(),
    }


def lifecycle_counts() -> dict:
    return {
        "engineeringDocument": EngineeringDocument.objects.count(),
        "engineeringDocumentVersion": EngineeringDocumentVersion.objects.count(),
        "workflowInstance": WorkflowInstance.objects.count(),
        "approvalTask": ApprovalTask.objects.count(),
        "approvalDecision": ApprovalDecision.objects.count(),
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
                json.dumps(row, ensure_ascii=False, default=str) for row in cursor.fetchall()
            )
        cursor.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        schema_hash = hashlib.sha256(
            canonical(cursor.fetchall()).encode("utf-8")
        ).hexdigest().upper()
    return rows, schema_hash


EXPECTED_DELTAS = {
    EngineeringDocument._meta.db_table: 1,
    EngineeringDocumentVersion._meta.db_table: 1,
    ExternalIdentity._meta.db_table: 4,
    MasterDataWriteRequest._meta.db_table: 4,
    WorkflowInstance._meta.db_table: 1,
    ApprovalTask._meta.db_table: 1,
    ApprovalDecision._meta.db_table: 1,
    OrganizationOperatingAuditRecord._meta.db_table: 4,
    BusinessStateTransition._meta.db_table: 2,
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


def users() -> tuple[User, User, User]:
    maintainer = User.objects.get(
        pk=MAINTAINER_ID, username=MAINTAINER_USERNAME,
        is_active=True, is_superuser=False,
    )
    reviewer = User.objects.get(
        pk=REVIEWER_ID, username=REVIEWER_USERNAME,
        is_active=True, is_superuser=False,
    )
    publisher = User.objects.get(
        pk=PUBLISHER_ID, username=PUBLISHER_USERNAME,
        is_active=True, is_superuser=False,
    )
    assert {maintainer.company_id, reviewer.company_id, publisher.company_id} == {1}
    assert len({maintainer.pk, reviewer.pk, publisher.pk}) == 3
    return maintainer, reviewer, publisher


def exact_target_version(*, allow_missing: bool = False):
    documents = list(
        EngineeringDocument.objects.filter(document_no=DOCUMENT_NO)
        .prefetch_related("document_versions")[:2]
    )
    if not documents:
        if allow_missing:
            return None
        raise AssertionError("target_engineering_document_missing")
    assert len(documents) == 1, "target_engineering_document_not_unique"
    document = documents[0]
    versions = list(document.document_versions.order_by("pk")[:2])
    if not versions:
        if allow_missing:
            return None
        raise AssertionError("target_engineering_document_version_missing")
    assert len(versions) == 1, "target_engineering_document_version_not_unique"
    version = EngineeringDocumentVersion.objects.select_related(
        "document", "order_engineering_instance__sales_order_item__sales_order",
        "order_engineering_baseline", "engineering_calculation",
        "related_bom__bom", "related_routing__routing",
    ).get(pk=versions[0].pk)
    expected = {
        "documentName": DOCUMENT_NAME,
        "documentType": DOCUMENT_TYPE,
        "releaseSubjectType": "ORDER_ENGINEERED_PRODUCT",
        "orderEngineeringInstanceId": INSTANCE_ID,
        "engineeringBaselineId": BASELINE_ID,
        "engineeringCalculationId": CALCULATION_ID,
        "productBomId": PRODUCT_BOM_ID,
        "bomVersionId": BOM_VERSION_ID,
        "routingId": 31,
        "routingVersionId": 31,
        "documentVersion": "V1.0",
    }
    actual = {
        "documentName": version.document_name,
        "documentType": version.document.document_type,
        "releaseSubjectType": version.release_subject_type,
        "orderEngineeringInstanceId": version.order_engineering_instance_id,
        "engineeringBaselineId": version.order_engineering_baseline_id,
        "engineeringCalculationId": version.engineering_calculation_id,
        "productBomId": version.document.product_bom_id,
        "bomVersionId": version.related_bom_id,
        "routingId": version.document.routing_id,
        "routingVersionId": version.related_routing_id,
        "documentVersion": version.document_version,
    }
    assert actual == expected, f"target_source_chain_mismatch:{actual}"
    assert version.order_engineering_instance.sales_order_item_id == ITEM_ID
    assert version.order_engineering_instance.sales_order_item.sales_order.order_no == ORDER_NO
    version.full_clean()
    return version


def duplicate_facts(version_id: int | None = None) -> dict:
    if version_id is None:
        return {
            "workflowInstances": 0,
            "reviewTransitions": 0,
            "releaseTransitions": 0,
            "reviewAudits": 0,
            "releaseAudits": 0,
        }
    return {
        "workflowInstances": WorkflowInstance.objects.filter(
            document_type__in=(
                "EngineeringDocumentVersion", "pde.EngineeringDocumentVersion",
                "engineering-document-versions",
            ),
            document_id=version_id,
        ).count(),
        "reviewTransitions": BusinessStateTransition.objects.filter(
            object_type="EngineeringDocumentVersion", object_id=version_id,
            action_code=REVIEW_ACTION, target_state="reviewed",
        ).count(),
        "releaseTransitions": BusinessStateTransition.objects.filter(
            object_type="EngineeringDocumentVersion", object_id=version_id,
            action_code=RELEASE_ACTION, target_state="released",
        ).count(),
        "reviewAudits": OrganizationOperatingAuditRecord.objects.filter(
            target_type="EngineeringDocumentVersion", target_id=version_id,
            action_code=REVIEW_ACTION,
        ).count(),
        "releaseAudits": OrganizationOperatingAuditRecord.objects.filter(
            target_type="EngineeringDocumentVersion", target_id=version_id,
            action_code=RELEASE_ACTION,
        ).count(),
    }


def permission_precheck(existing_version: EngineeringDocumentVersion) -> dict:
    definition, node, template_error = resolve_workflow_template()
    assert template_error is None
    review_actors = eligible_review_actors(existing_version, definition, node)
    release_actors = eligible_release_actors(existing_version)
    reviewer = next((row for row in review_actors if row["userId"] == REVIEWER_ID), None)
    publisher = next((row for row in release_actors if row["userId"] == PUBLISHER_ID), None)
    assert reviewer is not None, "formal_reviewer_not_eligible"
    assert publisher is not None, "formal_publisher_not_eligible"
    assert reviewer["userId"] != publisher["userId"]
    assert reviewer["authorizationDecisionCode"] == "ALLOWED"
    assert publisher["authorizationDecisionCode"] == "ALLOWED"
    return {
        "workflow": {
            "definitionId": definition.pk,
            "definitionCode": definition.definition_code,
            "nodeId": node.pk,
            "nodeCode": node.node_code,
        },
        "reviewer": reviewer,
        "publisher": publisher,
        "segregationOfDuties": True,
    }


def precheck(maintainer: User) -> dict:
    item = SalesOrderItem.objects.select_related("sales_order").get(pk=ITEM_ID)
    assert item.line_no == LINE_NO and item.sales_order.order_no == ORDER_NO
    assert item.sales_order_id == ORDER_ID
    version = BOMVersion.objects.select_related("bom").get(pk=BOM_VERSION_ID)
    assert version.bom_id == PRODUCT_BOM_ID
    assert version.order_engineering_instance_id == INSTANCE_ID
    assert version.source_calculation_id == CALCULATION_ID
    assert version.bom_version == "CALC-4" and version.revision == 1
    assert version.status == "released"
    assert ProductManufacturingOutput.objects.filter(
        order_engineering_instance_id=INSTANCE_ID,
    ).count() == 0
    assert EngineeringDocument.objects.filter(
        order_engineering_instance_id=INSTANCE_ID,
    ).count() == 0
    assert EngineeringDocumentVersion.objects.filter(
        order_engineering_instance_id=INSTANCE_ID,
    ).count() == 0
    registration = OrderEngineeringDocumentRegistrationService.preflight(
        user=maintainer,
        order_no=ORDER_NO,
        line_no=LINE_NO,
        document_no=DOCUMENT_NO,
        document_name=DOCUMENT_NAME,
        document_type=DOCUMENT_TYPE,
    )
    assert registration["idempotentComplete"] is False
    assert registration["counts"] == {
        "engineeringDocument": 0,
        "engineeringDocumentVersion": 0,
        "productManufacturingOutput": 0,
    }
    assert registration["chain"]["bomVersion"] == {
        "id": BOM_VERSION_ID,
        "bomVersion": "CALC-4",
        "revision": 1,
        "status": "released",
    }
    existing_version = EngineeringDocumentVersion.objects.get(pk=1)
    permissions = permission_precheck(existing_version)
    return {
        "item4Counts": registration["counts"],
        "globalLifecycleCounts": lifecycle_counts(),
        "sourceChain": registration["chain"],
        "registrationAuthorization": registration["authorization"],
        "registrationExecutionChain": registration["executionChain"],
        "responsibilities": permissions,
        "duplicateVersionCandidates": 0,
        "duplicateReviewOrReleaseFacts": duplicate_facts(),
    }


def execute_chain(maintainer: User, reviewer: User, publisher: User) -> dict:
    version = exact_target_version(allow_missing=True)
    registration = None
    review = None
    publication = None
    skipped = []

    if version is None:
        registration = OrderEngineeringDocumentRegistrationService.register(
            user=maintainer,
            order_no=ORDER_NO,
            line_no=LINE_NO,
            document_no=DOCUMENT_NO,
            document_name=DOCUMENT_NAME,
            document_type=DOCUMENT_TYPE,
            idempotency_key=REGISTRATION_KEY,
            reason=REGISTRATION_REASON,
        )
        assert registration["outcome"] == "PASS"
        version = exact_target_version()
    elif version.status in {"reviewed", "released"}:
        skipped.append("registration_exact_target_already_advanced")
    else:
        registration = OrderEngineeringDocumentRegistrationService.register(
            user=maintainer,
            order_no=ORDER_NO,
            line_no=LINE_NO,
            document_no=DOCUMENT_NO,
            document_name=DOCUMENT_NAME,
            document_type=DOCUMENT_TYPE,
            idempotency_key=REGISTRATION_KEY,
            reason=REGISTRATION_REASON,
        )
        version = exact_target_version()

    if version.status == "draft":
        review_preflight = project_review_preflight(version, reviewer)
        assert review_preflight["readyForHumanReview"] is True
        assert review_preflight["reviewAllowed"] is True
        assert review_preflight["currentActor"]["userId"] == REVIEWER_ID
        review = review_engineering_document_version(
            object_id=version.pk,
            user=reviewer,
            reason=REVIEW_REASON,
            idempotency_key=REVIEW_KEY,
            action=REVIEW_ACTION,
        )
        version.refresh_from_db()
    elif version.status in {"reviewed", "released"}:
        skipped.append("review_exact_target_already_completed")
    else:
        raise AssertionError(f"unexpected_document_version_status:{version.status}")

    if version.status == "reviewed":
        release_preflight = project_release_preflight(version, publisher)
        assert release_preflight["readyForHumanRelease"] is True
        assert release_preflight["releaseAllowed"] is True
        assert release_preflight["currentActor"]["userId"] == PUBLISHER_ID
        assert release_preflight["reviewReadback"]["actorId"] == REVIEWER_ID
        publication = release_engineering_document_version(
            object_id=version.pk,
            user=publisher,
            reason=RELEASE_REASON,
            idempotency_key=RELEASE_KEY,
            action=RELEASE_ACTION,
        )
        version.refresh_from_db()
    elif version.status == "released":
        skipped.append("release_exact_target_already_completed")
    else:
        raise AssertionError(f"unexpected_document_version_status:{version.status}")

    assert version.status == "released"
    final = final_readback(version)
    return {
        "idempotentReplay": registration is None and review is None and publication is None,
        "registration": registration,
        "review": review,
        "publication": publication,
        "skippedStages": skipped,
        "readback": final,
    }


def next_gate(item: SalesOrderItem) -> dict:
    try:
        instance, document, fields, fingerprint = resolve_sources(item)
        source_gate = {
            "targetGateCode": "MANUFACTURING_OUTPUT_RELEASED_DOCUMENT_REQUIRED",
            "targetGateResult": "CLEARED",
            "sourceReady": True,
            "orderEngineeringInstanceId": instance.pk,
            "engineeringDocumentVersionId": document.pk,
            "sourceFields": fields,
            "sourceFingerprint": fingerprint,
        }
    except ManufacturingOutputError as exc:
        source_gate = {
            "targetGateCode": "MANUFACTURING_OUTPUT_RELEASED_DOCUMENT_REQUIRED",
            "targetGateResult": "NOT_CLEARED" if exc.code == "MANUFACTURING_OUTPUT_RELEASED_DOCUMENT_REQUIRED" else "CLEARED",
            "sourceReady": False,
            "firstBlockerCode": exc.code,
            "firstBlockerMessage": exc.message,
            "details": exc.details,
        }
    order = SalesOrder.objects.get(pk=ORDER_ID)
    readiness = engineering_readiness_facts(order)
    line = next(row for row in readiness["lines"] if row["salesOrderItemId"] == ITEM_ID)
    return {
        "manufacturingOutputSourceGate": source_gate,
        "demandAdmission": {
            "code": "ORDER_DEMAND_MANUFACTURING_NOT_READY" if not line["ready"] else "PASS",
            "salesOrderItemId": ITEM_ID,
            "engineeringBlockerCode": line["engineeringBlockerCode"],
            "blockers": line["blockers"],
            "manufacturingReady": line["manufacturingReady"],
            "planningDemandEligible": line["planningDemandEligible"],
        },
    }


def final_readback(version: EngineeringDocumentVersion) -> dict:
    version = exact_target_version()
    review = review_readback(version)
    publication = release_readback(version)
    completeness = project_release_source_completeness(version)
    integrity = project_release_content_integrity(version)
    duplicates = duplicate_facts(version.pk)
    assert version.status == "released"
    assert review["completed"] is True and review["actorId"] == REVIEWER_ID
    assert publication["completed"] is True and publication["actorId"] == PUBLISHER_ID
    assert review["workflowInstanceId"] == publication["workflowInstanceId"]
    assert completeness["complete"] is True
    assert integrity["valid"] is True
    assert duplicates == {
        "workflowInstances": 1,
        "reviewTransitions": 1,
        "releaseTransitions": 1,
        "reviewAudits": 1,
        "releaseAudits": 1,
    }
    assert version.manufacturing_outputs.count() == 0
    item = SalesOrderItem.objects.get(pk=ITEM_ID)
    gate = next_gate(item)
    assert gate["manufacturingOutputSourceGate"]["targetGateResult"] == "CLEARED"
    return {
        "engineeringDocument": {
            "id": version.document_id,
            "documentNo": version.document.document_no,
            "documentName": version.document.document_name,
            "documentType": version.document.document_type,
            "status": version.document.status,
            "versionProjection": version.document.version,
            "orderEngineeringInstanceId": version.document.order_engineering_instance_id,
            "productBomId": version.document.product_bom_id,
            "routingId": version.document.routing_id,
        },
        "engineeringDocumentVersion": {
            "id": version.pk,
            "documentVersion": version.document_version,
            "status": version.status,
            "releaseSubjectType": version.release_subject_type,
            "orderEngineeringInstanceId": version.order_engineering_instance_id,
            "engineeringBaselineId": version.order_engineering_baseline_id,
            "engineeringCalculationId": version.engineering_calculation_id,
            "bomVersionId": version.related_bom_id,
            "routingVersionId": version.related_routing_id,
        },
        "review": review,
        "publication": publication,
        "sourceCompleteness": completeness,
        "contentIntegrity": integrity,
        "duplicateFacts": duplicates,
        "manufacturingOutputCount": version.manufacturing_outputs.count(),
        "nextGate": gate,
    }


def json_ready(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized-item4", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--backup")
    parser.add_argument("--output")
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()

    assert Path(connection.settings_dict["NAME"]).resolve() == DATABASE.resolve(), "wrong_database"
    assert os.environ.get("PCE_RUNTIME_PROFILE") == "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    assert os.environ.get("PCE_DATABASE_IDENTITY") == DATABASE_IDENTITY
    assert os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") == "1"
    connection.ensure_connection()

    before_sha = sha256(DATABASE)
    if args.verify_existing:
        version = exact_target_version()
        output = {
            "mode": "READ_ONLY_FINAL",
            "database": {
                "identity": DATABASE_IDENTITY,
                "path": str(DATABASE),
                "sha256": before_sha,
            },
            "finalReadback": final_readback(version),
            "lifecycleCounts": lifecycle_counts(),
            "protectedCounts": protected_counts(),
            "protectedObjectHashes": {
                key: value["sha256"] for key, value in protected_snapshot().items()
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
        return

    if args.execute_authorized_item4:
        assert args.expected_sha256 and args.backup, "write_requires_expected_sha_and_backup"
        assert before_sha == args.expected_sha256.upper(), "database_sha_changed_before_write"
        backup = Path(args.backup).resolve()
        assert backup.is_file() and backup.parent.is_relative_to(DATABASE.parent), "invalid_backup"
        assert sha256(backup) == before_sha, "backup_sha_mismatch"

    maintainer, reviewer, publisher = users()
    physical_before = physical_snapshot()
    protected_before = protected_snapshot()
    counts_before = protected_counts()
    lifecycle_before = lifecycle_counts()
    before = precheck(maintainer)

    if not args.execute_authorized_item4:
        output = {
            "mode": "READ_ONLY",
            "database": {
                "identity": DATABASE_IDENTITY,
                "path": str(DATABASE),
                "sha256": before_sha,
            },
            "before": before,
            "protectedObjectHashes": {
                key: value["sha256"] for key, value in protected_before.items()
            },
            "protectedCounts": counts_before,
        }
    else:
        first = execute_chain(maintainer, reviewer, publisher)
        physical_after_first = physical_snapshot()
        physical_delta = compare_physical(physical_before, physical_after_first)
        assert protected_snapshot() == protected_before, "protected_object_changed"
        assert protected_counts() == counts_before, "forbidden_object_changed"
        connection.close()
        after_first_sha = sha256(DATABASE)

        replay = execute_chain(maintainer, reviewer, publisher)
        assert replay["idempotentReplay"] is True
        physical_after_replay = physical_snapshot()
        assert physical_after_replay == physical_after_first, "idempotent_replay_wrote_database"
        assert protected_snapshot() == protected_before, "protected_object_changed_after_replay"
        assert protected_counts() == counts_before, "forbidden_object_changed_after_replay"
        final = final_readback(exact_target_version())
        lifecycle_after = lifecycle_counts()
        connection.close()
        after_replay_sha = sha256(DATABASE)
        assert after_replay_sha == after_first_sha, "idempotent_replay_changed_database_sha"

        output = {
            "mode": "EXECUTED",
            "database": {
                "identity": DATABASE_IDENTITY,
                "path": str(DATABASE),
                "beforeSha256": before_sha,
                "afterFirstExecutionSha256": after_first_sha,
                "afterIdempotentReplaySha256": after_replay_sha,
            },
            "backup": {"path": str(Path(args.backup).resolve()), "sha256": before_sha},
            "before": before,
            "firstExecution": first,
            "finalReadback": final,
            "physicalDelta": physical_delta,
            "lifecycleCounts": {"before": lifecycle_before, "after": lifecycle_after},
            "idempotency": {
                "registrationKey": REGISTRATION_KEY,
                "reviewKey": REVIEW_KEY,
                "releaseKey": RELEASE_KEY,
                "wholeChainReplay": replay,
                "replayBusinessWriteCount": 0,
                "databaseShaUnchangedOnReplay": after_replay_sha == after_first_sha,
                "physicalSnapshotUnchangedOnReplay": physical_after_replay == physical_after_first,
            },
            "preservation": {
                "allPreExistingDatabaseRowsPreserved": physical_delta["allExistingRowsPreserved"],
                "protectedObjectHashesBeforeAndAfterEqual": protected_snapshot() == protected_before,
                "protectedCountsBeforeAndAfterEqual": protected_counts() == counts_before,
                "protectedObjectHashes": {
                    key: value["sha256"] for key, value in protected_before.items()
                },
                "protectedCounts": counts_before,
            },
        }

    serialized = json.dumps(json_ready(output), ensure_ascii=False, indent=2)
    if args.output:
        target = Path(args.output).resolve()
        assert target.is_relative_to(Path(__file__).resolve().parents[2]), "output_outside_source"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
