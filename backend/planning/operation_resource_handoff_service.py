

# Native formal continuation: individually restored symbols; existing proofs preserved.
from copy import deepcopy

from hashlib import sha256

import re

from types import SimpleNamespace

from django.db import IntegrityError, transaction

from masterdata.models import ExternalIdentity, MasterDataWriteRequest

from pde.models import WorkCenter

from system.models import OrganizationOperatingAuditRecord, Process, User, Workshop

from workflow_runtime.action_permissions import ActionPermissionValidator

from workflow_runtime.models import BusinessStateTransition

from workflow_runtime.state_transitions import record_projected_business_transition

from . import formal_scheduling_service as formal

from . import work_order_workshop_receipt_service as receipt

from .work_order_execution_service import _fail, _hash

from .work_order_models import ProductionWorkOrder, ProductionWorkOrderOperation as Operation

from .work_order_workshop_receipt_models import ProductionWorkOrderWorkshopReceipt as Receipt

from .workshop_task_models import ProductionWorkshopTask as Task

from .services import PlanningBusinessError, record_audit

from .operation_resource_handoff_contract import (ACTION, CONTRACT, GET_PATH, MODULE,
    NAMESPACE, OBJECT, PROCESS, REQUIRED_PERMISSION, RESPONSIBILITY, WORKFLOW_NODE,
    action_contract, register_action)

EXPECTED = ('expectedWorkOrderVersion', 'expectedWorkOrderSnapshotHash',
    'expectedOperationSnapshotHash', 'expectedOriginalReceiptHash',
    'expectedOriginalMembershipHash', 'expectedCurrentSnapshotHash', 'expectedHandoffVersion')

def _history_error():
    _fail('RESOURCE_HANDOFF_HISTORY_UNPROVEN', '工序归属承接的冻结来源、状态、审计或防重复证明不一致。')

def _intent_hash(actor_id, operation_id, payload):
    body = {key: value for key, value in payload.items() if key != 'idempotencyKey'}
    body['reason'] = body['reason'].strip()
    body['requestKeyHash'] = sha256(payload['idempotencyKey'].encode()).hexdigest()
    return _hash({'actorId': actor_id, 'actionCode': ACTION, 'operationId': operation_id, 'payload': body})

def _payload(payload):
    if not isinstance(payload, dict) or set(payload) != set(EXPECTED) | {'reason', 'idempotencyKey'}:
        _fail('RESOURCE_HANDOFF_PAYLOAD_INVALID', '归属承接意图须完整引用工单、工序、原接收、当前归属及版本。', 400)
    for key in ('expectedWorkOrderVersion', 'expectedHandoffVersion'):
        if type(payload[key]) is not int or payload[key] < 0:
            _fail('RESOURCE_HANDOFF_VERSION_INVALID', '归属承接版本无效，请重新读取正式事实。', 400)
    for key in set(EXPECTED) - {'expectedWorkOrderVersion', 'expectedHandoffVersion'}:
        if not isinstance(payload[key], str) or not re.fullmatch('[0-9a-f]{64}', payload[key]):
            _fail('RESOURCE_HANDOFF_HASH_INVALID', '归属承接缺少本次正式读取的完整来源哈希。', 400)
    if not isinstance(payload['reason'], str) or not 2 <= len(payload['reason'].strip()) <= 240:
        _fail('RESOURCE_HANDOFF_REASON_REQUIRED', '请填写2至240字的归属承接原因。', 400)
    if not isinstance(payload['idempotencyKey'], str) or not 1 <= len(payload['idempotencyKey']) <= 120:
        _fail('RESOURCE_HANDOFF_IDEMPOTENCY_REQUIRED', '归属承接缺少有效防重复标识。', 400)

def _history(operation, membership):
    """Verify every immutable event without reinterpreting it using new masters."""
    events = list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=operation.pk)
        .order_by('version', 'pk'))
    if not events:
        if MasterDataWriteRequest.objects.filter(organization_id=operation.work_order.company_id,
                entity_type=OBJECT, target_entity_id=str(operation.pk)).exists():
            _history_error()
        return []
    if not isinstance(membership, dict) or not membership:
        _history_error()
    previous_status, previous_ref, previous_hash = '', None, None
    previous_workshop = membership.get('originalWorkshopId')
    result = []
    for version, event in enumerate(events, 1):
        match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', event.audit_reference or '')
        audit = OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
        before = audit.before_snapshot if audit and isinstance(audit.before_snapshot, dict) else {}
        after = audit.after_snapshot if audit and isinstance(audit.after_snapshot, dict) else {}
        state, authorization, node = after.get('state'), after.get('authorization'), after.get('workflowNode')
        if (not audit or event.version != version or event.action_code != ACTION
                or event.source_state != previous_status or event.workflow_instance_id is not None
                or audit.target_type != OBJECT or audit.target_id != operation.pk
                or audit.organization_id != operation.work_order.company_id
                or audit.actor_id != event.operator_id or audit.action_code != ACTION or audit.reason != event.reason
                or not isinstance(before.get('state'), dict) or before['state'].get('status') != previous_status
                or not isinstance(state, dict) or not isinstance(authorization, dict) or not isinstance(node, dict)):
            _history_error()
        snapshot, qualification, actor = state.get('snapshot'), state.get('qualification'), state.get('actorEvidence')
        if (not isinstance(snapshot, dict) or not isinstance(qualification, dict) or not isinstance(actor, dict)
                or not isinstance(snapshot.get('currentSnapshot'), dict)
                or not isinstance(snapshot['currentSnapshot'].get('workshop'), dict)
                or not isinstance(state.get('intentPayload'), dict)
                or state.get('contractVersion') != CONTRACT or state.get('projectionVersion') != version
                or state.get('status') != event.target_state
                or state.get('proofHash') != _hash(snapshot)
                or event.target_state != 'effective:' + _hash({'version': version, 'proofHash': state['proofHash']})
                or snapshot.get('companyId') != operation.work_order.company_id
                or snapshot.get('workOrderId') != operation.work_order_id or snapshot.get('operationId') != operation.pk
                or snapshot.get('originalMembership') != membership
                or snapshot.get('originalMembershipHash') != _hash(membership)
                or snapshot.get('currentSnapshotHash') != _hash(snapshot['currentSnapshot'])
                or not isinstance(snapshot.get('currentVersionFacts'), dict)
                or snapshot['currentVersionFacts'].get('ready') is not True
                or qualification.get('currentVersionFacts') != snapshot['currentVersionFacts']
                or snapshot['currentSnapshot'].get('companyId') != operation.work_order.company_id
                or snapshot['currentSnapshot'].get('workOrderId') != operation.work_order_id
                or snapshot['currentSnapshot'].get('operationId') != operation.pk
                or snapshot.get('previousTransitionRef') != previous_ref
                or snapshot.get('previousProofHash') != previous_hash
                or snapshot.get('fromWorkshopId') != previous_workshop
                or snapshot.get('toWorkshopId') != snapshot['currentSnapshot'].get('workshop', {}).get('id')
                or not isinstance(snapshot.get('toWorkshopId'), int)
                or actor.get('userId') != event.operator_id or actor.get('companyId') != operation.work_order.company_id
                or actor.get('workshopId') != snapshot['toWorkshopId']
                or qualification.get('qualificationProven') is not True
                or qualification.get('currentActorEvidence') != actor
                or actor.get('explicitAuthorityProven') is not True
                or not isinstance(actor.get('matchedAuthorityEvidence'), list) or not actor['matchedAuthorityEvidence']
                or not isinstance(qualification.get('checks'), list) or not qualification['checks']
                or any(not isinstance(check, dict) or check.get('eligible') is not True for check in qualification['checks'])
                or authorization.get('allowed') is not True
                or not isinstance(authorization.get('permissionCodes'), list)
                or not any(code in (REQUIRED_PERMISSION, '*') for code in authorization['permissionCodes'])
                or not isinstance(authorization.get('roleCodes'), list) or not authorization['roleCodes']
                or node.get('processCode') != PROCESS or node.get('nodeCode') != WORKFLOW_NODE
                or node.get('authorityActionCode') != REQUIRED_PERMISSION
                or node.get('responsibilityCode') != RESPONSIBILITY
                or any(type(node.get(key)) is not int or node[key] <= 0 for key in ('processId', 'nodeId'))
                or node.get('processId') != qualification.get('definitionId')
                or node.get('nodeId') != qualification.get('nodeId')
                or before.get('workflowNode') != node):
            _history_error()
        matches = list(MasterDataWriteRequest.objects.filter(organization_id=operation.work_order.company_id,
            action_code=ACTION, entity_type=OBJECT, target_entity_id=str(operation.pk),
            request_hash=state.get('requestHash')).select_related('source_identity'))
        ledger = matches[0] if len(matches) == 1 else None
        identity = ledger.source_identity if ledger else None
        expected_result = {'operationId': operation.pk, 'transitionId': event.pk,
            'projectionVersion': version, 'proofHash': state['proofHash']}
        if (not ledger or ledger.status != 'COMMITTED' or not identity
                or state.get('requestKeyHash') != sha256(ledger.idempotency_key.encode()).hexdigest()
                or identity.organization_id != operation.work_order.company_id
                or identity.source_system != NAMESPACE or identity.source_type != 'INTERNAL'
                or identity.source_object_type != ACTION or identity.external_id != state['requestKeyHash']
                or identity.target_entity_type != OBJECT or identity.target_entity_id != str(operation.pk)
                or identity.mapping_status != 'MATCH' or identity.source_fingerprint != ledger.request_hash
                or ledger.result != expected_result
                or ledger.audit_metadata != {'actorId': event.operator_id, 'contractVersion': CONTRACT}
                or identity.audit_metadata != {'contractVersion': CONTRACT, 'originalReceiptPreserved': True}):
            _history_error()
        intent = {**state['intentPayload'], 'idempotencyKey': ledger.idempotency_key}
        try:
            _payload(intent)
        except PlanningBusinessError:
            _history_error()
        if (_intent_hash(event.operator_id, operation.pk, intent) != ledger.request_hash
                or intent['expectedWorkOrderVersion'] != membership.get('workOrderVersion')
                or intent['expectedWorkOrderSnapshotHash'] != membership.get('workOrderSnapshotHash')
                or intent['expectedOperationSnapshotHash'] != membership.get('operationSnapshotHash')
                or intent['expectedOriginalReceiptHash'] != membership.get('receiptSnapshotHash')
                or intent['expectedOriginalMembershipHash'] != _hash(membership)
                or intent['expectedCurrentSnapshotHash'] != snapshot['currentSnapshotHash']
                or intent['expectedHandoffVersion'] != version - 1 or intent['reason'].strip() != event.reason):
            _history_error()
        zone = operation.work_order.source_snapshot['sourceSchedule']['timezone']
        proof = {'id': event.pk, 'version': version, 'projectionVersion': version,
            'ref': f'BusinessStateTransition:{event.pk}', 'proofHash': state['proofHash'],
            'snapshot': deepcopy(snapshot), 'currentSnapshotHash': snapshot['currentSnapshotHash'],
            'companyId': operation.work_order.company_id, 'workOrderId': operation.work_order_id,
            'operationId': operation.pk, 'originalReceiptId': membership['receiptId'],
            'originalReceiptHash': membership['receiptSnapshotHash'],
            'fromWorkshopId': snapshot['fromWorkshopId'], 'toWorkshopId': snapshot['toWorkshopId'],
            'actorId': event.operator_id, 'actorLabel': actor.get('employeeName') or actor.get('username'),
            'currentActorEvidence': deepcopy(actor), 'requestKeyHash': state['requestKeyHash'],
            'requestHash': state['requestHash'], 'reason': event.reason,
            'auditReference': event.audit_reference, 'confirmedAt': event.timestamp.isoformat(),
            'timeLabel': formal._label(event.timestamp, zone), 'effectiveAt': event.timestamp.isoformat(),
            'statusCode': event.target_state, 'statusLabel': '归属承接已生效',
            'sourceState': event.source_state, 'targetState': event.target_state,
            'stateMachineConsistent': True}
        result.append(proof)
        previous_status, previous_ref, previous_hash = event.target_state, proof['ref'], proof['proofHash']
        previous_workshop = snapshot['toWorkshopId']
    return result

class _OperationFacts:
    def __init__(self, operation):
        self.operation = operation

    def read(self, module_code, object_ids):
        valid = module_code == MODULE and object_ids == [str(self.operation.pk)]
        return {'found': valid, 'objectIds': object_ids if valid else [],
            'statuses': [self.operation.work_order.status] if valid else [],
            'legalEntityIds': [str(self.operation.work_order.company_id)] if valid else [],
            'currentStateSource': 'server', 'reason': '' if valid else 'object_scope_mismatch'}

def _base(operation, actor=None, context=None):
    from .operation_resource_source import read_operation_resource
    base = context if context is not None else read_operation_resource(operation, actor=actor, include_handoff=False)
    if actor is not None:
        from .operation_start_service import _current_version_facts
        adapter = SimpleNamespace(source_operation=operation, work_order=operation.work_order,
            company_id=operation.work_order.company_id,
            work_center_id=base.get('workCenter').pk if base.get('workCenter') else operation.work_center_id,
            workshop_id=base['workshop'].pk if base['workshop'] else None,
            source_snapshot={'operation': operation.source_snapshot})
        base['currentVersionFacts'] = _current_version_facts(adapter, actor)
    return base

def _accepted_source_ready(base):
    facts = base['facts']
    admission=facts.get('currentAllocationAdmission')
    return bool(facts.get('summaryOnly') is not True and facts.get('allocationAdmissionIncluded') is not False
        and isinstance(admission,dict) and admission.get('ready') is True
        and facts.get('effectiveReceiptProven', facts.get('originalReceiptProven')) is True
        and all(facts.get(key) is True for key in ('currentResourceValid', 'masterDataConsistent', 'sourceUnchanged'))
        and base['currentVersionFacts']['ready'])

def _qualification(actor, operation, base, history):
    facts, workshop = base['facts'], base['workshop']
    ready_source = _accepted_source_ready(base)
    if workshop:
        q, _ = receipt._qualification(actor, operation.work_order, workshop, source_ok=ready_source)
    else:
        q = {'ready': False, 'qualificationProven': False, 'issues': [], 'checks': [],
            'currentActorEvidence': receipt._employees(actor)[4], 'nativeDecision': {}}
    # The inherited group-receipt check says a source "changed" for every
    # missing receipt too. Explain the actual effective source here instead.
    issues = [item['statusLabel'] for item in q.get('issues', [])
        if item.get('code') != 'WORKSHOP_RECEIPT_RELEASEDSOURCE']
    if not ready_source:
        missing_source = facts.get('blockingReasons') or ['本工序有效接收、当前资源或正式来源尚未完整证实，不能办理归属承接。']
        issues.extend(message for message in missing_source if message not in issues)
    current_version = base['currentVersionFacts']
    q['checks'].append({'checkCode': 'currentEngineeringVersion', 'complete': True,
        'eligible': current_version['ready'], 'statusLabel': current_version['statusLabel']})
    if not current_version['ready']:
        issues.extend(item['statusLabel'] for item in current_version['issues'])
    current_proof = history[-1] if history and history[-1]['currentSnapshotHash'] == _hash(base['currentSnapshot']) else None
    change_required = bool(facts.get('changeRequired') or (history and not current_proof))
    if not change_required:
        issues.append(facts.get('handoffStatusLabel') or '本工序当前归属与原冻结接收一致，无需归属承接。')
    if current_proof:
        issues.append('本次资源归属已有正式承接证明，不重复承接。')
    task = Task.objects.filter(source_operation_id=operation.pk).first()
    task_block = bool(task and not current_proof and change_required)
    if task_block:
        issues.append('本工序已有冻结执行任务，当前承接不迁移或重建任务；须先取得正式任务归属变更能力。')
    decision = ActionPermissionValidator(fact_provider=_OperationFacts(operation)).evaluate(user=actor,
        module_code=MODULE, action_code=ACTION, object_ids=[operation.pk], selection_count=1,
        requested_legal_entity_id=str(operation.work_order.company_id))
    if not decision['granted']:
        issues.append('当前账号未通过工序归属承接正式动作权限校验。')
    q = deepcopy(q)
    ready = bool(ready_source and current_version['ready'] and not issues
        and all(check.get('eligible') is True for check in q['checks']))
    q.update(ready=ready, qualificationProven=ready, missingItems=list(dict.fromkeys(issues)),
        currentVersionFacts=deepcopy(current_version),
        taskBlock=task_block, existingTaskId=task.pk if task else None,
        statusLabel='可以确认本工序归属承接' if ready else '；'.join(dict.fromkeys(issues)))
    return q

def _row(operation, actor, context=None):
    base = _base(operation, actor, context)
    membership = base.get('effectiveMembership') or base['originalMembership']
    history = _history(operation, membership)
    facts = deepcopy(base['facts'])
    proof = history[-1] if history and history[-1]['currentSnapshotHash'] == _hash(base['currentSnapshot']) else None
    change_required = bool(facts.get('changeRequired') or (history and not proof))
    q = _qualification(actor, operation, base, history)
    current_workshop = base['workshop']
    original_workshop = base['facts']['originalReceiptWorkshop']
    # A precise receipt's membership is its new acceptance baseline, never
    # evidence that the original order/group had a frozen workshop.
    accepted_workshop = None
    if membership and base['receipt']:
        accepted_workshop={'id':membership['originalWorkshopId'],'name':base['receipt'].source_snapshot['workshopName']}
    status = ('归属承接已生效' if proof else '当前资源归属已变化，等待新的正式承接' if history
        else '资源归属已变化，待正式承接' if change_required else facts['handoffStatusLabel'])
    if (base.get('workCenter') or operation.work_center) and facts.get('masterDataConsistent') is not True:
        status = '正式工序与当前工作中心归属不一致，须先校正主数据'
    action = {**action_contract(operation.pk), 'displayName': '已承接' if proof else '确认本工序归属承接',
        'enabled': q['ready'], 'disabledReason': '' if q['ready'] else '；'.join(q['missingItems'])}
    frozen = receipt._receipt(base['receipt']) if base['receipt'] else None
    return {**facts, 'id': operation.pk, 'operationId': operation.pk, 'sequence': operation.sequence,
        'workOrderId': operation.work_order_id, 'workOrderNo': operation.work_order.no,
        'operationName': operation.operation.name,
        'workCenterName':base['workCenter'].name if base.get('workCenter') else operation.work_center.name if operation.work_center else None,
        'formalProcessWorkshopId': operation.operation.workshop_id,
        'formalProcessWorkshopName': operation.operation.workshop.name if operation.operation.workshop_id else None,
        'currentWorkshopId': current_workshop.pk if current_workshop else None,
        'currentWorkshopDepartmentId': current_workshop.department_id if current_workshop else None,
        'masterDataMaintenancePath': '/foundation/master-data/operations?view=maintain',
        'masterDataMaintenancePathLabel': '企业基础资料 → 制造资源 → 工序 → 维护 → 编辑 → 所属车间 / 生产区域 → 保存并回读',
        'changeRequired': change_required,
        'handoffApplicable': bool(membership and change_required),
        'handoffStatusLabel': status,
        'originalWorkshopName': original_workshop['name'] if original_workshop else None,
        'receiptBaselineWorkshopName': accepted_workshop['name'] if accepted_workshop else None,
        'receiptBaselineLabel': '逐工序精确接收的资源归属基线' if facts.get('preciseReceiptProven') else '原冻结车间接收的归属基线',
        'currentWorkshopName': current_workshop.name if current_workshop else None,
        'effectiveWorkshopName': current_workshop.name if current_workshop and (proof or not change_required) else None,
        'statusLabel': status, 'sourceReady': bool(_accepted_source_ready(base) and (proof or not change_required)),
        'originalReceipt': frozen, 'originalFrozenReceipt': deepcopy(facts.get('originalReceipt')),
        'receiptAnchor': frozen, 'frozenReceiptId': membership.get('receiptId') if membership else None,
        'frozenReceiptHash': membership.get('receiptSnapshotHash') if membership else None,
        'originalMembershipHash': _hash(membership) if membership else None,
        'currentSnapshotHash': _hash(base['currentSnapshot']), 'currentResourceHash': _hash(base['currentSnapshot']),
        'operationSnapshotHash': operation.snapshot_hash, 'workOrderVersion': operation.work_order.version,
        'workOrderSnapshotHash': operation.work_order.snapshot_hash,
        'handoffVersion': len(history), 'projectionVersion': len(history),
        'currentVersionFacts': deepcopy(base['currentVersionFacts']),
        'resourceHandoff': proof, 'handoffFact': proof, 'statusTransitionHistory': history,
        'statusTransitionCount': len(history), 'stateMachineConsistent': True,
        'qualification': q, 'availableAction': action, 'availableActions': {'confirm': action},
        'blockingReasons': q['missingItems'], 'taskBlock': q['taskBlock'],
        'sourceBasisLabel': ('正式资源选择＋逐工序精确接收'+('＋本工序归属承接' if proof else '；新归属待承接' if change_required else ''))
            if facts.get('preciseReceiptProven') else '正式资源选择证明；尚待本工序精确接收，未扩大原冻结接收范围'
            if facts.get('resourceSelection') else
            '原冻结接收＋本工序正式归属承接' if proof else '原冻结接收；当前新归属尚未承接' if change_required else
            '原冻结接收' if membership else facts['currentResourceBasisLabel']+'；尚无本工序正式接收证明'}

def _read_resource_handoffs(*, user, work_order_id=None, operation_id=None, response_mode=None,locate_latest_own_action=False):
    from .workshop_reception_read_projection import response_mode as parse_mode,SELECTED_DETAIL,operation_directory_row
    from .workshop_reception_read_projection import (validate_locator_request,latest_own_action_candidate,
        verified_view_location,view_location_fields)
    response_mode=parse_mode(response_mode)
    validate_locator_request(locate_latest_own_action,response_mode)
    register_action()
    actor, scope = receipt._actor(user)
    for value in (work_order_id, operation_id):
        if value is not None and (type(value) is not int or value <= 0):
            _fail('RESOURCE_HANDOFF_QUERY_INVALID', '工单及工序身份须为正整数。', 400)
    orders = receipt._rows(actor, scope)
    if operation_id is not None and work_order_id is None:
        work_order_id = Operation.objects.filter(pk=operation_id,
            work_order_id__in=orders.values_list('pk', flat=True)).values_list('work_order_id', flat=True).first()
        if work_order_id is None:
            _fail('RESOURCE_HANDOFF_OPERATION_NOT_VISIBLE', '未找到当前公司范围内的工单工序。', 403)
    options, selected_order = [], None
    for order in orders:
        from .operation_resource_selection_service import selection_authority
        whole_readable=receipt._whole_readable(actor,order)
        centers = [] if response_mode==SELECTED_DETAIL and whole_readable else [
            selection_authority(item)[1] for item in order.operations.select_related('work_center__workshop')]
        visible = whole_readable or any(
            center and center.workshop and receipt._readable(actor, center.workshop, order) for center in centers)
        if not visible:
            continue
        options.append({'workOrderId': order.pk, 'workOrderNo': order.no, 'productionPlanId': order.production_plan_id})
        if order.pk == work_order_id:
            selected_order = order
    if work_order_id is not None and selected_order is None:
        _fail('RESOURCE_HANDOFF_ORDER_NOT_VISIBLE', '当前账号不能查看此公司及工单范围的归属承接。', 403)
    rows = [];directory=[];visible_contexts=[];candidate=None;suggestion=None
    location_requested=bool(locate_latest_own_action and operation_id is None)
    if selected_order:
        from .operation_resource_source import read_order_resources
        from .work_order_execution_service import _verify
        contexts=([(operation,None) for operation in _verify(selected_order)[0]]
            if response_mode==SELECTED_DETAIL else read_order_resources(selected_order,actor=actor,include_handoff=False))
        whole_readable=receipt._whole_readable(actor,selected_order)
        for operation, context in contexts:
            center=(context.get('workCenter') or operation.work_center) if context is not None else (
                selection_authority(operation)[1] if not whole_readable else None)
            if not whole_readable and not (
                    center and center.workshop and receipt._readable(actor, center.workshop, selected_order)):
                continue
            directory.append(operation_directory_row(operation))
            visible_contexts.append((operation,context))
        if location_requested:
            candidate=latest_own_action_candidate(actor,[operation for operation,context in visible_contexts])
            if candidate:operation_id=candidate[0].pk
        for operation,context in visible_contexts:
            if response_mode!=SELECTED_DETAIL or operation.pk==operation_id:
                rows.append(_row(operation, actor, context))
    selected = next((row for row in rows if row['operationId'] == operation_id), None) if operation_id else None
    if operation_id is not None and selected is None:
        _fail('RESOURCE_HANDOFF_OPERATION_NOT_VISIBLE', '所选工序不属于本工单及当前正式查看范围。', 403)
    if candidate:
        suggestion=verified_view_location(actor,candidate,selected)
    empty = {'ready': False, 'missingItems': ['请选择需核对归属的正式工单工序。'], 'statusLabel': '请选择正式工单工序'}
    disabled = {**action_contract(), 'enabled': False, 'disabledReason': empty['statusLabel']}
    return {'contractVersion': CONTRACT, 'moduleCode': MODULE, 'companyId': actor.company_id,
        **view_location_fields(location_requested,suggestion),
        'responseMode':response_mode,'operationOptions':directory if response_mode==SELECTED_DETAIL else None,
        'directoryResultCount':len(directory),'detailResultCount':len(rows),
        'currentActorEvidence': receipt._employees(actor)[4], 'currentStateSource': 'server', 'factSource': 'server',
        'workOrderId': work_order_id, 'workOrderOptions': options, 'operations': rows, 'selectedOperation': selected,
        'qualification': selected['qualification'] if selected else empty,
        'availableAction': selected['availableAction'] if selected else disabled,
        'availableActions': {'confirm': selected['availableAction'] if selected else disabled},
        'statusLabel': ('工序目录已读取，请选择工序读取当前归属、接收及资格事实' if selected_order else
            '请选择已下达工单；工序目录及详情尚未读取') if response_mode==SELECTED_DETAIL and selected is None else
            '工序资源归属及原冻结接收事实已读取' if selected_order else '请选择已下达工单',
        'businessWriteCount': 0, 'auditWriteCount': 0}

def read_resource_handoffs(*,user,work_order_id=None,operation_id=None,response_mode=None,locate_latest_own_action=False):
    from pde.operation_allocation_source_handoff_service import allocation_admission_context
    actor,_=receipt._actor(user)
    with allocation_admission_context(user=actor):
        return _read_resource_handoffs(user=actor,work_order_id=work_order_id,operation_id=operation_id,
            response_mode=response_mode,locate_latest_own_action=locate_latest_own_action)

def _writes(created=False):
    return {'businessWriteCount': 1 if created else 0, 'auditWriteCount': 1 if created else 0,
        'stateTransitionWriteCount': 1 if created else 0, 'resourceHandoffCreatedCount': 1 if created else 0,
        'idempotencyWriteCount': 2 if created else 0, 'taskUpdatedCount': 0, 'workOrderUpdatedCount': 0,
        'originalReceiptUpdatedCount': 0, 'operationSourceUpdatedCount': 0, 'masterDataUpdatedCount': 0,
        'actualStartCount': 0, 'actualReportCount': 0, 'completionCreatedCount': 0,
        'inventoryUpdatedCount': 0, 'scheduleUpdatedCount': 0, 'downstreamReleasedCount': 0}

def confirm_resource_handoff(*, user, operation_id, payload):
    _payload(payload)
    if type(operation_id) is not int or operation_id <= 0:
        _fail('RESOURCE_HANDOFF_QUERY_INVALID', '工单工序身份须为正整数。', 400)
    register_action()
    actor, runtime_scope = receipt._actor(user)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            order_ids = receipt._rows(actor, runtime_scope).values_list('pk', flat=True)
            operation = Operation.objects.select_for_update().filter(pk=operation_id, work_order_id__in=order_ids).select_related(
                'work_order__production_plan', 'work_center__workshop', 'operation', 'effective_step', 'root_step').first()
            if not operation:
                _fail('RESOURCE_HANDOFF_OPERATION_NOT_VISIBLE', '未找到当前公司范围内的工单工序。', 403)
            ProductionWorkOrder.objects.select_for_update().get(pk=operation.work_order_id)
            from .operation_resource_selection_service import selection_authority
            effective_center = selection_authority(operation)[1]
            if effective_center:
                WorkCenter.objects.select_for_update().get(pk=effective_center.pk)
                if effective_center.workshop_id:
                    Workshop.objects.select_for_update().get(pk=effective_center.workshop_id)
            Process.objects.select_for_update().get(pk=operation.operation_id)
            list(type(operation.root_step).objects.select_for_update().filter(
                pk__in={operation.root_step_id, operation.effective_step_id}).order_by('pk').values_list('pk', flat=True))
            list(type(operation.root_routing_version).objects.select_for_update().filter(
                pk__in={operation.root_routing_version_id, operation.effective_routing_version_id}).order_by('pk').values_list('pk', flat=True))
            # Re-read locked masters; the relation cache obtained before a lock
            # cannot serve as the current ownership CAS after waiting for it.
            operation = Operation.objects.select_related('work_order__production_plan', 'work_center__workshop',
                'operation', 'effective_step', 'root_step').get(pk=operation_id)
            if operation.work_center and operation.work_center.workshop_id:
                Workshop.objects.select_for_update().get(pk=operation.work_center.workshop_id)
                operation.work_center.workshop.refresh_from_db()
            base = _base(operation, actor)
            effective_center = base.get('workCenter') or operation.work_center
            if not (receipt._whole_readable(actor, operation.work_order) or (
                    effective_center and effective_center.workshop and
                    receipt._readable(actor, effective_center.workshop, operation.work_order))):
                _fail('RESOURCE_HANDOFF_OPERATION_NOT_VISIBLE', '当前账号没有此工序资源归属的正式查看范围。', 403)
            if base['receipt']:
                Receipt.objects.select_for_update().get(pk=base['receipt'].pk)
            membership = base.get('effectiveMembership') or base['originalMembership']
            history = _history(operation, membership)
            q = _qualification(actor, operation, base, history)
            request_hash = _intent_hash(actor.pk, operation_id, payload)
            old = MasterDataWriteRequest.objects.filter(organization_id=actor.company_id, action_code=ACTION,
                idempotency_key=payload['idempotencyKey']).first()
            current = history[-1] if history and history[-1]['currentSnapshotHash'] == _hash(base['currentSnapshot']) else None
            if old:
                proof = next((row for row in history if row['requestKeyHash'] == sha256(payload['idempotencyKey'].encode()).hexdigest()), None)
                if (old.status != 'COMMITTED' or old.entity_type != OBJECT or old.target_entity_id != str(operation_id)
                        or old.request_hash != request_hash or not proof or proof['actorId'] != actor.pk):
                    _fail('RESOURCE_HANDOFF_IDEMPOTENCY_CONFLICT', '防重复标识已绑定其他工序、人员或归属意图。')
                source_ok = _accepted_source_ready(base)
                role, _ = receipt._qualification(actor, operation.work_order, base['workshop'], source_ok=source_ok)
                if not role['ready'] or not current or current['id'] != proof['id']:
                    _fail('RESOURCE_HANDOFF_RESULT_CHANGED', '当前资源或责任已变化，旧意图不得重放，请只读核对。')
                return read_resource_handoffs(user=actor, work_order_id=operation.work_order_id, operation_id=operation_id), _writes()
            expected = {'expectedWorkOrderVersion': operation.work_order.version,
                'expectedWorkOrderSnapshotHash': operation.work_order.snapshot_hash,
                'expectedOperationSnapshotHash': operation.snapshot_hash,
                'expectedOriginalReceiptHash': membership.get('receiptSnapshotHash') if membership else None,
                'expectedOriginalMembershipHash': _hash(membership) if membership else None,
                'expectedCurrentSnapshotHash': _hash(base['currentSnapshot']), 'expectedHandoffVersion': len(history)}
            if any(payload[key] != value for key, value in expected.items()):
                _fail('RESOURCE_HANDOFF_SOURCE_OR_VERSION_CHANGED', '原接收、工序来源、资源归属或承接版本已变化，请只读重新核对。')
            if current:
                # A new transport key is not a new business ownership change.
                source_ok = _accepted_source_ready(base)
                if not receipt._qualification(actor, operation.work_order, base['workshop'], source_ok=source_ok)[0]['ready']:
                    _fail('RESOURCE_HANDOFF_NOT_READY', '当前账号未满足目标车间正式承接责任及范围。', 403)
                return read_resource_handoffs(user=actor, work_order_id=operation.work_order_id, operation_id=operation_id), _writes()
            if not q['ready']:
                _fail('RESOURCE_HANDOFF_NOT_READY', '；'.join(q['missingItems']), 403)
            reason = payload['reason'].strip()
            previous = history[-1] if history else None
            snapshot = {'companyId': actor.company_id, 'workOrderId': operation.work_order_id,
                'operationId': operation_id, 'originalMembership': deepcopy(membership),
                'originalMembershipHash': _hash(membership), 'currentSnapshot': deepcopy(base['currentSnapshot']),
                'currentSnapshotHash': _hash(base['currentSnapshot']),
                'currentVersionFacts': deepcopy(base['currentVersionFacts']),
                'fromWorkshopId': previous['toWorkshopId'] if previous else membership['originalWorkshopId'],
                'toWorkshopId': base['workshop'].pk,
                'previousTransitionRef': previous['ref'] if previous else None,
                'previousProofHash': previous['proofHash'] if previous else None}
            version, proof_hash = len(history) + 1, _hash(snapshot)
            target = 'effective:' + _hash({'version': version, 'proofHash': proof_hash})
            previous_status = previous['targetState'] if previous else ''
            state = {'contractVersion': CONTRACT, 'projectionVersion': version, 'status': target,
                'snapshot': snapshot, 'proofHash': proof_hash, 'qualification': deepcopy(q),
                'actorEvidence': deepcopy(q['currentActorEvidence']),
                'requestKeyHash': sha256(payload['idempotencyKey'].encode()).hexdigest(), 'requestHash': request_hash,
                'intentPayload': {key: value for key, value in payload.items() if key != 'idempotencyKey'}}
            audit = record_audit(user=actor, action_code=ACTION, target=operation, target_type=OBJECT,
                target_no=operation.work_order.no + ' / ' + operation.operation.name,
                before={'status': previous_status}, after=state, authorization=q['nativeDecision'], reason=reason)
            node = {'processCode': PROCESS, 'nodeCode': WORKFLOW_NODE, 'processId': q['definitionId'],
                'nodeId': q['nodeId'], 'authorityActionCode': REQUIRED_PERMISSION, 'responsibilityCode': RESPONSIBILITY}
            audit.before_snapshot['workflowNode'] = node
            audit.after_snapshot['workflowNode'] = node
            audit.save(update_fields=['before_snapshot', 'after_snapshot'])
            event = record_projected_business_transition(object_type=OBJECT, object_id=operation_id,
                source_state=previous_status, target_state=target, action_code=ACTION, operator=actor,
                reason=reason, audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
                allowed_transitions={(previous_status, target)})
            identity = ExternalIdentity.objects.create(organization_id=actor.company_id, source_system=NAMESPACE,
                source_type='INTERNAL', source_object_type=ACTION, external_id=state['requestKeyHash'],
                target_entity_type=OBJECT, target_entity_id=str(operation_id), mapping_status='MATCH',
                source_fingerprint=request_hash, audit_metadata={'contractVersion': CONTRACT, 'originalReceiptPreserved': True})
            MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=ACTION,
                entity_type=OBJECT, idempotency_key=payload['idempotencyKey'], request_hash=request_hash,
                source_identity=identity, status='COMMITTED', target_entity_id=str(operation_id),
                result={'operationId': operation_id, 'transitionId': event.pk, 'projectionVersion': version, 'proofHash': proof_hash},
                audit_metadata={'actorId': actor.pk, 'contractVersion': CONTRACT})
            _history(operation, membership)
            return read_resource_handoffs(user=actor, work_order_id=operation.work_order_id, operation_id=operation_id), _writes(True)
    except IntegrityError:
        _fail('RESOURCE_HANDOFF_CONCURRENT_CONFLICT', '此工序存在并发归属承接，请只读重新核对结果，不自动重试。')


# Native formal continuation: individually restored symbols; existing proofs preserved.
def read_handoff_projection(operation, membership, currentSnapshot):
    history = _history(operation, membership)
    proof = history[-1] if history and history[-1]['currentSnapshotHash'] == _hash(currentSnapshot) else None
    return {'history': history, 'currentProof': proof, 'requiresNewHandoff': bool(history and not proof)}
