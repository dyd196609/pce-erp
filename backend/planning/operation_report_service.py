"""Actual executor's append-only partial reporting, with exact decimal totals.

Reports are quantity facts, never completion facts. No Task, Start, source,
inventory, schedule or occupancy row is projected by this service.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import re
from types import SimpleNamespace

from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from masterdata.models import ExternalIdentity, MasterDataWriteRequest, UnitOfMeasure
from system.models import PositionResponsibility, PositionWorkflowResponsibility, OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition, ProcessDefinition
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.state_transitions import create_business_object_with_initial_state, record_projected_business_transition
from . import mes_test_source_bridge as formal
from . import mes_test_source_bridge as receipt_service
from . import mes_test_source_bridge as start_service
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_start_models import ProductionOperationStart as Start
from .operation_report_models import ProductionOperationReport as Report
from .mes_test_source_bridge import _hash, _fail
from .mes_test_source_bridge import _effective
from .workshop_task_time import task_datetime_label
from .mes_task_date_facts import task_date_facts
from .mes_test_source_bridge import record_audit
from .operation_report_contract import (CONTRACT, MODULE, READ_PERMISSION, REPORT_ACTION, PROCESS,
    WORKFLOW_NODE, RESPONSIBILITY, OBJECT, action_contract, register_action)

STATUS = {'': '尚无本次报工记录', 'reported': '已报工', 'open': '可分次报工',
    'quantity_reached': '报工量已达任务量', 'precision_residual': '剩余量低于正式单位最小报工量'}
_DECIMAL = re.compile(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z')


def _add(a, b):
    # Decimal's ambient context must not round a long formal quantity. Each
    # operand is a bounded persisted decimal string; no SQL SUM or float is used.
    with localcontext() as context:
        context.prec = max(28, len(a.as_tuple().digits) + len(b.as_tuple().digits)
            + abs(a.as_tuple().exponent) + abs(b.as_tuple().exponent) + 4)
        return a + b


def _text(number):
    value = format(number, 'f')
    return (value.rstrip('0').rstrip('.') if '.' in value else value) or '0'


def _decimal(value, *, positive=False, precision=None, code='OPERATION_REPORT_QUANTITY_INVALID'):
    if not isinstance(value, str) or not 1 <= len(value) <= 100 or not _DECIMAL.fullmatch(value):
        _fail(code, '本次实际完成量须为明确填写的十进制数字文本，不接受科学计数、符号或空白。', 400)
    places = len(value.partition('.')[2])
    if precision is not None and places > precision:
        _fail('OPERATION_REPORT_UNIT_PRECISION_EXCEEDED', f'本次实际完成量最多允许{precision}位小数；未修改或截断输入。', 400)
    try:
        quantity = Decimal(value)
    except InvalidOperation:
        _fail(code, '实际完成量不是有效十进制数量。', 400)
    if not quantity.is_finite() or quantity < 0 or (positive and quantity == 0):
        _fail(code, '本次实际完成量必须大于零。', 400)
    return quantity


def _unit(task):
    unit = UnitOfMeasure.objects.filter(pk=task.workload_uom_id, company_id=task.company_id, is_active=True).first()
    if unit is None or type(unit.decimal_places) is not int or not 0 <= unit.decimal_places <= 6:
        _fail('OPERATION_REPORT_UNIT_UNPROVEN', '正式作业单位或其小数精度尚未核实，禁止报工。')
    return unit, {'id': unit.pk, 'companyId': unit.company_id, 'code': unit.code, 'name': unit.name,
        'symbol': unit.symbol, 'dimension': unit.dimension, 'decimalPlaces': unit.decimal_places,
        'precisionAuthority': 'masterdata.UnitOfMeasure.decimal_places'}


def _quantity_facts(task, unit, total):
    ceiling = _decimal(task.workload_quantity, positive=True, code='OPERATION_REPORT_TASK_QUANTITY_INVALID')
    remaining = _add(ceiling, total.copy_negate())
    if remaining < 0:
        _fail('OPERATION_REPORT_HISTORY_INCONSISTENT', '已审计累计报工量超过正式任务作业量。')
    minimum = Decimal(1).scaleb(-unit.decimal_places)
    residual = 0 < remaining < minimum
    state = 'quantity_reached' if remaining == 0 else 'precision_residual' if residual else 'open'
    unit_label = unit.name or unit.symbol or unit.code
    task_precision = len(task.workload_quantity.partition('.')[2])
    return {'workloadQuantity': task.workload_quantity, 'reportedQuantity': _text(total),
        'remainingQuantity': _text(remaining), 'quantityPrecision': unit.decimal_places,
        'minimumReportQuantity': _text(minimum), 'remainingBelowUnitPrecision': residual,
        'quantityStatusCode': state, 'quantityStatusLabel': STATUS[state],
        'reportedQuantityLabel': f'{_text(total)} {unit_label}', 'remainingQuantityLabel': f'{_text(remaining)} {unit_label}',
        'quantityPrecisionAuthority': 'masterdata.UnitOfMeasure.decimal_places',
        'taskQuantityExceedsUnitPrecision': task_precision > unit.decimal_places,
        'precisionNotice': '任务原量保留全部精度；本次输入遵循正式单位精度。若留下小于最小报工量的余量，系统不会补齐、归零或认定完工。'
            if task_precision > unit.decimal_places else '',
        'completionProven': False, 'predecessorCompletionFact': None, 'downstreamReleased': False}


def _start_snapshot(start):
    return {'id': start.pk, **start_service._state(start)}


class _Facts:
    def __init__(self, actor, task, state):
        self.actor, self.task, self.state = actor, task, state

    def read(self, module_code, object_ids):
        valid = module_code == MODULE and object_ids == [str(self.task.pk)] and self.task.company_id == self.actor.company_id
        return {'found': valid, 'objectIds': object_ids if valid else [], 'statuses': [self.state] if valid else [],
            'legalEntityIds': [str(self.task.company_id)] if valid else [], 'currentStateSource': 'server',
            'reason': '' if valid else 'object_scope_mismatch'}


def _qualification(actor, task, start, source, quantity):
    from .operation_executor_scope import executor_scope
    register_action()
    employee, position, _, workshop, evidence, employment_valid = start_service._identity(actor)
    scope = executor_scope(position, company_id=task.company_id, workshop_id=task.workshop_id,
        operation_id=task.source_operation.operation_id, work_center_id=task.work_center_id)
    identity_valid = bool(employment_valid and scope['ready'] and start_service._owned(actor, task, employee)
        and task.execution_position_id == position.pk and task.assignment_snapshot.get('positionId') == position.pk
        and task.workshop_id == workshop.pk and position.process_id in (None, task.source_operation.operation_id)
        and start and start.started_by_id == actor.pk and start.execution_employee_id == employee.pk
        and start.execution_position_id == position.pk)
    issues = []
    if not scope['ready']:
        issues.append(scope['statusLabel'])
    if not employment_valid:
        issues.append('当前账号缺少唯一有效的同公司本人任职、岗位及车间关系。')
    if not identity_valid:
        issues.append('必须由任务冻结指定执行人及实际开工人本人，以当前有效执行岗位报工。')
    process = ProcessDefinition.objects.filter(definition_code=PROCESS, active=True, business_domain='MES').first()
    node = process.nodes.filter(node_code=WORKFLOW_NODE, business_action_code=REPORT_ACTION, active=True).first() if process else None
    duties = list(PositionResponsibility.objects.filter(position=position, active=True,
        responsibility__code=RESPONSIBILITY, responsibility__status='ACTIVE', responsibility__is_active=True)
        .select_related('responsibility')) if identity_valid else []
    duty = duties[0] if len(duties) == 1 and _effective(duties[0].responsibility, start_service._today()) else None
    mappings = list(PositionWorkflowResponsibility.objects.filter(position=position, responsibility=duty.responsibility,
        workflow_node=node, workflow_code=PROCESS, node_code=WORKFLOW_NODE, ownership_type='EXECUTOR', active=True)) if duty and node else []
    mapping = mappings[0] if len(mappings) == 1 and _effective(mappings[0], start_service._today()) else None
    if not process or not node:
        issues.append('正式工序报工节点尚未生效。')
    if not duty or not mapping:
        issues.append('执行岗位缺少有效工序报工职责及精确节点执行关系。')
    authorized, matched, native = receipt_service._authority(actor, REPORT_ACTION, task.workshop.department_id, actor.pk)
    decision = ActionPermissionValidator(fact_provider=_Facts(actor, task, quantity['quantityStatusCode'])).evaluate(user=actor,
        module_code=MODULE, action_code=REPORT_ACTION, object_ids=[task.pk], selection_count=1,
        requested_legal_entity_id=str(actor.company_id))
    if not authorized:
        issues.append('当前账号缺少同一角色的明确报工权限及本公司数据范围。')
    elif not decision['granted'] and quantity['quantityStatusCode'] == 'open':
        issues.append(decision['reason'] or '正式报工动作服务端校验未通过。')
    if not source['ready']:
        issues.append(source['statusLabel'])
    if not start:
        issues.append('任务尚未正式开工，不能报工。')
    if quantity['quantityStatusCode'] == 'quantity_reached':
        issues.append('报工量已达任务量，不能继续报量；此状态不表示工序完工。')
    elif quantity['remainingBelowUnitPrecision']:
        issues.append('剩余未报量小于正式单位最小报工量，禁止补齐或超量；需由用户维护正式数量与单位口径。')
    evidence.update(positionResponsibilityId=duty.pk if duty else None,
        workflowResponsibilityId=mapping.pk if mapping else None, matchedAuthorityEvidence=matched)
    return {'ready': not issues, 'statusLabel': '本人已开工任务满足本次报工准入' if not issues else '报工条件未通过',
        'missingItems': issues, 'currentActorEvidence': evidence, 'authorization': native,
        'definitionId': process.pk if process else None, 'nodeId': node.pk if node else None,
        'sourceFacts': source, 'quantityFacts': deepcopy(quantity), 'selfTaskOnly': True,
        'actualStarterSelfOnly': True, 'startRecordId': start.pk if start else None,
        'startSnapshotHash': _hash(_start_snapshot(start)) if start else None}


def _state(record):
    return {'status': record.status, 'version': record.version, 'taskId': record.task_id, 'startRecordId': record.start_id,
        'taskVersion': record.task_version, 'sourceSnapshotHash': record.source_snapshot_hash,
        'assignmentHash': record.assignment_hash, 'startSnapshotHash': record.start_snapshot_hash,
        'quantity': record.quantity, 'reportedBefore': record.reported_before, 'reportedAfter': record.reported_after,
        'quantityPrecision': record.quantity_precision, 'unitSnapshot': record.unit_snapshot,
        'reportedById': record.reported_by_id, 'reportedAt': record.reported_at.isoformat(), 'reason': record.reason,
        'requestKeyHash': record.request_key_hash, 'requestHash': record.request_hash,
        'reportQualification': record.report_qualification}


def _request_payload(record, ledger):
    return {'expectedVersion': record.task_version, 'expectedSourceSnapshotHash': record.source_snapshot_hash,
        'expectedAssignmentHash': record.assignment_hash, 'expectedStartId': record.start_id,
        'expectedStartSnapshotHash': record.start_snapshot_hash, 'quantity': record.quantity,
        'reason': record.reason, 'idempotencyKey': ledger.idempotency_key}


def _request_hash(actor_id, task_id, payload):
    return _hash({'actorId': actor_id, 'action': REPORT_ACTION, 'taskId': task_id,
        'payload': {**payload, 'reason': payload['reason'].strip()}})


def _verify_record(record, task, start, before_total):
    # Formal legacy completion snapshots freeze the original Chinese labels in
    # their report set. Keep that canonical formatter; TEST retains its ISO labels.
    from .workshop_task_time import task_datetime_label
    if task.work_order.usage_purpose == 'PRODUCTION_USE':
        from .mes_formal_source_admission import formal_datetime_label as task_datetime_label
    from .mes_evidence_graph import history, audit as raw_audit,definition_rows,_raw
    events=history(OBJECT,record.pk,task.company_id)
    if events is NotImplemented:events=list(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=record.pk).order_by('version','pk'))
    event = events[0] if len(events) == 1 else None
    match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', event.audit_reference or '') if event else None
    audit=raw_audit(int(match[1]),task.company_id) if match else None
    if audit is NotImplemented:audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first()
    definitions=definition_rows(task.company_id,PROCESS) if _raw(task.company_id) is not None else None
    process=(definitions[0] if definitions else None) if definitions is not None else ProcessDefinition.objects.filter(definition_code=PROCESS).first()
    node=(next((n for n in process._mes_raw_nodes if n.node_code==WORKFLOW_NODE),None) if definitions is not None else process.nodes.filter(node_code=WORKFLOW_NODE).first()) if process else None
    expected_node = {'processCode': PROCESS, 'nodeCode': WORKFLOW_NODE,
        'processId': process.pk if process else None, 'nodeId': node.pk if node else None}
    from .mes_evidence_graph import report_ledgers
    ledgers=report_ledgers(task,record,REPORT_ACTION)
    if ledgers is NotImplemented:ledgers=list(MasterDataWriteRequest.objects.filter(organization_id=task.company_id,
        action_code=REPORT_ACTION,entity_type=OBJECT,target_entity_id=str(record.pk)).select_related('source_identity'))
    ledger = ledgers[0] if len(ledgers) == 1 else None
    before, after = (audit.before_snapshot, audit.after_snapshot) if audit else ({}, {})
    q, unit = record.report_qualification, record.unit_snapshot
    if not isinstance(q, dict) or any(not isinstance(q.get(k), dict) for k in ('currentActorEvidence', 'sourceFacts', 'quantityFacts', 'authorization')):
        _fail('OPERATION_REPORT_HISTORY_INCONSISTENT', '正式报工冻结资格结构不完整。')
    if not isinstance(unit, dict) or type(record.quantity_precision) is not int or not 0 <= record.quantity_precision <= 6:
        _fail('OPERATION_REPORT_HISTORY_INCONSISTENT', '正式报工单位及精度快照不完整。')
    if not isinstance(q['sourceFacts'].get('currentSourceChecks'), dict):
        _fail('OPERATION_REPORT_HISTORY_INCONSISTENT', '正式报工来源资格结构不完整。')
    if (not isinstance(q['authorization'].get('permissionCodes'), list)
            or (ledger is not None and not isinstance(ledger.audit_metadata, dict))
            or (audit is not None and (not isinstance(before, dict) or not isinstance(after, dict)
                or not isinstance(after.get('authorization'), dict)
                or not isinstance(after['authorization'].get('permissionCodes'), list)))):
        _fail('OPERATION_REPORT_HISTORY_INCONSISTENT', '正式报工授权、审计或防重复账本结构不完整。')
    quantity = _decimal(record.quantity, positive=True, precision=record.quantity_precision, code='OPERATION_REPORT_HISTORY_INCONSISTENT')
    after_total = _add(before_total, quantity)
    actor, source, qty = q['currentActorEvidence'], q['sourceFacts'], q['quantityFacts']
    frozen_valid = bool(q.get('ready') is True and q.get('selfTaskOnly') is True and q.get('actualStarterSelfOnly') is True
        and actor.get('userId') == record.reported_by_id and actor.get('employeeId') == record.execution_employee_id
        and actor.get('positionId') == record.execution_position_id and actor.get('companyId') == record.company_id
        and actor.get('workshopId') == record.workshop_id and actor.get('uniqueEmployeeAccountLink') is True
        and actor.get('currentEmploymentValid') is True and process and node
        and q.get('definitionId') == process.pk and q.get('nodeId') == node.pk
        and q.get('startRecordId') == start.pk and q.get('startSnapshotHash') == record.start_snapshot_hash
        and q['authorization'].get('allowed') is True and REPORT_ACTION in q['authorization'].get('permissionCodes', [])
        and source.get('ready') is True and source.get('snapshotHash') == record.source_snapshot_hash
        and source.get('receiptValid') is True and source.get('currentSourceChecks', {}).get('ready') is True
        and qty == _quantity_facts(task, SimpleNamespace(decimal_places=record.quantity_precision,
            name=unit.get('name'), symbol=unit.get('symbol'), code=unit.get('code')), before_total)
        and qty.get('quantityStatusCode') == 'open'
        and qty.get('completionProven') is False and qty.get('predecessorCompletionFact') is None)
    identity = ledger.source_identity if ledger else None
    valid = bool(record.status == 'reported' and record.version == 0 and record.task_id == task.pk and record.start_id == start.pk
        and record.company_id == task.company_id and record.task_version == task.version
        and record.work_order_id == task.work_order_id and record.receipt_id == task.receipt_id
        and record.source_operation_id == task.source_operation_id and record.workshop_id == task.workshop_id
        and record.work_center_id == task.work_center_id and record.workload_quantity == task.workload_quantity
        and record.workload_uom_id == task.workload_uom_id and unit.get('id') == task.workload_uom_id
        and unit.get('companyId') == task.company_id and unit.get('decimalPlaces') == record.quantity_precision
        and unit.get('precisionAuthority') == 'masterdata.UnitOfMeasure.decimal_places'
        and record.source_snapshot == task.source_snapshot and _hash(record.source_snapshot) == record.source_snapshot_hash == task.source_snapshot_hash
        and record.assignment_snapshot == task.assignment_snapshot and _hash(record.assignment_snapshot) == record.assignment_hash == task.assignment_hash
        and record.start_snapshot == _start_snapshot(start) and _hash(record.start_snapshot) == record.start_snapshot_hash
        and record.execution_position_id == task.execution_position_id and record.execution_employee_id == task.execution_employee_id
        and record.reported_by_id == start.started_by_id == task.assignment_snapshot.get('userId')
        and record.reason.strip() == record.reason and 2 <= len(record.reason) <= 300
        and record.reported_before == _text(before_total) and record.reported_after == _text(after_total)
        and after_total <= _decimal(task.workload_quantity, positive=True) and frozen_valid
        and ledger and ledger.status == 'COMMITTED' and ledger.request_hash == record.request_hash
        and sha256(ledger.idempotency_key.encode('utf-8')).hexdigest() == record.request_key_hash
        and _request_hash(record.reported_by_id, task.pk, _request_payload(record, ledger)) == record.request_hash
        and ledger.result == {'taskId': task.pk, 'operationStartId': start.pk, 'operationReportId': record.pk}
        and ledger.audit_metadata.get('actorId') == record.reported_by_id
        and identity and identity.organization_id == task.company_id and identity.source_system == 'MES_OPERATION_REPORT'
        and identity.source_object_type == 'ProductionOperationReportRequest' and identity.external_id == record.request_key_hash
        and identity.target_entity_type == OBJECT and identity.target_entity_id == str(record.pk)
        and identity.source_fingerprint == record.request_hash and identity.source_type == 'INTERNAL'
        and identity.mapping_status == 'MATCH'
        and event and event.version == 1 and event.source_state == '' and event.target_state == 'reported'
        and event.action_code == REPORT_ACTION and event.operator_id == record.reported_by_id and event.reason == record.reason
        and audit and audit.actor_id == record.reported_by_id and audit.organization_id == task.company_id
        and audit.target_type == OBJECT and audit.target_id == record.pk and audit.action_code == REPORT_ACTION
        and audit.reason == record.reason and isinstance(before, dict) and isinstance(after, dict)
        and before.get('state') == {'status': ''} and after.get('state') == _state(record)
        and after.get('authorization', {}).get('allowed') is True
        and REPORT_ACTION in after.get('authorization', {}).get('permissionCodes', [])
        and process and node and before.get('workflowNode') == after.get('workflowNode') == expected_node)
    if not valid:
        _fail('OPERATION_REPORT_HISTORY_INCONSISTENT', '正式报工、累计数量、来源、资格、防重复账本或审计不一致。')
    from .mes_test_source_bridge import execution_timezone
    zone = execution_timezone(task)
    history = [{'id': event.pk, 'sourceState': '', 'targetState': 'reported', 'sourceStateLabel': STATUS[''],
        'targetStateLabel': STATUS['reported'], 'actionCode': REPORT_ACTION, 'actionLabel': '报工',
        'operatorId': event.operator_id, 'reason': event.reason, 'auditReference': event.audit_reference,
        'version': event.version, 'timestamp': event.timestamp.isoformat(), 'timestampLabel': task_datetime_label(event.timestamp, zone)}]
    return {'id': record.pk, 'statusCode': record.status, 'statusLabel': STATUS[record.status],
        'taskId': task.pk, 'taskVersion': record.task_version, 'startRecordId': start.pk,
        'sourceSnapshotHash': record.source_snapshot_hash, 'assignmentHash': record.assignment_hash,
        'startSnapshotHash': record.start_snapshot_hash, 'quantity': record.quantity,
        'quantityLabel': f'{record.quantity} {unit["name"]}', 'quantityPrecision': record.quantity_precision,
        'uomId': record.workload_uom_id, 'uomLabel': unit['name'],
        'reportedBefore': record.reported_before, 'reportedAfter': record.reported_after,
        'reportedById': record.reported_by_id, 'reportedByLabel': record.assignment_snapshot.get('employeeName'),
        'reportedAt': record.reported_at.isoformat(), 'reportedAtLabel': task_datetime_label(record.reported_at, zone),
        'reason': record.reason, 'auditReference': event.audit_reference, 'requestKeyHash': record.request_key_hash,
        'version': record.version, 'statusTransitionHistory': history, 'statusTransitionCount': len(history),
        'stateMachineConsistent': True, 'completionProven': False}, after_total


def _reports(task, start, *, recorded_dates=None):
    rows, total = [], Decimal(0)
    from .mes_evidence_graph import report_rows
    for record in report_rows(task):
        row, total = _verify_record(record, task, start, total)
        rows.append(row)
        if recorded_dates is not None:
            # Separate projection: rows participate in frozen completion hashes.
            recorded_dates.append({'reportId': record.pk, 'reportedAt': record.reported_at,
                'recordedAt': record.created_at})
    return rows, total


from .operation_resource_read_scope import scoped_execution_read


@scoped_execution_read
def read_operation_reports(*, user, task_id=None,work_order_id=None):
    actor, runtime_scope = receipt_service._actor(user)
    if task_id is not None and (type(task_id) is not int or task_id <= 0):
        _fail('OPERATION_REPORT_QUERY_INVALID', '任务身份须为正式正整数。', 400)
    employee, _, _, workshop, evidence, _ = start_service._identity(actor)
    if not receipt_service._authority(actor, READ_PERMISSION, workshop.department_id if workshop else None, actor.pk)[0]:
        _fail('OPERATION_REPORT_READ_DENIED', '当前账号没有报工查看权限及有效本公司范围。', 403)
    visible_orders = receipt_service._rows(actor, runtime_scope).values_list('pk', flat=True)
    records = Task.objects.filter(company_id=actor.company_id, status='dispatched', work_order_id__in=visible_orders,
        execution_employee_id=employee.pk if employee else None, operation_start__isnull=False).select_related(
            'work_order__production_plan', 'source_operation__effective_step', 'source_operation__work_center__workshop',
            'workshop', 'work_center', 'operation_start').order_by('pk')
    if task_id is not None:
        records = records.filter(pk=task_id)
    if work_order_id is not None:records=records.filter(work_order_id=work_order_id)
    tasks = []
    for task in records:
        start = task.operation_start
        if not start_service._owned(actor, task, employee) or start.started_by_id != actor.pk:
            continue
        source = start_service._source(task, actor)
        execution = start_service._verify_record(start, task)
        if getattr(task, 'execution_mode', 'QUANTIFIED') != 'QUANTIFIED':
            from .operation_execution_mode import task_execution_mode
            from .operation_execution_confirmation_service import report_task_row
            tasks.append(report_task_row(task, start, actor, source, execution, task_execution_mode(task, actor=actor)))
            tasks[-1]['usagePurpose'] = task.work_order.usage_purpose
            tasks[-1]['dateFacts'] = task_date_facts(task, start)
            continue
        unit, _ = _unit(task)
        recorded_dates = []
        reports, total = _reports(task, start, recorded_dates=recorded_dates)
        quantity = _quantity_facts(task, unit, total)
        qualification = _qualification(actor, task, start, source, quantity)
        action = {**action_contract(task.pk), 'enabled': qualification['ready'],
            'disabledReason': '' if qualification['ready'] else '；'.join(qualification['missingItems'])}
        operation = task.source_snapshot['operation']
        tasks.append({'id': task.pk, 'taskId': task.pk, 'no': task.no, 'taskNo': task.no,'usagePurpose':task.work_order.usage_purpose,
            'workOrderId': task.work_order_id, 'workOrderNo': task.work_order.no, 'workOrderVersion': task.work_order_version,
            'operationId': task.source_operation_id, 'operationName': operation['operationName'], 'sequence': operation['sequence'],
            'rootRoutingVersionId': operation['rootRoutingVersionId'], 'routeVersionId': operation['effectiveRoutingVersionId'],
            'rootStepId': operation['rootStepId'], 'stepId': operation['effectiveStepId'],
            'workshopId': task.workshop_id, 'workshopName': task.workshop.name, 'receiptId': task.receipt_id,
            'receiptValid': source['receiptValid'],
            'receiptStatusLabel': source['resourceSource']['statusLabel'] if source['receiptValid'] else '接收事实未通过核对',
            'resourceSource': source['resourceSource'], 'originalReceiptWorkshop': source['originalReceiptWorkshop'],
            'effectiveWorkshop': source['effectiveWorkshop'], 'effectiveReceptionAuthority': source['effectiveReceptionAuthority'],
            'workCenterId': task.work_center_id, 'workCenterCode': task.work_center.code,
            'workCenterName': task.work_center.name if task.source_snapshot.get('executionResourceSelectionRef') else operation['workCenterName'],
            'workloadUomId': unit.pk, 'workloadUomCode': unit.code, 'workloadUomLabel': unit.name,
            'workloadLabel': operation['workloadLabel'], **quantity,
            'positionId': task.execution_position_id, 'positionName': task.assignment_snapshot.get('positionName'),
            'employeeId': task.execution_employee_id, 'employeeName': task.assignment_snapshot.get('employeeName'),
            'employeeUsername': task.assignment_snapshot.get('username'), 'dispatchStatusLabel': '已派工',
            'statusCode': quantity['quantityStatusCode'], 'statusLabel': quantity['quantityStatusLabel'],
            'executionStatusLabel': '已开工', 'executionRecord': execution, 'startRecordId': start.pk,
            'startSnapshotHash': _hash(_start_snapshot(start)), 'startAuditReference': execution['auditReference'],
            'startedAtLabel': execution['startedAtLabel'], 'startedByLabel': execution['startedByLabel'],
            'version': task.version, 'sourceSnapshotHash': task.source_snapshot_hash, 'assignmentHash': task.assignment_hash,
            'sourceConsistent': source['ready'], 'reports': reports, 'operationReportRecordCount': len(reports), 'reportRecordCount': len(reports),
            'qualification': qualification, 'availableActions': {'report': action}, 'stateMachineConsistent': True})
        # Read-only mode metadata; the existing quantity payload, state and
        # frozen report/start hashes keep their original V1 canonical shape.
        from .operation_execution_mode import task_execution_mode, mode_display
        tasks[-1].update(mode_display(task_execution_mode(task, verify_current=False)))
        tasks[-1]['dateFacts'] = task_date_facts(task, start, report_dates=recorded_dates)
    selected = next((row for row in tasks if row['id'] == task_id), None) if task_id else None
    if work_order_id is not None and not tasks:_fail('OPERATION_REPORT_TASK_NOT_VISIBLE','当前测试工单不在本人报工读取范围。',403)
    if task_id and selected is None:
        _fail('OPERATION_REPORT_TASK_NOT_VISIBLE', '所选任务不属于当前账号本公司本人已开工范围。', 403)
    empty = {'ready': False, 'statusLabel': '请选择本人已开工任务', 'missingItems': ['请选择本人已开工任务。']}
    facts = {'contractVersion': CONTRACT, 'moduleCode': MODULE, 'factSource': 'server', 'currentStateSource': 'server',
        'usagePurpose':selected['usagePurpose'] if selected else ('MIXED_AUTHORIZED' if any(x['usagePurpose']=='PRODUCTION_USE' for x in tasks) else 'TEST_BUSINESS'),'purposeLabel':('正式生产用途来源（独立开发测试环境不代表企业放行）' if selected and selected['usagePurpose']=='PRODUCTION_USE' else '本人授权任务含正式与测试来源；各任务用途独立核验，独立环境不代表企业放行' if not selected and any(x['usagePurpose']=='PRODUCTION_USE' for x in tasks) else '隔离测试用途；服务测试代办记录按原办理账号追溯，不表示用户本人点击'),
        'companyId': actor.company_id, 'currentActorEvidence': evidence, 'tasks': tasks, 'selectedTask': selected,
        'qualification': selected['qualification'] if selected else empty,
        'availableActions': selected['availableActions'] if selected else {'report': {**action_contract(),
            'enabled': False, 'disabledReason': '请选择本人已开工任务。'}},
        'statusLabel': '本人已开工任务及正式报工事实已读取', 'businessWriteCount': 0, 'auditWriteCount': 0,
        'actualStartCount': 0, 'actualReportCount': 0, 'operationReportRecordCount': sum(len(row['reports']) for row in tasks),
        'reportRecordCount': sum(len(row['reports']) for row in tasks),
        'actualReportSupported': True, 'completionSupported': False, 'selfTaskOnly': True,
        'predecessorCompletionAuthorityAvailable': False}
    # Independent transport projection. The canonical report rows participate
    # in frozen completion hashes and must retain their exact original shape.
    report_ids = [r['id'] for t in tasks for r in t['reports']]
    originals = Report.objects.filter(pk__in=report_ids, company_id=actor.company_id, reported_by_id=actor.pk)
    hashes = {r.pk: r.request_hash for r in originals}
    facts['operationRequestProofs'] = [
        {'taskId': t['taskId'], 'recordId': r['id'], 'actorId': actor.pk, 'companyId': actor.company_id,
         'actionCode': REPORT_ACTION, 'requestKeyHash': r['requestKeyHash'],
         'requestHash': hashes[r['id']], 'auditReference': r['auditReference']}
        for t in tasks for r in t['reports'] if r['id'] in hashes]
    for t in tasks:
        proof = t.get('executionConfirmation')
        if proof:
            facts['operationRequestProofs'].append({'taskId': t['taskId'], 'actorId': actor.pk,
                'companyId': actor.company_id, 'actionCode': 'production.operation.confirm_execution',
                'requestKeyHash': proof['requestKeyHash'], 'requestHash': proof['requestHash'],
                'auditReference': proof['auditReference']})
    return facts


def _payload(payload):
    expected = {'expectedVersion', 'expectedSourceSnapshotHash', 'expectedAssignmentHash', 'expectedStartId',
        'expectedStartSnapshotHash', 'quantity', 'reason', 'idempotencyKey'}
    if not isinstance(payload, dict) or set(payload) != expected:
        _fail('OPERATION_REPORT_PAYLOAD_INVALID', '报工提交字段不符合正式合同；实际数量须由本人填写，时间由服务端确定。', 400)
    if type(payload['expectedVersion']) is not int or payload['expectedVersion'] < 0:
        _fail('OPERATION_REPORT_VERSION_REQUIRED', '请指定已读取任务的正式版本。', 400)
    if type(payload['expectedStartId']) is not int or payload['expectedStartId'] <= 0:
        _fail('OPERATION_REPORT_START_EXPECTATION_REQUIRED', '请指定已读取的正式开工记录。', 400)
    for field in ('expectedSourceSnapshotHash', 'expectedAssignmentHash', 'expectedStartSnapshotHash'):
        if not isinstance(payload[field], str) or not re.fullmatch('[0-9a-f]{64}', payload[field]):
            _fail('OPERATION_REPORT_SOURCE_EXPECTATION_REQUIRED', '请重新读取任务、人员及开工冻结来源。', 400)
    if not isinstance(payload['reason'], str) or not 2 <= len(payload['reason'].strip()) <= 300:
        _fail('OPERATION_REPORT_REASON_REQUIRED', '请填写2至300字的报工原因。', 400)
    if not isinstance(payload['idempotencyKey'], str) or not 1 <= len(payload['idempotencyKey']) <= 120:
        _fail('OPERATION_REPORT_IDEMPOTENCY_REQUIRED', '报工必须有有效防重复标识。', 400)
    _decimal(payload['quantity'], positive=True)


def _intent(actor, task_id, payload):
    request_hash = _request_hash(actor.pk, task_id, payload)
    old = MasterDataWriteRequest.objects.filter(organization_id=actor.company_id, action_code=REPORT_ACTION,
        idempotency_key=payload['idempotencyKey']).first()
    if old and (old.status != 'COMMITTED' or old.entity_type != OBJECT or old.request_hash != request_hash):
        _fail('OPERATION_REPORT_IDEMPOTENCY_CONFLICT', '防重复标识已经用于其他人员或报工意图。')
    return request_hash, old


def report_operation(*, user, task_id, payload):
    _payload(payload)
    if type(task_id) is not int or task_id <= 0:
        _fail('OPERATION_REPORT_QUERY_INVALID', '任务身份须为正式正整数。', 400)
    actor, _ = receipt_service._actor(user)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            task = Task.objects.select_for_update().filter(pk=task_id, company_id=actor.company_id).first()
            if task is None:
                _fail('OPERATION_REPORT_TASK_NOT_VISIBLE', '未找到本公司本人已开工任务。', 403)
            if getattr(task, 'execution_mode', 'QUANTIFIED') != 'QUANTIFIED':
                _fail('OPERATION_REPORT_NON_QUANTIFIED', '本任务不单独计量，请登记实际经过；不能提交数量报工。', 400)
            facts = read_operation_reports(user=actor, task_id=task_id)
            selected = facts['selectedTask']
            request_hash, replay = _intent(actor, task_id, payload)
            start = Start.objects.get(task_id=task.pk)
            if (task.version != payload['expectedVersion'] or task.source_snapshot_hash != payload['expectedSourceSnapshotHash']
                    or task.assignment_hash != payload['expectedAssignmentHash'] or start.pk != payload['expectedStartId']
                    or _hash(_start_snapshot(start)) != payload['expectedStartSnapshotHash']):
                _fail('OPERATION_REPORT_SOURCE_OR_VERSION_CHANGED', '任务、来源、冻结执行人员或开工事实已变化，请只读重新核对。')
            unit, unit_snapshot = _unit(task)
            amount = _decimal(payload['quantity'], positive=True, precision=unit.decimal_places)
            if replay:
                matched = next((r for r in selected['reports'] if str(r['id']) == replay.target_entity_id), None)
                if matched is None or matched['requestKeyHash'] != sha256(payload['idempotencyKey'].encode('utf-8')).hexdigest():
                    _fail('OPERATION_REPORT_IDEMPOTENCY_CONFLICT', '防重复账本未指向该任务正式报工记录。')
                # The historical intent is already committed. Validate current
                # rights separately from a total-reached state; never add it twice.
                q = _qualification(actor, task, start, selected['qualification']['sourceFacts'],
                    _quantity_facts(task, unit, Decimal(matched['reportedBefore'])))
                if not q['ready']:
                    _fail('OPERATION_REPORT_NOT_READY', '；'.join(q['missingItems']), 403)
                return facts, _writes(True)
            if not selected['availableActions']['report']['enabled']:
                _fail('OPERATION_REPORT_NOT_READY', selected['availableActions']['report']['disabledReason'], 403)
            before_total = Decimal(selected['reportedQuantity'])
            after_total = _add(before_total, amount)
            if after_total > _decimal(task.workload_quantity, positive=True):
                _fail('OPERATION_REPORT_QUANTITY_EXCEEDED', '本次报工将超过正式任务剩余未报量；未截断或修改输入。', 400)
            q = selected['qualification']
            record = create_business_object_with_initial_state(model=Report, initial_state='reported',
                company_id=task.company_id, task=task, start=start, work_order_id=task.work_order_id, receipt_id=task.receipt_id,
                source_operation_id=task.source_operation_id, workshop_id=task.workshop_id, work_center_id=task.work_center_id,
                workload_quantity=task.workload_quantity, workload_uom_id=task.workload_uom_id, task_version=task.version,
                quantity=payload['quantity'], reported_before=_text(before_total), reported_after=_text(after_total),
                quantity_precision=unit.decimal_places, unit_snapshot=unit_snapshot,
                source_snapshot=deepcopy(task.source_snapshot), source_snapshot_hash=task.source_snapshot_hash,
                assignment_snapshot=deepcopy(task.assignment_snapshot), assignment_hash=task.assignment_hash,
                start_snapshot=_start_snapshot(start), start_snapshot_hash=_hash(_start_snapshot(start)),
                execution_position_id=task.execution_position_id, execution_employee_id=task.execution_employee_id,
                reported_by=actor, reported_at=timezone.now(), report_qualification=deepcopy(q), reason=payload['reason'].strip(),
                request_key_hash=sha256(payload['idempotencyKey'].encode('utf-8')).hexdigest(), request_hash=request_hash)
            audit = record_audit(user=actor, action_code=REPORT_ACTION, target=record, target_type=OBJECT,
                target_no=task.no, before={'status': ''}, after=_state(record), authorization=q['authorization'], reason=record.reason)
            node = {'processCode': PROCESS, 'nodeCode': WORKFLOW_NODE, 'processId': q['definitionId'], 'nodeId': q['nodeId']}
            audit.before_snapshot['workflowNode'] = node; audit.after_snapshot['workflowNode'] = node
            audit.save(update_fields=['before_snapshot', 'after_snapshot'])
            record_projected_business_transition(object_type=OBJECT, object_id=record.pk, source_state='', target_state='reported',
                action_code=REPORT_ACTION, operator=actor, reason=record.reason,
                audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions={('', 'reported')})
            identity = ExternalIdentity.objects.create(organization_id=actor.company_id, source_system='MES_OPERATION_REPORT',
                source_type='INTERNAL', source_object_type='ProductionOperationReportRequest', external_id=record.request_key_hash,
                target_entity_type=OBJECT, target_entity_id=str(record.pk), mapping_status='MATCH', source_fingerprint=request_hash,
                audit_metadata={'actualQuantityOnly': True, 'completionProven': False})
            MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=REPORT_ACTION,
                entity_type=OBJECT, idempotency_key=payload['idempotencyKey'], request_hash=request_hash, source_identity=identity,
                status='COMMITTED', target_entity_id=str(record.pk),
                result={'taskId': task.pk, 'operationStartId': start.pk, 'operationReportId': record.pk},
                audit_metadata={'actorId': actor.pk, 'actualQuantityOnly': True, 'completionProven': False})
            _verify_record(record, task, start, before_total)
            return read_operation_reports(user=actor, task_id=task_id), _writes()
    except IntegrityError:
        _fail('OPERATION_REPORT_CONCURRENT_CONFLICT', '报工或防重复标识已由其他操作保存，请只读刷新。')
    except DatabaseError:
        _fail('OPERATION_REPORT_TRANSACTION_FAILED', '报工事务结果尚未核实，请先只读刷新，不会自动重放。', 503)


def _writes(replay=False):
    count = 0 if replay else 1
    return {'idempotent': replay, 'businessWriteCount': count, 'auditWriteCount': count,
        'operationReportCreatedCount': count, 'stateTransitionWriteCount': count, 'actualReportCount': count,
        'actualStartCount': 0, 'actualDispatchCount': 0, 'completionCreatedCount': 0, 'workOrderUpdatedCount': 0,
        'operationSourceUpdatedCount': 0, 'taskUpdatedCount': 0, 'resourceOccupancyReleasedCount': 0,
        'scheduleUpdatedCount': 0, 'inventoryUpdatedCount': 0}
