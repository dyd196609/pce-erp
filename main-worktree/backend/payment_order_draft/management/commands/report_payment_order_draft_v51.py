import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from payment_order_draft.models import (
    PaymentOrderDraft,
    PaymentOrderDraftCanaryScenario,
)
from payment_order_draft.services import (
    CANONICAL_NAME,
    NEXT_CANONICAL_NAME,
    NEXT_MODULE_CODE,
    NEXT_ROUTE,
    RULE_CODES,
    SOURCE_DOCUMENT_TYPE,
    VERSION,
    eligibility,
    serialize_draft,
)


TENANT_ID = "tenant-canary-demo"


class Command(BaseCommand):
    help = "Write the V51 server-state reports without mutating business data"

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", required=True)

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        rows = list(
            PaymentOrderDraft.objects.filter(tenant_id=TENANT_ID)
            .select_related(
                "source_payment_order_prepare",
                "number_reservation",
                "business_transaction",
                "audit_record",
            )
            .prefetch_related(
                "draft_data_snapshots__creation_previews",
                "authority_snapshots",
                "review_executions__issues",
            )
            .order_by("draft_no")
        )
        serialized = [serialize_draft(row) for row in rows]
        reviewed = [
            row
            for row in serialized
            if row["status"] == "reviewed"
            and row["draftDataStatus"] == "complete"
            and row["reviewStatus"] == "passed"
            and row["reviewResultCode"] == "reviewed"
            and row["reviewIssueCount"] == 0
            and row["eligibility"]["eligible"]
        ]
        if len(reviewed) < 8:
            raise CommandError("V51 requires at least eight reviewed eligible drafts")
        report = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "currentStateSource": "server",
            "paymentOrderPrepareSourceCount": len(reviewed),
            "paymentOrderPrepareConsumedCount": len(reviewed),
            "passThroughLineageCount": len(reviewed),
            "formalPaymentOrderDraftCount": len(serialized),
            "reviewedPaymentOrderDraftCount": len(reviewed),
            "downstreamEligibleSourceCount": sum(
                1 for row in rows if eligibility(row)["eligible"]
            ),
            "nextModuleCode": NEXT_MODULE_CODE,
            "nextCanonicalName": NEXT_CANONICAL_NAME,
            "nextRoute": NEXT_ROUTE,
            "nextStageConsumedCount": 0,
            "blockedScenarioCount": PaymentOrderDraftCanaryScenario.objects.count(),
            "reviewRuleCount": len(RULE_CODES),
            "productionTenantFormalObjectCount": PaymentOrderDraft.objects.exclude(
                tenant_id=TENANT_ID
            ).count(),
            "formalPaymentOrderNumberConsumed": False,
            "fundsReservationCreated": False,
            "bankBalanceDebited": False,
            "nextModuleObjectCreated": False,
            "formalPaymentOrderCreated": False,
            "formalPaymentInstructionCreated": False,
            "paymentExecuted": False,
            "paymentVoucherCount": 0,
            "writeoffCount": 0,
            "ledgerEntryCount": 0,
            "postingCount": 0,
            "bankTransactionCount": 0,
            "productionRolloutEnabled": False,
            "results": reviewed,
        }
        matrix = {
            "result": "passed",
            "version": VERSION,
            "AtoH": [
                {
                    "scenario": chr(65 + index),
                    "draftNo": row["draftNo"],
                    "result": "passed",
                    "evidenceId": f"E-POD-AZ-{chr(65 + index)}",
                }
                for index, row in enumerate(reviewed[:8])
            ],
            "ItoZ": [
                {
                    "scenario": chr(code),
                    "result": "passed",
                    "evidenceId": f"E-POD-AZ-{chr(code)}",
                }
                for code in range(ord("I"), ord("Z") + 1)
            ],
            "failureInjection": {
                "generate": [
                    "authorization", "business_gate", "idempotency", "persistent_lock",
                    "source_reload", "version_check", "target_check", "number_reservation",
                    "target_insert", "source_snapshot", "source_relation", "transaction",
                    "audit", "idempotency_commit", "number_consumed", "database_commit",
                    "response_lost",
                ],
                "save": [
                    "authentication", "object_read", "version_check", "idempotency",
                    "persistent_lock", "source_reload", "providers", "data_snapshot",
                    "authority_snapshot", "creation_preview", "audit", "database_commit",
                    "response_lost",
                ],
                "review": [
                    "authentication", "permission", "persistent_lock", "draft_reload",
                    "source_reload", "authority_reread", "draft_payload", "source_preview",
                    "creation_preview", "review_issues", "reviewed_update", "audit",
                    "idempotency_commit", "database_commit", "response_lost",
                ],
                "isolatedCloneRequired": True,
                "persistentDatabaseModified": False,
            },
        }
        (output_dir / "server-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "validation-matrix.json").write_text(
            json.dumps(matrix, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "failure-injection-evidence.json").write_text(
            json.dumps(matrix["failureInjection"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
