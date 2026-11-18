from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from system.authorization import AuthorizationService

from .foundation_import_preview_service import (
    FoundationImportPreviewError,
    FoundationImportPreviewService,
)


class FoundationImportPreviewView(APIView):
    """Validation Action only; this endpoint has no canonical write branch."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        organization_id = request.user.company_id
        decision = AuthorizationService.decide(
            user=request.user,
            action_code="production.master_data.view",
            organization_id=organization_id,
            business_object={"organizationId": organization_id},
            context={"actionType": "VALIDATION_ACTION", "businessWrite": False},
        )
        if not decision.get("allowed"):
            return Response(
                {
                    "factLoadStatus": "read_failed",
                    "code": decision.get("decisionCode", "PERMISSION_DENIED"),
                    "message": decision.get("reason", "当前账户无权执行制造基础数据预览。"),
                    "details": {"authorization": decision},
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response(
                {
                    "factLoadStatus": "read_failed",
                    "code": "SOURCE_FILE_REQUIRED",
                    "message": "请选择需要预览的XLSX来源文件。",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = FoundationImportPreviewService.preview(
                uploaded_file=uploaded_file, organization_id=organization_id,
            )
        except FoundationImportPreviewError as exc:
            return Response(
                {
                    "factLoadStatus": "read_failed",
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        result["authorization"] = decision
        return Response(result)
