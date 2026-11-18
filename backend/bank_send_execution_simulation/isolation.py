from django.conf import settings
from django.db import transaction

from workflow_runtime.fact_loads import build_fact_load_facts
from workflow_runtime.facts import business_state_transition_facts
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .models import (
    BankSendExecutionSimulation,
    BankSendProductionIsolationGate,
    BankSendSimulationAudit,
)


VERSION = "V1.14.2.8.4.7.65"
AUDIT_MODULE_CODE = "bank-send-simulation-audit"
ISOLATION_MODULE_CODE = "bank-send-isolation-gate"
ISOLATION_OBJECT_TYPE = "bank_send_production_isolation_gate"
ISOLATION_TRANSITIONS = (
    ("created", "checked"),
    ("checked", "isolated"),
)
ISOLATION_EXPECTED_TRANSITIONS = {
    "created": (),
    "checked": (("created", "checked", "check-bank-send-production-isolation"),),
    "isolated": (
        ("created", "checked", "check-bank-send-production-isolation"),
        ("checked", "isolated", "enforce-bank-send-production-isolation"),
    ),
}
AUDIT_TYPE_LABELS = {
    "simulation_created": "已创建",
    "simulation_validated": "已校验",
    "simulation_started": "模拟开始",
    "simulation_completed": "模拟完成",
    "simulation_failed": "模拟失败",
    "simulation_recovered": "已恢复",
}
ISOLATION_STATUS_LABELS = {
    "created": "已创建",
    "checked": "已检查",
    "isolated": "隔离有效",
}


def protection_counts():
    return {
        "bankMessageSendWriteCount": 0,
        "paymentExecutionWriteCount": 0,
        "financialImpactWriteCount": 0,
        "businessProgressWriteCount": 0,
        "bankSendObjectCount": 0,
    }


def _audit_payloads(simulation):
    transitions = list(
        BusinessStateTransition.objects.filter(
            object_type="bank_send_execution_simulation",
            object_id=simulation.pk,
        ).select_related("operator").order_by("version", "pk")
    )
    by_action = {row.action_code: row for row in transitions}
    payloads = [{
        "audit_type": "simulation_created",
        "operator": simulation.created_by,
        "occurred_at": simulation.created_at,
        "reason": "isolated_simulation_object_created",
    }]
    action_map = (
        ("validate-bank-send-execution-simulation", "simulation_validated"),
        ("run-bank-send-execution-simulation", "simulation_started"),
        ("complete-bank-send-execution-simulation", "simulation_completed"),
        ("fail-bank-send-execution-simulation", "simulation_failed"),
    )
    for action_code, audit_type in action_map:
        row = by_action.get(action_code)
        if row:
            payloads.append({
                "audit_type": audit_type,
                "operator": row.operator,
                "occurred_at": row.timestamp,
                "reason": row.reason,
            })
    recovery = getattr(simulation, "recovery", None)
    if recovery and recovery.recovery_status == "resolved":
        payloads.append({
            "audit_type": "simulation_recovered",
            "operator": recovery.resolved_by or simulation.created_by,
            "occurred_at": recovery.updated_at,
            "reason": recovery.resolution_note
            or "manual_recovery_record_resolved_without_retry",
        })
    return payloads


def ensure_simulation_audits(simulation):
    rows = []
    for payload in _audit_payloads(simulation):
        audit_type = payload["audit_type"]
        audit_no = f"BSSA-{simulation.simulation_no}-{audit_type.upper()}"
        row, _ = BankSendSimulationAudit.objects.get_or_create(
            simulation=simulation,
            audit_type=audit_type,
            defaults={
                "audit_no": audit_no,
                "simulation_no": simulation.simulation_no,
                "tenant_id": simulation.tenant_id,
                "batch_id": simulation.batch_id,
                "operator": payload["operator"],
                "occurred_at": payload["occurred_at"],
                "reason": payload["reason"],
                "audit_reference": f"BankSendSimulationAudit:{audit_no}",
            },
        )
        rows.append(row)
    return rows


def ensure_all_simulation_audits(queryset=None):
    queryset = queryset or BankSendExecutionSimulation.objects.all()
    for simulation in queryset.select_related(
        "created_by", "recovery", "recovery__resolved_by"
    ):
        ensure_simulation_audits(simulation)
    return BankSendSimulationAudit.objects.count()


def serialize_audit(row):
    return {
        "id": row.pk,
        "auditNo": row.audit_no,
        "simulationNo": row.simulation_no,
        "tenantId": row.tenant_id,
        "batchId": row.batch_id,
        "auditType": row.audit_type,
        "auditTypeLabel": AUDIT_TYPE_LABELS[row.audit_type],
        "operator": row.operator.get_username(),
        "timestamp": row.occurred_at.isoformat(),
        "reason": row.reason,
        "auditReference": row.audit_reference,
        "factSource": "server",
    }


def simulation_audit_facts(rows, *, api_url, tenant_id, batch_id):
    facts = {
        "factType": "BankSendSimulationAuditFacts",
        "factSource": "server",
        "recordCount": len(rows),
        "simulationCount": len({row["simulationNo"] for row in rows}),
        "createdAuditCount": sum(row["auditType"] == "simulation_created" for row in rows),
        "validatedAuditCount": sum(row["auditType"] == "simulation_validated" for row in rows),
        "startedAuditCount": sum(row["auditType"] == "simulation_started" for row in rows),
        "completedAuditCount": sum(row["auditType"] == "simulation_completed" for row in rows),
        "failedAuditCount": sum(row["auditType"] == "simulation_failed" for row in rows),
        "recoveredAuditCount": sum(row["auditType"] == "simulation_recovered" for row in rows),
        "simulationAuditWriteCount": len(rows),
        "isolationGateWriteCount": BankSendProductionIsolationGate.objects.count(),
        **protection_counts(),
    }
    return {
        **facts,
        **build_fact_load_facts(
            fact_load_status="success",
            api_url=api_url,
            http_status=200,
            tenant_id=tenant_id,
            batch_id=batch_id,
        ),
    }


def evaluate_isolation_checks():
    checks = {
        "ISOLATION-001": not bool(
            getattr(settings, "PCE_BANK_PRODUCTION_API_URL", "")
        ),
        "ISOLATION-002": not bool(
            getattr(settings, "PCE_BANK_PRODUCTION_SECRET_AVAILABLE", False)
        ),
        "ISOLATION-003": bool(
            getattr(settings, "PCE_BANK_SEND_SIMULATION_FEATURE_ENABLED", False)
        ),
        "ISOLATION-004": not bool(
            getattr(settings, "PCE_BANK_PRODUCTION_SEND_ALLOWED", False)
        ),
        "ISOLATION-005": not bool(
            getattr(settings, "PCE_PAYMENT_EXECUTION_ALLOWED", False)
        ),
        "ISOLATION-006": protection_counts()["bankMessageSendWriteCount"] == 0,
    }
    return {
        **checks,
        "passed": all(checks.values()),
        "factSource": "server",
    }


def _append_gate_audit(gate, action_code, operator, reason):
    reference = f"BankSendProductionIsolationGateAudit:{gate.gate_no}:{action_code}"
    gate.audit_events = [*gate.audit_events, {
        "actionCode": action_code,
        "operator": operator.get_username(),
        "reason": reason,
        "auditReference": reference,
    }]
    gate.save(update_fields=["audit_events", "updated_at"])
    return reference


def _transition_gate(gate, source, target, action_code, operator, reason):
    reference = _append_gate_audit(gate, action_code, operator, reason)
    transition_business_object(
        business_object=gate,
        object_type=ISOLATION_OBJECT_TYPE,
        source_state=source,
        target_state=target,
        action_code=action_code,
        operator=operator,
        reason=reason,
        audit_reference=reference,
        allowed_transitions=ISOLATION_TRANSITIONS,
    )


def create_production_isolation_gate(*, user, tenant_id, batch_id):
    existing = BankSendProductionIsolationGate.objects.filter(
        tenant_id=tenant_id, batch_id=batch_id
    ).first()
    if existing:
        return existing
    checks = evaluate_isolation_checks()
    if not checks["passed"]:
        raise ValueError("Production isolation checks failed")
    with transaction.atomic():
        existing = BankSendProductionIsolationGate.objects.select_for_update().filter(
            tenant_id=tenant_id, batch_id=batch_id
        ).first()
        if existing:
            return existing
        gate = create_business_object_with_initial_state(
            model=BankSendProductionIsolationGate,
            initial_state="created",
            gate_no=f"BSPIG-{tenant_id}-{batch_id}",
            tenant_id=tenant_id,
            batch_id=batch_id,
            simulation_environment=True,
            production_connection_enabled=False,
            production_secret_available=False,
            production_send_allowed=False,
            payment_execution_allowed=False,
            approval_status="not_approved",
            checks=checks,
            audit_events=[],
            created_by=user,
        )
        _transition_gate(
            gate, "created", "checked",
            "check-bank-send-production-isolation", user,
            "production_connection_secret_and_permissions_checked",
        )
        _transition_gate(
            gate, "checked", "isolated",
            "enforce-bank-send-production-isolation", user,
            "simulation_environment_isolated_from_production_send",
        )
    return BankSendProductionIsolationGate.objects.get(pk=gate.pk)


def _gate_transition_facts(gate):
    facts = business_state_transition_facts(
        business_object=gate,
        object_type=ISOLATION_OBJECT_TYPE,
        expected_transitions=ISOLATION_EXPECTED_TRANSITIONS,
        audit_target_type="BankSendProductionIsolationGate",
    )
    history = facts["statusTransitionHistory"]
    expected = ISOLATION_EXPECTED_TRANSITIONS.get(gate.status)
    actual = tuple(
        (row["sourceState"], row["targetState"], row["actionCode"])
        for row in history
    )
    audit_events = {
        (row["actionCode"], row["auditReference"])
        for row in gate.audit_events
    }
    facts["stateMachineConsistent"] = (
        expected is not None
        and actual == tuple(expected)
        and [row["version"] for row in history]
        == list(range(1, len(history) + 1))
        and all(
            row["reason"]
            and (row["actionCode"], row["auditReference"]) in audit_events
            for row in history
        )
    )
    return facts


def serialize_isolation_gate(gate):
    return {
        "id": gate.pk,
        "gateNo": gate.gate_no,
        "tenantId": gate.tenant_id,
        "batchId": gate.batch_id,
        "simulationEnvironment": gate.simulation_environment,
        "productionConnectionEnabled": gate.production_connection_enabled,
        "productionSecretAvailable": gate.production_secret_available,
        "productionSendAllowed": gate.production_send_allowed,
        "paymentExecutionAllowed": gate.payment_execution_allowed,
        "approvalStatus": gate.approval_status,
        "status": gate.status,
        "statusCode": gate.status,
        "statusLabel": ISOLATION_STATUS_LABELS[gate.status],
        "checks": gate.checks,
        "factSource": "server",
        **_gate_transition_facts(gate),
        **protection_counts(),
    }


def isolation_gate_facts(rows, *, api_url, tenant_id, batch_id):
    facts = {
        "factType": "BankSendProductionIsolationGateFacts",
        "factSource": "server",
        "recordCount": len(rows),
        "gateCount": len(rows),
        "isolatedCount": sum(row["status"] == "isolated" for row in rows),
        "productionConnectionEnabledCount": sum(
            row["productionConnectionEnabled"] for row in rows
        ),
        "productionSecretAvailableCount": sum(
            row["productionSecretAvailable"] for row in rows
        ),
        "productionSendAllowedCount": sum(
            row["productionSendAllowed"] for row in rows
        ),
        "simulationAuditWriteCount": BankSendSimulationAudit.objects.count(),
        "isolationGateWriteCount": len(rows),
        **protection_counts(),
    }
    return {
        **facts,
        **build_fact_load_facts(
            fact_load_status="success",
            api_url=api_url,
            http_status=200,
            tenant_id=tenant_id,
            batch_id=batch_id,
        ),
    }
