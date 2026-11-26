"""Purpose-preserving test source adapter to native MES storage/protocol.

Numbering, company mutex, state initialization, audit and operation full_clean
are native services. Only generation/read are open; purpose is not a state.
"""
from functools import wraps
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import os,re
from django.db import connection,transaction
from system.models import RolePermission,OrganizationOperatingAuditRecord
from system.authorization import AuthorizationService
from masterdata.models import CodeRule
from workflow_runtime.action_permissions import POLICIES,ActionPermissionPolicy,ActionPermissionValidator
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition
from pde.production_foundation_service import _audit
from pde.order_routing_execution_service import fail
from pde.models import RoutingStep
from .work_order_models import ProductionWorkOrder as WO,ProductionWorkOrderOperation as Operation
from .models import FormalProductionSchedule as Schedule
from .scheduling_primitives import _hash,_json,_writer_lock
from .test_scheduling_service import _actor,_arrangement,_retry

CONTRACT='PCE-TEST-WORK-ORDER-V1'
MODULE='test-production-work-order'
ACTION='generate-test-work-order'
PERMISSION='planning.production_plan.confirm'
ENTITY='test_production_work_order'
OBJECT='ProductionWorkOrder'

def _boundary():
    declared=os.environ.get('PCE_TEST_WORK_ORDER_DATABASE','')
    if os.environ.get('PCE_TEST_WORK_ORDER_ISOLATED')!='1' or not declared or Path(declared).resolve()!=Path(connection.settings_dict['NAME']).resolve() or connection.vendor!='sqlite':
        fail('TEST_WORK_ORDER_ISOLATION_REQUIRED','测试工单生成仅开放明确绑定的隔离数据库。')
    with connection.cursor() as c:actual=next((r[2] for r in c.execute('pragma database_list') if r[1]=='main'),'')
    if not actual or Path(actual).resolve()!=Path(declared).resolve():fail('TEST_WORK_ORDER_DATABASE_MISMATCH','实际测试数据库绑定不一致。')

def decision(actor,schedule_id):
    roles=tuple(RolePermission.objects.filter(permission__code=PERMISSION).order_by('role__code').values_list('role__code',flat=True).distinct())
    POLICIES[(MODULE,ACTION)]=ActionPermissionPolicy(ACTION,MODULE,PERMISSION,roles,'legal_entity','planning.test_work_order_service.generate',('source_ready',),'single')
    class Facts:
        def read(self,module_code,object_ids):
            found=module_code==MODULE and object_ids==[str(schedule_id)]
            return {'found':found,'objectIds':[str(schedule_id)] if found else [],'statuses':['source_ready'],'legalEntityIds':[str(actor.company_id)],'currentStateSource':'server'}
    proof=ActionPermissionValidator(fact_provider=Facts()).evaluate(user=actor,module_code=MODULE,action_code=ACTION,object_ids=[schedule_id],selection_count=1,requested_legal_entity_id=str(actor.company_id))
    native=AuthorizationService.decide(user=actor,action_code=PERMISSION,organization_id=actor.company_id,business_object={'organizationId':actor.company_id})
    if not proof['granted'] or not native['allowed']:fail('PERMISSION_DENIED',proof.get('reason') or native.get('reason') or '没有测试工单生成权限。')
    return proof,native

def source_for(base):
    schedule=Schedule.objects.get(pk=base['sourceSchedule']['id'],company_id=base['scope']['companyId'],usage_purpose='TEST_BUSINESS')
    frozen={r['stepId']:r for r in schedule.snapshot['preview']['rows']}
    steps=RoutingStep.objects.in_bulk(frozen)
    reservations={}
    for reservation in schedule.reservations.all():
        reservations.setdefault(reservation.routing_step_id,[]).append(reservation.pk)
    operations=[]
    for row in base['rows']:
        if row['decision']!='REQUIRED':continue
        step=steps[row['stepId']];old=frozen[step.pk]
        if step.routing_version_id!=base['scope']['routingVersionId'] or step.operation_id!=row['operationId'] or old['workloadQuantity'] is None:fail('WORK_ORDER_FIXED_STEP_CHANGED','准确固定步骤或作业量来源不一致。')
        operations.append({'sequence':row['sequence'],'rootStepId':step.pk,'effectiveStepId':step.pk,'rootRoutingVersionId':step.routing_version_id,'effectiveRoutingVersionId':step.routing_version_id,'operationId':step.operation_id,'operationName':row['operationName'],'workCenterId':row['workCenterId'],'workCenterName':row['workCenterName'],'dependencyOnly':False,'workloadQuantity':row['workloadQuantity'],'workloadUomId':old['workloadUnitId'],'workloadUomLabel':row['workloadUnitLabel'],'requirementId':row['requirementId'],'start':row['start'],'end':row['end'],'processingMinutes':old['processingMinutes'],'predecessorSequences':old['predecessorSequences'],'reservationIds':reservations.get(step.pk,[]),'frozenStep':deepcopy(old)})
    if not operations:fail('WORK_ORDER_OPERATIONS_REQUIRED','不能生成没有实际执行工序的空工单。')
    selected=[{k:v for k,v in r.items() if k!='statusLabel'} for r in base['rows']]
    return _json({'contractVersion':CONTRACT,'companyId':base['scope']['companyId'],'scope':base['scope'],'product':base['product'],'sourceSchedule':{**base['sourceSchedule'],'revision':schedule.revision},'routeSelections':selected,'operations':operations,'workflowMetadata':base['workflow']})

def token(actor,source):return _hash({'contract':CONTRACT,'action':ACTION,'userId':actor.pk,'companyId':actor.company_id,'sourceHash':_hash(source)})

def require_formal_work_order(row):
    if row.usage_purpose!='PRODUCTION_USE' or not row.production_plan_id or row.source_schedule.usage_purpose!='PRODUCTION_USE' or row.source_schedule.production_plan_id!=row.production_plan_id or row.source_schedule.company_id!=row.company_id:
        fail('FORMAL_WORK_ORDER_PURPOSE_REJECTED','正式生成、下达及执行消费者拒绝测试或未分类工单。')
    return row

from .verified_read_memo import verified_model_read
@verified_model_read
def verify(row):
    if row.usage_purpose=='PRODUCTION_USE':
        from .work_order_execution_service import _verify
        return _verify(row)
    source=row.source_snapshot
    if row.usage_purpose!='TEST_BUSINESS' or row.production_plan_id is not None or source.get('contractVersion')!=CONTRACT or _hash(source)!=row.snapshot_hash or source['companyId']!=row.company_id or source['sourceSchedule']['id']!=row.source_schedule_id or row.source_schedule.company_id!=row.company_id or row.source_schedule.usage_purpose!='TEST_BUSINESS':fail('TEST_WORK_ORDER_SOURCE_INVALID','测试用途、排程、公司或冻结Hash不一致。')
    p=source['product']
    if p['materialId']!=row.material_id or Decimal(p['quantity'])!=row.quantity or p['uomId']!=row.uom_id:fail('TEST_WORK_ORDER_PRODUCT_INVALID','产品数量或单位与冻结来源不一致。')
    operations=list(row.operations.order_by('sequence','pk'))
    if len(operations)!=len(source['operations']):fail('TEST_WORK_ORDER_OPERATIONS_INVALID','工序明细数量不完整。')
    for op,previous in zip(operations,source['operations']):
        if op.source_snapshot!=previous or op.snapshot_hash!=_hash(previous) or op.root_step_id!=previous['rootStepId'] or op.effective_step_id!=previous['effectiveStepId'] or op.root_routing_version_id!=previous['rootRoutingVersionId'] or op.effective_routing_version_id!=previous['effectiveRoutingVersionId'] or op.operation_id!=previous['operationId'] or op.work_center_id!=previous['workCenterId'] or op.workload_quantity!=previous['workloadQuantity'] or op.workload_uom_id!=previous['workloadUomId'] or op.sequence!=previous['sequence'] or op.dependency_only!=previous['dependencyOnly']:fail('TEST_WORK_ORDER_OPERATION_SOURCE_INVALID','工序、版本、独立作业量或单位被改写。')
    events=list(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=row.pk).order_by('version','pk'))
    pairs=[('','draft','planning.test_work_order.generate')]+([('draft','released','planning.test_work_order.release')] if row.status=='released' else [])
    if row.status not in ('draft','released') or row.version!=len(pairs)-1 or len(events)!=len(pairs):fail('TEST_WORK_ORDER_STATE_INVALID','生命周期状态与统一转换记录不一致。')
    for i,(event,pair) in enumerate(zip(events,pairs),1):
        aid=event.audit_reference.removeprefix('OrganizationOperatingAuditRecord:')
        audit=OrganizationOperatingAuditRecord.objects.filter(pk=aid,target_type=OBJECT,target_id=row.pk,organization_id=row.company_id,actor_id=event.operator_id,action_code=event.action_code).first()
        before=audit.before_snapshot if audit else {};after=audit.after_snapshot if audit else {};state=after.get('state',{});proof=state.get('actionPermissionDecision',{});native=after.get('authorization',{})
        if event.version!=i or (event.source_state,event.target_state,event.action_code)!=pair or before.get('state',{}).get('status')!=pair[0] or state.get('status')!=pair[1] or state.get('snapshotHash')!=row.snapshot_hash or proof.get('granted') is not True or proof.get('action',{}).get('moduleCode')!=MODULE or native.get('allowed') is not True or proof.get('action',{}).get('requiredPermission') not in native.get('permissionCodes',[]):fail('TEST_WORK_ORDER_AUDIT_INVALID','真实审计、操作人、状态及动作授权证明不一致。')
        if audit.reason.strip()!=event.reason or proof.get('action',{}).get('actionCode')!=('generate-test-work-order' if i==1 else 'release-test-work-order'):
            fail('TEST_WORK_ORDER_ACTION_HISTORY_INVALID','审计原因及动作与真实转换不一致。')
        if i>1:
            q=state.get('releaseQualification',{});actor=q.get('currentActorEvidence',{})
            node=after.get('workflowNode',{})
            if q.get('qualificationProven') is not True or actor.get('userId')!=event.operator_id or actor.get('companyId')!=row.company_id or node.get('nodeCode')!='PRODUCTION_WORK_ORDER_RELEASE' or node.get('processCode')!='MES_PRODUCTION_OPERATION' or node.get('nodeId')!=q.get('nodeId') or node.get('processId')!=q.get('definitionId'):
                fail('TEST_WORK_ORDER_RELEASE_PROOF_INVALID','下达岗位、流程节点或人员证明不完整。')
    if (row.status=='draft' and any((row.released_by_id,row.released_at,row.release_idempotency_key,row.release_request_hash)) or row.status=='released' and (not all((row.released_by_id,row.released_at,row.release_idempotency_key,row.release_request_hash)) or row.released_by_id!=events[-1].operator_id)):
        fail('TEST_WORK_ORDER_RELEASE_HISTORY_INVALID','下达字段与真实状态或操作人不一致。')
    if events[0].operator_id!=row.created_by_id:fail('TEST_WORK_ORDER_ACTOR_INVALID','生成操作人与转换记录不一致。')
    return operations,events

def present(row,current_source=None):
    ops,events=verify(row);s=row.source_snapshot
    return {'id':row.pk,'no':row.no,'purposeLabel':'测试用途（不得正式执行）','usagePurpose':row.usage_purpose,'statusLabel':'测试草稿（已生成，未下达）' if row.status=='draft' else '测试工单已下达（测试用途）','isDraft':row.status=='draft','version':row.version,'product':s['product'],'quantity':str(row.quantity),'uomLabel':s['product']['uomLabel'],'sourceScheduleId':row.source_schedule_id,'sourceScheduleNo':s['sourceSchedule']['scheduleNo'],'scope':s['scope'],'startAt':s['sourceSchedule']['startAt'],'completionAt':s['sourceSchedule']['completionAt'],'snapshotHash':row.snapshot_hash,'currentSourceValid':current_source is not None and s==current_source,'operationCount':len(ops),'skippedCount':sum(x['decision']=='NOT_APPLICABLE' for x in s['routeSelections']),'routeSelections':s['routeSelections'],'operations':[{'id':op.pk,**{k:v for k,v in op.source_snapshot.items() if k!='frozenStep'}} for op in ops],'stateTransitionHistory':[{'id':event.pk,'sourceState':event.source_state,'targetState':event.target_state,'actionCode':event.action_code,'version':event.version} for event in events],'statusTransitionCount':len(events),'stateMachineConsistent':True,'releaseAllowed':False,'formalManufacturingEligible':False}

def source_read_scope(function):
    """Memoize proofs only within this fresh DB read transaction, never across requests."""
    @wraps(function)
    def wrapped(*args,**kwargs):
        from pde.routing_read_context import _current
        token=_current.set({}) if _current.get() is None else None
        try:
            with transaction.atomic():return function(*args,**kwargs)
        finally:
            if token is not None:_current.reset(token)
    return wrapped

@source_read_scope
def read(*,user,arrangement_id,schedule_id,expected_snapshot_hash=None):
    actor=_actor(user);_arrangement(actor,arrangement_id)
    schedule=Schedule.objects.filter(pk=schedule_id,company_id=actor.company_id,execution_arrangement_id=arrangement_id,usage_purpose='TEST_BUSINESS').first()
    if not schedule:fail('SCOPE_DENIED','工单来源排程不属于当前公司和安排。')
    from .test_work_order_reception import _read_source
    row=WO.objects.filter(company_id=actor.company_id,source_schedule=schedule,usage_purpose='TEST_BUSINESS').first()
    try:base=_read_source(user=actor,arrangement_id=arrangement_id,schedule_id=schedule_id,expected_snapshot_hash=expected_snapshot_hash);source=source_for(base)
    except Exception as error:
        if row is None or not hasattr(error,'code') or error.code in ('SCOPE_DENIED','PERMISSION_DENIED','WORK_ORDER_SCHEDULE_VERSION_CHANGED'):raise
        current=present(row);s=row.source_snapshot
        return {'contractVersion':CONTRACT,'factSource':'server','requestIdentity':{'userId':actor.pk,'username':actor.username,'companyId':actor.company_id},'scope':s['scope'],'sourceSchedule':s['sourceSchedule'],'product':s['product'],'rows':s['routeSelections'],'workflow':s['workflowMetadata'],'workOrder':current,'canGenerate':False,'executionToken':None,'availableActions':[],'blockers':[str(error)],'statusLabel':'已生成测试工单保留历史；当前来源失效，禁止新增或下达','releaseAllowed':False,'databaseBusinessWriteCount':0}
    can_generate=not base['blockers'] and row is None
    try:decision(actor,schedule_id);permission=True;reason=''
    except Exception as e:permission=False;reason=str(e)
    rule=CodeRule.objects.filter(company_id=actor.company_id,entity_type=ENTITY).first()
    if rule is None:base['blockers'].append('测试工单编号目录尚未维护。')
    allowed=can_generate and permission and rule is not None
    base.update(workOrder=present(row,source) if row else None,canGenerate=allowed,executionToken=token(actor,source) if permission and not base['blockers'] else None,statusLabel=('测试工单已下达，车间接收独立核对' if row.status=='released' else '测试草稿工单已生成保存') if row else '测试来源已核验，可明确生成草稿工单',availableActions=[{'actionCode':ACTION,'displayName':'生成并保存测试草稿工单','moduleCode':MODULE,'requiredPermission':PERMISSION,'organizationScope':actor.company_id,'serverValidator':'planning.test_work_order_service.generate','executable':allowed,'disabledReason':reason or ('已有工单，直接查看持久记录。' if row else '；'.join(base['blockers']))}],releaseAllowed=False)
    if row:
        from .test_work_order_dispatch_service import read as read_dispatch
        base['dispatch']=read_dispatch(user=actor,work_order_id=row.pk)
        base['releaseAllowed']=any(x['executable'] for x in base['dispatch']['availableActions'])
        base['workOrder']['releaseAllowed']=base['releaseAllowed']
    return base

def generate(*,user,arrangement_id,schedule_id,payload):
    if not isinstance(payload,dict) or set(payload)!={'executionToken','idempotencyKey','reason'}:fail('WORK_ORDER_FIELDS_INVALID','只接受来源凭据、幂等键及操作说明，不接受公司、用途、数量或明细覆盖。')
    for key,limit in (('idempotencyKey',120),('reason',240)):
        if not isinstance(payload[key],str) or not payload[key].strip() or len(payload[key])>limit:fail('WORK_ORDER_INPUT_INVALID','幂等标识和操作说明不能为空或过长。')
    if not isinstance(payload['executionToken'],str) or not re.fullmatch('[0-9a-f]{64}',payload['executionToken']):fail('WORK_ORDER_TOKEN_REQUIRED','必须引用当前账号的服务端来源凭据。')
    actor=_actor(user);_boundary()
    request_hash=_hash({'arrangementId':arrangement_id,'scheduleId':schedule_id,**payload})
    def run():
        with transaction.atomic():
            _writer_lock(actor);fresh=_actor(actor);_arrangement(fresh,arrangement_id);auth=decision(fresh,schedule_id)
            from .test_work_order_reception import _read_source
            base=_read_source(user=fresh,arrangement_id=arrangement_id,schedule_id=schedule_id);source=source_for(base)
            if base['blockers']:fail('WORK_ORDER_STRUCTURE_INVALID','；'.join(base['blockers']))
            if payload['executionToken']!=token(fresh,source):fail('WORK_ORDER_SOURCE_CHANGED','排程、版本、产品数量或账号来源凭据已变化，请重新读取。')
            prior=WO.objects.filter(company_id=fresh.company_id,idempotency_key=payload['idempotencyKey']).first()
            if prior:
                if prior.source_schedule_id!=schedule_id or prior.request_hash!=request_hash or prior.source_snapshot!=source:fail('WORK_ORDER_IDEMPOTENCY_CONFLICT','幂等标识已用于其他来源或内容。')
                verify(prior);return prior.pk,True
            prior=WO.objects.filter(company_id=fresh.company_id,source_schedule_id=schedule_id,usage_purpose='TEST_BUSINESS').first()
            if prior:
                verify(prior)
                if prior.source_snapshot!=source:fail('WORK_ORDER_SOURCE_CHANGED','已有工单的来源已改变，不能换绑。')
                return prior.pk,True
            rule=CodeRule.objects.filter(company_id=fresh.company_id,entity_type=ENTITY).first()
            if rule is None or not rule.prefix or not 1<=rule.seq_length<=20 or rule.current_seq<0:fail('WORK_ORDER_NUMBER_RULE_REQUIRED','测试编号规则尚未通过正常维护。')
            number=CodeRule.next_code(company_id=fresh.company_id,entity_type=ENTITY)
            row=create_business_object_with_initial_state(model=WO,initial_state='draft',usage_purpose='TEST_BUSINESS',company_id=fresh.company_id,production_plan=None,source_schedule_id=schedule_id,no=number,material_id=source['product']['materialId'],quantity=Decimal(source['product']['quantity']),uom_id=source['product']['uomId'],source_snapshot=source,snapshot_hash=_hash(source),idempotency_key=payload['idempotencyKey'],request_hash=request_hash,created_by=fresh)
            for item in source['operations']:
                op=Operation(work_order=row,sequence=item['sequence'],root_step_id=item['rootStepId'],effective_step_id=item['effectiveStepId'],root_routing_version_id=item['rootRoutingVersionId'],effective_routing_version_id=item['effectiveRoutingVersionId'],operation_id=item['operationId'],work_center_id=item['workCenterId'],dependency_only=item['dependencyOnly'],workload_quantity=item['workloadQuantity'],workload_uom_id=item['workloadUomId'],source_snapshot=item,snapshot_hash=_hash(item));op.full_clean();op.save(force_insert=True)
            proof,native=auth
            audit=_audit(user=fresh,organization_id=fresh.company_id,action_code='planning.test_work_order.generate',instance=row,before={'status':''},after={'status':'draft','snapshotHash':row.snapshot_hash,'actionPermissionDecision':proof},reason=payload['reason'],authorization=native,execution_chain={'userId':fresh.pk,'purpose':'TEST_BUSINESS','boundary':'本轮仅生成草稿，不构成下达/执行批准'},audit_context={'workflowMetadata':source['workflowMetadata']})
            record_projected_business_transition(object_type=OBJECT,object_id=row.pk,source_state='',target_state='draft',action_code=audit.action_code,operator=fresh,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions=(('','draft'),))
            verify(row);return row.pk,False
    pk,repeated=_retry(run)
    return {'workOrderId':pk,'idempotent':repeated,'operationWrites':{'workOrderCreatedCount':0 if repeated else 1,'operationCreatedCount':0 if repeated else WO.objects.get(pk=pk).operations.count(),'numberSequenceAdvanceCount':0 if repeated else 1,'auditWriteCount':0 if repeated else 1,'stateTransitionWriteCount':0 if repeated else 1,'resourceOccupationWriteCount':0},'facts':read(user=actor,arrangement_id=arrangement_id,schedule_id=schedule_id)}

def deny_release(*,user,work_order_id):
    actor=_actor(user);row=WO.objects.filter(pk=work_order_id,company_id=actor.company_id).first()
    if row is None:fail('SCOPE_DENIED','工单不属于当前公司。')
    if row.usage_purpose=='TEST_BUSINESS':fail('TEST_WORK_ORDER_RELEASE_NOT_ENABLED','本轮只开放测试工单生成、保存和查看；下达及执行门禁关闭。')
    require_formal_work_order(row)
    fail('FORMAL_WORK_ORDER_NATIVE_ENTRY_REQUIRED','正式工单必须沿原正式准入及权限链办理。')
