from hashlib import sha256
from django.db import transaction
from .test_business_bom_service import authorize,validate_source,fail
from .models import BOMVersion,BOMItem,BOMItemSourceRequirement

@transaction.atomic
def derive_test_version(*,user,version_id,key,reason):
    if not key or not reason.strip():fail('TEST_DERIVATION_REASON_REQUIRED','复制或派生须提供原因及幂等键。')
    original=BOMVersion.objects.select_for_update().select_related('bom').get(pk=version_id)
    authorize(user,'production.master_data.bom.maintain',original.bom.company_id)
    if original.usage_purpose!='TEST_BUSINESS':fail('TEST_VERSION_REQUIRED','此操作只复制测试草稿，不改变正式版本链。')
    record=original.bom.source_calculation
    validate_source(record,user)
    from .test_business_bom_service import validate_requirements
    validate_requirements(record,list(record.material_requirements.select_related('source_detail','material','uom')))
    from .product_bom_detail_projection import project_product_bom_material_detail
    project_product_bom_material_detail(bom=original.bom,bom_version=original,order_item=record.sales_order_item)
    name='TEST-'+sha256((str(original.pk)+':'+key).encode()).hexdigest()[:24]
    existing=BOMVersion.objects.filter(bom=original.bom,bom_version=name).first()
    if existing:return {'id':existing.pk,'idempotent':True}
    from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition
    from system.models import OrganizationOperatingAuditRecord
    version=create_business_object_with_initial_state(model=BOMVersion,initial_state='draft',bom=original.bom,bom_scope='order_specific',bom_version=name,revision=original.revision+1,order_engineering_instance=original.order_engineering_instance,origin_version=original,usage_purpose='TEST_BUSINESS')
    pending=list(original.items.order_by('line_no'));clones={}
    while pending:
        progress=False
        for item in list(pending):
            if item.parent_item_id and item.parent_item_id not in clones:continue
            fields={f.attname:getattr(item,f.attname) for f in item._meta.concrete_fields if f.name not in ('id','bom_version','parent_item','created_at','updated_at')}
            clone=BOMItem(bom_version=version,parent_item=clones.get(item.parent_item_id),**fields);clone.full_clean();clone.save();clones[item.pk]=clone
            pending.remove(item);progress=True
        if not progress:fail('TEST_BOM_STRUCTURE_INVALID','来源BOM结构循环或缺失，复制事务已回滚。')
    audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=original.bom.company_id,action_code='production.master_data.bom.maintain',target_type='BOMVersion',target_id=version.pk,target_label=name,reason=reason,after_snapshot={'usagePurpose':'TEST_BUSINESS','originVersionId':original.pk,'sourceCalculationId':record.pk})
    record_projected_business_transition(object_type='BOMVersion',object_id=version.pk,source_state='',target_state='draft',action_code='production.master_data.bom.maintain',operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','draft')})
    return {'id':version.pk,'idempotent':False}
