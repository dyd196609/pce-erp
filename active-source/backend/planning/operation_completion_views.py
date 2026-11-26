from pde.routing_read_context import routing_read_request
"""One formal fact envelope and explicit completion request/review intents."""
import re
from django.db import DatabaseError
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from workflow_runtime.fact_loads import successful_fact_load_facts, failed_fact_load_facts
from .views import envelope
from .services import PlanningBusinessError
from .operation_completion_service import read_operation_completions, execute_completion
from .operation_predecessor_authority import verification_context
from .mes_test_source_bridge import allocation_admission_context

SURFACES=('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts')
COUNTS=('businessWriteCount','auditWriteCount','stateTransitionWriteCount','completionRequestCreatedCount',
    'completionCreatedCount','approvalDecisionCreatedCount','actualReportCount','actualStartCount','taskUpdatedCount',
    'workOrderUpdatedCount','operationSourceUpdatedCount','resourceOccupancyReleasedCount','scheduleUpdatedCount',
    'inventoryUpdatedCount','downstreamReleasedCount','completionGenerationCreatedCount','workflowClosureCreatedCount',
    'quantityAccountCASWriteCount')

class OperationCompletionFactsView(APIView):
    permission_classes=[IsAuthenticated]
    http_method_names=['get','head','options']
    def result(self,facts=None,*,code=None,message=None,status=200,writes=None):
        tenant=str(facts['companyId']) if facts else str(getattr(self.request.user,'company_id',''))
        loaded=successful_fact_load_facts(request=self.request,api_url=self.request.path,tenant_id=tenant,result_count=len(facts['tasks'])) if code is None else failed_fact_load_facts(request=self.request,api_url=self.request.path,tenant_id=tenant,http_status=status,error_code=code,error_message=message)
        surface={**loaded,'operationCompletionFacts':facts,'passed':code is None and not (facts or {}).get('taskReadFailures'),
            'resultCount':len(facts['tasks']) if facts else None,**{key:0 if code is None else None for key in COUNTS}}
        if writes and code is None:surface.update(writes)
        return envelope({**surface,'factLoadFacts':loaded,**{key:dict(surface) for key in SURFACES}},
            error={'code':code,'message':message} if code else None,http_status=status)
    def handle_exception(self,exc):
        if isinstance(exc,APIException):return self.result(code=str(exc.default_code),message=str(exc.detail),status=exc.status_code)
        return super().handle_exception(exc)
    @routing_read_request
    def get(self,request):
        try:
            recovery={'actionCode','requestHash','requestKeyHash','generationId'}
            if set(request.query_params)-({'taskId','workOrderId'}|recovery) or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
                raise PlanningBusinessError('OPERATION_COMPLETION_QUERY_INVALID','只读参数不符合工序完工合同。',http_status=400)
            raw=request.query_params.get('taskId')
            if raw is not None and (len(raw)>18 or not re.fullmatch('[1-9][0-9]*',raw)):
                raise PlanningBusinessError('OPERATION_COMPLETION_QUERY_INVALID','任务身份须为正整数。',http_status=400)
            query=None
            if recovery & set(request.query_params):
                from .operation_completion_v3_authority import REQUEST_ACTION,APPROVE_ACTION,WITHDRAW_ACTION
                generation=request.query_params.get('generationId','')
                if (not raw or not recovery.issubset(set(request.query_params))
                        or request.query_params.get('actionCode') not in (REQUEST_ACTION,APPROVE_ACTION,WITHDRAW_ACTION)
                        or not re.fullmatch('0|[1-9][0-9]{0,17}',generation)
                        or any(not re.fullmatch('[a-f0-9]{64}',request.query_params.get(k,'')) for k in ('requestHash','requestKeyHash'))):
                    raise PlanningBusinessError('OPERATION_COMPLETION_RECOVERY_QUERY_INVALID','原意图只读核查须完整指定动作、准确原代次及请求Hash。',http_status=400)
                query={k:request.query_params[k] for k in recovery};query['generationId']=int(generation)
            with allocation_admission_context(user=request.user),verification_context():
                raw_order=request.query_params.get('workOrderId')
                if raw_order is not None and not re.fullmatch('[1-9][0-9]{0,17}',raw_order):raise PlanningBusinessError('OPERATION_COMPLETION_QUERY_INVALID','工单须为准确正整数。',http_status=400)
                return self.result(read_operation_completions(user=request.user,task_id=int(raw) if raw else None,readback_query=query,work_order_id=int(raw_order) if raw_order else None))
        except PlanningBusinessError as error:return self.result(code=error.code,message=error.message,status=error.http_status)
        except DatabaseError:return self.result(code='OPERATION_COMPLETION_READ_FAILED',message='工序完工事实暂未读取，请重新读取。',status=503)

class OperationCompletionRequestView(OperationCompletionFactsView):
    http_method_names=['post','options']
    action='request'
    def post(self,request,task_id):
        try:
            if request.query_params:raise PlanningBusinessError('OPERATION_COMPLETION_QUERY_INVALID','完工意图不接受额外查询参数。',http_status=400)
            with verification_context():
                facts,writes=execute_completion(user=request.user,task_id=task_id,payload=request.data,action=self.action)
                return self.result(facts,writes=writes)
        except PlanningBusinessError as error:return self.result(code=error.code,message=error.message,status=error.http_status)
        except DatabaseError:return self.result(code='OPERATION_COMPLETION_RESULT_UNVERIFIED',message='本次完工申请或审核结果待核实，请只读重新读取，不重复操作。',status=503)

class OperationCompletionApproveView(OperationCompletionRequestView):
    action='approve'


class OperationCompletionWithdrawReplaceView(OperationCompletionRequestView):
    action='withdrawReplace'


class OperationCompletionDirectoryView(OperationCompletionFactsView):
    """Versioned read-only summary; the detail/error envelope stays intact."""
    @routing_read_request
    def get(self,request):
        try:
            if set(request.query_params)-{'workOrderId'} or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
                raise PlanningBusinessError('OPERATION_COMPLETION_QUERY_INVALID','目录只接受准确工单筛选。',http_status=400)
            raw=request.query_params.get('workOrderId')
            if raw is not None and not re.fullmatch('[1-9][0-9]{0,17}',raw):
                raise PlanningBusinessError('OPERATION_COMPLETION_QUERY_INVALID','工单须为准确正整数。',http_status=400)
            from .operation_completion_service import read_operation_completion_directory
            with allocation_admission_context(user=request.user),verification_context():
                return self.result(read_operation_completion_directory(user=request.user,work_order_id=int(raw) if raw else None))
        except PlanningBusinessError as error:return self.result(code=error.code,message=error.message,status=error.http_status)
        except DatabaseError:return self.result(code='OPERATION_COMPLETION_READ_FAILED',message='工序目录暂未读取，请重新读取。',status=503)
