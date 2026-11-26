from pde.baseline_usage_service import production_baselines
"""Purpose-specific, zero-write review over saved engineering and plan facts.

Purpose candidates select final quantity fields, never every extension output.
Saved operation loads also retain EORs proved by the native allocation reader.
Conversion/lifecycle and allocation proofs remain owned by their existing services.
Unknown mappings stay unknown; this reader cannot confer scheduling eligibility.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from hashlib import sha256
from time import perf_counter

from planning.models import ProductionPlan
from planning.quantity_semantics import planning_quantity_facts
from django.db import transaction
from django.db.models import Q
from system.authorization import AuthorizationService

from .engineering_rule_foundation import canonical_json
from .manufacturing_capacity_scope import capacity_usage_scope_proof
from .manufacturing_fact_batch_service import ManufacturingFactBatchService
from .models import (
    CapacityProductType, EngineeringCalculationRecord, EngineeringDerivedFact,
    EngineeringOperationRequirement, OrderEngineeringBaselineItem,
    ProductManufacturingOutput, RoutingStep,
    ProductionPlanOperationRequirementAllocation,
)
from .operation_requirement_service import (
    OperationRequirementError, OperationRequirementService, VIEW, _active, _authorize,
    _plan_source_consistency, _read_once, _requirement_read_cache, _source_read_cache,
)
from .operation_requirement_correction_service import requirement_lifecycle

CONTRACT = 'PCE-ENGINEERING-WORKLOAD-PURPOSE-REVIEW-V1'
# Canonical final quantities are explicit business contracts, not name matching.
PURPOSES = {
    'BoardNetAreaSummary': ('CUTTING', '板材开料面积'),
    'PaintingProcessAreaQuantity': ('PAINTING', '油漆来源候选面积'),
    'DoorAssemblyQuantity': ('DOOR_ASSEMBLY', '房门组装套数'),
}


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _number(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _text(value):
    if value is None:
        return None
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _key(value):
    return sha256(canonical_json(value).encode('utf-8')).hexdigest()


def _reason(code, label):
    return {'code': code, 'statusLabel': label}


def _unique(reasons):
    return list({(row['code'], row['statusLabel']): row for row in reasons}.values())


def _unit(unit):
    return {'uomId': unit.pk, 'uomCode': unit.code, 'uomLabel': unit.name} if unit else {
        'uomId': None, 'uomCode': None, 'uomLabel': '单位未知'}


def _dimensions(base, output, unit, *, purpose, mode=None, product_type=None, workshop=None,
                quantity_basis='SOURCE_SCOPE_TOTAL'):
    item = base.sales_order_item
    version = output.routing_version if output else None
    route = version.routing if version and version.routing_id else None
    return {'companyId': base.company_id, 'sourceRecordId': base.source_record_id,
        'sourceCalculationId': base.pk, 'salesOrderId': item.sales_order_id,
        'salesOrderItemId': item.pk, 'lineNo': item.line_no, 'orderNo': item.sales_order.order_no,
        'baselineId': output.order_engineering_baseline_id if output else None,
        'routingId': route.pk if route else None, 'routingCode': route.routing_code if route else None,
        'routingVersionId': version.pk if version else None,
        'routingVersionLabel': f'版本ID {version.pk} / {version.routing_version}' if version else '适用版本未知',
        'manufacturingModeId': mode.pk if mode else None,
        'manufacturingModeVersion': mode.version if mode else None,
        'manufacturingModeLabel': f'{mode.name} / {mode.version}' if mode else '制造模式未证明',
        'productTypeId': product_type.pk if product_type else None,
        'productionGroupId': workshop.pk if workshop else None,
        'productionGroupLabel': workshop.name if workshop else '生产组归属未证明',
        'quantityBasis': quantity_basis, 'quantityBasisLabel': '完整来源范围总量' if quantity_basis == 'SOURCE_SCOPE_TOTAL' else '每基准数量',
        'purposeCode': purpose,
        'sourceScopeLabel': f'{item.sales_order.order_no} 第{item.line_no}行；基线{output.order_engineering_baseline_id if output else "未知"}',
        **_unit(unit)}


def _identity(dimensions):
    # Order-line scope is a deliberate finer partition: scope cannot silently grow.
    return [dimensions.get(key) for key in ('companyId', 'sourceRecordId', 'salesOrderItemId',
        'baselineId', 'purposeCode', 'productionGroupId', 'routingId', 'routingVersionId',
        'manufacturingModeId', 'manufacturingModeVersion', 'productTypeId', 'quantityBasis', 'uomId')]


def _group(dimensions, purpose_label):
    return {'key': _key(_identity(dimensions)), 'purposeCode': dimensions['purposeCode'],
        'purposeLabel': purpose_label, 'dimensions': dimensions, 'statusLabel': '只读评审；不代表已执行投产或排产准入',
        'engineeringCandidate': {'quantity': None, 'uomLabel': dimensions['uomLabel'], 'statusLabel': '对应数量未知'},
        'confirmedPlan': {'quantity': None, 'uomLabel': dimensions['uomLabel'],
            'statusLabel': '对应数量未知', 'scopeLabel': dimensions['sourceScopeLabel'],
            'sourceLabel': '既有计划数量服务', 'plans': []},
        'comparison': {'allowed': False, 'difference': None, 'statusLabel': '用途、单位或对象范围尚未全部证明，不计算差额'},
        'contributions': [], 'missingReasons': []}


def _finish_candidate(group):
    if group.get('candidateAmbiguous'):
        return
    contributions = group['contributions']
    seen, total = set(), Decimal(0)
    for row in contributions:
        identity = row['contributionIdentity']
        value = _number(row['quantity'])
        if identity in seen or value is None:
            group['missingReasons'].append(_reason('CONTRIBUTION_IDENTITY_UNPROVEN',
                '来源贡献重复或数量未知；未选择最大ID、未按数值去重'))
            return
        seen.add(identity)
        total += value
    if contributions:
        physical_source = group['purposeCode'] == 'PHYSICAL_SOURCE'
        source_only = physical_source or any(reason['code'] == 'PURPOSE_DIMENSIONS_UNKNOWN' for reason in group['missingReasons'])
        group['engineeringCandidate'].update(quantity=None if source_only else _text(total),
            sourceQuantity=_text(total), statusLabel='正式物理来源量已知；生产用途、生产组或模式未证明，候选量未知' if physical_source else
                '正式来源量已知；生产组或模式映射未证明，候选量未知' if source_only else '已保存正式来源候选量')


def _plan_read(user, bases, *, read_cache=None, source_plan_cache=None):
    decision = AuthorizationService.decide(user=user, action_code='planning.view',
        organization_id=str(user.company_id), business_object={'organizationId': str(user.company_id), 'departmentId': None})
    if not decision.get('allowed'):
        return {'allowed': False, 'statusLabel': '计划数量受限：当前账号没有既有计划查看权限'}, {}, {}
    by_item, allocations = defaultdict(list), {}
    plans = ProductionPlan.objects.filter(
        planning_requirement__demand__sales_order_item_id__in=[base.sales_order_item_id for base in bases],
        planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id,
    ).select_related('planning_requirement__demand__sales_order_item__uom',
        'planning_requirement__demand__sales_order_item__sales_order',
        'planning_requirement__demand__manufacturing_output__routing_version__routing',
        'planning_requirement__demand__manufacturing_output__order_engineering_instance',
        'planning_requirement__demand__manufacturing_output__order_engineering_baseline',
        'planning_requirement__demand__manufacturing_output__engineering_document_version',
        'planning_requirement__demand__manufacturing_output__bom_version')
    for plan in plans:
        requirement, demand = plan.planning_requirement, plan.planning_requirement.demand
        item = demand.sales_order_item
        facts = planning_quantity_facts(demand_qty=demand.required_qty, requirement=requirement, plan=plan)
        output = demand.manufacturing_output
        by_item[item.pk].append({'id': plan.pk, 'planNo': plan.plan_no,
            'quantity': facts['effectivePlanQty'], 'recordedQuantity': facts['recordedPlanQty'],
            'statusLabel': plan.get_status_display(), 'effective': facts.get('effectivePlanStatus') is not None,
            'manufacturingOutputId': output.pk if output else None,
            'routingVersionId': output.routing_version_id if output else None, **_unit(item.uom),
            'scopeLabel': f'订单行ID {item.pk} / 页面第{item.line_no}行',
            'quantityFacts': facts})
        # The original read validates allocations and preserves its confirmed-only
        # admission contract. It does not run readiness, allocation or dates.
        allocations[plan.pk] = OperationRequirementService.read(user=user, production_plan_id=plan.pk,
            _read_cache=read_cache)
        if source_plan_cache is not None:
            source_plan_cache[plan.pk] = plan
        invalid_ids = [row['allocationId'] for row in allocations[plan.pk].get('blockers', []) if row.get('allocationId')]
        requirement_by_allocation = dict(ProductionPlanOperationRequirementAllocation.objects.filter(
            pk__in=invalid_ids, company_id=user.company_id, production_plan=plan).values_list('pk', 'operation_requirement_id'))
        allocations[plan.pk]['blockers'] = [{**row, 'operationRequirementId': requirement_by_allocation.get(row.get('allocationId'))}
            for row in allocations[plan.pk].get('blockers', [])]
    return {'allowed': True, 'statusLabel': '已按既有计划查看权限读取'}, by_item, allocations


def _plan_column(group, plan_rows, allowed, *, physical=False, physical_scope_proved=False, output=None):
    if not allowed:
        group['confirmedPlan'].update(statusLabel='受限：没有计划查看权限')
        return
    group['confirmedPlan']['plans'] = plan_rows
    if not physical:
        group['missingReasons'].append(_reason('PLAN_PURPOSE_QUANTITY_UNKNOWN',
            '计划原单位保留；尚无该用途与对象的正式数量映射，不能自动换算'))
        return
    matching = [row for row in plan_rows if row['effective'] and row['uomId'] == group['dimensions']['uomId']
        and output and row['manufacturingOutputId'] == output.pk
        and row['routingVersionId'] == group['dimensions']['routingVersionId']]
    if matching and physical_scope_proved:
        total = sum((_number(row['quantity']) for row in matching), Decimal(0))
        group['confirmedPlan'].update(quantity=_text(total), statusLabel='既有有效计划量（已确认/已发布）；原计划单位')
    elif not plan_rows:
        group['confirmedPlan']['statusLabel'] = '未保存该范围计划；对应数量未知'


def _eor_contribution(base, output, fact, requirement, *, historical=False):
    """Compact trace, with producer and this exact EOR's rule kept distinct."""
    trace = _mapping(fact.trace)
    group = _mapping(trace.get('group'))
    item = base.sales_order_item
    baseline_id = trace.get('baselineId') or output.order_engineering_baseline_id
    return {'contributionIdentity': f'eor:{requirement.pk}',
        'orderNo': item.sales_order.order_no, 'lineNo': item.line_no, 'salesOrderItemId': item.pk,
        'designItemId': trace.get('designItemId') or group.get('designItemId'),
        'baselineItemId': trace.get('baselineItemId') or group.get('baselineItemId'),
        'baselineId': baseline_id, 'sourceCalculationId': requirement.source_calculation_id,
        'originCalculationId': base.pk, 'sourceFactId': fact.pk,
        'ruleCode': fact.rule.rule_code, 'ruleVersion': fact.source_detail.rule_version,
        'operationRequirementId': requirement.pk,
        'operationRuleCode': requirement.source_detail.rule_code,
        'operationRuleVersion': requirement.source_detail.rule_version,
        'quantity': _text(requirement.workload_quantity), 'uomLabel': requirement.uom.name,
        'sourceScopeLabel': f'{item.sales_order.order_no} 第{item.line_no}行；来源基线{baseline_id or "未知"}',
        'statusLabel': '已被替代；仅供历史追溯' if historical else '有效工序需求；与已分配计划负荷分别表达'}


def _capacity(req, quantity, dimensions):
    result = {'quantity': None, 'uomLabel': dimensions['uomLabel'], 'timeBasisLabel': '天',
        'theoreticalResourceDays': None, 'theoreticalResourceDaysLabel': '对应资源天未知',
        'capacityScopeLabel': '产能用途待证明', 'admissionStatusLabel': '不授予APS资格',
        'statusLabel': '匹配产能未知'}
    capacity = req.standard_capacity
    if not capacity:
        return result
    result.update(standardCapacityId=capacity.pk, effectiveFrom=str(capacity.effective_from) if capacity.effective_from else None,
        effectiveTo=str(capacity.effective_to) if capacity.effective_to else None,
        applicabilityPeriodLabel=f'{capacity.effective_from or "生效日期未知"} 至 {capacity.effective_to or "未设截止日"}')
    try:
        scope = capacity_usage_scope_proof(capacity)
    except OperationRequirementError as exc:
        result['statusLabel'] = exc.message
        return result
    result['capacityScopeLabel'] = '仅限工程工序需求，不可作为APS可用产能' if scope else '既有产能合同；未在本轮放行APS'
    result['admissionStatusLabel'] = '仅限工程需求，禁止APS放行' if scope else '只读理论数量匹配，不代表分配或排程通过'
    value = _number(capacity.quantity)
    if (not _active(capacity) or capacity.company_id != req.calculation.company_id
        or capacity.uom_id != req.uom_id or capacity.operation_id != req.operation_id
        or capacity.work_center_id != req.work_center_id or capacity.product_type_id != dimensions['productTypeId']
        or capacity.measurement_status != 'measured' or capacity.time_basis != 'day'
        or capacity.time_unit != 'DAY' or capacity.time_basis_quantity != Decimal(1)
        or value is None or value <= 0):
        result['statusLabel'] = '用途、资源、单位、有效期或1天基数未匹配，资源天未知'
        return result
    ratio = Fraction(quantity) / Fraction(value)
    with localcontext() as context:
        context.prec = 28
        days = quantity / value
    result.update(quantity=_text(value), theoreticalResourceDays=_text(days),
        theoreticalResourceDaysLabel=f'{ratio.numerator}/{ratio.denominator} 资源天' if ratio.denominator != 1 else f'{ratio.numerator} 资源天',
        statusLabel='标准日产能与有效工程负荷匹配；不生成日期')
    return result


def _append_requirement_load(*, user, req, fact, base, output, kind, purpose, label,
        loads, effective_ids, access, plans, allocation_reads, source_plan_cache, source_read_cache,
        scope_plan_id=None, saved_step_id=None):
    """One official EOR per load; allocation proofs stay in the native reader."""
    if scope_plan_id is None and req.pk in effective_ids:
        return
    effective_ids.add(req.pk)
    manufacturing = _mapping(_mapping(req.calculation.trace).get('sourceSnapshot')).get('manufacturing', {})
    routing = _mapping(manufacturing.get('routingContext'))
    step_id = saved_step_id or routing.get('routingStepId')
    # Reuse only raw route rows in this typed, transaction-bound read cache.
    # Every occurrence still applies the original step and ambiguity checks.
    steps = _read_once(_requirement_read_cache(source_read_cache, user.company_id),
        ('purpose_routing_steps', user.company_id, output.routing_version_id, step_id, req.operation_id),
        lambda: list(RoutingStep.objects.filter(routing_version_id=output.routing_version_id,
            operation_id=req.operation_id).order_by('sequence')))
    if step_id:
        steps = [step for step in steps if step.pk == step_id]
    step = steps[0] if len(steps) == 1 else None
    dimensions = _dimensions(base, output, req.uom, purpose=purpose, mode=req.manufacturing_mode,
        product_type=req.standard_capacity.product_type if req.standard_capacity_id else kind,
        workshop=req.work_center.workshop if req.work_center_id else None, quantity_basis=req.quantity_basis)
    if scope_plan_id is not None:
        dimensions['productionPlanId'] = scope_plan_id
    dimensions.update(routingStepId=step.pk if step else None, operationId=req.operation_id,
        workCenterId=req.work_center_id, standardCapacityId=req.standard_capacity_id,
        capacityEffectiveFrom=str(req.standard_capacity.effective_from) if req.standard_capacity_id else None,
        capacityEffectiveTo=str(req.standard_capacity.effective_to) if req.standard_capacity_id else None)
    load_key = _key([*_identity(dimensions), dimensions['routingStepId'], req.operation_id,
        req.work_center_id, req.standard_capacity_id, dimensions['capacityEffectiveFrom'], dimensions['capacityEffectiveTo'],
        None if step else req.pk, *([scope_plan_id] if scope_plan_id is not None else [])])
    load = loads.setdefault(load_key, {'key': load_key, 'dimensions': dimensions, 'purposeLabel': label,
        'operationName': req.operation.name, 'stepSequence': step.sequence if step else None,
        'workCenterLabel': req.work_center.name if req.work_center_id else '工作中心未知',
        'effectiveQuantity': '0', 'uomLabel': dimensions['uomLabel'], 'allocatedQuantity': None,
        'allocationStatusLabel': '未分配' if access['allowed'] else '分配读取受限：没有计划查看权限',
        'requirementIds': [], 'contributions': [], 'missingReasons': [], '_requirements': [], '_allocated': []})
    if req.pk in load['requirementIds']:
        return
    load['effectiveQuantity'] = _text(Decimal(load['effectiveQuantity']) + req.workload_quantity)
    load['requirementIds'].append(req.pk); load['_requirements'].append(req)
    load['contributions'].append(_eor_contribution(base, output, fact, req))
    if not step:
        load['missingReasons'].append(_reason('STEP_POSITION_UNKNOWN', '正式路线步骤不能唯一对应，保留工序负荷但不合并步骤用途'))
    if routing.get('stepApplicability', {}).get('resolutionMode') == 'TERMINAL_VERSION_COMPATIBILITY' or routing.get('stepApplicability', {}).get('contractExplicit') is False:
        load['missingReasons'].append(_reason('STEP_COMPATIBILITY', '沿用既有终态版本步骤兼容机制；未建立显式步骤合同，不仅因兼容标记判阻断'))
    if req.source_calculation_id != output.engineering_calculation_id:
        candidate_plans = [row for row in plans.get(base.sales_order_item_id, [])
            if row['effective'] and (scope_plan_id is None or row['id'] == scope_plan_id)] if access['allowed'] else []
        if not candidate_plans:
            load['missingReasons'].append(_reason('ALLOCATION_SOURCE_NOT_ASSESSED',
                '尚无可读取的有效计划来源上下文；主核算与正式扩展关系须由既有计划准入服务核验'))
        else:
            source_errors = []
            for plan_row in candidate_plans:
                plan_id = plan_row['id']
                if plan_id not in source_plan_cache:
                    source_plan_cache[plan_id] = ProductionPlan.objects.select_related(
                        'planning_requirement__demand__manufacturing_output',
                        'planning_requirement__demand__sales_order_item__sales_order').filter(
                        pk=plan_id, planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id).first()
                plan = source_plan_cache[plan_id]
                if plan is None:
                    source_errors.append(_reason('PLAN_NOT_FOUND', '正式计划不存在或不属于当前公司'))
                    continue
                try:
                    _plan_source_consistency(user.company_id, plan, req,
                        routing_step=step, read_cache=source_read_cache)
                except OperationRequirementError as exc:
                    source_errors.append(_reason(exc.code, exc.message))
                else:
                    break
            else:
                load['missingReasons'].extend(source_errors)
    if access['allowed']:
        for plan_id, read in allocation_reads.items():
            if scope_plan_id is not None and plan_id != scope_plan_id:
                continue
            scoped_blockers = [row for row in read.get('blockers', []) if row.get('operationRequirementId') == req.pk]
            if scoped_blockers:
                load['allocationStatusLabel'] = '保存分配校验受阻；对应数量未知'
                load['missingReasons'].extend(scoped_blockers)
            for allocation in read.get('allocations', []):
                if allocation['operationRequirementId'] == req.pk and (scope_plan_id is None
                    or allocation['routingStepId'] == dimensions['routingStepId']):
                    load['_allocated'].append(allocation)


@transaction.atomic
def build_purpose_review(*, user, calculations, _read_cache=None):
    started = perf_counter()
    _authorize(user, VIEW)
    source_read_cache = _source_read_cache(user, _read_cache)
    source_plan_cache = {}
    bases = list(EngineeringCalculationRecord.objects.filter(pk__in=[row.pk for row in calculations],
        company_id=user.company_id, scope='order_engineering', status='completed').select_related(
            'source_record', 'sales_order_item__sales_order', 'sales_order_item__uom', 'engineering_instance'))
    access, plans, allocation_reads = _plan_read(user, bases,
        read_cache=source_read_cache, source_plan_cache=source_plan_cache)
    result = {'contractVersion': CONTRACT, 'factSource': 'server', 'readStatus': 'loaded',
        'statusLabel': '按用途分组的只读评审；候选量和计划量分列，不授予排产资格',
        'planningAccess': access, 'groups': [], 'operationLoads': [], 'historyRequirements': [],
        'missingReasons': [], 'businessWriteCount': 0,
        'counts': {'effectiveRequirementCount': 0, 'historicalRequirementCount': 0}}
    groups, loads, effective_ids, historical_ids = {}, {}, set(), set()
    contribution_owners = {}
    # Only this atomic read owns these ORM/proof caches. The source service is
    # authoritative; different calculation IDs alone are not an incompatibility.
    for base in bases:
        outputs = list(ProductManufacturingOutput.objects.filter(engineering_calculation=base,
            order_engineering_instance_id=base.engineering_instance_id,
            order_engineering_instance__company_id=user.company_id,
            release_status='released_to_manufacturing').select_related('routing_version__routing', 'order_engineering_baseline'))
        if len(outputs) != 1:
            result['missingReasons'].append(_reason('FIXED_OUTPUT_UNPROVEN', f'核算{base.pk}未唯一对应正式制造发布，未猜测版本'))
            continue
        output = outputs[0]
        kinds = list(CapacityProductType.objects.filter(company_id=user.company_id,
            product_category_id=base.engineering_instance.product_category_id,
            manufacturing_process_type_id=base.engineering_instance.selected_process_type_id, is_active=True))
        kind = kinds[0] if len(kinds) == 1 else None
        baseline_items = list(OrderEngineeringBaselineItem.objects.filter(baseline__in=production_baselines(),
            baseline_id=output.order_engineering_baseline_id, design_item__sales_order_item_id=base.sales_order_item_id,
            design_item__company_id=user.company_id, source_record_id=base.source_record_id,
            confirmable=True).select_related('design_item__physical_uom'))
        physical = {}
        for baseline_item in baseline_items:
            frozen = _mapping(_mapping(baseline_item.content_snapshot).get('designItem'))
            design = baseline_item.design_item
            quantity = _number(frozen.get('physicalQuantity'))
            if (frozen.get('id') != design.pk or frozen.get('physicalUomId') != design.physical_uom_id
                or quantity is None or not design.physical_uom_id):
                result['missingReasons'].append(_reason('PHYSICAL_QUANTITY_UNPROVEN', '固定基线实物数量或正式单位关系不完整'))
                continue
            dimensions = _dimensions(base, output, design.physical_uom, purpose='PHYSICAL_SOURCE', product_type=kind)
            group = physical.setdefault(_key(_identity(dimensions)), _group(dimensions, '正式来源物理数量'))
            group['contributions'].append({'contributionIdentity': f'physical:{baseline_item.pk}',
                'orderNo': dimensions['orderNo'], 'lineNo': dimensions['lineNo'], 'salesOrderItemId': base.sales_order_item_id,
                'designItemId': design.pk, 'baselineItemId': baseline_item.pk, 'sourceCalculationId': base.pk,
                'originCalculationId': base.pk, 'sourceFactId': None, 'ruleCode': None, 'ruleVersion': None,
                'quantity': _text(quantity), 'uomLabel': dimensions['uomLabel'], 'statusLabel': '正式固定基线物理量'})
        physical_total = (sum((_number(row['quantity']) for group in physical.values() for row in group['contributions']), Decimal(0))
            if len(physical) == 1 else None)
        for group in physical.values():
            _finish_candidate(group)
            group['missingReasons'].append(_reason('PHYSICAL_PURPOSE_MAPPING_UNKNOWN', '物理来源量不自动代表房门组装或其他生产用途；制造模式和生产组映射未证明'))
            _plan_column(group, plans.get(base.sales_order_item_id, []), access['allowed'], physical=True,
                physical_scope_proved=len(physical) == 1 and physical_total == base.sales_order_item.quantity, output=output)
            groups[group['key']] = group
        facts = list(EngineeringDerivedFact.objects.filter(
            Q(calculation=base) | Q(calculation__origin_calculation=base, calculation__scope='fact_extension',
                calculation__supersedes__isnull=True), calculation__company_id=user.company_id,
            calculation__status='completed',
            canonical_field__in=PURPOSES, status='active').select_related('calculation', 'source_detail__rule', 'rule', 'uom'))
        by_calc = defaultdict(list)
        for fact in facts:
            if (fact.calculation.source_record_id == base.source_record_id
                and fact.calculation.sales_order_item_id == base.sales_order_item_id
                and fact.calculation.engineering_instance_id == base.engineering_instance_id):
                by_calc[fact.calculation_id].append(fact)
        for calculation_id, selected in by_calc.items():
            try:
                conversion = OperationRequirementService.read_source_conversion(user=user,
                    source_calculation_id=calculation_id, source_fact_ids=[fact.pk for fact in selected],
                    _read_cache=source_read_cache)
                converted = {row['sourceFactId']: row for row in conversion['facts']}
                # Classification preserves the producer's exact GROUP_SUM keys.
                for keys in {tuple(_mapping(fact.rule.specification.get('factExtension')).get('groupKeys', []))
                             for fact in selected if _mapping(fact.rule.specification.get('factExtension')).get('strategy') == 'GROUP_SUM'}:
                    ManufacturingFactBatchService.consolidated_readback(user=user,
                        calculation_ids=[calculation_id], group_keys=list(keys))
            except Exception as exc:
                result['missingReasons'].append(_reason(getattr(exc, 'code', 'FORMAL_SOURCE_READ_FAILED'),
                    getattr(exc, 'message', '正式用途来源读取或校验失败；未以零替代')))
                continue
            requirements = {row.pk: row for row in EngineeringOperationRequirement.objects.filter(
                source_calculation_id=calculation_id, source_fact_id__in=[fact.pk for fact in selected]).select_related(
                'calculation', 'source_detail__rule', 'manufacturing_mode', 'operation', 'uom', 'standard_capacity',
                'work_center__workshop', 'standard_capacity__operation', 'standard_capacity__work_center',
                'standard_capacity__product_type__product_category', 'standard_capacity__product_type__manufacturing_process_type', 'standard_capacity__uom')}
            for fact in selected:
                status = converted.get(fact.pk, {})
                purpose, label = PURPOSES[fact.canonical_field]
                if status.get('sourceProofPassed') is not True:
                    result['missingReasons'].extend(status.get('blockers') or [
                        _reason('SOURCE_PROOF_UNPROVEN', '正式用途来源证明未通过；候选量未知')])
                    continue
                current = [requirements[row['id']] for row in status.get('requirements', [])]
                # Historical rows need their persisted replacement proof, not
                # applicability under today's current version. The native current
                # reader correctly refuses obsolete version inputs.
                historical = list(status.get('historicalRequirements', []))
                known_history = {row['id'] for row in historical}
                for req in requirements.values():
                    if req.source_fact_id != fact.pk or req.pk in known_history:
                        continue
                    lifecycle = requirement_lifecycle(req, user.company_id, read_cache=source_read_cache)
                    if lifecycle and lifecycle['statusCode'] == 'SUPERSEDED':
                        historical.append({'id': req.pk, 'operationName': req.operation.name,
                            'sourceCalculationId': req.source_calculation_id, 'sourceFactId': req.source_fact_id,
                            'lifecycle': lifecycle})
                # A quantity may feed several steps, but each distinct official
                # mode/group combination gets the source contribution only once.
                signatures = {}
                for req in current:
                    workshop = req.work_center.workshop if req.work_center_id else None
                    signature = (req.manufacturing_mode_id, workshop.pk if workshop else None,
                                 req.standard_capacity.product_type_id if req.standard_capacity_id else None, req.quantity_basis)
                    signatures.setdefault(signature, (req.manufacturing_mode, workshop))
                if not signatures:
                    signatures[(None, None, kind.pk if kind else None, 'SOURCE_SCOPE_TOTAL')] = (None, None)
                for signature, (mode, workshop) in signatures.items():
                    mapped_type = next((req.standard_capacity.product_type for req in current
                        if req.standard_capacity_id and req.standard_capacity.product_type_id == signature[2]), None)
                    dimensions = _dimensions(base, output, fact.uom, purpose=purpose, mode=mode,
                        product_type=mapped_type or kind, workshop=workshop, quantity_basis=signature[3])
                    dimensions['areaType'] = fact.trace.get('AreaType')
                    identity = _key([*_identity(dimensions), dimensions['areaType']])
                    group = groups.setdefault(identity, _group(dimensions, label))
                    group['key'] = identity
                    trace = _mapping(fact.trace); object_group = _mapping(trace.get('group'))
                    inputs = list(fact.inputs.order_by('sequence').values_list('source_fact_id', flat=True))
                    design_id = trace.get('designItemId') or object_group.get('designItemId')
                    baseline_item_id = trace.get('baselineItemId') or object_group.get('baselineItemId')
                    contribution_id = _key([purpose, base.pk, dimensions['baselineId'],
                        dimensions['areaType'],
                        [design_id, baseline_item_id] if design_id and baseline_item_id else inputs])
                    previous = contribution_owners.get(contribution_id)
                    if previous and previous[0] != fact.pk:
                        for affected in (previous[1], group):
                            affected['candidateAmbiguous'] = True
                            affected['engineeringCandidate'].update(quantity=None, statusLabel='有效贡献身份冲突，对应数量未知')
                            affected['missingReasons'].append(_reason('CONTRIBUTION_IDENTITY_UNPROVEN',
                                '同对象、用途、基线及来源贡献存在多份正式扩展，未按最大ID或规则版本择一，未重复累计'))
                    else:
                        contribution_owners[contribution_id] = (fact.pk, group)
                    group['contributions'].append({'contributionIdentity': contribution_id,
                        'orderNo': dimensions['orderNo'], 'lineNo': dimensions['lineNo'], 'salesOrderItemId': base.sales_order_item_id,
                        'designItemId': design_id, 'baselineItemId': baseline_item_id,
                        'sourceCalculationId': fact.calculation_id, 'originCalculationId': base.pk,
                        'sourceFactId': fact.pk, 'ruleCode': fact.rule.rule_code, 'ruleVersion': fact.source_detail.rule_version,
                        'sourceFactIds': inputs, 'quantity': _text(_number(fact.value.get('decimal'))),
                        'uomLabel': dimensions['uomLabel'], 'statusLabel': '正式扩展最终用途事实；不加输入中间事实'})
                    if not mode or not workshop or not dimensions['productTypeId']:
                        group['missingReasons'].append(_reason('PURPOSE_DIMENSIONS_UNKNOWN', '缺少正式制造模式、生产组或产能产品类型映射；不并入其他已知组'))
                    group['missingReasons'].extend(status.get('blockers', []))
                    _plan_column(group, plans.get(base.sales_order_item_id, []), access['allowed'])
                for saved in historical:
                    if saved['id'] not in historical_ids:
                        historical_ids.add(saved['id'])
                        historical_req = requirements[saved['id']]
                        old_routing = _mapping(_mapping(_mapping(historical_req.calculation.trace).get('sourceSnapshot')).get('manufacturing')).get('routingContext', {})
                        historical_contribution = _eor_contribution(base, output, fact, historical_req, historical=True)
                        result['historyRequirements'].append({'key': f'history:{saved["id"]}', 'id': saved['id'],
                            'purposeLabel': label, 'operationName': saved.get('operationName'),
                            'sourceCalculationId': saved['sourceCalculationId'], 'sourceFactId': saved['sourceFactId'],
                            'originCalculationId': base.pk, 'workloadQuantity': _text(historical_req.workload_quantity),
                            'uomLabel': historical_req.uom.name,
                            'dimensions': {'orderNo': base.sales_order_item.sales_order.order_no,
                                'lineNo': base.sales_order_item.line_no, 'salesOrderItemId': base.sales_order_item_id,
                                'sourceScopeLabel': historical_contribution['sourceScopeLabel'],
                                'routingVersionId': old_routing.get('routingVersionId'),
                                'routingVersionLabel': f'历史固定版本ID {old_routing.get("routingVersionId", "未知")}'},
                            'contributions': [historical_contribution],
                            'supersededById': saved.get('lifecycle', {}).get('replacementRequirementId'), 'statusLabel': '已被替代；仅供追溯，不进入当前汇总'})
                for req in current:
                    _append_requirement_load(user=user, req=req, fact=fact, base=base, output=output,
                        kind=kind, purpose=purpose, label=label, loads=loads, effective_ids=effective_ids,
                        access=access, plans=plans, allocation_reads=allocation_reads,
                        source_plan_cache=source_plan_cache, source_read_cache=source_read_cache)
        # Purpose candidates and saved operation loads have different authorities.
        # Discover only native-validated saved EORs omitted by the candidate-field
        # whitelist. Raw facts, preview mappings and other unsaved steps are not
        # new purpose quantities. No additional proof/read/save service is run.
        if access['allowed']:
            original_effective_ids = set(effective_ids)
            matching_plans = {row['id'] for row in plans.get(base.sales_order_item_id, [])
                if row['effective'] and row['manufacturingOutputId'] == output.pk
                and row['routingVersionId'] == output.routing_version_id}
            for plan_id in sorted(matching_plans):
                read = allocation_reads[plan_id]
                result['missingReasons'].extend({**reason, 'productionPlanId': plan_id}
                    for reason in read.get('blockers', [])
                    if reason.get('operationRequirementId') not in original_effective_ids)
                saved = read.get('allocations', [])
                saved_ids = {row['operationRequirementId'] for row in saved} - original_effective_ids
                requirements = EngineeringOperationRequirement.objects.filter(
                    Q(source_calculation=base) | Q(source_calculation__origin_calculation=base,
                        source_calculation__scope='fact_extension', source_calculation__supersedes__isnull=True),
                    pk__in=saved_ids, calculation__company_id=user.company_id,
                    source_calculation__company_id=user.company_id,
                    source_calculation__sales_order_item_id=base.sales_order_item_id,
                    source_calculation__source_record_id=base.source_record_id,
                    source_calculation__engineering_instance_id=base.engineering_instance_id,
                    source_calculation__status='completed', source_fact__status='active').select_related(
                        'calculation', 'source_detail__rule', 'manufacturing_mode', 'operation', 'uom',
                        'standard_capacity__product_type', 'work_center__workshop',
                        'source_fact__rule', 'source_fact__source_detail')
                by_id = {req.pk: req for req in requirements}
                for allocation in saved:
                    req = by_id.get(allocation['operationRequirementId'])
                    if req is None:
                        if allocation['operationRequirementId'] in saved_ids:
                            result['missingReasons'].append({**_reason('SAVED_REQUIREMENT_SCOPE_UNPROVEN',
                                '已保存需求未匹配当前正式来源范围，未混入其他订单、版本或对象'),
                                'allocationId': allocation['allocationId'], 'productionPlanId': plan_id,
                                'operationRequirementId': allocation['operationRequirementId']})
                        continue
                    fact = req.source_fact
                    # Exact persisted operation-rule identity and governed source
                    # class partition loads, without inventing a W area purpose.
                    purpose = 'FORMAL_OPERATION:' + _key([req.source_detail.rule_id,
                        req.source_detail.rule_version, _mapping(fact.trace).get('AreaType')])
                    _append_requirement_load(user=user, req=req, fact=fact, base=base, output=output,
                        kind=kind, purpose=purpose, label=f'{req.operation.name}工序需求', loads=loads,
                        effective_ids=effective_ids, access=access, plans=plans, allocation_reads=allocation_reads,
                        source_plan_cache=source_plan_cache, source_read_cache=source_read_cache,
                        scope_plan_id=plan_id, saved_step_id=allocation['routingStepId'])
        for purpose, label in (('FINISH_AREA', '饰面组投产面积'), ('CABINET_AREA', '柜体组投产面积')):
            dimensions = _dimensions(base, output, None, purpose=purpose, product_type=kind)
            group = _group(dimensions, label)
            group['missingReasons'].append(_reason('PURPOSE_SOURCE_MAPPING_UNKNOWN', '当前所选正式来源尚未唯一证明该用途面积与生产组映射；不从开料总面积反推'))
            _plan_column(group, plans.get(base.sales_order_item_id, []), access['allowed'])
            groups[group['key']] = group
    for group in groups.values():
        if group['engineeringCandidate']['quantity'] is None:
            _finish_candidate(group)
        group['missingReasons'] = _unique(group['missingReasons'])
    for load in loads.values():
        req = load.pop('_requirements')[0]
        allocations = list({row['allocationId']: row for row in load.pop('_allocated')}.values())
        if load['dimensions'].get('productionPlanId') is not None:
            # Additive response provenance; existing UI already renders EOR and
            # object contributions. Plan identities remain explicit in the read.
            load['allocations'] = allocations
            for contribution in load['contributions']:
                contribution['allocations'] = [row for row in allocations
                    if row['operationRequirementId'] == contribution['operationRequirementId']]
        if allocations and not any(reason.get('allocationId') for reason in load['missingReasons']):
            load['allocatedQuantity'] = _text(sum((Decimal(row['allocatedQuantity']) for row in allocations), Decimal(0)))
            load['allocationStatusLabel'] = '已保存且通过原服务校验的计划负荷'
        load['capacity'] = _capacity(req, Decimal(load['effectiveQuantity']), load['dimensions'])
        if not load['dimensions']['routingStepId']:
            load['capacity'].update(theoreticalResourceDays=None, theoreticalResourceDaysLabel='步骤位置未知，资源天未知')
        load['missingReasons'] = _unique(load['missingReasons'])
    result.update(groups=list(groups.values()), operationLoads=list(loads.values()),
        counts={'effectiveRequirementCount': len(effective_ids), 'historicalRequirementCount': len(historical_ids)},
        readDurationMs=round((perf_counter() - started) * 1000, 3))
    return result
