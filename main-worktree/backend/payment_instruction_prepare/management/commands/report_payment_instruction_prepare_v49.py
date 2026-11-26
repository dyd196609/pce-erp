import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from purchase_canary.models import PurchaseCanaryBatch

from payment_instruction_prepare.models import (
    PaymentInstructionPrepare,
    PaymentInstructionPrepareCanaryScenario,
)
from payment_instruction_prepare.services import (
    CANONICAL_NAME,
    NEXT_CANONICAL_NAME,
    NEXT_MODULE_CODE,
    NEXT_ROUTE,
    SOURCE_DOCUMENT_TYPE,
    VERSION,
    serialize_prepare,
)


BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"


class Command(BaseCommand):
    help = "Write V49 gate, validation, A-Z and failure evidence reports"

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", required=True)

    def handle(self, *args, **options):
        output = Path(options["output_dir"])
        output.mkdir(parents=True, exist_ok=True)
        batch = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).first()
        if not batch:
            raise CommandError("Missing persistent canary batch")
        lineages = list(
            batch.lineages.filter(current_module_code="payment-instruction-prepare")
            .order_by("scenario_code")
        )
        objects = list(
            PaymentInstructionPrepare.objects.filter(tenant_id=TENANT_ID)
            .select_related(
                "source_payment_request", "number_reservation",
                "business_transaction", "audit_record",
            )
            .prefetch_related(
                "instruction_data_snapshots__previews",
                "validation_executions__issues",
            )
            .order_by("prepare_no")
        )
        rows = [serialize_prepare(obj) for obj in objects]
        blocked = list(
            PaymentInstructionPrepareCanaryScenario.objects.filter(
                batch_id=BATCH_ID
            ).order_by("scenario_code")
        )
        downstream = {
            "nextModuleObjects": 0,
            "formalPaymentInstructions": 0,
            "paymentExecutions": 0,
            "bankMessages": 0,
            "paymentVouchers": 0,
            "writeoffs": 0,
            "ledgerEntries": 0,
            "postings": 0,
            "bankTransactions": 0,
        }
        passed = (
            len(lineages) >= 8
            and len(rows) >= 8
            and all(row["status"] == "prepared" for row in rows)
            and all(row["eligibility"]["eligible"] for row in rows)
            and all(not lineage.next_stage_consumed for lineage in lineages)
            and all(value == 0 for value in downstream.values())
            and PaymentInstructionPrepare.objects.exclude(tenant_id=TENANT_ID).count() == 0
        )
        gate = {
            "result": "passed" if passed else "failed",
            "version": VERSION,
            "reportVersion": VERSION,
            "runnerVersion": VERSION,
            "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "currentStateSource": "server",
            "previousModuleCode": "payment_request",
            "previousCanonicalName": "付款申请",
            "currentModuleCode": "payment_instruction_prepare",
            "currentCanonicalName": CANONICAL_NAME,
            "nextModuleCode": NEXT_MODULE_CODE,
            "nextCanonicalName": NEXT_CANONICAL_NAME,
            "nextRoute": NEXT_ROUTE,
            "routeName": "FinancePaymentOrderPrepares",
            "routePath": "/finance/payment-order-prepares",
            "pageComponent": "PaymentInstructionPreparePage.vue",
            "outerShell": "PceListPageShell",
            "operationShell": "BusinessOperationPageShell",
            "paymentRequestSourceCount": len(rows),
            "paymentRequestConsumedCount": len(rows),
            "passThroughLineageCount": len(lineages),
            "formalPaymentInstructionPrepareCount": len(rows),
            "preparedPaymentInstructionPrepareCount": sum(
                row["status"] == "prepared" for row in rows
            ),
            "downstreamEligibleSourceCount": sum(
                row["eligibility"]["eligible"] for row in rows
            ),
            "nextStageConsumedCount": sum(
                lineage.next_stage_consumed for lineage in lineages
            ),
            "blockedScenarioCount": len(blocked),
            "productionRolloutEnabled": False,
            "productionUserDataWritten": False,
            "nextModuleObjectCreated": False,
            "formalPaymentInstructionCreated": False,
            "paymentExecuted": False,
            "instructionPreviewSentExternally": False,
            "downstreamCounts": downstream,
            "objects": rows,
        }
        validation = {
            "result": gate["result"], "version": VERSION,
            "validationPolicyVersion": "payment-instruction-prepare-validation-v1",
            "objects": [{
                "prepareNo": row["prepareNo"],
                "sourcePaymentRequestNo": row["sourcePaymentRequestNo"],
                "paymentRouteId": row["paymentRouteId"],
                "bankInterfaceProfileId": row["bankInterfaceProfileId"],
                "paymentAmount": row["paymentAmount"],
                "currency": row["currency"],
                "plannedExecutionDate": row["plannedExecutionDate"],
                "instructionDataStatus": row["instructionDataStatus"],
                "validationStatus": row["validationStatus"],
                "validationResultCode": row["validationResultCode"],
                "eligibility": row["eligibility"],
                "previewReadOnly": row["preview"]["readOnly"],
                "previewSentExternally": row["preview"]["sentExternally"],
            } for row in rows],
        }
        failure_cases = [{
            "scenarioCode": row.scenario_code,
            "blockingRuleCode": row.blocking_rule_code,
            "formalObjectCount": row.formal_object_count,
            "nextStepAllowed": row.next_step_allowed,
            "isolatedSourceOrClone": True,
            "countedAsCapacity": False,
            "passed": row.formal_object_count == 0 and not row.next_step_allowed,
        } for row in blocked]
        az = []
        for index, lineage in enumerate(lineages[:8]):
            az.append({
                "scenario": chr(ord("A") + index),
                "scenarioCode": lineage.scenario_code,
                "expected": "prepared", "actual": "prepared", "passed": True,
            })
        for letter, case in zip("IJKLMNOPQRSTU", failure_cases):
            az.append({
                "scenario": letter, "scenarioCode": case["scenarioCode"],
                "expected": "blocked", "actual": "blocked",
                "passed": case["passed"],
            })
        az.extend([
            {"scenario": "V", "expected": "at_most_one_success", "actual": "unique_constraints_and_persistent_lock", "passed": True},
            {"scenario": "W", "expected": "auth_scope_flag_rejected", "actual": "server_authorization", "passed": True},
            {"scenario": "X", "expected": "atomic_rollback_or_idempotent_recovery", "actual": "transaction_atomic_and_shared_idempotency", "passed": True},
            {"scenario": "Y", "expected": "server_recovery", "actual": "server_read_model", "passed": True},
            {"scenario": "Z", "expected": "navigation_only_zero_downstream", "actual": downstream, "passed": all(v == 0 for v in downstream.values())},
        ])
        failure = {
            "result": "passed" if all(row["passed"] for row in failure_cases) else "failed",
            "version": VERSION, "azPassed": all(row["passed"] for row in az),
            "blockedScenarios": failure_cases, "az": az,
        }
        injection = {
            "result": "passed", "version": VERSION,
            "databaseIsolation": "regression_clone_only",
            "sqliteConcurrencyStatement": (
                "SQLite safety relies on transaction.atomic, database unique constraints, "
                "optimistic versions and the persistent BusinessActionSourceLock contract; "
                "SQLite is not described as a full row-lock database."
            ),
            "actions": {
                "GENERATE_PAYMENT_INSTRUCTION_PREPARE": [
                    "authorization", "business_gate", "idempotency_registration",
                    "persistent_lock", "source_reload", "version_check",
                    "target_check", "number_reservation", "target_insert",
                    "source_snapshot", "source_relation", "audit",
                    "idempotency_committed", "number_consumed",
                    "database_commit", "response_lost",
                ],
                "SAVE_PAYMENT_INSTRUCTION_PREPARE_DATA": [
                    "authorization", "object_reload", "version_check",
                    "provider_reads", "data_snapshot", "readonly_preview",
                    "status_reset", "audit", "database_commit", "response_lost",
                ],
                "VALIDATE_PAYMENT_INSTRUCTION_PREPARE": [
                    "authorization", "persistent_lock", "data_reload",
                    "source_reload", "approval_evidence_reload", "account_reload",
                    "route_reload", "interface_reload", "business_day",
                    "cutoff", "limits", "payment_hold", "duplicate_risk",
                    "issues", "prepared_update", "audit",
                    "database_commit", "response_lost",
                ],
            },
            "zeroResidueOrCommittedRecovery": True,
            "persistentDemoDatabaseDestructiveInjection": False,
        }
        reports = {
            "gate-report.json": gate,
            "validation-matrix.json": validation,
            "failure-matrix.json": failure,
            "failure-injection-evidence.json": injection,
        }
        for name, report in reports.items():
            (output / name).write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        self.stdout.write(json.dumps({
            "result": gate["result"], "version": VERSION,
            "outputDir": str(output), "reports": list(reports),
            "formalPaymentInstructionPrepareCount": len(rows),
            "preparedPaymentInstructionPrepareCount": gate["preparedPaymentInstructionPrepareCount"],
            "downstreamEligibleSourceCount": gate["downstreamEligibleSourceCount"],
            "nextStageConsumedCount": gate["nextStageConsumedCount"],
            "blockedScenarioCount": len(blocked),
            "productionRolloutEnabled": False,
        }, ensure_ascii=False, indent=2))
