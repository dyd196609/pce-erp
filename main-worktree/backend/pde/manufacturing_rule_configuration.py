"""Validate data-configured manufacturing context for the existing EOR handoff.

This module only reads formal references. It never derives a process from a
field, product name, order identity, or unit conversion, and never changes a
source fact or capacity. Rules without this extension keep their old contract.
"""
from decimal import Decimal, InvalidOperation
import json

from django.utils import timezone

from masterdata.models import UnitOfMeasure
from system.models import Company, Process, Workshop

from .engineering_rule_foundation import (
    EngineeringRuleError, specification_hash, validate_specification,
)
from .models import (
    CapacityProductType, EngineeringRuleDefinition, ManufacturingMode,
    StandardCapacity, WorkCenter, WorkCenterOperationCapability,
)
from .operation_non_quantified_context import (
    REFERENCE_TYPE, STANDARD_CAPACITY, CONTEXT_KEY, source_preparation_context,
)


CONTRACT = "PCE-MANUFACTURING-EOR-RULE-V1"


def _fail(code, message, **details):
    # The existing handoff service imports this extension; import its error
    # only when needed so there is no module-initialization cycle.
    from .operation_requirement_service import OperationRequirementError
    raise OperationRequirementError(code, message, details)


def _today():
    now = timezone.now()
    return timezone.localtime(now).date() if timezone.is_aware(now) else now.date()


def _active(row):
    today = _today()
    return bool(row and getattr(row, "is_active", True)
                and (not getattr(row, "effective_from", None) or row.effective_from <= today)
                and (not getattr(row, "effective_to", None) or row.effective_to >= today))


def _positive_id(value, field):
    if type(value) is not int or value <= 0:
        _fail("MANUFACTURING_CONFIG_INVALID", "制造规则必须明确正式正整数FK", field=field)
    return value


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("MANUFACTURING_CONFIG_INVALID", "制造规则必须声明非空且精确的版本或字段标识", field=field)
    return value


def _json(value, field):
    try:
        # Ensure snapshots can be stored and hashed without non-finite values.
        json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True)
    except (ValueError, TypeError):
        _fail("MANUFACTURING_CONFIG_INVALID", "制造规则选择条件必须为有效JSON数据", field=field)
    return value


def _decimal(value):
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        _fail("MANUFACTURING_CAPACITY_INVALID", "正式日产能数量未维护或无效")
    if not result.is_finite():
        _fail("MANUFACTURING_CAPACITY_INVALID", "正式日产能数量必须是有限数值")
    return result


def _date_text(row, name):
    value = getattr(row, name, None)
    return value.isoformat() if value is not None else None


def _unit_token(uom, token):
    return isinstance(token, str) and bool(token.strip()) and token in {
        value for value in (uom.code, uom.name, uom.symbol)
        if isinstance(value, str) and value.strip()
    }


def _trace_matches(trace, expected):
    # JSON equality preserves boolean/number and nested-value distinctions;
    # Python's equality alone would accept True in place of a configured 1.
    try:
        return all(key in trace and json.dumps(trace[key], allow_nan=False, sort_keys=True)
                   == json.dumps(value, allow_nan=False, sort_keys=True)
                   for key, value in expected.items())
    except (TypeError, ValueError):
        return False


def _configuration(rule, *, require_released):
    raw_spec = rule.specification
    if not isinstance(raw_spec, dict) or "manufacturing" not in raw_spec:
        return None
    config = raw_spec["manufacturing"]
    if not isinstance(config, dict) or config.get("contractVersion") != CONTRACT:
        _fail("MANUFACTURING_CONFIG_INVALID", "制造规则必须声明正式制造模式EOR合同")
    if not _active(rule) or (require_released and rule.status != "released"):
        _fail("MANUFACTURING_RULE_NOT_RELEASED", "生成EOR必须使用当前有效的已发布制造规则版本")
    if not require_released and rule.status not in {"draft", "reviewed", "released"}:
        _fail("MANUFACTURING_RULE_NOT_RELEASED", "制造规则当前状态不允许发布配置校验")
    if config.get("factDisposition") != "GENERATE_EOR":
        _fail("MANUFACTURING_CONFIG_INVALID", "制造工序规则必须明确GENERATE_EOR事实处置")
    if "capacityUsageScope" in config:
        from .manufacturing_capacity_scope import validate_capacity_usage_scope
        validate_capacity_usage_scope(config["capacityUsageScope"])
    if "routingContext" in config:
        from .manufacturing_routing_context import routing_configuration
        routing_configuration(config)
    try:
        spec = validate_specification(raw_spec)
    except EngineeringRuleError as exc:
        _fail(exc.code, exc.message, **exc.details)
    output = spec["outputs"][0]
    if output.get("resultDomain") != "OPERATION_REQUIREMENT" or len(spec["inputs"]) != 1:
        _fail("MANUFACTURING_CONFIG_INVALID", "制造规则必须使用单一工程事实输入并原生输出EOR")
    factory_scope, selector = config.get("factoryScope"), config.get("sourceSelector")
    if not isinstance(factory_scope, dict) or not isinstance(selector, dict):
        _fail("MANUFACTURING_CONFIG_INVALID", "制造规则必须明确工厂范围与来源事实选择器")
    _positive_id(factory_scope.get("companyId"), "factoryScope.companyId")
    _positive_id(factory_scope.get("workshopId"), "factoryScope.workshopId")
    _positive_id(config.get("modeId"), "modeId")
    _text(config.get("modeVersion"), "modeVersion")
    _positive_id(config.get("workCenterId"), "workCenterId")
    capacity_mode = config.get('capacityMode', STANDARD_CAPACITY)
    if capacity_mode not in (STANDARD_CAPACITY, REFERENCE_TYPE):
        _fail('MANUFACTURING_CONFIG_INVALID', '制造规则的产能处理方式未被明确支持')
    if capacity_mode == REFERENCE_TYPE:
        if config.get('standardCapacityId') is not None or 'capacityUsageScope' in config:
            _fail('MANUFACTURING_CONFIG_INVALID', '精确准备裁决路径不得混入标准产能或产能用途域')
    else:
        _positive_id(config.get("standardCapacityId"), "standardCapacityId")
    _text(selector.get("canonicalField"), "sourceSelector.canonicalField")
    _positive_id(selector.get("producerRuleId"), "sourceSelector.producerRuleId")
    _text(selector.get("producerRuleVersion"), "sourceSelector.producerRuleVersion")
    trace_equals = selector.get("traceEquals")
    if not isinstance(trace_equals, dict) or any(
        not isinstance(key, str) or not key.strip() for key in trace_equals
    ):
        _fail("MANUFACTURING_CONFIG_INVALID", "来源选择器必须明确traceEquals数据条件对象")
    _json(trace_equals, "sourceSelector.traceEquals")
    if "candidatePolicy" in selector and selector["candidatePolicy"] != "MATCH_CONFIGURED_TRACE":
        _fail("MANUFACTURING_CONFIG_INVALID", "来源候选策略必须为正式配置追溯条件匹配")
    if "objectTraceKeys" in selector:
        keys = selector["objectTraceKeys"]
        if (not isinstance(keys, list) or not keys
                or any(not isinstance(key, str) or not key.strip() or key != key.strip() for key in keys)
                or len(keys) != len(set(keys))):
            _fail("MANUFACTURING_CONFIG_INVALID", "工程对象追溯必须配置无重复的精确来源trace字段列表")
    input_contract = spec["inputs"][0]
    source_field = input_contract.get("sourceCanonicalField", input_contract["canonicalName"])
    if (input_contract.get("sourceType") != "ENGINEERING_DERIVED"
            or source_field != selector["canonicalField"]):
        _fail("MANUFACTURING_SOURCE_SELECTOR_MISMATCH", "规则输入与来源选择器必须精确声明同一工程事实字段")
    return spec, config, selector


def _formal_references(rule, spec, config, selector, *, read_cache=None):
    company_id, output = rule.company_id, spec["outputs"][0]
    from .operation_requirement_service import _read_once, _requirement_read_cache
    cache = _requirement_read_cache(read_cache, company_id)
    def load(key, loader):
        # Retain the raw row only; all checks, including failed checks, rerun.
        return _read_once(cache, ('manufacturing_raw', company_id, *key), loader)
    factory_scope = config["factoryScope"]
    if factory_scope["companyId"] != company_id or not load(('company',), lambda: Company.objects.filter(
        pk=company_id, is_active=True,
    ).exists()):
        _fail("MANUFACTURING_FACTORY_SCOPE_MISMATCH", "制造规则工厂范围必须属于当前有效公司")
    workshop = load(('workshop', factory_scope['workshopId']), lambda: Workshop.objects.filter(
        pk=factory_scope["workshopId"], company_id=company_id, is_active=True,
    ).first())
    if not workshop:
        _fail("MANUFACTURING_FACTORY_SCOPE_MISMATCH", "制造规则引用的车间缺失、停用或跨公司")
    mode = load(('mode', config['modeId']), lambda: ManufacturingMode.objects.select_related("uom").filter(
        pk=config["modeId"], company_id=company_id,
    ).first())
    if not mode or mode.version != config["modeVersion"] or mode.status != "released" or not _active(mode):
        _fail("MANUFACTURING_MODE_INVALID", "制造模式必须存在且属于精确的当前有效已发布版本")
    operation_id = _positive_id(output.get("operationId"), "outputs.operationId")
    product_type_id = _positive_id(output.get("productTypeId"), "outputs.productTypeId")
    uom_id = _positive_id(output.get("uomId"), "outputs.uomId")
    operation = load(('operation', operation_id), lambda: Process.objects.filter(pk=operation_id, company_id=company_id).first())
    work_center = load(('work_center', config['workCenterId']), lambda: WorkCenter.objects.filter(pk=config["workCenterId"], company_id=company_id).first())
    if not _active(operation) or not _active(work_center):
        _fail("MANUFACTURING_RESOURCE_INVALID", "制造规则工序或工作中心缺失、停用或已失效")
    if work_center.workshop_id != workshop.pk or (
        operation.workshop_id and operation.workshop_id != workshop.pk
    ):
        _fail("MANUFACTURING_FACTORY_SCOPE_MISMATCH", "配置工厂范围与正式工序及工作中心车间不一致")
    capability = None
    if operation.work_center_id and operation.work_center_id != work_center.pk:
        capability = load(('capability', operation.pk, work_center.pk), lambda: WorkCenterOperationCapability.objects.filter(
            operation=operation, work_center=work_center,
        ).first())
        if not _active(capability):
            _fail("MANUFACTURING_RESOURCE_INVALID", "配置工作中心与工序默认资源不同且没有有效正式替代能力")
    product_type = load(('product_type', product_type_id), lambda: CapacityProductType.objects.select_related(
        "product_category", "manufacturing_process_type",
    ).filter(pk=product_type_id, company_id=company_id).first())
    if (not _active(product_type) or not _active(product_type.product_category)
            or not _active(product_type.manufacturing_process_type)
            or product_type.product_category.company_id != company_id
            or product_type.manufacturing_process_type.company_id != company_id):
        _fail("MANUFACTURING_PRODUCT_TYPE_MISMATCH", "制造规则产品类型、产品分类或工艺类型缺失、停用或跨公司")
    uom = load(('uom', uom_id), lambda: UnitOfMeasure.objects.filter(pk=uom_id, company_id=company_id, is_active=True).first())
    if (not uom or operation.calculation_uom_id != uom_id or mode.uom_id != uom_id
            or not _unit_token(uom, output.get("unit"))
            or not _unit_token(uom, spec["inputs"][0].get("unit"))):
        _fail("MANUFACTURING_UOM_MISMATCH", "事实输入、制造模式与工序输出必须使用相同正式单位，禁止推测换算")
    producer = load(('producer', selector['producerRuleId']), lambda: EngineeringRuleDefinition.objects.filter(
        pk=selector["producerRuleId"], company_id=company_id,
    ).first())
    if (not producer or producer.version != selector["producerRuleVersion"]
            or producer.status != "released"):
        _fail("MANUFACTURING_SOURCE_SELECTOR_MISMATCH", "来源选择器必须引用精确的正式已发布生产规则版本")
    producer_spec = producer.specification
    producer_outputs = producer_spec.get("outputs") if isinstance(producer_spec, dict) else None
    if (not isinstance(producer_outputs, list) or len(producer_outputs) != 1
            or not isinstance(producer_outputs[0], dict)
            or producer_outputs[0].get("resultDomain") != "DERIVED_FACT"):
        _fail("MANUFACTURING_SOURCE_SELECTOR_MISMATCH", "来源选择器生产规则必须原生输出DERIVED_FACT")
    if config.get('capacityMode') == REFERENCE_TYPE:
        return {
            'mode': mode, 'operation': operation, 'product_type': product_type, 'uom': uom,
            'work_center': work_center, 'workshop': workshop, 'producer': producer,
            'capacity': None, 'capability': capability, 'capacity_source_rules': None,
            'capacity_usage_scope': None, 'independent_scheduling': False,
        }
    capacity = load(('capacity', config['standardCapacityId']), lambda: StandardCapacity.objects.filter(
        pk=config["standardCapacityId"], company_id=company_id,
    ).first())
    if capacity and capacity.product_type_id != product_type.pk:
        _fail("MANUFACTURING_PRODUCT_TYPE_MISMATCH", "正式日产能产品类型与规则产品类型不一致")
    if capacity and capacity.uom_id != uom.pk:
        _fail("MANUFACTURING_UOM_MISMATCH", "正式日产能单位与制造模式、工序及规则单位不一致")
    if (not _active(capacity) or capacity.operation_id != operation.pk
            or capacity.product_type_id != product_type.pk or capacity.work_center_id != work_center.pk
            or capacity.uom_id != uom.pk or capacity.time_basis != "day"
            or capacity.time_basis_quantity != Decimal(1) or capacity.time_unit != "DAY"):
        _fail("MANUFACTURING_CAPACITY_INVALID", "显式日产能FK必须与公司、工序、类型、工作中心、单位及每日时间基准一致")
    quantity = _decimal(capacity.quantity)
    source_rules_snapshot = None
    from .manufacturing_capacity_scope import capacity_usage_scope_proof
    usage_scope = (capacity_usage_scope_proof(capacity, read_cache=cache) if cache is not None
        else capacity_usage_scope_proof(capacity))
    if "capacityUsageScope" in config and (
            usage_scope is None or not _trace_matches(usage_scope, config["capacityUsageScope"])):
        _fail("MANUFACTURING_CAPACITY_SCOPE_INVALID", "正式规则声明的产能用途域与已提交权威证明不一致，禁止降级至旧合同")
    if capacity.measurement_status == "measured" and quantity > 0:
        independent_scheduling = usage_scope is None
        conditions = capacity.conditions if isinstance(capacity.conditions, dict) else {}
        if "apsSourceRules" in conditions:
            from .daily_capacity_service import capacity_source_rules
            source_rules = capacity_source_rules(product_type, company_id=company_id, on_date=_today(),
                **({'read_cache': cache} if cache is not None else {}))
            if (source_rules["status"] != "VALID"
                    or operation.pk in source_rules["manifest"].get("auxiliaryOperationIds", [])
                    or capacity.pk not in {row.pk for row in source_rules["capacityRows"]}):
                _fail("MANUFACTURING_CAPACITY_INVALID", "正日产能与其已声明的正式工序适用来源规则不一致")
            source_rules_snapshot = source_rules["fact"]
    elif capacity.measurement_status == "zero_capacity" and quantity == 0:
        from .daily_capacity_service import capacity_source_rules
        source_rules = capacity_source_rules(product_type, company_id=company_id, on_date=_today(),
            **({'read_cache': cache} if cache is not None else {}))
        if (source_rules["status"] != "VALID"
                or operation.pk not in source_rules["manifest"].get("auxiliaryOperationIds", [])
                or capacity.pk not in {row.pk for row in source_rules["capacityRows"]}):
            _fail("MANUFACTURING_CAPACITY_INVALID", "零产能必须由一致的正式配套工序来源规则佐证，不能独立排期")
        source_rules_snapshot = source_rules["fact"]
        independent_scheduling = False
    else:
        _fail("MANUFACTURING_CAPACITY_INVALID", "工序需求必须有正日产能或受正式规则证明的配套零产能")
    return {
        "mode": mode, "operation": operation, "product_type": product_type, "uom": uom,
        "work_center": work_center, "workshop": workshop, "producer": producer,
        "capacity": capacity, "capability": capability,
        "capacity_source_rules": source_rules_snapshot,
        "capacity_usage_scope": usage_scope,
        "independent_scheduling": independent_scheduling,
    }


def _snapshot(rule, config, selector, rows):
    mode, operation, capacity = rows["mode"], rows["operation"], rows["capacity"]
    work_center, product_type = rows["work_center"], rows["product_type"]
    source_rules = rows["capacity_source_rules"]
    if (isinstance(source_rules, dict)
            and source_rules.get("contractVersion") == "PCE-APS-CAPACITY-SOURCE-RULES-V1"
            and source_rules.get("status") == "VALID"):
        # V1 persisted this label in immutable EOR hashes. Keep that wire
        # representation stable; current UI meanings use the live facts.
        source_rules = {**source_rules, "statusLabel": "已读取一致的正式空白及配套工序来源规则"}
    snapshot = {
        "contractVersion": CONTRACT, "factSource": "server",
        "ruleId": rule.pk, "ruleVersion": rule.version,
        "modeId": mode.pk, "modeVersion": mode.version,
        "workCenterId": work_center.pk, "standardCapacityId": capacity.pk if capacity else None,
        "ruleSpecificationHash": specification_hash(rule.specification),
        "factoryScope": {"companyId": rule.company_id, "workshopId": rows["workshop"].pk},
        "mode": {
            "id": mode.pk, "code": mode.code, "version": mode.version,
            "status": mode.status, "uomId": mode.uom_id,
            "effectiveFrom": _date_text(mode, "effective_from"),
            "effectiveTo": _date_text(mode, "effective_to"),
        },
        "operation": {"id": operation.pk, "companyId": operation.company_id,
                      "workshopId": operation.workshop_id, "uomId": operation.calculation_uom_id},
        "workCenter": {
            "id": work_center.pk, "companyId": work_center.company_id,
            "workshopId": work_center.workshop_id,
            "effectiveFrom": _date_text(work_center, "effective_from"),
            "effectiveTo": _date_text(work_center, "effective_to"),
            "operationCapabilityId": rows["capability"].pk if rows["capability"] else None,
        },
        "productType": {"id": product_type.pk, "productCategoryId": product_type.product_category_id,
                        "manufacturingProcessTypeId": product_type.manufacturing_process_type_id},
        "standardCapacity": None if capacity is None else {
            "id": capacity.pk, "companyId": capacity.company_id, "operationId": capacity.operation_id,
            "workCenterId": capacity.work_center_id, "productTypeId": capacity.product_type_id,
            "quantity": str(capacity.quantity), "uomId": capacity.uom_id,
            "measurementStatus": capacity.measurement_status, "timeBasis": capacity.time_basis,
            "timeBasisQuantity": str(capacity.time_basis_quantity), "timeUnit": capacity.time_unit,
            "effectiveFrom": _date_text(capacity, "effective_from"),
            "effectiveTo": _date_text(capacity, "effective_to"),
            "conditions": _json(capacity.conditions, "standardCapacity.conditions"),
            "independentApsSchedulingAllowed": rows["independent_scheduling"],
            "capacitySourceRules": source_rules,
        },
        "sourceSelector": _json(selector, "sourceSelector"),
        "producerSpecificationHash": specification_hash(rows["producer"].specification),
        "factDisposition": config["factDisposition"], "unitConversionApplied": False,
    }
    if rows["capacity_usage_scope"] is not None:
        snapshot["standardCapacity"]["capacityUsageScope"] = rows["capacity_usage_scope"]
    if config.get('capacityMode') == REFERENCE_TYPE:
        snapshot['capacityMode'] = REFERENCE_TYPE
        snapshot['quantitativeOccupancyAllowed'] = False
        snapshot['independentDurationAllowed'] = False
    return snapshot


def publication_config_validation(rule, *, require_released=False):
    """Check a configuration before publication without inventing source facts.

    Draft/reviewed rules are accepted for publication checks. All referenced
    manufacturing modes and producing rules must already be released. Runtime
    generation additionally requires the EOR rule itself to be released.
    """
    contract = _configuration(rule, require_released=require_released)
    if contract is None:
        return None
    spec, config, selector = contract
    rows = _formal_references(rule, spec, config, selector)
    if "routingContext" in config:
        from .manufacturing_routing_context import publication_routing_validation
        publication_routing_validation(rule, spec, config, rows)
    return _snapshot(rule, config, selector, rows)


def configured_source_candidate(*, selector, fact):
    """Apply an explicitly opted-in selector before attempting an EOR.

    Historical rules retain their canonical-field/producer candidate contract.
    Classified facts can use complete version and JSON trace predicates; the
    actual generation still revalidates the full source and resource proof.
    """
    if (fact.canonical_field != selector.get("canonicalField")
            or fact.rule_id != selector.get("producerRuleId")):
        return False
    if "candidatePolicy" not in selector:
        return True
    if selector["candidatePolicy"] != "MATCH_CONFIGURED_TRACE":
        _fail("MANUFACTURING_CONFIG_INVALID", "来源候选策略未经正式配置")
    detail = fact.source_detail if fact.source_detail_id else None
    return bool(detail and detail.rule_id == selector["producerRuleId"]
                and detail.rule_version == selector["producerRuleVersion"]
                and isinstance(fact.trace, dict)
                and _trace_matches(fact.trace, selector["traceEquals"]))


def validate_manufacturing_rule_context(*, rule, origin, fact, operation, uom, product_type, read_cache=None,
                                       user=None, generation_context=None, expected_preparation_context=None):
    """Return the exact immutable-input context, or fail before creating an EOR."""
    from .operation_requirement_service import _ReadOnlyProofCache
    if isinstance(read_cache, _ReadOnlyProofCache) and not read_cache.is_current(rule.company_id):
        read_cache = None
    contract = _configuration(rule, require_released=True)
    if contract is None:
        return None
    spec, config, selector = contract
    # The caller owns this dictionary for one read transaction. Failed proofs
    # are never stored, and source-specific checks below still run every time.
    resource_key = ('manufacturing_references', rule.company_id, rule.pk,
                    rule.version, specification_hash(spec), _today())
    if read_cache is None:
        rows = _formal_references(rule, spec, config, selector)
    else:
        if resource_key not in read_cache:
            read_cache[resource_key] = _formal_references(rule, spec, config, selector, read_cache=read_cache)
        rows = read_cache[resource_key]
    if (operation.pk != rows["operation"].pk or product_type.pk != rows["product_type"].pk
            or uom.pk != rows["uom"].pk):
        _fail("MANUFACTURING_CONFIG_INVALID", "实际生成上下文与正式规则显式引用不一致")
    instance = origin.engineering_instance
    if (origin.company_id != rule.company_id or not instance
            or instance.company_id != rule.company_id
            or instance.product_category_id != product_type.product_category_id
            or instance.selected_process_type_id != product_type.manufacturing_process_type_id):
        _fail("MANUFACTURING_PRODUCT_TYPE_MISMATCH", "规则产品类型必须精确匹配来源工程实例的产品分类及选定工艺")
    detail = fact.source_detail if fact.source_detail_id else None
    trace = fact.trace if isinstance(fact.trace, dict) else {}
    if (fact.calculation_id != origin.pk or fact.status != "active"
            or fact.source_type != "ENGINEERING_DERIVED" or not detail
            or detail.calculation_id != origin.pk or detail.status != "succeeded"
            or fact.canonical_field != selector["canonicalField"]
            or fact.rule_id != selector["producerRuleId"]
            or detail.rule_id != selector["producerRuleId"]
            or detail.rule_version != selector["producerRuleVersion"]
            or not _trace_matches(trace, selector["traceEquals"])):
        _fail("MANUFACTURING_SOURCE_SELECTOR_MISMATCH", "来源事实、生产规则版本或追溯条件不满足正式选择器")
    if fact.uom_id != uom.pk or detail.uom_id != uom.pk:
        _fail("MANUFACTURING_UOM_MISMATCH", "来源工程事实与制造模式、工序及日产能单位必须完全一致")
    snapshot = _snapshot(rule, config, selector, rows)
    preparation_runtime = None
    if config.get('capacityMode') == REFERENCE_TYPE:
        snapshot[CONTEXT_KEY], preparation_runtime = source_preparation_context(user=user, generation_context=generation_context,
            origin=origin, fact=fact, operation=operation, product_type=product_type,
            read_cache=read_cache, expected_context=expected_preparation_context,
            work_center=rows['work_center'], return_runtime_context=True)
    if "routingContext" in config:
        from .manufacturing_routing_context import validate_routing_context
        snapshot["routingContext"] = validate_routing_context(
            rule=rule, spec=spec, config=config, rows=rows, origin=origin, fact=fact,
            **({'runtime_context': preparation_runtime} if preparation_runtime is not None else {}))
    snapshot["selectedSource"] = {
        "calculationId": origin.pk, "engineeringInstanceId": instance.pk,
        "factId": fact.pk, "canonicalField": fact.canonical_field,
        "factType": fact.value_type, "sourceDetailId": detail.pk,
        "producerRuleId": fact.rule_id, "producerRuleVersion": detail.rule_version,
        "uomId": fact.uom_id, "value": _json(fact.value, "sourceFact.value"),
        "traceMatches": {key: trace[key] for key in selector["traceEquals"]},
    }
    if "objectTraceKeys" in selector:
        engineering_object = {}
        for key in selector["objectTraceKeys"]:
            value = trace.get(key)
            if not ((type(value) is int and value > 0)
                    or (isinstance(value, str) and value.strip() and value == value.strip())):
                _fail("MANUFACTURING_SOURCE_SELECTOR_MISMATCH", "来源事实缺少配置要求的正式工程对象追溯字段", field=key)
            engineering_object[key] = value
        snapshot["selectedSource"]["sourceEngineeringObject"] = _json(engineering_object, "sourceEngineeringObject")
    return snapshot
