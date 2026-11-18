from django.conf import settings
from django.db import transaction

from bank_send_task.models import BankSendTask

from .models import BankSendExecutionGateCanaryPoolEntry


BLOCKED_SCENARIOS = (
    ("freeze_failed", "FORMAL_PAYMENT_ORDER_FREEZE_INCONSISTENT"),
    ("approval_failed", "APPROVAL_NOT_APPROVED"),
    ("risk_failed", "RISK_REVIEW_NOT_PASSED"),
    ("funds_insufficient", "FUNDS_NOT_AVAILABLE"),
    ("segregation_failed", "SEGREGATION_OF_DUTIES_NOT_PASSED"),
    ("message_hash_changed", "MESSAGE_PREVIEW_HASH_MISMATCH"),
)


def _assert_canary_database():
    if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
        raise RuntimeError(
            "BankSendExecutionGate canary pool is test-database only"
        )


@transaction.atomic
def seed_bank_send_execution_gate_canary_pool(tasks=None):
    _assert_canary_database()
    tenant_id = settings.PCE_CANARY_TENANT_ID
    batch_id = settings.PCE_CANARY_BATCH_ID
    source_tasks = list(
        tasks
        or BankSendTask.objects.filter(
            tenant_id=tenant_id,
            batch_id=batch_id,
            status=BankSendTask.Status.READY_TO_SEND,
        ).order_by("task_no")[:8]
    )
    if len(source_tasks) < 8:
        raise RuntimeError("Eight ready_to_send tasks are required")
    for index, task in enumerate(source_tasks, 1):
        BankSendExecutionGateCanaryPoolEntry.objects.update_or_create(
            tenant_id=tenant_id,
            batch_id=batch_id,
            scenario_code=f"normal-{index:02d}",
            defaults={
                "pool_no": f"BSEG-POOL-N-{index:02d}",
                "pool_type": "normal",
                "source_task": task,
                "eligibility_snapshot": {
                    "eligible": True,
                    "serverDerived": True,
                },
                "blocking_reason": "",
            },
        )
    for index, (scenario, reason) in enumerate(BLOCKED_SCENARIOS, 1):
        BankSendExecutionGateCanaryPoolEntry.objects.update_or_create(
            tenant_id=tenant_id,
            batch_id=batch_id,
            scenario_code=scenario,
            defaults={
                "pool_no": f"BSEG-POOL-B-{index:02d}",
                "pool_type": "blocked",
                "source_task": source_tasks[(index - 1) % 8],
                "eligibility_snapshot": {
                    "eligible": False,
                    "blockingReasons": [reason],
                    "serverDerived": True,
                },
                "blocking_reason": reason,
            },
        )
    for index in range(1, 21):
        BankSendExecutionGateCanaryPoolEntry.objects.update_or_create(
            tenant_id=tenant_id,
            batch_id=batch_id,
            scenario_code=f"reserve-{index:02d}",
            defaults={
                "pool_no": f"BSEG-POOL-R-{index:02d}",
                "pool_type": "reserve",
                "source_task": None,
                "eligibility_snapshot": {
                    "eligible": True,
                    "templateOnly": True,
                    "serverDerived": True,
                },
                "blocking_reason": "",
                "reserve_activated": False,
            },
        )
    return bank_send_execution_gate_canary_facts()


def bank_send_execution_gate_canary_facts():
    if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
        return {
            "factType": "BankSendExecutionGateCanaryFacts",
            "currentStateSource": "server",
            "normalPoolCount": 0,
            "blockedPoolCount": 0,
            "reservePoolCount": 0,
            "createdGateCount": 0,
            "blockedGateCount": 0,
            "availablePoolCount": 0,
            "poolSufficient": False,
            "productionUserDataWritten": False,
        }
    tenant_id = settings.PCE_CANARY_TENANT_ID
    batch_id = settings.PCE_CANARY_BATCH_ID
    queryset = BankSendExecutionGateCanaryPoolEntry.objects.filter(
        tenant_id=tenant_id,
        batch_id=batch_id,
    )
    normal = queryset.filter(pool_type="normal")
    blocked = queryset.filter(pool_type="blocked")
    reserve = queryset.filter(pool_type="reserve")
    created = normal.filter(source_task__execution_gate__isnull=False)
    available = normal.filter(source_task__execution_gate__isnull=True).count()
    available += reserve.filter(reserve_activated=True).count()
    return {
        "factType": "BankSendExecutionGateCanaryFacts",
        "currentStateSource": "server",
        "normalPoolCount": normal.count(),
        "blockedPoolCount": blocked.count(),
        "reservePoolCount": reserve.count(),
        "createdGateCount": created.count(),
        "blockedGateCount": blocked.count(),
        "availablePoolCount": available,
        "poolSufficient": (
            normal.count() >= 8
            and blocked.count() >= 6
            and reserve.count() >= 20
        ),
        "productionUserDataWritten": False,
    }


__all__ = [
    "BLOCKED_SCENARIOS",
    "bank_send_execution_gate_canary_facts",
    "seed_bank_send_execution_gate_canary_pool",
]
