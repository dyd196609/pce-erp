"""Native PRODUCTION_USE admission. Never relabel or consume TEST parents.

Admission re-reads the plan/order/engineering lineage, saved schedule, release,
receipt and dispatch proofs. It grants no actor permission and performs no write.
"""
from pde.routing_read_context import routing_read_phase
from copy import deepcopy
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from masterdata.models import UnitOfMeasure
from .scheduling_primitives import _hash
from .services import PlanningBusinessError
from .test_work_order_service import require_formal_work_order
from . import work_order_execution_service as orders
from . import workshop_task_service as tasks
from . import formal_scheduling_service as schedules
from .workshop_receipt_protocol import _legacy_receipt, _effective
from .test_operation_start_protocol import _today


def fail(code, message, status=409):
    raise PlanningBusinessError(code, message, http_status=status)


def formal_datetime_label(value, zone):
    from django.utils import timezone
    from zoneinfo import ZoneInfo
    if value is None:return None
    if timezone.is_naive(value):value=timezone.make_aware(value,timezone.get_default_timezone())
    return value.astimezone(ZoneInfo(zone)).strftime('%Y年%m月%d日 %H:%M:%S')


def current_version(task, actor):
    from pde.plan_step_context_service import resolve_step_context, version_fact, _company
    op=task.source_operation
    context=resolve_step_context(task.work_order.production_plan,op.root_step_id,user=actor)
    current=version_fact(context)
    previous=op.source_snapshot['frozenStep']['engineeringVersion']
    keys=('originalManufacturingOutputId','effectiveManufacturingOutputId',
          'originalRoutingVersionId','effectiveRoutingVersionId','rootRoutingStepId','effectiveRoutingStepId',
          'bindingId','sourceBaselineId','mainCalculationId','sourceSelection')
    root,step=context['root_step'],context['step']
    valid=(all(current.get(k)==previous.get(k) for k in keys)
        and context['plan'].pk==task.work_order.production_plan_id
        and _company(root)==_company(step)==task.company_id==actor.company_id
        and root.pk==op.root_step_id and root.routing_version_id==op.root_routing_version_id
        and step.pk==op.effective_step_id and step.routing_version_id==op.effective_routing_version_id
        and step.is_active and step.operation_id==op.operation_id
        and step.work_center_id in (None,task.work_center_id) and step.workshop_id in (None,task.workshop_id))
    if not valid:fail('MES_FORMAL_VERSION_CHANGED','当前正式工程版本或准确步骤已变化。')
    return current


@routing_read_phase("taskSource")
def source(task, actor):
    try:
        return _source(task,actor)
    except (ObjectDoesNotExist,ValidationError,KeyError,TypeError,AttributeError,ValueError) as error:
        fail('MES_FORMAL_SOURCE_UNPROVEN','正式来源关系或版本事实不完整，未授予执行资格。')


from .verified_read_memo import verified_model_read


@verified_model_read
def _verify_source_schedule(schedule):
    return schedules._verify_schedule(schedule)


def _source(task, actor):
    if actor.company_id!=task.company_id:fail('MES_FORMAL_COMPANY_DENIED','任务不属于当前公司。',403)
    order=task.work_order;op=task.source_operation
    from pde.capacity_evidence_read_scope import evidence_cache, read_scope_plan

    evidence = evidence_cache(task.company_id)
    require_formal_work_order(order)
    if evidence is None:
        orders._verify(order)
        schedules._verify_schedule(order.source_schedule)
    else:
        # Native member proof verifies the same order, including its original
        # audit and transitions. The receiving task's own proof still follows.
        orders.read_verified_member_ids(order)
        _verify_source_schedule.validate_only(order.source_schedule)
    tasks._verify_history(task)
    # The plan is an original scoped row. Each task still checks its own
    # frozen order, receipt, engineering lineage and proper company below.
    persisted_plan = read_scope_plan(order.production_plan_id, evidence) if evidence is not None else None
    plan = persisted_plan if persisted_plan is not None else order.production_plan
    req = plan.planning_requirement
    demand = req.demand
    item=demand.sales_order_item;sale=item.sales_order if item else None
    frozen=order.source_snapshot
    from pde.order_lifecycle_source_projection import terminal_read_allowed
    output=demand.manufacturing_output
    if not (output and output.release_status=='released_to_manufacturing' and output.engineering_status=='ready'
        and output.order_engineering_instance.sales_order_item_id==item.pk
        and output.order_engineering_baseline.company_id==order.company_id
        and output.order_engineering_baseline.sales_order_id==sale.pk
        and output.order_engineering_baseline.status=='confirmed'
        and output.order_engineering_baseline.approval_scope!='TEST_BUSINESS'
        and output.engineering_calculation.approval_scope!='TEST_BUSINESS'
        and output.bom_version.status=='released' and output.bom_version.usage_purpose in ('PRODUCTION_USE','SHARED_DEFINITION')
        and output.routing_version.status=='released' and output.routing_version.usage_purpose in ('PRODUCTION_USE','SHARED_DEFINITION')):
        fail('MES_FORMAL_ENGINEERING_RELEASE_INVALID','正式制造输出、基线、核算、BOM或路线未获原生发布，TEST工程来源不能进入正式用途。')
    if not (sale and sale.company_id==order.company_id==task.company_id==order.source_schedule.company_id
        and order.source_schedule.production_plan_id==plan.pk
        and frozen.get('salesOrderId')==sale.pk and frozen.get('salesOrderItemId')==item.pk
        and frozen.get('demandId')==demand.pk and frozen.get('requirementId')==req.pk
        and plan.status=='confirmed' and demand.status=='confirmed'
        and (sale.status in ('approved','confirmed','engineering','manufacturing_ready','in_progress','delivering') or terminal_read_allowed(sale))
        and plan.material_id==demand.material_id==order.material_id
        and Decimal(frozen['quantity'])==order.quantity==plan.planned_qty
        and demand.manufacturing_output_id and order.source_schedule.status=='saved'
        and order.status=='released' and task.status=='dispatched' and task.work_order_version==order.version
        and op.work_order_id==order.pk):
        fail('MES_FORMAL_LINEAGE_INVALID','正式订单、需求、计划、排程和工单来源不完整或已失效。')
    # New exact resource, allocation and nonquantity contracts retain their
    # complete native verifier. The historical quantified shape stays exact.
    legacy_keys={'companyId','workOrderId','workOrderNo','workOrderVersion','workOrderSnapshotHash',
        'receiptId','receiptSnapshotHash','workshopId','sourceOperationId','operationSnapshotHash','workCenterId','operation'}
    if task.execution_mode!='QUANTIFIED' or set(task.source_snapshot)!=legacy_keys:
        from .operation_start_service import _source as native_source
        result=native_source(task,actor)
        if not result['ready']:fail('MES_FORMAL_NATIVE_SOURCE_UNPROVEN',result['statusLabel'])
        return result
    receipt=task.receipt
    _legacy_receipt(receipt)
    expected={'companyId':order.company_id,'workOrderId':order.pk,'workOrderNo':order.no,
        'workOrderVersion':order.version,'workOrderSnapshotHash':order.snapshot_hash,
        'receiptId':receipt.pk,'receiptSnapshotHash':receipt.snapshot_hash,'workshopId':task.workshop_id,
        'sourceOperationId':op.pk,'operationSnapshotHash':op.snapshot_hash,'workCenterId':op.work_center_id,
        'operation':deepcopy(op.source_snapshot)}
    center=op.work_center
    if not (receipt.company_id==task.company_id and receipt.work_order_id==order.pk
        and receipt.workshop_id==task.workshop_id and receipt.work_order_version==order.version
        and receipt.work_order_snapshot_hash==order.snapshot_hash
        and any(x.get('operationId')==op.pk and x.get('operationSnapshotHash')==op.snapshot_hash
            and x.get('source')==op.source_snapshot and x.get('workCenterId')==task.work_center_id
            and x.get('workshopId')==task.workshop_id for x in receipt.source_snapshot.get('operations',[]))
        and expected==task.source_snapshot and _hash(expected)==task.source_snapshot_hash
        and center and center.pk==task.work_center_id and center.company_id==task.company_id
        and center.workshop_id==task.workshop_id and _effective(center,_today())
        and UnitOfMeasure.objects.filter(pk=task.workload_uom_id,company_id=task.company_id,is_active=True).exists()):
        fail('MES_FORMAL_RECEIPT_SOURCE_INVALID','正式接收范围、派工冻结来源或资源不一致。')
    version=current_version(task,actor)
    workshop={'id':task.workshop_id,'code':task.workshop.code,'name':task.workshop.name}
    return {'ready':True,'statusLabel':'正式订单、工程版本、计划、排程、下达、接收及派工来源已核实',
        'snapshotHash':task.source_snapshot_hash,'receiptValid':True,
        'currentSourceChecks':{'ready':True,'authority':'NATIVE_FORMAL_SOURCE_ADMISSION','currentEngineeringVersion':version},
        'resourceSource':{'sourceReady':True,'statusLabel':'正式车间接收来源已核实','usagePurpose':'PRODUCTION_USE','receiptId':receipt.pk},
        'originalReceiptWorkshop':workshop,'effectiveWorkshop':workshop,'effectiveReceptionAuthority':'VERIFIED_FORMAL_WORKSHOP_RECEIPT'}
