"""Current physical resource and append-only custody proof authority."""
from pde.routing_read_context import routing_read_phase
from copy import deepcopy
from decimal import Decimal
from .operation_handover_core import (fail, _hash, initialize, verify_record, number, text,add,offset_iso)
from .operation_handover_models import (OperationCustodyEvent, OperationCustodySlice,
    OperationHandoverAllocation, OperationInputAllocation)
from .operation_resource_read_scope import scoped_execution_read
from .custody_dependency_reads import task_events,task_inputs


def same_workshop_receipt_proven(row):
    """U is a workshop bucket, not proof that a range was never received.

    Only a native RECEIVE event covering this exact live leaf admits the
    same-workshop continuation. No status, holder or matching numeric ID alone
    is sufficient. The existing custody/record authorities remain mandatory.
    """
    if (row.status!='U' or row.holder_workshop_id!=row.root.task.workshop_id
        or not row.data.get('receivedLegId') or not row.data.get('receivedEmployeeId')):
        return False
    from .operation_handover_models import OperationHandover
    header=OperationHandover.objects.filter(pk=row.data['receivedLegId'],company_id=row.company_id,
        data__taskId=row.root.task_id,target_work_center_id=row.holder_work_center_id,
        target_workshop_id=row.holder_workshop_id).first()
    if not header:return False
    allocation=header.allocations.filter(pk=row.data.get('legAllocationId'),root_id=row.root_id).first()
    if (not allocation or not header.sender_employee_id
        or not int(allocation.source_slice.start_atom)<=int(row.start_atom)<int(row.end_atom)<=int(allocation.source_slice.end_atom)):
        return False
    verify_handover(header);verify_record(row)
    for event in OperationCustodyEvent.objects.filter(handover=header,allocation=allocation,kind='RECEIVE').order_by('pk'):
        if (event.data.get('receiverEmployeeId')==row.data['receivedEmployeeId']
            and any(s.get('rootId')==row.root_id and s.get('data',{}).get('receivedLegId')==header.pk
                and int(s['startAtom'])<=int(row.start_atom)<int(row.end_atom)<=int(s['endAtom'])
                for s in event.data.get('afterSlices',[]))):
            verify_record(event)
            return True
    return False


def resource_context(operation, actor, *, include_plan=False):
    if operation.work_order.usage_purpose=='TEST_BUSINESS':
        from .workshop_task_models import ProductionWorkshopTask
        from .mes_test_source_bridge import _source
        task=ProductionWorkshopTask.objects.filter(source_operation=operation,company_id=actor.company_id).first()
        if not task:fail('HANDOVER_TEST_TASK_REQUIRED','测试资源必须关联同公司真实派工任务。',403)
        facts=_source(task,actor)
        if not facts['ready']:fail('HANDOVER_TEST_SOURCE_CHANGED',facts['statusLabel'])
        step=operation.effective_step;center=operation.work_center;workshop=center.workshop
        if _hash(operation.source_snapshot)!=operation.snapshot_hash or step.predecessor_sequences!=operation.source_snapshot.get('predecessorSequences'):fail('HANDOVER_TEST_SOURCE_DAMAGED','测试工序来源或前置关系已改变。')
        snapshot={'usagePurpose':'TEST_BUSINESS','operationId':operation.pk,'operationSnapshotHash':operation.snapshot_hash,'routingVersionId':operation.effective_routing_version_id,'stepId':operation.effective_step_id,'workCenterId':center.pk,'workshopId':workshop.pk,'resourceSelectionReference':None,'preciseReceiptReference':task.receipt.snapshot_hash}
        if include_plan:
            unit=operation.workload_uom;applicable=task.execution_mode=='QUANTIFIED'
            snapshot['targetPlanSummary']={'operationId':operation.pk,'operationSnapshotHash':operation.snapshot_hash,'sourceHash':operation.snapshot_hash,'routingVersionId':operation.effective_routing_version_id,'executionMode':task.execution_mode,'executionModeLabel':'定量执行' if applicable else '不统计数量','modeSourceHash':task.source_snapshot_hash,'quantityApplicable':applicable,'quantity':operation.workload_quantity if applicable else None,'uom':{'id':unit.pk,'code':unit.code,'name':unit.name,'decimalPlaces':unit.decimal_places} if applicable and unit else None,'referenceWorkload':None,'statusLabel':'测试目标自身来源计划；与来源交接量分列，不自动换算'}
        return {'workCenter':center,'workshop':workshop,'context':{'facts':facts},'snapshot':snapshot}
    from .operation_resource_source import read_operation_resource
    if _hash(operation.source_snapshot)!=operation.snapshot_hash:
        fail('HANDOVER_OPERATION_SOURCE_DAMAGED','工单工序冻结来源或Hash损坏。')
    context=read_operation_resource(operation,actor=actor)
    center=context.get('workCenter',operation.work_center);workshop=context.get('workshop')
    facts=context['facts'];step=operation.effective_step
    if (not center or not workshop or center.company_id!=operation.work_order.company_id
        or center.workshop_id!=workshop.pk or not center.is_active
        or not facts.get('currentResourceValid') or not facts.get('masterDataConsistent')
        or not step.is_active or step.routing_version_id!=operation.effective_routing_version_id
        or step.operation_id!=operation.operation_id
        or step.predecessor_sequences!=operation.source_snapshot.get('predecessorSequences')):
        fail('HANDOVER_RESOURCE_UNPROVEN','当前有效工作中心、车间或正式路线来源尚未核实。')
    snapshot={'operationId':operation.pk,'operationSnapshotHash':operation.snapshot_hash,
            'routingVersionId':operation.effective_routing_version_id,'stepId':operation.effective_step_id,
            'workCenterId':center.pk,'workshopId':workshop.pk,
            'resourceSelectionReference':facts.get('resourceSelectionReference'),
            'preciseReceiptReference':facts.get('preciseReceiptReference')}
    if include_plan:
        from .operation_execution_mode import resolve_operation_execution_mode
        mode=resolve_operation_execution_mode(operation,actor=actor)
        if not mode['ready']:fail('HANDOVER_TARGET_MODE_UNPROVEN','目标正式计量模式尚未核实：'+'；'.join(mode['blockingReasons']))
        applicable=mode['quantityApplicable'] is True;unit=operation.workload_uom
        quantity=operation.workload_quantity
        from .operation_continuation_service import is_receipt_mode
        if is_receipt_mode(mode):
            from masterdata.models import UnitOfMeasure
            quantity=mode['referenceWorkload']['quantity']
            unit=UnitOfMeasure.objects.get(pk=mode['referenceWorkload']['uomId'],company_id=actor.company_id,is_active=True)
        snapshot['targetPlanSummary']={'operationId':operation.pk,'operationSnapshotHash':operation.snapshot_hash,
            'sourceHash':operation.snapshot_hash,'routingVersionId':operation.effective_routing_version_id,
            'executionMode':mode['executionMode'],'executionModeLabel':mode['executionModeLabel'],
            'modeSourceHash':mode['modeSourceHash'],'quantityApplicable':mode['quantityApplicable'],
            'quantity':quantity if applicable else None,
            'uom':{'id':unit.pk,'code':unit.code,'name':unit.name,'decimalPlaces':unit.decimal_places} if applicable and unit else None,
            'referenceWorkload':mode['referenceWorkload'] if not applicable else None,
            'statusLabel':'目标自身正式计划；与本次移交数量分别列示，不换算' if applicable else '目标无投产统计量；工程参考不得作交接数量'}
    return {'workCenter':center,'workshop':workshop,'context':context,'snapshot':snapshot}


def slice_projection(row):
    return {'id':row.pk,'rootId':row.root_id,'quantity':row.quantity,'startAtom':row.start_atom,
        'endAtom':row.end_atom,'status':row.status,'version':row.version,
        'holderWorkshopId':row.holder_workshop_id,'holderWorkCenterId':row.holder_work_center_id,
        'reservedById':row.reserved_by_id,'frozen':row.frozen,'data':deepcopy(row.data)}


def header_projection(row):
    return {'id':row.pk,'status':row.status,'version':row.version,'data':deepcopy(row.data),
        'senderEmployeeId':row.sender_employee_id,'receiverEmployeeId':row.receiver_employee_id,
        'dispatchedAt':row.dispatched_at.isoformat() if row.dispatched_at else None}


def allocation_projection(row):
    return {'id':row.pk,'status':row.status,'version':row.version,'sourceSliceId':row.source_slice_id,
        'quantity':row.quantity,'data':deepcopy(row.data)}


def event_payload(row):
    return {'taskId':row.task_id,'handoverId':row.handover_id,'allocationId':row.allocation_id,
        'sliceId':row.slice_id,'kind':row.kind,'quantity':row.quantity,'debit':row.debit,
        'credit':row.credit,'occurredAt':row.occurred_at.isoformat(),
        'previousHash':row.previous_hash,'data':row.data}


def custody_event(*,actor,code,q,task,kind,quantity,debit,credit,stamp,intent_hash,
                  reason,slices=(),handover=None,allocation=None,data=None):
    previous=OperationCustodyEvent.objects.filter(task_id=task.pk).order_by('-pk').first()
    payload={'taskId':task.pk,'handoverId':handover.pk if handover else None,
        'allocationId':allocation.pk if allocation else None,'sliceId':slices[0].pk if slices else None,
        'kind':kind,'quantity':text(quantity),'debit':debit,'credit':credit,
        'occurredAt':stamp.isoformat(),'previousHash':previous.event_hash if previous else '',
        'data':{**deepcopy(data or {}),'afterSlices':[slice_projection(s) for s in slices],
            'afterHandovers':[header_projection(handover)] if handover else [],
            'afterAllocations':[allocation_projection(a) for a in handover.allocations.order_by('pk')] if handover else []}}
    row=initialize(OperationCustodyEvent,actor=actor,code=code,q=q,status='recorded',
        source=payload,intent_hash=intent_hash,reason=reason,task=task,handover=handover,
        allocation=allocation,slice=slices[0] if slices else None,kind=kind,quantity=text(quantity),
        debit=debit,credit=credit,occurred_at=stamp,previous_hash=payload['previousHash'],
        event_hash=_hash(payload),data=payload['data'])
    return row


@scoped_execution_read
def verify_task_custody(task):
    from .operation_predecessor_authority import verification_context,_proof_cache_epoch
    with verification_context() as context:
        epoch=_proof_cache_epoch(context)
        if epoch is None:return _verify_task_custody_uncached(task)
        if context.get('custodyVerificationEpoch')!=epoch:
            context['custodyVerificationEpoch']=epoch;context['custodyVerifiedTasks']={}
        key=(task.company_id,task.pk,task.version,task.source_snapshot_hash,task.assignment_hash,
            task.work_order_id,task.source_operation_id,task.work_center_id,task.workshop_id,
            task.execution_mode,task.workload_quantity,task.workload_uom_id)
        cache=context['custodyVerifiedTasks'];path=context.setdefault('custodyVerificationPath',set())
        if key in cache:return True
        if key in path:fail('CUSTODY_VERIFICATION_CYCLE','保管证明出现递归循环，不能放行。')
        path.add(key)
        try:
            result=_verify_task_custody_uncached(task)
            if _proof_cache_epoch(context)!=epoch:fail('CUSTODY_READ_CHANGED','保管证明读取期间发生变化，不能复用。')
            cache[key]=True;return result
        finally:path.remove(key)


@routing_read_phase("custody")
def _verify_task_custody_uncached(task):
    previous='';expected={};headers={};allocations={}
    events=task_events(task.pk)
    from pde.routing_read_context import _current
    from .operation_handover_core import record_proof_batch
    context=_current.get()
    proof_batch=record_proof_batch(events) if context and context.get('__http_get_read__') is True else None
    for event in events:
        event_history=verify_record(event,proof_batch=proof_batch)
        if (event.company_id!=task.company_id or event.previous_hash!=previous
            or event.event_hash!=_hash(event_payload(event)) or event.source_snapshot!=event_payload(event)):
            fail('CUSTODY_EVENT_CHAIN_UNPROVEN','数量保管事件或前事件Hash不一致，不能以投影补齐。')
        if event.kind=='FG_WAREHOUSE_ACCEPT':
            from .finished_goods_authority import verify_warehouse_conversion
            verify_warehouse_conversion(event)
        if event.kind in ('INPUT_PROVEN','RANGE_RELEASE'):
            from system.models import OrganizationOperatingAuditRecord
            states={s['id']:s for s in event.data.get('afterSlices',[])}
            for reference in event.data.get('projectionAudits',[]):
                import re
                match=re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)',reference.get('auditReference',''))
                audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
                state=states.get(reference.get('sliceId'));proof=audit.after_snapshot.get('state',{}) if audit else {}
                if (not state or not audit or audit.target_type!='OperationCustodySlice' or audit.target_id!=state['id']
                    or audit.organization_id!=task.company_id or audit.actor_id!=event.created_by_id
                    or audit.action_code!=event_history['statusTransitionHistory'][0]['actionCode']
                    or not isinstance(proof.get('row',{}).get('projection'),dict)
                    or not proof['row']['projection']
                    or any(key not in ('frozen','version','data') or state.get(key)!=value for key,value in proof['row']['projection'].items())
                    or proof.get('qualification',{}).get('ready') is not True):
                    fail('OUTPUT_INPUT_RELEASE_AUDIT_UNPROVEN','投入闭合解除冻结缺少相同动作及真实审计。')
            if event.kind=='INPUT_PROVEN' and (not event.data.get('subsetReleaseOnly') or event.data.get('effectiveOutputDelta')!='0' or event.credit):
                fail('OUTPUT_INPUT_RELEASE_NOT_SUBSET','解除冻结仅改变可支配子集，不得增加生产或保管数量。')
        for state in event.data.get('afterSlices',[]):
            expected[state['id']]=state
        for state in event.data.get('afterHandovers',[]):headers[state['id']]=state
        for state in event.data.get('afterAllocations',[]):allocations[state['id']]=state
        previous=event.event_hash
    rows=list(OperationCustodySlice.objects.filter(root__task_id=task.pk).order_by('pk'))
    for row in rows:
        if expected.get(row.pk)!=slice_projection(row):
            fail('CUSTODY_PROJECTION_UNPROVEN','当前份额投影缺少一致的正式事件，禁止读取为可用量。')
    if set(expected)!={r.pk for r in rows}:
        fail('CUSTODY_EVENT_OBJECT_UNPROVEN','保管事件引用了缺失或其他来源的份额。')
    from .operation_handover_models import OperationHandover
    header_rows=(OperationHandover.objects.filter(pk__in=headers,company_id=task.company_id).in_bulk()
        if proof_batch is not None else None)
    allocation_rows=(OperationHandoverAllocation.objects.filter(pk__in=allocations,root__task_id=task.pk).in_bulk()
        if proof_batch is not None else None)
    for pk,projection in headers.items():
        row=header_rows.get(pk) if header_rows is not None else OperationHandover.objects.filter(pk=pk,company_id=task.company_id).first()
        if not row or header_projection(row)!=projection:
            fail('CUSTODY_HEADER_PROJECTION_UNPROVEN','交接单当前状态或版本缺少一致的正式事件。')
    for pk,projection in allocations.items():
        row=allocation_rows.get(pk) if allocation_rows is not None else OperationHandoverAllocation.objects.filter(pk=pk,root__task_id=task.pk).first()
        if not row or allocation_projection(row)!=projection:
            fail('CUSTODY_ALLOCATION_PROJECTION_UNPROVEN','交接分量当前余额或版本缺少一致的正式事件。')
    from .operation_handover_models import OperationCustodyException
    for exception in OperationCustodyException.objects.filter(task_id=task.pk,status__in=('confirmed','rejected')):
        if exception.company_id!=task.company_id:fail('CUSTODY_REVIEW_OBJECT_MISMATCH','关联处置与准确来源公司不一致。')
        verify_record(exception)
    for allocation in task_inputs(task.pk):
        verify_record(allocation)
        release=allocation.source_snapshot.get('sourceRangeReleaseProof',{})
        span=allocation.data.get('outputRange',{})
        from .operation_handover_core import atoms
        out_hi=atoms(allocation.output.quantity,allocation.output.uom.decimal_places)
        shape=isinstance(span,dict) and set(span)=={'startAtom','endAtom'}
        try:scope_valid=shape and 0<=int(span['startAtom'])<int(span['endAtom'])<=out_hi
        except (ValueError,TypeError):scope_valid=False
        if (allocation.company_id!=task.company_id or allocation.execution_start.task_id!=task.pk
            or allocation.source_slice.company_id!=task.company_id
            or allocation.source_slice.status!='C'
            or allocation.data.get('executionStartId')!=allocation.execution_start_id
            or allocation.data.get('outputId')!=allocation.output_id or not scope_valid
            or allocation.data.get('outputRange')!=allocation.source_snapshot.get('outputRange')
            or allocation.data.get('outputUomId')!=allocation.output.uom_id
            or release.get('outputEvidenceId')!=allocation.source_slice.root_id
            or release.get('scopeHash')!=allocation.source_slice.root.scope_hash
            or release.get('sourceSnapshotHash')!=allocation.source_slice.root.source_snapshot_hash
            or release.get('inputPurpose',{}).get('taskId')!=task.pk
            or release!=input_custody_basis(allocation.source_slice,task)):
            fail('OUTPUT_INPUT_CLOSURE_UNPROVEN','新产出缺少真实投入范围及原份额封闭证明。')
    return True


def handover_totals(row):
    sent=Decimal(0);received=Decimal(0);short=Decimal(0);in_transit=Decimal(0);returned=Decimal(0);lost=Decimal(0);unmatched=Decimal(0)
    for a in row.allocations.order_by('pk'):
        verify_record(a)
        data=a.data
        sent=add(sent,a.quantity if data.get('dispatched') else '0')
        received=add(received,data.get('received','0'));short=add(short,data.get('short','0'))
        returned=add(returned,data.get('returnedBeforeReceipt','0'));lost=add(lost,data.get('lost','0'))
        unmatched=add(unmatched,data.get('unmatched','0'))
        if data.get('dispatched'):
            remaining=add(a.quantity,-Decimal(data.get('received','0')),-Decimal(data.get('short','0')),-Decimal(data.get('returnedBeforeReceipt','0')),-Decimal(data.get('lost','0')))
            if remaining<0:fail('HANDOVER_LEG_CONSERVATION_FAILED','单腿收讫、差额或退回超过原发出份额。')
            in_transit=add(in_transit,remaining)
    return {'sentQuantity':text(sent),'receivedQuantity':text(received),'inTransitQuantity':text(in_transit),
        'shortQuantity':text(short),'returnedBeforeReceiptQuantity':text(returned),
        'lostQuantity':text(lost),'unmatchedQuantity':text(unmatched)}


def short_resolution(row):
    """Resolve an immutable original shortage range against verified leaf facts."""
    from .operation_handover_core import atoms,from_atoms
    ranges=row.source_snapshot.get('scopeRanges')
    if not isinstance(ranges,list) or not ranges:fail('CUSTODY_SHORT_SCOPE_UNPROVEN','原短收缺少准确范围，不能按整腿余额猜测结清。')
    remaining=0;precision=row.allocation.uom.decimal_places
    covered=0
    for scope in ranges:
        lo,hi=int(scope['startAtom']),int(scope['endAtom']);covered+=hi-lo
        for leaf in OperationCustodySlice.objects.filter(root_id=scope['rootId']).exclude(status='closed'):
            overlap=max(0,min(hi,int(leaf.end_atom))-max(lo,int(leaf.start_atom)))
            if not overlap:continue
            unresolved=(leaf.status=='Q' or (leaf.data.get('originalUnreceivedAllocationId')==row.allocation_id
                and not leaf.data.get('originalUnreceivedResolvedBy') and leaf.status!='Z'))
            if unresolved:remaining+=overlap
    if covered!=atoms(row.quantity,precision):fail('CUSTODY_SHORT_SCOPE_UNPROVEN','原短收范围之和与正式差额不一致。')
    references=[]
    for event in OperationCustodyEvent.objects.filter(task_id=row.task_id,allocation_id=row.allocation_id).order_by('pk'):
        if event.kind in ('RECEIVE','RETURN_UNRECEIVED','EXCEPTION_RESOLVE','UNMATCHED_SOURCE_MATCH'):
            references.append({'eventId':event.pk,'eventHash':event.event_hash,'kind':event.kind,
                'occurredAt':event.occurred_at.isoformat()})
    return {'remainingQuantity':text(from_atoms(remaining,precision)),'resolutionReferences':references}


def settle_short_exceptions(allocation,*,actor,code,q,reason):
    from .operation_handover_models import OperationCustodyException
    from .operation_handover_core import project,transition
    for row in OperationCustodyException.objects.filter(allocation=allocation,kind='SHORT',status='pending'):
        result=short_resolution(row)
        if result['remainingQuantity']=='0':
            project(row,data={**row.data,**result})
            transition(row,'confirmed',actor=actor,code=code,q=q,reason=reason)


def unmatched_resolution(row):
    """Claims consume the original observed X ranges in formal FIFO order."""
    from .operation_handover_models import OperationCustodyException
    originals=list(OperationCustodyException.objects.filter(allocation_id=row.allocation_id,
        kind='UNMATCHED_EXCESS').order_by('pk'))
    for original in originals:verify_record(original)
    total=add(*(x.quantity for x in originals));unclaimed=Decimal(row.allocation.data.get('unmatched','0'))
    claimed=add(total,-unclaimed)
    if claimed<0:fail('CUSTODY_UNMATCHED_SCOPE_UNPROVEN','未匹配余额超过正式原始超收观察。')
    remaining=None
    for original in originals:
        used=min(claimed,Decimal(original.quantity));claimed=add(claimed,-used)
        if original.pk==row.pk:remaining=add(original.quantity,-used)
    if remaining is None:fail('CUSTODY_UNMATCHED_SCOPE_UNPROVEN','原始超收观察缺失。')
    references=[{'eventId':e.pk,'eventHash':e.event_hash,'occurredAt':e.occurred_at.isoformat()}
        for e in OperationCustodyEvent.objects.filter(task_id=row.task_id,allocation_id=row.allocation_id,
            kind='EXCEPTION_RESOLVE',debit='UNMATCHED_CLAIM').order_by('pk')]
    return {'remainingQuantity':text(remaining),'resolutionReferences':references,
        'scopeConsumptionLabel':'同一原物流分量的真实超收观察按原记录顺序匹配，不新增产出'}


def settle_unmatched_exceptions(allocation,*,actor,code,q,reason):
    from .operation_handover_models import OperationCustodyException
    from .operation_handover_core import project,transition
    for row in OperationCustodyException.objects.filter(allocation=allocation,kind='UNMATCHED_EXCESS',status='pending'):
        result=unmatched_resolution(row)
        if result['remainingQuantity']=='0':
            project(row,data={**row.data,**result})
            transition(row,'confirmed',actor=actor,code=code,q=q,reason=reason)


@routing_read_phase("custody")
def verify_handover(row, *, include_task_custody=True):
    history=verify_record(row)
    if row.sender_employee_id and row.sender_employee_id==row.receiver_employee_id:
        fail('HANDOVER_PARTIES_NOT_SEPARATE','实际交出与收讫必须为不同真实员工。')
    units=set(row.allocations.values_list('uom_id',flat=True))
    if len(units)!=1:fail('HANDOVER_UNIT_SCOPE_UNPROVEN','正式物流腿必须具有同一来源单位的真实分量，不能为空或混合单位。')
    seen=set()
    for a in row.allocations.select_related('root__task'):
        if a.company_id!=row.company_id or a.root.company_id!=row.company_id or a.root.task.work_order.company_id!=row.company_id:
            fail('HANDOVER_OBJECT_COMPANY_MISMATCH','物流分量与公司或生产root不一致。')
        if include_task_custody and a.root.task_id not in seen:
            verify_task_custody(a.root.task)
            seen.add(a.root.task_id)
    return {**history,**handover_totals(row)}


def is_upstream(source_operation, destination_task):
    if destination_task.work_order.usage_purpose=='TEST_BUSINESS':
        from .test_operation_predecessor_authority import route_nodes
        from .operation_dependency_graph import validate_graph
        if source_operation.work_order_id!=destination_task.work_order_id:return False
        nodes=route_nodes(destination_task.work_order);issue=validate_graph(nodes,destination_task.source_operation.sequence)
        if issue:fail('OUTPUT_INPUT_ROUTE_UNPROVEN',issue)
        visited=set();stack=list(nodes[destination_task.source_operation.sequence]['frozenPredecessors'])
        while stack:
            seq=stack.pop()
            if seq in visited:continue
            visited.add(seq)
            if seq==source_operation.sequence:return True
            stack.extend(nodes[seq]['frozenPredecessors'])
        return False
    from .operation_predecessor_authority import _graph
    graph,issue=_graph(destination_task)
    if issue:fail('OUTPUT_INPUT_ROUTE_UNPROVEN',issue)
    visited=set();stack=list(destination_task.source_operation.source_snapshot['predecessorSequences'])
    while stack:
        seq=stack.pop()
        if seq in visited:continue
        visited.add(seq)
        operation=graph.get(seq)
        if not operation:fail('OUTPUT_INPUT_ROUTE_UNPROVEN','投入来源的显式前序工序缺失。')
        if operation.pk==source_operation.pk:return True
        stack.extend(operation.source_snapshot['predecessorSequences'])
    return False


@routing_read_phase("custody")
def input_custody_basis(row,destination_task,actor=None):
    """Re-prove one exact range; workshop equality alone never grants custody."""
    from .operation_handover_models import OperationHandover
    from .operation_output_authority import evidence_proof
    from .custody_dependency_reads import read_rows
    verify_task_custody(row.root.task);verify_record(row)
    if (row.company_id!=destination_task.company_id or row.root.task.work_order_id!=destination_task.work_order_id
        or row.holder_workshop_id!=destination_task.workshop_id
        or not is_upstream(row.root.task.source_operation,destination_task)):
        fail('OUTPUT_INPUT_SOURCE_UNPROVEN','真实批次、当前车间或显式工艺来源与目标任务不一致。')
    evidence_proof(row.root)
    if row.data.get('originalUnreceivedAllocationId') and not row.data.get('originalUnreceivedResolvedBy'):
        fail('OUTPUT_INPUT_UNRECEIVED_SOURCE_BLOCKED','仅已定位的原未签份额尚未结清，不得投入。')
    purpose={'taskId':destination_task.pk,'operationId':destination_task.source_operation_id,
        'workCenterId':destination_task.work_center_id}
    reference={'outputEvidenceId':row.root_id,'scopeHash':row.root.scope_hash,
        'sourceSnapshotHash':row.root.source_snapshot_hash}
    release_hash=row.data.get('rangeReleaseIntentHash')
    if release_hash:
        events=[event for event in task_events(row.root.task_id) if event.company_id==row.company_id
            and event.kind=='RANGE_RELEASE' and event.intent_hash==release_hash]
        if len(events)!=1:fail('OUTPUT_SOURCE_RANGE_RELEASE_UNPROVEN','来源范围释放事件不唯一或缺失。')
        event=events[0];history=verify_record(event);release=event.data.get('rangeRelease',{})
        target=release.get('target',{})
        if (history['statusTransitionHistory'][0]['actionCode']!='production.operation.handover.range.release'
            or target.get('workCenterId')!=destination_task.work_center_id
            or target.get('taskId') is not None and (target.get('taskId')!=destination_task.pk
                or target.get('taskVersion')!=destination_task.version
                or target.get('taskSourceSnapshotHash')!=destination_task.source_snapshot_hash)
            or target.get('operationId') is not None and target.get('operationId')!=destination_task.source_operation_id
            or event.qualification_snapshot.get('currentActorEvidence',{}).get('workCenterId')!=release.get('sourceWorkCenterId')
            or not any(s.get('rootId')==row.root_id and int(s['startAtom'])<=int(row.start_atom)<int(row.end_atom)<=int(s['endAtom'])
                and s.get('rootSourceHash')==row.root.source_snapshot_hash for s in release.get('ranges',[]))):
            fail('OUTPUT_SOURCE_RANGE_RELEASE_UNPROVEN','来源负责人释放未准确绑定本份额及真实目标任务。')
        return {**reference,'kind':'SOURCE_RANGE_RELEASE','inputPurpose':{**purpose,'reference':release['reference']},
            'eventId':event.pk,'eventHash':event.event_hash,'requestHash':event.intent_hash,
            'availableAt':offset_iso(max(source_available_at(row,include_range=False),event.occurred_at))}
    leg_id=row.data.get('receivedLegId')
    if leg_id:
        header=read_rows('input_header',(leg_id,row.company_id,row.root.task_id),lambda:
            OperationHandover.objects.filter(pk=leg_id,company_id=row.company_id,data__taskId=row.root.task_id).first())
        allocations=read_rows('input_header_allocations',header.pk,lambda:list(header.allocations.order_by('pk'))) if header else []
        allocation_id=OperationHandoverAllocation._meta.pk.get_prep_value(row.data.get('legAllocationId')) if header else None
        allocation=next((item for item in allocations if item.pk==allocation_id and item.root_id==row.root_id),None)
        if (header and allocation and header.destination_kind=='production' and header.sender_employee_id
            and header.target_operation_id==destination_task.source_operation_id
            and header.target_work_center_id==destination_task.work_center_id
            and header.target_workshop_id==destination_task.workshop_id and row.holder_work_center_id==header.target_work_center_id):
            verify_handover(header)
            receipt=None
            receipts=read_rows('input_header_receipts',header.pk,lambda:list(
                OperationCustodyEvent.objects.filter(handover=header,kind='RECEIVE').order_by('pk')))
            for event in receipts:
                if (event.data.get('receiverEmployeeId')==row.data.get('receivedEmployeeId')
                    and any(s.get('rootId')==row.root_id and int(s['startAtom'])<=int(row.start_atom)<int(row.end_atom)<=int(s['endAtom'])
                        and s.get('data',{}).get('receivedLegId')==header.pk for s in event.data.get('afterSlices',[]))):
                    verify_record(event);receipt={'eventId':event.pk,'eventHash':event.event_hash,
                        'receiverEmployeeId':event.data['receiverEmployeeId'],'occurredAt':offset_iso(event.occurred_at)};break
            claim_id=row.data.get('unmatchedClaimExceptionId')
            if not receipt and claim_id:
                from .operation_handover_models import OperationCustodyException
                from .operation_output_authority import verify_shared_review
                claim=OperationCustodyException.objects.filter(pk=claim_id,company_id=row.company_id,kind='UNMATCHED_CLAIM',status='confirmed').first()
                if claim and claim.data.get('matchedAllocationId')==allocation.pk:
                    verify_record(claim);review=verify_shared_review(claim)
                    match=OperationCustodyEvent.objects.filter(company_id=row.company_id,kind='EXCEPTION_RESOLVE',
                        data__exceptionId=claim.pk).order_by('pk').last()
                    if not match:fail('OUTPUT_INPUT_RECEIPT_UNPROVEN','真实认领缺少准确处置事件。')
                    verify_record(match)
                    receipt={'claimExceptionId':claim.pk,'claimSourceHash':claim.source_snapshot_hash,
                        'rawReceiptHandoverId':claim.handover_id,'review':review,'occurredAt':offset_iso(match.occurred_at)}
            if not receipt:fail('OUTPUT_INPUT_RECEIPT_UNPROVEN','本范围缺少对应的真实接收事件或已核定的原多收来源证明。')
            return {**reference,'kind':'FORMAL_PRODUCTION_RECEIPT','inputPurpose':purpose,
                'handoverId':header.pk,'handoverSourceHash':header.source_snapshot_hash,
                'allocationId':allocation.pk,'senderEmployeeId':header.sender_employee_id,'receiptProof':receipt,
                'availableAt':receipt['occurredAt']}
    original=row.root.scope_manifest.get('inputPurpose')
    source_q=row.root.qualification_snapshot
    if (row.data.get('normalPurposeActive') and row.root.kind in ('NORMAL_CONFIRM','WHOLE_RELEASE') and isinstance(original,dict)
        and all(original.get(k)==v for k,v in purpose.items())
        and source_q.get('actionContract',{}).get('actionCode')=='production.operation.output.confirm'
        and source_q.get('currentActorEvidence',{}).get('workCenterId')==row.root.task.work_center_id
        and source_q.get('currentActorEvidence',{}).get('workCenterResponsibilityScopeId')):
        return {**reference,'kind':'SOURCE_NORMAL_OUTPUT_PURPOSE','inputPurpose':deepcopy(original),
            'availableAt':offset_iso(source_available_at(row))}
    fail('OUTPUT_SOURCE_RANGE_RELEASE_REQUIRED','本范围尚无真实来源负责人用途释放或准确生产去处正式收讫证明；同车间不等于可任意消费。')


def custody_responsibility(row):
    """Current exclusive management authority; the physical holder is unchanged."""
    if row.status not in ('U','S','V'):return None
    release_hash=row.data.get('rangeReleaseIntentHash')
    if not release_hash:
        purpose=row.root.scope_manifest.get('inputPurpose')
        q=row.root.qualification_snapshot
        if (row.data.get('normalPurposeActive') and row.root.kind in ('NORMAL_CONFIRM','WHOLE_RELEASE')
            and isinstance(purpose,dict) and q.get('actionContract',{}).get('actionCode')=='production.operation.output.confirm'
            and q.get('currentActorEvidence',{}).get('workCenterResponsibilityScopeId')):
            verify_record(row.root);return purpose['workCenterId']
        return row.holder_work_center_id
    events=[event for event in task_events(row.root.task_id) if event.company_id==row.company_id
        and event.kind=='RANGE_RELEASE' and event.intent_hash==release_hash]
    if len(events)!=1:fail('CUSTODY_RESPONSIBILITY_UNPROVEN','当前责任可支配范围缺少唯一正式释放事件。')
    event=events[0];proof=verify_record(event);release=event.data.get('rangeRelease',{})
    target=release.get('target',{})
    if (proof['statusTransitionHistory'][0]['actionCode']!='production.operation.handover.range.release'
        or event.qualification_snapshot.get('currentActorEvidence',{}).get('workCenterId')!=release.get('sourceWorkCenterId')
        or target.get('workshopId')!=row.holder_workshop_id
        or not any(s.get('rootId')==row.root_id and s.get('rootSourceHash')==row.root.source_snapshot_hash
            and int(s['startAtom'])<=int(row.start_atom)<int(row.end_atom)<=int(s['endAtom']) for s in release.get('ranges',[]))):
        fail('CUSTODY_RESPONSIBILITY_UNPROVEN','责任释放未绑定本真实范围、同车间或准确Source权限。')
    return target['workCenterId']


def source_available_at(row,*,include_range=True):
    times=[row.root.occurred_at]
    for event in task_events(row.root.task_id):
        if event.company_id!=row.company_id:continue
        if event.kind=='OUTPUT_RELEASE' and event.data.get('outputEvidenceId')==row.root_id:times.append(event.occurred_at)
        if include_range and event.kind=='RANGE_RELEASE' and event.intent_hash==row.data.get('rangeReleaseIntentHash'):times.append(event.occurred_at)
        if event.kind in ('RECEIVE','UNMATCHED_SOURCE_MATCH') and event.handover_id==row.data.get('receivedLegId'):
            if any(s.get('rootId')==row.root_id and int(s['startAtom'])<=int(row.start_atom)<int(row.end_atom)<=int(s['endAtom']) for s in event.data.get('afterSlices',[])):
                times.append(event.occurred_at)
    return max(times)


def tracked_input_scope_exists(task):
    from .operation_handover_models import OperationOutputEvidence,OperationHandover
    if OperationOutputEvidence.objects.filter(company_id=task.company_id,status='confirmed',
        kind__in=('NORMAL_CONFIRM','WHOLE_RELEASE'),scope_manifest__inputPurpose__taskId=task.pk).exclude(task_id=task.pk).exists():return True
    for event in OperationCustodyEvent.objects.filter(company_id=task.company_id,kind='RANGE_RELEASE',
        task__work_order_id=task.work_order_id,data__rangeRelease__target__workCenterId=task.work_center_id).exclude(task=task):
        target=event.data.get('rangeRelease',{}).get('target',{})
        if target.get('taskId') in (None,task.pk) and target.get('operationId') in (None,task.source_operation_id):return True
    return OperationHandover.objects.filter(company_id=task.company_id,target_operation_id=task.source_operation_id,
        target_work_center_id=task.work_center_id,destination_kind='production',receiver_employee__isnull=False).exclude(data__taskId=task.pk).exists()
