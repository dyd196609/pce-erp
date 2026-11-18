"""Formal, database-serialized custody movements. No production is dispatched."""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
from django.db import transaction, IntegrityError, OperationalError
from .operation_handover_core import *
from .operation_handover_core import _hash
from .operation_handover_contract import ACTIONS
from .operation_handover_models import (OperationOutputEvidence as Output, OperationCustodySlice as Slice,
    OperationHandover as Handover, OperationHandoverAllocation as Allocation,
    OperationCustodyException as ExceptionRecord, OperationInputAllocation as InputAllocation)
from .operation_output_authority import task_context, bind_account, evidence_proof, read_task_quantity_account
from .operation_handover_authority import (custody_event, verify_task_custody, verify_handover,
    resource_context, handover_totals, is_upstream,settle_short_exceptions,input_custody_basis,custody_responsibility,source_available_at,same_workshop_receipt_proven)
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_resource_read_scope import scoped_execution_read

BASE={'reason','idempotencyKey','occurredAt'}
LABELS={'prepared':'已备交，尚未实际交出','cancelled':'已取消未交备交','in_transit':'已交出，待收讫',
    'partially_received':'部分收讫，余量仍在途','received':'本物流段已收齐','discrepancy_pending':'差额待核',
    'closed_with_difference':'本物流段已依正式差额事实结清'}


def _emit(actor,code,q,task,kind,quantity,debit,credit,stamp,digest,reason,slices=(),header=None,allocation=None,data=None):
    return custody_event(actor=actor,code=code,q=q,task=task,kind=kind,quantity=quantity,debit=debit,
        credit=credit,stamp=stamp,intent_hash=digest,reason=reason,slices=slices,handover=header,allocation=allocation,data=data)


def split_slice(row,amount,*,actor,code,q,stamp,digest,reason,header=None,context=None):
    ctx=context if context is not None else task_context(row.root.task,actor);precision=ctx['unit'].decimal_places
    amount=Decimal(amount)
    if not 0<amount<=Decimal(row.quantity):fail('HANDOVER_SLICE_EXCEEDED','分量超过真实可支配份额。')
    if amount==Decimal(row.quantity):return row
    lo,hi=int(row.start_atom),int(row.end_atom);middle=lo+atoms(amount,precision)
    if not lo<middle<hi:fail('HANDOVER_SLICE_PRECISION','分拆不能表示为来源单位的准确区间。')
    previous_status=row.status
    transition(row,'closed',actor=actor,code=code,q=q,reason=reason)
    children=[]
    for start,end in ((lo,middle),(middle,hi)):
        child=initialize(Slice,actor=actor,code=code,q=q,status=previous_status,
            source={'parentSliceId':row.pk,'parentSourceHash':row.source_snapshot_hash,
                'rootId':row.root_id,'startAtom':str(start),'endAtom':str(end)},intent_hash=digest,reason=reason,
            root=row.root,parent=row,quantity=text(from_atoms(end-start,precision)),start_atom=str(start),end_atom=str(end),
            holder_workshop_id=row.holder_workshop_id,holder_work_center_id=row.holder_work_center_id,
            reserved_by=row.reserved_by,frozen=row.frozen,data=deepcopy(row.data))
        children.append(child)
    _emit(actor,code,q,row.root.task,'SPLIT',row.quantity,previous_status,previous_status,stamp,digest,reason,
        [row]+children,header=header,data={'parentSliceId':row.pk})
    return children[0]


def _task(actor,task_id):
    task=Task.objects.select_related('work_order','source_operation','work_center','workload_uom').filter(pk=task_id,company_id=actor.company_id).first()
    if not task:fail('HANDOVER_TASK_NOT_VISIBLE','未找到本公司正式来源任务。',403)
    return task


def _target(actor,task,delivery):
    from pde.models import WorkCenter
    from .work_order_models import ProductionWorkOrderOperation
    strict_id(delivery.get('targetWorkCenterId'),'目标工作中心')
    strict_id(delivery.get('targetOperationId'),'目标工序',nullable=True)
    center=WorkCenter.objects.select_related('workshop').filter(pk=delivery.get('targetWorkCenterId'),company_id=actor.company_id,is_active=True).first()
    if not center or not center.workshop_id:fail('HANDOVER_TARGET_RESOURCE_UNPROVEN','请选择同公司当前有效的实际目标工作中心。')
    target_op=None;source={}
    if delivery.get('targetOperationId'):
        target_op=ProductionWorkOrderOperation.objects.select_related('work_order','effective_step').filter(
            pk=delivery['targetOperationId'],work_order_id=task.work_order_id).first()
        if not target_op:fail('HANDOVER_TARGET_OPERATION_MISMATCH','物流目标不是本工单的正式工序。')
        from .operation_handover_route import reconciled_physical_target
        current=reconciled_physical_target(actor,task,target_op,center) or resource_context(target_op,actor,include_plan=True)
        if current['workCenter'].pk!=center.pk:fail('HANDOVER_TARGET_RESOURCE_CHANGED','实际目标与工序当前有效资源不一致。')
        source=current['snapshot']
    kind=delivery.get('destinationKind','production')
    if kind not in ('storage','production'):fail('HANDOVER_DESTINATION_INVALID','去处仅接受正式生产去处或受托暂存。',400)
    if kind=='storage' and not str(delivery.get('destinationReference','')).strip():
        fail('HANDOVER_STORAGE_REFERENCE_REQUIRED','暂存须填写唯一实际暂存区或容器标识。',400)
    if kind=='production' and not target_op:
        fail('HANDOVER_TARGET_OPERATION_REQUIRED','生产去处须绑定本工单真实目标工序，暂不要求该工序已有任务。',400)
    return center,target_op,kind,source


def _prepare(actor,payload,accounts,action='prepare'):
    allowed=BASE|{'taskId','sourceWorkCenterId','expectedSourceSnapshotHash','expectedAccountSnapshotHash',
        'deliveries','sliceAllocations','targetWorkCenterId','targetOperationId','destinationKind',
        'destinationReference','purpose','previousHandoverId','outputConfirmation'}
    payload_guard(payload,allowed,{'taskId','sourceWorkCenterId','expectedSourceSnapshotHash','occurredAt','reason','idempotencyKey'})
    strict_id(payload['taskId'],'来源任务');strict_id(payload['sourceWorkCenterId'],'实际交出中心')
    strict_id(payload.get('previousHandoverId'),'前物流段',nullable=True)
    task=_task(actor,payload['taskId']);ctx=task_context(task,actor);account=accounts[task.pk];bind_account(ctx,account)
    previous=None
    if payload.get('previousHandoverId') is not None:
        previous=Handover.objects.filter(pk=payload['previousHandoverId'],company_id=actor.company_id,data__taskId=task.pk).first()
        if not previous:fail('HANDOVER_PREVIOUS_SCOPE_MISMATCH','所带前物流段不属于本公司本生产来源，不能挂接。',403)
        verify_handover(previous)
    code=ACTIONS[action][0];q=qualify(actor,code,payload['sourceWorkCenterId'],'ProductionWorkshopTask',task.pk)
    digest,replay=intent(actor,code,None,payload)
    if replay:
        header=Handover.objects.get(pk=replay.target_entity_id,company_id=actor.company_id);verify_handover(header);return header,False
    ctx['account']=account
    current=read_task_quantity_account(task,actor,context=ctx)
    if not current['ready']:fail('HANDOVER_CURRENT_PRODUCTION_BLOCKED','；'.join(current['blockingReasons']))
    if payload['expectedSourceSnapshotHash']!=task.source_snapshot_hash or payload.get('expectedAccountSnapshotHash',current['accountSnapshotHash'])!=current['accountSnapshotHash']:
        fail('HANDOVER_SOURCE_OR_ACCOUNT_CHANGED','原来源或数量账户已变化，请保留选择只读重新核查。')
    stamp=occurred(payload['occurredAt']);reason=payload['reason'].strip()
    new_slice=None
    if payload.get('outputConfirmation'):
        from .operation_output_service import confirm_output
        sub=deepcopy(payload['outputConfirmation'])
        sub['taskId']=task.pk;sub['reason']=reason
        sub['idempotencyKey']='embedded-output-'+sha256(payload['idempotencyKey'].encode()).hexdigest()
        output,_=confirm_output(actor=actor,payload=sub,accounts=accounts,context=ctx)
        new_slice=output.slices.filter(parent__isnull=True).first()
    deliveries=payload.get('deliveries')
    if deliveries is None:
        deliveries=[{k:deepcopy(v) for k,v in payload.items() if k in {'targetWorkCenterId','targetOperationId',
            'destinationKind','destinationReference','sliceAllocations','purpose'}}]
    if not isinstance(deliveries,list) or not deliveries:fail('HANDOVER_DELIVERIES_REQUIRED','请选择至少一个真实去处及准确份额。',400)
    headers=[]
    for delivery in deliveries:
        if not isinstance(delivery,dict) or set(delivery)-{'targetWorkCenterId','targetOperationId','destinationKind',
            'destinationReference','sliceAllocations','purpose','quantity'}:
            fail('HANDOVER_DELIVERY_INVALID','去处意图包含未注册字段。',400)
        center,target_op,destination,target_source=_target(actor,task,delivery)
        from pde.models import WorkCenter
        source_wc=WorkCenter.objects.select_related('workshop').filter(pk=payload['sourceWorkCenterId'],company_id=actor.company_id,is_active=True).first()
        if not source_wc or not source_wc.workshop_id:fail('HANDOVER_SOURCE_WC_UNPROVEN','实际交出中心或车间未核实。')
        if destination=='production' and action!='return':
            from .operation_handover_route import validate_production_target
            validate_production_target(actor,task,target_op)
        if action=='return' and center.pk!=task.work_center_id:
            fail('HANDOVER_RETURN_SOURCE_MISMATCH','退回须明确送至本原生产来源中心，不能借退回改为其他去处。')
        selections=delivery.get('sliceAllocations')
        if selections is None and new_slice:
            requested=number(delivery.get('quantity'),positive=True,precision=ctx['unit'].decimal_places)
            selections=[];remaining=requested
            for leaf in Slice.objects.filter(root_id=new_slice.root_id,status='U',reserved_by=None,frozen=False).order_by('pk'):
                if remaining<=0:break
                amount=min(remaining,Decimal(leaf.quantity))
                selections.append({'sliceId':leaf.pk,'expectedVersion':leaf.version,'quantity':text(amount)})
                remaining=add(remaining,-amount)
            if remaining>0:fail('HANDOVER_NEW_OUTPUT_RANGE_EXCEEDED','本次多去处累计超过同事务新确认的真实未占用范围。')
        if not isinstance(selections,list) or not selections:fail('HANDOVER_SLICES_REQUIRED','请选择已确认并定位的真实批次份额。',400)
        source={'taskId':task.pk,'sourceSnapshotHash':task.source_snapshot_hash,'accountKey':ctx['accountKey'],
            'sourceWorkCenterId':source_wc.pk,'sourceWorkshopId':source_wc.workshop_id,
            'target':target_source,'targetWorkCenterId':center.pk,'targetWorkshopId':center.workshop_id,
            'destinationKind':destination,'purpose':str(delivery.get('purpose','')).strip(),
            'intentPayload':{k:deepcopy(v) for k,v in payload.items() if k!='idempotencyKey'}}
        if (destination=='storage' or action=='return') and target_op and target_op.pk not in [op.pk for op in task.work_order.operations.all()
            if task.source_operation.sequence in op.source_snapshot.get('predecessorSequences',[])]:
            if not source['purpose']:
                fail('HANDOVER_INDIRECT_PURPOSE_REQUIRED','非直接工艺后序送达须明确真实物流用途，不代表前序准入。',400)
        header=initialize(Handover,actor=actor,code=code,q=q,status='prepared',source=source,intent_hash=digest,reason=reason,
            no='HO-'+uuid4().hex,kind='RETURN' if action=='return' else 'FORWARD' if action=='forward' else 'NORMAL',
            source_work_center=source_wc,source_workshop_id=source_wc.workshop_id,target_work_center=center,
            target_workshop_id=center.workshop_id,target_operation=target_op,destination_kind=destination,
            destination_reference=str(delivery.get('destinationReference','')).strip(),
            previous_handover_id=payload.get('previousHandoverId'),data={'taskId':task.pk})
        from .operation_handover_number import assign_number
        assign_number(header,actor=actor)
        for selection in selections:
            if not isinstance(selection,dict) or set(selection)!={'sliceId','expectedVersion','quantity'}:
                fail('HANDOVER_SLICE_INTENT_INVALID','份额选择只接受真实ID、原版本及数量。',400)
            strict_id(selection['sliceId'],'份额');strict_id(selection['expectedVersion'],'份额版本',zero=True)
            row=Slice.objects.select_related('root__task').filter(pk=selection['sliceId'],company_id=actor.company_id,root__task_id=task.pk).first()
            if (not row or row.version!=selection['expectedVersion'] or row.status not in ('U','S','V')
                or row.reserved_by_id or row.frozen or row.holder_workshop_id!=source_wc.workshop_id
                or custody_responsibility(row)!=source_wc.pk):
                fail('HANDOVER_SLICE_NOT_AVAILABLE','该份额不是本实际中心可支配的准确版本，或已占用／冻结。')
            if action in ('forward','return') and row.status not in ('S','V') and not same_workshop_receipt_proven(row):
                fail('HANDOVER_REAL_RECEIPT_REQUIRED','转送或退回必须引用真实已收讫且未投入的保管份额。')
            if row.data.get('originalUnreceivedAllocationId') and not row.data.get('originalUnreceivedResolvedBy') and action!='return':
                fail('HANDOVER_UNRECEIVED_SCOPE_UNRESOLVED','原未签范围仅已定位保管；须先正式实回源或处置，不能转送冒充原收讫。')
            prior_id=row.data.get('receivedLegId')
            prior_allocation_id=row.data.get('legAllocationId')
            if row.data.get('originalUnreceivedAllocationId') and not row.data.get('originalUnreceivedResolvedBy'):
                original=Allocation.objects.filter(pk=row.data['originalUnreceivedAllocationId'],company_id=actor.company_id,root=row.root).first()
                if not original:fail('HANDOVER_PREVIOUS_SCOPE_MISMATCH','未签定位范围缺少准确原物流腿。')
                prior_id=original.handover_id;prior_allocation_id=original.pk
            if prior_id is not None:
                prior=Handover.objects.filter(pk=prior_id,company_id=actor.company_id,data__taskId=task.pk).first()
                if not prior:fail('HANDOVER_PREVIOUS_SCOPE_MISMATCH','份额原物流腿不属于本公司本来源。')
                verify_handover(prior)
            if previous is not None and prior_id!=previous.pk:
                fail('HANDOVER_PREVIOUS_SLICE_MISMATCH','所带前物流段不是本准确份额真实经历的前段。')
            amount=number(selection['quantity'],positive=True,precision=ctx['unit'].decimal_places)
            row=split_slice(row,amount,actor=actor,code=code,q=q,stamp=stamp,digest=digest,reason=reason,header=header,context=ctx)
            alloc=initialize(Allocation,actor=actor,code=code,q=q,status='bound',
                source={'sliceId':row.pk,'rootId':row.root_id,'sourceHash':row.source_snapshot_hash,
                    'quantity':row.quantity,'startAtom':row.start_atom,'endAtom':row.end_atom,
                    'priorHandoverId':prior_id,'priorAllocationId':prior_allocation_id},
                intent_hash=digest,reason=reason,handover=header,source_slice=row,root=row.root,
                quantity=row.quantity,uom_id=row.root.uom_id,data={'received':'0','short':'0','lost':'0',
                    'returnedBeforeReceipt':'0','unmatched':'0','dispatched':False,'originalBucket':row.status})
            project(row,reserved_by=alloc,version=row.version+1)
            _emit(actor,code,q,task,'PREPARE',row.quantity,row.status,row.status,stamp,digest,reason,[row],header=header,allocation=alloc)
        headers.append(header)
    bump(account,'custody')
    commit_intent(actor,code,payload,digest,headers[0],{'taskId':task.pk,
        'handoverId':headers[0].pk,'handoverIds':[h.pk for h in headers]})
    headers[0]._validated_output_context=ctx
    return headers[0],True


def _expect_header(row,payload):
    strict_id(payload.get('expectedVersion'),'交接单版本',zero=True)
    if payload.get('expectedVersion')!=row.version or payload.get('expectedSourceSnapshotHash')!=row.source_snapshot_hash:
        fail('HANDOVER_VERSION_CHANGED','交接单版本或原意图Hash已变化，请只读重新核对。')


def _refresh_status(row,actor,code,q,reason):
    totals=handover_totals(row)
    if Decimal(totals['shortQuantity'])>0:state='discrepancy_pending'
    elif Decimal(totals['inTransitQuantity'])>0:
        state='partially_received' if Decimal(totals['receivedQuantity'])>0 else 'in_transit'
    elif Decimal(totals['returnedBeforeReceiptQuantity'])>0 or Decimal(totals['lostQuantity'])>0:state='closed_with_difference'
    else:state='received'
    if row.status==state:project(row,version=row.version+1)
    else:transition(row,state,actor=actor,code=code,q=q,reason=reason)


def _current_target(actor,row,task):
    """New physical actions require today's target; historical proofs stay frozen."""
    center,operation,kind,snapshot=_target(actor,task,{'targetWorkCenterId':row.target_work_center_id,
        'targetOperationId':row.target_operation_id,'destinationKind':row.destination_kind,
        'destinationReference':row.destination_reference})
    if kind=='production' and row.kind!='RETURN':
        from .operation_handover_route import validate_production_target
        validate_production_target(actor,task,operation)
    if (center.workshop.company_id!=actor.company_id or not center.workshop.is_active
        or center.workshop_id!=row.target_workshop_id or center.pk!=row.source_snapshot.get('targetWorkCenterId')
        or center.workshop_id!=row.source_snapshot.get('targetWorkshopId')
        or snapshot!=row.source_snapshot.get('target') or kind!=row.source_snapshot.get('destinationKind')):
        fail('HANDOVER_TARGET_CHANGED','目标当前正式资源或车间与本单冻结目标已不一致；保留原在途与历史，先核查治理，不得回填。')


def _dispatch_cancel(actor,row,payload,accounts,action):
    payload_guard(payload,BASE|{'expectedVersion','expectedSourceSnapshotHash'},
        {'expectedVersion','expectedSourceSnapshotHash','occurredAt','reason','idempotencyKey'})
    task=_task(actor,row.data['taskId']);code=ACTIONS[action][0]
    q=qualify(actor,code,row.source_work_center_id,'OperationHandover',row.pk,'prepared')
    verify_handover(row);digest,replay=intent(actor,code,row.pk,payload)
    if replay:return row,False
    _expect_header(row,payload)
    if row.status!='prepared':fail('HANDOVER_NOT_PREPARED','只有尚未真实交出的备交可以交出或取消。')
    resource_context(task.source_operation,actor)
    if action=='dispatch':_current_target(actor,row,task)
    stamp=occurred(payload['occurredAt']);reason=payload['reason'].strip()
    if action=='dispatch':
        project(row,sender_employee_id=q['currentActorEvidence']['employeeId'],dispatched_at=stamp)
        transition(row,'in_transit',actor=actor,code=code,q=q,reason=reason)
    else:transition(row,'cancelled',actor=actor,code=code,q=q,reason=reason)
    for alloc in row.allocations.select_related('source_slice__root__task'):
        slice=alloc.source_slice
        if slice.reserved_by_id!=alloc.pk or slice.status not in ('U','S','V') or slice.frozen or custody_responsibility(slice)!=row.source_work_center_id:
            fail('HANDOVER_RESERVATION_CHANGED','本单占用或实际在手份额已变化。')
        previous=slice.status
        project(slice,reserved_by=None,version=slice.version+1)
        if action=='dispatch':
            if stamp<source_available_at(slice):fail('HANDOVER_TIME_BEFORE_OUTPUT','实际交出不得早于正式批次可用／真实收讫／当前责任释放。',400)
            transition(slice,'I',actor=actor,code=code,q=q,reason=reason)
            project(slice,data={**slice.data,'legAllocationId':alloc.pk},holder_workshop=None,holder_work_center=None)
            project(alloc,data={**alloc.data,'dispatched':True},version=alloc.version+1)
        event=_emit(actor,code,q,task,'DISPATCH' if action=='dispatch' else 'CANCEL',slice.quantity,
            previous,'I' if action=='dispatch' else previous,stamp,digest,reason,[slice],header=row,allocation=alloc)
    bump(accounts[task.pk],'custody')
    commit_intent(actor,code,payload,digest,row,{'handoverId':row.pk,'taskId':task.pk,'status':row.status,
        'eventReference':f'OperationCustodyEvent:{event.pk}'})
    return row,True


def _receive(actor,row,payload,accounts):
    payload_guard(payload,BASE|{'expectedVersion','expectedSourceSnapshotHash','receipts'},
        {'expectedVersion','expectedSourceSnapshotHash','receipts','occurredAt','reason','idempotencyKey'})
    code=ACTIONS['receive'][0];q=qualify(actor,code,row.target_work_center_id,'OperationHandover',row.pk,'in_transit')
    verify_handover(row);digest,replay=intent(actor,code,row.pk,payload)
    if replay:return row,False
    _expect_header(row,payload)
    if row.status not in ('in_transit','partially_received','discrepancy_pending'):
        fail('HANDOVER_RECEIPT_STATE_INVALID','本单没有可办理的实际在途或明确待核份额。')
    task=_task(actor,row.data['taskId'])
    _current_target(actor,row,task)
    employee=q['currentActorEvidence']['employeeId']
    if not row.sender_employee_id or employee==row.sender_employee_id:
        fail('HANDOVER_RECEIVER_NOT_SEPARATE','接收人须与实际交出人为不同真实员工。',403)
    stamp=occurred(payload['occurredAt'],not_before=row.dispatched_at);reason=payload['reason'].strip()
    if not isinstance(payload['receipts'],list) or not payload['receipts']:
        fail('HANDOVER_RECEIPTS_REQUIRED','请明确本次实际收讫范围和是否核对完毕。',400)
    ctx=task_context(task,actor)
    for item in payload['receipts']:
        if not isinstance(item,dict) or set(item)!={'allocationId','expectedVersion','quantity','intent'} or item['intent'] not in ('partial','scope_closed_short'):
            fail('HANDOVER_RECEIPT_INTENT_INVALID','收讫须明确partial或scope_closed_short及原分量版本。',400)
        strict_id(item['allocationId'],'物流分量');strict_id(item['expectedVersion'],'物流分量版本',zero=True)
        alloc=row.allocations.select_related('root__task').filter(pk=item['allocationId']).first()
        if not alloc or alloc.version!=item['expectedVersion']:fail('HANDOVER_ALLOCATION_CHANGED','原物流分量版本已变化。')
        raw=number(item['quantity'],precision=ctx['unit'].decimal_places)
        leaves=list(Slice.objects.filter(root=alloc.root,status__in=('I','Q')).order_by('pk'))
        leaves=[s for s in leaves if s.data.get('legAllocationId')==alloc.pk]
        available=add(*(s.quantity for s in leaves));matched=min(raw,available);excess=add(raw,-matched)
        remain=matched;changes=[];old_short=Decimal(alloc.data.get('short','0'));short_consumed=Decimal(0)
        for leaf in leaves:
            if remain<=0:break
            part=min(remain,Decimal(leaf.quantity));bucket=leaf.status
            selected=split_slice(leaf,part,actor=actor,code=code,q=q,stamp=stamp,digest=digest,reason=reason,header=row,context=ctx)
            target_bucket='U' if row.target_workshop_id==alloc.root.task.workshop_id else 'S' if row.destination_kind=='storage' else 'V'
            transition(selected,target_bucket,actor=actor,code=code,q=q,reason=reason)
            project(selected,holder_workshop_id=row.target_workshop_id,holder_work_center_id=row.target_work_center_id,
                data={**selected.data,'receivedById':actor.pk,'receivedEmployeeId':employee,
                    'receivingOperationId':row.target_operation_id,'receivedLegId':row.pk,
                    'priorRangeReleaseIntentHash':selected.data.get('rangeReleaseIntentHash'),
                    'rangeReleaseIntentHash':None,'normalPurposeActive':False})
            if bucket=='Q':short_consumed=add(short_consumed,part)
            original_id=selected.data.get('originalUnreceivedAllocationId')
            if row.kind=='RETURN' and target_bucket=='U' and original_id:
                origin=Allocation.objects.select_related('handover','root__task').get(pk=original_id,company_id=actor.company_id)
                if (origin.root_id!=selected.root_id or origin.handover.source_work_center_id!=row.target_work_center_id
                    or Decimal(origin.data.get('short','0'))<part):
                    fail('HANDOVER_RETURN_ORIGIN_UNPROVEN','实物退回原未签范围或原来源中心不一致。')
                project(origin,data={**origin.data,'short':text(add(origin.data.get('short','0'),-part)),
                    'returnedBeforeReceipt':text(add(origin.data.get('returnedBeforeReceipt','0'),part))},version=origin.version+1)
                project(selected,data={**selected.data,'originalUnreceivedResolvedBy':row.pk})
                _refresh_status(origin.handover,actor,code,q,reason)
                _emit(actor,code,q,task,'RETURN_UNRECEIVED',part,'I','U',stamp,digest,reason,[],
                    header=origin.handover,allocation=origin,data={'returnHandoverId':row.pk,'returnedSliceId':selected.pk,
                        'effectiveOutputDelta':'0','originalReceivedDelta':'0','returnedBeforeReceiptDelta':text(part)})
                settle_short_exceptions(origin,actor=actor,code=code,q=q,reason=reason)
            remain=add(remain,-part);changes.append(selected)
        short_added=Decimal(0)
        if item['intent']=='scope_closed_short':
            for leaf in Slice.objects.filter(root=alloc.root,status='I').order_by('pk'):
                if leaf.data.get('legAllocationId')!=alloc.pk:continue
                transition(leaf,'Q',actor=actor,code=code,q=q,reason=reason);changes.append(leaf)
                short_added=add(short_added,leaf.quantity)
        data={**alloc.data,'received':text(add(alloc.data.get('received','0'),matched)),
            'short':text(add(old_short,-short_consumed,short_added)),
            'unmatched':text(add(alloc.data.get('unmatched','0'),excess))}
        project(alloc,data=data,version=alloc.version+1)
        if excess>0:
            initialize(ExceptionRecord,actor=actor,code=code,q=q,status='pending',
                source={'handoverId':row.pk,'allocationId':alloc.pk,'rawQuantity':text(raw),'matchedQuantity':text(matched)},
                intent_hash=digest,reason=reason,task=task,handover=row,allocation=alloc,kind='UNMATCHED_EXCESS',
                original_quantity=text(raw),quantity=text(excess),occurred_at=stamp,data={'rootId':alloc.root_id})
        project(row,receiver_employee_id=employee,data={**row.data,'lastReceivedAt':stamp.isoformat()})
        _refresh_status(row,actor,code,q,reason)
        event=_emit(actor,code,q,task,'RECEIVE',matched,'I/Q','U/S/V',stamp,digest,reason,changes,header=row,allocation=alloc,
            data={'rawReceivedQuantity':text(raw),'matchedQuantity':text(matched),'unmatchedQuantity':text(excess),
                'receiverEmployeeId':employee,'scopeIntent':item['intent']})
        settle_short_exceptions(alloc,actor=actor,code=code,q=q,reason=reason)
        if short_added>0:
            initialize(ExceptionRecord,actor=actor,code=code,q=q,status='pending',
                source={'handoverId':row.pk,'allocationId':alloc.pk,'difference':text(short_added),
                    'scopeRanges':[{'rootId':s.root_id,'startAtom':s.start_atom,'endAtom':s.end_atom}
                        for s in changes if s.status=='Q']},intent_hash=digest,
                reason=reason,task=task,handover=row,allocation=alloc,kind='SHORT',original_quantity=alloc.quantity,
                quantity=text(short_added),occurred_at=stamp,data={'rootId':alloc.root_id})
    bump(accounts[task.pk],'custody')
    commit_intent(actor,code,payload,digest,row,{'handoverId':row.pk,'taskId':task.pk,'status':row.status,
        'eventReference':f'OperationCustodyEvent:{event.pk}'})
    row._validated_output_context=ctx
    return row,True


def close_inputs_for_output(*,actor,ctx,output,inputs,accounts,code,q,stamp,digest,reason):
    if not isinstance(inputs,list) or not inputs:fail('OUTPUT_INPUT_PROOF_REQUIRED','须明确真实投入批次范围，不能仅凭已开工推断投入。')
    input_q=qualify(actor,ACTIONS['input.confirm'][0],ctx['task'].work_center_id,'OperationOutputEvidence',output.pk)
    if stamp>output.occurred_at:fail('OUTPUT_INPUT_AFTER_OUTPUT','实际投入不得晚于本新产出实际发生时点；记账补录时间另行保留，不能倒造物理先后。')
    changed_roots=set();output_ranges=[];output_hi=atoms(output.quantity,ctx['unit'].decimal_places)
    for item in inputs:
        span=item.get('outputRange') if isinstance(item,dict) else None
        if (not isinstance(span,dict) or set(span)!={'startAtom','endAtom'}
            or any(not isinstance(span[k],str) or not re.fullmatch(r'0|[1-9][0-9]*',span[k]) for k in span)):
            fail('OUTPUT_INPUT_MAPPING_REQUIRED','每项真实投入须明确对应本新产出的准确范围，不能以一份投入推定全批。',400)
        lo,hi=int(span['startAtom']),int(span['endAtom'])
        if not 0<=lo<hi<=output_hi:fail('OUTPUT_INPUT_MAPPING_EXCEEDED','投入关联的新产出范围超出本批。')
        output_ranges.append((lo,hi))
    cursor=0
    for lo,hi in sorted(output_ranges):
        if lo>cursor:fail('OUTPUT_INPUT_MAPPING_INCOMPLETE','本新产出范围仍有未闭合投入缺口，不能解除冻结。')
        cursor=max(cursor,hi)
    if cursor!=output_hi:fail('OUTPUT_INPUT_MAPPING_INCOMPLETE','投入关联尚未覆盖本批完整新产出范围。')
    for item in inputs:
        if not isinstance(item,dict) or set(item)!={'sliceId','expectedVersion','quantity','evidenceReference','outputRange'} or not str(item['evidenceReference']).strip():
            fail('OUTPUT_INPUT_SCOPE_INVALID','投入须提供真实份额、原版本、准确数量和实际执行范围依据。',400)
        strict_id(item['sliceId'],'投入份额');strict_id(item['expectedVersion'],'投入份额版本',zero=True)
        row=Slice.objects.select_related('root__task__source_operation').filter(pk=item['sliceId'],company_id=actor.company_id).first()
        if row and row.data.get('originalUnreceivedAllocationId') and not row.data.get('originalUnreceivedResolvedBy'):
            fail('OUTPUT_INPUT_UNRECEIVED_SOURCE_BLOCKED','原未签差额仅已定位，尚无正式补收、实回或处置，不得投入使原责任消失。')
        if (not row or row.status not in ('U','S','V') or row.version!=item['expectedVersion'] or row.reserved_by_id
            or row.frozen or row.holder_workshop_id!=ctx['task'].workshop_id
            or row.root.task.work_order_id!=ctx['task'].work_order_id
            or not is_upstream(row.root.task.source_operation,ctx['task'])):
            fail('OUTPUT_INPUT_SOURCE_UNPROVEN','投入来源、保管范围、工艺关系、版本或可支配状态不一致。')
        from .operation_handover_route import require_actual_receipt, validate_production_target
        validate_production_target(actor,row.root.task,ctx['task'].source_operation)
        require_actual_receipt(row,ctx['task'])
        basis=input_custody_basis(row,ctx['task'],actor)
        from django.utils.dateparse import parse_datetime
        available=parse_datetime(basis['availableAt'])
        occurred(offset_iso(stamp),not_before=available)
        source_ctx=task_context(row.root.task,actor);amount=number(item['quantity'],positive=True,precision=source_ctx['unit'].decimal_places)
        selected=split_slice(row,amount,actor=actor,code=code,q=q,stamp=stamp,digest=digest,reason=reason,context=source_ctx)
        old=selected.status
        transition(selected,'C',actor=actor,code=code,q=input_q,reason=reason)
        allocation=initialize(InputAllocation,actor=actor,code=code,q=input_q,status='confirmed',
            source={'sourceSliceId':selected.pk,'sourceHash':selected.source_snapshot_hash,'outputId':output.pk,
                'executionStartId':ctx['start'].pk,'evidenceReference':item['evidenceReference'],
                'outputRange':deepcopy(item['outputRange']),'outputUomId':output.uom_id,
                'sourceRangeReleaseProof':deepcopy(basis)},
            intent_hash=digest,reason=reason,source_slice=selected,output=output,execution_start=ctx['start'],
            quantity=selected.quantity,uom_id=selected.root.uom_id,start_atom=selected.start_atom,end_atom=selected.end_atom,
            data={'outputId':output.pk,'executionStartId':ctx['start'].pk,'evidenceReference':item['evidenceReference'],
                'outputRange':deepcopy(item['outputRange']),'outputUomId':output.uom_id})
        _emit(actor,code,input_q,selected.root.task,'INPUT_CLOSURE',selected.quantity,old,'C',stamp,digest,reason,[selected],
            data={'inputAllocationId':allocation.pk,'outputId':output.pk,'executionStartId':ctx['start'].pk})
        changed_roots.add(selected.root.task_id)
    output_slices=list(output.slices.exclude(status='closed'))
    audit_refs=[]
    for row in output_slices:
        if row.frozen:audit_refs.append({'sliceId':row.pk,'auditReference':audited_projection(row,actor=actor,
            code=code,q=input_q,reason=reason,frozen=False,version=row.version+1)})
    _emit(actor,code,input_q,ctx['task'],'INPUT_PROVEN',output.quantity,'F','',stamp,digest,reason,output_slices,
        data={'outputId':output.pk,'inputAllocationIds':list(output.input_allocations.values_list('pk',flat=True)),
            'projectionAudits':audit_refs,'subsetReleaseOnly':True,'effectiveOutputDelta':'0','custodyBucketDelta':'0'})
    for record in ExceptionRecord.objects.filter(task=ctx['task'],kind='INPUT_UNPROVEN',status='pending',data__outputId=output.pk):
        transition(record,'confirmed',actor=actor,code=code,q=input_q,reason=reason)
    for task_id in changed_roots:bump(accounts[task_id],'custody')


def _release_range(actor,payload,accounts):
    allowed=BASE|{'taskId','sourceWorkCenterId','expectedSourceSnapshotHash','expectedAccountSnapshotHash',
        'targetTaskId','targetOperationId','targetWorkCenterId','scopeReference','sliceAllocations'}
    payload_guard(payload,allowed,allowed-{'expectedAccountSnapshotHash','targetTaskId','targetOperationId'})
    for key in ('taskId','sourceWorkCenterId','targetWorkCenterId'):strict_id(payload[key],key)
    for key in ('targetTaskId','targetOperationId'):strict_id(payload.get(key),key,nullable=True)
    task=_task(actor,payload['taskId']);code=ACTIONS['range.release'][0]
    q=qualify(actor,code,payload['sourceWorkCenterId'],'ProductionWorkshopTask',task.pk,'open')
    digest,replay=intent(actor,code,None,payload)
    if replay:
        from .operation_handover_models import OperationCustodyEvent
        event=OperationCustodyEvent.objects.get(pk=replay.target_entity_id,company_id=actor.company_id)
        verify_record(event);verify_task_custody(task);return event,False
    ctx=task_context(task,actor);account=accounts[task.pk];bind_account(ctx,account)
    if payload['expectedSourceSnapshotHash']!=task.source_snapshot_hash:fail('HANDOVER_SOURCE_OR_ACCOUNT_CHANGED','原生产来源已变化。')
    if 'expectedAccountSnapshotHash' in payload:
        current=read_task_quantity_account(task,actor,context=ctx)
        if current.get('accountSnapshotHash')!=payload['expectedAccountSnapshotHash']:fail('HANDOVER_SOURCE_OR_ACCOUNT_CHANGED','当前范围或占用已变化，请保留意图只读重查。')
    from pde.models import WorkCenter
    center=WorkCenter.objects.select_related('workshop').filter(pk=payload['targetWorkCenterId'],company_id=actor.company_id,is_active=True,workshop__is_active=True).first()
    if not center:fail('OUTPUT_RANGE_RELEASE_TARGET_CHANGED','目标责任工作中心须为同公司当前有效正式资源。')
    source_center=WorkCenter.objects.filter(pk=payload['sourceWorkCenterId'],company_id=actor.company_id,
        is_active=True,workshop__is_active=True).first()
    if not source_center or source_center.workshop_id!=center.workshop_id:
        fail('OUTPUT_RANGE_RELEASE_SOURCE_WORKSHOP_CHANGED','当前Source责任中心与目标中心不在同一真实车间；旧范围证明不能跨车间释放，请先核查正式归属。')
    target=None;operation=None
    if payload.get('targetTaskId') is not None:
        target=_task(actor,payload['targetTaskId'])
        if (target.pk==task.pk or target.status!='dispatched' or target.work_order_id!=task.work_order_id or target.execution_mode!='QUANTIFIED'
            or target.source_operation_id!=payload.get('targetOperationId') or target.work_center_id!=center.pk
            or not is_upstream(task.source_operation,target)):
            fail('OUTPUT_RANGE_RELEASE_UNPROVEN','指定投入任务须为同工单明确正式后序、定量且已派工；不填造新任务。')
        from .test_workshop_task_service import verify as _verify_history
        _verify_history(target);operation=target.source_operation
    elif payload.get('targetOperationId') is not None:
        operation=task.work_order.operations.filter(pk=payload['targetOperationId']).first()
        if not operation:fail('OUTPUT_RANGE_RELEASE_TARGET_CHANGED','指定工序须为本工单真实正式工序。')
    if operation is not None:
        from .operation_handover_route import validate_production_target
        validate_production_target(actor,task,operation)
        current_target=resource_context(operation,actor)
        if current_target['workCenter'].pk!=center.pk:fail('OUTPUT_RANGE_RELEASE_TARGET_CHANGED','指定工序当前正式资源与目标责任中心不一致。')
    reference=payload['scopeReference']
    if not isinstance(reference,str) or not 2<=len(reference.strip())<=300:fail('OUTPUT_RANGE_RELEASE_REFERENCE_REQUIRED','须明确填写真实范围及用途依据。',400)
    selections=payload['sliceAllocations']
    if not isinstance(selections,list) or not selections:fail('HANDOVER_SLICES_REQUIRED','须明确选择当前负责人可支配的真实范围。',400)
    stamp=occurred(payload['occurredAt']);reason=payload['reason'].strip();changed=[];ranges=[];audits=[]
    target_data={'taskId':target.pk if target else None,'taskVersion':target.version if target else None,
        'taskSourceSnapshotHash':target.source_snapshot_hash if target else None,
        'operationId':operation.pk if operation else None,'workCenterId':center.pk,'workshopId':center.workshop_id,
        'scopeKind':'FORMAL_TASK_INPUT' if target else 'WORK_ORDER_WORK_CENTER_CUSTODY',
        'statusLabel':'指定真实投入任务范围' if target else '仅明确本工单本中心可支配责任，不代表任务／投产／实收或投入'}
    verify_task_custody(task)
    for item in selections:
        if not isinstance(item,dict) or set(item)!={'sliceId','expectedVersion','quantity'}:fail('HANDOVER_SLICE_INTENT_INVALID','范围释放只接受准确份额、原版本及数量。',400)
        strict_id(item['sliceId'],'释放份额');strict_id(item['expectedVersion'],'释放份额版本',zero=True)
        row=Slice.objects.select_related('root__task').filter(pk=item['sliceId'],company_id=actor.company_id,root__task=task).first()
        if (not row or row.version!=item['expectedVersion'] or row.status not in ('U','S','V') or row.frozen or row.reserved_by_id
            or custody_responsibility(row)!=payload['sourceWorkCenterId'] or row.holder_workshop_id!=center.workshop_id):
            fail('OUTPUT_RANGE_RELEASE_CUSTODY_UNPROVEN','仅本当前负责人真实在手、未占用冻结且同车间的准确范围可明确释放；跨车间须实际交接。',403)
        if row.data.get('originalUnreceivedAllocationId') and not row.data.get('originalUnreceivedResolvedBy'):
            fail('OUTPUT_RANGE_RELEASE_UNRECEIVED_BLOCKED','原未签定位范围未结清，不能改为投入用途。')
        evidence_proof(row.root,ctx)
        amount=number(item['quantity'],positive=True,precision=ctx['unit'].decimal_places)
        occurred(payload['occurredAt'],not_before=source_available_at(row))
        row=split_slice(row,amount,actor=actor,code=code,q=q,stamp=stamp,digest=digest,reason=reason,context=ctx)
        data={**row.data,'previousRangeReleaseIntentHash':row.data.get('rangeReleaseIntentHash'),
            'rangeReleaseIntentHash':digest,'normalPurposeActive':False,'inputPurpose':{**target_data,'reference':reference.strip()}}
        audits.append({'sliceId':row.pk,'auditReference':audited_projection(row,actor=actor,code=code,q=q,reason=reason,
            data=data,version=row.version+1)})
        changed.append(row);ranges.append({'sliceId':row.pk,'rootId':row.root_id,'rootSourceHash':row.root.source_snapshot_hash,
            'startAtom':row.start_atom,'endAtom':row.end_atom,'quantity':row.quantity,'uomId':row.root.uom_id,
            'previousResponsibleWorkCenterId':payload['sourceWorkCenterId'],'physicalHolderWorkCenterId':row.holder_work_center_id,
            'previousRangeReleaseIntentHash':row.data.get('previousRangeReleaseIntentHash')})
    event=_emit(actor,code,q,task,'RANGE_RELEASE',text(add(*(s.quantity for s in changed))),'','',stamp,digest,reason,changed,
        data={'rangeRelease':{'sourceWorkCenterId':payload['sourceWorkCenterId'],'target':target_data,
            'reference':reference.strip(),'ranges':ranges,'intentSliceIds':[i['sliceId'] for i in selections]},
            'projectionAudits':audits,'effectiveOutputDelta':'0'})
    bump(account,'release');bump(account,'custody')
    commit_intent(actor,code,payload,digest,event,{'taskId':task.pk,'originalObjectId':None,
        'outputIds':sorted({s.root_id for s in changed}),'sliceIds':[s.pk for s in changed],
        'eventReference':f'OperationCustodyEvent:{event.pk}'})
    return event,True


def execute_handover(*,user,action,payload,handover_id=None,exception_id=None):
    if action=='range.receive':
        from .operation_range_receipt_service import receive_range
        return receive_range(user=user,payload=payload)
    actor=actor_for(user)
    if action in ('exception.submit','exception.confirm','input.confirm'):
        from .operation_handover_exceptions import execute_exception
        return execute_exception(user=user,action=action,payload=payload,exception_id=exception_id)
    if action not in ('prepare','forward','return','dispatch','cancel','receive','range.release'):
        fail('HANDOVER_ACTION_INVALID','未注册的工序交接动作。',400)
    header=None
    if handover_id is not None:
        header=Handover.objects.select_related('target_operation__work_order','target_operation__effective_step').filter(pk=handover_id,company_id=actor.company_id).first()
        if not header:fail('HANDOVER_NOT_VISIBLE','未找到本公司正式交接单。',403)
    task_id=header.data['taskId'] if header else payload.get('taskId') if isinstance(payload,dict) else None
    task_ids=[task_id]
    sub=payload.get('outputConfirmation',{}) if isinstance(payload,dict) else {}
    ids=[i.get('sliceId') for i in sub.get('inputAllocations',[]) if isinstance(i,dict)]
    task_ids.extend(Slice.objects.filter(pk__in=ids,company_id=actor.company_id).values_list('root__task_id',flat=True))
    try:
        with transaction.atomic():
            accounts=lock_accounts(actor,task_ids)
            from .mes_test_source_bridge import allocation_admission_context
            from .operation_predecessor_authority import verification_context
            with allocation_admission_context(user=actor),verification_context():
                before=capture_counts()
                if handover_id is not None:header=Handover.objects.select_related('target_operation__work_order','target_operation__effective_step').get(pk=handover_id,company_id=actor.company_id)
                if action=='range.release':header,created=_release_range(actor,payload,accounts)
                elif action in ('prepare','forward','return'):header,created=_prepare(actor,payload,accounts,action)
                elif action in ('dispatch','cancel'):header,created=_dispatch_cancel(actor,header,payload,accounts,action)
                else:header,created=_receive(actor,header,payload,accounts)
                from .operation_handover_facts import read_operation_handovers
                facts=read_operation_handovers(user=actor,task_id=task_id,handover_id=header.pk if isinstance(header,Handover) else None,
                    custody_work_center_id=payload.get('sourceWorkCenterId') if action=='range.release' else None,
                    _context=getattr(header,'_validated_output_context',None))
                return facts,writes_since(before) if created else writes()
    except IntegrityError:
        fail('HANDOVER_RESULT_UNVERIFIED','数据库约束冲突，本次原意图结果待核实；请保留原请求标识只读核查，禁止重复提交。',503)
    except OperationalError:
        fail('HANDOVER_RESULT_UNVERIFIED','数据库暂不可用，本次原意图结果待核实；请保留原请求标识只读核查，禁止重复提交。',503)
