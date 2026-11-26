from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie

from pde.production_foundation_service import ProductionFoundationError

from .validated_fact_formalization_service import ValidatedFactFormalizationService


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ValidatedFactFormalizationView(APIView):
    """Preflight/readback plus the explicitly authorized, idempotent minimal write."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(ValidatedFactFormalizationService.facts(request.user.company_id))

    def post(self, request):
        try:
            return Response(ValidatedFactFormalizationService.execute(request.user))
        except ProductionFoundationError as exc:
            return Response(
                {"errorCode": exc.code, "errorMessage": exc.message, "details": exc.details},
                status=status.HTTP_403_FORBIDDEN if exc.code in {
                    "PERMISSION_DENIED", "FORMAL_EXECUTION_CHAIN_REQUIRED"
                } else status.HTTP_409_CONFLICT,
            )
