from collections.abc import Mapping
from django.db import DatabaseError
from rest_framework import permissions
from rest_framework.views import APIView
from workflow_runtime.fact_loads import failed_fact_load_facts, successful_fact_load_facts

from .supply_admission_service import SupplyAdmissionError, confirm_supply_admission, query_supply_admission
from .views import envelope


class SupplyAdmissionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def fail(self, request, error):
        facts = failed_fact_load_facts(api_url=request.path, http_status=error.http_status,
            error_code=error.code, error_message=error.message,
            tenant_id=str(request.user.company_id), request=request)
        return envelope({"factLoadFacts": facts, "strictFacts": {"passed": False}, **facts}, error={"code": error.code, "message": error.message}, http_status=error.http_status)

    def get(self, request, order_id, item_id):
        try:
            confirmation = query_supply_admission(user=request.user, order_id=order_id, item_id=item_id)
            facts = successful_fact_load_facts(result_count=bool(confirmation.get("factId")), api_url=request.path, tenant_id=str(request.user.company_id), request=request)
            return envelope({"confirmation": confirmation, "factLoadFacts": facts, **facts})
        except SupplyAdmissionError as error:
            return self.fail(request, error)
        except DatabaseError:
            return self.fail(request, SupplyAdmissionError("SUPPLY_ADMISSION_READ_FAILED", "正式供应承接事实读取失败，不使用默认值或Material回退。", 503))

    def post(self, request, order_id, item_id):
        try:
            if not isinstance(request.data, Mapping):
                raise SupplyAdmissionError("INVALID_PAYLOAD", "供应确认请求必须是JSON对象。", 400)
            if set(request.data) - {"supplyType", "idempotencyKey", "reason", "manufacturingOwnerUserId"}:
                raise SupplyAdmissionError("UNSUPPORTED_FIELD", "责任人、岗位、确认状态与时间由服务端解析，不接受客户端代填。", 400)
            return envelope(confirm_supply_admission(
                user=request.user, order_id=order_id, item_id=item_id,
                supply_type=request.data.get("supplyType"), idempotency_key=request.data.get("idempotencyKey"), reason=request.data.get("reason"),
                manufacturing_owner_user_id=request.data.get("manufacturingOwnerUserId"),
            ))
        except SupplyAdmissionError as error:
            return self.fail(request, error)
        except DatabaseError:
            return self.fail(request, SupplyAdmissionError("SUPPLY_ADMISSION_WRITE_FAILED", "供应承接事务未完成，请用同一幂等键重试；不得补写确认结果。", 503))
