"""Formal responsibility configuration for sales-order manufacturing admission.

The service is deliberately configuration-only.  It never submits, approves or
confirms a sales order and never creates planning or manufacturing execution
objects.  All writes are additive, audited and idempotent; existing sales-order
approval semantics are treated as protected facts.
"""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import json

from django.db import transaction

from pfm.models import Employee
from sales.models import SalesOrder
from system.authorization import AuthorizationService
from system.models import (
    Company,
    OrganizationOperatingAuditRecord,
    Permission,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from system.organization_operating import (
    OrganizationOperatingError,
    OrganizationOperatingService,
)
from workflow_runtime.definition_service import (
    WorkflowDefinitionError,
    WorkflowDefinitionOperatingService,
)
from workflow_runtime.execution_resolution import WorkflowExecutionResolutionService
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition


CONTRACT_VERSION = "PCE-ORDER-MANUFACTURING-ADMISSION-RESPONSIBILITY-V1.0"
PROCESS_CODE = "ORDER_MANUFACTURING_ADMISSION"
PROCESS_NAME = "制造承接确认"
PROCESS_ENGLISH_NAME = "Manufacturing Admission Confirmation"
DOCUMENT_TYPE = "SalesOrderManufacturingAdmission"
NODE_CODE = "MANUFACTURING_ADMISSION_CONFIRM"
RESPONSIBILITY_CODE = "MANUFACTURING_ADMISSION_APPROVER"
RESPONSIBILITY_NAME = "制造承接确认责任人"
ROLE_CODE = "manufacturing_admission_approver"
ROLE_NAME = "制造承接确认责任人"
PERMISSION_CODE = "pde.order.manufacturing_admission.confirm"
PERMISSION_NAME = "订单制造承接确认"
PERMISSION_MODULE = "PDE"
GENERIC_OWNERSHIP_TYPE = PositionWorkflowResponsibility.OwnershipType.APPROVER

_MANAGEMENT_PERMISSIONS = (
    "system.organization.responsibility.manage",
    "system.organization.workflow_responsibility.manage",
)


class ManufacturingAdmissionConfigurationError(ValueError):
    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _canonical_hash(value):
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _snapshot(instance):
    if instance is None:
        return None
    return {
        field.attname: getattr(instance, field.attname)
        for field in instance._meta.concrete_fields
    }


def _audit(*, actor, action_code, target, target_type, label, reason, after):
    return OrganizationOperatingAuditRecord.objects.create(
        actor=actor,
        organization_id=actor.company_id,
        action_code=action_code,
        target_type=target_type,
        target_id=target.pk,
        target_label=label,
        reason=reason,
        before_snapshot={},
        after_snapshot=after,
    )


def _authorize_configuration(actor):
    if not actor.is_active or not actor.company_id:
        raise ManufacturingAdmissionConfigurationError(
            "CONFIGURATION_ACTOR_INVALID", "配置操作人不是当前公司的有效账号。"
        )
    decisions = {
        code: AuthorizationService.decide(
            user=actor, action_code=code, organization_id=str(actor.company_id)
        )
        for code in _MANAGEMENT_PERMISSIONS
    }
    denied = [code for code, decision in decisions.items() if not decision["allowed"]]
    if denied:
        raise ManufacturingAdmissionConfigurationError(
            "CONFIGURATION_ACTOR_PERMISSION_DENIED",
            "配置操作人缺少正式组织/流程责任维护权限。",
            details={"deniedPermissionCodes": denied},
        )
    return decisions


def _assert_exact(row, expected, *, code, message):
    actual = {key: getattr(row, key) for key in expected}
    if actual != expected:
        raise ManufacturingAdmissionConfigurationError(
            code, message, details={"expected": expected, "actual": actual}
        )


def _protected_sales_approval_hash():
    payload = {
        "permissions": list(
            Permission.objects.filter(code="sales.order.approve")
            .order_by("pk")
            .values()
        ),
        "roles": list(
            Role.objects.filter(code="sales_order_approver")
            .order_by("pk")
            .values()
        ),
        "rolePermissions": list(
            RolePermission.objects.filter(role__code="sales_order_approver")
            .order_by("pk")
            .values()
        ),
        "responsibilities": list(
            Responsibility.objects.filter(code__in=("ORDER_APPROVE", "APPROVER"))
            .order_by("pk")
            .values()
        ),
        "workflowResponsibilities": list(
            PositionWorkflowResponsibility.objects.filter(
                workflow_code="ORDER_APPROVE"
            )
            .order_by("pk")
            .values()
        ),
    }
    return _canonical_hash(payload)


def _ensure_permission_role_and_scope(*, actor, responsible_user, company, reason, writes):
    permission = Permission.objects.select_for_update().filter(code=PERMISSION_CODE).first()
    if permission:
        _assert_exact(
            permission,
            {"name": PERMISSION_NAME, "module": PERMISSION_MODULE},
            code="PERMISSION_SEMANTIC_CONFLICT",
            message="制造承接确认权限编码已存在但业务语义不一致。",
        )
    else:
        permission = Permission.objects.create(
            code=PERMISSION_CODE, name=PERMISSION_NAME, module=PERMISSION_MODULE
        )
        audit = _audit(
            actor=actor,
            action_code="REGISTER_MANUFACTURING_ADMISSION_PERMISSION",
            target=permission,
            target_type="Permission",
            label=f"{permission.code} - {permission.name}",
            reason=reason,
            after={"code": permission.code, "name": permission.name, "module": permission.module},
        )
        writes.append({"type": "Permission", "id": permission.pk, "operation": "CREATE", "auditId": audit.pk})

    role = Role.objects.select_for_update().filter(code=ROLE_CODE).first()
    role_description = "仅用于制造承接确认；不含销售订单审批、订单状态变更或制造输出发布权限。"
    if role:
        _assert_exact(
            role,
            {"name": ROLE_NAME, "description": role_description},
            code="ROLE_SEMANTIC_CONFLICT",
            message="制造承接确认角色编码已存在但业务语义不一致。",
        )
    else:
        role = Role.objects.create(
            code=ROLE_CODE, name=ROLE_NAME, description=role_description
        )
        audit = _audit(
            actor=actor,
            action_code="CREATE_MANUFACTURING_ADMISSION_ROLE",
            target=role,
            target_type="Role",
            label=f"{role.code} - {role.name}",
            reason=reason,
            after={"code": role.code, "name": role.name, "description": role.description},
        )
        writes.append({"type": "Role", "id": role.pk, "operation": "CREATE", "auditId": audit.pk})

    existing_permission_codes = set(
        RolePermission.objects.filter(role=role).values_list("permission__code", flat=True)
    )
    unexpected = existing_permission_codes - {PERMISSION_CODE}
    if unexpected:
        raise ManufacturingAdmissionConfigurationError(
            "ROLE_PERMISSION_BOUNDARY_CONFLICT",
            "制造承接确认角色已含超出最小范围的权限，停止配置。",
            details={"unexpectedPermissionCodes": sorted(unexpected)},
        )
    role_permission = RolePermission.objects.filter(role=role, permission=permission).first()
    if not role_permission:
        role_permission = RolePermission.objects.create(role=role, permission=permission)
        audit = _audit(
            actor=actor,
            action_code="BIND_MANUFACTURING_ADMISSION_ROLE_PERMISSION",
            target=role_permission,
            target_type="RolePermission",
            label=f"{role.code} / {permission.code}",
            reason=reason,
            after={"roleCode": role.code, "permissionCode": permission.code},
        )
        writes.append({"type": "RolePermission", "id": role_permission.pk, "operation": "CREATE", "auditId": audit.pk})

    assignment = UserRoleScopeAssignment.objects.select_for_update().filter(
        user=responsible_user, role=role, organization=company
    ).first()
    if assignment:
        expected = {
            "department_id": None,
            "scope_code": UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            "active": True,
        }
        _assert_exact(
            assignment,
            expected,
            code="ROLE_SCOPE_ASSIGNMENT_CONFLICT",
            message="制造承接责任人的既有同角色授权范围不符合公司级最小配置。",
        )
    else:
        authority_payload = {
            "userId": responsible_user.pk,
            "roleCode": role.code,
            "legalEntityId": str(company.pk),
            "departmentId": None,
            "scopeCode": UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            "version": 1,
        }
        assignment = UserRoleScopeAssignment.objects.create(
            user=responsible_user,
            role=role,
            organization=company,
            department=None,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True,
            version=1,
            business_hash=_canonical_hash(authority_payload),
        )
        audit = _audit(
            actor=actor,
            action_code="GRANT_MANUFACTURING_ADMISSION_ROLE_SCOPE",
            target=assignment,
            target_type="UserRoleScopeAssignment",
            label=f"{responsible_user.username} / {role.code} / {company.code}",
            reason=reason,
            after={**authority_payload, "businessHash": assignment.business_hash},
        )
        writes.append({"type": "UserRoleScopeAssignment", "id": assignment.pk, "operation": "CREATE", "auditId": audit.pk})
    return permission, role, assignment


def _ensure_responsibility(*, actor, position, effective_from, reason, writes):
    description = (
        "承担销售订单进入制造体系前的制造承接确认；不代表销售订单审批，"
        "不改变订单状态，不授予Demand创建或制造输出发布权限。"
    )
    responsibility = Responsibility.objects.select_for_update().filter(
        code=RESPONSIBILITY_CODE
    ).first()
    if not responsibility:
        result = OrganizationOperatingService.execute(
            user=actor,
            action="SAVE_RESPONSIBILITY",
            request_identity="ORDER-MANUFACTURING-ADMISSION-RESPONSIBILITY-DRAFT-V1",
            payload={
                "code": RESPONSIBILITY_CODE,
                "name": RESPONSIBILITY_NAME,
                "description": description,
                "category": "PDE",
                "status": Responsibility.Status.DRAFT,
                "reason": reason,
            },
        )
        responsibility = Responsibility.objects.get(pk=result["target"]["id"])
        writes.append({"type": "Responsibility", "id": responsibility.pk, "operation": "CREATE", "auditId": result["auditId"]})
    if responsibility.status == Responsibility.Status.DRAFT:
        result = OrganizationOperatingService.execute(
            user=actor,
            action="SAVE_RESPONSIBILITY",
            request_identity="ORDER-MANUFACTURING-ADMISSION-RESPONSIBILITY-ACTIVE-V1",
            payload={
                "id": responsibility.pk,
                "code": RESPONSIBILITY_CODE,
                "name": RESPONSIBILITY_NAME,
                "description": description,
                "category": "PDE",
                "status": Responsibility.Status.ACTIVE,
                "effectiveFrom": effective_from.isoformat(),
                "reason": reason,
            },
        )
        responsibility.refresh_from_db()
        writes.append({"type": "Responsibility", "id": responsibility.pk, "operation": "ACTIVATE", "auditId": result["auditId"]})
    _assert_exact(
        responsibility,
        {
            "name": RESPONSIBILITY_NAME,
            "description": description,
            "category": "PDE",
            "status": Responsibility.Status.ACTIVE,
            "is_active": True,
            "effective_from": effective_from,
            "effective_to": None,
        },
        code="RESPONSIBILITY_SEMANTIC_CONFLICT",
        message="制造承接确认职责已存在但正式语义或有效期不一致。",
    )

    position_mapping = PositionResponsibility.objects.select_for_update().filter(
        position=position, responsibility=responsibility
    ).first()
    if position_mapping:
        _assert_exact(
            position_mapping,
            {"is_primary": False, "active": True},
            code="POSITION_RESPONSIBILITY_CONFLICT",
            message="岗位制造承接职责关系已存在但配置不一致。",
        )
    else:
        result = OrganizationOperatingService.execute(
            user=actor,
            action="SAVE_POSITION_RESPONSIBILITY",
            request_identity="ORDER-MANUFACTURING-ADMISSION-POSITION-RESPONSIBILITY-V1",
            payload={
                "positionId": position.pk,
                "responsibilityId": responsibility.pk,
                "isPrimary": False,
                "active": True,
                "reason": reason,
            },
        )
        position_mapping = PositionResponsibility.objects.get(pk=result["target"]["id"])
        writes.append({"type": "PositionResponsibility", "id": position_mapping.pk, "operation": "CREATE", "auditId": result["auditId"]})
    return responsibility, position_mapping


def _ensure_process(*, actor, permission, reason, writes):
    definition = ProcessDefinition.objects.prefetch_related("nodes").filter(
        definition_code=PROCESS_CODE
    ).first()
    if not definition:
        result = WorkflowDefinitionOperatingService.configure_atomic_minimal_template(
            user=actor,
            idempotency_key="ORDER-MANUFACTURING-ADMISSION-CATALOG-V1",
            payload={
                "definition": {
                    "definitionCode": PROCESS_CODE,
                    "definitionName": PROCESS_NAME,
                    "businessDomain": "PDE",
                    "description": (
                        f"{PROCESS_ENGLISH_NAME}；独立于销售订单审批，"
                        "仅定义制造体系责任承接确认。"
                    ),
                    "documentType": DOCUMENT_TYPE,
                    "version": 1,
                    "active": True,
                },
                "node": {
                    "nodeCode": NODE_CODE,
                    "nodeName": PROCESS_NAME,
                    "sequence": 1,
                    "businessActionCode": permission.code,
                    "active": True,
                    "description": "由正式指定的制造承接责任人执行；本配置不自动执行确认。",
                },
                "reason": reason,
            },
        )
        definition = ProcessDefinition.objects.get(pk=result["definition"]["id"])
        writes.extend([
            {"type": "ProcessDefinition", "id": definition.pk, "operation": "CREATE", "auditId": result["auditId"]},
            {"type": "WorkflowNodeDefinition", "id": result["node"]["id"], "operation": "CREATE", "auditId": result["auditId"]},
        ])
    _assert_exact(
        definition,
        {
            "definition_name": PROCESS_NAME,
            "business_domain": "PDE",
            "document_type": DOCUMENT_TYPE,
            "version": 1,
            "active": True,
        },
        code="PROCESS_DEFINITION_CONFLICT",
        message="制造承接确认流程编码已存在但正式定义不一致。",
    )
    nodes = list(definition.nodes.all())
    if len(nodes) != 1:
        raise ManufacturingAdmissionConfigurationError(
            "PROCESS_NODE_CONFLICT", "制造承接确认流程必须且只能包含一个责任确认节点。"
        )
    node = nodes[0]
    _assert_exact(
        node,
        {
            "node_code": NODE_CODE,
            "node_name": PROCESS_NAME,
            "sequence": 1,
            "business_action_code": permission.code,
            "active": True,
        },
        code="PROCESS_NODE_CONFLICT",
        message="制造承接确认节点已存在但业务动作或节点语义不一致。",
    )
    return definition, node


def _ensure_workflow_responsibility(
    *, actor, position, responsibility, node, effective_from, reason, writes
):
    mapping = PositionWorkflowResponsibility.objects.select_for_update().filter(
        position=position,
        workflow_code=PROCESS_CODE,
        node_code=NODE_CODE,
        ownership_type=GENERIC_OWNERSHIP_TYPE,
    ).first()
    if mapping:
        _assert_exact(
            mapping,
            {
                "responsibility_id": responsibility.pk,
                "workflow_node_id": node.pk,
                "active": True,
                "effective_from": effective_from,
                "effective_to": None,
            },
            code="WORKFLOW_RESPONSIBILITY_CONFLICT",
            message="制造承接流程责任关系已存在但职责、节点或有效期不一致。",
        )
    else:
        result = OrganizationOperatingService.execute(
            user=actor,
            action="SAVE_WORKFLOW_RESPONSIBILITY",
            payload={
                "positionId": position.pk,
                "responsibilityId": responsibility.pk,
                "workflowNodeId": node.pk,
                "ownershipType": GENERIC_OWNERSHIP_TYPE,
                "active": True,
                "effectiveFrom": effective_from.isoformat(),
                "reason": reason,
            },
        )
        mapping = PositionWorkflowResponsibility.objects.get(pk=result["target"]["id"])
        writes.append({"type": "PositionWorkflowResponsibility", "id": mapping.pk, "operation": "CREATE", "auditId": result["auditId"]})
    return mapping


@transaction.atomic
def configure_manufacturing_admission_responsibility(
    *,
    actor,
    order_no,
    expected_order_id,
    employee_no,
    username,
    company_code,
    reason,
    effective_from=None,
):
    """Configure and read back the exact designated manufacturing responsibility."""

    if len(str(reason or "").strip()) < 2:
        raise ManufacturingAdmissionConfigurationError("REASON_REQUIRED", "必须提供正式配置原因。")
    reason = str(reason).strip()
    effective_from = effective_from or date.today()
    authorization = _authorize_configuration(actor)

    company = Company.objects.select_for_update().filter(code=company_code).first()
    if not company or not company.is_active or actor.company_id != company.pk:
        raise ManufacturingAdmissionConfigurationError(
            "COMPANY_SCOPE_INVALID", "公司不存在、已停用或不属于配置操作人。"
        )
    order = SalesOrder.objects.select_for_update().filter(
        pk=expected_order_id, order_no=order_no, company=company
    ).first()
    if not order:
        raise ManufacturingAdmissionConfigurationError("ORDER_NOT_FOUND", "指定销售订单不存在。")
    if order.status != "draft":
        raise ManufacturingAdmissionConfigurationError(
            "ORDER_FACT_CHANGED", "销售订单已不再是本轮要求保持的draft状态。"
        )
    order_before = _snapshot(order)
    sales_approval_hash_before = _protected_sales_approval_hash()

    employee = Employee.objects.select_for_update().select_related(
        "user", "department_ref", "position_ref"
    ).filter(employee_no=employee_no).first()
    if not employee or employee.status != "active":
        raise ManufacturingAdmissionConfigurationError(
            "RESPONSIBLE_EMPLOYEE_INVALID", "指定制造承接责任人员工不存在或不是在职状态。"
        )
    responsible_user = employee.user
    if not responsible_user or responsible_user.username != username or not responsible_user.is_active:
        raise ManufacturingAdmissionConfigurationError(
            "RESPONSIBLE_ACCOUNT_INVALID", "指定员工未关联给定的有效系统账号。"
        )
    if responsible_user.company_id != company.pk:
        raise ManufacturingAdmissionConfigurationError(
            "RESPONSIBLE_ACCOUNT_SCOPE_INVALID", "指定账号不属于COMP001。"
        )
    position = employee.position_ref
    department = employee.department_ref
    if (
        not position
        or not position.is_active
        or position.company_id != company.pk
        or not department
        or department.company_id != company.pk
        or position.department_id != department.pk
    ):
        raise ManufacturingAdmissionConfigurationError(
            "RESPONSIBLE_POSITION_SCOPE_INVALID", "指定员工缺少当前公司内有效且一致的部门/岗位关系。"
        )
    if order.created_by_id == responsible_user.pk:
        raise ManufacturingAdmissionConfigurationError(
            "SEGREGATION_OF_DUTIES_FAILED", "制造承接责任人不得与订单制单人为同一账号。"
        )

    writes = []
    try:
        permission, role, assignment = _ensure_permission_role_and_scope(
            actor=actor,
            responsible_user=responsible_user,
            company=company,
            reason=reason,
            writes=writes,
        )
        responsibility, position_mapping = _ensure_responsibility(
            actor=actor,
            position=position,
            effective_from=effective_from,
            reason=reason,
            writes=writes,
        )
        definition, node = _ensure_process(
            actor=actor, permission=permission, reason=reason, writes=writes
        )
        workflow_mapping = _ensure_workflow_responsibility(
            actor=actor,
            position=position,
            responsibility=responsibility,
            node=node,
            effective_from=effective_from,
            reason=reason,
            writes=writes,
        )
    except (OrganizationOperatingError, WorkflowDefinitionError) as error:
        raise ManufacturingAdmissionConfigurationError(
            getattr(error, "code", "FORMAL_SERVICE_FAILED"),
            getattr(error, "message", str(error)),
        ) from error

    resolution = WorkflowExecutionResolutionService.resolve(
        user=actor, definition_id=definition.pk
    )
    node_resolution = resolution["nodes"][0]
    responsible_account = next(
        (row for row in node_resolution["accounts"] if row["id"] == responsible_user.pk), None
    )
    if not node_resolution["executable"] or not responsible_account or not responsible_account["executable"]:
        raise ManufacturingAdmissionConfigurationError(
            "MANUFACTURING_ADMISSION_EXECUTOR_NOT_RESOLVED",
            "正式流程解析未能把指定账号解析为可执行制造承接责任人。",
            details={"resolution": resolution},
        )

    order.refresh_from_db()
    if _snapshot(order) != order_before:
        raise ManufacturingAdmissionConfigurationError(
            "ORDER_PROTECTION_FAILED", "配置过程中销售订单事实发生变化，事务已回滚。"
        )
    sales_approval_hash_after = _protected_sales_approval_hash()
    if sales_approval_hash_after != sales_approval_hash_before:
        raise ManufacturingAdmissionConfigurationError(
            "HISTORICAL_SALES_APPROVAL_PROTECTION_FAILED",
            "历史销售订单审批模型发生变化，事务已回滚。",
        )

    return {
        "contractVersion": CONTRACT_VERSION,
        "configurationStatus": "READY",
        "manufacturingAdmissionConfirmationStatus": "NOT_EXECUTED",
        "responsibilityAdmissionBlockerResolved": True,
        "productionDemandOverallAdmissionReady": order.status in {
            "confirmed", "approved", "engineering", "manufacturing_ready",
            "in_progress", "delivering", "completed",
        },
        "remainingDemandGate": (
            None if order.status != "draft" else "SALES_ORDER_NOT_APPROVED"
        ),
        "order": {
            "id": order.pk,
            "orderNo": order.order_no,
            "status": order.status,
            "creatorUserId": order.created_by_id,
            "changed": False,
        },
        "responsiblePerson": {
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "fullName": employee.full_name,
            "employeeStatus": employee.status,
            "userId": responsible_user.pk,
            "username": responsible_user.username,
            "accountActive": responsible_user.is_active,
            "departmentId": department.pk,
            "departmentCode": department.code,
            "departmentName": department.name,
            "positionId": position.pk,
            "positionCode": position.code,
            "positionName": position.name,
            "segregatedFromOrderCreator": order.created_by_id != responsible_user.pk,
        },
        "configuration": {
            "processDefinitionId": definition.pk,
            "processCode": definition.definition_code,
            "processName": definition.definition_name,
            "processEnglishName": PROCESS_ENGLISH_NAME,
            "documentType": definition.document_type,
            "workflowNodeId": node.pk,
            "nodeCode": node.node_code,
            "permissionId": permission.pk,
            "permissionCode": permission.code,
            "roleId": role.pk,
            "roleCode": role.code,
            "roleScopeAssignmentId": assignment.pk,
            "scopeCode": assignment.scope_code,
            "responsibilityId": responsibility.pk,
            "responsibilityType": responsibility.code,
            "genericOwnershipType": workflow_mapping.ownership_type,
            "positionResponsibilityId": position_mapping.pk,
            "workflowResponsibilityId": workflow_mapping.pk,
        },
        "resolution": resolution,
        "authorization": authorization,
        "businessWriteCount": len(writes),
        "businessWrites": writes,
        "protectedSalesApprovalHash": sales_approval_hash_after,
        "prohibitedBusinessWrites": {
            "salesOrderStatus": 0,
            "salesOrderSubmit": 0,
            "salesOrderApprove": 0,
            "salesOrderConfirm": 0,
            "demand": 0,
            "planningRequirement": 0,
            "manufacturingOutput": 0,
            "bom": 0,
            "routing": 0,
            "account": 0,
        },
    }


__all__ = [
    "CONTRACT_VERSION",
    "ManufacturingAdmissionConfigurationError",
    "configure_manufacturing_admission_responsibility",
]
