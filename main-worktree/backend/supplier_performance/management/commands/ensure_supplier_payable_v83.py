from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from supplier_performance.models import SupplierPayableConfirmation, SupplierPaymentRequest
from supplier_performance.services import ensure_v83_demo_data


class Command(BaseCommand):
    help = "Create isolated V83 supplier payable confirmation and payment request fixtures."

    def handle(self, *args, **options):
        operator, _ = get_user_model().objects.get_or_create(
            username="v83-payable-operator",
            defaults={
                "real_name": "V83 供应商应付操作员",
                "company_id": 1,
                "email": "v83@example.invalid",
                "is_active": True,
            },
        )
        ensure_v83_demo_data(operator)
        self.stdout.write(self.style.SUCCESS(
            f"payableConfirmations={SupplierPayableConfirmation.objects.count()} "
            f"paymentRequests={SupplierPaymentRequest.objects.count()} "
            "paymentExecutionWriteCount=0 bankSendWriteCount=0 financialImpactWriteCount=0"
        ))
