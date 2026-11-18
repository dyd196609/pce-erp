from django.conf import settings
from django.db import transaction

from bank_send_execution_gate.models import BankSendExecutionGate
from .models import BankSendRequestCanaryPoolEntry


BLOCKED_SCENARIOS = (
    ("authorization_hash_changed", "AUTHORIZATION_HASH_CHANGED"),
    ("amount_changed", "AMOUNT_CHANGED"),
    ("beneficiary_account_changed", "BENEFICIARY_ACCOUNT_CHANGED"),
    ("preview_hash_changed", "PREVIEW_HASH_CHANGED"),
    ("interface_unavailable", "INTERFACE_UNAVAILABLE"),
    ("authorization_invalidated", "AUTHORIZATION_INVALIDATED"),
    ("formal_order_freeze_changed", "FORMAL_ORDER_FREEZE_CHANGED"),
    ("segregation_failed", "SEGREGATION_FAILED"),
)


def _assert_canary_database():
    if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
        raise RuntimeError("BankSendRequest canary pool is test-database only")


@transaction.atomic
def seed_bank_send_request_canary_pool(gates=None):
    _assert_canary_database()
    tenant_id = settings.PCE_CANARY_TENANT_ID
    batch_id = settings.PCE_CANARY_BATCH_ID
    sources = list(gates or BankSendExecutionGate.objects.filter(
        tenant_id=tenant_id, batch_id=batch_id, status="ready_for_execution"
    ).order_by("gate_no")[:8])
    if len(sources) < 8:
        raise RuntimeError("Eight ready_for_execution gates are required")
    for index, gate in enumerate(sources, 1):
        BankSendRequestCanaryPoolEntry.objects.update_or_create(
            tenant_id=tenant_id, batch_id=batch_id, scenario_code=f"normal-{index:02d}",
            defaults={
                "pool_no": f"BSR-POOL-N-{index:02d}", "pool_type": "normal",
                "source_gate": gate,
                "validation_snapshot": {"eligible": True, "serverDerived": True},
                "blocking_reason": "",
            },
        )
    for index, (scenario, reason) in enumerate(BLOCKED_SCENARIOS, 1):
        BankSendRequestCanaryPoolEntry.objects.update_or_create(
            tenant_id=tenant_id, batch_id=batch_id, scenario_code=scenario,
            defaults={
                "pool_no": f"BSR-POOL-B-{index:02d}", "pool_type": "blocked",
                "source_gate": sources[(index - 1) % 8],
                "validation_snapshot": {
                    "eligible": False, "result": "blocked",
                    "blockingReasons": [reason], "serverDerived": True,
                },
                "blocking_reason": reason,
            },
        )
    for index in range(1, 21):
        BankSendRequestCanaryPoolEntry.objects.update_or_create(
            tenant_id=tenant_id, batch_id=batch_id, scenario_code=f"reserve-{index:02d}",
            defaults={
                "pool_no": f"BSR-POOL-R-{index:02d}", "pool_type": "reserve",
                "source_gate": None,
                "validation_snapshot": {
                    "eligible": True, "templateOnly": True, "serverDerived": True,
                },
                "blocking_reason": "", "reserve_activated": False,
            },
        )
    return bank_send_request_canary_facts()


def bank_send_request_canary_facts():
    empty = {
        "factType": "BankSendRequestCanaryFacts",
        "currentStateSource": "server", "normalPoolCount": 0,
        "blockedPoolCount": 0, "reservePoolCount": 0,
        "createdRequestCount": 0, "blockedRequestCount": 0,
        "availablePoolCount": 0, "poolSufficient": False,
        "productionUserDataWritten": False,
    }
    if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
        return empty
    qs = BankSendRequestCanaryPoolEntry.objects.filter(
        tenant_id=settings.PCE_CANARY_TENANT_ID,
        batch_id=settings.PCE_CANARY_BATCH_ID,
    )
    normal = qs.filter(pool_type="normal")
    blocked = qs.filter(pool_type="blocked")
    reserve = qs.filter(pool_type="reserve")
    created = normal.filter(source_gate__send_request__isnull=False)
    return {
        **empty,
        "normalPoolCount": normal.count(),
        "blockedPoolCount": blocked.count(),
        "reservePoolCount": reserve.count(),
        "createdRequestCount": created.count(),
        "blockedRequestCount": blocked.count(),
        "availablePoolCount":
            normal.filter(source_gate__send_request__isnull=True).count()
            + reserve.filter(reserve_activated=True).count(),
        "poolSufficient": (
            normal.count() >= 8 and blocked.count() >= 8 and reserve.count() >= 20
        ),
    }

