from procurement.quantity_contract import exact_total
from planning.material_purchase_service import material_allowed, purchasing_unit
"""Explicit native price confirmation; existing result/price and STANDARD order service."""
import copy
from datetime import date
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from masterdata.models import MasterDataWriteRequest, PriceApprovalResult, SupplierMaterialPrice
from pde.product_design_service import _canonical_hash, _write_request, _commit_request
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, PositionWorkflowResponsibility, PositionResponsibility, User
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import record_projected_business_transition
from . import preparation_review_service as review
from .comparison_registration_service import fail, text, identifier, verify_registered_fact
from .fact_read_access import permission_role_evidence, object_read_context
from .models import PriceApprovalPreparation, PurchaseInquiry, PurchaseRequestItem, PurchaseOrderItem, Supplier
from .scm_runtime_services import _business_date

CONTRACT='PCE-NATIVE-FORMAL-PRICE-CONFIRMATION-V1'
PERMISSION='procurement.price_confirmation.confirm'
PERMISSION_NAME='正式价格确认及登记'
PROCESS='SCM_FORMAL_PRICE_CONFIRMATION'
NODE='CONFIRM_PRICE'
DUTY='SCM_FORMAL_PRICE_CONFIRMATION'
ENTITY='FormalPriceConfirmationAction'
ACTION_CONTRACT={'contractVersion':CONTRACT,'actionCode':'CONFIRM_PRICE','moduleCode':'SCM_PRICE_APPROVAL',
 'displayName':PERMISSION_NAME,'requiredPermission':PERMISSION,'role':'purchase_manager',
 'organizationScope':'EXISTING_ROLE_SCOPE','serverValidator':'procurement.formal_price_confirmation_service.execute_confirmation',
 'separateApprovalLayer':False,'automaticOrderCreation':False}
ORDER_SOURCE_ACTION_CONTRACT={'contractVersion':CONTRACT,'actionCode':'PREVIEW_STANDARD_ORDER_FROM_CONFIRMED_PRICE',
 'moduleCode':'SCM_PURCHASE_ORDER','displayName':'按正式价格核对标准订单准入','requiredPermission':'procurement.purchase_order.create',
 'role':'EXISTING_ORIGINAL_CREATE_ROLES','organizationScope':'EXISTING_ORIGINAL_CREATE_SCOPE',
 'serverValidator':'procurement.formal_price_confirmation_service.standard_order_context','businessWriteCount':0}
TERM_KEYS={'taxRate','taxIncluded','effectiveDate','expiryDate','freightIncluded','deliveryDate'}

def decimal(value):
 try:
  if isinstance(value,bool):raise ValueError()
  result=Decimal(str(value))
  if not result.is_finite():raise ValueError()
  return result
 except (InvalidOperation,ValueError,TypeError):fail('FORMAL_PRICE_NUMBER_INVALID','价格条件的数值无效。',400)

def normalize_terms(value):
 """Optional source-owned quote facts, entered before original receipt locks the quote."""
 if not isinstance(value,dict) or set(value)-TERM_KEYS:
  fail('QUOTATION_TERMS_INVALID','报价条件仅接受结构化税率、含税、有效期、含运费及交期事实。',400)
 result={k:value.get(k) for k in sorted(TERM_KEYS)}
 for k in ['taxIncluded','freightIncluded']:
  if result[k] is not None and type(result[k]) is not bool:fail('QUOTATION_TERMS_INVALID','含税及含运费条件须明确为是、否或未提供。',400)
 if result['taxRate'] is not None:
  n=decimal(result['taxRate'])
  if not 0<=n<=100 or n.as_tuple().exponent < -2:fail('QUOTATION_TERMS_INVALID','报价税率须在0至100之间且最多两位小数。',400)
  result['taxRate']=str(n)
 for k in ['effectiveDate','expiryDate','deliveryDate']:
  if result[k] is not None:
   try:
    d=date.fromisoformat(result[k]);assert d.isoformat()==result[k]
   except (TypeError,ValueError,AssertionError):fail('QUOTATION_TERMS_INVALID','报价日期须为准确的YYYY-MM-DD或未提供。',400)
 if result['effectiveDate'] and result['expiryDate'] and result['expiryDate']<result['effectiveDate']:
  fail('QUOTATION_TERMS_INVALID','报价失效日不得早于生效日。',400)
 return result

def qualification(user):
 review.validate_read_identity(user)
 if user.is_superuser or not any(x.role_code=='purchase_manager' and PERMISSION in
    AuthorizationService.permission_codes_for_user(user,{x.role_code}) for x in AuthorizationService.authority_evidence(user)):
  fail('FORMAL_PRICE_DENIED','当前岗位没有正式价格确认及登记执行资格。',403)

def _authority(user,snapshot,registrant,context):
 qualification(user)
 # Existing formal employee, source separation and original manager scope, not client identity.
 review._authority(user,snapshot,registrant,context)
 facts={**context,'ownerUserId':context.get('ownerUserId') or '__NOT_PROVIDED__',
        'departmentId':context.get('departmentId') or '__NOT_PROVIDED__'}
 if not any(x.role_code=='purchase_manager' and AuthorizationService._scope_matches(x,user,facts,{})
    for x in permission_role_evidence(user,PERMISSION,context['organizationId'])):
  fail('FORMAL_PRICE_SCOPE_DENIED','超出本采购经理原有效价格确认范围。',403)
 today=_business_date();position=user.employee_profile.position_ref
 mappings=PositionWorkflowResponsibility.objects.select_related('responsibility','workflow_node__process_definition').filter(
  position=position,active=True,ownership_type='OWNER',responsibility__code=DUTY,responsibility__status='ACTIVE',
  responsibility__is_active=True,workflow_node__node_code=NODE,workflow_node__active=True,
  workflow_node__business_action_code=PERMISSION,workflow_node__process_definition__definition_code=PROCESS,
  workflow_node__process_definition__document_type='PriceApprovalResult',workflow_node__process_definition__active=True)
 for m in mappings:
  d=m.workflow_node.process_definition
  periods=[(m.effective_from,m.effective_to),(m.responsibility.effective_from,m.responsibility.effective_to)]
  if (m.workflow_code==PROCESS and m.node_code==NODE and d.version==1 and m.workflow_node.sequence==1
    and d.nodes.filter(active=True).count()==1 and all((not a or a<=today) and (not b or b>=today) for a,b in periods)
    and PositionResponsibility.objects.filter(position=position,responsibility=m.responsibility,active=True).exists()):
   decision=AuthorizationService.decide(user=user,action_code=PERMISSION,organization_id=context['organizationId'],business_object=context)
   if decision.get('allowed'):return decision
 fail('FORMAL_PRICE_DUTY_REQUIRED','缺少原岗位有效价格确认职责或正式流程节点。',403)

def _source(p,*,lock=False):
 snapshot,event,_=verify_registered_fact(p.source_comparison)
 # Reuse the original preparation's exact frozen-projection contract even for order consumers.
 from .price_approval_preparation_service import _candidate_from_evidence
 fact=p.source_comparison
 if (p.comparison_basis!=fact.comparison_result or p.source_quotation_evidence!=fact.supplier_quote_evidence
     or p.supplier_candidates!=[_candidate_from_evidence(x) for x in fact.supplier_quote_evidence]
     or p.material_lines!=[{'materialCode':fact.material_code,'materialName':fact.material_name,'quantity':str(fact.quantity)}]):
  fail('FORMAL_PRICE_SOURCE_PENDING','准备资料与其准确冻结比较版本不一致，不能作为价格或订单依据。')
 history,wf,task=review._history(p)
 if p.status!='completed' or not history or history[-1]['result']!='pass':
  fail('FORMAL_PRICE_REVIEW_PASS_REQUIRED','须为当前准确准备版本的正式审核通过结论。')
 inquiry=PurchaseInquiry.objects.select_related('source_purchase_request').get(pk=snapshot['inquiry']['id'])
 item=PurchaseRequestItem.objects.select_related('material','purchase_request').get(pk=snapshot['requestItem']['id'],purchase_request_id=snapshot['request']['id'])
 scope=object_read_context(inquiry.source_purchase_request)
 if not scope:fail('FORMAL_PRICE_SOURCE_PENDING','来源责任和企业尚待核定。')
 review._fresh(p,inquiry,item,scope,lock=lock)
 selected=p.selected_supplier.get('supplierCode') if isinstance(p.selected_supplier,dict) else None
 quotes=[x for x in snapshot['quotations'] if x['supplierCode']==selected]
 if len(quotes)!=1:fail('FORMAL_PRICE_SUPPLIER_UNPROVEN','审核候选未唯一对应准确已接收原生报价。')
 quote=quotes[0];raw=quote['lineSnapshot'].get('commercialTerms')
 if not Supplier.objects.filter(pk=quote['supplierMasterId'],company_id=scope['organizationId'],is_active=True).exists() or not material_allowed(item.material,request_item=item):
  fail('FORMAL_PRICE_MASTER_INACTIVE','供应商或物料原生主数据当前未启用或不适用采购。')
 if raw is None:fail('FORMAL_PRICE_CONDITIONS_MISSING','原生报价未提供结构化价格适用条件，不采用默认税率或日期。')
 terms=normalize_terms(raw)
 if any(v is None for v in terms.values()):fail('FORMAL_PRICE_CONDITIONS_MISSING','税率、含税、有效期、运费或交期存在未提供条件，不能确认适用价格。')
 if terms['freightIncluded'] is not True:
  fail('FORMAL_PRICE_FREIGHT_NOT_APPLICABLE','本报价运费未包含；原订单尚无独立运费承接依据，不能默认运费为零。')
 if (quote['unit']!=item.unit or purchasing_unit(item)!=item.unit or decimal(quote['quantity'])!=item.quantity):
  fail('FORMAL_PRICE_UNIT_QUANTITY_UNPROVEN','原生报价计价单位或适用数量与申请不符；不作无依据换算。')
 commercial={'supplierId':quote['supplierMasterId'],'supplierCode':quote['supplierCode'],'materialId':item.material_id,
  'materialCode':item.material_code,'unit':quote['unit'],'quantity':quote['quantity'],'unitPrice':quote['unitPrice'],
  'currency':quote['currency'],'terms':terms}
 return snapshot,event,history,wf,task,inquiry,item,scope,quote,commercial

def _receipt(row):
 return {**row.result,'resultState':'COMMITTED','receiptAsOf':row.updated_at.isoformat(),
  'stateMeaning':'ORIGINAL_ACTION_RESULT_NOT_CURRENT_ELIGIBILITY','executionAuthorizedByResult':False,
  'automaticReplayAllowed':False,'businessWriteCount':0}

@transaction.atomic
def confirmation_context(*,user,preparation_id):
 qualification(user);p,snapshot,event,_,_,scope=review._load(user,preparation_id)
 _authority(user,snapshot,event,scope)
 snapshot,event,history,wf,task,inq,item,scope,quote,commercial=_source(p)
 result=PriceApprovalResult.objects.filter(preparation=p).first()
 if result:verify_price(result,result.effective_price)
 return {'contractVersion':CONTRACT,'preparationId':p.pk,'approvalPrepareNo':p.approval_prepare_no,
  'sourceComparisonFactId':str(p.source_comparison_id),'sourceComparisonVersion':p.source_comparison.fact_version,
  'sourceFingerprint':p.source_comparison.comparison_result['sourceFingerprint'],'decisionVersion':p.decision_version,
  'workflowVersion':wf.version,'reviewDecisionId':task.decisions.order_by('-decision_sequence').first().pk,
  'selectedQuotationId':quote['quotationId'],'commercial':commercial,'conditionsFingerprint':_canonical_hash(commercial),
  'statusLabel':'已正式确认价格' if result else '审核通过，尚未正式确认价格',
  'availableActions':[] if result else ['CONFIRM_PRICE'],'priceApprovalResultId':result.pk if result else None,
  'purchaseOrderCreated':False,'purchaseOrderApproved':False,'automaticReplayAllowed':False,'businessWriteCount':0}

@transaction.atomic
def action_result(*,user,preparation_id,key):
 qualification(user);p,snapshot,event,_,_,scope=review._load(user,preparation_id);_authority(user,snapshot,event,scope)
 row=MasterDataWriteRequest.objects.filter(organization_id=user.company_id,action_code=PERMISSION,entity_type=ENTITY,idempotency_key=text(key,'同次动作键',120)).first()
 if row and (row.audit_metadata.get('actorId')!=user.pk or row.audit_metadata.get('preparationId')!=p.pk):
  fail('FORMAL_PRICE_RESULT_NOT_FOUND','同次结果不属于本办理人及对象。',404)
 return _receipt(row) if row and row.status=='COMMITTED' else {'resultState':'UNKNOWN','result':None,'automaticReplayAllowed':False,'businessWriteCount':0}

@transaction.atomic
def execute_confirmation(*,user,preparation_id,payload):
 qualification(user)
 keys={'action','sourceComparisonFactId','sourceComparisonVersion','sourceFingerprint','expectedDecisionVersion',
  'expectedWorkflowVersion','selectedQuotationId','expectedConditionsFingerprint','selectionReason','reason','idempotencyKey'}
 if not isinstance(payload,dict) or set(payload)!=keys or payload['action']!='CONFIRM_PRICE':
  fail('FORMAL_PRICE_INPUT_INVALID','须提交正式价格确认意图及准确版本，不接受客户端身份、状态或覆盖价格。',400)
 key=text(payload['idempotencyKey'],'同次动作键',120);reason=text(payload['reason'],'办理理由',240)
 selection=text(payload['selectionReason'],'供应商及报价选择依据',2000)
 p,snapshot,event,_,_,scope=review._load(user,preparation_id,lock=True);authorization=_authority(user,snapshot,event,scope)
 body={**payload,'actorId':user.pk,'preparationId':p.pk}
 prior=MasterDataWriteRequest.objects.select_for_update().filter(organization_id=user.company_id,action_code=PERMISSION,entity_type=ENTITY,idempotency_key=key).first()
 if prior:
  if prior.audit_metadata.get('actorId')!=user.pk or prior.audit_metadata.get('preparationId')!=p.pk:fail('FORMAL_PRICE_RESULT_NOT_FOUND','同次结果不属于本办理人及对象。',404)
  if prior.request_hash!=_canonical_hash(body):fail('FORMAL_PRICE_REQUEST_CHANGED','同次动作内容已变化。')
  if prior.status!='COMMITTED':fail('FORMAL_PRICE_RESULT_UNKNOWN','结果尚未核实，请先查询同次动作。')
  verify_price(PriceApprovalResult.objects.get(pk=prior.result['priceApprovalResultId']),current=False)
  return {**_receipt(prior),'idempotentReplay':True}
 snapshot,event,history,wf,task,inq,item,scope,quote,commercial=_source(p,lock=True)
 expected={'sourceComparisonFactId':str(p.source_comparison_id),'sourceComparisonVersion':p.source_comparison.fact_version,
  'sourceFingerprint':p.source_comparison.comparison_result['sourceFingerprint'],'expectedDecisionVersion':p.decision_version,
  'expectedWorkflowVersion':wf.version,'selectedQuotationId':quote['quotationId'],'expectedConditionsFingerprint':_canonical_hash(commercial)}
 if any(payload[k]!=v or (type(v) is int and type(payload[k]) is not int) for k,v in expected.items()):
  fail('FORMAL_PRICE_VERSION_CONFLICT','来源、审核决定、报价或条件版本已变化，请先读取准确上下文。')
 if PriceApprovalResult.objects.select_for_update().filter(preparation_identity=str(p.pk)).exists():
  fail('FORMAL_PRICE_ALREADY_CONFIRMED','该准确准备已有价格决定，请查询原动作，不重复登记。')
 request,created,_=_write_request(user=user,action_code=PERMISSION,entity_type=ENTITY,key=key,request_body=body)
 if not created:fail('FORMAL_PRICE_RESULT_UNKNOWN','同次结果待核实。')
 now=timezone.now();decision=task.decisions.order_by('-decision_sequence').first()
 source={'requestId':item.purchase_request_id,'requestNo':item.purchase_request.request_no,'requestItemId':item.pk,
  'requestLineNo':item.line_no,'inquiryId':inq.pk,'inquiryNo':inq.inquiry_no,'quotationId':quote['quotationId'],
  'quotationNo':quote['quotationNo'],'quotationLineNo':quote['requestLineNo'],'companyId':scope['organizationId']}
 proof={'contractVersion':CONTRACT,'preparationId':p.pk,'preparationNo':p.approval_prepare_no,
  'comparisonFactId':str(p.source_comparison_id),'comparisonVersion':p.source_comparison.fact_version,
  'sourceFingerprint':expected['sourceFingerprint'],'decisionVersion':p.decision_version,'workflowVersion':wf.version,
  'reviewDecisionId':decision.pk,'reviewAuditId':history[-1]['auditId'],'reviewActorId':history[-1]['actorId'],
  'source':source,'commercial':commercial,'conditionsFingerprint':expected['expectedConditionsFingerprint'],
  'actorId':user.pk,'confirmedAt':now.isoformat(),'selectionReason':selection,'reason':reason,'writeRequestId':request.pk}
 from masterdata.master_data_statistics_runtime import SupplierMaterialPriceRuntime
 result,price=SupplierMaterialPriceRuntime._persist_native_price_confirmation(preparation=p,proof=proof,
  actor=user,confirmed_at=now,approved_at=p.reviewed_at)
 event=OrganizationOperatingAuditRecord.objects.create(action_code=PERMISSION,actor=user,organization_id=user.company_id,
  target_type='PriceApprovalResult',target_id=result.pk,target_label=result.result_no,reason=reason,
  before_snapshot={'exists':False},after_snapshot={'authorization':authorization})
 pe=OrganizationOperatingAuditRecord.objects.create(action_code=PERMISSION,actor=user,organization_id=user.company_id,
  target_type='SupplierMaterialPrice',target_id=price.pk,target_label=price.price_no,reason=reason,
  before_snapshot={'state':{'status':''}},after_snapshot={'state':{'status':'ACTIVE'},'authorization':authorization})
 record_projected_business_transition(object_type='SupplierMaterialPrice',object_id=price.pk,source_state='',target_state='ACTIVE',
  action_code=PERMISSION,operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{pe.pk}',allowed_transitions={('','ACTIVE')})
 proof.update(resultId=result.pk,resultNo=result.result_no,priceId=price.pk,priceNo=price.price_no,auditId=event.pk,priceAuditId=pe.pk)
 proof['proofHash']=_canonical_hash(proof);result.source_trace=proof;result.save(update_fields=['source_trace'])
 event.after_snapshot={**event.after_snapshot,'confirmation':proof};event.save(update_fields=['after_snapshot'])
 output={'preparationId':p.pk,'priceApprovalResultId':result.pk,'priceApprovalResultNo':result.result_no,
  'supplierMaterialPriceId':price.pk,'supplierMaterialPriceNo':price.price_no,'auditId':event.pk,'priceAuditId':pe.pk,
  'confirmedBy':user.pk,'confirmedAt':now.isoformat(),'statusLabel':'已正式确认并登记有效价格',
  'targetId':str(result.pk),'purchaseOrderCreated':False,'purchaseOrderApproved':False,'idempotentReplay':False}
 _commit_request(request,output);verify_price(result,price)
 return {**_receipt(request),'businessWriteCount':1}

def is_native_result(result):
 return (result.original_source_type==CONTRACT or isinstance(result.source_trace,dict) and result.source_trace.get('contractVersion')==CONTRACT
  or OrganizationOperatingAuditRecord.objects.filter(action_code=PERMISSION,target_type='PriceApprovalResult',target_id=result.pk).exists())

def verify_price(result,price=None,*,current=True):
 proof=result.source_trace
 if not isinstance(proof,dict) or proof.get('contractVersion')!=CONTRACT:fail('FORMAL_PRICE_PROOF_PENDING','正式价格来源证明待核。')
 price=price or result.effective_price
 audit=OrganizationOperatingAuditRecord.objects.filter(pk=proof.get('auditId'),action_code=PERMISSION,
  target_type='PriceApprovalResult',target_id=result.pk,actor_id=proof.get('actorId'),organization_id=proof.get('source',{}).get('companyId')).first()
 request=MasterDataWriteRequest.objects.filter(pk=proof.get('writeRequestId'),action_code=PERMISSION,entity_type=ENTITY,status='COMMITTED').first()
 price_event=OrganizationOperatingAuditRecord.objects.filter(pk=proof.get('priceAuditId'),action_code=PERMISSION,
  target_type='SupplierMaterialPrice',target_id=price.pk,actor_id=proof.get('actorId'),organization_id=proof.get('source',{}).get('companyId')).first()
 c=proof.get('commercial',{});terms=c.get('terms',{})
 if (not audit or audit.after_snapshot.get('confirmation')!=proof or not audit.after_snapshot.get('authorization',{}).get('allowed')
  or not request or request.result.get('priceApprovalResultId')!=result.pk or request.result.get('auditId')!=audit.pk
  or request.audit_metadata.get('actorId')!=proof.get('actorId') or request.audit_metadata.get('preparationId')!=result.preparation_id
  or request.audit_metadata.get('sourceComparisonFactId')!=proof.get('comparisonFactId')
  or request.audit_metadata.get('sourceComparisonVersion')!=proof.get('comparisonVersion')
  or request.audit_metadata.get('sourceFingerprint')!=proof.get('sourceFingerprint')
  or request.audit_metadata.get('expectedDecisionVersion')!=proof.get('decisionVersion')
  or request.audit_metadata.get('expectedWorkflowVersion')!=proof.get('workflowVersion')
  or request.audit_metadata.get('expectedConditionsFingerprint')!=proof.get('conditionsFingerprint')
  or request.audit_metadata.get('selectedQuotationId')!=proof.get('source',{}).get('quotationId')
  or not price_event or not price_event.after_snapshot.get('authorization',{}).get('allowed')
  or price_event.reason!=proof.get('reason') or price_event.after_snapshot.get('state',{}).get('status')!='ACTIVE'
  or request.request_hash!=_canonical_hash(request.audit_metadata)
  or proof.get('proofHash')!=_canonical_hash({k:v for k,v in proof.items() if k!='proofHash'})
  or proof.get('conditionsFingerprint')!=_canonical_hash(c)
  or (result.pk,result.result_no,price.pk,price.price_no)!=(proof.get('resultId'),proof.get('resultNo'),proof.get('priceId'),proof.get('priceNo'))
  or result.preparation_id!=proof.get('preparationId') or result.preparation_identity!=str(result.preparation_id)
  or result.original_source_type!=CONTRACT or result.approval_conclusion!='pass'
  or result.original_source_object_id!=proof.get('comparisonFactId') or result.original_source_reference!=proof.get('source',{}).get('quotationNo')
  or result.supplier_id!=c.get('supplierId') or result.material_id!=c.get('materialId')
  or price.price_approval_result_id!=result.pk or price.supplier_id!=result.supplier_id or price.material_id!=result.material_id
  or result.approved_price!=decimal(c.get('unitPrice')) or price.approved_price!=result.approved_price
  or result.currency!=c.get('currency') or price.currency!=result.currency
  or result.tax_rate!=decimal(terms.get('taxRate')) or price.tax_rate!=result.tax_rate
  or price.effective_date.isoformat()!=terms.get('effectiveDate') or (price.expiry_date.isoformat() if price.expiry_date else None)!=terms.get('expiryDate')
  or result.confirmed_by!=str(proof.get('actorId')) or result.confirmed_at.isoformat()!=proof.get('confirmedAt')
  or result.approved_by!=str(proof.get('reviewActorId'))
  or price.confirmed_by!=result.confirmed_by or price.confirmed_at!=result.confirmed_at):
  fail('FORMAL_PRICE_PROOF_INCONSISTENT','正式价格、准确版本、办理人或原审计证明不一致。')
 if not BusinessStateTransition.objects.filter(object_type='SupplierMaterialPrice',object_id=price.pk,
  action_code=PERMISSION,source_state='',target_state='ACTIVE',operator_id=proof['actorId'],
  audit_reference=f"OrganizationOperatingAuditRecord:{proof['priceAuditId']}").exists():
  fail('FORMAL_PRICE_PROOF_INCONSISTENT','有效价格缺少原生初始化审计依据。')
 p=result.preparation
 if not p or not review.is_native(p):fail('FORMAL_PRICE_SOURCE_PENDING','缺少原生准备来源。')
 snapshot,_,_=verify_registered_fact(p.source_comparison);history,wf,task=review._history(p)
 historical=next((x for x in history if x['auditId']==proof.get('reviewAuditId')),None)
 review_decision=task.decisions.filter(pk=proof.get('reviewDecisionId'),actor_id=proof.get('reviewActorId'),decision='pass',comment=result.review_opinion).first() if task else None
 if (not historical or historical['result']!='pass' or historical['actorId']!=proof.get('reviewActorId')
  or historical['decisionVersion']!=proof.get('decisionVersion') or not review_decision):
  fail('FORMAL_PRICE_PROOF_INCONSISTENT','价格确认未绑定准确的原审核通过决定。')
 if current:
  _,_,_,_,_,_,_,_,q,commercial=_source(p)
  if (commercial!=c or p.decision_version!=proof['decisionVersion'] or wf.version!=proof['workflowVersion']
   or task.decisions.order_by('-decision_sequence').first().pk!=proof['reviewDecisionId']
   or str(p.source_comparison_id)!=proof['comparisonFactId'] or p.source_comparison.fact_version!=proof['comparisonVersion']
   or p.source_comparison.comparison_result['sourceFingerprint']!=proof['sourceFingerprint']):
   fail('FORMAL_PRICE_VERSION_CONFLICT','当前准备、来源或审核决定已变化，旧价格证明不能用于新标准订单。')
 return proof

def _order_authority(user,source):
 review.validate_read_identity(user)
 item=PurchaseRequestItem.objects.select_related('purchase_request').get(pk=source['requestItemId'])
 scope=object_read_context(item.purchase_request)
 decision=AuthorizationService.decide(user=user,action_code='procurement.purchase_order.create',organization_id=source['companyId'],business_object=scope)
 if user.is_superuser or not scope or not decision.get('allowed'):
  fail('FORMAL_PRICE_ORDER_DENIED','当前业务身份没有原标准采购订单创建资格或范围。',403)
 return decision

@transaction.atomic
def standard_order_context(*,user,result_id):
 result=PriceApprovalResult.objects.select_related('preparation','effective_price').filter(pk=identifier(result_id)).first()
 if not result or not is_native_result(result):fail('FORMAL_PRICE_RESULT_NOT_FOUND','未找到本次新原生价格结果。',404)
 proof=verify_price(result,current=False);_order_authority(user,proof['source']);price=result.effective_price;c=proof['commercial'];src=proof['source']
 existing=list(PurchaseOrderItem.objects.filter(price_approval_result=result).select_related('po').order_by('pk'))
 if existing:
  return {'contractVersion':CONTRACT,'resultState':'COMMITTED','purchaseOrderIds':sorted({x.po_id for x in existing}),
   'creationRequest':None,'availableActions':[],'stateMeaning':'ORIGINAL_ACTION_RESULT_NOT_CURRENT_ELIGIBILITY',
   'executionAuthorizedByResult':False,'businessWriteCount':0,'automaticReplayAllowed':False}
 verify_price(result,price)
 # Reuse original gate request shape, anchored to the committed native confirmation, not a local decision.
 identity=f"PRICE-CONFIRMATION:{proof['writeRequestId']}"
 payload={'requestId':identity,'gateId':identity,'admissionResultId':proof['proofHash'],'status':'PENDING_CONFIRMATION',
  'purchaseRequestIds':[src['requestNo']],'inquiryIds':[src['inquiryNo']],
  'quoteComparisonIds':[result.preparation.source_comparison.comparison_no],
  'supplierGroups':[{'supplierId':result.supplier_id,'supplierCode':result.supplier.code,'supplierName':result.supplier.name,
   'materialLines':[{'sourceRequestNo':src['requestNo'],'materialCode':c['materialCode'],'quantity':c['quantity'],
    'unit':c['unit'],'priceApprovalResultId':result.pk,'supplierMaterialPriceNo':price.price_no,
    'unitPrice':str(price.approved_price),'taxRate':str(price.tax_rate),'currency':price.currency,
    'effectiveDate':price.effective_date.isoformat()}]}]}
 from .scm_runtime_services import PurchaseOrderCreationService
 preview,_=PurchaseOrderCreationService.create_from_gate_request(payload,user.pk,preview=True)
 return {'contractVersion':CONTRACT,'creationRequest':payload,'preview':preview,'priceConditions':c,
  'sourceVersion':{'comparisonFactId':proof['comparisonFactId'],'comparisonVersion':proof['comparisonVersion'],
   'decisionVersion':proof['decisionVersion'],'reviewDecisionId':proof['reviewDecisionId']},'businessWriteCount':0,'automaticReplayAllowed':False}

def validate_standard_line(*,result,price,item,quantity,unit,order_date,raw,payload,actor_id):
 proof=verify_price(result,price);src=proof['source'];c=proof['commercial'];user=User.objects.defer('password').get(pk=actor_id)
 _order_authority(user,src)
 if (src['requestItemId']!=item.pk or src['requestId']!=item.purchase_request_id
  or c['materialId']!=item.material_id or c['unit']!=unit or raw.get('unit')!=unit
  or decimal(raw.get('quantity'))!=quantity or not 0<quantity<=decimal(c['quantity'])
  or not date.fromisoformat(c['terms']['effectiveDate'])<=order_date<=date.fromisoformat(c['terms']['expiryDate'])
  or date.fromisoformat(c['terms']['deliveryDate'])<order_date
  or not item.required_date or c['terms']['deliveryDate']>item.required_date.isoformat()):
  fail('FORMAL_PRICE_ORDER_NOT_APPLICABLE','价格来源、数量、单位、有效期或交期不适用于本标准订单。')
 identity=f"PRICE-CONFIRMATION:{proof['writeRequestId']}"
 if (payload.get('requestId')!=identity or payload.get('gateId')!=identity or payload.get('admissionResultId')!=proof['proofHash']):
  fail('FORMAL_PRICE_ORDER_SOURCE_CHANGED','标准订单上下文未绑定本次真实价格确认来源。')
 consumed=exact_total(PurchaseOrderItem.objects.filter(source_purchase_request_item=item).exclude(po__status='cancelled'),'quantity')
 if consumed+quantity>decimal(c['quantity']):fail('FORMAL_PRICE_QUANTITY_ALREADY_USED','原订单已占用本来源适用数量，不能重复覆盖。')
 return proof

def creation_request_hash(payload):
 return _canonical_hash({k:v for k,v in payload.items() if k!='previewOnly'})

def validate_creation_replay(orders,payload,actor_id):
 for order in orders:
  lines=list(order.items.select_related('price_approval_result'))
  native=[x for x in lines if x.price_approval_result_id and is_native_result(x.price_approval_result)]
  if not native:continue
  for line in native:
   proof=verify_price(line.price_approval_result,current=False)
   _order_authority(User.objects.defer('password').get(pk=actor_id),proof['source'])
  if order.source_trace.get('nativePriceCreationRequestHash')!=creation_request_hash(payload):
   fail('FORMAL_PRICE_ORDER_REQUEST_CHANGED','同次标准订单创建内容与原已提交结果不一致。')

def record_standard_creation(order,payload,actor_id):
 from .business_action_control import record_action_audit
 native=[x for x in order.items.select_related('price_approval_result') if x.price_approval_result_id and is_native_result(x.price_approval_result)]
 if not native:return
 user=User.objects.defer('password').get(pk=actor_id)
 proof=verify_price(native[0].price_approval_result);authorization=_order_authority(user,proof['source'])
 event=record_action_audit(user=user,action_code='procurement.purchase_order.create',organization_id=order.company_id,
  target_type='PurchaseOrder',target_id=order.pk,target_no=order.po_no,before={'exists':False},
  after={'status':order.status,'sourcePriceConfirmation':proof['auditId'],'priceResultIds':[x.price_approval_result_id for x in native]},
  authorization=authorization,reason='依准确原生价格确认显式创建标准订单，不批准或下达')
 order.source_trace={**order.source_trace,'nativePriceCreationRequestHash':creation_request_hash(payload),'nativePriceCreationAuditId':event.pk}
 order.save(update_fields=['source_trace'])

def validate_order_prices(order):
 for line in order.items.select_related('price_approval_result','supplier_material_price'):
  if not line.price_approval_result_id or not is_native_result(line.price_approval_result):continue
  proof=verify_price(line.price_approval_result,line.supplier_material_price);c=proof['commercial'];src=proof['source']
  if (line.source_purchase_request_item_id!=src['requestItemId'] or line.material_id!=c['materialId']
   or order.supplier_id!=c['supplierId'] or line.unit_snapshot!=c['unit']
   or not 0<line.quantity<=decimal(c['quantity']) or line.unit_price_snapshot!=decimal(c['unitPrice'])
   or line.currency_snapshot!=c['currency'] or line.tax_rate_snapshot!=decimal(c['terms']['taxRate'])):
   fail('FORMAL_PRICE_ORDER_NOT_APPLICABLE','标准订单当前明细与原生价格确认来源不一致。')
