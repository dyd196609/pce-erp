"""Explicit isolated TEST release/reception; uses native MES protocol and storage."""
from copy import deepcopy
from django.db import transaction
from django.utils import timezone
from system.models import User,PositionResponsibility,PositionWorkflowResponsibility,Permission
from workflow_runtime.models import ProcessDefinition
from workflow_runtime.action_permissions import ActionPermissionPolicy,ActionPermissionValidator,POLICIES
from workflow_runtime.state_transitions import transition_business_object,create_business_object_with_initial_state,record_projected_business_transition
from pde.production_foundation_service import _audit
from pde.order_routing_execution_service import fail
from . import test_work_order_service as wo
from . import workshop_receipt_protocol as protocol
from .work_order_workshop_receipt_models import ProductionWorkOrderWorkshopReceipt as Receipt
from .work_order_models import ProductionWorkOrder as WO
from .scheduling_primitives import _hash,_writer_lock
from .test_scheduling_service import _actor,_retry

RELEASE='planning.test_work_order.release'
RECEIVE=protocol.ACTION
RELEASE_PERMISSION='production.order.release'
MODULE=wo.MODULE

def _order(actor,pk):
 row=WO.objects.filter(pk=pk,company_id=actor.company_id,usage_purpose='TEST_BUSINESS').select_related('source_schedule').first()
 if not row:fail('SCOPE_DENIED','仅允许本公司真实测试工单，不能伪造用途选择分支。')
 wo.verify.validate_only(row)
 return row

def _fresh(actor,row):
 from django.db import connection
 from pde.routing_read_context import _current
 cache=_current.get();cache_key=None
 if cache is not None and connection.vendor=='sqlite':
  connection.ensure_connection()
  with connection.cursor() as cursor:
   cursor.execute('PRAGMA data_version');epoch=cursor.fetchone()[0]
  cache_key=('test_work_order_fresh',actor.company_id,row.pk,row.snapshot_hash,id(connection.connection),connection.connection.total_changes,epoch)
  if cache_key in cache:return deepcopy(cache[cache_key])
 from .test_work_order_reception import _read_source
 # Internal dependency proof uses the persisted source custodian, never a caller
 # selected identity. Receipt authority remains the current actor's exact workshop
 # qualification; this grants no master-data permission to receiving employees.
 source_custodian=_actor(row.created_by)
 if source_custodian.company_id!=actor.company_id:fail('SCOPE_DENIED','来源保管人与当前公司不一致。')
 from pde.routing_read_context import _current
 memo_token=_current.set({}) if _current.get() is None else None
 try:
  base=_read_source(user=source_custodian,arrangement_id=row.source_snapshot['scope']['arrangementId'],schedule_id=row.source_schedule_id)
 finally:
  if memo_token is not None:_current.reset(memo_token)
 if base['blockers'] or wo.source_for(base)!=row.source_snapshot:fail('TEST_WORK_ORDER_SOURCE_CHANGED','当前排程、安排修订、需求、数量或日期与冻结来源不一致。')
 from .test_scheduling_service import verify
 parts=verify(row.source_schedule)
 if not parts or any(p.released_at for p in parts):fail('TEST_WORK_ORDER_OCCUPATION_INVALID','来源排程有效占用不完整或已释放。')
 if cache_key is not None:cache[cache_key]=deepcopy(base)
 return base

def _release_qualification(actor,row):
 employee,position,department,_,evidence=protocol._employees(actor)
 today=(timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date())
 process=ProcessDefinition.objects.filter(definition_code=protocol.PROCESS,active=True,document_type='ProductionWorkOrder').first()
 node=process.nodes.filter(node_code='PRODUCTION_WORK_ORDER_RELEASE',active=True,business_action_code=RELEASE_PERMISSION).first() if process else None
 valid=bool(employee and protocol._effective(position,today) and protocol._effective(department,today) and position.department_id==department.pk and position.company_id==department.company_id==actor.company_id and (employee.hire_date is None or employee.hire_date<=today) and (employee.leave_date is None or employee.leave_date>today) and (employee.resignation_date is None or employee.resignation_date>today))
 duties=list(PositionResponsibility.objects.filter(position=position,active=True,responsibility__code='RESP_PMC_PLAN_001',responsibility__status='ACTIVE',responsibility__is_active=True).select_related('responsibility')) if valid else []
 duty=duties[0] if len(duties)==1 and protocol._effective(duties[0].responsibility,today) else None
 mappings=list(PositionWorkflowResponsibility.objects.filter(position=position,responsibility=duty.responsibility,workflow_node=node,workflow_code=protocol.PROCESS,node_code='PRODUCTION_WORK_ORDER_RELEASE',ownership_type='OWNER',active=True)) if duty and node else []
 mapping=mappings[0] if len(mappings)==1 and protocol._effective(mappings[0],today) else None
 allowed,matched,native=protocol._authority(actor,RELEASE_PERMISSION,department.pk if department else None,row.created_by_id)
 roles=tuple(protocol.RolePermission.objects.filter(permission__code=RELEASE_PERMISSION).order_by('role__code').values_list('role__code',flat=True).distinct())
 POLICIES[(MODULE,'release-test-work-order')]=ActionPermissionPolicy('release-test-work-order',MODULE,RELEASE_PERMISSION,roles,'legal_entity','planning.test_work_order_dispatch_service.release',('draft','released'),'single')
 class Facts:
  def read(self,module_code,object_ids):return {'found':module_code==MODULE and object_ids==[str(row.pk)],'objectIds':[str(row.pk)],'statuses':[row.status],'legalEntityIds':[str(row.company_id)],'currentStateSource':'server'}
 decision=ActionPermissionValidator(fact_provider=Facts()).evaluate(user=actor,module_code=MODULE,action_code='release-test-work-order',object_ids=[row.pk],selection_count=1,requested_legal_entity_id=str(actor.company_id))
 ready=bool(valid and duty and mapping and node and Permission.objects.filter(code=RELEASE_PERMISSION).exists() and allowed and decision['granted'])
 evidence.update(positionResponsibilityId=duty.pk if duty else None,workflowResponsibilityId=mapping.pk if mapping else None,matchedAuthorityEvidence=matched)
 return {'ready':ready,'qualificationProven':ready,'currentActorEvidence':evidence,'definitionId':process.pk if process else None,'nodeId':node.pk if node else None,'nativeDecision':native,'actionPermissionDecision':decision,'statusLabel':'当前岗位可测试下达' if ready else '当前岗位下达职责或明确权限不足'}

def _groups(row):
 ops,_=wo.verify(row);groups={}
 for op in ops:
  center=op.work_center;workshop=center.workshop if center else None
  if not workshop or not center.is_active or not workshop.is_active or center.company_id!=row.company_id or workshop.company_id!=row.company_id or not protocol._effective(center,(timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date())) or center.department_id and workshop.department_id and center.department_id!=workshop.department_id:
   fail('TEST_WORK_ORDER_WORKSHOP_INVALID','执行工序的工作中心、车间归属或效期不完整。')
  if any(v is not None and v!=workshop.pk for v in (op.source_snapshot.get('workshopId'),op.source_snapshot.get('frozenStep',{}).get('workshopId'))):fail('TEST_WORK_ORDER_WORKSHOP_CHANGED','工序冻结车间与当前归属冲突。')
  group=groups.setdefault(workshop.pk,{'workshop':workshop,'operations':[]})
  group['operations'].append({'operationId':op.pk,'operationSnapshotHash':op.snapshot_hash,'workCenterId':center.pk,'workCenterCompanyId':center.company_id,'workshopId':workshop.pk,'workshopDepartmentId':workshop.department_id,'source':deepcopy(op.source_snapshot)})
 return groups

def _source(row,group):
 w=group['workshop'];p=row.source_snapshot['product']
 return {'contractVersion':'PCE-TEST-WORKSHOP-RECEIPT-V1','usagePurpose':row.usage_purpose,'companyId':row.company_id,'workOrderId':row.pk,'workOrderNo':row.no,'productionPlanId':None,'workOrderVersion':row.version,'workOrderSnapshotHash':row.snapshot_hash,'quantity':str(row.quantity),'uomId':row.uom_id,'uomCode':row.uom.code,'uomLabel':p['uomLabel'],'workshopId':w.pk,'workshopCode':w.code,'workshopName':w.name,'workshopDepartmentId':w.department_id,'operations':group['operations']}

from .verified_read_memo import verified_model_read
@verified_model_read
def _receipt(row):
 if row is None:return protocol._legacy_receipt(None)
 parent=row.work_order
 if parent.usage_purpose!='TEST_BUSINESS' or row.company_id!=parent.company_id or row.source_snapshot.get('usagePurpose')!='TEST_BUSINESS' or parent.status!='released' or row.work_order_version!=parent.version or row.work_order_snapshot_hash!=parent.snapshot_hash:fail('TEST_RECEIPT_PARENT_INVALID','接收用途必须沿真实本公司已下达测试工单追溯。')
 wo.verify.validate_only(parent)
 return protocol._legacy_receipt(row)

def _eligible_receivers(row,group):
 from pfm.formal_employee import formal_employee_queryset
 ids=formal_employee_queryset(company_id=row.company_id).filter(position_ref__workshop=group['workshop'],user__is_active=True).values_list('user_id',flat=True).distinct()
 result=[]
 for actor in User.objects.filter(pk__in=ids,company_id=row.company_id,is_active=True):
  q,_=protocol._qualification(actor,row,group['workshop'],source_ok=True)
  if q['ready']:result.append({'userId':actor.pk,'username':actor.username,'employeeName':q['currentActorEvidence']['employeeName'],'positionName':q['currentActorEvidence']['positionName']})
 return result

def _release_token(actor,row,q):return _hash({'action':RELEASE,'actorId':actor.pk,'workOrderId':row.pk,'snapshotHash':row.snapshot_hash,'qualification':{k:q[k] for k in ('currentActorEvidence','definitionId','nodeId','nativeDecision')}})

@wo.source_read_scope
def read(*,user,work_order_id):
 actor=_actor(user);row=_order(actor,work_order_id)
 if not protocol._whole_readable(actor,row):fail('PERMISSION_DENIED','没有本公司工单查看权限。')
 current=True;problem=''
 try:_fresh(actor,row)
 except Exception as e:
  if not hasattr(e,'code'):raise
  current=False;problem=str(e)
 qualification=_release_qualification(actor,row);groups=_groups(row);scopes=[]
 for key,g in groups.items():
  receipt=Receipt.objects.filter(work_order=row,workshop_id=key).first();fact=_receipt(receipt)
  if receipt and receipt.source_snapshot!=_source(row,g):fail('TEST_RECEIPT_SCOPE_CHANGED','已接收范围与当前车间工序不一致。')
  candidates=_eligible_receivers(row,g)
  own_q,_=protocol._qualification(actor,row,g['workshop'],source_ok=current)
  own_ready=row.status=='released' and current and own_q['ready'] and not fact['received']
  own_action={'actionCode':'receive-test-workshop','displayName':'接收本车间测试工序','executable':own_ready,'executionToken':protocol._token(actor,_source(row,g),own_q) if own_ready else None}
  scopes.append({'workshopId':key,'workshopName':g['workshop'].name,'operationCount':len(g['operations']),'operations':[{'id':x['operationId'],**x['source']} for x in g['operations']],'receipt':fact,'availableAction':own_action,'candidates':candidates,'candidateStatusLabel':'唯一有效办理人' if len(candidates)==1 else '办理人缺失' if not candidates else '多个合法办理人，须选择','sourceHash':_hash(_source(row,g))})
 release_label=None
 if row.released_by_id:
  _,events=wo.verify(row)
  audit=protocol.OrganizationOperatingAuditRecord.objects.get(pk=events[-1].audit_reference.removeprefix('OrganizationOperatingAuditRecord:'))
  frozen_actor=audit.after_snapshot.get('state',{}).get('releaseQualification',{}).get('currentActorEvidence',{})
  release_label=frozen_actor.get('employeeName') or frozen_actor.get('username') or row.released_by.username
 ready=row.status=='draft' and current and qualification['ready']
 return {'factSource':'server','requestIdentity':{'userId':actor.pk,'username':actor.username,'companyId':actor.company_id},'workOrderId':row.pk,'workOrderNo':row.no,'usagePurpose':row.usage_purpose,'statusLabel':'测试工单已下达' if row.status=='released' else '测试草稿待下达','version':row.version,'snapshotHash':row.snapshot_hash,'currentSourceValid':current,'sourceProblem':problem,'releasedById':row.released_by_id,'releasedByLabel':release_label,'releasedAt':row.released_at.isoformat() if row.released_at else None,'scopes':scopes,'scopeCount':len(scopes),'receivedScopeCount':sum(x['receipt']['received'] for x in scopes),'remainingScopeCount':sum(not x['receipt']['received'] for x in scopes),'operationCount':sum(x['operationCount'] for x in scopes),'releaseQualification':qualification,'releaseToken':_release_token(actor,row,qualification) if current and qualification['ready'] else None,'availableActions':[{'actionCode':'release-test-work-order','displayName':'下达测试工单','executable':ready,'disabledReason':'' if ready else '已下达或来源、职责不满足'}],'formalManufacturingEligible':False,'dispatchAllowed':False,'startAllowed':False,'reportAllowed':False,'businessWriteCount':0}

def _payload(payload,fields):
 if not isinstance(payload,dict) or set(payload)!=fields:fail('TEST_DISPATCH_FIELDS_INVALID','请求仅接受当前凭据、版本、幂等标识和办理说明，不接受用途、公司或身份覆盖。')
 for key in ('idempotencyKey','reason'):
  if not isinstance(payload[key],str) or not payload[key].strip() or len(payload[key])>(120 if key=='idempotencyKey' else 240):fail('TEST_DISPATCH_INPUT_INVALID','办理说明和幂等标识必须有效。')

def release(*,user,work_order_id,payload):
 _payload(payload,{'expectedVersion','executionToken','idempotencyKey','reason'});actor=_actor(user);wo._boundary()
 def run():
  with transaction.atomic():
   _writer_lock(actor);fresh=_actor(actor);row=_order(fresh,work_order_id);_fresh(fresh,row);_groups(row);q=_release_qualification(fresh,row)
   if not q['ready']:fail('TEST_RELEASE_QUALIFICATION_REQUIRED',q['statusLabel'])
   if payload['executionToken']!=_release_token(fresh,row,q):fail('TEST_RELEASE_SOURCE_CHANGED','来源、账号或职责凭据已改变。')
   request_hash=_hash({'actorId':fresh.pk,'workOrderId':row.pk,**payload})
   if row.status=='released':
    if row.release_request_hash==request_hash or (payload['expectedVersion']==row.version-1 and row.released_by_id==fresh.pk):return True
    fail('TEST_RELEASE_ALREADY_RELEASED','已下达，不能再次形成下达记录。')
   if payload['executionToken']!=_release_token(fresh,row,q):fail('TEST_RELEASE_SOURCE_CHANGED','来源、账号或职责凭据已改变。')
   if type(payload['expectedVersion']) is not int or row.version!=payload['expectedVersion']:fail('TEST_RELEASE_VERSION_CHANGED','工单版本已变化。')
   node={'processId':q['definitionId'],'processCode':protocol.PROCESS,'nodeId':q['nodeId'],'nodeCode':'PRODUCTION_WORK_ORDER_RELEASE'}
   audit=_audit(user=fresh,organization_id=row.company_id,action_code=RELEASE,instance=row,before={'status':'draft'},after={'status':'released','snapshotHash':row.snapshot_hash,'actionPermissionDecision':q['actionPermissionDecision'],'releaseQualification':q},reason=payload['reason'],authorization=q['nativeDecision'],execution_chain={'userId':fresh.pk,'purpose':'TEST_BUSINESS','boundary':'仅测试下达，不派工开工报工'})
   for field in ('before_snapshot','after_snapshot'):getattr(audit,field)['workflowNode']=node
   audit.save(update_fields=['before_snapshot','after_snapshot'])
   row.release_idempotency_key=payload['idempotencyKey'];row.release_request_hash=request_hash;row.released_by=fresh;row.released_at=timezone.now();row.save(update_fields=['release_idempotency_key','release_request_hash','released_by','released_at','updated_at'])
   transition_business_object(business_object=row,object_type=wo.OBJECT,source_state='draft',target_state='released',action_code=RELEASE,operator=fresh,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('draft','released')})
   wo.verify.validate_only(row);return False
 repeated=_retry(run)
 return {'idempotent':repeated}

def receive(*,user,work_order_id,workshop_id,payload):
 protocol._payload(payload);actor=_actor(user);wo._boundary()
 def run():
  with transaction.atomic():
   _writer_lock(actor);fresh=_actor(actor);row=_order(fresh,work_order_id);_fresh(fresh,row)
   if row.status!='released':fail('TEST_RECEIPT_ORDER_NOT_RELEASED','测试工单尚未下达。')
   group=_groups(row).get(workshop_id)
   if not group or not protocol._readable(fresh,group['workshop'],row):fail('SCOPE_DENIED','无权查看本车间工序。')
   q,_=protocol._qualification(fresh,row,group['workshop'],source_ok=True)
   if not q['ready']:fail('TEST_RECEIPT_QUALIFICATION_REQUIRED',q['statusLabel'])
   source=_source(row,group)
   if payload['expectedWorkOrderVersion']!=row.version or payload['expectedWorkOrderSnapshotHash']!=row.snapshot_hash or payload['expectedScopeSnapshotHash']!=_hash(source) or payload['executionToken']!=protocol._token(fresh,source,q):fail('TEST_RECEIPT_SOURCE_CHANGED','工单版本、车间归属或当前办理资格已改变。')
   request_hash=_hash({'actorId':fresh.pk,'workOrderId':row.pk,'source':source,'payload':payload})
   prior=Receipt.objects.filter(company_id=fresh.company_id,idempotency_key=payload['idempotencyKey']).first()
   if prior and (prior.work_order_id!=row.pk or prior.workshop_id!=workshop_id or prior.request_hash!=request_hash):fail('TEST_RECEIPT_IDEMPOTENCY_CONFLICT','幂等标识已用于其他办理。')
   prior=prior or Receipt.objects.filter(work_order=row,workshop_id=workshop_id).first()
   if prior:
    _receipt(prior)
    if prior.source_snapshot!=source:fail('TEST_RECEIPT_SOURCE_CHANGED','原接收冻结范围不同。')
    return prior.pk,True
   receipt=create_business_object_with_initial_state(model=Receipt,initial_state='received',company_id=row.company_id,work_order=row,workshop_id=workshop_id,work_order_version=row.version,work_order_snapshot_hash=row.snapshot_hash,source_snapshot=source,snapshot_hash=_hash(source),qualification_snapshot=q,qualification_hash=_hash(q),idempotency_key=payload['idempotencyKey'],request_hash=request_hash,received_by=fresh)
   audit=_audit(user=fresh,organization_id=row.company_id,action_code=RECEIVE,instance=receipt,before={'status':''},after={'status':'received','snapshotHash':receipt.snapshot_hash,'receivingQualification':q},reason=payload['reason'],authorization=q['nativeDecision'],execution_chain={'userId':fresh.pk,'purpose':'TEST_BUSINESS','parentWorkOrderId':row.pk})
   node={'processId':q['definitionId'],'processCode':protocol.PROCESS,'nodeId':q['nodeId'],'nodeCode':protocol.WORKFLOW_NODE}
   for field in ('before_snapshot','after_snapshot'):getattr(audit,field)['workflowNode']=node
   audit.save(update_fields=['before_snapshot','after_snapshot'])
   record_projected_business_transition(object_type=protocol.OBJECT,object_id=receipt.pk,source_state='',target_state='received',action_code=RECEIVE,operator=fresh,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','received')})
   _receipt(receipt);return receipt.pk,False
 pk,repeated=_retry(run)
 return {'receiptId':pk,'idempotent':repeated}

def receive_payload(*,user,work_order_id,workshop_id,reason,idempotency_key):
 actor=_actor(user);row=_order(actor,work_order_id);_fresh(actor,row);group=_groups(row).get(workshop_id)
 if not group:fail('SCOPE_DENIED','工单不存在此车间范围。')
 q,_=protocol._qualification(actor,row,group['workshop'],source_ok=True)
 if not q['ready']:fail('TEST_RECEIPT_QUALIFICATION_REQUIRED',q['statusLabel'])
 s=_source(row,group)
 return {'expectedWorkOrderVersion':row.version,'expectedWorkOrderSnapshotHash':row.snapshot_hash,'expectedScopeSnapshotHash':_hash(s),'executionToken':protocol._token(actor,s,q),'idempotencyKey':idempotency_key,'reason':reason}
