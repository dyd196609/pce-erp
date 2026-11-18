"""Native incoming rejected scope -> immutable observations. Only registration and custody; no supplier opinion, disposition or inventory write."""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, PositionWorkflowResponsibility, PositionResponsibility
from pfm.formal_employee import formal_employee_queryset
from masterdata.models import MasterDataWriteRequest
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state as initial,record_projected_business_transition as projected
from pde.product_design_service import _canonical_hash,_write_request,_commit_request
from .models import IncomingQualityExceptionFact as Fact,PurchaseInspection,Warehouse,WarehouseLocation
from .material_stock_authority import actor,fail,quantity,inspection_line_facts
from .material_preparation_service import _time
from planning.work_order_workshop_receipt_service import _effective

ENTITY='IncomingQualityExceptionFact'
PROCESS='PROCUREMENT_INCOMING_EXCEPTION'
CODES={'register':'quality.incoming_exception.register','custody':'warehouse.incoming_exception.custody'}
LABELS={'register':'已登记不合格范围，待仓管确认','custody':'已记录本人实物保管确认'}
def text(value,label,required=True,limit=1000):
 if value is None and not required:return None
 if not isinstance(value,str) or len(value)>limit or required and not value.strip():fail('INCOMING_EXCEPTION_INPUT_INVALID',label+'须明确填写。',400)
 return value.strip()

def source(user,inspection_id,kind,lock=False):
 user=actor(user)
 if kind not in CODES:fail('INCOMING_EXCEPTION_ACTION_UNKNOWN','没有该异常动作。',404)
 q=PurchaseInspection.objects.select_related('source_receipt__source_purchase_order')
 if lock:q=q.select_for_update()
 i=q.filter(pk=inspection_id,source_receipt__source_purchase_order__company_id=user.company_id).first()
 if not i:fail('INCOMING_EXCEPTION_NOT_FOUND','本企业没有该准确检验来源。',404)
 order=i.source_receipt.source_purchase_order
 decision=AuthorizationService.decide(user=user,action_code=CODES[kind],organization_id=user.company_id,
  business_object={'organizationId':user.company_id,'companyId':user.company_id,'departmentId':order.purchase_department_id or order.department_id,'ownerUserId':order.created_by})
 e=formal_employee_queryset(company_id=user.company_id).filter(user_id=user.pk).select_related('position_ref','department_ref').first()
 today=timezone.now().date()
 links=PositionWorkflowResponsibility.objects.filter(position_id=e.position_ref_id if e else None,active=True,ownership_type='EXECUTOR',workflow_node__process_definition__definition_code=PROCESS,workflow_node__process_definition__active=True,workflow_node__active=True,workflow_node__business_action_code=CODES[kind],responsibility__is_active=True,responsibility__status='ACTIVE')
 link=links.first() if links.count()==1 else None
 if not decision['allowed'] or not e or not link or not PositionResponsibility.objects.filter(position_id=e.position_ref_id,responsibility_id=link.responsibility_id,active=True).exists() or not _effective(e.position_ref,today) or not _effective(e.department_ref,today) or e.hire_date and e.hire_date>today or e.leave_date and e.leave_date<=today or e.resignation_date and e.resignation_date<=today or link.effective_from and link.effective_from>today or link.effective_to and link.effective_to<today:
  fail('INCOMING_EXCEPTION_QUALIFICATION_DENIED','须本人原有效岗位、执行职责和准确单据范围。',403)
 facts=inspection_line_facts(i)
 if facts['rejectedQuantity'] is None:fail('INCOMING_EXCEPTION_QUALITY_PENDING','本次检验尚未最终判定不合格数量。')
 if Decimal(facts['rejectedQuantity'])<=0:fail('INCOMING_EXCEPTION_NO_REJECTED_SCOPE','本次检验没有正式不合格范围。')
 return user,i,order,e,decision,facts

def receipt(row):
 audit=row.audit_record
 proof={'kind':row.kind,'inspectionId':row.inspection_id,'registrationId':row.registration_id,'quantity':format(row.quantity,'.6f') if row.quantity is not None else None,'intentId':row.intent_id,'actorId':row.created_by_id,'occurredAt':row.occurred_at.isoformat(),'payload':row.payload,'source':row.source_snapshot}
 chain=list(BusinessStateTransition.objects.filter(object_type=ENTITY,object_id=row.pk))
 if audit.target_id!=row.pk or audit.target_type!=ENTITY or audit.actor_id!=row.created_by_id or audit.organization_id!=row.company_id or audit.after_snapshot.get('factHash')!=_canonical_hash(proof) or len(chain)!=1 or chain[0].audit_reference!=f'OrganizationOperatingAuditRecord:{audit.pk}' or chain[0].operator_id!=row.created_by_id or chain[0].target_state!='recorded':
  fail('INCOMING_EXCEPTION_HISTORY_UNPROVEN','异常事实、审计或状态证明不一致，保留原记录待核。')
 label=LABELS[row.kind]
 return {'id':row.pk,**proof,'registeredAt':row.created_at.isoformat(),'statusLabel':label,'auditId':audit.pk,'historicalFactOnly':True,'inventoryEffect':'NONE'}

def context(*,user,inspection_id,kind,registration_id=None):
 user,i,order,e,decision,facts=source(user,inspection_id,kind)
 rows=list(Fact.objects.filter(inspection=i,company_id=user.company_id).select_related('audit_record').order_by('pk'))
 allfacts=[receipt(r) for r in rows]
 registered=sum((r.quantity for r in rows if r.kind=='register'),Decimal('0'))
 if registered>Decimal(facts['rejectedQuantity']):fail('INCOMING_EXCEPTION_SCOPE_CONFLICT','累计异常登记超出正式不合格量，保持待核。')
 root=next((r for r in rows if r.pk==registration_id and r.kind=='register'),None)
 if registration_id is not None and root is None:fail('INCOMING_EXCEPTION_REGISTRATION_NOT_FOUND','所选登记不属于本次准确检验。',404)
 selected=[r for r in rows if root and r.registration_id==root.pk]
 return {'inspection':facts,'registrations':[x for x in allfacts if x['kind']=='register'],'history':allfacts,'registrationId':root.pk if root else None,'registeredRejectedQuantity':str(registered),'remainingRegistrableQuantity':str(Decimal(facts['rejectedQuantity'])-registered),
  'custodyFacts':[x for x in allfacts if root and x['registrationId']==root.pk and x['kind']=='custody'],
  'custodyStatusLabel':'待仓管确认' if not any(r.kind=='custody' for r in selected) else '按逐次本人核对记录查看；差异及未核范围保留',
  'collectionVersion':_canonical_hash({'facts':allfacts,'source':facts}),'actionAuthorization':{'allowed':kind=='register' and registered<Decimal(facts['rejectedQuantity']) or kind!='register' and root is not None,'permission':CODES[kind]},'businessWriteCount':0,'currentStateSource':'server'}

@transaction.atomic
def execute(*,user,inspection_id,kind,payload):
 user,i,order,e,decision,facts=source(user,inspection_id,kind,True)
 required={'idempotencyKey','intentId','expectedCollectionVersion','reason','occurredAt','registrationId','details'}
 if not isinstance(payload,dict) or set(payload)!=required:fail('INCOMING_EXCEPTION_INPUT_INVALID','仅接受准确动作意图、版本、发生时间和本次资料。',400)
 key=text(payload['idempotencyKey'],'同次标识',limit=160);intent=text(payload['intentId'],'业务意图',limit=120);reason=text(payload['reason'],'办理依据',limit=300)
 occurred=_time(payload['occurredAt'])
 if occurred>timezone.now():fail('INCOMING_EXCEPTION_TIME_INVALID','发生时间不能晚于服务器登记时间。',400)
 root_id=payload['registrationId'];body=payload['details']
 if not isinstance(body,dict):fail('INCOMING_EXCEPTION_INPUT_INVALID','本次资料须为明确结构。',400)
 meaning={'inspectionId':i.pk,'kind':kind,'actorId':user.pk,**{k:v for k,v in payload.items() if k not in {'idempotencyKey','expectedCollectionVersion'}}}
 old=Fact.objects.filter(company_id=user.company_id,kind=kind,intent_id=intent).select_related('audit_record').first()
 if old:
  if old.intent_hash!=_canonical_hash(meaning):fail('INCOMING_EXCEPTION_INTENT_CONFLICT','同一意图内容已变化，不覆盖或重复登记。')
  return {**receipt(old),'businessWriteCount':0,'idempotent':True}
 c=context(user=user,inspection_id=i.pk,kind=kind,registration_id=root_id)
 if payload['expectedCollectionVersion']!=c['collectionVersion']:fail('INCOMING_EXCEPTION_VERSION_CONFLICT','记录集合已变化，请刷新或查询原动作，不自动重放。')
 root=Fact.objects.filter(pk=root_id,company_id=user.company_id,inspection=i,kind='register').first() if root_id else None
 if kind!='register' and not root:fail('INCOMING_EXCEPTION_REGISTRATION_REQUIRED','须选择本检验的准确异常登记。',400)
 if root and occurred<root.occurred_at:fail('INCOMING_EXCEPTION_TIME_INVALID','后续核对或意见时间不能早于异常登记。',400)
 qty=None
 if kind=='register':
  if root_id is not None or set(body)!={'quantity','basis'}:fail('INCOMING_EXCEPTION_INPUT_INVALID','异常登记须明确数量和依据，不自报来源。',400)
  qty=quantity(body['quantity']);text(body['basis'],'异常依据')
  if qty>Decimal(c['remainingRegistrableQuantity']) or qty!=qty.quantize(Decimal(1).scaleb(-i.source_receipt.source_purchase_order.items.get(pk=facts['purchaseOrderItemId']).material.base_uom.decimal_places)):fail('INCOMING_EXCEPTION_QUANTITY_EXCEEDED','超过本检验尚未登记的不合格范围或单位精度。')
 elif kind=='custody':
  if set(body)!={'actualQuantity','warehouseId','locationId','locationDescription','isolated','quantityVerified','pendingReason','basis'}:fail('INCOMING_EXCEPTION_INPUT_INVALID','须区分实际核对量、位置、隔离及待核原因。',400)
  if body['isolated'] is not None and type(body['isolated']) is not bool or type(body['quantityVerified']) is not bool:fail('INCOMING_EXCEPTION_INPUT_INVALID','核实与隔离须为明确事实或未知。',400)
  qty=quantity(body['actualQuantity'],zero=True) if body['actualQuantity'] is not None else None
  warehouse=Warehouse.objects.filter(pk=body['warehouseId'],company_id=user.company_id,is_active=True).first() if body['warehouseId'] else None
  location=WarehouseLocation.objects.filter(pk=body['locationId'],warehouse=warehouse,is_active=True).first() if body['locationId'] else None
  if body['warehouseId'] and not warehouse or body['locationId'] and not location:fail('INCOMING_EXCEPTION_LOCATION_UNPROVEN','所选实际位置不在原企业仓储范围。',403)
  if warehouse:
   storage=AuthorizationService.decide(user=user,action_code=CODES[kind],organization_id=warehouse.company_id,business_object={'companyId':warehouse.company_id,'organizationId':warehouse.company_id,'warehouseId':warehouse.pk,'departmentId':order.purchase_department_id or order.department_id,'ownerUserId':order.created_by})
   if not storage.get('allowed'):fail('INCOMING_EXCEPTION_LOCATION_DENIED','本人没有所选实际仓储位置的原授权范围。',403)
  body={**body,'locationDescription':text(body['locationDescription'],'实际位置说明',required=False),'basis':text(body['basis'],'实物核对依据'),'pendingReason':text(body['pendingReason'],'待核原因',required=False)}
  precision=order.items.get(pk=facts['purchaseOrderItemId']).material.base_uom.decimal_places
  if qty is not None and qty!=qty.quantize(Decimal(1).scaleb(-precision)):fail('INCOMING_EXCEPTION_UNIT_PRECISION_INVALID','实际核对量不符合原单位精度，不舍入。')
  confirmed=bool(body['quantityVerified'] and qty is not None and qty<=root.quantity and qty>0 and warehouse and (location or body['locationDescription']) and body['isolated'] is not None)
  difference=None if qty is None else str(root.quantity-qty)
  if (not confirmed or qty!=root.quantity) and not body['pendingReason']:fail('INCOMING_EXCEPTION_PENDING_REASON_REQUIRED','无法核实或存在数量差异时必须保留具体待核原因。',400)
  body={**body,'confirmedCustodyQuantity':str(qty) if confirmed else None,'confirmedCustodianId':user.pk if confirmed else None,'differenceQuantity':difference,'entireRegistrationConfirmed':confirmed and qty==root.quantity}
 req,created,_=_write_request(user=user,action_code=CODES[kind],entity_type=ENTITY,key=key,request_body=meaning)
 if not created and req.status=='COMMITTED':
  row=Fact.objects.select_related('audit_record').filter(pk=req.result.get('id'),created_by=user,company_id=user.company_id,inspection=i).first()
  if not row:fail('INCOMING_EXCEPTION_RESULT_NOT_FOUND','原回执不属于本次身份或来源。',404)
  return {**receipt(row),'businessWriteCount':0}
 proof={'kind':kind,'inspectionId':i.pk,'registrationId':root_id,'quantity':format(qty,'.6f') if qty is not None else None,'intentId':intent,'actorId':user.pk,'occurredAt':occurred.isoformat(),'payload':body,'source':{'lineFacts':facts,'employeeId':e.pk,'employeeNo':e.employee_no,'employeeName':e.full_name,'positionId':e.position_ref_id,'positionName':e.position_ref.name,'purchaseOrderNo':order.po_no,'supplierId':order.supplier_id,'supplierCode':order.supplier_code_snapshot,'supplierName':order.supplier_name_snapshot,'authorization':decision}}
 audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=CODES[kind],target_type=ENTITY,target_id=0,target_label=i.inspection_no,reason=reason,after_snapshot={'factHash':_canonical_hash(proof),'fact':proof})
 row=initial(model=Fact,initial_state='recorded',company_id=user.company_id,inspection=i,registration=root,kind=kind,quantity=qty,intent_id=intent,intent_hash=_canonical_hash(meaning),payload=body,source_snapshot=proof['source'],created_by=user,occurred_at=occurred,audit_record=audit)
 audit.target_id=row.pk;audit.save(update_fields=['target_id'])
 projected(object_type=ENTITY,object_id=row.pk,source_state='',target_state='recorded',action_code=CODES[kind],operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','recorded')})
 result={**receipt(row),'businessWriteCount':1};_commit_request(req,result);return result

def result_query(*,user,inspection_id,kind,key,intent_id=None):
 user,i,*_=source(user,inspection_id,kind)
 req=MasterDataWriteRequest.objects.filter(organization_id=user.company_id,entity_type=ENTITY,action_code=CODES[kind],idempotency_key=key,status='COMMITTED').first()
 row=Fact.objects.select_related('audit_record').filter(pk=req.result.get('id'),company_id=user.company_id,inspection=i,created_by=user).first() if req else None
 if not req and intent_id:
  row=Fact.objects.select_related('audit_record').filter(company_id=user.company_id,inspection=i,kind=kind,intent_id=intent_id,created_by=user).first()
 if req and not row:fail('INCOMING_EXCEPTION_RESULT_NOT_FOUND','原结果不属于本次身份、检验或动作。',404)
 return {'resultState':'COMMITTED' if row else 'UNKNOWN','result':receipt(row) if row else None,'businessWriteCount':0,'automaticReplayAllowed':False,'historicalReceiptOnly':True}
