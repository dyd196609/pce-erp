

# Native formal continuation: individually restored symbols; existing proofs preserved.
from copy import deepcopy

import re

from django.db import DatabaseError, IntegrityError, transaction

from django.utils import timezone

from pfm.formal_employee import formal_employee_queryset

from system.authorization import AuthorityEvidence, AuthorizationService

from system.models import (Company, OrganizationOperatingAuditRecord, Permission,
    PositionResponsibility, PositionWorkflowResponsibility, RolePermission,
    UserRoleScopeAssignment)

from workflow_runtime.action_permissions import ActionPermissionValidator

from workflow_runtime.models import BusinessStateTransition, ProcessDefinition, WorkflowNodeDefinition

from workflow_runtime.state_transitions import create_business_object_with_initial_state, record_projected_business_transition

from . import formal_scheduling_service as formal

from . import work_order_execution_service as execution

from .services import PlanningBusinessError, _plan_start_actor, record_audit

from .work_order_models import ProductionWorkOrder

from .work_order_release_admission_service import _effective

from .work_order_workshop_receipt_models import ProductionWorkOrderWorkshopReceipt as Receipt

from .work_order_workshop_receipt_contract import (ACTION, CONTRACT, DOCUMENT_TYPE, MODULE,
    OBJECT, PROCESS, READ_PERMISSION, RESPONSIBILITY, WORKFLOW_NODE, action_contract)

_hash = execution._hash

_fail = execution._fail

LABELS = {"": "尚未接收", "not_received": "本车间尚未接收", "received": "本车间工序已接收"}

PATHS = {
    "catalog": {"pathLabel": "受控登记生产工单查看、车间接收权限及正式接收节点",
        "statusLabel": "由授权管理人员完成技术目录登记；不自动赋权或任命。"},
    "employee": {"path": "/organization", "query": {"tab": "employees"},
        "pathLabel": "组织结构 → 员工档案 → 编辑既有员工 → 正式部门、岗位及登录账户",
        "statusLabel": "核对本人正式在职员工及当前有效任职；不自动选择人员。"},
    "position": {"path": "/organization", "query": {"tab": "positions"},
        "pathLabel": "组织结构 → 岗位管理 → 编辑既有岗位 → 所属车间 / 职责分配 / 流程责任",
        "statusLabel": "由用户明确维护既有岗位所属车间、生产计划承接职责及正式接收节点负责关系。"},
    "authority": {"path": "/organization", "query": {"tab": "users"},
        "pathLabel": "组织结构 → 角色管理配置权限 → 用户账户分配该角色及本公司数据范围",
        "statusLabel": "同一正式角色须同时具备明确接收权限与匹配的数据范围；读取权限不代表可接收。"},
    "source": {"path": "/planning/requirements", "query": {"section": "work-order-reception"}, "pathLabel": "业务流程中心 → MES生产流程 → 生产工单 → 只读刷新",
        "statusLabel": "核对已下达工单及正式工作中心所属车间；不改写冻结工序或正式排程。"},
}

def _actor(user):
    runtime_scope = formal._execution_boundary()
    actor = _plan_start_actor(user)
    if not Company.objects.filter(pk=actor.company_id, is_active=True).exists():
        _fail("WORKSHOP_RECEIPT_COMPANY_INACTIVE", "当前正式公司未生效。", 403)
    return actor, runtime_scope

def _employees(actor):
    rows = list(formal_employee_queryset(company_id=actor.company_id).filter(user_id=actor.pk)
        .select_related("position_ref__workshop", "department_ref")[:2])
    employee = rows[0] if len(rows) == 1 else None
    position = employee.position_ref if employee else None
    department = employee.department_ref if employee else None
    workshop = position.workshop if position and position.workshop_id else None
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
    assignments = list(UserRoleScopeAssignment.objects.filter(user_id=actor.pk, organization_id=actor.company_id,
        organization__is_active=True, active=True).select_related("role").order_by("role__code", "pk"))
    grants = {row.role_id: row for row in RolePermission.objects.filter(permission__code=permission_code,
        role_id__in=[row.role_id for row in assignments])}
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
    zone = row.work_order.source_snapshot["sourceSchedule"]["timezone"]
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

def _receipt(row):
    """Old group proof unchanged; typed anchors never imply a whole group."""
    fact=_legacy_receipt(row)
    from .operation_resource_selection_service import is_precise_anchor,precise_anchor_projection
    return precise_anchor_projection(row,fact) if is_precise_anchor(row) else fact

def _groups(row):
    operations, _ = execution._verify(row)
    presented = execution._present(row)
    by_id = {item["id"]: item for item in presented["operations"]}
    groups, unassigned, source_ok = {}, [], True
    current_relations = {}
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    for operation in operations:
        line = deepcopy(by_id[operation.pk])
        center = operation.work_center
        if center is None:
            line["statusLabel"] = "依赖承接节点，无独立加工工作中心，未分配车间" if operation.dependency_only else "缺少正式工作中心，未分配车间"
            unassigned.append(line)
            source_ok = source_ok and operation.dependency_only
            continue
        workshop = center.workshop
        valid = bool(workshop and center.company_id == row.company_id and _effective(center, today)
            and workshop.company_id == row.company_id and workshop.is_active
            and (center.department_id is None or center.department.company_id == row.company_id)
            and (workshop.department_id is None or workshop.department.company_id == row.company_id)
            and (center.department_id is None or workshop.department_id is None or center.department_id == workshop.department_id))
        declared = operation.source_snapshot.get("workshopId")
        frozen_declared = operation.source_snapshot.get("frozenStep", {}).get("workshopId")
        valid = valid and all(value is None or workshop and value == workshop.pk for value in (declared, frozen_declared))
        if workshop is None or workshop.company_id != row.company_id:
            source_ok = False
            line["statusLabel"] = "工作中心未关联本公司正式车间，未分配接收范围"
            unassigned.append(line)
            continue
        line.update(workCenterCode=center.code, workshopId=workshop.pk, workshopName=workshop.name)
        current_relations[operation.pk] = (center.pk, workshop.pk)
        group = groups.setdefault(workshop.pk, {"workshop": workshop, "operations": [], "frozenOperations": [], "sourceOk": True})
        group["sourceOk"] = group["sourceOk"] and valid
        group["operations"].append(line)
        group["frozenOperations"].append({"operationId": operation.pk, "operationSnapshotHash": operation.snapshot_hash,
            "workCenterId": center.pk, "workCenterCompanyId": center.company_id,
            "workshopId": workshop.pk, "workshopDepartmentId": workshop.department_id,
            "source": deepcopy(operation.source_snapshot)})
    receipts = {receipt.workshop_id: receipt for receipt in Receipt.objects.filter(work_order=row).order_by("pk")}
    for receipt in receipts.values():
        _receipt(receipt)
        from .operation_resource_selection_service import original_group_source
        frozen_source, supplement = original_group_source(receipt)
        if frozen_source is None:
            # A precise-only anchor has not received this original group.
            # Its existence must not make the legitimate first group action
            # permanently fail the unique (order,workshop) constraint.
            continue
        current_group = groups.get(receipt.workshop_id)
        if current_group is None:
            source_ok = False
        elif frozen_source != _source(row, current_group):
            current_group["sourceOk"] = False
        for frozen in frozen_source.get("operations", []):
            if current_relations.get(frozen.get("operationId")) != (frozen.get("workCenterId"), frozen.get("workshopId")):
                if current_group:
                    current_group["sourceOk"] = False
                moved = current_relations.get(frozen.get("operationId"))
                if moved and moved[1] in groups:
                    groups[moved[1]]["sourceOk"] = False
    return presented, groups, unassigned, bool(source_ok), receipts

def _source(row, group):
    workshop = group["workshop"]
    return {"companyId": row.company_id, "workOrderId": row.pk, "workOrderNo": row.no,
        "productionPlanId": row.production_plan_id, "workOrderVersion": row.version,
        "workOrderSnapshotHash": row.snapshot_hash, "quantity": str(row.quantity),
        "uomId": row.uom_id, "uomCode": row.source_snapshot["uomCode"], "uomLabel": row.source_snapshot["uomLabel"],
        "workshopId": workshop.pk, "workshopCode": workshop.code, "workshopName": workshop.name,
        "workshopDepartmentId": workshop.department_id, "operations": group["frozenOperations"]}

def _token(actor, source, qualification):
    return _hash({"contract": CONTRACT, "action": ACTION, "actorId": actor.pk,
        "source": source, "qualification": qualification})

def _rows(actor, runtime_scope):
    rows = ProductionWorkOrder.objects.filter(company_id=actor.company_id, status="released",
        usage_purpose='PRODUCTION_USE',production_plan__isnull=False,source_schedule__usage_purpose='PRODUCTION_USE')
    if runtime_scope is not None:
        company_code = Company.objects.filter(pk=actor.company_id).values_list("code", flat=True).first()
        if runtime_scope.get("companyId") != actor.company_id or runtime_scope.get("companyCode") != company_code:
            _fail("WORKSHOP_RECEIPT_RUNTIME_SCOPE_INVALID", "当前运行环境未开放本公司工单范围。", 403)
        rows = rows.filter(production_plan_id=runtime_scope["productionPlanId"], production_plan__plan_no=runtime_scope["productionPlanNo"])
    return rows.select_related("production_plan").order_by("pk")

def _read_workshop_reception(*, user, production_plan_id=None,response_mode=None,locate_latest_own_action=False):
    from .workshop_reception_read_projection import response_mode as parse_mode,SELECTED_DETAIL
    from .workshop_reception_read_projection import (validate_locator_request,latest_own_action_candidate,
        verified_view_location,view_location_fields)
    response_mode=parse_mode(response_mode)
    validate_locator_request(locate_latest_own_action,response_mode)
    actor, runtime_scope = _actor(user)
    if production_plan_id is not None and (type(production_plan_id) is not int or production_plan_id <= 0):
        _fail("WORKSHOP_RECEIPT_PLAN_INVALID", "请选择有效正式生产计划身份。", 400)
    options, selected = [], None
    location_operations=[];location_orders={};candidate=None
    for row in _rows(actor, runtime_scope):
        presented, groups, unassigned, source_ok, receipts = _groups(row)
        visible = {key: group for key, group in groups.items() if _readable(actor, group["workshop"], row)}
        if not visible:
            continue
        options.append({"workOrderId": row.pk, "workOrderNo": row.no, "productionPlanId": row.production_plan_id,
            "productionPlanNo": row.production_plan.plan_no, "quantityLabel": presented["quantityLabel"],
            "statusLabel": presented["statusLabel"], "workshopIds": list(visible)})
        location_orders[row.pk]=(row,presented,visible,unassigned,source_ok,receipts)
        if locate_latest_own_action and (production_plan_id is None or row.production_plan_id==production_plan_id):
            operation_ids=None if _whole_readable(actor,row) else {
                item['id'] for group in visible.values() for item in group['operations']}
            location_operations.extend(operation for operation in row.operations.select_related('operation')
                if operation_ids is None or operation.pk in operation_ids)
        if row.production_plan_id == production_plan_id:
            selected = row, presented, visible, unassigned, source_ok, receipts
    if production_plan_id is not None and selected is None:
        _fail("WORKSHOP_RECEIPT_NOT_VISIBLE", "未找到当前账户有权查看的本公司已下达工单。", 403)
    if locate_latest_own_action:
        candidate=latest_own_action_candidate(actor,location_operations)
        if candidate:
            selected=location_orders[candidate[0].work_order_id]
    if not actor.is_superuser and not options:
        # Do not turn a receive-only grant into a company work-order directory.
        has_read = UserRoleScopeAssignment.objects.filter(user_id=actor.pk, organization_id=actor.company_id,
            active=True, role__rolepermission__permission__code__in=(READ_PERMISSION, "planning.view")).exists()
        if not has_read:
            _fail("WORKSHOP_RECEIPT_READ_DENIED", "当前账户缺少正式工单查看权限及匹配的数据范围。", 403)
    evidence = _employees(actor)[-1]
    result = {"contractVersion": CONTRACT, "moduleCode": MODULE, "factSource": "server", "currentStateSource": "server",
        **view_location_fields(locate_latest_own_action),
        'responseMode':response_mode,
        'perOperationResourceFactsKind':'RESOURCE_RECEIPT_SUMMARY' if response_mode==SELECTED_DETAIL else 'FULL_EXECUTION_ADMISSION',
        "companyId": actor.company_id, "currentActorEvidence": evidence, "workOrderOptions": options,
        "productionPlanId": None, "productionPlanNo": None, "workOrder": None, "scopes": [], "unassignedOperations": [],
        "visibleOperationCount": 0, "scopeVisibilityLabel": "仅显示当前正式查看权限及数据范围内的车间工序",
        "scopeSummary": {"scopeCount": 0, "assignedOperationCount": 0, "unassignedOperationCount": 0,
            "dependencyOnlyUnassignedCount": 0, "receivedScopeCount": 0, "statusLabel": "请选择已下达工单"},
        "statusLabel": "请选择有权查看的已下达生产工单", "businessWriteCount": 0, "auditWriteCount": 0}
    if selected is None:
        return result
    row, presented, groups, unassigned, source_ok, receipts = selected
    from .operation_resource_source import read_order_resources,read_order_resource_summaries
    resource_by_operation = (read_order_resource_summaries(row,actor=actor) if response_mode==SELECTED_DETAIL else
        {operation.pk: context['facts'] for operation, context in read_order_resources(row, actor=actor)})
    if candidate:
        result.update(view_location_fields(True,verified_view_location(actor,candidate,resource_by_operation[candidate[0].pk])))
    if not _whole_readable(actor, row):
        unassigned = []
    # This list records the original order's absent work-center assignment.
    # A later selection/precise receipt must be visible without rewriting it.
    unassigned = [{**line, 'frozenScopeStatusLabel': line['statusLabel'],
        'scopeBasisLabel': '原工单冻结工作中心为空；不代表当前有效资源未选择',
        'resourceSource': resource_by_operation[line['id']],
        'effectiveWorkshop': resource_by_operation[line['id']]['effectiveWorkshop'],
        'statusLabel': '原冻结未归属；' + resource_by_operation[line['id']]['resourceSelectionStatusLabel']
            + '；' + resource_by_operation[line['id']]['receiptStatusLabel']}
        for line in unassigned]
    scopes = []
    for key, group in groups.items():
        workshop, source = group["workshop"], _source(row, group)
        qualification, contract = _qualification(actor, row, workshop, source_ok=source_ok and group["sourceOk"])
        receipt = _receipt(receipts.get(key))
        if receipt["received"] and receipt.get("scopeSnapshotHash",receipt["snapshotHash"]) != _hash(source):
            receipt["statusLabel"] = "原冻结范围已接收；当前工序范围已变化，不能视为全部已接收"
        enabled = qualification["ready"] and not receipt["received"]
        reason = "本车间已保存接收记录，不重复接收" if receipt["received"] else "" if enabled else qualification["statusLabel"]
        operation_lines = [{**line, 'resourceSource': resource_by_operation[line['id']],
            'originalReceiptWorkshop': resource_by_operation[line['id']]['originalReceiptWorkshop'],
            'effectiveWorkshop': resource_by_operation[line['id']]['effectiveWorkshop'],
            'effectiveReceptionAuthority': resource_by_operation[line['id']]['effectiveReceptionAuthority']}
            for line in group['operations']]
        scopes.append({"workshopId": key, "workshopCode": workshop.code, "workshopName": workshop.name,
            "scopeBasisLabel": "按原工单冻结工作中心的当前车间归组；正式新增资源选择及精确接收另有证明",
            "departmentId": workshop.department_id, "operationIds": [line["id"] for line in group["operations"]],
            "operationCount": len(group["operations"]), "workCenterIds": sorted({line["workCenterId"] for line in group["operations"]}),
            "operations": operation_lines, "scopeSnapshotHash": _hash(source), "qualification": qualification,
            "receipt": receipt, "actionContract": contract,
            "availableAction": {"key": "receive", "actionCode": ACTION, "displayName": contract["displayName"],
                "apiPath": contract["apiPath"], "enabled": enabled, "disabledReason": reason,
                "executionToken": _token(actor, source, qualification) if enabled else None}})
    header_keys = ("id", "no", "generated", "released", "statusCode", "statusLabel", "version", "quantity", "quantityLabel",
        "uomId", "uomCode", "uomLabel", "materialId", "materialCode", "materialName", "sourceScheduleId", "snapshotHash", "operationCount")
    header = {key: presented[key] for key in header_keys}
    header["productionPlanId"] = row.production_plan_id
    result.update(productionPlanId=row.production_plan_id, productionPlanNo=row.production_plan.plan_no,
        workOrder=header, scopes=scopes, unassignedOperations=unassigned,
        visibleOperationCount=sum(group["operationCount"] for group in scopes) + len(unassigned),
        scopeSummary={"scopeCount": len(scopes), "assignedOperationCount": sum(group["operationCount"] for group in scopes),
            "unassignedOperationCount": len(unassigned), "dependencyOnlyUnassignedCount": sum(bool(line["dependencyOnly"]) for line in unassigned),
            "receivedScopeCount": sum(group["receipt"]["received"] for group in scopes),
            "statusLabel": "此处按原工单冻结工作中心归组；原冻结未归属清单保留历史，当前资源及精确接收以独立正式证明为准"},
        statusLabel="已下达工单车间接收事实已读取")
    return result

def read_workshop_reception(*,user,production_plan_id=None,response_mode=None,locate_latest_own_action=False):
    from pde.operation_allocation_source_handoff_service import allocation_admission_context
    actor,_=_actor(user)
    with allocation_admission_context(user=actor):
        return _read_workshop_reception(user=actor,production_plan_id=production_plan_id,response_mode=response_mode,
            locate_latest_own_action=locate_latest_own_action)

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

def _audit(actor, row, receipt, qualification, reason):
    node = WorkflowNodeDefinition.objects.select_related("process_definition").filter(
        pk=qualification["nodeId"], process_definition_id=qualification["definitionId"], node_code=WORKFLOW_NODE,
        process_definition__definition_code=PROCESS, business_action_code=ACTION, active=True, process_definition__active=True).first()
    if node is None:
        _fail("WORKSHOP_RECEIPT_NODE_CHANGED", "正式接收节点已改变，接收事务未保存。")
    audit = record_audit(user=actor, action_code=ACTION, target=receipt, target_type=OBJECT,
        target_no=row.no + " / " + receipt.source_snapshot["workshopName"], before={"status": ""},
        after={"status": "received", "snapshotHash": receipt.snapshot_hash,
            "receivingQualification": deepcopy(qualification), "workOrderId": row.pk,
            "workshopId": receipt.workshop_id, "receiptContract": CONTRACT},
        authorization=qualification["nativeDecision"], reason=reason)
    formal_node = {"processId": node.process_definition_id, "processCode": PROCESS,
        "processName": node.process_definition.definition_name, "nodeId": node.pk,
        "nodeCode": WORKFLOW_NODE, "nodeName": node.node_name, "sequence": node.sequence}
    audit.before_snapshot["workflowNode"] = formal_node
    audit.after_snapshot["workflowNode"] = formal_node
    audit.save(update_fields=["before_snapshot", "after_snapshot"])
    return audit

def _writes(idempotent=False):
    return {"idempotent": idempotent, "businessWriteCount": 0 if idempotent else 1,
        "workshopReceiptCreatedCount": 0 if idempotent else 1, "auditWriteCount": 0 if idempotent else 1,
        "stateTransitionWriteCount": 0 if idempotent else 1, "technicalMutexWriteCount": 1,
        "workOrderCreatedCount": 0, "workOrderReleasedCount": 0, "workOrderOperationCreatedCount": 0,
        "productionScheduleCreatedCount": 0, "resourceOccupancyCreatedCount": 0, "resourceOccupancyReleasedCount": 0}

def receive_workshop_scope(*, user, work_order_id, workshop_id, payload):
    _payload(payload)
    if type(work_order_id) is not int or type(workshop_id) is not int or min(work_order_id, workshop_id) <= 0:
        _fail("WORKSHOP_RECEIPT_ID_INVALID", "必须指定正式工单及车间。", 400)
    actor, runtime_scope = _actor(user)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            actor, runtime_scope = _actor(user)
            row = _rows(actor, runtime_scope).filter(pk=work_order_id).first()
            if row is None:
                _fail("WORKSHOP_RECEIPT_ORDER_NOT_RELEASED", "工单不存在、不属于本公司或尚未下达。", 403)
            _, groups, _, source_ok, _ = _groups(row)
            group = groups.get(workshop_id)
            if group is None or not _readable(actor, group["workshop"], row):
                _fail("WORKSHOP_RECEIPT_SCOPE_NOT_VISIBLE", "当前账户无权查看本车间正式工序范围。", 403)
            qualification, _ = _qualification(actor, row, group["workshop"], source_ok=source_ok and group["sourceOk"])
            if not qualification["ready"]:
                _fail("WORKSHOP_RECEIPT_QUALIFICATION_REQUIRED", qualification["statusLabel"], 403)
            source = _source(row, group)
            from .operation_resource_selection_service import is_precise_anchor, supplement_original_group
            existing_anchor = Receipt.objects.filter(work_order=row, workshop_id=workshop_id).first()
            if is_precise_anchor(existing_anchor):
                if (payload["expectedWorkOrderVersion"] != row.version
                        or payload["expectedWorkOrderSnapshotHash"] != row.snapshot_hash
                        or payload["expectedScopeSnapshotHash"] != _hash(source)
                        or payload["executionToken"] != _token(actor, source, qualification)):
                    _fail("WORKSHOP_RECEIPT_SOURCE_CHANGED", "原冻结车间组或接收责任已变化，请只读重新读取。")
                created=supplement_original_group(actor,row,group,existing_anchor,source,qualification,payload)
                writes=_writes(not created)
                writes.update(workshopReceiptCreatedCount=0,workshopReceiptSupplementCreatedCount=int(created),
                    originalReceiptUpdatedCount=0)
                facts=read_workshop_reception(user=actor,production_plan_id=row.production_plan_id)
                facts.update(businessWriteCount=writes['businessWriteCount'],auditWriteCount=writes['auditWriteCount'])
                return facts,writes
            request_hash = _hash({"action": ACTION, "actorId": actor.pk, "companyId": actor.company_id,
                "workOrderId": row.pk, "workshopId": workshop_id, "sourceHash": _hash(source), "payload": payload})
            previous = Receipt.objects.filter(company_id=actor.company_id, idempotency_key=payload["idempotencyKey"]).first()
            if previous:
                if previous.request_hash != request_hash or previous.work_order_id != row.pk or previous.workshop_id != workshop_id:
                    _fail("WORKSHOP_RECEIPT_IDEMPOTENCY_CONFLICT", "该幂等标识已用于不同人员、来源或接收意图。")
                _receipt(previous)
                writes = _writes(True)
            else:
                if Receipt.objects.filter(work_order=row, workshop_id=workshop_id).exists():
                    _fail("WORKSHOP_RECEIPT_ALREADY_RECEIVED", "本车间已有正式接收记录，请只读刷新查看。")
                if (payload["expectedWorkOrderVersion"] != row.version
                        or payload["expectedWorkOrderSnapshotHash"] != row.snapshot_hash
                        or payload["expectedScopeSnapshotHash"] != _hash(source)
                        or payload["executionToken"] != _token(actor, source, qualification)):
                    _fail("WORKSHOP_RECEIPT_SOURCE_CHANGED", "工单、当前人员资格或工作中心车间范围已改变，请重新只读刷新。")
                receipt = create_business_object_with_initial_state(model=Receipt, initial_state="received",
                    company_id=actor.company_id, work_order=row, workshop_id=workshop_id,
                    work_order_version=row.version, work_order_snapshot_hash=row.snapshot_hash,
                    source_snapshot=source, snapshot_hash=_hash(source), qualification_snapshot=qualification,
                    qualification_hash=_hash(qualification), idempotency_key=payload["idempotencyKey"],
                    request_hash=request_hash, received_by=actor)
                audit = _audit(actor, row, receipt, qualification, payload["reason"].strip())
                record_projected_business_transition(object_type=OBJECT, object_id=receipt.pk,
                    source_state="", target_state="received", action_code=ACTION, operator=actor,
                    reason=payload["reason"].strip(), audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
                    allowed_transitions={("", "received")})
                _receipt(receipt)
                writes = _writes()
            facts = read_workshop_reception(user=actor, production_plan_id=row.production_plan_id)
            facts.update(businessWriteCount=writes["businessWriteCount"], auditWriteCount=writes["auditWriteCount"])
            return facts, writes
    except IntegrityError:
        _fail("WORKSHOP_RECEIPT_CONCURRENT_CONFLICT", "另一接收事务已保存或幂等标识冲突，请先只读刷新；未自动重试。")
    except DatabaseError:
        _fail("WORKSHOP_RECEIPT_TRANSACTION_FAILED", "接收事务未完成并已回滚，请先只读刷新；不会自动重试。", 503)
