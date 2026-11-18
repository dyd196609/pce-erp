"""Versioned, server-only incremental facts over immutable engineering results.

All semantic selectors, arithmetic and units come from published rule data.
Existing engineering calculations are read, never executed or superseded.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from masterdata.models import CodeRule
from system.models import Company, OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state, record_projected_business_transition,
    transition_business_object,
)
from .engineering_rule_foundation import evaluate_specification, specification_hash, validate_specification
from .engineering_fact_metadata import (
    RESERVED_TRACE_KEYS, metadata_trace, resolve_metadata, validate_metadata_configuration,
)
from .manufacturing_configuration_service import CREATE, RELEASE, _create_released
from .models import (EngineeringCalculationRecord, EngineeringCalculationDetail,
    EngineeringDerivedFact, EngineeringFactInput, EngineeringRuleDefinition)
from .operation_requirement_service import (
    EXECUTE, _authorize, _executor, _fail, _digest, _key, _active, _unit, _source_output_proof, _read_once,
)
from .production_foundation_service import _audit, _snapshot

CONTRACT = 'PCE-ENGINEERING-FACT-EXTENSION-V1'
GROUP_IDENTITY_RESERVED_KEYS = RESERVED_TRACE_KEYS | frozenset((
    'sourceFactId', 'sourceCalculationId', 'sourceDetailId', 'sourceRecordId',
    'sourceRecordVersion', 'sourceRecordHash', 'sourceInputHash', 'sourceOutputProof',
    'sourcePath', 'factSource', 'metadataProof', 'inputName', 'normalization',
    'normalizedValue', 'uomId', 'value',
))


def _decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _fail('FACT_INPUT_INVALID', '输入事实必须为有限非负十进制数')
    if not result.is_finite() or result < 0:
        _fail('FACT_INPUT_INVALID', '输入事实必须为有限非负十进制数')
    return result


def _plan_unit(unit_id, company_id, units=None):
    """Reuse an accepted current unit row only within one plan invocation."""
    if units is None or type(unit_id) is not int or type(company_id) is not int:
        return _unit(unit_id, company_id)
    key = (company_id, unit_id)
    if key not in units:
        units[key] = _unit(unit_id, company_id)
    return units[key]


def _config(rule, units=None):
    spec = validate_specification(rule.specification)
    config = spec.get('factExtension')
    if (not isinstance(config, dict) or config.get('contractVersion') != CONTRACT
        or config.get('strategy') not in ('OBJECT_FORMULA', 'SCOPE_SUM', 'GROUP_SUM')
        or spec['outputs'][0]['resultDomain'] != 'DERIVED_FACT'):
        _fail('FACT_RULE_INVALID', '事实扩展必须使用版本化原生DERIVED_FACT规则合同')
    unit = _plan_unit(config.get('outputUomId'), rule.company_id, units)
    output = spec['outputs'][0]
    if output.get('unit') != unit.code or output.get('unitDimension') != unit.dimension:
        _fail('FACT_UOM_MISMATCH', '规则输出必须绑定正式计量单位与维度')
    if not isinstance(config.get('bindings'), list) or not config['bindings']:
        _fail('FACT_RULE_INVALID', '规则必须显式声明输入来源绑定')
    names = {row['canonicalName'] for row in spec['inputs']}
    if config['strategy'] == 'OBJECT_FORMULA' and {row.get('inputName') for row in config['bindings']} != names:
        _fail('FACT_RULE_INVALID', '对象公式必须为每个正式输入提供来源绑定')
    if config['strategy'] == 'SCOPE_SUM' and len(names) != 1:
        _fail('FACT_RULE_INVALID', '范围汇总仅接受一个正式AGGREGATED输入')
    if 'objectInputConditions' in config and config['strategy'] != 'GROUP_SUM':
        _fail('FACT_RULE_INVALID', '冻结对象来源条件只能显式用于分类汇总规则')
    if 'inheritGroupIdentity' in config:
        keys = config.get('groupKeys')
        metadata_bindings = config.get('metadataBindings')
        metadata_names = {row['name'] for row in (metadata_bindings if isinstance(metadata_bindings, list) else [])
                          if isinstance(row, dict) and isinstance(row.get('name'), str)}
        aliases = {config[name] for name in ('quantityTraceKey', 'uomTraceKey', 'inputHashTraceKey')
                   if isinstance(config.get(name), str)}
        if (type(config['inheritGroupIdentity']) is not bool or config['strategy'] != 'OBJECT_FORMULA'
                or not isinstance(keys, list) or not keys
                or any(not isinstance(key, str) or not key.strip() or key != key.strip() for key in keys)
                or len(keys) != len(set(keys))
                or set(keys) & (GROUP_IDENTITY_RESERVED_KEYS | metadata_names | aliases)):
            _fail('FACT_RULE_INVALID', '对象身份继承必须以布尔配置启用对象公式，并使用无重复且不覆盖正式证据的分组键')
    if config['strategy'] == 'GROUP_SUM':
        validate_metadata_configuration(config)
        if (len(names) != 1 or spec['inputs'][0].get('sourceType') != 'AGGREGATED'
                or spec['expression'].strip() != spec['inputs'][0]['canonicalName']
                or any(binding.get('sourceScope') != 'ORIGIN' for binding in config['bindings'])):
            _fail('FACT_RULE_INVALID', '分类汇总只能直接汇总一个原正式数值输入，不得混入比例或替代来源')
    for binding in config['bindings']:
        selector = binding.get('selector', {})
        if (binding.get('inputName') not in names or binding.get('sourceScope') not in ('ORIGIN', 'EXTENSION')
            or type(selector.get('producerRuleId')) is not int
            or not selector.get('producerRuleVersion') or not selector.get('canonicalField')
            or type(binding.get('sourceUomId')) is not int or type(binding.get('targetUomId')) is not int):
            _fail('FACT_RULE_INVALID', '来源必须声明范围、精确生产规则版本、字段及单位FK')
        producer = EngineeringRuleDefinition.objects.filter(pk=selector['producerRuleId'], company_id=rule.company_id).first()
        if not producer or producer.version != selector['producerRuleVersion'] or producer.status != 'released':
            _fail('FACT_RULE_NOT_RELEASED', '输入生产规则必须已发布且版本精确匹配')
        source_unit = _plan_unit(binding['sourceUomId'], rule.company_id, units)
        target_unit = _plan_unit(binding['targetUomId'], rule.company_id, units)
        declared = next(c for c in spec['inputs'] if c['canonicalName'] == binding['inputName'])
        dimension = declared.get('unitDimension')
        multiplier = (config['strategy'] == 'OBJECT_FORMULA' and target_unit.dimension == 'count'
                      and dimension == 'dimensionless')
        if (source_unit.dimension != target_unit.dimension or declared.get('unit') != target_unit.code
            or (dimension != target_unit.dimension and not multiplier)):
            _fail('FACT_UOM_MISMATCH', '输入算术单位和维度必须对应配置的正式单位；计数乘数需显式声明无量纲')
    return spec, config, unit


def _origin(pk, company_id):
    origin = EngineeringCalculationRecord.objects.select_related(
        'source_record', 'engineering_instance', 'sales_order_item__sales_order').filter(pk=pk, company_id=company_id).first()
    if not origin or origin.scope != 'order_engineering' or origin.status != 'completed':
        _fail('SOURCE_CALCULATION_MISSING', '必须指定同公司已完成的原正式工程核算')
    if not all((origin.source_record_id, origin.engineering_instance_id, origin.sales_order_item_id)):
        _fail('SOURCE_CALCULATION_CONTEXT_MISSING', '原核算必须保留正式来源、实例和订单行FK')
    if (origin.source_record.company_id != company_id or origin.source_record.status != 'confirmed'
        or origin.engineering_instance.company_id != company_id
        or origin.engineering_instance.source_record_id != origin.source_record_id
        or origin.engineering_instance.sales_order_item_id != origin.sales_order_item_id
        or origin.sales_order_item.sales_order.company_id != company_id):
        _fail('SOURCE_FACT_MISMATCH', '原工程核算正式FK血缘不一致')
    return origin


def _source_snapshot(fact, origin):
    detail = fact.source_detail
    if (fact.calculation_id != origin.pk or fact.status != 'active' or fact.source_type != 'ENGINEERING_DERIVED'
        or not detail or detail.status != 'succeeded' or detail.calculation_id != origin.pk
        or detail.uom_id != fact.uom_id or not isinstance(fact.value, dict)
        or not isinstance(detail.output_value, dict)):
        _fail('SOURCE_FACT_MISMATCH', '仅接受原核算中有成功明细的正式派生事实')
    proof = _source_output_proof(origin, fact, detail, origin.company_id)
    value = _decimal(fact.value.get('decimal'))
    if value != _decimal(detail.output_value.get('decimal')):
        _fail('SOURCE_FACT_MISMATCH', '来源事实与成功明细的数量不一致')
    return {'sourceFactId': fact.pk, 'sourceCalculationId': origin.pk, 'sourceDetailId': detail.pk,
        'canonicalField': fact.canonical_field, 'value': fact.value, 'uomId': fact.uom_id,
        'sourcePath': fact.source_path, 'sourceTrace': fact.trace, 'sourceOutputProof': proof,
        'sourceInputHash': _digest(detail.input_snapshot)}


def _matches(row, binding, category_id):
    selector = binding['selector']
    categories = binding.get('productCategoryIds')
    if categories and category_id not in categories:
        return False
    return (row['field'] == selector['canonicalField'] and row['producer'] == selector['producerRuleId']
        and row['version'] == selector['producerRuleVersion']
        and (not binding.get('selectByUom') or row['uomId'] == binding['sourceUomId'])
        and all(row['trace'].get(key) == value for key, value in selector.get('traceEquals', {}).items()))


def _normalized(row, binding, company_id, units=None):
    if row['uomId'] != binding['sourceUomId']:
        _fail('FACT_UOM_MISMATCH', '所选正式输入事实的单位不符合配置，不得静默遗漏')
    source = _plan_unit(row['uomId'], company_id, units)
    target = _plan_unit(binding['targetUomId'], company_id, units)
    if source.dimension != target.dimension:
        _fail('FACT_UOM_MISMATCH', '来源与规则目标单位的正式维度不一致')
    if source.pk == target.pk:
        factor = Decimal(1)
    elif source.conversion_base_id == target.pk and not target.conversion_base_id and target.conversion_factor == 1:
        factor = _decimal(source.conversion_factor)
        if factor == 0:
            _fail('FACT_UOM_MISMATCH', '正式单位换算系数必须大于零')
    else:
        _fail('FACT_UOM_MISMATCH', '没有明确正式单位换算关系，禁止猜测换算')
    contract = {'sourceUomId': source.pk, 'sourceDimension': source.dimension,
        'targetUomId': target.pk, 'targetDimension': target.dimension,
        'conversionBaseId': source.conversion_base_id, 'conversionFactor': str(source.conversion_factor),
        'appliedFactor': str(factor)}
    value = _decimal(row['value']) * factor
    return value, {'inputName': binding['inputName'], 'source': row['snapshot'],
        'normalization': contract, 'normalizedValue': str(value)}


def _plan(origin, rules):
    prior, units = set(), {}
    for rule in rules:
        _, config, _ = _config(rule, units)
        for binding in config['bindings']:
            if binding['sourceScope'] == 'EXTENSION' and binding['selector']['producerRuleId'] not in prior:
                _fail('FACT_DEPENDENCY_ORDER_INVALID', '增量输入生产规则必须在同一精确规则集合中先执行')
        prior.add(rule.pk)
    category = origin.engineering_instance.product_category_id
    facts = list(EngineeringDerivedFact.objects.filter(calculation=origin).select_related('source_detail__rule', 'uom'))
    originals = [{'field': f.canonical_field, 'producer': f.rule_id, 'version': f.source_detail.rule_version,
        'uomId': f.uom_id, 'value': f.value.get('decimal') if isinstance(f.value, dict) else None,
        'trace': f.trace, 'snapshot': _source_snapshot(f, origin)} for f in facts if f.source_detail_id]
    contexts, extensions = [], []
    classified = any(rule.specification.get('factExtension', {}).get('strategy') == 'GROUP_SUM' for rule in rules)
    conditioned = any('objectInputConditions' in rule.specification.get('factExtension', {}) for rule in rules)
    retained, metadata_cache = [], {}
    excluded = []
    by_fact = {fact.pk: fact for fact in facts}
    for rule in rules:
        if rule.company_id != origin.company_id or rule.status != 'released' or not _active(rule):
            _fail('FACT_RULE_NOT_RELEASED', '增量事实只允许同公司当前有效的已发布规则')
        spec, config, uom = _config(rule, units)
        if config.get('productCategoryIds') and category not in config['productCategoryIds']:
            continue
        selected = []
        for binding in config['bindings']:
            pool = originals if binding['sourceScope'] == 'ORIGIN' else extensions
            selected.append((binding, [row for row in pool if _matches(row, binding, category)]))
        groups = {}
        if config['strategy'] == 'OBJECT_FORMULA':
            keys = config.get('groupKeys')
            if not isinstance(keys, list) or not keys or config.get('anchorInput') not in {b['inputName'] for b, _ in selected}:
                _fail('FACT_RULE_INVALID', '对象公式必须配置正式分组键与数量锚点')
            anchor = next(rows for binding, rows in selected if binding['inputName'] == config['anchorInput'])
            for row in anchor:
                group = tuple(row['trace'].get(key) for key in keys)
                if any(value is None for value in group):
                    _fail('FACT_SOURCE_GROUP_MISSING', '输入事实缺少正式工程对象分组血缘')
                if config.get('inheritGroupIdentity') is True and any(
                        not ((type(value) is int and value > 0)
                             or (isinstance(value, str) and value.strip() and value == value.strip()))
                        for value in group):
                    _fail('FACT_SOURCE_GROUP_MISSING', '继承对象身份必须为正式正整数或精确非空文本')
                if group in groups:
                    _fail('FACT_INPUT_AMBIGUOUS', '同一正式对象存在重复输入事实')
                groups[group] = row
            if config.get('requirePositiveInputGroups'):
                for binding, rows in selected:
                    if binding['inputName'] == config['anchorInput']:
                        continue
                    for row in rows:
                        if _decimal(row['value']) > 0 and tuple(row['trace'].get(key) for key in keys) not in groups:
                            _fail('FACT_INPUT_MISSING', '有有效对象尺寸但缺少正式数量锚点，禁止遗漏对象')
            jobs = []
            for group in sorted(groups):
                pairs = []
                for binding, rows in selected:
                    matches = [row for row in rows if tuple(row['trace'].get(key) for key in keys) == group]
                    if len(matches) != 1:
                        _fail('FACT_INPUT_MISSING', '同一正式工程对象必须具备全部唯一输入事实')
                    pairs.append((binding, matches[0]))
                jobs.append((dict(zip(keys, group)), pairs))
        elif config['strategy'] == 'GROUP_SUM':
            pairs = [(binding, row) for binding, rows in selected for row in rows]
            source_keys = [row['snapshot']['sourceFactId'] for _, row in pairs]
            if len(source_keys) != len(set(source_keys)):
                _fail('FACT_INPUT_AMBIGUOUS', '分类汇总不得重复引用同一正式输入事实')
            grouped = {}
            for binding, row in pairs:
                resolved = resolve_metadata(origin=origin, fact=by_fact[row['snapshot']['sourceFactId']],
                    config=config, cache=metadata_cache)
                enriched = {**row, 'metadata': resolved['metadata'], 'metadataProof': resolved['proof']}
                if resolved.get('excluded') is True:
                    excluded.append({'ruleId': rule.pk, 'ruleVersion': rule.version,
                        'sourceFactId': row['snapshot']['sourceFactId'],
                        'sourceCalculationId': origin.pk, 'sourceDetailId': row['snapshot']['sourceDetailId'],
                        'value': row['snapshot']['value'], 'uomId': row['uomId'],
                        'reasonCode': 'OBJECT_INPUT_CONDITION_NOT_MATCHED',
                        'sourceSnapshot': row['snapshot'], 'metadataProof': resolved['proof']})
                    continue
                if resolved['missing']:
                    retained.append({'ruleId': rule.pk, 'ruleVersion': rule.version,
                        'sourceFactId': row['snapshot']['sourceFactId'],
                        'sourceCalculationId': origin.pk, 'sourceDetailId': row['snapshot']['sourceDetailId'],
                        'value': row['snapshot']['value'], 'uomId': row['uomId'],
                        'missingFields': resolved['missing'], 'sourceSnapshot': row['snapshot'],
                        'metadataProof': resolved['proof']})
                    continue
                group = {key: resolved['metadata'][key] for key in config['groupKeys']}
                group_key = _digest(group)
                grouped.setdefault(group_key, {'group': group, 'metadata': resolved['metadata'], 'pairs': []})
                saved = grouped[group_key]
                if saved['metadata'] != resolved['metadata']:
                    _fail('FACT_METADATA_AMBIGUOUS', '同一分类编码分组对应的正式元数据身份不一致')
                saved['pairs'].append((binding, enriched))
            jobs = [(row['group'], row['pairs']) for _, row in sorted(grouped.items())]
        else:
            pairs = [(binding, row) for binding, rows in selected for row in rows]
            source_keys = [str(row['snapshot'].get('sourceFactId', row['snapshot'].get('outputKey'))) for _, row in pairs]
            if len(source_keys) != len(set(source_keys)):
                _fail('FACT_INPUT_AMBIGUOUS', '汇总规则重复引用同一正式输入事实')
            if not pairs:
                _fail('FACT_INPUT_MISSING', '范围汇总必须具有正式面积输入')
            jobs = [({}, pairs)]
        for group, pairs in jobs:
            inputs, sources = {}, []
            for binding, row in pairs:
                value, snapshot = _normalized(row, binding, origin.company_id, units)
                if config['strategy'] == 'GROUP_SUM':
                    snapshot['metadata'] = deepcopy(row['metadata'])
                    snapshot['metadataProof'] = deepcopy(row['metadataProof'])
                sources.append(snapshot)
                name = binding['inputName']
                inputs[name] = inputs.get(name, Decimal(0)) + value
            input_contracts = {c['canonicalName']: c for c in spec['inputs']}
            values = {name: {'value': str(value), 'unit': input_contracts[name].get('unit'),
                'unitDimension': input_contracts[name].get('unitDimension')} for name, value in inputs.items()}
            result = evaluate_specification(spec, values)
            key = _digest({'ruleId': rule.pk, 'ruleVersion': rule.version, 'group': group})
            context = {'outputKey': key, 'ruleId': rule.pk, 'ruleVersion': rule.version,
                'specificationHash': specification_hash(spec), 'group': group,
                'inputs': values, 'sources': sources, 'result': result, 'uomId': uom.pk}
            if config['strategy'] == 'GROUP_SUM':
                context['metadata'] = deepcopy(pairs[0][1]['metadata'])
                context['inputHash'] = _digest({'inputs': values, 'sources': sources})
            contexts.append(context)
            extension_trace = {'contractVersion': CONTRACT}
            if config.get('inheritGroupIdentity') is True:
                extension_trace.update(deepcopy(group))
            if config['strategy'] == 'GROUP_SUM':
                extension_trace.update(metadata_trace(context, config, uom_code=uom.code))
            extensions.append({'field': result['canonicalName'], 'producer': rule.pk, 'version': rule.version,
                'uomId': uom.pk, 'value': result['value'], 'trace': extension_trace,
                'snapshot': {'outputKey': key, 'value': {'decimal': result['value']}, 'uomId': uom.pk,
                    'producerRuleId': rule.pk, 'producerRuleVersion': rule.version,
                    'specificationHash': specification_hash(spec)}})
    source = {'calculationId': origin.pk, 'inputHash': origin.input_hash, 'resultHash': origin.result_hash,
        'ruleGraphHash': origin.rule_graph_hash, 'sourceRecordId': origin.source_record_id,
        'sourceRecordVersion': origin.source_record.source_version, 'sourceRecordHash': origin.source_record.content_hash,
        'salesOrderItemId': origin.sales_order_item_id, 'engineeringInstanceId': origin.engineering_instance_id}
    graph = [{'id': r.pk, 'version': r.version, 'specificationHash': specification_hash(r.specification)} for r in rules]
    inputs = {'source': source, 'graph': graph, 'inputs': [c['sources'] for c in contexts]}
    results = contexts
    if classified:
        inputs['retainedMissingMetadata'] = retained
        results = {'contexts': contexts, 'retainedMissingMetadata': retained}
    if conditioned:
        inputs['excludedInputs'] = excluded
        results['excludedInputs'] = excluded
    plan = {'source': source, 'graph': graph, 'contexts': contexts,
        'inputHash': _digest(inputs), 'ruleGraphHash': _digest(graph), 'resultHash': _digest(results)}
    if classified:
        plan['retainedMissingMetadata'] = retained
    if conditioned:
        plan['excludedInputs'] = excluded
    return plan


def _audit_event(user, obj, before, after, decision, chain, reason):
    return _audit(user=user, organization_id=user.company_id, action_code=EXECUTE, instance=obj,
        before=before, after=after, reason=reason, authorization=decision, execution_chain=chain,
        audit_context={'contractVersion': CONTRACT})


def _initialize(user, obj, decision, chain, reason):
    audit = _audit_event(user, obj, {'status': ''}, _snapshot(obj), decision, chain, reason)
    record_projected_business_transition(object_type=type(obj).__name__, object_id=obj.pk, source_state='',
        target_state=obj.status, action_code=EXECUTE, operator=user, reason=reason,
        audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions=(('', obj.status),))


def _finish(user, obj, target, decision, chain, reason):
    audit = _audit_event(user, obj, _snapshot(obj), {**_snapshot(obj), 'status': target}, decision, chain, reason)
    transition_business_object(business_object=obj, object_type=type(obj).__name__, source_state=obj.status,
        target_state=target, action_code=EXECUTE, operator=user, reason=reason,
        audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions=((obj.status, target),),
        version_field=None, updated_at_field='updated_at' if hasattr(obj, 'updated_at') else None)
    return audit


def _history_cache(objects):
    """Load current history once for this validation call; never retain it."""
    by_type = {}
    for obj in objects:
        by_type.setdefault(type(obj).__name__, set()).add(obj.pk)
    scope = Q()
    for object_type, ids in by_type.items():
        scope |= Q(object_type=object_type, object_id__in=ids)
    histories, audit_ids = {}, set()
    for row in BusinessStateTransition.objects.filter(scope).order_by('object_type', 'object_id', 'version'):
        histories.setdefault((row.object_type, str(row.object_id)), []).append(row)
        reference = str(row.audit_reference)
        if reference.startswith('OrganizationOperatingAuditRecord:') and reference.split(':')[-1].isdigit():
            try:
                audit_ids.add(int(reference.split(':')[-1]))
            except ValueError:
                # The original per-row proof still rejects an invalid reference.
                continue
    audits = {row.pk: row for row in OrganizationOperatingAuditRecord.objects.filter(pk__in=audit_ids)}
    from django.contrib.auth import get_user_model
    actors = {row['id']: row for row in get_user_model().objects.filter(
        pk__in={audit.actor_id for audit in audits.values()}).values('id', 'username', 'company_id')}
    return {'histories': histories, 'audits': audits, 'actors': actors}


def _prove_history(obj, states, company_id, cache=None):
    if cache is None:
        rows = list(BusinessStateTransition.objects.filter(object_type=type(obj).__name__,
            object_id=str(obj.pk)).order_by('version'))
    else:
        rows = cache['histories'].get((type(obj).__name__, str(obj.pk)), [])
    if [(r.source_state, r.target_state) for r in rows] != list(states):
        _fail('FACT_EXTENSION_AUDIT_MISSING', '增量对象的完整状态链与正式执行合同不一致')
    actor_id = rows[0].operator_id
    for version, row in enumerate(rows, 1):
        reference = str(row.audit_reference)
        if (row.version != version or row.action_code != EXECUTE or row.operator_id != actor_id
            or not reference.startswith('OrganizationOperatingAuditRecord:') or not reference.split(':')[-1].isdigit()):
            _fail('FACT_EXTENSION_AUDIT_MISSING', '增量运行、明细或事实缺少匹配的正式状态历史与审计')
        if cache is None:
            audit = OrganizationOperatingAuditRecord.objects.filter(pk=reference.split(':')[-1],
                organization_id=company_id, target_type=type(obj).__name__, target_id=obj.pk,
                actor_id=actor_id, action_code=EXECUTE).first()
        else:
            if row.object_type != type(obj).__name__ or row.object_id != obj.pk:
                _fail('FACT_EXTENSION_AUDIT_MISSING', '局部读取的状态历史必须对应同一正式对象')
            audit = cache['audits'].get(int(reference.split(':')[-1]))
            if audit and (audit.organization_id != company_id or audit.target_type != type(obj).__name__
                    or audit.target_id != obj.pk or audit.actor_id != actor_id or audit.action_code != EXECUTE):
                audit = None
        if cache is None:
            from django.contrib.auth import get_user_model
            actor = get_user_model().objects.filter(pk=actor_id).values('username', 'company_id').first()
        else:
            actor = cache['actors'].get(actor_id)
        if (not audit or not actor or actor['company_id'] != company_id
            or audit.after_snapshot.get('state', {}).get('status') != row.target_state
            or audit.after_snapshot.get('authorization', {}).get('allowed') is not True
            or audit.after_snapshot.get('executionChain', {}).get('account') != actor['username']):
            _fail('FACT_EXTENSION_AUDIT_MISSING', '增量状态转换与真实审计不一致')
        if version == len(rows):
            saved = audit.after_snapshot['state']
            current = _snapshot(obj)
            if any(current[key] != saved.get(key) for key in current if key != 'updated_at'):
                from .historical_source_schema import CALC_ADDED, legacy_production_calculation
                legacy = (audit.after_snapshot.get('importContext', {}).get('contractVersion') == CONTRACT
                    and set(current) - set(saved) == CALC_ADDED
                    and not (set(saved) - set(current))
                    and legacy_production_calculation(obj, audit.created_at)
                    and all(value == saved[key] for key, value in current.items()
                        if key not in CALC_ADDED and key != 'updated_at'))
                if legacy:
                    continue
                _fail('FACT_EXTENSION_AUDIT_MISSING', '增量终态字段、追踪或计算时间与完成审计不一致')


def _saved_extension_plan(origin, base, rules, *, read_cache=None):
    """Verify the native saved result, never re-evaluate its producing rules."""
    plan = origin.trace.get('plan')
    if (not isinstance(plan, dict) or not isinstance(plan.get('source'), dict)
        or not isinstance(plan.get('graph'), list) or not isinstance(plan.get('contexts'), list)):
        _fail('FACT_EXTENSION_HASH_MISMATCH', '增量运行缺少完整冻结输入与输出计划')
    plan = deepcopy(plan)
    source = plan['source']
    expected_source = {'calculationId': base.pk, 'inputHash': base.input_hash, 'resultHash': base.result_hash,
        'ruleGraphHash': base.rule_graph_hash, 'sourceRecordId': base.source_record_id,
        'sourceRecordVersion': base.source_record.source_version, 'sourceRecordHash': base.source_record.content_hash,
        'salesOrderItemId': base.sales_order_item_id, 'engineeringInstanceId': base.engineering_instance_id}
    graph = [{'id': rule.pk, 'version': rule.version,
        'specificationHash': specification_hash(rule.specification)} for rule in rules]
    if (any(source.get(key) != value for key, value in expected_source.items())
        or any(rule.company_id != origin.company_id for rule in rules) or plan['graph'] != graph):
        _fail('FACT_EXTENSION_HASH_MISMATCH', '固定主核算、公司、规则版本或内部结果Hash不一致')
    inputs = {'source': source, 'graph': graph, 'inputs': [row['sources'] for row in plan['contexts']]}
    results = plan['contexts']
    if 'retainedMissingMetadata' in plan:
        inputs['retainedMissingMetadata'] = plan['retainedMissingMetadata']
        results = {'contexts': plan['contexts'], 'retainedMissingMetadata': plan['retainedMissingMetadata']}
    if 'excludedInputs' in plan:
        if not isinstance(results, dict):
            _fail('FACT_EXTENSION_HASH_MISMATCH', '冻结分类计划的保留或排除结构不一致')
        inputs['excludedInputs'] = plan['excludedInputs']
        results['excludedInputs'] = plan['excludedInputs']
    if (plan.get('inputHash') != _digest(inputs) or plan.get('ruleGraphHash') != _digest(graph)
        or plan.get('resultHash') != _digest(results) or origin.input_hash != plan['inputHash']
        or origin.rule_graph_hash != plan['ruleGraphHash'] or origin.result_hash != plan['resultHash']):
        _fail('FACT_EXTENSION_HASH_MISMATCH', '冻结输入、规则图与输出Hash不一致')
    # Preserve the original legacy envelope contract. Native object mains
    # additionally prove their pinned normalized input and baseline, without
    # invoking the import adapter or any classification/formula evaluator.
    if any(key in base.trace for key in ('baselineReference', 'objectInputSnapshot', 'workbookSource')):
        from .engineering_fact_metadata import _prepare_origin
        _prepare_origin(base, read_cache=read_cache)
    from .operation_requirement_service import _requirement_read_cache
    cache = _requirement_read_cache(read_cache, base.company_id)
    if cache is not None:
        from .engineering_calculation_continuation_service import _main_proof_rows
        source_rows, _, _ = _main_proof_rows(base, read_cache=cache)
    else:
        source_rows = base.derived_facts.select_related('source_detail__rule', 'uom')
    originals = {row.pk: _source_snapshot(row, base) for row in source_rows if row.source_detail_id}
    if (isinstance(base.trace.get('resultSnapshot'), list) and base.trace['resultSnapshot']
        and all(isinstance(row, dict) and 'unit' in row for row in base.trace['resultSnapshot'])):
        from .engineering_calculation_continuation_service import _main_proof
        _main_proof(base, read_cache=read_cache)
    by_key, units = {}, {}
    for expected in plan['contexts']:
        rule = next((rule for rule in rules if rule.pk == expected.get('ruleId')), None)
        spec = rule.specification if rule else {}
        config = spec.get('factExtension', {})
        unit = _plan_unit(expected.get('uomId'), origin.company_id, units)
        if (not rule or expected.get('ruleVersion') != rule.version
            or expected.get('specificationHash') != specification_hash(spec)
            or expected.get('outputKey') != _digest({'ruleId': rule.pk,
                'ruleVersion': rule.version, 'group': expected.get('group')})
            or config.get('outputUomId') != unit.pk
            or spec.get('outputs', [{}])[0].get('unit') != unit.code
            or spec.get('outputs', [{}])[0].get('unitDimension') != unit.dimension):
            _fail('FACT_EXTENSION_UNPROVEN', '冻结输出的规则、单位或对象身份不一致')
        for saved in expected['sources']:
            upstream = saved['source']
            if 'sourceFactId' in upstream:
                if originals.get(upstream['sourceFactId']) != upstream:
                    _fail('SOURCE_FACT_MISMATCH', '冻结输入与原主核算的真实事实、明细或单位不一致')
            elif by_key.get(upstream.get('outputKey')) != upstream:
                _fail('FACT_EXTENSION_UNPROVEN', '冻结上游增量输入身份、顺序或值不一致')
            normal = saved.get('normalization', {})
            binding = {'sourceUomId': normal.get('sourceUomId'),
                'targetUomId': normal.get('targetUomId'), 'inputName': saved.get('inputName')}
            _, checked = _normalized({'uomId': upstream.get('uomId'),
                'value': upstream.get('value', {}).get('decimal'), 'snapshot': upstream}, binding, origin.company_id, units)
            if any(saved.get(key) != checked[key] for key in checked):
                _fail('FACT_EXTENSION_HASH_MISMATCH', '冻结输入数量与正式单位换算、链接快照不一致')
        by_key[expected['outputKey']] = {'outputKey': expected['outputKey'],
            'value': {'decimal': expected['result']['value']}, 'uomId': unit.pk,
            'producerRuleId': rule.pk, 'producerRuleVersion': rule.version,
            'specificationHash': specification_hash(spec)}
    for retained in plan.get('retainedMissingMetadata', []) + plan.get('excludedInputs', []):
        upstream = retained.get('sourceSnapshot', {})
        if (originals.get(retained.get('sourceFactId')) != upstream
            or retained.get('value') != upstream.get('value') or retained.get('uomId') != upstream.get('uomId')):
            _fail('SOURCE_FACT_MISMATCH', '冻结保留或排除输入的真实来源、数量或单位不一致')
    return plan


def validate_extension_fact(origin, fact, *, read_cache=None):
    from .operation_requirement_service import _ReadOnlyProofCache
    if isinstance(read_cache, _ReadOnlyProofCache) and not read_cache.is_current(origin.company_id):
        read_cache = None
    if (origin.scope != 'fact_extension' or origin.status != 'completed' or not origin.origin_calculation_id
        or origin.trace.get('purpose') != CONTRACT or origin.supersedes_id):
        _fail('FACT_EXTENSION_UNPROVEN', '增量事实缺少独立已完成运行与正式原核算FK')
    base = _origin(origin.origin_calculation_id, origin.company_id)
    if any(getattr(origin, key) != getattr(base, key) for key in
        ('company_id', 'source_record_id', 'sales_order_item_id', 'engineering_instance_id')):
        _fail('FACT_EXTENSION_UNPROVEN', '增量事实与原核算正式FK不一致')
    ids = origin.trace.get('ruleIds', [])
    rules = list(EngineeringRuleDefinition.objects.filter(pk__in=ids))
    by_id = {r.pk: r for r in rules}
    if not ids or len(ids) != len(set(ids)) or any(pk not in by_id for pk in ids):
        _fail('FACT_EXTENSION_UNPROVEN', '增量事实规则版本集合不完整')
    # Only the expensive pure proof reconstruction is reused inside a caller's
    # read transaction. The first complete proof checks every output/member/
    # value/trace/link/history below. Writers retain their original behavior.
    plan_key = ('extension_plan', origin.company_id, origin.pk, origin.input_hash,
        origin.result_hash, origin.rule_graph_hash, base.pk, base.input_hash,
        base.result_hash, base.rule_graph_hash, base.source_record_id, base.sales_order_item_id,
        base.engineering_instance_id, base.source_record.status, base.source_record.source_version,
        base.source_record.content_hash, tuple((by_id[pk].pk, by_id[pk].version,
            by_id[pk].status, by_id[pk].effective_from, by_id[pk].effective_to,
            specification_hash(by_id[pk].specification)) for pk in ids))
    # Only a public, atomic pure read may reuse a complete calculation proof.
    # It proves every output/link/history once, and retains each member's exact
    # snapshot. Plain dictionaries (including writers) retain the old checks.
    complete_cache = read_cache if (isinstance(read_cache, _ReadOnlyProofCache)
        and read_cache.is_current(origin.company_id)) else None
    complete_key = ('complete_extension_read', plan_key, _digest(origin.trace),
        origin.source_record_id, origin.sales_order_item_id, origin.engineering_instance_id)
    if complete_cache is not None and complete_key in complete_cache:
        proved = complete_cache[complete_key]
        if proved['members'].get(fact.pk) == _digest(_snapshot(fact)):
            return dict(proved['proof'])
    outputs = list(origin.derived_facts.select_related('source_detail__rule', 'uom').prefetch_related(
        Prefetch('inputs', queryset=EngineeringFactInput.objects.order_by('sequence'), to_attr='_proof_inputs')
    ).order_by('sequence'))
    history = _history_cache([origin, *outputs, *[row.source_detail for row in outputs if row.source_detail]])
    _prove_history(origin, (('', 'running'), ('running', 'completed')), origin.company_id, cache=history)
    plan = _read_once(read_cache, plan_key, lambda: _saved_extension_plan(origin, base,
        [by_id[pk] for pk in ids], read_cache=read_cache))
    if len(outputs) != len(plan['contexts']) or fact.pk not in {f.pk for f in outputs}:
        _fail('FACT_EXTENSION_UNPROVEN', '增量事实集合与真实计算输出不一致')
    by_key = {f.trace.get('outputKey'): f for f in outputs}
    for expected, saved in zip(plan['contexts'], outputs):
        detail = saved.source_detail
        if (saved.rule_id != expected['ruleId'] or saved.canonical_field != expected['result']['canonicalName']
            or saved.status != 'active' or saved.source_type != 'ENGINEERING_DERIVED'
            or saved.value != {'decimal': expected['result']['value']} or saved.uom_id != expected['uomId']
            or not detail or detail.status != 'succeeded' or detail.calculation_id != origin.pk
            or detail.rule_id != expected['ruleId'] or detail.rule_version != expected['ruleVersion']
            or detail.expression_snapshot != detail.rule.specification['expression']
            or detail.input_snapshot != {'inputs': expected['inputs'], 'sources': expected['sources']}
            or detail.dependency_snapshot != expected['sources'] or detail.output_value != saved.value
            or detail.uom_id != saved.uom_id or saved.trace.get('outputKey') != expected['outputKey']
            or detail.output_name != saved.canonical_field or saved.value_type != 'decimal'
            or saved.trace.get('contractVersion') != CONTRACT or saved.trace.get('detailId') != detail.pk
            or saved.trace.get('ruleCode') != detail.rule_code or saved.trace.get('ruleVersion') != detail.rule_version
            or saved.trace.get('specificationHash') != expected['specificationHash']
            or saved.trace.get('group') != expected['group'] or saved.trace.get('baseEngineeringCalculationId') != base.pk
            or saved.trace.get('outputHash') != _digest(expected)):
            _fail('FACT_EXTENSION_UNPROVEN', '增量事实或成功明细与原生冻结输入输出证明不一致')
        if 'metadata' in expected:
            from .manufacturing_rule_configuration import _trace_matches
            config = detail.rule.specification['factExtension']
            trace_values = metadata_trace(expected, config, uom_code=saved.uom.code)
            if not _trace_matches(saved.trace, trace_values):
                _fail('FACT_EXTENSION_UNPROVEN', '分类元数据、数量、单位别名或输入Hash与正式来源证明不一致')
        links = saved._proof_inputs
        if len(links) != len(expected['sources']):
            _fail('FACT_EXTENSION_UNPROVEN', '正式输入来源FK集合不完整')
        for snapshot, link in zip(expected['sources'], links):
            source = snapshot['source']
            upstream_id = source.get('sourceFactId')
            if upstream_id is None:
                upstream = by_key.get(source.get('outputKey'))
                upstream_id = upstream.pk if upstream else None
            if (link.source_fact_id != upstream_id or link.input_name != snapshot['inputName']
                or link.input_snapshot != snapshot or link.source_hash != _digest(snapshot)):
                _fail('FACT_EXTENSION_UNPROVEN', '正式输入来源FK与不可变快照、Hash不一致')
        _prove_history(saved, (('', 'active'),), origin.company_id, cache=history)
        _prove_history(detail, (('', 'running'), ('running', 'succeeded')), origin.company_id, cache=history)
    proof = {'contractVersion': CONTRACT, 'baseEngineeringCalculationId': base.pk,
        'originInputHash': base.input_hash, 'originResultHash': base.result_hash,
        'inputHash': origin.input_hash, 'resultHash': origin.result_hash,
        'sourceRecordId': base.source_record_id, 'sourceRecordVersion': plan['source']['sourceRecordVersion']}
    if complete_cache is not None:
        complete_cache[complete_key] = {'proof': dict(proof),
            'members': {row.pk: _digest(_snapshot(row)) for row in outputs}}
    return proof


class EngineeringFactExtensionService:
    @classmethod
    def preview(cls, *, user, source_calculation_id, rule_ids):
        from .operation_requirement_service import VIEW
        _authorize(user, VIEW)
        origin = _origin(source_calculation_id, user.company_id)
        if (not isinstance(rule_ids, list) or not rule_ids
                or any(type(pk) is not int or pk <= 0 for pk in rule_ids)
                or len(rule_ids) != len(set(rule_ids))):
            _fail('FACT_RULE_NOT_RELEASED', '必须选择完整精确的发布规则集合')
        by_id = {rule.pk: rule for rule in EngineeringRuleDefinition.objects.filter(pk__in=rule_ids)}
        if any(pk not in by_id for pk in rule_ids):
            _fail('FACT_RULE_NOT_RELEASED', '必须选择完整精确的发布规则集合')
        plan = _plan(origin, [by_id[pk] for pk in rule_ids])
        result = {'contractVersion': CONTRACT, 'factSource': 'server',
            'sourceCalculationId': origin.pk, 'plan': plan, 'groupCount': len(plan['contexts']),
            'retainedMissingMetadata': plan.get('retainedMissingMetadata', []),
            'businessWriteCount': 0, 'auditWriteCount': 0}
        if 'retainedMissingMetadata' in plan:
            result['retainedMissingMetadata'] = plan['retainedMissingMetadata']
        if 'excludedInputs' in plan:
            result['excludedInputs'] = plan['excludedInputs']
        return result

    @classmethod
    @transaction.atomic
    def configure(cls, *, user, package, reason):
        if package.get('contractVersion') != CONTRACT or package.get('companyId') != user.company_id or not reason:
            _fail('FACT_PACKAGE_INVALID', '事实配置包必须提供正式合同、公司及办理原因')
        decisions = {p: _authorize(user, p) for p in (CREATE, RELEASE)}
        chain = _executor(user)
        Company.objects.select_for_update().get(pk=user.company_id)
        ids = []
        for row in package['rules']:
            spec = deepcopy(row['specification'])
            for binding in spec['factExtension']['bindings']:
                selector = binding['selector']
                code = selector.pop('producerRuleCode', None)
                if code:
                    producer = EngineeringRuleDefinition.objects.filter(company_id=user.company_id,
                        rule_code=code, version=selector['producerRuleVersion'], status='released').first()
                    if not producer:
                        _fail('FACT_RULE_NOT_RELEASED', '配置引用的精确生产规则版本未发布')
                    selector['producerRuleId'] = producer.pk
            fields = dict(company_id=user.company_id, rule_code=row['ruleCode'], rule_name=row['ruleName'],
                version=row['version'], rule_kind='formula', specification=spec)
            candidate = EngineeringRuleDefinition(**fields)
            _config(candidate)
            saved = EngineeringRuleDefinition.objects.filter(company_id=user.company_id,
                rule_code=row['ruleCode'], version=row['version']).first()
            if saved:
                if saved.status != 'released' or any(getattr(saved, key) != value for key, value in fields.items()):
                    _fail('FACT_RULE_VERSION_CONFLICT', '已有规则版本禁止覆盖；必须建立新版本')
            else:
                saved = _create_released(EngineeringRuleDefinition, fields, user=user, decisions=decisions,
                    chain=chain, reason=reason, package_hash=_digest(package))
            ids.append(saved.pk)
        return {'contractVersion': CONTRACT, 'ruleIds': ids, 'factSource': 'server'}

    @classmethod
    @transaction.atomic
    def derive(cls, *, user, source_calculation_id, rule_ids, idempotency_key, reason):
        decision, chain = _authorize(user, EXECUTE), _executor(user)
        request_key = _key(idempotency_key)
        if not str(reason).strip():
            _fail('REASON_REQUIRED', '事实补充必须填写办理原因')
        Company.objects.select_for_update().get(pk=user.company_id)
        origin = _origin(source_calculation_id, user.company_id)
        by_id = {r.pk: r for r in EngineeringRuleDefinition.objects.filter(pk__in=rule_ids)}
        if not rule_ids or len(rule_ids) != len(set(rule_ids)) or any(pk not in by_id for pk in rule_ids):
            _fail('FACT_RULE_NOT_RELEASED', '必须选择完整精确的发布规则集合')
        plan = _plan(origin, [by_id[pk] for pk in rule_ids])
        if not plan['contexts']:
            if plan.get('retainedMissingMetadata') or plan.get('excludedInputs'):
                result = {'contractVersion': CONTRACT, 'calculationId': None, 'factIds': [],
                    'idempotent': False, 'businessWriteCount': 0, 'auditWriteCount': 0,
                    'factSource': 'server', 'retainedMissingMetadata': plan['retainedMissingMetadata'],
                    'inputHash': plan['inputHash'], 'resultHash': plan['resultHash']}
                if 'excludedInputs' in plan:
                    result['excludedInputs'] = plan['excludedInputs']
                return result
            _fail('FACT_INPUT_MISSING', '没有符合正式规则的输入事实')
        semantic_key = _digest({'contract': CONTRACT, 'inputHash': plan['inputHash']})
        bound = EngineeringCalculationRecord.objects.filter(company_id=user.company_id, scope='fact_extension',
            trace__clientRequestKey=request_key).first()
        if bound and bound.idempotency_key != semantic_key:
            _fail('IDEMPOTENCY_CONFLICT', '幂等键已绑定其他正式来源或规则输入')
        alias = OrganizationOperatingAuditRecord.objects.filter(organization_id=user.company_id,
            target_type='EngineeringCalculationRecord', action_code=EXECUTE,
            after_snapshot__state__requestBinding__requestKey=request_key).first()
        if alias and alias.after_snapshot['state']['requestBinding'].get('inputHash') != plan['inputHash']:
            _fail('IDEMPOTENCY_CONFLICT', '幂等别名已绑定其他正式输入')
        existing = EngineeringCalculationRecord.objects.filter(company_id=user.company_id, idempotency_key=semantic_key).first()
        if existing:
            facts = list(existing.derived_facts.order_by('sequence'))
            validate_extension_fact(existing, facts[-1])
            alias_writes = 0
            if not bound and not alias:
                _audit_event(user, existing, {}, {'idempotentReplay': True,
                    'requestBinding': {'requestKey': request_key, 'inputHash': plan['inputHash']}},
                    decision, chain, reason)
                alias_writes = 1
            replay = {'calculationId': existing.pk, 'factIds': [f.pk for f in facts], 'idempotent': True,
                'businessWriteCount': 0, 'auditWriteCount': alias_writes}
            if 'retainedMissingMetadata' in plan:
                replay['retainedMissingMetadata'] = plan['retainedMissingMetadata']
            if 'excludedInputs' in plan:
                replay['excludedInputs'] = plan['excludedInputs']
            return replay
        code = CodeRule.next_code(entity_type='production_engineering_calculation', company_id=user.company_id)
        started = timezone.now()
        calc = create_business_object_with_initial_state(model=EngineeringCalculationRecord, initial_state='running',
            company_id=user.company_id, scope='fact_extension', origin_calculation=origin,
            source_record=origin.source_record, sales_order_item=origin.sales_order_item,
            engineering_instance=origin.engineering_instance, calculation_no=code,
            rule_set_version=CONTRACT, revision=1, idempotency_key=semantic_key,
            input_hash=plan['inputHash'], rule_graph_hash=plan['ruleGraphHash'], started_at=started,
            trace={'purpose': CONTRACT, 'ruleIds': rule_ids, 'plan': plan, 'clientRequestKey': request_key, 'factSource': 'server'})
        _initialize(user, calc, decision, chain, reason)
        outputs = {}
        for sequence, context in enumerate(plan['contexts'], 1):
            rule = by_id[context['ruleId']]
            detail = create_business_object_with_initial_state(model=EngineeringCalculationDetail, initial_state='running',
                calculation=calc, sequence=sequence, rule=rule, rule_code=rule.rule_code, rule_version=rule.version,
                expression_snapshot=rule.specification['expression'],
                input_snapshot={'inputs': context['inputs'], 'sources': context['sources']},
                dependency_snapshot=context['sources'], output_name=context['result']['canonicalName'],
                output_value={'decimal': context['result']['value']}, uom_id=context['uomId'],
                precision=rule.specification['decimalPrecision'], rounding=rule.specification['roundingMode'],
                started_at=started, finished_at=timezone.now())
            _initialize(user, detail, decision, chain, reason)
            _finish(user, detail, 'succeeded', decision, chain, reason)
            fact_trace = {'contractVersion': CONTRACT, 'resultDomain': 'DERIVED_FACT', 'detailId': detail.pk,
                'ruleCode': rule.rule_code, 'ruleVersion': rule.version, 'specificationHash': context['specificationHash'],
                'outputKey': context['outputKey'], 'outputHash': _digest(context),
                'baseEngineeringCalculationId': origin.pk, 'group': context['group'], 'calculatedAt': timezone.now().isoformat()}
            if 'metadata' in context:
                fact_trace.update(metadata_trace(context, rule.specification['factExtension'], uom_code=detail.uom.code))
            fact = create_business_object_with_initial_state(model=EngineeringDerivedFact, initial_state='active',
                calculation=calc, source_detail=detail, rule=rule,
                fact_code=context['result']['canonicalName'], canonical_field=context['result']['canonicalName'],
                sequence=sequence, value=detail.output_value, value_type='decimal', uom_id=context['uomId'],
                source_path=f'EngineeringCalculationDetail:{detail.pk}.output_value',
                trace=fact_trace)
            for index, snapshot in enumerate(context['sources'], 1):
                upstream_id = snapshot['source'].get('sourceFactId')
                upstream = EngineeringDerivedFact.objects.get(pk=upstream_id) if upstream_id else outputs[snapshot['source']['outputKey']]
                link = EngineeringFactInput(fact=fact, source_fact=upstream, input_name=snapshot['inputName'], sequence=index,
                    source_hash=_digest(snapshot), input_snapshot=snapshot)
                link.full_clean()
                link.save()
            _initialize(user, fact, decision, chain, reason)
            outputs[context['outputKey']] = fact
        calc.result_hash, calc.finished_at = plan['resultHash'], timezone.now()
        calc.save(update_fields=['result_hash', 'finished_at', 'updated_at'])
        _finish(user, calc, 'completed', decision, chain, reason)
        facts = list(outputs.values())
        validate_extension_fact(calc, facts[-1])
        result = {'contractVersion': CONTRACT, 'calculationId': calc.pk, 'factIds': [f.pk for f in facts],
            'idempotent': False, 'businessWriteCount': 1 + len(facts) * 2 + sum(len(c['sources']) for c in plan['contexts']),
            'auditWriteCount': 2 + len(facts) * 3, 'factSource': 'server'}
        if 'retainedMissingMetadata' in plan:
            result['retainedMissingMetadata'] = plan['retainedMissingMetadata']
        if 'excludedInputs' in plan:
            result['excludedInputs'] = plan['excludedInputs']
        return result
