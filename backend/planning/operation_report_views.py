from pde.routing_read_context import routing_read_request
"""Authenticated self-task facts and one explicit actual-quantity intent."""
import re
from django.db import DatabaseError
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from workflow_runtime.fact_loads import successful_fact_load_facts, failed_fact_load_facts
from .services import PlanningBusinessError
from pde.order_routing_execution_service import ArrangementError
from .views import envelope
from .operation_report_service import read_operation_reports, report_operation

SURFACES = ('apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts')
COUNTS = ('businessWriteCount', 'auditWriteCount', 'actualDispatchCount', 'actualStartCount', 'actualReportCount',
    'actualExecutionConfirmationCount', 'operationExecutionConfirmationCreatedCount',
    'resourceOccupancyReleasedCount', 'workOrderUpdatedCount', 'operationSourceUpdatedCount', 'taskUpdatedCount',
    'scheduleUpdatedCount', 'inventoryUpdatedCount', 'stateTransitionWriteCount', 'operationReportCreatedCount', 'completionCreatedCount')


class OperationReportFactsView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'head', 'options']

    def result(self, facts=None, *, code=None, message=None, status=200, writes=None):
        tenant = str(facts['companyId']) if facts else str(getattr(self.request.user, 'company_id', ''))
        loaded = successful_fact_load_facts(request=self.request, api_url=self.request.path, tenant_id=tenant,
            result_count=len(facts['tasks'])) if code is None else failed_fact_load_facts(request=self.request,
                api_url=self.request.path, tenant_id=tenant, http_status=status, error_code=code, error_message=message)
        surface = {**loaded, 'operationReportFacts': facts, 'passed': code is None,
            'resultCount': len(facts['tasks']) if facts else None,
            **{key: 0 if code is None else None for key in COUNTS}}
        if writes and code is None:
            surface.update(writes)
        return envelope({**surface, 'factLoadFacts': loaded, **{key: dict(surface) for key in SURFACES}},
            error={'code': code, 'message': message} if code else None, http_status=status)

    def handle_exception(self, exc):
        if isinstance(exc, APIException):
            return self.result(code=str(exc.default_code), message=str(exc.detail), status=exc.status_code)
        return super().handle_exception(exc)

    @routing_read_request
    def get(self,request):
        try:
            if set(request.query_params) - {'taskId','workOrderId'} or any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
                raise PlanningBusinessError('OPERATION_REPORT_QUERY_INVALID', '只读参数不符合正式报工合同。', http_status=400)
            raw = request.query_params.get('taskId')
            if raw is not None and (len(raw) > 18 or not re.fullmatch('[1-9][0-9]*', raw)):
                raise PlanningBusinessError('OPERATION_REPORT_QUERY_INVALID', '任务身份须为正整数。', http_status=400)
            raw_order=request.query_params.get('workOrderId')
            if raw_order is not None and not re.fullmatch('[1-9][0-9]{0,17}',raw_order):raise PlanningBusinessError('OPERATION_REPORT_QUERY_INVALID','工单须为准确正整数。',http_status=400)
            return self.result(read_operation_reports(user=request.user, task_id=int(raw) if raw else None,work_order_id=int(raw_order) if raw_order else None))
        except (PlanningBusinessError, ArrangementError) as error:
            return self.result(code=error.code, message=getattr(error, 'message', str(error)), status=getattr(error, 'http_status', 409))
        except DatabaseError:
            return self.result(code='OPERATION_REPORT_READ_FAILED', message='工序报工事实暂未读取，请核对正式结构部署。', status=503)


class OperationReportView(OperationReportFactsView):
    http_method_names = ['post', 'options']

    def post(self, request, task_id):
        try:
            if request.query_params:
                raise PlanningBusinessError('OPERATION_REPORT_QUERY_INVALID', '报工意图不接受额外查询参数。', http_status=400)
            facts, writes = report_operation(user=request.user, task_id=task_id, payload=request.data)
            return self.result(facts, writes=writes)
        except (PlanningBusinessError, ArrangementError) as error:
            return self.result(code=error.code, message=getattr(error, 'message', str(error)), status=getattr(error, 'http_status', 409))
        except DatabaseError:
            return self.result(code='OPERATION_REPORT_RESULT_UNVERIFIED',
                message='报工结果尚未核实，请只读重新读取事实，不会自动重放。', status=503)


class OperationExecutionConfirmationView(OperationReportFactsView):
    http_method_names = ['post', 'options']

    def post(self, request, task_id):
        from .operation_execution_confirmation_service import confirm_execution
        try:
            if request.query_params:
                raise PlanningBusinessError('OPERATION_EXECUTION_QUERY_INVALID', '实际经过登记不接受额外查询参数。', http_status=400)
            facts, writes = confirm_execution(user=request.user, task_id=task_id, payload=request.data)
            return self.result(facts, writes=writes)
        except (PlanningBusinessError, ArrangementError) as error:
            return self.result(code=error.code, message=getattr(error, 'message', str(error)), status=getattr(error, 'http_status', 409))
        except DatabaseError:
            return self.result(code='OPERATION_EXECUTION_RESULT_UNVERIFIED',
                message='实际经过结果尚未核实，请只读回查，不会自动重试。', status=503)
