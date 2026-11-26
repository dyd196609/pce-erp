"""Server-authoritative PDE engineering-preparation admission chain.

The module persists the exact CRM predecessor selected by the P0 gate and the
exact PDE final-approval fact.  Downstream writes consume this immutable chain;
they never re-select a review by display ordering or a source string alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from django.db import transaction

from sales.models import SalesOrderItem
from workflow_runtime.models import ApprovalDecision, WorkflowInstance

from .crm_order_admission import CRMOrderAdmissionError, require_crm_order_admission
from .crm_sales_order_identity import assess_relation_identity
from .models import (
    OrderCrossFunctionalReview,
    OrderReviewSalesOrderRelation,
    PDEEngineeringPreparationAuthorization,
    PDEReviewPredecessorRelation,
)
from .admission_chain_revocation import (
    active_crm_order_relations,
    active_pde_authorizations,
    active_pde_predecessors,
)


class PDEEngineeringPreparationAdmissionError(ValueError):
    def __init__(self, code, message, *, details=None, http_status=409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status


@dataclass(frozen=True)
class PDEEngineeringPreparationAdmissionResult:
    authorization_id: int
    predecessor_relation_id: int
    pde_review_id: int
    pde_review_version: int
    crm_order_relation_id: int
    crm_review_id: int
    sales_order_id: int
    sales_order_item_id: int
    workflow_instance_id: int
    approval_decision_id: int

    def as_dict(self):
        return {
            "authorizationId": self.authorization_id,
            "predecessorRelationId": self.predecessor_relation_id,
            "pdeReviewId": self.pde_review_id,
            "pdeReviewVersion": self.pde_review_version,
            "crmOrderRelationId": self.crm_order_relation_id,
            "crmReviewId": self.crm_review_id,
            "salesOrderId": self.sales_order_id,
            "salesOrderItemId": self.sales_order_item_id,
            "workflowInstanceId": self.workflow_instance_id,
            "approvalDecisionId": self.approval_decision_id,
            "admitted": True,
        }


def _hash(payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _scope_identity_hash(relation):
    rows = list(
        relation.scope_items.order_by("line_no_snapshot", "sales_order_item_id").values(
            "sales_order_item_id",
            "line_no_snapshot",
            "external_line_no_snapshot",
            "item_identity_hash",
        )
    )
    if not rows:
        raise PDEEngineeringPreparationAdmissionError(
            "CRM_ORDER_REVIEW_SCOPE_EMPTY",
            "CRM订单评审正式关系没有订单行范围，已阻断PDE工程准备。",
            details={"crmOrderRelationId": relation.pk},
        )
    return _hash({
        "crmOrderRelationId": relation.pk,
        "salesOrderId": relation.sales_order_id,
        "scopeMode": relation.scope_mode,
        "orderVersion": relation.order_version_snapshot,
        "items": rows,
    })


def _crm_gate_for_relation(relation, *, lock=False):
    review = relation.review
    try:
        result = require_crm_order_admission(
            company_id=relation.company_id,
            source_record_id=review.source_record_id,
            source_order_no=review.source_order_no,
            source_version=review.source_version,
            lock=lock,
        )
    except CRMOrderAdmissionError as exc:
        raise PDEEngineeringPreparationAdmissionError(
            exc.code, exc.message, details=exc.details, http_status=exc.http_status,
        ) from exc
    if result.review_id != relation.review_id or result.review_version != review.review_version:
        raise PDEEngineeringPreparationAdmissionError(
            "CRM_ORDER_REVIEW_PREDECESSOR_SUPERSEDED",
            "CRM准入Gate返回的评审版本与已固化正式前置不一致，已失败关闭。",
            details={
                "expectedReviewId": relation.review_id,
                "actualReviewId": result.review_id,
            },
        )
    identity = assess_relation_identity(relation)
    if not identity["allowed"]:
        raise PDEEngineeringPreparationAdmissionError(
            "CRM_SALES_ORDER_BUSINESS_IDENTITY_INVALID",
            "0032关系的CRM来源与正式销售订单业务身份不一致或证明不完整；当前关系只读保留，禁止继续下游准入。",
            details={"businessIdentity": identity},
            http_status=409,
        )
    return result


def _validate_predecessor(predecessor, *, lock=False):
    review = predecessor.pde_review
    relation = predecessor.crm_order_relation
    if (
        hasattr(predecessor, "admission_chain_revocation")
        or hasattr(relation, "admission_chain_revocation")
    ):
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_ADMISSION_CHAIN_REVOKED",
            "该PDE准入链已正式撤销，仅保留历史审计，禁止继续消费。",
            details={
                "predecessorRelationId": predecessor.pk,
                "crmOrderRelationId": relation.pk,
            },
        )
    if review.review_type != "PDE_PRODUCTION_FEASIBILITY":
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_REVIEW_TYPE_INVALID", "正式前置未指向PDE生产可行性评审。",
        )
    if relation.scope_mode == "UNRESOLVED":
        raise PDEEngineeringPreparationAdmissionError(
            "CRM_ORDER_REVIEW_SCOPE_UNRESOLVED", "未解析的历史订单范围不能授权PDE工程准备。",
        )
    if not (
        predecessor.company_id == review.company_id == relation.company_id
        and review.source_record_id == relation.review.source_record_id
        and review.source_version == relation.review.source_version
        and review.source_content_hash == relation.review.source_content_hash
        and predecessor.crm_review_version_snapshot == relation.review.review_version
        and predecessor.pde_review_version_snapshot == review.review_version
        and predecessor.order_version_snapshot == relation.order_version_snapshot
        and predecessor.source_content_hash_snapshot == review.source_content_hash
    ):
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_REVIEW_PREDECESSOR_FACT_MISMATCH",
            "PDE评审与CRM正式前置快照不一致，已失败关闭。",
            details={"predecessorRelationId": predecessor.pk},
        )
    scope_hash = _scope_identity_hash(relation)
    if scope_hash != predecessor.scope_identity_hash_snapshot:
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_REVIEW_SCOPE_CHANGED", "订单评审范围与已固化PDE前置快照不一致。",
        )
    _crm_gate_for_relation(relation, lock=lock)
    return scope_hash


def require_pde_review_predecessor_relation(*, pde_review, lock=False):
    """Validate an already-persisted predecessor without creating/backfilling one."""
    queryset = PDEReviewPredecessorRelation.objects.select_related(
        "pde_review", "crm_order_relation__review", "crm_order_relation__sales_order",
    )
    if lock:
        queryset = queryset.select_for_update()
    predecessor = queryset.filter(pde_review_id=pde_review.pk).first()
    if not predecessor:
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_REVIEW_PREDECESSOR_REQUIRED",
            "PDE评审缺少创建时固化的正式CRM前置关系；禁止自动回填。",
        )
    _validate_predecessor(predecessor, lock=lock)
    return predecessor


@transaction.atomic
def create_pde_review_predecessor_relation(
    *, pde_review, user, crm_order_relation_id=None,
):
    """Persist the exact CRM 0032 relation when a new PDE review is created."""
    review = OrderCrossFunctionalReview.objects.select_for_update().get(pk=pde_review.pk)
    if review.review_type != "PDE_PRODUCTION_FEASIBILITY":
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_REVIEW_TYPE_INVALID", "只有PDE生产可行性评审可以建立正式前置。",
        )
    relations = active_crm_order_relations(
        OrderReviewSalesOrderRelation.objects.select_for_update().select_related(
            "review__source_record", "sales_order",
        )
    ).filter(
        company_id=review.company_id,
        review__source_record_id=review.source_record_id,
    )
    if crm_order_relation_id not in (None, ""):
        try:
            relation_id = int(crm_order_relation_id)
        except (TypeError, ValueError) as exc:
            raise PDEEngineeringPreparationAdmissionError(
                "CRM_ORDER_FORMAL_RELATION_ID_INVALID",
                "0032正式订单关系标识无效。",
                http_status=400,
            ) from exc
        relations = relations.filter(pk=relation_id)
    else:
        # New formal PDE reviews carry the SalesOrder number as their display
        # identity.  Historical reviews carried the CRM source order number.
        # Resolve either identity deterministically, but never choose between
        # multiple 0032 rows merely by insertion order.
        order_matches = relations.filter(
            sales_order__order_no=review.source_order_no,
        )
        if order_matches.exists():
            relations = order_matches
        else:
            legacy_matches = relations.filter(
                review__source_order_no=review.source_order_no,
            )
            if legacy_matches.exists():
                try:
                    gate = require_crm_order_admission(
                        company_id=review.company_id,
                        source_record_id=review.source_record_id,
                        source_order_no=review.source_order_no,
                        source_version=review.source_version,
                        lock=True,
                    )
                except CRMOrderAdmissionError as exc:
                    raise PDEEngineeringPreparationAdmissionError(
                        exc.code, exc.message,
                        details=exc.details, http_status=exc.http_status,
                    ) from exc
                relations = legacy_matches.filter(review_id=gate.review_id)
    candidates = list(relations.order_by("pk")[:2])
    if not candidates:
        raise PDEEngineeringPreparationAdmissionError(
            "CRM_ORDER_FORMAL_RELATION_REQUIRED",
            "CRM评审尚未形成0032正式订单关系，禁止创建PDE评审。",
            details={"sourceRecordId": review.source_record_id},
        )
    if len(candidates) != 1:
        raise PDEEngineeringPreparationAdmissionError(
            "CRM_ORDER_FORMAL_RELATION_NOT_UNIQUE",
            "PDE评审无法唯一解析0032正式订单关系，已失败关闭。",
            details={"candidateCount": len(candidates)},
        )
    relation = candidates[0]
    if relation.scope_mode == "UNRESOLVED":
        raise PDEEngineeringPreparationAdmissionError(
            "CRM_ORDER_REVIEW_SCOPE_UNRESOLVED", "未解析的历史订单范围不能形成在线PDE前置。",
        )
    scope_hash = _scope_identity_hash(relation)
    crm_result = _crm_gate_for_relation(relation, lock=True)
    if not (
        review.source_record_id == relation.review.source_record_id
        and review.source_version == relation.review.source_version
        and review.source_content_hash == relation.review.source_content_hash
        and review.source_order_no in {
            relation.sales_order.order_no,
            relation.review.source_order_no,
        }
    ):
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_REVIEW_FORMAL_CONTEXT_MISMATCH",
            "PDE评审与0032绑定的订单、CRM评审或来源版本不一致。",
        )
    existing = active_pde_predecessors(
        PDEReviewPredecessorRelation.objects.select_for_update()
    ).filter(pde_review=review).first()
    expected = {
        "company_id": review.company_id,
        "crm_order_relation_id": relation.pk,
        "crm_review_version_snapshot": crm_result.review_version,
        "pde_review_version_snapshot": review.review_version,
        "order_version_snapshot": relation.order_version_snapshot,
        "source_content_hash_snapshot": review.source_content_hash,
        "scope_identity_hash_snapshot": scope_hash,
        "resolution_basis": "RUNTIME_GATE",
    }
    if existing:
        if any(getattr(existing, field) != value for field, value in expected.items()):
            raise PDEEngineeringPreparationAdmissionError(
                "PDE_REVIEW_PREDECESSOR_CONFLICT", "PDE评审已存在不一致的正式前置关系。",
            )
        return existing
    audit = {
        "pdeReviewId": review.pk,
        "pdeReviewVersion": review.review_version,
        "crmOrderRelationId": relation.pk,
        "crmReviewId": relation.review_id,
        "scopeIdentityHash": scope_hash,
    }
    return PDEReviewPredecessorRelation.objects.create(
        pde_review=review,
        created_by=user,
        audit_hash=_hash(audit),
        **expected,
    )


@transaction.atomic
def create_pde_engineering_preparation_authorization(
    *, pde_review, workflow_instance, approval_decision, user,
):
    """Persist authorization in the same transaction as PDE final approval."""
    review = OrderCrossFunctionalReview.objects.select_for_update().get(pk=pde_review.pk)
    predecessor = active_pde_predecessors(
        PDEReviewPredecessorRelation.objects.select_for_update().select_related(
            "pde_review", "crm_order_relation__review", "crm_order_relation__sales_order",
        )
    ).filter(pde_review=review).first()
    if not predecessor:
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_REVIEW_PREDECESSOR_REQUIRED", "PDE评审缺少正式CRM前置关系，禁止批准工程准备。",
        )
    scope_hash = _validate_predecessor(predecessor, lock=True)
    if review.record_status != "SUBMITTED" or review.conclusion in {
        "REJECT", "RETURN_FOR_COMPLETION", "CONDITIONAL",
    }:
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_REVIEW_NOT_ADMISSIBLE", "PDE评审状态或结论不允许形成工程准备授权。",
        )
    workflow = WorkflowInstance.objects.select_for_update().get(pk=workflow_instance.pk)
    decision = ApprovalDecision.objects.select_for_update().select_related(
        "task__workflow_instance",
    ).get(pk=approval_decision.pk)
    if not (
        workflow.document_type == "PDEProductionFeasibilityReview"
        and workflow.document_id == review.pk
        and workflow.status == WorkflowInstance.Status.APPROVED
        and decision.task.workflow_instance_id == workflow.pk
        and decision.decision == "approved"
    ):
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_FINAL_APPROVAL_FACT_INVALID", "PDE最终审批事实不完整或不一致。",
        )
    existing = active_pde_authorizations(
        PDEEngineeringPreparationAuthorization.objects.select_for_update()
    ).filter(predecessor_relation=predecessor).first()
    expected = {
        "company_id": review.company_id,
        "workflow_instance_id": workflow.pk,
        "approval_decision_id": decision.pk,
        "pde_review_version_snapshot": review.review_version,
        "pde_review_content_hash_snapshot": review.source_content_hash,
        "order_version_snapshot": predecessor.order_version_snapshot,
        "scope_identity_hash_snapshot": scope_hash,
        "authorization_basis": "FINAL_APPROVAL",
    }
    if existing:
        if any(getattr(existing, field) != value for field, value in expected.items()):
            raise PDEEngineeringPreparationAdmissionError(
                "PDE_ENGINEERING_AUTHORIZATION_CONFLICT",
                "PDE评审已存在不一致的工程准备授权。",
            )
        return existing
    return PDEEngineeringPreparationAuthorization.objects.create(
        predecessor_relation=predecessor,
        created_by=user,
        audit_hash=_hash({
            "predecessorRelationId": predecessor.pk,
            "workflowInstanceId": workflow.pk,
            "approvalDecisionId": decision.pk,
            "scopeIdentityHash": scope_hash,
        }),
        **expected,
    )


def _authorization_queryset(*, lock=False):
    queryset = active_pde_authorizations(
        PDEEngineeringPreparationAuthorization.objects.select_related(
        "predecessor_relation__pde_review",
        "predecessor_relation__crm_order_relation__review",
        "predecessor_relation__crm_order_relation__sales_order",
        "workflow_instance",
        "approval_decision__task__workflow_instance",
        )
    )
    return queryset.select_for_update() if lock else queryset


def require_pde_engineering_preparation_admission(
    *, company_id, sales_order_item_id, authorization_id=None, lock=False,
):
    """Return one exact authorization for a scoped order line or fail closed."""
    items = SalesOrderItem.objects.select_related("sales_order")
    if lock:
        items = items.select_for_update()
    item = items.filter(pk=sales_order_item_id, sales_order__company_id=company_id).first()
    if not item:
        raise PDEEngineeringPreparationAdmissionError(
            "SALES_ORDER_ITEM_CONTEXT_NOT_FOUND", "销售订单行与企业上下文不一致。",
        )
    queryset = _authorization_queryset(lock=lock).filter(company_id=company_id)
    if authorization_id is not None and str(authorization_id).strip():
        try:
            authorization_id = int(authorization_id)
        except (TypeError, ValueError) as exc:
            raise PDEEngineeringPreparationAdmissionError(
                "PDE_ENGINEERING_AUTHORIZATION_ID_INVALID", "工程准备授权标识无效。",
            ) from exc
        revoked = PDEEngineeringPreparationAuthorization.objects.filter(
            pk=authorization_id,
            company_id=company_id,
            admission_chain_revocation__isnull=False,
        ).first()
        if revoked:
            raise PDEEngineeringPreparationAdmissionError(
                "PDE_ADMISSION_CHAIN_REVOKED",
                "指定的PDE工程准备授权已随冲突链正式撤销，禁止继续消费。",
                details={"authorizationId": revoked.pk},
            )
        candidates = list(queryset.filter(pk=authorization_id)[:2])
    else:
        candidates = list(queryset.filter(
            predecessor_relation__crm_order_relation__scope_items__sales_order_item=item,
        ).distinct()[:2])
    if len(candidates) != 1:
        revoked_ids = list(
            PDEEngineeringPreparationAuthorization.objects.filter(
                company_id=company_id,
                admission_chain_revocation__isnull=False,
                predecessor_relation__crm_order_relation__scope_items__sales_order_item=item,
            ).values_list("pk", flat=True).distinct()[:2]
        )
        if not candidates and revoked_ids:
            raise PDEEngineeringPreparationAdmissionError(
                "PDE_ADMISSION_CHAIN_REVOKED",
                "该订单行的PDE准入链已正式撤销，仅保留历史审计，禁止继续消费。",
                details={
                    "salesOrderItemId": item.pk,
                    "revokedAuthorizationIds": revoked_ids,
                },
            )
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_ENGINEERING_AUTHORIZATION_NOT_UNIQUE",
            ("订单行尚无有效PDE工程准备授权，请先完成生产可行性评审及授权。"
             if not candidates else "订单行存在多条有效PDE工程准备授权，请核定适用授权后继续。"),
            details={"salesOrderItemId": item.pk, "candidateCount": len(candidates)},
        )
    authorization = candidates[0]
    predecessor = authorization.predecessor_relation
    relation = predecessor.crm_order_relation
    scope_hash = _validate_predecessor(predecessor, lock=lock)
    if not relation.scope_items.filter(sales_order_item=item).exists():
        raise PDEEngineeringPreparationAdmissionError(
            "SALES_ORDER_ITEM_OUT_OF_REVIEW_SCOPE", "销售订单行不属于已批准评审范围。",
        )
    review = predecessor.pde_review
    workflow = authorization.workflow_instance
    decision = authorization.approval_decision
    if not (
        relation.sales_order_id == item.sales_order_id
        and authorization.company_id == item.sales_order.company_id
        and review.record_status == "SUBMITTED"
        and review.conclusion not in {"REJECT", "RETURN_FOR_COMPLETION", "CONDITIONAL"}
        and workflow.document_type == "PDEProductionFeasibilityReview"
        and workflow.document_id == review.pk
        and workflow.status == WorkflowInstance.Status.APPROVED
        and decision.task.workflow_instance_id == workflow.pk
        and decision.decision == "approved"
        and authorization.pde_review_version_snapshot == review.review_version
        and authorization.pde_review_content_hash_snapshot == review.source_content_hash
        and authorization.order_version_snapshot == relation.order_version_snapshot
        and authorization.scope_identity_hash_snapshot == scope_hash
    ):
        raise PDEEngineeringPreparationAdmissionError(
            "PDE_ENGINEERING_AUTHORIZATION_FACT_MISMATCH",
            "PDE工程准备授权事实与当前正式关系不一致。",
        )
    return PDEEngineeringPreparationAdmissionResult(
        authorization_id=authorization.pk,
        predecessor_relation_id=predecessor.pk,
        pde_review_id=review.pk,
        pde_review_version=review.review_version,
        crm_order_relation_id=relation.pk,
        crm_review_id=relation.review_id,
        sales_order_id=relation.sales_order_id,
        sales_order_item_id=item.pk,
        workflow_instance_id=workflow.pk,
        approval_decision_id=decision.pk,
    )

