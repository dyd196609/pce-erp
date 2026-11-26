import logging

from django.http import JsonResponse
from django.views.defaults import page_not_found, server_error
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .fact_loads import failed_fact_load_facts


logger = logging.getLogger(__name__)


def pce_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get("request")
    if request is None or request.method != "GET":
        return response

    status_code = response.status_code if response is not None else 500
    if response is None:
        logger.exception(
            "Unhandled API fact read failure",
            exc_info=exc,
        )
    error_code = (
        getattr(exc, "default_code", "")
        or type(exc).__name__
        or "FACT_READ_FAILED"
    )
    error_message = (
        str(getattr(exc, "detail", "") or "")
        or (
            "Server fact read failed"
            if status_code >= 500
            else str(exc)
        )
    )
    fact_load_facts = failed_fact_load_facts(
        api_url=request.path,
        http_status=status_code,
        error_code=str(error_code),
        error_message=error_message,
        request=request,
    )
    payload = {
        "result": "blocked",
        "currentStateSource": "server",
        **fact_load_facts,
        "factLoadFacts": fact_load_facts,
        "data": {
            **fact_load_facts,
            "factLoadFacts": fact_load_facts,
        },
        "error": {
            "code": fact_load_facts["errorCode"],
            "message": fact_load_facts["errorMessage"],
        },
    }
    if response is not None and isinstance(response.data, dict):
        payload["error"]["detail"] = response.data
    return Response(payload, status=status_code)


def _api_error_payload(
    request,
    *,
    status_code,
    error_code,
    error_message,
):
    fact_load_facts = failed_fact_load_facts(
        api_url=request.path,
        http_status=status_code,
        error_code=error_code,
        error_message=error_message,
        request=request,
    )
    return {
        "result": "blocked",
        "currentStateSource": "server",
        **fact_load_facts,
        "factLoadFacts": fact_load_facts,
        "data": {
            **fact_load_facts,
            "factLoadFacts": fact_load_facts,
        },
        "error": {
            "code": fact_load_facts["errorCode"],
            "message": fact_load_facts["errorMessage"],
        },
    }


def pce_not_found_handler(request, exception):
    if not request.path.startswith("/api/"):
        return page_not_found(request, exception)
    return JsonResponse(
        _api_error_payload(
            request,
            status_code=404,
            error_code="API_NOT_FOUND",
            error_message=f"API route not found: {request.path}",
        ),
        status=404,
    )


def pce_api_not_found(request, unmatched_path=""):
    """Return the API error contract even when Django DEBUG is enabled."""
    return pce_not_found_handler(request, exception=None)


def pce_server_error_handler(request):
    if not request.path.startswith("/api/"):
        return server_error(request)
    return JsonResponse(
        _api_error_payload(
            request,
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
            error_message=f"Server fact read failed: {request.path}",
        ),
        status=500,
    )
