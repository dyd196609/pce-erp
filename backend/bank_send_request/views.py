from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bank_send_execution_gate.models import BankSendExecutionGate
from reconciliation.services import ReconciliationError
from .canary import bank_send_request_canary_facts
from .models import BankSendRequestCanaryPoolEntry
from .repositories import BankSendRequestRepository
from .services import (
    CANONICAL_NAME, MODULE_CODE, VERSION, bank_send_request_facts_for_rows,
    create_bank_send_request, downstream_counts, evaluate_pre_dispatch_validation,
    rerun_pre_dispatch_validation, serialize_request,
)


def error_response(exc):
    return Response({
        "result": "blocked", "version": VERSION,
        "classification": {
            "BSR_PERMISSION_DENIED": "permission_denied",
            "BSR_PRODUCTION_DISABLED": "permission_denied",
            "BSR_VERSION_CONFLICT": "version_conflict",
            "BSR_SOURCE_CHANGED": "source_changed",
            "BSR_PRE_DISPATCH_BLOCKED": "blocked",
        }.get(exc.code, "blocked"),
        "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
        "bankMessageSent": False, "paymentExecuted": False, "fundsDebited": False,
    }, status=exc.http_status)


class ScopedMixin:
    def get_permissions(self):
        permission = AllowAny if (
            getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            and self.request.method == "GET"
        ) else IsAuthenticated
        return [permission()]

    def request_queryset(self, request):
        qs = BankSendRequestRepository().queryset()
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(company_id=request.user.company_id)
        return qs

    def gate_queryset(self, request):
        qs = BankSendExecutionGate.objects.select_related(
            "source_task__source_preparation__source_formal_payment_order__execution_freeze",
            "source_task__source_preparation__source_formal_payment_order__source_risk_review__source_payment_order_draft",
            "source_task__source_preparation__send_gate",
            "source_task__message_preview",
        )
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(company_id=request.user.company_id)
        return qs


class BankSendRequestListView(ScopedMixin, APIView):
    def get(self, request):
        rows = [serialize_request(row) for row in self.request_queryset(request)]
        sources = [{
            "id": gate.pk, "gateNo": gate.gate_no,
            "bankSendTaskNo": gate.bank_send_task_no,
            "formalPaymentOrderNo": gate.formal_payment_order_no,
            "status": gate.status, "version": gate.version,
            "validationEligibility": evaluate_pre_dispatch_validation(gate),
            "targetExists": hasattr(gate, "send_request"),
            "targetRequestNo": gate.send_request.request_no if hasattr(gate, "send_request") else "",
            "currentStateSource": "server",
        } for gate in self.gate_queryset(request)]
        canary = bank_send_request_canary_facts()
        tenant = settings.PCE_CANARY_TENANT_ID if getattr(
            settings, "PCE_CANARY_DEMO_MODE", False
        ) else None
        facts = bank_send_request_facts_for_rows(
            rows=rows, canary_pool_facts=canary, tenant_id=tenant,
            batch_id=getattr(settings, "PCE_CANARY_BATCH_ID", ""), request=request,
        )
        keys = (
            "requestCount", "draftCount", "validatedCount", "readyToDispatchCount",
            "bankMessageSentCount", "paymentExecutionCount", "fundsDebitCount",
        )
        capacity = {key: facts[key] for key in keys}
        return Response({
            "result": "passed", "version": VERSION, "canonicalName": CANONICAL_NAME,
            "moduleCode": MODULE_CODE, "currentStateSource": "server",
            "data": {
                **capacity, **facts["factLoadFacts"], "factLoadFacts": facts["factLoadFacts"],
                "count": facts["requestCount"], "results": rows, "sources": sources,
                "capacity": capacity, "downstreamCounts": downstream_counts(),
                "writeIntentFacts": facts["writeIntentFacts"],
                "bankSendRequestFacts": facts, "canaryPoolFacts": canary,
                "bankSendExecutionEnabled": False, "productionRolloutEnabled": False,
            },
        })


class BankSendRequestCreateView(ScopedMixin, APIView):
    def post(self, request, gate_id):
        gate = self.gate_queryset(request).filter(pk=gate_id).first()
        if not gate:
            return error_response(ReconciliationError("BSR_SOURCE_NOT_FOUND", "Execution gate not found", 404))
        try:
            result = create_bank_send_request(
                user=request.user, gate=gate,
                idempotency_key=str(request.data.get("idempotencyKey", "")).strip(),
                expected_source_version=int(request.data.get("expectedSourceVersion", -1)),
                explicit_user_action=request.data.get("explicitUserAction") is True,
            )
            return Response({"result": "passed", "version": VERSION, **result}, status=201 if result["created"] else 200)
        except ReconciliationError as exc:
            return error_response(exc)


class BankSendRequestRevalidateView(ScopedMixin, APIView):
    def post(self, request, request_id):
        obj = self.request_queryset(request).filter(pk=request_id).first()
        if not obj:
            return error_response(ReconciliationError("BSR_NOT_FOUND", "Bank send request not found", 404))
        return Response({"version": VERSION, **rerun_pre_dispatch_validation(user=request.user, request_object=obj)})


class BankSendRequestBlockedAttemptView(ScopedMixin, APIView):
    def post(self, request, scenario_code):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return error_response(ReconciliationError("BSR_PRODUCTION_DISABLED", "Canary only", 403))
        entry = BankSendRequestCanaryPoolEntry.objects.filter(
            tenant_id=settings.PCE_CANARY_TENANT_ID,
            batch_id=settings.PCE_CANARY_BATCH_ID, pool_type="blocked",
            scenario_code=scenario_code,
        ).first()
        if not entry:
            return error_response(ReconciliationError("BSR_SOURCE_NOT_FOUND", "Scenario not found", 404))
        return error_response(ReconciliationError("BSR_PRE_DISPATCH_BLOCKED", entry.blocking_reason, 409))
