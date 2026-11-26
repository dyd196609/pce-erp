from dataclasses import dataclass

from .write_intents import (
    build_bank_send_task_write_intent_facts,
    build_write_intent_facts,
)


class StateTransitionFactError(ValueError):
    """Raised when a state-transition fact payload is internally inconsistent."""


class BankSendPreparationFactError(ValueError):
    """Raised when the authoritative bank-send preparation facts are invalid."""


class BankSendTaskFactError(ValueError):
    """Raised when authoritative bank-send task facts are invalid."""


@dataclass(frozen=True)
class BankSendPreparationFacts:
    """Single server-side source for bank-send preparation acceptance facts."""

    source_formal_payment_order_count: int
    bank_send_preparation_count: int
    prepared_count: int
    eligible_count: int
    preview_count: int
    next_stage_consumed_count: int
    write_intent_facts: dict

    @classmethod
    def from_serialized_rows(
        cls,
        *,
        serialized_rows,
        source_formal_payment_order_count,
        business_progress_counts,
    ):
        rows = tuple(serialized_rows)
        source_count = int(source_formal_payment_order_count)
        if source_count < 0:
            raise BankSendPreparationFactError(
                "sourceFormalPaymentOrderCount must be non-negative"
            )
        preview_only_enforced = all(
            (
                row["messagePreview"]["exists"] is not True
                or row["messagePreview"]["status"] == "preview_only"
            )
            and row["messagePreview"]["sent"] is False
            and row["messagePreview"]["bankSecretExposed"] is False
            for row in rows
        )
        preview_count = sum(
            row["messagePreview"]["exists"] is True for row in rows
        )
        task_count = int(business_progress_counts.get("bankSendTasks", 0))
        audit_count = sum(
            row["auditStatus"] == "committed" for row in rows
        ) + sum(
            row["messagePreview"].get("auditStatus") == "committed"
            for row in rows
        )
        try:
            write_intent_facts = build_write_intent_facts(
                preview_preparation_write_count=preview_count,
                audit_write_count=audit_count,
                business_progress_counts=business_progress_counts,
                preview_only_enforced=preview_only_enforced,
            )
        except ValueError as exc:
            raise BankSendPreparationFactError(str(exc)) from exc
        if write_intent_facts["forbiddenBusinessProgressWriteCount"] != 0:
            raise BankSendPreparationFactError(
                "business progress writes are forbidden before bank sending"
            )
        return cls(
            source_formal_payment_order_count=source_count,
            bank_send_preparation_count=len(rows),
            prepared_count=sum(row["status"] == "prepared" for row in rows),
            eligible_count=sum(
                row["gate"]["eligible"] is True for row in rows
            ),
            preview_count=preview_count,
            next_stage_consumed_count=task_count,
            write_intent_facts=write_intent_facts,
        )

    def as_dict(self):
        return {
            "factType": "BankSendPreparationFacts",
            "currentStateSource": "server",
            "sourceFormalPaymentOrderCount":
                self.source_formal_payment_order_count,
            "bankSendPreparationCount": self.bank_send_preparation_count,
            "preparedCount": self.prepared_count,
            "eligibleCount": self.eligible_count,
            "previewCount": self.preview_count,
            "nextStageConsumedCount": self.next_stage_consumed_count,
            "writeIntentFacts": dict(self.write_intent_facts),
            "passed": (
                self.source_formal_payment_order_count >= 8
                and self.bank_send_preparation_count >= 8
                and self.prepared_count == self.bank_send_preparation_count
                and self.eligible_count == self.bank_send_preparation_count
                and self.write_intent_facts[
                    "forbiddenBusinessProgressWriteCount"
                ]
                == 0
                and self.write_intent_facts["previewOnlyEnforced"] is True
            ),
        }


@dataclass(frozen=True)
class BankSendTaskFacts:
    """Single server-side source for bank-send task acceptance facts."""

    source_bank_send_preparation_count: int
    preview_ready_source_count: int
    bank_send_task_count: int
    prepared_count: int
    queued_count: int
    ready_to_send_count: int
    write_intent_facts: dict

    @classmethod
    def from_serialized_rows(
        cls,
        *,
        serialized_sources,
        serialized_rows,
        bank_send_execution_counts,
    ):
        sources = tuple(serialized_sources)
        rows = tuple(serialized_rows)
        preview_ready_count = sum(
            source["taskEligibility"]["eligible"] is True
            for source in sources
        )
        if any(
            row["messagePreview"]["status"] != "preview_only"
            or row["messagePreview"]["sent"] is not False
            for row in rows
        ):
            raise BankSendTaskFactError(
                "bank-send tasks require preview_only message bindings"
            )
        audit_count = sum(
            int(row["writeIntentFacts"]["auditWriteCount"])
            for row in rows
        )
        try:
            write_intent_facts = (
                build_bank_send_task_write_intent_facts(
                    send_task_preparation_write_count=len(rows),
                    audit_write_count=audit_count,
                    bank_send_execution_counts=bank_send_execution_counts,
                )
            )
        except ValueError as exc:
            raise BankSendTaskFactError(str(exc)) from exc
        if write_intent_facts["bankSendExecutionWriteCount"] != 0:
            raise BankSendTaskFactError(
                "bank-send execution writes are forbidden in V59"
            )
        return cls(
            source_bank_send_preparation_count=len(sources),
            preview_ready_source_count=preview_ready_count,
            bank_send_task_count=len(rows),
            prepared_count=sum(row["status"] == "prepared" for row in rows),
            queued_count=sum(row["status"] == "queued" for row in rows),
            ready_to_send_count=sum(
                row["status"] == "ready_to_send" for row in rows
            ),
            write_intent_facts=write_intent_facts,
        )

    def as_dict(self):
        sent_count = 0
        execution_count = 0
        return {
            "factType": "BankSendTaskFacts",
            "currentStateSource": "server",
            "sourceBankSendPreparationCount":
                self.source_bank_send_preparation_count,
            "previewReadySourceCount": self.preview_ready_source_count,
            "bankSendTaskCount": self.bank_send_task_count,
            "taskCount": self.bank_send_task_count,
            "preparedCount": self.prepared_count,
            "queuedCount": self.queued_count,
            "readyToSendCount": self.ready_to_send_count,
            "sentCount": sent_count,
            "executionCount": execution_count,
            "writeIntentFacts": dict(self.write_intent_facts),
            "passed": (
                self.source_bank_send_preparation_count >= 8
                and self.preview_ready_source_count >= 1
                and self.ready_to_send_count == self.bank_send_task_count
                and self.write_intent_facts[
                    "bankSendExecutionWriteCount"
                ]
                == 0
                and self.write_intent_facts[
                    "bankSendExecutionWriteBlocked"
                ]
                is True
                and sent_count == 0
                and execution_count == 0
            ),
        }


@dataclass(frozen=True)
class BankSendExecutionGateFacts:
    """Authoritative pre-execution authorization facts."""

    gate_count: int
    pending_review_count: int
    approved_count: int
    ready_for_execution_count: int
    write_intent_facts: dict

    @classmethod
    def from_serialized_rows(cls, *, serialized_rows, write_intent_facts):
        rows = tuple(serialized_rows)
        return cls(
            gate_count=len(rows),
            pending_review_count=sum(
                row["status"] == "pending_review" for row in rows
            ),
            approved_count=sum(
                row["status"] == "approved" for row in rows
            ),
            ready_for_execution_count=sum(
                row["status"] == "ready_for_execution" for row in rows
            ),
            write_intent_facts=dict(write_intent_facts),
        )

    def as_dict(self):
        return {
            "factType": "BankSendExecutionGateFacts",
            "currentStateSource": "server",
            "gateCount": self.gate_count,
            "pendingReviewCount": self.pending_review_count,
            "approvedCount": self.approved_count,
            "readyForExecutionCount": self.ready_for_execution_count,
            "executedCount": 0,
            "bankSendExecutionCount": 0,
            "bankMessageSentCount": 0,
            "paymentExecutionCount": 0,
            "writeIntentFacts": dict(self.write_intent_facts),
            "passed": (
                self.write_intent_facts[
                    "bankSendExecutionWriteCount"
                ]
                == 0
                and self.write_intent_facts[
                    "paymentExecutionWriteCount"
                ]
                == 0
                and self.write_intent_facts[
                    "businessProgressWriteCount"
                ]
                == 0
            ),
        }


@dataclass(frozen=True)
class BankSendRequestFacts:
    """Authoritative bank send pre-dispatch request facts."""

    request_count: int
    draft_count: int
    validated_count: int
    ready_to_dispatch_count: int
    write_intent_facts: dict

    @classmethod
    def from_serialized_rows(cls, *, serialized_rows, write_intent_facts):
        rows = tuple(serialized_rows)
        return cls(
            request_count=len(rows),
            draft_count=sum(row["status"] == "draft" for row in rows),
            validated_count=sum(row["status"] == "validated" for row in rows),
            ready_to_dispatch_count=sum(
                row["status"] == "ready_to_dispatch" for row in rows
            ),
            write_intent_facts=dict(write_intent_facts),
        )

    def as_dict(self):
        writes = self.write_intent_facts
        return {
            "factType": "BankSendRequestFacts",
            "currentStateSource": "server",
            "requestCount": self.request_count,
            "draftCount": self.draft_count,
            "validatedCount": self.validated_count,
            "readyToDispatchCount": self.ready_to_dispatch_count,
            "bankMessageSentCount": 0,
            "paymentExecutionCount": 0,
            "fundsDebitCount": 0,
            "writeIntentFacts": dict(writes),
            "passed": (
                writes["bankSendExecutionWriteCount"] == 0
                and writes["bankMessageSendWriteCount"] == 0
                and writes["paymentExecutionWriteCount"] == 0
                and writes["businessProgressWriteCount"] == 0
            ),
        }


def status_transition_facts(*, history, state_machine_consistent):
    """Build the authoritative server-side transition history/count pair."""
    persisted_history = list(history)
    return {
        "statusTransitionHistory": persisted_history,
        "statusTransitionCount": len(persisted_history),
        "stateMachineConsistent": state_machine_consistent is True,
    }


def assert_status_transition_count_matches_history(payload):
    """Reject incomplete or contradictory server transition facts."""
    history = payload.get("statusTransitionHistory")
    count = payload.get("statusTransitionCount")
    if not isinstance(history, list):
        raise StateTransitionFactError(
            "statusTransitionHistory must be a server-derived list"
        )
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise StateTransitionFactError(
            "statusTransitionCount must be a non-negative server-derived integer"
        )
    if count != len(history):
        raise StateTransitionFactError(
            "statusTransitionCount must equal statusTransitionHistory length"
        )
    return payload


def business_state_collection_facts(serialized_rows):
    """Aggregate already verified server row facts without client recomputation."""
    rows = list(serialized_rows)
    history = [
        transition
        for row in rows
        for transition in row["statusTransitionHistory"]
    ]
    payload = status_transition_facts(
        history=history,
        state_machine_consistent=all(
            row["stateMachineConsistent"] is True for row in rows
        ),
    )
    return {
        "currentStateSource": "server",
        "objectCount": len(rows),
        **assert_status_transition_count_matches_history(payload),
    }


def _serialize_transition(row):
    operator_name = row.operator.get_username()
    timestamp = row.timestamp.isoformat()
    return {
        "id": row.pk,
        "objectType": row.object_type,
        "objectId": row.object_id,
        "sourceState": row.source_state,
        "targetState": row.target_state,
        "operator": {
            "id": row.operator_id,
            "name": operator_name,
        },
        "timestamp": timestamp,
        "reason": row.reason,
        "version": row.version,
        "auditReference": row.audit_reference,
        "actionCode": row.action_code,
        "workflowInstanceId": row.workflow_instance_id,
        # Compatibility aliases consumed by existing strict-page diagnostics.
        "businessType": row.object_type,
        "businessObjectId": row.object_id,
        "fromStatus": row.source_state,
        "toStatus": row.target_state,
        "operatorId": row.operator_id,
        "operatorName": operator_name,
        "transitionVersion": row.version,
        "createdAt": timestamp,
    }


def business_state_transition_facts(
    *,
    business_object,
    object_type,
    expected_transitions,
    audit_target_type,
    expected_workflow_instance_id=None,
):
    """Build and verify persisted transition facts for any governed object."""
    from reconciliation.models import BusinessActionAuditRecord

    from .models import BusinessStateTransition

    transitions = list(
        BusinessStateTransition.objects.filter(
            object_type=object_type,
            object_id=business_object.pk,
        )
        .select_related("operator", "workflow_instance")
        .order_by("version", "timestamp", "pk")
    )
    history = [_serialize_transition(row) for row in transitions]
    expected = expected_transitions.get(business_object.status)
    actual = tuple(
        (row["sourceState"], row["targetState"], row["actionCode"])
        for row in history
    )
    consistent = expected is not None and actual == tuple(expected)
    consistent = consistent and [
        row["version"] for row in history
    ] == list(range(1, len(history) + 1))
    consistent = consistent and all(
        row["reason"]
        and row["auditReference"].startswith("BusinessActionAuditRecord:")
        for row in history
    )
    if expected_workflow_instance_id is not None:
        consistent = consistent and all(
            row["workflowInstanceId"] == expected_workflow_instance_id
            for row in history
        )
    try:
        audit_ids = [
            int(row["auditReference"].rsplit(":", 1)[1])
            for row in history
        ]
    except (IndexError, TypeError, ValueError):
        audit_ids = []
        consistent = False
    audits = {
        row.pk: row
        for row in BusinessActionAuditRecord.objects.filter(pk__in=audit_ids)
    }
    consistent = consistent and len(audits) == len(history)
    consistent = consistent and all(
        audit_id in audits
        and audits[audit_id].target_type == audit_target_type
        and str(audits[audit_id].target_id) == str(business_object.pk)
        and audits[audit_id].action_code == history[index]["actionCode"]
        and audits[audit_id].result == "committed"
        and audits[audit_id].actor_id == history[index]["operatorId"]
        for index, audit_id in enumerate(audit_ids)
    )
    payload = status_transition_facts(
        history=history,
        state_machine_consistent=consistent,
    )
    return assert_status_transition_count_matches_history(payload)


def business_state_transition_facts_from_allowed_transitions(
    *,
    business_object,
    object_type,
    allowed_transitions,
    audit_target_types,
    initial_states,
):
    """Verify a governed object whose valid history can contain repeated checks."""
    from reconciliation.models import BusinessActionAuditRecord

    from .models import BusinessStateTransition

    transitions = list(
        BusinessStateTransition.objects.filter(
            object_type=object_type,
            object_id=business_object.pk,
        )
        .select_related("operator", "workflow_instance")
        .order_by("version", "timestamp", "pk")
    )
    history = [_serialize_transition(row) for row in transitions]
    allowed = set(allowed_transitions)
    initial = set(initial_states)
    target_types = set(audit_target_types)
    consistent = [
        row["version"] for row in history
    ] == list(range(1, len(history) + 1))
    consistent = consistent and all(
        (
            row["sourceState"],
            row["targetState"],
            row["actionCode"],
        )
        in allowed
        for row in history
    )
    if history:
        consistent = consistent and history[0]["sourceState"] in initial
        consistent = consistent and all(
            history[index - 1]["targetState"] == row["sourceState"]
            for index, row in enumerate(history[1:], 1)
        )
        consistent = (
            consistent
            and history[-1]["targetState"] == business_object.status
        )
    else:
        consistent = consistent and business_object.status in initial
    consistent = consistent and all(
        row["reason"]
        and row["auditReference"].startswith("BusinessActionAuditRecord:")
        for row in history
    )
    try:
        audit_ids = [
            int(row["auditReference"].rsplit(":", 1)[1])
            for row in history
        ]
    except (IndexError, TypeError, ValueError):
        audit_ids = []
        consistent = False
    audits = {
        row.pk: row
        for row in BusinessActionAuditRecord.objects.filter(pk__in=audit_ids)
    }
    consistent = consistent and len(audits) == len(history)
    consistent = consistent and all(
        audit_id in audits
        and audits[audit_id].target_type in target_types
        and str(audits[audit_id].target_id) == str(business_object.pk)
        and audits[audit_id].action_code == history[index]["actionCode"]
        and audits[audit_id].result == "committed"
        and audits[audit_id].actor_id == history[index]["operatorId"]
        for index, audit_id in enumerate(audit_ids)
    )
    return assert_status_transition_count_matches_history(
        status_transition_facts(
            history=history,
            state_machine_consistent=consistent,
        )
    )


__all__ = [
    "BankSendPreparationFactError",
    "BankSendPreparationFacts",
    "BankSendTaskFactError",
    "BankSendTaskFacts",
    "BankSendExecutionGateFacts",
    "BankSendRequestFacts",
    "StateTransitionFactError",
    "assert_status_transition_count_matches_history",
    "business_state_collection_facts",
    "business_state_transition_facts",
    "business_state_transition_facts_from_allowed_transitions",
    "status_transition_facts",
]
