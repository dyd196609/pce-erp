"""Explicit raw-material reservations; every unknown source continues to hold quota."""
from decimal import Decimal
from django.db import transaction
from system.models import Company,OrganizationOperatingAuditRecord,PositionResponsibility,PositionWorkflowResponsibility
from system.authorization import AuthorizationService
from pfm.formal_employee import formal_employee_queryset
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition
from pde.product_design_service import _canonical_hash,_write_request,_commit_request
from masterdata.models import MasterDataWriteRequest
from planning import material_demand_service as demand_authority
from planning.models import Demand,ProductionPlan
from .models import ProductionMaterialStockAllocation as Allocation,InventoryTransaction,InventoryBalance,OrderStockAllocation
from .material_allocation_configuration import PERMISSION,PROCESS,NODE,DUTY
from .material_stock_authority import actor,quantity,stock_proof,fail,PURPOSE

CONTRACT='PCE-PRODUCTION-MATERIAL-STOCK-ALLOCATION-V1'
ENTITY='ProductionMaterialStockAllocation'
def text(raw,size=160):
 if not isinstance(raw,str) or not 1<=len(raw.strip())<=size:fail('MATERIAL_ALLOCATION_INPUT_INVALID','须提供明确原意图、请求键及理由。',400)
 return raw.strip()
def _actor_demand(user,demand_id,*,current=True,action_code=PERMISSION):
 if action_code==PERMISSION:process,node_code=PROCESS,NODE
 else:
  from .material_preparation_configuration import PERMISSION as PREPARE,PROCESS as PREPARE_PROCESS,NODE as PREPARE_NODE
  if action_code==PREPARE:process,node_code=PREPARE_PROCESS,PREPARE_NODE
  else:
   from .material_issue_configuration import ISSUE,SPECS
   if action_code!=ISSUE:fail('MATERIAL_ACTION_UNKNOWN','未注册的原料动作。',403)
   process,node_code=SPECS[ISSUE][:2]
 user=actor(user)
 if type(demand_id) is not int or demand_id<=0:fail('MATERIAL_DEMAND_INPUT_INVALID','须准确选择已确认需求。',400)
 d=Demand.objects.select_related('department','material').filter(pk=demand_id,source_type=demand_authority.SOURCE,department__company_id=user.company_id).first()
 if not d:fail('MATERIAL_DEMAND_NOT_FOUND','需求不在当前范围。',404)
 decision=AuthorizationService.decide(user=user,action_code=action_code,organization_id=user.company_id,business_object={'companyId':user.company_id,'organizationId':user.company_id,'departmentId':d.department_id,'ownerUserId':d.created_by_id})
 if not decision.get('allowed'):fail('MATERIAL_ALLOCATION_PERMISSION_DENIED','没有本需求原范围的原料分配资格。',403)
 e=formal_employee_queryset(company_id=user.company_id).filter(user_id=user.pk).first()
 node=PositionWorkflowResponsibility.objects.filter(position_id=e.position_ref_id if e else None,active=True,workflow_node__active=True,
  workflow_node__process_definition__active=True,workflow_node__process_definition__definition_code=process,workflow_node__node_code=node_code,
  workflow_node__business_action_code=action_code,responsibility__code=DUTY,responsibility__status='ACTIVE',responsibility__is_active=True).first()
 if not e or not node or not PositionResponsibility.objects.filter(position_id=e.position_ref_id,responsibility=node.responsibility,active=True).exists():fail('MATERIAL_ALLOCATION_DUTY_REQUIRED','须原在职仓管及有效仓库出入库职责、动作节点。',403)
 for code in ['warehouse.inventory.read','warehouse.inventory_transaction.read']:
  if not AuthorizationService.decide(user=user,action_code=code,organization_id=user.company_id,business_object={'companyId':user.company_id,'organizationId':user.company_id,'departmentId':d.department_id,'ownerUserId':d.created_by_id}).get('allowed'):fail('MATERIAL_STOCK_READ_PERMISSION_REQUIRED','原库存读取资格未落实，不能按空库存办理。',403)
 proof,_=demand_authority.verify_demand(d,current=False)
 if d.status!='confirmed':fail('MATERIAL_DEMAND_NOT_CONFIRMED','仅已确认正式生产用料需求可分配。')
 if current:
  plan=ProductionPlan.objects.get(pk=proof['productionPlanId'],planning_requirement__demand__department__company_id=user.company_id)
  # The newly approved narrow warehouse context consumes the original source
  # authority without granting the whole planning list/read permission.
  source,_=demand_authority.resolve_source(actor=user,plan=plan,selection=proof)
  if _canonical_hash(source)!=_canonical_hash(proof):fail('MATERIAL_DEMAND_SOURCE_CHANGED','需求来源或生产范围已变化，原占用保留待核。')
 return user,d,proof,{**decision,'workflowNodeId':node.workflow_node_id,'workflowResponsibilityId':node.pk,'actorEmployeeId':e.pk}
def _stored(row):
 p=row.source_snapshot;a=row.audit_record
 fields={'companyId':row.company_id,'demandId':row.demand_id,'sourceTransactionId':row.source_transaction_id,'warehouseId':row.warehouse_id,'locationId':row.location_id,'lotId':row.lot_id,'materialId':row.material_id,'uomId':row.uom_id,'usagePurpose':row.usage_purpose,'quantity':format(row.quantity,'.6f'),'intentId':row.intent_id,'actorId':row.created_by_id,'version':row.version,'status':row.status}
 request=MasterDataWriteRequest.objects.filter(pk=p.get('writeRequestId'),organization_id=row.company_id,entity_type=ENTITY,action_code=PERMISSION,status='COMMITTED').first()
 if any(p.get(k)!=v for k,v in fields.items()) or a.target_type!=ENTITY or a.target_id!=row.pk or a.organization_id!=row.company_id or a.actor_id!=row.created_by_id or a.action_code!=PERMISSION or a.after_snapshot.get('allocationProof')!=p or not a.after_snapshot.get('authorization',{}).get('allowed') or row.intent_hash!=_canonical_hash(p.get('intent')) or not request or request.result.get('allocationId')!=row.pk or request.result.get('auditId')!=a.pk or request.request_hash!=_canonical_hash(request.audit_metadata):fail('MATERIAL_OCCUPANCY_PROOF_UNPROVEN','占用关系与原审计/提交证明不一致，不能把额度释放为0。')
 chain=list(BusinessStateTransition.objects.filter(object_type=ENTITY,object_id=row.pk))
 if len(chain)!=1 or chain[0].source_state!='' or chain[0].target_state!='occupied' or chain[0].action_code!=PERMISSION or chain[0].operator_id!=row.created_by_id or chain[0].audit_reference!=f'OrganizationOperatingAuditRecord:{a.pk}':fail('MATERIAL_OCCUPANCY_STATE_UNPROVEN','占用缺原统一状态证明，保持待核。')
 return fields
def _rows(demand):
 rows=list(Allocation.objects.filter(company_id=demand.department.company_id,demand=demand).select_related('audit_record'))
 for row in rows:_stored(row)
 return rows
def _demand_version(rows):return _canonical_hash([{'id':x.pk,'quantity':format(x.quantity,'.6f'),'version':x.version,'status':x.status} for x in rows])
def _stock(user,tx_id):
 tx=InventoryTransaction.objects.select_related('source_inbound__source_inspection__source_receipt__source_purchase_order','warehouse','location','lot','material__base_uom').filter(pk=tx_id,warehouse__company_id=user.company_id).first()
 if not tx:fail('MATERIAL_STOCK_NOT_FOUND','库存来源不存在或不在原企业范围。',404)
 return tx,stock_proof(tx)
def _stock_scope(user,d,tx,*,action_code=PERMISSION):
 decision=AuthorizationService.decide(user=user,action_code=action_code,organization_id=tx.warehouse.company_id,business_object={'companyId':tx.warehouse.company_id,'organizationId':tx.warehouse.company_id,'warehouseId':tx.warehouse_id,'departmentId':d.department_id,'ownerUserId':d.created_by_id})
 if not decision.get('allowed'):fail('MATERIAL_STOCK_SCOPE_DENIED','该仓储来源不在原授权范围。',403)
def _capacity(d,proof,tx,source):
 i=source['identity']
 if i['materialId']!=d.material_id or i['uomId']!=proof['uomId'] or i['companyId']!=proof['companyId']:fail('MATERIAL_STOCK_UNIT_MISMATCH','需求与库存不是同一原料、单位及企业，不换算或猜配。')
 dimension={'company_id':i['companyId'],'warehouse_id':i['warehouseId'],'location_id':i['locationId'],'lot_id':i['lotId'],'material_id':i['materialId'],'usage_purpose':i['usagePurpose']}
 held=list(Allocation.objects.select_for_update().filter(**dimension).select_related('audit_record'))
 # Never filter pending/invalid source projections out of an occupied relation.
 for row in held:_stored(row)
 if OrderStockAllocation.objects.filter(company_id=i['companyId'],status='active',source_transaction__warehouse_id=i['warehouseId'],source_transaction__location_id=i['locationId'],source_transaction__lot_id=i['lotId'],source_transaction__material_id=i['materialId']).exists():fail('MATERIAL_STOCK_OTHER_OCCUPANCY_PENDING','此原料维度出现其他订单占用，不能忽略或重复使用。')
 balance=InventoryBalance.objects.select_for_update().filter(warehouse_id=i['warehouseId'],location_id=i['locationId'],lot_id=i['lotId'],material_id=i['materialId'],usage_purpose=PURPOSE).first()
 if not balance:fail('MATERIAL_STOCK_BALANCE_UNPROVEN','未找到同仓/库位/批次/用途的原库存余额。')
 if InventoryTransaction.objects.filter(warehouse_id=i['warehouseId'],location_id=i['locationId'],lot_id=i['lotId'],material_id=i['materialId'],usage_purpose=PURPOSE,direction='OUT',material_issue__isnull=True).exists():
  fail('MATERIAL_STOCK_OUTBOUND_UNPROVEN','本库存维度存在缺正式发料关系的OUT，保留占用待核，不按余额放行。')
 from .material_issue_accounting import consumed
 issued=consumed(held)
 total=sum((x.quantity-issued[x.pk] for x in held),Decimal('0'));origin=sum((x.quantity for x in held if x.source_transaction_id==tx.pk),Decimal('0'))
 if total>balance.quantity or origin>tx.quantity:fail('MATERIAL_STOCK_OCCUPANCY_CONFLICT','已登记占用超过当前可证明实物，保留占用待核。')
 snapshot={'balanceId':balance.pk,'balanceQuantity':str(balance.quantity),'held':[{'id':x.pk,'quantity':format(x.quantity,'.6f'),'version':x.version,**({'issuedQty':format(issued[x.pk],'.6f')} if issued[x.pk] else {})} for x in held]}
 return {'physicalQty':str(balance.quantity),'dimensionOccupiedQty':format(total,'.6f'),'sourceOccupiedQty':format(origin,'.6f'),'sourceUnoccupiedQty':format(min(balance.quantity-total,tx.quantity-origin),'.6f'),'dimensionFingerprint':_canonical_hash(snapshot)}
def _projection(row):
 frozen=_stored(row)
 try:
  user,d,p,_=_actor_demand(row.created_by_id and row.created_by,row.demand_id,current=True)
  tx,now=_stock(user,row.source_transaction_id)
  if row.source_snapshot['stockFingerprint']!=now['sourceFingerprint'] or row.source_snapshot['demandFingerprint']!=_canonical_hash(p):fail('MATERIAL_ALLOCATION_SOURCE_CHANGED','原占用依据已变化。')
  current='CURRENT';reason=None
 except Exception as error:
  if not hasattr(error,'code'):raise
  current='PENDING_REVALIDATION';reason={'code':error.code,'message':str(error)}
 from .material_issue_accounting import consumed
 from .models import ProductionMaterialIssue
 issued=consumed([row])[row.pk]
 received=sum((x.quantity for x in ProductionMaterialIssue.objects.filter(allocation=row,status='received')),Decimal('0'))
 return {**frozen,'allocationId':row.pk,'statusLabel':'已确认分配，已发另列' if issued else '已确认占用','currentSourceStatus':current,'blockingReason':reason,
  'quotaStillHeld':row.quantity>issued,'preparedQty':None,'issuedQty':format(issued,'.6f'),'receivedQty':format(received,'.6f'),
  'pendingReceiptQty':format(issued-received,'.6f'),'remainingOccupiedQty':format(row.quantity-issued,'.6f')}

@transaction.atomic
def context(*,user,demand_id,source_id=None):
 user,d,p,decision=_actor_demand(user,demand_id,current=False);rows=_rows(d);occupied=sum((x.quantity for x in rows),Decimal('0'))
 projections=[_projection(x) for x in rows]
 result={'contractVersion':CONTRACT,'demandId':d.pk,'demandNo':d.demand_no,'requiredQty':d.quantity_text,'materialId':d.material_id,'uomId':p['uomId'],'uomCode':p['uomCode'],'productionRange':[p['rangeStart'],p['rangeEnd']],
  'recordedOccupiedQty':format(occupied,'.6f'),'unallocatedDemandQty':format(d.required_qty-occupied,'.6f'),'demandAllocationVersion':_demand_version(rows),'demandFingerprint':_canonical_hash(p),'allocations':projections,
  'physicalStockQty':None,'qualityAvailableQty':None,'sourceUnoccupiedQty':None,'preparedQty':None,
  'issuedQty':format(sum((Decimal(x['issuedQty']) for x in projections),Decimal('0')),'.6f'),
  'preparedStatus':'NOT_IN_SCOPE','issuedStatus':'NATIVE_ISSUE_CONTRACT','currentStateSource':'server','businessWriteCount':0}
 try:_actor_demand(user,demand_id,current=True)
 except Exception as e:
  if not hasattr(e,'code'):raise
  return {**result,'sourceStatus':'PENDING_REVALIDATION','blockingReason':{'code':e.code,'message':str(e)},'sourceCandidates':None}
 if source_id is not None:
  if type(source_id) is not int or source_id<=0:fail('MATERIAL_STOCK_INPUT_INVALID','须准确选择库存流水。',400)
  tx,stock=_stock(user,source_id);_stock_scope(user,d,tx);capacity=_capacity(d,p,tx,stock)
  return {**result,'sourceStatus':'VERIFIED','sourceTransactionId':tx.pk,'stockFingerprint':stock['sourceFingerprint'],'stockIdentity':stock['identity'],**capacity,'physicalStockQty':capacity['physicalQty'],'qualifiedInboundQty':str(tx.quantity),'qualityAvailableQty':format(min(Decimal(capacity['physicalQty']),tx.quantity),'.6f')}
 candidates=[]
 for tx in InventoryTransaction.objects.filter(warehouse__company_id=user.company_id,material_id=d.material_id,direction='IN').order_by('pk'):
  try:
   tx,stock=_stock(user,tx.pk);_stock_scope(user,d,tx);capacity=_capacity(d,p,tx,stock)
   candidates.append({'sourceTransactionId':tx.pk,'qualification':'VERIFIED','stockIdentity':stock['identity'],'stockFingerprint':stock['sourceFingerprint'],**capacity})
  except Exception as e:
   if not hasattr(e,'code'):raise
   candidates.append({'sourceTransactionId':tx.pk,'qualification':'PENDING','sourceUnoccupiedQty':None,'error':{'code':e.code,'message':str(e)}})
 return {**result,'sourceStatus':'CANDIDATES_RECORDED' if candidates else 'NO_PROVEN_SOURCE','sourceCandidates':candidates,'candidateRecordCount':len(candidates),'noSourceIsNotQuantityZero':True}

@transaction.atomic
def confirm(*,user,payload,key):
 required={'demandId','sourceTransactionId','quantity','intentId','expectedDemandAllocationVersion','expectedDemandFingerprint','expectedStockFingerprint','expectedDimensionFingerprint','reason'}
 if not isinstance(payload,dict) or set(payload)!=required:fail('MATERIAL_ALLOCATION_INPUT_INVALID','须原准确需求/来源、数量、意图及预期版本，不接受自报身份、状态或范围。',400)
 text(key);text(payload['reason'],300);intent=text(payload['intentId'],120);user,d,p,decision=_actor_demand(user,payload['demandId'],current=False)
 Company.objects.select_for_update().get(pk=user.company_id)
 request,created,_=_write_request(user=user,action_code=PERMISSION,entity_type=ENTITY,key=key,request_body={'actorId':user.pk,**payload})
 if not created and request.status=='COMMITTED':return _own_result(user,request)
 qty=quantity(payload['quantity'],6)
 meaning={'demandId':d.pk,'sourceTransactionId':payload['sourceTransactionId'],'quantity':format(qty,'.6f'),'actorId':user.pk,'intentId':intent}
 existing=Allocation.objects.filter(company_id=user.company_id,intent_id=intent).select_related('audit_record').first()
 if existing:
  _stored(existing)
  if existing.created_by_id!=user.pk or existing.intent_hash!=_canonical_hash(meaning):fail('MATERIAL_INTENT_CONFLICT','原意图已用于其他数量/来源，不覆盖或重复占用。')
  transaction.set_rollback(True);return {'allocationId':existing.pk,'auditId':existing.audit_record_id,'quantity':format(existing.quantity,'.6f'),'idempotent':True,'historicalReceiptOnly':True,'quotaStillHeld':True,'businessWriteCount':0}
 _actor_demand(user,d.pk,current=True)
 rows=_rows(d)
 if payload['expectedDemandAllocationVersion']!=_demand_version(rows) or payload['expectedDemandFingerprint']!=_canonical_hash(p):fail('MATERIAL_ALLOCATION_VERSION_CONFLICT','需求依据或已占用版本变化，原意图不可自动重放。')
 if type(payload['sourceTransactionId']) is not int:fail('MATERIAL_STOCK_INPUT_INVALID','须准确库存来源。',400)
 tx,stock=_stock(user,payload['sourceTransactionId']);_stock_scope(user,d,tx);capacity=_capacity(d,p,tx,stock)
 if payload['expectedStockFingerprint']!=stock['sourceFingerprint'] or payload['expectedDimensionFingerprint']!=capacity['dimensionFingerprint']:fail('MATERIAL_STOCK_VERSION_CONFLICT','来源或同库存维度占用已变化，请查询原动作。')
 held=sum((x.quantity for x in rows),Decimal('0'))
 if qty!=qty.quantize(Decimal(1).scaleb(-tx.material.base_uom.decimal_places)):fail('MATERIAL_ALLOCATION_UNIT_PRECISION','分配数量不符合原单位精度，6位字段不扩大单位规则。')
 if qty>d.required_qty-held:fail('MATERIAL_DEMAND_ALLOCATION_EXCEEDED','分配超出准确需求尚未覆盖量。')
 if qty>Decimal(capacity['sourceUnoccupiedQty']):fail('MATERIAL_STOCK_ALLOCATION_EXCEEDED','分配超出来源或同实际库存维度尚可分配量。')
 i=stock['identity'];snapshot={**i,**meaning,'contractVersion':CONTRACT,'version':1,'status':'occupied','demandFingerprint':_canonical_hash(p),'stockFingerprint':stock['sourceFingerprint'],'stockProof':stock['proof'],'productionRange':[p['rangeStart'],p['rangeEnd']],'writeRequestId':request.pk,'intent':meaning}
 event=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=PERMISSION,target_type=ENTITY,target_id=0,target_label=d.demand_no,reason=payload['reason'],after_snapshot={'allocationProof':snapshot,'authorization':decision})
 row=create_business_object_with_initial_state(model=Allocation,initial_state='occupied',company_id=user.company_id,demand=d,source_transaction=tx,warehouse_id=i['warehouseId'],location_id=i['locationId'],lot_id=i['lotId'],material_id=i['materialId'],uom_id=i['uomId'],usage_purpose=PURPOSE,quantity=qty,intent_id=intent,intent_hash=_canonical_hash(meaning),source_snapshot=snapshot,created_by=user,audit_record=event)
 event.target_id=row.pk;event.save(update_fields=['target_id'])
 record_projected_business_transition(object_type=ENTITY,object_id=row.pk,source_state='',target_state='occupied',action_code=PERMISSION,operator=user,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',allowed_transitions={('','occupied')})
 result={'allocationId':row.pk,'demandId':d.pk,'auditId':event.pk,'quantity':format(qty,'.6f'),'uomId':i['uomId'],'status':'occupied','statusLabel':'已确认占用','quotaStillHeld':True,'businessWriteCount':1}
 _commit_request(request,result);return result
def _own_result(user,request):
 row=Allocation.objects.select_related('audit_record').filter(pk=request.result.get('allocationId'),company_id=user.company_id,created_by=user).first()
 if not row:fail('MATERIAL_ALLOCATION_RESULT_NOT_FOUND','同次动作不属于当前办理人。',404)
 _stored(row);return {**request.result,'businessWriteCount':0,'idempotent':True,'historicalReceiptOnly':True,'executionAuthorizedByResult':False}
def result_query(*,user,demand_id,key):
 user,d,_,_=_actor_demand(user,demand_id,current=False);text(key)
 request=MasterDataWriteRequest.objects.filter(organization_id=user.company_id,entity_type=ENTITY,action_code=PERMISSION,idempotency_key=key,status='COMMITTED').first()
 if request and request.result.get('demandId')!=d.pk:fail('MATERIAL_ALLOCATION_RESULT_NOT_FOUND','同次动作不属于本需求。',404)
 return {'resultState':'COMMITTED' if request else 'UNKNOWN','result':_own_result(user,request) if request else None,'automaticReplayAllowed':False,'historicalReceiptOnly':True,'businessWriteCount':0}
