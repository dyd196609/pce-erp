"""One server-owned baseline usage gate. Empty legacy scope is evidence checked."""
from .models import OrderEngineeringBaseline
from .routing_read_context import memo_read

def successor_evidence(revision):
    from .product_design_service import ProductDesignError
    from .design_revision_approval_service import effective,digest
    approval=revision.approval
    effective(approval)
    if revision.predecessor_revision_id!=approval.source_revision_id or revision.approval_scope!=approval.approval_scope or revision.origin_nature!=approval.origin_nature:
        raise ProductDesignError('APPROVED_SUCCESSOR_BINDING_MISMATCH','获准后继与批准对象绑定不一致。',409)
    from .product_version_management_service import _content_snapshot
    original=approval.content_snapshot['revision']
    actual=_content_snapshot(revision.design_item,revision)['revision']
    ignored={'id','revision','designNature','sourceProvenance','changeReason','createdById','createdAt'}
    if {k:v for k,v in original.items() if k not in ignored}!={k:v for k,v in actual.items() if k not in ignored}:
        raise ProductDesignError('APPROVED_SUCCESSOR_CONTENT_MISMATCH','后继设计内容不等于获准冻结内容。',409)
    return {'approvalId':approval.pk,'decisionId':approval.final_decision_id,'sourceRevisionId':approval.source_revision_id,'contentHash':approval.content_hash,'approvalScope':approval.approval_scope,'originNature':approval.origin_nature,'processVersion':approval.process_version}

@memo_read('baseline_validation', lambda baseline,purpose='PRODUCTION_USE',allow_draft=False:
    (tuple((f.attname,repr(getattr(baseline,f.attname))) for f in baseline._meta.concrete_fields),purpose,allow_draft))
def validate_baseline(baseline,purpose='PRODUCTION_USE',allow_draft=False):
    from .product_design_service import ProductDesignError
    from .product_version_management_service import _hash
    from workflow_runtime.models import BusinessStateTransition
    from system.models import OrganizationOperatingAuditRecord
    if baseline.status!='confirmed' and not (allow_draft and baseline.status=='draft'):
        raise ProductDesignError('BASELINE_STATE_NOT_USABLE','基线状态不允许当前用途。',409)
    items=list(baseline.items.select_related('design_revision__approval','design_item','source_record'))
    if not items or len(items)!=baseline.scope_item_count or _hash([x.content_hash for x in items])!=baseline.snapshot_hash:
        raise ProductDesignError('BASELINE_FROZEN_HASH_INVALID','基线冻结范围或哈希不一致。',409)
    for item in items:
        if _hash(item.content_snapshot)!=item.content_hash:
            raise ProductDesignError('BASELINE_ITEM_HASH_INVALID','基线项冻结内容哈希不一致。',409)
        frozen=item.content_snapshot.get('approval')
        if frozen:
            if not item.design_revision_id or not item.design_revision.approval_id or successor_evidence(item.design_revision)!=frozen:
                raise ProductDesignError('BASELINE_APPROVAL_INVALID','基线批准依据已失效或与冻结事实不一致。',409)
            if frozen['approvalScope']!=baseline.approval_scope:
                raise ProductDesignError('BASELINE_APPROVAL_SCOPE_MISMATCH','基线用途与批准用途不一致。',409)
        elif baseline.approval_scope:
            raise ProductDesignError('BASELINE_APPROVAL_REQUIRED','新用途基线缺少精确资料批准事实。',409)
    if baseline.approval_scope:
        if baseline.approval_scope!=purpose:
            raise ProductDesignError('BASELINE_USAGE_SCOPE_DENIED','测试业务基线不得用于生产业务；不同用途不得互相提升。',403)
        return {'scope':baseline.approval_scope,'authority':'EXACT_REVISION_APPROVAL'}
    # Legacy compatibility is exact frozen evidence, not an empty-scope default.
    if purpose!='PRODUCTION_USE':
        raise ProductDesignError('LEGACY_TEST_CONTRACT_REQUIRED','存量基线没有测试消费用途契约。',409)
    for item in items:
        snap=item.content_snapshot
        nature=(snap.get('revision') or {}).get('designNature') or (snap.get('designItem') or {}).get('designDataNature')
        if nature not in ('FORMAL','EXISTING_DESIGN_IMPORTED') or item.source_content_hash_snapshot!=item.source_record.content_hash or item.source_version_snapshot!=item.source_record.source_version or not item.confirmable:
            raise ProductDesignError('LEGACY_BASELINE_EVIDENCE_GAP','存量基线缺少可追溯生产适用依据；不修改历史快照。',409)
    if not allow_draft:
        transitions=BusinessStateTransition.objects.filter(object_type='OrderEngineeringBaseline',object_id=baseline.pk,target_state='confirmed')
        if not transitions.exists() or not OrganizationOperatingAuditRecord.objects.filter(action_code='pde.order_engineering_baseline.confirm',target_type='OrderEngineeringBaseline',target_id=baseline.pk,organization_id=baseline.company_id).exists():
            raise ProductDesignError('LEGACY_BASELINE_CONFIRM_EVIDENCE_GAP','存量确认缺少状态转换或权威审计。',409)
    return {'scope':'PRODUCTION_USE','authority':'VERIFIED_LEGACY_FROZEN_EVIDENCE','baselineId':baseline.pk}

@memo_read('production_baselines', lambda: ())
def _production_baseline_ids():
    from .product_design_service import ProductDesignError
    ids=[]
    for baseline in OrderEngineeringBaseline.objects.filter(status='confirmed'):
        try:validate_baseline(baseline);ids.append(baseline.pk)
        except ProductDesignError:pass
    return tuple(ids)


def production_baselines():
    return OrderEngineeringBaseline.objects.filter(pk__in=_production_baseline_ids())

def production_status(baseline):
    from .product_design_service import ProductDesignError
    try:validate_baseline(baseline);return baseline.status
    except ProductDesignError:return 'usage_blocked'
