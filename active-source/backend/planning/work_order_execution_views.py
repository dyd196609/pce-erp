

# Native formal continuation: individually restored symbols; existing proofs preserved.
from django.db import DatabaseError

from .services import PlanningBusinessError

from .work_order_reception_views import ProductionWorkOrderReceptionView

from .work_order_execution_service import generate_work_order, release_work_order

class ProductionWorkOrderGenerateView(ProductionWorkOrderReceptionView):
    http_method_names = ["post", "options"]
    service = staticmethod(generate_work_order)

    def post(self, request, production_plan_id):
        try:
            if request.query_params:
                raise PlanningBusinessError("WORK_ORDER_QUERY_INVALID", "工单执行意图不接受额外查询参数。", http_status=400)
            facts, writes = self.service(user=request.user, production_plan_id=production_plan_id, payload=request.data)
            return self.result(facts, writes=writes)
        except PlanningBusinessError as error:
            return self.result(code=error.code, message=error.message, status=error.http_status)
        except DatabaseError:
            return self.result(code="WORK_ORDER_EXECUTION_FAILED", message="工单事务未完成，请先只读刷新核对；不会自动重试。", status=503)

class ProductionWorkOrderReleaseView(ProductionWorkOrderGenerateView):
    service = staticmethod(release_work_order)
