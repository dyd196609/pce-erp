"""TEST source boundary for the existing native MES rules, not a second ledger."""
from types import SimpleNamespace
from contextlib import contextmanager
from django.utils import timezone
from system.models import OrganizationOperatingAuditRecord,Company
from .services import PlanningBusinessError
from .test_scheduling_service import _actor as fresh_actor
from .scheduling_primitives import _hash,_writer_lock
from . import workshop_receipt_protocol as receipt
from . import test_operation_start_protocol as protocol
from . import test_operation_start_service as starts
def execution_timezone(task):
 from django.conf import settings
 return task.work_order.source_snapshot['sourceSchedule'].get('timezone') or task.work_order.source_schedule.snapshot.get('timezone') or settings.TIME_ZONE

def _fail(code,message,status=409):raise PlanningBusinessError(code,message,http_status=status)
def _assert_hash(definition):
 from workflow_runtime.definition_service import serialize_definition,_canonical_hash,WorkflowDefinitionError
 fact=serialize_definition(definition,include_nodes=True)
 value={key:fact[key] for key in ('definitionCode','definitionName','businessDomain','description','documentType','version','active')}
 value['nodes']=[{key:row[key] for key in ('nodeCode','nodeName','sequence','businessActionCode','active','description')} for row in sorted(fact['nodes'],key=lambda row:(row['sequence'],row['nodeCode']))]
 if definition.definition_hash!=_canonical_hash(value):raise WorkflowDefinitionError('RELEASE_CATALOG_HASH_CONFLICT','流程内容与保存Hash不一致。',http_status=409)
def _actor(user):return fresh_actor(user),{}
def _rows(actor,runtime_scope=None):
 from .work_order_models import ProductionWorkOrder
 from django.db.models import Q
 return ProductionWorkOrder.objects.filter(company_id=actor.company_id).filter(
  Q(usage_purpose='TEST_BUSINESS',production_plan__isnull=True)|Q(usage_purpose='PRODUCTION_USE',production_plan__isnull=False))
@contextmanager
def allocation_admission_context(*,user,**kwargs):
 """TEST has no formal production-plan allocation; memoize its real source proofs."""
 from pde.routing_read_context import _current
 actor=fresh_actor(user);token=_current.set({}) if _current.get() is None else None
 try:yield {'cache':_current.get(),'actorId':actor.pk,'usagePurpose':'TEST_BUSINESS'}
 finally:
  if token is not None:_current.reset(token)
_authority=receipt._authority
_employees=receipt._employees
_effective=receipt._effective
_identity=protocol._identity
_owned=protocol._owned
_today=protocol._today
_state=protocol._state
def _verify_record(record,task):
 if task.work_order.usage_purpose=='PRODUCTION_USE':
  if task.execution_mode!='QUANTIFIED':
   from .operation_start_service import _verify_record as verify
   return verify(record,task)
  from .mes_formal_start_protocol import _verify_record as verify
  return verify(record,task)
 return starts._verify(record,task)

from .verified_read_memo import verified_model_read
@verified_model_read
def _source(task,actor):
 if task.company_id!=actor.company_id:_fail('MES_SOURCE_COMPANY_DENIED','任务不属于当前公司。',403)
 if task.work_order.usage_purpose=='PRODUCTION_USE':
  from .mes_formal_source_admission import source
  return source(task,actor)
 if task.work_order.usage_purpose!='TEST_BUSINESS':_fail('MES_TEST_PURPOSE_REQUIRED','测试来源适配器禁止消费正式用途。')
 if task.work_order.production_plan_id is not None:_fail('MES_TEST_PARENT_INVALID','测试来源不得绑定正式生产计划。')
 from django.db import connection
 from pde.routing_read_context import _current
 cache=_current.get();key=None
 if cache is not None and connection.vendor=='sqlite':
  connection.ensure_connection()
  with connection.cursor() as cursor:
   cursor.execute('PRAGMA data_version');epoch=cursor.fetchone()[0]
  # _read_context uses the persisted source custodian and company, not caller
  # permissions. Each command still independently qualifies its current actor.
  key=('mes_test_source_context',actor.company_id,task.work_order_id,id(connection.connection),connection.connection.total_changes,epoch)
 if key is not None and key in cache:contexts,current,problem=cache[key]
 else:
  contexts,current,problem=starts._read_context(actor,task.work_order,False)
  if key is not None:cache[key]=(contexts,current,problem)
 source=starts._source(task,contexts[task.source_operation_id],current,problem)
 workshop=task.workshop
 display={'id':workshop.pk,'code':workshop.code,'name':workshop.name}
 return {**source,'resourceSource':{'sourceReady':source['ready'],'statusLabel':source['statusLabel'],'usagePurpose':'TEST_BUSINESS','receiptId':task.receipt_id},'originalReceiptWorkshop':display,'effectiveWorkshop':display,'effectiveReceptionAuthority':'VERIFIED_TEST_WORKSHOP_RECEIPT'}

def record_audit(*,user,action_code,target,target_type,target_no,before,after,authorization,reason,work_order=None):
 task=getattr(target,'task',None)
 order=work_order or getattr(target,'work_order',None) or getattr(task,'work_order',None)
 if order is not None and order.company_id!=user.company_id:
  _fail('MES_AUDIT_COMPANY_MISMATCH','审计业务来源与操作人公司不一致。',403)
 if order is None:
  from .work_order_models import ProductionWorkOrder
  snapshot=getattr(target,'source_snapshot',{}) or {}
  order_id=snapshot.get('workOrderId')
  if order_id:order=ProductionWorkOrder.objects.filter(pk=order_id,company_id=user.company_id).first()
 common={'actor':{'userId':user.pk,'companyId':user.company_id},'authorization':authorization,'usagePurpose':order.usage_purpose if order else 'UNCLASSIFIED'}
 return OrganizationOperatingAuditRecord.objects.create(action_code=action_code,actor=user,organization_id=user.company_id,target_type=target_type,target_id=target.pk,target_label=target_no,reason=reason,before_snapshot={**common,'state':before},after_snapshot={**common,'state':after})

def read_reports(module,user,task_id=None):
 actor=fresh_actor(user);employee,position,department,workshop,evidence,valid=protocol._identity(actor)
 if not valid or not module.receipt_service._authority(actor,module.READ_PERMISSION,workshop.department_id,actor.pk)[0]:_fail('OPERATION_REPORT_READ_DENIED','没有有效本人报工读取授权。',403)
 records=module.Task.objects.filter(company_id=actor.company_id,execution_employee_id=employee.pk,work_order__usage_purpose='TEST_BUSINESS',operation_start__isnull=False)
 if task_id is not None:records=records.filter(pk=task_id)
 rows=[]
 for task in records:
  if not protocol._owned(actor,task,employee):continue
  start=module.Start.objects.get(task=task)
  source=_source(task,actor);execution=starts._verify(start,task)
  unit,_=module._unit(task);reports,total=module._reports(task,start);quantity=module._quantity_facts(task,unit,total)
  q=module._qualification(actor,task,start,source,quantity)
  rows.append({'id':task.pk,'taskId':task.pk,'taskNo':task.no,'workOrderId':task.work_order_id,'workOrderNo':task.work_order.no,'usagePurpose':'TEST_BUSINESS','operationName':task.source_snapshot['operation']['operationName'],'version':task.version,'sourceSnapshotHash':task.source_snapshot_hash,'assignmentHash':task.assignment_hash,'startRecordId':start.pk,'startSnapshotHash':_hash(module._start_snapshot(start)),'executionRecord':execution,'reports':reports,**quantity,'qualification':q,'availableActions':{'report':{**module.action_contract(task.pk),'enabled':q['ready'],'disabledReason':'；'.join(q['missingItems'])}}})
 selected=next((x for x in rows if x['taskId']==task_id),None) if task_id else None
 if task_id and not selected:_fail('OPERATION_REPORT_TASK_NOT_VISIBLE','不属于本公司本人已开工任务。',403)
 return {'contractVersion':module.CONTRACT,'companyId':actor.company_id,'usagePurpose':'TEST_BUSINESS','factSource':'server','currentStateSource':'server','currentActorEvidence':evidence,'tasks':rows,'selectedTask':selected,'selfTaskOnly':True}
