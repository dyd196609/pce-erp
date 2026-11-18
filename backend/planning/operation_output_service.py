"""Formal partial output and independent supplementary production reporting."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from django.db import transaction, IntegrityError, OperationalError
from django.utils import timezone
from .operation_handover_core import *
from .operation_handover_core import _hash
from .operation_output_contract import ACTIONS
from .operation_output_authority import (task_context, bind_account, whole_coverage,
    evidence_proof, read_task_quantity_account,reporter_authority)
from .operation_handover_models import (OperationOutputEvidence as Output,
    OperationOutputAllocation as Coverage, OperationCustodySlice as Slice,
    OperationCustodyException as ExceptionRecord)
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_resource_read_scope import scoped_execution_read

COMMON={'taskId','expectedVersion','expectedSourceSnapshotHash','expectedAssignmentHash',
    'expectedStartId','expectedStartSnapshotHash','expectedReleaseRevision','expectedProductionRevision',
    'batchLabel','scopeManifest','quantity','uomId','occurredAt','reason','idempotencyKey',
    'reportAllocations','inputAllocations'}


def _expect(ctx,payload,account):
    expected={'expectedVersion':ctx['task'].version,
        'expectedSourceSnapshotHash':ctx['task'].source_snapshot_hash,
        'expectedAssignmentHash':ctx['task'].assignment_hash,
        'expectedStartId':ctx['start'].pk if ctx['start'] else None,
        'expectedStartSnapshotHash':ctx['snapshot'].get('startSnapshotHash')}
    for key in ('expectedVersion','expectedStartId','expectedReleaseRevision','expectedProductionRevision'):
        if key in payload and (type(payload[key]) is not int or payload[key]<0):
            fail('OUTPUT_EXPECTATION_INVALID','任务及生产／释放版本须为正式非负整数。',400)
    if any(payload.get(k)!=v for k,v in expected.items()):
        fail('OUTPUT_SOURCE_OR_VERSION_CHANGED','任务、开工、人员或原来源已变化，请只读重新核对。')
    if strict_id(payload.get('uomId'),'正式产出单位')!=ctx['unit'].pk:
        fail('OUTPUT_UNIT_MISMATCH','产出必须沿用来源正式单位，不能隐式换算。')
    if payload.get('expectedReleaseRevision',account.release_revision)!=account.release_revision:
        fail('OUTPUT_RELEASE_CHANGED','来源分量释放版本已变化，请只读重查。')
    production_revision=len(ctx['records'])+account.production_revision
    if payload.get('expectedProductionRevision',production_revision)!=production_revision:
        fail('OUTPUT_PRODUCTION_CHANGED','原报工或生产异常版本已变化，请只读重查。')


def _scope(ctx,payload):
    manifest=payload.get('scopeManifest');label=payload.get('batchLabel')
    if (not isinstance(manifest,dict) or not isinstance(manifest.get('reference'),str)
        or len(manifest['reference'].strip())<2 or not isinstance(manifest.get('range'),str)
        or len(manifest['range'].strip())<2 or not isinstance(label,str) or not 1<=len(label.strip())<=160):
        fail('OUTPUT_PHYSICAL_SCOPE_REQUIRED','请填写真实批次标识、可核对清单引用和准确实物范围。',400)
    purpose=manifest.get('inputPurpose')
    if purpose is not None:
        from .operation_handover_authority import is_upstream
        if not isinstance(purpose,dict) or set(purpose)!={'taskId','operationId','workCenterId','reference'}:
            fail('OUTPUT_RANGE_RELEASE_INVALID','同车间投入用途须明确真实目标任务／工序／工作中心及范围依据。',400)
        for key in ('taskId','operationId','workCenterId'):strict_id(purpose[key],'投入用途'+key)
        target=Task.objects.select_related('source_operation','work_order').filter(pk=purpose['taskId'],
            company_id=ctx['task'].company_id,work_order_id=ctx['task'].work_order_id,status='dispatched').first()
        if (not target or target.execution_mode!='QUANTIFIED' or target.source_operation_id!=purpose['operationId']
            or target.work_center_id!=purpose['workCenterId'] or not str(purpose['reference']).strip()
            or not is_upstream(ctx['task'].source_operation,target)):
            fail('OUTPUT_RANGE_RELEASE_UNPROVEN','释放用途未绑定真实同工单定量目标及正式工艺祖先关系。')
    digest=_hash({'taskId':ctx['task'].pk,'manifest':manifest})
    if Output.objects.filter(task_id=ctx['task'].pk,scope_hash=digest).exists():
        fail('OUTPUT_SCOPE_ALREADY_RECORDED','该实物范围已有正式产出声明或确认，不能换key重复增加产出。')
    return manifest,label.strip(),digest


def _coverage(ctx,payload):
    selections=payload.get('reportAllocations')
    if not isinstance(selections,list) or not selections:
        fail('OUTPUT_REPORT_COVERAGE_REQUIRED','请选择真实报工及尚未定位的准确分量。',400)
    mapped={r['id']:r for r in ctx['records']};prepared=[];total=Decimal(0);seen={}
    for item in selections:
        if not isinstance(item,dict) or set(item)!={'reportId','startAtom','endAtom'}:
            fail('OUTPUT_REPORT_COVERAGE_INVALID','报工分量只接受准确报工ID及最小单位起止坐标。',400)
        if type(item['reportId']) is not int or not (record:=mapped.get(item['reportId'])):
            fail('OUTPUT_REPORT_COVERAGE_INVALID','分量来源不是本任务的正式验真报工。')
        if any(not isinstance(item[k],str) or not re.fullmatch(r'0|[1-9][0-9]*',item[k]) for k in ('startAtom','endAtom')):
            fail('OUTPUT_REPORT_COVERAGE_INVALID','报工最小单位坐标必须是规范非负整数。',400)
        lo,hi=int(item['startAtom']),int(item['endAtom'])
        if not 0<=lo<hi<=atoms(record['quantity'],ctx['unit'].decimal_places):
            fail('OUTPUT_REPORT_COVERAGE_EXCEEDED','所选分量超过原正式报工范围。')
        old=[(int(a.start_atom),int(a.end_atom)) for a in Coverage.objects.filter(report_id=item['reportId'],
            evidence__status='confirmed',coverage_kind='RELEASE')]
        if any(max(lo,a)<min(hi,b) for a,b in old+seen.get(item['reportId'],[])):
            fail('OUTPUT_REPORT_ALREADY_RELEASED','该报工分量已定位释放或与本次选择重叠。')
        seen.setdefault(item['reportId'],[]).append((lo,hi))
        amount=from_atoms(hi-lo,ctx['unit'].decimal_places);total=add(total,amount)
        prepared.append({'reportId':item['reportId'],'startAtom':str(lo),'endAtom':str(hi),
            'quantity':text(amount),'sourceHash':_hash(record),'coverageKind':'RELEASE'})
    if 'quantity' in payload and number(payload['quantity'],positive=True,precision=ctx['unit'].decimal_places)!=total:
        fail('OUTPUT_COVERAGE_QUANTITY_MISMATCH','确认数量与所选报工分量之和不一致。')
    return prepared,total


def _insert_coverage(row,items):
    for item in items:
        allocation=Coverage(evidence=row,report_id=item['reportId'],coverage_kind=item['coverageKind'],
            start_atom=item['startAtom'],end_atom=item['endAtom'],quantity=item['quantity'],source_hash=item['sourceHash'])
        allocation._output_allocation_authorized=True
        allocation.save(force_insert=True)


def _mint(row,ctx,actor,code,q,stamp,digest,payload,accounts):
    from .operation_handover_authority import custody_event
    from .operation_handover_authority import tracked_input_scope_exists
    needs_inputs=bool(payload.get('inputAllocations') or tracked_input_scope_exists(ctx['task']))
    root=initialize(Slice,actor=actor,code=code,q=q,status='U',
        source={'outputEvidenceId':row.pk,'sourceHash':row.source_snapshot_hash,'scopeHash':row.scope_hash},
        intent_hash=digest,reason=payload['reason'].strip(),root=row,quantity=row.quantity,start_atom='0',
        end_atom=str(atoms(row.quantity,ctx['unit'].decimal_places)),holder_workshop_id=ctx['task'].workshop_id,
        holder_work_center_id=ctx['task'].work_center_id,frozen=needs_inputs,
        data={'batchLabel':row.batch_label,'scopeManifest':row.scope_manifest,'inputClosureRequired':needs_inputs,
            'normalPurposeActive':bool(row.kind in ('NORMAL_CONFIRM','WHOLE_RELEASE') and row.scope_manifest.get('inputPurpose')),
            'inputAccountingBoundary':'CURRENT_EXPLICIT_RELEASES_ONLY'})
    custody_event(actor=actor,code=code,q=q,task=ctx['task'],kind='OUTPUT_RELEASE',quantity=row.quantity,
        debit='W' if row.kind=='WHOLE_RELEASE' else '',credit='U',stamp=stamp,intent_hash=digest,
        reason=payload['reason'].strip(),slices=[root],data={'outputEvidenceId':row.pk,'effectiveOutputDelta':
            '0' if row.kind=='WHOLE_RELEASE' else row.quantity})
    if needs_inputs:
        if payload.get('inputAllocations') and row.kind!='EXCESS_REPORT':
            from .operation_handover_exceptions import _input
            child={'outputId':row.pk,'expectedVersion':row.version,'expectedSourceSnapshotHash':row.source_snapshot_hash,
                'inputAllocations':deepcopy(payload['inputAllocations']),'occurredAt':offset_iso(stamp),
                'reason':payload['reason'],'idempotencyKey':'embedded-input-'+sha256(payload['idempotencyKey'].encode()).hexdigest()}
            # An explicit compound output/input intention receives its own real
            # input action, qualification, ledger and audit inside this atomic transaction.
            _input(actor,child,accounts)
        else:
            initialize(ExceptionRecord,actor=actor,code=code,q=q,status='pending',source={'outputId':row.pk},
                intent_hash=digest,reason='投入来源范围尚未闭合；冻结本批产出防止旧新双出。',
                task=ctx['task'],slice=root,kind='INPUT_UNPROVEN',original_quantity=row.quantity,
                quantity=row.quantity,occurred_at=stamp,data={'outputId':row.pk})
    return root


def confirm_output(*,actor,payload,accounts,digest=None,context=None):
    payload_guard(payload,COMMON,{'taskId','expectedVersion','expectedSourceSnapshotHash',
        'expectedAssignmentHash','expectedStartId','expectedStartSnapshotHash','reportAllocations',
        'scopeManifest','batchLabel','uomId','occurredAt','reason','idempotencyKey','expectedReleaseRevision','expectedProductionRevision'})
    task=Task.objects.select_related('work_order','source_operation','work_center').filter(pk=payload['taskId'],company_id=actor.company_id).first()
    if not task:fail('OUTPUT_TASK_NOT_VISIBLE','未找到本公司正式来源任务。',403)
    ctx=context if context is not None else task_context(task,actor);account=accounts[task.pk];ctx['account']=account;bind_account(ctx,account)
    code=ACTIONS['confirm'][0];q=qualify(actor,code,task.work_center_id,'ProductionWorkshopTask',task.pk)
    request_hash,replay=intent(actor,code,None,payload)
    if replay:
        row=Output.objects.get(pk=replay.target_entity_id,company_id=actor.company_id)
        evidence_proof(row,ctx);row._validated_output_context=ctx;return row,False
    if not ctx['quantified']:fail('OUTPUT_NON_QUANTITATIVE_NOT_APPLICABLE','仅经过工序不产生数值产出；请沿原合法定量批次办理物流。')
    _expect(ctx,payload,account)
    current=read_task_quantity_account(task,actor,context=ctx)
    if not current['ready']:fail('OUTPUT_CURRENT_PRODUCTION_BLOCKED','；'.join(current['blockingReasons']))
    stamp=occurred(payload['occurredAt'],not_before=ctx['start'].started_at)
    manifest,label,scope_hash=_scope(ctx,payload);coverage,amount=_coverage(ctx,payload)
    whole=whole_coverage(task);kind='WHOLE_RELEASE' if whole.get('valid') else 'NORMAL_CONFIRM'
    source={'task':deepcopy(ctx['snapshot']),'allocations':coverage,'wholeCoverage':whole.get('proof') if whole.get('valid') else None,
        'intentPayload':{k:deepcopy(v) for k,v in payload.items() if k!='idempotencyKey'}}
    row=initialize(Output,actor=actor,code=code,q=q,status='confirmed',source=source,intent_hash=request_hash,
        reason=payload['reason'].strip(),task=task,kind=kind,quantity=text(amount),uom_id=task.workload_uom_id,
        account_key=ctx['accountKey'],batch_label=label,scope_manifest=manifest,scope_hash=scope_hash,
        occurred_at=stamp,confirmed_by=actor,confirmed_at=timezone.now(),data={})
    _insert_coverage(row,coverage);_mint(row,ctx,actor,code,q,stamp,request_hash,payload,accounts)
    bump(account,'release');bump(account,'custody')
    commit_intent(actor,code,payload,request_hash,row,{'outputId':row.pk,'taskId':task.pk,'proofHash':evidence_proof(row,ctx)['proofHash']})
    row._validated_output_context=ctx
    return row,True


def _shared_initial(model,name,actor,output,code,q,reason,**fields):
    from .mes_test_source_bridge import record_audit
    from .operation_output_authority import shared_projection
    from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition
    obj=create_business_object_with_initial_state(model=model,initial_state='pending',**fields)
    audit=record_audit(user=actor,action_code=code,target=obj,target_type=name,target_no=f'Output:{output.pk}',
        before={'status':'','version':None},after={'status':'pending','version':obj.version,'outputEvidenceId':output.pk,
            'businessObjectType':type(output).__name__,'businessObjectId':output.pk,'sourceHash':output.source_snapshot_hash,
            'objectProjection':shared_projection(obj)},
        authorization=q['authorization'],reason=reason)
    record_projected_business_transition(object_type=name,object_id=obj.pk,source_state='',target_state='pending',
        action_code=code,operator=actor,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','pending')})
    return obj


def _review_proof(actor,row,payload,q,decision,stamp,registered_at=None):
    """Bind a persisted Decision to its actual intent before the write ledger exists."""
    from .mes_test_source_bridge import record_audit
    from .operation_output_authority import decision_projection,shared_projection
    assert_actual_qualification(actor,q,stamp)
    proof={'companyId':row.company_id,'businessObjectType':type(row).__name__,'businessObjectId':row.pk,
        'sourceHash':row.source_snapshot_hash,'requestObjectId':row.pk,'actorId':actor.pk,
        'reviewerEmployeeId':q['currentActorEvidence']['employeeId'],
        'intentPayload':{k:deepcopy(v) for k,v in payload.items() if k!='idempotencyKey'},
        'requestHash':decision.decision_hash,'requestKeyHash':sha256(payload['idempotencyKey'].encode()).hexdigest(),
        'parentVersionBefore':row.version,'parentVersionAfter':row.version+1,
        'parentTargetState':'confirmed' if decision.decision=='approved' else 'rejected',
        'workflowId':row.workflow_id,'workflowVersionBefore':row.workflow.version,
        'workflowVersionAfter':row.workflow.version+1,'approvalTaskId':row.approval_task_id,
        'approvalTaskVersionBefore':row.approval_task.version,'approvalTaskVersionAfter':row.approval_task.version+1,
        'sharedBefore':{'WorkflowInstance':shared_projection(row.workflow),'ApprovalTask':shared_projection(row.approval_task)},
        'actualReviewedAt':stamp.isoformat(),'parentConfirmedAt':registered_at.isoformat() if registered_at else None,
        'qualification':deepcopy(q),'decision':decision_projection(decision)}
    audit=record_audit(user=actor,action_code=decision.action_id,target=decision,target_type='ApprovalDecision',
        target_no=f'{type(row).__name__}:{row.pk}',before={'decision':None},after={'reviewProof':deepcopy(proof)},
        authorization=q['authorization'],reason=payload['reason'].strip(),work_order=row.task.work_order)
    return {**proof,'decisionAuditReference':f'OrganizationOperatingAuditRecord:{audit.pk}'}


def _shared_decide(obj,actor,row,code,q,reason,target,review_proof):
    from .mes_test_source_bridge import record_audit
    from .operation_output_authority import shared_projection
    from workflow_runtime.state_transitions import transition_business_object
    obj.completed_at=timezone.now()
    after_projection={**shared_projection(obj),'status':target,'version':obj.version+1}
    audit=record_audit(user=actor,action_code=code,target=obj,target_type=type(obj).__name__,target_no=f'Output:{row.pk}',
        before={'status':'pending','version':obj.version},after={'status':target,'version':obj.version+1,
            'completedAt':obj.completed_at.isoformat(),'outputEvidenceId':row.pk,
            'businessObjectType':type(row).__name__,'businessObjectId':row.pk,'sourceHash':row.source_snapshot_hash,
            'reviewProof':deepcopy(review_proof),'objectProjection':after_projection},
        authorization=q['authorization'],reason=reason)
    obj.save(update_fields=['completed_at'])
    transition_business_object(business_object=obj,object_type=type(obj).__name__,source_state='pending',target_state=target,
        action_code=code,operator=actor,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
        allowed_transitions={('pending',target)},updated_at_field=None)


def _declare_excess(actor,payload,accounts):
    from workflow_runtime.models import WorkflowInstance,ApprovalTask
    from .operation_handover_permissions import reviewer_role_for
    payload_guard(payload,COMMON,{'taskId','expectedVersion','expectedSourceSnapshotHash','expectedAssignmentHash',
        'expectedStartId','expectedStartSnapshotHash','quantity','uomId','batchLabel','scopeManifest','occurredAt','reason','idempotencyKey','expectedReleaseRevision','expectedProductionRevision'})
    if (isinstance(payload.get('scopeManifest'),dict) and 'inputPurpose' in payload['scopeManifest']
        or 'inputAllocations' in payload or 'reportAllocations' in payload):
        fail('EXCESS_SOURCE_RELEASE_NOT_AUTHORIZED','执行人补充报工不签发来源范围释放或投入证明；请待真实来源负责人另行明确办理。',400)
    task=Task.objects.select_related('work_order','source_operation','work_center').filter(pk=payload['taskId'],company_id=actor.company_id).first()
    if not task:fail('OUTPUT_TASK_NOT_VISIBLE','未找到本公司实际开工任务。',403)
    ctx=task_context(task,actor);account=accounts[task.pk];bind_account(ctx,account)
    code=ACTIONS['excess.report'][0];q=qualify(actor,code,task.work_center_id,'ProductionWorkshopTask',task.pk)
    if ctx['start'].started_by_id!=actor.pk or task.assignment_snapshot.get('userId')!=actor.pk:
        fail('EXCESS_ACTUAL_EXECUTOR_REQUIRED','须由原冻结执行人及实际开工人本人补充真实超产事实。',403)
    original_authority=reporter_authority(ctx,actor)
    if not original_authority['ready']:fail('EXCESS_ORIGINAL_REPORT_AUTHORITY_MISSING','；'.join(original_authority['missingItems']),403)
    q={**q,'originalReportAuthority':original_authority}
    digest,replay=intent(actor,code,None,payload)
    if replay:
        row=Output.objects.get(pk=replay.target_entity_id,company_id=actor.company_id);evidence_proof(row,ctx);return row,False
    if not ctx['quantified']:fail('OUTPUT_NON_QUANTITATIVE_NOT_APPLICABLE','无投产统计量工序不能申报数值超产。')
    _expect(ctx,payload,account)
    manifest,label,scope_hash=_scope(ctx,payload);amount=number(payload['quantity'],positive=True,precision=ctx['unit'].decimal_places)
    stamp=occurred(payload['occurredAt'],not_before=ctx['start'].started_at)
    row=initialize(Output,actor=actor,code=code,q=q,status='declared',
        source={'task':ctx['snapshot'],'allocations':[],
            'intentPayload':{k:deepcopy(v) for k,v in payload.items() if k!='idempotencyKey'}},intent_hash=digest,reason=payload['reason'].strip(),
        task=task,kind='EXCESS_REPORT',quantity=text(amount),uom_id=task.workload_uom_id,account_key=ctx['accountKey'],
        batch_label=label,scope_manifest=manifest,scope_hash=scope_hash,occurred_at=stamp,
        data={'inputAllocations':deepcopy(payload.get('inputAllocations',[]))})
    reviewer_role=reviewer_role_for(user=actor,work_center_id=task.work_center_id)
    workflow=_shared_initial(WorkflowInstance,'WorkflowInstance',actor,row,code,q,payload['reason'].strip(),
        instance_no=f'MES-OUTPUT-{actor.company_id}-{row.pk}',process_definition_id=q['definitionId'],
        document_type='OperationOutputEvidence',document_id=row.pk,current_step=1,total_steps=1,version=1)
    approval=_shared_initial(ApprovalTask,'ApprovalTask',actor,row,code,q,payload['reason'].strip(),
        task_no=f'MES-OUTPUT-REVIEW-{actor.company_id}-{row.pk}',workflow_instance=workflow,step_no=1,
        required_role_code=reviewer_role,minimum_approvals=1,allow_parallel=False,version=1)
    project(row,workflow=workflow,approval_task=approval)
    bump(account,'production')
    commit_intent(actor,code,payload,digest,row,{'outputId':row.pk,'taskId':task.pk,'workflowInstanceId':workflow.pk,'approvalTaskId':approval.pk})
    ctx['account']=account;row._validated_output_context=ctx
    return row,True


def _review_excess(actor,row,payload,accounts):
    from workflow_runtime.models import ApprovalDecision
    payload_guard(payload,{'expectedVersion','expectedSourceSnapshotHash','expectedWorkflowVersion','expectedApprovalTaskVersion',
        'decision','occurredAt','reason','idempotencyKey'}, {'expectedVersion','expectedSourceSnapshotHash','expectedWorkflowVersion',
        'expectedApprovalTaskVersion','decision','occurredAt','reason','idempotencyKey'})
    for key in ('expectedVersion','expectedWorkflowVersion','expectedApprovalTaskVersion'):strict_id(payload[key],key,zero=True)
    ctx=task_context(row.task,actor);account=accounts[row.task_id];bind_account(ctx,account)
    code=ACTIONS['excess.review'][0];q=qualify(actor,code,row.task.work_center_id,'OperationOutputEvidence',row.pk,'declared')
    evidence_proof(row,ctx);digest,replay=intent(actor,code,row.pk,payload)
    if replay:row._validated_output_context=ctx;return row,False
    if (row.kind!='EXCESS_REPORT' or row.status!='declared' or row.version!=payload['expectedVersion']
        or row.source_snapshot_hash!=payload['expectedSourceSnapshotHash']
        or row.workflow.version!=payload['expectedWorkflowVersion'] or row.approval_task.version!=payload['expectedApprovalTaskVersion']
        or row.workflow.status!='pending' or row.approval_task.status!='pending'):
        fail('EXCESS_REVIEW_VERSION_CHANGED','超产声明或共享审核对象版本已变化。')
    employee=q['currentActorEvidence'].get('employeeId')
    if (actor.pk==row.created_by_id or employee==row.qualification_snapshot['currentActorEvidence'].get('employeeId')
        or row.approval_task.required_role_code not in q.get('roleCodes',[])):
        fail('EXCESS_REVIEW_NOT_INDEPENDENT','须由不同真实员工及正式生产跟单审核角色确认。',403)
    if payload['decision'] not in ('approve','reject'):
        fail('EXCESS_REVIEW_INTENT_INVALID','请明确选择确认或拒绝本次超产事实。',400)
    reviewed_at=occurred(payload['occurredAt'],not_before=row.occurred_at)
    approved=payload['decision']=='approve'
    if approved and ctx['R']!=ctx['P']:
        fail('EXCESS_NORMAL_REPORT_NOT_REACHED','原正式正常报工尚未达到P，超产仅保留待核，不得绕过剩余量或精度限制。')
    target='approved' if approved else 'rejected'
    decision=ApprovalDecision.objects.create(task=row.approval_task,decision_sequence=1,actor=actor,decision=target,
        comment=payload['reason'].strip(),action_id=code,idempotency_key=payload['idempotencyKey'],decision_hash=digest)
    registered_at=timezone.now()
    review_proof=_review_proof(actor,row,payload,q,decision,reviewed_at,registered_at)
    _shared_decide(row.approval_task,actor,row,code,q,payload['reason'].strip(),target,review_proof)
    _shared_decide(row.workflow,actor,row,code,q,payload['reason'].strip(),target,review_proof)
    project(row,confirmed_by=actor,confirmed_at=registered_at,approval_decision=decision,
        data={**row.data,'reviewerEmployeeId':employee,'reviewedAt':reviewed_at.isoformat(),'reviewProof':review_proof})
    transition(row,'confirmed' if approved else 'rejected',actor=actor,code=code,q=q,reason=payload['reason'].strip())
    bump(account,'production')
    if approved:
        mint_payload={'reason':payload['reason'],'inputAllocations':row.data.get('inputAllocations',[]),
            'idempotencyKey':payload['idempotencyKey']}
        _mint(row,ctx,actor,code,q,reviewed_at,digest,mint_payload,accounts);bump(account,'custody')
    commit_intent(actor,code,payload,digest,row,{'outputId':row.pk,'taskId':row.task_id,'decisionId':decision.pk,
        'proofHash':evidence_proof(row,ctx)['proofHash']})
    ctx['account']=account;row._validated_output_context=ctx
    return row,True


def execute_output(*,user,action,payload,output_id=None):
    actor=actor_for(user)
    if action not in ('confirm','excess.report','excess.review','correct'):
        fail('OUTPUT_ACTION_INVALID','未注册的正式产出动作。',400)
    if action=='correct':
        from .operation_handover_exceptions import confirm_output_correction
        return confirm_output_correction(user=user,payload=payload,output_id=output_id)
    task_id=payload.get('taskId') if isinstance(payload,dict) else None
    row=None
    if output_id is not None:
        row=Output.objects.select_related('task__work_order','task__source_operation','task__work_center','workflow','approval_task').filter(pk=output_id,company_id=actor.company_id).first()
        if not row:fail('OUTPUT_NOT_VISIBLE','未找到本公司正式产出记录。',403)
        task_id=row.task_id
    task_ids=[task_id]
    inputs=(payload.get('inputAllocations',[]) if isinstance(payload,dict) else []) or (row.data.get('inputAllocations',[]) if row else [])
    ids=[i.get('sliceId') for i in inputs if isinstance(i,dict)]
    task_ids.extend(Slice.objects.filter(pk__in=ids,company_id=actor.company_id).values_list('root__task_id',flat=True))
    try:
        with transaction.atomic():
            accounts=lock_accounts(actor,task_ids)
            from .mes_test_source_bridge import allocation_admission_context
            from .operation_predecessor_authority import verification_context
            with allocation_admission_context(user=actor),verification_context():
                before=capture_counts()
                if output_id is not None:row=Output.objects.select_related('task__work_order','task__source_operation','task__work_center','workflow','approval_task').get(pk=output_id,company_id=actor.company_id)
                if action=='confirm':row,created=confirm_output(actor=actor,payload=payload,accounts=accounts)
                elif action=='excess.report':row,created=_declare_excess(actor,payload,accounts)
                else:row,created=_review_excess(actor,row,payload,accounts)
                from .operation_handover_facts import read_operation_outputs
                facts=read_operation_outputs(user=actor,task_id=task_id,output_id=row.pk,
                    _context=getattr(row,'_validated_output_context',None))
                return facts,writes_since(before) if created else writes()
    except IntegrityError:
        fail('OUTPUT_RESULT_UNVERIFIED','数据库约束冲突，本次原意图结果待核实；请保留原请求标识只读核查，禁止重复提交。',503)
    except OperationalError:
        fail('OUTPUT_RESULT_UNVERIFIED','数据库暂不可用，本次原意图结果待核实；请保留原请求标识只读核查，禁止重复提交。',503)
