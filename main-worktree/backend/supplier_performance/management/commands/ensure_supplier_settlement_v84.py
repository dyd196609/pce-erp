from django.core.management.base import BaseCommand

from supplier_performance.services import ensure_v84_demo_data


class Command(BaseCommand):
    help = "Ensure isolated V84 supplier settlement closed-loop acceptance data"

    def handle(self, *args, **options):
        result = ensure_v84_demo_data()
        self.stdout.write(self.style.SUCCESS(
            "V84 supplier settlement ready "
            f"paymentStatusRecords={result['paymentStatusRecords']} "
            f"settlementCompletions={result['settlementCompletions']}"
        ))
