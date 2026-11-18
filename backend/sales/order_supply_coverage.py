"""M09 projection of original Demand scopes and WMS reservations, never a quantity account."""
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
from planning.models import Demand
from planning.work_order_models import ProductionWorkOrder
from planning.order_batch_service import verify_batch, number, fail
from procurement.order_stock_allocation import allocations_for_line
from pde.order_lifecycle_source_projection import terminal_closure_read


@terminal_closure_read
def _line_supply_coverage(_unused, item, *, lock=False):
    from .mes_completion_admission import _work_order_facts, reason
    from .services import _require_crm_admission
    _require_crm_admission(company_id=item.sales_order.company_id,order=item.sales_order,lock=lock)
    blockers=[];work_orders=[];batch_facts=[];intervals=[]
    rows=Demand.objects.filter(sales_order_item=item).select_related('department','planning_requirement__production_plan')
    if lock:rows=rows.select_for_update()
    demands=list(rows)
    allocation_history=allocations_for_line(item,lock=lock,include_inactive=True)
    allocations=[fact for fact in allocation_history if fact['active']]
    for allocation in allocations:
        intervals.append((number(allocation['rangeStart'],zero=True),number(allocation['rangeEnd']), 'STOCK', allocation['allocationId']))
    # Unregistered version branches remain unknown, even if one is newer or all
    # happen to have enough quantities. A predecessor is not a batch certificate.
    if len(demands)>1 and any(not demand.batch_key for demand in demands):
        fail('M09_SOURCE_SELECTION_REQUIRED','多个历史制造来源尚无正式分批/更正范围，不能按新旧时间猜选或累计。')
    completed=Decimal('0');planned=Decimal('0')
    for demand in demands:
        proof=verify_batch(demand)
        if proof and not proof['active']:
            batch_facts.append({**proof,'manufacturingCompleted':False,'coverageExcluded':'Native unplanned cancellation; original record/audit retained'})
            continue
        if proof:
            start,end=number(proof['rangeStart'],zero=True),number(proof['rangeEnd'])
        else:
            if (demand.required_qty!=item.quantity or demand.department.company_id!=item.sales_order.company_id
                or demand.material_id!=item.material_id or demand.source_type!='sales_order'
                or demand.source_document_type!='SalesOrderItem' or demand.source_document_id!=str(item.pk)):
                fail('M09_DEMAND_SOURCE_MISMATCH','原需求与本订单行不一致。')
            start,end=Decimal('0'),item.quantity
        intervals.append((start,end,'DEMAND',demand.pk));planned+=end-start
        batch={'demandId':demand.pk,'batchKey':demand.batch_key or None,
            'rangeStart':str(start),'rangeEnd':str(end),'quantity':str(end-start),'uomId':item.uom_id,
            'manufacturingCompleted':False,'scopeProof':proof,'manufacturingOutputId':demand.manufacturing_output_id}
        batch_facts.append(batch)
        try:requirement=demand.planning_requirement;plan=requirement.production_plan
        except ObjectDoesNotExist:
            blockers.append(reason('M09_PLAN_REQUIRED','该制造范围尚无原生有效计划。',scope='DEMAND',object_id=demand.pk));continue
        if (requirement.material_id!=item.material_id or requirement.supply_type!='production'
            or plan.material_id!=item.material_id or plan.planned_qty!=requirement.net_required_qty
            or plan.status not in {'confirmed','released'} or plan.planned_qty>end-start):
            fail('M09_PLAN_SOURCE_MISMATCH','计划来源、状态或本批范围数量不一致。')
        if plan.planned_qty!=end-start:
            blockers.append(reason('M09_NON_MES_COVERAGE_UNPROVEN','历史净制造范围未经正式登记；余额快照和新分配不能回填旧计划来源。',scope='DEMAND',object_id=demand.pk))
        orders=ProductionWorkOrder.objects.filter(production_plan=plan,company_id=item.sales_order.company_id)
        if lock:orders=orders.select_for_update()
        orders=list(orders.select_related('source_schedule','uom','material'))
        closed=bool(orders)
        if not orders:
            blockers.append(reason('M09_WORK_ORDER_REQUIRED','本批尚无来源可证工单。',scope='DEMAND',object_id=demand.pk))
        for order in orders:
            fact=_work_order_facts(order,item,demand,plan,lock=lock)
            fact['orderCoverageQuantity']=str(end-start)
            fact['coverageQuantityMeaning']='Approved batch scope; controlled excess output stays in native task accounts and is not added again'
            work_orders.append(fact);blockers.extend(fact['blockingReasons']);closed=closed and fact['mesClosed']
        if closed and plan.planned_qty==end-start:completed+=end-start
        batch['manufacturingCompleted']=closed
    intervals.sort(key=lambda row:(row[0],row[1],row[2],row[3]))
    previous=Decimal('0');covered=Decimal('0');gaps=[]
    for start,end,kind,pk in intervals:
        if start<previous:
            fail('COVERAGE_RANGE_OVERLAP','制造范围、库存分配或替代引用存在重复覆盖，未推定完成。')
        if start>previous:gaps.append({'rangeStart':str(previous),'rangeEnd':str(start)})
        previous=end;covered+=end-start
    if previous<item.quantity:gaps.append({'rangeStart':str(previous),'rangeEnd':str(item.quantity)})
    if previous>item.quantity or covered>item.quantity:
        fail('COVERAGE_RANGE_INVALID','累计有效范围超出本订单已批准数量。')
    stock=sum((number(row['targetQuantity']) for row in allocations),Decimal('0'))
    if gaps:
        blockers.append(reason('M09_SUPPLY_COVERAGE_INSUFFICIENT','本订单行仍存在未经证明的供给范围。',scope='ORDER_LINE',object_id=item.pk))
    if not intervals:
        blockers.append(reason('M09_DEMAND_REQUIRED','既无制造来源也无准确库存分配，不能把无工单视为完成。',scope='ORDER_LINE',object_id=item.pk))
    ready=not blockers and covered==item.quantity and completed+stock==item.quantity
    return {'workOrders':work_orders,'blockingReasons':blockers,'ready':ready,
        'completionStatus':('SUPPLY_READY' if stock>0 else 'COMPLETED') if ready else 'INCOMPLETE',
        'supplyCoverage':{'contractVersion':'PCE-ORDER-SUPPLY-COVERAGE-V1','factKind':'SYSTEM_DERIVED',
            'authority':'native Demand batch audit + native WMS receipt allocation + existing MES closure',
            'requiredQuantity':str(item.quantity),'uomId':item.uom_id,'uomLabel':item.uom.name,
            'plannedManufacturingScopeQuantity':str(planned),'manufacturingCompletedQuantity':str(completed),
            'confirmedStockCoverageQuantity':str(stock),'supplyCoverageReady':ready,
            'supplyCoverageStatusCode':'READY' if ready else 'BLOCKED',
            'supplyCoverageStatusLabel':'供给覆盖已就绪' if ready else '供给范围尚未闭合',
            'manufacturingCompletionStatusLabel':('本行无须新增制造范围' if planned==0 and ready else
                '制造范围已实际闭合' if planned>0 and completed==planned else '制造范围尚未闭合'),
            'completionMeaningLabel':'仅核对本订单行供给及制造闭合；不推断发货、签收或履约完成',
            'manufacturingCompletionStatus':'NOT_REQUIRED' if planned==0 and ready else 'COMPLETED' if planned>0 and completed==planned else 'INCOMPLETE',
            'unprovedRanges':gaps,'batches':batch_facts,'stockAllocations':allocations,'stockAllocationHistory':allocation_history,
            'shipmentOrFulfilmentInferred':False,'automaticallyChangesOrderStatus':False,
            'physicalCompletedAt':None,'physicalCompletedAtStatus':'NOT_COLLECTED'}}


def line_supply_coverage(item, *, lock=False):
    return _line_supply_coverage(None, item, lock=lock)
