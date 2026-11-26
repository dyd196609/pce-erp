"""Native append-only object decisions over immutable V1 applicability roots."""
from copy import deepcopy

from django.db import IntegrityError, transaction

CONTRACT = 'PCE-ROUTING-OBJECT-APPLICABILITY-CORRECTION-V1'
PROOF_CONTRACT = 'PCE-ROUTING-OBJECT-APPLICABILITY-PROOF-V2'
ACTION = 'pde.routing_step.correct_object_applicability'
ENTITY_TYPE = 'routing-step-object-applicability-correction'
SOURCE_OBJECT_TYPE = 'ROUTING_STEP_OBJECT_APPLICABILITY_CORRECTION'


class CorrectionChainError(ValueError):
    """Pure graph rejection; converted to the original native domain error."""


def ordered_chain(nodes, root_id):
    """Typed FK graph only. Neither ID/time ordering nor audit JSON is a link."""
    if type(root_id) is not int or root_id <= 0:
        raise CorrectionChainError('invalid root ID')
    if not isinstance(nodes, list):
        raise CorrectionChainError('nodes must be an explicit list')
    if not nodes:
        return []
    by_id, children, first = {}, {}, []
    for row in nodes:
        if not isinstance(row, dict) or set(row) != {'id', 'predecessor_id', 'root_record_id'}:
            raise CorrectionChainError('invalid graph node shape')
        pk, parent = row['id'], row['predecessor_id']
        if (type(pk) is not int or pk <= 0 or pk in by_id
            or type(row['root_record_id']) is not int or row['root_record_id'] != root_id):
            raise CorrectionChainError('duplicate/invalid ID or different root')
        if parent is not None and (type(parent) is not int or parent <= 0 or parent == pk):
            raise CorrectionChainError('invalid predecessor or self cycle')
        by_id[pk] = row
        if parent is None:
            first.append(pk)
        else:
            if parent in children:
                raise CorrectionChainError('forked predecessor')
            children[parent] = pk
    if len(first) != 1 or any(parent not in by_id for parent in children):
        raise CorrectionChainError('missing/duplicate first node or missing predecessor')
    result, seen, current = [], set(), first[0]
    while current is not None:
        if current in seen:
            raise CorrectionChainError('cycle')
        seen.add(current)
        result.append(by_id[current])
        current = children.get(current)
    if seen != set(by_id):
        raise CorrectionChainError('disconnected or cyclic component')
    return result


def _native():
    # Lazy to keep the pure graph test independent of settings/models/DB.
    from . import routing_object_applicability_service
    return routing_object_applicability_service


def _fail(code, message, **details):
    _native()._fail(code, message, **details)


def _model():
    from django.apps import apps
    from django.db import connections, router
    try:
        model = apps.get_model('pde', 'RoutingStepObjectApplicabilityCorrection')
    except LookupError:
        model = None
    if model is None:
        _fail('OBJECT_CORRECTION_STRUCTURE_REQUIRED', '正式追加纠正结构尚未部署，禁止提交或推断纠正成功。')
    # Registration alone does not prove that a separately authorized migration
    # has deployed the physical table. This is read-only schema introspection;
    # do not query an absent business table or silently restore the old NA.
    alias = router.db_for_read(model)
    connection = connections[alias]
    from .routing_read_context import _current
    from .capacity_evidence_read_scope import evidence_cache
    from .operation_requirement_service import _read_once

    request = _current.get() or {}
    cache = evidence_cache(request.get('__reader_company_id__'))
    if cache is not None and cache.database_alias == alias:
        # The successful structure check belongs to this atomic read only.
        _read_once(cache, ('routing_correction_schema', alias, model._meta.db_table),
            lambda: _verify_structure(connection, model))
    else:
        _verify_structure(connection, model)
    return model


def _verify_structure(connection, model):
    table = model._meta.db_table
    if table not in connection.introspection.table_names():
        _fail('OBJECT_CORRECTION_STRUCTURE_REQUIRED', '纠正模型已注册但正式存储未部署，禁止查询缺表或提交。')
    with connection.cursor() as cursor:
        columns = {column.name for column in connection.introspection.get_table_description(cursor, table)}
        constraints = connection.introspection.get_constraints(cursor, table)
    missing = sorted({field.column for field in model._meta.concrete_fields} - columns)
    unique_columns = {tuple(row.get('columns') or ()) for row in constraints.values() if row.get('unique')}
    first = constraints.get('pde_obj_corr_first_unique', {})
    checks = ('pde_obj_corr_decision_valid', 'pde_obj_corr_hash_required', 'pde_obj_corr_no_self')
    if (missing or not first.get('unique') or first.get('columns') != ['root_record_id']
        or ('predecessor_id',) not in unique_columns or ('write_request_id',) not in unique_columns
        or any(not constraints.get(name, {}).get('check') for name in checks)):
        _fail('OBJECT_CORRECTION_STRUCTURE_REQUIRED', '纠正表的正式列或必要唯一／检查约束未完整部署。',
            missingColumns=missing)


def _snapshot(record):
    from .production_foundation_service import _snapshot as native_snapshot
    return native_snapshot(record)


def _hash(value):
    return _native()._hash(value)


def _record_hash(record, proof):
    return _hash({'record': _snapshot(record), 'committedProof': proof})


def _root(scope, root_id):
    root = _native()._model().objects.filter(pk=root_id,
        production_plan_id=scope['plan'].pk, routing_step_id=scope['step'].pk).first()
    if root is None:
        _fail('OBJECT_CORRECTION_ROOT_INVALID', '纠正根记录不在当前固定计划和步骤范围。')
    # This is the unmodified V1 native proof and its original serialization.
    proof = _native()._committed_proof(root, scope)
    return root, proof, _record_hash(root, proof)


def _anchor(root, context, root_hash, predecessor, predecessor_hash):
    return {'contractVersion': CONTRACT, 'context': context, 'rootRecordId': root.pk,
        'rootRecordHash': root_hash,
        'predecessorCorrectionId': predecessor.pk if predecessor else None,
        'predecessorRecordHash': predecessor_hash}


def _external_id(anchor):
    return 'RoutingObjectCorrection:' + _hash(anchor)


def _payload(anchor, decision, basis, reason):
    return {**anchor, 'decision': decision, 'basis': basis, 'reason': reason}


def _result(row, audit_id, identity_id, source):
    return {'contractVersion': CONTRACT, 'recordType': type(row).__name__, 'recordId': row.pk,
        'rootRecordId': row.root_record_id, 'predecessorCorrectionId': row.predecessor_id,
        'contextHash': row.context_hash, 'decision': row.decision,
        'sourceFactId': source['id'], 'sourceSnapshotHash': source['sourceSnapshotHash'],
        'auditId': audit_id, 'writeRequestId': row.write_request_id, 'sourceIdentityId': identity_id,
        'confirmedByUserId': row.created_by_id, 'idempotentReplay': False}


def _binding(row, scope, root, root_proof, root_hash, predecessor, predecessor_hash):
    """Valid while the new native ledger is RESERVED and audit not yet created."""
    from system.models import User
    native = _native()
    obj = next((obj for obj in scope['objects'] if obj.pk == root.baseline_item_id), None)
    context = native._context(scope, obj) if obj else None
    if (context is None or row.root_record_id != root.pk or row.company_id != scope['company_id']
        or row.context_hash != root.context_hash or row.context_hash != _hash(context)
        or row.root_record_hash != root_hash or row.predecessor_hash != predecessor_hash
        or row.predecessor_id != (predecessor.pk if predecessor else None)
        or row.decision not in native.DECISIONS or not isinstance(row.reason, str) or not row.reason.strip()):
        _fail('OBJECT_CORRECTION_CONTEXT_DRIFT', '纠正根、前驱、公司、完整上下文或历史节点Hash不一致。')
    source = native._validate_basis(row.basis, scope, obj)
    # Never SELECT a full User or select_related(created_by).
    actor = User.objects.filter(pk=row.created_by_id).values('id', 'company_id', 'username').first()
    anchor = _anchor(root, context, root_hash, predecessor, predecessor_hash)
    ledger, identity = row.write_request, row.write_request.source_identity
    if identity is None:
        _fail('OBJECT_CORRECTION_LEDGER_INVALID', '纠正请求缺少原生来源身份。')
    if (not actor or actor['company_id'] != scope['company_id']
        or ledger.organization_id != scope['company_id'] or ledger.action_code != ACTION
        or ledger.entity_type != ENTITY_TYPE or not isinstance(ledger.audit_metadata, dict)
        or ledger.audit_metadata.get('operatorId') != row.created_by_id
        or ledger.request_hash != _hash(_payload(anchor, row.decision, row.basis, row.reason))
        or identity.organization_id != scope['company_id'] or identity.source_system != 'PCE_SYSTEM'
        or identity.source_type != 'ROUTING_VERSION_CONTROLLED_CHANGE'
        or identity.source_object_type != SOURCE_OBJECT_TYPE or identity.target_entity_type != ENTITY_TYPE
        or identity.external_id != _external_id(anchor) or identity.source_fingerprint != _hash(anchor)
        or not isinstance(identity.audit_metadata, dict)
        or identity.audit_metadata.get('fingerprintPayload') != anchor):
        _fail('OBJECT_CORRECTION_LEDGER_INVALID', '纠正的原生身份、请求Hash或办理人绑定不一致。')
    state = {'record': _snapshot(row), 'context': context, 'rootRecordProof': root_proof,
        'predecessorRecordHash': predecessor_hash,
        'previousDecision': predecessor.decision if predecessor else root.decision,
        'newDecision': row.decision}
    return context, anchor, source, actor, state


def _committed(row, scope, root, root_proof, root_hash, predecessor, predecessor_hash):
    from masterdata.models import ExternalIdentity, MasterDataWriteRequest
    from system.models import OrganizationOperatingAuditRecord
    from .routing_version_successor_service import ROUTING_PERMISSION
    context, anchor, source, actor, state = _binding(
        row, scope, root, root_proof, root_hash, predecessor, predecessor_hash)
    ledger, identity = row.write_request, row.write_request.source_identity
    if (ledger.status != MasterDataWriteRequest.Status.COMMITTED or ledger.target_entity_id != str(row.pk)
        or ledger.audit_metadata.get('contractVersion') != CONTRACT
        or identity.mapping_status != ExternalIdentity.MappingStatus.MATCH
        or identity.target_entity_id != str(row.pk) or identity.audit_metadata.get('contractVersion') != CONTRACT):
        _fail('OBJECT_CORRECTION_COMMIT_INVALID', '纠正没有精确已提交的原生身份和请求。')
    audits = list(OrganizationOperatingAuditRecord.objects.filter(organization_id=scope['company_id'],
        action_code=ACTION, target_type=type(row).__name__, target_id=row.pk))
    if len(audits) != 1:
        _fail('OBJECT_CORRECTION_AUDIT_INVALID', '纠正必须有唯一且指向本纠正记录类型的原生审计。')
    audit = audits[0]
    envelope = audit.after_snapshot if isinstance(audit.after_snapshot, dict) else {}
    authorization, chain = envelope.get('authorization'), envelope.get('executionChain')
    import_context = {'contractVersion': CONTRACT, 'contextHash': row.context_hash,
        'rootRecordId': root.pk, 'sourceFingerprint': _hash(anchor), 'requestHash': ledger.request_hash}
    if (audit.actor_id != row.created_by_id or audit.reason != row.reason[:300]
        or envelope.get('state') != state or envelope.get('factSource') != 'server'
        or audit.before_snapshot != {**envelope, 'state': {}}
        or not isinstance(authorization, dict) or authorization.get('allowed') is not True
        or authorization.get('actionCode') != ROUTING_PERMISSION
        or not _native()._organization_matches(authorization.get('organizationId'), scope['company_id'])
        or not isinstance(chain, dict) or chain.get('account') != actor['username']
        or any(type(chain.get(key)) is not int or chain[key] <= 0
            for key in ('employeeId', 'positionId', 'responsibilityId'))
        or envelope.get('importContext') != import_context):
        _fail('OBJECT_CORRECTION_AUDIT_MISMATCH', '纠正与原生审计的上下文、权限或责任链不一致。')
    result = _result(row, audit.pk, identity.pk, source)
    if ledger.result != result:
        _fail('OBJECT_CORRECTION_COMMIT_INVALID', '纠正记录与已提交幂等结果不一致。')
    return result


def read_chain(root, scope, *, lock=False):
    """All nodes must validate; a missing/bad node never restores the old NA."""
    from system.models import OrganizationOperatingAuditRecord
    root_proof = _native()._committed_proof(root, scope)
    root_hash = _record_hash(root, root_proof)
    model = _model()
    if lock:
        # Lock only correction rows; read related proofs separately so no
        # database-specific joined FOR UPDATE behavior is required.
        list(model.objects.select_for_update().filter(root_record_id=root.pk))
    rows = list(model.objects.filter(root_record_id=root.pk).select_related('write_request__source_identity'))
    by_id = {row.pk: row for row in rows}
    # Audit is consistency evidence, not the correction relationship authority.
    # A committed native correction audit whose typed row vanished/moved fails
    # closed instead of being interpreted as "this root was never corrected".
    audit_ids = set(OrganizationOperatingAuditRecord.objects.filter(
        organization_id=scope['company_id'], action_code=ACTION, target_type=model.__name__,
        after_snapshot__state__record__root_record_id=root.pk).values_list('target_id', flat=True))
    if {str(value) for value in audit_ids} != {str(value) for value in by_id}:
        _fail('OBJECT_CORRECTION_AUDIT_SET_MISMATCH', '纠正记录集合与原生提交审计集合不一致。')
    try:
        ordered = ordered_chain([{'id': row.pk, 'root_record_id': row.root_record_id,
            'predecessor_id': row.predecessor_id} for row in rows], root.pk)
    except CorrectionChainError as error:
        _fail('OBJECT_CORRECTION_CHAIN_INVALID', '纠正关系有缺失、分叉、循环或跨根引用。', graphError=str(error))
    history, predecessor, previous_hash = [], None, root_hash
    for item in ordered:
        row = by_id[item['id']]
        proof = _committed(row, scope, root, root_proof, root_hash, predecessor, previous_hash)
        history.append({'row': row, 'proof': proof, 'recordHash': _record_hash(row, proof)})
        predecessor, previous_hash = row, history[-1]['recordHash']
    return {'root': root, 'rootProof': root_proof, 'rootHash': root_hash, 'history': history,
        'current': predecessor, 'currentHash': previous_hash}


def effective_for_root(root, scope):
    """Shared consumer: no correction preserves the exact V1 result object."""
    chain = read_chain(root, scope)
    if not chain['history']:
        return root.decision, chain['rootProof'], deepcopy(root.basis), root.reason
    current = chain['history'][-1]
    proof = {'contractVersion': PROOF_CONTRACT, 'proofKind': 'FORMAL_APPEND_ONLY_CORRECTION',
        'baselineItemId': root.baseline_item_id, 'designItemId': root.design_item_id,
        'effectiveDecision': current['row'].decision, 'rootRecordProof': chain['rootProof'],
        'currentCorrectionProof': current['proof'],
        'history': [entry['proof'] for entry in chain['history']]}
    return current['row'].decision, proof, deepcopy(current['row'].basis), current['row'].reason


def validate_record_context(record):
    """Model clean, before the new row's native audit is inserted."""
    scope = _native()._load_scope(record.root_record.production_plan_id, record.root_record.routing_step_id)
    root, proof, root_hash = _root(scope, record.root_record_id)
    chain = read_chain(root, scope)
    return _binding(record, scope, root, proof, root_hash, chain['current'], chain['currentHash'])[0]


@transaction.atomic
def prepare_group(user, production_plan_id, routing_step_id, root_record_ids):
    """Pure native preparation; permission/execution chain is not bypassed."""
    from .routing_version_successor_service import _authorize
    scope = _native()._load_scope(production_plan_id, routing_step_id)
    _, authorization, execution_chain = _authorize(user, scope['output'].routing_version)
    if (not isinstance(root_record_ids, list) or not root_record_ids
        or any(type(value) is not int or value <= 0 for value in root_record_ids)
        or len(set(root_record_ids)) != len(root_record_ids)):
        _fail('OBJECT_CORRECTION_GROUP_INVALID', '必须提供无重复的正式根记录组。')
    results = []
    for root_id in root_record_ids:
        _native()._positive_id(root_id, 'rootRecordId')
        root, proof, root_hash = _root(scope, root_id)
        chain = read_chain(root, scope)
        context = _native()._context(scope, next(obj for obj in scope['objects'] if obj.pk == root.baseline_item_id))
        anchor = _anchor(root, context, root_hash, chain['current'], chain['currentHash'])
        results.append({'rootRecordId': root.pk, 'baselineItemId': root.baseline_item_id,
            'context': context, 'contextHash': root.context_hash, 'rootRecordProof': proof,
            'expectedCurrentCorrectionId': chain['current'].pk if chain['current'] else None,
            'expectedCurrentRecordHash': chain['currentHash'],
            'suggestedIdempotencyKey': 'routing-object-correction:v1:' + _hash(anchor)})
    return {'contractVersion': CONTRACT, 'objects': results, 'authorization': authorization,
        'executionChain': execution_chain, 'businessWriteCount': 0, 'auditWriteCount': 0}


@transaction.atomic
def correct_group(user, production_plan_id, routing_step_id, contributions, reason):
    """Original native authorization, atomic transaction and four-table write chain.

    All contributions are validated before the first new identity reservation.
    """
    from masterdata.models import ExternalIdentity, MasterDataWriteRequest
    from .production_foundation_service import _audit
    from .routing_version_successor_service import _authorize, _identity, _ledger
    native = _native()
    scope = native._load_scope(production_plan_id, routing_step_id, lock=True)
    organization_id, authorization, execution_chain = _authorize(user, scope['output'].routing_version)
    if not isinstance(reason, str) or not reason.strip():
        _fail('OBJECT_CORRECTION_REASON_REQUIRED', '追加纠正必须有明确办理原因。')
    reason = reason.strip()
    if not isinstance(contributions, list) or not contributions:
        _fail('OBJECT_CORRECTION_GROUP_INVALID', '必须提供非空精确纠正组。')
    prepared, roots_seen, objects_seen, keys_seen = [], set(), set(), set()
    for item in contributions:
        if not isinstance(item, dict) or set(item) != {'rootRecordId', 'baselineItemId', 'contextHash',
            'expectedCurrentCorrectionId', 'expectedCurrentRecordHash', 'decision', 'basis', 'idempotencyKey'}:
            _fail('OBJECT_CORRECTION_PAYLOAD_INVALID', '纠正必须提供精确版本化载荷字段。')
        root_id = native._positive_id(item['rootRecordId'], 'rootRecordId')
        obj_id = native._positive_id(item['baselineItemId'], 'baselineItemId')
        expected_id, key = item['expectedCurrentCorrectionId'], item['idempotencyKey']
        if expected_id is not None:
            native._positive_id(expected_id, 'expectedCurrentCorrectionId')
        if (root_id in roots_seen or obj_id in objects_seen or type(item['decision']) is not str
            or item['decision'] not in native.DECISIONS
            or not isinstance(key, str) or not key.strip() or key != key.strip() or len(key) > 160 or key in keys_seen):
            _fail('OBJECT_CORRECTION_GROUP_INVALID', '纠正对象、决定或稳定键无效/重复。')
        roots_seen.add(root_id)
        objects_seen.add(obj_id)
        keys_seen.add(key)
        list(native._model().objects.select_for_update().filter(pk=root_id))
        root, root_proof, root_hash = _root(scope, root_id)
        if root.baseline_item_id != obj_id or item['contextHash'] != root.context_hash:
            _fail('OBJECT_CORRECTION_CONTEXT_DRIFT', '纠正对象或完整上下文Hash与原记录不一致。')
        obj = next(obj for obj in scope['objects'] if obj.pk == obj_id)
        native._validate_basis(item['basis'], scope, obj)
        chain = read_chain(root, scope, lock=True)
        by_id = {entry['row'].pk: entry for entry in chain['history']}
        predecessor = by_id.get(expected_id, {}).get('row') if expected_id is not None else None
        if expected_id is not None and predecessor is None:
            _fail('OBJECT_CORRECTION_PREDECESSOR_INVALID', '期望前驱不在本根的完整原生链。')
        expected_hash = by_id[expected_id]['recordHash'] if expected_id is not None else root_hash
        if item['expectedCurrentRecordHash'] != expected_hash:
            _fail('OBJECT_CORRECTION_PREDECESSOR_DRIFT', '期望前驱或原记录Hash已变化。')
        context = native._context(scope, obj)
        anchor = _anchor(root, context, root_hash, predecessor, expected_hash)
        payload = _payload(anchor, item['decision'], deepcopy(item['basis']), reason)
        ledger = MasterDataWriteRequest.objects.select_for_update().filter(
            organization_id=organization_id, action_code=ACTION, idempotency_key=key).first()
        if ledger is not None:
            bound = [entry for entry in chain['history'] if entry['row'].write_request_id == ledger.pk]
            if len(bound) != 1 or ledger.request_hash != _hash(payload):
                _fail('OBJECT_CORRECTION_IDEMPOTENCY_CONFLICT', '原纠正键已绑定其他节点、范围或完整载荷。')
            # A historical exact replay remains historical even after a later
            # child exists. It never creates a node or changes the current leaf.
            prepared.append({'replay': {**bound[0]['proof'], 'idempotentReplay': True}})
            continue
        if expected_id != (chain['current'].pk if chain['current'] else None):
            _fail('OBJECT_CORRECTION_STALE_PREDECESSOR', '新纠正必须精确衔接唯一当前节点，禁止分叉或换键别名。')
        current_decision = chain['current'].decision if chain['current'] else root.decision
        if item['decision'] == current_decision:
            _fail('OBJECT_CORRECTION_NO_CHANGE', '当前版本只接受实际决定变化，不为相同决定建立新节点别名。')
        prepared.append({'root': root, 'rootProof': root_proof, 'rootHash': root_hash,
            'predecessor': predecessor, 'predecessorHash': expected_hash, 'context': context,
            'anchor': anchor, 'payload': payload, 'key': key})
    results, created = [], 0
    try:
        for item in prepared:
            if 'replay' in item:
                results.append(item['replay'])
                continue
            anchor, payload = item['anchor'], item['payload']
            identity, fingerprint = _identity(organization_id=organization_id, object_type=SOURCE_OBJECT_TYPE,
                external_id=_external_id(anchor), target_type=ENTITY_TYPE, fingerprint_payload=anchor)
            if (identity.target_entity_id or identity.mapping_status != ExternalIdentity.MappingStatus.CREATE
                or identity.source_fingerprint != fingerprint):
                _fail('OBJECT_CORRECTION_NODE_CONFLICT', '同一前驱纠正身份已经绑定，不能换键建立别名。')
            ledger = _ledger(organization_id=organization_id, action_code=ACTION, entity_type=ENTITY_TYPE,
                idempotency_key=item['key'], request_hash=_hash(payload), identity=identity, user=user)
            row = _model()(company_id=organization_id, root_record=item['root'], predecessor=item['predecessor'],
                context_hash=item['root'].context_hash, root_record_hash=item['rootHash'],
                predecessor_hash=item['predecessorHash'], decision=payload['decision'],
                basis=payload['basis'], reason=reason, created_by=user, write_request=ledger)
            row._object_applicability_correction_creation_authorized = True
            row.save()
            _, _, source, _, state = _binding(row, scope, item['root'], item['rootProof'],
                item['rootHash'], item['predecessor'], item['predecessorHash'])
            audit = _audit(user=user, organization_id=organization_id, action_code=ACTION, instance=row,
                before={}, after=state, reason=reason, authorization=authorization, execution_chain=execution_chain,
                audit_context={'contractVersion': CONTRACT, 'contextHash': row.context_hash,
                    'rootRecordId': item['root'].pk, 'sourceFingerprint': fingerprint, 'requestHash': ledger.request_hash})
            identity.target_entity_id, identity.mapping_status = str(row.pk), ExternalIdentity.MappingStatus.MATCH
            identity.audit_metadata = {'contractVersion': CONTRACT, 'fingerprintPayload': anchor}
            identity.full_clean()
            identity.save()
            result = _result(row, audit.pk, identity.pk, source)
            ledger.status, ledger.target_entity_id, ledger.result = MasterDataWriteRequest.Status.COMMITTED, str(row.pk), result
            ledger.audit_metadata = {'operatorId': user.pk, 'contractVersion': CONTRACT}
            ledger.save(update_fields=('status', 'target_entity_id', 'result', 'audit_metadata', 'updated_at'))
            _committed(row, scope, item['root'], item['rootProof'], item['rootHash'],
                item['predecessor'], item['predecessorHash'])
            results.append(result)
            created += 1
    except IntegrityError as error:
        # No query/retry after an IntegrityError. Raising leaves @atomic and
        # rolls back all new business/support rows in the submitted group.
        _fail('OBJECT_CORRECTION_CONCURRENT_CONFLICT', '并发节点/稳定键冲突；本组整体回滚且不自动换键重试。',
            errorType=type(error).__name__)
    return {'contractVersion': CONTRACT, 'productionPlanId': production_plan_id, 'routingStepId': routing_step_id,
        'createdCount': created, 'replayedCount': len(results) - created, 'objects': results,
        'statusLabel': '仅正式对象适用性追加纠正；不生成EOR或分配，不代表全路线投产通过'}
