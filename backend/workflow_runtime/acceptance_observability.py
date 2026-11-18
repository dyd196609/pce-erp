from django.db.models import Sum
from django.utils import timezone

from formal_payment_order.models import (
    FormalPaymentOrder,
    FormalPaymentOrderSendGateCanaryScenario,
)

from .fact_loads import FACT_LOAD_CONTRACT_VERSION, fact_load_context_from_request


ACCEPTANCE_OBSERVABILITY_CONTRACT_VERSION = (
    "PCE-ACCEPTANCE-OBSERVABILITY-CONTRACT-V1.0"
)

PAGE_PROFILES = {
    "FIN_PAYMENT_VOUCHER_PREPARE_PREVIEW": {
        "record_scope": "current_server_preview_source",
        "single_record": True,
        "action_count": 3,
    },
    "formal-payment-voucher": {
        "record_scope": "frozen_formal_payment_order_sources",
        "single_record": False,
        "action_count": 0,
    },
    "payment-execution-prepare": {
        "record_scope": "frozen_formal_payment_order_sources",
        "single_record": False,
        "action_count": 0,
    },
}


class AcceptanceFactsNotRegistered(LookupError):
    pass


def build_acceptance_facts(page_code, *, request=None):
    profile = PAGE_PROFILES.get(str(page_code or "").strip())
    if not profile:
        raise AcceptanceFactsNotRegistered(page_code)

    frozen_sources = FormalPaymentOrder.objects.filter(
        status=FormalPaymentOrder.Status.FROZEN_FOR_EXECUTION
    )
    source_count = frozen_sources.count()
    record_count = min(source_count, 1) if profile["single_record"] else source_count
    downstream = FormalPaymentOrderSendGateCanaryScenario.objects.aggregate(
        bank_message_count=Sum("bank_message_count"),
        payment_execution_count=Sum("payment_execution_count"),
    )
    downstream_object_count = int(downstream["bank_message_count"] or 0) + int(
        downstream["payment_execution_count"] or 0
    )
    return {
        "contractVersion": ACCEPTANCE_OBSERVABILITY_CONTRACT_VERSION,
        "factLoadContractVersion": FACT_LOAD_CONTRACT_VERSION,
        "factLoadStatus": "success",
        "apiUrl": (
            "/api/workflow/action-permissions/acceptance-observability/"
            f"{page_code}"
        ),
        "httpStatus": 200,
        "loadedAt": timezone.now().isoformat(),
        **fact_load_context_from_request(request),
        "pageCode": page_code,
        "factSource": "server",
        "recordCount": record_count,
        "selectedCount": 0,
        "actionCount": profile["action_count"],
        "dangerActionCount": 0,
        "businessProgressWriteCount": 0,
        "downstreamObjectCount": downstream_object_count,
        "fieldSources": {
            "recordCount": profile["record_scope"],
            "selectedCount": "server_read_session",
            "actionCount": "server_acceptance_action_profile",
            "dangerActionCount": "server_forbidden_action_profile",
            "businessProgressWriteCount": "server_read_only_request_audit",
            "downstreamObjectCount": (
                "formal_payment_order_send_gate_canary_scenarios"
            ),
        },
    }


__all__ = [
    "ACCEPTANCE_OBSERVABILITY_CONTRACT_VERSION",
    "AcceptanceFactsNotRegistered",
    "PAGE_PROFILES",
    "build_acceptance_facts",
]
