"""Controlled correction and current-fact filters for revoked PDE admission chains."""

from __future__ import annotations

from hashlib import sha256
import json

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from planning.models import ProductionPlan
from sales.models import SalesOrder
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import (
    BusinessStateTransitionError,
    transition_business_object,
)

from .models import (
    EngineeringCalculationRecord,
    OrderCrossFunctionalReview,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
    OrderReviewSalesOrderRelation,
    PDEAdmissionChainRevocation,
    PDEEngineeringPreparationAuthorization,
    PDEReviewPredecessorRelation,
    ProductBOM,
    ProductDesignItem,
    ProductManufacturingOutput,
    Routing,
)


ACTION_CODE = "pde.admission_chain.revoke"
OBJECT_TYPE = "OrderEngineeringInstance"
REASON_CODE = "BUSINESS_IDENTITY_CONFLICT"
CURRENT_CHAIN_ABSENT_CODE = "PDE_ADMISSION_CHAIN_REVOKED"
CURRENT_CHAIN_ABSENT_MESSAGE = (
    "当前不存在有效的旧0032 / PDE / OEI准入链；历史冲突链已撤销并保留审计。"
)


class PDEAdmissionChainRevocationError(ValueError):
    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _canonical_hash(payload):
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def active_crm_order_relations(queryset=None):
    queryset = queryset if queryset is not None else OrderReviewSalesOrderRelation.objects.all()
    return queryset.filter(
        admission_chain_revocation__isnull=True,
    ).exclude(
        sales_order__status__in=("cancelled", "closed"),
    )


def active_pde_predecessors(queryset=None):
    queryset = queryset if queryset is not None else PDEReviewPredecessorRelation.objects.all()
    return queryset.filter(admission_chain_revocation__isnull=True)


def active_pde_authorizations(queryset=None):
    queryset = queryset if queryset is not None else PDEEngineeringPreparationAuthorization.objects.all()
    return queryset.filter(admission_chain_revocation__isnull=True)


def active_order_engineering_instances(queryset=None):
    queryset = queryset if queryset is not None else OrderEngineeringInstance.objects.all()
    return queryset.filter(
        admission_chain_revocation__isnull=True,
    ).exclude(
        status="inactive",
    ).exclude(
        sales_order_item__sales_order__status__in=("cancelled", "closed"),
    )


def _downstream_counts(*, order, item, engineering_instance):
    return {
        "productDesignItems": ProductDesignItem.objects.filter(
            sales_order_item=item,
        ).count(),
        "engineeringBaselines": OrderEngineeringBaseline.objects.filter(
            sales_order=order,
        ).count(),
        "engineeringCalculations": EngineeringCalculationRecord.objects.filter(
            Q(sales_order_item=item) | Q(engineering_instance=engineering_instance),
        ).distinct().count(),
        "productBoms": ProductBOM.objects.filter(
            order_engineering_instance=engineering_instance,
        ).count(),
        "routings": Routing.objects.filter(
            order_engineering_instance=engineering_instance,
        ).count(),
        "manufacturingOutputs": ProductManufacturingOutput.objects.filter(
            order_engineering_instance=engineering_instance,
        ).count(),
        "productionPlans": ProductionPlan.objects.filter(
            planning_requirement__demand__sales_order_item=item,
        ).count(),
    }


def _identity_snapshot(*, relation, pde_review, predecessor, authorization, instance,
                       development_order):
    order = relation.sales_order
    item = instance.sales_order_item
    source = pde_review.source_record
    return {
        "companyId": relation.company_id,
        "crmOrderRelationId": relation.pk,
        "crmReviewId": relation.review_id,
        "pdeReviewId": pde_review.pk,
        "predecessorRelationId": predecessor.pk,
        "authorizationId": authorization.pk,
        "engineeringInstanceId": instance.pk,
        "engineeringInstanceNo": instance.instance_no,
        "engineeringInstanceSourceState": instance.status,
        "engineeringInstanceTargetState": "inactive",
        "sourceRecordId": source.pk,
        "sourceVersion": source.source_version,
        "sourceContentHash": source.content_hash,
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "salesOrderItemId": item.pk,
        "customerId": order.customer_id,
        "customerName": order.customer.name,
        "projectReference": order.project_reference,
        "contractReference": order.contract_reference,
        "externalSourceNo": order.external_source_no,
        "developmentOrderId": development_order.pk,
        "developmentOrderNo": development_order.order_no,
        "developmentOrderAcceptanceMarker": development_order.acceptance_marker,
    }


def _replay_result(revocation):
    audit_reference = f"OrganizationOperatingAuditRecord:{revocation.audit_record_id}"
    transitions = BusinessStateTransition.objects.filter(
        object_type=OBJECT_TYPE,
        object_id=revocation.engineering_instance_id,
        source_state="draft",
        target_state="inactive",
        action_code=ACTION_CODE,
        audit_reference=audit_reference,
    )
    instance = revocation.engineering_instance
    if instance.status != "inactive" or transitions.count() != 1:
        raise PDEAdmissionChainRevocationError(
            "PDE_ADMISSION_REVOCATION_INCOMPLETE",
            "既有撤销事实未形成唯一OEI失效转换，禁止继续或重复写入。",
            details={
                "revocationId": revocation.pk,
                "engineeringInstanceId": instance.pk,
                "engineeringInstanceStatus": instance.status,
                "transitionCount": transitions.count(),
            },
        )
    transition = transitions.get()
    return {
        "revocationId": revocation.pk,
        "revocationNo": revocation.revocation_no,
        "idempotencyKey": revocation.idempotency_key,
        "organizationAuditId": revocation.audit_record_id,
        "businessStateTransitionId": transition.pk,
        "engineeringInstanceId": instance.pk,
        "engineeringInstanceStatus": instance.status,
        "chain": dict(revocation.identity_snapshot),
        "idempotent": True,
        "businessWriteCount": 0,
    }


@transaction.atomic
def revoke_pde_admission_chain(
    *, actor, authorized_by, relation_id, pde_review_id, predecessor_id,
    authorization_id, engineering_instance_id, expected_order_id,
    expected_development_order_id, expected_source_record_id,
    idempotency_key, reason,
):
    """Append one revocation fact and inactivate its OEI in one transaction."""

    key = str(idempotency_key or "").strip()
    reason = str(reason or "").strip()
    if not key:
        raise PDEAdmissionChainRevocationError(
            "IDEMPOTENCY_KEY_REQUIRED", "准入链纠正必须提供幂等键。",
        )
    if not reason:
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_REASON_REQUIRED", "准入链纠正必须提供明确原因。",
        )
    if len(reason) > 240:
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_REASON_TOO_LONG", "准入链纠正原因不得超过240个字符。",
        )
    if not actor or not authorized_by or actor.company_id != authorized_by.company_id:
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_ACTOR_SCOPE_INVALID", "纠正执行人和授权确认人必须属于同一公司。",
        )

    existing = PDEAdmissionChainRevocation.objects.select_for_update().select_related(
        "engineering_instance", "audit_record",
    ).filter(company_id=actor.company_id, idempotency_key=key).first()
    if existing:
        expected_ids = {
            "crm_order_relation_id": relation_id,
            "pde_review_id": pde_review_id,
            "predecessor_relation_id": predecessor_id,
            "authorization_id": authorization_id,
            "engineering_instance_id": engineering_instance_id,
        }
        mismatches = {
            field: {"expected": value, "actual": getattr(existing, field)}
            for field, value in expected_ids.items()
            if getattr(existing, field) != value
        }
        if mismatches:
            raise PDEAdmissionChainRevocationError(
                "IDEMPOTENCY_CONFLICT",
                "同一幂等键已经用于不同的准入链纠正事实。",
                details={"mismatches": mismatches},
            )
        return _replay_result(existing)

    relation = OrderReviewSalesOrderRelation.objects.select_for_update().select_related(
        "review__source_record", "sales_order__customer",
    ).filter(pk=relation_id, company_id=actor.company_id).first()
    pde_review = OrderCrossFunctionalReview.objects.select_for_update().select_related(
        "source_record",
    ).filter(
        pk=pde_review_id,
        company_id=actor.company_id,
        review_type="PDE_PRODUCTION_FEASIBILITY",
    ).first()
    predecessor = PDEReviewPredecessorRelation.objects.select_for_update().filter(
        pk=predecessor_id, company_id=actor.company_id,
    ).first()
    authorization = PDEEngineeringPreparationAuthorization.objects.select_for_update().filter(
        pk=authorization_id, company_id=actor.company_id,
    ).first()
    instance = OrderEngineeringInstance.objects.select_for_update().select_related(
        "sales_order_item__sales_order", "source_record",
    ).filter(pk=engineering_instance_id, company_id=actor.company_id).first()
    if not all((relation, pde_review, predecessor, authorization, instance)):
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_TARGET_NOT_FOUND",
            "目标0032、PDE评审、前置、授权或OEI不存在于当前公司。",
        )

    target_chain = {
        "predecessor.crm_order_relation_id": predecessor.crm_order_relation_id,
        "predecessor.pde_review_id": predecessor.pde_review_id,
        "authorization.predecessor_relation_id": authorization.predecessor_relation_id,
        "instance.engineering_preparation_authorization_id": (
            instance.engineering_preparation_authorization_id
        ),
    }
    expected_chain = {
        "predecessor.crm_order_relation_id": relation.pk,
        "predecessor.pde_review_id": pde_review.pk,
        "authorization.predecessor_relation_id": predecessor.pk,
        "instance.engineering_preparation_authorization_id": authorization.pk,
    }
    chain_mismatches = {
        field: {"expected": expected_chain[field], "actual": actual}
        for field, actual in target_chain.items()
        if actual != expected_chain[field]
    }
    if chain_mismatches:
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_CHAIN_MISMATCH",
            "目标记录没有组成唯一、连续的PDE准入冲突链。",
            details={"mismatches": chain_mismatches},
        )
    if pde_review.source_record_id != relation.review.source_record_id:
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_SOURCE_MISMATCH", "PDE评审与0032历史来源不一致。",
        )
    if instance.source_record_id != pde_review.source_record_id:
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_OEI_SOURCE_MISMATCH", "OEI与PDE评审历史来源不一致。",
        )
    if instance.sales_order_item.sales_order_id != relation.sales_order_id:
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_ORDER_MISMATCH", "OEI订单与0032历史订单不一致。",
        )
    if relation.sales_order_id != int(expected_order_id):
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_ORDER_IDENTITY_MISMATCH",
            "目标0032未指向授权纠正的正式销售订单。",
            details={
                "expectedOrderId": int(expected_order_id),
                "actualOrderId": relation.sales_order_id,
            },
        )
    if pde_review.source_record_id != int(expected_source_record_id):
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_SOURCE_ID_MISMATCH",
            "目标链未引用授权纠正的工程来源记录。",
            details={
                "expectedSourceRecordId": int(expected_source_record_id),
                "actualSourceRecordId": pde_review.source_record_id,
            },
        )
    development_order = SalesOrder.objects.select_for_update().filter(
        company_id=actor.company_id,
        pk=int(expected_development_order_id),
        acceptance_marker="DEVELOPMENT_ONLY",
    ).first()
    if not development_order:
        raise PDEAdmissionChainRevocationError(
            "DEVELOPMENT_ORDER_PROTECTION_FAILED",
            "受保护的DEVELOPMENT_ONLY订单不存在或身份标识已变化。",
            details={"expectedDevelopmentOrderId": int(expected_development_order_id)},
        )
    if instance.status != "draft":
        raise PDEAdmissionChainRevocationError(
            "OEI_DRAFT_REQUIRED",
            "本次最小纠正只允许将目标OEI从draft转换为inactive。",
            details={"engineeringInstanceId": instance.pk, "status": instance.status},
        )

    existing_target = PDEAdmissionChainRevocation.objects.select_for_update().filter(
        Q(crm_order_relation=relation)
        | Q(pde_review=pde_review)
        | Q(predecessor_relation=predecessor)
        | Q(authorization=authorization)
        | Q(engineering_instance=instance)
    ).first()
    if existing_target:
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_TARGET_ALREADY_RECORDED",
            "目标链已有另一条撤销事实，禁止形成第二套纠正结果。",
            details={"revocationId": existing_target.pk},
        )

    downstream_counts = _downstream_counts(
        order=relation.sales_order,
        item=instance.sales_order_item,
        engineering_instance=instance,
    )
    if any(downstream_counts.values()):
        raise PDEAdmissionChainRevocationError(
            "REVOCATION_DOWNSTREAM_FACTS_EXIST",
            "目标错误链已经形成下游正式对象，超出本次最小纠正授权范围。",
            details={"downstreamCounts": downstream_counts},
        )

    snapshot = _identity_snapshot(
        relation=relation,
        pde_review=pde_review,
        predecessor=predecessor,
        authorization=authorization,
        instance=instance,
        development_order=development_order,
    )
    effective_at = timezone.now()
    revocation_no = f"PDE-ACR-{relation.company_id}-{relation.pk:06d}"
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_CODE,
        actor=actor,
        organization_id=actor.company_id,
        target_type="PDEAdmissionChainRevocation",
        target_id=relation.pk,
        target_label=revocation_no,
        reason=reason,
        before_snapshot={
            "admissionChainState": "ACTIVE",
            "chain": snapshot,
            "downstreamCounts": downstream_counts,
        },
        after_snapshot={
            "admissionChainState": "REVOKED",
            "reasonCode": REASON_CODE,
            "engineeringInstanceStatus": "inactive",
            "chain": snapshot,
            "historicalObjectsDeleted": 0,
            "historicalObjectsRebound": 0,
        },
    )
    audit_hash = _canonical_hash({
        "revocationNo": revocation_no,
        "idempotencyKey": key,
        "reasonCode": REASON_CODE,
        "reason": reason,
        "identitySnapshot": snapshot,
        "organizationAuditId": audit.pk,
        "effectiveAt": effective_at.isoformat(),
    })
    revocation = PDEAdmissionChainRevocation.objects.create(
        company_id=actor.company_id,
        revocation_no=revocation_no,
        idempotency_key=key,
        crm_order_relation=relation,
        pde_review=pde_review,
        predecessor_relation=predecessor,
        authorization=authorization,
        engineering_instance=instance,
        reason_code=REASON_CODE,
        reason=reason,
        identity_snapshot=snapshot,
        authorized_by=authorized_by,
        created_by=actor,
        audit_record=audit,
        audit_hash=audit_hash,
        effective_at=effective_at,
    )
    audit_reference = f"OrganizationOperatingAuditRecord:{audit.pk}"
    try:
        transition = transition_business_object(
            business_object=instance,
            object_type=OBJECT_TYPE,
            source_state="draft",
            target_state="inactive",
            action_code=ACTION_CODE,
            operator=actor,
            reason=reason,
            audit_reference=audit_reference,
            workflow_instance=None,
            allowed_transitions={("draft", "inactive")},
            version_field=None,
        )
    except BusinessStateTransitionError as exc:
        raise PDEAdmissionChainRevocationError(
            "OEI_STATE_TRANSITION_FAILED",
            "目标OEI无法通过正式状态转换服务失效。",
            details={"error": str(exc)},
        ) from exc

    return {
        "revocationId": revocation.pk,
        "revocationNo": revocation.revocation_no,
        "idempotencyKey": key,
        "organizationAuditId": audit.pk,
        "businessStateTransitionId": transition.pk,
        "engineeringInstanceId": instance.pk,
        "engineeringInstanceStatus": "inactive",
        "chain": snapshot,
        "idempotent": False,
        "businessWriteCount": 3,
    }


__all__ = [
    "ACTION_CODE",
    "CURRENT_CHAIN_ABSENT_CODE",
    "CURRENT_CHAIN_ABSENT_MESSAGE",
    "PDEAdmissionChainRevocationError",
    "active_crm_order_relations",
    "active_order_engineering_instances",
    "active_pde_authorizations",
    "active_pde_predecessors",
    "revoke_pde_admission_chain",
]

