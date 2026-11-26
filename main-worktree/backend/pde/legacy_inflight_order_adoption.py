"""Formal adoption of pre-admission-model in-flight SalesOrders.

The service preserves the historical record.  It never creates or edits a CRM
Review, 0032 relation, 0033 predecessor, PDE authorization, OEI, calculation,
BOM or routing.  The persisted adoption is a closed immutable scope and its
revocation is an independent append-only fact.
"""

from __future__ import annotations
from pde.baseline_usage_service import production_status, production_baselines

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from masterdata.models import MasterDataWriteRequest
from sales.crm_source_establishment import (
    SalesOrderCRMSourceEstablishmentError,
    resolve_current_crm_source,
)
from sales.models import SalesOrder
from system.authorization import AuthorizationService
from system.models import (
    OrganizationOperatingAuditRecord,
    PositionWorkflowResponsibility,
)

from .manufacturing_structure_service import (
    ManufacturingStructureError,
    ManufacturingStructureService,
)
from .models import (
    BOMVersion,
    EngineeringCalculationDetail,
    EngineeringCalculationRecord,
    EngineeringDerivedFact,
    LegacyInFlightOrderAdoption,
    LegacyInFlightOrderAdoptionRevocation,
    OrderCrossFunctionalReview,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
    OrderReviewSalesOrderRelation,
    PDEAdmissionChainRevocation,
    PDEEngineeringPreparationAuthorization,
    PDEReviewPredecessorRelation,
    ProductBOM,
    ProductDesignCompletionRecord,
    ProductDesignItem,
    Routing,
)


ACTION_CODE = "pde.legacy_inflight_order.adopt"
REVOCATION_ACTION_CODE = "pde.legacy_inflight_order.revoke"
AUTHORIZATION_PERMISSION = "production.engineering.source.maintain"
REASON_CODE = "PRE_ADMISSION_MODEL_IN_FLIGHT"
ADMISSION_MODE = "LEGACY_IN_FLIGHT_ADOPTION"
STATUS_CODE = "PDE_LEGACY_IN_FLIGHT_ADOPTED"
MODEL_CUTOFF_MIGRATIONS = (
    "0032_order_review_sales_order_relation",
    "0033_pde_engineering_preparation_relations",
)


class LegacyInFlightOrderAdoptionError(ValueError):
    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class ActiveLegacyAdoptionResult:
    adoption: LegacyInFlightOrderAdoption
    source_binding: object
    evidence: dict
    calculation_continuations: tuple = ()

    @property
    def relation_id(self):
        return None

    @property
    def scope_mode(self):
        return "IMMUTABLE_LEGACY_SCOPE"

    @property
    def identity(self):
        return self.source_binding.scope["identityComparisons"]

    def as_dict(self):
        historical = self.evidence.get("historicalReviewException")
        result = {
            "admitted": True,
            "admissionMode": ADMISSION_MODE,
            "statusCode": STATUS_CODE,
            "statusLabel": "历史在制订单已正式承接",
            "legacyAdoptionId": self.adoption.pk,
            "legacyAdoptionNo": self.adoption.adoption_no,
            "legacyAdoptionEvidenceHash": self.adoption.evidence_hash,
            "sourceRecordId": self.adoption.source_record_id,
            "sourceIdentityId": self.adoption.source_identity_id,
            "sourceOrderNo": self.source_binding.scope["sourceOrderNo"],
            "sourceVersion": self.adoption.source_record.source_version,
            "sourceContentHash": self.adoption.source_record.content_hash,
            "reviewId": None,
            "reviewVersion": None,
            "workflowInstanceId": None,
            "approvalDecisionId": None,
            "relationId": None,
            "scopeMode": "IMMUTABLE_LEGACY_SCOPE",
            "businessIdentity": self.source_binding.scope["identityComparisons"],
            "currentReview": None,
            "currentRelation": None,
            "currentPredecessor": None,
            "currentAuthorization": None,
            "historicalReviewException": historical,
            "scope": deepcopy(self.evidence.get("scope") or {}),
        }
        if self.calculation_continuations:
            result['calculationContinuations'] = deepcopy(list(self.calculation_continuations))
        return result


def canonical_json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def evidence_hash(value):
    return sha256(canonical_json(value).encode("utf-8")).hexdigest().upper()


def _raise(code, message, **details):
    raise LegacyInFlightOrderAdoptionError(code, message, details=details)


def _iso(value):
    return value.isoformat() if value else None


def _actor_facts(actor):
    employee = getattr(actor, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    department = getattr(employee, "department_ref", None) if employee else None
    return employee, position, department, {
        "accountId": getattr(actor, "pk", None),
        "account": getattr(actor, "username", ""),
        "employeeId": getattr(employee, "pk", None),
        "employeeNo": getattr(employee, "employee_no", ""),
        "employeeName": getattr(employee, "full_name", ""),
        "positionId": getattr(employee, "position_ref_id", None),
        "positionCode": getattr(position, "code", ""),
        "positionName": getattr(position, "name", ""),
        "departmentId": getattr(employee, "department_ref_id", None),
        "departmentCode": getattr(department, "code", ""),
        "departmentName": getattr(department, "name", ""),
        "companyId": getattr(actor, "company_id", None),
    }


def _assert_actor_authorized(*, actor, order):
    if not actor or not actor.is_authenticated or not actor.is_active:
        _raise("LEGACY_ADOPTION_ACTOR_INVALID", "历史在制承接必须由有效登录账户执行。")
    if actor.is_superuser:
        _raise("LEGACY_ADOPTION_ADMIN_FORBIDDEN", "历史在制承接禁止使用管理员或超级用户账户执行。")
    employee, position, department, facts = _actor_facts(actor)
    if (
        not employee
        or employee.status != "active"
        or not position
        or not position.is_active
        or not department
        or not department.is_active
    ):
        _raise(
            "LEGACY_ADOPTION_EMPLOYEE_REQUIRED",
            "执行账户必须关联在职员工、有效部门和正式岗位。",
        )
    if actor.company_id != order.company_id or department.company_id != order.company_id:
        _raise("LEGACY_ADOPTION_COMPANY_MISMATCH", "执行员工与销售订单不属于同一公司。")
    authorization = AuthorizationService.decide(
        user=actor,
        action_code=AUTHORIZATION_PERMISSION,
        organization_id=order.company_id,
        business_object={
            "organizationId": order.company_id,
            "departmentId": order.department_id,
            "ownerUserId": order.created_by_id,
        },
    )
    if not authorization.get("allowed"):
        _raise(
            "LEGACY_ADOPTION_PERMISSION_DENIED",
            "执行账户没有正式工程来源维护权限或数据范围不覆盖目标订单。",
            authorization=authorization,
        )
    workflow_mapping = PositionWorkflowResponsibility.objects.select_related(
        "responsibility", "workflow_node__process_definition",
    ).filter(
        position=position,
        active=True,
        responsibility__is_active=True,
        ownership_type__in=("OWNER", "EXECUTOR"),
    ).order_by("pk").first()
    if not workflow_mapping:
        _raise(
            "LEGACY_ADOPTION_WORKFLOW_RESPONSIBILITY_REQUIRED",
            "执行岗位没有生效的正式流程负责/执行责任，禁止历史承接。",
        )
    facts["roles"] = authorization.get("roleCodes") or []
    facts["authorizationPermission"] = AUTHORIZATION_PERMISSION
    facts["workflowResponsibility"] = {
        "mappingId": workflow_mapping.pk,
        "workflowCode": workflow_mapping.workflow_code,
        "nodeCode": workflow_mapping.node_code,
        "ownershipType": workflow_mapping.ownership_type,
        "responsibilityCode": workflow_mapping.responsibility.code,
    }
    return authorization, facts, workflow_mapping


def _cutoff_evidence():
    rows = {
        row.name: row.applied
        for row in MigrationRecorder.Migration.objects.filter(
            app="pde", name__in=MODEL_CUTOFF_MIGRATIONS,
        )
    }
    missing = [name for name in MODEL_CUTOFF_MIGRATIONS if name not in rows]
    if missing:
        _raise(
            "LEGACY_ADOPTION_CUTOFF_EVIDENCE_MISSING",
            "无法证明0032/0033正式Admission模型上线时间，禁止历史承接。",
            missingMigrations=missing,
        )
    return {
        name: {"migration": f"pde.{name}", "appliedAt": _iso(rows[name])}
        for name in MODEL_CUTOFF_MIGRATIONS
    }, rows


def _assert_before_cutoff(*, label, value, cutoff):
    if not value or value >= cutoff:
        _raise(
            "LEGACY_ADOPTION_POST_MODEL_EVIDENCE_FORBIDDEN",
            "关键工程成果不是在0032正式模型上线前形成，禁止历史承接。",
            subject=label,
            evidenceAt=_iso(value),
            cutoffAt=_iso(cutoff),
        )


def _relation_counts(order):
    relations = OrderReviewSalesOrderRelation.objects.filter(
        company_id=order.company_id, sales_order_id=order.pk,
    )
    predecessors = PDEReviewPredecessorRelation.objects.filter(
        company_id=order.company_id,
        crm_order_relation__sales_order_id=order.pk,
    )
    authorizations = PDEEngineeringPreparationAuthorization.objects.filter(
        company_id=order.company_id,
        predecessor_relation__crm_order_relation__sales_order_id=order.pk,
    )
    revocations = PDEAdmissionChainRevocation.objects.filter(
        company_id=order.company_id,
        crm_order_relation__sales_order_id=order.pk,
    )
    return {
        "relation0032": relations.count(),
        "relation0033": predecessors.count(),
        "authorization": authorizations.count(),
        "admissionRevocation": revocations.count(),
    }


def _bom_snapshot(instances):
    rows = []
    for instance in instances:
        headers = list(
            ProductBOM.objects.filter(
                order_engineering_instance=instance, is_active=True,
            ).order_by("pk")
        )
        versions = list(
            BOMVersion.objects.filter(
                order_engineering_instance=instance,
            ).select_related("bom", "source_calculation").order_by("pk")
        )
        rows.append({
            "lineNo": instance.sales_order_item.line_no,
            "salesOrderItemId": instance.sales_order_item_id,
            "orderEngineeringInstanceId": instance.pk,
            "bomIds": [row.pk for row in headers],
            "bomCodes": [row.bom_code for row in headers],
            "bomStatuses": [row.status for row in headers],
            "bomVersionIds": [row.pk for row in versions],
            "bomVersions": [row.bom_version for row in versions],
            "bomVersionStatuses": [row.status for row in versions],
            "sourceCalculationIds": [row.source_calculation_id for row in versions],
        })
    return {
        "lines": rows,
        "bomCompletion": sum(bool(row["bomIds"]) for row in rows),
        "bomVersionCompletion": sum(bool(row["bomVersionIds"]) for row in rows),
        "releasedBomVersionCount": sum(
            status == "released"
            for row in rows for status in row["bomVersionStatuses"]
        ),
        "lineCount": len(rows),
    }


def _routing_snapshot(instances):
    rows = []
    for instance in instances:
        direct_ids = list(
            Routing.objects.filter(
                order_engineering_instance=instance, is_active=True,
            ).values_list("pk", flat=True)
        )
        try:
            resolved = ManufacturingStructureService.resolve_effective_routing(instance)
            routing = resolved["routing"]
            version = resolved["routing_version"]
            row = {
                "lineNo": instance.sales_order_item.line_no,
                "orderEngineeringInstanceId": instance.pk,
                "routingId": routing.pk,
                "routingCode": routing.routing_code,
                "routingVersionId": version.pk,
                "routingVersion": version.routing_version,
                "routingVersionStatus": version.status,
                "resolvedScope": resolved["resolved_scope"],
                "orderSpecificPersistedBinding": bool(direct_ids),
                "orderSpecificRoutingIds": direct_ids,
            }
        except ManufacturingStructureError as exc:
            row = {
                "lineNo": instance.sales_order_item.line_no,
                "orderEngineeringInstanceId": instance.pk,
                "routingId": None,
                "routingVersionId": None,
                "routingVersionStatus": None,
                "resolvedScope": None,
                "orderSpecificPersistedBinding": bool(direct_ids),
                "orderSpecificRoutingIds": direct_ids,
                "resolutionError": {"code": exc.code, "message": exc.message},
            }
        rows.append(row)
    return {
        "lines": rows,
        "resolvedCount": sum(row["routingVersionId"] is not None for row in rows),
        "orderSpecificPersistedBindingCount": sum(
            row["orderSpecificPersistedBinding"] for row in rows
        ),
        "lineCount": len(rows),
    }


def build_legacy_adoption_evidence(*, order, lock=False):
    """Read-only fail-closed eligibility and deterministic evidence builder."""

    if order.business_purpose != SalesOrder.BusinessPurpose.FORMAL_SALE:
        _raise(
            "LEGACY_ADOPTION_FORMAL_SALE_REQUIRED",
            "只有持久化为FORMAL_SALE的真实订单可以历史承接。",
            businessPurpose=order.business_purpose,
        )
    if order.status == "cancelled":
        _raise("LEGACY_ADOPTION_CANCELLED_ORDER_FORBIDDEN", "已取消订单禁止历史承接。")

    relation_counts = _relation_counts(order)
    if relation_counts["admissionRevocation"]:
        _raise(
            "LEGACY_ADOPTION_ADMISSION_REVOCATION_PRESENT",
            "订单存在Admission Revocation，禁止历史承接。",
            relationCounts=relation_counts,
        )
    if relation_counts["relation0032"]:
        _raise(
            "LEGACY_ADOPTION_0032_PRESENT",
            "订单已存在0032关系，不得改走历史承接。",
            relationCounts=relation_counts,
        )
    if relation_counts["relation0033"]:
        _raise(
            "LEGACY_ADOPTION_0033_PRESENT",
            "订单已存在0033关系，不得改走历史承接。",
            relationCounts=relation_counts,
        )
    if relation_counts["authorization"]:
        _raise(
            "LEGACY_ADOPTION_AUTHORIZATION_PRESENT",
            "订单已存在工程准备Authorization，不得改走历史承接。",
            relationCounts=relation_counts,
        )

    try:
        source_binding = resolve_current_crm_source(order=order, lock=lock)
    except SalesOrderCRMSourceEstablishmentError as exc:
        raise LegacyInFlightOrderAdoptionError(
            exc.code, exc.message, details=exc.details,
        ) from exc
    if not source_binding:
        _raise("LEGACY_ADOPTION_CURRENT_SOURCE_REQUIRED", "订单没有唯一正式CRM来源。")

    baselines = production_baselines().filter(
        company_id=order.company_id, sales_order_id=order.pk, status="confirmed",
    ).order_by("pk")
    if lock:
        baselines = baselines.select_for_update()
    baselines = list(baselines[:3])
    if len(baselines) != 1:
        _raise(
            "LEGACY_ADOPTION_CONFIRMED_BASELINE_AMBIGUOUS",
            "历史承接要求唯一已确认工程基线。",
            confirmedBaselineIds=[row.pk for row in baselines],
        )
    baseline = baselines[0]
    baseline_item_count = baseline.items.count()
    if (
        baseline.blocker_count
        or baseline.scope_item_count <= 0
        or baseline.confirmable_item_count != baseline.scope_item_count
        or baseline_item_count != baseline.scope_item_count
    ):
        _raise(
            "LEGACY_ADOPTION_BASELINE_INCOMPLETE",
            "工程基线不是完整可确认范围，禁止历史承接。",
            baselineId=baseline.pk,
            scopeItemCount=baseline.scope_item_count,
            confirmableItemCount=baseline.confirmable_item_count,
            blockerCount=baseline.blocker_count,
            persistedItemCount=baseline_item_count,
        )

    order_items = list(order.items.order_by("line_no", "pk"))
    item_ids = [row.pk for row in order_items]
    if not item_ids:
        _raise("LEGACY_ADOPTION_ORDER_SCOPE_EMPTY", "销售订单没有可承接订单行。")
    design_items = list(
        ProductDesignItem.objects.filter(
            company_id=order.company_id,
            sales_order_item_id__in=item_ids,
            source_record_id=source_binding.source.pk,
        ).order_by("sales_order_item__line_no", "pk")
    )
    if not design_items or {row.sales_order_item_id for row in design_items} != set(item_ids):
        _raise(
            "LEGACY_ADOPTION_DESIGN_SCOPE_INCOMPLETE",
            "历史产品设计没有完整覆盖当前订单行范围。",
            salesOrderItemIds=item_ids,
            designSalesOrderItemIds=sorted({row.sales_order_item_id for row in design_items}),
        )
    completion_count = ProductDesignCompletionRecord.objects.filter(
        design_item_id__in=[row.pk for row in design_items],
    ).count()
    if completion_count != len(design_items):
        _raise(
            "LEGACY_ADOPTION_DESIGN_COMPLETION_INCOMPLETE",
            "产品设计完成记录没有精确覆盖历史设计项。",
            productDesignItemCount=len(design_items),
            completionRecordCount=completion_count,
        )

    instances = OrderEngineeringInstance.objects.select_related(
        "sales_order_item__sales_order", "source_record", "product_category",
        "selected_process_type", "product",
    ).filter(
        company_id=order.company_id,
        sales_order_item_id__in=item_ids,
    ).order_by("sales_order_item__line_no", "pk")
    if lock:
        instances = instances.select_for_update()
    instances = list(instances)
    if (
        len(instances) != len(item_ids)
        or {row.sales_order_item_id for row in instances} != set(item_ids)
        or any(row.source_record_id != source_binding.source.pk for row in instances)
        or any(row.status not in {"source_confirmed", "calculated", "released"} for row in instances)
        or any(row.engineering_preparation_authorization_id is not None for row in instances)
    ):
        _raise(
            "LEGACY_ADOPTION_OEI_SCOPE_INCOMPLETE",
            "OEI没有以同一来源、无伪造Authorization完整覆盖订单行。",
            salesOrderItemIds=item_ids,
            oeiIds=[row.pk for row in instances],
        )

    calculations = list(
        EngineeringCalculationRecord.objects.filter(
            company_id=order.company_id,
            engineering_instance_id__in=[row.pk for row in instances],
            sales_order_item_id__in=item_ids,
            source_record_id=source_binding.source.pk,
            scope="order_engineering",
            status="completed",
        ).order_by("engineering_instance_id", "revision", "pk")
    )
    per_instance = Counter(row.engineering_instance_id for row in calculations)
    if (
        len(calculations) != len(instances)
        or set(per_instance) != {row.pk for row in instances}
        or any(value != 1 for value in per_instance.values())
    ):
        _raise(
            "LEGACY_ADOPTION_CALCULATION_SCOPE_INCOMPLETE",
            "已完成工程核算没有一对一稳定覆盖OEI范围。",
            oeiIds=[row.pk for row in instances],
            calculationIds=[row.pk for row in calculations],
            perOeiCount=dict(per_instance),
        )

    cutoff_evidence, cutoff_rows = _cutoff_evidence()
    cutoff = cutoff_rows[MODEL_CUTOFF_MIGRATIONS[0]]
    critical_times = {
        "salesOrderCreatedAt": order.created_at,
        "productDesignLatestCreatedAt": max(row.created_at for row in design_items),
        "engineeringBaselineCreatedAt": baseline.created_at,
        "engineeringBaselineConfirmedAt": baseline.confirmed_at,
        "orderEngineeringInstanceLatestCreatedAt": max(row.created_at for row in instances),
        "engineeringCalculationLatestCreatedAt": max(row.created_at for row in calculations),
        "engineeringCalculationLatestFinishedAt": max(
            (row.finished_at or row.created_at) for row in calculations
        ),
    }
    completion_latest = ProductDesignCompletionRecord.objects.filter(
        design_item_id__in=[row.pk for row in design_items],
    ).order_by("-recorded_at").values_list("recorded_at", flat=True).first()
    critical_times["productDesignCompletionLatestAt"] = completion_latest
    for label, value in critical_times.items():
        _assert_before_cutoff(label=label, value=value, cutoff=cutoff)

    historical_review = OrderCrossFunctionalReview.objects.filter(
        company_id=order.company_id,
        source_record_id=source_binding.source.pk,
        source_order_no=source_binding.scope["sourceOrderNo"],
        review_type="CRM_ORDER_REVIEW",
        record_status="SUBMITTED",
    ).order_by("created_at", "pk").first()
    review_exception = (
        {
            "reviewId": historical_review.pk,
            "reviewVersion": historical_review.review_version,
            "recordStatus": historical_review.record_status,
            "conclusion": historical_review.conclusion,
            "preserved": True,
            "usedAsApproval": False,
        }
        if historical_review else None
    )

    detail_count = EngineeringCalculationDetail.objects.filter(
        calculation_id__in=[row.pk for row in calculations],
    ).count()
    derived_count = EngineeringDerivedFact.objects.filter(
        calculation_id__in=[row.pk for row in calculations],
    ).count()
    bom = _bom_snapshot(instances)
    routing = _routing_snapshot(instances)
    evidence = {
        "schemaVersion": "PDE-LEGACY-IN-FLIGHT-ADOPTION-V1",
        "reasonCode": REASON_CODE,
        "salesOrder": {
            "id": order.pk,
            "orderNo": order.order_no,
            "businessPurpose": order.business_purpose,
            "status": order.status,
            "customerId": order.customer_id,
            "customerName": order.customer.name,
            "projectReference": order.project_reference,
            "externalSourceNo": order.external_source_no,
            "createdAt": _iso(order.created_at),
        },
        "source": {
            "id": source_binding.source.pk,
            "sourceNo": source_binding.source.source_no,
            "sourceVersion": source_binding.source.source_version,
            "contentHash": source_binding.source.content_hash,
            "status": source_binding.source.status,
        },
        "sourceIdentity": {
            "id": source_binding.identity.pk,
            "externalId": source_binding.identity.external_id,
            "sourceFingerprint": source_binding.identity.source_fingerprint,
            "targetEntityType": source_binding.identity.target_entity_type,
            "targetEntityId": source_binding.identity.target_entity_id,
        },
        "historicalReviewException": review_exception,
        "engineeringBaseline": {
            "id": baseline.pk,
            "baselineNo": baseline.baseline_no,
            "status": baseline.status,
            "snapshotHash": baseline.snapshot_hash,
            "scopeItemCount": baseline.scope_item_count,
            "confirmableItemCount": baseline.confirmable_item_count,
            "blockerCount": baseline.blocker_count,
            "createdAt": _iso(baseline.created_at),
            "confirmedAt": _iso(baseline.confirmed_at),
        },
        "scope": {
            "salesOrderId": order.pk,
            "salesOrderItemIds": item_ids,
            "lineNos": [row.line_no for row in order_items],
            "orderEngineeringInstanceIds": [row.pk for row in instances],
            "engineeringCalculationIds": [row.pk for row in calculations],
            "engineeringBaselineId": baseline.pk,
            "sourceRecordId": source_binding.source.pk,
            "sourceIdentityId": source_binding.identity.pk,
        },
        "orderEngineeringInstances": [
            {
                "id": row.pk,
                "instanceNo": row.instance_no,
                "salesOrderItemId": row.sales_order_item_id,
                "lineNo": row.sales_order_item.line_no,
                "sourceRecordId": row.source_record_id,
                "status": row.status,
                "engineeringPreparationAuthorizationId": row.engineering_preparation_authorization_id,
                "createdAt": _iso(row.created_at),
            }
            for row in instances
        ],
        "engineeringCalculations": [
            {
                "id": row.pk,
                "calculationNo": row.calculation_no,
                "orderEngineeringInstanceId": row.engineering_instance_id,
                "salesOrderItemId": row.sales_order_item_id,
                "sourceRecordId": row.source_record_id,
                "status": row.status,
                "revision": row.revision,
                "inputHash": row.input_hash,
                "ruleGraphHash": row.rule_graph_hash,
                "resultHash": row.result_hash,
                "createdAt": _iso(row.created_at),
                "finishedAt": _iso(row.finished_at),
            }
            for row in calculations
        ],
        "engineeringResults": {
            "productDesignItemCount": len(design_items),
            "productDesignCompletionRecordCount": completion_count,
            "calculationDetailCount": detail_count,
            "engineeringDerivedFactCount": derived_count,
        },
        "bomAtAdoption": bom,
        "routingAtAdoption": routing,
        "migrationCutoffEvidence": cutoff_evidence,
        "criticalEvidenceTimes": {
            key: _iso(value) for key, value in critical_times.items()
        },
        "legacyAdmissionGap": {
            "currentCrmReview": None,
            "relation0032": None,
            "predecessor0033": None,
            "engineeringPreparationAuthorization": None,
            "relationCounts": relation_counts,
        },
    }
    return {
        "order": order,
        "sourceBinding": source_binding,
        "baseline": baseline,
        "instances": instances,
        "calculations": calculations,
        "cutoffEvidence": cutoff_evidence,
        "evidence": evidence,
        "evidenceHash": evidence_hash(evidence),
        "businessWriteCount": 0,
    }


def inspect_legacy_inflight_order_adoption(*, actor, order):
    """Read-only command/API preflight including actor authority evidence."""

    authorization, actor_facts, workflow_mapping = _assert_actor_authorized(
        actor=actor, order=order,
    )
    built = build_legacy_adoption_evidence(order=order)
    return {
        "eligible": True,
        "actionCode": ACTION_CODE,
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "sourceRecordId": built["sourceBinding"].source.pk,
        "sourceIdentityId": built["sourceBinding"].identity.pk,
        "engineeringBaselineId": built["baseline"].pk,
        "orderEngineeringInstanceIds": sorted(row.pk for row in built["instances"]),
        "engineeringCalculationIds": sorted(row.pk for row in built["calculations"]),
        "evidenceHash": built["evidenceHash"],
        "evidenceSnapshot": deepcopy(built["evidence"]),
        "actor": actor_facts,
        "authorizationDecision": authorization.get("decisionCode"),
        "workflowResponsibilityId": workflow_mapping.pk,
        "businessWriteCount": 0,
    }


def _expected_scope_check(*, built, expected):
    actual = {
        "sourceRecordId": built["sourceBinding"].source.pk,
        "sourceIdentityId": built["sourceBinding"].identity.pk,
        "engineeringBaselineId": built["baseline"].pk,
        "orderEngineeringInstanceIds": sorted(row.pk for row in built["instances"]),
        "engineeringCalculationIds": sorted(row.pk for row in built["calculations"]),
    }
    mismatch = {
        key: {"expected": expected[key], "actual": actual[key]}
        for key in actual
        if expected.get(key) != actual[key]
    }
    if mismatch:
        _raise(
            "LEGACY_ADOPTION_EXPECTED_SCOPE_MISMATCH",
            "当前历史工程范围与受控执行参数不一致。",
            mismatch=mismatch,
        )


def _serialize_adoption(adoption, *, idempotent, actor_facts=None):
    return {
        "actionCode": ACTION_CODE,
        "admitted": True,
        "admissionMode": ADMISSION_MODE,
        "statusCode": STATUS_CODE,
        "legacyAdoptionId": adoption.pk,
        "legacyAdoptionNo": adoption.adoption_no,
        "salesOrderId": adoption.sales_order_id,
        "salesOrderNo": adoption.sales_order.order_no,
        "sourceRecordId": adoption.source_record_id,
        "sourceIdentityId": adoption.source_identity_id,
        "engineeringBaselineId": adoption.engineering_baseline_id,
        "evidenceHash": adoption.evidence_hash,
        "evidenceSnapshot": deepcopy(adoption.evidence_snapshot),
        "auditId": adoption.audit_record_id,
        "actionRequestId": adoption.action_request_id,
        "createdAt": adoption.created_at.isoformat(),
        "createdBy": actor_facts or _actor_facts(adoption.created_by)[3],
        "idempotent": idempotent,
        "reviewWriteCount": 0,
        "relation0032WriteCount": 0,
        "relation0033WriteCount": 0,
        "authorizationWriteCount": 0,
        "oeiWriteCount": 0,
        "calculationWriteCount": 0,
        "bomWriteCount": 0,
    }


@transaction.atomic
def adopt_legacy_inflight_order(
    *, actor, order_id, expected_order_no, expected_source_record_id,
    expected_source_identity_id, expected_engineering_baseline_id,
    expected_order_engineering_instance_ids, expected_engineering_calculation_ids,
    idempotency_key, business_reason,
):
    key = str(idempotency_key or "").strip()
    reason = str(business_reason or "").strip()
    if not key:
        _raise("LEGACY_ADOPTION_IDEMPOTENCY_REQUIRED", "历史承接必须提供幂等键。")
    if not reason:
        _raise("LEGACY_ADOPTION_BUSINESS_REASON_REQUIRED", "历史承接必须提供正式业务授权依据。")

    order = SalesOrder.objects.select_for_update().select_related(
        "company", "department", "customer", "created_by",
    ).filter(pk=order_id).first()
    if not order or order.order_no != expected_order_no:
        _raise(
            "LEGACY_ADOPTION_ORDER_MISMATCH",
            "销售订单不存在或编号已变化。",
            salesOrderId=order_id,
            expectedOrderNo=expected_order_no,
        )

    replay = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=order.company_id,
        action_code=ACTION_CODE,
        entity_type="LegacyInFlightOrderAdoption",
        idempotency_key=key,
    ).first()
    if replay:
        adoption = LegacyInFlightOrderAdoption.objects.select_related(
            "sales_order", "source_record", "source_identity", "engineering_baseline",
            "created_by", "audit_record", "action_request",
        ).filter(action_request=replay).first()
        if (
            replay.status != MasterDataWriteRequest.Status.COMMITTED
            or not adoption
            or adoption.sales_order_id != order.pk
            or evidence_hash(adoption.evidence_snapshot) != adoption.evidence_hash
        ):
            _raise(
                "LEGACY_ADOPTION_IDEMPOTENCY_RESULT_INCOMPLETE",
                "既有幂等请求没有完整、可验证的承接结果。",
                actionRequestId=replay.pk,
            )
        return _serialize_adoption(adoption, idempotent=True)

    authorization, actor_facts, workflow_mapping = _assert_actor_authorized(
        actor=actor, order=order,
    )
    if LegacyInFlightOrderAdoption.objects.filter(sales_order=order).exists():
        _raise(
            "LEGACY_ADOPTION_ALREADY_EXISTS",
            "该订单已经存在历史承接事实；新幂等键不得重复承接。",
        )
    built = build_legacy_adoption_evidence(order=order, lock=True)
    expected = {
        "sourceRecordId": int(expected_source_record_id),
        "sourceIdentityId": int(expected_source_identity_id),
        "engineeringBaselineId": int(expected_engineering_baseline_id),
        "orderEngineeringInstanceIds": sorted(int(value) for value in expected_order_engineering_instance_ids),
        "engineeringCalculationIds": sorted(int(value) for value in expected_engineering_calculation_ids),
    }
    _expected_scope_check(built=built, expected=expected)

    payload = {
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "reasonCode": REASON_CODE,
        "businessReason": reason,
        "evidenceHash": built["evidenceHash"],
        "expectedScope": expected,
    }
    request = MasterDataWriteRequest.objects.create(
        organization_id=order.company_id,
        action_code=ACTION_CODE,
        entity_type="LegacyInFlightOrderAdoption",
        idempotency_key=key,
        request_hash=evidence_hash(payload),
        source_identity=built["sourceBinding"].identity,
        status=MasterDataWriteRequest.Status.RESERVED,
        audit_metadata={
            "reason": reason,
            "actor": actor_facts,
            "authorizationDecision": authorization.get("decisionCode"),
            "workflowResponsibilityId": workflow_mapping.pk,
        },
    )
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_CODE,
        actor=actor,
        organization_id=order.company_id,
        target_type="SalesOrder",
        target_id=order.pk,
        target_label=order.order_no,
        reason=reason,
        before_snapshot={
            "legacyAdoptionCount": 0,
            "admissionMode": None,
            "relationCounts": _relation_counts(order),
        },
        after_snapshot={
            "legacyAdoptionCount": 1,
            "admissionMode": ADMISSION_MODE,
            "evidenceHash": built["evidenceHash"],
            "scope": deepcopy(built["evidence"]["scope"]),
            "historicalReviewException": deepcopy(
                built["evidence"]["historicalReviewException"]
            ),
            "standardAdmissionObjectsFabricated": False,
            "reviewWriteCount": 0,
            "relation0032WriteCount": 0,
            "relation0033WriteCount": 0,
            "authorizationWriteCount": 0,
            "actor": actor_facts,
            "idempotencyKey": key,
        },
    )
    adoption = LegacyInFlightOrderAdoption(
        adoption_no=f"LIA-{order.order_no}",
        company_id=order.company_id,
        sales_order=order,
        source_record=built["sourceBinding"].source,
        source_identity=built["sourceBinding"].identity,
        engineering_baseline=built["baseline"],
        reason_code=REASON_CODE,
        business_reason=reason,
        evidence_snapshot=built["evidence"],
        evidence_hash=built["evidenceHash"],
        cutoff_evidence=built["cutoffEvidence"],
        idempotency_key=key,
        created_by=actor,
        audit_record=audit,
        action_request=request,
    )
    adoption.save()
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(adoption.pk)
    request.result = {
        "legacyAdoptionId": adoption.pk,
        "legacyAdoptionNo": adoption.adoption_no,
        "salesOrderId": order.pk,
        "evidenceHash": adoption.evidence_hash,
        "organizationAuditId": audit.pk,
    }
    request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])
    return _serialize_adoption(
        adoption, idempotent=False, actor_facts=actor_facts,
    )


def require_active_legacy_adoption(
    *, order, sales_order_item_id=None, engineering_instance_id=None,
    calculation_id=None, lock=False,
):
    queryset = LegacyInFlightOrderAdoption.objects.select_related(
        "sales_order__customer", "source_record", "source_identity",
        "engineering_baseline", "audit_record", "action_request",
    ).filter(company_id=order.company_id, sales_order_id=order.pk)
    if lock:
        queryset = queryset.select_for_update()
    adoption = queryset.first()
    if not adoption:
        return None
    revocation = LegacyInFlightOrderAdoptionRevocation.objects.filter(
        adoption=adoption,
    ).first()
    if revocation:
        _raise(
            "PDE_LEGACY_IN_FLIGHT_ADOPTION_REVOKED",
            "历史在制订单承接已经撤销，当前准入失败关闭。",
            legacyAdoptionId=adoption.pk,
            revocationId=revocation.pk,
            revocationNo=revocation.revocation_no,
        )
    if evidence_hash(adoption.evidence_snapshot) != adoption.evidence_hash:
        _raise(
            "PDE_LEGACY_IN_FLIGHT_EVIDENCE_HASH_MISMATCH",
            "历史承接Evidence Hash校验失败，当前准入失败关闭。",
            legacyAdoptionId=adoption.pk,
        )
    if order.business_purpose != SalesOrder.BusinessPurpose.FORMAL_SALE or order.status == "cancelled":
        _raise(
            "PDE_LEGACY_IN_FLIGHT_ORDER_NOT_CURRENT",
            "订单已不满足历史在制承接的当前业务身份。",
            legacyAdoptionId=adoption.pk,
            businessPurpose=order.business_purpose,
            orderStatus=order.status,
        )
    if _relation_counts(order) != {
        "relation0032": 0,
        "relation0033": 0,
        "authorization": 0,
        "admissionRevocation": 0,
    }:
        _raise(
            "PDE_LEGACY_IN_FLIGHT_STANDARD_CHAIN_CONFLICT",
            "历史承接订单出现标准Admission链或撤销冲突，当前准入失败关闭。",
            relationCounts=_relation_counts(order),
        )
    scope = adoption.evidence_snapshot.get("scope") or {}
    current_item_ids = sorted(order.items.values_list("pk", flat=True))
    current_oei_ids = sorted(
        OrderEngineeringInstance.objects.filter(
            sales_order_item__sales_order_id=order.pk,
        ).exclude(status="inactive").values_list("pk", flat=True)
    )
    current_calculation_ids = sorted(
        EngineeringCalculationRecord.objects.filter(
            engineering_instance_id__in=scope.get("orderEngineeringInstanceIds") or [],
            scope="order_engineering",
            status="completed",
        ).values_list("pk", flat=True)
    )
    if current_item_ids != sorted(scope.get("salesOrderItemIds") or []):
        _raise("PDE_LEGACY_IN_FLIGHT_ORDER_SCOPE_DRIFT", "订单行范围已超出历史承接锁定范围。")
    if current_oei_ids != sorted(scope.get("orderEngineeringInstanceIds") or []):
        _raise("PDE_LEGACY_IN_FLIGHT_OEI_SCOPE_DRIFT", "OEI范围已超出历史承接锁定范围。")
    from .engineering_calculation_continuation_service import admitted_continuations, EngineeringCalculationContinuationError
    try:
        continuations = admitted_continuations(adoption)
    except EngineeringCalculationContinuationError as error:
        raise LegacyInFlightOrderAdoptionError(error.code,error.message,details=error.details) from error
    allowed_calculation_ids = sorted(set(scope.get("engineeringCalculationIds") or [])
        | {row['newCalculationId'] for row in continuations})
    if current_calculation_ids != allowed_calculation_ids:
        _raise("PDE_LEGACY_IN_FLIGHT_CALCULATION_SCOPE_DRIFT", "工程核算范围已超出历史承接锁定范围。")
    try:
        source_binding = resolve_current_crm_source(order=order, lock=lock)
    except SalesOrderCRMSourceEstablishmentError as exc:
        raise LegacyInFlightOrderAdoptionError(
            exc.code, exc.message, details=exc.details,
        ) from exc
    if (
        not source_binding
        or source_binding.source.pk != adoption.source_record_id
        or source_binding.identity.pk != adoption.source_identity_id
        or source_binding.source.content_hash != adoption.evidence_snapshot["source"]["contentHash"]
    ):
        _raise(
            "PDE_LEGACY_IN_FLIGHT_SOURCE_DRIFT",
            "历史承接锁定的Source或Source Identity已漂移。",
            legacyAdoptionId=adoption.pk,
        )
    baseline = adoption.engineering_baseline
    if (
        production_status(baseline) != "confirmed"
        or baseline.snapshot_hash != adoption.evidence_snapshot["engineeringBaseline"]["snapshotHash"]
    ):
        _raise(
            "PDE_LEGACY_IN_FLIGHT_BASELINE_DRIFT",
            "历史承接锁定的工程基线已漂移。",
            legacyAdoptionId=adoption.pk,
        )
    requested = {
        "salesOrderItemId": sales_order_item_id,
        "orderEngineeringInstanceId": engineering_instance_id,
        "engineeringCalculationId": calculation_id,
    }
    membership = {
        "salesOrderItemId": scope.get("salesOrderItemIds") or [],
        "orderEngineeringInstanceId": scope.get("orderEngineeringInstanceIds") or [],
        "engineeringCalculationId": allowed_calculation_ids,
    }
    outside = {
        key: value for key, value in requested.items()
        if value is not None and int(value) not in membership[key]
    }
    if outside:
        _raise(
            "PDE_LEGACY_IN_FLIGHT_SCOPE_MISMATCH",
            "请求对象不在历史承接锁定范围内。",
            outsideScope=outside,
            lockedScope=scope,
        )
    return ActiveLegacyAdoptionResult(
        adoption=adoption,
        source_binding=source_binding,
        evidence=deepcopy(adoption.evidence_snapshot),
        calculation_continuations=tuple(continuations),
    )


@transaction.atomic
def revoke_legacy_inflight_order_adoption(
    *, actor, adoption_id, reason_code, reason, idempotency_key,
):
    key = str(idempotency_key or "").strip()
    reason = str(reason or "").strip()
    if not key:
        _raise("LEGACY_ADOPTION_REVOCATION_IDEMPOTENCY_REQUIRED", "承接撤销必须提供幂等键。")
    if reason_code not in {
        "BUSINESS_IDENTITY_CONFLICT", "EVIDENCE_INVALIDATED",
    }:
        _raise("LEGACY_ADOPTION_REVOCATION_REASON_INVALID", "承接撤销原因编码无效。")
    if not reason:
        _raise("LEGACY_ADOPTION_REVOCATION_REASON_REQUIRED", "承接撤销必须提供明确原因。")
    adoption = LegacyInFlightOrderAdoption.objects.select_for_update().select_related(
        "sales_order", "source_identity", "created_by",
    ).filter(pk=adoption_id).first()
    if not adoption:
        _raise("LEGACY_ADOPTION_NOT_FOUND", "历史在制承接事实不存在。")
    order = adoption.sales_order
    replay = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=adoption.company_id,
        action_code=REVOCATION_ACTION_CODE,
        entity_type="LegacyInFlightOrderAdoptionRevocation",
        idempotency_key=key,
    ).first()
    if replay:
        revocation = LegacyInFlightOrderAdoptionRevocation.objects.filter(
            action_request=replay,
        ).first()
        if replay.status != MasterDataWriteRequest.Status.COMMITTED or not revocation:
            _raise(
                "LEGACY_ADOPTION_REVOCATION_REPLAY_INCOMPLETE",
                "既有撤销幂等请求没有完整提交结果。",
            )
        return {
            "actionCode": REVOCATION_ACTION_CODE,
            "legacyAdoptionId": adoption.pk,
            "revocationId": revocation.pk,
            "revocationNo": revocation.revocation_no,
            "evidenceHash": revocation.evidence_hash,
            "auditId": revocation.audit_record_id,
            "actionRequestId": revocation.action_request_id,
            "idempotent": True,
        }
    _authorization, actor_facts, workflow_mapping = _assert_actor_authorized(
        actor=actor, order=order,
    )
    if LegacyInFlightOrderAdoptionRevocation.objects.filter(adoption=adoption).exists():
        _raise("LEGACY_ADOPTION_ALREADY_REVOKED", "历史在制承接已经被撤销。")
    snapshot = {
        "schemaVersion": "PDE-LEGACY-IN-FLIGHT-ADOPTION-REVOCATION-V1",
        "legacyAdoptionId": adoption.pk,
        "legacyAdoptionNo": adoption.adoption_no,
        "legacyAdoptionEvidenceHash": adoption.evidence_hash,
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "reasonCode": reason_code,
        "reason": reason,
        "actor": actor_facts,
    }
    digest = evidence_hash(snapshot)
    request = MasterDataWriteRequest.objects.create(
        organization_id=adoption.company_id,
        action_code=REVOCATION_ACTION_CODE,
        entity_type="LegacyInFlightOrderAdoptionRevocation",
        idempotency_key=key,
        request_hash=digest,
        source_identity=adoption.source_identity,
        status=MasterDataWriteRequest.Status.RESERVED,
        audit_metadata={
            "reason": reason,
            "reasonCode": reason_code,
            "actor": actor_facts,
            "workflowResponsibilityId": workflow_mapping.pk,
        },
    )
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=REVOCATION_ACTION_CODE,
        actor=actor,
        organization_id=adoption.company_id,
        target_type="LegacyInFlightOrderAdoption",
        target_id=adoption.pk,
        target_label=adoption.adoption_no,
        reason=reason,
        before_snapshot={"active": True, "evidenceHash": adoption.evidence_hash},
        after_snapshot={
            "active": False,
            "reasonCode": reason_code,
            "revocationEvidenceHash": digest,
            "originalAdoptionPreserved": True,
            "actor": actor_facts,
        },
    )
    effective_at = timezone.now()
    revocation = LegacyInFlightOrderAdoptionRevocation(
        revocation_no=f"LIA-REV-{adoption.pk}-{effective_at:%Y%m%d%H%M%S}",
        company_id=adoption.company_id,
        adoption=adoption,
        reason_code=reason_code,
        reason=reason,
        evidence_snapshot=snapshot,
        evidence_hash=digest,
        idempotency_key=key,
        created_by=actor,
        audit_record=audit,
        action_request=request,
        effective_at=effective_at,
    )
    revocation.save()
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(revocation.pk)
    request.result = {
        "legacyAdoptionId": adoption.pk,
        "revocationId": revocation.pk,
        "revocationNo": revocation.revocation_no,
        "evidenceHash": revocation.evidence_hash,
        "organizationAuditId": audit.pk,
    }
    request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])
    return {
        "actionCode": REVOCATION_ACTION_CODE,
        "legacyAdoptionId": adoption.pk,
        "revocationId": revocation.pk,
        "revocationNo": revocation.revocation_no,
        "evidenceHash": revocation.evidence_hash,
        "auditId": audit.pk,
        "actionRequestId": request.pk,
        "effectiveAt": revocation.effective_at.isoformat(),
        "idempotent": False,
    }
