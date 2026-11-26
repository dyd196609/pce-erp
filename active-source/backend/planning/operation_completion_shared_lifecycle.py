"""Read-only shared lifecycle of one already-authorized completion Task.

This is a projection consumer, never a new approval or eligibility authority.
It accepts no HTTP workflow IDs and does not reconstruct production proofs.
"""
from copy import deepcopy
import re

from .work_order_execution_service import _fail,_hash

CONTRACT='PCE-TASK-SHARED-WORKFLOW-LIFECYCLE-V1'
LABELS={'':'尚未创建共享审批','pending':'共享待审','approved':'共享审核已批准',
    'rejected':'共享审核已驳回','closed':'原申请人撤回待审后关闭'}


def _history(obj,workflow_id,company_id):
    from workflow_runtime.models import BusinessStateTransition
    from system.models import OrganizationOperatingAuditRecord
    name=type(obj).__name__;previous='';result=[]
    from .mes_evidence_graph import history as raw_history, audit as raw_audit
    rows=raw_history(name,obj.pk,company_id)
    if rows is NotImplemented:rows=list(BusinessStateTransition.objects.filter(object_type=name,object_id=obj.pk).order_by('version','pk'))
    for index,event in enumerate(rows,1):
        match=re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)',event.audit_reference or '')
        audit=raw_audit(int(match[1]),company_id) if match else None
        if audit is NotImplemented:audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first()
        after=audit.after_snapshot if audit and isinstance(audit.after_snapshot,dict) else {}
        state=after.get('state') if isinstance(after.get('state'),dict) else {}
        if (event.version!=index or event.source_state!=previous or event.target_state not in LABELS
            or event.workflow_instance_id not in (None,workflow_id)
            or not audit or audit.organization_id!=company_id or audit.target_type!=name or audit.target_id!=obj.pk
            or audit.actor_id!=event.operator_id or audit.action_code!=event.action_code or audit.reason!=event.reason
            or state.get('status')!=event.target_state):
            _fail('COMPLETION_SHARED_LIFECYCLE_HISTORY_UNPROVEN','本任务共享历史与原审计、对象或公司不一致。')
        result.append({'id':event.pk,'objectType':name,'objectId':obj.pk,'version':event.version,
            'sourceState':event.source_state,'targetState':event.target_state,
            'sourceStateLabel':LABELS.get(event.source_state,'共享状态待核实'),'targetStateLabel':LABELS[event.target_state],
            'actionCode':event.action_code,'operatorId':event.operator_id,'reason':event.reason,
            'timestamp':event.timestamp.isoformat(),'auditReference':event.audit_reference})
        previous=event.target_state
    if not rows or previous!=obj.status or obj.version!=len(rows):
        _fail('COMPLETION_SHARED_LIFECYCLE_HISTORY_UNPROVEN','本任务共享当前状态或版本与完整持久历史不一致。')
    return {'objectType':name,'objectId':obj.pk,'statusTransitionCount':len(result),
        'statusTransitionHistory':result,'stateMachineConsistent':True}


def task_shared_workflow_lifecycle(*,actor,task,bundle,completion,stage=None):
    from workflow_runtime.models import WorkflowInstance,ApprovalTask,WorkflowClosure
    from workflow_runtime.closure_service import pending_approval_tasks
    from .operation_completion_generation_models import OperationCompletionGeneration as Generation
    from . import operation_completion_v3_authority as v3
    from . import operation_completion_service as legacy
    before=v3._stage_binding(task,actor)
    if not isinstance(bundle,dict):_fail('COMPLETION_SHARED_LIFECYCLE_CONTEXT_INVALID','正式任务核验上下文缺失。')
    snapshot=bundle.get('snapshot')
    if snapshot is not None and (not isinstance(snapshot,dict) or bundle.get('snapshotHash')!=_hash(snapshot)
        or any(snapshot.get(key)!=value for key,value in {'companyId':task.company_id,'taskId':task.pk,
            'workOrderId':task.work_order_id,'taskVersion':task.version,'sourceSnapshotHash':task.source_snapshot_hash,
            'assignmentHash':task.assignment_hash}.items())):
        _fail('COMPLETION_SHARED_LIFECYCLE_CONTEXT_INVALID','共享投影未绑定已验真的本公司准确任务及来源。')
    if stage is not None:
        if not isinstance(stage,v3._CompletionReadStage) or stage.token is not v3._STAGE_TOKEN:
            _fail('COMPLETION_SHARED_LIFECYCLE_CONTEXT_INVALID','定量投影只接受本次正式读取的已验阶段。')
        stage.validate(task,actor,bundle)
        if stage.current!=completion:_fail('COMPLETION_SHARED_LIFECYCLE_CONTEXT_INVALID','当前整体投影与本次验真阶段不一致。')
        proofs=deepcopy(stage.histories or ([completion] if completion else []))
    else:
        if task.execution_mode=='QUANTIFIED':_fail('COMPLETION_SHARED_LIFECYCLE_CONTEXT_INVALID','定量共享投影缺少本次正式验真阶段。')
        # NonQ retains its original validated producer, without constructing a
        # quantitative Stage/account or manufacturing missing workflow rows.
        proofs=deepcopy([completion] if completion else [])
    def finish(value):
        if stage is not None:stage.validate(task,actor,bundle)
        elif v3._stage_binding(task,actor)!=before:
            _fail('COMPLETION_SHARED_LIFECYCLE_READ_CHANGED','共享投影读取期间数据库或人员上下文已变化，请只读重查。')
        return value
    base={'contractVersion':CONTRACT,'currentStateSource':'server','scope':'AUTHORIZED_COMPLETION_TASK',
        'companyId':task.company_id,'taskId':task.pk,'taskSourceSnapshotHash':task.source_snapshot_hash,
        'actorId':actor.pk,'arbitraryWorkflowSelectionAllowed':False,
        'diagnostics':{'authority':'VALIDATED_TASK_COMPLETION_CHAIN_AND_SHARED_PERSISTED_ROWS',
            'globalWorkbenchCovered':False,'proofAndProductionHashModified':False}}
    if not proofs:
        if (WorkflowInstance.objects.filter(document_type=legacy.OBJECT,document_id=task.pk).exists()
            or Generation.objects.filter(task_id=task.pk).exists()):
            _fail('COMPLETION_SHARED_LIFECYCLE_SCOPE_UNPROVEN','存在未被本任务正式完成链核实的共享来源，不能当作零记录。')
        pending_ids=list(pending_approval_tasks(ApprovalTask.objects.none()).values_list('pk',flat=True))
        if pending_ids:_fail('COMPLETION_SHARED_LIFECYCLE_COUNTS_UNPROVEN','空任务范围出现未核实待办。')
        return finish({**base,'availability':'verified_empty','statusLabel':'本任务尚无共享审批申请，已核实无待办或关闭记录',
            'workflowCount':0,'pendingCount':0,'pendingTaskCount':0,'approvedCount':0,'rejectedCount':0,'closedCount':0,
            'pendingTaskIds':pending_ids,'workflows':[],'closures':[],'statusTransitionHistory':[],
            'statusTransitionCount':0,'stateMachineConsistent':True,'pendingHelperApplied':True})
    refs={};proof_generation_ids={p.get('generationId') for p in proofs if p.get('generationId')}
    for proof in proofs:
        wf_id=proof.get('workflowInstanceId');approval_id=proof.get('approvalTaskId')
        if wf_id is None and approval_id is None and proof.get('completionProtocolVersion',2)==2:
            if (WorkflowInstance.objects.filter(document_type=legacy.OBJECT,document_id=task.pk).exists()
                or Generation.objects.filter(task_id=task.pk).exists()):
                _fail('COMPLETION_SHARED_LIFECYCLE_SCOPE_UNPROVEN','旧证明与实际共享对象绑定不一致。')
            return finish({**base,'availability':'legacy_boundary','statusLabel':'旧正式证明未关联共享审批实体；保留原证明，不补建、不推算共享统计',
                'workflowCount':None,'pendingCount':None,'pendingTaskCount':None,'approvedCount':None,'rejectedCount':None,'closedCount':None,
                'pendingTaskIds':None,'workflows':[],'closures':[],'statusTransitionHistory':None,
                'statusTransitionCount':None,'stateMachineConsistent':None,'pendingHelperApplied':False,
                'legacyCompletionReference':proof.get('approvalAuditReference') or proof.get('requestAuditReference')})
        if type(wf_id) is not int or wf_id<=0 or type(approval_id) is not int or approval_id<=0:
            _fail('COMPLETION_SHARED_LIFECYCLE_SCOPE_UNPROVEN','共享投影缺少准确的正式审批身份，不能推算状态。')
        if wf_id in refs:
            if refs[wf_id]!=proof:_fail('COMPLETION_SHARED_LIFECYCLE_SCOPE_UNPROVEN','同一共享流程被不同完成来源重复引用。')
        else:refs[wf_id]=proof
    from .mes_evidence_graph import generations
    raw_generations=generations(task)
    actual_generations=[{'id':r.pk,'company_id':r.company_id,'workflow_instance_id':r.workflow_instance_id} for r in raw_generations]
    actual_workflows=set(WorkflowInstance.objects.filter(document_type=legacy.OBJECT,document_id=task.pk).values_list('pk',flat=True))
    actual_workflows.update(row['workflow_instance_id'] for row in actual_generations if row['workflow_instance_id'])
    if (any(row['company_id']!=task.company_id for row in actual_generations)
        or {row['id'] for row in actual_generations}!=proof_generation_ids or actual_workflows!=set(refs)):
        _fail('COMPLETION_SHARED_LIFECYCLE_SCOPE_UNPROVEN','本任务存在未被正式链核实的共享流程或代次，不能遗漏后当作已核实统计。')
    workflows=[];closures=[];flat={};counts={key:0 for key in ('pending','approved','rejected','closed')};approval_ids=[]
    for wf_id,proof in refs.items():
        generation=None;generation_id=proof.get('generationId')
        if generation_id:
            if type(generation_id) is not int or generation_id<=0:_fail('COMPLETION_SHARED_LIFECYCLE_SCOPE_UNPROVEN','完成代次身份须为准确正整数。')
            generation=next((r for r in raw_generations if r.pk==generation_id and r.task_id==task.pk and r.company_id==task.company_id),None)
            if (not generation or generation.workflow_instance_id!=wf_id or generation.approval_task_id!=proof['approvalTaskId']
                or generation.source_snapshot_hash!=proof.get('sourceSnapshotHash')):
                _fail('COMPLETION_SHARED_LIFECYCLE_SCOPE_UNPROVEN','共享流程的代次、公司、任务或原来源不一致。')
        workflow=generation.workflow_instance if generation and generation.workflow_instance_id==wf_id else WorkflowInstance.objects.filter(pk=wf_id).first()
        approval=generation.approval_task if generation and generation.approval_task_id==proof['approvalTaskId'] and generation.approval_task.workflow_instance_id==wf_id else ApprovalTask.objects.filter(pk=proof['approvalTaskId'],workflow_instance_id=wf_id).first()
        native=proof.get('completionProtocolVersion',2)==3
        expected_type=v3.OBJECT if native else legacy.OBJECT
        expected_id=generation_id if native else task.pk
        expected_state='closed' if proof.get('generationStatusCode')=='superseded' else {'pending_review':'pending','completed':'approved','rejected':'rejected'}.get(proof.get('statusCode'))
        if (not workflow or not approval or workflow.document_type!=expected_type or workflow.document_id!=expected_id
            or workflow.status!=expected_state or approval.status!=expected_state
            or workflow.version!=proof.get('workflowVersion') or approval.version!=proof.get('approvalTaskVersion')):
            _fail('COMPLETION_SHARED_LIFECYCLE_SCOPE_UNPROVEN','共享当前状态或对象不属于本任务已验真的完成链。')
        approval_ids.append(approval.pk);groups=[_history(workflow,wf_id,task.company_id),_history(approval,wf_id,task.company_id)]
        closed=None
        if expected_state=='closed':
            closed=deepcopy(proof.get('closure'))
            entity=WorkflowClosure.objects.filter(pk=generation.closure_id,company_id=task.company_id).first() if generation else None
            if (not isinstance(closed,dict) or not entity or entity.workflow_instance_id!=wf_id or entity.approval_task_id!=approval.pk
                or entity.pk!=closed.get('closureId') or entity.snapshot_hash!=closed.get('proofHash')
                or entity.source_object_type!=v3.OBJECT or entity.source_object_id!=generation.pk
                or entity.replacement_object_id not in proof_generation_ids
                or closed.get('pendingCount')!=0 or closed.get('approvedCount')!=0 or closed.get('rejectedCount')!=0 or closed.get('closedCount')!=1
                or closed.get('reviewed') is not False or closed.get('rejected') is not False or closed.get('approvalDecisionId') is not None):
                _fail('COMPLETION_SHARED_LIFECYCLE_CLOSURE_UNPROVEN','关闭缺少本任务已验真的原申请、真实原因和替代关联。')
            groups.append(_history(entity,wf_id,task.company_id));closures.append(closed)
        for group in groups:
            for event in group['statusTransitionHistory']:flat[event['id']]=event
        counts[expected_state]+=1
        workflows.append({'workflowInstanceId':wf_id,'approvalTaskId':approval.pk,
            'generationId':generation_id,'generationSequence':proof.get('generationSequence'),
            'completionProtocolVersion':proof.get('completionProtocolVersion',2),'statusCode':expected_state,
            'statusLabel':closed['statusLabel'] if closed else LABELS[expected_state],
            'requestAuditReference':proof.get('requestAuditReference'),'approvalAuditReference':proof.get('approvalAuditReference'),
            'closure':closed,'sharedHistory':groups,'stateMachineConsistent':True})
    # A real production consumer of the shared pending predicate. IDs originate
    # exclusively in the authorized Task's validated chain, never in an API arg.
    scoped=ApprovalTask.objects.filter(pk__in=approval_ids,workflow_instance_id__in=list(refs))
    pending_ids=list(pending_approval_tasks(scoped).order_by('pk').values_list('pk',flat=True))
    expected_pending=sorted(row['approvalTaskId'] for row in workflows if row['statusCode']=='pending')
    if pending_ids!=expected_pending or sum(counts.values())!=len(refs):
        _fail('COMPLETION_SHARED_LIFECYCLE_COUNTS_UNPROVEN','本任务真实待办与共享生命周期统计不一致。')
    history=[flat[key] for key in sorted(flat)]
    return finish({**base,'availability':'verified','statusLabel':'本任务共享待办、历史、关闭原因及统计已同源核实',
        'workflowCount':len(refs),'pendingCount':counts['pending'],'pendingTaskCount':len(pending_ids),
        'approvedCount':counts['approved'],'rejectedCount':counts['rejected'],'closedCount':counts['closed'],
        'pendingTaskIds':pending_ids,'pendingHelperApplied':True,'workflows':workflows,'closures':closures,
        'statusTransitionHistory':history,'statusTransitionCount':len(history),'stateMachineConsistent':True})
