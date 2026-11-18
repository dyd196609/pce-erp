from django.db import transaction
from django.utils import timezone

from workflow_runtime.fact_loads import build_fact_load_facts
from workflow_runtime.facts import business_state_transition_facts
from workflow_runtime.models import UserOrganizationRoleAuthority
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .models import (
    BankSendDualIsolationCheck,
    BankSendProductionReleaseDecision,
    BankSendProductionReleaseReview,
)
from .v66 import evaluate_final_checks, protection_counts as v66_protection_counts


VERSION = "V1.14.2.8.4.7.67"
DUAL_ISOLATION_MODULE_CODE = "bank-send-dual-isolation-check"
RELEASE_REVIEW_MODULE_CODE = "bank-send-production-release-review"
REVIEW_OBJECT_TYPE = "bank_send_production_release_review"
BUSINESS_OWNER_ROLE = "bank_send_business_owner"
FUND_OWNER_ROLE = "bank_send_fund_owner"
SECURITY_OWNER_ROLE = "bank_send_security_owner"
REVIEW_TRANSITIONS = (
    ("draft", "reviewing"),
    ("reviewing", "review_passed"),
    ("review_passed", "locked"),
)
REVIEW_EXPECTED_TRANSITIONS = {
    "draft": (),
    "reviewing": (
        ("draft", "reviewing", "submit-production-business-review"),
    ),
    "review_passed": (
        ("draft", "reviewing", "submit-production-business-review"),
        ("reviewing", "review_passed", "submit-production-fund-review"),
    ),
    "locked": (
        ("draft", "reviewing", "submit-production-business-review"),
        ("reviewing", "review_passed", "submit-production-fund-review"),
        ("review_passed", "locked", "submit-production-security-review"),
    ),
}
REVIEW_STATUS_LABELS = {
    "draft": "评审草稿",
    "reviewing": "评审中",
    "review_passed": "生产评审通过",
    "locked": "生产评审已锁定",
}
ROLE_BY_STAGE = {
    "business": BUSINESS_OWNER_ROLE,
    "fund": FUND_OWNER_ROLE,
    "security": SECURITY_OWNER_ROLE,
}
TRANSITION_BY_STAGE = {
    "business": (
        "draft",
        "reviewing",
        "submit-production-business-review",
    ),
    "fund": (
        "reviewing",
        "review_passed",
        "submit-production-fund-review",
    ),
    "security": (
        "review_passed",
        "locked",
        "submit-production-security-review",
    ),
}


def protection_counts():
    return {
        **v66_protection_counts(),
        "dualIsolationWriteCount": BankSendDualIsolationCheck.objects.count(),
        "releaseReviewWriteCount": BankSendProductionReleaseReview.objects.count(),
        "bankMessageSendWriteCount": 0,
        "paymentExecutionWriteCount": 0,
        "financialImpactWriteCount": 0,
        "businessProgressWriteCount": 0,
        "bankSendObjectCount": 0,
    }


def evaluate_dual_isolation(approval):
    gate = approval.trace.isolation_gate
    categories = {
        "environment_check": (
            gate.status == "isolated"
            and gate.simulation_environment is True
        ),
        "credential_check": gate.production_secret_available is False,
        "permission_check": (
            gate.production_send_allowed is False
            and gate.payment_execution_allowed is False
        ),
        "interface_check": gate.production_connection_enabled is False,
    }
    details = {
        "productionEnvironmentIsolated": categories["environment_check"],
        "productionInterfaceDisabled": (
            gate.production_connection_enabled is False
        ),
        "productionCredentialAbsent": (
            gate.production_secret_available is False
        ),
        "sendPermissionDisabled": gate.production_send_allowed is False,
        "paymentPermissionDisabled": (
            gate.payment_execution_allowed is False
        ),
    }
    return {
        "categories": categories,
        "details": details,
        "passed": all(categories.values()) and all(details.values()),
        "factSource": "server",
    }


def create_dual_isolation_check(*, approval, user):
    evaluated = evaluate_dual_isolation(approval)
    if approval.status != "final_locked" or not evaluated["passed"]:
        raise ValueError("Dual isolation check failed")
    with transaction.atomic():
        existing = BankSendDualIsolationCheck.objects.filter(
            approval=approval
        ).first()
        if existing:
            return existing
        return BankSendDualIsolationCheck.objects.create(
            check_no=f"BSDIC-{approval.approval_no}",
            trace=approval.trace,
            approval=approval,
            trace_no=approval.trace_no,
            approval_no=approval.approval_no,
            tenant_id=approval.tenant_id,
            batch_id=approval.batch_id,
            environment_isolated=True,
            production_interface_disabled=True,
            production_credential_absent=True,
            send_permission_disabled=True,
            payment_permission_disabled=True,
            category_results=evaluated,
            result="passed",
            checked_by=user,
            checked_at=timezone.now(),
        )


def evaluate_release_checks(approval, isolation_check):
    trace = approval.trace
    simulation = trace.source_simulation
    audit_types = set(
        simulation.independent_audits.values_list("audit_type", flat=True)
    )
    gate = trace.isolation_gate
    protection = protection_counts()
    checks = {
        "RELEASE-001": approval.status == "final_locked",
        "RELEASE-002": (
            trace.trace_complete
            and len(trace.node_snapshot) == 8
            and all(row.get("businessNo") for row in trace.node_snapshot)
        ),
        "RELEASE-003": simulation.status == "simulation_success",
        "RELEASE-004": {
            "simulation_created",
            "simulation_validated",
            "simulation_started",
            "simulation_completed",
        }.issubset(audit_types),
        "RELEASE-005": (
            isolation_check.result == "passed"
            and gate.status == "isolated"
        ),
        "RELEASE-006": gate.production_connection_enabled is False,
        "RELEASE-007": gate.production_secret_available is False,
        "RELEASE-008": gate.production_send_allowed is False,
        "RELEASE-009": gate.payment_execution_allowed is False,
        "RELEASE-010": protection["businessProgressWriteCount"] == 0,
    }
    return {
        **checks,
        "passed": all(checks.values()),
        "factSource": "server",
    }


def create_release_review(*, approval, isolation_check, user):
    if isolation_check.approval_id != approval.pk:
        raise ValueError("Isolation check approval mismatch")
    checks = evaluate_release_checks(approval, isolation_check)
    if not checks["passed"]:
        raise ValueError("Production release review checks failed")
    with transaction.atomic():
        existing = BankSendProductionReleaseReview.objects.filter(
            approval=approval
        ).first()
        if existing:
            return existing
        return create_business_object_with_initial_state(
            model=BankSendProductionReleaseReview,
            initial_state="draft",
            review_no=f"BSPRR-{approval.approval_no}",
            trace=approval.trace,
            approval=approval,
            isolation_check=isolation_check,
            trace_no=approval.trace_no,
            approval_no=approval.approval_no,
            isolation_check_no=isolation_check.check_no,
            tenant_id=approval.tenant_id,
            batch_id=approval.batch_id,
            checks=checks,
            audit_events=[],
            created_by=user,
        )


def _legal_entity(review):
    return (
        review.trace.source_simulation.source_request.legal_entity_id
    )


def _has_role(user, review, role):
    return UserOrganizationRoleAuthority.objects.filter(
        user=user,
        role_code=role,
        legal_entity_id=_legal_entity(review),
        active=True,
    ).exists()


def submit_release_decision(*, review, user, stage, reason):
    if stage not in ROLE_BY_STAGE:
        raise ValueError("Invalid review stage")
    role = ROLE_BY_STAGE[stage]
    source, target, action_code = TRANSITION_BY_STAGE[stage]
    if review.status != source:
        raise ValueError(f"{stage} review requires {source} status")
    if not _has_role(user, review, role):
        raise PermissionError(f"{role} role required")
    if review.decisions.filter(operator=user).exists():
        raise PermissionError("Independent review users are required")
    if review.decisions.filter(role=role).exists():
        raise PermissionError("Independent review roles are required")
    checks = evaluate_release_checks(
        review.approval, review.isolation_check
    )
    if not checks["passed"]:
        raise ValueError("Release checks no longer pass")
    reference = (
        f"BankSendProductionReleaseReviewAudit:"
        f"{review.review_no}:{action_code}"
    )
    with transaction.atomic():
        review.audit_events = [
            *review.audit_events,
            {
                "actionCode": action_code,
                "operator": user.get_username(),
                "role": role,
                "timestamp": timezone.now().isoformat(),
                "reason": reason,
                "decision": "confirmed",
                "auditReference": reference,
            },
        ]
        review.save(update_fields=["audit_events", "updated_at"])
        transition_business_object(
            business_object=review,
            object_type=REVIEW_OBJECT_TYPE,
            source_state=source,
            target_state=target,
            action_code=action_code,
            operator=user,
            reason=reason,
            audit_reference=reference,
            allowed_transitions=REVIEW_TRANSITIONS,
        )
        BankSendProductionReleaseDecision.objects.create(
            review=review,
            stage=stage,
            operator=user,
            role=role,
            occurred_at=timezone.now(),
            reason=reason,
            decision="confirmed",
            audit_reference=reference,
        )
    return BankSendProductionReleaseReview.objects.get(pk=review.pk)


def _review_transition_facts(review):
    facts = business_state_transition_facts(
        business_object=review,
        object_type=REVIEW_OBJECT_TYPE,
        expected_transitions=REVIEW_EXPECTED_TRANSITIONS,
        audit_target_type="BankSendProductionReleaseReview",
    )
    history = facts["statusTransitionHistory"]
    actual = tuple(
        (row["sourceState"], row["targetState"], row["actionCode"])
        for row in history
    )
    expected = REVIEW_EXPECTED_TRANSITIONS.get(review.status)
    references = {
        (row["actionCode"], row["auditReference"])
        for row in review.audit_events
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


def serialize_isolation_check(check):
    categories = check.category_results.get("categories", {})
    details = check.category_results.get("details", {})
    return {
        "id": check.pk,
        "checkNo": check.check_no,
        "traceNo": check.trace_no,
        "approvalNo": check.approval_no,
        "tenantId": check.tenant_id,
        "batchId": check.batch_id,
        "result": check.result,
        "resultLabel": "隔离检查通过" if check.result == "passed" else "隔离检查失败",
        "environmentCheck": categories.get("environment_check", False),
        "credentialCheck": categories.get("credential_check", False),
        "permissionCheck": categories.get("permission_check", False),
        "interfaceCheck": categories.get("interface_check", False),
        **details,
        "checkedBy": check.checked_by.get_username(),
        "checkedAt": check.checked_at.isoformat(),
        "factSource": "server",
    }


def _serialize_decision(decision):
    return {
        "stage": decision.stage,
        "operator": decision.operator.get_username(),
        "role": decision.role,
        "timestamp": decision.occurred_at.isoformat(),
        "reason": decision.reason,
        "decision": decision.decision,
        "auditReference": decision.audit_reference,
    }


def serialize_release_review(review):
    decisions = [
        _serialize_decision(row)
        for row in review.decisions.select_related("operator").order_by("pk")
    ]
    return {
        "id": review.pk,
        "reviewNo": review.review_no,
        "traceNo": review.trace_no,
        "approvalNo": review.approval_no,
        "isolationCheckNo": review.isolation_check_no,
        "tenantId": review.tenant_id,
        "batchId": review.batch_id,
        "status": review.status,
        "statusCode": review.status,
        "statusLabel": REVIEW_STATUS_LABELS[review.status],
        "checks": review.checks,
        "isolation": serialize_isolation_check(review.isolation_check),
        "decisions": decisions,
        "businessReview": next(
            (row for row in decisions if row["stage"] == "business"), None
        ),
        "fundReview": next(
            (row for row in decisions if row["stage"] == "fund"), None
        ),
        "securityReview": next(
            (row for row in decisions if row["stage"] == "security"), None
        ),
        "productionReviewMeansSent": False,
        "bankSent": False,
        **_review_transition_facts(review),
    }


def _base_facts(*, fact_type, api_url, tenant_id, batch_id, count):
    return {
        "factType": fact_type,
        "factSource": "server",
        "recordCount": count,
        **protection_counts(),
        **build_fact_load_facts(
            fact_load_status="success",
            api_url=api_url,
            http_status=200,
            tenant_id=tenant_id,
            batch_id=batch_id,
        ),
    }


def dual_isolation_facts(rows, *, tenant_id, batch_id):
    return {
        **_base_facts(
            fact_type="BankSendDualIsolationCheckFacts",
            api_url="/api/finance/bank-send-dual-isolation-checks/",
            tenant_id=tenant_id,
            batch_id=batch_id,
            count=len(rows),
        ),
        "checkCount": len(rows),
        "passedCount": sum(row["result"] == "passed" for row in rows),
        "failedCount": sum(row["result"] == "failed" for row in rows),
        "environmentPassedCount": sum(row["environmentCheck"] for row in rows),
        "credentialPassedCount": sum(row["credentialCheck"] for row in rows),
        "permissionPassedCount": sum(row["permissionCheck"] for row in rows),
        "interfacePassedCount": sum(row["interfaceCheck"] for row in rows),
    }


def release_review_facts(rows, *, tenant_id, batch_id):
    return {
        **_base_facts(
            fact_type="BankSendProductionReleaseReviewFacts",
            api_url="/api/finance/bank-send-production-release-reviews/",
            tenant_id=tenant_id,
            batch_id=batch_id,
            count=len(rows),
        ),
        "reviewCount": len(rows),
        "draftCount": sum(row["status"] == "draft" for row in rows),
        "reviewingCount": sum(row["status"] == "reviewing" for row in rows),
        "reviewPassedCount": sum(
            row["status"] == "review_passed" for row in rows
        ),
        "lockedCount": sum(row["status"] == "locked" for row in rows),
        "completeManualReviewCount": sum(
            len(row["decisions"]) >= 2
            and len({item["operator"] for item in row["decisions"]})
            == len(row["decisions"])
            and len({item["role"] for item in row["decisions"]})
            == len(row["decisions"])
            for row in rows
        ),
        "bankSentCount": 0,
        "paymentExecutionCount": 0,
    }
