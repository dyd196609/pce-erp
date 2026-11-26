"""Formal process applicability from the existing approved capacity matrix.

Capacity is never an operation workload, a completion or a custody quantity.
Only an explicit non-applicable entry in a VALID complete native source
manifest proves a saved blank; missing/invalid sources remain unknown.
"""
from copy import deepcopy
from .daily_capacity_service import capacity_source_rules
from .operation_requirement_service import _today
from .models import CapacityProductType


def has_development_assumption(value):
    if isinstance(value, dict):
        return value.get('code') == 'FORMAL-CHAIN-DEV' or any(has_development_assumption(v) for v in value.values())
    return isinstance(value, list) and any(has_development_assumption(v) for v in value)


def read_route_capacity(version, *, company_id):
    route = version.routing
    unknown = {'status': 'PENDING', 'productTypeCode': None, 'steps': {},
        'blockingReason': '正式工艺类型、完整产能来源或精确关联待核实；缺项不能作为不执行。'}
    if not route or route.company_id != company_id or not route.is_active:
        return unknown
    from .routing_capacity_identity import routing_capacity_identity
    category_id,process_id=routing_capacity_identity(route,company_id)
    if not category_id or not process_id:return unknown
    from .capacity_evidence_read_scope import evidence_cache
    cache = evidence_cache(company_id)
    on_date = _today()
    if cache is None:
        return _read_route_capacity(version, route.pk, company_id, category_id, process_id, on_date, unknown)
    from .operation_requirement_service import _read_once
    key = ('route_capacity_result', company_id, on_date, route.pk, version.pk, category_id, process_id)
    return deepcopy(_read_once(cache, key,
        lambda: _read_route_capacity(version, route.pk, company_id, category_id, process_id, on_date, unknown)))


def _read_route_capacity(version, routing_id, company_id, category_id, process_id, on_date, unknown):
    kinds = list(CapacityProductType.objects.filter(company_id=company_id,
        product_category_id=category_id,
        manufacturing_process_type_id=process_id, is_active=True))
    if len(kinds) != 1:
        return unknown
    kind = kinds[0]
    source = capacity_source_rules(kind, company_id=company_id, on_date=on_date)
    if source['status'] != 'VALID':
        return {**unknown, 'productTypeCode': kind.code, 'blockingReason': source['fact']['statusLabel'],
            'sourceStatus': source['status']}
    manifest = source['manifest']
    rows = source['capacityRows']
    steps = {}
    for step in version.steps.select_related('operation').order_by('sequence'):
        matches = [r for r in rows if r.operation_id == step.operation_id]
        if step.operation_id in manifest['nonApplicableOperationIds']:
            result, capacity, meaning = 'NOT_APPLICABLE', None, '正式保存的产能矩阵空值：不经过'
        elif step.operation_id in manifest['applicableOperationIds'] and matches:
            values = {r.quantity for r in matches}
            if len(values) != 1:
                steps[step.pk] = {'result': 'PENDING', 'reason': '同工序正式产能值冲突，不能推断执行或数量。'}
                continue
            capacity = next(iter(values))
            result, meaning = 'REQUIRED', ('标准产能为0：经过，无法准确确定产能，不占用产能'
                if capacity == 0 else '标准产能为数值：经过，有产能数据')
        else:
            steps[step.pk] = {'result': 'PENDING', 'reason': '完整正式来源未覆盖此工序；不是保存空值。'}
            continue
        steps[step.pk] = {'result': result, 'sourceValuePresent': True,
            'sourceValue': None if capacity is None else str(capacity), 'meaning': meaning,
            'capacityIds': [r.pk for r in matches], 'capacityCodes': [r.code for r in matches],
            'sourceCells': [r.conditions.get('sourceCell') for r in matches],
            'workCenterIds': sorted({r.work_center_id for r in matches}),
            'workCenterNames': sorted({r.work_center.name for r in matches}),
            'capacityUomLabels': sorted({r.uom.name for r in matches}),
            'capacityOccupancyApplicable': capacity is not None and capacity > 0,
            'quantityAuthoritySeparate': True}
    return {'status': 'VALID', 'productTypeId': kind.pk, 'productTypeCode': kind.code,
        'routingId': routing_id, 'routingVersionId': version.pk,
        'sourceSha256': manifest['sourceSha256'], 'sourceContract': manifest['contractVersion'],
        'sourceProof': deepcopy(source['fact']), 'steps': steps, 'blockingReason': None}


def reconcile_development_applicability(step, payload):
    """Replace an explicitly technical assumption using a proved native source.

    The original decision/audit remains visible, never rewritten. Ordinary
    business decisions and historical proof replays keep their own authority.
    """
    if not has_development_assumption(payload):
        return payload
    from planning.operation_predecessor_authority import _historical_proof_only
    if _historical_proof_only.get():
        return payload
    source = read_route_capacity(step.routing_version,
        company_id=step.routing_version.routing.company_id)
    formal = source['steps'].get(step.pk, {})
    result = formal.get('result', 'PENDING')
    if source['status'] == 'VALID' and result == payload.get('result'):
        return payload
    reconciled = deepcopy(payload)
    reconciled.pop('objectApplicability', None)
    reconciled.update(result=result, resultLabel={'REQUIRED': '正式标准产能来源确认经过',
        'NOT_APPLICABLE': '正式保存空值确认不经过', 'PENDING': '正式来源读取或关联待核实'}[result],
        formalApplicabilityValidated=source['status'] == 'VALID' and result != 'PENDING',
        contractSource='APPROVED_CAPACITY_MATRIX_RECONCILIATION',
        formalSourceLabel='既有正式标准产能数值/0/空值来源规则',
        supersededTechnicalApplicability=deepcopy(payload),
        capacityApplicability={'source': source['sourceProof'] if source['status'] == 'VALID' else source,
            'step': formal, 'historicalDecisionUnchanged': True},
        pendingReason=source['blockingReason'] if result == 'PENDING' else '')
    return reconciled
