"""Formal exact-WC responsibility governance; reads never appoint or grant."""
import hashlib,json,re
from datetime import date
from django.db import transaction,IntegrityError
from django.utils import timezone
from masterdata.models import ExternalIdentity,MasterDataWriteRequest
from pfm.formal_employee import formal_employee_queryset
from system.authorization import AuthorizationService
from system.models import PositionWorkflowResponsibility,PositionResponsibility,OrganizationOperatingAuditRecord,RolePermission
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.action_permissions import ActionPermissionPolicy,ActionPermissionValidator,POLICIES
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition,transition_business_object
from planning.services import PlanningBusinessError
from planning.mes_test_source_bridge import record_audit,_actor,_employees,_authority,_effective
from .models import WorkCenter
from .work_center_responsibility_models import WorkCenterResponsibilityScope as Scope

CONTRACT='PCE-WORK-CENTER-RESPONSIBILITY-V1';MODULE='production-work-center-responsibility'
OBJECT='WorkCenterResponsibilityScope';PATH='/api/pde/work-center-responsibilities/'
PERMISSION='system.organization.workflow_responsibility.manage'
PREFIX='pde.work_center_responsibility.'
LABELS={'active':'生效','disabled':'已停用'}
def business_today():
    now=timezone.now()
    return timezone.localdate(now) if timezone.is_aware(now) else now.date()
hash_value=lambda v:hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def fail(code,message,status=409):raise PlanningBusinessError(code,message,http_status=status)
def actor_for(user):return _actor(user)[0]
def request_hash(actor,action,object_id,payload):
    return hash_value({'actorId':actor.pk,'actionCode':action,'objectId':object_id,
        'payload':{k:v for k,v in payload.items() if k!='idempotencyKey'}})

class ObjectFacts:
    def __init__(self,actor,module,object_id,status):self.actor,self.module,self.pk,self.status=actor,module,object_id,status
    def read(self,module_code,object_ids):
        valid=module_code==self.module and object_ids==[str(self.pk)]
        return {'found':valid,'objectIds':object_ids if valid else [],'statuses':[self.status] if valid else [],
            'legalEntityIds':[str(self.actor.company_id)] if valid else [],'currentStateSource':'server'}

def management_qualification(actor,action='read',object_id=0,status='active'):
    code=PREFIX+action
    roles=tuple(RolePermission.objects.filter(permission__code=PERMISSION).values_list('role__code',flat=True).distinct())
    policy=ActionPermissionPolicy(actionCode=code,moduleCode=MODULE,requiredPermission=PERMISSION,role=roles,
        organizationScope='legal_entity',serverValidator='pde.work_center_responsibility_service.execute_work_center_responsibility',
        allowedStatuses=('*',),scope='single')
    old=POLICIES.get((MODULE,code))
    if old and old.serverValidator!=policy.serverValidator:fail('WC_SCOPE_CONTRACT_CONFLICT','工作中心责任维护动作身份冲突。')
    POLICIES[(MODULE,code)]=policy
    native=AuthorizationService.decide(user=actor,action_code=PERMISSION,organization_id=actor.company_id)
    # Organization responsibility maintenance is company-scoped. Native empty
    # object fallbacks must not turn a SELF grant into company-wide maintenance.
    strict_company_scope=bool(actor.is_superuser or _authority(actor,PERMISSION,None,None)[0])
    decision=ActionPermissionValidator(fact_provider=ObjectFacts(actor,MODULE,object_id,status)).evaluate(user=actor,
        module_code=MODULE,action_code=code,object_ids=[object_id],selection_count=1,requested_legal_entity_id=str(actor.company_id))
    permitted=bool(strict_company_scope and native['allowed'] and decision['granted'] and not(action=='disable' and status=='disabled'))
    return {'ready':permitted,'authorization':native,'decision':decision,
        'currentActorEvidence':{'userId':actor.pk,'username':actor.username,'companyId':actor.company_id},
        'statusLabel':'可维护工作中心责任范围' if permitted else '该责任范围已停用' if action=='disable' and status=='disabled' else '缺少正式流程责任维护权限'}

def state(row):
    return {'id':row.pk,'companyId':row.company_id,'workCenterId':row.work_center_id,
        'workflowResponsibilityId':row.workflow_responsibility_id,'employeeId':row.employee_id,
        'effectiveFrom':row.effective_from.isoformat() if row.effective_from else None,
        'effectiveTo':row.effective_to.isoformat() if row.effective_to else None,
        'status':row.status,'version':row.version,'createdById':row.created_by_id}

def scope_history(row,*,actor=None):
    from system.authorization_read_inputs import current_inputs
    inputs=current_inputs()
    raw=inputs.scope_history_rows(actor,row) if inputs is not None and actor is not None else NotImplemented
    events=(raw[0] if raw is not NotImplemented else
        list(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=row.pk).order_by('version','pk')))
    history=[]
    for n,event in enumerate(events,1):
        match=re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)',event.audit_reference or '')
        audit=((raw[1].get(int(match[1])) if raw is not NotImplemented else
            OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first()) if match else None)
        if (event.version!=n or not audit or audit.organization_id!=row.company_id or audit.target_type!=OBJECT
                or audit.target_id!=row.pk or audit.actor_id!=event.operator_id or audit.action_code!=event.action_code):
            fail('WC_SCOPE_HISTORY_INVALID','工作中心责任范围历史或审计不一致。')
        history.append({'id':event.pk,'sourceState':event.source_state,'targetState':event.target_state,
            'actionCode':event.action_code,'operatorId':event.operator_id,'reason':event.reason,
            'auditReference':event.audit_reference,'version':event.version,'timestamp':event.timestamp.isoformat()})
    if (len(events)!=row.version+1 or not events or events[-1].target_state!=row.status
            or audit.after_snapshot.get('state')!=state(row)):
        fail('WC_SCOPE_HISTORY_INVALID','工作中心责任范围当前版本与历史不一致。')
    return history

def serialize(row,actor):
    current=state(row);history=scope_history(row)
    data={**current,'statusCode':row.status,'statusLabel':LABELS[row.status],'scopeHash':hash_value(current),
        'workCenterName':row.work_center.name,'workflowResponsibilityLabel':' / '.join((row.workflow_responsibility.position.name,
            row.workflow_responsibility.workflow_node.process_definition.definition_name,row.workflow_responsibility.workflow_node.node_name,
            row.workflow_responsibility.responsibility.name)),
        'employeeName':row.employee.full_name if row.employee else '岗位有效任职范围',
        'stateTransitionHistory':history,'statusTransitionHistory':history,'statusTransitionCount':len(history),'stateMachineConsistent':True}
    data.pop('status',None)
    today=business_today()
    data['validityStatusLabel']=('已停用' if row.status=='disabled' else '尚未到生效日' if row.effective_from and row.effective_from>today
        else '已过有效期' if row.effective_to and row.effective_to<today else '当前有效')
    data['actionQualifications']={k:management_qualification(actor,k,row.pk,row.status) for k in ('update','disable')}
    data['active']=row.status=='active'
    data['availableActions']=[{'key':key,'actionCode':PREFIX+key,'displayName':label,'apiPath':PATH+f'{row.pk}/{key}/',
        'httpMethod':'POST','requiredPermission':PERMISSION,'serverValidator':'pde.work_center_responsibility_service.execute_work_center_responsibility',
        'enabled':data['actionQualifications'][key]['ready'],'disabledReason':'' if data['actionQualifications'][key]['ready'] else data['actionQualifications'][key]['statusLabel']}
        for key,label in [('update','保存责任有效期及员工限定'),('disable','停用本责任范围')]]
    return data

def recover(actor,action,req_hash,key_hash):
    if not any((action,req_hash,key_hash)):return None
    if not action or not req_hash or not key_hash or not re.fullmatch('[a-f0-9]{64}',req_hash) or not re.fullmatch('[a-f0-9]{64}',key_hash):
        fail('WC_SCOPE_RECOVERY_INVALID','只读核查须携准确动作及原请求标识。',400)
    if not action.startswith(PREFIX):fail('WC_SCOPE_RECOVERY_INVALID','核查动作不属于工作中心责任维护。',400)
    rows=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=action,entity_type=OBJECT,request_hash=req_hash)
    matched=[r for r in rows if r.audit_metadata.get('actorId')==actor.pk
        and hashlib.sha256(r.idempotency_key.encode()).hexdigest()==key_hash]
    result={'status':'unknown','actionCode':action,'requestHash':req_hash,'requestKeyHash':key_hash,'actorId':actor.pk,
        'statusLabel':'结果待核实，禁止重复提交'}
    if len(matched)==1 and matched[0].status=='COMMITTED':
        ledger=matched[0];row=Scope.objects.filter(pk=int(ledger.target_entity_id),company_id=actor.company_id).first()
        if not row:fail('WC_SCOPE_RECOVERY_INCONSISTENT','原请求已提交但正式对象缺失。')
        scope_history(row)
        reference=ledger.audit_metadata.get('auditReference')
        events=scope_history(row)
        if (not any(e['auditReference']==reference and e['actionCode']==action and e['operatorId']==actor.pk for e in events)
            or ledger.result.get('scopeId')!=row.pk or ledger.source_identity.source_fingerprint!=req_hash):
            fail('WC_SCOPE_RECOVERY_INCONSISTENT','原请求账本与对应动作审计不一致。')
        result.update(status='verified',statusLabel='原请求正式结果已核实',proof=ledger.result,auditReference=reference,
            proofReference=reference,objectId=ledger.audit_metadata.get('requestObjectId'))
    return result

def read_work_center_responsibilities(*,user,scope_id=None,work_center_id=None,recovery_action=None,request_hash=None,request_key_hash=None):
    actor=actor_for(user);q=management_qualification(actor)
    if not q['ready']:fail('WC_SCOPE_READ_DENIED',q['statusLabel'],403)
    rows=Scope.objects.filter(company_id=actor.company_id).select_related('work_center','workflow_responsibility__position','employee')
    if scope_id is not None:rows=rows.filter(pk=scope_id)
    if work_center_id is not None:rows=rows.filter(work_center_id=work_center_id)
    if scope_id is not None and not rows.exists():fail('WC_SCOPE_NOT_FOUND','准确责任范围不存在或不在当前公司。',404)
    centers=list(WorkCenter.objects.filter(company_id=actor.company_id,is_active=True).values('id','code','name','workshop_id'))
    mappings=list(PositionWorkflowResponsibility.objects.filter(position__company_id=actor.company_id,active=True,
        responsibility__is_active=True,responsibility__status='ACTIVE',ownership_type='OWNER',workflow_node__active=True)
        .values('id','position_id','position__name','responsibility__code','responsibility__name','workflow_code','node_code',
            'workflow_node__node_name','workflow_node__process_definition__definition_name'))
    for item in mappings:
        item['workflowResponsibilityLabel']=' / '.join((item['position__name'],
            item['workflow_node__process_definition__definition_name'],item['workflow_node__node_name'],item['responsibility__name']))
    employees=list(formal_employee_queryset(company_id=actor.company_id).values('id','employee_no','full_name','position_ref_id','user_id'))
    available=[]
    for key,label in [('read','读取工作中心责任范围'),('create','新建工作中心责任绑定')]:
        qualification=management_qualification(actor,key)
        available.append({'key':key,'actionCode':PREFIX+key,'displayName':label,'apiPath':PATH if key=='read' else PATH+'create/',
            'httpMethod':'GET' if key=='read' else 'POST','enabled':qualification['ready'],'disabledReason':'' if qualification['ready'] else qualification['statusLabel'],
            'requiredPermission':PERMISSION,'serverValidator':'pde.work_center_responsibility_service.execute_work_center_responsibility'})
    return {'contractVersion':CONTRACT,'moduleCode':MODULE,'factSource':'server','currentStateSource':'server','companyId':actor.company_id,
        'currentActorEvidence':q['currentActorEvidence'],'rows':[serialize(row,actor) for row in rows.order_by('pk')],
        'workCenters':centers,'workflowResponsibilities':mappings,'employees':employees,'availableActions':available,
        'resultRecovery':recover(actor,recovery_action,request_hash,request_key_hash)}

def _date(value):
    if value is None:return None
    if not isinstance(value,str):fail('WC_SCOPE_DATE_INVALID','有效期须为明确日期。',400)
    try:return date.fromisoformat(value)
    except ValueError:fail('WC_SCOPE_DATE_INVALID','有效期须为YYYY-MM-DD。',400)

def execute_work_center_responsibility(*,user,action,payload,scope_id=None):
    if action not in ('create','update','disable') or not isinstance(payload,dict):fail('WC_SCOPE_ACTION_INVALID','维护意图不符合正式合同。',400)
    allowed={'workCenterId','workflowResponsibilityId','employeeId','effectiveFrom','effectiveTo','expectedVersion','expectedScopeHash','active','reason','idempotencyKey'}
    if set(payload)-allowed:fail('WC_SCOPE_PAYLOAD_INVALID','维护意图含非正式字段。',400)
    for field in ('workCenterId','workflowResponsibilityId','employeeId'):
        value=payload.get(field)
        if value is not None and (type(value) is not int or value<=0):fail('WC_SCOPE_ID_INVALID','正式引用须为正整数或空。',400)
    if payload.get('expectedVersion') is not None and (type(payload['expectedVersion']) is not int or payload['expectedVersion']<0):fail('WC_SCOPE_VERSION_INVALID','版本标识无效。',400)
    reason=payload.get('reason');key=payload.get('idempotencyKey')
    if not isinstance(reason,str) or reason!=reason.strip() or not 2<=len(reason)<=300:fail('WC_SCOPE_REASON_REQUIRED','请填写2至300字真实维护原因。',400)
    if not isinstance(key,str) or not re.fullmatch('[A-Za-z0-9._:-]{12,160}',key):fail('WC_SCOPE_KEY_INVALID','原请求防重复标识无效。',400)
    actor=actor_for(user);code=PREFIX+action;rh=request_hash(actor,code,scope_id,payload)
    with transaction.atomic():
        old=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=code,idempotency_key=key).first()
        if old:
            if old.status!='COMMITTED' or old.request_hash!=rh or old.audit_metadata.get('actorId')!=actor.pk:fail('WC_SCOPE_IDEMPOTENCY_CONFLICT','原请求标识已用于不同意图。')
            row_id=int(old.target_entity_id)
            return read_work_center_responsibilities(user=actor,scope_id=row_id),{'businessWriteCount':0,'auditWriteCount':0,'stateTransitionWriteCount':0,'idempotentReplay':True}
        q=management_qualification(actor,action,scope_id or 0)
        if not q['ready']:fail('WC_SCOPE_WRITE_DENIED',q['statusLabel'],403)
        row=Scope.objects.select_for_update().filter(pk=scope_id,company_id=actor.company_id).first() if scope_id else None
        if action!='create' and not row:fail('WC_SCOPE_NOT_FOUND','责任绑定不存在或不在本公司。',404)
        if action=='create' and (scope_id is not None or payload.get('expectedVersion') is not None or payload.get('expectedScopeHash') is not None):fail('WC_SCOPE_VERSION_CONFLICT','新建不得冒用旧版本。')
        if row:
            scope_history(row)
            if payload.get('expectedVersion')!=row.version or payload.get('expectedScopeHash')!=hash_value(state(row)):fail('WC_SCOPE_VERSION_CONFLICT','责任范围已变化，请只读重查。')
        before=state(row) if row else {}
        if action=='disable':
            if row.status=='disabled':fail('WC_SCOPE_ALREADY_DISABLED','该责任范围已停用。')
            target='disabled'
        else:
            center=WorkCenter.objects.filter(pk=payload.get('workCenterId'),company_id=actor.company_id,is_active=True).select_related('workshop').first()
            mapping=PositionWorkflowResponsibility.objects.filter(pk=payload.get('workflowResponsibilityId'),position__company_id=actor.company_id,
                active=True,ownership_type='OWNER',responsibility__is_active=True,responsibility__status='ACTIVE',workflow_node__active=True,
                workflow_node__process_definition__active=True).select_related('position','responsibility','workflow_node__process_definition').first()
            today=business_today()
            if not center or not center.workshop_id or not mapping or not _effective(mapping,today) or not _effective(mapping.responsibility,today):fail('WC_SCOPE_SOURCE_INVALID','工作中心、正式流程责任或其有效期不合法。')
            if not PositionResponsibility.objects.filter(position_id=mapping.position_id,responsibility_id=mapping.responsibility_id,active=True).exists():fail('WC_SCOPE_DUTY_MISSING','原岗位尚未正式承担该职责。')
            if mapping.position.workshop_id and mapping.position.workshop_id!=center.workshop_id:fail('WC_SCOPE_WORKSHOP_MISMATCH','岗位车间与工作中心不一致。')
            employee_id=payload.get('employeeId');employee=None
            if employee_id is not None:
                employee=formal_employee_queryset(company_id=actor.company_id).filter(pk=employee_id,position_ref_id=mapping.position_id).first()
                if not employee:fail('WC_SCOPE_EMPLOYEE_INVALID','员工限定必须为该岗位的真实有效任职员工。')
            elif formal_employee_queryset(company_id=actor.company_id).filter(position_ref_id=mapping.position_id).count()!=1:
                fail('WC_SCOPE_EMPLOYEE_LIMIT_REQUIRED','该岗位有效任职人员不唯一，必须明确实际员工限定。')
            period=(_date(payload.get('effectiveFrom')),_date(payload.get('effectiveTo')))
            if all(period) and period[1]<period[0]:fail('WC_SCOPE_PERIOD_INVALID','失效日不得早于生效日。',400)
            if 'active' in payload and type(payload['active']) is not bool:fail('WC_SCOPE_ACTIVE_INVALID','生效选择须明确布尔值。',400)
            target='active' if payload.get('active',row.status=='active' if row else True) else 'disabled'
            if row and (row.work_center_id!=center.pk or row.workflow_responsibility_id!=mapping.pk):fail('WC_SCOPE_IDENTITY_IMMUTABLE','原工作中心及流程责任身份不可改换，请另建绑定。')
            if not row:
                if Scope.objects.filter(company_id=actor.company_id,work_center=center,workflow_responsibility=mapping).exists():fail('WC_SCOPE_DUPLICATE','该工作中心与正式流程责任已存在绑定。')
                row=create_business_object_with_initial_state(model=Scope,initial_state=target,company_id=actor.company_id,
                    work_center=center,workflow_responsibility=mapping,employee=employee,effective_from=period[0],effective_to=period[1],created_by=actor)
            else:
                row.employee=employee;row.effective_from,row.effective_to=period
                row._scope_fields_authorized=True
                row.save(update_fields=['employee','effective_from','effective_to'])
                row._scope_fields_authorized=False
        after={**state(row),'status':target,'version':row.version if action=='create' else row.version+1}
        audit=record_audit(user=actor,action_code=code,target=row,target_type=OBJECT,target_no=str(row.pk),before=before,after=after,
            authorization=q['authorization'],reason=reason)
        ref=f'OrganizationOperatingAuditRecord:{audit.pk}'
        if action=='create':record_projected_business_transition(object_type=OBJECT,object_id=row.pk,source_state='',target_state=target,
            action_code=code,operator=actor,reason=reason,audit_reference=ref,allowed_transitions={('',target)})
        else:transition_business_object(business_object=row,object_type=OBJECT,source_state=row.status,target_state=target,
            action_code=code,operator=actor,reason=reason,audit_reference=ref,allowed_transitions={(row.status,target)})
        identity=ExternalIdentity.objects.create(organization_id=actor.company_id,source_system='PDE_WC_RESPONSIBILITY',source_type='INTERNAL',
            source_object_type=OBJECT,external_id=hashlib.sha256((code+':'+key).encode()).hexdigest(),target_entity_type=OBJECT,
            target_entity_id=str(row.pk),mapping_status='MATCH',source_fingerprint=rh)
        MasterDataWriteRequest.objects.create(organization_id=actor.company_id,action_code=code,entity_type=OBJECT,idempotency_key=key,
            request_hash=rh,source_identity=identity,status='COMMITTED',target_entity_id=str(row.pk),
            result={'scopeId':row.pk,'version':row.version,'scopeHash':hash_value(state(row)),'auditReference':ref},
            audit_metadata={'actorId':actor.pk,'auditReference':ref,'requestObjectId':scope_id})
    facts=read_work_center_responsibilities(user=actor,scope_id=row.pk)
    facts['resultRecovery']={'status':'verified','actorId':actor.pk,'actionCode':code,'requestHash':rh,
        'requestKeyHash':hashlib.sha256(key.encode()).hexdigest(),'proofReference':ref,'objectId':scope_id,
        'proof':{'scopeId':row.pk,'version':row.version,'auditReference':ref}}
    return facts,{'businessWriteCount':1,'auditWriteCount':1,'stateTransitionWriteCount':1}
