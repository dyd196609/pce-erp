

# Native formal continuation: individually restored symbols; existing proofs preserved.
from copy import deepcopy

from hashlib import sha256

import re

from types import SimpleNamespace

from django.db import IntegrityError, DatabaseError, transaction

from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest

from pde.models import WorkCenter, WorkCenterOperationCapability

from system.models import OrganizationOperatingAuditRecord, Workshop

from workflow_runtime.action_permissions import ActionPermissionValidator

from workflow_runtime.models import BusinessStateTransition

from workflow_runtime.state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition)

from . import formal_scheduling_service as formal

from . import work_order_workshop_receipt_service as receipts

from .work_order_workshop_receipt_models import ProductionWorkOrderWorkshopReceipt as Receipt

from .work_order_models import ProductionWorkOrderOperation as Operation

from .workshop_task_models import ProductionWorkshopTask as Task

from .work_order_execution_service import _verify, _hash, _fail

from .work_order_release_admission_service import _effective

from .workshop_task_time import task_datetime_label

from .services import record_audit, PlanningBusinessError

from .operation_resource_selection_contract import (CONTRACT,GET_PATH,MODULE,PROCESS,WORKFLOW_NODE,
    RESPONSIBILITY,READ_PERMISSION,REQUIRED_PERMISSION,SELECT_ACTION,RECEIVE_ACTION,SELECT_OBJECT,
    RECEIVE_OBJECT,SUPPLEMENT_OBJECT,ANCHOR_KIND,NAMESPACE,register_actions,action_contract)

SELECT_EXPECTED=('expectedWorkOrderVersion','expectedWorkOrderSnapshotHash','expectedOperationSnapshotHash',
    'expectedSelectionVersion','expectedCandidateSnapshotHash','workCenterId')

RECEIVE_EXPECTED=('expectedWorkOrderVersion','expectedWorkOrderSnapshotHash','expectedOperationSnapshotHash',
    'expectedSelectionVersion','expectedSelectionHash','expectedCurrentResourceHash','expectedReceiptVersion')

def _today():
    now=timezone.now()
    return timezone.localdate() if timezone.is_aware(now) else now.date()

def _history_error():
    _fail('OPERATION_RESOURCE_HISTORY_UNPROVEN','资源选择／精确接收的冻结来源、责任、审计、状态或幂等证明不一致。')

def _intent_hash(actor_id,action,object_id,payload):
    body={key:value for key,value in payload.items() if key!='idempotencyKey'}
    body['reason']=body['reason'].strip();body['requestKeyHash']=sha256(payload['idempotencyKey'].encode()).hexdigest()
    return _hash({'actorId':actor_id,'actionCode':action,'operationId':object_id,'payload':body})

def _payload(payload,select):
    expected=SELECT_EXPECTED if select else RECEIVE_EXPECTED
    if not isinstance(payload,dict) or set(payload)!=set(expected)|{'reason','idempotencyKey'}:
        _fail('OPERATION_RESOURCE_PAYLOAD_INVALID','请完整引用本次工单、工序、资源候选／选择版本和接收版本；不接受业务状态或默认资源。',400)
    integers={'expectedWorkOrderVersion','expectedSelectionVersion','expectedReceiptVersion','workCenterId'}
    for key in expected:
        if key in integers:
            if type(payload[key]) is not int or payload[key]<(1 if key=='workCenterId' else 0):
                _fail('OPERATION_RESOURCE_VERSION_INVALID','工单、资源或接收版本无效，请只读重新读取。',400)
        elif not isinstance(payload[key],str) or not re.fullmatch('[0-9a-f]{64}',payload[key]):
            _fail('OPERATION_RESOURCE_HASH_INVALID','资源选择／接收缺少本次正式读取的完整来源哈希。',400)
    if not isinstance(payload['reason'],str) or not 2<=len(payload['reason'].strip())<=240:
        _fail('OPERATION_RESOURCE_REASON_REQUIRED','请填写2至240字的正式资源选择或接收原因。',400)
    if not isinstance(payload['idempotencyKey'],str) or not 1<=len(payload['idempotencyKey'])<=120:
        _fail('OPERATION_RESOURCE_IDEMPOTENCY_REQUIRED','缺少有效防重复标识，请先只读回查。',400)

def _subject_order(subject):return subject.work_order

def _proof_history(subject,kind):
    order=_subject_order(subject)
    action={SELECT_OBJECT:SELECT_ACTION,RECEIVE_OBJECT:RECEIVE_ACTION,SUPPLEMENT_OBJECT:REQUIRED_PERMISSION}[kind]
    events=list(BusinessStateTransition.objects.filter(object_type=kind,object_id=subject.pk).order_by('version','pk'))
    ledgers=list(MasterDataWriteRequest.objects.filter(organization_id=order.company_id,entity_type=kind,
        target_entity_id=str(subject.pk),action_code=action).select_related('source_identity'))
    if not events:
        if ledgers:_history_error()
        return []
    if len(events)!=1 or len(ledgers)!=1:_history_error()
    event,ledger=events[0],ledgers[0]
    match=re.fullmatch('OrganizationOperatingAuditRecord:([1-9][0-9]*)',event.audit_reference or '')
    audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
    before=audit.before_snapshot if audit and isinstance(audit.before_snapshot,dict) else {}
    after=audit.after_snapshot if audit and isinstance(audit.after_snapshot,dict) else {}
    state=after.get('state');auth=after.get('authorization');node=after.get('workflowNode')
    if (not isinstance(state,dict) or not isinstance(auth,dict) or not isinstance(node,dict)
            or not isinstance(state.get('snapshot'),dict) or not isinstance(state.get('qualification'),dict)
            or not isinstance(state.get('actorEvidence'),dict) or not isinstance(state.get('intentPayload'),dict)):_history_error()
    snapshot,q,actor=state['snapshot'],state['qualification'],state['actorEvidence']
    identity=ledger.source_identity
    target=('selected:' if kind==SELECT_OBJECT else 'received:')+_hash(snapshot)
    if (event.version!=1 or event.source_state!='' or event.target_state!=target or event.action_code!=action
            or event.workflow_instance_id is not None or not audit or audit.organization_id!=order.company_id
            or audit.target_type!=kind or audit.target_id!=subject.pk or audit.actor_id!=event.operator_id
            or audit.action_code!=action or audit.reason!=event.reason or before.get('state')!={'status':''}
            or state.get('status')!=target or state.get('contractVersion')!=CONTRACT or state.get('projectionVersion')!=1
            or state.get('proofHash')!=_hash(snapshot) or snapshot.get('companyId')!=order.company_id
            or snapshot.get('workOrderId')!=order.pk or snapshot.get('workOrderVersion')!=order.version
            or snapshot.get('workOrderSnapshotHash')!=order.snapshot_hash or actor.get('userId')!=event.operator_id
            or actor.get('companyId')!=order.company_id or q.get('currentActorEvidence')!=actor
            or q.get('qualificationProven') is not True or not isinstance(q.get('checks'),list) or not q['checks']
            or any(not isinstance(check,dict) or check.get('eligible') is not True for check in q['checks'])
            or actor.get('explicitAuthorityProven') is not True or not actor.get('matchedAuthorityEvidence')
            or auth.get('allowed') is not True or not isinstance(auth.get('permissionCodes'),list)
            or not any(code in (REQUIRED_PERMISSION,'*') for code in auth['permissionCodes'])
            or node.get('processCode')!=PROCESS or node.get('nodeCode')!=WORKFLOW_NODE
            or node.get('authorityActionCode')!=REQUIRED_PERMISSION or node.get('responsibilityCode')!=RESPONSIBILITY
            or node.get('processId')!=q.get('definitionId') or node.get('nodeId')!=q.get('nodeId')
            or before.get('workflowNode')!=node or ledger.status!='COMMITTED'
            or ledger.audit_metadata!={'actorId':event.operator_id,'contractVersion':CONTRACT}
            or not identity or identity.organization_id!=order.company_id or identity.source_system!=NAMESPACE
            or identity.source_type!='INTERNAL' or identity.source_object_type!=action
            or identity.external_id!=state.get('requestKeyHash') or identity.target_entity_type!=kind
            or identity.target_entity_id!=str(subject.pk) or identity.mapping_status!='MATCH'
            or identity.source_fingerprint!=ledger.request_hash
            or identity.audit_metadata!={'contractVersion':CONTRACT,'immutableOrderPreserved':True}
            or state.get('requestKeyHash')!=sha256(ledger.idempotency_key.encode()).hexdigest()
            or state.get('requestHash')!=ledger.request_hash
            or ledger.result!={'objectId':subject.pk,'transitionId':event.pk,'proofHash':_hash(snapshot),'projectionVersion':1}):_history_error()
    intent={**state['intentPayload'],'idempotencyKey':ledger.idempotency_key}
    if (_intent_hash(event.operator_id,action,subject.pk,intent)!=ledger.request_hash
            or intent.get('reason','').strip()!=event.reason):_history_error()
    if kind!=SUPPLEMENT_OBJECT:
        if (snapshot.get('operationId')!=subject.pk or snapshot.get('operationSnapshotHash')!=subject.snapshot_hash
                or snapshot.get('frozenOperation')!=subject.source_snapshot):_history_error()
        try:_payload(intent,kind==SELECT_OBJECT)
        except PlanningBusinessError:_history_error()
        expected={'expectedWorkOrderVersion':order.version,'expectedWorkOrderSnapshotHash':order.snapshot_hash,
            'expectedOperationSnapshotHash':subject.snapshot_hash}
        if any(intent.get(key)!=value for key,value in expected.items()):_history_error()
    else:
        if (snapshot.get('receiptAnchorId')!=subject.pk or snapshot.get('receiptAnchorHash')!=subject.snapshot_hash
                or not isinstance(snapshot.get('groupSnapshot'),dict)
                or snapshot.get('groupSnapshotHash')!=_hash(snapshot['groupSnapshot'])):_history_error()
        try:receipts._payload(intent)
        except PlanningBusinessError:_history_error()
        if (intent.get('expectedWorkOrderVersion')!=order.version
                or intent.get('expectedWorkOrderSnapshotHash')!=order.snapshot_hash
                or intent.get('expectedScopeSnapshotHash')!=snapshot['groupSnapshotHash']
                or intent.get('executionToken')!=receipts._token(SimpleNamespace(pk=event.operator_id),snapshot['groupSnapshot'],q)):_history_error()
    if kind==SELECT_OBJECT:
        candidate={key:value for key,value in snapshot.items() if key not in ('workCenterName','workshopName','candidateSnapshotHash')}
        if (snapshot.get('candidateSnapshotHash')!=_hash(candidate)
                or intent.get('expectedCandidateSnapshotHash')!=snapshot['candidateSnapshotHash']
                or intent.get('expectedSelectionVersion')!=0
                or intent.get('workCenterId')!=snapshot.get('currentResource',{}).get('workCenter',{}).get('id')):_history_error()
    elif kind==RECEIVE_OBJECT:
        selection=snapshot.get('selection')
        if (not isinstance(selection,dict) or snapshot.get('selectionHash')!=selection.get('proofHash')
                or snapshot.get('currentResourceHash')!=_hash(snapshot.get('currentResource'))
                or intent.get('expectedSelectionHash')!=snapshot['selectionHash']
                or intent.get('expectedSelectionVersion')!=snapshot.get('selectionVersion')
                or intent.get('expectedCurrentResourceHash')!=snapshot['currentResourceHash']
                or intent.get('expectedReceiptVersion')!=0
                or snapshot.get('receiptAnchorIsOriginalMembership') is not False):_history_error()
    zone=order.source_snapshot['sourceSchedule']['timezone']
    proof={'id':event.pk,'ref':f'BusinessStateTransition:{event.pk}','contractVersion':CONTRACT,
        'proofType':kind,'projectionVersion':1,'version':1,'proofHash':_hash(snapshot),'snapshot':deepcopy(snapshot),
        'companyId':order.company_id,'workOrderId':order.pk,'operationId':subject.pk if kind!=SUPPLEMENT_OBJECT else None,
        'actorId':event.operator_id,'actorLabel':actor.get('employeeName') or actor.get('username'),
        'currentActorEvidence':deepcopy(actor),'confirmedAt':event.timestamp.isoformat(),
        'timeLabel':task_datetime_label(event.timestamp,zone),'reason':event.reason,'auditReference':event.audit_reference,
        'requestKeyHash':state['requestKeyHash'],'requestHash':state['requestHash'],'statusCode':event.target_state,
        'statusLabel':{SELECT_OBJECT:'已选择资源',RECEIVE_OBJECT:'已精确接收',SUPPLEMENT_OBJECT:'原冻结车间组已补充接收'}[kind],
        'sourceState':'','targetState':event.target_state,'stateMachineConsistent':True}
    proof['statusTransitionHistory']=[{'id':event.pk,'version':1,'sourceState':'','targetState':event.target_state,
        'sourceStateLabel':'尚未保存本次正式证明','targetStateLabel':proof['statusLabel'],'actionCode':action,
        'operatorId':event.operator_id,'reason':event.reason,'auditReference':event.audit_reference,
        'timestamp':event.timestamp.isoformat(),'timestampLabel':proof['timeLabel']}]
    proof['statusTransitionCount']=1
    return [proof]

def _store_proof(actor,subject,kind,snapshot,q,payload):
    action={SELECT_OBJECT:SELECT_ACTION,RECEIVE_OBJECT:RECEIVE_ACTION,SUPPLEMENT_OBJECT:REQUIRED_PERMISSION}[kind]
    request_hash=_intent_hash(actor.pk,action,subject.pk,payload);reason=payload['reason'].strip()
    target=('selected:' if kind==SELECT_OBJECT else 'received:')+_hash(snapshot)
    state={'contractVersion':CONTRACT,'projectionVersion':1,'status':target,'snapshot':deepcopy(snapshot),
        'proofHash':_hash(snapshot),'qualification':deepcopy(q),'actorEvidence':deepcopy(q['currentActorEvidence']),
        'intentPayload':{k:v for k,v in payload.items() if k!='idempotencyKey'},'requestHash':request_hash,
        'requestKeyHash':sha256(payload['idempotencyKey'].encode()).hexdigest()}
    audit=record_audit(user=actor,action_code=action,target=subject,target_type=kind,
        target_no=subject.work_order.no,before={'status':''},after=state,authorization=q['nativeDecision'],reason=reason)
    node={'processCode':PROCESS,'nodeCode':WORKFLOW_NODE,'processId':q['definitionId'],'nodeId':q['nodeId'],
        'authorityActionCode':REQUIRED_PERMISSION,'responsibilityCode':RESPONSIBILITY}
    audit.before_snapshot['workflowNode']=node;audit.after_snapshot['workflowNode']=node
    audit.save(update_fields=['before_snapshot','after_snapshot'])
    event=record_projected_business_transition(object_type=kind,object_id=subject.pk,source_state='',target_state=target,
        action_code=action,operator=actor,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
        allowed_transitions={('',target)})
    identity=ExternalIdentity.objects.create(organization_id=actor.company_id,source_system=NAMESPACE,source_type='INTERNAL',
        source_object_type=action,external_id=state['requestKeyHash'],target_entity_type=kind,target_entity_id=str(subject.pk),
        mapping_status='MATCH',source_fingerprint=request_hash,audit_metadata={'contractVersion':CONTRACT,'immutableOrderPreserved':True})
    MasterDataWriteRequest.objects.create(organization_id=actor.company_id,action_code=action,entity_type=kind,
        target_entity_id=str(subject.pk),idempotency_key=payload['idempotencyKey'],request_hash=request_hash,
        status='COMMITTED',source_identity=identity,result={'objectId':subject.pk,'transitionId':event.pk,
            'proofHash':_hash(snapshot),'projectionVersion':1},audit_metadata={'actorId':actor.pk,'contractVersion':CONTRACT})
    return _proof_history(subject,kind)[0]

def _base_snapshot(operation):
    order=operation.work_order
    return {'companyId':order.company_id,'workOrderId':order.pk,'workOrderVersion':order.version,
        'workOrderSnapshotHash':order.snapshot_hash,'operationId':operation.pk,
        'operationSnapshotHash':operation.snapshot_hash,'frozenOperation':deepcopy(operation.source_snapshot)}

def resource_snapshot(operation,center):
    from .operation_resource_source import _current_snapshot
    return _current_snapshot(operation,center.workshop if center else None,effective_center=center)

def _current_version(operation,actor,center):
    from .operation_start_service import _current_version_facts
    return _current_version_facts(SimpleNamespace(source_operation=operation,work_order=operation.work_order,
        company_id=operation.work_order.company_id,work_center_id=center.pk if center else None,
        workshop_id=center.workshop_id if center else None,
        source_snapshot={'operation':operation.source_snapshot}),actor)

def _allocation_admission(operation,actor):
    from pde.operation_allocation_source_handoff_service import read_plan_allocation_admission
    return read_plan_allocation_admission(user=actor,production_plan_id=operation.work_order.production_plan_id,
        routing_step_id=operation.root_step_id)

def _current_qualification(actor,operation,center,action,*,source_ok=True,extra=()):
    if center is None or center.workshop is None:
        missing=list(dict.fromkeys(list(extra)+['请明确选择有正式能力且在本人责任车间内的工作中心。']))
        return {'ready':False,'qualificationProven':False,'checks':[],'issues':[],
            'missingItems':missing,
            'statusLabel':'；'.join(missing),'currentActorEvidence':receipts._employees(actor)[4],
            'nativeDecision':{},'definitionId':None,'nodeId':None}
    q,_=receipts._qualification(actor,operation.work_order,center.workshop,source_ok=source_ok)
    from .operation_resource_handoff_service import _OperationFacts
    decision=ActionPermissionValidator(fact_provider=_OperationFacts(operation)).evaluate(user=actor,
        module_code=MODULE,action_code=action,object_ids=[operation.pk],selection_count=1,
        requested_legal_entity_id=str(operation.work_order.company_id))
    version=_current_version(operation,actor,center)
    allocation=_allocation_admission(operation,actor)
    q=deepcopy(q);issues=[item['statusLabel'] for item in q['issues']]+list(extra)
    if not decision['granted']:issues.append('当前账号未通过资源选择／精确接收同一职责权限及范围校验。')
    if not version['ready']:issues.extend(item['statusLabel'] for item in version['issues'])
    if not allocation['ready']:issues.extend(allocation['blockingReasons'])
    q['checks'].extend([
        {'checkCode':'currentEngineeringVersion','complete':True,'eligible':bool(version['ready']),'statusLabel':version['statusLabel']},
        {'checkCode':'currentAllocationSource','complete':True,'eligible':bool(allocation['ready']),
            'statusLabel':'目标正式分配来源及整体预算已核验' if allocation['ready'] else '；'.join(allocation['blockingReasons'])},
        {'checkCode':'exactOperationAction','complete':True,'eligible':bool(decision['granted']),
            'statusLabel':'当前工序动作范围已核实' if decision['granted'] else '当前动作范围未通过'}])
    q.update(ready=not issues,qualificationProven=not issues,missingItems=list(dict.fromkeys(issues)),
        currentVersionFacts=version,currentAllocationAdmission=allocation,
        statusLabel='当前责任人可办理正式资源选择／精确接收' if not issues else '；'.join(dict.fromkeys(issues)))
    return q

def _candidate_valid(operation,center,capability):
    today=_today();order=operation.work_order;process=operation.operation
    return bool(center and center.workshop and capability and _effective(center,today) and _effective(capability,today)
        and center.company_id==center.workshop.company_id==order.company_id
        and center.workshop.is_active and capability.work_center_id==center.pk and capability.operation_id==operation.operation_id
        and process.company_id in (None,order.company_id) and _effective(process,today)
        and process.workshop_id in (None,center.workshop_id)
        and (center.department_id is None or center.department.company_id==order.company_id)
        and (center.workshop.department_id is None or center.workshop.department.company_id==order.company_id)
        and (center.department_id is None or center.workshop.department_id is None or center.department_id==center.workshop.department_id)
        and all(step and step.is_active and step.work_center_id in (None,center.pk)
            and step.workshop_id in (None,center.workshop_id) for step in (operation.root_step,operation.effective_step)))

def _candidate_snapshot(operation,center,capability,version,allocation):
    return {**_base_snapshot(operation),'currentResource':resource_snapshot(operation,center),
        'capability':{'id':capability.pk,'workCenterId':capability.work_center_id,'operationId':capability.operation_id,
            'assignmentRole':capability.assignment_role,'capabilityCode':capability.capability_code,
            'parameters':deepcopy(capability.capability_parameters),'isActive':capability.is_active,
            'effectiveFrom':str(capability.effective_from) if capability.effective_from else None,
            'effectiveTo':str(capability.effective_to) if capability.effective_to else None},
        'currentVersionFacts':deepcopy(version),'currentAllocationAdmission':deepcopy(allocation)}

def selection_history(operation):return _proof_history(operation,SELECT_OBJECT)

def precise_receipt_history(operation):return _proof_history(operation,RECEIVE_OBJECT)

def selection_authority(operation):
    history=selection_history(operation)
    if operation.work_center_id is not None:
        if history:_history_error()
        center=operation.work_center
        snapshot={**_base_snapshot(operation),'workCenterId':center.pk,'frozenWorkCenterSource':deepcopy(operation.source_snapshot)}
        return {'proofType':'FROZEN_ORDER_RESOURCE','projectionVersion':0,'version':0,
            'ref':f'ProductionWorkOrderOperation:{operation.pk}','proofHash':_hash(snapshot),'selectionHash':_hash(snapshot),
            'snapshot':snapshot,'workCenterId':center.pk,'workCenterName':center.name,'workshopId':center.workshop_id,
            'workshopName':center.workshop.name if center.workshop else None,'statusLabel':'原工单已冻结执行资源'},center,None
    if not history:return None,None,None
    proof=history[0];snapshot=proof['snapshot'];resource=snapshot.get('currentResource')
    if (not isinstance(resource,dict) or not isinstance(resource.get('workCenter'),dict)
            or not isinstance(snapshot.get('capability'),dict)
            or snapshot.get('currentVersionFacts',{}).get('ready') is not True
            or snapshot.get('currentAllocationAdmission',{}).get('ready') is not True):_history_error()
    center=WorkCenter.objects.select_related('workshop','department').filter(pk=resource['workCenter']['id'],company_id=operation.work_order.company_id).first()
    fact={**proof,'selectionHash':proof['proofHash'],'workCenterId':resource['workCenter']['id'],
        'workCenterName':snapshot.get('workCenterName'),'workshopId':resource['workshop']['id'],
        'workshopName':snapshot.get('workshopName')}
    return fact,center,proof

def _create_anchor(actor,operation,center,selection,q,payload):
    order=operation.work_order
    old=Receipt.objects.filter(work_order=order,workshop_id=center.workshop_id).first()
    if old:
        receipts._receipt(old)
        return old,False
    source={'receiptKind':ANCHOR_KIND,'contractVersion':CONTRACT,'companyId':order.company_id,
        'productionPlanId':order.production_plan_id,'workOrderId':order.pk,'workOrderNo':order.no,
        'workOrderVersion':order.version,'workOrderSnapshotHash':order.snapshot_hash,
        'quantity':str(order.quantity),'uomId':order.uom_id,'uomCode':order.source_snapshot.get('uomCode'),
        'uomLabel':order.source_snapshot.get('uomLabel'),'workshopId':center.workshop_id,
        'workshopName':center.workshop.name,'workshopCode':center.workshop.code,
        'workshopDepartmentId':center.workshop.department_id,'operations':[],
        'firstPreciseOperationId':operation.pk,'firstSelectionHash':selection['proofHash']}
    key='OPERATION-ANCHOR:'+sha256((str(operation.pk)+':'+payload['idempotencyKey']).encode()).hexdigest()
    anchor=create_business_object_with_initial_state(model=Receipt,initial_state='received',company_id=actor.company_id,
        work_order=order,workshop_id=center.workshop_id,work_order_version=order.version,work_order_snapshot_hash=order.snapshot_hash,
        source_snapshot=source,snapshot_hash=_hash(source),qualification_snapshot=deepcopy(q),qualification_hash=_hash(q),
        idempotency_key=key,request_hash=_hash({'anchor':source,'actorId':actor.pk,'key':key}),received_by=actor)
    audit=receipts._audit(actor,order,anchor,q,payload['reason'].strip())
    from .work_order_workshop_receipt_contract import OBJECT as ANCHOR_OBJECT
    record_projected_business_transition(object_type=ANCHOR_OBJECT,object_id=anchor.pk,source_state='',target_state='received',
        action_code=REQUIRED_PERMISSION,operator=actor,reason=payload['reason'].strip(),
        audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','received')})
    receipts._legacy_receipt(anchor)
    return anchor,True

def _row(operation,actor,work_center_id=None,context=None):
    register_actions()
    if context is None:_verify(operation.work_order)
    selection,center,persistent=selection_authority(operation)
    precise_values=precise_receipt_history(operation);precise=precise_values[0] if precise_values else None
    from .operation_execution_mode import resolve_operation_execution_mode
    mode=resolve_operation_execution_mode(operation,actor=actor)
    task=Task.objects.filter(source_operation_id=operation.pk).first()
    candidates=[]
    for capability in WorkCenterOperationCapability.objects.filter(operation_id=operation.operation_id,is_active=True,
            work_center__company_id=actor.company_id).select_related('work_center__workshop','work_center__department').order_by('work_center_id'):
        candidate=capability.work_center
        if not _candidate_valid(operation,candidate,capability) or not receipts._readable(actor,candidate.workshop,operation.work_order):continue
        q=_current_qualification(actor,operation,candidate,SELECT_ACTION,source_ok=mode['ready'])
        snapshot=_candidate_snapshot(operation,candidate,capability,q.get('currentVersionFacts'),q.get('currentAllocationAdmission'))
        candidates.append({'id':candidate.pk,'name':candidate.name,'code':candidate.code,'workCenterId':candidate.pk,
            'workshopId':candidate.workshop_id,'workshopName':candidate.workshop.name,
            'capabilityId':capability.pk,'assignmentRole':capability.assignment_role,
            'candidateSnapshotHash':_hash(snapshot),'qualification':q,'enabled':q['ready'],'blockingReasons':q['missingItems']})
    preview=next((candidate for candidate in candidates if candidate['id']==work_center_id),None)
    selected_center=WorkCenter.objects.select_related('workshop','department').filter(pk=work_center_id,company_id=actor.company_id).first() if preview else None
    select_extra=[]
    if operation.work_center_id is not None:select_extra.append('原工单已有冻结执行资源，不属于首次资源选择；变更须走正式归属承接。')
    if persistent:select_extra.append('已有正式资源选择证明，不重复选择；归属变化须另行承接。')
    if task:select_extra.append('本工序已有冻结任务，未开放任务资源迁移，不能重新选择或伪装首次选择。')
    if not mode['ready']:select_extra.extend(mode['blockingReasons'])
    sq=_current_qualification(actor,operation,selected_center or (center if selection else None),SELECT_ACTION,
        source_ok=mode['ready'],extra=select_extra)
    from .operation_resource_source import read_operation_resource
    context=context if context is not None else read_operation_resource(operation,actor=actor)
    old_member=context['originalMembership']
    receive_extra=[]
    if not selection or not center:receive_extra.append('尚无本工序的正式资源选择依据，不能精确接收。')
    if old_member:receive_extra.append('原冻结接收已准确包含本工序，无需重复精确接收。')
    if precise:receive_extra.append('本工序已有正式精确接收证明，不重复接收。')
    if task and not precise:receive_extra.append('已有任务尚无本次精确接收证明，不以新接收迁移旧任务。')
    if not mode['ready']:receive_extra.extend(mode['blockingReasons'])
    capability=WorkCenterOperationCapability.objects.filter(work_center=center,operation_id=operation.operation_id,is_active=True).first() if center else None
    resource_ok=bool(center and _candidate_valid(operation,center,capability))
    if selection and not resource_ok:receive_extra.append('已选择资源的当前能力、车间或正式来源不一致，请先办理合法维护／承接。')
    rq=_current_qualification(actor,operation,center,RECEIVE_ACTION,source_ok=bool(mode['ready'] and resource_ok),extra=receive_extra)
    current_hash=_hash(resource_snapshot(operation,center)) if center else None
    selection_label=selection['statusLabel'] if selection else '尚未正式选择执行资源'
    receipt_label='已精确接收' if precise else '原冻结接收已覆盖本工序' if old_member else '尚无本工序精确接收证明'
    select_action={**action_contract('selectResource',operation.pk),'displayName':'已选择资源' if selection else '正式选择执行资源',
        'enabled':sq['ready'],'disabledReason':'' if sq['ready'] else sq['statusLabel']}
    receive_action={**action_contract('receiveOperation',operation.pk),'displayName':'已精确接收' if precise else '确认本工序精确接收',
        'enabled':rq['ready'],'disabledReason':'' if rq['ready'] else rq['statusLabel']}
    return {'id':operation.pk,'operationId':operation.pk,'workOrderId':operation.work_order_id,'workOrderNo':operation.work_order.no,
        'operationName':operation.operation.name,'formalProcessId':operation.operation_id,'sequence':operation.sequence,
        'workOrderVersion':operation.work_order.version,'workOrderSnapshotHash':operation.work_order.snapshot_hash,
        'operationSnapshotHash':operation.snapshot_hash,'frozenWorkCenterId':operation.work_center_id,
        'candidateWorkCenters':candidates,'selectedCandidateWorkCenterId':work_center_id,'selectedCandidateSnapshotHash':preview['candidateSnapshotHash'] if preview else None,
        'selectionFact':deepcopy(selection),'resourceSelectionProof':persistent,'preciseReceiptProof':precise,
        'selectionVersion':persistent['projectionVersion'] if persistent else 0,'receiptVersion':precise['projectionVersion'] if precise else 0,
        'currentResourceHash':current_hash,'selectionStatusLabel':selection_label,'receiptStatusLabel':receipt_label,
        'sourceBasisLabel':'原工单冻结来源；正式资源选择与精确接收另有独立证明，旧接收不改写',
        'statusCode':operation.work_order.status,'statusLabel':receipt_label+'；'+selection_label,
        'sourceReady':bool(context['facts']['sourceReady'] and mode['ready']),
        'currentResourceFacts':context['facts'],'currentAllocationAdmission':context['facts']['currentAllocationAdmission'],
        'blockingReasons':list(dict.fromkeys(context['facts']['blockingReasons']+mode['blockingReasons'])),
        'qualification':sq if work_center_id is not None else rq,'selectQualification':sq,'receiveQualification':rq,
        'availableActions':{'selectResource':select_action,'receiveOperation':receive_action},
        'existingTaskId':task.pk if task else None,'taskMigrationSupported':False,'executionModeFacts':mode,
        'originalMembershipProven':bool(old_member),'originalMembershipNotExtended':True}

def _readback_result(actor, operation, row, query):
    """Verify only the named action/intent; absence is always inconclusive."""
    if query is None:
        return None
    fields={'actionCode','selectionVersion','receiptVersion','requestHash','requestKeyHash'}
    if (not isinstance(query,dict) or set(query)!=fields or operation is None
            or query.get('actionCode') not in (SELECT_ACTION,RECEIVE_ACTION)
            or any(type(query.get(key)) is not int or query[key]<0 for key in ('selectionVersion','receiptVersion'))
            or any(not isinstance(query.get(key),str) or not re.fullmatch('[0-9a-f]{64}',query[key])
                for key in ('requestHash','requestKeyHash'))):
        _fail('OPERATION_RESOURCE_READBACK_QUERY_INVALID','只读核查须完整引用原动作、准确工序、选择／接收版本及原请求标识。',400)
    select=query['actionCode']==SELECT_ACTION
    proof=row['resourceSelectionProof' if select else 'preciseReceiptProof']
    snapshot=proof['snapshot'] if proof else {}
    # _proof_history already validated the committed ledger and original
    # payload. Reconstruct its version reference without publishing raw keys.
    kind=SELECT_OBJECT if select else RECEIVE_OBJECT
    ledger=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=query['actionCode'],
        entity_type=kind,target_entity_id=str(operation.pk),request_hash=query['requestHash'],
        status='COMMITTED').first()
    intent_matches=bool(ledger and proof and proof['actorId']==actor.pk
        and ledger.audit_metadata=={'actorId':actor.pk,'contractVersion':CONTRACT}
        and proof['requestHash']==query['requestHash'] and proof['requestKeyHash']==query['requestKeyHash']
        and sha256(ledger.idempotency_key.encode()).hexdigest()==query['requestKeyHash'])
    if select:
        intent_matches=bool(intent_matches and query['selectionVersion']==0 and query['receiptVersion']==0
            and proof['projectionVersion']==query['selectionVersion']+1)
    else:
        intent_matches=bool(intent_matches and snapshot.get('selectionVersion')==query['selectionVersion']
            and snapshot.get('selectionHash')==row['selectionFact']['proofHash']
            and proof['projectionVersion']==query['receiptVersion']+1 and query['receiptVersion']==0)
    return {**deepcopy(query),'operationId':operation.pk,'workOrderId':operation.work_order_id,'actorId':actor.pk,
        'status':'verified' if intent_matches else 'unknown',
        'statusLabel':'本次正式资源选择已按原请求核实' if intent_matches and select else
            '本次精确接收已按原请求核实' if intent_matches else '本次原请求结果仍未知，请继续只读核查，不重复提交',
        'proofRef':proof['ref'] if intent_matches else None,'proofHash':proof['proofHash'] if intent_matches else None,
        'auditReference':proof['auditReference'] if intent_matches else None,'businessWriteCount':0,'auditWriteCount':0}

def _read_operation_resources(*,user,work_order_id=None,operation_id=None,work_center_id=None,readback_query=None,response_mode=None,locate_latest_own_action=False):
    from .workshop_reception_read_projection import response_mode as parse_mode,SELECTED_DETAIL,operation_directory_row
    from .workshop_reception_read_projection import (validate_locator_request,latest_own_action_candidate,
        verified_view_location,view_location_fields)
    response_mode=parse_mode(response_mode)
    validate_locator_request(locate_latest_own_action,response_mode)
    if readback_query is not None and locate_latest_own_action:
        _fail('OPERATION_RESOURCE_READBACK_QUERY_INVALID','待核实的原请求仅按准确工序只读核查，不使用最近办理定位。',400)
    register_actions();actor,scope=receipts._actor(user)
    if readback_query is not None and (work_order_id is None or operation_id is None):
        _fail('OPERATION_RESOURCE_READBACK_QUERY_INVALID','原请求只读核查须同时指定正式工单和准确工序。',400)
    for value in (work_order_id,operation_id,work_center_id):
        if value is not None and (type(value) is not int or value<=0):_fail('OPERATION_RESOURCE_QUERY_INVALID','工单、工序或所选工作中心身份须为正整数。',400)
    orders=receipts._rows(actor,scope)
    if operation_id is not None and work_order_id is None:
        work_order_id=Operation.objects.filter(pk=operation_id,work_order_id__in=orders.values_list('pk',flat=True)).values_list('work_order_id',flat=True).first()
        if work_order_id is None:_fail('OPERATION_RESOURCE_NOT_VISIBLE','未找到本公司正式工单工序。',403)
    options=[];selected_order=None
    for order in orders:
        readable=receipts._whole_readable(actor,order)
        if not readable:
            shops=Workshop.objects.filter(pk__in=WorkCenterOperationCapability.objects.filter(
                operation_id__in=order.operations.values_list('operation_id',flat=True),is_active=True,
                work_center__company_id=actor.company_id).values_list('work_center__workshop_id',flat=True),is_active=True)
            readable=any(receipts._readable(actor,shop,order) for shop in shops)
        if readable:
            options.append({'workOrderId':order.pk,'workOrderNo':order.no,'productionPlanId':order.production_plan_id})
            if order.pk==work_order_id:selected_order=order
    if work_order_id is not None and selected_order is None:_fail('OPERATION_RESOURCE_NOT_VISIBLE','当前账号不能查看此公司及工单的执行资源。',403)
    rows=[];directory=[];contexts=[];visible_contexts=[];candidate=None;suggestion=None
    location_requested=bool(locate_latest_own_action and operation_id is None)
    if selected_order:
        from .operation_resource_source import read_order_resources
        contexts=([(operation,None) for operation in _verify(selected_order)[0]]
            if response_mode==SELECTED_DETAIL else read_order_resources(selected_order,actor=actor))
        whole_readable=receipts._whole_readable(actor,selected_order)
        for operation,context in contexts:
            if not whole_readable:
                shop_ids=WorkCenterOperationCapability.objects.filter(operation_id=operation.operation_id,is_active=True,
                    work_center__company_id=actor.company_id).values_list('work_center__workshop_id',flat=True)
                if not any(receipts._readable(actor,shop,selected_order) for shop in Workshop.objects.filter(pk__in=shop_ids,is_active=True)):continue
            directory.append(operation_directory_row(operation))
            visible_contexts.append((operation,context))
        if location_requested:
            candidate=latest_own_action_candidate(actor,[operation for operation,context in visible_contexts])
            if candidate:operation_id=candidate[0].pk
        for operation,context in visible_contexts:
            if response_mode!=SELECTED_DETAIL or operation.pk==operation_id:
                rows.append(_row(operation,actor,work_center_id if operation.pk==operation_id else None,context=context))
    selected=next((row for row in rows if row['operationId']==operation_id),None)
    if operation_id is not None and selected is None:_fail('OPERATION_RESOURCE_NOT_VISIBLE','所选工序不属于当前正式可见范围。',403)
    if candidate:
        suggestion=verified_view_location(actor,candidate,selected['currentResourceFacts'])
    readback_operation=next((operation for operation,context in contexts if operation.pk==operation_id),None) if selected_order else None
    readback=_readback_result(actor,readback_operation,selected,readback_query)
    empty={'ready':False,'missingItems':['请选择正式工单工序及明确的执行资源。'],'statusLabel':'请选择正式工单工序及执行资源',
        'currentActorEvidence':receipts._employees(actor)[4]}
    return {'contractVersion':CONTRACT,'moduleCode':MODULE,'companyId':actor.company_id,'currentStateSource':'server','factSource':'server',
        **view_location_fields(location_requested,suggestion),
        'responseMode':response_mode,'operationOptions':directory if response_mode==SELECTED_DETAIL else None,
        'directoryResultCount':len(directory),'detailResultCount':len(rows),
        'currentActorEvidence':receipts._employees(actor)[4],'workOrderId':work_order_id,'workOrderOptions':options,'operations':rows,
        'selectedOperation':selected,'readbackResult':readback,'qualification':selected['qualification'] if selected else empty,
        'availableActions':selected['availableActions'] if selected else {key:{**action_contract(key),'enabled':False,
            'disabledReason':empty['statusLabel']} for key in ('selectResource','receiveOperation')},
        'statusLabel':('工序目录已读取，请选择工序读取当前资源、接收及资格事实' if selected_order else
            '请选择已下达工单；工序目录及详情尚未读取') if response_mode==SELECTED_DETAIL and selected is None else
            '正式资源选择与逐工序接收事实已读取','businessWriteCount':0,'auditWriteCount':0}

def read_operation_resources(*,user,work_order_id=None,operation_id=None,work_center_id=None,readback_query=None,response_mode=None,locate_latest_own_action=False):
    from pde.operation_allocation_source_handoff_service import allocation_admission_context
    with allocation_admission_context(user=user):
        return _read_operation_resources(user=user,work_order_id=work_order_id,operation_id=operation_id,work_center_id=work_center_id,
            readback_query=readback_query,response_mode=response_mode,locate_latest_own_action=locate_latest_own_action)

def _writes(created,anchor=False):
    return {'businessWriteCount':int(created)+int(anchor),'auditWriteCount':int(created)+int(anchor),
        'stateTransitionWriteCount':int(created)+int(anchor),'resourceSelectionCreatedCount':0,
        'preciseOperationReceiptCreatedCount':0,'receiptAnchorCreatedCount':int(anchor),
        'originalReceiptUpdatedCount':0,'workOrderUpdatedCount':0,'operationSourceUpdatedCount':0,
        'taskUpdatedCount':0,'actualStartCount':0,'actualReportCount':0,'completionCreatedCount':0,
        'masterDataUpdatedCount':0,'inventoryUpdatedCount':0,'scheduleUpdatedCount':0,'resourceOccupancyReleasedCount':0}

def _perform(*,user,operation_id,payload,select):
    _payload(payload,select);register_actions();actor,scope=receipts._actor(user)
    kind,action=(SELECT_OBJECT,SELECT_ACTION) if select else (RECEIVE_OBJECT,RECEIVE_ACTION)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            operation=Operation.objects.select_related('work_order__production_plan','operation','work_center__workshop',
                'root_step','effective_step').select_for_update().filter(pk=operation_id,
                    work_order_id__in=receipts._rows(actor,scope).values_list('pk',flat=True)).first()
            if operation is None:_fail('OPERATION_RESOURCE_NOT_VISIBLE','未找到当前公司及正式责任范围内的工单工序。',403)
            _verify(operation.work_order)
            row=_row(operation,actor,payload.get('workCenterId') if select else None)
            q=row['selectQualification'] if select else row['receiveQualification']
            proof=row['resourceSelectionProof'] if select else row['preciseReceiptProof']
            request_hash=_intent_hash(actor.pk,action,operation.pk,payload)
            old=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=action,
                idempotency_key=payload['idempotencyKey']).first()
            if old:
                # Exact intent may be re-read after a normal completed action;
                # do not treat the completion-only reason as a new denial.
                if (not proof or old.entity_type!=kind or old.target_entity_id!=str(operation.pk) or old.status!='COMMITTED'
                        or old.request_hash!=request_hash or proof['requestHash']!=request_hash or proof['actorId']!=actor.pk):
                    _fail('OPERATION_RESOURCE_IDEMPOTENCY_CONFLICT','该标识已绑定其他资源、来源、人员或接收意图。')
                selection,center,_=selection_authority(operation)
                current=_current_qualification(actor,operation,center,action,source_ok=True)
                if not current['ready']:_fail('OPERATION_RESOURCE_NOT_READY',current['statusLabel'],403)
                return read_operation_resources(user=actor,work_order_id=operation.work_order_id,operation_id=operation.pk),_writes(False)
            if proof:_fail('OPERATION_RESOURCE_ALREADY_RECORDED','本工序已有对应正式证明，不重复创建；请只读回查。')
            expected={'expectedWorkOrderVersion':operation.work_order.version,'expectedWorkOrderSnapshotHash':operation.work_order.snapshot_hash,
                'expectedOperationSnapshotHash':operation.snapshot_hash,'expectedSelectionVersion':row['selectionVersion']}
            if select:expected['expectedCandidateSnapshotHash']=row['selectedCandidateSnapshotHash']
            else:expected.update(expectedSelectionHash=row['selectionFact']['proofHash'] if row['selectionFact'] else None,
                expectedCurrentResourceHash=row['currentResourceHash'],expectedReceiptVersion=row['receiptVersion'])
            if any(payload[key]!=value for key,value in expected.items()):_fail('OPERATION_RESOURCE_SOURCE_CHANGED','工单、工序、候选资源、选择或接收版本已变化，请只读重新读取。')
            if not q['ready']:_fail('OPERATION_RESOURCE_NOT_READY',q['statusLabel'],403)
            if select:
                candidate=next(candidate for candidate in row['candidateWorkCenters'] if candidate['id']==payload['workCenterId'])
                center=WorkCenter.objects.select_related('workshop','department').get(pk=payload['workCenterId'],company_id=actor.company_id)
                capability=WorkCenterOperationCapability.objects.get(pk=candidate['capabilityId'])
                snapshot=_candidate_snapshot(operation,center,capability,q['currentVersionFacts'],q['currentAllocationAdmission'])
                if _hash(snapshot)!=payload['expectedCandidateSnapshotHash']:
                    _fail('OPERATION_RESOURCE_SOURCE_CHANGED','候选能力、工程来源或资源归属在保存前已变化，请只读重新读取。')
                snapshot.update(workCenterName=center.name,workshopName=center.workshop.name,
                    candidateSnapshotHash=payload['expectedCandidateSnapshotHash'])
                _store_proof(actor,operation,kind,snapshot,q,payload);anchor_created=False
            else:
                selection,center,_=selection_authority(operation)
                anchor,anchor_created=_create_anchor(actor,operation,center,selection,q,payload)
                current_resource=resource_snapshot(operation,center)
                if _hash(current_resource)!=payload['expectedCurrentResourceHash']:
                    _fail('OPERATION_RESOURCE_SOURCE_CHANGED','正式选择的资源在精确接收保存前已变化，请只读重新读取。')
                snapshot={**_base_snapshot(operation),'selection':deepcopy(selection),'selectionHash':selection['proofHash'],
                    'selectionVersion':row['selectionVersion'],'currentResource':current_resource,
                    'currentResourceHash':row['currentResourceHash'],'receiptAnchorId':anchor.pk,'receiptAnchorHash':anchor.snapshot_hash,
                    'receiptAnchorIsOriginalMembership':False,'currentVersionFacts':deepcopy(q['currentVersionFacts']),
                    'currentAllocationAdmission':deepcopy(q['currentAllocationAdmission'])}
                _store_proof(actor,operation,kind,snapshot,q,payload)
                receipts._receipt(anchor)
            writes=_writes(True,anchor_created)
            writes['resourceSelectionCreatedCount' if select else 'preciseOperationReceiptCreatedCount']=1
            return read_operation_resources(user=actor,work_order_id=operation.work_order_id,operation_id=operation.pk),writes
    except IntegrityError:_fail('OPERATION_RESOURCE_CONCURRENT_CONFLICT','资源或接收存在并发正式意图，请只读回查，不自动重试。')

def select_operation_resource(*,user,operation_id,payload):return _perform(user=user,operation_id=operation_id,payload=payload,select=True)

def receive_operation(*,user,operation_id,payload):return _perform(user=user,operation_id=operation_id,payload=payload,select=False)


# Native formal continuation: individually restored symbols; existing proofs preserved.
def validate_precise_receipt(operation,selection,proof):
    """Independent frozen selection/anchor/projection linkage, no today grants."""
    snapshot=proof['snapshot'];frozen=snapshot.get('selection')
    if (not selection or not isinstance(frozen,dict) or frozen.get('proofHash')!=selection['proofHash']
            or frozen.get('ref')!=selection['ref'] or snapshot.get('selectionHash')!=selection['proofHash']
            or snapshot.get('selectionVersion')!=selection['projectionVersion']
            or snapshot.get('currentResource',{}).get('workCenter',{}).get('id')!=selection['workCenterId']):_history_error()
    anchor=Receipt.objects.select_related('work_order','workshop').filter(pk=snapshot.get('receiptAnchorId'),
        company_id=operation.work_order.company_id,work_order_id=operation.work_order_id).first()
    if (not anchor or snapshot.get('receiptAnchorHash')!=anchor.snapshot_hash
            or anchor.workshop_id!=snapshot['currentResource']['workshop']['id']):_history_error()
    receipts._legacy_receipt(anchor)
    return anchor,proof

def is_precise_anchor(row):return bool(row and isinstance(row.source_snapshot,dict) and row.source_snapshot.get('receiptKind')==ANCHOR_KIND)

def _group_supplement(row):
    values=_proof_history(row,SUPPLEMENT_OBJECT)
    return values[0] if values else None

def precise_anchor_projection(row,legacy_fact):
    """The row anchors identities; it never claims its empty group was received."""
    source=row.source_snapshot
    if source.get('operations')!=[] or type(source.get('firstPreciseOperationId')) is not int:_history_error()
    operation=Operation.objects.select_related('work_order').filter(pk=source['firstPreciseOperationId'],work_order_id=row.work_order_id).first()
    history=precise_receipt_history(operation) if operation else []
    proof=history[0] if history else None
    if (not proof or proof['snapshot'].get('receiptAnchorId')!=row.pk
            or proof['snapshot'].get('receiptAnchorHash')!=row.snapshot_hash):_history_error()
    supplement=_group_supplement(row)
    result=deepcopy(legacy_fact)
    result.update(received=bool(supplement),receiptScopeKind=ANCHOR_KIND,originalFrozenGroupReceived=bool(supplement),
        statusLabel='原冻结车间组已补充接收' if supplement else '仅有逐工序精确接收；原冻结车间组尚未接收',
        scopeSnapshotHash=supplement['snapshot']['groupSnapshotHash'] if supplement else None,
        groupSupplement=deepcopy(supplement),anchorSnapshotHash=row.snapshot_hash,
        firstPreciseReceiptRef=proof['ref'],firstPreciseReceiptHash=proof['proofHash'])
    zone=row.work_order.source_snapshot['sourceSchedule']['timezone']
    result['receivedAtLabel']=task_datetime_label(row.received_at,zone)
    return result

def original_group_source(row):
    """Read the actual frozen group scope, or no group when anchor-only."""
    if not is_precise_anchor(row):return row.source_snapshot,None
    supplement=_group_supplement(row)
    return (deepcopy(supplement['snapshot']['groupSnapshot']),supplement) if supplement else (None,None)

def supplement_original_group(actor,order,group,anchor,source,q,payload):
    """A later ordinary group receipt may complete an earlier precise anchor."""
    history=_proof_history(anchor,SUPPLEMENT_OBJECT)
    if history:
        proof=history[0]
        if proof['requestHash']!=_intent_hash(actor.pk,REQUIRED_PERMISSION,anchor.pk,payload):
            _fail('WORKSHOP_RECEIPT_ALREADY_RECEIVED','本车间原冻结组已有正式补充接收，请只读查看。')
        return False
    snapshot={'companyId':order.company_id,'workOrderId':order.pk,'workOrderVersion':order.version,
        'workOrderSnapshotHash':order.snapshot_hash,'receiptAnchorId':anchor.pk,'receiptAnchorHash':anchor.snapshot_hash,
        'groupSnapshot':deepcopy(source),'groupSnapshotHash':_hash(source)}
    _store_proof(actor,anchor,SUPPLEMENT_OBJECT,snapshot,q,payload)
    receipts._receipt(anchor)
    return True
