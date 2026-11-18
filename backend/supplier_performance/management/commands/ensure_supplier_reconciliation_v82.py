from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from supplier_performance.models import (
    BuyerPerformanceMetric,
    SupplierReconciliationConfirmation,
    SupplierReconciliationDifference,
)
from supplier_performance.services import ensure_v82_demo_data


class Command(BaseCommand):
    help = "Create isolated V82 difference and collaboration fixtures."

    def handle(self, *args, **options):
        operator, _ = get_user_model().objects.get_or_create(
            username="v82-settlement-operator",
            defaults={
                "real_name": "V82 差异分析操作员",
                "company_id": 1,
                "email": "v82@example.invalid",
                "is_active": True,
            },
        )
        ensure_v82_demo_data(operator)
        self.stdout.write(self.style.SUCCESS(
            f"differences={SupplierReconciliationDifference.objects.count()} "
            f"confirmations={SupplierReconciliationConfirmation.objects.count()} "
            f"buyerMetrics={BuyerPerformanceMetric.objects.count()} "
            "paymentWriteCount=0 bankSendWriteCount=0 financialImpactWriteCount=0"
        ))
