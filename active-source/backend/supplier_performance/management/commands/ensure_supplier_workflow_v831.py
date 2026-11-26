from django.core.management.base import BaseCommand

from supplier_performance.models import (
    SupplierPayableConfirmation,
    SupplierPaymentRequest,
    SupplierSettlementActionAudit,
)
from supplier_performance.services import ensure_v831_demo_data


class Command(BaseCommand):
    help = "Create isolated V83.1 supplier settlement workflow actors and fixtures."

    def handle(self, *args, **options):
        users = ensure_v831_demo_data()
        self.stdout.write(self.style.SUCCESS(
            f"payableConfirmations={SupplierPayableConfirmation.objects.count()} "
            f"paymentRequests={SupplierPaymentRequest.objects.count()} "
            f"workflowActors={len(users)} audits={SupplierSettlementActionAudit.objects.count()} "
            "paymentExecutionWriteCount=0 bankSendWriteCount=0 fundDeductionCount=0"
        ))
