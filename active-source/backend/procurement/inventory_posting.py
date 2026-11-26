"""Shared existing WMS balance/transaction posting, with an explicit source purpose."""
from decimal import Decimal
from django.db import connection
from django.core.exceptions import ValidationError
from .inventory_purpose import TEST,LEGACY,_write_scope

def post_inbound_stock(*,inbound,warehouse,location,material_id,lot,quantity,employee,user):
    if inbound.usage_purpose=='PRODUCTION_USE' and inbound.source_inspection_id and not inbound.production_transfer_id:
        from .material_stock_authority import post_raw_stock
        return post_raw_stock(inbound=inbound,warehouse=warehouse,location=location,material_id=material_id,lot=lot,quantity=quantity,employee=employee,user=user)
    from .models import InventoryBalance,InventoryTransaction
    from masterdata.models import Material
    from .scm_runtime_services import _next_number
    if not connection.in_atomic_block:raise ValidationError('库存记账须与来源入库在同一事务内。')
    purpose=inbound.usage_purpose;test=purpose==TEST;formal=purpose=='PRODUCTION_USE' and bool(inbound.production_transfer_id)
    if inbound.warehouse_id!=warehouse.pk or inbound.location_id!=(location.pk if location else None):
        raise ValidationError('库存来源仓及库位与入库单不一致。')
    material=Material.objects.get(pk=material_id)
    if material.company_id!=warehouse.company_id or location and location.warehouse_id!=warehouse.pk:
        raise ValidationError('库存物料、仓、库位必须在同公司及准确仓范围。')
    if test or formal:
        if (test and not _write_scope.get() or inbound.status!='processing' or not inbound.production_transfer_id or inbound.source_inspection_id
            or warehouse.usage_purpose!=purpose or not lot or lot.usage_purpose!=purpose
            or lot.company_id!=warehouse.company_id or lot.material_id!=material_id or lot.warehouse_id!=warehouse.pk):
            raise ValidationError('测试入库仅能消费同用途的生产成品来源和独立TEST批次。')
        transfer=inbound.production_transfer
        if (transfer.status!='in_transit' or transfer.receiver_id!=user.pk or transfer.material_id!=material_id
            or Decimal(transfer.quantity)!=quantity or material.base_uom_id!=transfer.uom_id
            or transfer.work_order.usage_purpose!=purpose or transfer.company_id!=warehouse.company_id
            or transfer.source_snapshot.get('usagePurpose')!=purpose):raise ValidationError('库存记账须对应本次真实成品在途来源、指定收方及原产品单位。')
        if formal:
            from planning.finished_goods_authority import order_for,verify_frozen_closure
            from planning.operation_handover_core import verify_record
            verify_record(transfer)
            order=order_for(user,transfer.work_order_id)
            verify_frozen_closure(order,transfer.source_snapshot['executionClosure'])
        value=Decimal(quantity)
        if value<=0 or value!=value.quantize(Decimal('0.0001')):raise ValidationError('测试库存数量必须为正且不超过原WMS精度，不舍入。')
        manager=InventoryBalance.all_objects
    else:
        if warehouse.usage_purpose==TEST or lot and lot.usage_purpose==TEST:
            raise ValidationError('正式／历史入库禁止消费或释放TEST资源及批次。')
        manager=InventoryBalance.objects
    lookup={'warehouse':warehouse,'material_id':material_id,'location':location,'lot':lot}
    if test or formal:lookup['usage_purpose']=purpose
    balance,_=manager.select_for_update().get_or_create(**lookup,defaults={'quantity':Decimal('0')})
    if ((test or formal) and balance.usage_purpose!=purpose
            or not (test or formal) and balance.usage_purpose!=LEGACY):raise ValidationError('禁止跨用途更新库存余额。')
    before=balance.quantity;after=before+quantity
    balance.quantity=after;balance.save(update_fields=['quantity','updated_at'])
    transaction=(InventoryTransaction.all_objects if test else InventoryTransaction.objects).create(
        transaction_no=_next_number('TIT' if test else 'IT',InventoryTransaction,'transaction_no',include_test=test),
        source_inbound=inbound,warehouse=warehouse,material_id=material_id,location=location,lot=lot,
        direction='IN',quantity=quantity,before_quantity=before,after_quantity=after,
        operator_employee=employee,operator_account_id=user.pk,usage_purpose=purpose if test or formal else LEGACY)
    return balance,transaction

def post_material_issue_stock(*,allocation,quantity,employee,user,occurred_at):
    """Called only inside the native issue transaction, never on receipt."""
    from .models import InventoryBalance,InventoryTransaction
    from .material_stock_authority import original_quantity_field,fail
    from .scm_runtime_services import _next_number
    if not connection.in_atomic_block or allocation.company_id!=user.company_id or allocation.usage_purpose!='PRODUCTION_USE':
        fail('MATERIAL_ISSUE_POSTING_BOUNDARY','发料记账须处于本企业准确原分配事务。')
    qty=original_quantity_field(InventoryTransaction,'quantity',quantity)
    dims={k:getattr(allocation,k) for k in ['warehouse_id','location_id','lot_id','material_id','usage_purpose']}
    balance=InventoryBalance.objects.select_for_update().filter(**dims).first()
    if not balance or balance.quantity<qty:fail('MATERIAL_ISSUE_STOCK_INSUFFICIENT','同原库位批次库存不足，不能超发或忽略其他占用。')
    before=balance.quantity;after=original_quantity_field(InventoryBalance,'quantity',before-qty)
    balance.quantity=after;balance.save(update_fields=['quantity','updated_at']);balance.refresh_from_db()
    if balance.quantity!=after:fail('MATERIAL_ISSUE_STOCK_PRECISION_UNSUPPORTED','原数据库库存无法无损保存本次余额，事务回滚，不舍入。')
    posting=InventoryTransaction(transaction_no=_next_number('IT',InventoryTransaction,'transaction_no'),source_inbound_id=allocation.source_transaction.source_inbound_id,
        **dims,direction='OUT',quantity=qty,before_quantity=before,after_quantity=after,operator_employee=employee,operator_account_id=user.pk,occurred_at=occurred_at)
    posting._native_material_issue_posting=True;posting.save(force_insert=True)
    posting.refresh_from_db()
    if (posting.quantity,posting.before_quantity,posting.after_quantity)!=(qty,before,after):fail('MATERIAL_ISSUE_STOCK_PRECISION_UNSUPPORTED','原流水数据库无法无损承载本次数量，事务回滚。')
    return posting
