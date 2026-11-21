from .quantity_contract import quantity_text
"""Native raw-stock provenance on the existing receipt/inspection/inbound services."""
from decimal import Decimal,InvalidOperation
from django.db import transaction
from django.utils import timezone
from masterdata.models import MasterDataWriteRequest
from system.models import User,Company,OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state as initial,record_projected_business_transition as projected,transition_business_object as transition
from pde.product_design_service import _canonical_hash,_write_request,_commit_request
from .models import PurchaseOrder,PurchaseReceipt,PurchaseInspection,WarehouseInbound,InventoryBalance,InventoryTransaction,Warehouse,WarehouseLocation,InventoryLot
from .scm_runtime_services import ScmRuntimeActionError,_authorize_fulfillment,_next_number,_business_date
from .comparison_registration_service import ComparisonRegistrationError

SOURCE_ERRORS=(ScmRuntimeActionError,ComparisonRegistrationError)

CONTRACT='PCE-NATIVE-PRODUCTION-RAW-STOCK-V1'
PURPOSE='PRODUCTION_USE'
ACTIONS={'confirm-receipt':'procurement.receipt.receive','create-inspection':'quality.purchase.inspect','transition-inspection':'quality.purchase.inspect','confirm-inbound':'warehouse.purchase.putaway'}
def fail(code,message,status=409):raise ScmRuntimeActionError(code,message,status)
def quantity(raw,places=6,*,zero=False):
 if isinstance(raw,(float,bool)):fail('RAW_QUANTITY_INVALID','数量须为准确十进制字符串，不接收float。',400)
 try:
  value=Decimal(str(raw));q=Decimal(1).scaleb(-places)
  if not value.is_finite() or value<0 or not zero and value==0 or value!=value.quantize(q) or value>=Decimal('1e14'):raise ValueError()
  return value
 except (InvalidOperation,ValueError,TypeError):fail('RAW_QUANTITY_PRECISION_UNSUPPORTED','原收发字段不能无损承载此量，不舍入、不扩大字段。')

def original_quantity_field(model,field_name,value):
 field=model._meta.get_field(field_name)
 if value!=value.quantize(Decimal(1).scaleb(-field.decimal_places)) or abs(value)>=Decimal(10)**(field.max_digits-field.decimal_places):
  fail('RAW_DOWNSTREAM_QUANTITY_PRECISION_UNSUPPORTED','原采购行或库存字段无法准确承接本数量；不舍入、不扩大字段。')
 return value
def actor(user):
 u=User.objects.defer('password').filter(pk=getattr(user,'pk',None),is_active=True,is_superuser=False).first()
 if not u or not Company.objects.filter(pk=u.company_id,is_active=True).exists():fail('RAW_BUSINESS_ACTOR_REQUIRED','须使用原有效业务员工身份。',403)
 return u

def warehouse_resource(warehouse,location):
 if not warehouse or not location or warehouse.usage_purpose!=PURPOSE or not warehouse.is_active or not location.is_active or location.warehouse_id!=warehouse.pk:fail('RAW_WAREHOUSE_SOURCE_UNPROVEN','须准确正式用途原料仓及有效库位。')
 audits=[]
 for action,target,pk in [('REGISTER_FORMAL_RAW_MATERIAL_WAREHOUSE','Warehouse',warehouse.pk),('REGISTER_FORMAL_RAW_MATERIAL_LOCATION','WarehouseLocation',location.pk)]:
  event=OrganizationOperatingAuditRecord.objects.filter(organization_id=warehouse.company_id,action_code=action,target_type=target,target_id=pk,after_snapshot__warehouseId=warehouse.pk).first()
  state=event.after_snapshot if event else {}
  # The original maintenance audit stores direct snapshots. A location takes
  # its purpose from the exact parent warehouse, not a second purpose column.
  if not event or not state.get('configurationOnly') or target=='Warehouse' and state.get('usagePurpose')!=PURPOSE or target=='WarehouseLocation' and state.get('locationId')!=location.pk:fail('RAW_WAREHOUSE_SOURCE_UNPROVEN','原料仓及库位缺正式维护来源，不按名称或成品仓用途猜配。')
  audits.append(event.pk)
 return audits
def row_facts(row):
 result={'type':type(row).__name__,'id':row.pk,'status':row.status,'quantity':quantity_text(row.quantity),'items':row.items}
 for name in ['source_purchase_order_id','source_receipt_id','source_inspection_id','production_transfer_id','warehouse_id','location_id','operator_account_id','inspector_account_id','usage_purpose','qualified_quantity','rejected_quantity']:
  if hasattr(row,name):
   x=getattr(row,name);result[name]=quantity_text(Decimal(str(x))) if name in {'qualified_quantity','rejected_quantity'} else x
 return result

def _numeric_state(state):
 # Model defaults may be integer zero before reload. Compare exact numeric
 # facts without rewriting the original audit content or its recorded hash.
 result=dict(state)
 for field in ('quantity','qualified_quantity','rejected_quantity'):
  if field in result:result[field]=quantity_text(quantity(result[field],zero=True))
 return result
def audit_step(row,action,user,decision,target,reason,source=''):
 state={**row_facts(row),'status':target}
 event=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=action,
  target_type=type(row).__name__,target_id=row.pk,target_label=row.object_no,reason=reason,
  before_snapshot={'status':source},after_snapshot={'contractVersion':CONTRACT,'authorization':decision,'state':state,'stateHash':_canonical_hash(state)})
 ref=f'OrganizationOperatingAuditRecord:{event.pk}'
 if source:
  transition(business_object=row,object_type=type(row).__name__,source_state=source,target_state=target,action_code=action,
   operator=user,reason=reason,audit_reference=ref,allowed_transitions={(source,target)},version_field=None)
 else:projected(object_type=type(row).__name__,object_id=row.pk,source_state='',target_state=target,action_code=action,
   operator=user,reason=reason,audit_reference=ref,allowed_transitions={('',target)})
 return event
def verify_history(row):
 chain=list(BusinessStateTransition.objects.filter(object_type=type(row).__name__,object_id=row.pk).order_by('version','pk'))
 previous='';last=None
 for t in chain:
  ref=t.audit_reference.removeprefix('OrganizationOperatingAuditRecord:')
  a=OrganizationOperatingAuditRecord.objects.filter(pk=int(ref),organization_id=row.source_purchase_order.company_id if isinstance(row,PurchaseReceipt) else row.source_receipt.source_purchase_order.company_id if isinstance(row,PurchaseInspection) else row.warehouse.company_id).first() if ref.isdigit() else None
  snapshot=a.after_snapshot if a else {}
  if not a or a.target_type!=type(row).__name__ or a.target_id!=row.pk or a.actor_id!=t.operator_id or a.action_code!=t.action_code or snapshot.get('contractVersion')!=CONTRACT or not snapshot.get('authorization',{}).get('allowed') or snapshot.get('stateHash')!=_canonical_hash(snapshot.get('state')) or snapshot.get('state',{}).get('status')!=t.target_state or t.source_state!=previous:
   fail('RAW_SOURCE_HISTORY_UNPROVEN','原料来源审计或统一状态证明不一致，保留原记录待核。')
  previous=t.target_state;last=snapshot
 if not last or previous!=row.status or _numeric_state(last['state'])!=_numeric_state(row_facts(row)):fail('RAW_SOURCE_HISTORY_UNPROVEN','缺少准确原料来源初始化/当前状态证明。')
 return {'historyIds':[x.pk for x in chain],'lastAuditId':a.pk,'stateHash':last['stateHash']}
def _business_line_no(line):
 # The original PO item has no business line-number field. Do not relabel a
 # request line number, database PK or array position as a PO line number.
 return None

def _source_line_identity(line):
 from .fact_read_access import object_read_context
 item=line.source_purchase_request_item
 scope=object_read_context(item.purchase_request) if item else None
 proved=bool(scope and scope['organizationId']==line.po.company_id)
 if item and not scope and line.po.source_purchase_request_id==item.purchase_request_id:
  from .purchase_order_approval_service import _origin
  # A new native DIRECT creation audit proves its typed request relationship;
  # it does not assign a company to an old unowned request.
  creation=_origin(line.po)
  proved=creation.after_snapshot.get('state',{}).get('sourcePurchaseRequestId')==item.purchase_request_id
 if not item or not proved or item.material_id!=line.material_id:
  return {'sourcePurchaseRequestNo':None,'sourcePurchaseRequestLineNo':None,'purchaseOrderLineNoStatus':'NOT_PROVIDED'}
 return {'sourcePurchaseRequestNo':item.purchase_request.request_no,'sourcePurchaseRequestLineNo':item.line_no,'purchaseOrderLineNoStatus':'NOT_PROVIDED'}

def _checked_line(order,line):
 m=line.material
 if line.po_id!=order.pk or not m or m.company_id!=order.company_id or m.material_type=='finished' or not m.is_active or not m.base_uom_id or m.base_uom.company_id!=order.company_id or line.unit_snapshot not in {m.base_uom.code,m.base_uom.name}:
  fail('RAW_ORDER_MATERIAL_UNIT_UNPROVEN','原采购行、物料及基本单位证明不完整，不猜配或换算。')
 return line

def _bound_line(order,row):
 if not isinstance(row.items,list) or len(row.items)!=1:
  fail('RAW_QUALITY_LINE_SCOPE_PENDING','旧混料记录没有逐行质量依据，保留待核。')
 item=row.items[0]
 if not isinstance(item,dict) or not isinstance(item.get('rawMaterialProof'),dict):fail('RAW_LINE_SOURCE_UNPROVEN','原记录没有可核验的类型化采购行来源。')
 proof=item['rawMaterialProof']
 line=order.items.select_related('material__base_uom','source_purchase_request_item').filter(pk=item.get('purchaseOrderItemId')).first()
 if not line:fail('RAW_LINE_SOURCE_UNPROVEN','记录没有准确的本采购单行关系。')
 _checked_line(order,line)
 expected={'contractVersion':CONTRACT,'usagePurpose':PURPOSE,'companyId':order.company_id,'orderId':order.pk,'orderItemId':line.pk,'materialId':line.material_id,'uomId':line.material.base_uom_id,'unitPrecision':line.material.base_uom.decimal_places}
 if (any(proof.get(k)!=v for k,v in expected.items()) or item.get('materialId')!=line.material_id
     or item.get('unit')!=line.unit_snapshot or quantity(item.get('quantity'))!=row.quantity):
  fail('RAW_LINE_SOURCE_UNPROVEN','采购行、原料、单位或本次数量与正式来源证据不一致。')
 if isinstance(row,PurchaseInspection) and proof.get('receiptId')!=row.source_receipt_id:
  fail('RAW_LINE_SOURCE_UNPROVEN','检验未绑定本次准确收货。')
 if isinstance(row,WarehouseInbound) and (proof.get('receiptId')!=row.source_inspection.source_receipt_id or proof.get('inspectionId')!=row.source_inspection_id):
  fail('RAW_LINE_SOURCE_UNPROVEN','入库未绑定准确收货和检验。')
 return line

def _order_line(order,*,row=None,line_id=None,allow_unselected=False):
 from .purchase_order_approval_service import _history
 history,_=_history(order)
 if len(history)!=4:fail('RAW_ORDER_NOT_RELEASED','须原独立审批及下达证明，不能只按订单状态放行。')
 frozen=history[0]['frozenSource'];approved={x['id']:x for x in frozen['lines']}
 current=list(order.items.all())
 if set(approved)!={x.pk for x in current} or frozen['companyId']!=order.company_id or frozen['orderId']!=order.pk:
  fail('RAW_APPROVED_LINE_CHANGED','当前采购行集合不符合原批准范围，保持待核。')
 for item in current:
  original=approved[item.pk]
  identity={'materialId':item.material_id,'requestItemId':item.source_purchase_request_item_id,'resultId':item.price_approval_result_id,'priceId':item.supplier_material_price_id,'unit':item.unit_snapshot}
  if any(original.get(k)!=v for k,v in identity.items()) or Decimal(original['quantity'])!=item.quantity:
   fail('RAW_APPROVED_LINE_CHANGED','当前采购行来源、数量或单位不符合原批准范围。')
 if row is not None:
  line=_bound_line(order,row)
  if line_id is not None and line.pk!=line_id:fail('RAW_LINE_SOURCE_CONFLICT','选择的采购行与原记录不一致。')
  return line
 lines=list(order.items.select_related('material__base_uom','source_purchase_request_item'))
 if line_id is None:
  if len(lines)==1:return _checked_line(order,lines[0])
  if allow_unselected:return None
  fail('RAW_PURCHASE_LINE_REQUIRED','请从本单候选中明确选择采购行，不按行序或数量猜配。',400)
 if type(line_id) is not int or line_id<=0:fail('RAW_PURCHASE_LINE_INVALID','采购行身份须为本单正式候选。',400)
 line=next((x for x in lines if x.pk==line_id),None)
 if not line:fail('RAW_LINE_SOURCE_NOT_FOUND','采购行不属于当前获准采购单。',404)
 return _checked_line(order,line)

def _line_receipts(order,line):
 rows=[]
 for row in order.scm_receipts.order_by('pk'):
  verify_history(row);bound=_bound_line(order,row)
  if bound.pk==line.pk:
   if row.status!='received':fail('RAW_RECEIPT_SCOPE_PENDING','已有收货尚未形成完整实收证明，不能推定剩余可收量。')
   rows.append(row)
 return rows

def _successful_inbounds(inspection):
 order=inspection.source_receipt.source_purchase_order;line=_bound_line(order,inspection)
 total=Decimal('0');records=[]
 for ib in inspection.warehouse_inbounds.order_by('pk'):
  verify_history(ib)
  if _bound_line(order,ib).pk!=line.pk or ib.status!='completed':fail('RAW_INBOUND_SCOPE_PENDING','已有入库未能证明成功记账，额度保持待核。')
  txs=list(InventoryTransaction.objects.filter(source_inbound=ib,direction='IN'))
  if len(txs)!=1:fail('RAW_INBOUND_LEDGER_UNPROVEN','本入库没有唯一可核对的库存IN。')
  tx=txs[0]
  if (tx.direction!='IN' or tx.usage_purpose!=PURPOSE or tx.material_id!=line.material_id
      or tx.warehouse_id!=ib.warehouse_id or tx.location_id!=ib.location_id or tx.quantity!=ib.quantity
      or tx.after_quantity-tx.before_quantity!=tx.quantity or not tx.lot_id or tx.lot.lot_no!=ib.items[0].get('lotNo')):
   fail('RAW_INBOUND_LEDGER_UNPROVEN','本检验的入库行、批次、数量与库存IN不一致。')
  total+=tx.quantity;records.append({'inboundId':ib.pk,'inboundNo':ib.inbound_no,'transactionId':tx.pk,'transactionNo':tx.transaction_no,'quantity':str(tx.quantity)})
 if total>inspection.qualified_quantity:fail('RAW_STOCK_QUALITY_SCOPE_INVALID','本检验已记账量超过正式合格范围。')
 return total,records

def inspection_line_facts(inspection):
 order=inspection.source_receipt.source_purchase_order
 line=_order_line(order,row=inspection.source_receipt)
 verify_history(inspection.source_receipt);verify_history(inspection)
 if _bound_line(order,inspection).pk!=line.pk:fail('RAW_LINE_SOURCE_CONFLICT','检验与收货不属于同一采购行。')
 if inspection.quantity!=inspection.source_receipt.quantity:fail('RAW_QUALITY_SCOPE_UNPROVEN','检验范围未覆盖本次准确收货。')
 final=inspection.status in {'qualified','rejected'}
 if final and inspection.qualified_quantity+inspection.rejected_quantity!=inspection.quantity:fail('RAW_QUALITY_SCOPE_UNPROVEN','最终质量结论未完整覆盖本次检验范围。')
 used,records=_successful_inbounds(inspection)
 if not final and used:fail('RAW_QUALITY_SCOPE_UNPROVEN','尚未最终判定的检验出现入库事实。')
 allowed=inspection.status=='qualified'
 available=inspection.qualified_quantity-used if allowed else Decimal('0') if final else None
 return {'purchaseOrderId':order.pk,'purchaseOrderNo':order.po_no,'purchaseOrderItemId':line.pk,**_source_line_identity(line),
  'purchaseOrderLineNo':_business_line_no(line),'purchaseRequestItemId':line.source_purchase_request_item_id,
  'materialId':line.material_id,'materialCode':line.material.code,'materialName':line.material.name,
  'unit':line.unit_snapshot,'receiptId':inspection.source_receipt_id,'receiptNo':inspection.source_receipt.receipt_no,
  'inspectionId':inspection.pk,'inspectionNo':inspection.inspection_no,'statusLabel':inspection.get_status_display(),
  'registeredReceivedQuantity':str(inspection.source_receipt.quantity),'inspectionScopeQuantity':str(inspection.quantity),
  'actualInspectedQuantity':None,'actualInspectedQuantityStatus':'NOT_PROVIDED',
  'qualifiedQuantity':str(inspection.qualified_quantity) if final else None,
  'rejectedQuantity':str(inspection.rejected_quantity) if final else None,
  'successfullyInboundQuantity':str(used),'currentInboundEligibleQuantity':str(available) if available is not None else None,
  'qualityReleaseStatus':'RELEASED' if allowed else 'REJECTED' if final else 'PENDING',
  'qualityReleaseStatusLabel':'本检验范围已放行' if allowed else '本检验范围不合格' if final else '本检验范围仍待判定',
  'blockingReason':None if allowed and available>0 else {'code':'RAW_QUALITY_EXHAUSTED' if allowed else 'RAW_QUALITY_NOT_RELEASED','message':'本检验合格量已用尽。' if allowed else '本范围尚无可入库的正式合格结论。'},
  'inboundRecords':records,'actionQualificationNotGrantedByRead':True}

def quality_projection(inspection):
 try:return {'lineReleaseFacts':inspection_line_facts(inspection),'lineReleaseStatus':'PROVIDED'}
 except SOURCE_ERRORS as exc:
  return {'lineReleaseFacts':None,'lineReleaseStatus':'SOURCE_UNKNOWN','lineReleaseBlockingReason':{'code':exc.code,'message':str(exc)},'actualInspectedQuantity':None,'actualInspectedQuantityStatus':'NOT_PROVIDED'}

def _line_summary(order,line):
 receipts=_line_receipts(order,line);received=sum((r.quantity for r in receipts),Decimal('0'))
 if received>line.quantity:fail('RAW_RECEIPT_QUANTITY_EXCEEDED','原采购行登记收货量超出批准数量，保持待核。')
 scopes=[]
 for receipt in receipts:
  inspections=list(receipt.inspections.order_by('pk'))
  if len(inspections)>1:fail('RAW_QUALITY_SCOPE_UNPROVEN','一次收货存在多张未经核定的检验，不累计合格量。')
  scopes.extend(inspection_line_facts(i) for i in inspections)
 return {'purchaseOrderItemId':line.pk,'purchaseOrderLineNo':_business_line_no(line),**_source_line_identity(line),
  'purchaseRequestItemId':line.source_purchase_request_item_id,'materialId':line.material_id,
  'materialCode':line.material.code,'materialName':line.material.name,'unit':line.unit_snapshot,
  'orderedQuantity':str(line.quantity),'registeredReceivedQuantity':str(received),'remainingReceivableQuantity':str(line.quantity-received),
  'receiptIds':[r.pk for r in receipts],'inspectionScopes':scopes,
  'actualInspectedQuantity':None,'actualInspectedQuantityStatus':'NOT_PROVIDED',
  'qualityStatusLabel':'部分收货范围已放行，其余待判' if any(x['qualityReleaseStatus']=='RELEASED' for x in scopes) and (len(scopes)<len(receipts) or any(x['qualityReleaseStatus']=='PENDING' for x in scopes)) else '本行收货仍待判定' if scopes and all(x['qualityReleaseStatus']=='PENDING' for x in scopes) else '已有质量结论，按各检验范围核对' if scopes else '尚无本行检验结论'}

def _refresh_order(order,user,action,decision,reason):
 lines=list(order.items.select_related('material__base_uom','source_purchase_request_item'))
 try:summaries=[_line_summary(order,_checked_line(order,x)) for x in lines]
 except SOURCE_ERRORS:return  # Keep header unchanged when another historical range is unproved.
 received=bool(lines) and all(Decimal(x['registeredReceivedQuantity'])==line.quantity for line,x in zip(lines,summaries))
 inspected=received and all(x['inspectionScopes'] and len(x['inspectionScopes'])==len(x['receiptIds']) and all(q['qualityReleaseStatus']=='RELEASED' for q in x['inspectionScopes']) for x in summaries)
 stored=inspected and all(all(Decimal(q['successfullyInboundQuantity'])==Decimal(q['registeredReceivedQuantity']) for q in x['inspectionScopes']) for x in summaries)
 for source,target,ready in [('final_approved','received',received),('received','inspected',inspected),('inspected','stored',stored)]:
  if order.status==source and ready:_order_move(order,target,user,action,decision,reason)

def _source(action,pk,user,*,lock=False,line_id=None,allow_unselected=False):
 model=PurchaseOrder if action=='confirm-receipt' else PurchaseReceipt if action=='create-inspection' else PurchaseInspection
 query=model.objects.select_for_update() if lock else model.objects
 row=query.filter(pk=pk).first()
 order=row if isinstance(row,PurchaseOrder) else row.source_purchase_order if isinstance(row,PurchaseReceipt) else row.source_receipt.source_purchase_order if row else None
 if not order or order.company_id!=user.company_id:fail('RAW_SOURCE_NOT_FOUND','原来源不在当前范围。',404)
 decision,employee=_authorize_fulfillment(user=user,action_code=ACTIONS[action],order=order)
 original=row.source_receipt if isinstance(row,PurchaseInspection) else row if isinstance(row,PurchaseReceipt) else None
 line=_order_line(order,row=original,line_id=line_id,allow_unselected=allow_unselected)
 if not isinstance(row,PurchaseOrder):verify_history(row)
 if isinstance(row,PurchaseInspection):
  verify_history(row.source_receipt)
  if _bound_line(order,row).pk!=line.pk:fail('RAW_LINE_SOURCE_CONFLICT','检验与本次收货的采购行不符。')
 return row,order,line,decision,employee

def source_context(*,user,action,object_id,purchase_order_item_id=None):
 user=actor(user)
 if action not in ACTIONS:fail('RAW_ACTION_UNKNOWN','没有本次原料来源动作。',404)
 row,order,line,decision,employee=_source(action,object_id,user,line_id=purchase_order_item_id,allow_unselected=True)
 body={'sourceType':type(row).__name__,'sourceId':row.pk,'orderId':order.pk,'orderNo':order.po_no,
  'orderState':order.status,'lineId':line.pk if line else None,'materialId':line.material_id if line else None,
  'uomId':line.material.base_uom_id if line else None,'unitPrecision':line.material.base_uom.decimal_places if line else None,
  'unit':line.unit_snapshot if line else None,'lineQuantity':str(line.quantity) if line else None,
  'state':row_facts(row) if not isinstance(row,PurchaseOrder) else None,
  'receipts':[row_facts(x) for x in _line_receipts(order,line)] if line else [],
  'inspectionInbounds':[row_facts(x) for x in row.warehouse_inbounds.order_by('pk')] if isinstance(row,PurchaseInspection) else []}
 candidates=[]
 for candidate in order.items.select_related('material__base_uom','source_purchase_request_item').order_by('pk'):
  try:candidates.append({**_line_summary(order,_checked_line(order,candidate)),'sourceStatus':'PROVIDED'})
  except SOURCE_ERRORS as exc:candidates.append({'purchaseOrderItemId':candidate.pk,'purchaseOrderLineNo':_business_line_no(candidate),'sourceStatus':'SOURCE_UNKNOWN','blockingReason':{'code':exc.code,'message':str(exc)}})
 body['purchaseOrderLineNo']=_business_line_no(line) if line else None
 body['lineCandidates']=candidates
 if isinstance(row,PurchaseInspection):body['lineReleaseFacts']=inspection_line_facts(row)
 if action=='confirm-receipt':
  selected_summary=next((x for x in candidates if line and x['purchaseOrderItemId']==line.pk),None)
  allowed=bool(line and selected_summary and selected_summary.get('sourceStatus')=='PROVIDED' and order.status in {'final_approved','received'} and Decimal(selected_summary['remainingReceivableQuantity'])>0)
  blocked='请先明确选择采购行。' if line is None else '本行已收齐、状态不允许或来源待核。'
 elif action=='create-inspection':
  allowed=row.status=='received' and not row.inspections.exists();blocked='本次收货未确认或已有检验记录。'
 elif action=='transition-inspection':
  allowed=row.status in {'pending','inspecting'} and row.inspector_employee_id==employee.pk;blocked='须由原检验责任人按原顺序办理本次范围。'
 else:
  available=body['lineReleaseFacts']['currentInboundEligibleQuantity']
  allowed=available is not None and Decimal(available)>0;blocked=body['lineReleaseFacts']['blockingReason']['message'] if not allowed else ''
 return {'source':body,'sourceFingerprint':_canonical_hash(body),'usagePurpose':PURPOSE,'currentStateSource':'server','businessWriteCount':0,
  'selectionRequired':line is None,'selectionStatusLabel':'请明确选择本次采购行' if line is None else '已绑定准确采购行',
  'actionAuthorization':{'allowed':allowed,'blockingReason':None if allowed else {'code':'RAW_ACTION_CONDITIONS_UNMET','message':blocked},
   'qualificationMeaning':'仅原岗位与本次准确来源读取；实际提交事务内重验，不授予其他动作'}}


def source_directory(*, user, action, query='', page=1, page_size=20):
 """Discover only original action-scoped sources; never grant a full-list read."""
 from django.db.models import Q
 from .scm_runtime_services import authorize_action, _fulfillment_actor
 user=actor(user)
 if action not in {'confirm-receipt','confirm-inbound'}:fail('RAW_DIRECTORY_ACTION_UNKNOWN','仅提供原收货及合格入库来源目录。',404)
 decision=authorize_action(user=user,action_code=ACTIONS[action],organization_id=user.company_id)
 if not decision.get('allowed'):fail(decision.get('decisionCode','PERMISSION_DENIED'),decision.get('reason','没有本目录读取资格。'),403)
 _fulfillment_actor(user=user,action_code=ACTIONS[action],company_id=user.company_id)
 if not isinstance(query,str) or len(query)>100 or type(page) is not int or page<1 or type(page_size) is not int or not 1<=page_size<=100:
  fail('RAW_DIRECTORY_INPUT_INVALID','查询文字最多100字，页码须为正整数，每页1至100条。',400)
 query=query.strip()
 if action=='confirm-receipt':
  rows=PurchaseOrder.objects.filter(company_id=user.company_id,status__in=['final_approved','received','inspected','stored']).order_by('pk')
  if query:rows=rows.filter(po_no__icontains=query)
 else:
  rows=PurchaseInspection.objects.filter(source_receipt__source_purchase_order__company_id=user.company_id).select_related('source_receipt__source_purchase_order').order_by('pk')
  if query:rows=rows.filter(Q(inspection_no__icontains=query)|Q(source_receipt__receipt_no__icontains=query)|Q(source_receipt__source_purchase_order__po_no__icontains=query))
 scoped=[]
 for row in rows:
  order=row if action=='confirm-receipt' else row.source_receipt.source_purchase_order
  try:_authorize_fulfillment(user=user,action_code=ACTIONS[action],order=order)
  except ScmRuntimeActionError as exc:
   if exc.http_status==403:continue
   raise
  scoped.append((row,order))
 result=[]
 for row,order in scoped[(page-1)*page_size:page*page_size]:
  item={'sourceType':type(row).__name__,'sourceId':row.pk,'purchaseOrderNo':order.po_no,
   'receiptNo':row.source_receipt.receipt_no if action=='confirm-inbound' else None,
   'inspectionNo':row.inspection_no if action=='confirm-inbound' else None,
   'contextUrl':f'/api/procurement/scm-runtime-actions/{action}/{row.pk}/?usagePurpose={PURPOSE}',
   'actionEligibilityMustBeReRead':True}
  try:
   context=source_context(user=user,action=action,object_id=row.pk)
   item.update(sourceStatus='PROVIDED',actionAuthorization=context['actionAuthorization'],selectionRequired=context['selectionRequired'])
   facts=context['source'].get('lineReleaseFacts')
   if facts:
    item['summary']={k:facts[k] for k in ['materialCode','materialName','unit','sourcePurchaseRequestNo','sourcePurchaseRequestLineNo','registeredReceivedQuantity','qualifiedQuantity','rejectedQuantity','successfullyInboundQuantity','currentInboundEligibleQuantity','qualityReleaseStatus','blockingReason']}
    item['statusLabel']='本检验范围不合格' if facts['qualityReleaseStatus']=='REJECTED' else '检验待判' if facts['qualityReleaseStatus']=='PENDING' else '合格量已用尽' if Decimal(facts['currentInboundEligibleQuantity'])==0 else '有本次合格可入量'
   else:
    lines=context['source']['lineCandidates'];known=[x for x in lines if x.get('sourceStatus')=='PROVIDED'];unknown=len(lines)-len(known)
    receivable=order.status in {'final_approved','received'} and any(Decimal(x['remainingReceivableQuantity'])>0 for x in known)
    item['summary']={'materials':[{k:x[k] for k in ['materialCode','materialName','unit','sourcePurchaseRequestNo','sourcePurchaseRequestLineNo']} for x in known],
     'sourcePendingLineCount':unknown,'receiptScopeStatus':'RECEIVABLE' if receivable else 'SOURCE_UNKNOWN' if unknown else 'EXHAUSTED' if known and all(Decimal(x['remainingReceivableQuantity'])==0 for x in known) else 'CONDITIONS_UNMET'}
    item['statusLabel']=('有可收采购行，部分来源待核' if unknown else '有可收采购行') if receivable else '采购行来源待核' if unknown else '本单采购行已收齐' if item['summary']['receiptScopeStatus']=='EXHAUSTED' else '当前收货条件未满足'
  except SOURCE_ERRORS as exc:
   if exc.http_status in {403,404}:raise
   item.update(sourceStatus='SOURCE_UNKNOWN',statusLabel='来源待核',summary=None,
    actionAuthorization={'allowed':False,'blockingReason':{'code':exc.code,'message':str(exc)}})
  result.append(item)
 return {'contractVersion':'PCE-WMS-SCOPED-SOURCE-DIRECTORY-V1','action':action,'usagePurpose':PURPOSE,
  'results':result,'count':len(scoped),'page':page,'pageSize':page_size,'businessWriteCount':0,
  'currentStateSource':'server','qualificationMeaning':'仅当前岗位原动作范围内找单；不是完整采购/质检目录授权，选中后必须重读原动作上下文。'}


def source_action_result(*,user,action,object_id,key,purchase_order_item_id=None):
 user=actor(user)
 if action not in ACTIONS or not isinstance(key,str) or not 1<=len(key)<=160:fail('RAW_ACTION_RESULT_INPUT_INVALID','须准确原动作及同次请求键。',400)
 request=MasterDataWriteRequest.objects.filter(organization_id=user.company_id,entity_type='ProductionRawStockAction',action_code=ACTIONS[action],idempotency_key=key,status='COMMITTED').first()
 if request:
  p=request.audit_metadata
  selected=p.get('purchaseOrderItemId')
  if purchase_order_item_id is not None and selected is not None and selected!=purchase_order_item_id:fail('RAW_RESULT_NOT_FOUND','本次结果不是所选采购行。',404)
  _source(action,object_id,user,line_id=selected if selected is not None else purchase_order_item_id)

  event=OrganizationOperatingAuditRecord.objects.filter(pk=request.result.get('auditId'),actor=user,organization_id=user.company_id).first()
  if p.get('sourceId')!=object_id or p.get('action')!=action or p.get('actorId')!=user.pk or not event or request.request_hash!=_canonical_hash(p):fail('RAW_RESULT_NOT_FOUND','原结果不属于当前办理人、来源及同次动作。',404)
 if not request:_source(action,object_id,user,line_id=purchase_order_item_id,allow_unselected=True)
 return {'resultState':'COMMITTED' if request else 'UNKNOWN','result':request.result if request else None,'historicalReceiptOnly':True,'executionAuthorizedByResult':False,'automaticReplayAllowed':False,'businessWriteCount':0}
def _order_move(order,target,user,action,decision,reason):
 if order.status==target:return
 state={'status':target,'orderId':order.pk}
 audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=action,target_type='PurchaseOrder',target_id=order.pk,target_label=order.po_no,reason=reason,
  before_snapshot={'status':order.status},after_snapshot={'contractVersion':CONTRACT,'authorization':decision,'state':state})
 transition(business_object=order,object_type='procurement.PurchaseOrder',source_state=order.status,target_state=target,action_code=action,operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={(order.status,target)},version_field=None)
def verify_order_transitions(order,rows):
 """Approval decisions stay four; all extra canonical fulfilment events remain checked."""
 previous='final_approved'
 allowed={('final_approved','received'),('received','inspected'),('inspected','stored')}
 for t in rows:
  ref=t.audit_reference.removeprefix('OrganizationOperatingAuditRecord:')
  a=OrganizationOperatingAuditRecord.objects.filter(pk=int(ref),target_type='PurchaseOrder',target_id=order.pk,organization_id=order.company_id,actor_id=t.operator_id,action_code=t.action_code).first() if ref.isdigit() else None
  snap=a.after_snapshot if a else {}
  if not a or snap.get('contractVersion')!=CONTRACT or not snap.get('authorization',{}).get('allowed') or snap.get('state',{}).get('status')!=t.target_state or t.source_state!=previous or (t.source_state,t.target_state) not in allowed:fail('RAW_ORDER_HISTORY_UNPROVEN','订单后续状态证明不完整，不能遮蔽异常历史。')
  previous=t.target_state
 if rows and order.status!=previous:fail('RAW_ORDER_HISTORY_UNPROVEN','订单当前状态不符合原后续转换。')

@transaction.atomic
def execute(*,user,action,object_id,payload):
 user=actor(user)
 if action not in ACTIONS or not isinstance(payload,dict):fail('RAW_ACTION_UNKNOWN','没有本次原料动作。',400)
 reason=payload.get('reason');key=payload.get('idempotencyKey')
 if not isinstance(reason,str) or not 1<=len(reason.strip())<=300 or not isinstance(key,str) or not 1<=len(key)<=160 or payload.get('usagePurpose')!=PURPOSE:fail('RAW_INTENT_REQUIRED','须明确正式生产用途、办理理由及同次动作键。',400)
 extra={'confirm-receipt':{'quantity'},'create-inspection':set(),'transition-inspection':{'inspectionAction','qualifiedQuantity'},'confirm-inbound':{'quantity','warehouseCode','locationCode','lotNumbers'}}[action]
 selected=payload.get('purchaseOrderItemId') if action=='confirm-receipt' else None
 if action=='confirm-receipt' and 'purchaseOrderItemId' in payload:extra=extra|{'purchaseOrderItemId'}
 if set(payload)!={'usagePurpose','reason','idempotencyKey','expectedSourceFingerprint'}|extra:fail('RAW_INTENT_INVALID','只接受本动作准确字段，不接受自报身份或状态。',400)
 row,order,line,decision,employee=_source(action,object_id,user,line_id=selected)
 request,created,_=_write_request(user=user,action_code=ACTIONS[action],entity_type='ProductionRawStockAction',key=key,request_body={'action':action,'sourceId':object_id,'actorId':user.pk,**payload})
 if not created and request.status=='COMMITTED':
  event=OrganizationOperatingAuditRecord.objects.filter(pk=request.result.get('auditId'),actor=user,organization_id=user.company_id).first()
  if not event:fail('RAW_RESULT_NOT_FOUND','同次动作不属于当前办理人。',404)
  return {**request.result,'historicalReceiptOnly':True,'businessWriteCount':0}
 row,order,line,decision,employee=_source(action,object_id,user,lock=True,line_id=selected)
 order=PurchaseOrder.objects.select_for_update().get(pk=order.pk)
 current=source_context(user=user,action=action,object_id=object_id,purchase_order_item_id=selected)
 if payload['expectedSourceFingerprint']!=current['sourceFingerprint']:fail('RAW_SOURCE_CHANGED','准确来源或版本已变化，请查询/刷新，不自动重放。')
 proof={'contractVersion':CONTRACT,'usagePurpose':PURPOSE,'companyId':order.company_id,'orderId':order.pk,'orderItemId':line.pk,'materialId':line.material_id,'uomId':line.material.base_uom_id,'unitPrecision':line.material.base_uom.decimal_places}
 if action=='confirm-receipt':
  if order.status not in {'final_approved','received'}:fail('RAW_ORDER_STATE_INVALID','原订单当前状态不允许收货。')
  qty=quantity(payload['quantity']);prior=sum((x.quantity for x in _line_receipts(order,line)),Decimal('0'))
  original_quantity_field(type(line),'actual_quantity',prior+qty)
  if qty!=qty.quantize(Decimal(1).scaleb(-line.material.base_uom.decimal_places)) or prior+qty>line.quantity:fail('RAW_RECEIPT_QUANTITY_EXCEEDED','收货超出准确订单行/单位范围。')
  items=[{'purchaseOrderItemId':line.pk,'materialId':line.material_id,'materialCode':line.material.code,'unit':line.unit_snapshot,'quantity':str(qty),'rawMaterialProof':proof}]
  value=initial(model=PurchaseReceipt,initial_state='draft',receipt_no=_next_number('RC',PurchaseReceipt,'receipt_no'),source_purchase_order=order,quantity=qty,amount=(line.amount*qty/line.quantity).quantize(Decimal('.01')),items=items,receipt_date=_business_date(),operator_employee=employee,operator_account_id=user.pk)
  audit_step(value,ACTIONS[action],user,decision,'draft',reason)
  event=audit_step(value,ACTIONS[action],user,decision,'received',reason,'draft')
  line.actual_quantity=prior+qty;line.actual_arrival_date=_business_date();line.actual_unit_price=line.unit_price_snapshot or line.unit_price;line.actual_amount=(line.actual_unit_price*line.actual_quantity).quantize(Decimal('.01'));line.save(update_fields=['actual_quantity','actual_arrival_date','actual_unit_price','actual_amount'])
  _refresh_order(order,user,ACTIONS[action],decision,reason)
 elif action=='create-inspection':
  if row.status!='received' or row.inspections.exists():fail('RAW_INSPECTION_STATE_INVALID','收货未确认或已有检验记录，不重复建立。')
  items=[{**x,'rawMaterialProof':{**proof,'receiptId':row.pk}} for x in row.items]
  value=initial(model=PurchaseInspection,initial_state='pending',inspection_no=_next_number('IQC',PurchaseInspection,'inspection_no'),source_receipt=row,quantity=row.quantity,amount=row.amount,items=items,inspector_employee=employee,inspector_account_id=user.pk)
  event=audit_step(value,ACTIONS[action],user,decision,'pending',reason)
 elif action=='transition-inspection':
  value=row;intent=payload['inspectionAction'];target={'START':'inspecting','QUALIFY':'qualified','REJECT':'rejected'}.get(intent)
  allowed={('pending','inspecting'),('inspecting','qualified'),('inspecting','rejected')}
  if (value.status,target) not in allowed or value.inspector_employee_id!=employee.pk:fail('RAW_INSPECTION_STATE_INVALID','原检验顺序或原检验责任人不符合。')
  before=value.status
  if target in {'qualified','rejected'}:
   qty=quantity(payload['qualifiedQuantity']) if target=='qualified' else Decimal('0')
   if qty>value.quantity or qty!=qty.quantize(Decimal(1).scaleb(-line.material.base_uom.decimal_places)):fail('RAW_QUALITY_QUANTITY_INVALID','合格量超范围或单位精度不符。')
   value.qualified_quantity=qty;value.rejected_quantity=value.quantity-qty;value.inspection_date=_business_date();value.save(update_fields=['qualified_quantity','rejected_quantity','inspection_date'])
  event=audit_step(value,ACTIONS[action],user,decision,target,reason,before)
  _refresh_order(order,user,ACTIONS[action],decision,reason)
 else:
  if row.status!='qualified':fail('RAW_QUALITY_NOT_RELEASED','原检验尚未形成合格事实。')
  qty=quantity(payload['quantity']);prior,_=_successful_inbounds(row)
  if prior+qty>row.qualified_quantity or qty!=qty.quantize(Decimal(1).scaleb(-line.material.base_uom.decimal_places)):fail('RAW_INBOUND_QUANTITY_EXCEEDED','本次入库超出原合格量或单位精度。')
  wh=Warehouse.objects.filter(code=payload['warehouseCode'],company_id=user.company_id,is_active=True,usage_purpose=PURPOSE).first()
  loc=WarehouseLocation.objects.filter(warehouse=wh,code=payload['locationCode'],is_active=True).first() if wh else None
  lots=payload['lotNumbers'];lot_no=lots.get(str(line.material_id)) if isinstance(lots,dict) and set(lots)=={str(line.material_id)} else None
  if not wh or not loc or not isinstance(lot_no,str) or not 1<=len(lot_no.strip())<=100:fail('RAW_WAREHOUSE_LOT_UNPROVEN','须明确原范围正式用途仓、库位和本次准确原料批号，不自动选批。')
  warehouse_resource(wh,loc)
  lot_no=lot_no.strip()
  lot=InventoryLot.all_objects.select_for_update().filter(warehouse=wh,company_id=user.company_id,material_id=line.material_id,lot_no=lot_no).first()
  if lot and (not lot.is_active or lot.usage_purpose!=PURPOSE):fail('RAW_WAREHOUSE_LOT_UNPROVEN','既有批次用途或状态不符，不转换旧批次。')
  if not lot:
   lot=InventoryLot.all_objects.create(warehouse=wh,company_id=user.company_id,material_id=line.material_id,lot_no=lot_no,usage_purpose=PURPOSE,is_active=True)
   registration=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=ACTIONS[action],target_type='InventoryLot',target_id=lot.pk,target_label=lot.lot_no,reason=reason,
    after_snapshot={'contractVersion':CONTRACT,'authorization':decision,'lotProof':{**proof,'warehouseId':wh.pk,'lotId':lot.pk,'lotNo':lot_no,'receiptId':row.source_receipt_id,'inspectionId':row.pk}})
  else:
   registration=OrganizationOperatingAuditRecord.objects.filter(target_type='InventoryLot',target_id=lot.pk,organization_id=user.company_id,action_code=ACTIONS[action],after_snapshot__contractVersion=CONTRACT).order_by('pk').first()
   if not registration:fail('RAW_LOT_REGISTRATION_UNPROVEN','旧批次没有本原生登记证明，保留待核，不补造历史。')
  items=[{'purchaseOrderItemId':line.pk,'materialId':line.material_id,'materialCode':line.material.code,'unit':line.unit_snapshot,'quantity':str(qty),'lotNo':lot.lot_no,'rawMaterialProof':{**proof,'receiptId':row.source_receipt_id,'inspectionId':row.pk,'lotRegistrationAuditId':registration.pk}}]
  value=initial(model=WarehouseInbound,initial_state='planned',inbound_no=_next_number('IN',WarehouseInbound,'inbound_no'),source_inspection=row,quantity=qty,amount=row.amount,items=items,warehouse=wh,location=loc,inbound_date=_business_date(),operator_employee=employee,operator_account_id=user.pk,usage_purpose=PURPOSE)
  audit_step(value,ACTIONS[action],user,decision,'planned',reason);audit_step(value,ACTIONS[action],user,decision,'processing',reason,'planned')
  from .inventory_posting import post_inbound_stock
  post_inbound_stock(inbound=value,warehouse=wh,location=loc,material_id=line.material_id,lot=lot,quantity=qty,employee=employee,user=user)
  event=audit_step(value,ACTIONS[action],user,decision,'completed',reason,'processing')
  _refresh_order(order,user,ACTIONS[action],decision,reason)
 result={'objectId':value.pk,'objectType':type(value).__name__,'objectNo':value.object_no,'status':value.status,'auditId':event.pk,'usagePurpose':PURPOSE,'businessWriteCount':1}
 _commit_request(request,result);return result

def post_raw_stock(*,inbound,warehouse,location,material_id,lot,quantity:Decimal,employee,user):
 from django.db import connection
 if not connection.in_atomic_block or inbound.status!='processing' or inbound.usage_purpose!=PURPOSE or not inbound.source_inspection_id or inbound.production_transfer_id:fail('RAW_POSTING_BOUNDARY_INVALID','原料记账须在准确原入库事务及处理中阶段。')
 verify_history(inbound);verify_history(inbound.source_inspection);verify_history(inbound.source_inspection.source_receipt)
 p=inbound.items[0]['rawMaterialProof']
 if p['materialId']!=material_id or p['companyId']!=warehouse.company_id or warehouse.usage_purpose!=PURPOSE or not location or location.warehouse_id!=warehouse.pk or not lot or lot.warehouse_id!=warehouse.pk or lot.material_id!=material_id or lot.company_id!=warehouse.company_id or lot.usage_purpose!=PURPOSE:fail('RAW_POSTING_SOURCE_INVALID','原料来源企业、仓储、批次及用途不一致。')
 qty=globals()['quantity'](quantity)
 lookup={'warehouse':warehouse,'material_id':material_id,'location':location,'lot':lot,'usage_purpose':PURPOSE}
 b,_=InventoryBalance.objects.select_for_update().get_or_create(**lookup,defaults={'quantity':Decimal('0')});before=b.quantity;b.quantity=original_quantity_field(InventoryBalance,'quantity',before+qty);b.save(update_fields=['quantity','updated_at'])
 return b,InventoryTransaction.objects.create(transaction_no=_next_number('IT',InventoryTransaction,'transaction_no'),source_inbound=inbound,**lookup,direction='IN',quantity=qty,before_quantity=before,after_quantity=b.quantity,operator_employee=employee,operator_account_id=user.pk)

def stock_proof(tx):
 ib=tx.source_inbound;wh=tx.warehouse;lot=tx.lot;m=tx.material
 if not ib:fail('RAW_STOCK_SOURCE_UNPROVEN','库存流水缺少准确原生入库来源，不能按余额推断可分配。')
 if tx.direction!='IN' or tx.usage_purpose!=PURPOSE or ib.usage_purpose!=PURPOSE or ib.status!='completed' or not ib.source_inspection_id or ib.production_transfer_id or not lot or lot.usage_purpose!=PURPOSE or not lot.is_active or not wh.is_active or wh.usage_purpose!=PURPOSE or lot.company_id!=wh.company_id or lot.warehouse_id!=wh.pk or lot.material_id!=m.pk or m.company_id!=wh.company_id or m.material_type=='finished' or not m.is_active or not tx.location_id or not tx.location.is_active or tx.location.warehouse_id!=wh.pk or not m.base_uom_id:fail('RAW_STOCK_SOURCE_UNPROVEN','原料用途、批次、仓储、准确入库或物料证明缺失。')
 if lot.expiry_date and lot.expiry_date<_business_date() or lot.reinspection_date and lot.reinspection_date<_business_date():fail('RAW_STOCK_QUALITY_RECHECK_REQUIRED','原批次有效/复检条件待核，不自动放行。')
 warehouse_resource(wh,tx.location)
 inspection=ib.source_inspection;receipt=inspection.source_receipt;order=receipt.source_purchase_order
 line=_order_line(order,row=receipt);h=[verify_history(x) for x in [receipt,inspection,ib]]
 p=ib.items[0].get('rawMaterialProof',{}) if len(ib.items)==1 else {}
 registration=OrganizationOperatingAuditRecord.objects.filter(pk=p.get('lotRegistrationAuditId'),organization_id=wh.company_id,target_type='InventoryLot',target_id=lot.pk,action_code=ACTIONS['confirm-inbound']).first()
 lp=registration.after_snapshot.get('lotProof',{}) if registration else {}
 if not registration or registration.after_snapshot.get('contractVersion')!=CONTRACT or not registration.after_snapshot.get('authorization',{}).get('allowed') or any(lp.get(k)!=v for k,v in {'companyId':wh.company_id,'materialId':m.pk,'uomId':m.base_uom_id,'warehouseId':wh.pk,'lotId':lot.pk,'lotNo':lot.lot_no,'usagePurpose':PURPOSE}.items()):fail('RAW_LOT_REGISTRATION_UNPROVEN','批次原生登记与当前身份不一致，保留占用待核。')
 if inspection.status!='qualified' or receipt.status!='received' or order.company_id!=wh.company_id or p.get('contractVersion')!=CONTRACT or p.get('usagePurpose')!=PURPOSE or p.get('companyId')!=wh.company_id or p.get('orderItemId')!=line.pk or p.get('receiptId')!=receipt.pk or p.get('inspectionId')!=inspection.pk or p.get('materialId')!=m.pk or p.get('uomId')!=m.base_uom_id or p.get('unitPrecision')!=m.base_uom.decimal_places or tx.material_id!=line.material_id or tx.warehouse_id!=ib.warehouse_id or tx.location_id!=ib.location_id or ib.items[0].get('lotNo')!=lot.lot_no or globals()['quantity'](ib.items[0].get('quantity'))!=tx.quantity or ib.quantity!=tx.quantity or tx.after_quantity-tx.before_quantity!=tx.quantity:fail('RAW_STOCK_SOURCE_CHANGED','原料检验、单位、版本或库存来源已变化，保留占用待核。')
 inbound_total,_=_successful_inbounds(inspection)
 if inbound_total>inspection.qualified_quantity:fail('RAW_STOCK_QUALITY_SCOPE_INVALID','本检验累计入库超过准确合格范围。')
 identity={'companyId':wh.company_id,'warehouseId':wh.pk,'locationId':tx.location_id,'lotId':lot.pk,'materialId':m.pk,'uomId':m.base_uom_id,'usagePurpose':PURPOSE}
 frozen={**identity,'transactionId':tx.pk,'transactionNo':tx.transaction_no,'inboundId':ib.pk,'receiptId':receipt.pk,'inspectionId':inspection.pk,'quantity':str(tx.quantity),'before':str(tx.before_quantity),'after':str(tx.after_quantity),'history':h,'sourceProof':p,'lotNo':lot.lot_no,'expiry':str(lot.expiry_date),'reinspection':str(lot.reinspection_date)}
 return {'identity':identity,'proof':frozen,'sourceFingerprint':_canonical_hash(frozen)}

