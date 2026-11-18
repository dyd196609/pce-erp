import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.migrations.recorder import MigrationRecorder

from bank_send_preparation.models import (
    BankMessagePreview,
    BankSendGate,
    BankSendPreparation,
)
from bank_send_preparation.services import (
    VERSION,
    downstream_counts,
    serialize_preparation,
    bank_send_preparation_facts_for_rows,
)
from formal_payment_order.models import FormalPaymentOrder
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionTransaction,
)
from system.models import User
from workflow_runtime.action_permissions import ActionPermissionValidator
from workflow_runtime.models import BusinessStateTransition


class Command(BaseCommand):
    help = "Emit read-only V58 bank-send preparation acceptance facts."

    def handle(self, *args, **options):
        tenant_id = settings.PCE_CANARY_TENANT_ID
        preparations = list(
            BankSendPreparation.objects.filter(
                tenant_id=tenant_id,
            ).order_by("prepare_no")
        )
        rows = [serialize_preparation(row) for row in preparations]
        object_ids = [row.pk for row in preparations[:1]]
        operator = User.objects.get(username="v552-operator")
        viewer = User.objects.get(username="v552-viewer")
        outscope = User.objects.get(username="v552-outscope")
        validator = ActionPermissionValidator()
        operator_decision = validator.evaluate(
            user=operator,
            module_code="bank-send-preparation",
            action_code="generate-bank-message-preview",
            object_ids=object_ids,
            selection_count=len(object_ids),
        )
        viewer_decision = validator.evaluate(
            user=viewer,
            module_code="bank-send-preparation",
            action_code="generate-bank-message-preview",
            object_ids=object_ids,
            selection_count=len(object_ids),
        )
        outscope_decision = validator.evaluate(
            user=outscope,
            module_code="bank-send-preparation",
            action_code="generate-bank-message-preview",
            object_ids=object_ids,
            selection_count=len(object_ids),
        )
        preview_ids = list(
            BankMessagePreview.objects.filter(
                preparation__tenant_id=tenant_id,
            ).values_list("pk", flat=True)
        )
        transition_count = BusinessStateTransition.objects.filter(
            object_type="bank_send_preparation",
            object_id__in=[row.pk for row in preparations],
        ).count()
        transaction_count = BusinessActionTransaction.objects.filter(
            action_code__in=[
                "prepare-bank-send-gate",
                "generate-bank-message-preview",
            ],
            tenant_id=tenant_id,
            status=BusinessActionTransaction.Status.COMMITTED,
        ).count()
        idempotency_count = BusinessActionIdempotency.objects.filter(
            action_code__in=[
                "prepare-bank-send-gate",
                "generate-bank-message-preview",
            ],
            tenant_id=tenant_id,
            status=BusinessActionIdempotency.Status.COMMITTED,
        ).count()
        audit_count = BusinessActionAuditRecord.objects.filter(
            action_code__in=[
                "prepare-bank-send-gate",
                "generate-bank-message-preview",
            ],
            tenant_id=tenant_id,
            result="committed",
        ).count()
        counts = downstream_counts(tenant_id=settings.PCE_CANARY_TENANT_ID)
        source_formal_payment_order_count = FormalPaymentOrder.objects.filter(
            tenant_id=tenant_id,
            status="frozen_for_execution",
        ).count()
        bank_send_preparation_facts = (
            bank_send_preparation_facts_for_rows(
                rows,
                source_formal_payment_order_count=(
                    source_formal_payment_order_count
                ),
                counts=counts,
            )
        )
        write_intent_facts = bank_send_preparation_facts[
            "writeIntentFacts"
        ]
        migration_applied = MigrationRecorder.Migration.objects.filter(
            app="bank_send_preparation",
            name="0001_initial",
        ).exists()
        conditions = {
            "formalPaymentOrderCountIsEight":
                source_formal_payment_order_count == 8,
            "bankSendPreparationCountIsEight": len(rows) == 8,
            "allPrepared": all(row["status"] == "prepared" for row in rows),
            "allGatesEligible": all(row["gate"]["eligible"] for row in rows),
            "allTransitionsReal": (
                transition_count == 8
                and all(
                    row["statusTransitionCount"] == 1
                    and row["stateMachineConsistent"]
                    for row in rows
                )
            ),
            "previewOnlyEnforced":
                write_intent_facts["previewOnlyEnforced"] is True,
            "previewWriteAllowed": (
                write_intent_facts["previewPreparationWriteCount"] >= 0
                and write_intent_facts["previewWriteAllowed"] is True
            ),
            "businessProgressWriteBlocked": (
                write_intent_facts[
                    "forbiddenBusinessProgressWriteCount"
                ]
                == 0
                and write_intent_facts[
                    "businessProgressWriteBlocked"
                ]
                is True
            ),
            "operatorAllowed": operator_decision["granted"] is True,
            "viewerDenied": viewer_decision["granted"] is False,
            "outscopeDenied": outscope_decision["granted"] is False,
            "downstreamZero": all(value == 0 for value in counts.values()),
            "migrationApplied": migration_applied,
            "productionRolloutDisabled": not getattr(
                settings,
                "PCE_BANK_SEND_PREPARATION_PRODUCTION_ROLLOUT_ENABLED",
                False,
            ),
        }
        report = {
            "result": (
                "passed" if all(conditions.values()) else "failed"
            ),
            "version": VERSION,
            "canonicalName": "银行发送准备",
            "sourceDocumentType": "formalPaymentOrder",
            "currentStateSource": "server",
            "formalPaymentOrderCount":
                source_formal_payment_order_count,
            "bankSendPreparationCount": len(rows),
            "preparedCount": sum(
                row["status"] == "prepared" for row in rows
            ),
            "eligibleCount": sum(row["gate"]["eligible"] for row in rows),
            "bankSendGateCount": BankSendGate.objects.filter(
                preparation__tenant_id=tenant_id,
            ).count(),
            "previewCount": len(preview_ids),
            "previewStatuses": sorted(
                set(
                    row["messagePreview"]["status"]
                    for row in rows
                    if row["messagePreview"]["exists"]
                )
            ),
            "writeIntentFacts": write_intent_facts,
            "bankSendPreparationFacts": bank_send_preparation_facts,
            "previewPreparationWriteCount": write_intent_facts[
                "previewPreparationWriteCount"
            ],
            "auditWriteCount": write_intent_facts["auditWriteCount"],
            "forbiddenBusinessProgressWriteCount": write_intent_facts[
                "forbiddenBusinessProgressWriteCount"
            ],
            "statusTransitionCount": transition_count,
            "committedTransactionCount": transaction_count,
            "committedIdempotencyCount": idempotency_count,
            "committedAuditCount": audit_count,
            "permission": {
                "operatorPreviewGranted": operator_decision["granted"],
                "viewerPreviewGranted": viewer_decision["granted"],
                "outscopePreviewGranted": outscope_decision["granted"],
                "serverValidationRequired": True,
                "frontendVisibilityIsAuthority": False,
            },
            "conditions": conditions,
            "downstreamCounts": counts,
            "bankSendCreated": False,
            "bankMessageSent": False,
            "paymentExecuted": False,
            "fundsDebited": False,
            "bankTransactionCreated": False,
            "productionUserDataWritten": False,
            "rows": rows,
        }
        self.stdout.write(
            json.dumps(report, ensure_ascii=False, sort_keys=True)
        )
        if report["result"] != "passed":
            raise CommandError(
                "V58 read-only acceptance facts are inconsistent"
            )
