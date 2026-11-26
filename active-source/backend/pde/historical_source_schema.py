"""Exact pre-migration proof projections, never a source or approval override.

Only the declared V1 consumers opt in. Full old snapshots/hashes must match;
new purpose, approval and routing bindings remain authoritative and checked.
"""
from datetime import datetime, timezone
from django.db.migrations.recorder import MigrationRecorder

CALC_BINDING = '0054_test_business_calculation_binding'
CALC_PURPOSE = '0059_order_execution_workload_contract'
ROUTE_PURPOSE = '0057_test_route_successor_purpose'
OUTPUT_BINDING = '0058_order_routing_execution_arrangement'
CALC_ADDED = frozenset(('usage_purpose', 'approval_scope', 'baseline_id',
    'design_revision_id', 'design_approval_id'))


def predates_migrations(created_at, names):
    if not isinstance(created_at, datetime):
        return False
    def utc(value):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    dates = dict(MigrationRecorder.Migration.objects.filter(app='pde', name__in=names)
        .values_list('name', 'applied'))
    return set(dates) == set(names) and all(utc(created_at) < utc(value) for value in dates.values())


def legacy_production_calculation(calc, proof_created_at):
    """Re-derive migration0059's formal root lineage; never trust a label alone."""
    from .models import EngineeringCalculationRecord
    if not isinstance(calc, EngineeringCalculationRecord) or not predates_migrations(
            proof_created_at, (CALC_BINDING, CALC_PURPOSE)):
        return False
    seen = set()
    while calc is not None:
        if (calc.pk in seen or calc.usage_purpose != 'PRODUCTION_USE'
                or calc.approval_scope != '' or calc.baseline_id is not None
                or calc.design_revision_id is not None or calc.design_approval_id is not None
                or not predates_migrations(calc.finished_at, (CALC_BINDING, CALC_PURPOSE))):
            return False
        seen.add(calc.pk)
        keys = ('company_id', 'source_record_id', 'sales_order_item_id', 'engineering_instance_id')
        if not all(getattr(calc, key) is not None for key in keys):
            return False
        if calc.scope == 'order_engineering' and calc.origin_calculation_id is None:
            return True
        if calc.scope != 'fact_extension' or not calc.origin_calculation_id:
            return False
        parent = calc.origin_calculation
        if any(getattr(calc, key) != getattr(parent, key) for key in keys):
            return False
        calc = parent
    return False


def preparation_v1_context(row, scope):
    """Reconstruct the entire old context from unchanged native rows, or fail."""
    from copy import deepcopy
    from .production_foundation_service import _snapshot
    from .operation_input_preparation_service import CONTRACT, _hash
    context = scope['context']
    if (context.get('contractVersion') != CONTRACT or scope.get('conditional')
            or scope.get('quantity_policy') or 'consumer' in context
            or not predates_migrations(row.created_at, (ROUTE_PURPOSE, OUTPUT_BINDING))):
        return None
    output = scope['native']['output']
    version = output.routing_version
    route = version.routing
    steps = list(version.steps.select_related('operation'))
    if (output.order_routing_arrangement_id is not None
            or version.origin_version_id is not None or version.test_origin_bom_id is not None
            or version.usage_purpose != 'SHARED_DEFINITION'
            or version.status != 'released' or route.status != 'released'
            or not route.is_active or route.company_id != row.company_id or not steps
            or any(not step.is_active or not step.operation.is_active
                or step.operation.company_id != row.company_id for step in steps)
            or not predates_migrations(version.created_at, (ROUTE_PURPOSE,))
            or not predates_migrations(output.created_at, (OUTPUT_BINDING,))):
        return None
    historical = deepcopy(context)
    historical['routingVersionHash'] = _hash({key:value for key,value in _snapshot(version).items()
        if key not in ('usage_purpose', 'origin_version_id', 'test_origin_bom_id')})
    historical['manufacturingOutputHash'] = _hash({key:value for key,value in _snapshot(output).items()
        if key != 'order_routing_arrangement_id'})
    # Full context equality includes every sourceSelection, formal object,
    # revision, scope, status, date, unit and original business name.
    identity = row.creation_write_request.source_identity
    saved = identity.audit_metadata
    if (not isinstance(saved, dict) or saved != {'contractVersion':CONTRACT, 'context':historical}
            or identity.source_fingerprint != _hash(historical)
            or row.context_hash != _hash(historical)):
        return None
    return historical
def historical_work_center_dates(snapshot, requirement):
    """Reproduce old dates only through a complete formal maintenance chain.

    Current active/effective resource checks have already run. This restores
    only the immutable EOR representation; it grants no current resource use.
    """
    if requirement is None:
        return snapshot
    from copy import deepcopy
    from .models import EngineeringOperationRequirement, WorkCenter
    from .production_foundation_service import _snapshot
    from system.models import OrganizationOperatingAuditRecord
    saved = EngineeringOperationRequirement.objects.filter(pk=requirement.pk).select_related(
        'calculation', 'audit_record').first()
    if not saved or _snapshot(saved) != _snapshot(requirement):
        return snapshot
    original = saved.calculation.trace.get('sourceSnapshot', {}).get('manufacturing', {})
    before = original.get('workCenter', {})
    current = snapshot.get('workCenter', {})
    date_keys = ('effectiveFrom', 'effectiveTo')
    if (not before or {k:v for k,v in before.items() if k not in date_keys}
        != {k:v for k,v in current.items() if k not in date_keys}
        or all(before.get(k) == current.get(k) for k in date_keys)):
        return snapshot
    company_id = saved.calculation.company_id
    if (saved.audit_record.organization_id != company_id
        or saved.audit_record.after_snapshot.get('state', {}).get('trace') != saved.calculation.trace
        or original.get('contractVersion') != 'PCE-MANUFACTURING-EOR-RULE-V1'):
        return snapshot
    center = WorkCenter.objects.filter(pk=current.get('id'), company_id=company_id).first()
    if not center:
        return snapshot
    fields = ('effective_from', 'effective_to')
    expected = [before.get(k) for k in date_keys]
    changed = False
    for audit in OrganizationOperatingAuditRecord.objects.filter(organization_id=company_id,
        target_type='WorkCenter', target_id=center.pk, created_at__gt=saved.created_at,
        action_code='production.master_data.resource.maintain').order_by('created_at','pk'):
        left, right = audit.before_snapshot, audit.after_snapshot
        a, b = left.get('state', {}), right.get('state', {})
        if not all(k in a and k in b for k in fields):
            return snapshot
        if (left.get('factSource') != 'server' or right.get('factSource') != 'server'
            or not right.get('authorization', {}).get('allowed')
            or a.get('id') != center.pk or b.get('id') != center.pk
            or a.get('company_id') != company_id or b.get('company_id') != company_id
            or [a[k] for k in fields] != expected):
            return snapshot
        after = [b[k] for k in fields]
        changed = changed or after != expected
        expected = after
    live = [getattr(center,k).isoformat() if getattr(center,k) else None for k in fields]
    if not changed or expected != live or expected != [current.get(k) for k in date_keys]:
        return snapshot
    result = deepcopy(snapshot)
    for key in date_keys:
        result['workCenter'][key] = before[key]
    return result

