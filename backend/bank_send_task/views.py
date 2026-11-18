from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bank_send_preparation.repositories import BankSendPreparationRepository
from reconciliation.services import ReconciliationError
from workflow_runtime.action_permissions import (
    ActionPermissionValidator,
    authorized_view_legal_entities,
)

from .canary import (
    bank_send_task_canary_facts,
    replenish_bank_send_task_canary_pool,
)
from .models import BankSendTask, BankSendTaskCanaryPoolEntry
from .repositories import BankSendTaskRepository
from .services import (
    CANONICAL_NAME,
    MODULE_CODE,
    SOURCE_DOCUMENT_TYPE,
    VERSION,
    bank_send_task_facts_for_rows,
    create_bank_send_task,
    downstream_counts,
    evaluate_task_creation_gate,
    serialize_task,
)


def error_response(exc):
    return Response(
        {
            "result": "blocked",
            "version": VERSION,
            "classification": {
                "BST_PERMISSION_DENIED": "permission_denied",
                "BST_PRODUCTION_DISABLED": "permission_denied",
                "BST_VERSION_CONFLICT": "version_conflict",
                "BST_IDEMPOTENCY_CONFLICT": "idempotency_conflict",
                "BST_GATE_CHANGED": "gate_changed",
                "BST_GATE_BLOCKED": "gate_blocked",
                "BST_SOURCE_LOCKED": "source_locked",
            }.get(exc.code, "blocked"),
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
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

    def task_queryset(self, request):
        queryset = BankSendTaskRepository().queryset()
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

    def source_queryset(self, request):
        queryset = BankSendPreparationRepository().queryset()
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


class BankSendTaskListView(ScopedMixin, APIView):
    def get(self, request):
        tasks = [serialize_task(row) for row in self.task_queryset(request)]
        sources = [
            {
                "id": row.pk,
                "prepareNo": row.prepare_no,
                "sourceFormalPaymentOrderNo":
                    row.source_formal_payment_order_no,
                "status": row.status,
                "version": row.version,
                "legalEntityId": row.legal_entity_id,
                "supplierName": row.supplier_name,
                "currency": row.currency,
                "amount": str(row.amount),
                "plannedExecutionDate":
                    row.planned_execution_date.isoformat(),
                "messagePreview": {
                    "exists": hasattr(row, "message_preview"),
                    "previewNo": (
                        row.message_preview.preview_no
                        if hasattr(row, "message_preview")
                        else ""
                    ),
                    "status": (
                        row.message_preview.status
                        if hasattr(row, "message_preview")
                        else "not_generated"
                    ),
                    "sent": False,
                },
                "taskEligibility": evaluate_task_creation_gate(row),
                "targetExists": hasattr(row, "send_task"),
                "targetTaskNo": (
                    row.send_task.task_no if hasattr(row, "send_task") else ""
                ),
                "currentStateSource": "server",
            }
            for row in self.source_queryset(request)
        ]
        canary_pool_facts = bank_send_task_canary_facts()
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
        facts = bank_send_task_facts_for_rows(
            sources=sources,
            rows=tasks,
            canary_pool_facts=canary_pool_facts,
            tenant_id=tenant_id,
            batch_id=batch_id,
            request=request,
        )
        fact_load_facts = facts["factLoadFacts"]
        capacity = {
            key: facts[key]
            for key in (
                "sourceBankSendPreparationCount",
                "previewReadySourceCount",
                "bankSendTaskCount",
                "taskCount",
                "preparedCount",
                "queuedCount",
                "readyToSendCount",
                "sentCount",
                "executionCount",
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
                    "count": facts["bankSendTaskCount"],
                    "results": tasks,
                    "sources": sources,
                    "capacity": capacity,
                    "downstreamCounts": downstream_counts(),
                    "writeIntentFacts": facts["writeIntentFacts"],
                    "bankSendTaskFacts": facts,
                    "canaryPoolFacts": canary_pool_facts,
                    "bankSendExecutionEnabled": False,
                    "productionRolloutEnabled": False,
                    "productionTenantObjectCount":
                        BankSendTask.objects.exclude(
                            tenant_id=getattr(
                                settings,
                                "PCE_CANARY_TENANT_ID",
                                "tenant-canary-demo",
                            )
                        ).count(),
                },
            }
        )


class BankSendTaskDetailView(ScopedMixin, APIView):
    def get(self, request, task_id):
        task = self.task_queryset(request).filter(pk=task_id).first()
        if not task:
            return error_response(
                ReconciliationError(
                    "BST_NOT_FOUND",
                    "Bank send task not found",
                    404,
                )
            )
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "canonicalName": CANONICAL_NAME,
                "currentStateSource": "server",
                "data": serialize_task(task),
            }
        )


class BankSendTaskCreateView(ScopedMixin, APIView):
    def post(self, request, preparation_id):
        preparation = BankSendPreparationRepository().get(preparation_id)
        if not preparation:
            return error_response(
                ReconciliationError(
                    "BST_SOURCE_NOT_FOUND",
                    "Bank send preparation not found",
                    404,
                )
            )
        try:
            outcome = create_bank_send_task(
                user=request.user,
                preparation=preparation,
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
                    "bankMessageSent": False,
                    "paymentExecuted": False,
                    "fundsDebited": False,
                    "bankTransactionCreated": False,
                },
                status=201 if outcome["created"] else 200,
            )
        except ReconciliationError as exc:
            return error_response(exc)


class BankSendTaskCanaryPoolReplenishView(ScopedMixin, APIView):
    def post(self, request):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return error_response(
                ReconciliationError(
                    "BST_PRODUCTION_DISABLED",
                    "Canary pool replenishment is test-database only",
                    403,
                )
            )
        source = self.source_queryset(request).order_by("pk").first()
        decision = ActionPermissionValidator().evaluate(
            user=request.user,
            module_code=MODULE_CODE,
            action_code="create-bank-send-task",
            object_ids=[source.pk] if source else [],
            selection_count=1 if source else 0,
        )
        if not decision["granted"]:
            return error_response(
                ReconciliationError(
                    "BST_PERMISSION_DENIED",
                    "Bank-send task test role is required",
                    403,
                )
            )
        count = min(max(int(request.data.get("count", 8)), 1), 20)
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "currentStateSource": "server",
                "data": replenish_bank_send_task_canary_pool(count=count),
            }
        )


class BankSendTaskCanaryBlockedAttemptView(ScopedMixin, APIView):
    def post(self, request, scenario_code):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return error_response(
                ReconciliationError(
                    "BST_PRODUCTION_DISABLED",
                    "Canary blocked scenario is test-database only",
                    403,
                )
            )
        row = BankSendTaskCanaryPoolEntry.objects.filter(
            tenant_id=settings.PCE_CANARY_TENANT_ID,
            batch_id=settings.PCE_CANARY_BATCH_ID,
            pool_type=BankSendTaskCanaryPoolEntry.PoolType.BLOCKED,
            scenario_code=scenario_code,
        ).first()
        if not row:
            return error_response(
                ReconciliationError(
                    "BST_SOURCE_NOT_FOUND",
                    "Canary blocked scenario not found",
                    404,
                )
            )
        return error_response(
            ReconciliationError(
                "BST_GATE_BLOCKED",
                row.blocking_reason,
                409,
            )
        )
