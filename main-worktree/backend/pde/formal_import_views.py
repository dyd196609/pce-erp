from urllib.parse import quote
import json

from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from system.authorization import AuthorizationService

from .formal_import_actor_context import (
    FormalImportActorContextError, preview_actor_binding, resolve_formal_import_actor,
)
from .formal_import_request_trace import append_rehearsal_trace, build_actor_request_trace
from .formal_import_service import FormalImportError, FormalImportService
from .production_foundation_service import ENTITY_CONFIG, ProductionFoundationError


def _error_response(exc):
    denied = (
        exc.code in {"PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID", "FORMAL_EXECUTION_CHAIN_REQUIRED", "PREVIEW_ACTOR_CONTEXT_CHANGED"}
        or str(exc.code).startswith("FORMAL_IMPORT_ACTOR_")
    )
    return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=status.HTTP_403_FORBIDDEN if denied else status.HTTP_400_BAD_REQUEST)


class FormalImportBaseView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @staticmethod
    def authorize_read(request):
        organization_id = request.user.company_id
        decision = AuthorizationService.decide(
            user=request.user, action_code="production.master_data.view",
            organization_id=organization_id, business_object={"organizationId": organization_id},
            context={"actionType": "FORMAL_IMPORT_PREVIEW", "businessWrite": False},
        )
        if not decision.get("allowed"):
            raise FormalImportError(decision.get("decisionCode", "PERMISSION_DENIED"), decision.get("reason", "当前账户无权读取正式导入能力。"), {"authorization": decision})
        return decision


class FormalImportTemplateView(FormalImportBaseView):
    def get(self, request, entity):
        try:
            self.authorize_read(request)
            content = FormalImportService.template_bytes(entity)
            schema = FormalImportService.schema(entity)
            filename = f"{FormalImportService.worksheet_name(schema)}-正式导入模板.xlsx"
            response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
            return response
        except FormalImportError as exc:
            return _error_response(exc)


class FormalImportPreviewView(FormalImportBaseView):
    def post(self, request, entity):
        try:
            decision = self.authorize_read(request)
            uploaded = request.FILES.get("file")
            if not uploaded:
                raise FormalImportError("SOURCE_FILE_REQUIRED", "请选择Excel或UTF-8 CSV导入文件。")
            result = FormalImportService.preview(
                entity, uploaded_file=uploaded, organization_id=request.user.company_id,
                actor_binding=preview_actor_binding(user=request.user, organization_id=request.user.company_id),
            )
            result["authorization"] = decision
            return Response(result)
        except FormalImportError as exc:
            return _error_response(exc)


class FormalImportCommitView(FormalImportBaseView):
    def post(self, request, entity):
        trace = build_actor_request_trace(request, entity=entity, phase="COMMIT")
        try:
            uploaded = request.FILES.get("file")
            if not uploaded:
                raise FormalImportError("SOURCE_FILE_REQUIRED", "请选择与预览一致的Excel或UTF-8 CSV导入文件。")
            confirmed = str(request.data.get("confirmed", "")).lower() == "true"
            submitted_binding = request.data.get("previewActorBinding")
            if submitted_binding:
                try:
                    submitted_binding = json.loads(submitted_binding)
                except (TypeError, ValueError) as exc:
                    raise FormalImportError("PREVIEW_ACTOR_CONTEXT_INVALID", "预览身份上下文无效，请重新预览。") from exc
            result = FormalImportService.commit(
                entity, uploaded_file=uploaded, organization_id=request.user.company_id, user=request.user,
                preview_fingerprint=request.data.get("previewFingerprint"), idempotency_key=request.data.get("idempotencyKey"), confirmed=confirmed,
                preview_actor_binding=submitted_binding,
            )
            trace.update(result.get("actorContext") or {})
            trace["authorization"] = (result.get("actorContext") or {}).get("authorizationDecision")
            append_rehearsal_trace(trace, outcome="PASS")
            return Response(result, status=status.HTTP_201_CREATED)
        except (FormalImportError, ProductionFoundationError) as exc:
            trace["authorization"] = (exc.details or {}).get("authorization")
            trace["permissionCode"] = ENTITY_CONFIG.get(entity, (None, None))[1]
            trace["failureMessage"] = exc.message
            append_rehearsal_trace(trace, outcome="FAIL", error_code=exc.code)
            exc.details = {**(exc.details or {}), "requestActorTrace": trace}
            return _error_response(exc)


class FormalImportCurrentActorContextView(FormalImportBaseView):
    parser_classes = []

    def get(self, request):
        trace = build_actor_request_trace(request, entity="formal-import", phase="CURRENT_CONTEXT")
        try:
            actor = resolve_formal_import_actor(
                user=request.user, organization_id=request.user.company_id,
                action_code="masterdata.customer.maintain",
            )
            trace.update(actor)
            trace["importAuthorizationResult"] = "ALLOWED"
        except FormalImportActorContextError as exc:
            trace["importAuthorizationResult"] = exc.code
        return Response({
            "status": "AUTHENTICATED",
            "actorBinding": preview_actor_binding(user=request.user, organization_id=request.user.company_id),
            "requestActorTrace": trace,
        })
