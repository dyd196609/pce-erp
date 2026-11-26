from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from payment_order_draft.models import PaymentOrderDraft
from reconciliation.services import canonical_hash

from payment_risk_review.models import PaymentRiskReviewCanaryScenario
from payment_risk_review.services import ensure_review_for_source, execute_risk_review


SUCCESS_SCENARIOS = [
    "SUCCESS_01",
    "SUCCESS_02",
    "SUCCESS_03",
    "SUCCESS_04",
    "SUCCESS_05",
    "SUCCESS_06",
    "SUCCESS_07",
    "SUCCESS_08",
]
BLOCKED_SCENARIOS = [
    ("FUNDS_INSUFFICIENT", "PRR_FUNDS_AVAILABLE"),
    ("DUPLICATE_PAYMENT", "PRR_DUPLICATE_PAYMENT"),
    ("BANK_INTERFACE_DOWN", "PRR_BANK_INTERFACE"),
    ("PAYEE_ACCOUNT_DISABLED", "PRR_PAYEE_ACCOUNT"),
    ("SUPPLIER_BLOCKED", "PRR_SUPPLIER_ACTIVE"),
    ("AMOUNT_CHANGED", "PRR_SOURCE_VERSION_CURRENT"),
    ("SOURCE_STALE", "PRR_SOURCE_VERSION_CURRENT"),
    ("RULE_FAILED", "PRR_SOURCE_ELIGIBLE"),
    ("ROLE_CONFLICT", "PRR_MAKER_CHECKER"),
    ("LIMIT_EXCEEDED", "PRR_SINGLE_LIMIT"),
    ("DATE_RISK", "PRR_PAYMENT_DATE"),
    ("MANUAL_BLOCK", "PRR_MANUAL_BLOCK"),
]


class Command(BaseCommand):
    help = "Create the durable V52 payment-risk-review canary group."

    def handle(self, *args, **options):
        tenant_id = settings.PCE_CANARY_TENANT_ID
        sources = list(
            PaymentOrderDraft.objects.filter(
                tenant_id=tenant_id,
                status="reviewed",
                review_status="passed",
            ).order_by("draft_no")
        )
        if len(sources) != 8:
            raise CommandError(f"Expected 8 reviewed POD sources, got {len(sources)}")
        created_count = 0
        executed_count = 0
        with transaction.atomic():
            for source, scenario_code in zip(sources, SUCCESS_SCENARIOS, strict=True):
                review, created = ensure_review_for_source(
                    user=source.created_by,
                    source=source,
                    scenario_code=scenario_code,
                )
                created_count += int(created)
                outcome = execute_risk_review(
                    user=source.created_by,
                    review=review,
                    idempotency_key=f"V52-{scenario_code}-{source.draft_no}",
                    expected_version=review.version,
                    explicit_user_action=True,
                )
                executed_count += int(outcome["executed"])
                if outcome["data"]["status"] != "passed":
                    raise CommandError(f"Canary review did not pass: {source.draft_no}")
            for scenario_code, risk_code in BLOCKED_SCENARIOS:
                values = {
                    "batch_id": settings.PCE_CANARY_BATCH_ID,
                    "scenario_code": scenario_code,
                    "scenario_class": "blocked",
                    "risk_code": risk_code,
                    "risk_level": "high",
                    "blocking_reasons": [risk_code],
                    "eligible": False,
                    "formal_object_count": 0,
                    "scenario_hash": canonical_hash({
                        "scenarioCode": scenario_code,
                        "riskCode": risk_code,
                        "eligible": False,
                    }),
                }
                row, created = PaymentRiskReviewCanaryScenario.objects.get_or_create(
                    batch_id=values["batch_id"],
                    scenario_code=scenario_code,
                    defaults=values,
                )
                if not created:
                    actual = {
                        "scenario_class": row.scenario_class,
                        "risk_code": row.risk_code,
                        "risk_level": row.risk_level,
                        "blocking_reasons": row.blocking_reasons,
                        "eligible": row.eligible,
                        "formal_object_count": row.formal_object_count,
                        "scenario_hash": row.scenario_hash,
                    }
                    expected = {key: values[key] for key in actual}
                    if actual != expected:
                        raise CommandError(f"Existing scenario drifted: {scenario_code}")
        self.stdout.write(self.style.SUCCESS(
            f"V52 canary ready: reviews=8 created={created_count} executed={executed_count} blockedScenarios=12"
        ))
