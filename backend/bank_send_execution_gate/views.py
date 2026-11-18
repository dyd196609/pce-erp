from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bank_send_task.models import BankSendTask
from bank_send_task.repositories import BankSendTaskRepository
from reconciliation.services import ReconciliationError
from workflow_runtime.action_permissions import (
    authorized_view_legal_entities,
)

from .canary import bank_send_execution_gate_canary_facts
from .models import (
    BankSendExecutionGate,
    BankSendExecutionGateCanaryPoolEntry,
)
from .repositories import BankSendExecutionGateRepository
from .services import (
    CANONICAL_NAME,
    MODULE_CODE,
    VERSION,
    bank_send_execution_gate_facts_for_rows,
    create_bank_send_execution_gate,
    downstream_counts,
    evaluate_execution_authorization,
    serialize_gate,
)


def error_response(exc):
    return Response(
        {
            "result": "blocked",
            "version": VERSION,
            "classification": {
                "BSEG_PERMISSION_DENIED": "permission_denied",
                "BSEG_PRODUCTION_DISABLED": "permission_denied",
                "BSEG_VERSION_CONFLICT": "version_conflict",
                "BSEG_IDEMPOTENCY_CONFLICT": "idempotency_conflict",
                "BSEG_GATE_CHANGED": "gate_changed",
                "BSEG_GATE_BLOCKED": "gate_blocked",
            }.get(exc.code, "blocked"),
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
            "bankSendExecuted": False,
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

    def gate_queryset(self, request):
        queryset = BankSendExecutionGateRepository().queryset()
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            queryset = queryset.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
        elif not request.user.is_superuser:
            queryset = queryset.filter(company_id=request.user.company_id)
        if (
            request.user
            and request.user.is_authenticated
            and not request.user.is_superuser
        ):
            allowed = authorized_view_legal_entities(
                request.user,
                MODULE_CODE,
            )
            if allowed is not None:
                queryset = queryset.filter(legal_entity_id__in=allowed)
        return queryset

    def task_queryset(self, request):
        queryset = BankSendTaskRepository().queryset()
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            queryset = queryset.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
        elif not request.user.is_superuser:
            queryset = queryset.filter(company_id=request.user.company_id)
        return queryset


class BankSendExecutionGateListView(ScopedMixin, APIView):
    def get(self, request):
        rows = [serialize_gate(row) for row in self.gate_queryset(request)]
        sources = [
            {
                "id": task.pk,
                "taskNo": task.task_no,
                "formalPaymentOrderNo":
                    task.source_formal_payment_order_no,
                "status": task.status,
                "version": task.version,
                "legalEntityId": task.legal_entity_id,
                "authorizationEligibility":
                    evaluate_execution_authorization(task),
                "targetExists": hasattr(task, "execution_gate"),
                "targetGateNo": (
                    task.execution_gate.gate_no
                    if hasattr(task, "execution_gate")
                    else ""
                ),
                "currentStateSource": "server",
            }
            for task in self.task_queryset(request)
        ]
        canary = bank_send_execution_gate_canary_facts()
        tenant_id = (
            settings.PCE_CANARY_TENANT_ID
            if getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            else None
        )
        batch_id = getattr(
            settings,
            "PCE_CANARY_BATCH_ID",
            "PURCHASE-FLOW-DEMO-V1",
        )
        facts = bank_send_execution_gate_facts_for_rows(
            rows=rows,
            canary_pool_facts=canary,
            tenant_id=tenant_id,
            batch_id=batch_id,
            request=request,
        )
        fact_load_facts = facts["factLoadFacts"]
        capacity_fields = (
            "gateCount",
            "pendingReviewCount",
            "approvedCount",
            "readyForExecutionCount",
            "executedCount",
            "bankSendExecutionCount",
            "bankMessageSentCount",
            "paymentExecutionCount",
        )
        capacity = {key: facts[key] for key in capacity_fields}
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "canonicalName": CANONICAL_NAME,
                "moduleCode": MODULE_CODE,
                "currentStateSource": "server",
                "data": {
                    **capacity,
                    **fact_load_facts,
                    "factLoadFacts": fact_load_facts,
                    "tenantId": fact_load_facts["tenantId"],
                    "batchId": fact_load_facts["batchId"],
                    "count": facts["gateCount"],
                    "results": rows,
                    "sources": sources,
                    "capacity": capacity,
                    "downstreamCounts": downstream_counts(),
                    "writeIntentFacts": facts["writeIntentFacts"],
                    "bankSendExecutionGateFacts": facts,
                    "canaryPoolFacts": canary,
                    "bankSendExecutionEnabled": False,
                    "productionRolloutEnabled": False,
                    "productionTenantObjectCount":
                        BankSendExecutionGate.objects.exclude(
                            tenant_id=getattr(
                                settings,
                                "PCE_CANARY_TENANT_ID",
                                "tenant-canary-demo",
                            )
                        ).count(),
                },
            }
        )


class BankSendExecutionGateCreateView(ScopedMixin, APIView):
    def post(self, request, task_id):
        task = self.task_queryset(request).filter(pk=task_id).first()
        if not task:
            return error_response(
                ReconciliationError(
                    "BSEG_SOURCE_NOT_FOUND",
                    "Bank send task not found",
                    404,
                )
            )
        try:
            outcome = create_bank_send_execution_gate(
                user=request.user,
                task=task,
                idempotency_key=str(
                    request.data.get("idempotencyKey", "")
                ).strip(),
                expected_source_version=int(
                    request.data.get("expectedSourceVersion", -1)
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
                    "bankSendExecuted": False,
                    "bankMessageSent": False,
                    "paymentExecuted": False,
                    "fundsDebited": False,
                    "bankTransactionCreated": False,
                },
                status=201 if outcome["created"] else 200,
            )
        except ReconciliationError as exc:
            return error_response(exc)


class BankSendExecutionGateCanaryBlockedAttemptView(
    ScopedMixin,
    APIView,
):
    def post(self, request, scenario_code):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return error_response(
                ReconciliationError(
                    "BSEG_PRODUCTION_DISABLED",
                    "Canary blocked scenario is test-database only",
                    403,
                )
            )
        entry = BankSendExecutionGateCanaryPoolEntry.objects.filter(
            tenant_id=settings.PCE_CANARY_TENANT_ID,
            batch_id=settings.PCE_CANARY_BATCH_ID,
            pool_type="blocked",
            scenario_code=scenario_code,
        ).first()
        if not entry:
            return error_response(
                ReconciliationError(
                    "BSEG_SOURCE_NOT_FOUND",
                    "Blocked scenario not found",
                    404,
                )
            )
        return error_response(
            ReconciliationError(
                "BSEG_GATE_BLOCKED",
                entry.blocking_reason,
                409,
            )
        )
