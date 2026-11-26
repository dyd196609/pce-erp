from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PurchaseInquiry, SupplierQuotation
from .scm_page_facts import _normalized_object
from .supplier_quotation_service import save_supplier_quotation, submit_supplier_quotation


def _response(quotation, created=False):
    return {
        "success": True,
        "data": {
            "created": created,
            "quotation": _normalized_object(quotation),
            "priceApprovalCreated": False,
            "purchaseOrderCreated": False,
            "supplierRecommendationCreated": False,
        },
        "error": None,
        "meta": {"module": "SCM", "source": "server", "businessWriteCount": 1, "productionUserDataWritten": False},
    }


class SupplierQuotationSaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            quotation, created = save_supplier_quotation(
                request.data.get("sourceInquiryId"), request.data.get("supplierId"),
                request.data.get("materialCode"), request.data.get("quotePrice"),
                request.data.get("remark", ""), request.data.get("currency", "CNY"),
            )
            return Response(_response(quotation, created), status=201 if created else 200)
        except PurchaseInquiry.DoesNotExist:
            return Response({"success": False, "data": None, "error": {"code": "SOURCE_INQUIRY_NOT_FOUND", "message": "来源询价不存在。"}, "meta": {"module": "SCM", "productionUserDataWritten": False}}, status=404)
        except ValueError as error:
            return Response({"success": False, "data": None, "error": {"code": "SUPPLIER_QUOTATION_BLOCKED", "message": str(error)}, "meta": {"module": "SCM", "productionUserDataWritten": False}}, status=409)


class SupplierQuotationSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quotation_id):
        try:
            return Response(_response(submit_supplier_quotation(quotation_id)))
        except SupplierQuotation.DoesNotExist:
            return Response({"success": False, "data": None, "error": {"code": "SUPPLIER_QUOTATION_NOT_FOUND", "message": "供应商报价不存在。"}, "meta": {"module": "SCM", "productionUserDataWritten": False}}, status=404)
        except ValueError as error:
            return Response({"success": False, "data": None, "error": {"code": "SUPPLIER_QUOTATION_BLOCKED", "message": str(error)}, "meta": {"module": "SCM", "productionUserDataWritten": False}}, status=409)
