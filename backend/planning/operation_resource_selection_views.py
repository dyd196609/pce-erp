

# Native formal continuation: individually restored symbols; existing proofs preserved.
import re

from django.db import DatabaseError

from rest_framework.exceptions import APIException

from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView

from workflow_runtime.fact_loads import successful_fact_load_facts,failed_fact_load_facts

from .views import envelope

from .services import PlanningBusinessError

from .operation_resource_selection_service import read_operation_resources,select_operation_resource,receive_operation

SURFACES=('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts')

COUNTS=('businessWriteCount','auditWriteCount','stateTransitionWriteCount','resourceSelectionCreatedCount',
    'preciseOperationReceiptCreatedCount','receiptAnchorCreatedCount','originalReceiptUpdatedCount','workOrderUpdatedCount',
    'operationSourceUpdatedCount','taskUpdatedCount','actualStartCount','actualReportCount','completionCreatedCount',
    'masterDataUpdatedCount','inventoryUpdatedCount','scheduleUpdatedCount','resourceOccupancyReleasedCount')

class OperationResourceFactsView(APIView):
    permission_classes=[IsAuthenticated]
    http_method_names=['get','head','options']

    def result(self,facts=None,*,code=None,message=None,status=200,writes=None):
        tenant=str(facts['companyId']) if facts else str(getattr(self.request.user,'company_id',''))
        loaded=successful_fact_load_facts(request=self.request,api_url=self.request.path,tenant_id=tenant,
            result_count=facts.get('directoryResultCount',len(facts['operations']))) if code is None else failed_fact_load_facts(request=self.request,
                api_url=self.request.path,tenant_id=tenant,http_status=status,error_code=code,error_message=message)
        surface={**loaded,'operationResourceFacts':facts,'passed':code is None,
            'resultCount':len(facts['operations']) if facts else None,**{key:0 if code is None else None for key in COUNTS}}
        if writes and code is None:surface.update(writes)
        return envelope({**surface,'factLoadFacts':loaded,**{key:dict(surface) for key in SURFACES}},
            error={'code':code,'message':message} if code else None,http_status=status)

    def handle_exception(self,exc):
        if isinstance(exc,APIException):return self.result(code=str(exc.default_code),message=str(exc.detail),status=exc.status_code)
        return super().handle_exception(exc)

    def get(self,request):
        try:
            readback_fields={'actionCode','selectionVersion','receiptVersion','requestHash','requestKeyHash'}
            if set(request.query_params)-({'workOrderId','operationId','workCenterId','responseMode','locateOwnLatestFormalAction'}|readback_fields) or any(
                    len(request.query_params.getlist(key))!=1 for key in request.query_params):
                raise PlanningBusinessError('OPERATION_RESOURCE_QUERY_INVALID','资源只读参数不符合正式合同。',http_status=400)
            params={}
            for field,param in (('workOrderId','work_order_id'),('operationId','operation_id'),('workCenterId','work_center_id')):
                raw=request.query_params.get(field)
                if raw is not None and (len(raw)>18 or not re.fullmatch('[1-9][0-9]*',raw)):
                    raise PlanningBusinessError('OPERATION_RESOURCE_QUERY_INVALID','工单、工序及明确工作中心身份须为正整数。',http_status=400)
                params[param]=int(raw) if raw else None
            params['response_mode']=request.query_params.get('responseMode')
            from .workshop_reception_read_projection import latest_own_action_flag
            params['locate_latest_own_action']=latest_own_action_flag(request.query_params.get('locateOwnLatestFormalAction'))
            supplied=readback_fields & set(request.query_params)
            if supplied:
                if supplied!=readback_fields or params['work_order_id'] is None or params['operation_id'] is None:
                    raise PlanningBusinessError('OPERATION_RESOURCE_READBACK_QUERY_INVALID','原请求只读核查须完整提供工单、准确工序、动作、选择／接收版本及原请求标识。',http_status=400)
                query={key:request.query_params[key] for key in readback_fields}
                for key in ('selectionVersion','receiptVersion'):
                    if len(query[key])>18 or not re.fullmatch('0|[1-9][0-9]*',query[key]):
                        raise PlanningBusinessError('OPERATION_RESOURCE_READBACK_QUERY_INVALID','原请求选择或接收版本须为非负整数。',http_status=400)
                    query[key]=int(query[key])
                params['readback_query']=query
            return self.result(read_operation_resources(user=request.user,**params))
        except PlanningBusinessError as error:return self.result(code=error.code,message=error.message,status=error.http_status)
        except DatabaseError:return self.result(code='OPERATION_RESOURCE_READ_FAILED',message='资源及精确接收事实暂未读取，请只读重新核对。',status=503)

class OperationResourceSelectView(OperationResourceFactsView):
    http_method_names=['post','options']
    operation=staticmethod(select_operation_resource)
    def post(self,request,operation_id):
        try:
            if request.query_params:raise PlanningBusinessError('OPERATION_RESOURCE_QUERY_INVALID','正式资源意图不接受额外查询参数。',http_status=400)
            facts,writes=self.operation(user=request.user,operation_id=operation_id,payload=request.data)
            return self.result(facts,writes=writes)
        except PlanningBusinessError as error:return self.result(code=error.code,message=error.message,status=error.http_status)
        except DatabaseError:return self.result(code='OPERATION_RESOURCE_RESULT_UNVERIFIED',
            message='本次资源选择或精确接收结果待核实，请只读回查，不自动重试。',status=503)

class OperationResourceReceiveView(OperationResourceSelectView):
    operation=staticmethod(receive_operation)
