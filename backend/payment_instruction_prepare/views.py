from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payment_request.models import PaymentRequest
from purchase_canary.models import PurchaseCanaryBatch
from purchase_canary.read_models import (
    historical_lineage_facts,
    successful_lineage_by_object_no,
)
from reconciliation.services import ReconciliationError
from workflow_runtime.fact_loads import successful_fact_load_facts

from .models import PaymentInstructionPrepare, PaymentInstructionPrepareCanaryScenario
from .services import (
    CANONICAL_NAME,
    GENERATE_ACTION,
    NEXT_CANONICAL_NAME,
    NEXT_MODULE_CODE,
    NEXT_ROUTE,
    SAVE_ACTION,
    SOURCE_DOCUMENT_TYPE,
    VALIDATE_ACTION,
    VERSION,
    generate_payment_instruction_prepare,
    recover_action_result,
    save_instruction_data,
    serialize_prepare,
    source_gate,
    validate_instruction_prepare,
)


def downstream_counts():
    return {
        "nextModuleObjects": 0,
        "formalPaymentInstructions": 0,
        "paymentExecutions": 0,
        "bankMessages": 0,
        "paymentVouchers": 0,
        "writeoffs": 0,
        "ledgerEntries": 0,
        "postings": 0,
        "bankTransactions": 0,
    }


def error_response(exc):
    classification = {
        "PIP_AUTH_UNAUTHENTICATED": "authentication_failed",
        "PIP_AUTH_PERMISSION_DENIED": "permission_denied",
        "PIP_AUTH_SCOPE_DENIED": "permission_denied",
        "PIP_AUTH_FEATURE_DISABLED": "feature_disabled",
        "PIP_AUTH_PRODUCTION_ROLLOUT_DISABLED": "permission_denied",
        "VERSION_CONFLICT": "version_conflict",
        "PIP_IDEMPOTENCY_PAYLOAD_CONFLICT": "idempotency_conflict",
        "PIP_IN_PROGRESS": "in_progress",
        "PIP_COMMIT_UNKNOWN": "commit_unknown",
    }.get(exc.code, "blocked")
    return Response({
        "result": "blocked", "version": VERSION, "classification": classification,
        "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
        "nextModuleObjectCreated": False,
        "formalPaymentInstructionCreated": False,
        "paymentExecuted": False,
    }, status=exc.http_status)


class ScopedMixin:
    def get_permissions(self):
        permission = (
            AllowAny if getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            and self.request.method == "GET" else IsAuthenticated
        )
        return [permission()]

    def queryset(self, request):
        queryset = PaymentInstructionPrepare.objects.select_related(
            "source_payment_request", "number_reservation",
            "business_transaction", "audit_record",
        ).prefetch_related(
            "instruction_data_snapshots__previews",
            "validation_executions__issues",
        ).order_by("prepare_no")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return queryset.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(company_id=request.user.company_id)


class PrepareListView(ScopedMixin, APIView):
    def get(self, request):
        batch_id = request.query_params.get(
            "canaryBatchId", getattr(settings, "PCE_CANARY_BATCH_ID", "PURCHASE-FLOW-DEMO-V1")
        )
        batch = PurchaseCanaryBatch.objects.filter(batch_id=batch_id).first()
        objects = list(self.queryset(request))
        lineage_by_number = successful_lineage_by_object_no(
            batch,
            [obj.prepare_no for obj in objects],
        )
        results = []
        for obj in objects:
            row = lineage_by_number.get(obj.prepare_no)
            if not row:
                continue
            results.append({
                **serialize_prepare(obj),
                **historical_lineage_facts(row, obj.prepare_no),
            })
        blocked_rows = PaymentInstructionPrepareCanaryScenario.objects.filter(
            batch_id=batch_id
        ).order_by("scenario_code")
        blocked = [{
            "scenarioCode": row.scenario_code, "scenarioClass": "blocked",
            "scenarioRole": row.scenario_code.lower(),
            "blockingRuleCode": row.blocking_rule_code,
            "blockingReason": row.blocking_reason,
            "formalObjectCount": row.formal_object_count,
            "nextStepAllowed": row.next_step_allowed,
        } for row in blocked_rows]
        success = [{
            "scenarioCode": row["scenarioCode"], "scenarioClass": "pass_through",
            "scenarioRole": row["scenarioRole"], "currentObjectNo": row["prepareNo"],
            "currentStatus": row["status"], "formalObjectCount": 1,
            "nextStepAllowed": row["eligibility"]["eligible"],
        } for row in results]
        eligible = sum(1 for row in results if row["eligibility"]["eligible"])
        consumed = sum(1 for row in results if row["nextStageConsumed"])
        capacity = {
            "canaryBatchId": batch_id, "paymentRequestSourceCount": len(results),
            "paymentRequestConsumedCount": len(results),
            "passThroughLineageCount": len(results),
            "blockedScenarioCount": len(blocked),
            "formalPaymentInstructionPrepareCount": len(results),
            "validatedPaymentInstructionPrepareCount": sum(
                1 for row in results if row["status"] == "validated"
            ),
            "preparedPaymentInstructionPrepareCount": sum(
                1 for row in results if row["status"] == "validated"
            ),
            "downstreamEligibleSourceCount": eligible,
            "nextStageConsumedCount": consumed,
            "unconsumedAvailableCount": eligible - consumed,
            "nextModuleCode": NEXT_MODULE_CODE,
            "nextCanonicalName": NEXT_CANONICAL_NAME,
            "nextRoute": NEXT_ROUTE,
            "passed": (
                len(results) >= 8
                and eligible >= 8
                and consumed == len(results)
            ),
        }
        tenant_id = getattr(
            settings,
            "PCE_CANARY_TENANT_ID",
            "tenant-canary-demo",
        )
        fact_load_facts = successful_fact_load_facts(
            result_count=len(results),
            api_url="/api/finance/payment-instruction-prepares/",
            tenant_id=tenant_id,
            batch_id=batch_id,
            request=request,
        )
        return Response({
            "result": "passed", "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "currentStateSource": "server",
            "data": {
                "count": len(results), "results": results,
                "tenantId": tenant_id,
                "batchId": batch_id,
                "canaryBatchId": batch_id,
                **fact_load_facts,
                "factLoadFacts": fact_load_facts,
                "capacity": capacity, "scenarioOverview": success + blocked,
                "downstreamCounts": downstream_counts(),
                "productionTenantFormalObjectCount": PaymentInstructionPrepare.objects.exclude(
                    tenant_id=getattr(settings, "PCE_CANARY_TENANT_ID", "tenant-canary-demo")
                ).count(),
                "productionRolloutEnabled": False,
            },
        })


class PrepareDetailView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PIP_NOT_FOUND", "Prepare not found", 404))
        return Response({
            "result": "passed", "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "currentStateSource": "server",
            "data": serialize_prepare(obj),
            "downstreamCounts": downstream_counts(),
        })


class PrepareBySourceView(ScopedMixin, APIView):
    def get(self, request, payment_request_id):
        source = PaymentRequest.objects.filter(pk=payment_request_id).first()
        if not source:
            return error_response(ReconciliationError("PIP_SOURCE_NOT_FOUND", "Source not found", 404))
        target = self.queryset(request).filter(source_payment_request=source).first()
        return Response({
            "result": "passed", "version": VERSION,
            "currentStateSource": "server",
            "data": {
                "targetExistenceStatus": "single_target" if target else "no_target",
                "targetCount": 1 if target else 0,
                "generationAllowed": not target and not source_gate(source, check_existing=False),
                "generationStatus": "existing_target" if target else "not_started",
                "paymentInstructionPrepare": serialize_prepare(target) if target else None,
            },
        })


class GenerateView(ScopedMixin, APIView):
    def post(self, request):
        source = PaymentRequest.objects.filter(
            pk=request.data.get("sourcePaymentRequestId")
        ).first()
        if not source:
            return error_response(ReconciliationError("PIP_SOURCE_NOT_FOUND", "Source not found", 404))
        try:
            outcome = generate_payment_instruction_prepare(
                user=request.user, source=source,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_source_version=int(request.data.get("expectedSourceVersion", -1)),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                failure_step=request.data.get("failureStep", ""),
            )
            return Response({
                "result": "passed", "version": VERSION,
                "nextModuleObjectCreated": False,
                "formalPaymentInstructionCreated": False,
                "paymentExecuted": False, **outcome,
            }, status=201 if outcome["created"] else 200)
        except ReconciliationError as exc:
            return error_response(exc)


class InstructionDataView(ScopedMixin, APIView):
    def put(self, request, prepare_id):
        obj = PaymentInstructionPrepare.objects.filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PIP_NOT_FOUND", "Prepare not found", 404))
        try:
            return Response({
                "result": "passed", "version": VERSION,
                "nextModuleObjectCreated": False,
                "formalPaymentInstructionCreated": False,
                "paymentExecuted": False,
                **save_instruction_data(
                    user=request.user, obj=obj, payload=request.data,
                    idempotency_key=request.data.get("idempotencyKey", ""),
                    expected_version=int(request.data.get("expectedVersion", -1)),
                    explicit_user_action=request.data.get("explicitUserAction") is True,
                    failure_step=request.data.get("failureStep", ""),
                ),
            })
        except ReconciliationError as exc:
            return error_response(exc)


class ValidateView(ScopedMixin, APIView):
    def post(self, request, prepare_id):
        obj = PaymentInstructionPrepare.objects.filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PIP_NOT_FOUND", "Prepare not found", 404))
        try:
            outcome = validate_instruction_prepare(
                user=request.user, obj=obj,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_version=int(request.data.get("expectedVersion", -1)),
                expected_instruction_data_version=int(
                    request.data.get("expectedInstructionDataVersion", -1)
                ),
                expected_source_version=int(request.data.get("expectedSourceVersion", -1)),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                failure_step=request.data.get("failureStep", ""),
            )
            return Response({
                "result": "passed" if outcome["validated"] else "blocked",
                "version": VERSION, "nextModuleObjectCreated": False,
                "formalPaymentInstructionCreated": False,
                "paymentExecuted": False, **outcome,
            }, status=200 if outcome["validated"] else 409)
        except ReconciliationError as exc:
            return error_response(exc)


class EligibilityView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PIP_NOT_FOUND", "Prepare not found", 404))
        return Response({
            "result": "passed", "version": VERSION, "currentStateSource": "server",
            "data": serialize_prepare(obj, include_issues=False)["eligibility"],
        })


class ValidationIssuesView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PIP_NOT_FOUND", "Prepare not found", 404))
        return Response({
            "result": "passed", "version": VERSION, "currentStateSource": "server",
            "data": serialize_prepare(obj)["validation"],
        })


class ActionResultView(ScopedMixin, APIView):
    action_code = ""

    def get(self, request, idempotency_key):
        try:
            return Response({
                "result": "passed", "version": VERSION,
                "currentStateSource": "server",
                **recover_action_result(self.action_code, idempotency_key),
            })
        except ReconciliationError as exc:
            return error_response(exc)


class GenerationResultView(ActionResultView):
    action_code = GENERATE_ACTION


class InstructionDataResultView(ActionResultView):
    action_code = SAVE_ACTION


class ValidationResultView(ActionResultView):
    action_code = VALIDATE_ACTION
