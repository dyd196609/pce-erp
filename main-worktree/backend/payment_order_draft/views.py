from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payment_order_prepare.models import PaymentOrderPrepare
from purchase_canary.models import PurchaseCanaryBatch
from reconciliation.services import ReconciliationError
from workflow_runtime.fact_loads import successful_fact_load_facts

from .models import PaymentOrderDraft, PaymentOrderDraftCanaryScenario
from .services import (
    CANONICAL_NAME,
    GENERATE_ACTION,
    NEXT_CANONICAL_NAME,
    NEXT_MODULE_CODE,
    NEXT_ROUTE,
    SAVE_ACTION,
    SOURCE_DOCUMENT_TYPE,
    REVIEW_ACTION,
    VERSION,
    eligibility,
    generate_payment_order_draft,
    recover_action_result,
    save_draft_data,
    serialize_draft,
    source_gate,
    review_payment_order_draft,
)


def downstream_counts():
    return {
        "nextModuleObjects": 0,
        "formalPaymentOrders": 0,
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
        "POP_AUTH_UNAUTHENTICATED": "authentication_failed",
        "POP_AUTH_PERMISSION_DENIED": "permission_denied",
        "POP_AUTH_SCOPE_DENIED": "permission_denied",
        "POP_AUTH_FEATURE_DISABLED": "feature_disabled",
        "POP_AUTH_PRODUCTION_ROLLOUT_DISABLED": "permission_denied",
        "VERSION_CONFLICT": "version_conflict",
        "POP_IDEMPOTENCY_PAYLOAD_CONFLICT": "idempotency_conflict",
        "POP_IN_PROGRESS": "in_progress",
        "POP_COMMIT_UNKNOWN": "commit_unknown",
    }.get(exc.code, "blocked")
    return Response(
        {
            "result": "blocked",
            "version": VERSION,
            "classification": classification,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
            "nextModuleObjectCreated": False,
            "formalPaymentOrderCreated": False,
            "paymentExecuted": False,
        },
        status=exc.http_status,
    )


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
        queryset = (
            PaymentOrderDraft.objects.select_related(
                "source_payment_order_prepare",
                "number_reservation",
                "business_transaction",
                "audit_record",
            )
            .prefetch_related(
                "draft_data_snapshots__creation_previews",
                "authority_snapshots",
                "review_executions__issues",
            )
            .order_by("draft_no")
        )
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return queryset.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(company_id=request.user.company_id)


class PrepareListView(ScopedMixin, APIView):
    def get(self, request):
        batch_id = request.query_params.get(
            "canaryBatchId",
            getattr(settings, "PCE_CANARY_BATCH_ID", "PURCHASE-FLOW-DEMO-V1"),
        )
        batch = PurchaseCanaryBatch.objects.filter(batch_id=batch_id).first()
        source_lineages = (
            batch.lineages.filter(current_module_code="payment-order-draft")
            .order_by("scenario_code")
            if batch
            else []
        )
        lineage_by_source_id = {row.current_object_id: row for row in source_lineages}
        objects = self.queryset(request).filter(
            source_payment_order_prepare_id__in=lineage_by_source_id
        )
        results = []
        for obj in objects:
            row = lineage_by_source_id[obj.source_payment_order_prepare_id]
            results.append(
                {
                    **serialize_draft(obj),
                    "canaryLineageId": row.canary_lineage_id,
                    "scenarioCode": row.scenario_code,
                    "scenarioClass": row.scenario_class,
                    "scenarioRole": row.scenario_role,
                    "downstreamEligible": row.downstream_eligible,
                    "reservedForNextModule": row.reserved_for_next_module,
                    "nextStageConsumed": row.next_stage_consumed,
                    "upstreamObjectNos": row.upstream_object_nos,
                }
            )
        blocked_rows = PaymentOrderDraftCanaryScenario.objects.filter(
            batch_id=batch_id
        ).order_by("scenario_code")
        blocked = [
            {
                "scenarioCode": row.scenario_code,
                "scenarioClass": row.scenario_class,
                "scenarioRole": row.scenario_code.lower(),
                "blockingRuleCode": row.blocking_rule_code,
                "blockingReason": row.blocking_reason,
                "formalObjectCount": row.formal_object_count,
                "nextStepAllowed": row.next_step_allowed,
            }
            for row in blocked_rows
        ]
        success = [
            {
                "scenarioCode": row["scenarioCode"],
                "scenarioClass": "pass_through",
                "scenarioRole": row["scenarioRole"],
                "currentObjectNo": row["draftNo"],
                "currentStatus": row["status"],
                "formalObjectCount": 1,
                "nextStepAllowed": row["eligibility"]["eligible"],
            }
            for row in results
        ]
        eligible = sum(1 for row in results if row["eligibility"]["eligible"])
        consumed = sum(1 for row in results if row["nextStageConsumed"])
        reviewed = sum(1 for row in results if row["status"] == "reviewed")
        capacity = {
            "canaryBatchId": batch_id,
            "paymentOrderPrepareSourceCount": len(results),
            "paymentOrderPrepareConsumedCount": len(results),
            "passThroughLineageCount": len(results),
            "blockedScenarioCount": len(blocked),
            "formalPaymentOrderDraftCount": len(results),
            "reviewedPaymentOrderDraftCount": reviewed,
            "downstreamEligibleSourceCount": eligible,
            "nextStageConsumedCount": 0,
            "unconsumedAvailableCount": eligible,
            "nextModuleCode": NEXT_MODULE_CODE,
            "nextCanonicalName": NEXT_CANONICAL_NAME,
            "nextRoute": NEXT_ROUTE,
            "passed": len(results) >= 8 and reviewed >= 8 and eligible >= 8,
        }
        tenant_id = getattr(
            settings,
            "PCE_CANARY_TENANT_ID",
            "tenant-canary-demo",
        )
        fact_load_facts = successful_fact_load_facts(
            result_count=len(results),
            api_url="/api/finance/payment-order-drafts/",
            tenant_id=tenant_id,
            batch_id=batch_id,
            request=request,
        )
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "canonicalName": CANONICAL_NAME,
                "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
                "currentStateSource": "server",
                "data": {
                    "count": len(results),
                    "results": results,
                    "tenantId": tenant_id,
                    "batchId": batch_id,
                    "canaryBatchId": batch_id,
                    **fact_load_facts,
                    "factLoadFacts": fact_load_facts,
                    "capacity": capacity,
                    "scenarioOverview": success + blocked,
                    "downstreamCounts": downstream_counts(),
                    "productionTenantFormalObjectCount": PaymentOrderDraft.objects.exclude(
                        tenant_id=getattr(
                            settings, "PCE_CANARY_TENANT_ID", "tenant-canary-demo"
                        )
                    ).count(),
                    "productionRolloutEnabled": False,
                },
            }
        )


class PrepareDetailView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(
                ReconciliationError("POP_NOT_FOUND", "Prepare not found", 404)
            )
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "canonicalName": CANONICAL_NAME,
                "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
                "currentStateSource": "server",
                "data": serialize_draft(obj),
                "downstreamCounts": downstream_counts(),
            }
        )


class PrepareBySourceView(ScopedMixin, APIView):
    def get(self, request, source_id):
        source = PaymentOrderPrepare.objects.filter(pk=source_id).first()
        if not source:
            return error_response(
                ReconciliationError("POP_SOURCE_NOT_FOUND", "Source not found", 404)
            )
        target = self.queryset(request).filter(
            source_payment_order_prepare=source
        ).first()
        reasons = source_gate(source, check_existing=False)
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "currentStateSource": "server",
                "data": {
                    "targetExistenceStatus": "single_target"
                    if target
                    else "no_target",
                    "targetCount": 1 if target else 0,
                    "generationAllowed": not target and not reasons,
                    "generationStatus": "existing_target"
                    if target
                    else ("eligible" if not reasons else "blocked"),
                    "blockingReasons": reasons,
                    "paymentOrderDraft": serialize_draft(target)
                    if target
                    else None,
                },
            }
        )


class GenerateView(ScopedMixin, APIView):
    def post(self, request):
        source = PaymentOrderPrepare.objects.filter(
            pk=request.data.get("sourcePaymentOrderPrepareId")
        ).first()
        if not source:
            return error_response(
                ReconciliationError("POP_SOURCE_NOT_FOUND", "Source not found", 404)
            )
        try:
            outcome = generate_payment_order_draft(
                user=request.user,
                source=source,
                idempotency_key=request.data.get("idempotencyKey", ""),
                expected_source_version=int(
                    request.data.get("expectedSourceVersion", -1)
                ),
                explicit_user_action=request.data.get("explicitUserAction") is True,
                failure_step=request.data.get("failureStep", ""),
            )
            return Response(
                {
                    "result": "passed",
                    "version": VERSION,
                    "nextModuleObjectCreated": False,
                    "formalPaymentOrderCreated": False,
                    "paymentExecuted": False,
                    **outcome,
                },
                status=201 if outcome["created"] else 200,
            )
        except ReconciliationError as exc:
            return error_response(exc)


class DraftDataView(ScopedMixin, APIView):
    def put(self, request, prepare_id):
        obj = PaymentOrderDraft.objects.filter(pk=prepare_id).first()
        if not obj:
            return error_response(
                ReconciliationError("POP_NOT_FOUND", "Prepare not found", 404)
            )
        try:
            return Response(
                {
                    "result": "passed",
                    "version": VERSION,
                    "nextModuleObjectCreated": False,
                    "formalPaymentOrderCreated": False,
                    "paymentExecuted": False,
                    **save_draft_data(
                        user=request.user,
                        obj=obj,
                        payload=request.data,
                        idempotency_key=request.data.get("idempotencyKey", ""),
                        expected_version=int(request.data.get("expectedVersion", -1)),
                        expected_draft_data_version=int(
                            request.data.get("expectedDraftDataVersion", -1)
                        ),
                        expected_payment_order_prepare_version=int(
                            request.data.get(
                                "expectedPaymentOrderPrepareVersion", -1
                            )
                        ),
                        explicit_user_action=request.data.get("explicitUserAction")
                        is True,
                        failure_step=request.data.get("failureStep", ""),
                    ),
                }
            )
        except ReconciliationError as exc:
            return error_response(exc)


class ReviewView(ScopedMixin, APIView):
    def post(self, request, prepare_id):
        obj = PaymentOrderDraft.objects.filter(pk=prepare_id).first()
        if not obj:
            return error_response(
                ReconciliationError("POP_NOT_FOUND", "Prepare not found", 404)
            )
        try:
            return Response(
                {
                    "result": "passed",
                    "version": VERSION,
                    "nextModuleObjectCreated": False,
                    "formalPaymentOrderCreated": False,
                    "paymentExecuted": False,
                    **review_payment_order_draft(
                        user=request.user,
                        obj=obj,
                        idempotency_key=request.data.get("idempotencyKey", ""),
                        expected_version=int(request.data.get("expectedVersion", -1)),
                        expected_draft_data_version=int(
                            request.data.get("expectedDraftDataVersion", -1)
                        ),
                        expected_payment_order_prepare_version=int(
                            request.data.get(
                                "expectedPaymentOrderPrepareVersion", -1
                            )
                        ),
                        explicit_user_action=request.data.get("explicitUserAction")
                        is True,
                        failure_step=request.data.get("failureStep", ""),
                    ),
                }
            )
        except ReconciliationError as exc:
            return error_response(exc)


class ReviewIssuesView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(
                ReconciliationError("POP_NOT_FOUND", "Prepare not found", 404)
            )
        serialized = serialize_draft(obj)
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "data": serialized["review"],
                "currentStateSource": "server",
            }
        )


class EligibilityView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(
                ReconciliationError("POP_NOT_FOUND", "Prepare not found", 404)
            )
        return Response(
            {
                "result": "passed",
                "version": VERSION,
                "data": eligibility(obj),
                "currentStateSource": "server",
                "nextModuleObjectCreated": False,
            }
        )


class ActionResultView(ScopedMixin, APIView):
    action_code = ""

    def get(self, request, idempotency_key):
        try:
            return Response(
                {
                    "result": "passed",
                    "version": VERSION,
                    "currentStateSource": "server",
                    **recover_action_result(self.action_code, idempotency_key),
                }
            )
        except ReconciliationError as exc:
            return error_response(exc)


class GenerationResultView(ActionResultView):
    action_code = GENERATE_ACTION


class DraftDataResultView(ActionResultView):
    action_code = SAVE_ACTION


class ReviewResultView(ActionResultView):
    action_code = REVIEW_ACTION
