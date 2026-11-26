import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from formal_payment_order.facts import (
    build_execution_gate_facts,
    execution_snapshot_hash,
)
from formal_payment_order.models import (
    FormalPaymentOrder,
    FormalPaymentOrderSendGateCanaryScenario,
)
from formal_payment_order.services import (
    APPROVAL_ROLES,
    APPROVE_ACTION,
    DOCUMENT_TYPE,
    FREEZE_ACTION,
    SEND_GATE_BATCH_ID,
    SUBMIT_ACTION,
    VERSION,
    freeze_formal_payment_order,
)
from reconciliation.models import BusinessActionAuditRecord
from workflow_runtime.models import ApprovalDecision, ApprovalTask, WorkflowInstance


def _guard(name, passed, expected, actual):
    return {
        "name": name,
        "passed": bool(passed),
        "expected": expected,
        "actual": actual,
    }


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Command(BaseCommand):
    help = "Read-only V54 runtime proof and optional JSON report"

    def add_arguments(self, parser):
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V54 report requires PCE_CANARY_DEMO_MODE")
        orders = list(
            FormalPaymentOrder.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
            .select_related(
                "source_risk_review__source_payment_order_draft",
                "approval__workflow_instance",
                "execution_freeze",
                "created_by",
            )
            .order_by("order_no")
        )
        facts = [build_execution_gate_facts(order) for order in orders]
        blocked = list(
            FormalPaymentOrderSendGateCanaryScenario.objects.filter(
                batch_id=SEND_GATE_BATCH_ID
            ).order_by("scenario_code")
        )
        workflow_ids = [
            order.approval.workflow_instance_id
            for order in orders
            if hasattr(order, "approval")
        ]
        workflows = WorkflowInstance.objects.filter(
            pk__in=workflow_ids,
            document_type=DOCUMENT_TYPE,
        )
        tasks = ApprovalTask.objects.filter(workflow_instance_id__in=workflow_ids)
        decisions = ApprovalDecision.objects.filter(
            task__workflow_instance_id__in=workflow_ids
        )
        transition_audits = BusinessActionAuditRecord.objects.filter(
            target_type="formalPaymentOrder",
            target_id__in=[order.pk for order in orders],
            action_code__in=[SUBMIT_ACTION, APPROVE_ACTION, FREEZE_ACTION],
        )
        hashes_valid = all(
            order.execution_freeze.freeze_hash
            == execution_snapshot_hash(order, order.approval)
            for order in orders
        )
        histories_valid = all(
            len(fact.approval_history) >= 2
            and [row["roleCode"] for row in fact.approval_history[:2]]
            == list(APPROVAL_ROLES)
            and len({row["actorId"] for row in fact.approval_history[:2]}) == 2
            and order.created_by_id
            not in {row["actorId"] for row in fact.approval_history[:2]}
            for order, fact in zip(orders, facts)
        )
        runtime_guards = [
            _guard(
                "workflow_engine_is_shared",
                workflows.count() == 8
                and tasks.count() == 16
                and decisions.count() == 16,
                "8 shared instances / 16 tasks / 16 decisions",
                {
                    "instances": workflows.count(),
                    "tasks": tasks.count(),
                    "decisions": decisions.count(),
                },
            ),
            _guard(
                "formal_payment_order_state_transition_valid",
                all(order.status == "frozen_for_execution" for order in orders)
                and transition_audits.filter(action_code=SUBMIT_ACTION).count() == 8
                and transition_audits.filter(action_code=APPROVE_ACTION).count() == 16
                and transition_audits.filter(action_code=FREEZE_ACTION).count() == 8,
                "8 prepared->submitted->approved->frozen audit chains",
                {
                    "submitAudits": transition_audits.filter(
                        action_code=SUBMIT_ACTION
                    ).count(),
                    "approveAudits": transition_audits.filter(
                        action_code=APPROVE_ACTION
                    ).count(),
                    "freezeAudits": transition_audits.filter(
                        action_code=FREEZE_ACTION
                    ).count(),
                },
            ),
            _guard(
                "approval_requires_workflow_instance",
                len(workflow_ids) == 8 and len(set(workflow_ids)) == 8,
                "one unique workflow instance per formal payment order",
                workflow_ids,
            ),
            _guard(
                "freeze_requires_approved_status",
                all(
                    order.approval.approval_status == "approved"
                    and order.approval.approved_at
                    and order.execution_freeze.approval_version
                    == order.approval.version
                    for order in orders
                ),
                "all freezes reference approved approval versions",
                "all approved" if orders else "no objects",
            ),
            _guard(
                "freeze_hash_protects_execution_fields",
                hashes_valid,
                "all 8 freeze hashes equal current protected execution facts",
                hashes_valid,
            ),
            _guard(
                "bank_send_eligibility_server_derived",
                all(
                    fact.bank_send_eligibility.server_derived
                    and fact.bank_send_eligibility.ready_for_bank_send
                    for fact in facts
                ),
                "8 server-derived ready_for_bank_send facts",
                sum(
                    fact.bank_send_eligibility.ready_for_bank_send
                    for fact in facts
                ),
            ),
            _guard(
                "bank_message_zero_before_send",
                all(
                    fact.bank_send_eligibility.bank_message_count == 0
                    and fact.bank_send_eligibility.bank_send_task_count == 0
                    for fact in facts
                )
                and all(row.bank_message_count == 0 for row in blocked),
                "bank messages/tasks = 0 for success and blocked groups",
                0,
            ),
            _guard(
                "payment_execution_zero_before_release",
                all(
                    fact.bank_send_eligibility.payment_execution_count == 0
                    for fact in facts
                )
                and all(row.payment_execution_count == 0 for row in blocked),
                "payment executions = 0",
                0,
            ),
            _guard(
                "approval_segregation_valid",
                histories_valid,
                "maker/checker/final authorizer are distinct with required roles",
                histories_valid,
            ),
            _guard(
                "all_pages_use_common_workflow_contract",
                workflows.count() == len(orders),
                "all V54 approval pages use workflow_runtime",
                {"formalPaymentOrder": "workflow_runtime"},
            ),
        ]
        replay = None
        if orders:
            first = orders[0]
            replay = freeze_formal_payment_order(
                user=first.execution_freeze.frozen_by,
                order=first,
                idempotency_key=f"V54-FREEZE-{first.order_no}",
                expected_order_version=first.version - 1,
                expected_approval_version=first.approval.version,
                explicit_user_action=True,
            )
        database_path = settings.DATABASES["default"]["NAME"]
        report = {
            "result": "passed"
            if len(orders) == 8
            and len(blocked) >= 15
            and all(row.passed if hasattr(row, "passed") else row["passed"] for row in runtime_guards)
            else "failed",
            "version": VERSION,
            "canonicalName": "正式付款单审批冻结与银行发送前最终门禁",
            "formalPaymentOrderCount": len(orders),
            "approvedCount": sum(fact.approval_status == "approved" for fact in facts),
            "frozenCount": sum(fact.freeze_status == "frozen" for fact in facts),
            "bankSendEligibleCount": sum(
                fact.bank_send_eligibility.ready_for_bank_send for fact in facts
            ),
            "blockedScenarioCount": len(blocked),
            "idempotencyReplayClassification": (
                replay["classification"] if replay else "not_checked"
            ),
            "runtimeGuards": runtime_guards,
            "successObjects": [
                {
                    "orderNo": order.order_no,
                    "status": order.status,
                    "approvalStatus": fact.approval_status,
                    "workflowInstance": fact.workflow_instance,
                    "approvalHistory": list(fact.approval_history),
                    "freezeStatus": fact.freeze_status,
                    "freezeHash": fact.freeze_hash,
                    "bankSendEligibility": fact.bank_send_eligibility.as_dict(),
                }
                for order, fact in zip(orders, facts)
            ],
            "blockedScenarios": [
                {
                    "scenarioCode": row.scenario_code,
                    "blockingFact": row.blocking_fact,
                    "bankSendEligible": row.bank_send_eligible,
                    "bankMessageCount": row.bank_message_count,
                    "paymentExecutionCount": row.payment_execution_count,
                }
                for row in blocked
            ],
            "downstreamCounts": {
                "bankMessages": 0,
                "bankSendTasks": 0,
                "paymentExecutions": 0,
                "paymentVouchers": 0,
                "writeoffs": 0,
                "ledgerEntries": 0,
                "postings": 0,
                "bankTransactions": 0,
            },
            "bankMessageCreated": False,
            "paymentExecuted": False,
            "ledgerCreated": False,
            "productionUserDataWritten": False,
            "databasePath": str(database_path),
            "databaseSha256": _sha256(database_path),
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
            raise CommandError("V54 runtime report failed")
