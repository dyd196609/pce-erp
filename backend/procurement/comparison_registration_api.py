"""Original SCM application entry and readonly same-action recovery."""
from django.db import IntegrityError, OperationalError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from pde.product_design_service import ProductDesignError
from .comparison_registration_service import (ACTION_CONTRACT, ComparisonRegistrationError,
    register_comparison, registration_context, action_result)


def response(data=None, error=None, status=200):
    return Response({"success": error is None, "data": data, "error": error,
        "meta": {"source": "server", "actionContract": ACTION_CONTRACT,
                 "automaticReplayAllowed": False}}, status=status)


def invoke(callback):
    try:return response(callback())
    except (ComparisonRegistrationError, ProductDesignError) as error:
        return response(error={"code": error.code, "message": str(error)}, status=error.http_status)
    except IntegrityError:
        return response(error={"code": "COMPARISON_CONCURRENT_CHANGE", "message": "比较版本或同次动作已有并发变化，请先查询原结果。"}, status=409)
    except OperationalError as error:
        if "locked" not in str(error).lower():raise
        return response(error={"code": "COMPARISON_CONCURRENT_CHANGE", "message": "原生事务正在并发提交，请先查询同次结果，不自动重放。"}, status=409)


class QuoteComparisonRegistrationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        if set(params) - {"inquiryId", "requestItemId", "idempotencyKey"}:
            return response(error={"code": "COMPARISON_INPUT_INVALID", "message": "仅接受准确来源行及同次动作键。"}, status=400)
        if "idempotencyKey" in params:
            return invoke(lambda: action_result(user=request.user, inquiry_id=params.get("inquiryId"),
                item_id=params.get("requestItemId"), key=params.get("idempotencyKey")))
        return invoke(lambda: registration_context(user=request.user, inquiry_id=params.get("inquiryId"),
            item_id=params.get("requestItemId")))

    def post(self, request):
        return invoke(lambda: register_comparison(user=request.user, payload=request.data))
