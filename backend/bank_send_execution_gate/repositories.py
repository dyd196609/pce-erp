from .models import BankSendExecutionGate


class BankSendExecutionGateRepository:
    repository_code = "bank_send_execution_gate_repository"

    def queryset(self):
        return (
            BankSendExecutionGate.objects.select_related(
                "source_task__source_preparation__source_formal_payment_order",
                "source_task__source_preparation__send_gate",
                "source_task__message_preview",
                "business_transaction",
                "audit_record",
                "created_by",
            )
            .order_by("gate_no")
        )

    def get(self, gate_id):
        return self.queryset().filter(pk=gate_id).first()

    def by_source(self, task_id):
        return self.queryset().filter(source_task_id=task_id).first()


__all__ = ["BankSendExecutionGateRepository"]
