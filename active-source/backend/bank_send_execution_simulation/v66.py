from django.conf import settings
from django.db import transaction
from django.utils import timezone

from workflow_runtime.fact_loads import build_fact_load_facts
from workflow_runtime.facts import business_state_transition_facts
from workflow_runtime.models import UserOrganizationRoleAuthority
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .isolation import (
    evaluate_isolation_checks,
    protection_counts as v65_protection_counts,
)
from .models import (
    BankSendChainTrace,
    BankSendExecutionSimulation,
    BankSendFinalApproval,
    BankSendFinalApprovalDecision,
    BankSendProductionIsolationGate,
    BankSendSimulationAudit,
)


VERSION = "V1.14.2.8.4.7.66"
TRACE_MODULE_CODE = "bank-send-chain-trace"
APPROVAL_MODULE_CODE = "bank-send-final-approval"
APPROVAL_OBJECT_TYPE = "bank_send_final_approval"
BUSINESS_REVIEWER_ROLE = "bank_send_business_reviewer"
FUND_OWNER_ROLE = "bank_send_fund_owner"
APPROVAL_TRANSITIONS = (
    ("pending", "first_approved"),
    ("first_approved", "second_approved"),
    ("second_approved", "final_locked"),
)
APPROVAL_EXPECTED_TRANSITIONS = {
    "pending": (),
    "first_approved": (
        ("pending", "first_approved", "submit-bank-send-first-approval"),
    ),
    "second_approved": (
        ("pending", "first_approved", "submit-bank-send-first-approval"),
        (
            "first_approved",
            "second_approved",
            "submit-bank-send-second-approval",
        ),
    ),
    "final_locked": (
        ("pending", "first_approved", "submit-bank-send-first-approval"),
        (
            "first_approved",
            "second_approved",
            "submit-bank-send-second-approval",
        ),
        (
            "second_approved",
            "final_locked",
            "lock-bank-send-final-approval",
        ),
    ),
}
APPROVAL_STATUS_LABELS = {
    "pending": "待审批",
    "first_approved": "第一审批通过",
    "second_approved": "第二审批通过",
    "final_locked": "最终审批已锁定",
}


def protection_counts():
    base = v65_protection_counts()
    return {
        **base,
        "chainTraceWriteCount": BankSendChainTrace.objects.count(),
        "finalApprovalWriteCount": BankSendFinalApproval.objects.count(),
        "financialImpactWriteCount": 0,
    }


def _audit_for_trace(simulation):
    preferred = (
        "simulation_completed"
        if simulation.status == "simulation_success"
        else "simulation_recovered"
    )
    return (
        simulation.independent_audits.filter(audit_type=preferred).first()
        or simulation.independent_audits.order_by("-occurred_at", "-pk").first()
    )


def _node_snapshot(simulation, isolation_gate, audit):
    request = simulation.source_request
    execution_gate = request.source_gate
    task = execution_gate.source_task
    preparation = task.source_preparation
    order = preparation.source_formal_payment_order
    return [
        {
            "order": 1,
            "nodeType": "FormalPaymentOrder",
            "nodeLabel": "正式付款单",
            "businessNo": order.order_no,
            "status": order.status,
            "source": "server",
        },
        {
            "order": 2,
            "nodeType": "BankSendPreparation",
            "nodeLabel": "银行发送准备",
            "businessNo": preparation.prepare_no,
            "status": preparation.status,
            "source": "server",
        },
        {
            "order": 3,
            "nodeType": "BankSendTask",
            "nodeLabel": "银行发送任务",
            "businessNo": task.task_no,
            "status": task.status,
            "source": "server",
        },
        {
            "order": 4,
            "nodeType": "BankSendExecutionGate",
            "nodeLabel": "执行授权",
            "businessNo": execution_gate.gate_no,
            "status": execution_gate.status,
            "source": "server",
        },
        {
            "order": 5,
            "nodeType": "BankSendRequest",
            "nodeLabel": "发送请求",
            "businessNo": request.request_no,
            "status": request.status,
            "source": "server",
        },
        {
            "order": 6,
            "nodeType": "BankSendExecutionSimulation",
            "nodeLabel": "执行模拟",
            "businessNo": simulation.simulation_no,
            "status": simulation.status,
            "source": "server",
        },
        {
            "order": 7,
            "nodeType": "BankSendSimulationAudit",
            "nodeLabel": "模拟审计",
            "businessNo": audit.audit_no if audit else "",
            "status": audit.audit_type if audit else "missing",
            "source": "server",
        },
        {
            "order": 8,
            "nodeType": "BankSendProductionIsolationGate",
            "nodeLabel": "生产隔离",
            "businessNo": isolation_gate.gate_no if isolation_gate else "",
            "status": isolation_gate.status if isolation_gate else "missing",
            "source": "server",
        },
    ]


def build_chain_trace(*, simulation, user):
    isolation_gate = BankSendProductionIsolationGate.objects.filter(
        tenant_id=simulation.tenant_id,
        batch_id=simulation.batch_id,
    ).first()
    audit = _audit_for_trace(simulation)
    if not isolation_gate or not audit:
        raise ValueError("Bank send chain trace is incomplete")
    nodes = _node_snapshot(simulation, isolation_gate, audit)
    trace_complete = (
        len(nodes) == 8
        and [row["order"] for row in nodes] == list(range(1, 9))
        and all(row["businessNo"] and row["source"] == "server" for row in nodes)
    )
    if not trace_complete:
        raise ValueError("Bank send chain trace node validation failed")
    request = simulation.source_request
    execution_gate = request.source_gate
    task = execution_gate.source_task
    preparation = task.source_preparation
    with transaction.atomic():
        trace, _ = BankSendChainTrace.objects.get_or_create(
            source_simulation=simulation,
            defaults={
                "trace_no": f"BSCT-{simulation.simulation_no}",
                "tenant_id": simulation.tenant_id,
                "batch_id": simulation.batch_id,
                "isolation_gate": isolation_gate,
                "formal_payment_order_no": task.source_formal_payment_order_no,
                "bank_send_preparation_no": preparation.prepare_no,
                "bank_send_task_no": task.task_no,
                "bank_send_execution_gate_no": execution_gate.gate_no,
                "bank_send_request_no": request.request_no,
                "simulation_no": simulation.simulation_no,
                "simulation_audit_no": audit.audit_no,
                "isolation_gate_no": isolation_gate.gate_no,
                "trace_complete": True,
                "trace_source": "server",
                "node_snapshot": nodes,
                "created_by": user,
            },
        )
    return trace


def ensure_chain_traces(*, user, queryset=None):
    simulations = queryset or BankSendExecutionSimulation.objects.all()
    return [build_chain_trace(simulation=row, user=user) for row in simulations]


def evaluate_final_checks(trace):
    simulation = trace.source_simulation
    request = simulation.source_request
    execution_gate = request.source_gate
    audits = simulation.independent_audits.all()
    audit_types = set(audits.values_list("audit_type", flat=True))
    isolation_gate = trace.isolation_gate
    protection = protection_counts()
    checks = {
        "FINAL-001": bool(request.pk),
        "FINAL-002": (
            bool(execution_gate.pk)
            and execution_gate.status == "ready_for_execution"
        ),
        "FINAL-003": simulation.status == "simulation_success",
        "FINAL-004": {
            "simulation_created",
            "simulation_validated",
            "simulation_started",
            "simulation_completed",
        }.issubset(audit_types)
        and all(
            row.operator_id and row.reason and row.audit_reference
            for row in audits
        ),
        "FINAL-005": (
            isolation_gate.status == "isolated"
            and evaluate_isolation_checks()["passed"] is True
        ),
        "FINAL-006": isolation_gate.production_connection_enabled is False,
        "FINAL-007": isolation_gate.production_secret_available is False,
        "FINAL-008": (
            request.status == "ready_to_dispatch"
            and protection["bankMessageSendWriteCount"] == 0
            and protection["paymentExecutionWriteCount"] == 0
            and protection["businessProgressWriteCount"] == 0
        ),
    }
    return {**checks, "passed": all(checks.values()), "factSource": "server"}


def create_final_approval(*, trace, user):
    checks = evaluate_final_checks(trace)
    if not trace.trace_complete or not checks["passed"]:
        raise ValueError("Final approval checks failed")
    with transaction.atomic():
        existing = BankSendFinalApproval.objects.select_for_update().filter(
            trace=trace
        ).first()
        if existing:
            return existing
        return create_business_object_with_initial_state(
            model=BankSendFinalApproval,
            initial_state="pending",
            approval_no=f"BSFA-{trace.trace_no}",
            trace=trace,
            trace_no=trace.trace_no,
            request_no=trace.bank_send_request_no,
            tenant_id=trace.tenant_id,
            batch_id=trace.batch_id,
            checks=checks,
            audit_events=[],
            created_by=user,
        )


def _request_legal_entity(approval):
    return approval.trace.source_simulation.source_request.legal_entity_id


def _has_role(user, approval, role):
    return UserOrganizationRoleAuthority.objects.filter(
        user=user,
        role_code=role,
        legal_entity_id=_request_legal_entity(approval),
        active=True,
    ).exists()


def _append_approval_audit(approval, action_code, user, role, reason):
    reference = (
        f"BankSendFinalApprovalAudit:{approval.approval_no}:{action_code}"
    )
    approval.audit_events = [
        *approval.audit_events,
        {
            "actionCode": action_code,
            "operator": user.get_username(),
            "role": role,
            "timestamp": timezone.now().isoformat(),
            "reason": reason,
            "auditReference": reference,
        },
    ]
    approval.save(update_fields=["audit_events", "updated_at"])
    return reference


def _transition_approval(
    approval,
    source,
    target,
    action_code,
    user,
    role,
    reason,
):
    reference = _append_approval_audit(
        approval, action_code, user, role, reason
    )
    transition_business_object(
        business_object=approval,
        object_type=APPROVAL_OBJECT_TYPE,
        source_state=source,
        target_state=target,
        action_code=action_code,
        operator=user,
        reason=reason,
        audit_reference=reference,
        allowed_transitions=APPROVAL_TRANSITIONS,
    )
    return reference


def submit_first_approval(*, approval, user, reason):
    if approval.status != "pending":
        raise ValueError("First approval requires pending status")
    if not _has_role(user, approval, BUSINESS_REVIEWER_ROLE):
        raise PermissionError("Business reviewer role required")
    if not evaluate_final_checks(approval.trace)["passed"]:
        raise ValueError("Final approval checks no longer pass")
    with transaction.atomic():
        reference = _transition_approval(
            approval,
            "pending",
            "first_approved",
            "submit-bank-send-first-approval",
            user,
            BUSINESS_REVIEWER_ROLE,
            reason,
        )
        BankSendFinalApprovalDecision.objects.create(
            approval=approval,
            stage="first",
            operator=user,
            role=BUSINESS_REVIEWER_ROLE,
            occurred_at=timezone.now(),
            reason=reason,
            audit_reference=reference,
        )
    return BankSendFinalApproval.objects.get(pk=approval.pk)


def submit_second_approval(*, approval, user, reason):
    if approval.status != "first_approved":
        raise ValueError("Second approval requires first_approved status")
    first = approval.decisions.filter(stage="first").first()
    if not first or first.operator_id == user.pk:
        raise PermissionError("Two independent approval users are required")
    if not _has_role(user, approval, FUND_OWNER_ROLE):
        raise PermissionError("Fund owner role required")
    if first.role == FUND_OWNER_ROLE:
        raise PermissionError("Approval roles must differ")
    if not evaluate_final_checks(approval.trace)["passed"]:
        raise ValueError("Final approval checks no longer pass")
    with transaction.atomic():
        second_reference = _transition_approval(
            approval,
            "first_approved",
            "second_approved",
            "submit-bank-send-second-approval",
            user,
            FUND_OWNER_ROLE,
            reason,
        )
        BankSendFinalApprovalDecision.objects.create(
            approval=approval,
            stage="second",
            operator=user,
            role=FUND_OWNER_ROLE,
            occurred_at=timezone.now(),
            reason=reason,
            audit_reference=second_reference,
        )
        _transition_approval(
            approval,
            "second_approved",
            "final_locked",
            "lock-bank-send-final-approval",
            user,
            FUND_OWNER_ROLE,
            "dual_role_approval_completed_and_send_remains_forbidden",
        )
    return BankSendFinalApproval.objects.get(pk=approval.pk)


def _approval_transition_facts(approval):
    facts = business_state_transition_facts(
        business_object=approval,
        object_type=APPROVAL_OBJECT_TYPE,
        expected_transitions=APPROVAL_EXPECTED_TRANSITIONS,
        audit_target_type="BankSendFinalApproval",
    )
    history = facts["statusTransitionHistory"]
    actual = tuple(
        (row["sourceState"], row["targetState"], row["actionCode"])
        for row in history
    )
    expected = APPROVAL_EXPECTED_TRANSITIONS.get(approval.status)
    references = {
        (row["actionCode"], row["auditReference"])
        for row in approval.audit_events
    }
    facts["stateMachineConsistent"] = (
        expected is not None
        and actual == tuple(expected)
        and [row["version"] for row in history]
        == list(range(1, len(history) + 1))
        and all(
            row["reason"]
            and (row["actionCode"], row["auditReference"]) in references
            for row in history
        )
    )
    return facts


def serialize_trace(trace):
    return {
        "id": trace.pk,
        "traceNo": trace.trace_no,
        "tenantId": trace.tenant_id,
        "batchId": trace.batch_id,
        "formalPaymentOrderNo": trace.formal_payment_order_no,
        "bankSendPreparationNo": trace.bank_send_preparation_no,
        "bankSendTaskNo": trace.bank_send_task_no,
        "bankSendExecutionGateNo": trace.bank_send_execution_gate_no,
        "bankSendRequestNo": trace.bank_send_request_no,
        "simulationNo": trace.simulation_no,
        "simulationAuditNo": trace.simulation_audit_no,
        "isolationGateNo": trace.isolation_gate_no,
        "traceComplete": trace.trace_complete,
        "traceSource": trace.trace_source,
        "nodeCount": len(trace.node_snapshot),
        "missingNodeCount": sum(
            not row.get("businessNo") for row in trace.node_snapshot
        ),
        "nodes": trace.node_snapshot,
        "realBankSend": False,
        "paymentExecution": False,
        "fundsDebited": False,
    }


def serialize_decision(decision):
    return {
        "stage": decision.stage,
        "operator": decision.operator.get_username(),
        "role": decision.role,
        "timestamp": decision.occurred_at.isoformat(),
        "reason": decision.reason,
        "auditReference": decision.audit_reference,
    }


def serialize_approval(approval):
    decisions = [
        serialize_decision(row)
        for row in approval.decisions.select_related("operator").order_by("pk")
    ]
    return {
        "id": approval.pk,
        "approvalNo": approval.approval_no,
        "traceNo": approval.trace_no,
        "requestNo": approval.request_no,
        "tenantId": approval.tenant_id,
        "batchId": approval.batch_id,
        "status": approval.status,
        "statusCode": approval.status,
        "statusLabel": APPROVAL_STATUS_LABELS[approval.status],
        "checks": approval.checks,
        "firstApproval": next(
            (row for row in decisions if row["stage"] == "first"), None
        ),
        "secondApproval": next(
            (row for row in decisions if row["stage"] == "second"), None
        ),
        "decisions": decisions,
        "finalApprovalMeansSent": False,
        "bankSent": False,
        **_approval_transition_facts(approval),
    }


def _base_facts(*, fact_type, api_url, tenant_id, batch_id, record_count):
    return {
        "factType": fact_type,
        "factSource": "server",
        "recordCount": record_count,
        **protection_counts(),
        **build_fact_load_facts(
            fact_load_status="success",
            api_url=api_url,
            http_status=200,
            tenant_id=tenant_id,
            batch_id=batch_id,
        ),
    }


def chain_trace_facts(rows, *, tenant_id, batch_id):
    base = _base_facts(
        fact_type="BankSendChainTraceFacts",
        api_url="/api/finance/bank-send-chain-traces/",
        tenant_id=tenant_id,
        batch_id=batch_id,
        record_count=len(rows),
    )
    return {
        **base,
        "traceCount": len(rows),
        "completeTraceCount": sum(row["traceComplete"] for row in rows),
        "nodeCount": max((row["nodeCount"] for row in rows), default=0),
        "missingNodeCount": sum(row["missingNodeCount"] for row in rows),
        "realBankSendCount": 0,
        "paymentExecutionCount": 0,
        "fundsDebitCount": 0,
    }


def final_approval_facts(rows, *, tenant_id, batch_id):
    base = _base_facts(
        fact_type="BankSendFinalApprovalFacts",
        api_url="/api/finance/bank-send-final-approvals/",
        tenant_id=tenant_id,
        batch_id=batch_id,
        record_count=len(rows),
    )
    return {
        **base,
        "approvalCount": len(rows),
        "pendingCount": sum(row["status"] == "pending" for row in rows),
        "firstApprovedCount": sum(
            row["status"] == "first_approved" for row in rows
        ),
        "secondApprovedCount": sum(
            row["status"] == "second_approved" for row in rows
        ),
        "finalLockedCount": sum(
            row["status"] == "final_locked" for row in rows
        ),
        "dualPersonApprovalCount": sum(
            bool(row["firstApproval"] and row["secondApproval"])
            and row["firstApproval"]["operator"]
            != row["secondApproval"]["operator"]
            and row["firstApproval"]["role"] != row["secondApproval"]["role"]
            for row in rows
        ),
        "bankSentCount": 0,
        "paymentExecutionCount": 0,
    }
