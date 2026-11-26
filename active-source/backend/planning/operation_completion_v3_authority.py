"""Explicit completion-generation authority, preserving legacy Q/NonQ proofs.

Imports have no side effects. In particular, configuration and all writes are
explicit, and every writer acquires the shared stable Task account first.
"""
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
import re
from threading import RLock
from django.db import transaction, IntegrityError, connection
from django.db.models import Max
from django.utils import timezone
from workflow_runtime.models import (WorkflowInstance, ApprovalTask, ApprovalDecision,
    BusinessStateTransition, ProcessDefinition, WorkflowNodeDefinition)
from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES, ActionPermissionValidator
from workflow_runtime.state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition, transition_business_object)
from workflow_runtime.closure_service import close_pending_workflow, closure_facts as _native_closure_facts, WorkflowClosureError
from masterdata.models import MasterDataWriteRequest, ExternalIdentity
from system.models import PositionResponsibility, PositionWorkflowResponsibility, User, OrganizationOperatingAuditRecord
from .operation_completion_generation_models import OperationCompletionGeneration as Generation
from .operation_completion_contract import (REQUEST_ACTION as LEGACY_REQUEST, APPROVE_ACTION as LEGACY_APPROVE,
    REQUEST_RESPONSIBILITY, REVIEW_RESPONSIBILITY, MODULE, BUSINESS_PROCESS)
from .operation_completion_quantity_account import (production_snapshot, production_issues,
    verify_frozen_production, quantity_account, has_new_production, combined_source,native_context)
from .mes_test_source_bridge import _fail, _hash
from .mes_test_source_bridge import _effective
from .mes_test_source_bridge import _assert_hash
from .workshop_task_time import task_datetime_label

CONTRACT='PCE-PRODUCTION-OPERATION-COMPLETION-V3'
OBJECT='OperationCompletionGeneration'
PROCESS='MES_OPERATION_COMPLETION_REVIEW_V3'
REQUEST_ACTION='production.operation.complete.v3.request'
APPROVE_ACTION='production.operation.complete.v3.approve'
WITHDRAW_ACTION='production.operation.complete.withdraw_replace'
REQUEST_NODE='PRODUCTION_OPERATION_COMPLETE_V3_REQUEST'
REVIEW_NODE='PRODUCTION_OPERATION_COMPLETE_V3_REVIEW'
WITHDRAW_NODE='PRODUCTION_OPERATION_COMPLETE_V3_WITHDRAW_REPLACE'
LABELS={'pending':'待生产跟单员审核','approved':'工序完工已生效',
    'superseded':'因生产事实变化撤回待审','rejected':'申请未通过'}
DEFINITION={'definitionCode':PROCESS,'definitionName':'工序完工生产事实版本审核模板',
    'businessDomain':'MES','documentType':OBJECT,'version':1,'active':True,
    'description':'独立代次承接生产事实；申请人可明确撤回待审并替代，不构成拒绝或审核，不放行物流库存或后序。'}
NODES=(
    {'nodeCode':REQUEST_NODE,'nodeName':'新版本人整体完工申请','sequence':1,'businessActionCode':REQUEST_ACTION,
        'active':True,'description':'原本人申请职责核对当前生产事实后提出独立代次申请。'},
    {'nodeCode':REVIEW_NODE,'nodeName':'新版生产跟单整体完工独审','sequence':2,'businessActionCode':APPROVE_ACTION,
        'active':True,'description':'独立生产跟单角色审核准确代次及冻结生产证据。'},
    {'nodeCode':WITHDRAW_NODE,'nodeName':'本人撤回待审并关联替代','sequence':3,'businessActionCode':WITHDRAW_ACTION,
        'active':True,'description':'仅原申请人关闭未决申请并关联新代次；没有审核决策，不认定产出不合格。'},
)
ACTION_SPECS={
    'request':(REQUEST_ACTION,LEGACY_REQUEST,REQUEST_NODE,REQUEST_RESPONSIBILITY,'EXECUTOR','提交完工申请'),
    'approve':(APPROVE_ACTION,LEGACY_APPROVE,REVIEW_NODE,REVIEW_RESPONSIBILITY,'REVIEWER','审核完工数据'),
    'withdrawReplace':(WITHDRAW_ACTION,WITHDRAW_ACTION,WITHDRAW_NODE,REQUEST_RESPONSIBILITY,'EXECUTOR','撤回待审并关联替代'),
}
_policy_lock,_owned_policies=RLock(),{}
_STAGE_TOKEN=object()


@contextmanager
def completion_writer_context(actor,task_id):
    """Stable writer anchor precedes every production/source read scope."""
    from .operation_predecessor_authority import verification_context
    from .operation_handover_core import lock_accounts
    from .mes_test_source_bridge import allocation_admission_context
    with verification_context():
        with transaction.atomic():
            lock_accounts(actor,[task_id])
            with allocation_admission_context(user=actor):
                yield


def _stage_binding(task,actor):
    from .operation_predecessor_authority import _context,_historical_proof_only
    if (not actor or not getattr(actor,'pk',None) or not getattr(actor,'company_id',None)
            or actor.company_id!=task.company_id):
        _fail('COMPLETION_READ_CONTEXT_ACTOR_INVALID','正式核验阶段须绑定当前真实同公司账号，不能借用其他人员或公司。')
    current=_context.get()
    if current is None:_fail('COMPLETION_READ_CONTEXT_REQUIRED','当前正式读取上下文缺失，不能复用核验结果。')
    owner=current.setdefault('completionStageOwner',object())
    connection.ensure_connection()
    if connection.vendor=='sqlite':
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA data_version');external=cursor.fetchone()[0]
        epoch=(id(connection.connection),connection.connection.total_changes,external,
            id(connection.atomic_blocks[0]) if connection.in_atomic_block and connection.atomic_blocks else None)
    else:
        # No proof reuse on a vendor without the supported write epoch.
        return owner,None
    return owner,(actor.pk,actor.company_id,task.company_id,task.pk,task.version,
        task.source_snapshot_hash,task.assignment_hash,task.execution_mode,_historical_proof_only.get(),epoch)


class _VerifiedWholeCoverage(dict):
    def __init__(self,payload,task,actor):
        super().__init__(deepcopy(payload));self.token=_STAGE_TOKEN
        self.owner,self.binding=_stage_binding(task,actor);self.digest=_hash(dict(self))


def validate_whole_coverage(task,actor,proof):
    owner,binding=_stage_binding(task,actor)
    if (not isinstance(proof,_VerifiedWholeCoverage) or proof.token is not _STAGE_TOKEN
            or proof.owner is not owner or not binding or proof.binding!=binding
            or proof.digest!=_hash(dict(proof))):
        _fail('COMPLETION_WHOLE_CONTEXT_INVALID','整体覆盖只接受当前同账号、同对象及同写入序号的正式核验结果。')
    return deepcopy(dict(proof))


class _CompletionReadStage:
    def __init__(self,task,actor,bundle,current,histories,generations,context,production):
        self.token=_STAGE_TOKEN;self.owner,self.binding=_stage_binding(task,actor)
        self.bundle_hash=bundle['snapshotHash'];self.current=current;self.histories=histories
        self.generations=generations;self.context=context;self.production=production
        valid=bool(current and current['statusCode']=='completed' and current['stateMachineConsistent'] is True)
        self.whole=_VerifiedWholeCoverage({'valid':valid,'quantity':str(task.workload_quantity) if valid else None,
            'reportIds':[r['id'] for r in bundle['reports']] if valid else [],
            'reportSetHash':bundle['reportSetHash'] if valid else None,'proof':current if valid else None},task,actor)
        self.digest=_hash({'current':current,'histories':histories,'production':production})

    def validate(self,task,actor,bundle):
        owner,binding=_stage_binding(task,actor)
        if (self.token is not _STAGE_TOKEN or self.owner is not owner or not binding or self.binding!=binding
                or self.bundle_hash!=bundle['snapshotHash']
                or self.digest!=_hash({'current':self.current,'histories':self.histories,'production':self.production})):
            _fail('COMPLETION_READ_STAGE_CHANGED','读取或写入序号已变化，不能复用先前整体完工核验结果。')


def completion_read_stage(task,actor,bundle):
    if task.execution_mode!='QUANTIFIED':
        _fail('COMPLETION_STAGE_NONQUANTITATIVE','不可统计任务沿原实际经过协议核验，不构造定量代次。')
    owner,binding=_stage_binding(task,actor)
    context=native_context(task,actor)
    current,histories,generations=_completion_chain(task,bundle,native_production_context=context)
    production=production_snapshot(task,actor,context=context)
    end_owner,end_binding=_stage_binding(task,actor)
    if owner is not end_owner or not binding or binding!=end_binding:
        _fail('COMPLETION_READ_STAGE_CHANGED','正式核验期间生产事实发生变化，请只读重新读取。')
    return _CompletionReadStage(task,actor,bundle,current,histories,generations,context,production)


def closure_facts(closure):
    try:return _native_closure_facts(closure)
    except WorkflowClosureError as error:_fail('COMPLETION_SHARED_CLOSURE_UNPROVEN',str(error))


def expected_definition_hash():
    from workflow_runtime.definition_service import _canonical_hash
    return _canonical_hash({**DEFINITION,'nodes':[dict(row) for row in NODES]})


def read_quantitative_whole_coverage(task,*,native_production_context=None):
    """Reuse a whole proof only inside the exact current database read epoch."""
    from .operation_resource_read_scope import scoped_execution_read
    from .operation_predecessor_authority import verification_context, _proof_cache_epoch, _historical_proof_only
    @scoped_execution_read
    def read():
        with verification_context() as context:
            producer=native_production_context
            if producer is not None:
                from .operation_output_authority import validated_task_context
                producer=validated_task_context(task,context=producer)
            epoch=_proof_cache_epoch(context)
            if epoch is None:return _read_quantitative_whole_coverage(task,native_production_context=producer)
            if context.get('wholeCoverageEpoch')!=epoch:
                context['wholeCoverageEpoch']=epoch;context['wholeCoverageProofs']={}
            key=(task.company_id,task.pk,task.version,task.source_snapshot_hash,task.assignment_hash,
                task.work_order_id,task.source_operation_id,task.work_center_id,task.workshop_id,
                task.execution_mode,task.workload_quantity,task.workload_uom_id,_historical_proof_only.get())
            cache=context['wholeCoverageProofs'];path=context.setdefault('wholeCoveragePath',set())
            if key in cache:return deepcopy(cache[key])
            if key in path:_fail('COMPLETION_WHOLE_PROOF_CYCLE','整体完工证明出现循环，不能跳过核验。')
            path.add(key)
            try:
                # The canonical proof re-reads its original starter/producer.
                # A consumer's sealed context is validated above, but does not
                # become another completion authority or change the cache key.
                result=_read_quantitative_whole_coverage(task)
                if _proof_cache_epoch(context)!=epoch:
                    _fail('COMPLETION_WHOLE_READ_CHANGED','整体完工证明读取期间发生变化，请重新核查。')
                cache[key]=deepcopy(result);return result
            finally:path.remove(key)
    return read()


def _read_quantitative_whole_coverage(task,*,native_production_context=None):
    """Native original producer validation; never calls the quantity account."""
    from . import operation_completion_service as legacy
    from .operation_start_models import ProductionOperationStart
    if getattr(task,'execution_mode','QUANTIFIED')!='QUANTIFIED':
        return {'valid':False,'quantity':None,'reportIds':[],'reportSetHash':None,'proof':None}
    # Absence of an application is not an approved whole proof. It needs no
    # second full producer traversal after the account caller verified source.
    # Orphaned workflow/ledger/audit evidence must still take the full failing
    # history path, rather than being silently treated as ordinary absence.
    old_object=legacy.OBJECT
    recorded=(Generation.objects.filter(task_id=task.pk).exists()
        or BusinessStateTransition.objects.filter(object_type=old_object,object_id=task.pk).exists()
        or WorkflowInstance.objects.filter(document_type=old_object,document_id=task.pk).exists()
        or MasterDataWriteRequest.objects.filter(organization_id=task.company_id,
            entity_type=old_object,target_entity_id=str(task.pk)).exists()
        or _orphan_v3_evidence_exists(task))
    if not recorded:
        return {'valid':False,'quantity':None,'reportIds':[],'reportSetHash':None,'proof':None}
    start=ProductionOperationStart.objects.filter(task_id=task.pk).first()
    actor=User.objects.defer('password').filter(pk=start.started_by_id,company_id=task.company_id).first() if start else None
    if not actor:
        return {'valid':False,'quantity':None,'reportIds':[],'reportSetHash':None,'proof':None}
    bundle=validated_bundle(task,actor)
    fact=read_effective_completion(task,bundle,native_production_context=native_production_context)
    valid=bool(fact and fact['statusCode']=='completed' and fact['stateMachineConsistent'] is True)
    return {'valid':valid,'quantity':str(task.workload_quantity) if valid else None,
        'reportIds':[row['id'] for row in bundle['reports']] if valid else [],
        'reportSetHash':bundle['reportSetHash'] if valid else None,'proof':fact if valid else None}


def _legacy():
    from . import operation_completion_service
    return operation_completion_service


def _orphan_v3_evidence_exists(task):
    return (MasterDataWriteRequest.objects.filter(organization_id=task.company_id,entity_type=OBJECT,
            result__taskId=task.pk).exists()
        or OrganizationOperatingAuditRecord.objects.filter(organization_id=task.company_id,
            target_type=OBJECT,after_snapshot__state__taskId=task.pk).exists())


def validated_bundle(task,actor):
    """Reuse only a native verified producer within the current read context.

    Original producer code and proof algorithms remain unchanged. Any local
    SQL write or other SQLite connection commit invalidates this read's cache.
    Other database vendors simply perform the original full verification.
    """
    from .operation_predecessor_authority import verification_context, _historical_proof_only, current_rollback_generation
    if connection.vendor!='sqlite':return _legacy()._bundle(task,actor)
    connection.ensure_connection()
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA data_version');data_version=cursor.fetchone()[0]
    epoch=(id(connection.connection),connection.connection.total_changes,data_version,current_rollback_generation())
    with verification_context() as context:
        if context.get('completionBundleEpoch')!=epoch:
            context['completionBundleEpoch']=epoch;context['completionBundles']={}
        cache=context['completionBundles']
        key=(actor.pk,actor.company_id,task.company_id,task.pk,task.version,
            task.source_snapshot_hash,task.assignment_hash,task.execution_mode,
            _historical_proof_only.get(),connection.in_atomic_block)
        if key not in cache:
            value=_legacy()._bundle(task,actor)
            # A producer cannot have written SQL or raced a different commit
            # while being treated as one stable, reusable native read.
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA data_version');after=cursor.fetchone()[0]
            if epoch!=(id(connection.connection),connection.connection.total_changes,after,current_rollback_generation()):
                context['completionBundles']={}
                _fail('COMPLETION_READ_SNAPSHOT_CHANGED','正式生产证明读取期间发生变化，请重新只读核查；未复用过期事实。')
            cache[key]=deepcopy(value)
        return deepcopy(cache[key])


def _setup():
    from pde.routing_read_context import _current
    from .mes_evidence_graph import _raw,definition_rows
    company=(_current.get() or {}).get('__reader_company_id__')
    raw=definition_rows(company,PROCESS) if company and _raw(company) is not None else None
    definition=next((r for r in raw if r.document_type==OBJECT and r.business_domain=='MES' and r.active),None) if raw is not None else ProcessDefinition.objects.filter(
        definition_code=PROCESS,document_type=OBJECT,business_domain='MES',active=True).first()
    if not definition:
        return None,{}
    _assert_hash(definition)
    if definition.definition_hash!=expected_definition_hash():
        _fail('COMPLETION_V3_TEMPLATE_CHANGED','新版整体完工模板与正式目录不一致。')
    nodes={row['nodeCode']:(next((n for n in definition._mes_raw_nodes if n.node_code==row['nodeCode']
        and n.business_action_code==row['businessActionCode'] and n.active),None) if raw is not None else
        definition.nodes.filter(node_code=row['nodeCode'],business_action_code=row['businessActionCode'],active=True).first()) for row in NODES}
    return definition,nodes


def _role(actor,task,key):
    legacy=_legacy(); code,permission,node_code,duty_code,ownership,_=ACTION_SPECS[key]
    employee,position,evidence,valid=legacy._person(actor)
    definition,nodes=_setup();node=nodes.get(node_code)
    duties=list(PositionResponsibility.objects.filter(position=position,active=True,
        responsibility__code=duty_code,responsibility__status='ACTIVE',responsibility__is_active=True)
        .select_related('responsibility')) if valid else []
    duty=duties[0] if len(duties)==1 and _effective(duties[0].responsibility,legacy.starts._today()) else None
    matches=list(PositionWorkflowResponsibility.objects.filter(position=position,responsibility=duty.responsibility,
        workflow_node=node,workflow_code=PROCESS,node_code=node_code,ownership_type=ownership,active=True)) if duty and node else []
    mapping=matches[0] if len(matches)==1 and _effective(matches[0],legacy.starts._today()) else None
    allowed,matched,authorization=legacy.receipt._authority(actor,permission,task.workshop.department_id,actor.pk)
    issues=[]
    if not valid:issues.append('当前账号缺少唯一有效的同公司本人任职、岗位和部门关系。')
    if not definition or not node:issues.append('新版整体完工正式模板及本动作节点尚未核实。')
    if not duty or not mapping:issues.append('当前岗位缺少新版本动作的正式职责及精确节点责任关系。')
    if not allowed:issues.append('当前账号缺少本动作同一角色的明确权限及公司范围。')
    evidence.update(positionResponsibilityId=duty.pk if duty else None,workflowResponsibilityId=mapping.pk if mapping else None,
        responsibilityId=duty.responsibility_id if duty else None,workflowNodeId=node.pk if node else None,
        workflowProcessCode=PROCESS,workflowNodeCode=node_code,responsibilityCode=duty_code,ownershipType=ownership,
        matchedRoleCodes=sorted({row['roleCode'] for row in matched}),matchedAuthorityEvidence=matched)
    return {'ready':not issues,'missingItems':issues,'currentActorEvidence':evidence,'authorization':authorization,
        'definitionId':definition.pk if definition else None,'definitionHash':definition.definition_hash if definition else None,
        'nodeId':node.pk if node else None,'roleCodes':evidence['matchedRoleCodes']}


def register_actions():
    from system.models import RolePermission
    with _policy_lock:
        for key,(code,permission,*_) in ACTION_SPECS.items():
            roles=tuple(RolePermission.objects.filter(permission__code=permission).order_by('role__code').values_list('role__code',flat=True).distinct())
            policy=ActionPermissionPolicy(actionCode=code,moduleCode=MODULE,requiredPermission=permission,role=roles,
                organizationScope='legal_entity',serverValidator='planning.operation_completion_v3_authority.execute',
                allowedStatuses=('unrequested',) if key=='request' else ('pending_review',),scope='single')
            previous=POLICIES.get((MODULE,code))
            if previous is not None and previous!=policy and (previous is not _owned_policies.get(code) or replace(previous,role=roles)!=policy):
                _fail('COMPLETION_V3_ACTION_CONFLICT','新版完工动作已被另一权威绑定，禁止覆盖。')
            POLICIES[(MODULE,code)]=policy;_owned_policies[code]=policy


def action_contract(key,task_id=None):
    register_actions();code,permission,node,duty,_,label=ACTION_SPECS[key]
    suffix='withdraw-and-replace' if key=='withdrawReplace' else key
    return {**POLICIES[(MODULE,code)].serialize(),'key':key,'displayName':label,
        'apiPath':f'/api/planning/operation-completions/{task_id}/{suffix}/' if task_id else None,
        'httpMethod':'POST','processCode':PROCESS,'businessProcessCode':BUSINESS_PROCESS,
        'workflowNodeCode':node,'requiredResponsibility':duty,'objectType':OBJECT,
        'assessmentSourceObjectType':'ProductionWorkshopTask','sameRolePermissionAndScopeRequired':True,
        'differentApplicantReviewerAndRoleRequired':True,'downstreamReleaseSupported':False,'completionProtocolVersion':3}


def intent_hash(actor_id,company_id,code,task_id,payload):
    # New-protocol canonical intent matches the shared handover core. The
    # caller sends its exact normalized payload; hashing never rewrites text.
    # Company is independently bound by the ledger, Task and generation.
    body={k:deepcopy(v) for k,v in payload.items() if k!='idempotencyKey'}
    return _hash({'actorId':actor_id,'actionCode':code,'objectId':task_id,'payload':body})


def _audit_event(actor,task,obj,name,action,q,reason,before,after):
    from .mes_test_source_bridge import record_audit
    state={**deepcopy(after),'contractVersion':CONTRACT}
    row=record_audit(user=actor,action_code=action,target=obj,target_type=name,target_no=task.no,
        before=deepcopy(before),after=state,authorization=q['authorization'],reason=reason)
    node={'processCode':PROCESS,'businessProcessCode':BUSINESS_PROCESS,'nodeCode':q['currentActorEvidence']['workflowNodeCode'],
        'processId':q['definitionId'],'nodeId':q['nodeId']}
    row.before_snapshot['workflowNode']=node;row.after_snapshot['workflowNode']=node
    row.save(update_fields=['before_snapshot','after_snapshot'])
    return f'OrganizationOperatingAuditRecord:{row.pk}'


def _state(gen):
    return {'generationId':gen.pk,'taskId':gen.task_id,'companyId':gen.company_id,'sequence':gen.sequence,
        'protocol':gen.protocol,'status':gen.status,'version':gen.version,'applicantId':gen.applicant_id,
        'precedingGenerationId':gen.preceding_generation_id,'legacyRequestId':gen.legacy_request_id,
        'sourceSnapshotHash':gen.source_snapshot_hash,'productionRevision':gen.production_revision,
        'productionHash':gen.production_hash,'requestHash':gen.request_hash,'requestKeyHash':gen.request_key_hash,
        'workflowInstanceId':gen.workflow_instance_id,'approvalTaskId':gen.approval_task_id}


def _audit_state(event,name,obj_id,company_id):
    match=re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)',event.audit_reference or '')
    from .mes_evidence_graph import audit as raw_audit,audit_node_matches
    audit=raw_audit(int(match[1]),company_id) if match else None
    if audit is NotImplemented:
        audit=OrganizationOperatingAuditRecord.objects.select_related('actor').defer('actor__password').filter(pk=int(match[1])).first()
    if (not audit or audit.target_type!=name or audit.target_id!=obj_id or audit.organization_id!=company_id
            or audit.actor.company_id!=company_id
            or audit.actor_id!=event.operator_id or audit.action_code!=event.action_code or audit.reason!=event.reason
            or not isinstance(audit.after_snapshot,dict) or not isinstance(audit.after_snapshot.get('state'),dict)
            or not isinstance(audit.before_snapshot,dict) or not isinstance(audit.before_snapshot.get('state'),dict)):
        _fail('COMPLETION_V3_AUDIT_UNPROVEN','新版完工缺少真实同对象、同动作和同操作人的审计。')
    state=audit.after_snapshot['state'];auth=audit.after_snapshot.get('authorization',{})
    if (not isinstance(auth,dict) or not isinstance(auth.get('permissionCodes'),list)
            or not isinstance(auth.get('roleCodes'),list)
            or any(not isinstance(x,str) or not x for x in auth.get('permissionCodes',[])+auth.get('roleCodes',[]))):
        _fail('COMPLETION_V3_AUDIT_UNPROVEN','新版审计授权结构不完整。')
    permission=next((spec[1] for spec in ACTION_SPECS.values() if spec[0]==event.action_code),None)
    spec=next((spec for spec in ACTION_SPECS.values() if spec[0]==event.action_code),None)
    node=audit.after_snapshot.get('workflowNode')
    if (state.get('contractVersion')!=CONTRACT or state.get('status')!=event.target_state
            or audit.before_snapshot['state'].get('status')!=event.source_state
            or auth.get('allowed') is not True or not permission or permission not in auth.get('permissionCodes',[])
            or not auth.get('roleCodes') or not isinstance(node,dict) or not spec
            or node.get('processCode')!=PROCESS or node.get('businessProcessCode')!=BUSINESS_PROCESS
            or node.get('nodeCode')!=spec[2] or audit.before_snapshot.get('workflowNode')!=node
            or not audit_node_matches(company_id,node.get('nodeId'),node.get('processId'),PROCESS,spec[2],event.action_code)):
        _fail('COMPLETION_V3_AUDIT_UNPROVEN','新版完工审计状态、授权及动作不一致。')
    return audit,state


def _ledger(gen,code,request_hash,key_hash):
    from .mes_evidence_graph import ledgers
    rows=ledgers(gen,code,request_hash)
    if rows is NotImplemented:
        rows=list(MasterDataWriteRequest.objects.filter(organization_id=gen.company_id,action_code=code,
            entity_type=OBJECT,target_entity_id=str(gen.pk),request_hash=request_hash).select_related('source_identity'))
    ledger=rows[0] if len(rows)==1 else None
    if (not ledger or not isinstance(ledger.audit_metadata,dict) or ledger.status!='COMMITTED' or sha256(ledger.idempotency_key.encode()).hexdigest()!=key_hash
            or ledger.source_identity.organization_id!=gen.company_id or ledger.source_identity.target_entity_type!=OBJECT
            or ledger.source_identity.target_entity_id!=str(gen.pk) or ledger.source_identity.source_fingerprint!=request_hash
            or ledger.source_identity.external_id!=key_hash or ledger.source_identity.mapping_status!='MATCH'
            or ledger.source_identity.source_system!='MES_OPERATION_COMPLETION_V3'
            or ledger.source_identity.source_type!='INTERNAL' or ledger.source_identity.source_object_type!=code
            or ledger.audit_metadata.get('contractVersion')!=CONTRACT or not isinstance(ledger.audit_metadata.get('intentPayload'),dict)):
        _fail('COMPLETION_V3_LEDGER_UNPROVEN','新版完工原请求账本、来源身份或Hash无法核实。')
    payload={**ledger.audit_metadata['intentPayload'],'idempotencyKey':ledger.idempotency_key}
    _payload(payload,next(key for key,spec in ACTION_SPECS.items() if spec[0]==code))
    if intent_hash(ledger.audit_metadata.get('actorId'),gen.company_id,code,gen.task_id,payload)!=request_hash:
        _fail('COMPLETION_V3_LEDGER_UNPROVEN','新版完工原请求与操作者/对象/内容不一致。')
    expected={'taskId':gen.task_id,'generationId':gen.pk,'workflowInstanceId':gen.workflow_instance_id,
        'approvalTaskId':gen.approval_task_id,'completed':code==APPROVE_ACTION}
    if code==WITHDRAW_ACTION:
        previous=gen.preceding_generation
        expected={'taskId':gen.task_id,'generationId':gen.pk,'precedingGenerationId':previous.pk if previous else None,
            'closureId':previous.closure_id if previous else None,'completed':False}
    if ledger.result!=expected:
        _fail('COMPLETION_V3_LEDGER_UNPROVEN','原请求正式结果不属于准确代次或共享审批。')
    return ledger


def _write_ledger(gen,actor,code,payload,result):
    h=intent_hash(actor.pk,gen.company_id,code,gen.task_id,payload);key=sha256(payload['idempotencyKey'].encode()).hexdigest()
    identity=ExternalIdentity.objects.create(organization_id=gen.company_id,source_system='MES_OPERATION_COMPLETION_V3',
        source_type='INTERNAL',source_object_type=code,external_id=key,target_entity_type=OBJECT,
        target_entity_id=str(gen.pk),mapping_status='MATCH',source_fingerprint=h,
        audit_metadata={'contractVersion':CONTRACT,'downstreamReleased':False})
    return MasterDataWriteRequest.objects.create(organization_id=gen.company_id,action_code=code,entity_type=OBJECT,
        idempotency_key=payload['idempotencyKey'],request_hash=h,source_identity=identity,status='COMMITTED',
        target_entity_id=str(gen.pk),result=result,audit_metadata={'actorId':actor.pk,'contractVersion':CONTRACT,
            'intentPayload':{k:v for k,v in payload.items() if k!='idempotencyKey'}})


def _proof(gen,task,bundle,*,native_production_context=None):
    if gen.company_id!=task.company_id or gen.task_id!=task.pk:
        _fail('COMPLETION_GENERATION_OBJECT_MISMATCH','整体完工代次不属于准确公司和任务。')
    if gen.protocol=='V2_BRIDGE':
        archived=_legacy()._legacy_history(task,bundle,gen.closure if gen.closure_id else None)
        if (gen.status!='superseded' or gen.sequence!=1 or gen.preceding_generation_id is not None
                or not archived or gen.legacy_request_id!=archived['statusTransitionHistory'][0]['id']
                or gen.applicant_id!=archived['applicantId'] or gen.request_audit_reference!=archived['requestAuditReference']
                or gen.source_snapshot_hash!=archived['sourceSnapshotHash'] or gen.source_snapshot!=bundle['snapshot']
                or _hash(gen.source_snapshot)!=gen.source_snapshot_hash
                or gen.request_hash!=archived['requestHash'] or gen.request_key_hash!=archived['requestKeyHash']
                or gen.request_reason!=archived['requestReason']
                or gen.workflow_instance_id!=archived['workflowInstanceId'] or gen.approval_task_id!=archived['approvalTaskId']
                or gen.request_snapshot!={'originalRequestReference':archived['requestAuditReference'],'bridgeOnly':True}
                or gen.production_snapshot!={'legacyProtocol':2,'captureStatus':'NOT_CAPTURED_BY_LEGACY_REQUEST',
                    'originalRequestReference':archived['requestAuditReference'],'reportSetHash':bundle['reportSetHash']}
                or gen.production_revision!=0 or gen.production_hash!=_hash(gen.production_snapshot)
                or gen.requested_at!=BusinessStateTransition.objects.get(pk=gen.legacy_request_id).timestamp):
            _fail('COMPLETION_BRIDGE_UNPROVEN','原待审桥接未准确引用原申请及原Hash。')
        from .mes_evidence_graph import history as raw_history
        bridge_events=raw_history(OBJECT,gen.pk,gen.company_id)
        if bridge_events is NotImplemented:bridge_events=list(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=gen.pk).order_by('version','pk'))
        if len(bridge_events)!=2 or gen.version!=2:
            _fail('COMPLETION_BRIDGE_HISTORY_UNPROVEN','桥接及本人撤回缺少完整独立历史。')
        for n,(event,states) in enumerate(zip(bridge_events,[('','pending'),('pending','superseded')]),1):
            _,saved=_audit_state(event,OBJECT,gen.pk,gen.company_id)
            if (event.version!=n or (event.source_state,event.target_state)!=states or event.action_code!=WITHDRAW_ACTION
                    or event.operator_id!=gen.applicant_id or saved.get('generationId')!=gen.pk
                    or saved.get('requestHash')!=gen.request_hash or saved.get('sourceSnapshotHash')!=gen.source_snapshot_hash):
                _fail('COMPLETION_BRIDGE_HISTORY_UNPROVEN','桥接事实被修改或被误作重新申请/审核。')
        result={**archived,'completionProtocolVersion':2,'generationId':gen.pk,'generationSequence':gen.sequence,
            'generationVersion':gen.version,'generationStatusCode':gen.status,
            'legacyRequestPreserved':True,'legacyHistoryUnchanged':True,
            'bridgeHistory':{'statusTransitionCount':len(bridge_events),
                'statusTransitionHistory':[{'id':event.pk,'version':event.version,'actionCode':event.action_code,
                    'sourceStateLabel':'尚未建立代次桥接' if event.version==1 else '原待审申请桥接已登记',
                    'targetStateLabel':'原待审申请桥接已登记' if event.version==1 else LABELS['superseded'],
                    'operatorId':event.operator_id,'reason':event.reason,'auditReference':event.audit_reference}
                    for event in bridge_events]}}
    else:
        if (gen.protocol!='V3' or not gen.workflow_instance_id or not gen.approval_task_id
                or not isinstance(gen.source_snapshot,dict) or not isinstance(gen.production_snapshot,dict)
                or _hash(gen.source_snapshot)!=gen.source_snapshot_hash
                or gen.source_snapshot.get('baseSourceSnapshotHash')!=bundle['snapshotHash']
                or gen.source_snapshot.get('baseSourceSnapshot')!=bundle['snapshot']
                or gen.source_snapshot.get('productionSnapshot')!=gen.production_snapshot
                or gen.production_snapshot.get('hash')!=gen.production_hash
                or gen.production_snapshot.get('revision')!=gen.production_revision):
            _fail('COMPLETION_GENERATION_SOURCE_UNPROVEN','新版代次来源、生产快照或Hash不一致。')
        verify_frozen_production(task,gen.production_snapshot,context=native_production_context)
        from .mes_evidence_graph import history as raw_history
        events=raw_history(OBJECT,gen.pk,gen.company_id)
        if events is NotImplemented:events=list(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=gen.pk).order_by('version','pk'))
        statuses=[('', 'pending',REQUEST_ACTION)]
        if gen.status=='approved':statuses.append(('pending','approved',APPROVE_ACTION))
        elif gen.status=='superseded':statuses.append(('pending','superseded',WITHDRAW_ACTION))
        elif gen.status!='pending':_fail('COMPLETION_GENERATION_STATE_UNPROVEN','新版整体完工代次状态不在正式合同。')
        if len(events)!=len(statuses) or gen.version!=len(events):
            _fail('COMPLETION_GENERATION_HISTORY_UNPROVEN','整体完工代次缺少完整真实状态历史。')
        states=[];audits=[]
        for n,(event,triple) in enumerate(zip(events,statuses),1):
            audit,state=_audit_state(event,OBJECT,gen.pk,gen.company_id)
            immutable={k:v for k,v in _state(gen).items() if k not in ('status','version')}
            if (event.version!=n or (event.source_state,event.target_state,event.action_code)!=triple
                    or state.get('version')!=n or any(state.get(k)!=v for k,v in immutable.items())):
                _fail('COMPLETION_GENERATION_HISTORY_UNPROVEN','整体完工代次转换、版本或对象不一致。')
            states.append(state);audits.append(audit)
        first=states[0];last=states[-1]
        captured=gen.request_snapshot
        person=first.get('actorEvidence')
        if (not isinstance(captured,dict) or not isinstance(person,dict)
                or person!=captured.get('actorEvidence') or person.get('userId')!=gen.applicant_id
                or person.get('companyId')!=gen.company_id or person.get('employeeId')!=task.execution_employee_id
                or person.get('positionId')!=task.execution_position_id
                or person.get('uniqueEmployeeAccountLink') is not True or person.get('currentEmploymentValid') is not True
                or not isinstance(person.get('matchedRoleCodes'),list) or not person['matchedRoleCodes']
                or any(not isinstance(x,str) or not x for x in person['matchedRoleCodes'])
                or any(type(person.get(k)) is not int or person[k]<=0 for k in ('userId','companyId','employeeId','positionId',
                    'responsibilityId','positionResponsibilityId','workflowResponsibilityId','workflowNodeId'))):
            _fail('COMPLETION_GENERATION_ACTOR_UNPROVEN','新版申请缺少原本人、正式任职及精确责任证据。')
        if (first.get('requestHash')!=gen.request_hash or first.get('requestKeyHash')!=gen.request_key_hash
                or first.get('sourceSnapshotHash')!=gen.source_snapshot_hash or events[0].operator_id!=gen.applicant_id
                or gen.request_audit_reference!=events[0].audit_reference
                or gen.workflow_instance.document_type!=OBJECT or gen.workflow_instance.document_id!=gen.pk
                or gen.approval_task.workflow_instance_id!=gen.workflow_instance_id):
            _fail('COMPLETION_GENERATION_BINDING_UNPROVEN','代次没有绑定准确原申请及真实共享审批身份。')
        original_ledger=_ledger(gen,REQUEST_ACTION,gen.request_hash,gen.request_key_hash)
        expected_intent={'expectedVersion':task.version,'expectedSourceSnapshotHash':task.source_snapshot_hash,
            'expectedAssignmentHash':task.assignment_hash,'expectedStartId':bundle['start'].pk if bundle['start'] else None,
            'expectedStartSnapshotHash':bundle['startHash'],'expectedReportSetHash':bundle['reportSetHash'],
            'expectedCompletionVersion':0,'expectedGenerationId':0,'expectedGenerationVersion':0,
            'expectedProductionRevision':gen.production_revision,'expectedProductionHash':gen.production_hash}
        if (original_ledger.audit_metadata.get('actorId')!=gen.applicant_id
                or original_ledger.audit_metadata.get('intentPayload')!=captured.get('intentPayload')
                or captured['intentPayload'].get('reason','').strip()!=gen.request_reason
                or any(captured['intentPayload'].get(k)!=v for k,v in expected_intent.items())
                or person.get('workflowProcessCode')!=PROCESS or person.get('workflowNodeCode')!=REQUEST_NODE
                or person.get('responsibilityCode')!=REQUEST_RESPONSIBILITY or person.get('ownershipType')!='EXECUTOR'
                or person.get('workflowNodeId')!=audits[0].after_snapshot['workflowNode']['nodeId']
                or not set(person['matchedRoleCodes']).issubset(set(audits[0].after_snapshot['authorization']['roleCodes']))):
            _fail('COMPLETION_GENERATION_INTENT_UNPROVEN','代次原申请人、原因及完整意图与正式账本不一致。')
        if gen.preceding_generation_id:
            previous=gen.preceding_generation
            if previous.status!='superseded' or not previous.closure_id:
                _fail('COMPLETION_GENERATION_REPLACEMENT_UNPROVEN','替代申请缺少原代次的真实本人关闭。')
            closed=closure_facts(previous.closure)
            withdrawn=_ledger(gen,WITHDRAW_ACTION,closed['requestHash'],closed['requestKeyHash'])
            root_intent=withdrawn.audit_metadata['intentPayload']
            derived={k:v for k,v in root_intent.items() if k in set(_legacy().EXPECTED)|{'reason'}|set(EXTRA_EXPECTED)}
            derived.update(expectedGenerationId=0,expectedGenerationVersion=0,expectedCompletionVersion=0)
            if (captured['intentPayload']!=derived or withdrawn.idempotency_key!=original_ledger.idempotency_key
                    or withdrawn.audit_metadata.get('actorId')!=gen.applicant_id
                    or previous.applicant_id!=gen.applicant_id
                    or root_intent.get('expectedLegacyRequestId')!=(previous.legacy_request_id if previous.protocol=='V2_BRIDGE'
                        else BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=previous.pk,version=1).get().pk)
                    or root_intent.get('expectedGenerationId')!=(0 if previous.protocol=='V2_BRIDGE' else previous.pk)
                    or root_intent.get('expectedGenerationVersion')!=(0 if previous.protocol=='V2_BRIDGE' else 1)
                    or root_intent.get('expectedCompletionVersion')!=1
                    or root_intent.get('expectedWorkflowVersion')!=1 or root_intent.get('expectedApprovalTaskVersion')!=1
                    or root_intent.get('withdrawReason','').strip()!=closed['reason']):
                _fail('COMPLETION_GENERATION_REPLACEMENT_UNPROVEN','替代申请未准确衍生自原本人撤回意图。')
        completed=gen.status=='approved'
        if completed:
            decision=gen.approval_decision
            if (not decision or decision.task_id!=gen.approval_task_id or decision.actor_id!=events[-1].operator_id
                    or decision.decision!='approved' or decision.action_id!=APPROVE_ACTION
                    or decision.actor_id==gen.applicant_id or decision.comment!=events[-1].reason
                    or decision.decision_hash!=last.get('approvalRequestHash')
                    or sha256(decision.idempotency_key.encode()).hexdigest()!=last.get('approvalRequestKeyHash')
                    or decision.decision_sequence!=1 or gen.approval_task.decisions.count()!=1
                    or gen.workflow_instance.status!='approved' or gen.approval_task.status!='approved'
                    or not isinstance(last.get('actorEvidence'),dict)
                    or not isinstance(last['actorEvidence'].get('matchedRoleCodes'),list)
                    or not last['actorEvidence']['matchedRoleCodes']
                    or any(not isinstance(x,str) or not x for x in last['actorEvidence']['matchedRoleCodes'])
                    or last['actorEvidence'].get('userId')!=decision.actor_id
                    or last['actorEvidence'].get('companyId')!=gen.company_id
                    or last['actorEvidence'].get('employeeId')==person['employeeId']
                    or any(type(last['actorEvidence'].get(k)) is not int or last['actorEvidence'][k]<=0 for k in
                        ('userId','companyId','employeeId','positionId','responsibilityId','positionResponsibilityId','workflowResponsibilityId','workflowNodeId'))
                    or last['actorEvidence'].get('uniqueEmployeeAccountLink') is not True
                    or last['actorEvidence'].get('currentEmploymentValid') is not True
                    or last['actorEvidence'].get('workflowProcessCode')!=PROCESS
                    or last['actorEvidence'].get('workflowNodeCode')!=REVIEW_NODE
                    or last['actorEvidence'].get('responsibilityCode')!=REVIEW_RESPONSIBILITY
                    or last['actorEvidence'].get('ownershipType')!='REVIEWER'
                    or last['actorEvidence'].get('workflowNodeId')!=audits[-1].after_snapshot['workflowNode']['nodeId']
                    or gen.approval_task.required_role_code not in last['actorEvidence']['matchedRoleCodes']
                    or not set(last['actorEvidence']['matchedRoleCodes']).issubset(set(audits[-1].after_snapshot['authorization']['roleCodes']))
                    or set(first['actorEvidence']['matchedRoleCodes']) & set(last['actorEvidence']['matchedRoleCodes'])):
                _fail('COMPLETION_GENERATION_DECISION_UNPROVEN','新版独立审核、人员/角色分离或决策不一致。')
            approval_ledger=_ledger(gen,APPROVE_ACTION,last['approvalRequestHash'],last['approvalRequestKeyHash'])
            if approval_ledger.audit_metadata.get('actorId')!=decision.actor_id:
                _fail('COMPLETION_GENERATION_DECISION_UNPROVEN','审核账本操作者与真实审核人不一致。')
        elif gen.approval_decision_id or gen.approval_task.decisions.exists():
            _fail('COMPLETION_GENERATION_DECISION_UNPROVEN','未审核代次出现不应存在的审核决策。')
        if gen.status=='pending' and (gen.workflow_instance.status!='pending' or gen.approval_task.status!='pending'):
            _fail('COMPLETION_GENERATION_WORKFLOW_UNPROVEN','待审代次共享状态不一致。')
        if (gen.workflow_instance.process_definition_id!=captured.get('definitionId')
                or gen.workflow_instance.process_definition.definition_hash!=captured.get('definitionHash')
                or captured.get('definitionHash')!=expected_definition_hash()
                or gen.workflow_instance.current_step!=1 or gen.workflow_instance.total_steps!=1
                or gen.workflow_instance.tasks.count()!=1
                or gen.approval_task.step_no!=1 or gen.approval_task.minimum_approvals!=1 or gen.approval_task.allow_parallel
                or gen.approval_task.required_role_code!=captured.get('reviewerRoleCode')):
            _fail('COMPLETION_GENERATION_WORKFLOW_UNPROVEN','代次共享模板、节点或审核角色不符合冻结合同。')
        for name,obj in (('WorkflowInstance',gen.workflow_instance),('ApprovalTask',gen.approval_task)):
            from .mes_evidence_graph import history as raw_history
            shared=raw_history(name,obj.pk,gen.company_id)
            if shared is NotImplemented:shared=list(BusinessStateTransition.objects.filter(object_type=name,object_id=obj.pk).order_by('version','pk'))
            expected_shared=[('','pending',REQUEST_ACTION)]+([('pending','approved',APPROVE_ACTION)] if completed else [])
            if gen.status=='superseded':
                if not gen.closure_id:_fail('COMPLETION_GENERATION_CLOSURE_UNPROVEN','撤回代次缺正式关闭记录。')
                closure_facts(gen.closure);shared=shared[:1]
            elif obj.version!=len(expected_shared) or len(shared)!=len(expected_shared) or bool(obj.completed_at)!=completed:
                _fail('COMPLETION_GENERATION_SHARED_HISTORY','共享对象状态、完成时间或历史长度不一致。')
            if len(shared)!=len(expected_shared):_fail('COMPLETION_GENERATION_SHARED_HISTORY','共享历史不完整。')
            for n,(event,triple) in enumerate(zip(shared,expected_shared),1):
                _,saved=_audit_state(event,name,obj.pk,gen.company_id)
                if (event.version!=n or (event.source_state,event.target_state,event.action_code)!=triple
                        or saved.get('generationId')!=gen.pk or saved.get('taskId')!=task.pk
                        or event.operator_id!=(gen.approval_decision.actor_id if n==2 else gen.applicant_id)
                        or event.workflow_instance_id!=gen.workflow_instance_id):
                    _fail('COMPLETION_GENERATION_SHARED_HISTORY','共享申请/审核历史不属于准确代次、人员或动作。')
        zone=task.work_order.source_schedule.timezone
        result={'contractVersion':CONTRACT,'completionProtocolVersion':3,'generationId':gen.pk,'generationSequence':gen.sequence,
            'generationVersion':gen.version,'generationStatusCode':gen.status,
            'statusCode':'completed' if completed else 'pending_review','statusLabel':LABELS[gen.status],
            'projectionVersion':2 if completed else 1,'sourceSnapshotHash':gen.source_snapshot_hash,
            'applicantId':gen.applicant_id,'applicantLabel':first['actorEvidence'].get('employeeName'),
            'requestReason':gen.request_reason,'requestedAtLabel':task_datetime_label(gen.requested_at,zone),
            'requestAuditReference':gen.request_audit_reference,'requestKeyHash':gen.request_key_hash,'requestHash':gen.request_hash,
            'reviewerId':gen.approval_decision.actor_id if completed else None,
            'reviewerLabel':last['actorEvidence'].get('employeeName') if completed else None,
            'reviewReason':events[-1].reason if completed else None,
            'completedAtLabel':task_datetime_label(audits[-1].created_at,zone) if completed else None,
            'approvalAuditReference':events[-1].audit_reference if completed else None,
            'approvalRequestKeyHash':last.get('approvalRequestKeyHash') if completed else None,
            'approvalRequestHash':last.get('approvalRequestHash') if completed else None,
            'workflowInstanceId':gen.workflow_instance_id,'workflowVersion':gen.workflow_instance.version,
            'approvalTaskId':gen.approval_task_id,'approvalTaskVersion':gen.approval_task.version,
            'approvalDecisionId':gen.approval_decision_id,'reviewerRoleCode':gen.approval_task.required_role_code,
            'applicantRoleCodes':first['actorEvidence']['matchedRoleCodes'],'stateMachineConsistent':True,
            'statusTransitionCount':len(events),'statusTransitionHistory':[{'id':e.pk,'version':e.version,
                'actionCode':e.action_code,'actionLabel':'提交工序完工申请' if e.action_code==REQUEST_ACTION else
                    '审核确认工序完工' if e.action_code==APPROVE_ACTION else '申请人撤回待审并关联替代',
                'sourceStateLabel':LABELS.get(e.source_state,'尚未申请完工'),'targetStateLabel':LABELS[e.target_state],
                'operatorId':e.operator_id,'timestampLabel':task_datetime_label(e.timestamp,zone),
                'auditReference':e.audit_reference} for e in events]}
    if gen.status=='superseded':
        if not gen.closure_id:
            _fail('COMPLETION_GENERATION_CLOSURE_UNPROVEN','已撤回代次缺少正式关闭事实。')
        closed=closure_facts(gen.closure)
        if (closed['sourceObjectType']!=OBJECT or closed['sourceObjectId']!=gen.pk
                or closed['replacementObjectType']!=OBJECT or closed['closedById']!=gen.applicant_id
                or closed['originalRequestReference']!=gen.request_audit_reference
                or not hasattr(gen,'replacement_generation') or closed['replacementObjectId']!=gen.replacement_generation.pk):
            _fail('COMPLETION_GENERATION_CLOSURE_UNPROVEN','关闭与替代代次没有准确相互引用。')
        terminal=BusinessStateTransition.objects.get(object_type=OBJECT,object_id=gen.pk,version=2)
        _,terminal_state=_audit_state(terminal,OBJECT,gen.pk,gen.company_id)
        if (terminal.operator_id!=gen.applicant_id or terminal.reason!=closed['reason']
                or terminal_state.get('withdrawRequestHash')!=closed['requestHash']
                or terminal_state.get('withdrawRequestKeyHash')!=closed['requestKeyHash']):
            _fail('COMPLETION_GENERATION_CLOSURE_UNPROVEN','原代次撤回转换与共享关闭的原申请人、原因或原请求不一致。')
        ledger=_ledger(gen.replacement_generation,WITHDRAW_ACTION,closed['requestHash'],closed['requestKeyHash'])
        if ledger.audit_metadata.get('actorId')!=gen.applicant_id:
            _fail('COMPLETION_GENERATION_CLOSURE_UNPROVEN','撤回原请求操作者不是原申请人。')
        result.update(statusCode='superseded',statusLabel=LABELS['superseded'],closure=closed,completionProven=False)
    return result


def _completion_chain(task,bundle,*,native_production_context=None):
    from .mes_evidence_graph import generations
    rows=generations(task)
    if not rows:
        if _orphan_v3_evidence_exists(task):
            _fail('COMPLETION_GENERATION_MISSING','新版完工存在正式账本或审计，但准确代次缺失；禁止视为尚未申请。')
        return _legacy()._legacy_history(task,bundle),[],[]
    previous=None;active=[];histories=[]
    for index,row in enumerate(rows,1):
        if row.sequence!=index or row.preceding_generation_id!=(previous.pk if previous else None):
            _fail('COMPLETION_GENERATION_CHAIN_UNPROVEN','整体完工代次顺序或紧前关联不一致。')
        proof=_proof(row,task,bundle,native_production_context=native_production_context);histories.append(proof)
        if row.status in ('pending','approved'):active.append(proof)
        previous=row
    if len(active)!=1 or rows[-1].status not in ('pending','approved'):
        _fail('COMPLETION_GENERATION_ACTIVE_UNPROVEN','每个任务必须且只能有一个当前待审或已生效整体代次。')
    return active[0],histories,rows


def read_effective_completion(task,bundle,*,native_production_context=None):
    return _completion_chain(task,bundle,native_production_context=native_production_context)[0]


def current_production_status(task,actor,completion,production=None):
    """Current admission is separate from the original immutable proof.

    Logistics/release revisions are deliberately absent from this producer
    snapshot. A later production correction cannot rewrite an old approval.
    """
    historical=bool(completion and completion.get('statusCode')=='completed'
        and completion.get('stateMachineConsistent') is True)
    if task.execution_mode!='QUANTIFIED':
        return {'historicalProofValid':historical,'quantityApplicable':False,'P':None,'R':None,'E':None,
            'currentAdmissionReady':None,'statusLabel':'不可统计任务按原实际经过及独立审核证明核验；不适用数量门禁。',
            'blockingIssues':[],'wholeProductionQuantity':None,'planQuantity':None,
            'wholeProductionCoversPlan':None,'productionChanged':False,
            'releaseAndCustodyAffectHistoricalProof':False}
    production=production or production_snapshot(task,actor)
    issues=production_issues(production)
    corrections=[p for p in production['payload'].get('productionCorrections',[])
        if p.get('statusCode')=='confirmed']
    captured=[]
    if historical and completion.get('completionProtocolVersion')==3:
        gen=Generation.objects.get(pk=completion['generationId'],task_id=task.pk,company_id=task.company_id)
        captured=[p for p in gen.production_snapshot['payload'].get('productionCorrections',[])
            if p.get('statusCode')=='confirmed']
    return {'historicalProofValid':historical,'currentAdmissionReady':not issues,
        'statusLabel':'当前生产事实已核实' if not issues else '当前生产事实存在阻断',
        'blockingIssues':list(dict.fromkeys(issues)),'productionRevision':production['revision'],
        'productionHash':production['hash'],'wholeProductionQuantity':production['wholeProductionQuantity'],
        'planQuantity':production['planQuantity'],'wholeProductionCoversPlan':production['wholeProductionCoversPlan'],
        'productionChanged':bool(historical and corrections!=captured),
        'currentCorrectionReferences':[{'ref':p.get('ref'),'proofHash':p.get('proofHash'),
            'quantity':p.get('quantity')} for p in corrections],
        'productionChangeNotice':'原独审生效后生产更正确认已有变化；原整体证明保留，当前是否准入仅按现有效产出及未决生产真实性异常判断。' if historical and corrections!=captured else None,
        'releaseAndCustodyAffectHistoricalProof':False}


def _reviewers(task,applicant_id,applicant_roles):
    from pfm.formal_employee import formal_employee_queryset
    definition,nodes=_setup();node=nodes.get(REVIEW_NODE)
    positions=PositionWorkflowResponsibility.objects.filter(workflow_node=node,workflow_code=PROCESS,
        node_code=REVIEW_NODE,ownership_type='REVIEWER',active=True).values_list('position_id',flat=True) if node else []
    people=formal_employee_queryset(company_id=task.company_id).filter(position_ref_id__in=positions,
        user__is_active=True,user__is_superuser=False).exclude(user_id=applicant_id)
    result=[]
    for person_id in people.values_list('user_id',flat=True).distinct():
        actor=User.objects.defer('password').get(pk=person_id);q=_role(actor,task,'approve')
        if q['ready'] and not set(q['roleCodes'])&set(applicant_roles):
            result.append({'userId':actor.pk,'label':q['currentActorEvidence'].get('employeeName'),'roleCodes':q['roleCodes']})
    return result


def qualification(actor,task,bundle,completion,key,production):
    legacy=_legacy();q=_role(actor,task,key);issues=q['missingItems'][:];lifecycle=[]
    issues.extend(bundle['issues']);issues.extend(production_issues(production))
    state=completion['statusCode'] if completion else 'unrequested'
    if key in ('request','withdrawReplace'):
        employee,position,_,_,_,valid=legacy.starts._identity(actor)
        from .operation_executor_scope import executor_scope
        scope=executor_scope(position,company_id=task.company_id,workshop_id=task.workshop_id,
            operation_id=task.source_operation.operation_id,work_center_id=task.work_center_id)
        if not scope['ready']:issues.extend(scope['missingItems'])
        if not (valid and legacy.starts._owned(actor,task,employee) and position
                and position.pk==task.execution_position_id and bundle['start']
                and bundle['start'].started_by_id==actor.pk):
            issues.append('须由原任务冻结执行人及实际开工人本人办理整体申请或撤回替代。')
        if key=='request' and completion:
            text='本任务已有当前整体申请或已审核生效，不得重复申请。';issues.append(text);lifecycle.append(text)
        if key=='withdrawReplace' and (not completion or state!='pending_review' or completion['applicantId']!=actor.pk):
            text='仅原申请人本人可撤回当前尚未审核的整体申请。';issues.append(text);lifecycle.append(text)
        request_role=q if key=='request' else _role(actor,task,'request')
        if key=='withdrawReplace':issues.extend(request_role['missingItems'])
        options=_reviewers(task,actor.pk,request_role['roleCodes']) if request_role['ready'] else []
        roles={role for option in options for role in option['roleCodes']}
        if len(roles)!=1:issues.append('未解析到与申请人员/角色分离的唯一正式新版审核角色。')
        q['reviewerRoleCode']=next(iter(roles)) if len(roles)==1 else None
        q['reviewerCandidates']=options
    else:
        if not completion or state!='pending_review':
            text='当前没有可以审核的新版待审整体申请。';issues.append(text);lifecycle.append(text)
        if completion:
            if completion['applicantId']==actor.pk:issues.append('申请人不能审核本人申请。')
            if set(q['roleCodes'])&set(completion['applicantRoleCodes']):issues.append('申请与审核角色必须独立。')
            if completion['reviewerRoleCode'] not in q['roleCodes']:issues.append('当前账号不属于本代次指定独立审核角色。')
            if completion.get('completionProtocolVersion')!=3:
                issues.append('原V2待审申请应沿原协议审核，或由本人明确撤回并替代新版。')
            else:
                gen=Generation.objects.get(pk=completion['generationId'])
                if gen.production_revision!=production['revision'] or gen.production_hash!=production['hash']:
                    issues.append('生产事实已变化；请由原申请人撤回待审并关联替代，不能用旧审核意图覆盖。')
    register_actions();decision=ActionPermissionValidator(fact_provider=legacy._Facts(actor,task,state)).evaluate(
        user=actor,module_code=MODULE,action_code=ACTION_SPECS[key][0],object_ids=[task.pk],selection_count=1,
        requested_legal_entity_id=str(task.company_id))
    if not decision['granted'] and not issues:issues.append(decision['reason'] or '本动作正式权限校验未通过。')
    issues=list(dict.fromkeys(issues));admission=[x for x in issues if x not in lifecycle]
    q.update(ready=not issues,missingItems=issues,admissionMissingItems=admission,lifecycleMissingItems=lifecycle,
        statusLabel='当前动作可办理' if not issues else '当前整体完工操作条件未通过')
    return q


def _actions(actor,task,bundle,completion,production):
    qs={key:qualification(actor,task,bundle,completion,key,production) for key in ACTION_SPECS}
    actions={key:{**action_contract(key,task.pk),'enabled':q['ready'],
        'disabledReason':'' if q['ready'] else '；'.join(q['missingItems'])} for key,q in qs.items()}
    return qs,actions


def reviewer_can_read(actor,task):
    return _role(actor,task,'approve')['ready']


def decorate_task_row(actor,task,bundle,completion,row,*,stage=None):
    from .operation_completion_shared_lifecycle import task_shared_workflow_lifecycle
    if task.execution_mode!='QUANTIFIED':
        row['completionProtocolVersion']=2
        row['sharedWorkflowLifecycle']=task_shared_workflow_lifecycle(actor=actor,task=task,bundle=bundle,completion=completion)
        return row
    stage=stage or completion_read_stage(task,actor,bundle);stage.validate(task,actor,bundle)
    if stage.current!=completion:_fail('COMPLETION_READ_STAGE_CHANGED','同次读取的当前整体投影不一致。')
    production=stage.production;generations=stage.generations;histories=stage.histories
    qs,actions=_actions(actor,task,bundle,completion,production)
    definition,nodes=_setup()
    use_v3=bool(generations or (completion is None and definition and all(nodes.values())))
    current=generations[-1] if generations else None
    row['completionProtocolVersion']=3 if use_v3 else 2
    row['quantityAccount']=quantity_account(task,actor,context=stage.context,whole_proof=stage.whole)
    row['completionV3']={'contractVersion':CONTRACT,'generationId':current.pk if current else 0,
        'generationVersion':current.version if current else 0,'productionRevision':production['revision'],
        'productionHash':production['hash'],'blockingIssues':production_issues(production),
        'generationHistory':histories,'availableActions':actions,'definitionReady':bool(definition and all(nodes.values())),
        'requestRecordId':completion['statusTransitionHistory'][0]['id'] if completion else 0,
        'productionSnapshot':deepcopy(production),
        'currentProductionStatus':current_production_status(task,actor,completion,production)}
    if use_v3:
        row['availableActions']=actions;row['requestQualification']=qs['request'];row['reviewQualification']=qs['approve']
        owned=bool(_legacy().starts._owned(actor,task,_legacy()._person(actor)[0]))
        row['qualification']=qs['request'] if owned else qs['approve']
        row['recordProgress']=_legacy()._record_progress(task,completion,row['qualification'])
        progress=row['recordProgress'];progress.update(contractVersion='PCE-OPERATION-COMPLETION-PROGRESS-V3',
            scope='ONE_ACTIVE_COMPLETION_GENERATION_PER_TASK',scopeLabel='每任务仅一个当前整体申请；本人可按正式动作撤回待审并关联替代，已生效不重复申请。')
        if completion:
            identity={**progress['recordIdentity'],'generationId':completion['generationId'],
                'generationSequence':completion['generationSequence'],'generationVersion':completion['generationVersion'],'protocolVersion':3}
            progress.update(recordIdentity=identity,recordKey=f"{OBJECT}:{task.company_id}:{completion['generationId']}:{progress['recordId']}")
    elif has_new_production(production) and completion and completion['statusCode']=='pending_review':
        text='出现新增生产事实，原申请人须明确撤回待审并关联替代V3，不能沿旧审核意图放行。'
        row['availableActions']['approve'].update(enabled=False,disabledReason=text)
        row['reviewQualification']['ready']=False;row['reviewQualification']['missingItems'].append(text)
    row['sharedWorkflowLifecycle']=task_shared_workflow_lifecycle(actor=actor,task=task,bundle=bundle,completion=completion,stage=stage)
    stage.validate(task,actor,bundle)
    return row


def ensure_legacy_write_allowed(task,actor):
    if Generation.objects.filter(task_id=task.pk).exists():
        _fail('COMPLETION_LEGACY_PROTOCOL_BLOCKED','本任务已有正式代次，请使用明确的新版本动作及当前代次。')
    if task.execution_mode=='QUANTIFIED' and has_new_production(production_snapshot(task,actor)):
        _fail('COMPLETION_LEGACY_PRODUCTION_CHANGED','已有补充生产事实或更正，禁止以旧payload绕过新事实。')


def readback_result(actor,task_id,query):
    if query is None:return None
    result={'status':'unknown','statusLabel':'本次准确操作结果仍待核实，请仅只读核查，不重复提交。',
        'actionCode':query['actionCode'],'generationId':query['generationId'],'submittedGenerationId':query['generationId'],
        'taskId':task_id,'companyId':actor.company_id,'actorId':actor.pk,
        'actualGenerationId':None,'requestHash':query['requestHash'],'requestKeyHash':query['requestKeyHash'],
        'proofRef':None,'auditReference':None,'businessWriteCount':0,'auditWriteCount':0}
    rows=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=query['actionCode'],
        entity_type=OBJECT,request_hash=query['requestHash'],audit_metadata__actorId=actor.pk,status='COMMITTED')
    matched=[]
    for ledger in rows:
        if sha256(ledger.idempotency_key.encode()).hexdigest()!=query['requestKeyHash']:continue
        payload=ledger.audit_metadata.get('intentPayload',{})
        if payload.get('expectedGenerationId')!=query['generationId']:continue
        gen=Generation.objects.filter(pk=ledger.target_entity_id,task_id=task_id,company_id=actor.company_id).first()
        if gen:
            _ledger(gen,query['actionCode'],query['requestHash'],query['requestKeyHash']);matched.append((gen,ledger))
    if len(matched)!=1:return result
    gen,ledger=matched[0]
    audit=gen.request_audit_reference
    proof=f'{OBJECT}:{gen.pk}'
    if query['actionCode']==WITHDRAW_ACTION:
        if not gen.preceding_generation_id or not gen.preceding_generation.closure_id:return result
        closed=closure_facts(gen.preceding_generation.closure)
        if closed['requestHash']!=query['requestHash'] or closed['requestKeyHash']!=query['requestKeyHash']:return result
        proof=f"WorkflowClosure:{closed['closureId']}";audit=closed['auditReference']
    elif query['actionCode']==APPROVE_ACTION:
        if gen.status!='approved':return result
        event=BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=gen.pk,action_code=APPROVE_ACTION).first()
        if not event:return result
        audit=event.audit_reference
    elif query['actionCode']!=REQUEST_ACTION:return result
    return {**result,'status':'verified','statusLabel':'本次准确操作已由正式原请求证明核实。',
        'actualGenerationId':gen.pk,'proofRef':proof,'auditReference':audit}


EXTRA_EXPECTED=('completionProtocolVersion','expectedGenerationId','expectedGenerationVersion',
    'expectedProductionRevision','expectedProductionHash')


def _payload(payload,key):
    legacy=_legacy()
    fields=set(legacy.EXPECTED)|{'reason','idempotencyKey'}|set(EXTRA_EXPECTED)
    if key in ('approve','withdrawReplace'):fields|={'expectedWorkflowVersion','expectedApprovalTaskVersion'}
    if key=='withdrawReplace':fields|={'withdrawReason','expectedLegacyRequestId'}
    if not isinstance(payload,dict) or set(payload)!=fields or payload.get('completionProtocolVersion')!=3:
        _fail('COMPLETION_V3_PAYLOAD_INVALID','新版完工意图须完整包含准确代次、生产事实版本和原请求。',400)
    ordinary={k:v for k,v in payload.items() if k in set(legacy.EXPECTED)|{'reason','idempotencyKey','expectedWorkflowVersion','expectedApprovalTaskVersion'}}
    legacy._payload(ordinary,'approve' if key in ('approve','withdrawReplace') else 'request')
    for field in ('expectedGenerationId','expectedGenerationVersion','expectedProductionRevision'):
        if type(payload[field]) is not int or payload[field]<0:
            _fail('COMPLETION_V3_EXPECTATION_INVALID','新版代次及生产事实期望版本无效。',400)
    if not isinstance(payload['expectedProductionHash'],str) or not re.fullmatch('[a-f0-9]{64}',payload['expectedProductionHash']):
        _fail('COMPLETION_V3_EXPECTATION_INVALID','新版生产证据Hash无效。',400)
    if key=='withdrawReplace':
        if type(payload['expectedLegacyRequestId']) is not int or payload['expectedLegacyRequestId']<=0:
            _fail('COMPLETION_V3_EXPECTATION_INVALID','撤回须准确引用原申请记录。',400)
        if not isinstance(payload['withdrawReason'],str) or not 2<=len(payload['withdrawReason'].strip())<=240:
            _fail('COMPLETION_V3_WITHDRAW_REASON_REQUIRED','请明确填写2至240字的撤回原因；替代申请原因另行填写。',400)


def _shared_initial(model,name,actor,task,gen,q,**fields):
    obj=create_business_object_with_initial_state(model=model,initial_state='pending',**fields)
    ref=_audit_event(actor,task,obj,name,REQUEST_ACTION,q,gen.request_reason,{'status':''},
        {'status':'pending','generationId':gen.pk,'taskId':task.pk,'requestHash':gen.request_hash})
    record_projected_business_transition(object_type=name,object_id=obj.pk,source_state='',target_state='pending',
        action_code=REQUEST_ACTION,operator=actor,reason=gen.request_reason,audit_reference=ref,
        workflow_instance=obj if name=='WorkflowInstance' else obj.workflow_instance,allowed_transitions={('','pending')})
    return obj,ref


def _new_generation(actor,task,bundle,production,q,payload,preceding=None):
    source,h=combined_source(bundle,production)
    seq=(Generation.objects.filter(task_id=task.pk).aggregate(n=Max('sequence'))['n'] or 0)+1
    request=intent_hash(actor.pk,task.company_id,REQUEST_ACTION,task.pk,payload)
    gen=create_business_object_with_initial_state(model=Generation,initial_state='pending',task=task,
        company_id=task.company_id,sequence=seq,protocol='V3',version=1,applicant=actor,
        preceding_generation=preceding,source_snapshot=source,source_snapshot_hash=h,
        production_snapshot=deepcopy(production),production_revision=production['revision'],production_hash=production['hash'],
        request_hash=request,request_key_hash=sha256(payload['idempotencyKey'].encode()).hexdigest(),
        request_snapshot={'actorEvidence':deepcopy(q['currentActorEvidence']),
            'intentPayload':{k:v for k,v in payload.items() if k!='idempotencyKey'},
            'definitionId':q['definitionId'],'definitionHash':q['definitionHash'],'reviewerRoleCode':q['reviewerRoleCode']},
        requested_at=timezone.now(),request_reason=payload['reason'].strip())
    wf,ref1=_shared_initial(WorkflowInstance,'WorkflowInstance',actor,task,gen,q,
        instance_no=f'MES-OC3-{task.company_id}-{gen.pk}',process_definition_id=q['definitionId'],document_type=OBJECT,
        document_id=gen.pk,current_step=1,total_steps=1,version=1)
    approval,ref2=_shared_initial(ApprovalTask,'ApprovalTask',actor,task,gen,q,
        task_no=f'MES-OC3-REVIEW-{task.company_id}-{gen.pk}',workflow_instance=wf,step_no=1,
        required_role_code=q['reviewerRoleCode'],minimum_approvals=1,allow_parallel=False,version=1)
    gen.workflow_instance=wf;gen.approval_task=approval;gen.save(update_fields=['workflow_instance','approval_task'])
    ref3=_audit_event(actor,task,gen,OBJECT,REQUEST_ACTION,q,gen.request_reason,{'status':''},
        {**_state(gen),'actorEvidence':deepcopy(q['currentActorEvidence'])})
    gen.request_audit_reference=ref3;gen.save(update_fields=['request_audit_reference'])
    record_projected_business_transition(object_type=OBJECT,object_id=gen.pk,source_state='',target_state='pending',
        action_code=REQUEST_ACTION,operator=actor,reason=gen.request_reason,audit_reference=ref3,
        workflow_instance=wf,allowed_transitions={('','pending')})
    _write_ledger(gen,actor,REQUEST_ACTION,payload,{'taskId':task.pk,'generationId':gen.pk,
        'workflowInstanceId':wf.pk,'approvalTaskId':approval.pk,'completed':False})
    return gen,[ref1,ref2,ref3]


def _bridge(actor,task,bundle,completion,q):
    if Generation.objects.filter(task_id=task.pk).exists():
        _fail('COMPLETION_BRIDGE_CONFLICT','任务已有代次，不得再次桥接原申请。')
    request=BusinessStateTransition.objects.get(pk=completion['statusTransitionHistory'][0]['id'])
    historical={'legacyProtocol':2,'captureStatus':'NOT_CAPTURED_BY_LEGACY_REQUEST',
        'originalRequestReference':completion['requestAuditReference'],'reportSetHash':bundle['reportSetHash']}
    gen=create_business_object_with_initial_state(model=Generation,initial_state='pending',task=task,
        company_id=task.company_id,sequence=1,protocol='V2_BRIDGE',version=1,applicant=actor,
        legacy_request=request,workflow_instance_id=completion['workflowInstanceId'],approval_task_id=completion['approvalTaskId'],
        source_snapshot=deepcopy(bundle['snapshot']),source_snapshot_hash=completion['sourceSnapshotHash'],
        production_snapshot=historical,production_revision=0,production_hash=_hash(historical),
        request_snapshot={'originalRequestReference':completion['requestAuditReference'],'bridgeOnly':True},
        request_hash=completion['requestHash'],request_key_hash=completion['requestKeyHash'],
        requested_at=request.timestamp,request_reason=completion['requestReason'],request_audit_reference=completion['requestAuditReference'])
    ref=_audit_event(actor,task,gen,OBJECT,WITHDRAW_ACTION,q,'承接原待审申请以办理本人明确撤回；未重办申请或审核。',
        {'status':''},{**_state(gen),'actorEvidence':deepcopy(q['currentActorEvidence']),'bridgeOnly':True})
    record_projected_business_transition(object_type=OBJECT,object_id=gen.pk,source_state='',target_state='pending',
        action_code=WITHDRAW_ACTION,operator=actor,reason='承接原待审申请以办理本人明确撤回；未重办申请或审核。',
        audit_reference=ref,workflow_instance=gen.workflow_instance,allowed_transitions={('','pending')})
    return gen,ref


def _advance(gen,actor,task,q,target,code,reason,extra=None):
    before=_state(gen);after={**before,'status':target,'version':gen.version+1,
        'actorEvidence':deepcopy(q['currentActorEvidence']),**(extra or {})}
    ref=_audit_event(actor,task,gen,OBJECT,code,q,reason,before,after)
    transition_business_object(business_object=gen,object_type=OBJECT,source_state='pending',target_state=target,
        action_code=code,operator=actor,reason=reason,audit_reference=ref,workflow_instance=gen.workflow_instance,
        allowed_transitions={('pending',target)},updated_at_field=None)
    return ref


def _approve_shared(obj,name,gen,task,actor,q,reason):
    ref=_audit_event(actor,task,obj,name,APPROVE_ACTION,q,reason,{'status':'pending'},
        {'status':'approved','generationId':gen.pk,'taskId':task.pk})
    obj.completed_at=timezone.now();obj.save(update_fields=['completed_at'])
    transition_business_object(business_object=obj,object_type=name,source_state='pending',target_state='approved',
        action_code=APPROVE_ACTION,operator=actor,reason=reason,audit_reference=ref,
        workflow_instance=gen.workflow_instance,allowed_transitions={('pending','approved')},updated_at_field=None)
    return ref


def _writes(key=None,refs=(),generation_count=0,closure_count=0):
    return {**_legacy()._writes(), 'businessWriteCount':1 if key else 0,'auditWriteCount':len(refs),
        'stateTransitionWriteCount':len(refs),'completionRequestCreatedCount':1 if key in ('request','withdrawReplace') else 0,
        'completionCreatedCount':1 if key=='approve' else 0,'approvalDecisionCreatedCount':1 if key=='approve' else 0,
        'completionGenerationCreatedCount':generation_count,'workflowClosureCreatedCount':closure_count,
        'quantityAccountCASWriteCount':1}


def execute(*,user,task_id,payload,action='request'):
    if action not in ACTION_SPECS:_fail('COMPLETION_V3_ACTION_INVALID','新版整体完工动作不在正式合同。',400)
    _payload(payload,action)
    if type(task_id) is not int or task_id<=0:_fail('OPERATION_COMPLETION_QUERY_INVALID','任务身份须为正整数。',400)
    legacy=_legacy();actor,_=legacy.receipt._actor(user);code=ACTION_SPECS[action][0]
    from .workshop_task_models import ProductionWorkshopTask
    try:
        with completion_writer_context(actor,task_id):
            task=ProductionWorkshopTask.objects.select_for_update().filter(pk=task_id,company_id=actor.company_id).select_related(
                'work_order__production_plan','source_operation__effective_step','source_operation__work_center__workshop','workshop','work_center').first()
            if not task or task.execution_mode!='QUANTIFIED':
                _fail('COMPLETION_V3_TASK_INVALID','新版数量完工代次仅适用于本公司准确正量任务。',403)
            bundle=validated_bundle(task,actor);stage=completion_read_stage(task,actor,bundle)
            completion=stage.current;production=stage.production
            q=qualification(actor,task,bundle,completion,action,production)
            h=intent_hash(actor.pk,task.company_id,code,task.pk,payload);keyhash=sha256(payload['idempotencyKey'].encode()).hexdigest()
            old=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=code,idempotency_key=payload['idempotencyKey']).first()
            if old:
                gen=Generation.objects.filter(pk=old.target_entity_id,task_id=task.pk,company_id=actor.company_id).first()
                if not gen or old.request_hash!=h or not _role(actor,task,action)['ready']:
                    _fail('COMPLETION_V3_IDEMPOTENCY_CONFLICT','原标识已用于其他对象、人员或操作意图。')
                _ledger(gen,code,h,keyhash)
                return legacy.read_operation_completions(user=actor,task_id=task.pk,_verified_stage=stage),_writes()
            current=Generation.objects.filter(task_id=task.pk,status__in=('pending','approved')).first()
            expected={'expectedVersion':task.version,'expectedSourceSnapshotHash':task.source_snapshot_hash,
                'expectedAssignmentHash':task.assignment_hash,'expectedStartId':bundle['start'].pk if bundle['start'] else None,
                'expectedStartSnapshotHash':bundle['startHash'],'expectedReportSetHash':bundle['reportSetHash'],
                'expectedCompletionVersion':completion['projectionVersion'] if completion else 0,
                'expectedGenerationId':current.pk if current else 0,'expectedGenerationVersion':current.version if current else 0,
                'expectedProductionRevision':production['revision'],'expectedProductionHash':production['hash']}
            if action in ('approve','withdrawReplace'):
                expected.update(expectedWorkflowVersion=completion['workflowVersion'] if completion else None,
                    expectedApprovalTaskVersion=completion['approvalTaskVersion'] if completion else None)
            if action=='withdrawReplace':expected['expectedLegacyRequestId']=completion['statusTransitionHistory'][0]['id'] if completion else None
            if any(payload[k]!=v for k,v in expected.items()):
                _fail('COMPLETION_V3_SOURCE_OR_VERSION_CHANGED','原申请、准确代次或当前生产事实已变化，请只读核查。')
            if not q['ready']:_fail('COMPLETION_V3_NOT_READY','；'.join(q['missingItems']),403)
            refs=[];created=0;closed_count=0
            if action=='request':
                gen,refs=_new_generation(actor,task,bundle,production,q,payload);created=1
            elif action=='approve':
                gen=current
                decision=ApprovalDecision.objects.create(task_id=gen.approval_task_id,decision_sequence=1,actor=actor,
                    decision='approved',comment=payload['reason'].strip(),action_id=APPROVE_ACTION,
                    idempotency_key=payload['idempotencyKey'],decision_hash=h)
                gen.approval_decision=decision;gen.save(update_fields=['approval_decision'])
                refs=[_approve_shared(gen.approval_task,'ApprovalTask',gen,task,actor,q,payload['reason'].strip()),
                    _approve_shared(gen.workflow_instance,'WorkflowInstance',gen,task,actor,q,payload['reason'].strip()),
                    _advance(gen,actor,task,q,'approved',APPROVE_ACTION,payload['reason'].strip(),
                        {'approvalRequestHash':h,'approvalRequestKeyHash':keyhash})]
                _write_ledger(gen,actor,APPROVE_ACTION,payload,{'taskId':task.pk,'generationId':gen.pk,
                    'workflowInstanceId':gen.workflow_instance_id,'approvalTaskId':gen.approval_task_id,'completed':True})
            else:
                oldgen=current
                if oldgen is None:
                    oldgen,ref=_bridge(actor,task,bundle,completion,q);refs.append(ref);created+=1
                refs.append(_advance(oldgen,actor,task,q,'superseded',WITHDRAW_ACTION,payload['withdrawReason'].strip(),
                    {'withdrawRequestHash':h,'withdrawRequestKeyHash':keyhash}))
                replacement={k:v for k,v in payload.items() if k in set(legacy.EXPECTED)|{'reason','idempotencyKey'}|set(EXTRA_EXPECTED)}
                replacement.update(expectedGenerationId=0,expectedGenerationVersion=0,expectedCompletionVersion=0)
                request_q=qualification(actor,task,bundle,None,'request',production)
                if not request_q['ready']:_fail('COMPLETION_V3_REPLACEMENT_NOT_READY','；'.join(request_q['missingItems']),403)
                gen,newrefs=_new_generation(actor,task,bundle,production,request_q,replacement,oldgen);refs.extend(newrefs);created+=1
                closed=close_pending_workflow(workflow=oldgen.workflow_instance,approval_task=oldgen.approval_task,
                    actor=actor,applicant_id=oldgen.applicant_id,expected_workflow_version=payload['expectedWorkflowVersion'],
                    expected_approval_version=payload['expectedApprovalTaskVersion'],action_code=WITHDRAW_ACTION,
                    reason=payload['withdrawReason'].strip(),authorization=q['authorization'],source_object_type=OBJECT,
                    source_object_id=oldgen.pk,replacement_object_type=OBJECT,replacement_object_id=gen.pk,
                    original_request_reference=oldgen.request_audit_reference,request_hash=h,request_key_hash=keyhash)
                oldgen.closure=closed;oldgen.save(update_fields=['closure']);closed_count=1
                proof=closure_facts(closed);refs.extend(group['statusTransitionHistory'][-1]['auditReference'] for group in proof['sharedHistory'])
                _write_ledger(gen,actor,WITHDRAW_ACTION,payload,{'taskId':task.pk,'generationId':gen.pk,
                    'precedingGenerationId':oldgen.pk,'closureId':closed.pk,'completed':False})
            # The response reader below performs the one complete post-write
            # chain verification in this same transaction. A write-invalidated
            # Stage is never passed into that read.
            return legacy.read_operation_completions(user=actor,task_id=task.pk),_writes(action,refs,created,closed_count)
    except WorkflowClosureError as error:
        _fail('COMPLETION_SHARED_CLOSURE_UNPROVEN',str(error))
    except IntegrityError:
        _fail('COMPLETION_V3_CONCURRENT_CONFLICT','任务已被并发申请、审核或替代，请只读核查，不自动重试。')
