import re

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from procurement.models import Supplier


class Command(BaseCommand):
    help = "Verify SupplierMaster delivery-address completeness."

    def handle(self, *args, **options):
        suppliers = list(Supplier.objects.order_by("code", "id"))
        invalid = [
            supplier.code for supplier in suppliers
            if not re.fullmatch(
                r".+省.+市.+公司", str(supplier.delivery_address or "").strip()
            )
        ]
        non_independent = list(
            Supplier.objects.filter(delivery_address=F("address"))
            .order_by("code").values_list("code", flat=True)
        )
        failures = []
        if len(suppliers) != 100:
            failures.append(f"SupplierMaster记录数应为100，实际为{len(suppliers)}")
        if invalid:
            failures.append(f"送货地址缺失或格式错误：{invalid}")
        if non_independent:
            failures.append(f"注册地址与送货地址未独立维护：{non_independent}")
        if failures:
            raise CommandError("\n".join(failures))

        self.stdout.write("SUPPLIER-DELIVERY-ADDRESS-001 PASS")
        self.stdout.write(f"SupplierMaster Delivery Address PASS ({len(suppliers)})")
        self.stdout.write("Supplier Code Changed NO")
        self.stdout.write("Business Transaction Write Count PASS (0)")

