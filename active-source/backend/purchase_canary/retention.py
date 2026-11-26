CANARY_ACCEPTANCE_DATA_TYPE = "canary_acceptance"
AUTOMATED_TEST_DATA_TYPE = "test"

_ACCEPTANCE_PURPOSES = frozenset({
    "persistent_demonstration",
    "canary_acceptance",
    "acceptance",
})


class CanaryAcceptanceDataProtected(RuntimeError):
    pass


def canary_data_type(batch):
    purpose = str(getattr(batch, "purpose", "") or "").strip().lower()
    return (
        CANARY_ACCEPTANCE_DATA_TYPE
        if purpose in _ACCEPTANCE_PURPOSES
        else AUTOMATED_TEST_DATA_TYPE
    )


def canary_retention_policy(batch):
    data_type = canary_data_type(batch)
    protected = data_type == CANARY_ACCEPTANCE_DATA_TYPE
    return {
        "dataType": data_type,
        "visibleOnBusinessPages": protected,
        "autoDeleteAllowed": not protected,
        "cleanupPolicy": "manual_only" if protected else "automatic_allowed",
        "retainedAfterRefresh": protected,
    }


def assert_canary_cleanup_allowed(batch):
    policy = canary_retention_policy(batch)
    if not policy["autoDeleteAllowed"]:
        raise CanaryAcceptanceDataProtected(
            f"验收金丝雀批次 {batch.batch_id} 禁止自动清理"
        )
    return True
