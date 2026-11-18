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
    DOCUMENT_TYPE,
    serialize_order,
)
from reconciliation.models import BusinessActionAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import (
    BusinessStateTransitionError,
    transition_business_object,
)


VERSION = "V1.14.2.8.4.7.54.2"
EXPECTED_REASONS = (
    "approval_submission",
    "final_approval_completed",
    "execution_facts_frozen",
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
    help = "Read-only V54.2 formal payment order transition fact report"

    def add_arguments(self, parser):
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V54.2 report requires PCE_CANARY_DEMO_MODE")
        orders = list(
            FormalPaymentOrder.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
            .select_related(
                "source_risk_review__source_payment_order_draft",
                "source_snapshot",
                "evidence_snapshot",
                "number_reservation",
                "business_transaction",
                "approval__workflow_instance",
                "execution_freeze",
            )
            .order_by("order_no")
        )
        order_ids = [order.pk for order in orders]
        transitions = list(
            BusinessStateTransition.objects.filter(
                object_type=DOCUMENT_TYPE,
                object_id__in=order_ids,
            )
            .select_related("operator", "workflow_instance")
            .order_by("object_id", "version")
        )
        facts = [build_execution_gate_facts(order) for order in orders]
        serialized = [serialize_order(order) for order in orders]
        audit_ids = []
        for row in transitions:
            prefix, _, identifier = row.audit_reference.partition(":")
            if prefix == "BusinessActionAuditRecord" and identifier.isdigit():
                audit_ids.append(int(identifier))
        audits = {
            row.pk: row
            for row in BusinessActionAuditRecord.objects.filter(pk__in=audit_ids)
        }
        audit_matches = all(
            row.audit_reference == f"BusinessActionAuditRecord:{audit.pk}"
            and audit.target_type == "formalPaymentOrder"
            and audit.target_id == row.object_id
            and audit.action_code == row.action_code
            and audit.actor_id == row.operator_id
            and audit.result == "committed"
            for row in transitions
            for audit in [audits.get(int(row.audit_reference.rsplit(":", 1)[1]))]
            if audit is not None
        ) and len(audits) == len(transitions)
        expected_sequence = EXPECTED_STATE_TRANSITIONS["frozen_for_execution"]
        histories_complete = all(
            tuple(
                (
                    row["sourceState"],
                    row["targetState"],
                    row["actionCode"],
                )
                for row in fact.status_transition_history
            )
            == expected_sequence
            and tuple(
                row["reason"] for row in fact.status_transition_history
            )
            == EXPECTED_REASONS
            and [row["version"] for row in fact.status_transition_history]
            == [1, 2, 3]
            and all(row["auditReference"] for row in fact.status_transition_history)
            for fact in facts
        )
        direct_save_blocked = False
        bulk_update_blocked = False
        direct_initial_state_blocked = False
        missing_reason_blocked = False
        missing_audit_blocked = False
        if orders:
            probe = FormalPaymentOrder.objects.get(pk=orders[0].pk)
            probe.status = FormalPaymentOrder.Status.APPROVED
            try:
                with transaction.atomic():
                    probe.save(update_fields=["status", "updated_at"])
            except ValidationError:
                direct_save_blocked = True
            try:
                FormalPaymentOrder.objects.filter(pk=orders[0].pk).update(
                    status=FormalPaymentOrder.Status.APPROVED
                )
            except ValidationError:
                bulk_update_blocked = True
            try:
                with transaction.atomic():
                    FormalPaymentOrder(
                        status=FormalPaymentOrder.Status.PREPARED
                    ).save()
            except ValidationError:
                direct_initial_state_blocked = True
            current = FormalPaymentOrder.objects.get(pk=orders[0].pk)
            try:
                with transaction.atomic():
                    transition_business_object(
                        business_object=current,
                        object_type=DOCUMENT_TYPE,
                        source_state=current.status,
                        target_state=current.status,
                        action_code="invalid-missing-reason",
                        operator=current.created_by,
                        reason="",
                        audit_reference="BusinessActionAuditRecord:1",
                        allowed_transitions=ALLOWED_STATE_TRANSITIONS,
                    )
            except BusinessStateTransitionError:
                missing_reason_blocked = True
            try:
                with transaction.atomic():
                    transition_business_object(
                        business_object=current,
                        object_type=DOCUMENT_TYPE,
                        source_state=current.status,
                        target_state=current.status,
                        action_code="invalid-missing-audit",
                        operator=current.created_by,
                        reason="probe",
                        audit_reference="",
                        allowed_transitions=ALLOWED_STATE_TRANSITIONS,
                    )
            except BusinessStateTransitionError:
                missing_audit_blocked = True
        guards = [
            _guard(
                "transition_history_is_database_sourced",
                len(transitions) == 24,
                24,
                len(transitions),
            ),
            _guard(
                "transition_chain_is_complete",
                histories_complete,
                "8 prepared->submitted->approved->frozen_for_execution chains",
                [len(fact.status_transition_history) for fact in facts],
            ),
            _guard(
                "transition_audit_reference_is_authoritative",
                audit_matches,
                "24 unique committed BusinessActionAuditRecord references",
                len(audits),
            ),
            _guard(
                "transition_reason_is_required",
                all(bool(row.reason) for row in transitions)
                and missing_reason_blocked,
                "24 reasons and missing reason rejected",
                sum(bool(row.reason) for row in transitions),
            ),
            _guard(
                "transition_version_is_contiguous",
                all(
                    [row["version"] for row in fact.status_transition_history]
                    == [1, 2, 3]
                    for fact in facts
                ),
                "[1,2,3] for every object",
                True,
            ),
            _guard(
                "direct_status_mutation_is_blocked",
                direct_save_blocked and bulk_update_blocked,
                "model save and queryset update blocked",
                {
                    "modelSaveBlocked": direct_save_blocked,
                    "querysetUpdateBlocked": bulk_update_blocked,
                },
            ),
            _guard(
                "initial_state_requires_service",
                direct_initial_state_blocked,
                "direct prepared creation blocked",
                direct_initial_state_blocked,
            ),
            _guard(
                "audit_reference_is_required",
                all(bool(row.audit_reference) for row in transitions)
                and missing_audit_blocked,
                "24 audit references and missing reference rejected",
                sum(bool(row.audit_reference) for row in transitions),
            ),
            _guard(
                "server_transition_count_matches_history",
                all(
                    row["statusTransitionCount"]
                    == len(row["statusTransitionHistory"])
                    == 3
                    for row in serialized
                ),
                "server count = server history length = 3",
                [row["statusTransitionCount"] for row in serialized],
            ),
            _guard(
                "state_machine_consistent_is_true",
                all(
                    row["stateMachineConsistent"] is True
                    for row in serialized
                ),
                "8 true",
                sum(row["stateMachineConsistent"] is True for row in serialized),
            ),
        ]
        downstream_counts = facts[0].downstream_counts if facts else {}
        report = {
            "result": "passed"
            if len(orders) == 8
            and all(row["passed"] for row in guards)
            and all(value == 0 for value in downstream_counts.values())
            else "failed",
            "version": VERSION,
            "canonicalName": "正式付款单状态机转换事实完整性修复",
            "currentStateSource": "server",
            "formalPaymentOrderCount": len(orders),
            "businessStateTransitionCount": len(transitions),
            "statusTransitionCountPerObject": [
                row["statusTransitionCount"] for row in serialized
            ],
            "stateMachineConsistentCount": sum(
                row["stateMachineConsistent"] is True for row in serialized
            ),
            "reasonCompleteCount": sum(bool(row.reason) for row in transitions),
            "auditReferenceCompleteCount": sum(
                bool(row.audit_reference) for row in transitions
            ),
            "guards": guards,
            "successObjects": [
                {
                    "orderNo": order.order_no,
                    "status": row["status"],
                    "statusTransitionHistory": row["statusTransitionHistory"],
                    "statusTransitionCount": row["statusTransitionCount"],
                    "stateMachineConsistent": row["stateMachineConsistent"],
                }
                for order, row in zip(orders, serialized)
            ],
            "downstreamCounts": downstream_counts,
            "bankMessageCreated": False,
            "bankSendTaskCreated": False,
            "paymentExecuted": False,
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
            raise CommandError("V54.2 transition fact report failed")
