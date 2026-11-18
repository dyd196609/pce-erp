

# Native formal date consumer restoration.
from contextvars import ContextVar

from copy import deepcopy

from datetime import date, datetime, timedelta

from decimal import Decimal

from hashlib import sha256

import json

from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist, ValidationError

from django.db import IntegrityError, OperationalError, transaction

from django.utils import timezone

from masterdata.models import CodeRule, ExternalIdentity, MasterDataWriteRequest

from system.authorization import AuthorizationService

from system.models import Company, OrganizationOperatingAuditRecord, User

from workflow_runtime.models import BusinessStateTransition

from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state, record_projected_business_transition,
    transition_business_object,
)

from .models import (ManufacturingTimePolicyRevision as Policy,
    ManufacturingTimePolicyNameOption as NameOption, StandardCapacity)

from .production_foundation_service import ProductionFoundationError, _actor_chain, _audit

CONTRACT = 'PCE-MANUFACTURING-TIME-POLICY-V1'

ENTITY = 'manufacturing-time-policies'

OBJECT = 'ManufacturingTimePolicyRevision'

VIEW = 'production.master_data.view'

RESOURCE = 'production.master_data.resource.maintain'

CAPACITY = 'production.master_data.capacity.maintain'

_write_guard = ContextVar('manufacturing_time_policy_write', default=False)

_name_write_guard = ContextVar('manufacturing_time_policy_name_write', default=False)

NUMBER_ENTITY = 'production_manufacturing_time_policy'

NAME_ENTITY = 'manufacturing-time-policy-name-options'

NAME_OBJECT = 'ManufacturingTimePolicyNameOption'

NAME_CONTRACT = 'PCE-MANUFACTURING-TIME-POLICY-NAME-OPTION-V1'

NAME_BATCH_ENTITY = 'manufacturing-time-policy-name-option-sets'

NAME_BATCH_CONTRACT = 'PCE-MANUFACTURING-TIME-POLICY-NAME-REFERENCES-V1'

FIELDS = {
    'kind': 'kind', 'code': 'code', 'name': 'name',
    'effectiveFrom': 'effective_from', 'effectiveTo': 'effective_to',
    'workCenterId': 'work_center_id', 'operationId': 'operation_id',
    'standardCapacityId': 'standard_capacity_id', 'sharedVersionId': 'shared_version_id',
    'predecessorId': 'predecessor_id', 'payload': 'payload',
}

class TimePolicyError(ProductionFoundationError):
    pass

def _fail(code, message, **details):
    if details.get('path') and 'errors' not in details:
        details['errors'] = [{'code': code, 'message': message,
            'path': details['path'], 'severity': 'ERROR'}]
    raise TimePolicyError(code, message, details)

def _model_invalid(path, message):
    raise ValidationError({path: message})

def _model_issues(error):
    """Keep model rejections consumable by the existing field-issue contract."""
    fields = getattr(error, 'message_dict', None) or {'payload': error.messages}
    return [{'code': 'POLICY_INVALID', 'message': str(message), 'path': path, 'severity': 'ERROR'}
        for path, messages in fields.items() for message in messages]

def _json(value):
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value

def _hash(value):
    return sha256(json.dumps(_json(value), ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()

def physical_hash(row):
    return _hash({f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields})

def _state(row):
    # The audit FK points back to this very envelope and is checked separately.
    return _json({f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields
        if f.attname != 'confirmation_audit_id'})

def _content(row):
    return {key: getattr(row, key) for key in (
        'company_id', 'kind', 'code', 'name', 'revision', 'scope_key', 'predecessor_id',
        'shared_version_id', 'work_center_id', 'operation_id', 'standard_capacity_id',
        'effective_from', 'effective_to', 'schema_version', 'payload', 'reference_snapshot')}

def _scope(row):
    identity = ({'code': row.code} if row.kind == Policy.Kind.SHARED_ARRANGEMENT else
        {'workCenterId': row.work_center_id} if row.kind == Policy.Kind.WC_APPLICATION else
        {'operationId': row.operation_id, 'workCenterId': row.work_center_id}
        if row.kind == Policy.Kind.OPERATION_RESTRICTION else
        {'standardCapacityId': row.standard_capacity_id})
    return {'companyId': row.company_id, 'kind': row.kind, **identity}

def _actor(user, *, kind=None, write=False):
    if not user or not getattr(user, 'pk', None):
        _fail('PERMISSION_DENIED', '必须使用当前已认证公司账号。')
    current = User.objects.filter(pk=user.pk, is_active=True).first()
    if not current or not current.company_id or current.company_id != getattr(user, 'company_id', None):
        _fail('PERMISSION_DENIED', '账号公司或有效状态已变化。')
    permission = (CAPACITY if kind == Policy.Kind.CAPACITY_TIME_BASIS else RESOURCE) if write else VIEW
    decision = AuthorizationService.decide(user=current, action_code=permission,
        organization_id=current.company_id, business_object={'organizationId': current.company_id})
    if not decision.get('allowed'):
        _fail(decision.get('decisionCode', 'PERMISSION_DENIED'), decision.get('reason', '没有当前动作权限。'))
    chain = _actor_chain(current) if write else {}
    return current, decision, chain, permission

def maintenance_authorization(*, user, kind=None):
    result = {'canRead': False, 'canMaintain': False}
    for write, key in ((False, 'canRead'), (True, 'canMaintain')):
        try:
            _, decision, chain, _ = _actor(user, kind=kind, write=write)
            result.update({key: True})
            if write:
                result.update(authorization=decision, executionChain=chain)
        except ProductionFoundationError as error:
            result[key + 'Reason'] = error.message
    return result

def _date(value, field):
    if value in (None, ''):
        return None
    if type(value) is date:
        return value
    if not isinstance(value, str):
        _fail('POLICY_INVALID', '日期必须为ISO日期。', path=field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _fail('POLICY_INVALID', '日期必须为ISO日期。', path=field)
    if value != parsed.isoformat():
        _fail('POLICY_INVALID', '日期必须为完整ISO日期。', path=field)
    return parsed

def validate_model_record(row):
    """Business checks shared by ORM guards and the native service."""
    if row.kind not in Policy.Kind.values or row.status not in {'draft', 'confirmed'}:
        _model_invalid('kind' if row.kind not in Policy.Kind.values else 'status', '制造时间版本类型或状态无效。')
    wc, op, sc, shared = row.work_center_id, row.operation_id, row.standard_capacity_id, row.shared_version_id
    valid = (
        row.kind == Policy.Kind.SHARED_ARRANGEMENT and not any((wc, op, sc, shared))
        or row.kind == Policy.Kind.WC_APPLICATION and wc and shared and not any((op, sc))
        or row.kind == Policy.Kind.OPERATION_RESTRICTION and op and not any((sc, shared))
        or row.kind == Policy.Kind.CAPACITY_TIME_BASIS and sc and not any((wc, op)))
    if not valid:
        required = {Policy.Kind.SHARED_ARRANGEMENT: (),
            Policy.Kind.WC_APPLICATION: ('work_center_id', 'shared_version_id'),
            Policy.Kind.OPERATION_RESTRICTION: ('operation_id',),
            Policy.Kind.CAPACITY_TIME_BASIS: ('standard_capacity_id',)}[row.kind]
        allowed = set(required) | ({'work_center_id'} if row.kind == Policy.Kind.OPERATION_RESTRICTION
            else {'shared_version_id'} if row.kind == Policy.Kind.CAPACITY_TIME_BASIS else set())
        for field in required:
            if not getattr(row, field):
                _model_invalid(next(key for key, value in FIELDS.items() if value == field),
                    '当前配置类型必须填写该业务引用。')
        for field in ('work_center_id', 'operation_id', 'standard_capacity_id', 'shared_version_id'):
            if field not in allowed and getattr(row, field):
                _model_invalid(next(key for key, value in FIELDS.items() if value == field),
                    '当前配置类型不允许填写该业务引用。')
    if row.schema_version != CONTRACT or not isinstance(row.payload, dict) or not isinstance(row.reference_snapshot, dict):
        _model_invalid('payload', '制造时间版本必须使用受治理结构化合同。')
    if row.scope_key != _hash(_scope(row)) or row.content_hash != _hash(_content(row)):
        _model_invalid('payload', '制造时间范围或内容Hash不一致。')
    if row.effective_to and row.effective_from and row.effective_to < row.effective_from:
        _model_invalid('effectiveTo', '失效日期不得早于生效日期。')
    for name in ('work_center', 'operation', 'standard_capacity', 'shared_version'):
        if getattr(row, name + '_id'):
            path = next(key for key, value in FIELDS.items() if value == name + '_id')
            try:
                target = getattr(row, name)
            except ObjectDoesNotExist:
                _model_invalid(path, '制造时间引用不存在，请选择正式业务对象。')
            if target.company_id != row.company_id:
                _model_invalid(path, '制造时间引用必须属于同一公司。')
    if shared and (row.shared_version.kind != Policy.Kind.SHARED_ARRANGEMENT or row.shared_version.status != 'confirmed'):
        _model_invalid('sharedVersionId', '制度引用必须指向同公司已确认共用版本。')
    if row.kind == Policy.Kind.CAPACITY_TIME_BASIS:
        source = row.payload.get('standardDaySource', 'UNRESOLVED')
        if ((source == 'WORK_SYSTEM_REVISION') != bool(shared)
                or source not in {'WORK_SYSTEM_REVISION', 'UNRESOLVED'}
                or row.status == 'confirmed' and source != 'WORK_SYSTEM_REVISION'):
            _model_invalid('sharedVersionId', '产能标准日必须明确引用制度版本；未齐依据只可待完善。')
    if row.predecessor_id:
        previous = row.predecessor
        if (previous.pk == row.pk or previous.company_id != row.company_id or previous.kind != row.kind
                or previous.status != 'confirmed'
                or row.revision != previous.revision + 1):
            _model_invalid('predecessorId', '前驱必须是同公司、同类型的已确认上一修订。')
        if previous.scope_key != row.scope_key:
            before, after = _scope(previous), _scope(row)
            path = next((key for key in after if before.get(key) != after[key]), 'predecessorId')
            _model_invalid(path, '新修订必须保持前驱版本的业务适用范围。')
        if row.effective_from and previous.effective_from:
            if row.effective_from < previous.effective_from:
                _model_invalid('effectiveFrom', '新修订生效日期不得早于前驱版本。')
            if row.status == 'confirmed' and row.effective_from == previous.effective_from:
                _model_invalid('effectiveFrom', '已确认后继的生效日期必须晚于前驱版本。')
    elif row.revision != 1:
        _model_invalid('predecessorId', '首修订序号必须为1。')

def _normalize(row, *, strict=False):
    from .manufacturing_time_calculation import normalize_policy_payload
    result = normalize_policy_payload(row.kind, deepcopy(row.payload), strict=strict)
    if not isinstance(result, dict) or not isinstance(result.get('payload'), dict):
        _fail('POLICY_CALCULATION_INVALID', '时间规范化结果不符合服务合同。')
    return result

def _references(row):
    proof = {}
    if row.shared_version_id:
        shared = Policy.objects.filter(pk=row.shared_version_id, company_id=row.company_id).first()
        if shared is None:
            _fail('POLICY_REFERENCE_INVALID', '制度引用不存在或跨公司。', path='sharedVersionId')
        _verify(shared)
        if shared.company_id != row.company_id or shared.kind != Policy.Kind.SHARED_ARRANGEMENT or shared.status != 'confirmed':
            _fail('POLICY_REFERENCE_INVALID', '制度引用不是同公司已确认共用版本。', path='sharedVersionId')
        proof['sharedVersion'] = {'id': shared.pk, 'contentHash': shared.content_hash,
            'revision': shared.revision, 'payload': deepcopy(shared.payload)}
    if row.standard_capacity_id:
        capacity = StandardCapacity.objects.select_related('work_center', 'operation', 'product_type', 'uom').filter(
            pk=row.standard_capacity_id, company_id=row.company_id).first()
        if capacity is None or not all((capacity.work_center_id, capacity.operation_id,
                capacity.product_type_id, capacity.uom_id)):
            _fail('POLICY_REFERENCE_INVALID', '标准产能不存在、跨公司或没有完整真实范围。')
        if any(target.company_id != row.company_id for target in (
                capacity.work_center, capacity.operation, capacity.product_type, capacity.uom)):
            _fail('POLICY_REFERENCE_INVALID', '标准产能引用的资源、工序、产品类型或单位跨公司。')
        if (capacity.operation.calculation_uom_id != capacity.uom_id
                or capacity.operation.calculation_basis != capacity.uom.dimension):
            _fail('POLICY_REFERENCE_INVALID', '标准产能单位必须等于工序正式核算单位，且单位维度必须与工序核算维度一致。')
        if (capacity.resource_scope != 'work_center' or capacity.time_basis != 'day'
                or capacity.time_basis_quantity != Decimal(1) or capacity.time_unit != 'DAY'
                or capacity.measurement_status != 'measured' or capacity.quantity is None or capacity.quantity <= 0):
            _fail('POLICY_REFERENCE_INVALID', '分钟线性依据必须引用正式正数每日产能。')
        row.standard_capacity = capacity
        actual = physical_hash(capacity)
        supplied = row.payload.get('standardCapacityHash')
        if supplied and supplied != actual:
            _fail('POLICY_REFERENCE_CHANGED', '标准产能物理事实已变化。', path='payload.standardCapacityHash')
        row.payload['standardCapacityHash'] = actual
        proof['standardCapacity'] = {'id': capacity.pk, 'physicalHash': actual,
            'operationId': capacity.operation_id, 'workCenterId': capacity.work_center_id,
            'productTypeId': capacity.product_type_id, 'uomId': capacity.uom_id}
    return proof

def _build(user, payload, *, current=None, header_required=True):
    if not isinstance(payload, dict) or set(payload) - set(FIELDS):
        _fail('POLICY_INVALID', '仅允许提交已声明的时间版本字段。', fields=sorted(set(payload) - set(FIELDS)) if isinstance(payload, dict) else [])
    values = {name: payload.get(key) for key, name in FIELDS.items()}
    for key in ('code', 'name'):
        if not header_required:
            if values[key] is not None and not isinstance(values[key], str):
                _fail('POLICY_INVALID', '配置编号和名称必须为文字；核算不要求填写。', path=key)
            values[key] = (values[key] or '').strip()
            continue
        if (not isinstance(values[key], str) or not values[key].strip()
                or len(values[key].strip()) > (80 if key == 'code' else 160)):
            _fail('POLICY_INVALID', '必须维护配置编码和名称。', path=key)
        values[key] = values[key].strip()
    for key in ('work_center_id', 'operation_id', 'standard_capacity_id', 'shared_version_id', 'predecessor_id'):
        if values[key] is not None and (type(values[key]) is not int or values[key] <= 0):
            _fail('POLICY_INVALID', '引用必须是正式正整数ID或空值。', path=key)
    values['effective_from'] = _date(values['effective_from'], 'effectiveFrom')
    values['effective_to'] = _date(values['effective_to'], 'effectiveTo')
    values['payload'] = deepcopy(values['payload'] if values['payload'] is not None else {})
    if not isinstance(values['payload'], dict):
        _fail('POLICY_INVALID', '时间内容必须是结构化对象。', path='payload')
    row = Policy(company_id=user.company_id, **values)
    if current:
        row.pk, row.version, row.revision = current.pk, current.version + 1, current.revision
    elif row.predecessor_id:
        previous = Policy.objects.filter(pk=row.predecessor_id, company_id=user.company_id).first()
        if previous is None:
            _fail('POLICY_REFERENCE_INVALID', '前驱版本不存在或跨公司。', path='predecessorId')
        row.predecessor, row.revision = previous, previous.revision + 1
    row.scope_key = _hash(_scope(row))
    try:
        row.reference_snapshot = _references(row)
        normalized = _normalize(row)
        row.payload = normalized['payload']
        if any(error.get('severity', 'ERROR') != 'INCOMPLETE' for error in normalized.get('errors', [])):
            _fail('POLICY_INVALID', '时间配置存在格式或区间错误。', errors=normalized['errors'])
        row.content_hash = _hash(_content(row))
        validate_model_record(row)
    except ValidationError as error:
        issues = _model_issues(error)
        _fail('POLICY_INVALID', issues[0]['message'], errors=issues)
    except ObjectDoesNotExist:
        _fail('POLICY_INVALID', '时间配置引用不存在。', path='predecessorId')
    if current and (row.scope_key != current.scope_key or row.kind != current.kind
            or row.predecessor_id != current.predecessor_id or row.code != current.code):
        _fail('POLICY_SCOPE_IMMUTABLE', '草稿更新不得改换类型、范围、编码或前驱。')
    return row, normalized

def _validation(row, *, strict=False):
    result = _normalize(row, strict=strict)
    if row.effective_from is None:
        result.setdefault('errors', []).append({'code': 'PERIOD_REQUIRED', 'path': 'effectiveFrom',
            'severity': 'INCOMPLETE', 'message': '生效日期尚未维护。'})
    elif (row.status == 'draft' and row.predecessor_id and row.predecessor.effective_from
            and row.effective_from == row.predecessor.effective_from):
        result.setdefault('errors', []).append({'code': 'SUCCESSOR_PERIOD_REQUIRED', 'path': 'effectiveFrom',
            'severity': 'INCOMPLETE',
            'message': '新修订沿用前驱生效日期，已保存的待完善草稿不生效；确认前须维护晚于前驱版本的生效日期。'})
    if row.kind == Policy.Kind.CAPACITY_TIME_BASIS and row.shared_version_id:
        shared = row.shared_version
        source = _normalize(shared, strict=True)
        pattern = row.payload.get('standardPattern')
        fact = source.get('facts', {}).get('patterns', {}).get(pattern, {}).get('processing')
        if not fact or not Decimal(str(fact.get('netMinutes', '0'))) > 0:
            result.setdefault('errors', []).append({'code': 'STANDARD_PATTERN_REQUIRED',
                'path': 'payload.standardPattern', 'severity': 'INCOMPLETE',
                'message': '所选共用版本必须有明确的标准净加工模式。'})
        else:
            result.setdefault('facts', {})['standardDayMinutes'] = fact['netMinutes']
            result['facts']['standardDaySource'] = {'policyId': shared.pk, 'contentHash': shared.content_hash,
                'standardPattern': pattern}
    result['ready'] = not result.get('errors')
    return result

def _verify(row, *, seen=None):
    seen = set() if seen is None else seen
    if row.pk in seen:
        _fail('POLICY_PROOF_INVALID', '制度引用出现循环。')
    seen.add(row.pk)
    try:
        validate_model_record(row)
    except ValidationError as error:
        _fail('POLICY_PROOF_INVALID', '版本物理事实或Hash不一致。', errors=_model_issues(error))
    identity = row.creation_write_request.source_identity
    creation = row.creation_write_request
    if (identity.organization_id != row.company_id or identity.target_entity_type != ENTITY
            or identity.target_entity_id != str(row.pk) or identity.mapping_status != 'MATCH'
            or identity.source_system != 'PCE_SYSTEM' or identity.source_type != 'MANUFACTURING_TIME_POLICY'
            or identity.source_object_type != OBJECT or identity.source_fingerprint != _hash({'scope': _scope(row), 'revision': row.revision})
            or identity.audit_metadata != {'contractVersion': CONTRACT, 'scope': _scope(row), 'revision': row.revision}
            or creation.organization_id != row.company_id or creation.entity_type != ENTITY
            or creation.target_entity_id != str(row.pk) or creation.status != 'COMMITTED'):
        _fail('POLICY_PROOF_INVALID', '版本身份或初始正式写入链不一致。')
    audits = list(OrganizationOperatingAuditRecord.objects.filter(
        organization_id=row.company_id, target_type=OBJECT, target_id=row.pk).order_by('pk'))
    previous = {}
    for audit in audits:
        context = (audit.after_snapshot or {}).get('importContext', {})
        ledger = MasterDataWriteRequest.objects.filter(pk=context.get('writeRequestId')).first()
        after = (audit.after_snapshot or {}).get('state', {})
        if (context.get('contractVersion') != CONTRACT or audit.action_code not in {RESOURCE, CAPACITY}
                or not ledger or ledger.status != 'COMMITTED' or ledger.organization_id != row.company_id
                or ledger.entity_type != ENTITY or ledger.target_entity_id != str(row.pk)
                or ledger.result.get('auditId') != audit.pk or ledger.source_identity_id != identity.pk
                or ledger.result.get('recordId') != row.pk or ledger.result.get('contentHash') != after.get('content_hash')
                or ledger.result.get('version') != after.get('version')
                or not (audit.after_snapshot or {}).get('authorization', {}).get('allowed')
                or ledger.audit_metadata.get('operatorId') != audit.actor_id
                or ledger.request_hash != _hash(ledger.audit_metadata.get('request'))
                or (audit.before_snapshot or {}).get('state') != previous):
            _fail('POLICY_PROOF_INVALID', '版本修订审计、请求Hash或前后事实链不一致。')
        previous = deepcopy(audit.after_snapshot.get('state'))
    if not audits or previous != _state(row):
        _fail('POLICY_PROOF_INVALID', '版本当前状态与最后已提交审计不一致。')
    if audits[0].after_snapshot['importContext']['writeRequestId'] != creation.pk:
        _fail('POLICY_PROOF_INVALID', '初始审计必须引用该版本自身的创建账本。')
    transitions = list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=row.pk).order_by('version', 'pk'))
    expected = [('', 'draft')] + ([('draft', 'confirmed')] if row.status == 'confirmed' else [])
    if len(transitions) != len(expected):
        _fail('POLICY_PROOF_INVALID', '版本统一转换历史数量不一致。')
    for index, (transition, (old, new)) in enumerate(zip(transitions, expected), start=1):
        target_audit = audits[0] if new == 'draft' else audits[-1]
        if (transition.version != index or transition.source_state != old or transition.target_state != new
                or transition.operator_id != target_audit.actor_id
                or transition.action_code != target_audit.action_code
                or transition.audit_reference != f'OrganizationOperatingAuditRecord:{target_audit.pk}'):
            _fail('POLICY_PROOF_INVALID', '版本状态转换与原生审计不一致。')
    if row.status == 'confirmed' and (row.confirmation_audit_id != audits[-1].pk
            or row.confirmation_write_request_id != audits[-1].after_snapshot['importContext']['writeRequestId']
            or not row.confirmation_basis or row.confirmed_by_id != audits[-1].actor_id):
        _fail('POLICY_PROOF_INVALID', '版本确认事实不完整。')
    if row.shared_version_id:
        _verify(row.shared_version, seen=seen)
        frozen = row.reference_snapshot.get('sharedVersion', {})
        if (frozen.get('id') != row.shared_version_id or frozen.get('contentHash') != row.shared_version.content_hash
                or frozen.get('payload') != row.shared_version.payload):
            _fail('POLICY_REFERENCE_CHANGED', '共用版本引用事实已变化。')
    if row.standard_capacity_id:
        if row.reference_snapshot.get('standardCapacity', {}).get('physicalHash') != physical_hash(row.standard_capacity):
            _fail('POLICY_REFERENCE_CHANGED', '标准产能物理事实已变化；不得重新解释旧时间依据。')
    return transitions

def _present(row, *, verified=False):
    transitions = _verify(row) if not verified else list(BusinessStateTransition.objects.filter(
        object_type=OBJECT, object_id=row.pk).order_by('version', 'pk'))
    result = {key: _json(getattr(row, field)) for key, field in FIELDS.items()}
    result.update(id=row.pk, recordId=row.pk, companyId=row.company_id, revision=row.revision,
        version=row.version, expectedRevision=row.version, scopeKey=row.scope_key,
        kindLabel=row.get_kind_display(), statusCode=row.status, statusLabel=row.get_status_display(),
        contentHash=row.content_hash, schemaVersion=row.schema_version,
        referenceSnapshot=deepcopy(row.reference_snapshot), confirmationBasis=row.confirmation_basis,
        confirmedAt=_json(row.confirmed_at), validation=_validation(row, strict=row.status == 'confirmed'),
        stateTransitionHistory=[{'id': t.pk, 'sourceState': t.source_state, 'targetState': t.target_state,
            'operatorId': t.operator_id, 'actionCode': t.action_code, 'auditReference': t.audit_reference,
            'version': t.version, 'timestamp': _json(t.timestamp)} for t in transitions])
    result['statusTransitionCount'] = len(result['stateTransitionHistory'])
    return result

def _row(user, policy_id, *, lock=False):
    if type(policy_id) is not int or policy_id <= 0:
        _fail('POLICY_INVALID', '版本身份必须为正式正整数ID。')
    query = Policy.objects.select_related('creation_write_request__source_identity', 'shared_version',
        'standard_capacity', 'predecessor', 'work_center', 'operation')
    if lock:
        query = query.select_for_update()
    row = query.filter(pk=policy_id, company_id=user.company_id).first()
    if row is None:
        _fail('POLICY_NOT_FOUND', '时间版本不存在或不属于当前公司。')
    return row

@transaction.atomic
def read_revision(*, user, policy_id):
    actor, _, _, _ = _actor(user)
    return {'contractVersion': CONTRACT, 'factSource': 'server', 'row': _present(_row(actor, policy_id)),
        'businessWriteCount': 0, 'auditWriteCount': 0}

@transaction.atomic
def list_policies(*, user, kind=None):
    actor, _, _, _ = _actor(user)
    query = Policy.objects.filter(company_id=actor.company_id).order_by('kind', 'scope_key', 'revision', 'pk')
    if kind is not None:
        if kind not in Policy.Kind.values:
            _fail('POLICY_INVALID', '时间配置类型无效。')
        query = query.filter(kind=kind)
    return [_present(row) for row in query]

@transaction.atomic
def preview_policy(*, user, payload):
    actor, _, _, _ = _actor(user)
    if (isinstance(payload, dict) and payload.get('kind') == Policy.Kind.SHARED_ARRANGEMENT
            and payload.get('predecessorId') is None):
        return _preview_shared_draft(payload)
    if isinstance(payload, dict) and payload.get('predecessorId') is not None:
        previous = _row(actor, payload['predecessorId'])
        _verify(previous)
        if payload.get('code') not in (None, '', previous.code):
            _fail('POLICY_SCOPE_IMMUTABLE', '修订核算必须沿用原编号。', path='code')
        payload = {**deepcopy(payload), 'code': previous.code}
    row, _ = _build(actor, payload, header_required=False)
    validation = _validation(row)
    return {'contractVersion': CONTRACT, 'factSource': 'server', 'payload': deepcopy(row.payload),
        'validation': validation, 'ready': validation['ready'], 'errors': validation.get('errors', []),
        'facts': validation.get('facts', {}), 'businessWriteCount': 0, 'auditWriteCount': 0,
        'previewScope': 'CURRENT_DRAFT', 'inputAuthority': 'DRAFT_FORM',
        'isEffectivePolicyProof': False, 'isSavedRevisionProof': False}

def _preview_shared_draft(payload):
    """Calculate maintained intervals, without manufacturing a revision identity.

    Names and validity periods belong to maintenance.  They remain visible as
    save requirements, but are not a prerequisite for arithmetic on the current
    form.  This path cannot interpret any formal resource or predecessor link.
    Formal reads, saving and confirmation continue through their native proof.
    """
    unknown = set(payload) - set(FIELDS)
    if unknown:
        _fail('POLICY_INVALID', '仅允许提交已声明的时间版本字段。', fields=sorted(unknown))
    for key in ('code', 'name'):
        if payload.get(key) is not None and not isinstance(payload[key], str):
            _fail('POLICY_INVALID', '配置编号和名称必须为文字；核算不要求填写。', path=key)
    for key in ('workCenterId', 'operationId', 'standardCapacityId', 'sharedVersionId', 'predecessorId'):
        value = payload.get(key)
        if value is not None:
            if type(value) is not int or value <= 0:
                _fail('POLICY_INVALID', '引用必须是正式正整数ID或空值。', path=key)
            _fail('POLICY_PREVIEW_REFERENCE_UNSUPPORTED',
                  '当前草稿时段核算不证明资源或前驱版本关系；不能带入正式引用。', path=key)
    content = payload.get('payload')
    if not isinstance(content, dict):
        _fail('POLICY_INVALID', '时间内容必须是结构化对象。', path='payload')
    starts = _date(payload.get('effectiveFrom'), 'effectiveFrom')
    ends = _date(payload.get('effectiveTo'), 'effectiveTo')
    if starts and ends and ends < starts:
        _fail('POLICY_INVALID', '失效日期不得早于生效日期。', path='effectiveTo')
    from .manufacturing_time_calculation import normalize_policy_payload
    validation = normalize_policy_payload(Policy.Kind.SHARED_ARRANGEMENT, deepcopy(content))
    if any(error.get('severity', 'ERROR') != 'INCOMPLETE' for error in validation.get('errors', [])):
        _fail('POLICY_INVALID', '时间配置存在格式或区间错误。', errors=validation['errors'])
    requirements = []
    for key, label, limit in (('name', '名称', 160),):
        value = payload.get(key)
        if value is None or isinstance(value, str) and not value.strip():
            requirements.append({'code': 'POLICY_HEADER_REQUIRED', 'path': key, 'severity': 'INCOMPLETE',
                'message': f'保存待完善配置前请填写{label}；当前时段分钟已独立核算。'})
        elif not isinstance(value, str) or len(value.strip()) > limit:
            requirements.append({'code': 'POLICY_HEADER_INVALID', 'path': key, 'severity': 'ERROR',
                'message': f'{label}必须为不超过{limit}字的文字；当前读数不证明配置可保存。'})
    save_requirements = deepcopy(requirements)
    if starts is None:
        requirements.append({'code': 'PERIOD_REQUIRED', 'path': 'effectiveFrom', 'severity': 'INCOMPLETE',
            'message': '生效日期尚未维护；当前读数不是生效期间证明。'})
    validation.setdefault('errors', []).extend(deepcopy(requirements))
    validation['ready'] = not validation['errors']
    return {'contractVersion': CONTRACT, 'factSource': 'server', 'payload': deepcopy(validation['payload']),
        'validation': validation, 'ready': validation['ready'], 'errors': validation['errors'],
        'facts': validation['facts'], 'saveRequirements': save_requirements,
        'previewScope': 'CURRENT_DRAFT', 'inputAuthority': 'DRAFT_FORM',
        'isEffectivePolicyProof': False, 'isSavedRevisionProof': False,
        'businessWriteCount': 0, 'auditWriteCount': 0}

def _input(key, reason):
    if not isinstance(key, str) or key != key.strip() or not 1 <= len(key) <= 160:
        _fail('IDEMPOTENCY_CONFLICT', '必须提供稳定幂等键。')
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 240:
        _fail('REASON_REQUIRED', '必须提供不超过240字的维护原因。', path='reason')
    return reason.strip()

def _replay(actor, action, key, request):
    old = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=actor.company_id, action_code=action, idempotency_key=key).first()
    if old:
        if old.status != 'COMMITTED' or old.entity_type != ENTITY or old.request_hash != _hash(request):
            _fail('IDEMPOTENCY_CONFLICT', '同一幂等键必须绑定完全相同的已提交请求。')
        row = _row(actor, int(old.target_entity_id), lock=True)
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'row': _present(row),
            'idempotentReplay': True, 'historicalResult': deepcopy(old.result),
            'writeRequestId': old.pk, 'auditId': old.result['auditId'],
            'businessWriteCount': 0, 'auditWriteCount': 0, 'stateTransitionWriteCount': 0}

def _commit(ledger, row, audit, *, transitions):
    result = {'recordId': row.pk, 'revision': row.revision, 'version': row.version,
        'contentHash': row.content_hash, 'statusCode': row.status, 'auditId': audit.pk}
    ledger.status, ledger.target_entity_id, ledger.result = 'COMMITTED', str(row.pk), result
    ledger.save(update_fields=('status', 'target_entity_id', 'result', 'updated_at'))
    return {'contractVersion': CONTRACT, 'factSource': 'server', 'row': _present(row),
        'idempotentReplay': False, 'writeRequestId': ledger.pk, 'auditId': audit.pk,
        'businessWriteCount': 1, 'auditWriteCount': 1, 'stateTransitionWriteCount': transitions}

def _mutate(function):
    def run(**kwargs):
        try:
            with transaction.atomic():
                return function(**kwargs)
        except IntegrityError as error:
            raise TimePolicyError('POLICY_CONFLICT', '并发范围、修订或单一后继冲突。') from error
        except OperationalError as error:
            if 'locked' in str(error).lower():
                raise TimePolicyError('POLICY_CONFLICT', '并发写入冲突；本次未提交。') from error
            raise
        except ValidationError as error:
            raise TimePolicyError('POLICY_INVALID', '制造时间物理记录未通过原生校验。',
                {'errors': _model_issues(error)}) from error
    return run

def _numbered_input(actor, payload, old):
    """Allocate only after replay; keep the original request as its audit input."""
    result = deepcopy(payload)
    if result.get('code') is not None and not isinstance(result['code'], str):
        _fail('POLICY_INVALID', '配置编号必须为文字；新建编号由服务端产生。', path='code')
    owner = old
    if owner is None and payload.get('predecessorId') is not None:
        try:
            owner = _row(actor, payload['predecessorId'], lock=True)
        except TimePolicyError as error:
            if error.code in {'POLICY_INVALID', 'POLICY_NOT_FOUND'}:
                _fail(error.code, '前驱版本身份无效、不存在或不属于当前公司。', path='predecessorId')
            raise
        _verify(owner)
        if owner.status != 'confirmed':
            _fail('POLICY_REFERENCE_INVALID', '后继只能引用本公司已确认前驱。', path='predecessorId')
    if owner is not None:
        supplied = result.get('code')
        if supplied not in (None, '', owner.code):
            _fail('POLICY_SCOPE_IMMUTABLE', '已有草稿及修订必须沿用原编号。', path='code')
        result['code'] = owner.code
        return result
    rule, _ = CodeRule.objects.select_for_update().get_or_create(
        company_id=actor.company_id, entity_type=NUMBER_ENTITY,
        defaults={'prefix': 'MTP-', 'date_format': '', 'seq_length': 8, 'current_seq': 0})
    if (not isinstance(rule.prefix, (str, type(None)))
            or len(rule.prefix or '') > 20 or not isinstance(rule.date_format, (str, type(None)))
            or len(rule.date_format or '') > 20 or type(rule.seq_length) is not int
            or not 1 <= rule.seq_length <= 32 or type(rule.current_seq) is not int or rule.current_seq < 0):
        _fail('CODE_RULE_INVALID', '现有工作制度编号规则不合法，未自动覆盖或重置。')
    code = CodeRule.next_code(entity_type=NUMBER_ENTITY, company_id=actor.company_id)
    if not code or len(code) > 80 or Policy.objects.filter(company_id=actor.company_id, code=code).exists():
        _fail('POLICY_CODE_CONFLICT', '自动编号与已有配置冲突，本次未保存；旧编号未改变。')
    result['code'] = code
    return result

def _name_row(actor, option_id, *, lock=False):
    if type(option_id) is not int or option_id <= 0:
        _fail('NAME_OPTION_INVALID', '参考名称身份必须为正式正整数。', path='optionId')
    query = NameOption.objects.select_for_update() if lock else NameOption.objects
    row = query.filter(pk=option_id, company_id=actor.company_id).first()
    if row is None:
        _fail('NAME_OPTION_NOT_FOUND', '参考名称不存在或不属于当前公司。', path='optionId')
    return row

def _verify_name_option(row):
    audits = list(OrganizationOperatingAuditRecord.objects.filter(
        organization_id=row.company_id, target_type=NAME_OBJECT, target_id=row.pk).order_by('pk'))
    if len(audits) != row.version:
        _fail('NAME_OPTION_PROOF_INVALID', '参考名称版本与维护审计数量不一致。')
    previous, identity_id = {}, None
    for audit in audits:
        context = (audit.after_snapshot or {}).get('importContext', {})
        ledger = MasterDataWriteRequest.objects.select_related('source_identity').filter(
            pk=context.get('writeRequestId')).first()
        after = (audit.after_snapshot or {}).get('state', {})
        if (context.get('contractVersion') != NAME_CONTRACT or audit.action_code != RESOURCE
                or not ledger or ledger.status != 'COMMITTED' or ledger.entity_type != NAME_ENTITY
                or ledger.organization_id != row.company_id or ledger.target_entity_id != str(row.pk)
                or ledger.action_code != RESOURCE or ledger.result.get('auditId') != audit.pk
                or ledger.result.get('optionId') != row.pk or ledger.result.get('version') != after.get('version')
                or ledger.audit_metadata.get('operatorId') != audit.actor_id
                or ledger.request_hash != _hash(ledger.audit_metadata.get('request'))
                or (audit.before_snapshot or {}).get('state') != previous
                or not (audit.after_snapshot or {}).get('authorization', {}).get('allowed')):
            _fail('NAME_OPTION_PROOF_INVALID', '参考名称维护账本、审计或请求证明不一致。')
        identity = ledger.source_identity
        if (identity.organization_id != row.company_id or identity.target_entity_type != NAME_ENTITY
                or identity.target_entity_id != str(row.pk) or identity.mapping_status != 'MATCH'
                or identity.source_system != 'PCE_SYSTEM' or identity.source_type != 'MANUFACTURING_TIME_POLICY_NAME'
                or identity.source_object_type != NAME_OBJECT or identity_id not in (None, identity.pk)):
            _fail('NAME_OPTION_PROOF_INVALID', '参考名称真实公司身份不一致。')
        identity_id, previous = identity.pk, deepcopy(after)
    if previous != _state(row):
        _fail('NAME_OPTION_PROOF_INVALID', '参考名称当前事实与最后已提交审计不一致。')
    return audits[-1]

def _present_name_option(row):
    _verify_name_option(row)
    return {'id': row.pk, 'companyId': row.company_id, 'name': row.name, 'isActive': row.is_active,
        'sortOrder': row.sort_order, 'version': row.version, 'createdAt': _json(row.created_at),
        'updatedAt': _json(row.updated_at), 'statusLabel': '可选' if row.is_active else '已停用'}

@transaction.atomic
def list_name_options(*, user, include_inactive=True):
    actor, _, _, _ = _actor(user)
    query = NameOption.objects.filter(company_id=actor.company_id).order_by('sort_order', 'pk')
    if not include_inactive:
        query = query.filter(is_active=True)
    return [_present_name_option(row) for row in query]

def _name_result(actor, ledger, row, *, replay):
    options = list_name_options(user=actor)
    return {'contractVersion': NAME_CONTRACT, 'factSource': 'server', 'nameOption': _present_name_option(row),
        'nameOptions': options, 'choices': {'nameOptions': [item for item in options if item['isActive']]},
        'idempotentReplay': replay, 'writeRequestId': ledger.pk, 'auditId': ledger.result['auditId'],
        'businessWriteCount': 0 if replay else 1, 'auditWriteCount': 0 if replay else 1,
        'referenceOptionWriteCount': 0 if replay else 1, 'stateTransitionWriteCount': 0}

@_mutate
def save_name_option(*, user, name, idempotency_key, reason, option_id=None,
                     expected_version=None, is_active=True, sort_order=0):
    reason = _input(idempotency_key, reason)
    actor, decision, chain, action = _actor(user, kind=Policy.Kind.SHARED_ARRANGEMENT, write=True)
    Company.objects.select_for_update().get(pk=actor.company_id)
    request = {'intent': 'saveNameOption', 'optionId': option_id, 'expectedVersion': expected_version,
        'name': name, 'isActive': is_active, 'sortOrder': sort_order, 'reason': reason, 'operatorId': actor.pk}
    ledger = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=actor.company_id, action_code=action, idempotency_key=idempotency_key).first()
    if ledger:
        if ledger.status != 'COMMITTED' or ledger.entity_type != NAME_ENTITY or ledger.request_hash != _hash(request):
            _fail('IDEMPOTENCY_CONFLICT', '同一幂等键必须绑定完全相同的已提交请求。')
        return _name_result(actor, ledger, _name_row(actor, int(ledger.target_entity_id), lock=True), replay=True)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 160:
        _fail('NAME_OPTION_INVALID', '请填写不超过160字的参考名称。', path='name')
    if type(is_active) is not bool:
        _fail('NAME_OPTION_INVALID', '请明确参考名称是否可选。', path='isActive')
    if type(sort_order) is not int or not 0 <= sort_order <= 2147483647:
        _fail('NAME_OPTION_INVALID', '显示顺序必须为非负整数。', path='sortOrder')
    row = _name_row(actor, option_id, lock=True) if option_id is not None else None
    if type(expected_version) is not int or expected_version != (row.version if row else 0):
        _fail('REVISION_CONFLICT', '参考名称版本已变化，请读取当前事实。', path='expectedVersion')
    last_audit = _verify_name_option(row) if row else None
    before = _state(row) if row else {}
    if NameOption.objects.filter(company_id=actor.company_id, name=name.strip()).exclude(pk=row.pk if row else None).exists():
        _fail('NAME_OPTION_CONFLICT', '当前公司已有相同参考名称，请复用已有项。', path='name')
    if row is None:
        row = NameOption(company_id=actor.company_id, name=name.strip(), is_active=is_active, sort_order=sort_order)
    else:
        row.name, row.is_active, row.sort_order, row.version = name.strip(), is_active, sort_order, row.version + 1
    token = _name_write_guard.set(True)
    try:
        row.save()
    finally:
        _name_write_guard.reset(token)
    if last_audit:
        old_ledger_id = last_audit.after_snapshot['importContext']['writeRequestId']
        identity = MasterDataWriteRequest.objects.get(pk=old_ledger_id).source_identity
    else:
        identity = ExternalIdentity.objects.create(organization_id=actor.company_id, source_system='PCE_SYSTEM',
            source_type='MANUFACTURING_TIME_POLICY_NAME', source_object_type=NAME_OBJECT,
            external_id=str(row.pk), target_entity_type=NAME_ENTITY, target_entity_id=str(row.pk), mapping_status='MATCH',
            source_fingerprint=_hash({'companyId': actor.company_id, 'optionId': row.pk}),
            audit_metadata={'contractVersion': NAME_CONTRACT})
    ledger = MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=action,
        entity_type=NAME_ENTITY, idempotency_key=idempotency_key, request_hash=_hash(request), source_identity=identity,
        audit_metadata={'operatorId': actor.pk, 'request': _json(request), 'contractVersion': NAME_CONTRACT})
    audit = _audit(user=actor, organization_id=actor.company_id, action_code=action, instance=row,
        before=before, after=_state(row), reason=reason, authorization=decision, execution_chain=chain,
        audit_context={'contractVersion': NAME_CONTRACT, 'writeRequestId': ledger.pk, 'intent': 'saveNameOption'})
    ledger.status, ledger.target_entity_id = 'COMMITTED', str(row.pk)
    ledger.result = {'optionId': row.pk, 'version': row.version, 'auditId': audit.pk}
    ledger.save(update_fields=('status', 'target_entity_id', 'result', 'updated_at'))
    return _name_result(actor, ledger, row, replay=False)

def _name_reference_data():
    value = json.loads(Path(__file__).with_name('manufacturing_time_policy_name_references.json').read_text(encoding='utf-8'))
    names = value.get('names') if isinstance(value, dict) else None
    if (not isinstance(value, dict) or value.get('contractVersion') != NAME_BATCH_CONTRACT
            or not isinstance(names, list) or not names
            or any(not isinstance(name, str) or not name.strip() or name != name.strip() or len(name) > 160 for name in names)
            or len(names) != len(set(names))):
        _fail('NAME_REFERENCE_DATA_INVALID', '受审参考名称数据不完整，未建立名称。')
    return value

def _name_batch_result(actor, ledger, *, replay):
    result = deepcopy(ledger.result)
    audit = OrganizationOperatingAuditRecord.objects.filter(pk=result.get('auditId')).first()
    identity = ledger.source_identity
    if (not audit or audit.organization_id != actor.company_id or audit.target_type != 'Company'
            or audit.target_id != actor.company_id or audit.action_code != RESOURCE
            or audit.after_snapshot.get('importContext', {}).get('writeRequestId') != ledger.pk
            or audit.after_snapshot.get('importContext', {}).get('contractVersion') != NAME_BATCH_CONTRACT
            or audit.before_snapshot.get('state') != audit.after_snapshot.get('state')
            or audit.after_snapshot.get('importContext', {}).get('optionIds') != result.get('optionIds')
            or audit.after_snapshot.get('importContext', {}).get('companyFieldWriteCount') != 0
            or not audit.after_snapshot.get('authorization', {}).get('allowed')
            or identity.organization_id != actor.company_id or identity.target_entity_type != NAME_BATCH_ENTITY
            or identity.target_entity_id != str(actor.company_id) or identity.mapping_status != 'MATCH'
            or identity.source_system != 'PCE_SYSTEM' or identity.source_type != 'MANUFACTURING_TIME_POLICY_NAME_SET'
            or identity.source_object_type != 'Company' or identity.source_fingerprint != ledger.request_hash
            or ledger.organization_id != actor.company_id or ledger.entity_type != NAME_BATCH_ENTITY
            or ledger.action_code != RESOURCE or ledger.audit_metadata.get('operatorId') != audit.actor_id
            or ledger.request_hash != _hash(ledger.audit_metadata.get('request'))
            or ledger.target_entity_id != str(actor.company_id) or ledger.status != 'COMMITTED'
            or not isinstance(result.get('optionIds'), list) or not result['optionIds']
            or any(type(pk) is not int or pk <= 0 for pk in result['optionIds'])
            or len(result['optionIds']) != len(set(result['optionIds']))
            or type(result.get('createdCount')) is not int or type(result.get('reusedCount')) is not int
            or result.get('createdCount', -1) < 0 or result.get('reusedCount', -1) < 0
            or result.get('createdCount', -1) + result.get('reusedCount', -1) != len(result['optionIds'])):
        _fail('NAME_OPTION_PROOF_INVALID', '建立名称参考的真实公司、账本或审计不一致。')
    for pk in result.get('optionIds', []):
        _verify_name_option(_name_row(actor, pk))
    options = list_name_options(user=actor)
    return {'factSource': 'server', 'nameOptions': options,
        'choices': {'nameOptions': [row for row in options if row['isActive']]},
        'optionIds': result['optionIds'], 'createdCount': result['createdCount'], 'reusedCount': result['reusedCount'],
        'countsAreHistorical': replay, 'idempotentReplay': replay, 'writeRequestId': ledger.pk,
        'auditId': audit.pk, 'businessWriteCount': 0 if replay else result['createdCount'],
        'referenceOptionWriteCount': 0 if replay else result['createdCount'],
        'auditWriteCount': 0 if replay else result['createdCount'] + 1, 'companyFieldWriteCount': 0,
        'stateTransitionWriteCount': 0}

@_mutate
def ensure_name_options(*, user, idempotency_key, reason):
    """An explicit company-scoped reference operation, never GET initialization."""
    reason = _input(idempotency_key, reason)
    actor, decision, chain, action = _actor(user, kind=Policy.Kind.SHARED_ARRANGEMENT, write=True)
    company = Company.objects.select_for_update().get(pk=actor.company_id)
    data = _name_reference_data()
    request = {'intent': 'ensureNameOptions', 'reason': reason, 'operatorId': actor.pk,
        'companyId': actor.company_id, 'referenceDataHash': _hash(data)}
    ledger = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=actor.company_id, action_code=action, idempotency_key=idempotency_key).first()
    if ledger:
        if ledger.entity_type != NAME_BATCH_ENTITY or ledger.request_hash != _hash(request):
            _fail('IDEMPOTENCY_CONFLICT', '同一幂等键必须绑定完全相同的建立名称参考请求。')
        return _name_batch_result(actor, ledger, replay=True)
    ids, created = [], 0
    for index, name in enumerate(data['names']):
        row = NameOption.objects.filter(company_id=actor.company_id, name=name).first()
        if row:
            _verify_name_option(row)
            ids.append(row.pk)
            continue
        key = 'name-reference-item:' + _hash({'companyId': actor.company_id, 'key': idempotency_key, 'index': index})
        saved = save_name_option(user=actor, name=name, is_active=True, sort_order=index,
            expected_version=0, idempotency_key=key, reason=reason)
        ids.append(saved['nameOption']['id'])
        created += 1
    identity = ExternalIdentity.objects.create(organization_id=actor.company_id, source_system='PCE_SYSTEM',
        source_type='MANUFACTURING_TIME_POLICY_NAME_SET', source_object_type='Company',
        external_id=_hash({'companyId': actor.company_id, 'key': idempotency_key}),
        target_entity_type=NAME_BATCH_ENTITY, target_entity_id=str(actor.company_id), mapping_status='MATCH',
        source_fingerprint=_hash(request), audit_metadata={'contractVersion': NAME_BATCH_CONTRACT})
    ledger = MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=action,
        entity_type=NAME_BATCH_ENTITY, idempotency_key=idempotency_key, request_hash=_hash(request), source_identity=identity,
        audit_metadata={'operatorId': actor.pk, 'request': _json(request), 'contractVersion': NAME_BATCH_CONTRACT})
    # The real Company is the scope target only; none of its fields is changed.
    state = _state(company)
    audit = _audit(user=actor, organization_id=actor.company_id, action_code=action, instance=company,
        before=state, after=state, reason=reason, authorization=decision, execution_chain=chain,
        audit_context={'contractVersion': NAME_BATCH_CONTRACT, 'writeRequestId': ledger.pk,
            'intent': 'ensureNameOptions', 'optionIds': ids, 'companyFieldWriteCount': 0})
    ledger.status, ledger.target_entity_id = 'COMMITTED', str(actor.company_id)
    ledger.result = {'optionIds': ids, 'createdCount': created, 'reusedCount': len(ids) - created, 'auditId': audit.pk}
    ledger.save(update_fields=('status', 'target_entity_id', 'result', 'updated_at'))
    return _name_batch_result(actor, ledger, replay=False)

@_mutate
def save_draft(*, user, payload, idempotency_key, reason, policy_id=None, expected_revision=None):
    reason = _input(idempotency_key, reason)
    if policy_id is not None and (type(policy_id) is not int or policy_id <= 0):
        _fail('POLICY_INVALID', '版本身份必须为正式正整数ID。')
    if not isinstance(payload, dict):
        _fail('POLICY_INVALID', '必须提交结构化时间配置。')
    actor, decision, chain, action = _actor(user, kind=payload.get('kind'), write=True)
    Company.objects.select_for_update().get(pk=actor.company_id)
    request = {'intent': 'saveDraft', 'policyId': policy_id, 'expectedRevision': expected_revision,
        'policy': deepcopy(payload), 'reason': reason, 'operatorId': actor.pk}
    replay = _replay(actor, action, idempotency_key, request)
    if replay:
        return replay
    old = _row(actor, policy_id, lock=True) if policy_id else None
    if old:
        _verify(old)
        if old.status != 'draft':
            _fail('POLICY_IMMUTABLE', '已确认版本不得覆盖。')
        if type(expected_revision) is not int or expected_revision != old.version:
            _fail('REVISION_CONFLICT', '草稿修订已变化，请读取当前正式事实。')
    elif expected_revision is not None and (type(expected_revision) is not int or expected_revision != 0):
        _fail('REVISION_CONFLICT', '新版本不能提交既有乐观版本。')
    row, _ = _build(actor, _numbered_input(actor, payload, old), current=old)
    before = _state(old) if old else {}
    if old is None:
        if Policy.objects.filter(company_id=actor.company_id, kind=row.kind,
                scope_key=row.scope_key, revision=row.revision).exists():
            _fail('POLICY_CONFLICT', '同范围该修订已存在，不能换编码另建权威。')
        identity = ExternalIdentity.objects.create(organization_id=actor.company_id,
            source_system='PCE_SYSTEM', source_type='MANUFACTURING_TIME_POLICY', source_object_type=OBJECT,
            external_id=f'{row.scope_key}:{row.revision}', target_entity_type=ENTITY, mapping_status='CREATE',
            source_fingerprint=_hash({'scope': _scope(row), 'revision': row.revision}),
            audit_metadata={'contractVersion': CONTRACT, 'scope': _scope(row), 'revision': row.revision})
    else:
        identity = old.creation_write_request.source_identity
    ledger = MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=action,
        entity_type=ENTITY, idempotency_key=idempotency_key, request_hash=_hash(request), source_identity=identity,
        audit_metadata={'operatorId': actor.pk, 'request': _json(request), 'contractVersion': CONTRACT})
    token = _write_guard.set(True)
    try:
        if old is None:
            fields = _content(row)
            fields.update(version=1, content_hash=row.content_hash, created_by=actor, updated_by=actor,
                creation_write_request=ledger)
            row = create_business_object_with_initial_state(model=Policy, initial_state='draft', **fields)
        else:
            for key in _content(row):
                setattr(old, key, deepcopy(getattr(row, key)))
            old.content_hash, old.version, old.updated_by = row.content_hash, row.version, actor
            old.save()
            row = old
    finally:
        _write_guard.reset(token)
    audit = _audit(user=actor, organization_id=actor.company_id, action_code=action, instance=row,
        before=before, after=_state(row), reason=reason, authorization=decision, execution_chain=chain,
        audit_context={'contractVersion': CONTRACT, 'writeRequestId': ledger.pk, 'intent': 'saveDraft'})
    if old is None:
        record_projected_business_transition(object_type=OBJECT, object_id=row.pk, source_state='',
            target_state='draft', action_code=action, operator=actor, reason=reason,
            audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions=(('', 'draft'),))
        identity.target_entity_id, identity.mapping_status = str(row.pk), 'MATCH'
        identity.save(update_fields=('target_entity_id', 'mapping_status', 'last_seen'))
    return _commit(ledger, row, audit, transitions=1 if old is None else 0)

def _confirmed_scope(row):
    return Policy.objects.select_for_update().filter(company_id=row.company_id, kind=row.kind,
        scope_key=row.scope_key, status='confirmed').order_by('revision', 'pk')

def _check_chain(row):
    confirmed = list(_confirmed_scope(row))
    for candidate in confirmed:
        _verify(candidate)
    if not confirmed:
        if row.predecessor_id is not None or row.revision != 1:
            _fail('POLICY_CHAIN_INVALID', '首个确认版本必须为第一修订且无前驱。')
        return
    tip = confirmed[-1]
    if (row.predecessor_id != tip.pk or row.revision != tip.revision + 1
            or row.effective_from <= tip.effective_from):
        _fail('POLICY_CHAIN_INVALID', '后继只能接续同范围链尾且边界严格递增。')

@_mutate
def confirm(*, user, policy_id, expected_content_hash, idempotency_key, reason, confirmation_basis):
    reason = _input(idempotency_key, reason)
    if not isinstance(confirmation_basis, str) or not confirmation_basis.strip() or len(confirmation_basis) > 1000:
        _fail('CONFIRMATION_BASIS_REQUIRED', '确认必须明确记录业务依据。')
    actor, _, _, _ = _actor(user)
    Company.objects.select_for_update().get(pk=actor.company_id)
    row = _row(actor, policy_id, lock=True)
    actor, decision, chain, action = _actor(actor, kind=row.kind, write=True)
    request = {'intent': 'confirm', 'policyId': policy_id, 'expectedContentHash': expected_content_hash,
        'reason': reason, 'confirmationBasis': confirmation_basis.strip(), 'operatorId': actor.pk}
    replay = _replay(actor, action, idempotency_key, request)
    if replay:
        return replay
    _verify(row)
    if row.status != 'draft':
        _fail('POLICY_IMMUTABLE', '已确认版本不可重复转换。')
    if expected_content_hash != row.content_hash:
        _fail('CONTENT_CHANGED', '确认内容已变化，禁止确认旧页面事实。')
    validation = _validation(row, strict=True)
    if not validation['ready']:
        _fail('POLICY_INCOMPLETE', '配置尚未完整，保留待完善草稿。', errors=validation.get('errors', []))
    _check_chain(row)
    before = _state(row)
    ledger = MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=action,
        entity_type=ENTITY, idempotency_key=idempotency_key, request_hash=_hash(request),
        source_identity=row.creation_write_request.source_identity,
        audit_metadata={'operatorId': actor.pk, 'request': _json(request), 'contractVersion': CONTRACT})
    token = _write_guard.set(True)
    try:
        row.confirmed_by, row.confirmed_at = actor, timezone.now()
        row.confirmation_basis, row.confirmation_write_request, row.updated_by = confirmation_basis.strip(), ledger, actor
        row.save(update_fields=('confirmed_by', 'confirmed_at', 'confirmation_basis', 'confirmation_write_request', 'updated_by', 'updated_at'))
        after = _state(row)
        after.update(status='confirmed', version=row.version + 1)
        audit = _audit(user=actor, organization_id=actor.company_id, action_code=action, instance=row,
            before=before, after=after, reason=reason, authorization=decision, execution_chain=chain,
            audit_context={'contractVersion': CONTRACT, 'writeRequestId': ledger.pk, 'intent': 'confirm'})
        row.confirmation_audit = audit
        row.save(update_fields=('confirmation_audit',))
        transition_business_object(business_object=row, object_type=OBJECT, source_state='draft', target_state='confirmed',
            action_code=action, operator=actor, reason=reason, audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
            allowed_transitions=(('draft', 'confirmed'),), updated_at_field=None)
    finally:
        _write_guard.reset(token)
    return _commit(ledger, row, audit, transitions=1)

@transaction.atomic
def resolve_scope(*, user, kind, on_date, work_center_id=None, operation_id=None, standard_capacity_id=None, code=None):
    actor, _, _, _ = _actor(user)
    day = _date(on_date, 'onDate')
    if day is None or kind not in Policy.Kind.values:
        _fail('POLICY_SCOPE_REQUIRED', '必须明确配置类型、业务日期和完整范围。')
    probe = Policy(company_id=actor.company_id, kind=kind, code=code or '',
        work_center_id=work_center_id, operation_id=operation_id, standard_capacity_id=standard_capacity_id)
    if (kind == Policy.Kind.SHARED_ARRANGEMENT and not code
            or kind == Policy.Kind.WC_APPLICATION and not work_center_id
            or kind == Policy.Kind.OPERATION_RESTRICTION and not operation_id
            or kind == Policy.Kind.CAPACITY_TIME_BASIS and not standard_capacity_id):
        _fail('POLICY_SCOPE_REQUIRED', '必须指定真实的配置适用范围。')
    rows = list(Policy.objects.filter(company_id=actor.company_id, kind=kind,
        scope_key=_hash(_scope(probe)), status='confirmed').order_by('revision', 'pk'))
    previous = None
    candidates = []
    for index, row in enumerate(rows):
        _verify(row)
        if ((previous is None and (row.revision != 1 or row.predecessor_id))
                or previous is not None and (row.predecessor_id != previous.pk
                    or row.revision != previous.revision + 1 or row.effective_from <= previous.effective_from)):
            _fail('POLICY_CHAIN_INVALID', '配置版本链断裂、分叉或边界倒置。')
        end = row.effective_to + timedelta(days=1) if row.effective_to else None
        cutover = rows[index + 1].effective_from if index + 1 < len(rows) else None
        logical_end = min(end, cutover) if end and cutover else end or cutover
        if row.effective_from <= day and (logical_end is None or day < logical_end):
            candidates.append((row, logical_end))
        previous = row
    if len(candidates) != 1:
        _fail('POLICY_SCOPE_MISSING' if not candidates else 'POLICY_CONFLICT', '该业务日没有唯一有效的已确认配置。')
    row, logical_end = candidates[0]
    if row.kind == Policy.Kind.WC_APPLICATION:
        selected = resolve_scope(user=actor, kind=Policy.Kind.SHARED_ARRANGEMENT, code=row.shared_version.code, on_date=day)
        if selected['row']['id'] != row.shared_version_id:
            _fail('POLICY_REFERENCE_EXPIRED', '中心明确引用的制度版本在该日期已失效；不得自动取后继。')
    return {'contractVersion': CONTRACT, 'factSource': 'server', 'row': _present(row),
        'resolvedDate': day.isoformat(), 'logicalEffectiveToExclusive': _json(logical_end),
        'businessWriteCount': 0, 'auditWriteCount': 0}
