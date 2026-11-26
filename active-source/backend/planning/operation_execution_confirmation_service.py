"""One immutable actual-passage proof over a nonquantified Task and real Start.

The existing shared projection/audit/identity facilities persist this proof;
there is no quantity report and no automatic completion or downstream action.
"""
from copy import deepcopy
from hashlib import sha256
import re
from django.db import IntegrityError, transaction
from django.conf import settings
from django.utils import timezone
from masterdata.models import MasterDataWriteRequest, ExternalIdentity
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition, ProcessDefinition
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.state_transitions import record_projected_business_transition
from .mes_test_source_bridge import record_audit
from .mes_test_source_bridge import _hash, _fail
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_start_models import ProductionOperationStart as Start
from .operation_report_models import ProductionOperationReport as Report
from .workshop_task_time import task_datetime_label
from . import mes_test_source_bridge as formal
from . import mes_test_source_bridge as receipt
from . import mes_test_source_bridge as starts
from .operation_execution_confirmation_contract import (CONTRACT,OBJECT,ACTION,REQUIRED_PERMISSION,
    MODULE,PROCESS,WORKFLOW_NODE,RESPONSIBILITY,action_contract,register_action)

EXPECTED=('expectedVersion','expectedSourceSnapshotHash','expectedAssignmentHash','expectedStartId',
    'expectedStartSnapshotHash','expectedExecutionVersion')

def _payload(payload):
    if not isinstance(payload,dict) or set(payload)!=set(EXPECTED)|{'reason','idempotencyKey'}:
        _fail('OPERATION_EXECUTION_PAYLOAD_INVALID','实际经过意图只接受任务、开工及经过版本、原因和防重复标识，不接受数量。',400)
    for key in ('expectedVersion','expectedStartId','expectedExecutionVersion'):
        if type(payload[key]) is not int or payload[key] < (0 if key=='expectedExecutionVersion' else 1):
            _fail('OPERATION_EXECUTION_EXPECTATION_INVALID','任务、开工或实际经过版本无效，请重新读取。',400)
    for key in ('expectedSourceSnapshotHash','expectedAssignmentHash','expectedStartSnapshotHash'):
        if not isinstance(payload[key],str) or not re.fullmatch('[a-f0-9]{64}',payload[key]):
            _fail('OPERATION_EXECUTION_EXPECTATION_INVALID','请完整引用本次读取的任务、执行人员和开工来源。',400)
    if not isinstance(payload['reason'],str) or not 2<=len(payload['reason'].strip())<=300:
        _fail('OPERATION_EXECUTION_REASON_REQUIRED','请填写2至300字的真实实际经过说明。',400)
    if not isinstance(payload['idempotencyKey'],str) or not 1<=len(payload['idempotencyKey'])<=120:
        _fail('OPERATION_EXECUTION_IDEMPOTENCY_REQUIRED','实际经过登记缺少有效防重复标识。',400)

def _intent(actor_id,task_id,payload):
    return _hash({'actorId':actor_id,'action':ACTION,'taskId':task_id,
        'payload':{**payload,'reason':payload['reason'].strip()}})

def _snapshot(task,start,mode):
    from .operation_report_service import _start_snapshot
    return {'companyId':task.company_id,'taskId':task.pk,'workOrderId':task.work_order_id,
        'sourceOperationId':task.source_operation_id,'taskVersion':task.version,
        'sourceSnapshotHash':task.source_snapshot_hash,'assignmentHash':task.assignment_hash,
        'startRecordId':start.pk,'startSnapshotHash':_hash(_start_snapshot(start)),
        'executionMode':'NON_QUANTIFIED_REQUIRED','modeSourceHash':mode['modeSourceHash'],
        'modeSourceProof':deepcopy(task.source_snapshot.get('modeSourceProof'))}

def _history(task,start):
    from .workshop_task_time import task_datetime_label
    from .operation_execution_mode import task_execution_mode
    events=list(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=task.pk).order_by('version','pk'))
    ledgers=list(MasterDataWriteRequest.objects.filter(organization_id=task.company_id,entity_type=OBJECT,
        target_entity_id=str(task.pk),action_code=ACTION).select_related('source_identity'))
    if not events:
        if ledgers:_fail('OPERATION_EXECUTION_HISTORY_UNPROVEN','实际经过账本缺少对应正式证明。')
        return None
    if len(events)!=1 or len(ledgers)!=1:
        _fail('OPERATION_EXECUTION_HISTORY_UNPROVEN','实际经过必须是本任务唯一已提交证明。')
    event,ledger=events[0],ledgers[0]
    match=re.fullmatch('OrganizationOperatingAuditRecord:([1-9][0-9]*)',event.audit_reference or '')
    audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
    before=audit.before_snapshot if audit and isinstance(audit.before_snapshot,dict) else {}
    after=audit.after_snapshot if audit and isinstance(audit.after_snapshot,dict) else {}
    state=after.get('state');q=state.get('qualification') if isinstance(state,dict) else None
    identity=ledger.source_identity
    if (not isinstance(state,dict) or not isinstance(q,dict)
            or any(not isinstance(q.get(k),dict) for k in ('currentActorEvidence','sourceFacts','authorization'))
            or not isinstance(q['sourceFacts'].get('currentSourceChecks'),dict)
            or not isinstance(q['authorization'].get('permissionCodes'),list)):
        _fail('OPERATION_EXECUTION_HISTORY_UNPROVEN','实际经过冻结证明或责任结构损坏。')
    mode=task_execution_mode(task,verify_current=False)
    snapshot=_snapshot(task,start,mode)
    actor=q['currentActorEvidence'];node=after.get('workflowNode');auth=after.get('authorization')
    process=ProcessDefinition.objects.filter(definition_code=PROCESS,active=True,business_domain='MES').first()
    live_node=process.nodes.filter(node_code=WORKFLOW_NODE,business_action_code=REQUIRED_PERMISSION,active=True).first() if process else None
    payload=state.get('intentPayload')
    if not isinstance(payload,dict):_fail('OPERATION_EXECUTION_HISTORY_UNPROVEN','实际经过缺少完整冻结意图。')
    payload={**payload,'idempotencyKey':ledger.idempotency_key};_payload(payload)
    expected={'expectedVersion':task.version,'expectedSourceSnapshotHash':task.source_snapshot_hash,
        'expectedAssignmentHash':task.assignment_hash,'expectedStartId':start.pk,
        'expectedStartSnapshotHash':snapshot['startSnapshotHash'],'expectedExecutionVersion':0}
    if (event.version!=1 or event.source_state!='' or event.target_state!='confirmed' or event.action_code!=ACTION
            or event.workflow_instance_id is not None or not audit or audit.target_type!=OBJECT or audit.target_id!=task.pk
            or audit.organization_id!=task.company_id or audit.actor_id!=event.operator_id or audit.action_code!=ACTION
            or audit.reason!=event.reason or before.get('state')!={'status':''}
            or state.get('status')!='confirmed' or state.get('contractVersion')!=CONTRACT
            or state.get('snapshot')!=snapshot or state.get('proofHash')!=_hash(snapshot)
            or state.get('confirmedById')!=start.started_by_id or event.operator_id!=start.started_by_id
            or actor.get('userId')!=event.operator_id or actor.get('companyId')!=task.company_id
            or actor.get('employeeId')!=task.execution_employee_id or actor.get('positionId')!=task.execution_position_id
            or actor.get('workshopId')!=task.workshop_id or q.get('ready') is not True
            or actor.get('uniqueEmployeeAccountLink') is not True or actor.get('currentEmploymentValid') is not True
            or q.get('selfTaskOnly') is not True or q.get('actualStarterSelfOnly') is not True
            or q.get('executionMode')!='NON_QUANTIFIED_REQUIRED' or q.get('modeSourceHash')!=mode['modeSourceHash']
            or q['sourceFacts'].get('ready') is not True or q['sourceFacts'].get('snapshotHash')!=task.source_snapshot_hash
            or q['sourceFacts'].get('receiptValid') is not True or q['sourceFacts']['currentSourceChecks'].get('ready') is not True
            or q['authorization'].get('allowed') is not True or REQUIRED_PERMISSION not in q['authorization']['permissionCodes']
            or not isinstance(auth,dict) or not isinstance(auth.get('permissionCodes'),list)
            or auth.get('allowed') is not True or REQUIRED_PERMISSION not in auth['permissionCodes']
            or not isinstance(node,dict) or node.get('processCode')!=PROCESS or node.get('nodeCode')!=WORKFLOW_NODE
            or node.get('authorityActionCode')!=REQUIRED_PERMISSION or node.get('responsibilityCode')!=RESPONSIBILITY
            or node.get('processId')!=q.get('definitionId') or node.get('nodeId')!=q.get('nodeId')
            or not process or not live_node or q.get('definitionId')!=process.pk or q.get('nodeId')!=live_node.pk
            or before.get('workflowNode')!=node or ledger.status!='COMMITTED'
            or not isinstance(ledger.audit_metadata,dict) or ledger.audit_metadata!={'actorId':event.operator_id,'contractVersion':CONTRACT}
            or any(payload.get(k)!=v for k,v in expected.items()) or payload['reason'].strip()!=event.reason
            or ledger.request_hash!=_intent(event.operator_id,task.pk,payload)
            or state.get('requestHash')!=ledger.request_hash or state.get('requestKeyHash')!=sha256(ledger.idempotency_key.encode()).hexdigest()
            or not identity or identity.organization_id!=task.company_id or identity.source_system!='MES_OPERATION_EXECUTION'
            or identity.source_type!='INTERNAL' or identity.source_object_type!=ACTION
            or identity.external_id!=state['requestKeyHash'] or identity.target_entity_type!=OBJECT
            or identity.target_entity_id!=str(task.pk) or identity.mapping_status!='MATCH'
            or identity.source_fingerprint!=ledger.request_hash
            or identity.audit_metadata!={'contractVersion':CONTRACT,'quantityApplicable':False}
            or ledger.result!={'taskId':task.pk,'startRecordId':start.pk,'transitionId':event.pk,'proofHash':state['proofHash']}):
        _fail('OPERATION_EXECUTION_HISTORY_UNPROVEN','实际经过的任务、开工、模式、本人资格、审计或防重复证明不一致。')
    if not isinstance(state.get('confirmedAt'),str) or not state['confirmedAt']:
        _fail('OPERATION_EXECUTION_HISTORY_UNPROVEN','实际经过缺少正式服务端登记时间。')
    zone=task.work_order.source_snapshot['sourceSchedule']['timezone']
    from datetime import datetime
    try:at=datetime.fromisoformat(state['confirmedAt'])
    except ValueError:_fail('OPERATION_EXECUTION_HISTORY_UNPROVEN','实际经过服务端时间格式损坏。')
    # Match the existing Task datetime contract: a Django-local naive value is
    # in the configured default zone, never the scheduling service's UTC-naive.
    def instant(value):
        return timezone.make_aware(value,timezone.get_default_timezone()) if timezone.is_naive(value) else value
    if (state.get('timestampTimezone')!=timezone.get_default_timezone_name()
            or state.get('timestampBasis')!=('DJANGO_LOCAL_DATETIME' if timezone.is_naive(at) else 'AWARE_DATETIME')
            or not instant(start.started_at)<=instant(at)<=instant(audit.created_at)<=instant(event.timestamp)):
        _fail('OPERATION_EXECUTION_HISTORY_UNPROVEN','实际经过登记时间与正式开工、审计或转换时间不一致。')
    history=[{'id':event.pk,'sourceState':'','targetState':'confirmed','sourceStateLabel':'未登记实际经过',
        'targetStateLabel':'已登记实际经过','version':1,'operatorId':event.operator_id,'reason':event.reason,
        'actionCode':ACTION,'actionLabel':'登记实际经过','auditReference':event.audit_reference,
        'timestamp':event.timestamp.isoformat(),'timestampLabel':task_datetime_label(event.timestamp,zone)}]
    proof = {'id':event.pk,'ref':f'BusinessStateTransition:{event.pk}','proofType':'ACTUAL_EXECUTION_CONFIRMATION',
        'contractVersion':CONTRACT,'taskId':task.pk,'startRecordId':start.pk,'projectionVersion':1,
        **{k:snapshot[k] for k in ('sourceSnapshotHash','assignmentHash','startSnapshotHash','modeSourceHash')},
        'proofHash':state['proofHash'],'snapshot':snapshot,'confirmedById':event.operator_id,
        'confirmedByLabel':actor.get('employeeName') or actor.get('username'),'confirmedAt':state['confirmedAt'],
        'confirmedAtLabel':task_datetime_label(at,zone),'reason':event.reason,'auditReference':event.audit_reference,
        'timestampBasis':state['timestampBasis'],'timestampTimezone':state['timestampTimezone'],
        'requestKeyHash':state['requestKeyHash'],'requestHash':state['requestHash'],'statusCode':'confirmed',
        'statusLabel':'已登记实际经过','statusTransitionHistory':history,'statusTransitionCount':1,
        'stateMachineConsistent':True,'quantityApplicable':False,'completionProven':False}
    return _completion_frozen_labels(proof, task, at, event, zone)


def _completion_frozen_labels(proof, task, at, event, zone):
    """Old full completion proofs may freeze the former display labels.

    Reproduce only those two labels, and only when the entire execution proof
    equals the immutable completion copy. Native completion verification still
    checks its full snapshot, hash, actors, intent, audit and state chain.
    New ISO-labelled proofs keep their existing representation.
    """
    if task.work_order.usage_purpose != 'PRODUCTION_USE':
        return proof
    from .operation_completion_contract import OBJECT as COMPLETION_OBJECT
    from .mes_formal_source_admission import formal_datetime_label
    first = BusinessStateTransition.objects.filter(object_type=COMPLETION_OBJECT,
        object_id=task.pk).order_by('version','pk').first()
    match = re.fullmatch('OrganizationOperatingAuditRecord:([1-9][0-9]*)',
        first.audit_reference or '') if first else None
    audit = OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1]),
        target_type=COMPLETION_OBJECT, target_id=task.pk, organization_id=task.company_id).first() if match else None
    state = audit.after_snapshot.get('state', {}) if audit else {}
    frozen = state.get('sourceSnapshot')
    if not isinstance(frozen, dict) or state.get('sourceSnapshotHash') != _hash(frozen):
        return proof
    legacy = deepcopy(proof)
    legacy['confirmedAtLabel'] = formal_datetime_label(at, zone)
    legacy['statusTransitionHistory'][0]['timestampLabel'] = formal_datetime_label(event.timestamp, zone)
    return legacy if frozen.get('executionConfirmation') == legacy else proof


def qualification(actor,task,start,source,mode,proof):
    from . import operation_report_service as reports
    register_action()
    q=reports._qualification(actor,task,start,source,{'quantityStatusCode':'open','remainingBelowUnitPrecision':False})
    q.pop('quantityFacts',None)
    q.update(executionMode=mode['executionMode'],modeSourceHash=mode.get('modeSourceHash'),quantityApplicable=False)
    issues=q['missingItems'][:]
    if mode['executionMode']!='NON_QUANTIFIED_REQUIRED' or not mode['ready']:
        issues.extend(mode.get('blockingReasons') or ['本任务不是经正式证明的必经不可统计模式。'])
    if Report.objects.filter(task_id=task.pk).exists():issues.append('不可统计任务存在数量报工冲突，请核对正式记录。')
    decision=ActionPermissionValidator(fact_provider=reports._Facts(actor,task,'confirmed' if proof else 'unconfirmed')).evaluate(
        user=actor,module_code=MODULE,action_code=ACTION,object_ids=[task.pk],selection_count=1,
        requested_legal_entity_id=str(task.company_id))
    if not decision['granted'] and not proof:issues.append(decision.get('reason') or '实际经过登记动作权限未通过。')
    q.update(ready=not issues and not proof,admissionReady=not issues,missingItems=issues,
        statusLabel='已登记实际经过；可继续核对完工申请' if proof and not issues else
            '本人可登记实际经过，不填写数量' if not issues else '；'.join(issues))
    return q

def confirm_execution(*,user,task_id,payload):
    from .operation_execution_mode import task_execution_mode
    from . import operation_report_service as reports
    _payload(payload);register_action();actor,_=receipt._actor(user)
    if type(task_id) is not int or task_id<=0:_fail('OPERATION_EXECUTION_TASK_INVALID','任务身份须为正整数。',400)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            task=Task.objects.select_for_update().filter(pk=task_id,company_id=actor.company_id).first()
            if not task:_fail('OPERATION_EXECUTION_NOT_VISIBLE','未找到本公司本人已开工任务。',403)
            facts=reports.read_operation_reports(user=actor,task_id=task_id);selected=facts['selectedTask']
            mode=task_execution_mode(task,actor=actor);start=Start.objects.get(task_id=task.pk)
            proof=_history(task,start);source=starts._source(task,actor)
            q=qualification(actor,task,start,source,mode,proof)
            request_hash=_intent(actor.pk,task.pk,payload)
            old=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=ACTION,
                idempotency_key=payload['idempotencyKey']).first()
            if old:
                if (not proof or old.status!='COMMITTED' or old.entity_type!=OBJECT or old.target_entity_id!=str(task.pk)
                        or old.request_hash!=request_hash or proof['requestHash']!=request_hash
                        or proof['confirmedById']!=actor.pk or not q['admissionReady']):
                    _fail('OPERATION_EXECUTION_IDEMPOTENCY_CONFLICT','实际经过标识已绑定其他意图，或当前责任／来源已变化。')
                return facts,_writes(False)
            expected={'expectedVersion':task.version,'expectedSourceSnapshotHash':task.source_snapshot_hash,
                'expectedAssignmentHash':task.assignment_hash,'expectedStartId':start.pk,
                'expectedStartSnapshotHash':_hash(reports._start_snapshot(start)),
                'expectedExecutionVersion':1 if proof else 0}
            if any(payload[k]!=v for k,v in expected.items()):
                _fail('OPERATION_EXECUTION_SOURCE_CHANGED','任务、人员、模式、开工或实际经过版本已变化，请只读重新读取。')
            if proof:
                if not q['admissionReady']:_fail('OPERATION_EXECUTION_NOT_READY','；'.join(q['missingItems']),403)
                return facts,_writes(False)
            if not q['ready']:_fail('OPERATION_EXECUTION_NOT_READY','；'.join(q['missingItems']),403)
            snapshot=_snapshot(task,start,mode);reason=payload['reason'].strip()
            confirmed_at=timezone.now()
            state={'contractVersion':CONTRACT,'status':'confirmed','snapshot':snapshot,'proofHash':_hash(snapshot),
                'qualification':deepcopy(q),'confirmedById':actor.pk,'confirmedAt':confirmed_at.isoformat(),
                'timestampBasis':'DJANGO_LOCAL_DATETIME' if timezone.is_naive(confirmed_at) else 'AWARE_DATETIME',
                'timestampTimezone':timezone.get_default_timezone_name(),
                'requestKeyHash':sha256(payload['idempotencyKey'].encode()).hexdigest(),'requestHash':request_hash,
                'intentPayload':{k:v for k,v in payload.items() if k!='idempotencyKey'}}
            audit=record_audit(user=actor,action_code=ACTION,target=task,target_type=OBJECT,target_no=task.no,
                before={'status':''},after=state,authorization=q['authorization'],reason=reason)
            node={'processCode':PROCESS,'nodeCode':WORKFLOW_NODE,'processId':q['definitionId'],'nodeId':q['nodeId'],
                'authorityActionCode':REQUIRED_PERMISSION,'responsibilityCode':RESPONSIBILITY}
            audit.before_snapshot['workflowNode']=node;audit.after_snapshot['workflowNode']=node
            audit.save(update_fields=['before_snapshot','after_snapshot'])
            event=record_projected_business_transition(object_type=OBJECT,object_id=task.pk,source_state='',target_state='confirmed',
                action_code=ACTION,operator=actor,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
                allowed_transitions={('','confirmed')})
            identity=ExternalIdentity.objects.create(organization_id=actor.company_id,source_system='MES_OPERATION_EXECUTION',
                source_type='INTERNAL',source_object_type=ACTION,external_id=state['requestKeyHash'],target_entity_type=OBJECT,
                target_entity_id=str(task.pk),mapping_status='MATCH',source_fingerprint=request_hash,
                audit_metadata={'contractVersion':CONTRACT,'quantityApplicable':False})
            MasterDataWriteRequest.objects.create(organization_id=actor.company_id,action_code=ACTION,entity_type=OBJECT,
                target_entity_id=str(task.pk),idempotency_key=payload['idempotencyKey'],request_hash=request_hash,
                status='COMMITTED',source_identity=identity,result={'taskId':task.pk,'startRecordId':start.pk,
                    'transitionId':event.pk,'proofHash':state['proofHash']},
                audit_metadata={'actorId':actor.pk,'contractVersion':CONTRACT})
            _history(task,start)
            return reports.read_operation_reports(user=actor,task_id=task_id),_writes(True)
    except IntegrityError:_fail('OPERATION_EXECUTION_CONCURRENT_CONFLICT','此任务存在并发经过登记，请只读回查，不自动重试。')

def _writes(created):
    return {'businessWriteCount':int(created),'auditWriteCount':int(created),'stateTransitionWriteCount':int(created),
        'actualExecutionConfirmationCount':int(created),'operationExecutionConfirmationCreatedCount':int(created),
        'actualReportCount':0,'operationReportCreatedCount':0,'actualStartCount':0,'taskUpdatedCount':0,
        'completionCreatedCount':0,'workOrderUpdatedCount':0,'operationSourceUpdatedCount':0,
        'inventoryUpdatedCount':0,'scheduleUpdatedCount':0,'resourceOccupancyReleasedCount':0}


def quantity_facts():
    """No fabricated zero or unit; engineering references live in mode facts."""
    return {'workloadQuantity':None,'reportedQuantity':None,'remainingQuantity':None,'quantityPrecision':None,
        'minimumReportQuantity':None,'remainingBelowUnitPrecision':False,'quantityStatusCode':'non_quantified',
        'quantityStatusLabel':'必经不单独计量','reportedQuantityLabel':'不单独计量','remainingQuantityLabel':'不单独计量',
        'quantityPrecisionAuthority':None,'taskQuantityExceedsUnitPrecision':False,'precisionNotice':'',
        'completionProven':False,'predecessorCompletionFact':None,'downstreamReleased':False}


def report_task_row(task,start,actor,source,execution,mode):
    """The report page remains the single entry; this branch never reads a UOM."""
    from .operation_report_contract import action_contract as quantity_action
    from .operation_report_service import _start_snapshot
    from .operation_execution_mode import task_execution_mode
    display=task_execution_mode(task,verify_current=False)
    proof=_history(task,start);q=qualification(actor,task,start,source,mode,proof)
    action={**action_contract(task.pk),'displayName':'已登记实际经过' if proof else '登记实际经过','enabled':q['ready'],
        'disabledReason':'' if q['ready'] else '已登记实际经过，不重复登记。' if proof and not q['missingItems'] else '；'.join(q['missingItems'])}
    operation=task.source_snapshot['operation']
    return {'id':task.pk,'taskId':task.pk,'no':task.no,'taskNo':task.no,
        'workOrderId':task.work_order_id,'workOrderNo':task.work_order.no,'workOrderVersion':task.work_order_version,
        'operationId':task.source_operation_id,'operationName':operation['operationName'],'sequence':operation['sequence'],
        'rootRoutingVersionId':operation['rootRoutingVersionId'],'routeVersionId':operation['effectiveRoutingVersionId'],
        'rootStepId':operation['rootStepId'],'stepId':operation['effectiveStepId'],
        'workshopId':task.workshop_id,'workshopName':task.workshop.name,'receiptId':task.receipt_id,'receiptValid':source['receiptValid'],
        'receiptStatusLabel':source['resourceSource']['statusLabel'] if source['receiptValid'] else '接收事实未通过核对',
        **{k:source[k] for k in ('resourceSource','originalReceiptWorkshop','effectiveWorkshop','effectiveReceptionAuthority')},
        'workCenterId':task.work_center_id,'workCenterCode':task.work_center.code,
        'workCenterName':task.work_center.name if task.source_snapshot.get('executionResourceSelectionRef') else operation['workCenterName'],
        'workloadUomId':None,'workloadUomCode':None,'workloadUomLabel':None,'workloadLabel':'不单独计量',**quantity_facts(),
        **{k:display.get(k) for k in ('executionMode','executionModeLabel','quantityApplicable','modeSourceHash','referenceWorkload')},
        'currentExecutionModeFacts':mode,
        'executionConfirmation':proof,'executionConfirmationVersion':1 if proof else 0,
        'positionId':task.execution_position_id,'positionName':task.assignment_snapshot.get('positionName'),
        'employeeId':task.execution_employee_id,'employeeName':task.assignment_snapshot.get('employeeName'),
        'employeeUsername':task.assignment_snapshot.get('username'),'dispatchStatusLabel':'已派工',
        'statusCode':'confirmed' if proof else 'unconfirmed','statusLabel':proof['statusLabel'] if proof else '待登记实际经过',
        'executionStatusLabel':'已开工','executionRecord':execution,'startRecordId':start.pk,
        'startSnapshotHash':_hash(_start_snapshot(start)),'startAuditReference':execution['auditReference'],
        'startedAtLabel':execution['startedAtLabel'],'startedByLabel':execution['startedByLabel'],
        'version':task.version,'sourceSnapshotHash':task.source_snapshot_hash,'assignmentHash':task.assignment_hash,
        'sourceConsistent':source['ready'],'reports':[],'operationReportRecordCount':0,'reportRecordCount':0,
        'qualification':q,'availableActions':{'report':{**quantity_action(task.pk),'enabled':False,
            'disabledReason':'本任务为必经不单独计量模式，请登记真实实际经过，不填写数量。'},'confirmExecution':action},
        'stateMachineConsistent':True}
