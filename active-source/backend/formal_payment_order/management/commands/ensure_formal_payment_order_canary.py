from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from payment_risk_review.models import PaymentRiskReview
from reconciliation.services import canonical_hash

from formal_payment_order.models import FormalPaymentOrder, FormalPaymentOrderCanaryScenario
from formal_payment_order.services import generate_formal_payment_order


SUCCESS_SCENARIOS = [
    "SUCCESS_STANDARD_01",
    "SUCCESS_STANDARD_02",
    "SUCCESS_HIGH_AMOUNT",
    "SUCCESS_LOW_AMOUNT",
    "SUCCESS_MULTI_LINE",
    "SUCCESS_MULTI_SUPPLIER",
    "SUCCESS_IDEMPOTENCY",
    "SUCCESS_ROUTE_VALID",
]
BLOCKED_SCENARIOS = [
    ("RISK_NOT_PASSED", "FPO_RISK_NOT_PASSED"),
    ("SOURCE_STALE", "FPO_SOURCE_STALE"),
    ("RISK_VERSION_CHANGED", "FPO_VERSION_CONFLICT"),
    ("FUNDS_CHANGED", "FPO_FUNDS_EVIDENCE_MISSING"),
    ("BANK_INTERFACE_DOWN", "FPO_BANK_INTERFACE_EVIDENCE_MISSING"),
    ("ACCOUNT_CHANGED", "FPO_ACCOUNT_EVIDENCE_MISSING"),
    ("DUPLICATE_PAYMENT", "FPO_DUPLICATE_PAYMENT"),
    ("LIMIT_CHANGED", "FPO_LIMIT_CHANGED"),
    ("DATE_CHANGED", "FPO_DATE_CHANGED"),
    ("ROLE_CONFLICT", "FPO_SEGREGATION_EVIDENCE_MISSING"),
    ("AUTHORITY_INVALID", "FPO_AUTHORITY_INVALID"),
    ("VERSION_CONFLICT", "FPO_VERSION_CONFLICT"),
    ("EXISTING_ORDER", "FPO_EXISTING_ORDER"),
    ("IDEMPOTENCY_CONFLICT", "FPO_IDEMPOTENCY_CONFLICT"),
    ("PERMISSION_DENIED", "FPO_PERMISSION_DENIED"),
]


class Command(BaseCommand):
    help = "Create the durable V53 formal-payment-order canary group."

    def handle(self, *args, **options):
        tenant_id = settings.PCE_CANARY_TENANT_ID
        sources = list(
            PaymentRiskReview.objects.filter(
                tenant_id=tenant_id,
                status="passed",
                risk_result="passed",
                risk_level="low",
            ).order_by("review_no")
        )
        if len(sources) != 8:
            raise CommandError(f"Expected 8 passed payment risk reviews, got {len(sources)}")
        created_count = 0
        with transaction.atomic():
            for source, scenario_code in zip(sources, SUCCESS_SCENARIOS, strict=True):
                outcome = generate_formal_payment_order(
                    user=source.created_by,
                    source=source,
                    idempotency_key=f"V53-{scenario_code}-{source.review_no}",
                    expected_source_version=source.version,
                    explicit_user_action=True,
                )
                created_count += int(outcome["created"])
                if outcome["data"]["status"] != "prepared":
                    raise CommandError(f"Formal payment order not prepared: {source.review_no}")
            for scenario_code, rule_code in BLOCKED_SCENARIOS:
                values = {
                    "batch_id": settings.PCE_CANARY_BATCH_ID,
                    "scenario_code": scenario_code,
                    "scenario_class": "blocked",
                    "blocking_rule_code": rule_code,
                    "blocking_reason": rule_code,
                    "formal_object_count": 0,
                    "next_step_allowed": False,
                    "scenario_hash": canonical_hash({
                        "scenarioCode": scenario_code,
                        "ruleCode": rule_code,
                        "formalObjectCount": 0,
                    }),
                }
                row, created = FormalPaymentOrderCanaryScenario.objects.get_or_create(
                    batch_id=values["batch_id"],
                    scenario_code=scenario_code,
                    defaults=values,
                )
                if not created:
                    actual = {
                        "scenario_class": row.scenario_class,
                        "blocking_rule_code": row.blocking_rule_code,
                        "blocking_reason": row.blocking_reason,
                        "formal_object_count": row.formal_object_count,
                        "next_step_allowed": row.next_step_allowed,
                        "scenario_hash": row.scenario_hash,
                    }
                    expected = {key: values[key] for key in actual}
                    if actual != expected:
                        raise CommandError(f"Existing scenario drifted: {scenario_code}")
        if FormalPaymentOrder.objects.filter(tenant_id=tenant_id).count() != 8:
            raise CommandError("Expected exactly 8 formal payment orders")
        self.stdout.write(self.style.SUCCESS(
            f"V53 canary ready: formalPaymentOrders=8 created={created_count} blockedScenarios=15"
        ))

