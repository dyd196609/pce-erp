from .models import BankSendRequest


class BankSendRequestRepository:
    def queryset(self):
        return BankSendRequest.objects.select_related(
            "source_gate__source_task__source_preparation__source_formal_payment_order",
            "source_gate__source_task__source_preparation__send_gate",
            "source_gate__source_task__message_preview",
            "business_transaction", "audit_record", "created_by",
        ).prefetch_related("pre_dispatch_validations").order_by("request_no")

    def get(self, request_id):
        return self.queryset().filter(pk=request_id).first()

    def by_source(self, gate_id):
        return self.queryset().filter(source_gate_id=gate_id).first()

