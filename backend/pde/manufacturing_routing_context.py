from pde.baseline_usage_service import production_baselines, production_status
"""Opt-in formal routing/version/step proof for existing manufacturing EOR rules."""
from django.core.exceptions import ValidationError

from .manufacturing_structure_service import ManufacturingStructureError, ManufacturingStructureService
from .models import ProductManufacturingOutput, Routing, RoutingVersion, RoutingStep
from .routing_step_applicability_service import RoutingStepApplicabilityResolver, REQUIRED

CONTRACT = 'PCE-MANUFACTURING-ROUTING-CONTEXT-V1'


def _fail(code, message, **details):
    from .operation_requirement_service import _fail as fail
    fail(code, message, **details)


def routing_configuration(config):
    if 'routingContext' not in config:
        return None
    value = config['routingContext']
    if (not isinstance(value, dict)
            or set(value) != {'contractVersion', 'routingId', 'routingVersionId', 'routingStepId'}
            or value.get('contractVersion') != CONTRACT
            or any(type(value.get(key)) is not int or value[key] <= 0
                   for key in ('routingId', 'routingVersionId', 'routingStepId'))):
        _fail('MANUFACTURING_ROUTING_CONFIG_INVALID', '路线配置必须声明正式合同及精确Route/Version/Step正整数FK')
    return value


def _references(rule, spec, config, rows):
    declared = routing_configuration(config)
    if declared is None:
        return None
    from .manufacturing_rule_configuration import _active, _today
    route = Routing.objects.filter(pk=declared['routingId'], company_id=rule.company_id).first()
    version = RoutingVersion.objects.filter(pk=declared['routingVersionId'], routing_id=declared['routingId']).first()
    step = RoutingStep.objects.select_related('routing_version__routing', 'operation').filter(
        pk=declared['routingStepId'], routing_version_id=declared['routingVersionId']).first()
    if (not _active(route) or route.status != 'released' or not version or version.status != 'released'
            or (version.effective_date and version.effective_date > _today())
            or (version.expire_date and version.expire_date < _today())
            or not _active(step) or step.operation_id != rows['operation'].pk):
        _fail('MANUFACTURING_ROUTING_REFERENCE_INVALID', '路线、有效发布版本、精确步骤及正式工序必须一致')
    if step.work_center_id and step.work_center_id != rows['work_center'].pk:
        _fail('MANUFACTURING_ROUTING_RESOURCE_MISMATCH', '路线步骤资源与规则明确工作中心不一致')
    if step.workshop_id and step.workshop_id != rows['work_center'].workshop_id:
        _fail('MANUFACTURING_ROUTING_RESOURCE_MISMATCH', '路线步骤车间与正式工作中心不一致')
    evidence = spec.get('sourceEvidence', {}).get('formalRouting')
    if evidence is not None and (not isinstance(evidence, dict) or any(
            evidence.get(key) != expected for key, expected in {
                'routingId': route.pk, 'routingCode': route.routing_code,
                'routingVersionId': version.pk, 'routingVersion': version.routing_version,
                'routingStepId': step.pk, 'sequence': step.sequence, 'operationId': step.operation_id,
            }.items())):
        _fail('MANUFACTURING_ROUTING_EVIDENCE_MISMATCH', '规则正式路线证据与实际Route/Version/Step字段不一致')
    return route, version, step


def publication_routing_validation(rule, spec, config, rows):
    """Reference checks only; applicability needs the actual runtime source."""
    return _references(rule, spec, config, rows)


def validate_routing_context(*, rule, spec, config, rows, origin, fact, runtime_context=None):
    references = _references(rule, spec, config, rows)
    if references is None:
        return None
    route, version, step = references
    base = origin.origin_calculation if origin.scope == 'fact_extension' else origin
    if (base.scope != 'order_engineering' or base.status != 'completed'
            or any(getattr(base, key) != getattr(origin, key) for key in
                   ('company_id', 'source_record_id', 'sales_order_item_id', 'engineering_instance_id'))):
        _fail('MANUFACTURING_ROUTING_SOURCE_INVALID', '路线来源必须固定引用同一正式已完成订单工程核算')
    trace = fact.trace if isinstance(fact.trace, dict) else {}
    baseline_id = trace.get('baselineId')
    # Scope summaries legitimately inherit their object identities through
    # immutable input links rather than a top-level trace baseline. Recover
    # that identity only for a fully proved native extension, never for an
    # invalid explicit baseline or a direct source with missing identity.
    inherited_baseline = 'baselineId' not in trace and origin.scope == 'fact_extension'
    baseline_provenance = None
    if inherited_baseline:
        from .engineering_fact_extension_service import validate_extension_fact
        extension_proof = validate_extension_fact(origin, fact)
    elif type(baseline_id) is not int or baseline_id <= 0:
        _fail('MANUFACTURING_ROUTING_SOURCE_INVALID', '路线承接必须具有已证明的正式工程基线身份')
    if runtime_context is not None:
        from .operation_non_quantified_context import REFERENCE_TYPE
        scope = runtime_context['scope']
        output = runtime_context['output']
        plan = runtime_context['plan']
        if (config.get('capacityMode') != REFERENCE_TYPE
                or scope['companyId'] != rule.company_id or scope['mainCalculationId'] != base.pk
                or scope['productionPlanId'] != plan.pk or scope['manufacturingOutputId'] != output.pk
                or scope['routingVersionId'] != version.pk or scope['routingStepId'] != step.pk
                or output.engineering_calculation_id != base.pk
                or output.order_engineering_instance_id != base.engineering_instance_id
                or output.release_status != 'released_to_manufacturing'
                or (not inherited_baseline and output.order_engineering_baseline_id != baseline_id)):
            _fail('MANUFACTURING_ROUTING_SOURCE_INVALID', '显式不可定量计划上下文与所配路线及来源不一致')
        outputs = [output]
    else:
        outputs = ProductManufacturingOutput.objects.select_related(
            'bom_version__bom', 'order_engineering_baseline', 'engineering_document_version',
            'routing_version__routing', 'order_engineering_instance', 'engineering_calculation',
        ).filter(order_engineering_instance_id=base.engineering_instance_id,
                 engineering_calculation_id=base.pk, release_status='released_to_manufacturing')
        if not inherited_baseline:
            outputs = outputs.filter(order_engineering_baseline_id=baseline_id)
        outputs = list(outputs)
    if len(outputs) != 1:
        _fail('MANUFACTURING_ROUTING_OUTPUT_INVALID', '必须唯一对应同一核算/工程实例/基线的正式制造发布')
    output = outputs[0]
    if inherited_baseline:
        from .operation_requirement_service import _extension_object_coverage
        coverage = _extension_object_coverage(rule.company_id, base, origin, fact, output)
        baseline_provenance = {'proofKind': 'FORMAL_EXTENSION_OBJECT_COVERAGE',
            'factExtension': extension_proof, 'objectCoverage': coverage}
    baseline, bom = output.order_engineering_baseline, output.bom_version
    instance = base.engineering_instance
    from .manufacturing_rule_configuration import _today
    if (baseline.company_id != rule.company_id or production_status(baseline) != 'confirmed'
            or baseline.sales_order_id != base.sales_order_item.sales_order_id
            or output.engineering_status != 'ready'
            or (output.effective_date and output.effective_date > _today())
            or bom.status != 'released' or bom.source_calculation_id != base.pk
            or bom.order_engineering_instance_id != instance.pk):
        _fail('MANUFACTURING_ROUTING_OUTPUT_INVALID', '制造发布、BOM及确认基线与实际来源身份不一致')
    try:
        output.clean()
    except ValidationError as exc:
        _fail('MANUFACTURING_ROUTING_OUTPUT_INVALID', '正式制造发布的冻结来源及版本组合校验失败',
              errors=getattr(exc, 'message_dict', exc.messages))
    context = {
        'organizationId': rule.company_id, 'salesOrderItemId': base.sales_order_item_id,
        'orderEngineeringInstanceId': instance.pk, 'orderEngineeringBaselineId': baseline.pk,
        'engineeringCalculationId': base.pk, 'bomVersionId': bom.pk,
    }
    try:
        resolved = ManufacturingStructureService.resolve_effective_routing(
            instance, on_date=_today(), exact_version_context=context)
    except ManufacturingStructureError as exc:
        _fail('MANUFACTURING_ROUTING_VERSION_INVALID', exc.message, resolverCode=exc.code, **exc.details)
    if (resolved['routing'].pk != route.pk or resolved['routing_version'].pk != version.pk
            or output.routing_version_id != version.pk):
        _fail('MANUFACTURING_ROUTING_VERSION_MISMATCH', '配置版本必须等于正式来源解析及制造发布锁定的适用版本',
              configuredVersionId=version.pk, resolvedVersionId=resolved['routing_version'].pk,
              outputVersionId=output.routing_version_id)
    applicability = RoutingStepApplicabilityResolver.resolve(
        step, engineering_calculation=base, engineering_document_version=output.engineering_document_version,
        order_engineering_instance=instance, order_engineering_baseline=baseline, bom_version=bom,
        **({'production_plan': runtime_context['plan'], 'manufacturing_output': output}
           if runtime_context is not None else {}))
    if applicability['result'] != REQUIRED:
        _fail('MANUFACTURING_ROUTING_STEP_NOT_REQUIRED', '正式来源上下文未证明本路线步骤必须执行',
              applicability=applicability)
    from .operation_requirement_service import _digest
    from .production_foundation_service import _snapshot
    return {
        'contractVersion': CONTRACT, 'factSource': 'server',
        'sourceEngineeringCalculationId': base.pk, 'sourceFactCalculationId': origin.pk,
        'sourceFactId': fact.pk, 'manufacturingOutputId': output.pk,
        'context': context, 'routingId': route.pk, 'routingCode': route.routing_code,
        'routingVersionId': version.pk, 'routingVersion': version.routing_version,
        'routingStepId': step.pk, 'sequence': step.sequence, 'operationId': step.operation_id,
        'workCenterId': rows['work_center'].pk, 'standardCapacityId': rows['capacity'].pk if rows['capacity'] else None,
        'productTypeId': rows['product_type'].pk, 'uomId': rows['uom'].pk,
        'resolvedScope': resolved['resolved_scope'], 'stepApplicability': applicability,
        'formalSourceHashes': {
            'engineeringCalculationInputHash': base.input_hash, 'engineeringCalculationResultHash': base.result_hash,
            'baselineSnapshotHash': baseline.snapshot_hash,
            'manufacturingOutputHash': _digest(_snapshot(output)), 'bomVersionHash': _digest(_snapshot(bom)),
            'routingHash': _digest(_snapshot(route)), 'routingVersionHash': _digest(_snapshot(version)),
            'routingStepHash': _digest(_snapshot(step)),
        },
        **({'baselineProvenance': baseline_provenance} if inherited_baseline else {}),
    }
