from payment_order_draft.models import PaymentOrderDraft

from .models import PaymentRiskReview


class PaymentOrderDraftRepository:
    repository_code = "payment_order_draft_risk_source_repository"

    def get(self, source_id):
        return (
            PaymentOrderDraft.objects.select_related(
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
            .filter(pk=source_id)
            .first()
        )

    def eligible(self, tenant_id):
        return (
            PaymentOrderDraft.objects.select_related("source_payment_order_prepare")
            .prefetch_related(
                "draft_data_snapshots__creation_previews",
                "authority_snapshots",
                "review_executions__issues",
            )
            .filter(tenant_id=tenant_id, status="reviewed", review_status="passed")
            .order_by("draft_no")
        )


class PaymentRiskReviewRepository:
    repository_code = "payment_risk_review_repository"

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

    def get(self, review_id):
        return self.queryset().filter(pk=review_id).first()

