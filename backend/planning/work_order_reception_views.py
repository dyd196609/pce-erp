

# Native formal continuation: individually restored symbols; existing proofs preserved.
import re

from django.db import DatabaseError

from rest_framework.exceptions import APIException

from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView

from workflow_runtime.fact_loads import failed_fact_load_facts, successful_fact_load_facts

from .services import PlanningBusinessError

from .views import envelope

from .work_order_reception_service import read_work_order_reception

SURFACES = ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts")

class ProductionWorkOrderReceptionView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def result(self, facts=None, *, code=None, message=None, status=200, writes=None):
        tenant = str(facts["companyId"]) if facts else str(getattr(self.request.user, "company_id", ""))
        loaded = (successful_fact_load_facts(request=self.request, result_count=1,
            api_url=self.request.path, tenant_id=tenant) if code is None else
            failed_fact_load_facts(request=self.request, api_url=self.request.path, http_status=status,
                error_code=code, error_message=message, tenant_id=tenant))
        surface = {**loaded, "workOrderReceptionFacts": facts, "passed": code is None,
            "resultCount": 1 if code is None else None, "businessWriteCount": 0, "auditWriteCount": 0,
            "workOrderCreatedCount": 0, "workOrderReleasedCount": 0, "productionScheduleCreatedCount": 0,
            "resourceOccupancyCreatedCount": 0, "resourceOccupancyReleasedCount": 0, "capacityGrantCreatedCount": 0}
        if writes is not None:
            surface.update(writes)
        return envelope({**surface, "factLoadFacts": loaded, **{k: dict(surface) for k in SURFACES}},
            error={"code": code, "message": message} if code else None, http_status=status)

    def handle_exception(self, exc):
        if isinstance(exc, APIException):
            return self.result(code=str(exc.default_code), message=str(exc.detail), status=exc.status_code)
        return super().handle_exception(exc)

    def get(self, request, production_plan_id):
        try:
            if set(request.query_params) - {"scheduleId", "revision", "snapshotHash"}:
                raise PlanningBusinessError("WORK_ORDER_RECEPTION_QUERY_INVALID", "只读接收参数不符合正式合同。", http_status=400)
            args = {}
            for key, target in (("scheduleId", "expected_schedule_id"), ("revision", "expected_revision")):
                if key in request.query_params:
                    raw = request.query_params[key]
                    if not re.fullmatch(r"[1-9][0-9]*", raw):
                        raise PlanningBusinessError("WORK_ORDER_RECEPTION_QUERY_INVALID", "正式版本身份须为正整数。", http_status=400)
                    args[target] = int(raw)
            if "snapshotHash" in request.query_params:
                raw = request.query_params["snapshotHash"]
                if not re.fullmatch(r"[0-9a-f]{64}", raw):
                    raise PlanningBusinessError("WORK_ORDER_RECEPTION_QUERY_INVALID", "冻结Hash格式无效。", http_status=400)
                args["expected_snapshot_hash"] = raw
            return self.result(read_work_order_reception(user=request.user, production_plan_id=production_plan_id, **args))
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code="WORK_ORDER_RECEPTION_READ_FAILED", message="正式排程接收事实读取失败；未生成或下达工单。", status=503)
