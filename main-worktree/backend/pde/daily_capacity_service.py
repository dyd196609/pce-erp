from pde.baseline_usage_service import production_baselines
"""Persisted daily-capacity facts and read-only DAY duration calculations.

Legacy hourly facts are deliberately outside this contract. No object is saved.
"""
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from django.db import transaction
import json
import marshal
import math
import re

from .models import CapacityProductType, StandardCapacity, WorkCenterOperationCapability
from .plan_step_context_service import (
    effective_output, effective_calculation, effective_baseline, source_selection,
)

CONTRACT = "PCE-APS-DAILY-CAPACITY-V1"
SOURCE_RULES_CONTRACT = "PCE-APS-CAPACITY-SOURCE-RULES-V1"
AUXILIARY_DATE_MODE = "AUXILIARY_NO_INDEPENDENT_DATE"
CAPACITY_TRISTATE_CONTRACT = 'PCE-CAPACITY-TRISTATE-V1'
CAPACITY_TRISTATE_PRINCIPLES = {
    'contractVersion': CAPACITY_TRISTATE_CONTRACT,
    'positive': {'code': 'QUANTIFIED', 'statusLabel': '经过且有产能数据'},
    'zero': {'code': 'NON_QUANTIFIED', 'statusLabel': '经过但无法准确核算，不计定量产能占用'},
    'blank': {'code': 'NOT_APPLICABLE', 'statusLabel': '不经过'},
}


def capacity_tristate_semantics(*, source_value, source_scope_proven=False,
        measurement_status=None, scope=None, record_present=None,
        quantitative_occupancy_allowed=False, conflict_code=None,
        preparation_days=None, transfer_days=None):
    """Explain three business meanings, never infer a blank from absent rows.

    Scope proof comes from the native source/object/ruling consumer, not a client
    number. Diagnostic failures have no meaningCode and are not a fourth valid
    capacity state. This pure projection grants no generation or date permission.
    """
    value, meaning = None, None
    invalid = conflict_code
    if measurement_status == 'not_determinable':
        invalid = invalid or 'LEGACY_CAPACITY_SEMANTICS_CONFLICT'
    elif source_value is None and measurement_status is not None:
        invalid = invalid or 'CAPACITY_MEASUREMENT_VALUE_CONFLICT'
    elif source_value is not None:
        try:
            if isinstance(source_value, bool):
                raise ValueError('Boolean is not a capacity quantity')
            value = Decimal(str(source_value))
            if not value.is_finite() or value < 0:
                raise ValueError('Capacity quantity must be finite and nonnegative')
            if value > 0 and record_present is False:
                invalid = invalid or 'CAPACITY_POSITIVE_STANDARD_RECORD_MISSING'
        except (InvalidOperation, TypeError, ValueError):
            invalid = invalid or 'CAPACITY_SOURCE_VALUE_INVALID'
    if not invalid and source_scope_proven:
        if source_value is None:
            meaning = 'NOT_APPLICABLE'
        elif value is not None:
            if measurement_status not in (None, 'measured' if value > 0 else 'zero_capacity'):
                invalid = 'CAPACITY_MEASUREMENT_VALUE_CONFLICT'
            else:
                meaning = 'QUANTIFIED' if value > 0 else 'NON_QUANTIFIED'
    if not meaning and not invalid:
        invalid = 'CAPACITY_SOURCE_SCOPE_UNPROVEN'
    labels = {entry['code']: entry['statusLabel'] for key, entry in CAPACITY_TRISTATE_PRINCIPLES.items()
        if key != 'contractVersion'}
    if meaning:
        label = labels[meaning]
        source_label = ('正式正数产能及其范围已证明' if meaning == 'QUANTIFIED'
            else '当前精确范围已确认按0语义经过' if meaning == 'NON_QUANTIFIED'
            else '正式来源空白或对象结论已证明本范围不经过')
    elif invalid == 'LEGACY_CAPACITY_SEMANTICS_CONFLICT':
        label = '历史产能含义与三态合同冲突，须核对'
        source_label = '历史“适用但无法确定”不能作为有效第四类，也不能据此判定不经过'
    else:
        label = '本范围的产能三态依据尚未证明'
        source_label = ('未取得本范围的正式来源空白证明；缺记录不等于不经过'
            if source_value is None else '原始数量保留；当前范围及其正式语义依据尚未证明')
    record_label = ('已有标准产能记录' if record_present is True else
        '当前范围无标准产能记录；缺记录不等于来源空白或不经过' if record_present is False else
        '标准产能记录存在性未在本投影确认')
    return {'contractVersion': CAPACITY_TRISTATE_CONTRACT, 'principles': deepcopy(CAPACITY_TRISTATE_PRINCIPLES),
        'meaningCode': meaning, 'statusLabel': label, 'valid': meaning is not None,
        'sourceValue': str(value) if value is not None else None,
        'sourceStatusLabel': source_label, 'recordPresenceStatusLabel': record_label,
        'recordPresent': record_present, 'scope': deepcopy(scope) if scope is not None else {},
        'conflictCode': invalid if meaning is None else None,
        'passesOperation': False if meaning == 'NOT_APPLICABLE' else True if meaning else None,
        'quantitativeOccupancyAllowed': bool(meaning == 'QUANTIFIED' and quantitative_occupancy_allowed),
        'independentDurationAllowed': bool(meaning == 'QUANTIFIED' and quantitative_occupancy_allowed),
        'preparationDays': str(preparation_days) if preparation_days is not None else None,
        'transferDays': str(transfer_days) if transfer_days is not None else None,
        'preparationTransferPolicyLabel': (
            '保留准备及转运原始DAY值；仅在原定量时长合同满足后计入，不补造缺失时间' if meaning == 'QUANTIFIED' else
            '保留准备及转运原始DAY值；不形成准确总加工时长，不生成独立定量占用' if meaning == 'NON_QUANTIFIED' else
            '本范围不经过，不计算该工序时间' if meaning == 'NOT_APPLICABLE' else
            '准备及转运原始值仅供追溯，尚未形成准确总加工时长'),
        'dependencyPolicyLabel': ('保留路线前后置依赖；0不表示工序已完成，也不删除步骤' if meaning == 'NON_QUANTIFIED' else
            '保留原路线追溯；后继继承有效前置依赖' if meaning == 'NOT_APPLICABLE' else '保留既有路线前后置依赖'),
        'grantsRulePublication': False, 'grantsRequirementGeneration': False,
        'grantsAllocation': False, 'grantsScheduling': False}


def scoped_capacity_semantics(*, scope, applicability, source_rules, capacity_facts,
        preparation_days=None, transfer_days=None):
    """Project a native exact-step conclusion without choosing a resource."""
    scope = deepcopy(scope)
    state = applicability.get('result')
    common = {'scope': scope, 'record_present': bool(capacity_facts),
        'preparation_days': preparation_days, 'transfer_days': transfer_days}
    if state == 'NOT_APPLICABLE':
        return capacity_tristate_semantics(source_value=None, source_scope_proven=True, **common)
    manifest = source_rules.get('manifest', {})
    valid_source = source_rules.get('status') == 'VALID'
    operation_id = scope.get('operationId')
    if (state == 'PENDING' or (state == 'REQUIRED' and valid_source
            and operation_id in manifest.get('nonApplicableOperationIds', []))):
        return capacity_tristate_semantics(source_value=None,
            conflict_code='CAPACITY_OBJECT_SCOPE_CONFLICT' if state == 'REQUIRED' else 'CAPACITY_OBJECT_SCOPE_UNPROVEN', **common)
    if valid_source and operation_id in manifest.get('auxiliaryOperationIds', []):
        return capacity_tristate_semantics(source_value='0', measurement_status='zero_capacity',
            source_scope_proven=True, **common)
    meanings = [fact.get('capacitySemantics', {}) for fact in capacity_facts]
    valid = [fact for fact in capacity_facts if fact.get('capacitySemantics', {}).get('valid')]
    values = {fact['capacitySemantics']['sourceValue'] for fact in valid}
    if valid and len(valid) == len(capacity_facts) and len(values) == 1:
        return capacity_tristate_semantics(source_value=next(iter(values)),
            measurement_status=valid[0]['measurementStatus'], source_scope_proven=True,
            quantitative_occupancy_allowed=any(fact['available'] for fact in valid), **common)
    conflict = ('CAPACITY_QUANTITATIVE_SELECTION_REQUIRED' if len(values) > 1 else
        next((item.get('conflictCode') for item in meanings if item.get('conflictCode')), None))
    if source_rules.get('status') == 'INVALID':
        conflict = conflict or 'CAPACITY_SOURCE_RULES_INVALID'
    result = capacity_tristate_semantics(source_value=None, conflict_code=conflict, **common)
    result['sourceValues'] = sorted(values)
    if len(values) > 1:
        result['sourceStatusLabel'] = '存在多个合法数量参考；尚未选择资源或数量，不取首条'
    return result


def _valid_business_fact_reference(reference):
    if isinstance(reference, str):
        return bool(reference.strip())
    if not isinstance(reference, dict) or not reference or any(not isinstance(key, str) for key in reference):
        return False
    try:
        json.dumps(reference, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def _capacity_guard_json_supported(value):
    """Keep non-finite/custom JSON on the original strict comparison path."""
    kind = type(value)
    if kind is float:
        return math.isfinite(value)
    if kind in (type(None), bool, int, str):
        return True
    if kind in (tuple, list):
        return all(_capacity_guard_json_supported(item) for item in value)
    if kind is dict:
        return all(_capacity_guard_json_supported(key) and _capacity_guard_json_supported(item)
            for key, item in value.items())
    return False


def _capacity_guard_bytes(model_groups):
    """Complete typed concrete values, encoded only as a pollution guard.

    Marshal is never read back or treated as a business approval. Every call
    rebuilds the full model/JSON values; native source validation still runs.
    Unsupported values retain the existing strict/deepcopy guard below.
    """
    try:
        groups = []
        for models in model_groups:
            group = []
            for model in models:
                if model is None:
                    group.append(None)
                    continue
                fields = []
                for field in model._meta.concrete_fields:
                    value = getattr(model, field.attname)
                    kind = type(value)
                    if kind is Decimal:
                        if not value.is_finite():
                            return None
                        encoded = str(value)
                    elif kind in (date, datetime, time):
                        encoded = value.isoformat()
                    elif kind in (dict, list, tuple):
                        if not _capacity_guard_json_supported(value):
                            return None
                        encoded = value
                    elif kind is float:
                        if not math.isfinite(value):
                            return None
                        encoded = value
                    elif kind in (type(None), bool, int, str, bytes):
                        encoded = value
                    else:
                        return None
                    fields.append((field.attname, kind.__module__, kind.__qualname__, encoded))
                group.append((model._meta.label_lower, tuple(fields)))
            groups.append(tuple(group))
        # Version 2 has no reference/alias flags: merely holding another
        # reference to unchanged nested JSON must not invalidate this read.
        # Every typed concrete value remains encoded on every comparison.
        return marshal.dumps(tuple(groups), 2)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None


def _capacity_guard_snapshot(model_groups, legacy_guard):
    encoded = _capacity_guard_bytes(model_groups)
    return ({'bytes': encoded} if encoded is not None else
        {'legacy': deepcopy(legacy_guard())})


def _capacity_guard_matches(saved, model_groups, legacy_guard):
    if 'bytes' in saved:
        encoded = _capacity_guard_bytes(model_groups)
        return encoded is not None and encoded == saved['bytes']
    from .operation_requirement_service import _same_concrete_values
    return _same_concrete_values(saved['legacy'], legacy_guard())


def capacity_source_rules(product_type, *, company_id, on_date, read_cache=None):
    """Read approved applicability only from consistent current formal SC rows.

    Absence of a capacity never proves absence of an operation. A complete,
    internally consistent source manifest must establish that business fact.
    """
    from system.models import Process
    from . import operation_requirement_service as native
    from .routing_planning_readiness_service import RoutingPlanningReadinessService as Rules

    def outcome(status, label, *, manifest=None, rows=()):
        return {'status': status, 'manifest': manifest or {}, 'capacityRows': list(rows), 'fact': {
            'contractVersion': SOURCE_RULES_CONTRACT, 'status': status, 'statusLabel': label,
            'factSource': 'server', **({'manifest': manifest} if manifest else {}),
        }}

    if product_type is None:
        return outcome('MISSING', '未取得正式产能产品类型，不能推断工序是否经过')
    if product_type.company_id != company_id:
        return outcome('INVALID', '正式产能产品类型不属于当前公司')
    cache = native._requirement_read_cache(read_cache, company_id)

    def load_rows():
        return list(StandardCapacity.objects.filter(
            company_id=company_id, product_type_id=product_type.pk,
        ).select_related('product_type', 'work_center', 'operation', 'uom'))

    def concrete_values(row):
        if row is None:
            return None
        return (row._meta.label_lower, tuple((field.attname, getattr(row, field.attname))
            for field in row._meta.concrete_fields))

    def raw_guard(rows):
        # Full concrete values include every conditions/manifest field and the
        # complete related identities consumed below. The stored deep copy
        # prevents nested JSON mutation from modifying its own comparison.
        return tuple(tuple(concrete_values(model) for model in (
            row, row.product_type, row.work_center, row.operation, row.uom)) for row in rows)

    def model_groups(rows):
        return ((row, row.product_type, row.work_center, row.operation, row.uom) for row in rows)

    raw_key = None
    if cache is not None:
        raw_key = ('capacity_source_raw_rows', company_id, cache.user_id, on_date,
            product_type.pk, native._proof_record_hash(product_type, read_cache=cache))
        saved = cache.get(raw_key)
        if saved is not None and not _capacity_guard_matches(saved['guard'],
                model_groups(saved['rows']), lambda: raw_guard(saved['rows'])):
            # Never allow an altered call-owned ORM instance to seed a source
            # decision or leave dependent approvals alive after pollution.
            cache.invalidate_proofs()
            saved = None
        if saved is None:
            raw_rows = load_rows()
            cache[raw_key] = {'rows': raw_rows, 'guard': _capacity_guard_snapshot(
                model_groups(raw_rows), lambda: raw_guard(raw_rows))}
        else:
            raw_rows = saved['rows']
    else:
        raw_rows = load_rows()
    rows = [row for row in raw_rows if Rules._active_on(row, on_date)]
    # A separately versioned EOR-only scope does not amend the historical APS
    # applicability contract. Prove every declaration before excluding it;
    # unknown or forged JSON labels invalidate the source facts.
    from .manufacturing_capacity_scope import capacity_usage_scope_proof
    legacy_rows = []
    for row in rows:
        try:
            scope = (capacity_usage_scope_proof(row, read_cache=read_cache) if read_cache is not None
                else capacity_usage_scope_proof(row))
        except DailyCapacityError as exc:
            return outcome('INVALID', f'正式产能用途域受阻：{exc}')
        if scope is None:
            legacy_rows.append(row)
    rows = legacy_rows
    manifests = [row.conditions.get('apsSourceRules') if isinstance(row.conditions, dict) else None for row in rows]
    if not any(manifest is not None for manifest in manifests):
        return outcome('MISSING', '没有正式来源规则，产能空缺不能推断为不经过工序')
    invalid = lambda reason: outcome('INVALID', f'正式产能来源规则受阻：{reason}')
    manifest = manifests[0]
    if not isinstance(manifest, dict) or any(item != manifest for item in manifests):
        return invalid('同一产品类型的有效产能来源规则缺失或不一致')
    if (manifest.get('contractVersion') != SOURCE_RULES_CONTRACT
        or not isinstance(manifest.get('sourceSha256'), str)
        or re.fullmatch(r'[0-9a-fA-F]{64}', manifest['sourceSha256']) is None
        or manifest.get('productTypeCode') != product_type.code
        or not _valid_business_fact_reference(manifest.get('businessFactReference'))):
        return invalid('来源合同、文件哈希、产品类型或业务批准引用无效')
    try:
        effective = date.fromisoformat(manifest.get('effectiveDate', ''))
    except (TypeError, ValueError):
        return invalid('来源规则生效日期无效')
    if effective > on_date or not Rules._active_on(product_type, on_date):
        return invalid('来源规则或产品类型尚未生效')
    sets = {}
    for key in ('applicableOperationIds', 'nonApplicableOperationIds', 'auxiliaryOperationIds'):
        values = manifest.get(key)
        if (not isinstance(values, list) or any(type(value) is not int or value <= 0 for value in values)
            or values != sorted(set(values))):
            return invalid('工序身份列表必须是排序、无重复的正式正整数ID')
        sets[key] = set(values)
    applicable, non_applicable, auxiliary = (sets[key] for key in sets)
    if not applicable or applicable & non_applicable or not auxiliary.issubset(applicable):
        return invalid('经过、不经过与配套工序范围互相冲突')
    all_ids = applicable | non_applicable
    real_ids = native._read_once(cache,
        ('capacity_source_raw_operation_ids', company_id, cache.user_id if cache is not None else None,
            on_date, tuple(sorted(all_ids))), lambda:
        set(Process.objects.filter(company_id=company_id, pk__in=all_ids).values_list('pk', flat=True)))
    if real_ids != all_ids:
        return invalid('来源规则包含其他公司或不存在的工序')
    source_days = {}
    for key in ('preparationDays', 'transferDays'):
        if key not in manifest or isinstance(manifest[key], bool):
            return invalid('来源确认的准备及转运DAY值缺失或无效')
        value = manifest[key]
        if value is None:
            source_days[key] = None
            continue
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return invalid('来源确认的准备及转运DAY值必须为有限非负数或明确空值')
        if not parsed.is_finite() or parsed < 0:
            return invalid('来源确认的准备及转运DAY值必须为有限非负数或明确空值')
        source_days[key] = parsed
    seen = set()
    for row in rows:
        conditions = row.conditions
        if (row.company_id != company_id or row.product_type_id != product_type.pk
            or row.effective_from != effective or row.time_basis != 'day'
            or row.time_basis_quantity != Decimal(1) or row.time_unit != 'DAY'
            or conditions.get('sourceSha256') != manifest['sourceSha256']
            or conditions.get('sourceProductTypeCode') != product_type.code
            or not row.work_center_id or not Rules._active_on(row.work_center, on_date)
            or row.work_center.company_id != company_id or not row.operation_id
            or row.operation.company_id != company_id or not row.uom_id
            or row.uom.company_id != company_id or not row.uom.is_active
            or not row.operation.calculation_uom_id or row.uom_id != row.operation.calculation_uom_id
            or row.preparation_days != source_days['preparationDays']
            or row.transfer_days != source_days['transferDays']):
            return invalid('正式产能的公司、类型、资源、单位、日期、天数或来源与规则不一致')
        operation_id = row.operation_id
        if operation_id not in applicable or operation_id in non_applicable:
            return invalid('不经过工序存在正式产能或产能工序不在经过范围')
        try:
            quantity = Decimal(str(row.quantity))
        except (InvalidOperation, ValueError, TypeError):
            return invalid('正式产能数量无效')
        if not quantity.is_finite():
            return invalid('正式产能数量无效')
        if operation_id in auxiliary:
            if row.measurement_status != 'zero_capacity' or quantity != 0:
                return invalid('配套工序与正式零产能事实冲突')
        elif row.measurement_status != 'measured' or quantity <= 0:
            return invalid('独立工序缺少正式正产能，禁止把零值改成独立产能')
        seen.add(operation_id)
    if seen != applicable:
        return invalid('来源经过工序与当前有效正式产能记录不完整对应')
    return outcome('VALID', '已读取一致的正数、0及来源空白三态规则', manifest=manifest, rows=rows)


class DailyCapacityError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _decimal(value, field, *, positive=False):
    if value is None or value == "":
        raise DailyCapacityError(f"{field}_MISSING", f"{field}未维护")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise DailyCapacityError(f"{field}_INVALID", f"{field}必须为有效数值")
    if not parsed.is_finite() or parsed < 0 or (positive and parsed == 0):
        raise DailyCapacityError(f"{field}_INVALID", f"{field}必须为{'正数' if positive else '非负数'}")
    return parsed


def duration_days(*, demand_quantity, capacity_quantity, demand_uom_id, capacity_uom_id,
                  preparation_days, transfer_days):
    """Calculate quantity/daily quantity + explicit DAY times, without conversions."""
    if not demand_uom_id or not capacity_uom_id:
        raise DailyCapacityError("CAPACITY_UOM_MISSING", "需求与产能计量单位必须维护")
    if demand_uom_id != capacity_uom_id:
        raise DailyCapacityError("CAPACITY_UOM_MISMATCH", "需求与日产能单位不一致，必须提供正式同单位作业量")
    demand = _decimal(demand_quantity, "DEMAND_QUANTITY", positive=True)
    capacity = _decimal(capacity_quantity, "DAILY_CAPACITY", positive=True)
    preparation = _decimal(preparation_days, "PREPARATION_DAYS")
    transfer = _decimal(transfer_days, "TRANSFER_DAYS")
    production = demand / capacity
    return {
        "productionDays": str(production), "preparationDays": str(preparation),
        "transferDays": str(transfer), "durationDays": str(preparation + production + transfer),
        "timeUnit": "DAY", "timeUnitLabel": "天", "contractVersion": CONTRACT,
    }


def _plan_capacity_context(plan, company_id=None, *, routing_step_id=None, read_cache=None):
    """Shared fixed-source checks, in the original date-consumer order."""
    from planning.models import ProductionPlan
    if isinstance(plan, ProductionPlan):
        plan = ProductionPlan.objects.get(pk=plan.pk)
    if routing_step_id is not None:
        from .plan_step_context_service import resolve_step_context, bind_plan_context, PlanStepContextError
        try:
            version_context = resolve_step_context(plan, routing_step_id, read_cache=read_cache)
            plan = bind_plan_context(plan, version_context)
        except PlanStepContextError as error:
            raise DailyCapacityError(error.code, error.message) from error
    requirement = plan.planning_requirement
    demand = requirement.demand if requirement else None
    from .plan_step_context_service import effective_output
    output = effective_output(plan) if demand else None
    if not output or not output.routing_version_id:
        raise DailyCapacityError('PLAN_ROUTING_SOURCE_MISSING', '生产计划没有固定制造输出/工艺版本来源')
    item = demand.sales_order_item
    source_company = item.sales_order.company_id if item else None
    expected_company = company_id or source_company
    output_company = (output.product.company_id if output.product_id else
                      output.order_engineering_instance.company_id if output.order_engineering_instance_id else None)
    route_company = (output.routing_version.routing.company_id if output.routing_version.routing_id else
                     output.routing_version.product.company_id if output.routing_version.product_id else None)
    if not expected_company or source_company != expected_company or output_company != expected_company or route_company != expected_company:
        raise DailyCapacityError('PLAN_SOURCE_COMPANY_MISMATCH', '计划、制造输出与固定工艺版本必须属于当前公司')
    if output.order_engineering_instance_id and getattr(output.order_engineering_instance, 'sales_order_item_id', None) != getattr(item, 'id', None):
        raise DailyCapacityError('PLAN_MANUFACTURING_OUTPUT_SOURCE_MISMATCH', '按单制造输出必须对应计划的同一订单行')
    return plan, output, item, expected_company


def _plan_for_step(plan, step_id):
    from .plan_step_context_service import resolve_step_context, bind_plan_context, PlanStepContextError
    context = getattr(plan, '_native_step_version_context', None)
    if context is not None and step_id in {context['step'].pk, context['root_step'].pk}:
        return plan
    try:
        return bind_plan_context(plan, resolve_step_context(plan, step_id))
    except PlanStepContextError as error:
        raise DailyCapacityError(error.code, error.message) from error


def _object_applicability_scope(plan, output, applicability):
    """Consume the resolver's exact partition, never derive exclusions locally."""
    if 'objectApplicability' not in applicability:
        return None
    proof = applicability['objectApplicability']
    expected_scope = {'productionPlanId': plan.pk, 'manufacturingOutputId': output.pk,
        'baselineId': getattr(effective_baseline(plan), 'pk', None)}
    if (not isinstance(proof, dict) or proof.get('scope') != expected_scope
            or proof.get('complete') is not True
            or proof.get('result') != applicability.get('result')
            or proof.get('result') not in {'REQUIRED', 'NOT_APPLICABLE'}):
        raise DailyCapacityError('OBJECT_APPLICABILITY_SCOPE_UNPROVEN',
            '对象适用性尚未完整证明同一计划、制造输出及固定基线范围')

    groups = {}
    for identity in ('DesignItemIds', 'BaselineItemIds'):
        for name in ('full', 'required', 'excluded', 'unknown'):
            values = proof.get(f'{name}{identity}')
            if (not isinstance(values, list) or any(type(value) is not int or value <= 0 for value in values)
                    or len(set(values)) != len(values)):
                raise DailyCapacityError('OBJECT_APPLICABILITY_SCOPE_UNPROVEN',
                    '对象适用性缺少明确且不重复的正式对象及基线项范围')
            groups[f'{name}{identity}'] = set(values)
        full, required, excluded, unknown = (groups[f'{name}{identity}']
            for name in ('full', 'required', 'excluded', 'unknown'))
        if (not full or unknown or required & excluded or required | excluded != full
                or bool(required) != (proof['result'] == 'REQUIRED')):
            raise DailyCapacityError('OBJECT_APPLICABILITY_SCOPE_UNPROVEN',
                '必经对象与正式排除对象必须互斥并恰好覆盖固定范围，未知对象不得跳过')
    return groups


def _validated_demand_object_coverage(plan, output, item, step, demand, *, company_id, read_cache=None):
    """Bind one native current-read proof to each actual saved contribution.

    Object coverage is read metadata, not a retrofit to an immutable allocation
    snapshot. Both capacity consumers use this same binding; absent or invalid
    evidence never becomes the whole baseline by implication.
    """
    from .models import OrderEngineeringBaselineItem, ProductionPlanOperationRequirementAllocation
    plan = _plan_for_step(plan, step['stepId'])
    output = effective_output(plan)
    base, baseline = effective_calculation(plan), effective_baseline(plan)
    if baseline is None or base is None:
        raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
            '对象覆盖缺少可证明的计划固定主核算及基线')

    ids = demand.get('allocationIds') if 'allocationIds' in demand else [demand.get('allocationId')]
    if (not isinstance(ids, list) or not ids or any(type(value) is not int or value <= 0 for value in ids)
            or len(set(ids)) != len(ids)
            or ('allocationId' in demand and demand['allocationId'] is not None
                and ids != [demand['allocationId']])):
        raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
            '对象覆盖必须绑定明确且不重复的已保存分配身份')
    rows = list(ProductionPlanOperationRequirementAllocation.objects.filter(
        pk__in=ids, company_id=company_id, production_plan_id=plan.pk,
        routing_step_id=step['stepId'], operation_id=step['operationId'],
    ).select_related('operation_requirement'))
    if {row.pk for row in rows} != set(ids):
        raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
            '已保存分配身份未完整对应当前公司、计划及步骤')
    contributions = demand.get('contributions')
    if contributions is None and len(ids) == 1:
        contributions = [demand]
    if (not isinstance(contributions, list) or len(contributions) != len(ids)
            or any(not isinstance(row, dict) or type(row.get('allocationId')) is not int
                for row in contributions)
            or {row['allocationId'] for row in contributions} != set(ids)):
        raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
            '当前原生来源证明未完整对应已保存分配集合')
    by_id = {row['allocationId']: row for row in contributions}
    baseline_rows = dict(OrderEngineeringBaselineItem.objects.filter(baseline__in=production_baselines(),
        baseline_id=baseline.pk, design_item__sales_order_item_id=item.pk,
    ).values_list('pk', 'design_item_id'))
    objects, baseline_items, input_facts = set(), set(), set()
    proofs = []
    component_coverages = []
    for row in rows:
        req = row.operation_requirement
        proof = by_id[row.pk].get('objectCoverageProof')
        expected_scope = {'companyId': company_id, 'productionPlanId': plan.pk,
            'manufacturingOutputId': output.pk, 'mainCalculationId': base.pk,
            'salesOrderItemId': item.pk, 'baselineId': baseline.pk,
            'routingVersionId': output.routing_version_id, 'routingStepId': step['stepId'],
            'operationId': step['operationId'], 'productTypeId': row.product_type_id}
        if (not isinstance(proof, dict)
                or proof.get('contractVersion') != 'PCE-ALLOCATION-OBJECT-COVERAGE-READ-V1'
                or proof.get('proofSource') != 'CURRENT_READ_VALIDATED_SOURCE_CHAIN'
                or proof.get('status') != 'PROVEN' or proof.get('scope') != expected_scope
                or any(type(value) is not int or value <= 0 for value in proof.get('scope', {}).values())
                or any(type(proof.get(key)) is not int or proof[key] <= 0 for key in
                    ('allocationId', 'operationRequirementId', 'sourceFactId', 'sourceCalculationId'))
                or proof.get('allocationId') != row.pk or proof.get('operationRequirementId') != req.pk
                or proof.get('sourceCalculationId') != req.source_calculation_id
                or proof.get('sourceFactId') != req.source_fact_id
                or proof.get('sourceHash') != req.source_hash or proof.get('inputHash') != row.input_hash
                or proof.get('operationRequirementInputHash') != req.input_hash
                or proof.get('generationKey') != req.generation_key
                or proof.get('snapshotHasPlanEngineeringSource')
                    is not ('planEngineeringSource' in row.source_snapshot)):
            raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
                '当前对象证明的来源、Hash、计划步骤或分配绑定不一致')
        coverage = proof.get('coverage')
        if (not isinstance(coverage, dict) or type(coverage.get('baselineId')) is not int
                or coverage['baselineId'] <= 0 or coverage['baselineId'] != baseline.pk
                or coverage.get('baselineSnapshotHash') != baseline.snapshot_hash
                or not isinstance(coverage.get('selectedItemHash'), str)
                or coverage['selectedItemHash'] != (base.trace or {})
                    .get('baselineReference', {}).get('selectedItemHash')):
            raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
                '当前对象证明未匹配正式固定基线及所选对象Hash')
        found = {}
        for key in ('designItemIds', 'baselineItemIds', 'inputFactIds'):
            values = coverage.get(key)
            if (not isinstance(values, list) or not values
                    or any(type(value) is not int or value <= 0 for value in values)
                    or len(set(values)) != len(values)):
                raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
                    '当前对象证明缺少明确且不重复的正式对象、基线项及原始输入身份')
            found[key] = set(values)
        if (not found['baselineItemIds'] <= set(baseline_rows)
                or {baseline_rows[value] for value in found['baselineItemIds']} != found['designItemIds']
                or req.source_fact_id not in found['inputFactIds']
                or input_facts & found['inputFactIds']):
            raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
                '对象证明超出固定基线、对象对应冲突或贡献之间重叠')
        composition = proof.get('allocationComposition')
        if composition != row.source_snapshot.get('allocationComposition'):
            raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN', '组合声明证明与分配不可变快照不一致')
        if composition is not None:
            from . import operation_requirement_service as native
            try:
                if native._composition_proof(req, company_id, read_cache=read_cache) != composition:
                    raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN', '组合声明未通过当前正式配置及审计重验')
            except native.OperationRequirementError as exc:
                raise DailyCapacityError(exc.code, exc.message) from exc
        from .operation_contribution_composition import (
            OperationContributionCompositionError, composition_allows_shared_objects,
        )
        found['baselineId'] = coverage['baselineId']
        for previous_composition, previous_found in component_coverages:
            overlaps = any(previous_found[key] & found[key] for key in ('designItemIds', 'baselineItemIds'))
            try:
                if overlaps and not composition_allows_shared_objects(previous_composition, composition, previous_found, found):
                    raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN', '同对象贡献没有不同互补组件的正式组合依据')
            except OperationContributionCompositionError as exc:
                raise DailyCapacityError(exc.code, exc.message) from exc
        component_coverages.append((composition, found))
        objects.update(found['designItemIds'])
        baseline_items.update(found['baselineItemIds'])
        input_facts.update(found['inputFactIds'])
        proofs.append(deepcopy(proof))
    return {'designItemIds': objects, 'baselineItemIds': baseline_items,
        'inputFactIds': input_facts, 'proofs': proofs}


def _validate_applicable_demand_objects(plan, output, item, step, demand, *, company_id,
        read_cache=None, validated_coverage=None):
    """The date and no-date readers require the same saved required subset."""
    plan = _plan_for_step(plan, step['stepId'])
    output = effective_output(plan)
    scope = _object_applicability_scope(plan, output, step['applicability'])
    if scope is None:
        return
    from .models import OrderEngineeringBaselineItem

    baseline_rows = list(OrderEngineeringBaselineItem.objects.filter(baseline__in=production_baselines(),
        baseline_id=getattr(effective_baseline(plan), 'pk', None), design_item__sales_order_item_id=item.pk,
    ).values_list('pk', 'design_item_id'))
    if (scope['fullBaselineItemIds'] != {row[0] for row in baseline_rows}
            or scope['fullDesignItemIds'] != {row[1] for row in baseline_rows}):
        raise DailyCapacityError('OBJECT_APPLICABILITY_SCOPE_UNPROVEN',
            '对象适用性范围与计划当前固定基线对象集合不一致')
    found = validated_coverage if validated_coverage is not None else _validated_demand_object_coverage(
        plan, output, item, step, demand, company_id=company_id, read_cache=read_cache)
    if (found['designItemIds'] != scope['requiredDesignItemIds']
            or found['baselineItemIds'] != scope['requiredBaselineItemIds']):
        raise DailyCapacityError('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
            '已保存分配必须精确覆盖必经对象；不得包含已排除对象、遗漏对象或按比例缩减负荷')


def _read_plan_step_demands(plan, output, item, readiness, *, company_id, demand_reader,
        read_cache=None, validated_coverage=None):
    """One exact-step demand/product-type check; no capacity or date work."""
    scoped, blockers, facts = {}, [], []
    for step in readiness['steps']:
        if step['applicability']['result'] != 'REQUIRED' or step.get('capacityDateMode') == AUXILIARY_DATE_MODE:
            continue
        try:
            demand = demand_reader(plan, output, item, step, company_id=company_id)
            scoped[step['sequence']] = demand
            if (demand.get('productTypeId') is not None
                    and demand['productTypeId'] != readiness.get('productTypeId')):
                raise DailyCapacityError('CAPACITY_PRODUCT_TYPE_SOURCE_MISMATCH',
                    '正式步骤分配的产品类型与当前日产能来源不一致，禁止使用其他类型的产能计算日期')
            _validate_applicable_demand_objects(plan, output, item, step, demand, company_id=company_id,
                read_cache=read_cache, validated_coverage=validated_coverage)
            if demand.get('allocationId') or demand.get('allocationIds'):
                facts.append({'stepId': step['stepId'], **demand,
                    'quantity': str(demand['quantity']), 'planAllocationConfirmed': True})
        except DailyCapacityError as exc:
            blockers.append({'stepId': step['stepId'], 'sequence': step['sequence'], 'operationId': step['operationId'],
                'code': exc.code, 'statusLabel': str(exc)})
            if getattr(exc, 'process_demand_fact', None):
                facts.append({'stepId': step['stepId'], **exc.process_demand_fact})
    return scoped, blockers, facts


def _no_date_capacity_guard_models(capacity):
    return (capacity, capacity.work_center, capacity.operation, capacity.product_type,
        capacity.uom, capacity.product_type.product_category,
        capacity.product_type.manufacturing_process_type)


def _no_date_capacity_raw_guard(capacity):
    """Complete call-owned values, without creating a capacity qualification."""
    values = []
    for model in _no_date_capacity_guard_models(capacity):
        if model is None:
            values.append(None)
            continue
        concrete = []
        for field in model._meta.concrete_fields:
            value = getattr(model, field.attname)
            if hasattr(value, 'isoformat'):
                value = (type(value).__name__, value.isoformat())
            elif isinstance(value, Decimal):
                value = ('Decimal', str(value))
            concrete.append((field.attname, value))
        values.append((model._meta.label_lower, tuple(concrete)))
    return tuple(values)


def _remember_no_date_raw_capacities(user, read_cache, capacities):
    """Index only the full batch's raw rows inside its live typed read."""
    from . import operation_requirement_service as native
    cache = native._requirement_read_cache(read_cache, user.company_id)
    if cache is None or cache.user_id != user.pk:
        return
    for capacity in capacities:
        if capacity.company_id != user.company_id:
            continue  # Never prime another company's FK, even for a bad caller.
        key = ('no_date_raw_capacity', user.company_id, user.pk, native._today(), capacity.pk)
        if key not in cache:
            cache[key] = {'row': capacity, 'guard': _capacity_guard_snapshot(
                [_no_date_capacity_guard_models(capacity)], lambda: _no_date_capacity_raw_guard(capacity))}


def _current_plan_capacity(fact, on_date, *, no_date_reference=None,
        source_rules_cache=None, read_user=None):
    """Fact changes still raise outside the date consumer's candidate try."""
    from . import operation_requirement_service as native
    raw_cache = (native._requirement_read_cache(source_rules_cache, read_user.company_id)
        if read_user is not None else None)
    if raw_cache is not None and raw_cache.user_id != read_user.pk:
        raw_cache = None
    capacity = None
    if raw_cache is not None:
        raw_key = ('no_date_raw_capacity', read_user.company_id, read_user.pk, native._today(), fact['id'])
        saved = raw_cache.get(raw_key)
        if saved is not None:
            if _capacity_guard_matches(saved['guard'],
                    [_no_date_capacity_guard_models(saved['row'])],
                    lambda: _no_date_capacity_raw_guard(saved['row'])):
                capacity = saved['row']
            else:
                # An altered ORM/JSON reference cannot supply current facts or
                # keep other source approvals alive. Re-read the native FK.
                raw_cache.invalidate_proofs()
        if capacity is None:
            capacity = StandardCapacity.objects.select_related('work_center', 'operation', 'uom',
                'product_type__product_category', 'product_type__manufacturing_process_type').get(pk=fact['id'])
            _remember_no_date_raw_capacities(read_user, raw_cache, [capacity])
    else:
        # Existing date/plain callers retain the original native SQL path.
        capacity = StandardCapacity.objects.select_related('work_center').get(pk=fact['id'])
    if raw_cache is not None and capacity.company_id == read_user.company_id:
        source_key = (capacity.company_id, capacity.product_type_id, on_date)
        if source_key not in raw_cache:
            # The original qualification guard below requires this native
            # source-rules read. Construct it from the actual validator after
            # checking the raw capacity, rather than forcing each step onto
            # an uncached full-product read or manufacturing a successful key.
            source_rules = capacity_source_rules(capacity.product_type,
                company_id=capacity.company_id, on_date=on_date, read_cache=raw_cache)
            if raw_cache.is_current(capacity.company_id):
                raw_cache[source_key] = source_rules
    cache = (native._requirement_read_cache(source_rules_cache, capacity.company_id)
        if read_user is not None else None)
    if (cache is not None and (cache.user_id != read_user.pk or read_user.company_id != capacity.company_id
            or (capacity.company_id, capacity.product_type_id, on_date) not in cache)):
        cache = None
    current = capacity_fact(capacity, on_date, **({'source_rules_cache': cache} if cache is not None else {}))
    qualified = False
    if no_date_reference is not None:
        from .operation_requirement_service import _proof_record_hash
        from .manufacturing_capacity_scope import capacity_usage_scope_proof
        reference = no_date_reference['capacityReference']
        qualified = (no_date_reference.get('consumer') == 'ALLOCATED_LOAD_NO_DATE'
            and no_date_reference.get('formalConsumptionValidated') is True
            and reference['standardCapacityId'] == capacity.pk
            and no_date_reference['selectedCapacityFact'] == current
            and reference['capacityRecordHash'] == _proof_record_hash(capacity,
                **({'read_cache': cache} if cache is not None else {}))
            # The same live company/actor cache retains raw scope references;
            # the native ledger/audit/physical-state checks still run each time.
            and no_date_reference['capacityUsageScopeProof'] == capacity_usage_scope_proof(capacity,
                **({'read_cache': cache} if cache is not None else {}))
            and current['capacitySemantics'].get('valid') is True
            and current['capacitySemantics'].get('meaningCode') == 'QUANTIFIED'
            and capacity.measurement_status == 'measured' and capacity.quantity is not None and capacity.quantity > 0)
    if current != fact or not (current['available'] or qualified):
        raise DailyCapacityError('CAPACITY_FACT_CHANGED', '日产能事实发生变化，必须重新读取并计算')
    return capacity


def _allocated_capacity_duration(step, capacity, process_demand):
    """Shared candidate calculation, once per step rather than per object."""
    if (process_demand.get('productTypeId') is not None
            and capacity.product_type_id != process_demand['productTypeId']):
        raise DailyCapacityError('CAPACITY_PRODUCT_TYPE_SOURCE_MISMATCH',
            '所选标准产能未引用该步骤分配的正式产品类型')
    return duration_days(demand_quantity=process_demand['quantity'], capacity_quantity=capacity.quantity,
        demand_uom_id=process_demand['uomId'], capacity_uom_id=capacity.uom_id,
        preparation_days=step['preparationDays'], transfer_days=step['transferDays'])


def _saved_load_capacity_blockers(source_read):
    """Keep exact-step capacity conflicts separate from valid saved-load proof."""
    scope, applicability = source_read.get('scope', {}), source_read.get('applicability', {})
    if not scope or applicability.get('result') == 'NOT_APPLICABLE':
        return []
    blockers, semantics = [], source_read.get('capacitySemantics', {})
    if semantics.get('valid') is False and semantics.get('conflictCode'):
        blockers.append({'stepId': scope['routingStepId'], 'code': semantics['conflictCode'],
            'statusLabel': semantics['statusLabel']})
    requirements = {row['operationRequirementId'] for row in source_read['savedAllocations']['items']}
    used = {row.get('standardCapacityId') for row in source_read['formalRequirements']['items']
        if row['operationRequirementId'] in requirements}
    for fact in source_read.get('standardCapacityFacts', []):
        usage = fact.get('capacityUsageScope', {})
        if (fact['id'] in used and usage.get('usageScope') == 'ENGINEERING_EOR_ONLY'
                and fact.get('independentApsSchedulingAllowed') is False):
            blockers.append({'stepId': scope['routingStepId'], 'standardCapacityId': fact['id'],
                'code': 'ALLOCATED_STANDARD_CAPACITY_UNMATCHED',
                'statusLabel': '已保存负荷引用工程EOR用途产能；当前原生APS定量匹配尚未开放，保留正式数量及用途证明'})
    return blockers


def _no_date_consumption_projection(readiness, source_read, reference, on_date):
    """Project only the authorized single-step no-date consumer, never APS dates."""
    if (reference.get('contractVersion') != 'PCE-PLAN-STEP-CAPACITY-CONSUMPTION-REFERENCE-V1'
            or reference.get('consumer') != 'ALLOCATED_LOAD_NO_DATE'
            or reference.get('formalConsumptionValidated') is not True
            or reference.get('exactScope') != source_read['scope']
            or source_read['applicability']['result'] != 'REQUIRED'
            or len(readiness['steps']) != 1):
        raise DailyCapacityError('CAPACITY_OBJECT_SCOPE_CONFLICT', '正式产能消费关系与当前准确必经步骤不一致')
    scope = reference['exactScope']
    projected = deepcopy(readiness)
    step = projected['steps'][0]
    if (step['stepId'] != scope['routingStepId'] or step['operationId'] != scope['operationId']
            or step['applicability']['result'] != 'REQUIRED'):
        raise DailyCapacityError('CAPACITY_OBJECT_SCOPE_CONFLICT', '本次无日期消费不能替代原生工序适用性结论')
    fact = reference['selectedCapacityFact']
    selected = _current_plan_capacity(fact, on_date, no_date_reference=reference)
    shared = reference['sharedTimeSource']
    if shared['timeUnit'] != 'DAY' or shared['countPolicy'] != 'ONCE_PER_STEP':
        raise DailyCapacityError('APS_SOURCE_RULES_INVALID', '共享准备及转运时间必须为整步骤一次的正式DAY来源')
    times, selections = {}, {}
    for name, field in (('preparation', 'preparationDays'), ('transfer', 'transferDays')):
        value = _decimal(shared[field], field)
        step_days = step.get('timeSelection', {}).get(name, {}).get('stepDays')
        capacity_days = getattr(selected, 'preparation_days' if name == 'preparation' else 'transfer_days')
        if any(raw is not None and _decimal(raw, field) != value for raw in (step_days, capacity_days)):
            raise DailyCapacityError('APS_SOURCE_RULES_INVALID', '既有非空步骤或产能DAY与正式共享时间标准冲突')
        times[field] = str(value)
        selections[name] = {'stepDays': step_days,
            'standardCapacityDays': [{'standardCapacityId': selected.pk,
                'days': str(capacity_days) if capacity_days is not None else None}],
            'selectedDays': str(value), 'source': 'CAPACITY_SOURCE_RULES_HEADER',
            'sourceId': shared['sourceId'], 'referenceHash': shared['referenceHash'], 'timeUnit': 'DAY'}
    resolved = {'DAILY_CAPACITY_MISSING', 'PREPARATION_DAYS_MISSING', 'TRANSFER_DAYS_MISSING'}
    if scope['operationId'] in step.get('sourceRulesFact', {}).get('manifest', {}).get('nonApplicableOperationIds', []):
        resolved.add('SOURCE_OBJECT_APPLICABILITY_CONFLICT')
    pairs = [(code, step['blockerLabels'][index]) for index, code in enumerate(step['blockerCodes'])
        if code not in resolved]
    if fact['workCenterId'] not in {row['id'] for row in step['candidateWorkCenters']}:
        if not any(code == 'WORK_CENTER_CANDIDATE_MISSING' for code, _ in pairs):
            pairs.append(('WORK_CENTER_CANDIDATE_MISSING', '正式消费产能未匹配本次有效工序工作中心候选'))
    step.update(times, dailyCapacity=[deepcopy(fact)], capacities=[deepcopy(fact)],
        timeSelection=selections, capacityConsumptionReference=deepcopy(reference),
        blockerCodes=[code for code, _ in pairs], blockerLabels=[label for _, label in pairs], planningReady=not pairs)
    projected['blockers'] = [b for b in projected['blockers'] if b['code'] not in resolved]
    if any(code == 'WORK_CENTER_CANDIDATE_MISSING' for code, _ in pairs) and not any(
            b['code'] == 'WORK_CENTER_CANDIDATE_MISSING' for b in projected['blockers']):
        projected['blockers'].append({'code': 'WORK_CENTER_CANDIDATE_MISSING',
            'label': '正式消费产能未匹配本次有效工序工作中心候选', 'affectedStepCount': 1})
    projected['requiredHumanInputCodes'] = list(dict.fromkeys(b['code'] for b in projected['blockers']))
    projected.update(capacityConsumptionReference=deepcopy(reference), noDateConsumptionProjected=True,
        scopeReady=not projected['blockers'], planningReady=False,
        readyStepCount=int(not pairs),
        statusCode='NO_DATE_CONSUMPTION_REFERENCE_PROJECTED',
        statusLabel='本步骤按正式关系读取无日期产能及共享DAY来源；日期排程资格未开放',
        blockingSummary='；'.join(b['label'] for b in projected['blockers']) or '无',
        requiredHumanInputLabel='；'.join(b['label'] for b in projected['blockers']) or '无',
        resolvedBlockerCodes=sorted(resolved))
    return projected


def _empty_load_policy(source_read):
    """Consume native plan-stage proof, never infer a policy from no rows."""
    from .operation_workload_source_service import _waiting_trigger, _non_separate_quantity_policy
    scope, applicability = source_read.get('scope', {}), source_read.get('applicability') or {}
    policy = _waiting_trigger(applicability)
    quantity_policy = _non_separate_quantity_policy(source_read.get('inputPreparation'), scope, applicability)
    if applicability.get('result') == 'NOT_APPLICABLE':
        bucket_code, code, label = 'NOT_APPLICABLE', 'NOT_APPLICABLE_VERIFIED', '本步骤正式不适用已核验，无需独立需求和分配'
    elif policy is not None:
        bucket_code, code, label = 'WAITING_TRIGGER', 'WAITING_TRIGGER', policy['triggerPolicyLabel']
    elif quantity_policy is not None:
        bucket_code, code, label = ('NOT_SEPARATELY_MEASURED', 'NOT_SEPARATELY_MEASURED_VERIFIED',
            quantity_policy['statusLabel'])
    else:
        return None
    blockers = deepcopy(source_read.get('blockers', []))
    keys = ('companyId', 'productionPlanId', 'manufacturingOutputId', 'mainCalculationId',
        'salesOrderItemId', 'baselineId', 'routingVersionId', 'routingStepId', 'operationId', 'productTypeId')
    if (source_read.get('factSource') != 'server' or set(scope) != set(keys)
            or any(type(scope[key]) is not int or scope[key] <= 0 for key in keys)
            or applicability.get('pendingCode')):
        blockers.append({'code': 'OBJECT_APPLICABILITY_SCOPE_UNPROVEN',
            'statusLabel': '合法空负荷必须保留本次原生读取的完整准确范围及正式政策'})
    objects = applicability.get('objectApplicability')
    if bucket_code == 'NOT_APPLICABLE' and 'objectApplicability' in applicability:
        if (not isinstance(objects, dict) or objects.get('complete') is not True
                or objects.get('result') != 'NOT_APPLICABLE'
                or objects.get('scope') != {key: scope.get(key) for key in
                    ('productionPlanId', 'manufacturingOutputId', 'baselineId')}
                or any(not isinstance(objects.get('full' + name), list) or not objects['full' + name]
                    or any(type(value) is not int or value <= 0 for value in objects['full' + name])
                    or len(set(objects['full' + name])) != len(objects['full' + name])
                    or objects.get('excluded' + name) != objects['full' + name]
                    or objects.get('required' + name) != [] or objects.get('unknown' + name) != []
                    for name in ('DesignItemIds', 'BaselineItemIds'))):
            blockers.append({'code': 'OBJECT_APPLICABILITY_SCOPE_UNPROVEN',
                'statusLabel': '正式不适用必须完整证明固定对象已排除，未知或部分范围不能豁免分配'})
    for name in ('formalRequirements', 'savedAllocations'):
        bucket = source_read.get(name, {})
        blockers.extend(deepcopy(bucket.get('blockers', [])))
        persisted = bucket.get('persistence') or {}
        if (bucket.get('statusCode') != bucket_code or bucket.get('items') != []
                or persisted.get('factSource') != 'server' or persisted.get('readStatus') != 'loaded'
                or type(persisted.get('recordCount')) is not int or persisted['recordCount'] != 0
                or persisted.get('recordIds') != [] or persisted.get('operationMismatchRecordIds') != []
                or name == 'savedAllocations' and any(bucket.get(key) is not None for key in
                    ('quantity', 'uomId', 'uomLabel'))):
            blockers.append({'code': 'WORKLOAD_PERSISTENCE_READ_FAILED'
                if persisted.get('readStatus') != 'loaded' else 'CONDITIONAL_TRIGGER_PERSISTENCE_CONFLICT'
                if bucket_code == 'WAITING_TRIGGER' else 'QUANTITY_POLICY_PERSISTENCE_CONFLICT'
                if bucket_code == 'NOT_SEPARATELY_MEASURED' else 'OBJECT_APPLICABILITY_SCOPE_UNPROVEN',
                'statusLabel': '本步骤政策与当前真实需求、分配或读取事实不一致，不能承接为空负荷', 'factKey': name})
    return {'statusCode': code, 'statusLabel': label, 'blockers': blockers}


def _empty_load_readback(result, source_read, disposition, *, user, read_cache):
    """Retain policy/reference facts without granting quantitative matching."""
    from .operation_workload_source_service import _scope_context
    scope = source_read['scope']
    plan, output, item, _, step, _, _ = _scope_context(user, scope['productionPlanId'],
        scope['routingStepId'], _read_cache=read_cache)
    blockers = deepcopy(result['blockers']) + disposition['blockers']
    if plan.status != 'confirmed' or output.release_status != 'released_to_manufacturing' or output.routing_version.status != 'released':
        result['sourceStatusBlocker'] = '生产计划、制造输出或工艺版本尚未完成正式发布/确认'
        blockers.append({'code': 'PLAN_STATE_NOT_CONFIRMED', 'statusLabel': result['sourceStatusBlocker']})
    sequences = set(output.routing_version.steps.values_list('sequence', flat=True))
    if any(value not in sequences for value in (step.predecessor_sequences or [])):
        blockers.append({'code': 'DEPENDENCY_REFERENCE_MISSING', 'statusLabel': '前置步骤引用不存在'})
    references = {'step': {'preparationDays': str(step.preparation_days) if step.preparation_days is not None else None,
        'transferDays': str(step.transfer_days) if step.transfer_days is not None else None, 'timeUnit': 'DAY'},
        'standardCapacities': [{'standardCapacityId': fact['id'],
            'preparationDays': fact['preparationDays'], 'transferDays': fact['transferDays'], 'timeUnit': fact['timeUnit']}
            for fact in source_read.get('standardCapacityFacts', [])]}
    verified = not blockers
    row = {'stepId': step.pk, 'sequence': step.sequence, 'operationId': step.operation_id,
        'operationName': step.operation.name, 'applicability': deepcopy(source_read['applicability']),
        'capacitySemantics': deepcopy(source_read.get('capacitySemantics')),
        'inputPreparation': deepcopy(source_read.get('inputPreparation')),
        'predecessorSequences': deepcopy(step.predecessor_sequences or []), 'successorCount': None,
        'timeReferences': references, 'processDemand': None, 'capacityMatches': [],
        'objectCoverage': {'complete': None, 'status': 'INDEPENDENT_QUANTITY_COVERAGE_NOT_CLAIMED',
            'statusLabel': '保留正式适用性及政策依据，不虚构独立数量对象覆盖'},
        'noDateMatchPassed': False, 'legalEmptyLoadVerified': verified,
        'independentAllocationRequired': False if verified else None, 'blockers': blockers,
        'statusCode': disposition['statusCode'] if verified else 'LEGAL_EMPTY_LOAD_CONFLICT',
        'statusLabel': disposition['statusLabel'] if verified else '空负荷政策与当前正式事实存在冲突'}
    result.update(productionPlanNo=plan.plan_no, planSourceQuantity=str(plan.planned_qty),
        planSourceUomId=item.uom_id, manufacturingOutputId=output.pk,
        steps=[row], blockers=blockers, legalEmptyLoadVerified=verified,
        independentAllocationRequired=False if verified else None,
        noDateMatchPassed=False, timeReferences=deepcopy(references), dailyReadinessEvaluated=False,
        processDemandBlockers=[], processDemandFacts=[],
        statusCode=row['statusCode'], statusLabel=row['statusLabel'])
    return result


def _route_sequence_set(route, cache):
    values = frozenset(route.steps.values_list('sequence', flat=True))
    cache[route.pk] = values
    return values


def _no_date_raw_read(*, user, operation_ids, read_cache, routing_keys=None):
    """Raw candidates for this route request; qualification remains per scope.

    A route identity is the complete code/category/process triple used by the
    native readiness selector. Retain every matching type, including duplicate
    and inactive candidates; never narrow to a previously chosen kind PK.
    """
    from .operation_requirement_service import _requirement_read_cache
    from django.db.models import Q
    from django.utils import timezone
    cache = _requirement_read_cache(read_cache, user.company_id)
    if cache is None or cache.user_id != user.pk:
        raise DailyCapacityError('READ_CONTEXT_REQUIRED', '无日期批量读取必须保持本次办理人的有效只读事务')
    types = CapacityProductType.objects.filter(company_id=user.company_id)
    if routing_keys is not None:
        matching = Q(pk__in=[])
        for code, category_id, process_id in sorted(set(routing_keys), key=repr):
            matching |= Q(code=code, product_category_id=category_id,
                manufacturing_process_type_id=process_id)
        types = types.filter(matching)
    types = list(types)
    candidates = StandardCapacity.objects.filter(company_id=user.company_id,
        operation_id__in=operation_ids, time_basis='day', time_basis_quantity=1)
    if routing_keys is not None:
        # These IDs are the entire exact-triple candidate set, not the selected
        # kind. Original duplicate/resource/use-scope checks still see all rows.
        candidates = candidates.filter(product_type_id__in=[kind.pk for kind in types])
    capacities = list(candidates.select_related(
        'product_type__product_category', 'product_type__manufacturing_process_type',
        'uom', 'operation', 'work_center'))
    _remember_no_date_raw_capacities(user, cache, capacities)
    return {'types': types,
        'capacities': capacities,
        'capabilities': list(WorkCenterOperationCapability.objects.filter(
            operation_id__in=operation_ids, work_center__company_id=user.company_id).select_related('work_center')),
        'sequences': {}, 'assessedAt': timezone.now().isoformat()}


def _no_date_capacity_for_source(*, user, source_read, read_cache, raw_read=None,
        saved_rows=None, coverage=None):
    """Private native-bundle consumer shared by overview and current detail."""
    from . import operation_requirement_service as native
    from .operation_workload_source_service import _scope_context
    from .production_foundation_service import ProductionFoundationError
    from .models import ProductionPlanOperationRequirementAllocation
    from django.utils import timezone
    cache = native._requirement_read_cache(read_cache, user.company_id)
    if cache is None or cache.user_id != user.pk:
        raise DailyCapacityError('READ_CONTEXT_REQUIRED', '无日期结果必须来自同一有权办理人的当前读取')
    scope = source_read.get('scope') or {}
    assessed_at = raw_read['assessedAt'] if raw_read is not None else timezone.now().isoformat()
    try:
        if not scope.get('productionPlanId') or not scope.get('routingStepId'):
            raise DailyCapacityError('PLAN_ROUTING_SOURCE_MISSING', '当前步骤准确范围尚未读取成功')
        context = _scope_context(user, scope['productionPlanId'], scope['routingStepId'], _read_cache=cache)
        plan, output, item, base, step, kind, applicability = context
        from .plan_step_context_service import resolve_step_context, bind_plan_context, PlanStepContextError
        # The workload scope cache preserves persisted models, not every
        # transient plan attribute. Restore the native binding with the same
        # actor-owned proof cache before effective_* or demand consumption.
        try:
            version = resolve_step_context(plan, scope['routingStepId'], user=user, read_cache=cache)
        except PlanStepContextError as error:
            raise DailyCapacityError(error.code, error.message) from error
        plan = bind_plan_context(plan, version)
        output, base, step = effective_output(plan), effective_calculation(plan), version['step']
        context = plan, output, item, base, step, kind, applicability
        expected = {'companyId': user.company_id, 'productionPlanId': plan.pk,
            'manufacturingOutputId': output.pk, 'mainCalculationId': base.pk, 'salesOrderItemId': item.pk,
            'baselineId': effective_baseline(plan).pk, 'routingVersionId': output.routing_version_id,
            'routingStepId': step.pk, 'operationId': step.operation_id, 'productTypeId': kind.pk}
        shown_applicability = deepcopy(applicability)
        from .routing_step_applicability_service import RESULT_LABELS
        for fact in (shown_applicability.get('objectApplicability') or {}).get('objects', []):
            decision = fact.get('effectiveDecision', fact.get('decision'))
            if decision in RESULT_LABELS:
                fact['decisionLabel'] = RESULT_LABELS[decision]
        if scope != expected or shown_applicability != source_read.get('applicability'):
            raise DailyCapacityError('PLAN_ROUTING_VERSION_MISMATCH', '无日期结果与本次原生固定步骤及正式适用性不一致')
        if raw_read is None:
            route = output.routing_version.routing
            routing_key = (route.routing_code if route else '',
                route.product_category_id if route else None,
                route.manufacturing_process_type_id if route else None)
            raw_read = _no_date_raw_read(user=user, operation_ids=[step.operation_id],
                read_cache=cache, routing_keys=[routing_key])
        ids = [row['allocationId'] for row in source_read['savedAllocations']['items']]
        if saved_rows is None:
            saved_rows = {row.pk: row for row in ProductionPlanOperationRequirementAllocation.objects.filter(
                company_id=user.company_id, production_plan_id=plan.pk, pk__in=ids).select_related('operation_requirement')}
        demand = cache.get(('verified_process_demand', user.company_id, plan.pk, step.pk))
        prepared = {'context': context, 'source_read': source_read, 'saved_rows': saved_rows,
            'demand': demand, 'coverage': coverage}
        result = AllocatedLoadCapacityReadinessService._assess_read(user=user, production_plan_id=plan.pk,
            routing_step_id=step.pk, read_cache=cache, _prepared=prepared, _raw_read=raw_read)
    except (DailyCapacityError, ProductionFoundationError) as error:
        result = {'steps': [], 'blockers': deepcopy(source_read.get('blockers', [])) +
            [{'code': error.code, 'statusLabel': str(error)}]}
    row = result['steps'][0] if len(result['steps']) == 1 else {}
    blockers = []
    for blocker in result.get('blockers', []) + row.get('blockers', []):
        if blocker not in blockers:
            blockers.append(deepcopy(blocker))
    if result.get('sourceStatusBlocker'):
        blockers.append({'code': 'PLAN_STATE_NOT_CONFIRMED', 'statusLabel': result['sourceStatusBlocker']})
    semantic = source_read.get('capacitySemantics') or {}
    non_quantified = (source_read.get('savedAllocations', {}).get('statusCode') == 'SAVED'
        and semantic.get('valid') is True and semantic.get('meaningCode') == 'NON_QUANTIFIED')
    code = row.get('statusCode', 'NO_DATE_UNPROVEN')
    stage = ('NON_QUANTIFIED_SAVED_LOAD' if non_quantified else code
        if code in {'NOT_APPLICABLE_VERIFIED', 'WAITING_TRIGGER', 'NOT_SEPARATELY_MEASURED_VERIFIED'} else 'QUANTIFIED')
    quantitative_passed = row.get('noDateMatchPassed') is True and not blockers
    matches = []
    for match in row.get('capacityMatches', []):
        compact = {key: deepcopy(match[key]) for key in ('standardCapacityId', 'workCenterId', 'capacityFact',
            'productionDays', 'preparationDays', 'transferDays', 'durationDays', 'timeUnit', 'timeUnitLabel',
            'preparationIncludedCount', 'transferIncludedCount', 'timeSelection') if key in match}
        reference = match.get('capacityConsumptionReference')
        if reference is not None:
            compact['capacityConsumptionReference'] = {key: deepcopy(reference[key]) for key in
                ('contractVersion', 'consumer', 'recordId', 'revision', 'auditIds', 'referenceHash')}
        compact['displayLabels'] = _no_date_display_labels(stage, [compact], matched=quantitative_passed)
        matches.append(compact)
    references = deepcopy(row.get('timeReferences') or {'step': None,
        'standardCapacities': [{key: fact[key] for key in
            ('preparationDays', 'transferDays', 'timeUnit')} | {'standardCapacityId': fact['id']}
            for fact in source_read.get('standardCapacityFacts', [])]})
    compact = {'contractVersion': 'PCE-ALLOCATED-LOAD-NO-DATE-CAPACITY-V1', 'factSource': 'server',
        'scope': deepcopy(scope), 'assessedAt': assessed_at, 'stage': stage, 'statusCode': code,
        'statusLabel': ('有保存负荷，产能无法准确核算；不计独立定量占用' if non_quantified and not blockers else
            row.get('statusLabel', '本步骤无日期产能核对尚未证明')),
        'legalEmptyLoadVerified': result.get('legalEmptyLoadVerified') is True,
        'independentAllocationRequired': result.get('independentAllocationRequired', True),
        'allocatedLoadReadPassed': result.get('allocatedLoadReadPassed') is True,
        'noDateMatchPassed': row.get('noDateMatchPassed') is True and not blockers,
        'scopeNoDateReady': result.get('scopeNoDateReady') is True and not blockers,
        'matchedStepCount': result.get('matchedStepCount', 0),
        'matchedAllocationCount': result.get('matchedAllocationCount', 0),
        'capacityMatches': matches, 'timeReferences': references, 'blockers': blockers,
        'dateLayerBlockers': deepcopy(result.get('dateLayerBlockers', [])),
        'dateConditions': {'planStartDateProvided': False, 'calendarOccupationEvaluated': False,
            'capacityAndResourceExecutionWindowEvaluated': False,
            'statusLabel': '仅核对当前无日期事实；未评估计划日期、执行期间、资源占用或排程'},
        'planningReady': False, 'businessWriteCount': 0, 'auditWriteCount': 0,
        'dateOccupationCount': 0, 'productionScheduleCreatedCount': 0}
    if result.get('capacityConsumptionReference') is not None:
        reference = result['capacityConsumptionReference']
        compact['capacityConsumptionReference'] = {key: deepcopy(reference[key]) for key in
            ('contractVersion', 'consumer', 'recordId', 'revision', 'auditIds', 'referenceHash')}
        compact['originalSourceCapacityBlockers'] = deepcopy(result['originalSourceCapacityBlockers'])
        compact['resolvedSourceCapacityBlockers'] = deepcopy(result['resolvedSourceCapacityBlockers'])
        compact['originalReadinessBlockers'] = deepcopy(result['originalReadiness']['blockers'])
    compact['displayLabels'] = _no_date_display_labels(stage, matches, matched=quantitative_passed)
    compact['resultHash'] = native._digest(compact)
    return compact


def _no_date_display_labels(stage, matches, *, matched=False):
    """Server presentation of the exact selected math; missing stays unknown."""
    boundary = '仅本步骤无日期核对；未形成计划日期、资源占用或排程'
    if len(matches) == 1 and matched:
        match, fact = matches[0], matches[0]['capacityFact']
        times = match.get('timeSelection') or {}
        def origin(name):
            selected = times.get(name) or {}
            source = {'RoutingStep': '路线步骤', 'StandardCapacity': '标准产能',
                'CAPACITY_SOURCE_RULES_HEADER': '正式统一时间来源'}.get(selected.get('source'), selected.get('sourceLabel'))
            return source or '来源未证明'
        return {'capacityLabel': f"{fact['capacityQuantity']} {fact['uomLabel']}/天",
            'productionDaysLabel': f"{match['productionDays']} 天",
            'preparationDaysLabel': f"{match['preparationDays']} 天（本步骤计一次）",
            'transferDaysLabel': f"{match['transferDays']} 天（本步骤计一次）",
            'totalDaysLabel': f"{match['durationDays']} 天（本步骤理论时长）",
            'timeSourceLabel': f"准备：{origin('preparation')}；转运：{origin('transfer')}",
            'scopeBoundaryLabel': boundary}
    reason = {'NON_QUANTIFIED_SAVED_LOAD': '经过但无法准确核算，不计定量产能占用',
        'NOT_APPLICABLE_VERIFIED': '正式不适用，无独立定量时长', 'WAITING_TRIGGER': '当前待触发，未形成独立定量时长',
        'NOT_SEPARATELY_MEASURED_VERIFIED': '不单独计量，无独立计划量或实际量'}.get(stage)
    label = reason or ('存在多个有效产能匹配，请逐项查看' if matches and matched else
        '当前匹配或对象校验受阻，理论天数未知' if matches else '产能或无日期匹配尚未证明')
    return {'capacityLabel': label, 'productionDaysLabel': reason or '理论生产天数未唯一确定',
        'preparationDaysLabel': '仅保留原时间参考，未形成定量计算',
        'transferDaysLabel': '仅保留原时间参考，未形成定量计算',
        'totalDaysLabel': label, 'timeSourceLabel': '原时间来源参考保留；未将未知时间视为零',
        'scopeBoundaryLabel': boundary}


class AllocatedLoadCapacityReadinessService:
    """Authorised saved-load/capacity assessment. Never builds dates or bookings."""

    @classmethod
    @transaction.atomic
    def assess(cls, *, user, production_plan_id, on_date=None, routing_step_id=None):
        from .operation_requirement_service import _authorize, PLAN_VIEW, _source_read_cache

        _authorize(user, PLAN_VIEW)
        return cls._assess_read(user=user, production_plan_id=production_plan_id,
            on_date=on_date, routing_step_id=routing_step_id,
            read_cache=_source_read_cache(user, None))

    @classmethod
    def _assess_read(cls, *, user, production_plan_id, on_date=None, routing_step_id=None,
            read_cache, _prepared=None, _raw_read=None):
        from planning.models import ProductionPlan
        from .operation_requirement_service import OperationRequirementService, process_demand_for_plan
        from .models import OrderEngineeringBaselineItem, ProductionPlanOperationRequirementAllocation
        from .formal_engineering_continuation_service import _baseline_reference
        from .engineering_calculation_service import EngineeringCalculationError
        source_capacity_blockers = []
        consumption_reference = None
        empty_load_policy = None
        assessment_date = on_date or date.today()
        single_step = routing_step_id is not None
        if single_step:
            from .operation_workload_source_service import read_for_plan
            from .operation_requirement_service import _allocation_fact
            # This reader validates the actor, company, fixed manufacturing
            # version and step before reading any target source or allocation.
            # Its saved-load bucket reuses the native contribution/budget proof;
            # unrelated candidate/configuration diagnostics do not invalidate it.
            source_read = (_prepared['source_read'] if _prepared is not None else
                read_for_plan(user=user, production_plan_id=production_plan_id,
                    routing_step_id=routing_step_id, _read_cache=read_cache))
            empty_load_policy = _empty_load_policy(source_read)
            saved = source_read['savedAllocations']
            scope = source_read['scope']
            load_blockers = list(saved['blockers'] if scope else source_read['blockers'])
            ids = [row['allocationId'] for row in saved['items']]
            rows = ([_prepared['saved_rows'][pk] for pk in ids if pk in _prepared['saved_rows']]
                if _prepared is not None else list(ProductionPlanOperationRequirementAllocation.objects.filter(
                    pk__in=ids, company_id=user.company_id, production_plan_id=production_plan_id,
                    routing_step_id=scope['routingStepId']))) if scope else []
            if ({row.pk for row in rows} != set(ids) or any(row.company_id != user.company_id
                    or row.production_plan_id != production_plan_id or row.routing_step_id != scope['routingStepId']
                    for row in rows)):
                raise DailyCapacityError('ALLOCATION_STEP_MISMATCH', '已保存分配不属于当前计划及目标步骤')
            source_capacity_blockers = _saved_load_capacity_blockers(source_read)
            allocation_read = {'contractVersion': source_read['contractVersion'], 'factSource': 'server',
                'productionPlanId': production_plan_id, 'allocations': [_allocation_fact(row) for row in rows],
                'blockers': load_blockers, 'resultCount': len(rows),
                'passed': saved['statusCode'] == 'SAVED' and bool(rows) and not load_blockers,
                'businessWriteCount': 0, 'auditWriteCount': 0, 'sourceRead': source_read}
            if not allocation_read['passed'] and not load_blockers and empty_load_policy is None:
                load_blockers.append({'code': 'PROCESS_DEMAND_PLAN_ALLOCATION_MISSING',
                    'statusLabel': '目标步骤没有通过原生校验的已保存分配，负荷未知'})
        else:
            allocation_read = OperationRequirementService.read(user=user, production_plan_id=production_plan_id,
                _read_cache=read_cache)
        result = {'contractVersion': 'PCE-ALLOCATED-LOAD-NO-DATE-CAPACITY-V1', 'factSource': 'server',
            'productionPlanId': production_plan_id, 'assessmentDate': assessment_date.isoformat(),
            'planStartDate': None, 'planExecutionWindowEvaluated': False, 'allocationRead': allocation_read,
            'allocatedLoadReadPassed': allocation_read['passed'], 'steps': [], 'matchedStepCount': 0,
            'matchedAllocationCount': 0, 'allRequiredStepsCovered': False, 'noDateReady': False,
            'planningReady': False, 'businessWriteCount': 0, 'dateOccupationCount': 0,
            'productionScheduleCreatedCount': 0, 'blockers': list(allocation_read['blockers'])}
        result['blockers'].extend(source_capacity_blockers)
        if single_step:
            result.update(evaluationScope={'type': 'SINGLE_STEP', 'routingStepId': routing_step_id,
                'wholeRouteEvaluated': False}, scopeNoDateReady=False, evaluatedRequiredStepsCovered=False)
            if empty_load_policy is not None:
                return _empty_load_readback(result, source_read, empty_load_policy, user=user, read_cache=read_cache)
        if allocation_read['blockers']:
            return result
        if single_step:
            from .operation_input_preparation_service import resolve_capacity_consumption_reference
            consumption_reference = resolve_capacity_consumption_reference(user=user,
                exact_scope=source_read['scope'], on_date=assessment_date, read_cache=read_cache)
            if consumption_reference is not None:
                resolved = [b for b in source_capacity_blockers
                    if b['stepId'] == source_read['scope']['routingStepId'] and (
                        b['code'] == 'CAPACITY_OBJECT_SCOPE_CONFLICT'
                        or b['code'] == 'ALLOCATED_STANDARD_CAPACITY_UNMATCHED'
                            and b.get('standardCapacityId') == consumption_reference['capacityReference']['standardCapacityId'])]
                result.update(capacityConsumptionReference=deepcopy(consumption_reference),
                    originalSourceCapacityBlockers=deepcopy(source_capacity_blockers),
                    resolvedSourceCapacityBlockers=deepcopy(resolved))
                source_capacity_blockers = [b for b in source_capacity_blockers if b not in resolved]
                result['blockers'] = [b for b in result['blockers'] if b not in resolved]
        plan, output, item, company_id = ((_prepared['context'][0], _prepared['context'][1],
            _prepared['context'][2], user.company_id) if _prepared is not None else
            _plan_capacity_context(ProductionPlan.objects.get(pk=production_plan_id), user.company_id,
                routing_step_id=routing_step_id if single_step else None))
        if single_step:
            routing_step_id = plan._native_step_version_context['step'].pk
        result.update(productionPlanNo=plan.plan_no, planSourceQuantity=str(plan.planned_qty),
            planSourceUomId=item.uom_id, manufacturingOutputId=output.pk)
        readiness_reader = (_daily_capacity_readiness if _prepared is not None else DailyCapacityReadinessService.assess)
        readiness = readiness_reader(output.routing_version,
            bom_version=output.bom_version, on_date=assessment_date,
            engineering_calculation=effective_calculation(plan),
            engineering_document_version=output.engineering_document_version,
            order_engineering_instance=output.order_engineering_instance,
            order_engineering_baseline=effective_baseline(plan),
            production_plan=plan, manufacturing_output=output, user=user,
            **({'routing_step_id': routing_step_id} if single_step else {}),
            **({'_prepared': _prepared, '_raw_read': _raw_read, '_read_cache': read_cache} if _prepared is not None else {}))
        if consumption_reference is not None:
            result['originalReadiness'] = deepcopy(readiness)
            readiness = _no_date_consumption_projection(readiness, source_read, consumption_reference, assessment_date)
        result['readiness'] = readiness  # Active no-date view; originalReadiness is retained above.
        result['dateLayerBlockers'] = [b for b in readiness['blockers'] if b['code'] == 'MANUFACTURING_CALENDAR_MISSING']
        result['blockers'].extend(b for b in readiness['blockers'] if b['code'] != 'MANUFACTURING_CALENDAR_MISSING')
        result['dateConditions'] = {'planStartDateProvided': False, 'calendarOccupationEvaluated': False,
            'capacityAndResourceExecutionWindowEvaluated': False,
            'statusLabel': '仅核对评估日的当前记录；未评估计划执行期间、日期窗口或资源占用'}
        if plan.status != 'confirmed' or output.release_status != 'released_to_manufacturing' or output.routing_version.status != 'released':
            result['sourceStatusBlocker'] = '生产计划、制造输出或工艺版本尚未完成正式发布/确认'
            return result

        def saved_demand(*args, **kwargs):
            demand = (_prepared['demand'] if _prepared is not None else
                process_demand_for_plan(*args, user=user, read_cache=read_cache, **kwargs))
            if demand is None:
                raise DailyCapacityError('PROCESS_DEMAND_PLAN_ALLOCATION_MISSING', '该计划步骤没有已保存分配；已分配负荷未知，不以候选需求或零值代替')
            return demand

        scoped, demand_blockers, demand_facts = _read_plan_step_demands(plan, output, item, readiness,
            company_id=company_id, demand_reader=saved_demand, read_cache=read_cache,
            validated_coverage=_prepared['coverage'] if _prepared is not None else None)
        result.update(processDemandBlockers=demand_blockers, processDemandFacts=demand_facts)
        saved_rows = (_prepared['saved_rows'] if _prepared is not None else
            {r.pk: r for r in ProductionPlanOperationRequirementAllocation.objects.filter(
                pk__in=[r['allocationId'] for r in allocation_read['allocations']], company_id=company_id,
                production_plan_id=plan.pk).select_related('operation_requirement')})
        def expected_for_plan(current_plan):
            expected, reason = None, '缺少可证明的计划固定对象范围'
            baseline, base = effective_baseline(current_plan), effective_calculation(current_plan)
            cache, key = None, None
            if _prepared is not None and baseline is not None and base is not None:
                from . import operation_requirement_service as native
                cache = native._requirement_read_cache(read_cache, company_id)
                if cache is not None and cache.user_id == user.pk:
                    source_selection(current_plan)  # Preserve the full in-memory source guard.
                    version = getattr(current_plan, '_native_step_version_context', {})
                    try:
                        key = ('no_date_expected_objects', company_id, user.pk, current_plan.pk,
                            *(native._proof_record_hash(model, read_cache=cache) for model in
                                (item, base, baseline, effective_output(current_plan))),
                            version.get('_sourceIntegrity'), getattr(version.get('binding'), 'pk', None),
                            native._today(), cache._write_epoch)
                    except (AttributeError, TypeError, ValueError):
                        key = None  # Unsupported values retain the original native proof.
                    if key is not None and key in cache:
                        return set(cache[key]), reason
            if baseline is not None and base is not None:
                baseline_items = list(OrderEngineeringBaselineItem.objects.filter(baseline__in=production_baselines(),
                    baseline_id=baseline.pk, design_item__sales_order_item_id=item.pk)
                    .order_by('source_attribute_id', 'design_item_id', 'pk'))
                try:
                    reference = _baseline_reference(baseline, baseline_items)
                    if reference == base.trace.get('baselineReference'):
                        expected = {r.design_item_id for r in baseline_items}
                except EngineeringCalculationError as exc:
                    reason = exc.message
            if (expected and key is not None and cache.is_current(company_id)
                    and cache.user_id == user.pk and key[-1] == cache._write_epoch):
                cache[key] = frozenset(expected)
            return expected, reason

        original_expected, original_coverage_reason = expected_for_plan(plan)
        matched_ids, required_results = set(), []
        for step in readiness['steps']:
            current_plan = _plan_for_step(plan, step['stepId'])
            current_output = effective_output(current_plan)
            expected_objects, coverage_reason = ((expected_for_plan(current_plan))
                if source_selection(current_plan) is not None else (original_expected, original_coverage_reason))
            row = {'stepId': step['stepId'], 'sequence': step['sequence'], 'operationId': step['operationId'],
                'operationName': step.get('operationName', ''), 'applicability': step['applicability'],
                'capacityDateMode': step.get('capacityDateMode'), 'processDemand': None, 'capacityMatches': [],
                'blockers': [deepcopy(b) for b in source_capacity_blockers if b['stepId'] == step['stepId']],
                'dateLayerBlockers': [b for b in step['blockerCodes'] if b == 'MANUFACTURING_CALENDAR_MISSING'],
                'noDateMatchPassed': False, 'objectCoverage': {'complete': False, 'status': 'NOT_EVALUATED'}}
            if step.get('capacitySemantics', {}).get('preparationRulingOnly'):
                row.update(capacitySemantics=deepcopy(step['capacitySemantics']),
                    inputPreparation=deepcopy(step['inputPreparation']),
                    preparationSourceRead=deepcopy(step['preparationSourceRead']))
            result['steps'].append(row)
            if step['applicability']['result'] != 'REQUIRED' or step.get('capacityDateMode') == AUXILIARY_DATE_MODE:
                row['statusCode'] = ('AUXILIARY' if step.get('capacityDateMode') == AUXILIARY_DATE_MODE
                                     else step['applicability']['result'])
                row['statusLabel'] = step['applicability'].get('resultLabel', '工序适用性未证明')
                row['blockers'].extend({'code': code, 'statusLabel': step['blockerLabels'][index]}
                    for index, code in enumerate(step['blockerCodes']) if code != 'MANUFACTURING_CALENDAR_MISSING')
                continue
            required_results.append(row)
            failure = next((b for b in demand_blockers if b['stepId'] == step['stepId']), None)
            if failure:
                row.update(statusCode='LOAD_UNPROVEN', statusLabel=failure['statusLabel'], blockers=row['blockers'] + [failure])
                continue
            demand = scoped[step['sequence']]
            ids = demand.get('allocationIds') or [demand['allocationId']]
            contributions = [saved_rows[i] for i in ids]
            try:
                coverage = (_prepared['coverage'] if _prepared is not None and _prepared['coverage'] is not None else
                    _validated_demand_object_coverage(current_plan, current_output, item, step, demand,
                        company_id=company_id, read_cache=read_cache))
                objects = coverage['designItemIds']
            except DailyCapacityError as exc:
                coverage = None
                objects = set()
                row['blockers'].append({'code': exc.code, 'statusLabel': str(exc)})
            object_scope = _object_applicability_scope(current_plan, current_output, step['applicability'])
            required_objects = object_scope['requiredDesignItemIds'] if object_scope is not None else expected_objects
            complete = bool(required_objects) and objects == required_objects
            if object_scope is not None:
                complete = complete and expected_objects == object_scope['fullDesignItemIds']
            row['objectCoverage'] = {'complete': complete,
                'status': 'COMPLETE_FIXED_BASELINE_SCOPE' if complete else 'OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
                'designItemIds': sorted(objects), 'expectedDesignItemIds': sorted(required_objects) if required_objects is not None else None,
                'baselineItemIds': sorted(coverage['baselineItemIds']) if coverage is not None else [],
                'inputFactIds': sorted(coverage['inputFactIds']) if coverage is not None else [],
                'proofSource': 'CURRENT_READ_VALIDATED_SOURCE_CHAIN' if coverage is not None else None,
                'proofStatusLabel': ('本次读取验证已保存贡献的对象证明；未改写历史快照' if coverage is not None
                    else '本次读取尚未取得可核验的对象证明'),
                'proofs': deepcopy(coverage['proofs']) if coverage is not None else [],
                'statusLabel': '已覆盖计划固定基线对象范围' if complete else coverage_reason if expected_objects is None
                    else '仅证明已保存对象贡献；其余基线对象是否不适用尚未证明'}
            if object_scope is not None:
                row['objectCoverage'].update(
                    fullDesignItemIds=sorted(object_scope['fullDesignItemIds']),
                    excludedDesignItemIds=sorted(object_scope['excludedDesignItemIds']),
                    status='COMPLETE_REQUIRED_OBJECT_SCOPE' if complete else 'OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
                    statusLabel='已覆盖全部必经对象，其余对象有正式排除依据' if complete
                        else '已保存分配未完整证明当前必经对象及正式排除范围')
            row['processDemand'] = {**demand, 'quantity': str(demand['quantity']),
                'savedContributions': [{'allocationId': r.pk, 'operationRequirementId': r.operation_requirement_id,
                    'sourceSnapshot': r.source_snapshot, 'auditId': r.audit_record_id} for r in contributions]}
            if consumption_reference is not None:
                expected_load = consumption_reference['savedLoadReference']
                expected_coverage = consumption_reference['validatedObjectCoverage']
                if (set(ids) != set(expected_load['allocationIds'])
                        or {r.operation_requirement_id for r in contributions} != set(expected_load['operationRequirementIds'])
                        or demand['quantity'] != _decimal(expected_load['quantity'], 'DEMAND_QUANTITY', positive=True)
                        or demand['uomId'] != expected_load['uomId'] or coverage is None
                        or any(set(coverage[key]) != set(expected_coverage[key]) for key in
                            ('designItemIds', 'baselineItemIds', 'inputFactIds'))):
                    row['blockers'].append({'code': 'CAPACITY_OBJECT_SCOPE_CONFLICT',
                        'statusLabel': '本次实际保存负荷或对象证明与正式产能消费关系不一致'})
                row['capacityConsumptionReference'] = deepcopy(consumption_reference)
            row['blockers'].extend({'code': code, 'statusLabel': step['blockerLabels'][index]}
                for index, code in enumerate(step['blockerCodes']) if code != 'MANUFACTURING_CALENDAR_MISSING')
            allowed_capacities = {r.operation_requirement.standard_capacity_id for r in contributions}
            if not row['blockers']:
                for fact in step['dailyCapacity']:
                    selected_reference = (consumption_reference if consumption_reference is not None
                        and fact['id'] == consumption_reference['capacityReference']['standardCapacityId'] else None)
                    if (not fact['available'] and selected_reference is None) or fact['id'] not in allowed_capacities:
                        continue
                    capacity_kwargs = ({'source_rules_cache': read_cache, 'read_user': user}
                        if _prepared is not None else {})
                    capacity = (_current_plan_capacity(fact, assessment_date, no_date_reference=selected_reference, **capacity_kwargs)
                        if selected_reference is not None else _current_plan_capacity(fact, assessment_date, **capacity_kwargs))
                    try:
                        days = _allocated_capacity_duration(step, capacity, demand)
                    except DailyCapacityError as exc:
                        row['blockers'].append({'code': exc.code, 'statusLabel': str(exc)})
                        continue
                    row['capacityMatches'].append({'standardCapacityId': capacity.pk, 'workCenterId': capacity.work_center_id,
                        'capacityFact': fact, **days, 'preparationIncludedCount': 1, 'transferIncludedCount': 1,
                        **({'capacityConsumptionReference': deepcopy(selected_reference)} if selected_reference is not None else {}),
                        **({'timeSelection': step['timeSelection']} if single_step else {})})
            if not row['capacityMatches'] and not row['blockers']:
                row['blockers'].append({'code': 'ALLOCATED_STANDARD_CAPACITY_UNMATCHED',
                    'statusLabel': '已保存分配引用的标准产能未匹配本次适用候选，理论时长未知'})
            if not complete:
                row['blockers'].append({'code': 'OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN',
                    'statusLabel': row['objectCoverage']['statusLabel']})
            row['noDateMatchPassed'] = bool(row['capacityMatches']) and not row['blockers'] and complete
            row['statusCode'] = 'MATCHED' if row['noDateMatchPassed'] else 'MATCH_OR_COVERAGE_UNPROVEN'
            row['statusLabel'] = '已保存负荷、对象覆盖及标准产能无日期匹配通过' if row['noDateMatchPassed'] else '无日期匹配或对象覆盖尚未证明'
            if row['noDateMatchPassed']:
                matched_ids.update(ids)
        result['matchedStepCount'] = sum(r['noDateMatchPassed'] for r in required_results)
        result['matchedAllocationCount'] = len(matched_ids)
        applicability_known = all(s['applicability']['result'] in {'REQUIRED', 'NOT_APPLICABLE'} for s in readiness['steps'])
        result['allRequiredStepsCovered'] = applicability_known and bool(required_results) and all(r['objectCoverage']['complete'] for r in required_results)
        result['noDateReady'] = (applicability_known and bool(required_results)
            and not result['blockers'] and all(r['noDateMatchPassed'] for r in required_results))
        result['blockers'].extend(demand_blockers)
        result['blockers'].extend({'stepId': r['stepId'], **b} for r in required_results
            for b in r['blockers'] if b not in demand_blockers)
        result['statusLabel'] = ('已保存负荷与标准产能无日期匹配通过；日期条件未评估' if result['noDateReady']
            else '已核对保存负荷；全路线仍有负荷、覆盖或产能未证明项')
        if single_step:
            result.update(scopeNoDateReady=result['noDateReady'],
                evaluatedRequiredStepsCovered=result['allRequiredStepsCovered'],
                allRequiredStepsCovered=False, noDateReady=False,
                statusLabel='本步骤已保存负荷与标准产能无日期匹配通过；整路线及日期未评估'
                    if result['noDateReady'] else '本步骤无日期匹配或对象覆盖尚未证明')
        return result


def working_date_window(*, start_date, duration, calendar, daily_bookings=None, horizon_days=3660):
    """Reserve fractional working-day slots in an in-memory resource calendar.

    A positive calendar day is one capacity day. Available minutes select open
    days only; they cannot fabricate shifts or scale a business daily capacity.
    The caller owns temporary bookings; no persistence or schedule object exists.
    """
    remaining = _decimal(duration, "DURATION_DAYS", positive=True)
    if not isinstance(start_date, date):
        raise DailyCapacityError("START_DATE_REQUIRED", "必须明确排产开始日期")
    weekly = calendar.get("weeklyAvailableMinutes") if isinstance(calendar, dict) else None
    keys = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
    if not isinstance(weekly, dict) or set(weekly) != set(keys) or calendar.get("contractVersion") != "PCE-MFG-CALENDAR-V1.0" or not calendar.get("timezone"):
        raise DailyCapacityError("MANUFACTURING_CALENDAR_MISSING", "制造日历合同未维护")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1440 for v in weekly.values()):
        raise DailyCapacityError("MANUFACTURING_CALENDAR_INVALID", "制造日历每日可用分钟无效")
    exceptions = calendar.get("exceptions", [])
    if not isinstance(exceptions, list):
        raise DailyCapacityError("MANUFACTURING_CALENDAR_INVALID", "日期例外必须为列表")
    exception_map = {}
    for item in exceptions:
        try:
            key = date.fromisoformat(str(item["date"])).isoformat()
            minutes = item["availableMinutes"]
        except (KeyError, TypeError, ValueError):
            raise DailyCapacityError("MANUFACTURING_CALENDAR_INVALID", "日期例外无效")
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not 0 <= minutes <= 1440 or key in exception_map:
            raise DailyCapacityError("MANUFACTURING_CALENDAR_INVALID", "日期例外重复或分钟无效")
        exception_map[key] = minutes
    bookings = daily_bookings if daily_bookings is not None else {}
    proposed = dict(bookings)
    allocations = []
    current = start_date
    for _ in range(horizon_days):
        key = current.isoformat()
        minutes = exception_map.get(key, weekly[keys[current.weekday()]])
        used = Decimal(str(proposed.get(key, "0")))
        if not used.is_finite() or not 0 <= used <= 1:
            raise DailyCapacityError("RESOURCE_BOOKING_INVALID", "资源当天占用超过一天")
        if minutes > 0 and used < 1:
            amount = min(Decimal(1) - used, remaining)
            proposed[key] = str(used + amount)
            allocations.append({"date": key, "allocatedDays": str(amount)})
            remaining -= amount
            if remaining == 0:
                bookings.clear()
                bookings.update(proposed)
                return {"startDate": allocations[0]["date"], "endDate": allocations[-1]["date"],
                        "allocations": allocations, "timeUnit": "DAY", "businessWriteCount": 0}
        current += timedelta(days=1)
    raise DailyCapacityError("CALENDAR_HORIZON_EXHAUSTED", "日历期间内没有足够的可用工作日")


def capacity_fact(row, on_date=None, *, source_rules=None, source_rules_cache=None):
    from .routing_planning_readiness_service import RoutingPlanningReadinessService as Rules
    on_date = on_date or date.today()
    formal_context_valid = bool(Rules._active_on(row, on_date) and row.effective_from and row.product_type_id
                     and Rules._active_on(row.product_type, on_date)
                     and row.work_center_id and Rules._active_on(row.work_center, on_date)
                     and row.operation_id and Rules._active_on(row.operation, on_date)
                     and row.work_center.company_id == row.company_id
                     and row.operation.company_id == row.company_id
                     and row.product_type.company_id == row.company_id
                     and row.uom.company_id == row.company_id
                     and row.uom.is_active and row.time_basis == "day"
                     and row.time_basis_quantity == Decimal(1))
    available = bool(formal_context_valid and row.measurement_status == "measured"
        and row.quantity is not None and row.quantity > 0)
    # This surface is also used while the formal creation transaction is still
    # building its ledger. A scope declaration can only deny APS availability
    # here; the EOR gate separately requires committed authoritative proof.
    conditions = row.conditions if isinstance(getattr(row, 'conditions', None), dict) else {}
    declared_scope = 'capacityUsageScope' in conditions
    if declared_scope:
        available = False
    semantic_scope_proven = (formal_context_valid and row.measurement_status == 'measured'
        and getattr(row.operation, 'calculation_uom_id', row.uom_id) == row.uom_id)
    if row.measurement_status == 'zero_capacity' or 'apsSourceRules' in conditions:
        proof = source_rules
        if proof is None and 'apsSourceRules' in conditions:
            cache_key = (row.company_id, row.product_type_id, on_date)
            if source_rules_cache is None:
                proof = capacity_source_rules(row.product_type, company_id=row.company_id, on_date=on_date)
            else:
                from .operation_requirement_service import _ReadOnlyProofCache, _requirement_read_cache
                cache = _requirement_read_cache(source_rules_cache, row.company_id)
                # The caller owns this dictionary for one read/list only. Never
                # retain a source proof between requests or write/verify stages.
                if isinstance(source_rules_cache, _ReadOnlyProofCache):
                    # Typed reads reuse only guarded raw references here. The
                    # manifest, unit and scope validators still run each time;
                    # expired/foreign caches fall through to fresh native SQL.
                    proof = capacity_source_rules(row.product_type, company_id=row.company_id,
                        on_date=on_date, read_cache=cache)
                    if cache is not None:
                        # Preserve the existing native consumer's key, while
                        # never using it to bypass the raw/model guards above.
                        cache[cache_key] = proof
                else:
                    if cache_key not in source_rules_cache:
                        source_rules_cache[cache_key] = capacity_source_rules(
                            row.product_type, company_id=row.company_id, on_date=on_date)
                    proof = source_rules_cache[cache_key]
        semantic_scope_proven = bool(formal_context_valid and proof and proof['status'] == 'VALID'
            and row.pk in {item.pk for item in proof['capacityRows']}
            and row.operation_id in proof['manifest'].get(
                'auxiliaryOperationIds' if row.measurement_status == 'zero_capacity' else 'applicableOperationIds', []))
    semantics = capacity_tristate_semantics(source_value=row.quantity,
        measurement_status=row.measurement_status, source_scope_proven=semantic_scope_proven,
        scope={'companyId': row.company_id, 'productTypeId': row.product_type_id,
            'productTypeCode': row.product_type.code if row.product_type_id else None,
            'operationId': row.operation_id, 'standardCapacityId': row.pk, 'workCenterId': row.work_center_id},
        record_present=True, quantitative_occupancy_allowed=available,
        preparation_days=row.preparation_days, transfer_days=row.transfer_days)
    fact = {
        "id": row.pk, "code": row.code, "name": row.name,
        "productTypeId": row.product_type_id,
        "productTypeCode": row.product_type.code if row.product_type_id else None,
        "productTypeName": row.product_type.name if row.product_type_id else None,
        "workCenterId": row.work_center_id, "operationId": row.operation_id,
        "operationName": row.operation.name if row.operation_id else None,
        "capacityQuantity": str(row.quantity) if row.quantity is not None else None,
        "quantity": str(row.quantity) if row.quantity is not None else None,
        "uomId": row.uom_id, "uomCode": row.uom.code, "uomLabel": row.uom.name,
        "timeBasis": row.time_basis, "timeBasisQuantity": str(row.time_basis_quantity) if row.time_basis_quantity is not None else None,
        "preparationDays": str(row.preparation_days) if row.preparation_days is not None else None,
        "transferDays": str(row.transfer_days) if row.transfer_days is not None else None,
        "timeUnit": "DAY", "timeUnitLabel": "天", "measurementStatus": row.measurement_status,
        "statusLabel": semantics['statusLabel'], 'capacitySemantics': semantics,
        'capacityAvailabilityLabel': '可用于原定量产能计算' if available else '未开放独立定量产能计算',
        "available": available, "effectiveDate": row.effective_from.isoformat() if row.effective_from else None,
        "factSource": "server", "contractVersion": CONTRACT,
    }
    if declared_scope:
        fact.update({
            'statusLabel': '专用产能未开放APS排程，需核验用途域与正式审计',
            'capacityUsageScope': conditions['capacityUsageScope'],
            'independentApsSchedulingAllowed': False,
        })
    return fact


def work_center_capacity_facts(work_center, on_date=None, *, source_rules_cache=None):
    rows = getattr(work_center, '_pce_snapshot_capacities', None)
    if rows is None:
        rows = work_center.standard_capacities.filter(time_basis="day", product_type__isnull=False).select_related(
            "product_type", "uom", "operation", "work_center").order_by("product_type__code", "operation_id", "pk")
    proof_cache = source_rules_cache if source_rules_cache is not None else {}
    return [capacity_fact(row, on_date, source_rules_cache=proof_cache) for row in rows]


class DailyCapacityReadinessService:
    @classmethod
    def assess_plan_date_scope(cls, plan, *, company_id, on_date, user=None):
        """Date-only bridge; retain the direct mixed-version refusal below.

        Return JSON readiness separately from call-owned native step contexts.
        Scheduling keys belong to the original plan, even when a successor
        route numbers its effective steps differently. Nothing is persisted.
        """
        from .models import PlanStepVersionBinding
        from django.core.exceptions import ValidationError
        from .plan_step_context_service import (
            resolve_step_context, bind_plan_context, version_fact,
            effective_routing_version, PlanStepContextError,
        )
        plan, output, item, company_id = _plan_capacity_context(plan, company_id)
        bindings = PlanStepVersionBinding.objects.filter(production_plan_id=plan.pk)
        if not bindings.exists():
            # Preserve the established unbound date contract and its guard.
            return cls.assess(output.routing_version, bom_version=output.bom_version,
                engineering_calculation=output.engineering_calculation,
                engineering_document_version=output.engineering_document_version,
                order_engineering_instance=output.order_engineering_instance,
                order_engineering_baseline=output.order_engineering_baseline,
                production_plan=plan, manufacturing_output=output, on_date=on_date), {}
        if user is None or user.company_id != company_id:
            raise DailyCapacityError('PLAN_MIXED_VERSION_DATE_SCOPE_REQUIRED',
                '混合来源日期核对必须由当前公司办理人按有效步骤上下文读取')
        from system.authorization import AuthorizationService
        decision = AuthorizationService.decide(user=user, action_code='planning.view',
            organization_id=company_id, business_object={'organizationId': company_id})
        if not decision.get('allowed'):
            raise DailyCapacityError(decision.get('decisionCode', 'PERMISSION_DENIED'),
                decision.get('reason', '没有生产计划读取权限'))
        roots = list(output.routing_version.steps.order_by('sequence', 'pk'))
        sequences = {step.sequence for step in roots}
        root_ids = {step.pk for step in roots}
        if (not roots or len(sequences) != len(roots)
                or any(type(value) is not int or value <= 0 for value in sequences)):
            raise DailyCapacityError('PLAN_MIXED_VERSION_DATE_SCOPE_REQUIRED',
                '原计划路线缺少完整且唯一的逻辑步骤，不能组合日期')
        # Do not let a malformed old binding disappear outside the root loop.
        if any(company != company_id or root not in root_ids
                for company, root in bindings.values_list('company_id', 'root_step_id')):
            raise DailyCapacityError('PLAN_MIXED_VERSION_DATE_SCOPE_REQUIRED',
                '计划步骤绑定超出原路线或公司范围')
        for step in roots:
            predecessors = step.predecessor_sequences
            if (not isinstance(predecessors, list)
                    or any(type(value) is not int or value not in sequences for value in predecessors)
                    or len(set(predecessors)) != len(predecessors)):
                raise DailyCapacityError('DEPENDENCY_REFERENCE_MISSING', '原路线前置步骤引用不完整或重复')
        remaining = {step.sequence: set(step.predecessor_sequences) for step in roots}
        resolved = set()
        while remaining:
            ready = {key for key, predecessors in remaining.items() if predecessors <= resolved}
            if not ready:
                raise DailyCapacityError('ROUTING_DEPENDENCY_CYCLE', '原路线前置步骤形成循环')
            resolved.update(ready)
            remaining = {key: value for key, value in remaining.items() if key not in ready}

        contexts, sources = {}, {}
        # First prove *all* actual sources, before evaluating any calendars.
        for root in roots:
            try:
                context = resolve_step_context(plan, root.pk, user=user)
                bound = bind_plan_context(plan, context)
                effective = context['step']
                selected_output = effective_output(bound)
                if (context['plan'].pk != plan.pk or context['originalOutput'].pk != output.pk
                        or context['root_step'].pk != root.pk or effective.operation_id != root.operation_id
                        or selected_output.routing_version_id != effective.routing_version_id):
                    raise DailyCapacityError('PLAN_MIXED_VERSION_DATE_SCOPE_REQUIRED',
                        '有效步骤未精确对应原计划逻辑步骤及正式输出')
                if (selected_output.release_status != 'released_to_manufacturing'
                        or effective_routing_version(bound).status != 'released'):
                    raise DailyCapacityError('PLAN_SOURCE_NOT_RELEASED', '有效步骤的制造输出或路线尚未正式发布')
                sources[root.sequence] = version_fact(context)
            except ValidationError as exc:
                raise DailyCapacityError(getattr(exc, 'code', None) or 'PLAN_STEP_SOURCE_UNPROVEN',
                    getattr(exc, 'message', str(exc))) from exc
            contexts[root.sequence] = (bound, selected_output, item, context)

        rows, counts, labels = [], Counter(), {}
        for root in roots:
            bound, selected_output, _, context = contexts[root.sequence]
            effective = context['step']
            try:
                scoped = cls.assess(effective_routing_version(bound),
                    bom_version=selected_output.bom_version,
                    engineering_calculation=effective_calculation(bound),
                    engineering_document_version=selected_output.engineering_document_version,
                    order_engineering_instance=selected_output.order_engineering_instance,
                    order_engineering_baseline=effective_baseline(bound),
                    production_plan=bound, manufacturing_output=selected_output,
                    routing_step_id=effective.pk, user=user, on_date=on_date)
            except ValidationError as exc:
                raise DailyCapacityError(getattr(exc, 'code', None) or 'PLAN_STEP_SOURCE_UNPROVEN',
                    getattr(exc, 'message', str(exc))) from exc
            if (len(scoped['steps']) != 1 or scoped['steps'][0]['stepId'] != effective.pk
                    or scoped['steps'][0]['operationId'] != root.operation_id):
                raise DailyCapacityError('PLAN_MIXED_VERSION_DATE_SCOPE_REQUIRED',
                    '单步骤读取没有完整对应有效来源，禁止授予整计划日期资格')
            row = deepcopy(scoped['steps'][0])
            row.update(rootStepId=root.pk, effectiveSequence=row['sequence'],
                effectivePredecessorSequences=row['predecessorSequences'],
                sequence=root.sequence, predecessorSequences=list(root.predecessor_sequences),
                engineeringVersion=sources[root.sequence], productTypeId=scoped['productTypeId'])
            rows.append(row)
            counts.update(row['blockerCodes'])
            labels.update({code: label for code, label in zip(row['blockerCodes'], row['blockerLabels'])})
        successors = Counter(p for step in roots for p in step.predecessor_sequences)
        for row in rows:
            row['successorCount'] = successors[row['sequence']]
        blockers = [{'code': code, 'label': labels[code], 'affectedStepCount': count}
            for code, count in counts.items()]
        ready = bool(rows) and not blockers and all(row['planningReady'] for row in rows)
        surface = {'contractVersion': CONTRACT, 'factSource': 'server',
            'assessmentDate': on_date.isoformat(), 'routingVersionId': output.routing_version_id,
            'bomVersionId': output.bom_version_id, 'steps': rows, 'stepCount': len(rows),
            'planningReady': ready, 'effectiveStepSourcesValidated': True,
            'evaluationScope': {'type': 'PLAN_EFFECTIVE_STEPS', 'wholeRouteEvaluated': True,
                'productionPlanId': plan.pk, 'rootRoutingVersionId': output.routing_version_id},
            'dependencyTopology': {'rootStepCount': sum(not s.predecessor_sequences for s in roots),
                'branchStepCount': sum(count > 1 for count in successors.values()),
                'mergeStepCount': sum(len(s.predecessor_sequences) > 1 for s in roots),
                'dependencyReferenceIntegrity': True},
            'blockers': blockers, 'requiredHumanInputCodes': list(counts),
            'statusLabel': '有效步骤来源已承接；日产能资料齐备' if ready else '有效步骤来源已承接；日期资料仍有阻断',
            'businessWriteCount': 0, 'productionScheduleCreatedCount': 0}
        return surface, contexts

    @classmethod
    def assess(cls, routing_version, *, bom_version=None, on_date=None,
               engineering_calculation=None, engineering_document_version=None,
               order_engineering_baseline=None, order_engineering_instance=None,
               production_plan=None, manufacturing_output=None, routing_step_id=None, user=None):
        return _daily_capacity_readiness(routing_version, bom_version=bom_version, on_date=on_date,
            engineering_calculation=engineering_calculation, engineering_document_version=engineering_document_version,
            order_engineering_baseline=order_engineering_baseline, order_engineering_instance=order_engineering_instance,
            production_plan=production_plan, manufacturing_output=manufacturing_output,
            routing_step_id=routing_step_id, user=user)


def _daily_capacity_readiness(routing_version, *, bom_version=None, on_date=None,
        engineering_calculation=None, engineering_document_version=None,
        order_engineering_baseline=None, order_engineering_instance=None,
        production_plan=None, manufacturing_output=None, routing_step_id=None, user=None,
        _prepared=None, _raw_read=None, _read_cache=None):
    from .routing_planning_readiness_service import RoutingPlanningReadinessService as Rules
    from .routing_step_applicability_service import (
        RoutingStepApplicabilityResolver, CONTRACT_VERSION as APPLICABILITY_CONTRACT,
        NOT_APPLICABLE, PENDING,
    )
    on_date = on_date or date.today()
    route = routing_version.routing
    company_id = route.company_id if route else routing_version.product.company_id
    single_step = routing_step_id is not None
    if production_plan is not None and not single_step:
        from .models import PlanStepVersionBinding
        if PlanStepVersionBinding.objects.filter(production_plan_id=production_plan.pk).exists():
            raise DailyCapacityError('PLAN_MIXED_VERSION_DATE_SCOPE_REQUIRED',
                '计划包含显式步骤工程版本承接，整体日期核对不得回退原输出；请按有效步骤上下文核对')
    step_query = routing_version.steps.select_related(
        'operation__calculation_uom', 'operation__work_center', 'work_center')
    if single_step:
        if type(routing_step_id) is not int or routing_step_id <= 0:
            raise DailyCapacityError('ROUTING_STEP_ID_INVALID', '路线步骤必须是正式正整数ID')
        if production_plan is None or manufacturing_output is None:
            raise DailyCapacityError('PLAN_ROUTING_SOURCE_MISSING', '单步骤核对必须由正式计划及固定制造输出承接')
        _, fixed_output, _, _ = ((_prepared['context'][0], _prepared['context'][1], _prepared['context'][2], company_id)
            if _prepared is not None else _plan_capacity_context(production_plan, company_id, routing_step_id=routing_step_id))
        if (fixed_output.pk != manufacturing_output.pk
                or fixed_output.routing_version_id != routing_version.pk):
            raise DailyCapacityError('PLAN_ROUTING_VERSION_MISMATCH', '目标步骤必须属于计划固定制造输出及路线版本')
        step_query = step_query.filter(pk=routing_step_id,
            operation__company_id=company_id, is_active=True)
        if _prepared is None and not step_query.exists():
            raise DailyCapacityError('ROUTING_STEP_SCOPE_MISMATCH', '目标步骤不属于计划固定的有效路线版本及公司')
    types = ([row for row in _raw_read['types'] if row.company_id == company_id
        and row.code == (route.routing_code if route else '')
        and row.product_category_id == (route.product_category_id if route else None)
        and row.manufacturing_process_type_id == (route.manufacturing_process_type_id if route else None)]
        if _raw_read is not None else list(CapacityProductType.objects.filter(
            company_id=company_id, code=route.routing_code if route else '',
            product_category_id=route.product_category_id if route else None,
            manufacturing_process_type_id=route.manufacturing_process_type_id if route else None)))
    types = [row for row in types if Rules._active_on(row, on_date)]
    product_type = types[0] if len(types) == 1 else None
    source_rules = capacity_source_rules(product_type, company_id=company_id, on_date=on_date,
        **({'read_cache': _read_cache} if _prepared is not None else {}))
    if _prepared is not None and product_type is not None and source_rules.get('status') == 'VALID':
        from .operation_requirement_service import _requirement_read_cache
        cache = _requirement_read_cache(_read_cache, company_id)
        if cache is not None and user is not None and cache.user_id == user.pk:
            cache[(company_id, product_type.pk, on_date)] = source_rules
    steps = [_prepared['context'][4]] if _prepared is not None else list(step_query)
    preparation_steps = set()
    if user is not None and production_plan is not None and manufacturing_output is not None:
        _, fixed_output, _, _ = ((_prepared['context'][0], _prepared['context'][1], _prepared['context'][2], user.company_id)
            if _prepared is not None else _plan_capacity_context(production_plan, user.company_id,
                routing_step_id=routing_step_id if single_step else None))
        if (user.company_id != company_id or fixed_output.pk != manufacturing_output.pk
                or fixed_output.routing_version_id != routing_version.pk):
            raise DailyCapacityError('PLAN_ROUTING_VERSION_MISMATCH',
                '准备裁决只能由办理人同公司计划固定的制造输出及路线版本承接')
        from .models import OperationInputPreparationDraft
        preparation_steps = ({steps[0].pk} if (_prepared['source_read'].get('inputPreparation') or {}).get('recordId') else set()) if _prepared is not None else set(
            OperationInputPreparationDraft.objects.filter(company_id=company_id, production_plan_id=production_plan.pk,
                routing_step_id__in=[step.pk for step in steps]).values_list('routing_step_id', flat=True))
    # Only version identities are read outside the target, to retain the
    # real predecessor-reference check. No other step is resolved/evaluated.
    sequence_set = ((_raw_read['sequences'].setdefault(routing_version.pk, None)
        or _route_sequence_set(routing_version, _raw_read['sequences'])) if _raw_read is not None else
        set(routing_version.steps.values_list('sequence', flat=True))
        if single_step else {s.sequence for s in steps})
    successors = Counter() if single_step else Counter(p for s in steps for p in (s.predecessor_sequences or []))
    labels = {
        "ROUTING_STEPS_MISSING": "路线版本没有工艺步骤",
        "OPERATION_INACTIVE": "工序已停用或不在有效期间",
        "ROUTING_STEP_INACTIVE": "路线步骤已停用",
        "DEPENDENCY_REFERENCE_MISSING": "前置步骤引用不存在",
        "CAPACITY_PRODUCT_TYPE_MISSING": "日产能产品类型未维护或存在歧义",
        "WORK_CENTER_CANDIDATE_MISSING": "候选工作中心未维护",
        "DAILY_CAPACITY_MISSING": "对应产品类型/工序的有效日产能未维护",
        "DAILY_CAPACITY_AMBIGUOUS": "同资源存在多个有效日产能事实",
        "PREPARATION_DAYS_MISSING": "准备时间（天）未维护",
        "TRANSFER_DAYS_MISSING": "转运时间（天）未维护",
        "MANUFACTURING_CALENDAR_MISSING": "工作中心制造日历未维护",
        "ROUTING_STEP_APPLICABILITY_PENDING": "工序适用条件尚无可证明的正式结论",
        "SOURCE_OBJECT_APPLICABILITY_CONFLICT": "正式对象适用性与产能来源工序范围冲突",
        "APS_SOURCE_RULES_INVALID": "正式产能空白/配套工序来源规则无效或互相冲突",
    }
    result = []
    counts = Counter()
    if not steps: counts["ROUTING_STEPS_MISSING"] = 1
    for step in steps:
        operation = step.operation
        step_plan = _plan_for_step(production_plan, step.pk) if production_plan is not None else None
        selected = source_selection(step_plan) if step_plan is not None else None
        applicability = deepcopy(_prepared['context'][6]) if _prepared is not None else RoutingStepApplicabilityResolver.resolve(
            step, bom_version=bom_version,
            engineering_calculation=effective_calculation(step_plan) if selected is not None else engineering_calculation,
            engineering_document_version=engineering_document_version,
            order_engineering_baseline=effective_baseline(step_plan) if selected is not None else order_engineering_baseline,
            order_engineering_instance=order_engineering_instance,
            production_plan=step_plan, manufacturing_output=manufacturing_output,
        )
        routing_applicability = applicability
        date_mode = 'INDEPENDENT_DATE'
        source_conflict_label = ''
        manifest = source_rules.get('manifest', {})
        preparation_source = None
        if step.pk in preparation_steps and applicability['result'] == 'REQUIRED':
            # Reuse the authorized formal reader and its exact-scope ruling
            # selector. Never trust a caller-supplied preparation dictionary
            # or let a capacity ruling decide whether objects must pass.
            from .operation_workload_source_service import read_for_plan
            source_read = (_prepared['source_read'] if _prepared is not None else
                read_for_plan(user=user, production_plan_id=production_plan.pk, routing_step_id=step.pk))
            semantics = source_read.get('capacitySemantics', {})
            if semantics.get('preparationRulingOnly'):
                preparation_source = source_read
        object_proof = applicability.get('objectApplicability')
        object_pending = ('objectApplicability' in applicability and
            (applicability['result'] == PENDING or not isinstance(object_proof, dict)
             or object_proof.get('complete') is not True or object_proof.get('result') == PENDING))
        object_source_conflict = False
        if preparation_source is not None:
            date_mode = AUXILIARY_DATE_MODE
            source_conflict_label = '原始产能来源保留；当前精确范围采用已保存0裁决，正式投入来源、需求及负荷门禁仍保留'
        elif source_rules['status'] == 'VALID' and 'objectApplicability' in applicability:
            manifest = source_rules['manifest']
            if object_pending:
                source_conflict_label = '对象适用性证据待定，产能来源空白或配套声明不能替代精确对象结论'
            elif operation.pk in manifest['nonApplicableOperationIds'] and applicability['result'] == 'REQUIRED':
                object_source_conflict = True
                source_conflict_label = '正式对象要求经过该工序，但产能来源声明不经过，必须先核对冲突'
            elif operation.pk in manifest['auxiliaryOperationIds']:
                if applicability['result'] == NOT_APPLICABLE:
                    source_conflict_label = '精确对象已全部正式排除；通用配套声明不改变本次对象结论'
                else:
                    date_mode = AUXILIARY_DATE_MODE
        elif source_rules['status'] == 'VALID':
            manifest = source_rules['manifest']
            if operation.pk in manifest['nonApplicableOperationIds']:
                if applicability['result'] == 'REQUIRED':
                    object_source_conflict = True
                    source_conflict_label = '正式路线要求执行，但产能来源声明不经过；保留必经结论并核对范围冲突'
                else:
                    if applicability['result'] == PENDING:
                        source_conflict_label = '正式业务来源已确认不经过，本次排产跳过；原工程待定事实保留在路线适用性追溯'
                    applicability = {**applicability, 'result': NOT_APPLICABLE,
                        'resultLabel': '来源确认不经过该工序', 'sourceLabel': '正式产能来源空白规则',
                        'sourceRulesContract': SOURCE_RULES_CONTRACT}
            elif operation.pk in manifest['auxiliaryOperationIds']:
                date_mode = AUXILIARY_DATE_MODE
                if applicability['result'] == PENDING:
                    source_conflict_label = '正式来源已确认配套工序，但既有工程适用条件待定，保留阻断；不独立排产'
                else:
                    applicability = {**applicability, 'result': 'REQUIRED',
                        'resultLabel': '来源确认配套工序，仍经过但不独立排产', 'sourceLabel': '正式零产能配套规则',
                        'sourceRulesContract': SOURCE_RULES_CONTRACT}
        if applicability['result'] == NOT_APPLICABLE:
            date_mode = 'NOT_APPLICABLE'
        elif applicability['result'] == PENDING and date_mode != AUXILIARY_DATE_MODE:
            date_mode = 'APPLICABILITY_PENDING'
        blockers = []
        if source_rules['status'] == 'INVALID': blockers.append('APS_SOURCE_RULES_INVALID')
        if object_source_conflict: blockers.append('SOURCE_OBJECT_APPLICABILITY_CONFLICT')
        if source_rules['status'] == 'VALID' and date_mode != 'NOT_APPLICABLE':
            try:
                # Compare declared facts, not the value used by a historical import.
                # A missing source time leaves the existing explicit-step selection intact.
                time_conflict = any(
                    value is not None and manifest[field] is not None
                    and Decimal(str(value)) != Decimal(str(manifest[field]))
                    for field, value in (('preparationDays', step.preparation_days),
                                         ('transferDays', step.transfer_days)))
            except (InvalidOperation, ValueError, TypeError):
                time_conflict = True
            if time_conflict:
                blockers.append('APS_SOURCE_RULES_INVALID')
                source_conflict_label = '路线步骤天数与正式来源配置的DAY值冲突，未修改路线'
        if not step.is_active: blockers.append("ROUTING_STEP_INACTIVE")
        if any(x not in sequence_set for x in (step.predecessor_sequences or [])):
            blockers.append("DEPENDENCY_REFERENCE_MISSING")
        if applicability["result"] == PENDING:
            blockers.append("ROUTING_STEP_APPLICABILITY_PENDING")
        if applicability["result"] in {NOT_APPLICABLE, PENDING}:
            counts.update(blockers)
            result.append({
                "stepId": step.pk, "sequence": step.sequence, "predecessorSequences": step.predecessor_sequences or [],
                "successorCount": successors[step.sequence], "operationId": operation.pk,
                "operationCode": operation.code, "operationName": operation.name, "applicability": applicability,
                "routingApplicability": routing_applicability, "capacityDateMode": date_mode,
                "sourceRulesFact": source_rules['fact'],
                "sourceRulesConflictLabel": source_conflict_label,
                "dailyCapacity": [], "capacities": [], "candidateWorkCenters": [], "equipment": [],
                "preparationDays": None, "transferDays": None, "timeUnit": "DAY", "timeUnitLabel": "天",
                "workloadReady": False, "planningReady": not blockers, "capacityDemandEvaluated": False,
                "capacityDemandSkippedReason": applicability["resultLabel"],
                "blockerCodes": blockers, "blockerLabels": [labels[x] for x in blockers],
            })
            continue
        if not Rules._active_on(operation, on_date): blockers.append("OPERATION_INACTIVE")
        if preparation_source is not None:
            # This exact-plan ruling is qualitative evidence, not the
            # manifest auxiliary exemption. Its formal input/read gates
            # remain authoritative even though no quantitative time exists.
            for blocker in preparation_source['blockers']:
                code = blocker['code']
                labels.setdefault(code, blocker.get('statusLabel', code))
                if code not in blockers:
                    blockers.append(code)
            counts.update(blockers)
            result.append({
                'stepId': step.pk, 'sequence': step.sequence, 'predecessorSequences': step.predecessor_sequences or [],
                'successorCount': successors[step.sequence], 'operationId': operation.pk,
                'operationCode': operation.code, 'operationName': operation.name, 'applicability': applicability,
                'routingApplicability': routing_applicability, 'capacityDateMode': date_mode,
                'sourceRulesFact': source_rules['fact'], 'sourceRulesConflictLabel': source_conflict_label,
                'capacitySemantics': deepcopy(preparation_source['capacitySemantics']),
                'inputPreparation': deepcopy(preparation_source['inputPreparation']),
                'preparationSourceRead': deepcopy(preparation_source),
                'dailyCapacity': [], 'capacities': [], 'candidateWorkCenters': [], 'equipment': [],
                'preparationDays': None, 'transferDays': None, 'timeUnit': 'DAY', 'timeUnitLabel': '天',
                'workloadReady': False, 'planningReady': not blockers, 'capacityDemandEvaluated': False,
                'capacityDemandSkippedReason': '精确0裁决不形成独立定量时长；正式投入来源、需求及负荷按原生读取核对',
                'blockerCodes': blockers, 'blockerLabels': [labels[code] for code in blockers],
            })
            continue
        candidates = {}
        def add(w, source, role):
            if w and w.company_id == company_id and Rules._active_on(w, on_date):
                candidates.setdefault(w.pk, {"id": w.pk, "code": w.code, "name": w.name,
                    "workshopId": w.workshop_id, "source": source, "role": role,
                    "calendar": Rules._calendar_fact(w)})
        add(step.work_center, "RoutingStep.work_center", "direct")
        add(operation.work_center, "Process.work_center", "default")
        relations = ([rel for rel in _raw_read['capabilities'] if rel.operation_id == operation.pk]
            if _raw_read is not None else WorkCenterOperationCapability.objects.filter(operation=operation).select_related("work_center"))
        for rel in relations:
            if Rules._active_on(rel, on_date):
                add(rel.work_center, f"WorkCenterOperationCapability:{rel.pk}", rel.assignment_role)
        if date_mode == AUXILIARY_DATE_MODE:
            auxiliary_rows = [row for row in source_rules['capacityRows'] if row.operation_id == operation.pk]
            if not any(row.work_center_id in candidates for row in auxiliary_rows):
                blockers.append('WORK_CENTER_CANDIDATE_MISSING')
            counts.update(blockers)
            result.append({
                'stepId': step.pk, 'sequence': step.sequence, 'predecessorSequences': step.predecessor_sequences or [],
                'successorCount': successors[step.sequence], 'operationId': operation.pk,
                'operationCode': operation.code, 'operationName': operation.name, 'applicability': applicability,
                'routingApplicability': routing_applicability, 'capacityDateMode': date_mode,
                'sourceRulesFact': source_rules['fact'], 'candidateWorkCenters': list(candidates.values()),
                'sourceRulesConflictLabel': source_conflict_label,
                'dailyCapacity': [capacity_fact(row, on_date, source_rules=source_rules) for row in auxiliary_rows],
                'capacities': [capacity_fact(row, on_date, source_rules=source_rules) for row in auxiliary_rows], 'equipment': [],
                'preparationDays': source_rules['manifest']['preparationDays'],
                'transferDays': source_rules['manifest']['transferDays'], 'timeUnit': 'DAY', 'timeUnitLabel': '天',
                'workloadReady': False, 'workloadStatusLabel': '经过但无法准确核算，不计定量产能占用',
                'planningReady': not blockers, 'capacityDemandEvaluated': False,
                'capacityDemandSkippedReason': '来源确认按0语义经过；不计算独立定量时长或占用，保留路线依赖',
                'blockerCodes': blockers, 'blockerLabels': [labels[x] for x in blockers],
            })
            continue
        capacities = ([row for row in _raw_read['capacities'] if row.company_id == company_id
            and row.product_type_id == product_type.pk and row.operation_id == operation.pk
            and row.work_center_id in candidates and row.time_basis == 'day' and row.time_basis_quantity == 1]
            if _raw_read is not None else list(StandardCapacity.objects.filter(
                company_id=company_id, product_type=product_type, operation=operation,
                work_center_id__in=candidates, time_basis='day', time_basis_quantity=1,
            ).select_related('product_type', 'uom', 'operation'))) if product_type else []
        facts = [capacity_fact(row, on_date, source_rules=source_rules) for row in capacities]
        available = [row for row, fact in zip(capacities, facts) if fact["available"]]
        duplicate_resource = any(n > 1 for n in Counter(r.work_center_id for r in available).values())
        if product_type is None: blockers.append("CAPACITY_PRODUCT_TYPE_MISSING")
        if not candidates: blockers.append("WORK_CENTER_CANDIDATE_MISSING")
        if not available: blockers.append("DAILY_CAPACITY_MISSING")
        if duplicate_resource: blockers.append("DAILY_CAPACITY_AMBIGUOUS")
        preparation = step.preparation_days
        transfer = step.transfer_days
        if preparation is None and len(available) == 1: preparation = available[0].preparation_days
        if transfer is None and len(available) == 1: transfer = available[0].transfer_days
        time_selection = {}
        if single_step:
            for name, field, selected in (('preparation', 'preparation_days', preparation),
                    ('transfer', 'transfer_days', transfer)):
                explicit = getattr(step, field)
                fallback = available[0] if explicit is None and len(available) == 1 else None
                time_selection[name] = {
                    'stepDays': str(explicit) if explicit is not None else None,
                    'standardCapacityDays': [{'standardCapacityId': cap.pk,
                        'days': str(getattr(cap, field)) if getattr(cap, field) is not None else None}
                        for cap in available],
                    'selectedDays': str(selected) if selected is not None else None,
                    'source': 'RoutingStep' if explicit is not None else 'StandardCapacity'
                        if fallback is not None and selected is not None else None,
                    'sourceId': step.pk if explicit is not None else fallback.pk
                        if fallback is not None and selected is not None else None,
                    'timeUnit': 'DAY'}
        if preparation is None: blockers.append("PREPARATION_DAYS_MISSING")
        if transfer is None: blockers.append("TRANSFER_DAYS_MISSING")
        if not any(candidates[row.work_center_id]["calendar"]["ready"] for row in available):
            blockers.append("MANUFACTURING_CALENDAR_MISSING")
        if applicability["result"] == NOT_APPLICABLE:
            blockers = [b for b in blockers if b in {"ROUTING_STEP_INACTIVE", "DEPENDENCY_REFERENCE_MISSING"}]
        counts.update(blockers)
        result.append({
            "stepId": step.pk, "sequence": step.sequence, "predecessorSequences": step.predecessor_sequences or [],
            "successorCount": successors[step.sequence], "operationId": operation.pk,
            "operationCode": operation.code, "operationName": operation.name, "applicability": applicability,
            "routingApplicability": routing_applicability, "capacityDateMode": date_mode,
            "sourceRulesFact": source_rules['fact'],
            "sourceRulesConflictLabel": source_conflict_label,
            "calculationBasis": operation.calculation_basis,
            "calculationUomId": operation.calculation_uom_id,
            "calculationUom": operation.calculation_uom.name if operation.calculation_uom_id else "",
            "quantityDriver": operation.quantity_driver or "", "workloadReady": False,
            "workloadStatusLabel": "本检查未验证计划工序需求量，须读取正式需求来源后计算日期",
            "dailyCapacity": facts, "capacities": facts, "candidateWorkCenters": list(candidates.values()), "equipment": [],
            "preparationDays": str(preparation) if preparation is not None else None,
            "transferDays": str(transfer) if transfer is not None else None,
            **({'timeSelection': time_selection} if single_step else {}),
            "timeUnit": "DAY", "timeUnitLabel": "天", "planningReady": not blockers,
            "capacityDemandEvaluated": applicability["result"] != NOT_APPLICABLE,
            "blockerCodes": blockers, "blockerLabels": [labels[x] for x in blockers],
        })
    for projected_step in result:
        if projected_step.get('capacitySemantics', {}).get('preparationRulingOnly'):
            # Keep the same validated selector result used by the formal
            # source reader; the original blank matrix is still traceable.
            continue
        projected_step['capacitySemantics'] = scoped_capacity_semantics(
            scope={'companyId': company_id, 'productTypeId': product_type.pk if product_type else None,
                'productTypeCode': product_type.code if product_type else None,
                'routingVersionId': routing_version.pk, 'routingStepId': projected_step['stepId'],
                'sequence': projected_step['sequence'], 'operationId': projected_step['operationId'],
                'operationName': projected_step['operationName']},
            applicability=projected_step['applicability'], source_rules=source_rules,
            capacity_facts=projected_step['dailyCapacity'],
            preparation_days=projected_step['preparationDays'], transfer_days=projected_step['transferDays'])
    blockers = [{"code": k, "label": labels[k], "affectedStepCount": n} for k,n in counts.items()]
    ready = bool(result) and not blockers
    surface = {
        "factSource": "server", "contractVersion": CONTRACT, "durationContract": CONTRACT,
        "sourceRulesFact": source_rules['fact'],
        "assessmentDate": on_date.isoformat(), "routingId": routing_version.routing_id,
        "routingVersionId": routing_version.pk, "routingVersionNo": routing_version.routing_version,
        "bomVersionId": bom_version.pk if bom_version else None,
        "bomVersionNo": bom_version.bom_version if bom_version else "", "productTypeId": product_type.pk if product_type else None,
        "planningReady": ready, "statusCode": "READY_FOR_PRODUCTION_PLANNING" if ready else "BLOCKED_MISSING_FORMAL_PLANNING_DATA",
        "statusLabel": "已具备日产能计划读取条件" if ready else "尚不具备日产能计划读取条件",
        "blockingSummary": "无阻断" if ready else "；".join(f"{r['label']}（{r['affectedStepCount']}步）" for r in blockers),
        "blockers": blockers, "requiredHumanInputCodes": list(counts),
        "requiredHumanInputLabel": "无" if not counts else "；".join(labels[k] for k in counts),
        "dependencyTopology": {"rootStepCount": sum(not s.predecessor_sequences for s in steps),
            "branchStepCount": sum(n > 1 for n in successors.values()),
            "mergeStepCount": sum(len(s.predecessor_sequences or []) > 1 for s in steps),
            "dependencyReferenceIntegrity": "DEPENDENCY_REFERENCE_MISSING" not in counts},
        "applicabilityContractVersion": APPLICABILITY_CONTRACT, "stepCount": len(result),
        "requiredStepCount": sum(r['applicability']['result'] == 'REQUIRED' for r in result),
        "auxiliaryStepCount": sum(r['capacityDateMode'] == AUXILIARY_DATE_MODE for r in result),
        "independentDateStepCount": sum(r['applicability']['result'] == 'REQUIRED'
            and r['capacityDateMode'] == 'INDEPENDENT_DATE' for r in result),
        "notApplicableStepCount": sum(r['applicability']['result'] == NOT_APPLICABLE for r in result),
        "pendingApplicabilityStepCount": sum(r['applicability']['result'] == PENDING for r in result),
        "readyStepCount": sum(r['planningReady'] for r in result), "steps": result,
        "productionPlanCreatedCount": 0, "productionScheduleCreatedCount": 0, "businessWriteCount": 0,
    }
    if single_step:
        for projected_step in result:
            projected_step['successorCount'] = None  # Outside the evaluated scope.
        surface.update(evaluationScope={'type': 'SINGLE_STEP', 'routingStepId': routing_step_id,
            'wholeRouteEvaluated': False}, scopeReady=ready, planningReady=False,
            statusCode='STEP_CAPACITY_FACTS_READY' if ready else 'STEP_CAPACITY_FACTS_BLOCKED',
            statusLabel='本步骤日产能资料已核对；整路线未评估' if ready else '本步骤日产能资料仍有阻断')
        surface['dependencyTopology']['branchStepCount'] = None
    return surface
