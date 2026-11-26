import json

from django.core.management.base import BaseCommand, CommandError

from purchase_canary.models import PurchaseCanaryBatch

from payment_request_prepare.models import (
    PayeeBankAccountAuthority,
    PayerBankAccountAuthority,
    PaymentCalendarAuthority,
    PaymentHoldAuthority,
    PaymentMethodAuthority,
    PaymentRequestPrepare,
    PaymentRequestPrepareCanaryScenario,
)
from payment_request_prepare.services import VERSION, serialize_prepare


BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"


class Command(BaseCommand):
    help = "Emit the immutable V47 checkpoint snapshot as JSON"

    def handle(self, *args, **options):
        batch = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).first()
        if not batch:
            raise CommandError(f"Missing prerequisite batch: {BATCH_ID}")
        lineages = list(
            batch.lineages.filter(
                current_module_code="payment-request-prepare"
            ).order_by("scenario_code")
        )
        objects = {
            obj.pk: obj
            for obj in PaymentRequestPrepare.objects.filter(
                tenant_id=TENANT_ID
            ).select_related(
                "source_payable_confirmation_prepare",
                "source_snapshot",
                "number_reservation",
                "business_transaction",
                "audit_record",
            ).prefetch_related(
                "payment_data_snapshots",
                "validation_executions__issues",
            )
        }
        prepares = []
        for lineage in lineages:
            obj = objects.get(lineage.current_object_id)
            if not obj:
                raise CommandError(
                    f"Missing V47 target for {lineage.canary_lineage_id}"
                )
            row = serialize_prepare(obj)
            row.update({
                "canaryLineageId": lineage.canary_lineage_id,
                "scenarioCode": lineage.scenario_code,
                "scenarioRole": lineage.scenario_role,
                "downstreamEligible": lineage.downstream_eligible,
                "reservedForNextModule": lineage.reserved_for_next_module,
                "nextStageConsumed": lineage.next_stage_consumed,
                "sourceRelationHash": lineage.source_relation_hash,
                "upstreamObjectNos": lineage.upstream_object_nos,
                "sourceSnapshot": {
                    "id": obj.source_snapshot.pk,
                    "sourceConfirmationHash": obj.source_snapshot.source_confirmation_hash,
                    "sourceAccountingHash": obj.source_snapshot.source_accounting_hash,
                    "sourceValidationHash": obj.source_snapshot.source_validation_hash,
                    "sourceEligibilityHash": obj.source_snapshot.source_eligibility_hash,
                },
            })
            prepares.append(row)
        blocked = list(
            PaymentRequestPrepareCanaryScenario.objects.filter(
                batch_id=BATCH_ID
            ).order_by("scenario_code").values(
                "scenario_code",
                "scenario_role",
                "blocking_module",
                "blocking_rule_code",
                "blocking_reason",
                "current_last_valid_object_no",
                "formal_object_count",
                "next_step_allowed",
                "scenario_hash",
            )
        )
        production_count = PaymentRequestPrepare.objects.exclude(
            tenant_id=TENANT_ID
        ).count()
        eligible_count = sum(
            1 for row in prepares
            if row["eligibility"]["eligible"] and row["downstreamEligible"]
        )
        payload = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": "付款申请准备",
            "sourceDocumentType": "payableConfirmationPrepare",
            "currentStateSource": "server",
            "canaryBatchId": BATCH_ID,
            "formalPaymentRequestPrepareCount": len(prepares),
            "downstreamEligibleSourceCount": eligible_count,
            "nextStageConsumedCount": sum(
                1 for row in prepares if row["nextStageConsumed"]
            ),
            "blockedScenarioCount": len(blocked),
            "nextModuleCode": "payment_request",
            "paymentRequestCreated": False,
            "productionTenantFormalObjectCount": production_count,
            "authorityCounts": {
                "payeeBankAccounts": PayeeBankAccountAuthority.objects.count(),
                "payerBankAccounts": PayerBankAccountAuthority.objects.count(),
                "paymentMethods": PaymentMethodAuthority.objects.count(),
                "paymentCalendarDates": PaymentCalendarAuthority.objects.count(),
                "paymentHolds": PaymentHoldAuthority.objects.count(),
            },
            "prepares": prepares,
            "blockedScenarios": blocked,
        }
        if (
            len(prepares) < 8
            or eligible_count < 8
            or payload["nextStageConsumedCount"] != 0
            or len(blocked) < 12
            or production_count != 0
        ):
            raise CommandError(json.dumps(payload, ensure_ascii=False))
        self.stdout.write(
            json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )
