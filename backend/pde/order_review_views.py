from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .order_review_service import (
    ReviewBusinessError, append_review, build_review_facts,
    final_approve_review, save_draft, sign_items, submit_review,
)


class OrderReviewView(APIView):
    permission_classes = [IsAuthenticated]
    review_type = ""
    formal_context_required = False

    def _context_args(self, request):
        payload = request.data if request.method == "POST" else request.query_params
        return {
            "crm_order_relation_id": payload.get("crmOrderRelationId"),
            "sales_order_id": payload.get("salesOrderId"),
            "formal_context_required": self.formal_context_required,
        }

    def get(self, request):
        context_args = self._context_args(request)
        return self._run(lambda: build_review_facts(
            user=request.user,
            review_type=self.review_type,
            source_record_id=request.query_params.get("sourceRecord"),
            **context_args,
        ))

    def post(self, request):
        source_id = request.data.get("sourceRecord") or request.query_params.get("sourceRecord")
        context_args = self._context_args(request)
        action = request.data.get("action") or "legacyAppend"
        handlers = {
            "saveDraft": lambda: save_draft(user=request.user, review_type=self.review_type, source_record_id=source_id, data=request.data, idempotency_key=request.headers.get("Idempotency-Key"), **context_args),
            "signItems": lambda: sign_items(user=request.user, review_type=self.review_type, source_record_id=source_id, data=request.data, **context_args),
            "submitReview": lambda: submit_review(user=request.user, review_type=self.review_type, source_record_id=source_id, data=request.data, **context_args),
            "finalApprove": lambda: final_approve_review(user=request.user, review_type=self.review_type, source_record_id=source_id, data=request.data, idempotency_key=request.headers.get("Idempotency-Key"), **context_args),
            "legacyAppend": lambda: append_review(user=request.user, review_type=self.review_type, source_record_id=source_id, data=request.data, idempotency_key=request.headers.get("Idempotency-Key"), **context_args),
        }
        if action not in handlers:
            return self._run(lambda: (_ for _ in ()).throw(ReviewBusinessError("REVIEW_ACTION_INVALID", "评审操作无效。")))
        return self._run(handlers[action])

    @staticmethod
    def _run(callback):
        try:
            payload = callback()
            return Response({"success": True, "data": payload, "error": None, "meta": {"module": payload["review"]["moduleCode"], "source": "server"}})
        except ReviewBusinessError as exc:
            return Response({"success": False, "data": None, "error": {"code": exc.code, "message": exc.message}, "meta": {"module": "ORDER_REVIEW", "source": "server"}}, status=exc.http_status)


class ProductionFeasibilityReviewView(OrderReviewView):
    review_type = "PDE_PRODUCTION_FEASIBILITY"
    formal_context_required = True
