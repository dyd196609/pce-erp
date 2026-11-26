"""Canonical enterprise-foundation owner of standard route maintenance."""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ObjectDoesNotExist,ValidationError
from functools import wraps
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError

def domain_read_errors(fn):
    @wraps(fn)
    def wrapped(self,request,*args,**kwargs):
        try:return fn(self,request,*args,**kwargs)
        except Exception as exc:
            if isinstance(exc,(ValueError,ValidationError,ObjectDoesNotExist,IntegrityError,ProtectedError)) or hasattr(exc,'code'):
                from .views import _read_failure
                return _read_failure(request,status_code=403 if getattr(exc,'code','') in ('SCOPE_DENIED','PERMISSION_DENIED') else 409,error_code=getattr(exc,'code','FOUNDATION_READ_FAILED'),error_message=str(exc))
            raise
    return wrapped

class FoundationRoutingControlView(APIView):
    permission_classes=[IsAuthenticated]

    @domain_read_errors
    def get(self,request,object_id,action='versions'):
        from .models import Routing,RoutingVersion
        from .test_business_bom_service import authorize
        from .production_foundation_service import ProductionFoundationService
        route=Routing.objects.get(pk=object_id)
        authorize(request.user,'production.master_data.view',route.company_id)
        versions=list(route.versions.order_by('-revision'))
        result=[]
        for version in versions:
            from .standard_routing_owner_service import edit_boundary,structure_hash
            result.append({'id':version.pk,'name':version.routing_version,'revision':version.revision,
                'statusLabel':version.get_status_display(),'usageLabel':version.get_usage_purpose_display(),
                'originVersionId':version.origin_version_id,'steps':[{'id':s.pk,'sequence':s.sequence,
                    'operationId':s.operation_id,'operationName':s.operation.name,'predecessors':s.predecessor_sequences,
                    'workCenterId':s.work_center_id or s.operation.work_center_id} for s in version.steps.select_related('operation').order_by('sequence')],
                'canEdit':not edit_boundary(version) and ProductionFoundationService.maintenance_authorization('routing-steps',user=request.user)['allowed'],
                'editDisabledReason':edit_boundary(version)})
            result[-1]['editHash']=structure_hash(version)
            from .models import TestEngineeringRoutingBinding
            from .order_routing_models import OrderRoutingExecutionArrangement
            legacy=version.usage_purpose=='TEST_BUSINESS' and TestEngineeringRoutingBinding.objects.filter(routing_version=version).exists()
            result[-1]['canCreateSuccessor']=not legacy and (version.status in ('reviewed','released','obsolete') or OrderRoutingExecutionArrangement.objects.filter(routing_version=version,status='confirmed').exists())
            result[-1]['successorDisabledReason']='旧机制历史只读，不推广到新订单安排' if legacy else '当前草稿直接维护，订单选择不增加标准版本'
        return Response({'versions':result,'ownerLabel':'标准路线唯一维护归属：企业基础资料→工艺路线',
            'operations':ProductionFoundationService.reference_options('operations',organization_id=route.company_id),
            'testBomVersions':list(__import__('pde.models',fromlist=['BOMVersion']).BOMVersion.objects.filter(bom__company_id=route.company_id,usage_purpose='TEST_BUSINESS').values('id','bom_version')),
            'authorization':ProductionFoundationService.maintenance_authorization('routings',user=request.user),
            'requestIdentity':{'userId':request.user.pk,'username':request.user.username,'companyId':request.user.company_id},'databaseBusinessWriteCount':0})

    def post(self,request,object_id,action):
        from .routing_version_successor_service import RoutingVersionSuccessorService,RoutingStepApplicabilityMaintenanceService
        from .production_foundation_service import ProductionFoundationService
        data=request.data
        try:
            if action=='initial-version':
                result=ProductionFoundationService.write('routing-versions',user=request.user,payload={'routing_id':object_id,'reason':data['reason']},idempotency_key=data['idempotencyKey'],source_identity={'sourceSystem':'PCE_SYSTEM','sourceType':'STANDARD_ROUTING_INITIAL_VERSION','sourceObjectType':'RoutingVersion','externalId':f'Routing:{object_id}:initial'})
            elif action=='save-structure':
                from .standard_routing_owner_service import save_structure
                result=save_structure(user=request.user,version_id=object_id,rows=data['rows'],expected_hash=data['expectedHash'],reason=data['reason'],key=data['idempotencyKey'])
            elif action=='successor':
                if set(data)-{'reason','idempotencyKey','testBomVersionId'}:raise ValueError('不接受调用者指定用途、状态或沿革。')
                result=RoutingVersionSuccessorService.create(source_id=object_id,user=request.user,
                    reason=data.get('reason'),idempotency_key=data.get('idempotencyKey'),test_bom_version_id=data.get('testBomVersionId'))
            elif action=='applicability':
                result=RoutingStepApplicabilityMaintenanceService.update(step_id=object_id,user=request.user,
                    idempotency_key=data.get('idempotencyKey'),mode=data.get('mode'),condition_code=data.get('conditionCode') or '',reason=data.get('reason') or '')
            elif action=='insert-operation':
                return Response({'code':'STANDARD_STRUCTURE_SERVICE_REQUIRED','message':'标准工序结构请通过企业基础资料的保存标准结构服务维护；旧补插入口已停止新增。','databaseBusinessWriteCount':0},status=409)
            elif action=='review':
                from .routing_version_review_service import review_routing_version
                result=review_routing_version(object_id=object_id,user=request.user,reason=data.get('reason'),idempotency_key=data.get('idempotencyKey'))
            elif action=='release':
                from .routing_version_release_service import release_routing_version
                result=release_routing_version(object_id=object_id,user=request.user,reason=data.get('reason'),idempotency_key=data.get('idempotencyKey'))
            else:return Response({'message':'未登记的标准路线动作。'},status=400)
            return Response({'result':result,'ownerLabel':'企业基础资料→工艺路线','factSource':'server'})
        except Exception as exc:
            if isinstance(exc,(ValueError,ValidationError,ObjectDoesNotExist,IntegrityError,ProtectedError)) or hasattr(exc,'code'):
                return Response({'code':getattr(exc,'code','FOUNDATION_ROUTING_REJECTED'),'message':str(exc),'databaseBusinessWriteCount':0},status=403 if getattr(exc,'code','') in ('SCOPE_DENIED','ORGANIZATION_SCOPE_DENIED','PERMISSION_DENIED') else 409)
            raise
