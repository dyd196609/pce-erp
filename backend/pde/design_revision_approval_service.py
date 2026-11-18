"""Exact design approval and approved successor services; no caller content replacement."""
from hashlib import sha256
import json
from django.db import transaction
from django.utils import timezone
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import ProcessDefinition, WorkflowInstance, ApprovalTask, ApprovalDecision
from workflow_runtime.state_transitions import create_business_object_with_initial_state, transition_business_object
from .models import DesignRevisionApproval, ProductDesignRevision
from .product_design_service import ProductDesignError, _write_request, _commit_request
from .product_version_management_service import _content_snapshot

PROCESS = 'PDE_DESIGN_REVISION_APPROVAL'
DOCUMENT = 'ProductDesignRevisionApproval'
PREFIX = 'production.engineering.design_approval.'

def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def process_fingerprint(process):
    from workflow_runtime.models import SegregationOfDutiesAuthority
    sod=SegregationOfDutiesAuthority.objects.filter(document_type=DOCUMENT).values('applicant_cannot_approve','same_user_restriction','required_role_separation','version','business_hash').first()
    if not sod or not all(sod[x] for x in ('applicant_cannot_approve','same_user_restriction','required_role_separation')):
        raise ProductDesignError('DESIGN_APPROVAL_SOD_CONTRACT_INVALID','设计资料批准职责分离契约缺失或失效。',409)
    nodes=list(process.nodes.order_by('sequence').values('node_code','sequence','business_action_code','active'))
    if len(nodes)!=1 or not nodes[0]['active'] or nodes[0]['business_action_code']!=PREFIX+'approve':
        raise ProductDesignError('DESIGN_APPROVAL_NODE_CONTRACT_INVALID','批准节点契约不完整。',409)
    return digest({'definitionHash':process.definition_hash,'version':process.version,'nodes':nodes,'sod':sod})

def authorize(user, action, company):
    decision = AuthorizationService.decide(user=user, action_code=PREFIX+action, organization_id=company, business_object={'organizationId':company})
    if not decision['allowed'] or (action in ('approve','revoke') and 'design_revision_approver' not in decision['roleCodes']):
        raise ProductDesignError('DESIGN_APPROVAL_PERMISSION_DENIED', decision['reason'], 403)
    return decision

def audit(user, action, target, reason, after):
    return OrganizationOperatingAuditRecord.objects.create(actor=user, organization_id=user.company_id, action_code=PREFIX+action, target_type=DOCUMENT, target_id=target, target_label=str(target), reason=reason, after_snapshot=after)

def change(obj, target, user, event, action, reason, object_type=DOCUMENT):
    event = OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=PREFIX+action,target_type=object_type,target_id=obj.pk,target_label=str(obj.pk),reason=reason,after_snapshot={'parentAuditId':event.pk,'targetState':target})
    transition_business_object(business_object=obj, object_type=object_type, source_state=obj.status, target_state=target, action_code=PREFIX+action, operator=user, reason=reason, audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}', allowed_transitions=((obj.status,target),), updated_at_field='updated_at' if object_type==DOCUMENT else None)
    if hasattr(obj, 'completed_at'):
        obj.completed_at=timezone.now();obj.save(update_fields=['completed_at'])

def current_exact(approval, require_current=True):
    item = approval.source_revision.design_item
    source = item.source_record
    if approval.company_id != item.company_id or approval.sales_order_item_id != item.sales_order_item_id or approval.engineering_instance.sales_order_item_id != item.sales_order_item_id or approval.source_record_id != source.pk:
        raise ProductDesignError('DESIGN_APPROVAL_SCOPE_MISMATCH','批准对象与公司、订单行、实例或来源不一致。',409)
    if source.source_version != approval.source_version or source.content_hash != approval.source_hash or source.status != 'confirmed':
        raise ProductDesignError('DESIGN_APPROVAL_SOURCE_CHANGED','批准来源版本或内容已变化。',409)
    # Snapshot hashes include the revision and item identity at submission. The item
    # version advances when a successor is created; immutable content fields do not.
    frozen = approval.content_snapshot
    actual = _content_snapshot(item,approval.source_revision)
    actual['designItem']['version']=frozen['designItem']['version']
    if digest(frozen) != approval.content_hash or digest(actual) != approval.content_hash:
        raise ProductDesignError('DESIGN_APPROVAL_CONTENT_CHANGED','获准内容或精确修订快照不一致。',409)
    if require_current and item.design_revisions.order_by('-revision').first().pk != approval.source_revision_id:
        raise ProductDesignError('DESIGN_APPROVAL_REVISION_STALE','送审后已有新修订，请重新送审。',409)
    from .product_design_instance_service import resolve
    context={'companyId':item.company_id,'orderEngineeringInstanceId':approval.engineering_instance_id,'salesOrderId':item.sales_order_item.sales_order_id,'salesOrderItemId':item.sales_order_item_id,'sourceRecordId':source.pk,'sourceVersion':source.source_version,'authorizationId':approval.engineering_instance.engineering_preparation_authorization_id}
    resolve(approval.applicant,context)
    if not approval.process_definition.active or approval.process_version != approval.process_definition.version or approval.process_hash != process_fingerprint(approval.process_definition):
        raise ProductDesignError('DESIGN_APPROVAL_PROCESS_STALE','批准流程版本已失效。',409)
    return item

def effective(approval):
    current_exact(approval,require_current=False)
    if approval.approval_scope=='PRODUCTION_USE':
        from .production_design_admission import assess
        expected=assess(user=approval.applicant,instance=approval.engineering_instance,
            line=approval.sales_order_item,source=approval.source_record,revision=approval.source_revision,existing_approval=approval)
        rows=list(OrganizationOperatingAuditRecord.objects.filter(action_code=PREFIX+'submit',target_type=DOCUMENT,
            target_id=approval.pk,organization_id=approval.company_id,actor_id=approval.applicant_id))
        if len(rows)!=1 or rows[0].after_snapshot.get('productionAdmission')!=expected:
            raise ProductDesignError('PRODUCTION_DESIGN_ADMISSION_PROOF_INVALID','正式用途准入与原始来源或持久化审计不一致。',409)
    workflow=approval.workflow_instance
    decision=approval.final_decision
    if approval.status!='approved' or not workflow or workflow.status!='approved' or not decision or decision.decision!='approved' or decision.task.workflow_instance_id!=workflow.pk or decision.actor_id==approval.applicant_id or workflow.process_definition_id!=approval.process_definition_id or workflow.document_type!=DOCUMENT or workflow.document_id!=approval.pk:
        raise ProductDesignError('DESIGN_APPROVAL_NOT_EFFECTIVE','资料批准未通过、已撤销或批准依据不完整。',409)
    authorize(decision.actor,'approve',approval.company_id)
    return True

def submit(user, context, revision_id, content_hash, key):
    return _submit(user,context,revision_id,content_hash,key,purpose='TEST_BUSINESS')

def submit_production(user, context, revision_id, content_hash, key):
    return _submit(user,context,revision_id,content_hash,key,purpose='PRODUCTION_USE')

@transaction.atomic
def _submit(user, context, revision_id, content_hash, key, *, purpose):
    from .product_design_instance_service import resolve
    instance,line,source=resolve(user,context,lock=True)
    authorize(user,'submit',user.company_id)
    revision=ProductDesignRevision.objects.select_for_update().select_related('design_item').filter(pk=revision_id,design_item__sales_order_item=line,design_item__company_id=user.company_id).first()
    if not revision:
        raise ProductDesignError('DESIGN_REVISION_NOT_FOUND','指定修订不属于当前实例。',404)
    body={'revisionId':revision.pk,'hash':content_hash,'context':context}
    if purpose=='PRODUCTION_USE':body['intendedPurpose']=purpose
    request,created,_=_write_request(user=user,action_code=PREFIX+'submit',entity_type=DOCUMENT,key=key,request_body=body)
    if not created and request.result.get('approvalId'):
        return DesignRevisionApproval.objects.get(pk=request.result['approvalId']),True
    snapshot=_content_snapshot(revision.design_item,revision)
    if digest(snapshot)!=content_hash:
        raise ProductDesignError('DESIGN_APPROVAL_HASH_MISMATCH','送审内容哈希已变化，请刷新。',409)
    process=ProcessDefinition.objects.filter(definition_code=PROCESS,document_type=DOCUMENT,active=True).first()
    if not process:
        raise ProductDesignError('DESIGN_APPROVAL_PROCESS_REQUIRED','资料批准流程尚未登记。',409)
    # Production eligibility requires a separate, implemented authority provider.
    # This general workflow accepts any exact revision, but cannot invent that authority.
    scope='TEST_BUSINESS';production_admission=None
    if purpose=='PRODUCTION_USE':
        from .production_design_admission import assess
        production_admission=assess(user=user,instance=instance,line=line,source=source,revision=revision)
        scope='PRODUCTION_USE'
    elif purpose!='TEST_BUSINESS':
        raise ProductDesignError('DESIGN_APPROVAL_PURPOSE_INVALID','未知批准用途。',409)
    # Scope is assigned by the server's registered approval contract. Production
    # promotion has no registered evidence provider and is not exposed here.
    if revision.design_item.design_revisions.order_by('-revision').first().pk!=revision.pk:
        raise ProductDesignError('DESIGN_APPROVAL_REVISION_STALE','只能提交当前精确修订。',409)
    obj=create_business_object_with_initial_state(model=DesignRevisionApproval,initial_state='pending',company_id=user.company_id,sales_order_item=line,engineering_instance=instance,source_revision=revision,source_record=source,source_version=source.source_version,source_hash=source.content_hash,content_snapshot=snapshot,content_hash=content_hash,origin_nature=revision.origin_nature or revision.design_nature,approval_scope=scope,applicant=user,process_definition=process,process_version=process.version,process_hash=process_fingerprint(process))
    workflow=create_business_object_with_initial_state(model=WorkflowInstance,initial_state='pending',instance_no=f'DESIGN-APP-{obj.pk}',process_definition=process,document_type=DOCUMENT,document_id=obj.pk,total_steps=1)
    create_business_object_with_initial_state(model=ApprovalTask,initial_state='pending',task_no=f'DESIGN-APP-TASK-{obj.pk}',workflow_instance=workflow,step_no=1,required_role_code='design_revision_approver',minimum_approvals=1)
    obj.workflow_instance=workflow;obj.save(update_fields=['workflow_instance'])
    event=audit(user,'submit',obj.pk,'提交精确设计修订批准',{'contentHash':content_hash,'scope':scope,'workflowId':workflow.pk,**({'productionAdmission':production_admission} if production_admission else {})})
    _commit_request(request,{'approvalId':obj.pk,'auditId':event.pk})
    return obj,False

@transaction.atomic
def decide(user, approval_id, decision, expected_hash, reason, key):
    obj=DesignRevisionApproval.objects.select_for_update().get(pk=approval_id,company_id=user.company_id)
    if user.pk==obj.applicant_id:
        raise ProductDesignError('DESIGN_APPROVAL_SELF_APPROVAL','提交人不得审批本人申请。',403)
    reviewer_authority=authorize(user,'approve',obj.company_id)
    if obj.approval_scope=='PRODUCTION_USE':
        applicant_authority=authorize(obj.applicant,'submit',obj.company_id)
        if set(reviewer_authority['roleCodes']) & set(applicant_authority['roleCodes']):
            raise ProductDesignError('PRODUCTION_DESIGN_ROLE_SEPARATION_REQUIRED','正式用途资料批准必须由不同办理角色独立完成。',403)
    if decision not in ('approved','rejected') or not reason.strip() or expected_hash!=obj.content_hash:
        raise ProductDesignError('DESIGN_APPROVAL_DECISION_INVALID','决定、意见或精确内容哈希不一致。',409)
    request,created,_=_write_request(user=user,action_code=PREFIX+'approve',entity_type=DOCUMENT,key=key,request_body={'approvalId':obj.pk,'hash':expected_hash,'decision':decision,'reason':reason})
    if not created and request.status=='COMMITTED':return obj,True
    if obj.status!='pending':raise ProductDesignError('DESIGN_APPROVAL_ALREADY_DECIDED','该申请已办理。',409)
    current_exact(obj)
    workflow=WorkflowInstance.objects.select_for_update().get(pk=obj.workflow_instance_id)
    task=ApprovalTask.objects.select_for_update().get(workflow_instance=workflow,step_no=1)
    final=ApprovalDecision.objects.create(task=task,actor=user,decision=decision,comment=reason,action_id=f'DESIGN-APP-{obj.pk}',idempotency_key=key,decision_hash=digest({'hash':expected_hash,'decision':decision,'actor':user.pk}))
    event=audit(user,'approve',obj.pk,reason,{'decisionId':final.pk,'decision':decision,'contentHash':expected_hash})
    change(task,decision,user,event,'approve',reason,'ApprovalTask');change(workflow,decision,user,event,'approve',reason,'WorkflowInstance')
    obj.final_decision=final;obj.save(update_fields=['final_decision']);change(obj,decision,user,event,'approve',reason)
    _commit_request(request,{'approvalId':obj.pk,'auditId':event.pk})
    return obj,False

@transaction.atomic
def create_successor(user,approval_id,key):
    obj=DesignRevisionApproval.objects.select_for_update().get(pk=approval_id,company_id=user.company_id)
    authorize(user,'submit',obj.company_id);effective(obj)
    request,created,_=_write_request(user=user,action_code=PREFIX+'successor',entity_type=DOCUMENT,key=key,request_body={'approvalId':obj.pk,'hash':obj.content_hash})
    existing=ProductDesignRevision.objects.filter(approval=obj).first()
    if existing:return existing,True
    item=current_exact(obj)
    from .models import ProductDesignItem
    item=ProductDesignItem.objects.select_for_update().get(pk=item.pk)
    if item.design_revisions.order_by("-revision").first().pk!=obj.source_revision_id:
        raise ProductDesignError("DESIGN_APPROVAL_REVISION_STALE","批准后已有其它修订，不能替换当前修订。",409)
    original=obj.source_revision
    fields={f.attname:getattr(original,f.attname) for f in ProductDesignRevision._meta.concrete_fields if f.name not in ('id','revision','created_at','created_by','approval','predecessor_revision','origin_nature','approval_scope','legacy_source_record','source_provenance','design_nature','change_reason')}
    successor=ProductDesignRevision.objects.create(**fields,revision=original.revision+1,created_by=user,approval=obj,predecessor_revision=original,origin_nature=obj.origin_nature,approval_scope=obj.approval_scope,design_nature='FORMAL',change_reason='依据精确资料批准生成获准后继；来源性质保留',source_provenance={**original.source_provenance,'approvalId':obj.pk,'sourceRevisionId':original.pk,'originNature':obj.origin_nature,'approvalScope':obj.approval_scope,'approvedContentHash':obj.content_hash})
    item.version+=1;item.save(update_fields=['version','updated_at'])
    event=audit(user,'successor',obj.pk,'从获准冻结内容生成后继修订',{'successorId':successor.pk,'sourceRevisionId':original.pk,'contentHash':obj.content_hash})
    _commit_request(request,{'approvalId':obj.pk,'auditId':event.pk,'successorId':successor.pk})
    return successor,False

@transaction.atomic
def revoke(user,approval_id,reason,key):
    obj=DesignRevisionApproval.objects.select_for_update().get(pk=approval_id,company_id=user.company_id)
    authorize(user,'revoke',obj.company_id)
    request,created,_=_write_request(user=user,action_code=PREFIX+'revoke',entity_type=DOCUMENT,key=key,request_body={'approvalId':obj.pk,'reason':reason})
    if not created and request.status=='COMMITTED':return obj,True
    if obj.status!='approved' or not reason.strip():raise ProductDesignError('DESIGN_APPROVAL_REVOKE_INVALID','仅有效批准可凭依据撤销。',409)
    event=audit(user,'revoke',obj.pk,reason,{'decisionId':obj.final_decision_id});change(obj,'revoked',user,event,'revoke',reason);_commit_request(request,{'approvalId':obj.pk,'auditId':event.pk});return obj,False
