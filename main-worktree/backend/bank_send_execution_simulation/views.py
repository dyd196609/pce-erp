from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bank_send_request.models import BankSendRequest
from reconciliation.services import ReconciliationError

from .models import (
    BankSendChainTrace,
    BankSendExecutionRecovery,
    BankSendExecutionSimulation,
    BankSendFinalApproval,
    BankSendProductionIsolationGate,
    BankSendDualIsolationCheck,
    BankSendExecutionFramework,
    BankSendProductionReleaseReview,
    BankSendSimulationAudit,
)
from .isolation import (
    AUDIT_MODULE_CODE,
    ISOLATION_MODULE_CODE,
    isolation_gate_facts,
    serialize_audit,
    serialize_isolation_gate,
    simulation_audit_facts,
)
from .services import (
    CANONICAL_NAME, MODULE_CODE, VERSION, create_execution_simulation,
    protection_counts, resolve_execution_recovery, serialize_simulation,
    simulation_facts,
)
from .v66 import (
    APPROVAL_MODULE_CODE,
    TRACE_MODULE_CODE,
    VERSION as V66_VERSION,
    chain_trace_facts,
    final_approval_facts,
    serialize_approval,
    serialize_trace,
    submit_first_approval,
    submit_second_approval,
)
from .v67 import (
    DUAL_ISOLATION_MODULE_CODE,
    RELEASE_REVIEW_MODULE_CODE,
    VERSION as V67_VERSION,
    dual_isolation_facts,
    release_review_facts,
    serialize_isolation_check as serialize_dual_isolation_check,
    serialize_release_review,
    submit_release_decision,
)
from .v68 import (
    ADAPTER_MODULE_CODE,
    FRAMEWORK_MODULE_CODE,
    VERSION as V68_VERSION,
    adapter_facts,
    framework_facts,
    serialize_adapter_review,
    serialize_framework,
)


def _error(exc):
    return Response({
        "result": "blocked", "version": VERSION,
        "error": {"code": exc.code, "message": exc.message},
        **protection_counts(),
    }, status=exc.http_status)


class ScopedMixin:
    def get_permissions(self):
        permission = AllowAny if (
            getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            and self.request.method == "GET"
        ) else IsAuthenticated
        return [permission()]

    def simulations(self, request):
        qs = BankSendExecutionSimulation.objects.select_related(
            "source_request", "recovery", "recovery__resolved_by"
        ).order_by("id")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            return qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        if request.user.is_superuser:
            return qs
        return qs.filter(source_request__company_id=request.user.company_id)


class SimulationListView(ScopedMixin, APIView):
    def get(self, request):
        rows = [serialize_simulation(row) for row in self.simulations(request)]
        tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        batch = getattr(settings, "PCE_CANARY_BATCH_ID", "")
        facts = simulation_facts(
            rows, api_url="/api/finance/bank-send-simulations/",
            tenant_id=tenant, batch_id=batch,
        )
        fact_load_facts = {
            key: facts[key]
            for key in (
                "factLoadContractVersion", "factLoadStatus", "apiUrl",
                "httpStatus", "errorCode", "errorMessage", "loadedAt",
                "tenantId", "batchId",
            )
        }
        return Response({
            "result": "passed", "version": VERSION,
            "canonicalName": CANONICAL_NAME, "moduleCode": MODULE_CODE,
            "data": {
                **facts, "factLoadFacts": fact_load_facts,
                "count": facts["simulationCount"], "results": rows,
                "simulationFacts": facts, "strictFacts": facts,
                "acceptanceFacts": {
                    "contractVersion": "PCE-ACCEPTANCE-OBSERVABILITY-CONTRACT-V1.0",
                    "pageCode": MODULE_CODE, "factSource": "server",
                    "recordCount": facts["simulationCount"],
                    "selectedCount": 0, "actionCount": 3,
                    "dangerActionCount": 0, "businessProgressWriteCount": 0,
                    "downstreamObjectCount": 0,
                    "factLoadStatus": "success",
                },
                **protection_counts(),
            },
        })


class SimulationCreateView(ScopedMixin, APIView):
    def post(self, request, request_id):
        source = BankSendRequest.objects.filter(pk=request_id).first()
        if not source:
            return _error(ReconciliationError("BSES_SOURCE_NOT_FOUND", "Request not found", 404))
        try:
            result = create_execution_simulation(
                user=request.user, request_object=source,
                idempotency_key=request.data.get("idempotencyKey"),
                execution_version=int(request.data.get("executionVersion", 1)),
                simulate_failure=request.data.get("simulateFailure") is True,
            )
            return Response({"result": "passed", "version": VERSION, **result}, status=201 if result["created"] else 200)
        except ReconciliationError as exc:
            return _error(exc)


class RecoveryResolveView(ScopedMixin, APIView):
    def post(self, request, recovery_id):
        recovery = BankSendExecutionRecovery.objects.filter(pk=recovery_id).first()
        if not recovery:
            return _error(ReconciliationError("BSER_NOT_FOUND", "Recovery not found", 404))
        return Response({
            "result": "passed", "version": VERSION,
            "data": resolve_execution_recovery(
                user=request.user, recovery=recovery,
                resolution_note=request.data.get("resolutionNote"),
            ),
        })


def _acceptance_facts(module_code, record_count, action_count):
    return {
        "contractVersion": "PCE-ACCEPTANCE-OBSERVABILITY-CONTRACT-V1.0",
        "pageAcceptanceContractVersion": "PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0",
        "pageCode": module_code,
        "factSource": "server",
        "recordCount": record_count,
        "selectedCount": 0,
        "actionCount": action_count,
        "dangerActionCount": 0,
        "businessProgressWriteCount": 0,
        "downstreamObjectCount": 0,
        "factLoadStatus": "success",
        "acceptanceStatus": "PASS",
        "unknownReason": "",
    }


class SimulationAuditListView(ScopedMixin, APIView):
    def get(self, request):
        qs = BankSendSimulationAudit.objects.select_related(
            "simulation", "operator"
        ).order_by("occurred_at", "pk")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(
                simulation__source_request__company_id=request.user.company_id
            )
        rows = [serialize_audit(row) for row in qs]
        tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        batch = getattr(settings, "PCE_CANARY_BATCH_ID", "")
        facts = simulation_audit_facts(
            rows,
            api_url="/api/finance/bank-send-simulation-audits/",
            tenant_id=tenant,
            batch_id=batch,
        )
        acceptance = _acceptance_facts(
            AUDIT_MODULE_CODE, facts["recordCount"], 1
        )
        return Response({
            "result": "passed",
            "version": "V1.14.2.8.4.7.65",
            "canonicalName": "银行发送模拟审计",
            "moduleCode": AUDIT_MODULE_CODE,
            "data": {
                **facts,
                "count": facts["recordCount"],
                "results": rows,
                "auditFacts": facts,
                "diagnosticFacts": facts,
                "strictFacts": facts,
                "acceptanceFacts": acceptance,
            },
        })


class ProductionIsolationGateListView(ScopedMixin, APIView):
    def get(self, request):
        qs = BankSendProductionIsolationGate.objects.select_related(
            "created_by"
        ).order_by("pk")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(created_by__company_id=request.user.company_id)
        rows = [serialize_isolation_gate(row) for row in qs]
        tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        batch = getattr(settings, "PCE_CANARY_BATCH_ID", "")
        facts = isolation_gate_facts(
            rows,
            api_url="/api/finance/bank-send-isolation-gates/",
            tenant_id=tenant,
            batch_id=batch,
        )
        acceptance = _acceptance_facts(
            ISOLATION_MODULE_CODE, facts["recordCount"], 1
        )
        return Response({
            "result": "passed",
            "version": "V1.14.2.8.4.7.65",
            "canonicalName": "银行发送生产隔离门禁",
            "moduleCode": ISOLATION_MODULE_CODE,
            "data": {
                **facts,
                "count": facts["recordCount"],
                "results": rows,
                "isolationFacts": facts,
                "diagnosticFacts": facts,
                "strictFacts": facts,
                "acceptanceFacts": acceptance,
            },
        })


class ChainTraceListView(ScopedMixin, APIView):
    def get(self, request):
        qs = BankSendChainTrace.objects.select_related(
            "source_simulation",
            "source_simulation__source_request",
            "isolation_gate",
        ).order_by("pk")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(
                source_simulation__source_request__company_id=request.user.company_id
            )
        rows = [serialize_trace(row) for row in qs]
        tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        batch = getattr(settings, "PCE_CANARY_BATCH_ID", "")
        facts = chain_trace_facts(
            rows, tenant_id=tenant, batch_id=batch
        )
        acceptance = _acceptance_facts(
            TRACE_MODULE_CODE, facts["recordCount"], 1
        )
        return Response({
            "result": "passed",
            "version": V66_VERSION,
            "canonicalName": "银行发送全链路追踪",
            "moduleCode": TRACE_MODULE_CODE,
            "data": {
                **facts,
                "count": facts["recordCount"],
                "results": rows,
                "traceFacts": facts,
                "diagnosticFacts": facts,
                "strictFacts": facts,
                "acceptanceFacts": acceptance,
            },
        })


class FinalApprovalListView(ScopedMixin, APIView):
    def get(self, request):
        qs = BankSendFinalApproval.objects.select_related(
            "trace",
            "trace__source_simulation",
            "trace__source_simulation__source_request",
        ).prefetch_related("decisions__operator").order_by("pk")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(
                trace__source_simulation__source_request__company_id=request.user.company_id
            )
        rows = [serialize_approval(row) for row in qs]
        tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        batch = getattr(settings, "PCE_CANARY_BATCH_ID", "")
        facts = final_approval_facts(
            rows, tenant_id=tenant, batch_id=batch
        )
        acceptance = _acceptance_facts(
            APPROVAL_MODULE_CODE, facts["recordCount"], 3
        )
        return Response({
            "result": "passed",
            "version": V66_VERSION,
            "canonicalName": "银行发送最终审批",
            "moduleCode": APPROVAL_MODULE_CODE,
            "data": {
                **facts,
                "count": facts["recordCount"],
                "results": rows,
                "approvalFacts": facts,
                "diagnosticFacts": facts,
                "strictFacts": facts,
                "acceptanceFacts": acceptance,
            },
        })


class FinalApprovalFirstSubmitView(ScopedMixin, APIView):
    def post(self, request, approval_id):
        approval = BankSendFinalApproval.objects.filter(pk=approval_id).first()
        if not approval:
            return Response(
                {"result": "blocked", "error": {"code": "BSFA_NOT_FOUND"}},
                status=404,
            )
        try:
            row = submit_first_approval(
                approval=approval,
                user=request.user,
                reason=request.data.get("reason") or "business_review_passed",
            )
        except PermissionError as exc:
            return Response(
                {"result": "blocked", "error": {"code": "BSFA_ROLE_DENIED", "message": str(exc)}},
                status=403,
            )
        except ValueError as exc:
            return Response(
                {"result": "blocked", "error": {"code": "BSFA_CHECK_BLOCKED", "message": str(exc)}},
                status=409,
            )
        return Response({"result": "passed", "version": V66_VERSION, "data": serialize_approval(row)})


class FinalApprovalSecondSubmitView(ScopedMixin, APIView):
    def post(self, request, approval_id):
        approval = BankSendFinalApproval.objects.filter(pk=approval_id).first()
        if not approval:
            return Response(
                {"result": "blocked", "error": {"code": "BSFA_NOT_FOUND"}},
                status=404,
            )
        try:
            row = submit_second_approval(
                approval=approval,
                user=request.user,
                reason=request.data.get("reason") or "fund_owner_review_passed",
            )
        except PermissionError as exc:
            return Response(
                {"result": "blocked", "error": {"code": "BSFA_SOD_DENIED", "message": str(exc)}},
                status=403,
            )
        except ValueError as exc:
            return Response(
                {"result": "blocked", "error": {"code": "BSFA_CHECK_BLOCKED", "message": str(exc)}},
                status=409,
            )
        return Response({"result": "passed", "version": V66_VERSION, "data": serialize_approval(row)})


class DualIsolationCheckListView(ScopedMixin, APIView):
    def get(self, request):
        qs = BankSendDualIsolationCheck.objects.select_related(
            "trace", "approval", "checked_by"
        ).order_by("pk")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(
                trace__source_simulation__source_request__company_id=request.user.company_id
            )
        rows = [serialize_dual_isolation_check(row) for row in qs]
        tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        batch = getattr(settings, "PCE_CANARY_BATCH_ID", "")
        facts = dual_isolation_facts(
            rows, tenant_id=tenant, batch_id=batch
        )
        acceptance = _acceptance_facts(
            DUAL_ISOLATION_MODULE_CODE, facts["recordCount"], 1
        )
        return Response({
            "result": "passed",
            "version": V67_VERSION,
            "canonicalName": "银行发送双重隔离检查",
            "moduleCode": DUAL_ISOLATION_MODULE_CODE,
            "data": {
                **facts,
                "count": facts["recordCount"],
                "results": rows,
                "isolationFacts": facts,
                "diagnosticFacts": facts,
                "strictFacts": facts,
                "acceptanceFacts": acceptance,
            },
        })


class ProductionReleaseReviewListView(ScopedMixin, APIView):
    def get(self, request):
        qs = BankSendProductionReleaseReview.objects.select_related(
            "trace",
            "approval",
            "isolation_check",
            "trace__source_simulation__source_request",
        ).prefetch_related("decisions__operator").order_by("pk")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(
                trace__source_simulation__source_request__company_id=request.user.company_id
            )
        rows = [serialize_release_review(row) for row in qs]
        tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        batch = getattr(settings, "PCE_CANARY_BATCH_ID", "")
        facts = release_review_facts(
            rows, tenant_id=tenant, batch_id=batch
        )
        acceptance = _acceptance_facts(
            RELEASE_REVIEW_MODULE_CODE, facts["recordCount"], 4
        )
        return Response({
            "result": "passed",
            "version": V67_VERSION,
            "canonicalName": "真实银行发送前生产隔离评审",
            "moduleCode": RELEASE_REVIEW_MODULE_CODE,
            "data": {
                **facts,
                "count": facts["recordCount"],
                "results": rows,
                "reviewFacts": facts,
                "diagnosticFacts": facts,
                "strictFacts": facts,
                "acceptanceFacts": acceptance,
            },
        })


class ProductionReleaseDecisionSubmitView(ScopedMixin, APIView):
    def post(self, request, review_id, stage):
        review = BankSendProductionReleaseReview.objects.filter(
            pk=review_id
        ).first()
        if not review:
            return Response(
                {"result": "blocked", "error": {"code": "BSPRR_NOT_FOUND"}},
                status=404,
            )
        try:
            row = submit_release_decision(
                review=review,
                user=request.user,
                stage=stage,
                reason=request.data.get("reason") or f"{stage}_review_confirmed",
            )
        except PermissionError as exc:
            return Response(
                {
                    "result": "blocked",
                    "error": {
                        "code": "BSPRR_ROLE_DENIED",
                        "message": str(exc),
                    },
                },
                status=403,
            )
        except ValueError as exc:
            return Response(
                {
                    "result": "blocked",
                    "error": {
                        "code": "BSPRR_CHECK_BLOCKED",
                        "message": str(exc),
                    },
                },
                status=409,
            )
        return Response({
            "result": "passed",
            "version": V67_VERSION,
            "data": serialize_release_review(row),
        })


class ExecutionFrameworkReviewListView(ScopedMixin, APIView):
    def get(self, request):
        qs = BankSendExecutionFramework.objects.select_related(
            "source_review",
            "source_review__trace__source_simulation__source_request",
            "safety_review__reviewed_by",
        ).order_by("pk")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(
                source_review__trace__source_simulation__source_request__company_id=request.user.company_id
            )
        rows = [serialize_framework(row) for row in qs]
        tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        batch = getattr(settings, "PCE_CANARY_BATCH_ID", "")
        facts = framework_facts(rows, tenant_id=tenant, batch_id=batch)
        acceptance = _acceptance_facts(
            FRAMEWORK_MODULE_CODE, facts["recordCount"], 4
        )
        return Response({
            "result": "passed",
            "version": V68_VERSION,
            "canonicalName": "银行发送执行框架评审",
            "moduleCode": FRAMEWORK_MODULE_CODE,
            "data": {
                **facts,
                "count": facts["recordCount"],
                "results": rows,
                "frameworkFacts": facts,
                "diagnosticFacts": facts,
                "strictFacts": facts,
                "acceptanceFacts": acceptance,
            },
        })


class ConnectorAdapterReviewListView(ScopedMixin, APIView):
    def get(self, request):
        qs = BankSendExecutionFramework.objects.select_related(
            "source_review__trace__source_simulation__source_request",
        ).prefetch_related(
            "source_review__trace__source_simulation__source_request__execution_idempotencies",
            "source_review__trace__source_simulation__source_request__execution_framework_failures",
        ).order_by("pk")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            qs = qs.filter(tenant_id=settings.PCE_CANARY_TENANT_ID)
        elif not request.user.is_superuser:
            qs = qs.filter(
                source_review__trace__source_simulation__source_request__company_id=request.user.company_id
            )
        rows = [serialize_adapter_review(row) for row in qs]
        tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        batch = getattr(settings, "PCE_CANARY_BATCH_ID", "")
        facts = adapter_facts(rows, tenant_id=tenant, batch_id=batch)
        acceptance = _acceptance_facts(
            ADAPTER_MODULE_CODE, facts["recordCount"], 4
        )
        return Response({
            "result": "passed",
            "version": V68_VERSION,
            "canonicalName": "银行接口适配评审",
            "moduleCode": ADAPTER_MODULE_CODE,
            "data": {
                **facts,
                "count": facts["recordCount"],
                "results": rows,
                "adapterFacts": facts,
                "diagnosticFacts": facts,
                "strictFacts": facts,
                "acceptanceFacts": acceptance,
            },
        })
