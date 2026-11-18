"""Server-owned intended-use evidence for a NEW exact design approval.

Development origin remains visible. An existing TEST approval/revision is never
promoted or relabelled. This does not publish engineering or release a pilot.
"""
def assess(*,user,instance,line,source,revision,existing_approval=None):
    from .order_lifecycle_source_projection import terminal_read_allowed
    from .product_design_service import ProductDesignError
    from .models import DesignRevisionApproval
    from .design_revision_approval_service import digest
    item=revision.design_item
    if revision.approval_scope or revision.approval_id:
        raise ProductDesignError('PRODUCTION_DESIGN_NEW_REVISION_REQUIRED','正式用途须新提交未分类的准确修订，禁止提升既有TEST修订或获准后继。',409)
    approvals=DesignRevisionApproval.objects.filter(source_revision=revision)
    if existing_approval is not None:approvals=approvals.exclude(pk=existing_approval.pk)
    if approvals.exists():
        raise ProductDesignError('PRODUCTION_DESIGN_PURPOSE_ALREADY_BOUND','该修订已提交其他用途批准，不能换用途重办。',409)
    order=line.sales_order
    inputs=(revision.design_data or {}).get('calculationInputs') or {}
    if inputs.get('ruleFamily')=='THREE_IN_ONE' and inputs.get('contractVersion')!='CABINET-PARTS-V1':
        raise ProductDesignError('PRODUCTION_DESIGN_INPUT_CONTRACT_REQUIRED','正式用途须新建准确部件输入修订，不能消费TEST专用输入合同。',409)
    if not (user.company_id==instance.company_id==source.company_id==item.company_id==order.company_id
        and instance.sales_order_item_id==line.pk==item.sales_order_item_id
        and instance.source_record_id==item.source_record_id==source.pk
        and source.status=='confirmed' and item.source_version==source.source_version
        and item.source_content_hash==source.content_hash
        and (order.status in ('approved','confirmed','engineering','manufacturing_ready','in_progress') or terminal_read_allowed(order))
        and revision.design_data and revision.design_item_id==item.pk):
        raise ProductDesignError('PRODUCTION_DESIGN_SOURCE_UNPROVEN','正式用途设计缺少同公司有效订单、工程准备、当前来源或结构化设计。',409)
    body={'contractVersion':'PCE-PRODUCTION-DESIGN-SOURCE-ADMISSION-V1','intendedPurpose':'PRODUCTION_USE',
        'companyId':user.company_id,'salesOrderId':order.pk,'salesOrderItemId':line.pk,
        'engineeringInstanceId':instance.pk,'authorizationId':instance.engineering_preparation_authorization_id,
        'sourceRecordId':source.pk,'sourceVersion':source.source_version,'sourceContentHash':source.content_hash,
        'revisionId':revision.pk,'originNature':revision.origin_nature or revision.design_nature,
        'designContentHash':digest(revision.design_data),'pilotReleased':False}
    return {**body,'proofHash':digest(body)}
