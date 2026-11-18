"""Audited difference/correction decisions, never a balancing write shortcut."""
from copy import deepcopy
from decimal import Decimal
from django.db import transaction,IntegrityError,OperationalError
from django.utils import timezone
from .operation_handover_core import *
from .operation_handover_core import _hash
from .operation_handover_contract import ACTIONS
from .operation_handover_models import (OperationOutputEvidence as Output,OperationCustodySlice as Slice,
    OperationHandover as Handover,OperationHandoverAllocation as Allocation,
    OperationCustodyException as ExceptionRecord,OperationCustodyEvent as Event)
from .operation_output_authority import task_context,bind_account,evidence_proof,verify_shared_review
from .operation_handover_authority import verify_task_custody,settle_short_exceptions,settle_unmatched_exceptions,custody_responsibility
from .operation_handover_service import (_task,split_slice,_emit,_refresh_status,close_inputs_for_output)
from .operation_resource_read_scope import scoped_execution_read


def _shared_request(row,actor,code,q,reason):
    from workflow_runtime.models import WorkflowInstance,ApprovalTask
    from .operation_handover_permissions import reviewer_role_for
    from .operation_output_service import _shared_initial
    role=reviewer_role_for(user=actor,action_code=ACTIONS['exception.confirm'][0],work_center_id=row.data['workCenterId'])
    workflow=_shared_initial(WorkflowInstance,'WorkflowInstance',actor,row,code,q,reason,
        instance_no=f'MES-CUSTODY-EX-{row.company_id}-{row.pk}',process_definition_id=q['definitionId'],
        document_type='OperationCustodyException',document_id=row.pk,current_step=1,total_steps=1,version=1)
    approval=_shared_initial(ApprovalTask,'ApprovalTask',actor,row,code,q,reason,
        task_no=f'MES-CUSTODY-REVIEW-{row.company_id}-{row.pk}',workflow_instance=workflow,step_no=1,
        required_role_code=role,minimum_approvals=1,allow_parallel=False,version=1)
    project(row,workflow=workflow,approval_task=approval)


def _submit(actor,payload,accounts):
    allowed={'taskId','handoverId','allocationId','sliceId','outputId','kind','quantity','workCenterId',
        'evidenceReference','proposal','occurredAt','reason','idempotencyKey','expectedSliceVersion',
        'exceptionId','confirmationReference'}
    payload_guard(payload,allowed,{'taskId','workCenterId','occurredAt','reason','idempotencyKey'})
    for key in ('taskId','workCenterId'):strict_id(payload[key],key)
    for key in ('handoverId','allocationId','sliceId','outputId','exceptionId','expectedSliceVersion'):
        if key in payload:strict_id(payload[key],key,nullable=key!='expectedSliceVersion',zero=key=='expectedSliceVersion')
    task=_task(actor,payload['taskId']);code=ACTIONS['exception.submit'][0]
    q=qualify(actor,code,payload['workCenterId'],'OperationCustodyException',payload.get('exceptionId'))
    digest,replay=intent(actor,code,payload.get('exceptionId'),payload)
    if replay:return ExceptionRecord.objects.get(pk=replay.target_entity_id),False
    ctx=task_context(task,actor);stamp=occurred(payload['occurredAt']);reason=payload['reason'].strip()
    if not ctx['quantified']:fail('CUSTODY_QUANTITY_NOT_APPLICABLE','本经过工序无统计产量，不适用数值异常；请明确原合法定量批次来源。',400)
    if payload.get('exceptionId'):
        row=ExceptionRecord.objects.select_related('handover').filter(pk=payload['exceptionId'],task=task,company_id=actor.company_id).first()
        if not row or row.status!='pending' or not row.handover_id:fail('CUSTODY_PARTY_CONFIRM_INVALID','该异常没有可确认的双方交接范围。')
        if not row.workflow_id:fail('CUSTODY_OBSERVATION_REQUIRES_PROPOSAL','原差额观察不直接审批或双方确认；请另行登记准确处置提案。')
        stamp=occurred(payload['occurredAt'],not_before=row.occurred_at)
        allowed_wcs={row.handover.source_work_center_id,row.handover.target_work_center_id}
        if row.slice_id:allowed_wcs.add(custody_responsibility(row.slice))
        if row.kind=='LOCATE_SHORT':allowed_wcs.add(row.data.get('proposal',{}).get('holderWorkCenterId'))
        if payload['workCenterId'] not in allowed_wcs or not str(payload.get('confirmationReference','')).strip():
            fail('CUSTODY_PARTY_SCOPE_INVALID','须由此物流段真实责任方明确确认准确范围及依据。',403)
        event=_emit(actor,code,q,task,'EXCEPTION_PARTY_CONFIRM','0','','',stamp,digest,reason,header=row.handover,
            data={'exceptionId':row.pk,'workCenterId':payload['workCenterId'],
                'employeeId':q['currentActorEvidence']['employeeId'],'confirmationReference':payload['confirmationReference']})
        commit_intent(actor,code,payload,digest,row,{'taskId':task.pk,'exceptionId':row.pk,
            'originalObjectId':row.pk,'eventReference':f'OperationCustodyEvent:{event.pk}'})
        bump(accounts[task.pk],'custody');return row,True
    kind=payload.get('kind')
    if kind not in ('LOSS','LOCATE_SHORT','RECEIPT_CORRECTION','OUTPUT_CORRECTION','UNMATCHED_CLAIM'):
        fail('CUSTODY_EXCEPTION_KIND_INVALID','请选择已开放的差额、定位、关联更正或多收匹配意图。',400)
    amount=number(payload.get('quantity'),positive=True,precision=ctx['unit'].decimal_places)
    if not str(payload.get('evidenceReference','')).strip():fail('CUSTODY_REAL_EVIDENCE_REQUIRED','异常不能仅凭原因平账，须填写真实原始依据。',400)
    proposal=payload.get('proposal',{})
    if not isinstance(proposal,dict):fail('CUSTODY_PROPOSAL_INVALID','异常处置意图须为明确结构。',400)
    expected_proposal={'LOSS':set(),'LOCATE_SHORT':{'holderWorkCenterId','holderReference'},
        'RECEIPT_CORRECTION':{'direction'},'OUTPUT_CORRECTION':{'direction'},'UNMATCHED_CLAIM':{'matchedAllocationId'}}[kind]
    if set(proposal)!=expected_proposal:fail('CUSTODY_PROPOSAL_INVALID','处置提案字段须与本准确异常类型一致。',400)
    if kind=='LOCATE_SHORT':strict_id(proposal['holderWorkCenterId'],'实际保管中心')
    if kind=='UNMATCHED_CLAIM':strict_id(proposal['matchedAllocationId'],'实际匹配物流分量')
    header=Handover.objects.filter(pk=payload.get('handoverId'),company_id=actor.company_id,data__taskId=task.pk).first() if payload.get('handoverId') else None
    allocation=header.allocations.filter(pk=payload.get('allocationId')).first() if header and payload.get('allocationId') else None
    slice=Slice.objects.select_related('root__task').filter(pk=payload.get('sliceId'),company_id=actor.company_id,root__task=task).first() if payload.get('sliceId') else None
    if slice:occurred(payload['occurredAt'],not_before=slice.root.occurred_at)
    if header and header.dispatched_at:occurred(payload['occurredAt'],not_before=header.dispatched_at)
    if kind=='OUTPUT_CORRECTION':
        if payload['workCenterId']!=task.work_center_id:
            fail('OUTPUT_CORRECTION_SOURCE_AUTHORITY_REQUIRED','产出真实性更正须由原生产中心负责人明确提出，不得借其他物流腿取得减产权限。',403)
        if slice and slice.status=='U' and slice.holder_work_center_id!=task.work_center_id:
            fail('OUTPUT_CORRECTION_SOURCE_CUSTODY_REQUIRED','直接减产仅接受原生产中心真实在手范围。',403)
        if header and (not allocation or not slice or slice.data.get('legAllocationId')!=allocation.pk
            or allocation.handover_id!=header.pk or allocation.root_id!=slice.root_id):
            fail('OUTPUT_CORRECTION_UNRELATED_HANDOVER','产出更正所带物流腿须是本份额的真实关联，不能借用其他交接单。',403)
    if header:
        if payload['workCenterId'] not in (header.source_work_center_id,header.target_work_center_id):
            fail('CUSTODY_EXCEPTION_PARTY_INVALID','当前责任中心不属于该准确物流段。',403)
    elif payload['workCenterId']!=task.work_center_id:
        fail('CUSTODY_EXCEPTION_SOURCE_INVALID','产出异常须属于此任务真实来源中心。',403)
    if kind in ('LOSS','LOCATE_SHORT','RECEIPT_CORRECTION','UNMATCHED_CLAIM') and not allocation:
        fail('CUSTODY_ALLOCATION_REQUIRED','物流异常必须准确关联原物流分量。',400)
    if kind in ('RECEIPT_CORRECTION','OUTPUT_CORRECTION'):
        if not slice or slice.version!=payload.get('expectedSliceVersion') or slice.status not in ('U','S','V') or slice.reserved_by_id or slice.frozen:
            fail('CUSTODY_CORRECTION_SCOPE_NOT_AVAILABLE','拟更正分量已占用、冻结、分送或不在真实在手范围，不能简单改数。')
        if amount>Decimal(slice.quantity):fail('CUSTODY_CORRECTION_SCOPE_EXCEEDED','更正超过可核对实际范围。')
        if kind=='RECEIPT_CORRECTION' and slice.data.get('legAllocationId')!=allocation.pk:
            fail('CUSTODY_CORRECTION_LEG_MISMATCH','更正份额不是本腿原收讫范围。')
        if kind=='OUTPUT_CORRECTION' and slice.root_id!=payload.get('outputId'):
            fail('OUTPUT_CORRECTION_PRODUCER_MISMATCH','产出更正须引用该实际份额的准确产出依据。')
        slice=split_slice(slice,amount,actor=actor,code=code,q=q,stamp=stamp,digest=digest,reason=reason,header=header)
        project(slice,frozen=True,version=slice.version+1)
    source={'taskId':task.pk,'sourceSnapshotHash':task.source_snapshot_hash,'proposal':deepcopy(proposal),
        'currentResponsibleWorkCenterId':custody_responsibility(slice) if slice else None,
        'intentPayload':{k:deepcopy(v) for k,v in payload.items() if k!='idempotencyKey'}}
    row=initialize(ExceptionRecord,actor=actor,code=code,q=q,status='pending',source=source,intent_hash=digest,
        reason=reason,task=task,handover=header,allocation=allocation,slice=slice,kind=kind,
        original_quantity=allocation.quantity if allocation else slice.quantity if slice else text(amount),
        quantity=text(amount),occurred_at=stamp,data={'workCenterId':payload['workCenterId'],'proposal':proposal,
            'evidenceReference':payload['evidenceReference'],'outputId':payload.get('outputId')})
    _shared_request(row,actor,code,q,reason)
    event=_emit(actor,code,q,task,'EXCEPTION_PROPOSE',amount,'','F' if slice else '',stamp,digest,reason,
        [slice] if slice else [],header=header,allocation=allocation,
        data={'exceptionId':row.pk,'workCenterId':payload['workCenterId'],
            'employeeId':q['currentActorEvidence']['employeeId'],'proposal':deepcopy(proposal)})
    bump(accounts[task.pk],'production' if kind=='OUTPUT_CORRECTION' else 'custody')
    commit_intent(actor,code,payload,digest,row,{'taskId':task.pk,'exceptionId':row.pk,'originalObjectId':None,
        'eventReference':f'OperationCustodyEvent:{event.pk}'})
    return row,True


def _parties(row):
    confirmations={}
    for event in Event.objects.filter(task_id=row.task_id,kind__in=('EXCEPTION_PROPOSE','EXCEPTION_PARTY_CONFIRM')).order_by('pk'):
        if event.data.get('exceptionId')!=row.pk:continue
        verify_record(event)
        confirmations[event.data['workCenterId']]=event.data['employeeId']
    return confirmations


def _review_identity(actor,row,payload,code):
    q=qualify(actor,code,row.data.get('workCenterId',row.task.work_center_id),'OperationCustodyException',row.pk,row.status)
    verify_record(row)
    if row.data.get('proposal')!=row.source_snapshot.get('proposal') or row.data.get('workCenterId')!=row.source_snapshot.get('intentPayload',{}).get('workCenterId'):
        fail('CUSTODY_EXCEPTION_INTENT_DAMAGED','异常原提案及责任中心与冻结意图不一致。')
    if (row.status!='pending' or row.version!=payload['expectedVersion']
        or row.source_snapshot_hash!=payload['expectedSourceSnapshotHash'] or not row.workflow_id
        or row.workflow.status!='pending' or row.approval_task.status!='pending'
        or row.workflow.version!=payload['expectedWorkflowVersion']
        or row.approval_task.version!=payload['expectedApprovalTaskVersion']):
        fail('CUSTODY_EXCEPTION_VERSION_CHANGED','原异常或共享审核版本已变化，禁止重放处置。')
    employee=q['currentActorEvidence']['employeeId']
    if (actor.pk==row.created_by_id or employee==row.qualification_snapshot['currentActorEvidence'].get('employeeId')
        or row.approval_task.required_role_code not in q['roleCodes']):
        fail('CUSTODY_EXCEPTION_REVIEW_NOT_INDEPENDENT','异常须由不同真实员工及其独立正式审核角色确认。',403)
    return q


def _apply(row,actor,code,q,stamp,digest,reason,accounts):
    from pde.models import WorkCenter
    from .operation_output_service import _mint
    task=row.task;ctx=task_context(task,actor);amount=Decimal(row.quantity);proposal=row.data['proposal']
    header=row.handover;allocation=row.allocation;changed=[];result={}
    if row.kind in ('LOSS','LOCATE_SHORT'):
        leaves=[s for s in Slice.objects.filter(root=allocation.root,status='Q').order_by('pk')
            if s.data.get('legAllocationId')==allocation.pk]
        if amount>add(*(s.quantity for s in leaves)):fail('CUSTODY_SHORT_RANGE_CHANGED','待核份额已变化，不能重复处置。')
        center=None
        if row.kind=='LOCATE_SHORT':
            if set(proposal)!={'holderWorkCenterId','holderReference'} or not str(proposal['holderReference']).strip():
                fail('CUSTODY_REAL_CUSTODIAN_REQUIRED','定位须明确真实保管中心及可核对实物依据。',400)
            center=WorkCenter.objects.select_related('workshop').filter(pk=proposal['holderWorkCenterId'],company_id=actor.company_id,is_active=True).first()
            if not center or not center.workshop_id:fail('CUSTODY_REAL_CUSTODIAN_REQUIRED','实际保管中心无有效正式车间。')
            if center.pk not in _parties(row):fail('CUSTODY_CUSTODIAN_CONFIRMATION_REQUIRED','实际保管中心负责人尚未正式确认本准确范围。')
        remaining=amount
        for leaf in leaves:
            if remaining<=0:break
            part=min(remaining,Decimal(leaf.quantity));selected=split_slice(leaf,part,actor=actor,code=code,q=q,stamp=stamp,digest=digest,reason=reason,header=header)
            transition(selected,'Z' if row.kind=='LOSS' else 'S',actor=actor,code=code,q=q,reason=reason)
            if center:project(selected,holder_work_center=center,holder_workshop_id=center.workshop_id,
                data={**selected.data,'locatedShortExceptionId':row.pk,'originalUnreceivedAllocationId':allocation.pk,
                    'priorRangeReleaseIntentHash':selected.data.get('rangeReleaseIntentHash'),
                    'rangeReleaseIntentHash':None,'normalPurposeActive':False})
            changed.append(selected);remaining=add(remaining,-part)
        if row.kind=='LOSS':
            project(allocation,data={**allocation.data,'short':text(add(allocation.data['short'],-amount)),
                'lost':text(add(allocation.data.get('lost','0'),amount))},version=allocation.version+1)
            _refresh_status(header,actor,code,q,reason)
        # Located Q is now controlled custody. The original leg remains unresolved
        # until a genuine RETURN reaches source; no original a or global A is added.
        result={'sliceIds':[s.pk for s in changed]}
    elif row.kind=='RECEIPT_CORRECTION':
        parties=_parties(row)
        if (header.source_work_center_id not in parties or header.target_work_center_id not in parties
            or parties[header.source_work_center_id]==parties[header.target_work_center_id]):
            fail('CUSTODY_BOTH_PARTIES_REQUIRED','跨责任收讫更正须由双方不同真实负责人明确确认。')
        if proposal!={'direction':'decrease'}:
            fail('CUSTODY_RECEIPT_CORRECTION_INTENT','本入口只接受有准确原在手份额的实收调减；调增须匹配真实原在途／待核来源。',400)
        selected=Slice.objects.get(pk=row.slice_id)
        responsible=custody_responsibility(selected)
        if responsible and responsible not in parties:
            fail('CUSTODY_CURRENT_RESPONSIBLE_CONFIRMATION_REQUIRED','当前责任中心尚未正式确认准确关联更正范围。')
        if not selected.frozen or selected.reserved_by_id or selected.status not in ('U','S','V'):
            fail('CUSTODY_CORRECTION_SCOPE_CHANGED','更正前冻结的原范围已变化。')
        project(selected,frozen=False,version=selected.version+1)
        transition(selected,'Q',actor=actor,code=code,q=q,reason=reason)
        project(selected,holder_workshop=None,holder_work_center=None)
        project(allocation,data={**allocation.data,'received':text(add(allocation.data['received'],-amount)),
            'short':text(add(allocation.data['short'],amount))},version=allocation.version+1)
        if Decimal(allocation.data['received'])<0:fail('CUSTODY_CORRECTION_NEGATIVE','更正后原实收不能为负。')
        _refresh_status(header,actor,code,q,reason);changed=[selected]
    elif row.kind=='OUTPUT_CORRECTION':
        if proposal!={'direction':'decrease'}:
            fail('OUTPUT_CORRECTION_NEW_PRODUCTION_REQUIRED','增量必须有真实未重复产出依据；不得用更正绕过原报工或超产确认。')
        selected=Slice.objects.select_related('root').get(pk=row.slice_id)
        if (not selected.frozen or selected.status!='U' or selected.reserved_by_id
            or selected.holder_work_center_id!=task.work_center_id or row.data.get('workCenterId')!=task.work_center_id
            or custody_responsibility(selected)!=task.work_center_id):
            fail('OUTPUT_CORRECTION_ALREADY_MOVED','产出调减只允许未占用、尚在源的准确范围；已交份额须先逐段实际处理。')
        original=selected.root
        correction=initialize(Output,actor=actor,code=code,q=q,status='confirmed',
            source={'task':ctx['snapshot'],'allocations':[],'exceptionId':row.pk,'exceptionSourceHash':row.source_snapshot_hash},
            intent_hash=digest,reason=reason,task=task,kind='OUTPUT_CORRECTION',quantity=row.quantity,
            uom_id=original.uom_id,account_key=original.account_key,batch_label=original.batch_label,
            scope_manifest=deepcopy(original.scope_manifest),scope_hash=_hash({'exceptionId':row.pk,'sourceScopeHash':original.scope_hash}),
            occurred_at=stamp,confirmed_by=actor,confirmed_at=timezone.now(),correction_of=original,effect_sign=-1,
            workflow=row.workflow,approval_task=row.approval_task,approval_decision=row.approval_decision,
            data={'exceptionId':row.pk})
        project(selected,frozen=False,version=selected.version+1,data={**selected.data,'voidedByOutputCorrectionId':correction.pk})
        transition(selected,'closed',actor=actor,code=code,q=q,reason=reason)
        changed=[selected];result={'outputCorrectionId':correction.pk};bump(accounts[task.pk],'production')
    elif row.kind=='UNMATCHED_CLAIM':
        matched=Allocation.objects.select_related('handover','root__task').filter(pk=proposal.get('matchedAllocationId'),company_id=actor.company_id).first()
        if (set(proposal)!={'matchedAllocationId'} or not matched or matched.root.account_key!=allocation.root.account_key
            or matched.handover.target_work_center_id!=header.target_work_center_id or not matched.data.get('dispatched')
            or matched.handover.source_work_center_id!=header.source_work_center_id):
            fail('CUSTODY_EXCESS_SOURCE_UNPROVEN','超收只能匹配相同真实来源、实际目标及另一已真实交出未收份额，不能挂靠别的root。')
        parties=_parties(row)
        if not all(wc in parties for wc in (header.source_work_center_id,header.target_work_center_id)):
            fail('CUSTODY_BOTH_PARTIES_REQUIRED','多收来源匹配须双方正式确认。')
        leaves=[s for s in Slice.objects.filter(root=matched.root,status__in=('I','Q')).order_by('pk') if s.data.get('legAllocationId')==matched.pk]
        if amount>add(*(s.quantity for s in leaves)) or amount>Decimal(allocation.data['unmatched']):
            fail('CUSTODY_EXCESS_SOURCE_EXCEEDED','多收匹配超过真实未收来源或原未匹配数量。')
        remaining=amount;from_q=Decimal(0)
        for leaf in leaves:
            if remaining<=0:break
            part=min(remaining,Decimal(leaf.quantity));prior=leaf.status
            selected=split_slice(leaf,part,actor=actor,code=code,q=q,stamp=stamp,digest=digest,reason=reason,header=matched.handover)
            target='U' if matched.handover.target_workshop_id==task.workshop_id else 'S' if matched.handover.destination_kind=='storage' else 'V'
            transition(selected,target,actor=actor,code=code,q=q,reason=reason)
            project(selected,holder_work_center_id=matched.handover.target_work_center_id,holder_workshop_id=matched.handover.target_workshop_id,
                data={**selected.data,'unmatchedClaimExceptionId':row.pk,'receivedLegId':matched.handover_id})
            if prior=='Q':from_q=add(from_q,part)
            changed.append(selected);remaining=add(remaining,-part)
        project(matched,data={**matched.data,'received':text(add(matched.data['received'],amount)),
            'short':text(add(matched.data['short'],-from_q))},version=matched.version+1)
        project(allocation,data={**allocation.data,'unmatched':text(add(allocation.data['unmatched'],-amount))},version=allocation.version+1)
        _refresh_status(matched.handover,actor,code,q,reason)
        _emit(actor,code,q,task,'UNMATCHED_SOURCE_MATCH',amount,'I/Q','V',stamp,digest,reason,changed,
            header=matched.handover,allocation=matched,data={'exceptionId':row.pk,'originalRawReceiptHandoverId':header.pk})
        result={'matchedAllocationId':matched.pk}
    else:fail('CUSTODY_EXCEPTION_ACTION_UNSUPPORTED','此异常需要准确专用事实，不支持通过任意状态平账。')
    event=_emit(actor,code,q,task,'EXCEPTION_RESOLVE',amount,row.kind,'RESOLVED',stamp,digest,reason,
        changed,header=header,allocation=allocation,data={'exceptionId':row.pk,**result})
    if allocation:
        settle_short_exceptions(allocation,actor=actor,code=code,q=q,reason=reason)
        if row.kind=='UNMATCHED_CLAIM':settle_unmatched_exceptions(allocation,actor=actor,code=code,q=q,reason=reason)
    return {**result,'eventReference':f'OperationCustodyEvent:{event.pk}'}


def _confirm(actor,row,payload,accounts,code=None):
    from workflow_runtime.models import ApprovalDecision
    from .operation_output_service import _shared_decide,_review_proof
    payload_guard(payload,{'expectedVersion','expectedSourceSnapshotHash','expectedWorkflowVersion',
        'expectedApprovalTaskVersion','decision','occurredAt','reason','idempotencyKey','exceptionId'},
        {'expectedVersion','expectedSourceSnapshotHash','expectedWorkflowVersion','expectedApprovalTaskVersion','decision','occurredAt','reason','idempotencyKey'})
    for key in ('expectedVersion','expectedWorkflowVersion','expectedApprovalTaskVersion'):strict_id(payload[key],key,zero=True)
    code=code or ACTIONS['exception.confirm'][0]
    digest,replay=intent(actor,code,row.pk,payload)
    if replay:
        qualify(actor,code,row.data.get('workCenterId',row.task.work_center_id),'OperationCustodyException',row.pk,'pending')
        verify_record(row);return row,False
    q=_review_identity(actor,row,payload,code)
    if payload['decision'] not in ('approve','reject'):fail('CUSTODY_REVIEW_INTENT_INVALID','请选择明确确认或拒绝意图。',400)
    stamp=occurred(payload['occurredAt'],not_before=row.occurred_at);reason=payload['reason'].strip();approved=payload['decision']=='approve'
    decision=ApprovalDecision.objects.create(task=row.approval_task,decision_sequence=1,actor=actor,
        decision='approved' if approved else 'rejected',comment=reason,action_id=code,
        idempotency_key=payload['idempotencyKey'],decision_hash=digest)
    review_proof=_review_proof(actor,row,payload,q,decision,stamp)
    _shared_decide(row.approval_task,actor,row,code,q,reason,'approved' if approved else 'rejected',review_proof)
    _shared_decide(row.workflow,actor,row,code,q,reason,'approved' if approved else 'rejected',review_proof)
    project(row,approval_decision=decision,data={**row.data,'reviewerId':actor.pk,
        'reviewerEmployeeId':q['currentActorEvidence']['employeeId'],'reviewedAt':stamp.isoformat(),'reviewProof':review_proof})
    result=_apply(row,actor,code,q,stamp,digest,reason,accounts) if approved else {}
    if not approved and row.slice_id:
        selected=row.slice
        if selected.frozen:
            project(selected,frozen=False,version=selected.version+1)
            event=_emit(actor,code,q,row.task,'EXCEPTION_REJECTED',row.quantity,'F',selected.status,stamp,digest,reason,[selected],
                header=row.handover,allocation=row.allocation,data={'exceptionId':row.pk})
            result['eventReference']=f'OperationCustodyEvent:{event.pk}'
    project(row,data={**row.data,**result})
    transition(row,'confirmed' if approved else 'rejected',actor=actor,code=code,q=q,reason=reason)
    verify_shared_review(row)
    bump(accounts[row.task_id],'production' if row.kind=='OUTPUT_CORRECTION' else 'custody')
    commit_intent(actor,code,payload,digest,row,{'taskId':row.task_id,'exceptionId':row.pk,
        'originalObjectId':row.pk,'decisionId':decision.pk,**result})
    return row,True


def _input(actor,payload,accounts):
    from .operation_handover_service import close_inputs_for_output
    payload_guard(payload,{'outputId','expectedVersion','expectedSourceSnapshotHash','inputAllocations',
        'occurredAt','reason','idempotencyKey'},{'outputId','expectedVersion','expectedSourceSnapshotHash',
        'inputAllocations','occurredAt','reason','idempotencyKey'})
    strict_id(payload['outputId'],'投入关联产出');strict_id(payload['expectedVersion'],'投入关联版本',zero=True)
    row=Output.objects.select_related('task').filter(pk=payload['outputId'],company_id=actor.company_id,status='confirmed').first()
    if not row:fail('OUTPUT_INPUT_OUTPUT_UNPROVEN','投入关联须引用真实已确认产出。')
    code=ACTIONS['input.confirm'][0];q=qualify(actor,code,row.task.work_center_id,'OperationOutputEvidence',row.pk)
    digest,replay=intent(actor,code,row.pk,payload)
    if replay:return row,False
    if row.version!=payload['expectedVersion'] or row.source_snapshot_hash!=payload['expectedSourceSnapshotHash']:
        fail('OUTPUT_INPUT_VERSION_CHANGED','产出或投入源版本变化。')
    if row.input_allocations.exists():fail('OUTPUT_INPUT_ALREADY_CLOSED','该产出已有真实投入闭合，请勿重复确认。')
    ctx=task_context(row.task,actor);bind_account(ctx,accounts[row.task_id]);stamp=occurred(payload['occurredAt'],not_before=ctx['start'].started_at)
    close_inputs_for_output(actor=actor,ctx=ctx,output=row,inputs=payload['inputAllocations'],accounts=accounts,
        code=code,q=q,stamp=stamp,digest=digest,reason=payload['reason'].strip())
    bump(accounts[row.task_id],'custody')
    event=Event.objects.filter(task_id=row.task_id,kind='INPUT_PROVEN',intent_hash=digest).latest('pk')
    commit_intent(actor,code,payload,digest,row,{'taskId':row.task_id,'outputId':row.pk,'originalObjectId':row.pk,
        'eventReference':f'OperationCustodyEvent:{event.pk}'})
    return row,True


def execute_exception(*,user,action,payload,exception_id=None,code_override=None):
    actor=actor_for(user);row=None
    if exception_id is not None:
        row=ExceptionRecord.objects.select_related('task__work_order','task__source_operation','handover','allocation','slice','workflow','approval_task').filter(pk=exception_id,company_id=actor.company_id).first()
        if not row:fail('CUSTODY_EXCEPTION_NOT_VISIBLE','未找到本公司准确异常对象。',403)
    task_id=row.task_id if row else payload.get('taskId')
    if action=='input.confirm':
        output=Output.objects.filter(pk=payload.get('outputId'),company_id=actor.company_id).first()
        if not output:fail('OUTPUT_NOT_VISIBLE','投入引用产出不在本公司范围。',403)
        task_id=output.task_id
    tasks=[task_id]
    tasks.extend(Slice.objects.filter(pk__in=[i.get('sliceId') for i in payload.get('inputAllocations',[]) if isinstance(i,dict)],
        company_id=actor.company_id).values_list('root__task_id',flat=True))
    try:
        with transaction.atomic():
            accounts=lock_accounts(actor,tasks)
            from pde.operation_allocation_source_handoff_service import allocation_admission_context
            from .operation_predecessor_authority import verification_context
            with allocation_admission_context(user=actor),verification_context():
                before=capture_counts()
                if exception_id is not None:row=ExceptionRecord.objects.select_related('task__work_order','task__source_operation','handover','allocation','slice','workflow','approval_task').get(pk=exception_id,company_id=actor.company_id)
                if action=='exception.submit':result,created=_submit(actor,payload,accounts)
                elif action=='input.confirm':result,created=_input(actor,payload,accounts)
                else:result,created=_confirm(actor,row,payload,accounts,code_override)
                from .operation_handover_facts import read_operation_handovers,read_operation_outputs
                if code_override=='production.operation.output.correct':
                    facts=read_operation_outputs(user=actor,task_id=task_id,
                        output_id=result.data.get('outputCorrectionId') or result.data.get('outputId'))
                else:
                    facts=read_operation_handovers(user=actor,task_id=task_id,
                        exception_id=result.pk if isinstance(result,ExceptionRecord) else None,
                        output_id=result.pk if isinstance(result,Output) else None)
                return facts,writes_since(before) if created else writes()
    except IntegrityError:
        fail('CUSTODY_EXCEPTION_RESULT_UNVERIFIED','数据库约束冲突，本次原意图结果待核实；请保留原请求标识只读核查，禁止重复提交。',503)
    except OperationalError:
        fail('CUSTODY_EXCEPTION_RESULT_UNVERIFIED','数据库暂不可用，本次原意图结果待核实；请保留原请求标识只读核查，禁止重复提交。',503)


def confirm_output_correction(*,user,payload,output_id=None):
    return execute_exception(user=user,action='exception.confirm',payload=payload,
        exception_id=payload.get('exceptionId'),code_override='production.operation.output.correct')
