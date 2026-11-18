from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from workflow_runtime.facts import business_state_collection_facts

from .models import PurchaseReconciliation, PurchaseReconciliationSourceSnapshot
from .checking import (
    authorize_read,
    build_invoice_prepare_eligibility,
    complete_reconciliation_check,
    serialize_reconciliation,
)
from .services import ReconciliationError, generate_purchase_reconciliation, recover_by_idempotency, serialize_result


class GenerateSerializer(serializers.Serializer):
    sourceKey = serializers.CharField(max_length=160)
    finalReviewId = serializers.CharField(max_length=80)
    idempotencyKey = serializers.CharField(max_length=120)
    explicitUserAction = serializers.BooleanField()


class CompleteCheckSerializer(serializers.Serializer):
    idempotencyKey = serializers.CharField(max_length=120)
    expectedVersion = serializers.IntegerField(min_value=1)
    explicitUserAction = serializers.BooleanField()


def error_response(error):
    return Response({"result": "rejected", "errorCode": error.code, "message": error.message, "retryable": error.retryable}, status=error.http_status)


class GenerateView(APIView):
    # Authentication is still performed by DRF, while the service owns the
    # stable unauthenticated/permission/scope/feature error contract.
    permission_classes = []

    def post(self, request):
        serializer = GenerateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(ReconciliationError("PRC_REQUEST_INVALID", "Request validation failed", 400))
        try:
            data = serializer.validated_data
            failure_step = request.headers.get("X-PCE-Test-Failure-Step", "")
            result = generate_purchase_reconciliation(user=request.user, source_key=data["sourceKey"], final_review_id=data["finalReviewId"], idempotency_key=data["idempotencyKey"], explicit_user_action=data["explicitUserAction"], failure_step=failure_step)
            return Response({"result": "passed", "data": result}, status=status.HTTP_200_OK if result["replayed"] else status.HTTP_201_CREATED)
        except ReconciliationError as error:
            return error_response(error)


class GenerationResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, idempotency_key):
        result = recover_by_idempotency(idempotency_key)
        return Response({"result": "passed", "data": result})


class BySourceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, source_key):
        try:
            source = PurchaseReconciliationSourceSnapshot.objects.get(source_key=source_key)
        except PurchaseReconciliationSourceSnapshot.DoesNotExist:
            return error_response(ReconciliationError("PRC_SOURCE_NOT_FOUND", "Source not found", 404))
        if request.user.company_id != source.company_id:
            return error_response(ReconciliationError("PRC_AUTH_SCOPE_DENIED", "Source is outside actor company scope", 403))
        obj = PurchaseReconciliation.objects.filter(source_key=source_key).first()
        return Response({"result": "passed", "data": serialize_result(obj) if obj else None})


class ReconciliationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = PurchaseReconciliation.objects.filter(company_id=request.user.company_id).order_by("-created_at", "-id")
        data = [serialize_reconciliation(item) for item in queryset]
        return Response({
            "result": "passed",
            "currentStateSource": "server",
            "data": {
                "count": len(data),
                "results": data,
                "strictFacts": business_state_collection_facts(data),
            },
        })


class ReconciliationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, reconciliation_id):
        try:
            obj = PurchaseReconciliation.objects.get(pk=reconciliation_id)
            authorize_read(request.user, obj)
            return obj
        except PurchaseReconciliation.DoesNotExist as exc:
            raise ReconciliationError("PRC_RECONCILIATION_NOT_FOUND", "Purchase reconciliation not found", 404) from exc

    def get(self, request, reconciliation_id):
        try:
            return Response({"result": "passed", "data": serialize_reconciliation(self.get_object(request, reconciliation_id))})
        except ReconciliationError as error:
            return error_response(error)


class ReconciliationDifferencesView(ReconciliationDetailView):
    def get(self, request, reconciliation_id):
        try:
            obj = self.get_object(request, reconciliation_id)
            data = [
                {
                    "differenceCode": item.difference_code,
                    "fieldName": item.field_name,
                    "expectedValue": item.expected_value,
                    "actualValue": item.actual_value,
                    "blocking": item.blocking,
                }
                for item in obj.differences.order_by("id")
            ]
            return Response({"result": "passed", "data": {"count": len(data), "results": data}})
        except ReconciliationError as error:
            return error_response(error)


class ReconciliationEligibilityView(ReconciliationDetailView):
    def get(self, request, reconciliation_id):
        try:
            obj = self.get_object(request, reconciliation_id)
            return Response({"result": "passed", "data": build_invoice_prepare_eligibility(obj)})
        except ReconciliationError as error:
            return error_response(error)


class CompleteReconciliationCheckView(APIView):
    permission_classes = []

    def post(self, request, reconciliation_id):
        serializer = CompleteCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(ReconciliationError("PRC_REQUEST_INVALID", "Request validation failed", 400))
        try:
            data = serializer.validated_data
            result = complete_reconciliation_check(
                user=request.user,
                reconciliation_id=reconciliation_id,
                idempotency_key=data["idempotencyKey"],
                expected_version=data["expectedVersion"],
                explicit_user_action=data["explicitUserAction"],
                failure_step=request.headers.get("X-PCE-Test-Failure-Step", ""),
            )
            return Response({"result": "passed", "data": result}, status=status.HTTP_200_OK)
        except ReconciliationError as error:
            return error_response(error)
