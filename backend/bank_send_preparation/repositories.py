from formal_payment_order.models import FormalPaymentOrder

from .models import BankSendPreparation


class FormalPaymentOrderSourceRepository:
    repository_code = "bank_send_preparation_formal_payment_order_repository"

    def queryset(self):
        return (
            FormalPaymentOrder.objects.select_related(
                "source_risk_review__source_payment_order_draft",
                "approval__workflow_instance",
                "execution_freeze",
                "evidence_snapshot",
                "created_by",
            )
            .prefetch_related(
                "approval__workflow_instance__tasks__decisions__actor",
            )
            .order_by("order_no")
        )

    def get(self, order_id):
        return self.queryset().filter(pk=order_id).first()


class BankSendPreparationRepository:
    repository_code = "bank_send_preparation_repository"

    def queryset(self):
        return (
            BankSendPreparation.objects.select_related(
                "source_formal_payment_order__source_risk_review__source_payment_order_draft",
                "source_formal_payment_order__approval__workflow_instance",
                "source_formal_payment_order__execution_freeze",
                "source_formal_payment_order__evidence_snapshot",
                "send_gate",
                "message_preview",
                "message_preview__audit_record",
                "send_task",
                "audit_record",
                "created_by",
            )
            .prefetch_related(
                "source_formal_payment_order__approval__workflow_instance__tasks__decisions__actor",
            )
            .order_by("prepare_no")
        )

    def get(self, preparation_id):
        return self.queryset().filter(pk=preparation_id).first()

    def by_source(self, source_id):
        return self.queryset().filter(
            source_formal_payment_order_id=source_id
        ).first()


__all__ = [
    "BankSendPreparationRepository",
    "FormalPaymentOrderSourceRepository",
]
