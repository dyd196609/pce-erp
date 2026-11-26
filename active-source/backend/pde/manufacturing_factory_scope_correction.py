"""Audited, versioned workshop corrections; original rule/EOR proofs stay exact.

This is a maintenance service, not a manufacturing execution action. A new
released rule version carries the correction. An additive audit binds exactly
which existing requirements may still reproduce their original workshop fields.
All other source, quantity, version and resource checks remain native checks.
"""
from copy import deepcopy
from hashlib import sha256

from django.db import transaction
from django.utils import timezone

from system.authorization import AuthorizationService
from system.models import Process, Workshop, OrganizationOperatingAuditRecord
from .models import EngineeringRuleDefinition, EngineeringOperationRequirement, WorkCenter
from .engineering_rule_foundation import canonical_json, specification_hash
from .production_foundation_service import (
    ProductionFoundationError, ProductionFoundationService, EngineeringLifecycleService,
    _actor_chain, _audit, _snapshot,
)

CONTRACT = 'PCE-MANUFACTURING-FACTORY-SCOPE-CORRECTION-V1'
ACTION = 'production.engineering.rule.correct_factory_scope'
PERMISSIONS = ('production.engineering.rule.create', 'production.engineering.rule.release')


def _hash(value):
    return sha256(canonical_json(value).encode('utf-8')).hexdigest()


def _fail(message):
    raise ProductionFoundationError('FACTORY_SCOPE_CORRECTION_UNPROVEN', message)


def _semantic(spec):
    value = deepcopy(spec)
    value['rulePackage'].pop('version', None)
    value['manufacturing'].pop('factoryScope', None)
    return value


def _resource_scope(rule):
    config = rule.specification['manufacturing']
    operation = Process.objects.get(pk=rule.specification['outputs'][0]['operationId'])
    center = WorkCenter.objects.get(pk=config['workCenterId'])
    return {'companyId': rule.company_id, 'operationId': operation.pk,
        'operationCompanyId': operation.company_id, 'operationWorkshopId': operation.workshop_id,
        'operationWorkCenterId': operation.work_center_id, 'operationUomId': operation.calculation_uom_id,
        'workCenterId': center.pk, 'workCenterCompanyId': center.company_id,
        'workCenterWorkshopId': center.workshop_id,
        'workCenterEffectiveFrom': center.effective_from.isoformat() if center.effective_from else None,
        'workCenterEffectiveTo': center.effective_to.isoformat() if center.effective_to else None}


def _maintenance_proofs(rule, audit_ids, old_workshop, new_workshop):
    """Require the original formal resource moves, never a guessed name map."""
    scope = _resource_scope(rule)
    expected = {'Process': scope['operationId'], 'WorkCenter': scope['workCenterId']}
    records = list(OrganizationOperatingAuditRecord.objects.filter(pk__in=audit_ids))
    if len(records) != 2 or {r.target_type for r in records} != set(expected):
        _fail('纠正必须引用工序与工作中心各自唯一的正式车间维护审计。')
    for row in records:
        before, after = row.before_snapshot, row.after_snapshot
        if (row.organization_id != rule.company_id or row.target_id != expected[row.target_type]
            or row.action_code != 'production.master_data.resource.maintain'
            or before.get('state', {}).get('workshop_id') != old_workshop
            or after.get('state', {}).get('workshop_id') != new_workshop
            or after.get('factSource') != 'server' or not after.get('authorization', {}).get('allowed')):
            _fail('车间纠正与原正式维护审计的对象、公司或前后归属不一致。')
    return {str(row.pk): _hash({'before': row.before_snapshot, 'after': row.after_snapshot,
        'actorId': row.actor_id, 'action': row.action_code}) for row in records}


def _authorize(user, rule, approval_reference):
    if not user or not user.is_active or user.company_id != rule.company_id:
        _fail('正式纠正必须由同公司有效维护账号办理。')
    decisions = [AuthorizationService.decide(user=user, action_code=action,
        organization_id=rule.company_id, business_object={'organizationId': rule.company_id,
            'entity': 'engineering-rule-definitions', 'id': rule.pk,
            'approvalReference': approval_reference}) for action in PERMISSIONS]
    if not all(d.get('allowed') for d in decisions):
        _fail('当前账号不具备原规则创建及发布权限，不能办理来源归属纠正。')
    return {'allowed': True, 'requiredPermissions': list(PERMISSIONS), 'decisions': decisions}, _actor_chain(user)


def read_correction(rule, *, read_cache=None):
    from .operation_requirement_service import _read_once, _requirement_read_cache
    cache = _requirement_read_cache(read_cache, rule.company_id)
    return _read_once(cache, ('factory_scope_correction', rule.company_id, rule.pk,
        _hash(_snapshot(rule))), lambda: _read_correction_uncached(rule))


def _read_correction_uncached(rule):
    records = list(OrganizationOperatingAuditRecord.objects.filter(organization_id=rule.company_id,
        target_type='EngineeringRuleDefinition', target_id=rule.pk, action_code=ACTION).order_by('pk'))
    if not records:
        return None
    if len(records) != 1:
        _fail('同一原规则存在多个归属纠正，必须先核定正式沿革。')
    audit = records[0]
    after, before = audit.after_snapshot, audit.before_snapshot
    state = after.get('state', {})
    proof = state.get('proof', {})
    if (after.get('importContext') != {'contractVersion': CONTRACT}
        or before.get('importContext') != after.get('importContext')
        or before.get('factSource') != 'server' or after.get('factSource') != 'server'
        or state.get('contractVersion') != CONTRACT or state.get('proofHash') != _hash(proof)
        or proof.get('originalRule') != _snapshot(rule)
        or before.get('state') != {'originalRule': proof.get('originalRule')}
        or not proof.get('approvalReference') or not proof.get('reason')
        or audit.reason != proof.get('reason')
        or after.get('authorization') != before.get('authorization')
        or after.get('executionChain') != before.get('executionChain')
        or not after.get('authorization', {}).get('allowed')
        or after.get('authorization', {}).get('requiredPermissions') != list(PERMISSIONS)
        or proof.get('actorId') != audit.actor_id
        or after.get('executionChain', {}).get('account') != audit.actor.username
        or not all(after.get('executionChain', {}).get(k) for k in ('employeeId','positionId','responsibilityId'))):
        _fail('规则归属纠正的原规则、授权、责任、审计或证明不一致。')
    target = EngineeringRuleDefinition.objects.filter(pk=proof.get('targetRule', {}).get('id')).first()
    if (not target or target.company_id != rule.company_id or target.status != 'released'
        or target.rule_code != rule.rule_code or target.version == rule.version
        or _snapshot(target) != proof['targetRule']
        or _semantic(target.specification) != _semantic(rule.specification)
        or target.specification['manufacturing']['factoryScope'] != proof.get('correctedScope')
        or _resource_scope(rule) != proof.get('resourceScope')):
        _fail('纠正版本、当前正式资源或原数量与单位语义已变化。')
    old_scope = rule.specification['manufacturing']['factoryScope']
    if _maintenance_proofs(rule, [int(k) for k in proof['maintenanceProofs']],
        old_scope['workshopId'], proof['correctedScope']['workshopId']) != proof['maintenanceProofs']:
        _fail('纠正引用的原维护证明已变化。')
    from .manufacturing_rule_configuration import publication_config_validation
    current = publication_config_validation(target, require_released=True)
    if current != proof['targetManufacturing']:
        _fail('纠正版本的完整制造资源证明已变化，不能沿用旧承接。')
    for key, value in proof['publicationAudits'].items():
        row = OrganizationOperatingAuditRecord.objects.filter(pk=int(key), target_id=target.pk,
            target_type='EngineeringRuleDefinition', organization_id=rule.company_id).first()
        if not row or _hash({'before': row.before_snapshot, 'after': row.after_snapshot,
            'actorId': row.actor_id, 'action': row.action_code}) != value:
            _fail('纠正版本缺少原生创建、评审或发布审计。')
    return {'auditId': audit.pk, 'proofHash': state['proofHash'], 'proof': proof,
        'targetRule': target, 'approvalReference': proof['approvalReference']}


def effective_config(rule, config, *, read_cache=None):
    correction = read_correction(rule, read_cache=read_cache)
    if correction is None:
        return config, None
    value = deepcopy(config)
    value['factoryScope'] = correction['proof']['correctedScope']
    return value, correction


def historical_snapshot(snapshot, *, rule, requirement, correction):
    """Only maintenance-proven resource fields reproduce a bound old proof."""
    if correction is None or requirement is None:
        return snapshot
    saved = EngineeringOperationRequirement.objects.filter(pk=requirement.pk,
        calculation__company_id=rule.company_id).select_related('calculation','audit_record','source_detail').first()
    enrollment = correction['proof']['historicalRequirements'].get(str(requirement.pk))
    if (not saved or not enrollment or _snapshot(saved) != _snapshot(requirement)
        or _hash(_snapshot(saved)) != enrollment['recordHash']
        or saved.source_detail.rule_id != rule.pk
        or saved.audit_record_id != enrollment['generationAuditId']
        or _hash(saved.audit_record.after_snapshot) != enrollment['generationAuditHash']
        or saved.audit_record.after_snapshot.get('state', {}).get('trace') != saved.calculation.trace):
        _fail('原需求未被本次正式纠正精确承接，或原生成事实已变化。')
    original = saved.calculation.trace['sourceSnapshot']['manufacturing']
    if _hash(original) != enrollment['manufacturingHash']:
        _fail('原制造冻结证明不一致。')
    value = deepcopy(snapshot)
    for key in ('factoryScope','operation','workCenter'):
        value[key]['workshopId'] = original[key]['workshopId']
    move = OrganizationOperatingAuditRecord.objects.get(
        pk__in=[int(k) for k in correction['proof']['maintenanceProofs']], target_type='WorkCenter')
    for field, wire in (('effective_from','effectiveFrom'), ('effective_to','effectiveTo')):
        before = move.before_snapshot['state'].get(field)
        after = move.after_snapshot['state'].get(field)
        if original['workCenter'][wire] != before or snapshot['workCenter'][wire] != after:
            _fail('工作中心原有效期与正式归属维护前后事实不一致。')
        value['workCenter'][wire] = before
    if value != original:
        _fail('除经批准的车间归属外，来源、版本、资源、数量或上下文仍不一致。')
    return value


@transaction.atomic
def correct_factory_scope(*, user, rule_id, expected_rule_hash, expected_resource_scope,
        target_workshop_id, target_version, maintenance_audit_ids, approval_reference, reason, idempotency_key):
    """Create/review/release a successor via native services, then add a proof."""
    reason, approval_reference, idempotency_key = (str(v or '').strip()
        for v in (reason, approval_reference, idempotency_key))
    if not all((reason, approval_reference, idempotency_key)) or len(reason) > 300:
        _fail('纠正必须提供批准引用、幂等键及不超过300字的真实原因。')
    rule = EngineeringRuleDefinition.objects.select_for_update().get(pk=rule_id)
    decision, chain = _authorize(user, rule, approval_reference)
    previous = read_correction(rule)
    if previous:
        proof = previous['proof']
        if (proof['idempotencyKey'] != idempotency_key or proof['approvalReference'] != approval_reference
            or proof['reason'] != reason or proof['correctedScope']['workshopId'] != target_workshop_id
            or proof['targetRule']['version'] != target_version
            or _hash(proof['originalRule']) != expected_rule_hash
            or proof['resourceScope'] != expected_resource_scope):
            _fail('既有纠正与本次意图不一致，禁止重复覆盖。')
        return {'auditId': previous['auditId'], 'targetRuleId': previous['targetRule'].pk,
            'proofHash': previous['proofHash'], 'idempotent': True}
    if (rule.status != 'released' or _hash(_snapshot(rule)) != expected_rule_hash
        or _resource_scope(rule) != expected_resource_scope):
        _fail('原规则或当前资源与获批纠正的预期事实不一致。')
    old_scope = rule.specification['manufacturing']['factoryScope']
    scope = {'companyId': rule.company_id, 'workshopId': target_workshop_id}
    resources = _resource_scope(rule)
    if (type(target_workshop_id) is not int or old_scope == scope
        or resources['operationCompanyId'] != rule.company_id or resources['workCenterCompanyId'] != rule.company_id
        or resources['operationWorkshopId'] != target_workshop_id
        or resources['workCenterWorkshopId'] != target_workshop_id
        or not Workshop.objects.filter(pk=target_workshop_id, company_id=rule.company_id, is_active=True).exists()):
        _fail('目标车间必须与同公司现行工序及工作中心的正式归属完全一致。')
    maintenance = _maintenance_proofs(rule, maintenance_audit_ids, old_scope['workshopId'], target_workshop_id)
    spec = deepcopy(rule.specification)
    spec['rulePackage']['version'] = target_version
    spec['manufacturing']['factoryScope'] = scope
    payload = {k: getattr(rule,k) for k in ('company_id','rule_code','rule_name','rule_kind')}
    payload.update(version=target_version, specification=spec,
        effective_from=timezone.now().date().isoformat(), effective_to=None)
    created = ProductionFoundationService.write('engineering-rule-definitions', user=user, payload=payload,
        idempotency_key=idempotency_key+':version', source_identity={'sourceSystem': CONTRACT,
            'sourceType': 'INTERNAL', 'sourceObjectType': ACTION, 'externalId': idempotency_key,
            'sourceFingerprint': _hash({'rule':expected_rule_hash,'scope':scope,'approval':approval_reference}),
            'auditMetadata': {'contractVersion':CONTRACT,'approvalReference':approval_reference,'reason':reason}})
    target_id = created['row']['id']
    publications = [created['auditId']]
    for status in ('reviewed','released'):
        result = EngineeringLifecycleService.transition('engineering-rule-definitions', object_id=target_id,
            target_status=status, user=user, reason=reason, idempotency_key=idempotency_key+':'+status)
        publications.append(result['auditId'])
    target = EngineeringRuleDefinition.objects.get(pk=target_id)
    from .manufacturing_rule_configuration import publication_config_validation
    target_manufacturing = publication_config_validation(target, require_released=True)
    requirements = list(EngineeringOperationRequirement.objects.filter(source_detail__rule=rule)
        .select_related('calculation','audit_record','source_detail'))
    enrollment = {str(req.pk): {'recordHash':_hash(_snapshot(req)), 'generationAuditId':req.audit_record_id,
        'generationAuditHash':_hash(req.audit_record.after_snapshot),
        'manufacturingHash':_hash(req.calculation.trace['sourceSnapshot']['manufacturing'])} for req in requirements}
    proof = {'originalRule':_snapshot(rule), 'targetRule':_snapshot(target), 'correctedScope':scope,
        'resourceScope':resources, 'maintenanceProofs':maintenance, 'historicalRequirements':enrollment,
        'targetManufacturing':target_manufacturing, 'approvalReference':approval_reference,
        'reason':reason, 'idempotencyKey':idempotency_key, 'actorId':user.pk,
        'publicationAudits':{str(a.pk):_hash({'before':a.before_snapshot,'after':a.after_snapshot,
            'actorId':a.actor_id,'action':a.action_code}) for a in OrganizationOperatingAuditRecord.objects.filter(pk__in=publications)}}
    audit = _audit(user=user, organization_id=rule.company_id, action_code=ACTION, instance=rule,
        before={'originalRule':proof['originalRule']},
        after={'contractVersion':CONTRACT,'proof':proof,'proofHash':_hash(proof)}, reason=reason,
        authorization=decision, execution_chain=chain, audit_context={'contractVersion':CONTRACT})
    from .operation_requirement_service import _validate_requirement
    for requirement in requirements:
        _validate_requirement(requirement, rule.company_id, user=user)
    return {'auditId':audit.pk, 'targetRuleId':target.pk, 'proofHash':_hash(proof),
        'historicalRequirementIds':[req.pk for req in requirements], 'idempotent':False}
