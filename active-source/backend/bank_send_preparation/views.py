from django.conf import settings
from django.db.models import Q
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from formal_payment_order.models import FormalPaymentOrder
from reconciliation.services import ReconciliationError
from workflow_runtime.action_permissions import authorized_view_legal_entities

from .models import BankMessagePreview, BankSendPreparation
from .repositories import BankSendPreparationRepository
from .services import (
    CANONICAL_NAME,
    MODULE_CODE,
    SOURCE_DOCUMENT_TYPE,
    VERSION,
    downstream_counts,
    evaluate_bank_send_gate,
    generate_bank_message_preview,
    serialize_preparation,
    bank_send_preparation_facts_for_rows,
)


def error_response(exc):
    return Response(
        {
            "result": "blocked",
            "version": VERSION,
            "classification": {
                "BSP_AUTH_REQUIRED": "authentication_failed",
                "BSP_PERMISSION_DENIED": "permission_denied",
                "BSP_PRODUCTION_DISABLED": "permission_denied",
                "BSP_VERSION_CONFLICT": "version_conflict",
                "BSP_IDEMPOTENCY_CONFLICT": "idempotency_conflict",
                "BSP_GATE_CHANGED": "gate_changed",
                "BSP_GATE_BLOCKED": "gate_blocked",
            }.get(exc.code, "blocked"),
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
            "bankSendCreated": False,
            "bankMessageSent": False,
            "paymentExecuted": False,
            "fundsDebited": False,
            "bankTransactionCreated": False,
        },
        status=exc.http_status,
    )


class ScopedMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request,
            response,
            *args,
            **kwargs,
        )
        response["Cache-Control"] = "private, no-store"
        response["Pragma"] = "no-cache"
        return response

    def get_permissions(self):
        permission = (
            AllowAny
            if (
                getattr(settings, "PCE_CANARY_DEMO_MODE", False)
                and self.request.method == "GET"
            )
            else IsAuthenticated
        )
        return [permission()]

    def queryset(self, request):
        queryset = BankSendPreparationRepository().queryset()
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            queryset = queryset.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
        elif not request.user.is_superuser:
            queryset = queryset.filter(company_id=request.user.company_id)
        if request.user and request.user.is_authenticated and not request.user.is_superuser:
            allowed = authorized_view_legal_entities(
                request.user,
                MODULE_CODE,
            )
            if allowed is not None:
                queryset = queryset.filter(legal_entity_id__in=allowed)
        return queryset


class BankSendPreparationListView(ScopedMixin, APIView):
    def get(self, request):
        preparations = list(self.queryset(request))
        results = [serialize_preparation(row) for row in preparations]
        source_query = FormalPaymentOrder.objects.filter(
            status="frozen_for_execution",
        )
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            source_query = source_query.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
        elif not request.user.is_superuser:
            source_query = source_query.filter(company_id=request.user.company_id)
        eligible_sources = [
            order
            for order in source_query
            if evaluate_bank_send_gate(order)["eligible"]
        ]
        tenant_id = (
            settings.PCE_CANARY_TENANT_ID
            if getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            else None
        )
        counts = downstream_counts(tenant_id=tenant_id)
        batch_id = getattr(
            settings,
            "PCE_CANARY_BATCH_ID",
            "PURCHASE-FLOW-DEMO-V1",
        )
        bank_send_preparation_facts = (
            bank_send_preparation_facts_for_rows(
                results,
                source_formal_payment_order_count=len(eligible_sources),
                counts=counts,
                tenant_id=tenant_id,
                batch_id=batch_id,
                request=request,
            )
        )
        fact_load_facts = bank_send_preparation_facts["factLoadFacts"]
        write_intent_facts = bank_send_preparation_facts[
            "writeIntentFacts"
        ]
        capacity = {
            key: bank_send_preparation_facts[key]
            for key in (
                "sourceFormalPaymentOrderCount",
                "bankSendPreparationCount",
                "preparedCount",
                "eligibleCount",
                "previewCount",
                "nextStageConsumedCount",
                "passed",
            )
        }
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "canonicalName": CANONICAL_NAME,
                "moduleCode": MODULE_CODE,
                "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
                "currentStateSource": "server",
                "data": {
                    **capacity,
                    **fact_load_facts,
                    "factLoadFacts": fact_load_facts,
                    "tenantId": fact_load_facts["tenantId"],
                    "batchId": fact_load_facts["batchId"],
                    "count": bank_send_preparation_facts[
                        "bankSendPreparationCount"
                    ],
                    "results": results,
                    "capacity": capacity,
                    "downstreamCounts": counts,
                    "writeIntentFacts": write_intent_facts,
                    "bankSendPreparationFacts":
                        bank_send_preparation_facts,
                    "productionTenantObjectCount": BankSendPreparation.objects.exclude(
                        tenant_id=getattr(
                            settings,
                            "PCE_CANARY_TENANT_ID",
                            "tenant-canary-demo",
                        )
                    ).count(),
                    "bankSendEnabled": False,
                    "productionRolloutEnabled": False,
                },
            }
        )


class BankSendPreparationDetailView(ScopedMixin, APIView):
    def get(self, request, preparation_id):
        preparation = self.queryset(request).filter(pk=preparation_id).first()
        if not preparation:
            return error_response(
                ReconciliationError(
                    "BSP_NOT_FOUND",
                    "Bank send preparation not found",
                    404,
                )
            )
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "canonicalName": CANONICAL_NAME,
                "currentStateSource": "server",
                "data": serialize_preparation(preparation),
                "downstreamCounts": downstream_counts(
                    preparation_id=preparation.pk,
                ),
            }
        )


class BankSendEligibilityView(ScopedMixin, APIView):
    def get(self, request, preparation_id):
        preparation = self.queryset(request).filter(pk=preparation_id).first()
        if not preparation:
            return error_response(
                ReconciliationError(
                    "BSP_NOT_FOUND",
                    "Bank send preparation not found",
                    404,
                )
            )
        serialized = serialize_preparation(preparation)
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "currentStateSource": "server",
                "data": serialized["eligibility"],
                "bankSendCreated": False,
            }
        )


class BankSendGateView(ScopedMixin, APIView):
    def get(self, request, preparation_id):
        preparation = self.queryset(request).filter(pk=preparation_id).first()
        if not preparation:
            return error_response(
                ReconciliationError(
                    "BSP_NOT_FOUND",
                    "Bank send preparation not found",
                    404,
                )
            )
        serialized = serialize_preparation(preparation)
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "currentStateSource": "server",
                "data": serialized["gate"],
                "bankSendCreated": False,
            }
        )


class BankMessagePreviewGenerateView(ScopedMixin, APIView):
    def post(self, request, preparation_id):
        preparation = (
            BankSendPreparationRepository().get(preparation_id)
        )
        if not preparation:
            return error_response(
                ReconciliationError(
                    "BSP_NOT_FOUND",
                    "Bank send preparation not found",
                    404,
                )
            )
        try:
            outcome = generate_bank_message_preview(
                user=request.user,
                preparation=preparation,
                idempotency_key=str(
                    request.data.get("idempotencyKey", "")
                ).strip(),
                expected_version=int(
                    request.data.get("expectedVersion", -1)
                ),
                explicit_user_action=(
                    request.data.get("explicitUserAction") is True
                ),
            )
            return Response(
                {
                    "result": "passed",
                    "version": VERSION,
                    **outcome,
                    "bankSendCreated": False,
                    "bankMessageSent": False,
                    "paymentExecuted": False,
                    "fundsDebited": False,
                    "bankTransactionCreated": False,
                },
                status=201 if outcome["created"] else 200,
            )
        except ReconciliationError as exc:
            return error_response(exc)


class BankMessagePreviewDetailView(ScopedMixin, APIView):
    def get(self, request, preparation_id):
        preparation = self.queryset(request).filter(pk=preparation_id).first()
        if not preparation:
            return error_response(
                ReconciliationError(
                    "BSP_NOT_FOUND",
                    "Bank send preparation not found",
                    404,
                )
            )
        serialized = serialize_preparation(preparation)
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "currentStateSource": "server",
                "data": serialized["messagePreview"],
                "bankSendCreated": False,
                "bankMessageSent": False,
            }
        )
