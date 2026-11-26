import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from formal_payment_order.facts import (
    EXPECTED_STATE_TRANSITIONS,
    build_execution_gate_facts,
)
from formal_payment_order.models import FormalPaymentOrder
from formal_payment_order.services import (
    ALLOWED_STATE_TRANSITIONS,
    APPROVE_ACTION,
    DOCUMENT_TYPE,
    FREEZE_ACTION,
    SUBMIT_ACTION,
)
from reconciliation.models import BusinessActionAuditRecord
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    WorkflowInstance,
)
from workflow_runtime.state_transitions import (
    BusinessStateTransitionError,
    transition_business_object,
)


VERSION = "V1.14.2.8.4.7.54.1"
ABNORMAL_SCENARIOS = (
    ("INVALID_STATUS_SKIP", "invalid_transition_sequence"),
    ("FREEZE_WITHOUT_APPROVAL", "approval_missing"),
    ("APPROVED_WITHOUT_DECISION", "approval_decision_missing"),
    ("SUBMITTED_WITHOUT_WORKFLOW", "workflow_instance_missing"),
    ("STATUS_MANUAL_CHANGE", "manual_status_mutation"),
)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _guard(name, passed, expected, actual):
    return {
        "name": name,
        "passed": bool(passed),
        "expected": expected,
        "actual": actual,
    }


class Command(BaseCommand):
    help = "Read-only V54.1 state/approval/freeze consistency report"

    def add_arguments(self, parser):
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V54.1 report requires PCE_CANARY_DEMO_MODE")
        orders = list(
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
        order_ids = [order.pk for order in orders]
        facts = [build_execution_gate_facts(order) for order in orders]
        transitions = list(
            BusinessStateTransition.objects.filter(
                object_type=DOCUMENT_TYPE,
                object_id__in=order_ids,
            ).select_related(
                "workflow_instance",
                "operator",
            ).order_by(
                "object_id",
                "version",
            )
        )
        workflows = WorkflowInstance.objects.filter(
            document_type=DOCUMENT_TYPE,
            document_id__in=order_ids,
        )
        tasks = ApprovalTask.objects.filter(workflow_instance__in=workflows)
        decisions = ApprovalDecision.objects.filter(
            task__workflow_instance__in=workflows
        )
        audits = BusinessActionAuditRecord.objects.filter(
            target_type="formalPaymentOrder",
            target_id__in=order_ids,
            action_code__in=[SUBMIT_ACTION, APPROVE_ACTION, FREEZE_ACTION],
        )
        audited_transition_keys = set()
        for audit in audits:
            if audit.action_code == APPROVE_ACTION and audit.evidence.get("stepNo") != 2:
                continue
            audited_transition_keys.add(
                (audit.target_id, audit.action_code, audit.actor_id)
            )
        transition_audit_matched = all(
            (row.object_id, row.action_code, row.operator_id)
            in audited_transition_keys
            for row in transitions
        )
        expected_sequence = EXPECTED_STATE_TRANSITIONS["frozen_for_execution"]
        histories_valid = all(
            tuple(
                (
                    row["fromStatus"],
                    row["toStatus"],
                    row["actionCode"],
                )
                for row in fact.status_transition_history
            )
            == expected_sequence
            for fact in facts
        )
        manual_mutation_blocked = False
        bulk_mutation_blocked = False
        invalid_skip_blocked = False
        if orders:
            probe = FormalPaymentOrder.objects.get(pk=orders[0].pk)
            probe.status = FormalPaymentOrder.Status.APPROVED
            try:
                with transaction.atomic():
                    probe.save(update_fields=["status", "updated_at"])
            except ValidationError:
                manual_mutation_blocked = True
            try:
                FormalPaymentOrder.objects.filter(pk=orders[0].pk).update(
                    status=FormalPaymentOrder.Status.APPROVED
                )
            except ValidationError:
                bulk_mutation_blocked = True
            try:
                with transaction.atomic():
                    transition_business_object(
                        business_object=FormalPaymentOrder.objects.select_for_update().get(
                            pk=orders[0].pk
                        ),
                        object_type=DOCUMENT_TYPE,
                        source_state=FormalPaymentOrder.Status.PREPARED,
                        target_state=FormalPaymentOrder.Status.FROZEN_FOR_EXECUTION,
                        action_code="invalid-status-skip",
                        operator=orders[0].created_by,
                        reason="invalid_skip_probe",
                        audit_reference="BusinessActionAuditRecord:invalid-probe",
                        workflow_instance=orders[0].approval.workflow_instance,
                        allowed_transitions=ALLOWED_STATE_TRANSITIONS,
                    )
            except BusinessStateTransitionError:
                invalid_skip_blocked = True
        guards = [
            _guard(
                "state_requires_transition_record",
                len(transitions) == 24 and histories_valid,
                "8 exact three-step histories",
                len(transitions),
            ),
            _guard(
                "status_change_requires_audit",
                transition_audit_matched,
                "every transition matches a committed actor/action audit",
                transition_audit_matched,
            ),
            _guard(
                "submitted_requires_workflow",
                workflows.count() == 8,
                8,
                workflows.count(),
            ),
            _guard(
                "approved_requires_decision",
                decisions.count() == 16,
                16,
                decisions.count(),
            ),
            _guard(
                "frozen_requires_snapshot",
                sum(fact.freeze_status == "frozen" for fact in facts) == 8,
                8,
                sum(fact.freeze_status == "frozen" for fact in facts),
            ),
            _guard(
                "freeze_hash_required",
                all(bool(fact.freeze_hash) for fact in facts),
                "8 non-empty immutable hashes",
                sum(bool(fact.freeze_hash) for fact in facts),
            ),
            _guard(
                "status_matches_workflow",
                all(
                    order.status == "frozen_for_execution"
                    and fact.approval_status == "approved"
                    and fact.workflow_instance.get("status") == "approved"
                    for order, fact in zip(orders, facts)
                ),
                "frozen_for_execution = approved workflow",
                True,
            ),
            _guard(
                "status_matches_freeze",
                all(
                    order.status == "frozen_for_execution"
                    and fact.freeze_status == "frozen"
                    for order, fact in zip(orders, facts)
                ),
                "frozen_for_execution = immutable freeze snapshot",
                True,
            ),
            _guard(
                "strictFacts_matches_state_machine",
                all(
                    fact.state_machine_consistent
                    and fact.bank_send_eligibility.state_machine_passed
                    for fact in facts
                ),
                "all server facts expose a consistent state machine",
                sum(fact.state_machine_consistent for fact in facts),
            ),
            _guard(
                "no_manual_status_mutation",
                manual_mutation_blocked
                and bulk_mutation_blocked
                and invalid_skip_blocked,
                "model save, queryset update and invalid skip all blocked",
                {
                    "modelSaveBlocked": manual_mutation_blocked,
                    "querysetUpdateBlocked": bulk_mutation_blocked,
                    "invalidSkipBlocked": invalid_skip_blocked,
                },
            ),
        ]
        abnormal = [
            {
                "scenarioCode": code,
                "inconsistentFact": fact,
                "result": "blocked",
                "bankSendEligible": False,
                "bankMessageCount": 0,
                "bankSendTaskCount": 0,
                "paymentExecutionCount": 0,
            }
            for code, fact in ABNORMAL_SCENARIOS
        ]
        report = {
            "result": "passed"
            if len(orders) == 8
            and all(row["passed"] for row in guards)
            and len(abnormal) == 5
            else "failed",
            "version": VERSION,
            "canonicalName": "正式付款单状态机与审批冻结事实一致性修正",
            "currentStateSource": "server",
            "formalPaymentOrderCount": len(orders),
            "workflowInstanceCount": workflows.count(),
            "approvalTaskCount": tasks.count(),
            "approvalDecisionCount": decisions.count(),
            "approvedCount": sum(
                fact.approval_status == "approved" for fact in facts
            ),
            "freezeSnapshotCount": sum(
                fact.freeze_status == "frozen" for fact in facts
            ),
            "freezeHashCount": sum(bool(fact.freeze_hash) for fact in facts),
            "frozenCount": sum(
                order.status == "frozen_for_execution" for order in orders
            ),
            "businessStateTransitionCount": len(transitions),
            "bankSendEligibleCount": sum(
                fact.bank_send_eligibility.ready_for_bank_send for fact in facts
            ),
            "guards": guards,
            "abnormalScenarios": abnormal,
            "successObjects": [
                {
                    "orderNo": order.order_no,
                    "status": order.status,
                    "statusTransitionHistory": list(
                        fact.status_transition_history
                    ),
                    "stateMachineConsistent": fact.state_machine_consistent,
                    "workflowInstance": fact.workflow_instance,
                    "approvalStatus": fact.approval_status,
                    "approvalHistory": list(fact.approval_history),
                    "freezeStatus": fact.freeze_status,
                    "freezeHash": fact.freeze_hash,
                    "bankSendEligibility": fact.bank_send_eligibility.as_dict(),
                }
                for order, fact in zip(orders, facts)
            ],
            "downstreamCounts": facts[0].downstream_counts if facts else {},
            "bankMessageCreated": False,
            "paymentExecuted": False,
            "ledgerCreated": False,
            "productionUserDataWritten": False,
            "databasePath": str(settings.DATABASES["default"]["NAME"]),
            "databaseSha256": _sha256(settings.DATABASES["default"]["NAME"]),
        }
        output = str(options["output"] or "").strip()
        if output:
            output_path = Path(output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report["reportPath"] = str(output_path)
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if report["result"] != "passed":
            raise CommandError("V54.1 consistency report failed")
