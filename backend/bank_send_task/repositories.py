from .models import BankSendTask


class BankSendTaskRepository:
    repository_code = "bank_send_task_repository"

    def queryset(self):
        return (
            BankSendTask.objects.select_related(
                "source_preparation__source_formal_payment_order",
                "source_preparation__source_formal_payment_order__approval",
                "source_preparation__send_gate",
                "message_preview",
                "number_reservation",
                "business_transaction",
                "audit_record",
                "created_by",
            )
            .order_by("task_no")
        )

    def get(self, task_id):
        return self.queryset().filter(pk=task_id).first()

    def by_source(self, source_preparation_id):
        return self.queryset().filter(
            source_preparation_id=source_preparation_id
        ).first()


__all__ = ["BankSendTaskRepository"]
