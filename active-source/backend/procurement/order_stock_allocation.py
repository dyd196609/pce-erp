"""Native order reservations of existing WMS receipts. No stock posting or copied balance."""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from planning.order_batch_service import actor_line, fail, line_identity, range_values, number, required_text
from planning.finished_goods_permissions import warehouse_qualification
from pde.product_design_service import _write_request, _commit_request, _canonical_hash
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state, record_projected_business_transition, transition_business_object
from .models import InventoryTransaction, InventoryBalance, OrderStockAllocation
from pde.order_lifecycle_source_projection import terminal_closure_read

CONTRACT = 'PCE-ORDER-STOCK-ALLOCATION-V1'
PERMISSION = 'warehouse.production.putaway'


def receipt_facts(receipt, *, lock=False):
    inbound, lot, warehouse = receipt.source_inbound, receipt.lot, receipt.warehouse
    if (receipt.direction != 'IN' or receipt.quantity<=0 or receipt.after_quantity-receipt.before_quantity != receipt.quantity
        or receipt.usage_purpose == 'TEST_BUSINESS' or inbound.usage_purpose != receipt.usage_purpose
        or inbound.status not in {'completed','closed'} or inbound.warehouse_id != receipt.warehouse_id
        or not lot or not lot.is_active or lot.company_id != warehouse.company_id
        or lot.material_id != receipt.material_id or lot.warehouse_id != warehouse.pk
        or not warehouse.is_active or lot.usage_purpose != receipt.usage_purpose):
        fail('STOCK_RECEIPT_UNPROVEN', '库存来源、批次、用途或原生入库状态不能证明有效实物。')
    if receipt.location_id and (receipt.location.warehouse_id != warehouse.pk or not receipt.location.is_active):
        fail('STOCK_RECEIPT_UNPROVEN', '入库库位无效或不属于本仓库。')
    if (lot.expiry_date and lot.expiry_date < timezone.localdate()):
        fail('STOCK_LOT_EXPIRED', '本批次已失效，不能计入有效分配。')
    if (receipt.material.company_id != warehouse.company_id or not receipt.material.base_uom_id
        or receipt.material.material_type!='finished' or not receipt.material.is_active
        or receipt.material.base_uom.company_id!=warehouse.company_id):
        fail('STOCK_RECEIPT_UNPROVEN', '库存产品企业或单位缺失。')
    # A formal manufacturing receipt remains attributable to its own approved
    # Demand. Without a native surplus/release proof, allocating it again would
    # count the same product in two orders (or twice in the same order).
    if inbound.production_transfer_id:
        fail('STOCK_MANUFACTURING_SCOPE_RESERVED', '该成品已绑定原制造批覆盖；缺少可释放剩余范围证明，不能再次增加订单覆盖。')
    if not inbound.source_inspection_id:
        fail('STOCK_RECEIPT_UNPROVEN', '库存缺少原生采购或制造来源。')
    inspection=inbound.source_inspection
    if inspection.status != 'qualified':
        fail('STOCK_RECEIPT_UNPROVEN', '原采购检验尚未形成有效接受事实。')
    if inspection.source_receipt.source_purchase_order.company_id!=warehouse.company_id:
        fail('STOCK_RECEIPT_UNPROVEN','采购来源企业不一致。')
    native_audits=OrganizationOperatingAuditRecord.objects.filter(organization_id=warehouse.company_id,
        target_type='WarehouseInbound',target_id=inbound.pk,action_code='warehouse.purchase.putaway',
        actor_id=receipt.operator_account_id,after_snapshot__authorization__allowed=True,
        after_snapshot__state__warehouseCode=warehouse.code)
    matches=[event for event in native_audits if number(event.after_snapshot.get('state',{}).get('quantity'))==inbound.quantity]
    event=matches[0] if len(matches)==1 else None
    matched=[row for row in inbound.items if row.get('materialId')==receipt.material_id and row.get('lotNo')==lot.lot_no]
    if (not event or sum((number(row.get('quantity')) for row in matched),Decimal('0'))!=receipt.quantity
        or any(row.get('unit') not in {receipt.material.base_uom.code,receipt.material.base_uom.name} for row in matched)):
        fail('STOCK_RECEIPT_AUDIT_UNPROVEN','库存缺少原生入库审计、准确批次明细或正式单位证明。')
    balances=InventoryBalance.objects.filter(warehouse_id=receipt.warehouse_id, material_id=receipt.material_id,
        location_id=receipt.location_id, lot_id=receipt.lot_id, usage_purpose=receipt.usage_purpose)
    if lock:balances=balances.select_for_update()
    balance=balances.first()
    if not balance:
        fail('STOCK_BALANCE_UNPROVEN', '未取得同产品、批次、库位及用途的原库存余额。')
    allocated=OrderStockAllocation.objects.filter(source_transaction=receipt, status='active').aggregate(q=Sum('quantity'))['q'] or Decimal('0')
    dimensional=OrderStockAllocation.objects.filter(status='active',source_transaction__warehouse_id=receipt.warehouse_id,
        source_transaction__material_id=receipt.material_id,source_transaction__lot_id=receipt.lot_id,
        source_transaction__location_id=receipt.location_id).aggregate(q=Sum('quantity'))['q'] or Decimal('0')
    if allocated>receipt.quantity or dimensional>balance.quantity:
        fail('STOCK_ALLOCATION_EXCEEDS_AVAILABLE', '有效分配已超过可证明的来源或当前实物余额。')
    fields=('id','source_inbound_id','warehouse_id','material_id','location_id','lot_id','direction',
        'quantity','before_quantity','after_quantity','usage_purpose','operator_account_id','occurred_at')
    frozen={f:str(getattr(receipt,f)) for f in fields}
    return {'transaction': frozen, 'transactionHash': _canonical_hash(frozen),
        'warehouseId':warehouse.pk,'materialId':receipt.material_id,'lotId':lot.pk,
        'lotNo':lot.lot_no,'uomId':receipt.material.base_uom_id,'usagePurpose':receipt.usage_purpose,
        'inboundAuditId':event.pk,'availableForReservation':str(min(receipt.quantity-allocated,balance.quantity-dimensional))}


def allocation_facts(allocation, *, lock=False, validate_current=True):
    item=allocation.sales_order_item
    snapshot=allocation.source_snapshot
    event=allocation.audit_record
    if (allocation.company_id != item.sales_order.company_id or event.organization_id!=allocation.company_id
        or event.target_type!='OrderStockAllocation' or event.target_id!=allocation.pk
        or event.action_code!=PERMISSION or not event.after_snapshot.get('authorization',{}).get('allowed')
        or event.after_snapshot.get('sourceSnapshot')!=snapshot
        or any(snapshot.get(k)!=v for k,v in line_identity(item).items())
        or snapshot.get('quantity')!=str(allocation.quantity) or snapshot.get('stockUomId')!=allocation.uom_id
        or snapshot.get('rangeStart')!=str(allocation.range_start) or snapshot.get('rangeEnd')!=str(allocation.range_end)
        or snapshot.get('sourceTransactionId')!=allocation.source_transaction_id
        or snapshot.get('substitutionApprovalId')!=allocation.substitution_approval_id):
        fail('STOCK_ALLOCATION_AUDIT_UNPROVEN', '库存分配缺少一致的准确订单行和原生审计。')
    history=list(BusinessStateTransition.objects.filter(object_type='OrderStockAllocation',object_id=allocation.pk).order_by('pk'))
    if not history or history[0].source_state!='' or history[0].target_state!='active' or history[-1].target_state!=allocation.status:
        fail('STOCK_ALLOCATION_STATE_UNPROVEN', '库存分配状态缺少原生状态历史。')
    for row in history:
        if not OrganizationOperatingAuditRecord.objects.filter(pk=int(row.audit_reference.split(':')[-1]),
            organization_id=allocation.company_id,target_type='OrderStockAllocation',target_id=allocation.pk).exists():
            fail('STOCK_ALLOCATION_STATE_UNPROVEN', '库存分配状态缺少原审计。')
    from masterdata.models import MasterDataWriteRequest
    request=MasterDataWriteRequest.objects.filter(pk=snapshot.get('writeRequestId'),organization_id=allocation.company_id,
        action_code=PERMISSION,entity_type='OrderStockAllocate',status='COMMITTED').first()
    if (not request or request.result.get('allocationId')!=allocation.pk or request.result.get('auditId')!=event.pk
        or request.request_hash!=_canonical_hash(request.audit_metadata)):
        fail('STOCK_ALLOCATION_AUDIT_UNPROVEN','库存分配缺少一致的原生提交结果。')
    if not validate_current:
        return {'allocationId':allocation.pk,'active':allocation.status=='active'}
    if allocation.status!='active':
        return {'allocationId':allocation.pk,'active':False,'status':allocation.status,'quantity':None,'targetQuantity':None,
            'statusLabel':allocation.get_status_display(),'allocationRegisteredAt':allocation.created_at.isoformat(),
            'recordedQuantity':str(allocation.quantity),'uomId':allocation.uom_id,
            'rangeStart':str(allocation.range_start),'rangeEnd':str(allocation.range_end),
            'sourceTransactionId':allocation.source_transaction_id,'auditId':event.pk,
            'stateHistory':[{'transitionId':row.pk,'sourceState':row.source_state,'targetState':row.target_state,
                'auditReference':row.audit_reference} for row in history]}
    current=receipt_facts(allocation.source_transaction,lock=lock)
    if snapshot.get('receiptHash')!=current['transactionHash']:
        fail('STOCK_RECEIPT_CHANGED', '原库存来源流水发生变化。')
    start,end=range_values(item,allocation.range_start,allocation.range_end)
    substitution=None
    if allocation.source_transaction.material_id!=item.material_id:
        from pde.finished_goods_substitution import substitution_proof
        substitution=substitution_proof(item=item,approval_id=allocation.substitution_approval_id,
            material_id=allocation.source_transaction.material_id,stock_uom_id=allocation.uom_id,
            start=start,end=end,quantity=allocation.quantity)
    elif allocation.uom_id!=item.uom_id or allocation.quantity!=end-start or allocation.substitution_approval_id:
        fail('STOCK_ALLOCATION_UNIT_MISMATCH', '同产品分配单位、范围或数量不一致。')
    if snapshot.get('substitutionProof')!=substitution:
        fail('STOCK_SUBSTITUTION_CHANGED', '精确替代批准或换算证明发生变化。')
    return {'allocationId':allocation.pk,'active':True,'status':'active','quantity':str(allocation.quantity),
        'statusLabel':allocation.get_status_display(),'allocationRegisteredAt':allocation.created_at.isoformat(),
        'allocationRegisteredAtMeaning':'库存分配登记时间；不是现场制造完成时间',
        'targetQuantity':str(end-start),'rangeStart':str(start),'rangeEnd':str(end),'uomId':allocation.uom_id,
        'uomLabel':allocation.uom.name,'targetUomId':item.uom_id,'targetUomLabel':item.uom.name,
        'materialId':allocation.source_transaction.material_id,
        'warehouseId':current['warehouseId'],'lotId':current['lotId'],'lotNo':current['lotNo'],
        'sourceTransactionId':allocation.source_transaction_id,'auditId':event.pk,'substitutionProof':substitution,
        'receiptRecordedAt':allocation.source_transaction.occurred_at.isoformat(),'receiptRecordedAtMeaning':'原入库流水发生时间',
        'completionMeaning':'SUPPLY_RESERVATION_ONLY; no shipment/receipt/fulfilment inference'}


@terminal_closure_read
def _allocations_for_line(_unused, item, *, lock=False, include_inactive=False):
    rows=OrderStockAllocation.objects.filter(sales_order_item=item).select_related(
        'sales_order_item__sales_order','source_transaction__source_inbound__source_inspection',
        'source_transaction__material','source_transaction__lot','source_transaction__warehouse',
        'source_transaction__location','audit_record')
    if lock:rows=rows.select_for_update()
    facts=[allocation_facts(row,lock=lock) for row in rows]
    return facts if include_inactive else [fact for fact in facts if fact['active']]


def allocations_for_line(item, *, lock=False, include_inactive=False):
    return _allocations_for_line(None,item,lock=lock,include_inactive=include_inactive)


@transaction.atomic
def allocate(*, user, item_id, payload, key):
    actor,item,decision=actor_line(user,item_id,PERMISSION,lock=True)
    warehouse_qualification(actor,purpose='PRODUCTION_USE')
    allowed={'sourceTransactionId','quantity','uomId','rangeStart','rangeEnd','substitutionApprovalId','reason'}
    if not isinstance(payload,dict) or set(payload)!=allowed:
        fail('STOCK_ALLOCATION_INPUT_INVALID','必须准确指定库存来源、数量单位、范围和依据。',400)
    required_text(payload['reason'],code='STOCK_ALLOCATION_INPUT_INVALID')
    if any(type(payload[name]) is not int or payload[name]<=0 for name in ('sourceTransactionId','uomId')) or (
        payload['substitutionApprovalId'] is not None and (type(payload['substitutionApprovalId']) is not int or payload['substitutionApprovalId']<=0)):
        fail('STOCK_ALLOCATION_INPUT_INVALID','库存来源、单位及批准必须使用明确的正式身份。',400)
    from sales.supply_admission_service import supply_admission_facts
    if supply_admission_facts(item)['supplyBranch']!='MAKE':
        fail('STOCK_ALLOCATION_NOT_APPLICABLE','本合同仅核定适用制造订单的供给，不改变其他业务模式。')
    if item.material.material_type!='finished':
        fail('STOCK_ALLOCATION_NOT_APPLICABLE','本合同只证明准确成品SKU，不把BOM材料分配当成成品覆盖。')
    if item.sales_order.status not in {'confirmed','approved','engineering','manufacturing_ready','in_progress'}:
        fail('STOCK_ALLOCATION_ORDER_STATE_INVALID','当前订单状态不允许新分配。')
    from sales.services import _require_crm_admission
    _require_crm_admission(company_id=actor.company_id,order=item.sales_order,lock=True)
    request,created,_=_write_request(user=actor,action_code=PERMISSION,entity_type='OrderStockAllocate',key=key,
        request_body={'orderId':item.sales_order_id,'itemIds':[item.pk],**payload})
    if not created and request.status=='COMMITTED':
        return {**request.result,'idempotent':True}
    start,end=range_values(item,payload['rangeStart'],payload['rangeEnd']);quantity=number(payload['quantity'])
    receipt=InventoryTransaction.objects.select_for_update().select_related('source_inbound__source_inspection',
        'material','lot','warehouse','location').filter(pk=payload['sourceTransactionId'],warehouse__company_id=actor.company_id).first()
    if not receipt:fail('STOCK_SOURCE_NOT_FOUND','库存来源不存在或不属于当前企业。',404)
    facts=receipt_facts(receipt,lock=True)
    if quantity!=quantity.quantize(Decimal(1).scaleb(-receipt.material.base_uom.decimal_places)):
        fail('STOCK_ALLOCATION_UNIT_MISMATCH','实物分配数量不符合原库存基本单位精度。')
    if payload['uomId']!=facts['uomId'] or quantity>number(facts['availableForReservation'],zero=True):
        fail('STOCK_ALLOCATION_EXCEEDS_AVAILABLE','分配单位不符或超过可证明实物。')
    from planning.order_batch_service import assert_free_range
    assert_free_range(item,start,end)
    substitution=None
    if receipt.material_id!=item.material_id:
        from pde.finished_goods_substitution import substitution_proof
        substitution=substitution_proof(item=item,approval_id=payload['substitutionApprovalId'],material_id=receipt.material_id,
            stock_uom_id=payload['uomId'],start=start,end=end,quantity=quantity)
    elif payload['uomId']!=item.uom_id or quantity!=end-start or payload['substitutionApprovalId']:
        fail('STOCK_ALLOCATION_UNIT_MISMATCH','同产品数量、单位或范围不一致。')
    snapshot={**line_identity(item),'contractVersion':CONTRACT,'sourceTransactionId':receipt.pk,
        'receiptHash':facts['transactionHash'],'quantity':str(quantity),'stockUomId':payload['uomId'],
        'rangeStart':str(start),'rangeEnd':str(end),'substitutionApprovalId':payload['substitutionApprovalId'],
        'substitutionProof':substitution,'writeRequestId':request.pk}
    event=OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,
        action_code=PERMISSION,target_type='OrderStockAllocation',target_id=0,target_label=f'订单行{item.pk}',
        reason=payload['reason'],after_snapshot={'sourceSnapshot':snapshot,'authorization':decision})
    allocation=create_business_object_with_initial_state(model=OrderStockAllocation,initial_state='active',
        company_id=actor.company_id,sales_order_item=item,source_transaction=receipt,quantity=quantity,uom_id=payload['uomId'],
        range_start=start,range_end=end,substitution_approval_id=payload['substitutionApprovalId'],source_snapshot=snapshot,
        audit_record=event,created_by=actor)
    event.target_id=allocation.pk;event.save(update_fields=['target_id'])
    record_projected_business_transition(object_type='OrderStockAllocation',object_id=allocation.pk,source_state='',target_state='active',
        action_code=PERMISSION,operator=actor,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',allowed_transitions={('','active')})
    result={'allocationId':allocation.pk,'auditId':event.pk,'idempotent':False}
    _commit_request(request,result)
    result['allocation']=allocation_facts(allocation,lock=True)
    return result


@transaction.atomic
def release(*,user,allocation_id,payload,key):
    row=OrderStockAllocation.objects.select_related('sales_order_item__sales_order').filter(
        pk=allocation_id,company_id=user.company_id).first()
    if not row:fail('STOCK_ALLOCATION_NOT_FOUND','库存分配不存在或不属于当前企业。',404)
    actor,item,decision=actor_line(user,row.sales_order_item_id,PERMISSION,lock=True)
    warehouse_qualification(actor,purpose='PRODUCTION_USE')
    row=OrderStockAllocation.objects.select_for_update().get(pk=row.pk)
    if (not isinstance(payload,dict) or set(payload)!={'expectedVersion','reason'}
        or type(payload['expectedVersion']) is not int or payload['expectedVersion']<=0):
        fail('STOCK_RELEASE_INPUT_INVALID','释放须有原版本和明确依据。',400)
    required_text(payload['reason'],code='STOCK_RELEASE_INPUT_INVALID')
    request,created,_=_write_request(user=actor,action_code=PERMISSION,entity_type='OrderStockRelease',key=key,
        request_body={'allocationId':row.pk,'orderId':item.sales_order_id,**payload})
    if not created and request.status=='COMMITTED':return {**request.result,'idempotent':True}
    # Even an expired/invalid lot must be releasable; verify the original immutable
    # registration and state separately from current physical availability.
    if row.status!='active' or row.version!=payload['expectedVersion']:
        fail('STOCK_RELEASE_VERSION_CONFLICT','分配已变化，请先查询同次动作或刷新事实。')
    allocation_facts(row,validate_current=False)
    if item.sales_order.status in {'completed','closed'}:
        fail('STOCK_RELEASE_TERMINAL_ORDER','原订单已终态，须先按正式更正合同处理，不能撤去完成依据。')
    event=OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,
        action_code=PERMISSION,target_type='OrderStockAllocation',target_id=row.pk,target_label=f'分配{row.pk}',
        reason=payload['reason'],before_snapshot={'status':row.status,'version':row.version},
        after_snapshot={'status':'released','authorization':decision,'originalAuditId':row.audit_record_id})
    transition_business_object(business_object=row,object_type='OrderStockAllocation',source_state='active',target_state='released',
        action_code=PERMISSION,operator=actor,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',allowed_transitions={('active','released')})
    result={'allocationId':row.pk,'auditId':event.pk,'status':'released','idempotent':False}
    _commit_request(request,result)
    return result
