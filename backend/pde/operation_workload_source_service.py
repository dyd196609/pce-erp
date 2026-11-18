from pde.baseline_usage_service import production_baselines
"""Operation source configuration over the existing, versioned EOR rule authority.

The metadata projection never evaluates rules or validates an order's sources.
The selected-plan reader uses the existing native proofs, without generation,
allocation, dates or duration.  A source fact is not an EOR or a saved load.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.db.models import F

from masterdata.models import UnitOfMeasure
from planning.models import ProductionPlan
from system.authorization import AuthorizationService
from system.models import Company, Process

from .engineering_rule_foundation import (EngineeringRuleError, canonical_json, specification_hash,
    validate_specification, evaluate_specification)
from .manufacturing_configuration_service import CREATE, RELEASE, ManufacturingConfigurationService
from .manufacturing_rule_configuration import CONTRACT as MANUFACTURING_CONTRACT, _configuration
from .models import (CapacityProductType, EngineeringDerivedFact, EngineeringOperationRequirement,
    EngineeringRuleDefinition, ManufacturingMode, OrderEngineeringBaselineItem,
    ProductionPlanOperationRequirementAllocation, Routing, RoutingStep, RoutingStepObjectApplicability,
    RoutingVersion, StandardCapacity, WorkCenter,
    WorkCenterOperationCapability)
from .production_foundation_service import ProductionFoundationError, _actor_chain
from . import operation_requirement_service as native
from . import engineering_rule_foundation as rule_foundation
from .operation_read_diagnostics import read_span
from .operation_non_quantified_context import (
    REFERENCE_TYPE, STANDARD_CAPACITY, plan_preparation,
)
from .plan_step_context_service import (
    effective_calculation, effective_baseline, source_selection,
)

CONTRACT = 'PCE-OPERATION-WORKLOAD-SOURCE-V1'
RULE_VIEW = 'production.engineering.rule.view'
SOURCE_SELECTION_CONTRACT = 'PCE-OPERATION-SOURCE-SELECTION-V1'
_SCHEME_BATCH_KEY = object()


def read_for_arrangement(*, user, arrangement_id, baseline_item_id=None,
                         expected_edit_version=None, expected_read_hash=None):
    """Read current order choices and exact sources without a plan/output writer."""
    from .order_execution_workload_read_service import read_arrangement_workload
    return read_arrangement_workload(user=user, arrangement_id=arrangement_id,
        baseline_item_id=baseline_item_id, expected_edit_version=expected_edit_version,
        expected_read_hash=expected_read_hash)


class OperationWorkloadSourceError(ProductionFoundationError):
    pass


def _fail(code, message, **details):
    raise OperationWorkloadSourceError(code, message, details)


def _id(value, name):
    if type(value) is not int or value <= 0:
        _fail('WORKLOAD_SOURCE_ID_INVALID', f'{name}必须是明确的正式正整数ID')
    return value


def _authorize(user, permission):
    try:
        return native._authorize(user, permission)
    except native.OperationRequirementError as error:
        raise OperationWorkloadSourceError(error.code, error.message, error.details) from error


def _reason(error):
    return {'code': getattr(error, 'code', 'WORKLOAD_SOURCE_INVALID'),
        'statusLabel': getattr(error, 'message', '正式作业量来源校验失败')}


def _get(row, key, default=None):
    return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)


def _operation_id(row):
    return _get(row, 'id', _get(row, 'pk'))


def _rules(company_id):
    """One metadata query per projection; no per-operation source proof."""
    return list(EngineeringRuleDefinition.objects.filter(company_id=company_id,
        status='released').order_by('pk'))


def _references(rules, operations, company_id):
    ids = {key: set() for key in ('producer', 'mode', 'kind', 'center', 'capacity', 'unit', 'route', 'version', 'step')}
    for operation in operations:
        if type(_get(operation, 'calculation_uom_id')) is int:
            ids['unit'].add(_get(operation, 'calculation_uom_id'))
    for rule in rules:
        spec = rule.specification if isinstance(rule.specification, dict) else {}
        outputs = spec.get('outputs', [])
        output = outputs[0] if isinstance(outputs, list) and len(outputs) == 1 and isinstance(outputs[0], dict) else {}
        config = spec.get('manufacturing') if isinstance(spec.get('manufacturing'), dict) else {}
        selector = config.get('sourceSelector') if isinstance(config.get('sourceSelector'), dict) else {}
        routing = config.get('routingContext') if isinstance(config.get('routingContext'), dict) else {}
        for key, value in [('producer', selector.get('producerRuleId')), ('mode', config.get('modeId')),
                ('kind', output.get('productTypeId')), ('center', config.get('workCenterId')),
                ('capacity', config.get('standardCapacityId')), ('unit', output.get('uomId')),
                ('unit', output.get('basisUomId')), ('route', routing.get('routingId')),
                ('version', routing.get('routingVersionId')), ('step', routing.get('routingStepId'))]:
            if type(value) is int and value > 0:
                ids[key].add(value)
    models = {'producer': EngineeringRuleDefinition, 'mode': ManufacturingMode, 'kind': CapacityProductType,
        'center': WorkCenter, 'capacity': StandardCapacity, 'unit': UnitOfMeasure}
    references = {}
    for key, model in models.items():
        rows = model.objects.filter(company_id=company_id, pk__in=ids[key])
        if key == 'kind':
            rows = rows.select_related('product_category', 'manufacturing_process_type')
        elif key == 'center':
            rows = rows.select_related('workshop')
        references[key] = {row.pk: row for row in rows}
    references['companyActive'] = Company.objects.filter(pk=company_id, is_active=True).exists()
    references['capabilities'] = {(row.operation_id, row.work_center_id): row
        for row in WorkCenterOperationCapability.objects.filter(operation_id__in={_operation_id(row) for row in operations},
            work_center_id__in=ids['center'], operation__company_id=company_id, work_center__company_id=company_id)}
    references['route'] = {row.pk: row for row in Routing.objects.filter(pk__in=ids['route'], company_id=company_id)}
    references['version'] = {row.pk: row for row in RoutingVersion.objects.filter(pk__in=ids['version'], routing__company_id=company_id)}
    references['step'] = {row.pk: row for row in RoutingStep.objects.filter(pk__in=ids['step'], routing_version__routing__company_id=company_id)}
    return references


def _capacity_metadata(capacity, kind, operation_id, refs):
    """Publication's current quantity/day metadata, without an order proof."""
    if (not capacity.effective_from or capacity.time_basis != 'day'
            or capacity.time_basis_quantity != Decimal(1) or capacity.time_unit != 'DAY'):
        _fail('MANUFACTURING_CAPACITY_INVALID', '正式产能必须具有生效日及精确的数量/天基准')
    try:
        quantity = Decimal(str(capacity.quantity))
    except (InvalidOperation, ValueError, TypeError):
        _fail('MANUFACTURING_CAPACITY_INVALID', '正式产能数量缺失或不是有效十进制数')
    measured = capacity.measurement_status == 'measured' and quantity.is_finite() and quantity > 0
    auxiliary = capacity.measurement_status == 'zero_capacity' and quantity.is_finite() and quantity == 0
    if not measured and not auxiliary:
        _fail('MANUFACTURING_CAPACITY_INVALID', '正式产能必须为已测正日产能或有正式佐证的配套零产能')
    conditions = capacity.conditions if isinstance(capacity.conditions, dict) else {}
    if auxiliary or 'apsSourceRules' in conditions:
        from .daily_capacity_service import capacity_source_rules
        proofs = refs.setdefault('capacitySourceRules', {})
        if kind.pk not in proofs:
            proofs[kind.pk] = capacity_source_rules(kind, company_id=kind.company_id, on_date=native._today())
        proof = proofs[kind.pk]
        is_auxiliary = operation_id in proof.get('manifest', {}).get('auxiliaryOperationIds', [])
        if (proof.get('status') != 'VALID' or is_auxiliary != auxiliary
                or capacity.pk not in {row.pk for row in proof.get('capacityRows', [])}):
            _fail('MANUFACTURING_CAPACITY_INVALID', '产能计量状态与原生工序适用来源规则不一致')


def _routing_metadata(config, operation_id, center, spec, refs):
    declared = config.get('routingContext')
    if declared is None:
        return
    route = refs['route'].get(declared['routingId'])
    version = refs['version'].get(declared['routingVersionId'])
    step = refs['step'].get(declared['routingStepId'])
    today = native._today()
    if (not native._active(route) or route.status != 'released' or not version or version.status != 'released'
            or version.routing_id != route.pk or (version.effective_date and version.effective_date > today)
            or (version.expire_date and version.expire_date < today) or not native._active(step)
            or step.routing_version_id != version.pk or step.operation_id != operation_id):
        _fail('MANUFACTURING_ROUTING_REFERENCE_INVALID', '规则指定的正式路线、当前版本和步骤工序不一致')
    if ((step.work_center_id and step.work_center_id != center.pk)
            or (step.workshop_id and step.workshop_id != center.workshop_id)):
        _fail('MANUFACTURING_ROUTING_RESOURCE_MISMATCH', '规则指定的路线步骤资源与正式工作中心不一致')
    evidence = spec.get('sourceEvidence', {}).get('formalRouting')
    if evidence is not None and (not isinstance(evidence, dict) or any(evidence.get(key) != value
            for key, value in {'routingId': route.pk, 'routingCode': route.routing_code,
                'routingVersionId': version.pk, 'routingVersion': version.routing_version,
                'routingStepId': step.pk, 'sequence': step.sequence, 'operationId': operation_id}.items())):
        _fail('MANUFACTURING_ROUTING_EVIDENCE_MISMATCH', '规则路线出处与当前正式路线、版本及步骤字段不一致')


def _evaluation_semantics_hash(specification):
    """Compare the complete evaluation contract before hiding any fallback.

    Only documentary evidence, package version and the exact routing scope
    may differ. Precision, scale, rounding, inputs, outputs, dependencies and
    every other semantic field remain part of this conservative signature.
    """
    semantic = deepcopy(specification)
    semantic.pop('sourceEvidence', None)
    if isinstance(semantic.get('rulePackage'), dict):
        semantic['rulePackage'].pop('version', None)
    if isinstance(semantic.get('manufacturing'), dict):
        semantic['manufacturing'].pop('routingContext', None)
    return specification_hash(semantic)


def _summary(rule, operation, refs):
    spec = validate_specification(rule.specification)
    output, inputs = spec['outputs'][0], spec['inputs']
    if (output.get('resultDomain') != 'OPERATION_REQUIREMENT'
            or output.get('operationId') != _operation_id(operation) or len(inputs) != 1
            or inputs[0].get('sourceType') != 'ENGINEERING_DERIVED'
            or output.get('quantityBasis') not in native.KNOWN_BASES
            or output.get('sourceScope') != 'SALES_ORDER_ITEM'):
        _fail('OPERATION_RULE_MAPPING_MISSING', '发布规则没有明确的原生工序、来源及数量范围合同')
    kind = refs['kind'].get(output.get('productTypeId'))
    unit = refs['unit'].get(_get(operation, 'calculation_uom_id'))
    if (not refs['companyActive'] or not native._active(kind) or not native._active(unit)
            or not native._active(kind.product_category) or not native._active(kind.manufacturing_process_type)
            or kind.product_category.company_id != rule.company_id
            or kind.manufacturing_process_type.company_id != rule.company_id):
        _fail('WORKLOAD_SOURCE_REFERENCE_INVALID', '工序规则的正式产品类型或计量单位无效')
    if not native._unit_token(unit, output.get('unit')) or output.get('uomId', unit.pk) != unit.pk:
        _fail('OPERATION_UOM_MISMATCH', '发布规则输出与工序核算单位不一致')
    canonical = inputs[0].get('sourceCanonicalField', inputs[0]['canonicalName'])
    dynamic_basis = (isinstance(spec.get('manufacturing'), dict)
        and spec['manufacturing'].get('contractVersion') == MANUFACTURING_CONTRACT
        and output.get('basisQuantitySource') == 'SALES_ORDER_ITEM')
    if dynamic_basis:
        if (output['quantityBasis'] != 'SOURCE_SCOPE_TOTAL' or 'basisQuantity' in output
                or output.get('basisUomSource') != 'SALES_ORDER_ITEM' or 'basisUomId' in output):
            _fail('QUANTITY_BASIS_MISMATCH', '动态来源总量必须使用订单行正式数量及单位，不能混入固定基数')
    else:
        native._number(output.get('basisQuantity'), 'QUANTITY_BASIS_MISSING')
        if not native._active(refs['unit'].get(output.get('basisUomId'))):
            _fail('QUANTITY_BASIS_MISSING', '原规则缺少正式有效基准单位')
    evidence = spec.get('sourceEvidence') if isinstance(spec.get('sourceEvidence'), dict) else {}
    summary = {'ruleId': rule.pk, 'ruleCode': rule.rule_code, 'ruleName': rule.rule_name,
        'ruleVersion': rule.version, 'specificationHash': specification_hash(spec),
        'evaluationSemanticsHash': _evaluation_semantics_hash(spec),
        'operationId': _operation_id(operation), 'productTypeId': kind.pk,
        'sourceCanonicalField': canonical, 'sourceSelector': {'canonicalField': canonical},
        'quantityBasis': output['quantityBasis'], 'sourceScope': output['sourceScope'],
        'quantityBasisContract': {key: deepcopy(output[key]) for key in ('quantityBasis', 'sourceScope',
            'basisQuantity', 'basisUomId', 'basisQuantitySource', 'basisUomSource') if key in output},
        'uomId': unit.pk, 'uomLabel': unit.name, 'manufacturingModeId': None,
        'workCenterId': None, 'standardCapacityId': None,
        'contractKind': 'FORMAL_LEGACY_RULE', 'structuredMaintenanceSupported': False,
        'configurationValidation': 'METADATA_ONLY', 'statusLabel': '已有正式发布的工序来源规则',
        'sourceExpression': spec.get('expression'), 'sourceEvidence': deepcopy(evidence),
        'quantityExpression': spec.get('expression'),
        'quantityBasisLabel': {'SOURCE_SCOPE_TOTAL': '正式来源范围总量，不乘计划数量',
            'PER_BASIS_QUANTITY': '按正式来源基数比例承接，保留原比例合同'}[output['quantityBasis']],
        'deduplicationLabel': '仅承接正式规则选定来源；总览不相加原始与派生量、不按对象数复制数量',
        'producerVersion': None,
        'producerRuleVersion': None,
        'capacityUsageScopeLabel': '未声明专用产能用途域；不据此认定APS就绪',
        'purposeLabel': evidence.get('workloadDefinition') or rule.rule_name,
        'effectiveFrom': rule.effective_from.isoformat() if rule.effective_from else None,
        'effectiveTo': rule.effective_to.isoformat() if rule.effective_to else None}
    contract = _configuration(rule, require_released=True)
    if contract is not None:
        _, config, selector = contract
        producer = refs['producer'].get(selector['producerRuleId'])
        mode = refs['mode'].get(config['modeId'])
        center = refs['center'].get(config['workCenterId'])
        non_quantified = config.get('capacityMode') == REFERENCE_TYPE
        capacity = refs['capacity'].get(config.get('standardCapacityId'))
        if (not producer or producer.status != 'released' or not native._active(producer)
                or producer.version != selector['producerRuleVersion']
                or not mode or mode.status != 'released' or not native._active(mode)
                or mode.version != config['modeVersion'] or mode.uom_id != unit.pk
                or not native._active(center)
                or (not non_quantified and (not native._active(capacity)
                    or capacity.operation_id != _operation_id(operation) or capacity.product_type_id != kind.pk
                    or capacity.work_center_id != center.pk or capacity.uom_id != unit.pk))
                or config['factoryScope']['companyId'] != rule.company_id
                or center.workshop_id != config['factoryScope']['workshopId']
                or not native._active(center.workshop) or center.workshop.company_id != rule.company_id
                or (_get(operation, 'workshop_id') and _get(operation, 'workshop_id') != center.workshop_id)
                or not native._unit_token(unit, inputs[0].get('unit'))):
            _fail('WORKLOAD_SOURCE_REFERENCE_INVALID', '制造规则引用的来源版本、模式、资源、产能或单位无效')
        if (_get(operation, 'work_center_id') and _get(operation, 'work_center_id') != center.pk
                and not native._active(refs['capabilities'].get((_operation_id(operation), center.pk)))):
            _fail('MANUFACTURING_RESOURCE_INVALID', '规则资源不同于工序默认资源且缺少有效替代能力')
        if not non_quantified:
            _capacity_metadata(capacity, kind, _operation_id(operation), refs)
        _routing_metadata(config, _operation_id(operation), center, spec, refs)
        producer_spec = validate_specification(producer.specification)
        if producer_spec['outputs'][0].get('resultDomain') != 'DERIVED_FACT':
            _fail('SOURCE_OUTPUT_DOMAIN_MISMATCH', '制造来源生产规则必须原生输出DERIVED_FACT')
        summary.update(sourceSelector=deepcopy(selector), manufacturingModeId=mode.pk,
            manufacturingModeVersion=mode.version, workCenterId=center.pk,
            standardCapacityId=capacity.pk if capacity else None, producerSpecificationHash=specification_hash(producer_spec),
            producerVersion=selector['producerRuleVersion'], producerRuleVersion=selector['producerRuleVersion'],
            contractKind='MANUFACTURING_EOR_RULE', structuredMaintenanceSupported=True)
        summary.update(capacityMode=REFERENCE_TYPE if non_quantified else STANDARD_CAPACITY,
            capacityModeLabel='正式精确准备裁决核验的不可定量工序' if non_quantified else '正式标准产能引用',
            requiresPlanPreparation=non_quantified)
        if 'capacityUsageScope' in config:
            summary['capacityUsageScope'] = deepcopy(config['capacityUsageScope'])
            summary['capacityUsageScopeLabel'] = ('规则声明工程EOR专用产能；不代表APS独立产能或投产通过'
                if config['capacityUsageScope'].get('usageScope') == 'ENGINEERING_EOR_ONLY'
                else '规则声明的正式产能用途域；总览仅投影，不扩大为排程结论')
        if 'routingContext' in config:
            summary['routingContext'] = deepcopy(config['routingContext'])
    return summary


def _overlap(left, right):
    if left['productTypeId'] != right['productTypeId']:
        return False
    for key in ('routingId', 'routingVersionId', 'routingStepId'):
        a_route, b_route = left.get('routingContext', {}), right.get('routingContext', {})
        if a_route.get(key) is not None and b_route.get(key) is not None and a_route[key] != b_route[key]:
            return False
    a, b = left['sourceSelector'], right['sourceSelector']
    if a.get('canonicalField') != b.get('canonicalField'):
        return False
    for key in ('producerRuleId', 'producerRuleVersion'):
        if a.get(key) is not None and b.get(key) is not None and a[key] != b[key]:
            return False
    at, bt = a.get('traceEquals', {}), b.get('traceEquals', {})
    return not any(key in bt and bt[key] != value for key, value in at.items())


def _routing_matches(declared, context):
    if context is None or declared is None:
        return True
    keys = ('routingId', 'routingVersionId', 'routingStepId')
    # Malformed declarations cannot establish that a failed rule is outside
    # this scope. Keep its explicit invalid blocker instead of hiding it.
    if not isinstance(declared, dict) or any(type(declared.get(key)) is not int or declared[key] <= 0 for key in keys):
        return True
    return all(declared[key] == context[key] for key in keys)


def _finish_projection(value):
    value['blockers'] = [row for row in value['blockers'] if row.get('code') != 'WORKLOAD_SOURCE_RULE_AMBIGUOUS']
    value.update(hasValidSourceConfiguration=False,
        statusCode='LEGACY_UNBOUND' if value['legacyQuantityDriver'] else 'MISSING',
        statusLabel='旧来源说明尚未绑定正式规则' if value['legacyQuantityDriver'] else '尚未配置正式作业量来源')
    sources = value['sources']
    conflicts = [(a['ruleId'], b['ruleId']) for index, a in enumerate(sources)
        for b in sources[index + 1:] if _overlap(a, b)]
    if conflicts:
        value['blockers'].append({'code': 'WORKLOAD_SOURCE_RULE_AMBIGUOUS',
            'statusLabel': '同产品类型存在来源选择条件可重叠的发布规则', 'rulePairs': conflicts})
        value.update(statusCode='AMBIGUOUS', statusLabel='正式作业量来源规则存在歧义')
    elif value['blockers']:
        value.update(statusCode='INVALID', statusLabel='正式作业量来源配置校验未通过')
    elif sources:
        value.update(statusCode='CONFIGURED', statusLabel='已配置正式作业量来源规则', hasValidSourceConfiguration=True)
    return value


def restrict_operation_projection(projection, routing_context):
    """Pure scope restriction over an already batch-read operation projection."""
    if not isinstance(routing_context, dict):
        _fail('WORKLOAD_SOURCE_ROUTING_CONTEXT_INVALID', '必须提供正式路线、版本及步骤范围')
    for key in ('routingId', 'routingVersionId', 'routingStepId'):
        _id(routing_context.get(key), key)
    value = deepcopy(projection)
    # Re-restriction preserves fallback provenance without reusing a previous
    # scope's selection decision.
    existing_ids = {row['ruleId'] for row in value['sources']}
    for row in value.get('overriddenSources', []):
        if row['ruleId'] not in existing_ids:
            value['sources'].append({key: item for key, item in row.items()
                                     if key not in {'overriddenByRuleIds', 'overrideReason'}})
    value['sources'] = [row for row in value['sources'] if _routing_matches(row.get('routingContext'), routing_context)]
    value['blockers'] = [row for row in value['blockers'] if row.get('code') != 'WORKLOAD_SOURCE_RULE_AMBIGUOUS'
        and _routing_matches(row.get('routingContext'), routing_context)]
    value['routingContext'] = {key: routing_context[key] for key in ('routingId', 'routingVersionId', 'routingStepId')}
    # An exact, validated step configuration can override only an identical
    # fallback from the same formal code family. Version labels and documentary
    # sourceEvidence do not establish precedence. Retain every overridden row.
    keys = ('operationId', 'productTypeId', 'uomId', 'quantityBasis', 'quantityBasisContract', 'sourceScope',
            'sourceSelector', 'manufacturingModeId', 'manufacturingModeVersion',
            'workCenterId', 'standardCapacityId', 'sourceExpression', 'evaluationSemanticsHash')
    def same_family(left, right):
        return bool(left.get('ruleCode') and left.get('ruleCode') == right.get('ruleCode')
                    and left.get('operationId') == right.get('operationId')
                    and left.get('productTypeId') == right.get('productTypeId'))
    def identical_binding(left, right):
        if any(left.get(key) is None or right.get(key) is None for key in keys):
            return False
        return (canonical_json({**{key: left[key] for key in keys}, 'capacityUsageScope': left.get('capacityUsageScope')})
                == canonical_json({**{key: right[key] for key in keys}, 'capacityUsageScope': right.get('capacityUsageScope')}))
    exact = [row for row in value['sources'] if isinstance(row.get('routingContext'), dict)
             and all(row['routingContext'].get(key) == routing_context[key]
                     for key in ('routingId', 'routingVersionId', 'routingStepId'))]
    overridden, selected, conflicts = [], [], []
    for row in value['sources']:
        matches = [specific for specific in exact if same_family(row, specific)] if row.get('routingContext') is None else []
        identical = [specific for specific in matches if identical_binding(row, specific)]
        if identical and len(identical) == len(matches):
            overridden.append({**row, 'overriddenByRuleIds': [entry['ruleId'] for entry in identical],
                'overrideReason': {'code': 'EXACT_STEP_CONFIGURATION_OVERRIDES_IDENTICAL_FALLBACK',
                    'statusLabel': '当前精确步骤配置覆盖相同通用回退；原发布规则保留'}})
        else:
            selected.append(row)
            conflicts.extend((row['ruleId'], specific['ruleId']) for specific in matches
                             if not identical_binding(row, specific))
    value['sources'] = selected
    value['inheritedSources'] = [row for row in selected if row.get('routingContext') is None]
    value['overriddenSources'] = overridden
    value['selectionPolicy'] = 'EXACT_STEP_OVERRIDES_IDENTICAL_RULE_FAMILY_FALLBACK'
    conflicts.extend((left['ruleId'], right['ruleId']) for index, left in enumerate(selected)
                     for right in selected[index + 1:] if same_family(left, right)
                     and not identical_binding(left, right))
    value = _finish_projection(value)
    if conflicts:
        value['blockers'].append({'code': 'WORKLOAD_SOURCE_RULE_AMBIGUOUS',
            'statusLabel': '同规则族存在未能消除的定义差异，不能自动选择', 'rulePairs': sorted(set(conflicts))})
        value.update(statusCode='AMBIGUOUS', statusLabel='正式作业量来源规则存在歧义', hasValidSourceConfiguration=False)
    return value


def project_operation_sources(operations, company_id, product_type_id=None, routing_context=None,
        *, include_schemes=False, scheme_operation_ids=None, _apply_selection=True):
    """Batch, metadata-only source projection; legacy labels confer no authority."""
    operations = list(operations)
    by_id = {_operation_id(row): row for row in operations}
    rules = [rule for rule in _rules(company_id) if native._active(rule)]
    refs = _references(rules, operations, company_id)
    result = {}
    for operation_id, operation in by_id.items():
        legacy = _get(operation, 'quantity_driver', '') or ''
        result[operation_id] = {'contractVersion': CONTRACT, 'factSource': 'server',
            'operationId': operation_id, 'legacyQuantityDriver': legacy,
            'authoritySource': 'EngineeringRuleDefinition', 'sources': [], 'blockers': [],
            'statusCode': 'LEGACY_UNBOUND' if legacy else 'MISSING',
            'statusLabel': '旧来源说明尚未绑定正式规则' if legacy else '尚未配置正式作业量来源',
            'hasValidSourceConfiguration': False, 'businessWriteCount': 0}
    for rule in rules:
        spec = rule.specification if isinstance(rule.specification, dict) else {}
        outputs = spec.get('outputs')
        if not isinstance(outputs, list) or len(outputs) != 1 or not isinstance(outputs[0], dict):
            continue
        output = outputs[0]
        operation_id = output.get('operationId')
        if (output.get('resultDomain') != 'OPERATION_REQUIREMENT' or operation_id not in by_id
                or (product_type_id is not None and output.get('productTypeId') != product_type_id)):
            continue
        config = spec.get('manufacturing') if isinstance(spec.get('manufacturing'), dict) else {}
        declared_routing = config.get('routingContext')
        try:
            if _get(by_id[operation_id], 'company_id') != company_id or not _get(by_id[operation_id], 'is_active', True):
                _fail('WORKLOAD_SOURCE_COMPANY_MISMATCH', '工序不属于当前公司有效范围')
            result[operation_id]['sources'].append(_summary(rule, by_id[operation_id], refs))
        except (EngineeringRuleError, ProductionFoundationError, native.OperationRequirementError) as error:
            result[operation_id]['blockers'].append({**_reason(error), 'ruleId': rule.pk,
                'routingContext': deepcopy(declared_routing)})
    for value in result.values():
        _finish_projection(value)
    if routing_context is not None:
        result = {key: restrict_operation_projection(value, routing_context) for key, value in result.items()}
    for operation_id, operation in by_id.items():
        operation_schemes = include_schemes and (scheme_operation_ids is None or operation_id in scheme_operation_ids)
        if not operation_schemes and not _apply_selection:
            continue
        value = result[operation_id]
        options = []
        try:
            if not operation_schemes:
                _, entries = _selection_entries(operation)
                if not entries:
                    continue
            options = source_scheme_options(operation, rules=rules,
                projection=value if product_type_id is None and routing_context is None else None)
            selection = source_selection_readback(operation, options=options)
            if operation_schemes:
                value.update(sourceSchemes=options, sourceSelection=selection)
            if _apply_selection and selection['selections']:
                retained, unselected = [], []
                for source in value['sources']:
                    scope = _scheme_scope(operation, source['productTypeId'],
                        routing_context if routing_context is not None else source.get('routingContext'))
                    chosen = _scheme_for_scope(selection['selections'], scope)
                    (retained if chosen is None or source['ruleId'] in
                        {row['ruleId'] for row in chosen['ruleRefs']} else unselected).append(source)
                value.update(sources=retained, unselectedSources=unselected)
                _finish_projection(value)
        except ProductionFoundationError as error:
            # Maintenance must remain readable so an invalid reference can be
            # diagnosed; it must never fall back to a different active scheme.
            value.update(hasValidSourceConfiguration=False, statusCode='INVALID',
                statusLabel='已保存来源方案引用失效，须按正式范围维护',
                sourceSchemes=options,
                sourceSelection={'contractVersion': SOURCE_SELECTION_CONTRACT,
                    'revision': None, 'selectionHash': None, 'selections': [],
                    'statusLabel': error.message, 'valid': False},
                sources=[], unselectedSources=deepcopy(value['sources']))
            value['blockers'].append(_reason(error))
    return result


def _scheme_scope(operation, product_type_id, routing_context=None):
    context = deepcopy(routing_context)
    if context is not None:
        if isinstance(context, dict) and set(context) == {'contractVersion', 'routingId', 'routingVersionId', 'routingStepId'}:
            context = {key: context[key] for key in ('routingId', 'routingVersionId', 'routingStepId')}
        if (not isinstance(context, dict) or set(context) != {'routingId', 'routingVersionId', 'routingStepId'}
                or any(type(value) is not int or value <= 0 for value in context.values())):
            _fail('WORKLOAD_SOURCE_SELECTION_SCOPE_INVALID', '方案必须使用完整路线、版本及步骤范围')
    return {'companyId': _get(operation, 'company_id'), 'operationId': _operation_id(operation),
        'productTypeId': _id(product_type_id, '产品类型'), 'routingContext': context}


def _scheme_core(option):
    return {key: deepcopy(option[key]) for key in
        ('scope', 'schemeId', 'schemeHash', 'ruleRefs', 'compositionRef')}


def source_scheme_options(operation, *, rules=None, projection=None):
    """Current complete published groups, never upstream producers or first rows."""
    from .operation_contribution_composition import (
        ROLE, OperationContributionCompositionError, validate_composition_references,
        _declaration_audit_proof,
    )
    company_id = _get(operation, 'company_id')
    rules = rules if rules is not None else [row for row in _rules(company_id) if native._active(row)]
    if projection is None:
        projection = project_operation_sources([operation], company_id, _apply_selection=False)[_operation_id(operation)]
    sources = {row['ruleId']: row for row in projection['sources']}
    options, declared_members = [], set()
    declared_rules = _rules(company_id)
    for declaration in declared_rules:
        spec = declaration.specification
        if not isinstance(spec, dict) or spec.get('ruleRole') != ROLE:
            continue
        composition = spec.get('allocationComposition', {})
        if not isinstance(composition, dict) or not isinstance(composition.get('resourceScope'), dict):
            continue
        if composition.get('resourceScope', {}).get('operationId') != _operation_id(operation):
            continue
        # An invalid declaration cannot turn its members into singleton choices.
        for member in composition.get('memberRules', []) if isinstance(composition.get('memberRules'), list) else []:
            if not isinstance(member, dict):
                continue
            declared_members.update(row.pk for row in declared_rules if
                (row.rule_code, row.version) == (member.get('ruleCode'), member.get('ruleVersion')))
        if not native._active(declaration):
            continue
        try:
            validated = validate_composition_references(declaration)
            _declaration_audit_proof(declaration)
        except (OperationContributionCompositionError, native.OperationRequirementError):
            continue
        member_ids = validated['memberRuleIds']
        if not member_ids or any(pk not in sources for pk in member_ids):
            continue
        members = [sources[pk] for pk in member_ids]
        contexts = {canonical_json(row.get('routingContext')) for row in members}
        if len(contexts) != 1:
            continue
        options.append(_scheme_option(operation, members, declaration))
    cohorts = {}
    for row in sources.values():
        if row['ruleId'] not in declared_members:
            key = (row['productTypeId'], canonical_json(row.get('routingContext')))
            cohorts.setdefault(key, []).append(row)
    # Multiple undeclared components are not a proved selectable whole group.
    for members in cohorts.values():
        if len(members) == 1:
            options.append(_scheme_option(operation, members, None))
    return sorted(options, key=lambda row: (canonical_json(row['scope']), row['schemeId']))


def _scheme_option(operation, members, declaration):
    first = members[0]
    scope = _scheme_scope(operation, first['productTypeId'], first.get('routingContext'))
    if any(_scheme_scope(operation, row['productTypeId'], row.get('routingContext')) != scope
            or row['uomId'] != first['uomId'] for row in members):
        _fail('WORKLOAD_SOURCE_SCHEME_INVALID', '正式方案成员必须属于同一产品、路线范围及单位')
    kind = CapacityProductType.objects.get(pk=scope['productTypeId'], company_id=scope['companyId'])
    rule_refs = [{'ruleId': row['ruleId'], 'ruleCode': row['ruleCode'], 'ruleName': row['ruleName'],
        'ruleVersion': row['ruleVersion'], 'specificationHash': row['specificationHash'],
        'label': f"{row['ruleName']} / {row['ruleVersion']}"} for row in sorted(members, key=lambda row: row['ruleId'])]
    composition = ({'id': declaration.pk, 'ruleCode': declaration.rule_code, 'ruleVersion': declaration.version,
        'specificationHash': specification_hash(declaration.specification)} if declaration else None)
    identity = {'scope': scope, 'ruleRefs': [{key: row[key] for key in
        ('ruleId', 'ruleCode', 'ruleVersion', 'specificationHash')} for row in rule_refs], 'compositionRef': composition}
    context = scope['routingContext']
    context_label = '本产品类型通用范围'
    if context is not None:
        step = RoutingStep.objects.select_related('routing_version__routing', 'operation').get(pk=context['routingStepId'])
        if (step.routing_version_id != context['routingVersionId'] or step.routing_version.routing_id != context['routingId']
                or step.operation_id != _operation_id(operation)):
            _fail('WORKLOAD_SOURCE_SELECTION_SCOPE_INVALID', '方案路线版本与工序步骤不一致')
        context_label = f'{step.routing_version.routing} / {step.routing_version.routing_version} / 第{step.sequence}步 {step.operation.name}'
    name = declaration.rule_name if declaration else first['ruleName']
    return {'schemeId': f'COMPOSITION:{declaration.pk}' if declaration else f"RULE:{first['ruleId']}",
        'schemeHash': specification_hash(identity), 'scope': scope, 'ruleRefs': rule_refs, 'compositionRef': composition,
        'name': name, 'label': name, 'statusLabel': '正式完整来源方案，可明确保存应用',
        'quantityBasisLabel': first['quantityBasisLabel'], 'uomId': first['uomId'], 'uomLabel': first['uomLabel'],
        'productTypeId': kind.pk, 'productTypeLabel': f'{kind.code} / {kind.name}',
        'routingContext': context, 'routingContextLabel': context_label}


def _selection_entries(operation, *, verify_audit=True):
    state = _get(operation, 'workload_source_selection')
    if state in (None, {}):
        from system.models import OrganizationOperatingAuditRecord
        history = OrganizationOperatingAuditRecord.objects.filter(organization_id=_get(operation, 'company_id'),
            target_type='Process', target_id=_operation_id(operation),
            action_code='production.master_data.resource.maintain',
            after_snapshot__importContext__sourceSchemeAuthorization__isnull=False)
        if any((audit.after_snapshot or {}).get('state', {}).get('workload_source_selection')
                for audit in history):
            _fail('WORKLOAD_SOURCE_SELECTION_MISSING', '本工序曾正式保存方案引用，当前标记缺失不得回退旧规则')
        return {}, []
    if (not isinstance(state, dict) or set(state) != {'contractVersion', 'revision', 'selections'}
            or state['contractVersion'] != SOURCE_SELECTION_CONTRACT or type(state['revision']) is not int
            or state['revision'] < 1 or not isinstance(state['selections'], list) or not state['selections']):
        _fail('WORKLOAD_SOURCE_SELECTION_INVALID', '已保存来源方案合同损坏，不得回退旧规则')
    scopes = set()
    for row in state['selections']:
        if not isinstance(row, dict) or set(row) != {'scope', 'schemeId', 'schemeHash', 'ruleRefs', 'compositionRef'}:
            _fail('WORKLOAD_SOURCE_SELECTION_INVALID', '已保存方案成员引用不完整')
        scope = row['scope']
        if (not isinstance(scope, dict) or set(scope) != {'companyId', 'operationId', 'productTypeId', 'routingContext'}
                or canonical_json(scope) != canonical_json(_scheme_scope(operation,
                    scope.get('productTypeId'), scope.get('routingContext')))):
            _fail('WORKLOAD_SOURCE_SELECTION_SCOPE_INVALID', '来源方案引用跨公司或工序范围')
        key = canonical_json(scope)
        if key in scopes:
            _fail('WORKLOAD_SOURCE_SELECTION_AMBIGUOUS', '同一准确范围存在多个已应用方案')
        scopes.add(key)
    if verify_audit:
        from system.models import OrganizationOperatingAuditRecord
        audits = OrganizationOperatingAuditRecord.objects.filter(organization_id=_get(operation, 'company_id'),
            target_type='Process', target_id=_operation_id(operation),
            action_code='production.master_data.resource.maintain').order_by('-pk')
        proved = False
        for audit in audits:
            snapshot = audit.after_snapshot if isinstance(audit.after_snapshot, dict) else {}
            auth = snapshot.get('importContext', {}).get('sourceSchemeAuthorization', {})
            if (canonical_json(snapshot.get('state', {}).get('workload_source_selection')) == canonical_json(state)
                    and snapshot.get('authorization', {}).get('allowed') is True
                    and all(auth.get(action, {}).get('allowed') is True for action in (CREATE, RELEASE))):
                proved = True
                break
        if not proved:
            _fail('WORKLOAD_SOURCE_SELECTION_AUDIT_INVALID', '来源方案引用缺少原维护与规则权限审计证明')
    return state, state['selections']


def source_selection_readback(operation, *, options=None):
    state, entries = _selection_entries(operation)
    options = source_scheme_options(operation) if options is None and entries else (options or [])
    selected = []
    for entry in entries:
        matches = [row for row in options if canonical_json(_scheme_core(row)) == canonical_json(entry)]
        if len(matches) != 1:
            _fail('WORKLOAD_SOURCE_SELECTION_STALE', '已应用方案已失效、缺成员或范围不一致，不得回退')
        selected.append(deepcopy(matches[0]))
    return {'contractVersion': SOURCE_SELECTION_CONTRACT, 'revision': state.get('revision', 0),
        'selectionHash': specification_hash(state), 'selections': selected, 'valid': True,
        'statusLabel': '已明确保存正式来源方案' if entries else '尚未明确选择，沿用既有正式规则'}


def _scheme_for_scope(entries, scope):
    exact = [row for row in entries if row['scope'] == scope]
    if not exact and scope['routingContext'] is not None:
        exact = [row for row in entries if row['scope'] == {**scope, 'routingContext': None}]
    if len(exact) > 1:
        _fail('WORKLOAD_SOURCE_SELECTION_AMBIGUOUS', '当前正式范围的方案选择不唯一')
    return exact[0] if exact else None


def prepare_source_scheme_selection(*, user, operation, intent):
    """Pure proposed field value; original Process writer persists and audits."""
    authorization = _configure_authorization(user)
    if not authorization['allowed']:
        _fail('PERMISSION_DENIED', '当前账号没有正式来源方案维护所需规则权限或实名执行链')
    if (not isinstance(intent, dict) or set(intent) !=
            {'contractVersion', 'expectedRevision', 'scope', 'schemeId', 'schemeHash'}
            or intent['contractVersion'] != SOURCE_SELECTION_CONTRACT):
        _fail('WORKLOAD_SOURCE_SELECTION_INTENT_INVALID', '只能提交准确范围及服务器完整方案选择意图')
    state, entries = _selection_entries(operation)
    if type(intent['expectedRevision']) is not int or intent['expectedRevision'] != state.get('revision', 0):
        _fail('WORKLOAD_SOURCE_SELECTION_REVISION_CONFLICT', '来源方案已变化，请重新读取后维护')
    options = source_scheme_options(operation)
    matches = [row for row in options if canonical_json(row['scope']) == canonical_json(intent['scope']) and row['schemeId'] == intent['schemeId']
        and row['schemeHash'] == intent['schemeHash']]
    if len(matches) != 1:
        _fail('WORKLOAD_SOURCE_SELECTION_STALE', '所选正式方案已失效、范围不符或整组证明已变化')
    chosen = _scheme_core(matches[0])
    prior = next((row for row in entries if row['scope'] == chosen['scope']), None)
    if prior == chosen:
        return deepcopy(state), authorization['authorizationByAction']
    # This is a choice for future generation. Existing requirements, saved
    # allocations and fixed plan readers keep their original rule references.
    updated = [deepcopy(row) for row in entries if row['scope'] != chosen['scope']] + [chosen]
    return {'contractVersion': SOURCE_SELECTION_CONTRACT, 'revision': state.get('revision', 0) + 1,
        'selections': sorted(updated, key=lambda row: canonical_json(row['scope']))}, authorization['authorizationByAction']


class _SourceSchemeBatch:
    def __init__(self, user, rule_ids):
        self.key, self.user_id, self.company_id = _SCHEME_BATCH_KEY, user.pk, user.company_id
        self.rule_ids = frozenset(rule_ids)


def check_source_scheme_generation(*, user, rule, batch=None):
    spec = rule.specification if isinstance(rule.specification, dict) else {}
    outputs = spec.get('outputs', [])
    if len(outputs) != 1 or outputs[0].get('resultDomain') != 'OPERATION_REQUIREMENT':
        return None
    operation = Process.objects.get(pk=outputs[0]['operationId'], company_id=user.company_id)
    _, entries = _selection_entries(operation)
    if not entries:
        return None
    selected = source_selection_readback(operation)
    declared_scope = spec.get('manufacturing', {}).get('routingContext')
    scope = _scheme_scope(operation, outputs[0]['productTypeId'], declared_scope)
    if declared_scope is None and any(row['scope']['productTypeId'] == scope['productTypeId']
            and row['scope']['routingContext'] is not None for row in selected['selections']):
        _fail('WORKLOAD_SOURCE_SELECTION_SCOPE_REQUIRED', '本产品已明确配置路线版本方案；新办理不得以未限定路线的通用规则绕过')
    chosen = _scheme_for_scope(selected['selections'], scope)
    if chosen is None:
        return None
    ids = {row['ruleId'] for row in chosen['ruleRefs']}
    if rule.pk not in ids:
        _fail('WORKLOAD_SOURCE_SCHEME_NOT_SELECTED', '本准确范围的新办理只能使用已明确保存的完整来源方案')
    if len(ids) > 1 and not (isinstance(batch, _SourceSchemeBatch) and batch.key is _SCHEME_BATCH_KEY
            and batch.user_id == user.pk and batch.company_id == user.company_id and ids <= batch.rule_ids):
        _fail('WORKLOAD_SOURCE_SCHEME_GROUP_REQUIRED', '已选多规则方案必须由原生批量入口完整办理，禁止单成员绕过')
    return ids


def operation_source_configuration(operation, product_type_id=None, routing_context=None, *, _apply_selection=True):
    return project_operation_sources([operation], _get(operation, 'company_id'), product_type_id,
        routing_context=routing_context, _apply_selection=_apply_selection)[_operation_id(operation)]


def _configure_authorization(user):
    decisions = {action: AuthorizationService.decide(user=user, action_code=action,
        organization_id=user.company_id, business_object={'organizationId': user.company_id})
        for action in (CREATE, RELEASE)}
    permission = all(row.get('allowed') for row in decisions.values())
    chain, blocker = {}, None
    if permission:
        try:
            chain = _actor_chain(user)
        except ProductionFoundationError as error:
            blocker = _reason(error)
    if not permission:
        denied = next(row for row in decisions.values() if not row.get('allowed'))
        blocker = {'code': denied.get('decisionCode', 'PERMISSION_DENIED'),
            'statusLabel': denied.get('reason', '当前账号没有正式规则配置权限')}
    return {'allowed': permission and bool(chain), 'permissionAllowed': permission,
        'executionChainComplete': bool(chain), 'executionChain': chain,
        'authorizationByAction': decisions, 'decisionCode': blocker['code'] if blocker else 'ALLOWED',
        'statusLabel': blocker['statusLabel'] if blocker else '具备原生规则配置及实名执行资格',
        'blockers': [blocker] if blocker else []}


def _numeric_producer(rule, units):
    if isinstance(rule.specification, dict) and rule.specification.get('ruleRole') == 'OPERATION_ALLOCATION_COMPOSITION':
        return None
    spec = validate_specification(rule.specification)
    output = spec['outputs'][0]
    if output.get('resultDomain') != 'DERIVED_FACT' or output.get('valueType') != 'decimal':
        return None
    matches = [unit for unit in units if native._unit_token(unit, output.get('unit'))
        and unit.dimension == output.get('unitDimension')]
    if len(matches) != 1:
        return None
    extension = spec.get('factExtension') if isinstance(spec.get('factExtension'), dict) else {}
    strategy = extension.get('strategy', 'DIRECT_FACT')
    semantics = {'strategy': strategy, 'groupKeys': deepcopy(extension.get('groupKeys', [])),
        'statusLabel': {'OBJECT_FORMULA': '正式对象公式输出；对象覆盖须在所选计划中核验',
            'SCOPE_SUM': '正式来源范围汇总；不再次叠加原始明细',
            'GROUP_SUM': '正式分类汇总；分组及对象覆盖须在所选计划中核验'}.get(strategy,
                '正式派生事实输出；不据字段名称推断明细或汇总'),
        'deduplicationLabel': '仅承接已证明的正式事实；不同字段不自动证明互不重叠',
        'unitSemanticsLabel': '正式单位相同仅证明计量单位匹配，不等于业务投入语义已确认'}
    return {'id': rule.pk, 'producerRuleId': rule.pk, 'label': f'{rule.rule_name} / {rule.version}',
        'code': rule.rule_code, 'version': rule.version, 'canonicalField': output['canonicalName'],
        'specificationHash': specification_hash(spec), 'valueType': output['valueType'],
        'resultDomain': output['resultDomain'], 'uomId': matches[0].pk, 'uomLabel': matches[0].name,
        'unitDimension': matches[0].dimension, 'sourceSemantics': semantics}


def _quantity_contracts():
    return [{'code': 'SOURCE_SCOPE_TOTAL', 'statusLabel': '正式订单行来源总量，不乘计划数量',
        'requiresBasisQuantity': False, 'requiresBasisUomId': False, 'dynamicOrderBasis': True},
        {'code': 'PER_BASIS_QUANTITY', 'statusLabel': '每正式基准数量作业量，按原生比例承接',
        'requiresBasisQuantity': True, 'requiresBasisUomId': True, 'dynamicOrderBasis': False}]


def _expression_contract():
    return {'inputAlias': 'source_quantity', 'defaultExpression': 'source_quantity',
        'operators': ['+', '-', '*', '/'], 'unaryOperators': ['+', '-'],
        'functionsAllowed': False, 'multipleInputsAllowed': False,
        'statusLabel': '仅对一个正式来源量作受控算术；不自动增加损耗率或跨来源相加',
        'unitSemanticsLabel': '输入、工序、模式及产能使用同一正式单位；业务口径仍须正式依据'}


def _routing_options(company_id, kinds):
    rows = RoutingStep.objects.filter(is_active=True, operation__company_id=company_id,
        routing_version__status='released', routing_version__routing__company_id=company_id,
        routing_version__routing__status='released').select_related('operation',
            'routing_version__routing__product', 'routing_version__routing__order_engineering_instance__product')
    result = []
    for step in rows.order_by('routing_version_id', 'sequence', 'pk'):
        version, route = step.routing_version, step.routing_version.routing
        if (not native._active(route) or not native._active(step.operation)
            or (version.effective_date and version.effective_date > native._today())
            or (version.expire_date and version.expire_date < native._today())):
            continue
        instance = route.order_engineering_instance if route.order_engineering_instance_id else None
        product = route.product if route.product_id else (instance.product if instance and instance.product_id else None)
        category = route.product_category_id or (instance.product_category_id if instance else None) or (product.category_id if product else None)
        process_type = route.manufacturing_process_type_id or (instance.selected_process_type_id if instance else None)
        allowed = [kind['id'] for kind in kinds if kind['productCategoryId'] == category
            and (process_type is None or kind['manufacturingProcessTypeId'] == process_type)]
        result.append({'contractVersion': 'PCE-MANUFACTURING-ROUTING-CONTEXT-V1', 'routingId': route.pk,
            'routingVersionId': version.pk, 'routingStepId': step.pk, 'operationId': step.operation_id,
            'productTypeIds': allowed, 'label': f'{route.routing_code} / {version.routing_version} / {step.sequence} / {step.operation.name}'})
    return result


def _formal_trace_options(rules, producer, *, product_type_id=None, allowed_product_types=None):
    """Declared selector metadata only; never infer conditions from fact values."""
    options = {}
    for rule in rules:
        if not native._active(rule):
            continue
        raw = rule.specification if isinstance(rule.specification, dict) else {}
        config = raw.get('manufacturing') if isinstance(raw.get('manufacturing'), dict) else {}
        declared = config.get('sourceSelector') if isinstance(config.get('sourceSelector'), dict) else {}
        if (declared.get('producerRuleId') != producer['id']
                or declared.get('producerRuleVersion') != producer['version']
                or declared.get('canonicalField') != producer['canonicalField']):
            continue
        try:
            contract = _configuration(rule, require_released=True)
        except (native.OperationRequirementError, EngineeringRuleError):
            continue
        if contract is None:
            continue
        spec, _, selector = contract
        kind_id = spec['outputs'][0].get('productTypeId')
        if ((product_type_id is not None and kind_id != product_type_id)
                or (allowed_product_types is not None and kind_id not in allowed_product_types)
                or selector['producerRuleId'] != producer['id']
                or selector['producerRuleVersion'] != producer['version']
                or selector['canonicalField'] != producer['canonicalField']):
            continue
        binding = {'producerRuleId': producer['id'], 'producerRuleVersion': producer['version'],
                   'productTypeId': kind_id, 'traceEquals': selector['traceEquals']}
        key = 'trace:' + specification_hash(binding)
        option = options.setdefault(key, {'key': key, 'productTypeId': kind_id,
            'traceEquals': deepcopy(selector['traceEquals']), 'label': rule.rule_name,
            'statusLabel': '已有发布规则的正式来源条件；保存时仍重验当前引用', 'sourceRuleIds': []})
        option['sourceRuleIds'].append(rule.pk)
    return [options[key] for key in sorted(options)]


def _catalog_capacity_options(capacities, *, kinds, centers, units):
    """Retain measured options; admit zero only with the native source proof."""
    kinds = {row.pk: row for row in kinds}
    center_ids, unit_ids = {row['id'] for row in centers}, {row.pk for row in units}
    result, references = [], {}
    for row in capacities:
        if (not native._active(row) or row.product_type_id not in kinds
                or row.work_center_id not in center_ids or row.uom_id not in unit_ids
                or row.time_basis != 'day' or row.time_basis_quantity != 1
                or row.time_unit != 'DAY' or not row.effective_from):
            continue
        if row.measurement_status == 'zero_capacity':
            try:
                _capacity_metadata(row, kinds[row.product_type_id], row.operation_id, references)
            except ProductionFoundationError:
                continue
        elif row.measurement_status != 'measured' or row.quantity is None or row.quantity <= 0:
            continue
        result.append({'id': row.pk, 'label': f'{row.code} / {row.name}', 'operationId': row.operation_id,
            'productTypeId': row.product_type_id, 'workCenterId': row.work_center_id, 'uomId': row.uom_id,
            'quantity': str(row.quantity) if row.quantity is not None else None})
    return result


@transaction.atomic
def catalog(*, user):
    _authorize(user, RULE_VIEW)
    company_id = user.company_id
    units = [row for row in UnitOfMeasure.objects.filter(company_id=company_id, is_active=True) if native._active(row)]
    producers = []
    rules = _rules(company_id)
    for rule in rules:
        if native._active(rule):
            try:
                row = _numeric_producer(rule, units)
                if row:
                    producers.append(row)
            except EngineeringRuleError:
                continue
    modes = [{'id': row.pk, 'label': f'{row.name} / {row.version}', 'code': row.code,
        'version': row.version, 'uomId': row.uom_id}
        for row in ManufacturingMode.objects.filter(company_id=company_id, status='released') if native._active(row)]
    kind_rows = [row for row in CapacityProductType.objects.filter(company_id=company_id, is_active=True).select_related(
            'product_category', 'manufacturing_process_type') if native._active(row)
        and native._active(row.product_category) and native._active(row.manufacturing_process_type)
        and row.product_category.company_id == company_id and row.manufacturing_process_type.company_id == company_id]
    kinds = [{'id': row.pk, 'label': f'{row.code} / {row.name}', 'code': row.code,
        'productCategoryId': row.product_category_id, 'manufacturingProcessTypeId': row.manufacturing_process_type_id}
        for row in kind_rows]
    for producer in producers:
        options = _formal_trace_options(rules, producer, allowed_product_types={row['id'] for row in kinds})
        if options:
            producer['traceOptions'] = options
    centers = [{'id': row.pk, 'label': f'{row.code} / {row.name}', 'workshopId': row.workshop_id}
        for row in WorkCenter.objects.filter(company_id=company_id, is_active=True).select_related('workshop')
        if native._active(row) and row.workshop_id and native._active(row.workshop)
        and row.workshop.company_id == company_id]
    capacities = _catalog_capacity_options(
        StandardCapacity.objects.filter(company_id=company_id, is_active=True),
        kinds=kind_rows, centers=centers, units=units)
    center_ids = {row['id'] for row in centers}
    center_capabilities = [{'operationId': row.operation_id, 'workCenterId': row.work_center_id,
        'source': 'FORMAL_CAPABILITY'} for row in WorkCenterOperationCapability.objects.filter(
            operation__company_id=company_id, work_center__company_id=company_id,
            work_center_id__in=center_ids).select_related('operation')
        if native._active(row) and native._active(row.operation)]
    center_capabilities.extend({'operationId': row.pk, 'workCenterId': row.work_center_id,
        'source': 'FORMAL_OPERATION_DEFAULT'} for row in Process.objects.filter(
            company_id=company_id, work_center_id__in=center_ids) if native._active(row))
    plans = []
    decision = AuthorizationService.decide(user=user, action_code=native.PLAN_VIEW, organization_id=company_id,
        business_object={'organizationId': company_id})
    if decision.get('allowed'):
        rows = list(ProductionPlan.objects.filter(
            planning_requirement__demand__sales_order_item__sales_order__company_id=company_id,
            planning_requirement__demand__manufacturing_output__routing_version__routing__company_id=company_id,
            planning_requirement__demand__manufacturing_output__routing_version__status='released',
            planning_requirement__demand__manufacturing_output__release_status='released_to_manufacturing'
        ).filter(Q(planning_requirement__demand__manufacturing_output__product__company_id=company_id)
            | Q(planning_requirement__demand__manufacturing_output__order_engineering_instance__company_id=company_id,
                planning_requirement__demand__manufacturing_output__order_engineering_instance__sales_order_item_id=F(
                    'planning_requirement__demand__sales_order_item_id'))
        ).select_related('planning_requirement__demand__manufacturing_output'))
        version_ids = {row.planning_requirement.demand.manufacturing_output.routing_version_id for row in rows}
        steps, all_steps = {}, {}
        for row in RoutingStep.objects.filter(routing_version_id__in=version_ids).select_related('operation').order_by('sequence', 'pk'):
            all_steps.setdefault(row.routing_version_id, []).append({'id': row.pk, 'operationId': row.operation_id,
                'label': f'{row.sequence} / {row.operation.name}', 'isActive': row.is_active})
            if not row.is_active:
                continue
            steps.setdefault(row.routing_version_id, []).append({'id': row.pk, 'operationId': row.operation_id,
                'label': f'{row.sequence} / {row.operation.name}'})
        for row in rows:
            output = row.planning_requirement.demand.manufacturing_output
            plans.append({'id': row.pk, 'label': row.plan_no, 'manufacturingOutputId': output.pk,
                'routingVersionId': output.routing_version_id, 'routingSteps': steps.get(output.routing_version_id, []),
                'allRoutingSteps': all_steps.get(output.routing_version_id, [])})
    return {'contractVersion': CONTRACT, 'factSource': 'server', 'companyId': company_id,
        'producers': producers, 'manufacturingModes': modes, 'productTypes': kinds,
        'workCenters': centers, 'standardCapacities': capacities, 'productionPlans': plans,
        'workCenterOperationCapabilities': center_capabilities,
        'capacityModes': [
            {'value': STANDARD_CAPACITY, 'statusLabel': '正式标准产能引用',
             'requiresStandardCapacity': True, 'requiresPlanPreparation': False},
            {'value': REFERENCE_TYPE, 'statusLabel': '正式精确准备裁决核验的不可定量工序',
             'requiresStandardCapacity': False, 'requiresPlanPreparation': True}],
        'configureAuthorization': _configure_authorization(user), 'businessWriteCount': 0,
        'units': [{'id': row.pk, 'label': row.name, 'code': row.code, 'dimension': row.dimension} for row in units],
        'quantityContracts': _quantity_contracts(), 'expressionContract': _expression_contract(),
        'routingContexts': _routing_options(company_id, kinds),
        'scopeContracts': [{'code': 'PRODUCT_TYPE', 'statusLabel': '精确产品类型范围', 'requiresRoutingContext': False},
            {'code': 'ROUTING_STEP', 'statusLabel': '精确路线、版本及步骤覆盖', 'requiresRoutingContext': True}],
        'supportedScopes': [{'code': 'PRODUCT_TYPE', 'statusLabel': '当前公司及精确产品类型'},
            {'code': 'ROUTING_STEP', 'statusLabel': '正式路线、版本及步骤精确范围'}],
        'matchingPriorityLabels': ['先限定当前公司及正式产品类型，来源生产者版本与追溯条件必须精确匹配',
            '精确步骤仅在同规则族且完整求值语义相同时覆盖通用回退，原规则保留追溯',
            '同优先级重叠或非等价定义阻断，不取第一条；不同版本不自动取最新或退役旧版'],
        'capacitySemanticVerification': {'statusCode': 'NOT_SUPPORTED',
            'statusLabel': '已校验正式单位、工序、产品类型和资源；现有产能模型未提供独立投入面积语义认证合同'},
        'unsupportedScopes': [{'code': 'MATERIAL_SUBSET', 'statusLabel': '物料或物料类子范围尚无完整消费合同'},
            {'code': 'CROSS_SOURCE_SUM', 'statusLabel': '不在工序规则中临时汇总多个来源或进行跨字段去重'}]}


def _bucket(code, label, *, quantity=False):
    value = {'statusCode': code, 'statusLabel': label, 'items': [], 'blockers': []}
    if quantity:
        value.update(quantity=None, uomId=None, uomLabel=None)
    return value


def _scope_proof_key(user, context, *, read_cache=None):
    plan, output, item, base, step, kind, applicability = context
    return ('verified_workload_step_scope', user.company_id, user.pk, native._today(),
        plan.pk, step.pk, *(native._proof_record_hash(row, read_cache=read_cache) for row in (
            plan, plan.planning_requirement, plan.planning_requirement.demand,
            output, item, base, base.source_record, base.engineering_instance,
            effective_baseline(plan), output.bom_version,
            output.engineering_document_version, output.routing_version,
            output.routing_version.routing, step, step.operation, kind)),
        native._digest(applicability), native._digest(source_selection(plan)))


def _remember_scope(user, cache, context):
    if (not isinstance(cache, native._ReadOnlyProofCache) or cache.user_id != user.pk
            or not cache.is_current(user.company_id)):
        return
    plan, _, _, _, step, _, _ = context
    key = _scope_proof_key(user, context, read_cache=cache)
    cache[key] = native._copy_read_proof(context)
    cache[('verified_workload_step_scope_index', user.company_id, user.pk, plan.pk, step.pk)] = key
    version_context = getattr(plan, '_native_step_version_context', None)
    if version_context:
        cache[('verified_workload_step_scope_index', user.company_id, user.pk,
            plan.pk, version_context['root_step'].pk)] = key


def _scope_context(user, production_plan_id, routing_step_id, *, _read_cache=None):
    if (isinstance(_read_cache, native._ReadOnlyProofCache) and _read_cache.user_id == user.pk
            and _read_cache.is_current(user.company_id)):
        index = ('verified_workload_step_scope_index', user.company_id, user.pk,
            production_plan_id, routing_step_id)
        key = _read_cache.get(index)
        context = _read_cache.get(key) if key is not None else None
        if context is not None and key == _scope_proof_key(user, context, read_cache=_read_cache):
            # Only the original native scope/resolver or the route reader's
            # already validated exact step can seed this request-local proof.
            return native._copy_read_proof(context)
        if context is not None:
            _read_cache.invalidate_proofs()
    from .daily_capacity_service import _plan_capacity_context
    from .manufacturing_structure_service import ManufacturingStructureService
    from .routing_step_applicability_service import RoutingStepApplicabilityResolver
    plan = ProductionPlan.objects.filter(pk=production_plan_id,
        planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id).first()
    if not plan:
        _fail('WORKLOAD_SOURCE_PLAN_MISSING', '所选计划不存在或不属于当前公司')
    try:
        plan, output, item, company_id = _plan_capacity_context(plan, user.company_id,
            routing_step_id=routing_step_id, read_cache=_read_cache)
    except native.DailyCapacityError as error:
        if error.code in {'STEP_VERSION_STEP_MISSING', 'STEP_VERSION_ROOT_UNPROVEN', 'STEP_VERSION_NOT_BOUND'}:
            _fail('WORKLOAD_SOURCE_STEP_MISMATCH', '所选步骤不属于计划固定或正式承接的有效路线版本及工序')
        raise
    version_context = getattr(plan, '_native_step_version_context', None)
    if version_context:
        routing_step_id = version_context['step'].pk
    base, baseline = effective_calculation(plan), effective_baseline(plan)
    if (not base or base.scope != 'order_engineering' or base.status != 'completed'
            or base.company_id != company_id or base.sales_order_item_id != item.pk
            or base.engineering_instance_id != output.order_engineering_instance_id
            or output.release_status != 'released_to_manufacturing' or output.routing_version.status != 'released'):
        _fail('WORKLOAD_SOURCE_CONTEXT_INVALID', '计划固定制造输出、主核算与已发布路线版本不一致')
    step = RoutingStep.objects.select_related('operation__calculation_uom', 'routing_version').filter(
        pk=routing_step_id, routing_version=output.routing_version, operation__company_id=company_id, is_active=True).first()
    if not step or not native._active(step.operation):
        _fail('WORKLOAD_SOURCE_STEP_MISMATCH', '所选步骤不属于计划固定的有效路线版本及工序')
    output.clean()
    # The route remains the anchor's published route. A selected calculation is
    # an operation source, never a fabricated replacement for its output FKs.
    route_base = output.engineering_calculation
    exact = {'organizationId': company_id, 'salesOrderItemId': item.pk,
        'orderEngineeringInstanceId': route_base.engineering_instance_id,
        'orderEngineeringBaselineId': output.order_engineering_baseline_id,
        'engineeringCalculationId': route_base.pk, 'bomVersionId': output.bom_version_id}
    resolved = ManufacturingStructureService.resolve_effective_routing(route_base.engineering_instance,
        on_date=native._today(), exact_version_context=exact)
    if resolved['routing_version'].pk != output.routing_version_id:
        _fail('WORKLOAD_SOURCE_STEP_MISMATCH', '正式来源解析的路线版本与计划固定版本不一致')
    instance, route = base.engineering_instance, output.routing_version.routing
    category_id = instance.product_category_id or (instance.product.category_id if instance.product_id else None)
    process_type_id = instance.selected_process_type_id
    if (not category_id or not process_type_id
        or (route.product_category_id and route.product_category_id != category_id)
        or (route.manufacturing_process_type_id and route.manufacturing_process_type_id != process_type_id)
        or (route.product_id and route.product_id != instance.product_id)
        or (route.order_engineering_instance_id and route.order_engineering_instance_id != instance.pk)):
        _fail('WORKLOAD_SOURCE_PRODUCT_TYPE_AMBIGUOUS', '工程实例类别、所选工艺与已解析正式路线主体不一致')
    kinds = [row for row in CapacityProductType.objects.filter(company_id=company_id,
        product_category_id=category_id, manufacturing_process_type_id=process_type_id,
        is_active=True) if native._active(row)]
    if len(kinds) != 1:
        _fail('WORKLOAD_SOURCE_PRODUCT_TYPE_AMBIGUOUS', '计划路线未唯一对应有效的正式产能产品类型')
    applicability = RoutingStepApplicabilityResolver.resolve(step, engineering_calculation=base,
        engineering_document_version=output.engineering_document_version,
        order_engineering_instance=base.engineering_instance, order_engineering_baseline=baseline,
        bom_version=output.bom_version, production_plan=plan, manufacturing_output=output,
        read_cache=_read_cache)
    context = plan, output, item, base, step, kinds[0], applicability
    _remember_scope(user, _read_cache, context)
    return context


def _candidate_matches(fact, source):
    selector = source['sourceSelector']
    if fact.canonical_field != selector['canonicalField']:
        return False
    if selector.get('producerRuleId') is not None:
        detail = fact.source_detail
        if (fact.rule_id != selector['producerRuleId'] or not detail
                or detail.rule_id != selector['producerRuleId'] or detail.rule_version != selector['producerRuleVersion']):
            return False
    trace = fact.trace if isinstance(fact.trace, dict) else {}
    return all(trace.get(key) == value for key, value in selector.get('traceEquals', {}).items())


def _engineering_only_configuration(configuration):
    """A valid, uniformly explicit engineering-only contract is a separate use.

    This never overrides applicability or proves production readiness. Missing,
    invalid or mixed-purpose definitions cannot establish this distinction.
    """
    sources = configuration.get('sources', [])
    return bool(configuration.get('hasValidSourceConfiguration') is True and sources
        and all(isinstance(row.get('capacityUsageScope'), dict)
            and row['capacityUsageScope'].get('usageScope') == 'ENGINEERING_EOR_ONLY' for row in sources))


def _step_capacity_semantics(*, user, scope, applicability, source_rules, capacities, preparation=None):
    from .daily_capacity_service import (capacity_fact, scoped_capacity_semantics,
        capacity_tristate_semantics, CAPACITY_TRISTATE_CONTRACT)
    facts = [capacity_fact(row, native._today(), source_rules=source_rules) for row in capacities]
    result = scoped_capacity_semantics(scope=scope, applicability=applicability,
        source_rules=source_rules, capacity_facts=facts)
    if _non_separate_quantity_policy(preparation, scope, applicability) is not None:
        # This policy references the existing capacity fact. Statistical UOM
        # does not replace that fact's original measurement or time basis.
        return result, facts
    policy = _waiting_trigger(applicability)
    conditional_capacity = policy.get('conditionalCapacityPolicy') if policy is not None else None
    if (isinstance(conditional_capacity, dict)
            and conditional_capacity.get('appliesWhen') == 'TRIGGERED'
            and conditional_capacity.get('meaningCode') == 'NON_QUANTIFIED'
            and conditional_capacity.get('sourceValue') == '0'
            and conditional_capacity.get('quantitativeOccupancyAllowed') is False):
        original = result
        result = capacity_tristate_semantics(source_value='0', source_scope_proven=True,
            measurement_status='zero_capacity', scope=scope, record_present=bool(capacities))
        result.update(statusLabel='异常触发后经过；产能按0语义不可定量，不计定量产能占用',
            sourceStatusLabel='来自本计划步骤已提交的条件准备裁决，当前尚未触发',
            passesOperation=None, passesWhenTriggered=True, appliesWhen='TRIGGERED',
            triggerStatus='WAITING_TRIGGER', conditionalPolicyOnly=True,
            formalStandardCapacitySubstituted=False, referenceSemantics=original)
        return result, facts
    # A verified preparation ruling is exact-context qualitative evidence. It
    # does not replace a StandardCapacity, a source rule or any execution gate.
    ruling = preparation.get('capacitySemantics') if isinstance(preparation, dict) else None
    exact_keys = {'companyId', 'productionPlanId', 'manufacturingOutputId', 'mainCalculationId',
        'salesOrderItemId', 'baselineId', 'routingVersionId', 'routingStepId', 'operationId', 'productTypeId'}
    if (applicability.get('result') == 'REQUIRED' and isinstance(ruling, dict)
            and ruling.get('contractVersion') == CAPACITY_TRISTATE_CONTRACT
            and ruling.get('valid') is True and ruling.get('meaningCode') == 'NON_QUANTIFIED'
            and ruling.get('sourceValue') == '0' and set(preparation.get('exactScope', {})) == exact_keys
            and all(scope.get(key) == value for key, value in preparation.get('exactScope', {}).items())):
        result = deepcopy(ruling)
        result.update(scope=deepcopy(scope), recordPresent=bool(capacities),
            recordPresenceStatusLabel=('已有标准产能记录' if capacities else
                '当前范围无标准产能记录；缺记录不等于来源空白或不经过'),
            quantitativeOccupancyAllowed=False, independentDurationAllowed=False,
            grantsRulePublication=False, grantsRequirementGeneration=False,
            grantsAllocation=False, grantsScheduling=False,
            preparationRulingOnly=True, formalStandardCapacitySubstituted=False)
        resolution = preparation.get('capacityResolution', {})
        source_proof = resolution.get('sourceProof') if isinstance(resolution, dict) else None
        if isinstance(source_proof, dict):
            result['originalSourceValue'] = deepcopy(source_proof.get('rawValue'))
            result['originalSourceValueKind'] = source_proof.get('rawValueKind')
            if source_proof.get('rawValueKind') == 'BLANK':
                result['sourceStatusLabel'] = '原始来源矩阵为空白；当前精确范围采用已提交的0裁决，原来源及正式规则门禁保留'
    return result, facts


def _step_metadata_key(user, cache, context, on_date):
    """Own metadata by the same actor, atomic snapshot, date and exact scope."""
    if (not isinstance(cache, native._ReadOnlyProofCache) or cache.user_id != user.pk
            or native._requirement_read_cache(cache, user.company_id) is None
            or on_date != native._today()):
        return None
    scope_key = _scope_proof_key(user, context, read_cache=cache)
    if scope_key[3] != on_date:
        return None
    return ('verified_workload_step_metadata', scope_key)


def _remember_step_metadata(user, cache, context, metadata, on_date):
    key = _step_metadata_key(user, cache, context, on_date)
    if key is not None:
        value = deepcopy(metadata)
        cache[key] = {'metadata': value, 'metadataHash': native._digest(value)}


def _read_step_metadata(*, user, context, scope, _read_cache=None):
    """Reuse already-read metadata; native demand and allocation proofs still run.

    Only this call's typed cache is accepted. Its original atomic read owns the
    database snapshot, and a same-connection write invalidates the whole dict.
    Cached JSON is copied in both directions; source/preparation/model objects
    are never shared with a caller. A failed read cannot seed a metadata proof.
    """
    plan, _, _, _, step, kind, applicability = context
    on_date = native._today()
    key = _step_metadata_key(user, _read_cache, context, on_date)
    entry = _read_cache.get(key) if key is not None else None
    if (isinstance(entry, dict) and isinstance(entry.get('metadata'), dict)
            and entry.get('metadataHash') == native._digest(entry['metadata'])):
        return deepcopy(entry['metadata'])
    from .operation_input_preparation_service import read_preparation
    from .models import OperationInputPreparationDraft
    from .daily_capacity_service import capacity_source_rules
    has_preparation = OperationInputPreparationDraft.objects.filter(company_id=user.company_id,
        production_plan_id=plan.pk, routing_step_id=step.pk).exists()
    preparation = read_preparation(user=user, exact_scope=scope, read_cache=_read_cache) if has_preparation else None
    capacity_proof = capacity_source_rules(kind, company_id=user.company_id, on_date=on_date,
        read_cache=_read_cache)
    capacities = list(StandardCapacity.objects.filter(company_id=user.company_id, product_type_id=kind.pk,
        operation_id=step.operation_id).select_related('uom', 'product_type', 'operation', 'work_center'))
    semantics, facts = _step_capacity_semantics(user=user,
        scope={**scope, 'productTypeCode': kind.code, 'operationName': step.operation.name, 'sequence': step.sequence},
        applicability=applicability, source_rules=capacity_proof, capacities=capacities, preparation=preparation)
    metadata = {'inputPreparation': preparation, 'capacitySemantics': semantics, 'standardCapacityFacts': facts}
    # A read crossing midnight or an in-memory exact-scope change must fall
    # through again, rather than labelling old dependencies with a new key.
    if key is not None and key == _step_metadata_key(user, _read_cache, context, on_date):
        _remember_step_metadata(user, _read_cache, context, metadata, on_date)
    return deepcopy(metadata)


WORKLOAD_REVIEW_CONTRACT = 'PCE-ROUTE-WORKLOAD-READ-V1'
_UNREAD_BUCKETS = {'NOT_READ', 'NOT_EVALUATED', 'READ_FAILED', 'PENDING', 'NOT_APPLICABLE'}


def _waiting_trigger(applicability):
    """Only a verified native plan-stage ruling can defer quantity preparation."""
    policy = (applicability or {}).get('conditionalExecution')
    return (policy if isinstance(policy, dict)
        and (applicability or {}).get('result') == 'PENDING'
        and policy.get('formalPolicyValidated') is True
        and policy.get('triggerStatus') == 'WAITING_TRIGGER' else None)


def _non_separate_quantity_policy(preparation, scope, applicability):
    """Accept only a proved native policy for this exact required plan step."""
    if not isinstance(preparation, dict) or (applicability or {}).get('result') != 'REQUIRED':
        return None
    policy = preparation.get('quantityPolicy')
    keys = ('companyId', 'productionPlanId', 'manufacturingOutputId', 'mainCalculationId',
        'salesOrderItemId', 'baselineId', 'routingVersionId', 'routingStepId', 'operationId', 'productTypeId')
    if (not isinstance(policy, dict) or preparation.get('factSource') != 'server'
            or preparation.get('recordStatus') != 'RECORDED'
            or type(preparation.get('recordId')) is not int or preparation['recordId'] <= 0
            or policy.get('contractVersion') != 'PCE-OPERATION-QUANTITY-POLICY-V1'
            or policy.get('measurementMode') != 'NOT_SEPARATELY_MEASURED'
            or policy.get('formalPolicyValidated') is not True
            or policy.get('nullReason') != 'NOT_SEPARATELY_MEASURED'
            or policy.get('scopeDetermination') != 'DRAWING_AND_SITE'
            or policy.get('objectCoverageClaimed') is not False
            or any(key not in policy or policy[key] is not None for key in ('plannedQuantity', 'actualQuantity'))
            or any(preparation.get(key) is not False for key in
                ('formalRulePublished', 'readyForGeneration', 'readyForAllocation', 'readyForScheduling'))
            or any(type((scope or {}).get(key)) is not int or scope[key] <= 0
                or preparation.get('exactScope', {}).get(key) != scope[key]
                or policy.get('exactScope', {}).get(key) != scope[key] for key in keys)):
        return None
    reference = policy.get('statisticalUomReference')
    if (not isinstance(reference, dict)
            or any(type(reference.get(key)) is not int or reference[key] <= 0 for key in
                ('uomId', 'sourceCompanyId', 'sourceProductionPlanId', 'sourceRoutingVersionId',
                 'sourceRoutingStepId', 'sourceOperationId'))
            or any(reference[ref] != scope[key] for ref, key in
                (('sourceCompanyId', 'companyId'), ('sourceProductionPlanId', 'productionPlanId'),
                 ('sourceRoutingVersionId', 'routingVersionId')))
            or reference['sourceRoutingStepId'] == scope['routingStepId']
            or any(not isinstance(policy.get(key), str) or not policy[key].strip() for key in
                ('statusLabel', 'plannedQuantityReasonLabel', 'actualQuantityReasonLabel', 'capacityIndependenceLabel'))
            or not isinstance(reference.get('uomLabel'), str) or not reference['uomLabel'].strip()
            or not isinstance(reference.get('proofHash'), str) or len(reference['proofHash']) != 64
            or any(char not in '0123456789abcdef' for char in reference['proofHash'])):
        return None
    return policy


def _compact_workload_item(value):
    """Transmit current facts and proof identities, not every frozen snapshot."""
    fields = {'id', 'operationRequirementId', 'allocationId', 'calculationId', 'sourceCalculationId',
        'sourceFactId', 'sourceDetailId', 'operationId', 'routingStepId', 'ruleId', 'ruleCode', 'ruleName',
        'ruleVersion', 'quantity', 'workloadQuantity', 'quantityBasis', 'basisQuantity', 'basisUomId',
        'uomId', 'uomLabel', 'requirementQuantity', 'requirementUOMId', 'auditId', 'sourceHash', 'inputHash',
        'generationKey', 'sourceCanonicalField', 'sourceProofPassed', 'newEorRuleEvaluated', 'statusLabel',
        'manufacturingModeId', 'workCenterId', 'standardCapacityId', 'manufacturingReferenceType',
        'manufacturingPreparationContext', 'objectCoverage', 'objectCoverageProof', 'nativeGenerationContext',
        'sourceEngineeringCalculationId', 'routingId', 'routingVersionId', 'factSource'}
    result = {key: deepcopy(val) for key, val in value.items() if key in fields}
    if isinstance(value.get('lifecycle'), dict):
        result['lifecycle'] = {key: deepcopy(value['lifecycle'][key])
            for key in ('statusCode', 'statusLabel', 'effective') if key in value['lifecycle']}
    return result


def _read_non_separate_workload(result, *, company_id, plan, base, item, step, projection):
    policy = _non_separate_quantity_policy(result.get('inputPreparation'), result['scope'], result['applicability'])
    if policy is None:
        return False
    result['quantityPolicy'] = deepcopy(policy)
    result['blockers'].extend(projection['blockers'])
    semantics = result.get('capacitySemantics', {})
    if semantics.get('valid') is not True or semantics.get('meaningCode') != 'NON_QUANTIFIED':
        result['blockers'].append({'code': 'QUANTITY_POLICY_CAPACITY_REFERENCE_CONFLICT',
            'statusLabel': '不单独计量政策的当前正式0产能引用未通过校验'})
    result['formalRequirements']['persistence'] = _workload_persistence(
        _workload_requirement_rows(company_id=company_id, base=base, item=item, step=step),
        operation_id=step.operation_id)
    result['savedAllocations']['persistence'] = _workload_persistence(
        ProductionPlanOperationRequirementAllocation.objects.filter(company_id=company_id,
            production_plan_id=plan.pk, routing_step_id=step.pk),
        operation_id=step.operation_id, allocation=True)
    if any(result[name]['persistence'].get('readStatus') == 'loaded'
            and result[name]['persistence'].get('recordCount', 0) > 0
            for name in ('formalRequirements', 'savedAllocations')):
        # Continue the ordinary native reader, so actual existing rows and
        # quantities are displayed and validated rather than concealed.
        result['blockers'].append({'code': 'QUANTITY_POLICY_PERSISTENCE_CONFLICT',
            'statusLabel': '不单独计量步骤出现正式需求或分配，必须保留实际记录并核对'})
        return False
    result['sourceCandidates'].update(statusCode='NOT_SEPARATELY_MEASURED',
        statusLabel='本步骤不单独计量，无需独立数量来源，不建立空壳来源规则')
    result['sourceConfiguration'].update(originalStatusLabel=projection['statusLabel'],
        statusLabel='随前工序配套，不单独计量；不以独立数量来源生成需求或分配')
    result['formalRequirements']['quantitySummary'] = []
    for name in ('formalRequirements', 'savedAllocations'):
        bucket = result[name]
        if bucket['persistence']['readStatus'] != 'loaded':
            bucket.update(statusCode='READ_FAILED', statusLabel=bucket['persistence']['statusLabel'])
            result['blockers'].append({'code': 'WORKLOAD_PERSISTENCE_READ_FAILED',
                'statusLabel': bucket['statusLabel'], 'factKey': name})
        else:
            bucket.update(statusCode='NOT_SEPARATELY_MEASURED',
                statusLabel='不单独计量，无需独立正式需求' if name == 'formalRequirements' else
                    '不单独计量，无需独立计划分配')
            bucket['persistence']['quantityStatusLabel'] = policy['plannedQuantityReasonLabel']
    result['workloadReview'] = _workload_row_review(
        {**result, 'sequence': step.sequence, 'operationName': step.operation.name},
        coverage={'statusCode': 'NOT_SEPARATELY_MEASURED',
            'statusLabel': '具体处理范围依图纸或现场加工方式确定，不预造逐门逐边覆盖'})
    return True


def _compact_workload_bucket(bucket):
    result = {key: deepcopy(val) for key, val in bucket.items() if key != 'items'}
    result['items'] = [_compact_workload_item(row) for row in bucket.get('items', [])]
    return result


def _workload_row_review(row, *, coverage):
    """Map independently read business layers to one Chinese presentation fact.

    A capacity role never grants a demand exemption. Engineering-only and
    auxiliary records retain their native requirement/load buckets verbatim.
    """
    formal, saved = row['formalRequirements'], row['savedAllocations']
    applicability = row['applicability'] or {}
    code = applicability.get('result')
    blockers = deepcopy(row.get('blockers', []))
    policy = _waiting_trigger(applicability)
    quantity_policy = _non_separate_quantity_policy(row.get('inputPreparation'), row.get('scope'), applicability)
    formal_count = None if formal['statusCode'] in _UNREAD_BUCKETS else len(formal['items'])
    allocation_count = None if saved['statusCode'] in _UNREAD_BUCKETS else len(saved['items'])
    if quantity_policy is not None:
        formal_count = (formal.get('persistence') or {}).get('recordCount')
        allocation_count = (saved.get('persistence') or {}).get('recordCount')
        if (not blockers and formal['statusCode'] == saved['statusCode'] == 'NOT_SEPARATELY_MEASURED'
                and formal_count == allocation_count == 0
                and all((bucket.get('persistence') or {}).get('readStatus') == 'loaded'
                    for bucket in (formal, saved))):
            reference = quantity_policy['statisticalUomReference']
            return {'statusCode': 'NOT_SEPARATELY_MEASURED', 'statusLabel': quantity_policy['statusLabel'],
                'sequence': row['sequence'], 'operationName': row['operationName'],
                'applicabilityLabel': '要求执行／必经', 'processingLabel': quantity_policy['capacityIndependenceLabel'],
                'sourceBusinessLabel': '随前工序配套，不单独计量',
                'formalRequirementStatusLabel': formal['statusLabel'], 'formalRequirementCount': 0,
                'allocationStatusLabel': saved['statusLabel'], 'allocationCount': 0,
                'formalRequirementPersistenceLabel': formal['persistence']['statusLabel'],
                'allocationPersistenceLabel': saved['persistence']['statusLabel'],
                'formalRequirementQuantitySummary': [], 'savedQuantity': None, 'uomLabel': None,
                'coverageStatusLabel': coverage['statusLabel'], 'blockers': [],
                'formalRequirementDisplayLabel': '不单独计量，无需独立数量需求；当前0条',
                'allocationDisplayLabel': '不单独计量，无需独立数量分配；当前0条',
                'savedQuantityDisplayLabel': f"不单独计量；统计单位：{reference['uomLabel']}",
                'sourceRuleDisplayLabel': '已保存不单独计量政策，不建立空壳数量来源',
                'sourceInputDisplayLabel': quantity_policy['plannedQuantityReasonLabel'],
                'quantityContractDisplayLabel': quantity_policy['actualQuantityReasonLabel']}
    if policy is not None:
        formal_count = (formal.get('persistence') or {}).get('recordCount')
        allocation_count = (saved.get('persistence') or {}).get('recordCount')
    if (policy is not None and not blockers
            and formal['statusCode'] == saved['statusCode'] == 'WAITING_TRIGGER'
            and formal_count == allocation_count == 0
            and all((bucket.get('persistence') or {}).get('readStatus') == 'loaded'
                for bucket in (formal, saved))):
        pending = policy['pendingScopeLabel']
        return {'statusCode': 'WAITING_TRIGGER', 'statusLabel': policy['triggerPolicyLabel'],
            'sequence': row['sequence'], 'operationName': row['operationName'],
            'applicabilityLabel': policy['triggerPolicyLabel'],
            'processingLabel': policy['capacityIndependenceLabel'],
            'sourceBusinessLabel': '异常触发后按实际处理方式承接正式来源',
            'formalRequirementStatusLabel': formal['statusLabel'], 'formalRequirementCount': 0,
            'allocationStatusLabel': saved['statusLabel'], 'allocationCount': 0,
            'formalRequirementPersistenceLabel': (formal.get('persistence') or {}).get('statusLabel', ''),
            'allocationPersistenceLabel': (saved.get('persistence') or {}).get('statusLabel', ''),
            'formalRequirementQuantitySummary': [], 'savedQuantity': None, 'uomLabel': None,
            'coverageStatusLabel': pending, 'blockers': [],
            'formalRequirementDisplayLabel': '当前待触发，无需预置投产数量；正式需求0条',
            'allocationDisplayLabel': '当前待触发，未生成分配；0条',
            'savedQuantityDisplayLabel': pending,
            'sourceRuleDisplayLabel': '异常触发后按实际处理方式选择正式来源',
            'sourceInputDisplayLabel': pending,
            'quantityContractDisplayLabel': '当前无需预置数量；触发后分别确认实际计量单位'}
    sources = row['sourceConfiguration'].get('sources', [])
    names = list(dict.fromkeys(value['ruleName'] for value in sources if value.get('ruleName')))
    source_label = '；'.join(names) if names else '尚无正式来源方案'
    processing = '按正式来源及已保存贡献承接投产量'
    if row.get('capacitySemantics', {}).get('preparationRulingOnly'):
        processing = '经过；精确准备裁决支持产能不可定量，投产数量仍独立核验'
    elif row.get('engineeringOnly'):
        processing = '工程需求用途；排除旧APS产能合同，投产来源、需求及分配分别读取核验'
    elif row.get('capacityRole') == 'AUXILIARY':
        semantics = row.get('capacitySemantics', {})
        processing = ('经过；产能不可定量、不计定量占用，当前独立投产闭环仍须按正式来源、需求及分配证明'
            if semantics.get('valid') is True and semantics.get('meaningCode') == 'NON_QUANTIFIED'
            else '正式配套层次；不据此豁免工程需求或将未知负荷写为0')
    if code == 'NOT_APPLICABLE':
        status, label = 'NOT_APPLICABLE', '有正式依据的当前对象不适用'
        processing = '按当前原生对象适用性保留不适用分支'
    elif policy is not None:
        status, label = 'BLOCKED', '条件准备已有正式裁决，但当前读取存在真实冲突'
    elif code != 'REQUIRED':
        status, label = 'PENDING', '当前投产适用性尚未证明'
    elif (blockers or formal['statusCode'] != 'EXISTS' or saved['statusCode'] != 'SAVED'
            or coverage['statusCode'] != 'PROVEN'):
        status, label = 'BLOCKED', '当前投产量存在真实缺项或尚未证明'
    else:
        status, label = 'SAVED', '正式需求、分配及投产量已保存，对象覆盖已证明'
    return {'statusCode': status, 'statusLabel': label, 'sequence': row['sequence'],
        'operationName': row['operationName'],
        'applicabilityLabel': (policy['triggerPolicyLabel'] if policy is not None else
            {'REQUIRED': '要求执行／必经', 'NOT_APPLICABLE': '当前对象正式不适用',
            'PENDING': '适用性待证明'}.get(code, '适用性未返回')), 'processingLabel': processing,
        'sourceBusinessLabel': source_label,
        'formalRequirementStatusLabel': formal['statusLabel'], 'formalRequirementCount': formal_count,
        'allocationStatusLabel': saved['statusLabel'], 'allocationCount': allocation_count,
        'formalRequirementPersistenceLabel': (formal.get('persistence') or {}).get('statusLabel', ''),
        'allocationPersistenceLabel': (saved.get('persistence') or {}).get('statusLabel', ''),
        'formalRequirementQuantitySummary': deepcopy(formal.get('quantitySummary', [])),
        'savedQuantity': saved.get('quantity'), 'uomLabel': saved.get('uomLabel'),
        'coverageStatusLabel': coverage['statusLabel'], 'blockers': blockers}


def _source_projection_key(company_id, plan, output, base, step_id, product_type_id):
    baseline = effective_baseline(plan)
    return ('workload_source_projection', company_id, plan.pk, output.pk, base.pk,
        base.input_hash, base.result_hash, baseline.pk,
        baseline.snapshot_hash, output.routing_version_id, step_id, product_type_id,
        native._digest(source_selection(plan)))


@read_span('routeWorkloads')
def _include_route_workloads(result, *, user, plan, output, item, _read_cache=None):
    """One current atomic plan read with bounded, actor-owned proof reuse."""
    from .daily_capacity_service import _validated_demand_object_coverage
    cache = native._source_read_cache(user, _read_cache)
    allocation_read = native.OperationRequirementService.read(user=user,
        production_plan_id=plan.pk, _read_cache=cache)
    result['planAllocationRead'] = {key: deepcopy(allocation_read[key]) for key in
        ('productionPlanId', 'resultCount', 'passed', 'statusLabel', 'blockers', 'businessWriteCount')}
    result['planAllocationRead']['allocations'] = deepcopy(allocation_read['allocations'])
    from .daily_capacity_service import _no_date_raw_read, _no_date_capacity_for_source
    version_ids = {row['effectiveVersion']['effectiveRoutingVersionId'] for row in result['rows']}
    route_keys = set(RoutingVersion.objects.filter(pk__in=version_ids).values_list(
        'routing__routing_code', 'routing__product_category_id', 'routing__manufacturing_process_type_id'))
    raw_read = _no_date_raw_read(user=user, operation_ids={row['operationId'] for row in result['rows']},
        read_cache=cache, routing_keys=route_keys)
    saved_rows = {row.pk: row for row in native._read_allocation_rows(user.company_id,
        production_plan_id=plan.pk, read_cache=cache)}
    # The metadata already declares the exact source context of every visible
    # step. Batch only those requested operations/fields per source version;
    # each step below still runs its original native validators independently.
    grouped = {}
    for row in result['rows']:
        group = grouped.setdefault(row['effectiveVersion']['mainCalculationId'],
            {'operations': set(), 'fields': set()})
        group['operations'].add(row['operationId'])
        group['fields'].update(source['sourceCanonicalField']
            for source in row['sourceConfiguration'].get('sources', []))
    for base_id, group in grouped.items():
        cache[('route_requested_source_rows', user.company_id, plan.pk, base_id, item.pk)] = {
            'operations': tuple(sorted(group['operations'])), 'fields': tuple(sorted(group['fields']))}
    for row in result['rows']:
        from .plan_step_context_service import resolve_step_context, bind_plan_context
        version_context = resolve_step_context(plan, row['routingStepId'], user=user, read_cache=cache)
        current_plan = bind_plan_context(plan, version_context)
        current_output, current_step = version_context['output'], version_context['step']
        baseline = effective_baseline(current_plan)
        baseline_pairs = native._read_once(cache, ('route_baseline_object_pairs', user.company_id,
            plan.pk, baseline.pk, baseline.snapshot_hash, item.pk), lambda: dict(
                OrderEngineeringBaselineItem.objects.filter(baseline__in=production_baselines(),baseline_id=baseline.pk,
                    design_item__sales_order_item_id=item.pk).values_list('pk', 'design_item_id')))
        cache[_source_projection_key(user.company_id, current_plan, current_output, effective_calculation(current_plan),
            current_step.pk, result['scope']['productTypeId'])] = deepcopy(row['sourceConfiguration'])
        current = read_for_plan(user=user, production_plan_id=plan.pk,
            routing_step_id=row['routingStepId'], _read_cache=cache)
        row['scope'] = deepcopy(current['scope'])
        row['effectiveVersion'] = deepcopy(current['effectiveVersion'])
        row['applicability'] = deepcopy(current['applicability'])
        row['sourceConfiguration'] = deepcopy(current['sourceConfiguration'])
        if 'capacitySemantics' in current:
            row['capacitySemantics'] = deepcopy(current['capacitySemantics'])
        row['blockers'] = deepcopy(current['blockers'])
        for key in ('sourceCandidates', 'formalRequirements', 'savedAllocations'):
            row[key] = _compact_workload_bucket(current[key])
        # The original preparation record is not rewritten. The overview sends
        # only its identity and formal interpretation; the step reader retains
        # the historical evidence for expansion on demand.
        preparation = current.get('inputPreparation')
        row['inputPreparation'] = ({key: deepcopy(preparation[key]) for key in
            ('recordStatus', 'recordId', 'revision', 'exactScope', 'capacitySemantics') if key in preparation}
            if isinstance(preparation, dict) else None)
        if isinstance(preparation, dict) and 'quantityPolicy' in preparation:
            row['inputPreparation'].update({key: deepcopy(preparation[key]) for key in
                ('contractVersion', 'factSource', 'quantityPolicy', 'formalRulePublished',
                 'readyForGeneration', 'readyForAllocation', 'readyForScheduling') if key in preparation})
            if 'quantityPolicy' in current:
                row['quantityPolicy'] = deepcopy(current['quantityPolicy'])
        found = None
        coverage = {'statusCode': 'NOT_OBTAINED', 'statusLabel': '尚未取得已保存贡献的对象覆盖证明',
            'designItemIds': None, 'baselineItemIds': None, 'inputFactIds': None, 'proofSource': None}
        demand = cache.get(('verified_process_demand', user.company_id, plan.pk, current_step.pk))
        if row['savedAllocations']['statusCode'] == 'SAVED' and demand is not None:
            try:
                found = _validated_demand_object_coverage(current_plan, current_output, item,
                    {'stepId': current_step.pk, 'operationId': row['operationId']}, demand,
                    company_id=user.company_id, read_cache=cache)
                partition = (row['applicability'] or {}).get('objectApplicability')
                expected = (set(partition['requiredBaselineItemIds']) if partition is not None else set(baseline_pairs))
                if (not expected or not expected <= set(baseline_pairs) or found['baselineItemIds'] != expected
                        or found['designItemIds'] != {baseline_pairs[pk] for pk in expected}):
                    _fail('WORKLOAD_SOURCE_COVERAGE_INCOMPLETE', '已保存贡献未恰好覆盖本步骤正式必经对象范围')
                coverage.update(statusCode='PROVEN', statusLabel='已证明精确对象覆盖，无重叠或遗漏',
                    proofSource='CURRENT_READ_VALIDATED_SOURCE_CHAIN',
                    **{key: sorted(found[key]) for key in ('designItemIds', 'baselineItemIds', 'inputFactIds')})
            except (native.DailyCapacityError, OperationWorkloadSourceError) as error:
                coverage.update(statusCode='UNPROVEN', statusLabel=getattr(error, 'message', str(error)))
                row['blockers'].append(_reason(error))
        elif _waiting_trigger(row['applicability']) is not None:
            coverage.update(statusCode='DEFERRED_UNTIL_TRIGGER',
                statusLabel=_waiting_trigger(row['applicability'])['pendingScopeLabel'])
        elif _non_separate_quantity_policy(row.get('inputPreparation'), row.get('scope'), row['applicability']) is not None:
            coverage.update(statusCode='NOT_SEPARATELY_MEASURED',
                statusLabel='具体处理范围依图纸或现场加工方式确定，不预造逐门逐边覆盖')
        elif (row['applicability'] or {}).get('result') == 'NOT_APPLICABLE':
            coverage.update(statusCode='NOT_APPLICABLE', statusLabel='当前对象正式不适用；未伪造分配覆盖证明')
        row['objectCoverage'] = coverage
        row['noDateCapacity'] = _no_date_capacity_for_source(user=user, source_read=current,
            read_cache=cache, raw_read=raw_read, saved_rows=saved_rows,
            coverage=found if coverage['statusCode'] == 'PROVEN' else None)
        row['workloadReview'] = _workload_row_review(row, coverage=coverage)
    reviews = [row['workloadReview'] for row in result['rows']]
    read_complete = all(row.get('scope', {}).get('routingStepId') == row['effectiveVersion']['effectiveRoutingStepId']
        and all(row[key]['statusCode'] not in {'NOT_READ', 'NOT_EVALUATED', 'READ_FAILED'}
            for key in ('sourceCandidates', 'formalRequirements', 'savedAllocations'))
        and all(not row[key].get('persistence') or row[key]['persistence']['readStatus'] == 'loaded'
            for key in ('formalRequirements', 'savedAllocations')) for row in result['rows'])
    business_complete = (read_complete and bool(reviews) and not allocation_read['blockers']
        and all(row['statusCode'] in {'SAVED', 'NOT_APPLICABLE', 'WAITING_TRIGGER', 'NOT_SEPARATELY_MEASURED'} for row in reviews))
    result.update(workloadReviewIncluded=True, workloadReviewContract=WORKLOAD_REVIEW_CONTRACT,
        readComplete=read_complete, businessComplete=business_complete)
    result['summary'].update(workloadStatusCode='COMPLETE' if business_complete else 'BLOCKED',
        workloadStatusLabel='当前投产量核对完成' if business_complete else '当前投产量已读取；真实未决事项保留',
        workloadReadStepCount=sum(row.get('scope', {}).get('routingStepId') == row['effectiveVersion']['effectiveRoutingStepId'] for row in result['rows']),
        savedWorkloadStepCount=sum(row['savedAllocations']['statusCode'] == 'SAVED' for row in result['rows']),
        formalRequirementRecordCount=sum(row['formalRequirementCount'] or 0 for row in reviews),
        allocationRecordCount=sum(row['allocationCount'] or 0 for row in reviews),
        coverageProvenStepCount=sum(row['objectCoverage']['statusCode'] == 'PROVEN' for row in result['rows']),
        waitingTriggerStepCount=sum(row['statusCode'] == 'WAITING_TRIGGER' for row in reviews),
        nonSeparateMeasurementStepCount=sum(row['statusCode'] == 'NOT_SEPARATELY_MEASURED' for row in reviews),
        workloadBlockedStepCount=sum(row['statusCode'] not in {'SAVED', 'NOT_APPLICABLE', 'WAITING_TRIGGER', 'NOT_SEPARATELY_MEASURED'} for row in reviews))
    result.update(noDateCapacityIncluded=True, noDateCapacityContract='PCE-ALLOCATED-LOAD-NO-DATE-CAPACITY-V1')
    no_date_rows = [row['noDateCapacity'] for row in result['rows']]
    result['noDateCapacitySummary'] = {'factSource': 'server', 'assessedAt': raw_read['assessedAt'],
        'readStepCount': len(no_date_rows), 'matchedStepCount': sum(row['noDateMatchPassed'] for row in no_date_rows),
        'legalEmptyLoadStepCount': sum(row['legalEmptyLoadVerified'] for row in no_date_rows),
        'nonQuantifiedSavedLoadStepCount': sum(row['stage'] == 'NON_QUANTIFIED_SAVED_LOAD' for row in no_date_rows),
        'notApplicableStepCount': sum(row['statusCode'] == 'NOT_APPLICABLE_VERIFIED' for row in no_date_rows),
        'waitingTriggerStepCount': sum(row['statusCode'] == 'WAITING_TRIGGER' for row in no_date_rows),
        'nonSeparateMeasurementStepCount': sum(row['statusCode'] == 'NOT_SEPARATELY_MEASURED_VERIFIED' for row in no_date_rows),
        'blockedStepCount': sum(bool(row['blockers']) for row in no_date_rows),
        'statusLabel': '当前各步骤无日期事实已读取；未形成整路线日期或排程资格',
        'planningReady': False, 'businessWriteCount': 0, 'auditWriteCount': 0,
        'resultHash': native._digest([row['resultHash'] for row in no_date_rows])}
    no_date_summary = result['noDateCapacitySummary']
    no_date_summary['statusLabel'] = (f"已读取{no_date_summary['readStepCount']}步：定量匹配{no_date_summary['matchedStepCount']}步、"
        f"有保存负荷但不可定量{no_date_summary['nonQuantifiedSavedLoadStepCount']}步、正式不适用{no_date_summary['notApplicableStepCount']}步、"
        f"待触发{no_date_summary['waitingTriggerStepCount']}步、不单独计量{no_date_summary['nonSeparateMeasurementStepCount']}步、"
        f"存在阻断{no_date_summary['blockedStepCount']}步；未评估日期或排程")
    result['workloadResultHash'] = native._digest({'scope': result['scope'], 'rows': result['rows'],
        'planAllocationRead': result['planAllocationRead'], 'readComplete': read_complete,
        'businessComplete': business_complete})


@transaction.atomic
@read_span('routeAggregate')
def read_route_overview(*, user, production_plan_id, include_workloads=False):
    """Batch metadata by default; current workload proofs are explicitly opt-in.

    Object decisions still use the native resolver. The exact plan/step absence
    query is batched within this same atomic read, so rows without records retain
    the resolver's unchanged legacy path without one existence query per step.
    """
    from .daily_capacity_service import _plan_capacity_context, capacity_source_rules
    from .routing_step_applicability_service import RoutingStepApplicabilityResolver

    _authorize(user, native.VIEW)
    _authorize(user, native.PLAN_VIEW)
    _authorize(user, RULE_VIEW)
    if type(include_workloads) is not bool:
        _fail('WORKLOAD_SOURCE_PAYLOAD_INVALID', '投产量读取选项必须为明确布尔值')
    _id(production_plan_id, '生产计划ID')
    cache = native._source_read_cache(user, None) if include_workloads else None
    plan = ProductionPlan.objects.filter(pk=production_plan_id,
        planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id).first()
    if plan is None:
        _fail('WORKLOAD_SOURCE_PLAN_MISSING', '所选计划不存在或不属于当前公司')
    try:
        plan, output, item, company_id = _plan_capacity_context(plan, user.company_id)
        steps = list(RoutingStep.objects.filter(routing_version_id=output.routing_version_id).select_related(
            'routing_version__routing', 'operation__calculation_uom', 'operation__work_center').order_by('sequence', 'pk'))
        if not steps:
            _fail('WORKLOAD_SOURCE_ROUTE_EMPTY', '计划固定的正式路线没有步骤')
        anchor = next((step for step in steps if native._active(step) and native._active(step.operation)), None)
        if anchor is None:
            _fail('WORKLOAD_SOURCE_ROUTE_EMPTY', '计划固定的正式路线没有当前有效步骤')
        original_plan, original_output, original_item = plan, output, item
        _, anchor_output, _, _, _, kind, first_applicability = _scope_context(user, plan.pk, anchor.pk,
            _read_cache=cache)
        plan, output, item, base = original_plan, original_output, original_item, original_output.engineering_calculation
        if anchor_output.pk != output.pk:
            first_applicability = None
    except native.DailyCapacityError as error:
        raise OperationWorkloadSourceError(error.code, error.message, getattr(error, 'details', {})) from error
    except ValidationError:
        _fail('WORKLOAD_SOURCE_CONTEXT_INVALID', '计划制造输出或正式来源上下文校验未通过')
    if any(step.operation.company_id != company_id for step in steps):
        _fail('WORKLOAD_SOURCE_STEP_MISMATCH', '路线含有不属于当前公司的工序')
    routing_id = output.routing_version.routing_id
    projected = project_operation_sources([step.operation for step in steps], company_id,
        product_type_id=kind.pk, _apply_selection=False)
    capacities = list(StandardCapacity.objects.filter(company_id=company_id, product_type_id=kind.pk,
        operation_id__in={step.operation_id for step in steps}).select_related('uom', 'product_type', 'operation', 'work_center'))
    metadata_date = native._today()
    capacity_proof = capacity_source_rules(kind, company_id=company_id, on_date=metadata_date,
        **({'read_cache': cache} if cache is not None else {}))
    manifest = capacity_proof.get('manifest', {})
    from .models import OperationInputPreparationDraft, PlanStepVersionBinding
    bound_roots = set(PlanStepVersionBinding.objects.filter(production_plan_id=plan.pk).values_list('root_step_id', flat=True))
    bound_targets = set(PlanStepVersionBinding.objects.filter(production_plan_id=plan.pk).values_list('target_step_id', flat=True))
    scope_step_ids = [step.pk for step in steps] + list(bound_targets)
    object_steps = set(RoutingStepObjectApplicability.objects.filter(production_plan_id=plan.pk,
        routing_step_id__in=scope_step_ids).values_list('routing_step_id', flat=True))
    preparation_steps = set(OperationInputPreparationDraft.objects.filter(company_id=company_id,
        production_plan_id=plan.pk, routing_step_id__in=scope_step_ids).values_list('routing_step_id', flat=True))
    center_ids = {value for step in steps for value in (step.work_center_id, step.operation.work_center_id) if value}
    center_ids.update(row.work_center_id for row in capacities if row.work_center_id)
    centers = {row.pk: row for row in WorkCenter.objects.filter(company_id=company_id, pk__in=center_ids)}
    rows = []
    original_context = plan, output, item, base
    for root in steps:
        plan, output, item, base = original_context
        step, bound_applicability = root, None
        from .plan_step_context_service import resolve_step_context, version_fact
        version_context = ({'plan':plan, 'originalOutput':output, 'output':output,
            'root_step':root, 'step':root, 'binding':None, 'bindingProof':None}
            if root.pk not in bound_roots else resolve_step_context(plan, root.pk, user=user, read_cache=cache))
        if root.pk in bound_roots:
            plan, output, item, base, step, _, bound_applicability = _scope_context(user, plan.pk, root.pk, _read_cache=cache)
        context = {'routingId': output.routing_version.routing_id, 'routingVersionId': output.routing_version_id, 'routingStepId': step.pk}
        configuration = restrict_operation_projection(projected[step.operation_id], context)
        if bound_applicability is not None:
            applicability = bound_applicability
        elif step.pk == anchor.pk and first_applicability is not None:
            applicability = first_applicability
        else:
            applicability = RoutingStepApplicabilityResolver.resolve(step, engineering_calculation=base,
                engineering_document_version=output.engineering_document_version,
                order_engineering_instance=base.engineering_instance,
                order_engineering_baseline=effective_baseline(plan), bom_version=output.bom_version,
                production_plan=plan if step.pk in object_steps or step.pk in preparation_steps else None,
                manufacturing_output=output, read_cache=cache)
        if native._active(step) and native._active(step.operation):
            _remember_scope(user, cache, (plan, output, item, base, step, kind, applicability))
        role = 'UNKNOWN'
        if capacity_proof['status'] == 'VALID':
            if step.operation_id in manifest.get('nonApplicableOperationIds', []):
                role = 'NON_APPLICABLE'
            elif step.operation_id in manifest.get('auxiliaryOperationIds', []):
                role = 'AUXILIARY'
            elif step.operation_id in manifest.get('applicableOperationIds', []):
                role = 'INDEPENDENT'
        role_labels = {'UNKNOWN': '正式产能来源未证明该工序角色',
            'NON_APPLICABLE': '正式产能来源声明此产品不经过该工序',
            'AUXILIARY': '正式配套工序；不以缺独立日产能或独立来源规则判为未就绪',
            'INDEPENDENT': '正式来源声明为独立日产能工序'}
        blockers = deepcopy(configuration['blockers'])
        engineering_only = role == 'NON_APPLICABLE' and _engineering_only_configuration(configuration)
        conflict = role == 'NON_APPLICABLE' and applicability.get('result') == 'REQUIRED' and not engineering_only
        if conflict:
            blockers.append({'code': 'WORKLOAD_SOURCE_APPLICABILITY_LAYERS_DIFFER',
                'statusLabel': '产能来源声明不经过，路线解析仍要求执行；两层适用性需分别核对'})
        if capacity_proof['status'] != 'VALID':
            blockers.append({'code': 'WORKLOAD_SOURCE_CAPACITY_SOURCE_UNPROVEN',
                'statusLabel': capacity_proof['fact']['statusLabel']})
        if not native._active(step) or not native._active(step.operation):
            blockers.append({'code': 'WORKLOAD_SOURCE_STEP_INACTIVE', 'statusLabel': '正式步骤或工序当前无效'})
        needs_source = (applicability.get('result') != 'NOT_APPLICABLE'
            and _waiting_trigger(applicability) is None and role not in {'NON_APPLICABLE', 'AUXILIARY'})
        if needs_source and not configuration['hasValidSourceConfiguration'] and not configuration['blockers']:
            blockers.append({'code': 'OPERATION_RULE_MAPPING_MISSING', 'statusLabel': configuration['statusLabel']})
        active_rules = configuration['sources']
        bindings = [{'ruleId': row['ruleId'], 'manufacturingModeId': row['manufacturingModeId'],
            'workCenterId': row['workCenterId'], 'standardCapacityId': row['standardCapacityId'], 'uomId': row['uomId']}
            for row in active_rules]
        exact_scope = {'companyId': company_id, 'productionPlanId': plan.pk, 'manufacturingOutputId': output.pk,
            'mainCalculationId': base.pk, 'salesOrderItemId': item.pk, 'baselineId': getattr(effective_baseline(plan), 'pk', None),
            'routingVersionId': output.routing_version_id, 'routingStepId': step.pk,
            'operationId': step.operation_id, 'productTypeId': kind.pk}
        preparation = None
        if step.pk in preparation_steps:
            from .operation_input_preparation_service import read_preparation
            preparation = read_preparation(user=user, exact_scope=exact_scope,read_cache=cache)
        scoped_capacities = [cap for cap in capacities if cap.operation_id == step.operation_id]
        semantics, capacity_facts = _step_capacity_semantics(user=user,
            scope={**exact_scope, 'productTypeCode': kind.code, 'operationName': step.operation.name, 'sequence': step.sequence},
            applicability=applicability, source_rules=capacity_proof, capacities=scoped_capacities, preparation=preparation)
        if native._active(step) and native._active(step.operation):
            _remember_step_metadata(user, cache, (plan, output, item, base, step, kind, applicability),
                {'inputPreparation': preparation, 'capacitySemantics': semantics,
                    'standardCapacityFacts': capacity_facts}, metadata_date)
        original_source_role, original_source_conflict = role, conflict
        if semantics.get('preparationRulingOnly'):
            # The source matrix remains traceable, while every current machine
            # field follows the same exact-scope ruling as the displayed label.
            role, conflict, engineering_only = 'AUXILIARY', False, False
            needs_source = applicability.get('result') != 'NOT_APPLICABLE'
            blockers = [item for item in blockers if item.get('code') != 'WORKLOAD_SOURCE_APPLICABILITY_LAYERS_DIFFER']
            if needs_source and not configuration['hasValidSourceConfiguration'] and not configuration['blockers']:
                if not any(item.get('code') == 'OPERATION_RULE_MAPPING_MISSING' for item in blockers):
                    blockers.append({'code': 'OPERATION_RULE_MAPPING_MISSING', 'statusLabel': configuration['statusLabel']})
        fact_by_id = {fact['id']: fact for fact in capacity_facts}
        candidates = [{'id': cap.pk, 'code': cap.code, 'name': cap.name, 'operationId': cap.operation_id,
            'productTypeId': cap.product_type_id,
            'productTypeCode': fact_by_id[cap.pk]['productTypeCode'],
            'productTypeName': fact_by_id[cap.pk]['productTypeName'],
            'workCenterId': cap.work_center_id,
            'workCenterName': cap.work_center.name if cap.work_center_id else None, 'uomId': cap.uom_id,
            'uomLabel': cap.uom.name if cap.uom_id else None,
            'quantity': str(cap.quantity) if cap.quantity is not None else None,
            'timeBasis': cap.time_basis,
            'timeBasisQuantity': str(cap.time_basis_quantity) if cap.time_basis_quantity is not None else None,
            'timeUnit': cap.time_unit, 'timeUnitLabel': fact_by_id[cap.pk]['timeUnitLabel'],
            'measurementStatus': cap.measurement_status, 'currentlyActive': native._active(cap),
            'statusLabel': fact_by_id[cap.pk]['statusLabel'],
            'capacitySemantics': fact_by_id[cap.pk]['capacitySemantics']}
            for cap in scoped_capacities]
        relevant_centers = {value for value in (step.work_center_id, step.operation.work_center_id) if value}
        relevant_centers.update(cap['workCenterId'] for cap in candidates if cap['workCenterId'])
        selection = 'AMBIGUOUS' if configuration['statusCode'] == 'AMBIGUOUS' else 'RULE_BOUND' if any(
            row['standardCapacityId'] for row in bindings) else 'REFERENCE_ONLY'
        if _waiting_trigger(applicability) is not None and not blockers:
            status_code, label = 'WAITING_TRIGGER', _waiting_trigger(applicability)['triggerPolicyLabel']
        elif applicability.get('result') == 'NOT_APPLICABLE':
            status_code, label = 'NOT_APPLICABLE', '当前计划对象正式不适用；保留配置及产能层事实'
        elif conflict:
            status_code, label = 'APPLICABILITY_REVIEW', '适用性层次存在差异，待核对'
        elif applicability.get('result') == 'PENDING':
            status_code, label = 'PENDING', '当前步骤对象适用性待证明'
        elif blockers:
            status_code, label = configuration['statusCode'] if configuration['blockers'] else 'BLOCKED', '当前步骤配置仍有缺项或冲突'
        elif role == 'AUXILIARY':
            status_code, label = 'AUXILIARY', role_labels[role]
        elif engineering_only:
            status_code, label = 'ENGINEERING_ONLY', '工程需求用途，排除旧APS产能合同；投产需求与分配分别读取'
        else:
            status_code, label = 'CONFIGURATION_READ', '已读取配置元数据；来源、需求及负荷须按步骤核对'
        rows.append({'routingStepId': root.pk, 'sequence': root.sequence,
            'effectiveVersion': version_fact(version_context),
            'predecessorSequences': deepcopy(step.predecessor_sequences), 'operationId': step.operation_id,
            'operationCode': step.operation.code, 'operationName': step.operation.name,
            'uomId': step.operation.calculation_uom_id,
            'uomLabel': step.operation.calculation_uom.name if step.operation.calculation_uom_id else None,
            'applicability': applicability, 'sourceConfiguration': configuration,
            'capacitySemantics': semantics, 'inputPreparation': preparation,
            'resourceReferences': {'explicitStepWorkCenterId': step.work_center_id,
                'operationDefaultWorkCenterId': step.operation.work_center_id,
                'effectiveReferenceWorkCenterId': step.work_center_id or step.operation.work_center_id,
                'workCenters': [{'id': centers[pk].pk, 'code': centers[pk].code, 'name': centers[pk].name,
                    'workshopId': centers[pk].workshop_id,
                    'statusLabel': '当前有效工作中心' if native._active(centers[pk]) else '当前无效工作中心'}
                    for pk in sorted(relevant_centers) if pk in centers],
                'ruleResourceBindings': bindings, 'standardCapacityCandidates': candidates,
                'selectionStatusCode': selection, 'statusLabel': {'RULE_BOUND': '正式规则显式资源绑定',
                    'REFERENCE_ONLY': '资源参考；未由来源规则选定', 'AMBIGUOUS': '来源规则歧义，资源未唯一选定'}[selection]},
            'capacityRole': role, 'currentRole': role, 'originalSourceRole': original_source_role,
            'originalSourceConflict': original_source_conflict, 'capacitySourceStatus': capacity_proof['status'],
            'capacityApplicability': {'result': 'REQUIRED' if semantics.get('preparationRulingOnly') else role,
                'currentRole': role, 'originalSourceRole': original_source_role,
                'statusLabel': semantics['statusLabel'] if semantics.get('preparationRulingOnly') else role_labels[role],
                'originalSourceStatusLabel': role_labels[original_source_role],
                'sourceContract': manifest.get('contractVersion'), 'sourceSha256': manifest.get('sourceSha256'),
                'sourceStatusLabel': capacity_proof['fact']['statusLabel']},
            'formalRequirements': _bucket('NOT_READ', '总览未读取正式工序需求'),
            'savedAllocations': _bucket('NOT_READ', '总览未读取已保存负荷', quantity=True),
            'engineeringOnly': engineering_only,
            'needsSourceConfiguration': needs_source, 'statusCode': status_code, 'statusLabel': label, 'blockers': blockers})
        if _waiting_trigger(applicability) is not None:
            rows[-1]['operationDefaultUomReference'] = {
                'uomId': rows[-1]['uomId'], 'uomLabel': rows[-1]['uomLabel']}
            rows[-1].update(uomId=None, uomLabel=None)
        quantity_policy = _non_separate_quantity_policy(preparation, exact_scope, applicability)
        if quantity_policy is not None:
            reference = quantity_policy['statisticalUomReference']
            rows[-1]['quantityPolicy'] = deepcopy(quantity_policy)
            rows[-1]['operationDefaultUomReference'] = {
                'uomId': rows[-1]['uomId'], 'uomLabel': rows[-1]['uomLabel']}
            rows[-1].update(uomId=reference['uomId'], uomLabel=reference['uomLabel'],
                uomPurpose='STATISTICAL_ONLY_NO_INDEPENDENT_QUANTITY', needsSourceConfiguration=False)
    plan, output, item, base = original_context
    summary = {'stepCount': len(rows),
        'configuredCount': sum(row['sourceConfiguration']['hasValidSourceConfiguration'] for row in rows),
        'missingCount': sum(row['needsSourceConfiguration'] and row['sourceConfiguration']['statusCode'] in {'MISSING', 'LEGACY_UNBOUND'} for row in rows),
        'ambiguousCount': sum(row['sourceConfiguration']['statusCode'] == 'AMBIGUOUS' for row in rows),
        'invalidCount': sum(row['sourceConfiguration']['statusCode'] == 'INVALID' for row in rows),
        'notApplicableCount': sum(row['applicability']['result'] == 'NOT_APPLICABLE' for row in rows),
        'capacityNonApplicableCount': sum(row['capacityRole'] == 'NON_APPLICABLE' for row in rows),
        'auxiliaryCount': sum(row['capacityRole'] == 'AUXILIARY' for row in rows),
        'engineeringOnlyCount': sum(row['statusCode'] == 'ENGINEERING_ONLY' for row in rows),
        'applicabilityConflictCount': sum(row['statusCode'] == 'APPLICABILITY_REVIEW' for row in rows)}
    blocked = any(row['blockers'] or row['statusCode'] == 'PENDING' for row in rows)
    summary.update(statusCode='BLOCKED' if blocked else 'METADATA_READ',
        statusLabel='集中配置仍有缺项或适用性差异' if blocked else '路线配置元数据已读取；未评估正式需求或负荷')
    result = {'scope': {'companyId': company_id, 'productionPlanId': plan.pk, 'manufacturingOutputId': output.pk,
        'mainCalculationId': base.pk, 'salesOrderItemId': item.pk, 'baselineId': getattr(effective_baseline(plan), 'pk', None),
        'routingId': routing_id, 'routingVersionId': output.routing_version_id, 'productTypeId': kind.pk},
        'rows': rows, 'summary': summary, 'capacitySource': capacity_proof['fact'],
        'businessWriteCount': 0, 'auditWriteCount': 0, 'newEorRuleEvaluated': False,
        'generated': False, 'allocationSaved': False, 'wholeRouteReady': False}
    if include_workloads:
        _include_route_workloads(result, user=user, plan=plan, output=output, item=item, _read_cache=cache)
    return result


def _workload_requirement_rows(*, company_id, base, item, step=None):
    """The existing exact engineering source scope, shared by both read paths."""
    origins = Q(source_calculation=base) | Q(source_calculation__origin_calculation=base,
        source_calculation__scope='fact_extension', source_calculation__supersedes__isnull=True)
    rows = EngineeringOperationRequirement.objects.filter(origins,
        calculation__company_id=company_id,
        source_calculation__company_id=company_id, source_calculation__status='completed',
        source_calculation__source_record_id=base.source_record_id,
        source_calculation__sales_order_item_id=item.pk,
        source_calculation__engineering_instance_id=base.engineering_instance_id)
    return rows.filter(operation_id=step.operation_id) if step is not None else rows


def _scope_row_batch(cache, company_id, plan, base, item):
    cache = native._requirement_read_cache(cache, company_id)
    if cache is None:
        return None, None
    scope = cache.get(('route_requested_source_rows', company_id, plan.pk, base.pk, item.pk))
    if scope is None:
        return cache, None
    return cache, (base.pk, base.source_record_id, item.pk, base.engineering_instance_id,
        scope['operations'], scope['fields'])


def _read_requirement_rows(company_id, plan, base, item, step, cache):
    cache, batch = _scope_row_batch(cache, company_id, plan, base, item)
    def load():
        rows = _workload_requirement_rows(company_id=company_id, base=base, item=item,
            step=None if batch is not None else step)
        if batch is not None:
            rows = rows.filter(operation_id__in=batch[-2])
        return list(rows.select_related('calculation', 'source_fact', 'source_detail',
            'audit_record', 'uom').prefetch_related('source_detail__rule', 'source_calculation'))
    rows = (native._read_once(cache, ('route_scope_requirement_rows', company_id,
        plan.pk, *batch), load) if batch is not None else load())
    return [row for row in rows if row.operation_id == step.operation_id]


def _read_candidate_rows(company_id, plan, base, item, fields, cache):
    cache, batch = _scope_row_batch(cache, company_id, plan, base, item)
    def load():
        return list(EngineeringDerivedFact.objects.filter(
            Q(calculation=base) | Q(calculation__origin_calculation=base, calculation__scope='fact_extension',
                calculation__supersedes__isnull=True), calculation__company_id=company_id,
            calculation__status='completed', calculation__source_record_id=base.source_record_id,
            calculation__sales_order_item_id=item.pk, calculation__engineering_instance_id=base.engineering_instance_id,
            status='active', canonical_field__in=batch[-1] if batch is not None else fields
        ).select_related('source_detail', 'uom')
            .prefetch_related('source_detail__rule', 'rule', 'calculation__origin_calculation').order_by('pk'))
    rows = (native._read_once(cache, ('route_scope_candidate_rows', company_id,
        plan.pk, *batch), load) if batch is not None else load())
    return [row for row in rows if row.canonical_field in fields]


def _workload_persistence(queryset, *, operation_id, allocation=False):
    """Expose physical record presence independently of current applicability.

    A saved row is not a currently valid demand or load. Read no quantities,
    and never hide a step allocation whose operation association is wrong.
    """
    empty = '当前计划该工序尚未保存分配（0条）' if allocation else '当前工程范围尚无该工序已保存需求记录（0条）'
    noun = '当前计划步骤已保存分配' if allocation else '当前工程范围已保存工序需求'
    result = {'factSource': 'server', 'readStatus': 'read_failed', 'recordCount': None,
        'recordIds': None, 'operationMismatchRecordIds': None,
        'statusLabel': '当前保存记录读取失败，记录数未知', 'quantityStatusLabel': '数量未知'}
    try:
        # A database read failure rolls back this local savepoint, so the
        # surrounding current-fact read can return an explicit unknown state.
        with transaction.atomic():
            rows = list(queryset.order_by('pk').values_list('pk', 'operation_id'))
    except DatabaseError:
        return result
    ids = [pk for pk, _ in rows]
    mismatch = [pk for pk, actual_operation in rows if actual_operation != operation_id]
    label = empty if not rows else f'{noun}记录存在（{len(rows)}条）；本次有效性尚未核验'
    quantity_label = ('尚未保存分配，投产量未知' if allocation else '尚无已保存正式需求数量') if not rows else '已保存记录的本次有效数量尚未核验'
    if mismatch:
        label = f'{noun}记录存在工序关联不一致（{len(mismatch)}条）；不能认定为当前工序有效记录'
        quantity_label = '数量未知，已保存记录存在工序关联错误'
    result.update(readStatus='loaded', recordCount=len(rows), recordIds=ids,
        operationMismatchRecordIds=mismatch, statusLabel=label, quantityStatusLabel=quantity_label)
    return result


def _formal_requirement_quantity_summary(formal):
    """Sum only a fully native-validated demand bucket, grouping by formal UOM."""
    if formal.get('statusCode') != 'EXISTS':
        return []
    totals = {}
    for item in formal['items']:
        raw = item.get('workloadQuantity', item.get('quantity'))
        try:
            quantity = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            _fail('WORKLOAD_REQUIREMENT_SUMMARY_INVALID', '已校验正式需求的数量缺失或格式无效，不能汇总')
        uom_id, label = item.get('uomId'), item.get('uomLabel')
        if (not quantity.is_finite() or quantity <= 0 or type(uom_id) is not int or uom_id <= 0
                or not isinstance(label, str) or not label.strip()
                or 'workloadQuantity' in item and 'quantity' in item
                and item['quantity'] != item['workloadQuantity']):
            _fail('WORKLOAD_REQUIREMENT_SUMMARY_INVALID', '已校验正式需求的数量或正式单位不一致，不能汇总')
        if uom_id in totals and totals[uom_id]['uomLabel'] != label:
            _fail('WORKLOAD_REQUIREMENT_SUMMARY_INVALID', '同一正式单位的名称不一致，不能汇总')
        total = totals.setdefault(uom_id, {'quantity': Decimal(0), 'uomId': uom_id, 'uomLabel': label})
        total['quantity'] += quantity
    return [{**totals[key], 'quantity': format(totals[key]['quantity'], 'f')} for key in sorted(totals)]


@transaction.atomic
def read_for_plan(*, user, production_plan_id, routing_step_id, _read_cache=None, include_no_date=False):
    if type(include_no_date) is not bool:
        _fail('NO_DATE_READ_FLAG_INVALID', '无日期读取标记必须是明确布尔值')
    if not include_no_date:
        return _read_for_plan(user=user, production_plan_id=production_plan_id,
            routing_step_id=routing_step_id, _read_cache=_read_cache)
    _authorize(user, native.VIEW)
    _authorize(user, native.PLAN_VIEW)
    cache = native._source_read_cache(user, _read_cache)
    result = _read_for_plan(user=user, production_plan_id=production_plan_id,
        routing_step_id=routing_step_id, _read_cache=cache)
    from .daily_capacity_service import _no_date_capacity_for_source
    result.update(noDateCapacityIncluded=True, noDateCapacityContract='PCE-ALLOCATED-LOAD-NO-DATE-CAPACITY-V1',
        noDateCapacity=_no_date_capacity_for_source(user=user, source_read=result, read_cache=cache))
    return result


@read_span('stepRead')
def _read_for_plan(*, user, production_plan_id, routing_step_id, _read_cache=None):
    _authorize(user, native.VIEW)
    _authorize(user, native.PLAN_VIEW)
    _id(production_plan_id, '生产计划ID')
    _id(routing_step_id, '路线步骤ID')
    cache = native._source_read_cache(user, _read_cache)
    result = {'contractVersion': CONTRACT, 'factSource': 'server', 'scope': {}, 'applicability': None,
        'sourceConfiguration': {'statusCode': 'NOT_EVALUATED', 'statusLabel': '尚未核对正式配置', 'rules': [], 'blockers': []},
        'sourceCandidates': _bucket('NOT_EVALUATED', '尚未核对来源工程事实'),
        'formalRequirements': _bucket('NOT_EVALUATED', '尚未核对正式工序需求'),
        'savedAllocations': _bucket('NOT_EVALUATED', '尚未读取已保存分配', quantity=True),
        'blockers': [], 'businessWriteCount': 0, 'auditWriteCount': 0,
        'newEorRuleEvaluated': False, 'generated': False, 'allocationSaved': False}
    try:
        plan, output, item, base, step, kind, applicability = _scope_context(user, production_plan_id, routing_step_id,
            _read_cache=cache)
    except Exception as error:
        if not isinstance(error, (ProductionFoundationError, native.DailyCapacityError, ValidationError)) and not hasattr(error, 'code'):
            raise
        result['blockers'].append(_reason(error))
        return result
    company_id = user.company_id
    from .plan_step_context_service import version_fact
    result['effectiveVersion'] = version_fact(getattr(plan, '_native_step_version_context', {
        'originalOutput':output, 'output':output, 'root_step':step, 'step':step, 'binding':None}))
    result['scope'] = {'companyId': company_id, 'productionPlanId': plan.pk, 'manufacturingOutputId': output.pk,
        'mainCalculationId': base.pk, 'salesOrderItemId': item.pk, 'baselineId': getattr(effective_baseline(plan), 'pk', None),
        'routingVersionId': output.routing_version_id, 'routingStepId': step.pk, 'operationId': step.operation_id,
        'productTypeId': kind.pk}
    # Existing source reads retain their original eligibility and permissions.
    # Only persisted preparation evidence adds the strict preparation contract.
    result.update(_read_step_metadata(user=user, context=(plan, output, item, base, step, kind, applicability),
        scope=result['scope'], _read_cache=cache))
    from .routing_step_applicability_service import RESULT_LABELS
    result['applicability'] = deepcopy(applicability)
    for object_fact in (result['applicability'].get('objectApplicability') or {}).get('objects', []):
        decision = object_fact.get('effectiveDecision', object_fact.get('decision'))
        if decision in RESULT_LABELS:
            object_fact['decisionLabel'] = RESULT_LABELS[decision]
    # Configuration and capacity are independent current server layers; an
    # object exclusion never erases an existing source plan or standard capacity.
    projection = native._read_once(cache,
        _source_projection_key(company_id, plan, output, base, step.pk, kind.pk),
        lambda: operation_source_configuration(step.operation, kind.pk,
            routing_context={'routingId': output.routing_version.routing_id,
                'routingVersionId': output.routing_version_id, 'routingStepId': step.pk}, _apply_selection=False))
    result['sourceConfiguration'] = {**projection, 'rules': projection['sources']}
    if _read_non_separate_workload(result, company_id=company_id, plan=plan,
            base=base, item=item, step=step, projection=projection):
        return result
    if applicability.get('result') != 'REQUIRED':
        policy = _waiting_trigger(applicability)
        code = ('WAITING_TRIGGER' if policy is not None else
            'NOT_APPLICABLE' if applicability.get('result') == 'NOT_APPLICABLE' else 'PENDING')
        label = (policy['pendingScopeLabel'] if policy is not None else
            '当前对象范围不适用该工序' if code == 'NOT_APPLICABLE' else '当前步骤对象适用性尚未证明')
        for name in ('sourceCandidates', 'formalRequirements', 'savedAllocations'):
            result[name].update(statusCode=code, statusLabel=label)
        result['formalRequirements']['persistence'] = _workload_persistence(
            _workload_requirement_rows(company_id=company_id, base=base, item=item, step=step),
            operation_id=step.operation_id)
        result['savedAllocations']['persistence'] = _workload_persistence(
            ProductionPlanOperationRequirementAllocation.objects.filter(company_id=company_id,
                production_plan_id=plan.pk, routing_step_id=step.pk),
            operation_id=step.operation_id, allocation=True)
        result['formalRequirements']['quantitySummary'] = []
        for name in ('formalRequirements', 'savedAllocations'):
            if result[name]['persistence']['readStatus'] == 'read_failed':
                result['blockers'].append({'code': 'WORKLOAD_PERSISTENCE_READ_FAILED',
                    'statusLabel': result[name]['persistence']['statusLabel'], 'factKey': name})
            elif policy is not None and result[name]['persistence']['recordCount'] != 0:
                result['blockers'].append({'code': 'CONDITIONAL_TRIGGER_PERSISTENCE_CONFLICT',
                    'statusLabel': '待触发步骤存在已保存需求或分配，必须保留并核对，不能豁免', 'factKey': name})
        if policy is not None:
            # Only the absence of pre-trigger quantities is deferred. Invalid
            # configurations, failed reads and existing saved rows stay visible.
            result['conditionalExecution'] = deepcopy(policy)
            result['conditionalCapacityPolicy'] = deepcopy(policy['conditionalCapacityPolicy'])
            result['blockers'].extend(projection['blockers'])
            if not projection['blockers']:
                result['sourceConfiguration'].update(originalStatusLabel=projection['statusLabel'],
                    statusLabel='当前待触发；异常发生后按实际处理方式承接正式作业量来源')
            for name in ('formalRequirements', 'savedAllocations'):
                if (result[name]['persistence']['readStatus'] == 'loaded'
                        and result[name]['persistence']['recordCount'] == 0):
                    result[name]['statusLabel'] = ('当前待触发，无需预置投产数量，未生成正式需求'
                        if name == 'formalRequirements' else '当前待触发，未生成计划分配')
                    result[name]['persistence']['quantityStatusLabel'] = policy['pendingScopeLabel']
                else:
                    result[name].update(statusCode='CONFLICT',
                        statusLabel=result[name]['persistence']['statusLabel'])
            result['workloadReview'] = _workload_row_review(
                {**result, 'sequence': step.sequence, 'operationName': step.operation.name},
                coverage={'statusCode': 'DEFERRED_UNTIL_TRIGGER', 'statusLabel': policy['pendingScopeLabel']})
        if code == 'PENDING':
            result['blockers'].append({'code': 'WORKLOAD_SOURCE_APPLICABILITY_PENDING', 'statusLabel': label})
        return result
    result['blockers'].extend(projection['blockers'])
    requirements = _read_requirement_rows(company_id, plan, base, item, step, cache)
    native._prefetch_requirement_history(requirements, company_id, cache)
    from .operation_requirement_correction_service import requirement_lifecycle, require_effective_requirement
    for requirement in requirements:
        try:
            native_context = native._validate_requirement(requirement, company_id, read_cache=cache)
            lifecycle = requirement_lifecycle(requirement, company_id, read_cache=cache) or {}
            if lifecycle.get('statusCode') == 'SUPERSEDED':
                continue
            require_effective_requirement(requirement, company_id, read_cache=cache)
            native._plan_source_consistency(company_id, plan, requirement, native_context=native_context,
                routing_step=step, read_cache=cache)
            if requirement.source_detail.rule.specification['outputs'][0].get('productTypeId') != kind.pk:
                _fail('ALLOCATION_PRODUCT_TYPE_MISMATCH', '正式需求与计划产能产品类型不一致')
            result['formalRequirements']['items'].append({**native._requirement_fact(requirement, read_cache=cache),
                'uomLabel': requirement.uom.name})
        except (native.OperationRequirementError, ProductionFoundationError) as error:
            result['formalRequirements']['blockers'].append({**_reason(error), 'operationRequirementId': requirement.pk})
    formal = result['formalRequirements']
    formal.update(statusCode='INVALID' if formal['blockers'] else 'EXISTS' if formal['items'] else 'MISSING',
        statusLabel='正式工序需求校验受阻' if formal['blockers'] else '存在原生校验通过的正式工序需求' if formal['items'] else '当前范围尚无正式工序需求')
    formal['quantitySummary'] = _formal_requirement_quantity_summary(formal)
    if formal['statusCode'] == 'MISSING':
        formal['blockers'].append({'code': 'OPERATION_REQUIREMENT_NOT_GENERATED', 'statusLabel': formal['statusLabel']})
    saved = result['savedAllocations']
    try:
        demand = native.process_demand_for_plan(plan, output, item,
            {'stepId': step.pk, 'operationId': step.operation_id}, company_id=company_id,
            user=user, read_cache=cache)
        cache[('verified_process_demand', company_id, plan.pk, step.pk)] = deepcopy(demand)
        if demand is None:
            saved.update(statusCode='MISSING', statusLabel='该计划步骤尚未保存分配，投产量未知')
            saved['blockers'].append({'code': 'PROCESS_DEMAND_PLAN_ALLOCATION_MISSING', 'statusLabel': saved['statusLabel']})
        else:
            rows = sorted(native._read_allocation_rows(company_id, production_plan_id=plan.pk,
                routing_step_id=step.pk, read_cache=cache), key=lambda row: row.pk)
            # Coverage is a current, actor-bound native read proof. Never add it
            # to a historical source snapshot or reconstruct it from quantities.
            contributions = demand.get('contributions')
            if (not isinstance(contributions, list)
                    or {entry.get('allocationId') for entry in contributions} != {row.pk for row in rows}
                    or len(contributions) != len(rows)):
                _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '当前原生贡献身份没有完整对应已保存分配')
            proofs = {entry['allocationId']: entry.get('objectCoverageProof') for entry in contributions}
            saved['items'] = [{'allocationId': row.pk, 'operationRequirementId': row.operation_requirement_id,
                'routingStepId': row.routing_step_id, 'quantity': str(row.allocated_quantity), 'uomId': row.uom_id,
                'uomLabel': step.operation.calculation_uom.name if row.uom_id == step.operation.calculation_uom_id else None,
                'auditId': row.audit_record_id,
                'sourceCalculationId': row.operation_requirement.source_calculation_id,
                'sourceFactId': row.operation_requirement.source_fact_id,
                'ruleId': row.operation_requirement.source_detail.rule_id,
                'ruleVersion': row.operation_requirement.source_detail.rule_version,
                'objectCoverageProof': deepcopy(proofs[row.pk])} for row in rows]
            proofs_by_requirement = {row.operation_requirement_id: proofs[row.pk] for row in rows}
            for requirement_fact in formal['items']:
                if requirement_fact['operationRequirementId'] in proofs_by_requirement:
                    requirement_fact['objectCoverageProof'] = deepcopy(
                        proofs_by_requirement[requirement_fact['operationRequirementId']])
            if demand['uomId'] != step.operation.calculation_uom_id:
                _fail('OPERATION_UOM_MISMATCH', '已保存负荷的原生计量单位与当前正式工序单位不一致')
            saved.update(statusCode='SAVED', statusLabel='已保存且通过原生校验的计划负荷',
                quantity=str(demand['quantity']), uomId=demand['uomId'], uomLabel=step.operation.calculation_uom.name)
    except (native.OperationRequirementError, ProductionFoundationError) as error:
        saved.update(statusCode='INVALID', statusLabel='已有分配校验受阻，负荷未知')
        saved['blockers'].append(_reason(error))
    result['blockers'].extend(formal['blockers'] + saved['blockers'])
    if not projection['hasValidSourceConfiguration']:
        result['sourceCandidates'].update(statusCode=projection['statusCode'], statusLabel=projection['statusLabel'])
        if not projection['blockers']:
            result['blockers'].append({'code': 'OPERATION_RULE_MAPPING_MISSING', 'statusLabel': projection['statusLabel']})
        return result
    facts = _read_candidate_rows(company_id, plan, base, item,
        {row['sourceCanonicalField'] for row in projection['sources']}, cache)
    objects = applicability.get('objectApplicability')
    expected = set(objects['requiredBaselineItemIds']) if objects is not None else set(
        OrderEngineeringBaselineItem.objects.filter(baseline__in=production_baselines(),baseline_id=getattr(effective_baseline(plan), 'pk', None),
            design_item__sales_order_item_id=item.pk).values_list('pk', flat=True))
    bucket = result['sourceCandidates']
    coverage_by_rule = {}
    for source in projection['sources']:
        for fact in facts:
            if not _candidate_matches(fact, source):
                continue
            try:
                context = native._generation_context(company_id, fact.calculation_id, fact.pk, source['ruleId'],
                    evaluate=False, read_cache=cache, user=user,
                    generation_context={'productionPlanId': plan.pk, 'routingStepId': step.pk})
                if context['product_type'].pk != kind.pk:
                    _fail('ALLOCATION_PRODUCT_TYPE_MISMATCH', '来源候选与计划产品类型不一致')
                if fact.calculation_id != base.pk:
                    proof = context['source_snapshot'].get('factExtension', {})
                    if (proof.get('baseEngineeringCalculationId') != base.pk
                            or proof.get('originInputHash') != base.input_hash or proof.get('originResultHash') != base.result_hash):
                        _fail('ALLOCATION_SOURCE_MISMATCH', '合法扩展未绑定计划当前主核算Hash')
                coverage = native._extension_object_coverage(company_id, base, fact.calculation, fact, output, read_cache=cache,
                    **({'baseline': effective_baseline(plan)} if source_selection(plan) is not None else {}))
                actual = set(coverage['baselineItemIds'])
                if not expected or not actual or not actual <= expected:
                    _fail('WORKLOAD_SOURCE_OBJECT_SCOPE_MISMATCH', '候选覆盖超出本次适用对象或无法证明对象范围，禁止比例拆分')
                occupied = coverage_by_rule.setdefault(source['ruleId'], set())
                if occupied & actual:
                    _fail('WORKLOAD_SOURCE_FACT_AMBIGUOUS', '同规则存在重叠对象的多个事实或重复汇总，不取首条也不相加')
                occupied.update(actual)
                bucket['items'].append({'ruleId': source['ruleId'], 'ruleCode': source['ruleCode'],
                    'ruleVersion': source['ruleVersion'], 'sourceCalculationId': fact.calculation_id,
                    'sourceFactId': fact.pk, 'sourceCanonicalField': fact.canonical_field,
                    'quantity': str(fact.value['decimal']), 'uomId': fact.uom_id, 'uomLabel': fact.uom.name,
                    'sourceHash': context['source_hash'], 'inputHash': context['input_hash'],
                    'generationKey': context['generation_key'], 'objectCoverage': coverage,
                    'sourceProofPassed': True, 'newEorRuleEvaluated': False,
                    **({'nativeGenerationContext': {'productionPlanId': plan.pk, 'routingStepId': step.pk}}
                       if source.get('capacityMode') == REFERENCE_TYPE else {}),
                    'statusLabel': '正式来源工程数量；本读取未求值或生成工序需求'})
            except (native.OperationRequirementError, ProductionFoundationError) as error:
                bucket['blockers'].append({**_reason(error), 'ruleId': source['ruleId'], 'sourceFactId': fact.pk})
    complete = bool(bucket['items']) and all(coverage_by_rule.get(row['ruleId'], set()) == expected for row in projection['sources'])
    bucket.update(statusCode='INVALID' if bucket['blockers'] else 'AVAILABLE' if complete else 'PARTIAL' if bucket['items'] else 'MISSING',
        statusLabel='来源候选校验受阻' if bucket['blockers'] else '已证明精确来源及适用对象；尚不代表需求生成或分配'
        if complete else '来源候选尚未完整覆盖适用对象' if bucket['items'] else '当前范围没有精确匹配且通过证明的来源事实')
    if not bucket['items'] and not bucket['blockers']:
        bucket['blockers'].append({'code': 'WORKLOAD_SOURCE_FACT_MISSING', 'statusLabel': bucket['statusLabel']})
    if bucket['statusCode'] == 'PARTIAL':
        bucket['blockers'].append({'code': 'WORKLOAD_SOURCE_COVERAGE_INCOMPLETE', 'statusLabel': bucket['statusLabel']})
    result['blockers'].extend(bucket['blockers'])
    return result


def _explicit_source_conditions(trace):
    """Validate authored scalar predicates without inferring any source facts."""
    if not isinstance(trace, dict) or not trace:
        _fail('WORKLOAD_SOURCE_EXPLICIT_CONDITIONS_INVALID', '显式来源条件必须为非空条件对象')
    for key, value in trace.items():
        if (not isinstance(key, str) or not key or key != key.strip() or not key.isprintable()
                or type(value) not in (str, int, bool, type(None))):
            _fail('WORKLOAD_SOURCE_EXPLICIT_CONDITIONS_INVALID',
                '条件键必须为无首尾空白或控制字符的文本，值仅允许文本、整数、布尔值或空值')
    return deepcopy(trace)


@transaction.atomic
def _prepare_configuration(*, user, operation_id, payload, reason):
    """Load current formal references once; the compiler below performs no I/O."""
    _id(operation_id, '工序ID')
    if not isinstance(payload, dict):
        _fail('WORKLOAD_SOURCE_PAYLOAD_INVALID', '必须提供结构化的正式来源配置字段')
    allowed = {'ruleCode', 'ruleName', 'version', 'effectiveFrom', 'effectiveTo', 'producerRuleId',
        'producerVersion', 'canonicalField', 'modeId', 'productTypeId', 'workCenterId', 'standardCapacityId',
        'traceEquals', 'sourceSelectorKey', 'quantityBasis', 'basisQuantity', 'basisUomId',
        'expression', 'routingContext', 'sourceSelectorMode', 'capacityMode'}
    if set(payload) - allowed:
        _fail('WORKLOAD_SOURCE_PAYLOAD_INVALID', '来源配置包含不支持字段', fields=sorted(set(payload) - allowed))
    operation = Process.objects.select_related('calculation_uom').filter(pk=operation_id, company_id=user.company_id).first()
    if not native._active(operation) or not operation.calculation_uom_id:
        _fail('WORKLOAD_SOURCE_OPERATION_INVALID', '必须选择同公司有效且已维护正式计量单位的工序')
    capacity_mode = payload.get('capacityMode', STANDARD_CAPACITY)
    if capacity_mode not in (STANDARD_CAPACITY, REFERENCE_TYPE):
        _fail('WORKLOAD_SOURCE_CONFIG_INVALID', '必须明确选择受支持的产能处理方式')
    for field in ('producerRuleId', 'modeId', 'productTypeId', 'workCenterId'):
        _id(payload.get(field), field)
    if capacity_mode == REFERENCE_TYPE:
        if payload.get('standardCapacityId') is not None:
            _fail('WORKLOAD_SOURCE_CONFIG_INVALID', '不可定量处理不得混入标准产能或伪零产能')
    else:
        _id(payload.get('standardCapacityId'), 'standardCapacityId')
    producer = EngineeringRuleDefinition.objects.filter(pk=payload['producerRuleId'], company_id=user.company_id, status='released').first()
    if not producer or not native._active(producer):
        _fail('WORKLOAD_SOURCE_PRODUCER_INVALID', '来源生产规则必须为同公司当前有效发布版本')
    units = list(UnitOfMeasure.objects.filter(company_id=user.company_id, is_active=True))
    try:
        source = _numeric_producer(producer, units)
    except EngineeringRuleError as error:
        raise OperationWorkloadSourceError(error.code, error.message, error.details) from error
    if not source or source['uomId'] != operation.calculation_uom_id:
        _fail('OPERATION_UOM_MISMATCH', '来源必须为唯一正式单位的数值型DERIVED_FACT，且与工序核算单位一致')
    if (payload.get('producerVersion', producer.version) != producer.version
            or payload.get('canonicalField', source['canonicalField']) != source['canonicalField']):
        _fail('WORKLOAD_SOURCE_PRODUCER_INVALID', '提交的来源版本或字段与正式生产规则不一致')
    mode = ManufacturingMode.objects.filter(pk=payload['modeId'], company_id=user.company_id, status='released').first()
    center = WorkCenter.objects.filter(pk=payload['workCenterId'], company_id=user.company_id).first()
    if not mode or not native._active(mode) or not native._active(center) or not center.workshop_id:
        _fail('WORKLOAD_SOURCE_REFERENCE_INVALID', '必须选择同公司有效的已发布模式及正式工作中心/车间')
    trace = payload.get('traceEquals', {})
    if not isinstance(trace, dict):
        _fail('WORKLOAD_SOURCE_PAYLOAD_INVALID', '来源追溯条件必须是结构化对象')
    selector_mode = payload.get('sourceSelectorMode', 'CATALOG')
    if selector_mode not in ('CATALOG', 'EXPLICIT_CONDITIONS'):
        _fail('WORKLOAD_SOURCE_SELECTOR_MODE_INVALID', '必须明确选择正式目录或显式维护来源条件')
    if selector_mode == 'EXPLICIT_CONDITIONS':
        if payload.get('sourceSelectorKey') not in (None, ''):
            _fail('WORKLOAD_SOURCE_TRACE_SCOPE_MISMATCH', '显式维护条件不得同时提交正式目录选项')
        if not isinstance(reason, str) or not reason.strip():
            _fail('WORKLOAD_SOURCE_PAYLOAD_INVALID', '显式维护来源条件必须提供办理原因')
        trace = _explicit_source_conditions(trace)
        options = []
    else:
        options = _formal_trace_options(_rules(user.company_id), source)
    if options:
        matching = [row for row in options if row['productTypeId'] == payload['productTypeId']]
        if not matching:
            _fail('WORKLOAD_SOURCE_TRACE_SCOPE_MISMATCH', '当前来源目录没有所选产品类型的正式条件')
        requested_key = payload.get('sourceSelectorKey')
        selected = ([row for row in matching if row['key'] == requested_key] if requested_key else
            [row for row in matching if canonical_json(row['traceEquals']) == canonical_json(trace)] if trace else
            matching if len(matching) == 1 else [])
        if len(selected) != 1:
            _fail('WORKLOAD_SOURCE_TRACE_SELECTION_REQUIRED', '必须明确选择当前产品类型的正式来源条件，不能取首项或使用通配条件')
        if trace and canonical_json(trace) != canonical_json(selected[0]['traceEquals']):
            _fail('WORKLOAD_SOURCE_TRACE_SCOPE_MISMATCH', '提交追溯条件与所选正式来源条件不一致')
        trace = deepcopy(selected[0]['traceEquals'])
    elif payload.get('sourceSelectorKey'):
        _fail('WORKLOAD_SOURCE_TRACE_SCOPE_MISMATCH', '所选来源条件已不在当前正式目录')
    for field in ('ruleCode', 'ruleName', 'version', 'effectiveFrom'):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            _fail('WORKLOAD_SOURCE_PAYLOAD_INVALID', f'{field}为正式配置必填项')
    quantity_basis = payload.get('quantityBasis', 'SOURCE_SCOPE_TOTAL')
    if quantity_basis not in native.KNOWN_BASES:
        _fail('QUANTITY_BASIS_MISSING', '必须选择现有正式数量口径')
    basis_unit = None
    if quantity_basis == 'PER_BASIS_QUANTITY':
        native._number(payload.get('basisQuantity'), 'QUANTITY_BASIS_MISSING')
        basis_unit = native._unit(_id(payload.get('basisUomId'), '基准单位'), user.company_id, 'QUANTITY_BASIS_MISSING')
    elif any(payload.get(key) not in (None, '') for key in ('basisQuantity', 'basisUomId')):
        _fail('QUANTITY_BASIS_MISMATCH', '来源总量使用订单行动态基数，不得混入固定基准数量或单位')
    expression = payload.get('expression', 'source_quantity')
    if not isinstance(expression, str) or not expression.strip():
        _fail('INVALID_EXPRESSION', '必须提供单一正式来源别名的受控表达式')
    spec = _compile_configuration(operation, payload, source, mode, center, trace, reason,
        quantity_basis, basis_unit, expression)
    validate_specification(spec)
    _validate_expression_unit(spec)
    persisted_spec = deepcopy(spec)
    persisted_spec['manufacturing'].pop('modeCode')
    persisted_spec['manufacturing']['modeId'] = mode.pk
    candidate = EngineeringRuleDefinition(company_id=user.company_id, rule_code=payload['ruleCode'],
        rule_name=payload['ruleName'], version=payload['version'], rule_kind='formula',
        specification=persisted_spec, status='released', effective_from=date.fromisoformat(payload['effectiveFrom']),
        effective_to=date.fromisoformat(payload['effectiveTo']) if payload.get('effectiveTo') else None)
    if candidate.effective_to and candidate.effective_to < candidate.effective_from:
        _fail('WORKLOAD_SOURCE_CONFIG_INVALID', '失效日期不得早于生效日期')
    from .manufacturing_rule_configuration import publication_config_validation
    validation = publication_config_validation(candidate, require_released=False)
    if 'routingContext' in payload:
        kinds = [{'id': row.pk, 'productCategoryId': row.product_category_id,
            'manufacturingProcessTypeId': row.manufacturing_process_type_id}
            for row in CapacityProductType.objects.filter(pk=payload['productTypeId'], company_id=user.company_id)]
        option = [row for row in _routing_options(user.company_id, kinds)
            if all(row[key] == payload['routingContext'].get(key) for key in ('routingId', 'routingVersionId', 'routingStepId'))]
        if len(option) != 1 or payload['productTypeId'] not in option[0]['productTypeIds']:
            _fail('MANUFACTURING_PRODUCT_TYPE_MISMATCH', '精确步骤与产品类型范围不一致')
    conflicts = _configuration_conflicts(candidate, operation)
    return {'operation': operation, 'producer': producer, 'source': source, 'mode': mode, 'workCenter': center,
        'candidate': candidate, 'nativeValidation': validation, 'conflicts': conflicts,
        'package': {'contractVersion': MANUFACTURING_CONTRACT, 'companyId': user.company_id,
            'modes': [], 'rules': [{'ruleCode': payload['ruleCode'], 'ruleName': payload['ruleName'],
                'version': payload['version'], 'effectiveFrom': payload['effectiveFrom'],
                'effectiveTo': payload.get('effectiveTo'), 'specification': spec}]}}


def _compile_configuration(operation, payload, source, mode, center, trace, reason,
                           quantity_basis, basis_unit, expression):
    """Pure shared compiler; omitted optional fields retain the original spec."""
    spec = {'rulePackage': {'code': payload['ruleCode'], 'version': payload['version']},
        'expression': expression, 'inputs': [{'canonicalName': 'source_quantity',
            'sourceCanonicalField': source['canonicalField'], 'sourceType': 'ENGINEERING_DERIVED',
            'valueType': 'decimal', 'unit': operation.calculation_uom.code,
            'unitDimension': operation.calculation_uom.dimension, 'required': True, 'unitRequired': True}],
        'outputs': [{'canonicalName': 'operation_quantity', 'resultDomain': 'OPERATION_REQUIREMENT',
            'valueType': 'decimal', 'unit': operation.calculation_uom.code,
            'unitDimension': operation.calculation_uom.dimension, 'uomId': operation.calculation_uom_id,
            'operationId': operation.pk, 'productTypeId': payload['productTypeId'],
            'quantityBasis': quantity_basis, 'basisQuantitySource': 'SALES_ORDER_ITEM',
            'basisUomSource': 'SALES_ORDER_ITEM', 'sourceScope': 'SALES_ORDER_ITEM'}],
        'dependencies': [], 'applicability': {'scope': 'fact_extension'},
        'decimalPrecision': 28, 'outputScale': 6, 'roundingMode': 'ROUND_HALF_UP',
        'sourceEvidence': {'reference': str(reason or '').strip(),
            'workloadDefinition': '工序管理明确绑定正式工程来源；来源总量不重复计入，不乘计划数量'},
        'manufacturing': {'contractVersion': MANUFACTURING_CONTRACT, 'modeCode': mode.code,
            'modeVersion': mode.version, 'workCenterId': center.pk, 'standardCapacityId': payload.get('standardCapacityId'),
            'factoryScope': {'companyId': operation.company_id, 'workshopId': center.workshop_id},
            'sourceSelector': {'canonicalField': source['canonicalField'], 'producerRuleId': source['id'],
                'producerRuleVersion': source['version'], 'traceEquals': deepcopy(trace)}, 'factDisposition': 'GENERATE_EOR'}}
    if payload.get('capacityMode') == REFERENCE_TYPE:
        spec['manufacturing']['capacityMode'] = REFERENCE_TYPE
    if quantity_basis == 'PER_BASIS_QUANTITY':
        output = spec['outputs'][0]
        output.pop('basisQuantitySource')
        output.pop('basisUomSource')
        output.update(basisQuantity=str(native._number(payload['basisQuantity'])), basisUomId=basis_unit.pk)
        spec['sourceEvidence']['workloadDefinition'] = '每正式基准数量作业量；按原生基准比例承接，不将其误作整订单总量'
    if 'routingContext' in payload:
        spec['manufacturing']['routingContext'] = deepcopy(payload['routingContext'])
    return spec


def _validate_expression_unit(spec):
    """Infer dimensions only using the native safe AST/dimension primitives.

    No substitute numerical workload is evaluated. Actual values are evaluated
    only by evaluate_specification after the selected plan's native proof.
    """
    tree = rule_foundation._parse_expression(spec['expression'], {'source_quantity'})
    dimension = rule_foundation._dimension(spec['inputs'][0]['unitDimension'])
    import ast
    def unit(node):
        if isinstance(node, ast.Name):
            return dimension, False
        if isinstance(node, ast.Constant):
            return {}, True
        if isinstance(node, ast.UnaryOp):
            return unit(node.operand)
        left, literal_left = unit(node.left)
        right, literal_right = unit(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if left == right:
                result = left
            elif literal_left and not left:
                result = right
            elif literal_right and not right:
                result = left
            else:
                _fail('UNIT_MISMATCH', '受控表达式加减维度与正式来源单位不一致')
        else:
            result = rule_foundation._combine_dimensions(left, right, 1 if isinstance(node.op, ast.Mult) else -1)
        return result, literal_left and literal_right
    if unit(tree.body)[0] != rule_foundation._dimension(spec['outputs'][0]['unitDimension']):
        _fail('UNIT_MISMATCH', '受控表达式输出维度必须等于正式工序单位')


def _new_source_independence_conflicts(proposed, selected):
    """Guard new adapter writes, without reinterpreting historical readers.

    A different field or producer is not evidence of an independent business
    contribution. Disjoint formal scope is excluded first; selectors on the
    same exact producer/field retain the original overlap/trace contract. The
    caller supplies sources retained by the original precedence contract.
    """
    conflicts = []
    for other in selected:
        if other is proposed or other.get('ruleId') == proposed.get('ruleId'):
            continue
        if other['productTypeId'] != proposed['productTypeId']:
            continue
        left_route, right_route = proposed.get('routingContext') or {}, other.get('routingContext') or {}
        if any(left_route.get(key) is not None and right_route.get(key) is not None
               and left_route[key] != right_route[key]
               for key in ('routingId', 'routingVersionId', 'routingStepId')):
            continue
        left, right = proposed['sourceSelector'], other['sourceSelector']
        same_origin = all(left.get(key) is not None and right.get(key) is not None
                          and left[key] == right[key]
                          for key in ('canonicalField', 'producerRuleId', 'producerRuleVersion'))
        # Same-source overlap or mutual exclusion remains governed by the
        # original projection; do not introduce a new trace proof mechanism.
        if same_origin:
            continue
        conflicts.append({'code': 'WORKLOAD_SOURCE_INDEPENDENCE_UNPROVEN',
            'statusLabel': '同一产品与路线范围的不同来源尚无独立贡献证明；不能同时发布',
            'ruleId': other['ruleId'], 'proposedSourceSelector': deepcopy(left),
            'existingSourceSelector': deepcopy(right)})
    return conflicts


def _configuration_conflicts(candidate, operation):
    """A new version never silently supersedes existing authoritative rules."""
    existing = EngineeringRuleDefinition.objects.filter(company_id=candidate.company_id,
        rule_code=candidate.rule_code, version=candidate.version).first()
    if existing:
        fields = ('rule_name', 'rule_kind', 'specification', 'effective_from', 'effective_to')
        if existing.status != 'released' or any(getattr(existing, key) != getattr(candidate, key) for key in fields):
            return [{'code': 'MANUFACTURING_VERSION_CONFLICT',
                'statusLabel': '已存在规则版本不可修改；来源与公式可只读核对，发布须使用合法的新版本及无冲突范围',
                'ruleId': existing.pk}]
        # Exact native replay creates no alternative version or new source.
        # Preserve the original idempotent contract, including visible current
        # projection blockers; a different payload never takes this path.
        return []
    output = candidate.specification['outputs'][0]
    projection = project_operation_sources([operation], candidate.company_id, output['productTypeId'])[operation.pk]
    proposed = _summary(candidate, operation, _references([candidate], [operation], candidate.company_id))
    projection['sources'] = [row for row in projection['sources'] if row['ruleId'] != candidate.pk]
    projection['sources'].append(proposed)
    context = proposed.get('routingContext')
    result = restrict_operation_projection(projection, context) if context else _finish_projection(projection)
    # A source hidden only by the exact, identical-family fallback contract is
    # not a competing contribution. All other retained sources need separation
    # proof for a new write, even where the historical reader permits both.
    retained_proposed = next((row for row in result['sources'] if row['ruleId'] == candidate.pk), None)
    conflicts = deepcopy(result['blockers'])
    if retained_proposed is not None:
        conflicts.extend(_new_source_independence_conflicts(retained_proposed, result['sources']))
    return conflicts


@transaction.atomic
def configure(*, user, operation_id, payload, reason, generation_context=None):
    """Compile once, reject conflicting scope, then call the sole native writer."""
    try:
        prepared = _prepare_configuration(user=user, operation_id=operation_id, payload=payload, reason=reason)
        if prepared['candidate'].specification['manufacturing'].get('capacityMode') == REFERENCE_TYPE:
            plan_preparation(user=user, generation_context=generation_context, operation=prepared['operation'],
                product_type=CapacityProductType.objects.get(pk=payload['productTypeId'], company_id=user.company_id),
                work_center=prepared['workCenter'])
        if prepared['conflicts']:
            code = ('MANUFACTURING_VERSION_CONFLICT' if any(row['code'] == 'MANUFACTURING_VERSION_CONFLICT'
                for row in prepared['conflicts']) else 'WORKLOAD_SOURCE_INDEPENDENCE_UNPROVEN'
                if any(row['code'] == 'WORKLOAD_SOURCE_INDEPENDENCE_UNPROVEN' for row in prepared['conflicts'])
                else 'WORKLOAD_SOURCE_RULE_AMBIGUOUS')
            _fail(code, '当前正式版本或所选配置范围冲突；未保存', conflicts=prepared['conflicts'])
        result = ManufacturingConfigurationService.configure(user=user, reason=reason, package=prepared['package'])
    except (native.OperationRequirementError, EngineeringRuleError) as error:
        raise OperationWorkloadSourceError(error.code, error.message, getattr(error, 'details', {})) from error
    except (ValueError, ValidationError):
        _fail('WORKLOAD_SOURCE_CONFIG_INVALID', '正式配置字段、日期或模型校验失败')
    return {'contractVersion': CONTRACT, 'factSource': 'server', 'operationId': prepared['operation'].pk,
        'configuration': operation_source_configuration(prepared['operation'], payload['productTypeId'],
            routing_context=payload.get('routingContext')),
        'nativeResult': result, 'generated': False, 'allocationSaved': False,
        'statusLabel': '正式作业量来源规则已由原生服务保存发布并读回；未生成需求或分配'}


@transaction.atomic
def preview_configuration(*, user, company_id, operation_id, payload, plan_id=None, routing_step_id=None):
    """Native, non-persistent draft proof; no generation/readiness/save call.

    Published identity conflicts remain separate from source/formula feedback.
    Draft outputs are never substituted for formal EOR or saved allocation.
    """
    _authorize(user, RULE_VIEW)
    _id(company_id, '公司ID')
    _id(operation_id, '工序ID')
    if user.company_id != company_id:
        _fail('ORGANIZATION_MISMATCH', '只能预览当前登录公司的正式配置')
    result = {'contractVersion': CONTRACT, 'factSource': 'server',
        'scope': {'companyId': company_id, 'operationId': operation_id,
            'productionPlanId': plan_id, 'routingStepId': routing_step_id},
        'requestPayload': deepcopy(payload), 'requestPayloadHash': specification_hash(payload),
        'configurationPreview': {'passed': False, 'statusCode': 'INVALID', 'statusLabel': '配置草稿尚未通过校验',
            'conflicts': [], 'blockers': [], 'isPersisted': False, 'proofKind': 'DRAFT_REFERENCE_VALIDATION'},
        'sourceQuantities': _bucket('NOT_EVALUATED', '本次草稿尚未读取正式来源数量'),
        'expressionOutputs': _bucket('NOT_EVALUATED', '本次草稿尚未计算预计表达式输出'),
        'formalRequirements': _bucket('NOT_READ', '尚未读取现行正式工序需求'),
        'savedAllocations': _bucket('NOT_READ', '尚未读取已保存负荷', quantity=True),
        'nativeValidation': {'specificationValid': False, 'publicationReferencesValid': False,
            'expressionUnitValid': False, 'actualSourceEvaluated': False,
            'requirementGenerationReadinessExecuted': False, 'savedRule': False},
        'configureAuthorization': _configure_authorization(user), 'blockers': [],
        'businessWriteCount': 0, 'auditWriteCount': 0, 'generated': False, 'allocationSaved': False}
    try:
        prepared = _prepare_configuration(user=user, operation_id=operation_id, payload=payload,
            reason='只读草稿校验，不保存；正式保存的来源引用由办理原因确定')
        candidate, operation = prepared['candidate'], prepared['operation']
        spec = candidate.specification
        preview = result['configurationPreview']
        preview.update(compiledSpecification=deepcopy(spec), normalizedSpecification=deepcopy(spec),
            specificationHash=specification_hash(spec), evaluationSemanticsHash=_evaluation_semantics_hash(spec),
            conflicts=prepared['conflicts'], nativePublicationValidation=prepared['nativeValidation'],
            isPersisted=False, proofKind='DRAFT_REFERENCE_VALIDATION',
            sourceEvidenceReferenceLabel='预览引用是技术说明；正式保存原因不会由预览代填业务事实')
        result['nativeValidation'].update(specificationValid=True, publicationReferencesValid=True, expressionUnitValid=True)
        if spec['manufacturing'].get('capacityMode') == REFERENCE_TYPE and (plan_id is None or routing_step_id is None):
            _fail('NON_QUANTIFIED_CONTEXT_REQUIRED', '不可定量草稿必须显式选定正式计划及步骤核验准备裁决')
        result['blockers'].extend(prepared['conflicts'])
        if (plan_id is None) != (routing_step_id is None):
            _fail('WORKLOAD_SOURCE_CONTEXT_REQUIRED', '计划和步骤必须同时提供，不能推断首个步骤')
        if plan_id is not None:
            _authorize(user, native.VIEW)
            _authorize(user, native.PLAN_VIEW)
            _id(plan_id, '计划ID')
            _id(routing_step_id, '步骤ID')
            plan, output, item, base, step, kind, applicability = _scope_context(user, plan_id, routing_step_id)
            if step.operation_id != operation_id or spec['outputs'][0]['productTypeId'] != kind.pk:
                _fail('ALLOCATION_PRODUCT_TYPE_MISMATCH', '草稿工序/产品类型与计划固定步骤不一致')
            selected_scope = {'routingId': output.routing_version.routing_id,
                'routingVersionId': output.routing_version_id, 'routingStepId': step.pk}
            declared = spec['manufacturing'].get('routingContext')
            if declared and not _routing_matches(declared, selected_scope):
                _fail('WORKLOAD_SOURCE_STEP_MISMATCH', '草稿精确步骤与当前预览计划范围不一致')
            current = read_for_plan(user=user, production_plan_id=plan_id, routing_step_id=routing_step_id)
            result['formalRequirements'] = current['formalRequirements']
            result['savedAllocations'] = current['savedAllocations']
            result['applicability'] = applicability
            if applicability['result'] != 'REQUIRED':
                _fail('WORKLOAD_SOURCE_APPLICABILITY_PENDING', '当前对象适用性未要求执行；不计算投入量', applicability=applicability)
            output_contract = spec['outputs'][0]
            basis_qty = (native._number(item.quantity) if output_contract['quantityBasis'] == 'SOURCE_SCOPE_TOTAL'
                else native._number(output_contract['basisQuantity']))
            basis_uom_id = (item.uom_id if output_contract['quantityBasis'] == 'SOURCE_SCOPE_TOTAL'
                else output_contract['basisUomId'])
            if basis_uom_id != item.uom_id:
                _fail('PLAN_QUANTITY_UOM_MISMATCH', '草稿正式基准单位必须与本订单行数量单位一致，禁止换算')
            selector = spec['manufacturing']['sourceSelector']
            facts = EngineeringDerivedFact.objects.filter(
                Q(calculation=base) | Q(calculation__origin_calculation=base, calculation__scope='fact_extension',
                    calculation__supersedes__isnull=True), calculation__company_id=company_id,
                calculation__status='completed', calculation__source_record_id=base.source_record_id,
                calculation__sales_order_item_id=item.pk, calculation__engineering_instance_id=base.engineering_instance_id,
                status='active', rule_id=selector['producerRuleId'], canonical_field=selector['canonicalField']
            ).select_related('calculation__origin_calculation', 'source_detail__rule', 'rule', 'uom')
            partition = applicability.get('objectApplicability')
            expected = set(partition['requiredBaselineItemIds']) if partition is not None else set(
                OrderEngineeringBaselineItem.objects.filter(baseline__in=production_baselines(),baseline_id=getattr(effective_baseline(plan), 'pk', None),
                    design_item__sales_order_item_id=item.pk).values_list('pk', flat=True))
            occupied = set()
            cache = native._source_read_cache(user, None)
            from .manufacturing_rule_configuration import validate_manufacturing_rule_context
            from .engineering_fact_extension_service import validate_extension_fact
            for fact in facts.order_by('pk'):
                if not _candidate_matches(fact, {'sourceSelector': selector}):
                    continue
                try:
                    detail = fact.source_detail
                    producer_proof = native._source_output_proof(fact.calculation, fact, detail, company_id)
                    if (detail.status != 'succeeded' or detail.calculation_id != fact.calculation_id
                        or detail.uom_id != fact.uom_id or native._number(detail.output_value.get('decimal')) != native._number(fact.value.get('decimal'))):
                        _fail('SOURCE_FACT_MISMATCH', '草稿来源事实与原生成功明细不一致')
                    extension_proof = (validate_extension_fact(fact.calculation, fact, read_cache=cache)
                        if fact.calculation_id != base.pk else None)
                    proof = validate_manufacturing_rule_context(rule=candidate, origin=fact.calculation, fact=fact,
                        operation=operation, uom=operation.calculation_uom, product_type=kind, read_cache=cache,
                        user=user, generation_context={'productionPlanId': plan_id, 'routingStepId': routing_step_id})
                    coverage = native._extension_object_coverage(company_id, base, fact.calculation, fact, output, read_cache=cache,
                        **({'baseline': effective_baseline(plan)} if source_selection(plan) is not None else {}))
                    actual = set(coverage['baselineItemIds'])
                    if not actual or not actual <= expected or occupied & actual:
                        _fail('WORKLOAD_SOURCE_FACT_AMBIGUOUS', '草稿来源覆盖不完整、越界或重叠，不取首条也不相加')
                    occupied.update(actual)
                    quantity = str(native._number(fact.value.get('decimal')))
                    source_row = {'sourceFactId': fact.pk, 'sourceCalculationId': fact.calculation_id,
                        'sourceCanonicalField': fact.canonical_field, 'quantity': quantity, 'sourceQuantity': quantity,
                        'uomId': fact.uom_id, 'uomLabel': fact.uom.name, 'objectCoverage': coverage,
                        'nativeProducerProof': producer_proof, 'nativeManufacturingProof': proof,
                        'nativeExtensionProof': extension_proof, 'statusLabel': '正式来源事实量，不是预计输出或已保存负荷'}
                    result['sourceQuantities']['items'].append(source_row)
                    evaluated = evaluate_specification(spec, {'source_quantity': {'value': quantity,
                        'unit': fact.uom.code, 'unitDimension': fact.uom.dimension}})
                    value = native._number(evaluated['value'])
                    result['expressionOutputs']['items'].append({'sourceFactId': fact.pk,
                        'sourceCalculationId': fact.calculation_id, 'expression': spec['expression'],
                        'inputAlias': 'source_quantity', 'sourceQuantity': quantity, 'outputQuantity': str(value),
                        'uomId': operation.calculation_uom_id, 'uomLabel': operation.calculation_uom.name,
                        'quantityBasis': output_contract['quantityBasis'], 'basisQuantity': str(basis_qty), 'basisUomId': basis_uom_id,
                        'statusLabel': '安全表达式预计输出；未生成需求或保存分配'})
                except (native.OperationRequirementError, ProductionFoundationError, EngineeringRuleError) as error:
                    result['sourceQuantities']['blockers'].append({**_reason(error), 'sourceFactId': fact.pk})
            complete = bool(expected) and occupied == expected and bool(result['expressionOutputs']['items'])
            source_blockers = result['sourceQuantities']['blockers']
            if not complete and not source_blockers:
                source_blockers.append({'code': 'WORKLOAD_SOURCE_COVERAGE_INCOMPLETE', 'statusLabel': '草稿来源尚未完整证明全部适用对象'})
            result['sourceQuantities'].update(statusCode='INVALID' if source_blockers else 'AVAILABLE',
                statusLabel='来源事实证明受阻' if source_blockers else '已核对草稿精确来源及完整对象覆盖')
            result['expressionOutputs'].update(statusCode='INVALID' if source_blockers else 'EVALUATED',
                statusLabel='预计输出校验受阻' if source_blockers else '已只读求值；仍不是正式需求或保存负荷')
            result['blockers'].extend(source_blockers)
            result['nativeValidation']['actualSourceEvaluated'] = complete and not source_blockers
        preview.update(passed=not result['blockers'], statusCode='BLOCKED' if result['blockers'] else 'VALID',
            statusLabel='草稿存在配置或来源阻断，未保存' if result['blockers'] else '草稿只读校验通过；未保存或发布')
    except (native.OperationRequirementError, ProductionFoundationError, EngineeringRuleError, ValidationError, ValueError) as error:
        blocker = _reason(error)
        result['blockers'].append(blocker)
        result['configurationPreview'].update(passed=False, statusCode='BLOCKED', statusLabel='草稿校验受阻，未保存')
    result['configurationPreview']['blockers'] = deepcopy(result['blockers'])
    return result
