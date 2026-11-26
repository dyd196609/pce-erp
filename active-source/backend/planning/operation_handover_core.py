"""Shared exact-number, transaction, proof and idempotency primitives.

Only the candidate's declared native environment can write. No source task,
report, receipt, completion or inventory object is changed by this module.
"""
from copy import deepcopy
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal, localcontext
from hashlib import sha256
import re
from django.db import connection, transaction, OperationalError
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from masterdata.models import MasterDataWriteRequest, ExternalIdentity
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition, transition_business_object)
from .mes_test_source_bridge import record_audit
from .mes_test_source_bridge import _hash, _fail
from .operation_handover_models import OperationQuantityAccount


def fail(code, message, status=409):
    _fail(code, message, status)


def number(value, *, positive=False, precision=None):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9][0-9]*)(\.[0-9]+)?', value):
        fail('HANDOVER_QUANTITY_INVALID', '数量须为非负规范十进制字符串，不接受浮点、负数或科学计数。', 400)
    if precision is not None and len(value.partition('.')[2]) > precision:
        fail('HANDOVER_UNIT_PRECISION', '数量超过正式来源单位精度；未截断输入。', 400)
    result = Decimal(value)
    if not result.is_finite() or result < 0 or positive and result == 0:
        fail('HANDOVER_QUANTITY_INVALID', '本次数量须为正式有效正数。', 400)
    return result


def text(value):
    result = format(Decimal(value), 'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


def add(*values):
    with localcontext() as ctx:
        ctx.prec = max(200, sum(len(str(v)) for v in values) + 20)
        return sum((Decimal(v) for v in values), Decimal(0))


def atoms(value, precision):
    with localcontext() as ctx:
        ctx.prec = max(200, len(str(value)) + 20)
        q = Decimal(value).scaleb(precision)
        if q != q.to_integral_value():
            fail('HANDOVER_UNIT_PRECISION', '数量不能表示为正式单位最小份额。', 400)
        return int(q)


def from_atoms(value, precision):
    with localcontext() as ctx:
        ctx.prec = max(200, len(str(value)) + 20)
        return Decimal(value).scaleb(-precision)


def occurred(value, *, not_before=None):
    if not isinstance(value, str) or not (stamp := parse_datetime(value)) or timezone.is_naive(stamp):
        fail('HANDOVER_ACTUAL_TIME_REQUIRED', '请明确填写含时区的实际发生时间。', 400)
    zone=timezone.get_default_timezone()
    now=timezone.now()
    now=now if timezone.is_aware(now) else timezone.make_aware(now,zone)
    before=not_before if not_before is None or timezone.is_aware(not_before) else timezone.make_aware(not_before,zone)
    if stamp > now or before and stamp < before:
        fail('HANDOVER_ACTUAL_TIME_INVALID', '实际时间不得为未来，也不得早于所引用的实际交出／开工。', 400)
    return stamp.astimezone(datetime_timezone.utc) if settings.USE_TZ else timezone.make_naive(stamp,zone)


def payload_guard(payload, allowed, required=()):
    if not isinstance(payload, dict) or set(payload) - set(allowed) or set(required) - set(payload):
        fail('HANDOVER_PAYLOAD_INVALID', '动作意图字段不完整或包含禁止字段。', 400)
    if not isinstance(payload.get('reason'), str) or not 2 <= len(payload['reason'].strip()) <= 300:
        fail('HANDOVER_REASON_REQUIRED', '请填写2至300字的真实操作原因。', 400)
    if not isinstance(payload.get('idempotencyKey'), str) or not 1 <= len(payload['idempotencyKey']) <= 120:
        fail('HANDOVER_IDEMPOTENCY_REQUIRED', '缺少有效原请求防重复标识。', 400)


def actor_for(user):
    from .operation_handover_permissions import actor_for as native
    return native(user)


def qualify(actor, action, wc, obj='OperationHandover', object_id=None, status='open', required=True):
    from .operation_handover_permissions import require_action, check_action
    call = require_action if required else check_action
    return call(user=actor, action_code=action, work_center_id=wc, object_type=obj,
                object_id=object_id, status=status)


def lock_accounts(actor, task_ids):
    """First SQL is a write on the new stable anchor, before any snapshot read."""
    if not connection.in_atomic_block:
        fail('HANDOVER_TRANSACTION_REQUIRED', '数量写入必须在完整原子事务内。')
    from .test_operation_start_service import _boundary as _execution_boundary
    _execution_boundary()
    result = {}
    for task_id in sorted(set(task_ids)):
        if type(task_id) is not int or task_id <= 0:
            fail('HANDOVER_TASK_INVALID', '正式任务身份须为正整数。', 400)
        if connection.vendor == 'sqlite':
            with connection.cursor() as cursor:
                cursor.execute('INSERT OR IGNORE INTO planning_operation_quantity_account '
                    '(company_id,task_id,revision,production_revision,release_revision,custody_revision,account_key,source_hash) '
                    "VALUES (%s,%s,0,0,0,0,'','')", [actor.company_id, task_id])
        else:
            OperationQuantityAccount.objects.get_or_create(company_id=actor.company_id, task_id=task_id)
        row = OperationQuantityAccount.objects.select_for_update().get(task_id=task_id)
        if row.company_id != actor.company_id:
            fail('HANDOVER_ACCOUNT_COMPANY_MISMATCH', '数量账户不在本公司范围。', 403)
        changed = OperationQuantityAccount.objects.filter(pk=row.pk, revision=row.revision).update(revision=row.revision + 1)
        if changed != 1:
            fail('HANDOVER_ACCOUNT_CHANGED', '数量账户已被其他动作改变，请只读重查。')
        row.revision += 1
        result[task_id] = row
    return result


def bump(account, kind):
    field = kind + '_revision'
    value = getattr(account, field) + 1
    if OperationQuantityAccount.objects.filter(pk=account.pk, revision=account.revision).update(**{field: value}) != 1:
        fail('HANDOVER_ACCOUNT_CHANGED', '数量账户版本变化，请只读重查。')
    setattr(account, field, value)


def strict_id(value, label='正式对象', *, nullable=False, zero=False):
    if nullable and value is None:return None
    if type(value) is not int or value<(0 if zero else 1):
        fail('HANDOVER_IDENTIFIER_INVALID',f'{label}须为准确正式整数，不能使用布尔值、小数或无效编号。',400)
    return value


def offset_iso(value):
    if timezone.is_naive(value):value=timezone.make_aware(value,timezone.get_default_timezone())
    return value.isoformat()


def assert_actual_qualification(actor,q,stamp):
    """Current permission is necessary; known formal dates must cover the action."""
    from .mes_test_source_bridge import _effective
    from system.models import Position,Department,PositionWorkflowResponsibility,UserRoleScopeAssignment
    from pfm.formal_employee import formal_employee_queryset
    from pde.work_center_responsibility_models import WorkCenterResponsibilityScope
    day=timezone.localtime(stamp,timezone.get_default_timezone()).date() if timezone.is_aware(stamp) else stamp.date()
    evidence=q.get('currentActorEvidence',{});records=[]
    employee=formal_employee_queryset(company_id=actor.company_id).filter(pk=evidence.get('employeeId')).first()
    if not employee:fail('HANDOVER_ACTUAL_ACTOR_UNPROVEN','实际动作须对应本公司真实员工。',403)
    if any(value is not None and day<value for value in (employee.hire_date,)) or any(value is not None and day>=value for value in (employee.leave_date,employee.resignation_date)):
        fail('HANDOVER_ACTUAL_DATE_AUTHORITY_INVALID','声明实际发生日不在员工正式有效任职日期内。',403)
    for model,key in ((Position,'positionId'),(Department,'departmentId'),
        (PositionWorkflowResponsibility,'workflowResponsibilityId'),(WorkCenterResponsibilityScope,'workCenterResponsibilityScopeId')):
        if evidence.get(key):
            record=model.objects.filter(pk=evidence[key]).first()
            if not record or not _effective(record,day):fail('HANDOVER_ACTUAL_DATE_AUTHORITY_INVALID','声明实际发生日不在正式岗位／职责／工作中心范围有效期内。',403)
            records.append(record)
    dated_scopes=[]
    for match in evidence.get('matchedAuthorityEvidence',[]):
        record=UserRoleScopeAssignment.objects.filter(pk=match.get('roleScopeAssignmentId'),user_id=actor.pk).first()
        if record and _effective(record,day):dated_scopes.append(record.pk)
    if evidence.get('matchedAuthorityEvidence') and not dated_scopes:
        fail('HANDOVER_ACTUAL_DATE_AUTHORITY_INVALID','声明实际发生日不在任一实际匹配角色数据范围有效期内。',403)
    original=q.get('originalReportAuthority',{}).get('currentActorEvidence',{})
    if original.get('workflowResponsibilityId'):
        mapping=PositionWorkflowResponsibility.objects.filter(pk=original['workflowResponsibilityId']).first()
        if not mapping or not _effective(mapping,day):fail('HANDOVER_ACTUAL_DATE_AUTHORITY_INVALID','声明实际日未覆盖原正式报工职责。',403)


def _immutable(row):
    mutable = {'status', 'version', 'updated_at', 'data', 'reserved_by_id', 'frozen',
        'holder_workshop_id', 'holder_work_center_id', 'confirmed_by_id', 'confirmed_at',
        'workflow_id', 'approval_task_id', 'approval_decision_id', 'sender_employee_id', 'receiver_employee_id', 'dispatched_at'}
    result = {}
    for field in row._meta.concrete_fields:
        if field.attname in mutable:
            continue
        value = getattr(row, field.attname)
        result[field.attname] = value.isoformat() if isinstance(value, datetime) else value
    return result


def _audit(actor, row, code, reason, q, before, after):
    audit = record_audit(user=actor, action_code=code, target=row, target_type=type(row).__name__,
        target_no=getattr(row, 'no', str(row.pk)), before=before,
        after={'row': after, 'immutable': _immutable(row), 'sourceHash': row.source_snapshot_hash,
            'qualification': deepcopy(q),'projectionData':deepcopy(getattr(row,'data',{}))}, authorization=q['authorization'], reason=reason)
    node = {'processCode': q.get('actionContract',{}).get('workflowProcessCode','MES_OPERATION_HANDOVER'), 'businessProcessCode': q.get('actionContract',{}).get('businessProcessCode','MES_PRODUCTION_OPERATION'), 'processId': q.get('definitionId'),
        'nodeId': q.get('nodeId'), 'authorityActionCode': code}
    audit.before_snapshot['workflowNode'] = node
    audit.after_snapshot['workflowNode'] = node
    audit.save(update_fields=['before_snapshot', 'after_snapshot'])
    return audit


def initialize(model, *, actor, code, q, status, source, intent_hash, reason, **fields):
    if fields.get('occurred_at') is not None:assert_actual_qualification(actor,q,fields['occurred_at'])
    row = create_business_object_with_initial_state(model=model, initial_state=status,
        company_id=actor.company_id, source_snapshot=deepcopy(source), source_snapshot_hash=_hash(source),
        qualification_snapshot=deepcopy(q), intent_hash=intent_hash, created_by=actor, reason=reason, **fields)
    audit = _audit(actor, row, code, reason, q, {'status': ''}, {'status': status, 'version': row.version})
    record_projected_business_transition(object_type=type(row).__name__, object_id=row.pk,
        source_state='', target_state=status, action_code=code, operator=actor, reason=reason,
        audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions={('', status)})
    return row


def project(row, **fields):
    row._handover_projection_authorized = True
    try:
        for key, value in fields.items():
            setattr(row, key, value)
        row.save(update_fields=list(fields) + ['updated_at'])
    finally:
        row._handover_projection_authorized = False


def audited_projection(row, *, actor, code, q, reason, **fields):
    """Audit metadata changes without inventing a same-state business transition."""
    before={key:getattr(row,key) for key in fields}
    project(row,**fields)
    audit=_audit(actor,row,code,reason,q,{'projection':before},
        {'projection':deepcopy(fields),'status':row.status,'version':row.version})
    return f'OrganizationOperatingAuditRecord:{audit.pk}'


def transition(row, target, *, actor, code, q, reason):
    if row.status == target:
        return None
    audit = _audit(actor, row, code, reason, q, {'status': row.status}, {'status': target, 'version': row.version + 1})
    return transition_business_object(business_object=row, object_type=type(row).__name__,
        source_state=row.status, target_state=target, action_code=code, operator=actor,
        reason=reason, audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
        allowed_transitions={(row.status, target)})


def record_proof_batch(rows, *, audit_actor=False):
    """Load exact history/audit edges; each consumer still verifies its row."""
    from django.db.models import Q
    from system.models import OrganizationOperatingAuditRecord
    rows = list(rows)
    groups = {}
    for row in rows:
        groups.setdefault(type(row).__name__, set()).add(row.pk)
    predicate = Q(pk__in=[])
    for object_type, ids in groups.items():
        predicate |= Q(object_type=object_type, object_id__in=ids)
    histories = {(kind, pk): [] for kind, ids in groups.items() for pk in ids}
    audit_ids = set()
    for event in BusinessStateTransition.objects.filter(predicate).order_by('version', 'pk'):
        histories[(event.object_type, event.object_id)].append(event)
        match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', event.audit_reference or '')
        if match:
            audit_ids.add(int(match[1]))
    audits = (OrganizationOperatingAuditRecord.objects.select_related('actor').defer('actor__password') if audit_actor else OrganizationOperatingAuditRecord.objects).in_bulk(audit_ids)
    return histories, audits


def verify_record(row, *, proof_batch=None):
    from system.models import OrganizationOperatingAuditRecord
    if _hash(row.source_snapshot) != row.source_snapshot_hash:
        fail('HANDOVER_SOURCE_PROOF_DAMAGED', '正式来源快照或Hash损坏。')
    identity = (type(row).__name__, row.pk)
    events = (proof_batch[0][identity] if proof_batch is not None else
        list(BusinessStateTransition.objects.filter(object_type=identity[0], object_id=row.pk).order_by('version','pk')))
    if not events:
        fail('HANDOVER_HISTORY_UNPROVEN', '正式对象缺少状态及审计历史。')
    previous = ''
    history = []
    for index, event in enumerate(events, 1):
        match = re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)', event.audit_reference or '')
        audit = ((proof_batch[1].get(int(match[1])) if proof_batch is not None else
            OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first()) if match else None)
        state = audit.after_snapshot.get('state') if audit and isinstance(audit.after_snapshot, dict) else None
        if (event.version != index or event.source_state != previous or not audit
            or audit.actor_id != event.operator_id or audit.action_code != event.action_code
            or audit.target_type != type(row).__name__ or audit.target_id != row.pk
            or audit.organization_id != row.company_id or audit.reason != event.reason
            or not isinstance(state, dict) or state.get('immutable') != _immutable(row)
            or not isinstance(state.get('row'),dict) or not isinstance(state.get('qualification'),dict)
            or state.get('sourceHash') != row.source_snapshot_hash
            or state.get('row', {}).get('status') != event.target_state
            or state.get('qualification', {}).get('ready') is not True
            or state.get('qualification',{}).get('actionContract',{}).get('actionCode')!=event.action_code):
            fail('HANDOVER_HISTORY_UNPROVEN', '对象、动作、人员、来源或正式审计历史不一致。')
        history.append({'id':event.pk,'sourceState':event.source_state,'targetState':event.target_state,
            'actionCode':event.action_code,'operatorId':event.operator_id,'auditReference':event.audit_reference,
            'version':event.version,'timestamp':event.timestamp.isoformat(),'reason':event.reason})
        previous = event.target_state
    if previous != row.status:
        fail('HANDOVER_HISTORY_UNPROVEN', '持久状态与真实状态历史不一致。')
    if (type(row).__name__ in ('OperationOutputEvidence','OperationCustodyException','OperationInputAllocation') and row.status in ('confirmed','rejected')
        or type(row).__name__=='ProductionFinishedGoodsTransfer' and row.status=='received'):
        if state.get('projectionData')!=getattr(row,'data',{}):
            fail('HANDOVER_PROOF_PROJECTION_CHANGED','已生效对象的关联内容与原正式审计不一致。')
    if ((type(row).__name__=='OperationOutputEvidence' and row.kind=='EXCESS_REPORT' or type(row).__name__=='OperationCustodyException')
        and row.status in ('confirmed','rejected') and (row.workflow_id or row.approval_task_id or row.approval_decision_id)):
        from .operation_output_authority import verify_shared_review
        verify_shared_review(row)
    return {'statusTransitionHistory':history,'statusTransitionCount':len(history),'stateMachineConsistent':True}


def intent(actor, code, object_id, payload):
    digest = _hash({'actorId':actor.pk,'actionCode':code,'objectId':object_id,
        'payload':{k:deepcopy(v) for k,v in payload.items() if k!='idempotencyKey'}})
    old = MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,
        action_code=code,idempotency_key=payload['idempotencyKey']).select_related('source_identity').first()
    if old and (old.status != 'COMMITTED' or old.request_hash != digest or old.audit_metadata.get('actorId') != actor.pk):
        fail('HANDOVER_IDEMPOTENCY_CONFLICT', '原请求标识已绑定其他对象、动作或意图。')
    return digest, old


def commit_intent(actor, code, payload, digest, row, result):
    identity = ExternalIdentity.objects.create(organization_id=actor.company_id,
        source_system='MES_OPERATION_HANDOVER',source_type='INTERNAL',source_object_type=code,
        external_id=sha256(payload['idempotencyKey'].encode()).hexdigest(),target_entity_type=type(row).__name__,
        target_entity_id=str(row.pk),mapping_status='MATCH',source_fingerprint=digest,
        audit_metadata={'actorId':actor.pk,'sourceHash':row.source_snapshot_hash})
    return MasterDataWriteRequest.objects.create(organization_id=actor.company_id,action_code=code,
        entity_type=type(row).__name__,idempotency_key=payload['idempotencyKey'],request_hash=digest,
        source_identity=identity,status='COMMITTED',target_entity_id=str(row.pk),result=result,
        audit_metadata={'actorId':actor.pk,'sourceHash':row.source_snapshot_hash})


def writes(created=False):
    return {'businessWriteCount':int(created),'auditWriteCount':int(created),'actualDispatchCount':0,
        'actualStartCount':0,'actualReportCount':0,'inventoryUpdatedCount':0,'workOrderUpdatedCount':0,
        'operationSourceUpdatedCount':0,'taskUpdatedCount':0,'scheduleUpdatedCount':0,
        'stateTransitionWriteCount':int(created),'resourceOccupancyReleasedCount':0}


def capture_counts():
    from system.models import OrganizationOperatingAuditRecord
    from workflow_runtime.models import WorkflowInstance, ApprovalTask, ApprovalDecision
    from . import operation_handover_models as m
    models=[m.OperationOutputEvidence,m.OperationOutputAllocation,m.OperationCustodySlice,
        m.OperationHandover,m.OperationHandoverAllocation,m.OperationCustodyEvent,
        m.OperationCustodyException,m.OperationInputAllocation,WorkflowInstance,ApprovalTask,ApprovalDecision]
    return {'business':sum(model.objects.count() for model in models),
        'audit':OrganizationOperatingAuditRecord.objects.count(),'transition':BusinessStateTransition.objects.count()}


def writes_since(before):
    after=capture_counts();result=writes()
    result.update(businessWriteCount=after['business']-before['business'],
        auditWriteCount=after['audit']-before['audit'],stateTransitionWriteCount=after['transition']-before['transition'])
    return result
