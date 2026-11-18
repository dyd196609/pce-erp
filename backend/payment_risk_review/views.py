from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reconciliation.services import ReconciliationError

from .models import PaymentRiskReview, PaymentRiskReviewCanaryScenario
from .repositories import PaymentRiskReviewRepository
from .services import (
    CANONICAL_NAME,
    SOURCE_DOCUMENT_TYPE,
    VERSION,
    execute_risk_review,
    eligibility,
    serialize_review,
)


def downstream_counts():
    return {
        "formalPaymentOrders": 0,
        "formalPaymentInstructions": 0,
        "signingResults": 0,
        "bankMessages": 0,
        "paymentExecutions": 0,
        "paymentVouchers": 0,
        "writeoffs": 0,
        "ledgerEntries": 0,
        "postings": 0,
        "bankTransactions": 0,
    }


def error_response(exc):
    return Response(
        {
            "result": "blocked",
            "version": VERSION,
            "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
            "formalPaymentOrderCreated": False,
            "paymentExecuted": False,
        },
        status=exc.http_status,
    )


class ScopedMixin:
    def get_permissions(self):
        permission = (
            AllowAny
            if getattr(settings, "PCE_CANARY_DEMO_MODE", False) and self.request.method == "GET"
            else IsAuthenticated
        )
        return [permission()]

    def queryset(self, request):
        queryset = PaymentRiskReviewRepository().queryset()
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return queryset.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(company_id=request.user.company_id)


class RiskReviewListView(ScopedMixin, APIView):
    def get(self, request):
        results = [serialize_review(row) for row in self.queryset(request)]
        passed = sum(row["status"] == "passed" for row in results)
        blocked = sum(row["status"] == "blocked" for row in results)
        scenarios = list(
            PaymentRiskReviewCanaryScenario.objects.filter(
                batch_id=getattr(settings, "PCE_CANARY_BATCH_ID", "PURCHASE-FLOW-DEMO-V1")
            ).order_by("scenario_code").values(
                "scenario_code", "risk_code", "risk_level", "blocking_reasons", "eligible"
            )
        )
        return Response({
            "result": "passed",
            "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "currentStateSource": "server",
            "data": {
                "capacity": {
                    "sourceDraftCount": len(results),
                    "riskReviewCount": len(results),
                    "passedCount": passed,
                    "blockedCount": blocked,
                    "blockedScenarioCount": len(scenarios),
                    "nextStageConsumedCount": 0,
                },
                "results": results,
                "blockedScenarios": scenarios,
                "downstreamCounts": downstream_counts(),
            },
        })


class RiskReviewDetailView(ScopedMixin, APIView):
    def get(self, request, review_id):
        review = self.queryset(request).filter(pk=review_id).first()
        if not review:
            return error_response(ReconciliationError("PRR_NOT_FOUND", "Risk review not found", 404))
        return Response({
            "result": "passed",
            "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "currentStateSource": "server",
            "data": serialize_review(review),
            "downstreamCounts": downstream_counts(),
        })


class RiskReviewExecuteView(ScopedMixin, APIView):
    def post(self, request, review_id):
        review = PaymentRiskReview.objects.filter(pk=review_id).first()
        if not review:
            return error_response(ReconciliationError("PRR_NOT_FOUND", "Risk review not found", 404))
        try:
            outcome = execute_risk_review(
                user=request.user,
                review=review,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_version=int(request.data.get("expectedVersion", -1)),
                explicit_user_action=request.data.get("explicitUserAction") is True,
            )
            return Response({
                "result": "passed",
                "version": VERSION,
                **outcome,
                "formalPaymentOrderCreated": False,
                "paymentExecuted": False,
            })
        except ReconciliationError as exc:
            return error_response(exc)


class RiskReviewEligibilityView(ScopedMixin, APIView):
    def get(self, request, review_id):
        review = self.queryset(request).filter(pk=review_id).first()
        if not review:
            return error_response(ReconciliationError("PRR_NOT_FOUND", "Risk review not found", 404))
        return Response({
            "result": "passed",
            "version": VERSION,
            "currentStateSource": "server",
            "data": eligibility(review),
            "formalPaymentOrderCreated": False,
        })

