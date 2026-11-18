from django.conf import settings
from django.db import IntegrityError, transaction

from bank_send_request.models import BankSendRequest
from reconciliation.services import ReconciliationError, canonical_hash
from workflow_runtime.fact_loads import build_fact_load_facts
from workflow_runtime.facts import business_state_transition_facts
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .models import BankSendExecutionRecovery, BankSendExecutionSimulation


VERSION = "V1.14.2.8.4.7.64"
MODULE_CODE = "bank-send-simulation"
CANONICAL_NAME = "银行发送执行模拟"
SIMULATION_OBJECT_TYPE = "bank_send_execution_simulation"
RECOVERY_OBJECT_TYPE = "bank_send_execution_recovery"
EXECUTION_VERSION = 1
SIMULATION_TRANSITIONS = (
    ("created", "validated"),
    ("validated", "simulation_running"),
    ("simulation_running", "simulation_success"),
    ("simulation_running", "simulation_failed"),
)
RECOVERY_TRANSITIONS = (("pending", "resolved"),)
SIMULATION_EXPECTED_TRANSITIONS = {
    "created": (),
    "validated": (
        ("created", "validated", "validate-bank-send-execution-simulation"),
    ),
    "simulation_running": (
        ("created", "validated", "validate-bank-send-execution-simulation"),
        ("validated", "simulation_running", "run-bank-send-execution-simulation"),
    ),
    "simulation_success": (
        ("created", "validated", "validate-bank-send-execution-simulation"),
        ("validated", "simulation_running", "run-bank-send-execution-simulation"),
        ("simulation_running", "simulation_success", "complete-bank-send-execution-simulation"),
    ),
    "simulation_failed": (
        ("created", "validated", "validate-bank-send-execution-simulation"),
        ("validated", "simulation_running", "run-bank-send-execution-simulation"),
        ("simulation_running", "simulation_failed", "fail-bank-send-execution-simulation"),
    ),
}
RECOVERY_EXPECTED_TRANSITIONS = {
    "pending": (),
    "resolved": (
        ("pending", "resolved", "resolve-bank-send-execution-recovery"),
    ),
}
STATUS_LABELS = {
    "created": "已创建",
    "validated": "校验通过",
    "simulation_running": "模拟执行中",
    "simulation_success": "模拟成功",
    "simulation_failed": "模拟失败",
}
RECOVERY_LABELS = {"pending": "待恢复", "resolved": "已恢复"}


def protection_counts():
    return {
        "bankMessageSentCount": 0,
        "paymentExecutionCount": 0,
        "fundsDebitCount": 0,
        "bankTransactionCount": 0,
        "businessProgressWriteCount": 0,
    }


def _source_parts(request_object):
    gate = request_object.source_gate
    task = gate.source_task
    preparation = task.source_preparation
    order = preparation.source_formal_payment_order
    return gate, task, preparation, order, order.execution_freeze


def evaluate_simulation_checks(request_object, *, simulated_interface_available=True):
    gate, task, preparation, order, freeze = _source_parts(request_object)
    request_validation_payload = {
        key: value
        for key, value in request_object.validation_snapshot.items()
        if key != "validationHash"
    }
    checks = {
        "requestReadyToDispatch": request_object.status == "ready_to_dispatch",
        "authorizationReadyForExecution": gate.status == "ready_for_execution",
        "authorizationHashConsistent": (
            request_object.authorization_hash_snapshot == gate.authorization_hash
        ),
        "requestHashConsistent": (
            request_object.validation_hash
            == canonical_hash(request_validation_payload)
        ),
        "paymentAmountConsistent": (
            request_object.amount_snapshot
            == str(task.amount)
            == str(preparation.amount)
            == str(order.amount)
        ),
        "beneficiaryAccountConsistent": (
            bool(freeze.payee_account_id)
            and request_object.beneficiary_account_snapshot == freeze.payee_account_id
        ),
        "messageDigestConsistent": (
            request_object.message_preview_hash_snapshot == task.message_preview_hash
            == task.message_preview.payload_hash
        ),
        "simulatedBankInterfaceAvailable": simulated_interface_available is True,
        "bankMessageNotSent": protection_counts()["bankMessageSentCount"] == 0,
    }
    reasons = {
        "requestReadyToDispatch": "REQUEST_NOT_READY",
        "authorizationReadyForExecution": "AUTHORIZATION_NOT_READY",
        "authorizationHashConsistent": "AUTHORIZATION_HASH_CHANGED",
        "requestHashConsistent": "REQUEST_HASH_CHANGED",
        "paymentAmountConsistent": "PAYMENT_AMOUNT_CHANGED",
        "beneficiaryAccountConsistent": "BENEFICIARY_ACCOUNT_CHANGED",
        "messageDigestConsistent": "MESSAGE_DIGEST_CHANGED",
        "simulatedBankInterfaceAvailable": "SIMULATED_INTERFACE_UNAVAILABLE",
        "bankMessageNotSent": "BANK_MESSAGE_ALREADY_SENT",
    }
    failures = [reasons[key] for key, passed in checks.items() if not passed]
    return {
        **checks,
        "eligible": not failures,
        "failureCodes": failures,
        "serverDerived": True,
        "factSource": "server",
    }


def _audit_reference(simulation_no, action_code):
    return f"BankSendExecutionSimulationAudit:{simulation_no}:{action_code}"


def _append_audit(obj, action_code, operator, reason):
    events = [*obj.audit_events, {
        "actionCode": action_code,
        "operator": operator.get_username(),
        "reason": reason,
        "auditReference": _audit_reference(
            getattr(obj, "simulation_no", getattr(obj, "recovery_no", "")),
            action_code,
        ),
    }]
    obj.audit_events = events
    obj.save(update_fields=["audit_events", "updated_at"])
    return events[-1]["auditReference"]


def _transition(obj, *, object_type, source, target, action, operator, reason, allowed):
    audit_reference = _append_audit(obj, action, operator, reason)
    transition_business_object(
        business_object=obj, object_type=object_type,
        source_state=source, target_state=target, action_code=action,
        operator=operator, reason=reason, audit_reference=audit_reference,
        allowed_transitions=allowed,
        status_field="recovery_status" if object_type == RECOVERY_OBJECT_TYPE else "status",
    )


def _assert_feature_enabled(request_object):
    if not getattr(settings, "PCE_BANK_SEND_SIMULATION_FEATURE_ENABLED", False):
        raise ReconciliationError("BSES_FEATURE_DISABLED", "Simulation is disabled", 403)
    trusted = getattr(settings, "PCE_BANK_SEND_SIMULATION_TEST_TENANTS", set())
    if request_object.tenant_id not in trusted:
        raise ReconciliationError(
            "BSES_PRODUCTION_DISABLED",
            "Simulation is limited to isolated test tenants",
            403,
        )


def create_execution_simulation(
    *, user, request_object, idempotency_key, execution_version=EXECUTION_VERSION,
    simulate_failure=False,
):
    _assert_feature_enabled(request_object)
    key = str(idempotency_key or "").strip()
    if not key:
        raise ReconciliationError("BSES_IDEMPOTENCY_REQUIRED", "Idempotency key required", 400)
    existing = BankSendExecutionSimulation.objects.filter(
        source_request=request_object, execution_version=execution_version
    ).first()
    if existing:
        from .isolation import ensure_simulation_audits
        ensure_simulation_audits(existing)
        return {"created": False, "classification": "existing_result", "data": serialize_simulation(existing)}
    with transaction.atomic():
        locked = BankSendRequest.objects.select_for_update().select_related(
            "source_gate__source_task__source_preparation__source_formal_payment_order__execution_freeze",
            "source_gate__source_task__source_preparation",
            "source_gate__source_task__message_preview",
        ).get(pk=request_object.pk)
        existing = BankSendExecutionSimulation.objects.filter(
            source_request=locked, execution_version=execution_version
        ).first()
        if existing:
            from .isolation import ensure_simulation_audits
            ensure_simulation_audits(existing)
            return {"created": False, "classification": "existing_result", "data": serialize_simulation(existing)}
        checks = evaluate_simulation_checks(
            locked, simulated_interface_available=not simulate_failure
        )
        simulation_no = f"BSES-{locked.request_no}-V{execution_version}"
        obj = create_business_object_with_initial_state(
            model=BankSendExecutionSimulation, initial_state="created",
            simulation_no=simulation_no, tenant_id=locked.tenant_id,
            batch_id=locked.batch_id, source_request=locked,
            bank_send_request_no=locked.request_no,
            bank_send_execution_gate_no=locked.bank_send_execution_gate_no,
            execution_version=execution_version,
            execution_simulation_idempotency_key=key,
            checks=checks, result={}, created_by=user,
            audit_events=[],
        )
        _transition(
            obj, object_type=SIMULATION_OBJECT_TYPE, source="created",
            target="validated", action="validate-bank-send-execution-simulation",
            operator=user, reason="server_simulation_inputs_validated",
            allowed=SIMULATION_TRANSITIONS,
        )
        _transition(
            obj, object_type=SIMULATION_OBJECT_TYPE, source="validated",
            target="simulation_running", action="run-bank-send-execution-simulation",
            operator=user, reason="isolated_simulation_started_without_external_io",
            allowed=SIMULATION_TRANSITIONS,
        )
        if checks["eligible"]:
            obj.result = {
                "outcome": "simulation_success",
                "bankMessageSent": False,
                "paymentExecuted": False,
                "fundsDebited": False,
                "bankTransactionCreated": False,
            }
            obj.save(update_fields=["result", "updated_at"])
            _transition(
                obj, object_type=SIMULATION_OBJECT_TYPE,
                source="simulation_running", target="simulation_success",
                action="complete-bank-send-execution-simulation",
                operator=user, reason="simulation_completed_without_external_send",
                allowed=SIMULATION_TRANSITIONS,
            )
        else:
            obj.failure_code = checks["failureCodes"][0]
            obj.failure_reason = "模拟检查未通过，未发生任何外部发送或付款执行。"
            obj.result = {"outcome": "simulation_failed", **protection_counts()}
            obj.save(update_fields=["failure_code", "failure_reason", "result", "updated_at"])
            _transition(
                obj, object_type=SIMULATION_OBJECT_TYPE,
                source="simulation_running", target="simulation_failed",
                action="fail-bank-send-execution-simulation",
                operator=user, reason=obj.failure_code,
                allowed=SIMULATION_TRANSITIONS,
            )
            create_business_object_with_initial_state(
                model=BankSendExecutionRecovery, initial_state="pending",
                recovery_no=f"BSER-{simulation_no}", simulation=obj,
                failure_code=obj.failure_code, failure_reason=obj.failure_reason,
                resolution_note="", audit_events=[],
            )
    from .isolation import ensure_simulation_audits
    ensure_simulation_audits(obj)
    return {
        "created": True, "classification": "created",
        "data": serialize_simulation(
            BankSendExecutionSimulation.objects.get(pk=obj.pk)
        ),
    }


def resolve_execution_recovery(*, user, recovery, resolution_note):
    with transaction.atomic():
        locked = BankSendExecutionRecovery.objects.select_for_update().get(pk=recovery.pk)
        if locked.recovery_status == "resolved":
            return serialize_recovery(locked)
        locked.resolution_note = str(resolution_note or "").strip() or "模拟环境问题已人工确认"
        locked.resolved_by = user
        locked.save(update_fields=["resolution_note", "resolved_by", "updated_at"])
        _transition(
            locked, object_type=RECOVERY_OBJECT_TYPE, source="pending",
            target="resolved", action="resolve-bank-send-execution-recovery",
            operator=user, reason="manual_recovery_record_resolved_without_retry",
            allowed=RECOVERY_TRANSITIONS,
        )
    resolved = BankSendExecutionRecovery.objects.get(pk=locked.pk)
    from .isolation import ensure_simulation_audits
    ensure_simulation_audits(resolved.simulation)
    return serialize_recovery(resolved)


def _transition_facts(obj, object_type):
    facts = business_state_transition_facts(
        business_object=obj, object_type=object_type,
        expected_transitions=(
            RECOVERY_EXPECTED_TRANSITIONS
            if object_type == RECOVERY_OBJECT_TYPE
            else SIMULATION_EXPECTED_TRANSITIONS
        ),
        audit_target_type="BankSendExecutionSimulation",
    )
    # V64 simulation audit references are deliberately isolated from the
    # production BusinessActionAuditRecord ledger.  The shared fact helper
    # therefore cannot resolve them as production audit rows, even though the
    # persisted transition chain and the simulation audit ledger agree.  Verify
    # that isolated ledger explicitly instead of reporting a false mismatch.
    current_state = (
        obj.recovery_status if object_type == RECOVERY_OBJECT_TYPE else obj.status
    )
    expected = (
        RECOVERY_EXPECTED_TRANSITIONS
        if object_type == RECOVERY_OBJECT_TYPE
        else SIMULATION_EXPECTED_TRANSITIONS
    ).get(current_state)
    history = facts["statusTransitionHistory"]
    actual = tuple(
        (row["sourceState"], row["targetState"], row["actionCode"])
        for row in history
    )
    audit_events = {
        (row["actionCode"], row["auditReference"])
        for row in obj.audit_events
    }
    consistent = (
        expected is not None
        and actual == tuple(expected)
        and [row["version"] for row in history]
        == list(range(1, len(history) + 1))
        and all(
            bool(row["reason"])
            and (row["actionCode"], row["auditReference"]) in audit_events
            for row in history
        )
    )
    facts["stateMachineConsistent"] = consistent
    return facts


def serialize_recovery(recovery):
    facts = _transition_facts(recovery, RECOVERY_OBJECT_TYPE)
    return {
        "id": recovery.pk, "recoveryNo": recovery.recovery_no,
        "simulationNo": recovery.simulation.simulation_no,
        "failureCode": recovery.failure_code,
        "failureReason": recovery.failure_reason,
        "recoveryStatus": recovery.recovery_status,
        "recoveryStatusLabel": RECOVERY_LABELS[recovery.recovery_status],
        "resolutionNote": recovery.resolution_note,
        "auditEvents": recovery.audit_events,
        **facts,
    }


def serialize_simulation(obj):
    facts = _transition_facts(obj, SIMULATION_OBJECT_TYPE)
    recovery = serialize_recovery(obj.recovery) if hasattr(obj, "recovery") else None
    return {
        "id": obj.pk, "simulationNo": obj.simulation_no,
        "tenantId": obj.tenant_id, "batchId": obj.batch_id,
        "bankSendRequestNo": obj.bank_send_request_no,
        "bankSendExecutionGateNo": obj.bank_send_execution_gate_no,
        "status": obj.status, "statusCode": obj.status,
        "statusLabel": STATUS_LABELS[obj.status],
        "simulationResult": "模拟成功" if obj.status == "simulation_success" else "模拟失败",
        "checks": obj.checks, "result": obj.result,
        "failureCode": obj.failure_code, "failureReason": obj.failure_reason,
        "recovery": recovery, "auditEvents": obj.audit_events,
        "executionSimulationIdempotencyKey": obj.execution_simulation_idempotency_key,
        "currentStateSource": "server", **facts, **protection_counts(),
    }


def simulation_facts(rows, *, api_url, tenant_id, batch_id):
    statuses = [row["status"] for row in rows]
    facts = {
        "factType": "BankSendExecutionSimulationFacts",
        "factSource": "server", "currentStateSource": "server",
        "simulationCount": len(rows),
        "createdCount": statuses.count("created"),
        "validatedCount": statuses.count("validated"),
        "runningCount": statuses.count("simulation_running"),
        "successCount": statuses.count("simulation_success"),
        "failedCount": statuses.count("simulation_failed"),
        "simulationWriteCount": len(rows),
        "bankMessageSendWriteCount": 0,
        "paymentExecutionWriteCount": 0,
        "businessProgressWriteCount": 0,
        **protection_counts(),
    }
    return {
        **facts,
        **build_fact_load_facts(
            fact_load_status="success", api_url=api_url, http_status=200,
            tenant_id=tenant_id, batch_id=batch_id,
        ),
    }


def simulation_state_guard(obj):
    facts = _transition_facts(obj, SIMULATION_OBJECT_TYPE)
    history = facts["statusTransitionHistory"]
    checks = {
        "unifiedStateService": all(row["objectType"] == SIMULATION_OBJECT_TYPE for row in history),
        "noSkippedState": all(
            (row["sourceState"], row["targetState"]) in SIMULATION_TRANSITIONS
            for row in history
        ),
        "historyLengthMatchesCount": len(history) == facts["statusTransitionCount"],
        "auditReferenceComplete": all(bool(row["auditReference"]) for row in history),
        "sentStateAbsent": all(row["targetState"] not in {"sent", "executed"} for row in history),
    }
    return {"guardCode": "bank_send_execution_simulation_state_guard", **checks, "passed": all(checks.values())}
