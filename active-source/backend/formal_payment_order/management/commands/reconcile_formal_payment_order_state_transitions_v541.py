import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from formal_payment_order.facts import build_execution_gate_facts
from formal_payment_order.models import FormalPaymentOrder
from formal_payment_order.services import (
    APPROVE_ACTION,
    DOCUMENT_TYPE,
    FREEZE_ACTION,
    SUBMIT_ACTION,
)
from reconciliation.models import BusinessActionAuditRecord
from workflow_runtime.models import ApprovalDecision, BusinessStateTransition


VERSION = "V1.14.2.8.4.7.54.1"
EXPECTED = (
    ("prepared", "submitted", SUBMIT_ACTION),
    ("submitted", "approved", APPROVE_ACTION),
    ("approved", "frozen_for_execution", FREEZE_ACTION),
)


class Command(BaseCommand):
    help = "Reconcile V54.1 transition facts from committed approval/freeze audits"

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V54.1 reconciliation requires PCE_CANARY_DEMO_MODE")
        orders = list(
            FormalPaymentOrder.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
            .select_related(
                "approval__workflow_instance",
                "execution_freeze",
            )
            .order_by("order_no")
        )
        if len(orders) != 8:
            raise CommandError("V54.1 requires exactly eight formal payment orders")
        created_count = 0
        with transaction.atomic():
            for source in orders:
                order = (
                    FormalPaymentOrder.objects.select_for_update()
                    .select_related(
                        "approval__workflow_instance",
                        "execution_freeze",
                    )
                    .get(pk=source.pk)
                )
                approval = getattr(order, "approval", None)
                workflow = approval.workflow_instance if approval else None
                freeze = getattr(order, "execution_freeze", None)
                decisions = ApprovalDecision.objects.filter(
                    task__workflow_instance=workflow,
                    decision="approved",
                ).count() if workflow else 0
                if not (
                    order.status == FormalPaymentOrder.Status.FROZEN_FOR_EXECUTION
                    and approval
                    and approval.approval_status == "approved"
                    and workflow
                    and workflow.status == "approved"
                    and decisions == 2
                    and freeze
                    and freeze.freeze_hash
                ):
                    raise CommandError(
                        f"{order.order_no} lacks authoritative V54 approval/freeze facts"
                    )
                audits = list(
                    BusinessActionAuditRecord.objects.filter(
                        target_type="formalPaymentOrder",
                        target_id=order.pk,
                        action_code__in=[
                            SUBMIT_ACTION,
                            APPROVE_ACTION,
                            FREEZE_ACTION,
                        ],
                    )
                    .select_related("actor")
                    .order_by("created_at", "pk")
                )
                audit_by_transition = {}
                for audit in audits:
                    if audit.action_code == SUBMIT_ACTION:
                        audit_by_transition[SUBMIT_ACTION] = audit
                    elif (
                        audit.action_code == APPROVE_ACTION
                        and audit.evidence.get("stepNo") == 2
                    ):
                        audit_by_transition[APPROVE_ACTION] = audit
                    elif audit.action_code == FREEZE_ACTION:
                        audit_by_transition[FREEZE_ACTION] = audit
                if set(audit_by_transition) != {
                    SUBMIT_ACTION,
                    APPROVE_ACTION,
                    FREEZE_ACTION,
                }:
                    raise CommandError(
                        f"{order.order_no} lacks committed transition audit evidence"
                    )
                existing = list(
                    BusinessStateTransition.objects.filter(
                        object_type=DOCUMENT_TYPE,
                        object_id=order.pk,
                    ).order_by("version")
                )
                if existing:
                    actual = tuple(
                        (row.source_state, row.target_state, row.action_code)
                        for row in existing
                    )
                    if actual != EXPECTED:
                        raise CommandError(
                            f"{order.order_no} transition history conflicts with V54 facts"
                        )
                    continue
                for version, (from_status, to_status, action_code) in enumerate(
                    EXPECTED,
                    start=1,
                ):
                    audit = audit_by_transition[action_code]
                    transition = BusinessStateTransition.objects.create(
                        object_type=DOCUMENT_TYPE,
                        object_id=order.pk,
                        source_state=from_status,
                        target_state=to_status,
                        action_code=action_code,
                        workflow_instance=workflow,
                        operator=audit.actor,
                        reason={
                            SUBMIT_ACTION: "approval_submission",
                            APPROVE_ACTION: "final_approval_completed",
                            FREEZE_ACTION: "execution_facts_frozen",
                        }[action_code],
                        audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                        version=version,
                    )
                    BusinessStateTransition.objects.filter(
                        pk=transition.pk
                    ).update(timestamp=audit.created_at)
                    created_count += 1
        refreshed = list(
            FormalPaymentOrder.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
            .select_related(
                "source_risk_review__source_payment_order_draft",
                "approval__workflow_instance",
                "execution_freeze",
            )
            .order_by("order_no")
        )
        facts = [build_execution_gate_facts(order) for order in refreshed]
        transition_count = BusinessStateTransition.objects.filter(
            object_type=DOCUMENT_TYPE,
            object_id__in=[order.pk for order in refreshed],
        ).count()
        result = {
            "result": "passed",
            "version": VERSION,
            "formalPaymentOrderCount": len(refreshed),
            "workflowInstanceCount": sum(
                bool(fact.workflow_instance) for fact in facts
            ),
            "approvalTaskCount": sum(
                len(order.approval.workflow_instance.tasks.all())
                for order in refreshed
            ),
            "approvalDecisionCount": sum(
                len(fact.approval_history) for fact in facts
            ),
            "freezeSnapshotCount": sum(
                fact.freeze_status == "frozen" for fact in facts
            ),
            "freezeHashCount": sum(bool(fact.freeze_hash) for fact in facts),
            "businessStateTransitionCount": transition_count,
            "createdTransitionCount": created_count,
            "stateMachineConsistentCount": sum(
                fact.state_machine_consistent for fact in facts
            ),
            "bankSendEligibleCount": sum(
                fact.bank_send_eligibility.ready_for_bank_send for fact in facts
            ),
            "businessActionsReplayed": False,
            "productionUserDataWritten": False,
        }
        if not (
            result["workflowInstanceCount"] == 8
            and result["approvalTaskCount"] == 16
            and result["approvalDecisionCount"] == 16
            and result["freezeSnapshotCount"] == 8
            and result["freezeHashCount"] == 8
            and result["businessStateTransitionCount"] == 24
            and result["stateMachineConsistentCount"] == 8
            and result["bankSendEligibleCount"] == 8
        ):
            raise CommandError(json.dumps(result, ensure_ascii=False))
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
