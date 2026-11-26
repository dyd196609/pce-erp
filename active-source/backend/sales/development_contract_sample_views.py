from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .development_contract_sample import (
    build_development_contract_entry,
    build_development_contract_preview,
    calculate_quote,
    save_development_contract,
)
from .services import SalesBusinessError


def _error(error):
    return Response({"success": False, "data": error.data, "error": {"code": error.code, "message": error.message},
        "meta": {"module": "SALES", "source": "server", "status": error.http_status}}, status=error.http_status)


class DevelopmentContractEntryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            entry = build_development_contract_entry(company_id=request.user.company_id, user=request.user)
        except SalesBusinessError as error:
            return _error(error)
        return Response({"success": True, "data": {"entry": entry}, "error": None,
            "meta": {"module": "SALES", "source": "server", "status": 200}})


class DevelopmentContractSampleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, source_record_id):
        try:
            preview = build_development_contract_preview(company_id=request.user.company_id, source_record_id=source_record_id, user=request.user)
        except SalesBusinessError as error:
            return _error(error)
        return Response({"success": True, "data": {"preview": preview}, "error": None,
            "meta": {"module": "SALES", "source": "server", "status": 200}})

    def post(self, request, source_record_id):
        try:
            preview, replayed = save_development_contract(user=request.user, source_record_id=source_record_id,
                payload=request.data or {}, idempotency_key=request.headers.get("Idempotency-Key"))
        except SalesBusinessError as error:
            return _error(error)
        return Response({"success": True, "data": {"preview": preview, "replayed": replayed}, "error": None,
            "meta": {"module": "SALES", "source": "server", "status": 200}})


class DevelopmentContractQuoteCalculateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, source_record_id):
        try:
            preview = build_development_contract_preview(company_id=request.user.company_id, source_record_id=source_record_id, user=request.user)
            calculated = calculate_quote((request.data or {}).get("lines") or [])
        except SalesBusinessError as error:
            return _error(error)
        return Response({"success": True, "data": {**calculated, "source": preview["source"], "businessWriteCount": 0}, "error": None,
            "meta": {"module": "SALES", "source": "server", "status": 200}})
