"""Explicit, plan-scoped preparation evidence for non-quantified EORs.

Manufacturing references remain real EOR foreign keys.  The existing JSON trace
only holds the discriminator and immutable admission evidence; it never supplies
replacement mode/work-center references.  No writer is called here.
"""
from copy import deepcopy
import re

REFERENCE_TYPE = 'PREPARATION_NON_QUANTIFIED'
STANDARD_CAPACITY = 'STANDARD_CAPACITY'
TYPE_KEY = 'manufacturingReferenceType'
CONTEXT_KEY = 'manufacturingPreparationContext'
CONTEXT_CONTRACT = 'PCE-EOR-PREPARATION-CONTEXT-V1'
SCOPE_KEYS = ('companyId', 'productionPlanId', 'manufacturingOutputId',
              'mainCalculationId', 'salesOrderItemId', 'baselineId',
              'routingVersionId', 'routingStepId', 'operationId', 'productTypeId')
HASH_KEYS = ('contextHash', 'objectsHash', 'contentHash')


def _json_type(path):
    return 'JSON_TYPE("trace", \'$.' + path + '\')'


def _json_value(path):
    return 'JSON_EXTRACT("trace", \'$.' + path + '\')'


def _check_sql():
    # SQLite is the migration target. Explicit JSON types and outer COALESCE
    # prevent SQL NULL/boolean/string coercion from admitting malformed rows.
    refs = ('"manufacturing_mode_id"', '"work_center_id"', '"standard_capacity_id"')
    legacy = ['%s IS NULL' % _json_type(TYPE_KEY), '%s IS NULL' % _json_type(CONTEXT_KEY),
              '((' + ' AND '.join(x + ' IS NULL' for x in refs) + ') OR (' +
              ' AND '.join(x + ' IS NOT NULL' for x in refs) + '))']
    new = ["%s = 'text'" % _json_type(TYPE_KEY),
           "%s = '%s'" % (_json_value(TYPE_KEY), REFERENCE_TYPE),
           refs[0] + ' IS NOT NULL', refs[1] + ' IS NOT NULL', refs[2] + ' IS NULL',
           "%s = 'object'" % _json_type(CONTEXT_KEY),
           "%s = 'text'" % _json_type(CONTEXT_KEY + '.contractVersion'),
           "%s = '%s'" % (_json_value(CONTEXT_KEY + '.contractVersion'), CONTEXT_CONTRACT),
           "%s = 'object'" % _json_type(CONTEXT_KEY + '.exactScope')]
    for key in ('recordId', 'revision'):
        path = CONTEXT_KEY + '.' + key
        new += ["%s = 'integer'" % _json_type(path), _json_value(path) + ' > 0']
    for key in SCOPE_KEYS:
        path = CONTEXT_KEY + '.exactScope.' + key
        new += ["%s = 'integer'" % _json_type(path), _json_value(path) + ' > 0']
    for key in HASH_KEYS:
        path = CONTEXT_KEY + '.' + key
        value = _json_value(path)
        new += ["%s = 'text'" % _json_type(path), 'LENGTH(' + value + ') = 64',
                value + " NOT GLOB '*[^0-9a-f]*'"]
    new.append("%s = 'object'" % _json_type(CONTEXT_KEY + '.capacityRuling'))
    for key, value in (('code', 'CONFIRMED_ZERO'), ('meaningCode', 'NON_QUANTIFIED'), ('sourceValue', '0')):
        path = CONTEXT_KEY + '.capacityRuling.' + key
        new += ["%s = 'text'" % _json_type(path), "%s = '%s'" % (_json_value(path), value)]
    new.append("%s = 'object'" % _json_type(CONTEXT_KEY + '.sourceObjectCoverage'))
    for key in ('designItemIds', 'baselineItemIds', 'inputFactIds'):
        path = CONTEXT_KEY + '.sourceObjectCoverage.' + key
        new += ["%s = 'array'" % _json_type(path), "JSON_ARRAY_LENGTH(\"trace\", '$." + path + "') > 0"]
    return 'COALESCE(((' + ' AND '.join(legacy) + ') OR (' + ' AND '.join(new) + ')), 0)'


EOR_REFERENCE_CHECK_SQL = _check_sql()


def reference_type(req):
    trace = req.trace if isinstance(req.trace, dict) else {}
    return trace.get(TYPE_KEY) if TYPE_KEY in trace else None


def preparation_context_valid(value):
    if not isinstance(value, dict) or value.get('contractVersion') != CONTEXT_CONTRACT:
        return False
    scope = value.get('exactScope')
    if (not isinstance(scope, dict) or set(scope) != set(SCOPE_KEYS)
            or any(type(scope.get(key)) is not int or scope[key] <= 0 for key in SCOPE_KEYS)
            or any(type(value.get(key)) is not int or value[key] <= 0 for key in ('recordId', 'revision'))
            or any(not isinstance(value.get(key), str) or re.fullmatch(r'[0-9a-f]{64}', value[key]) is None
                   for key in HASH_KEYS)):
        return False
    if value.get('capacityRuling') != {'code': 'CONFIRMED_ZERO', 'meaningCode': 'NON_QUANTIFIED', 'sourceValue': '0'}:
        return False
    coverage = value.get('sourceObjectCoverage')
    return bool(isinstance(coverage, dict) and all(
        isinstance(coverage.get(key), list) and coverage[key]
        and all(type(pk) is int and pk > 0 for pk in coverage[key])
        and len(coverage[key]) == len(set(coverage[key]))
        for key in ('designItemIds', 'baselineItemIds', 'inputFactIds')))


def reference_record_errors(req):
    trace = req.trace if isinstance(req.trace, dict) else {}
    if TYPE_KEY not in trace and CONTEXT_KEY not in trace:
        return {}
    if trace.get(TYPE_KEY) != REFERENCE_TYPE or not preparation_context_valid(trace.get(CONTEXT_KEY)):
        return {'trace': '不可定量制造需求必须保存明确类型及完整正式准备上下文。'}
    if not req.manufacturing_mode_id or not req.work_center_id or req.standard_capacity_id is not None:
        return {'manufacturing_mode': '不可定量制造需求必须保留真实制造模式、工作中心且不伪造标准产能。'}
    if (req.manufacturing_mode.company_id != req.calculation.company_id
            or req.manufacturing_mode.uom_id != req.uom_id
            or req.work_center.company_id != req.calculation.company_id):
        return {'manufacturing_mode': '不可定量制造引用的公司及正式单位不一致。'}
    calculation_trace = req.calculation.trace if isinstance(req.calculation.trace, dict) else {}
    source_snapshot = calculation_trace.get('sourceSnapshot')
    snapshot = source_snapshot.get('manufacturing') if isinstance(source_snapshot, dict) else None
    if (not isinstance(snapshot, dict) or snapshot.get('capacityMode') != REFERENCE_TYPE
            or snapshot.get(CONTEXT_KEY) != trace[CONTEXT_KEY]
            or snapshot.get('modeId') != req.manufacturing_mode_id
            or snapshot.get('workCenterId') != req.work_center_id
            or snapshot.get('standardCapacityId') is not None):
        return {'trace': '不可定量真实制造引用与生成来源快照不一致。'}
    return {}


def _fail(code, message, **details):
    from .operation_requirement_service import _fail as fail
    fail(code, message, **details)


def generation_scope(value):
    if (not isinstance(value, dict) or set(value) != {'productionPlanId', 'routingStepId'}
            or any(type(value.get(key)) is not int or value[key] <= 0 for key in value)):
        _fail('NON_QUANTIFIED_CONTEXT_REQUIRED', '不可定量承接必须显式提供正式计划及步骤，不能推断唯一计划')
    return value


def _plan_preparation(*, user, generation_context, operation, product_type, work_center=None,read_cache=None,
                      _existing_requirement=None):
    """Read the existing exact preparation contract, never a source reader loop."""
    from .operation_requirement_service import _authorize, VIEW, PLAN_VIEW, _today
    from .operation_workload_source_service import _scope_context, _step_capacity_semantics
    from .operation_input_preparation_service import read_preparation
    from .daily_capacity_service import capacity_source_rules
    from .models import StandardCapacity
    from .plan_step_context_service import effective_baseline
    if user is None:
        _fail('NON_QUANTIFIED_CONTEXT_REQUIRED', '不可定量正式上下文校验缺少当前有权读取的真实办理用户')
    generation_scope(generation_context)
    if _existing_requirement is None:
        _authorize(user, VIEW)
        _authorize(user, PLAN_VIEW)
    else:
        # Internal proof revalidation of an existing EOR; its caller owns the
        # business read/action authorization. Never grant PDE creation/view
        # rights, impersonate its producer, or accept an unsaved/cross-scope row.
        from .models import EngineeringOperationRequirement
        from .production_foundation_service import _snapshot
        req = _existing_requirement
        persisted = (EngineeringOperationRequirement.objects.filter(pk=req.pk,
            calculation__company_id=user.company_id).first()
            if isinstance(req, EngineeringOperationRequirement) else None)
        frozen = req.trace.get(CONTEXT_KEY) if persisted and isinstance(req.trace, dict) else None
        if (not user.is_authenticated or not user.is_active or persisted is None
                or _snapshot(persisted) != _snapshot(req) or not preparation_context_valid(frozen)
                or frozen['exactScope']['companyId'] != user.company_id
                or generation_context != {key:frozen['exactScope'][key]
                    for key in ('productionPlanId','routingStepId')}
                or req.operation_id != operation.pk
                or frozen['exactScope']['productTypeId'] != product_type.pk):
            _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '既有需求读取必须绑定当前同公司完整持久化需求及原准备范围')
    plan, output, item, base, step, kind, applicability = _scope_context(
        user, generation_context['productionPlanId'], generation_context['routingStepId'],_read_cache=read_cache)
    if step.operation_id != operation.pk or kind.pk != product_type.pk:
        _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '不可定量计划步骤的工序或产品类型与规则不一致')
    if work_center is not None and (
            (step.work_center_id and step.work_center_id != work_center.pk)
            or (step.workshop_id and step.workshop_id != work_center.workshop_id)):
        _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '不可定量正式计划步骤资源与规则明确工作中心不一致')
    scope = {'companyId': user.company_id, 'productionPlanId': plan.pk,
             'manufacturingOutputId': output.pk, 'mainCalculationId': base.pk,
             'salesOrderItemId': item.pk, 'baselineId': getattr(effective_baseline(plan), 'pk', None),
             'routingVersionId': output.routing_version_id, 'routingStepId': step.pk,
             'operationId': step.operation_id, 'productTypeId': kind.pk}
    if _existing_requirement is None:
        preparation = read_preparation(user=user, exact_scope=scope,read_cache=read_cache)
    else:
        from . import operation_input_preparation_service as prep
        from .conditional_execution_preparation import saved_for_scope
        if scope != _existing_requirement.trace[CONTEXT_KEY]['exactScope']:
            _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '既有需求的完整准备身份已变化')
        row = saved_for_scope(scope)
        if row is None:
            _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '既有需求缺少原正式准备记录')
        native_scope = prep._scope(user, scope, policy_basis=row.business_basis, read_cache=read_cache)
        preparation = prep._present(native_scope, row, prep._verify(row, native_scope))
        prep._reference_history_check(scope, row)
    capacities = list(StandardCapacity.objects.filter(company_id=user.company_id,
        operation_id=operation.pk, product_type_id=kind.pk))
    semantics, _ = _step_capacity_semantics(user=user, scope=scope, applicability=applicability,
        source_rules=capacity_source_rules(kind, company_id=user.company_id, on_date=_today()),
        capacities=capacities, preparation=preparation)
    if (applicability.get('result') != 'REQUIRED' or semantics.get('preparationRulingOnly') is not True
            or preparation.get('recordStatus') != 'RECORDED'
            or preparation.get('capacityResolution', {}).get('code') != 'CONFIRMED_ZERO'):
        _fail('NON_QUANTIFIED_PREPARATION_INVALID', '当前正式范围没有可消费的有效精确0裁决及必经对象证明')
    return dict(plan=plan, output=output, item=item, base=base, step=step, kind=kind,
                applicability=applicability, scope=scope, preparation=preparation)


def plan_preparation(*, user, generation_context, operation, product_type, work_center=None, read_cache=None):
    from django.core.exceptions import ValidationError
    try:
        def load():
            return _plan_preparation(user=user, generation_context=generation_context,
                                    operation=operation, product_type=product_type, work_center=work_center,read_cache=read_cache)

        from .operation_requirement_service import _ReadOnlyProofCache, _authorize, _digest, _read_once, VIEW, PLAN_VIEW, _today
        from .operation_input_preparation_service import VIEW as PREPARATION_VIEW
        if (user is None or not isinstance(read_cache, _ReadOnlyProofCache)
                or read_cache.user_id != user.pk or not read_cache.is_current(user.company_id)):
            return load()
        generation_scope(generation_context)
        permissions = [_authorize(user, permission) for permission in (VIEW, PLAN_VIEW, PREPARATION_VIEW)]
        raw = read_cache._connection.connection
        if raw is None or not hasattr(raw, 'total_changes'):
            return load()
        from .models import OperationInputPreparationDraft
        from .production_foundation_service import _snapshot
        # Read the whole candidate set (including duplicates), never select a
        # successful record by position. The loader still proves every scope,
        # object, version, audit and ruling before anything enters the cache.
        records = list(OperationInputPreparationDraft.objects.filter(company_id=user.company_id,
            production_plan_id=generation_context['productionPlanId'],
            routing_step_id=generation_context['routingStepId']).order_by('pk')[:2])

        def reference_version(row):
            # Concrete fields only: the presentation snapshot of a work center
            # would additionally evaluate its unrelated capacity catalogue.
            return None if row is None else _digest({field.attname: str(getattr(row, field.attname))
                for field in row._meta.concrete_fields})

        key = ('non_quantified_plan_preparation', user.company_id, user.pk, _digest(permissions), _today(),
            _digest(generation_context), reference_version(operation), reference_version(product_type),
            reference_version(work_center), _digest([_snapshot(row) for row in records]), raw.total_changes)
        # Only the plan-level proof is shared in this user's atomic read. Each
        # source/rule/Fact hash, coverage and frozen expected context is checked
        # separately below. A new request or any same-connection write misses.
        return deepcopy(_read_once(read_cache, key, load))
    except Exception as error:
        if isinstance(error, ValidationError):
            _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '不可定量正式计划、版本或来源上下文校验失败',
                  errors=getattr(error, 'message_dict', error.messages))
        if not hasattr(error, 'code'):
            raise
        # Preserve a native preparation/authorization/scope code. Readiness
        # already owns the handoff error envelope; do not relabel it as success.
        _fail(error.code, getattr(error, 'message', str(error)),
              **(getattr(error, 'details', None) or {}))


def source_preparation_context(*, user, generation_context, origin, fact, operation,
                               product_type, read_cache=None, expected_context=None, work_center=None,
                               return_runtime_context=False, existing_requirement=None):
    from .operation_requirement_service import _extension_object_coverage
    from .plan_step_context_service import effective_baseline, source_selection
    if existing_requirement is not None:
        if (expected_context != existing_requirement.trace.get(CONTEXT_KEY)
                or existing_requirement.source_calculation_id != origin.pk
                or existing_requirement.source_fact_id != fact.pk):
            _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '既有需求不得替换源核算、源事实或原准备上下文')
        current = _plan_preparation(user=user, generation_context=generation_context,
            operation=operation, product_type=product_type, work_center=work_center,
            read_cache=read_cache, _existing_requirement=existing_requirement)
    else:
        current = plan_preparation(user=user, generation_context=generation_context,
            operation=operation, product_type=product_type, work_center=work_center, read_cache=read_cache)
    base, output = current['base'], current['output']
    if (origin.pk != base.pk and (origin.scope != 'fact_extension' or origin.origin_calculation_id != base.pk)):
        _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '所选来源不属于显式计划固定主核算及其合法扩展')
    if any(getattr(origin, key) != getattr(base, key) for key in
           ('company_id', 'source_record_id', 'sales_order_item_id', 'engineering_instance_id')):
        _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '不可定量来源的公司、订单行或工程实例越出显式范围')
    coverage = _extension_object_coverage(user.company_id, base, origin, fact, output, read_cache=read_cache,
        **({'baseline': effective_baseline(current['plan'])}
           if source_selection(current['plan']) is not None else {}))
    partition = current['applicability'].get('objectApplicability')
    expected = (set(partition['requiredBaselineItemIds']) if partition is not None
                else {row['baselineItemId'] for row in current['preparation']['objectCoverage']})
    actual = set(coverage['baselineItemIds'])
    if not actual or not actual <= expected:
        _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '不可定量来源对象未精确落入本次正式必经对象范围')
    prep = current['preparation']
    result = {'contractVersion': CONTEXT_CONTRACT, 'exactScope': current['scope'],
              'recordId': prep['recordId'], 'revision': prep['revision'],
              **{key: prep[key] for key in HASH_KEYS},
              'capacityRuling': {'code': 'CONFIRMED_ZERO', 'meaningCode': 'NON_QUANTIFIED', 'sourceValue': '0'},
              'sourceObjectCoverage': coverage}
    if not preparation_context_valid(result):
        _fail('NON_QUANTIFIED_PREPARATION_INVALID', '原生准备证明未提供完整可保存上下文')
    if expected_context is not None and result != expected_context:
        _fail('NON_QUANTIFIED_PREPARATION_CHANGED', '正式准备修订、范围或对象证明已变化，禁止沿用旧需求身份')
    return (deepcopy(result), current) if return_runtime_context else deepcopy(result)
