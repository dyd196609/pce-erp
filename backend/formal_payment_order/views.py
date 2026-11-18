from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payment_risk_review.services import eligibility as risk_review_eligibility
from reconciliation.services import ReconciliationError
from workflow_runtime.fact_loads import successful_fact_load_facts

from .models import (
    FormalPaymentOrder,
    FormalPaymentOrderCanaryScenario,
    FormalPaymentOrderSendGateCanaryScenario,
)
from .repositories import FormalPaymentOrderRepository, PaymentRiskReviewRepository
from .services import (
    CANONICAL_NAME,
    SEND_GATE_BATCH_ID,
    SOURCE_DOCUMENT_TYPE,
    VERSION,
    approve_formal_payment_order,
    freeze_formal_payment_order,
    generate_formal_payment_order,
    recover_generation_result,
    serialize_order,
    source_gate,
    submit_formal_payment_order,
)


def downstream_counts():
    return {
        "bankMessages": 0,
        "bankSendTasks": 0,
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
            "classification": {
                "FPO_AUTH_UNAUTHENTICATED": "authentication_failed",
                "FPO_PERMISSION_DENIED": "permission_denied",
                "FPO_PRODUCTION_DISABLED": "permission_denied",
                "FPO_VERSION_CONFLICT": "version_conflict",
                "FPO_IDEMPOTENCY_CONFLICT": "idempotency_conflict",
                "FPO_IN_PROGRESS": "in_progress",
                "FPO_SUBMIT_STATE_INVALID": "state_transition_blocked",
                "FPO_APPROVAL_STATE_INVALID": "state_transition_blocked",
                "FPO_APPROVAL_SEGREGATION_INVALID": "segregation_blocked",
                "FPO_FREEZE_REQUIRES_APPROVED_STATUS": "freeze_blocked",
                "FPO_FREEZE_GATE_BLOCKED": "freeze_blocked",
            }.get(exc.code, "blocked"),
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
            "bankMessageCreated": False,
            "paymentExecuted": False,
            "ledgerCreated": False,
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

    def order_queryset(self, request):
        queryset = FormalPaymentOrderRepository().queryset()
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return queryset.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(company_id=request.user.company_id)

    def source_queryset(self, request):
        queryset = PaymentRiskReviewRepository().queryset()
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return queryset.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(company_id=request.user.company_id)


def serialize_source(source):
    draft = source.source_payment_order_draft
    allowed = risk_review_eligibility(source)
    return {
        "id": source.pk,
        "reviewNo": source.review_no,
        "sourcePaymentOrderDraftNo": draft.draft_no,
        "scenarioCode": source.scenario_code,
        "supplierId": draft.supplier_id,
        "supplierName": draft.supplier_name,
        "currency": draft.currency,
        "amount": str(draft.payment_amount),
        "plannedExecutionDate": draft.planned_execution_date.isoformat(),
        "status": source.status,
        "riskResult": source.risk_result,
        "riskLevel": source.risk_level,
        "version": source.version,
        "reviewVersion": source.review_version,
        "eligibility": allowed,
        "currentStateSource": "server",
    }


class FormalPaymentOrderListView(ScopedMixin, APIView):
    def get(self, request):
        sources = list(self.source_queryset(request).filter(
            status="passed",
            risk_result="passed",
            risk_level="low",
        ))
        orders = list(self.order_queryset(request))
        results = [serialize_order(order) for order in orders]
        source_results = [serialize_source(source) for source in sources]
        batch_id = getattr(settings, "PCE_CANARY_BATCH_ID", "PURCHASE-FLOW-DEMO-V1")
        blocked = list(
            FormalPaymentOrderSendGateCanaryScenario.objects.filter(
                batch_id=SEND_GATE_BATCH_ID
            )
            .order_by("scenario_code")
            .values(
                "scenario_code",
                "blocking_fact",
                "blocking_reason",
                "bank_send_eligible",
                "bank_message_count",
                "payment_execution_count",
            )
        )
        capacity = {
            "sourceRiskReviewCount": len(source_results),
            "formalPaymentOrderCount": len(results),
            "preparedCount": sum(row["status"] == "prepared" for row in results),
            "approvedCount": sum(
                row["approvalStatus"] == "approved" for row in results
            ),
            "frozenCount": sum(
                row["freezeStatus"] == "frozen" for row in results
            ),
            "bankSendEligibleCount": sum(
                row["bankSendEligibility"]["readyForBankSend"] for row in results
            ),
            "blockedScenarioCount": len(blocked),
            "nextStageConsumedCount": 0,
            "unconsumedAvailableCount": len(results),
            "passed": (
                len(source_results) >= 8
                and len(results) >= 8
                and sum(row["approvalStatus"] == "approved" for row in results) >= 8
                and sum(row["freezeStatus"] == "frozen" for row in results) >= 8
                and sum(
                    row["bankSendEligibility"]["readyForBankSend"]
                    for row in results
                )
                >= 8
                and len(blocked) >= 15
            ),
        }
        tenant_id = getattr(
            settings,
            "PCE_CANARY_TENANT_ID",
            "tenant-canary-demo",
        )
        fact_load_facts = successful_fact_load_facts(
            result_count=len(results),
            api_url="/api/finance/formal-payment-orders/",
            tenant_id=tenant_id,
            batch_id=batch_id,
            request=request,
        )
        return Response({
            "result": "passed",
            "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "moduleCode": "formal-payment-order",
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "currentStateSource": "server",
            "data": {
                "count": len(results),
                "results": results,
                "sources": source_results,
                "tenantId": tenant_id,
                "batchId": batch_id,
                "canaryBatchId": batch_id,
                **fact_load_facts,
                "factLoadFacts": fact_load_facts,
                "capacity": capacity,
                "blockedScenarios": blocked,
                "downstreamCounts": downstream_counts(),
                "productionTenantFormalObjectCount": FormalPaymentOrder.objects.exclude(
                    tenant_id=getattr(settings, "PCE_CANARY_TENANT_ID", "tenant-canary-demo")
                ).count(),
                "productionRolloutEnabled": False,
            },
        })


class FormalPaymentOrderDetailView(ScopedMixin, APIView):
    def get(self, request, order_id):
        order = self.order_queryset(request).filter(pk=order_id).first()
        if not order:
            return error_response(ReconciliationError("FPO_NOT_FOUND", "Formal payment order not found", 404))
        return Response({
            "result": "passed",
            "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "currentStateSource": "server",
            "data": serialize_order(order),
            "downstreamCounts": downstream_counts(),
        })


class FormalPaymentOrderBySourceView(ScopedMixin, APIView):
    def get(self, request, source_id):
        source = self.source_queryset(request).filter(pk=source_id).first()
        if not source:
            return error_response(ReconciliationError("FPO_SOURCE_NOT_FOUND", "Risk review not found", 404))
        target = self.order_queryset(request).filter(source_risk_review=source).first()
        reasons = source_gate(source, check_existing=False)
        return Response({
            "result": "passed",
            "version": VERSION,
            "currentStateSource": "server",
            "data": {
                "targetExistenceStatus": "single_target" if target else "no_target",
                "targetCount": 1 if target else 0,
                "generationAllowed": not target and not reasons,
                "generationStatus": "existing_target" if target else ("eligible" if not reasons else "blocked"),
                "blockingReasons": reasons,
                "formalPaymentOrder": serialize_order(target) if target else None,
            },
        })


class FormalPaymentOrderGenerateView(ScopedMixin, APIView):
    def post(self, request):
        source = PaymentRiskReviewRepository().get(request.data.get("sourceRiskReviewId"))
        if not source:
            return error_response(ReconciliationError("FPO_SOURCE_NOT_FOUND", "Risk review not found", 404))
        try:
            outcome = generate_formal_payment_order(
                user=request.user,
                source=source,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_source_version=int(request.data.get("expectedSourceVersion", -1)),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                failure_step=request.data.get("failureStep", ""),
            )
            return Response({
                "result": "passed",
                "version": VERSION,
                **outcome,
                "bankMessageCreated": False,
                "paymentExecuted": False,
                "ledgerCreated": False,
            }, status=201 if outcome["created"] else 200)
        except ReconciliationError as exc:
            return error_response(exc)


class FormalPaymentOrderGenerationResultView(ScopedMixin, APIView):
    def get(self, request, idempotency_key):
        try:
            return Response({
                "result": "passed",
                "version": VERSION,
                "currentStateSource": "server",
                **recover_generation_result(idempotency_key),
            })
        except ReconciliationError as exc:
            return error_response(exc)


class FormalPaymentOrderSubmitView(ScopedMixin, APIView):
    def post(self, request, order_id):
        order = self.order_queryset(request).filter(pk=order_id).first()
        if not order:
            return error_response(
                ReconciliationError("FPO_NOT_FOUND", "Formal payment order not found", 404)
            )
        try:
            result = submit_formal_payment_order(
                user=request.user,
                order=order,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_version=int(request.data.get("expectedVersion", -1)),
                explicit_user_action=request.data.get("explicitUserAction") is True,
            )
            return Response(
                {
                    "result": "passed",
                    "version": VERSION,
                    **result,
                    "bankMessageCreated": False,
                    "paymentExecuted": False,
                    "ledgerCreated": False,
                }
            )
        except ReconciliationError as exc:
            return error_response(exc)


class FormalPaymentOrderApproveView(ScopedMixin, APIView):
    def post(self, request, order_id):
        order = self.order_queryset(request).filter(pk=order_id).first()
        if not order:
            return error_response(
                ReconciliationError("FPO_NOT_FOUND", "Formal payment order not found", 404)
            )
        try:
            result = approve_formal_payment_order(
                user=request.user,
                order=order,
                task_id=int(request.data.get("taskId", 0)),
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_order_version=int(
                    request.data.get("expectedOrderVersion", -1)
                ),
                expected_workflow_version=int(
                    request.data.get("expectedWorkflowVersion", -1)
                ),
                expected_task_version=int(
                    request.data.get("expectedTaskVersion", -1)
                ),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                comment=request.data.get("comment", ""),
            )
            return Response(
                {
                    "result": "passed",
                    "version": VERSION,
                    **result,
                    "bankMessageCreated": False,
                    "paymentExecuted": False,
                    "ledgerCreated": False,
                }
            )
        except ReconciliationError as exc:
            return error_response(exc)


class FormalPaymentOrderFreezeView(ScopedMixin, APIView):
    def post(self, request, order_id):
        order = self.order_queryset(request).filter(pk=order_id).first()
        if not order:
            return error_response(
                ReconciliationError("FPO_NOT_FOUND", "Formal payment order not found", 404)
            )
        try:
            result = freeze_formal_payment_order(
                user=request.user,
                order=order,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_order_version=int(
                    request.data.get("expectedOrderVersion", -1)
                ),
                expected_approval_version=int(
                    request.data.get("expectedApprovalVersion", -1)
                ),
                explicit_user_action=request.data.get("explicitUserAction") is True,
            )
            return Response(
                {
                    "result": "passed",
                    "version": VERSION,
                    **result,
                    "bankMessageCreated": False,
                    "paymentExecuted": False,
                    "ledgerCreated": False,
                }
            )
        except ReconciliationError as exc:
            return error_response(exc)


class FormalPaymentOrderApprovalHistoryView(ScopedMixin, APIView):
    def get(self, request, order_id):
        order = self.order_queryset(request).filter(pk=order_id).first()
        if not order:
            return error_response(
                ReconciliationError("FPO_NOT_FOUND", "Formal payment order not found", 404)
            )
        serialized = serialize_order(order)
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "currentStateSource": "server",
                "data": {
                    "approvalStatus": serialized["approvalStatus"],
                    "workflowInstance": serialized["workflowInstance"],
                    "approvalHistory": serialized["approvalHistory"],
                },
            }
        )
