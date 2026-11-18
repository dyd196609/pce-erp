"""Controlled removal of a stale current CRM source context from SalesOrder.

Historical Source, Review, Relation and Revocation records are never changed.
The SalesOrder row lock serializes correction attempts; the audit fact makes an
identical replay observable and write-free without adding schema.
"""

from __future__ import annotations

from copy import deepcopy

from django.db import transaction

from pde.models import (
    EngineeringSourceRecord,
    OrderCrossFunctionalReview,
    OrderReviewSalesOrderRelation,
    PDEAdmissionChainRevocation,
)
from system.models import OrganizationOperatingAuditRecord

from .models import SalesOrder


ACTION_CODE = "sales.order.crm_source_context.correct"
SOURCE_CONTEXT_KEYS = ("sourceRecordId", "sourceVersion", "sourceContentHash")


class SalesOrderCRMSourceCorrectionError(ValueError):
    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _source_context(order):
    delivery = (
        order.delivery_information
        if isinstance(order.delivery_information, dict) else {}
    )
    return {
        "externalSourceNo": order.external_source_no,
        "sourceRecordId": delivery.get("sourceRecordId"),
        "sourceVersion": delivery.get("sourceVersion"),
        "sourceContentHash": delivery.get("sourceContentHash"),
    }


def _matching_audit(*, order, idempotency_key):
    audits = OrganizationOperatingAuditRecord.objects.filter(
        action_code=ACTION_CODE,
        organization_id=order.company_id,
        target_type="SalesOrder",
        target_id=order.pk,
    ).order_by("pk")
    matches = [
        audit for audit in audits
        if (audit.after_snapshot or {}).get("idempotencyKey") == idempotency_key
    ]
    if len(matches) > 1:
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_AUDIT_AMBIGUOUS",
            "同一销售订单来源纠正幂等键存在多条审计记录，禁止继续写入。",
            details={"auditIds": [audit.pk for audit in matches]},
        )
    return matches[0] if matches else None


def _replay_result(*, order, audit, idempotency_key):
    current = _source_context(order)
    expected = (audit.after_snapshot or {}).get("currentSourceContext") or {}
    if current != expected:
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_REPLAY_MISMATCH",
            "既有纠正审计与销售订单当前来源事实不一致，禁止继续或重复写入。",
            details={"current": current, "auditedAfter": expected},
        )
    return {
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "idempotencyKey": idempotency_key,
        "organizationAuditId": audit.pk,
        "before": (audit.before_snapshot or {}).get("currentSourceContext") or {},
        "after": current,
        "idempotent": True,
        "businessWriteCount": 0,
        "businessStateTransitionCount": 0,
    }


@transaction.atomic
def correct_sales_order_crm_source_context(
    *, actor, order_id, expected_order_no, expected_source_record_id,
    expected_source_version, expected_external_source_no, expected_relation_id,
    expected_revocation_id, idempotency_key, reason,
):
    """Clear only the proven stale current-source references, with one audit."""

    key = str(idempotency_key or "").strip()
    reason = str(reason or "").strip()
    if not key:
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_IDEMPOTENCY_REQUIRED",
            "销售订单来源纠正必须提供幂等键。",
        )
    if not reason:
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_REASON_REQUIRED",
            "销售订单来源纠正必须提供明确原因。",
        )

    order = SalesOrder.objects.select_for_update().select_related(
        "customer",
    ).filter(pk=order_id).first()
    if not order:
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_ORDER_NOT_FOUND",
            "未找到授权纠正的销售订单。",
            details={"salesOrderId": order_id},
        )
    if actor.company_id != order.company_id:
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_COMPANY_MISMATCH",
            "纠正执行人与销售订单不属于同一公司。",
        )

    existing = _matching_audit(order=order, idempotency_key=key)
    if existing:
        return _replay_result(
            order=order,
            audit=existing,
            idempotency_key=key,
        )

    other_audits = OrganizationOperatingAuditRecord.objects.filter(
        action_code=ACTION_CODE,
        organization_id=order.company_id,
        target_type="SalesOrder",
        target_id=order.pk,
    )
    if other_audits.exists():
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_ALREADY_RECORDED",
            "该销售订单已有不同幂等键的来源纠正审计，禁止形成第二套纠正结果。",
            details={"auditIds": list(other_audits.values_list("pk", flat=True))},
        )

    if order.order_no != expected_order_no or order.status != "draft":
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_TARGET_MISMATCH",
            "销售订单编号或状态已变化，超出本次最小纠正授权范围。",
            details={
                "salesOrderId": order.pk,
                "orderNo": order.order_no,
                "status": order.status,
            },
        )

    relation = OrderReviewSalesOrderRelation.objects.select_for_update().select_related(
        "review__source_record",
    ).filter(
        pk=expected_relation_id,
        company_id=order.company_id,
        sales_order_id=order.pk,
    ).first()
    revocation = PDEAdmissionChainRevocation.objects.select_for_update().filter(
        pk=expected_revocation_id,
        company_id=order.company_id,
        crm_order_relation_id=expected_relation_id,
    ).first()
    if not relation or not revocation:
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_REVOCATION_REQUIRED",
            "目标遗留来源没有对应的正式关系与链级撤销事实，禁止解除引用。",
            details={
                "relationId": expected_relation_id,
                "revocationId": expected_revocation_id,
            },
        )
    review = relation.review
    source = review.source_record
    if (
        source.pk != expected_source_record_id
        or source.source_version != expected_source_version
    ):
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_SOURCE_MISMATCH",
            "历史关系指向的来源与授权目标不一致，禁止解除引用。",
            details={
                "sourceRecordId": source.pk,
                "sourceVersion": source.source_version,
            },
        )

    before_context = _source_context(order)
    if (
        before_context["externalSourceNo"] != expected_external_source_no
        or before_context["sourceRecordId"] != expected_source_record_id
        or before_context["sourceVersion"] != expected_source_version
    ):
        raise SalesOrderCRMSourceCorrectionError(
            "CRM_SOURCE_CORRECTION_STALE_CONTEXT_MISMATCH",
            "销售订单当前来源上下文不再等于已授权纠正目标，禁止继续写入。",
            details={"currentSourceContext": before_context},
        )

    delivery_after = deepcopy(order.delivery_information)
    for field in SOURCE_CONTEXT_KEYS:
        delivery_after.pop(field, None)
    protected_identity = {
        "customerId": order.customer_id,
        "customerName": order.customer.name,
        "projectReference": order.project_reference,
        "contractReference": order.contract_reference,
        "status": order.status,
    }
    version_before = order.version
    order.external_source_no = ""
    order.delivery_information = delivery_after
    order.version += 1
    order.save(update_fields=[
        "external_source_no", "delivery_information", "version", "updated_at",
    ])
    after_context = _source_context(order)

    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_CODE,
        actor=actor,
        organization_id=order.company_id,
        target_type="SalesOrder",
        target_id=order.pk,
        target_label=order.order_no,
        reason=reason,
        before_snapshot={
            "currentSourceContext": before_context,
            "orderVersion": version_before,
            "protectedOrderIdentity": protected_identity,
            "historicalRelation": {
                "relationId": relation.pk,
                "reviewId": review.pk,
                "sourceRecordId": source.pk,
                "sourceVersion": source.source_version,
                "revocationId": revocation.pk,
                "revocationNo": revocation.revocation_no,
            },
        },
        after_snapshot={
            "currentSourceContext": after_context,
            "orderVersion": order.version,
            "protectedOrderIdentity": protected_identity,
            "idempotencyKey": key,
            "historicalObjectsDeleted": 0,
            "historicalObjectsModified": 0,
            "businessStateTransitionCount": 0,
        },
    )
    return {
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "idempotencyKey": key,
        "organizationAuditId": audit.pk,
        "before": before_context,
        "after": after_context,
        "idempotent": False,
        "businessWriteCount": 2,
        "businessStateTransitionCount": 0,
    }


