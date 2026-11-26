"""Read-only proof for explicitly declared, versioned workload compositions.

Declarations are decisions in the existing engineering-rule authority. They do
not generate engineering facts or requirements and never confer write access.
"""
from copy import deepcopy
from hashlib import sha256
import re


ROLE = 'OPERATION_ALLOCATION_COMPOSITION'
CONTRACT = 'PCE-OPERATION-ALLOCATION-COMPOSITION-V1'
CREATE = 'production.engineering.rule.create'
RELEASE = 'production.engineering.rule.release'
_SCOPE_KEYS = {'companyId', 'productTypeId', 'operationId', 'manufacturingModeId',
    'workCenterId', 'standardCapacityId', 'uomId', 'quantityBasis', 'basisUomId'}
_MEMBER_KEYS = {'ruleCode', 'ruleVersion', 'specificationHash', 'componentCode'}
_IMMUTABLE_FIELDS = ('company_id', 'rule_code', 'rule_name', 'version', 'rule_kind',
    'specification', 'effective_from', 'effective_to')


class OperationContributionCompositionError(Exception):
    def __init__(self, code, message, details=None):
        self.code, self.message, self.details = code, message, details or {}
        super().__init__(message)


def _fail(code, message, **details):
    raise OperationContributionCompositionError(code, message, details)


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail('ALLOCATION_COMPOSITION_INVALID', '组合声明字段必须是明确且无首尾空白的文本。', field=field)
    return value


def _keys(value, expected, field):
    if not isinstance(value, dict) or set(value) != expected:
        _fail('ALLOCATION_COMPOSITION_INVALID', '组合声明字段缺失或含未支持字段。', field=field)


def validate_composition_specification(specification):
    """Validate the non-executable declaration without reading any database."""
    from .engineering_rule_foundation import CODE_PATTERN, VERSION_PATTERN
    _keys(specification, {'ruleRole', 'rulePackage', 'sourceEvidence', 'allocationComposition'}, 'specification')
    if specification['ruleRole'] != ROLE:
        _fail('ALLOCATION_COMPOSITION_INVALID', '组合声明必须使用明确的非执行规则角色。')
    package = specification['rulePackage']
    _keys(package, {'code', 'version'}, 'rulePackage')
    if (not CODE_PATTERN.fullmatch(_text(package['code'], 'rulePackage.code'))
            or not VERSION_PATTERN.fullmatch(_text(package['version'], 'rulePackage.version'))):
        _fail('ALLOCATION_COMPOSITION_INVALID', '组合声明编码或版本格式无效。')
    evidence = specification['sourceEvidence']
    _keys(evidence, {'reference'}, 'sourceEvidence')
    _text(evidence['reference'], 'sourceEvidence.reference')
    composition = specification['allocationComposition']
    _keys(composition, {'contractVersion', 'operator', 'quantityPurpose', 'memberRules',
        'resourceScope', 'allowSameObjectAcrossComponents', 'inputOverlap'}, 'allocationComposition')
    if (composition['contractVersion'] != CONTRACT or composition['operator'] != 'SUM'
            or composition['allowSameObjectAcrossComponents'] is not True
            or composition['inputOverlap'] != 'FORBID'):
        _fail('ALLOCATION_COMPOSITION_INVALID', '组合声明仅支持明确的互补分量加法，并始终禁止输入事实重叠。')
    _text(composition['quantityPurpose'], 'quantityPurpose')
    members = composition['memberRules']
    if not isinstance(members, list) or len(members) < 2:
        _fail('ALLOCATION_COMPOSITION_INVALID', '组合声明必须列明至少两个正式规则分量。')
    identities, components = set(), set()
    for member in members:
        _keys(member, _MEMBER_KEYS, 'memberRules')
        for key in _MEMBER_KEYS:
            _text(member[key], 'memberRules.' + key)
        if (not CODE_PATTERN.fullmatch(member['ruleCode'])
                or not VERSION_PATTERN.fullmatch(member['ruleVersion'])
                or not re.fullmatch(r'[0-9a-f]{64}', member['specificationHash'])):
            _fail('ALLOCATION_COMPOSITION_INVALID', '组合成员必须绑定精确规则编码、版本及规范哈希。')
        identity = (member['ruleCode'], member['ruleVersion'])
        if identity in identities or member['componentCode'] in components:
            _fail('ALLOCATION_COMPOSITION_INVALID', '组合成员规则或分量身份重复。')
        identities.add(identity)
        components.add(member['componentCode'])
    scope = composition['resourceScope']
    _keys(scope, _SCOPE_KEYS, 'resourceScope')
    for key in _SCOPE_KEYS - {'quantityBasis'}:
        if key == 'standardCapacityId' and scope[key] is None:
            continue
        if type(scope[key]) is not int or scope[key] <= 0:
            _fail('ALLOCATION_COMPOSITION_INVALID', '组合资源引用必须是明确的正式正整数身份。', field=key)
    if scope['quantityBasis'] not in {'SOURCE_SCOPE_TOTAL', 'PER_BASIS_QUANTITY'}:
        _fail('ALLOCATION_COMPOSITION_INVALID', '组合声明缺少已支持的正式数量口径。')
    return deepcopy(specification)


def _hash(value):
    from .engineering_rule_foundation import canonical_json
    return sha256(canonical_json(value).encode()).hexdigest()


def _cache_key(cache, key):
    live = _native_cache(cache, getattr(cache, 'company_id', None))
    if live is None:
        return None
    return ('operation_contribution_composition', live._raw_connection.total_changes, key)


def _read(cache, key, loader):
    qualified = _cache_key(cache, key)
    if qualified is None:
        return loader()
    if qualified in cache:
        return cache[qualified]
    value = loader()
    if _cache_key(cache, key) == qualified:
        cache[qualified] = value
    return value


def _native_cache(read_cache, company_id):
    from .operation_requirement_service import _requirement_read_cache
    return _requirement_read_cache(read_cache, company_id)


def _today():
    from .operation_requirement_service import _today as native_today
    return native_today()


def _active(row, on_date):
    return bool(row and getattr(row, 'is_active', True)
        and (not getattr(row, 'effective_from', None) or row.effective_from <= on_date)
        and (not getattr(row, 'effective_to', None) or row.effective_to >= on_date))


def _immutable(row):
    values = {}
    for key in _IMMUTABLE_FIELDS:
        value = getattr(row, key)
        values[key] = value.isoformat() if hasattr(value, 'isoformat') else value
    return values


def validate_composition_references(rule, *, read_cache=None):
    """Check a candidate's exact current members and native manufacturing refs.

    This is also used before publication, so it deliberately requires no audit
    or released status for the declaration itself. Members must be released.
    """
    from masterdata.models import UnitOfMeasure
    from .models import EngineeringRuleDefinition
    from .engineering_rule_foundation import specification_hash
    from .manufacturing_rule_configuration import publication_config_validation
    spec = validate_composition_specification(rule.specification)
    composition, on_date = spec['allocationComposition'], _today()
    scope, package = composition['resourceScope'], spec['rulePackage']
    if (rule.rule_kind != 'decision' or rule.company_id != scope['companyId']
            or rule.rule_code != package['code'] or rule.version != package['version']
            or not _active(rule, on_date)):
        _fail('ALLOCATION_COMPOSITION_RESOURCE_MISMATCH', '组合声明的类型、公司、版本或有效期与正式对象不一致。')
    cache = _native_cache(read_cache, rule.company_id)
    basis_unit = _read(cache, ('composition_basis_uom', rule.company_id, scope['basisUomId']), lambda:
        UnitOfMeasure.objects.filter(pk=scope['basisUomId'], company_id=rule.company_id, is_active=True).first())
    if not basis_unit:
        _fail('ALLOCATION_COMPOSITION_RESOURCE_MISMATCH', '组合声明的基准单位无效或不属于当前公司。')
    rows = []
    for member in composition['memberRules']:
        row = _read(cache, ('composition_member', rule.company_id, member['ruleCode'], member['ruleVersion']), lambda:
            EngineeringRuleDefinition.objects.filter(company_id=rule.company_id,
                rule_code=member['ruleCode'], version=member['ruleVersion']).first())
        if (not row or row.status != 'released' or not _active(row, on_date)
                or specification_hash(row.specification) != member['specificationHash']):
            _fail('ALLOCATION_COMPOSITION_MEMBER_MISMATCH', '组合成员未发布、已失效或与绑定的不可变规则哈希不一致。',
                ruleCode=member['ruleCode'], ruleVersion=member['ruleVersion'])
        member_spec = row.specification
        if not isinstance(member_spec, dict):
            _fail('ALLOCATION_COMPOSITION_MEMBER_MISMATCH', '组合成员缺少正式规则规格。')
        output = member_spec.get('outputs', [None])[0] if isinstance(member_spec.get('outputs'), list) and member_spec['outputs'] else None
        config = member_spec.get('manufacturing')
        semantics = member_spec.get('applicability', {})
        if (not isinstance(output, dict) or not isinstance(config, dict)
                or not isinstance(semantics, dict) or member_spec.get('ruleRole') == ROLE
                or output.get('resultDomain') != 'OPERATION_REQUIREMENT'
                or output.get('canonicalName') != composition['quantityPurpose']
                or semantics.get('sourceSemantic') != member['componentCode']
                or output.get('sourceScope') != 'SALES_ORDER_ITEM'):
            _fail('ALLOCATION_COMPOSITION_MEMBER_MISMATCH', '组合成员没有一致的正式数量用途或精确分量语义。')
        actual_scope = {'companyId': row.company_id, 'productTypeId': output.get('productTypeId'),
            'operationId': output.get('operationId'), 'manufacturingModeId': config.get('modeId'),
            'workCenterId': config.get('workCenterId'), 'standardCapacityId': config.get('standardCapacityId'),
            'uomId': output.get('uomId'), 'quantityBasis': output.get('quantityBasis'),
            'basisUomId': (scope['basisUomId'] if output.get('basisUomSource') == 'SALES_ORDER_ITEM'
                and 'basisUomId' not in output else output.get('basisUomId'))}
        if actual_scope != scope:
            _fail('ALLOCATION_COMPOSITION_RESOURCE_MISMATCH', '组合成员的正式资源、单位或数量口径与声明范围不一致。',
                ruleCode=member['ruleCode'])
        validation_base = ('composition_member_publication', row.company_id, on_date.isoformat(), _hash(_immutable(row)))
        validation_key = _cache_key(cache, validation_base)
        if validation_key is None or validation_key not in cache:
            try:
                native_proof = publication_config_validation(row, require_released=True)
            except Exception as error:
                if not hasattr(error, 'code'):
                    raise
                _fail('ALLOCATION_COMPOSITION_MEMBER_MISMATCH', '组合成员的原生制造配置校验未通过。',
                    ruleCode=member['ruleCode'], nativeCode=error.code, nativeMessage=str(error))
            if native_proof is None:
                _fail('ALLOCATION_COMPOSITION_MEMBER_MISMATCH', '组合成员必须具有正式制造配置证明。')
            if validation_key is not None and _cache_key(cache, validation_base) == validation_key and _today() == on_date:
                cache[validation_key] = True
        rows.append(row)
    return {'specification': spec, 'memberRuleIds': [row.pk for row in rows]}


def _declaration_audit_proof(rule, *, read_cache=None):
    from system.models import OrganizationOperatingAuditRecord
    from workflow_runtime.models import BusinessStateTransition
    cache = _native_cache(read_cache, rule.company_id)
    transitions = _read(cache, ('composition_transitions', rule.company_id, rule.pk), lambda:
        list(BusinessStateTransition.objects.filter(object_type='EngineeringRuleDefinition',
            object_id=rule.pk).order_by('version')))
    stages = (('', 'draft', CREATE), ('draft', 'reviewed', RELEASE), ('reviewed', 'released', RELEASE))
    if len(transitions) != len(stages):
        _fail('ALLOCATION_COMPOSITION_AUDIT_UNPROVEN', '组合声明缺少完整的三阶段正式状态转换证明。')
    immutable, audit_ids, state_ids, actor_ids = _immutable(rule), [], [], []
    package_hash = None
    for version, (transition, (source, target, action)) in enumerate(zip(transitions, stages), 1):
        prefix = 'OrganizationOperatingAuditRecord:'
        reference = transition.audit_reference
        if ((transition.source_state, transition.target_state, transition.action_code, transition.version)
                != (source, target, action, version) or not transition.reason
                or not isinstance(reference, str) or not reference.startswith(prefix)
                or not reference[len(prefix):].isdigit()):
            _fail('ALLOCATION_COMPOSITION_AUDIT_UNPROVEN', '组合声明状态转换的阶段、动作或审计引用不一致。')
        audit_id = int(reference[len(prefix):])
        audit = _read(cache, ('composition_audit', rule.company_id, audit_id), lambda:
            OrganizationOperatingAuditRecord.objects.select_related('actor').only('id', 'organization_id',
                'actor_id', 'target_type', 'target_id', 'action_code', 'reason', 'before_snapshot',
                'after_snapshot', 'actor__id', 'actor__username', 'actor__company_id').filter(pk=audit_id).first())
        if (not audit or audit.organization_id != rule.company_id or audit.target_type != 'EngineeringRuleDefinition'
                or audit.target_id != rule.pk or audit.action_code != action
                or audit.actor_id != transition.operator_id or audit.actor.company_id != rule.company_id
                or not audit.reason):
            _fail('ALLOCATION_COMPOSITION_AUDIT_UNPROVEN', '组合声明审计的公司、对象、动作或真实办理人与转换不一致。')
        before, after = audit.before_snapshot, audit.after_snapshot
        if not isinstance(before, dict) or not isinstance(after, dict):
            _fail('ALLOCATION_COMPOSITION_AUDIT_UNPROVEN', '组合声明审计缺少正式前后快照。')
        for snapshot, expected_status in ((before, source), (after, target)):
            state, authorization, chain = (snapshot.get(key) for key in ('state', 'authorization', 'executionChain'))
            imported = snapshot.get('importContext')
            if (snapshot.get('factSource') != 'server' or not isinstance(state, dict)
                    or state.get('status') != expected_status or not isinstance(authorization, dict)
                    or authorization.get('allowed') is not True or authorization.get('actionCode') != action
                    or str(authorization.get('organizationId')) != str(rule.company_id)
                    or not isinstance(chain, dict) or not isinstance(imported, dict)
                    or chain.get('account') != audit.actor.username
                    or imported.get('contractVersion') != 'PCE-MANUFACTURING-EOR-RULE-V1'
                    or any(not chain.get(key) for key in ('account', 'employeeId', 'employeeNo', 'positionId',
                        'positionCode', 'responsibilityId', 'responsibilityCode'))
                    or not re.fullmatch(r'[0-9a-f]{64}', str(imported.get('packageHash', '')))):
                _fail('ALLOCATION_COMPOSITION_AUDIT_UNPROVEN', '组合声明审计缺少真实授权、实名职责链或配置包证明。')
            if expected_status and (state.get('id') != rule.pk
                    or any(state.get(key) != value for key, value in immutable.items())):
                _fail('ALLOCATION_COMPOSITION_AUDIT_UNPROVEN', '组合声明的审计快照与不可变版本、范围或规则内容不一致。')
            if package_hash is None:
                package_hash = imported['packageHash']
            elif package_hash != imported['packageHash']:
                _fail('ALLOCATION_COMPOSITION_AUDIT_UNPROVEN', '组合声明的三阶段配置包证明不一致。')
        if (before['executionChain'] != after['executionChain']
                or before['authorization'] != after['authorization']
                or before['importContext'] != after['importContext']):
            _fail('ALLOCATION_COMPOSITION_AUDIT_UNPROVEN', '组合声明阶段前后实名办理链不一致。')
        audit_ids.append(audit_id)
        state_ids.append(transition.pk)
        actor_ids.append(audit.actor_id)
    if len(set(audit_ids)) != 3 or len(set(actor_ids)) != 1:
        _fail('ALLOCATION_COMPOSITION_AUDIT_UNPROVEN', '组合声明各阶段不得复用同一审计。')
    return {'auditIds': audit_ids, 'stateTransitionIds': state_ids, 'actorIds': actor_ids,
        'packageHash': package_hash}


def composition_for_requirement(req, company_id, read_cache=None):
    """Resolve exactly one current declaration; never infer addition from names."""
    from .models import EngineeringRuleDefinition
    from .engineering_rule_foundation import specification_hash
    if req.calculation.company_id != company_id:
        _fail('ALLOCATION_COMPOSITION_RESOURCE_MISMATCH', '需求不属于当前公司。')
    member_rule, on_date = req.source_detail.rule, _today()
    output = member_rule.specification['outputs'][0]
    actual = {'companyId': req.calculation.company_id, 'productTypeId': output.get('productTypeId'),
        'operationId': req.operation_id, 'manufacturingModeId': req.manufacturing_mode_id,
        'workCenterId': req.work_center_id, 'standardCapacityId': req.standard_capacity_id,
        'uomId': req.uom_id, 'quantityBasis': req.quantity_basis, 'basisUomId': req.basis_uom_id}
    cache = _native_cache(read_cache, company_id)
    declarations = _read(cache, ('composition_declarations', company_id, on_date.isoformat()), lambda:
        list(EngineeringRuleDefinition.objects.filter(company_id=company_id,
            rule_kind='decision', status='released').order_by('pk')))
    matches = []
    for declaration in declarations:
        raw = declaration.specification
        if not isinstance(raw, dict) or raw.get('ruleRole') != ROLE or not _active(declaration, on_date):
            continue
        spec = validate_composition_specification(raw)
        composition = spec['allocationComposition']
        scope = composition['resourceScope']
        if actual != scope:
            continue
        members = [row for row in composition['memberRules']
            if (row['ruleCode'], row['ruleVersion']) == (member_rule.rule_code, member_rule.version)]
        if not members:
            continue
        if len(members) != 1 or members[0]['specificationHash'] != specification_hash(member_rule.specification):
            _fail('ALLOCATION_COMPOSITION_MEMBER_MISMATCH', '需求来源规则与组合声明绑定的精确版本哈希不一致。')
        validate_composition_references(declaration, read_cache=cache)
        if req.source_detail.rule_version != member_rule.version:
            _fail('ALLOCATION_COMPOSITION_RESOURCE_MISMATCH', '当前需求的正式来源、资源或数量口径不在组合声明范围。')
        matches.append({'contractVersion': CONTRACT, 'declarationId': declaration.pk,
            'ruleCode': declaration.rule_code, 'ruleVersion': declaration.version,
            'specificationHash': specification_hash(spec), 'quantityPurpose': composition['quantityPurpose'],
            'componentCode': members[0]['componentCode'], 'memberRules': deepcopy(composition['memberRules']),
            'resourceScope': deepcopy(scope), 'auditProof': _declaration_audit_proof(declaration, read_cache=cache)})
    if len(matches) > 1:
        _fail('ALLOCATION_COMPOSITION_AMBIGUOUS', '当前需求命中多个已发布组合声明，不能任意选择。',
            declarationIds=[row['declarationId'] for row in matches])
    return deepcopy(matches[0]) if matches else None


def composition_allows_shared_objects(left, right, left_identity, right_identity):
    """Permit shared objects only for distinct, explicitly bound components.

    Identity leaf overlap remains forbidden even when the business declaration
    authorizes different components on the same baseline/design object.
    """
    if set(left_identity['inputFactIds']) & set(right_identity['inputFactIds']):
        _fail('ALLOCATION_CONTRIBUTION_OVERLAP', '组合贡献重叠使用了同一原始输入事实，不能重复分配。')
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    keys = ('contractVersion', 'declarationId', 'ruleCode', 'ruleVersion', 'specificationHash',
        'quantityPurpose', 'memberRules', 'resourceScope', 'auditProof')
    if (left.get('contractVersion') != CONTRACT or any(left.get(key) != right.get(key) for key in keys)
            or left.get('componentCode') == right.get('componentCode')):
        return False
    members = left.get('memberRules')
    if (not isinstance(members, list) or any(not isinstance(row, dict)
            or not isinstance(row.get('componentCode'), str) for row in members)):
        return False
    components = {row['componentCode'] for row in members}
    return bool(left.get('componentCode') in components and right.get('componentCode') in components
        and type(left_identity.get('baselineId')) is int and left_identity['baselineId'] > 0
        and left_identity['baselineId'] == right_identity.get('baselineId'))
