"""Formal, operation-scoped execution mode; never infer completion or resources.

Legacy quantified snapshots retain their canonical shape. New nonquantity
execution freezes an exact native preparation/applicability proof. A zero
capacity, dependency marker, missing quantity or UI label alone grants nothing.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ObjectDoesNotExist, ValidationError

from .services import PlanningBusinessError
from .work_order_execution_service import _fail, _hash, _verify

CONTRACT = 'PCE-OPERATION-EXECUTION-MODE-V1'
QUANTIFIED = 'QUANTIFIED'
NON_QUANTIFIED_REQUIRED = 'NON_QUANTIFIED_REQUIRED'
NOT_APPLICABLE = 'NOT_APPLICABLE'
PENDING = 'PENDING'
LABELS = {QUANTIFIED: '可统计实际数量', NON_QUANTIFIED_REQUIRED: '必经但不统计实际数量',
    NOT_APPLICABLE: '本次正式不适用', PENDING: '执行模式依据待核实'}


def _quantified_proof(operation):
    return {'contractVersion': CONTRACT, 'executionMode': QUANTIFIED,
        'companyId': operation.work_order.company_id, 'workOrderId': operation.work_order_id,
        'operationId': operation.pk, 'operationSnapshotHash': operation.snapshot_hash,
        'workOrderSnapshotHash': operation.work_order.snapshot_hash,
        'sourceAuthority': 'IMMUTABLE_FORMAL_QUANTIFIED_WORK_ORDER_SOURCE'}


def _reference(operation):
    quantity, unit = operation.workload_quantity, operation.workload_uom
    return {'quantity': quantity, 'uomId': operation.workload_uom_id,
        'uomCode': unit.code if unit else None, 'uomLabel': unit.name if unit else None,
        'statusLabel': '正式来源参考作业量；不代表实际完成量' if quantity is not None else '不单独计量，未填造数量或单位',
        'nullReason': None if quantity is not None else 'NOT_SEPARATELY_MEASURED_OR_FORMAL_SOURCE_NULL'}


def _pair_valid(operation, *, required=False):
    if operation.workload_quantity is None and operation.workload_uom_id is None:
        return not required
    if operation.workload_quantity is None or operation.workload_uom_id is None:
        return False
    try:
        value = Decimal(operation.workload_quantity)
        return bool(value.is_finite() and value > 0 and operation.workload_uom.company_id == operation.work_order.company_id
            and operation.workload_uom.is_active)
    except (InvalidOperation, TypeError, ValueError):
        return False


def _load_formal_mode_basis(operation, actor):
    """Internal exact-source reader; caller gets no PDE maintenance permission.

This is the explicit synthetic-upstream boundary used only by isolated tests.
Production always re-proves native scope, complete preparation history and
current engineering identity here, without a writer or a permission fallback.
"""
    from .operation_exemption_authority import _load_scope
    from pde import operation_input_preparation_service as prep
    from pde.conditional_execution_preparation import (saved_for_scope, is_quantity_basis,
        is_conditional_basis, build_quantity_policy_context, build_conditional_context)
    from pde.plan_step_context_service import effective_baseline
    from .workshop_reception_read_projection import current_native_read_cache
    read_cache=current_native_read_cache(actor)
    operation, context, version, frozen = _load_scope(operation, actor)
    plan, output, item, base, step, kind, applicability = context
    exact = {'companyId': operation.work_order.company_id, 'productionPlanId': plan.pk,
        'manufacturingOutputId': output.pk, 'mainCalculationId': base.pk, 'salesOrderItemId': item.pk,
        'baselineId': effective_baseline(plan).pk, 'routingVersionId': output.routing_version_id,
        'routingStepId': step.pk, 'operationId': step.operation_id, 'productTypeId': kind.pk}
    row = saved_for_scope(exact)
    prepared = None
    if row is not None:
        if is_quantity_basis(row.business_basis):
            policy = row.business_basis['quantityPolicy']
            native_scope = build_quantity_policy_context(user=None, exact_scope=exact,
                statistical_routing_step_id=policy['statisticalUomReference']['routingStepId'],
                standard_capacity_id=policy['capacityReference']['standardCapacityId'],read_cache=read_cache)
        elif is_conditional_basis(row.business_basis):
            native_scope = build_conditional_context(user=None, exact_scope=exact,read_cache=read_cache)
        else:
            native_scope = prep._scope(actor, exact, policy_basis=row.business_basis,read_cache=read_cache)
        prepared = prep._present(native_scope, row, prep._verify(row, native_scope))
    prep._reference_history_check(exact, row)
    return {'scope': exact, 'engineeringVersion': version, 'applicability': deepcopy(applicability),
        'preparation': prepared, 'sourceAuthority': 'NATIVE_PDE_APPLICABILITY_AND_PREPARATION'}


def _current_formal_context(operation, actor):
    """Internal current applicability read without PDE maintenance grants."""
    from .operation_exemption_authority import _load_scope
    operation, context, version, _ = _load_scope(operation, actor)
    plan, output, item, base, step, kind, applicability = context
    from pde.plan_step_context_service import effective_baseline
    return {'scope': {'companyId': operation.work_order.company_id, 'productionPlanId': plan.pk,
        'manufacturingOutputId': output.pk, 'mainCalculationId': base.pk, 'salesOrderItemId': item.pk,
        'baselineId': effective_baseline(plan).pk, 'routingVersionId': output.routing_version_id,
        'routingStepId': step.pk, 'operationId': step.operation_id, 'productTypeId': kind.pk},
        'engineeringVersion': version, 'applicability': deepcopy(applicability),
        'sourceAuthority': 'NATIVE_PDE_APPLICABILITY_AND_PREPARATION'}


def _current_policy_rows(operation):
    from pde.models import OperationInputPreparationDraft
    return list(OperationInputPreparationDraft.objects.filter(company_id=operation.work_order.company_id,
        production_plan_id=operation.work_order.production_plan_id,
        routing_step_id=operation.effective_step_id).only('business_basis')[:2])


def _requires_native_policy_read(operation):
    rows = _current_policy_rows(operation)
    if len(rows) > 1:
        return True
    for row in rows:
        basis = row.business_basis
        if not isinstance(basis, dict) or 'quantityPolicy' in basis or 'conditionalExecution' in basis:
            return True
        entries = basis.get('entries', [])
        if not isinstance(entries, list) or any(not isinstance(item, dict) or 'capacityRuling' in item for item in entries):
            return True
    return False


def _proof(operation, mode, basis):
    prep = basis.get('preparation') or {}
    version = basis.get('engineeringVersion') or {}
    from .operation_exemption_authority import VERSION_KEYS
    return {'contractVersion': CONTRACT, 'companyId': operation.work_order.company_id,
        'workOrderId': operation.work_order_id, 'operationId': operation.pk,
        'operationSnapshotHash': operation.snapshot_hash, 'executionMode': mode,
        'scope': deepcopy(basis.get('scope')), 'engineeringVersion': {key: deepcopy(version.get(key)) for key in VERSION_KEYS},
        'applicability': deepcopy(basis.get('applicability')),
        'preparation': {key: deepcopy(prep.get(key)) for key in ('recordId', 'revision', 'contextHash',
            'objectsHash', 'contentHash', 'auditIds', 'writeRequestId', 'sourceIdentityId',
            'quantityPolicy', 'capacityResolution', 'capacitySemantics')},
        'sourceAuthority': basis.get('sourceAuthority', 'NATIVE_PDE_APPLICABILITY_AND_PREPARATION')}


def _result(operation, mode, *, ready, proof=None, issues=()):
    return {'executionMode': mode, 'executionModeLabel': LABELS[mode],
        'quantityApplicable': True if mode == QUANTIFIED else False if mode == NON_QUANTIFIED_REQUIRED else None,
        'modeSourceHash': _hash(proof) if proof is not None else None,
        'modeSourceProof': deepcopy(proof), 'sourceProof': deepcopy(proof),
        'referenceWorkload': _reference(operation), 'ready': bool(ready), 'blockingReasons': list(issues),
        'sourceAuthority': proof.get('sourceAuthority') if proof else 'FORMAL_MODE_UNPROVEN',
        'resourceAdmissionSeparate': True, 'businessWriteCount': 0, 'auditWriteCount': 0}


def _classify_basis(operation, basis):
    """Classify only a native-verified scope, not arbitrary capacity facts."""
    app, prep = basis.get('applicability') or {}, basis.get('preparation') or {}
    scope = basis.get('scope')
    from .operation_exemption_authority import VERSION_KEYS
    frozen_version = operation.source_snapshot.get('frozenStep', {}).get('engineeringVersion')
    current_version = basis.get('engineeringVersion')
    if (not isinstance(scope, dict) or scope.get('companyId') != operation.work_order.company_id
            or scope.get('productionPlanId') != operation.work_order.production_plan_id
            or scope.get('routingStepId') != operation.effective_step_id
            or scope.get('operationId') != operation.operation_id
            or app.get('result') not in ('REQUIRED', 'NOT_APPLICABLE', 'PENDING')
            or not isinstance(frozen_version, dict) or not isinstance(current_version, dict)
            or any(current_version.get(key) != frozen_version.get(key) for key in VERSION_KEYS)):
        return _result(operation, PENDING, ready=False, issues=['执行模式缺少本公司、本工单及精确步骤的正式来源证明。'])
    if app['result'] == 'NOT_APPLICABLE':
        return _result(operation, NOT_APPLICABLE, ready=False, proof=_proof(operation, NOT_APPLICABLE, basis),
            issues=['本工序正式不适用，应核对免执行证明，不创建实际执行任务。'])
    if app['result'] == 'PENDING' or app.get('conditionalExecution'):
        return _result(operation, PENDING, ready=False, proof=_proof(operation, PENDING, basis),
            issues=[app.get('pendingReason') or '本工序适用性待确认或待实际触发，不能执行或推断免执行。'])
    if app.get('formalApplicabilityValidated') is not True:
        return _result(operation, PENDING, ready=False, issues=['本工序必须执行的正式适用性尚未核实。'])
    policy = prep.get('quantityPolicy')
    from pde.operation_workload_source_service import _non_separate_quantity_policy
    quantity_policy = _non_separate_quantity_policy(prep, scope, app)
    semantics, resolution = prep.get('capacitySemantics') or {}, prep.get('capacityResolution') or {}
    prepared = bool(prep.get('factSource') == 'server' and prep.get('recordStatus') == 'RECORDED'
        and type(prep.get('recordId')) is int and prep['recordId'] > 0
        and type(prep.get('revision')) is int and prep['revision'] > 0
        and prep.get('exactScope') == scope and isinstance(prep.get('auditIds'), list) and prep['auditIds']
        and all(type(value) is int and value > 0 for value in prep['auditIds'])
        and all(type(prep.get(key)) is int and prep[key] > 0 for key in ('writeRequestId', 'sourceIdentityId'))
        and all(isinstance(prep.get(key), str) and len(prep[key]) == 64
            and all(char in '0123456789abcdef' for char in prep[key])
            for key in ('contextHash', 'objectsHash', 'contentHash')))
    formal_zero_preparation = bool(prepared and policy is None and resolution.get('valid') is True
        and resolution.get('code') == 'CONFIRMED_ZERO' and isinstance(resolution.get('sourceProof'), dict)
        and resolution['sourceProof'].get('currentApplicability') == 'REQUIRED'
        and semantics.get('valid') is True and semantics.get('meaningCode') == 'NON_QUANTIFIED'
        and semantics.get('independentDurationAllowed') is False
        and semantics.get('quantitativeOccupancyAllowed') is False)
    if prepared and (quantity_policy is not None or formal_zero_preparation):
        if not _pair_valid(operation):
            return _result(operation, PENDING, ready=False, issues=['正式参考作业量及单位不成对或来源不合法，不能填造参考量。'])
        return _result(operation, NON_QUANTIFIED_REQUIRED, ready=True,
            proof=_proof(operation, NON_QUANTIFIED_REQUIRED, basis))
    return _result(operation, PENDING, ready=False, issues=['未取得正式不单独计量政策或经完整审计核验的必经非量准备裁决；不以0产能或dependencyOnly代替。'])


def resolve_operation_execution_mode(operation, *, actor=None):
    """Mode facts do not grant receipt, resource, dispatch or execution rights."""
    try:
        _verify(operation.work_order)
        if actor is not None and (not actor.is_active or actor.company_id != operation.work_order.company_id):
            return _result(operation, PENDING, ready=False, issues=['当前账号与执行工单不属于同一有效公司范围。'])
        frozen = operation.source_snapshot.get('frozenStep', {})
        app = frozen.get('applicability') or {}
        if actor is not None:
            from .operation_continuation_service import execution_mode as continuation_mode
            continued=continuation_mode(operation,actor)
            if continued is not None:return continued
        # Accepted legacy quantified source contracts sometimes predate the
        # applicability projection. Their immutable positive-processing source
        # remains authoritative; never rewrite it or require PDE maintenance.
        if (not operation.dependency_only and app.get('result') in (None, 'REQUIRED')
                and frozen.get('processingMinutes') is not None and _pair_valid(operation, required=True)
                and not frozen.get('quantityPolicy')
                and (frozen.get('capacitySemantics') or {}).get('meaningCode') != 'NON_QUANTIFIED'):
            if app:
                if actor is None:
                    return _result(operation, PENDING, ready=False, issues=['当前正式适用性核验缺少同公司读取账号。'])
                current = _current_formal_context(operation, actor)
                current_app = current.get('applicability') or {}
                if (current_app.get('result') != 'REQUIRED'
                        or current_app.get('formalApplicabilityValidated') is not True
                        or current_app.get('conditionalExecution')):
                    return _classify_basis(operation, current)
                if _requires_native_policy_read(operation):
                    return _classify_basis(operation, _load_formal_mode_basis(operation, actor))
            return _result(operation, QUANTIFIED, ready=True, proof=_quantified_proof(operation))
        if actor is None:
            return _result(operation, PENDING, ready=False, issues=['正式非量模式核验缺少当前同公司读取账号。'])
        return _classify_basis(operation, _load_formal_mode_basis(operation, actor))
    except Exception as error:
        if not isinstance(error, (PlanningBusinessError, ValidationError, ObjectDoesNotExist,
                KeyError, TypeError, ValueError, AttributeError)) and not hasattr(error, 'code'):
            raise
        return _result(operation, PENDING, ready=False,
            issues=['正式执行模式来源未通过核验：' + str(getattr(error, 'message', None) or getattr(error, 'code', None) or type(error).__name__)])


def task_execution_mode(task, *, actor=None, verify_current=True):
    """Validate frozen mode, with an optional independent current read."""
    mode = getattr(task, 'execution_mode', QUANTIFIED)
    source = task.source_snapshot
    if not isinstance(source, dict):
        _fail('OPERATION_EXECUTION_MODE_HISTORY_INCONSISTENT', '任务冻结执行模式来源结构损坏。')
    if mode == QUANTIFIED:
        from .operation_continuation_service import frozen_input_reference
        continued_reference=frozen_input_reference(task)
        if source.get('executionMode') not in (None, QUANTIFIED):
            _fail('OPERATION_EXECUTION_MODE_HISTORY_INCONSISTENT', '任务模式与冻结来源不一致。')
        if verify_current:
            current = resolve_operation_execution_mode(task.source_operation, actor=actor)
            if current['executionMode'] != QUANTIFIED:
                current['ready'] = False
                current['blockingReasons'].append('当前正式执行模式与任务冻结正量模式不一致。')
            return current
        result=_result(task.source_operation, QUANTIFIED, ready=True,
            proof=source['modeSourceProof'] if continued_reference else _quantified_proof(task.source_operation))
        if continued_reference:result['referenceWorkload']=continued_reference
        return result
    proof = source.get('modeSourceProof')
    if (mode != NON_QUANTIFIED_REQUIRED or source.get('executionMode') != mode or not isinstance(proof, dict)
            or source.get('modeSourceHash') != _hash(proof) or proof.get('contractVersion') != CONTRACT
            or proof.get('executionMode') != mode or proof.get('companyId') != task.company_id
            or proof.get('workOrderId') != task.work_order_id or proof.get('operationId') != task.source_operation_id
            or proof.get('operationSnapshotHash') != task.source_operation.snapshot_hash):
        _fail('OPERATION_EXECUTION_MODE_HISTORY_INCONSISTENT', '非量任务缺少同公司同工序的冻结正式模式证明。')
    frozen = _result(task.source_operation, mode, ready=True, proof=proof)
    if not verify_current:
        return frozen
    current = resolve_operation_execution_mode(task.source_operation, actor=actor)
    if current['executionMode'] != mode or current['modeSourceHash'] != source['modeSourceHash']:
        current['ready'] = False
        current['blockingReasons'].append('正式非量政策、适用性或来源版本与任务冻结依据已变化，请核对原正式来源。')
    return current


def source_with_mode(source, mode):
    """Only new nonquantity sources extend the legacy canonical dictionary."""
    result = deepcopy(source)
    from .operation_continuation_service import is_receipt_mode
    if (mode['executionMode'] == NON_QUANTIFIED_REQUIRED or is_receipt_mode(mode)) and mode['ready']:
        result.update(executionMode=mode['executionMode'], modeSourceHash=mode['modeSourceHash'],
            modeSourceProof=deepcopy(mode['modeSourceProof']))
    return result


def mode_display(mode):
    return {key: deepcopy(mode.get(key)) for key in ('executionMode', 'executionModeLabel',
        'quantityApplicable', 'modeSourceHash', 'referenceWorkload')}
