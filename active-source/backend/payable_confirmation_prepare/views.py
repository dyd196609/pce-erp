from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft
from purchase_canary.models import PurchaseCanaryBatch, PurchaseCanaryLineage
from reconciliation.services import ReconciliationError
from workflow_runtime.facts import business_state_collection_facts

from .models import (
    PayableConfirmationCanaryScenario,
    PayableConfirmationPrepare,
)
from .services import (
    build_current_state,
    generate_payable_confirmation_prepare,
    recover_generation_result,
    serialize_blocked_scenario,
    serialize_prepare,
    validate_accounting_data,
)


def error_response(exc):
    classification = {
        "PCP_AUTH_UNAUTHENTICATED": "authentication_failed",
        "PCP_AUTH_PERMISSION_DENIED": "permission_denied",
        "PCP_AUTH_SCOPE_DENIED": "permission_denied",
        "PCP_AUTH_FEATURE_DISABLED": "feature_disabled",
        "PCP_AUTH_PRODUCTION_ROLLOUT_DISABLED": "permission_denied",
        "PCP_SOURCE_VERSION_CONFLICT": "version_conflict",
        "PCP_IDEMPOTENCY_PAYLOAD_CONFLICT": "idempotency_conflict",
        "PCP_IN_PROGRESS": "in_progress",
        "PCP_COMMIT_UNKNOWN": "commit_unknown",
        "PCP_RECOVERY_REQUIRED": "recovery_required",
        "PCP_VALIDATION_FAILED": "validation_failed",
    }.get(exc.code, "blocked")
    return Response({
        "result": "blocked",
        "classification": classification,
        "error": {
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
        },
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
        queryset = PayableConfirmationPrepare.objects.select_related(
            "source_purchase_accounts_payable_draft",
            "source_purchase_accounts_payable_draft__source_purchase_reconciliation",
            "number_reservation",
            "business_transaction",
            "audit_record",
            "accounting_snapshot",
        ).order_by("prepare_no")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return queryset.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(company_id=request.user.company_id)


def serialize_source(source):
    return {
        "id": source.pk,
        "draftNo": source.draft_no,
        "status": source.status,
        "version": source.version,
        "sourceDocumentType": "purchaseAccountsPayableDraft",
        "tenantId": source.tenant_id,
        "supplierId": source.supplier_id,
        "supplierName": source.supplier_name,
        "legalEntityId": source.legal_entity_id,
        "ledgerBookId": source.ledger_book_id,
        "currency": source.currency,
        "amountExcludingTax": str(source.amount_excluding_tax),
        "taxAmount": str(source.tax_amount),
        "payableAmount": str(source.payable_amount),
        "invoiceDate": source.invoice_date.isoformat(),
        "sourcePurchaseInvoicePrepareNo": (
            source.source_purchase_invoice_prepare_no
        ),
        "sourcePurchaseReconciliationNo": (
            source.source_purchase_reconciliation_no
        ),
    }


def downstream_counts():
    return {
        "paymentRequestPrepares": 0,
        "paymentApplications": 0,
        "payments": 0,
        "paymentVouchers": 0,
        "writeoffs": 0,
        "ledgerEntries": 0,
        "postings": 0,
        "bankTransactions": 0,
    }


class PrepareListView(ScopedMixin, APIView):
    def get(self, request):
        scenario_code = request.query_params.get("scenarioCode", "")
        scenario_class = request.query_params.get("scenarioClass", "all")
        queryset = self.queryset(request)
        batch_id = request.query_params.get(
            "canaryBatchId",
            getattr(settings, "PCE_CANARY_BATCH_ID", "PURCHASE-FLOW-DEMO-V1"),
        )
        batch = PurchaseCanaryBatch.objects.filter(batch_id=batch_id).first()
        lineage_queryset = PurchaseCanaryLineage.objects.none()
        if batch:
            lineage_queryset = batch.lineages.filter(
                current_module_code="payable-confirmation-prepare"
            ).order_by("scenario_code")
        if scenario_code:
            lineage_queryset = lineage_queryset.filter(
                scenario_code=scenario_code
            )
        lineage_rows = list(lineage_queryset)
        lineage_by_object_id = {
            row.current_object_id: row for row in lineage_rows
        }
        objects = list(queryset.filter(pk__in=lineage_by_object_id))
        success_rows = []
        for obj in objects:
            lineage = lineage_by_object_id[obj.pk]
            success_rows.append({
                **serialize_prepare(obj),
                "canaryLineageId": lineage.canary_lineage_id,
                "scenarioCode": lineage.scenario_code,
                "scenarioClass": lineage.scenario_class,
                "scenarioRole": lineage.scenario_role,
                "downstreamEligible": lineage.downstream_eligible,
                "reservedForNextModule": lineage.reserved_for_next_module,
                "nextStageConsumed": lineage.next_stage_consumed,
                "sourceRelationHash": lineage.source_relation_hash,
                "upstreamObjectNos": lineage.upstream_object_nos,
            })
        blocked_queryset = PayableConfirmationCanaryScenario.objects.filter(
            batch_id=batch_id
        ).order_by("scenario_code")
        if scenario_code:
            blocked_queryset = blocked_queryset.filter(
                scenario_code=scenario_code
            )
        blocked_rows = [
            serialize_blocked_scenario(row) for row in blocked_queryset
        ]
        scenario_overview = [
            {
                "canaryLineageId": row["canaryLineageId"],
                "scenarioCode": row["scenarioCode"],
                "scenarioClass": "pass_through",
                "scenarioRole": row["scenarioRole"],
                "currentModuleCode": "payable-confirmation-prepare",
                "currentObjectNo": row["prepareNo"],
                "currentStatus": row["status"],
                "formalPayableConfirmationPrepareCreated": True,
                "formalObjectCount": 1,
                "downstreamEligible": row["downstreamEligible"],
                "nextStepAllowed": row["eligibility"]["eligible"],
                "blockingModule": "",
                "blockingRuleCode": "",
                "blockingReason": "",
            }
            for row in success_rows
        ] + blocked_rows
        if scenario_class == "success":
            scenario_overview = [
                row for row in scenario_overview
                if row["scenarioClass"] == "pass_through"
            ]
        elif scenario_class == "blocked":
            scenario_overview = [
                row for row in scenario_overview
                if row["scenarioClass"] == "blocked"
            ]
            success_rows = []
        all_success_count = (
            batch.lineages.filter(
                current_module_code="payable-confirmation-prepare"
            ).count()
            if batch else 0
        )
        all_formal_count = queryset.count()
        eligible_count = sum(
            1 for row in self.queryset(request)
            if serialize_prepare(row)["eligibility"]["eligible"]
        )
        consumed_count = (
            batch.lineages.filter(
                current_module_code="payable-confirmation-prepare",
                next_stage_consumed=True,
            ).count()
            if batch else 0
        )
        return Response({
            "result": "passed",
            "version": "V1.14.2.8.4.7.46",
            "canonicalName": "应付确认准备",
            "sourceDocumentType": "purchaseAccountsPayableDraft",
            "currentStateSource": "server",
            "data": {
                "count": len(success_rows),
                "results": success_rows,
                "strictFacts": business_state_collection_facts(success_rows),
                "capacity": {
                    "canaryBatchId": batch_id,
                    "passThroughLineageCount": all_success_count,
                    "blockedScenarioCount": (
                        PayableConfirmationCanaryScenario.objects.filter(
                            batch_id=batch_id
                        ).count()
                    ),
                    "formalPayableConfirmationPrepareCount": all_formal_count,
                    "downstreamEligibleSourceCount": eligible_count,
                    "nextStageConsumedCount": consumed_count,
                    "unconsumedAvailableCount": eligible_count - consumed_count,
                    "nextModuleCode": "payment_request_prepare",
                    "passed": (
                        all_success_count >= 8
                        and all_formal_count >= 8
                        and eligible_count >= 8
                        and consumed_count == 0
                    ),
                },
                "scenarioOverview": scenario_overview,
                "downstreamCounts": downstream_counts(),
                "paymentRequestPrepareCreated": False,
                "productionTenantFormalObjectCount": 0,
            },
        })


class PrepareDetailView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(
                ReconciliationError("PCP_NOT_FOUND", "Prepare not found", 404)
            )
        return Response({
            "result": "passed",
            "version": "V1.14.2.8.4.7.46",
            "canonicalName": "应付确认准备",
            "sourceDocumentType": "purchaseAccountsPayableDraft",
            "currentStateSource": "server",
            "data": serialize_prepare(obj),
            "downstreamCounts": downstream_counts(),
        })


class PrepareBySourceView(ScopedMixin, APIView):
    def get(self, request, draft_id):
        source = PurchaseAccountsPayableDraft.objects.filter(pk=draft_id).first()
        if not source:
            return error_response(
                ReconciliationError("PCP_SOURCE_NOT_FOUND", "Source draft not found", 404)
            )
        return Response({
            "result": "passed",
            "version": "V1.14.2.8.4.7.46",
            "canonicalName": "应付确认准备",
            "sourceDocumentType": "purchaseAccountsPayableDraft",
            "currentStateSource": "server",
            "data": {
                "source": serialize_source(source),
                "currentState": build_current_state(source),
                "paymentRequestPrepareCreated": False,
            },
        })


class ValidateView(ScopedMixin, APIView):
    def post(self, request):
        source = PurchaseAccountsPayableDraft.objects.filter(
            pk=request.data.get("sourcePurchaseAccountsPayableDraftId")
        ).first()
        if not source:
            return error_response(
                ReconciliationError("PCP_SOURCE_NOT_FOUND", "Source draft not found", 404)
            )
        try:
            _, validation = validate_accounting_data(
                source, request.data.get("accountingData")
            )
            return Response({
                "result": "passed" if validation["passed"] else "blocked",
                "version": "V1.14.2.8.4.7.46",
                "canonicalName": "应付确认准备",
                "sourceDocumentType": "purchaseAccountsPayableDraft",
                "data": validation,
                "writePerformed": False,
                "paymentRequestPrepareCreated": False,
            }, status=200 if validation["passed"] else 409)
        except ReconciliationError as exc:
            return error_response(exc)


class GenerateView(ScopedMixin, APIView):
    def post(self, request):
        source = PurchaseAccountsPayableDraft.objects.filter(
            pk=request.data.get("sourcePurchaseAccountsPayableDraftId")
        ).first()
        if not source:
            return error_response(
                ReconciliationError("PCP_SOURCE_NOT_FOUND", "Source draft not found", 404)
            )
        try:
            outcome = generate_payable_confirmation_prepare(
                user=request.user,
                source=source,
                accounting_data=request.data.get("accountingData"),
                idempotency_key=str(request.data.get("idempotencyKey") or ""),
                expected_source_version=int(
                    request.data.get("expectedSourceVersion", source.version)
                ),
                failure_step=str(request.data.get("failureStep") or ""),
            )
            return Response({
                "result": "passed",
                "version": "V1.14.2.8.4.7.46",
                "canonicalName": "应付确认准备",
                "sourceDocumentType": "purchaseAccountsPayableDraft",
                **outcome,
                "paymentRequestPrepareCreated": False,
            }, status=201 if outcome["created"] else 200)
        except ReconciliationError as exc:
            return error_response(exc)


class GenerationResultView(ScopedMixin, APIView):
    def get(self, request, idempotency_key):
        try:
            return Response({
                "result": "passed",
                "version": "V1.14.2.8.4.7.46",
                "canonicalName": "应付确认准备",
                "sourceDocumentType": "purchaseAccountsPayableDraft",
                **recover_generation_result(idempotency_key),
                "paymentRequestPrepareCreated": False,
            })
        except ReconciliationError as exc:
            return error_response(exc)
