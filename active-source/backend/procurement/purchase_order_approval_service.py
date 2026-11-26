"""Original PO four actions, shared workflow decisions, exact source and actor proof."""
import copy
from datetime import date
from decimal import Decimal
from django.db import transaction, OperationalError, IntegrityError
from django.utils import timezone
from masterdata.models import MasterDataWriteRequest
from pde.product_design_service import _canonical_hash, _write_request, _commit_request
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import WorkflowInstance, ApprovalTask, ApprovalDecision, BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state, record_projected_business_transition, transition_business_object
from .models import PurchaseOrder
from .comparison_registration_service import fail, text, identifier
from .fact_read_access import permission_role_evidence
from .scm_runtime_services import PurchaseOrderExecutionService, _business_date

CONTRACT='PCE-NATIVE-PURCHASE-ORDER-FOUR-ACTIONS-V1'
DOCUMENT='procurement.PurchaseOrder'
ENTITY='PurchaseOrderApprovalAction'
PROCESS='PROCUREMENT_PURCHASE_REQUEST_TO_ORDER'
STEPS=[(a,*PurchaseOrderExecutionService.TRANSITIONS[a],label,ownership) for a,label,ownership in [
       ('procurement.purchase_order.submit','提交采购订单','OWNER'),
       ('procurement.purchase_order.approve','审核采购订单','APPROVER'),
       ('procurement.purchase_order.review','复核采购订单','REVIEWER'),
       ('procurement.purchase_order.release','下达采购订单','APPROVER')]]
ACTION_CONTRACTS=[{'contractVersion':CONTRACT,'actionCode':a,'moduleCode':'SCM_PURCHASE_ORDER','displayName':label,
 'requiredPermission':a,'role':'EXISTING_PERMISSION_BEARING_ROLE','organizationScope':'ORIGINAL_TYPED_SCOPE',
 'serverValidator':'procurement.purchase_order_approval_service.execute_action'} for a,_,_,label,_ in STEPS]

def _scope(order):
 return {'organizationId':order.company_id,'companyId':order.company_id,
         'departmentId':order.purchase_department_id or order.department_id,'ownerUserId':order.created_by}

def _load(user,order_id,*,lock=False):
 if not user or not user.is_authenticated or not user.is_active:fail('ORDER_IDENTITY_INVALID','当前登录身份无效。',403)
 rows=PurchaseOrder.objects.select_related('supplier')
 if lock:rows=rows.select_for_update()
 order=rows.filter(pk=identifier(order_id)).first()
 if order is None:fail('PURCHASE_ORDER_NOT_FOUND','采购订单不存在或不在授权范围。',404)
 decision=AuthorizationService.decide(user=user,action_code='procurement.purchase_order.view',organization_id=order.company_id,business_object=_scope(order))
 if not decision.get('allowed'):fail('PURCHASE_ORDER_NOT_FOUND','采购订单不存在或不在授权范围。',404)
 return order

def _authority(user,action,order):
 from .scm_runtime_services import _authorize_fulfillment
 from workflow_runtime.models import WorkflowNodeDefinition
 from system.models import PositionWorkflowResponsibility
 if user.is_superuser:fail('ORDER_BUSINESS_ACTOR_REQUIRED','维护身份不自动取得采购订单办理资格。',403)
 decision,_=_authorize_fulfillment(user=user,action_code=action,order=order)
 roles=[e.role_code for e in permission_role_evidence(user,action,order.company_id)
        if AuthorizationService._scope_matches(e,user,_scope(order),{})]
 if not roles:fail('ORDER_SCOPE_DENIED','该动作角色的原范围不覆盖本订单。',403)
 node=WorkflowNodeDefinition.objects.select_related('process_definition').filter(
  process_definition__definition_code=PROCESS,process_definition__active=True,business_action_code=action,active=True).first()
 index=[x[0] for x in STEPS].index(action)
 if not node or node.node_code!=['SUBMIT_PURCHASE_ORDER','APPROVE_PURCHASE_ORDER','REVIEW_PURCHASE_ORDER','RELEASE_PURCHASE_ORDER'][index] or node.sequence!=index+5:
  fail('ORDER_WORKFLOW_NODE_UNPROVEN','原采购订单节点身份或顺序待核。')
 today=_business_date()
 mappings=PositionWorkflowResponsibility.objects.select_related('responsibility').filter(
  position=user.employee_profile.position_ref,workflow_node=node,workflow_code=PROCESS,node_code=node.node_code,
  ownership_type=STEPS[index][4],active=True,responsibility__is_active=True,responsibility__status='ACTIVE')
 if not any(all((not a or a<=today) and (not b or b>=today) for a,b in [(m.effective_from,m.effective_to),(m.responsibility.effective_from,m.responsibility.effective_to)]) for m in mappings):
  fail('ORDER_DUTY_REQUIRED','缺少本动作生效的原岗位职责及节点关系。',403)
 return decision,sorted(roles)[0],node

def _origin(order):
 if not order.created_by:fail('ORDER_MAKER_UNPROVEN','历史订单缺少准确制单人证明，保持待核。')
 audit_id=(order.source_trace or {}).get('nativePriceCreationAuditId')
 events=OrganizationOperatingAuditRecord.objects.filter(action_code='procurement.purchase_order.create',target_type='PurchaseOrder',target_id=order.pk,organization_id=order.company_id,actor_id=order.created_by)
 if audit_id:events=events.filter(pk=audit_id)
 candidates=[e for e in events if e.target_label==order.po_no and e.after_snapshot.get('document',{}).get('id')==order.pk
             and e.after_snapshot.get('state',{}).get('status')=='draft' and e.after_snapshot.get('authorization',{}).get('allowed')]
 if len(candidates)!=1:fail('ORDER_CREATION_SOURCE_PENDING','订单原始创建、制单人及来源审计未获唯一证明，保持待核。')
 person=candidates[0].after_snapshot.get('employee',{})
 if not person.get('id') or not person.get('employeeNo') or candidates[0].after_snapshot.get('account',{}).get('userId')!=order.created_by:
  fail('ORDER_MAKER_UNPROVEN','原始创建审计缺少制单人员准确身份，保持待核。')
 return candidates[0]

def _snapshot(order,*,current=True):
 from .formal_price_confirmation_service import validate_order_prices,is_native_result,verify_price
 origin=_origin(order)
 if current:validate_order_prices(order)
 lines=[]
 for item in order.items.select_related('price_approval_result','supplier_material_price','material').order_by('pk'):
  native=item.price_approval_result_id and is_native_result(item.price_approval_result)
  proof=verify_price(item.price_approval_result,item.supplier_material_price,current=current) if native else None
  if proof and current:
   conditions=proof['commercial']['terms']
   if not date.fromisoformat(conditions['effectiveDate'])<=order.order_date<=date.fromisoformat(conditions['expiryDate']):fail('ORDER_PRICE_DATE_NOT_APPLICABLE','订单日期不在原价格适用期内。')
   if item.unit_price!=item.unit_price_snapshot or item.amount!=(item.quantity*item.unit_price_snapshot).quantize(Decimal('.01')):
    fail('ORDER_PRICE_FACT_MISMATCH','订单实际单价、金额与准确价格依据不一致。')
  lines.append({'id':item.pk,'materialId':item.material_id,'requestItemId':item.source_purchase_request_item_id,
   'resultId':item.price_approval_result_id,'priceId':item.supplier_material_price_id,'quantity':str(item.quantity),
   'unit':item.unit_snapshot,'unitPrice':str(item.unit_price),'priceSnapshot':str(item.unit_price_snapshot),
   'amount':str(item.amount),'currency':item.currency_snapshot,'taxRate':str(item.tax_rate_snapshot),
   'expectedDate':item.expected_date.isoformat() if item.expected_date else None,'nativePriceProofHash':proof['proofHash'] if proof else None})
 if not lines:fail('ORDER_LINES_UNPROVEN','订单缺少可核对的原明细。')
 if current and sum((Decimal(x['amount']) for x in lines),Decimal('0'))!=order.total_amount:fail('ORDER_AMOUNT_MISMATCH','订单总额与原明细不一致。')
 return {'orderId':order.pk,'orderNo':order.po_no,'companyId':order.company_id,'makerId':order.created_by,
  'makerEmployeeId':origin.after_snapshot['employee']['id'],'makerEmployeeNo':origin.after_snapshot['employee']['employeeNo'],
  'creationAuditId':origin.pk,'purchaseMode':order.purchase_mode,'supplierId':order.supplier_id,
  'orderDate':order.order_date.isoformat(),'expectedDate':order.expected_date.isoformat() if order.expected_date else None,
  'departmentId':order.department_id,'purchaseDepartmentId':order.purchase_department_id,
  'sourceTrace':copy.deepcopy(order.source_trace),'totalAmount':str(order.total_amount),'lines':lines}

def _workflow(order,lock=False):
 rows=WorkflowInstance.objects.select_related('process_definition')
 if lock:rows=rows.select_for_update()
 return rows.filter(document_type=DOCUMENT,document_id=order.pk).first()

def _history(order,*,lock=False):
 wf=_workflow(order,lock)
 events=list(OrganizationOperatingAuditRecord.objects.filter(target_type='PurchaseOrder',target_id=order.pk,
  organization_id=order.company_id,action_code__in=[x[0] for x in STEPS]).order_by('pk'))
 all_transitions=list(BusinessStateTransition.objects.filter(object_type=DOCUMENT,object_id=order.pk).order_by('version'))
 approval_codes={x[0] for x in STEPS}
 transitions=[x for x in all_transitions if x.action_code in approval_codes]
 fulfilment=[x for x in all_transitions if x.action_code not in approval_codes]
 if fulfilment:
  from .material_stock_authority import verify_order_transitions
  verify_order_transitions(order,fulfilment)
 if not events:
  if wf or transitions or order.status!='draft':fail('ORDER_APPROVAL_HISTORY_PENDING','历史订单缺少准确办理人与流程决定，保持待核。')
  return [],None
 if not wf or wf.process_definition.definition_code!=PROCESS or wf.total_steps!=4 or len(events)!=len(transitions) or len(events)>4:
  fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','订单共享流程、决定及转换不完整。')
 history=[]
 for index,(event,transition) in enumerate(zip(events,transitions)):
  action,source,target,_,_=STEPS[index];proof=event.after_snapshot.get('orderApproval',{})
  if not isinstance(proof,dict):fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','订单办理证明不是原结构化合同。')
  task=wf.tasks.filter(step_no=index+1).first();decision=task.decisions.first() if task else None
  request=MasterDataWriteRequest.objects.filter(pk=proof.get('writeRequestId'),entity_type=ENTITY,action_code=action,organization_id=order.company_id,status='COMMITTED').first()
  expected_hash=_canonical_hash({k:v for k,v in proof.items() if k!='proofHash'}) if isinstance(proof,dict) else None
  if (proof.get('contractVersion')!=CONTRACT or proof.get('orderId')!=order.pk or proof.get('actorId')!=event.actor_id
      or proof.get('action')!=action or proof.get('beforeStatus')!=source or proof.get('status')!=target
      or proof.get('decisionVersion')!=index+1 or proof.get('proofHash')!=expected_hash
      or not request or request.result.get('auditId')!=event.pk or request.request_hash!=_canonical_hash(request.audit_metadata)
      or request.audit_metadata.get('actorId')!=event.actor_id or request.audit_metadata.get('orderId')!=order.pk
      or request.audit_metadata.get('actorEmployeeId')!=proof.get('actorEmployeeId') or not proof.get('actorEmployeeId')
      or request.audit_metadata.get('sourceFingerprint')!=proof.get('sourceFingerprint')
      or not task or not decision or task.decisions.count()!=1 or task.status!='approved'
      or proof.get('workflowInstanceId')!=wf.pk or proof.get('approvalTaskId')!=task.pk
      or task.required_role_code not in event.after_snapshot.get('authorization',{}).get('roleCodes',[])
      or decision.pk!=proof.get('approvalDecisionId') or decision.actor_id!=event.actor_id
      or decision.action_id!=f'PO-APPROVAL:{action}' or decision.idempotency_key!=request.idempotency_key
      or decision.decision_hash!=_canonical_hash(proof.get('decision')) or decision.comment!=event.reason
      or transition.source_state!=source or transition.target_state!=target or transition.action_code!=action
      or transition.operator_id!=event.actor_id or transition.workflow_instance_id!=wf.pk
      or transition.audit_reference!=f'OrganizationOperatingAuditRecord:{event.pk}'
      or not event.after_snapshot.get('authorization',{}).get('allowed')):
   fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','订单审计、共享决定、同次动作或状态转换不一致。')
  if index and proof.get('sourceFingerprint')!=history[0]['sourceFingerprint']:fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','本单办理依据发生未核定变化。')
  if not index and _canonical_hash(proof.get('frozenSource'))!=proof.get('sourceFingerprint'):fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','原提交冻结依据摘要不一致。')
  maker_person=proof['frozenSource']['makerEmployeeId'] if not index else history[0]['frozenSource']['makerEmployeeId']
  if index>0 and (event.actor_id==order.created_by or proof['actorEmployeeId']==maker_person):fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','历史决定违反本单制单人员分离合同。')
  if index==3 and (event.actor_id==events[2].actor_id or proof['actorEmployeeId']==history[2]['actorEmployeeId']):fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','历史复核与下达人员不分离。')
  history.append({**proof,'auditId':event.pk,'occurredAt':event.created_at.isoformat(),'reason':event.reason})
 later_status=len(events)==4 and order.status in {'received','inspected','stored','closed'}
 if (order.status!=STEPS[len(events)-1][2] and not later_status) or wf.tasks.count()!=len(events) or wf.version!=len(events)+1 or wf.current_step!=min(len(events)+1,4) or wf.status!=('approved' if len(events)==4 else 'pending'):
  fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','订单当前状态与共享流程版本不一致。')
 # Every shared object keeps real initialization/transition audit references, too.
 for obj,name,expected in [(wf,'WorkflowInstance',len(events)+1)]+[(t,'ApprovalTask',2) for t in wf.tasks.all()]:
  chain=list(BusinessStateTransition.objects.filter(object_type=name,object_id=obj.pk).order_by('version'))
  if len(chain)!=expected or obj.version!=expected:fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','共享对象转换数量及版本不一致。')
  previous=''
  for tr in chain:
   ref=tr.audit_reference.removeprefix('OrganizationOperatingAuditRecord:')
   audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(ref)).first() if ref.isdigit() else None
   if not audit or audit.target_type!=name or audit.target_id!=obj.pk or audit.actor_id!=tr.operator_id or audit.after_snapshot.get('state',{}).get('status')!=tr.target_state or tr.source_state!=previous:
    fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','共享对象真实审计引用不一致。')
   previous=tr.target_state
  if previous!=obj.status:fail('ORDER_APPROVAL_HISTORY_INCONSISTENT','共享对象当前状态不一致。')
 return history,wf

def _separation(user,order,action,history):
 maker=_origin(order).after_snapshot['employee']['id'];person=user.employee_profile.pk
 if action!=STEPS[0][0] and (user.pk==order.created_by or person==maker):fail('ORDER_MAKER_SEPARATION','制单人不得审核、复核或最终下达本单。',403)
 if action==STEPS[3][0]:
  if len(history)<3:fail('ORDER_REVIEW_DECISION_PENDING','缺少本单准确复核决定。')
  if history[2]['actorId']==user.pk or history[2]['actorEmployeeId']==person:fail('ORDER_REVIEW_RELEASE_SEPARATION','复核人与最终下达人必须分离。',403)

def _receipt(row):
 return {**row.result,'resultState':'COMMITTED','receiptAsOf':row.updated_at.isoformat(),
  'stateMeaning':'ORIGINAL_ACTION_RESULT_NOT_CURRENT_ELIGIBILITY','executionAuthorizedByResult':False,'automaticReplayAllowed':False,'businessWriteCount':0}

@transaction.atomic
def action_context(*,user,order_id,action):
 order=_load(user,order_id);history,wf=_history(order);snapshot=_snapshot(order);fingerprint=_canonical_hash(snapshot)
 if history and fingerprint!=history[0]['sourceFingerprint']:fail('ORDER_FROZEN_SOURCE_CHANGED','订单已提交依据发生变化，须走原正式更正机制。')
 actions=[];blocked=[]
 for code,source,_,_,_ in STEPS:
  if order.status!=source:continue
  try:_authority(user,code,order);_separation(user,order,code,history);actions.append(code)
  except Exception as error:
   if not hasattr(error,'code'):raise
   blocked.append({'code':error.code,'message':str(error)})
 return {'contractVersion':CONTRACT,'orderId':order.pk,'orderNo':order.po_no,'sourceFingerprint':fingerprint,
  'decisionVersion':len(history),'workflowVersion':wf.version if wf else 0,'statusCode':order.status,
  'statusLabel':order.get_status_display(),'history':history,'availableActions':actions,'blockedReasons':blocked,
  'requestedAction':action,'actionContracts':ACTION_CONTRACTS,'automaticReplayAllowed':False,'businessWriteCount':0}

@transaction.atomic
def action_result(*,user,order_id,action,key):
 order=_load(user,order_id);_authority(user,action,order);_history(order)
 row=MasterDataWriteRequest.objects.filter(organization_id=order.company_id,entity_type=ENTITY,action_code=action,idempotency_key=text(key,'同次动作键',120)).first()
 if row and (row.audit_metadata.get('actorId')!=user.pk or row.audit_metadata.get('orderId')!=order.pk):fail('ORDER_ACTION_RESULT_NOT_FOUND','同次结果不属于本办理人及对象。',404)
 return _receipt(row) if row and row.status=='COMMITTED' else {'resultState':'UNKNOWN','result':None,'automaticReplayAllowed':False,'businessWriteCount':0}

def _audit(user,obj,name,before,after,action,reason,authorization,order):
 return OrganizationOperatingAuditRecord.objects.create(action_code=action,actor=user,organization_id=order.company_id,
  target_type=name,target_id=obj.pk,target_label=order.po_no,reason=reason,
  before_snapshot={'state':before},after_snapshot={'state':after,'authorization':authorization,'orderId':order.pk})

def _initial(user,obj,name,action,reason,authorization,order,wf):
 event=_audit(user,obj,name,{'status':''},{'status':'pending'},action,reason,authorization,order)
 record_projected_business_transition(object_type=name,object_id=obj.pk,source_state='',target_state='pending',action_code=action,
  operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',workflow_instance=wf,allowed_transitions={('','pending')})

def _advance(user,obj,name,target,action,reason,authorization,order,wf):
 source=obj.status;event=_audit(user,obj,name,{'status':source},{'status':target},action,reason,authorization,order)
 transition_business_object(business_object=obj,object_type=name,source_state=source,target_state=target,action_code=action,
  operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',workflow_instance=wf,
  allowed_transitions={(source,target)},updated_at_field=None)

@transaction.atomic
def _execute_atomic(*,user,order_id,action,payload):
 if action not in [x[0] for x in STEPS]:fail('ORDER_ACTION_INVALID','不是原采购订单四动作。',400)
 keys={'sourceFingerprint','expectedDecisionVersion','expectedWorkflowVersion','reason','idempotencyKey'}
 if not isinstance(payload,dict) or set(payload)!=keys:fail('ORDER_ACTION_INPUT_INVALID','须提交准确来源、决定/流程版本、理由及同次动作键，不接受自报身份或状态。',400)
 key=text(payload['idempotencyKey'],'同次动作键',120);reason=text(payload['reason'],'办理理由',240)
 order=_load(user,order_id,lock=True);authorization,role,node=_authority(user,action,order);history,wf=_history(order,lock=True)
 body={**payload,'actorId':user.pk,'actorEmployeeId':user.employee_profile.pk,'orderId':order.pk,'action':action}
 prior=MasterDataWriteRequest.objects.select_for_update().filter(organization_id=order.company_id,entity_type=ENTITY,action_code=action,idempotency_key=key).first()
 if prior:
  if prior.audit_metadata.get('actorId')!=user.pk or prior.audit_metadata.get('orderId')!=order.pk:fail('ORDER_ACTION_RESULT_NOT_FOUND','同次结果不属于本办理人及对象。',404)
  if prior.request_hash!=_canonical_hash(body):fail('ORDER_ACTION_REQUEST_CHANGED','同次动作内容已变化。')
  if prior.status!='COMMITTED':fail('ORDER_ACTION_RESULT_UNKNOWN','结果待核实，请先查询同次动作。')
  return {**_receipt(prior),'idempotentReplay':True}
 source,target=next((s,t) for a,s,t,_,_ in STEPS if a==action)
 if order.status!=source or len(history)!=[x[0] for x in STEPS].index(action):fail('ORDER_ACTION_SEQUENCE_CONFLICT','当前状态或办理顺序不允许该动作。')
 _separation(user,order,action,history);snapshot=_snapshot(order);fingerprint=_canonical_hash(snapshot)
 if history and fingerprint!=history[0]['sourceFingerprint']:fail('ORDER_FROZEN_SOURCE_CHANGED','提交后的准确订单依据发生变化，保持待核。')
 if (payload['sourceFingerprint']!=fingerprint or type(payload['expectedDecisionVersion']) is not int or payload['expectedDecisionVersion']!=len(history)
     or type(payload['expectedWorkflowVersion']) is not int or payload['expectedWorkflowVersion']!=(wf.version if wf else 0)):
  fail('ORDER_APPROVAL_VERSION_CONFLICT','来源、决定或流程版本已变化，请先查询原结果。')
 request,created,_=_write_request(user=user,action_code=action,entity_type=ENTITY,key=key,request_body=body)
 if not created:fail('ORDER_ACTION_RESULT_UNKNOWN','并发结果待核实，请先查询。')
 if wf is None:
  wf=create_business_object_with_initial_state(model=WorkflowInstance,initial_state='pending',instance_no=f'PO-APPROVAL-{order.pk}',
   process_definition=node.process_definition,document_type=DOCUMENT,document_id=order.pk,current_step=1,total_steps=4,version=1)
  _initial(user,wf,'WorkflowInstance',action,reason,authorization,order,wf)
 step=len(history)+1
 task=create_business_object_with_initial_state(model=ApprovalTask,initial_state='pending',task_no=f'PO-APPROVAL-{order.pk}-{step}',
  workflow_instance=wf,step_no=step,required_role_code=role,minimum_approvals=1,allow_parallel=False,version=1)
 _initial(user,task,'ApprovalTask',action,reason,authorization,order,wf)
 value={'contractVersion':CONTRACT,'orderId':order.pk,'action':action,'actorId':user.pk,'actorEmployeeId':user.employee_profile.pk,'sourceFingerprint':fingerprint,
        'decisionVersion':step,'workflowNodeId':node.pk,'workflowNodeCode':node.node_code,'workflowNodeSequence':node.sequence,
        'reason':reason,'creationAuditId':snapshot['creationAuditId']}
 decision=ApprovalDecision.objects.create(task=task,decision_sequence=1,actor=user,decision=action.rsplit('.',1)[-1],comment=reason,
  action_id=f'PO-APPROVAL:{action}',idempotency_key=key,decision_hash=_canonical_hash(value))
 _advance(user,task,'ApprovalTask','approved',action,reason,authorization,order,wf);task.completed_at=timezone.now();task.save(update_fields=['completed_at'])
 wf.current_step=min(step+1,4);wf.completed_at=timezone.now() if step==4 else None;wf.save(update_fields=['current_step','completed_at'])
 _advance(user,wf,'WorkflowInstance','approved' if step==4 else 'pending',action,reason,authorization,order,wf)
 event=_audit(user,order,'PurchaseOrder',{'status':source},{'status':target},action,reason,authorization,order)
 transition_business_object(business_object=order,object_type=DOCUMENT,source_state=source,target_state=target,action_code=action,
  operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',workflow_instance=wf,
  allowed_transitions={(source,target)},version_field=None)
 proof={'contractVersion':CONTRACT,'orderId':order.pk,'action':action,'actorId':user.pk,'actorEmployeeId':user.employee_profile.pk,'beforeStatus':source,'status':target,
  'sourceFingerprint':fingerprint,'frozenSource':snapshot if step==1 else None,'decisionVersion':step,'workflowVersion':wf.version,
  'workflowInstanceId':wf.pk,'approvalTaskId':task.pk,'approvalDecisionId':decision.pk,'decision':value,'writeRequestId':request.pk}
 proof['proofHash']=_canonical_hash(proof);event.after_snapshot={**event.after_snapshot,'orderApproval':proof};event.save(update_fields=['after_snapshot'])
 output={'objectId':order.pk,'objectType':'PurchaseOrder','objectNo':order.po_no,'status':order.status,'statusLabel':order.get_status_display(),
  'decisionVersion':step,'workflowVersion':wf.version,'auditId':event.pk,'approvalDecisionId':decision.pk,'targetId':str(order.pk)}
 _commit_request(request,output);_history(order)
 return {**_receipt(request),'businessWriteCount':1}


def execute_action(*,user,order_id,action,payload):
 try:
  return _execute_atomic(user=user,order_id=order_id,action=action,payload=payload)
 except OperationalError as error:
  if 'locked' in str(error).lower():fail('ORDER_CONCURRENT_CHANGE','并发状态变化，结果待核实，请先查询同次动作。')
  raise
 except IntegrityError as error:
  if 'UNIQUE constraint failed' in str(error) and any(t in str(error) for t in ('workflow_instances','workflow_approval_tasks','workflow_approval_decisions','masterdata_write_request')):
   fail('ORDER_CONCURRENT_CHANGE','并发同次动作冲突，请先查询原结果。')
  raise
