from pde.routing_read_context import routing_read_request
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import APIException
from django.db import DatabaseError
from workflow_runtime.fact_loads import successful_fact_load_facts,failed_fact_load_facts
from .views import envelope
from .services import PlanningBusinessError
from .finished_goods_service import read_finished_goods,execute_finished_goods
from pde.order_routing_execution_service import ArrangementError

class FinishedGoodsFactsView(APIView):
    permission_classes=[IsAuthenticated]
    http_method_names=['get','head','options']
    action=None
    def result(self,facts=None,*,code=None,message=None,status=200,writes=None):
        count=len(facts['transfers']) if facts else None
        tenant=str(getattr(self.request.user,'company_id',''))
        load=successful_fact_load_facts(request=self.request,api_url=self.request.path,tenant_id=tenant,result_count=count or 0) if code is None else failed_fact_load_facts(
            request=self.request,api_url=self.request.path,tenant_id=tenant,http_status=status,error_code=code,error_message=message)
        surface={**load,'finishedGoodsFacts':facts,'resultCount':count if code is None else None,
            'passed':code is None and bool(facts and facts['passed']),
            **{key:0 if code is None else None for key in ('businessWriteCount','auditWriteCount','stateTransitionWriteCount','actualStartCount','actualReportCount','inventoryUpdatedCount','resourceOccupancyReleasedCount')}}
        if writes and code is None:surface.update(writes)
        return envelope({**surface,'factLoadFacts':load,**{key:dict(surface) for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts')}},
            error={'code':code,'message':message} if code else None,http_status=status)
    def handle_exception(self,error):
        if isinstance(error,APIException):return self.result(code=str(error.default_code),message=str(error.detail),status=error.status_code)
        return super().handle_exception(error)
    @routing_read_request
    def get(self,request):
        names={'workOrderId':'work_order_id','transferId':'transfer_id','recoveryAction':'recovery_action','requestHash':'request_hash','requestKeyHash':'request_key_hash'}
        try:
            if set(request.query_params)-set(names) or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
                raise PlanningBusinessError('FG_QUERY_INVALID','成品只读查询字段不符合合同。',http_status=400)
            values={}
            for key,value in request.query_params.items():
                if key.endswith('Id'):
                    if not value.isascii() or not value.isdigit() or value.startswith('0') or len(value)>18:raise PlanningBusinessError('FG_QUERY_INVALID','对象ID须为准确正整数。',http_status=400)
                    value=int(value)
                values[names[key]]=value
            from .completed_closure_read_cache import completed_closure_read_scope
            with completed_closure_read_scope():
                return self.result(read_finished_goods(user=request.user,**values))
        except PlanningBusinessError as exc:return self.result(code=exc.code,message=exc.message,status=exc.http_status)
        except ArrangementError as exc:return self.result(code=exc.code,message=str(exc),status=403 if exc.code=='SCOPE_DENIED' else 409)
        except DatabaseError:return self.result(code='FG_READ_FAILED',message='成品交接与入库读取失败，请明确只读重读。',status=503)
    def post(self,request,transfer_id=None):
        try:
            if request.query_params:raise PlanningBusinessError('FG_QUERY_INVALID','成品写意图不接受查询参数。',http_status=400)
            facts,writes=execute_finished_goods(user=request.user,action=self.action,payload=request.data,transfer_id=transfer_id)
            return self.result(facts,writes=writes)
        except PlanningBusinessError as exc:return self.result(code=exc.code,message=exc.message,status=exc.http_status)
        except ArrangementError as exc:return self.result(code=exc.code,message=str(exc),status=403 if exc.code=='SCOPE_DENIED' else 409)
        except DatabaseError:return self.result(code='FG_RESULT_UNVERIFIED',message='本次原意图结果待核实，禁止重复提交或换标识重试；请按原请求只读回查。',status=503)

class FinishedGoodsPrepareView(FinishedGoodsFactsView):action='prepare';http_method_names=['post','options']
class FinishedGoodsDispatchView(FinishedGoodsPrepareView):action='dispatch'
class FinishedGoodsCancelView(FinishedGoodsPrepareView):action='cancel'
class FinishedGoodsReceiveView(FinishedGoodsPrepareView):action='receive'
