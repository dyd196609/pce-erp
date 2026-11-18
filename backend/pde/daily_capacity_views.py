"""Scoped read-only DAY date preview; never creates a schedule or runs MRP."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.db import DatabaseError, transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from planning.models import ProductionPlan
from system.authorization import AuthorizationService
from workflow_runtime.fact_loads import failed_fact_load_facts, successful_fact_load_facts
from .daily_capacity_service import (
    AUXILIARY_DATE_MODE, CONTRACT, DailyCapacityError, DailyCapacityReadinessService, capacity_fact, duration_days,
    working_date_window,
    _plan_capacity_context, _read_plan_step_demands, _current_plan_capacity, _allocated_capacity_duration,
)
from .models import EngineeringOperationRequirement, StandardCapacity, WorkCenterOperationCapability


def process_demand_for_plan(plan, output, item, step, *, company_id, user=None, require_saved=False):
    """Consume proven plan/step allocations; unallocated legacy workload blocks."""
    from .operation_requirement_service import process_demand_for_plan as read_allocated_demand

    calculation = output.engineering_calculation
    if calculation is not None and calculation.usage_purpose != 'PRODUCTION_USE':
        raise DailyCapacityError('SOURCE_PURPOSE_REJECTED', '日期产能消费者拒绝测试及未分类来源')

    allocated = read_allocated_demand(plan, output, item, step, company_id=company_id,
        **({'user': user} if user is not None else {}))
    if allocated is not None:
        return allocated
    if require_saved:
        raise DailyCapacityError('PROCESS_DEMAND_PLAN_ALLOCATION_MISSING',
            '有效步骤缺少已保存分配，禁止回退原输出需求或计划数量计算日期')
    calculation = output.engineering_calculation
    if not calculation or not getattr(calculation, 'pk', None):
        raise DailyCapacityError('PROCESS_DEMAND_QUANTITY_MISSING', '固定工程计算没有可确认的工序作业量来源')
    if (calculation.company_id != company_id or calculation.scope != 'order_engineering'
        or calculation.status != 'completed' or calculation.sales_order_item_id != item.pk
        or calculation.engineering_instance_id != output.order_engineering_instance_id):
        raise DailyCapacityError('PROCESS_DEMAND_SOURCE_MISMATCH', '工序作业量必须绑定同公司、同订单行、同工程实例的已完成固定工程计算')
    rows = list(EngineeringOperationRequirement.objects.filter(
        calculation_id=calculation.pk, operation_id=step['operationId'],
    ).select_related('source_detail', 'operation', 'uom').order_by('pk'))
    if not rows:
        raise DailyCapacityError('PROCESS_DEMAND_QUANTITY_MISSING', '同一固定工程计算与工序没有持久化作业量，禁止以生产计划数量替代')
    if len(rows) != 1:
        raise DailyCapacityError('PROCESS_DEMAND_QUANTITY_AMBIGUOUS', '同一固定计算与工序存在多个作业量来源，尚无正式汇总或步骤分配关系')
    requirement = rows[0]
    if requirement.usage_purpose != 'PRODUCTION_USE':
        raise DailyCapacityError('SOURCE_PURPOSE_REJECTED', '日期产能消费者拒绝测试及未分类需求')
    detail = requirement.source_detail
    trace = requirement.trace if isinstance(requirement.trace, dict) else {}
    if (requirement.calculation_id != calculation.pk or requirement.operation_id != step['operationId']
        or detail.calculation_id != calculation.pk or detail.status != 'succeeded'
        or requirement.operation.company_id != company_id
        or trace.get('resultDomain') != 'OPERATION_REQUIREMENT'
        or trace.get('detailId') != detail.pk):
        raise DailyCapacityError('PROCESS_DEMAND_SOURCE_MISMATCH', '工序需求与固定计算成功明细的正式血缘不一致')
    if not requirement.uom_id or not requirement.operation.calculation_uom_id:
        raise DailyCapacityError('PROCESS_DEMAND_UOM_MISSING', '工序需求或工序正式核算计量单位未确认')
    if (requirement.uom.company_id != company_id or not requirement.uom.is_active
        or requirement.uom_id != requirement.operation.calculation_uom_id
        or detail.uom_id != requirement.uom_id):
        raise DailyCapacityError('PROCESS_DEMAND_UOM_MISMATCH', '工序需求、成功明细与工序正式核算单位不一致，禁止隐式换算')
    if not isinstance(detail.output_value, dict):
        raise DailyCapacityError('PROCESS_DEMAND_QUANTITY_MISSING', '固定成功明细未保存可确认的十进制作业量对象')
    try:
        quantity = Decimal(str(requirement.workload_quantity))
        source_quantity = Decimal(str(detail.output_value.get('decimal')))
    except (InvalidOperation, ValueError, TypeError):
        raise DailyCapacityError('PROCESS_DEMAND_QUANTITY_MISSING', '工序需求或成功计算明细没有可确认的十进制作业量')
    if not quantity.is_finite() or not source_quantity.is_finite() or quantity <= 0 or quantity != source_quantity:
        raise DailyCapacityError('PROCESS_DEMAND_SOURCE_MISMATCH', '工序需求作业量与固定成功明细不一致')
    error = DailyCapacityError('PROCESS_DEMAND_PLAN_QUANTITY_BASIS_MISSING',
        '已读取工序作业量，但该需求没有经确认的数量口径及生产计划步骤分配，禁止据此推算排产日期')
    error.process_demand_fact = {
        'engineeringCalculationId': calculation.pk, 'engineeringOperationRequirementId': requirement.pk,
        'sourceDetailId': detail.pk, 'operationId': requirement.operation_id,
        'workloadQuantity': str(quantity), 'uomId': requirement.uom_id,
        'factSource': 'server', 'planAllocationConfirmed': False,
    }
    raise error


def validate_capability_window(step, capacity, allocations):
    """Check the exact candidate authority across all allocated work dates."""
    candidate = next((row for row in step.get('candidateWorkCenters', [])
                      if row['id'] == capacity.work_center_id), None)
    if candidate is None or capacity.operation_id != step['operationId']:
        raise DailyCapacityError('RESOURCE_CAPABILITY_SOURCE_MISSING', '所选产能没有同工序候选工作中心的正式来源')
    source = candidate.get('source', '')
    # These sources are FK facts read by readiness inside the same transaction.
    if source in {'RoutingStep.work_center', 'Process.work_center'}:
        return
    prefix = 'WorkCenterOperationCapability:'
    if not source.startswith(prefix) or not source[len(prefix):].isdigit():
        raise DailyCapacityError('RESOURCE_CAPABILITY_SOURCE_MISSING', '所选工序工作中心能力关系来源不可确认')
    relation = WorkCenterOperationCapability.objects.filter(
        pk=int(source[len(prefix):]), operation_id=step['operationId'], work_center_id=capacity.work_center_id,
    ).first()
    if relation is None or not relation.is_active:
        raise DailyCapacityError('RESOURCE_CAPABILITY_CHANGED', '所选工序工作中心能力关系已变化或停用')
    dates = [date.fromisoformat(row['date']) for row in allocations]
    if not dates or ((relation.effective_from and min(dates) < relation.effective_from)
                     or (relation.effective_to and max(dates) > relation.effective_to)):
        raise DailyCapacityError('RESOURCE_CAPABILITY_EFFECTIVE_WINDOW_MISMATCH', '排产日期超出所选工序工作中心能力关系的有效期间')


@transaction.atomic
def production_plan_date_preview(plan, *, start_date, company_id=None, user=None):
    plan, output, item, expected_company = _plan_capacity_context(plan, company_id)
    readiness, step_contexts = DailyCapacityReadinessService.assess_plan_date_scope(
        plan, company_id=expected_company, on_date=start_date, user=user)
    result = {"contractVersion": CONTRACT, "factSource": "server", "productionPlanId": plan.pk,
              "productionPlanNo": plan.plan_no, "routingVersionId": output.routing_version_id,
              "startDateInput": start_date.isoformat(), "readiness": readiness,
              "statusLabel": "日模型日期计算受阻", "previewReady": False, "dates": [],
              "businessWriteCount": 0, "productionScheduleCreatedCount": 0, "mrpRunCount": 0}
    if plan.status != 'confirmed' or output.release_status != 'released_to_manufacturing' or output.routing_version.status != 'released':
        result['sourceStatusBlocker']='生产计划、制造输出或工艺版本尚未完成正式发布/确认'
        return result
    if step_contexts:
        scoped_demands, demand_blockers, demand_facts = {}, [], []
        for row in readiness['steps']:
            bound, selected_output, selected_item, _ = step_contexts[row['sequence']]
            def read_effective_demand(*args, **kwargs):
                return process_demand_for_plan(*args, user=user, require_saved=True, **kwargs)
            scoped, blockers, facts = _read_plan_step_demands(bound, selected_output, selected_item,
                {'steps': [row], 'productTypeId': row['productTypeId']},
                company_id=expected_company, demand_reader=read_effective_demand)
            scoped_demands.update(scoped)
            demand_blockers.extend(blockers)
            demand_facts.extend(facts)
        result.update(processDemandBlockers=demand_blockers, processDemandFacts=demand_facts)
    else:
        scoped_demands, result['processDemandBlockers'], result['processDemandFacts'] = _read_plan_step_demands(
            plan, output, item, readiness, company_id=expected_company, demand_reader=process_demand_for_plan)
    if result['processDemandBlockers']:
        result['statusLabel'] = '工序需求、步骤分配或产能来源受阻，日期预览受阻'
        return result
    if not readiness['planningReady']:
        return result
    all_steps={r['sequence']:r for r in readiness['steps']}
    pending = {r['sequence']:dict(r) for r in readiness['steps'] if r['applicability']['result']=='REQUIRED'
               and r.get('capacityDateMode') != AUXILIARY_DATE_MODE}
    if not pending:
        result['statusLabel'] = '当前路线没有需独立计算日期的工序，未生成日期'
        return result
    def inherited_predecessors(sequence,visiting):
        if sequence in visiting:
            raise DailyCapacityError('ROUTING_DEPENDENCY_CYCLE','路线前置步骤形成循环')
        if sequence not in all_steps:
            raise DailyCapacityError('DEPENDENCY_REFERENCE_MISSING','路线前置步骤不存在')
        if sequence in pending:return {sequence}
        result=set()
        for predecessor in all_steps[sequence]['predecessorSequences']:
            result.update(inherited_predecessors(predecessor,visiting|{sequence}))
        return result
    for row in pending.values():
        required=set()
        for predecessor in row['predecessorSequences']:
            required.update(inherited_predecessors(predecessor,{row['sequence']}))
        row['effectivePredecessors']=sorted(required)
    finished = {}
    bookings = {}
    while pending:
        eligible = [r for r in pending.values() if all(p in finished for p in r['effectivePredecessors'])]
        if not eligible:
            raise DailyCapacityError("ROUTING_DEPENDENCY_CYCLE", "路线前置步骤形成循环")
        row = min(eligible,key=lambda r:r['sequence'])
        earliest = max([start_date]+[date.fromisoformat(finished[p]['endDate'])+timedelta(days=1)
                                    for p in row['effectivePredecessors']])
        choices = []
        for fact in row['dailyCapacity']:
            if not fact['available']:
                continue
            capacity = _current_plan_capacity(fact, start_date)
            policy = capacity.work_center.capacity_policy
            calendar = policy.get('calendar',{}) if isinstance(policy, dict) else {}
            resource_bookings = dict(bookings.get(capacity.work_center_id,{}))
            try:
                process_demand = scoped_demands[row['sequence']]
                days = _allocated_capacity_duration(row, capacity, process_demand)
                window = working_date_window(start_date=earliest,duration=days['durationDays'],calendar=calendar,
                                             daily_bookings=resource_bookings)
                validate_capability_window(row, capacity, window['allocations'])
                consumed_dates=[date.fromisoformat(a['date']) for a in window['allocations']]
                validity_rows=[capacity,capacity.work_center,getattr(capacity,'operation',None),getattr(capacity,'product_type',None)]
                if any((getattr(v,'effective_from',None) and min(consumed_dates)<v.effective_from)
                       or (getattr(v,'effective_to',None) and max(consumed_dates)>v.effective_to)
                       for v in validity_rows if v is not None):
                    raise DailyCapacityError('CAPACITY_EFFECTIVE_WINDOW_MISMATCH','排产日期超出产能或资源的有效期间')
            except DailyCapacityError as exc:
                choices.append({'error':exc})
                continue
            choices.append({'capacity':capacity,'days':days,'window':window,'bookings':resource_bookings})
        feasible = [c for c in choices if 'capacity' in c]
        if not feasible:
            raise choices[0]['error'] if choices else DailyCapacityError('DAILY_CAPACITY_MISSING','没有可用日产能')
        chosen = min(feasible,key=lambda c:(c['window']['endDate'],c['capacity'].pk))
        bookings[chosen['capacity'].work_center_id]=chosen['bookings']
        projected={'stepId':row['stepId'],'sequence':row['sequence'],'operationId':row['operationId'],
                   'workCenterId':chosen['capacity'].work_center_id,'standardCapacityId':chosen['capacity'].pk,
                   'processDemandQuantity':str(scoped_demands[row['sequence']]['quantity']),
                   'processDemandUomId':scoped_demands[row['sequence']]['uomId'],
                   **chosen['days'],**chosen['window']}
        if step_contexts:
            projected.update(rootStepId=row['rootStepId'], effectiveSequence=row['effectiveSequence'],
                engineeringVersion=row['engineeringVersion'])
        finished[row['sequence']]=projected
        pending.pop(row['sequence'])
        result['dates'].append(projected)
    result.update(previewReady=True,statusLabel='日模型日期预览已计算',
                  endDate=max([r['endDate'] for r in result['dates']],default=start_date.isoformat()),
                  calendarGranularityLabel='工作日；前置工序完成后的下一工作日开始')
    return result


class DailyCapacityDatePreviewView(APIView):
    permission_classes=[IsAuthenticated]

    def failure(self,request,code,message,http_status):
        facts=failed_fact_load_facts(request=request,api_url=request.path,http_status=http_status,
                                    error_code=code,error_message=message,
                                    tenant_id=str(request.user.company_id) if getattr(request.user,'company_id',None) else None)
        surface={**facts,'passed':False,'resultCount':None,'businessWriteCount':0,'productionScheduleCreatedCount':0}
        return Response({'code':code,'message':message,'previewReady':False,**facts,'factLoadFacts':facts,
                         **{key:dict(surface) for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts')}},status=http_status)

    def handle_exception(self,exc):
        from rest_framework.exceptions import APIException
        if isinstance(exc,APIException):
            return self.failure(self.request,str(getattr(exc,'default_code','API_ERROR')),str(exc.detail),exc.status_code)
        return super().handle_exception(exc)

    def get(self,request):
        company_id=request.user.company_id
        if not company_id:
            return self.failure(request,'ORGANIZATION_REQUIRED','当前账户缺少公司范围',403)
        decision=AuthorizationService.decide(user=request.user,action_code='planning.view',
            organization_id=company_id,business_object={'organizationId':company_id})
        if not decision.get('allowed'):
            return self.failure(request,decision.get('decisionCode','PERMISSION_DENIED'),
                                decision.get('reason','没有生产计划读取权限'),403)
        try:
            plan_id=int(request.query_params.get('productionPlanId',''))
            start=date.fromisoformat(request.query_params.get('startDate',''))
        except (TypeError,ValueError):
            return self.failure(request,'PLAN_DATE_INPUT_REQUIRED','必须提供生产计划ID及ISO开始日期',400)
        try:
            plan=ProductionPlan.objects.filter(pk=plan_id,
                planning_requirement__demand__sales_order_item__sales_order__company_id=company_id).first()
            if plan is None:
                return self.failure(request,'PLAN_NOT_FOUND','生产计划不存在或不在当前公司范围',404)
            payload=production_plan_date_preview(plan,start_date=start,company_id=company_id,user=request.user)
            facts=successful_fact_load_facts(request=request,result_count=1,api_url=request.path,tenant_id=str(company_id))
            surface={**payload,**facts,'resultCount':1,'passed':bool(payload['previewReady'])}
            return Response({**surface,'factLoadFacts':facts,
                             **{key:dict(surface) for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts')}})
        except DailyCapacityError as exc:
            return self.failure(request,exc.code,str(exc),409)
        except DatabaseError:
            return self.failure(request,'DAILY_CAPACITY_READ_FAILED','日产能或计划事实读取失败',503)
