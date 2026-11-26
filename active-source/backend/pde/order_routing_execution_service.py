"""Independent order-step arrangements; standard definitions stay unchanged."""
from copy import deepcopy
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import BOMVersion,RoutingVersion,OrderRoutingExecutionArrangement as Arrangement,OrderRoutingExecutionDecision as Decision
from .routing_object_applicability_service import DECISIONS
from .routing_version_successor_service import _identity,_ledger,_canonical_hash
from .production_foundation_service import _snapshot,_audit
from .test_business_bom_service import authorize
from .master_data_actor import maintenance_actor
from .design_revision_approval_service import digest
from masterdata.models import MasterDataWriteRequest

PERMISSION='production.master_data.routing.maintain'
ACTION='pde.order_routing_execution.maintain'
ACTION_REGISTRY={
 'select':{'actionCode':'select-order-standard-routing','displayName':'选择并固定标准路线版本'},
 'save':{'actionCode':'save-order-execution-draft','displayName':'保存订单执行安排'},
 'confirm':{'actionCode':'confirm-order-execution','displayName':'确认订单执行安排'},
 'revise':{'actionCode':'revise-order-execution','displayName':'办理安排自身修订'},
}
LABELS={'REQUIRED':'执行（经过但未必已有定量数据）','NOT_APPLICABLE':'本单不执行（依据明确条件或业务要求）','PENDING':'待核定（尚无足够依据决定是否执行）'}
EVIDENCE={'USER_CONFIRMED':'用户／业务明确依据','TEST_ASSUMPTION':'补拟测试假设','UNRESOLVED':'依据待核定'}

class ArrangementError(ValueError):
 def __init__(self,code,message,details=None):self.code=code;self.details=details or [];super().__init__(message)
def fail(code,msg,details=None):raise ArrangementError(code,msg,details)

def context(user,bom_id,write=False):
 bom=BOMVersion.objects.select_related('bom__source_calculation','source_calculation','order_engineering_instance').get(pk=bom_id)
 authorize(user,PERMISSION if write else 'production.master_data.view',bom.bom.company_id)
 if bom.usage_purpose=='TEST_BUSINESS':
  from .test_engineering_routing_service import source
  bom,record=source(user,bom_id,write=write)
 else:
  from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
  eligible=FormalManufacturingEligibilityService.resolve(bom)
  if bom.usage_purpose!='PRODUCTION_USE' or not eligible['formalManufacturingEligible']:
   fail('SOURCE_NOT_QUALIFIED','仅接受来源完整的测试草稿或符合原正式资格的物料清单。')
  record=bom.source_calculation
  if not record or record.status!='completed' or record.company_id!=bom.bom.company_id:
   fail('SOURCE_NOT_QUALIFIED','根核算来源尚未完成或公司不一致。')
 chain=maintenance_actor(user,action_code=PERMISSION,organization_id=record.company_id) if write else {}
 return bom,record,chain

def baseline_for(record):
 baseline=record.baseline
 if baseline is None:
  from .routing_manual_applicability_service import _baseline_for_calculation
  baseline=_baseline_for_calculation(record)
 if baseline is None:fail('FROZEN_BASELINE_REQUIRED','该来源缺少可证明的冻结工程基线，不能创建订单执行安排；原正式记录保持。')
 return baseline

def standard_proof(user,bom,record,version_id):
 version=RoutingVersion.objects.select_related('routing','origin_version','test_origin_bom').get(pk=version_id)
 from .models import TestEngineeringRoutingBinding
 if version.usage_purpose=='TEST_BUSINESS' and TestEngineeringRoutingBinding.objects.filter(routing_version=version).exists():
  fail('LEGACY_TEST_ROUTING_HISTORY','此版本属于旧机制隔离历史，不作为新订单安排标准；请到企业基础资料办理结构补正。')
 if bom.usage_purpose!='TEST_BUSINESS' and (version.status!='released' or version.usage_purpose=='TEST_BUSINESS'):
  fail('STANDARD_ROUTE_NOT_RELEASED','正式订单只能引用合格已发布标准版本，不能引用测试草稿。')
 if version.usage_purpose=='TEST_BUSINESS':
  _,origin,_=context(user,version.test_origin_bom_id)
  if origin.pk!=record.pk:fail('STANDARD_ROUTE_SOURCE_MISMATCH','测试标准草稿与本单根核算来源不一致。')
 from .test_engineering_routing_service import route_snapshot
 route=route_snapshot(version,record.engineering_instance)
 # Only standard structure/resource facts here. No order applicability plan.
 baseline=baseline_for(record)
 return version,{'bom':_snapshot(bom),'rootCalculationId':record.pk,'resultHash':record.result_hash,
  'sourceId':record.source_record_id,'sourceVersion':record.source_record.source_version,
  'baselineId':baseline.pk,'baselineHash':baseline.snapshot_hash,'standard':route}

def used(obj):
 from .models import EngineeringOperationRequirement
 return obj.manufacturing_outputs.exists() or EngineeringOperationRequirement.objects.filter(execution_arrangement=obj).exists()

from planning.verified_read_memo import verified_source_read
@verified_source_read
def _load(user,pk,write=False):
 obj=Arrangement.objects.select_related('bom_version','routing_version','source_calculation','engineering_instance').get(pk=pk)
 bom,record,chain=context(user,obj.bom_version_id,write)
 if (record.pk!=obj.source_calculation_id or record.engineering_instance_id!=obj.engineering_instance_id
     or record.company_id!=obj.company_id or bom.usage_purpose!=obj.usage_purpose):
  fail('ARRANGEMENT_SOURCE_CHANGED','订单执行安排的公司、来源或用途不一致。')
 _,proof=standard_proof(user,bom,record,obj.routing_version_id)
 if digest(proof)!=obj.reference_hash:fail('FIXED_SOURCE_CHANGED','所选固定标准版本或工程来源变化，须显式核定，不能切换最新版。')
 return obj,bom,record,chain

def _reserve(user,company,key,payload):
 if not isinstance(key,str) or not key.strip():fail('IDEMPOTENCY_KEY_REQUIRED','办理须提供幂等键。')
 identity,fingerprint=_identity(organization_id=company,object_type='ORDER_ROUTING_EXECUTION',
  external_id=f"BOM:{payload['bomVersionId']}:arrangement:{payload.get('arrangementId','select')}",
  target_type='order-routing-execution',fingerprint_payload={'bomVersionId':payload['bomVersionId']})
 ledger=_ledger(organization_id=company,action_code=ACTION,entity_type='order-routing-execution',
  idempotency_key=key,request_hash=_canonical_hash(payload),identity=identity,user=user)
 return ledger

def _commit(ledger,result):
 ledger.status=MasterDataWriteRequest.Status.COMMITTED;ledger.result=result;ledger.target_entity_id=str(result['id'])
 ledger.save(update_fields=['status','result','target_entity_id','updated_at'])
 return result

def _note(reason):
 if not isinstance(reason,str) or not reason.strip():fail('BASIS_REQUIRED','须填写图纸或业务办理依据。')

def _audit_change(user,obj,chain,before,after,reason):
 return _audit(user=user,organization_id=obj.company_id,action_code=ACTION,instance=obj,before=before,after=after,
  reason=reason,authorization={'permission':PERMISSION,'companyId':obj.company_id},execution_chain=chain,
  audit_context={'owner':'ORDER_EXECUTION','standardRouteWriteCount':0,'bomVersionWriteCount':0})

def _snapshot_arr(obj):
 return {'arrangement':_snapshot(obj),'decisions':[_snapshot(x) for x in obj.decisions.order_by('pk')]}

def _write(obj):
 obj._arrangement_write_authorized=True
 try:obj.save()
 finally:obj._arrangement_write_authorized=False

@transaction.atomic
def select_standard(*,user,bom_version_id,routing_version_id,reason,key,reference_hash,expected_edit_version=None,reset_execution=False):
 _note(reason);bom,record,chain=context(user,bom_version_id,True)
 BOMVersion.objects.select_for_update().get(pk=bom.pk)
 version,proof=standard_proof(user,bom,record,routing_version_id)
 if reference_hash!=digest(proof):fail('STANDARD_PREVIEW_CHANGED','标准版本或来源已变化，请回读后重新选择。')
 payload={'bomVersionId':bom.pk,'routingVersionId':version.pk,'referenceHash':reference_hash,'action':'select','reason':reason,'expectedEditVersion':expected_edit_version,'resetExecution':reset_execution}
 ledger=_reserve(user,record.company_id,key,payload)
 if ledger.status==MasterDataWriteRequest.Status.COMMITTED:return {**ledger.result,'idempotent':True}
 obj=Arrangement.objects.select_for_update().filter(company_id=record.company_id,bom_version=bom).order_by('-arrangement_revision').first()
 if obj:
  if obj.routing_version_id==version.pk and obj.reference_hash==digest(proof):return _commit(ledger,{'id':obj.pk,'idempotent':True})
  if obj.status!='draft' or used(obj):fail('CONTROLLED_REVISION_REQUIRED','已确认或被引用的安排须先办理自身修订；不新增路线或物料清单版本。')
  if type(expected_edit_version) is not int or expected_edit_version!=obj.edit_version or reset_execution is not True:fail('REFERENCE_CHANGE_CONFIRMATION_REQUIRED','修改固定引用须核对编辑序号并明确重新安排，原安排保留在审计中。')
  before=_snapshot_arr(obj);obj.decisions.all().delete();obj.routing_version=version;obj.reference_proof=proof;obj.reference_hash=digest(proof);obj.edit_version+=1;_write(obj)
  audit=_audit_change(user,obj,chain,before,_snapshot_arr(obj),reason)
 else:
  from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition
  obj=create_business_object_with_initial_state(model=Arrangement,initial_state='draft',company_id=record.company_id,
   engineering_instance=record.engineering_instance,source_calculation=record,bom_version=bom,routing_version=version,
   usage_purpose=bom.usage_purpose,reference_proof=proof,reference_hash=digest(proof),created_by=user)
  audit=_audit_change(user,obj,chain,{},_snapshot_arr(obj),reason)
  record_projected_business_transition(object_type='OrderRoutingExecutionArrangement',object_id=obj.pk,source_state='',target_state='draft',action_code=ACTION,operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','draft')})
 return _commit(ledger,{'id':obj.pk,'auditId':audit.pk,'idempotent':False})

@transaction.atomic
def save_decisions(*,user,arrangement_id,decisions,expected_edit_version,reason,key):
 _note(reason);obj,bom,record,chain=_load(user,arrangement_id,True)
 obj=Arrangement.objects.select_for_update().get(pk=obj.pk)
 payload={'bomVersionId':bom.pk,'arrangementId':obj.pk,'action':'save','decisions':decisions,'expectedEditVersion':expected_edit_version,'reason':reason}
 ledger=_reserve(user,obj.company_id,key,payload)
 if ledger.status==MasterDataWriteRequest.Status.COMMITTED:return {**ledger.result,'idempotent':True}
 if obj.status!='draft' or used(obj):fail('CONTROLLED_REVISION_REQUIRED','已确认或被引用安排不能直接编辑，请办理安排自身修订。')
 if type(expected_edit_version) is not int or obj.edit_version!=expected_edit_version:fail('ARRANGEMENT_STALE','安排已被更新，请回读后再保存；不会覆盖其他办理。')
 if not isinstance(decisions,list) or not decisions:fail('DECISION_REQUIRED','至少选择一项已有工序执行安排。')
 before=_snapshot_arr(obj);steps={x['stepId']:x for x in obj.reference_proof['standard']['steps']};seen=set();pending=[];field_errors=[]
 prior_decisions={(x.routing_step_id,x.baseline_item_id):x for x in obj.decisions.all()}
 for row in decisions:
  if not isinstance(row,dict) or set(row)-{'stepId','decision','basis','evidenceClass','baselineItemId'}:fail('ORDER_STEP_FIELDS_INVALID','订单页面不能增加工序、改名称顺序或指定用途。')
  step_id=row.get('stepId');object_id=row.get('baselineItemId');identity=(step_id,object_id)
  if type(step_id) is not int or step_id not in steps or identity in seen:fail('STANDARD_STEP_REQUIRED','须选择所选标准版本的已有且唯一工序；缺项请到企业基础资料补正。')
  seen.add(identity)
  step=steps[step_id]
  def issue(field,message):field_errors.append({'stepId':step_id,'sequence':step['sequence'],'operationName':step['operationName'],'field':field,'message':f"第{step['sequence']}步“{step['operationName']}”：{message}"})
  if row.get('decision') not in DECISIONS:issue('decision','请选择执行、不执行或待核定。')
  if row.get('evidenceClass') not in EVIDENCE:issue('evidenceClass','请选择依据性质。')
  if not isinstance(row.get('basis'),str) or not row['basis'].strip():issue('basis','依据文字不能为空；尚未确定时可明确填写待核定事项。')
  if row.get('decision') in ('REQUIRED','NOT_APPLICABLE') and row.get('evidenceClass')=='UNRESOLVED':issue('evidenceClass','执行状态已选执行或不执行，依据性质仍为“依据待核定”；请明确测试假设或业务依据，或把执行状态保留为待核定。')
  prior=prior_decisions.get(identity)
  if prior and (row.get('decision')!=prior.decision or row.get('evidenceClass')!=prior.evidence_class) and str(row.get('basis') or '').strip()==prior.basis.strip():issue('basis','执行状态或依据性质已修改，依据文字仍是上次保存内容；请补充本次选择的具体依据，不会自动改成业务确认。')
  if object_id is not None:
   from .models import OrderEngineeringBaselineItem
   if type(object_id) is not int or not OrderEngineeringBaselineItem.objects.filter(pk=object_id,baseline_id=obj.reference_proof['baselineId'],design_item__sales_order_item_id=record.sales_order_item_id).exists():fail('ORDER_OBJECT_SCOPE_INVALID','适用对象不是本单冻结设计对象。')
  pending.append(row)
 if field_errors:fail('DECISION_FIELDS_INCONSISTENT','工序字段不一致或依据缺失；输入应保留，请逐项核对。',field_errors)
 audit=_audit_change(user,obj,chain,before,{'submittedDecisions':pending,'nextEditVersion':obj.edit_version+1},reason)
 for row in pending:
  decision=Decision.objects.filter(arrangement=obj,routing_step_id=row['stepId'],baseline_item_id=row.get('baselineItemId')).first()
  decision=decision or Decision(arrangement=obj,routing_step_id=row['stepId'],baseline_item_id=row.get('baselineItemId'))
  decision.decision=row['decision'];decision.basis=row['basis'];decision.evidence_class=row['evidenceClass'];decision.last_audit=audit
  decision._arrangement_write_authorized=True;decision.save()
 obj.edit_version+=1;_write(obj)
 return _commit(ledger,{'id':obj.pk,'auditId':audit.pk,'editVersion':obj.edit_version,'idempotent':False})

@transaction.atomic
def confirm(*,user,arrangement_id,expected_edit_version,reason,key):
 _note(reason);obj,bom,record,chain=_load(user,arrangement_id,True);obj=Arrangement.objects.select_for_update().get(pk=obj.pk)
 payload={'bomVersionId':bom.pk,'arrangementId':obj.pk,'action':'confirm','expectedEditVersion':expected_edit_version,'reason':reason}
 ledger=_reserve(user,obj.company_id,key,payload)
 if ledger.status==MasterDataWriteRequest.Status.COMMITTED:return {**ledger.result,'idempotent':True}
 if obj.status!='draft' or type(expected_edit_version) is not int or obj.edit_version!=expected_edit_version:fail('ARRANGEMENT_STALE','安排状态或编辑序号已变化。')
 rows=list(obj.decisions.all());whole={x.routing_step_id:x for x in rows if not x.baseline_item_id}
 if set(whole)!={s['stepId'] for s in obj.reference_proof['standard']['steps']} or any(x.decision=='PENDING' for x in rows):fail('ORDER_EXECUTION_PENDING','仍有未核定工序，不能确认；未知不作为不执行。')
 audit=_audit_change(user,obj,chain,_snapshot_arr(obj),{'statusLabel':'已确认','purpose':obj.usage_purpose},reason)
 from workflow_runtime.state_transitions import transition_business_object
 transition_business_object(business_object=obj,object_type='OrderRoutingExecutionArrangement',source_state='draft',target_state='confirmed',action_code=ACTION,operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('draft','confirmed')},version_field=None)
 return _commit(ledger,{'id':obj.pk,'auditId':audit.pk,'idempotent':False})

@transaction.atomic
def revise(*,user,arrangement_id,reason,key):
 _note(reason);old,bom,record,chain=_load(user,arrangement_id,True);old=Arrangement.objects.select_for_update().get(pk=old.pk)
 payload={'bomVersionId':bom.pk,'arrangementId':old.pk,'action':'revise','reason':reason}
 ledger=_reserve(user,old.company_id,key,payload)
 if ledger.status==MasterDataWriteRequest.Status.COMMITTED:return {**ledger.result,'idempotent':True}
 if old.status=='draft' and not used(old):fail('DRAFT_EDIT_DIRECTLY','草稿直接维护，不因每次执行选择新建安排修订。')
 if Arrangement.objects.filter(predecessor=old).exists():fail('ARRANGEMENT_SUCCESSOR_EXISTS','已有安排后继草稿，请回读，不能重复新建。')
 from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition
 obj=create_business_object_with_initial_state(model=Arrangement,initial_state='draft',company_id=old.company_id,engineering_instance_id=old.engineering_instance_id,
  source_calculation_id=old.source_calculation_id,bom_version_id=old.bom_version_id,routing_version_id=old.routing_version_id,
  usage_purpose=old.usage_purpose,arrangement_revision=old.arrangement_revision+1,predecessor=old,
  reference_proof=deepcopy(old.reference_proof),reference_hash=old.reference_hash,created_by=user)
 audit=_audit_change(user,obj,chain,{'predecessorArrangementId':old.pk,'referenced':used(old)},_snapshot(obj),reason)
 for row in old.decisions.all():
  clone=Decision(arrangement=obj,routing_step_id=row.routing_step_id,baseline_item_id=row.baseline_item_id,decision=row.decision,basis=row.basis,evidence_class=row.evidence_class,last_audit=audit)
  clone._arrangement_write_authorized=True;clone.save()
 record_projected_business_transition(object_type='OrderRoutingExecutionArrangement',object_id=obj.pk,source_state='',target_state='draft',action_code=ACTION,operator=user,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','draft')})
 return _commit(ledger,{'id':obj.pk,'auditId':audit.pk,'idempotent':False})

def read(*,user,arrangement_id,baseline_item_id=None):
 obj,bom,record,_=_load(user,arrangement_id)
 from .models import OrderEngineeringBaselineItem
 objects=list(OrderEngineeringBaselineItem.objects.filter(baseline_id=obj.reference_proof['baselineId'],design_item__sales_order_item_id=record.sales_order_item_id).values('id','design_item_id','content_snapshot'))
 if baseline_item_id is not None and baseline_item_id not in {x['id'] for x in objects}:fail('ORDER_OBJECT_SCOPE_INVALID','适用对象不属于此订单行。')
 decisions=list(obj.decisions.select_related('last_audit__actor'));lookup={(x.routing_step_id,x.baseline_item_id):x for x in decisions};rows=[]
 for step in obj.reference_proof['standard']['steps']:
  row=lookup.get((step['stepId'],baseline_item_id)) or lookup.get((step['stepId'],None))
  if row and (row.last_audit.target_type!='OrderRoutingExecutionArrangement' or row.last_audit.target_id!=obj.pk or row.last_audit.organization_id!=obj.company_id):fail('DECISION_AUDIT_INVALID','订单安排办理审计不一致。')
  rows.append({**step,'decision':row.decision if row else 'PENDING','decisionLabel':LABELS[row.decision] if row else LABELS['PENDING'],
   'basis':row.basis if row else '尚未办理','evidenceClass':row.evidence_class if row else 'UNRESOLVED','evidenceLabel':EVIDENCE[row.evidence_class] if row else EVIDENCE['UNRESOLVED'],
   'baselineItemId':row.baseline_item_id if row else None,'scopeLabel':'指定冻结部件' if row and row.baseline_item_id else '整个订单行',
   'auditId':row.last_audit_id if row else None,'operatorLabel':row.last_audit.actor.username if row else '', 'quantity':None})
 from system.models import OrganizationOperatingAuditRecord
 audits=list(OrganizationOperatingAuditRecord.objects.filter(target_type='OrderRoutingExecutionArrangement',target_id=obj.pk,organization_id=obj.company_id).values('id','actor__username','reason','created_at'))
 can_edit=False;reason=''
 try:context(user,bom.pk,True);can_edit=obj.status=='draft' and not used(obj)
 except Exception as exc:reason=str(exc)
 actions=[]
 successor_exists=Arrangement.objects.filter(predecessor=obj).exists()
 incomplete=any(x.decision=='PENDING' for x in decisions) or {x.routing_step_id for x in decisions if x.baseline_item_id is None}!={x['stepId'] for x in rows}
 for action,value in ACTION_REGISTRY.items():
  enabled=(can_edit if action in ('save','select','confirm') else obj.status!='draft' or used(obj)) and not reason
  action_reason=reason
  if action=='confirm' and incomplete:enabled=False
  if action=='revise' and successor_exists:
   enabled=False;action_reason='已有后继安排，请选择后继修订查看或办理。'
  actions.append({**value,'action':action,'moduleCode':'routing-management','requiredPermission':PERMISSION,'organizationScope':obj.company_id,'serverValidator':'order_routing_execution_service','executable':enabled,'disabledReason':action_reason or ('仍有待核定工序，不能确认' if action=='confirm' and incomplete else '当前阶段须通过安排自身修订办理' if not enabled else '')})
 result={'id':obj.pk,'orderNo':record.sales_order_item.sales_order.order_no,'bomVersionId':bom.pk,'bomVersionName':bom.bom_version,
  'routingVersionId':obj.routing_version_id,'routingVersionName':obj.routing_version.routing_version,'routingVersionRevision':obj.routing_version.revision,'sourceCalculationId':record.pk,'sourceCalculationNo':record.calculation_no,'sourceId':record.source_record_id,'baselineId':obj.reference_proof['baselineId'],'routingCode':obj.routing_version.routing.routing_code,
  'routingName':obj.routing_version.routing.name,'standardStepCount':len(rows),'steps':rows,'objects':objects,
  'statusLabel':obj.get_status_display(),'editVersion':obj.edit_version,'arrangementRevision':obj.arrangement_revision,'predecessorId':obj.predecessor_id,
  'purposeLabel':'测试业务（不得制造）' if obj.usage_purpose=='TEST_BUSINESS' else '正式业务（仍须原生产门禁）',
  'usagePurpose':obj.usage_purpose,'formalManufacturingEligible':False,'availableActions':actions,'auditHistory':audits,
  'requestIdentity':{'userId':user.pk,'username':user.username,'companyId':user.company_id},'databaseBusinessWriteCount':0}
 from .frozen_workload_persistence import read_saved_workloads
 result['operationWorkloads']=read_saved_workloads(user=user,arrangement=obj)
 current={x['stepId']:x for x in result['operationWorkloads']['rows'] if x['current']}
 for step in result['steps']:
  saved=current.get(step['stepId'])
  step['workloadQuantityText']=saved['quantityText'] if saved else None
  step['workloadUnitLabel']=saved['unitLabel'] if saved else ''
  step['workloadSourceLabel']=saved['sourceLabel'] if saved else ''
  step['workloadStatusLabel']=('已保存测试作业量' if saved else '本测试场景不执行；不生成需求' if step['decision']=='NOT_APPLICABLE' else '执行条件待核定；作业量未知' if step['decision']=='PENDING' else '本步执行；缺少获准的处理对象／计量依据，作业量未知')
 # Unquantified saved choices must report actual source configuration, not infer missing geometry.
 missing_steps=[x for x in result['steps'] if x['decision']=='REQUIRED' and x['stepId'] not in current]
 if missing_steps:
  from .models import RoutingStep, CapacityProductType
  from .operation_workload_source_service import operation_source_configuration
  from .operation_requirement_service import _active
  route=obj.routing_version.routing
  kinds=[x for x in CapacityProductType.objects.filter(company_id=obj.company_id,
   product_category_id=route.product_category_id, manufacturing_process_type_id=route.manufacturing_process_type_id) if x.is_active and _active(x)]
  actual_steps={x.pk:x for x in RoutingStep.objects.filter(pk__in=[x['stepId'] for x in missing_steps]).select_related('operation__calculation_uom')}
  for step in missing_steps:
   actual=actual_steps[step['stepId']];operation=actual.operation
   scope={'routingId':route.pk,'routingVersionId':obj.routing_version_id,'routingStepId':actual.pk}
   source=operation_source_configuration(operation,kinds[0].pk,scope) if len(kinds)==1 else {'statusLabel':'产品工艺范围未唯一匹配，禁止选取来源','sources':[],'hasValidSourceConfiguration':False,'businessWriteCount':0}
   unit=operation.calculation_uom.name if operation.calculation_uom_id else '未维护'
   review={'operationId':operation.pk,'operationCode':operation.code,
    'calculationBasis':operation.calculation_basis,'calculationBasisLabel':operation.get_calculation_basis_display(),
    'uomId':operation.calculation_uom_id,'uomLabel':unit,'legacyQuantityDriver':operation.quantity_driver,
    'productTypeId':kinds[0].pk if len(kinds)==1 else None,
    'productTypeLabel':kinds[0].code+'／'+kinds[0].name if len(kinds)==1 else '产品分类与工艺范围未唯一匹配',
    'sourceConfiguration':source,'executionBasis':step['basis']}
   step['systemSourceReview']=review
   step['workloadStatusLabel']='本步执行；'+source['statusLabel']+'，尚不能生成作业量'
   step['workloadSourceLabel']='系统核对：核算维度'+review['calculationBasisLabel']+'，单位'+unit+'；旧投产量说明“'+(operation.quantity_driver or '未维护')+'”；适用产品工艺'+review['productTypeLabel']+'；'+source['statusLabel']+'。执行依据：'+step['basis']
 result['routeWorkloadSummary']={'totalSteps':len(result['steps']),'quantifiedSteps':len(current),'notApplicableSteps':sum(x['decision']=='NOT_APPLICABLE' for x in result['steps']),'pendingExecutionSteps':sum(x['decision']=='PENDING' for x in result['steps']),'unknownQuantitySteps':sum(x['decision']=='REQUIRED' and x['stepId'] not in current for x in result['steps']),'nonQuantifiedSteps':0,'nextNodeEligible':False,'nextNodeStatusLabel':'测试用途不具备正式下一节点准入；作业量、标准产能、日历及日期排产须分别核验'}
 return result

def catalog(user):
 authorize(user,'production.master_data.view',user.company_id)
 rows=[]
 for obj in Arrangement.objects.filter(company_id=user.company_id).order_by('-pk'):
  try:rows.append(read(user=user,arrangement_id=obj.pk))
  except ArrangementError as exc:
   rows.append({'id':obj.pk,'bomVersionId':obj.bom_version_id,'editVersion':obj.edit_version,'arrangementRevision':obj.arrangement_revision,
     'orderNo':obj.source_calculation.sales_order_item.sales_order.order_no,'factLoadStatus':'read_failed','statusLabel':str(exc),'formalManufacturingEligible':False})
 return rows

def validate_manufacturing_reference(output):
 obj=output.order_routing_arrangement
 if obj.usage_purpose!='PRODUCTION_USE' or obj.status!='confirmed' or (obj.bom_version_id,obj.routing_version_id,obj.engineering_instance_id)!=(output.bom_version_id,output.routing_version_id,output.order_engineering_instance_id):
  raise ValidationError('制造引用必须是同一来源、已确认的正式订单执行安排；测试安排不能进入制造。')


def catalog_index(user):
 """Company-scoped navigation only; selected arrangement must pass full read()."""
 authorize(user,'production.master_data.view',user.company_id)
 objects=list(Arrangement.objects.filter(company_id=user.company_id).select_related('source_calculation__sales_order_item__sales_order').order_by('-arrangement_revision','-pk'))
 superseded={x.predecessor_id for x in objects if x.predecessor_id}
 return [{'id':x.pk,'orderNo':x.source_calculation.sales_order_item.sales_order.order_no,
  'orderItemId':x.source_calculation.sales_order_item_id,'bomVersionId':x.bom_version_id,
  'arrangementRevision':x.arrangement_revision,'editVersion':x.edit_version,
  'isCurrent':x.pk not in superseded,'referenceValidation':'DETAIL_READ_REQUIRED',
  'statusLabel':x.get_status_display(), 'requestIdentity':{'userId':user.pk,'username':user.username,'companyId':user.company_id}}
  for x in objects]
