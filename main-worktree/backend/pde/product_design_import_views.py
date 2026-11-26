from urllib.parse import quote

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .product_design_import_service import (
    build_product_design_import_template, commit_product_design_import,
    parse_product_design_import,
)
from .product_design_service import ProductDesignError
from .product_design_export_service import export_product_design_excel


def _error(exc):
    return Response(
        {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        status=exc.http_status,
    )


class ProductDesignImportBaseView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]


class ProductDesignImportTemplateView(ProductDesignImportBaseView):
    parser_classes = []

    def get(self, request):
        content = build_product_design_import_template()
        filename = "产品设计导入模板.xlsx"
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return response


class ProductDesignImportPreviewView(ProductDesignImportBaseView):
    def post(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return _error(ProductDesignError("SOURCE_FILE_REQUIRED", "请选择产品设计Excel导入文件。"))
        try:
            return Response(parse_product_design_import(uploaded, request.user.company_id))
        except ProductDesignError as exc:
            return _error(exc)


class ProductDesignImportCommitView(ProductDesignImportBaseView):
    def post(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return _error(ProductDesignError("SOURCE_FILE_REQUIRED", "请选择与预览一致的产品设计Excel导入文件。"))
        try:
            result = commit_product_design_import(
                uploaded_file=uploaded, user=request.user,
                preview_fingerprint=request.data.get("previewFingerprint"),
                idempotency_key=request.data.get("idempotencyKey"),
                confirmed=str(request.data.get("confirmed") or "").lower() == "true",
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except ProductDesignError as exc:
            return _error(exc)


class ProductDesignExportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            content, audit = export_product_design_excel(user=request.user, payload=request.data)
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            filename = f"产品设计当前结果-{timezone.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
            response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
            response["X-PCE-Export-Audit-Id"] = str(audit.pk)
            return response
        except ProductDesignError as exc:
            return _error(exc)
