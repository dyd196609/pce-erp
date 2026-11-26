"""Physical delivery follows actual execution, independent of workshop borders."""
from .operation_handover_core import fail, _hash
from .operation_execution_mode import resolve_operation_execution_mode

def has_development_assumption(value):
    if isinstance(value, dict):
        if value.get('code') == 'FORMAL-CHAIN-DEV': return True
        return any(has_development_assumption(v) for v in value.values())
    if isinstance(value, list): return any(has_development_assumption(v) for v in value)
    return False

def movement_kind(mode):
    code = mode.get('executionMode')
    if code == 'NOT_APPLICABLE': return 'SKIP'
    if not mode.get('ready'): fail('HANDOVER_ROUTE_MODE_PENDING', '工序适用性或数量模式待核实，不得跳过。')
    if code == 'NON_QUANTIFIED_REQUIRED': return 'COMPLETE_WITHOUT_PHYSICAL'
    if code == 'QUANTIFIED': return 'PHYSICAL'
    fail('HANDOVER_ROUTE_MODE_PENDING', '工序数量模式缺失，不得推断不执行。')

def validate_production_target(actor, task, target):
    if target.work_order_id != task.work_order_id or target.work_order.company_id != actor.company_id:
        fail('HANDOVER_TARGET_OPERATION_MISMATCH', '目标须属于同公司同工单。')
    from .operation_predecessor_authority import _graph, _completion, verification_context
    from .operation_route_facts import read_operation_route
    route_facts = read_operation_route(task, actor)
    reconciled = {r['sequence']: r for r in route_facts['operations']}
    graph, issue = _graph(task)
    if issue: fail('HANDOVER_ROUTE_UNPROVEN', issue)
    # Validate the entire successor graph too; _graph validates ancestors of task.
    operations = list(task.work_order.operations.select_related('effective_step').order_by('sequence'))
    by_sequence = {op.sequence:op for op in operations}
    for op in operations:
        refs = op.source_snapshot.get('predecessorSequences')
        if (_hash(op.source_snapshot) != op.snapshot_hash or not isinstance(refs,list)
            or refs != op.effective_step.predecessor_sequences
            or any(type(n) is not int or n not in by_sequence for n in refs)):
            fail('HANDOVER_ROUTE_UNPROVEN', '冻结路线依赖缺失或已变化。')
    source_mode = resolve_operation_execution_mode(task.source_operation, actor=actor)
    if movement_kind(source_mode) != 'PHYSICAL':
        fail('HANDOVER_SOURCE_NOT_QUANTIFIED', '非量经过不生成实物交接，须保留执行完工事实。')
    reached = set(); active = set()
    def walk(sequence, context):
        if sequence in active: fail('HANDOVER_ROUTE_CYCLE', '正式后序存在循环。')
        active.add(sequence)
        for op in operations:
            if sequence not in op.source_snapshot['predecessorSequences']: continue
            app = op.source_snapshot.get('frozenStep',{}).get('applicability',{})
            if has_development_assumption(app):
                formal = reconciled[op.sequence]
                if route_facts['sourceStatus'] != 'VALID' or formal['formalApplicability'] == 'PENDING':
                    fail('HANDOVER_FORMAL_APPLICABILITY_UNPROVEN',
                        '正式标准产能来源读取或关联未通过，不能将技术缺项当作不执行。')
                if formal['formalApplicability'] == 'REQUIRED' and app.get('result') == 'NOT_APPLICABLE':
                    # The incoming physical quantity belongs to the verified
                    # source batch. Missing destination planning configuration
                    # must not turn a required operation into a skipped/NQ node.
                    # A new handover freezes its formal correction proof; this
                    # never rewrites the old operation or grants production.
                    current_mode = resolve_operation_execution_mode(op, actor=actor)
                    if current_mode['executionMode'] == 'NON_QUANTIFIED_REQUIRED' and current_mode['ready']:
                        proof = _completion(op, task, context)
                        if proof.get('proofType') != 'FORMAL_NON_QUANTITATIVE_COMPLETION':
                            fail('HANDOVER_INTERMEDIATE_PROOF_REQUIRED', '必经非量工序缺少正式完成证明。')
                        walk(op.sequence, context)
                    else:
                        reached.add(op.pk)
                    continue
            mode = resolve_operation_execution_mode(op, actor=actor)
            kind = movement_kind(mode)
            if kind == 'PHYSICAL': reached.add(op.pk)
            else:
                # Reuse complete native exemption/nonquantity proofs. Missing
                # tasks, reports or quantities never imply exemption/completion.
                proof = _completion(op, task, context)
                expected = 'FORMAL_EXEMPTION' if kind == 'SKIP' else 'FORMAL_NON_QUANTITATIVE_COMPLETION'
                if proof.get('proofType') != expected:
                    fail('HANDOVER_INTERMEDIATE_PROOF_REQUIRED', '中间工序缺少正式免执行或非量完工证明。')
                walk(op.sequence, context)
        active.remove(sequence)
    with verification_context() as context: walk(task.source_operation.sequence, context)
    if target.pk not in reached:
        fail('HANDOVER_ILLEGAL_SUCCESSOR', '目标不是沿有效路线承接的下一定量执行工序，禁止跳序。')
    return True


def reconciled_physical_target(actor, task, operation, center):
    """Logistics-only resource proof over the approved matrix, not dispatch.

    No target plan/output quantity is invented. The normal handover service
    still proves exact source slices, sender/receiver duties and actual receipt.
    """
    app = operation.source_snapshot.get('frozenStep', {}).get('applicability', {})
    if not has_development_assumption(app) or app.get('result') != 'NOT_APPLICABLE':
        return None
    from pde.capacity_route_applicability import read_route_capacity
    from .work_order_execution_service import _verify
    from .operation_exemption_authority import _load_scope
    _verify(operation.work_order)
    if (_hash(operation.source_snapshot) != operation.snapshot_hash
            or operation.work_order_id != task.work_order_id
            or operation.work_order.company_id != actor.company_id):
        fail('HANDOVER_TARGET_OPERATION_MISMATCH', '目标来源必须属于同公司同工单。')
    _, context, engineering_version, _ = _load_scope(operation, actor)
    applicability = context[6]
    if (applicability.get('result') != 'REQUIRED'
            or applicability.get('formalApplicabilityValidated') is not True):
        fail('HANDOVER_CORRECTED_TARGET_UNPROVEN', '目标精确工单、工程基线及正式适用来源未通过核实。')
    source = read_route_capacity(operation.effective_routing_version, company_id=actor.company_id)
    formal = source['steps'].get(operation.effective_step_id, {})
    department = center.workshop.department if center.workshop_id and center.workshop.department_id else center.department
    if (source['status'] != 'VALID' or formal.get('result') != 'REQUIRED'
            or center.pk not in formal.get('workCenterIds', []) or not center.is_active
            or center.company_id != actor.company_id or not center.workshop_id
            or center.workshop.company_id != actor.company_id or not center.workshop.is_active
            or (department is not None and (not department.is_active or department.company_id != actor.company_id))):
        fail('HANDOVER_CORRECTED_TARGET_UNPROVEN', '当前正式工艺及实际接收工作中心未获完整证明。')
    validate_production_target(actor, task, operation)
    snapshot = {'operationId': operation.pk, 'operationSnapshotHash': operation.snapshot_hash,
        'routingVersionId': operation.effective_routing_version_id, 'stepId': operation.effective_step_id,
        'workCenterId': center.pk, 'workshopId': center.workshop_id,
        'resourceSelectionReference': None, 'preciseReceiptReference': None,
        'logisticsOnly': True,
        'applicabilityCorrectionProof': {'contractVersion': 'PCE-PHYSICAL-RECEIPT-APPLICABILITY-V1',
            'companyId': actor.company_id, 'workOrderId': task.work_order_id,
            'originalOperationSnapshotHash': operation.snapshot_hash,
            'currentEngineeringVersion': engineering_version,
            'formalSource': source['sourceProof'], 'formalStep': formal,
            'originalDecisionUnchanged': True, 'grantsDispatchOrStart': False},
        'targetPlanSummary': {'operationId': operation.pk, 'operationSnapshotHash': operation.snapshot_hash,
            'sourceHash': operation.snapshot_hash, 'routingVersionId': operation.effective_routing_version_id,
            'executionMode': 'PENDING', 'executionModeLabel': '目标生产计量资格另核；按交出批次实物接收',
            'modeSourceHash': None, 'quantityApplicable': None, 'quantity': None, 'uom': None,
            'referenceWorkload': None,
            'statusLabel': '目标计划投产量未知；实物数量及单位来自本单交出批次，不从产能推造'}}
    return {'workCenter': center, 'workshop': center.workshop,
        'context': {'logisticsOnly': True}, 'snapshot': snapshot}


def require_actual_receipt(row, target):
    from .operation_handover_models import OperationCustodyEvent as Event, OperationHandover
    leg = row.data.get('receivedLegId')
    if leg and OperationHandover.objects.filter(pk=leg,company_id=target.company_id,
            target_operation_id=target.source_operation_id).exists():
        return
    for receipt in Event.objects.filter(task_id=row.root.task_id,company_id=target.company_id,
            kind='RANGE_RECEIVED',data__targetTaskId=target.pk):
        from .operation_handover_core import verify_record
        verify_record(receipt)
        release = Event.objects.filter(pk=receipt.data.get('releaseEventId'),task_id=row.root.task_id,
            company_id=target.company_id,kind='RANGE_RELEASE').first()
        if not release: continue
        verify_record(release)
        for part in release.data.get('rangeRelease',{}).get('ranges',[]):
            if (part.get('rootId')==row.root_id and int(part['startAtom'])<=int(row.start_atom)
                and int(part['endAtom'])>=int(row.end_atom)):
                return
    fail('HANDOVER_ACTUAL_RECEIPT_REQUIRED', '定量来源须有本目标准确批次范围的实际收讫证明，不能仅以范围释放代替。')


def historical_route_review(row, task):
    from .custody_dependency_reads import read_rows

    operations = read_rows('historical_route_operations', (task.company_id, task.work_order_id),
        lambda: tuple(task.work_order.operations.all()))
    graph = {op.sequence:op for op in operations}
    versions = {}
    target = next((op for op in operations if op.pk==row.target_operation_id),None)
    pending=[];conflicts=[];stack=[target.sequence] if target else [];seen=set();sources={}
    while stack:
        seq=stack.pop()
        if seq in seen or seq==task.source_operation.sequence: continue
        seen.add(seq);op=graph.get(seq)
        if op is None: continue
        app=op.source_snapshot.get('frozenStep',{}).get('applicability',{})
        if app.get('result')=='NOT_APPLICABLE' and has_development_assumption(app):
            from pde.capacity_route_applicability import read_route_capacity
            version_id = op.effective_routing_version_id
            if version_id not in versions:
                versions[version_id] = read_rows('historical_route_version', (task.company_id, version_id),
                    lambda: op.effective_routing_version)
            version = versions[version_id]
            if version.pk not in sources:sources[version.pk]=read_route_capacity(version,company_id=task.company_id)
            source=sources[version.pk];formal=source['steps'].get(op.effective_step_id,{})
            item={'sequence':seq,'operationName':op.source_snapshot.get('operationName'),
                'snapshotHash':op.snapshot_hash,'formalSource':formal}
            if source['status']!='VALID' or formal.get('result')=='PENDING':
                pending.append({**item,'issue':'正式来源读取或关联待核实；不能据技术缺项跳过'})
            elif formal.get('result')=='REQUIRED':
                conflicts.append({**item,'issue':'正式标准产能已证明执行，原冻结开发假设将其排除'})
        stack.extend(op.source_snapshot.get('predecessorSequences',[]))
    correction = row.source_snapshot.get('target', {}).get('applicabilityCorrectionProof', {})
    corrected = bool(target and correction.get('contractVersion') == 'PCE-PHYSICAL-RECEIPT-APPLICABILITY-V1'
        and correction.get('companyId') == task.company_id and correction.get('workOrderId') == task.work_order_id
        and correction.get('originalOperationSnapshotHash') == target.snapshot_hash
        and correction.get('formalSource', {}).get('status') == 'VALID'
        and correction.get('formalStep', {}).get('result') == 'REQUIRED')
    if corrected:
        conflicts = [item for item in conflicts if item['sequence'] != target.sequence]
    return {'routeReviewStatus':'历史目标与正式工艺来源冲突；原历史保留' if conflicts else '正式来源待核实；原历史保留' if pending else '已按正式来源更正物流承接；原冻结记录保留' if corrected else '未发现开发假设免执行冲突',
        'routeApplicabilityPending':sorted(pending,key=lambda x:x['sequence']),
        'routeSourceConflicts':sorted(conflicts,key=lambda x:x['sequence']),
        'routeCorrectionApplied': corrected,
        'originalHistoryUnchanged':True}
