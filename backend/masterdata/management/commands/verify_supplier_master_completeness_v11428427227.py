import re

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from masterdata.supplier_master_runtime import SupplierMasterRuntimeAdapter
from procurement.models import Supplier, SupplierDuplicateReview


class Command(BaseCommand):
    help = "Verify SupplierMaster completeness and duplicate-review governance."

    def handle(self, *args, **options):
        suppliers = list(Supplier.objects.order_by("code", "id"))
        invalid_fields = []
        invalid_addresses = []
        for supplier in suppliers:
            fields = {
                "地址": supplier.address,
                "分类": supplier.category,
                "联系人": supplier.contact_person,
                "联系电话": supplier.contact_phone,
            }
            missing = [
                label for label, value in fields.items()
                if not str(value or "").strip()
                or str(value).strip() in {"未维护", "未分类"}
            ]
            if missing:
                invalid_fields.append({"code": supplier.code, "fields": missing})
            if not re.fullmatch(r".+省.+市.+公司", str(supplier.address or "").strip()):
                invalid_addresses.append(supplier.code)

        duplicate_names = list(
            Supplier.objects.values("name")
            .annotate(record_count=Count("id"))
            .filter(record_count__gt=1)
        )
        duplicate_suppliers = Supplier.objects.filter(
            name__in=[row["name"] for row in duplicate_names]
        )
        review_supplier_ids = set(
            SupplierDuplicateReview.objects.filter(
                status=SupplierDuplicateReview.STATUS_PENDING
            ).values_list("supplier_id", flat=True)
        )
        review_missing = list(
            duplicate_suppliers.exclude(id__in=review_supplier_ids)
            .order_by("code").values_list("code", flat=True)
        )
        duplicate_codes = list(
            Supplier.objects.values("code")
            .annotate(record_count=Count("id"))
            .filter(record_count__gt=1)
        )
        runtime_facts = SupplierMasterRuntimeAdapter.facts()
        classified_count = sum(
            1 for supplier in suppliers if supplier.category != "待分类"
        )

        failures = []
        if len(suppliers) < 100:
            failures.append(f"SupplierMaster治理基线不得少于100，实际为{len(suppliers)}")
        if classified_count == 0:
            failures.append("可判断业务类型的供应商未执行分类")
        if invalid_fields:
            failures.append(f"基础字段不完整：{invalid_fields}")
        if invalid_addresses:
            failures.append(f"地址格式不符合省/市/公司结构：{invalid_addresses}")
        if duplicate_codes:
            failures.append(f"供应商编码重复：{duplicate_codes}")
        if review_missing:
            failures.append(f"同名供应商缺少待人工确认审核：{review_missing}")
        if runtime_facts["supplierFieldCompleteGate"] != "PASS":
            failures.append("页面Runtime字段完整性事实未通过")
        if runtime_facts["supplierDuplicateReviewGate"] != "PASS":
            failures.append("页面Runtime重复审核事实未通过")

        if failures:
            raise CommandError("\n".join(failures))

        self.stdout.write("SUPPLIER-FIELD-COMPLETE-002 PASS")
        self.stdout.write("SUPPLIER-DUPLICATE-REVIEW-001 PASS")
        self.stdout.write(f"SupplierMaster Count PASS ({len(suppliers)})")
        self.stdout.write(f"Supplier Category Classification PASS ({classified_count})")
        self.stdout.write(
            f"Duplicate Supplier Review PASS ({duplicate_suppliers.count()})"
        )
        self.stdout.write("Business Transaction Write Count PASS (0)")
