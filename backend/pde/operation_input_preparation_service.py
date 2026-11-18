"""Native, plan-bound preparation evidence with no publication/execution path.

Missing sources and unmeasured capacity remain unknown.  This module never
calls a rule writer, fact generator, allocation writer or scheduling service.
"""
from contextvars import ContextVar
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from datetime import date
import re

from django.core.exceptions import ValidationError
from django.db import transaction

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, UnitOfMeasure
from pfm.models import Employee
from system.models import Company, OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state, record_projected_business_transition,
)

from .engineering_rule_foundation import _parse_expression, specification_hash
from .operation_read_diagnostics import read_span
from .models import (
    CapacityProductType, EngineeringRuleDefinition, ManufacturingMode, OperationInputPreparationDraft,
    StandardCapacity, WorkCenter, WorkCenterOperationCapability,
)
from .production_foundation_service import ProductionFoundationError, _actor_chain, _audit, _snapshot
from .plan_step_context_service import effective_baseline, source_selection

CONTRACT = 'PCE-OPERATION-INPUT-PREPARATION-V1'
BASIS_CONTRACT = 'PCE-OPERATION-INPUT-PREPARATION-BASIS-V1'
CAPACITY_RULING_CONTRACT = 'PCE-OPERATION-INPUT-CAPACITY-RULING-V1'
CAPACITY_SOURCE_PROOF_CONTRACT = 'PCE-CAPACITY-SOURCE-PROOF-V1'
CAPACITY_CONSUMPTION_CONTRACT = 'PCE-PLAN-STEP-CAPACITY-CONSUMPTION-REFERENCE-V1'
ACTION = 'pde.operation_input_preparation.save'
ENTITY = 'operation-input-preparation-draft'
OBJECT_TYPE = 'OperationInputPreparationDraft'
CREATE = 'production.engineering.rule.create'
UPDATE = 'production.engineering.rule.update_draft'
CAPACITY = 'production.master_data.capacity.maintain'
VIEW = 'production.engineering.rule.view'
_write_guard = ContextVar('operation_input_preparation_native_write', default=False)
SCOPE_FIELDS = {
    'companyId': 'company_id', 'operationId': 'operation_id', 'productTypeId': 'product_type_id',
    'productionPlanId': 'production_plan_id', 'manufacturingOutputId': 'manufacturing_output_id',
    'mainCalculationId': 'main_calculation_id', 'baselineId': 'engineering_baseline_id',
    'routingVersionId': 'routing_version_id', 'routingStepId': 'routing_step_id',
}
SCOPE_KEYS = set(SCOPE_FIELDS) | {'salesOrderItemId'}


class OperationInputPreparationError(ProductionFoundationError):
    pass


def _fail(code, message, **details):
    raise OperationInputPreparationError('PREPARATION_' + code, message, details)


def _hash(value):
    try:
        return specification_hash(value)
    except (ValueError, TypeError) as error:
        raise OperationInputPreparationError('PREPARATION_PAYLOAD_INVALID', '准备记录必须使用可验证的正式JSON结构') from error


def _positive(value):
    return type(value) is int and value > 0


def _token(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _authorize(user, permission):
    from .operation_requirement_service import _authorize as native_authorize
    try:
        return native_authorize(user, permission)
    except Exception as error:
        if not hasattr(error, 'code'):
            raise
        raise OperationInputPreparationError(error.code, error.message, error.details) from error


def _actor(user):
    chain = _actor_chain(user)
    employee = Employee.objects.select_related('position_ref', 'department_ref').filter(
        pk=chain['employeeId'], user_id=user.pk, status='active').first()
    if (not employee or not employee.position_ref_id or not employee.department_ref_id
            or employee.position_ref.company_id != user.company_id
            or employee.department_ref.company_id != user.company_id):
        _fail('ACTOR_SCOPE_INVALID', '办理人员工、岗位及部门必须属于当前公司')
    return chain


def _scope_impl(user, exact_scope, *, lock=False, read_cache=None):
    """Re-prove the full native source and complete object set on every call."""
    from .routing_object_applicability_service import _load_scope, _contexts
    from .operation_workload_source_service import _scope_context
    from .operation_requirement_service import _requirement_read_cache
    read_cache = None if lock else _requirement_read_cache(read_cache, user.company_id)
    if read_cache is not None and read_cache.user_id != user.pk:
        read_cache = None
    if (not isinstance(exact_scope, dict) or set(exact_scope) != SCOPE_KEYS
            or any(not _positive(exact_scope.get(key)) for key in SCOPE_KEYS)
            or exact_scope['companyId'] != user.company_id):
        _fail('SCOPE_INVALID', '准备记录必须绑定当前公司完整的九项正式FK及订单行范围')
    # Do not load another company's sources even for a rejected request.
    from planning.models import ProductionPlan
    if not ProductionPlan.objects.filter(pk=exact_scope['productionPlanId'],
            planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id).exists():
        _fail('SCOPE_INVALID', '生产计划不属于当前公司')
    native = _load_scope(exact_scope['productionPlanId'], exact_scope['routingStepId'], lock=lock,read_cache=read_cache)
    if lock:
        for row in (native['base'], native['base'].source_record, native['output'].routing_version,
                    native['step'], native['step'].operation, native['output'].routing_version.routing):
            list(type(row).objects.select_for_update().filter(pk=row.pk))
        list(type(native['objects'][0].design_item).objects.select_for_update().filter(
            pk__in=[row.design_item_id for row in native['objects']]))
        list(CapacityProductType.objects.select_for_update().filter(pk=exact_scope['productTypeId'],
            company_id=user.company_id))
        # Fresh instances after all formal roots are locked.
        native = _load_scope(exact_scope['productionPlanId'], exact_scope['routingStepId'], lock=True)
    plan, output, item, base, step, kind, applicability = _scope_context(
        user, exact_scope['productionPlanId'], exact_scope['routingStepId'],_read_cache=read_cache)
    actual = {'companyId': native['company_id'], 'productionPlanId': plan.pk,
        'manufacturingOutputId': output.pk, 'mainCalculationId': base.pk,
        'salesOrderItemId': item.pk, 'baselineId': effective_baseline(plan).pk,
        'routingVersionId': output.routing_version_id, 'routingStepId': step.pk,
        'operationId': step.operation_id, 'productTypeId': kind.pk}
    if exact_scope != actual:
        _fail('CONTEXT_DRIFT', '计划、输出、基线、来源、工序或产品类型已漂移，必须重新读取')
    contexts = _contexts(native, native['objects'])
    coverage = [{key: deepcopy(detail[key]) for key in (
        'baselineItemId', 'designItemId', 'designItemVersion', 'objectContentHash',
        'sourceRecordId', 'sourceVersion', 'sourceContentHash')} for detail in contexts]
    coverage.sort(key=lambda row: (row['baselineItemId'], row['designItemId']))
    context = {'contractVersion': CONTRACT, 'exactScope': actual,
        'objectsHash': _hash(coverage), 'formalContexts': contexts,
        'routingVersionHash': _hash(_snapshot(output.routing_version)),
        'routingStepHash': _hash(_snapshot(step)), 'productTypeHash': _hash(_snapshot(kind)),
        'operationHash': _hash(_snapshot(step.operation)),
        'manufacturingOutputHash': _hash(_snapshot(output))}
    selection = source_selection(plan)
    if selection is not None:
        context['sourceSelection'] = deepcopy(selection)
    return {'scope': actual, 'native': native, 'kind': kind, 'context': context, 'applicability': applicability,
        '_reader': user, '_read_cache': read_cache, '_lock': lock,
        'coverage': coverage, 'context_hash': _hash(context), 'objects_hash': _hash(coverage)}


def _consumption_scope_impl(user, exact_scope, *, lock=False, read_cache=None):
    """Saved-load scope uses frozen inputs, never a current design edit version."""
    from planning.models import ProductionPlan
    from . import operation_requirement_service as operation
    from .daily_capacity_service import _validated_demand_object_coverage
    from .engineering_fact_metadata import _prepare_origin
    from .operation_workload_source_service import _scope_context
    from .routing_object_applicability_service import _contexts
    if (not isinstance(exact_scope, dict) or set(exact_scope) != SCOPE_KEYS
            or any(not _positive(exact_scope.get(key)) for key in SCOPE_KEYS)
            or exact_scope['companyId'] != user.company_id):
        _fail('SCOPE_INVALID', '无日期消费引用必须绑定本公司完整正式范围')
    if not ProductionPlan.objects.filter(pk=exact_scope['productionPlanId'],
            planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id).exists():
        _fail('SCOPE_INVALID', '生产计划不属于当前公司')
    cache = operation._source_read_cache(user, None if lock else read_cache)

    def load():
        plan, output, item, base, step, kind, applicability = _scope_context(
            user, exact_scope['productionPlanId'], exact_scope['routingStepId'], _read_cache=None if lock else cache)
        origin = _prepare_origin(base, read_cache=None if lock else cache)
        baseline = effective_baseline(plan)
        actual = {'companyId': user.company_id, 'productionPlanId': plan.pk,
            'manufacturingOutputId': output.pk, 'mainCalculationId': base.pk,
            'salesOrderItemId': item.pk, 'baselineId': baseline.pk if baseline else None,
            'routingVersionId': output.routing_version_id, 'routingStepId': step.pk,
            'operationId': step.operation_id, 'productTypeId': kind.pk}
        if (actual != exact_scope or origin['baseline'].pk != actual['baselineId']
                or applicability.get('result') != 'REQUIRED'):
            _fail('CONTEXT_DRIFT', '无日期消费的固定来源、完整范围或正式必经结论不一致')
        objects = sorted(origin['byItem'].values(),
            key=lambda obj: (obj.source_attribute_id, obj.design_item_id, obj.pk))
        if any(not obj.confirmable for obj in objects):
            _fail('CONTEXT_DRIFT', '冻结基线含不可确认对象，不能配置消费引用')
        native = {'company_id': user.company_id, 'plan': plan,
            'demand': plan.planning_requirement.demand, 'item': item, 'output': output,
            'base': base, 'baseline': baseline, 'step': step, 'objects': objects,
            'reference': base.trace['baselineReference']}
        return native, kind, applicability

    native, kind, applicability = load()
    if lock:
        roots = [native[key] for key in ('plan', 'output', 'base', 'baseline', 'step')]
        roots += [native['base'].source_record, native['base'].engineering_instance,
            native['output'].routing_version, native['output'].routing_version.routing,
            native['step'].operation, kind]
        roots += native['objects']
        roots += [obj.design_item for obj in native['objects']]
        roots += [obj.source_attribute for obj in native['objects']]
        for root in roots:
            list(type(root).objects.select_for_update().filter(pk=root.pk))
        native, kind, applicability = load()
    plan, output, item, step = (native[key] for key in ('plan', 'output', 'item', 'step'))
    demand = operation.process_demand_for_plan(plan, output, item,
        {'stepId': step.pk, 'operationId': step.operation_id}, company_id=user.company_id,
        user=user, read_cache=cache)
    if demand is None:
        _fail('CAPACITY_REFERENCE_INVALID', '无日期消费引用必须已有本步骤原生已保存负荷')
    proved = _validated_demand_object_coverage(plan, output, item,
        {'stepId': step.pk, 'operationId': step.operation_id}, demand,
        company_id=user.company_id, read_cache=cache)
    if (proved['designItemIds'] != {obj.design_item_id for obj in native['objects']}
            or proved['baselineItemIds'] != {obj.pk for obj in native['objects']}):
        _fail('CAPACITY_REFERENCE_INVALID', '原生负荷必须完整覆盖冻结基线，不得由分配推定或缩小完整对象集合')
    contexts = _contexts(native, native['objects'])
    coverage = [{key: deepcopy(detail[key]) for key in ('baselineItemId', 'designItemId',
        'designItemVersion', 'objectContentHash', 'sourceRecordId', 'sourceVersion', 'sourceContentHash')}
        for detail in contexts]
    coverage.sort(key=lambda row: (row['baselineItemId'], row['designItemId']))
    context = {'contractVersion': CONTRACT, 'consumer': 'ALLOCATED_LOAD_NO_DATE',
        'exactScope': deepcopy(exact_scope), 'objectsHash': _hash(coverage), 'formalContexts': contexts,
        'routingVersionHash': _hash(_snapshot(output.routing_version)),
        'routingStepHash': _hash(_snapshot(step)), 'productTypeHash': _hash(_snapshot(kind)),
        'operationHash': _hash(_snapshot(step.operation)), 'manufacturingOutputHash': _hash(_snapshot(output)),
        'frozenInputHash': native['base'].input_hash}
    selection = source_selection(plan)
    if selection is not None:
        context['sourceSelection'] = deepcopy(selection)
    load_key = ('input_preparation_consumption_load', user.company_id, user.pk, _hash(context))
    if not lock:
        # Only a same-snapshot typed read may reuse this already native-proved
        # load. A write clears the entry; locked writes always prove it again.
        cache[load_key] = deepcopy((demand, proved))
    return {'scope': deepcopy(exact_scope), 'native': native, 'kind': kind, 'context': context,
        'applicability': applicability, '_reader': user, '_read_cache': cache, '_lock': lock,
        '_consumption_load_key': load_key if not lock else None,
        '_consumption_saved_quantity': str(demand['quantity']),
        'coverage': coverage, 'context_hash': _hash(context), 'objects_hash': _hash(coverage)}


def _scope(user, exact_scope, *, lock=False, read_cache=None, conditional=False, policy_basis=None, consumer=None):
    try:
        if consumer not in (None, 'ALLOCATED_LOAD_NO_DATE'):
            _fail('CAPACITY_REFERENCE_INVALID', '仅支持明确的已保存负荷无日期消费用途')
        if consumer is not None or _has_capacity_reference(policy_basis):
            return _consumption_scope_impl(user, exact_scope, lock=lock, read_cache=read_cache)
        from .conditional_execution_preparation import is_quantity_basis, build_quantity_policy_context
        if is_quantity_basis(policy_basis):
            policy = policy_basis.get('quantityPolicy')
            reference = policy.get('statisticalUomReference') if isinstance(policy, dict) else None
            capacity = policy.get('capacityReference') if isinstance(policy, dict) else None
            if not isinstance(reference, dict) or not isinstance(capacity, dict):
                _fail('QUANTITY_POLICY_INVALID', '数量政策必须提供明确的统计单位及产能引用')
            return build_quantity_policy_context(user=user, exact_scope=exact_scope, lock=lock,
                statistical_routing_step_id=reference.get('routingStepId'),
                standard_capacity_id=capacity.get('standardCapacityId'), read_cache=read_cache)
        if conditional:
            from .conditional_execution_preparation import build_conditional_context
            return build_conditional_context(user=user, exact_scope=exact_scope, lock=lock, read_cache=read_cache)
        return _scope_impl(user, exact_scope, lock=lock,read_cache=read_cache)
    except OperationInputPreparationError:
        raise
    except Exception as error:
        if not isinstance(error, ValidationError) and not hasattr(error, 'code'):
            raise
        _fail('CONTEXT_DRIFT', '正式计划、来源版本或完整对象关系校验失败，必须重新读取',
            sourceCode=getattr(error, 'code', 'VALIDATION_ERROR'))


def _basis(value, scope, *, save_only=False):
    from .conditional_execution_preparation import is_conditional_basis, validate_basis, is_quantity_basis, validate_quantity_basis
    if is_quantity_basis(value):
        return validate_quantity_basis(value, scope)
    if is_conditional_basis(value):
        return validate_basis(value, scope)
    if scope.get('conditional') or scope.get('quantity_policy'):
        _fail('CONDITIONAL_INVALID', '条件准备协议不可被删除或替换为对象投入合同')
    scope.pop('_capacity_reference', None)
    if (not isinstance(value, dict) or set(value) != {'contractVersion', 'entries'}
            or value.get('contractVersion') != BASIS_CONTRACT
            or not isinstance(value.get('entries'), list) or not value['entries']):
        _fail('BASIS_INVALID', '必须保存版本化原答复、出处Hash及精确业务范围')
    seen = set()
    for entry in value['entries']:
        required = {'reference', 'referenceSha256', 'exactStatement', 'scope', 'objectCoverage'}
        if (not isinstance(entry, dict) or not required.issubset(entry)
                or set(entry) - required - {'capacityRuling', 'capacityConsumptionReference'}
                or any(not isinstance(entry.get(key), str) or not entry[key].strip()
                       for key in ('reference', 'exactStatement'))
                or not _token(entry.get('referenceSha256'))
                or entry['scope'] != scope['scope'] or entry['objectCoverage'] != scope['coverage']):
            _fail('BASIS_INVALID', '原答复必须绑定完整正式对象集合、Hash和本次唯一范围')
        if 'capacityRuling' in entry:
            _validate_capacity_ruling(entry, scope)
        if 'capacityConsumptionReference' in entry:
            if 'capacityRuling' in entry:
                _fail('CAPACITY_REFERENCE_INVALID', '正产能引用不能同时声明0裁决')
        identity = (entry['reference'], entry['referenceSha256'], entry['exactStatement'])
        if identity in seen:
            _fail('BASIS_INVALID', '原答复条目不得重复')
        seen.add(identity)
    _hash(value)
    result = deepcopy(value)
    references = [entry for entry in result['entries'] if 'capacityConsumptionReference' in entry]
    if references:
        # Older entries remain immutable historical selections. Only the last
        # explicit reference is current; history is proved by native audits.
        current = references[-1]
        current['capacityConsumptionReference'] = _resolve_capacity_reference(
            scope, current['capacityConsumptionReference'], save_only=save_only)
        for entry in references[:-1]:
            _reference_pointer(entry['capacityConsumptionReference'], canonical=True)
        scope['_capacity_reference'] = current['capacityConsumptionReference']
    return result


def build_capacity_consumption_reference(*, standard_capacity_id, product_type_id, source_sha256,
        source_effective_date, effective_from, effective_to=None):
    """Typed maintenance intent; no client quantity, unit, time or eligibility."""
    return {'contractVersion': CAPACITY_CONSUMPTION_CONTRACT, 'consumer': 'ALLOCATED_LOAD_NO_DATE',
        'standardCapacityId': standard_capacity_id,
        'unifiedTimeSource': {'referenceType': 'FORMAL_CAPACITY_SOURCE_RULES_HEADER',
            'productTypeId': product_type_id, 'sourceSha256': source_sha256,
            'effectiveDate': source_effective_date},
        'effectiveFrom': effective_from, 'effectiveTo': effective_to}


def _has_capacity_reference(basis):
    return (isinstance(basis, dict) and isinstance(basis.get('entries'), list)
        and any(isinstance(entry, dict) and 'capacityConsumptionReference' in entry
            for entry in basis['entries']))


def _reference_pointer(value, *, canonical=False):
    keys = {'contractVersion', 'consumer', 'standardCapacityId', 'unifiedTimeSource', 'effectiveFrom', 'effectiveTo'}
    if (not isinstance(value, dict) or set(value) != keys | ({'proof'} if canonical else set())
            or value.get('contractVersion') != CAPACITY_CONSUMPTION_CONTRACT
            or value.get('consumer') != 'ALLOCATED_LOAD_NO_DATE'
            or not _positive(value.get('standardCapacityId'))):
        _fail('CAPACITY_REFERENCE_INVALID', '正产能消费引用必须使用精确版本化指针，不接受客户端数量、单位或资格')
    source = value['unifiedTimeSource']
    if (not isinstance(source, dict) or set(source) != {'referenceType', 'productTypeId', 'sourceSha256', 'effectiveDate'}
            or source.get('referenceType') != 'FORMAL_CAPACITY_SOURCE_RULES_HEADER'
            or not _positive(source.get('productTypeId')) or not _token(source.get('sourceSha256'))):
        _fail('CAPACITY_REFERENCE_INVALID', '统一时间必须引用正式来源合同及准确产品类型和Hash')
    try:
        start = date.fromisoformat(value['effectiveFrom'])
        end = date.fromisoformat(value['effectiveTo']) if value['effectiveTo'] is not None else None
        date.fromisoformat(source['effectiveDate'])
        if end is not None and end < start:
            raise ValueError
    except (TypeError, ValueError):
        _fail('CAPACITY_REFERENCE_INVALID', '消费关系及统一来源必须使用有效日期区间')
    if canonical and (not isinstance(value['proof'], dict) or not value['proof']):
        _fail('CAPACITY_REFERENCE_INVALID', '已保存引用缺少服务端绑定证明，读取不得补造')
    return start, end


def _resolve_capacity_reference(scope, value, *, save_only=False):
    try:
        return _resolve_capacity_reference_impl(scope, value, save_only=save_only)
    except OperationInputPreparationError:
        raise
    except Exception as error:
        if not hasattr(error, 'code'):
            raise
        raise OperationInputPreparationError(error.code, getattr(error, 'message', str(error)),
            getattr(error, 'details', {})) from error


def _resolve_capacity_reference_impl(scope, value, *, save_only=False):
    from . import operation_requirement_service as native
    from . import daily_capacity_service as daily
    from .manufacturing_capacity_scope import capacity_usage_scope_proof
    from .models import ProductionPlanOperationRequirementAllocation
    canonical = isinstance(value, dict) and 'proof' in value
    start, end = _reference_pointer(value, canonical=canonical)
    if not save_only and not canonical:
        _fail('CAPACITY_REFERENCE_INVALID', '已保存引用必须包含原生证明，不能在读取时升级裸指针')
    user = scope.get('_reader')
    if user is None:
        _fail('CAPACITY_REFERENCE_INVALID', '消费关系必须使用本次真实读取账号')
    today = scope.get('_reference_on_date') or native._today()
    if not isinstance(today, date) or today < start or end is not None and today > end:
        _fail('CAPACITY_REFERENCE_INACTIVE', '本次评估日不在正式消费关系生效区间')
    if scope['applicability'].get('result') != 'REQUIRED':
        _fail('CAPACITY_REFERENCE_INVALID', '正产能消费必须保留本精确步骤正式必经证明')
    exact, kind = scope['scope'], scope['kind']
    if scope.get('_lock'):
        list(StandardCapacity.objects.select_for_update().filter(company_id=exact['companyId'], product_type_id=kind.pk))
    capacities = StandardCapacity.objects.select_related('operation', 'work_center__workshop',
        'product_type__product_category', 'product_type__manufacturing_process_type', 'uom').filter(
        pk=value['standardCapacityId'], company_id=exact['companyId'], product_type_id=kind.pk,
        operation_id=exact['operationId'])
    if scope.get('_lock'):
        capacities = capacities.select_for_update()
    capacity = capacities.first()
    step, plan, output, item = (scope['native'][key] for key in ('step', 'plan', 'output', 'item'))
    from .routing_planning_readiness_service import RoutingPlanningReadinessService as Rules
    if (capacity is None or not Rules._active_on(capacity, today)
            or capacity.measurement_status != 'measured' or capacity.quantity is None or capacity.quantity <= 0
            or capacity.time_basis != 'day' or capacity.time_basis_quantity != Decimal(1) or capacity.time_unit != 'DAY'
            or capacity.uom_id != step.operation.calculation_uom_id
            or not capacity.work_center_id or not Rules._active_on(capacity.work_center, today)
            or not capacity.work_center.workshop_id or not Rules._active_on(capacity.work_center.workshop, today)
            or capacity.work_center.company_id != exact['companyId']
            or capacity.work_center.workshop.company_id != exact['companyId']
            or step.work_center_id and step.work_center_id != capacity.work_center_id
            or step.workshop_id and step.workshop_id != capacity.work_center.workshop_id
            or step.operation.work_center_id and step.operation.work_center_id != capacity.work_center_id):
        _fail('CAPACITY_REFERENCE_INVALID', '正日产能的公司、产品类型、工序、资源、单位、日期或DAY基准不一致')
    cache = native._source_read_cache(user, scope.get('_read_cache'))
    scope['_read_cache'] = cache
    usage = capacity_usage_scope_proof(capacity, read_cache=cache)
    if usage is None:
        _fail('CAPACITY_REFERENCE_INVALID', '本消费引用必须保留原正式工程产能用途证明')
    source_rules = daily.capacity_source_rules(kind, company_id=exact['companyId'], on_date=today, read_cache=cache)
    manifest = source_rules.get('manifest', {})
    expected_source = {'referenceType': 'FORMAL_CAPACITY_SOURCE_RULES_HEADER', 'productTypeId': kind.pk,
        'sourceSha256': manifest.get('sourceSha256'), 'effectiveDate': manifest.get('effectiveDate')}
    if source_rules.get('status') != 'VALID' or value['unifiedTimeSource'] != expected_source:
        _fail('CAPACITY_REFERENCE_INVALID', '统一时间来源必须匹配当前正式DB合同，不能引用文档缓存或别的类型')
    times = {}
    for key in ('preparationDays', 'transferDays'):
        times[key] = daily._decimal(manifest.get(key), key)
        if times[key] < 0:
            _fail('CAPACITY_REFERENCE_INVALID', '统一时间必须为明确有限非负DAY值，未知不能补0')
    for key, field in (('preparationDays', 'preparation_days'), ('transferDays', 'transfer_days')):
        if any(getattr(row, field) is not None and Decimal(str(getattr(row, field))) != times[key]
                for row in (step, capacity)):
            _fail('CAPACITY_REFERENCE_INVALID', '已保存步骤或产能DAY值与统一时间标准冲突，禁止覆盖')
    remembered = cache.get(scope.get('_consumption_load_key')) if not scope.get('_lock') else None
    if remembered is None:
        demand = native.process_demand_for_plan(plan, output, item,
            {'stepId': step.pk, 'operationId': step.operation_id}, company_id=exact['companyId'], user=user, read_cache=cache)
        coverage = None
    else:
        demand, coverage = deepcopy(remembered)
    if demand is None or demand.get('uomId') != capacity.uom_id:
        _fail('CAPACITY_REFERENCE_INVALID', '消费关系必须承接本步骤原生已保存负荷及相同正式单位')
    coverage = coverage if coverage is not None else daily._validated_demand_object_coverage(plan, output, item,
        {'stepId': step.pk, 'operationId': step.operation_id}, demand, company_id=exact['companyId'], read_cache=cache)
    if (coverage['designItemIds'] != {row['designItemId'] for row in scope['coverage']}
            or coverage['baselineItemIds'] != {row['baselineItemId'] for row in scope['coverage']}):
        _fail('CAPACITY_REFERENCE_INVALID', '已保存负荷必须完整覆盖本步骤固定对象，不能用引用缩小范围')
    allocation_ids = demand.get('allocationIds') or [demand['allocationId']]
    rows = list(ProductionPlanOperationRequirementAllocation.objects.filter(pk__in=allocation_ids,
        company_id=exact['companyId'], production_plan_id=plan.pk, routing_step_id=step.pk)
        .select_related('operation_requirement').order_by('pk'))
    if ({row.pk for row in rows} != set(allocation_ids)
            or any(row.operation_requirement.standard_capacity_id != capacity.pk
                or row.operation_requirement.work_center_id != capacity.work_center_id
                or row.uom_id != capacity.uom_id for row in rows)):
        _fail('CAPACITY_REFERENCE_INVALID', '正式消费只能引用已保存需求实际冻结的产能、工作中心和单位')
    cap_fact = daily.capacity_fact(capacity, today)
    if cap_fact.get('capacitySemantics', {}).get('valid') is not True:
        _fail('CAPACITY_REFERENCE_INVALID', '正式正日产能当前语义证明无效')
    header_proof = {'sourceRulesFact': source_rules['fact'],
        'capacityRecords': [{'id': row.pk, 'hash': native._proof_record_hash(row)}
            for row in sorted(source_rules['capacityRows'], key=lambda row: row.pk)]}
    time_hash = _hash(header_proof)
    proof = {'exactScope': deepcopy(exact),
        'capacityReference': {'standardCapacityId': capacity.pk,
            'capacityRecordHash': native._proof_record_hash(capacity), 'proofHash': _hash(usage)},
        'selectedCapacityFact': cap_fact, 'capacityUsageScopeProof': usage,
        'savedLoadReference': {'allocationIds': sorted(allocation_ids),
            'operationRequirementIds': sorted(row.operation_requirement_id for row in rows),
            'quantity': str(demand['quantity']), 'uomId': demand['uomId'],
            'objectCoverageProofHash': _hash(sorted(coverage['proofs'], key=lambda row: row['allocationId'])),
            'allocationRecordsHash': _hash([native._proof_record_hash(row) for row in rows])},
        'validatedObjectCoverage': {key: sorted(coverage[key]) for key in
            ('designItemIds', 'baselineItemIds', 'inputFactIds')},
        'sharedTimeSource': {'sourceId': kind.pk, 'sourceSha256': manifest['sourceSha256'],
            'effectiveDate': manifest['effectiveDate'], 'referenceHash': time_hash, 'proofHash': time_hash,
            **{key: str(number) for key, number in times.items()}, 'timeUnit': 'DAY',
            'countPolicy': 'ONCE_PER_STEP', 'sourceRulesFact': deepcopy(source_rules['fact'])}}
    result = {key: deepcopy(item) for key, item in value.items() if key != 'proof'}
    result['proof'] = proof
    if canonical and value != result:
        _fail('CAPACITY_REFERENCE_CHANGED', '已保存产能、负荷、对象或统一时间证明已变化，读取不得补签')
    return result


def _reference_history_check(exact_scope, row):
    ledgers = MasterDataWriteRequest.objects.filter(organization_id=exact_scope['companyId'], action_code=ACTION,
        status=MasterDataWriteRequest.Status.COMMITTED,
        entity_type=ENTITY, audit_metadata__payload__exactScope__productionPlanId=exact_scope['productionPlanId'],
        audit_metadata__payload__exactScope__routingStepId=exact_scope['routingStepId'])
    existed = any(_has_capacity_reference(value.get('payload', {}).get('businessBasis'))
        for value in ledgers.values_list('audit_metadata', flat=True) if isinstance(value, dict))
    if existed and (row is None or not _has_capacity_reference(row.business_basis)
            or row.company_id != exact_scope['companyId']):
        _fail('HISTORY_INVALID', '已提交的产能消费引用缺行、跨范围或协议标记被删除')


def _reference_readback(scope, row, proof):
    reference = scope.get('_capacity_reference')
    if reference is None:
        _fail('CAPACITY_REFERENCE_INVALID', '当前引用未通过本次原生验证')
    audits, _ = proof
    return {'contractVersion': CAPACITY_CONSUMPTION_CONTRACT, 'consumer': reference['consumer'],
        'formalConsumptionValidated': True,
        'recordId': row.pk, 'revision': row.revision, 'auditIds': [audit.pk for audit in audits],
        'referenceHash': _hash(reference), 'effectiveFrom': reference['effectiveFrom'],
        'effectiveTo': reference['effectiveTo'], 'grantsRulePublication': False,
        'grantsRequirementGeneration': False, 'grantsAllocation': False, 'grantsScheduling': False,
        **deepcopy(reference['proof'])}


@transaction.atomic
def resolve_capacity_consumption_reference(*, user, exact_scope, on_date=None, read_cache=None):
    _authorize(user, VIEW)
    from planning.models import ProductionPlan
    from .models import RoutingStep
    if (not isinstance(exact_scope, dict) or set(exact_scope) != SCOPE_KEYS
            or any(not _positive(exact_scope.get(key)) for key in SCOPE_KEYS)
            or exact_scope['companyId'] != user.company_id
            or not ProductionPlan.objects.filter(pk=exact_scope['productionPlanId'],
                planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id).exists()
            or not RoutingStep.objects.filter(pk=exact_scope['routingStepId'],
                routing_version_id=exact_scope['routingVersionId'], operation_id=exact_scope['operationId'],
                operation__company_id=user.company_id).exists()):
        _fail('SCOPE_INVALID', '无日期消费引用必须绑定本公司完整正式范围')
    rows = list(OperationInputPreparationDraft.objects.select_related('creation_write_request__source_identity')
        .filter(production_plan_id=exact_scope['productionPlanId'], routing_step_id=exact_scope['routingStepId'])[:2])
    if len(rows) > 1:
        _fail('SCOPE_CONFLICT', '同一计划步骤存在多个准备上下文')
    row = rows[0] if rows else None
    _reference_history_check(exact_scope, row)
    if row is None or not _has_capacity_reference(row.business_basis):
        return None
    scope = _scope(user, exact_scope, read_cache=read_cache, consumer='ALLOCATED_LOAD_NO_DATE')
    scope['_reference_on_date'] = on_date
    return _reference_readback(scope, row, _verify(row, scope))


def _capacity_principles():
    from .daily_capacity_service import CAPACITY_TRISTATE_PRINCIPLES
    return deepcopy(CAPACITY_TRISTATE_PRINCIPLES)


def _validate_capacity_ruling(entry, scope):
    ruling = entry['capacityRuling']
    required = {'contractVersion', 'rulingType', 'supersedesRevision', 'reason',
        'sourceProof', 'principles', 'userDecision'}
    if (not isinstance(ruling, dict) or set(ruling) != required
            or ruling.get('contractVersion') != CAPACITY_RULING_CONTRACT
            or ruling.get('rulingType') not in {'REVOKE_UNMEASURED', 'CONFIRM_ZERO'}
            or not _positive(ruling.get('supersedesRevision'))
            or not isinstance(ruling.get('reason'), str) or not ruling['reason'].strip()
            or ruling.get('principles') != _capacity_principles()):
        _fail('CAPACITY_RULING_INVALID', '产能纠正必须声明版本、被替代修订、原因及统一三态原则')
    source = ruling.get('sourceProof')
    source_keys = {'contractVersion', 'sourcePath', 'sourceSha256', 'sheetName', 'sourceCell',
        'productTypeCode', 'processName', 'rawValue', 'rawValueKind', 'currentApplicability',
        'evidenceReference', 'evidenceSha256'}
    if (not isinstance(source, dict) or set(source) != source_keys
            or source.get('contractVersion') != CAPACITY_SOURCE_PROOF_CONTRACT
            or any(not isinstance(source.get(key), str) or not source[key].strip() for key in
                ('sourcePath', 'sheetName', 'sourceCell', 'evidenceReference'))
            or not _token(source.get('sourceSha256')) or not _token(source.get('evidenceSha256'))
            or re.fullmatch(r'[A-Z]+[1-9][0-9]*', source['sourceCell']) is None
            or source.get('productTypeCode') != scope['kind'].code
            or source.get('processName') != scope['native']['step'].operation.name
            or source.get('currentApplicability') != 'REQUIRED'
            or scope['applicability'].get('result') != 'REQUIRED'
            or not ((source.get('rawValueKind') == 'BLANK' and source.get('rawValue') is None)
                or (source.get('rawValueKind') == 'NUMERIC_ZERO' and source.get('rawValue') == '0'))):
        _fail('CAPACITY_RULING_INVALID', '产能纠正必须保留原矩阵空白或0的真实出处，并绑定当前产品工序及必经证明')
    decision = ruling.get('userDecision')
    if ruling['rulingType'] == 'CONFIRM_ZERO':
        expected = {'confirmedZero': True, 'reference': entry['reference'],
            'referenceSha256': entry['referenceSha256'], 'exactStatement': entry['exactStatement']}
        if decision != expected:
            _fail('CAPACITY_RULING_INVALID', '按0语义承接必须绑定本精确范围的明确人工答复，不能从原空白或缺记录推导')
    elif decision is not None:
        _fail('CAPACITY_RULING_INVALID', '尚未确认0的纠正不得伪造人工0裁决')


def _validate_ruling_append(previous_basis, new_basis, supersedes_revision):
    prior = previous_basis['entries'] if previous_basis else []
    if new_basis['entries'][:len(prior)] != prior:
        _fail('BASIS_IMMUTABLE', '原答复及已经保存的产能裁决不能覆盖、删除或改写')
    appended = [entry['capacityRuling'] for entry in new_basis['entries'][len(prior):]
        if 'capacityRuling' in entry]
    if len(appended) > 1 or any(item['supersedesRevision'] != supersedes_revision for item in appended):
        _fail('CAPACITY_RULING_REVISION_CONFLICT', '每次修订只能追加一个绑定当前修订号的产能纠正')
    if appended and not _positive(supersedes_revision):
        _fail('CAPACITY_RULING_REVISION_CONFLICT', '产能纠正必须追加到既有准备记录，不能新建替代记录')


def build_capacity_ruling_basis(*, current_preparation, reference, reference_sha256,
        exact_statement, reason, source_proof, confirmed_zero=True):
    """Pure payload builder. Actual authorization/provenance is checked on save."""
    if (not isinstance(current_preparation, dict)
            or current_preparation.get('recordStatus') != 'RECORDED'
            or not _positive(current_preparation.get('recordId'))
            or not _positive(current_preparation.get('revision'))
            or type(confirmed_zero) is not bool):
        _fail('CAPACITY_RULING_INVALID', '纠正载荷必须从当前已读取的同一准备记录构造')
    basis = deepcopy(current_preparation['businessBasis'])
    entry = {'reference': reference, 'referenceSha256': reference_sha256,
        'exactStatement': exact_statement, 'scope': deepcopy(current_preparation['exactScope']),
        'objectCoverage': deepcopy(current_preparation['objectCoverage'])}
    entry['capacityRuling'] = {'contractVersion': CAPACITY_RULING_CONTRACT,
        'rulingType': 'CONFIRM_ZERO' if confirmed_zero else 'REVOKE_UNMEASURED',
        'supersedesRevision': current_preparation['revision'], 'reason': reason,
        'sourceProof': deepcopy(source_proof), 'principles': _capacity_principles(),
        'userDecision': {'confirmedZero': True, 'reference': reference,
            'referenceSha256': reference_sha256, 'exactStatement': exact_statement} if confirmed_zero else None}
    basis['entries'].append(entry)
    return basis


def _selection(scope, value, producer_rule_id, manufacturing_mode_id, work_center_id, standard_capacity_id):
    if scope.get('conditional') or scope.get('quantity_policy'):
        if any(item is not None for item in (value, producer_rule_id, manufacturing_mode_id,
                work_center_id, standard_capacity_id)):
            _fail('CONDITIONAL_INVALID', '待触发准备不得预置未知数量、单位、来源或定量资源绑定')
        return None, None
    from . import operation_requirement_service as native
    from .operation_workload_source_service import _numeric_producer, _formal_trace_options, _rules
    company_id = scope['scope']['companyId']
    operation = scope['native']['step'].operation
    if value is not None and (not isinstance(value, dict) or set(value) - {
            'traceEquals', 'quantityBasis', 'basisQuantity', 'basisUomId', 'expression'}):
        _fail('SELECTION_INVALID', '草稿只接受既有来源条件、数量口径、基数、单位和单来源表达式')
    selection = deepcopy(value)
    for label, pk in (('producerRuleId', producer_rule_id), ('manufacturingModeId', manufacturing_mode_id),
                      ('workCenterId', work_center_id), ('standardCapacityId', standard_capacity_id)):
        if pk is not None and not _positive(pk):
            _fail('SELECTION_INVALID', '已选目录必须使用正式正整数FK', field=label)
    producer = None
    producer_info = None
    if producer_rule_id is not None:
        producer = EngineeringRuleDefinition.objects.filter(pk=producer_rule_id,
            company_id=company_id, status='released').first()
        if not native._active(producer):
            _fail('SELECTION_INVALID', '来源必须为同公司当前有效的正式发布规则')
        try:
            producer_info = _numeric_producer(producer,
                list(UnitOfMeasure.objects.filter(company_id=company_id, is_active=True)))
        except Exception as error:
            if not hasattr(error, 'code'):
                raise
            _fail('SELECTION_INVALID', '来源生产者的正式数值及单位合同无效')
        if not producer_info or producer_info['uomId'] != operation.calculation_uom_id:
            _fail('SELECTION_INVALID', '来源必须为数值型DERIVED_FACT且使用相容的正式工序单位')
    mode = None
    if manufacturing_mode_id is not None:
        mode = ManufacturingMode.objects.filter(pk=manufacturing_mode_id,
            company_id=company_id, status='released').first()
        if not native._active(mode) or mode.uom_id != operation.calculation_uom_id:
            _fail('SELECTION_INVALID', '模式必须为同公司有效发布版本且单位相容')
    center = None
    if work_center_id is not None:
        center = WorkCenter.objects.select_related('workshop').filter(pk=work_center_id,
            company_id=company_id).first()
        step = scope['native']['step']
        if (not native._active(center) or not center.workshop_id
                or not native._active(center.workshop) or center.workshop.company_id != company_id
                or (step.work_center_id and center.pk != step.work_center_id)
                or (step.workshop_id and center.workshop_id != step.workshop_id)
                or (operation.workshop_id and center.workshop_id != operation.workshop_id)
                or (operation.work_center_id and center.pk != operation.work_center_id
                    and not WorkCenterOperationCapability.objects.filter(operation=operation,
                        work_center=center, is_active=True).exists())):
            _fail('SELECTION_INVALID', '资源必须为当前步骤同公司合法工作中心及车间')
    if standard_capacity_id is not None:
        capacity = StandardCapacity.objects.filter(pk=standard_capacity_id, company_id=company_id,
            operation_id=operation.pk, product_type_id=scope['kind'].pk).first()
        if not native._active(capacity) or (center and capacity.work_center_id != center.pk):
            _fail('SELECTION_INVALID', '参考产能必须指向当前范围的正式目录')
        _fail('UNMEASURED_CAPACITY_CONFLICT', '准备裁决不代替正式标准产能引用；原产能维护与发布门禁继续独立校验')
    if selection is not None:
        trace = selection.get('traceEquals')
        if trace is not None:
            if not isinstance(trace, dict) or (trace and not producer_info):
                _fail('SELECTION_INVALID', '正式来源条件必须依附已选生产者')
            if trace:
                options = _formal_trace_options(_rules(company_id), producer_info,
                    product_type_id=scope['kind'].pk)
                if not any(row['traceEquals'] == trace for row in options):
                    _fail('SELECTION_INVALID', '来源条件不属于当前正式目录与产品类型')
        basis = selection.get('quantityBasis')
        if basis is not None and basis not in native.KNOWN_BASES:
            _fail('SELECTION_INVALID', '数量口径必须引用既有正式合同')
        number = selection.get('basisQuantity')
        if number is not None:
            try:
                number = Decimal(str(number))
            except (InvalidOperation, TypeError, ValueError):
                _fail('SELECTION_INVALID', '基准数量必须为有限正数')
            if not number.is_finite() or number <= 0 or basis != 'PER_BASIS_QUANTITY':
                _fail('SELECTION_INVALID', '基准数量只能属于正式每基数口径，且必须为正数')
            selection['basisQuantity'] = format(number, 'f')
        unit_id = selection.get('basisUomId')
        if unit_id is not None:
            if (not _positive(unit_id) or basis != 'PER_BASIS_QUANTITY'
                    or unit_id != scope['native']['item'].uom_id
                    or not UnitOfMeasure.objects.filter(pk=unit_id, company_id=company_id, is_active=True).exists()):
                _fail('SELECTION_INVALID', '基准单位必须为同公司有效正式单位及相应数量口径')
        expression = selection.get('expression')
        if expression is not None:
            try:
                _parse_expression(expression, {'source_quantity'})
            except Exception as error:
                if not hasattr(error, 'code'):
                    raise
                _fail('SELECTION_INVALID', '表达式只允许单一source_quantity别名的安全算术')
        _hash(selection)
    return selection, producer_info


def _content(row):
    # Bind selected immutable versions/content as well as formal FK identity.
    # Use concrete fields only: WorkCenter's regular UI snapshot also includes
    # dynamic capacity summaries, which are outside this preparation record.
    references = {}
    for name in ('producer_rule', 'manufacturing_mode', 'work_center', 'standard_capacity'):
        if getattr(row, name + '_id') is None:
            references[name] = None
            continue
        selected = getattr(row, name)
        snapshot = {}
        for field in selected._meta.concrete_fields:
            value = getattr(selected, field.attname)
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            elif isinstance(value, Decimal):
                value = str(value)
            snapshot[field.attname] = value
        references[name] = _hash(snapshot)
    return {'contractVersion': CONTRACT, 'contextHash': row.context_hash, 'objectsHash': row.objects_hash,
        'objectCoverage': row.object_coverage, 'status': row.status,
        'inputStandardStatus': row.input_standard_status,
        'capacityMeasurementStatus': row.capacity_measurement_status,
        'producerRuleId': row.producer_rule_id, 'manufacturingModeId': row.manufacturing_mode_id,
        'workCenterId': row.work_center_id, 'standardCapacityId': row.standard_capacity_id,
        'draftSelection': row.draft_selection, 'businessBasis': row.business_basis, 'revision': row.revision,
        'selectedReferenceHashes': references}


def validate_model_record(row):
    """Guard immutable identity/evidence even inside the authorized service."""
    if (row.status != 'draft' or row.input_standard_status != 'PENDING_CONFIRMATION'
            or row.capacity_measurement_status != 'UNMEASURED' or row.standard_capacity_id is not None
            or type(row.revision) is not int or row.revision < 1
            or any(not _token(getattr(row, name)) for name in ('context_hash', 'objects_hash', 'content_hash'))
            or _hash(row.object_coverage) != row.objects_hash or _hash(_content(row)) != row.content_hash):
        _fail('PROTECTED_RECORD', '准备状态、内容Hash或未测数量合同不完整')
    if not row._state.adding:
        old = OperationInputPreparationDraft.objects.get(pk=row.pk)
        immutable = tuple(SCOPE_FIELDS.values()) + ('object_coverage', 'objects_hash', 'context_hash',
            'status', 'input_standard_status', 'capacity_measurement_status', 'creation_write_request_id', 'created_by_id')
        if any(getattr(row, key) != getattr(old, key) for key in immutable):
            _fail('PROTECTED_RECORD', '准备记录正式范围、初始状态和原生身份不可改写')
        prior = old.business_basis.get('entries', [])
        if row.business_basis.get('entries', [])[:len(prior)] != prior:
            _fail('BASIS_IMMUTABLE', '原答复及其Hash不得覆盖、修改或删除')
        from .conditional_execution_preparation import is_conditional_basis
        if (is_conditional_basis(old.business_basis) and _hash(old.business_basis['conditionalExecution'])
                != _hash(row.business_basis.get('conditionalExecution'))):
            _fail('BASIS_IMMUTABLE', '已保存待触发政策不可替换，只能保留政策及原文后追加依据')
        from .conditional_execution_preparation import is_quantity_basis
        if (is_quantity_basis(old.business_basis) and _hash(old.business_basis['quantityPolicy'])
                != _hash(row.business_basis.get('quantityPolicy'))):
            _fail('BASIS_IMMUTABLE', '已保存不单独计量政策不可替换，只能追加依据')
        if row.revision != old.revision + 1:
            _fail('REVISION_CONFLICT', '草稿更新必须递增且校验当前修订号')


def _verify(row, scope):
    """Independent persisted proof: row, identity, all ledgers, audits and BST."""
    from .operation_requirement_service import _requirement_read_cache, _read_once, _today
    if row.context_hash != scope['context_hash']:
        from .historical_source_schema import preparation_v1_context
        historical = preparation_v1_context(row, scope)
        if historical is not None:
            # Only this verifier sees the exact prior schema. No row, audit,
            # hash or caller's current scope is modified; all remaining native
            # ledger, authorization, revision and content proofs run below.
            scope = {**scope, 'context':historical, 'context_hash':_hash(historical)}
    reader = scope.get('_reader')
    cache = (None if scope.get('_lock') else
        _requirement_read_cache(scope.get('_read_cache'), row.company_id))
    if cache is not None and (reader is None or cache.user_id != reader.pk
            or reader.company_id != row.company_id):
        cache = None

    def raw(key, loader):
        # Share exact native reads, never an approval. Every invocation below
        # still proves every revision, original actor, ledger and frozen state.
        return _read_once(cache, ('preparation_verify_raw', row.company_id,
            cache.user_id if cache is not None else None, _today(), *key), loader)
    if (any(getattr(row, field) != scope['scope'][key] for key, field in SCOPE_FIELDS.items())
            or row.context_hash != scope['context_hash'] or row.objects_hash != scope['objects_hash']
            or row.object_coverage != scope['coverage'] or row.content_hash != _hash(_content(row))):
        _fail('CONTEXT_DRIFT', '已保存准备记录与当前完整正式范围或内容Hash不一致')
    _basis(row.business_basis, scope)
    _selection(scope, row.draft_selection, row.producer_rule_id, row.manufacturing_mode_id,
        row.work_center_id, row.standard_capacity_id)
    creation = row.creation_write_request
    identity = creation.source_identity
    if (creation.status != 'COMMITTED' or creation.entity_type != ENTITY or creation.action_code != ACTION
            or creation.organization_id != row.company_id or creation.target_entity_id != str(row.pk)
            or identity.organization_id != row.company_id or identity.source_system != 'PCE_SYSTEM'
            or identity.source_type != 'OPERATION_INPUT_PREPARATION'
            or identity.source_object_type != OBJECT_TYPE or identity.target_entity_type != ENTITY
            or identity.external_id != 'OperationInputPreparation:' + row.context_hash
            or identity.target_entity_id != str(row.pk) or identity.mapping_status != 'MATCH'
            or identity.source_fingerprint != _hash(scope['context'])
            or identity.audit_metadata != {'contractVersion': CONTRACT, 'context': scope['context']}):
        _fail('HISTORY_INVALID', '准备记录缺少已提交原生请求及唯一来源身份')
    audits = raw(('audits', ACTION, OBJECT_TYPE, row.pk, 'pk'), lambda:
        list(OrganizationOperatingAuditRecord.objects.filter(organization_id=row.company_id,
        action_code=ACTION, target_type=OBJECT_TYPE, target_id=row.pk).order_by('pk')))
    if len(audits) != row.revision:
        _fail('HISTORY_INVALID', '每项草稿修订必须具有唯一真实审计')
    previous = {}
    for revision, audit in enumerate(audits, 1):
        envelope = audit.after_snapshot
        state = envelope.get('state') if isinstance(envelope, dict) else None
        imports = envelope.get('importContext') if isinstance(envelope, dict) else None
        chain = envelope.get('executionChain') if isinstance(envelope, dict) else None
        authorization = envelope.get('authorization') if isinstance(envelope, dict) else None
        if (scope.get('conditional') or scope.get('quantity_policy')
                or _has_capacity_reference(state.get('business_basis') if isinstance(state, dict) else None)):
            from .routing_version_successor_service import ROUTING_PERMISSION
            routing = authorization.get('conditionalRoutingAuthorization') if isinstance(authorization, dict) else None
            if (not isinstance(routing, dict) or routing.get('allowed') is not True
                    or routing.get('actionCode') != ROUTING_PERMISSION
                    or str(routing.get('organizationId')) != str(row.company_id)):
                _fail('HISTORY_INVALID', '条件准备缺少原生路线维护权限证明')
        actor = raw(('actor', audit.actor_id, 'id', 'company_id', 'username'), lambda:
            User.objects.filter(pk=audit.actor_id).values('id', 'company_id', 'username').first())
        if (not isinstance(state, dict) or state.get('revision') != revision
                or not isinstance(imports, dict) or imports.get('contractVersion') != CONTRACT
                or imports.get('contextHash') != row.context_hash
                or not actor or actor['company_id'] != row.company_id
                or not isinstance(chain, dict) or chain.get('account') != actor['username']
                or any(not _positive(chain.get(key)) for key in ('employeeId', 'positionId', 'responsibilityId'))
                or not isinstance(authorization, dict) or authorization.get('allowed') is not True
                or authorization.get('actionCode') != (CREATE if revision == 1 else UPDATE)
                or str(authorization.get('organizationId')) != str(row.company_id)
                or not isinstance(authorization.get('capacityAuthorization'), dict)
                or authorization['capacityAuthorization'].get('allowed') is not True
                or authorization['capacityAuthorization'].get('actionCode') != CAPACITY
                or envelope.get('factSource') != 'server'
                or audit.before_snapshot != {**envelope, 'state': previous}):
            _fail('HISTORY_INVALID', '准备审计的原生状态、双权限或实名办理链不完整')
        request_id = imports.get('writeRequestId')
        ledger = raw(('ledger', type(request_id).__name__, repr(request_id), 'source_identity'), lambda:
            MasterDataWriteRequest.objects.select_related('source_identity').filter(pk=request_id).first())
        metadata = ledger.audit_metadata if ledger else None
        payload = metadata.get('payload') if isinstance(metadata, dict) else None
        if (not ledger or ledger.status != 'COMMITTED' or ledger.action_code != ACTION
                or ledger.entity_type != ENTITY or ledger.organization_id != row.company_id
                or ledger.source_identity_id != identity.pk or ledger.target_entity_id != str(row.pk)
                or not isinstance(payload, dict) or ledger.request_hash != _hash(payload)
                or payload.get('operatorId') != audit.actor_id
                or payload.get('businessBasis') != state.get('business_basis')
                or payload.get('contextHash') != row.context_hash
                or imports.get('requestHash') != ledger.request_hash
                or imports.get('basisHash') != _hash(state.get('business_basis'))
                or ledger.result.get('recordId') != row.pk or ledger.result.get('revision') != revision
                or ledger.result.get('auditId') != audit.pk
                or (revision == 1 and (ledger.pk != creation.pk or audit.actor_id != row.created_by_id))):
            _fail('HISTORY_INVALID', '准备修订未绑定同一已提交账本、原答复及原生审计')
        if (state.get('context_hash') != row.context_hash
                or any(state.get(field) != getattr(row, field) for field in SCOPE_FIELDS.values())
                or state.get('object_coverage') != row.object_coverage
                or state.get('objects_hash') != row.objects_hash
                or state.get('status') != 'draft' or state.get('input_standard_status') != 'PENDING_CONFIRMATION'
                or state.get('capacity_measurement_status') != 'UNMEASURED'):
            _fail('HISTORY_INVALID', '准备修订审计不得扩大范围或提升准备状态')
        if (scope.get('conditional') and _hash(state.get('business_basis', {}).get('conditionalExecution'))
                != _hash(row.business_basis['conditionalExecution'])):
            _fail('HISTORY_INVALID', '条件政策的历史修订不可被替换')
        if (scope.get('quantity_policy') and _hash(state.get('business_basis', {}).get('quantityPolicy'))
                != _hash(row.business_basis['quantityPolicy'])):
            _fail('HISTORY_INVALID', '数量政策的历史修订不可被替换')
        if previous:
            prior = previous['business_basis']['entries']
            if state['business_basis']['entries'][:len(prior)] != prior:
                _fail('BASIS_IMMUTABLE', '历史原答复链不得被替换或删除')
        _validate_ruling_append(previous.get('business_basis') if previous else None,
            state['business_basis'], revision - 1)
        previous = state
    if previous != _snapshot(row):
        _fail('HISTORY_INVALID', '准备当前记录与最后已提交审计快照不一致')
    transitions = raw(('transitions', OBJECT_TYPE, row.pk, 'version', 'pk'), lambda:
        list(BusinessStateTransition.objects.filter(object_type=OBJECT_TYPE,
        object_id=row.pk).order_by('version', 'pk')))
    if (len(transitions) != 1 or transitions[0].source_state != '' or transitions[0].target_state != 'draft'
            or transitions[0].version != 1 or transitions[0].operator_id != row.created_by_id
            or transitions[0].action_code != ACTION
            or transitions[0].audit_reference != f'OrganizationOperatingAuditRecord:{audits[0].pk}'
            or transitions[0].reason != audits[0].reason):
        _fail('HISTORY_INVALID', '准备草稿必须且只拥有一次引用真实审计的统一初始状态')
    return audits, transitions


def _capacity_current(scope, row=None):
    if row is not None and _has_capacity_reference(row.business_basis):
        reference = scope.get('_capacity_reference')
        if reference is None:
            _fail('CAPACITY_REFERENCE_INVALID', '正式消费引用尚未通过本次原生读取验证')
        fact = reference['proof']['selectedCapacityFact']
        return {'statusCode': 'POSITIVE_CAPACITY_REFERENCE_RECORDED',
            'statusLabel': '已保存正产能无日期引用',
            'capacityMeasurementStatus': 'measured', 'capacityBusinessValue': fact['quantity'],
            'capacityQuantity': fact['quantity'], 'legacyCapacityMeasurementStatus': row.capacity_measurement_status,
            'capacityMeasurementStatusLabel': '引用现有正式正日产能；原EOR及用途证明保持',
            'capacityResolution': {'valid': True, 'code': 'FORMAL_POSITIVE_CAPACITY_REFERENCE',
                'formalStandardCapacityPresent': True, 'originalConclusionRevoked': False,
                'statusLabel': '已保存正产能及统一时间的本步骤无日期消费引用'},
            'capacitySemantics': deepcopy(fact['capacitySemantics'])}
    if scope.get('quantity_policy'):
        from .conditional_execution_preparation import quantity_capacity_readback
        return quantity_capacity_readback(scope)
    if scope.get('conditional'):
        from .conditional_execution_preparation import capacity_readback
        return capacity_readback(scope, row)
    """Legacy UNMEASURED storage is historical; current truth has three meanings."""
    from .daily_capacity_service import capacity_tristate_semantics
    entries = row.business_basis['entries'] if row else []
    rulings = [(index, entry['capacityRuling']) for index, entry in enumerate(entries)
        if 'capacityRuling' in entry]
    current_index, ruling = rulings[-1] if rulings else (None, None)
    zero_ruling = bool(ruling and ruling['rulingType'] == 'CONFIRM_ZERO')
    formal_rows = StandardCapacity.objects.filter(company_id=scope['scope']['companyId'],
        operation_id=scope['scope']['operationId'], product_type_id=scope['scope']['productTypeId']) if row else None
    formal_present = formal_rows.exists() if row else None
    from .operation_requirement_service import _active
    positive_conflict = bool(zero_ruling and any(_active(capacity) for capacity in
        formal_rows.filter(measurement_status='measured', quantity__gt=0)))
    confirmed = zero_ruling and not positive_conflict
    conflict = ('CAPACITY_SOURCE_RULING_CONFLICT' if positive_conflict else
        None if confirmed else 'CAPACITY_SOURCE_OBJECT_CONFLICT' if ruling else 'CAPACITY_RULING_NOT_RECORDED')
    semantics = capacity_tristate_semantics(source_value='0' if confirmed else None,
        source_scope_proven=confirmed, measurement_status='zero_capacity' if confirmed else None,
        scope=scope['scope'], record_present=formal_present,
        quantitative_occupancy_allowed=False, conflict_code=conflict)
    label = ('已存0裁决与当前正数标准产能冲突，须核对' if positive_conflict else
        '经过但无法准确核算，不计定量产能占用' if confirmed else
        '原产能结论已撤销；来源空白与必经裁决冲突，尚未确认' if ruling else
        '历史未测表述不作当前产能裁决，待三态核对' if row else '尚未记录')
    resolution = {'valid': confirmed, 'code': 'CONFIRMED_ZERO' if confirmed else
        'UNRESOLVED_CONFLICT' if ruling else 'REQUIRES_REASSESSMENT' if row else 'NOT_RECORDED',
        'statusLabel': label, 'originalConclusionRevoked': bool(ruling),
        'formalStandardCapacityPresent': formal_present,
        'rulingRevision': ruling['supersedesRevision'] + 1 if ruling else None,
        'sourceProof': deepcopy(ruling['sourceProof']) if ruling else None}
    presentation = []
    for index, entry in enumerate(entries):
        presentation.append({'entryIndex': index,
            'statusLabel': '当前产能纠正依据' if index == current_index else
                '历史依据：原产能表述仅供追溯，投入标准待确认仍保留',
            'exactStatement': entry['exactStatement'], 'reference': entry['reference'],
            'referenceSha256': entry['referenceSha256']})
    return {'capacityMeasurementStatus': 'zero_capacity' if confirmed else None,
        'capacityMeasurementStatusLabel': label, 'capacityBusinessValue': 0 if confirmed else None,
        'rulingBusinessValue': 0 if zero_ruling else None,
        'effectiveCapacityState': 'zero_capacity' if confirmed else None,
        'legacyCapacityMeasurementStatus': row.capacity_measurement_status if row else None,
        'capacityResolution': resolution, 'capacitySemantics': semantics,
        'capacityTristatePrinciples': _capacity_principles(),
        'businessBasisPresentation': presentation,
        'statusLabel': '准备记录已纠正，原产能结论已撤销' if ruling else
            '历史准备记录已保存，产能依据待三态核对' if row else '尚无正式准备记录'}


def _present(scope, row=None, proof=None):
    if row is not None and proof is not None and row.context_hash != scope['context_hash']:
        from .historical_source_schema import preparation_v1_context
        historical = preparation_v1_context(row, scope)
        if historical is None:
            _fail('CONTEXT_DRIFT', '准备展示必须沿用本次完整核实的同版本上下文')
        scope = {**scope, 'context':historical, 'context_hash':_hash(historical)}
    if scope.get('quantity_policy'):
        from .conditional_execution_preparation import present_quantity_policy
        return present_quantity_policy(scope, row, proof)
    if scope.get('conditional'):
        from .conditional_execution_preparation import present
        return present(scope, row, proof)
    remaining = [('SOURCE_STANDARD_PENDING', '确认正式投入来源、面积业务口径及来源规则'),
        ('INPUT_QUANTITY_UNKNOWN', '投入数量仍未知，待正式来源标准确认'),
        ('CAPACITY_SOURCE_REVIEW', '核对正式产能来源及资源单位；本准备裁决不创建标准产能'),
        ('FORMAL_REQUIREMENT_MISSING', '正式工序需求仍缺失，准备记录不生成需求'),
        ('SAVED_LOAD_UNKNOWN', '已保存负荷仍未知，准备记录不保存分配'),
        ('DURATION_AND_DATES_NOT_READY', '理论用时及日期条件仍不足')]
    result = {'contractVersion': CONTRACT, 'factSource': 'server', 'currentStateSource': 'server',
        'exactScope': deepcopy(scope['scope']), 'contextHash': scope['context_hash'],
        'scopeLabel': ('公司{companyId} / 订单行{salesOrderItemId} / 计划{productionPlanId} / '
            '制造输出{manufacturingOutputId} / 主核算{mainCalculationId} / 基线{baselineId} / '
            '路线版本{routingVersionId} / 步骤{routingStepId} / 工序{operationId} / '
            '产品类型{productTypeId}').format(**scope['scope']) + ' / 设计对象' +
            '、'.join(str(item['designItemId']) for item in scope['coverage']),
        'context': deepcopy(scope['context']), 'objectCoverage': deepcopy(scope['coverage']),
        'objectsHash': scope['objects_hash'], 'recordStatus': 'RECORDED' if row else 'NOT_RECORDED',
        'statusCode': 'RECORDED' if row else 'NOT_RECORDED', 'isPersisted': bool(row),
        'statusLabel': '准备记录已保存' if row else '尚无正式准备记录',
        'inputStandardStatus': 'PENDING_CONFIRMATION' if row else None,
        'inputStandardStatusLabel': '待确认' if row else '尚未记录',
        'sourceQuantity': None, 'inputQuantity': None, 'capacityQuantity': None,
        'businessBasis': deepcopy(row.business_basis) if row else None,
        'draftSelection': deepcopy(row.draft_selection) if row else None,
        'recordId': row.pk if row else None, 'revision': row.revision if row else None,
        'contentHash': row.content_hash if row else None,
        'remainingItems': [{'code': code, 'statusLabel': label} for code, label in remaining],
        'formalRulePublished': False, 'readyForGeneration': False, 'readyForAllocation': False,
        'formalRuleStatusLabel': '准备记录不代表正式规则已发布',
        'readinessStatusLabel': '投入标准、正式产能引用、需求和负荷仍未就绪；理论用时及日期条件不足',
        'readyForScheduling': False, 'businessWriteCount': 0, 'auditWriteCount': 0,
        'stateTransitionWriteCount': 0, 'supportWriteCount': 0,
        'statusTransitionHistory': [], 'statusTransitionCount': 0, 'stateMachineConsistent': True}
    if row:
        audits, transitions = proof
        result.update(createdByUserId=row.created_by_id, updatedByUserId=row.updated_by_id,
            createdAt=row.created_at.isoformat(), updatedAt=row.updated_at.isoformat(),
            auditIds=[audit.pk for audit in audits], writeRequestId=row.creation_write_request_id,
            sourceIdentityId=row.creation_write_request.source_identity_id,
            statusTransitionHistory=[{'id': item.pk, 'sourceState': item.source_state,
                'targetState': item.target_state, 'version': item.version, 'operatorId': item.operator_id,
                'auditReference': item.audit_reference, 'timestamp': item.timestamp.isoformat()}
                for item in transitions], statusTransitionCount=len(transitions))
        producer = row.producer_rule if row.producer_rule_id is not None else None
        mode = row.manufacturing_mode if row.manufacturing_mode_id is not None else None
        result.update(producerRuleId=row.producer_rule_id,
            producerRuleVersion=producer.version if producer else None,
            canonicalField=producer.specification['outputs'][0]['canonicalName'] if producer else None,
            manufacturingModeId=row.manufacturing_mode_id,
            manufacturingModeVersion=mode.version if mode else None,
            workCenterId=row.work_center_id, standardCapacityId=row.standard_capacity_id,
            selectionValidationStatusLabel='目录引用有效；业务来源、数量及单位语义仍待确认')
    result['technicalScopeLabel'] = result['scopeLabel']
    native = scope['native']
    result['scopeLabel'] = (f"工艺{native['output'].routing_version.routing.routing_code} / "
        f"路线第{native['step'].sequence}步 {native['step'].operation.name} / "
        f"生产计划{native['plan'].plan_no} / 订单{native['item'].sales_order.order_no} "
        f"第{native['item'].line_no}行 / 本次{len(scope['coverage'])}项工程对象")
    result.update(_capacity_current(scope, row))
    if row is None and scope['context'].get('consumer') == 'ALLOCATED_LOAD_NO_DATE':
        result.update(sourceQuantity=scope['_consumption_saved_quantity'],
            inputQuantity=scope['_consumption_saved_quantity'],
            inputStandardStatusLabel='原正式需求及已保存负荷已验证；消费引用尚未记录',
            readinessStatusLabel='已保存负荷已知；本步骤正产能及统一时间消费引用尚未记录',
            remainingItems=[{'code': 'CAPACITY_CONSUMPTION_REFERENCE_NOT_RECORDED',
                'statusLabel': '维护本步骤正产能及统一时间的无日期消费引用'}])
    if row is not None and _has_capacity_reference(row.business_basis):
        reference = _reference_readback(scope, row, proof)
        result.update(capacityConsumptionReference=reference, remainingItems=[],
            sourceQuantity=reference['savedLoadReference']['quantity'],
            inputQuantity=reference['savedLoadReference']['quantity'],
            inputStandardStatusLabel='沿用原正式需求及已保存负荷',
            formalRuleStatusLabel='消费引用不改原正式规则、需求或分配',
            readinessStatusLabel='正产能及统一时间引用已保存；本读取不创建日期或排程',
            businessBasisPresentation=[{'entryIndex': index, 'statusLabel': '已保存的正式消费引用依据',
                'exactStatement': entry['exactStatement'], 'reference': entry['reference'],
                'referenceSha256': entry['referenceSha256']}
                for index, entry in enumerate(row.business_basis['entries'])])
    return result


@transaction.atomic
@read_span('preparationRead')
def read_preparation(*, user, exact_scope, read_cache=None, consumer=None):
    _authorize(user, VIEW)
    from .conditional_execution_preparation import saved_for_scope, is_conditional_basis, is_plan_policy_basis
    if (not isinstance(exact_scope, dict) or set(exact_scope) != SCOPE_KEYS
            or any(not _positive(exact_scope.get(key)) for key in SCOPE_KEYS)
            or exact_scope['companyId'] != user.company_id):
        _fail('SCOPE_INVALID', '准备记录必须绑定当前公司完整正式范围')
    if consumer not in (None, 'ALLOCATED_LOAD_NO_DATE'):
        _fail('CAPACITY_REFERENCE_INVALID', '仅支持明确的已保存负荷无日期消费用途')
    conditional_row = saved_for_scope(exact_scope)
    if conditional_row is not None and is_plan_policy_basis(conditional_row.business_basis):
        if consumer is not None:
            _fail('CAPACITY_REFERENCE_INVALID', '数量或待触发政策不可转换为已保存定量消费引用')
        scope = _scope(user, exact_scope, conditional=is_conditional_basis(conditional_row.business_basis),
            policy_basis=conditional_row.business_basis, read_cache=read_cache)
        return _present(scope, conditional_row, _verify(conditional_row, scope))
    scope = _scope(user, exact_scope, read_cache=read_cache, consumer=consumer,
        policy_basis=conditional_row.business_basis if conditional_row is not None else None)
    # Plan/step locates historical evidence before comparing its complete FK
    # scope. A changed baseline/output must fail, rather than hide a saved
    # preparation as if the current request had never had a record.
    candidates = list(OperationInputPreparationDraft.objects.select_related(
        'creation_write_request__source_identity').filter(company_id=scope['scope']['companyId'],
            production_plan_id=scope['scope']['productionPlanId'],
            routing_step_id=scope['scope']['routingStepId'])[:2])
    if len(candidates) > 1:
        _fail('SCOPE_CONFLICT', '同一计划步骤存在多个准备上下文，必须明确核对，不能按时间或主键选择')
    row = candidates[0] if candidates else None
    _reference_history_check(exact_scope, row)
    return _present(scope, row, _verify(row, scope) if row else None)


@transaction.atomic
def save_preparation(*, user, exact_scope, business_basis, idempotency_key,
                     expected_context_hash, reason, draft_selection=None, expected_revision=None,
                     producer_rule_id=None, manufacturing_mode_id=None,
                     work_center_id=None, standard_capacity_id=None):
    if not isinstance(idempotency_key, str) or idempotency_key != idempotency_key.strip() or not 1 <= len(idempotency_key) <= 160:
        _fail('IDEMPOTENCY_CONFLICT', '保存必须提供不超过160字的稳定幂等键')
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 240:
        _fail('REASON_REQUIRED', '保存必须提供不超过240字的正式办理原因')
    reason = reason.strip()
    # Authorization and actor chain must precede even an exact replay.
    _authorize(user, VIEW)
    capacity_decision = _authorize(user, CAPACITY)
    from .conditional_execution_preparation import is_conditional_basis, is_plan_policy_basis
    conditional_routing = None
    if is_plan_policy_basis(business_basis) or _has_capacity_reference(business_basis):
        from .routing_version_successor_service import ROUTING_PERMISSION
        conditional_routing = _authorize(user, ROUTING_PERMISSION)
    chain = _actor(user)
    Company.objects.select_for_update().get(pk=user.company_id)
    from .conditional_execution_preparation import is_conditional_basis
    scope = _scope(user, exact_scope, lock=True, conditional=is_conditional_basis(business_basis), policy_basis=business_basis)
    if not _token(expected_context_hash) or expected_context_hash != scope['context_hash']:
        _fail('CONTEXT_DRIFT', '保存前必须以当前正式上下文Hash重新核验完整范围')
    basis = _basis(business_basis, scope, save_only=True)
    for model, pk in ((EngineeringRuleDefinition, producer_rule_id), (ManufacturingMode, manufacturing_mode_id),
                      (WorkCenter, work_center_id), (StandardCapacity, standard_capacity_id)):
        if _positive(pk):
            list(model.objects.select_for_update().filter(pk=pk, company_id=user.company_id))
    selection, producer_info = _selection(scope, draft_selection, producer_rule_id,
        manufacturing_mode_id, work_center_id, standard_capacity_id)
    if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
        _fail('REVISION_CONFLICT', '必须提供有效的期望修订号')
    payload = {'contractVersion': CONTRACT, 'exactScope': deepcopy(scope['scope']),
        'contextHash': expected_context_hash, 'expectedRevision': expected_revision,
        'operatorId': user.pk, 'businessBasis': basis, 'draftSelection': selection,
        'producerRuleId': producer_rule_id, 'manufacturingModeId': manufacturing_mode_id,
        'workCenterId': work_center_id, 'standardCapacityId': standard_capacity_id,
        'producerReference': producer_info, 'reason': reason,
        'inputStandardStatus': 'PENDING_CONFIRMATION', 'capacityMeasurementStatus': 'UNMEASURED'}
    payload_hash = _hash(payload)
    row = OperationInputPreparationDraft.objects.select_for_update().select_related(
        'creation_write_request__source_identity').filter(
            **{field: scope['scope'][key] for key, field in SCOPE_FIELDS.items()}).first()
    old_ledger = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=user.company_id, action_code=ACTION, idempotency_key=idempotency_key).first()
    if old_ledger:
        operation_permission = CREATE if old_ledger.audit_metadata.get('payload', {}).get('expectedRevision') in (None, 0) else UPDATE
        _authorize(user, operation_permission)
        if (not row or old_ledger.request_hash != payload_hash or old_ledger.status != 'COMMITTED'
                or old_ledger.target_entity_id != str(row.pk) or old_ledger.entity_type != ENTITY):
            _fail('IDEMPOTENCY_CONFLICT', '同一幂等键必须绑定同一完整载荷及已提交结果')
        proof = _verify(row, scope)
        historical = deepcopy(old_ledger.result)
        historical['resultSemantics'] = 'HISTORICAL_COMMITTED_RESULT'
        return {**_present(scope, row, proof), 'idempotentReplay': True,
            'historicalResult': historical, 'historicalResultRevision': old_ledger.result['revision'],
            'writeRequestId': old_ledger.pk, 'auditId': old_ledger.result['auditId'],
            'businessWriteCount': 0, 'auditWriteCount': 0, 'stateTransitionWriteCount': 0,
            'supportWriteCount': 0}
    permission = UPDATE if row else CREATE
    authorization = {**_authorize(user, permission), 'capacityAuthorization': capacity_decision}
    if conditional_routing is not None:
        authorization['conditionalRoutingAuthorization'] = conditional_routing
    if row:
        _verify(row, scope)
        if (scope.get('conditional') and _hash(row.business_basis['conditionalExecution'])
                != _hash(basis['conditionalExecution'])):
            _fail('BASIS_IMMUTABLE', '已保存待触发政策不可替换，只能追加依据')
        if (scope.get('quantity_policy') and _hash(row.business_basis['quantityPolicy'])
                != _hash(basis['quantityPolicy'])):
            _fail('BASIS_IMMUTABLE', '已保存不单独计量政策不可替换，只能追加依据')
        if expected_revision != row.revision:
            _fail('REVISION_CONFLICT', '草稿修订已变化，必须重新读取再保存')
        entries = row.business_basis['entries']
        if basis['entries'][:len(entries)] != entries:
            _fail('BASIS_IMMUTABLE', '原答复、出处和范围不可覆盖，只能保留后追加新答复')
        _validate_ruling_append(row.business_basis, basis, row.revision)
        identity = row.creation_write_request.source_identity
        before = _snapshot(row)
    else:
        _validate_ruling_append(None, basis, 0)
        if expected_revision not in (None, 0):
            _fail('REVISION_CONFLICT', '新范围不能提交既有草稿修订号')
        if OperationInputPreparationDraft.objects.filter(context_hash=scope['context_hash']).exists():
            _fail('CONTEXT_DRIFT', '同一上下文Hash已绑定其他正式范围')
        identity, identity_created = ExternalIdentity.objects.select_for_update().get_or_create(
            organization_id=user.company_id, source_system='PCE_SYSTEM',
            source_type='OPERATION_INPUT_PREPARATION', source_object_type=OBJECT_TYPE,
            external_id='OperationInputPreparation:' + scope['context_hash'],
            defaults={'target_entity_type': ENTITY, 'mapping_status': 'CREATE',
                'source_fingerprint': _hash(scope['context']),
                'audit_metadata': {'contractVersion': CONTRACT, 'context': scope['context']}})
        if not identity_created:
            _fail('IDEMPOTENCY_CONFLICT', '新准备记录不得复用未证明或已有目标的来源身份')
        before = {}
    ledger = MasterDataWriteRequest.objects.create(organization_id=user.company_id,
        action_code=ACTION, entity_type=ENTITY, idempotency_key=idempotency_key,
        request_hash=payload_hash, source_identity=identity,
        audit_metadata={'contractVersion': CONTRACT, 'operatorId': user.pk, 'payload': payload})
    token = _write_guard.set(True)
    try:
        values = {'producer_rule_id': producer_rule_id, 'manufacturing_mode_id': manufacturing_mode_id,
            'work_center_id': work_center_id, 'standard_capacity_id': standard_capacity_id,
            'draft_selection': selection, 'business_basis': basis, 'updated_by_id': user.pk}
        created = row is None
        if created:
            fields = {field: scope['scope'][key] for key, field in SCOPE_FIELDS.items()}
            fields.update(values, object_coverage=scope['coverage'], objects_hash=scope['objects_hash'],
                context_hash=scope['context_hash'], input_standard_status='PENDING_CONFIRMATION',
                capacity_measurement_status='UNMEASURED', revision=1,
                creation_write_request=ledger, created_by_id=user.pk)
            candidate = OperationInputPreparationDraft(status='draft', **fields)
            fields['content_hash'] = _hash(_content(candidate))
            row = create_business_object_with_initial_state(model=OperationInputPreparationDraft,
                initial_state='draft', **fields)
        else:
            for name, value in values.items():
                setattr(row, name, value)
            row.revision += 1
            row.content_hash = _hash(_content(row))
            row.save()
    finally:
        _write_guard.reset(token)
    audit = _audit(user=user, organization_id=user.company_id, action_code=ACTION, instance=row,
        before=before, after=_snapshot(row), reason=reason, authorization=authorization,
        execution_chain=chain, audit_context={'contractVersion': CONTRACT, 'contextHash': row.context_hash,
            'writeRequestId': ledger.pk, 'requestHash': payload_hash, 'basisHash': _hash(basis)})
    if created:
        record_projected_business_transition(object_type=OBJECT_TYPE, object_id=row.pk,
            source_state='', target_state='draft', action_code=ACTION, operator=user, reason=reason,
            audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions=(('', 'draft'),))
        identity.target_entity_id, identity.mapping_status = str(row.pk), 'MATCH'
        identity.full_clean()
        identity.save(update_fields=('target_entity_id', 'mapping_status', 'last_seen'))
    result = {'contractVersion': CONTRACT, 'factSource': 'server', 'recordId': row.pk,
        'contextHash': row.context_hash, 'contentHash': row.content_hash, 'revision': row.revision,
        'inputStandardStatus': 'PENDING_CONFIRMATION', 'writeRequestId': ledger.pk,
        'sourceIdentityId': identity.pk, 'auditId': audit.pk, 'idempotentReplay': False,
        'businessWriteCount': 1, 'auditWriteCount': 1,
        'stateTransitionWriteCount': 1 if created else 0, 'supportWriteCount': 4 if created else 2,
        'formalRulePublished': False, 'readyForGeneration': False,
        'readyForAllocation': False, 'readyForScheduling': False}
    if _has_capacity_reference(basis):
        scope['_capacity_reference'] = [entry['capacityConsumptionReference'] for entry in basis['entries']
            if 'capacityConsumptionReference' in entry][-1]
    result.update(_capacity_current(scope, row))
    ledger.status, ledger.target_entity_id, ledger.result = 'COMMITTED', str(row.pk), result
    ledger.save(update_fields=('status', 'target_entity_id', 'result', 'updated_at'))
    row = OperationInputPreparationDraft.objects.select_related('creation_write_request__source_identity').get(pk=row.pk)
    proof = _verify(row, scope)
    if _has_capacity_reference(row.business_basis):
        result['capacityConsumptionReference'] = _reference_readback(scope, row, proof)
    return result


class OperationInputPreparationService:
    read_preparation = staticmethod(read_preparation)
    save_preparation = staticmethod(save_preparation)
    resolve_capacity_consumption_reference = staticmethod(resolve_capacity_consumption_reference)


__all__ = ['OperationInputPreparationError', 'OperationInputPreparationService',
    'read_preparation', 'save_preparation', 'build_capacity_ruling_basis',
    'build_capacity_consumption_reference', 'resolve_capacity_consumption_reference']
