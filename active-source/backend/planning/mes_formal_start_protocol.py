"""Formal assignee/qualification/history protocol; original action and predecessor authority."""
import re
from pde.routing_read_context import routing_read_phase
from decimal import Decimal
from django.utils import timezone
from pfm.models import Employee
from system.models import PositionResponsibility,PositionWorkflowResponsibility,OrganizationOperatingAuditRecord,RolePermission
from workflow_runtime.models import BusinessStateTransition,ProcessDefinition
from workflow_runtime.action_permissions import ActionPermissionValidator,ActionPermissionPolicy,POLICIES
from masterdata.models import MasterDataWriteRequest
from . import workshop_receipt_protocol as receipt_service
from .workshop_receipt_protocol import _effective
from .workshop_task_time import task_datetime_label
from .scheduling_primitives import _hash
from .operation_execution_mode import task_execution_mode
from pde.order_routing_execution_service import fail as _fail
from .operation_start_contract import PROCESS,WORKFLOW_NODE,RESPONSIBILITY,OBJECT,register_action
CONTRACT='PCE-PRODUCTION-OPERATION-START-V1'
MODULE='production-operation-start'
START_ACTION='production.operation.start'
READ_PERMISSION='production.operation.read'
NON_QUANTIFIED_REQUIRED='NON_QUANTIFIED_REQUIRED'
STATUS={'':'尚无开工记录','waiting':'待开工','started':'已开工'}
def mode_display(mode):return {'executionMode':mode['executionMode'],'executionModeLabel':'按本工序有效作业量计量'}
def _today():
    now = timezone.now()
    return timezone.localdate(now) if timezone.is_aware(now) else now.date()

def _identity(actor):
    employee, position, department, workshop, evidence = receipt_service._employees(actor)
    unique = Employee.objects.filter(user_id=actor.pk).count() == 1
    today = _today()
    valid = bool(unique and employee and position and department and workshop
        and _effective(position, today) and _effective(department, today)
        and position.company_id == department.company_id == workshop.company_id == actor.company_id
        and position.department_id == department.pk and workshop.is_active
        and (workshop.department_id is None or workshop.department_id == department.pk)
        and (employee.hire_date is None or employee.hire_date <= today)
        and (employee.leave_date is None or employee.leave_date > today)
        and (employee.resignation_date is None or employee.resignation_date > today))
    evidence['uniqueEmployeeAccountLink'] = unique
    evidence['currentEmploymentValid'] = valid
    return employee, position, department, workshop, evidence, valid

def _owned(actor, task, employee):
    assignment = task.assignment_snapshot
    return bool(employee and task.company_id == actor.company_id and task.execution_employee_id == employee.pk
        and assignment.get('employeeId') == employee.pk and assignment.get('userId') == actor.pk
        and assignment.get('username') == actor.username)

class _Facts:
    def __init__(self, actor, task, state):
        self.actor, self.task, self.state = actor, task, state

    def read(self, module_code, object_ids):
        valid = module_code == MODULE and object_ids == [str(self.task.pk)] and self.task.company_id == self.actor.company_id
        return {'found': valid, 'objectIds': object_ids if valid else [], 'statuses': [self.state] if valid else [],
            'legalEntityIds': [str(self.task.company_id)] if valid else [], 'currentStateSource': 'server',
            'reason': '' if valid else 'object_scope_mismatch'}

def _qualification(actor, task, source, predecessors, *, state):
    from .operation_executor_scope import executor_scope
    register_action()
    employee, position, department, workshop, evidence, employment_valid = _identity(actor)
    issues = []
    if not employment_valid:
        issues.append('当前账号缺少唯一有效的同公司本人任职、岗位及车间关系。')
    identity_valid = bool(employment_valid and _owned(actor, task, employee)
        and task.execution_position_id == position.pk and task.workshop_id == workshop.pk
        and task.assignment_snapshot.get('positionId') == position.pk)
    scope = executor_scope(position, company_id=task.company_id, workshop_id=task.workshop_id,
        operation_id=task.source_operation.operation_id, work_center_id=task.work_center_id)
    evidence['executorScope'] = scope
    if not identity_valid:
        issues.append('必须由任务冻结指定的执行人本人，以当前有效执行岗位开工。')
    if not scope['ready']:
        issues.extend(scope['missingItems'])
    process = ProcessDefinition.objects.filter(definition_code=PROCESS, active=True, business_domain='MES').first()
    node = process.nodes.filter(node_code=WORKFLOW_NODE, business_action_code='production.operation.start', active=True).first() if process else None
    duties = list(PositionResponsibility.objects.filter(position=position, active=True,
        responsibility__code=RESPONSIBILITY, responsibility__status='ACTIVE', responsibility__is_active=True)
        .select_related('responsibility')) if identity_valid else []
    duty = duties[0] if len(duties) == 1 and _effective(duties[0].responsibility, _today()) else None
    mappings = list(PositionWorkflowResponsibility.objects.filter(position=position, responsibility=duty.responsibility,
        workflow_node=node, workflow_code=PROCESS, node_code=WORKFLOW_NODE, ownership_type='EXECUTOR', active=True)) if duty and node else []
    mapping = mappings[0] if len(mappings) == 1 and _effective(mappings[0], _today()) else None
    if not process or not node:
        issues.append('正式工序开工节点尚未生效。')
    if not duty or not mapping:
        issues.append('执行岗位缺少有效工序开工职责及精确节点执行关系。')
    authorized, matched, native = receipt_service._authority(actor, START_ACTION, task.workshop.department_id, actor.pk)
    decision = ActionPermissionValidator(fact_provider=_Facts(actor, task, state)).evaluate(user=actor,
        module_code=MODULE, action_code=START_ACTION, object_ids=[task.pk], selection_count=1,
        requested_legal_entity_id=str(actor.company_id))
    if not authorized:
        issues.append('当前账号缺少同一角色的明确开工权限及本公司数据范围。')
    elif not decision['granted']:
        issues.append('任务已经开工，不可重复开工。' if state == 'started' and decision['decisionCode'] == 'business_state_denied'
            else decision['reason'] or '正式开工动作服务端校验未通过。')
    if not source['ready']:
        issues.append(source['statusLabel'])
    if not predecessors['ready']:
        issues.append(predecessors['statusLabel'])
    if state == 'started' and '任务已经开工，不可重复开工。' not in issues:
        issues.append('任务已经开工，不可重复开工。')
    evidence.update(positionResponsibilityId=duty.pk if duty else None,
        workflowResponsibilityId=mapping.pk if mapping else None, matchedAuthorityEvidence=matched)
    return {'ready': not issues, 'statusLabel': '本人任务满足正式开工条件' if not issues else
        '任务已开工，不可重复开工' if state == 'started' else '开工条件未通过',
        'missingItems': issues, 'currentActorEvidence': evidence, 'authorization': native,
        'definitionId': process.pk if process else None, 'nodeId': node.pk if node else None,
        'sourceFacts': source, 'predecessorFacts': predecessors, 'selfTaskOnly': True}

def _state(record):
    result = {'status': record.status, 'version': record.version, 'taskId': record.task_id,
        'taskVersion': record.task_version, 'sourceSnapshotHash': record.source_snapshot_hash,
        'assignmentHash': record.assignment_hash, 'startedById': record.started_by_id,
        'startedAt': record.started_at.isoformat(), 'reason': record.reason,
        'startQualification': record.start_qualification}
    if record.execution_mode == NON_QUANTIFIED_REQUIRED:
        result.update(executionMode=record.execution_mode, modeSourceHash=record.source_snapshot['modeSourceHash'])
    return result

def _verify_record(record, task):
    from .operation_predecessor_authority import verification_context
    with verification_context():
        return _verify_record_unscoped(record, task)

@routing_read_phase("startProof")
def _verify_record_unscoped(record, task):
    from .operation_predecessor_authority import frozen_predecessors_valid
    from .mes_evidence_graph import raw_input
    events = raw_input(task.company_id, ('start_history_rows', OBJECT, record.pk), lambda: list(
        BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=record.pk).order_by('version', 'pk')))
    event = events[0] if len(events) == 1 else None
    match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', event.audit_reference or '') if event else None
    audit = raw_input(task.company_id, ('start_audit_row', int(match[1])), lambda:
        OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first()) if match else None
    process = raw_input(task.company_id, ('start_process_row', PROCESS), lambda:
        ProcessDefinition.objects.filter(definition_code=PROCESS).first())
    node = raw_input(task.company_id, ('start_process_node_row', process.pk, WORKFLOW_NODE), lambda:
        process.nodes.filter(node_code=WORKFLOW_NODE).first()) if process else None
    expected_node = {'processCode': PROCESS, 'nodeCode': WORKFLOW_NODE,
        'processId': process.pk if process else None, 'nodeId': node.pk if node else None}
    before = audit.before_snapshot if audit else {}
    after = audit.after_snapshot if audit else {}
    qualification = record.start_qualification
    if not isinstance(qualification, dict) or any(not isinstance(qualification.get(key), dict)
            for key in ('currentActorEvidence', 'sourceFacts', 'predecessorFacts', 'authorization')):
        _fail('OPERATION_START_HISTORY_INCONSISTENT', '正式开工冻结资格结构不完整。')
    actor_evidence = qualification.get('currentActorEvidence', {})
    source_facts = qualification.get('sourceFacts', {})
    predecessor_facts = qualification.get('predecessorFacts', {})
    if not isinstance(source_facts.get('currentSourceChecks'), dict):
        _fail('OPERATION_START_HISTORY_INCONSISTENT', '正式开工冻结来源资格结构不完整。')
    frozen_qualification_valid = bool(qualification.get('ready') is True and qualification.get('selfTaskOnly') is True
        and actor_evidence.get('userId') == record.started_by_id
        and actor_evidence.get('employeeId') == record.execution_employee_id
        and actor_evidence.get('positionId') == record.execution_position_id
        and actor_evidence.get('companyId') == record.company_id and actor_evidence.get('workshopId') == record.workshop_id
        and actor_evidence.get('uniqueEmployeeAccountLink') is True and actor_evidence.get('currentEmploymentValid') is True
        and process and node and qualification.get('definitionId') == process.pk and qualification.get('nodeId') == node.pk
        and qualification.get('authorization', {}).get('allowed') is True
        and START_ACTION in qualification.get('authorization', {}).get('permissionCodes', [])
        and source_facts.get('ready') is True and source_facts.get('snapshotHash') == record.source_snapshot_hash
        and source_facts.get('currentSourceChecks', {}).get('ready') is True and source_facts.get('receiptValid') is True
        and predecessor_facts.get('ready') is True and predecessor_facts.get('routeRelationshipConsistent') is True
        and predecessor_facts.get('plannedDatesUsedAsCompletion') is False
        and frozen_predecessors_valid(task, predecessor_facts))
    valid = bool(record.status == 'started' and record.version == 0
        and record.execution_mode == task.execution_mode
        and record.task_id == task.pk and record.company_id == task.company_id
        and record.task_version == task.version and record.work_order_id == task.work_order_id
        and record.receipt_id == task.receipt_id and record.source_operation_id == task.source_operation_id
        and record.workshop_id == task.workshop_id and record.work_center_id == task.work_center_id
        and record.workload_quantity == task.workload_quantity and record.workload_uom_id == task.workload_uom_id
        and record.source_snapshot == task.source_snapshot and _hash(record.source_snapshot) == record.source_snapshot_hash == task.source_snapshot_hash
        and record.assignment_snapshot == task.assignment_snapshot and _hash(record.assignment_snapshot) == record.assignment_hash == task.assignment_hash
        and record.execution_position_id == task.execution_position_id and record.execution_employee_id == task.execution_employee_id
        and record.started_by_id == task.assignment_snapshot.get('userId') and record.reason.strip()
        and frozen_qualification_valid
        and event and event.version == 1 and event.source_state == '' and event.target_state == 'started'
        and event.action_code == START_ACTION and event.operator_id == record.started_by_id and event.reason == record.reason
        and audit and audit.actor_id == record.started_by_id and audit.organization_id == task.company_id
        and audit.target_type == OBJECT and audit.target_id == record.pk and audit.action_code == START_ACTION
        and audit.reason == record.reason and isinstance(before, dict) and isinstance(after, dict)
        and before.get('state') == {'status': ''} and after.get('state') == _state(record)
        and after.get('authorization', {}).get('allowed') is True
        and START_ACTION in after.get('authorization', {}).get('permissionCodes', [])
        and process and node and before.get('workflowNode') == after.get('workflowNode') == expected_node)
    if not valid:
        _fail('OPERATION_START_HISTORY_INCONSISTENT', '正式开工记录、冻结来源或状态审计不一致。')
    zone = task.work_order.source_snapshot['sourceSchedule'].get('timezone','Asia/Shanghai')
    history = [{'id': event.pk, 'sourceState': '', 'targetState': 'started',
        'sourceStateLabel': STATUS[''], 'targetStateLabel': STATUS['started'], 'actionCode': START_ACTION,
        'actionLabel': '开工', 'operatorId': event.operator_id, 'reason': event.reason,
        'auditReference': event.audit_reference, 'version': event.version,
        'timestamp': event.timestamp.isoformat(), 'timestampLabel': task_datetime_label(event.timestamp, zone)}]
    return {'id': record.pk, 'statusCode': record.status, 'statusLabel': STATUS[record.status],
        'taskId': task.pk, 'taskVersion': record.task_version, 'sourceSnapshotHash': record.source_snapshot_hash,
        'assignmentHash': record.assignment_hash, 'startedById': record.started_by_id,
        'startedByLabel': record.assignment_snapshot.get('employeeName'),
        'startedAt': record.started_at.isoformat(), 'startedAtLabel': task_datetime_label(record.started_at, zone),
        'reason': record.reason, 'auditReference': event.audit_reference, 'version': record.version,
        'statusTransitionHistory': history, 'statusTransitionCount': len(history), 'stateMachineConsistent': True,
        **mode_display(task_execution_mode(task, verify_current=False))}

def _payload(payload):
    expected = {'expectedVersion', 'expectedSourceSnapshotHash', 'expectedAssignmentHash', 'reason', 'idempotencyKey'}
    if not isinstance(payload, dict) or set(payload) != expected:
        _fail('OPERATION_START_PAYLOAD_INVALID', '开工提交字段不符合正式合同；时间及执行数量由服务端事实确定。', 400)
    if type(payload['expectedVersion']) is not int or payload['expectedVersion'] < 0:
        _fail('OPERATION_START_VERSION_REQUIRED', '请指定已读取任务的正式版本。', 400)
    for field in ('expectedSourceSnapshotHash', 'expectedAssignmentHash'):
        if not isinstance(payload[field], str) or not re.fullmatch('[0-9a-f]{64}', payload[field]):
            _fail('OPERATION_START_SOURCE_EXPECTATION_REQUIRED', '请重新读取任务及冻结人员来源。', 400)
    if not isinstance(payload['reason'], str) or not 2 <= len(payload['reason'].strip()) <= 300:
        _fail('OPERATION_START_REASON_REQUIRED', '请填写2至300字的开工原因。', 400)
    if not isinstance(payload['idempotencyKey'], str) or not 1 <= len(payload['idempotencyKey']) <= 120:
        _fail('OPERATION_START_IDEMPOTENCY_REQUIRED', '开工必须有有效防重复标识。', 400)

def _intent(actor, task_id, payload):
    request_hash = _hash({'actorId': actor.pk, 'action': START_ACTION, 'taskId': task_id, 'payload': payload})
    old = MasterDataWriteRequest.objects.filter(organization_id=actor.company_id, action_code=START_ACTION,
        idempotency_key=payload['idempotencyKey']).first()
    if old and (old.status != 'COMMITTED' or old.entity_type != OBJECT or old.request_hash != request_hash):
        _fail('OPERATION_START_IDEMPOTENCY_CONFLICT', '防重复标识已经用于其他人员或开工意图。')
    return request_hash, old
