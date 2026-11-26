from dataclasses import asdict, dataclass, field

from payment_risk_review.providers import PaymentOrderDraftRiskEvidenceProvider
from reconciliation.models import BusinessActionAuditRecord
from reconciliation.services import canonical_hash
from workflow_runtime.facts import (
    assert_status_transition_count_matches_history,
    status_transition_facts,
)
from workflow_runtime.models import ApprovalDecision, BusinessStateTransition


EXPECTED_STATE_TRANSITIONS = {
    "prepared": (),
    "submitted": (
        ("prepared", "submitted", "submit-formal-payment-order"),
    ),
    "approved": (
        ("prepared", "submitted", "submit-formal-payment-order"),
        ("submitted", "approved", "approve-formal-payment-order"),
    ),
    "frozen_for_execution": (
        ("prepared", "submitted", "submit-formal-payment-order"),
        ("submitted", "approved", "approve-formal-payment-order"),
        (
            "approved",
            "frozen_for_execution",
            "freeze-formal-payment-order",
        ),
    ),
}


def _masked_reference(value):
    text = str(value or "")
    if not text:
        return ""
    return f"***{text[-4:]}"


def execution_snapshot_payload(order, approval, authority=None):
    authority = authority or PaymentOrderDraftRiskEvidenceProvider().read(
        order.source_risk_review.source_payment_order_draft_id
    )
    bank = (authority or {}).get("bank") or {}
    payer = bank.get("payer") or {}
    payee = bank.get("payee") or {}
    route = bank.get("route") or {}
    return {
        "formalPaymentOrderId": order.pk,
        "formalPaymentOrderNo": order.order_no,
        "amount": str(order.amount),
        "currency": order.currency,
        "payerAccountId": payer.get("bankAccountId", ""),
        "payeeAccountId": payee.get("bankAccountId", ""),
        "bankRoute": route.get("routeId") or route.get("routeCode") or "",
        "executionDate": order.planned_execution_date.isoformat(),
        "riskVersion": order.source_risk_review.review_version,
        "approvalVersion": approval.version,
    }


def execution_snapshot_hash(order, approval, authority=None):
    return canonical_hash(execution_snapshot_payload(order, approval, authority))


@dataclass(frozen=True)
class BankSendEligibility:
    state_machine_passed: bool
    risk_passed: bool
    approval_passed: bool
    freeze_passed: bool
    funds_passed: bool
    bank_passed: bool
    signature_passed: bool
    segregation_passed: bool
    ready_for_bank_send: bool
    blocking_reasons: tuple[str, ...] = field(default_factory=tuple)
    bank_message_count: int = 0
    bank_send_task_count: int = 0
    payment_execution_count: int = 0
    server_derived: bool = True

    def as_dict(self):
        return {
            "stateMachinePassed": self.state_machine_passed,
            "riskPassed": self.risk_passed,
            "approvalPassed": self.approval_passed,
            "freezePassed": self.freeze_passed,
            "fundsPassed": self.funds_passed,
            "bankPassed": self.bank_passed,
            "signaturePassed": self.signature_passed,
            "segregationPassed": self.segregation_passed,
            "readyForBankSend": self.ready_for_bank_send,
            "nextStepReadiness": (
                "ready_for_bank_send" if self.ready_for_bank_send else "blocked"
            ),
            "blockingReasons": list(self.blocking_reasons),
            "bankMessageCount": self.bank_message_count,
            "bankSendTaskCount": self.bank_send_task_count,
            "paymentExecutionCount": self.payment_execution_count,
            "serverDerived": self.server_derived,
        }


@dataclass(frozen=True)
class FormalPaymentOrderExecutionGateFacts:
    business_status: str
    status_transition_history: tuple[dict, ...]
    state_machine_consistent: bool
    approval_status: str
    workflow_instance: dict
    approval_history: tuple[dict, ...]
    freeze_status: str
    freeze_hash: str
    freeze_snapshot: dict
    bank_send_eligibility: BankSendEligibility
    downstream_counts: dict
    current_state_source: str = "server"

    def as_dict(self):
        transition_facts = status_transition_facts(
            history=self.status_transition_history,
            state_machine_consistent=self.state_machine_consistent,
        )
        payload = {
            "status": self.business_status,
            **transition_facts,
            "approvalStatus": self.approval_status,
            "workflowInstance": self.workflow_instance,
            "approvalHistory": list(self.approval_history),
            "freezeStatus": self.freeze_status,
            "freezeHash": self.freeze_hash,
            "freezeSnapshot": self.freeze_snapshot,
            "bankSendEligibility": self.bank_send_eligibility.as_dict(),
            "downstreamCounts": dict(self.downstream_counts),
            "currentStateSource": self.current_state_source,
        }
        return assert_status_transition_count_matches_history(payload)


def _approval_history(order, workflow):
    if not workflow:
        return []
    decisions = (
        ApprovalDecision.objects.filter(task__workflow_instance=workflow)
        .select_related("actor", "task")
        .order_by("task__step_no", "decision_sequence", "created_at")
    )
    return [
        {
            "stepNo": row.task.step_no,
            "taskNo": row.task.task_no,
            "roleCode": row.task.required_role_code,
            "decision": row.decision,
            "actorId": row.actor_id,
            "actorName": row.actor.get_username(),
            "createdAt": row.created_at.isoformat(),
        }
        for row in decisions
    ]


def _status_transition_history(order):
    transitions = BusinessStateTransition.objects.filter(
        object_type="formal_payment_order",
        object_id=order.pk,
    ).select_related("operator", "workflow_instance").order_by(
        "version",
        "timestamp",
    )
    return [
        {
            "id": row.pk,
            "objectType": row.object_type,
            "objectId": row.object_id,
            "sourceState": row.source_state,
            "targetState": row.target_state,
            "operator": {
                "id": row.operator_id,
                "name": row.operator.get_username(),
            },
            "timestamp": row.timestamp.isoformat(),
            "reason": row.reason,
            "version": row.version,
            "auditReference": row.audit_reference,
            "actionCode": row.action_code,
            "workflowInstanceId": row.workflow_instance_id,
            # V54.1 compatibility aliases; V54.2 consistency uses canonical fields above.
            "businessType": row.object_type,
            "businessObjectId": row.object_id,
            "fromStatus": row.source_state,
            "toStatus": row.target_state,
            "operatorId": row.operator_id,
            "operatorName": row.operator.get_username(),
            "transitionVersion": row.version,
            "createdAt": row.timestamp.isoformat(),
        }
        for row in transitions
    ]


def _state_machine_consistent(order, approval, workflow, freeze, history, decisions):
    expected = EXPECTED_STATE_TRANSITIONS.get(order.status)
    actual = tuple(
        (row["fromStatus"], row["toStatus"], row["actionCode"])
        for row in history
    )
    if expected is None or actual != expected:
        return False
    if [row["transitionVersion"] for row in history] != list(
        range(1, len(history) + 1)
    ):
        return False
    if any(
        not row["reason"]
        or not row["auditReference"].startswith("BusinessActionAuditRecord:")
        for row in history
    ):
        return False
    try:
        audit_ids = [
            int(row["auditReference"].rsplit(":", 1)[1])
            for row in history
        ]
    except (IndexError, TypeError, ValueError):
        return False
    audits = {
        row.pk: row
        for row in BusinessActionAuditRecord.objects.filter(pk__in=audit_ids)
    }
    if len(audits) != len(history):
        return False
    if any(
        (
            audits[audit_id].target_type != "formalPaymentOrder"
            or audits[audit_id].target_id != order.pk
            or audits[audit_id].action_code != history[index]["actionCode"]
            or audits[audit_id].result != "committed"
            or audits[audit_id].actor_id != history[index]["operatorId"]
        )
        for index, audit_id in enumerate(audit_ids)
    ):
        return False
    if any(
        row["workflowInstanceId"] != (workflow.pk if workflow else None)
        for row in history
    ):
        return False
    if order.status == "prepared":
        return not approval and not workflow and not freeze and not decisions
    if order.status == "submitted":
        return bool(
            approval
            and workflow
            and approval.approval_status == "pending"
            and workflow.status == "pending"
            and not freeze
        )
    if order.status == "approved":
        return bool(
            approval
            and workflow
            and approval.approval_status == "approved"
            and workflow.status == "approved"
            and len(decisions) >= 2
            and not freeze
        )
    return bool(
        approval
        and workflow
        and approval.approval_status == "approved"
        and workflow.status == "approved"
        and len(decisions) >= 2
        and freeze
        and freeze.freeze_hash
    )


def build_execution_gate_facts(order, *, overrides=None):
    overrides = overrides or {}
    approval = getattr(order, "approval", None)
    workflow = approval.workflow_instance if approval else None
    freeze = getattr(order, "execution_freeze", None)
    authority = PaymentOrderDraftRiskEvidenceProvider().read(
        order.source_risk_review.source_payment_order_draft_id
    ) or {}
    bank = authority.get("bank") or {}
    funds = authority.get("funds") or {}
    source = authority.get("source") or {}
    risk = order.source_risk_review
    history = _approval_history(order, workflow)
    transition_history = _status_transition_history(order)
    state_machine_passed = _state_machine_consistent(
        order,
        approval,
        workflow,
        freeze,
        transition_history,
        history,
    )

    risk_passed = bool(
        risk.status == "passed"
        and risk.risk_result == "passed"
        and risk.risk_level == "low"
        and risk.review_version == order.source_risk_review_version
        and source.get("version") == risk.source_payment_order_draft.version
    )
    approval_passed = bool(
        approval
        and approval.approval_status == "approved"
        and workflow
        and workflow.status == "approved"
        and len(history) >= 2
    )
    freeze_passed = bool(
        freeze
        and order.status == "frozen_for_execution"
        and approval
        and freeze.approval_version == approval.version
        and freeze.risk_version == risk.review_version
        and freeze.freeze_hash
        == execution_snapshot_hash(order, approval, authority)
    )
    funds_passed = bool(
        funds.get("active")
        and funds.get("sufficient")
        and not funds.get("fundsReservationCreated")
        and not funds.get("bankBalanceDebited")
    )
    payer = bank.get("payer") or {}
    payee = bank.get("payee") or {}
    route = bank.get("route") or {}
    interface = bank.get("interface") or {}
    bank_passed = bool(
        payer.get("active")
        and payer.get("availableForPayment")
        and payee.get("active")
        and payee.get("paymentEnabled")
        and route.get("active")
        and interface.get("active")
        and interface.get("paymentEnabled")
        and interface.get("connectionStatus") == "available"
    )
    signing_policy = bank.get("signingPolicy") or {}
    signing_capability = bank.get("signingCapability") or {}
    authorization_route = bank.get("authorizationRoute") or {}
    signature_passed = bool(
        signing_policy.get("active")
        and signing_policy.get("requiredSignatures", 0) >= 2
        and signing_capability.get("active")
        and signing_capability.get("credentialStatus") == "ready"
        and signing_capability.get("certificateStatus") == "valid"
        and signing_capability.get("signingServiceStatus") == "available"
        and authorization_route.get("active")
        and authorization_route.get("stepCount", 0) >= 2
    )
    actors = [row["actorId"] for row in history if row["decision"] == "approved"]
    roles = [row["roleCode"] for row in history if row["decision"] == "approved"]
    segregation_passed = bool(
        len(actors) >= 2
        and len(set(actors)) == len(actors)
        and order.created_by_id not in actors
        and roles[:2] == ["payment_checker", "payment_authorizer"]
    )

    evaluated = {
        "stateMachinePassed": state_machine_passed,
        "riskPassed": risk_passed,
        "approvalPassed": approval_passed,
        "freezePassed": freeze_passed,
        "fundsPassed": funds_passed,
        "bankPassed": bank_passed,
        "signaturePassed": signature_passed,
        "segregationPassed": segregation_passed,
    }
    evaluated.update(overrides)
    reason_codes = {
        "stateMachinePassed": "STATE_MACHINE_FACTS_INCONSISTENT",
        "riskPassed": "RISK_REVIEW_NOT_PASSED",
        "approvalPassed": "APPROVAL_NOT_PASSED",
        "freezePassed": "FREEZE_NOT_VALID",
        "fundsPassed": "FUNDS_NOT_AVAILABLE",
        "bankPassed": "BANK_CAPABILITY_NOT_AVAILABLE",
        "signaturePassed": "SIGNATURE_CAPABILITY_NOT_AVAILABLE",
        "segregationPassed": "SEGREGATION_NOT_VALID",
    }
    blocking = tuple(
        reason_codes[key] for key, passed in evaluated.items() if not passed
    )
    eligibility = BankSendEligibility(
        state_machine_passed=evaluated["stateMachinePassed"],
        risk_passed=evaluated["riskPassed"],
        approval_passed=evaluated["approvalPassed"],
        freeze_passed=evaluated["freezePassed"],
        funds_passed=evaluated["fundsPassed"],
        bank_passed=evaluated["bankPassed"],
        signature_passed=evaluated["signaturePassed"],
        segregation_passed=evaluated["segregationPassed"],
        ready_for_bank_send=not blocking,
        blocking_reasons=blocking,
    )
    return FormalPaymentOrderExecutionGateFacts(
        business_status=order.status,
        status_transition_history=tuple(transition_history),
        state_machine_consistent=state_machine_passed,
        approval_status=approval.approval_status if approval else "not_started",
        workflow_instance={
            "id": workflow.pk,
            "instanceNo": workflow.instance_no,
            "status": workflow.status,
            "currentStep": workflow.current_step,
            "totalSteps": workflow.total_steps,
            "version": workflow.version,
        }
        if workflow
        else {},
        approval_history=tuple(history),
        freeze_status="frozen" if freeze else "not_frozen",
        freeze_hash=freeze.freeze_hash if freeze else "",
        freeze_snapshot={
            "amount": str(freeze.amount),
            "currency": freeze.currency,
            "payerAccount": _masked_reference(freeze.payer_account_id),
            "payeeAccount": _masked_reference(freeze.payee_account_id),
            "bankRoute": freeze.bank_route,
            "executionDate": freeze.execution_date.isoformat(),
            "riskVersion": freeze.risk_version,
            "approvalVersion": freeze.approval_version,
            "version": freeze.version,
        }
        if freeze
        else {},
        bank_send_eligibility=eligibility,
        downstream_counts={
            "bankMessages": 0,
            "bankSendTasks": 0,
            "paymentExecutions": 0,
            "paymentVouchers": 0,
            "writeoffs": 0,
            "ledgerEntries": 0,
            "postings": 0,
            "bankTransactions": 0,
        },
    )


__all__ = [
    "BankSendEligibility",
    "EXPECTED_STATE_TRANSITIONS",
    "FormalPaymentOrderExecutionGateFacts",
    "build_execution_gate_facts",
    "execution_snapshot_hash",
    "execution_snapshot_payload",
]
