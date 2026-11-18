"""Native dispatch qualifications and persistence protocol for isolated TEST tasks."""
from copy import deepcopy
from decimal import Decimal,InvalidOperation
import re
from django.utils import timezone
from system.models import Position,PositionResponsibility,PositionWorkflowResponsibility,OrganizationOperatingAuditRecord,RolePermission
from pfm.formal_employee import formal_employee_queryset
from masterdata.models import MasterDataWriteRequest,ExternalIdentity
from workflow_runtime.models import BusinessStateTransition,ProcessDefinition
from workflow_runtime.action_permissions import ActionPermissionValidator,ActionPermissionPolicy,POLICIES
from . import workshop_receipt_protocol as receipt_service
from .workshop_receipt_protocol import _effective
from .operation_executor_scope import executor_scope
from .workshop_task_time import task_datetime_label
from .scheduling_primitives import _hash
from pde.order_routing_execution_service import fail as _fail
CONTRACT='PCE-TEST-WORKSHOP-TASK-V1'
MODULE='test-production-workshop-task'
SAVE_ACTION='test.workshop_task.save'
DISPATCH_ACTION='test.workshop_task.dispatch'
PROCESS='MES_PRODUCTION_OPERATION'
WORKFLOW_NODE='PRODUCTION_WORKSHOP_TASK_DISPATCH'
RESPONSIBILITY='RESP_PROD_TASK_DISPATCH_001'
OBJECT='ProductionWorkshopTask'
STATUS={'':'未建立','draft':'测试任务草稿','dispatched':'已测试派工'}
QUANTIFIED='QUANTIFIED'
NON_QUANTIFIED_REQUIRED='NON_QUANTIFIED_REQUIRED'
def register_actions():
 for action,status in ((SAVE_ACTION,'released'),(DISPATCH_ACTION,'draft')):
  roles=tuple(RolePermission.objects.filter(permission__code=action).order_by('role__code').values_list('role__code',flat=True).distinct())
  POLICIES[(MODULE,action)]=ActionPermissionPolicy(action,MODULE,action,roles,'legal_entity','planning.test_workshop_task_service.dispatch', (status,), 'single')
def task_execution_mode(task,verify_current=False):
 from .test_work_order_service import verify
 verify.validate_only(task.work_order)
 if task.work_order.usage_purpose!='TEST_BUSINESS' or task.source_snapshot.get('usagePurpose')!='TEST_BUSINESS' or task.execution_mode!='QUANTIFIED' or Decimal(task.workload_quantity)<=0 or task.workload_uom.company_id!=task.company_id:
  _fail('TEST_TASK_MODE_SOURCE_INVALID','测试任务定量模式、正数作业量或来源用途无效。')
 return {'executionMode':'QUANTIFIED'}

def _positive(value, label, nullable=False):
    if nullable and value is None:
        return value
    if type(value) is not int or value <= 0:
        _fail('WORKSHOP_TASK_PAYLOAD_INVALID', label + '必须为正式正整数身份。', 400)
    return value

def _payload(payload, dispatch=False):
    expected = {'expectedVersion', 'expectedSourceSnapshotHash', 'reason', 'idempotencyKey'}
    if not dispatch:
        expected |= {'operationId', 'taskId', 'employeeId', 'positionId'}
    if not isinstance(payload, dict) or set(payload) != expected:
        _fail('WORKSHOP_TASK_PAYLOAD_INVALID', '提交字段不符合正式车间任务动作合同。', 400)
    if not isinstance(payload['reason'], str) or not 2 <= len(payload['reason'].strip()) <= 300:
        _fail('WORKSHOP_TASK_REASON_REQUIRED', '请填写2至300字的操作原因。', 400)
    if not isinstance(payload['idempotencyKey'], str) or not 1 <= len(payload['idempotencyKey']) <= 120:
        _fail('WORKSHOP_TASK_IDEMPOTENCY_REQUIRED', '操作必须有有效防重复标识。', 400)
    if not isinstance(payload['expectedSourceSnapshotHash'], str) or not re.fullmatch('[0-9a-f]{64}', payload['expectedSourceSnapshotHash']):
        _fail('WORKSHOP_TASK_SOURCE_EXPECTATION_REQUIRED', '请重新读取正式来源后再操作。', 400)
    version = payload['expectedVersion']
    if version is not None and (type(version) is not int or version < 0):
        _fail('WORKSHOP_TASK_VERSION_INVALID', '任务版本无效。', 400)
    if dispatch and version is None:
        _fail('WORKSHOP_TASK_VERSION_REQUIRED', '正式派工须指定已保存任务版本。', 400)
    if not dispatch:
        for key in ('operationId', 'taskId', 'employeeId', 'positionId'):
            _positive(payload[key], key, nullable=key != 'operationId')

def _position_valid(position, company_id, workshop_id, operation_id, work_center_id=None):
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    return bool(position and _effective(position, today) and _effective(position.department, today)
        and position.company_id == company_id == position.department.company_id
        and position.workshop_id == workshop_id
        and executor_scope(position, company_id=company_id, workshop_id=workshop_id,
            operation_id=operation_id, work_center_id=work_center_id)['ready'])

def _candidates(company_id, workshop_id, operation_id, work_center_id=None):
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    positions = [position for position in Position.objects.filter(company_id=company_id, workshop_id=workshop_id)
        .select_related('department', 'process', 'team').order_by('code', 'pk') if _position_valid(position, company_id, workshop_id, operation_id, work_center_id)]
    employees = []
    for employee in (formal_employee_queryset(company_id=company_id).filter(position_ref_id__in=[p.pk for p in positions])
            .select_related('position_ref', 'user').only('id', 'employee_no', 'full_name', 'user_id', 'status',
                'hire_date', 'leave_date', 'resignation_date', 'position_ref_id', 'position_ref__name',
                'user__id', 'user__username', 'user__is_active', 'user__company_id').order_by('employee_no', 'pk')):
        if (not employee.user_id or not employee.user.is_active or employee.user.company_id != company_id
                or employee.hire_date and employee.hire_date > today
                or employee.leave_date and employee.leave_date <= today
                or employee.resignation_date and employee.resignation_date <= today
                or formal_employee_queryset().filter(user_id=employee.user_id).count() != 1):
            continue
        employees.append({'id': employee.pk, 'employeeId': employee.pk, 'employeeNo': employee.employee_no,
            'employeeName': employee.full_name, 'positionId': employee.position_ref_id,
            'positionName': employee.position_ref.name, 'userId': employee.user_id, 'username': employee.user.username})
    return [{'id': p.pk, 'positionId': p.pk, 'code': p.code, 'name': p.name} for p in positions], employees

class _Facts:
    def __init__(self, actor, object_id, state):
        self.actor, self.object_id, self.state = actor, object_id, state

    def read(self, module_code, object_ids):
        valid = module_code == MODULE and object_ids == [str(self.object_id)]
        return {'found': valid, 'objectIds': object_ids if valid else [], 'statuses': [self.state] if valid else [],
            'legalEntityIds': [str(self.actor.company_id)] if valid else [], 'currentStateSource': 'server',
            'reason': '' if valid else 'object_scope_mismatch'}

def _dispatcher(actor, order, workshop, action, object_id, state):
    register_actions()
    issues = []
    employee, position, department, assigned, evidence = receipt_service._employees(actor)
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    valid = bool(employee and position and department and _effective(position, today) and _effective(department, today)
        and position.company_id == department.company_id == actor.company_id and position.department_id == department.pk
        and (employee.hire_date is None or employee.hire_date <= today)
        and (employee.leave_date is None or employee.leave_date > today)
        and (employee.resignation_date is None or employee.resignation_date > today))
    if not valid:
        issues.append('分派人缺少唯一有效的同公司正式任职。')
    if not valid or assigned is None or assigned.pk != workshop.pk:
        issues.append('分派人岗位所属车间与任务范围不一致。')
    process = ProcessDefinition.objects.filter(definition_code=PROCESS, active=True, business_domain='MES').first()
    node = process.nodes.filter(node_code=WORKFLOW_NODE, business_action_code="production.task.dispatch", active=True).first() if process else None
    duties = list(PositionResponsibility.objects.filter(position=position, active=True, responsibility__code=RESPONSIBILITY,
        responsibility__status='ACTIVE', responsibility__is_active=True).select_related('responsibility')) if valid else []
    duty = duties[0] if len(duties) == 1 and _effective(duties[0].responsibility, today) else None
    mappings = list(PositionWorkflowResponsibility.objects.filter(position=position, responsibility=duty.responsibility,
        workflow_node=node, workflow_code=PROCESS, node_code=WORKFLOW_NODE, ownership_type='OWNER', active=True)) if duty and node else []
    mapping = mappings[0] if len(mappings) == 1 and _effective(mappings[0], today) else None
    if not process or not node:
        issues.append('正式车间任务／派工节点尚未生效。')
    if not duty or not mapping:
        issues.append('分派岗位缺少有效车间任务分派职责及本节点负责关系。')
    authorized, matched, native = receipt_service._authority(actor, action, workshop.department_id, order.released_by_id)
    decision = ActionPermissionValidator(fact_provider=_Facts(actor, object_id, state)).evaluate(user=actor,
        module_code=MODULE, action_code=action, object_ids=[object_id], selection_count=1,
        requested_legal_entity_id=str(actor.company_id))
    if not authorized:
        issues.append('当前账号缺少同一角色的明确动作权限及本公司数据范围。')
    elif not decision['granted']:
        if decision['decisionCode'] == 'business_state_denied' and action == DISPATCH_ACTION and state == 'dispatched':
            issues.append('任务已经正式派工，不可重复派工。')
        else:
            issues.append(decision['reason'] or '正式动作服务端校验未通过。')
    evidence.update(positionResponsibilityId=duty.pk if duty else None, workflowResponsibilityId=mapping.pk if mapping else None,
        matchedAuthorityEvidence=matched)
    return {'ready': not issues, 'statusLabel': '当前人员可分派本车间任务' if not issues else '本车间任务分派条件未通过',
        'missingItems': issues, 'currentActorEvidence': evidence, 'definitionId': process.pk if process else None,
        'nodeId': node.pk if node else None, 'authorization': native}

def _assignment(position_id, employee_id, positions, employees):
    position = next((row for row in positions if row['id'] == position_id), None)
    employee = next((row for row in employees if row['id'] == employee_id and row['positionId'] == position_id), None)
    issues = []
    if position_id is None:
        issues.append('尚未指定执行岗位。')
    elif position is None:
        issues.append('执行岗位不在本公司、本车间有效候选范围。')
    if employee_id is None:
        issues.append('尚未指定实际执行人员。')
    elif employee is None:
        issues.append('执行人员、有效任职或既有有效账号不符合所选岗位。')
    snapshot = {'positionId': position_id, 'positionName': position['name'] if position else None,
        'employeeId': employee_id, 'employeeName': employee['employeeName'] if employee else None,
        'employeeNo': employee['employeeNo'] if employee else None, 'userId': employee['userId'] if employee else None,
        'username': employee['username'] if employee else None}
    return snapshot, issues

def _state(task):
    result = {'status': task.status, 'version': task.version, 'sourceSnapshotHash': task.source_snapshot_hash,
        'assignment': task.assignment_snapshot, 'assignmentHash': task.assignment_hash,
        'dispatchedById': task.dispatched_by_id, 'dispatchedAt': task.dispatched_at.isoformat() if task.dispatched_at else None,
        'dispatchQualification': task.dispatch_qualification}
    if task.execution_mode == NON_QUANTIFIED_REQUIRED:
        result.update(executionMode=task.execution_mode, modeSourceHash=task.source_snapshot['modeSourceHash'])
    return result

def _verify_history(task):
    if not isinstance(task.source_snapshot, dict) or not isinstance(task.assignment_snapshot, dict) or not isinstance(task.dispatch_qualification, dict):
        _fail('WORKSHOP_TASK_HISTORY_INCONSISTENT', '任务正式快照结构损坏。')
    task_execution_mode(task, verify_current=False)
    events = list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=task.pk).order_by('version', 'pk'))
    if (_hash(task.source_snapshot) != task.source_snapshot_hash or _hash(task.assignment_snapshot) != task.assignment_hash
            or task.source_snapshot.get('companyId') != task.company_id or task.source_snapshot.get('sourceOperationId') != task.source_operation_id
            or task.source_snapshot.get('receiptId') != task.receipt_id or task.source_snapshot.get('workshopId') != task.workshop_id
            or task.source_snapshot.get('workOrderId') != task.work_order_id or task.source_snapshot.get('workOrderVersion') != task.work_order_version
            or task.source_snapshot.get('workCenterId') != task.work_center_id
            or task.source_snapshot.get('operation', {}).get('workloadQuantity') != task.workload_quantity
            or task.source_snapshot.get('operation', {}).get('workloadUomId') != task.workload_uom_id
            or task.assignment_snapshot.get('positionId') != task.execution_position_id
            or task.assignment_snapshot.get('employeeId') != task.execution_employee_id
            or len(events) != task.version + 1 or not events):
        _fail('WORKSHOP_TASK_HISTORY_INCONSISTENT', '任务来源、人员快照、版本或状态历史不一致。')
    previous = ''
    previous_state = None
    history = []
    process = ProcessDefinition.objects.filter(definition_code=PROCESS).first()
    node = process.nodes.filter(node_code=WORKFLOW_NODE).first() if process else None
    expected_node = {'processCode': PROCESS, 'nodeCode': WORKFLOW_NODE,
        'processId': process.pk if process else None, 'nodeId': node.pk if node else None}
    zone = task.work_order.source_snapshot['sourceSchedule'].get('timezone','Asia/Shanghai')
    for index, event in enumerate(events, 1):
        allowed = event.action_code == SAVE_ACTION and event.target_state == 'draft' and previous in ('', 'draft') or (
            event.action_code == DISPATCH_ACTION and previous == 'draft' and event.target_state == 'dispatched')
        match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', event.audit_reference or '')
        audit = OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
        after = audit.after_snapshot if audit else {}
        before = audit.before_snapshot if audit else {}
        if (not isinstance(after, dict) or not isinstance(before, dict) or not isinstance(after.get('state'), dict)
                or not isinstance(after.get('authorization'), dict) or not isinstance(after.get('workflowNode'), dict)):
            _fail('WORKSHOP_TASK_AUDIT_INCONSISTENT', '任务正式审计结构损坏。')
        audit_state = after['state']
        if (event.version != index or event.source_state != previous or not allowed or not audit
                or audit.actor_id != event.operator_id or audit.target_type != OBJECT or audit.target_id != task.pk
                or audit.organization_id != task.company_id or audit.action_code != event.action_code or audit.reason.strip() != event.reason
                or audit_state.get('status') != event.target_state
                or audit_state.get('version') != index - 1
                or audit_state.get('sourceSnapshotHash') != task.source_snapshot_hash
                or not isinstance(audit_state.get('assignment'), dict)
                or audit_state.get('assignmentHash') != _hash(audit_state.get('assignment'))
                or before.get('state') != (previous_state if previous_state is not None else {'status': ''})
                or after.get('authorization', {}).get('allowed') is not True
                or event.action_code not in after.get('authorization', {}).get('permissionCodes', [])
                or not process or not node or after.get('workflowNode') != expected_node or before.get('workflowNode') != expected_node):
            _fail('WORKSHOP_TASK_AUDIT_INCONSISTENT', '任务状态历史与正式审计不一致。')
        previous = event.target_state
        previous_state = audit_state
        history.append({'id': event.pk, 'sourceState': event.source_state, 'targetState': event.target_state,
            'sourceStateLabel': STATUS[event.source_state], 'targetStateLabel': STATUS[event.target_state],
            'actionCode': event.action_code, 'actionLabel': '测试派工' if event.action_code == DISPATCH_ACTION else '保存任务草稿',
            'operatorId': event.operator_id, 'reason': event.reason,
            'auditReference': event.audit_reference, 'version': event.version,
            'timestamp': event.timestamp.isoformat(), 'timestampLabel': task_datetime_label(event.timestamp, zone)})
    if previous != task.status or after['state'] != _state(task):
        _fail('WORKSHOP_TASK_CURRENT_STATE_INCONSISTENT', '任务当前状态不等于最后一次正式审计结果。')
    if task.status == 'dispatched' and (not task.dispatched_by_id or not task.dispatched_at
            or not task.execution_employee_id or not task.execution_position_id or not task.dispatch_qualification.get('ready')
            or events[-1].operator_id != task.dispatched_by_id
            or task.dispatch_qualification.get('currentActorEvidence', {}).get('userId') != task.dispatched_by_id
            or task.dispatch_qualification.get('currentActorEvidence', {}).get('companyId') != task.company_id
            or task.dispatch_qualification.get('currentActorEvidence', {}).get('workshopId') != task.workshop_id
            or task.dispatch_qualification.get('definitionId') != process.pk or task.dispatch_qualification.get('nodeId') != node.pk):
        _fail('WORKSHOP_TASK_DISPATCH_INCONSISTENT', '已派工任务缺少完整人员、派工人或冻结资格。')
    if task.status == 'draft' and (task.dispatched_by_id or task.dispatched_at or task.dispatch_qualification):
        _fail('WORKSHOP_TASK_DRAFT_INCONSISTENT', '草稿不得包含实际派工结果。')
    return history

def _intent(actor, action, payload, task_id=None):
    request_hash = _hash({'actorId': actor.pk, 'action': action, 'taskId': task_id, 'payload': payload})
    old = MasterDataWriteRequest.objects.filter(organization_id=actor.company_id, action_code=action,
        idempotency_key=payload['idempotencyKey']).first()
    if old and (old.status != 'COMMITTED' or old.entity_type != OBJECT or old.request_hash != request_hash):
        _fail('WORKSHOP_TASK_IDEMPOTENCY_CONFLICT', '防重复标识已用于其他人员或操作意图。')
    return request_hash, old

def _ledger(actor, action, payload, request_hash, task):
    identity, _ = ExternalIdentity.objects.get_or_create(organization_id=actor.company_id, source_system='MES_TEST_WORKSHOP_TASK',
        source_type='INTERNAL', source_object_type='ProductionWorkOrderOperation', external_id=str(task.source_operation_id),
        target_entity_type=OBJECT, defaults={'target_entity_id': str(task.pk), 'mapping_status': 'MATCH',
            'source_fingerprint': task.source_snapshot_hash, 'audit_metadata': {'usagePurpose':'TEST_BUSINESS','sourceAuthority':'SAVED_TEST_WORK_ORDER_RECEIPT'}})
    if identity.target_entity_id != str(task.pk) or identity.source_fingerprint != task.source_snapshot_hash:
        _fail('WORKSHOP_TASK_LEDGER_SOURCE_CONFLICT', '任务来源账本身份冲突。')
    MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=action, entity_type=OBJECT,
        idempotency_key=payload['idempotencyKey'], request_hash=request_hash, source_identity=identity,
        status='COMMITTED', target_entity_id=str(task.pk), result={'taskId': task.pk, 'version': task.version},
        audit_metadata={'actorId': actor.pk, 'usagePurpose':'TEST_BUSINESS'})
