"""Read current formal route separately from immutable historic movements."""
from pde.capacity_route_applicability import read_route_capacity, has_development_assumption


def read_operation_route(task, actor, *, verified_headers=()):
    from .operation_execution_mode import resolve_operation_execution_mode
    operations = list(task.work_order.operations.select_related('effective_routing_version__routing',
        'effective_step__operation', 'workload_uom', 'work_center').order_by('sequence'))
    if actor.company_id != task.company_id:
        from .operation_handover_core import fail
        fail('HANDOVER_ROUTE_SCOPE_DENIED', '路线仅限本公司本工单。', 403)
    versions = {}
    from .workshop_task_models import ProductionWorkshopTask
    tasks = dict(ProductionWorkshopTask.objects.filter(work_order_id=task.work_order_id,
        company_id=task.company_id).values_list('source_operation_id', 'no'))
    rows = []
    from .operation_continuation_service import read_route_plan,is_receipt_mode
    continuation=read_route_plan(task.work_order,actor)
    for op in operations:
        version = op.effective_routing_version
        if version.pk not in versions:
            versions[version.pk] = read_route_capacity(version, company_id=task.company_id)
        source = versions[version.pk]
        formal = source['steps'].get(op.effective_step_id, {})
        frozen = op.source_snapshot.get('frozenStep', {}).get('applicability', {})
        technical = has_development_assumption(frozen)
        # Normal business decisions retain their authority. This reconciliation
        # replaces only explicitly marked development assumptions; a genuine
        # conflicting business decision remains a conflict, never an override.
        result = formal.get('result', 'PENDING')
        conflict = bool(result != 'PENDING' and frozen.get('result') not in (None, result))
        current = result if technical else ('PENDING' if conflict else frozen.get('result', result))
        mode = resolve_operation_execution_mode(op, actor=actor) if current == 'REQUIRED' else {}
        quantity_mode = mode.get('executionMode', 'PENDING') if current == 'REQUIRED' else None
        blockers = []
        if source['status'] != 'VALID': blockers.append(source['blockingReason'])
        if conflict and not continuation:
            blockers.append('正式来源已证明本工序'+('执行' if result == 'REQUIRED' else '不执行')+
                '，与原冻结'+('开发假设' if technical else '业务依据')+'不一致；须可追溯更正，原记录不覆盖。')
        if current == 'REQUIRED' and (quantity_mode == 'PENDING' or not mode.get('ready')):
            blockers.extend(mode.get('blockingReasons') or ['本工序投产数量/非量政策及冻结承接尚未完整核实，不能由产能值填造数量。'])
        logistics_reconciled = bool(technical and conflict and result == 'REQUIRED'
            and task.execution_mode == 'QUANTIFIED' and source['status'] == 'VALID'
            and formal.get('workCenterIds') and quantity_mode != 'NON_QUANTIFIED_REQUIRED'
            and (not continuation or quantity_mode=='QUANTIFIED'))
        input_plan=(mode.get('modeSourceProof') or {}).get('continuationInputPlan')
        reference=mode.get('referenceWorkload') or {}
        task_numbers=[tasks[op.pk]] if op.pk in tasks else []
        planning_label=('已有原生任务：'+'、'.join(task_numbers)+'；执行与完工仍按正式服务核验' if task_numbers
            else '正式不执行，无需投产任务' if current=='NOT_APPLICABLE'
            else '承接已登记，等待本工序真实实收形成投产引用' if continuation and quantity_mode=='QUANTIFIED' and not mode.get('ready')
            else '本工序投产来源已核实，可按原生职责办理任务' if mode.get('ready')
            else '投产依据待核实，不跳过本工序')
        rows.append({'operationId': op.pk, 'sequence': op.sequence, 'stepId': op.effective_step_id,
            'operationName': op.source_snapshot.get('operationName') or op.effective_step.operation.name,
            'predecessorSequences': op.source_snapshot.get('predecessorSequences'),
            'applicability': current, 'formalApplicability': result,
            'frozenApplicability': frozen.get('result'), 'developmentAssumption': technical,
            'sourceConflict': conflict, 'capacitySource': formal,
            'quantityMode': quantity_mode, 'quantityModeLabel': mode.get('executionModeLabel'),
            'physicalHandoverRequired': True if logistics_reconciled or quantity_mode == 'QUANTIFIED' else False if current == 'NOT_APPLICABLE' or quantity_mode == 'NON_QUANTIFIED_REQUIRED' else None,
            'logisticsReconciliationAvailable': logistics_reconciled,
            'handoverBlockingReasons': [] if logistics_reconciled else blockers,
            'executionBlockingReasons': blockers,
            'referenceQuantity': str(op.workload_quantity) if op.workload_quantity is not None else None,
            'referenceUomLabel': op.workload_uom.name if op.workload_uom_id else None,
            'taskNos': [tasks[op.pk]] if op.pk in tasks else [],
            'executionPlanLabel':task.work_order.no+' · 第'+str(op.sequence)+'工序承接' if continuation else None,
            'continuationRouteRef':continuation['ref'] if continuation else None,
            'productionInputPlanRef':input_plan['ref'] if input_plan else None,
            'productionInputQuantity':reference.get('quantity') if is_receipt_mode(mode) else None,
            'productionInputUomLabel':reference.get('uomLabel') if is_receipt_mode(mode) else None,
            'productionInputBatchNos':[r['businessNo'] for r in input_plan['snapshot']['input']['receipts']] if input_plan else [],
            'productionPlanningStatus':('TASK_EXISTS' if task_numbers else 'NOT_APPLICABLE' if current=='NOT_APPLICABLE'
                else 'AWAITING_ACTUAL_RECEIPT' if continuation and quantity_mode=='QUANTIFIED' and not mode.get('ready')
                else 'READY_FOR_TASK' if mode.get('ready') else 'SOURCE_UNPROVEN'),
            'productionPlanningStatusLabel':planning_label,
            'blockingReasons': blockers})
    successors = []; pending = []; seen = set()
    def walk(seq):
        if seq in seen: return
        seen.add(seq)
        for row in rows:
            if seq not in (row['predecessorSequences'] or []): continue
            if row['applicability'] == 'NOT_APPLICABLE': walk(row['sequence'])
            elif row['applicability'] == 'REQUIRED': successors.append(row)
            else: pending.append(row)
    walk(task.source_operation.sequence)
    # The next executed node may be non-quantitative. Its completion remains
    # mandatory even though the physical batch is received further downstream.
    # Keep these two route answers separate and reuse native completion proof.
    from .operation_predecessor_authority import _completion, verification_context
    from .services import PlanningBusinessError
    by_id = {op.pk: op for op in operations}
    physical = []
    def physical_walk(sequence, context, inherited=(), active=()):
        if sequence in active:
            return
        for row in rows:
            if sequence not in (row['predecessorSequences'] or []):
                continue
            if row['applicability'] == 'NOT_APPLICABLE':
                physical_walk(row['sequence'], context, inherited, (*active, sequence))
            elif row['applicability'] == 'REQUIRED' and row['quantityMode'] == 'NON_QUANTIFIED_REQUIRED':
                reasons = list(inherited)
                try:
                    proof = _completion(by_id[row['operationId']], task, context)
                    if proof.get('proofType') != 'FORMAL_NON_QUANTITATIVE_COMPLETION':
                        reasons.append(row['operationName']+'须先取得正式非量完工证明。')
                except PlanningBusinessError as error:
                    reasons.append(row['operationName']+'须先完成：'+error.message)
                physical_walk(row['sequence'], context, reasons, (*active, sequence))
            elif row['physicalHandoverRequired'] is True:
                candidate = dict(row)
                candidate['handoverBlockingReasons'] = list(dict.fromkeys([*inherited, *row['handoverBlockingReasons']]))
                candidate['handoverReady'] = not candidate['handoverBlockingReasons']
                physical.append(candidate)
    with verification_context() as context:
        physical_walk(task.source_operation.sequence, context)
    blocking = [reason for row in successors+pending for reason in row['handoverBlockingReasons']]
    blocking.extend(reason for row in physical for reason in row['handoverBlockingReasons'])
    for row in physical:
        row['quantitySourceLabel'] = '正式实物交接批次；按实际收讫数量、原单位及范围承接投产，不等同于目标产出量'
        row['receivedInputBatches'] = [{'handoverId': h['id'], 'businessNo': h.get('businessNo') or h['no'],
            'receivedQuantity': h['correctedMatchedReceiveQuantity'], 'uomLabel': h['uomLabel'],
            'currentHeldQuantity': h['currentTargetHeldQuantity'],
            'statusLabel': h['receiptStateLabel'], 'originalUnitPreserved': True}
            for h in verified_headers if h['targetOperationId'] == row['operationId']
                and h['workOrderId'] == task.work_order_id and h['correctedMatchedReceiveQuantity'] != '0']
    return {'contractVersion': 'PCE-CURRENT-OPERATION-ROUTE-V1', 'workOrderNo': task.work_order.no,
        'continuationPlan':({'businessLabel':task.work_order.no+' · 正式承接方案1','ref':continuation['ref'],
            'proofHash':continuation['proofHash'],'originalWorkOrderSnapshotHash':task.work_order.snapshot_hash,
            'statusLabel':'正式承接方案已登记；原冻结与已完成历史保留，缺失任务按真实实收投产来源衔接',
            'originalHistoryPreserved':True,'automaticDispatch':False,'automaticStart':False} if continuation else None),
        'sourceTaskNo': task.no, 'sourceOperationSequence': task.source_operation.sequence,
        'productTypeCodes': sorted({s['productTypeCode'] for s in versions.values() if s.get('productTypeCode')}),
        'sourceStatus': 'VALID' if all(s['status'] == 'VALID' for s in versions.values()) else 'PENDING',
        'sources': list(versions.values()), 'operations': rows, 'nextExecutionOperations': successors,
        'physicalHandoverTargets': physical,
        'quantitySourceLabel': '投产数量来源：正式实物交接的实际收讫批次；计划参考、实际产出及标准产能分别表达',
        'handoverTargetStatusLabel': '按交出批次实物接收；目标生产执行资格另行核实' if physical else '正式交接目标尚不可办理；核对正式来源',
        'blockingReasons': list(dict.fromkeys(blocking)),
        'unresolvedSuccessors': pending, 'historicalRecordsUnchanged': True,
        'businessWriteCount': 0, 'auditWriteCount': 0}
