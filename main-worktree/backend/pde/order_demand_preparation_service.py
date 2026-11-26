"""Server-authoritative CRM order -> PDE demand/preparation bridge.

This module deliberately stops before product design.  It persists customer
requirements in the existing ProductRequirement authority and projects the
engineering-preparation state from the formal SalesOrder, source record and
approved PDE review.  No BOM, routing, manufacturing output, MRP or downstream
execution object is created here.
"""

from __future__ import annotations

from hashlib import sha256
import json

from django.db import transaction

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from sales.models import SalesOrder
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import ApprovalDecision, WorkflowInstance

from .models import (
    EngineeringSourceRecord, OrderCrossFunctionalReview, ProductDesignItem,
    OrderReviewSalesOrderRelation, OrderReviewScopeItem,
    PDEAdmissionChainRevocation, PDEEngineeringPreparationAuthorization,
    PDEReviewPredecessorRelation,
    ProductRequirement,
)
from .admission_chain_revocation import (
    CURRENT_CHAIN_ABSENT_CODE,
    CURRENT_CHAIN_ABSENT_MESSAGE,
    active_crm_order_relations,
    active_pde_authorizations,
    active_pde_predecessors,
)
from .crm_order_admission import CRMOrderAdmissionError, require_crm_order_admission
from .pde_engineering_preparation_admission import (
    PDEEngineeringPreparationAdmissionError,
    require_pde_engineering_preparation_admission,
)


ACTION_CODE = "pde.order_demand.prepare"
SOURCE_SYSTEM = "PCE_SALES_ORDER"
SOURCE_TYPE = "ORDER_DEMAND_PREPARATION"
SOURCE_OBJECT_TYPE = "SALES_ORDER"
PDE_PREDECESSOR_PENDING_MESSAGE = (
    "当前订单具备0032前置关系，但尚未形成新的PDE工程准备关系。"
)


class OrderDemandPreparationError(ValueError):
    def __init__(self, code, message, http_status=400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def _canonical_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _authorization(user):
    decision = AuthorizationService.decide(
        user=user,
        action_code="production.engineering.readiness.maintain",
        organization_id=user.company_id,
        business_object={"organizationId": user.company_id},
        context={"actionType": "ORDER_DEMAND_PREPARATION", "businessWrite": True},
    )
    if not decision.get("allowed"):
        raise OrderDemandPreparationError(
            decision.get("decisionCode", "PERMISSION_DENIED"),
            decision.get("reason", "当前账户没有工程准备维护权限。"),
            403,
        )
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    if not employee or employee.status != "active" or not position or not position.is_active:
        raise OrderDemandPreparationError(
            "PDE_PREPARATION_ACTOR_REQUIRED",
            "工程准备账户必须关联在职员工和正式岗位。",
            409,
        )
    return decision, employee, position


def _selector_id(value, field_name):
    if value is None or str(value).strip() == "":
        return None
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise OrderDemandPreparationError(
            "PDE_PREPARATION_SELECTOR_INVALID",
            "PDE工程准备承接标识无效。",
            400,
            {field_name: value},
        ) from exc
    if value <= 0:
        raise OrderDemandPreparationError(
            "PDE_PREPARATION_SELECTOR_INVALID",
            "PDE工程准备承接标识必须为正整数。",
            400,
            {field_name: value},
        )
    return value


def _has_version_carry_forward(relation, order):
    from .crm_order_version_carry_forward import CarryForwardError, matching_proof
    relation.sales_order = order
    try:
        return matching_proof(relation) is not None
    except CarryForwardError:
        return False


def _resolve_formal_preparation_context(
    company_id, *, crm_order_relation_id=None, sales_order_id=None, lock=False,
):
    """Resolve the current PDE intake context from the immutable 0032 relation.

    This is deliberately read-only.  In particular it never creates a PDE
    review, predecessor, authorization, OEI, or a compatibility backfill.
    """

    relation_id = _selector_id(crm_order_relation_id, "crmOrderRelationId")
    order_id = _selector_id(sales_order_id, "salesOrderId")
    relations = active_crm_order_relations(
        OrderReviewSalesOrderRelation.objects.select_related(
            "review__source_record", "sales_order__customer", "sales_order__sales_owner",
        )
    ).filter(company_id=company_id)
    if relation_id is not None:
        relations = relations.filter(pk=relation_id)
    if order_id is not None:
        relations = relations.filter(sales_order_id=order_id)
    if lock:
        relations = relations.select_for_update()
    candidates = list(relations.order_by("pk")[:2])
    if not candidates:
        raise OrderDemandPreparationError(
            "CRM_ORDER_FORMAL_RELATION_REQUIRED",
            "当前企业没有可用于PDE工程准备承接的0032正式订单关系。",
            409,
            {
                "crmOrderRelationId": relation_id,
                "salesOrderId": order_id,
            },
        )
    if len(candidates) != 1:
        raise OrderDemandPreparationError(
            "CRM_ORDER_FORMAL_RELATION_NOT_UNIQUE",
            "PDE工程准备承接无法唯一解析0032正式订单关系，请明确订单或关系标识。",
            409,
            {"candidateCount": len(candidates)},
        )

    relation = candidates[0]
    review = relation.review
    source = review.source_record
    orders = SalesOrder.objects.select_related("customer", "sales_owner")
    if lock:
        orders = orders.select_for_update()
    order = orders.get(pk=relation.sales_order_id)

    try:
        crm_admission = require_crm_order_admission(
            company_id=company_id,
            source_record_id=source.pk,
            source_order_no=review.source_order_no,
            source_version=review.source_version,
            lock=lock,
        )
    except CRMOrderAdmissionError as exc:
        raise OrderDemandPreparationError(
            exc.code, exc.message, exc.http_status,
            {"crmOrderAdmission": exc.details},
        ) from exc

    if not (
        relation.company_id == review.company_id == source.company_id == order.company_id == company_id
        and review.review_type == "CRM_ORDER_REVIEW"
        and review.record_status == "SUBMITTED"
        and crm_admission.review_id == review.pk
        and crm_admission.review_version == review.review_version
        and review.source_version == source.source_version
        and review.source_content_hash.lower() == source.content_hash.lower()
        and relation.source_content_hash_snapshot.lower() == source.content_hash.lower()
        and (
            relation.order_version_snapshot == order.version
            or _has_version_carry_forward(relation, order)
        )
    ):
        raise OrderDemandPreparationError(
            "PDE_PREPARATION_CONTEXT_MISMATCH",
            "0032、SalesOrder、CRM评审与来源版本/内容哈希不一致，已失败关闭。",
            409,
            {
                "crmOrderRelationId": relation.pk,
                "salesOrderId": order.pk,
                "crmReviewId": review.pk,
                "sourceRecordId": source.pk,
            },
        )
    if relation.scope_mode == "UNRESOLVED":
        raise OrderDemandPreparationError(
            "CRM_ORDER_REVIEW_SCOPE_UNRESOLVED",
            "0032评审范围尚未解析，不能形成PDE工程准备上下文。",
            409,
            {"crmOrderRelationId": relation.pk},
        )

    scope_rows = OrderReviewScopeItem.objects.select_related(
        "sales_order_item__material", "sales_order_item__uom",
    ).filter(relation=relation).order_by("line_no_snapshot", "sales_order_item_id")
    if lock:
        scope_rows = scope_rows.select_for_update()
    scope_rows = list(scope_rows)
    if not scope_rows:
        raise OrderDemandPreparationError(
            "CRM_ORDER_REVIEW_SCOPE_EMPTY",
            "0032正式关系没有订单行范围，不能形成PDE工程准备上下文。",
            409,
            {"crmOrderRelationId": relation.pk},
        )

    order_items = order.items.select_related("material", "uom").order_by("line_no", "pk")
    if lock:
        order_items = order_items.select_for_update()
    order_items = list(order_items)
    order_item_ids = {item.pk for item in order_items}
    scope_item_ids = {row.sales_order_item_id for row in scope_rows}
    snapshots_match = all(
        row.sales_order_item.sales_order_id == order.pk
        and row.line_no_snapshot == row.sales_order_item.line_no
        and row.external_line_no_snapshot == row.sales_order_item.external_line_no
        for row in scope_rows
    )
    scope_matches = (
        scope_item_ids == order_item_ids
        if relation.scope_mode == "WHOLE_ORDER"
        else scope_item_ids.issubset(order_item_ids) and bool(relation.scope_reason.strip())
    )
    if relation.scope_mode not in {"WHOLE_ORDER", "SELECTED_ITEMS"} or not snapshots_match or not scope_matches:
        raise OrderDemandPreparationError(
            "CRM_ORDER_REVIEW_SCOPE_MISMATCH",
            "0032订单范围与当前SalesOrderItem事实不一致，已失败关闭。",
            409,
            {
                "crmOrderRelationId": relation.pk,
                "scopeMode": relation.scope_mode,
                "scopeItemIds": sorted(scope_item_ids),
                "salesOrderItemIds": sorted(order_item_ids),
            },
        )

    predecessors = active_pde_predecessors(
        PDEReviewPredecessorRelation.objects.select_related("pde_review")
    ).filter(company_id=company_id, crm_order_relation=relation)
    if lock:
        predecessors = predecessors.select_for_update()
    predecessors = list(predecessors.order_by("pk")[:2])
    if not predecessors:
        status_code = "PDE_REVIEW_PREDECESSOR_PENDING"
        status_message = PDE_PREDECESSOR_PENDING_MESSAGE
    elif len(predecessors) == 1:
        status_code = "PDE_REVIEW_PREDECESSOR_ESTABLISHED"
        status_message = "当前订单已形成PDE工程准备正式前置关系。"
    else:
        status_code = "PDE_REVIEW_PREDECESSOR_NOT_UNIQUE"
        status_message = "当前0032关系对应多个PDE工程准备前置，已失败关闭。"

    return {
        "relation": relation,
        "crm_review": review,
        "crm_admission": crm_admission,
        "order": order,
        "source": source,
        "scope_rows": tuple(scope_rows),
        "scope_items": tuple(row.sales_order_item for row in scope_rows),
        "predecessors": tuple(predecessors),
        "predecessor": predecessors[0] if len(predecessors) == 1 else None,
        "status_code": status_code,
        "status_message": status_message,
    }


def _preparation_context_facts(context):
    relation = context["relation"]
    review = context["crm_review"]
    source = context["source"]
    order = context["order"]
    predecessor = context["predecessor"]
    return {
        "companyId": relation.company_id,
        "crmOrderRelationId": relation.pk,
        "resolutionBasis": relation.resolution_basis,
        "scopeMode": relation.scope_mode,
        "scopeReason": relation.scope_reason,
        "scopeItemCount": len(context["scope_items"]),
        "scopeItemIds": [item.pk for item in context["scope_items"]],
        "scopeItemLineNos": [item.line_no for item in context["scope_items"]],
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "salesOrderStatus": order.status,
        "orderVersion": order.version,
        "customer": order.customer.name,
        "orderDate": order.order_date.isoformat(),
        "requiredDeliveryDate": order.required_delivery_date.isoformat(),
        "crmReviewId": review.pk,
        "crmReviewVersion": review.review_version,
        "sourceRecordId": source.pk,
        "sourceOrderNo": review.source_order_no,
        "sourceVersion": source.source_version,
        "sourceContentHash": source.content_hash,
        "sourceContentHashVerified": True,
        "pdePredecessorRelationId": predecessor.pk if predecessor else None,
        "pdeReviewId": predecessor.pde_review_id if predecessor else None,
        "statusCode": context["status_code"],
        "statusMessage": context["status_message"],
        "canPrepare": predecessor is not None,
        "orderItems": [
            {
                "salesOrderItemId": item.pk,
                "lineNo": item.line_no,
                "externalLineNo": item.external_line_no,
                "productCode": item.material.code,
                "productName": item.customer_product_name or item.material.name,
                "quantity": str(item.quantity),
                "requiredDate": item.required_date.isoformat(),
            }
            for item in context["scope_items"]
        ],
        "readWriteCount": 0,
    }


def _revoked_preparation_facts(
    company_id, *, crm_order_relation_id=None, sales_order_id=None,
):
    """Project a known revoked history as an empty current admission context."""

    relation_id = _selector_id(crm_order_relation_id, "crmOrderRelationId")
    order_id = _selector_id(sales_order_id, "salesOrderId")
    queryset = PDEAdmissionChainRevocation.objects.select_related(
        "crm_order_relation__sales_order__customer",
        "engineering_instance__sales_order_item",
    ).filter(company_id=company_id).exclude(
        crm_order_relation__sales_order__status__in=("cancelled", "closed"),
    )
    if relation_id is not None:
        queryset = queryset.filter(crm_order_relation_id=relation_id)
    if order_id is not None:
        queryset = queryset.filter(crm_order_relation__sales_order_id=order_id)
    candidates = list(queryset.order_by("pk")[:2])
    if len(candidates) != 1:
        return None
    revocation = candidates[0]
    relation = revocation.crm_order_relation
    order = relation.sales_order
    snapshot = dict(revocation.identity_snapshot or {})
    context = {
        "companyId": company_id,
        "crmOrderRelationId": None,
        "resolutionBasis": "REVOKED_HISTORY",
        "scopeMode": "NONE",
        "scopeReason": "历史0032关系已撤销，不属于当前有效订单范围。",
        "scopeItemCount": 0,
        "scopeItemIds": [],
        "scopeItemLineNos": [],
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "salesOrderStatus": order.status,
        "orderVersion": order.version,
        "customer": order.customer.name,
        "orderDate": order.order_date.isoformat(),
        "requiredDeliveryDate": order.required_delivery_date.isoformat(),
        "crmReviewId": None,
        "crmReviewVersion": None,
        "sourceRecordId": None,
        "sourceOrderNo": "",
        "sourceVersion": "",
        "sourceContentHash": "",
        "sourceContentHashVerified": None,
        "pdePredecessorRelationId": None,
        "pdeReviewId": None,
        "statusCode": CURRENT_CHAIN_ABSENT_CODE,
        "statusMessage": CURRENT_CHAIN_ABSENT_MESSAGE,
        "canPrepare": False,
        "orderItems": [],
        "readWriteCount": 0,
        "revocationId": revocation.pk,
        "revocationNo": revocation.revocation_no,
        "revokedCrmOrderRelationId": relation.pk,
        "revokedCrmReviewId": snapshot.get("crmReviewId"),
        "revokedPdeReviewId": revocation.pde_review_id,
        "revokedPredecessorRelationId": revocation.predecessor_relation_id,
        "revokedAuthorizationId": revocation.authorization_id,
        "revokedEngineeringInstanceId": revocation.engineering_instance_id,
        "revokedEngineeringInstanceStatusLabel": (
            revocation.engineering_instance.get_status_display()
        ),
        "historicalChainPreserved": True,
    }
    return {
        "order": order,
        "source": None,
        "crmReview": None,
        "crmOrderRelation": None,
        "pdePredecessorRelation": None,
        "review": None,
        "workflow": None,
        "approval": None,
        "statusCode": CURRENT_CHAIN_ABSENT_CODE,
        "statusMessage": CURRENT_CHAIN_ABSENT_MESSAGE,
        "canPrepare": False,
        "contextFacts": context,
        "requirements": [],
        "rows": [],
    }


def preparation_context_facts(
    company_id, *, crm_order_relation_id=None, sales_order_id=None,
):
    """Return the server-owned, zero-write CRM→0032→PDE intake projection."""

    try:
        context = _resolve_formal_preparation_context(
            company_id,
            crm_order_relation_id=crm_order_relation_id,
            sales_order_id=sales_order_id,
        )
    except OrderDemandPreparationError as exc:
        revoked = _revoked_preparation_facts(
            company_id,
            crm_order_relation_id=crm_order_relation_id,
            sales_order_id=sales_order_id,
        )
        if revoked is not None and exc.code == "CRM_ORDER_FORMAL_RELATION_REQUIRED":
            return revoked["contextFacts"]
        raise
    return _preparation_context_facts(context)


def _authorized_target_facts(context, *, lock=False):
    if not context["predecessors"]:
        raise OrderDemandPreparationError(
            "PDE_REVIEW_PREDECESSOR_REQUIRED",
            PDE_PREDECESSOR_PENDING_MESSAGE,
            409,
            {
                "crmOrderRelationId": context["relation"].pk,
                "salesOrderId": context["order"].pk,
            },
        )
    if context["predecessor"] is None:
        raise OrderDemandPreparationError(
            "PDE_REVIEW_PREDECESSOR_NOT_UNIQUE",
            context["status_message"],
            409,
            {"crmOrderRelationId": context["relation"].pk},
        )

    admissions = []
    try:
        for item in context["scope_items"]:
            admissions.append(require_pde_engineering_preparation_admission(
                company_id=context["relation"].company_id,
                sales_order_item_id=item.pk,
                lock=lock,
            ))
    except PDEEngineeringPreparationAdmissionError as exc:
        raise OrderDemandPreparationError(
            exc.code, exc.message, exc.http_status,
            {"pdeEngineeringPreparationAdmission": exc.details},
        ) from exc
    if any(
        row.crm_order_relation_id != context["relation"].pk
        or row.sales_order_id != context["order"].pk
        or row.predecessor_relation_id != context["predecessor"].pk
        for row in admissions
    ):
        raise OrderDemandPreparationError(
            "PDE_ENGINEERING_AUTHORIZATION_CONTEXT_MISMATCH",
            "PDE工程准备授权未精确指向当前0032订单范围。",
            409,
        )
    authorization_ids = {row.authorization_id for row in admissions}
    if len(authorization_ids) != 1:
        raise OrderDemandPreparationError(
            "PDE_ENGINEERING_AUTHORIZATION_NOT_UNIQUE",
            "订单行无法收敛到同一PDE工程准备授权，已失败关闭。",
            409,
        )
    admission = admissions[0]
    review = OrderCrossFunctionalReview.objects.get(pk=admission.pde_review_id)
    if (
        review.source_record_id != context["source"].pk
        or review.source_version != context["source"].source_version
        or review.source_content_hash.lower() != context["source"].content_hash.lower()
    ):
        raise OrderDemandPreparationError(
            "PDE_ENGINEERING_SOURCE_MISMATCH", "PDE正式授权与工程来源不一致。", 409
        )
    workflow = WorkflowInstance.objects.get(pk=admission.workflow_instance_id)
    decision = ApprovalDecision.objects.select_related("actor").get(
        pk=admission.approval_decision_id,
    )
    return context["order"], context["source"], review, workflow, decision


def _target_facts(
    company_id, *, lock=False, crm_order_relation_id=None, sales_order_id=None,
    include_context=False,
):
    context = _resolve_formal_preparation_context(
        company_id,
        crm_order_relation_id=crm_order_relation_id,
        sales_order_id=sales_order_id,
        lock=lock,
    )
    facts = _authorized_target_facts(context, lock=lock)
    return (*facts, context) if include_context else facts


def _identity_for_order(company_id, order):
    return ExternalIdentity.objects.get_or_create(
        organization_id=company_id,
        source_system=SOURCE_SYSTEM,
        source_type=SOURCE_TYPE,
        source_object_type=SOURCE_OBJECT_TYPE,
        external_id=f"SalesOrder:{order.pk}",
        defaults={
            "target_entity_type": "ProductRequirementBatch",
            "mapping_status": ExternalIdentity.MappingStatus.REVIEW,
            "source_fingerprint": _canonical_hash({"orderId": order.pk, "version": order.version}),
            "audit_metadata": {
                "orderNo": order.order_no,
                "contractNo": order.contract_reference,
            },
        },
    )


@transaction.atomic
def prepare_order_demand(*, user, idempotency_key):
    decision, employee, position = _authorization(user)
    order, source, review, workflow, approval, context = _target_facts(
        user.company_id, lock=True, include_context=True,
    )
    key = str(idempotency_key or "").strip()
    if not key:
        raise OrderDemandPreparationError("IDEMPOTENCY_KEY_REQUIRED", "工程准备保存必须提供幂等键。")
    request_payload = {
        "orderId": order.pk,
        "orderVersion": order.version,
        "sourceRecordId": source.pk,
        "sourceVersion": source.source_version,
        "reviewId": review.pk,
        "reviewVersion": review.review_version,
        "approvalDecisionId": approval.pk,
        "crmOrderRelationId": context["relation"].pk,
        "lineIds": [item.pk for item in context["scope_items"]],
    }
    request_hash = _canonical_hash(request_payload)
    root_identity, _ = _identity_for_order(user.company_id, order)
    request, created = MasterDataWriteRequest.objects.select_for_update().get_or_create(
        organization_id=user.company_id,
        action_code=ACTION_CODE,
        entity_type="ProductRequirementBatch",
        idempotency_key=key,
        defaults={
            "request_hash": request_hash,
            "source_identity": root_identity,
            "audit_metadata": request_payload,
        },
    )
    if not created:
        if request.request_hash != request_hash:
            raise OrderDemandPreparationError(
                "IDEMPOTENCY_CONFLICT", "同一幂等键已用于不同工程准备内容。", 409
            )
        if request.status == MasterDataWriteRequest.Status.COMMITTED:
            return preparation_facts(
                user.company_id, crm_order_relation_id=context["relation"].pk,
            ), True

    created_ids = []
    requirement_ids = []
    for item in context["scope_items"]:
        requirement_no = f"{order.order_no}-REQ-{item.line_no:02d}"
        requirement, was_created = ProductRequirement.objects.get_or_create(
            requirement_no=requirement_no,
            defaults={
                "customer": order.customer.name,
                "product_name": item.customer_product_name or item.material.name,
                "requirement_source": f"CRM销售订单/{order.order_no}",
                "requirement_date": order.order_date,
                "owner": order.sales_owner.full_name if order.sales_owner_id else employee.full_name,
                "status": "confirmed",
            },
        )
        expected = {
            "customer": order.customer.name,
            "product_name": item.customer_product_name or item.material.name,
            "requirement_source": f"CRM销售订单/{order.order_no}",
            "requirement_date": order.order_date,
        }
        if not was_created and any(getattr(requirement, field) != value for field, value in expected.items()):
            raise OrderDemandPreparationError(
                "PRODUCT_REQUIREMENT_CONFLICT",
                f"需求{requirement_no}已存在但与当前销售订单事实不一致。",
                409,
            )
        requirement_ids.append(requirement.pk)
        if was_created:
            created_ids.append(requirement.pk)
        identity, _ = ExternalIdentity.objects.get_or_create(
            organization_id=user.company_id,
            source_system=SOURCE_SYSTEM,
            source_type=SOURCE_TYPE,
            source_object_type="SALES_ORDER_ITEM",
            external_id=f"SalesOrderItem:{item.pk}",
            defaults={
                "target_entity_type": "ProductRequirement",
                "target_entity_id": str(requirement.pk),
                "mapping_status": ExternalIdentity.MappingStatus.MATCH,
                "source_fingerprint": _canonical_hash({
                    "orderItemId": item.pk,
                    "quantity": str(item.quantity),
                    "requiredDate": item.required_date.isoformat(),
                    "engineeringAttributeCount": item.engineering_attributes.count(),
                }),
                "audit_metadata": {
                    "orderId": order.pk,
                    "orderNo": order.order_no,
                    "lineNo": item.line_no,
                    "reviewId": review.pk,
                    "approvalDecisionId": approval.pk,
                },
            },
        )
        if identity.target_entity_id != str(requirement.pk):
            raise OrderDemandPreparationError(
                "ORDER_DEMAND_IDENTITY_CONFLICT", "订单明细已有不同需求映射。", 409
            )

    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_CODE,
        actor=user,
        organization_id=user.company_id,
        target_type="ProductRequirementBatch",
        target_id=order.pk,
        target_label=order.order_no,
        reason="正式销售订单承接：按0032评审范围形成客户需求与工程准备关系，停止于产品设计前",
        before_snapshot={"requirementIds": []},
        after_snapshot={
            "requirementIds": requirement_ids,
            "createdRequirementIds": created_ids,
            "sourceRecordId": source.pk,
            "sourceVersion": source.source_version,
            "reviewId": review.pk,
            "reviewVersion": review.review_version,
            "workflowInstanceId": workflow.pk,
            "approvalDecisionId": approval.pk,
            "approvalActorId": approval.actor_id,
            "actor": {
                "userId": user.pk,
                "username": user.username,
                "employeeId": employee.pk,
                "positionCode": position.code,
            },
            "authorization": decision,
            "productDesignWriteCount": 0,
            "bomWriteCount": 0,
            "routingWriteCount": 0,
            "mrpWriteCount": 0,
            "procurementWriteCount": 0,
            "manufacturingWriteCount": 0,
        },
    )
    root_identity.target_entity_id = str(order.pk)
    root_identity.mapping_status = ExternalIdentity.MappingStatus.MATCH
    root_identity.audit_metadata = {
        **(root_identity.audit_metadata or {}),
        "requirementIds": requirement_ids,
        "reviewId": review.pk,
        "approvalDecisionId": approval.pk,
    }
    root_identity.save(update_fields=["target_entity_id", "mapping_status", "audit_metadata", "last_seen"])
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(order.pk)
    request.result = {
        "salesOrderId": order.pk,
        "requirementIds": requirement_ids,
        "auditId": audit.pk,
    }
    request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])
    return preparation_facts(
        user.company_id, crm_order_relation_id=context["relation"].pk,
    ), False


def _linked_requirements(company_id):
    identities = ExternalIdentity.objects.filter(
        organization_id=company_id,
        source_system=SOURCE_SYSTEM,
        source_type=SOURCE_TYPE,
        source_object_type="SALES_ORDER_ITEM",
        target_entity_type="ProductRequirement",
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
    )
    target_ids = [int(value) for value in identities.values_list("target_entity_id", flat=True) if str(value).isdigit()]
    return ProductRequirement.objects.filter(pk__in=target_ids).order_by("requirement_no")


def requirement_facts(company_id):
    rows = []
    identities = {
        int(row.target_entity_id): row
        for row in ExternalIdentity.objects.filter(
            organization_id=company_id,
            source_system=SOURCE_SYSTEM,
            source_type=SOURCE_TYPE,
            source_object_type="SALES_ORDER_ITEM",
            target_entity_type="ProductRequirement",
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
        )
        if str(row.target_entity_id).isdigit()
    }
    item_ids = [int(row.external_id.split(":", 1)[1]) for row in identities.values()]
    item_map = {
        item.pk: item
        for order in SalesOrder.objects.filter(company_id=company_id).prefetch_related("items__uom")
        for item in order.items.all() if item.pk in item_ids
    }
    for requirement in ProductRequirement.objects.filter(pk__in=identities).order_by("requirement_no"):
        identity = identities[requirement.pk]
        item_id = int(identity.external_id.split(":", 1)[1])
        item = item_map.get(item_id)
        if not item:
            continue
        order = item.sales_order
        rows.append({
            "id": requirement.pk,
            "requirementNo": requirement.requirement_no,
            "orderNo": order.order_no,
            "customer": requirement.customer,
            "productName": requirement.product_name,
            "quantityLabel": f"{item.quantity.normalize()} {item.uom.name if item.uom_id else ''}".strip(),
            "requirementSource": requirement.requirement_source,
            "sourceVersion": (
                ProductDesignItem.objects.filter(
                    company_id=company_id, sales_order_item_id=item.pk,
                ).values_list("source_version", flat=True).order_by().first() or ""
            ),
            "requirementDate": requirement.requirement_date.isoformat(),
            "requiredDeliveryDate": item.required_date.isoformat(),
            "owner": requirement.owner,
            "statusLabel": requirement.get_status_display(),
        })
    return rows


def engineering_readiness_facts(company_id, order_no=None):
    """Project ordinary readiness reads from persisted relationships, not a dev sample.

    The sample-specific ``_target_facts`` remains available only to the explicit
    governed preparation action.  This read has no writes and does not require a
    particular external order name, row count, review version or signature count.
    """
    from .models import OrderCrossFunctionalReview, ProductDesignItem
    from .product_design_service import design_group_progress

    requirements = requirement_facts(company_id)
    requirement_by_item = {}
    identities = ExternalIdentity.objects.filter(
        organization_id=company_id,
        source_system=SOURCE_SYSTEM,
        source_type=SOURCE_TYPE,
        source_object_type="SALES_ORDER_ITEM",
        target_entity_type="ProductRequirement",
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
    )
    requirement_by_id = {
        row.pk: row for row in ProductRequirement.objects.filter(
            pk__in=[int(value) for value in identities.values_list("target_entity_id", flat=True) if str(value).isdigit()]
        )
    }
    for identity in identities:
        if not identity.external_id.startswith("SalesOrderItem:") or not str(identity.target_entity_id).isdigit():
            continue
        item_id = int(identity.external_id.split(":", 1)[1])
        requirement_by_item[item_id] = requirement_by_id.get(int(identity.target_entity_id))

    orders = SalesOrder.objects.filter(company_id=company_id)
    if order_no:
        orders = orders.filter(order_no=order_no)
    orders = orders.select_related("customer").prefetch_related("items__material", "items__uom")
    progress = design_group_progress(company_id)
    rows = []
    for order in orders.order_by("-updated_at", "-pk"):
        for item in order.items.all():
            design_items = ProductDesignItem.objects.filter(
                company_id=company_id, sales_order_item=item,
            )
            source_ids = list(design_items.order_by().values_list("source_record_id", flat=True).distinct())
            source_versions = list(design_items.order_by().values_list("source_version", flat=True).distinct())
            authorizations = list(
                active_pde_authorizations(
                    PDEEngineeringPreparationAuthorization.objects.select_related(
                    "predecessor_relation__pde_review",
                    )
                ).filter(
                    company_id=company_id,
                    predecessor_relation__crm_order_relation__scope_items__sales_order_item=item,
                ).distinct()[:2]
            )
            review = (
                authorizations[0].predecessor_relation.pde_review
                if len(authorizations) == 1 else None
            )
            requirement = requirement_by_item.get(item.pk)
            item_progress = progress.get(item.pk)
            purchased_finished = (
                item.material.material_type == "finished"
                and item.material.is_purchased and not item.material.is_produced
            )
            if purchased_finished and not design_items.exists():
                engineering_status = "采购成品，无需产品设计"
                next_action = "进入采购履约路径"
            elif item_progress:
                engineering_status = item_progress["statusLabel"]
                next_action = item_progress["nextActionLabel"]
            elif requirement:
                engineering_status = "客户需求已形成，待工程范围确认"
                next_action = "进入生产可行性评审或产品设计准备"
            else:
                engineering_status = "需求关系尚未建立"
                next_action = "先完成客户订单需求确认"
            rows.append({
                "id": item.pk,
                "orderNo": order.order_no,
                "orderLineNo": item.line_no,
                "customer": order.customer.name,
                "productCode": item.material.code,
                "productName": item.customer_product_name or item.material.name,
                "engineeringModeCode": item.engineering_mode,
                "engineeringModeLabel": item.get_engineering_mode_display(),
                "deliveryDate": item.required_date.isoformat(),
                "sourceOrderNo": order.external_source_no,
                "sourceVersion": source_versions[0] if len(source_versions) == 1 else ("多个来源" if source_versions else ""),
                "requirementStatusLabel": requirement.get_status_display() if requirement else "需求待形成",
                "reviewStatusLabel": review.get_record_status_display() if review else ("正式授权存在歧义" if len(authorizations) > 1 else "待形成正式授权"),
                "engineeringStatusLabel": engineering_status,
                "bomStatusLabel": "未开始",
                "routingStatusLabel": "未开始",
                "documentStatusLabel": "未开始",
                "manufacturingOutputStatusLabel": "未开始",
                "mrpReadyStatusLabel": "未准备",
                "deliveryRiskLabel": "未评估",
                "nextActionLabel": next_action,
                "designItemCount": design_items.count(),
                "designCompletedFactCount": item_progress["completedFactCount"] if item_progress else 0,
                "designDatedCompletionCount": item_progress["datedCompletionCount"] if item_progress else 0,
                "productionInputReadyLabel": "否",
            })
    return {
        "rows": rows,
        "requirements": requirements,
        "orderCount": len({row["orderNo"] for row in rows}),
        "sourceRecordCount": ProductDesignItem.objects.filter(company_id=company_id).values("source_record_id").distinct().count(),
        "readWriteCount": 0,
    }


def preparation_facts(
    company_id, *, crm_order_relation_id=None, sales_order_id=None,
):
    try:
        context = _resolve_formal_preparation_context(
            company_id,
            crm_order_relation_id=crm_order_relation_id,
            sales_order_id=sales_order_id,
        )
    except OrderDemandPreparationError as exc:
        revoked = _revoked_preparation_facts(
            company_id,
            crm_order_relation_id=crm_order_relation_id,
            sales_order_id=sales_order_id,
        )
        if revoked is not None and exc.code == "CRM_ORDER_FORMAL_RELATION_REQUIRED":
            return revoked
        raise
    order = context["order"]
    source = context["source"]
    if context["predecessor"] is None:
        review = workflow = approval = None
    else:
        order, source, review, workflow, approval = _authorized_target_facts(context)
    from .product_design_service import design_group_progress
    design_progress = design_group_progress(company_id)
    from .models import OrderEngineeringInstance
    from .admission_chain_revocation import active_order_engineering_instances
    engineering_instances = {
        instance.sales_order_item_id: instance
        for instance in active_order_engineering_instances(
            OrderEngineeringInstance.objects.filter(company_id=company_id, sales_order_item__sales_order=order)
        )
    }
    requirements = list(_linked_requirements(company_id))
    requirement_by_no = {row.requirement_no: row for row in requirements}
    rows = []
    for item in context["scope_items"]:
        requirement = requirement_by_no.get(f"{order.order_no}-REQ-{item.line_no:02d}")
        progress = design_progress.get(item.pk)
        instance = engineering_instances.get(item.pk)
        pending = context["predecessor"] is None
        rows.append({
            "id": item.pk,
            "orderNo": order.order_no,
            "orderLineNo": item.line_no,
            "productCode": item.material.code,
            "productName": item.customer_product_name or item.material.name,
            "deliveryDate": item.required_date.isoformat(),
            "sourceOrderNo": context["crm_review"].source_order_no,
            "sourceVersion": source.source_version,
            "requirementStatusLabel": requirement.get_status_display() if requirement else "需求待形成",
            "reviewStatusLabel": (
                "PDE评审已正式通过" if approval else context["status_message"]
            ),
            "engineeringStatusLabel": (
                context["status_message"] if pending else
                (progress["statusLabel"] if progress else ("工程输入已准备，待产品设计" if requirement else "需求待形成"))
            ),
            "bomStatusLabel": "未开始",
            "routingStatusLabel": "未开始",
            "documentStatusLabel": "未开始",
            "manufacturingOutputStatusLabel": "未开始",
            "mrpReadyStatusLabel": "未准备",
            "deliveryRiskLabel": "需要关注",
            "nextActionLabel": (
                context["status_message"] if pending else
                (progress["nextActionLabel"] if progress else (
                    "工程身份已确认，待建立产品设计项" if instance else "等待用户确认后进入产品设计"
                ))
            ),
            "orderEngineeringInstanceId": instance.pk if instance else None,
            "orderEngineeringInstanceNo": instance.instance_no if instance else None,
            "designItemCount": progress["itemCount"] if progress else 0,
            "designCompletedFactCount": progress["completedFactCount"] if progress else 0,
            "designDatedCompletionCount": progress["datedCompletionCount"] if progress else 0,
            "productionInputReadyLabel": "否",
        })
    return {
        "order": order,
        "source": source,
        "crmReview": context["crm_review"],
        "crmOrderRelation": context["relation"],
        "pdePredecessorRelation": context["predecessor"],
        "review": review,
        "workflow": workflow,
        "approval": approval,
        "statusCode": context["status_code"],
        "statusMessage": context["status_message"],
        "canPrepare": context["predecessor"] is not None,
        "contextFacts": _preparation_context_facts(context),
        "requirements": requirements,
        "rows": rows,
    }
