

# Native formal continuation: individually restored symbols; existing proofs preserved.
import re

from django.db import DatabaseError

from rest_framework.exceptions import APIException

from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView

from workflow_runtime.fact_loads import successful_fact_load_facts, failed_fact_load_facts

from .services import PlanningBusinessError

from .views import envelope

from .work_order_workshop_receipt_service import read_workshop_reception, receive_workshop_scope

SURFACES = ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts")

class ProductionWorkOrderWorkshopReceptionView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def result(self, facts=None, *, code=None, message=None, status=200, writes=None):
        tenant = str(facts["companyId"]) if facts else str(getattr(self.request.user, "company_id", ""))
        loaded = successful_fact_load_facts(request=self.request, api_url=self.request.path, tenant_id=tenant,
            result_count=1) if code is None else failed_fact_load_facts(request=self.request,
                api_url=self.request.path, tenant_id=tenant, http_status=status, error_code=code, error_message=message)
        surface = {**loaded, "workshopReceptionFacts": facts, "passed": code is None,
            "resultCount": 1 if code is None else None, "businessWriteCount": 0, "auditWriteCount": 0,
            "workshopReceiptCreatedCount": 0, "workOrderCreatedCount": 0, "workOrderReleasedCount": 0,
            "productionScheduleCreatedCount": 0, "resourceOccupancyCreatedCount": 0, "resourceOccupancyReleasedCount": 0}
        if writes:
            surface.update(writes)
        return envelope({**surface, "factLoadFacts": loaded, **{key: dict(surface) for key in SURFACES}},
            error={"code": code, "message": message} if code else None, http_status=status)

    def handle_exception(self, exc):
        if isinstance(exc, APIException):
            return self.result(code=str(exc.default_code), message=str(exc.detail), status=exc.status_code)
        return super().handle_exception(exc)

    def get(self, request):
        try:
            if set(request.query_params) - {"productionPlanId","responseMode","locateOwnLatestFormalAction"} or any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
                raise PlanningBusinessError("WORKSHOP_RECEIPT_QUERY_INVALID", "接收只读参数不符合正式合同。", http_status=400)
            plan_id = request.query_params.get("productionPlanId")
            if plan_id is not None and not re.fullmatch(r"[1-9][0-9]*", plan_id):
                raise PlanningBusinessError("WORKSHOP_RECEIPT_QUERY_INVALID", "生产计划身份须为正整数。", http_status=400)
            from .workshop_reception_read_projection import latest_own_action_flag
            return self.result(read_workshop_reception(user=request.user, production_plan_id=int(plan_id) if plan_id else None,
                response_mode=request.query_params.get('responseMode'),
                locate_latest_own_action=latest_own_action_flag(request.query_params.get('locateOwnLatestFormalAction'))))
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code="WORKSHOP_RECEIPT_READ_FAILED", message="车间接收事实暂未读取；请核对正式结构部署，未执行接收。", status=503)

class ProductionWorkOrderWorkshopReceiveView(ProductionWorkOrderWorkshopReceptionView):
    http_method_names = ["post", "options"]

    def post(self, request, work_order_id, workshop_id):
        try:
            if request.query_params:
                raise PlanningBusinessError("WORKSHOP_RECEIPT_QUERY_INVALID", "明确接收动作不接受额外查询参数。", http_status=400)
            facts, writes = receive_workshop_scope(user=request.user, work_order_id=work_order_id,
                workshop_id=workshop_id, payload=request.data)
            return self.result(facts, writes=writes)
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code="WORKSHOP_RECEIPT_RESULT_UNVERIFIED", message="接收结果尚未核实，请只读刷新后核对；不会自动重试。", status=503)
