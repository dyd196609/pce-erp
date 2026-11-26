"""Delivered formal task history kernel; TEST parents are explicitly refused."""
import re
from .work_order_execution_service import _hash,_fail
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition,ProcessDefinition
from .workshop_task_contract import OBJECT,SAVE_ACTION,DISPATCH_ACTION,PROCESS,WORKFLOW_NODE
from .operation_execution_mode import task_execution_mode,NON_QUANTIFIED_REQUIRED
from .workshop_task_time import task_datetime_label
STATUS={'':'未建立','draft':'草稿','dispatched':'已派工'}

def _state(task):
    result = {'status': task.status, 'version': task.version, 'sourceSnapshotHash': task.source_snapshot_hash,
        'assignment': task.assignment_snapshot, 'assignmentHash': task.assignment_hash,
        'dispatchedById': task.dispatched_by_id, 'dispatchedAt': task.dispatched_at.isoformat() if task.dispatched_at else None,
        'dispatchQualification': task.dispatch_qualification}
    if task.execution_mode == NON_QUANTIFIED_REQUIRED:
        result.update(executionMode=task.execution_mode, modeSourceHash=task.source_snapshot['modeSourceHash'])
    return result

def _verify_history(task):
    from .custody_dependency_reads import read_rows
    from .test_work_order_service import require_formal_work_order

    require_formal_work_order(task.work_order)
    if not isinstance(task.source_snapshot, dict) or not isinstance(task.assignment_snapshot, dict) or not isinstance(task.dispatch_qualification, dict):
        _fail('WORKSHOP_TASK_HISTORY_INCONSISTENT', '任务正式快照结构损坏。')
    frozen_mode=task_execution_mode(task, verify_current=False)
    from .operation_continuation_service import is_receipt_mode
    reference=frozen_mode['referenceWorkload'] if is_receipt_mode(frozen_mode) else task.source_snapshot.get('operation',{})
    expected_quantity=reference.get('quantity') if is_receipt_mode(frozen_mode) else reference.get('workloadQuantity')
    expected_unit=reference.get('uomId') if is_receipt_mode(frozen_mode) else reference.get('workloadUomId')
    events = read_rows('workshop_task_transitions', (task.company_id, task.pk),
        lambda: tuple(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=task.pk).order_by('version', 'pk')))
    if (_hash(task.source_snapshot) != task.source_snapshot_hash or _hash(task.assignment_snapshot) != task.assignment_hash
            or task.source_snapshot.get('companyId') != task.company_id or task.source_snapshot.get('sourceOperationId') != task.source_operation_id
            or task.source_snapshot.get('receiptId') != task.receipt_id or task.source_snapshot.get('workshopId') != task.workshop_id
            or task.source_snapshot.get('workOrderId') != task.work_order_id or task.source_snapshot.get('workOrderVersion') != task.work_order_version
            or task.source_snapshot.get('workCenterId') != task.work_center_id
            or expected_quantity != task.workload_quantity
            or expected_unit != task.workload_uom_id
            or task.assignment_snapshot.get('positionId') != task.execution_position_id
            or task.assignment_snapshot.get('employeeId') != task.execution_employee_id
            or len(events) != task.version + 1 or not events):
        _fail('WORKSHOP_TASK_HISTORY_INCONSISTENT', '任务来源、人员快照、版本或状态历史不一致。')
    previous = ''
    previous_state = None
    history = []
    process = read_rows('workshop_task_process', (task.company_id, PROCESS),
        lambda: ProcessDefinition.objects.filter(definition_code=PROCESS).first())
    node = read_rows('workshop_task_node', (task.company_id, process.pk, WORKFLOW_NODE),
        lambda: process.nodes.filter(node_code=WORKFLOW_NODE).first()) if process else None
    expected_node = {'processCode': PROCESS, 'nodeCode': WORKFLOW_NODE,
        'processId': process.pk if process else None, 'nodeId': node.pk if node else None}
    zone = task.work_order.source_snapshot['sourceSchedule']['timezone']
    for index, event in enumerate(events, 1):
        allowed = event.action_code == SAVE_ACTION and event.target_state == 'draft' and previous in ('', 'draft') or (
            event.action_code == DISPATCH_ACTION and previous == 'draft' and event.target_state == 'dispatched')
        match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', event.audit_reference or '')
        audit = read_rows('workshop_task_audit', (task.company_id, int(match[1])),
            lambda: OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first()) if match else None
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
            'actionCode': event.action_code, 'actionLabel': '正式派工' if event.action_code == DISPATCH_ACTION else '保存任务草稿',
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


# Native formal continuation: individually restored symbols; existing proofs preserved.
from copy import deepcopy

from decimal import Decimal, InvalidOperation

from django.db import DatabaseError, IntegrityError, transaction

from django.utils import timezone

from masterdata.models import CodeRule, ExternalIdentity, MasterDataWriteRequest, UnitOfMeasure

from pfm.formal_employee import formal_employee_queryset

from system.models import Position, PositionResponsibility, PositionWorkflowResponsibility, OrganizationOperatingAuditRecord

from workflow_runtime.action_permissions import ActionPermissionValidator

from workflow_runtime.state_transitions import create_business_object_with_initial_state, record_projected_business_transition, transition_business_object

from . import work_order_workshop_receipt_service as receipt_service

from . import formal_scheduling_service as formal

from .workshop_task_models import ProductionWorkshopTask as Task

from .workshop_task_contract import (CONTRACT, MODULE, READ_PERMISSION, SAVE_ACTION, DISPATCH_ACTION,
    PROCESS, WORKFLOW_NODE, RESPONSIBILITY, OBJECT, NUMBER_ENTITY, action_contracts, register_actions)

from .services import record_audit, PlanningBusinessError

from .work_order_release_admission_service import _effective

from .operation_executor_scope import executor_scope

from .operation_resource_read_scope import scoped_execution_read

from .operation_execution_mode import (resolve_operation_execution_mode, task_execution_mode,
    source_with_mode, mode_display, QUANTIFIED, NON_QUANTIFIED_REQUIRED)

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
    node = process.nodes.filter(node_code=WORKFLOW_NODE, business_action_code=DISPATCH_ACTION, active=True).first() if process else None
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

def _sources(actor, runtime_scope,work_order_id=None):
    from .operation_resource_source import read_order_resources
    assigned_workshop = receipt_service._employees(actor)[3]
    if assigned_workshop is None:
        return []
    options = []
    orders=receipt_service._rows(actor,runtime_scope)
    if work_order_id is not None:orders=orders.filter(pk=work_order_id)
    for order in orders:
        existing = {task.source_operation_id: task.source_snapshot_hash for task in
            Task.objects.filter(work_order=order).only('source_operation_id', 'source_snapshot_hash')}
        for operation, context in read_order_resources(order, actor=actor):
            workshop, receipt = context['workshop'], context['receipt']
            # A company-scoped read grant never widens the dispatcher's formal
            # assigned workshop. Use the native effective resource (including
            # exact resource selection), not a guessed department mapping.
            if workshop is None or workshop.pk != assigned_workshop.pk:
                continue
            center = context.get('workCenter', operation.work_center)
            mode = resolve_operation_execution_mode(operation, actor=actor)
            # First-choice proof supplies the effective execution resource;
            # the released operation and its original NULL remain immutable.
            selected_resource_path = operation.work_center_id is None
            special = mode['executionMode'] != QUANTIFIED or selected_resource_path
            if not special and (workshop is None or receipt is None):
                continue
            department_id = workshop.department_id if workshop else None
            if not receipt_service._authority(actor, READ_PERMISSION, department_id, order.released_by_id)[0]:
                continue
            line = {'id': operation.pk, **{key: deepcopy(value) for key, value in operation.source_snapshot.items() if key != 'frozenStep'}}
            from .operation_continuation_service import is_receipt_mode
            if is_receipt_mode(mode):
                reference=mode['referenceWorkload']
                line.update(dependencyOnly=False,workloadQuantity=reference['quantity'],
                    workloadUomId=reference['uomId'],workloadLabel=reference['quantity']+' '+reference['uomLabel'])
            if selected_resource_path:
                line.update(workCenterId=center.pk if center else None,
                    workCenterName=center.name if center else None)
            if not special and (line['dependencyOnly'] or not line['workCenterId'] or not line['workloadQuantity'] or not line['workloadUomId']):
                continue
            try:
                workload_valid = Decimal(line['workloadQuantity']).is_finite() and Decimal(line['workloadQuantity']) > 0
            except (InvalidOperation, TypeError, ValueError):
                workload_valid = False
            unit_valid = UnitOfMeasure.objects.filter(pk=line['workloadUomId'], company_id=actor.company_id, is_active=True).exists()
            if mode['executionMode'] == NON_QUANTIFIED_REQUIRED:
                workload_valid = ((line['workloadQuantity'] is None and line['workloadUomId'] is None)
                    or workload_valid and unit_valid)
                unit_valid = workload_valid
                line['workloadLabel'] = ('不统计实际完成数量；正式参考作业量：' + line['workloadLabel']
                    if line['workloadQuantity'] is not None else '不单独计量，保留正式空数量／单位')
            source, resource = source_with_mode(context['source'], mode), context['facts']
            if not mode['ready']:
                resource['blockingReasons'].extend(mode['blockingReasons'])
                resource['sourceReady'] = False
            if resource['blockingReasons']:
                resource['statusLabel'] = '；'.join(dict.fromkeys(resource['blockingReasons']))
            source_hash = _hash(source)
            existing_consistent = operation.pk not in existing or existing[operation.pk] == source_hash
            if not existing_consistent:
                resource['blockingReasons'].append('已有任务仍冻结原归属；本轮不自动迁移或重建任务，请先按正式方案处理已有任务承接。')
                resource['sourceReady'] = False
                resource['statusLabel'] = resource['blockingReasons'][0]
            display = {**line, 'operationId': operation.pk, 'formalOperationId': operation.operation_id,
                'workOrderId': order.pk, 'workOrderNo': order.no, 'workOrderVersion': order.version,
                'receiptId': receipt.pk if receipt else None, 'workshopId': workshop.pk if workshop else None,
                'workshopName': workshop.name if workshop else None,
                'workCenterCode': center.code if center else None,
                'operationSnapshotHash': operation.snapshot_hash, 'sourceSnapshotHash': source_hash,
                'sourceConsistent': bool(resource['sourceReady'] and workload_valid and unit_valid),
                'receipt': resource['originalReceipt'], 'resourceSource': resource,
                'originalReceiptWorkshop': resource['originalReceiptWorkshop'],
                'effectiveWorkshop': resource['effectiveWorkshop'],
                'effectiveReceptionAuthority': resource['effectiveReceptionAuthority'], **mode_display(mode),
                'executionModeFacts': mode,
                'referenceWorkshop': {'id': operation.operation.workshop_id, 'name': operation.operation.workshop.name}
                    if operation.operation.workshop_id else None}
            options.append((display, source, order, workshop))
    return options

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

def _present(task, source_display=None):
    history = _verify_history(task)
    operation = task.source_snapshot['operation']
    zone = task.work_order.source_snapshot['sourceSchedule']['timezone']
    return {'id': task.pk, 'no': task.no, 'statusCode': task.status, 'statusLabel': STATUS[task.status], 'version': task.version,
        'operationId': task.source_operation_id, 'operationName': operation['operationName'], 'sequence': operation['sequence'],
        'workOrderId': task.work_order_id, 'workOrderNo': task.work_order.no, 'workshopId': task.workshop_id,
        'workshopName': task.workshop.name, 'receiptId': task.receipt_id, 'workCenterId': task.work_center_id,
        'workCenterName': task.work_center.name if task.source_snapshot.get('executionResourceSelectionRef') else operation['workCenterName'], 'workloadQuantity': task.workload_quantity,
        'workloadUomId': task.workload_uom_id, 'workloadLabel': (str(task.workload_quantity)+' '+task.workload_uom.name
            if task.source_snapshot.get('modeSourceProof',{}).get('continuationInputPlan') else operation['workloadLabel']),
        'positionId': task.execution_position_id, 'positionName': task.assignment_snapshot.get('positionName'),
        'employeeId': task.execution_employee_id, 'employeeName': task.assignment_snapshot.get('employeeName'),
        'employeeUsername': task.assignment_snapshot.get('username'), 'sourceSnapshotHash': task.source_snapshot_hash,
        'sourceConsistent': bool(source_display and source_display['sourceConsistent'] and source_display['sourceSnapshotHash'] == task.source_snapshot_hash),
        'createdAtLabel': task_datetime_label(task.created_at, zone),
        'dispatchedByLabel': task.dispatch_qualification.get('currentActorEvidence', {}).get('employeeName'),
        'dispatchedAtLabel': task_datetime_label(task.dispatched_at, zone) if task.dispatched_at else '尚未派工',
        'stateTransitionHistory': history, 'statusTransitionHistory': history,
        'statusTransitionCount': len(history), 'stateMachineConsistent': True,
        'actualStartCount': 0, 'actualReportCount': 0, 'executionPermissionProven': False,
        **mode_display(task_execution_mode(task, verify_current=False))}

@scoped_execution_read
def read_workshop_tasks(*, user, work_order_id=None, operation_id=None):
    actor, runtime_scope = receipt_service._actor(user)
    for key, value in (('工单', work_order_id), ('工序', operation_id)):
        if value is not None:
            _positive(value, key)
    if not receipt_service._authority(actor, READ_PERMISSION, None, None)[0]:
        # Object-scoped readers are evaluated against each real source below.
        from system.models import UserRoleScopeAssignment
        if not UserRoleScopeAssignment.objects.filter(user_id=actor.pk, active=True, organization_id=actor.company_id,
                role__rolepermission__permission__code=READ_PERMISSION).exists():
            _fail('WORKSHOP_TASK_READ_DENIED', '当前账号没有车间任务查看权限及有效公司范围。', 403)
    if operation_id is not None:
        from .work_order_models import ProductionWorkOrderOperation
        operation=ProductionWorkOrderOperation.objects.filter(pk=operation_id,work_order__company_id=actor.company_id).first()
        if operation is None or work_order_id is not None and work_order_id!=operation.work_order_id:
            _fail('WORKSHOP_TASK_SOURCE_NOT_VISIBLE','工序与本公司本工单不一致。',403)
        work_order_id=operation.work_order_id
    sources = _sources(actor, runtime_scope,work_order_id)
    sources = [entry for entry in sources if work_order_id is None or entry[0]['workOrderId'] == work_order_id]
    selected = next((entry for entry in sources if entry[0]['id'] == operation_id), None) if operation_id else None
    if operation_id and selected is None:
        _fail('WORKSHOP_TASK_SOURCE_NOT_VISIBLE', '所选工序尚未接收、不可派工或不在当前查看范围。', 403)
    by_op = {entry[0]['id']: entry[0] for entry in sources}
    tasks = [_present(task, by_op.get(task.source_operation_id)) for task in Task.objects.filter(
        company_id=actor.company_id, source_operation_id__in=by_op).select_related('work_order', 'workshop').order_by('-pk')]
    task_by_op = {task['operationId']: task for task in tasks}
    for display, _, _, _ in sources:
        task = task_by_op.get(display['id'])
        display.update(taskId=task['id'] if task else None, taskNo=task['no'] if task else None)
    evidence = receipt_service._employees(actor)[-1]
    contracts = action_contracts()
    disabled = lambda contract, reason: {**contract, 'enabled': False, 'disabledReason': reason}
    result = {'contractVersion': CONTRACT, 'moduleCode': MODULE, 'factSource': 'server', 'currentStateSource': 'server',
        'companyId': actor.company_id, 'currentActorEvidence': evidence, 'operationOptions': [entry[0] for entry in sources],
        'selectedOperation': None, 'candidatePositions': [], 'candidateEmployees': [], 'tasks': tasks, 'selectedTask': None,
        'qualification': {'ready': False, 'missingItems': ['请选择已接收的加工工序。'], 'statusLabel': '请选择工序'},
        'availableActions': {key: disabled(value, '请先选择已接收工序。') for key, value in contracts.items()},
        'statusLabel': '车间任务事实已读取', 'businessWriteCount': 0, 'auditWriteCount': 0,
        'actualDispatchCount': 0, 'actualStartCount': 0, 'actualReportCount': 0,
        'candidateMeaningLabel': '候选仅证明本次任务分派的任职及账号关系，不代表具备后续开工或报工权限。',
        'maintenancePath': {'path': '/organization', 'query': {'tab': 'employees'},
            'pathLabel': '组织结构→岗位管理维护所属车间／部门及有效期→员工档案维护有效任职与既有账号'},
        'actualStartOrReportSupported': False}
    if selected:
        display, source, order, workshop = selected
        task = task_by_op.get(display['id'])
        if workshop is None or display['receiptId'] is None or display['workCenterId'] is None:
            positions, employees = [], []
            qualification = {'ready': False, 'missingItems': [], 'currentActorEvidence': evidence,
                'statusLabel': '本工序尚无正式执行资源及精确接收证明'}
        else:
            positions, employees = _candidates(actor.company_id, workshop.pk, display['formalOperationId'], display['workCenterId'])
            qualification = _dispatcher(actor, order, workshop, SAVE_ACTION, display['id'], 'released')
        if not display['sourceConsistent']:
            qualification['missingItems'].extend(display['resourceSource']['blockingReasons'] or ['本工序数量或正式单位不符合当前派工要求。'])
            qualification['ready'] = False
            qualification['statusLabel'] = '；'.join(qualification['missingItems'])
        save_enabled = qualification['ready'] and (task is None or task['statusCode'] == 'draft')
        dispatch_q = {'ready': False, 'statusLabel': '请先保存任务草稿', 'missingItems': ['请先保存任务草稿。']}
        if task:
            dispatch_q = (_dispatcher(actor, order, workshop, DISPATCH_ACTION, task['id'], task['statusCode'])
                if workshop is not None else {'ready': False, 'missingItems': ['本工序尚无正式执行资源及精确接收证明。'],
                    'statusLabel': '正式派工条件未通过'})
            current_assignment, missing = _assignment(task['positionId'], task['employeeId'], positions, employees)
            dispatch_q['missingItems'].extend(missing)
            persisted_task = Task.objects.only('assignment_snapshot').get(pk=task['id'])
            if not missing and current_assignment != persisted_task.assignment_snapshot:
                dispatch_q['missingItems'].append('执行岗位或人员资料已变化，请核对并重新保存草稿。')
            if not task['sourceConsistent']:
                dispatch_q['missingItems'].extend(display['resourceSource']['blockingReasons'] or ['任务来源与当前正式接收范围不一致。'])
            if task['statusCode'] != 'draft':
                reason = '任务已经正式派工，不可重复派工。'
                if reason not in dispatch_q['missingItems']:
                    dispatch_q['missingItems'].append(reason)
            dispatch_q['ready'] = not dispatch_q['missingItems']
            dispatch_q['statusLabel'] = ('任务已正式派工，不可重复派工' if task['statusCode'] == 'dispatched'
                else '已保存任务满足正式派工条件' if dispatch_q['ready'] else '正式派工条件未通过')
            task['dispatchQualification'] = dispatch_q
            task['missingItems'] = dispatch_q['missingItems']
        contracts = action_contracts(task['id'] if task else None)
        result.update(selectedOperation=display, selectedTask=task, candidatePositions=positions, candidateEmployees=employees,
            qualification=qualification, availableActions={
                'saveDraft': {**contracts['saveDraft'], 'enabled': save_enabled,
                    'disabledReason': '' if save_enabled else '已派工不可修改' if task and task['statusCode'] == 'dispatched' else '；'.join(qualification['missingItems'])},
                'dispatch': {**contracts['dispatch'], 'enabled': dispatch_q['ready'],
                    'disabledReason': '' if dispatch_q['ready'] else '；'.join(dispatch_q['missingItems'])}})
    return result

def _intent(actor, action, payload, task_id=None):
    request_hash = _hash({'actorId': actor.pk, 'action': action, 'taskId': task_id, 'payload': payload})
    old = MasterDataWriteRequest.objects.filter(organization_id=actor.company_id, action_code=action,
        idempotency_key=payload['idempotencyKey']).first()
    if old and (old.status != 'COMMITTED' or old.entity_type != OBJECT or old.request_hash != request_hash):
        _fail('WORKSHOP_TASK_IDEMPOTENCY_CONFLICT', '防重复标识已用于其他人员或操作意图。')
    return request_hash, old

def _ledger(actor, action, payload, request_hash, task):
    identity, _ = ExternalIdentity.objects.get_or_create(organization_id=actor.company_id, source_system='MES_WORKSHOP_TASK',
        source_type='INTERNAL', source_object_type='ProductionWorkOrderOperation', external_id=str(task.source_operation_id),
        target_entity_type=OBJECT, defaults={'target_entity_id': str(task.pk), 'mapping_status': 'MATCH',
            'source_fingerprint': task.source_snapshot_hash, 'audit_metadata': {'formalTaskOnly': True}})
    if identity.target_entity_id != str(task.pk) or identity.source_fingerprint != task.source_snapshot_hash:
        _fail('WORKSHOP_TASK_LEDGER_SOURCE_CONFLICT', '任务来源账本身份冲突。')
    MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=action, entity_type=OBJECT,
        idempotency_key=payload['idempotencyKey'], request_hash=request_hash, source_identity=identity,
        status='COMMITTED', target_entity_id=str(task.pk), result={'taskId': task.pk, 'version': task.version},
        audit_metadata={'actorId': actor.pk, 'formalTaskOnly': True})

def _audit(actor, task, action, before, qualification, reason, target_state, target_version):
    after = {**_state(task), 'status': target_state, 'version': target_version}
    audit = record_audit(user=actor, action_code=action, target=task, target_type=OBJECT, target_no=task.no,
        before=before, after=after, authorization=qualification['authorization'], reason=reason.strip())
    node = {'processCode': PROCESS, 'nodeCode': WORKFLOW_NODE, 'processId': qualification['definitionId'], 'nodeId': qualification['nodeId']}
    audit.before_snapshot['workflowNode'] = node
    audit.after_snapshot['workflowNode'] = node
    audit.save(update_fields=['before_snapshot', 'after_snapshot'])
    return audit

def _selected(actor, operation_id):
    facts = read_workshop_tasks(user=actor, operation_id=operation_id)
    if not facts['qualification']['ready']:
        _fail('WORKSHOP_TASK_DISPATCHER_UNQUALIFIED', '；'.join(facts['qualification']['missingItems']), 403)
    return facts

def save_task_draft(*, user, payload):
    _payload(payload)
    actor, _ = receipt_service._actor(user)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            facts = _selected(actor, payload['operationId'])
            display = facts['selectedOperation']
            request_hash, replay = _intent(actor, SAVE_ACTION, payload)
            if replay:
                task = Task.objects.get(pk=int(replay.target_entity_id), company_id=actor.company_id)
                return read_workshop_tasks(user=actor, operation_id=task.source_operation_id), _writes(True)
            if display['sourceSnapshotHash'] != payload['expectedSourceSnapshotHash']:
                _fail('WORKSHOP_TASK_SOURCE_CHANGED', '正式来源已变化，请重新读取。')
            existing = Task.objects.select_for_update().filter(source_operation_id=payload['operationId']).first()
            if existing and (payload['taskId'] != existing.pk or payload['expectedVersion'] != existing.version or existing.status != 'draft'):
                _fail('WORKSHOP_TASK_DUPLICATE_OR_STALE', '该工序已有任务、任务已派工或版本已变化，请先刷新。')
            if not existing and (payload['taskId'] is not None or payload['expectedVersion'] is not None):
                _fail('WORKSHOP_TASK_NOT_FOUND', '指定草稿不存在，请重新读取。')
            assignment, missing = _assignment(payload['positionId'], payload['employeeId'], facts['candidatePositions'], facts['candidateEmployees'])
            invalid_position = payload['positionId'] is not None and not any(p['id'] == payload['positionId'] for p in facts['candidatePositions'])
            invalid_employee = payload['employeeId'] is not None and not any(e['id'] == payload['employeeId'] and e['positionId'] == payload['positionId'] for e in facts['candidateEmployees'])
            if invalid_position or invalid_employee:
                _fail('WORKSHOP_TASK_ASSIGNEE_INVALID', '执行岗位与员工必须来自同一合法有效任职及既有账号候选。', 403)
            qualification = facts['qualification']
            if existing:
                task = existing
                _verify_history(task)
                before = _state(task)
                task.execution_position_id = payload['positionId']
                task.execution_employee_id = payload['employeeId']
                task.assignment_snapshot, task.assignment_hash = assignment, _hash(assignment)
                task.save(update_fields=['execution_position', 'execution_employee', 'assignment_snapshot', 'assignment_hash', 'updated_at'])
                audit = _audit(actor, task, SAVE_ACTION, before, qualification, payload['reason'], 'draft', task.version + 1)
                transition_business_object(business_object=task, object_type=OBJECT, source_state='draft', target_state='draft',
                    action_code=SAVE_ACTION, operator=actor, reason=payload['reason'], audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
                    allowed_transitions={('draft', 'draft')})
            else:
                source_entry = next(entry for entry in _sources(actor, receipt_service._actor(actor)[1],display['workOrderId']) if entry[0]['id'] == payload['operationId'])
                source = source_entry[1]
                if _hash(source)!=display['sourceSnapshotHash']:
                    _fail('WORKSHOP_TASK_SOURCE_CHANGED','派工准备期间正式来源已变化，请重新读取。')
                rule = CodeRule.objects.filter(company_id=actor.company_id, entity_type=NUMBER_ENTITY).first()
                if rule is None or not rule.prefix or not 1 <= rule.seq_length <= 20 or rule.current_seq < 0:
                    _fail('WORKSHOP_TASK_NUMBER_RULE_REQUIRED', '正式车间任务编号规则尚未登记或无效。')
                task = create_business_object_with_initial_state(model=Task, initial_state='draft', company_id=actor.company_id,
                    no=CodeRule.next_code(company_id=actor.company_id, entity_type=NUMBER_ENTITY), work_order_id=display['workOrderId'],
                    receipt_id=display['receiptId'], source_operation_id=display['id'], workshop_id=display['workshopId'],
                    work_center_id=display['workCenterId'], execution_mode=display['executionMode'],
                    workload_quantity=display['workloadQuantity'], workload_uom_id=display['workloadUomId'],
                    work_order_version=display['workOrderVersion'], source_snapshot=source, source_snapshot_hash=_hash(source),
                    execution_position_id=payload['positionId'], execution_employee_id=payload['employeeId'],
                    assignment_snapshot=assignment, assignment_hash=_hash(assignment), created_by=actor)
                audit = _audit(actor, task, SAVE_ACTION, {'status': ''}, qualification, payload['reason'], 'draft', 0)
                record_projected_business_transition(object_type=OBJECT, object_id=task.pk, source_state='', target_state='draft',
                    action_code=SAVE_ACTION, operator=actor, reason=payload['reason'], audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
                    allowed_transitions={('', 'draft')})
            _ledger(actor, SAVE_ACTION, payload, request_hash, task)
            _verify_history(task)
            return read_workshop_tasks(user=actor, operation_id=task.source_operation_id), _writes()
    except IntegrityError:
        _fail('WORKSHOP_TASK_CONCURRENT_CONFLICT', '该工序任务或防重复标识已被其他操作保存，请只读刷新。')
    except DatabaseError:
        _fail('WORKSHOP_TASK_TRANSACTION_FAILED', '任务保存事务未完成并已回滚，请先只读刷新。', 503)

def dispatch_task(*, user, task_id, payload):
    _payload(payload, True)
    _positive(task_id, '任务')
    actor, _ = receipt_service._actor(user)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            task = Task.objects.select_for_update().filter(pk=task_id, company_id=actor.company_id).first()
            if task is None:
                _fail('WORKSHOP_TASK_NOT_VISIBLE', '未找到本公司任务。', 403)
            facts = read_workshop_tasks(user=actor, operation_id=task.source_operation_id)
            request_hash, replay = _intent(actor, DISPATCH_ACTION, payload, task_id)
            # A repeat request still needs the current same-workshop dispatcher chain.
            q = _dispatcher(actor, task.work_order, task.workshop, DISPATCH_ACTION, task.pk, 'draft')
            if not q['ready']:
                _fail('WORKSHOP_TASK_DISPATCHER_UNQUALIFIED', '；'.join(q['missingItems']), 403)
            if replay:
                if int(replay.target_entity_id) != task_id:
                    _fail('WORKSHOP_TASK_IDEMPOTENCY_CONFLICT', '防重复标识引用其他任务。')
                _verify_history(task)
                return facts, _writes(True)
            if not facts['availableActions']['dispatch']['enabled']:
                _fail('WORKSHOP_TASK_NOT_READY', facts['availableActions']['dispatch']['disabledReason'], 403)
            if task.version != payload['expectedVersion'] or task.source_snapshot_hash != payload['expectedSourceSnapshotHash']:
                _fail('WORKSHOP_TASK_SOURCE_OR_VERSION_CHANGED', '任务版本或正式来源已变化，请重新读取。')
            before = _state(task)
            task.dispatched_by = actor
            task.dispatched_at = timezone.now()
            task.dispatch_qualification = facts['selectedTask']['dispatchQualification']
            task.save(update_fields=['dispatched_by', 'dispatched_at', 'dispatch_qualification', 'updated_at'])
            audit = _audit(actor, task, DISPATCH_ACTION, before, q, payload['reason'], 'dispatched', task.version + 1)
            transition_business_object(business_object=task, object_type=OBJECT, source_state='draft', target_state='dispatched',
                action_code=DISPATCH_ACTION, operator=actor, reason=payload['reason'], audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
                allowed_transitions={('draft', 'dispatched')})
            _ledger(actor, DISPATCH_ACTION, payload, request_hash, task)
            _verify_history(task)
            return read_workshop_tasks(user=actor, operation_id=task.source_operation_id), _writes(dispatched=True)
    except IntegrityError:
        _fail('WORKSHOP_TASK_CONCURRENT_CONFLICT', '任务或防重复标识已被其他操作保存，请只读刷新。')
    except DatabaseError:
        _fail('WORKSHOP_TASK_TRANSACTION_FAILED', '派工事务未完成并已回滚，请先只读刷新。', 503)

def _writes(replay=False, dispatched=False):
    return {'idempotent': replay, 'businessWriteCount': 0 if replay else 1, 'auditWriteCount': 0 if replay else 1,
        'workshopTaskCreatedOrUpdatedCount': 0 if replay else 1, 'actualDispatchCount': int(dispatched and not replay),
        'actualStartCount': 0, 'actualReportCount': 0, 'resourceOccupancyReleasedCount': 0,
        'workOrderUpdatedCount': 0, 'operationSourceUpdatedCount': 0}
