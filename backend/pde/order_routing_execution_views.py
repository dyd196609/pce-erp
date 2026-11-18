from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ObjectDoesNotExist,ValidationError
from . import order_routing_execution_service as service
from .routing_read_context import routing_read_request

class OrderRoutingExecutionView(APIView):
 permission_classes=[IsAuthenticated]

 @routing_read_request
 def get(self,request):
  from .views import _facts,_read_failure
  try:
   from .test_business_bom_service import authorize
   try:
    authorize(request.user,'production.master_data.view',request.user.company_id)
    assignee_only=False
   except Exception as permission_error:
    if getattr(permission_error,'code','') not in ('PERMISSION_DENIED','SCOPE_DENIED','ORGANIZATION_MISMATCH','ROLE_REQUIRED','ACTION_NOT_GRANTED'):raise
    assignee_only=True
   if assignee_only:
    from planning.test_assignee_entry import entry
    action=request.query_params.get('action')
    if action not in (None,'index','test-operation-starts') or set(request.query_params)-{'action','arrangementId'}:
     raise service.ArrangementError('SCOPE_DENIED','本人入口仅允许本人任务及必要安排身份读取。')
    aid=int(request.query_params['arrangementId']) if request.query_params.get('arrangementId') else None
    scoped=entry(request.user,aid)
    if action!='test-operation-starts':
     payload=_facts('pde-routings',scoped['orderExecutionArrangements'],request);payload.update(scoped)
     for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key].update(scoped)
     return Response(payload)
   if request.query_params.get('action') in ('test-workshop-tasks','test-operation-starts'):
    if set(request.query_params)-{'action','arrangementId'} or not request.query_params.get('arrangementId'):raise service.ArrangementError('TEST_TASK_FIELDS_INVALID','派工查看只接受真实安排身份。')
    from planning.test_scheduling_service import _actor
    from planning.work_order_models import ProductionWorkOrder
    from planning.test_workshop_task_service import read
    if request.query_params['action']=='test-operation-starts':
     from planning.test_operation_start_service import read
    actor=_actor(request.user)
    from pde.models import OrderRoutingExecutionArrangement
    arr=OrderRoutingExecutionArrangement.objects.filter(pk=int(request.query_params['arrangementId']),company_id=actor.company_id,usage_purpose='TEST_BUSINESS').first()
    if arr is None:raise service.ArrangementError('SCOPE_DENIED','安排不存在、越公司或不是测试来源。')
    orders=list(ProductionWorkOrder.objects.filter(company_id=actor.company_id,usage_purpose='TEST_BUSINESS',source_schedule__execution_arrangement=arr,source_schedule__status='saved').order_by('pk')[:2])
    if len(orders)>1:raise service.ArrangementError('TEST_TASK_SOURCE_AMBIGUOUS','当前安排存在多个已保存工单来源，不能自行挑选。')
    if not orders:
     from pde.test_business_bom_service import authorize
     authorize(actor,'planning.view',arr.company_id)
    result=read(user=actor,work_order_id=orders[0].pk,**({'own_only':True} if assignee_only else {})) if orders else {'factSource':'server','requestIdentity':{'userId':actor.pk,'username':actor.username,'companyId':actor.company_id},'scope':{'companyId':arr.company_id,'arrangementId':arr.pk,'arrangementRevision':arr.arrangement_revision,'arrangementEditVersion':arr.edit_version},'workOrderId':None,'workOrderNo':None,'groups':[],'summary':None,'emptyReason':'当前安排尚无有效已保存测试工单，暂不能派工。'}
    fact_key='testOperationStarts' if request.query_params['action']=='test-operation-starts' else 'testWorkshopTasks'
    payload=_facts('pde-routings',result.get('groups',result.get('rows',[])),request);payload[fact_key]=result
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key][fact_key]=result
    return Response(payload)
   if request.query_params.get('action')=='saved-order-work-orders':
    if set(request.query_params)-{'action','arrangementId'} or not request.query_params.get('arrangementId'):raise service.ArrangementError('WORK_ORDER_FIELDS_INVALID','已保存结果只接受真实安排身份，不接受公司、用途或来源覆盖。')
    from planning.test_scheduling_service import read as read_schedules
    from planning.test_work_order_service import read as read_work_order
    arrangement_id=int(request.query_params['arrangementId'])
    saved=read_schedules(user=request.user,arrangement_id=arrangement_id)
    current=saved['activeSchedule']
    result=read_work_order(user=request.user,arrangement_id=arrangement_id,schedule_id=current['id'],expected_snapshot_hash=current['snapshotHash']) if current else None
    payload=_facts('pde-routings',saved['history'],request)
    values={'orderExecutionTestSchedule':saved,'testWorkOrderReception':result}
    payload.update(values)
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key].update(values)
    return Response(payload)
   if request.query_params.get('action')=='test-work-order-reception':
    if set(request.query_params)-{'action','arrangementId','scheduleId','expectedSnapshotHash'} or not request.query_params.get('arrangementId') or not request.query_params.get('scheduleId'):raise service.ArrangementError('WORK_ORDER_FIELDS_INVALID','工单承接核对只接受明确真实安排、排程及读取凭据。')
    from planning.test_work_order_reception import read_reception
    result=read_reception(user=request.user,arrangement_id=int(request.query_params['arrangementId']),schedule_id=int(request.query_params['scheduleId']),expected_snapshot_hash=request.query_params.get('expectedSnapshotHash'))
    payload=_facts('pde-routings',result['rows'],request);payload['testWorkOrderReception']=result
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]['testWorkOrderReception']=result
    return Response(payload)
   if request.query_params.get('action')=='test-schedules':
    if set(request.query_params)-{'action','arrangementId'}:raise service.ArrangementError('TEST_SCHEDULE_FIELDS_INVALID','只接受安排身份。')
    from planning.test_scheduling_service import read
    result=read(user=request.user,arrangement_id=int(request.query_params['arrangementId']))
    payload=_facts('pde-routings',result['history'],request);payload['orderExecutionTestSchedule']=result
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]['orderExecutionTestSchedule']=result
    return Response(payload)
   if request.query_params.get('action')=='date-preview':
    if set(request.query_params)-{'action','arrangementId','startAt'} or not request.query_params.get('arrangementId') or not request.query_params.get('startAt'):
     raise service.ArrangementError('DATE_PREVIEW_FIELDS_INVALID','日期预览只接受已保存安排身份及带时区测试开始时间。')
    from .order_execution_date_preview_service import preview_dates
    result=preview_dates(user=request.user,arrangement_id=int(request.query_params['arrangementId']),start_at=request.query_params['startAt'])
    payload=_facts('pde-routings',result['rows'],request);payload['orderExecutionDatePreview']=result
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]['orderExecutionDatePreview']=result
    return Response(payload)
   if request.query_params.get('action')=='capacity':
    if set(request.query_params)-{'action','arrangementId'} or not request.query_params.get('arrangementId'):
     raise service.ArrangementError('CAPACITY_READ_FIELDS_INVALID','仅接受已保存安排身份，不接受调用者指定公司、用途、数量或产能。')
    from .order_execution_capacity_read_service import read_capacity_review
    result=read_capacity_review(user=request.user,arrangement_id=int(request.query_params['arrangementId']))
    payload=_facts('pde-routings',result['rows'],request);payload['orderExecutionCapacity']=result
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]['orderExecutionCapacity']=result
    return Response(payload)
   if request.query_params.get('action')=='workload':
    allowed={'action','arrangementId','baselineItemId','expectedEditVersion','expectedReadHash'}
    if set(request.query_params)-allowed:
     raise service.ArrangementError('ORDER_WORKLOAD_FIELDS_INVALID','作业量只读核定不接受调用者指定公司、用途、来源、规则或数量。')
    if not request.query_params.get('arrangementId'):
     raise service.ArrangementError('ORDER_WORKLOAD_ARRANGEMENT_REQUIRED','请明确选择已保存的订单执行安排。')
    from .operation_workload_source_service import read_for_arrangement
    result=read_for_arrangement(user=request.user,arrangement_id=int(request.query_params['arrangementId']),
     baseline_item_id=int(request.query_params['baselineItemId']) if request.query_params.get('baselineItemId') else None,
     expected_edit_version=int(request.query_params['expectedEditVersion']) if request.query_params.get('expectedEditVersion') else None,
     expected_read_hash=request.query_params.get('expectedReadHash'))
    payload=_facts('pde-routings',result['steps'],request);payload['orderExecutionWorkload']=result
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):
     payload[key]['orderExecutionWorkload']=result;payload[key]['operationWorkloadReadinessPassed']=False
     payload[key]['acceptanceStatus']='BLOCKED';payload[key]['passed']=False
     payload[key]['statusLabel']=result['readinessStatusLabel']
    return Response(payload)
   if request.query_params.get('action')=='index':
    rows=service.catalog_index(request.user)
    payload=_facts('pde-routings',rows,request);payload['orderExecutionArrangements']=rows
    payload['requestIdentity']={'userId':request.user.pk,'username':request.user.username,'companyId':request.user.company_id}
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]['orderExecutionArrangements']=rows
    return Response(payload)
   if request.query_params.get('action')=='preview':
    bom,record,_=service.context(request.user,int(request.query_params['bomVersionId']))
    version,proof=service.standard_proof(request.user,bom,record,int(request.query_params['routingVersionId']))
    return Response({'referenceHash':service.digest(proof),'routingVersionId':version.pk,'versionName':version.routing_version,'steps':proof['standard']['steps'],'databaseBusinessWriteCount':0})
   if request.query_params.get('action')=='choices':
    from .models import BOMVersion,RoutingVersion
    from .test_business_bom_service import authorize
    authorize(request.user,'production.master_data.view',request.user.company_id)
    boms=list(BOMVersion.objects.filter(bom__company_id=request.user.company_id).values('id','bom_version','usage_purpose','order_engineering_instance_id'))
    routes=list(RoutingVersion.objects.filter(routing__company_id=request.user.company_id).values('id','routing_version','revision','status','usage_purpose','routing__routing_code','routing__name'))
    from .production_foundation_service import ProductionFoundationService
    return Response({'bomVersions':boms,'standardVersions':routes,'actionRegistry':service.ACTION_REGISTRY,
      'maintenanceAuthorization':ProductionFoundationService.maintenance_authorization('routings',user=request.user),
      'requestIdentity':{'userId':request.user.pk,'username':request.user.username,'companyId':request.user.company_id},'databaseBusinessWriteCount':0})
   object_id=request.query_params.get('arrangementId');object_item=request.query_params.get('baselineItemId')
   rows=[service.read(user=request.user,arrangement_id=int(object_id),baseline_item_id=int(object_item) if object_item else None)] if object_id else service.catalog(request.user)
   payload=_facts('pde-routings',rows,request);payload['orderExecutionArrangements']=rows
   for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]['orderExecutionArrangements']=rows
   return Response(payload)
  except Exception as exc:
   if isinstance(exc,(ValueError,ValidationError,ObjectDoesNotExist)) or hasattr(exc,'code'):
    denied=getattr(exc,'code','') in ('PERMISSION_DENIED','SCOPE_DENIED','ORGANIZATION_MISMATCH','ROLE_REQUIRED','ACTION_NOT_GRANTED','MES_ASSIGNEE_SCOPE_NOT_APPLICABLE')
    return _read_failure(request,status_code=403 if denied else 409,error_code=getattr(exc,'code','ORDER_ARRANGEMENT_READ_FAILED'),error_message=str(exc))
   raise

 def post(self,request):
  try:
   if request.data.get('action')=='generate-test-work-order':
    from planning.test_work_order_service import generate
    d=dict(request.data);d.pop('action');arrangement_id=d.pop('arrangementId',None);schedule_id=d.pop('scheduleId',None)
    if type(arrangement_id) is not int or type(schedule_id) is not int:raise service.ArrangementError('WORK_ORDER_SOURCE_REQUIRED','须明确真实安排及排程身份。')
    result=generate(user=request.user,arrangement_id=arrangement_id,schedule_id=schedule_id,payload=d)
    facts=result['facts'];base={'testWorkOrderReception':facts,'testWorkOrderOperation':{k:v for k,v in result.items() if k!='facts'}};payload=dict(base)
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]=dict(base)
    return Response(payload)
   if request.data.get('action')=='start-test-operation':
    from planning.test_operation_start_service import start,read
    from planning.workshop_task_models import ProductionWorkshopTask
    d=dict(request.data);d.pop('action');task_id=d.pop('taskId',None)
    operation=start(user=request.user,task_id=task_id,payload=d)
    task=ProductionWorkshopTask.objects.get(pk=task_id,company_id=request.user.company_id)
    result=read(user=request.user,work_order_id=task.work_order_id)
    base={'testOperationStarts':result,'testOperationStartOperation':operation};payload=dict(base)
    for name in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[name]=dict(base)
    return Response(payload)
   if request.data.get('action')=='dispatch-test-workshop-tasks':
    from planning.test_workshop_task_service import dispatch,read
    d=dict(request.data);d.pop('action');pk=d.pop('workOrderId',None);wid=d.pop('workshopId',None)
    if type(pk) is not int or type(wid) is not int:raise service.ArrangementError('TEST_TASK_SOURCE_REQUIRED','须指定真实测试工单与车间。')
    result=dispatch(user=request.user,work_order_id=pk,workshop_id=wid,payload=d)
    facts=read(user=request.user,work_order_id=pk);base={'testWorkshopTasks':facts,'testWorkshopTaskOperation':result};payload=dict(base)
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]=dict(base)
    return Response(payload)
   if request.data.get('action')=='receive-test-workshop':
    from planning.test_work_order_dispatch_service import receive,read
    d=dict(request.data);d.pop('action');pk=d.pop('workOrderId',None);wid=d.pop('workshopId',None)
    if type(pk) is not int or type(wid) is not int:raise service.ArrangementError('RECEIPT_ID_REQUIRED','必须指定真实工单及车间。')
    result=receive(user=request.user,work_order_id=pk,workshop_id=wid,payload=d)
    facts=read(user=request.user,work_order_id=pk);base={'testWorkOrderDispatch':facts,'testWorkOrderOperation':result};payload=dict(base)
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]=dict(base)
    return Response(payload)
   if request.data.get('action')=='release-test-work-order':
    from planning.test_work_order_dispatch_service import release
    from planning.test_work_order_service import read
    d=dict(request.data);d.pop('action');pk=d.pop('workOrderId',None)
    if type(pk) is not int:raise service.ArrangementError('WORK_ORDER_ID_REQUIRED','必须指定真实测试工单。')
    result=release(user=request.user,work_order_id=pk,payload=d)
    from planning.work_order_models import ProductionWorkOrder
    row=ProductionWorkOrder.objects.get(pk=pk,company_id=request.user.company_id)
    facts=read(user=request.user,arrangement_id=row.source_snapshot['scope']['arrangementId'],schedule_id=row.source_schedule_id)
    base={'testWorkOrderReception':facts,'testWorkOrderOperation':{'idempotent':result['idempotent']}};payload=dict(base)
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]=dict(base)
    return Response(payload)
   if request.data.get('action') in ('execute-test-work-order',):
    from planning.test_work_order_service import deny_release
    return deny_release(user=request.user,work_order_id=request.data.get('workOrderId'))
   if request.data.get('action') in ('save-test-schedule','cancel-test-schedule'):
    from planning.test_scheduling_service import commit,cancel
    d=dict(request.data);action=d.pop('action');arrangement_id=d.pop('arrangementId',None)
    if type(arrangement_id) is not int:raise service.ArrangementError('ARRANGEMENT_REQUIRED','须指定真实安排身份。')
    if action=='save-test-schedule':result=commit(user=request.user,arrangement_id=arrangement_id,payload=d)
    else:result=cancel(user=request.user,arrangement_id=arrangement_id,schedule_id=d.pop('scheduleId',None),payload=d)
    facts=result['facts'];payload={'orderExecutionTestSchedule':facts,'testScheduleOperation':{k:v for k,v in result.items() if k!='facts'}}
    base=dict(payload)
    for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):payload[key]=dict(base)
    return Response(payload)
   d=request.data;action=d.get('action');allowed={'action','bomVersionId','routingVersionId','referenceHash','arrangementId','decisions','expectedEditVersion','reason','idempotencyKey','resetExecution'}
   if set(d)-allowed:return Response({'message':'不接受用途、状态、标准结构、操作者或审批结论字段。'},status=400)
   common={'user':request.user,'reason':d.get('reason'),'key':d.get('idempotencyKey')}
   if action=='select':result=service.select_standard(**common,bom_version_id=d['bomVersionId'],routing_version_id=d['routingVersionId'],expected_edit_version=d.get('expectedEditVersion'),reset_execution=d.get('resetExecution',False),reference_hash=d.get('referenceHash'))
   elif action=='save':result=service.save_decisions(**common,arrangement_id=d['arrangementId'],decisions=d['decisions'],expected_edit_version=d['expectedEditVersion'])
   elif action=='confirm':result=service.confirm(**common,arrangement_id=d['arrangementId'],expected_edit_version=d['expectedEditVersion'])
   elif action=='revise':result=service.revise(**common,arrangement_id=d['arrangementId'])
   else:return Response({'message':'未登记订单安排动作。'},status=400)
   return Response(result)
  except Exception as exc:
   if isinstance(exc,(ValueError,ValidationError,ObjectDoesNotExist)) or hasattr(exc,'code'):
    return Response({'code':getattr(exc,'code','ORDER_ARRANGEMENT_WRITE_FAILED'),'message':str(exc),'fieldErrors':getattr(exc,'details',[]),'databaseBusinessWriteCount':0},status=403 if getattr(exc,'code','') in ('PERMISSION_DENIED','SCOPE_DENIED') else 409)
   raise
