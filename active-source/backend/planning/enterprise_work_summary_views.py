from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import APIException
from django.db import DatabaseError
from workflow_runtime.fact_loads import successful_fact_load_facts,failed_fact_load_facts
from pde.routing_read_context import routing_read_request
from .enterprise_work_summary import read_summary
from .services import PlanningBusinessError
from pde.order_routing_execution_service import ArrangementError
from .views import envelope

class EnterpriseWorkSummaryView(APIView):
    permission_classes=[IsAuthenticated]
    http_method_names=['get','head','options']
    def failure(self,code,message,status):
        load=failed_fact_load_facts(request=self.request,api_url=self.request.path,tenant_id=str(getattr(self.request.user,'company_id','')),http_status=status,error_code=code,error_message=message)
        return envelope({**load,'summary':None,'passed':False},error={'code':code,'message':message},http_status=status)
    def handle_exception(self,e):
        if isinstance(e,APIException):return self.failure(str(e.default_code),str(e.detail),e.status_code)
        return super().handle_exception(e)
    @routing_read_request
    def get(self,request):
        if request.query_params:return self.failure('HOME_QUERY_INVALID','首页摘要不接受客户端企业、人员或权限参数。',400)
        try:
            facts=read_summary(request.user)
            load=successful_fact_load_facts(request=request,api_url=request.path,tenant_id=str(facts['companyId']),result_count=facts['total'])
            return envelope({**load,'summary':facts,'passed':True})
        except PlanningBusinessError as e:return self.failure(e.code,e.message,e.http_status)
        except ArrangementError as e:return self.failure(e.code,str(e),getattr(e,'http_status',403))
        except DatabaseError:return self.failure('HOME_READ_FAILED','工作摘要读取失败；数量暂不可用。',503)
