"""Append-only completion projection with shared, separate-person approval.

No Task/Start/Report, source, inventory, schedule, reservation or successor is
updated. A request is pending evidence; only a verified shared decision makes
this independent completion projection effective.
"""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import re

from django.db import IntegrityError, transaction
from django.utils import timezone
from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.models import (OrganizationOperatingAuditRecord, PositionResponsibility,
    PositionWorkflowResponsibility, User)
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from workflow_runtime.models import (ProcessDefinition, WorkflowNodeDefinition, WorkflowInstance, ApprovalTask,
    ApprovalDecision, BusinessStateTransition)
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition, transition_business_object)
from . import mes_test_source_bridge as formal
from . import mes_test_source_bridge as receipt
from . import mes_test_source_bridge as starts
from . import operation_report_service as reports
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_start_models import ProductionOperationStart as Start
from .services import PlanningBusinessError, record_audit
from .mes_test_source_bridge import _hash, _fail
from .mes_test_source_bridge import _effective
from .workshop_task_time import task_datetime_label
from .mes_task_date_facts import task_date_facts
from .operation_completion_contract import (CONTRACT, MODULE, OBJECT, PROCESS, BUSINESS_PROCESS,
    READ_PERMISSION, REQUEST_ACTION, APPROVE_ACTION, REQUEST_NODE, REVIEW_NODE,
    REQUEST_RESPONSIBILITY, REVIEW_RESPONSIBILITY, LABELS, action_contract, register_actions)
from .mes_test_source_bridge import _assert_hash
from workflow_runtime.definition_service import WorkflowDefinitionError

EXPECTED = ('expectedVersion', 'expectedSourceSnapshotHash', 'expectedAssignmentHash', 'expectedStartId',
    'expectedStartSnapshotHash', 'expectedReportSetHash', 'expectedCompletionVersion')

def _person(actor):
    employee, position, department, workshop, evidence = receipt._employees(actor)
    today = starts._today()
    unique = Employee.objects.filter(user_id=actor.pk).count() == 1
    valid = bool(employee and position and department and not actor.is_superuser
        and unique
        and _effective(position, today) and _effective(department, today)
        and position.company_id == department.company_id == actor.company_id
        and position.department_id == department.pk
        and (employee.hire_date is None or employee.hire_date <= today)
        and (employee.leave_date is None or employee.leave_date > today)
        and (employee.resignation_date is None or employee.resignation_date > today))
    evidence.update(uniqueEmployeeAccountLink=unique, currentEmploymentValid=valid)
    return employee, position, evidence, valid

def _setup():
    definition = ProcessDefinition.objects.filter(definition_code=PROCESS, active=True,
        business_domain='MES', document_type=OBJECT).first()
    if definition:
        try:
            _assert_hash(definition)
        except WorkflowDefinitionError:
            _fail('OPERATION_COMPLETION_TEMPLATE_UNPROVEN', '正式工序完工审核模板与已保存内容哈希不一致。')
    nodes = {}
    for action, code in ((REQUEST_ACTION, REQUEST_NODE), (APPROVE_ACTION, REVIEW_NODE)):
        nodes[action] = definition.nodes.filter(node_code=code, business_action_code=action, active=True).first() if definition else None
    return definition, nodes

def _role(actor, action, task):
    employee, position, evidence, valid = _person(actor)
    definition, nodes = _setup(); node = nodes[action]
    duty_code = REQUEST_RESPONSIBILITY if action == REQUEST_ACTION else REVIEW_RESPONSIBILITY
    ownership = 'EXECUTOR' if action == REQUEST_ACTION else 'REVIEWER'
    duties = list(PositionResponsibility.objects.filter(position=position, active=True,
        responsibility__code=duty_code, responsibility__status='ACTIVE', responsibility__is_active=True)
        .select_related('responsibility')) if valid else []
    duty = duties[0] if len(duties) == 1 and _effective(duties[0].responsibility, starts._today()) else None
    mappings = list(PositionWorkflowResponsibility.objects.filter(position=position, responsibility=duty.responsibility,
        workflow_node=node, workflow_code=PROCESS, node_code=node.node_code, ownership_type=ownership, active=True)) if duty and node else []
    mapping = mappings[0] if len(mappings) == 1 and _effective(mappings[0], starts._today()) else None
    allowed, matched, native = receipt._authority(actor, action, task.workshop.department_id, actor.pk)
    issues = []
    if not valid: issues.append('当前账号缺少唯一有效的同公司本人任职、岗位和部门关系。')
    if not definition or not node: issues.append('正式工序完工申请及生产跟单审核模板尚未核实。')
    if not duty or not mapping: issues.append('当前岗位缺少本动作独立完工职责及精确流程责任映射。')
    if not allowed: issues.append('当前账号缺少同一独立角色的本动作权限及本公司数据范围。')
    evidence.update(positionResponsibilityId=duty.pk if duty else None,
        workflowResponsibilityId=mapping.pk if mapping else None,
        responsibilityId=duty.responsibility_id if duty else None,
        workflowNodeId=node.pk if node else None, workflowProcessCode=PROCESS,
        workflowNodeCode=node.node_code if node else None, responsibilityCode=duty_code, ownershipType=ownership,
        matchedRoleCodes=sorted({row['roleCode'] for row in matched}), matchedAuthorityEvidence=matched)
    return {'ready':not issues, 'missingItems':issues, 'currentActorEvidence':evidence,
        'authorization':native, 'definitionId':definition.pk if definition else None,
        'nodeId':node.pk if node else None, 'definitionHash':definition.definition_hash if definition else None,
        'roleCodes':evidence['matchedRoleCodes']}

def _bundle(task, actor):
    start = Start.objects.filter(task_id=task.pk).first()
    source = starts._source(task, actor)
    if not start:
        return {'ready':False, 'issues':['任务尚无正式开工记录，不能申请或确认完工。'],
            'start':None, 'reports':[], 'quantity':None, 'snapshot':None, 'snapshotHash':None,
            'reportSetHash':_hash([]), 'startHash':None, 'source':source}
    starts._verify_record(start, task)
    if getattr(task, 'execution_mode', 'QUANTIFIED') != 'QUANTIFIED':
        return _nonquantified_bundle(task, actor, start, source)
    unit, unit_snapshot = reports._unit(task)
    records, total = reports._reports(task, start)
    quantity = reports._quantity_facts(task, unit, total)
    start_hash = _hash(reports._start_snapshot(start))
    snapshot = {'companyId':task.company_id, 'taskId':task.pk, 'workOrderId':task.work_order_id,
        'sourceOperationId':task.source_operation_id, 'receiptId':task.receipt_id,
        'taskVersion':task.version, 'sourceSnapshotHash':task.source_snapshot_hash,
        'assignmentHash':task.assignment_hash, 'startId':start.pk, 'startSnapshotHash':start_hash,
        'reports':records, 'reportSetHash':_hash(records), 'workloadQuantity':task.workload_quantity,
        'reportedQuantity':quantity['reportedQuantity'], 'remainingQuantity':quantity['remainingQuantity'],
        'unitSnapshot':unit_snapshot, 'quantityPrecision':unit.decimal_places}
    issues = []
    if not source['ready']: issues.append(source['statusLabel'])
    if not records: issues.append('尚无经正式审计核验的报工记录。')
    if Decimal(quantity['remainingQuantity']) != 0:
        issues.append('正式报工量尚未达到当前任务作业量，不能申请或确认本次完工。')
    return {'ready':not issues, 'issues':issues, 'start':start, 'reports':records, 'quantity':quantity,
        'snapshot':snapshot, 'snapshotHash':_hash(snapshot), 'reportSetHash':_hash(records),
        'startHash':start_hash, 'source':source}


def _nonquantified_bundle(task, actor, start, source):
    from .operation_execution_mode import task_execution_mode
    from .operation_execution_confirmation_service import _history as execution_history, quantity_facts
    mode=task_execution_mode(task,actor=actor)
    frozen_mode=task_execution_mode(task,verify_current=False)
    confirmation=execution_history(task,start)
    evidence=[] if not confirmation else [{'proofType':'ACTUAL_EXECUTION_CONFIRMATION',
        'ref':confirmation['ref'],'proofHash':confirmation['proofHash'],
        'requestHash':confirmation['requestHash'],'auditReference':confirmation['auditReference']}]
    start_hash=_hash(reports._start_snapshot(start));report_hash=_hash(evidence)
    snapshot={'companyId':task.company_id,'taskId':task.pk,'workOrderId':task.work_order_id,
        'sourceOperationId':task.source_operation_id,'receiptId':task.receipt_id,
        'taskVersion':task.version,'sourceSnapshotHash':task.source_snapshot_hash,'assignmentHash':task.assignment_hash,
        'startId':start.pk,'startSnapshotHash':start_hash,'executionMode':frozen_mode['executionMode'],
        'modeSourceHash':frozen_mode['modeSourceHash'],'quantityApplicable':False,
        'executionEvidence':evidence,'executionConfirmation':confirmation,'reportSetHash':report_hash,
        'workloadQuantity':None,'reportedQuantity':None,'remainingQuantity':None,'unitSnapshot':None,'quantityPrecision':None}
    issues=[]
    if not source['ready']:issues.append(source['statusLabel'])
    if mode['executionMode']!='NON_QUANTIFIED_REQUIRED' or not mode['ready']:
        issues.extend(mode.get('blockingReasons') or ['正式执行模式尚未核实，不能申请或确认完工。'])
    if not confirmation:issues.append('尚无本人真实开工后登记、经独立回读核验的实际经过证明。')
    if reports.Report.objects.filter(task_id=task.pk).exists():issues.append('不可统计任务存在数量报工冲突，禁止审核生效。')
    return {'ready':not issues,'issues':issues,'start':start,'reports':[],'quantity':quantity_facts(),
        'snapshot':snapshot,'snapshotHash':_hash(snapshot),'reportSetHash':report_hash,'startHash':start_hash,
        'source':source,'executionMode':frozen_mode,'executionConfirmation':confirmation}

def _audit(event, object_type, object_id):
    match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', event.audit_reference or '')
    row = OrganizationOperatingAuditRecord.objects.select_related('actor').defer('actor__password').filter(pk=int(match[1])).first() if match else None
    if (not row or row.target_type != object_type or row.target_id != object_id or row.actor_id != event.operator_id
            or row.action_code != event.action_code or row.reason != event.reason
            or not isinstance(row.before_snapshot, dict) or not isinstance(row.after_snapshot, dict)):
        _fail('OPERATION_COMPLETION_HISTORY_UNPROVEN', '完工状态缺少同对象、同动作和同操作人的真实审计。')
    before, after = row.before_snapshot.get('state'), row.after_snapshot.get('state')
    authorization = row.after_snapshot.get('authorization')
    node = row.after_snapshot.get('workflowNode')
    node_code = REQUEST_NODE if event.action_code == REQUEST_ACTION else REVIEW_NODE
    if (not isinstance(before, dict) or not isinstance(after, dict)
            or before.get('status') != event.source_state or after.get('status') != event.target_state
            or after.get('contractVersion') != CONTRACT
            or not isinstance(authorization, dict) or authorization.get('allowed') is not True
            or not isinstance(authorization.get('permissionCodes'), list)
            or event.action_code not in authorization['permissionCodes']
            or not isinstance(authorization.get('roleCodes'), list) or not authorization['roleCodes']
            or any(not isinstance(code,str) or not code for code in authorization['roleCodes'])
            or not isinstance(node,dict) or node.get('processCode') != PROCESS
            or node.get('businessProcessCode') != BUSINESS_PROCESS or node.get('nodeCode') != node_code
            or any(type(node.get(key)) is not int or node[key] <= 0 for key in ('processId','nodeId'))
            or row.before_snapshot.get('workflowNode') != node):
        _fail('OPERATION_COMPLETION_HISTORY_UNPROVEN', '完工转换、审计前后状态或授权快照不一致。')
    if not WorkflowNodeDefinition.objects.filter(pk=node['nodeId'],process_definition_id=node['processId'],
            process_definition__definition_code=PROCESS,process_definition__active=True,
            node_code=node_code,business_action_code=event.action_code,active=True).exists():
        _fail('OPERATION_COMPLETION_HISTORY_UNPROVEN', '完工审计未绑定对应的正式内部审批节点。')
    return row, after

def _shared_history(obj, name, completed, company_id, task_id, closure=None):
    events = list(BusinessStateTransition.objects.filter(object_type=name, object_id=obj.pk).order_by('version','pk'))
    if closure is not None:
        from .operation_completion_v3_authority import closure_facts
        closure_facts(closure)
        expected_id=closure.workflow_instance_id if name=='WorkflowInstance' else closure.approval_task_id
        if obj.pk!=expected_id or completed or len(events)!=2 or obj.status!='closed':
            _fail('OPERATION_COMPLETION_WORKFLOW_UNPROVEN','原待审关闭未绑定准确共享对象。')
        events=events[:1]
    expected = [('', 'pending', REQUEST_ACTION)] + ([('pending', 'approved', APPROVE_ACTION)] if completed else [])
    if len(events) != len(expected) or (closure is None and (obj.version != len(expected) or obj.status != expected[-1][1])):
        _fail('OPERATION_COMPLETION_WORKFLOW_UNPROVEN', '共享审批实例或任务的状态、版本及真实转换历史不一致。')
    for version, (event, states) in enumerate(zip(events, expected), 1):
        if event.version != version or (event.source_state,event.target_state,event.action_code) != states:
            _fail('OPERATION_COMPLETION_WORKFLOW_UNPROVEN', '共享审批转换链不符合工序完工审核合同。')
        audit, state = _audit(event, name, obj.pk)
        if audit.organization_id != company_id or state.get('completionTaskId') != task_id:
            _fail('OPERATION_COMPLETION_WORKFLOW_UNPROVEN', '共享审批转换不属于本公司本任务。')
    return events

def _binding_hash(actor_id, action, task_id, payload):
    body = {key:value for key,value in payload.items() if key != 'idempotencyKey'}
    body['reason'] = body['reason'].strip()
    body['requestKeyHash'] = sha256(payload['idempotencyKey'].encode()).hexdigest()
    return _hash({'actorId':actor_id,'action':action,'taskId':task_id,'payload':body})

def _verify_ledger(state, action, task):
    rows = list(MasterDataWriteRequest.objects.filter(organization_id=task.company_id, action_code=action,
        entity_type=OBJECT, target_entity_id=str(task.pk), request_hash=state['intentHash']).select_related('source_identity'))
    ledger = rows[0] if len(rows) == 1 else None
    if (not ledger or ledger.status != 'COMMITTED'
            or sha256(ledger.idempotency_key.encode()).hexdigest() != state['intentKeyHash']
            or ledger.source_identity.organization_id != task.company_id
            or ledger.source_identity.target_entity_type != OBJECT or ledger.source_identity.target_entity_id != str(task.pk)
            or ledger.source_identity.source_system != 'MES_OPERATION_COMPLETION'
            or ledger.source_identity.source_type != 'INTERNAL' or ledger.source_identity.source_object_type != action
            or ledger.source_identity.external_id != state['intentKeyHash']
            or ledger.source_identity.mapping_status != 'MATCH' or ledger.source_identity.source_fingerprint != ledger.request_hash
            or not isinstance(ledger.audit_metadata, dict)
            or ledger.audit_metadata.get('actorId') != state['actorEvidence']['userId']
            or ledger.audit_metadata.get('contractVersion') != CONTRACT
            or not isinstance(ledger.source_identity.audit_metadata, dict)
            or ledger.source_identity.audit_metadata.get('contractVersion') != CONTRACT
            or ledger.source_identity.audit_metadata.get('downstreamReleased') is not False
            or ledger.result != {'taskId':task.pk,'workflowInstanceId':state['workflowInstanceId'],
                'approvalTaskId':state['approvalTaskId'],'completed':action == APPROVE_ACTION}):
        _fail('OPERATION_COMPLETION_LEDGER_UNPROVEN', '完工防重复账本、来源身份和正式结果不一致。')
    try:
        _payload({**state['intentPayload'],'idempotencyKey':ledger.idempotency_key},
            'request' if action == REQUEST_ACTION else 'approve')
    except PlanningBusinessError:
        _fail('OPERATION_COMPLETION_LEDGER_UNPROVEN', '历史完工意图字段或类型不符合正式合同。')
    if _binding_hash(state['actorEvidence']['userId'], action, task.pk,
            {**state['intentPayload'],'idempotencyKey':ledger.idempotency_key}) != ledger.request_hash:
        _fail('OPERATION_COMPLETION_LEDGER_UNPROVEN', '完工意图与防重复账本哈希不一致。')
    return ledger

def _legacy_history(task, bundle, closure=None):
    events = list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=task.pk).order_by('version','pk'))
    workflow = WorkflowInstance.objects.filter(document_type=OBJECT, document_id=task.pk).first()
    if not events:
        if workflow or MasterDataWriteRequest.objects.filter(organization_id=task.company_id, entity_type=OBJECT, target_entity_id=str(task.pk)).exists():
            _fail('OPERATION_COMPLETION_HISTORY_UNPROVEN', '存在未能匹配正式转换的完工审批或账本。')
        return None
    if len(events) not in (1,2) or not workflow:
        _fail('OPERATION_COMPLETION_HISTORY_UNPROVEN', '完工申请与共享审批链不完整。')
    expected = [('', 'pending_review', REQUEST_ACTION)] + ([('pending_review','completed',APPROVE_ACTION)] if len(events)==2 else [])
    definition, nodes = _setup()
    states, audits = [], []
    for version, (event, triple) in enumerate(zip(events,expected),1):
        if event.version != version or (event.source_state,event.target_state,event.action_code) != triple:
            _fail('OPERATION_COMPLETION_HISTORY_UNPROVEN', '完工申请与审核状态转换不符合正式合同。')
        audit, state = _audit(event, OBJECT, task.pk)
        evidence = state.get('actorEvidence')
        positive_ids = ('userId','companyId','employeeId','positionId','responsibilityId',
            'positionResponsibilityId','workflowResponsibilityId','workflowNodeId')
        role_codes = evidence.get('matchedRoleCodes') if isinstance(evidence,dict) else None
        if (not isinstance(evidence,dict)
                or any(type(evidence.get(key)) is not int or evidence[key] <= 0 for key in positive_ids)
                or not isinstance(role_codes,list) or not role_codes
                or any(not isinstance(code,str) or not code for code in role_codes)
                or len(role_codes)!=len(set(role_codes))
                or not isinstance(state.get('intentPayload'),dict)
                or not isinstance(state.get('sourceSnapshot'),dict)
                or any(not isinstance(state.get(key),str) or not re.fullmatch('[0-9a-f]{64}',state[key])
                    for key in ('sourceSnapshotHash','intentKeyHash','intentHash'))
                or any(type(state.get(key)) is not int or state[key] <= 0
                    for key in ('taskId','companyId','definitionId','workflowInstanceId','approvalTaskId'))
                or not definition or not nodes[event.action_code]
                or state.get('definitionId') != definition.pk or state.get('definitionHash') != definition.definition_hash
                or audit.organization_id != task.company_id or audit.actor.company_id != task.company_id
                or evidence.get('userId') != audit.actor_id or evidence.get('companyId') != task.company_id
                or evidence.get('uniqueEmployeeAccountLink') is not True or evidence.get('currentEmploymentValid') is not True
                or evidence.get('workflowProcessCode') != PROCESS or evidence.get('workflowNodeId') != nodes[event.action_code].pk
                or evidence.get('workflowNodeCode') != nodes[event.action_code].node_code
                or evidence.get('responsibilityCode') != (REQUEST_RESPONSIBILITY if version==1 else REVIEW_RESPONSIBILITY)
                or evidence.get('ownershipType') != ('EXECUTOR' if version==1 else 'REVIEWER')
                or not set(role_codes).issubset(set(audit.after_snapshot['authorization']['roleCodes']))
                or state.get('taskId') != task.pk or state.get('companyId') != task.company_id
                or state.get('workflowInstanceId') != workflow.pk
                or state.get('sourceSnapshotHash') != _hash(state.get('sourceSnapshot'))
                or not bundle['snapshot'] or state.get('sourceSnapshotHash') != bundle['snapshotHash']):
            _fail('OPERATION_COMPLETION_HISTORY_UNPROVEN', '完工责任、来源、开工、数量或报工快照无法完整回读。')
        _verify_ledger(state, event.action_code, task)
        if (state['intentPayload']['reason'].strip() != event.reason
                or state['intentPayload']['expectedCompletionVersion'] != version-1
                or (version==1 and (event.operator_id != bundle['start'].started_by_id
                    or evidence['employeeId'] != task.execution_employee_id
                    or evidence['positionId'] != task.execution_position_id))):
            _fail('OPERATION_COMPLETION_HISTORY_UNPROVEN', '完工申请执行人、岗位或历史操作意图与正式来源不一致。')
        states.append(state); audits.append(audit)
    first, last = states[0], states[-1]
    approval_tasks = list(workflow.tasks.all())
    approval = approval_tasks[0] if len(approval_tasks)==1 else None
    completed = len(events)==2
    if (workflow.document_type != OBJECT or workflow.document_id != task.pk or workflow.current_step != 1 or workflow.total_steps != 1
            or workflow.process_definition_id != first.get('definitionId') or not approval
            or approval.pk != first['approvalTaskId'] or last['approvalTaskId'] != approval.pk
            or approval.step_no != 1 or approval.minimum_approvals != 1 or approval.allow_parallel
            or not isinstance(first.get('reviewerRoleCode'),str) or not first['reviewerRoleCode']
            or approval.required_role_code != first['reviewerRoleCode']
            or last.get('reviewerRoleCode') != first['reviewerRoleCode']):
        _fail('OPERATION_COMPLETION_WORKFLOW_UNPROVEN', '工序完工未匹配单一正式共享审批实例与任务。')
    workflow_events = _shared_history(workflow, 'WorkflowInstance', completed, task.company_id, task.pk, closure)
    approval_events = _shared_history(approval, 'ApprovalTask', completed, task.company_id, task.pk, closure)
    if (any(event.workflow_instance_id != workflow.pk for event in events)
            or any(shared.operator_id != event.operator_id for group in (workflow_events,approval_events) for shared,event in zip(group,events))
            or bool(workflow.completed_at) != bool(completed or closure) or bool(approval.completed_at) != bool(completed or closure)):
        _fail('OPERATION_COMPLETION_WORKFLOW_UNPROVEN', '完工投影、共享审批操作人或实际完成时间不一致。')
    decisions = list(approval.decisions.all())
    decision = decisions[0] if len(decisions)==1 else None
    if completed:
        if (not decision or decision.decision != 'approved' or decision.decision_sequence != 1
                or decision.actor_id != events[-1].operator_id or decision.comment != events[-1].reason
                or decision.action_id != APPROVE_ACTION or decision.pk != last.get('approvalDecisionId')
                or decision.decision_hash != last['intentHash']
                or sha256(decision.idempotency_key.encode()).hexdigest() != last['intentKeyHash']
                or events[0].operator_id == decision.actor_id
                or set(first['actorEvidence']['matchedRoleCodes']) & set(last['actorEvidence']['matchedRoleCodes'])
                or approval.required_role_code not in last['actorEvidence']['matchedRoleCodes']):
            _fail('OPERATION_COMPLETION_DECISION_UNPROVEN', '审核决策、申请审核人员/角色分离或确认生效证据不一致。')
    elif decisions:
        _fail('OPERATION_COMPLETION_DECISION_UNPROVEN', '待审核申请出现未核实的审核决策。')
    zone = task.work_order.source_schedule.timezone
    return {'statusCode':'completed' if completed else 'pending_review', 'statusLabel':LABELS['completed' if completed else 'pending_review'],
        'projectionVersion':len(events), 'sourceSnapshotHash':first['sourceSnapshotHash'],
        'applicantId':events[0].operator_id, 'applicantLabel':first['actorEvidence'].get('employeeName') or audits[0].actor.real_name,
        'requestReason':events[0].reason, 'requestedAtLabel':task_datetime_label(audits[0].created_at,zone),
        'requestAuditReference':events[0].audit_reference, 'requestKeyHash':first['intentKeyHash'], 'requestHash':first['intentHash'],
        'reviewerId':decision.actor_id if decision else None,
        'reviewerLabel':last['actorEvidence'].get('employeeName') if completed else None,
        'reviewReason':events[-1].reason if completed else None,
        'completedAtLabel':task_datetime_label(audits[-1].created_at,zone) if completed else None,
        'approvalAuditReference':events[-1].audit_reference if completed else None,
        'approvalRequestKeyHash':last['intentKeyHash'] if completed else None,
        'approvalRequestHash':last['intentHash'] if completed else None,
        'workflowInstanceId':workflow.pk, 'workflowVersion':workflow.version,
        'approvalTaskId':approval.pk, 'approvalTaskVersion':approval.version,
        'approvalDecisionId':decision.pk if decision else None,
        'reviewerRoleCode':approval.required_role_code, 'applicantRoleCodes':first['actorEvidence']['matchedRoleCodes'],
        'stateMachineConsistent':True, 'statusTransitionCount':len(events),
        'statusTransitionHistory':[{'id':event.pk,'version':event.version,'actionCode':event.action_code,
            'actionLabel':'提交工序完工申请' if event.action_code==REQUEST_ACTION else '审核确认工序完工',
            'sourceStateLabel':LABELS[event.source_state], 'targetStateLabel':LABELS[event.target_state],
            'operatorId':event.operator_id,'timestampLabel':task_datetime_label(event.timestamp,zone),
            'auditReference':event.audit_reference} for event in events]}

def _history(task, bundle):
    from .operation_completion_v3_authority import read_effective_completion
    return read_effective_completion(task,bundle)


class _Facts:
    def __init__(self, actor, task, state): self.actor,self.task,self.state=actor,task,state
    def read(self,module_code,object_ids):
        valid=module_code==MODULE and object_ids==[str(self.task.pk)] and self.task.company_id==self.actor.company_id
        return {'found':valid,'objectIds':object_ids if valid else [],'statuses':[self.state] if valid else [],
            'legalEntityIds':[str(self.task.company_id)] if valid else [],'currentStateSource':'server'}

def _reviewers(task, applicant_id, applicant_roles):
    _,nodes = _setup(); node=nodes[APPROVE_ACTION]
    position_ids=PositionWorkflowResponsibility.objects.filter(workflow_node=node,workflow_code=PROCESS,
        node_code=REVIEW_NODE,ownership_type='REVIEWER',active=True).values_list('position_id',flat=True) if node else []
    employees=formal_employee_queryset(company_id=task.company_id).filter(position_ref_id__in=position_ids,
        user__is_active=True,user__is_superuser=False).exclude(user_id=applicant_id)
    options=[]
    for user_id in employees.values_list('user_id',flat=True).distinct():
        actor=User.objects.defer('password').get(pk=user_id); q=_role(actor,APPROVE_ACTION,task)
        if q['ready'] and not set(q['roleCodes']) & set(applicant_roles):
            options.append({'userId':actor.pk,'label':q['currentActorEvidence']['employeeName'],'roleCodes':q['roleCodes']})
    return options

def _qualification(actor, task, bundle, completion, key):
    action=REQUEST_ACTION if key=='request' else APPROVE_ACTION
    q=_role(actor,action,task); issues=q['missingItems'][:]
    lifecycle=[]
    state=completion['statusCode'] if completion else 'unrequested'
    issues.extend(bundle['issues'])
    if key=='request':
        employee,position,_,_,_,valid=starts._identity(actor)
        from .operation_executor_scope import executor_scope
        scope=executor_scope(position,company_id=task.company_id,workshop_id=task.workshop_id,
            operation_id=task.source_operation.operation_id,work_center_id=task.work_center_id)
        if not scope['ready']: issues.append(scope['statusLabel'])
        if not (valid and starts._owned(actor,task,employee) and position
                and position.pk==task.execution_position_id and bundle['start']
                and bundle['start'].started_by_id==actor.pk and bundle['start'].execution_position_id==position.pk):
            issues.append('须由任务冻结执行人及实际开工人本人提出完工申请。')
        if completion:
            message='本任务已有完工申请或已审核生效，不重复创建。'
            issues.append(message);lifecycle.append(message)
        options=_reviewers(task,actor.pk,q['roleCodes']) if q['ready'] else []
        reviewer_roles={role for row in options for role in row['roleCodes']}
        if len(reviewer_roles)!=1:
            issues.append('尚未解析到同公司、与申请人及申请角色分离的唯一生产跟单审核角色。')
        q['reviewerRoleCode']=next(iter(reviewer_roles)) if len(reviewer_roles)==1 else None
        q['reviewerCandidates']=options
    else:
        if not completion or state!='pending_review':
            message='当前没有可审核的待确认完工申请。'
            issues.append(message);lifecycle.append(message)
        if completion:
            if actor.pk==completion['applicantId']: issues.append('完工申请人不得审核本人申请。')
            if set(q['roleCodes']) & set(completion['applicantRoleCodes']): issues.append('申请与审核必须使用不同的独立角色。')
            if completion['reviewerRoleCode'] not in q['roleCodes']: issues.append('当前账号不属于本次共享审核任务要求的生产跟单角色。')
    decision=ActionPermissionValidator(fact_provider=_Facts(actor,task,state)).evaluate(user=actor,module_code=MODULE,
        action_code=action,object_ids=[task.pk],selection_count=1,requested_legal_entity_id=str(task.company_id))
    if not decision['granted'] and not issues: issues.append(decision['reason'] or '正式动作服务端校验未通过。')
    admission=[message for message in issues if message not in lifecycle]
    normal_label=('本次完工数据已审核' if state=='completed' else
        '本次完工申请已提交，待审核' if state=='pending_review' else '尚无已提交的完工申请')
    q.update(ready=not issues,missingItems=issues,admissionMissingItems=admission,lifecycleMissingItems=lifecycle,
        statusLabel=('可以提出工序完工申请，审核后方生效' if key=='request' else '可以审核确认本次工序完工') if not issues
            else '工序完工准入未通过' if admission else normal_label)
    return q

def _record_progress(task, completion, qualification):
    """Read-only display of one verified request; never an execution authority.

    The current business contract admits one request/review per task.  The
    stable request event identifies that record across refreshes and accounts;
    another task's request cannot reuse its progress.
    """
    submitted=completion is not None
    reviewed=bool(completion and completion['approvalDecisionId'])
    record_id=completion['statusTransitionHistory'][0]['id'] if submitted else None
    identity={'companyId':task.company_id,'taskId':task.pk,'requestTransitionId':record_id,
        'workflowInstanceId':completion['workflowInstanceId'],
        'requestAuditReference':completion['requestAuditReference']} if submitted else None
    submission_label='本次完工申请已提交，待审核' if submitted and not reviewed else '本次完工申请已提交' if submitted else '未提交'
    review_label='本次完工数据已审核' if reviewed else '待生产跟单员审核' if submitted else '尚无已提交的完工申请'
    admission=qualification['admissionMissingItems'][:]
    return {'contractVersion':'PCE-OPERATION-COMPLETION-PROGRESS-V1','recordId':record_id,
        'recordKey':f'{OBJECT}:{task.company_id}:{task.pk}:{record_id}' if submitted else None,
        'recordIdentity':identity,'submitted':submitted,'reviewed':reviewed,
        'submissionLabel':submission_label,'reviewLabel':review_label,
        'requestButtonLabel':'已提交' if submitted else '提交完工申请',
        'approveButtonLabel':'已审核' if reviewed else '审核完工数据',
        'admissionIssues':admission,'noticeLabel':'当前操作条件需要核对' if admission else review_label if reviewed else submission_label,
        'reviewResponsibilityLabel':'生产跟单员',
        'scope':'ONE_REQUEST_AND_ONE_REVIEW_PER_TASK',
        'scopeLabel':'每个任务仅一笔完工申请及一次审核；可逐个任务查看各自记录，不支持同任务分批、追加或多轮申请。'}

def _mode_display(task,actor,bundle):
    # Add read-only mode facts without altering any frozen V1 state or intent.
    from .operation_execution_mode import task_execution_mode
    mode=bundle.get('executionMode') or task_execution_mode(task,verify_current=False)
    result={k:mode.get(k) for k in ('executionMode','executionModeLabel','quantityApplicable','modeSourceHash','referenceWorkload')}
    if getattr(task,'execution_mode','QUANTIFIED')!='QUANTIFIED':
        result.update(executionConfirmation=bundle.get('executionConfirmation'),
            executionConfirmationVersion=1 if bundle.get('executionConfirmation') else 0)
    return result


from .operation_resource_read_scope import scoped_execution_read


@scoped_execution_read
def read_operation_completions(*,user,task_id=None,readback_query=None,_verified_stage=None,work_order_id=None):
    register_actions(); actor,runtime_scope=receipt._actor(user)
    if task_id is not None and (type(task_id) is not int or task_id<=0): _fail('OPERATION_COMPLETION_QUERY_INVALID','任务身份须为正整数。',400)
    employee,_,evidence,_=_person(actor)
    if not receipt._authority(actor,READ_PERMISSION,None,actor.pk)[0]:
        _fail('OPERATION_COMPLETION_READ_DENIED','当前账号缺少独立工序完工查看权限及本公司范围。',403)
    orders=receipt._rows(actor,runtime_scope).values_list('pk',flat=True)
    records=Task.objects.filter(company_id=actor.company_id,status='dispatched',work_order_id__in=orders).select_related(
        'work_order__production_plan','source_operation__effective_step','source_operation__work_center__workshop','workshop','work_center')
    if task_id is not None:records=records.filter(pk=task_id)
    if work_order_id is not None:records=records.filter(work_order_id=work_order_id)
    tasks=[];read_failures=[]
    for task in records.order_by('work_order_id','source_operation__sequence'):
        owned=bool(employee and starts._owned(actor,task,employee))
        review=_role(actor,APPROVE_ACTION,task)
        from .operation_completion_v3_authority import (reviewer_can_read, decorate_task_row,
            validated_bundle,completion_read_stage,_CompletionReadStage)
        from .operation_completion_generation_models import OperationCompletionGeneration
        has_generation=OperationCompletionGeneration.objects.filter(task_id=task.pk).exists()
        has_projection=BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=task.pk).exists() or has_generation
        if not owned and not ((review['ready'] or reviewer_can_read(actor,task)) and has_projection): continue
        from .services import PlanningBusinessError
        from pde.order_routing_execution_service import ArrangementError
        before_count=len(tasks)
        try:
            bundle=validated_bundle(task,actor);stage=None
            if task.execution_mode=='QUANTIFIED':
                if _verified_stage is not None and task_id==task.pk:
                    if not isinstance(_verified_stage,_CompletionReadStage):
                        _fail('COMPLETION_READ_STAGE_INVALID','只接受本服务当前正式读取阶段，不接收外部已验证标识。')
                    stage=_verified_stage;stage.validate(task,actor,bundle)
                else:stage=completion_read_stage(task,actor,bundle)
                completion=stage.current
            else:completion=_history(task,bundle)
            q_request=_qualification(actor,task,bundle,completion,'request'); q_review=_qualification(actor,task,bundle,completion,'approve')
            qualification=q_request if owned else q_review
            progress=_record_progress(task,completion,qualification)
            overall={'completionProven':bool(completion and completion['statusCode']=='completed'),
                'statusCode':completion['statusCode'] if completion else 'unrequested',
                'statusLabel':completion['statusLabel'] if completion else LABELS['unrequested'],
                'source':'verified_completion_projection'}
            actions={key:{**action_contract(key,task.pk),'enabled':q['ready'],
                'disabledReason':'' if q['ready'] else '；'.join(q['missingItems'])} for key,q in (('request',q_request),('approve',q_review))}
            quantity=bundle['quantity'] or {'workloadQuantity':task.workload_quantity,'reportedQuantity':None,'remainingQuantity':None,'quantityPrecision':None}
            if getattr(task,'execution_mode','QUANTIFIED')!='QUANTIFIED':
                from .operation_execution_confirmation_service import quantity_facts
                quantity=quantity_facts()
            operation=task.source_snapshot['operation']
            tasks.append({'id':task.pk,'taskId':task.pk,'no':task.no,'usagePurpose':task.work_order.usage_purpose,'workOrderId':task.work_order_id,'workOrderNo':task.work_order.no,
                'operationName':operation['operationName'],'frozenSequence':operation['sequence'],'workshopName':task.workshop.name,
                'workCenterName':task.work_center.name if task.source_snapshot.get('executionResourceSelectionRef') else operation['workCenterName'],
                **{key:quantity[key] for key in ('workloadQuantity','reportedQuantity','remainingQuantity','quantityPrecision')},
                'workloadUomLabel':task.workload_uom.name if task.execution_mode=='QUANTIFIED' and task.workload_uom_id else None,
                **_mode_display(task,actor,bundle),'version':task.version,'sourceSnapshotHash':task.source_snapshot_hash,
                'assignmentHash':task.assignment_hash,'startId':bundle['start'].pk if bundle['start'] else None,
                'startSnapshotHash':bundle['startHash'],'reportSetHash':bundle['reportSetHash'],
                'completionProjectionVersion':completion['projectionVersion'] if completion else 0,
                'completionStatusCode':completion['statusCode'] if completion else 'unrequested',
                'completionStatusLabel':completion['statusLabel'] if completion else LABELS['unrequested'],
                'completionProven':bool(completion and completion['statusCode']=='completed'),
                'formalFactsComplete':bundle['snapshot'] is not None and (getattr(task,'execution_mode','QUANTIFIED')=='QUANTIFIED'
                    or bundle.get('executionConfirmation') is not None),
                'downstreamReleased':False,'completionFact':completion,'availableActions':actions,
                'recordProgress':progress,'overallCompletion':overall,
                **({'resourceSource':deepcopy(bundle['source']['resourceSource']),
                    'effectiveWorkshop':deepcopy(bundle['source']['effectiveWorkshop']),
                    'effectiveReceptionAuthority':bundle['source']['effectiveReceptionAuthority']}
                    if task.source_snapshot.get('executionResourceSelectionRef') else {}),
                'qualification':qualification,'requestQualification':q_request,'reviewQualification':q_review,
                'stateMachineConsistent':True})
            decorate_task_row(actor,task,bundle,completion,tasks[-1],stage=stage)
            tasks[-1]['dateFacts'] = task_date_facts(task, bundle['start'], completion=completion)
        except (PlanningBusinessError,ArrangementError) as error:
            # A selected detail keeps its original failure. An unselected
            # directory records the failing object explicitly and never lets it
            # conceal independently verified objects from another work order.
            if task_id is not None:
                _fail(error.code,getattr(error,'message',str(error)),getattr(error,'http_status',409))
            del tasks[before_count:]
            read_failures.append({'taskId':task.pk,'taskNo':task.no,'workOrderNo':task.work_order.no,
                'operationName':task.source_snapshot.get('operation',{}).get('operationName'),
                'factLoadStatus':'read_failed','errorCode':error.code,'errorMessage':getattr(error,'message',str(error)),
                'quantity':None,'completionStatus':None,'writeEligibilityIncluded':False})
    selected=next((row for row in tasks if row['taskId']==task_id),None) if task_id else None
    if work_order_id is not None and not tasks:_fail('OPERATION_COMPLETION_TASK_NOT_VISIBLE','所选测试工单不在当前本人或独审读取范围。',403)
    if task_id and selected is None: _fail('OPERATION_COMPLETION_TASK_NOT_VISIBLE','所选任务不属于本公司本人执行或合法生产跟单审核范围。',403)
    empty={'ready':False,'statusLabel':'请选择正式任务','missingItems':['请选择正式任务。']}
    from .operation_completion_v3_authority import readback_result
    return {'contractVersion':CONTRACT,'moduleCode':MODULE,'businessProcessCode':BUSINESS_PROCESS,'factSource':'server',
        'usagePurpose':selected['usagePurpose'] if selected else ('MIXED_AUTHORIZED' if any(x['usagePurpose']=='PRODUCTION_USE' for x in tasks) else 'TEST_BUSINESS'),
        'purposeLabel':'正式生产用途；独立开发样本不代表企业放行' if selected and selected['usagePurpose']=='PRODUCTION_USE' else '本人授权任务含正式来源，逐单核验；独立环境不代表企业放行' if any(x['usagePurpose']=='PRODUCTION_USE' for x in tasks) else '隔离测试用途；测试代办与独立审核按真实账号留痕，不表示用户本人点击',
        'taskReadFailures':read_failures,'authorizedTaskCount':len(tasks)+len(read_failures),'fullyVerified':not read_failures,'currentStateSource':'server','companyId':actor.company_id,'currentActorEvidence':evidence,'tasks':tasks,'selectedTask':selected,
        'qualification':selected['qualification'] if selected else empty,
        'availableActions':selected['availableActions'] if selected else {key:{**action_contract(key),'enabled':False,'disabledReason':'请选择正式任务。'} for key in ('request','approve')},
        'statusLabel':'工序完工申请及生产跟单审核事实已读取','completionEffectiveOnlyAfterReview':True,
        'downstreamReleaseSupported':False,'businessWriteCount':0,'auditWriteCount':0,
        'readbackResult':readback_result(actor,task_id,readback_query)}

def _payload(payload,key):
    expected=set(EXPECTED)|{'reason','idempotencyKey'}
    if key=='approve': expected|={'expectedWorkflowVersion','expectedApprovalTaskVersion'}
    if not isinstance(payload,dict) or set(payload)!=expected:
        _fail('OPERATION_COMPLETION_PAYLOAD_INVALID','完工意图必须完整包含当前来源、状态版本、原因及防重复标识。',400)
    for field in ('expectedVersion','expectedStartId','expectedCompletionVersion')+ (('expectedWorkflowVersion','expectedApprovalTaskVersion') if key=='approve' else ()):
        if type(payload[field]) is not int or payload[field]<(0 if field=='expectedCompletionVersion' else 1):
            _fail('OPERATION_COMPLETION_EXPECTATION_INVALID','完工意图的版本或开工身份无效，请重新读取。',400)
    for field in ('expectedSourceSnapshotHash','expectedAssignmentHash','expectedStartSnapshotHash','expectedReportSetHash'):
        if not isinstance(payload[field],str) or not re.fullmatch('[0-9a-f]{64}',payload[field]):
            _fail('OPERATION_COMPLETION_EXPECTATION_INVALID','来源、开工或报工集合哈希无效，请重新读取。',400)
    if not isinstance(payload['reason'],str) or not 2<=len(payload['reason'].strip())<=240:
        _fail('OPERATION_COMPLETION_REASON_REQUIRED','请填写2至240字的完工申请或审核原因。',400)
    if not isinstance(payload['idempotencyKey'],str) or not 1<=len(payload['idempotencyKey'])<=120:
        _fail('OPERATION_COMPLETION_IDEMPOTENCY_REQUIRED','本次操作缺少有效防重复标识。',400)

def _event(user,task,target,target_type,before,after,action,reason,q):
    after={**after,'contractVersion':CONTRACT}
    audit=record_audit(user=user,action_code=action,target=target,target_type=target_type,target_no=task.no,
        before=before,after=after,authorization=q['authorization'],reason=reason)
    node={'processCode':PROCESS,'businessProcessCode':BUSINESS_PROCESS,
        'nodeCode':REQUEST_NODE if action==REQUEST_ACTION else REVIEW_NODE,
        'processId':q['definitionId'],'nodeId':q['nodeId']}
    audit.before_snapshot['workflowNode']=node
    audit.after_snapshot['workflowNode']=node
    audit.save(update_fields=['before_snapshot','after_snapshot'])
    return audit, f'OrganizationOperatingAuditRecord:{audit.pk}'

def _shared_initial(model,name,actor,task,action,q,reason,**fields):
    obj=create_business_object_with_initial_state(model=model,initial_state='pending',**fields)
    _,reference=_event(actor,task,obj,name,{'status':''},{'status':'pending','completionTaskId':task.pk},action,reason,q)
    record_projected_business_transition(object_type=name,object_id=obj.pk,source_state='',target_state='pending',
        action_code=action,operator=actor,reason=reason,audit_reference=reference,allowed_transitions={('','pending')})
    return obj

def _shared_approve(obj,name,actor,task,q,reason):
    _,reference=_event(actor,task,obj,name,{'status':'pending'},{'status':'approved','completionTaskId':task.pk},APPROVE_ACTION,reason,q)
    obj.completed_at=timezone.now();obj.save(update_fields=['completed_at'])
    transition_business_object(business_object=obj,object_type=name,source_state='pending',target_state='approved',
        action_code=APPROVE_ACTION,operator=actor,reason=reason,audit_reference=reference,
        allowed_transitions={('pending','approved')},updated_at_field=None)

def _writes(key=None):
    return {'businessWriteCount':1 if key else 0,'auditWriteCount':3 if key else 0,
        'stateTransitionWriteCount':3 if key else 0,'completionRequestCreatedCount':1 if key=='request' else 0,
        'completionCreatedCount':1 if key=='approve' else 0,'approvalDecisionCreatedCount':1 if key=='approve' else 0,
        'actualReportCount':0,'actualStartCount':0,'taskUpdatedCount':0,'workOrderUpdatedCount':0,
        'operationSourceUpdatedCount':0,'resourceOccupancyReleasedCount':0,'scheduleUpdatedCount':0,
        'inventoryUpdatedCount':0,'downstreamReleasedCount':0}

def execute_completion(*,user,task_id,payload,action='request'):
    if action=='withdrawReplace' or isinstance(payload,dict) and payload.get('completionProtocolVersion')==3:
        from .operation_completion_v3_authority import execute
        return execute(user=user,task_id=task_id,payload=payload,action=action)
    if action not in ('request','approve'): _fail('OPERATION_COMPLETION_ACTION_INVALID','未注册的工序完工动作。',400)
    _payload(payload,action)
    if type(task_id) is not int or task_id<=0: _fail('OPERATION_COMPLETION_QUERY_INVALID','任务身份须为正整数。',400)
    actor,_=receipt._actor(user); code=REQUEST_ACTION if action=='request' else APPROVE_ACTION
    try:
        from .operation_completion_v3_authority import completion_writer_context
        with completion_writer_context(actor,task_id):
            formal._writer_lock(actor)
            task=Task.objects.select_for_update().filter(pk=task_id,company_id=actor.company_id).select_related(
                'work_order__production_plan','source_operation__effective_step','source_operation__work_center__workshop','workshop','work_center').first()
            if not task: _fail('OPERATION_COMPLETION_TASK_NOT_VISIBLE','未找到本公司正式任务。',403)
            from .operation_completion_v3_authority import ensure_legacy_write_allowed
            ensure_legacy_write_allowed(task,actor)
            facts=read_operation_completions(user=actor,task_id=task_id); selected=facts['selectedTask']
            from .operation_completion_v3_authority import validated_bundle
            bundle=validated_bundle(task,actor); completion=_history(task,bundle)
            intent_hash=_binding_hash(actor.pk,code,task_id,payload)
            old=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=code,idempotency_key=payload['idempotencyKey']).first()
            q=_qualification(actor,task,bundle,completion,action)
            # Exact committed intent may be read again without replaying it;
            # current role/scope and source must still be valid.
            if old:
                role=_role(actor,code,task)
                matched_key=completion and (completion['requestKeyHash'] if action=='request' else completion['approvalRequestKeyHash'])
                if (old.status!='COMMITTED' or old.entity_type!=OBJECT or old.target_entity_id!=str(task_id)
                        or old.request_hash!=intent_hash or not matched_key
                        or matched_key!=sha256(payload['idempotencyKey'].encode()).hexdigest()):
                    _fail('OPERATION_COMPLETION_IDEMPOTENCY_CONFLICT','防重复标识已绑定其他人员或操作意图。')
                if not role['ready'] or not bundle['ready']: _fail('OPERATION_COMPLETION_NOT_READY','当前责任、权限或来源已变化，不能确认旧意图。',403)
                return facts,{**_writes(),'quantityAccountCASWriteCount':1}
            expected={'expectedVersion':task.version,'expectedSourceSnapshotHash':task.source_snapshot_hash,
                'expectedAssignmentHash':task.assignment_hash,'expectedStartId':selected['startId'],
                'expectedStartSnapshotHash':selected['startSnapshotHash'],'expectedReportSetHash':selected['reportSetHash'],
                'expectedCompletionVersion':selected['completionProjectionVersion']}
            if action=='approve' and completion:
                expected.update(expectedWorkflowVersion=completion['workflowVersion'],expectedApprovalTaskVersion=completion['approvalTaskVersion'])
            if any(payload[key]!=value for key,value in expected.items()):
                _fail('OPERATION_COMPLETION_SOURCE_OR_VERSION_CHANGED','任务、开工、报工集合或审批版本已变化，请只读重新核对。')
            if not q['ready']: _fail('OPERATION_COMPLETION_NOT_READY','；'.join(q['missingItems']),403)
            reason=payload['reason'].strip(); key_hash=sha256(payload['idempotencyKey'].encode()).hexdigest()
            if action=='request':
                workflow=_shared_initial(WorkflowInstance,'WorkflowInstance',actor,task,code,q,reason,
                    instance_no=f'MES-OC-{task.company_id}-{task.pk}',process_definition_id=q['definitionId'],
                    document_type=OBJECT,document_id=task.pk,current_step=1,total_steps=1,version=1)
                approval=_shared_initial(ApprovalTask,'ApprovalTask',actor,task,code,q,reason,
                    task_no=f'MES-OC-REVIEW-{task.company_id}-{task.pk}',workflow_instance=workflow,step_no=1,
                    required_role_code=q['reviewerRoleCode'],minimum_approvals=1,allow_parallel=False,version=1)
                decision=None; target='pending_review'; previous=''
            else:
                workflow=WorkflowInstance.objects.select_for_update().get(pk=completion['workflowInstanceId'])
                approval=ApprovalTask.objects.select_for_update().get(pk=completion['approvalTaskId'])
                decision=ApprovalDecision.objects.create(task=approval,decision_sequence=1,actor=actor,decision='approved',
                    comment=reason,action_id=code,idempotency_key=payload['idempotencyKey'],decision_hash=intent_hash)
                _shared_approve(approval,'ApprovalTask',actor,task,q,reason)
                _shared_approve(workflow,'WorkflowInstance',actor,task,q,reason)
                target='completed';previous='pending_review'
            state={'contractVersion':CONTRACT,'status':target,'taskId':task_id,'companyId':actor.company_id,
                'sourceSnapshot':deepcopy(bundle['snapshot']),'sourceSnapshotHash':bundle['snapshotHash'],
                'actorEvidence':deepcopy(q['currentActorEvidence']),'definitionId':workflow.process_definition_id,
                'definitionHash':q['definitionHash'],
                'workflowInstanceId':workflow.pk,'approvalTaskId':approval.pk,
                'approvalDecisionId':decision.pk if decision else None,'reviewerRoleCode':approval.required_role_code,
                'intentKeyHash':key_hash,'intentHash':intent_hash,
                'intentPayload':{key:value for key,value in payload.items() if key!='idempotencyKey'}}
            _,reference=_event(actor,task,task,OBJECT,{'status':previous},state,code,reason,q)
            record_projected_business_transition(object_type=OBJECT,object_id=task_id,source_state=previous,target_state=target,
                action_code=code,operator=actor,reason=reason,audit_reference=reference,workflow_instance=workflow,
                allowed_transitions={('','pending_review'),('pending_review','completed')})
            identity=ExternalIdentity.objects.create(organization_id=actor.company_id,source_system='MES_OPERATION_COMPLETION',
                source_type='INTERNAL',source_object_type=code,external_id=key_hash,target_entity_type=OBJECT,
                target_entity_id=str(task_id),mapping_status='MATCH',source_fingerprint=intent_hash,
                audit_metadata={'contractVersion':CONTRACT,'downstreamReleased':False})
            MasterDataWriteRequest.objects.create(organization_id=actor.company_id,action_code=code,entity_type=OBJECT,
                idempotency_key=payload['idempotencyKey'],request_hash=intent_hash,source_identity=identity,status='COMMITTED',
                target_entity_id=str(task_id),result={'taskId':task_id,'workflowInstanceId':workflow.pk,
                    'approvalTaskId':approval.pk,'completed':action=='approve'},audit_metadata={'actorId':actor.pk,'contractVersion':CONTRACT})
            return read_operation_completions(user=actor,task_id=task_id),{**_writes(action),'quantityAccountCASWriteCount':1}
    except IntegrityError:
        _fail('OPERATION_COMPLETION_CONCURRENT_CONFLICT','当前任务已存在并发完工或审核意图，请只读重新读取，不自动重试。')


DIRECTORY_CONTRACT='PCE-OPERATION-COMPLETION-DIRECTORY-V1'

@scoped_execution_read
def read_operation_completion_directory(*,user,work_order_id=None):
    """Verified display projection, never an application/approval authority.

    The native chain and shared persisted history are verified before projecting;
    no full action form, quantity-account display or per-row detail DTO is built.
    """
    register_actions();actor,runtime_scope=receipt._actor(user)
    employee,_,evidence,_=_person(actor)
    if not receipt._authority(actor,READ_PERMISSION,None,actor.pk)[0]:
        _fail('OPERATION_COMPLETION_READ_DENIED','当前账号缺少独立工序完工查看权限及本公司范围。',403)
    orders=receipt._rows(actor,runtime_scope).values_list('pk',flat=True)
    records=Task.objects.filter(company_id=actor.company_id,status='dispatched',work_order_id__in=orders).select_related(
        'work_order__production_plan','source_operation__effective_step','source_operation__work_center__workshop',
        'workshop','work_center','workload_uom')
    if work_order_id is not None:records=records.filter(work_order_id=work_order_id)
    from .operation_completion_v3_authority import reviewer_can_read,validated_bundle,completion_read_stage
    from .operation_completion_shared_lifecycle import task_shared_workflow_lifecycle
    from .operation_completion_generation_models import OperationCompletionGeneration
    tasks=[];authorized=[]
    for task in records.order_by('work_order_id','source_operation__sequence'):
        owned=bool(employee and starts._owned(actor,task,employee))
        review=_role(actor,APPROVE_ACTION,task)
        has_generation=OperationCompletionGeneration.objects.filter(task_id=task.pk).exists()
        has_projection=BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=task.pk).exists() or has_generation
        if not owned and not ((review['ready'] or reviewer_can_read(actor,task)) and has_projection):continue
        authorized.append(task)
    from .mes_evidence_graph import prepare_tasks
    prepare_tasks(authorized)
    for task in authorized:
        bundle=validated_bundle(task,actor);stage=None
        if task.execution_mode=='QUANTIFIED':
            stage=completion_read_stage(task,actor,bundle);completion=stage.current
        else:completion=_history(task,bundle)
        # This remains a verifier of orphan/missing workflow, audit and closure
        # facts. Its detail presentation is not returned as a directory fact.
        task_shared_workflow_lifecycle(actor=actor,task=task,bundle=bundle,completion=completion,stage=stage)
        quantity=bundle['quantity'] or {'workloadQuantity':task.workload_quantity,'reportedQuantity':None,'remainingQuantity':None,'quantityPrecision':None}
        if task.execution_mode!='QUANTIFIED':
            from .operation_execution_confirmation_service import quantity_facts
            quantity=quantity_facts()
        operation=task.source_snapshot['operation']
        progress=_record_progress(task,completion,{'admissionMissingItems':[]})
        status=completion['statusCode'] if completion else 'unrequested'
        label=completion['statusLabel'] if completion else LABELS['unrequested']
        row={'id':task.pk,'taskId':task.pk,'no':task.no,'usagePurpose':task.work_order.usage_purpose,'workOrderId':task.work_order_id,'workOrderNo':task.work_order.no,
            'operationName':operation['operationName'],'frozenSequence':operation['sequence'],'workshopName':task.workshop.name,
            'workCenterName':task.work_center.name if task.source_snapshot.get('executionResourceSelectionRef') else operation['workCenterName'],
            **{key:quantity[key] for key in ('workloadQuantity','reportedQuantity','remainingQuantity','quantityPrecision')},
            'workloadUomLabel':task.workload_uom.name if task.execution_mode=='QUANTIFIED' and task.workload_uom_id else None,
            **{k:v for k,v in _mode_display(task,actor,bundle).items() if k not in ('executionConfirmation','executionConfirmationVersion')},
            'version':task.version,'sourceSnapshotHash':task.source_snapshot_hash,'assignmentHash':task.assignment_hash,
            'completionProjectionVersion':completion['projectionVersion'] if completion else 0,
            'completionStatusCode':status,'completionStatusLabel':label,
            'completionProven':bool(completion and status=='completed'),
            'formalFactsComplete':bundle['snapshot'] is not None and (task.execution_mode=='QUANTIFIED' or bundle.get('executionConfirmation') is not None),
            'recordProgress':{key:progress[key] for key in ('recordId','submitted','reviewed','submissionLabel','reviewLabel')},
            'reviewerLabel':completion.get('reviewerLabel') if completion else None,
            'overallCompletion':{'completionProven':bool(completion and status=='completed'),'statusCode':status,'statusLabel':label,'source':'verified_completion_projection'},
            'viewQualification':{'allowed':True,'actorId':actor.pk,'companyId':actor.company_id,'taskId':task.pk,'scope':'NATIVE_COMPLETION_READER','writeEligibilityIncluded':False}}
        if stage:stage.validate(task,actor,bundle)
        tasks.append(row)
    if work_order_id is not None and not tasks:_fail('OPERATION_COMPLETION_TASK_NOT_VISIBLE','所选测试工单不在当前本人或独审读取范围。',403)
    return {'contractVersion':DIRECTORY_CONTRACT,'moduleCode':MODULE,'businessProcessCode':BUSINESS_PROCESS,
        'factSource':'server','currentStateSource':'server','usagePurpose':'MIXED_AUTHORIZED' if any(x['usagePurpose']=='PRODUCTION_USE' for x in tasks) else 'TEST_BUSINESS',
        'purposeLabel':'本人授权任务含正式来源，逐单核验；独立环境不代表企业放行' if any(x['usagePurpose']=='PRODUCTION_USE' for x in tasks) else '隔离测试用途；测试代办与独立审核按真实账号留痕，不表示用户本人点击',
        'companyId':actor.company_id,'currentActorEvidence':evidence,'tasks':tasks,'selectedTask':None,
        'statusLabel':'已核实职责范围内工序目录；办理资格请查看任务完整详情',
        'writeEligibilityIncluded':False,'businessWriteCount':0,'auditWriteCount':0}
