from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from .models import BankSendTask, BankSendTaskCanaryPoolEntry


BLOCKED_SCENARIOS = (
    ("approval_not_approved", "APPROVAL_NOT_APPROVED"),
    ("freeze_inconsistent", "FORMAL_PAYMENT_ORDER_FREEZE_INCONSISTENT"),
    ("risk_review_failed", "RISK_REVIEW_NOT_PASSED"),
    ("funds_unavailable", "FUNDS_NOT_AVAILABLE"),
    ("segregation_failed", "SEGREGATION_OF_DUTIES_NOT_PASSED"),
)
NORMAL_POOL_MINIMUM = 8
BLOCKED_POOL_MINIMUM = 5
RESERVE_POOL_MINIMUM = 20


@dataclass(frozen=True)
class BankSendTaskCanaryFacts:
    normal_pool_count: int
    blocked_pool_count: int
    reserve_pool_count: int
    created_task_count: int
    blocked_task_count: int
    available_pool_count: int

    def as_dict(self):
        return {
            "factType": "BankSendTaskCanaryFacts",
            "currentStateSource": "server",
            "normalPoolCount": self.normal_pool_count,
            "blockedPoolCount": self.blocked_pool_count,
            "reservePoolCount": self.reserve_pool_count,
            "createdTaskCount": self.created_task_count,
            "blockedTaskCount": self.blocked_task_count,
            "availablePoolCount": self.available_pool_count,
            "poolSufficient": (
                self.normal_pool_count >= NORMAL_POOL_MINIMUM
                and self.blocked_pool_count >= BLOCKED_POOL_MINIMUM
                and self.reserve_pool_count >= RESERVE_POOL_MINIMUM
            ),
            "productionUserDataWritten": False,
        }


def _scope():
    return (
        getattr(settings, "PCE_CANARY_TENANT_ID", "tenant-canary-demo"),
        getattr(settings, "PCE_CANARY_BATCH_ID", "PURCHASE-FLOW-DEMO-V1"),
    )


def assert_isolated_canary_pool_enabled():
    if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
        raise RuntimeError("BankSendTask Canary Pool is test-database only")
    database_path = str(settings.DATABASES["default"]["NAME"])
    if database_path.endswith("db.sqlite3"):
        raise RuntimeError("BankSendTask Canary Pool cannot use developer database")


def seed_bank_send_task_canary_pool(preparations):
    assert_isolated_canary_pool_enabled()
    tenant_id, batch_id = _scope()
    rows = list(preparations)[:NORMAL_POOL_MINIMUM]
    if len(rows) < NORMAL_POOL_MINIMUM:
        raise RuntimeError("At least eight bank-send preparations are required")
    with transaction.atomic():
        for index, preparation in enumerate(rows, start=1):
            BankSendTaskCanaryPoolEntry.objects.update_or_create(
                tenant_id=tenant_id,
                batch_id=batch_id,
                scenario_code=f"normal-{index:02d}",
                defaults={
                    "pool_no": f"BST-POOL-NORMAL-{index:02d}",
                    "pool_type": BankSendTaskCanaryPoolEntry.PoolType.NORMAL,
                    "source_preparation": preparation,
                    "eligibility_snapshot": {
                        "eligible": True,
                        "bankSendPreparationPrepared": True,
                        "bankSendGatePassed": True,
                        "formalPaymentOrderFreezeConsistent": True,
                        "approvalApproved": True,
                        "riskReviewPassed": True,
                        "fundsAvailable": True,
                        "segregationOfDutiesPassed": True,
                        "serverDerived": True,
                    },
                    "blocking_reason": "",
                    "reserve_activated": False,
                },
            )
        for index, (scenario, reason) in enumerate(
            BLOCKED_SCENARIOS,
            start=1,
        ):
            BankSendTaskCanaryPoolEntry.objects.update_or_create(
                tenant_id=tenant_id,
                batch_id=batch_id,
                scenario_code=scenario,
                defaults={
                    "pool_no": f"BST-POOL-BLOCKED-{index:02d}",
                    "pool_type": BankSendTaskCanaryPoolEntry.PoolType.BLOCKED,
                    "source_preparation": None,
                    "eligibility_snapshot": {
                        "eligible": False,
                        "blockingReasons": [reason],
                        "serverDerived": True,
                    },
                    "blocking_reason": reason,
                    "reserve_activated": False,
                },
            )
        for index in range(1, RESERVE_POOL_MINIMUM + 1):
            BankSendTaskCanaryPoolEntry.objects.update_or_create(
                tenant_id=tenant_id,
                batch_id=batch_id,
                scenario_code=f"reserve-{index:02d}",
                defaults={
                    "pool_no": f"BST-POOL-RESERVE-{index:02d}",
                    "pool_type": BankSendTaskCanaryPoolEntry.PoolType.RESERVE,
                    "source_preparation": None,
                    "eligibility_snapshot": {
                        "eligible": True,
                        "templateOnly": True,
                        "serverDerived": True,
                    },
                    "blocking_reason": "",
                    "reserve_activated": False,
                },
            )


def bank_send_task_canary_facts():
    tenant_id, batch_id = _scope()
    entries = BankSendTaskCanaryPoolEntry.objects.filter(
        tenant_id=tenant_id,
        batch_id=batch_id,
    )
    normal = entries.filter(
        pool_type=BankSendTaskCanaryPoolEntry.PoolType.NORMAL
    )
    blocked = entries.filter(
        pool_type=BankSendTaskCanaryPoolEntry.PoolType.BLOCKED
    )
    reserve = entries.filter(
        pool_type=BankSendTaskCanaryPoolEntry.PoolType.RESERVE
    )
    created_source_ids = set(
        BankSendTask.objects.filter(
            tenant_id=tenant_id,
            batch_id=batch_id,
        ).values_list("source_preparation_id", flat=True)
    )
    available_normal = sum(
        row.source_preparation_id not in created_source_ids
        for row in normal.only("source_preparation_id")
    )
    activated_reserve = reserve.filter(reserve_activated=True).count()
    return BankSendTaskCanaryFacts(
        normal_pool_count=normal.count(),
        blocked_pool_count=blocked.count(),
        reserve_pool_count=reserve.count(),
        created_task_count=len(created_source_ids),
        blocked_task_count=blocked.filter(
            eligibility_snapshot__eligible=False
        ).count(),
        available_pool_count=available_normal + activated_reserve,
    ).as_dict()


def replenish_bank_send_task_canary_pool(count=8):
    assert_isolated_canary_pool_enabled()
    tenant_id, batch_id = _scope()
    with transaction.atomic():
        rows = list(
            BankSendTaskCanaryPoolEntry.objects.select_for_update()
            .filter(
                tenant_id=tenant_id,
                batch_id=batch_id,
                pool_type=BankSendTaskCanaryPoolEntry.PoolType.RESERVE,
                reserve_activated=False,
            )
            .order_by("pool_no")[:count]
        )
        BankSendTaskCanaryPoolEntry.objects.filter(
            pk__in=[row.pk for row in rows]
        ).update(reserve_activated=True)
    return {
        "replenishedCount": len(rows),
        "canaryPoolFacts": bank_send_task_canary_facts(),
        "productionUserDataWritten": False,
    }
