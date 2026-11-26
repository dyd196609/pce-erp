

# Native formal continuation: individually restored symbols; existing proofs preserved.
import re

from django.db import DatabaseError

from rest_framework.exceptions import APIException

from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView

from workflow_runtime.fact_loads import successful_fact_load_facts, failed_fact_load_facts

from .services import PlanningBusinessError

from .views import envelope

from .operation_start_service import read_operation_starts, start_operation

SURFACES = ('apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts')

COUNTS = ('businessWriteCount', 'auditWriteCount', 'actualDispatchCount', 'actualStartCount', 'actualReportCount',
    'resourceOccupancyReleasedCount', 'workOrderUpdatedCount', 'operationSourceUpdatedCount', 'taskUpdatedCount',
    'scheduleUpdatedCount', 'inventoryUpdatedCount', 'stateTransitionWriteCount', 'operationStartCreatedCount')

class OperationStartFactsView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'head', 'options']

    def result(self, facts=None, *, code=None, message=None, status=200, writes=None):
        tenant = str(facts['companyId']) if facts else str(getattr(self.request.user, 'company_id', ''))
        loaded = successful_fact_load_facts(request=self.request, api_url=self.request.path, tenant_id=tenant,
            result_count=len(facts['tasks'])) if code is None else failed_fact_load_facts(request=self.request,
                api_url=self.request.path, tenant_id=tenant, http_status=status, error_code=code, error_message=message)
        surface = {**loaded, 'operationStartFacts': facts, 'passed': code is None,
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

    def get(self, request):
        try:
            if set(request.query_params) - {'taskId'} or any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
                raise PlanningBusinessError('OPERATION_START_QUERY_INVALID', '只读参数不符合正式开工合同。', http_status=400)
            raw = request.query_params.get('taskId')
            if raw is not None and not re.fullmatch('[1-9][0-9]*', raw):
                raise PlanningBusinessError('OPERATION_START_QUERY_INVALID', '任务身份须为正整数。', http_status=400)
            return self.result(read_operation_starts(user=request.user, task_id=int(raw) if raw else None))
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code='OPERATION_START_READ_FAILED', message='工序开工事实暂未读取，请核对正式结构部署。', status=503)

class OperationStartView(OperationStartFactsView):
    http_method_names = ['post', 'options']

    def post(self, request, task_id):
        try:
            if request.query_params:
                raise PlanningBusinessError('OPERATION_START_QUERY_INVALID', '开工意图不接受额外查询参数。', http_status=400)
            facts, writes = start_operation(user=request.user, task_id=task_id, payload=request.data)
            return self.result(facts, writes=writes)
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code='OPERATION_START_RESULT_UNVERIFIED',
                message='开工结果尚未核实，请只读重新读取事实，不会自动重放。', status=503)
