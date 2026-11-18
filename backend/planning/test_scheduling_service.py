"""TEST source adapter to the existing schedule store and native save protocol.

Uses the delivered writer lock/segment conversion, native minute preview,
initialization/transition/audit services. No plans or execution objects created.
"""
from copy import deepcopy
from datetime import datetime,date,timezone
from decimal import Decimal
from pathlib import Path
import os,time
import re
from django.conf import settings
from django.db import connection,transaction,models,OperationalError
from system.models import User,RolePermission,OrganizationOperatingAuditRecord
from system.authorization import AuthorizationService
from workflow_runtime.action_permissions import ActionPermissionPolicy,ActionPermissionValidator,POLICIES
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition,transition_business_object
from pde.models import OrderRoutingExecutionArrangement as Arrangement
from pde.test_business_bom_service import authorize
from pde.production_foundation_service import _audit
from pde.order_routing_execution_service import fail
from pde.order_execution_capacity_read_service import read_capacity_review
from .models import FormalProductionSchedule as Schedule,ProcessingReservation as Reservation
from .scheduling_primitives import _hash,_json,_writer_lock,_segments,_instant,_db_instant,_read_instant

CONTRACT='PCE-TEST-SCHEDULE-V1'
MODULE='test-production-schedule'
OBJECT='FormalProductionSchedule'
PERMISSION='planning.production_plan.confirm'
SOURCE_KEYS=('stepId','sequence','operationId','decision','decisionBasis','workloadQuantity','workloadUnitId','workCenterId','capacity','calendar','result','preparationSource','transferSource','savedWorkloadReference')

def _actor(user):
    from system.authorization_read_inputs import current_inputs
    inputs=current_inputs();actor=inputs.actor(user) if inputs is not None else NotImplemented
    if actor is NotImplemented:actor=User.objects.get(pk=user.pk)
    if not actor.is_active or actor.company_id!=user.company_id:fail('SCOPE_DENIED','账号公司或有效身份已经变化。')
    return actor

def _boundary():
    configured=os.environ.get('PCE_TEST_SCHEDULING_DATABASE','')
    if os.environ.get('PCE_TEST_SCHEDULING_ISOLATED')!='1' or not configured or Path(configured).resolve()!=Path(connection.settings_dict['NAME']).resolve():
        fail('TEST_SCHEDULING_ISOLATION_REQUIRED','测试排程写入仅开放明确绑定的隔离数据库。')
    with connection.cursor() as cursor:
        actual=next((r[2] for r in cursor.execute('pragma database_list').fetchall() if r[1]=='main'),'')
    if not actual or Path(actual).resolve()!=Path(configured).resolve():fail('TEST_DATABASE_BINDING_INVALID','测试库实际连接不一致。')

def _arrangement(actor,pk):
    obj=Arrangement.objects.filter(pk=pk,company_id=actor.company_id).first()
    if obj is None:fail('SCOPE_DENIED','安排不存在或不属于当前公司。')
    authorize(actor,'production.master_data.view',obj.company_id)
    if obj.usage_purpose!='TEST_BUSINESS':fail('TEST_PURPOSE_REQUIRED','仅承接真实测试安排，不允许调用者选择用途。')
    return obj

def decision(actor,arr,action,row=None):
    roles=tuple(RolePermission.objects.filter(permission__code=PERMISSION).values_list('role__code',flat=True))
    POLICIES[(MODULE,action)]=ActionPermissionPolicy(action,MODULE,PERMISSION,roles,'legal_entity','planning.test_scheduling_service',('draft','saved','cancelled'),'single')
    target=row.pk if row else arr.pk
    class Facts:
        def read(self,module_code,object_ids):
            ok=module_code==MODULE and object_ids==[str(target)]
            return {'found':ok,'objectIds':[str(target)] if ok else [],'statuses':[row.status if row else 'draft'],'legalEntityIds':[str(arr.company_id)],'currentStateSource':'server'}
    result=ActionPermissionValidator(fact_provider=Facts()).evaluate(user=actor,module_code=MODULE,action_code=action,object_ids=[target],selection_count=1,requested_legal_entity_id=str(arr.company_id))
    if not result['granted']:fail('PERMISSION_DENIED',result.get('reason','没有测试排程动作权限。'))
    native=AuthorizationService.decide(user=actor,action_code=PERMISSION,organization_id=arr.company_id,business_object={'organizationId':arr.company_id})
    if not native['allowed']:fail('PERMISSION_DENIED',native['reason'])
    return result,native

def source_signature(value):
    return _hash({'scope':value['scope'],'sourceIdentity':value['sourceIdentity'],'rows':[{k:r.get(k) for k in SOURCE_KEYS} for r in value['rows']]})

def admission(value):
    return _hash({'sourceSignature':source_signature(value),'startAt':value['testStartAt'],'completionAt':value['completionAt'],'rows':value['rows'],'resourceFacts':value['resourceFacts']})

def require_formal_schedule(row):
    if row.usage_purpose!='PRODUCTION_USE' or not row.production_plan_id or row.execution_arrangement_id:
        fail('FORMAL_CONSUMER_PURPOSE_REJECTED','正式消费者拒绝测试及未分类排程。')
    return row

def verify(row):
    if row.usage_purpose!='TEST_BUSINESS' or row.production_plan_id or not row.execution_arrangement_id or row.snapshot.get('contractVersion')!=CONTRACT:
        fail('TEST_SCHEDULE_SOURCE_INVALID','不是具有真实安排来源的测试排程。')
    if row.company_id!=row.execution_arrangement.company_id or row.execution_arrangement.usage_purpose!='TEST_BUSINESS' or row.snapshot_hash!=_hash(row.snapshot):
        fail('SCHEDULE_SNAPSHOT_INVALID','测试排程公司、用途或冻结Hash不一致。')
    v=row.snapshot['preview']
    if v['scope']['arrangementId']!=row.execution_arrangement_id or _read_instant(row.start_at)!=_instant(v['testStartAt']) or _read_instant(row.end_at)!=_instant(v['completionAt']):
        fail('SCHEDULE_IDENTITY_INVALID','冻结时间及安排身份不一致。')
    transitions=list(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=row.pk).order_by('version','pk'))
    pairs=[('','draft'),('draft','saved')]+([('saved','cancelled')] if row.status=='cancelled' else [])
    if row.status not in ('saved','cancelled') or len(transitions)!=len(pairs) or row.version!=len(pairs)-1:fail('SCHEDULE_STATE_INVALID','状态与统一转换历史不一致。')
    for i,(t,pair) in enumerate(zip(transitions,pairs),1):
        aid=t.audit_reference.removeprefix('OrganizationOperatingAuditRecord:')
        a=OrganizationOperatingAuditRecord.objects.filter(pk=aid,organization_id=row.company_id,target_type=OBJECT,target_id=row.pk,actor_id=t.operator_id,action_code=t.action_code).first()
        proof=a.after_snapshot.get('state',{}) if a else {}
        if t.version!=i or (t.source_state,t.target_state)!=pair or proof.get('snapshotHash')!=row.snapshot_hash or proof.get('status')!=pair[1] or proof.get('actionPermissionDecision',{}).get('granted') is not True or proof.get('actionPermissionDecision',{}).get('action',{}).get('moduleCode')!=MODULE:
            fail('SCHEDULE_AUDIT_INVALID','缺少同一对象、操作人及快照的真实审计。')
        expected='cancel-test-schedule' if pair[1]=='cancelled' else 'save-test-schedule'
        native=a.after_snapshot.get('authorization',{})
        if proof['actionPermissionDecision'].get('action',{}).get('actionCode')!=expected or native.get('allowed') is not True or PERMISSION not in native.get('permissionCodes',[]):
            fail('SCHEDULE_ACTION_PROOF_INVALID','审计动作或原生组织授权不匹配。')
    actual=list(row.reservations.order_by('pk'))
    if len(actual)!=len(row.snapshot['segments']):fail('SCHEDULE_SEGMENTS_INVALID','占用条数与快照不一致。')
    for saved,source in zip(actual,row.snapshot['segments']):
        if saved.company_id!=row.company_id or saved.routing_step_id!=source['stepId'] or saved.work_center_id!=source['workCenterId'] or saved.sequence!=source['sequence'] or _read_instant(saved.start_at)!=_instant(source['start']) or _read_instant(saved.end_at)!=_instant(source['end']) or Decimal(saved.minutes)!=Decimal(source['minutes']) or saved.production_date.isoformat()!=source['productionDate'] or (saved.released_at is None)!=(row.status=='saved'):
            fail('SCHEDULE_SEGMENT_SOURCE_INVALID','加工分段或释放状态不匹配。')
    return actual

def _audit_state(actor,row,action,state,auth,reason):
    proof,native=auth
    return _audit(user=actor,organization_id=row.company_id,action_code=action,instance=row,before={},after={'status':state,'snapshotHash':row.snapshot_hash,'actionPermissionDecision':proof},reason=reason,authorization=native,execution_chain={'userId':actor.pk,'purpose':'TEST_BUSINESS','permissionBasis':'既有计划员权限；此动作只适用于测试排程，不授予正式排程权限'})

def _present(row,current_signature=None):
    reservations=verify(row);v=row.snapshot['preview']
    return {'id':row.pk,'scheduleNo':f'TEST-SCHEDULE-{row.pk:06d}','usagePurpose':row.usage_purpose,'purposeLabel':'测试用途（不得制造）','statusLabel':'已保存测试排程' if row.status=='saved' else '已取消并释放占用','cancelled':row.status=='cancelled','version':row.version,'arrangementId':row.execution_arrangement_id,'arrangementRevision':v['scope']['arrangementRevision'],'editVersion':v['scope']['arrangementEditVersion'],'startAt':v['testStartAt'],'completionAt':v['completionAt'],'snapshotHash':row.snapshot_hash,'currentSourceValid':row.status=='saved' and current_signature==row.snapshot['sourceSignature'],'formalManufacturingEligible':False,'activeReservationCount':sum(x.released_at is None for x in reservations),'releasedReservationCount':sum(x.released_at is not None for x in reservations),'reservations':[{'id':x.pk,'stepId':x.routing_step_id,'sequence':x.sequence,'workCenterId':x.work_center_id,'start':_read_instant(x.start_at).astimezone(_instant(v['testStartAt']).tzinfo).isoformat(),'end':_read_instant(x.end_at).astimezone(_instant(v['testStartAt']).tzinfo).isoformat(),'minutes':x.minutes,'released':x.released_at is not None} for x in reservations]}

def read(*,user,arrangement_id,current_review=None):
    actor=_actor(user);arr=_arrangement(actor,arrangement_id)
    issue=None
    try:current=current_review or read_capacity_review(user=actor,arrangement_id=arr.pk)
    except Exception as error:
        if not hasattr(error,'code'):raise
        issue={'code':error.code,'statusLabel':str(error)}
        current={'scope':{'companyId':arr.company_id,'arrangementId':arr.pk,'arrangementRevision':arr.arrangement_revision,'arrangementEditVersion':arr.edit_version,'usagePurpose':arr.usage_purpose},'requestIdentity':{'userId':actor.pk,'username':actor.username,'companyId':actor.company_id},'summary':{'workloadReady':False}}
    if current['scope']['arrangementId']!=arr.pk or current['scope']['companyId']!=actor.company_id:fail('SCOPE_DENIED','回读来源范围不一致。')
    signature=source_signature(current) if current['summary']['workloadReady'] else None
    rows=list(Schedule.objects.filter(company_id=actor.company_id,execution_arrangement=arr,usage_purpose='TEST_BUSINESS').order_by('-revision'))
    history=[_present(r,signature) for r in rows]
    actions=[]
    for name,label in (('save-test-schedule','保存测试排程'),('cancel-test-schedule','取消测试排程并释放占用')):
        try:decision(actor,arr,name,rows[0] if rows and name.startswith('cancel') else None);allowed=True;reason=''
        except Exception as e:allowed=False;reason=str(e)
        if name=='save-test-schedule' and any(not item['cancelled'] and item['currentSourceValid'] for item in history):
            allowed=False;reason='已有当前有效测试排程，无需再次保存。'
        if name=='cancel-test-schedule' and not any(not item['cancelled'] for item in history):
            allowed=False;reason='当前没有可取消的有效测试排程。'
        actions.append({'actionCode':name,'displayName':label,'moduleCode':MODULE,'requiredPermission':PERMISSION,'roleSource':'既有计划员角色与组织授权','organizationScope':arr.company_id,'serverValidator':'planning.test_scheduling_service','executable':allowed,'disabledReason':reason})
    return {'contractVersion':CONTRACT,'factSource':'server','scope':current['scope'],'requestIdentity':current['requestIdentity'],'currentSourceIssue':issue,'activeSchedule':next((r for r in history if not r['cancelled']),None),'history':history,'availableActions':actions,'formalManufacturingEligible':False,'databaseBusinessWriteCount':0}

def _payload(payload,keys):
    if not isinstance(payload,dict) or set(payload)!=set(keys):fail('TEST_SCHEDULE_FIELDS_INVALID','不接受用途、公司、来源、数量或分段等调用者覆盖字段。')
    for key in ('reason','idempotencyKey'):
        if not isinstance(payload[key],str) or not payload[key].strip() or len(payload[key])>300:fail('TEST_SCHEDULE_INPUT_INVALID','操作依据及幂等标识不能为空或过长。')
    return payload['reason'].strip(),payload['idempotencyKey'].strip()

def _retry(call):
    for attempt in range(4):
        try:return call()
        except OperationalError as e:
            if 'locked' not in str(e).lower() or attempt==3:raise
            time.sleep(.1*(attempt+1))

def commit(*,user,arrangement_id,payload):
    reason,idem=_payload(payload,('startAt','admissionToken','reason','idempotencyKey'))
    if not isinstance(payload['admissionToken'],str) or not re.fullmatch('[0-9a-f]{64}',payload['admissionToken']):fail('ADMISSION_TOKEN_REQUIRED','须提交服务端读取的准确准入凭据。')
    actor=_actor(user);_boundary();request_hash=_hash({'arrangementId':arrangement_id,**payload})
    def run():
        with transaction.atomic():
            _writer_lock(actor)
            arr=_arrangement(_actor(actor),arrangement_id);auth=decision(actor,arr,'save-test-schedule')
            prior=Schedule.objects.filter(company_id=actor.company_id,idempotency_key=idem).first()
            if prior:
                if prior.execution_arrangement_id!=arr.pk or prior.request_hash!=request_hash:fail('SCHEDULE_IDEMPOTENCY_CONFLICT','幂等键已用于不同来源或内容。')
                verify(prior);return prior.pk,True
            active=Schedule.objects.filter(execution_arrangement=arr,usage_purpose='TEST_BUSINESS',status='saved').first()
            if active:
                verify(active)
                current=read_capacity_review(user=actor,arrangement_id=arr.pk)
                if source_signature(current)!=active.snapshot['sourceSignature'] or payload['startAt']!=active.snapshot['preview']['testStartAt']:fail('SCHEDULE_ALREADY_SAVED_SOURCE_CHANGED','已有有效排程；来源或开始时间变化，须先取消并重新准入。')
                if payload['admissionToken']!=active.admission_token:fail('SCHEDULE_ADMISSION_CHANGED','已有排程的准入来源凭据不匹配，不新增占用。')
                return active.pk,True
            from pde.order_execution_date_preview_service import preview_dates
            value=preview_dates(user=actor,arrangement_id=arr.pk,start_at=payload['startAt'])
            if admission(value)!=payload['admissionToken']:fail('SCHEDULE_ADMISSION_CHANGED','来源、日历、日期或占用已变化；未保存，请重新预览后提交。')
            segments=_segments({'dates':[{**r,'rootStepId':r['stepId']} for r in value['rows']]},actor.company_id)
            if not segments:fail('POSITIVE_SCHEDULE_REQUIRED','不保存没有正数加工占用的空排程。')
            frozen={'contractVersion':CONTRACT,'preview':deepcopy(value),'segments':segments,'sourceSignature':source_signature(value)}
            revision=(Schedule.objects.filter(execution_arrangement=arr).aggregate(value=models.Max('revision'))['value'] or 0)+1
            row=create_business_object_with_initial_state(model=Schedule,initial_state='draft',company_id=actor.company_id,production_plan=None,usage_purpose='TEST_BUSINESS',execution_arrangement=arr,revision=revision,version=0,start_at=_db_instant(_instant(value['testStartAt'])),end_at=_db_instant(_instant(value['completionAt'])),saved_start_date=date.fromisoformat(value['testStartAt'][:10]),timezone=value['timezone'],snapshot=_json(frozen),snapshot_hash=_hash(frozen),admission_token=payload['admissionToken'],idempotency_key=idem,request_hash=request_hash,created_by=actor)
            initial=_audit_state(actor,row,'planning.test_schedule.initialize','draft',auth,reason)
            record_projected_business_transition(object_type=OBJECT,object_id=row.pk,source_state='',target_state='draft',action_code=initial.action_code,operator=actor,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{initial.pk}',allowed_transitions=(('','draft'),))
            for part in segments:
                Reservation.objects.create(schedule=row,company_id=actor.company_id,work_center_id=part['workCenterId'],routing_step_id=part['stepId'],sequence=part['sequence'],start_at=_db_instant(_instant(part['start'])),end_at=_db_instant(_instant(part['end'])),production_date=date.fromisoformat(part['productionDate']),minutes=part['minutes'])
            audit=_audit_state(actor,row,'planning.test_schedule.commit','saved',auth,reason)
            transition_business_object(business_object=row,object_type=OBJECT,source_state='draft',target_state='saved',action_code=audit.action_code,operator=actor,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions=(('draft','saved'),))
            verify(row);return row.pk,False
    pk,repeated=_retry(run)
    return {'scheduleId':pk,'idempotent':repeated,'operationWrites':{'scheduleCreatedCount':0 if repeated else 1,'reservationCreatedCount':0 if repeated else Schedule.objects.get(pk=pk).reservations.count(),'auditCreatedCount':0 if repeated else 2,'transitionCreatedCount':0 if repeated else 2,'coordinationWriteCount':1},'facts':read(user=actor,arrangement_id=arrangement_id)}

def cancel(*,user,arrangement_id,schedule_id,payload):
    reason,idem=_payload(payload,('expectedVersion','reason','idempotencyKey'));actor=_actor(user);_boundary()
    request_hash=_hash({'arrangementId':arrangement_id,'scheduleId':schedule_id,**payload})
    def run():
        with transaction.atomic():
            _writer_lock(actor);arr=_arrangement(_actor(actor),arrangement_id)
            row=Schedule.objects.filter(pk=schedule_id,execution_arrangement=arr,company_id=actor.company_id,usage_purpose='TEST_BUSINESS').first()
            if not row:fail('SCOPE_DENIED','测试排程不存在或不属于当前安排/公司。')
            auth=decision(actor,arr,'cancel-test-schedule',row);verify(row)
            if row.status=='cancelled':
                if row.cancel_idempotency_key!=idem or row.cancel_request_hash!=request_hash:fail('SCHEDULE_ALREADY_CANCELLED','已取消，不重复执行不同撤销请求。')
                return True
            if type(payload['expectedVersion']) is not int or row.version!=payload['expectedVersion']:fail('SCHEDULE_VERSION_CHANGED','排程版本已变化，请重新读取。')
            row.reservations.filter(released_at__isnull=True).update(released_at=_db_instant(datetime.now(timezone.utc)))
            audit=_audit_state(actor,row,'planning.test_schedule.cancel','cancelled',auth,reason)
            transition_business_object(business_object=row,object_type=OBJECT,source_state='saved',target_state='cancelled',action_code=audit.action_code,operator=actor,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions=(('saved','cancelled'),))
            Schedule.objects.filter(pk=row.pk).update(cancel_idempotency_key=idem,cancel_request_hash=request_hash)
            verify(row);return False
    repeated=_retry(run)
    return {'scheduleId':schedule_id,'idempotent':repeated,'operationWrites':{'scheduleCreatedCount':0,'reservationReleasedCount':0 if repeated else Schedule.objects.get(pk=schedule_id).reservations.count(),'auditCreatedCount':0 if repeated else 1,'transitionCreatedCount':0 if repeated else 1,'coordinationWriteCount':1},'facts':read(user=actor,arrangement_id=arrangement_id)}
