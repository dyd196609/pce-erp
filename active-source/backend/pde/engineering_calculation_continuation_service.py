"""Audited version authority around the existing formal main calculator.

This adds no calculator, approval system, legacy scope mutation or implicit
downstream selection. Every accepted new main is linked to its fixed ancestor.
"""
from copy import deepcopy
from hashlib import sha256
import json

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import OperationalError, transaction
from django.db.models import Q

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import Company, OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition, transition_business_object)
from .models import (EngineeringCalculationContinuation, EngineeringCalculationRecord,
    EngineeringCalculationDetail, EngineeringDerivedFact, EngineeringOperationRequirement,
    LegacyInFlightOrderAdoption, ProductDesignItem, ProductDesignRevision, ProductManufacturingOutput,
    ProductionPlanOperationRequirementAllocation)
from .engineering_calculation_service import EngineeringCalculationError, EngineeringCalculationService

CONTRACT = 'PCE-ENGINEERING-MAIN-VERSION-CONTINUATION-V1'
ACTION = 'production.engineering.calculation.version_continue'
PERMISSION = 'production.engineering.calculation.execute'
VIEW = 'production.engineering.calculation.view'
OBJECT = 'EngineeringCalculationContinuation'


class EngineeringCalculationContinuationError(EngineeringCalculationError):
    pass


def fail(code, message, **details):
    raise EngineeringCalculationContinuationError(code,message,details)


def normal(value):
    return json.loads(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str))


def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()


def _ids(**values):
    if any(type(value) is not int or value <= 0 for value in values.values()):
        fail('CONTINUATION_SCOPE_INVALID','必须明确选择正式订单行、工程实例、基线和前驱主核算')


def _authorize(user, *, write=False):
    decision = EngineeringCalculationService._authorize(user=user,
        action_code=PERMISSION if write else VIEW,company_id=user.company_id)
    chain = None
    if write:
        from .production_foundation_service import _actor_chain, ProductionFoundationError
        try:
            chain = _actor_chain(user)
        except ProductionFoundationError as error:
            raise EngineeringCalculationContinuationError(error.code,error.message,error.details) from error
    return decision, chain


def _execution_available(user):
    try:
        _authorize(user, write=True)
    except EngineeringCalculationError as error:
        return False, error.message
    return True, ''


def _main_row_values(row):
    # QuerySet.values() without explicit fields uses each concrete attname,
    # including ForeignKey *_id, and the same field-converted Python values.
    return {field.attname: getattr(row, field.attname) for field in row._meta.concrete_fields}


def _main_rows_guard(facts, details, cache):
    """Guard every call-owned model, including the original joined relations."""
    from . import operation_requirement_service as native
    rows = []
    for fact in facts:
        detail = fact.source_detail
        rows.extend((fact, detail, detail.rule if detail else None, fact.uom))
    rows.extend(details)
    return tuple((row._meta.label_lower, row.pk, native._proof_record_hash(row, read_cache=cache))
        for row in rows if row is not None)


def _main_proof_rows(calc, *, read_cache=None):
    """Reuse only raw Fact/Detail rows within one typed, unchanged read."""
    from . import operation_requirement_service as native
    cache = native._requirement_read_cache(read_cache, calc.company_id)
    key = ('continuation_main_proof_rows', calc.company_id, calc.pk)
    if cache is not None and key in cache:
        saved = cache[key]
        try:
            intact = saved['guard'] == _main_rows_guard(saved['facts'], saved['details'], cache)
        except (AttributeError, KeyError, ObjectDoesNotExist, TypeError, ValueError):
            intact = False
        if intact:
            return saved['facts'], saved['details'], True
        # A shared ORM instance may have been changed by another reader in
        # this call. It cannot carry an old approval into any native consumer.
        cache.invalidate_proofs()
    facts = list(calc.derived_facts.select_related('source_detail__rule', 'uom').order_by('sequence', 'pk'))
    details = list(calc.details.order_by('sequence', 'pk'))
    if cache is not None and cache.is_current(calc.company_id):
        cache[key] = {'facts': facts, 'details': details,
            'guard': _main_rows_guard(facts, details, cache)}
    return facts, details, cache is not None


def _main_proof(calc, *, read_cache=None):
    """The persisted result envelope must still describe every actual Fact."""
    from .formal_engineering_continuation_service import _hash
    trace = calc.trace or {}; results=trace.get('resultSnapshot'); graph=trace.get('ruleGraphSnapshot')
    if (calc.scope != 'order_engineering' or calc.status != 'completed'
        or not isinstance(results,list) or not results or not isinstance(graph,list) or not graph
        or _hash(results) != calc.result_hash or _hash(graph) != calc.rule_graph_hash):
        fail('CONTINUATION_PREVIOUS_MAIN_UNPROVEN','主核算缺少完整原生规则图及结果Hash证明',calculationId=calc.pk)
    facts, details, typed_rows = _main_proof_rows(calc, read_cache=read_cache)
    by_fact={row['factId']:row for row in results if isinstance(row,dict) and 'factId' in row}
    if len(by_fact) != len(results) or len(facts) != len(results) or len(details) != len(results):
        fail('CONTINUATION_PREVIOUS_MAIN_UNPROVEN','主核算结果、Fact或明细存在遗漏或重复',calculationId=calc.pk)
    for fact in facts:
        row=by_fact.get(fact.pk); detail=fact.source_detail
        if (not row or not detail or fact.status != 'active' or detail.status != 'succeeded'
            or detail.calculation_id != calc.pk or row.get('detailId') != detail.pk
            or row.get('canonicalField') != fact.canonical_field or row.get('value') != fact.value
            or detail.output_value != fact.value or row.get('ruleCode') != detail.rule_code
            or row.get('ruleVersion') != detail.rule_version or fact.rule_id != detail.rule_id
            or fact.uom_id != detail.uom_id):
            fail('CONTINUATION_PREVIOUS_FACT_CHANGED','原主核算Fact、明细、规则、单位或结果快照不一致',factId=fact.pk)
        expected_unit=row.get('unit') or None
        accepted_codes={expected_unit} if expected_unit else set()
        if expected_unit=='m2':accepted_codes|={'m²','㎡'}
        if (fact.trace.get('unitSnapshot')!=expected_unit
            or (fact.uom_id is None and expected_unit is not None)
            or (fact.uom_id is not None and (fact.uom.company_id!=calc.company_id or not fact.uom.is_active
                or fact.uom.code not in accepted_codes))):
            fail('CONTINUATION_PREVIOUS_UNIT_CHANGED','Fact正式单位与原结果及单位快照不一致',factId=fact.pk)
    return {'calculationId':calc.pk,'revision':calc.revision,'inputHash':calc.input_hash,
        'ruleGraphHash':calc.rule_graph_hash,'resultHash':calc.result_hash,
        'recordHash':digest({f.attname:getattr(calc,f.attname) for f in calc._meta.concrete_fields}),
        'factsHash':digest([_main_row_values(fact) for fact in sorted(facts, key=lambda fact: fact.pk)]
            if typed_rows else list(calc.derived_facts.order_by('pk').values())),
        'detailsHash':digest([_main_row_values(detail) for detail in sorted(details, key=lambda detail: detail.pk)]
            if typed_rows else list(calc.details.order_by('pk').values()))}


def _main_proof_matches(calc, frozen, *, proof_created_at, read_cache=None):
    current = _main_proof(calc, read_cache=read_cache)
    if current == frozen:
        return True
    from .historical_source_schema import CALC_ADDED, legacy_production_calculation
    if (not isinstance(frozen, dict) or set(frozen) != set(current)
            or not legacy_production_calculation(calc, proof_created_at)):
        return False
    historical = dict(current)
    historical['recordHash'] = digest({field.attname:getattr(calc, field.attname)
        for field in calc._meta.concrete_fields if field.attname not in CALC_ADDED})
    return historical == frozen


def _protected_snapshot(adoption, *, upper=None):
    """Only scoped immutable prefixes; appended native result rows are separate."""
    order_id=adoption.sales_order_id
    queries={
        'adoption':LegacyInFlightOrderAdoption.objects.filter(pk=adoption.pk),
        'calculations':EngineeringCalculationRecord.objects.filter(sales_order_item__sales_order_id=order_id),
        'details':EngineeringCalculationDetail.objects.filter(calculation__sales_order_item__sales_order_id=order_id),
        'facts':EngineeringDerivedFact.objects.filter(calculation__sales_order_item__sales_order_id=order_id),
        'requirements':EngineeringOperationRequirement.objects.filter(calculation__sales_order_item__sales_order_id=order_id),
        'allocations':ProductionPlanOperationRequirementAllocation.objects.filter(
            operation_requirement__calculation__sales_order_item__sales_order_id=order_id),
        'outputs':ProductManufacturingOutput.objects.filter(order_engineering_instance__sales_order_item__sales_order_id=order_id),
    }
    result={}
    for key,query in queries.items():
        if upper is not None:query=query.filter(pk__lte=upper[key]['maxId'])
        rows=list(query.order_by('pk').values())
        result[key]={'maxId':max((row['id'] for row in rows),default=0),'count':len(rows),'hash':digest(rows)}
    return result


def _baseline_basis(baseline, items, previous):
    from .product_version_management_service import CONFIRM_ACTION, _content_snapshot
    from .product_design_service import ACTION_DESIGN_SAVE
    from .formal_engineering_continuation_service import _baseline_reference
    reference=_baseline_reference(baseline,items)
    transition=BusinessStateTransition.objects.filter(object_type='OrderEngineeringBaseline',object_id=baseline.pk,
        source_state='draft',target_state='confirmed',action_code=CONFIRM_ACTION).first()
    audit_id=(transition.audit_reference.rsplit(':',1)[-1] if transition else '')
    audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(audit_id)).first() if audit_id.isdigit() else None
    requests=list(MasterDataWriteRequest.objects.filter(organization_id=baseline.company_id,
        action_code=CONFIRM_ACTION,entity_type='OrderEngineeringBaseline',status='COMMITTED',
        result__baselineId=baseline.pk))
    if (not baseline.confirmed_by_id or not baseline.confirmed_at or not audit or len(requests)!=1
        or audit.actor_id != baseline.confirmed_by_id or transition.operator_id != audit.actor_id
        or audit.organization_id != baseline.company_id or audit.action_code != CONFIRM_ACTION
        or audit.target_type != 'OrderEngineeringBaseline' or audit.target_id != baseline.pk
        or audit.after_snapshot.get('snapshotHash') != baseline.snapshot_hash
        or audit.after_snapshot.get('version') != baseline.version
        or requests[0].result.get('auditId') != audit.pk or requests[0].result.get('version') != baseline.version):
        fail('CONTINUATION_BASELINE_AUTHORITY_REQUIRED','目标基线缺少正式确认审计、状态事实及已提交请求')
    old_objects={row['designItemId']:row for row in previous.trace.get('objectInputSnapshot',[]) if isinstance(row,dict)}
    current_ids={item.design_item_id for item in items}
    if set(old_objects)!=current_ids:
        fail('CONTINUATION_OBJECT_SCOPE_CHANGED','新旧主核算必须覆盖同一订单行完整设计对象，不以名称或顺序拼接')
    revisions=[]
    for item in items:
        latest=ProductDesignRevision.objects.filter(design_item_id=item.design_item_id).order_by('-revision','-pk').first()
        if (not latest or latest.pk != item.design_revision_id or item.design_item.version != item.design_item_version
            or digest(item.content_snapshot)!=item.content_hash
            or normal(_content_snapshot(item.design_item,latest))!=item.content_snapshot):
            fail('CONTINUATION_CURRENT_DESIGN_UNPROVEN','目标基线未固定当前完整正式设计版本',designItemId=item.design_item_id)
        if old_objects[item.design_item_id].get('contentHash')==item.content_hash:continue
        candidates=OrganizationOperatingAuditRecord.objects.filter(organization_id=baseline.company_id,
            action_code=ACTION_DESIGN_SAVE,actor_id=latest.created_by_id).order_by('pk')
        matched=[]
        for candidate in candidates:
            if latest.pk not in (candidate.after_snapshot or {}).get('changedRevisionIds',[]):continue
            writes=list(MasterDataWriteRequest.objects.filter(organization_id=baseline.company_id,
                action_code=ACTION_DESIGN_SAVE,entity_type='ProductDesignRevision',status='COMMITTED',result__auditId=candidate.pk))
            if len(writes)!=1:continue
            write=writes[0]
            if (latest.pk not in write.result.get('changedRevisionIds',[])
                or item.design_item_id not in write.audit_metadata.get('itemIds',[])
                or digest(write.audit_metadata)!=write.request_hash
                or candidate.after_snapshot.get('requestHash')!=write.request_hash):continue
            matched.append((candidate,write))
        if len(matched)!=1:
            fail('CONTINUATION_REVISION_AUTHORITY_REQUIRED','发生内容变化的设计修订缺少唯一真实保存审计及已提交请求',designItemId=item.design_item_id)
        candidate,write=matched[0]
        revisions.append({'designItemId':item.design_item_id,'designRevisionId':latest.pk,
            'designRevision':latest.revision,'designItemVersion':item.design_item_version,
            'contentHash':item.content_hash,'auditId':candidate.pk,'writeRequestId':write.pk,
            'requestHash':write.request_hash,'changeReason':latest.change_reason})
    return {'contractVersion':CONTRACT,'reference':'正式工程基线确认及设计内容修订原生记录',
        'statusLabel':'服务端已核对正式基线确认及变更修订依据','baselineReference':reference,
        'baselineAuditId':audit.pk,'baselineTransitionId':transition.pk,'baselineWriteRequestId':requests[0].pk,
        'designRevisions':revisions}


def validate_continuation_model(row):
    if not isinstance(row.source_snapshot,dict) or not isinstance(row.result_snapshot,dict):
        raise ValidationError('主核算接续证据必须是完整结构化对象。')
    if not all(getattr(row,name+'_id',None) for name in ('company','adoption','sales_order_item',
        'engineering_instance','previous_calculation','baseline','write_request','created_by')):
        raise ValidationError('主核算接续必须固定完整正式身份。')
    previous=row.previous_calculation
    if (row.adoption.company_id!=row.company_id or row.adoption.sales_order_id!=row.sales_order_item.sales_order_id
        or row.sales_order_item.sales_order.company_id!=row.company_id or row.engineering_instance.company_id!=row.company_id
        or row.engineering_instance.sales_order_item_id!=row.sales_order_item_id
        or row.baseline.company_id!=row.company_id or row.baseline.sales_order_id!=row.adoption.sales_order_id
        or previous.company_id!=row.company_id or previous.sales_order_item_id!=row.sales_order_item_id
        or previous.engineering_instance_id!=row.engineering_instance_id or previous.scope!='order_engineering'):
        raise ValidationError('主核算接续必须属于同公司、同订单行、同实例和明确前驱。')
    if digest(row.source_snapshot)!=row.context_hash or digest(row.source_snapshot.get('continuationBasis'))!=row.basis_hash:
        raise ValidationError('主核算接续冻结上下文或正式依据Hash不一致。')
    expected={'contractVersion':CONTRACT,'companyId':row.company_id,'legacyAdoptionId':row.adoption_id,
        'legacyEvidenceHash':row.adoption.evidence_hash,'salesOrderItemId':row.sales_order_item_id,
        'engineeringInstanceId':row.engineering_instance_id,'baselineId':row.baseline_id,
        'previousCalculationId':row.previous_calculation_id}
    if any(row.source_snapshot.get(key)!=value for key,value in expected.items()):
        raise ValidationError('接续外键与冻结权威身份不一致。')
    if row.new_calculation_id:
        new=row.new_calculation
        if (new.pk==previous.pk or new.supersedes_id!=previous.pk or new.revision!=previous.revision+1
            or new.status!='completed' or new.scope!='order_engineering'
            or any(getattr(new,key)!=getattr(previous,key) for key in ('company_id','source_record_id','sales_order_item_id','engineering_instance_id'))
            or new.trace.get('baselineReference',{}).get('id')!=row.baseline_id
            or new.trace.get('workbookSource')!=row.source_snapshot.get('workbookSource')):
            raise ValidationError('新主核算必须为同范围、修订严格加一且来源完整的独立结果。')


def continuation_proof(row, *, read_cache=None):
    try:
        validate_continuation_model(row)
    except ValidationError as error:
        fail('CONTINUATION_SCOPE_UNPROVEN','正式接续身份或冻结Hash校验失败',validation=str(error))
    from .legacy_inflight_order_adoption import evidence_hash
    if evidence_hash(row.adoption.evidence_snapshot)!=row.adoption.evidence_hash:
        fail('CONTINUATION_LEGACY_EVIDENCE_CHANGED','原历史承接冻结证据Hash不一致')
    request=row.write_request; audit=row.audit_record
    if (row.status!='committed' or not row.new_calculation_id or not audit
        or request.status!='COMMITTED' or request.action_code!=ACTION or request.entity_type!=OBJECT
        or request.organization_id!=row.company_id or request.target_entity_id!=str(row.pk)
        or digest(request.audit_metadata.get('request'))!=request.request_hash
        or request.audit_metadata.get('request',{}).get('actorId')!=row.created_by_id
        or request.audit_metadata.get('request',{}).get('contextHash')!=row.context_hash
        or request.audit_metadata.get('request',{}).get('basisHash')!=row.basis_hash
        or request.result.get('continuationId')!=row.pk
        or request.result.get('contextHash')!=row.context_hash or request.result.get('continuationBasisHash')!=row.basis_hash
        or request.result.get('newCalculationId')!=row.new_calculation_id
        or audit.organization_id!=row.company_id or audit.action_code!=ACTION or audit.actor_id!=row.created_by_id
        or audit.target_type!=OBJECT or audit.target_id!=row.pk
        or audit.after_snapshot.get('sourceSnapshot')!=row.source_snapshot
        or audit.after_snapshot.get('resultSnapshot')!=row.result_snapshot):
        fail('CONTINUATION_COMMIT_UNPROVEN','主核算接续缺少一致的已提交请求与正式审计')
    states=list(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=row.pk).order_by('version'))
    if (len(states)!=2 or [(s.source_state,s.target_state) for s in states]!=[('','draft'),('draft','committed')]
        or [s.version for s in states]!=[1,2] or row.version!=1
        or any(s.action_code!=ACTION or s.operator_id!=row.created_by_id for s in states)
        or states[1].audit_reference!=f'OrganizationOperatingAuditRecord:{audit.pk}'
        or states[0].audit_reference!=f"OrganizationOperatingAuditRecord:{request.result.get('initializationAuditId')}"):
        fail('CONTINUATION_STATE_UNPROVEN','主核算接续缺少完整原生初始化及提交状态事实')
    initial=OrganizationOperatingAuditRecord.objects.filter(pk=request.result.get('initializationAuditId')).first()
    if (not initial or initial.organization_id!=row.company_id or initial.actor_id!=row.created_by_id
        or initial.action_code!=ACTION or initial.target_type!=OBJECT or initial.target_id!=row.pk
        or initial.before_snapshot!={} or initial.after_snapshot!={'status':'draft','contextHash':row.context_hash,
            'basisHash':row.basis_hash,'writeRequestId':request.pk}):
        fail('CONTINUATION_INITIALIZATION_UNPROVEN','接续初始化审计缺失或与冻结身份不一致')
    native_action='production.engineering.calculation.execute'
    native_audit=OrganizationOperatingAuditRecord.objects.filter(pk=row.result_snapshot.get('nativeAuditId')).first()
    native_state=(native_audit.after_snapshot or {}).get('state',{}) if native_audit else {}
    native_states=list(BusinessStateTransition.objects.filter(object_type='EngineeringCalculationRecord',
        object_id=row.new_calculation_id).order_by('version'))
    if (not native_audit or native_audit.organization_id!=row.company_id or native_audit.actor_id!=row.created_by_id
        or native_audit.action_code!=native_action or native_audit.target_type!='EngineeringCalculationRecord'
        or native_audit.target_id!=row.new_calculation_id or native_state.get('status')!='completed'
        or native_state.get('inputHash')!=row.new_calculation.input_hash
        or native_state.get('resultHash')!=row.new_calculation.result_hash
        or len(native_states)!=1 or native_states[0].source_state!='running' or native_states[0].target_state!='completed'
        or native_states[0].action_code!=native_action or native_states[0].operator_id!=row.created_by_id
        or native_states[0].audit_reference!=f'OrganizationOperatingAuditRecord:{native_audit.pk}'):
        fail('CONTINUATION_NATIVE_MAIN_UNPROVEN','新主核算缺少原生完成审计及状态事实')
    if not _main_proof_matches(row.previous_calculation, row.source_snapshot['previousCalculationProof'],
            proof_created_at=row.created_at, read_cache=read_cache):
        fail('CONTINUATION_PREVIOUS_MAIN_CHANGED','原主核算或Fact已变化，不能沿用接续资格')
    if not _main_proof_matches(row.new_calculation, row.result_snapshot.get('newCalculationProof'),
            proof_created_at=row.created_at, read_cache=read_cache):
        fail('CONTINUATION_NEW_MAIN_CHANGED','新主核算或Fact与提交证据不一致')
    # Whole-order preservation is proved before/after the creating transaction.
    # Admission rechecks this exact main lineage and its native ledger; each
    # existing requirement/allocation retains its original native validation.
    return {'continuationId':row.pk,'predecessorCalculationId':row.previous_calculation_id,
        **({'workbookSourceRecordId':row.source_snapshot['workbookSource']['sourceRecordId']} if row.source_snapshot.get('workbookSource') else {}),
        'id':row.pk,'requestStatus':request.status,'stateMachineConsistent':True,
        'newCalculationId':row.new_calculation_id,'salesOrderItemId':row.sales_order_item_id,
        'orderEngineeringInstanceId':row.engineering_instance_id,'orderEngineeringBaselineId':row.baseline_id,
        'contextHash':row.context_hash,'continuationBasisHash':row.basis_hash,'auditId':audit.pk,
        'writeRequestId':request.pk,'statusLabel':'已完成正式主核算版本接续','factSource':'server'}


def admitted_continuations(adoption):
    try:rows=list(EngineeringCalculationContinuation.objects.filter(adoption=adoption).select_related(
        'previous_calculation','new_calculation','write_request','audit_record').order_by('pk'))
    except OperationalError as error:
        if 'no such table: pde_engineering_calculation_continuation' in str(error).lower():return []
        raise
    proofs=[]; allowed=set(adoption.evidence_snapshot.get('scope',{}).get('engineeringCalculationIds',[]))
    for row in rows:
        if row.previous_calculation_id not in allowed:
            fail('CONTINUATION_LINEAGE_UNPROVEN','主核算接续前驱不在原冻结范围或已提交正式继任链')
        proof=continuation_proof(row); proofs.append(proof);allowed.add(row.new_calculation_id)
    return proofs


def validate_pending_authority(record, *, previous, sales_item, instance, baseline, company_id, user,workbook_source_context=None):
    if not transaction.get_connection().in_atomic_block or not getattr(record,'pk',None):
        fail('CONTINUATION_AUTHORITY_REQUIRED','原子主核算执行缺少本事务正式接续记录')
    row=EngineeringCalculationContinuation.objects.select_for_update().get(pk=record.pk)
    validate_continuation_model(row)
    request=row.write_request
    if (row.status!='draft' or row.new_calculation_id or row.company_id!=company_id or row.created_by_id!=user.pk
        or row.previous_calculation_id!=previous.pk or row.sales_order_item_id!=sales_item.pk
        or row.engineering_instance_id!=instance.pk or row.baseline_id!=baseline.pk
        or request.status!=MasterDataWriteRequest.Status.RESERVED or request.action_code!=ACTION or request.entity_type!=OBJECT
        or request.organization_id!=company_id or digest(request.audit_metadata.get('request'))!=request.request_hash
        or request.audit_metadata.get('request',{}).get('actorId')!=user.pk
        or row.source_snapshot.get('workbookSource')!=(workbook_source_context or {}).get('proof')
        or _main_proof(previous)!=row.source_snapshot['previousCalculationProof']
        or _protected_snapshot(row.adoption,upper=row.source_snapshot['protectedOldSnapshot'])!=row.source_snapshot['protectedOldSnapshot']):
        fail('CONTINUATION_AUTHORITY_REQUIRED','本事务正式接续记录的范围、请求或旧事实证明不一致')
    return row


class EngineeringCalculationContinuationService:
    @classmethod
    def facts(cls, *, user, sales_order_item_id, engineering_instance_id,workbook_source_record_id=None):
        _authorize(user)
        adoption=LegacyInFlightOrderAdoption.objects.filter(company_id=user.company_id,
            sales_order__items__pk=sales_order_item_id).first()
        actions=[{'actionCode':'preview','businessActionCode':ACTION,'displayName':'预览正式主核算版本接续',
            'allowed':bool(adoption and engineering_instance_id),'reason':''},
            {'actionCode':'execute','businessActionCode':ACTION,'displayName':'执行正式主核算版本接续',
                'allowed':False,'reason':'必须先读取完整正式预览及当前执行资格'}]
        result={'factSource':'server','statusLabel':'请选择明确前驱主核算及已确认新基线进行预览',
            'workbookSourceRecordId':workbook_source_record_id,
            'legacyAdoptionNo':adoption.adoption_no if adoption else None,
            'frozenScopeLabel':'原历史承接范围保持固定；新版本需要独立正式接续' if adoption else '当前行无历史承接记录',
            'availableActions':actions,'predecessorCalculations':[],'records':[]}
        if not adoption or not engineering_instance_id:return result
        proofs=admitted_continuations(adoption)
        result['records']=[p for p in proofs if p['salesOrderItemId']==sales_order_item_id]
        previous_ids={p['predecessorCalculationId'] for p in result['records']}
        allowed=set(adoption.evidence_snapshot.get('scope',{}).get('engineeringCalculationIds',[]))
        allowed.update(p['newCalculationId'] for p in proofs)
        for calc in EngineeringCalculationRecord.objects.filter(pk__in=allowed,company_id=user.company_id,
            sales_order_item_id=sales_order_item_id,engineering_instance_id=engineering_instance_id,
            scope='order_engineering',status='completed').exclude(pk__in=previous_ids).order_by('revision','pk'):
            baseline=calc.trace.get('baselineReference',{})
            result['predecessorCalculations'].append({'id':calc.pk,'calculationNo':calc.calculation_no,
                'baselineId':baseline.get('id'),'baselineNo':baseline.get('baselineNo'),'statusLabel':calc.get_status_display()})
        return result

    @classmethod
    @transaction.atomic
    def preview(cls, *, user, sales_order_item_id, engineering_instance_id, baseline_id, previous_calculation_id, rule_ids=None,
                workbook_source_record_id=None):
        _authorize(user);_ids(item=sales_order_item_id,instance=engineering_instance_id,baseline=baseline_id,previous=previous_calculation_id)
        from .formal_engineering_continuation_service import _resolve_context,_selected_workbook, FormalEngineeringContinuationService as Native
        from .legacy_inflight_order_adoption import require_active_legacy_adoption
        item,instance,baseline,items,_,_= _resolve_context(company_id=user.company_id,
            sales_order_item_id=sales_order_item_id,engineering_instance_id=engineering_instance_id,baseline_id=baseline_id)
        adoption_result=require_active_legacy_adoption(order=item.sales_order,sales_order_item_id=item.pk,
            engineering_instance_id=instance.pk,calculation_id=previous_calculation_id)
        if adoption_result is None:fail('CONTINUATION_LEGACY_AUTHORITY_REQUIRED','本版本接续必须有明确的原历史承接权威记录')
        adoption=adoption_result.adoption
        previous=EngineeringCalculationRecord.objects.filter(pk=previous_calculation_id,company_id=user.company_id,
            sales_order_item=item,engineering_instance=instance,scope='order_engineering',status='completed').first()
        if not previous:fail('CONTINUATION_PREVIOUS_SCOPE_INVALID','所选前驱不是当前行及实例已完成的正式主核算')
        existing=EngineeringCalculationContinuation.objects.filter(previous_calculation=previous).first()
        if existing:fail('CONTINUATION_ALREADY_COMMITTED','此前驱已有正式接续记录，请读取并明确选择后继主核算')
        admitted_ids=set(adoption.evidence_snapshot['scope']['engineeringCalculationIds'])
        admitted_ids.update(p['newCalculationId'] for p in admitted_continuations(adoption))
        if EngineeringCalculationRecord.objects.filter(pk__in=admitted_ids,supersedes=previous,scope='order_engineering').exists():
            fail('CONTINUATION_PREVIOUS_NOT_HEAD','所选前驱不是该实例正式版本链头')
        previous_proof=_main_proof(previous)
        frozen=next((p for p in adoption.evidence_snapshot.get('engineeringCalculations',[]) if p['id']==previous.pk),None)
        if frozen and any(frozen.get(key)!=previous_proof[key] for key in ('inputHash','ruleGraphHash','resultHash','revision')):
            fail('CONTINUATION_LEGACY_MAIN_CHANGED','原主核算Hash或修订与LIA冻结证据不一致')
        basis=_baseline_basis(baseline,items,previous)
        workbook=_selected_workbook(user.company_id,workbook_source_record_id,baseline=baseline)
        try:
            validation=Native.validate(user=user,sales_order_item_id=item.pk,engineering_instance_id=instance.pk,
                baseline_id=baseline.pk,rule_ids=rule_ids,**({'workbook_source_context':workbook} if workbook else {}))
        except (OSError,ValueError) as error:
            fail('CONTINUATION_SOURCE_READ_FAILED','正式核算来源读取失败，未形成接续资格',errorType=type(error).__name__,error=str(error))
        if previous.trace.get('baselineReference',{}).get('id')==baseline.pk:
            fail('CONTINUATION_NEW_VERSION_REQUIRED','必须选择独立已确认的新工程基线，禁止重放原核算')
        source={'contractVersion':CONTRACT,'companyId':user.company_id,'legacyAdoptionId':adoption.pk,
            'legacyEvidenceHash':adoption.evidence_hash,'salesOrderItemId':item.pk,'engineeringInstanceId':instance.pk,
            'baselineId':baseline.pk,'previousCalculationId':previous.pk,'previousCalculationProof':previous_proof,
            'continuationBasis':basis,'nativeValidation':normal(validation),'protectedOldSnapshot':_protected_snapshot(adoption),
            **({'workbookSource':workbook['proof']} if workbook else {})}
        executable,execution_reason=_execution_available(user)
        return {'contractVersion':CONTRACT,'factSource':'server','ready':validation['ready'],'blockers':validation['blockers'],
            'statusLabel':'正式新主核算接续准入已通过' if validation['ready'] else '正式新主核算接续存在未决事项',
            'expectedContextHash':digest(source),'contextHash':digest(source),'continuationBasisHash':digest(basis),
            'continuationBasis':basis,'sourceSnapshot':source,'newScope':validation['selection'],
            'oldFixedPreservation':{'statusLabel':'原历史承接范围、主核算、Fact及已有分配保持原身份',
                'legacyAdoptionId':adoption.pk,'legacyEvidenceHash':adoption.evidence_hash,'newExecutionGrantedToHistoricalAllocations':False},
            'availableActions':[{'actionCode':'preview','businessActionCode':ACTION,'displayName':'重新读取正式接续预览','allowed':True},
                {'actionCode':'execute','businessActionCode':ACTION,'displayName':'执行正式主核算版本接续',
                 'allowed':validation['ready'] and executable,'reason':execution_reason}],
            'workbookSourceRecordId':workbook_source_record_id,'businessWriteSideEffectCount':0,'auditWriteCount':0}

    @classmethod
    @transaction.atomic
    def execute(cls, *, user, sales_order_item_id, engineering_instance_id, baseline_id, previous_calculation_id,
                expected_context_hash, continuation_basis_hash, idempotency_key, reason, rule_ids=None,
                workbook_source_record_id=None):
        decision,chain=_authorize(user,write=True)
        if (not isinstance(reason,str) or not reason.strip() or len(reason)>240
            or not isinstance(idempotency_key,str) or not idempotency_key.strip() or len(idempotency_key)>160):
            fail('CONTINUATION_INPUT_REQUIRED','正式接续必须提供有效原因及幂等键')
        Company.objects.select_for_update().get(pk=user.company_id)
        # The native design editor locks these same object rows.
        list(ProductDesignItem.objects.select_for_update().filter(company_id=user.company_id,
            sales_order_item_id=sales_order_item_id).order_by('pk').values_list('pk',flat=True))
        body={'actorId':user.pk,'companyId':user.company_id,'salesOrderItemId':sales_order_item_id,
            'engineeringInstanceId':engineering_instance_id,'baselineId':baseline_id,'previousCalculationId':previous_calculation_id,
            'contextHash':expected_context_hash,'basisHash':continuation_basis_hash,'ruleIds':rule_ids,'reason':reason,
            **({'workbookSourceRecordId':workbook_source_record_id} if workbook_source_record_id is not None else {})}
        request_hash=digest(body)
        ledger=MasterDataWriteRequest.objects.select_for_update().filter(organization_id=user.company_id,
            action_code=ACTION,idempotency_key=idempotency_key).first()
        if ledger:
            if ledger.request_hash!=request_hash:fail('IDEMPOTENCY_CONFLICT','同一幂等键已绑定其他正式接续内容')
            if ledger.status=='COMMITTED':
                row=EngineeringCalculationContinuation.objects.get(pk=ledger.result['continuationId'])
                proof=continuation_proof(row)
                return {**ledger.result,'continuation':proof,'idempotent':True,'businessWriteSideEffectCount':0,'auditWriteCount':0}
            fail('CONTINUATION_INCOMPLETE_REQUEST','已有未提交接续请求，必须核对原事务结果，禁止自动重试')
        candidate=cls.preview(user=user,sales_order_item_id=sales_order_item_id,engineering_instance_id=engineering_instance_id,
            baseline_id=baseline_id,previous_calculation_id=previous_calculation_id,rule_ids=rule_ids,
            workbook_source_record_id=workbook_source_record_id)
        if not candidate['ready']:fail('CONTINUATION_NOT_READY','正式主核算接续准入未通过',blockers=candidate['blockers'])
        if candidate['contextHash']!=expected_context_hash or candidate['continuationBasisHash']!=continuation_basis_hash:
            fail('CONTINUATION_CANDIDATE_STALE','正式依据、输入或原固定事实已变化，请重新读取')
        source=candidate['sourceSnapshot']
        audit_before=OrganizationOperatingAuditRecord.objects.count()
        identity=ExternalIdentity.objects.create(organization_id=user.company_id,source_system='PCE',
            source_type=CONTRACT,source_object_type=OBJECT,external_id=f'{previous_calculation_id}:{expected_context_hash}',
            target_entity_type=OBJECT,mapping_status='REVIEW',source_fingerprint=expected_context_hash)
        ledger=MasterDataWriteRequest.objects.create(organization_id=user.company_id,action_code=ACTION,entity_type=OBJECT,
            idempotency_key=idempotency_key,request_hash=request_hash,source_identity=identity,
            audit_metadata={'request':body,'authorization':decision,'executionChain':chain})
        row=create_business_object_with_initial_state(model=EngineeringCalculationContinuation,initial_state='draft',
            company_id=user.company_id,adoption_id=source['legacyAdoptionId'],sales_order_item_id=sales_order_item_id,
            engineering_instance_id=engineering_instance_id,previous_calculation_id=previous_calculation_id,baseline_id=baseline_id,
            context_hash=expected_context_hash,basis_hash=continuation_basis_hash,source_snapshot=source,
            write_request=ledger,created_by=user,reason=reason)
        initial_audit=OrganizationOperatingAuditRecord.objects.create(organization_id=user.company_id,action_code=ACTION,
            actor=user,target_type=OBJECT,target_id=row.pk,target_label=f'主核算接续{row.pk}初始化',reason=reason,
            before_snapshot={},after_snapshot={'status':'draft','contextHash':row.context_hash,'basisHash':row.basis_hash,'writeRequestId':ledger.pk})
        initial=record_projected_business_transition(object_type=OBJECT,object_id=row.pk,source_state='',target_state='draft',
            action_code=ACTION,operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{initial_audit.pk}',allowed_transitions={('','draft')})
        from .formal_engineering_continuation_service import FormalEngineeringContinuationService as Native,_selected_workbook
        workbook=_selected_workbook(user.company_id,workbook_source_record_id,baseline=row.baseline)
        generated=Native.execute(user=user,sales_order_item_id=sales_order_item_id,engineering_instance_id=engineering_instance_id,
            baseline_id=baseline_id,rule_ids=rule_ids,reason=reason,continuation_record=row,
            **({'workbook_source_context':workbook} if workbook else {}))
        if generated['idempotent']:fail('CONTINUATION_UNBOUND_EXISTING_MAIN','发现未由本事务形成的主核算，禁止补签既有结果')
        row.new_calculation_id=generated['calculation']['id']
        row.result_snapshot={'newCalculationProof':_main_proof(row.new_calculation),'nativeAuditId':generated['auditId']}
        if _protected_snapshot(row.adoption,upper=source['protectedOldSnapshot'])!=source['protectedOldSnapshot']:
            fail('CONTINUATION_PRESERVATION_FAILED','原冻结事实或固定消费发生变化，接续事务已阻断')
        audit=OrganizationOperatingAuditRecord.objects.create(organization_id=user.company_id,action_code=ACTION,
            actor=user,target_type=OBJECT,target_id=row.pk,target_label=f'主核算接续{row.pk}提交',reason=reason,
            before_snapshot={'status':'draft'},after_snapshot={'status':'committed','sourceSnapshot':row.source_snapshot,
                'resultSnapshot':row.result_snapshot,'authorization':decision,'executionChain':chain})
        row.audit_record=audit;row._continuation_write_authorized=True
        row.save(update_fields=['new_calculation','result_snapshot','audit_record'])
        transition_business_object(business_object=row,object_type=OBJECT,source_state='draft',target_state='committed',
            action_code=ACTION,operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('draft','committed')})
        result={'continuationId':row.pk,'newCalculationId':row.new_calculation_id,'predecessorCalculationId':previous_calculation_id,
            **({'workbookSourceRecordId':workbook_source_record_id} if workbook_source_record_id is not None else {}),
            'contextHash':row.context_hash,'continuationBasisHash':row.basis_hash,
            'baselineId':baseline_id,'statusLabel':'已完成正式主核算版本接续','calculation':generated['calculation'],
            'auditId':audit.pk,'nativeCalculationAuditId':generated['auditId'],'writeRequestId':ledger.pk,
            'initializationAuditId':initial_audit.pk,'initializationTransitionId':initial.pk,'idempotent':False,
            'businessWriteSideEffectCount':2+row.new_calculation.details.count()+row.new_calculation.derived_facts.count(),
            'auditWriteCount':OrganizationOperatingAuditRecord.objects.count()-audit_before,'oldFactsModifiedCount':0}
        ledger.status='COMMITTED';ledger.target_entity_id=str(row.pk);ledger.result=normal(result)
        ledger.save(update_fields=['status','target_entity_id','result','updated_at'])
        result['continuation']=continuation_proof(row)
        return result
