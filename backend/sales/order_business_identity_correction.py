"""Controlled correction of a SalesOrder's current business identity.

This service is intentionally narrow.  It changes only the current identity
facts on one draft SalesOrder, preserves the commercial/order-line identity,
and records one durable action request plus one organization audit fact.
"""

from __future__ import annotations

from copy import deepcopy

from django.db import transaction

from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, PositionWorkflowResponsibility

from .models import SalesOrder, SalesOrderActionRequest


ACTION_CODE = "sales.order.correct_business_identity"
AUTHORIZATION_ACTION_CODE = "sales.order.update"
PROCESS_CODE = "SALES_ORDER_TO_SUPPLY_PLAN"
RESPONSIBILITY_CODE = "RESP_SALES_ORDER_002"
DEVELOPMENT_PURPOSE = SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION
FORMAL_PURPOSE = SalesOrder.BusinessPurpose.FORMAL_SALE
DEVELOPMENT_MARKER = "DEVELOPMENT_ONLY"
DEVELOPMENT_DELIVERY_KEYS = (
    "developmentOnly",
    "developmentContract",
    "externalCommunicationAllowed",
    "businessPurpose",
    "purpose",
    "acceptanceMarker",
    "developmentMarker",
)


class SalesOrderBusinessIdentityCorrectionError(ValueError):
    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _actor_facts(actor):
    employee = getattr(actor, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    department = getattr(employee, "department_ref", None) if employee else None
    return employee, position, department, {
        "accountId": actor.pk,
        "account": actor.username,
        "employeeId": getattr(employee, "pk", None),
        "employeeNo": getattr(employee, "employee_no", ""),
        "employeeName": getattr(employee, "full_name", ""),
        "departmentId": getattr(employee, "department_ref_id", None),
        "departmentCode": getattr(department, "code", ""),
        "departmentName": getattr(department, "name", ""),
        "positionId": getattr(employee, "position_ref_id", None),
        "positionCode": getattr(position, "code", ""),
        "positionName": getattr(position, "name", ""),
        "companyId": getattr(actor, "company_id", None),
    }


def _identity_snapshot(order):
    delivery = order.delivery_information if isinstance(order.delivery_information, dict) else {}
    return {
        "businessPurpose": order.business_purpose,
        "acceptanceMarker": order.acceptance_marker,
        "contractReference": order.contract_reference,
        "remark": order.remark,
        "deliveryIdentity": {
            key: deepcopy(delivery[key])
            for key in DEVELOPMENT_DELIVERY_KEYS
            if key in delivery
        },
        "orderVersion": order.version,
    }


def _protected_snapshot(order):
    items = list(order.items.order_by("line_no", "pk"))
    return {
        "orderNo": order.order_no,
        "companyId": order.company_id,
        "departmentId": order.department_id,
        "customerId": order.customer_id,
        "projectReference": order.project_reference,
        "externalSourceNo": order.external_source_no,
        "status": order.status,
        "salesOwnerId": order.sales_owner_id,
        "itemCount": len(items),
        "items": [
            {
                "id": item.pk,
                "lineNo": item.line_no,
                "materialId": item.material_id,
                "quantity": str(item.quantity),
                "externalLineNo": item.external_line_no,
            }
            for item in items
        ],
    }


def _assert_actor_authorized(*, actor, order):
    if not actor or not actor.is_authenticated or not actor.is_active:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_ACTOR_INVALID",
            "正式业务身份纠正必须由有效登录账户执行。",
        )
    if actor.is_superuser:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_ADMIN_FORBIDDEN",
            "正式业务身份纠正禁止使用管理员或超级用户账户执行。",
        )
    employee, position, department, actor_facts = _actor_facts(actor)
    if (
        not employee
        or employee.status != "active"
        or not position
        or not position.is_active
        or not department
        or not department.is_active
    ):
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_EMPLOYEE_REQUIRED",
            "执行账户必须关联在职员工、有效部门和正式岗位。",
        )
    if actor.company_id != order.company_id or department.company_id != order.company_id:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_COMPANY_MISMATCH",
            "执行员工与销售订单不属于同一公司。",
        )
    authorization = AuthorizationService.decide(
        user=actor,
        action_code=AUTHORIZATION_ACTION_CODE,
        organization_id=order.company_id,
        business_object={
            "organizationId": order.company_id,
            "departmentId": order.department_id,
        },
    )
    if not authorization.get("allowed"):
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_PERMISSION_DENIED",
            "执行账户没有销售订单更新权限或数据范围不覆盖目标订单。",
            details={"authorization": authorization},
        )
    mapping = PositionWorkflowResponsibility.objects.select_related(
        "responsibility", "workflow_node__process_definition",
    ).filter(
        position=position,
        active=True,
        responsibility__code=RESPONSIBILITY_CODE,
        responsibility__is_active=True,
        workflow_node__process_definition__definition_code=PROCESS_CODE,
        workflow_node__process_definition__active=True,
        workflow_node__business_action_code=AUTHORIZATION_ACTION_CODE,
        workflow_node__active=True,
    ).order_by("workflow_node__sequence", "pk").first()
    if not mapping:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_WORKFLOW_DENIED",
            "执行岗位未承担正式销售订单更新流程责任。",
        )
    return authorization, actor_facts, mapping


def _validate_development_delivery(delivery, expected_contract_reference):
    if not isinstance(delivery, dict):
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_DELIVERY_INVALID",
            "订单交付信息不是结构化对象，禁止纠正。",
        )
    if delivery.get("developmentOnly") is not True:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_DEVELOPMENT_FLAG_MISMATCH",
            "订单当前开发专用标记与授权目标不一致。",
        )
    contract = delivery.get("developmentContract")
    if (
        not isinstance(contract, dict)
        or contract.get("contractNo") != expected_contract_reference
        or str(contract.get("purpose") or "").upper() != DEVELOPMENT_MARKER
    ):
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_DEVELOPMENT_CONTRACT_MISMATCH",
            "订单当前开发合同事实与授权目标不一致。",
        )
    if "externalCommunicationAllowed" in delivery and delivery["externalCommunicationAllowed"] is not False:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_PROTECTION_FLAG_MISMATCH",
            "订单当前开发保护标记与授权目标不一致。",
        )
    allowed_purpose_values = {DEVELOPMENT_PURPOSE, DEVELOPMENT_MARKER}
    for key in ("businessPurpose", "purpose", "acceptanceMarker", "developmentMarker"):
        if key in delivery and str(delivery[key] or "").upper() not in allowed_purpose_values:
            raise SalesOrderBusinessIdentityCorrectionError(
                "SALES_IDENTITY_CORRECTION_DELIVERY_PURPOSE_MISMATCH",
                f"交付信息字段 {key} 不是已授权清除的开发用途值。",
            )


def _idempotent_result(*, order, action_request, key, request_id):
    if action_request.request_id != request_id:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_REPLAY_REQUEST_MISMATCH",
            "同一幂等键已绑定其他请求号，禁止复用。",
        )
    audit = action_request.audit_record
    current_identity = _identity_snapshot(order)
    current_protected = _protected_snapshot(order)
    expected_identity = (audit.after_snapshot or {}).get("currentIdentity") or {}
    expected_protected = (audit.after_snapshot or {}).get("protectedIdentity") or {}
    if current_identity != expected_identity or current_protected != expected_protected:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_REPLAY_MISMATCH",
            "既有纠正审计与当前订单事实不一致，禁止重复写入。",
            details={
                "currentIdentity": current_identity,
                "auditedIdentity": expected_identity,
                "currentProtectedIdentity": current_protected,
                "auditedProtectedIdentity": expected_protected,
            },
        )
    return {
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "actionCode": ACTION_CODE,
        "idempotencyKey": key,
        "requestId": request_id,
        "organizationAuditId": audit.pk,
        "actionRequestId": action_request.pk,
        "auditCreatedAt": audit.created_at.isoformat(),
        "before": (audit.before_snapshot or {}).get("currentIdentity") or {},
        "after": current_identity,
        "idempotent": True,
        "orderWriteCount": 0,
        "businessStateTransitionCount": 0,
        "downstreamWriteCount": 0,
    }


@transaction.atomic
def correct_sales_order_business_identity(
    *, actor, order_id, expected_order_no, expected_customer_id,
    expected_project_reference, expected_external_source_no,
    expected_contract_reference, expected_remark, expected_item_count,
    target_business_purpose, idempotency_key, request_id, reason,
    source="management-command",
):
    """Correct one development-validation order to its formal sales identity."""

    key = str(idempotency_key or "").strip()
    request_id = str(request_id or "").strip()
    reason = str(reason or "").strip()
    target_business_purpose = str(target_business_purpose or "").strip()
    if not key:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_IDEMPOTENCY_REQUIRED", "必须提供幂等键。",
        )
    if not request_id:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_REQUEST_ID_REQUIRED", "必须提供请求号。",
        )
    if not reason:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_REASON_REQUIRED", "必须提供明确纠正原因。",
        )
    if target_business_purpose != FORMAL_PURPOSE:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_TARGET_INVALID",
            "本动作只允许把当前身份纠正为 FORMAL_SALE。",
        )

    order = SalesOrder.objects.select_for_update().select_related(
        "company", "department", "customer", "sales_owner",
    ).prefetch_related("items").filter(pk=order_id).first()
    if not order:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_ORDER_NOT_FOUND", "未找到授权纠正的销售订单。",
        )
    authorization, actor_facts, mapping = _assert_actor_authorized(actor=actor, order=order)

    existing = SalesOrderActionRequest.objects.select_related("audit_record").filter(
        sales_order=order,
        action_code=ACTION_CODE,
        idempotency_key=key,
    ).first()
    if existing:
        return _idempotent_result(
            order=order, action_request=existing, key=key, request_id=request_id,
        )
    request_collision = SalesOrderActionRequest.objects.filter(
        sales_order=order, request_id=request_id,
    ).first()
    if request_collision:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_REQUEST_COLLISION",
            "请求号已用于其他销售订单动作。",
            details={"actionRequestId": request_collision.pk},
        )
    prior = SalesOrderActionRequest.objects.filter(
        sales_order=order, action_code=ACTION_CODE,
    ).first()
    if prior:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_ALREADY_RECORDED",
            "该订单已用其他幂等键完成业务身份纠正，禁止形成第二套结果。",
            details={"actionRequestId": prior.pk},
        )

    protected_before = _protected_snapshot(order)
    target_matches = (
        order.order_no == expected_order_no
        and order.customer_id == expected_customer_id
        and order.project_reference == expected_project_reference
        and order.external_source_no == expected_external_source_no
        and order.contract_reference == expected_contract_reference
        and order.remark == expected_remark
        and protected_before["itemCount"] == int(expected_item_count)
    )
    if not target_matches:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_TARGET_MISMATCH",
            "订单当前商业身份或行数已变化，超出本次最小纠正授权范围。",
            details={"protectedIdentity": protected_before},
        )
    if order.status == "cancelled":
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_CANCELLED",
            "已取消订单禁止执行业务身份纠正。",
        )
    if order.status != "draft":
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_STATUS_INVALID",
            "本次受控动作只允许纠正草稿订单。",
        )
    if (
        order.business_purpose != DEVELOPMENT_PURPOSE
        or order.acceptance_marker != DEVELOPMENT_MARKER
    ):
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_SOURCE_IDENTITY_MISMATCH",
            "订单当前业务用途或验收标记不是已授权的开发验证身份。",
            details={"currentIdentity": _identity_snapshot(order)},
        )
    _validate_development_delivery(order.delivery_information, expected_contract_reference)

    identity_before = _identity_snapshot(order)
    delivery_after = deepcopy(order.delivery_information)
    for key_to_remove in DEVELOPMENT_DELIVERY_KEYS:
        delivery_after.pop(key_to_remove, None)
    order.business_purpose = FORMAL_PURPOSE
    order.acceptance_marker = ""
    order.contract_reference = ""
    order.remark = ""
    order.delivery_information = delivery_after
    order.version += 1
    order.save(update_fields=[
        "business_purpose", "acceptance_marker", "contract_reference", "remark",
        "delivery_information", "version", "updated_at",
    ])

    identity_after = _identity_snapshot(order)
    protected_after = _protected_snapshot(order)
    if protected_after != protected_before:
        raise SalesOrderBusinessIdentityCorrectionError(
            "SALES_IDENTITY_CORRECTION_PROTECTED_IDENTITY_CHANGED",
            "受保护的订单商业身份或订单行发生变化，事务已回滚。",
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
            "currentIdentity": identity_before,
            "protectedIdentity": protected_before,
            "actor": actor_facts,
            "authorization": authorization,
            "workflowResponsibility": {
                "mappingId": mapping.pk,
                "responsibilityCode": mapping.responsibility.code,
                "businessActionCode": mapping.workflow_node.business_action_code,
            },
            "idempotencyKey": key,
            "requestId": request_id,
            "source": str(source or "management-command"),
        },
        after_snapshot={
            "currentIdentity": identity_after,
            "protectedIdentity": protected_after,
            "actor": actor_facts,
            "authorization": authorization,
            "idempotencyKey": key,
            "requestId": request_id,
            "source": str(source or "management-command"),
            "orderWriteCount": 1,
            "businessStateTransitionCount": 0,
            "downstreamWriteCount": 0,
        },
    )
    action_request = SalesOrderActionRequest.objects.create(
        sales_order=order,
        action_code=ACTION_CODE,
        idempotency_key=key,
        request_id=request_id,
        source=str(source or "management-command"),
        actor=actor,
        source_state=order.status,
        target_state=order.status,
        audit_record=audit,
    )
    return {
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "actionCode": ACTION_CODE,
        "idempotencyKey": key,
        "requestId": request_id,
        "organizationAuditId": audit.pk,
        "actionRequestId": action_request.pk,
        "auditCreatedAt": audit.created_at.isoformat(),
        "before": identity_before,
        "after": identity_after,
        "idempotent": False,
        "orderWriteCount": 1,
        "businessStateTransitionCount": 0,
        "downstreamWriteCount": 0,
    }
