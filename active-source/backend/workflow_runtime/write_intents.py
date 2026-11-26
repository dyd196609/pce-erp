from enum import StrEnum


class WriteIntentCategory(StrEnum):
    PREVIEW_PREPARATION_WRITE = "preview_preparation_write"
    SEND_TASK_PREPARATION_WRITE = "send_task_preparation_write"
    EXECUTION_GATE_PREPARATION_WRITE = (
        "execution_gate_preparation_write"
    )
    SEND_REQUEST_PREPARATION_WRITE = "send_request_preparation_write"
    BANK_SEND_EXECUTION_WRITE = "bank_send_execution_write"
    BANK_MESSAGE_SEND_WRITE = "bank_message_send_write"
    PAYMENT_EXECUTION_WRITE = "payment_execution_write"
    BUSINESS_PROGRESS_WRITE = "business_progress_write"
    AUDIT_WRITE = "audit_write"


SEND_TASK_PREPARATION_KEY = "bankSendTasks"
BANK_SEND_EXECUTION_KEYS = (
    "bankMessages",
    "paymentExecutions",
    "fundsDebits",
    "bankTransactions",
    "paymentVouchers",
    "ledgerEntries",
    "postings",
)
FORBIDDEN_BUSINESS_PROGRESS_KEYS = BANK_SEND_EXECUTION_KEYS


def build_write_intent_facts(
    *,
    preview_preparation_write_count,
    audit_write_count,
    business_progress_counts,
    preview_only_enforced,
):
    preview_count = int(preview_preparation_write_count)
    audit_count = int(audit_write_count)
    if preview_count < 0 or audit_count < 0:
        raise ValueError("write intent counts must be non-negative")
    normalized_execution_counts = {
        key: int(business_progress_counts.get(key, 0))
        for key in BANK_SEND_EXECUTION_KEYS
    }
    send_task_count = int(
        business_progress_counts.get(SEND_TASK_PREPARATION_KEY, 0)
    )
    if (
        send_task_count < 0
        or any(value < 0 for value in normalized_execution_counts.values())
    ):
        raise ValueError("business progress counts must be non-negative")
    forbidden_count = sum(normalized_execution_counts.values())
    if preview_only_enforced is not True:
        raise ValueError("preview-only preparation writes must remain read-only")
    normalized_progress_counts = {
        SEND_TASK_PREPARATION_KEY: send_task_count,
        **normalized_execution_counts,
    }
    return {
        "contractVersion": "PCE-WRITE-INTENT-CONTRACT-V1.0",
        "categories": [
            WriteIntentCategory.PREVIEW_PREPARATION_WRITE.value,
            WriteIntentCategory.SEND_TASK_PREPARATION_WRITE.value,
            WriteIntentCategory.BANK_SEND_EXECUTION_WRITE.value,
            WriteIntentCategory.BUSINESS_PROGRESS_WRITE.value,
            WriteIntentCategory.AUDIT_WRITE.value,
        ],
        "previewPreparationWriteCount": preview_count,
        "sendTaskPreparationWriteCount": send_task_count,
        "bankSendExecutionWriteCount": forbidden_count,
        "auditWriteCount": audit_count,
        "forbiddenBusinessProgressWriteCount": forbidden_count,
        "previewOnlyEnforced": True,
        "businessProgressCounts": normalized_progress_counts,
        "previewWriteAllowed": True,
        "sendTaskPreparationWriteAllowed": True,
        "bankSendExecutionWriteBlocked": forbidden_count == 0,
        "businessProgressWriteBlocked": forbidden_count == 0,
        "bankSendTaskCreated": send_task_count > 0,
        "bankSendCreated": normalized_execution_counts["bankMessages"] > 0,
        "bankMessageSent": (
            normalized_execution_counts["bankMessages"] > 0
        ),
        "paymentExecuted": (
            normalized_execution_counts["paymentExecutions"] > 0
        ),
        "fundsDebited": normalized_execution_counts["fundsDebits"] > 0,
        "bankTransactionCreated": (
            normalized_execution_counts["bankTransactions"] > 0
        ),
    }


def build_bank_send_task_write_intent_facts(
    *,
    send_task_preparation_write_count,
    audit_write_count,
    bank_send_execution_counts,
):
    return build_write_intent_facts(
        preview_preparation_write_count=0,
        audit_write_count=audit_write_count,
        business_progress_counts={
            SEND_TASK_PREPARATION_KEY:
                int(send_task_preparation_write_count),
            **dict(bank_send_execution_counts),
        },
        preview_only_enforced=True,
    )


def build_bank_send_execution_gate_write_intent_facts(
    *,
    execution_gate_preparation_write_count,
    audit_write_count,
    bank_send_execution_counts,
):
    gate_count = int(execution_gate_preparation_write_count)
    if gate_count < 0:
        raise ValueError(
            "execution gate preparation write count must be non-negative"
        )
    base = build_write_intent_facts(
        preview_preparation_write_count=0,
        audit_write_count=audit_write_count,
        business_progress_counts={
            SEND_TASK_PREPARATION_KEY: 0,
            **dict(bank_send_execution_counts),
        },
        preview_only_enforced=True,
    )
    categories = list(base["categories"])
    categories.insert(
        2,
        WriteIntentCategory.EXECUTION_GATE_PREPARATION_WRITE.value,
    )
    categories.insert(
        4,
        WriteIntentCategory.PAYMENT_EXECUTION_WRITE.value,
    )
    return {
        **base,
        "categories": categories,
        "executionGatePreparationWriteCount": gate_count,
        "executionGatePreparationWriteAllowed": True,
        "paymentExecutionWriteCount":
            base["businessProgressCounts"]["paymentExecutions"],
        "paymentExecutionWriteBlocked":
            base["businessProgressCounts"]["paymentExecutions"] == 0,
        "businessProgressWriteCount":
            base["forbiddenBusinessProgressWriteCount"],
    }


def build_bank_send_request_write_intent_facts(
    *,
    send_request_preparation_write_count,
    audit_write_count,
    bank_send_execution_counts,
):
    request_count = int(send_request_preparation_write_count)
    if request_count < 0:
        raise ValueError("send request preparation count must be non-negative")
    base = build_write_intent_facts(
        preview_preparation_write_count=0,
        audit_write_count=audit_write_count,
        business_progress_counts={
            SEND_TASK_PREPARATION_KEY: 0,
            **dict(bank_send_execution_counts),
        },
        preview_only_enforced=True,
    )
    categories = list(base["categories"])
    categories.insert(3, WriteIntentCategory.SEND_REQUEST_PREPARATION_WRITE.value)
    categories.insert(5, WriteIntentCategory.BANK_MESSAGE_SEND_WRITE.value)
    return {
        **base,
        "categories": categories,
        "sendRequestPreparationWriteCount": request_count,
        "sendRequestPreparationWriteAllowed": True,
        "bankMessageSendWriteCount": base["businessProgressCounts"]["bankMessages"],
        "bankMessageSendWriteBlocked":
            base["businessProgressCounts"]["bankMessages"] == 0,
        "paymentExecutionWriteCount":
            base["businessProgressCounts"]["paymentExecutions"],
        "paymentExecutionWriteBlocked":
            base["businessProgressCounts"]["paymentExecutions"] == 0,
        "businessProgressWriteCount": base["forbiddenBusinessProgressWriteCount"],
    }


__all__ = [
    "BANK_SEND_EXECUTION_KEYS",
    "FORBIDDEN_BUSINESS_PROGRESS_KEYS",
    "SEND_TASK_PREPARATION_KEY",
    "WriteIntentCategory",
    "build_bank_send_task_write_intent_facts",
    "build_bank_send_execution_gate_write_intent_facts",
    "build_bank_send_request_write_intent_facts",
    "build_write_intent_facts",
]
