"""Reused native receipt qualification/history protocol. No formal write entry."""
from copy import deepcopy
import re
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from django.utils import timezone
from pfm.formal_employee import formal_employee_queryset
from system.authorization import AuthorityEvidence, AuthorizationService
from system.models import Company,OrganizationOperatingAuditRecord,Permission,PositionResponsibility,PositionWorkflowResponsibility,RolePermission,UserRoleScopeAssignment
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.models import BusinessStateTransition,ProcessDefinition,WorkflowNodeDefinition
from .work_order_workshop_receipt_contract import ACTION,CONTRACT,DOCUMENT_TYPE,MODULE,OBJECT,PROCESS,READ_PERMISSION,RESPONSIBILITY,WORKFLOW_NODE,action_contract
from .scheduling_primitives import _hash
from pde.order_routing_execution_service import fail as _fail
formal=SimpleNamespace(_label=lambda value,zone:value.astimezone(ZoneInfo(zone)).isoformat())
LABELS={"":"尚未接收","not_received":"本车间尚未接收","received":"本车间工序已接收"}
PATHS={k:{"pathLabel":"组织结构→岗位、员工及权限，按真实范围维护"} for k in ('catalog','employee','position','authority','source')}

def _effective(row, today):
    return bool(row and getattr(row, "is_active", True)
        and (getattr(row, "effective_from", None) is None or row.effective_from <= today)
        and (getattr(row, "effective_to", None) is None or row.effective_to >= today))

def _employees(actor):
    from system.authorization_read_inputs import current_inputs
    inputs=current_inputs()
    rows=inputs.employees(actor) if inputs is not None else NotImplemented
    if rows is NotImplemented:
        rows = list(formal_employee_queryset(company_id=actor.company_id).filter(user_id=actor.pk)
            .select_related("position_ref__workshop", "department_ref")[:2])
    employee = rows[0] if len(rows) == 1 else None
    position = employee.position_ref if employee else None
    department = employee.department_ref if employee else None
    workshop = position.workshop if position and position.workshop_id else None
    company=inputs.company(actor,actor.company_id) if inputs is not None else NotImplemented
    if company is NotImplemented or company is None:
        company = Company.objects.only("id", "code", "name").get(pk=actor.company_id)
    evidence = {"userId": actor.pk, "username": actor.username, "companyId": actor.company_id,
        "companyCode": company.code, "companyName": company.name,
        "employeeId": employee.pk if employee else None, "employeeNo": employee.employee_no if employee else None,
        "employeeName": employee.full_name if employee else None, "positionId": position.pk if position else None,
        "positionCode": position.code if position else None, "positionName": position.name if position else None,
        "departmentId": department.pk if department else None, "workshopId": workshop.pk if workshop else None,
        "workshopCode": workshop.code if workshop else None, "workshopName": workshop.name if workshop else None}
    return employee, position, department, workshop, evidence

def _authority(actor, permission_code, department_id, owner_id):
    from .mes_read_indexes import authority_inputs
    indexed = authority_inputs(actor)
    if indexed is None:
        assignments = list(UserRoleScopeAssignment.objects.filter(user_id=actor.pk, organization_id=actor.company_id,
            organization__is_active=True, active=True).select_related("role").order_by("role__code", "pk"))
        grants = {row.role_id: row for row in RolePermission.objects.filter(permission__code=permission_code,
            role_id__in=[row.role_id for row in assignments])}
    else:
        assignments, by_permission = indexed
        grants = by_permission.get(permission_code, {})
    obj = {"organizationId": actor.company_id, "departmentId": department_id, "ownerUserId": owner_id}
    matched = []
    for assignment in assignments:
        if assignment.role_id not in grants or assignment.scope_code not in {"ALL", "ORGANIZATION", "DEPARTMENT", "SELF"}:
            continue
        # Native scope matching has permissive empty-object fallbacks. They are
        # not meaningful evidence for a workshop with no formal department.
        if assignment.scope_code == "DEPARTMENT" and department_id is None:
            continue
        if assignment.scope_code == "SELF" and owner_id is None:
            continue
        if AuthorizationService._scope_matches(AuthorityEvidence(role_code=assignment.role.code,
                organization_id=str(assignment.organization_id), scope_code=assignment.scope_code,
                department_id=assignment.department_id, source="system.UserRoleScopeAssignment"), actor, obj, {}):
            matched.append({"roleId": assignment.role_id, "roleCode": assignment.role.code,
                "roleName": assignment.role.name, "rolePermissionId": grants[assignment.role_id].pk,
                "roleScopeAssignmentId": assignment.pk, "scopeCode": assignment.scope_code,
                "departmentId": assignment.department_id})
    native = AuthorizationService.decide(user=actor, action_code=permission_code,
        organization_id=actor.company_id, business_object=obj)
    return bool(matched and native["allowed"]), matched, native

def _readable(actor, workshop, row):
    # Native superuser read remains read-only and never grants reception.
    if actor.is_superuser:
        return any(AuthorizationService.decide(user=actor, action_code=code, organization_id=actor.company_id,
            business_object={"organizationId": actor.company_id, "departmentId": workshop.department_id,
                "ownerUserId": row.released_by_id})["allowed"] for code in (READ_PERMISSION, "planning.view"))
    return any(_authority(actor, code, workshop.department_id, row.released_by_id)[0]
        for code in (READ_PERMISSION, "planning.view"))

def _whole_readable(actor, row):
    if actor.is_superuser:
        return any(AuthorizationService.decide(user=actor, action_code=code, organization_id=actor.company_id,
            business_object={"organizationId": actor.company_id, "ownerUserId": row.released_by_id})["allowed"]
            for code in (READ_PERMISSION, "planning.view"))
    for code in (READ_PERMISSION, "planning.view"):
        allowed, matched, _ = _authority(actor, code, None, row.released_by_id)
        if allowed and any(item["scopeCode"] in {"ALL", "ORGANIZATION", "SELF"} for item in matched):
            return True
    return False

class _OrderFacts:
    def __init__(self, actor, row):
        self.actor, self.row = actor, row

    def read(self, module_code, object_ids):
        valid = module_code == MODULE and object_ids == [str(self.row.pk)]
        return {"found": valid, "objectIds": [str(self.row.pk)] if valid else [],
            "statuses": [self.row.status] if valid else [], "legalEntityIds": [str(self.actor.company_id)] if valid else [],
            "currentStateSource": "server", "reason": "" if valid else "object_scope_mismatch"}

def _qualification(actor, row, workshop, *, source_ok):
    issues, checks = [], []
    def check(code, eligible, label, remedy, category="ACTOR_UNQUALIFIED"):
        checks.append({"checkCode": code, "complete": True, "eligible": bool(eligible), "statusLabel": label})
        if not eligible:
            issues.append({"code": "WORKSHOP_RECEIPT_" + code.upper(), "categoryCode": category,
                "categoryLabel": {"ACTOR_UNQUALIFIED": "当前人员资格不足", "CONFIGURATION_MISSING": "配置缺失",
                    "SOURCE_UNPROVEN": "来源事实未证实"}[category], "statusLabel": label,
                "remediation": dict(PATHS[remedy])})
    process = ProcessDefinition.objects.filter(definition_code=PROCESS).first()
    node = process.nodes.filter(node_code=WORKFLOW_NODE).first() if process else None
    config_ok = bool(Permission.objects.filter(code=ACTION).exists() and process and process.active
        and process.document_type == DOCUMENT_TYPE and node and node.active and node.business_action_code == ACTION)
    check("configuration", config_ok, "正式接收权限及生产流程接收节点已核实" if config_ok else "正式接收权限或流程接收节点尚未登记生效", "catalog", "CONFIGURATION_MISSING")
    employee, position, department, assigned_workshop, evidence = _employees(actor)
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    identity_ok = bool(employee and _effective(position, today) and _effective(department, today)
        and position.company_id == department.company_id == actor.company_id
        and position.department_id == department.pk
        and (employee.hire_date is None or employee.hire_date <= today)
        and (employee.leave_date is None or employee.leave_date > today)
        and (employee.resignation_date is None or employee.resignation_date > today))
    check("currentEmployment", identity_ok, "本人正式在职员工、岗位及部门有效" if identity_ok else "当前账户缺少唯一有效的同公司在职员工及岗位关系", "employee")
    workshop_ok = bool(identity_ok and assigned_workshop and assigned_workshop.pk == workshop.pk
        and assigned_workshop.company_id == actor.company_id and assigned_workshop.is_active
        and (workshop.department_id is None or workshop.department_id == department.pk))
    check("workshopAssignment", workshop_ok, "本人正式岗位所属车间与本接收范围一致" if workshop_ok else "当前岗位未明确关联本车间或所属范围不一致", "position")
    duties = list(PositionResponsibility.objects.filter(position=position, active=True,
        responsibility__code=RESPONSIBILITY, responsibility__status="ACTIVE", responsibility__is_active=True)
        .select_related("responsibility")) if identity_ok else []
    duty = duties[0] if len(duties) == 1 and _effective(duties[0].responsibility, today) else None
    mappings = list(PositionWorkflowResponsibility.objects.filter(position=position, responsibility=duty.responsibility,
        workflow_node=node, workflow_code=PROCESS, node_code=WORKFLOW_NODE, ownership_type="OWNER", active=True)) if duty and node else []
    mapping = mappings[0] if len(mappings) == 1 and _effective(mappings[0], today) else None
    responsible = bool(duty and mapping)
    check("receivingResponsibility", responsible, "生产计划承接职责及精确接收节点负责映射有效" if responsible else "当前岗位缺少有效生产计划承接职责或正式接收节点负责映射", "position")
    authorized, matched, native = _authority(actor, ACTION, workshop.department_id, row.released_by_id)
    contract = action_contract(row.pk, workshop.pk)
    decision = ActionPermissionValidator(fact_provider=_OrderFacts(actor, row)).evaluate(user=actor,
        module_code=MODULE, action_code=ACTION, object_ids=[row.pk], selection_count=1,
        requested_legal_entity_id=str(actor.company_id))
    authorized = bool(authorized and decision["granted"])
    check("actionAuthorization", authorized, "同一正式角色的明确接收权限及本公司数据范围已核实" if authorized else "当前账户缺少同一正式角色上的明确接收权限或匹配数据范围", "authority")
    check("releasedSource", source_ok, "已下达工单及当前工作中心车间范围一致" if source_ok else "工作中心归属或已接收冻结范围已改变，不能继续接收", "source", "SOURCE_UNPROVEN")
    evidence.update({"positionResponsibilityId": duty.pk if duty else None,
        "workflowResponsibilityId": mapping.pk if mapping else None, "matchedAuthorityEvidence": matched,
        "explicitAuthorityProven": authorized})
    ready = not issues and all(item["eligible"] for item in checks)
    return {"ready": ready, "qualificationProven": ready, "statusLabel": "当前人员可接收本车间工序" if ready else "本车间接收条件未通过",
        "checks": checks, "issues": issues, "currentActorEvidence": evidence,
        "definitionId": process.pk if process else None, "nodeId": node.pk if node else None,
        "nativeDecision": native}, contract

def _legacy_receipt(row):
    if row is None:
        return {"received": False, "id": None, "statusCode": "not_received", "statusLabel": LABELS["not_received"],
            "version": None, "receivedById": None, "receivedByLabel": None, "receivedAt": None,
            "receivedAtLabel": "尚未接收", "snapshotHash": None,
            "stateTransitionHistory": [], "statusTransitionCount": 0, "stateMachineConsistent": True}
    events = list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=row.pk).order_by("version", "pk"))
    if (not isinstance(row.source_snapshot, dict) or not isinstance(row.qualification_snapshot, dict)
            or row.status != "received" or row.version != 0 or row.snapshot_hash != _hash(row.source_snapshot)
            or row.qualification_hash != _hash(row.qualification_snapshot) or len(events) != 1
            or row.source_snapshot.get("workOrderId") != row.work_order_id
            or row.source_snapshot.get("workshopId") != row.workshop_id
            or row.source_snapshot.get("companyId") != row.company_id
            or row.source_snapshot.get("workOrderVersion") != row.work_order_version
            or row.source_snapshot.get("workOrderSnapshotHash") != row.work_order_snapshot_hash):
        _fail("WORKSHOP_RECEIPT_HISTORY_INCONSISTENT", "车间接收冻结来源或原生状态历史不完整。")
    event = events[0]
    match = re.fullmatch(r"OrganizationOperatingAuditRecord:([1-9][0-9]*)", event.audit_reference or "")
    audit = OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
    after = audit.after_snapshot if audit and isinstance(audit.after_snapshot, dict) else {}
    before = audit.before_snapshot if audit and isinstance(audit.before_snapshot, dict) else {}
    authorization = after.get("authorization", {})
    state = after.get("state", {})
    qualification = row.qualification_snapshot
    actor = qualification.get("currentActorEvidence", {})
    if (not isinstance(authorization, dict) or not isinstance(state, dict) or not isinstance(actor, dict)
            or not isinstance(before.get("state"), dict)
            or any(not isinstance(snapshot.get("workflowNode"), dict) for snapshot in (before, after))
            or not isinstance(row.source_snapshot.get("operations"), list)
            or any(not isinstance(item, dict) for item in row.source_snapshot["operations"])):
        _fail("WORKSHOP_RECEIPT_HISTORY_INCONSISTENT", "车间接收审计或冻结来源的结构已损坏。")
    permissions = authorization.get("permissionCodes") if isinstance(authorization, dict) else None
    if (event.version != 1 or (event.source_state, event.target_state, event.action_code) != ("", "received", ACTION)
            or event.operator_id != row.received_by_id or not audit or audit.actor_id != event.operator_id
            or audit.organization_id != row.company_id or audit.target_type != OBJECT or audit.target_id != row.pk
            or audit.action_code != ACTION or audit.reason.strip() != event.reason
            or before.get("state", {}).get("status") != "" or not isinstance(state, dict)
            or state.get("status") != "received" or state.get("snapshotHash") != row.snapshot_hash
            or state.get("receivingQualification") != qualification
            or authorization.get("allowed") is not True or not isinstance(permissions, (list, tuple))
            or any(not isinstance(code, str) for code in permissions) or not any(code in (ACTION, "*") for code in permissions)
            or qualification.get("qualificationProven") is not True
            or type(actor.get("userId")) is not int or actor.get("userId") != row.received_by_id
            or type(actor.get("companyId")) is not int or actor.get("companyId") != row.company_id
            or type(actor.get("workshopId")) is not int or actor.get("workshopId") != row.workshop_id):
        _fail("WORKSHOP_RECEIPT_AUTHORIZATION_HISTORY_INCONSISTENT", "车间接收审计的冻结人员、范围或授权证明不一致。")
    for snapshot in (before, after):
        node = snapshot.get("workflowNode", {})
        if (node.get("processCode") != PROCESS or node.get("nodeCode") != WORKFLOW_NODE
                or node.get("processId") != qualification.get("definitionId") or node.get("nodeId") != qualification.get("nodeId")):
            _fail("WORKSHOP_RECEIPT_NODE_HISTORY_INCONSISTENT", "接收审计未引用冻结的正式生产接收节点。")
    zone = row.work_order.source_snapshot["sourceSchedule"].get("timezone", "Asia/Shanghai")
    return {"received": True, "id": row.pk, "statusCode": row.status, "statusLabel": LABELS[row.status],
        "version": row.version, "receivedById": row.received_by_id,
        "receivedByLabel": actor.get("employeeName") or actor.get("username"),
        "receivedAt": row.received_at.isoformat(), "receivedAtLabel": formal._label(row.received_at, zone), "timezoneLabel": zone,
        "snapshotHash": row.snapshot_hash, "stateTransitionHistory": [{"id": event.pk,
            "sourceState": "", "targetState": "received", "sourceStateLabel": LABELS[""],
            "targetStateLabel": LABELS["received"], "actionCode": ACTION, "actionLabel": "接收本车间工序",
            "version": event.version, "operatorId": event.operator_id, "auditReference": event.audit_reference,
            "reason": event.reason, "timestamp": event.timestamp.isoformat(),
            "timestampLabel": formal._label(event.timestamp, zone)}],
        "statusTransitionCount": 1, "stateMachineConsistent": True}

def _token(actor, source, qualification):
    return _hash({"contract": CONTRACT, "action": ACTION, "actorId": actor.pk,
        "source": source, "qualification": qualification})

def _payload(payload):
    fields = {"expectedWorkOrderVersion", "expectedWorkOrderSnapshotHash", "expectedScopeSnapshotHash",
        "executionToken", "idempotencyKey", "reason"}
    if not isinstance(payload, dict) or set(payload) != fields:
        _fail("WORKSHOP_RECEIPT_FIELDS_INVALID", "接收提交字段不符合正式合同。", 400)
    if type(payload["expectedWorkOrderVersion"]) is not int or payload["expectedWorkOrderVersion"] < 0:
        _fail("WORKSHOP_RECEIPT_VERSION_INVALID", "必须提供真实工单版本。", 400)
    for key in ("expectedWorkOrderSnapshotHash", "expectedScopeSnapshotHash", "executionToken"):
        if not isinstance(payload[key], str) or not re.fullmatch(r"[0-9a-f]{64}", payload[key]):
            _fail("WORKSHOP_RECEIPT_HASH_INVALID", "必须引用本次只读取得的正式工单及范围凭据。", 400)
    for key, limit in (("idempotencyKey", 120), ("reason", 240)):
        if not isinstance(payload[key], str) or not payload[key].strip() or len(payload[key]) > limit:
            _fail("WORKSHOP_RECEIPT_REASON_REQUIRED", "请提供有效幂等标识及明确接收原因。", 400)
