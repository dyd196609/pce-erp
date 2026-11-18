from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from system.authorization import AuthorizationService

from .engineering_source_formalization import build_engineering_source_formalization_preview


class EngineeringSourceFormalizationPreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, source_record_id):
        decision = AuthorizationService.decide(
            user=request.user,
            action_code="sales.order.view",
            organization_id=request.user.company_id,
            business_object={"organizationId": request.user.company_id},
        )
        if not decision["allowed"]:
            return Response({
                "success": False,
                "data": {"authorization": decision},
                "error": {"code": decision["decisionCode"], "message": decision["reason"]},
                "meta": {"module": "SALES", "source": "server", "status": 403},
            }, status=403)
        try:
            preview = build_engineering_source_formalization_preview(
                company_id=request.user.company_id,
                source_record_id=source_record_id,
                user=request.user,
            )
        except ValueError:
            return Response({
                "success": False, "data": None,
                "error": {"code": "ENGINEERING_SOURCE_NOT_FOUND", "message": "当前公司范围内未找到该工程来源。"},
                "meta": {"module": "SALES", "source": "server", "status": 404},
            }, status=404)
        return Response({
            "success": True,
            "data": {"preview": preview, "authorization": decision, **{key: preview[key] for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts")}},
            "error": None,
            "meta": {"module": "SALES", "source": "server", "status": 200},
        })
