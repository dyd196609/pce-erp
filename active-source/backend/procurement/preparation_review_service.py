"""One native preparation-review stage; original shared decisions and transitions."""
import copy
import uuid
from django.db import transaction
from django.utils import timezone
from masterdata.models import MasterDataWriteRequest
from pde.product_design_service import _canonical_hash, _write_request, _commit_request
from pfm.formal_employee import is_formal_employee
from system.authorization import AuthorizationService
from system.models import (OrganizationOperatingAuditRecord, PositionResponsibility,
                           PositionWorkflowResponsibility)
from workflow_runtime.models import (ProcessDefinition, WorkflowInstance,
                                    ApprovalTask, ApprovalDecision, BusinessStateTransition)
from workflow_runtime.state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition, transition_business_object)
from .models import PriceApprovalPreparation, QuoteComparisonFact, PurchaseInquiry, PurchaseRequestItem
from .scm_runtime_services import _business_date
from .fact_read_access import (validate_read_identity, read_qualification, context_allowed,
                               permission_role_evidence, object_read_context)
from .scm_read_permission_catalog import PREPARATION_SCOPE
from .comparison_registration_service import (CONTRACT as REGISTRATION_CONTRACT,
    ComparisonRegistrationError, fail, identifier, text, verify_registered_fact,
    _source_objects, _source_bundle)

CONTRACT = "PCE-NATIVE-PREPARATION-SINGLE-REVIEW-V1"
PERMISSION = "procurement.price_approval_preparation.review"
PERMISSION_NAME = "核价准备审核"
PROCESS = "SCM_PRICE_PREPARATION_REVIEW"
NODE = "PREPARATION_REVIEW"
DUTY = "SCM_PRICE_PREPARATION_REVIEW"
ENTITY = "PreparationReviewAction"
ACTIONS = {"START_REVIEW", "SUBMIT_REVIEW", "REOPEN_REVIEW"}
ACTION_CONTRACT = {"contractVersion":CONTRACT, "requiredPermission":PERMISSION,
    "role":"purchase_manager", "organizationScope":"EXISTING_ROLE_SCOPE",
    "serverValidator":"procurement.preparation_review_service.execute_review",
    "singleReviewStage":True, "actions":sorted(ACTIONS),
    "forbidden":["PRICE_CONFIRM", "PRICE_APPROVE", "ORDER_APPROVE", "PAYMENT_EXECUTE"]}
ACTION_LABELS={'START_REVIEW':'进入核价准备审核','SUBMIT_REVIEW':'提交核价审核结论','REOPEN_REVIEW':'调整后重新核价'}
ACTION_CONTRACT['actionContracts']=[{'actionCode':a,'moduleCode':'SCM_PRICE_APPROVAL',
    'displayName':ACTION_LABELS[a],'requiredPermission':PERMISSION,'role':'purchase_manager',
    'organizationScope':'EXISTING_ROLE_SCOPE','serverValidator':ACTION_CONTRACT['serverValidator']}
    for a in sorted(ACTIONS)]
RESULT_LABELS = {"pass":"通过", "reject":"不同意", "adjust":"调整后重新核价"}


def is_native(preparation):
    return bool(preparation.fact_origin == "production_fact" and preparation.source_comparison_id
        and preparation.source_comparison.comparison_result.get("contractVersion") == REGISTRATION_CONTRACT)


def qualification(user):
    validate_read_identity(user)
    if user.is_superuser or not any(x.role_code == "purchase_manager" and
            PERMISSION in AuthorizationService.permission_codes_for_user(user,{x.role_code})
            for x in AuthorizationService.authority_evidence(user)):
        fail("PREPARATION_REVIEW_DENIED", "当前岗位没有核价准备审核执行资格。", 403)


def _load(user, preparation_id, *, lock=False):
    validate_read_identity(user);read_qualification(user, PREPARATION_SCOPE)
    rows=PriceApprovalPreparation.objects.select_related("source_comparison")
    if lock:rows=rows.select_for_update()
    p=rows.filter(pk=identifier(preparation_id)).first()
    if p is None:fail("PREPARATION_REVIEW_NOT_FOUND", "准备不存在或不在当前授权范围。",404)
    if not is_native(p):fail("PREPARATION_REVIEW_SOURCE_PENDING", "历史准备的正式来源继续待核，不补造关系。")
    snapshot,event,_=verify_registered_fact(p.source_comparison)
    from .price_approval_preparation_service import _candidate_from_evidence
    fact=p.source_comparison
    if (p.comparison_basis!=fact.comparison_result or p.source_quotation_evidence!=fact.supplier_quote_evidence
            or p.supplier_candidates!=[_candidate_from_evidence(x) for x in fact.supplier_quote_evidence]
            or p.material_lines!=[{'materialCode':fact.material_code,'materialName':fact.material_name,'quantity':str(fact.quantity)}]):
        fail('PREPARATION_REVIEW_SOURCE_PENDING','准备资料与其冻结比较版本不一致，不能自行补造或办理。')
    inquiry,item,context=_source_objects(user,snapshot['inquiry']['id'],snapshot['requestItem']['id'],lock=lock)
    if not context_allowed(user, PREPARATION_SCOPE, context):
        fail("PREPARATION_REVIEW_NOT_FOUND", "准备不存在或不在当前授权范围。",404)
    return p,snapshot,event,inquiry,item,context


def _authority(user, snapshot, registrant, context):
    qualification(user)
    facts={**context,"departmentId":context.get('departmentId') or '__NOT_PROVIDED__',
           "ownerUserId":context.get('ownerUserId') or '__NOT_PROVIDED__'}
    if context['organizationId'] != user.company_id or not any(x.role_code=='purchase_manager'
            and AuthorizationService._scope_matches(x,user,facts,{})
            for x in permission_role_evidence(user,PERMISSION,context['organizationId'])):
        fail("PREPARATION_REVIEW_SCOPE_DENIED", "超出采购经理原有效审核范围。",403)
    applicant=context.get('ownerUserId')
    if not applicant:fail("PREPARATION_APPLICANT_UNPROVEN", "来源申请人缺少准确身份依据。")
    if user.pk in {applicant,registrant.actor_id}:
        fail("PREPARATION_REVIEW_SEPARATION", "审核人必须与来源申请人、正式比较登记者分离。",403)
    employee=getattr(user,'employee_profile',None)
    if not is_formal_employee(employee,company_id=user.company_id):
        fail("PREPARATION_REVIEW_POSITION_REQUIRED", "缺少有效员工及岗位任职。",403)
    today=_business_date()
    mappings=PositionWorkflowResponsibility.objects.select_related('responsibility','workflow_node__process_definition').filter(
        position=employee.position_ref,active=True,ownership_type='OWNER',responsibility__code=DUTY,
        responsibility__is_active=True,responsibility__status='ACTIVE',
        workflow_node__node_code=NODE,workflow_node__active=True,
        workflow_node__business_action_code=PERMISSION,
        workflow_node__process_definition__definition_code=PROCESS,
        workflow_node__process_definition__document_type='PriceApprovalPreparation',
        workflow_node__process_definition__active=True)
    for m in mappings:
        definition=m.workflow_node.process_definition
        if (m.workflow_code!=PROCESS or m.node_code!=NODE or definition.version!=1
                or m.workflow_node.sequence!=1 or definition.nodes.filter(active=True).count()!=1):
            fail('PREPARATION_REVIEW_PROCESS_UNPROVEN','正式单环节定义及节点身份不一致。')
        periods=[(m.effective_from,m.effective_to),(m.responsibility.effective_from,m.responsibility.effective_to)]
        if all((not a or a<=today) and (not b or b>=today) for a,b in periods) and PositionResponsibility.objects.filter(
                position=employee.position_ref,responsibility=m.responsibility,active=True).exists():
            decision=AuthorizationService.decide(user=user,action_code=PERMISSION,
                organization_id=context['organizationId'],business_object=context)
            if not decision.get('allowed'):fail('PREPARATION_REVIEW_DENIED','原授权服务未准入本次审核。',403)
            return m.workflow_node.process_definition,decision
    fail("PREPARATION_REVIEW_DUTY_REQUIRED", "当前岗位没有生效的本核价审核职责及流程节点。",403)


def _state(p):
    return {'status':p.status,'decisionVersion':p.decision_version,'reviewResult':p.review_result,
        'opinion':p.review_opinion,'approvalOpinion':p.approval_opinion,
        'reviewer':p.reviewer,'reviewedAt':p.reviewed_at.isoformat() if p.reviewed_at else None,
        'selectedSupplier':copy.deepcopy(p.selected_supplier)}


def _workflow(p,lock=False):
    rows=WorkflowInstance.objects.select_related('process_definition')
    if lock:rows=rows.select_for_update()
    wf=rows.filter(document_type='PriceApprovalPreparation',document_id=p.pk).first()
    if wf and (wf.process_definition.definition_code!=PROCESS or wf.total_steps!=1 or wf.current_step!=1):
        fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','准备对应的共享流程身份不一致。')
    return wf


def _history(p):
    events=list(OrganizationOperatingAuditRecord.objects.filter(action_code=PERMISSION,
        target_type='PriceApprovalPreparation',target_id=p.pk).order_by('pk'))
    wf=_workflow(p);task=wf.tasks.filter(step_no=1).first() if wf else None
    decisions=list(task.decisions.order_by('decision_sequence')) if task else []
    transitions=list(BusinessStateTransition.objects.filter(object_type='PriceApprovalPreparation',
        object_id=p.pk,action_code=PERMISSION).order_by('version'))
    if len(transitions)!=len(events) or p.decision_version!=len(decisions):
        fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','审核决定及状态转换事实不完整。')
    if not events:
        if wf or p.status!='draft' or p.decision_version or p.review_result:
            fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','准备缺少准确审核初始化依据。')
        return [],None,None
    if not wf or not task or wf.tasks.count()!=1 or task.required_role_code!='purchase_manager':
        fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','共享审核任务不完整。')
    history=[];previous='draft';finished=0
    for event,transition in zip(events,transitions):
        proof=event.after_snapshot.get('review',{})
        if not isinstance(proof,dict):fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','审核来源证明格式不完整。')
        request=MasterDataWriteRequest.objects.filter(pk=proof.get('writeRequestId'),action_code=PERMISSION,
            entity_type=ENTITY,organization_id=event.organization_id,status='COMMITTED').first()
        if (proof.get('contractVersion')!=CONTRACT or proof.get('preparationId')!=p.pk
                or proof.get('comparisonFactId')!=str(p.source_comparison_id)
                or proof.get('comparisonVersion')!=p.source_comparison.fact_version
                or proof.get('sourceFingerprint')!=p.source_comparison.comparison_result['sourceFingerprint']
                or proof.get('workflowInstanceId')!=wf.pk or proof.get('approvalTaskId')!=task.pk
                or proof.get('actorId')!=event.actor_id or proof.get('beforeStatus')!=previous
                or transition.audit_reference!=f'OrganizationOperatingAuditRecord:{event.pk}'
                or transition.operator_id!=event.actor_id or transition.source_state!=previous
                or transition.target_state!=proof.get('state',{}).get('status')
                or not request or request.result.get('auditId')!=event.pk
                or request.audit_metadata.get('actorId')!=event.actor_id
                or request.audit_metadata.get('preparationId')!=p.pk
                or request.audit_metadata.get('action')!=proof.get('action')
                or not event.after_snapshot.get('authorization',{}).get('allowed')
                or request.request_hash!=_canonical_hash(request.audit_metadata)
                or proof.get('proofHash')!=_canonical_hash({k:v for k,v in proof.items() if k!='proofHash'})):
            fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','审核审计、来源、同次动作及转换不一致。')
        if proof['action']=='SUBMIT_REVIEW':
            finished+=1;d=decisions[finished-1] if len(decisions)>=finished else None
            value=proof.get('decision',{})
            if (not d or d.pk!=proof.get('approvalDecisionId') or d.decision_sequence!=finished
                    or d.actor_id!=event.actor_id or d.decision!=value.get('result')
                    or d.decision_hash!=_canonical_hash(value) or d.comment!=value.get('opinion')
                    or value.get('reason')!=event.reason):
                fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','共享审核决定与版本依据不一致。')
        history.append({'auditId':event.pk,'action':proof['action'],'actorId':event.actor_id,
            'occurredAt':event.created_at.isoformat(),'reason':event.reason,
            'comparisonFactId':proof['comparisonFactId'],'comparisonVersion':proof['comparisonVersion'],
            'sourceFingerprint':proof['sourceFingerprint'],'decisionVersion':proof['state']['decisionVersion'],
            'result':(proof.get('decision') or {}).get('result'),'resultLabel':RESULT_LABELS.get((proof.get('decision') or {}).get('result')),
            'opinion':(proof.get('decision') or {}).get('opinion'),'selectedSupplier':proof['state']['selectedSupplier']})
        previous=proof['state']['status']
    for obj,name in [(wf,'WorkflowInstance'),(task,'ApprovalTask')]:
        chain=list(BusinessStateTransition.objects.filter(object_type=name,object_id=obj.pk).order_by('version'))
        if len(chain)!=len(events) or obj.version!=len(events):
            fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','共享流程转换数量及版本不一致。')
        prior=''
        for index,(t,parent) in enumerate(zip(chain,events),1):
            prefix='OrganizationOperatingAuditRecord:'
            audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(t.audit_reference[len(prefix):])).first() if t.audit_reference.startswith(prefix) and t.audit_reference[len(prefix):].isdigit() else None
            if (not audit or audit.target_type!=name or audit.target_id!=obj.pk
                    or audit.actor_id!=parent.actor_id or audit.organization_id!=parent.organization_id
                    or audit.action_code!=PERMISSION or audit.reason!=parent.reason
                    or audit.before_snapshot.get('state',{}).get('status')!=prior
                    or audit.after_snapshot.get('state',{}).get('status')!=t.target_state
                    or t.source_state!=prior or t.version!=index or t.operator_id!=parent.actor_id
                    or t.action_code!=PERMISSION or t.workflow_instance_id!=wf.pk):
                fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','共享对象转换与真实审计不一致。')
            prior=t.target_state
        if prior!=obj.status:fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','共享对象当前状态与转换链不一致。')
    latest=events[-1].after_snapshot['review']
    if (finished!=len(decisions) or latest['state']!=_state(p)
            or latest['workflowVersion']!=wf.version or latest['approvalTaskVersion']!=task.version
            or latest['workflowStatus']!=wf.status or latest['approvalTaskStatus']!=task.status):
        fail('PREPARATION_REVIEW_HISTORY_INCONSISTENT','当前审核投影与已提交共享事实不一致。')
    return history,wf,task


def current_result(p):
    history,_,_=_history(p)
    return history[-1]['result'] if p.status=='completed' and history else ''


def native_received(p):
    snapshot,_,_=verify_registered_fact(p.source_comparison)
    return bool(snapshot['quotations']) and all(x['quotationStatus']=='received' and x['receivedAt']
        for x in snapshot['quotations'])


def _fresh(p,inquiry,item,context,*,lock=False):
    later=QuoteComparisonFact.objects.filter(comparison_no=p.source_comparison.comparison_no,
        fact_version__gt=p.source_comparison.fact_version)
    if later.exists():
        for row in later:verify_registered_fact(row)
        fail('PREPARATION_REVIEW_VERSION_SUPERSEDED','已有正式后续比较版本，原版保留追溯；请办理准确新版准备。')
    if _canonical_hash(_source_bundle(inquiry,item,context,lock=lock))!=p.source_comparison.comparison_result['sourceFingerprint']:
        fail('PREPARATION_REVIEW_SOURCE_CHANGED','来源或比较依据已变化，须按正式新版办理。')


def recommendation_reason(p):
    """Factual eligibility only; never grants a downstream action permission."""
    _history(p)
    snapshot,_,_=verify_registered_fact(p.source_comparison)
    inquiry=PurchaseInquiry.objects.select_related('source_purchase_request').filter(pk=snapshot['inquiry']['id']).first()
    item=PurchaseRequestItem.objects.select_related('material').filter(pk=snapshot['requestItem']['id'],
        purchase_request_id=snapshot['request']['id']).first()
    context=object_read_context(inquiry.source_purchase_request) if inquiry else None
    if not inquiry or not item or not context:return '原生核价来源或责任依据待核，不能进入后序。'
    try:_fresh(p,inquiry,item,context)
    except ComparisonRegistrationError as error:return str(error)
    return ''


@transaction.atomic
def review_context(*,user,preparation_id):
    p,snapshot,registrant,inquiry,item,context=_load(user,preparation_id)
    history,wf,task=_history(p);actions=[];blocked=[]
    try:
        _authority(user,snapshot,registrant,context)
        _fresh(p,inquiry,item,context)
        actions=({'draft':['START_REVIEW'],'reviewing':['SUBMIT_REVIEW']}.get(p.status) or
            (['REOPEN_REVIEW'] if p.status=='completed' and current_result(p)=='adjust' else []))
    except ComparisonRegistrationError as error:
        blocked=[{'code':error.code,'message':str(error)}]
    return {'contractVersion':CONTRACT,'preparationId':p.pk,'approvalPrepareNo':p.approval_prepare_no,
        'sourceComparisonFactId':str(p.source_comparison_id),'sourceComparisonVersion':p.source_comparison.fact_version,
        'sourceFingerprint':p.source_comparison.comparison_result['sourceFingerprint'],
        'decisionVersion':p.decision_version,'workflowVersion':wf.version if wf else 0,
        'statusCode':p.status,'statusLabel':p.get_status_display(),
        'currentResult':current_result(p) or None,'currentResultLabel':RESULT_LABELS.get(current_result(p)),
        'history':history,'availableActions':actions,'blockedReasons':blocked,
        'singleReviewStage':True,'readDoesNotAuthorizeExecution':True,'automaticReplayAllowed':False,
        'priceConfirmed':False,'priceApproved':False,'purchaseOrderApproved':False,'businessWriteCount':0}


def _receipt(row):
    return {**row.result,'resultState':'COMMITTED','receiptAsOf':row.updated_at.isoformat(),
        'stateMeaning':'ORIGINAL_ACTION_RESULT_NOT_CURRENT_ELIGIBILITY','executionAuthorizedByResult':False,
        'automaticReplayAllowed':False,'businessWriteCount':0}


@transaction.atomic
def action_result(*,user,preparation_id,key):
    qualification(user);p,*_= _load(user,preparation_id);_history(p)
    row=MasterDataWriteRequest.objects.filter(organization_id=user.company_id,action_code=PERMISSION,
        entity_type=ENTITY,idempotency_key=text(key,'同次动作键',120)).first()
    if row and (row.audit_metadata.get('actorId')!=user.pk or row.audit_metadata.get('preparationId')!=p.pk):
        fail('PREPARATION_REVIEW_RESULT_NOT_FOUND','该同次结果不属于当前办理人及对象。',404)
    return _receipt(row) if row and row.status=='COMMITTED' else {
        'resultState':'UNKNOWN','result':None,'automaticReplayAllowed':False,'businessWriteCount':0}


def _audit(user,obj,name,before,after,reason,authorization):
    event=OrganizationOperatingAuditRecord.objects.create(action_code=PERMISSION,actor=user,
        organization_id=user.company_id,target_type=name,target_id=obj.pk,target_label=f'{name}:{obj.pk}',
        reason=reason,before_snapshot={'state':before},after_snapshot={'state':after,'authorization':authorization})
    return event


def _initial(user,obj,name,reason,authorization,wf):
    e=_audit(user,obj,name,{'status':''},{'status':'pending'},reason,authorization)
    record_projected_business_transition(object_type=name,object_id=obj.pk,source_state='',target_state='pending',
        action_code=PERMISSION,operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{e.pk}',
        workflow_instance=wf,allowed_transitions={('','pending')})


def _transition(user,obj,name,target,reason,authorization,wf,*,version_field='version',reference=None):
    source=obj.status
    if reference is None:
        e=_audit(user,obj,name,{'status':source},{'status':target},reason,authorization)
        reference=f'OrganizationOperatingAuditRecord:{e.pk}'
    return transition_business_object(business_object=obj,object_type=name,source_state=source,target_state=target,
        action_code=PERMISSION,operator=user,reason=reason,audit_reference=reference,workflow_instance=wf,
        allowed_transitions={(source,target)},version_field=version_field,
        updated_at_field='updated_at' if name=='PriceApprovalPreparation' else None)


@transaction.atomic
def execute_review(*,user,preparation_id,payload):
    qualification(user)
    common={'action','sourceComparisonFactId','sourceComparisonVersion','sourceFingerprint',
        'expectedDecisionVersion','expectedWorkflowVersion','reason','idempotencyKey'}
    if not isinstance(payload,dict) or payload.get('action') not in ACTIONS:
        fail('PREPARATION_REVIEW_INPUT_INVALID','须提交正式审核动作，不接受直接指定状态。',400)
    action=payload['action'];expected=common|({'reviewResult','opinion','selectedSupplierCode'} if action=='SUBMIT_REVIEW' else set())
    if set(payload)!=expected:fail('PREPARATION_REVIEW_INPUT_INVALID','审核输入字段与本动作合同不符。',400)
    reason=text(payload['reason'],'办理理由',240);key=text(payload['idempotencyKey'],'同次动作键',120)
    p,snapshot,registrant,inquiry,item,context=_load(user,preparation_id,lock=True)
    definition,authorization=_authority(user,snapshot,registrant,context)
    history,wf,task=_history(p)
    body={**payload,'actorId':user.pk,'preparationId':p.pk}
    prior=MasterDataWriteRequest.objects.filter(organization_id=user.company_id,action_code=PERMISSION,idempotency_key=key).first()
    if prior:
        if prior.audit_metadata.get('actorId')!=user.pk or prior.audit_metadata.get('preparationId')!=p.pk:
            fail('PREPARATION_REVIEW_RESULT_NOT_FOUND','同次动作不属于当前办理人及对象。',404)
        if prior.request_hash!=_canonical_hash(body):fail('PREPARATION_REVIEW_REQUEST_CHANGED','同次动作内容已变化。')
        if prior.status!='COMMITTED':fail('PREPARATION_REVIEW_RESULT_UNKNOWN','原结果尚未核实，请先查询。')
        return {**_receipt(prior),'idempotentReplay':True}
    if (payload['sourceComparisonFactId']!=str(p.source_comparison_id)
            or type(payload['sourceComparisonVersion']) is not int or payload['sourceComparisonVersion']!=p.source_comparison.fact_version
            or payload['sourceFingerprint']!=p.source_comparison.comparison_result['sourceFingerprint']):
        fail('PREPARATION_REVIEW_SOURCE_CHANGED','准确来源或比较版本已变化，请按正式新版办理。')
    _fresh(p,inquiry,item,context,lock=True)
    if (type(payload['expectedDecisionVersion']) is not int or payload['expectedDecisionVersion']!=p.decision_version
            or type(payload['expectedWorkflowVersion']) is not int or payload['expectedWorkflowVersion']!=(wf.version if wf else 0)):
        fail('PREPARATION_REVIEW_VERSION_CONFLICT','当前决定或工作流版本已变化，请先查询原结果。')
    legal=(action=='START_REVIEW' and p.status=='draft' and wf is None or
        action=='SUBMIT_REVIEW' and p.status=='reviewing' and wf and wf.status=='pending' or
        action=='REOPEN_REVIEW' and p.status=='completed' and current_result(p)=='adjust')
    if not legal:fail('PREPARATION_REVIEW_ACTION_BLOCKED','当前准确版本不允许本次审核动作。')
    request,created,_=_write_request(user=user,action_code=PERMISSION,entity_type=ENTITY,key=key,request_body=body)
    if not created:fail('PREPARATION_REVIEW_RESULT_UNKNOWN','并发结果待核，请只查询同次动作。')
    before=_state(p)
    if action=='START_REVIEW':
        wf=create_business_object_with_initial_state(model=WorkflowInstance,initial_state='pending',
            instance_no='PAPR-'+uuid.uuid4().hex,process_definition=definition,
            document_type='PriceApprovalPreparation',document_id=p.pk,current_step=1,total_steps=1,version=1)
        task=create_business_object_with_initial_state(model=ApprovalTask,initial_state='pending',
            task_no='PAPRT-'+uuid.uuid4().hex,workflow_instance=wf,step_no=1,
            required_role_code='purchase_manager',minimum_approvals=1,allow_parallel=False,version=1)
        _initial(user,wf,'WorkflowInstance',reason,authorization,wf);_initial(user,task,'ApprovalTask',reason,authorization,wf)
    decision_value=None;decision=None
    if action=='SUBMIT_REVIEW':
        result=payload['reviewResult'];opinion=text(payload['opinion'],'核价意见',240)
        if result not in RESULT_LABELS:fail('PREPARATION_REVIEW_RESULT_INVALID','须明确三类审核结论之一。',400)
        code=payload['selectedSupplierCode']
        if not isinstance(code,str):fail('PREPARATION_REVIEW_INPUT_INVALID','核价候选编码必须为文本。',400)
        selected=next((x for x in p.supplier_candidates if (x.get('supplierCode') or x.get('supplierId'))==code),None) if code else None
        if (result=='pass' and not selected) or (code and not selected):
            fail('PREPARATION_REVIEW_CANDIDATE_REQUIRED','通过时须人工明确原候选中的核价意见对象，不自动选供。')
        p.review_result=result;p.review_opinion=opinion;p.approval_opinion=opinion
        p.selected_supplier=copy.deepcopy(selected or {});p.reviewer=user.get_username();p.reviewed_at=timezone.now();p.decision_version+=1
        p.save(update_fields=['review_result','review_opinion','approval_opinion','selected_supplier','reviewer','reviewed_at','decision_version','updated_at'])
        decision_value={'contractVersion':CONTRACT,'preparationId':p.pk,'comparisonFactId':str(p.source_comparison_id),
            'comparisonVersion':p.source_comparison.fact_version,'sourceFingerprint':payload['sourceFingerprint'],
            'decisionVersion':p.decision_version,'actorId':user.pk,'result':result,'reason':reason,'opinion':opinion,
            'selectedSupplier':copy.deepcopy(p.selected_supplier),'reviewedAt':p.reviewed_at.isoformat()}
        decision=ApprovalDecision.objects.create(task=task,decision_sequence=p.decision_version,actor=user,
            decision=result,comment=opinion,action_id=uuid.uuid4().hex,idempotency_key=key,
            decision_hash=_canonical_hash(decision_value))
        target='approved' if result=='pass' else 'rejected'
        for obj,name in [(task,'ApprovalTask'),(wf,'WorkflowInstance')]:
            obj.completed_at=timezone.now();obj.save(update_fields=['completed_at'])
            _transition(user,obj,name,target,reason,authorization,wf)
    elif action=='REOPEN_REVIEW':
        for obj,name in [(task,'ApprovalTask'),(wf,'WorkflowInstance')]:
            _transition(user,obj,name,'pending',reason,authorization,wf)
            obj.completed_at=None;obj.save(update_fields=['completed_at'])
        p.review_result='';p.review_opinion='';p.approval_opinion='';p.selected_supplier={};p.reviewer='';p.reviewed_at=None
        p.save(update_fields=['review_result','review_opinion','approval_opinion','selected_supplier','reviewer','reviewed_at','updated_at'])
    target='completed' if action=='SUBMIT_REVIEW' else 'reviewing'
    event=_audit(user,p,'PriceApprovalPreparation',before,{'status':target},reason,authorization)
    _transition(user,p,'PriceApprovalPreparation',target,reason,authorization,wf,version_field=None,
        reference=f'OrganizationOperatingAuditRecord:{event.pk}')
    proof={'contractVersion':CONTRACT,'action':action,'actorId':user.pk,'preparationId':p.pk,
        'comparisonFactId':str(p.source_comparison_id),'comparisonVersion':p.source_comparison.fact_version,
        'sourceFingerprint':payload['sourceFingerprint'],'beforeStatus':before['status'],'state':_state(p),
        'writeRequestId':request.pk,'workflowInstanceId':wf.pk,'approvalTaskId':task.pk,
        'workflowVersion':wf.version,'approvalTaskVersion':task.version,'workflowStatus':wf.status,
        'approvalTaskStatus':task.status,'approvalDecisionId':decision.pk if decision else None,'decision':decision_value}
    proof['proofHash']=_canonical_hash(proof)
    event.after_snapshot={**event.after_snapshot,'review':proof};event.save(update_fields=['after_snapshot'])
    result={'preparationId':p.pk,'approvalPrepareNo':p.approval_prepare_no,'targetId':str(p.pk),
        'sourceComparisonFactId':str(p.source_comparison_id),'sourceComparisonVersion':p.source_comparison.fact_version,
        'action':action,'statusCode':p.status,'statusLabel':p.get_status_display(),
        'reviewResult':p.review_result or None,'reviewResultLabel':RESULT_LABELS.get(p.review_result),
        'decisionVersion':p.decision_version,'workflowVersion':wf.version,'auditId':event.pk,
        'priceConfirmed':False,'priceApproved':False,'purchaseOrderApproved':False,'idempotentReplay':False}
    _commit_request(request,result);_history(p)
    return {**_receipt(request),'businessWriteCount':1}
