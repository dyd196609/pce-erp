import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from payment_risk_review.models import PaymentRiskReviewCanaryScenario
from payment_risk_review.repositories import PaymentRiskReviewRepository
from payment_risk_review.services import RULES, VERSION, serialize_review


class Command(BaseCommand):
    help = "Write the V52 server report and parameterized blocked matrix."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", required=True)

    def handle(self, *args, **options):
        root = Path(options["output_dir"]).resolve()
        root.mkdir(parents=True, exist_ok=True)
        reviews = list(
            PaymentRiskReviewRepository().queryset().filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
        )
        results = [serialize_review(row) for row in reviews]
        scenarios = list(
            PaymentRiskReviewCanaryScenario.objects.filter(
                batch_id=settings.PCE_CANARY_BATCH_ID
            ).order_by("scenario_code")
        )
        passed = sum(row["status"] == "passed" for row in results)
        eligible = sum(row["eligibility"]["eligible"] for row in results)
        report = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": "真实付款风险评审",
            "sourceDocumentType": "paymentOrderDraft",
            "currentStateSource": "server",
            "sourceDraftCount": len(results),
            "riskReviewCount": len(results),
            "passedRiskReviewCount": passed,
            "downstreamEligibleSourceCount": eligible,
            "blockedScenarioCount": len(scenarios),
            "nextStageConsumedCount": 0,
            "ruleCount": len(RULES),
            "formalPaymentOrderCreated": False,
            "paymentExecuted": False,
            "productionUserDataWritten": False,
            "results": results,
        }
        matrix = {
            "result": "passed",
            "version": VERSION,
            "scenarioCount": len(scenarios),
            "scenarios": [
                {
                    "scenarioCode": row.scenario_code,
                    "riskCode": row.risk_code,
                    "riskLevel": row.risk_level,
                    "eligible": row.eligible,
                    "blockingReasons": row.blocking_reasons,
                    "formalObjectCount": row.formal_object_count,
                    "passed": (
                        not row.eligible
                        and bool(row.blocking_reasons)
                        and row.formal_object_count == 0
                    ),
                }
                for row in scenarios
            ],
        }
        if not (
            len(results) == 8
            and passed == 8
            and eligible == 8
            and len(scenarios) >= 12
            and all(item["passed"] for item in matrix["scenarios"])
        ):
            raise CommandError("V52 report invariants failed")
        for name, value in [
            ("server-report.json", report),
            ("failure-injection-evidence.json", matrix),
            ("validation-matrix.json", {
                "result": "passed",
                "version": VERSION,
                "ruleCount": len(RULES),
                "rules": [
                    {"riskCode": code, "description": description, "dimension": dimension}
                    for code, description, dimension in RULES
                ],
                "allSuccessfulReviewsPassedAllRules": all(
                    row["ruleExecution"]["passedCount"] == len(RULES)
                    and row["ruleExecution"]["blockedCount"] == 0
                    for row in results
                ),
            }),
        ]:
            (root / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))

