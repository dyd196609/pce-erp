from pde.routing_read_context import routing_read_request
"""Native handover intent endpoints and five identical server fact surfaces."""
from django.db import DatabaseError,IntegrityError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.exceptions import APIException
from workflow_runtime.fact_loads import successful_fact_load_facts,failed_fact_load_facts
from .views import envelope
from .services import PlanningBusinessError
from .operation_predecessor_authority import verification_context

class OperationHandoverFactsView(APIView):
    permission_classes=[IsAuthenticated]
    fact_key='operationHandoverFacts';list_key='handovers';action=None
    http_method_names=['get','head','options']
    def read(self,request,**kwargs):
        from .operation_handover_facts import read_operation_handovers
        business_no=kwargs.pop('business_no',None)
        if business_no is not None:
            from .operation_handover_number import lookup_handover
            header=lookup_handover(request.user,business_no)
            if kwargs.get('handover_id') not in (None,header.pk):
                raise PlanningBusinessError('HANDOVER_QUERY_OBJECT_MISMATCH','业务编号与所选交接单冲突。',http_status=400)
            kwargs['handover_id']=header.pk
        return read_operation_handovers(user=request.user,**kwargs)
    def execute(self,request,**kwargs):
        from .operation_handover_service import execute_handover
        return execute_handover(user=request.user,action=self.action,payload=request.data,**kwargs)
    def result(self,facts=None,*,code=None,message=None,status=200,writes=None):
        tenant=str(getattr(self.request.user,'company_id',''))
        count=len(facts[self.list_key]) if facts else 0
        load=(successful_fact_load_facts(request=self.request,api_url=self.request.path,tenant_id=tenant,result_count=count)
            if code is None else failed_fact_load_facts(request=self.request,api_url=self.request.path,tenant_id=tenant,
                http_status=status,error_code=code,error_message=message))
        surface={**load,self.fact_key:facts,'passed':code is None,'resultCount':count if code is None else None,
            **{key:0 if code is None else None for key in ('businessWriteCount','auditWriteCount','stateTransitionWriteCount',
                'actualReportCount','actualStartCount','inventoryUpdatedCount','downstreamReleasedCount')}}
        if writes and code is None:surface.update(writes)
        return envelope({**surface,'factLoadFacts':load,**{key:dict(surface) for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts')}},
            error={'code':code,'message':message} if code else None,http_status=status)
    def handle_exception(self,error):
        if isinstance(error,APIException):return self.result(code=str(error.default_code),message=str(error.detail),status=error.status_code)
        return super().handle_exception(error)
    @routing_read_request
    def get(self,request):
        names={'taskId':'task_id','workOrderId':'work_order_id','handoverId':'handover_id','outputId':'output_id','exceptionId':'exception_id',
            'custodyWorkCenterId':'custody_work_center_id','sliceId':'slice_id',
            'direction':'direction','recoveryAction':'recovery_action','requestHash':'request_hash','requestKeyHash':'request_key_hash'}
        if self.fact_key=='operationHandoverFacts':names['businessNo']='business_no'
        try:
            if set(request.query_params)-set(names) or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
                raise PlanningBusinessError('HANDOVER_QUERY_INVALID','只读查询参数不符合工序交接合同。',http_status=400)
            values={}
            for key,value in request.query_params.items():
                if key.endswith('Id'):
                    if not value.isascii() or not value.isdigit() or value.startswith('0') or len(value)>18:raise PlanningBusinessError('HANDOVER_QUERY_INVALID','对象身份须为准确正整数。',http_status=400)
                    value=int(value)
                values[names[key]]=value
            with verification_context():
                return self.result(self.read(request,**values))
        except PlanningBusinessError as e:return self.result(code=e.code,message=e.message,status=e.http_status)
        except DatabaseError:return self.result(code='HANDOVER_READ_FAILED',message='工序交接事实读取失败，可明确只读重读。',status=503)
    def post(self,request,handover_id=None,exception_id=None):
        try:
            if request.query_params:raise PlanningBusinessError('HANDOVER_QUERY_INVALID','正式写意图不接受查询参数。',http_status=400)
            with verification_context():
                facts,writes=self.execute(request,handover_id=handover_id,exception_id=exception_id)
                return self.result(facts,writes=writes)
        except PlanningBusinessError as e:return self.result(code=e.code,message=e.message,status=e.http_status)
        except IntegrityError:return self.result(code='HANDOVER_RESULT_UNVERIFIED',message='数据库约束冲突，本次原意图结果待核实；请保留原标识只读核查，禁止重复提交。',status=503)
        except DatabaseError:return self.result(code='HANDOVER_RESULT_UNVERIFIED',message='本次结果待核实，禁止重复提交；请按原动作只读核查。',status=503)

class OperationHandoverPrepareView(OperationHandoverFactsView):action='prepare';http_method_names=['post','options']
class OperationHandoverDispatchView(OperationHandoverPrepareView):action='dispatch'
class OperationHandoverCancelView(OperationHandoverPrepareView):action='cancel'
class OperationHandoverReceiveView(OperationHandoverPrepareView):action='receive'
class OperationHandoverForwardView(OperationHandoverPrepareView):action='forward'
class OperationHandoverReturnView(OperationHandoverPrepareView):action='return'
class OperationHandoverExceptionView(OperationHandoverPrepareView):action='exception.submit'
class OperationHandoverExceptionConfirmView(OperationHandoverPrepareView):action='exception.confirm'
class OperationHandoverInputConfirmView(OperationHandoverPrepareView):action='input.confirm'
class OperationHandoverRangeReleaseView(OperationHandoverPrepareView):action='range.release'
class OperationHandoverRangeReceiveView(OperationHandoverPrepareView):action='range.receive'
