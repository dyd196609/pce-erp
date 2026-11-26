"""Native onsite return of rejected goods that never entered qualified stock.

Append-only exception facts; one original shared approval; no inventory or
settlement posting. Supplier replies remain opinions, never return authority.
"""
from decimal import Decimal
import uuid
from django.db import transaction
from django.utils import timezone
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord as Audit, PositionResponsibility, PositionWorkflowResponsibility
from pfm.formal_employee import formal_employee_queryset
from workflow_runtime.models import ProcessDefinition, WorkflowInstance, ApprovalTask, ApprovalDecision, BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state as initial, record_projected_business_transition as projected, transition_business_object as transition
from masterdata.models import MasterDataWriteRequest
from pde.product_design_service import _canonical_hash as digest, _write_request, _commit_request
from planning.operation_handover_configuration import business_today
from planning.work_order_workshop_receipt_service import _effective
from .models import IncomingQualityExceptionFact as Fact, PurchaseInspection, Warehouse
from . import incoming_exception_service as original
from .material_stock_authority import actor, fail, quantity, inspection_line_facts
from .material_preparation_service import _time

CONTRACT='PCE-NEVER-STOCKED-INCOMING-ONSITE-RETURN-V1'
PROCESS='PROCUREMENT_INCOMING_RETURN'
WORKFLOW_DOCUMENT='IncomingQualityReturnRequest'
ENTITY='IncomingQualityExceptionFact'
CODES={'return_request':'procurement.incoming_exception.return_request',
       'return_decide':'procurement.incoming_exception.return_decide',
       'return_handover':'warehouse.incoming_exception.return_handover'}
LABELS={'return_request':'已申请企业退供，尚未交出', 'return_decide':'已记录企业退供决定，尚不证明交出',
        'return_handover':'已记录供应商授权代表现场签收'}
DUTIES={'return_request':'RESP_PUR_EXCEPTION_004','return_decide':'SCM_INCOMING_RETURN_DECISION','return_handover':'RESP_WH_IO_001'}
NODES={'return_request':'RETURN_REQUEST','return_decide':'RETURN_DECIDE','return_handover':'RETURN_HANDOVER'}
ACTION_CONTRACT={'contractVersion':CONTRACT,'actionContracts':[{
 'actionCode':code,'moduleCode':'SCM_INCOMING_EXCEPTION','displayName':LABELS[kind],
 'requiredPermission':code,'role':'purchase_manager' if kind=='return_decide' else 'warehouse' if kind=='return_handover' else 'FORMAL_RESPONSIBLE_BUYER',
 'organizationScope':'EXISTING_NATIVE_OBJECT_SCOPE','serverValidator':'procurement.incoming_return_service.execute'}
 for kind,code in CODES.items()], 'inventoryEffect':'NONE','approvalStages':1}

def text(value,label,limit=1000):
 return original.text(value,label,limit=limit)

def identifier(value,label):
 if type(value) is not int or value<=0:fail('INCOMING_RETURN_INPUT_INVALID',label+'须从准确原对象选择。',400)
 return value

def qualification(user,kind,order):
 user=actor(user)
 if kind not in CODES:fail('INCOMING_RETURN_ACTION_UNKNOWN','没有该退供动作。',404)
 employee=formal_employee_queryset(company_id=user.company_id).filter(user_id=user.pk).select_related('position_ref','department_ref').first()
 buyer=formal_employee_queryset(company_id=order.company_id).filter(pk=order.buyer_employee_id).first()
 context={'companyId':order.company_id,'organizationId':order.company_id,
          'departmentId':order.purchase_department_id or order.department_id or '__NOT_PROVIDED__',
          'ownerUserId':buyer.user_id if buyer else '__NOT_PROVIDED__'}
 decision=AuthorizationService.decide(user=user,action_code=CODES[kind],organization_id=order.company_id,business_object=context)
 today=business_today()
 ownership='OWNER' if kind=='return_decide' else 'EXECUTOR'
 mappings=PositionWorkflowResponsibility.objects.select_related('responsibility','workflow_node__process_definition').filter(
  position_id=employee.position_ref_id if employee else None,active=True,ownership_type=ownership,
  responsibility__code=DUTIES[kind],responsibility__is_active=True,responsibility__status='ACTIVE',
  workflow_node__active=True,workflow_node__node_code=NODES[kind],workflow_node__business_action_code=CODES[kind],
  workflow_node__process_definition__definition_code=PROCESS,workflow_node__process_definition__active=True)
 link=mappings.first() if mappings.count()==1 else None
 if (not decision.get('allowed') or not employee or not link
     or not PositionResponsibility.objects.filter(position_id=employee.position_ref_id,responsibility_id=link.responsibility_id,active=True).exists()
     or not all(_effective(obj,today) for obj in (employee.position_ref,employee.department_ref,link.responsibility))
     or employee.hire_date and employee.hire_date>today or employee.leave_date and employee.leave_date<=today
     or employee.resignation_date and employee.resignation_date<=today
     or link.effective_from and link.effective_from>today or link.effective_to and link.effective_to<today):
  fail('INCOMING_RETURN_QUALIFICATION_DENIED','须本人的有效任职、原单据范围及本退供动作职责和权限。',403)
 definition=link.workflow_node.process_definition
 expected={(NODES[k],CODES[k],n) for n,k in enumerate(CODES,1)}
 if (definition.document_type!=WORKFLOW_DOCUMENT or definition.version!=1
     or set(definition.nodes.filter(active=True).values_list('node_code','business_action_code','sequence'))!=expected):
  fail('INCOMING_RETURN_WORKFLOW_UNPROVEN','正式退供流程及单环节决定节点不完整，保留待核。')
 role='purchase_manager' if kind=='return_decide' else 'warehouse' if kind=='return_handover' else None
 if role and not any(e.role_code==role and CODES[kind] in AuthorizationService.permission_codes_for_user(user,{role})
                     and AuthorizationService._scope_matches(e,user,context,{}) for e in AuthorizationService.authority_evidence(user)):
  fail('INCOMING_RETURN_ROLE_SCOPE_DENIED','原经理或仓管岗位及其准确范围不允许本动作。',403)
 if kind=='return_request':
  proof=original.responsible_buyer(order)
  if proof['userId']!=user.pk or proof['employeeId']!=employee.pk:
   fail('INCOMING_RETURN_NOT_RESPONSIBLE_BUYER','仅本采购可证明的正式负责采购员本人可申请。',403)
 return user,employee,decision,definition

def _load(user,inspection_id,kind,root_id,lock=False,current=True):
 user=actor(user)
 q=PurchaseInspection.objects.select_related('source_receipt__source_purchase_order')
 if lock:q=q.select_for_update()
 inspection=q.filter(pk=identifier(inspection_id,'检验单'),source_receipt__source_purchase_order__company_id=user.company_id).first()
 if not inspection:fail('INCOMING_RETURN_NOT_FOUND','本授权企业没有该准确检验来源。',404)
 order=inspection.source_receipt.source_purchase_order
 user,employee,authorization,definition=qualification(user,kind,order)
 q=Fact.objects.select_related('audit_record').filter(company_id=user.company_id,inspection=inspection)
 if lock:q=q.select_for_update()
 rows=list(q.order_by('pk'))
 root=next((r for r in rows if r.pk==root_id and r.kind=='register' and r.registration_id is None),None)
 if root is None:fail('INCOMING_RETURN_REGISTRATION_NOT_FOUND','须选择本次检验的准确不合格异常登记。',404)
 for row in rows:original.receipt(row)
 line=inspection_line_facts(inspection) if current else None
 if current:
  original.responsible_buyer(order)
  if root.source_snapshot.get('supplierId')!=order.supplier_id:fail('INCOMING_RETURN_SOURCE_PENDING','原异常供应商与当前采购来源不一致，不沿用旧申请或授权收方。')
  historical=root.source_snapshot.get('lineFacts',{})
  stable=('purchaseOrderId','purchaseOrderItemId','receiptId','inspectionId','materialId','unit',
          'inspectionScopeQuantity','qualifiedQuantity','rejectedQuantity','qualityReleaseStatus')
  if any(line.get(k)!=historical.get(k) for k in stable) or line.get('rejectedQuantity') is None:
   fail('INCOMING_RETURN_SOURCE_PENDING','原登记与当前采购行、实收及最终质量来源不一致，保留待核。')
  registered=sum((r.quantity for r in rows if r.kind=='register'),Decimal(0))
  if root.quantity<=0 or registered>Decimal(line['rejectedQuantity']):
   fail('INCOMING_RETURN_SCOPE_UNPROVEN','本次正式拒收数量与累计登记范围不符。')
  # The native source service proves every successful IN belongs to qualified
  # quantity; these rejected quantities have no IN, lot, or stock dimension.
  if Decimal(line['successfullyInboundQuantity'])>Decimal(line['qualifiedQuantity']):
   fail('INCOMING_RETURN_STOCK_SCOPE_PENDING','原入库超出合格范围，不得据此办理未入账退供。')
 selected=[r for r in rows if r.registration_id==root.pk]
 return user,inspection,order,employee,authorization,definition,root,selected,line

def _source_fingerprint(root,line):
 keys=('purchaseOrderId','purchaseOrderItemId','receiptId','inspectionId','materialId','unit',
       'inspectionScopeQuantity','qualifiedQuantity','rejectedQuantity','qualityReleaseStatus')
 return digest({'registrationFactHash':root.audit_record.after_snapshot['factHash'],
                'line':{k:line.get(k) for k in keys}})

def _opinions(rows):
 return [original.receipt(r) for r in rows if r.kind=='opinion']

def _workflow(request,decision_row=None):
 wf=WorkflowInstance.objects.select_related('process_definition').filter(document_type=WORKFLOW_DOCUMENT,document_id=request.pk).first()
 task=wf.tasks.first() if wf else None
 if (not wf or not task or wf.process_definition.definition_code!=PROCESS or wf.total_steps!=1
     or wf.current_step!=1 or wf.tasks.count()!=1 or task.step_no!=1 or task.required_role_code!='purchase_manager'
     or task.minimum_approvals!=1 or task.allow_parallel):
  fail('INCOMING_RETURN_APPROVAL_HISTORY_UNPROVEN','本准确申请的共享单环节决定依据不完整。')
 decisions=list(task.decisions.order_by('decision_sequence'))
 wanted='approved' if decision_row and decision_row.payload['decisionValue']['decision']=='approve' else 'rejected' if decision_row else 'pending'
 expected_count=2 if decision_row else 1
 if (wf.status!=wanted or task.status!=wanted or wf.version!=expected_count or task.version!=expected_count
     or len(decisions)!=(1 if decision_row else 0)):
  fail('INCOMING_RETURN_APPROVAL_HISTORY_UNPROVEN','共享当前状态、版本与决定不一致。')
 if decision_row:
  d=decisions[0];value=decision_row.payload['decisionValue']
  if (d.pk!=decision_row.payload.get('approvalDecisionId') or d.decision_sequence!=1
      or d.actor_id!=decision_row.created_by_id or d.decision!=value.get('decision')
      or d.comment!=value.get('reason') or d.decision_hash!=digest(value)
      or value.get('requestId')!=request.pk or value.get('requestIntentHash')!=request.intent_hash
      or value.get('decisionVersion')!=1 or value.get('actorId')!=d.actor_id
      or decision_row.payload.get('workflowInstanceId')!=wf.pk or decision_row.payload.get('approvalTaskId')!=task.pk
      or decision_row.quantity!=(request.quantity if wanted=='approved' else Decimal(0))):
   fail('INCOMING_RETURN_DECISION_UNPROVEN','企业决定、申请版本、数量、办理人及共享原决定不一致。')
 for obj,name in ((wf,'WorkflowInstance'),(task,'ApprovalTask')):
  chain=list(BusinessStateTransition.objects.filter(object_type=name,object_id=obj.pk).order_by('version'))
  if len(chain)!=expected_count:fail('INCOMING_RETURN_APPROVAL_HISTORY_UNPROVEN','共享决定转换链不完整。')
  previous=''
  for index,t in enumerate(chain,1):
   audit=Audit.objects.filter(pk=t.audit_reference.split(':')[-1]).first() if t.audit_reference.startswith('OrganizationOperatingAuditRecord:') and t.audit_reference.split(':')[-1].isdigit() else None
   expected_actor=request.created_by_id if index==1 else decision_row.created_by_id
   if (not audit or audit.target_type!=name or audit.target_id!=obj.pk or audit.actor_id!=expected_actor
       or audit.organization_id!=request.company_id or not audit.after_snapshot.get('authorization',{}).get('allowed')
       or audit.before_snapshot.get('state',{}).get('status')!=previous
       or audit.after_snapshot.get('state',{}).get('status')!=t.target_state
       or t.source_state!=previous or t.version!=index or t.operator_id!=expected_actor or t.workflow_instance_id!=wf.pk
       or t.action_code!=CODES['return_request' if index==1 else 'return_decide']):
    fail('INCOMING_RETURN_APPROVAL_HISTORY_UNPROVEN','共享对象、真实审计及状态转换不一致。')
   previous=t.target_state
  if previous!=obj.status:fail('INCOMING_RETURN_APPROVAL_HISTORY_UNPROVEN','共享当前状态与历史不一致。')
 return wf,task,decisions

def _history(root,rows):
 for row in rows:
  if row.kind in CODES:original.receipt(row)
 requests={r.pk:r for r in rows if r.kind=='return_request'}
 decisions={};handovers=[]
 for row in rows:
  if row.kind not in CODES:continue
  if row.payload.get('contractVersion')!=CONTRACT or row.source_snapshot.get('registrationId')!=root.pk:
   fail('INCOMING_RETURN_HISTORY_UNPROVEN','退供事实类型化来源与准确登记不一致。')
  if row.kind=='return_decide':
   key=row.payload.get('requestId')
   if key not in requests or key in decisions:fail('INCOMING_RETURN_HISTORY_UNPROVEN','企业决定的准确申请或唯一关系不成立。')
   decisions[key]=row
  elif row.kind=='return_handover':handovers.append(row)
 workflows={}
 for key,request in requests.items():workflows[key]=_workflow(request,decisions.get(key))
 sums={key:Decimal(0) for key in requests}
 for row in handovers:
  key=row.payload.get('requestId');decision=decisions.get(key)
  if (not decision or decision.payload['decisionValue']['decision']!='approve'
      or row.payload.get('decisionFactId')!=decision.pk or row.payload.get('decisionVersion')!=1
      or row.quantity is None or row.quantity<=0 or row.occurred_at<decision.occurred_at):
   fail('INCOMING_RETURN_HANDOVER_UNPROVEN','交付缺少本准确申请、企业批准及数量时间证明。')
  sums[key]+=row.quantity
 if any(sums[key]>(decisions[key].quantity if key in decisions else Decimal(0)) for key in sums):
  fail('INCOMING_RETURN_QUANTITY_CONFLICT','同一批准累计交付超量，保留全部原记录待核。')
 total=sum(sums.values(),Decimal(0))
 if total>root.quantity:fail('INCOMING_RETURN_QUANTITY_CONFLICT','同一异常跨申请累计交付超量，不能继续。')
 outstanding=Decimal(0)
 for key,request in requests.items():
  d=decisions.get(key)
  outstanding+=request.quantity if d is None else d.quantity-sums[key] if d.payload['decisionValue']['decision']=='approve' else Decimal(0)
 if total+outstanding>root.quantity:fail('INCOMING_RETURN_QUANTITY_CONFLICT','同一异常的未交批准及待决定申请重复覆盖。')
 return requests,decisions,handovers,sums,total,outstanding,workflows

def _custody(root,rows,handovers):
 observations=[r for r in rows if r.kind=='custody']
 latest=observations[-1] if observations else None
 raw=latest.payload.get('confirmedCustodyQuantity') if latest else None
 confirmed=Decimal(raw) if raw is not None else None
 # A later physical observation is the count at its own time, not another
 # receipt and not an additional quantity. Only subsequent handovers subtract.
 subsequent=sum((r.quantity for r in handovers if latest and r.occurred_at>=latest.occurred_at),Decimal(0))
 remaining=None if confirmed is None else confirmed-subsequent
 if remaining is not None and remaining<0:fail('INCOMING_RETURN_CUSTODY_CONFLICT','本人核实量与其后实交量不一致，保留待核。')
 return latest,remaining

def summary(root,rows):
 requests,decisions,handovers,sums,total,outstanding,workflows=_history(root,rows)
 latest,physical=_custody(root,rows,handovers)
 return {'registeredRejectedQuantity':str(root.quantity),'cumulativeHandedQuantity':str(total),
  'notHandedRegisteredQuantity':str(root.quantity-total),'unrequestedQuantity':str(root.quantity-total-outstanding),
  'outstandingApplicationOrApprovedQuantity':str(outstanding),
  'currentWarehouseVerifiedQuantity':str(physical) if physical is not None else None,
  'currentWarehouseVerifiedQuantityStatus':'PROVIDED' if physical is not None else 'NOT_PROVIDED',
  'latestCustodyFactId':latest.pk if latest else None,'remainingCustodianId':latest.payload.get('confirmedCustodianId') if latest and root.quantity>total else None,
  'historicalCustodyQuantity':latest.payload.get('confirmedCustodyQuantity') if latest else None,
  'statusLabel':'本范围已登记现场交付，未作异常结案' if total==root.quantity else '本范围部分交付，余量保管责任保留' if total else '本范围尚未交付，原保管责任保留',
  'inventoryEffect':'NONE','payableEffect':'NONE','exceptionClosed':False,'scope':'EXACT_REJECTED_REGISTRATION_ONLY',
  'requests':[{'requestId':key,'quantity':str(r.quantity),'decisionVersion':1 if key in decisions else 0,
   'decisionFactId':decisions[key].pk if key in decisions else None,'workflowVersion':workflows[key][0].version,
   'statusLabel':'待企业决定' if key not in decisions else '企业不同意退供' if decisions[key].quantity==0 else '本申请批准范围已交付' if sums[key]==decisions[key].quantity else '企业已批准，待交付或部分交付',
   'approvedQuantity':str(decisions[key].quantity) if key in decisions else None,'handedQuantity':str(sums[key]),
   'remainingApprovedQuantity':str(decisions[key].quantity-sums[key]) if key in decisions else None,
   'applicantId':r.created_by_id,'proposal':r.payload['proposal']} for key,r in requests.items()]}

def _separation(user,request,rows):
 opinion_actors={r.created_by_id for r in rows if r.kind=='opinion'}
 hander_actors={r.created_by_id for r in rows if r.kind=='return_handover'}
 if user.pk==request.created_by_id or user.pk in opinion_actors|hander_actors:
  fail('INCOMING_RETURN_SEPARATION_REQUIRED','决定人与本次申请人、供应商意见经办人及实际交出人须分离。',403)

def _available_handover(user,request,decision,root,rows,line,handovers,sums):
 if not decision or decision.quantity<=0:fail('INCOMING_RETURN_APPROVAL_REQUIRED','须本准确申请及版本的正式批准。')
 if user.pk==decision.created_by_id:
  fail('INCOMING_RETURN_SEPARATION_REQUIRED','企业决定人不得同时承担本笔实际交付。',403)
 if request.source_snapshot.get('sourceFingerprint')!=_source_fingerprint(root,line) or decision.source_snapshot.get('sourceFingerprint')!=_source_fingerprint(root,line):
  fail('INCOMING_RETURN_SOURCE_CHANGED','批准来源已变化，历史保留，不能沿旧版本交付。')
 if decision.payload['decisionValue']['supplierOpinionCollectionHash']!=digest(_opinions(rows)):
  fail('INCOMING_RETURN_SUPPLIER_CONDITIONS_CHANGED','批准后供应商意见或附加条件已变化，不能沿旧决定交付。')
 latest,physical=_custody(root,rows,handovers)
 if not latest or latest.payload.get('confirmedCustodianId')!=user.pk or physical is None:
  fail('INCOMING_RETURN_CUSTODY_PENDING','须本仓管本人有据确认的实际保管范围，不能借合格品库位批次。')
 storage=AuthorizationService.decide(user=user,action_code=CODES['return_handover'],organization_id=root.company_id,
  business_object={'companyId':root.company_id,'organizationId':root.company_id,'warehouseId':latest.payload.get('warehouseId'),
   'departmentId':line.get('departmentId') or '__NOT_PROVIDED__','ownerUserId':user.pk})
 if not Warehouse.objects.filter(pk=latest.payload.get('warehouseId'),company_id=root.company_id,is_active=True).exists() or not storage.get('allowed'):
  fail('INCOMING_RETURN_WAREHOUSE_SCOPE_DENIED','本人无该实际保管仓储范围的交付资格。',403)
 return latest,min(physical,decision.quantity-sums[request.pk])

@transaction.atomic
def registration_sources(*,user,inspection_id):
 """Discover exact-inspection roots using the existing decision qualification.

 Selection is read-only and grants neither a decision nor its current eligibility.
 The original detail/write paths revalidate the selected root and request.
 """
 user=actor(user)
 inspection=PurchaseInspection.objects.select_related('source_receipt__source_purchase_order').filter(
  pk=identifier(inspection_id,'检验单'),source_receipt__source_purchase_order__company_id=user.company_id).first()
 if not inspection:fail('INCOMING_RETURN_NOT_FOUND','本授权企业没有该准确检验来源。',404)
 qualification(user,'return_decide',inspection.source_receipt.source_purchase_order)
 line=inspection_line_facts(inspection)
 if line['rejectedQuantity'] is None:
  fail('INCOMING_EXCEPTION_QUALITY_PENDING','本次检验尚未最终判定不合格数量，不能据此认定没有异常。')
 roots=Fact.objects.select_related('audit_record').filter(company_id=user.company_id,inspection=inspection,kind='register',registration__isnull=True).order_by('pk')
 identity={k:line.get(k) for k in ('purchaseOrderId','purchaseOrderNo','purchaseOrderItemId','purchaseOrderLineNo',
  'receiptId','receiptNo','inspectionId','inspectionNo','materialId','materialCode','materialName','unit')}
 results=[]
 for root in roots:
  item={**identity,'registrationId':root.pk,'registeredRejectedQuantity':None,'registeredAt':None,
   'pendingRequestCount':None,'returnSummary':None,'sourceStatus':'SOURCE_UNKNOWN','statusLabel':'本登记来源或历史待核','blockingReason':None,
   'detailUrl':f'/api/procurement/incoming-exceptions/{inspection.pk}/returns/return_decide/?registrationId={root.pk}'}
  try:
   proof=original.receipt(root)
   item.update(registeredRejectedQuantity=proof['quantity'],registeredAt=proof['registeredAt'])
   current=context(user=user,inspection_id=inspection.pk,kind='return_decide',registration_id=root.pk)
   item.update(sourceStatus='PROVIDED',statusLabel='本检验异常登记，可选择后查看准确申请',returnSummary=current['returnSummary'],
    pendingRequestCount=sum(1 for r in current['returnSummary']['requests'] if r['decisionVersion']==0))
  except Exception as exc:
   if not hasattr(exc,'http_status') or exc.http_status!=409:raise
   item['blockingReason']={'code':exc.code,'message':str(exc),'httpStatus':exc.http_status}
  results.append(item)
 return {'contractVersion':CONTRACT,'projection':'EXACT_INSPECTION_RETURN_REGISTRATIONS',
  'inspection':identity,'results':results,'count':len(results),'countScope':'THIS_AUTHORIZED_INSPECTION_REGISTRATIONS_ONLY',
  'selectionGrantsExecution':False,'businessWriteCount':0,'requiresSelectedDetailReload':True}

@transaction.atomic
def context(*,user,inspection_id,kind,registration_id,request_id=None):
 user,i,order,e,authorization,definition,root,rows,line=_load(user,inspection_id,kind,registration_id)
 requests,decisions,handovers,sums,total,outstanding,workflows=_history(root,rows)
 selected=requests.get(request_id) if request_id is not None else None
 if request_id is not None and selected is None:fail('INCOMING_RETURN_REQUEST_NOT_FOUND','申请不属于所选准确异常登记。',404)
 allowed=False;reason=None
 try:
  if kind=='return_request':
   if root.quantity-total-outstanding<=0:fail('INCOMING_RETURN_NO_REQUESTABLE_SCOPE','本异常已被待决定申请、批准或实交范围覆盖，不重复申请。')
   allowed=True
  elif not selected:fail('INCOMING_RETURN_REQUEST_REQUIRED','请从本异常选择准确退供申请。')
  elif kind=='return_decide':
   _separation(user,selected,rows)
   if selected.pk in decisions:fail('INCOMING_RETURN_DECISION_EXISTS','本申请已有企业决定，不覆盖或重复审批。')
   if selected.source_snapshot.get('sourceFingerprint')!=_source_fingerprint(root,line):fail('INCOMING_RETURN_SOURCE_CHANGED','本申请来源已变化，保留待核。')
   allowed=True
  else:
   _,available=_available_handover(user,selected,decisions.get(selected.pk),root,rows,line,handovers,sums)
   if available<=0:fail('INCOMING_RETURN_NO_HANDOVER_SCOPE','本申请没有已核实且尚未交出的批准量。')
   allowed=True
 except Exception as exc:
  if not hasattr(exc,'code') or not hasattr(exc,'http_status'):raise
  if exc.http_status not in (403,409):raise
  reason={'code':exc.code,'message':str(exc),'httpStatus':exc.http_status}
 facts=[original.receipt(r) for r in rows]
 return {'contractVersion':CONTRACT,'inspection':line,'registration':original.receipt(root),
  'supplierOpinions':_opinions(rows),'supplierOpinionsAreNotEnterpriseApproval':True,
  'history':facts,'returnSummary':summary(root,rows),
  'collectionVersion':digest({'source':line,'facts':facts,'workflow':[(k,v[0].version,v[0].status) for k,v in workflows.items()]}),
  'sourceFingerprint':_source_fingerprint(root,line),'selectedRequestId':request_id,
  'actionAuthorization':{'allowed':allowed,'permission':CODES[kind],'blockingReason':reason},
  'factLoadStatus':'loaded','currentStateSource':'server','businessWriteCount':0,'inventoryEffect':'NONE'}

def _shared_audit(user,obj,name,source,target,code,reason,authorization,wf,initialize=False):
 audit=Audit.objects.create(actor=user,organization_id=user.company_id,action_code=code,target_type=name,target_id=obj.pk,
  target_label=f'{name}:{obj.pk}',reason=reason,before_snapshot={'state':{'status':source}},
  after_snapshot={'state':{'status':target},'authorization':authorization})
 args=dict(object_type=name,source_state=source,target_state=target,action_code=code,operator=user,reason=reason,
  audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',workflow_instance=wf,allowed_transitions={(source,target)})
 if initialize:projected(object_id=obj.pk,**args)
 else:transition(business_object=obj,updated_at_field=None,**args)

def _persist(user,i,root,kind,qty,intent,meaning,body,source,occurred,reason,req):
 proof={'kind':kind,'inspectionId':i.pk,'registrationId':root.pk,'quantity':format(qty,'.6f'),
  'intentId':intent,'actorId':user.pk,'occurredAt':occurred.isoformat(),'payload':body,'source':source}
 audit=Audit.objects.create(actor=user,organization_id=user.company_id,action_code=CODES[kind],target_type=ENTITY,target_id=0,
  target_label=i.inspection_no,reason=reason,after_snapshot={'factHash':digest(proof),'fact':proof})
 row=initial(model=Fact,initial_state='recorded',company_id=user.company_id,inspection=i,registration=root,kind=kind,quantity=qty,
  intent_id=intent,intent_hash=digest(meaning),payload=body,source_snapshot=source,created_by=user,occurred_at=occurred,audit_record=audit)
 audit.target_id=row.pk;audit.save(update_fields=['target_id'])
 projected(object_type=ENTITY,object_id=row.pk,source_state='',target_state='recorded',action_code=CODES[kind],operator=user,
  reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','recorded')})
 result={**original.receipt(row),'businessWriteCount':1,'historicalReceiptOnly':True,'automaticReplayAllowed':False}
 _commit_request(req,result)
 return row,result

@transaction.atomic
def execute(*,user,inspection_id,kind,payload):
 required={'idempotencyKey','intentId','expectedCollectionVersion','reason','occurredAt','registrationId','details'}
 if not isinstance(payload,dict) or set(payload)!=required or not isinstance(payload['details'],dict):
  fail('INCOMING_RETURN_INPUT_INVALID','只接受正式动作意图、准确版本及本次事实，不接受直接状态或身份。',400)
 user,i,order,e,authorization,definition,root,rows,line=_load(user,inspection_id,kind,identifier(payload['registrationId'],'异常登记'),lock=True)
 key=text(payload['idempotencyKey'],'同次标识',160);intent=text(payload['intentId'],'业务意图',120);reason=text(payload['reason'],'办理依据',240)
 occurred=_time(payload['occurredAt'])
 if occurred>timezone.now() or occurred<root.occurred_at:fail('INCOMING_RETURN_TIME_INVALID','实际发生时间须在原登记之后且不晚于本次登记。',400)
 meaning={'inspectionId':i.pk,'kind':kind,'actorId':user.pk,**{k:v for k,v in payload.items() if k not in {'idempotencyKey','expectedCollectionVersion'}}}
 old=Fact.objects.filter(company_id=user.company_id,kind=kind,intent_id=intent).select_related('audit_record').first()
 if old:
  if old.intent_hash!=digest(meaning):fail('INCOMING_RETURN_INTENT_CONFLICT','同一意图内容已变化，不能覆盖或重复办理。')
  return {**original.receipt(old),'businessWriteCount':0,'idempotent':True,'historicalReceiptOnly':True,'automaticReplayAllowed':False}
 requests,decisions,handovers,sums,total,outstanding,workflows=_history(root,rows)
 details=payload['details'];request_id=details.get('requestId') if kind!='return_request' else None
 c=context(user=user,inspection_id=i.pk,kind=kind,registration_id=root.pk,request_id=request_id)
 if payload['expectedCollectionVersion']!=c['collectionVersion']:fail('INCOMING_RETURN_VERSION_CONFLICT','来源、申请或交付集合已变化，请查询原结果或刷新，不自动重放。')
 if not c['actionAuthorization']['allowed']:
  b=c['actionAuthorization']['blockingReason'];fail(b['code'],b['message'],b['httpStatus'])
 source={'contractVersion':CONTRACT,'registrationId':root.pk,'lineFacts':line,'sourceFingerprint':c['sourceFingerprint'],
  'employeeId':e.pk,'employeeNo':e.employee_no,'employeeName':e.full_name,'positionId':e.position_ref_id,
  'purchaseOrderNo':order.po_no,'supplierId':order.supplier_id,'authorization':authorization}
 body={'contractVersion':CONTRACT,'inventoryEffect':'NONE','settlementEffect':'NONE','exceptionClosed':False}
 if kind=='return_request':
  if set(details)!={'quantity','proposal'} or not isinstance(details['proposal'],dict) or set(details['proposal'])!={'receiverName','receiverAuthorizationReference','returnBasis'}:
   fail('INCOMING_RETURN_INPUT_INVALID','须明确申请数量、供应商授权到场收方及本次退供依据。',400)
  qty=quantity(details['quantity'],places=6);precision=order.items.get(pk=line['purchaseOrderItemId']).material.base_uom.decimal_places
  if qty!=qty.quantize(Decimal(1).scaleb(-precision)) or qty>root.quantity-total-outstanding:
   fail('INCOMING_RETURN_QUANTITY_EXCEEDED','本异常跨申请尚可申请量或原单位精度不足。')
  proposal={k:text(v,{'receiverName':'授权代表姓名','receiverAuthorizationReference':'接收授权凭据','returnBasis':'企业退供申请依据'}[k],500) for k,v in details['proposal'].items()}
  body.update(proposal=proposal,supplierOpinionsAtApplication=_opinions(rows))
 elif kind=='return_decide':
  if set(details)!={'requestId','expectedDecisionVersion','decision','reviewedSupplierOpinionIds','supplierConditionsAssessment'}:
   fail('INCOMING_RETURN_INPUT_INVALID','企业决定须绑定准确申请、版本并核对全部回复及附加条件。',400)
  request=requests[identifier(request_id,'退供申请')];_separation(user,request,rows)
  if type(details['expectedDecisionVersion']) is not int or details['expectedDecisionVersion']!=0 or request.pk in decisions:
   fail('INCOMING_RETURN_DECISION_VERSION_CONFLICT','本申请企业决定版本已变化。')
  if occurred<request.occurred_at:fail('INCOMING_RETURN_TIME_INVALID','企业决定不能早于本次申请。',400)
  if details['decision'] not in ('approve','reject'):fail('INCOMING_RETURN_INPUT_INVALID','须明确同意或不同意本准确申请，不接受直接状态。',400)
  opinions=_opinions(rows)
  if details['reviewedSupplierOpinionIds']!=[r['id'] for r in opinions]:fail('INCOMING_RETURN_SUPPLIER_CONDITIONS_PENDING','须核对全部供应商回复及附加条件，不能只采用同意退货一句。')
  assessment=text(details['supplierConditionsAssessment'],'供应商条件核对意见',1000)
  qty=request.quantity if details['decision']=='approve' else Decimal(0)
  wf,task,_=workflows[request.pk]
  value={'contractVersion':CONTRACT,'requestId':request.pk,'requestIntentHash':request.intent_hash,'decisionVersion':1,
   'actorId':user.pk,'decision':details['decision'],'reason':reason,'quantity':str(qty),
   'supplierOpinions':opinions,'supplierOpinionCollectionHash':digest(opinions),'supplierConditionsAssessment':assessment,
   'sourceFingerprint':c['sourceFingerprint'],'occurredAt':occurred.isoformat()}
  body.update(requestId=request.pk,decisionValue=value,workflowInstanceId=wf.pk,approvalTaskId=task.pk)
 else:
  expected={'requestId','decisionId','decisionVersion','quantity','custodyFactId','actualVerifiedQuantity','receiverName',
   'receiverAuthorizationReference','receiptReference','receiverSignatureReference','originalReceiptVerified'}
  if set(details)!=expected:fail('INCOMING_RETURN_INPUT_INVALID','须准确批准、本人实点、到场授权收方及原始签收交接依据。',400)
  request=requests[identifier(request_id,'退供申请')];decision=decisions.get(request.pk)
  latest,available=_available_handover(user,request,decision,root,rows,line,handovers,sums)
  if details['decisionId']!=decision.pk or type(details['decisionVersion']) is not int or details['decisionVersion']!=1:
   fail('INCOMING_RETURN_DECISION_VERSION_CONFLICT','须本申请准确批准记录及决定版本。')
  if details['custodyFactId']!=latest.pk:fail('INCOMING_RETURN_CUSTODY_CHANGED','须重新核对最近一次本人保管事实。')
  qty=quantity(details['quantity'],places=6);verified=quantity(details['actualVerifiedQuantity'],places=6)
  precision=order.items.get(pk=line['purchaseOrderItemId']).material.base_uom.decimal_places
  if any(x!=x.quantize(Decimal(1).scaleb(-precision)) for x in (qty,verified)) or qty>available or qty>verified or verified>root.quantity-total:
   fail('INCOMING_RETURN_QUANTITY_EXCEEDED','实交量不得超过本人实点、准确批准及本异常跨申请尚未交出范围。')
  proposal=request.payload['proposal']
  if details['receiverName']!=proposal['receiverName'] or details['receiverAuthorizationReference']!=proposal['receiverAuthorizationReference']:
   fail('INCOMING_RETURN_RECEIVER_UNPROVEN','实际收方或其接收授权不属于本准确批准，不按供应商同意邮件猜认。')
  if details['originalReceiptVerified'] is not True:fail('INCOMING_RETURN_SIGNED_RECEIPT_REQUIRED','仅原始现场签收有据的数量才能确认交付及责任转移。')
  receipt_ref=text(details['receiptReference'],'原始签收交接凭据',500);signature=text(details['receiverSignatureReference'],'本次收方签收依据',500)
  if occurred<max([decision.occurred_at,latest.occurred_at]+[r.occurred_at for r in handovers]):
   fail('INCOMING_RETURN_TIME_INVALID','现场交付时间须符合准确批准、实物核对和历次交付顺序。',400)
  body.update(requestId=request.pk,decisionFactId=decision.pk,decisionVersion=1,custodyFactId=latest.pk,
   actualVerifiedQuantity=str(verified),handedQuantity=str(qty),unit=line['unit'],
   receiver={'supplierId':order.supplier_id,'name':proposal['receiverName'],'authorizationReference':proposal['receiverAuthorizationReference']},
   signedReceipt={'reference':receipt_ref,'signatureReference':signature,'verification':'PERSONALLY_CHECKED_ORIGINAL_REFERENCE_NOT_DIGITAL_SIGNATURE_VERIFICATION',
    'purchaseOrderId':order.pk,'purchaseOrderItemId':line['purchaseOrderItemId'],'receiptId':line['receiptId'],
    'inspectionId':i.pk,'registrationId':root.pk,'materialId':line['materialId'],'quantity':str(qty),'unit':line['unit'],
    'handoverEmployeeId':e.pk,'handoverUserId':user.pk,'receiverName':proposal['receiverName'],'occurredAt':occurred.isoformat()},
   previousCustodianId=latest.payload['confirmedCustodianId'],responsibilityTransferredQuantity=str(qty),
   remainingRegisteredQuantity=str(root.quantity-total-qty),remainingCustodianId=latest.payload['confirmedCustodianId'] if root.quantity-total>qty else None)
 req,created,_=_write_request(user=user,action_code=CODES[kind],entity_type=ENTITY,key=key,request_body=meaning)
 if not created:fail('INCOMING_RETURN_RESULT_UNKNOWN','原同次记录已存在，请先查询，不自动重放。')
 if kind=='return_decide':
  d=ApprovalDecision.objects.create(task=task,decision_sequence=1,actor=user,decision=details['decision'],comment=reason,
   action_id=uuid.uuid4().hex,idempotency_key=key,decision_hash=digest(value))
  body['approvalDecisionId']=d.pk
  for obj,name in ((task,'ApprovalTask'),(wf,'WorkflowInstance')):
   obj.completed_at=timezone.now();obj.save(update_fields=['completed_at'])
   _shared_audit(user,obj,name,'pending','approved' if qty else 'rejected',CODES[kind],reason,authorization,wf)
 row,result=_persist(user,i,root,kind,qty,intent,meaning,body,source,occurred,reason,req)
 if kind=='return_request':
  wf=initial(model=WorkflowInstance,initial_state='pending',instance_no='IR-'+uuid.uuid4().hex,
   process_definition=definition,document_type=WORKFLOW_DOCUMENT,document_id=row.pk,current_step=1,total_steps=1,version=1)
  task=initial(model=ApprovalTask,initial_state='pending',task_no='IRT-'+uuid.uuid4().hex,workflow_instance=wf,
   step_no=1,required_role_code='purchase_manager',minimum_approvals=1,allow_parallel=False,version=1)
  for obj,name in ((wf,'WorkflowInstance'),(task,'ApprovalTask')):_shared_audit(user,obj,name,'','pending',CODES[kind],reason,authorization,wf,True)
 # Verify the persisted relationship, shared decision and root-wide totals
 # before committing the same transaction, including its action receipt.
 updated=list(Fact.objects.filter(company_id=root.company_id,inspection=i,registration=root).select_related('audit_record').order_by('pk'))
 _history(root,updated)
 return result

@transaction.atomic
def result_query(*,user,inspection_id,kind,registration_id,key,intent_id=None):
 user,i,order,e,authorization,definition,root,rows,line=_load(user,inspection_id,kind,registration_id,current=False)
 key=text(key,'同次动作标识',160)
 req=MasterDataWriteRequest.objects.filter(organization_id=user.company_id,entity_type=ENTITY,action_code=CODES[kind],idempotency_key=key,status='COMMITTED').first()
 row=next((r for r in rows if r.pk==req.result.get('id') and r.created_by_id==user.pk and r.kind==kind),None) if req else None
 if not req and intent_id:row=next((r for r in rows if r.kind==kind and r.intent_id==intent_id and r.created_by_id==user.pk),None)
 if req and row is None:fail('INCOMING_RETURN_RESULT_NOT_FOUND','该同次结果不属于本办理人及准确异常范围。',404)
 return {'resultState':'COMMITTED' if row else 'UNKNOWN','result':original.receipt(row) if row else None,
  'businessWriteCount':0,'automaticReplayAllowed':False,'historicalReceiptOnly':True,'executionAuthorizedByResult':False}
