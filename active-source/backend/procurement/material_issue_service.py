"""Native prepared raw-material delivery; stock posts only on actual issue."""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from system.models import User,Company,PositionResponsibility,PositionWorkflowResponsibility,OrganizationOperatingAuditRecord
from system.authorization import AuthorizationService
from pfm.formal_employee import formal_employee_queryset
from masterdata.models import MasterDataWriteRequest
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition,transition_business_object
from pde.product_design_service import _canonical_hash,_write_request,_commit_request
from planning.mes_formal_source_admission import formal_datetime_label
from planning.work_order_models import ProductionWorkOrder
from planning import work_order_workshop_receipt_service as workshop_authority
from .models import ProductionMaterialIssue as Issue,ProductionMaterialStockAllocation as Allocation
from . import material_allocation_service as allocations,material_preparation_service as preparation
from .material_stock_authority import actor,quantity,fail
from .material_issue_configuration import ISSUE,RECEIVE,SPECS

ENTITY='ProductionMaterialIssue'
CONTRACT='PCE-PRODUCTION-MATERIAL-ISSUE-V1'
LABELS={'issued':'已发出，待收讫','received':'本笔已全量收讫','discrepancy_pending':'数量差异待核，交付责任未结'}
six=lambda n:format(n,'.6f')
text=allocations.text

def _business_time(raw):
 value=preparation._time(raw)
 if value>timezone.now():fail('MATERIAL_ISSUE_TIME_INVALID','实际发生时间不得晚于服务器登记时间。',400)
 return value

def _qualification(user,code,department_id,owner_id):
 user=actor(user);process,node,duty,_,_=SPECS[code]
 employees=list(formal_employee_queryset(company_id=user.company_id).filter(user_id=user.pk).select_related('position_ref','department_ref')[:2])
 e=employees[0] if len(employees)==1 else None;today=timezone.now().date()
 decision=AuthorizationService.decide(user=user,action_code=code,organization_id=user.company_id,
  business_object={'companyId':user.company_id,'organizationId':user.company_id,'departmentId':department_id,'ownerUserId':owner_id})
 links=list(PositionWorkflowResponsibility.objects.filter(position_id=e.position_ref_id if e else None,active=True,ownership_type='EXECUTOR',
  workflow_node__active=True,workflow_node__process_definition__active=True,workflow_node__process_definition__definition_code=process,
  workflow_node__node_code=node,workflow_node__business_action_code=code,responsibility__code=duty,responsibility__status='ACTIVE',responsibility__is_active=True))
 link=links[0] if len(links)==1 else None
 if (not e or not decision.get('allowed') or not link or not PositionResponsibility.objects.filter(position_id=e.position_ref_id,responsibility=link.responsibility,active=True).exists()
  or not workshop_authority._effective(e.position_ref,today) or not workshop_authority._effective(e.department_ref,today)
  or e.hire_date and e.hire_date>today or e.leave_date and e.leave_date<=today or e.resignation_date and e.resignation_date<=today
  or link.effective_from and link.effective_from>today or link.effective_to and link.effective_to<today):
  fail('MATERIAL_ISSUE_PERMISSION_DENIED','须本人原有效岗位、明确执行权限、职责节点及准确对象范围。',403)
 return user,e,{**decision,'employeeId':e.pk,'positionId':e.position_ref_id,'workflowResponsibilityId':link.pk,'workflowNodeId':link.workflow_node_id,'responsibilityCode':duty}

def _sender(user,allocation_id,*,current=False):
 user=actor(user)
 if type(allocation_id) is not int or allocation_id<=0:fail('MATERIAL_ISSUE_INPUT_INVALID','须选择准确原备料分配。',400)
 row=Allocation.objects.select_for_update().select_related('audit_record','source_transaction','location','lot','warehouse','material').filter(pk=allocation_id,company_id=user.company_id).first()
 if not row:fail('MATERIAL_ALLOCATION_NOT_FOUND','分配不在本企业范围。',404)
 user,d,p,decision=allocations._actor_demand(user,row.demand_id,current=current,action_code=ISSUE)
 _,e,q=_qualification(user,ISSUE,d.department_id,d.created_by_id)
 allocations._stored(row);allocations._stock_scope(user,d,row.source_transaction,action_code=ISSUE)
 return user,e,row,d,p,q

def _current(user,row,d,p):
 allocations._actor_demand(user,d.pk,current=True,action_code=ISSUE)
 tx,source=allocations._stock(user,row.source_transaction_id)
 if source['sourceFingerprint']!=row.source_snapshot['stockFingerprint'] or _canonical_hash(p)!=row.source_snapshot['demandFingerprint']:
  fail('MATERIAL_ISSUE_SOURCE_CHANGED','需求、来源或质量已变化，历史和剩余占用保留待核。')
 preparation._historical_applicability(row,source)
 facts,prepared,prep_version=preparation._history(row)
 from .material_issue_accounting import consumed
 used=consumed([row])[row.pk]
 capacity=allocations._capacity(d,p,tx,source)
 if prepared<used:fail('MATERIAL_ISSUE_PREPARATION_CONFLICT','累计已发量超过有证明的备料量，不能推断剩余。')
 version=_canonical_hash([{'id':x.pk,'status':x.status,'version':x.version,'proof':_canonical_hash(x.source_snapshot),'receipt':_canonical_hash(x.receipt_proof)} for x in Issue.objects.filter(allocation=row).order_by('pk')])
 return tx,source,capacity,facts,min(row.quantity-used,prepared-used),_canonical_hash({'preparationVersion':prep_version,'issues':version})

def _destination(proof,work_order_id,workshop_id,receiver_id):
 for ident in [work_order_id,workshop_id,receiver_id]:
  if type(ident) is not int or ident<=0:fail('MATERIAL_ISSUE_DESTINATION_REQUIRED','须显式选择准确工单、已接单车间及指定人员。',400)
 order=ProductionWorkOrder.objects.select_for_update().filter(pk=work_order_id,company_id=proof['companyId'],production_plan_id=proof['productionPlanId'],usage_purpose='PRODUCTION_USE').first()
 if not order or order.status!='released':fail('MATERIAL_ISSUE_DESTINATION_UNPROVEN','目的工单须同企业、同计划且已正式下达。')
 presented,groups,unassigned,source_ok,receipts=workshop_authority._groups(order)
 group=groups.get(workshop_id);receipt=receipts.get(workshop_id)
 if not source_ok or not group or not group['sourceOk'] or not receipt or not workshop_authority._receipt(receipt)['received']:
  fail('MATERIAL_ISSUE_WORKSHOP_UNPROVEN','本工单与指定车间的正式来源及已接单范围未完整证明。')
 snapshot=order.source_snapshot
 if (snapshot.get('salesOrderItemId')!=proof['salesOrderItemId'] or snapshot.get('demandId')!=proof['parentDemandId']
  or snapshot.get('uomId')!=proof['productionUomId'] or not Decimal('0')<=Decimal(proof['rangeStart'])<Decimal(proof['rangeEnd'])<=order.quantity):
  fail('MATERIAL_ISSUE_PRODUCTION_RANGE_UNPROVEN','需求与工单的订单行、正式生产单位或批准范围不一致，不按同计划猜配。')
 output=proof['manufacturingOutputId']
 if any(x['source'].get('originalManufacturingOutputId')!=output and x['source'].get('effectiveManufacturingOutputId')!=output for x in group['frozenOperations']):
  fail('MATERIAL_ISSUE_VERSION_UNPROVEN','工单车间冻结工程版本不能承接该准确用料来源。')
 receiver=User.objects.defer('password').filter(pk=receiver_id,company_id=proof['companyId'],is_active=True,is_superuser=False).first()
 if not receiver:fail('MATERIAL_ISSUE_RECEIVER_UNPROVEN','指定收方不是本企业有效原业务人员。',403)
 _,e,q=_qualification(receiver,RECEIVE,group['workshop'].department_id,receiver.pk)
 old,_=workshop_authority._qualification(receiver,order,group['workshop'],source_ok=source_ok and group['sourceOk'])
 if e.position_ref.workshop_id!=workshop_id or not old['ready']:
  fail('MATERIAL_ISSUE_RECEIVER_UNPROVEN','指定人没有本车间正式接单职责和准确范围。',403)
 return {'workOrderId':order.pk,'workOrderNo':order.no,'workOrderVersion':order.version,'workOrderSnapshotHash':order.snapshot_hash,
  'workshopId':workshop_id,'workshopName':group['workshop'].name,'receiptId':receipt.pk,'receiptHash':workshop_authority._receipt(receipt)['snapshotHash'],
  'receiverId':receiver.pk,'receiverLabel':e.full_name,'receiverEmployeeId':e.pk,'receiverPositionId':e.position_ref_id,
  'productionRange':[proof['rangeStart'],proof['rangeEnd']],'originalWorkshopSourceHash':_canonical_hash(workshop_authority._source(order,group)),
  'receiverAuthorization':q}

def verify_issue(row):
 p=row.source_snapshot;a=row.audit_record;out=row.outbound_transaction
 allocations._stored(row.allocation)
 frozen={'companyId':row.company_id,'allocationId':row.allocation_id,'workOrderId':row.work_order_id,'workshopId':row.workshop_id,'receiverId':row.receiver_id,
  'quantity':six(row.quantity),'actorId':row.created_by_id,'occurredAt':row.occurred_at.isoformat(),'registeredAt':row.created_at.isoformat(),'intentId':row.intent_id,'outboundTransactionId':out.pk}
 req=MasterDataWriteRequest.objects.filter(pk=p.get('writeRequestId'),organization_id=row.company_id,entity_type=ENTITY,action_code=ISSUE,status='COMMITTED').first()
 stock=p.get('stockPosting',{});allocation=row.allocation
 if (any(p.get(k)!=v for k,v in frozen.items()) or row.intent_hash!=_canonical_hash(p.get('intent')) or a.target_type!=ENTITY or a.target_id!=row.pk
  or a.actor_id!=row.created_by_id or a.action_code!=ISSUE or a.organization_id!=row.company_id or a.after_snapshot.get('issueProof')!=p
  or not a.after_snapshot.get('authorization',{}).get('allowed') or not req or req.result.get('issueId')!=row.pk or req.result.get('auditId')!=a.pk
  or req.request_hash!=_canonical_hash(req.audit_metadata) or p.get('allocationProofHash')!=_canonical_hash(allocation.source_snapshot)
  or out.direction!='OUT' or out.usage_purpose!='PRODUCTION_USE' or out.source_inbound_id!=allocation.source_transaction.source_inbound_id
  or any(getattr(out,k)!=getattr(allocation,k) for k in ['warehouse_id','location_id','lot_id','material_id'])
  or out.quantity!=row.quantity or out.before_quantity-out.after_quantity!=row.quantity or out.operator_account_id!=row.created_by_id
  or stock!={'transactionId':out.pk,'transactionNo':out.transaction_no,'before':str(out.before_quantity),'after':str(out.after_quantity),'quantity':str(out.quantity)}):
  fail('MATERIAL_ISSUE_PROOF_UNPROVEN','发料、OUT、原分配、审计或同次提交证明不一致，不能释放占用或重复扣库。')
 events=list(BusinessStateTransition.objects.filter(object_type=ENTITY,object_id=row.pk).order_by('version','pk'))
 expected=1 if row.status=='issued' else 2
 if len(events)!=expected or row.version!=expected or (events[0].source_state,events[0].target_state,events[0].action_code,events[0].operator_id,events[0].audit_reference)!=('', 'issued',ISSUE,row.created_by_id,f'OrganizationOperatingAuditRecord:{a.pk}'):
  fail('MATERIAL_ISSUE_STATE_UNPROVEN','发料状态与统一转换历史不一致。')
 if row.status=='issued':
  if row.receipt_proof or row.receipt_audit_id:fail('MATERIAL_ISSUE_STATE_UNPROVEN','待收状态出现未经转换的收讫依据。')
 else:
  rp=row.receipt_proof;ra=row.receipt_audit
  r=MasterDataWriteRequest.objects.filter(pk=rp.get('writeRequestId'),organization_id=row.company_id,entity_type=ENTITY,action_code=RECEIVE,status='COMMITTED').first()
  if (row.status not in {'received','discrepancy_pending'} or not ra or ra.target_id!=row.pk or ra.target_type!=ENTITY or ra.actor_id!=row.receiver_id
   or ra.organization_id!=row.company_id or ra.action_code!=RECEIVE or ra.after_snapshot.get('receiptProof')!=rp or rp.get('actorId')!=row.receiver_id
   or rp.get('issueProofHash')!=_canonical_hash(p) or rp.get('status')!=row.status or not ra.after_snapshot.get('authorization',{}).get('allowed')
   or not r or r.result.get('issueId')!=row.pk or r.result.get('auditId')!=ra.pk or r.request_hash!=_canonical_hash(r.audit_metadata)
   or (row.status=='received')!=(rp.get('reportedQuantity')==six(row.quantity))
   or (events[1].source_state,events[1].target_state,events[1].action_code,events[1].operator_id,events[1].audit_reference)!=('issued',row.status,RECEIVE,row.receiver_id,f'OrganizationOperatingAuditRecord:{ra.pk}')):
   fail('MATERIAL_RECEIPT_PROOF_UNPROVEN','收讫/差异事实、指定人、审计及提交证明不一致。')
 return p

def _projection(row):
 verify_issue(row);received=row.quantity if row.status=='received' else Decimal('0')
 return {'issueId':row.pk,'allocationId':row.allocation_id,'demandId':row.allocation.demand_id,'workOrderId':row.work_order_id,'workOrderNo':row.source_snapshot['destination']['workOrderNo'],
  'workshopId':row.workshop_id,'workshopLabel':row.source_snapshot['destination']['workshopName'],'receiverId':row.receiver_id,'receiverLabel':row.source_snapshot['destination']['receiverLabel'],
  'senderId':row.created_by_id,'senderLabel':row.source_snapshot['actorSnapshot']['employeeName'],'materialCode':row.source_snapshot['materialCode'],'materialName':row.source_snapshot['materialName'],
  'lotNo':row.allocation.source_snapshot['stockProof']['lotNo'],'locationId':row.allocation.location_id,'quantity':six(row.quantity),'uomCode':row.source_snapshot['uomCode'],
  'receivedQty':six(received),'pendingReceiptQty':six(row.quantity-received),'reportedQuantity':row.receipt_proof.get('reportedQuantity'),
  'custodianId':row.receiver_id if row.status=='received' else row.created_by_id,'custodyLabel':'车间领用人负责' if row.status=='received' else '发料仓管负责交付保管',
  'statusCode':row.status,'statusLabel':LABELS[row.status],'version':row.version,'sourceFingerprint':_canonical_hash(row.source_snapshot),
  'occurredAt':row.occurred_at.isoformat(),'registeredAt':row.created_at.isoformat(),'occurredAtLabel':formal_datetime_label(row.occurred_at,timezone.get_default_timezone_name()),
  'receipt':row.receipt_proof or None,'outboundTransactionId':row.outbound_transaction_id,'historicalFactOnly':True}

def _rows(allocation):return list(Issue.objects.filter(allocation=allocation).select_related('allocation__audit_record','audit_record','outbound_transaction','receipt_audit').order_by('pk'))

@transaction.atomic
def context(*,user,allocation_id):
 user,e,row,d,p,q=_sender(user,allocation_id)
 history=[_projection(x) for x in _rows(row)];issued=sum((Decimal(x['quantity']) for x in history),Decimal('0'));received=sum((Decimal(x['receivedQty']) for x in history),Decimal('0'))
 facts,prepared,version=preparation._history(row)
 out={'contractVersion':CONTRACT,'allocationId':row.pk,'demandId':d.pk,'demandNo':d.demand_no,'originalAllocatedQty':six(row.quantity),'historicalPreparedQty':six(prepared),
  'issuedQty':six(issued),'receivedQty':six(received),'pendingReceiptQty':six(issued-received),'remainingOccupiedQty':six(row.quantity-issued),'currentIssueableQty':None,
  'uomCode':p['uomCode'],'history':history,'destinations':None,'actionAuthorization':{'issue':{'allowed':False,'blockingReason':None}},'businessWriteCount':0}
 try:
  tx,source,capacity,facts,available,version=_current(user,row,d,p)
  destinations=[];blocks=[]
  receiver_positions=PositionWorkflowResponsibility.objects.filter(active=True,ownership_type='EXECUTOR',workflow_node__active=True,
   workflow_node__business_action_code=RECEIVE,position__company_id=user.company_id).values('position_id')
  for order in ProductionWorkOrder.objects.filter(company_id=user.company_id,production_plan_id=p['productionPlanId'],status='released',usage_purpose='PRODUCTION_USE').order_by('pk'):
   # Candidates are proven by the same authority as the subsequent write.
   for employee in formal_employee_queryset(company_id=user.company_id).filter(position_ref_id__in=receiver_positions,position_ref__workshop__isnull=False).select_related('position_ref','user'):
    try:
     destination=_destination(p,order.pk,employee.position_ref.workshop_id,employee.user_id)
     destinations.append({**destination,'expectedDestinationFingerprint':_canonical_hash(destination)})
    except Exception as error:
     if not hasattr(error,'code'):raise
     blocks.append({'workOrderId':order.pk,'code':error.code,'message':str(error)})
  out.update(currentIssueableQty=six(available),currentStockQty=capacity['physicalQty'],sourceFingerprint=source['sourceFingerprint'],allocationProofHash=_canonical_hash(row.source_snapshot),
   dimensionFingerprint=capacity['dimensionFingerprint'],collectionVersion=version,destinations=destinations,destinationBlockingReasons=blocks)
  out['actionAuthorization']['issue']={'allowed':available>0 and bool(destinations),'blockingReason':None if available>0 and destinations else {'code':'MATERIAL_ISSUE_NO_AVAILABLE_PREPARED_DESTINATION','message':'尚无有证明的可发备料量或合法指定目的地。'}}
 except Exception as error:
  if not hasattr(error,'code'):raise
  out['actionAuthorization']['issue']['blockingReason']={'code':error.code,'message':str(error)}
 return out

def _request(user,code,payload,key):
 text(key);text(payload.get('reason'),300);text(payload.get('intentId'),120)
 return _write_request(user=user,action_code=code,entity_type=ENTITY,key=key,request_body={'actorId':user.pk,**payload})

def _result(user,request):
 row=Issue.objects.select_related('allocation__audit_record','audit_record','outbound_transaction','receipt_audit').filter(pk=request.result.get('issueId'),company_id=user.company_id).first()
 if not row or user.pk not in {row.created_by_id,row.receiver_id} or request.audit_metadata.get('actorId')!=user.pk:fail('MATERIAL_ISSUE_RESULT_NOT_FOUND','同次动作不属于本办理人。',404)
 verify_issue(row)
 return {**request.result,'businessWriteCount':0,'idempotent':True,'historicalReceiptOnly':True,'executionAuthorizedByResult':False}

@transaction.atomic
def issue(*,user,payload,key):
 required={'allocationId','workOrderId','workshopId','receiverId','quantity','occurredAt','basis','intentId','expectedCollectionVersion','expectedAllocationProofHash','expectedSourceFingerprint','expectedDimensionFingerprint','expectedDestinationFingerprint','reason'}
 if not isinstance(payload,dict) or set(payload)!=required:fail('MATERIAL_ISSUE_INPUT_INVALID','须明确原备料、准确目的地、实际交出时间/数量/依据及预期版本，不接受自报资格或状态。',400)
 user,e,row,d,p,q=_sender(user,payload['allocationId']);Company.objects.select_for_update().get(pk=user.company_id)
 request,created,_=_request(user,ISSUE,payload,key)
 if not created and request.status=='COMMITTED':return _result(user,request)
 qty=quantity(payload['quantity'],6);occurred=_business_time(payload['occurredAt']);basis=text(payload['basis'],500)
 meaning={k:payload[k] for k in ['allocationId','workOrderId','workshopId','receiverId','intentId']};meaning.update(actorId=user.pk,quantity=six(qty),occurredAt=occurred.isoformat(),basis=basis)
 old=Issue.objects.filter(company_id=user.company_id,intent_id=payload['intentId']).first()
 if old:
  verify_issue(old)
  if old.intent_hash!=_canonical_hash(meaning) or old.created_by_id!=user.pk:fail('MATERIAL_ISSUE_INTENT_CONFLICT','原发料意图已有其他事实，不覆盖。')
  transaction.set_rollback(True);return {'issueId':old.pk,'quantity':six(old.quantity),'auditId':old.audit_record_id,'businessWriteCount':0,'idempotent':True,'historicalReceiptOnly':True,'executionAuthorizedByResult':False}
 tx,source,capacity,facts,available,version=_current(user,row,d,p)
 destination=_destination(p,payload['workOrderId'],payload['workshopId'],payload['receiverId'])
 if (payload['expectedCollectionVersion']!=version or payload['expectedAllocationProofHash']!=_canonical_hash(row.source_snapshot)
  or payload['expectedSourceFingerprint']!=source['sourceFingerprint'] or payload['expectedDimensionFingerprint']!=capacity['dimensionFingerprint']
  or payload['expectedDestinationFingerprint']!=_canonical_hash(destination)):fail('MATERIAL_ISSUE_VERSION_CONFLICT','来源、目的地、库存或办理集合变化；先查同次结果，不自动重放。')
 if qty>available:fail('MATERIAL_ISSUE_QUANTITY_EXCEEDED','超过本分配已备且尚未发出的准确数量。')
 if qty!=qty.quantize(Decimal(1).scaleb(-tx.material.base_uom.decimal_places)):fail('MATERIAL_ISSUE_UNIT_PRECISION','数量不符合原单位精度，不舍入。')
 if not facts or occurred<max(preparation._time(x['registeredAt']) for x in facts):fail('MATERIAL_ISSUE_TIME_INVALID','实际交出不得早于所采用备料的登记，不补造历史。')
 if e.created_at>occurred or e.updated_at>occurred:fail('MATERIAL_ISSUE_ACTOR_HISTORY_PENDING','实际发生时人员适用证明待核。')
 link=PositionWorkflowResponsibility.objects.get(pk=q['workflowResponsibilityId'])
 if link.effective_from and link.effective_from>occurred.date() or link.effective_to and link.effective_to<occurred.date():fail('MATERIAL_ISSUE_ACTOR_HISTORY_PENDING','实际发出时执行职责适用依据待核。')
 from .inventory_posting import post_material_issue_stock
 posting=post_material_issue_stock(allocation=row,quantity=qty,employee=e,user=user,occurred_at=occurred)
 registered=timezone.now();actor_snapshot={'employeeId':e.pk,'employeeName':e.full_name,'positionId':e.position_ref_id,'authorization':q}
 proof={**meaning,'companyId':user.company_id,'registeredAt':registered.isoformat(),'contractVersion':CONTRACT,'writeRequestId':request.pk,'intent':meaning,
  'allocationProofHash':_canonical_hash(row.source_snapshot),'sourceFingerprint':source['sourceFingerprint'],'preparationFacts':[{'id':x['preparationId'],'quantity':x['quantity'],'auditId':x['auditId']} for x in facts],
  'materialCode':tx.material.code,'materialName':tx.material.name,'uomCode':p['uomCode'],'actorSnapshot':actor_snapshot,'destination':destination,
  'outboundTransactionId':posting.pk,'stockPosting':{'transactionId':posting.pk,'transactionNo':posting.transaction_no,'before':str(posting.before_quantity),'after':str(posting.after_quantity),'quantity':str(posting.quantity)}}
 audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=ISSUE,target_type=ENTITY,target_id=0,target_label=d.demand_no,reason=payload['reason'],after_snapshot={'issueProof':proof,'authorization':q})
 result_row=create_business_object_with_initial_state(model=Issue,initial_state='issued',company_id=user.company_id,allocation=row,work_order_id=destination['workOrderId'],workshop_id=destination['workshopId'],receiver_id=destination['receiverId'],quantity=qty,
  occurred_at=occurred,created_at=registered,created_by=user,source_snapshot=proof,intent_id=payload['intentId'],intent_hash=_canonical_hash(meaning),audit_record=audit,outbound_transaction=posting)
 audit.target_id=result_row.pk;audit.save(update_fields=['target_id'])
 record_projected_business_transition(object_type=ENTITY,object_id=result_row.pk,source_state='',target_state='issued',action_code=ISSUE,operator=user,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','issued')})
 result={'issueId':result_row.pk,'allocationId':row.pk,'quantity':six(qty),'statusCode':'issued','statusLabel':LABELS['issued'],'version':1,'outboundTransactionId':posting.pk,'auditId':audit.pk,'businessWriteCount':1}
 _commit_request(request,result);return result

def _recipient_row(user,issue_id):
 user=actor(user)
 if type(issue_id) is not int or issue_id<=0:fail('MATERIAL_RECEIPT_INPUT_INVALID','须准确发料事实。',400)
 row=Issue.objects.select_for_update().select_related('allocation__audit_record','audit_record','outbound_transaction','receipt_audit','workshop').filter(pk=issue_id,company_id=user.company_id,receiver=user).first()
 if not row:fail('MATERIAL_ISSUE_NOT_FOUND','发料不属于本企业当前指定收方。',404)
 user,e,q=_qualification(user,RECEIVE,row.workshop.department_id,user.pk)
 if e.position_ref.workshop_id!=row.workshop_id:fail('MATERIAL_RECEIPT_SCOPE_DENIED','本人当前岗位不属于本笔指定车间。',403)
 verify_issue(row);return user,e,row,q

@transaction.atomic
def receipt_context(*,user,issue_id):
 user,e,row,q=_recipient_row(user,issue_id);out=_projection(row);out.update(contractVersion=CONTRACT,businessWriteCount=0)
 allowed=row.status=='issued';block=None
 try:
  d=row.allocation.demand;p,_=allocations.demand_authority.verify_demand(d,current=False)
  source,_=allocations.demand_authority.resolve_source(actor=user,plan=allocations.ProductionPlan.objects.get(pk=p['productionPlanId']),selection=p)
  if _canonical_hash(source)!=_canonical_hash(p):fail('MATERIAL_RECEIPT_SOURCE_CHANGED','当前生产来源变化，原交付责任保留待核。')
  _,stock=allocations._stock(user,row.allocation.source_transaction_id)
  destination=_destination(p,row.work_order_id,row.workshop_id,row.receiver_id)
  if stock['sourceFingerprint']!=row.source_snapshot['sourceFingerprint'] or _canonical_hash(destination)!=_canonical_hash(row.source_snapshot['destination']):fail('MATERIAL_RECEIPT_SOURCE_CHANGED','原料质量、目的地或指定资格发生变化，交付保留待核。')
 except Exception as error:
  if not hasattr(error,'code'):raise
  allowed=False;block={'code':error.code,'message':str(error)}
 if row.status!='issued':block={'code':'MATERIAL_RECEIPT_ALREADY_DECIDED','message':'本笔已收讫或差异待核，不自动重办或处置部分收讫。'}
 out['actionAuthorization']={'receive':{'allowed':allowed,'blockingReason':block}};return out

@transaction.atomic
def receive(*,user,payload,key):
 required={'issueId','quantity','occurredAt','basis','intentId','expectedVersion','expectedSourceFingerprint','reason'}
 if not isinstance(payload,dict) or set(payload)!=required:fail('MATERIAL_RECEIPT_INPUT_INVALID','须准确发料、核对数量/时间/依据及版本，不接受自报身份或状态。',400)
 user,e,row,q=_recipient_row(user,payload['issueId']);Company.objects.select_for_update().get(pk=user.company_id)
 request,created,_=_request(user,RECEIVE,payload,key)
 if not created and request.status=='COMMITTED':return _result(user,request)
 qty=quantity(payload['quantity'],6,zero=True);occurred=_business_time(payload['occurredAt']);basis=text(payload['basis'],500)
 meaning={'issueId':row.pk,'reportedQuantity':six(qty),'occurredAt':occurred.isoformat(),'basis':basis,'intentId':payload['intentId'],'actorId':user.pk}
 if row.receipt_proof:
  if row.receipt_proof.get('intent')!=meaning:fail('MATERIAL_RECEIPT_ALREADY_DECIDED','本笔已登记收讫或差异，不覆盖旧决定。')
  transaction.set_rollback(True);return {'issueId':row.pk,'statusCode':row.status,'statusLabel':LABELS[row.status],'businessWriteCount':0,'idempotent':True,'historicalReceiptOnly':True,'executionAuthorizedByResult':False}
 ctx=receipt_context(user=user,issue_id=row.pk)
 if not ctx['actionAuthorization']['receive']['allowed']:
  b=ctx['actionAuthorization']['receive']['blockingReason'];fail(b['code'],b['message'])
 if type(payload['expectedVersion']) is not int or payload['expectedVersion']!=row.version or payload['expectedSourceFingerprint']!=_canonical_hash(row.source_snapshot):fail('MATERIAL_RECEIPT_VERSION_CONFLICT','发料版本或来源变化，先查原动作。')
 if occurred<row.created_at or e.created_at>occurred or e.updated_at>occurred:fail('MATERIAL_RECEIPT_TIME_INVALID','收讫/核对时间早于已登记发出或人员发生时资格缺证。')
 link=PositionWorkflowResponsibility.objects.get(pk=q['workflowResponsibilityId'])
 if link.effective_from and link.effective_from>occurred.date() or link.effective_to and link.effective_to<occurred.date():fail('MATERIAL_RECEIPT_TIME_INVALID','实际收讫时执行职责适用依据待核。')
 if qty!=qty.quantize(Decimal(1).scaleb(-row.allocation.uom.decimal_places)):fail('MATERIAL_RECEIPT_UNIT_PRECISION','收方核对量不符合原单位精度。')
 target='received' if qty==row.quantity else 'discrepancy_pending'
 proof={**meaning,'registeredAt':timezone.now().isoformat(),'status':target,'issueProofHash':_canonical_hash(row.source_snapshot),'writeRequestId':request.pk,'intent':meaning,'authorization':q,'employeeId':e.pk}
 audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=RECEIVE,target_type=ENTITY,target_id=row.pk,target_label=str(row.pk),reason=payload['reason'],after_snapshot={'receiptProof':proof,'authorization':q})
 row.receipt_proof=proof;row.receipt_audit=audit;row._material_receipt_authorized=True;row.save(update_fields=['receipt_proof','receipt_audit'])
 transition_business_object(business_object=row,object_type=ENTITY,source_state='issued',target_state=target,action_code=RECEIVE,operator=user,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('issued','received'),('issued','discrepancy_pending')})
 result={'issueId':row.pk,'statusCode':target,'statusLabel':LABELS[target],'version':row.version,'reportedQuantity':six(qty),'receivedQty':six(qty) if target=='received' else '0.000000','pendingReceiptQty':'0.000000' if target=='received' else six(row.quantity),'auditId':audit.pk,'businessWriteCount':1}
 _commit_request(request,result);return result

@transaction.atomic
def own_receipts(*,user):
 user=actor(user);e=workshop_authority._employees(user)[0]
 if not e or not e.position_ref.workshop_id:fail('MATERIAL_RECEIPT_SCOPE_DENIED','须本车间有效原领用职责人员。',403)
 _qualification(user,RECEIVE,e.department_ref_id,user.pk)
 data=[receipt_context(user=user,issue_id=pk) for pk in Issue.objects.filter(company_id=user.company_id,receiver=user,workshop_id=e.position_ref.workshop_id).order_by('pk').values_list('pk',flat=True)]
 return {'contractVersion':CONTRACT,'rows':data,'count':len(data),'businessWriteCount':0,'scope':'仅本企业本人指定原料交付，不等于全车间或全系统待办数'}

@transaction.atomic
def result_query(*,user,action,key):
 user=actor(user);text(key)
 if action not in {ISSUE,RECEIVE}:fail('MATERIAL_ISSUE_INPUT_INVALID','须准确原业务动作。',400)
 # Query grants no current execution qualification; only original actor's committed action.
 req=MasterDataWriteRequest.objects.filter(organization_id=user.company_id,entity_type=ENTITY,action_code=action,idempotency_key=key,status='COMMITTED').first()
 if req and req.audit_metadata.get('actorId')!=user.pk:fail('MATERIAL_ISSUE_RESULT_NOT_FOUND','同次动作不属于本人。',404)
 return {'resultState':'COMMITTED' if req else 'UNKNOWN','result':_result(user,req) if req else None,'automaticReplayAllowed':False,'businessWriteCount':0}
