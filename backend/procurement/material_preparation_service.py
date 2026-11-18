"""Physical declarations on existing reservations; no inventory or reservation writes."""
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from system.models import Company,OrganizationOperatingAuditRecord,PositionWorkflowResponsibility
from masterdata.models import MasterDataWriteRequest
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition
from pde.product_design_service import _canonical_hash,_write_request,_commit_request
from planning.mes_formal_source_admission import formal_datetime_label
from pfm.formal_employee import formal_employee_queryset
from .models import ProductionMaterialPreparation as Preparation,ProductionMaterialStockAllocation as Allocation
from . import material_allocation_service as allocations
from .material_stock_authority import quantity,fail
from .material_preparation_configuration import PERMISSION,DUTY

ENTITY='ProductionMaterialPreparation'
CONTRACT='PCE-PRODUCTION-MATERIAL-PREPARATION-V1'
text=allocations.text
six=lambda n:format(n,'.6f')

def _time(raw):
 if not isinstance(raw,str) or not ('T' in raw or ' ' in raw):fail('MATERIAL_PREPARATION_TIME_REQUIRED','须本人明确实际备料发生日期和时间，不以日期零点或登记时间代填。',400)
 try:value=parse_datetime(raw)
 except ValueError:value=None
 if value is None:fail('MATERIAL_PREPARATION_TIME_REQUIRED','实际时间须为完整ISO日期时间。',400)
 # Original Django-local datetime contract (USE_TZ=False): aware input is
 # converted to the configured business zone before storing a naive value.
 zone=timezone.get_default_timezone()
 value=timezone.make_aware(value,zone) if timezone.is_naive(value) else value
 return value if settings.USE_TZ else timezone.make_naive(value,zone)

def _allocation(user,allocation_id,*,current=False):
 if type(allocation_id) is not int or allocation_id<=0:fail('MATERIAL_PREPARATION_INPUT_INVALID','须准确选择原分配。',400)
 # Authorize a real actor before projecting any object identity.
 from .material_stock_authority import actor
 user=actor(user)
 row=Allocation.objects.select_for_update().select_related('audit_record','created_by','location').filter(pk=allocation_id,company_id=user.company_id).first()
 if not row:fail('MATERIAL_ALLOCATION_NOT_FOUND','原分配不在当前企业范围。',404)
 user,d,p,decision=allocations._actor_demand(user,row.demand_id,current=current,action_code=PERMISSION)
 employee=formal_employee_queryset(company_id=user.company_id).get(pk=decision['actorEmployeeId'])
 node=PositionWorkflowResponsibility.objects.get(pk=decision['workflowResponsibilityId'])
 today=timezone.now().date()
 if (node.ownership_type!='EXECUTOR' or node.effective_from and node.effective_from>today or node.effective_to and node.effective_to<today
  or employee.hire_date and employee.hire_date>today
  or employee.resignation_date and employee.resignation_date<=today):
  fail('MATERIAL_PREPARATION_DUTY_NOT_EFFECTIVE','当前人员任职或备料执行职责不在有效期内。',403)
 allocations._stored(row)
 if not row.location_id:fail('MATERIAL_PREPARATION_LOCATION_UNPROVEN','原分配没有正式库存库位，不能确认备料。')
 # Scope is enforced on the frozen warehouse even when its current source is pending.
 allocations._stock_scope(user,d,row.source_transaction,action_code=PERMISSION)
 return user,row,d,p,decision

def _current(user,row,d,p):
 allocations._actor_demand(user,d.pk,current=True,action_code=PERMISSION)
 tx,source=allocations._stock(user,row.source_transaction_id)
 allocations._stock_scope(user,d,tx,action_code=PERMISSION)
 if source['sourceFingerprint']!=row.source_snapshot['stockFingerprint'] or _canonical_hash(p)!=row.source_snapshot['demandFingerprint']:
  fail('MATERIAL_PREPARATION_SOURCE_CHANGED','需求、质量或原库存来源已变化；历史和占用保留待核。')
 capacity=allocations._capacity(d,p,tx,source)
 return tx,source,capacity

def _historical_applicability(row,source):
 # The original allocation froze the exact native facts before occurrence.
 # A later maintenance event cannot be assumed retrospectively applicable,
 # even if values were changed back. No new retrospective time window.
 p=source['proof'];pairs=[('Demand',row.demand_id),('ProductionMaterialStockAllocation',row.pk),
  ('InventoryTransaction',row.source_transaction_id),('InventoryLot',row.lot_id),('Warehouse',row.warehouse_id),
  ('WarehouseLocation',row.location_id),('WarehouseInbound',p['inboundId']),('PurchaseInspection',p['inspectionId']),('PurchaseReceipt',p['receiptId']),
  ('PurchaseOrder',p['sourceProof']['orderId'])]
 q=Q(pk__in=[])
 for kind,pk in pairs:q|=Q(target_type=kind,target_id=pk)
 if OrganizationOperatingAuditRecord.objects.filter(q,organization_id=row.company_id,created_at__gt=row.created_at).exists():
  fail('MATERIAL_PREPARATION_HISTORICAL_SCOPE_PENDING','分配后出现来源维护，无法直接证明实际发生时适用；原占用及历史保留。')

def _evidence(raw,row,source):
 if not isinstance(raw,list) or len(raw)>20 or any(type(x) is not int or x<=0 for x in raw) or len(set(raw))!=len(raw):
  fail('MATERIAL_PREPARATION_EVIDENCE_INVALID','已有凭证仅引用本分配可核验的原审计，不新增附件要求。',400)
 if not raw:return []
 p=source['proof'];pairs=[('ProductionMaterialStockAllocation',row.pk),('Demand',row.demand_id),('InventoryLot',row.lot_id),
  ('WarehouseInbound',p['inboundId']),('PurchaseInspection',p['inspectionId']),('PurchaseReceipt',p['receiptId'])]
 q=Q(pk__in=[])
 for kind,pk in pairs:q|=Q(target_type=kind,target_id=pk)
 if set(OrganizationOperatingAuditRecord.objects.filter(q,organization_id=row.company_id,pk__in=raw).values_list('pk',flat=True))!=set(raw):
  fail('MATERIAL_PREPARATION_EVIDENCE_UNPROVEN','凭证不属于本需求、分配或准确原生来源。')
 return sorted(raw)

def _stored(row):
 p=row.source_snapshot;a=row.audit_record
 fields={'companyId':row.company_id,'allocationId':row.allocation_id,'locationId':row.location_id,'quantity':six(row.quantity),
  'preparationMark':row.preparation_mark,'basis':row.basis,'evidenceReferences':row.evidence_references,
  'occurredAt':row.occurred_at.isoformat(),'registeredAt':row.created_at.isoformat(),'actorId':row.created_by_id,
  'actorSnapshot':row.actor_snapshot,'intentId':row.intent_id,'status':row.status,'version':row.version}
 req=MasterDataWriteRequest.objects.filter(pk=p.get('writeRequestId'),organization_id=row.company_id,entity_type=ENTITY,action_code=PERMISSION,status='COMMITTED').first()
 receipt={'preparationId':row.pk,'allocationId':row.allocation_id,'demandId':row.allocation.demand_id,'quantity':six(row.quantity),
  'auditId':a.pk,'occurredAt':row.occurred_at.isoformat(),'registeredAt':row.created_at.isoformat(),'status':'recorded','statusLabel':'已登记备料事实'}
 if (any(p.get(k)!=v for k,v in fields.items()) or a.target_type!=ENTITY or a.target_id!=row.pk or a.organization_id!=row.company_id
  or a.actor_id!=row.created_by_id or a.action_code!=PERMISSION or a.after_snapshot.get('preparationProof')!=p
  or not a.after_snapshot.get('authorization',{}).get('allowed') or row.intent_hash!=_canonical_hash(p.get('intent'))
  or a.after_snapshot.get('authorization')!=row.actor_snapshot.get('authorization')
  or not req or any(req.result.get(k)!=v for k,v in receipt.items()) or req.request_hash!=_canonical_hash(req.audit_metadata)):
  fail('MATERIAL_PREPARATION_PROOF_UNPROVEN','备料事实与原审计、版本或同次提交证明不一致，不能显示0或已备妥。')
 allocations._stored(row.allocation)
 if p.get('allocationProofHash')!=_canonical_hash(row.allocation.source_snapshot) or row.location_id!=row.allocation.location_id or not row.allocation.created_at<=row.occurred_at<=row.created_at<=a.created_at:
  fail('MATERIAL_PREPARATION_HISTORY_UNPROVEN','备料历史的原分配、库位或时间证明不一致。')
 chain=list(BusinessStateTransition.objects.filter(object_type=ENTITY,object_id=row.pk))
 if (len(chain)!=1 or chain[0].source_state!='' or chain[0].target_state!='recorded' or chain[0].action_code!=PERMISSION
  or chain[0].operator_id!=row.created_by_id or chain[0].audit_reference!=f'OrganizationOperatingAuditRecord:{a.pk}'):
  fail('MATERIAL_PREPARATION_STATE_UNPROVEN','备料初始状态缺少原统一转换证明。')
 return {**fields,'preparationId':row.pk,'statusLabel':'已登记备料事实','auditId':a.pk,
  'occurredAtLabel':formal_datetime_label(row.occurred_at,timezone.get_default_timezone_name()),
  'registeredAtLabel':formal_datetime_label(row.created_at,timezone.get_default_timezone_name()),'historicalFactOnly':True}

def _history(row):
 rows=list(Preparation.objects.select_for_update().filter(allocation=row).select_related('audit_record','allocation__audit_record').order_by('pk'))
 facts=[_stored(x) for x in rows];total=sum((x.quantity for x in rows),Decimal('0'))
 if total>row.quantity:fail('MATERIAL_PREPARATION_TOTAL_CONFLICT','历史备料超过原分配，保持待核，不隐藏记录。')
 return facts,total,_canonical_hash([{'id':x.pk,'proof':_canonical_hash(x.source_snapshot)} for x in rows])

def _projection(user,row,d,p):
 facts,total,version=_history(row);remaining=row.quantity-total
 from .material_issue_accounting import consumed
 from .models import ProductionMaterialIssue
 issued=consumed([row])[row.pk]
 received=sum((x.quantity for x in ProductionMaterialIssue.objects.filter(allocation=row,status='received')),Decimal('0'))
 out={'allocationId':row.pk,'demandId':d.pk,'materialId':row.material_id,'uomId':row.uom_id,'warehouseId':row.warehouse_id,
  'locationId':row.location_id,'lotId':row.lot_id,'allocationQuantity':six(row.quantity),'recordedPreparedQty':six(total),
  'unrecordedQty':six(remaining),'remainingConfirmationQty':None,'preparationCollectionVersion':version,'history':facts,
  'quotaStillHeld':row.quantity>issued,'issuedQty':six(issued),'receivedQty':six(received),'pendingReceiptQty':six(issued-received),
  'remainingOccupiedQty':six(row.quantity-issued),'remainingPreparedQty':six(total-issued),'issueStatus':'NATIVE_ISSUE_CONTRACT','physicalUnpreparedQty':None,
  'currentReady':None,'currentStatus':'PENDING_REVALIDATION','statusLabel':'当前备妥资格待核','blockingReason':None}
 try:
  tx,source,capacity=_current(user,row,d,p);_historical_applicability(row,source)
  return {**out,'remainingConfirmationQty':six(remaining),'currentReady':remaining==0,'currentStatus':'READY' if remaining==0 else 'NOT_FULLY_CONFIRMED',
   'statusLabel':'本分配已完成备料登记，已发量另列' if issued else '本分配已备妥' if remaining==0 else '本分配尚未全量登记确认','sourceFingerprint':source['sourceFingerprint'],
   'allocationProofHash':_canonical_hash(row.source_snapshot),'dimensionFingerprint':capacity['dimensionFingerprint'],
   'sourceUnoccupiedQty':capacity['sourceUnoccupiedQty'],'currentEvidence':'VERIFIED','canConfirm':remaining>0}
 except Exception as error:
  if not hasattr(error,'code'):raise
  return {**out,'canConfirm':False,'currentEvidence':'UNKNOWN','blockingReason':{'code':error.code,'message':str(error)}}

@transaction.atomic
def context(*,user,allocation_id):
 user,row,d,p,decision=_allocation(user,allocation_id)
 all_rows=allocations._rows(d);projections=[]
 for a in all_rows:
  allocations._stock_scope(user,d,a.source_transaction,action_code=PERMISSION)
  projections.append(_projection(user,a,d,p))
 occupied=sum((a.quantity for a in all_rows),Decimal('0'))
 if occupied>d.required_qty:fail('MATERIAL_DEMAND_ALLOCATION_CONFLICT','原需求占用超出准确需求，不能显示齐备。')
 ready=occupied==d.required_qty and bool(projections) and all(x['currentReady'] is True for x in projections)
 unknown=any(x['currentReady'] is None for x in projections)
 selected=next(x for x in projections if x['allocationId']==row.pk)
 issued_total=sum((Decimal(x['issuedQty']) for x in projections),Decimal('0'))
 return {'contractVersion':CONTRACT,'currentStateSource':'server','selected':selected,'allocations':projections,
  'demand':{'demandId':d.pk,'demandNo':d.demand_no,'materialId':d.material_id,'uomId':p['uomId'],'uomCode':p['uomCode'],
   'productionRange':[p['rangeStart'],p['rangeEnd']],'requiredQty':d.quantity_text,'recordedOccupiedQty':six(occupied),
   'recordedPreparedQty':six(sum((Decimal(x['recordedPreparedQty']) for x in projections),Decimal('0'))),
   'currentReady':None if unknown else ready,'statusLabel':'当前齐备资格待核' if unknown else '本需求已完成备料登记，已发量另列' if ready and issued_total else '本需求已备齐' if ready else '本需求尚未取得完整齐备证明',
   'scope':'仅本需求、物料及准确生产范围；备料为历史登记，已发另列，不代表全工单或订单',
   'issuedQty':six(sum((Decimal(x['issuedQty']) for x in projections),Decimal('0'))),
   'remainingOccupiedQty':six(sum((Decimal(x['remainingOccupiedQty']) for x in projections),Decimal('0')))},'businessWriteCount':0}

@transaction.atomic
def confirm(*,user,payload,key):
 required={'allocationId','locationId','quantity','preparationMark','basis','evidenceReferences','occurredAt','intentId',
  'expectedCollectionVersion','expectedAllocationProofHash','expectedSourceFingerprint','expectedDimensionFingerprint','reason'}
 if not isinstance(payload,dict) or set(payload)!=required:fail('MATERIAL_PREPARATION_INPUT_INVALID','须提供原分配/库位、实际时间、数量及原意图版本；不接受自报资格或状态。',400)
 text(key);reason=text(payload['reason'],300);intent=text(payload['intentId'],120)
 user,row,d,p,decision=_allocation(user,payload['allocationId'])
 Company.objects.select_for_update().get(pk=user.company_id)
 request,created,_=_write_request(user=user,action_code=PERMISSION,entity_type=ENTITY,key=key,request_body={'actorId':user.pk,**payload})
 if not created and request.status=='COMMITTED':return _own_result(user,request,row)
 qty=quantity(payload['quantity'],6);mark=text(payload['preparationMark'],160);basis=text(payload['basis'],500);occurred=_time(payload['occurredAt'])
 refs=payload['evidenceReferences']
 if not isinstance(refs,list) or len(refs)>20 or any(type(x) is not int or x<=0 for x in refs) or len(set(refs))!=len(refs):
  fail('MATERIAL_PREPARATION_EVIDENCE_INVALID','已有凭证须为不重复的准确原审计引用。',400)
 meaning={'allocationId':payload['allocationId'],'locationId':payload['locationId'],'evidenceReferences':sorted(refs)}
 meaning.update(quantity=six(qty),preparationMark=mark,basis=basis,occurredAt=occurred.isoformat(),actorId=user.pk,intentId=intent)
 old=Preparation.objects.select_related('audit_record','allocation__audit_record').filter(company_id=user.company_id,intent_id=intent).first()
 if old:
  _stored(old)
  if old.created_by_id!=user.pk or old.intent_hash!=_canonical_hash(meaning):fail('MATERIAL_PREPARATION_INTENT_CONFLICT','原备料意图已对应其他事实，不能覆盖或重复登记。')
  transaction.set_rollback(True)
  return {'preparationId':old.pk,'allocationId':old.allocation_id,'quantity':six(old.quantity),'auditId':old.audit_record_id,'businessWriteCount':0,'idempotent':True,'historicalReceiptOnly':True,'executionAuthorizedByResult':False}
 tx,source,capacity=_current(user,row,d,p);_historical_applicability(row,source)
 facts,total,version=_history(row)
 if (payload['expectedCollectionVersion']!=version or payload['expectedAllocationProofHash']!=_canonical_hash(row.source_snapshot)
  or payload['expectedSourceFingerprint']!=source['sourceFingerprint'] or payload['expectedDimensionFingerprint']!=capacity['dimensionFingerprint']):
  fail('MATERIAL_PREPARATION_VERSION_CONFLICT','来源、库存维度或备料集合版本变化，查询原动作后重新核定，不能自动重放。')
 if type(payload['locationId']) is not int or payload['locationId']!=row.location_id:fail('MATERIAL_PREPARATION_LOCATION_MISMATCH','仅可在分配原正式库位内确认；跨库位须另有正式移位，不在本包办理。')
 if qty!=qty.quantize(Decimal(1).scaleb(-tx.material.base_uom.decimal_places)):fail('MATERIAL_PREPARATION_UNIT_PRECISION','备料数量不符合原单位精度，6位存储不扩大单位规则。')
 if qty>row.quantity-total:fail('MATERIAL_PREPARATION_QUANTITY_EXCEEDED','超过本分配尚可登记确认量，不重复扣占用或库存。')
 registered=timezone.now()
 if not row.created_at<=occurred<=registered:fail('MATERIAL_PREPARATION_TIME_OUTSIDE_ALLOCATION','实际发生时间不得早于分配生效或晚于服务器登记。')
 refs=_evidence(payload['evidenceReferences'],row,source)
 employee=formal_employee_queryset(company_id=user.company_id).get(pk=decision['actorEmployeeId'])
 node=PositionWorkflowResponsibility.objects.get(pk=decision['workflowResponsibilityId'])
 if (employee.created_at>occurred or employee.updated_at>occurred
  or employee.hire_date and employee.hire_date>occurred.date()
  or node.effective_from and node.effective_from>occurred.date()
  or node.effective_to and node.effective_to<occurred.date()):
  fail('MATERIAL_PREPARATION_ACTOR_HISTORY_PENDING','发生时人员或职责适用依据待核，不能以当前档案补造历史。')
 actor_snapshot={'employeeId':employee.pk,'positionId':employee.position_ref_id,'responsibilityCode':DUTY,
  'employeeRecordedAt':employee.created_at.isoformat(),'employeeLastChangedAt':employee.updated_at.isoformat(),
  'hireDate':employee.hire_date.isoformat() if employee.hire_date else None,
  'dutyEffectiveFrom':node.effective_from.isoformat() if node.effective_from else None,'dutyEffectiveTo':node.effective_to.isoformat() if node.effective_to else None,
  'workflowNodeId':decision['workflowNodeId'],'workflowResponsibilityId':decision['workflowResponsibilityId'],'authorization':decision}
 proof={**meaning,'companyId':user.company_id,'registeredAt':registered.isoformat(),'actorSnapshot':actor_snapshot,
  'status':'recorded','version':1,'contractVersion':CONTRACT,'allocationProofHash':_canonical_hash(row.source_snapshot),
  'demandFingerprint':_canonical_hash(p),'sourceFingerprint':source['sourceFingerprint'],'dimensionFingerprint':capacity['dimensionFingerprint'],
  'priorCollectionVersion':version,'writeRequestId':request.pk,'intent':meaning,'timestampTimezone':timezone.get_default_timezone_name(),
  'historicalApplicability':'EXACT_FROZEN_ALLOCATION_AND_NO_LATER_SOURCE_MAINTENANCE'}
 audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=PERMISSION,target_type=ENTITY,
  target_id=0,target_label=d.demand_no,reason=reason,after_snapshot={'preparationProof':proof,'authorization':decision})
 prepared=create_business_object_with_initial_state(model=Preparation,initial_state='recorded',company_id=user.company_id,allocation=row,location_id=row.location_id,
  quantity=qty,preparation_mark=mark,basis=basis,evidence_references=refs,occurred_at=occurred,created_at=registered,created_by=user,
  actor_snapshot=actor_snapshot,source_snapshot=proof,intent_id=intent,intent_hash=_canonical_hash(meaning),audit_record=audit)
 audit.target_id=prepared.pk;audit.save(update_fields=['target_id'])
 record_projected_business_transition(object_type=ENTITY,object_id=prepared.pk,source_state='',target_state='recorded',action_code=PERMISSION,
  operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','recorded')})
 result={'preparationId':prepared.pk,'allocationId':row.pk,'demandId':d.pk,'quantity':six(qty),'auditId':audit.pk,
  'occurredAt':occurred.isoformat(),'registeredAt':registered.isoformat(),'status':'recorded','statusLabel':'已登记备料事实','businessWriteCount':1}
 _commit_request(request,result);return result

def _own_result(user,request,allocation):
 row=Preparation.objects.select_related('audit_record','allocation__audit_record').filter(pk=request.result.get('preparationId'),company_id=user.company_id,created_by=user,allocation=allocation).first()
 if not row:fail('MATERIAL_PREPARATION_RESULT_NOT_FOUND','同次动作不属于当前办理人或准确分配。',404)
 _stored(row)
 return {**request.result,'businessWriteCount':0,'idempotent':True,'historicalReceiptOnly':True,'executionAuthorizedByResult':False}

@transaction.atomic
def result_query(*,user,allocation_id,key):
 user,row,d,p,decision=_allocation(user,allocation_id);text(key)
 request=MasterDataWriteRequest.objects.filter(organization_id=user.company_id,entity_type=ENTITY,action_code=PERMISSION,idempotency_key=key,status='COMMITTED').first()
 return {'resultState':'COMMITTED' if request else 'UNKNOWN','result':_own_result(user,request,row) if request else None,
  'automaticReplayAllowed':False,'historicalReceiptOnly':True,'businessWriteCount':0}
