

# Native formal date consumer restoration.
from contextlib import contextmanager

from contextvars import ContextVar

from copy import deepcopy

from hashlib import sha256

import re

from django.db import IntegrityError, transaction

from masterdata.models import MasterDataWriteRequest, ExternalIdentity

from system.models import Company, Process, Workshop, OrganizationOperatingAuditRecord

from workflow_runtime.models import BusinessStateTransition

from .models import (ProductionPlanOperationRequirementAllocation as Allocation,
    EngineeringRuleDefinition, ManufacturingMode, StandardCapacity, WorkCenter)

from . import operation_requirement_service as native

from .manufacturing_rule_configuration import publication_config_validation

from .engineering_rule_foundation import canonical_json, specification_hash, evaluate_specification

from .plan_step_context_service import resolve_step_context

CONTRACT='PCE-OPERATION-ALLOCATION-SOURCE-HANDOFF-V1'

OBJECT='OperationAllocationSourceHandoff'

ACTION='production.operation_source.handoff'

CREATE='production.engineering.rule.create'

RELEASE='production.engineering.rule.release'

_scope=ContextVar('allocation_source_handoff_read_context',default=None)

def _hash(value):return sha256(canonical_json(value).encode('utf-8')).hexdigest()

def _fail(code,message):native._fail(code,message)

def _actor(user):
    if not user or not user.is_active or not user.company_id or not Company.objects.filter(pk=user.company_id,is_active=True).exists():
        _fail('SOURCE_HANDOFF_ACTOR_REQUIRED','当前账号缺少有效的正式公司范围。')
    return user

@contextmanager
def allocation_admission_context(*,user,company_id=None):
    company_id=user.company_id if user else company_id
    if type(company_id) is not int or company_id<=0 or (user and not user.is_active):
        _fail('SOURCE_HANDOFF_SCOPE_REQUIRED','内部来源读取必须精确限定有效公司。')
    old=_scope.get()
    if old and old['companyId']==company_id and old['userId']==getattr(user,'pk',None):
        yield old;return
    with transaction.atomic():
        if not user or user.company_id!=company_id:
            _fail('SOURCE_HANDOFF_ACTOR_REQUIRED','当前版本的正式来源读取必须绑定同公司原生账号。')
        cache=native._ReadOnlyProofCache(user)
        context={'companyId':company_id,'userId':getattr(user,'pk',None),'cache':cache,
            'plans':{},'rows':{},'history':{},'admissions':{},'validations':{},
            'writeEpoch':getattr(transaction.get_connection().connection,'total_changes',None)}
        token=_scope.set(context)
        try:yield context
        finally:_scope.reset(token)

def _refresh(context):
    connection=transaction.get_connection()
    epoch=getattr(connection.connection,'total_changes',None)
    if not context['cache'].is_current(context['companyId']):
        _fail('SOURCE_HANDOFF_READ_CONTEXT_EXPIRED','来源读取事务已变化，请重新只读核对。')
    if epoch!=context['writeEpoch']:
        for key in ('plans','rows','history','admissions','validations'):context[key].clear()
        context['writeEpoch']=epoch

def _rows(company_id,plan_id,context):
    _refresh(context)
    if plan_id not in context['rows']:
        context['rows'][plan_id]=native._read_allocation_rows(company_id,
            production_plan_id=plan_id,read_cache=context['cache'])
    return context['rows'][plan_id]

def _allocation_hash(row):return native._proof_record_hash(row)

def _concrete_resources(rule):
    """Relevant live values only: labels/updated_at cannot revoke a handoff."""
    config=rule.specification.get('manufacturing',{})
    output=rule.specification['outputs'][0]
    def row(model,pk,fields):
        value=model.objects.filter(pk=pk,company_id=rule.company_id).values(*fields).first() if pk else None
        return {key:(item.isoformat() if hasattr(item,'isoformat') else str(item) if hasattr(item,'as_tuple') else item)
            for key,item in value.items()} if value else None
    return {'ruleId':rule.pk,'ruleVersion':rule.version,'specificationHash':specification_hash(rule.specification),
        'ruleStatus':rule.status,'effectiveFrom':rule.effective_from.isoformat() if rule.effective_from else None,
        'effectiveTo':rule.effective_to.isoformat() if rule.effective_to else None,
        'operation':row(Process,output.get('operationId'),('id','company_id','workshop_id','work_center_id','calculation_uom_id','is_active','effective_from','effective_to')),
        'workCenter':row(WorkCenter,config.get('workCenterId'),('id','company_id','workshop_id','department_id','is_active','effective_from','effective_to')),
        'factoryWorkshop':row(Workshop,config.get('factoryScope',{}).get('workshopId'),('id','company_id','department_id','is_active')),
        'mode':row(ManufacturingMode,config.get('modeId'),('id','company_id','version','status','uom_id','effective_from','effective_to')),
        'capacity':row(StandardCapacity,config.get('standardCapacityId'),('id','company_id','operation_id','work_center_id','product_type_id','uom_id','quantity','measurement_status','is_active','effective_from','effective_to'))}

def _current_context(row):
    req=row.operation_requirement;rule=req.source_detail.rule
    resources=_concrete_resources(rule)
    value={'companyId':row.company_id,'allocationId':row.pk,'allocationHash':_allocation_hash(row),
        'sourceHash':req.source_hash,'resources':resources}
    issues=[];snapshot=None
    try:snapshot=publication_config_validation(rule,require_released=True)
    except Exception as error:
        if not hasattr(error,'code'):raise
        issues.append(getattr(error,'message',str(error)))
    if not native._active(rule):issues.append('原规则不在当前有效期内，历史仍按原冻结证明保留。')
    return {'ready':not issues,'snapshot':snapshot,'resourceSnapshot':resources,
        'statusLabel':'原来源当前仍合法' if not issues else '当前制造资源范围与原来源存在差异',
        'currentContextHash':_hash(value),'blockingReasons':issues}

def _semantic_spec(spec):
    result=deepcopy(spec)
    # A new version is necessarily a new publication identity; it is not an
    # expression, source, applicability, quantity or unit semantic change.
    if isinstance(result.get('rulePackage'),dict):result['rulePackage'].pop('version',None)
    config=result.get('manufacturing')
    if isinstance(config,dict):
        for key in ('factoryScope','workCenterId','standardCapacityId'):config.pop(key,None)
    return result

def _candidate(row,rule):
    old=row.operation_requirement.source_detail.rule;req=row.operation_requirement
    if (rule.company_id!=row.company_id or rule.rule_code!=old.rule_code or rule.status!='released'
            or not native._active(rule) or _semantic_spec(rule.specification)!=_semantic_spec(old.specification)):
        _fail('SOURCE_HANDOFF_SEMANTIC_CHANGE','承接规则须为同公司同规则系列的有效已发布版本，且原来源、单位及数量语义完全保持。')
    current=publication_config_validation(rule,require_released=True)
    if current is None:_fail('SOURCE_HANDOFF_MANUFACTURING_REQUIRED','来源承接须有完整正式制造资源合同。')
    from .operation_allocation_source_version_service import verify_published_version
    verify_published_version(rule)
    result=evaluate_specification(rule.specification,req.source_detail.input_snapshot)
    if (result['resultDomain']!='OPERATION_REQUIREMENT' or native._number(result['value'])!=req.workload_quantity
            or rule.specification['outputs'][0].get('uomId')!=req.uom_id):
        _fail('SOURCE_HANDOFF_QUANTITY_CHANGE','承接不能修改旧需求或已分配数量及单位。')
    return {'id':rule.pk,'code':rule.rule_code,'name':rule.rule_name,'version':rule.version,
        'specificationHash':specification_hash(rule.specification),'statusLabel':'当前合法已发布且原数量语义一致',
        'manufacturingSnapshot':current,'currentResourceHash':_hash(_concrete_resources(rule))}

def _candidates(row):
    rows=[]
    for rule in EngineeringRuleDefinition.objects.filter(company_id=row.company_id,
            rule_code=row.operation_requirement.source_detail.rule.rule_code,status='released').order_by('pk'):
        try:rows.append(_candidate(row,rule))
        except Exception as error:
            if not hasattr(error,'code'):raise
    return rows

def _intent(actor_id,allocation_id,payload):
    return _hash({'actorId':actor_id,'action':ACTION,'allocationId':allocation_id,
        'payload':{**payload,'reason':payload['reason'].strip()}})

def _history(row):
    events=list(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=row.pk).order_by('version','pk'))
    ledgers=list(MasterDataWriteRequest.objects.filter(organization_id=row.company_id,entity_type=OBJECT,
        target_entity_id=str(row.pk),action_code=ACTION).select_related('source_identity'))
    if not events:
        if ledgers:_fail('SOURCE_HANDOFF_HISTORY_INVALID','承接账本没有对应正式状态证明。')
        return []
    result=[];previous=''
    if len(events)!=len(ledgers):_fail('SOURCE_HANDOFF_HISTORY_INVALID','承接转换与正式账本数量不一致。')
    ledger_by_hash={value.request_hash:value for value in ledgers}
    for index,event in enumerate(events,1):
        match=re.fullmatch('OrganizationOperatingAuditRecord:([1-9][0-9]*)',event.audit_reference or '')
        audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
        after=audit.after_snapshot if audit and isinstance(audit.after_snapshot,dict) else {}
        before=audit.before_snapshot if audit and isinstance(audit.before_snapshot,dict) else {}
        state=after.get('state',{});ledger=ledger_by_hash.get(state.get('requestHash'));identity=ledger.source_identity if ledger else None
        snapshot=state.get('snapshot');payload=state.get('intentPayload')
        if not isinstance(snapshot,dict) or not isinstance(payload,dict):_fail('SOURCE_HANDOFF_HISTORY_INVALID','承接冻结证明或意图结构损坏。')
        full_payload={**payload,'idempotencyKey':ledger.idempotency_key} if ledger else payload
        authorization=after.get('authorization',{});chain=after.get('executionChain',{})
        if (not audit or not ledger or not identity or audit.organization_id!=row.company_id
                or audit.target_type!=OBJECT or audit.target_id!=row.pk or audit.action_code!=ACTION
                or audit.actor_id!=event.operator_id or audit.reason!=event.reason
                or event.version!=index or event.source_state!=previous or event.action_code!=ACTION
                or event.workflow_instance_id is not None or event.target_state!='effective:'+state.get('proofHash','')
                or before.get('state')!={'status':previous} or state.get('status')!=event.target_state
                or state.get('contractVersion')!=CONTRACT or state.get('proofHash')!=_hash(snapshot)
                or snapshot.get('companyId')!=row.company_id or snapshot.get('allocationId')!=row.pk
                or snapshot.get('allocationHash')!=_allocation_hash(row) or snapshot.get('sourceHash')!=row.source_hash
                or snapshot.get('handoffVersion')!=index or state.get('actorId')!=event.operator_id
                or ledger.status!='COMMITTED' or ledger.request_hash!=_intent(event.operator_id,row.pk,full_payload)
                or state.get('requestKeyHash')!=sha256(ledger.idempotency_key.encode()).hexdigest()
                or ledger.result!={'allocationId':row.pk,'transitionId':event.pk,'proofHash':state['proofHash']}
                or identity.organization_id!=row.company_id or identity.source_system!='PDE_ALLOCATION_SOURCE_HANDOFF'
                or identity.source_type!='INTERNAL' or identity.source_object_type!=ACTION
                or identity.external_id!=state['requestKeyHash'] or identity.source_fingerprint!=ledger.request_hash
                or identity.target_entity_type!=OBJECT or identity.target_entity_id!=str(row.pk) or identity.mapping_status!='MATCH'
                or identity.audit_metadata!={'contractVersion':CONTRACT}
                or ledger.audit_metadata!={'actorId':event.operator_id,'contractVersion':CONTRACT}
                or after.get('factSource')!='server' or before.get('factSource')!='server'
                or after.get('importContext')!={'contractVersion':CONTRACT}
                or before.get('authorization')!=authorization or before.get('executionChain')!=chain
                or not authorization.get('allowed') or set(authorization.get('requiredPermissions',[]))!={CREATE,RELEASE}
                or chain.get('account')!=state.get('actorUsername') or not chain.get('employeeId') or not chain.get('positionId')
                or not chain.get('responsibilityId') or full_payload.get('reason','').strip()!=event.reason):
            _fail('SOURCE_HANDOFF_HISTORY_INVALID','承接的公司、旧分配、版本、责任、审计、账本或身份关系不一致。')
        target=snapshot.get('targetRule',{})
        if (full_payload.get('targetRuleId')!=target.get('id') or full_payload.get('targetRuleSpecificationHash')!=target.get('specificationHash')
                or full_payload.get('expectedAllocationHash')!=snapshot.get('allocationHash')
                or full_payload.get('expectedSourceHash')!=snapshot.get('sourceHash')
                or full_payload.get('expectedCurrentContextHash')!=snapshot.get('currentContextHash')
                or full_payload.get('expectedHandoffVersion')!=index-1
                or snapshot.get('productionPlanId')!=row.production_plan_id or snapshot.get('routingStepId')!=row.routing_step_id
                or snapshot.get('quantity')!=str(row.allocated_quantity) or snapshot.get('uomId')!=row.uom_id
                or snapshot.get('sourceQuantity')!=str(row.source_quantity) or snapshot.get('sourceUomId')!=row.source_uom_id
                or snapshot.get('confirmedAt')!=state.get('confirmedAt') or snapshot.get('timeLabel')!=state.get('timeLabel')
                or snapshot.get('actorId')!=event.operator_id or snapshot.get('actorUsername')!=state.get('actorUsername')
                or state.get('actorLabel')!=(chain.get('employeeName') or state.get('actorUsername'))
                or snapshot.get('budgetMembershipUnchanged') is not True):
            _fail('SOURCE_HANDOFF_HISTORY_INVALID','承接意图与已冻结目标规则版本不一致。')
        result.append({'ref':f'BusinessStateTransition:{event.pk}','id':event.pk,'companyId':row.company_id,
            'allocationId':row.pk,'targetRuleId':target['id'],'targetRuleVersion':target.get('version'),
            'projectionVersion':index,'version':index,'allocationHash':snapshot['allocationHash'],'sourceHash':snapshot['sourceHash'],
            'currentContextHash':snapshot['currentContextHash'],'actorId':event.operator_id,'actorLabel':state['actorLabel'],
            'confirmedAt':state['confirmedAt'],'timeLabel':state['timeLabel'],'auditReference':event.audit_reference,
            'requestHash':state['requestHash'],'requestKeyHash':state['requestKeyHash'],'reason':event.reason,
            'proofHash':state['proofHash'],'snapshot':deepcopy(snapshot),'statusLabel':'已承接','stateMachineConsistent':True})
        previous=event.target_state
    return result

def _historical(row,context):
    if row.pk not in context['history']:
        native._validate_allocation(row,row.company_id,verify_budget=False,read_cache=context['cache'],validation_cache=context['validations'])
        native._scope_budget(row.operation_requirement,row.company_id,
            source_scope=native._allocation_budget_scope(row.operation_requirement,row.company_id,plan=row.production_plan),
            read_cache=context['cache'],validation_cache=context['validations'])
        context['history'][row.pk]=True

def _row(row,context,*,include_candidates=False):
    issues=[];historical=True;proof=None;history=[];current=None;candidates=[]
    try:
        _historical(row,context);history=_history(row);current=_current_context(row)
        if include_candidates:candidates=_candidates(row)
        if history:
            last=history[-1]
            target=EngineeringRuleDefinition.objects.filter(pk=last['targetRuleId'],company_id=row.company_id).first()
            try:valid_target=_candidate(row,target) if target else None
            except Exception as error:
                if not hasattr(error,'code'):raise
                valid_target=None
            if (last['currentContextHash']==current['currentContextHash'] and valid_target
                    and valid_target==last['snapshot']['targetRule']):proof=last
            else:issues.append('资源或已承接规则依据再次变化，须正式重新承接，原记录保留。')
        elif not current['ready']:issues.extend(current['blockingReasons'])
    except Exception as error:
        if not hasattr(error,'code'):raise
        historical=False;issues.append(getattr(error,'message',str(error)))
    ready=historical and bool(current) and ((bool(proof)) if history else current['ready']) and not issues
    snapshot=row.operation_requirement.calculation.trace.get('sourceSnapshot',{})
    result={'allocationId':row.pk,'operationRequirementId':row.operation_requirement_id,'ruleId':row.rule_id,
        'ruleVersion':row.rule_version,'operationId':row.operation_id,'quantity':str(row.allocated_quantity),'uomId':row.uom_id,
        'sourceQuantity':str(row.source_quantity),'sourceUomId':row.source_uom_id,
        'allocationHash':_allocation_hash(row),'sourceHash':row.source_hash,
        'currentContextHash':current['currentContextHash'] if current else None,
        'handoffVersion':len(history),'handoffProof':proof,'history':history,'historicalValid':historical,
        'historicalSource':{'ruleId':row.rule_id,'ruleVersion':row.rule_version,'manufacturing':deepcopy(snapshot.get('manufacturing')),
            'statusLabel':'原冻结来源及审计已独立核验' if historical else '原冻结来源尚未通过独立核验',
            'generationAuditReference':f'OrganizationOperatingAuditRecord:{row.operation_requirement.audit_record_id}',
            'allocationAuditReference':f'OrganizationOperatingAuditRecord:{row.audit_record_id}'},
        'currentSource':current,'currentSourceReady':ready,'differences':issues,
        'blockingReasons':issues,'candidateRules':candidates,
        'statusCode':'handed_off' if proof else 'current' if ready else 'handoff_required' if historical else 'history_unproven',
        'statusLabel':'已承接' if proof else '原来源当前仍合法' if ready else '待正式来源承接' if historical else '历史来源待核实'}
    if include_candidates:
        from .operation_allocation_source_version_service import resource_options,publication_history
        result['resourceOptions']=resource_options(row) if historical and not ready else []
        result['publicationHistory']=publication_history(row)
        result['publishedVersionProof']=result['publicationHistory'][-1] if result['publicationHistory'] else None
    return result

def _admission_item(item):
    """Exact target proof references, without copying catalogue manifests.

    The full native history/current checks have already run in _row. MES
    freezes only necessary identities and quantities; the PDE maintenance
    reader retains full audited differences and source snapshots.
    """
    keys=('allocationId','operationRequirementId','ruleId','ruleVersion','operationId','quantity','uomId',
        'sourceQuantity','sourceUomId','allocationHash','sourceHash','currentContextHash','handoffVersion',
        'historicalValid','currentSourceReady','blockingReasons','statusCode','statusLabel')
    result={key:deepcopy(item[key]) for key in keys}
    proof=item['handoffProof']
    proof_keys=('ref','id','companyId','allocationId','targetRuleId','targetRuleVersion','version','projectionVersion',
        'proofHash','allocationHash','sourceHash','currentContextHash','auditReference','requestHash',
        'requestKeyHash','stateMachineConsistent','statusLabel')
    result['handoffProof']={key:deepcopy(proof[key]) for key in proof_keys} if proof else None
    return result

def read_plan_allocation_admission(*,user,production_plan_id,routing_step_id,company_id=None):
    if user:
        _actor(user)
        if company_id is not None and company_id!=user.company_id:_fail('SOURCE_HANDOFF_SCOPE_DENIED','来源读取公司与本人范围不一致。')
        company_id=user.company_id
    if any(type(value) is not int or value<=0 for value in (company_id,production_plan_id,routing_step_id)):
        _fail('SOURCE_HANDOFF_SCOPE_REQUIRED','来源读取必须明确公司、计划及准确步骤。')
    with allocation_admission_context(user=user,company_id=company_id) as context:
        _refresh(context)
        key=(production_plan_id,routing_step_id)
        if key in context['admissions']:return deepcopy(context['admissions'][key])
        from planning.models import ProductionPlan
        plan=context['plans'].get(production_plan_id)
        if plan is None:
            plan=ProductionPlan.objects.select_related('planning_requirement__demand__manufacturing_output',
                'planning_requirement__demand__sales_order_item__sales_order').filter(pk=production_plan_id,
                planning_requirement__demand__sales_order_item__sales_order__company_id=company_id).first()
            if plan is not None:context['plans'][production_plan_id]=plan
        if plan is None:_fail('SOURCE_HANDOFF_SCOPE_DENIED','未找到本公司准确计划来源。')
        saved=_rows(company_id,production_plan_id,context)
        if saved:
            version=resolve_step_context(plan,routing_step_id,user=user,read_cache=context['cache'])
            step=version['step'];root=version.get('root_step')
            step_ids={routing_step_id,step.pk}
            if root:step_ids.add(root.pk)
            rows=[row for row in saved if row.routing_step_id in step_ids]
        else:
            # No allocation is not a manufacturing/readiness proof. This
            # precise internal aspect contributes no handoff binding or
            # manufactured source; existing MES engineering, applicability,
            # preparation and receipt gates remain the current authority.
            from .models import RoutingStep
            if not RoutingStep.objects.filter(pk=routing_step_id,routing_version__routing__company_id=company_id).exists():
                _fail('SOURCE_HANDOFF_SCOPE_DENIED','未找到本公司准确工艺步骤。')
            rows=[]
        items=[_admission_item(_row(row,context)) for row in rows]
        reasons=[reason for item in items for reason in item['blockingReasons']]
        proof=[item['handoffProof'] for item in items if item['handoffProof']]
        binding={'allocationSourceHandoffRefs':[p['ref'] for p in proof],
            'allocationSourceHandoffHashes':[p['proofHash'] for p in proof],
            'allocationSourceHandoffVersions':[p['version'] for p in proof]} if proof else {}
        result={'contractVersion':CONTRACT,'companyId':company_id,'productionPlanId':production_plan_id,
            'routingStepId':routing_step_id,'ready':not reasons,'actionAdmission':bool(user),
            'items':items,'blockingReasons':reasons,'sourceBinding':binding,
            'sourceAspectOnly':True,'statusLabel':'已核对目标分配的历史及当前来源' if saved else '本计划尚无已保存分配；本项不替代正式工程、执行模式或接收准入',
            'budgetPreserved':True,'businessWriteCount':0,'auditWriteCount':0,'stateTransitionWriteCount':0}
        result['admissionHash']=_hash(result);context['admissions'][key]=deepcopy(result)
        return result
