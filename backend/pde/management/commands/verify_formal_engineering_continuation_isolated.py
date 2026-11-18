import json
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pde.formal_engineering_continuation_service import (
    FORMAL_RULE_PACKAGES,
    FormalEngineeringContinuationService,
)
import pde.formal_engineering_continuation_service as continuation_module
from pde.models import (
    EngineeringCalculationDetail,
    EngineeringCalculationRecord,
    EngineeringDerivedFact,
    EngineeringMaterialRequirement,
    EngineeringOperationRequirement,
    EngineeringRuleDefinition,
    EngineeringSourceRecord,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
)
from pde.production_foundation_service import EngineeringLifecycleService
from system.models import OrganizationOperatingAuditRecord, User


PROTECTED_DATABASE = Path(
    "D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3"
).resolve()
DEVELOPER_DATABASE = Path("D:/Dev-PCE/Source/backend/db.sqlite3").resolve()


class Command(BaseCommand):
    help = "Run the formal engineering continuation write chain only on an explicit isolated SQLite copy."

    def add_arguments(self, parser):
        parser.add_argument("--execution-username", required=True)
        parser.add_argument("--source-username", required=True)
        parser.add_argument("--order-no", default="SO202609180003")
        parser.add_argument("--baseline-no", default="EB-SO202609180003-002")
        parser.add_argument("--source-record-id", type=int, default=11)
        parser.add_argument("--confirm-isolated", action="store_true")

    @staticmethod
    def _database_path():
        return Path(settings.DATABASES["default"]["NAME"]).resolve()

    def _guard(self, confirmed):
        database = self._database_path()
        if not confirmed:
            raise CommandError("--confirm-isolated is required")
        if database in {PROTECTED_DATABASE, DEVELOPER_DATABASE}:
            raise CommandError("Protected acceptance and developer databases are forbidden")
        if database.suffix.lower() != ".sqlite3" or "isolated" not in database.name.lower():
            raise CommandError("Database filename must identify an isolated .sqlite3 copy")
        return database

    @staticmethod
    def _counts(queryset):
        return {
            "calculations": queryset.count(),
            "details": EngineeringCalculationDetail.objects.filter(calculation__in=queryset).count(),
            "derivedFacts": EngineeringDerivedFact.objects.filter(calculation__in=queryset).count(),
            "materialRequirements": EngineeringMaterialRequirement.objects.filter(calculation__in=queryset).count(),
            "operationRequirements": EngineeringOperationRequirement.objects.filter(calculation__in=queryset).count(),
        }

    def handle(self, *args, **options):
        database = self._guard(options["confirm_isolated"])
        execution_user = User.objects.get(username=options["execution_username"])
        source_user = User.objects.get(username=options["source_username"])
        order_no = options["order_no"]
        baseline = OrderEngineeringBaseline.objects.get(
            company_id=execution_user.company_id,
            sales_order__order_no=order_no,
            baseline_no=options["baseline_no"],
        )
        source = EngineeringSourceRecord.objects.get(
            company_id=execution_user.company_id, pk=options["source_record_id"]
        )
        if source.status == "draft":
            EngineeringLifecycleService.transition(
                "engineering-source-records",
                object_id=source.pk,
                target_status="confirmed",
                user=source_user,
                reason="隔离验证：通过正式来源状态机确认工程来源",
            )
        source.refresh_from_db()

        facts = FormalEngineeringContinuationService.facts(user=execution_user, order_no=order_no)
        if [row["designObjectCount"] for row in facts["lines"]] != [5, 3, 62, 1]:
            raise CommandError("Unexpected design object distribution")
        if facts["designObjectCount"] != 71:
            raise CommandError("Expected 71 design objects")
        if {f"{row['ruleCode']}@{row['version']}" for row in facts["formalRulePackages"]} != {
            f"{code}@{spec['version']}" for code, spec in FORMAL_RULE_PACKAGES.items()
        }:
            raise CommandError("The two released formal rule packages are required")

        rows = []
        for line in facts["lines"]:
            create_result = FormalEngineeringContinuationService.create_instance(
                user=execution_user,
                sales_order_item_id=line["salesOrderItemId"],
                idempotency_key=f"formal-continuation-isolated:{order_no}:{line['salesOrderItemId']}",
                reason="隔离验证：形成订单行工程实例",
            )
            instance = OrderEngineeringInstance.objects.get(
                sales_order_item_id=line["salesOrderItemId"]
            )
            if instance.status == "draft":
                FormalEngineeringContinuationService.confirm_instance_source(
                    user=execution_user,
                    engineering_instance_id=instance.pk,
                    reason="隔离验证：确认实例采用已确认工程来源",
                )
                instance.refresh_from_db()
            validation = FormalEngineeringContinuationService.validate(
                user=execution_user,
                sales_order_item_id=line["salesOrderItemId"],
                engineering_instance_id=instance.pk,
                baseline_id=baseline.pk,
            )
            if not validation["ready"]:
                raise CommandError(f"Line {line['lineNo']} validation is blocked")
            execution = FormalEngineeringContinuationService.execute(
                user=execution_user,
                sales_order_item_id=line["salesOrderItemId"],
                engineering_instance_id=instance.pk,
                baseline_id=baseline.pk,
                reason="隔离验证：按实例执行对象级正式工程核算",
            )
            retry = FormalEngineeringContinuationService.execute(
                user=execution_user,
                sales_order_item_id=line["salesOrderItemId"],
                engineering_instance_id=instance.pk,
                baseline_id=baseline.pk,
                reason="隔离验证：同一请求重试",
            )
            calculation = EngineeringCalculationRecord.objects.get(pk=execution["calculation"]["id"])
            trace = calculation.trace
            rows.append({
                "lineNo": line["lineNo"],
                "salesOrderItemId": line["salesOrderItemId"],
                "instanceId": instance.pk,
                "instanceNo": instance.instance_no,
                "instanceStatus": instance.status,
                "instanceCreatedNow": not create_result.get("idempotent", False),
                "objectCount": validation["selection"]["objectCount"],
                "resultPositionCount": validation["selection"]["resultPositionCount"],
                "calculationId": calculation.pk,
                "calculationNo": calculation.calculation_no,
                "calculationStatus": calculation.status,
                "baselineReference": trace.get("baselineReference"),
                "objectInputSnapshotHash": trace.get("objectInputSnapshotHash"),
                "ruleGraphSnapshot": trace.get("ruleGraphSnapshot"),
                "detailCount": calculation.details.count(),
                "derivedFactCount": calculation.derived_facts.count(),
                "retryIdempotent": retry.get("idempotent"),
                "retryCalculationId": retry["calculation"]["id"],
            })

        calculations = EngineeringCalculationRecord.objects.filter(
            company_id=execution_user.company_id,
            sales_order_item__sales_order__order_no=order_no,
        )
        persisted = self._counts(calculations)
        if sum(row["resultPositionCount"] for row in rows) != 388:
            raise CommandError("Expected 388 result positions")
        if persisted != {
            "calculations": 4,
            "details": 388,
            "derivedFacts": 388,
            "materialRequirements": 0,
            "operationRequirements": 0,
        }:
            raise CommandError(f"Unexpected persisted counts: {persisted}")
        if any(not row["retryIdempotent"] or row["retryCalculationId"] != row["calculationId"] for row in rows):
            raise CommandError("Idempotency replay did not return the original calculation")

        # Force a failure after the calculation aggregate is inserted. The local
        # hash wrapper changes only the final idempotency payload for this probe;
        # persisted baseline, input and released rule definitions remain untouched.
        # The patched first detail insert then proves the atomic block rolls back.
        rollback_target = OrderEngineeringInstance.objects.get(pk=rows[0]["instanceId"])
        rollback_before = self._counts(calculations)
        rollback_error = None
        original_hash = continuation_module._hash

        def isolated_probe_hash(value):
            digest = original_hash(value)
            if isinstance(value, dict) and {"engineeringInstanceId", "baselineId", "ruleGraphHash"}.issubset(value):
                return original_hash({"original": digest, "isolatedAtomicityProbe": True})
            return digest

        try:
            with mock.patch.object(continuation_module, "_hash", side_effect=isolated_probe_hash), mock.patch.object(
                EngineeringCalculationDetail.objects, "create", side_effect=RuntimeError("ISOLATED_ATOMICITY_PROBE")
            ):
                FormalEngineeringContinuationService.execute(
                    user=execution_user,
                    sales_order_item_id=rollback_target.sales_order_item_id,
                    engineering_instance_id=rollback_target.pk,
                    baseline_id=baseline.pk,
                    reason="隔离验证：事务回滚探针",
                )
        except RuntimeError as exc:
            rollback_error = str(exc)
        rollback_after = self._counts(calculations)
        if rollback_error != "ISOLATED_ATOMICITY_PROBE" or rollback_after != rollback_before:
            raise CommandError(
                f"Atomic rollback proof failed: error={rollback_error}, before={rollback_before}, after={rollback_after}"
            )

        baseline.refresh_from_db()
        source.refresh_from_db()
        rule_ids = [row["id"] for row in facts["formalRulePackages"]]
        audit_count = OrganizationOperatingAuditRecord.objects.filter(
            organization_id=execution_user.company_id,
            action_code="production.engineering.calculation.execute",
            target_type="EngineeringCalculationRecord",
            target_id__in=list(calculations.values_list("pk", flat=True)),
        ).count()
        result = {
            "result": "PASSED",
            "database": str(database),
            "protectedAcceptanceDatabaseWritten": False,
            "orderNo": order_no,
            "companyId": execution_user.company_id,
            "source": {"id": source.pk, "status": source.status, "actor": source_user.username},
            "baseline": {
                "id": baseline.pk,
                "baselineNo": baseline.baseline_no,
                "status": baseline.status,
                "itemCount": baseline.scope_item_count,
                "candidateHash": baseline.candidate_hash,
                "snapshotHash": baseline.snapshot_hash,
            },
            "rules": list(EngineeringRuleDefinition.objects.filter(pk__in=rule_ids).values(
                "id", "rule_code", "version", "status"
            )),
            "executionActor": execution_user.username,
            "lines": rows,
            "objectDistribution": [row["objectCount"] for row in rows],
            "objectCount": sum(row["objectCount"] for row in rows),
            "resultPositionCount": sum(row["resultPositionCount"] for row in rows),
            "persisted": persisted,
            "calculationAuditCount": audit_count,
            "atomicity": {
                "forcedError": rollback_error,
                "before": rollback_before,
                "after": rollback_after,
                "partialWriteCount": 0,
            },
            "boundaries": {
                "modelAdded": False,
                "migrationAdded": False,
                "materialRequirementCreated": False,
                "bomCreatedByThisChain": False,
                "downstreamExecuted": False,
            },
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
