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
    return _read_failure(request,status_code=409,error_code=getattr(exc,'code','ORDER_ARRANGEMENT_READ_FAILED'),error_message=str(exc))
   raise

 def post(self,request):
  try:
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
