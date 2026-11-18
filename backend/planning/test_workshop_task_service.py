"""Isolated TEST adapter to native workshop task storage, authority and state protocol."""
from copy import deepcopy
from decimal import Decimal
import os
from pathlib import Path
from django.db import connection,transaction
from django.utils import timezone
from system.models import User
from masterdata.models import CodeRule
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition,transition_business_object
from pde.production_foundation_service import _audit
from pde.order_routing_execution_service import fail
from . import test_workshop_task_protocol as native
from . import test_work_order_dispatch_service as parent
from .test_work_order_service import _boundary as work_order_boundary,source_read_scope
from .test_scheduling_service import _actor,_retry,_present as present_schedule
from .scheduling_primitives import _hash,_json,_writer_lock
from .workshop_task_models import ProductionWorkshopTask as Task
from .work_order_models import ProductionWorkOrderOperation
from .test_workshop_task_configuration import ENTITY

CONTRACT='PCE-TEST-WORKSHOP-TASK-V1'

def _boundary():
 work_order_boundary()
 declared=os.environ.get('PCE_TEST_TASK_DISPATCH_DATABASE','')
 if os.environ.get('PCE_TEST_TASK_DISPATCH_ISOLATED')!='1' or not declared or Path(declared).resolve()!=Path(connection.settings_dict['NAME']).resolve():fail('TEST_TASK_ISOLATION_REQUIRED','测试派工仅开放明确绑定的隔离数据库。')

def _source(order,operation,receipt):
 return {'contractVersion':CONTRACT,'usagePurpose':'TEST_BUSINESS','sourceAuthority':'SAVED_TEST_WORK_ORDER_AND_WORKSHOP_RECEIPT','companyId':order.company_id,'workOrderId':order.pk,'workOrderNo':order.no,'workOrderVersion':order.version,'workOrderSnapshotHash':order.snapshot_hash,'sourceScheduleId':order.source_schedule_id,'sourceScheduleHash':order.source_snapshot['sourceSchedule']['snapshotHash'],'arrangementScope':deepcopy(order.source_snapshot['scope']),'sourceOperationId':operation.pk,'sourceOperationSnapshotHash':operation.snapshot_hash,'receiptId':receipt.pk,'receiptSnapshotHash':receipt.snapshot_hash,'workshopId':receipt.workshop_id,'workCenterId':operation.work_center_id,'executionMode':'QUANTIFIED','operation':{**deepcopy(operation.source_snapshot),'workloadLabel':operation.workload_quantity+' '+operation.workload_uom.name}}

def _assignment(row,choice):
 positions,employees=row['positions'],row['employees']
 value,issues=native._assignment(choice['positionId'],choice['employeeId'],positions,employees)
 if issues:fail('TEST_TASK_RESOURCE_INVALID','；'.join(issues))
 position=next(p for p in row['positionObjects'] if p.pk==choice['positionId'])
 proof=native.executor_scope(position,company_id=row['order'].company_id,workshop_id=row['workshop'].pk,operation_id=row['operation'].operation_id,work_center_id=row['operation'].work_center_id)
 if not proof['ready']:fail('TEST_TASK_RESOURCE_SCOPE_INVALID',proof['statusLabel'])
 value['executorScope']=proof
 return value

from .verified_read_memo import verified_model_read
@verified_model_read
def verify(task):
 if task.work_order.usage_purpose=='PRODUCTION_USE':
  from .workshop_task_service import _verify_history
  return _verify_history(task)
 if task.work_order.usage_purpose!='TEST_BUSINESS' or task.source_snapshot.get('usagePurpose')!='TEST_BUSINESS' or task.work_order.production_plan_id is not None or task.company_id!=task.work_order.company_id or task.receipt.company_id!=task.company_id or task.receipt.work_order_id!=task.work_order_id or task.receipt.workshop_id!=task.workshop_id or task.source_operation.work_order_id!=task.work_order_id:fail('TEST_TASK_PARENT_INVALID','测试用途、父工单、接收和工序来源身份不一致。')
 parent._receipt(task.receipt)
 if task.work_order.status!='released' or task.work_order.version!=task.work_order_version or task.source_snapshot.get('workOrderSnapshotHash')!=task.work_order.snapshot_hash or task.source_snapshot.get('receiptSnapshotHash')!=task.receipt.snapshot_hash or task.source_snapshot.get('sourceOperationSnapshotHash')!=task.source_operation.snapshot_hash:fail('TEST_TASK_SOURCE_INVALID','父工单版本或冻结接收、工序来源被改写。')
 if not task.workload_uom.is_active or not Decimal(task.workload_quantity).is_finite() or Decimal(task.workload_quantity)<=0:fail('TEST_TASK_QUANTITY_INVALID','任务须保留有效正数作业量及单位。')
 return native._verify_history(task)

def _context(actor,order,*,strict=True):
 current=True;problem=''
 try:parent._fresh(actor,order)
 except Exception as error:
  if strict or not hasattr(error,'code'):raise
  current=False;problem=str(error)
 groups=parent._groups(order);result={}
 for wid,g in groups.items():
  receipt=parent.Receipt.objects.filter(work_order=order,workshop_id=wid).first()
  if receipt is None:fail('TEST_TASK_RECEIPT_REQUIRED','必须先保存本车间的真实接收记录。')
  parent._receipt(receipt)
  if receipt.source_snapshot!=parent._source(order,g):fail('TEST_TASK_RECEIPT_SCOPE_CHANGED','车间接收范围与当前工序不一致。')
  rows=[]
  for op in order.operations.filter(pk__in=[x['operationId'] for x in g['operations']]).select_related('operation','work_center','workload_uom').order_by('sequence','pk'):
   if op.dependency_only or op.workload_quantity is None or op.workload_uom_id is None or Decimal(op.workload_quantity)<=0 or op.workload_uom.company_id!=order.company_id or not op.workload_uom.is_active:fail('TEST_TASK_QUANTITY_SOURCE_REQUIRED','任务只能承接本工序有效正数作业量，不用产品数量或占用段数替代。')
   positions,employees=native._candidates(order.company_id,wid,op.operation_id,op.work_center_id)
   objects=list(native.Position.objects.filter(pk__in=[x['id'] for x in positions]).select_related('department','process','team'))
   rows.append({'order':order,'operation':op,'workshop':g['workshop'],'receipt':receipt,'source':_source(order,op,receipt),'positions':positions,'employees':employees,'positionObjects':objects})
  result[wid]={'workshop':g['workshop'],'receipt':receipt,'rows':rows}
 return result,current,problem

def _token(actor,order,group):
 sources=[{'source':x['source'],'positions':x['positions'],'employees':x['employees'],'executorProofs':[native.executor_scope(p,company_id=order.company_id,workshop_id=group['workshop'].pk,operation_id=x['operation'].operation_id,work_center_id=x['operation'].work_center_id) for p in x['positionObjects']]} for x in group['rows']]
 return _hash({'contract':CONTRACT,'actorId':actor.pk,'companyId':actor.company_id,'workOrderId':order.pk,'workOrderVersion':order.version,'sources':sources})

def _dispatchers(order,group):
 from pfm.formal_employee import formal_employee_queryset
 ids=formal_employee_queryset(company_id=order.company_id).filter(position_ref__workshop=group['workshop'],user__is_active=True).values_list('user_id',flat=True)
 found=[]
 for actor in User.objects.filter(pk__in=ids,company_id=order.company_id,is_active=True):
  q=native._dispatcher(actor,order,group['workshop'],native.SAVE_ACTION,group['rows'][0]['operation'].pk,'released')
  if q['ready']:found.append({'userId':actor.pk,**q['currentActorEvidence']})
 return found

@source_read_scope
def read(*,user,work_order_id):
 actor=_actor(user);order=parent._order(actor,work_order_id)
 if not parent.protocol._whole_readable(actor,order):fail('PERMISSION_DENIED','没有本公司工单及车间任务查看权限。')
 groups,current,problem=_context(actor,order,strict=False);presented=[]
 for wid,g in groups.items():
  rows=[]
  for row in g['rows']:
   op=row['operation'];task=Task.objects.filter(source_operation=op).first();task_view=None
   if task:
    history=verify(task);task_view={'id':task.pk,'no':task.no,'statusLabel':native.STATUS[task.status],'dispatched':task.status=='dispatched','version':task.version,'quantity':task.workload_quantity,'unitLabel':task.workload_uom.name,'positionName':task.assignment_snapshot['positionName'],'employeeName':task.assignment_snapshot['employeeName'],'employeeId':task.execution_employee_id,'dispatchedByLabel':task.dispatch_qualification.get('currentActorEvidence',{}).get('employeeName'),'dispatchedAt':task.dispatched_at.isoformat() if task.dispatched_at else None,'usagePurpose':'TEST_BUSINESS','sourceHash':task.source_snapshot_hash,'stateTransitionCount':len(history),'statusTransitionHistory':history,'stateMachineConsistent':True}
   choice={'positionId':row['employees'][0]['positionId'],'employeeId':row['employees'][0]['id']} if len(row['employees'])==1 else None
   valid_task=bool(task and current and task.source_snapshot==row['source'])
   if valid_task:
    try:valid_task=_assignment(row,{'positionId':task.execution_position_id,'employeeId':task.execution_employee_id})==task.assignment_snapshot
    except Exception as e:
     if not hasattr(e,'code'):raise
     valid_task=False
   assigned=Decimal(task.workload_quantity) if task and task.status=='dispatched' and valid_task else Decimal('0')
   total=Decimal(op.workload_quantity)
   if assigned>total:fail('TEST_TASK_OVERALLOCATED','已派工量超过本工序有效需求。')
   rows.append({'operationId':op.pk,'stepId':op.root_step_id,'sequence':op.sequence,'operationName':op.operation.name,'workCenterId':op.work_center_id,'workCenterName':op.work_center.name,'quantity':op.workload_quantity,'unitLabel':op.workload_uom.name,'assignedQuantity':str(assigned) if current and (not task or valid_task) else None,'remainingQuantity':str(total-assigned) if current and (not task or valid_task) else None,'start':op.source_snapshot['start'],'end':op.source_snapshot['end'],'candidates':row['employees'],'candidatePositions':row['positions'],'autoChoice':choice,'candidateLabel':'唯一有效岗位及员工' if choice else '缺少有效员工/岗位绑定' if not row['employees'] else '多个合法人员，须集中选择','task':task_view,'currentTaskValid':valid_task,'statusLabel':'已派工' if task and task.status=='dispatched' and valid_task else '历史任务来源已失效' if task else '未派工'})
  q=native._dispatcher(actor,order,g['workshop'],native.SAVE_ACTION,g['rows'][0]['operation'].pk,'released')
  executors=_dispatchers(order,g)
  presented.append({'workshopId':wid,'workshopName':g['workshop'].name,'receiptId':g['receipt'].pk,'rows':rows,'dispatchers':executors,'sourceToken':_token(actor,order,g) if current and q['ready'] else None,'availableAction':{'actionCode':'dispatch-test-workshop-tasks','displayName':'保存并派工本车间测试任务','executable':current and q['ready'] and any(x['task'] is None and x['autoChoice'] for x in rows),'disabledReason':q['statusLabel']},'dispatchedOperationCount':sum(x['task'] is not None and x['task']['dispatched'] and x['currentTaskValid'] for x in rows)})
 flat=[x for g in presented for x in g['rows']]
 from pde.models import Equipment
 equipment=[{'id':x.pk,'name':x.name,'workCenterId':x.work_center_id} for x in Equipment.objects.filter(work_center_id__in=[x['workCenterId'] for x in flat],is_active=True).select_related('work_center') if parent.protocol._effective(x,timezone.now().date()) and x.work_center.company_id==order.company_id]
 return {'contractVersion':CONTRACT,'factSource':'server','requestIdentity':{'userId':actor.pk,'username':actor.username,'companyId':actor.company_id},'workOrderId':order.pk,'workOrderNo':order.no,'workOrderStatusLabel':parent.wo.present(order)['statusLabel'],'scheduleStatusLabel':present_schedule(order.source_schedule)['statusLabel'],'scope':order.source_snapshot['scope'],'purposeLabel':'测试用途（不具备正式制造资格）','currentSourceValid':current,'sourceProblem':problem,'groups':presented,'summary':{'executingOperations':len(flat),'taskCount':sum(x['task'] is not None for x in flat),'dispatchedOperations':sum(x['task'] is not None and x['task']['dispatched'] and x['currentTaskValid'] for x in flat),'remainingOperations':sum(not (x['task'] is not None and x['task']['dispatched'] and x['currentTaskValid']) for x in flat)},'equipmentCandidates':equipment,'equipmentCount':len(equipment),'resourcePolicyLabel':'按各工序有效岗位与员工派工，班组能力按既有工作中心关联核验；本轮人员任务不新增设备预占或开工资格。','actualStartCount':0,'actualReportCount':0,'formalManufacturingEligible':False}

def _audit_task(actor,task,action,before,q,reason,target,version):
 audit=_audit(user=actor,organization_id=task.company_id,action_code=action,instance=task,before=before,after={**native._state(task),'status':target,'version':version},reason=reason,authorization=q['authorization'],execution_chain={'userId':actor.pk,'usagePurpose':'TEST_BUSINESS','sourceWorkOrderId':task.work_order_id,'receiptId':task.receipt_id,'boundary':'仅保存及测试派工，不开工不报工'})
 node={'processCode':native.PROCESS,'nodeCode':native.WORKFLOW_NODE,'processId':q['definitionId'],'nodeId':q['nodeId']}
 for key in ('before_snapshot','after_snapshot'):getattr(audit,key)['workflowNode']=node
 audit.save(update_fields=['before_snapshot','after_snapshot']);return audit

def dispatch(*,user,work_order_id,workshop_id,payload):
 expected={'sourceToken','assignments','reason','idempotencyKey'}
 if not isinstance(payload,dict) or set(payload)!=expected or not isinstance(payload['assignments'],list) or not payload['assignments']:fail('TEST_TASK_FIELDS_INVALID','只接受当前来源凭据、工序人员选择、原因及幂等标识，不接受公司、用途、数量或日期覆盖。')
 if not isinstance(payload['reason'],str) or not 2<=len(payload['reason'].strip())<=240 or not isinstance(payload['idempotencyKey'],str) or not 1<=len(payload['idempotencyKey'])<=70:fail('TEST_TASK_INPUT_INVALID','操作说明或幂等标识无效。')
 if any(not isinstance(x,dict) or set(x)!={'operationId','positionId','employeeId'} or any(type(v) is not int or v<=0 for v in x.values()) for x in payload['assignments']):fail('TEST_TASK_ASSIGNEE_INVALID','请选择真实工序、岗位及有效员工。')
 if len({x['operationId'] for x in payload['assignments']})!=len(payload['assignments']):fail('TEST_TASK_DUPLICATE_OPERATION','同批不能重复提交同一工序。')
 actor=_actor(user);_boundary()
 def run():
  with transaction.atomic():
   _writer_lock(actor);fresh=_actor(actor);order=parent._order(fresh,work_order_id);groups,current,_=_context(fresh,order);g=groups.get(workshop_id)
   if not g or order.status!='released':fail('SCOPE_DENIED','须指定已下达工单已接收的真实车间。')
   q=native._dispatcher(fresh,order,g['workshop'],native.SAVE_ACTION,g['rows'][0]['operation'].pk,'released')
   if not q['ready']:fail('TEST_TASK_DISPATCHER_UNQUALIFIED','；'.join(q['missingItems']))
   if payload['sourceToken']!=_token(fresh,order,g):fail('TEST_TASK_SOURCE_CHANGED','来源、岗位、班组能力或人员凭据已改变，请重新读取。')
   by_id={x['operation'].pk:x for x in g['rows']};results=[]
   for choice in payload['assignments']:
    context=by_id.get(choice['operationId'])
    if context is None:fail('TEST_TASK_WRONG_WORKSHOP','工序不属于当前车间已接收范围。')
    assignment=_assignment(context,choice);op=context['operation'];source=context['source']
    save_payload={'idempotencyKey':payload['idempotencyKey']+':'+str(op.pk)+':save','reason':payload['reason'],'sourceHash':_hash(source)}
    rh,old=native._intent(fresh,native.SAVE_ACTION,save_payload)
    task=Task.objects.filter(source_operation=op).first()
    if task:
     verify(task)
     if old and int(old.target_entity_id)!=task.pk:fail('TEST_TASK_LEDGER_SOURCE_CONFLICT','重复凭据对应了另一任务。')
     if task.source_snapshot!=source or task.assignment_snapshot!=assignment or task.status!='dispatched':fail('TEST_TASK_EXISTING_CONFLICT','该工序已有不同来源、不同分派或未完成的任务，不能覆盖。')
     results.append({'taskId':task.pk,'created':False});continue
    rule=CodeRule.objects.filter(company_id=order.company_id,entity_type=ENTITY).first()
    if rule is None:fail('TEST_TASK_NUMBER_RULE_REQUIRED','测试任务编号尚未正常维护。')
    task=create_business_object_with_initial_state(model=Task,initial_state='draft',company_id=order.company_id,no=CodeRule.next_code(company_id=order.company_id,entity_type=ENTITY),work_order=order,receipt=context['receipt'],source_operation=op,workshop=g['workshop'],work_center=op.work_center,execution_mode='QUANTIFIED',workload_quantity=op.workload_quantity,workload_uom=op.workload_uom,work_order_version=order.version,source_snapshot=source,source_snapshot_hash=_hash(source),execution_position_id=choice['positionId'],execution_employee_id=choice['employeeId'],assignment_snapshot=assignment,assignment_hash=_hash(assignment),created_by=fresh)
    if old:fail('TEST_TASK_LEDGER_REPLAY_CONFLICT','已提交账本未对应有效任务。')
    audit=_audit_task(fresh,task,native.SAVE_ACTION,{'status':''},q,payload['reason'],'draft',0)
    record_projected_business_transition(object_type=native.OBJECT,object_id=task.pk,source_state='',target_state='draft',action_code=native.SAVE_ACTION,operator=fresh,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','draft')})
    native._ledger(fresh,native.SAVE_ACTION,save_payload,rh,task);verify(task)
    dq=native._dispatcher(fresh,order,g['workshop'],native.DISPATCH_ACTION,task.pk,'draft')
    if not dq['ready']:fail('TEST_TASK_DISPATCHER_UNQUALIFIED','；'.join(dq['missingItems']))
    before=native._state(task);task.dispatched_by=fresh;task.dispatched_at=timezone.now();task.dispatch_qualification=dq;task.save(update_fields=['dispatched_by','dispatched_at','dispatch_qualification','updated_at'])
    audit=_audit_task(fresh,task,native.DISPATCH_ACTION,before,dq,payload['reason'],'dispatched',1)
    transition_business_object(business_object=task,object_type=native.OBJECT,source_state='draft',target_state='dispatched',action_code=native.DISPATCH_ACTION,operator=fresh,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('draft','dispatched')})
    dp={'idempotencyKey':payload['idempotencyKey']+':'+str(op.pk)+':dispatch','reason':payload['reason'],'sourceHash':_hash(source)};rh,old=native._intent(fresh,native.DISPATCH_ACTION,dp,task.pk)
    if old:fail('TEST_TASK_LEDGER_REPLAY_CONFLICT','派工账本异常重复。')
    native._ledger(fresh,native.DISPATCH_ACTION,dp,rh,task);verify(task);results.append({'taskId':task.pk,'created':True})
   return results
 results=_retry(run)
 return {'idempotent':not any(x['created'] for x in results),'tasks':results,'createdTaskCount':sum(x['created'] for x in results),'reservationWrites':0,'actualStartCount':0,'actualReportCount':0}
