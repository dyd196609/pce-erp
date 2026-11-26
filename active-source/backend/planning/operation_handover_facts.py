"""Single native page facts for output authority and physical custody."""
from pde.routing_read_context import routing_read_phase
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from .operation_handover_core import (actor_for,qualify,verify_record,fail,_hash,text,atoms,from_atoms,strict_id,add)
from .operation_handover_models import (OperationOutputEvidence as Output,OperationCustodySlice as Slice,
    OperationHandover as Handover,OperationCustodyException as ExceptionRecord,OperationCustodyEvent)
from .operation_output_authority import task_context,evidence_proof,read_task_quantity_account
from .operation_output_authority import validated_task_context
from .operation_handover_authority import verify_handover,same_workshop_receipt_proven
from .operation_handover_contract import CONTRACT as HANDOVER_CONTRACT,ACTIONS as HANDOVER_ACTIONS,action_contract as handover_contract
from .operation_output_contract import CONTRACT as OUTPUT_CONTRACT,ACTIONS as OUTPUT_ACTIONS,action_contract as output_contract
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_resource_read_scope import scoped_execution_read
from .operation_route_facts import read_operation_route

BUCKET_LABELS={'U':'来源当前在手','S':'受托暂存','V':'生产去处已收','I':'明确在途','Q':'差额待核',
    'Z':'正式核定损失','C':'已核实投入转化','closed':'原份额已拆分或正式关闭'}
OUTPUT_LABELS={'declared':'超产已申报，待独立确认','confirmed':'产出依据已确认','rejected':'本次产出声明已拒绝'}


def _options(actor,work_order_id=None):
    from .mes_test_source_bridge import _rows
    rows=Task.objects.filter(company_id=actor.company_id,status='dispatched',work_order_id__in=_rows(actor).values_list('pk',flat=True)).select_related('work_order','source_operation','work_center','workshop')
    if work_order_id is not None:rows=rows.filter(work_order_id=work_order_id)
    from pde.capacity_evidence_read_scope import evidence_cache
    if evidence_cache(actor.company_id) is not None:
        from django.db.models import Prefetch
        from .work_order_models import ProductionWorkOrder

        # An order can carry many task rows and a large frozen snapshot. Read
        # each authorized order once for this result set.
        orders = ProductionWorkOrder.objects.filter(company_id=actor.company_id).select_related(
            'source_schedule','production_plan')
        rows = rows.select_related(None).select_related('source_operation__operation','work_center','workshop')
        rows = rows.prefetch_related(Prefetch('work_order', queryset=orders))
    return rows.order_by('work_order_id','source_operation__sequence','pk')


def _option_rows(actor, work_order_id=None):
    from .custody_dependency_reads import read_rows

    return read_rows('handover_task_rows', (actor.company_id, actor.pk, work_order_id),
        lambda: tuple(_options(actor, work_order_id)))


def _task_option(task):
    return {'id':task.pk,'taskId':task.pk,'taskNo':task.no,'workOrderId':task.work_order_id,'usagePurpose':task.work_order.usage_purpose,
        'workOrderNo':task.work_order.no,'operationId':task.source_operation_id,
        'operationName':task.source_operation.operation.name,'sequence':task.source_operation.sequence,
        'workCenterId':task.work_center_id,'workCenterName':task.work_center.name,
        'workshopId':task.workshop_id,'workshopName':task.workshop.name,'executionMode':task.execution_mode,
        'executionModeLabel':{'QUANTIFIED':'定量执行','NON_QUANTIFIED_REQUIRED':'仅经过，无统计数量','EXEMPT':'正式免执行'}.get(task.execution_mode,'执行模式待核实'),
        'quantityApplicable':task.execution_mode=='QUANTIFIED','directoryOnly':True,
        'qualificationEvaluated':False,'statusLabel':'正式已派任务；选择后读取当前数量与资格'}


def _custody_directory(actor,work_order_id=None,*,verify_custody=True):
    from .operation_handover_authority import verify_task_custody,custody_responsibility
    result=[];principal=None
    for task in _option_rows(actor,work_order_id):
        scopes={task.work_center_id}
        rows=list(Slice.objects.filter(root__task=task,status__in=('U','S','V')).select_related('root'))
        scopes.update(custody_responsibility(row) for row in rows)
        for header in Handover.objects.filter(company_id=actor.company_id,data__taskId=task.pk):
            scopes.update((header.source_work_center_id,header.target_work_center_id))
        range_history=list(OperationCustodyEvent.objects.filter(company_id=actor.company_id,
            task_id=task.pk,kind='RANGE_RELEASE'))
        for event in range_history:
            # Hints select an exact duty to evaluate; they do not grant access.
            # Retain historical receiver visibility after the input is consumed.
            release=event.data.get('rangeRelease',{})
            scopes.update((release.get('sourceWorkCenterId'),release.get('target',{}).get('workCenterId')))
        for wc in sorted(x for x in scopes if x):
            q=qualify(actor,HANDOVER_ACTIONS['read'][0],wc,'ProductionWorkshopTask',task.pk,required=False)
            if q['ready']:
                # Candidate scope hints grant nothing: validate its complete
                # ledger only after the caller qualifies for that exact WC.
                if verify_custody and (rows or range_history):verify_task_custody(task)
                principal=principal or q
                result.append({**_task_option(task),'statusLabel':'当前授权责任或正式工单来源轻目录；选择后独立验真数量及资格'})
                break
    return result,principal


def _action(actor,key,*,output=False,wc=None,object_id=None,status='open',extra=()):
    actions=OUTPUT_ACTIONS if output else HANDOVER_ACTIONS
    code=actions[key][0];contract=(output_contract if output else handover_contract)(key,object_id)
    q=qualify(actor,code,wc,'OperationOutputEvidence' if output else 'OperationHandover',object_id,status,required=False)
    missing=q['missingItems'][:]+list(extra)
    if contract['apiPath'] is None:missing.append('请选择准确正式对象后办理。')
    return {**contract,'enabled':not missing,'disabledReason':'；'.join(missing),'qualification':q,
        'requestObjectId':object_id}


def _coverage_options(ctx):
    from .operation_handover_models import OperationOutputAllocation
    result=[]
    for record in ctx['records']:
        hi=atoms(record['quantity'],ctx['unit'].decimal_places);cursor=0
        rows=OperationOutputAllocation.objects.filter(report_id=record['id'],evidence__status='confirmed',coverage_kind='RELEASE')
        intervals=sorted((int(r.start_atom),int(r.end_atom)) for r in rows)
        for lo,end in intervals+[(hi,hi)]:
            if lo<cursor:fail('OUTPUT_REPORT_DOUBLE_RELEASE','报工分量重复，不能构造可用范围。')
            if lo>cursor:result.append({'reportId':record['id'],'startAtom':str(cursor),'endAtom':str(lo),
                'quantity':text(from_atoms(lo-cursor,ctx['unit'].decimal_places)),
                'quantityPrecision':ctx['unit'].decimal_places,'uomId':ctx['unit'].pk,
                'statusLabel':'经正式报工验真，尚未定位释放','reportProofHash':_hash(record)})
            cursor=end
    return result


def _output(row,ctx):
    return {'id':row.pk,'outputId':row.pk,'taskId':row.task_id,'kind':row.kind,
        'kindLabel':{'NORMAL_CONFIRM':'正常报工分量确认','WHOLE_RELEASE':'已独审产量定位，不重复增产','EXCESS_REPORT':'超计划补充报工','OUTPUT_CORRECTION':'产出关联调减，不是新增产量'}[row.kind],
        'quantity':row.quantity,'uomId':row.uom_id,'batchLabel':row.batch_label,'scopeManifest':row.scope_manifest,
        'statusCode':row.status,'statusLabel':OUTPUT_LABELS[row.status],'version':row.version,
        'sourceSnapshotHash':row.source_snapshot_hash,'occurredAt':row.occurred_at.isoformat(),
        'createdById':row.created_by_id,'declarerEmployeeId':row.qualification_snapshot.get('currentActorEvidence',{}).get('employeeId'),
        'reviewerRoleCode':row.approval_task.required_role_code if row.approval_task_id else None,
        'businessTimezone':'Asia/Shanghai','workflowInstanceId':row.workflow_id,
        'workflowVersion':row.workflow.version if row.workflow_id else None,
        'approvalTaskId':row.approval_task_id,'approvalTaskVersion':row.approval_task.version if row.approval_task_id else None,
        'approvalDecisionId':row.approval_decision_id,'proof':evidence_proof(row,ctx),
        'reviewExpectations':{'expectedVersion':row.version,'expectedSourceSnapshotHash':row.source_snapshot_hash,
            'expectedWorkflowVersion':row.workflow.version if row.workflow_id else None,
            'expectedApprovalTaskVersion':row.approval_task.version if row.approval_task_id else None}}


def _slices(task):
    from .operation_handover_authority import custody_responsibility
    from pde.models import WorkCenter
    result=[]
    for row in Slice.objects.filter(root__task_id=task.pk).exclude(status='closed').select_related('root','holder_work_center','holder_workshop'):
        history=verify_record(row)
        responsible=custody_responsibility(row)
        responsible_center=WorkCenter.objects.filter(pk=responsible,company_id=task.company_id).first() if responsible else None
        result.append({'id':row.pk,'sliceId':row.pk,'outputId':row.root_id,'taskId':task.pk,
            'batchLabel':row.root.batch_label,'scopeManifest':row.root.scope_manifest,
            'quantity':row.quantity,'uomId':row.root.uom_id,'version':row.version,'bucket':row.status,
            'statusCode':row.status,'statusLabel':BUCKET_LABELS[row.status],
            'holderWorkCenterId':row.holder_work_center_id,'holderWorkCenterName':row.holder_work_center.name if row.holder_work_center_id else None,
            'currentResponsibilityWorkCenterId':responsible,'currentResponsibilityWorkCenterName':responsible_center.name if responsible_center else None,
            'responsibilityBasisLabel':'正式Source范围释放／用途与真实收讫事件确定的当前唯一可支配责任；物理保管记录另列',
            'holderWorkshopId':row.holder_workshop_id,'holderWorkshopName':row.holder_workshop.name if row.holder_workshop_id else None,
            'reservedById':row.reserved_by_id,'frozen':row.frozen,
            'available':row.status in ('U','S','V') and not row.reserved_by_id and not row.frozen,
            'unreceivedScopeUnresolved':bool(row.data.get('originalUnreceivedAllocationId') and not row.data.get('originalUnreceivedResolvedBy')),
            'availableForForward':(row.status in ('S','V') or same_workshop_receipt_proven(row)) and not row.reserved_by_id and not row.frozen and not (row.data.get('originalUnreceivedAllocationId') and not row.data.get('originalUnreceivedResolvedBy')),
            'availableForReturn':(row.status in ('S','V') or same_workshop_receipt_proven(row)) and not row.reserved_by_id and not row.frozen,
            'inputPurpose':row.root.scope_manifest.get('inputPurpose'),'sourceSnapshotHash':row.source_snapshot_hash,**history})
    return result


@routing_read_phase("assembly")
def _header(row, *, directory=False):
    from .operation_handover_service import LABELS
    proof=verify_handover(row, include_task_custody=not directory);raw=Decimal(0);original_matched=Decimal(0);raw_x=Decimal(0);corrections=[]
    first=row.allocations.select_related('uom').first()
    source_task=Task.objects.select_related('work_order','source_operation__operation').get(pk=row.data['taskId'],company_id=row.company_id)
    sender=None;receipts=[];dispatches=[]
    current_held=Decimal(0)
    if not directory:
        for leaf in Slice.objects.filter(root__task=source_task,status__in=('U','S','V'),holder_work_center_id=row.target_work_center_id):
            if leaf.data.get('receivedLegId')==row.pk and (leaf.status!='U' or same_workshop_receipt_proven(leaf)):
                current_held=add(current_held,leaf.quantity)
    events = list(OperationCustodyEvent.objects.filter(handover=row).order_by('pk'))
    if directory:
        # List rows verify the leg and its own original events. The detailed
        # custody/account projection is read only when its detail is opened.
        from .operation_handover_authority import event_payload
        from .operation_handover_core import record_proof_batch
        event_proofs = record_proof_batch(events)
        for event in events:
            verify_record(event, proof_batch=event_proofs)
            payload = event_payload(event)
            if (event.company_id != row.company_id or event.task_id != source_task.pk
                    or event.source_snapshot != payload or event.event_hash != _hash(payload)):
                fail('CUSTODY_EVENT_CHAIN_UNPROVEN', '交接事件与原单依据不一致。')
    for event in events:
        historical_actor=event.qualification_snapshot.get('currentActorEvidence',{})
        if event.kind=='DISPATCH':
            sender=historical_actor
            dispatches.append({'eventId':event.pk,'eventHash':event.event_hash,'occurredAt':event.occurred_at.isoformat(),
                'employeeId':historical_actor.get('employeeId'),'employeeName':historical_actor.get('employeeName'),
                'quantity':event.quantity,'uomLabel':first.uom.name})
        if event.kind=='RECEIVE':
            receipts.append({'eventId':event.pk,'eventHash':event.event_hash,'occurredAt':event.occurred_at.isoformat(),
                'employeeId':historical_actor.get('employeeId'),'employeeName':historical_actor.get('employeeName'),
                'username':historical_actor.get('username'),'rawQuantity':event.data.get('rawReceivedQuantity'),
                'matchedQuantity':event.data.get('matchedQuantity'),'uomLabel':first.uom.name})
            raw=add(raw,event.data.get('rawReceivedQuantity','0'))
            original_matched=add(original_matched,event.data.get('matchedQuantity','0'))
            raw_x=add(raw_x,event.data.get('unmatchedQuantity','0'))
        if event.kind=='EXCEPTION_RESOLVE' and event.debit=='RECEIPT_CORRECTION':
            corrections.append({'eventId':event.pk,'eventHash':event.event_hash,'exceptionId':event.data.get('exceptionId'),
                'quantity':event.quantity,'occurredAt':event.occurred_at.isoformat()})
    receiver=receipts[-1] if receipts else None
    if sender and sender.get('employeeId')!=row.sender_employee_id:fail('HANDOVER_PARTY_PROOF_MISMATCH','交出人与正式交出事件不一致。')
    if receiver and receiver.get('employeeId')!=row.receiver_employee_id:fail('HANDOVER_PARTY_PROOF_MISMATCH','接收人与正式实收事件不一致。')
    from .work_order_models import ProductionWorkOrderOperation
    target_operation=ProductionWorkOrderOperation.objects.select_related('operation').filter(pk=row.target_operation_id,work_order=source_task.work_order).first() if row.target_operation_id else None
    if row.target_operation_id and (not target_operation or row.source_snapshot.get('target',{}).get('operationId')!=row.target_operation_id):
        fail('HANDOVER_OPERATION_PROOF_MISMATCH','交接目标工序与原工单冻结关系不一致。')
    from .operation_handover_number import read_number
    from .operation_handover_route import historical_route_review
    return {**read_number(row),**historical_route_review(row,source_task),'workOrderId':source_task.work_order_id,'workOrderNo':source_task.work_order.no,
        'sourceTaskNo':source_task.no,'sourceOperationId':source_task.source_operation_id,
        'sourceOperationName':source_task.source_operation.source_snapshot.get('operationName') or source_task.source_operation.operation.name,
        'targetOperationName':(target_operation.source_snapshot.get('operationName') or target_operation.operation.name) if target_operation else '未指定生产工序（按原去处）',
        'sourceWorkshopName':sender.get('workshopName') if sender else row.source_work_center.workshop.name,
        'targetWorkshopName':OperationCustodyEvent.objects.filter(handover=row,kind='RECEIVE').order_by('-pk').first().qualification_snapshot.get('currentActorEvidence',{}).get('workshopName') if receiver else row.target_work_center.workshop.name,
        'historicalSender':sender,'historicalReceipts':receipts,'historicalReceiver':receiver,
        'historicalDispatches':dispatches,'historicalRecordReadStatus':'loaded',
        'currentTargetHeldQuantity':None if directory else text(current_held),
        'receiptStateLabel':('历史交接已全部接收（本单已收齐）；当前在手另列' if row.status=='received' and Decimal(proof['sentQuantity'])>0 and proof['sentQuantity']==proof['receivedQuantity'] else LABELS[row.status]),
        'receiptStateExplanation':'历史实收取本物流腿正式接收及关联更正事实；当前目标在手仅取本腿仍在目标中心的未封闭份额。投入、转送或退回后在手可为0，不撤销历史接收。',
        'id':row.pk,'handoverId':row.pk,'no':row.no,'kind':row.kind,'taskId':row.data['taskId'],
        'sourceWorkCenterId':row.source_work_center_id,'sourceWorkCenterName':row.source_work_center.name,
        'targetWorkCenterId':row.target_work_center_id,'targetWorkCenterName':row.target_work_center.name,
        'sourceWorkshopId':row.source_workshop_id,'targetWorkshopId':row.target_workshop_id,
        'targetOperationId':row.target_operation_id,'destinationKind':row.destination_kind,
        'destinationKindLabel':'受托暂存' if row.destination_kind=='storage' else '正式生产去处',
        'destinationReference':row.destination_reference,'statusCode':row.status,'statusLabel':LABELS[row.status],
        'version':row.version,'sourceSnapshotHash':row.source_snapshot_hash,
        'uomId':first.uom_id if first else None,'uomLabel':first.uom.name if first else None,
        'senderEmployeeId':row.sender_employee_id,'receiverEmployeeId':row.receiver_employee_id,
        'senderEmployeeName':sender.get('employeeName') if sender else None,
        'receiverEmployeeName':receiver.get('employeeName') if receiver else None,
        'dispatchedAt':row.dispatched_at.isoformat() if row.dispatched_at else None,
        'lastReceivedAt':row.data.get('lastReceivedAt'),'businessTimezone':'Asia/Shanghai',
        'targetPlanSummary':row.source_snapshot.get('target',{}).get('targetPlanSummary'),
        'rawDeclaredReceiveQuantity':text(raw),'originalMatchedReceiveQuantity':text(original_matched),
        'originalUnmatchedReceiveQuantity':text(raw_x),'correctedMatchedReceiveQuantity':proof['receivedQuantity'],
        'declaredToMatchedDifferenceQuantity':text(add(raw,-Decimal(proof['receivedQuantity']))),
        'receiptDifferenceQuantity':text(add(proof['inTransitQuantity'],proof['shortQuantity'])),
        'receiptCorrectionReferences':corrections,
        'receiptMetricBasisLabel':'本单历史净匹配实收（关联更正后）与当前目标在手分别列示；在途、待核与超收另列，不以在手0推定未接收',
        'expectations':{'expectedVersion':row.version,'expectedSourceSnapshotHash':row.source_snapshot_hash},
        'allocations':[{'id':a.pk,'allocationId':a.pk,'sliceId':a.source_slice_id,'outputId':a.root_id,
            'quantity':a.quantity,'uomId':a.uom_id,'uomLabel':a.uom.name,'batchLabel':a.root.batch_label,
            'scopeManifest':a.root.scope_manifest,'version':a.version,'sourceSnapshotHash':a.source_snapshot_hash,
            'receivedQuantity':a.data.get('received','0'),'shortQuantity':a.data.get('short','0'),
            'unmatchedQuantity':a.data.get('unmatched','0'),'statusLabel':'物流腿原份额及正式收讫余额',
            **verify_record(a)} for a in row.allocations.select_related('uom','root').order_by('pk')],**proof}


def _exception(row):
    progress={}
    if row.kind=='SHORT':
        from .operation_handover_authority import short_resolution
        progress=short_resolution(row)
    elif row.kind=='UNMATCHED_EXCESS':
        from .operation_handover_authority import unmatched_resolution
        progress=unmatched_resolution(row)
    proposal=bool(row.workflow_id and row.approval_task_id)
    from .operation_handover_authority import custody_responsibility
    responsible=custody_responsibility(row.slice) if row.slice_id else None
    return {'id':row.pk,'exceptionId':row.pk,'taskId':row.task_id,'handoverId':row.handover_id,
        'allocationId':row.allocation_id,'sliceId':row.slice_id,'kind':row.kind,'quantity':row.quantity,
        'kindLabel':{'SHORT':'明确短收待核','UNMATCHED_EXCESS':'原实收超出已知来源','LOSS':'实物损失核定','LOCATE_SHORT':'未签范围实际保管定位',
            'RECEIPT_CORRECTION':'原实收关联更正','OUTPUT_CORRECTION':'产出真实性关联更正','UNMATCHED_CLAIM':'多收真实来源匹配','INPUT_UNPROVEN':'新产出投入范围待核'}[row.kind],
        'occurredAt':row.occurred_at.isoformat(),'businessTimezone':'Asia/Shanghai',
        'originalQuantity':row.original_quantity,'statusCode':row.status,
        'statusLabel':({'pending':'原观察事实待核，须另建准确处置或完成真实范围闭合','confirmed':'原观察已依正式事件结清','rejected':'原观察本次处置已拒绝'} if not proposal else
            {'pending':'正式关联处置待独审','confirmed':'关联处置已独立确认','rejected':'本次处置已独立拒绝'})[row.status],
        'independentReviewApplicable':proposal,'currentResponsibilityWorkCenterId':responsible,
        'sourceProductionWorkCenterId':row.task.work_center_id,
        'productionDecreaseScopeReady':bool(row.kind=='OUTPUT_CORRECTION' and row.slice_id and row.slice.status=='U' and responsible==row.task.work_center_id),
        'version':row.version,'sourceSnapshotHash':row.source_snapshot_hash,'data':row.data,
        'workflowInstanceId':row.workflow_id,'workflowVersion':row.workflow.version if row.workflow_id else None,
        'approvalTaskVersion':row.approval_task.version if row.approval_task_id else None,**verify_record(row),**progress}


def result_recovery(actor,action,request_hash,key_hash,*,task_id=None,output_id=None,handover_id=None,exception_id=None,slice_id=None):
    from masterdata.models import MasterDataWriteRequest
    result={'status':'unknown','actionCode':action,'requestHash':request_hash,'requestKeyHash':key_hash,
        'statusLabel':'原动作结果仍待核实；请勿重复提交','proofReference':None}
    if not action and not request_hash and not key_hash:return None
    allowed={x[0] for x in HANDOVER_ACTIONS.values()}|{x[0] for x in OUTPUT_ACTIONS.values()}
    if action not in allowed or not all(isinstance(x,str) and len(x)==64 for x in (request_hash,key_hash)):return result
    rows=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=action,
        request_hash=request_hash,status='COMMITTED',audit_metadata__actorId=actor.pk).select_related('source_identity')
    matched=[r for r in rows if sha256(r.idempotency_key.encode()).hexdigest()==key_hash]
    if len(matched)!=1:return result
    ledger=matched[0];identity=ledger.source_identity
    if (identity.organization_id!=actor.company_id or identity.mapping_status!='MATCH'
        or identity.source_fingerprint!=request_hash or identity.target_entity_type!=ledger.entity_type
        or identity.target_entity_id!=ledger.target_entity_id):return result
    range_receipt=(ledger.entity_type=='OperationCustodyEvent' and action=='production.operation.handover.receive' and ledger.result.get('releaseEventId'))
    if task_id is not None and ledger.result.get('taskId')!=task_id and not range_receipt:return result
    models={'OperationOutputEvidence':Output,'OperationHandover':Handover,'OperationCustodyException':ExceptionRecord,
        'OperationCustodyEvent':OperationCustodyEvent}
    model=models.get(ledger.entity_type)
    if model is None:return result
    row=model.objects.filter(pk=ledger.target_entity_id,company_id=actor.company_id).first()
    if not row:return result
    actual_task_id=row.data.get('taskId') if isinstance(row,Handover) else row.task_id
    if task_id is not None and actual_task_id!=task_id:return result
    if ledger.entity_type=='OperationHandover':
        verify_handover(row)
        if handover_id is not None:
            create=action in {'production.operation.handover.prepare','production.operation.handover.forward','production.operation.handover.return'}
            members=ledger.result.get('handoverIds',[row.pk]) if create else [row.pk]
            if handover_id not in members:return result
            member=Handover.objects.filter(pk=handover_id,company_id=actor.company_id).first()
            if not member or member.data.get('taskId')!=actual_task_id:return result
            verify_handover(member)
            if create and (member.intent_hash!=request_hash or member.created_by_id!=actor.pk):return result
            row=member
    elif ledger.entity_type=='OperationOutputEvidence':
        evidence_proof(row)
        if output_id is not None and action.endswith(('excess.review','input.confirm')) and row.pk!=output_id:return result
    elif ledger.entity_type=='OperationCustodyException':
        verify_record(row)
        if exception_id is not None and row.pk!=exception_id:return result
        if output_id is not None and action.endswith('output.correct') and row.data.get('outputId')!=output_id:return result
    else:
        verify_record(row)
        from .operation_handover_authority import verify_task_custody
        allowed_pair=(action=='production.operation.handover.range.release' and row.kind=='RANGE_RELEASE') or (range_receipt and row.kind=='RANGE_RECEIVED' and row.data.get('releaseEventId')==ledger.result.get('releaseEventId'))
        if not allowed_pair or row.intent_hash!=request_hash:return result
        if output_id is not None and output_id not in ledger.result.get('outputIds',[]):return result
        if slice_id is not None and slice_id not in row.data.get('rangeRelease',{}).get('intentSliceIds',[]):return result
        verify_task_custody(row.task)
    reference=ledger.result.get('eventReference')
    if reference:
        import re
        match=re.fullmatch(r'OperationCustodyEvent:([1-9][0-9]*)',reference) if isinstance(reference,str) else None
        if not match:return result
        event=OperationCustodyEvent.objects.filter(pk=int(match[1]),company_id=actor.company_id).first()
        if not event or event.intent_hash!=request_hash or event.created_by_id!=actor.pk:return result
        verify_record(event)
    else:
        if action.endswith('excess.review'):
            if not row.approval_decision_id or row.approval_decision.decision_hash!=request_hash or row.approval_decision.actor_id!=actor.pk:return result
            reference=f'ApprovalDecision:{row.approval_decision_id}'
        elif row.intent_hash==request_hash:
            reference=f'{type(row).__name__}:{row.pk}'
        else:
            from workflow_runtime.models import BusinessStateTransition
            events=BusinessStateTransition.objects.filter(object_type=type(row).__name__,object_id=row.pk,
                action_code=action,operator_id=actor.pk).order_by('-pk')
            if not events.exists():return result
            reference=events.first().audit_reference
    create_codes={'production.operation.output.confirm','production.operation.output.excess.report',
        'production.operation.handover.prepare','production.operation.handover.forward','production.operation.handover.return'}
    create_codes.add('production.operation.handover.range.release')
    original_id=ledger.result.get('originalObjectId',None if action in create_codes else row.pk)
    if range_receipt:original_id=row.data['releaseEventId']
    return {**result,'status':'verified','objectType':type(row).__name__,'objectId':original_id,'resultObjectId':row.pk,
        'proofReference':reference,'statusLabel':'对应原动作的正式结果已独立回读核实'}


@scoped_execution_read
def read_operation_outputs(*,user,task_id=None,output_id=None,work_order_id=None,recovery_action=None,request_hash=None,request_key_hash=None,direction='outgoing',_context=None):
    for value in (task_id,output_id,work_order_id):strict_id(value,'读取定位',nullable=True)
    actor=actor_for(user)
    task=None
    if output_id is not None:
        output=Output.objects.filter(pk=output_id,company_id=actor.company_id).first()
        if not output:fail('OUTPUT_NOT_VISIBLE','未找到本公司正式产出记录。',403)
        if task_id is not None and task_id!=output.task_id:fail('OUTPUT_QUERY_OBJECT_MISMATCH','产出与所选任务不一致。',400)
        task_id=output.task_id
    if task_id is not None:
        task=_options(actor,work_order_id).filter(pk=task_id).first()
        if not task:fail('OUTPUT_TASK_NOT_VISIBLE','所选任务不在本公司当前读取范围。',403)
    q=qualify(actor,OUTPUT_ACTIONS['read'][0],task.work_center_id if task else None,'ProductionWorkshopTask',task_id,required=True)
    options=[]
    for row in _option_rows(actor,work_order_id):
        if qualify(actor,OUTPUT_ACTIONS['read'][0],row.work_center_id,'ProductionWorkshopTask',row.pk,required=False)['ready']:
            options.append(_task_option(row))
    ctx=validated_task_context(task,actor,_context) if task else None
    account=read_task_quantity_account(task,actor,context=ctx) if task else None
    outputs=[_output(r,ctx) for r in Output.objects.filter(task_id=task_id).select_related('workflow','approval_task').order_by('pk')] if task else []
    selected=next((o for o in outputs if o['id']==output_id),None)
    issues=(account.get('blockingReasons',[]) if account else ['请选择真实来源任务。'])
    if task and not ctx['quantified']:issues=issues+['本任务无投产统计量；请明确选择原合法定量来源批次办理物流。']
    wc=task.work_center_id if task else None
    actions={key:_action(actor,key,output=True,wc=wc,object_id=output_id if key=='excess.review' else None,
        status=selected['statusCode'] if selected and key=='excess.review' else 'open',
        extra=issues if key in ('confirm','excess.report') else ([] if selected else ['请选择准确产出声明。']))
        for key in ('confirm','excess.report','excess.review','correct')}
    if selected and selected['statusCode']!='declared':
        actions['excess.review'].update(enabled=False,disabledReason='本声明不在待独立确认状态。')
    if selected and (selected['createdById']==actor.pk or selected['declarerEmployeeId']==q['currentActorEvidence'].get('employeeId')):
        actions['excess.review'].update(enabled=False,disabledReason='申请人与审核人须为不同真实员工。')
    if task and (not ctx['start'] or ctx['start'].started_by_id!=actor.pk or task.assignment_snapshot.get('userId')!=actor.pk):
        actions['excess.report'].update(enabled=False,disabledReason='须由原任务冻结执行人及实际开工人本人申报。')
    elif task and ctx['quantified'] and actions['excess.report']['enabled']:
        from .operation_output_authority import reporter_authority
        authority=reporter_authority(ctx,actor)
        if not authority['ready']:actions['excess.report'].update(enabled=False,disabledReason='；'.join(authority['missingItems']))
    if task:
        actions['excess.review']['approvalReady']=bool(ctx['quantified'] and ctx['R']==ctx['P'])
        actions['excess.review']['approvalDisabledReason']='' if actions['excess.review']['approvalReady'] else '原正常报工尚未达到P，仅可核查或明确拒绝，不能确认超产。'
    expectations=({'taskId':task.pk,'expectedVersion':task.version,'expectedSourceSnapshotHash':task.source_snapshot_hash,
        'expectedAssignmentHash':task.assignment_hash,'expectedStartId':ctx['start'].pk if ctx['start'] else None,
        'expectedStartSnapshotHash':ctx['snapshot'].get('startSnapshotHash'),'expectedReleaseRevision':account.get('releaseRevision'),
        'expectedProductionRevision':account.get('productionRevision'),'uomId':task.workload_uom_id} if task else None)
    return {'contractVersion':OUTPUT_CONTRACT,'moduleCode':'production-operation-output','factSource':'server','currentStateSource':'server',
        'usagePurpose':task.work_order.usage_purpose if task else 'MIXED_AUTHORIZED','purposeLabel':('正式生产用途来源（独立开发测试环境）' if task and task.work_order.usage_purpose=='PRODUCTION_USE' else '隔离测试用途；批次、数量及办理账号沿真实TEST来源追溯'),
        'companyId':actor.company_id,'currentActorEvidence':q['currentActorEvidence'],'taskOptions':options,
        'outputs':outputs,'selectedOutput':selected,'selectedTask':None if not task else {**_task_option(task),'directoryOnly':False,
            'qualificationEvaluated':True,'expectations':expectations,'reports':ctx['records'],
            'reportCoverageOptions':_coverage_options(ctx) if ctx['quantified'] else []},
        'quantityAccounts':[account] if account else [],'selectedQuantityAccount':account,
        'slices':_slices(task) if task else [],'qualification':q,'availableActions':actions,
        'detailFactsIncluded':bool(task),'statusLabel':'当前正式产出及数量事实已读取' if task else '正式任务目录已读取，请选择来源任务',
        'resultRecovery':result_recovery(actor,recovery_action,request_hash,request_key_hash,task_id=task_id,output_id=output_id),
        'businessWriteCount':0,'auditWriteCount':0,'actualStartCount':0,'actualReportCount':0,'inventoryUpdatedCount':0}


@scoped_execution_read
def read_operation_handovers(*,user,task_id=None,handover_id=None,work_order_id=None,output_id=None,exception_id=None,slice_id=None,custody_work_center_id=None,recovery_action=None,request_hash=None,request_key_hash=None,direction='outgoing',_context=None,_selected_detail=False):
    for value in (task_id,handover_id,work_order_id,output_id,exception_id,slice_id,custody_work_center_id):strict_id(value,'读取定位',nullable=True)
    if direction not in ('incoming','outgoing'):fail('HANDOVER_QUERY_INVALID','交接读取方向须为接收上游或交出下游。',400)
    if direction=='incoming':
        if any(x is not None for x in (output_id,exception_id,slice_id,custody_work_center_id,recovery_action,request_hash,request_key_hash)):
            fail('HANDOVER_QUERY_OBJECT_MISMATCH','上游接收历史只接受本任务、工单及准确交接单定位。',400)
        return _read_incoming(user,task_id,work_order_id,handover_id,_context,_selected_detail)
    actor=actor_for(user);selected_row=None
    if slice_id is not None:
        selected_slice=Slice.objects.select_related('root').filter(pk=slice_id,company_id=actor.company_id).first()
        if not selected_slice:fail('HANDOVER_SLICE_NOT_VISIBLE','所选份额不在本公司正式范围。',403)
        if task_id is not None and task_id!=selected_slice.root.task_id:fail('HANDOVER_QUERY_OBJECT_MISMATCH','份额与来源任务不一致。',400)
        if output_id is not None and output_id!=selected_slice.root_id:fail('HANDOVER_QUERY_OBJECT_MISMATCH','份额与所选原产出root不一致。',400)
        task_id=selected_slice.root.task_id
    if output_id is not None:
        selected_output=Output.objects.filter(pk=output_id,company_id=actor.company_id).first()
        if not selected_output:fail('OUTPUT_NOT_VISIBLE','未找到本公司正式产出对象。',403)
        if task_id is not None and task_id!=selected_output.task_id:fail('OUTPUT_QUERY_OBJECT_MISMATCH','所选产出与来源任务冲突。',400)
        task_id=selected_output.task_id
    if exception_id is not None:
        selected_exception=ExceptionRecord.objects.filter(pk=exception_id,company_id=actor.company_id).first()
        if not selected_exception:fail('HANDOVER_EXCEPTION_NOT_VISIBLE','未找到本公司正式异常对象。',403)
        if task_id is not None and task_id!=selected_exception.task_id:fail('HANDOVER_QUERY_OBJECT_MISMATCH','所选异常与来源任务冲突。',400)
        task_id=selected_exception.task_id
    if handover_id is not None:
        selected_row=Handover.objects.filter(pk=handover_id,company_id=actor.company_id).first()
        if not selected_row:fail('HANDOVER_NOT_VISIBLE','未找到本公司正式交接单。',403)
        if task_id is not None and selected_row.data['taskId']!=task_id:fail('HANDOVER_QUERY_OBJECT_MISMATCH','交接单与所选来源任务不一致。',400)
        task_id=selected_row.data['taskId']
    task=_options(actor,work_order_id).filter(pk=task_id).first() if task_id is not None else None
    if task_id is not None and not task:fail('HANDOVER_TASK_NOT_VISIBLE','来源任务不在当前公司及工单范围。',403)
    from .operation_handover_authority import verify_task_custody,is_upstream,custody_responsibility
    known_custody=set(Slice.objects.filter(root__task_id=task_id,status__in=('U','S','V')).exclude(holder_work_center=None).values_list('holder_work_center_id',flat=True)) if task else set()
    if task:known_custody.add(task.work_center_id)
    if task:
        for row in Slice.objects.filter(root__task=task,status__in=('U','S','V')).select_related('root'):
            responsible=custody_responsibility(row)
            if responsible:known_custody.add(responsible)
    for event in OperationCustodyEvent.objects.filter(company_id=actor.company_id,task_id=task_id,kind='RANGE_RELEASE'):
        verify_record(event)
        known_custody.update((event.data['rangeRelease']['sourceWorkCenterId'],event.data['rangeRelease']['target']['workCenterId']))
    if selected_row:
        verify_handover(selected_row)
        known_custody.update((selected_row.source_work_center_id,selected_row.target_work_center_id))
    if custody_work_center_id is not None and custody_work_center_id not in known_custody:
        fail('HANDOVER_CUSTODY_CONTEXT_UNPROVEN','所选中心不是该真实来源的现保管范围或原生产来源。',403)
    read_wc=custody_work_center_id or (selected_row.source_work_center_id if selected_row else task.work_center_id if task else None)
    q=qualify(actor,HANDOVER_ACTIONS['read'][0],read_wc,'OperationHandover',handover_id,required=False)
    if not q['ready'] and selected_row and custody_work_center_id is None:
        for wc in (selected_row.source_work_center_id,selected_row.target_work_center_id):
            q=qualify(actor,HANDOVER_ACTIONS['read'][0],wc,'OperationHandover',handover_id,required=False)
            if q['ready']:break
    if not q['ready'] and task and custody_work_center_id is None:
        for wc in sorted(x for x in known_custody if x):
            candidate=qualify(actor,HANDOVER_ACTIONS['read'][0],wc,'ProductionWorkshopTask',task.pk,required=False)
            if candidate['ready']:q=candidate;read_wc=wc;break
    directory_options=[]
    if task is None:
        directory_options,principal=_custody_directory(actor,work_order_id)
        if not q['ready'] and principal:q=principal
    if not q['ready']:fail('HANDOVER_READ_DENIED',q['statusLabel'],403)
    if task:verify_task_custody(task)
    ctx=validated_task_context(task,actor,_context) if task else None
    output_q=qualify(actor,OUTPUT_ACTIONS['read'][0],task.work_center_id if task else None,'ProductionWorkshopTask',task_id,required=False)
    # Exact detail verifies this task and all its dependencies. Other work
    # orders can be opened from the separately authorized directory.
    context_order_id = task.work_order_id if task and _selected_detail else work_order_id
    output_facts=read_operation_outputs(user=actor,task_id=task_id,output_id=output_id,work_order_id=context_order_id,_context=ctx) if output_q['ready'] else None
    rows=Handover.objects.filter(company_id=actor.company_id)
    if task_id is not None:rows=rows.filter(data__taskId=task_id)
    if work_order_id is not None:rows=rows.filter(data__taskId__in=list(_options(actor,work_order_id).values_list('pk',flat=True)))
    headers=[]
    for row in rows.select_related('source_work_center','target_work_center').order_by('-pk'):
        if any(qualify(actor,HANDOVER_ACTIONS['read'][0],wc,'OperationHandover',row.pk,required=False)['ready']
            for wc in (row.source_work_center_id,row.target_work_center_id)):
            headers.append(_header(row))
    selected=next((h for h in headers if h['id']==handover_id),None)
    if handover_id is not None and selected is None:fail('HANDOVER_READ_DENIED','所选交接单不在当前真实来源／接收范围。',403)
    account=output_facts['selectedQuantityAccount'] if output_facts else None
    custody_account=account if account is not None else read_task_quantity_account(task,actor,context=ctx) if task else None
    issues=custody_account.get('blockingReasons',[]) if custody_account else ['请先读取真实来源及合法可交份额。']
    source_wc=custody_work_center_id or (selected_row.source_work_center_id if selected_row else read_wc)
    actions={key:_action(actor,key,wc=selected_row.target_work_center_id if selected_row and key=='receive' else source_wc,
        object_id=handover_id if key in ('dispatch','cancel','receive') else None,
        status=selected_row.status if selected_row and key in ('dispatch','cancel','receive') else 'open',
        extra=(issues if key in ('prepare','forward','return','dispatch') else [])) for key in HANDOVER_ACTIONS if key!='read'}
    if selected_row:
        for key in ('dispatch','cancel'):
            if selected_row.status!='prepared':actions[key].update(enabled=False,disabledReason='本单不是尚未交出的备交。')
        if selected_row.status not in ('in_transit','partially_received','discrepancy_pending'):
            actions['receive'].update(enabled=False,disabledReason='本单没有未收在途或明确待核范围。')
        target_actions=[key for key in ('dispatch','receive') if actions[key]['enabled']]
        if target_actions:
            from .operation_handover_service import _current_target
            from .services import PlanningBusinessError
            try:_current_target(actor,selected_row,task)
            except PlanningBusinessError as error:
                for key in target_actions:
                    actions[key].update(enabled=False,disabledReason='；'.join(filter(None,
                        (actions[key]['disabledReason'],error.message))))
    if output_facts:actions.update(output_facts['availableActions'])
    from pde.models import WorkCenter
    centers=[{'id':c.pk,'name':c.name,'workshopId':c.workshop_id,'workshopName':c.workshop.name if c.workshop_id else None}
        for c in WorkCenter.objects.filter(company_id=actor.company_id,is_active=True).select_related('workshop').order_by('pk')]
    operations=[]
    if task:
        for operation in task.work_order.operations.select_related('operation').order_by('sequence'):
            operations.append({'id':operation.pk,'name':operation.operation.name,'sequence':operation.sequence,
                'workOrderId':task.work_order_id,'directoryOnly':True,'qualificationEvaluated':False})
    exceptions=[]
    for e in ExceptionRecord.objects.filter(company_id=actor.company_id,task_id=task_id).select_related('workflow','approval_task','handover').order_by('pk') if task else []:
        scopes={e.data.get('workCenterId',task.work_center_id)}
        if e.handover_id:scopes.update((e.handover.source_work_center_id,e.handover.target_work_center_id))
        if any(qualify(actor,HANDOVER_ACTIONS['read'][0],wc,'OperationCustodyException',e.pk,required=False)['ready'] for wc in scopes if wc):
            exceptions.append(_exception(e))
    selected_exception=next((e for e in exceptions if e['id']==exception_id),None)
    if exception_id is not None and selected_exception is None:fail('HANDOVER_READ_DENIED','所选异常不在当前真实责任读取范围。',403)
    if selected_exception:
        ex_row=ExceptionRecord.objects.get(pk=exception_id)
        actions['exception.confirm']=_action(actor,'exception.confirm',wc=ex_row.data.get('workCenterId',read_wc),
            object_id=ex_row.pk,status=ex_row.status,extra=[] if ex_row.status=='pending' and ex_row.workflow_id and ex_row.approval_task_id
            else ['原观察不直接独审；请登记准确正式处置提案或办理实际投入闭合。'])
        candidates={ex_row.data.get('workCenterId',read_wc)}
        if ex_row.handover_id:candidates.update((ex_row.handover.source_work_center_id,ex_row.handover.target_work_center_id))
        candidates.add(ex_row.data.get('proposal',{}).get('holderWorkCenterId'))
        if ex_row.slice_id:candidates.add(custody_responsibility(ex_row.slice))
        eligible=[wc for wc in sorted(x for x in candidates if x) if qualify(actor,HANDOVER_ACTIONS['exception.submit'][0],wc,
            'OperationCustodyException',ex_row.pk,'open',required=False)['ready']]
        actions['exception.submit']=_action(actor,'exception.submit',wc=eligible[0] if eligible else read_wc,
            object_id=ex_row.pk,status='open',extra=[] if eligible else ['当前人员无本异常双方的准确责任中心。'])
        actions['exception.submit']['eligibleWorkCenterIds']=eligible
        if not ex_row.workflow_id:actions['exception.submit'].update(enabled=False,disabledReason='此为原观察记录；请清除异常选择，另建准确处置提案，不重复审批原观察。')
        actions['correct']=_action(actor,'correct',output=True,wc=ex_row.data.get('workCenterId',read_wc),
            object_id=ex_row.pk,status=ex_row.status,extra=[] if ex_row.kind=='OUTPUT_CORRECTION' and ex_row.status=='pending'
            else ['请选择待独立确认的准确产出更正异常。'])
        if ex_row.kind=='OUTPUT_CORRECTION':
            for key in ('correct','exception.confirm'):
                actions[key]['approvalReady']=selected_exception['productionDecreaseScopeReady']
                actions[key]['approvalDisabledReason']='' if selected_exception['productionDecreaseScopeReady'] else '范围已在其他中心责任或已流转，不能直接减产；须先真实关联核查／责任归还，可明确拒绝本提案。'
    else:
        if 'correct' in actions:actions['correct'].update(enabled=False,disabledReason='请选择准确产出更正异常。',requestObjectId=None)
    selected_output=output_facts['selectedOutput'] if output_facts else None
    actions['input.confirm']=_action(actor,'input.confirm',wc=read_wc,object_id=selected_output['id'] if selected_output else None,
        status='open',extra=[] if selected_output and selected_output['statusCode']=='confirmed' else ['请选择真实已确认且待投入关联的产出。'])
    custody_contexts=[]
    for center in centers:
        if center['id'] not in known_custody:continue
        permitted={key:qualify(actor,HANDOVER_ACTIONS[key][0],center['id'],'ProductionWorkshopTask',task_id,'open',required=False)['ready']
            for key in ('prepare','forward','return','range.release')}
        held=any(custody_responsibility(s)==center['id'] for s in Slice.objects.filter(root__task_id=task_id,status__in=('U','S','V')).select_related('root'))
        custody_contexts.append({**center,'availableActionKeys':[k for k,v in permitted.items() if v],
            'statusLabel':'经正式事件核实的当前保管范围' if held else '原生产来源中心' if center['id']==task.work_center_id else '当前所选正式物流段责任范围；暂无在手份额'})
    input_options=[]
    if task and task.execution_mode=='QUANTIFIED':
        input_q=qualify(actor,HANDOVER_ACTIONS['input.confirm'][0],task.work_center_id,'ProductionWorkshopTask',task.pk,'open',required=False)
        if input_q['ready']:
            from .operation_handover_authority import input_custody_basis
            from .services import PlanningBusinessError
            for s in Slice.objects.filter(company_id=actor.company_id,status__in=('U','S','V'),reserved_by=None,frozen=False,
                holder_workshop_id=task.workshop_id,root__task__work_order_id=task.work_order_id).exclude(root__task=task).select_related('root__task__source_operation','root__uom'):
                if s.data.get('originalUnreceivedAllocationId') and not s.data.get('originalUnreceivedResolvedBy'):continue
                try:basis=input_custody_basis(s,task,actor)
                except PlanningBusinessError:continue
                verify_task_custody(s.root.task)
                input_options.append({'sliceId':s.pk,'expectedVersion':s.version,'quantity':s.quantity,'uomId':s.root.uom_id,'uomLabel':s.root.uom.name,
                    'batchLabel':s.root.batch_label,'scopeManifest':s.root.scope_manifest,'sourceTaskId':s.root.task_id,
                    'inputPurpose':basis['inputPurpose'],'sourceRangeReleaseProof':basis,'statusLabel':'真实来源范围用途或准确生产去处收讫证明已验真'})
    visible_slices=output_facts['slices'] if output_facts else [s for s in (_slices(task) if task else [])
        if s['currentResponsibilityWorkCenterId'] in {c['id'] for c in custody_contexts} and qualify(actor,HANDOVER_ACTIONS['read'][0],s['currentResponsibilityWorkCenterId'],'ProductionWorkshopTask',task_id,'open',required=False)['ready']]
    managed=[s for s in visible_slices if s['currentResponsibilityWorkCenterId']==source_wc and s['available']]
    for key in ('forward','return','range.release'):
        candidates=[s for s in managed if key=='range.release' or s['availableForReturn']]
        if key=='forward':candidates=[s for s in candidates if s['availableForForward']]
        if not candidates:actions[key].update(enabled=False,disabledReason='当前责任中心没有符合本动作的真实未占用／未冻结可支配范围。')
    if not managed:
        can_new=bool(output_facts and output_facts['availableActions']['confirm']['enabled'] and source_wc==task.work_center_id
            and output_facts['selectedTask']['reportCoverageOptions']) if task else False
        if not can_new:actions['prepare'].update(enabled=False,disabledReason='当前责任中心没有真实可备交范围；不能使用原物理holder记录绕过责任释放。')
    custody_source=None if not task else {**_task_option(task),'directoryOnly':False,'qualificationEvaluated':True,
        'quantityPrecision':ctx['unit'].decimal_places if ctx.get('unit') else None,
        'uomId':task.workload_uom_id,'uom':ctx.get('unitSnapshot'),'uomLabel':ctx.get('unitSnapshot',{}).get('name'),
        'sourceSnapshotHash':task.source_snapshot_hash,
        'expectations':{'taskId':task.pk,'expectedSourceSnapshotHash':task.source_snapshot_hash,
            'expectedAccountSnapshotHash':custody_account.get('accountSnapshotHash')},
        'statusLabel':'原生产来源身份与当前保管事实已验真；本区不授予产出办理权限'}
    if custody_source is not None:
        custody_source['availableManagedQuantity']=text(add(*(s['quantity'] for s in managed)))
        custody_source['managedQuantityBasisLabel']='仅当前所选责任中心真实可支配、未占用未冻结份额；不等于整Root总余额'
    matching=[];origins=[]
    if selected_exception and selected_exception['kind']=='UNMATCHED_CLAIM':
        x=ExceptionRecord.objects.get(pk=selected_exception['id'])
        if x.allocation_id:origins=[x.allocation]
    elif selected_row:origins=[a for a in selected_row.allocations.select_related('root','handover') if Decimal(a.data.get('unmatched','0'))>0]
    from .operation_handover_models import OperationHandoverAllocation
    for origin in origins:
            for a in OperationHandoverAllocation.objects.filter(root__account_key=origin.root.account_key,
                handover__source_work_center_id=origin.handover.source_work_center_id,
                handover__target_work_center_id=origin.handover.target_work_center_id).exclude(pk=origin.pk).select_related('handover'):
                outstanding=add(a.quantity,-Decimal(a.data.get('received','0')),-Decimal(a.data.get('lost','0')),-Decimal(a.data.get('returnedBeforeReceipt','0')))
                if a.data.get('dispatched') and outstanding>0:
                    verify_handover(a.handover)
                    matching.append({'originalAllocationId':origin.pk,'allocationId':a.pk,'handoverId':a.handover_id,'handoverNo':a.handover.no,
                        'quantity':text(outstanding),'uomId':a.uom_id,'expectedVersion':a.version,
                        'statusLabel':'同来源同实际目标的正式未收物流范围，须双方明确确认'})
    input_targets=[]
    if task and task.execution_mode=='QUANTIFIED':
        for target in _option_rows(actor,task.work_order_id):
            if target.execution_mode=='QUANTIFIED' and target.pk!=task.pk and is_upstream(task.source_operation,target):
                input_targets.append({**_task_option(target),'statusLabel':'正式获派的同工单后序任务；用途须原来源负责人明确确认'})
    if task is not None:directory_options,_=_custody_directory(actor,context_order_id)
    combined_options={row['id']:row for row in (output_facts['taskOptions'] if output_facts else [])}
    for row in directory_options:combined_options.setdefault(row['id'],row)
    range_releases=[]
    for event in OperationCustodyEvent.objects.filter(company_id=actor.company_id,task_id=task_id,kind='RANGE_RELEASE').order_by('pk'):
        release=event.data.get('rangeRelease',{})
        scopes=(release.get('sourceWorkCenterId'),release.get('target',{}).get('workCenterId'))
        if not any(qualify(actor,HANDOVER_ACTIONS['read'][0],wc,'OperationCustodyEvent',event.pk,required=False)['ready'] for wc in scopes if wc):continue
        verify_record(event)
        acknowledgement=OperationCustodyEvent.objects.filter(company_id=actor.company_id,task_id=task_id,
            kind='RANGE_RECEIVED',data__releaseEventId=event.pk).first()
        if acknowledgement:verify_record(acknowledgement)
        target_binding=release.get('target',{})
        receiving=qualify(actor,HANDOVER_ACTIONS['receive'][0],target_binding.get('workCenterId'),
            'OperationCustodyEvent',event.pk,required=False)
        receipt_issues=receiving['missingItems'][:]
        if acknowledgement:receipt_issues.append('此准确来源范围已经实际收讫，不重复接收。')
        if (event.created_by_id==actor.pk or receiving['currentActorEvidence'].get('employeeId')==event.qualification_snapshot.get('currentActorEvidence',{}).get('employeeId')):receipt_issues.append('交出及接收须由不同真实员工办理。')
        if not receipt_issues:
            target=Task.objects.filter(pk=target_binding.get('taskId'),company_id=actor.company_id,work_order=task.work_order).first()
            from .mes_test_source_bridge import _source
            if (not target or target.version!=target_binding.get('taskVersion') or target.source_snapshot_hash!=target_binding.get('taskSourceSnapshotHash')
                or target.work_center_id!=target_binding.get('workCenterId') or not _source(target,actor)['ready']):receipt_issues.append('目标任务、冻结来源或当前资源已变化，请重新核对。')
        receipt_action={**handover_contract('receive'),'key':'range.receive','apiPath':'/api/planning/operation-handovers/ranges/receive/',
            'requestObjectId':event.pk,'sourceTaskId':event.task_id,'targetTaskId':target_binding.get('taskId'),
            'enabled':not receipt_issues,'disabledReason':'；'.join(receipt_issues),'qualification':receiving}
        range_releases.append({'id':event.pk,'rangeReleaseId':event.pk,'eventHash':event.event_hash,
            'receiptAction':receipt_action,
            'requestHash':event.intent_hash,'source':event.data['rangeRelease'],'occurredAt':event.occurred_at.isoformat(),
            'businessTimezone':'Asia/Shanghai','sourceEmployeeName':event.qualification_snapshot.get('currentActorEvidence',{}).get('employeeName'),
            'actualReceipt':None if not acknowledgement else {'eventId':acknowledgement.pk,
                'eventHash':acknowledgement.event_hash,'occurredAt':acknowledgement.occurred_at.isoformat(),
                'receiverName':acknowledgement.qualification_snapshot.get('currentActorEvidence',{}).get('employeeName'),
                'quantity':acknowledgement.quantity},
            'statusLabel':'目标班组长已实际收讫；投入另行确认' if acknowledgement else '来源班组长已明确本范围用途；目标尚未确认实际收讫'})
    source_center=next((c for c in centers if c['id']==source_wc),None)
    range_centers=[c for c in centers if source_center and c['workshopId']==source_center['workshopId']]
    current_route = read_operation_route(task, actor, verified_headers=headers) if task else None
    from .operation_handover_display import decorate_directions
    decorate_directions(actor,headers,known_routes={task.pk:current_route} if task else {})
    legal_ids = {r['operationId'] for r in (current_route or {}).get('physicalHandoverTargets', [])
        if r.get('handoverReady')}
    return {'contractVersion':HANDOVER_CONTRACT,'moduleCode':'production-operation-handover','factSource':'server','currentStateSource':'server',
        'currentRoute': current_route,
        'legalPrepareTargets': [r for r in operations if r['id'] in legal_ids],
        'usagePurpose':task.work_order.usage_purpose if task else 'MIXED_AUTHORIZED','purposeLabel':('正式生产用途来源（独立开发测试环境）' if task and task.work_order.usage_purpose=='PRODUCTION_USE' else '隔离测试用途；各工序班组长职责办理，测试代办不冒称用户本人点击'),
        'companyId':actor.company_id,'currentActorEvidence':q['currentActorEvidence'],
        'taskOptions':list(combined_options.values()),'selectedTask':output_facts['selectedTask'] if output_facts else None,
        'readDirection':'outgoing','readDirectionLabel':'本任务交出的下游交接（交出方向）','handovers':headers,'selectedHandover':selected,'outputs':output_facts['outputs'] if output_facts else None,
        'selectedOutput':output_facts['selectedOutput'] if output_facts else None,'outputFacts':output_facts,
        'outputReadStatus':'loaded' if output_facts else 'read_denied','outputQualification':output_q,
        'quantityAccounts':output_facts['quantityAccounts'] if output_facts else None,'selectedQuantityAccount':account,
        'slices':visible_slices,'targetWorkCenters':centers,'sourceWorkCenters':custody_contexts,
        'selectedSliceId':slice_id,
        'custodyContexts':custody_contexts,'selectedCustodyWorkCenterId':custody_work_center_id,
        'selectedCustodySource':custody_source,'custodyAccountSnapshotHash':custody_account.get('accountSnapshotHash') if custody_account else None,
        'custodyBlockingReasons':issues,'targetOperations':operations,'inputOptions':input_options,
        'inputTargetTasks':input_targets,'matchingAllocationOptions':matching,'exceptions':exceptions,'selectedException':selected_exception,
        'rangeReleases':range_releases,
        'rangeTargetWorkCenters':range_centers,
        'filterOptions':{'statusLabels':[{'label':label,'value':label} for label in sorted({h['statusLabel'] for h in headers})]},
        'qualification':q,'availableActions':actions,'detailFactsIncluded':bool(task),
        'statusLabel':'工序批次交接及数量事实已正式读取' if task else '正式任务目录已读取，请选择来源任务',
        'resultRecovery':result_recovery(actor,recovery_action,request_hash,request_key_hash,
            task_id=task_id,handover_id=handover_id,output_id=output_id,exception_id=exception_id,slice_id=slice_id),
        'businessWriteCount':0,'auditWriteCount':0,'actualStartCount':0,'actualReportCount':0,'inventoryUpdatedCount':0}


def _check_receiving_target(row, task):
    target = row.source_snapshot.get('target', {})
    # Older tasks carry the same operation digest under the long field name.
    operation_hash = task.source_snapshot.get('operationSnapshotHash') or task.source_snapshot.get('sourceOperationSnapshotHash')
    if (target.get('operationId') != task.source_operation_id
            or not operation_hash or operation_hash != task.source_operation.snapshot_hash
            or target.get('operationSnapshotHash') != operation_hash
            or row.source_snapshot.get('targetWorkCenterId') != task.work_center_id
            or row.source_snapshot.get('targetWorkshopId') != task.workshop_id):
        fail('HANDOVER_RECEIVER_SOURCE_MISMATCH', '原交接冻结目标与本接收任务不一致。')


def _receiving_task(actor, row, sources, targets):
    source = sources.get(row.data.get('taskId'))
    if source is None:
        return None
    task = targets.get((source.work_order_id, row.target_operation_id, row.target_work_center_id))
    if task and qualify(actor, HANDOVER_ACTIONS['read'][0], task.work_center_id,
            'ProductionWorkshopTask', task.pk, required=False)['ready']:
        _check_receiving_target(row, task)
        return task
    return None


def _direction_tasks(actor, work_order_id):
    tasks = list(_options(actor, work_order_id))
    return ({task.pk: task for task in tasks},
        {(task.work_order_id, task.source_operation_id, task.work_center_id): task for task in tasks})


@scoped_execution_read
def receiving_task_for_number(*, user, handover, work_order_id=None):
    actor = actor_for(user)
    sources, targets = _direction_tasks(actor, work_order_id)
    task = _receiving_task(actor, handover, sources, targets)
    if not task:
        fail('HANDOVER_NOT_VISIBLE', '当前接收方向未找到可查看的交接单。', 403)
    return task.pk


@scoped_execution_read
def read_handover_directory(*, user, direction, work_order_id=None, task_id=None):
    from .operation_handover_display import direction_display
    from .operation_route_facts import read_operation_direction
    from .services import PlanningBusinessError

    actor = actor_for(user)
    sources, targets = _direction_tasks(actor, work_order_id)
    chosen = sources.get(task_id) if task_id else None
    if task_id and chosen is None:
        fail('HANDOVER_TASK_NOT_VISIBLE', '任务不在当前公司及工单范围。', 403)
    if direction == 'incoming' and chosen:
        qualify(actor, HANDOVER_ACTIONS['read'][0], chosen.work_center_id,
            'ProductionWorkshopTask', chosen.pk)

    headers, principal = [], None
    handovers = Handover.objects.filter(company_id=actor.company_id).select_related(
        'source_work_center__workshop', 'target_work_center__workshop').order_by('-pk')
    for row in handovers:
        source = sources.get(row.data.get('taskId'))
        if source is None:
            continue
        if direction == 'incoming':
            receiver = _receiving_task(actor, row, sources, targets)
            if receiver is None or (chosen and chosen.pk != receiver.pk):
                continue
            q = qualify(actor, HANDOVER_ACTIONS['read'][0], receiver.work_center_id,
                'ProductionWorkshopTask', receiver.pk, required=False)
        else:
            if chosen and chosen.pk != source.pk:
                continue
            receiver = None
            q = qualify(actor, HANDOVER_ACTIONS['read'][0], row.source_work_center_id,
                'OperationHandover', row.pk, required=False)
            if not q['ready']:
                continue
        principal = principal or q
        header = _header(row, directory=True)
        if receiver:
            header['receivingTaskId'] = receiver.pk
        try:
            header['directionDisplay'] = direction_display(header, read_operation_direction(source, actor))
        except PlanningBusinessError as error:
            header['directionDisplay'] = direction_display(header, None, error=error)
        headers.append(header)
    if principal is None:
        _, principal = _custody_directory(actor, work_order_id, verify_custody=False)
    if principal is None:
        fail('HANDOVER_READ_DENIED', '当前岗位未获授权查看交接单。', 403)
    labels = sorted({row['statusLabel'] for row in headers})
    return {
        'contractVersion': HANDOVER_CONTRACT, 'moduleCode': 'production-operation-handover',
        'factSource': 'server', 'currentStateSource': 'server', 'readMode': 'directory',
        'companyId': actor.company_id, 'currentActorEvidence': principal['currentActorEvidence'],
        'readDirection': direction,
        'readDirectionLabel': '本任务接收的上游交接（接收方向）' if direction == 'incoming' else '本任务交出的下游交接（交出方向）',
        'handovers': headers, 'availableActions': {},
        'filterOptions': {'statusLabels': [{'label': label, 'value': label} for label in labels]},
        'businessWriteCount': 0, 'auditWriteCount': 0,
    }


def _read_incoming(user,task_id,work_order_id,handover_id,context,selected_detail):
    """An explicit receiving-task context, independent of the immutable source taskId on each leg.

    Existing source-task and write contracts remain unchanged. Historical reads qualify
    today's receiver duty but verify original ledger/frozen targets, not current balances.
    """
    actor=actor_for(user)
    if task_id is None and handover_id is not None:fail('HANDOVER_QUERY_OBJECT_MISMATCH','查看上游原交接单须同时明确本接收任务。',400)
    task=_options(actor,work_order_id).filter(pk=task_id).first() if task_id else None
    if task_id and not task:fail('HANDOVER_TASK_NOT_VISIBLE','接收任务不在本公司、本工单合法正式范围。',403)
    if task:
        qualify(actor,HANDOVER_ACTIONS['read'][0],task.work_center_id,'ProductionWorkshopTask',task.pk)
    facts=read_operation_handovers(user=user,task_id=task_id,work_order_id=work_order_id,
        _context=context,_selected_detail=selected_detail)
    headers=[]
    if task:
        source_tasks={t.pk:t for t in _option_rows(actor,task.work_order_id)}
        for row in Handover.objects.filter(company_id=actor.company_id,target_operation_id=task.source_operation_id,
                target_work_center_id=task.work_center_id).select_related('source_work_center__workshop','target_work_center__workshop').order_by('-pk'):
            source=source_tasks.get(row.data.get('taskId'))
            if not source or source.work_order_id!=task.work_order_id:continue
            _check_receiving_target(row, task)
            headers.append(_header(row))
    from .operation_handover_display import decorate_directions
    decorate_directions(actor,headers)
    selected=next((h for h in headers if h['id']==handover_id),None)
    if handover_id and not selected:fail('HANDOVER_NOT_VISIBLE','原交接单不属于本任务的上游接收范围。',403)
    facts.update(readDirection='incoming',readDirectionLabel='本任务接收的上游交接（接收方向）',
        handovers=headers,selectedHandover=selected,
        statusLabel='上游接收历史已独立核实；本任务数量账户与原交接来源分别表达' if task else '请先选择本接收任务；未展示交出方向记录',
        filterOptions={'statusLabels':[{'label':v,'value':v} for v in sorted({h['statusLabel'] for h in headers})]})
    facts['taskOptions']=[row for row in facts['taskOptions'] if qualify(actor,HANDOVER_ACTIONS['read'][0],row['workCenterId'],'ProductionWorkshopTask',row['taskId'],required=False)['ready']]
    # Receiver-context history is deliberately read-only: never submit its taskId
    # as the source task on a legacy physical write action.
    facts['availableActions']={k:v for k,v in facts['availableActions'].items() if k=='read'}
    for release in facts.get('rangeReleases',[]):
        if release.get('receiptAction'):release['receiptAction'].update(enabled=False,disabledReason='当前为上游接收历史只读查看。')
    return facts
