"""Additive, audited configuration; never alters existing approval semantics."""

from django.db import transaction

from sales.models import SalesOrder
from system.authorization import AuthorizationService
from system.models import Company, OrganizationOperatingAuditRecord, Permission, Role, RolePermission, User, UserRoleScopeAssignment, PositionWorkflowResponsibility
from system.organization_operating import OrganizationOperatingService
from workflow_runtime.definition_service import WorkflowDefinitionOperatingService
from workflow_runtime.models import ProcessDefinition

from .supply_admission_contract import ACTION_CODE, NAME, NODE_CODE, OBJECT_TYPE, PROCESS_CODE, RESPONSIBILITY_TYPE, ROLE_CODE, ROLE_DESCRIPTION, ROLE_NAME
from .supply_admission_service import SupplyAdmissionError, canonical_hash, effective, resolve_responsibility


@transaction.atomic
def configure_supply_admission(*, actor, responsible_user, order_id, company_code, reason):
    actor = User.objects.select_for_update().get(pk=actor.pk)
    user = User.objects.select_for_update().get(pk=responsible_user.pk)
    company = Company.objects.get(code=company_code, is_active=True)
    if not 2 <= len(str(reason or "").strip()) <= 300:
        raise SupplyAdmissionError("CONFIGURATION_REASON_REQUIRED", "配置必须提供业务授权依据。", 400)
    for permission in ("system.organization.responsibility.manage", "system.organization.workflow_responsibility.manage"):
        decision = AuthorizationService.decide(user=actor, action_code=permission, organization_id=str(company.pk))
        if not decision["allowed"] or actor.company_id != company.pk:
            raise SupplyAdmissionError("CONFIGURATION_PERMISSION_DENIED", "缺少正式权限/流程责任配置管理权限。", 403)
    order = SalesOrder.objects.get(pk=order_id, company=company)
    if not user.is_active or user.is_superuser or user.pk == order.created_by_id:
        raise SupplyAdmissionError("CONFIGURATION_RESPONSIBLE_USER_INVALID", "指定责任人须为有效且与制单人分离的真实业务账号。")
    employee, position, department, duty = resolve_responsibility(user, company.pk)
    writes = []

    def ensure(model, lookup, values):
        row = model.objects.select_for_update().filter(**lookup).first()
        if row:
            if any(getattr(row, field) != value for field, value in values.items()):
                raise SupplyAdmissionError("CONFIGURATION_CONFLICT", f"{model.__name__}现有语义冲突，禁止覆盖。")
            return row
        row = model.objects.create(**lookup, **values)
        audit = OrganizationOperatingAuditRecord.objects.create(
            actor=actor, organization=company, action_code="sales.order_item.supply_admission.configure",
            target_type=model.__name__, target_id=row.pk, target_label=NAME,
            reason=reason, before_snapshot={}, after_snapshot={"targetUserId": user.pk, **lookup, **values},
        )
        writes.append({"model": model.__name__, "id": row.pk, "auditId": audit.pk})
        return row

    permission = ensure(Permission, {"code": ACTION_CODE}, {"name": NAME, "module": "SALES"})
    role = ensure(Role, {"code": ROLE_CODE}, {"name": ROLE_NAME, "description": ROLE_DESCRIPTION})
    if set(RolePermission.objects.filter(role=role).values_list("permission__code", flat=True)) - {ACTION_CODE}:
        raise SupplyAdmissionError("ROLE_BOUNDARY_CONFLICT", "专用角色存在超出供应确认的权限。")
    ensure(RolePermission, {"role_id": role.pk, "permission_id": permission.pk}, {})
    grant_data = {"user_id": user.pk, "role_id": role.pk, "organization_id": company.pk}
    ensure(UserRoleScopeAssignment, grant_data, {
        "scope_code": "ORGANIZATION", "department_id": None, "active": True,
        "business_hash": canonical_hash({**grant_data, "scope": "ORGANIZATION"}),
    })
    definition = ProcessDefinition.objects.filter(definition_code=PROCESS_CODE).first()
    if not definition:
        result = WorkflowDefinitionOperatingService.configure_atomic_minimal_template(
            user=actor, idempotency_key=f"{PROCESS_CODE}-CATALOG-V1",
            payload={
                "definition": {"definitionCode": PROCESS_CODE, "definitionName": NAME, "businessDomain": "SALES", "documentType": OBJECT_TYPE, "version": 1, "active": True, "description": "正式订单批准后，计划物控责任人确认订单行MAKE/BUY供应承接；不推进订单或创建Demand。"},
                "node": {"nodeCode": NODE_CODE, "nodeName": NAME, "sequence": 1, "businessActionCode": ACTION_CODE, "active": True, "description": f"责任类型{RESPONSIBILITY_TYPE}；复用现有计划物控岗位职责。"},
                "reason": reason,
            },
        )
        definition = ProcessDefinition.objects.get(pk=result["definition"]["id"])
        writes.extend([{ "model": "ProcessDefinition", "id": definition.pk, "auditId": result["auditId"]}, {"model": "WorkflowNodeDefinition", "id": result["node"]["id"], "auditId": result["auditId"]}])
    if (definition.document_type != OBJECT_TYPE or not definition.active
        or definition.definition_name != NAME or definition.business_domain != "SALES" or definition.version != 1):
        raise SupplyAdmissionError("PROCESS_CONFLICT", "供应承接确认正式流程定义冲突。")
    nodes = list(definition.nodes.all())
    if len(nodes) != 1 or nodes[0].node_code != NODE_CODE or nodes[0].business_action_code != ACTION_CODE or not nodes[0].active:
        raise SupplyAdmissionError("PROCESS_NODE_CONFLICT", "供应确认须有唯一有效专用动作节点。")
    node = nodes[0]
    mapping = PositionWorkflowResponsibility.objects.filter(position=position, workflow_code=PROCESS_CODE, node_code=NODE_CODE, ownership_type="OWNER").first()
    if not mapping:
        result = OrganizationOperatingService.execute(user=actor, action="SAVE_WORKFLOW_RESPONSIBILITY", payload={
            "positionId": position.pk, "responsibilityId": duty.responsibility_id,
            "workflowNodeId": node.pk, "ownershipType": "OWNER", "active": True, "reason": reason,
        })
        mapping = PositionWorkflowResponsibility.objects.get(pk=result["target"]["id"])
        writes.append({"model": "PositionWorkflowResponsibility", "id": mapping.pk, "auditId": result["auditId"]})
    if not mapping.active or not effective(mapping) or mapping.responsibility_id != duty.responsibility_id or mapping.workflow_node_id != node.pk:
        raise SupplyAdmissionError("WORKFLOW_RESPONSIBILITY_CONFLICT", "既有流程责任冲突，禁止覆盖。")
    return {"responsibleUserId": user.pk, "employeeId": employee.pk, "positionId": position.pk, "departmentId": department.pk, "positionResponsibilityId": duty.pk, "responsibilityType": RESPONSIBILITY_TYPE, "workflowResponsibilityId": mapping.pk, "roleId": role.pk, "permissionId": permission.pk, "processDefinitionId": definition.pk, "workflowNodeId": node.pk, "newObjects": writes, "idempotent": not writes}
