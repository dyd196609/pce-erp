

# Native formal continuation: individually restored symbols; existing proofs preserved.
import hashlib

import re

from django.utils import timezone

from pfm.formal_employee import formal_employee_queryset

from system.authorization import AuthorityEvidence, AuthorizationService

from system.models import (Company, OrganizationOperatingAuditRecord, Permission,
    PositionResponsibility, PositionWorkflowResponsibility, RolePermission,
    UserRoleScopeAssignment)

from workflow_runtime.action_permissions import ActionPermissionValidator

from workflow_runtime.facts import status_transition_facts

from workflow_runtime.models import BusinessStateTransition, ProcessDefinition

from .work_order_release_admission_contract import (ACTION, ALLOWED_ORDER_STATES,
    CONTRACT, DOCUMENT_TYPE, MODULE, PROCESS, RESPONSIBILITY, WORKFLOW_NODE, action_contract)

CATEGORIES = {"CONFIGURATION_MISSING": "配置缺失", "ACTOR_UNQUALIFIED": "当前人员资格不足",
    "BUSINESS_BLOCKED": "业务条件受阻", "SOURCE_UNPROVEN": "来源事实未证实"}

PATHS = {
    "permission": {"pathLabel": "受控权限登记（当前页面不提供创建入口）",
        "statusLabel": "先受控登记生产工单下达权限；权限目录只能查看，不会自动创建或授权。"},
    "workflow": {"path": "/process-designer", "pathLabel": "业务流程中心 → 流程设计中心 → 正式流程及节点",
        "statusLabel": "由授权管理人员核对正式生产流程及生产工单下达节点；不自动创建。"},
    "position": {"path": "/organization", "query": {"tab": "positions"},
        "pathLabel": "组织结构 → 岗位管理 → 编辑既有责任岗位 → 职责分配 / 流程责任",
        "statusLabel": "核对计划物控岗位职责及正式节点负责关系；不自动任命人员。"},
    "role": {"path": "/organization", "query": {"tab": "roles"},
        "pathLabel": "组织结构 → 角色管理 → 选择或新增角色 → 配置权限",
        "statusLabel": "由授权管理人员为所选正式角色明确配置生产工单下达权限；角色沿用系统自动编号，不要求固定编码。"},
    "user": {"path": "/organization", "query": {"tab": "users"},
        "pathLabel": "组织结构 → 用户账户 → 既有业务账户分配角色 → 当前公司与数据范围",
        "statusLabel": "核对当前业务账户在同一正式角色上的明确下达权限和公司数据范围，不以管理员读取权限代替。"},
    "employee": {"path": "/organization", "query": {"tab": "employees"},
        "pathLabel": "组织结构 → 员工档案 → 编辑既有员工 → 关联登录账户",
        "statusLabel": "核对既有账户的正式员工关联及员工部门、岗位、在职与有效期；不自动新建、绑定或任命。"},
    "order": {"path": "/sales/orders", "pathLabel": "业务流程中心 → 产品研发与工程管理中心 → PDE产品研发工程流程 → 生产需求准入 → 原订单",
        "statusLabel": "查看原订单当前状态及既有审批 / 确认事实；不重放审批或更改订单。"},
    "schedule": {"path": "/planning/requirements", "query": {"section": "formal-scheduling"},
        "pathLabel": "业务流程中心 → APS → 生产计划正式排程与占用",
        "statusLabel": "核对原计划、已保存有效排程及当前工程来源，保持已有排程及占用。"},
}

def _effective(row, today):
    return bool(row and getattr(row, "is_active", True)
        and (getattr(row, "effective_from", None) is None or row.effective_from <= today)
        and (getattr(row, "effective_to", None) is None or row.effective_to >= today))

def _audit_part(audit, side, key):
    snapshot = getattr(audit, side + "_snapshot", None)
    value = snapshot.get(key) if isinstance(snapshot, dict) else None
    return value if isinstance(value, dict) else {}

def _history(row, object_type, company_id, allowed, initial):
    events = list(BusinessStateTransition.objects.filter(object_type=object_type, object_id=row.pk)
        .select_related("workflow_instance").order_by("version", "pk"))
    history = [{"id": event.pk, "objectType": event.object_type, "objectId": event.object_id,
        "sourceState": event.source_state, "targetState": event.target_state, "operatorId": event.operator_id,
        "actionCode": event.action_code, "auditReference": event.audit_reference,
        "workflowInstanceId": event.workflow_instance_id, "version": event.version,
        "reason": event.reason, "timestamp": event.timestamp.isoformat()} for event in events]
    valid = bool(events) and [e.version for e in events] == list(range(1, len(events) + 1))
    valid = valid and events[0].source_state in initial and events[-1].target_state == row.status
    for index, event in enumerate(events):
        match = re.fullmatch(r"OrganizationOperatingAuditRecord:([1-9][0-9]*)", event.audit_reference)
        audit = OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
        authorization = _audit_part(audit, "after", "authorization")
        permissions = authorization.get("permissionCodes")
        permissions = permissions if isinstance(permissions, (list, tuple)) else []
        valid = valid and bool((event.source_state, event.target_state, event.action_code) in allowed
            and (not index or events[index - 1].target_state == event.source_state)
            and event.reason.strip() and event.timestamp and audit and audit.reason.strip()
            and audit.organization_id == company_id and audit.target_type == object_type
            and audit.target_id == row.pk and audit.actor_id == event.operator_id
            and audit.action_code == event.action_code
            and _audit_part(audit, "before", "state").get("status", "") == event.source_state
            and _audit_part(audit, "after", "state").get("status") == event.target_state
            and authorization.get("allowed") is True
            and any(code in ("*", event.action_code) for code in permissions if isinstance(code, str)))
    return status_transition_facts(history=history, state_machine_consistent=bool(valid)), events

def _order_proof(order, company_id):
    from sales.services import ORDER_ACTIONS, PROCESS_CODE
    allowed = {(source, target, action) for action, sources, target, _ in ORDER_ACTIONS.values() for source in sources}
    allowed.add(("draft", "confirmed", "sales.order.confirm"))
    proof, events = _history(order, "SalesOrder", company_id, allowed, {"draft"})
    if not proof["stateMachineConsistent"]:
        return proof
    valid = proof["stateMachineConsistent"]
    approval = next((event for event in events if event.target_state == "approved"), None)
    confirmation = next((event for event in events if event.target_state == "confirmed"), None)
    if approval:
        instance = approval.workflow_instance
        valid = valid and bool(instance and instance.document_type == "SalesOrder"
            and instance.document_id == order.pk and instance.status == "approved"
            and instance.process_definition.definition_code == PROCESS_CODE
            and order.approved_by_id == approval.operator_id and order.created_by_id != approval.operator_id)
        decisions = list(instance.tasks.filter(status="approved", required_role_code="sales_order_approver")
            .values_list("pk", flat=True)) if instance else []
        from workflow_runtime.models import ApprovalDecision
        decision = ApprovalDecision.objects.filter(task_id__in=decisions, actor_id=approval.operator_id,
            decision="approved").first()
        valid = valid and bool(decision and decision.decision_hash == hashlib.sha256(
            f"{decision.task_id}|{decision.actor_id}|{decision.action_id}|approved".encode()).hexdigest())
        if decision:
            audit_id = approval.audit_reference.rsplit(":", 1)[-1]
            audit = OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).first()
            state = _audit_part(audit, "after", "state")
            valid = valid and state.get("requestId") == decision.action_id and state.get("idempotencyKey") == decision.idempotency_key
    else:
        valid = valid and bool(confirmation and order.confirmed_by_id == confirmation.operator_id)
    proof["stateMachineConsistent"] = bool(valid)
    return proof

class _PlanFacts:
    def __init__(self, actor, plan):
        self.actor, self.plan = actor, plan

    def read(self, module_code, object_ids):
        valid = module_code == MODULE and object_ids == [str(self.plan.pk)]
        return {"found": valid, "objectIds": [str(self.plan.pk)] if valid else [],
            "statuses": [self.plan.status] if valid else [], "legalEntityIds": [str(self.actor.company_id)] if valid else [],
            "currentStateSource": "server", "reason": "" if valid else "object_scope_mismatch"}

def assess_release_admission(*, actor, plan, schedule, reception, source_checks):
    contract = action_contract()
    issues, checks = [], []

    def issue(code, category, label, remedy):
        issues.append({"code": code, "categoryCode": category, "categoryLabel": CATEGORIES[category],
            "statusLabel": label, "remediation": dict(PATHS[remedy])})

    def check(code, label, eligible, *, complete=True, details=None):
        checks.append({"checkCode": code, "complete": complete, "eligible": eligible,
            "statusLabel": label, **({"details": details} if details is not None else {})})

    from pde.formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
    demand = plan.planning_requirement.demand
    item = demand.sales_order_item
    order = item.sales_order if item else None
    purpose = FormalManufacturingEligibilityService.resolve(item)
    check("orderPurpose", purpose["statusLabel"], purpose["formalManufacturingEligible"], details=purpose)
    if not purpose["formalManufacturingEligible"]:
        issue(purpose["decisionCode"], "BUSINESS_BLOCKED", purpose["message"], "order")
    scope_ok = bool(order and order.company_id == actor.company_id
        and order.department.company_id == actor.company_id and order.customer.company_id == actor.company_id
        and demand.department.company_id == actor.company_id
        and all(material.company_id == actor.company_id for material in
            (plan.material, plan.planning_requirement.material, demand.material, item.material))
        and len({plan.material_id, plan.planning_requirement.material_id, demand.material_id, item.material_id}) == 1
        and demand.source_type == "sales_order" and demand.source_document_type == "SalesOrderItem"
        and demand.source_document_id == str(item.pk) and demand.source_document_no == order.order_no
        and plan.source_id == str(plan.planning_requirement_id))
    check("sourceScope", "当前公司、订单行、需求及生产计划正式来源范围一致" if scope_ok else "正式订单至生产计划来源范围未通过", scope_ok)
    if not scope_ok:
        issue("WORK_ORDER_RELEASE_SOURCE_SCOPE_INVALID", "SOURCE_UNPROVEN", "生产计划无法沿同公司正式关系唯一追溯原订单行及需求。", "schedule")
    order_proof = _order_proof(order, actor.company_id) if order else None
    state_ok = bool(order and order.status in ALLOWED_ORDER_STATES and order_proof["stateMachineConsistent"])
    check("orderState", f"当前订单状态：{order.get_status_display()}；核对既有审批或兼容确认事实" if order else "无正式订单行",
        state_ok, details={"orderId": order.pk if order else None, "stateProof": order_proof})
    if not state_ok:
        issue("WORK_ORDER_RELEASE_ORDER_STATE_INVALID", "BUSINESS_BLOCKED", "当前订单状态或既有审批 / 确认事实不满足工单下达准入；已完成、关闭或取消订单不能继续下达。", "order")
    plan_proof, plan_events = _history(plan, "ProductionPlan", actor.company_id,
        {("", "draft", "planning.production_plan.confirm"), ("draft", "confirmed", "planning.production_plan.confirm")}, {""})
    confirmation = next((event for event in plan_events if event.target_state == "confirmed"), None)
    plan_owner_proven = bool(plan.confirmed_by_id and confirmation and plan.confirmed_by_id == confirmation.operator_id)
    plan_proof["confirmationActorConsistent"] = plan_owner_proven
    plan_proof["stateMachineConsistent"] = bool(plan_proof["stateMachineConsistent"] and plan_owner_proven)
    plan_ok = plan.status == "confirmed" and plan_proof["stateMachineConsistent"]
    check("planState", f"当前计划状态：{plan.get_status_display()}；核对原生确认及审计", plan_ok, details=plan_proof)
    if not plan_ok:
        issue("WORK_ORDER_RELEASE_PLAN_STATE_INVALID", "BUSINESS_BLOCKED", "生产计划必须保持已确认且原生确认状态与审计事实完整。", "schedule")
    schedule_ok = bool(schedule and schedule["productionPlanId"] == plan.pk and reception["ready"])
    check("formalSchedule", reception["statusLabel"], schedule_ok)
    if not schedule_ok:
        issue("WORK_ORDER_RELEASE_SCHEDULE_NOT_READY", "SOURCE_UNPROVEN", "尚无通过接收核验的当前有效已保存正式排程。", "schedule")
    check("engineeringSources", source_checks["statusLabel"], source_checks["ready"])
    if not source_checks["ready"]:
        issue("WORK_ORDER_RELEASE_SOURCE_NOT_READY", "SOURCE_UNPROVEN", "当前工程、分配、资源或冻结时间依据未通过原接收来源复核。", "schedule")

    responsibility, _native_actor_decision = _plan_actor_qualification(actor, plan, plan_owner_proven, issue, check)
    ready = not issues and all(row["complete"] and row["eligible"] for row in checks)
    label = ("下达准入通过，尚未生成或下达工单" if ready else
        "下达准入受阻：职责与权限配置缺失" if any(row["categoryCode"] == "CONFIGURATION_MISSING" for row in issues) else "下达准入受阻")
    remediations = []
    for row in issues:
        if row["remediation"] not in remediations:
            remediations.append(row["remediation"])
    return {"contractVersion": CONTRACT, "ready": ready, "statusLabel": label, "issues": issues,
        "checks": checks, "actionContract": contract, "remediations": remediations}, responsibility


def _plan_actor_qualification(actor, plan, plan_owner_proven, issue, check):
    demand=plan.planning_requirement.demand
    process = ProcessDefinition.objects.filter(definition_code=PROCESS).first()
    node = process.nodes.filter(node_code=WORKFLOW_NODE).first() if process else None
    permission = Permission.objects.filter(code=ACTION).first()
    configs = ((permission, "PERMISSION", "缺少生产工单下达正式权限登记", "permission"),
        (process and process.active and process.document_type == DOCUMENT_TYPE, "PROCESS", "正式生产流程未登记、生效或业务对象不匹配", "workflow"),
        (node and node.active and node.business_action_code == ACTION, "NODE", "正式生产工单下达节点未登记、生效或动作编码不匹配", "workflow"))
    config_ok = all(bool(valid) for valid, *_ in configs)
    for valid, name, label, remedy in configs:
        if not valid:
            issue(f"WORK_ORDER_RELEASE_{name}_MISSING", "CONFIGURATION_MISSING", label, remedy)
    check("configuration", "正式动作及流程配置完整" if config_ok else "正式动作及流程配置缺失", config_ok)

    today = timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    employees = list(formal_employee_queryset(company_id=actor.company_id).filter(user_id=actor.pk)
        .select_related("position_ref", "department_ref")[:2])
    employee = employees[0] if len(employees) == 1 else None
    position = employee.position_ref if employee else None
    department = employee.department_ref if employee else None
    identity_ok = bool(employee and actor.is_active and Company.objects.filter(pk=actor.company_id, is_active=True).exists()
        and _effective(position, today) and _effective(department, today)
        and position.company_id == actor.company_id and department.company_id == actor.company_id
        and position.department_id == department.pk)
    duties = list(PositionResponsibility.objects.filter(position=position, active=True,
        responsibility__code=RESPONSIBILITY, responsibility__is_active=True, responsibility__status="ACTIVE")
        .select_related("responsibility")) if identity_ok else []
    duty = duties[0] if len(duties) == 1 and _effective(duties[0].responsibility, today) else None
    mappings = list(PositionWorkflowResponsibility.objects.filter(position=position, responsibility=duty.responsibility,
        workflow_node=node, workflow_code=PROCESS, node_code=WORKFLOW_NODE, ownership_type="OWNER", active=True)) if duty and node else []
    mapping = mappings[0] if len(mappings) == 1 and _effective(mappings[0], today) else None
    qualification = bool(identity_ok and duty and mapping and config_ok)
    if not identity_ok:
        issue("WORK_ORDER_RELEASE_ACTOR_IDENTITY_INVALID", "ACTOR_UNQUALIFIED", "当前账户缺少唯一有效的同公司在职员工、部门及岗位关系或效期不符。", "employee")
    elif not duty:
        issue("WORK_ORDER_RELEASE_PMC_RESPONSIBILITY_MISSING", "ACTOR_UNQUALIFIED", "当前岗位缺少有效计划物控职责。", "position")
    elif not mapping:
        issue("WORK_ORDER_RELEASE_WORKFLOW_MAPPING_MISSING", "CONFIGURATION_MISSING", "当前岗位尚无有效、精确的正式下达节点负责映射。", "position")
    scope_object = {"organizationId": actor.company_id, "departmentId": demand.department_id,
        "ownerUserId": plan.confirmed_by_id}
    assignments = list(UserRoleScopeAssignment.objects.filter(user_id=actor.pk,
        organization_id=actor.company_id, organization__is_active=True, active=True)
        .select_related("role").order_by("role__code", "pk"))
    permissions_by_role = {row.role_id: row for row in RolePermission.objects.filter(
        permission=permission, role_id__in={row.role_id for row in assignments})} if permission else {}
    # Permission and typed scope must belong to the very same formal role. The
    # shared providers aggregate roles, so their result alone is insufficient.
    matched = [(row, permissions_by_role[row.role_id]) for row in assignments
        if row.role_id in permissions_by_role and (row.scope_code != "SELF" or plan_owner_proven)
        and AuthorizationService._scope_matches(
            AuthorityEvidence(role_code=row.role.code, organization_id=str(row.organization_id),
                scope_code=row.scope_code, department_id=row.department_id,
                source="system.UserRoleScopeAssignment"), actor, scope_object, {})]
    scope, role_permission = matched[0] if matched else (None, None)
    role = scope.role if scope else None
    decision = ActionPermissionValidator(fact_provider=_PlanFacts(actor, plan)).evaluate(user=actor,
        module_code=MODULE, action_code=ACTION, object_ids=[plan.pk], selection_count=1,
        requested_legal_entity_id=str(actor.company_id))
    native_decision = AuthorizationService.decide(user=actor, action_code=ACTION,
        organization_id=actor.company_id, business_object=scope_object)
    authorized = bool(scope and role_permission and decision["granted"] and native_decision["allowed"])
    if not authorized:
        issue("WORK_ORDER_RELEASE_EXPLICIT_AUTHORITY_REQUIRED", "ACTOR_UNQUALIFIED", "当前账户必须在同一正式角色上具有明确下达权限和匹配的本公司数据范围；管理员读取权限不能代替。",
            "role" if assignments and not permissions_by_role else "user")
    qualification = qualification and authorized
    company = Company.objects.only("id", "code", "name").get(pk=actor.company_id)
    evidence = {"userId": actor.pk, "username": actor.username, "companyId": actor.company_id,
        "companyCode": company.code, "companyName": company.name,
        "employeeId": employee.pk if employee else None, "positionId": position.pk if position else None,
        "departmentId": department.pk if department else None,
        "positionResponsibilityId": duty.pk if duty else None,
        "workflowResponsibilityId": mapping.pk if mapping else None,
        "roleId": role.pk if role else None, "roleCode": role.code if role else None,
        "roleName": role.name if role else None,
        "rolePermissionId": role_permission.pk if role_permission else None,
        "roleScopeAssignmentId": scope.pk if scope else None, "explicitAuthorityProven": authorized,
        "matchedAuthorityEvidence": [{"roleId": row.role_id, "roleCode": row.role.code,
            "roleName": row.role.name, "rolePermissionId": grant.pk,
            "roleScopeAssignmentId": row.pk, "scopeCode": row.scope_code,
            "departmentId": row.department_id} for row, grant in matched]}
    check("responsibility", "当前人员计划物控岗位及下达负责关系已核实" if qualification else "当前人员下达责任资格不足",
        qualification, details=evidence)
    check("actionAuthorization", "同一正式角色的下达权限及匹配的本公司范围已核实" if authorized else "当前人员缺少明确下达权限或公司范围", authorized,
        details={"sharedDecision": decision, "nativeDecision": native_decision, "explicitAuthorityProven": authorized})
    responsibility = {"preparationRoleLabel": "计划物控：工单准备及后续下达", "executionRoleLabel": "车间：后续接收和执行",
        "qualificationProven": qualification, "statusLabel": "当前人员计划物控岗位及下达负责关系已核实" if qualification else "当前人员下达责任资格不足", "currentActorEvidence": evidence,
        "definitionId": process.pk if process else None, "nodeId": node.pk if node else None,
        "mappingId": mapping.pk if mapping else None}
    return responsibility, native_decision


def qualify_continuation_planner(actor, plan):
    """Same native PMC identity, node, same-role permission and company scope.

    A frozen-source correction does not pretend the old schedule is newly
    releasable. Only its existing planner qualification is reused here.
    """
    action_contract()
    proof, events = _history(plan, "ProductionPlan", actor.company_id,
        {("", "draft", "planning.production_plan.confirm"), ("draft", "confirmed", "planning.production_plan.confirm")}, {""})
    confirmation = next((event for event in events if event.target_state == "confirmed"), None)
    owner = bool(plan.confirmed_by_id and confirmation and plan.confirmed_by_id == confirmation.operator_id)
    issues = []
    def issue(code, category, label, remedy):
        issues.append({"code": code, "statusLabel": label})
    def check(*args, **kwargs):
        pass
    responsibility, native = _plan_actor_qualification(actor, plan, owner, issue, check)
    ready = bool(proof['stateMachineConsistent'] and plan.status == 'confirmed'
        and responsibility['qualificationProven'] and not issues)
    return {"ready": ready, "responsibility": responsibility, "nativeDecision": native,
        "issues": issues, "planStateProof": proof}
