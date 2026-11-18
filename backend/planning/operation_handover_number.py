"""Append-only business aliases using existing numbering and identity tables.
GET never allocates. Original audited HO identity remains unchanged.
"""
from django.db import transaction, IntegrityError
from masterdata.models import ExternalIdentity
from procurement.scm_runtime_services import _next_number
from .operation_handover_core import fail, _hash

SYSTEM = 'MES_HANDOVER_NUMBER_V1'

def _scope(row, kind):
    return dict(organization_id=0 if kind == 'NUMBER' else row.company_id, source_system=SYSTEM,
        source_type=kind, source_object_type='OperationHandover')

def read_number(row):
    mapping = ExternalIdentity.objects.filter(**_scope(row, 'HANDOVER'), external_id=row.no).first()
    if mapping is None:
        return {'businessNo': None, 'legacyNo': row.no, 'numberStatus': '待兼容登记'}
    no = mapping.audit_metadata.get('businessNo')
    reservation = ExternalIdentity.objects.filter(**_scope(row, 'NUMBER'), external_id=no,
        target_entity_id=str(row.pk), source_fingerprint=row.source_snapshot_hash).first()
    if (not reservation or mapping.target_entity_id != str(row.pk)
        or mapping.source_fingerprint != row.source_snapshot_hash):
        fail('HANDOVER_NUMBER_PROOF_INVALID', '交接业务编号映射与原始身份不一致。')
    return {'businessNo': no, 'legacyNo': row.no, 'numberStatus': '已登记'}

@transaction.atomic
def assign_number(row, *, actor):
    if actor.company_id != row.company_id:
        fail('HANDOVER_NUMBER_SCOPE', '交接编号不得跨公司登记。', 403)
    # The unique original-identity claim is acquired before reading the sequence.
    # SQLite serializes writers; PostgreSQL waits on the unique claim. A second
    # reader never allocates a second number for the same handover.
    mapping, created = ExternalIdentity.objects.get_or_create(**_scope(row, 'HANDOVER'),
        external_id=row.no, defaults=dict(target_entity_type='OperationHandover',
        target_entity_id=str(row.pk), mapping_status='MATCH', source_fingerprint=row.source_snapshot_hash))
    if not created:
        return read_number(row)
    for attempt in range(20):
        no = _next_number('JJ', ExternalIdentity, 'external_id')
        # Native generator sorts 4-digit suffixes lexically: fail closed on daily
        # exhaustion rather than recycling or truncating a number.
        if len(no) != 14:
            fail('HANDOVER_NUMBER_EXHAUSTED', '当日交接编号容量已满，请核对编号规则。')
        try:
            with transaction.atomic():
                ExternalIdentity.objects.create(**_scope(row, 'NUMBER'), external_id=no,
                    target_entity_type='OperationHandover', target_entity_id=str(row.pk),
                    mapping_status='MATCH', source_fingerprint=row.source_snapshot_hash,
                    audit_metadata={'originalNo': row.no, 'actorId': actor.pk, 'contract': SYSTEM})
            break
        except IntegrityError:
            if attempt == 19: raise
    mapping.audit_metadata = {'businessNo': no, 'originalNo': row.no, 'actorId': actor.pk,
        'contract': SYSTEM, 'originalIdentityHash': _hash({'id':row.pk,'no':row.no,'sourceHash':row.source_snapshot_hash})}
    mapping.save(update_fields=['audit_metadata','last_seen'])
    return read_number(row)


def lookup_handover(actor, value):
    from .operation_handover_models import OperationHandover
    if not isinstance(value,str) or not value or len(value)>80:
        fail('HANDOVER_QUERY_INVALID', '请输入完整交接业务编号或原HO编号。',400)
    row = OperationHandover.objects.filter(company_id=actor.company_id,no=value).first()
    if row is None:
        reservation=ExternalIdentity.objects.filter(organization_id=0,source_system=SYSTEM,
            source_type='NUMBER',source_object_type='OperationHandover',external_id=value).first()
        if reservation:
            row=OperationHandover.objects.filter(company_id=actor.company_id,pk=reservation.target_entity_id).first()
            if row and read_number(row)['businessNo']!=value: row=None
    if row is None: fail('HANDOVER_NOT_VISIBLE', '未找到当前公司可读取的交接编号。',403)
    # Caller must still execute the original exact task/WC permission reader.
    return row
