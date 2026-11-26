

# Native formal continuation: individually restored symbols; existing proofs preserved.
import re

from django.db import DatabaseError

from rest_framework.exceptions import APIException

from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView

from workflow_runtime.fact_loads import successful_fact_load_facts, failed_fact_load_facts

from .views import envelope

from .services import PlanningBusinessError

from .operation_resource_handoff_service import read_resource_handoffs, confirm_resource_handoff

SURFACES = ('apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts')

COUNTS = ('businessWriteCount', 'auditWriteCount', 'stateTransitionWriteCount',
    'resourceHandoffCreatedCount', 'idempotencyWriteCount', 'taskUpdatedCount',
    'workOrderUpdatedCount', 'originalReceiptUpdatedCount', 'operationSourceUpdatedCount',
    'masterDataUpdatedCount', 'actualStartCount', 'actualReportCount', 'completionCreatedCount',
    'inventoryUpdatedCount', 'scheduleUpdatedCount', 'downstreamReleasedCount')

class ResourceHandoffFactsView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'head', 'options']

    def result(self, facts=None, *, code=None, message=None, status=200, writes=None):
        tenant = str(facts['companyId']) if facts else str(getattr(self.request.user, 'company_id', ''))
        loaded = successful_fact_load_facts(request=self.request, api_url=self.request.path,
            tenant_id=tenant, result_count=facts.get('directoryResultCount',len(facts['operations']))) if code is None else failed_fact_load_facts(
                request=self.request, api_url=self.request.path, tenant_id=tenant,
                http_status=status, error_code=code, error_message=message)
        surface = {**loaded, 'resourceHandoffFacts': facts, 'passed': code is None,
            'resultCount': len(facts['operations']) if facts else None,
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
            if set(request.query_params) - {'workOrderId', 'operationId','responseMode','locateOwnLatestFormalAction'} or any(
                    len(request.query_params.getlist(key)) != 1 for key in request.query_params):
                raise PlanningBusinessError('RESOURCE_HANDOFF_QUERY_INVALID', '归属承接只读参数不符合正式合同。', http_status=400)
            params = {}
            for field, param in (('workOrderId', 'work_order_id'), ('operationId', 'operation_id')):
                raw = request.query_params.get(field)
                if raw is not None and (len(raw) > 18 or not re.fullmatch('[1-9][0-9]*', raw)):
                    raise PlanningBusinessError('RESOURCE_HANDOFF_QUERY_INVALID', '工单及工序身份须为正整数。', http_status=400)
                params[param] = int(raw) if raw else None
            params['response_mode']=request.query_params.get('responseMode')
            from .workshop_reception_read_projection import latest_own_action_flag
            params['locate_latest_own_action']=latest_own_action_flag(request.query_params.get('locateOwnLatestFormalAction'))
            return self.result(read_resource_handoffs(user=request.user, **params))
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code='RESOURCE_HANDOFF_READ_FAILED', message='工序归属事实暂未读取，请只读重新核对。', status=503)

class ResourceHandoffConfirmView(ResourceHandoffFactsView):
    http_method_names = ['post', 'options']

    def post(self, request, operation_id):
        try:
            if request.query_params:
                raise PlanningBusinessError('RESOURCE_HANDOFF_QUERY_INVALID', '归属承接意图不接受额外查询参数。', http_status=400)
            facts, writes = confirm_resource_handoff(user=request.user, operation_id=operation_id, payload=request.data)
            return self.result(facts, writes=writes)
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code='RESOURCE_HANDOFF_RESULT_UNVERIFIED',
                message='本次归属承接结果待核实，请只读重新核对，不重复操作。', status=503)
