"""One persisted engineering context for a stable plan step.

The plan and Demand are never rewritten or projected as different ORM rows.
Legacy allocations keep their original serialization and fixed output.
"""
from copy import copy, deepcopy
from decimal import Decimal
from hashlib import sha256
import json
import marshal

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import OperationalError

from .models import PlanStepVersionBinding, RoutingStep

CONTRACT = 'PCE-PLAN-STEP-VERSION-HANDOFF-V1'
OBJECT = 'PlanStepVersionBinding'
MAX_LINEAGE = 128
CALCULATION_CONTINUATION = 'CALCULATION_CONTINUATION'


class PlanStepContextError(ValidationError):
    def __init__(self, code, message, details=None):
        self.code, self.message, self.details = code, message, details or {}
        super().__init__(message, code=code)


def fail(code, message, **details):
    raise PlanStepContextError(code, message, details)


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


def _company(step):
    version = step.routing_version
    return version.routing.company_id if version.routing_id else version.product.company_id


def _route_owner(version):
    return ('routing', version.routing_id) if version.routing_id else ('product', version.product_id)


def root_step(step):
    current, visited = step, set()
    for _ in range(MAX_LINEAGE):
        if current.pk in visited:
            fail('STEP_VERSION_CYCLE', '步骤继任关系存在循环')
        visited.add(current.pk)
        if not current.predecessor_step_id:
            return current
        previous = current.predecessor_step
        if (previous.pk == current.pk or _company(previous) != _company(step)
            or _route_owner(previous.routing_version) != _route_owner(step.routing_version)
            or previous.routing_version_id == current.routing_version_id
            or previous.routing_version.revision >= current.routing_version.revision):
            fail('STEP_VERSION_LINEAGE_INVALID', '步骤前驱必须属于同公司、同路线的较早正式版本')
        current = previous
    fail('STEP_VERSION_LINEAGE_LIMIT', '步骤继任链超过可验证范围')


def validate_step_predecessor(step):
    if step.predecessor_step_id:
        root_step(step)


def calculation_source(plan, main_calculation_id, *, user=None, read_cache=None):
    """Prove saved 0046 lineage and fixed inputs; never execute a calculation."""
    from .models import EngineeringCalculationRecord, EngineeringCalculationContinuation
    from .engineering_calculation_continuation_service import continuation_proof
    from .engineering_fact_metadata import _prepare_origin
    anchor = plan.planning_requirement.demand.manufacturing_output
    item = plan.planning_requirement.demand.sales_order_item
    company_id = item.sales_order.company_id
    from .operation_requirement_service import _read_once, _requirement_read_cache
    cache = _requirement_read_cache(read_cache, company_id)
    if (type(main_calculation_id) is not int or main_calculation_id <= 0
            or user is not None and user.company_id != company_id):
        fail('STEP_VERSION_SOURCE_INVALID', '必须明确选择当前公司已保存的正式主核算')
    main = _read_once(cache, ('step_source_main_row', company_id, main_calculation_id), lambda:
        EngineeringCalculationRecord.objects.select_related('source_record', 'engineering_instance',
        'sales_order_item__sales_order').filter(pk=main_calculation_id, company_id=company_id).first())
    if (not anchor or not main or main.pk == anchor.engineering_calculation_id
            or main.scope != 'order_engineering' or main.status != 'completed'
            or main.sales_order_item_id != item.pk
            or main.engineering_instance_id != anchor.order_engineering_instance_id):
        fail('STEP_VERSION_SOURCE_INVALID', '所选主核算必须是原计划同订单行及实例的独立已完成接续结果')
    current, visited, lineage = main, set(), []
    try:
        for _ in range(MAX_LINEAGE):
            if current.pk == anchor.engineering_calculation_id:
                break
            if current.pk in visited:
                fail('STEP_VERSION_SOURCE_LINEAGE_INVALID', '主核算接续来源存在循环')
            visited.add(current.pk)
            row = _read_once(cache, ('step_source_continuation_row', company_id, current.pk), lambda:
                EngineeringCalculationContinuation.objects.select_related('previous_calculation',
                'new_calculation', 'baseline', 'write_request', 'audit_record').filter(
                    company_id=company_id, new_calculation_id=current.pk).first())
            if (row is None or row.sales_order_item_id != item.pk
                    or row.engineering_instance_id != main.engineering_instance_id):
                fail('STEP_VERSION_SOURCE_LINEAGE_INVALID', '所选主核算缺少回到原计划固定主核算的正式0046接续链')
            lineage.append(continuation_proof(row, read_cache=cache))
            current = row.previous_calculation
        else:
            fail('STEP_VERSION_SOURCE_LINEAGE_INVALID', '主核算接续链超过可验证范围')
        fixed = _prepare_origin(main, read_cache=cache)
    except PlanStepContextError:
        raise
    except Exception as error:
        if isinstance(error, ValidationError) or hasattr(error, 'code'):
            fail('STEP_VERSION_SOURCE_UNPROVEN', '已保存主核算的正式接续或固定输入证明未通过',
                cause=getattr(error, 'code', 'VALIDATION_ERROR'), reason=str(error))
        raise
    baseline = fixed['baseline']
    proof = {'selectionType': CALCULATION_CONTINUATION, 'anchorManufacturingOutputId': anchor.pk,
        'mainCalculationId': main.pk, 'baselineId': baseline.pk,
        'mainCalculationInputHash': main.input_hash, 'mainCalculationResultHash': main.result_hash,
        'mainCalculationRuleGraphHash': main.rule_graph_hash,
        'baselineSnapshotHash': baseline.snapshot_hash, 'savedObjectInputHash': fixed['inputHash'],
        'selectedObjectsHash': digest([{'baselineItemId': row.pk, 'designItemId': row.design_item_id,
            'contentHash': row.content_hash} for row in sorted(fixed['byItem'].values(), key=lambda row: row.pk)]),
        'continuationProofs': list(reversed(lineage))}
    return {'base': main, 'baseline': baseline, 'sourceProof': proof}


def _snapshot_selection(snapshot):
    if 'sourceSelection' not in snapshot:
        return None
    value = snapshot['sourceSelection']
    if (not isinstance(value, dict) or value.get('selectionType') != CALCULATION_CONTINUATION
            or any(type(value.get(key)) is not int or value[key] <= 0
                for key in ('anchorManufacturingOutputId', 'mainCalculationId', 'baselineId'))):
        fail('STEP_VERSION_SOURCE_INVALID', '步骤来源选择必须具有明确类型及完整已保存正式身份')
    return value


def route_mapping(original, target):
    """Prove complete bijection and predecessor DAG, never join names/sequences."""
    old = list(original.steps.select_related('routing_version__routing', 'operation').order_by('pk'))
    new = list(target.steps.select_related('routing_version__routing', 'predecessor_step__routing_version__routing',
        'operation').order_by('pk'))
    old_by_root, new_by_root = {}, {}
    for steps, mapping in ((old, old_by_root), (new, new_by_root)):
        for step in steps:
            key = root_step(step).pk
            if key in mapping:
                fail('STEP_VERSION_MAPPING_AMBIGUOUS', '同一路线存在重复逻辑步骤根')
            mapping[key] = step
    if old_by_root.keys() != new_by_root.keys() or not old:
        fail('STEP_VERSION_TOPOLOGY_CHANGED', '继任路线的完整步骤根集合发生变化')

    def topology(steps):
        by_sequence = {s.sequence: root_step(s).pk for s in steps}
        result = {}
        for step in steps:
            if any(v not in by_sequence for v in step.predecessor_sequences or []):
                fail('STEP_VERSION_TOPOLOGY_INVALID', '步骤依赖引用缺失的正式步骤')
            result[root_step(step).pk] = {'operationId': step.operation_id,
                'active': step.is_active,
                'predecessors': sorted(by_sequence[v] for v in step.predecessor_sequences or [])}
        return result
    if topology(old) != topology(new):
        fail('STEP_VERSION_TOPOLOGY_CHANGED', '步骤工序、启停范围或依赖拓扑发生变化，不能单步承接')
    result = [{'rootStepId': key, 'originalStepId': old_by_root[key].pk,
        'targetStepId': new_by_root[key].pk} for key in sorted(old_by_root)]
    if original.pk != target.pk:
        from system.models import OrganizationOperatingAuditRecord
        audit = OrganizationOperatingAuditRecord.objects.filter(
            organization_id=_company(old[0]), action_code='pde.routing_version.create_successor',
            target_id=target.pk).order_by('pk').last()
        state = (audit.after_snapshot or {}).get('state', {}) if audit else {}
        declared = state.get('stepPredecessorMapping')
        immediate = [{'predecessorStepId': s.predecessor_step_id, 'routingStepId': s.pk}
            for s in sorted(new, key=lambda s: s.pk)]
        from masterdata.models import MasterDataWriteRequest
        requests = list(MasterDataWriteRequest.objects.filter(organization_id=_company(old[0]),
            action_code='pde.routing_version.create_successor', entity_type='routing-versions',
            target_entity_id=str(target.pk), status=MasterDataWriteRequest.Status.COMMITTED))
        if (not audit or audit.target_type != 'RoutingVersion' or declared != immediate
            or state.get('stepPredecessorMappingHash') != digest(immediate)
            or any(s.predecessor_step.routing_version_id != state.get('sourceRoutingVersionId') for s in new)
            or len(requests) != 1 or requests[0].result.get('auditId') != audit.pk
            or requests[0].result.get('routingVersionId') != target.pk):
            fail('STEP_VERSION_MAPPING_UNPROVEN', '继任步骤映射缺少正式原生审计及Hash证明')
    return result


def validate_binding_model(binding):
    if not all(getattr(binding, key + '_id', None) for key in (
        'company', 'production_plan', 'root_step', 'target_step', 'manufacturing_output', 'write_request', 'created_by')):
        raise ValidationError('步骤版本绑定必须有完整正式FK')
    plan = binding.production_plan
    demand = plan.planning_requirement.demand
    output, original = binding.manufacturing_output, demand.manufacturing_output
    if not isinstance(binding.source_snapshot, dict):
        raise ValidationError('步骤绑定来源快照必须为正式对象')
    selection = _snapshot_selection(binding.source_snapshot)
    if (not original or demand.sales_order_item.sales_order.company_id != binding.company_id
        or output.release_subject_type != 'ORDER_ENGINEERED_PRODUCT'
        or output.order_engineering_instance_id != original.order_engineering_instance_id
        or output.order_engineering_instance.company_id != binding.company_id
        or binding.root_step.routing_version_id != original.routing_version_id
        or binding.target_step.routing_version_id != output.routing_version_id
        or root_step(binding.root_step).pk != root_step(binding.target_step).pk):
        raise ValidationError('步骤绑定必须固定同公司、同订单工程实例、原计划根步骤和目标输出精确步骤')
    if selection is not None and (output.pk != original.pk
            or selection['anchorManufacturingOutputId'] != original.pk):
        raise ValidationError('已保存主核算来源选择必须保留原计划真实制造输出锚点')
    if selection is not None and binding.target_step.applies_to_item_id is not None:
        fail('HANDOFF_SOURCE_BOM_DEPENDENCY_REQUIRED',
            '目标步骤显式依赖BOM组件，必须沿完整制造发布组合办理，不能只承接主核算来源')
    if binding.predecessor_id:
        old = binding.predecessor
        if (old.pk == binding.pk or old.company_id != binding.company_id
            or old.production_plan_id != binding.production_plan_id or old.root_step_id != binding.root_step_id
            or binding.revision != old.revision + 1):
            raise ValidationError('步骤版本绑定前驱必须同范围且修订严格加一')
    elif binding.revision != 1:
        raise ValidationError('步骤版本绑定首修订必须为1')
    if binding.source_snapshot and digest(binding.source_snapshot) != binding.context_hash:
        raise ValidationError('步骤版本绑定上下文Hash不一致')
    if binding.impact_snapshot and digest(binding.impact_snapshot) != binding.impact_hash:
        raise ValidationError('步骤版本绑定影响Hash不一致')


def binding_proof(binding, *, user=None, read_cache=None):
    validate_binding_model(binding)
    from masterdata.models import MasterDataWriteRequest
    from workflow_runtime.models import BusinessStateTransition
    from .manufacturing_output_generation_service import validate_selected_output
    selected = (validate_selected_output(binding.manufacturing_output, user=user,
        read_cache=read_cache, _content_plan_id=binding.production_plan_id) if read_cache is not None
        else validate_selected_output(binding.manufacturing_output, user=user))
    selection = _snapshot_selection(binding.source_snapshot)
    source_context = None
    binding._verified_source_context = None
    if selection is not None:
        source_context = calculation_source(binding.production_plan, selection['mainCalculationId'],
            user=user, read_cache=read_cache)
        if source_context['sourceProof'] != selection:
            fail('STEP_VERSION_SOURCE_CHANGED', '步骤冻结主核算接续、基线或来源证明已变化')
        # Call-owned real ORM references; no output FK or saved row is projected.
        binding._verified_source_context = source_context
    if not binding.audit_record_id or not binding.context_hash or not binding.impact_hash:
        fail('STEP_VERSION_BINDING_UNPROVEN', '生效绑定缺少正式审计及冻结Hash')
    audit, request = binding.audit_record, binding.write_request
    after = audit.after_snapshot or {}
    action = 'pde.plan_step.activate_engineering_version'
    if (request.status != MasterDataWriteRequest.Status.COMMITTED
        or request.organization_id != binding.company_id
        or request.action_code != action or request.entity_type != OBJECT
        or str(request.target_entity_id) != str(binding.pk)
        or request.result.get('bindingId') != binding.pk
        or request.result.get('contextHash') != binding.context_hash
        or audit.organization_id != binding.company_id or audit.actor_id != binding.created_by_id
        or audit.action_code != action
        or audit.target_type != OBJECT or audit.target_id != binding.pk
        or after.get('contextHash') != binding.context_hash or after.get('impactHash') != binding.impact_hash
        or after.get('sourceSnapshot') != binding.source_snapshot or after.get('impactSnapshot') != binding.impact_snapshot):
        fail('STEP_VERSION_BINDING_UNPROVEN', '步骤绑定请求、办理人、冻结快照或原生审计不一致')
    if selection is not None:
        bound_request = request.audit_metadata.get('request') if isinstance(request.audit_metadata, dict) else None
        if (not isinstance(bound_request, dict) or request.request_hash != digest(bound_request)
                or bound_request.get('mainCalculationId') != selection['mainCalculationId']
                or bound_request.get('outputId') != selection['anchorManufacturingOutputId']
                or bound_request.get('contextHash') != binding.context_hash
                or bound_request.get('impactHash') != binding.impact_hash):
            fail('STEP_VERSION_SOURCE_UNPROVEN', '主核算来源选择与正式请求冻结身份或Hash不一致')
    transitions = list(BusinessStateTransition.objects.filter(object_type=OBJECT,
        object_id=binding.pk).order_by('version'))
    if (len(transitions) < 2 or transitions[0].source_state != '' or transitions[0].target_state != 'draft'
        or transitions[1].source_state != 'draft' or transitions[1].target_state != 'active'
        or any(t.operator_id != binding.created_by_id for t in transitions[:2])
        or transitions[1].audit_reference != f'OrganizationOperatingAuditRecord:{audit.pk}'):
        fail('STEP_VERSION_BINDING_UNPROVEN', '步骤绑定缺少完整正式初始化及生效状态事实')
    initial_audit_id = request.result.get('initializationAuditId')
    from system.models import OrganizationOperatingAuditRecord
    initial_audit = OrganizationOperatingAuditRecord.objects.filter(pk=initial_audit_id,
        organization_id=binding.company_id, actor_id=binding.created_by_id, action_code=action,
        target_type=OBJECT, target_id=binding.pk).first()
    if (initial_audit is None or initial_audit.pk == audit.pk
        or transitions[0].audit_reference != f'OrganizationOperatingAuditRecord:{initial_audit.pk}'
        or request.result.get('initializationTransitionId') != transitions[0].pk
        or initial_audit.after_snapshot.get('contextHash') != binding.context_hash
        or initial_audit.after_snapshot.get('impactHash') != binding.impact_hash
        or initial_audit.after_snapshot.get('status') != 'draft'):
        fail('STEP_VERSION_BINDING_UNPROVEN', '步骤绑定初始化缺少独立原生审计与请求绑定')
    if (transitions[-1].target_state != binding.status or binding.version != len(transitions) - 1
        or [t.version for t in transitions] != list(range(1, len(transitions) + 1))
        or any(t.action_code != action for t in transitions)
        or any(a.target_state != b.source_state for a,b in zip(transitions,transitions[1:]))):
        fail('STEP_VERSION_BINDING_UNPROVEN', '步骤绑定当前状态与完整原生状态链不一致')
    mapping = route_mapping(binding.production_plan.planning_requirement.demand.manufacturing_output.routing_version,
        binding.manufacturing_output.routing_version)
    if binding.source_snapshot.get('stepMappingHash') != digest(mapping):
        fail('STEP_VERSION_MAPPING_UNPROVEN', '步骤绑定的正式映射已变化')
    if binding.source_snapshot.get('sourceFingerprint') != selected['sourceFingerprint']:
        fail('STEP_VERSION_SOURCE_CHANGED', '步骤绑定的制造发布组合指纹已变化')
    from .models import ProductionPlanOperationRequirementAllocation
    preserved = binding.impact_snapshot.get('preservedAllocations')
    if not isinstance(preserved, list):
        fail('STEP_VERSION_IMPACT_UNPROVEN', '步骤绑定缺少旧分配保留清单')
    ids = [row.get('allocationId') for row in preserved]
    current = list(ProductionPlanOperationRequirementAllocation.objects.filter(
        production_plan_id=binding.production_plan_id, pk__in=ids).order_by('pk'))
    actual = [{'allocationId': row.pk, 'inputHash': row.input_hash, 'sourceHash': row.source_hash,
        'snapshotHash': digest(row.source_snapshot), 'auditId': row.audit_record_id,
        'allocationHash':digest({f.attname:getattr(row,f.attname) for f in row._meta.concrete_fields})} for row in current]
    if actual != preserved:
        fail('STEP_VERSION_IMPACT_UNPROVEN', '被保留的历史分配已变化或缺失')
    proof = {'contractVersion': CONTRACT, 'bindingId': binding.pk, 'revision': binding.revision,
        'contextHash': binding.context_hash, 'impactHash': binding.impact_hash,
        'rootRoutingStepId': binding.root_step_id, 'effectiveRoutingStepId': binding.target_step_id,
        'manufacturingOutputId': binding.manufacturing_output_id,
        'routingVersionId': binding.manufacturing_output.routing_version_id,
        'sourceBaselineId': binding.manufacturing_output.order_engineering_baseline_id,
        'mainCalculationId': binding.manufacturing_output.engineering_calculation_id}
    if source_context is not None:
        proof.update(sourceBaselineId=source_context['baseline'].pk,
            mainCalculationId=source_context['base'].pk, sourceSelection=deepcopy(selection))
    return proof


_STEP_READ_RELATIONS = ('routing_version__routing',
    'predecessor_step__routing_version__routing', 'operation')
_BINDING_READ_RELATIONS = ('manufacturing_output__routing_version__routing',
    'manufacturing_output__order_engineering_instance__sales_order_item__sales_order',
    'manufacturing_output__engineering_calculation__source_record',
    'manufacturing_output__engineering_calculation__engineering_instance',
    'manufacturing_output__engineering_calculation__sales_order_item__sales_order',
    'manufacturing_output__engineering_calculation__sales_order_item__uom',
    'manufacturing_output__order_engineering_baseline__sales_order',
    'manufacturing_output__bom_version__bom',
    'manufacturing_output__engineering_document_version__document',
    'root_step__routing_version__routing', 'target_step__routing_version__routing',
    'audit_record', 'write_request', 'predecessor')
_OUTPUT_SOURCE_RELATIONS = {
    'engineering_calculation': ('source_record', 'engineering_instance',
        'sales_order_item__sales_order', 'sales_order_item__uom'),
    'order_engineering_baseline': ('sales_order',),
}


def _raw_context_row_guard(row, relations, cache):
    """Only raw concrete models, never a binding or applicability approval."""
    from . import operation_requirement_service as native
    rows, seen = [row], {id(row)}
    for relation in relations:
        current = row
        for name in relation.split('__'):
            current = getattr(current, name) if current is not None else None
            if current is not None and id(current) not in seen:
                rows.append(current)
                seen.add(id(current))
    return tuple((value._meta.label_lower, value.pk,
        native._proof_record_hash(value, read_cache=cache)) for value in rows)


def _step_raw_cache(plan, read_cache):
    from . import operation_requirement_service as native
    company_id = plan.planning_requirement.demand.sales_order_item.sales_order.company_id
    cache = native._requirement_read_cache(read_cache, company_id)
    original = plan.planning_requirement.demand.manufacturing_output
    if cache is None or original is None:
        return None, None
    version = original.routing_version
    owner_company = version.routing.company_id if version.routing_id else version.product.company_id
    if owner_company != company_id:
        # Preserve the original selected-step company rejection without a
        # broad read of another company's complete route or plan bindings.
        return None, None
    return cache, (company_id, plan.pk, original.pk, original.routing_version_id)


def _read_context_output_source(plan, output, field, *, read_cache=None):
    """Fill only an unloaded exact FK from this request's original raw rows."""
    relations = _OUTPUT_SOURCE_RELATIONS[field]
    # An explicit call-owned relation has the original ORM semantics. Do not
    # overwrite it with another instance or hide caller model pollution.
    if field in output._state.fields_cache:
        return getattr(output, field)
    cache, scope = _step_raw_cache(plan, read_cache)
    if cache is None:
        return getattr(output, field)
    field_model = output._meta.get_field(field)
    fk_id = getattr(output, field_model.attname)
    if fk_id is None:
        return None
    key = ('step_context_output_source_row', *scope, output.pk, field, fk_id)
    if key in cache:
        saved = cache[key]
        try:
            intact = saved['guard'] == _raw_context_row_guard(saved['row'], relations, cache)
        except (AttributeError, KeyError, ObjectDoesNotExist, TypeError, ValueError):
            intact = False
        if intact:
            return saved['row']
        cache.invalidate_proofs()
    row = field_model.remote_field.model.objects.select_related(*relations).get(pk=fk_id)
    # Retain the original per-consumer company rejection for a malformed FK;
    # a raw row from another company cannot enter the typed company cache.
    if getattr(row, 'company_id', None) == scope[0] and cache.is_current(scope[0]):
        cache[key] = {'row': row, 'guard': _raw_context_row_guard(row, relations, cache)}
    # Do not set fields_cache: other explicit output instances remain intact,
    # while every later unloaded lookup can recheck this raw model guard.
    return row


def _read_original_step_rows(plan, *, read_cache=None):
    cache, scope = _step_raw_cache(plan, read_cache)
    original = plan.planning_requirement.demand.manufacturing_output
    if cache is None:
        return list(original.routing_version.steps.select_related(
            'routing_version__routing', 'predecessor_step__routing_version__routing'))
    key = ('step_context_original_rows', *scope)
    if key not in cache:
        rows = list(original.routing_version.steps.select_related(*_STEP_READ_RELATIONS))
        cache[key] = {'rows': rows, 'by_id': {row.pk: row for row in rows},
            'ids': tuple(row.pk for row in rows),
            'guards': {row.pk: _raw_context_row_guard(row, _STEP_READ_RELATIONS, cache) for row in rows}}
        return rows
    saved = cache[key]
    # This entry is requested only when the native resolver must inspect the
    # whole original root set. Validate every row it will actually consume.
    try:
        intact = (tuple(row.pk for row in saved['rows']) == saved['ids'] and
            all(saved['guards'].get(row.pk) == _raw_context_row_guard(row, _STEP_READ_RELATIONS, cache)
                for row in saved['rows']))
    except (AttributeError, KeyError, ObjectDoesNotExist, TypeError, ValueError):
        intact = False
    if not intact:
        cache.invalidate_proofs()
        return _read_original_step_rows(plan, read_cache=cache)
    return saved['rows']


def _read_context_step(plan, step_id, *, read_cache=None):
    cache, scope = _step_raw_cache(plan, read_cache)
    if cache is None:
        return RoutingStep.objects.select_related(*_STEP_READ_RELATIONS).filter(pk=step_id).first()
    key = ('step_context_original_rows', *scope)
    if key not in cache:
        _read_original_step_rows(plan, read_cache=cache)
    saved = cache[key]
    step = saved['by_id'].get(step_id)
    if step is not None:
        try:
            intact = saved['guards'].get(step_id) == _raw_context_row_guard(step, _STEP_READ_RELATIONS, cache)
        except (AttributeError, KeyError, ObjectDoesNotExist, TypeError, ValueError):
            intact = False
        if intact:
            return step
        cache.invalidate_proofs()
        return _read_context_step(plan, step_id, read_cache=cache)
    # A caller may explicitly select a successor step outside the original
    # route. Keep its exact native lookup and all predecessor validation.
    return RoutingStep.objects.select_related(*_STEP_READ_RELATIONS).filter(pk=step_id).first()


def _read_context_bindings(plan, root, *, read_cache=None):
    cache, scope = _step_raw_cache(plan, read_cache)
    if cache is None:
        return list(PlanStepVersionBinding.objects.filter(production_plan=plan, root_step=root)
            .select_related(*_BINDING_READ_RELATIONS).order_by('revision'))
    key = ('step_context_binding_rows', *scope)
    if key not in cache:
        # Do not filter company/status: a bad old binding must still reach the
        # existing per-root company, head, tombstone and frozen-proof checks.
        rows = list(PlanStepVersionBinding.objects.filter(production_plan=plan)
            .select_related(*_BINDING_READ_RELATIONS).order_by('revision'))
        by_root = {}
        for row in rows:
            by_root.setdefault(row.root_step_id, []).append(row)
        cache[key] = {'by_root': {key: tuple(value) for key, value in by_root.items()},
            'guards': {row.pk: _raw_context_row_guard(row, _BINDING_READ_RELATIONS, cache) for row in rows}}
    saved = cache[key]
    # Keep the original raw partition immutable: mutating a shared binding's
    # root FK must trigger its guard, never filter it out into a false absence.
    rows = list(saved['by_root'].get(root.pk, ()))
    try:
        intact = all(saved['guards'].get(row.pk) == _raw_context_row_guard(row, _BINDING_READ_RELATIONS, cache)
            for row in rows)
    except (AttributeError, KeyError, ObjectDoesNotExist, TypeError, ValueError):
        intact = False
    if not intact:
        cache.invalidate_proofs()
        return _read_context_bindings(plan, root, read_cache=cache)
    return rows


def _resolve_step_context(plan, step_id, *, user=None, historical=False, frozen_proof=None, read_cache=None):
    """Select only an explicit active binding; a revoked head is a tombstone."""
    original = plan.planning_requirement.demand.manufacturing_output
    if not original:
        fail('STEP_VERSION_PLAN_SOURCE_MISSING', '计划缺少固定制造输出')
    company_id = plan.planning_requirement.demand.sales_order_item.sales_order.company_id
    from .capacity_evidence_read_scope import evidence_cache

    # Share guarded ORM inputs only. Binding proof still uses the caller's
    # original read context and independently verifies each bound step.
    snapshot_cache = evidence_cache(company_id) if read_cache is None else None
    raw_cache = read_cache if read_cache is not None else snapshot_cache
    step = _read_context_step(plan, step_id, read_cache=raw_cache)
    if step is None or _company(step) != company_id:
        fail('STEP_VERSION_STEP_MISSING', '正式步骤不存在或不属于当前公司')
    if historical and frozen_proof is None:
        if step.routing_version_id != original.routing_version_id:
            fail('STEP_VERSION_NOT_BOUND', '历史无绑定事实必须保持原计划固定路线')
        return {'plan':plan,'originalOutput':original,'output':original,
            'root_step':step,'step':step,'binding':None,'bindingProof':None,
            'base':_read_context_output_source(plan, original, 'engineering_calculation', read_cache=read_cache),
            'baseline':_read_context_output_source(plan, original, 'order_engineering_baseline', read_cache=read_cache),
            'routing_version':original.routing_version,'sourceProof':None}
    lineage_root = root_step(step).pk
    roots = ([step] if step.routing_version_id == original.routing_version_id else
        [s for s in _read_original_step_rows(plan, read_cache=raw_cache) if root_step(s).pk == lineage_root])
    if len(roots) != 1:
        fail('STEP_VERSION_ROOT_UNPROVEN', '所选步骤不能唯一映射到原计划固定路线')
    root = roots[0]
    if historical and frozen_proof is None:
        binding = None
    else:
        try:
            rows = _read_context_bindings(plan, root, read_cache=raw_cache)
        except OperationalError as error:
            if ('no such table: pde_plan_step_version_binding' not in str(error).lower() or frozen_proof):
                raise
            rows = []  # Pre-migration legacy reads cannot invent a binding.
        heads = [r for r in rows if r.pk not in {x.predecessor_id for x in rows if x.predecessor_id}]
        if len(heads) > 1 or rows and not heads:
            fail('STEP_VERSION_BINDING_AMBIGUOUS', '步骤版本承接存在多个前驱链头')
        if historical and frozen_proof is not None:
            matches = [r for r in rows if r.pk == frozen_proof.get('bindingId')]
            if len(matches) != 1 or matches[0].status == 'draft':
                fail('STEP_VERSION_HISTORICAL_BINDING_UNPROVEN', '历史冻结绑定不存在或尚未正式生效')
            binding = matches[0]
        else:
            binding = heads[0] if heads else None
        if binding and binding.status != 'active' and not (historical and frozen_proof is not None):
            fail('STEP_VERSION_NOT_ACTIVE', '该逻辑步骤版本承接尚未生效或已撤销，禁止回退原版本')
    proof = (binding_proof(binding, user=user, read_cache=read_cache) if read_cache is not None
        else binding_proof(binding, user=user)) if binding else None
    if frozen_proof is not None and proof != frozen_proof:
        fail('STEP_VERSION_BINDING_CHANGED', '已保存事实的版本绑定证明与当前正式证据不一致')
    output, actual = (binding.manufacturing_output, binding.target_step) if binding else (original, root)
    if not binding and step.pk != root.pk:
        fail('STEP_VERSION_NOT_BOUND', '新路线步骤尚未正式承接到当前计划')
    source = getattr(binding, '_verified_source_context', None) if binding else None
    result = {'plan': plan, 'originalOutput': original, 'output': output,
        'root_step': root, 'step': actual, 'binding': binding, 'bindingProof': proof,
        'base':source['base'] if source else _read_context_output_source(
            plan, output, 'engineering_calculation', read_cache=read_cache),
        'baseline':source['baseline'] if source else _read_context_output_source(
            plan, output, 'order_engineering_baseline', read_cache=read_cache),
        'routing_version':actual.routing_version, 'sourceProof':deepcopy(source['sourceProof']) if source else None}
    if source is not None:
        result['_sourceIntegrity'] = _source_context_fingerprint(result)
    if snapshot_cache is not None:
        from .operation_requirement_service import _copy_read_proof
        return _copy_read_proof(result)
    return result


def _source_context_fingerprint(context):
    """Call-owned concrete identities only; never reload a fact or a proof."""
    from . import operation_requirement_service as native
    return digest({'models': {name:native._proof_record_hash(context[name])
        for name in ('base', 'baseline', 'output', 'step')},
        'sourceProofHash':digest(context.get('sourceProof'))})


def _source_context_bytes(context):
    """Complete call-owned values; unsupported values retain canonical checks."""
    models = {}
    for name in ('base', 'baseline', 'output', 'step'):
        values = {}
        for field in context[name]._meta.concrete_fields:
            value = getattr(context[name], field.attname)
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            elif isinstance(value, Decimal):
                value = str(value)
            values[field.attname] = value
        models[name] = values
    try:
        # Protocol 2 is value-based: alias/refcount differences between equal
        # call-owned projections must not force a canonical fallback.
        return marshal.dumps({'models': models, 'sourceProof': context.get('sourceProof')}, 2)
    except (TypeError, ValueError):
        return None


class _SourceIntegrityFastGuard:
    """Immutable full values, never an approval or a deserialized snapshot."""
    __slots__ = ('_bytes', '_canonical')

    def __init__(self, context):
        object.__setattr__(self, '_bytes', _source_context_bytes(context))
        object.__setattr__(self, '_canonical', context['_sourceIntegrity'])

    def __setattr__(self, name, value):
        raise AttributeError('Source integrity guards are immutable')

    def __deepcopy__(self, memo):
        return self

    def matches(self, context):
        return (context.get('_sourceIntegrity') == self._canonical and self._bytes is not None
            and _source_context_bytes(context) == self._bytes)


def resolve_step_context(plan, step_id, *, user=None, historical=False, frozen_proof=None, read_cache=None):
    from . import operation_requirement_service as native
    company_id = plan.planning_requirement.demand.sales_order_item.sales_order.company_id
    cache = native._requirement_read_cache(read_cache, company_id)
    original = plan.planning_requirement.demand.manufacturing_output
    key = ('plan_step_version_context',company_id,plan.pk,step_id,historical,digest(frozen_proof),native._today(),
        plan.updated_at,original.pk if original else None,original.updated_at if original else None)
    if cache is not None and key in cache:
        cached = cache[key]
        try:
            source_selection(cached)
        except PlanStepContextError:
            # Shared ORM instances may have been altered in memory. Drop every
            # dependent approval and reconstruct this context from its DB scope.
            cache.invalidate_proofs()
        else:
            return native._copy_read_proof(cached)
    result = _resolve_step_context(plan,step_id,user=user,historical=historical,frozen_proof=frozen_proof,
        **({'read_cache': cache} if cache is not None else {}))
    if cache is not None:
        if result.get('_sourceIntegrity') is not None:
            result['_sourceIntegrityGuard'] = _SourceIntegrityFastGuard(result)
        cache[key] = native._copy_read_proof(result)
    return result


def version_fact(context):
    original, output = context['originalOutput'], context['output']
    binding = context['binding']
    result = {'statusLabel': '新工程版本已正式承接' if binding else '原计划固定工程版本',
        'versionLabel': f'制造输出{output.pk} / 工程基线{output.order_engineering_baseline_id} / 核算{output.engineering_calculation_id} / 路线{output.routing_version_id}',
        'originalManufacturingOutputId': original.pk, 'effectiveManufacturingOutputId': output.pk,
        'originalRoutingVersionId': original.routing_version_id, 'effectiveRoutingVersionId': output.routing_version_id,
        'rootRoutingStepId': context['root_step'].pk, 'effectiveRoutingStepId': context['step'].pk,
        'bindingId': binding.pk if binding else None, 'sourceBaselineId': output.order_engineering_baseline_id,
        'mainCalculationId': output.engineering_calculation_id}
    selection = source_selection(context)
    if selection is not None:
        result.update(statusLabel='已保存主核算已正式承接到本步骤',
            versionLabel=f'原制造输出{output.pk}锚点 / 工程基线{context["baseline"].pk} / 核算{context["base"].pk} / 路线{context["step"].routing_version_id}',
            sourceBaselineId=context['baseline'].pk, mainCalculationId=context['base'].pk,
            sourceSelection=selection)
    return result


def effective_output(plan):
    context = getattr(plan, '_native_step_version_context', None)
    if context:
        source_selection(context)
    return context['output'] if context else plan.planning_requirement.demand.manufacturing_output


def effective_calculation(plan):
    context = getattr(plan, '_native_step_version_context', None)
    if context and (source_selection(context) is not None or 'base' in context):
        return context['base']
    return effective_output(plan).engineering_calculation


def effective_baseline(plan):
    context = getattr(plan, '_native_step_version_context', None)
    if context and (source_selection(context) is not None or 'baseline' in context):
        baseline=context['baseline']
    else:
        baseline=effective_output(plan).order_engineering_baseline
    if baseline is not None:
        from .baseline_usage_service import validate_baseline
        from .product_design_service import ProductDesignError
        try:validate_baseline(baseline)
        except ProductDesignError as exc:fail(exc.code,exc.message)
    return baseline


def effective_routing_version(plan):
    context = getattr(plan, '_native_step_version_context', None)
    if context:
        source_selection(context)
    return context.get('routing_version', context['step'].routing_version) if context else effective_output(plan).routing_version


def source_selection(plan_or_context):
    """Project only the resolver's already verified, call-owned source proof."""
    context = (plan_or_context if isinstance(plan_or_context, dict)
        else getattr(plan_or_context, '_native_step_version_context', None))
    value = context.get('sourceProof') if context else None
    binding = context.get('bindingProof') if context else None
    selected = (value is not None or context is not None and '_sourceIntegrity' in context
        or isinstance(binding, dict) and 'sourceSelection' in binding)
    if selected:
        try:
            guard = context.get('_sourceIntegrityGuard')
            intact = (isinstance(guard, _SourceIntegrityFastGuard) and guard.matches(context)
                or context.get('_sourceIntegrity') == _source_context_fingerprint(context))
        except (AttributeError, KeyError, TypeError, ValueError):
            intact = False
        if not intact:
            fail('STEP_VERSION_SOURCE_CHANGED', '步骤已验证来源上下文在本次读取内发生变化，必须重新读取')
    if value is not None and (not isinstance(value, dict)
            or value.get('selectionType') != CALCULATION_CONTINUATION):
        fail('STEP_VERSION_SOURCE_INVALID', '步骤有效来源类型未获正式验证')
    return deepcopy(value)


def bind_plan_context(plan, context):
    # The property is call-owned only; concrete ORM fields and related FKs stay intact.
    projected = copy(plan)
    projected._native_step_version_context = {k:v for k,v in context.items() if k != 'plan'}
    return projected
