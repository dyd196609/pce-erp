"""Isolated TEST branch of native immutable actual-start storage/protocol."""
from copy import deepcopy
from pathlib import Path
import os
from django.db import connection,transaction
from django.utils import timezone
from system.models import User
from masterdata.models import ExternalIdentity,MasterDataWriteRequest
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition
from pde.production_foundation_service import _audit
from pde.order_routing_execution_service import fail
from .scheduling_primitives import _hash,_writer_lock
from .test_scheduling_service import _actor,_retry
from .test_work_order_service import source_read_scope
from .operation_resource_read_scope import scoped_execution_read
from .operation_start_models import ProductionOperationStart as Start
from . import test_workshop_task_service as tasks
from . import test_operation_start_protocol as native
from .test_operation_predecessor_authority import predecessor_facts,route_nodes


def _boundary():
 tasks._boundary();declared=os.environ.get('PCE_TEST_OPERATION_START_DATABASE','')
 if os.environ.get('PCE_TEST_OPERATION_START_ISOLATED')!='1' or not declared or Path(declared).resolve()!=Path(connection.settings_dict['NAME']).resolve():fail('TEST_START_ISOLATION_REQUIRED','测试开工仅开放明确绑定的隔离数据库。')

def _source(task,context,current,problem):
 tasks.verify.validate_only(task);op=task.source_operation;center=op.work_center
 source_ok=bool(current and task.status=='dispatched' and context['source']==task.source_snapshot and context['receipt'].status=='received' and tasks._assignment(context,{'positionId':task.execution_position_id,'employeeId':task.execution_employee_id})==task.assignment_snapshot and native._effective(center,native._today()) and center.company_id==task.company_id and center.workshop_id==task.workshop_id)
 return {'ready':source_ok,'statusLabel':'真实测试工单、接收、派工、准确步骤及当前冻结来源一致' if source_ok else problem or '派工、来源版本、接收或当前人员资源不一致','snapshotHash':task.source_snapshot_hash,'receiptValid':context['receipt'].status=='received','currentSourceChecks':{'ready':source_ok,'authority':'planning.test_work_order_dispatch_service._fresh;planning.test_workshop_task_service.verify/_assignment','stepId':op.root_step_id},'missingItems':[] if source_ok else [problem or '来源核验未通过']}

def _read_context(actor,order,strict=False):
 groups,current,problem=tasks._context(actor,order,strict=strict)
 return {x['operation'].pk:x for g in groups.values() for x in g['rows']},current,problem

from .verified_read_memo import verified_model_read
@verified_model_read
def _verify(record,task):
 if task.work_order.usage_purpose!='TEST_BUSINESS' or record.source_snapshot.get('usagePurpose')!='TEST_BUSINESS':fail('TEST_START_PURPOSE_INVALID','开工必须沿真实测试父工单追溯用途。')
 tasks.verify.validate_only(task)
 fact=native._verify_record(record,task)
 from system.models import OrganizationOperatingAuditRecord
 entries=list(OrganizationOperatingAuditRecord.objects.filter(action_code='MES_TEST_BROWSER_AGENT_ATTESTATION',
  target_type='ProductionOperationStart',target_id=record.pk,organization_id=record.company_id))
 if entries:
  if len(entries)!=1:fail('TEST_AGENT_ATTESTATION_CONFLICT','测试代办来源注记不唯一，请核查；不改写开工历史。')
  audit=entries[0];state=audit.after_snapshot.get('state',{})
  agent=state.get('agent')
  if audit.actor_id!=record.started_by_id or state.get('originalStartId')!=record.pk or state.get('testAgentDelegation') is not True or not isinstance(agent,str) or not 1<=len(agent.strip())<=80:fail('TEST_AGENT_ATTESTATION_INVALID','测试代办来源注记与原办理账号或开工记录不一致。')
  fact['testAgentProvenance']={'statusLabel':f'本次隔离测试由{agent}依授权操作浏览器；用户仅完成登录，不代表用户本人点击。原开工说明及历史保留。','auditReference':f'OrganizationOperatingAuditRecord:{audit.pk}'}
 return fact

@scoped_execution_read
def read(*,user,work_order_id,own_only=False):
 actor=_actor(user);order=tasks.parent._order(actor,work_order_id)
 if not own_only:
  from pde.test_business_bom_service import authorize
  try:authorize(actor,'production.master_data.view',actor.company_id)
  except Exception as exc:
   if getattr(exc,'code','') not in ('PERMISSION_DENIED','SCOPE_DENIED','ORGANIZATION_MISMATCH','ROLE_REQUIRED','ACTION_NOT_GRANTED'):raise
   own_only=True
 employee,position,department,workshop,_,_=native._identity(actor)
 whole=tasks.parent.protocol._whole_readable(actor,order)
 own_read=native.receipt_service._authority(actor,native.READ_PERMISSION,workshop.department_id if workshop else None,actor.pk)[0]
 if not whole and not own_read:fail('PERMISSION_DENIED','没有本公司工单查看或本人测试任务执行查看权限。')
 allowed_ids=None
 if own_only:
  from .test_assignee_entry import owned_tasks
  _,owned=owned_tasks(actor,order.source_schedule.execution_arrangement_id)
  allowed_ids={task.pk for task in owned if task.work_order_id==order.pk}
  if not allowed_ids:fail('SCOPE_DENIED','没有此工单资源范围内的本人任务。')
 contexts,current,problem=_read_context(actor,order);nodes=route_nodes(order);rows=[]
 for task in tasks.Task.objects.filter(work_order=order).select_related('work_order__source_schedule','source_operation__work_center','workshop','work_center','workload_uom','execution_employee','execution_position').order_by('source_operation__sequence'):
  if allowed_ids is not None and task.pk not in allowed_ids:continue
  if not whole and not native._owned(actor,task,employee):continue
  source=_source(task,contexts[task.source_operation_id],current,problem);pred=predecessor_facts(task,nodes);record=Start.objects.filter(task=task).first();execution=_verify(record,task) if record else None
  owner=_actor(User.objects.get(pk=task.assignment_snapshot['userId']));assigned_q=native._qualification(owner,task,source,pred,state='started' if record else 'waiting');viewer_q=native._qualification(actor,task,source,pred,state='started' if record else 'waiting')
  op=task.source_snapshot['operation'];action={'actionCode':'start-test-operation','displayName':'本人测试开工','executable':viewer_q['ready'],'disabledReason':'；'.join(viewer_q['missingItems'])}
  rows.append({'taskId':task.pk,'taskNo':task.no,'operationId':task.source_operation_id,'operationName':op['operationName'],'sequence':op['sequence'],'stepId':op['rootStepId'],'workshopName':task.workshop.name,'workCenterName':task.work_center.name,'employeeName':task.assignment_snapshot['employeeName'],'username':task.assignment_snapshot['username'],'positionName':task.assignment_snapshot['positionName'],'planStart':op['start'],'planEnd':op['end'],'execution':execution,'statusLabel':'已测试开工' if execution else '待开工','dispatchStatusLabel':'已派工（原任务保持）','predecessors':pred,'sourceValid':source['ready'],'sourceProblem':source['statusLabel'],'assigneeReady':assigned_q['ready'],'assigneeBlockers':assigned_q['missingItems'],'availableAction':action,'version':task.version,'sourceSnapshotHash':task.source_snapshot_hash,'assignmentHash':task.assignment_hash,'statusTransitionHistory':execution['statusTransitionHistory'] if execution else [],'statusTransitionCount':execution['statusTransitionCount'] if execution else 0})
 return {'contractVersion':native.CONTRACT,'factSource':'server','currentStateSource':'server','requestIdentity':{'userId':actor.pk,'username':actor.username,'companyId':actor.company_id},'workOrderId':order.pk,'workOrderNo':order.no,'workOrderStatusLabel':tasks.parent.wo.present(order)['statusLabel'],'scheduleStatusLabel':tasks.present_schedule(order.source_schedule)['statusLabel'],'scope':order.source_snapshot['scope'],'usagePurpose':'TEST_BUSINESS','purposeLabel':'测试用途（不具备正式制造资格）','currentSourceValid':current,'rows':rows,'summary':{'tasks':len(rows),'started':sum(x['execution'] is not None for x in rows),'waiting':sum(x['execution'] is None for x in rows),'predecessorBlocked':sum(not x['predecessors']['ready'] for x in rows)},'timePolicyLabel':'沿原生开工规则记录服务器当前实际时间；计划时间仅作对照，不复制为实际时间。原生协议未以计划开始日作为禁早门禁。','formalManufacturingEligible':False,'reportOrCompletionSupported':True,'mesNavigation':{'report':{'label':'本人分次报工','route':'/planning/operation-reports'},'completion':{'label':'完工申请与独立审核','route':'/planning/operation-completions'},'handover':{'label':'产出与工序交接','route':'/planning/operation-handovers'}}}

def start(*,user,task_id,payload):
 native._payload(payload)
 if type(task_id) is not int or task_id<=0:fail('TEST_START_TASK_ID_REQUIRED','须指定真实任务身份。')
 actor=_actor(user);_boundary()
 @source_read_scope
 def run():
  with transaction.atomic():
   _writer_lock(actor);fresh=_actor(actor);task=tasks.Task.objects.select_for_update().select_related('work_order__source_schedule','source_operation__work_center','workshop','work_center','workload_uom').filter(pk=task_id,company_id=fresh.company_id).first()
   if task is None:fail('SCOPE_DENIED','任务不存在或越公司。')
   order=tasks.parent._order(fresh,task.work_order_id);contexts,current,problem=_read_context(fresh,order,True);source=_source(task,contexts[task.source_operation_id],current,problem);pred=predecessor_facts(task)
   if task.version!=payload['expectedVersion'] or task.source_snapshot_hash!=payload['expectedSourceSnapshotHash'] or task.assignment_hash!=payload['expectedAssignmentHash']:fail('TEST_START_SOURCE_CHANGED','任务版本、冻结来源或执行人员凭据已改变。')
   q=native._qualification(fresh,task,source,pred,state='waiting')
   if not q['ready']:fail('TEST_START_NOT_READY','；'.join(q['missingItems']))
   rh,old=native._intent(fresh,task_id,payload);record=Start.objects.filter(task=task).first()
   if record:
    result=_verify(record,task)
    if old and int(old.target_entity_id)!=record.pk:fail('TEST_START_LEDGER_CONFLICT','账本未指向当前开工。')
    return {'idempotent':True,'createdCount':0,'execution':result}
   if old:fail('TEST_START_LEDGER_CONFLICT','账本未对应真实开工记录。')
   now=timezone.now()
   if task.dispatched_at is None or now<task.dispatched_at:fail('TEST_START_TIME_INVALID','实际开工不得早于派工实际保存时间。')
   q['timeEvidence']={'source':'DJANGO_SERVER_TIMEZONE_NOW','simulated':False,'planStart':task.source_snapshot['operation']['start'],'actualStart':now.isoformat(),'testAgentDelegation':payload['reason'].startswith('CODEX隔离测试代办：')}
   record=create_business_object_with_initial_state(model=Start,initial_state='started',company_id=task.company_id,task=task,work_order_id=task.work_order_id,receipt_id=task.receipt_id,source_operation_id=task.source_operation_id,workshop_id=task.workshop_id,work_center_id=task.work_center_id,execution_mode=task.execution_mode,workload_quantity=task.workload_quantity,workload_uom_id=task.workload_uom_id,task_version=task.version,source_snapshot=deepcopy(task.source_snapshot),source_snapshot_hash=task.source_snapshot_hash,assignment_snapshot=deepcopy(task.assignment_snapshot),assignment_hash=task.assignment_hash,execution_position_id=task.execution_position_id,execution_employee_id=task.execution_employee_id,started_by=fresh,started_at=now,start_qualification=deepcopy(q),reason=payload['reason'].strip())
   audit=_audit(user=fresh,organization_id=task.company_id,action_code=native.START_ACTION,instance=record,before={'status':''},after=native._state(record),reason=record.reason,authorization=q['authorization'],execution_chain={'userId':fresh.pk,'usagePurpose':'TEST_BUSINESS','sourceTaskId':task.pk,'actualStartOnly':True,'timeEvidence':q['timeEvidence']})
   node={'processCode':native.PROCESS,'nodeCode':native.WORKFLOW_NODE,'processId':q['definitionId'],'nodeId':q['nodeId']}
   audit.before_snapshot['workflowNode']=node;audit.after_snapshot['workflowNode']=node;audit.save(update_fields=['before_snapshot','after_snapshot'])
   record_projected_business_transition(object_type=native.OBJECT,object_id=record.pk,source_state='',target_state='started',action_code=native.START_ACTION,operator=fresh,reason=record.reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','started')})
   identity,created=ExternalIdentity.objects.get_or_create(organization_id=task.company_id,source_system='MES_TEST_OPERATION_START',source_type='INTERNAL',source_object_type='ProductionWorkshopTask',external_id=str(task.pk),target_entity_type=native.OBJECT,defaults={'target_entity_id':str(record.pk),'mapping_status':'MATCH','source_fingerprint':task.source_snapshot_hash,'audit_metadata':{'actualStartOnly':True,'usagePurpose':'TEST_BUSINESS'}})
   if not created:fail('TEST_START_LEDGER_CONFLICT','来源身份已有冲突。')
   MasterDataWriteRequest.objects.create(organization_id=task.company_id,action_code=native.START_ACTION,entity_type=native.OBJECT,idempotency_key=payload['idempotencyKey'],request_hash=rh,source_identity=identity,status='COMMITTED',target_entity_id=str(record.pk),result={'taskId':task.pk,'operationStartId':record.pk},audit_metadata={'actorId':fresh.pk,'usagePurpose':'TEST_BUSINESS','actualStartOnly':True})
   return {'idempotent':False,'createdCount':1,'execution':_verify(record,task)}
 return _retry(run)
