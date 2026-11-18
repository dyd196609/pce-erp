from django.db.models import ProtectedError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PurchaseRequest
from .purchase_inquiry_service import create_purchase_inquiry_from_request
from .scm_page_facts import _normalized_object


class PurchaseInquiryFromRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        actor = getattr(request.user, "username", "") or str(request.user)
        try:
            inquiry, created, preparation = create_purchase_inquiry_from_request(request_id, actor)
        except PurchaseRequest.DoesNotExist:
            return Response({
                "success": False,
                "data": None,
                "error": {"code": "PURCHASE_REQUEST_NOT_FOUND", "message": "来源采购申请不存在。"},
                "meta": {"module": "SCM", "productionUserDataWritten": False},
            }, status=404)
        except (ValueError, ProtectedError) as error:
            return Response({
                "success": False,
                "data": None,
                "error": {"code": "PURCHASE_INQUIRY_SOURCE_BLOCKED", "message": str(error)},
                "meta": {"module": "SCM", "productionUserDataWritten": False},
            }, status=409)

        return Response({
            "success": True,
            "data": {
                "created": created,
                "idempotent": not created,
                "inquiry": _normalized_object(inquiry),
                "inquiryPreparation": preparation,
                "supplierQuotationCreated": False,
                "priceApprovalCreated": False,
                "purchaseOrderCreated": False,
            },
            "error": None,
            "meta": {
                "module": "SCM",
                "source": "server",
                "businessWriteCount": 1 if created else 0,
                "productionUserDataWritten": False,
            },
        }, status=201 if created else 200)
