"""Append-only correction over the existing EOR, audit and state contracts.

Historical requirements and calculation evidence are never updated. Current
disposition belongs to the shared business-state projection, with a proven
one-to-one replacement and the native calculation supersedes foreign key.
"""
from copy import deepcopy
import re

from django.db import transaction
from system.models import Company, OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import record_projected_business_transition

from .models import EngineeringOperationRequirement
from .operation_requirement_service import (
    EXECUTE, OperationRequirementError, _authorize, _digest, _executor, _fail,
    _key, _proof_record_hash, _requirement_read_cache,
)
from .production_foundation_service import _audit, _snapshot

CONTRACT = 'PCE-EOR-CORRECTION-V1'
OBJECT_TYPE = 'EngineeringOperationRequirement'
EFFECTIVE = 'EFFECTIVE'
SUPERSEDED = 'SUPERSEDED'
ALLOWED = (('', EFFECTIVE), (EFFECTIVE, SUPERSEDED))


def _positive(value):
    return type(value) is int and value > 0


def _hash(value):
    try:
        return _digest(value)
    except (TypeError, ValueError):
        _fail('CORRECTION_RELATIONSHIP_UNPROVEN', '纠正证据必须具备可验证的正式JSON内容')


def _load(pk, company_id, *, lock=False):
    rows = EngineeringOperationRequirement.objects.select_related('calculation', 'source_detail__rule')
    if lock:
        rows = rows.select_for_update()
    row = rows.filter(pk=pk, calculation__company_id=company_id).first()
    if not row:
        _fail('CORRECTION_SOURCE_MISMATCH', '纠正来源必须为当前公司的正式工序需求')
    return row


def _identity(req):
    return {'operationRequirementId': req.pk, 'calculationId': req.calculation_id,
            'generationKey': req.generation_key, 'sourceHash': req.source_hash, 'inputHash': req.input_hash,
            'recordHash': _hash(_snapshot(req)), 'ruleId': req.source_detail.rule_id,
            'ruleVersion': req.source_detail.rule_version}


def _relationship(old, new, company_id):
    if (old.pk == new.pk or old.calculation.company_id != company_id
            or new.calculation.company_id != company_id
            or any(not _positive(getattr(old, name)) for name in (
                'source_calculation_id', 'source_fact_id', 'operation_id', 'uom_id'))
            or new.calculation.supersedes_id != old.calculation_id
            or old.calculation_id == new.calculation_id
            or any(getattr(old, name) != getattr(new, name) for name in (
                'source_calculation_id', 'source_fact_id', 'operation_id', 'uom_id',
                'workload_quantity', 'quantity_basis', 'basis_quantity', 'basis_uom_id'))
            or not old.generation_key or not new.generation_key or old.generation_key == new.generation_key):
        _fail('CORRECTION_RELATIONSHIP_UNPROVEN', '替代关系必须保留同一来源、工序、单位及数量，并具有独立运行和正式替代FK')
    expected_source = _identity(old)
    trace = new.calculation.trace
    snapshot = trace.get('sourceSnapshot') if isinstance(trace, dict) else None
    source = snapshot.get('sourceReplacement') if isinstance(snapshot, dict) else None
    if _hash(source) != _hash(expected_source):
        _fail('CORRECTION_RELATIONSHIP_UNPROVEN', '新运行的正式来源替代快照与原不可变需求不一致')
    specification = new.source_detail.rule.specification
    config = specification.get('manufacturing') if isinstance(specification, dict) else None
    route = config.get('routingContext') if isinstance(config, dict) else None
    if not isinstance(route, dict) or not all(_positive(route.get(key)) for key in (
            'routingId', 'routingVersionId', 'routingStepId')):
        _fail('CORRECTION_RELATIONSHIP_UNPROVEN', '替代规则必须启用正式路线版本及步骤校验')
    manufacturing = snapshot.get('manufacturing')
    runtime = manufacturing.get('routingContext') if isinstance(manufacturing, dict) else None
    context = runtime.get('context') if isinstance(runtime, dict) else None
    source_calculation = new.source_calculation
    source_fact_trace = new.source_fact.trace if isinstance(new.source_fact.trace, dict) else {}
    base_id = (source_calculation.origin_calculation_id if source_calculation.scope == 'fact_extension'
               else source_calculation.pk)
    keys = ('organizationId', 'salesOrderItemId', 'orderEngineeringInstanceId',
            'orderEngineeringBaselineId', 'engineeringCalculationId', 'bomVersionId')
    runtime_ids = ('sourceEngineeringCalculationId', 'sourceFactCalculationId', 'sourceFactId',
                   'manufacturingOutputId', 'sequence', 'operationId', 'workCenterId',
                   'standardCapacityId', 'productTypeId', 'uomId')
    if (not isinstance(runtime, dict) or runtime.get('contractVersion') != route.get('contractVersion')
            or runtime.get('factSource') != 'server' or not isinstance(context, dict)
            or set(context) != set(keys) or any(not _positive(context.get(key)) for key in keys)
            or any(not _positive(runtime.get(key)) for key in runtime_ids)
            or any(type(runtime.get(key)) is not int or runtime[key] != route[key]
                   for key in ('routingId', 'routingVersionId', 'routingStepId'))
            or context['organizationId'] != company_id
            or context['salesOrderItemId'] != new.calculation.sales_order_item_id
            or context['orderEngineeringInstanceId'] != new.calculation.engineering_instance_id
            or context['engineeringCalculationId'] != base_id
            or context['orderEngineeringBaselineId'] != source_fact_trace.get('baselineId')
            or runtime.get('sourceEngineeringCalculationId') != base_id
            or runtime.get('sourceFactCalculationId') != new.source_calculation_id
            or runtime.get('sourceFactId') != new.source_fact_id
            or runtime.get('operationId') != new.operation_id
            or runtime.get('workCenterId') != new.work_center_id
            or runtime.get('standardCapacityId') != new.standard_capacity_id
            or runtime.get('uomId') != new.uom_id):
        _fail('CORRECTION_RELATIONSHIP_UNPROVEN', '纠正审计必须对应新运行的完整正式路线来源及六项工程身份')
    hashes = runtime.get('formalSourceHashes')
    if (not isinstance(hashes, dict) or not hashes
            or any(not isinstance(value, str) or re.fullmatch(r'[0-9a-fA-F]{64}', value) is None
                   for value in hashes.values())):
        _fail('CORRECTION_RELATIONSHIP_UNPROVEN', '正式路线来源必须保留完整可验证的冻结来源Hash')
    return {'companyId': company_id, 'old': expected_source, 'new': _identity(new),
            'sourceCalculationId': old.source_calculation_id, 'sourceFactId': old.source_fact_id,
            'operationId': old.operation_id, 'uomId': old.uom_id,
            'requirementQuantity': str(old.workload_quantity), 'routingContext': deepcopy(runtime)}


class _LifecycleReadProof:
    """Unpublished evidence for one fully checked replacement pair.

    This collector is created only for the existing typed atomic read cache.
    Writers use the original uncached path. Its local memos avoid re-reading
    the same immutable relationship/history while completing that pair; no
    partial or failed pair becomes a consumable lifecycle result.
    """

    def __init__(self):
        self.relationships, self.histories, self.models = {}, {}, {}

    def remember(self, row, *, actor=False):
        self.models[id(row)] = (row, actor)

    def remember_requirement(self, row):
        for model in (row, row.calculation, row.source_detail, row.source_detail.rule):
            self.remember(model)

    def fingerprint(self):
        values = []
        for row, actor in self.models.values():
            # Historical audit actors deliberately defer credentials. Only the
            # identity fields actually consumed by _history belong to this proof.
            value = ({'id': row.pk, 'companyId': row.company_id, 'username': row.username}
                     if actor else _proof_record_hash(row))
            values.append(value)
        return _hash(values)


def _prove_relationship(saved, company_id, *, _proofs=None):
    if not isinstance(saved, dict) or not isinstance(saved.get('old'), dict) or not isinstance(saved.get('new'), dict):
        _fail('CORRECTION_RELATIONSHIP_UNPROVEN', '生命周期缺少完整正式替代关系')
    ids = [saved[role].get('operationRequirementId') for role in ('old', 'new')]
    if not all(_positive(pk) for pk in ids):
        _fail('CORRECTION_RELATIONSHIP_UNPROVEN', '替代关系必须使用精确正式需求身份')
    key = (company_id, _hash(saved)) if _proofs is not None else None
    if _proofs is not None and key in _proofs.relationships:
        expected, old, new = _proofs.relationships[key]
        return deepcopy(expected), old, new
    old, new = (_load(pk, company_id) for pk in ids)
    expected = _relationship(old, new, company_id)
    if _hash(saved) != _hash(expected):
        _fail('CORRECTION_RELATIONSHIP_UNPROVEN', '替代记录、GenerationKey或原完整行Hash证明失败')
    if _proofs is not None:
        _proofs.remember_requirement(old)
        _proofs.remember_requirement(new)
        _proofs.remember(new.source_calculation)
        _proofs.remember(new.source_fact)
        _proofs.relationships[key] = (deepcopy(expected), old, new)
    return expected, old, new


def _history(req, company_id, *, _proofs=None):
    key = (company_id, req.pk)
    if _proofs is not None and key in _proofs.histories:
        return deepcopy(_proofs.histories[key])
    rows = list(BusinessStateTransition.objects.filter(
        object_type=OBJECT_TYPE, object_id=req.pk).order_by('version', 'pk'))
    if not rows:
        return []
    result, source = [], ''
    for version, row in enumerate(rows, 1):
        match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', row.audit_reference or '')
        if (row.version != version or row.source_state != source
                or (row.source_state, row.target_state) not in ALLOWED
                or row.action_code != EXECUTE or not str(row.reason).strip() or not match):
            _fail('CORRECTION_HISTORY_UNPROVEN', '工序需求投影状态链缺失、重复或不符合正式合同')
        audit = OrganizationOperatingAuditRecord.objects.select_related('actor').defer('actor__password').filter(pk=int(match.group(1))).first()
        if (not audit or audit.organization_id != company_id or audit.actor_id != row.operator_id
                or audit.actor.company_id != company_id or audit.action_code != EXECUTE
                or audit.target_type != OBJECT_TYPE or audit.target_id != req.pk):
            _fail('CORRECTION_HISTORY_UNPROVEN', '状态转换必须引用同公司、同对象、同操作人的真实审计')
        before, after = audit.before_snapshot, audit.after_snapshot
        if (not isinstance(before, dict) or not isinstance(after, dict)
                or not isinstance(before.get('state'), dict) or not isinstance(after.get('state'), dict)
                or before['state'].get('status') != row.source_state
                or after['state'].get('status') != row.target_state
                or after['state'].get('contractVersion') != CONTRACT
                or after.get('factSource') != 'server'
                or not isinstance(after.get('importContext'), dict)
                or after['importContext'].get('contractVersion') != CONTRACT):
            _fail('CORRECTION_HISTORY_UNPROVEN', '投影状态与真实审计前后状态或合同不一致')
        authorization, chain = after.get('authorization'), after.get('executionChain')
        if (not isinstance(authorization, dict) or authorization.get('allowed') is not True
                or authorization.get('actionCode') != EXECUTE
                or str(authorization.get('organizationId')) != str(company_id)
                or not isinstance(chain, dict) or chain.get('account') != audit.actor.username
                or any(not _positive(chain.get(key)) for key in ('employeeId', 'positionId', 'responsibilityId'))):
            _fail('CORRECTION_HISTORY_UNPROVEN', '投影审计缺少正式授权与操作责任链')
        relationship, _, _ = _prove_relationship(after['state'].get('relationship'), company_id, _proofs=_proofs)
        if req.pk not in {relationship['old']['operationRequirementId'], relationship['new']['operationRequirementId']}:
            _fail('CORRECTION_HISTORY_UNPROVEN', '审计替代关系未引用当前工序需求')
        if row.target_state == SUPERSEDED and req.pk != relationship['old']['operationRequirementId']:
            _fail('CORRECTION_HISTORY_UNPROVEN', '已替代状态只能属于被替代的原正式需求')
        if _proofs is not None:
            _proofs.remember(row)
            _proofs.remember(audit)
            _proofs.remember(audit.actor, actor=True)
        result.append({'id': row.pk, 'version': row.version, 'sourceState': row.source_state,
            'targetState': row.target_state, 'actionCode': row.action_code, 'operatorId': row.operator_id,
            'reason': row.reason, 'auditId': audit.pk, 'auditReference': row.audit_reference,
            'timestamp': row.timestamp.isoformat(), 'relationship': relationship})
        source = row.target_state
    if _proofs is not None:
        _proofs.histories[key] = deepcopy(result)
    return result


def _complete_pair(relationship, old, new, company_id, *, _proofs=None):
    old_history = _history(old, company_id, _proofs=_proofs)
    new_history = _history(new, company_id, _proofs=_proofs)
    if ([(row['sourceState'], row['targetState']) for row in old_history] != list(ALLOWED)
            or [(row['sourceState'], row['targetState']) for row in new_history] != [('', EFFECTIVE)]
            or old_history[-1]['relationship'] != relationship or new_history[0]['relationship'] != relationship):
        _fail('CORRECTION_HISTORY_UNPROVEN', '正式替代必须具有原需求两段、新需求一段完整投影状态及相同替代证明')
    return old_history, new_history


def _lifecycle_cache_key(req, company_id, cache):
    return ('requirement_lifecycle', company_id, cache.user_id, req.pk,
        _hash(_snapshot(req)), _hash(_snapshot(req.calculation)),
        _hash(_snapshot(req.source_detail)), _hash(_snapshot(req.source_detail.rule)))


def _lifecycle_result(old, new, selected, *, superseded):
    return {'contractVersion': CONTRACT, 'statusCode': SUPERSEDED if superseded else EFFECTIVE,
        'statusLabel': '已被替代' if superseded else '有效需求',
        'replacementRequirementId': new.pk if superseded else None,
        'supersedesRequirementId': old.pk if not superseded else None,
        'history': selected, 'statusTransitionCount': len(selected), 'factSource': 'server'}


def requirement_lifecycle(req, company_id, *, read_cache=None):
    """Read current disposition from proven shared state/audit facts only."""
    if not _positive(req.pk) or not _positive(company_id) or req.calculation.company_id != company_id:
        _fail('CORRECTION_SOURCE_MISMATCH', '需求生命周期必须属于当前公司')
    cache = _requirement_read_cache(read_cache, company_id)
    read_epoch = cache._write_epoch if cache is not None else None
    cache_key = None
    if cache is not None:
        cache_key = _lifecycle_cache_key(req, company_id, cache)
        if cache_key in cache:
            saved = cache[cache_key]
            if saved is None:
                return None
            try:
                valid = (saved['proof'].fingerprint() == saved['modelHash']
                         and _hash(saved['results']) == saved['resultHash'])
            except (AttributeError, KeyError, TypeError, ValueError, OperationRequirementError):
                valid = False
            if valid:
                return deepcopy(saved['results'][req.pk])
            # Internal models follow the existing read-only ORM-reference
            # contract. Pollution invalidates every dependent request proof.
            cache.invalidate_proofs()
    proofs = _LifecycleReadProof() if cache is not None else None
    history = _history(req, company_id, _proofs=proofs)
    if not history:
        if cache is not None:
            cache[cache_key] = None
        return None
    relationship, old, new = _prove_relationship(history[-1]['relationship'], company_id, _proofs=proofs)
    old_history, new_history = _complete_pair(relationship, old, new, company_id, _proofs=proofs)
    results = {old.pk: _lifecycle_result(old, new, old_history, superseded=True),
               new.pk: _lifecycle_result(old, new, new_history, superseded=False)}
    if cache is not None and cache.is_current(company_id) and cache._write_epoch == read_epoch:
        # Both endpoint results are published together, only after the original
        # full pair contract succeeds. Same-connection writes clear this cache.
        saved = {'proof': proofs, 'modelHash': proofs.fingerprint(),
                 'results': deepcopy(results), 'resultHash': _hash(results)}
        for endpoint in (old, new):
            cache[_lifecycle_cache_key(endpoint, company_id, cache)] = saved
    return deepcopy(results[req.pk])


def require_effective_requirement(req, company_id, *, read_cache=None):
    lifecycle = requirement_lifecycle(req, company_id, read_cache=read_cache)
    if lifecycle is None and req.calculation.supersedes_id:
        _fail('CORRECTION_HISTORY_UNPROVEN', '替代需求缺少完整正式生命周期，不允许再次执行或分配')
    if lifecycle is not None and lifecycle['statusCode'] == SUPERSEDED:
        _fail('OPERATION_REQUIREMENT_SUPERSEDED', '原工序需求已由新的正式需求替代，不允许再次执行或分配',
              replacementRequirementId=lifecycle['replacementRequirementId'])
    return lifecycle


def _project(req, source, target, relationship, *, user, decision, chain, reason, binding=None):
    state = {'contractVersion': CONTRACT, 'status': target, 'relationship': relationship}
    if binding is not None:
        state['requestBinding'] = binding
    audit = _audit(user=user, organization_id=user.company_id, action_code=EXECUTE, instance=req,
        before={'contractVersion': CONTRACT, 'status': source, 'relationship': relationship}, after=state,
        reason=reason, authorization=decision, execution_chain=chain, audit_context={'contractVersion': CONTRACT})
    record_projected_business_transition(object_type=OBJECT_TYPE, object_id=req.pk,
        source_state=source, target_state=target, action_code=EXECUTE, operator=user,
        reason=reason, audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions=ALLOWED)


def _payload(replacements):
    if (not isinstance(replacements, list) or not replacements
            or any(not isinstance(row, dict) or set(row) != {'operationRequirementId', 'ruleId'}
                   or not _positive(row.get('operationRequirementId')) or not _positive(row.get('ruleId'))
                   for row in replacements)):
        _fail('CORRECTION_PAYLOAD_INVALID', '纠正批次必须明确正式需求及新规则正整数身份')
    if len({row['operationRequirementId'] for row in replacements}) != len(replacements):
        _fail('CORRECTION_PAYLOAD_INVALID', '同一批次不得重复替代同一原需求')
    return sorted((dict(row) for row in replacements), key=lambda row: row['operationRequirementId'])


def _binding(company_id, request_key, payload_hash):
    rows = list(OrganizationOperatingAuditRecord.objects.filter(organization_id=company_id,
        action_code=EXECUTE, target_type=OBJECT_TYPE,
        after_snapshot__importContext__contractVersion=CONTRACT,
        after_snapshot__state__requestBinding__clientIdempotencyKey=request_key).order_by('pk'))
    if not rows:
        return None
    if len(rows) != 1:
        _fail('CORRECTION_IDEMPOTENCY_CONFLICT', '纠正批次的正式幂等绑定不唯一')
    audit = rows[0]
    binding = audit.after_snapshot['state']['requestBinding']
    if (not isinstance(binding, dict) or binding.get('contractVersion') != CONTRACT or binding.get('payloadHash') != payload_hash
            or not isinstance(binding.get('replacements'), list)):
        _fail('CORRECTION_IDEMPOTENCY_CONFLICT', '幂等键已绑定不同的正式纠正批次')
    lifecycle = requirement_lifecycle(_load(audit.target_id, company_id), company_id)
    if not lifecycle or audit.pk not in {row['auditId'] for row in lifecycle['history']}:
        _fail('CORRECTION_HISTORY_UNPROVEN', '批次幂等绑定没有匹配的真实状态与替代审计')
    return binding


class OperationRequirementCorrectionService:
    @classmethod
    @transaction.atomic
    def correct(cls, *, user, replacements, idempotency_key, reason):
        from .operation_requirement_service import OperationRequirementService, _generation_context, _validate_requirement

        decision, chain = _authorize(user, EXECUTE), _executor(user)
        request_key = _key(idempotency_key)
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 240:
            _fail('REASON_REQUIRED', '纠正必须提供不超过240字的正式办理原因')
        reason = reason.strip()
        payload = _payload(replacements)
        payload_hash = _digest({'contractVersion': CONTRACT, 'companyId': user.company_id, 'replacements': payload})
        Company.objects.select_for_update().get(pk=user.company_id)
        bound = _binding(user.company_id, request_key, payload_hash)
        if bound is not None:
            expected = []
            for row in bound['replacements']:
                if (not isinstance(row, dict) or set(row) != {'operationRequirementId', 'replacementRequirementId', 'ruleId'}
                        or not all(_positive(value) for value in row.values())):
                    _fail('CORRECTION_HISTORY_UNPROVEN', '批次绑定缺少精确的新旧需求及规则身份')
                old = _load(row['operationRequirementId'], user.company_id, lock=True)
                new = _load(row['replacementRequirementId'], user.company_id)
                relationship = _relationship(old, new, user.company_id)
                _complete_pair(relationship, old, new, user.company_id)
                if new.source_detail.rule_id != row['ruleId']:
                    _fail('CORRECTION_IDEMPOTENCY_CONFLICT', '批次新需求没有引用已绑定的精确规则')
                _validate_requirement(new, user.company_id)
                expected.append({'operationRequirementId': old.pk, 'ruleId': new.source_detail.rule_id})
            if expected != payload:
                _fail('CORRECTION_IDEMPOTENCY_CONFLICT', '正式批次绑定与本次完整输入不一致')
            return {'contractVersion': CONTRACT, 'replacements': bound['replacements'],
                'operationRequirementIds': [row['replacementRequirementId'] for row in bound['replacements']],
                'idempotent': True, 'businessWriteCount': 0, 'auditWriteCount': 0, 'stateTransitionWriteCount': 0,
                'factSource': 'server'}

        prepared = []
        for row in payload:
            old = _load(row['operationRequirementId'], user.company_id, lock=True)
            if requirement_lifecycle(old, user.company_id) is not None:
                _fail('CORRECTION_ALREADY_MARKED', '已存在正式生命周期的需求必须使用原纠正批次重放')
            if old.plan_allocations.exists():
                _fail('CORRECTION_ALREADY_ALLOCATED', '已形成计划分配的需求不允许在本纠正合同内替代')
            _validate_requirement(old, user.company_id)
            context = _generation_context(user.company_id, old.source_calculation_id, old.source_fact_id,
                row['ruleId'], evaluate=True, supersedes_requirement_id=old.pk)
            if context['result']['value'] != str(old.workload_quantity):
                # Compare numbers without accepting a quantity correction under this contract.
                from decimal import Decimal
                if Decimal(context['result']['value']) != old.workload_quantity:
                    _fail('CORRECTION_SOURCE_MISMATCH', '路线版本纠正不得改变正式作业量')
            prepared.append((old, row['ruleId'], _digest(_snapshot(old))))

        results, pairs = [], []
        native_audits = 0
        for old, rule_id, old_hash in prepared:
            result = OperationRequirementService.generate(user=user,
                source_calculation_id=old.source_calculation_id, source_fact_id=old.source_fact_id, rule_id=rule_id,
                supersedes_requirement_id=old.pk, reason=reason,
                idempotency_key='eor-correction:' + _digest({'batch': request_key, 'oldRequirementId': old.pk}))
            new = _load(result['operationRequirementId'], user.company_id)
            if result.get('idempotent') or requirement_lifecycle(new, user.company_id) is not None:
                _fail('CORRECTION_ALREADY_MARKED', '新纠正批次不得复用未绑定或已有生命周期的替代运行')
            relationship = _relationship(old, new, user.company_id)
            if _digest(_snapshot(_load(old.pk, user.company_id))) != old_hash:
                _fail('CORRECTION_SOURCE_MISMATCH', '纠正过程中原不可变需求发生变化')
            pairs.append((old, new, relationship))
            results.append({'operationRequirementId': old.pk, 'replacementRequirementId': new.pk, 'ruleId': rule_id})
            native_audits += result['auditWriteCount']

        binding = {'contractVersion': CONTRACT, 'clientIdempotencyKey': request_key,
                   'payloadHash': payload_hash, 'replacements': results}
        for index, (old, new, relationship) in enumerate(pairs):
            _project(old, '', EFFECTIVE, relationship, user=user, decision=decision, chain=chain, reason=reason)
            _project(old, EFFECTIVE, SUPERSEDED, relationship, user=user, decision=decision, chain=chain,
                     reason=reason, binding=binding if index == 0 else None)
            _project(new, '', EFFECTIVE, relationship, user=user, decision=decision, chain=chain, reason=reason)
        for old, new, relationship in pairs:
            _complete_pair(relationship, old, new, user.company_id)
            _validate_requirement(new, user.company_id)
        return {'contractVersion': CONTRACT, 'replacements': results,
            'operationRequirementIds': [row['replacementRequirementId'] for row in results], 'idempotent': False,
            'businessWriteCount': len(pairs) * 3, 'auditWriteCount': native_audits + len(pairs) * 3,
            'stateTransitionWriteCount': len(pairs) * 7, 'factSource': 'server'}


__all__ = ['OperationRequirementCorrectionService', 'requirement_lifecycle', 'require_effective_requirement']
