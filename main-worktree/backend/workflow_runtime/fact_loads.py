from django.conf import settings
from django.utils import timezone


FACT_LOAD_CONTRACT_VERSION = "PCE-FACT-LOAD-CONTRACT-V1.0"
FACT_LOAD_STATUSES = frozenset(
    {
        "success",
        "loaded",
        "read_failed",
        "empty_valid",
    }
)
FACT_LOAD_CONTEXT_UNAVAILABLE = "server-context-unavailable"
FACT_LOAD_ERROR_REQUIRED_FIELDS = (
    "factLoadStatus",
    "apiUrl",
    "httpStatus",
    "errorCode",
    "errorMessage",
    "loadedAt",
    "tenantId",
    "batchId",
)


class FactLoadContractError(ValueError):
    """Raised when a fact-load payload violates the shared contract."""


def _non_empty_text(value, fallback):
    normalized = str(value or "").strip()
    return normalized or fallback


def fact_load_context_from_request(
    request=None,
    *,
    tenant_id=None,
    batch_id=None,
):
    user = getattr(request, "user", None)
    resolved_tenant_id = (
        tenant_id
        or getattr(request, "pce_tenant_id", None)
        or getattr(request, "tenant_id", None)
        or getattr(user, "tenant_id", None)
        or getattr(settings, "PCE_CANARY_TENANT_ID", None)
    )
    resolved_batch_id = (
        batch_id
        or getattr(request, "pce_batch_id", None)
        or getattr(request, "batch_id", None)
        or getattr(settings, "PCE_CANARY_BATCH_ID", None)
    )
    return {
        "tenantId": _non_empty_text(
            resolved_tenant_id,
            FACT_LOAD_CONTEXT_UNAVAILABLE,
        ),
        "batchId": _non_empty_text(
            resolved_batch_id,
            FACT_LOAD_CONTEXT_UNAVAILABLE,
        ),
    }


def build_fact_load_facts(
    *,
    fact_load_status,
    api_url,
    http_status,
    error_code="",
    error_message="",
    tenant_id=None,
    batch_id=None,
    loaded_at=None,
    request=None,
):
    status = str(fact_load_status or "")
    if status not in FACT_LOAD_STATUSES:
        raise FactLoadContractError(
            f"Unsupported factLoadStatus: {status or '<empty>'}"
        )
    normalized_http_status = int(http_status)
    if normalized_http_status < 100 or normalized_http_status > 599:
        raise FactLoadContractError("httpStatus must be a valid HTTP status")
    if not str(api_url or "").strip():
        raise FactLoadContractError("apiUrl cannot be empty")
    if status == "read_failed" and (
        not str(error_code or "").strip()
        or not str(error_message or "").strip()
    ):
        raise FactLoadContractError(
            "read_failed requires non-empty errorCode and errorMessage"
        )
    if status != "read_failed" and (error_code or error_message):
        raise FactLoadContractError(
            "successful fact loads cannot carry error fields"
        )
    request_context = fact_load_context_from_request(
        request,
        tenant_id=tenant_id,
        batch_id=batch_id,
    )
    facts = {
        "factLoadContractVersion": FACT_LOAD_CONTRACT_VERSION,
        "factLoadStatus": status,
        "apiUrl": str(api_url).strip(),
        "httpStatus": normalized_http_status,
        "errorCode": str(error_code or ""),
        "errorMessage": str(error_message or ""),
        "loadedAt": (
            loaded_at.isoformat()
            if hasattr(loaded_at, "isoformat")
            else str(loaded_at or timezone.now().isoformat())
        ),
        **request_context,
    }
    if status == "read_failed":
        empty_fields = [
            field
            for field in FACT_LOAD_ERROR_REQUIRED_FIELDS
            if field != "httpStatus" and not str(facts[field]).strip()
        ]
        if empty_fields:
            raise FactLoadContractError(
                "read_failed contains empty fields: "
                + ", ".join(empty_fields)
            )
    return facts


def successful_fact_load_facts(
    *,
    result_count,
    api_url,
    tenant_id=None,
    batch_id=None,
    loaded_at=None,
    request=None,
):
    return build_fact_load_facts(
        fact_load_status=(
            "loaded" if int(result_count) > 0 else "empty_valid"
        ),
        api_url=api_url,
        http_status=200,
        tenant_id=tenant_id,
        batch_id=batch_id,
        loaded_at=loaded_at,
        request=request,
    )


def failed_fact_load_facts(
    *,
    api_url,
    http_status,
    error_code,
    error_message,
    tenant_id=None,
    batch_id=None,
    loaded_at=None,
    request=None,
):
    return build_fact_load_facts(
        fact_load_status="read_failed",
        api_url=api_url,
        http_status=http_status,
        error_code=error_code,
        error_message=error_message,
        tenant_id=tenant_id,
        batch_id=batch_id,
        loaded_at=loaded_at,
        request=request,
    )


__all__ = [
    "FACT_LOAD_CONTRACT_VERSION",
    "FACT_LOAD_CONTEXT_UNAVAILABLE",
    "FACT_LOAD_ERROR_REQUIRED_FIELDS",
    "FACT_LOAD_STATUSES",
    "FactLoadContractError",
    "build_fact_load_facts",
    "fact_load_context_from_request",
    "failed_fact_load_facts",
    "successful_fact_load_facts",
]
