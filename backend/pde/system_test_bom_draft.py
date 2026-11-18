"""Physically pinned development admission to the existing BOM draft kernel.

No HTTP parameter creates this admission. It never grants review, release or
manufacturing eligibility and never alters the source order's business purpose.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from django.conf import settings
from django.db import connections

SCOPE = 'SYSTEM_TEST_BOM_DRAFT_ONCE_V1'
_TOKEN = object()


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), default=str).encode()).hexdigest()


def _fail(code, message):
    from .engineering_calculation_service import EngineeringCalculationError
    raise EngineeringCalculationError(code, message)


@dataclass(frozen=True)
class _Admission:
    token: object
    receipt_hash: str
    proof: dict


def _validate(*, user, calculation_id, preview_hash, operation):
    config = getattr(settings, 'PCE_SYSTEM_TEST_BOM_DRAFT', None)
    if not isinstance(config, dict) or config.get('enabled') is not True:
        _fail('SYSTEM_TEST_BOM_NOT_ACTIVATED', '服务端未激活受控测试BOM草稿。')
    root = Path(__file__).resolve().parents[2] / 'work'
    receipt = Path(config.get('receiptPath', '')).resolve()
    if not receipt.is_relative_to(root) or not receipt.is_file():
        _fail('SYSTEM_TEST_BOM_PIN_INVALID', '缺少工作区内服务端凭据。')
    raw = receipt.read_bytes()
    receipt_hash = sha256(raw).hexdigest()
    if receipt_hash != config.get('receiptSha256'):
        _fail('SYSTEM_TEST_BOM_PIN_CHANGED', '受控凭据内容已变化。')
    pin = json.loads(raw)
    contract = pin.get('contract', {})
    if (pin.get('scope') != SCOPE or pin.get('developmentOnly') is not True
            or digest(contract) != pin.get('contractHash')
            or operation not in pin.get('allowedActions', [])):
        _fail('SYSTEM_TEST_BOM_CONTRACT_DENIED', '用途、合同或动作不在激活范围。')
    target = Path(pin.get('databasePath', '')).resolve()
    if (not target.is_relative_to(root) or not target.name.endswith('-acceptance.sqlite3')
            or target.is_symlink() or not target.is_file()):
        _fail('SYSTEM_TEST_BOM_DATABASE_DENIED', '仅允许专属独立BOM验证副本。')
    stat = target.stat()
    if (stat.st_nlink != 1 or [stat.st_dev, stat.st_ino] != pin.get('physicalIdentity')
            or [stat.st_dev, stat.st_ino] in pin.get('protectedPhysicalIdentities', [])):
        _fail('SYSTEM_TEST_BOM_DATABASE_DENIED', '副本物理身份不符或命中保护对象。')
    for alias in connections:
        db = connections[alias]
        if db.settings_dict.get('ENGINE') != 'django.db.backends.sqlite3' or db.settings_dict.get('NAME') != str(target):
            _fail('SYSTEM_TEST_BOM_DATABASE_DENIED', '数据库配置未精确绑定受控副本。')
    db = connections['default']
    db.ensure_connection()
    if db.connection.execute('PRAGMA database_list').fetchall() != [(0, 'main', str(target))]:
        _fail('SYSTEM_TEST_BOM_DATABASE_DENIED', '实际数据库身份或附加数据库不符。')
    obj = contract.get('objectScope', {})
    if (not user or not user.is_active or user.is_superuser
            or user.pk != contract.get('actorId') or user.company_id != obj.get('companyId')):
        _fail('SYSTEM_TEST_BOM_ACTOR_DENIED', '操作者或公司不在受控范围。')
    from .models import BOMVersion, EngineeringCalculationRecord, ProductBOM
    from .system_test_material_handoff import requirement_evidence
    from .production_foundation_service import _actor_chain
    from .engineering_calculation_service import OrderEngineeringClosureService
    record = EngineeringCalculationRecord.objects.select_related(
        'engineering_instance__sales_order_item__sales_order', 'source_record',
    ).filter(pk=calculation_id, company_id=user.company_id).first()
    if not record or record.pk != obj.get('calculationId') or not record.engineering_instance_id:
        _fail('SYSTEM_TEST_BOM_OBJECT_DENIED', '受控核算记录不存在或跨公司。')
    instance = record.engineering_instance
    item = instance.sales_order_item
    if (record.pk != obj.get('calculationId') or item.sales_order_id != obj.get('orderId')
            or item.pk != obj.get('itemId') or instance.pk != obj.get('oeiId')
            or record.source_record_id != obj.get('sourceId')
            or item.sales_order.business_purpose != 'SYSTEM_TEST'
            or record.status != 'completed' or instance.status != 'calculated'
            or record.result_hash != contract.get('calculationResultHash')
            or digest(record.trace) != contract.get('calculationTraceHash')):
        _fail('SYSTEM_TEST_BOM_OBJECT_DENIED', '订单、核算、实例或冻结来源不符。')
    chain = _actor_chain(user)
    if chain.get('employeeId') != contract.get('employeeId') or chain.get('positionId') != contract.get('positionId'):
        _fail('SYSTEM_TEST_BOM_ACTOR_DENIED', '既有人员岗位与受控合同不符。')
    rows = list(record.material_requirements.select_related('calculation', 'source_detail').order_by('pk'))
    expected = contract.get('requirements', [])
    if [row.pk for row in rows] != [entry.get('requirementId') for entry in expected]:
        _fail('SYSTEM_TEST_BOM_REQUIREMENTS_CHANGED', '来源需求集合与合同不符。')
    for row, entry in zip(rows, expected):
        if digest(requirement_evidence(row)) != entry.get('evidenceHash'):
            _fail('SYSTEM_TEST_BOM_REQUIREMENTS_CHANGED', '需求完整来源账本、映射或合同已变化。')
    preview = OrderEngineeringClosureService.preview_bom(user=user, calculation_id=record.pk)
    if (preview_hash != contract.get('previewHash') or preview['previewHash'] != preview_hash
            or digest(preview['rows']) != contract.get('previewRowsHash')
            or contract.get('quantityBasis') != 'ORDER_TOTAL_NET'
            or contract.get('orderQuantityMultiplierApplied') is not False):
        _fail('SYSTEM_TEST_BOM_PREVIEW_CHANGED', '预览或订单总净量合同不符。')
    existing = list(BOMVersion.objects.filter(source_calculation=record))
    if existing:
        if len(existing) != 1:
            _fail('SYSTEM_TEST_BOM_EXISTING_CONFLICT', '存在冲突的已生成版本。')
        version = existing[0]
        saved = version.applicability.get('developmentValidation', {})
        if (version.status != 'draft' or version.bom.status != 'draft'
                or saved.get('receiptSha256') != receipt_hash
                or saved.get('contractHash') != pin['contractHash']
                or version.preview_hash != preview_hash):
            _fail('SYSTEM_TEST_BOM_EXISTING_CONFLICT', '已存在对象不属于同一受控草稿提交。')
    elif ProductBOM.objects.filter(company_id=user.company_id, order_engineering_instance=instance, is_active=True).exists():
        _fail('SYSTEM_TEST_BOM_EXISTING_CONFLICT', '已有BOM主表，不能借用或覆盖。')
    return _Admission(_TOKEN, receipt_hash, {
        'scope': SCOPE, 'developmentOnly': True, 'receiptSha256': receipt_hash,
        'contractHash': pin['contractHash'], 'userContentSha256': pin['userContentSha256'],
        'objectScope': obj, 'requirements': expected, 'previewHash': preview_hash,
        'quantityBasis': 'ORDER_TOTAL_NET', 'orderQuantityMultiplierApplied': False,
        'allowedActions': ['CREATE_DRAFT', 'READ_ONLY'],
        'formalCRMAdmitted': False, 'formalManufacturingEligible': False,
    })


def validate_admission(admission, *, user, calculation_id, preview_hash):
    if not isinstance(admission, _Admission) or admission.token is not _TOKEN:
        _fail('SYSTEM_TEST_BOM_ADMISSION_DENIED', '不能从客户端数据构造受控准入。')
    fresh = _validate(user=user, calculation_id=calculation_id, preview_hash=preview_hash, operation='generate_draft')
    if fresh.receipt_hash != admission.receipt_hash or fresh.proof != admission.proof:
        _fail('SYSTEM_TEST_BOM_ADMISSION_DENIED', '准入上下文已变化。')
    return dict(fresh.proof)


def generate_draft(*, user, calculation_id, preview_hash):
    admission = _validate(user=user, calculation_id=calculation_id, preview_hash=preview_hash, operation='generate_draft')
    from .engineering_calculation_service import OrderEngineeringClosureService
    return OrderEngineeringClosureService.generate_bom(
        user=user, calculation_id=calculation_id, preview_hash=preview_hash,
        reason='受控开发测试订单总净量BOM草稿；禁止评审、发布及制造',
        _development_admission=admission,
    )
