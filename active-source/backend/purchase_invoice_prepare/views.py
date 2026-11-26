from rest_framework.response import Response
from rest_framework.views import APIView

from reconciliation.checking import authorize_read
from reconciliation.models import PurchaseReconciliation
from reconciliation.services import ReconciliationError
from workflow_runtime.facts import business_state_collection_facts

from .models import PurchaseInvoicePrepare
from .services import (
    build_current_generation_state,
    generate_purchase_invoice_prepare,
    recover_generation_result,
    serialize_prepare,
)
from .v44_services import (
    build_ap_draft_eligibility,
    build_validation_read_model,
    recover_validation_result,
    save_invoice_data,
    validate_invoice_data,
)


def error_response(exc):
    return Response(
        {
            "result": "blocked",
            "classification": {
                "PIP_SOURCE_VERSION_CONFLICT": "version_conflict",
                "PIP_CHECK_VERSION_CONFLICT": "version_conflict",
                "PIP_EXISTING_TARGET": "existing_target",
                "PIP_AUTH_PERMISSION_DENIED": "permission_denied",
                "PIP_AUTH_FEATURE_DISABLED": "feature_disabled",
            }.get(exc.code, "blocked"),
            "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
        },
        status=exc.http_status,
    )


class ScopedMixin:
    def queryset(self, request):
        queryset = PurchaseInvoicePrepare.objects.all().order_by("-created_at")
        if not request.user.is_superuser:
            queryset = queryset.filter(company_id=request.user.company_id)
        return queryset


class PrepareListView(ScopedMixin, APIView):
    def get(self, request):
        data = [serialize_prepare(obj) for obj in self.queryset(request)]
        return Response({
            "result": "passed",
            "currentStateSource": "server",
            "data": {
                "count": len(data),
                "results": data,
                "strictFacts": business_state_collection_facts(data),
            },
        })


class PrepareDetailView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            return error_response(ReconciliationError("PIP_NOT_FOUND", "Invoice prepare not found", 404))
        return Response({
            "result": "passed",
            "data": {
                **serialize_prepare(obj),
                "currentState": build_current_generation_state(
                    obj.source_purchase_reconciliation,
                    [obj],
                ),
                "validationReadModel": build_validation_read_model(obj),
            },
        })


class PrepareBySourceView(ScopedMixin, APIView):
    def get(self, request, reconciliation_id):
        try:
            reconciliation = PurchaseReconciliation.objects.get(pk=reconciliation_id)
            authorize_read(request.user, reconciliation)
            items = list(
                self.queryset(request).filter(source_purchase_reconciliation_id=reconciliation_id)
            )
            current_state = build_current_generation_state(reconciliation, items)
            return Response({
                "result": "passed",
                "data": {
                    "count": len(items),
                    "results": [serialize_prepare(obj) for obj in items],
                    **current_state,
                },
            })
        except PurchaseReconciliation.DoesNotExist:
            return error_response(ReconciliationError("PIP_SOURCE_NOT_FOUND", "Purchase reconciliation not found", 404))
        except ReconciliationError as exc:
            return error_response(exc)


class GenerateView(APIView):
    def post(self, request):
        data = request.data
        forbidden = {
            "prepareNo", "status", "supplier", "supplierId", "amount", "settlementAmount",
            "currency", "eligibility", "sourceStatus", "existingTargetCount",
            "nextStepReadiness", "eligible",
        }
        if forbidden.intersection(data.keys()):
            return error_response(ReconciliationError("PIP_CLIENT_DERIVED_FIELD_FORBIDDEN", "Derived fields are server controlled", 400))
        try:
            result = generate_purchase_invoice_prepare(
                user=request.user,
                reconciliation_id=data.get("sourcePurchaseReconciliationId"),
                idempotency_key=data.get("idempotencyKey", ""),
                expected_reconciliation_version=data.get("expectedReconciliationVersion"),
                expected_check_version=data.get("expectedCheckVersion"),
                explicit_user_action=data.get("explicitUserAction") is True,
                failure_step=request.headers.get("X-PCE-Failure-Step", ""),
            )
            return Response({"result": "passed", **result}, status=201 if result["created"] else 200)
        except ReconciliationError as exc:
            return error_response(exc)


class GenerationResultView(APIView):
    def get(self, request, idempotency_key):
        try:
            return Response({
                "result": "passed",
                **recover_generation_result(idempotency_key, user=request.user),
            })
        except ReconciliationError as exc:
            return error_response(exc)


class PrepareV44Mixin(ScopedMixin):
    def get_prepare(self, request, prepare_id):
        obj = self.queryset(request).filter(pk=prepare_id).first()
        if not obj:
            raise ReconciliationError("PIP_NOT_FOUND", "Invoice prepare not found", 404)
        return obj


class InvoiceDataView(PrepareV44Mixin, APIView):
    forbidden = {
        "status", "invoiceDataStatus", "validationStatus", "validationResultCode",
        "prepared", "nextStepReadiness", "eligible", "issueCount",
        "invoiceIdentityKey", "dataHash",
    }

    def get(self, request, prepare_id):
        try:
            obj = self.get_prepare(request, prepare_id)
            return Response({"result": "passed", "data": build_validation_read_model(obj)})
        except ReconciliationError as exc:
            return error_response(exc)

    def put(self, request, prepare_id):
        data = request.data
        invoice_data = data.get("invoiceData") or {}
        if self.forbidden.intersection(data.keys()) or self.forbidden.intersection(invoice_data.keys()):
            return error_response(ReconciliationError(
                "PIP_DATA_SERVER_DERIVED_FIELD_FORBIDDEN", "Derived fields are server controlled", 400
            ))
        try:
            result = save_invoice_data(
                user=request.user, prepare_id=prepare_id,
                idempotency_key=data.get("idempotencyKey", ""),
                expected_version=data.get("expectedVersion"),
                expected_data_version=data.get("expectedDataVersion"),
                explicit_user_action=data.get("explicitUserAction") is True,
                invoice_data=invoice_data,
                failure_step=request.headers.get("X-PCE-Failure-Step", ""),
            )
            return Response({"result": "passed", **result})
        except (PurchaseInvoicePrepare.DoesNotExist, ReconciliationError) as exc:
            if isinstance(exc, PurchaseInvoicePrepare.DoesNotExist):
                exc = ReconciliationError("PIP_NOT_FOUND", "Invoice prepare not found", 404)
            return error_response(exc)


class ValidateInvoiceDataView(PrepareV44Mixin, APIView):
    forbidden = {
        "validationResult", "issues", "prepared", "eligible",
        "nextStepReadiness", "duplicateStatus",
    }

    def post(self, request, prepare_id):
        data = request.data
        if self.forbidden.intersection(data.keys()):
            return error_response(ReconciliationError(
                "PIP_VALIDATION_SERVER_DERIVED_FIELD_FORBIDDEN", "Derived fields are server controlled", 400
            ))
        try:
            result = validate_invoice_data(
                user=request.user, prepare_id=prepare_id,
                idempotency_key=data.get("idempotencyKey", ""),
                expected_version=data.get("expectedVersion"),
                expected_data_version=data.get("expectedDataVersion"),
                expected_reconciliation_version=data.get("expectedReconciliationVersion"),
                expected_check_version=data.get("expectedCheckVersion"),
                explicit_user_action=data.get("explicitUserAction") is True,
                failure_step=request.headers.get("X-PCE-Failure-Step", ""),
            )
            return Response({"result": "passed", **result})
        except (PurchaseInvoicePrepare.DoesNotExist, ReconciliationError) as exc:
            if isinstance(exc, PurchaseInvoicePrepare.DoesNotExist):
                exc = ReconciliationError("PIP_NOT_FOUND", "Invoice prepare not found", 404)
            return error_response(exc)


class ValidationIssuesView(PrepareV44Mixin, APIView):
    def get(self, request, prepare_id):
        try:
            model = build_validation_read_model(self.get_prepare(request, prepare_id))
            return Response({"result": "passed", "data": {
                "validation": model["validation"],
                "issues": model["validationIssues"],
                "currentStateSource": "server",
            }})
        except ReconciliationError as exc:
            return error_response(exc)


class AccountsPayableDraftEligibilityView(PrepareV44Mixin, APIView):
    def get(self, request, prepare_id):
        try:
            return Response({
                "result": "passed",
                "data": build_ap_draft_eligibility(self.get_prepare(request, prepare_id)),
            })
        except ReconciliationError as exc:
            return error_response(exc)


class ValidationResultView(APIView):
    def get(self, request, idempotency_key):
        try:
            return Response({
                "result": "passed",
                **recover_validation_result(idempotency_key, request.user),
            })
        except ReconciliationError as exc:
            return error_response(exc)
