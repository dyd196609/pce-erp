"""M09: derive MES completion from the existing native authorities, never write it."""
from decimal import Decimal
import logging
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from django.utils import timezone
from workflow_runtime.fact_loads import build_fact_load_facts
from planning.operation_resource_read_scope import scoped_execution_read
from pde.order_lifecycle_source_projection import terminal_closure_read

CONTRACT = 'PCE-ORDER-MES-COMPLETION-V1'


def reason(code, message, *, scope, object_id=None):
    return {'code': code, 'message': message, 'scope': scope, 'objectId': object_id}


@terminal_closure_read
def _work_order_facts(work_order, item, demand, plan, *, lock=False):
    from planning.test_work_order_service import verify
    from planning.finished_goods_authority import current_closure, task_graph
    from planning.operation_output_authority import read_task_quantity_account
    from planning.operation_start_models import ProductionOperationStart
    from system.models import User
    from planning.workshop_task_models import ProductionWorkshopTask
    from planning.operation_handover_models import OperationQuantityAccount
    verify(work_order)
    frozen = work_order.source_snapshot
    if (work_order.usage_purpose != 'PRODUCTION_USE' or work_order.company_id != item.sales_order.company_id
        or work_order.production_plan_id != plan.pk or frozen.get('salesOrderId') != item.sales_order_id
        or frozen.get('salesOrderItemId') != item.pk or frozen.get('demandId') != demand.pk
        or frozen.get('requirementId') != plan.planning_requirement_id
        or work_order.material_id != item.material_id or work_order.uom_id != item.uom_id
        or work_order.quantity != plan.planned_qty or work_order.quantity <= 0):
        raise ValueError('M09_WORK_ORDER_SOURCE_MISMATCH')
    if lock:
        list(ProductionWorkshopTask.objects.select_for_update().filter(work_order=work_order))
        list(OperationQuantityAccount.objects.select_for_update().filter(task__work_order=work_order))
    closure = current_closure(work_order)
    from planning.finished_goods_models import ProductionFinishedGoodsTransfer
    from planning.operation_handover_models import OperationCustodyEvent
    from planning.operation_handover_core import verify_record
    from planning.finished_goods_authority import verify_warehouse_conversion
    physical_blockers=[];receipts=[]
    transfers=list(ProductionFinishedGoodsTransfer.objects.filter(work_order=work_order,company_id=work_order.company_id).exclude(status='cancelled'))
    if len(transfers)!=1:
        physical_blockers.append(reason('M09_FINISHED_HANDOVER_UNPROVEN','原生整工单成品交接尚未形成唯一有效实收证明；不得把在手或未交接视为物理闭合。',scope='WORK_ORDER',object_id=work_order.pk))
    else:
        transfer=transfers[0];verify_record(transfer)
        if transfer.status!='received':
            physical_blockers.append(reason('M09_FINISHED_HANDOVER_PENDING','成品交接仍未实收，执行完工与物理闭合分别登记。',scope='WORK_ORDER',object_id=work_order.pk))
        else:
            if transfer.material_id!=item.material_id or transfer.uom_id!=item.uom_id or Decimal(transfer.quantity)!=work_order.quantity:
                raise ValueError('M09_FINISHED_PRODUCT_SOURCE_MISMATCH')
            events=list(OperationCustodyEvent.objects.filter(task=transfer.task,company_id=work_order.company_id,
                kind='FG_WAREHOUSE_ACCEPT',data__finishedGoodsTransferId=transfer.pk))
            if len(events)!=1:raise ValueError('M09_FINISHED_RECEIPT_UNPROVEN')
            verify_record(events[0]);verify_warehouse_conversion(events[0])
            receipts.append({'transferId':transfer.pk,'custodyEventId':events[0].pk,'authority':'planning.finished_goods_authority.verify_warehouse_conversion','quantity':transfer.quantity,'uomId':transfer.uom_id})
    tasks, _, _, _ = task_graph(work_order)
    quantities = []
    for task in tasks:
        start = ProductionOperationStart.objects.filter(task=task).first()
        if not start:
            quantities.append({'taskId':task.pk,'quantityApplicable':task.execution_mode=='QUANTIFIED',
                'quantityStatus':'NOT_STARTED','account':None,'physicalCompletedAt':None,'physicalCompletedAtStatus':'NOT_COLLECTED'})
            continue
        actor = User.objects.defer('password').get(pk=start.started_by_id)
        account = read_task_quantity_account(task,actor)
        if account['quantityApplicable']:
            for key,label in (('I','在途'),('Q','短收待核'),('X','未匹配差额')):
                if Decimal(account[key])>0:
                    physical_blockers.append({**reason('M09_CUSTODY_OPEN',label+'尚未按原交接合同闭合。',scope='TASK',object_id=task.pk),
                        'metric':key,'quantity':account[key],'uom':account['uom'],'responsibilityScope':'NATIVE_TASK_CUSTODY_ACCOUNT'})
        quantities.append({'taskId':task.pk,'quantityApplicable':account['quantityApplicable'],
            'quantityStatus':'APPLICABLE' if account['quantityApplicable'] else 'NOT_APPLICABLE',
            'account':{k:account.get(k) for k in ('P','R','E','W','U','S','V','I','Q','H','X','planDeficit','unconfirmedReportedQuantity','uom','blockingReasons','productionBlockingReasons')},
            'responsibilityScope':'THIS_TASK_AND_NATIVE_CUSTODY_LOCATIONS; no cross-task sum',
            'physicalCompletedAt':None,'physicalCompletedAtStatus':'NOT_COLLECTED'})
    return {'workOrderId':work_order.pk,'version':work_order.version,'statusCode':work_order.status,
        'statusLabel':work_order.get_status_display(),'executionCompleted':closure['ready'],
        'mesClosed':closure['ready'] and not physical_blockers,'physicalClosureReceipts':receipts,
        'completionAuthority':'planning.finished_goods_authority.current_closure',
        'sourceSnapshotHash':work_order.snapshot_hash,'closureProofHash':closure['hash'],
        'blockingReasons':[reason('MES_EXECUTION_NOT_CLOSED',text,scope='WORK_ORDER',object_id=work_order.pk) for text in closure['blockingReasons']]+physical_blockers,
        'quantity':str(work_order.quantity),'uomId':work_order.uom_id,
        'plannedStartDate':frozen.get('plannedStartDate'),'plannedRequiredDate':frozen.get('requiredDate'),
        'physicalCompletedAt':None,'physicalCompletedAtStatus':'NOT_COLLECTED','tasks':quantities}


@scoped_execution_read
def _order_mes_completion_facts(order, *, lock=False):
    """Internal caller has already authorized THIS order; not an unscoped API.

    BUY keeps the original sales completion contract. Unknown supply/source is
    not treated as BUY, zero outstanding or proved completion. Manufacturing
    output and workshop workload use their own units and are never added.
    """
    from sales.supply_admission_service import supply_admission_facts
    from planning.models import Demand
    from planning.work_order_models import ProductionWorkOrder
    lines=[];blockers=[];failed=False
    items=order.items.select_related('sales_order','uom').order_by('line_no','pk')
    if lock:items=items.select_for_update()
    for item in items:
        line={'salesOrderItemId':item.pk,'lineNo':item.line_no,'quantity':str(item.quantity),'uomId':item.uom_id,
            'requiredDate':item.required_date.isoformat(),'physicalCompletedAt':None,'physicalCompletedAtStatus':'NOT_COLLECTED',
            'manufacturingApplicable':None,'completionStatus':'SOURCE_UNKNOWN','ready':False,'workOrders':[],'blockingReasons':[]}
        try:
            supply=supply_admission_facts(item);branch=supply['supplyBranch']
            line['supplySource']={'authority':'sales.supply_admission_service.supply_admission_facts','factId':supply.get('factId'),'status':supply['status'],'branch':branch}
            if branch=='BUY':
                # An inconsistent existing MAKE chain must not disappear just
                # because a different branch was presented on the sales line.
                if ProductionWorkOrder.objects.filter(production_plan__planning_requirement__demand__sales_order_item=item).exists():
                    raise ValueError('M09_SUPPLY_BRANCH_CONFLICT')
                line.update(manufacturingApplicable=False,completionStatus='NOT_APPLICABLE',ready=True)
            elif branch!='MAKE':
                line['blockingReasons'].append(reason('M09_SUPPLY_SOURCE_UNKNOWN','供应承接来源未核实，不能推定不适用制造或已完成。',scope='ORDER_LINE',object_id=item.pk))
            else:
                line['manufacturingApplicable']=True
                from .order_supply_coverage import line_supply_coverage
                line.update(line_supply_coverage(item, lock=lock))
        except DatabaseError:
            failed=True;line['quantity']=None
            line.update(completionStatus='READ_FAILED',ready=False,workOrders=[])
            line['blockingReasons']=[reason('M09_FACT_READ_FAILED','完成事实读取失败，结果未知；未执行订单状态动作。',scope='ORDER_LINE',object_id=item.pk)]
        except Exception as exc:
            # Native business proof rejection is explicitly UNKNOWN, never an
            # empty/zero/completed substitute. Do not expose internal messages.
            logging.getLogger(__name__).warning('M09 native proof rejected for order %s line %s: %s',order.pk,item.pk,type(exc).__name__,exc_info=True)
            line.update(completionStatus='SOURCE_UNKNOWN',ready=False,workOrders=[])
            code=getattr(exc,'code',None) or (str(exc) if isinstance(exc,ValueError) and str(exc).startswith('M09_') else 'M09_NATIVE_SOURCE_UNPROVEN')
            line['blockingReasons']=[reason(code,'来源、版本、单位或原生证明未通过核验；未推定完成。',scope='ORDER_LINE',object_id=item.pk)]
        lines.append(line);blockers.extend(line['blockingReasons'])
    if not lines:blockers.append(reason('M09_ORDER_LINES_REQUIRED','缺少适用订单行，不能推定已完成。',scope='ORDER',object_id=order.pk))
    ready=bool(lines) and not blockers
    facts={'contractVersion':CONTRACT,'factKind':'SYSTEM_DERIVED','factSource':'native sales supply + planning work-order + MES closure authorities',
        'companyId':order.company_id,'salesOrderId':order.pk,'salesOrderVersion':order.version,
        'stateSource':'sales.SalesOrder + workflow_runtime.BusinessStateTransition',
        'formalStatusCode':order.status,'formalStatusLabel':order.get_status_display(),
        'mesApplicable':True if any(x['manufacturingApplicable'] is True for x in lines) else None if any(x['manufacturingApplicable'] is None for x in lines) else False,
        'completionEligibility':'READY' if ready else 'READ_FAILED' if failed else 'BLOCKED',
        'ready':ready,'passed':ready,'lines':lines,'blockingReasons':blockers,
        'physicalCompletedAt':None,'physicalCompletedAtStatus':'NOT_COLLECTED',
        'actualOrderCompletedAtSource':'native sales.order.complete transition; administrative event only',
        'automaticallyChangesOrderStatus':False,'loadedAt':timezone.now().isoformat()}
    facts.update(build_fact_load_facts(fact_load_status='read_failed' if failed else 'loaded',
        api_url=f'/api/sales/orders/{order.pk}/?includeCompletionFacts=1',http_status=503 if failed else 200,
        error_code='M09_FACT_READ_FAILED' if failed else '',error_message='完成事实读取失败，结果未知。' if failed else '',
        tenant_id=str(order.company_id),batch_id=f'SalesOrder:{order.pk}:v{order.version}'))
    return facts


def order_mes_completion_facts(order, *, lock=False):
    try:
        return _order_mes_completion_facts(order,lock=lock)
    except DatabaseError:
        facts={'contractVersion':CONTRACT,'factKind':'SYSTEM_DERIVED','salesOrderId':order.pk,
            'companyId':order.company_id,'salesOrderVersion':order.version,'ready':False,'passed':False,
            'completionEligibility':'READ_FAILED','mesApplicable':None,'lines':None,
            'blockingReasons':[reason('M09_FACT_READ_FAILED','完成事实读取失败，结果未知；未执行状态动作。',scope='ORDER',object_id=order.pk)],
            'physicalCompletedAt':None,'physicalCompletedAtStatus':'NOT_COLLECTED','automaticallyChangesOrderStatus':False}
        facts.update(build_fact_load_facts(fact_load_status='read_failed',api_url=f'/api/sales/orders/{order.pk}/?includeCompletionFacts=1',
            http_status=503,error_code='M09_FACT_READ_FAILED',error_message='完成事实读取失败，结果未知。',
            tenant_id=str(order.company_id),batch_id=f'SalesOrder:{order.pk}:v{order.version}'))
        return facts


def require_order_mes_completion(order):
    from .services import SalesBusinessError
    facts=order_mes_completion_facts(order,lock=True)
    if not facts['ready']:
        code='M09_FACT_READ_FAILED' if facts['factLoadStatus']=='read_failed' else 'SALES_ORDER_MES_NOT_CLOSED'
        data={'mesCompletionFacts':facts}
        if code=='M09_FACT_READ_FAILED':data['factLoadFacts']=facts
        raise SalesBusinessError(code,'制造完成准入未通过，请查看本订单完成事实及阻断原因。',503 if code=='M09_FACT_READ_FAILED' else 409,data)
    return facts
