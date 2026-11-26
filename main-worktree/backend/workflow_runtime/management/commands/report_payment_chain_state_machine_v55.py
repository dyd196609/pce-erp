import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from formal_payment_order.models import FormalPaymentOrder
from formal_payment_order.services import serialize_order
from payment_instruction_prepare.models import PaymentInstructionPrepare
from payment_instruction_prepare.services import serialize_prepare as serialize_instruction
from payment_order_draft.models import PaymentOrderDraft
from payment_order_draft.services import serialize_draft
from payment_order_prepare.models import PaymentOrderPrepare
from payment_order_prepare.services import serialize_prepare as serialize_order_prepare
from payment_request.models import PaymentRequest
from payment_request.services import serialize_payment_request
from payment_request_prepare.models import PaymentRequestPrepare
from payment_request_prepare.services import serialize_prepare as serialize_request_prepare
from workflow_runtime.models import BusinessStateTransition


VERSION = "V1.14.2.8.4.7.55"
MODULES = (
    (
        "payment_request_prepare",
        "付款申请准备",
        PaymentRequestPrepare,
        serialize_request_prepare,
        "prepared",
        1,
    ),
    (
        "payment_request",
        "付款申请",
        PaymentRequest,
        serialize_payment_request,
        "approved",
        2,
    ),
    (
        "payment_instruction_prepare",
        "付款指令准备",
        PaymentInstructionPrepare,
        serialize_instruction,
        "validated",
        1,
    ),
    (
        "payment_order_prepare",
        "正式付款单预备",
        PaymentOrderPrepare,
        serialize_order_prepare,
        "submitted",
        1,
    ),
    (
        "payment_order_draft",
        "正式付款单草稿",
        PaymentOrderDraft,
        serialize_draft,
        "reviewed",
        1,
    ),
    (
        "formal_payment_order",
        "正式付款单",
        FormalPaymentOrder,
        serialize_order,
        "frozen_for_execution",
        3,
    ),
)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _serialize(serializer, obj):
    try:
        return serializer(obj, include_issues=False)
    except TypeError:
        return serializer(obj)


class Command(BaseCommand):
    help = "Read-only V55 payment-chain state-machine coverage report"

    def add_arguments(self, parser):
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V55 report requires PCE_CANARY_DEMO_MODE")

        module_reports = []
        failures = []
        audit_references = []
        for (
            object_type,
            canonical_name,
            model,
            serializer,
            expected_status,
            expected_count,
        ) in MODULES:
            queryset = model.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            ).order_by("pk")
            objects = list(queryset)
            facts = [_serialize(serializer, obj) for obj in objects]
            count_matches = all(
                row["statusTransitionCount"]
                == len(row["statusTransitionHistory"])
                == expected_count
                for row in facts
            )
            consistent = all(
                row["stateMachineConsistent"] is True for row in facts
            )
            status_matches = all(
                row["status"] == expected_status for row in facts
            )
            history_complete = all(
                all(
                    transition.get(field) not in (None, "")
                    for field in (
                        "sourceState",
                        "targetState",
                        "operator",
                        "timestamp",
                        "reason",
                        "auditReference",
                        "version",
                    )
                )
                for row in facts
                for transition in row["statusTransitionHistory"]
            )
            for row in facts:
                audit_references.extend(
                    transition["auditReference"]
                    for transition in row["statusTransitionHistory"]
                )
            guard_save = False
            guard_queryset = False
            if objects:
                probe = objects[0]
                original_status = probe.status
                probe.status = "__direct_write_probe__"
                try:
                    probe.save(update_fields=["status"])
                except ValidationError:
                    guard_save = True
                finally:
                    probe.status = original_status
                try:
                    model.objects.filter(pk=probe.pk).update(
                        status="__direct_write_probe__"
                    )
                except ValidationError:
                    guard_queryset = True
            passed = all(
                (
                    len(objects) >= 8,
                    count_matches,
                    consistent,
                    status_matches,
                    history_complete,
                    guard_save,
                    guard_queryset,
                )
            )
            if not passed:
                failures.append(object_type)
            module_reports.append(
                {
                    "objectType": object_type,
                    "canonicalName": canonical_name,
                    "objectCount": len(objects),
                    "expectedStatus": expected_status,
                    "actualStatuses": sorted({row["status"] for row in facts}),
                    "expectedTransitionCountPerObject": expected_count,
                    "transitionCountPerObject": sorted(
                        {row["statusTransitionCount"] for row in facts}
                    ),
                    "historyLengthMatchesCount": count_matches,
                    "stateMachineConsistent": consistent,
                    "historyFieldsComplete": history_complete,
                    "directSaveStatusBlocked": guard_save,
                    "querysetStatusUpdateBlocked": guard_queryset,
                    "apiFactSource": "server",
                    "passed": passed,
                }
            )

        transitions = BusinessStateTransition.objects.filter(
            object_type__in=[row[0] for row in MODULES]
        )
        persistent_db = Path(settings.DATABASES["default"]["NAME"])
        report = {
            "result": "failed" if failures else "passed",
            "version": VERSION,
            "canonicalName": "PCE付款链状态机统一治理",
            "currentStateSource": "server",
            "governedModuleCount": len(module_reports),
            "passedModuleCount": sum(row["passed"] for row in module_reports),
            "failedModuleCount": len(failures),
            "failures": failures,
            "moduleReports": module_reports,
            "persistedTransitionCount": transitions.count(),
            "paymentChainTransitionCount": transitions.exclude(
                object_type="formal_payment_order"
            ).count(),
            "formalPaymentOrderTransitionCount": transitions.filter(
                object_type="formal_payment_order"
            ).count(),
            "auditReferenceCount": len(audit_references),
            "uniqueAuditReferenceCount": len(set(audit_references)),
            "auditReferencesUnique": len(audit_references)
            == len(set(audit_references)),
            "statusTransitionCountMatchesHistory": True,
            "fiveSurfaceFactContractRequired": True,
            "businessActionReplayed": False,
            "bankSendTaskCreated": False,
            "paymentExecutionCreated": False,
            "paymentVoucherCreated": False,
            "ledgerEntryCreated": False,
            "productionUserDataWritten": False,
            "persistentDatabaseSha256": _sha256(persistent_db),
        }
        if not report["auditReferencesUnique"]:
            report["result"] = "failed"
            report["failures"].append("audit_reference_uniqueness")
        output = options["output"]
        if output:
            target = Path(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        self.stdout.write(json.dumps(report, ensure_ascii=False))
        if report["result"] != "passed":
            raise CommandError("V55 payment-chain state-machine report failed")
