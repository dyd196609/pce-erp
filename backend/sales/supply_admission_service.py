"""Formal Action -> scoped authority -> PMC responsibility -> immutable fact."""

import hashlib
import json
from threading import RLock

from django.db import transaction
from django.utils import timezone

from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import PositionResponsibility, PositionWorkflowResponsibility, OrganizationOperatingAuditRecord, User, UserRoleScopeAssignment
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import record_projected_business_transition

from .models import SalesOrderItem, SalesOrderItemSupplyAdmission
from .supply_admission_contract import (
    ACTION_CODE, ALLOWED_ORDER_STATES, MODULE_CODE, NODE_CODE, OBJECT_TYPE,
    PMC_RESPONSIBILITY_CODE, PROCESS_CODE, RESPONSIBILITY_TYPE, ROLE_CODE,
)

_CONFIRM_LOCK = RLock()  # SQLite ignores row locks; database uniqueness is also enforced.


class SupplyAdmissionError(ValueError):
    def __init__(self, code, message, http_status=409):
        self.code, self.message, self.http_status = code, message, http_status
        super().__init__(message)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def effective(row):
    now = timezone.now()
    today = timezone.localtime(now).date() if timezone.is_aware(now) else now.date()
    return (not row.effective_from or row.effective_from <= today) and (not row.effective_to or row.effective_to >= today)


def source_snapshot(item):
    return {
        "salesOrderId": item.sales_order_id, "companyId": item.sales_order.company_id,
        "materialId": item.material_id, "quantity": str(item.quantity), "uomId": item.uom_id,
        "requiredDate": item.required_date.isoformat(), "engineeringMode": item.engineering_mode,
    }


class SupplyAdmissionFactProvider:
    def read(self, module_code, object_ids):
        rows = list(SalesOrderItem.objects.select_related("sales_order").filter(pk__in=object_ids))
        return {
            "found": module_code == MODULE_CODE and len(rows) == len(object_ids),
            "objectIds": [row.pk for row in rows],
            "statuses": [row.sales_order.status for row in rows],
            "legalEntityIds": sorted({str(row.sales_order.company_id) for row in rows}),
            "currentStateSource": "server", "reason": "object_not_found",
        }


def authorize(*, user, item, query=False):
    decision = ActionPermissionValidator(fact_provider=SupplyAdmissionFactProvider()).evaluate(
        user=user, module_code=MODULE_CODE,
        action_code="view-supply-admission" if query else ACTION_CODE,
        object_ids=[item.pk], selection_count=1,
    )
    if not decision["granted"]:
        raise SupplyAdmissionError("SUPPLY_ADMISSION_PERMISSION_DENIED", decision["reason"], 403)
    # Supplement the shared role validator with exact typed scope on THIS role.
    scope = UserRoleScopeAssignment.objects.filter(
        user=user, role__code=ROLE_CODE, organization_id=item.sales_order.company_id,
        scope_code="ORGANIZATION", active=True,
    ).first()
    if not scope or not user.is_active or user.is_superuser:
        raise SupplyAdmissionError("SUPPLY_ADMISSION_SCOPE_DENIED", "须由有效业务责任人在本公司专用角色范围内执行，管理员不能代确认。", 403)
    return decision, scope


def resolve_responsibility(user, company_id):
    employee = Employee.objects.select_related("position_ref__department", "department_ref").filter(user=user, status="active").first()
    position = employee.position_ref if employee else None
    department = employee.department_ref if employee else None
    if (not position or not department or not position.is_active or not department.is_active
        or position.company_id != company_id or department.company_id != company_id
        or position.department_id != department.pk or user.company_id != company_id
        or not effective(position) or not effective(department)):
        raise SupplyAdmissionError("SUPPLY_ADMISSION_IDENTITY_INVALID", "有效员工、计划物控岗位、部门和公司关系不完整。")
    duties = list(PositionResponsibility.objects.select_related("responsibility").filter(
        position=position, active=True, responsibility__code=PMC_RESPONSIBILITY_CODE,
        responsibility__is_active=True, responsibility__status="ACTIVE",
    ))
    if len(duties) != 1 or not effective(duties[0].responsibility):
        raise SupplyAdmissionError("SUPPLY_ADMISSION_PMC_DUTY_MISSING", "岗位缺少唯一有效的现有物料需求计划与供应协调职责。")
    duty = duties[0]
    return employee, position, department, duty


def resolve_manufacturing_execution_responsibility(*, user_id, company_id, decision_user):
    """Record the designated execution owner, not an execution/signature action."""
    user = User.objects.select_for_update().filter(pk=user_id).first()
    employee = Employee.objects.select_related("position_ref__department", "department_ref").filter(
        user=user, status="active",
    ).first() if user else None
    position = employee.position_ref if employee else None
    department = employee.department_ref if employee else None
    if (not user or not user.is_active or user.is_superuser or user.pk == decision_user.pk
        or user.company_id != company_id or not position or not department
        or not position.is_active or not department.is_active
        or position.company_id != company_id or department.company_id != company_id
        or position.department_id != department.pk
        or not effective(position) or not effective(department)):
        raise SupplyAdmissionError("MANUFACTURING_OWNER_INVALID", "指定生产执行责任人须为本公司有效员工/账号、独立有效岗位与部门，且与供应决策人分离。")
    duties = list(PositionResponsibility.objects.select_related("responsibility").filter(
        position=position, active=True, responsibility__code="RESP_PROD_PLAN_001",
        responsibility__is_active=True, responsibility__status="ACTIVE",
    ))
    if len(duties) != 1 or not effective(duties[0].responsibility):
        raise SupplyAdmissionError("MANUFACTURING_OWNER_DUTY_MISSING", "指定岗位缺少唯一有效的既有生产计划承接与达成职责；不自动补建或授权。")
    duty = duties[0]
    return {
        "userId": user.pk, "username": user.username, "employeeId": employee.pk,
        "employeeNo": employee.employee_no, "name": employee.full_name,
        "positionId": position.pk, "positionName": position.name,
        "departmentId": department.pk, "departmentName": department.name,
        "responsibilityId": duty.responsibility_id, "responsibilityCode": duty.responsibility.code,
        "responsibilityName": duty.responsibility.name, "positionResponsibilityId": duty.pk,
        "companyId": company_id, "assignmentSource": "USER_DESIGNATED",
        "assignedBy": decision_user.pk, "responsibilityAssignmentOnly": True,
        "executionPerformed": False,
    }


def _fact_payload(fact):
    return {
        "salesOrderItemId": fact.sales_order_item_id, "supplyType": fact.supply_type,
        "responsibilityType": fact.responsibility_type, "confirmedBy": fact.confirmed_by_id,
        "employeeId": fact.employee_id, "positionResponsibilityId": fact.position_responsibility_id,
        "workflowResponsibilityId": fact.workflow_responsibility_id,
        "confirmedAt": fact.confirmed_at.isoformat(), "reason": fact.reason,
        "idempotencyKey": fact.idempotency_key, "requestHash": fact.request_hash,
        "source": fact.source_snapshot, "responsibility": fact.responsibility_snapshot,
    }


def supply_admission_facts(item):
    """Absence/incomplete/stale evidence never falls back to Material fields."""
    fact = SalesOrderItemSupplyAdmission.objects.select_related("audit_record").filter(sales_order_item=item).first()
    if not fact:
        return {"status": "UNRESOLVED", "supplyBranch": "UNRESOLVED", "factId": None, "factSource": "ORDER_LINE_SUPPLY_ADMISSION", "reason": "订单行供应承接事实未确认"}
    payload = _fact_payload(fact)
    audit = fact.audit_record
    transitions = list(BusinessStateTransition.objects.filter(object_type=OBJECT_TYPE, object_id=item.pk))
    valid = (
        fact.supply_type in ("MAKE", "BUY") and fact.responsibility_type == RESPONSIBILITY_TYPE
        and canonical_hash(payload) == fact.fact_hash
        and audit.actor_id == fact.confirmed_by_id and audit.organization_id == item.sales_order.company_id
        and audit.target_type == "SalesOrderItem" and audit.target_id == item.pk and audit.action_code == ACTION_CODE
        and audit.after_snapshot.get("confirmation") == payload
        and audit.after_snapshot.get("factHash") == fact.fact_hash and audit.reason == fact.reason
        and len(transitions) == 1 and transitions[0].source_state == "UNCONFIRMED"
        and transitions[0].target_state == "CONFIRMED" and transitions[0].version == 1
        and transitions[0].operator_id == fact.confirmed_by_id and transitions[0].action_code == ACTION_CODE
        and transitions[0].audit_reference == f"OrganizationOperatingAuditRecord:{audit.pk}"
    )
    status = "CONFIRMED" if valid else "INVALID"
    carry_proof = None
    if valid and fact.source_snapshot != source_snapshot(item):
        from pde.order_engineering_identity_carry import supply_carry_proof
        carry_proof = supply_carry_proof(item, fact)
        status = "CONFIRMED" if carry_proof else "STALE"
    return {
        **payload, "status": status, "supplyBranch": fact.supply_type if status == "CONFIRMED" else "UNRESOLVED",
        "factId": fact.pk, "factSource": "ORDER_LINE_SUPPLY_ADMISSION", "auditId": audit.pk,
        "engineeringIdentityCarryProofId": carry_proof.pk if carry_proof else None,
        "stateMachineConsistent": valid, "statusTransitionCount": len(transitions),
        "resolutionReason": "" if status == "CONFIRMED" else "供应确认事实或来源/审计一致性未通过",
    }


def query_supply_admission(*, user, order_id, item_id):
    user = User.objects.get(pk=user.pk)
    item = SalesOrderItem.objects.select_related("sales_order").filter(pk=item_id, sales_order_id=order_id).first()
    if not item:
        raise SupplyAdmissionError("SALES_ORDER_ITEM_NOT_FOUND", "订单行不存在。", 404)
    authorize(user=user, item=item, query=True)
    return supply_admission_facts(item)


def confirm_supply_admission(*, user, order_id, item_id, supply_type, idempotency_key, reason,
                             manufacturing_owner_user_id=None):
    mode = str(supply_type or "").strip().upper()
    key, reason = str(idempotency_key or "").strip(), str(reason or "").strip()
    if mode not in ("MAKE", "BUY"):
        raise SupplyAdmissionError("SUPPLY_TYPE_UNSUPPORTED", "仅支持已注册正式MAKE/BUY模式；其他模式须另行定义，不自动推断。", 400)
    if not key or len(key) > 160 or not 2 <= len(reason) <= 300:
        raise SupplyAdmissionError("CONFIRMATION_REQUEST_INVALID", "须提供有效幂等键和2至300字业务确认依据。", 400)
    owner_id = None
    if manufacturing_owner_user_id is not None:
        owner_text = str(manufacturing_owner_user_id)
        if (isinstance(manufacturing_owner_user_id, bool)
            or len(owner_text) > 19 or not owner_text.isascii() or not owner_text.isdigit()
            or not 0 < int(owner_text) <= 9223372036854775807):
            raise SupplyAdmissionError("MANUFACTURING_OWNER_INVALID", "须提供已人工指定的有效生产执行责任人账号ID，不自动选择。", 400)
        if mode != "MAKE":
            raise SupplyAdmissionError("MANUFACTURING_OWNER_NOT_APPLICABLE", "生产执行责任仅适用于MAKE供应承接，不能与采购责任混用。", 400)
        owner_id = int(manufacturing_owner_user_id)
    with _CONFIRM_LOCK, transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        item = SalesOrderItem.objects.select_for_update().select_related("sales_order").filter(pk=item_id, sales_order_id=order_id).first()
        if not item:
            raise SupplyAdmissionError("SALES_ORDER_ITEM_NOT_FOUND", "订单行不存在。", 404)
        decision, scope = authorize(user=user, item=item)
        if item.sales_order.status not in ALLOWED_ORDER_STATES or item.sales_order.acceptance_marker:
            raise SupplyAdmissionError("SUPPLY_ADMISSION_ORDER_NOT_ELIGIBLE", "仅对已正式批准且非系统验收样本订单确认供应承接。")
        if user.pk == item.sales_order.created_by_id:
            raise SupplyAdmissionError("SUPPLY_ADMISSION_SOD_DENIED", "供应确认责任人与订单制单人须分离。", 403)
        request = {"actor": user.pk, "item": item.pk, "supplyType": mode, "reason": reason}
        # Preserve historical request hashes when no execution owner was supplied.
        if owner_id is not None:
            request["manufacturingOwnerUserId"] = owner_id
        request_hash = canonical_hash(request)
        existing = SalesOrderItemSupplyAdmission.objects.filter(sales_order_item=item).first()
        if existing:
            if existing.idempotency_key != key or existing.request_hash != request_hash:
                raise SupplyAdmissionError("SUPPLY_ADMISSION_ALREADY_CONFIRMED", "订单行已有确认事实；禁止覆盖或更换责任人。")
            facts = supply_admission_facts(item)
            if facts["status"] != "CONFIRMED":
                raise SupplyAdmissionError("SUPPLY_ADMISSION_HISTORY_INVALID", "既有确认历史不完整或来源变化，禁止重放成功。")
            return {"confirmation": facts, "idempotent": True, "businessWriteCount": 0, "auditWriteCount": 0}
        if SalesOrderItemSupplyAdmission.objects.filter(idempotency_key=key).exists():
            raise SupplyAdmissionError("IDEMPOTENCY_KEY_CONFLICT", "幂等键已用于其他订单行。")
        employee, position, department, duty = resolve_responsibility(user, item.sales_order.company_id)
        mappings = list(PositionWorkflowResponsibility.objects.select_related("workflow_node__process_definition").filter(
            position=position, responsibility=duty.responsibility, workflow_code=PROCESS_CODE,
            node_code=NODE_CODE, ownership_type="OWNER", active=True,
            workflow_node__active=True, workflow_node__business_action_code=ACTION_CODE,
            workflow_node__node_code=NODE_CODE, workflow_node__process_definition__definition_code=PROCESS_CODE,
            workflow_node__process_definition__document_type=OBJECT_TYPE, workflow_node__process_definition__active=True,
        ))
        if len(mappings) != 1 or not effective(mappings[0]):
            raise SupplyAdmissionError("SUPPLY_ADMISSION_WORKFLOW_DUTY_MISSING", "缺少唯一有效的订单行供应确认流程责任。", 403)
        mapping = mappings[0]
        responsibility = {
            "userId": user.pk, "username": user.username, "employeeId": employee.pk, "employeeNo": employee.employee_no,
            "name": employee.full_name, "positionId": position.pk, "positionName": position.name,
            "departmentId": department.pk, "departmentName": department.name,
            "responsibilityId": duty.responsibility_id, "responsibilityName": duty.responsibility.name,
            "positionResponsibilityId": duty.pk, "workflowResponsibilityId": mapping.pk,
            "processCode": PROCESS_CODE, "nodeId": mapping.workflow_node_id,
            "roleCode": ROLE_CODE, "roleScopeAssignmentId": scope.pk, "companyId": item.sales_order.company_id,
        }
        if owner_id is not None:
            responsibility["manufacturingExecution"] = resolve_manufacturing_execution_responsibility(
                user_id=owner_id, company_id=item.sales_order.company_id, decision_user=user,
            )
        fact = SalesOrderItemSupplyAdmission(
            sales_order_item=item, supply_type=mode, confirmed_by=user, employee=employee,
            position_responsibility=duty, workflow_responsibility=mapping, confirmed_at=timezone.now(),
            idempotency_key=key, request_hash=request_hash, reason=reason,
            source_snapshot=source_snapshot(item), responsibility_snapshot=responsibility,
        )
        payload = _fact_payload(fact)
        fact.fact_hash = canonical_hash(payload)
        fact.audit_record = OrganizationOperatingAuditRecord.objects.create(
            actor=user, organization_id=item.sales_order.company_id, action_code=ACTION_CODE,
            target_type="SalesOrderItem", target_id=item.pk,
            target_label=f"{item.sales_order.order_no} 第{item.line_no}行", reason=reason,
            before_snapshot={"supplyAdmission": "UNCONFIRMED"},
            after_snapshot={"confirmation": payload, "factHash": fact.fact_hash, "authorization": decision, "demandWriteCount": 0},
        )
        fact.full_clean()
        fact.save(force_insert=True)
        record_projected_business_transition(
            object_type=OBJECT_TYPE, object_id=item.pk, source_state="UNCONFIRMED", target_state="CONFIRMED",
            action_code=ACTION_CODE, operator=user, reason=reason,
            audit_reference=f"OrganizationOperatingAuditRecord:{fact.audit_record_id}",
            allowed_transitions=(("UNCONFIRMED", "CONFIRMED"),),
        )
        return {"confirmation": supply_admission_facts(item), "idempotent": False, "businessWriteCount": 2, "auditWriteCount": 1}
