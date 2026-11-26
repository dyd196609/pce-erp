

# Native formal continuation: individually restored symbols; existing proofs preserved.
import re

from django.db import DatabaseError

from rest_framework.exceptions import APIException

from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView

from workflow_runtime.fact_loads import successful_fact_load_facts, failed_fact_load_facts

from .services import PlanningBusinessError

from .views import envelope

from .workshop_task_service import read_workshop_tasks, save_task_draft, dispatch_task

SURFACES = ('apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts')

class WorkshopTaskFactsView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'head', 'options']

    def result(self, facts=None, *, code=None, message=None, status=200, writes=None):
        tenant = str(facts['companyId']) if facts else str(getattr(self.request.user, 'company_id', ''))
        loaded = successful_fact_load_facts(request=self.request, api_url=self.request.path, tenant_id=tenant,
            result_count=len(facts['tasks'])) if code is None else failed_fact_load_facts(request=self.request,
                api_url=self.request.path, tenant_id=tenant, http_status=status, error_code=code, error_message=message)
        surface = {**loaded, 'workshopTaskFacts': facts, 'passed': code is None,
            'resultCount': len(facts['tasks']) if facts else None, 'businessWriteCount': 0, 'auditWriteCount': 0,
            'actualDispatchCount': 0, 'actualStartCount': 0, 'actualReportCount': 0,
            'resourceOccupancyReleasedCount': 0, 'workOrderUpdatedCount': 0, 'operationSourceUpdatedCount': 0}
        if writes:
            surface.update(writes)
        if code is not None:
            for key in ('businessWriteCount', 'auditWriteCount', 'actualDispatchCount', 'actualStartCount',
                    'actualReportCount', 'resourceOccupancyReleasedCount', 'workOrderUpdatedCount', 'operationSourceUpdatedCount'):
                surface[key] = None
        return envelope({**surface, 'factLoadFacts': loaded, **{key: dict(surface) for key in SURFACES}},
            error={'code': code, 'message': message} if code else None, http_status=status)

    def handle_exception(self, exc):
        if isinstance(exc, APIException):
            return self.result(code=str(exc.default_code), message=str(exc.detail), status=exc.status_code)
        return super().handle_exception(exc)

    def get(self, request):
        try:
            if set(request.query_params) - {'workOrderId', 'operationId'} or any(
                    len(request.query_params.getlist(key)) != 1 for key in request.query_params):
                raise PlanningBusinessError('WORKSHOP_TASK_QUERY_INVALID', '只读参数不符合正式合同。', http_status=400)
            selected = {}
            for key, target in (('workOrderId', 'work_order_id'), ('operationId', 'operation_id')):
                raw = request.query_params.get(key)
                if raw is not None and not re.fullmatch('[1-9][0-9]*', raw):
                    raise PlanningBusinessError('WORKSHOP_TASK_QUERY_INVALID', '工单和工序身份须为正整数。', http_status=400)
                selected[target] = int(raw) if raw else None
            return self.result(read_workshop_tasks(user=request.user, **selected))
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)

        except DatabaseError:
            return self.result(code='WORKSHOP_TASK_READ_FAILED', message='车间任务事实暂未读取，请核对正式结构部署。', status=503)

class WorkshopTaskDraftView(WorkshopTaskFactsView):
    http_method_names = ['post', 'options']

    def post(self, request):
        try:
            if request.query_params:
                raise PlanningBusinessError('WORKSHOP_TASK_QUERY_INVALID', '保存意图不接受额外查询参数。', http_status=400)
            facts, writes = save_task_draft(user=request.user, payload=request.data)
            return self.result(facts, writes=writes)
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code='WORKSHOP_TASK_RESULT_UNVERIFIED',
                message='任务保存结果尚未核实，请先只读刷新；不会自动重试。', status=503)

class WorkshopTaskDispatchView(WorkshopTaskFactsView):
    http_method_names = ['post', 'options']

    def post(self, request, task_id):
        try:
            if request.query_params:
                raise PlanningBusinessError('WORKSHOP_TASK_QUERY_INVALID', '派工意图不接受额外查询参数。', http_status=400)
            facts, writes = dispatch_task(user=request.user, task_id=task_id, payload=request.data)
            return self.result(facts, writes=writes)
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code='WORKSHOP_TASK_RESULT_UNVERIFIED',
                message='派工结果尚未核实，请先只读刷新；不会自动重试。', status=503)
