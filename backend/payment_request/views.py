from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payment_request_prepare.models import PaymentRequestPrepare
from purchase_canary.models import PurchaseCanaryBatch
from reconciliation.services import ReconciliationError
from workflow_runtime.models import ApprovalTask
from workflow_runtime.action_permissions import authorized_view_legal_entities
from workflow_runtime.fact_loads import successful_fact_load_facts

from .models import PaymentRequest, PaymentRequestCanaryScenario
from .services import (
    APPROVE_ACTION,
    CANONICAL_NAME,
    GENERATE_ACTION,
    REJECT_ACTION,
    SOURCE_DOCUMENT_TYPE,
    SUBMIT_ACTION,
    VERSION,
    build_instruction_prepare_eligibility,
    decide_payment_request,
    generate_payment_request,
    recover_action_result,
    serialize_payment_request,
    serialize_source_eligibility,
    submit_payment_request,
)


def downstream_counts():
    return {
        "paymentInstructionPrepares": 0, "payments": 0, "paymentInstructions": 0,
        "paymentVouchers": 0, "writeoffs": 0, "ledgerEntries": 0,
        "postings": 0, "bankTransactions": 0,
    }


def error_response(exc):
    return Response({
        "result": "blocked", "version": VERSION,
        "classification": "blocked",
        "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
        "paymentInstructionPrepareCreated": False,
    }, status=exc.http_status)


class ScopedMixin:
    def get_permissions(self):
        permission = (
            AllowAny if getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            and self.request.method == "GET" else IsAuthenticated
        )
        return [permission()]

    def queryset(self, request):
        query = PaymentRequest.objects.select_related(
            "source_payment_request_prepare", "number_reservation",
            "business_transaction", "audit_record", "workflow_instance",
        ).prefetch_related(
            "workflow_instance__tasks__decisions", "workflow_relations__approval_route"
        ).order_by("request_no")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            query = query.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
            if (
                getattr(settings, "PCE_ACTION_PERMISSION_ENFORCED", False)
                and request.user.is_authenticated
            ):
                legal_entity_ids = authorized_view_legal_entities(
                    request.user, "payment-request"
                )
                if legal_entity_ids is not None:
                    query = query.filter(legal_entity_id__in=legal_entity_ids)
            return query
        if request.user.is_superuser:
            return query
        return query.filter(company_id=request.user.company_id)


class PaymentRequestListView(ScopedMixin, APIView):
    def get(self, request):
        batch_id = request.query_params.get(
            "canaryBatchId",
            getattr(settings, "PCE_CANARY_BATCH_ID", "PURCHASE-FLOW-DEMO-V1"),
        )
        results = [serialize_payment_request(obj) for obj in self.queryset(request)]
        scenarios = [{
            "scenarioCode": f"SUCCESS-{index:02d}", "scenarioClass": "pass_through",
            "scenarioRole": "approved payment request", "currentObjectNo": row["requestNo"],
            "currentStatus": row["status"],
            "downstreamEligible": row["eligibility"]["eligible"],
            "blockingRuleCode": "", "blockingReason": "",
        } for index, row in enumerate(results, 1)]
        scenarios += [{
            "scenarioCode": row.scenario_code, "scenarioClass": row.scenario_class,
            "scenarioRole": row.scenario_role,
            "currentObjectNo": row.current_last_valid_object_no,
            "currentStatus": "blocked", "downstreamEligible": False,
            "blockingRuleCode": row.blocking_rule_code,
            "blockingReason": row.blocking_reason,
        } for row in PaymentRequestCanaryScenario.objects.filter(batch_id=batch_id).order_by("scenario_code")]
        batch = PurchaseCanaryBatch.objects.filter(batch_id=batch_id).first()
        source_count = PaymentRequestPrepare.objects.filter(
            tenant_id=getattr(settings, "PCE_CANARY_TENANT_ID", "tenant-canary-demo")
        ).count()
        eligible = sum(1 for row in results if row["eligibility"]["eligible"])
        consumed = (
            batch.lineages.filter(current_module_code="payment-request", next_stage_consumed=True).count()
            if batch else 0
        )
        capacity = {
            "canaryBatchId": batch_id, "passThroughLineageCount": len(results),
            "blockedScenarioCount": PaymentRequestCanaryScenario.objects.filter(batch_id=batch_id).count(),
            "formalPaymentRequestCount": len(results),
            "approvedPaymentRequestCount": sum(row["status"] == "approved" for row in results),
            "downstreamEligibleSourceCount": eligible,
            "nextStageConsumedCount": consumed,
            "unconsumedAvailableCount": eligible - consumed,
            "paymentRequestPrepareSourceCount": source_count,
            "paymentRequestPrepareConsumedCount": len(results),
            "nextModuleCode": "payment_instruction_prepare",
            "passed": len(results) >= 8 and eligible >= 8 and consumed == 0,
        }
        tenant_id = getattr(
            settings,
            "PCE_CANARY_TENANT_ID",
            "tenant-canary-demo",
        )
        fact_load_facts = successful_fact_load_facts(
            result_count=len(results),
            api_url="/api/finance/payment-requests/",
            tenant_id=tenant_id,
            batch_id=batch_id,
            request=request,
        )
        return Response({
            "result": "passed", "version": VERSION, "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE, "currentStateSource": "server",
            "data": {
                "count": len(results), "results": results, "capacity": capacity,
                "tenantId": tenant_id,
                "batchId": batch_id,
                "canaryBatchId": batch_id,
                **fact_load_facts,
                "factLoadFacts": fact_load_facts,
                "scenarioOverview": scenarios, "downstreamCounts": downstream_counts(),
                "paymentInstructionPrepareCreated": False,
                "productionTenantFormalObjectCount": PaymentRequest.objects.exclude(
                    tenant_id=getattr(settings, "PCE_CANARY_TENANT_ID", "tenant-canary-demo")
                ).count(),
            },
        })


class PaymentRequestDetailView(ScopedMixin, APIView):
    def get(self, request, request_id):
        obj = self.queryset(request).filter(pk=request_id).first()
        if not obj:
            return error_response(ReconciliationError("PAYREQ_NOT_FOUND", "Request not found", 404))
        return Response({
            "result": "passed", "version": VERSION, "canonicalName": CANONICAL_NAME,
            "currentStateSource": "server", "data": serialize_payment_request(obj),
            "downstreamCounts": downstream_counts(),
        })


class PaymentRequestBySourceView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        source = PaymentRequestPrepare.objects.filter(pk=prepare_id).first()
        if not source:
            return error_response(ReconciliationError("PAYREQ_SOURCE_NOT_FOUND", "Source not found", 404))
        target = self.queryset(request).filter(source_payment_request_prepare=source).first()
        return Response({
            "result": "passed", "version": VERSION, "currentStateSource": "server",
            "data": {
                "sourceEligibility": serialize_source_eligibility(source),
                "paymentRequest": serialize_payment_request(target) if target else None,
            },
        })


class GenerateView(ScopedMixin, APIView):
    def post(self, request):
        source = PaymentRequestPrepare.objects.filter(
            pk=request.data.get("sourcePaymentRequestPrepareId")
        ).first()
        if not source:
            return error_response(ReconciliationError("PAYREQ_SOURCE_NOT_FOUND", "Source not found", 404))
        try:
            outcome = generate_payment_request(
                user=request.user, source=source,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_source_version=int(request.data.get("expectedSourceVersion", -1)),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                failure_step=request.data.get("failureStep", ""),
            )
            return Response({"result": "passed", "version": VERSION, **outcome},
                            status=201 if outcome["created"] else 200)
        except ReconciliationError as exc:
            return error_response(exc)


class SubmitView(ScopedMixin, APIView):
    def post(self, request, request_id):
        obj = PaymentRequest.objects.filter(pk=request_id).first()
        if not obj:
            return error_response(ReconciliationError("PAYREQ_NOT_FOUND", "Request not found", 404))
        try:
            outcome = submit_payment_request(
                user=request.user, obj=obj,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_version=int(request.data.get("expectedVersion", -1)),
                expected_source_prepare_version=int(request.data.get("expectedSourcePrepareVersion", -1)),
                expected_payment_data_version=int(request.data.get("expectedPaymentDataVersion", -1)),
                expected_source_validation_version=int(request.data.get("expectedSourceValidationVersion", -1)),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                application_reason=request.data.get("applicationReason", ""),
                failure_step=request.data.get("failureStep", ""),
            )
            return Response({"result": "passed", "version": VERSION, **outcome})
        except ReconciliationError as exc:
            return error_response(exc)


class DecisionView(ScopedMixin, APIView):
    decision = "approved"

    def post(self, request, request_id, task_id):
        obj = PaymentRequest.objects.filter(pk=request_id).first()
        task = ApprovalTask.objects.filter(pk=task_id).first()
        if not obj or not task:
            return error_response(ReconciliationError("PAYREQ_APPROVE_TASK_EXISTS", "Task not found", 404))
        try:
            outcome = decide_payment_request(
                user=request.user, obj=obj, task=task, decision=self.decision,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_payment_request_version=int(request.data.get("expectedPaymentRequestVersion", -1)),
                expected_workflow_version=int(request.data.get("expectedWorkflowVersion", -1)),
                expected_task_version=int(request.data.get("expectedTaskVersion", -1)),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                decision_comment=request.data.get("decisionComment", ""),
                failure_step=request.data.get("failureStep", ""),
            )
            return Response({"result": "passed", "version": VERSION, **outcome})
        except ReconciliationError as exc:
            return error_response(exc)


class ApproveView(DecisionView):
    decision = "approved"


class RejectView(DecisionView):
    decision = "rejected"


class ApprovalRouteView(ScopedMixin, APIView):
    def get(self, request, request_id):
        obj = self.queryset(request).filter(pk=request_id).first()
        return Response({"result": "passed", "version": VERSION, "currentStateSource": "server",
                         "data": serialize_payment_request(obj)["approvalRoute"] if obj else []})


class ApprovalTasksView(ScopedMixin, APIView):
    def get(self, request, request_id):
        obj = self.queryset(request).filter(pk=request_id).first()
        return Response({"result": "passed", "version": VERSION, "currentStateSource": "server",
                         "data": serialize_payment_request(obj)["approvalTasks"] if obj else []})


class ApprovalHistoryView(ScopedMixin, APIView):
    def get(self, request, request_id):
        obj = self.queryset(request).filter(pk=request_id).first()
        return Response({"result": "passed", "version": VERSION, "currentStateSource": "server",
                         "data": serialize_payment_request(obj)["approvalHistory"] if obj else []})


class EligibilityView(ScopedMixin, APIView):
    def get(self, request, request_id):
        obj = self.queryset(request).filter(pk=request_id).first()
        if not obj:
            return error_response(ReconciliationError("PAYREQ_NOT_FOUND", "Request not found", 404))
        return Response({"result": "passed", "version": VERSION, "currentStateSource": "server",
                         "data": build_instruction_prepare_eligibility(obj)})


class ActionResultView(ScopedMixin, APIView):
    action_code = ""

    def get(self, request, idempotency_key):
        try:
            return Response({"result": "passed", "version": VERSION,
                             "currentStateSource": "server",
                             **recover_action_result(self.action_code, idempotency_key)})
        except ReconciliationError as exc:
            return error_response(exc)


class GenerationResultView(ActionResultView):
    action_code = GENERATE_ACTION


class SubmissionResultView(ActionResultView):
    action_code = SUBMIT_ACTION


class ApprovalResultView(ActionResultView):
    action_code = APPROVE_ACTION


class RejectionResultView(ActionResultView):
    action_code = REJECT_ACTION
