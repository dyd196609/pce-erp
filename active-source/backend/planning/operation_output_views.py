from pde.routing_read_context import routing_read_request
from django.db import DatabaseError,IntegrityError
from .operation_handover_views import OperationHandoverFactsView
from .services import PlanningBusinessError
from .operation_predecessor_authority import verification_context

class OperationOutputFactsView(OperationHandoverFactsView):
    fact_key='operationOutputFacts';list_key='outputs'
    def read(self,request,**kwargs):
        from .operation_handover_facts import read_operation_outputs
        return read_operation_outputs(user=request.user,**kwargs)
    @routing_read_request
    def get(self,request):
        try:
            names={'outputId':'output_id','taskId':'task_id','workOrderId':'work_order_id',
                'recoveryAction':'recovery_action','requestHash':'request_hash','requestKeyHash':'request_key_hash'}
            if set(request.query_params)-set(names) or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
                raise PlanningBusinessError('OUTPUT_QUERY_INVALID','只读参数不符合正式产出合同。',http_status=400)
            values={}
            for key,value in request.query_params.items():
                if key.endswith('Id'):
                    if not value.isascii() or not value.isdigit() or value.startswith('0') or len(value)>18:
                        raise PlanningBusinessError('OUTPUT_QUERY_INVALID','准确对象须为正整数。',http_status=400)
                    value=int(value)
                values[names[key]]=value
            with verification_context():
                return self.result(self.read(request,**values))
        except PlanningBusinessError as e:return self.result(code=e.code,message=e.message,status=e.http_status)
        except DatabaseError:return self.result(code='OUTPUT_READ_FAILED',message='正式产出读取失败，可只读重查。',status=503)
    def post(self,request,output_id=None):
        try:
            if request.query_params:raise PlanningBusinessError('OUTPUT_QUERY_INVALID','正式产出写入不接受查询参数。',http_status=400)
            from .operation_output_service import execute_output
            with verification_context():
                facts,writes=execute_output(user=request.user,action=self.action,payload=request.data,output_id=output_id)
                return self.result(facts,writes=writes)
        except PlanningBusinessError as e:return self.result(code=e.code,message=e.message,status=e.http_status)
        except IntegrityError:return self.result(code='OUTPUT_RESULT_UNVERIFIED',message='数据库约束冲突，本次原意图结果待核实；请保留原标识只读核查，禁止重复提交。',status=503)
        except DatabaseError:return self.result(code='OUTPUT_RESULT_UNVERIFIED',message='产出操作结果待核实，禁止重复提交，请按原请求只读核查。',status=503)

class OperationOutputConfirmView(OperationOutputFactsView):action='confirm';http_method_names=['post','options']
class OperationOutputExcessReportView(OperationOutputConfirmView):action='excess.report'
class OperationOutputExcessReviewView(OperationOutputConfirmView):action='excess.review'
class OperationOutputCorrectionView(OperationOutputConfirmView):action='correct'
