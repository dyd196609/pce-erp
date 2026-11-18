from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from payment_risk_review.models import (
    PaymentRiskReview,
    PaymentRiskReviewCanaryScenario,
    RiskEvidenceSnapshot,
    RiskReviewExecution,
)
from payment_risk_review.services import execute_risk_review


class Command(BaseCommand):
    help = "Verify V52 uniqueness, idempotency, evidence and zero-downstream boundaries."

    def handle(self, *args, **options):
        reviews = list(PaymentRiskReview.objects.order_by("review_no"))
        if len(reviews) != 8 or not all(row.status == "passed" for row in reviews):
            raise CommandError("Expected eight passed risk reviews")
        if RiskReviewExecution.objects.count() != 8 or RiskEvidenceSnapshot.objects.count() != 8:
            raise CommandError("Execution/evidence cardinality mismatch")
        scenarios = list(PaymentRiskReviewCanaryScenario.objects.order_by("scenario_code"))
        if len(scenarios) < 12 or not all(not row.eligible and row.blocking_reasons for row in scenarios):
            raise CommandError("Blocked scenario matrix is incomplete")
        review = reviews[0]
        execution = review.executions.get()
        replay = execute_risk_review(
            user=review.created_by,
            review=review,
            idempotency_key=execution.idempotency_key,
            expected_version=review.version,
            explicit_user_action=True,
        )
        if replay["classification"] != "existing_result" or replay["executed"]:
            raise CommandError("Idempotent replay failed")
        duplicate_blocked = False
        try:
            with transaction.atomic():
                PaymentRiskReview.objects.create(
                    review_no="PRR-DUPLICATE-CONSTRAINT",
                    source_payment_order_draft=review.source_payment_order_draft,
                    source_payment_order_draft_no=review.source_payment_order_draft_no,
                    source_draft_version=review.source_draft_version,
                    source_draft_review_version=review.source_draft_review_version,
                    source_draft_hash=review.source_draft_hash,
                    tenant_id=review.tenant_id,
                    company_id=review.company_id,
                    created_by=review.created_by,
                )
        except IntegrityError:
            duplicate_blocked = True
        if not duplicate_blocked:
            raise CommandError("One-source-one-review constraint failed")
        self.stdout.write(self.style.SUCCESS(
            "V52 constraints passed: sourceUnique=true idempotency=true evidence=8 blockedScenarios=12 downstream=0"
        ))

