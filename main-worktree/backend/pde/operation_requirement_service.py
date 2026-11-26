from pde.baseline_usage_service import production_baselines, production_status
"""Audited operation workload handoff over released rules and fixed source facts.

The old engineering executor is never called. Source calculations, derived
facts, manufacturing outputs and production plans are exclusively read.
"""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from hashlib import sha256
import marshal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Model, Q
from django.utils import timezone

from masterdata.models import CodeRule, UnitOfMeasure
from planning.models import ProductionPlan
from system.authorization import AuthorizationService
from system.models import Company, Process
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state, record_projected_business_transition,
    transition_business_object,
)
from .daily_capacity_service import DailyCapacityError
from .operation_read_diagnostics import read_span
from .engineering_rule_foundation import (
    EngineeringRuleError, canonical_json, evaluate_specification, specification_hash,
    validate_specification,
)
from .models import (
    CapacityProductType, EngineeringCalculationDetail, EngineeringCalculationRecord,
    EngineeringDerivedFact, EngineeringOperationRequirement, EngineeringRuleDefinition,
    ProductionPlanOperationRequirementAllocation, RoutingStep,
)
from .production_foundation_service import ProductionFoundationError, _actor_chain, _audit, _snapshot
from .plan_step_context_service import (resolve_step_context, bind_plan_context, effective_output,
    effective_calculation, effective_baseline, source_selection, PlanStepContextError)
from .operation_non_quantified_context import (
    REFERENCE_TYPE, TYPE_KEY, CONTEXT_KEY, reference_type, reference_record_errors,
)

CONTRACT = 'PCE-OPERATION-REQUIREMENT-HANDOFF-V1'
VIEW = 'production.engineering.calculation.view'
EXECUTE = 'production.engineering.calculation.execute'
PLAN_VIEW = 'planning.view'
KNOWN_BASES = {'PER_BASIS_QUANTITY', 'SOURCE_SCOPE_TOTAL'}
_CURRENT_CALL_ACTOR = object()


def _bind_current_actor(cache, user):
    """Bind only the actual public caller, including write-call plain caches.

    This is not persisted or taken from a requirement's historical creator.
    Preparation permissions are still freshly checked by the native reader.
    """
    cache[_CURRENT_CALL_ACTOR] = user
    return cache


class OperationRequirementError(DailyCapacityError):
    def __init__(self, code, message, details=None):
        super().__init__(code, message)
        self.message, self.details = message, details or {}


class _ReadOnlyProofCache(dict):
    """Call-owned reads, usable only while their original atomic block exists."""

    def __init__(self, user):
        super().__init__()
        connection = transaction.get_connection()
        if not connection.in_atomic_block or not connection.atomic_blocks:
            raise RuntimeError('Read proofs require an active atomic read')
        self.company_id, self.user_id = user.company_id, user.pk
        self.user = user
        self.database_alias = connection.alias
        self._connection, self._atomic_block = connection, connection.atomic_blocks[-1]
        self._raw_connection = connection.connection
        self._write_epoch = getattr(self._raw_connection, 'total_changes', None)
        self.allocation_validation_cache = {}
        self.allocation_validation_epoch = None
        self.budget_proofs = {}

    def is_current(self, company_id):
        connection = transaction.get_connection(self.database_alias)
        actor = self.get(_CURRENT_CALL_ACTOR, self.user)
        if not (company_id == self.company_id and connection is self._connection
                and connection.connection is self._raw_connection and self._raw_connection is not None
                and connection.in_atomic_block and self._atomic_block in connection.atomic_blocks
                and getattr(actor, 'pk', None) == self.user_id
                and getattr(actor, 'company_id', None) == company_id):
            return False
        epoch = getattr(self._raw_connection, 'total_changes', None)
        if epoch is None:
            return False
        if epoch != self._write_epoch:
            # A same-connection write invalidates every request-local source,
            # scope, lifecycle and manufacturing proof, not just allocations.
            self.invalidate_proofs()
            self._write_epoch = epoch
        return True

    def invalidate_proofs(self):
        actor = self.get(_CURRENT_CALL_ACTOR, self.user)
        self.clear()
        self.allocation_validation_cache.clear()
        self.allocation_validation_epoch = None
        self.budget_proofs.clear()
        self[_CURRENT_CALL_ACTOR] = actor


def _fail(code, message, **details):
    raise OperationRequirementError(code, message, details)


def _digest(value):
    return sha256(canonical_json(value).encode('utf-8')).hexdigest()


def _number(value, code='SOURCE_QUANTITY_INVALID'):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        _fail(code, '正式数量必须是有效十进制数值')
    if not result.is_finite() or result <= 0:
        _fail(code, '正式数量必须是有限正数')
    return result


def _quantity_text(value):
    text = format(Decimal(str(value)), 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _today():
    now = timezone.now()
    return timezone.localtime(now).date() if timezone.is_aware(now) else now.date()


def _active(row):
    today = _today()
    return bool(row and getattr(row, 'is_active', True)
        and (not getattr(row, 'effective_from', None) or row.effective_from <= today)
        and (not getattr(row, 'effective_to', None) or row.effective_to >= today))


def _authorize(user, permission):
    company_id = getattr(user, 'company_id', None)
    if not company_id or not getattr(user, 'is_active', False):
        _fail('ORGANIZATION_REQUIRED', '办理账号必须启用且具有明确公司范围')
    if not Company.objects.filter(pk=company_id, is_active=True).exists():
        _fail('ORGANIZATION_INACTIVE', '公司不在有效经营范围')
    decision = AuthorizationService.decide(user=user, action_code=permission,
        organization_id=company_id, business_object={'organizationId': company_id})
    if not decision.get('allowed'):
        _fail(decision.get('decisionCode', 'PERMISSION_DENIED'), decision.get('reason', '当前账号未获正式动作权限'))
    return decision


def _executor(user):
    try:
        return _actor_chain(user)
    except ProductionFoundationError as exc:
        raise OperationRequirementError(exc.code, exc.message, exc.details) from exc


def _allocation_executor(user):
    """Keep the existing actor gate, with the current business action's label."""
    try:
        return _executor(user)
    except OperationRequirementError as exc:
        if exc.code == 'FORMAL_EXECUTION_CHAIN_REQUIRED':
            raise OperationRequirementError(exc.code,
                '正式计划分配执行账号必须关联在职员工、启用岗位和有效职责。', exc.details) from exc
        raise


def _key(value):
    key = str(value or '').strip()
    if not key or len(key) > 160:
        _fail('IDEMPOTENCY_KEY_REQUIRED', '正式办理必须提供不超过160字符的幂等键')
    return key


def _read_once(read_cache, key, loader):
    """Reuse ORM reads only inside one source-read transaction, never globally."""
    if isinstance(read_cache, _ReadOnlyProofCache) and not read_cache.is_current(read_cache.company_id):
        return loader()
    if read_cache is None:
        return loader()
    if key not in read_cache:
        read_cache[key] = loader()
    return read_cache[key]


def _read_guarded_raw(read_cache, key, loader):
    """Reuse exact raw rows, never an admission or a completed readback.

    Full loaded values retain their types; deferred fields are marked without
    reading credentials or other unused columns. Protocol2 ignores harmless
    alias/refcount changes. Unsupported values stay on the original SQL path.
    """
    cache = _requirement_read_cache(read_cache, getattr(read_cache, 'company_id', None))
    if cache is None:
        return loader()

    def concrete_value(value):
        kind = type(value)
        if kind in (date, datetime):
            return value.isoformat()
        if kind is Decimal:
            return str(value)
        if kind not in (type(None), bool, int, float, str, bytes, dict, list, tuple):
            raise TypeError('Unsupported raw concrete value')
        return value

    def snapshot(value, active):
        if isinstance(value, Model):
            if id(value) in active:
                raise ValueError('Cyclic loaded model graph')
            nested = active | {id(value)}
            fields = []
            for field in value._meta.concrete_fields:
                if field.attname not in value.__dict__:
                    fields.append((field.attname, 'deferred'))
                    continue
                raw = value.__dict__[field.attname]
                token = (type(raw).__module__, type(raw).__qualname__)
                converted = concrete_value(raw)
                fields.append((field.attname, token, converted))
            related = tuple((name, snapshot(row, nested))
                for name, row in sorted(value._state.fields_cache.items()))
            return ('model', value._meta.label_lower, tuple(fields), related)
        if type(value) is list:
            return ('list', tuple(snapshot(row, active) for row in value))
        if type(value) is tuple:
            return ('tuple', tuple(snapshot(row, active) for row in value))
        if type(value) is dict:
            return ('dict', tuple((snapshot(name, active), snapshot(row, active)) for name, row in value.items()))
        token = (type(value).__module__, type(value).__qualname__)
        converted = concrete_value(value)
        return ('value', token, converted)

    def guard(value):
        try:
            return marshal.dumps(snapshot(value, set()), 2)
        except (AttributeError, RecursionError, TypeError, ValueError):
            return None

    raw_key = ('guarded_raw_rows', cache.company_id, cache.user_id, _today(), key)

    def load():
        value = loader()
        return value, guard(value)

    value, saved = _read_once(cache, raw_key, load)
    if saved is None:
        cache.pop(raw_key, None)
        return value
    if saved == guard(value):
        return value
    # SQL prefilter fields are part of the guard too. In-memory pollution may
    # never turn a previously matching publication row into a false approval.
    cache.invalidate_proofs()
    value, saved = load()
    if saved is not None and cache.is_current(cache.company_id):
        cache[raw_key] = (value, saved)
    return value


def _requirement_read_cache(read_cache, company_id):
    return (read_cache if isinstance(read_cache, _ReadOnlyProofCache)
        and read_cache.is_current(company_id) else None)


def _source_read_cache(user, read_cache):
    if (isinstance(read_cache, _ReadOnlyProofCache) and read_cache.user_id == user.pk
        and read_cache.is_current(user.company_id)):
        return read_cache
    return _ReadOnlyProofCache(user)


def _allocation_read_cache(read_cache, company_id):
    """Only a live, actor-owned read may share successful allocation proofs."""
    cache = _requirement_read_cache(read_cache, company_id)
    if cache is None:
        return {}
    actor = cache.get(_CURRENT_CALL_ACTOR, cache.user)
    raw = cache._connection.connection
    if getattr(actor, 'pk', None) != cache.user_id or raw is None or not hasattr(raw, 'total_changes'):
        return {}
    if cache.allocation_validation_epoch != raw.total_changes:
        cache.allocation_validation_cache.clear()
        cache.allocation_validation_epoch = raw.total_changes
    return cache.allocation_validation_cache


def _read_allocation_rows(company_id, *, production_plan_id=None,
                          sales_order_item_id=None, routing_step_id=None, read_cache=None):
    """Batch raw rows in one actor-owned read, without caching an approval.

    A route reads the same plan at every step. Load its full ordered row set
    once, then partition it without hiding any retained row from the original
    validators. The whole-order budget uses a separate unfiltered source set;
    every row in that set is still validated before source-version exclusion.
    Plain write/proposal caches and expired/foreign typed caches never reuse
    these rows. The typed cache's connection/atomic/write-epoch guard remains
    the sole lifetime owner.
    """
    if (production_plan_id is None) == (sales_order_item_id is None):
        raise ValueError('Exactly one allocation read scope is required')
    cache = _requirement_read_cache(read_cache, company_id)
    scope = ('plan', production_plan_id) if production_plan_id is not None else ('order_item', sales_order_item_id)

    def load():
        rows = ProductionPlanOperationRequirementAllocation.objects.filter(company_id=company_id)
        if production_plan_id is not None:
            rows = rows.filter(production_plan_id=production_plan_id)
        else:
            rows = rows.filter(operation_requirement__source_calculation__sales_order_item_id=sales_order_item_id)
        query = rows.select_related('operation_requirement__source_detail',
            'operation_requirement__calculation', 'operation_requirement__audit_record',
            'operation_requirement__source_fact',
            'audit_record', 'routing_step').prefetch_related(
                'operation_requirement__source_detail__rule',
                'operation_requirement__source_calculation__sales_order_item',
                'production_plan__planning_requirement__demand__sales_order_item__sales_order',
                'production_plan__planning_requirement__demand__manufacturing_output')
        if cache is not None:
            # Allocation validation consumes only the audit's current state;
            # its unrelated prior snapshot is not a source/freeze hash input.
            query = query.defer('audit_record__before_snapshot')
        loaded = list(query)
        # Batch only raw transitions and their audit rows. The existing native
        # requirement/history checks still validate every row before approval.
        if cache is not None:
            requirements = [row.operation_requirement for row in loaded]
            _prefetch_requirement_history(requirements, company_id, cache)
            _prefetch_generation_references(requirements, company_id, cache)
        return loaded

    rows = _read_once(cache, ('raw_allocation_rows', company_id,
        cache.user_id if cache is not None else None, *scope), load)
    # Filtering a stable ordered list preserves the model's original ordering.
    # Do not use a successful proof or a client-provided subset to form it.
    return [row for row in rows if routing_step_id is None or row.routing_step_id == routing_step_id]


def _prefetch_requirement_history(requirements, company_id, read_cache):
    """Batch raw history reads; every original per-row proof still runs below."""
    cache = _requirement_read_cache(read_cache, company_id)
    if cache is None:
        return
    objects = {(type(req.calculation).__name__, req.calculation_id) for req in requirements}
    objects.update((type(req.source_detail).__name__, req.source_detail_id) for req in requirements)
    missing = {identity for identity in objects
        if ('requirement_transitions', company_id, *identity) not in cache}
    if not missing:
        return
    filters = Q()
    for object_type in {identity[0] for identity in missing}:
        filters |= Q(object_type=object_type,
            object_id__in=[pk for kind, pk in missing if kind == object_type])
    transitions = list(BusinessStateTransition.objects.filter(filters).order_by('version'))
    for identity in missing:
        cache[('requirement_transitions', company_id, *identity)] = []
    audit_ids = set()
    prefix = 'OrganizationOperatingAuditRecord:'
    for row in transitions:
        cache[('requirement_transitions', company_id, row.object_type, row.object_id)].append(row)
        reference = row.audit_reference
        if isinstance(reference, str) and reference.startswith(prefix) and reference[len(prefix):].isdigit():
            audit_ids.add(int(reference[len(prefix):]))
    if audit_ids:
        for audit in OrganizationOperatingAuditRecord.objects.filter(pk__in=audit_ids).only(
                'pk', 'organization_id', 'actor_id', 'target_type', 'target_id', 'action_code', 'after_snapshot'):
            cache[('requirement_transition_audit', company_id, audit.pk)] = audit


def _prefetch_generation_references(requirements, company_id, read_cache):
    """Batch only the native generation reader's raw FK references.

    These keys hold the same rows (or absence) as _generation_context's
    individual queries. No source, rule, permission or frozen-proof approval
    is stored here: every original validator still consumes and checks each
    requirement. The actor/atomic/connection/write-epoch cache guard owns the
    lifetime, so write/proposal and expired/foreign caches are never primed.
    """
    cache = _requirement_read_cache(read_cache, company_id)
    if cache is None:
        return
    requirements = tuple(requirements)
    origin_ids = {req.source_calculation_id for req in requirements
        if req.source_calculation_id is not None
        and ('origin', company_id, req.source_calculation_id) not in cache}
    if origin_ids:
        origins = EngineeringCalculationRecord.objects.select_related(
            'source_record', 'sales_order_item__sales_order', 'sales_order_item__uom',
            'engineering_instance',
        ).filter(pk__in=origin_ids, company_id=company_id)
        for origin_id in origin_ids:
            cache[('origin', company_id, origin_id)] = None
        for origin in origins:
            cache[('origin', company_id, origin.pk)] = origin

    fact_ids_by_origin = {}
    for req in requirements:
        key = ('source_fact', company_id, req.source_calculation_id, req.source_fact_id)
        if (req.source_fact_id is not None and key not in cache
                and cache.get(('origin', company_id, req.source_calculation_id)) is not None):
            fact_ids_by_origin.setdefault(req.source_calculation_id, set()).add(req.source_fact_id)
    if fact_ids_by_origin:
        filters = Q()
        for origin_id, fact_ids in fact_ids_by_origin.items():
            filters |= Q(calculation_id=origin_id, pk__in=fact_ids)
            for fact_id in fact_ids:
                cache[('source_fact', company_id, origin_id, fact_id)] = None
        facts = EngineeringDerivedFact.objects.select_related('source_detail__rule', 'uom').filter(
            filters, status='active')
        for fact in facts:
            cache[('source_fact', company_id, fact.calculation_id, fact.pk)] = fact

    rule_ids = {req.source_detail.rule_id for req in requirements
        if ('rule', company_id, req.source_detail.rule_id) not in cache}
    if rule_ids:
        rules = EngineeringRuleDefinition.objects.filter(pk__in=rule_ids, company_id=company_id)
        for rule_id in rule_ids:
            cache[('rule', company_id, rule_id)] = None
        for rule in rules:
            cache[('rule', company_id, rule.pk)] = rule


def _unit(unit_id, company_id, code='OPERATION_UOM_MISMATCH', *, read_cache=None):
    row = _read_once(read_cache, ('uom', company_id, unit_id), lambda:
        UnitOfMeasure.objects.filter(pk=unit_id, company_id=company_id, is_active=True).first())
    if not row:
        _fail(code, '计量单位缺失、停用或不属于当前公司')
    return row


def _unit_token(unit, token):
    return isinstance(token, str) and bool(token.strip()) and token in {
        value for value in (unit.code, unit.name, unit.symbol) if isinstance(value, str) and value.strip()}


def _source_output_proof(origin, fact, detail, company_id):
    producer = detail.rule
    if (fact.rule_id != detail.rule_id or producer.company_id != company_id
        or detail.rule_code != producer.rule_code or detail.rule_version != producer.version):
        _fail('SOURCE_OUTPUT_DOMAIN_UNPROVEN', '来源事实没有同一生产规则及精确版本的成功明细')
    producer_spec = producer.specification
    outputs = producer_spec.get('outputs') if isinstance(producer_spec, dict) else None
    if not isinstance(outputs, list) or len(outputs) != 1 or not isinstance(outputs[0], dict):
        _fail('SOURCE_OUTPUT_DOMAIN_UNPROVEN', '来源生产规则缺少可证明的原始输出合同')
    if outputs[0].get('resultDomain') != 'DERIVED_FACT':
        _fail('SOURCE_OUTPUT_DOMAIN_MISMATCH', '来源成功明细不是原生DERIVED_FACT输出')
    if fact.value_type != outputs[0].get('valueType'):
        _fail('SOURCE_OUTPUT_DOMAIN_UNPROVEN', '来源事实类型与固定生产规则输出类型不一致')
    producer_hash = specification_hash(producer_spec)
    trace = fact.trace if isinstance(fact.trace, dict) else {}
    direct_proof = (trace.get('resultDomain') == 'DERIVED_FACT' and trace.get('detailId') == detail.pk
        and trace.get('ruleCode') == detail.rule_code and trace.get('ruleVersion') == detail.rule_version
        and trace.get('specificationHash') == producer_hash
        and detail.output_name == fact.canonical_field == outputs[0].get('canonicalName'))
    source_trace = origin.trace if isinstance(origin.trace, dict) else {}
    graph = source_trace.get('ruleGraphSnapshot')
    graph_proof = isinstance(graph, list) and any(isinstance(row, dict)
        and row.get('ruleId', row.get('id')) == producer.pk and row.get('ruleCode') == detail.rule_code
        and row.get('ruleVersion', row.get('version')) == detail.rule_version
        and row.get('specificationHash') == producer_hash for row in graph)
    frozen_results = source_trace.get('resultSnapshot')
    # The approved object adapter explicitly maps Excel canonical columns to
    # named successful outputs; that frozen map is authority, never a guess.
    mapped_proof = graph_proof and isinstance(frozen_results, list) and any(isinstance(row, dict)
        and row.get('factId') == fact.pk and row.get('detailId') == detail.pk
        and row.get('canonicalField') == fact.canonical_field
        and row.get('displayName', row.get('canonicalField')) == detail.output_name
        and row.get('ruleCode') == detail.rule_code and row.get('ruleVersion') == detail.rule_version
        and row.get('value') == fact.value for row in frozen_results)
    if not direct_proof and not mapped_proof:
        _fail('SOURCE_OUTPUT_DOMAIN_UNPROVEN', '缺少固定DERIVED_FACT域、字段映射或生产规则哈希证据')
    return {'producerRuleId': producer.pk, 'producerVersion': producer.version,
        'producerSpecificationHash': producer_hash, 'resultDomain': 'DERIVED_FACT',
        'sourceCanonicalField': fact.canonical_field, 'sourceOutputName': detail.output_name}


@read_span('generationContext')
def _generation_context(company_id, source_calculation_id, source_fact_id, rule_id, *, evaluate=False,
                        supersedes_requirement_id=None, read_cache=None, user=None,
                        generation_context=None, expected_preparation_context=None):
    if isinstance(read_cache, _ReadOnlyProofCache) and not read_cache.is_current(company_id):
        read_cache = None
    if user is None and isinstance(read_cache, _ReadOnlyProofCache):
        user = read_cache.user
    if user is None and isinstance(read_cache, dict):
        user = read_cache.get(_CURRENT_CALL_ACTOR)
    origin = _read_once(read_cache, ('origin', company_id, source_calculation_id), lambda:
        EngineeringCalculationRecord.objects.select_related(
        'source_record', 'sales_order_item__sales_order', 'sales_order_item__uom', 'engineering_instance',
    ).filter(pk=source_calculation_id, company_id=company_id).first())
    if not origin or origin.scope not in {'order_engineering', 'fact_extension'} or origin.status != 'completed':
        _fail('SOURCE_CALCULATION_MISSING', '必须选择同公司已完成的正式来源工程核算')
    if not all((origin.source_record_id, origin.sales_order_item_id, origin.engineering_instance_id)):
        _fail('SOURCE_CALCULATION_CONTEXT_MISSING', '来源核算缺少正式来源记录、订单行或工程实例FK')
    item, instance, source = origin.sales_order_item, origin.engineering_instance, origin.source_record
    if (source.company_id != company_id or source.status != 'confirmed'
        or item.sales_order.company_id != company_id or instance.company_id != company_id
        or instance.sales_order_item_id != item.pk or instance.source_record_id != source.pk):
        _fail('SOURCE_FACT_MISMATCH', '来源核算、订单行、工程实例和EngineeringSourceRecord血缘不一致')
    fact = _read_once(read_cache, ('source_fact', company_id, origin.pk, source_fact_id), lambda:
        EngineeringDerivedFact.objects.select_related('source_detail__rule', 'uom').filter(
        pk=source_fact_id, calculation_id=origin.pk, status='active',
    ).first())
    if not fact or fact.source_type != 'ENGINEERING_DERIVED' or not fact.source_detail_id:
        _fail('SOURCE_FACT_MISMATCH', '来源必须是固定核算的真实有效派生事实及成功明细')
    detail = fact.source_detail
    if detail.calculation_id != origin.pk or detail.status != 'succeeded' or detail.uom_id != fact.uom_id:
        _fail('SOURCE_FACT_MISMATCH', '来源派生事实与成功明细的核算或单位血缘不一致')
    fact_extension = None
    if origin.scope == 'fact_extension':
        from .engineering_fact_extension_service import validate_extension_fact
        fact_extension = _read_once(read_cache,
            ('fact_extension_proof', company_id, origin.pk, fact.pk, origin.input_hash, origin.result_hash),
            lambda: validate_extension_fact(origin, fact, read_cache=read_cache))
    producer_proof = _source_output_proof(origin, fact, detail, company_id)
    if not isinstance(fact.value, dict) or not isinstance(detail.output_value, dict):
        _fail('SOURCE_FACT_MISMATCH', '来源事实或成功明细缺少真实十进制输出对象')
    source_value = _number(fact.value.get('decimal'))
    if source_value != _number(detail.output_value.get('decimal')):
        _fail('SOURCE_FACT_MISMATCH', '来源事实与成功明细数量不一致')
    source_uom = _unit(fact.uom_id, company_id, read_cache=read_cache)
    rule = _read_once(read_cache, ('rule', company_id, rule_id), lambda:
        EngineeringRuleDefinition.objects.filter(pk=rule_id, company_id=company_id).first())
    if not rule or rule.status != 'released' or not _active(rule):
        _fail('OPERATION_RULE_MAPPING_MISSING', '没有当前有效且已发布的正式工序需求规则')
    try:
        spec = validate_specification(rule.specification)
    except EngineeringRuleError as exc:
        raise OperationRequirementError(exc.code, exc.message, exc.details) from exc
    if spec.get('ruleRole') == 'OPERATION_ALLOCATION_COMPOSITION':
        _fail('NON_EXECUTABLE_RULE', '组合声明不能生成工程事实或正式工序需求')
    output = spec['outputs'][0]
    if output['resultDomain'] != 'OPERATION_REQUIREMENT':
        _fail('OPERATION_RULE_MAPPING_MISSING', '规则必须原生声明OPERATION_REQUIREMENT，不能改写派生事实结果域')
    operation_id = output.get('operationId')
    if type(operation_id) is not int or operation_id <= 0:
        _fail('OPERATION_RULE_MAPPING_MISSING', '规则输出必须声明正式工序ID')
    operation = _read_once(read_cache, ('operation', company_id, operation_id), lambda:
        Process.objects.select_related('calculation_uom').filter(pk=operation_id, company_id=company_id).first())
    if not _active(operation) or not operation.calculation_uom_id:
        _fail('OPERATION_RULE_MAPPING_MISSING', '规则引用的工序或核算单位未确认或未启用')
    uom = _unit(operation.calculation_uom_id, company_id, read_cache=read_cache)
    if (not _unit_token(uom, output.get('unit')) or ('uomId' in output
        and (type(output['uomId']) is not int or output['uomId'] != uom.pk))):
        _fail('OPERATION_UOM_MISMATCH', '规则输出单位必须明确等于工序正式核算单位')
    if type(output.get('productTypeId')) is not int or output['productTypeId'] <= 0:
        _fail('ALLOCATION_PRODUCT_TYPE_MISSING', '规则版本未声明正式产品类型FK映射')
    product_type = _read_once(read_cache, ('product_type', company_id, output['productTypeId']), lambda:
        CapacityProductType.objects.filter(pk=output['productTypeId'], company_id=company_id).first())
    if not _active(product_type):
        _fail('ALLOCATION_PRODUCT_TYPE_MISSING', '规则产品类型引用缺失、停用或跨公司')
    basis = output.get('quantityBasis')
    if basis not in KNOWN_BASES:
        _fail('QUANTITY_BASIS_MISSING', '规则版本未声明可确认的工序数量口径')
    if output.get('sourceScope') != 'SALES_ORDER_ITEM':
        _fail('SOURCE_SCOPE_MAPPING_MISSING', '本阶段仅支持规则明确声明SALES_ORDER_ITEM正式来源范围')
    manufacturing_config = spec.get('manufacturing')
    new_contract = isinstance(manufacturing_config, dict) and manufacturing_config.get('contractVersion') == 'PCE-MANUFACTURING-EOR-RULE-V1'
    if new_contract and output.get('basisQuantitySource') == 'SALES_ORDER_ITEM':
        if basis != 'SOURCE_SCOPE_TOTAL' or 'basisQuantity' in output:
            _fail('QUANTITY_BASIS_MISMATCH', '动态来源总量必须明确SOURCE_SCOPE_TOTAL且不得混入固定数量')
        basis_qty = _number(item.quantity, 'QUANTITY_BASIS_MISSING')
    else:
        basis_qty = _number(output.get('basisQuantity'), 'QUANTITY_BASIS_MISSING')
    basis_uom_id = (item.uom_id if new_contract and output.get('basisUomSource') == 'SALES_ORDER_ITEM'
                    else output.get('basisUomId'))
    if new_contract and output.get('basisUomSource') == 'SALES_ORDER_ITEM' and 'basisUomId' in output:
        _fail('QUANTITY_BASIS_MISMATCH', '来源单位引用与固定单位不得同时声明')
    if type(basis_uom_id) is not int or basis_uom_id <= 0:
        _fail('QUANTITY_BASIS_MISSING', '规则基准单位必须是明确的正式UOM整数FK')
    basis_uom = _unit(basis_uom_id, company_id, 'QUANTITY_BASIS_MISSING', read_cache=read_cache)
    if item.uom_id != basis_uom.pk:
        _fail('PLAN_QUANTITY_UOM_MISMATCH', '规则基准单位与正式来源订单行数量单位不一致，禁止推测换算')
    budget = _number(item.quantity)
    if basis == 'SOURCE_SCOPE_TOTAL' and basis_qty != budget:
        _fail('QUANTITY_BASIS_MISMATCH', '固定来源总量的基准数量必须等于正式订单行范围总数量')
    if len(spec['inputs']) != 1:
        _fail('OPERATION_INPUT_MAPPING_MISSING', '多输入或多来源汇总尚无正式来源映射，本阶段不能猜测输入')
    input_contract = spec['inputs'][0]
    source_field = input_contract.get('sourceCanonicalField', input_contract['canonicalName'])
    if input_contract['sourceType'] != 'ENGINEERING_DERIVED' or source_field != fact.canonical_field:
        _fail('OPERATION_INPUT_MAPPING_MISSING', '规则输入没有精确绑定所选来源派生字段')
    if 'unit' in input_contract and not _unit_token(source_uom, input_contract['unit']):
        _fail('OPERATION_UOM_MISMATCH', '规则输入单位与固定来源事实单位不一致')
    inputs = {input_contract['canonicalName']: {'value': str(source_value), 'unit': source_uom.code,
        'unitDimension': source_uom.dimension}}
    source_snapshot = {
        'companyId': company_id, 'sourceCalculationId': origin.pk, 'sourceCalculationStatus': origin.status,
        'sourceCalculationInputHash': origin.input_hash, 'sourceCalculationResultHash': origin.result_hash,
        'sourceCalculationRuleGraphHash': origin.rule_graph_hash,
        'sourceRecordId': source.pk, 'sourceRecordVersion': source.source_version, 'sourceRecordHash': source.content_hash,
        'sourceFactId': fact.pk, 'sourceFactCode': fact.fact_code, 'sourceCanonicalField': fact.canonical_field,
        'sourceFactValue': fact.value, 'sourceFactUomId': fact.uom_id,
        'sourceDetailId': detail.pk, 'sourceDetailOutput': detail.output_value,
        'sourceDetailRuleId': detail.rule_id, 'sourceDetailRuleVersion': detail.rule_version,
        'sourceDetailExpression': detail.expression_snapshot,
        'sourceOutputProof': producer_proof,
        'salesOrderItemId': item.pk, 'salesOrderItemQuantity': str(budget), 'salesOrderItemUomId': item.uom_id,
        'salesOrderItemVersion': getattr(item, 'version', None),
        'salesOrderItemUpdatedAt': (getattr(item, 'updated_at').isoformat()
                                   if getattr(item, 'updated_at', None) else None),
        'engineeringInstanceId': instance.pk, 'ruleId': rule.pk, 'ruleVersion': rule.version,
        'ruleSpecificationHash': specification_hash(spec), 'operationId': operation.pk,
        'quantityBasis': basis, 'basisQuantity': str(basis_qty), 'basisUomId': basis_uom.pk,
        'productTypeId': product_type.pk, 'productCategoryId': product_type.product_category_id,
        'manufacturingProcessTypeId': product_type.manufacturing_process_type_id,
        'sourceScope': 'SALES_ORDER_ITEM',
    }
    if origin.scope == 'fact_extension':
        # Only additive fact runs extend provenance. Historical EOR source and
        # input hashes keep their exact original serialization.
        source_snapshot['factExtension'] = fact_extension
    # Only the explicit new contract extends hashes. Historical EOR snapshots
    # retain their original representation and remain readable.
    from .manufacturing_rule_configuration import validate_manufacturing_rule_context
    manufacturing = validate_manufacturing_rule_context(rule=rule, origin=origin,
        fact=fact, operation=operation, uom=uom, product_type=product_type, read_cache=read_cache,
        user=user, generation_context=generation_context,
        expected_preparation_context=expected_preparation_context)
    if manufacturing is not None:
        source_snapshot['manufacturing'] = manufacturing
    supersedes = None
    if supersedes_requirement_id is not None:
        if type(supersedes_requirement_id) is not int or supersedes_requirement_id <= 0:
            _fail('OPERATION_CORRECTION_INVALID', '替代来源必须是正式工序需求正整数ID')
        if not manufacturing or not manufacturing.get('routingContext'):
            _fail('OPERATION_CORRECTION_RULE_REQUIRED', '纠正必须启用正式来源路线版本与步骤校验合同')
        supersedes = _read_once(_requirement_read_cache(read_cache, company_id),
            ('supersedes_requirement', company_id, supersedes_requirement_id), lambda:
            EngineeringOperationRequirement.objects.select_related(
                'calculation', 'source_detail__rule', 'audit_record',
            ).filter(pk=supersedes_requirement_id, calculation__company_id=company_id).first())
        if (not supersedes or supersedes.source_calculation_id != origin.pk
                or supersedes.source_fact_id != fact.pk or supersedes.operation_id != operation.pk
                or supersedes.uom_id != uom.pk or supersedes.quantity_basis != basis
                or supersedes.basis_quantity != basis_qty or supersedes.basis_uom_id != basis_uom.pk):
            _fail('OPERATION_CORRECTION_SOURCE_MISMATCH', '纠正只能替代同公司、同来源事实、同工序及同数量口径的历史需求')
        _validate_requirement(supersedes, company_id, read_cache=read_cache, user=user)
        source_snapshot['sourceReplacement'] = {
            'operationRequirementId': supersedes.pk, 'calculationId': supersedes.calculation_id,
            'generationKey': supersedes.generation_key, 'sourceHash': supersedes.source_hash,
            'inputHash': supersedes.input_hash, 'recordHash': _digest(_snapshot(supersedes)),
            'ruleId': supersedes.source_detail.rule_id, 'ruleVersion': supersedes.source_detail.rule_version,
        }
    source_hash = _digest(source_snapshot)
    input_snapshot = {'inputs': inputs, 'sourceHash': source_hash, 'ruleSpecification': spec}
    input_hash = _digest(input_snapshot)
    generation_key = 'eor:' + _digest({'contract': CONTRACT, 'sourceHash': source_hash, 'inputHash': input_hash})
    result = None
    evaluation_started_at = evaluation_finished_at = None
    if evaluate:
        evaluation_started_at = timezone.now()
        try:
            result = evaluate_specification(spec, inputs)
        except EngineeringRuleError as exc:
            raise OperationRequirementError(exc.code, exc.message, exc.details) from exc
        if result['resultDomain'] != 'OPERATION_REQUIREMENT':
            _fail('OPERATION_RULE_MAPPING_MISSING', '执行结果域与正式规则声明不一致')
        _number(result['value'], 'OPERATION_WORKLOAD_INVALID')
        evaluation_finished_at = timezone.now()
    return dict(origin=origin, fact=fact, rule=rule, spec=spec, operation=operation, uom=uom,
        basis=basis, basis_qty=basis_qty, basis_uom=basis_uom, budget=budget, inputs=inputs,
        product_type=product_type, supersedes=supersedes,
        source_snapshot=source_snapshot, source_hash=source_hash, input_snapshot=input_snapshot,
        input_hash=input_hash, generation_key=generation_key, result=result,
        evaluation_started_at=evaluation_started_at, evaluation_finished_at=evaluation_finished_at)


def _state_audit(user, obj, before, after, decision, chain, reason):
    return _audit(user=user, organization_id=user.company_id, action_code=EXECUTE, instance=obj,
        before=before, after=after, reason=reason, authorization=decision, execution_chain=chain,
        audit_context={'contractVersion': CONTRACT})


def _request_binding(company_id, kind, key, semantic_hash):
    rows = list(OrganizationOperatingAuditRecord.objects.filter(
        organization_id=company_id, action_code=EXECUTE,
        after_snapshot__importContext__contractVersion=CONTRACT,
        after_snapshot__state__requestBinding__contractVersion=CONTRACT,
        after_snapshot__state__requestBinding__kind=kind,
        after_snapshot__state__requestBinding__clientIdempotencyKey=key,
    ).select_related('actor').defer('actor__password').order_by('pk'))
    for row in rows:
        if row.actor.company_id != company_id:
            _fail('OPERATION_AUDIT_INCONSISTENT', '请求绑定审计办理人与当前公司范围不一致')
        if kind == 'generate':
            valid_target = row.target_type == 'EngineeringCalculationRecord' and EngineeringCalculationRecord.objects.filter(
                pk=row.target_id, company_id=company_id, scope='operation_requirement', trace__purpose=CONTRACT).exists()
        else:
            valid_target = row.target_type == 'ProductionPlan' and ProductionPlan.objects.filter(pk=row.target_id,
                planning_requirement__demand__sales_order_item__sales_order__company_id=company_id).exists()
        if not valid_target:
            _fail('OPERATION_AUDIT_INCONSISTENT', '请求绑定未引用本服务的真实同公司目标对象')
    if any(row.after_snapshot['state']['requestBinding'].get('semanticHash') != semantic_hash for row in rows):
        _fail('IDEMPOTENCY_PAYLOAD_CONFLICT', '同一办理幂等键已经绑定不同的正式来源或步骤')
    return bool(rows)


def _binding_fact(kind, key, semantic_hash):
    return {'contractVersion': CONTRACT, 'kind': kind, 'clientIdempotencyKey': key, 'semanticHash': semantic_hash}


def _initialize_history(user, obj, decision, chain, reason):
    audit = _state_audit(user, obj, {'status': ''}, _snapshot(obj), decision, chain, reason)
    record_projected_business_transition(object_type=type(obj).__name__, object_id=obj.pk,
        source_state='', target_state=obj.status, action_code=EXECUTE, operator=user, reason=reason,
        audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions=(('', obj.status),))


def _requirement_fact(req, *, read_cache=None):
    result = {'id': req.pk, 'operationRequirementId': req.pk, 'calculationId': req.calculation_id,
        'sourceCalculationId': req.source_calculation_id, 'sourceFactId': req.source_fact_id,
        'sourceDetailId': req.source_detail_id, 'operationId': req.operation_id,
        'workloadQuantity': str(req.workload_quantity), 'uomId': req.uom_id,
        'quantityBasis': req.quantity_basis, 'basisQuantity': str(req.basis_quantity),
        'basisUomId': req.basis_uom_id, 'sourceHash': req.source_hash, 'inputHash': req.input_hash,
        'generationKey': req.generation_key, 'ruleId': req.source_detail.rule_id,
        'ruleVersion': req.source_detail.rule_version, 'auditId': req.audit_record_id, 'factSource': 'server'}
    if req.manufacturing_mode_id:
        result.update(manufacturingModeId=req.manufacturing_mode_id,
            workCenterId=req.work_center_id, standardCapacityId=req.standard_capacity_id,
            requirementQuantity=str(req.workload_quantity), requirementUOMId=req.uom_id,
            sourceSnapshot=req.calculation.trace.get('sourceSnapshot'),
            inputSnapshot=req.source_detail.input_snapshot)
        routing = req.calculation.trace.get('sourceSnapshot', {}).get('manufacturing', {}).get('routingContext')
        if routing is not None:
            result.update(sourceEngineeringCalculationId=routing['sourceEngineeringCalculationId'],
                routingId=routing['routingId'], routingVersionId=routing['routingVersionId'],
                routingStepId=routing['routingStepId'])
    if reference_type(req) == REFERENCE_TYPE:
        result.update({TYPE_KEY: REFERENCE_TYPE, CONTEXT_KEY: req.trace[CONTEXT_KEY]})
    from .operation_requirement_correction_service import requirement_lifecycle
    lifecycle = requirement_lifecycle(req, req.calculation.company_id, read_cache=read_cache)
    if lifecycle is not None:
        result['lifecycle'] = lifecycle
    return result


def _check_audit(audit, *, company_id, actor_id, target_type, target_id):
    if (audit is None or audit.organization_id != company_id or audit.actor_id != actor_id
        or audit.target_type != target_type or audit.target_id != target_id or audit.action_code != EXECUTE):
        _fail('OPERATION_AUDIT_INCONSISTENT', '正式审计与对象、动作、公司或实际办理人不一致')
    if not isinstance(audit.after_snapshot, dict) or not isinstance(audit.after_snapshot.get('state'), dict):
        _fail('OPERATION_AUDIT_INCONSISTENT', '正式审计缺少持久化事实快照')
    return audit.after_snapshot['state']


def _same_concrete_values(left, right):
    """Type-sensitive full-value comparison, including every nested JSON value.

    Python's ordinary equality conflates true/1 and 1/1.0. They have different
    canonical hashes, so a pure-hash shortcut must not conflate them either.
    Dict order changes conservatively miss and return to the canonical hash.
    """
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return len(left) == len(right) and all(
            _same_concrete_values(lk, rk) and _same_concrete_values(lv, rv)
            for (lk, lv), (rk, rv) in zip(left.items(), right.items()))
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _same_concrete_values(lv, rv) for lv, rv in zip(left, right))
    return left == right


def _proof_record_hash(row, *, read_cache=None):
    """Concrete persisted identity only; no computed capacity/catalogue fields."""
    if row is None:
        return None
    values = {}
    for field in row._meta.concrete_fields:
        if isinstance(row, Process) and field.name == 'workload_source_selection':
            # Selection has its own current audit/native generation gate;
            # adding it must not reinterpret prior frozen Process hashes.
            continue
        value = getattr(row, field.attname)
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        values[field.attname] = value
    cache = _requirement_read_cache(read_cache, getattr(read_cache, 'company_id', None))
    key = None
    if cache is not None and values.get('company_id', cache.company_id) == cache.company_id:
        try:
            # Full typed bytes memoize only this pure hash. Reference tags can
            # conservatively miss for equal values with different aliasing;
            # they cannot turn changed concrete values into a cached hash.
            raw = marshal.dumps(values, 4)
        except (TypeError, ValueError):
            pass
        else:
            key = ('concrete_record_hash', cache.company_id, cache.user_id, _today(),
                row._meta.label_lower, raw)
            if key in cache:
                return cache[key]
    result = _digest(values)
    if key is not None and cache.is_current(cache.company_id):
        cache[key] = result
    return result


def _copy_read_proof(value):
    """Separate mutable proof JSON without duplicating cached ORM graphs.

    Models follow the existing request-local _read_once read-only contract.
    Their concrete identities are rechecked before a successful proof is reused.
    """
    if isinstance(value, Model):
        return value
    if isinstance(value, dict):
        return {key: _copy_read_proof(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_read_proof(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_read_proof(item) for item in value)
    return deepcopy(value)


def _requirement_context_model_hash(context, *, read_cache=None):
    rows = {key: value for key, value in context.items() if isinstance(value, Model)}
    origin, fact = context['origin'], context['fact']
    rows.update(sourceRecord=origin.source_record, sourceItem=origin.sales_order_item,
        sourceOrder=origin.sales_order_item.sales_order, sourceInstance=origin.engineering_instance,
        sourceDetail=fact.source_detail, sourceProducer=fact.source_detail.rule)
    predecessor = context.get('supersedes')
    if predecessor is not None:
        rows.update(predecessorCalculation=predecessor.calculation,
            predecessorDetail=predecessor.source_detail, predecessorRule=predecessor.source_detail.rule,
            predecessorAudit=predecessor.audit_record)
    return _digest({name: _proof_record_hash(row, read_cache=read_cache) for name, row in rows.items()})


def _validate_requirement(req, company_id, *, read_cache=None, user=None):
    cache = _requirement_read_cache(read_cache, company_id)
    if cache is not None and user is not None and user.pk != cache.user_id:
        cache = None
    key = None
    if cache is not None:
        # The complete current row/snapshot identities distinguish changed
        # in-memory instances at the same PK. The original atomic DB snapshot
        # and all-proof write epoch bind their source/correction dependencies.
        key = ('validated_requirement', company_id, cache.user_id, _today(),
            *(_proof_record_hash(row, read_cache=cache) for row in (req, req.calculation,
                req.source_detail, req.source_detail.rule, req.audit_record)))
        if key in cache:
            saved = cache[key]
            if saved['modelHash'] == _requirement_context_model_hash(saved['context'], read_cache=cache):
                return _copy_read_proof(saved['context'])
            # A caller must not turn an altered cached ORM instance into an
            # approval. Discard dependent proofs and reload the native chain.
            cache.invalidate_proofs()
    context = _validate_requirement_uncached(req, company_id, read_cache=read_cache, user=user)
    if cache is not None and cache.is_current(company_id):
        cache[key] = {'context': _copy_read_proof(context),
            'modelHash': _requirement_context_model_hash(context, read_cache=cache)}
    return context


@read_span('requirementValidation')
def _validate_requirement_uncached(req, company_id, *, read_cache=None, user=None):
    if req.quantity_basis not in KNOWN_BASES or not req.source_calculation_id or not req.source_fact_id:
        _fail('QUANTITY_BASIS_MISSING', '工序需求没有可确认的正式数量口径与来源')
    supersedes_id = None
    if req.calculation.supersedes_id:
        predecessor_ids = _read_once(_requirement_read_cache(read_cache, company_id),
            ('predecessor_requirements', company_id, req.calculation.supersedes_id), lambda:
            list(EngineeringOperationRequirement.objects.filter(
                calculation_id=req.calculation.supersedes_id,
            ).values_list('pk', flat=True)))
        if len(predecessor_ids) != 1:
            _fail('OPERATION_CORRECTION_SOURCE_MISMATCH', '替代计算必须唯一对应原正式工序需求')
        supersedes_id = predecessor_ids[0]
    preparation = None
    generation_context = None
    trace = req.trace if isinstance(req.trace, dict) else {}
    if TYPE_KEY in trace or CONTEXT_KEY in trace:
        if reference_record_errors(req):
            _fail('OPERATION_FACT_CHANGED', '不可定量工序需求的正式类型、制造引用或准备快照无效')
        preparation = trace[CONTEXT_KEY]
        generation_context = {key: preparation['exactScope'][key]
                              for key in ('productionPlanId', 'routingStepId')}
    context = _generation_context(company_id, req.source_calculation_id, req.source_fact_id,
        req.source_detail.rule_id, supersedes_requirement_id=supersedes_id, read_cache=read_cache,
        user=user, generation_context=generation_context, expected_preparation_context=preparation)
    if (context['source_snapshot'].get('manufacturing', {}).get('capacityMode') == REFERENCE_TYPE
            and reference_type(req) != REFERENCE_TYPE):
        _fail('OPERATION_FACT_CHANGED', '不可定量规则不得伪装为旧制造引用合同')
    manufacturing = context['source_snapshot'].get('manufacturing')
    if manufacturing and (req.manufacturing_mode_id != manufacturing['modeId']
        or req.work_center_id != manufacturing['workCenterId']
        or req.standard_capacity_id != manufacturing['standardCapacityId']):
        _fail('OPERATION_FACT_CHANGED', '制造模式、工作中心或标准产能引用与固定来源快照不一致')
    if not manufacturing and any((req.manufacturing_mode_id, req.work_center_id, req.standard_capacity_id)):
        _fail('OPERATION_FACT_CHANGED', '旧规则不得附加未声明的制造引用')
    calc, detail = req.calculation, req.source_detail
    if (calc.pk == context['origin'].pk or calc.status != 'completed' or calc.scope != 'operation_requirement'
        or any(getattr(calc, key) != getattr(context['origin'], key)
               for key in ('company_id', 'source_record_id', 'sales_order_item_id', 'engineering_instance_id'))
        or detail.calculation_id != calc.pk or detail.status != 'succeeded'
        or detail.rule_version != context['rule'].version or detail.rule_code != context['rule'].rule_code
        or detail.uom_id != req.uom_id or req.uom_id != context['uom'].pk
        or req.operation_id != context['operation'].pk):
        _fail('SOURCE_FACT_MISMATCH', '新工序需求运行、成功明细与固定来源/规则版本/工序单位血缘不一致')
    result_snapshot = calc.trace.get('resultSnapshot') if isinstance(calc.trace, dict) else None
    expected_output = context['spec']['outputs'][0]
    if (req.source_hash != context['source_hash'] or req.input_hash != context['input_hash']
        or req.generation_key != context['generation_key'] or req.quantity_basis != context['basis']
        or req.basis_quantity != context['basis_qty'] or req.basis_uom_id != context['basis_uom'].pk
        or detail.expression_snapshot != context['spec']['expression'] or detail.input_snapshot != context['inputs']
        or not isinstance(detail.output_value, dict)
        or _number(detail.output_value.get('decimal')) != req.workload_quantity
        or not isinstance(calc.trace, dict) or calc.trace.get('sourceSnapshot') != context['source_snapshot']
        or calc.trace.get('canonicalInputSnapshot') != context['inputs']
        or calc.trace.get('ruleSpecificationHash') != specification_hash(context['spec'])
        or calc.trace.get('ruleSpecification') != context['spec']
        or calc.input_hash != context['input_hash'] or calc.rule_graph_hash != specification_hash(context['spec'])
        or not isinstance(result_snapshot, dict) or result_snapshot.get('resultDomain') != 'OPERATION_REQUIREMENT'
        or result_snapshot.get('canonicalName') != detail.output_name
        or result_snapshot.get('canonicalName') != expected_output['canonicalName']
        or result_snapshot.get('specificationHash') != specification_hash(context['spec'])
        or result_snapshot.get('unit') != expected_output.get('unit')
        or result_snapshot.get('unitDimension') != expected_output.get('unitDimension')
        or result_snapshot.get('valueType') != expected_output.get('valueType')
        or result_snapshot.get('rulePackage') != context['spec']['rulePackage']
        or _number(result_snapshot.get('value')) != req.workload_quantity
        or calc.result_hash != _digest({'detailId': detail.pk, 'output': result_snapshot})):
        _fail('OPERATION_FACT_CHANGED', '来源、版本化输入输出或正式数量口径已变化，禁止读取旧分配')
    evidence = {'generationKey': req.generation_key, 'sourceHash': req.source_hash,
        'inputHash': req.input_hash, 'detailId': detail.pk, 'operationId': req.operation_id,
        'workloadQuantity': _quantity_text(req.workload_quantity), 'uomId': req.uom_id,
        'quantityBasis': req.quantity_basis, 'basisQuantity': _quantity_text(req.basis_quantity), 'basisUomId': req.basis_uom_id}
    state = _check_audit(req.audit_record, company_id=company_id, actor_id=req.created_by_id,
        target_type='EngineeringCalculationRecord', target_id=calc.pk)
    if state.get('operationRequirementEvidence') != evidence:
        _fail('OPERATION_AUDIT_INCONSISTENT', '生成审计与当前工序需求事实不一致')
    if (state.get('input_hash') != calc.input_hash or state.get('rule_graph_hash') != calc.rule_graph_hash
        or state.get('result_hash') != calc.result_hash or state.get('trace') != calc.trace):
        _fail('OPERATION_AUDIT_INCONSISTENT', '新运行哈希或版本化追踪与完成审计不一致')
    for obj, target in ((calc, 'completed'), (detail, 'succeeded')):
        transitions = _read_once(_requirement_read_cache(read_cache, company_id),
            ('requirement_transitions', company_id, type(obj).__name__, obj.pk), lambda:
            list(BusinessStateTransition.objects.filter(object_type=type(obj).__name__,
                object_id=obj.pk).order_by('version')))
        expected_pairs = [('', 'running'), ('running', target)]
        if [(row.source_state, row.target_state) for row in transitions] != expected_pairs:
            _fail('OPERATION_STATE_HISTORY_MISSING', '新运行或成功明细缺少统一状态转换事实')
        if obj is calc and transitions[-1].audit_reference != f'OrganizationOperatingAuditRecord:{req.audit_record_id}':
            _fail('OPERATION_AUDIT_INCONSISTENT', '新运行完成状态未引用同一真实生成审计')
        previous = ''
        for index, transition in enumerate(transitions, 1):
            if (transition.source_state != previous or transition.version != index
                or transition.action_code != EXECUTE or transition.operator_id != req.created_by_id):
                _fail('OPERATION_STATE_HISTORY_MISSING', '新运行或明细的统一转换链不完整')
            prefix = 'OrganizationOperatingAuditRecord:'
            reference = transition.audit_reference
            if not reference.startswith(prefix) or not reference[len(prefix):].isdigit():
                _fail('OPERATION_AUDIT_INCONSISTENT', '统一状态转换未引用真实审计')
            audit_id = int(reference[len(prefix):])
            audit = _read_once(_requirement_read_cache(read_cache, company_id),
                ('requirement_transition_audit', company_id, audit_id), lambda:
                OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).first())
            audit_state = _check_audit(audit, company_id=company_id, actor_id=req.created_by_id,
                target_type=type(obj).__name__, target_id=obj.pk)
            if audit_state.get('status') != transition.target_state:
                _fail('OPERATION_AUDIT_INCONSISTENT', '状态转换与权威审计的目标状态不一致')
            previous = transition.target_state
    return context


def _admission_check(checks, name, label, *, passed=True, code=None):
    if checks is not None:
        checks[name] = {'status': 'passed' if passed else 'blocked', 'passed': passed,
            'statusLabel': label, **({'reasonCode': code} if code else {})}


def _extension_object_coverage(company_id, base, origin, fact, output, *, read_cache=None, baseline=None):
    """Prove saved input contributions belong to the fixed baseline and line."""
    from .models import OrderEngineeringBaselineItem
    from .formal_engineering_continuation_service import _baseline_reference
    from .engineering_calculation_service import EngineeringCalculationError
    baseline = baseline if baseline is not None else output.order_engineering_baseline
    if (not baseline or baseline.company_id != company_id or production_status(baseline) != 'confirmed'
        or baseline.sales_order_id != base.sales_order_item.sales_order_id):
        _fail('ALLOCATION_EXTENSION_BASELINE_UNPROVEN', '扩展来源必须对应计划固定的同公司已确认工程基线')
    cache = _requirement_read_cache(read_cache, company_id)

    def baseline_objects():
        items = list(OrderEngineeringBaselineItem.objects.filter(baseline=baseline,
            design_item__sales_order_item_id=base.sales_order_item_id).select_related('design_item')
            .order_by('source_attribute_id', 'design_item_id', 'pk'))
        try:
            reference = _baseline_reference(baseline, items, read_cache=cache)
        except EngineeringCalculationError as exc:
            _fail('ALLOCATION_EXTENSION_BASELINE_UNPROVEN', exc.message, baselineCode=exc.code)
        if base.trace.get('baselineReference') != reference:
            _fail('ALLOCATION_EXTENSION_BASELINE_UNPROVEN', '主核算保存的完整基线及所选对象Hash与计划固定基线不一致')
        return items, reference

    if cache is None:
        items, reference = baseline_objects()
    else:
        # The complete header and selected-order-line set are proved once in
        # this immutable atomic read. Fact-specific membership is checked below.
        items, reference = _read_once(cache, ('coverage_baseline_objects', company_id,
            base.pk, base.source_record_id, base.sales_order_item_id, base.engineering_instance_id,
            base.input_hash, base.result_hash, base.rule_graph_hash,
            _digest(base.trace.get('baselineReference')), _digest(_snapshot(output)),
            _digest(_snapshot(baseline))), baseline_objects)
    by_id = {row.pk: row for row in items}
    pairs, leaves, visited = set(), set(), set()

    def identity(trace, name):
        group = trace.get('group') if isinstance(trace.get('group'), dict) else {}
        values = [value for value in (trace.get(name), group.get(name)) if value is not None]
        if any(type(value) is not int or value <= 0 for value in values) or len(set(values)) > 1:
            _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '正式来源对象身份缺失、冲突或不是有效整数FK')
        return values[0] if values else None

    def visit(row, stack):
        if row.pk in stack or len(stack) > 128:
            _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '正式事实输入关系存在循环或无法证明的深度')
        if row.pk in visited:
            return
        visited.add(row.pk)
        # Keep an explicitly loaded instance (including any in-memory change)
        # visible to the original checks. Otherwise share only this raw FK read
        # within the same guarded request instead of decoding its large trace
        # again for every input fact. No coverage approval is memoized here.
        calculation = row._state.fields_cache.get('calculation')
        if calculation is None:
            calculation = _read_once(cache, ('coverage_calculation_row', company_id,
                row.calculation_id), lambda: row.calculation)
        if (calculation.pk not in {base.pk, origin.pk} or calculation.company_id != company_id
            or calculation.source_record_id != base.source_record_id
            or calculation.sales_order_item_id != base.sales_order_item_id
            or calculation.engineering_instance_id != base.engineering_instance_id
            or row.status != 'active' or row.source_type != 'ENGINEERING_DERIVED'):
            _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '输入贡献越过当前主核算/合法扩展或固定订单行范围')
        trace = row.trace if isinstance(row.trace, dict) else {}
        baseline_id = identity(trace, 'baselineId')
        if baseline_id is not None and baseline_id != baseline.pk:
            _fail('ALLOCATION_EXTENSION_BASELINE_UNPROVEN', '来源事实声明的工程基线与计划固定基线不一致')
        design_id, item_id = identity(trace, 'designItemId'), identity(trace, 'baselineItemId')
        if (design_id is None) != (item_id is None):
            _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '正式对象与基线项必须成对存在，不能根据名称补齐')
        if item_id is not None:
            item = by_id.get(item_id)
            if (not item or item.design_item_id != design_id or not item.confirmable
                or item.source_record_id != base.source_record_id
                or item.design_item.company_id != company_id
                or _digest(item.content_snapshot) != item.content_hash
                or (trace.get('baselineContentHash') is not None
                    and trace['baselineContentHash'] != item.content_hash)):
                _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '对象贡献、固定基线内容Hash与订单行范围不一致')
            pairs.add((item_id, design_id))
        if cache is None:
            links = list(row.inputs.select_related('source_fact__calculation').order_by('sequence'))
        else:
            links = _read_once(cache, ('coverage_fact_inputs', company_id, row.pk,
                _digest(_snapshot(row))), lambda:
                list(row.inputs.select_related('source_fact').order_by('sequence')))
        if not links:
            if calculation.pk != base.pk or item_id is None:
                _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '叶子贡献缺少原主核算的正式对象/基线身份，不能猜测覆盖范围')
            leaves.add((item_id, design_id))
        for link in links:
            visit(link.source_fact, stack | {row.pk})

    visit(fact, set())
    if not leaves:
        _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '未能证明扩展来源的原始对象贡献')
    primary_trace = fact.trace if isinstance(fact.trace, dict) else {}
    primary = (identity(primary_trace, 'baselineItemId'), identity(primary_trace, 'designItemId'))
    if primary[0] is not None and leaves != {primary}:
        _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '单对象扩展事实的输入贡献包含其他对象，不得跨范围承接')
    return {'baselineId': baseline.pk, 'baselineSnapshotHash': baseline.snapshot_hash,
        'selectedItemHash': reference['selectedItemHash'],
        'designItemIds': sorted({pair[1] for pair in leaves}),
        'baselineItemIds': sorted({pair[0] for pair in leaves}), 'inputFactIds': sorted(visited)}


def _plan_source_consistency(company_id, plan, req, *, native_context=None,
                             routing_step=None, read_cache=None, checks=None):
    """Single authority for direct or formally proved extension plan sources."""
    from .operation_requirement_correction_service import require_effective_requirement
    require_effective_requirement(req, company_id, read_cache=read_cache)
    demand = plan.planning_requirement.demand
    item, output = demand.sales_order_item, effective_output(plan)
    selected_base, selected_baseline = effective_calculation(plan), effective_baseline(plan)
    selected_source = source_selection(plan)
    if reference_type(req) == REFERENCE_TYPE:
        scope = req.trace[CONTEXT_KEY]['exactScope']
        if (scope['productionPlanId'] != plan.pk or not output
                or scope['manufacturingOutputId'] != output.pk
                or scope['mainCalculationId'] != selected_base.pk
                or scope['baselineId'] != selected_baseline.pk
                or scope['routingVersionId'] != output.routing_version_id
                or (routing_step is not None and scope['routingStepId'] != routing_step.pk)):
            _fail('NON_QUANTIFIED_CONTEXT_MISMATCH', '精确准备裁决需求不得跨计划、制造输出或步骤复用')
    if (not item or not output or item.sales_order.company_id != company_id
        or item.pk != req.calculation.sales_order_item_id
        or output.order_engineering_instance_id != req.calculation.engineering_instance_id
        or output.order_engineering_instance.company_id != company_id
        or output.order_engineering_instance.sales_order_item_id != item.pk):
        _fail('ALLOCATION_SOURCE_MISMATCH', '计划、需求、制造输出与工序需求必须属于同公司、同订单行和工程实例')
    if selected_base.pk == req.source_calculation_id:
        direct = req.source_calculation
        if (direct.scope != 'order_engineering' or direct.status != 'completed'
            or direct.company_id != company_id
            or direct.sales_order_item_id != item.pk
            or direct.engineering_instance_id != output.order_engineering_instance_id
            or direct.source_record_id != req.calculation.source_record_id):
            _fail('ALLOCATION_SOURCE_MISMATCH', '直接来源必须是计划固定的同公司、同订单行已完成正式主核算')
        _admission_check(checks, 'sourceConsistency', '原直接主核算来源身份一致')
        if selected_source:
            # A newly selected direct main is not a historical direct-source
            # exemption. It must prove its selected objects and this exact
            # step's current applicability through the existing resolver.
            if routing_step is None:
                _fail('ALLOCATION_STEP_MISMATCH', '新来源直接需求必须绑定已证明的精确计划步骤')
            from .routing_step_applicability_service import RoutingStepApplicabilityResolver, REQUIRED
            direct_coverage = _extension_object_coverage(company_id, selected_base,
                direct, req.source_fact, output, read_cache=read_cache, baseline=selected_baseline)
            direct_applicability = RoutingStepApplicabilityResolver.resolve(
                routing_step, engineering_calculation=selected_base,
                engineering_document_version=output.engineering_document_version,
                order_engineering_instance=selected_base.engineering_instance,
                order_engineering_baseline=selected_baseline, bom_version=output.bom_version,
                production_plan=plan, manufacturing_output=output)
            if direct_applicability.get('result') != REQUIRED:
                _fail('ALLOCATION_STEP_NOT_REQUIRED', '新正式来源尚未证明本计划步骤及对象必须执行',
                    applicability=direct_applicability)
            partition = direct_applicability.get('objectApplicability')
            if partition and not set(direct_coverage['baselineItemIds']) <= set(partition['requiredBaselineItemIds']):
                _fail('ALLOCATION_STEP_NOT_REQUIRED', '直接来源对象未精确落入新基线下的正式必经范围')
            _admission_check(checks, 'objectCoverage', '新直接来源对象已按当前正式基线和步骤证明')
        else:
            _admission_check(checks, 'objectCoverage', '沿用原直接来源的正式订单行范围合同')
        return {'sourceType': 'DIRECT', 'sourceEngineeringCalculationId': req.source_calculation_id,
            'sourceFactCalculationId': req.source_calculation_id, 'sourceFactId': req.source_fact_id,
            'manufacturingOutputId': output.pk,
            **({'sourceSelection': deepcopy(selected_source)} if selected_source else {})}
    context = native_context or _validate_requirement(req, company_id, read_cache=read_cache)
    origin, fact = context['origin'], context['fact']
    if (origin.pk != req.source_calculation_id or fact.pk != req.source_fact_id
        or origin.scope != 'fact_extension' or not origin.origin_calculation_id
        or context['source_hash'] != req.source_hash or context['input_hash'] != req.input_hash
        or context['generation_key'] != req.generation_key):
        _fail('ALLOCATION_SOURCE_MISMATCH', '非直接来源必须具有本需求原生校验通过的合法扩展及精确输入Hash证明')
    base = origin.origin_calculation
    proof = context['source_snapshot'].get('factExtension')
    if (not isinstance(proof, dict) or proof.get('contractVersion') != 'PCE-ENGINEERING-FACT-EXTENSION-V1'
        or proof.get('baseEngineeringCalculationId') != base.pk
        or base.pk != selected_base.pk or base.scope != 'order_engineering'
        or base.status != 'completed' or origin.status != 'completed'
        or any(getattr(base, key) != getattr(origin, key) for key in
            ('company_id', 'source_record_id', 'sales_order_item_id', 'engineering_instance_id'))
        or base.company_id != company_id or base.sales_order_item_id != item.pk
        or base.engineering_instance_id != output.order_engineering_instance_id
        or proof.get('originInputHash') != base.input_hash or proof.get('originResultHash') != base.result_hash
        or proof.get('inputHash') != origin.input_hash or proof.get('resultHash') != origin.result_hash
        or proof.get('sourceRecordId') != base.source_record_id
        or proof.get('sourceRecordVersion') != base.source_record.source_version):
        _fail('ALLOCATION_SOURCE_MISMATCH', '合法扩展必须精确证明计划固定主核算、公司、订单行、实例及当前来源Hash')
    _admission_check(checks, 'sourceConsistency', '计划固定主核算与合法扩展的正式来源及Hash关系一致')
    if not selected_baseline:
        _fail('ALLOCATION_EXTENSION_BASELINE_UNPROVEN', '计划制造输出缺少固定工程基线，扩展对象范围未知')
    coverage = _read_once(read_cache, ('plan_extension_objects', company_id, origin.pk,
        origin.input_hash, origin.result_hash, base.pk, base.input_hash, base.result_hash,
        output.pk, selected_baseline.pk, selected_baseline.snapshot_hash,
        fact.pk, _digest(fact.trace)),
        lambda: _extension_object_coverage(company_id, base, origin, fact, output, read_cache=read_cache,
            **({'baseline': selected_baseline} if selected_source else {})))
    _admission_check(checks, 'objectCoverage', '正式输入对象均属于计划固定基线及同一订单行范围')
    from .manufacturing_structure_service import ManufacturingStructureService, ManufacturingStructureError
    from .routing_step_applicability_service import RoutingStepApplicabilityResolver, REQUIRED
    # Routing remains the formally released plan anchor. The selected source
    # has a separate audited main/baseline; never construct a fictitious output
    # by combining that new main with the anchor's old BOM.
    route_base = output.engineering_calculation if selected_source else base
    route_baseline = output.order_engineering_baseline if selected_source else selected_baseline
    exact_context = {'organizationId': company_id, 'salesOrderItemId': item.pk,
        'orderEngineeringInstanceId': route_base.engineering_instance_id,
        'orderEngineeringBaselineId': route_baseline.pk, 'engineeringCalculationId': route_base.pk,
        'bomVersionId': output.bom_version_id}
    routing = context['source_snapshot'].get('manufacturing', {}).get('routingContext')
    if routing is not None and (routing.get('sourceEngineeringCalculationId') != base.pk
        or routing.get('sourceFactCalculationId') != origin.pk or routing.get('sourceFactId') != fact.pk
        or routing.get('manufacturingOutputId') != output.pk
        or routing.get('routingVersionId') != output.routing_version_id
        or routing.get('context') != exact_context):
        _fail('ALLOCATION_STEP_MISMATCH', '需求原生路线来源上下文与计划固定工程组合不一致')
    # A native context returned by _validate_requirement has already run the
    # authoritative route resolver with current hashes. Legacy extension rules
    # lacking that opt-in still need the same resolver here, never an ID guess.
    if routing is None:
        def prove_route():
            try:
                output.clean()
                resolved = ManufacturingStructureService.resolve_effective_routing(base.engineering_instance,
                    on_date=_today(), exact_version_context=exact_context)
            except ValidationError as exc:
                _fail('ALLOCATION_SOURCE_MISMATCH', '计划制造输出的固定工程组合校验失败', errors=exc.messages)
            except ManufacturingStructureError as exc:
                _fail('ALLOCATION_STEP_MISMATCH', exc.message, resolverCode=exc.code)
            if resolved['routing_version'].pk != output.routing_version_id:
                _fail('ALLOCATION_STEP_MISMATCH', '合法扩展的正式适用版本不等于计划固定版本')
            return True

        cache = _requirement_read_cache(read_cache, company_id)
        if cache is None:
            prove_route()
        else:
            # Share the complete fixed route proof, never a requirement's
            # source/object/operation/step decision, inside this read only.
            fixed_route_key = ('plan_source_route', company_id, _today(), _digest(exact_context),
                _proof_record_hash(base, read_cache=cache), _proof_record_hash(base.engineering_instance, read_cache=cache),
                _proof_record_hash(output, read_cache=cache), _proof_record_hash(output.order_engineering_baseline, read_cache=cache),
                _proof_record_hash(output.routing_version, read_cache=cache), _proof_record_hash(output.routing_version.routing, read_cache=cache),
                _proof_record_hash(output.engineering_document_version, read_cache=cache) if output.engineering_document_version_id else None,
                _proof_record_hash(output.bom_version, read_cache=cache) if output.bom_version_id else None,
                coverage['selectedItemHash'])
            _read_once(cache, fixed_route_key, prove_route)
    applicability = None
    if routing_step is not None:
        if (routing_step.routing_version_id != output.routing_version_id
            or routing_step.operation_id != req.operation_id
            or (routing is not None and routing.get('routingStepId') != routing_step.pk)):
            _fail('ALLOCATION_STEP_MISMATCH', '需求必须承接同一正式版本及精确工序出现位置')
        if routing is not None:
            applicability = routing.get('stepApplicability')
        else:
            def prove_applicability():
                result = RoutingStepApplicabilityResolver.resolve(
                    routing_step, engineering_calculation=base, engineering_document_version=output.engineering_document_version,
                    order_engineering_instance=base.engineering_instance,
                    order_engineering_baseline=selected_baseline, bom_version=output.bom_version,
                    read_cache=cache,
                    **({'production_plan': plan, 'manufacturing_output': output} if selected_source else {}))
                if result.get('result') != REQUIRED:
                    _fail('ALLOCATION_STEP_NOT_REQUIRED', '正式来源尚未证明该计划步骤本次必须执行', applicability=result)
                return result

            if cache is None:
                applicability = prove_applicability()
            else:
                applicability = deepcopy(_read_once(cache, ('plan_source_step', fixed_route_key,
                    _proof_record_hash(routing_step, read_cache=cache)), prove_applicability))
        if applicability.get('result') != REQUIRED:
            _fail('ALLOCATION_STEP_NOT_REQUIRED', '正式来源尚未证明该计划步骤本次必须执行', applicability=applicability)
    return {'contractVersion': 'PCE-PLAN-LEGAL-EXTENSION-SOURCE-V1', 'sourceType': 'LEGAL_EXTENSION',
        'sourceEngineeringCalculationId': base.pk, 'sourceFactCalculationId': origin.pk,
        'sourceFactId': fact.pk, 'manufacturingOutputId': output.pk,
        **coverage, 'extensionProof': proof, 'routingVersionId': output.routing_version_id,
        'routingStepId': routing_step.pk if routing_step is not None else None,
        'stepApplicability': applicability, 'sourceHash': req.source_hash,
        'operationRequirementInputHash': req.input_hash,
        **({'sourceSelection': deepcopy(selected_source)} if selected_source else {})}


def _plan_context(company_id, plan_id, req, step_id, *, native_context=None,
                  read_cache=None, source_proof_out=None, checks=None,
                  historical=False, frozen_binding=None):
    from .operation_requirement_correction_service import require_effective_requirement
    require_effective_requirement(req, company_id, read_cache=read_cache)
    cache = _requirement_read_cache(read_cache, company_id)
    plan = _read_once(cache, ('allocation_plan', company_id, plan_id), lambda:
        ProductionPlan.objects.select_related(
            'material', 'planning_requirement__demand__sales_order_item__sales_order',
            'planning_requirement__demand__sales_order_item__uom',
            'planning_requirement__demand__manufacturing_output__routing_version__routing',
            'planning_requirement__demand__manufacturing_output__order_engineering_baseline',
            'planning_requirement__demand__manufacturing_output__order_engineering_instance',
        ).filter(pk=plan_id, planning_requirement__demand__sales_order_item__sales_order__company_id=company_id).first())
    if plan is None:
        _fail('PLAN_NOT_FOUND', '生产计划不存在或不属于当前公司')
    try:
        version_context = resolve_step_context(plan, step_id, historical=historical,
            frozen_proof=frozen_binding, user=getattr(cache, 'user', None), read_cache=cache)
    except PlanStepContextError as error:
        _fail(error.code, error.message, **error.details)
    plan = bind_plan_context(plan, version_context)
    step_id = version_context['step'].pk
    requirement = plan.planning_requirement
    demand = requirement.demand
    item, output = demand.sales_order_item, effective_output(plan)
    if plan.status != 'confirmed':
        _fail('PLAN_STATE_NOT_CONFIRMED', '生产计划必须保持已确认状态；本轮只读准入不改变计划状态')
    materials = (plan.material, requirement.material, demand.material, item.material)
    if (len({material.pk for material in materials}) != 1
        or any(material.company_id != company_id for material in materials)
        or demand.department.company_id != company_id):
        _fail('ALLOCATION_SOURCE_MISMATCH', '计划、需求与订单物料或部门的正式归属不一致')
    if plan.planned_qty != requirement.net_required_qty:
        _fail('PLAN_NET_QUANTITY_MISMATCH', '计划数量与正式净需求数量不一致，数量映射和预算尚未通过')
    if (output is None or output.release_status != 'released_to_manufacturing'
        or item.pk != req.calculation.sales_order_item_id
        or output.order_engineering_instance_id != req.calculation.engineering_instance_id
        or not output.routing_version_id or output.routing_version.status != 'released'):
        _fail('ALLOCATION_SOURCE_MISMATCH', '计划必须固定同一订单行、原工程核算、工程实例和已发布制造输出/路线')
    if (output.order_engineering_instance.company_id != company_id
        or output.order_engineering_instance.sales_order_item_id != item.pk):
        _fail('ALLOCATION_SOURCE_MISMATCH', '制造输出工程实例必须属于同公司、同一订单行')
    _admission_check(checks, 'planState', '计划仍为已确认，净需求、物料及已发布制造输出符合原合同')
    step = _read_once(cache, ('allocation_step', company_id, output.routing_version_id, step_id), lambda:
        RoutingStep.objects.select_related('operation').filter(pk=step_id,
            routing_version_id=output.routing_version_id).first())
    source_proof = _plan_source_consistency(company_id, plan, req, native_context=native_context,
        routing_step=step, read_cache=read_cache, checks=checks)
    if source_proof_out is not None:
        source_proof_out.update(source_proof)
    if not step or not step.is_active or step.operation_id != req.operation_id:
        _fail('ALLOCATION_STEP_MISMATCH', '步骤必须属于计划固定工艺版本并引用需求的同一正式工序')
    route = output.routing_version.routing
    product_type_id = req.source_detail.rule.specification['outputs'][0].get('productTypeId')
    if type(product_type_id) is not int or product_type_id <= 0:
        _fail('ALLOCATION_PRODUCT_TYPE_MISSING', '正式规则版本缺少产品类型FK映射')
    kind = _read_once(cache, ('allocation_product_type', company_id, product_type_id), lambda:
        CapacityProductType.objects.filter(pk=product_type_id, company_id=company_id).first())
    if (not _active(kind) or not route or route.company_id != company_id
        or kind.product_category_id != route.product_category_id
        or kind.manufacturing_process_type_id != route.manufacturing_process_type_id):
        _fail('ALLOCATION_PRODUCT_TYPE_MISSING', '规则产品类型与固定工艺路线的分类/工艺类型FK不一致')
    _admission_check(checks, 'stepResourceApplicability', '固定版本、工序出现位置及正式产品类型匹配；不代表APS可用')
    if item.uom_id != req.basis_uom_id:
        _fail('PLAN_QUANTITY_UOM_MISMATCH', '计划正式来源单位与工序基准单位不一致')
    quantity = _number(plan.planned_qty)
    if req.quantity_basis == 'SOURCE_SCOPE_TOTAL':
        if quantity != req.basis_quantity:
            _fail('SOURCE_SCOPE_PARTIAL_ALLOCATION_BLOCKED', '固定来源总作业量仅允许完整承接，部分分摊须有正式规则')
        workload = req.workload_quantity
    else:
        ratio = Fraction(req.workload_quantity) * Fraction(quantity) / Fraction(req.basis_quantity)
        scaled, remainder = divmod(ratio.numerator * 1_000_000, ratio.denominator)
        if remainder:
            _fail('ALLOCATION_PRECISION_UNCONFIRMED', '分配结果不能精确表达为六位小数，缺少明确获批的分配舍入口径')
        workload = Decimal(scaled).scaleb(-6)
    _number(workload, 'OPERATION_WORKLOAD_INVALID')
    _admission_check(checks, 'quantityMappingBudget', '计划原单位、来源数量预算及现有完整承接/精度合同已匹配')
    return plan, step, kind, quantity, workload


def _composition_proof(req, company_id, read_cache=None):
    from .operation_contribution_composition import (
        OperationContributionCompositionError, composition_for_requirement,
    )
    try:
        return composition_for_requirement(req, company_id, read_cache=read_cache)
    except OperationContributionCompositionError as exc:
        _fail(exc.code, exc.message, **exc.details)


def _allocation_snapshot(req, plan, step, product_type, quantity, workload, *, source_proof=None, read_cache=None):
    snapshot = {'contractVersion': CONTRACT, 'companyId': req.calculation.company_id,
        'productionPlanId': plan.pk, 'productionPlanNo': plan.plan_no, 'planQuantity': str(quantity),
        'planUpdatedAt': plan.updated_at.isoformat(), 'planStatus': plan.status,
        'operationRequirementId': req.pk, 'generationKey': req.generation_key,
        'sourceCalculationId': req.source_calculation_id, 'sourceFactId': req.source_fact_id,
        'sourceHash': req.source_hash, 'operationRequirementInputHash': req.input_hash,
        'routingVersionId': step.routing_version_id, 'routingStepId': step.pk, 'sequence': step.sequence,
        'operationId': req.operation_id, 'productTypeId': product_type.pk,
        'productTypeCode': product_type.code, 'productCategoryId': product_type.product_category_id,
        'manufacturingProcessTypeId': product_type.manufacturing_process_type_id,
        'quantityBasis': req.quantity_basis, 'basisQuantity': str(req.basis_quantity),
        'sourceQuantity': str(quantity), 'sourceUomId': req.basis_uom_id,
        'allocatedQuantity': str(workload), 'uomId': req.uom_id,
        'ruleId': req.source_detail.rule_id, 'ruleVersion': req.source_detail.rule_version}
    # Original direct-source serialization and existing immutable hashes stay
    # identical. Only newly admitted extension sources carry this extra proof.
    if source_proof and source_proof.get('sourceType') == 'LEGAL_EXTENSION':
        snapshot['planEngineeringSource'] = source_proof
    version_context = getattr(plan, '_native_step_version_context', None)
    if version_context and version_context.get('bindingProof'):
        snapshot['planStepVersionBinding'] = deepcopy(version_context['bindingProof'])
    cache = _requirement_read_cache(read_cache, req.calculation.company_id)
    if cache is not None:
        # The ordered raw set is not a successful proof. Preserve first()'s
        # exact FK predicates and ordering, including a genuinely empty set.
        existing = next((row for row in _read_allocation_rows(req.calculation.company_id,
            production_plan_id=plan.pk, routing_step_id=step.pk, read_cache=cache)
            if row.operation_requirement_id == req.pk), None)
    else:
        existing = ProductionPlanOperationRequirementAllocation.objects.filter(
            company_id=req.calculation.company_id, production_plan=plan,
            routing_step=step, operation_requirement=req).first()
    # A later declaration never retrofits an immutable historical snapshot.
    # Newly bound snapshots must keep proving the exact current declaration.
    if existing is None or 'allocationComposition' in existing.source_snapshot:
        composition = _composition_proof(req, req.calculation.company_id, read_cache)
        if composition is not None:
            snapshot['allocationComposition'] = composition
    return snapshot


def _allocation_object_coverage_proof(row, company_id, plan, step, kind, context,
                                      source_proof, *, read_cache=None):
    """Project current native object evidence without rewriting saved facts.

    This runs only after the original requirement, allocation snapshot and audit
    checks. A direct legacy snapshot intentionally has no extension envelope;
    its retained main-calculation leaves use the same formal resolver already
    used by contribution compatibility. Missing evidence stays unproved, while
    the original single-contribution quantity contract remains unchanged.
    """
    req = row.operation_requirement
    output = effective_output(plan)
    selected_base, selected_baseline = effective_calculation(plan), effective_baseline(plan)
    selected_source = source_selection(plan)
    declared = 'planEngineeringSource' in row.source_snapshot
    result = {'contractVersion': 'PCE-ALLOCATION-OBJECT-COVERAGE-READ-V1',
        'proofSource': 'CURRENT_READ_VALIDATED_SOURCE_CHAIN',
        'status': 'UNPROVEN', 'statusLabel': '当前保留来源链尚未证明对象覆盖',
        'snapshotStatusLabel': ('历史分配快照含覆盖字段，本次重新验证' if declared
            else '历史分配快照未保存覆盖字段，本次只读验证'),
        'scope': {'companyId': company_id, 'productionPlanId': plan.pk,
            'manufacturingOutputId': output.pk, 'mainCalculationId': selected_base.pk,
            'salesOrderItemId': plan.planning_requirement.demand.sales_order_item_id,
            'baselineId': selected_baseline.pk if selected_baseline else None,
            'routingVersionId': step.routing_version_id, 'routingStepId': step.pk,
            'operationId': req.operation_id, 'productTypeId': kind.pk},
        'allocationId': row.pk, 'operationRequirementId': req.pk,
        'sourceFactId': req.source_fact_id, 'sourceCalculationId': req.source_calculation_id,
        'sourceHash': req.source_hash, 'inputHash': row.input_hash,
        'operationRequirementInputHash': req.input_hash, 'generationKey': req.generation_key,
        'snapshotHasPlanEngineeringSource': declared, 'coverage': None}
    try:
        if declared:
            # An existing declaration must match the current native source
            # proof. Never reinterpret a malformed/conflicting declaration as
            # a legacy direct source merely because it has no object IDs.
            if (source_proof.get('sourceType') != 'LEGAL_EXTENSION'
                    or row.source_snapshot['planEngineeringSource'] != source_proof):
                _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '已保存对象声明与当前原生来源证明不一致')
            proof = source_proof
        else:
            origin, fact = context['origin'], context['fact']
            if (source_proof.get('sourceType') != 'DIRECT'
                    or origin.pk != selected_base.pk
                    or origin.pk != req.source_calculation_id or fact.pk != req.source_fact_id):
                _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '缺少可承接的正式直接来源对象链')
            proof = _extension_object_coverage(company_id, origin, origin, fact, output,
                read_cache=read_cache, **({'baseline': selected_baseline} if selected_source else {}))
        keys = ('baselineId', 'baselineSnapshotHash', 'selectedItemHash',
            'designItemIds', 'baselineItemIds', 'inputFactIds')
        coverage = {key: deepcopy(proof[key]) for key in keys}
        if (not selected_baseline or coverage['baselineId'] != selected_baseline.pk
                or coverage['baselineSnapshotHash'] != selected_baseline.snapshot_hash):
            _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '当前对象证明未匹配计划固定工程基线')
        for name in ('designItemIds', 'baselineItemIds', 'inputFactIds'):
            values = coverage[name]
            if (not isinstance(values, list) or not values
                    or any(type(value) is not int or value <= 0 for value in values)
                    or len(set(values)) != len(values)):
                _fail('ALLOCATION_OBJECT_COVERAGE_UNPROVEN', '当前对象证明缺少明确且不重复的正式身份')
        result.update(status='PROVEN', statusLabel='依据保留来源链，于本次读取验证的覆盖证明',
            coverage=coverage)
        if 'allocationComposition' in row.source_snapshot:
            result['allocationComposition'] = deepcopy(row.source_snapshot['allocationComposition'])
    except (OperationRequirementError, KeyError) as error:
        result.update(reasonCode=getattr(error, 'code', 'ALLOCATION_OBJECT_COVERAGE_UNPROVEN'),
            statusLabel=getattr(error, 'message', '当前保留来源链缺少完整对象覆盖字段'))
    return result


def _allocation_budget_scope(req, company_id, *, plan=None, validated=None):
    """Project a source identity only after the native plan/row proof passed."""
    if plan is not None:
        demand = plan.planning_requirement.demand
        output, main, baseline = effective_output(plan), effective_calculation(plan), effective_baseline(plan)
        identity = (company_id, demand.sales_order_item_id, output.pk if output else None,
            main.pk if main else None, baseline.pk if baseline else None)
    else:
        scope = (validated or {}).get('objectCoverageProof', {}).get('scope', {})
        identity = tuple(scope.get(key) for key in ('companyId', 'salesOrderItemId',
            'manufacturingOutputId', 'mainCalculationId', 'baselineId'))
    if (any(type(value) is not int or value <= 0 for value in identity)
            or identity[:2] != (company_id, req.source_calculation.sales_order_item_id)):
        _fail('ALLOCATION_SOURCE_MISMATCH', '分配数量预算缺少已验证的同公司订单行及准确制造来源身份')
    return identity


@read_span('allocationValidation')
def _validate_allocation(row, company_id, *, verify_budget=True, read_cache=None, validation_cache=None):
    req = row.operation_requirement
    # This cache is created by a single public read/atomic group call. It never
    # leaves that call, and never caches budget approval or a failed proof.
    # Include current row fields as well as immutable snapshot/hash identity so
    # a changed row cannot reuse a previous successful base validation.
    cache_key = ('validated_allocation_base', company_id, row.pk, row.input_hash,
        _digest(row.source_snapshot), tuple(str(getattr(row, field.attname))
            for field in row._meta.concrete_fields if field.name != 'source_snapshot'))
    if validation_cache is not None and cache_key in validation_cache:
        validated = deepcopy(validation_cache[cache_key])
        if verify_budget:
            _scope_budget(req, company_id,
                source_scope=_allocation_budget_scope(req, company_id, validated=validated),
                read_cache=read_cache, validation_cache=validation_cache)
        return validated
    from .operation_requirement_correction_service import require_effective_requirement
    require_effective_requirement(req, company_id, read_cache=read_cache)
    context = _validate_requirement(req, company_id, read_cache=read_cache)
    source_proof = {}
    plan, step, kind, quantity, workload = _plan_context(company_id, row.production_plan_id, req,
        row.routing_step_id, native_context=context, source_proof_out=source_proof, read_cache=read_cache,
        historical=True, frozen_binding=row.source_snapshot.get('planStepVersionBinding'))
    snapshot = _allocation_snapshot(req, plan, step, kind, quantity, workload, source_proof=source_proof, read_cache=read_cache)
    if (row.company_id != company_id or row.operation_id != req.operation_id or row.product_type_id != kind.pk
        or row.source_quantity != quantity or row.source_uom_id != req.basis_uom_id
        or row.allocated_quantity != workload or row.uom_id != req.uom_id
        or row.quantity_basis != req.quantity_basis or row.rule_id != req.source_detail.rule_id
        or row.rule_version != req.source_detail.rule_version or row.source_hash != req.source_hash
        or row.input_hash != _digest(snapshot) or row.source_snapshot != snapshot):
        _fail('ALLOCATION_FACT_CHANGED', '计划、步骤、需求、单位、口径或不可变分配快照已变化')
    state = _check_audit(row.audit_record, company_id=company_id, actor_id=row.created_by_id,
        target_type='ProductionPlan', target_id=plan.pk)
    if state.get('operationRequirementAllocation') != snapshot:
        _fail('OPERATION_AUDIT_INCONSISTENT', '分配审计与不可变来源快照不一致')
    result = {'allocationId': row.pk, 'operationRequirementId': req.pk,
        'quantity': workload, 'uomId': row.uom_id, 'sourceFactId': req.source_fact_id,
        'sourceCalculationId': req.source_calculation_id, 'productTypeId': row.product_type_id,
        'operationId': row.operation_id, 'routingStepId': row.routing_step_id, 'factSource': 'server',
        'objectCoverageProof': _allocation_object_coverage_proof(row, company_id, plan, step, kind,
            context, source_proof, read_cache=read_cache)}
    if validation_cache is not None:
        validation_cache[cache_key] = deepcopy(result)
    if verify_budget:
        _scope_budget(req, company_id, source_scope=_allocation_budget_scope(req, company_id, plan=plan),
            read_cache=read_cache, validation_cache=validation_cache)
    return result


@read_span('budgetRead')
def _scope_budget(req, company_id, *, proposed_plan=None, proposed_quantity=None,
                  source_scope=None, read_cache=None, validation_cache=None):
    cache = _requirement_read_cache(read_cache, company_id)
    raw = cache._connection.connection if cache is not None else None
    # The write/proposal path never reuses an earlier read approval. A physical
    # connection change counter also invalidates proofs after same-block writes.
    share = (cache is not None and proposed_plan is None and proposed_quantity is None
        and raw is not None and hasattr(raw, 'total_changes')
        and getattr(cache.get(_CURRENT_CALL_ACTOR, cache.user), 'pk', None) == cache.user_id)
    source_item = req.source_calculation.sales_order_item
    if proposed_plan is not None:
        proposed_scope = _allocation_budget_scope(req, company_id, plan=proposed_plan)
        if source_scope is not None and source_scope != proposed_scope:
            _fail('ALLOCATION_SOURCE_MISMATCH', '候选计划与数量预算准确制造来源不一致')
        source_scope = proposed_scope
    if (not isinstance(source_scope, tuple) or len(source_scope) != 5
            or any(type(value) is not int or value <= 0 for value in source_scope)
            or source_scope[:2] != (company_id, source_item.pk)):
        _fail('ALLOCATION_SOURCE_MISMATCH', '数量预算必须使用本次已验证的准确制造来源范围')
    key = (company_id, cache.user_id if share else None, source_item.pk,
        source_scope, req.basis_uom_id, str(source_item.quantity), raw.total_changes if share else None)
    if share and key in cache.budget_proofs:
        return deepcopy(cache.budget_proofs[key])
    budget_by_plan = {}
    rows = _read_allocation_rows(company_id,
        sales_order_item_id=req.source_calculation.sales_order_item_id, read_cache=cache)
    for row in rows:
        validated = _validate_allocation(row, company_id, verify_budget=False,
            read_cache=read_cache, validation_cache=validation_cache)
        # Validate every retained order-line allocation before separating source
        # versions; an untrusted FK must never hide a corrupt historical row.
        if _allocation_budget_scope(row.operation_requirement, company_id, validated=validated) != source_scope:
            continue
        if row.source_uom_id != req.basis_uom_id:
            _fail('PLAN_QUANTITY_UOM_MISMATCH', '既有源范围分配预算单位不一致')
        if row.production_plan_id in budget_by_plan and budget_by_plan[row.production_plan_id] != row.source_quantity:
            _fail('ALLOCATION_FACT_CHANGED', '同一计划的源范围数量快照不一致')
        budget_by_plan[row.production_plan_id] = row.source_quantity
    if proposed_plan is not None:
        budget_by_plan[proposed_plan.pk] = proposed_quantity
    budget = _number(req.source_calculation.sales_order_item.quantity)
    if sum(budget_by_plan.values(), Decimal(0)) > budget:
        _fail('ALLOCATION_SCOPE_EXCEEDED', '同一准确制造来源内去重计划后的分配源数量超过正式订单行范围预算')
    if share:
        cache.budget_proofs[key] = deepcopy(budget_by_plan)
    return budget_by_plan


def _contribution_entry(req, plan, step, kind_id, quantity, workload, source_proof, *, allocation_id=None):
    return {'req': req, 'plan': plan, 'step': step, 'kindId': kind_id, 'quantity': quantity,
        'workload': workload, 'sourceProof': source_proof, 'allocationId': allocation_id}


def _saved_contribution(row, company_id, *, read_cache=None, validation_cache=None):
    _validate_allocation(row, company_id, verify_budget=False,
        read_cache=read_cache, validation_cache=validation_cache)
    version_context = resolve_step_context(row.production_plan, row.routing_step_id, historical=True,
        frozen_proof=row.source_snapshot.get('planStepVersionBinding'), read_cache=read_cache)
    plan = bind_plan_context(row.production_plan, version_context)
    entry = _contribution_entry(row.operation_requirement, plan, row.routing_step,
        row.product_type_id, row.source_quantity, row.allocated_quantity,
        row.source_snapshot.get('planEngineeringSource', {'sourceType': 'DIRECT'}), allocation_id=row.pk)
    entry['compositionProof'] = deepcopy(row.source_snapshot.get('allocationComposition'))
    return entry


def _contribution_identity(entry, company_id, read_cache=None):
    """Object/leaf identity is proved only when multiple contributions coexist.

    Legacy direct single contributions keep their original source contract and
    byte-identical allocation snapshot. A second contribution requires actual
    saved object evidence, never a name or a different EOR ID alone.
    """
    if 'identity' in entry:
        return entry['identity']
    req, plan = entry['req'], entry['plan']
    proof = entry['sourceProof']
    if not proof.get('baselineItemIds') or not proof.get('designItemIds') or not proof.get('inputFactIds'):
        output = effective_output(plan)
        try:
            proof = _read_once(read_cache, ('direct_contribution_objects', company_id, req.pk, req.input_hash),
                lambda: _extension_object_coverage(company_id, req.source_calculation,
                    req.source_calculation, req.source_fact, output, read_cache=read_cache,
                    **({'baseline': effective_baseline(plan)} if source_selection(plan) else {})))
        except OperationRequirementError as exc:
            _fail('ALLOCATION_CONTRIBUTION_IDENTITY_UNPROVEN',
                '同一步骤的多个贡献必须有正式对象、基线及原始输入证明；当前来源不能确认彼此独立',
                operationRequirementId=req.pk, sourceCode=exc.code)
    entry['identity'] = {'baselineId': proof['baselineId'],
        'baselineItemIds': set(proof['baselineItemIds']), 'designItemIds': set(proof['designItemIds']),
        'inputFactIds': set(proof['inputFactIds'])}
    return entry['identity']


def _compatible_contributions(left, right, company_id, read_cache=None):
    a, b = left['req'], right['req']
    if a.pk == b.pk:
        _fail('ALLOCATION_CONTRIBUTION_DUPLICATE', '同一正式需求贡献不能在同一候选组重复出现')
    def composition(entry):
        if entry.get('allocationId') is not None:
            return entry.get('compositionProof')
        if 'compositionProof' not in entry:
            entry['compositionProof'] = _composition_proof(entry['req'], company_id, read_cache)
        return entry['compositionProof']
    left_composition, right_composition = composition(left), composition(right)
    if bool(left_composition) != bool(right_composition):
        _fail('ALLOCATION_CONTRIBUTION_INCOMPATIBLE', '组合声明绑定的贡献不能与未绑定的历史贡献隐式混合')
    def dimensions(entry):
        req, plan, step = entry['req'], entry['plan'], entry['step']
        output = effective_output(plan)
        fact = req.source_fact
        trace = fact.trace if isinstance(fact.trace, dict) else {}
        purpose, area_type = fact.canonical_field, trace.get('AreaType')
        if (not isinstance(purpose, str) or not purpose.strip()
            or ('AreaType' in trace and (not isinstance(area_type, str) or not area_type.strip()))):
            _fail('ALLOCATION_CONTRIBUTION_PURPOSE_UNPROVEN',
                '同一步骤的多个贡献必须有正式数量用途及声明的面积分类，不能由名称或单位猜测')
        declared = composition(entry)
        if declared:
            purpose = ('COMPOSITION', declared['declarationId'], declared['ruleVersion'],
                declared['specificationHash'], declared['quantityPurpose'])
        baseline = effective_baseline(plan)
        return (plan.pk, output.pk, effective_calculation(plan).pk, baseline.pk if baseline else None,
            step.routing_version_id, step.pk, req.operation_id, entry['kindId'], req.manufacturing_mode_id,
            req.work_center_id, req.standard_capacity_id, req.uom_id, req.quantity_basis,
            req.basis_uom_id, req.basis_quantity, entry['quantity'], purpose, area_type,
            reference_type(req), _digest({key: value for key, value in req.trace[CONTEXT_KEY].items()
                if key != 'sourceObjectCoverage'}) if reference_type(req) == REFERENCE_TYPE else None)
    if dimensions(left) != dimensions(right):
        _fail('ALLOCATION_CONTRIBUTION_INCOMPATIBLE',
            '同一步骤贡献的正式来源、制造模式、资源、用途、产品类型、单位或数量口径不兼容')
    one, two = (_contribution_identity(entry, company_id, read_cache) for entry in (left, right))
    if one['baselineId'] != two['baselineId']:
        _fail('ALLOCATION_CONTRIBUTION_INCOMPATIBLE', '同一步骤贡献必须属于同一固定工程基线')
    from .operation_contribution_composition import (
        OperationContributionCompositionError, composition_allows_shared_objects,
    )
    try:
        shared_objects_allowed = composition_allows_shared_objects(left_composition, right_composition, one, two)
    except OperationContributionCompositionError as exc:
        _fail(exc.code, exc.message, **exc.details)
    if (one['inputFactIds'] & two['inputFactIds'] or not shared_objects_allowed
            and any(one[key] & two[key] for key in ('baselineItemIds', 'designItemIds'))):
        _fail('ALLOCATION_CONTRIBUTION_OVERLAP',
            '同一步骤贡献重复或重叠使用了正式对象、基线项或原始输入事实，不能重复分配',
            operationRequirementIds=[a.pk, b.pk])


def _contribution_workload_budget(entry, company_id, *, read_cache=None):
    req = entry['req']
    cache = _requirement_read_cache(read_cache, company_id)
    if cache is not None:
        # This is the complete same-company order-line set, not just this
        # plan/step. Filtering the requirement retains the original global
        # per-requirement upper bound across all its allocations and plans.
        rows = [(row.production_plan_id, row.routing_step_id, row.allocated_quantity)
            for row in _read_allocation_rows(company_id,
                sales_order_item_id=req.source_calculation.sales_order_item_id, read_cache=cache)
            if row.operation_requirement_id == req.pk]
    else:
        rows = list(ProductionPlanOperationRequirementAllocation.objects.filter(company_id=company_id,
            operation_requirement_id=req.pk).values_list('production_plan_id', 'routing_step_id', 'allocated_quantity'))
    present = any(plan_id == entry['plan'].pk and step_id == entry['step'].pk for plan_id, step_id, _ in rows)
    proposed = sum((Fraction(quantity) for _, _, quantity in rows), Fraction(0))
    if not present:
        proposed += Fraction(entry['workload'])
    maximum = Fraction(req.workload_quantity)
    if req.quantity_basis == 'PER_BASIS_QUANTITY':
        # This is a rate per formal basis, not a full-line total. Preserve the
        # existing source-scope contract instead of capping it at one basis.
        maximum *= Fraction(req.source_calculation.sales_order_item.quantity) / Fraction(req.basis_quantity)
    if proposed > maximum:
        _fail('ALLOCATION_REQUIREMENT_WORKLOAD_EXCEEDED', '该正式需求贡献的累计分配负荷超过已证明的来源范围上限')


def _check_contribution_set(entries, company_id, *, read_cache=None):
    """One non-writing set contract for preview, save and downstream readback."""
    by_step, occurrences = {}, {}
    for entry in entries:
        req, plan, step = entry['req'], entry['plan'], entry['step']
        occurrence = (plan.pk, req.pk)
        if occurrence in occurrences and occurrences[occurrence] != step.pk:
            _fail('PROCESS_STEP_MAPPING_AMBIGUOUS', '同一完整需求不能复制到重复工序的不同步骤')
        occurrences[occurrence] = step.pk
        group = by_step.setdefault((plan.pk, step.pk), [])
        for previous in group:
            _compatible_contributions(previous, entry, company_id, read_cache)
        group.append(entry)
        _contribution_workload_budget(entry, company_id, read_cache=read_cache)
    return by_step


def _allocation_rows(company_id, plan_id, step_id=None):
    rows = ProductionPlanOperationRequirementAllocation.objects.filter(company_id=company_id, production_plan_id=plan_id)
    if step_id is not None:
        rows = rows.filter(routing_step_id=step_id)
    return rows.select_related('production_plan__planning_requirement__demand__manufacturing_output',
        'routing_step', 'operation_requirement__source_detail__rule',
        'operation_requirement__calculation', 'operation_requirement__audit_record', 'audit_record')


def _allocation_save_conditions(req, plan, step, quantity, company_id, *, kind=None, workload=None,
                                source_proof=None, read_cache=None, validation_cache=None):
    """The same non-writing contribution/budget gates used before actual save."""
    rows = list(_allocation_rows(company_id, plan.pk, step.pk))
    existing = next((row for row in rows if row.operation_requirement_id == req.pk), None)
    if ProductionPlanOperationRequirementAllocation.objects.filter(production_plan=plan,
            operation_requirement=req).exclude(routing_step=step).exists():
        _fail('PROCESS_STEP_MAPPING_AMBIGUOUS', '重复工序步骤缺少独立分配规则，不能复制同一完整工序需求')
    _scope_budget(req, company_id, proposed_plan=plan, proposed_quantity=quantity,
        read_cache=read_cache, validation_cache=validation_cache)
    entries = [_saved_contribution(row, company_id, read_cache=read_cache, validation_cache=validation_cache) for row in rows]
    if not existing:
        entries.append(_contribution_entry(req, plan, step, kind.pk, quantity, workload, source_proof))
    _check_contribution_set(entries, company_id, read_cache=read_cache)
    return existing


class OperationRequirementService:
    @classmethod
    @transaction.atomic
    def read_source_conversion(cls, *, user, source_calculation_id, source_fact_ids=None, _read_cache=None,
                               generation_context=None):
        """Read fixed-source conversion proofs without evaluating or generating outputs."""
        _authorize(user, VIEW)
        read_cache = _source_read_cache(user, _read_cache)
        if type(source_calculation_id) is not int or source_calculation_id <= 0:
            _fail('SOURCE_CALCULATION_MISSING', '必须明确选择正式来源工程核算ID')
        origin = EngineeringCalculationRecord.objects.select_related('source_record',
            'sales_order_item__sales_order', 'engineering_instance').filter(
            pk=source_calculation_id, company_id=user.company_id,
            scope__in=('order_engineering', 'fact_extension'), status='completed').first()
        if not origin:
            _fail('SOURCE_CALCULATION_MISSING', '正式来源核算不存在、未完成或不属于当前公司')
        if not all((origin.source_record_id, origin.sales_order_item_id, origin.engineering_instance_id)):
            _fail('SOURCE_CALCULATION_CONTEXT_MISSING', '固定来源核算缺少来源、订单行或工程实例外键')
        if (origin.source_record.company_id != user.company_id or origin.source_record.status != 'confirmed'
            or origin.sales_order_item.sales_order.company_id != user.company_id
            or origin.engineering_instance.company_id != user.company_id
            or origin.engineering_instance.sales_order_item_id != origin.sales_order_item_id
            or origin.engineering_instance.source_record_id != origin.source_record_id):
            _fail('SOURCE_FACT_MISMATCH', '固定来源核算、公司、订单行和工程实例外键不一致')
        queryset = EngineeringDerivedFact.objects.filter(calculation=origin).select_related(
            'source_detail__rule', 'rule', 'uom')
        if source_fact_ids is not None:
            if (not isinstance(source_fact_ids, list) or any(type(value) is not int or value <= 0
                for value in source_fact_ids) or len(set(source_fact_ids)) != len(source_fact_ids)):
                _fail('SOURCE_FACT_MISMATCH', '来源事实ID必须是明确且不重复的正式整数ID')
            queryset = queryset.filter(pk__in=source_fact_ids)
        source_facts = list(queryset.order_by('sequence', 'pk'))
        if source_fact_ids is not None and len(source_facts) != len(source_fact_ids):
            _fail('SOURCE_FACT_MISMATCH', '所选事实不属于同一固定来源核算')
        existing_by_fact = {}
        existing_rows = list(EngineeringOperationRequirement.objects.filter(
            source_calculation=origin, source_fact_id__in=[fact.pk for fact in source_facts]).select_related(
                'source_detail__rule', 'calculation', 'audit_record', 'operation', 'uom'))
        for requirement in existing_rows:
            existing_by_fact.setdefault(requirement.source_fact_id, []).append(requirement)
        _prefetch_requirement_history(existing_rows, user.company_id, read_cache)
        native_rules = []
        for rule in EngineeringRuleDefinition.objects.filter(company_id=user.company_id,
            status='released').order_by('pk'):
            specification = rule.specification if isinstance(rule.specification, dict) else {}
            outputs = specification.get('outputs')
            if (_active(rule) and isinstance(outputs, list) and any(isinstance(output, dict)
                and output.get('resultDomain') == 'OPERATION_REQUIREMENT' for output in outputs)):
                native_rules.append(rule)
        facts = []
        for fact in source_facts:
            blockers, requirements, candidates, historical = [], [], [], []
            source_proof_passed = False
            try:
                detail = fact.source_detail
                if (fact.status != 'active' or fact.source_type != 'ENGINEERING_DERIVED' or not detail
                    or detail.calculation_id != origin.pk or detail.status != 'succeeded'
                    or detail.uom_id != fact.uom_id or not isinstance(fact.value, dict)
                    or not isinstance(detail.output_value, dict)
                    or fact.value != detail.output_value):
                    _fail('SOURCE_FACT_MISMATCH', '来源事实与同一固定核算的成功明细不一致')
                if origin.scope == 'fact_extension':
                    from .engineering_fact_extension_service import validate_extension_fact
                    _read_once(read_cache,
                        ('fact_extension_proof', user.company_id, origin.pk, fact.pk, origin.input_hash, origin.result_hash),
                        lambda: validate_extension_fact(origin, fact, read_cache=read_cache))
                _source_output_proof(origin, fact, detail, user.company_id)
                source_proof_passed = True
            except OperationRequirementError as exc:
                blockers.append({'code': exc.code, 'statusLabel': exc.message})
            existing = existing_by_fact.get(fact.pk, [])
            invalid_count = 0
            for requirement in existing:
                try:
                    _validate_requirement(requirement, user.company_id, read_cache=read_cache, user=user)
                    requirement_fact = {**_requirement_fact(requirement, read_cache=read_cache),
                        'operationCode': requirement.operation.code,
                        'operationName': requirement.operation.name,
                        'uomCode': requirement.uom.code, 'uomLabel': requirement.uom.name}
                    if requirement_fact.get('lifecycle', {}).get('statusCode') == 'SUPERSEDED':
                        historical.append(requirement_fact)
                    else:
                        from .operation_requirement_correction_service import require_effective_requirement
                        require_effective_requirement(requirement, user.company_id, read_cache=read_cache)
                        requirements.append(requirement_fact)
                except OperationRequirementError as exc:
                    invalid_count += 1
                    blockers.append({'operationRequirementId': requirement.pk,
                        'code': exc.code, 'statusLabel': exc.message})
            for rule in native_rules:
                specification = rule.specification if isinstance(rule.specification, dict) else {}
                inputs = specification.get('inputs')
                # Only a versioned exact input declaration is a candidate. A
                # display name, source unit or Process name cannot create one.
                if not isinstance(inputs, list) or not any(isinstance(contract, dict)
                    and contract.get('sourceType') == 'ENGINEERING_DERIVED'
                    and contract.get('sourceCanonicalField', contract.get('canonicalName')) == fact.canonical_field
                    for contract in inputs):
                    continue
                candidate = {'ruleId': rule.pk, 'ruleCode': rule.rule_code,
                    'ruleVersion': rule.version, 'ready': False, 'blockers': []}
                try:
                    context = _generation_context(user.company_id, origin.pk, fact.pk, rule.pk,
                        evaluate=False, read_cache=read_cache, user=user, generation_context=generation_context)
                    candidate.update(ready=True, operationId=context['operation'].pk,
                        productTypeId=context['product_type'].pk, quantityBasis=context['basis'],
                        basisQuantity=str(context['basis_qty']), basisUomId=context['basis_uom'].pk,
                        statusLabel='正式版本已声明精确工序及数量口径；本读取未生成需求')
                except OperationRequirementError as exc:
                    candidate['blockers'].append({'code': exc.code, 'statusLabel': exc.message})
                    candidate['statusLabel'] = exc.message
                candidates.append(candidate)
            generated_rule_ids = {requirement['ruleId'] for requirement in [*requirements, *historical]}
            pending_candidates = [candidate for candidate in candidates if candidate['ready']
                and candidate['ruleId'] not in generated_rule_ids]
            if not requirements and not existing:
                if not native_rules:
                    blockers.append({'code': 'OPERATION_RULE_MAPPING_MISSING',
                        'statusLabel': '尚无有效已发布的原生工序需求规则，工程事实继续保留'})
                elif not candidates:
                    blockers.append({'code': 'OPERATION_INPUT_MAPPING_MISSING',
                        'statusLabel': '已发布规则未精确声明本来源字段的工序需求映射'})
                elif pending_candidates:
                    blockers.append({'code': 'OPERATION_REQUIREMENT_NOT_GENERATED',
                        'statusLabel': '正式映射存在，但尚未保存工序需求；只读查看不执行生成'})
                else:
                    blockers.extend(reason for candidate in candidates for reason in candidate['blockers'])
            elif pending_candidates:
                blockers.append({'code': 'OPERATION_REQUIREMENT_PARTIAL',
                    'statusLabel': '已有正式转换，另有精确规则映射尚未生成'})
            if requirements:
                conversion = 'PARTIAL' if blockers or invalid_count else 'CONVERTED'
                label = '已有正式转换，仍有未完成或无效来源' if conversion == 'PARTIAL' else '已转换为正式工序作业量'
            elif existing or any(reason['code'] not in {'OPERATION_RULE_MAPPING_MISSING',
                'OPERATION_INPUT_MAPPING_MISSING', 'OPERATION_REQUIREMENT_NOT_GENERATED'} for reason in blockers):
                conversion, label = 'BLOCKED', '正式工序需求来源校验受阻'
            else:
                conversion, label = 'NOT_CONVERTED', '尚未转换为正式工序作业量'
            facts.append({'sourceCalculationId': origin.pk, 'sourceFactId': fact.pk,
                'sourceProofPassed': source_proof_passed,
                'sourceDetailId': fact.source_detail_id, 'sourceCanonicalField': fact.canonical_field,
                'conversionStatusCode': conversion, 'statusLabel': label,
                'operationRequirementIds': [row['operationRequirementId'] for row in requirements],
                'requirements': requirements, 'ruleCandidates': candidates, 'blockers': blockers})
            if historical:
                facts[-1]['historicalRequirements'] = historical
                facts[-1]['historicalOperationRequirementIds'] = [row['id'] for row in historical]
        legacy = list(EngineeringOperationRequirement.objects.filter(calculation=origin,
            source_fact__isnull=True).values_list('pk', flat=True))
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'sourceCalculationId': origin.pk,
            'sourceRecordId': origin.source_record_id, 'salesOrderItemId': origin.sales_order_item_id,
            'facts': facts, 'nativeOperationRuleCount': len(native_rules),
            'unmappedOperationRequirementIds': legacy, 'businessWriteCount': 0,
            'statusLabel': '已读取固定工程来源与正式工序需求转换事实'}

    @classmethod
    def generate_readiness(cls, *, user, source_calculation_id, source_fact_id, rule_id,
                           supersedes_requirement_id=None, generation_context=None):
        _authorize(user, VIEW)
        try:
            context = _generation_context(user.company_id, source_calculation_id, source_fact_id, rule_id,
                evaluate=True, supersedes_requirement_id=supersedes_requirement_id,
                user=user, generation_context=generation_context)
            existing = EngineeringOperationRequirement.objects.filter(generation_key=context['generation_key']).first()
            if existing:
                if context['source_snapshot'].get('manufacturing', {}).get('capacityMode') == REFERENCE_TYPE:
                    _validate_requirement(existing, user.company_id, user=user)
                from .operation_requirement_correction_service import require_effective_requirement
                require_effective_requirement(existing, user.company_id)
            return {'contractVersion': CONTRACT, 'factSource': 'server', 'ready': True,
                'statusLabel': '正式工序规则及固定来源已齐备', 'sourceSnapshot': context['source_snapshot'],
                'sourceHash': context['source_hash'], 'inputHash': context['input_hash'],
                'generationKey': context['generation_key'], 'evaluatedOutput': context['result'], 'businessWriteCount': 0}
        except OperationRequirementError as exc:
            return {'contractVersion': CONTRACT, 'factSource': 'server', 'ready': False,
                'statusLabel': exc.message, 'blockers': [{'code': exc.code, 'statusLabel': exc.message}], 'businessWriteCount': 0}

    @classmethod
    @transaction.atomic
    def generate(cls, *, user, source_calculation_id, source_fact_id, rule_id, idempotency_key, reason='',
                 supersedes_requirement_id=None, generation_context=None, _source_scheme_batch=None):
        decision, chain = _authorize(user, EXECUTE), _executor(user)
        # Serialize this service's same-company semantic/idempotency decisions.
        # SELECT FOR UPDATE is a read lock; the Company record is never changed.
        Company.objects.select_for_update().get(pk=user.company_id)
        request_key = _key(idempotency_key)
        context = _generation_context(user.company_id, source_calculation_id, source_fact_id, rule_id,
            evaluate=True, supersedes_requirement_id=supersedes_requirement_id,
            user=user, generation_context=generation_context)
        # Lock the shared source identity, never update or supersede it.
        EngineeringCalculationRecord.objects.select_for_update().get(pk=context['origin'].pk)
        bound = _request_binding(user.company_id, 'generate', request_key, context['generation_key'])
        # Compatibility with a primary key stored before the alias-audit contract.
        conflict = EngineeringOperationRequirement.objects.filter(calculation__company_id=user.company_id,
            trace__clientIdempotencyKey=request_key).first()
        if conflict and conflict.generation_key != context['generation_key']:
            _fail('IDEMPOTENCY_PAYLOAD_CONFLICT', '同一新增幂等键已绑定不同正式来源或规则')
        existing = EngineeringOperationRequirement.objects.filter(generation_key=context['generation_key']).first()
        if existing:
            _validate_requirement(existing, user.company_id, user=user)
            from .operation_requirement_correction_service import require_effective_requirement
            require_effective_requirement(existing, user.company_id)
            alias_audit = None
            if not bound:
                alias_audit = _state_audit(user, existing.calculation, {}, {
                    'operationRequirementId': existing.pk, 'idempotentReplay': True,
                    'requestBinding': _binding_fact('generate', request_key, context['generation_key']),
                }, decision, chain, reason or '同一正式工序来源的新幂等别名绑定，未重复生成需求')
            return {'operationRequirementId': existing.pk, 'calculationId': existing.calculation_id,
                'detailId': existing.source_detail_id, 'auditId': existing.audit_record_id,
                'operationRequirement': _requirement_fact(existing), 'idempotent': True, 'businessWriteCount': 0,
                'auditWriteCount': 1 if alias_audit else 0, 'requestBindingAuditId': alias_audit.pk if alias_audit else None}
        from .operation_workload_source_service import check_source_scheme_generation
        try:
            check_source_scheme_generation(user=user, rule=context['rule'], batch=_source_scheme_batch)
        except ProductionFoundationError as error:
            _fail(error.code, error.message, **error.details)
        try:
            code = CodeRule.next_code(entity_type='production_engineering_calculation', company_id=user.company_id)
        except CodeRule.DoesNotExist:
            _fail('CODE_RULE_REQUIRED', '缺少正式工程核算编码规则')
        started_at, finished_at = context['evaluation_started_at'], context['evaluation_finished_at']
        result, spec, origin = context['result'], context['spec'], context['origin']
        calc = create_business_object_with_initial_state(model=EngineeringCalculationRecord, initial_state='running',
            company_id=user.company_id, scope='operation_requirement', source_record=origin.source_record,
            sales_order_item=origin.sales_order_item, engineering_instance=origin.engineering_instance,
            calculation_no=code, rule_set_version=f"{context['rule'].rule_code}@{context['rule'].version}",
            revision=context['supersedes'].calculation.revision + 1 if context['supersedes'] else 1,
            supersedes=context['supersedes'].calculation if context['supersedes'] else None,
            idempotency_key=_digest({'operationRequirement': context['generation_key']}),
            input_hash=context['input_hash'], rule_graph_hash=specification_hash(spec), started_at=started_at,
            trace={'purpose': CONTRACT, 'sourceSnapshot': context['source_snapshot'],
                'canonicalInputSnapshot': context['inputs'], 'ruleSpecificationHash': specification_hash(spec),
                'ruleSpecification': spec, 'generationKey': context['generation_key'], 'factSource': 'server'})
        _initialize_history(user, calc, decision, chain, reason or '独立工序需求承接运行初始化')
        detail = create_business_object_with_initial_state(model=EngineeringCalculationDetail, initial_state='running',
            calculation=calc, sequence=1, rule=context['rule'], rule_code=context['rule'].rule_code,
            rule_version=context['rule'].version, expression_snapshot=spec['expression'],
            input_snapshot=context['inputs'], dependency_snapshot=spec.get('dependencies', []),
            output_name=result['canonicalName'], output_value={'decimal': result['value']}, uom=context['uom'],
            precision=spec['decimalPrecision'], rounding=spec['roundingMode'], started_at=started_at, finished_at=finished_at)
        _initialize_history(user, detail, decision, chain, reason or '真实规则成功明细初始化')
        detail_audit = _state_audit(user, detail, _snapshot(detail), {**_snapshot(detail), 'status': 'succeeded',
            'resultDomain': result['resultDomain'], 'specificationHash': result['specificationHash']}, decision, chain,
            reason or '正式工序规则实际求值成功')
        transition_business_object(business_object=detail, object_type='EngineeringCalculationDetail', source_state='running',
            target_state='succeeded', action_code=EXECUTE, operator=user, reason=reason or '规则求值完成',
            audit_reference=f'OrganizationOperatingAuditRecord:{detail_audit.pk}', allowed_transitions=(('running', 'succeeded'),),
            version_field=None, updated_at_field=None)
        evidence = {'generationKey': context['generation_key'], 'sourceHash': context['source_hash'],
            'inputHash': context['input_hash'], 'detailId': detail.pk, 'operationId': context['operation'].pk,
            'workloadQuantity': _quantity_text(result['value']), 'uomId': context['uom'].pk,
            'quantityBasis': context['basis'], 'basisQuantity': _quantity_text(context['basis_qty']), 'basisUomId': context['basis_uom'].pk}
        calc.result_hash = _digest({'detailId': detail.pk, 'output': result})
        calc.finished_at = finished_at
        calc.trace = {**calc.trace, 'resultSnapshot': result, 'operationRequirementEvidence': evidence}
        calc.save(update_fields=['result_hash', 'finished_at', 'trace', 'updated_at'])
        audit = _state_audit(user, calc, _snapshot(calc), {**_snapshot(calc), 'status': 'completed',
            'operationRequirementEvidence': evidence,
            'requestBinding': _binding_fact('generate', request_key, context['generation_key']),
        }, decision, chain, reason or '工序需求承接完成，原核算不变')
        transition_business_object(business_object=calc, object_type='EngineeringCalculationRecord', source_state='running',
            target_state='completed', action_code=EXECUTE, operator=user, reason=reason or '独立承接运行完成',
            audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions=(('running', 'completed'),), version_field=None)
        req = EngineeringOperationRequirement(calculation=calc, source_detail=detail, sequence=1,
            operation=context['operation'], workload_quantity=Decimal(result['value']), uom=context['uom'],
            quantity_basis=context['basis'], basis_quantity=context['basis_qty'], basis_uom=context['basis_uom'],
            source_calculation=origin, source_fact=context['fact'], generation_key=context['generation_key'],
            source_hash=context['source_hash'], input_hash=context['input_hash'], created_by=user, audit_record=audit,
            source_path=f'EngineeringCalculationDetail:{detail.pk}.output_value',
            trace={'contractVersion': CONTRACT, 'clientIdempotencyKey': request_key, 'resultDomain': 'OPERATION_REQUIREMENT',
                'ruleId': context['rule'].pk, 'ruleCode': context['rule'].rule_code, 'ruleVersion': context['rule'].version,
                'detailId': detail.pk, 'specificationHash': result['specificationHash'], 'sourceScope': 'SALES_ORDER_ITEM'})
        manufacturing = context['source_snapshot'].get('manufacturing')
        if manufacturing:
            req.manufacturing_mode_id = manufacturing['modeId']
            req.work_center_id = manufacturing['workCenterId']
            req.standard_capacity_id = manufacturing['standardCapacityId']
            if manufacturing.get('capacityMode') == REFERENCE_TYPE:
                req.trace = {**req.trace, TYPE_KEY: REFERENCE_TYPE,
                             CONTEXT_KEY: manufacturing[CONTEXT_KEY]}
        try:
            req.full_clean()
            req.save()
        except ValidationError as exc:
            _fail('OPERATION_FACT_INVALID', '新工序需求正式模型校验失败', errors=exc.message_dict)
        req.refresh_from_db()
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'operationRequirementId': req.pk,
            'calculationId': calc.pk, 'detailId': detail.pk, 'auditId': audit.pk, 'operationRequirement': _requirement_fact(req),
            'idempotent': False, 'businessWriteCount': 3, 'auditWriteCount': 4,
            'sourceCalculationWriteCount': 0, 'productionPlanWriteCount': 0}

    @classmethod
    @transaction.atomic
    def allocation_readiness(cls, *, user, production_plan_id, operation_requirement_id,
                             routing_step_id, read_cache=None, _context_out=None, _validation_cache=None):
        _authorize(user, PLAN_VIEW)
        checks = {key: {'status': 'not_evaluated', 'passed': None, 'statusLabel': '尚未评估，未以通过或零值替代'}
            for key in ('requirementValidity', 'planState', 'sourceConsistency', 'objectCoverage',
                'quantityMappingBudget', 'stepResourceApplicability', 'saveDataConditions',
                'saveConditions', 'writeAuthorization')}
        cache = _bind_current_actor({} if read_cache is None else read_cache, user)
        validation_cache = {} if _validation_cache is None else _validation_cache
        result = {'contractVersion': CONTRACT, 'factSource': 'server', 'dataReady': False,
            'ready': False, 'canSave': False,
            'checks': checks, 'assessmentScope': 'SINGLE_REQUIREMENT', 'batchSaveAllowed': None,
            'executionPerformed': False, 'businessWriteCount': 0, 'auditWriteCount': 0,
            'allocationWriteCount': 0, 'productionPlanWriteCount': 0, 'productionScheduleCreatedCount': 0}
        stage = 'requirementValidity'
        try:
            req = EngineeringOperationRequirement.objects.select_related('source_detail__rule', 'calculation',
                'audit_record').get(pk=operation_requirement_id, calculation__company_id=user.company_id)
            from .operation_requirement_correction_service import require_effective_requirement
            require_effective_requirement(req, user.company_id)
            context = _validate_requirement(req, user.company_id, read_cache=cache, user=user)
            _admission_check(checks, 'requirementValidity', '当前工序需求有效，原生来源/规则/审计证明通过；历史已排除')
            stage, source_proof = 'planState', {}
            plan, step, kind, quantity, workload = _plan_context(user.company_id, production_plan_id, req,
                routing_step_id, native_context=context, read_cache=cache, source_proof_out=source_proof, checks=checks)
            stage = 'saveDataConditions'
            existing = _allocation_save_conditions(req, plan, step, quantity, user.company_id,
                kind=kind, workload=workload, source_proof=source_proof, read_cache=cache,
                validation_cache=validation_cache)
            _admission_check(checks, 'saveDataConditions', '本条需求通过正式贡献兼容、负荷及去重计划预算校验；不是整批保存承诺')
            snapshot = _allocation_snapshot(req, plan, step, kind, quantity, workload,
                source_proof=source_proof, read_cache=cache)
            if _context_out is not None:
                _context_out.update(_contribution_entry(req, plan, step, kind.pk, quantity, workload, source_proof,
                    allocation_id=existing.pk if existing else None))
                _context_out['compositionProof'] = deepcopy(snapshot.get('allocationComposition'))
            result.update(dataReady=True, sourceSnapshot=snapshot, existingAllocationId=existing.pk if existing else None,
                statusLabel='本条正式需求的数据门禁通过；尚须证明当前账号保存资格，未执行分配')
        except EngineeringOperationRequirement.DoesNotExist:
            _admission_check(checks, stage, '正式工序需求不存在', passed=False, code='OPERATION_REQUIREMENT_MISSING')
            result.update(statusLabel='正式工序需求不存在', blockers=[{'code': 'OPERATION_REQUIREMENT_MISSING', 'statusLabel': '正式工序需求不存在'}])
        except OperationRequirementError as exc:
            if exc.code in {'ALLOCATION_OBJECT_COVERAGE_UNPROVEN', 'ALLOCATION_EXTENSION_BASELINE_UNPROVEN'}:
                stage = 'objectCoverage'
            elif stage not in {'requirementValidity', 'saveDataConditions'} and (exc.code.startswith('ALLOCATION_STEP')
                or exc.code == 'ALLOCATION_PRODUCT_TYPE_MISSING'):
                stage = 'stepResourceApplicability'
            elif stage != 'requirementValidity' and exc.code in {'PLAN_QUANTITY_UOM_MISMATCH',
                'PLAN_NET_QUANTITY_MISMATCH',
                'SOURCE_SCOPE_PARTIAL_ALLOCATION_BLOCKED', 'ALLOCATION_PRECISION_UNCONFIRMED',
                'ALLOCATION_SCOPE_EXCEEDED', 'OPERATION_WORKLOAD_INVALID'}:
                stage = 'quantityMappingBudget'
            elif stage != 'requirementValidity' and exc.code == 'ALLOCATION_SOURCE_MISMATCH' and checks['planState']['passed']:
                stage = 'sourceConsistency'
            _admission_check(checks, stage, exc.message, passed=False, code=exc.code)
            result.update(statusLabel=exc.message, blockers=[{'code': exc.code, 'statusLabel': exc.message}])
        try:
            _authorize(user, EXECUTE)
            _allocation_executor(user)
            _admission_check(checks, 'writeAuthorization', '当前账号具备原保存动作权限及实际员工/岗位/责任链；本轮仍不执行保存')
        except OperationRequirementError as exc:
            _admission_check(checks, 'writeAuthorization', exc.message, passed=False, code=exc.code)
            if result['dataReady']:
                result.update(statusLabel='本条数据门禁通过，但当前账号保存执行链受阻：' + exc.message,
                    blockers=[{'code': exc.code, 'statusLabel': exc.message}])
        result['canSave'] = result['dataReady'] and checks['writeAuthorization']['passed'] is True
        result['ready'] = result['canSave']
        if result['canSave']:
            _admission_check(checks, 'saveConditions', '本条数据门禁及当前账号原保存权限/执行链均通过；未执行，不代表整批可保存')
            result['statusLabel'] = '本条保存前置条件只读验证通过；未保存分配，不代表整批、实际占用或APS通过'
        else:
            first_blocker = result.get('blockers', [{}])[0]
            _admission_check(checks, 'saveConditions', '保存条件未全部通过，未执行分配',
                passed=False, code=first_blocker.get('code', 'SAVE_CONDITIONS_NOT_MET'))
        result['saveStatusLabel'] = ('本条服务端保存前置条件已齐备；未执行，且不代表整批可保存'
            if result['canSave'] else '保存条件未全部证明；未执行分配')
        return result

    @classmethod
    @transaction.atomic
    def allocation_group_readiness(cls, *, user, production_plan_id, contributions, read_cache=None,
                                   _validation_cache=None, _read_cache=None):
        """Evaluate one explicit candidate set together, without allocating it."""
        _authorize(user, PLAN_VIEW)
        if not isinstance(contributions, list) or not contributions:
            _fail('ALLOCATION_GROUP_INVALID', '必须明确提供非空正式需求贡献集合')
        # A new public group call must prove current source contents. Only the
        # enclosing atomic group writer may supply its private call-local cache;
        # an externally reused native read_cache cannot carry old source proof.
        cache = _bind_current_actor({} if _read_cache is None else _read_cache, user)
        validation_cache = {} if _validation_cache is None else _validation_cache
        result = {'contractVersion': CONTRACT, 'factSource': 'server', 'assessmentScope': 'CONTRIBUTION_GROUP',
            'productionPlanId': production_plan_id, 'contributions': [], 'steps': [], 'groupChecks': {},
            'dataReady': False, 'ready': False, 'canSave': False, 'passed': False, 'batchSaveAllowed': False,
            'executionPerformed': False, 'businessWriteCount': 0, 'auditWriteCount': 0, 'allocationWriteCount': 0,
            'productionPlanWriteCount': 0, 'productionScheduleCreatedCount': 0, 'blockers': []}
        entries, seen, keys, occurrences = [], set(), {}, {}
        for position, candidate in enumerate(contributions):
            if (not isinstance(candidate, dict) or any(type(candidate.get(key)) is not int or candidate[key] <= 0
                    for key in ('operationRequirementId', 'routingStepId'))):
                _fail('ALLOCATION_GROUP_INVALID', '每条贡献必须明确引用正式需求ID和精确步骤ID')
            identity = (candidate['operationRequirementId'], candidate['routingStepId'])
            duplicate = identity in seen
            seen.add(identity)
            entry = {}
            row = cls.allocation_readiness(user=user, production_plan_id=production_plan_id,
                operation_requirement_id=identity[0], routing_step_id=identity[1], read_cache=cache,
                _context_out=entry, _validation_cache=validation_cache)
            row.update(operationRequirementId=identity[0], routingStepId=identity[1], candidatePosition=position)
            problem = None
            if duplicate:
                problem = ('ALLOCATION_CONTRIBUTION_DUPLICATE', '同一正式需求和步骤不能在候选集合中重复提交')
            elif identity[0] in occurrences and occurrences[identity[0]] != identity[1]:
                problem = ('PROCESS_STEP_MAPPING_AMBIGUOUS', '同一完整需求不能复制到不同的重复工序步骤')
            occurrences[identity[0]] = identity[1]
            if candidate.get('idempotencyKey') is not None:
                key = _key(candidate['idempotencyKey'])
                if key in keys and keys[key] != identity:
                    problem = ('IDEMPOTENCY_PAYLOAD_CONFLICT', '组内相同幂等键不能绑定不同正式贡献')
                keys[key] = identity
                if entry:
                    snapshot = row['sourceSnapshot']
                    try:
                        _request_binding(user.company_id, 'allocate', key, _digest(snapshot))
                        bound = ProductionPlanOperationRequirementAllocation.objects.filter(
                            company_id=user.company_id, idempotency_key=key).first()
                        if bound and bound.source_snapshot != snapshot:
                            _fail('IDEMPOTENCY_PAYLOAD_CONFLICT', '幂等键已绑定其他正式贡献')
                    except OperationRequirementError as exc:
                        problem = (exc.code, exc.message)
            if problem:
                row.update(dataReady=False, ready=False, canSave=False,
                    blockers=[{'code': problem[0], 'statusLabel': problem[1]}], statusLabel=problem[1])
                _admission_check(result['groupChecks'], 'candidateUniqueness', problem[1], passed=False, code=problem[0])
            elif entry:
                entries.append(entry)
            result['contributions'].append(row)
            result['blockers'].extend({'operationRequirementId': identity[0], 'routingStepId': identity[1], **blocker}
                for blocker in row.get('blockers', []))
        if 'candidateUniqueness' not in result['groupChecks']:
            _admission_check(result['groupChecks'], 'candidateUniqueness', '候选贡献及可选幂等键未重复或冲突')
        complete = len(entries) == len(contributions) and all(row['dataReady'] for row in result['contributions'])
        result['groupCoverage'] = {'requestedContributionCount': len(contributions),
            'dataValidatedContributionCount': len(entries), 'complete': complete}
        for name in ('contributionCompatibility', 'quantityBudget'):
            result['groupChecks'][name] = {'status': 'not_evaluated', 'passed': None,
                'statusLabel': ('候选成员数据受阻，尚未覆盖完整候选组；有效子集诊断不能替代整组通过'
                    if not complete else '完整候选组的兼容性及预算校验尚未完成，未以通过替代')}
        try:
            # Include persisted contributions once, replacing an exact replay
            # with its verified candidate. Pending peers are never evaluated as
            # 39 unrelated empty-database previews.
            candidate_keys = {(entry['req'].pk, entry['step'].pk) for entry in entries}
            combined = [_saved_contribution(row, user.company_id, read_cache=cache, validation_cache=validation_cache)
                for row in _allocation_rows(user.company_id, production_plan_id)
                if (row.operation_requirement_id, row.routing_step_id) not in candidate_keys]
            combined.extend(entries)
            grouped = _check_contribution_set(combined, user.company_id, read_cache=cache)
            for entry in entries:
                _scope_budget(entry['req'], user.company_id, proposed_plan=entry['plan'], proposed_quantity=entry['quantity'],
                    read_cache=cache, validation_cache=validation_cache)
            if complete:
                _admission_check(result['groupChecks'], 'contributionCompatibility',
                    '已在同一集合中核验全部候选及既存贡献，正式对象和输入不重叠，步骤资源单位相容')
                _admission_check(result['groupChecks'], 'quantityBudget',
                    '每条需求负荷上限符合正式口径；计划源数量按计划去重，不乘对象数或步骤数')
            for (_, step_id), group in sorted(grouped.items()):
                result['steps'].append({'routingStepId': step_id, 'operationId': group[0]['req'].operation_id,
                    'uomId': group[0]['req'].uom_id, 'contributionCount': len(group),
                    'operationRequirementIds': [entry['req'].pk for entry in group],
                    'allocatedQuantity': str(sum((entry['workload'] for entry in group), Decimal(0)))})
        except OperationRequirementError as exc:
            check = ('quantityBudget' if exc.code in {'ALLOCATION_REQUIREMENT_WORKLOAD_EXCEEDED',
                'ALLOCATION_SCOPE_EXCEEDED', 'PLAN_QUANTITY_UOM_MISMATCH'} else 'contributionCompatibility')
            _admission_check(result['groupChecks'], check, exc.message, passed=False, code=exc.code)
            result['blockers'].append({'code': exc.code, 'statusLabel': exc.message})
        result['dataReady'] = (len(entries) == len(contributions)
            and all(row['dataReady'] for row in result['contributions'])
            and result['groupChecks'].get('contributionCompatibility', {}).get('passed') is True)
        result['canSave'] = result['dataReady'] and all(row['canSave'] for row in result['contributions'])
        result['ready'] = result['passed'] = result['batchSaveAllowed'] = result['canSave']
        result['statusLabel'] = ('整组保存前置条件只读核验通过；未保存，不代表实际产能占用、排程或APS通过'
            if result['ready'] else '整组保存前置条件受阻；未保存任何分配')
        return result

    @classmethod
    @transaction.atomic
    def allocate_group(cls, *, user, production_plan_id, contributions, reason=''):
        """Atomic wrapper over the existing audited single-contribution writer."""
        _authorize(user, EXECUTE)
        _allocation_executor(user)
        _authorize(user, PLAN_VIEW)
        Company.objects.select_for_update().get(pk=user.company_id)
        cache, validation_cache = _bind_current_actor({}, user), {}
        if not isinstance(contributions, list) or not contributions or any(
                not isinstance(row, dict) or not row.get('idempotencyKey') for row in contributions):
            _fail('ALLOCATION_GROUP_INVALID', '整组保存的每条正式贡献必须有独立幂等键')
        admission = cls.allocation_group_readiness(user=user, production_plan_id=production_plan_id,
            contributions=contributions, _read_cache=cache, _validation_cache=validation_cache)
        if not admission['canSave']:
            first = admission['blockers'][0]
            _fail(first['code'], first['statusLabel'], groupAssessment=admission)
        saved = [cls.allocate(user=user, production_plan_id=production_plan_id,
            operation_requirement_id=row['operationRequirementId'], routing_step_id=row['routingStepId'],
            idempotency_key=row['idempotencyKey'], reason=reason,
            _read_cache=cache, _validation_cache=validation_cache) for row in contributions]
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'atomic': True, 'allocations': saved,
            'idempotent': all(row['idempotent'] for row in saved),
            'businessWriteCount': sum(row['businessWriteCount'] for row in saved),
            'auditWriteCount': sum(row['auditWriteCount'] for row in saved),
            'productionPlanWriteCount': 0, 'productionScheduleCreatedCount': 0}

    @classmethod
    @transaction.atomic
    def allocate(cls, *, user, production_plan_id, operation_requirement_id, routing_step_id, idempotency_key, reason='',
                 _read_cache=None, _validation_cache=None):
        decision, chain = _authorize(user, EXECUTE), _allocation_executor(user)
        _authorize(user, PLAN_VIEW)
        Company.objects.select_for_update().get(pk=user.company_id)
        cache = _bind_current_actor({} if _read_cache is None else _read_cache, user)
        validation_cache = {} if _validation_cache is None else _validation_cache
        key = _key(idempotency_key)
        try:
            req = EngineeringOperationRequirement.objects.select_for_update().select_related('source_detail__rule',
                'calculation', 'audit_record').get(pk=operation_requirement_id, calculation__company_id=user.company_id)
        except EngineeringOperationRequirement.DoesNotExist:
            _fail('OPERATION_REQUIREMENT_MISSING', '同公司正式工序需求不存在')
        from .operation_requirement_correction_service import require_effective_requirement
        require_effective_requirement(req, user.company_id)
        context = _validate_requirement(req, user.company_id, read_cache=cache, user=user)
        EngineeringCalculationRecord.objects.select_for_update().get(pk=req.source_calculation_id)
        source_proof = {}
        plan, step, kind, quantity, workload = _plan_context(user.company_id, production_plan_id, req,
            routing_step_id, native_context=context, source_proof_out=source_proof, read_cache=cache)
        snapshot = _allocation_snapshot(req, plan, step, kind, quantity, workload, source_proof=source_proof, read_cache=cache)
        semantic_hash = _digest(snapshot)
        bound = _request_binding(user.company_id, 'allocate', key, semantic_hash)
        existing = ProductionPlanOperationRequirementAllocation.objects.filter(company_id=user.company_id, idempotency_key=key).first()
        if existing:
            if existing.source_snapshot != snapshot:
                _fail('IDEMPOTENCY_PAYLOAD_CONFLICT', '同一分配幂等键已绑定不同计划步骤或需求')
            _validate_allocation(existing, user.company_id, read_cache=cache, validation_cache=validation_cache)
            _allocation_save_conditions(req, plan, step, quantity, user.company_id,
                kind=kind, workload=workload, source_proof=source_proof, read_cache=cache,
                validation_cache=validation_cache)
            return {'allocationId': existing.pk, 'auditId': existing.audit_record_id, 'allocation': _allocation_fact(existing),
                    'idempotent': True, 'businessWriteCount': 0, 'auditWriteCount': 0}
        same = _allocation_save_conditions(req, plan, step, quantity, user.company_id,
            kind=kind, workload=workload, source_proof=source_proof, read_cache=cache,
            validation_cache=validation_cache)
        if same is not None:
            alias_audit = None
            if not bound:
                alias_audit = _state_audit(user, plan, {}, {'allocationId': same.pk,
                    'idempotentReplay': True, 'requestBinding': _binding_fact('allocate', key, semantic_hash)},
                    decision, chain, reason or '同一正式步骤分配的新幂等别名绑定，未重复分配')
            return {'allocationId': same.pk, 'auditId': same.audit_record_id,
                'allocation': _allocation_fact(same), 'idempotent': True, 'businessWriteCount': 0,
                'auditWriteCount': 1 if alias_audit else 0, 'requestBindingAuditId': alias_audit.pk if alias_audit else None}
        audit = _state_audit(user, plan, {'status': plan.status}, {'status': plan.status,
            'operationRequirementAllocation': snapshot, 'productionPlanUnchanged': True,
            'requestBinding': _binding_fact('allocate', key, semantic_hash)}, decision, chain,
            reason or '正式工序需求分配至固定计划步骤，生产计划不变')
        row = ProductionPlanOperationRequirementAllocation(company_id=user.company_id, production_plan=plan,
            operation_requirement=req, routing_step=step, operation=req.operation, product_type=kind,
            quantity_basis=req.quantity_basis, source_quantity=quantity, source_uom=req.basis_uom,
            allocated_quantity=workload, uom=req.uom, rule=req.source_detail.rule,
            rule_version=req.source_detail.rule_version, created_by=user, audit_record=audit,
            source_hash=req.source_hash, input_hash=_digest(snapshot), idempotency_key=key, source_snapshot=snapshot)
        if reference_type(req) == REFERENCE_TYPE:
            # A one-call proof from the current authorized user, bound again by
            # model.clean to this requirement/source/hash; never persisted.
            row._native_requirement_context = {'operationRequirementId': req.pk, 'context': context}
        try:
            row.full_clean()
            row.save()
        except ValidationError as exc:
            _fail('ALLOCATION_FACT_INVALID', '正式计划步骤分配校验失败', errors=exc.message_dict)
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'allocationId': row.pk, 'auditId': audit.pk,
            'allocation': _allocation_fact(row), 'idempotent': False, 'businessWriteCount': 1,
            'auditWriteCount': 1, 'productionPlanWriteCount': 0, 'productionScheduleCreatedCount': 0}

    @classmethod
    @transaction.atomic
    def read(cls, *, user, production_plan_id, _read_cache=None):
        _authorize(user, PLAN_VIEW)
        if not ProductionPlan.objects.filter(pk=production_plan_id,
            planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id).exists():
            _fail('PLAN_NOT_FOUND', '生产计划不存在或不属于当前公司')
        facts, blockers, cache = [], [], _source_read_cache(user, _read_cache)
        rows = _read_allocation_rows(user.company_id,
            production_plan_id=production_plan_id, read_cache=cache)
        validation_cache = _allocation_read_cache(cache, user.company_id)
        _prefetch_requirement_history([row.operation_requirement for row in rows], user.company_id, cache)
        proved_budget_scopes = set()
        for row in rows:
            try:
                validated = _validate_allocation(row, user.company_id, verify_budget=False,
                    read_cache=cache, validation_cache=validation_cache)
                req = row.operation_requirement
                source_item = req.source_calculation.sales_order_item
                source_scope = _allocation_budget_scope(req, user.company_id, validated=validated)
                budget_scope = (user.company_id, source_item.pk, source_scope, req.basis_uom_id, source_item.quantity)
                # Reuse only a successful whole-scope proof within this atomic read.
                # The first proof still validates every allocation across all plans.
                if budget_scope not in proved_budget_scopes:
                    _scope_budget(req, user.company_id, source_scope=source_scope,
                        read_cache=cache, validation_cache=validation_cache)
                    proved_budget_scopes.add(budget_scope)
                facts.append({**_allocation_fact(row),
                    'objectCoverageProof': deepcopy(validated['objectCoverageProof'])})
            except OperationRequirementError as exc:
                blockers.append({'allocationId': row.pk, 'code': exc.code, 'statusLabel': exc.message})
        if rows and not blockers:
            try:
                _check_contribution_set([_saved_contribution(row, user.company_id,
                    read_cache=cache, validation_cache=validation_cache) for row in rows], user.company_id, read_cache=cache)
            except OperationRequirementError as exc:
                facts = []
                blockers.append({'code': exc.code, 'statusLabel': exc.message})
        surface = {'contractVersion': CONTRACT, 'factSource': 'server', 'productionPlanId': production_plan_id,
            'allocations': facts, 'blockers': blockers, 'resultCount': len(rows), 'passed': bool(rows) and not blockers,
            'statusLabel': '已读取正式计划步骤分配' if rows and not blockers else '步骤分配缺失或受阻', 'businessWriteCount': 0}
        return {**surface, **{key: dict(surface) for key in ('apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts')}}


def _allocation_fact(row):
    return {'allocationId': row.pk, 'productionPlanId': row.production_plan_id,
        'operationRequirementId': row.operation_requirement_id, 'routingStepId': row.routing_step_id,
        'operationId': row.operation_id, 'productTypeId': row.product_type_id,
        'quantityBasis': row.quantity_basis, 'sourceQuantity': str(row.source_quantity), 'sourceUomId': row.source_uom_id,
        'allocatedQuantity': str(row.allocated_quantity), 'uomId': row.uom_id,
        'sourceHash': row.source_hash, 'inputHash': row.input_hash, 'auditId': row.audit_record_id, 'factSource': 'server'}


def process_demand_for_plan(plan, output, item, step, *, company_id, user=None, read_cache=None):
    """Return a verified exact-step bridge, or None only when no bridge exists."""
    cache = {}
    if user is not None:
        _authorize(user, PLAN_VIEW)
        if user.company_id != company_id:
            _fail('ALLOCATION_SOURCE_MISMATCH', '当前读取账号公司与正式分配读取范围不一致')
        if (isinstance(read_cache, _ReadOnlyProofCache) and read_cache.user_id == user.pk
                and read_cache.is_current(company_id)):
            cache = read_cache
        _bind_current_actor(cache, user)
    if not isinstance(plan, ProductionPlan) or not plan.pk:
        return None
    rows = _read_allocation_rows(company_id, production_plan_id=plan.pk,
        routing_step_id=step['stepId'], read_cache=cache)
    if not rows:
        return None
    if any(row.operation_id != step['operationId'] for row in rows):
        _fail('ALLOCATION_STEP_MISMATCH', '日期入口工序与正式分配步骤不一致')
    current = _read_once(_requirement_read_cache(cache, company_id),
        ('process_demand_current_plan', company_id, plan.pk), lambda:
        ProductionPlan.objects.select_related(
            'planning_requirement__demand__sales_order_item__sales_order',
            'planning_requirement__demand__manufacturing_output').get(pk=plan.pk))
    demand = current.planning_requirement.demand
    version_context = resolve_step_context(current, step['stepId'], read_cache=cache)
    if (getattr(output, 'pk', None) != version_context['output'].pk
        or getattr(item, 'pk', None) != demand.sales_order_item_id):
        _fail('ALLOCATION_SOURCE_MISMATCH', '日期入口上下文与重读计划固定来源不一致，禁止读取缓存或其他订单行')
    validation_cache = _allocation_read_cache(cache, company_id)
    if len(rows) == 1:
        fact = _validate_allocation(rows[0], company_id, read_cache=cache, validation_cache=validation_cache)
        return {**fact, 'contributions': [{**_allocation_fact(rows[0]), **fact,
            'quantity': str(fact['quantity']), 'sourceSnapshot': rows[0].source_snapshot}]}
    entries = [_saved_contribution(row, company_id, read_cache=cache, validation_cache=validation_cache) for row in rows]
    _check_contribution_set(entries, company_id, read_cache=cache)
    # Keep every immutable contribution. A group has no single allocation,
    # fact or source-calculation ID; never copy the first row's identity.
    contributions = [_validate_allocation(row, company_id, read_cache=cache, validation_cache=validation_cache) for row in rows]
    return {'allocationIds': [row.pk for row in rows],
        'operationRequirementIds': [row.operation_requirement_id for row in rows],
        'contributions': [{**_allocation_fact(row), **fact, 'quantity': str(fact['quantity']),
            'sourceSnapshot': row.source_snapshot} for row, fact in zip(rows, contributions)],
        'quantity': sum((fact['quantity'] for fact in contributions), Decimal(0)),
        'uomId': rows[0].uom_id, 'productTypeId': rows[0].product_type_id,
        'operationId': rows[0].operation_id, 'routingStepId': rows[0].routing_step_id, 'factSource': 'server'}
