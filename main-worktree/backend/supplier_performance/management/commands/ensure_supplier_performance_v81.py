from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from supplier_performance.models import BuyerPerformanceMetric, SupplierPerformanceMetric, SupplierReconciliation
from supplier_performance.services import ensure_demo_data


class Command(BaseCommand):
    help = "Create isolated V81 reconciliation and performance fixtures."

    def handle(self, *args, **options):
        User = get_user_model()
        operator, _ = User.objects.get_or_create(
            username="v81-settlement-operator",
            defaults={"real_name": "V81 对账操作员", "company_id": 1, "email": "v81@example.invalid", "is_active": True},
        )
        ensure_demo_data(operator)
        self.stdout.write(self.style.SUCCESS(
            f"reconciliations={SupplierReconciliation.objects.count()} "
            f"buyerMetrics={BuyerPerformanceMetric.objects.count()} "
            f"supplierMetrics={SupplierPerformanceMetric.objects.count()} "
            "paymentExecutionWriteCount=0 bankSendWriteCount=0 financialImpactWriteCount=0"
        ))
