"""Append-only correction of a development freeze; no historical row rewrite.

The route plan identifies required operations and their real quantity source.
An input plan is a separate, exact actual-receipt allocation reference. Neither
plan dispatches a task, starts production, consumes stock or proves completion.
Resource selection, precise workshop receipt, dispatch and custody stay native.
"""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import re
from django.db import transaction
from masterdata.models import MasterDataWriteRequest, ExternalIdentity, UnitOfMeasure
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import record_projected_business_transition
from .services import record_audit
from .work_order_execution_service import _hash, _fail, _verify

CONTRACT='PCE-OPERATION-CONTINUATION-V1'
ROUTE='ProductionOperationContinuationRoute'
INPUT='ProductionOperationReceiptInputPlan'
ACTION='production.operation_source.continue'
NAMESPACE='MES_FORMAL_OPERATION_CONTINUATION'


def _history(subject,kind):
    """One append-only record per subject; all five native audit links verified."""
    order=subject if kind==ROUTE else subject.work_order
    events=list(BusinessStateTransition.objects.filter(object_type=kind,object_id=subject.pk).order_by('version','pk'))
    ledgers=list(MasterDataWriteRequest.objects.filter(organization_id=order.company_id,entity_type=kind,
        target_entity_id=str(subject.pk),action_code=ACTION).select_related('source_identity'))
    if not events:
        if ledgers:_fail('CONTINUATION_HISTORY_INCONSISTENT','承接记录缺少正式状态事实。')
        return None
    if len(events)!=1 or len(ledgers)!=1:_fail('CONTINUATION_HISTORY_INCONSISTENT','承接来源存在重复或不完整历史。')
    event,ledger=events[0],ledgers[0]
    match=re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)',event.audit_reference or '')
    audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
    state=(audit.after_snapshot or {}).get('state') if audit else None
    identity=ledger.source_identity
    if not isinstance(state,dict) or not isinstance(state.get('snapshot'),dict):
        _fail('CONTINUATION_HISTORY_INCONSISTENT','承接审计来源不完整。')
    snapshot=state['snapshot'];proof_hash=_hash(snapshot)
    intent=state.get('intent') or {}
    authorization=(audit.after_snapshot or {}).get('authorization') or {}
    if (event.version!=1 or event.source_state!='' or event.target_state!='recorded:'+proof_hash
            or event.action_code!=ACTION or audit.organization_id!=order.company_id
            or audit.target_type!=kind or audit.target_id!=subject.pk or audit.actor_id!=event.operator_id
            or audit.action_code!=ACTION or audit.reason!=event.reason
            or audit.before_snapshot.get('state')!={'status':''}
            or state.get('contractVersion')!=CONTRACT or state.get('proofHash')!=proof_hash
            or state.get('actorId')!=event.operator_id or state.get('companyId')!=order.company_id
            or _hash(intent)!=ledger.request_hash or intent.get('actorId')!=event.operator_id
            or intent.get('companyId')!=order.company_id or intent.get('kind')!=kind or intent.get('subjectId')!=subject.pk
            or (intent.get('payload') or {}).get('reason','').strip()!=event.reason
            or authorization.get('allowed') is not True
            or not (state.get('qualification') or {}).get('ready')
            or not ((state.get('qualification') or {}).get('responsibility') or {}).get('qualificationProven')
            or (((state.get('qualification') or {}).get('responsibility') or {}).get('currentActorEvidence') or {}).get('userId')!=event.operator_id
            or (((state.get('qualification') or {}).get('responsibility') or {}).get('currentActorEvidence') or {}).get('companyId')!=order.company_id
            or not ((state.get('qualification') or {}).get('nativeDecision') or {}).get('allowed')
            or not ((state.get('qualification') or {}).get('actionDecision') or {}).get('granted')
            or state.get('workOrderId')!=order.pk or state.get('status')!=event.target_state
            or ledger.status!='COMMITTED' or ledger.request_hash!=state.get('requestHash')
            or ledger.audit_metadata!={'actorId':event.operator_id,'contractVersion':CONTRACT}
            or ledger.result!={'transitionId':event.pk,'proofHash':proof_hash}
            or not identity or identity.organization_id!=order.company_id or identity.source_system!=NAMESPACE
            or identity.target_entity_type!=kind or identity.target_entity_id!=str(subject.pk)
            or identity.source_fingerprint!=ledger.request_hash or identity.external_id!=sha256(ledger.idempotency_key.encode()).hexdigest()
            or identity.source_object_type!=ACTION or identity.mapping_status!='MATCH'
            or snapshot.get('workOrderSnapshotHash')!=order.snapshot_hash
            or snapshot.get('companyId')!=order.company_id or snapshot.get('workOrderId')!=order.pk):
        _fail('CONTINUATION_HISTORY_INCONSISTENT','承接状态、原冻结、审计、请求及持久身份不一致。')
    return {'contractVersion':CONTRACT,'ref':f'BusinessStateTransition:{event.pk}',
        'proofHash':proof_hash,'auditReference':event.audit_reference,'snapshot':deepcopy(snapshot),
        'operatorId':event.operator_id,'recordedAt':event.timestamp.isoformat(),
        'idempotencyKey':ledger.idempotency_key,'requestHash':ledger.request_hash}


def _writer(actor,order):
    from .work_order_release_admission_service import qualify_continuation_planner
    from .work_order_release_admission_contract import ACTION as RELEASE_ACTION
    if not actor or not actor.is_active or actor.company_id!=order.company_id:
        _fail('CONTINUATION_SCOPE_DENIED','承接仅限同公司有效正式计划责任人。',403)
    qualification=qualify_continuation_planner(actor,order.production_plan)
    if not qualification['ready']:
        _fail('CONTINUATION_WRITER_DENIED','计划物控职责、正式下达节点或同角色权限范围未通过核验。',403)
    from .operation_continuation_contract import register_action,MODULE
    from .work_order_release_admission_service import _PlanFacts
    from workflow_runtime.action_permissions import ActionPermissionValidator
    register_action()
    decision=ActionPermissionValidator(fact_provider=_PlanFacts(actor,order.production_plan)).evaluate(
        user=actor,module_code=MODULE,action_code=ACTION,object_ids=[order.production_plan_id],
        selection_count=1,requested_legal_entity_id=str(actor.company_id))
    if not decision['granted']:
        _fail('CONTINUATION_WRITER_DENIED','当前承接动作未通过同公司计划权限校验。',403)
    qualification['actionDecision']=decision
    return {**qualification['nativeDecision'],'continuationQualification':qualification,
        'permissionCodes':[ACTION,RELEASE_ACTION]}


def _store(actor,subject,kind,snapshot,payload,authorization):
    order=subject if kind==ROUTE else subject.work_order
    key=payload.get('idempotencyKey');reason=payload.get('reason')
    if not isinstance(key,str) or not 1<=len(key)<=120 or not isinstance(reason,str) or not reason.strip():
        _fail('CONTINUATION_INTENT_REQUIRED','承接须有稳定请求标识和具体原因。')
    intent={'actorId':actor.pk,'companyId':actor.company_id,'kind':kind,'subjectId':subject.pk,
        'payload':{k:v for k,v in payload.items() if k!='idempotencyKey'}}
    request_hash=_hash(intent)
    prior=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,entity_type=kind,idempotency_key=key).first()
    existing=_history(subject,kind)
    if prior:
        if prior.request_hash!=request_hash or not existing or prior.target_entity_id!=str(subject.pk):
            _fail('CONTINUATION_IDEMPOTENCY_CONFLICT','原请求标识已绑定另一承接意图。')
        return existing,False
    if existing:_fail('CONTINUATION_ALREADY_RECORDED','本对象已有正式承接；保留原记录，不能换标识覆盖。')
    proof_hash=_hash(snapshot);target='recorded:'+proof_hash
    state={'contractVersion':CONTRACT,'companyId':actor.company_id,'workOrderId':order.pk,'actorId':actor.pk,
        'status':target,'snapshot':deepcopy(snapshot),'proofHash':proof_hash,'intent':intent,'requestHash':request_hash,
        'qualification':deepcopy(authorization['continuationQualification'])}
    audit=record_audit(user=actor,action_code=ACTION,target=subject,target_type=kind,target_no=order.no,
        before={'status':''},after=state,authorization=authorization,reason=reason.strip())
    event=record_projected_business_transition(object_type=kind,object_id=subject.pk,source_state='',target_state=target,
        action_code=ACTION,operator=actor,reason=reason.strip(),audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
        allowed_transitions={('',target)})
    identity=ExternalIdentity.objects.create(organization_id=actor.company_id,source_system=NAMESPACE,source_type='INTERNAL',
        source_object_type=ACTION,external_id=sha256(key.encode()).hexdigest(),target_entity_type=kind,
        target_entity_id=str(subject.pk),mapping_status='MATCH',source_fingerprint=request_hash,
        audit_metadata={'contractVersion':CONTRACT,'originalFrozenRecordPreserved':True})
    MasterDataWriteRequest.objects.create(organization_id=actor.company_id,action_code=ACTION,entity_type=kind,
        target_entity_id=str(subject.pk),idempotency_key=key,request_hash=request_hash,status='COMMITTED',source_identity=identity,
        result={'transitionId':event.pk,'proofHash':proof_hash},audit_metadata={'actorId':actor.pk,'contractVersion':CONTRACT})
    return _history(subject,kind),True


def read_route_plan(order,actor):
    if not actor or actor.company_id!=order.company_id:_fail('CONTINUATION_SCOPE_DENIED','承接不属于本公司。',403)
    if order.usage_purpose!='PRODUCTION_USE':return None
    _verify(order)
    record=_history(order,ROUTE)
    if not record:return None
    from pde.capacity_route_applicability import read_route_capacity
    operations=list(order.operations.select_related('effective_routing_version').order_by('sequence'))
    snapshot=record['snapshot'];versions={}
    for op in operations:
        if op.effective_routing_version_id not in versions:
            versions[op.effective_routing_version_id]=read_route_capacity(op.effective_routing_version,company_id=order.company_id)
    expected=[{'operationId':op.pk,'snapshotHash':op.snapshot_hash,'stepId':op.effective_step_id,
        'sequence':op.sequence,'applicability':versions[op.effective_routing_version_id]['steps'].get(op.effective_step_id,{}).get('result')}
        for op in operations]
    if (any(v['status']!='VALID' for v in versions.values()) or snapshot.get('operations')!=expected
            or snapshot.get('sourceHashes')!=sorted({v['sourceSha256'] for v in versions.values()})):
        _fail('CONTINUATION_SOURCE_CHANGED','正式工艺来源或承接范围已变化，原承接保留，禁止复用过期资格。')
    return record


def record_route_plan(*,user,work_order,payload):
    from .formal_scheduling_service import _writer_lock
    from pde.capacity_route_applicability import read_route_capacity,has_development_assumption
    if not isinstance(payload,dict) or set(payload)!={'idempotencyKey','reason'}:
        _fail('CONTINUATION_PAYLOAD_INVALID','承接只接收稳定请求标识与原因，数量、目标、状态均由正式来源确定。')
    with transaction.atomic():
        _writer_lock(user);authorization=_writer(user,work_order);_verify(work_order)
        if work_order.status!='released' or work_order.usage_purpose!='PRODUCTION_USE':
            _fail('CONTINUATION_RELEASE_REQUIRED','更正须引用同公司原生已下达正式工单。')
        ops=list(work_order.operations.select_related('effective_routing_version').order_by('sequence'))
        if not any(has_development_assumption(op.source_snapshot) for op in ops):
            _fail('CONTINUATION_NOT_DEVELOPMENT_FREEZE','本机制只更正有明确开发假设标识的原冻结，不覆盖业务裁决。')
        sources={}
        for op in ops:
            if op.effective_routing_version_id not in sources:
                sources[op.effective_routing_version_id]=read_route_capacity(op.effective_routing_version,company_id=work_order.company_id)
        if any(s['status']!='VALID' or any(r.get('result')=='PENDING' for r in s['steps'].values()) for s in sources.values()):
            _fail('CONTINUATION_FORMAL_SOURCE_REQUIRED','正式完整工艺来源未通过核实，不能更正原冻结。')
        from .operation_exemption_authority import _load_scope
        for op in ops:
            _,context,version,_=_load_scope(op,user)
            if context[6]['result']!=sources[op.effective_routing_version_id]['steps'][op.effective_step_id]['result']:
                _fail('CONTINUATION_APPLICABILITY_CONFLICT','当前业务适用结果与正式来源仍有冲突，不能覆盖。')
        snapshot={'companyId':work_order.company_id,'workOrderId':work_order.pk,'workOrderNo':work_order.no,
            'workOrderSnapshotHash':work_order.snapshot_hash,'productionPlanId':work_order.production_plan_id,
            'originalHistoryPreserved':True,'quantityPolicy':'ACTUAL_RECEIPT_INPUT_NOT_CAPACITY_OR_OUTPUT',
            'quantityPolicyBasis':'用户统一交接规则及2026-11-13实物交接来源指令；按正式批次实际收讫，未知量不填造',
            'sourceHashes':sorted({s['sourceSha256'] for s in sources.values()}),
            'operations':[{'operationId':op.pk,'snapshotHash':op.snapshot_hash,'stepId':op.effective_step_id,
                'sequence':op.sequence,'applicability':sources[op.effective_routing_version_id]['steps'][op.effective_step_id]['result']}
                for op in ops], 'automaticDispatch':False,'automaticStart':False,'stockConsumed':False}
        return _store(user,work_order,ROUTE,snapshot,payload,authorization)


def execution_mode(operation,actor):
    """Effective input mode over original immutable operation + correction."""
    from pde.capacity_route_applicability import has_development_assumption
    frozen=operation.source_snapshot.get('frozenStep',{}).get('applicability',{})
    if frozen.get('result')!='NOT_APPLICABLE' or not has_development_assumption(frozen):return None
    route=read_route_plan(operation.work_order,actor)
    if not route:return None
    member=next(r for r in route['snapshot']['operations'] if r['operationId']==operation.pk)
    if member['applicability']!='REQUIRED':return None
    from .operation_exemption_authority import _load_scope
    _,current_scope,_,_=_load_scope(operation,actor)
    if current_scope[6].get('result')!='REQUIRED' or not current_scope[6].get('formalApplicabilityValidated'):
        _fail('CONTINUATION_APPLICABILITY_CHANGED','当前正式适用结果与承接方案不一致，禁止沿旧计划执行。')
    from .operation_execution_mode import (_result,QUANTIFIED,CONTRACT as MODE_CONTRACT,
        _requires_native_policy_read,_load_formal_mode_basis,_classify_basis)
    # A pre-existing explicit preparation policy outranks receipt-derived Q.
    # Missing/invalid policy proof stays pending; never relabel it as quantity.
    if _requires_native_policy_read(operation):
        return _classify_basis(operation,_load_formal_mode_basis(operation,actor))
    from .operation_predecessor_authority import _historical_proof_only
    plan=read_input_plan(operation,actor,verify_current=not _historical_proof_only.get())
    proof={'contractVersion':MODE_CONTRACT,'executionMode':QUANTIFIED,'companyId':actor.company_id,
        'workOrderId':operation.work_order_id,'operationId':operation.pk,'operationSnapshotHash':operation.snapshot_hash,
        'sourceAuthority':'FORMAL_CONTINUATION_ACTUAL_RECEIPT_INPUT','continuationRouteRef':route['ref'],
        'continuationRouteHash':route['proofHash'],'continuationInputPlan':deepcopy(plan)}
    result=_result(operation,QUANTIFIED,ready=plan is not None,proof=proof,
        issues=() if plan else ('本工序已列入正式承接计划，等待本工序真实实收批次；不以0或标准产能填充投产量。',))
    if plan:
        inputs=plan['snapshot']['input']
        result['referenceWorkload']={'quantity':inputs['quantity'],'uomId':inputs['uomId'],
            'uomCode':inputs['uomCode'],'uomLabel':inputs['uomLabel'],
            'statusLabel':'正式实际接收投入计划参考；不等于实际产出','nullReason':None}
    else:
        result['referenceWorkload']={'quantity':None,'uomId':None,'uomCode':None,'uomLabel':None,
            'statusLabel':'等待本工序正式实际收讫批次','nullReason':'AWAITING_FORMAL_ACTUAL_RECEIPT'}
    return result


def is_receipt_mode(mode):
    return bool(mode.get('ready') and (mode.get('modeSourceProof') or {}).get('sourceAuthority')==
        'FORMAL_CONTINUATION_ACTUAL_RECEIPT_INPUT' and (mode.get('modeSourceProof') or {}).get('continuationInputPlan'))


def frozen_input_reference(task):
    """Verify the supplement identity before the native task audit is read.

    The task audit freezes the exact actual receipt reference and quantity;
    current receipt eligibility is independently re-proved by execution_mode.
    This does not recurse into the task's own history verifier.
    """
    source=task.source_snapshot;proof=source.get('modeSourceProof') or {}
    if proof.get('sourceAuthority')!='FORMAL_CONTINUATION_ACTUAL_RECEIPT_INPUT':return None
    plan=proof.get('continuationInputPlan') or {};snapshot=plan.get('snapshot') or {};inputs=snapshot.get('input') or {}
    route=_history(task.work_order,ROUTE)
    from .operation_execution_mode import CONTRACT as MODE_CONTRACT
    if (source.get('executionMode')!='QUANTIFIED' or proof.get('contractVersion')!=MODE_CONTRACT
            or source.get('modeSourceHash')!=_hash(proof) or proof.get('executionMode')!='QUANTIFIED'
            or proof.get('companyId')!=task.company_id or proof.get('workOrderId')!=task.work_order_id
            or proof.get('operationId')!=task.source_operation_id or proof.get('operationSnapshotHash')!=task.source_operation.snapshot_hash
            or plan.get('contractVersion')!=CONTRACT or plan.get('proofHash')!=_hash(snapshot)
            or snapshot.get('companyId')!=task.company_id or snapshot.get('workOrderId')!=task.work_order_id
            or snapshot.get('operationId')!=task.source_operation_id
            or snapshot.get('originalOperationSnapshotHash')!=task.source_operation.snapshot_hash
            or not route or snapshot.get('routePlanHash')!=route['proofHash'] or snapshot.get('routePlanRef')!=route['ref']
            or inputs.get('quantity')!=task.workload_quantity or inputs.get('uomId')!=task.workload_uom_id
            or not isinstance(inputs.get('receipts'),list) or not inputs['receipts']):
        _fail('CONTINUATION_TASK_PLAN_INCONSISTENT','任务冻结投产量、单位、原工序与正式承接证明不一致。')
    return {'quantity':inputs['quantity'],'uomId':inputs['uomId'],'uomCode':inputs['uomCode'],
        'uomLabel':inputs['uomLabel'],'statusLabel':'原生任务冻结的正式实收投入计划参考','nullReason':None}


def _receipt_sources(operation,ids):
    from .operation_handover_models import OperationHandover
    from .operation_handover_authority import verify_task_custody
    from .operation_handover_facts import _header
    from .workshop_task_models import ProductionWorkshopTask
    if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids) or any(type(x)is not int or x<=0 for x in ids):
        _fail('CONTINUATION_RECEIPT_REQUIRED','请选择互不重复的正式已收讫批次。')
    rows=[];units=set();centers=set();total=Decimal(0)
    for pk in sorted(ids):
        h=OperationHandover.objects.filter(pk=pk,company_id=operation.work_order.company_id,target_operation=operation).first()
        if not h:_fail('CONTINUATION_RECEIPT_SCOPE_MISMATCH','实收批次必须准确属于本工单本目标工序。')
        source=ProductionWorkshopTask.objects.get(pk=h.data['taskId'],company_id=h.company_id)
        if source.work_order_id!=operation.work_order_id:_fail('CONTINUATION_RECEIPT_SCOPE_MISMATCH','禁止跨工单借用投入数量。')
        verify_task_custody(source);fact=_header(h)
        amount=Decimal(fact['correctedMatchedReceiveQuantity'])
        allocation=h.allocations.select_related('uom').first()
        if amount<=0 or not allocation or h.status!='received':
            _fail('CONTINUATION_RECEIPT_NOT_FINAL','须为原生服务已全部实际收讫且净匹配数量为正的批次。')
        units.add(allocation.uom_id);centers.add(h.target_work_center_id);total+=amount
        rows.append({'handoverId':h.pk,'businessNo':fact['businessNo'],'sourceSnapshotHash':h.source_snapshot_hash,
            'version':h.version,'receivedQuantity':str(amount),'uomId':allocation.uom_id,
            'workCenterId':h.target_work_center_id,'receiptEventHashes':[r['eventHash'] for r in fact['historicalReceipts']]})
    if len(units)!=1 or len(centers)!=1:_fail('CONTINUATION_RECEIPT_UNIT_CONFLICT','投入计划只承接同一原单位、同一接收中心；不隐式换算或混合。')
    unit=UnitOfMeasure.objects.get(pk=next(iter(units)),company_id=operation.work_order.company_id,is_active=True)
    return {'receipts':rows,'quantity':format(total,'f'),'uomId':unit.pk,'uomCode':unit.code,'uomLabel':unit.name,
        'workCenterId':next(iter(centers)),'quantityMeaning':'本工序正式投产投入参考；不等于实际产出，不自动消耗实物'}


def read_input_plan(operation,actor,*,verify_current=True):
    from .workshop_task_models import ProductionWorkshopTask
    from pde.capacity_route_applicability import has_development_assumption
    if not actor or actor.company_id!=operation.work_order.company_id:
        _fail('CONTINUATION_SCOPE_DENIED','投入计划不属于本公司。',403)
    # This extension repairs excluded placeholders only. Existing actual task
    # quantities, native NQ policies and ordinary business decisions stay exact.
    frozen=operation.source_snapshot.get('frozenStep',{}).get('applicability',{})
    if frozen.get('result')!='NOT_APPLICABLE' or not has_development_assumption(frozen):
        return None
    task=ProductionWorkshopTask.objects.filter(source_operation=operation).first()
    saved=(task.source_snapshot.get('modeSourceProof') or {}).get('continuationInputPlan') if task else None
    if task and saved is None:
        return None
    route=read_route_plan(operation.work_order,actor)
    if route is None:return None
    member=next(r for r in route['snapshot']['operations'] if r['operationId']==operation.pk)
    if member['applicability']!='REQUIRED':return None
    if saved:
        from .workshop_task_service import _verify_history
        _verify_history(task)
        snapshot=saved['snapshot']
        if (saved.get('proofHash')!=_hash(snapshot)
                or snapshot.get('originalOperationSnapshotHash')!=operation.snapshot_hash
                or snapshot.get('routePlanHash')!=route['proofHash']
                or snapshot.get('operationId')!=operation.pk or snapshot.get('workOrderId')!=operation.work_order_id):
            _fail('CONTINUATION_TASK_PLAN_INCONSISTENT','任务冻结投入计划与正式承接来源不一致。')
        if verify_current:
            actual=_receipt_sources(operation,[r['handoverId'] for r in snapshot['input']['receipts']])
            if actual!=snapshot['input']:
                _fail('CONTINUATION_RECEIPT_CHANGED','实收更正或来源已变化；原任务保留，不自动重定量。')
        return deepcopy(saved)
    from .operation_handover_models import OperationHandover
    ids=list(OperationHandover.objects.filter(company_id=actor.company_id,target_operation=operation,
        status='received').order_by('pk').values_list('pk',flat=True))
    if not ids:return None
    inputs=_receipt_sources(operation,ids)
    from pde.capacity_route_applicability import read_route_capacity
    formal=read_route_capacity(operation.effective_routing_version,company_id=actor.company_id)
    if inputs['workCenterId'] not in formal['steps'][operation.effective_step_id]['workCenterIds']:
        _fail('CONTINUATION_RESOURCE_MISMATCH','实收中心与本工序正式资源不一致。')
    snapshot={'companyId':actor.company_id,'workOrderId':operation.work_order_id,
        'workOrderSnapshotHash':operation.work_order.snapshot_hash,'productionPlanId':operation.work_order.production_plan_id,
        'operationId':operation.pk,'originalOperationSnapshotHash':operation.snapshot_hash,
        'routePlanRef':route['ref'],'routePlanHash':route['proofHash'],'input':inputs,
        'executionMode':'QUANTIFIED','capacityUsedAsQuantity':False,'outputQuantityInvented':False,
        'originalFrozenRecordPreserved':True,'freezingAuthority':'NATIVE_WORKSHOP_TASK_DRAFT_AND_AUDIT'}
    digest=_hash(snapshot)
    return {'contractVersion':CONTRACT,'ref':route['ref']+'/operation/'+str(operation.sequence)+'/input/'+digest,
        'proofHash':digest,'snapshot':snapshot,'source':'FORMAL_RECEIPT_DERIVED_INPUT_PLAN'}
