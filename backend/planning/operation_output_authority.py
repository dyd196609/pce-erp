"""One authoritative quantity basis; native reports remain bounded and intact."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from .operation_handover_core import (fail, number, text, add, atoms, from_atoms,
    verify_record, _hash)
from .operation_handover_models import (OperationQuantityAccount, OperationOutputEvidence,
    OperationOutputAllocation, OperationCustodySlice, OperationCustodyException)

_CONTEXT_TOKEN=object()


def _context_epoch():
    from django.db import connection
    from .operation_predecessor_authority import current_rollback_generation
    connection.ensure_connection();raw=connection.connection
    if connection.vendor=='sqlite':
        with connection.cursor() as cursor:cursor.execute('PRAGMA data_version');version=cursor.fetchone()[0]
    else:version=None
    outer=id(connection.atomic_blocks[0]) if connection.in_atomic_block and connection.atomic_blocks else None
    return (connection.alias,str(connection.settings_dict.get('NAME')),id(raw),outer,
        getattr(raw,'total_changes',None),version,current_rollback_generation())


def _context_digest(ctx):
    account=ctx.get('account');start=ctx.get('start');source=ctx['source']
    return _hash({'snapshot':ctx['snapshot'],'records':ctx['records'],'P':str(ctx.get('P')),
        'R':str(ctx.get('R')),'quantified':ctx['quantified'],'unitSnapshot':ctx.get('unitSnapshot'),
        'blockingIssues':ctx['blockingIssues'],'sourceProof':source,'startId':start.pk if start else None,
        'startSourceHash':start.source_snapshot_hash if start else None,
        'account':None if account is None else {k:getattr(account,k) for k in ('pk','company_id','task_id','revision',
            'account_key','source_hash','production_revision','release_revision','custody_revision')}})


class _NativeTaskContext(dict):
    pass


def _seal_context(value,actor):
    from .operation_predecessor_authority import _context
    result=_NativeTaskContext(value);result._token=_CONTEXT_TOKEN;result._actor=actor
    result._read_owner=_context.get()
    result._binding=(value['task'].pk,value['task'].company_id,value['task'].version,value['task'].source_snapshot_hash,
        value['task'].assignment_hash,value['task'].execution_mode)
    result._digest=_context_digest(result);result._epoch=_context_epoch()
    return result


def validated_task_context(task,actor=None,context=None):
    from .operation_predecessor_authority import _context
    if context is None:return task_context(task,actor)
    binding=(task.pk,task.company_id,task.version,task.source_snapshot_hash,task.assignment_hash,task.execution_mode)
    if (not isinstance(context,_NativeTaskContext) or context._token is not _CONTEXT_TOKEN
        or context._binding!=binding
        or actor is not None and (context._actor.pk!=actor.pk or actor.company_id!=task.company_id)):
        fail('OUTPUT_VERIFIED_CONTEXT_MISMATCH','原生已验上下文与当前人员／公司／任务／来源不一致，不能从外部字典补齐。')
    if context._read_owner is None or context._read_owner is not _context.get() or context._epoch!=_context_epoch():
        return task_context(task,actor or context._actor)
    if context._digest!=_context_digest(context):fail('OUTPUT_VERIFIED_CONTEXT_MISMATCH','原生上下文内容或账户投影被内存修改，禁止继续复用。')
    return context


def task_context(task, actor=None):
    from .operation_predecessor_authority import _context
    from django.db import connection
    context=_context.get()
    if context is None or connection.vendor!='sqlite':return _task_context_uncached(task,actor)
    key=(_context_epoch(),tuple((f.attname,repr(getattr(task,f.attname))) for f in task._meta.concrete_fields),
        None if actor is None else (actor.pk,actor.company_id,actor.is_active))
    cache=context.setdefault('nativeTaskReadContexts',{})
    if key in cache:return validated_task_context(task,actor,cache[key])
    result=_task_context_uncached(task,actor)
    cache[key]=result
    return result

def _task_context_uncached(task, actor=None):
    from . import mes_test_source_bridge as starts
    from . import operation_report_service as reports
    from .operation_start_models import ProductionOperationStart
    start = ProductionOperationStart.objects.select_related('started_by').defer('started_by__password').filter(task_id=task.pk).first()
    if actor is None:
        from django.contrib.auth import get_user_model
        actor=start.started_by if start else get_user_model().objects.defer('password').filter(pk=task.dispatched_by_id).first()
    source = starts._source(task, actor)
    if start:
        starts._verify_record(start, task)
    if task.execution_mode != 'QUANTIFIED':
        return _seal_context({'task':task,'source':source,'start':start,'quantified':False,'P':None,
            'records':[],'R':None,'snapshot':{'taskId':task.pk,'sourceSnapshotHash':task.source_snapshot_hash},
            'blockingIssues':['本节点无投产统计量，不适用定量产出；工程参考量不得作P或E。']},actor)
    unit, unit_snapshot = reports._unit(task)
    records, total = reports._reports(task, start) if start else ([], Decimal(0))
    quantity = reports._quantity_facts(task, unit, total)
    snapshot = {'companyId':task.company_id,'workOrderId':task.work_order_id,'taskId':task.pk,
        'sourceOperationId':task.source_operation_id,'taskVersion':task.version,
        'workOrderVersion':task.work_order_version,'sourceSnapshotHash':task.source_snapshot_hash,
        'operationSnapshotHash':task.source_operation.snapshot_hash,'assignmentHash':task.assignment_hash,
        'startId':start.pk if start else None,'startSnapshotHash':_hash(reports._start_snapshot(start)) if start else None,
        'P':task.workload_quantity,'unitSnapshot':unit_snapshot,'reportSetHash':_hash(records)}
    key = _hash({k:snapshot[k] for k in ('companyId','workOrderId','taskId','sourceOperationId',
        'taskVersion','sourceSnapshotHash','P','unitSnapshot')})
    account = OperationQuantityAccount.objects.filter(task_id=task.pk).first()
    issues = ([] if source['ready'] else [source['statusLabel']]) + ([] if start else ['来源任务尚无正式实际开工。'])
    if account and account.account_key and (account.company_id != task.company_id
        or account.account_key != key or account.source_hash != task.source_snapshot_hash):
        issues.append('数量账户原计划谱系与当前任务／单位／来源不一致，禁止另开额度。')
    return _seal_context({'task':task,'source':source,'start':start,'quantified':True,'unit':unit,
        'unitSnapshot':unit_snapshot,'P':Decimal(task.workload_quantity),'R':total,
        'quantity':quantity,'records':records,'snapshot':snapshot,'accountKey':key,
        'account':account,'blockingIssues':issues},actor)


def bind_account(ctx, account):
    if ctx['blockingIssues'] or not ctx['quantified']:
        fail('OUTPUT_SOURCE_NOT_READY', '；'.join(ctx['blockingIssues']))
    if account.account_key and account.account_key != ctx['accountKey']:
        fail('OUTPUT_PLAN_LINEAGE_CHANGED', '同一来源任务不能通过改变Hash另开计划额度。')
    if not account.account_key:
        OperationQuantityAccount.objects.filter(pk=account.pk, revision=account.revision).update(
            account_key=ctx['accountKey'],source_hash=ctx['task'].source_snapshot_hash)
        account.account_key=ctx['accountKey'];account.source_hash=ctx['task'].source_snapshot_hash


def whole_coverage(task, *, context=None):
    from .operation_completion_v3_authority import read_quantitative_whole_coverage
    return read_quantitative_whole_coverage(task,native_production_context=validated_task_context(task,context=context)) if context is not None else read_quantitative_whole_coverage(task)


def reporter_authority(ctx,actor):
    """Reuse original reporter duties without granting its quantity-capped action."""
    from .operation_report_service import _qualification
    original=_qualification(actor,ctx['task'],ctx['start'],ctx['source'],ctx['quantity'])
    cap='报工量已达任务量，不能继续报量；此状态不表示工序完工。'
    issues=[item for item in original['missingItems'] if not (ctx['quantity']['quantityStatusCode']=='quantity_reached' and item==cap)]
    return {'ready':not issues,'missingItems':issues,'currentActorEvidence':original['currentActorEvidence'],
        'definitionId':original['definitionId'],'nodeId':original['nodeId'],'authorization':original['authorization'],
        'sourceSnapshotHash':ctx['snapshot']['sourceSnapshotHash'],'originalReportQuantityStatusCode':ctx['quantity']['quantityStatusCode'],
        'originalReportCapPreserved':True}


def shared_projection(obj):
    return {field.attname:(value.isoformat() if hasattr(value,'isoformat') else value)
        for field in obj._meta.concrete_fields for value in (getattr(obj,field.attname),)}


def decision_projection(decision):
    return {'id':decision.pk,'taskId':decision.task_id,'sequence':decision.decision_sequence,
        'actorId':decision.actor_id,'decision':decision.decision,'comment':decision.comment,
        'actionCode':decision.action_id,'requestKeyHash':sha256(decision.idempotency_key.encode()).hexdigest(),
        'decisionHash':decision.decision_hash,'createdAt':decision.created_at.isoformat(),
        'completedAt':decision.completed_at.isoformat()}


def verify_shared_review(row):
    from workflow_runtime.models import WorkflowInstance, ApprovalTask, ApprovalDecision, BusinessStateTransition
    from system.models import OrganizationOperatingAuditRecord
    import re
    if not isinstance(row.data,dict) or not isinstance(row.qualification_snapshot,dict):
        fail('OUTPUT_REVIEW_UNPROVEN','审核业务证明结构损坏。')
    if not row.workflow_id or not row.approval_task_id or not row.approval_decision_id:
        fail('OUTPUT_REVIEW_UNPROVEN', '补充产出缺少共享审批及独立决策。')
    workflow = WorkflowInstance.objects.filter(pk=row.workflow_id).first()
    approval = ApprovalTask.objects.filter(pk=row.approval_task_id).first()
    decision = ApprovalDecision.objects.filter(pk=row.approval_decision_id).first()
    terminal='approved' if row.status=='confirmed' else 'rejected' if row.status=='rejected' else None
    proof=row.data.get('reviewProof');kind=type(row).__name__
    if (not terminal or not isinstance(proof,dict) or not workflow or not approval or not decision or workflow.document_type != kind
        or workflow.document_id != row.pk or workflow.status != terminal
        or approval.workflow_instance_id != workflow.pk or approval.status != terminal
        or decision.task_id != approval.pk or decision.decision != terminal
        or decision.actor_id != row.confirmed_by_id or decision.actor_id == row.created_by_id):
        fail('OUTPUT_REVIEW_UNPROVEN', '共享审批对象、独立人员或批准决策不一致。')
    original_evidence=row.qualification_snapshot.get('currentActorEvidence')
    if not isinstance(original_evidence,dict):fail('OUTPUT_REVIEW_SEPARATION_UNPROVEN','原申请真实人员证明结构损坏。')
    initial_employee = original_evidence.get('employeeId')
    reviewed_employee = row.data.get('reviewerEmployeeId')
    if not initial_employee or not reviewed_employee or reviewed_employee == initial_employee:
        fail('OUTPUT_REVIEW_SEPARATION_UNPROVEN', '补充产出申请和确认须为不同真实员工。')
    payload=proof.get('intentPayload');q=proof.get('qualification')
    if (not isinstance(q,dict) or not isinstance(q.get('authorization'),dict)
        or not isinstance(q.get('currentActorEvidence'),dict) or not isinstance(q.get('actionContract'),dict)
        or not isinstance(q.get('roleCodes'),list)
        or not isinstance(proof.get('sharedBefore'),dict)):
        fail('OUTPUT_REVIEW_DECISION_DAMAGED','审核原资格或共享版本结构损坏。')
    expected_wc=row.task.work_center_id if kind=='OperationOutputEvidence' else row.source_snapshot.get('intentPayload',{}).get('workCenterId')
    expected_code='production.operation.output.excess.review' if kind=='OperationOutputEvidence' else 'production.operation.handover.exception.confirm'
    allowed_codes={expected_code}
    if kind=='OperationCustodyException' and row.kind=='OUTPUT_CORRECTION':allowed_codes.add('production.operation.output.correct')
    if (not isinstance(payload,dict) or 'idempotencyKey' in payload or not isinstance(q,dict)
        or proof.get('decision')!=decision_projection(decision) or decision.action_id not in allowed_codes
        or type(decision.decision_sequence) is not int or decision.decision_sequence!=1
        or ApprovalDecision.objects.filter(task_id=approval.pk).count()!=1
        or proof.get('companyId')!=row.company_id or proof.get('businessObjectType')!=kind
        or proof.get('businessObjectId')!=row.pk or proof.get('sourceHash')!=row.source_snapshot_hash
        or proof.get('requestObjectId')!=row.pk or proof.get('actorId')!=decision.actor_id
        or proof.get('reviewerEmployeeId')!=reviewed_employee
        or proof.get('requestKeyHash')!=sha256(decision.idempotency_key.encode()).hexdigest()
        or proof.get('requestHash')!=decision.decision_hash
        or _hash({'actorId':decision.actor_id,'actionCode':decision.action_id,'objectId':row.pk,'payload':payload})!=decision.decision_hash
        or payload.get('decision')!=('approve' if terminal=='approved' else 'reject')
        or not isinstance(payload.get('reason'),str) or payload['reason'].strip()!=decision.comment
        or payload.get('expectedSourceSnapshotHash')!=row.source_snapshot_hash
        or any(type(payload.get(k)) is not int or payload[k]<0 for k in ('expectedVersion','expectedWorkflowVersion','expectedApprovalTaskVersion'))
        or proof.get('parentVersionBefore')!=payload['expectedVersion'] or proof.get('parentVersionAfter')!=row.version
        or row.version!=payload['expectedVersion']+1 or proof.get('parentTargetState')!=row.status
        or proof.get('workflowId')!=workflow.pk or proof.get('approvalTaskId')!=approval.pk
        or proof.get('workflowVersionBefore')!=payload['expectedWorkflowVersion']
        or proof.get('workflowVersionAfter')!=workflow.version or workflow.version!=payload['expectedWorkflowVersion']+1
        or proof.get('approvalTaskVersionBefore')!=payload['expectedApprovalTaskVersion']
        or proof.get('approvalTaskVersionAfter')!=approval.version or approval.version!=payload['expectedApprovalTaskVersion']+1
        or q.get('ready') is not True or q.get('authorization',{}).get('allowed') is not True
        or q.get('actionContract',{}).get('actionCode')!=decision.action_id
        or q.get('currentActorEvidence',{}).get('employeeId')!=reviewed_employee
        or q['currentActorEvidence'].get('userId')!=decision.actor_id or q['currentActorEvidence'].get('companyId')!=row.company_id
        or q['currentActorEvidence'].get('workCenterId')!=expected_wc
        or workflow.process_definition_id!=row.qualification_snapshot.get('definitionId')
        or approval.required_role_code not in q.get('roleCodes',[])):
        fail('OUTPUT_REVIEW_DECISION_DAMAGED','独立审核决定、原请求、人员或版本与正式审计绑定不一致。')
    from .operation_handover_core import occurred
    confirmed_at=getattr(row,'confirmed_at',None)
    if (proof.get('actualReviewedAt')!=occurred(payload.get('occurredAt'),not_before=row.occurred_at).isoformat()
        or row.data.get('reviewedAt')!=proof.get('actualReviewedAt')
        or proof.get('parentConfirmedAt')!=(confirmed_at.isoformat() if confirmed_at else None)):
        fail('OUTPUT_REVIEW_DECISION_DAMAGED','独立审核实际发生时点与原意图不一致。')
    def audit_for(reference,obj_type,obj_id,actor_id,code,reason):
        match=re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)',reference or '')
        audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
        if (not audit or not isinstance(audit.before_snapshot,dict) or not isinstance(audit.after_snapshot,dict)
            or not isinstance(audit.before_snapshot.get('state'),dict) or not isinstance(audit.after_snapshot.get('state'),dict)
            or audit.target_type!=obj_type or audit.target_id!=obj_id
            or audit.organization_id!=row.company_id or audit.actor_id!=actor_id
            or audit.action_code!=code or audit.reason!=reason):
            fail('OUTPUT_REVIEW_HISTORY_UNPROVEN','审核审计的公司、对象、动作或真实人员不一致。')
        return audit
    decision_audit=audit_for(proof.get('decisionAuditReference'),'ApprovalDecision',decision.pk,
        decision.actor_id,decision.action_id,decision.comment)
    if (decision_audit.before_snapshot.get('state')!={'decision':None}
        or decision_audit.after_snapshot.get('state')!={'reviewProof':{k:v for k,v in proof.items() if k!='decisionAuditReference'}}):
        fail('OUTPUT_REVIEW_DECISION_DAMAGED','正式独立决定缺少不可变审计证明。')
    parent_events=list(BusinessStateTransition.objects.filter(object_type=kind,object_id=row.pk).order_by('version','pk'))
    parent_event=parent_events[-1] if parent_events else None
    if not parent_event or parent_event.target_state!=row.status or parent_event.operator_id!=decision.actor_id or parent_event.action_code!=decision.action_id:
        fail('OUTPUT_REVIEW_HISTORY_UNPROVEN','业务终态未绑定本次真实独立决定。')
    parent_audit=audit_for(parent_event.audit_reference,kind,row.pk,decision.actor_id,decision.action_id,decision.comment)
    parent_state=parent_audit.after_snapshot.get('state',{})
    if (not isinstance(parent_state.get('projectionData'),dict)
        or parent_state['projectionData'].get('reviewProof')!=proof or parent_state.get('qualification')!=q
        or parent_state.get('sourceHash')!=row.source_snapshot_hash
        or parent_state.get('row')!={'status':row.status,'version':row.version}
        or parent_audit.before_snapshot.get('state',{}).get('status')!=('declared' if kind=='OperationOutputEvidence' else 'pending')):
        fail('OUTPUT_REVIEW_HISTORY_UNPROVEN','业务终态审计、原生产证明与独立审核绑定不一致。')
    shared = []
    for obj in (workflow, approval):
        events = list(BusinessStateTransition.objects.filter(object_type=type(obj).__name__,object_id=obj.pk).order_by('version','pk'))
        if len(events) != 2 or [(e.source_state,e.target_state) for e in events] != [('', 'pending'),('pending',terminal)]:
            fail('OUTPUT_REVIEW_HISTORY_UNPROVEN', '共享审批必须具备完整正式申请与批准历史。')
        before=proof.get('sharedBefore',{}).get(type(obj).__name__)
        projection=shared_projection(obj)
        if (not isinstance(before,dict) or before.get('status')!='pending' or before.get('completed_at') is not None
            or before.get('version')!=1 or obj.version!=2 or obj.completed_at is None
            or {k:v for k,v in before.items() if k not in ('status','version','completed_at')}
                !={k:v for k,v in projection.items() if k not in ('status','version','completed_at')}):
            fail('OUTPUT_REVIEW_HISTORY_UNPROVEN','共享审批身份、版本或终态字段被修改。')
        for index,e in enumerate(events,1):
            audit=audit_for(e.audit_reference,type(obj).__name__,obj.pk,e.operator_id,e.action_code,e.reason)
            state=audit.after_snapshot.get('state',{})
            if (e.version!=index or state.get('outputEvidenceId')!=row.pk or state.get('businessObjectType')!=kind
                or state.get('businessObjectId')!=row.pk or state.get('sourceHash')!=row.source_snapshot_hash
                or state.get('status')!=e.target_state or state.get('version')!=index
                or state.get('objectProjection')!=(before if index==1 else projection)):
                fail('OUTPUT_REVIEW_HISTORY_UNPROVEN', '共享审核审计未绑定准确补充产出对象。')
            if index==1:
                if e.operator_id!=row.created_by_id or e.action_code!=row.qualification_snapshot.get('actionContract',{}).get('actionCode'):
                    fail('OUTPUT_REVIEW_HISTORY_UNPROVEN','共享申请与原真实申报人员或动作不一致。')
            elif (e.operator_id!=decision.actor_id or e.action_code!=decision.action_id or e.reason!=decision.comment
                or state.get('reviewProof')!=proof or state.get('completedAt')!=obj.completed_at.isoformat()
                or audit.before_snapshot.get('state')!={'status':'pending','version':1}):
                fail('OUTPUT_REVIEW_HISTORY_UNPROVEN','共享终态与原独立决定、意图或版本不一致。')
        shared.append({'objectType':type(obj).__name__,'id':obj.pk,'version':obj.version,
            'auditReferences':[e.audit_reference for e in events]})
    return {'workflowInstanceId':workflow.pk,'approvalTaskId':approval.pk,'approvalDecisionId':decision.pk,
        'decisionHash':decision.decision_hash,'reviewerId':decision.actor_id,'sharedHistory':shared,
        'decisionAuditReference':proof['decisionAuditReference'],'reviewProofHash':_hash(proof)}


def evidence_proof(row, ctx=None):
    history = verify_record(row)
    if ctx is None:
        ctx = task_context(row.task)
    if row.company_id != ctx['task'].company_id or row.task_id != ctx['task'].pk or row.account_key != ctx.get('accountKey'):
        fail('OUTPUT_OBJECT_MISMATCH', '产出证明与真实任务、公司或计划谱系不一致。')
    number(row.quantity,positive=True,precision=ctx['unit'].decimal_places)
    source = row.source_snapshot
    if row.kind=='EXCESS_REPORT' and row.data.get('inputAllocations',[])!=source.get('intentPayload',{}).get('inputAllocations',[]):
        fail('OUTPUT_FROZEN_INTENT_CHANGED','超产原始投入意图与正式声明快照不一致。')
    frozen = source.get('task',{})
    for key in ('taskId','sourceSnapshotHash','taskVersion','assignmentHash','startId','startSnapshotHash','P','unitSnapshot'):
        if frozen.get(key) != ctx['snapshot'].get(key):
            fail('OUTPUT_SOURCE_PROOF_CHANGED', '产出引用的任务、开工、人员或计划单位证明不一致。')
    allocations = list(row.allocations.order_by('pk'))
    descriptors = [{'reportId':r.report_id,'startAtom':r.start_atom,'endAtom':r.end_atom,
        'quantity':r.quantity,'sourceHash':r.source_hash,'coverageKind':r.coverage_kind} for r in allocations]
    if source.get('allocations') != descriptors:
        fail('OUTPUT_COVERAGE_PROOF_DAMAGED', '产出分量覆盖与冻结来源不一致。')
    report_map = {r['id']:r for r in ctx['records']}
    total = Decimal(0)
    for a in allocations:
        if a.report_id:
            record = report_map.get(a.report_id)
            if (not record or a.source_hash != _hash(record) or not 0 <= int(a.start_atom) < int(a.end_atom)
                or int(a.end_atom) > atoms(record['quantity'],ctx['unit'].decimal_places)
                or Decimal(a.quantity) != from_atoms(int(a.end_atom)-int(a.start_atom),ctx['unit'].decimal_places)):
                fail('OUTPUT_REPORT_COVERAGE_UNPROVEN', '分量未准确绑定正式报工及其有效范围。')
        total=add(total,a.quantity)
    if row.kind in ('NORMAL_CONFIRM','WHOLE_RELEASE') and total != Decimal(row.quantity):
        fail('OUTPUT_REPORT_COVERAGE_UNPROVEN', '产出数量与报工分量覆盖之和不一致。')
    proof = {'id':row.pk,'ref':f'OperationOutputEvidence:{row.pk}','kind':row.kind,'quantity':row.quantity,
        'taskId':row.task_id,'accountKey':row.account_key,'uomId':row.uom_id,'scopeHash':row.scope_hash,'effectSign':row.effect_sign,
        'sourceSnapshotHash':row.source_snapshot_hash,'statusCode':row.status,'version':row.version,
        'confirmedById':row.confirmed_by_id,'allocations':descriptors,**history}
    if row.kind=='EXCESS_REPORT' and row.status=='confirmed':
        proof['review']=verify_shared_review(row)
    elif row.kind=='OUTPUT_CORRECTION' and row.status=='confirmed':
        exception=OperationCustodyException.objects.filter(pk=row.data.get('exceptionId'),task_id=row.task_id,status='confirmed').first()
        if not exception or exception.data.get('outputCorrectionId')!=row.pk:
            fail('OUTPUT_CORRECTION_REVIEW_UNPROVEN','产出更正缺少准确的正式异常确认关联。')
        proof['review']=verify_shared_review(exception)
    proof['proofHash']=_hash(proof)
    return proof


def production_snapshot(task, actor=None, *, context=None):
    ctx=validated_task_context(task,actor,context)
    evidence=[];corrections=[];pending=[]
    if ctx['quantified']:
        for row in OperationOutputEvidence.objects.filter(task_id=task.pk,
            kind__in=('EXCESS_REPORT','OUTPUT_CORRECTION')).order_by('pk'):
            proof=evidence_proof(row,ctx)
            (corrections if row.kind=='OUTPUT_CORRECTION' else evidence).append(proof)
            if row.status=='declared':pending.append({'objectType':'OperationOutputEvidence','id':row.pk,
                'kind':row.kind,'sourceHash':row.source_snapshot_hash,'quantity':row.quantity,'version':row.version})
        for row in OperationCustodyException.objects.filter(task_id=task.pk,kind='OUTPUT_CORRECTION',status='pending').order_by('pk'):
            verify_record(row);pending.append({'objectType':'OperationCustodyException','id':row.pk,
                'kind':row.kind,'sourceHash':row.source_snapshot_hash,'quantity':row.quantity,'version':row.version})
    revision=len(ctx['records'])+(ctx.get('account').production_revision if ctx.get('account') else 0)
    payload={'companyId':task.company_id,'taskId':task.pk,'taskVersion':task.version,
        'sourceSnapshotHash':task.source_snapshot_hash,'reportSetHash':_hash(ctx['records']),
        'reportIds':[r['id'] for r in ctx['records']], 'supplementalEvidence':evidence,
        'productionCorrections':corrections,'unresolvedProductionExceptions':pending}
    whole_quantity=add(ctx['R'] or 0,
        *(p['quantity'] for p in evidence if p['statusCode']=='confirmed'),
        *(Decimal(p['quantity'])*p['effectSign'] for p in corrections if p['statusCode']=='confirmed'))
    return {'revision':revision,'hash':_hash(payload),'payload':payload,'blockingIssues':ctx['blockingIssues'][:],
        'wholeProductionQuantity':text(whole_quantity) if ctx['quantified'] else None,
        'planQuantity':text(ctx['P']) if ctx['quantified'] else None,
        'wholeProductionCoversPlan':bool(ctx['quantified'] and whole_quantity>=ctx['P'])}


def verify_production_snapshot(task, frozen_snapshot, *, context=None):
    """Validate referenced historical producers, never the later live account."""
    if (not isinstance(frozen_snapshot,dict) or not isinstance(frozen_snapshot.get('payload'),dict)
        or frozen_snapshot.get('hash') != _hash(frozen_snapshot['payload'])):
        fail('COMPLETION_PRODUCTION_SNAPSHOT_DAMAGED','整体完工冻结生产证据或Hash损坏。')
    frozen=frozen_snapshot['payload'];ctx=validated_task_context(task,context=context)
    if any(frozen.get(k)!=v for k,v in {'companyId':task.company_id,'taskId':task.pk,
        'taskVersion':task.version,'sourceSnapshotHash':task.source_snapshot_hash}.items()):
        fail('COMPLETION_PRODUCTION_OBJECT_MISMATCH','整体完工生产证据未绑定准确原任务。')
    ids=frozen.get('reportIds')
    if not isinstance(ids,list) or len(ids)!=len(set(ids)):
        fail('COMPLETION_PRODUCTION_REPORTS_DAMAGED','冻结报工集合身份损坏。')
    mapped={r['id']:r for r in ctx['records']}
    if any(i not in mapped for i in ids) or _hash([mapped[i] for i in ids])!=frozen.get('reportSetHash'):
        fail('COMPLETION_PRODUCTION_REPORTS_DAMAGED','冻结报工的正式原记录、数量或审计已不一致。')
    for key in ('supplementalEvidence','productionCorrections'):
        rows=frozen.get(key)
        if not isinstance(rows,list):fail('COMPLETION_PRODUCTION_PROOFS_DAMAGED','冻结生产证明集合结构损坏。')
        for proof in rows:
            row=OperationOutputEvidence.objects.filter(pk=proof.get('id'),task_id=task.pk,company_id=task.company_id).first()
            if not row or evidence_proof(row,ctx)!=proof:
                fail('COMPLETION_PRODUCTION_PROOFS_DAMAGED','冻结增补产出或更正的正式原证明不一致。')
    production_quantity=add(*(mapped[i]['quantity'] for i in ids),
        *(p['quantity'] for p in frozen['supplementalEvidence'] if p['statusCode']=='confirmed'),
        *(Decimal(p['quantity'])*p['effectSign'] for p in frozen['productionCorrections'] if p['statusCode']=='confirmed'))
    expected={'wholeProductionQuantity':text(production_quantity),'planQuantity':text(ctx['P']),
        'wholeProductionCoversPlan':production_quantity>=ctx['P']}
    if any(k in frozen_snapshot and frozen_snapshot[k]!=v for k,v in expected.items()):
        fail('COMPLETION_PRODUCTION_TOTAL_DAMAGED','冻结整体生产数量与其正式原证明之和不一致。')
    if frozen.get('unresolvedProductionExceptions'):
        fail('COMPLETION_PRODUCTION_UNRESOLVED','已生效整体完工不能含未解决的生产真实性异常。')
    return True


def read_task_quantity_account(task, actor=None, *, context=None, whole_proof=None):
    ctx=validated_task_context(task,actor,context)
    if ctx['task'].pk!=task.pk or ctx['task'].company_id!=task.company_id:
        fail('OUTPUT_VERIFIED_CONTEXT_MISMATCH','已验真来源上下文与当前对象不一致。')
    if not ctx['quantified']:
        return {'taskId':task.pk,'workOrderId':task.work_order_id,'quantityApplicable':False,
            'P':None,'R':None,'E':None,'statusLabel':'无投产统计量；沿原合法定量批次办理物流',
            'referenceWorkload':{'quantity':task.workload_quantity,'uomId':task.workload_uom_id},
            'blockingReasons':ctx['blockingIssues'],'ready':False,'basis':None,'uom':None}
    if whole_proof is not None:
        from .operation_completion_v3_authority import validate_whole_coverage
        whole=validate_whole_coverage(task,actor,whole_proof)
    else:whole=whole_coverage(task,context=ctx)
    normal=[];supplement=[];negative=Decimal(0)
    released=Decimal(0);intervals={}
    for row in OperationOutputEvidence.objects.filter(task_id=task.pk).order_by('pk'):
        proof=evidence_proof(row,ctx)
        if row.status!='confirmed':continue
        if row.kind in ('NORMAL_CONFIRM','WHOLE_RELEASE'):
            for item in proof['allocations']:
                key=item['reportId'];lo,hi=int(item['startAtom']),int(item['endAtom'])
                if any(max(lo,a)<min(hi,b) for a,b in intervals.get(key,[])):
                    fail('OUTPUT_REPORT_DOUBLE_RELEASE', '同一报工份额已被重复定位释放。')
                intervals.setdefault(key,[]).append((lo,hi))
            released=add(released,row.quantity)
            if row.kind=='NORMAL_CONFIRM':normal.append(Decimal(row.quantity))
        elif row.kind=='EXCESS_REPORT':supplement.append(Decimal(row.quantity))
        elif row.kind=='OUTPUT_CORRECTION':negative=add(negative,Decimal(row.quantity)*row.effect_sign)
    ordinary=ctx['R'] if whole.get('valid') else add(*normal)
    E=add(ordinary,*supplement,negative)
    buckets={k:Decimal(0) for k in ('U','S','V','I','Q','Z','C')}
    H=Decimal(0);F=Decimal(0);subH={k:Decimal(0) for k in ('U','S','V')};subF=dict(subH)
    from .operation_handover_authority import verify_task_custody
    verify_task_custody(task)
    for row in OperationCustodySlice.objects.filter(root__task_id=task.pk).exclude(status='closed').order_by('pk'):
        verify_record(row)
        amount=Decimal(row.quantity);buckets[row.status]=add(buckets[row.status],amount)
        if row.reserved_by_id:
            if row.status not in subH or row.frozen:fail('HANDOVER_RESERVATION_PROOF_DAMAGED','占用份额状态或冻结事实矛盾。')
            subH[row.status]=add(subH[row.status],amount);H=add(H,amount)
        if row.frozen:
            if row.status not in subF:fail('HANDOVER_FREEZE_PROOF_DAMAGED','冻结仅能属于真实在手份额。')
            subF[row.status]=add(subF[row.status],amount);F=add(F,amount)
    W=add(E,-add(*buckets.values()))
    if W<0 or W!=add(ordinary,-released):
        fail('OUTPUT_CUSTODY_CONSERVATION_FAILED','有效产出、未定位和实物份额不守恒，禁止准入。')
    from .operation_handover_models import OperationHandover
    from .operation_handover_authority import handover_totals
    gross_out=Decimal(0);gross_received=Decimal(0);unmatched=Decimal(0)
    for header in OperationHandover.objects.filter(company_id=task.company_id,data__taskId=task.pk).order_by('pk'):
        verify_record(header);leg=handover_totals(header)
        gross_out=add(gross_out,leg['sentQuantity']);gross_received=add(gross_received,leg['receivedQuantity'])
        unmatched=add(unmatched,leg['unmatchedQuantity'])
    source_dispatched=add(E,-W,-buckets['U'])
    account=ctx.get('account')
    unresolved=list(OperationOutputEvidence.objects.filter(task_id=task.pk,kind__in=('EXCESS_REPORT','OUTPUT_CORRECTION'),status='declared').values_list('pk',flat=True))
    pending_corrections=list(OperationCustodyException.objects.filter(task_id=task.pk,kind='OUTPUT_CORRECTION',status='pending').values_list('pk',flat=True))
    current_issues=ctx['blockingIssues'][:]
    production_issues=(['存在未确认补充报工或产出真实性更正，不能办理新的整体完工确认；原已验且未冻结份额可继续物流。'] if unresolved or pending_corrections else [])
    result={'taskId':task.pk,'workOrderId':task.work_order_id,'accountKey':ctx['accountKey'],
        'quantityApplicable':True,'P':text(ctx['P']),'R':text(ctx['R']),'E':text(E),'W':text(W),
        **{k:text(v) for k,v in buckets.items()},'H':text(H),'F':text(F),
        'O':text(gross_out),'A':text(gross_received),'X':text(unmatched),'D':text(source_dispatched),
        'cumulativeGrossSentQuantity':text(gross_out),'cumulativeGrossReceivedQuantity':text(gross_received),
        'cumulativeMatchedReceivedQuantity':text(gross_received),
        'sourceDispatchQuantity':text(source_dispatched),'plannedDispatchDeficit':text(max(add(ctx['P'],-source_dispatched),Decimal(0))),
        'logisticsMetricBasisLabel':'O为全路径实际交出累计；A为全路径来源匹配实收累计，各腿关联更正取净额，原申报与X另列；D=E-W-U为当前离源管理量，均不新增产量',
        'availableSource':text(add(buckets['U'],-subH['U'],-subF['U'])),
        'availableStorage':text(add(buckets['S'],-subH['S'],-subF['S'])),
        'availableDestination':text(add(buckets['V'],-subH['V'],-subF['V'])),
        'unconfirmedReportedQuantity':text(add(ctx['R'],-ordinary)),
        'planDeficit':text(max(add(ctx['P'],-E),Decimal(0))),'excessQuantity':text(max(add(E,-ctx['P']),Decimal(0))),
        'basis':{'type':'FROZEN_TASK_WORKLOAD','sourceSnapshotHash':task.source_snapshot_hash,'taskVersion':task.version},
        'uom':ctx['unitSnapshot'],'workOrderPlannedQuantity':str(task.work_order.quantity),
        'workOrderUomId':task.work_order.uom_id,'workOrderUomLabel':task.work_order.uom.name if task.work_order.uom_id else None,
        'productionRevision':len(ctx['records'])+(account.production_revision if account else 0),
        'releaseRevision':account.release_revision if account else 0,'custodyRevision':account.custody_revision if account else 0,
        'ready':not current_issues,'blockingReasons':current_issues,
        'productionAdmissionReady':not current_issues and not production_issues,
        'productionBlockingReasons':production_issues,'pendingSupplementalOutputIds':unresolved,
        'pendingProductionCorrectionIds':pending_corrections,
        'statusLabel':'产量待确认' if add(ctx['R'],-ordinary)>0 else '有效产出及保管份额已核实',
        'wholeCompletionCoverage':whole.get('proof') if whole.get('valid') else None}
    result['accountSnapshotHash']=_hash(result)
    return result
