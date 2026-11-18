from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payable_confirmation_prepare.models import PayableConfirmationPrepare
from purchase_canary.models import PurchaseCanaryBatch
from purchase_canary.read_models import (
    historical_lineage_facts,
    successful_lineage_by_object_no,
)
from reconciliation.services import ReconciliationError
from workflow_runtime.action_permissions import authorized_view_legal_entities

from .models import PaymentRequestPrepare, PaymentRequestPrepareCanaryScenario
from .services import (
    CANONICAL_NAME,
    GENERATE_ACTION,
    SAVE_ACTION,
    SOURCE_DOCUMENT_TYPE,
    VALIDATE_ACTION,
    VERSION,
    build_current_state,
    generate_payment_request_prepare,
    recover_action_result,
    save_payment_request_prepare_data,
    serialize_prepare,
    validate_payment_request_prepare,
)


def downstream_counts():
    return {
        "paymentRequests": 0,
        "payments": 0,
        "paymentInstructions": 0,
        "paymentVouchers": 0,
        "writeoffs": 0,
        "ledgerEntries": 0,
        "postings": 0,
        "bankTransactions": 0,
    }


def error_response(exc):
    classification = {
        "PRP_AUTH_UNAUTHENTICATED": "authentication_failed",
        "PRP_AUTH_PERMISSION_DENIED": "permission_denied",
        "PRP_AUTH_SCOPE_DENIED": "permission_denied",
        "PRP_AUTH_FEATURE_DISABLED": "feature_disabled",
        "PRP_AUTH_PRODUCTION_ROLLOUT_DISABLED": "permission_denied",
        "PRP_SOURCE_VERSION_CONFLICT": "version_conflict",
        "PRP_IDEMPOTENCY_PAYLOAD_CONFLICT": "idempotency_conflict",
        "PRP_IN_PROGRESS": "in_progress",
        "PRP_COMMIT_UNKNOWN": "commit_unknown",
    }.get(exc.code, "blocked")
    return Response({
        "result": "blocked",
        "version": VERSION,
        "classification": classification,
        "error": {
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
        },
        "paymentRequestCreated": False,
    }, status=exc.http_status)


class ScopedMixin:
    def get_permissions(self):
        permission = (
            AllowAny
            if getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            and self.request.method == "GET"
            else IsAuthenticated
        )
        return [permission()]

    def queryset(self, request):
        queryset = PaymentRequestPrepare.objects.select_related(
            "source_payable_confirmation_prepare",
            "number_reservation",
            "business_transaction",
            "audit_record",
        ).prefetch_related(
            "payment_data_snapshots",
            "validation_executions__issues",
        ).order_by("prepare_no")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            queryset = queryset.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
            if (
                getattr(settings, "PCE_ACTION_PERMISSION_ENFORCED", False)
                and request.user.is_authenticated
            ):
                legal_entity_ids = authorized_view_legal_entities(
                    request.user, "payment-request-prepare"
                )
                if legal_entity_ids is not None:
                    queryset = queryset.filter(
                        legal_entity_id__in=legal_entity_ids
                    )
            return queryset
        if request.user.is_superuser:
            return queryset
        return queryset.filter(company_id=request.user.company_id)


class PrepareListView(ScopedMixin, APIView):
    def get(self, request):
        batch_id = request.query_params.get(
            "canaryBatchId",
            getattr(settings, "PCE_CANARY_BATCH_ID", "PURCHASE-FLOW-DEMO-V1"),
        )
        scenario_class = request.query_params.get("scenarioClass", "all")
        scenario_code = request.query_params.get("scenarioCode", "")
        batch = PurchaseCanaryBatch.objects.filter(batch_id=batch_id).first()
        objects = list(self.queryset(request))
        lineage_by_number = successful_lineage_by_object_no(
            batch,
            [obj.prepare_no for obj in objects],
        )
        results = []
        for obj in objects:
            lineage = lineage_by_number.get(obj.prepare_no)
            if not lineage or (
                scenario_code and lineage.scenario_code != scenario_code
            ):
                continue
            results.append({
                **serialize_prepare(obj),
                **historical_lineage_facts(lineage, obj.prepare_no),
            })
        blocked_query = PaymentRequestPrepareCanaryScenario.objects.filter(
            batch_id=batch_id
        ).order_by("scenario_code")
        if scenario_code:
            blocked_query = blocked_query.filter(scenario_code=scenario_code)
        blocked = [{
            "scenarioCode": row.scenario_code,
            "scenarioClass": row.scenario_class,
            "scenarioRole": row.scenario_role,
            "blockingModule": row.blocking_module,
            "blockingRuleCode": row.blocking_rule_code,
            "blockingReason": row.blocking_reason,
            "currentLastValidObjectNo": row.current_last_valid_object_no,
            "formalObjectCount": row.formal_object_count,
            "nextStepAllowed": row.next_step_allowed,
            "scenarioHash": row.scenario_hash,
        } for row in blocked_query]
        scenarios = [{
            "scenarioCode": row["scenarioCode"],
            "scenarioClass": "pass_through",
            "scenarioRole": row["scenarioRole"],
            "currentModuleCode": "payment-request-prepare",
            "currentObjectNo": row["prepareNo"],
            "currentStatus": row["status"],
            "formalPaymentRequestPrepareCreated": True,
            "formalObjectCount": 1,
            "downstreamEligible": row["downstreamEligible"],
            "nextStepAllowed": row["eligibility"]["eligible"],
            "blockingModule": "",
            "blockingRuleCode": "",
            "blockingReason": "",
        } for row in results] + blocked
        if scenario_class == "success":
            scenarios = [row for row in scenarios if row["scenarioClass"] == "pass_through"]
        elif scenario_class == "blocked":
            scenarios = [row for row in scenarios if row["scenarioClass"] == "blocked"]
            results = []
        all_queryset = self.queryset(request)
        all_lineages = list(lineage_by_number.values())
        all_formal = all_queryset.count()
        eligible = sum(
            1 for obj in all_queryset
            if serialize_prepare(obj, include_issues=False)["eligibility"]["eligible"]
        )
        consumed = sum(
            historical_lineage_facts(
                lineage_by_number[obj.prepare_no],
                obj.prepare_no,
            )["nextStageConsumed"]
            for obj in objects
            if obj.prepare_no in lineage_by_number
        )
        capacity = {
            "canaryBatchId": batch_id,
            "passThroughLineageCount": len(all_lineages) if batch else 0,
            "blockedScenarioCount": PaymentRequestPrepareCanaryScenario.objects.filter(
                batch_id=batch_id
            ).count(),
            "formalPaymentRequestPrepareCount": all_formal,
            "downstreamEligibleSourceCount": eligible,
            "nextStageConsumedCount": consumed,
            "unconsumedAvailableCount": eligible - consumed,
            "nextModuleCode": "payment_request",
            "passed": (
                all_formal >= 8
                and eligible >= 8
                and consumed == all_formal
            ),
        }
        return Response({
            "result": "passed",
            "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "currentStateSource": "server",
            "data": {
                "count": len(results),
                "results": results,
                "capacity": capacity,
                "scenarioOverview": scenarios,
                "downstreamCounts": downstream_counts(),
                "paymentRequestCreated": False,
                "productionTenantFormalObjectCount": PaymentRequestPrepare.objects.exclude(
                    tenant_id=getattr(settings, "PCE_CANARY_TENANT_ID", "tenant-canary-demo")
                ).count(),
            },
        })


class PrepareDetailView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PRP_NOT_FOUND", "Prepare not found", 404))
        return Response({
            "result": "passed",
            "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "currentStateSource": "server",
            "data": serialize_prepare(obj),
            "downstreamCounts": downstream_counts(),
            "paymentRequestCreated": False,
        })


class PrepareBySourceView(ScopedMixin, APIView):
    def get(self, request, confirmation_prepare_id):
        source = PayableConfirmationPrepare.objects.filter(pk=confirmation_prepare_id).first()
        if not source:
            return error_response(ReconciliationError("PRP_SOURCE_NOT_FOUND", "Source not found", 404))
        return Response({
            "result": "passed",
            "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "currentStateSource": "server",
            "data": {
                "currentState": build_current_state(source),
                "paymentRequestCreated": False,
            },
        })


class GenerateView(ScopedMixin, APIView):
    def post(self, request):
        source = PayableConfirmationPrepare.objects.filter(
            pk=request.data.get("sourcePayableConfirmationPrepareId")
        ).first()
        if not source:
            return error_response(ReconciliationError("PRP_SOURCE_NOT_FOUND", "Source not found", 404))
        try:
            outcome = generate_payment_request_prepare(
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
                "canonicalName": CANONICAL_NAME,
                "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
                "paymentRequestCreated": False,
                **outcome,
            }, status=201 if outcome["created"] else 200)
        except ReconciliationError as exc:
            return error_response(exc)


class PaymentDataView(ScopedMixin, APIView):
    def put(self, request, prepare_id):
        obj = PaymentRequestPrepare.objects.filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PRP_NOT_FOUND", "Prepare not found", 404))
        try:
            outcome = save_payment_request_prepare_data(
                user=request.user,
                obj=obj,
                payload=request.data,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_version=int(request.data.get("expectedVersion", -1)),
                expected_payment_data_version=int(
                    request.data.get("expectedPaymentDataVersion", -1)
                ),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                failure_step=request.data.get("failureStep", ""),
            )
            return Response({
                "result": "passed",
                "version": VERSION,
                "paymentRequestCreated": False,
                **outcome,
            })
        except ReconciliationError as exc:
            return error_response(exc)


class ValidateView(ScopedMixin, APIView):
    def post(self, request, prepare_id):
        obj = PaymentRequestPrepare.objects.filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PRP_NOT_FOUND", "Prepare not found", 404))
        try:
            outcome = validate_payment_request_prepare(
                user=request.user,
                obj=obj,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_version=int(request.data.get("expectedVersion", -1)),
                expected_payment_data_version=int(request.data.get("expectedPaymentDataVersion", -1)),
                expected_confirmation_version=int(request.data.get("expectedConfirmationVersion", -1)),
                expected_accounting_data_version=int(request.data.get("expectedAccountingDataVersion", -1)),
                expected_confirmation_validation_version=int(
                    request.data.get("expectedConfirmationValidationVersion", -1)
                ),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                failure_step=request.data.get("failureStep", ""),
            )
            return Response({
                "result": "passed" if outcome["validated"] else "blocked",
                "version": VERSION,
                "paymentRequestCreated": False,
                **outcome,
            }, status=200 if outcome["validated"] else 409)
        except ReconciliationError as exc:
            return error_response(exc)


class ValidationIssuesView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PRP_NOT_FOUND", "Prepare not found", 404))
        data = serialize_prepare(obj)
        return Response({
            "result": "passed",
            "version": VERSION,
            "currentStateSource": "server",
            "data": data["validation"],
        })


class EligibilityView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PRP_NOT_FOUND", "Prepare not found", 404))
        return Response({
            "result": "passed",
            "version": VERSION,
            "currentStateSource": "server",
            "data": serialize_prepare(obj, include_issues=False)["eligibility"],
            "paymentRequestCreated": False,
        })


class ActionResultView(ScopedMixin, APIView):
    action_code = ""

    def get(self, request, idempotency_key):
        try:
            return Response({
                "result": "passed",
                "version": VERSION,
                "currentStateSource": "server",
                "paymentRequestCreated": False,
                **recover_action_result(self.action_code, idempotency_key),
            })
        except ReconciliationError as exc:
            return error_response(exc)


class GenerationResultView(ActionResultView):
    action_code = GENERATE_ACTION


class ValidationResultView(ActionResultView):
    action_code = VALIDATE_ACTION


class PaymentDataResultView(ActionResultView):
    action_code = SAVE_ACTION
