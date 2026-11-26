

# Native formal continuation: individually restored symbols; existing proofs preserved.
from pde.routing_read_context import routing_read_phase
from copy import deepcopy

from decimal import Decimal, InvalidOperation

import re

from django.db import DatabaseError, IntegrityError, transaction

from django.core.exceptions import ObjectDoesNotExist, ValidationError

from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, UnitOfMeasure

from pfm.models import Employee

from system.models import PositionResponsibility, PositionWorkflowResponsibility, OrganizationOperatingAuditRecord

from workflow_runtime.models import BusinessStateTransition, ProcessDefinition

from workflow_runtime.action_permissions import ActionPermissionValidator

from workflow_runtime.state_transitions import create_business_object_with_initial_state, record_projected_business_transition

from . import formal_scheduling_service as formal

from . import work_order_workshop_receipt_service as receipt_service

from . import workshop_task_service as task_service

from .workshop_task_models import ProductionWorkshopTask as Task

from .operation_start_models import ProductionOperationStart as Start

from .work_order_execution_service import _hash, _fail

from .work_order_release_admission_service import _effective

from .workshop_task_time import task_datetime_label

from .services import record_audit, PlanningBusinessError

from .operation_start_contract import (CONTRACT, MODULE, READ_PERMISSION, START_ACTION, PROCESS,
    WORKFLOW_NODE, RESPONSIBILITY, OBJECT, action_contract, register_action)

from .operation_execution_mode import (task_execution_mode, source_with_mode, mode_display,
    QUANTIFIED, NON_QUANTIFIED_REQUIRED)

STATUS = {'': '尚无开工记录', 'waiting': '待开工', 'started': '已开工'}

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

def _current_version_facts(task, actor):
    """Read the governed current step identity, without opening PDE maintenance.

    APS time-policy selection/read permissions belong to scheduling and are
    deliberately not reused as execution privileges. The published version
    resolver owns engineering identity and binding integrity.
    """
    from pde.plan_step_context_service import resolve_step_context, version_fact, _company
    from pde.operation_allocation_source_handoff_service import allocation_admission_context
    operation = task.source_operation
    keys = ('originalManufacturingOutputId', 'effectiveManufacturingOutputId',
        'originalRoutingVersionId', 'effectiveRoutingVersionId', 'rootRoutingStepId', 'effectiveRoutingStepId',
        'bindingId', 'sourceBaselineId', 'mainCalculationId', 'sourceSelection')
    try:
        with allocation_admission_context(user=actor,company_id=task.company_id) as proofs:
            context = resolve_step_context(task.work_order.production_plan, operation.root_step_id,
                user=actor,read_cache=proofs['cache'])
            current = version_fact(context)
        previous = task.source_snapshot['operation']['frozenStep']['engineeringVersion']
        step, root = context['step'], context['root_step']
        valid = bool(isinstance(previous, dict) and all(current.get(key) == previous.get(key) for key in keys)
            and context['plan'].pk == task.work_order.production_plan_id
            and _company(root) == _company(step) == task.company_id == actor.company_id
            and root.pk == operation.root_step_id and root.routing_version_id == operation.root_routing_version_id
            and step.pk == operation.effective_step_id and step.routing_version_id == operation.effective_routing_version_id
            and step.is_active and step.operation_id == operation.operation_id
            and step.work_center_id in (None, task.work_center_id) and step.workshop_id in (None, task.workshop_id))
        issues = [] if valid else [{'code': 'OPERATION_START_CURRENT_VERSION_CHANGED',
            'statusLabel': '当前正式步骤、工程版本或工作中心声明与已派工冻结来源不一致。'}]
        return {'ready': valid, 'statusLabel': '当前正式步骤及工程版本一致' if valid else '当前正式步骤或工程版本已变化',
            'issues': issues, 'stepId': operation.root_step_id, 'currentEngineeringVersion': current,
            'sourceAuthority': 'pde.plan_step_context_service.resolve_step_context/version_fact',
            'schedulingPolicyPermissionsRequired': False}
    except (ValidationError, ObjectDoesNotExist, KeyError, TypeError, AttributeError) as error:
        return {'ready': False, 'statusLabel': '当前正式步骤版本事实缺失或未通过核对',
            'issues': [{'code': str(getattr(error, 'code', None) or 'OPERATION_START_CURRENT_VERSION_UNPROVEN'),
                'statusLabel': '当前步骤版本不能由正式来源解析器证实。'}], 'stepId': operation.root_step_id,
            'currentEngineeringVersion': None,
            'sourceAuthority': 'pde.plan_step_context_service.resolve_step_context/version_fact',
            'schedulingPolicyPermissionsRequired': False}

def _source(task, actor):
    from .operation_resource_source import read_operation_resource
    task_service._verify_history(task)
    order, operation = task.work_order, task.source_operation
    context = read_operation_resource(operation, actor=actor)
    mode = task_execution_mode(task, actor=actor)
    source, resource, receipt = source_with_mode(context['source'], mode), context['facts'], context['receipt']
    today = _today()
    center = context.get('workCenter', operation.work_center)
    receipt_valid = bool((resource['originalReceiptProven'] or resource.get('preciseReceiptProven') is True)
        and receipt and receipt.status == 'received'
        and receipt.pk == task.receipt_id and receipt.snapshot_hash == task.source_snapshot.get('receiptSnapshotHash'))
    try:
        quantity_valid = Decimal(task.workload_quantity).is_finite() and Decimal(task.workload_quantity) > 0
    except (InvalidOperation, TypeError, ValueError):
        quantity_valid = False
    if task.execution_mode == NON_QUANTIFIED_REQUIRED:
        quantity_valid = ((task.workload_quantity is None and task.workload_uom_id is None)
            or quantity_valid and UnitOfMeasure.objects.filter(pk=task.workload_uom_id,
                company_id=task.company_id, is_active=True).exists())
    unit_valid = (task.execution_mode == NON_QUANTIFIED_REQUIRED and task.workload_quantity is None
        and task.workload_uom_id is None) or UnitOfMeasure.objects.filter(pk=task.workload_uom_id,
            company_id=task.company_id, is_active=True).exists()
    from .operation_continuation_service import is_receipt_mode
    if is_receipt_mode(mode):
        reference=mode['referenceWorkload']
        quantity_valid=bool(quantity_valid and Decimal(task.workload_quantity)==Decimal(reference['quantity'])
            and task.workload_uom_id==reference['uomId'])
    valid = bool(task.status == 'dispatched' and order.status == 'released' and task.work_order_version == order.version
        and resource['sourceReady'] and receipt_valid and _hash(source) == task.source_snapshot_hash
        and center and center.pk == task.work_center_id and center.company_id == task.company_id
        and center.workshop_id == task.workshop_id and _effective(center, today)
        and (task.execution_mode == NON_QUANTIFIED_REQUIRED or not operation.dependency_only
            or (mode.get('ready') and (mode.get('modeSourceProof') or {}).get('sourceAuthority')=='FORMAL_CONTINUATION_ACTUAL_RECEIPT_INPUT'))
        and mode['ready'] and quantity_valid and unit_valid)
    current = _current_version_facts(task, actor)
    valid = valid and current['ready']
    issues = list(resource['blockingReasons'])
    if not mode['ready']:
        issues.extend(mode['blockingReasons'])
    if _hash(source) != task.source_snapshot_hash:
        issues.append('已有任务仍冻结原来源或归属；本轮不自动迁移或重建任务。')
    if not current['ready']:
        issues.append('当前版本核对未通过：' + current['statusLabel'])
    result = {'ready': bool(valid), 'statusLabel': resource['statusLabel'] + '；正式派工及当前来源版本一致' if valid else
            '；'.join(issues) or '派工来源、接收、工作中心或当前版本未通过核对', 'missingItems': issues,
        'currentSourceChecks': current, 'snapshotHash': _hash(source), 'receiptValid': receipt_valid,
        'resourceSource': resource, 'originalReceiptWorkshop': resource['originalReceiptWorkshop'],
        'effectiveWorkshop': resource['effectiveWorkshop'], 'effectiveReceptionAuthority': resource['effectiveReceptionAuthority']}
    if task.execution_mode == NON_QUANTIFIED_REQUIRED:
        result.update(**mode_display(mode), executionModeFacts=mode)
    return result

def _predecessors(task):
    from .operation_predecessor_authority import predecessor_facts
    return predecessor_facts(task)

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
    node = process.nodes.filter(node_code=WORKFLOW_NODE, business_action_code=START_ACTION, active=True).first() if process else None
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
    events = list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=record.pk).order_by('version', 'pk'))
    event = events[0] if len(events) == 1 else None
    match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', event.audit_reference or '') if event else None
    audit = OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
    process = ProcessDefinition.objects.filter(definition_code=PROCESS).first()
    node = process.nodes.filter(node_code=WORKFLOW_NODE).first() if process else None
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
    zone = task.work_order.source_snapshot['sourceSchedule']['timezone']
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

from .operation_resource_read_scope import scoped_execution_read

@scoped_execution_read
def read_operation_starts(*, user, task_id=None):
    actor, runtime_scope = receipt_service._actor(user)
    if task_id is not None and (type(task_id) is not int or task_id <= 0):
        _fail('OPERATION_START_QUERY_INVALID', '任务身份须为正式正整数。', 400)
    employee, _, _, workshop, evidence, _ = _identity(actor)
    authorized = receipt_service._authority(actor, READ_PERMISSION, workshop.department_id if workshop else None, actor.pk)[0]
    if not authorized:
        _fail('OPERATION_START_READ_DENIED', '当前账号没有执行查看权限及有效本公司范围。', 403)
    visible_orders = receipt_service._rows(actor, runtime_scope).values_list('pk', flat=True)
    records = Task.objects.filter(company_id=actor.company_id, status='dispatched', work_order_id__in=visible_orders,
        execution_employee_id=employee.pk if employee else None).select_related('work_order__production_plan', 'source_operation__effective_step',
            'source_operation__work_center__workshop', 'workshop', 'work_center').order_by('pk')
    if task_id is not None:records=records.filter(pk=task_id)
    tasks = []
    for task in records:
        if not _owned(actor, task, employee):
            continue
        source = _source(task, actor)
        predecessors = _predecessors(task)
        record = Start.objects.filter(task_id=task.pk).first()
        execution = _verify_record(record, task) if record else None
        state = 'started' if record else 'waiting'
        qualification = _qualification(actor, task, source, predecessors, state=state)
        action = {**action_contract(task.pk), 'enabled': qualification['ready'],
            'disabledReason': '' if qualification['ready'] else '；'.join(qualification['missingItems'])}
        operation = task.source_snapshot['operation']
        history = execution['statusTransitionHistory'] if execution else []
        tasks.append({'id': task.pk, 'taskId': task.pk, 'no': task.no, 'taskNo': task.no,
            'workOrderId': task.work_order_id, 'workOrderNo': task.work_order.no,
            'workOrderVersion': task.work_order_version,
            'operationId': task.source_operation_id, 'operationName': operation['operationName'], 'sequence': operation['sequence'],
            'rootRoutingVersionId': operation['rootRoutingVersionId'], 'routeVersionId': operation['effectiveRoutingVersionId'],
            'rootStepId': operation['rootStepId'], 'stepId': operation['effectiveStepId'],
            'workshopId': task.workshop_id, 'workshopName': task.workshop.name,
            'receiptId': task.receipt_id, 'receiptValid': source['receiptValid'],
            'receiptStatusLabel': source['resourceSource']['statusLabel'] if source['receiptValid'] else '接收事实未通过本次开工核对',
            'resourceSource': source['resourceSource'], 'originalReceiptWorkshop': source['originalReceiptWorkshop'],
            'effectiveWorkshop': source['effectiveWorkshop'], 'effectiveReceptionAuthority': source['effectiveReceptionAuthority'],
            'workCenterId': task.work_center_id, 'workCenterCode': task.work_center.code,
            'workCenterName': task.work_center.name if task.source_snapshot.get('executionResourceSelectionRef') else operation['workCenterName'], 'workloadQuantity': task.workload_quantity,
            'workloadUomId': task.workload_uom_id,
            'workloadLabel': ('不统计实际完成数量；正式参考：' + operation['workloadLabel']
                if task.workload_quantity is not None else '不单独计量，保留正式空数量／单位')
                if task.execution_mode == NON_QUANTIFIED_REQUIRED else (str(task.workload_quantity)+' '+task.workload_uom.name
                    if task.source_snapshot.get('modeSourceProof',{}).get('continuationInputPlan') else operation['workloadLabel']),
            'positionId': task.execution_position_id, 'positionName': task.assignment_snapshot.get('positionName'),
            'employeeId': task.execution_employee_id, 'employeeName': task.assignment_snapshot.get('employeeName'),
            'employeeUsername': task.assignment_snapshot.get('username'), 'dispatchStatusLabel': '已派工', 'dispatchLabel': '已派工',
            'statusCode': state, 'statusLabel': STATUS[state], 'executionStatusCode': state, 'executionStatusLabel': STATUS[state],
            'executionStatusSource': 'planning.ProductionOperationStart' if record else 'DISPATCHED_TASK_WITHOUT_START_RECORD',
            'executionRecordPresent': record is not None,
            'version': task.version, 'sourceSnapshotHash': task.source_snapshot_hash, 'assignmentHash': task.assignment_hash,
            'assignmentSnapshotHash': task.assignment_hash, 'sourceConsistent': source['ready'],
            'executionRecord': execution, 'startedAtLabel': execution['startedAtLabel'] if execution else '尚未开工',
            'startedByLabel': execution['startedByLabel'] if execution else '尚未开工',
            'statusTransitionHistory': history, 'statusTransitionCount': len(history), 'stateMachineConsistent': True,
            'predecessorFacts': predecessors, 'qualification': qualification, 'availableActions': {'start': action},
            **mode_display(task_execution_mode(task, verify_current=False))})
    selected = next((row for row in tasks if row['id'] == task_id), None) if task_id else None
    if task_id and selected is None:
        _fail('OPERATION_START_TASK_NOT_VISIBLE', '所选任务不属于当前账号的本公司本人正式获派范围。', 403)
    empty = {'ready': False, 'statusLabel': '请选择本人已派工任务', 'missingItems': ['请选择本人已派工任务。']}
    return {'contractVersion': CONTRACT, 'moduleCode': MODULE, 'factSource': 'server', 'currentStateSource': 'server',
        'companyId': actor.company_id, 'currentActorEvidence': evidence, 'tasks': tasks, 'selectedTask': selected,
        'qualification': selected['qualification'] if selected else empty,
        'availableActions': selected['availableActions'] if selected else {'start': {**action_contract(),
            'enabled': False, 'disabledReason': '请选择本人已派工任务。'}},
        'statusLabel': '本人任务及工序开工事实已读取', 'businessWriteCount': 0, 'auditWriteCount': 0,
        'actualStartCount': 0, 'actualReportCount': 0, 'operationStartRecordCount': sum(row['executionRecord'] is not None for row in tasks),
        'actualStartSupported': True, 'reportOrCompletionSupported': False, 'selfTaskOnly': True,
        'predecessorCompletionAuthorityAvailable': True}

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

def start_operation(*, user, task_id, payload):
    _payload(payload)
    if type(task_id) is not int or task_id <= 0:
        _fail('OPERATION_START_QUERY_INVALID', '任务身份须为正式正整数。', 400)
    actor, _ = receipt_service._actor(user)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            task = Task.objects.select_for_update().filter(pk=task_id, company_id=actor.company_id).first()
            if task is None:
                _fail('OPERATION_START_TASK_NOT_VISIBLE', '未找到本公司本人获派任务。', 403)
            facts = read_operation_starts(user=actor, task_id=task_id)
            selected = facts['selectedTask']
            request_hash, replay = _intent(actor, task_id, payload)
            if (task.version != payload['expectedVersion'] or task.source_snapshot_hash != payload['expectedSourceSnapshotHash']
                    or task.assignment_hash != payload['expectedAssignmentHash']):
                _fail('OPERATION_START_SOURCE_OR_VERSION_CHANGED', '任务版本、来源或冻结执行人员已变化，请只读重新核对。')
            if replay:
                record = Start.objects.filter(pk=int(replay.target_entity_id), task_id=task_id).first()
                if record is None:
                    _fail('OPERATION_START_IDEMPOTENCY_CONFLICT', '防重复账本未指向该任务正式开工记录。')
                _verify_record(record, task)
                q = _qualification(actor, task, selected['qualification']['sourceFacts'], selected['predecessorFacts'], state='waiting')
                if not q['ready']:
                    _fail('OPERATION_START_NOT_READY', '；'.join(q['missingItems']), 403)
                return facts, _writes(True)
            if not selected['availableActions']['start']['enabled']:
                _fail('OPERATION_START_NOT_READY', selected['availableActions']['start']['disabledReason'], 403)
            if Start.objects.select_for_update().filter(task=task).exists():
                _fail('OPERATION_START_DUPLICATE', '任务已经开工，不可重复开工。')
            q = selected['qualification']
            record = create_business_object_with_initial_state(model=Start, initial_state='started',
                company_id=task.company_id, task=task, work_order_id=task.work_order_id, receipt_id=task.receipt_id,
                source_operation_id=task.source_operation_id, workshop_id=task.workshop_id, work_center_id=task.work_center_id,
                execution_mode=task.execution_mode, workload_quantity=task.workload_quantity,
                workload_uom_id=task.workload_uom_id, task_version=task.version,
                source_snapshot=deepcopy(task.source_snapshot), source_snapshot_hash=task.source_snapshot_hash,
                assignment_snapshot=deepcopy(task.assignment_snapshot), assignment_hash=task.assignment_hash,
                execution_position_id=task.execution_position_id, execution_employee_id=task.execution_employee_id,
                started_by=actor, started_at=timezone.now(), start_qualification=deepcopy(q), reason=payload['reason'].strip())
            audit = record_audit(user=actor, action_code=START_ACTION, target=record, target_type=OBJECT,
                target_no=task.no, before={'status': ''}, after=_state(record), authorization=q['authorization'], reason=record.reason)
            node = {'processCode': PROCESS, 'nodeCode': WORKFLOW_NODE, 'processId': q['definitionId'], 'nodeId': q['nodeId']}
            audit.before_snapshot['workflowNode'] = node; audit.after_snapshot['workflowNode'] = node
            audit.save(update_fields=['before_snapshot', 'after_snapshot'])
            record_projected_business_transition(object_type=OBJECT, object_id=record.pk, source_state='', target_state='started',
                action_code=START_ACTION, operator=actor, reason=record.reason,
                audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions={('', 'started')})
            identity, _ = ExternalIdentity.objects.get_or_create(organization_id=actor.company_id, source_system='MES_OPERATION_START',
                source_type='INTERNAL', source_object_type='ProductionWorkshopTask', external_id=str(task.pk), target_entity_type=OBJECT,
                defaults={'target_entity_id': str(record.pk), 'mapping_status': 'MATCH', 'source_fingerprint': task.source_snapshot_hash,
                    'audit_metadata': {'actualStartOnly': True}})
            if identity.target_entity_id != str(record.pk) or identity.source_fingerprint != task.source_snapshot_hash:
                _fail('OPERATION_START_LEDGER_SOURCE_CONFLICT', '开工来源账本身份冲突。')
            MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=START_ACTION,
                entity_type=OBJECT, idempotency_key=payload['idempotencyKey'], request_hash=request_hash, source_identity=identity,
                status='COMMITTED', target_entity_id=str(record.pk), result={'taskId': task.pk, 'operationStartId': record.pk},
                audit_metadata={'actorId': actor.pk, 'actualStartOnly': True})
            _verify_record(record, task)
            return read_operation_starts(user=actor, task_id=task_id), _writes()
    except IntegrityError:
        _fail('OPERATION_START_CONCURRENT_CONFLICT', '任务开工或防重复标识已被其他操作保存，请只读刷新。')
    except DatabaseError:
        _fail('OPERATION_START_TRANSACTION_FAILED', '开工事务结果尚未核实，请先只读刷新，不会自动重放。', 503)

def _writes(replay=False):
    return {'idempotent': replay, 'businessWriteCount': 0 if replay else 1, 'auditWriteCount': 0 if replay else 1,
        'operationStartCreatedCount': 0 if replay else 1, 'stateTransitionWriteCount': 0 if replay else 1,
        'actualStartCount': 0 if replay else 1, 'actualReportCount': 0, 'actualDispatchCount': 0,
        'workOrderUpdatedCount': 0, 'operationSourceUpdatedCount': 0, 'taskUpdatedCount': 0,
        'resourceOccupancyReleasedCount': 0, 'scheduleUpdatedCount': 0, 'inventoryUpdatedCount': 0}
