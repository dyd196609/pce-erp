from payment_risk_review.models import PaymentRiskReview

from .models import FormalPaymentOrder


class PaymentRiskReviewRepository:
    repository_code = "formal_payment_order_risk_review_repository"

    def queryset(self):
        return (
            PaymentRiskReview.objects.select_related(
                "source_payment_order_draft",
                "created_by",
            )
            .prefetch_related(
                "executions__issues",
                "evidence_snapshots",
            )
            .order_by("review_no")
        )

    def get(self, source_id):
        return self.queryset().filter(pk=source_id).first()

    def eligible(self, tenant_id):
        return self.queryset().filter(
            tenant_id=tenant_id,
            status="passed",
            risk_result="passed",
            risk_level="low",
        )


class FormalPaymentOrderRepository:
    repository_code = "formal_payment_order_repository"

    def queryset(self):
        return (
            FormalPaymentOrder.objects.select_related(
                "source_risk_review__source_payment_order_draft",
                "source_snapshot",
                "evidence_snapshot",
                "source_relation",
                "number_reservation",
                "business_transaction",
                "audit_record",
                "created_by",
                "approval__workflow_instance",
                "execution_freeze",
            )
            .prefetch_related(
                "approval__workflow_instance__tasks__decisions__actor",
            )
            .order_by("order_no")
        )

    def get(self, order_id):
        return self.queryset().filter(pk=order_id).first()

    def by_source(self, source_id):
        return self.queryset().filter(source_risk_review_id=source_id).first()
