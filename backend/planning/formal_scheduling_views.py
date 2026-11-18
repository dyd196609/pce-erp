

# Native formal continuation: individually restored symbols; existing proofs preserved.
from django.db import DatabaseError, IntegrityError, OperationalError

from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView

from workflow_runtime.fact_loads import failed_fact_load_facts, successful_fact_load_facts

from pde.production_foundation_service import ProductionFoundationError

from .views import envelope

from .services import PlanningBusinessError

from . import formal_scheduling_service as service

SURFACES = ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts")

class FormalSchedulingView(APIView):
    permission_classes = [IsAuthenticated]

    def result(self, facts, writes=None):
        loaded = successful_fact_load_facts(request=self.request, result_count=1,
            api_url=self.request.path, tenant_id=str(facts["companyId"]))
        surface = {**loaded, "formalSchedulingFacts": facts, "passed": True, "resultCount": 1,
            "businessWriteCount": 0, "auditWriteCount": 0, "productionScheduleCreatedCount": 0,
            "resourceOccupancyCreatedCount": 0, "resourceOccupancyReleasedCount": 0,
            "capacityGrantCreatedCount": 0, **(writes or {})}
        surface["businessWriteCount"] = sum(surface.get(key, 0) for key in
            ("productionScheduleCreatedCount", "resourceOccupancyCreatedCount", "resourceOccupancyReleasedCount", "capacityGrantCreatedCount"))
        return envelope({**surface, "factLoadFacts": loaded, **{key: dict(surface) for key in SURFACES}})

    def failure(self, code, message, status, detail=None):
        loaded = failed_fact_load_facts(request=self.request, api_url=self.request.path,
            http_status=status, error_code=code, error_message=message,
            tenant_id=str(self.request.user.company_id) if getattr(self.request.user, "company_id", None) else None)
        surface = {**loaded, "passed": False, "resultCount": None, "formalSchedulingFacts": None,
            "businessWriteCount": 0, "auditWriteCount": 0, "productionScheduleCreatedCount": 0,
            "resourceOccupancyCreatedCount": 0, "resourceOccupancyReleasedCount": 0, "capacityGrantCreatedCount": 0,
            "admissionFailure": detail}
        return envelope({**surface, "factLoadFacts": loaded, **{key: dict(surface) for key in SURFACES}},
            error={"code": code, "message": message}, http_status=status)

    def handle_exception(self, exc):
        from rest_framework.exceptions import APIException
        if isinstance(exc, APIException):
            return self.failure(str(getattr(exc, "default_code", "API_ERROR")), str(exc.detail), exc.status_code)
        return super().handle_exception(exc)

    def perform(self, call):
        try:
            result = call()
            return self.result(*result) if isinstance(result, tuple) else self.result(result)
        except PlanningBusinessError as error:
            return self.failure(error.code, error.message, error.http_status, error.data)
        except ProductionFoundationError as error:
            return self.failure(error.code, error.message, 409)
        except (OperationalError, IntegrityError):
            return self.failure("FORMAL_SCHEDULING_CONCURRENT_CHANGE", "排程或资源正在由另一事务更新，请重新读取后执行。", 409)
        except DatabaseError:
            return self.failure("FORMAL_SCHEDULING_DATABASE_FAILED", "正式排程事实读取或事务失败；未完成业务写入。", 503)

    def get(self, request, production_plan_id):
        return self.perform(lambda: service.read_formal_scheduling(user=request.user, production_plan_id=production_plan_id))

    def post(self, request, production_plan_id):
        return self.perform(lambda: service.commit_formal_schedule(user=request.user,
            production_plan_id=production_plan_id, payload=request.data))

class FormalSchedulingAdmissionView(FormalSchedulingView):
    http_method_names = ["get", "head", "options"]

    def get(self, request, production_plan_id):
        return self.perform(lambda: service.assess_formal_scheduling(user=request.user, production_plan_id=production_plan_id))

class FormalSchedulingCapacityScopeView(FormalSchedulingView):
    http_method_names = ["post", "options"]

    def post(self, request, production_plan_id):
        return self.perform(lambda: service.authorize_capacity_scope(user=request.user,
            production_plan_id=production_plan_id, payload=request.data))

class FormalSchedulingCancelView(FormalSchedulingView):
    http_method_names = ["post", "options"]

    def post(self, request, production_plan_id, schedule_id):
        return self.perform(lambda: service.cancel_formal_schedule(user=request.user,
            production_plan_id=production_plan_id, schedule_id=schedule_id, payload=request.data))
