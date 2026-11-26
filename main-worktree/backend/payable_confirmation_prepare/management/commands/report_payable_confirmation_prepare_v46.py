import json

from django.core.management.base import BaseCommand, CommandError

from purchase_canary.models import PurchaseCanaryBatch

from payable_confirmation_prepare.models import (
    PayableConfirmationCanaryScenario,
    PayableConfirmationPrepare,
)
from payable_confirmation_prepare.services import (
    build_payment_request_prepare_eligibility,
)


VERSION = "V1.14.2.8.4.7.46"
BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"


class Command(BaseCommand):
    help = "Emit the immutable V46 checkpoint snapshot as JSON"

    def handle(self, *args, **options):
        batch = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).first()
        if not batch:
            raise CommandError(f"Missing prerequisite canary batch: {BATCH_ID}")

        lineages = list(
            batch.lineages.filter(
                current_module_code="payable-confirmation-prepare"
            ).order_by("scenario_code")
        )
        prepares_by_id = {
            row.pk: row
            for row in PayableConfirmationPrepare.objects.filter(
                tenant_id=TENANT_ID
            ).select_related(
                "source_purchase_accounts_payable_draft",
                "number_reservation",
                "business_transaction",
                "audit_record",
                "accounting_snapshot",
            )
        }
        rows = []
        for lineage in lineages:
            prepare = prepares_by_id.get(lineage.current_object_id)
            if not prepare:
                raise CommandError(
                    f"Missing prepare for lineage {lineage.canary_lineage_id}"
                )
            execution = prepare.validation_executions.get(
                validation_version=prepare.validation_version
            )
            source_relation = prepare.source_relations.get(
                source_type="purchaseAccountsPayableDraft",
                source_id=prepare.source_purchase_accounts_payable_draft_id,
            )
            eligibility = build_payment_request_prepare_eligibility(prepare)
            rows.append({
                "id": prepare.pk,
                "prepareNo": prepare.prepare_no,
                "status": prepare.status,
                "sourceDocumentType": prepare.source_document_type,
                "sourceDraftId": prepare.source_purchase_accounts_payable_draft_id,
                "sourceDraftNo": prepare.source_draft_no,
                "sourceDraftVersion": prepare.source_draft_version,
                "sourceKey": prepare.source_key,
                "sourceSnapshotHash": prepare.source_snapshot_hash,
                "accountingDataVersion": prepare.accounting_data_version,
                "accountingSnapshotId": prepare.accounting_snapshot.pk,
                "accountingSnapshotHash": prepare.accounting_snapshot.snapshot_hash,
                "validationVersion": prepare.validation_version,
                "validationExecutionId": execution.pk,
                "validationStatus": prepare.validation_status,
                "validationResultCode": prepare.validation_result_code,
                "validationIssueCount": prepare.validation_issue_count,
                "paymentTermsCode": prepare.payment_terms_code,
                "paymentTermsDays": prepare.payment_terms_days,
                "dueDate": prepare.due_date.isoformat(),
                "accountingDate": prepare.accounting_date.isoformat(),
                "accountingPeriod": prepare.accounting_period,
                "debitTotal": str(prepare.debit_total),
                "creditTotal": str(prepare.credit_total),
                "idempotencyKey": prepare.idempotency_key,
                "numberReservationId": prepare.number_reservation_id,
                "numberReservationStatus": prepare.number_reservation.status,
                "transactionId": prepare.business_transaction.transaction_id,
                "transactionStatus": prepare.business_transaction.commit_status,
                "auditRecordId": prepare.audit_record_id,
                "auditStatus": prepare.audit_record.result,
                "sourceRelationId": source_relation.pk,
                "sourceRelationHash": lineage.source_relation_hash,
                "eligibility": eligibility,
                "canaryLineageId": lineage.canary_lineage_id,
                "scenarioCode": lineage.scenario_code,
                "scenarioRole": lineage.scenario_role,
                "downstreamEligible": lineage.downstream_eligible,
                "reservedForNextModule": lineage.reserved_for_next_module,
                "nextStageConsumed": lineage.next_stage_consumed,
                "upstreamObjectNos": lineage.upstream_object_nos,
            })

        blocked = list(
            PayableConfirmationCanaryScenario.objects.filter(
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
        production_count = PayableConfirmationPrepare.objects.exclude(
            tenant_id=TENANT_ID
        ).count()
        payload = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": "应付确认准备",
            "sourceDocumentType": "purchaseAccountsPayableDraft",
            "canaryBatchId": BATCH_ID,
            "formalPayableConfirmationPrepareCount": len(rows),
            "downstreamEligibleSourceCount": sum(
                1 for row in rows
                if row["eligibility"]["eligible"]
                and row["downstreamEligible"]
            ),
            "nextStageConsumedCount": sum(
                1 for row in rows if row["nextStageConsumed"]
            ),
            "blockedScenarioCount": len(blocked),
            "nextModuleCode": "payment_request_prepare",
            "paymentRequestPrepareCreated": False,
            "productionTenantFormalObjectCount": production_count,
            "prepares": rows,
            "blockedScenarios": blocked,
        }
        if (
            len(rows) < 8
            or payload["downstreamEligibleSourceCount"] < 8
            or payload["nextStageConsumedCount"] != 0
            or len(blocked) < 8
            or production_count != 0
        ):
            raise CommandError(json.dumps(payload, ensure_ascii=False))
        self.stdout.write(
            json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )
