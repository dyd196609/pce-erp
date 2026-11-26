"""Persistent BOM purpose, exact lineage and fail-closed production boundary."""
from django.core.exceptions import ValidationError
TEST = 'TEST_BUSINESS'
UNKNOWN = 'UNCLASSIFIED'
PRODUCTION = 'PRODUCTION_USE'

def bind_usage(obj):
    if obj.usage_purpose not in (TEST,UNKNOWN,PRODUCTION):raise ValidationError('BOM用途代码无效。')
    from .models import ProductBOM, EngineeringCalculationRecord
    old = type(obj).objects.filter(pk=obj.pk).first() if obj.pk else None
    record = EngineeringCalculationRecord.all_records.filter(pk=obj.source_calculation_id).first() if obj.source_calculation_id else None
    inherited = getattr(obj, 'origin_version', None) if hasattr(obj, 'origin_version_id') and obj.origin_version_id else None
    header = getattr(obj, 'bom', None) if hasattr(obj, 'bom_id') and obj.bom_id else None
    if inherited and (not header or inherited.bom_id != header.pk or inherited.order_engineering_instance_id != obj.order_engineering_instance_id):
        raise ValidationError('派生版本必须与来源版本属于同一BOM及工程实例。')
    if inherited and header and header.usage_purpose == TEST and inherited.usage_purpose != TEST:
        raise ValidationError('测试草稿不能伪造其他用途的来源版本。')
    if not record and inherited and header and header.source_calculation_id:
        record = EngineeringCalculationRecord.all_records.filter(pk=header.source_calculation_id).first()
    purpose = TEST if record and record.scope == 'test_business' else None
    for parent in (inherited, header):
        if parent and parent.usage_purpose == TEST:
            purpose = TEST
            if not record or record.pk != (parent.source_calculation_id or (parent.bom.source_calculation_id if getattr(parent,'bom_id',None) else None)):
                raise ValidationError('测试BOM派生必须保留精确来源核算。')
    if old and old.usage_purpose == TEST:
        if obj.usage_purpose != TEST or obj.source_calculation_id != old.source_calculation_id or getattr(obj,'origin_version_id',None) != getattr(old,'origin_version_id',None) or obj.order_engineering_instance_id != old.order_engineering_instance_id:
            raise ValidationError('测试BOM用途及来源不可降级或改写。')
        purpose = TEST
    if purpose == TEST:
        if obj.usage_purpose not in (UNKNOWN, TEST):
            raise ValidationError('调用者不得将测试来源标为生产用途。')
        obj.usage_purpose = TEST
        if not record or record.status != 'completed' or record.approval_scope != TEST:
            raise ValidationError('测试BOM必须引用完整且已完成的测试核算。')
        if obj.order_engineering_instance_id != record.engineering_instance_id:
            raise ValidationError('BOM与测试核算实例不一致。')
        company = obj.company_id if isinstance(obj,ProductBOM) else header.company_id if header else None
        if company != record.company_id or obj.status != 'draft':
            raise ValidationError('测试BOM仅允许同公司草稿。')
        from .test_calculation_persistence import validate_record_binding
        validate_record_binding(record)
    elif inherited and inherited.usage_purpose != obj.usage_purpose and obj.usage_purpose != UNKNOWN:
        raise ValidationError('派生版本用途必须继承来源。')
    elif obj.usage_purpose == TEST:
        raise ValidationError('测试用途缺少可信测试核算来源。')
    elif record and record.scope == 'order_engineering' and obj.usage_purpose == UNKNOWN:
        from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
        if FormalManufacturingEligibilityService.resolve(record)['formalManufacturingEligible']:
            obj.usage_purpose = PRODUCTION
    if obj.usage_purpose == PRODUCTION and (not old or old.usage_purpose != PRODUCTION):
        from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
        if not FormalManufacturingEligibilityService.resolve(record or obj)['formalManufacturingEligible']:
            raise ValidationError('缺少可信生产用途证据，禁止调用者自报生产用途。')
    if old and old.usage_purpose != UNKNOWN and old.usage_purpose != obj.usage_purpose:
        raise ValidationError('持久用途不可改写；需另建来源明确的新对象。')

def is_test_source(source):
    for field in ('bom_version','related_bom'):
        if getattr(source,field+'_id',None) and getattr(getattr(source,field),'usage_purpose',None)==TEST:return True
    if getattr(source,'usage_purpose',None) == TEST or getattr(source,'scope',None) == 'test_business':return True
    if getattr(source,'source_calculation_id',None):
        from .models import EngineeringCalculationRecord
        if EngineeringCalculationRecord.all_records.filter(pk=source.source_calculation_id,scope='test_business').exists():return True
    instance_id = getattr(source,'order_engineering_instance_id',None) or getattr(source,'engineering_instance_id',None)
    from .models import OrderEngineeringInstance,ProductBOM
    if isinstance(source,OrderEngineeringInstance):instance_id=source.pk
    return bool(instance_id and ProductBOM.objects.filter(order_engineering_instance_id=instance_id,usage_purpose=TEST).exists())

def require_production(source):
    if is_test_source(source):raise ValidationError('测试业务BOM只允许草稿查看，禁止正式评审、发布及生产消费。')

