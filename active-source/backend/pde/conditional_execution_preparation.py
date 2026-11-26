from pde.baseline_usage_service import production_baselines, production_status
"""Plan/step preparation for a declared condition which has not occurred.

The anchor is proven, while affected objects are deliberately not claimed.
Persistence and its entire independent proof remain owned by the native input
preparation service. This contract cannot trigger work or quantify a workload.
"""
from copy import deepcopy

from django.db import transaction

CONTRACT = 'PCE-CONDITIONAL-EXECUTION-PREPARATION-V1'
CONDITION = 'QUALITY_EXCEPTION_TRIGGERED'
LABEL = '品质异常触发时执行，当前待触发'
COVERAGE = {'scopeType': 'PLAN_STEP_CONDITION', 'status': 'UNKNOWN_UNTIL_TRIGGER',
    'objects': None, 'parts': None}
CAPACITY_POLICY = {'appliesWhen': 'TRIGGERED', 'meaningCode': 'NON_QUANTIFIED',
    'sourceValue': '0', 'quantitativeOccupancyAllowed': False,
    'independentDurationAllowed': False}
QUANTITY_CONTRACT = 'PCE-OPERATION-QUANTITY-POLICY-V1'
QUANTITY_MODE = 'NOT_SEPARATELY_MEASURED'
QUANTITY_LABEL = '常规必经配套，不单独统计计划投产量或实际产量'
QUANTITY_COVERAGE = {'scopeType': 'PLAN_STEP_QUANTITY_POLICY',
    'status': 'DETERMINED_BY_DRAWING_AND_SITE', 'objects': None, 'parts': None}


def is_conditional_basis(value):
    # A malformed marker must enter this branch and fail, never restore YES.
    return isinstance(value, dict) and 'conditionalExecution' in value


def is_quantity_basis(value):
    return isinstance(value, dict) and 'quantityPolicy' in value


def is_plan_policy_basis(value):
    return is_conditional_basis(value) or is_quantity_basis(value)


def _preparation_plan_hash(plan, exact_scope):
    """Preserve the original anchor across separately audited date metadata.

    The plan-date service deliberately does not revise the engineering core.
    Reconstruct only that original date, proving every later native change;
    every other concrete field must still match the original frozen hash.
    Scheduling continues to evaluate the current date and current resources.
    """
    from copy import copy
    from datetime import date
    from . import operation_requirement_service as native
    from . import operation_input_preparation_service as prep
    from .models import OperationInputPreparationDraft
    from planning.services import PLAN_START_DATE_ACTION, PLAN_START_DATE_PERMISSION
    from system.models import OrganizationOperatingAuditRecord
    current = native._proof_record_hash(plan)
    saved = OperationInputPreparationDraft.objects.select_related(
        'creation_write_request__source_identity').filter(
        **{field: exact_scope[key] for key, field in prep.SCOPE_FIELDS.items()}).first()
    if saved is None or not is_plan_policy_basis(saved.business_basis):
        return current
    original = saved.creation_write_request.source_identity.audit_metadata.get('context', {})
    expected = original.get('anchorHashes', {}).get('plan')
    if current == expected:
        return current
    changes = list(OrganizationOperatingAuditRecord.objects.select_related('actor').filter(
        organization_id=saved.company_id, target_type='ProductionPlan', target_id=plan.pk,
        action_code=PLAN_START_DATE_ACTION, created_at__gt=saved.created_at).order_by('-pk'))
    if not changes:
        return current  # The ordinary complete-context verifier will reject it.
    frozen = copy(plan)
    core = {'requiredDate': plan.required_date.isoformat(), 'status': plan.status,
        'updatedAt': plan.updated_at.isoformat()}
    for audit in changes:
        before, after = audit.before_snapshot.get('state', {}), audit.after_snapshot.get('state', {})
        authorization = audit.after_snapshot.get('authorization', {})
        actual = frozen.planned_start_date.isoformat() if frozen.planned_start_date else None
        if (audit.actor.company_id != saved.company_id or not authorization.get('allowed')
                or PLAN_START_DATE_PERMISSION not in authorization.get('permissionCodes', [])
                or any(before.get(k) != v or after.get(k) != v for k, v in core.items())
                or after.get('savedStartDate') != actual
                or after.get('writeIntent') != 'business_progress_write'
                or after.get('productionScheduleCreatedCount') != 0
                or after.get('resourceOccupancyCreatedCount') != 0):
            prep._fail('CONTEXT_DRIFT', '改期缺少连续原生审计或改变了准备记录的核心来源')
        try:
            value = before['savedStartDate']
            frozen.planned_start_date = date.fromisoformat(value) if value is not None else None
        except (KeyError, TypeError, ValueError):
            prep._fail('CONTEXT_DRIFT', '原生改期审计缺少有效原日期')
    return native._proof_record_hash(frozen)


@transaction.atomic
def build_conditional_context(*, user, exact_scope, lock=False, mode=None,
        statistical_routing_step_id=None, standard_capacity_id=None, read_cache=None):
    from planning.models import ProductionPlan
    from . import operation_input_preparation_service as prep
    from . import operation_requirement_service as native
    from .daily_capacity_service import _plan_capacity_context
    from .manufacturing_output_generation_service import validate_selected_output
    from .manufacturing_structure_service import ManufacturingStructureService
    from .models import CapacityProductType, RoutingStep
    from .plan_step_context_service import effective_calculation, effective_baseline, source_selection
    from .routing_step_applicability_service import RoutingStepApplicabilityResolver

    if mode not in (None, QUANTITY_MODE):
        prep._fail('QUANTITY_POLICY_INVALID', '计划步骤准备政策类型无效')
    if (not isinstance(exact_scope, dict) or set(exact_scope) != prep.SCOPE_KEYS
            or any(not prep._positive(exact_scope.get(key)) for key in prep.SCOPE_KEYS)
            or user is not None and user.company_id != exact_scope['companyId']):
        prep._fail('SCOPE_INVALID', '条件准备必须绑定当前公司完整计划及步骤身份')
    if user is not None:
        prep._authorize(user, prep.VIEW)
    company_id = exact_scope['companyId']
    cache = (native._requirement_read_cache(read_cache, company_id)
        if user is not None and not lock else None)
    if cache is not None and cache.user_id != user.pk:
        cache = None
    plans = ProductionPlan.objects.filter(pk=exact_scope['productionPlanId'],
        planning_requirement__demand__sales_order_item__sales_order__company_id=company_id)
    if lock:
        plans = plans.select_for_update()
    plan = plans.first()
    if plan is None:
        prep._fail('SCOPE_INVALID', '生产计划不属于当前公司')
    plan, output, item, _ = _plan_capacity_context(plan, company_id,
        routing_step_id=exact_scope['routingStepId'],
        **({'read_cache': cache} if cache is not None else {}))
    base, baseline = effective_calculation(plan), effective_baseline(plan)
    step = RoutingStep.objects.select_related('operation', 'routing_version__routing').filter(
        pk=exact_scope['routingStepId'], routing_version_id=output.routing_version_id,
        operation__company_id=company_id, is_active=True).first()
    if (plan.status != 'confirmed' or plan.planned_qty != plan.planning_requirement.net_required_qty
            or len({plan.material_id, plan.planning_requirement.material_id,
                    plan.planning_requirement.demand.material_id, item.material_id}) != 1
            or any(row.company_id != company_id for row in (plan.material,
                plan.planning_requirement.material, plan.planning_requirement.demand.material, item.material))
            or plan.planning_requirement.demand.department.company_id != company_id
            or not step or not native._active(step.operation)
            or not base or base.scope != 'order_engineering' or base.status != 'completed'
            or base.company_id != company_id or base.sales_order_item_id != item.pk
            or base.engineering_instance_id != output.order_engineering_instance_id
            or not baseline or baseline.company_id != company_id or production_status(baseline) != 'confirmed'
            or baseline.sales_order_id != item.sales_order_id
            or output.release_status != 'released_to_manufacturing'
            or output.routing_version.status != 'released'):
        prep._fail('CONTEXT_DRIFT', '条件准备的计划、固定输出、来源、基线或步骤资格不一致')
    if lock:
        for row in (output, base, baseline, step, step.operation, output.routing_version,
                    output.routing_version.routing, base.engineering_instance, base.source_record):
            list(type(row).objects.select_for_update().filter(pk=row.pk))
    # This proves the saved output and its frozen inputs. No current design
    # item is asserted to be an affected object of a future quality exception.
    selected = validate_selected_output(output, user=user,
        **({'read_cache': cache, '_content_plan_id': plan.pk} if cache is not None else {}))
    route_base, route = output.engineering_calculation, output.routing_version.routing
    resolved = ManufacturingStructureService.resolve_effective_routing(route_base.engineering_instance,
        on_date=native._today(), exact_version_context={'organizationId': company_id,
            'salesOrderItemId': item.pk, 'orderEngineeringInstanceId': route_base.engineering_instance_id,
            'orderEngineeringBaselineId': output.order_engineering_baseline_id,
            'engineeringCalculationId': route_base.pk, 'bomVersionId': output.bom_version_id})
    instance = base.engineering_instance
    category_id = instance.product_category_id or (instance.product.category_id if instance.product_id else None)
    process_id = instance.selected_process_type_id
    kinds = [row for row in CapacityProductType.objects.filter(company_id=company_id,
        product_category_id=category_id, manufacturing_process_type_id=process_id,
        is_active=True) if native._active(row)]
    if (resolved['routing_version'].pk != output.routing_version_id or not category_id or not process_id
            or route.product_category_id and route.product_category_id != category_id
            or route.manufacturing_process_type_id and route.manufacturing_process_type_id != process_id
            or route.product_id and route.product_id != instance.product_id
            or route.order_engineering_instance_id and route.order_engineering_instance_id != instance.pk
            or len(kinds) != 1):
        prep._fail('CONTEXT_DRIFT', '条件准备的正式路线与唯一产品类型不一致')
    kind = kinds[0]
    actual = {'companyId': company_id, 'productionPlanId': plan.pk, 'manufacturingOutputId': output.pk,
        'mainCalculationId': base.pk, 'salesOrderItemId': item.pk, 'baselineId': baseline.pk,
        'routingVersionId': output.routing_version_id, 'routingStepId': step.pk,
        'operationId': step.operation_id, 'productTypeId': kind.pk}
    if actual != exact_scope:
        prep._fail('CONTEXT_DRIFT', '条件准备的完整计划步骤锚点已变化')
    if lock:
        from .models import OperationInputPreparationDraft
        existing = list(OperationInputPreparationDraft.objects.select_for_update().filter(
            production_plan_id=plan.pk, routing_step_id=step.pk))
        marker = is_quantity_basis if mode == QUANTITY_MODE else is_conditional_basis
        if any(not marker(row.business_basis) for row in existing):
            prep._fail('CONDITIONAL_CONFLICT', '既有普通投入准备不可转换或覆盖为待触发政策')
        persisted = persistence({'scope': actual, 'native': {'base': base, 'item': item, 'step': step}})
        if persisted['formalRequirementCount'] or persisted['allocationCount']:
            prep._fail('CONDITIONAL_PERSISTENCE_CONFLICT', '已有正式需求或计划分配，禁止用待触发政策隐藏已保存量')
    # No production_plan is supplied: read the original immutable route's
    # decision, rather than recursively consuming this new plan policy.
    original = RoutingStepApplicabilityResolver.resolve(step, engineering_calculation=base,
        engineering_document_version=output.engineering_document_version,
        order_engineering_instance=instance, order_engineering_baseline=baseline,
        bom_version=output.bom_version)
    if original.get('pendingCode', '').startswith(('MANUAL_DECISION_', 'FORMAL_CONDITION_')):
        prep._fail('HISTORY_INVALID', '原适用性确认的原生证明失效，不得以条件准备掩盖')
    prior_audit_id = original.get('manualDecisionAuditId')
    prior_audit = None
    if prior_audit_id is not None:
        from system.models import OrganizationOperatingAuditRecord
        prior_audit = OrganizationOperatingAuditRecord.objects.filter(pk=prior_audit_id,
            organization_id=company_id, target_id=step.routing_version_id).first()
        if prior_audit is None:
            prep._fail('HISTORY_INVALID', '原人工确认审计缺失')
    context = {'contractVersion': CONTRACT, 'exactScope': actual,
        'scopeType': COVERAGE['scopeType'], 'objectCoverage': deepcopy(COVERAGE),
        'anchorHashes': {name: (_preparation_plan_hash(row, actual) if name == 'plan'
            else native._proof_record_hash(row)) for name, row in
            (('plan', plan), ('output', output), ('base', base), ('baseline', baseline),
             ('step', step), ('operation', step.operation), ('productType', kind))},
        'savedOutputFingerprint': selected['sourceFingerprint'],
        'sourceSelection': source_selection(plan), 'originalApplicability': original,
        'originalDecisionAuditHash': native._proof_record_hash(prior_audit)}
    if mode == QUANTITY_MODE:
        references = quantity_references(scope=actual, native={'plan': plan, 'output': output,
            'base': base, 'baseline': baseline, 'item': item, 'step': step}, kind=kind,
            original=original, statistical_routing_step_id=statistical_routing_step_id,
            standard_capacity_id=standard_capacity_id, lock=lock)
        context.update(contractVersion=QUANTITY_CONTRACT, scopeType=QUANTITY_COVERAGE['scopeType'],
            objectCoverage=deepcopy(QUANTITY_COVERAGE), quantityPolicyReferences={
                'statisticalUomReference': {'referenceType': 'ROUTE_STEP_SOURCE_CONFIGURATION',
                    'routingStepId': statistical_routing_step_id},
                'capacityReference': {'standardCapacityId': standard_capacity_id}},
            quantityPolicyReferenceProofs=deepcopy(references['proofs']))
        return {'scope': actual, 'native': {'plan': plan, 'output': output, 'item': item,
            'base': base, 'baseline': baseline, 'step': step}, 'kind': kind,
            'quantity_policy': True, 'quantity_references': references,
            'context': context, 'context_hash': prep._hash(context),
            'coverage': deepcopy(QUANTITY_COVERAGE), 'objects_hash': prep._hash(QUANTITY_COVERAGE),
            'applicability': original}
    return {'scope': actual, 'native': {'plan': plan, 'output': output, 'item': item,
        'base': base, 'baseline': baseline, 'step': step}, 'kind': kind,
        'conditional': True, 'context': context, 'context_hash': prep._hash(context),
        'coverage': deepcopy(COVERAGE), 'objects_hash': prep._hash(COVERAGE),
        'applicability': {'result': 'PENDING'}}


def build_quantity_policy_context(*, user, exact_scope, statistical_routing_step_id,
        standard_capacity_id, lock=False, read_cache=None):
    return build_conditional_context(user=user, exact_scope=exact_scope, lock=lock, mode=QUANTITY_MODE,
        statistical_routing_step_id=statistical_routing_step_id, standard_capacity_id=standard_capacity_id,
        read_cache=read_cache)


def quantity_references(*, scope, native, kind, original, statistical_routing_step_id,
        standard_capacity_id, lock=False):
    from decimal import Decimal
    from masterdata.models import UnitOfMeasure
    from . import operation_input_preparation_service as prep
    from . import operation_requirement_service as operation
    from .models import RoutingStep, StandardCapacity, EngineeringRuleDefinition
    from .operation_workload_source_service import operation_source_configuration
    from .daily_capacity_service import capacity_source_rules, capacity_fact
    from .manufacturing_rule_configuration import publication_config_validation
    if (not prep._positive(statistical_routing_step_id) or not prep._positive(standard_capacity_id)
            or statistical_routing_step_id == scope['routingStepId']
            or original.get('mode') != 'MANDATORY' or original.get('result') != 'REQUIRED'):
        prep._fail('QUANTITY_POLICY_INVALID', '不单独计量仅适用于已证明的常规必经步骤及明确同路线单位引用')
    steps = RoutingStep.objects.select_related('operation', 'routing_version').filter(
        pk=statistical_routing_step_id, routing_version_id=scope['routingVersionId'],
        operation__company_id=scope['companyId'], is_active=True)
    if lock:
        steps = steps.select_for_update()
    source_step = steps.first()
    if source_step is None or not operation._active(source_step.operation):
        prep._fail('QUANTITY_POLICY_UNIT_REFERENCE_INVALID', '统计单位必须引用本公司同一正式路线的有效步骤')
    configuration = operation_source_configuration(source_step.operation, kind.pk,
        routing_context={'routingId': native['output'].routing_version.routing_id,
            'routingVersionId': scope['routingVersionId'], 'routingStepId': source_step.pk})
    sources = configuration.get('sources', [])
    unit_ids = {item.get('uomId') for item in sources}
    if (not configuration.get('hasValidSourceConfiguration') or configuration.get('blockers')
            or not sources or len(unit_ids) != 1 or any(not prep._positive(pk) for pk in unit_ids)):
        prep._fail('QUANTITY_POLICY_UNIT_REFERENCE_INVALID', '被引用步骤的正式来源配置无效或无法唯一证明统计单位')
    unit = UnitOfMeasure.objects.filter(pk=next(iter(unit_ids)), company_id=scope['companyId'], is_active=True).first()
    if unit is None or not operation._active(unit):
        prep._fail('QUANTITY_POLICY_UNIT_REFERENCE_INVALID', '被引用统计单位已失效或不属于本公司')
    rules = EngineeringRuleDefinition.objects.filter(pk__in=[row['ruleId'] for row in sources],
        company_id=scope['companyId'], status='released').order_by('pk')
    if lock:
        rules = rules.select_for_update()
    rules = list(rules)
    if len(rules) != len(sources) or any(not operation._active(row) for row in rules):
        prep._fail('QUANTITY_POLICY_UNIT_REFERENCE_INVALID', '被引用正式来源规则版本已失效或不完整')
    proof = {'companyId': scope['companyId'], 'productionPlanId': scope['productionPlanId'],
        'routingVersionId': scope['routingVersionId'], 'routingStepId': source_step.pk,
        'operationId': source_step.operation_id, 'uomId': unit.pk,
        'stepHash': operation._proof_record_hash(source_step), 'unitHash': operation._proof_record_hash(unit),
        'rules': [{'ruleId': row.pk, 'ruleHash': operation._proof_record_hash(row),
            'publicationProof': publication_config_validation(row, require_released=True)} for row in rules]}
    capacities = StandardCapacity.objects.select_related('work_center__workshop', 'uom').filter(
        pk=standard_capacity_id, company_id=scope['companyId'])
    if lock:
        capacities = capacities.select_for_update()
    capacity = capacities.first()
    source_rules = capacity_source_rules(kind, company_id=scope['companyId'], on_date=operation._today())
    target = native['step']
    if (capacity is None or not operation._active(capacity)
            or capacity.operation_id != target.operation_id or capacity.product_type_id != kind.pk
            or capacity.uom_id != target.operation.calculation_uom_id
            or capacity.measurement_status != 'zero_capacity' or capacity.quantity != Decimal(0)
            or capacity.time_basis != 'day' or capacity.time_basis_quantity != Decimal(1) or capacity.time_unit != 'DAY'
            or not capacity.work_center_id or not operation._active(capacity.work_center)
            or capacity.work_center.company_id != scope['companyId']
            or not capacity.work_center.workshop_id or not operation._active(capacity.work_center.workshop)
            or capacity.work_center.workshop.company_id != scope['companyId']
            or target.work_center_id and target.work_center_id != capacity.work_center_id
            or target.operation.work_center_id and target.operation.work_center_id != capacity.work_center_id
            or source_rules.get('status') != 'VALID'
            or target.operation_id not in source_rules.get('manifest', {}).get('auxiliaryOperationIds', [])
            or capacity.pk not in {row.pk for row in source_rules.get('capacityRows', [])}):
        prep._fail('QUANTITY_POLICY_CAPACITY_INVALID', '不单独计量必须引用本工序同公司正式配套0产能，不得改写其原单位')
    capacity_read = capacity_fact(capacity, operation._today(), source_rules=source_rules)
    if (not capacity_read['capacitySemantics'].get('valid')
            or capacity_read['capacitySemantics'].get('meaningCode') != 'NON_QUANTIFIED'):
        prep._fail('QUANTITY_POLICY_CAPACITY_INVALID', '正式配套0产能的独立来源证明无效')
    proof_hash = prep._hash(proof)
    return {'statisticalUomReference': {'uomId': unit.pk, 'uomCode': unit.code, 'uomLabel': unit.name,
        'sourceCompanyId': scope['companyId'], 'sourceProductionPlanId': scope['productionPlanId'],
        'sourceRoutingVersionId': scope['routingVersionId'], 'sourceRoutingStepId': source_step.pk,
        'sourceOperationId': source_step.operation_id, 'statusLabel': '统计单位引用同路线有效正式来源配置',
        'proofHash': proof_hash}, 'capacity': capacity_read,
        'proofs': {'statisticalUomProofHash': proof_hash,
            'capacityRecordHash': operation._proof_record_hash(capacity),
            'capacitySourceRulesHash': prep._hash(source_rules['manifest'])}}


def build_quantity_policy_basis(*, context, reference, reference_sha256, exact_statement):
    from . import operation_input_preparation_service as prep
    return {'contractVersion': prep.BASIS_CONTRACT, 'quantityPolicy': {
        'contractVersion': QUANTITY_CONTRACT, 'measurementMode': QUANTITY_MODE,
        'plannedQuantity': None, 'actualQuantity': None, 'nullReason': QUANTITY_MODE,
        'scopeDetermination': 'DRAWING_AND_SITE', 'objectCoverageClaimed': False,
        **deepcopy(context['context']['quantityPolicyReferences'])},
        'entries': [{'reference': reference, 'referenceSha256': reference_sha256,
            'exactStatement': exact_statement, 'scope': deepcopy(context['scope']),
            'objectCoverage': deepcopy(QUANTITY_COVERAGE)}]}


def validate_quantity_basis(value, scope):
    from . import operation_input_preparation_service as prep
    expected = build_quantity_policy_basis(context=scope, reference='', reference_sha256='', exact_statement='')
    if (not scope.get('quantity_policy') or set(value) != set(expected)
            or prep._hash(value.get('quantityPolicy')) != prep._hash(expected['quantityPolicy'])
            or value.get('contractVersion') != prep.BASIS_CONTRACT
            or not isinstance(value.get('entries'), list) or not value['entries']):
        prep._fail('QUANTITY_POLICY_INVALID', '数量政策必须明确不单独计量、空值原因及服务端单位/产能引用，不接受客户端数量或单位')
    seen = set()
    for entry in value['entries']:
        if (not isinstance(entry, dict) or set(entry) != set(expected['entries'][0])
                or any(not isinstance(entry.get(key), str) or not entry[key].strip()
                    for key in ('reference', 'exactStatement'))
                or not prep._token(entry.get('referenceSha256')) or entry['scope'] != scope['scope']
                or entry['objectCoverage'] != QUANTITY_COVERAGE):
            prep._fail('BASIS_INVALID', '数量政策必须保留精确计划步骤、图纸现场范围及原答复出处')
        key = (entry['reference'], entry['referenceSha256'], entry['exactStatement'])
        if key in seen:
            prep._fail('BASIS_INVALID', '数量政策原答复不得重复')
        seen.add(key)
    return deepcopy(value)
def build_conditional_basis(*, context, reference, reference_sha256, exact_statement, execution_statement):
    from . import operation_input_preparation_service as prep
    return {'contractVersion': prep.BASIS_CONTRACT, 'conditionalExecution': {
        'contractVersion': CONTRACT, 'conditionCode': CONDITION, 'triggerStatus': 'WAITING_TRIGGER',
        'affectedObjects': None, 'affectedParts': None, 'quantity': None, 'uomId': None,
        'capacityPolicy': deepcopy(CAPACITY_POLICY),
        'executionFact': {'mode': 'SIMULATED', 'allMaterialUnissued': True,
            'allWorkUnstarted': True, 'statement': execution_statement},
        'originalApplicabilityHash': prep._hash(context['context']['originalApplicability'])},
        'entries': [{'reference': reference, 'referenceSha256': reference_sha256,
            'exactStatement': exact_statement, 'scope': deepcopy(context['scope']),
            'objectCoverage': deepcopy(COVERAGE)}]}


def validate_basis(value, scope):
    from . import operation_input_preparation_service as prep
    policy = value.get('conditionalExecution')
    expected = build_conditional_basis(context=scope, reference='', reference_sha256='',
        exact_statement='', execution_statement='')['conditionalExecution']
    execution = policy.get('executionFact') if isinstance(policy, dict) else None
    if (not isinstance(policy, dict) or set(policy) != set(expected)
            or not isinstance(execution, dict) or set(execution) != set(expected['executionFact'])
            or not isinstance(execution.get('statement'), str) or not execution['statement'].strip()):
        prep._fail('CONDITIONAL_INVALID', '条件准备必须声明尚未触发、未知范围及明确模拟执行事实')
    expected['executionFact']['statement'] = execution['statement']
    if prep._hash(policy) != prep._hash(expected) or not scope.get('conditional'):
        prep._fail('CONDITIONAL_INVALID', '条件准备不得伪造触发、对象、数量、单位或实际执行资格')
    if (set(value) != {'contractVersion', 'entries', 'conditionalExecution'}
            or value.get('contractVersion') != prep.BASIS_CONTRACT
            or not isinstance(value.get('entries'), list) or not value['entries']):
        prep._fail('BASIS_INVALID', '条件准备必须保存版本化原答复及出处Hash')
    seen = set()
    for entry in value['entries']:
        if (not isinstance(entry, dict) or set(entry) != {'reference', 'referenceSha256',
                'exactStatement', 'scope', 'objectCoverage'}
                or any(not isinstance(entry.get(key), str) or not entry[key].strip()
                    for key in ('reference', 'exactStatement'))
                or not prep._token(entry.get('referenceSha256'))
                or entry['scope'] != scope['scope'] or entry['objectCoverage'] != COVERAGE):
            prep._fail('BASIS_INVALID', '条件准备原文必须绑定完整计划步骤及未知对象范围')
        identity = (entry['reference'], entry['referenceSha256'], entry['exactStatement'])
        if identity in seen:
            prep._fail('BASIS_INVALID', '条件准备原答复不得重复')
        seen.add(identity)
    prep._hash(value)
    return deepcopy(value)


def capacity_readback(scope, row):
    return {'capacityMeasurementStatus': None, 'capacityBusinessValue': None,
        'capacityMeasurementStatusLabel': '触发后经过但无法准确核算，不计定量产能占用',
        'conditionalCapacityPolicy': deepcopy(CAPACITY_POLICY),
        'capacityResolution': {'valid': False, 'code': 'WAITING_TRIGGER', 'statusLabel': LABEL},
        'capacitySemantics': {'valid': False, 'meaningCode': None, 'sourceValue': None,
            'statusLabel': LABEL, 'quantitativeOccupancyAllowed': False,
            'grantsRulePublication': False, 'grantsRequirementGeneration': False,
            'grantsAllocation': False, 'grantsScheduling': False}}


def persistence(scope):
    from .operation_workload_source_service import _workload_requirement_rows
    from .models import ProductionPlanOperationRequirementAllocation
    ids, native = scope['scope'], scope['native']
    return {'formalRequirementCount': _workload_requirement_rows(company_id=ids['companyId'],
            base=native['base'], item=native['item'], step=native['step']).count(),
        'allocationCount': ProductionPlanOperationRequirementAllocation.objects.filter(
            company_id=ids['companyId'], production_plan_id=ids['productionPlanId'],
            routing_step_id=ids['routingStepId']).count()}


def present(scope, row, proof):
    from . import operation_input_preparation_service as prep
    audits, transitions = proof
    policy = deepcopy(row.business_basis['conditionalExecution'])
    policy.update(triggerPolicyLabel=LABEL,
        pendingScopeLabel='异常触发后确定实际处理对象、数量及单位，以及具体处理部位',
        executionFactLabel='模拟状态：未领料、未开工',
        capacityIndependenceLabel='产能0仅表示触发后不可定量，不表示投产量为0，也不授予执行或排程资格')
    result = {'contractVersion': prep.CONTRACT, 'factSource': 'server', 'currentStateSource': 'server',
        'exactScope': deepcopy(scope['scope']), 'context': deepcopy(scope['context']),
        'contextHash': scope['context_hash'], 'objectsHash': scope['objects_hash'],
        'objectCoverage': deepcopy(COVERAGE), 'recordStatus': 'RECORDED', 'statusCode': 'WAITING_TRIGGER',
        'statusLabel': LABEL, 'result': 'PENDING', 'resultLabel': LABEL,
        'conditionCode': CONDITION, 'triggerStatus': 'WAITING_TRIGGER', 'isPersisted': True,
        'recordId': row.pk, 'revision': row.revision, 'contentHash': row.content_hash,
        'businessBasis': deepcopy(row.business_basis), 'draftSelection': None,
        'conditionalExecution': policy, 'originalApplicability': deepcopy(scope['context']['originalApplicability']),
        'formalPolicyValidated': True, 'formalApplicabilityValidated': False,
        'sourceQuantity': None, 'inputQuantity': None, 'capacityQuantity': None, 'quantity': None, 'uomId': None,
        'inputStandardStatus': 'PENDING_CONFIRMATION', 'inputStandardStatusLabel': '触发后据实确认',
        'formalRuleStatusLabel': '条件准备不代表正式规则已发布或执行授权',
        'remainingItems': [{'code': 'TRIGGER_SCOPE_NOT_YET_DETERMINED',
            'statusLabel': policy['pendingScopeLabel']}],
        'businessBasisPresentation': [{'entryIndex': index, 'statusLabel': '已确认的条件准备依据',
            'exactStatement': entry['exactStatement'], 'reference': entry['reference'],
            'referenceSha256': entry['referenceSha256']}
            for index, entry in enumerate(row.business_basis['entries'])],
        'scopeLabel': f"生产计划{scope['native']['plan'].plan_no} / 路线第{scope['native']['step'].sequence}步条件准备；不声明对象覆盖",
        'auditIds': [audit.pk for audit in audits], 'writeRequestId': row.creation_write_request_id,
        'sourceIdentityId': row.creation_write_request.source_identity_id,
        'statusTransitionHistory': [{'id': item.pk, 'sourceState': item.source_state,
            'targetState': item.target_state, 'version': item.version, 'operatorId': item.operator_id,
            'auditReference': item.audit_reference, 'timestamp': item.timestamp.isoformat()}
            for item in transitions],
        'statusTransitionCount': len(transitions), 'stateMachineConsistent': True,
        'formalRulePublished': False, 'readyForGeneration': False, 'readyForAllocation': False,
        'readyForScheduling': False, 'businessWriteCount': 0, 'auditWriteCount': 0,
        'stateTransitionWriteCount': 0, 'supportWriteCount': 0}
    result.update({key: policy[key] for key in ('triggerPolicyLabel', 'pendingScopeLabel',
        'executionFactLabel', 'capacityIndependenceLabel')})
    result['persistence'] = persistence(scope)
    result['blockers'] = ([{'code': 'CONDITIONAL_PERSISTENCE_CONFLICT',
        'statusLabel': '待触发步骤已有正式需求或分配，须独立核对，禁止隐藏已保存量'}]
        if any(result['persistence'].values()) else [])
    result.update(capacity_readback(scope, row))
    return result


def quantity_capacity_readback(scope):
    capacity = scope['quantity_references']['capacity']
    return {'capacityMeasurementStatus': 'zero_capacity', 'capacityBusinessValue': 0,
        'capacityMeasurementStatusLabel': '经过但无法准确核算，不计定量产能占用',
        'capacitySemantics': deepcopy(capacity['capacitySemantics']),
        'capacityResolution': {'valid': True, 'code': 'FORMAL_AUXILIARY_ZERO_REFERENCE',
            'formalStandardCapacityPresent': True, 'originalConclusionRevoked': False,
            'statusLabel': '引用本工序有效正式配套0产能，原产能记录及单位保持'},
        'standardCapacityReference': deepcopy(capacity)}


def quantity_policy_readback(scope, row):
    policy = deepcopy(row.business_basis['quantityPolicy'])
    policy.update(exactScope=deepcopy(scope['scope']), formalPolicyValidated=True,
        statusLabel=QUANTITY_LABEL,
        plannedQuantityReasonLabel='本工序不单独统计计划投产量，空值原因是不单独计量',
        actualQuantityReasonLabel='本工序不单独统计实际产量，空值原因是不单独计量',
        scopeDeterminationLabel='实际处理范围按图纸及现场工艺确定，不预先枚举逐门逐边数量',
        statisticalUomReference=deepcopy(scope['quantity_references']['statisticalUomReference']),
        capacityIndependenceLabel='统计单位与正式产能原单位分别保留；0产能不等于投产量或产量为0，不计定量产能占用',
        grantsRulePublication=False, grantsRequirementGeneration=False, grantsAllocation=False, grantsScheduling=False)
    return policy


def present_quantity_policy(scope, row, proof):
    from . import operation_input_preparation_service as prep
    audits, transitions = proof
    policy = quantity_policy_readback(scope, row)
    result = {'contractVersion': prep.CONTRACT, 'factSource': 'server', 'currentStateSource': 'server',
        'exactScope': deepcopy(scope['scope']), 'context': deepcopy(scope['context']),
        'contextHash': scope['context_hash'], 'objectsHash': scope['objects_hash'],
        'objectCoverage': deepcopy(QUANTITY_COVERAGE), 'recordStatus': 'RECORDED', 'statusCode': QUANTITY_MODE,
        'statusLabel': QUANTITY_LABEL, 'isPersisted': True, 'recordId': row.pk,
        'revision': row.revision, 'contentHash': row.content_hash,
        'businessBasis': deepcopy(row.business_basis), 'draftSelection': None,
        'quantityPolicy': policy, 'originalApplicability': deepcopy(scope['context']['originalApplicability']),
        'formalPolicyValidated': True, 'formalApplicabilityValidated': True,
        'sourceQuantity': None, 'inputQuantity': None, 'capacityQuantity': None,
        'plannedQuantity': None, 'actualQuantity': None, 'nullReason': QUANTITY_MODE,
        'inputStandardStatus': 'PENDING_CONFIRMATION', 'inputStandardStatusLabel': QUANTITY_LABEL,
        'formalRuleStatusLabel': '正式数量政策不生成独立作业量规则、需求或分配',
        'remainingItems': [],
        'businessBasisPresentation': [{'entryIndex': index, 'statusLabel': '已确认的正式数量政策依据',
            'exactStatement': entry['exactStatement'], 'reference': entry['reference'],
            'referenceSha256': entry['referenceSha256']}
            for index, entry in enumerate(row.business_basis['entries'])],
        'scopeLabel': f"生产计划{scope['native']['plan'].plan_no} / 路线第{scope['native']['step'].sequence}步常规必经配套",
        'auditIds': [audit.pk for audit in audits], 'writeRequestId': row.creation_write_request_id,
        'sourceIdentityId': row.creation_write_request.source_identity_id,
        'statusTransitionHistory': [{'id': item.pk, 'sourceState': item.source_state,
            'targetState': item.target_state, 'version': item.version, 'operatorId': item.operator_id,
            'auditReference': item.audit_reference, 'timestamp': item.timestamp.isoformat()}
            for item in transitions], 'statusTransitionCount': len(transitions), 'stateMachineConsistent': True,
        'formalRulePublished': False, 'readyForGeneration': False, 'readyForAllocation': False,
        'readyForScheduling': False, 'businessWriteCount': 0, 'auditWriteCount': 0,
        'stateTransitionWriteCount': 0, 'supportWriteCount': 0,
        'persistence': persistence(scope)}
    result['blockers'] = ([{'code': 'QUANTITY_POLICY_PERSISTENCE_CONFLICT',
        'statusLabel': '不单独计量步骤已有正式需求或分配，须核对实际持久化事实，禁止隐藏数量'}]
        if any(result['persistence'].values()) else [])
    result.update(quantity_capacity_readback(scope))
    return result


def _preparation_plan_owned_by_company(company_id, plan_id):
    from planning.models import ProductionPlan
    from .capacity_evidence_read_scope import evidence_cache
    from .operation_requirement_service import _read_once

    return _read_once(evidence_cache(company_id), ('preparation_plan_company_row', company_id, plan_id),
        lambda: ProductionPlan.objects.filter(pk=plan_id,
            planning_requirement__demand__sales_order_item__sales_order__company_id=company_id).exists())


def saved_for_scope(exact_scope):
    """Locate first, then verify; a moved/deleted conditional row fails closed."""
    from .capacity_evidence_read_scope import evidence_cache
    from .operation_requirement_service import _read_once
    from django.db.models import Q
    from masterdata.models import MasterDataWriteRequest
    from . import operation_input_preparation_service as prep
    from .models import OperationInputPreparationDraft
    if (not isinstance(exact_scope, dict) or not prep._positive(exact_scope.get('companyId'))
            or not prep._positive(exact_scope.get('productionPlanId'))
            or not prep._positive(exact_scope.get('routingStepId'))
            or not _preparation_plan_owned_by_company(exact_scope['companyId'], exact_scope['productionPlanId'])):
        prep._fail('SCOPE_INVALID', '条件准备计划范围无效')
    company_id, plan_id, step_id = (exact_scope[key] for key in ('companyId', 'productionPlanId', 'routingStepId'))
    evidence = evidence_cache(company_id)
    rows = _read_once(evidence, ('conditional_preparation_rows', company_id, plan_id, step_id),
        lambda: list(OperationInputPreparationDraft.objects.select_related('creation_write_request__source_identity').filter(
            production_plan_id=plan_id, routing_step_id=step_id)[:2]))
    if len(rows) > 1:
        prep._fail('SCOPE_CONFLICT', '同一计划步骤不能有多个准备上下文')
    ledgers = MasterDataWriteRequest.objects.filter(organization_id=exact_scope['companyId'],
        action_code=prep.ACTION, entity_type=prep.ENTITY,
        audit_metadata__payload__exactScope__productionPlanId=exact_scope['productionPlanId'],
        audit_metadata__payload__exactScope__routingStepId=exact_scope['routingStepId']).filter(
            Q(audit_metadata__payload__businessBasis__conditionalExecution__contractVersion=CONTRACT)
            | Q(audit_metadata__payload__businessBasis__quantityPolicy__contractVersion=QUANTITY_CONTRACT))
    ledger_exists = _read_once(evidence, ('conditional_preparation_original_ledger', company_id, plan_id, step_id),
        ledgers.exists)
    if ledger_exists and (not rows or not is_plan_policy_basis(rows[0].business_basis)
            or rows[0].company_id != company_id):
        prep._fail('HISTORY_INVALID', '已提交条件准备记录缺失、迁移或协议被改写')
    return rows[0] if rows else None


@transaction.atomic
def resolve_conditional_execution(step, production_plan, *, manufacturing_output=None,
        engineering_calculation=None, order_engineering_instance=None,
        order_engineering_baseline=None, bom_version=None, read_cache=None):
    from planning.models import ProductionPlan
    from . import operation_input_preparation_service as prep
    from .capacity_evidence_read_scope import evidence_cache
    from .operation_requirement_service import _read_once

    plan_id = getattr(production_plan, 'pk', production_plan)
    evidence = evidence_cache(getattr(engineering_calculation, 'company_id', None))
    company_id = _read_once(evidence, ('conditional_preparation_plan_owner', plan_id),
        lambda: ProductionPlan.objects.filter(pk=plan_id).values_list(
            'planning_requirement__demand__sales_order_item__sales_order__company_id', flat=True).first())
    row = saved_for_scope({'companyId': company_id, 'productionPlanId': plan_id, 'routingStepId': step.pk})
    if row is None or not is_conditional_basis(row.business_basis):
        return None
    exact = {key: getattr(row, field) for key, field in prep.SCOPE_FIELDS.items()}
    exact['salesOrderItemId'] = row.production_plan.planning_requirement.demand.sales_order_item_id
    from . import operation_requirement_service as native
    cache = native._requirement_read_cache(read_cache, company_id)
    # A public typed read retains its actual actor and fresh preparation
    # permission check; legacy/no-cache internal callers keep their path.
    scope = build_conditional_context(user=cache.user if cache is not None else None,
        exact_scope=exact, read_cache=cache)
    expected = ((manufacturing_output, scope['native']['output']),
        (engineering_calculation, scope['native']['base']), (order_engineering_baseline, scope['native']['baseline']),
        (order_engineering_instance, scope['native']['base'].engineering_instance),
        (bom_version, scope['native']['output'].bom_version))
    if (scope['native']['step'].pk != step.pk or any(value is not None
            and getattr(value, 'pk', value) != actual.pk for value, actual in expected)):
        prep._fail('CONTEXT_DRIFT', '消费者提供的条件准备上下文不一致')
    return present(scope, row, prep._verify(row, scope))


@transaction.atomic
def resolve_quantity_policy(step, production_plan, *, manufacturing_output=None,
        engineering_calculation=None, order_engineering_instance=None,
        order_engineering_baseline=None, bom_version=None):
    from planning.models import ProductionPlan
    from . import operation_input_preparation_service as prep
    plan_id = getattr(production_plan, 'pk', production_plan)
    company_id = ProductionPlan.objects.filter(pk=plan_id).values_list(
        'planning_requirement__demand__sales_order_item__sales_order__company_id', flat=True).first()
    row = saved_for_scope({'companyId': company_id, 'productionPlanId': plan_id, 'routingStepId': step.pk})
    if row is None or not is_quantity_basis(row.business_basis):
        return None
    exact = {key: getattr(row, field) for key, field in prep.SCOPE_FIELDS.items()}
    exact['salesOrderItemId'] = row.production_plan.planning_requirement.demand.sales_order_item_id
    scope = prep._scope(user=None, exact_scope=exact, policy_basis=row.business_basis)
    expected = ((manufacturing_output, scope['native']['output']),
        (engineering_calculation, scope['native']['base']), (order_engineering_baseline, scope['native']['baseline']),
        (order_engineering_instance, scope['native']['base'].engineering_instance),
        (bom_version, scope['native']['output'].bom_version))
    if (scope['native']['step'].pk != step.pk or any(value is not None
            and getattr(value, 'pk', value) != actual.pk for value, actual in expected)):
        prep._fail('CONTEXT_DRIFT', '消费者提供的正式数量政策上下文不一致')
    prep._verify(row, scope)
    return quantity_policy_readback(scope, row)
