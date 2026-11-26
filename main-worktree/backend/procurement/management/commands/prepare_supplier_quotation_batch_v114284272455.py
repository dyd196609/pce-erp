from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from procurement.purchase_inquiry_service import create_purchase_inquiry_from_request
from procurement.supplier_quotation_service import (
    save_supplier_quotation,
    submit_supplier_quotation,
)


class Command(BaseCommand):
    help = "Create governed development acceptance quotations through formal SCM services."

    REQUEST_IDS = (33, 32, 31, 30)

    def handle(self, *args, **options):
        inquiry_create_count = 0
        quotation_create_count = 0
        quotation_line_write_count = 0
        quotation_submit_count = 0
        quotation_numbers = []

        for request_id in self.REQUEST_IDS:
            inquiry, inquiry_created, _ = create_purchase_inquiry_from_request(
                request_id, "Codex Acceptance V1.14.2.8.4.27.2.45.5"
            )
            inquiry_create_count += int(inquiry_created)
            candidates = list((inquiry.quotation or {}).get("supplierCandidates") or [])
            if len(candidates) != 1:
                raise CommandError(f"EXPECTED_ONE_SUPPLIER_CANDIDATE:{inquiry.inquiry_no}")
            supplier_id = candidates[0].get("supplierId")
            if not supplier_id:
                raise CommandError(f"SUPPLIER_ID_REQUIRED:{inquiry.inquiry_no}")

            existing = inquiry.supplier_quotations.filter(
                supplier_id=str(supplier_id)
            ).first()
            if existing and existing.quotation_status == "received":
                source_codes = {
                    str(line.get("materialCode") or "") for line in inquiry.items or []
                }
                quoted_codes = {
                    str(line.get("materialCode") or "") for line in existing.items or []
                    if Decimal(str(line.get("unitPrice") or 0)) > 0
                }
                if source_codes != quoted_codes:
                    raise CommandError(
                        f"RECEIVED_SUPPLIER_QUOTATION_INCOMPLETE:{existing.quotation_no}"
                    )
                quotation_numbers.append(existing.quotation_no)
                continue

            quotation = None
            for line_index, line in enumerate(inquiry.items or [], start=1):
                material_code = str(line.get("materialCode") or "").strip()
                if not material_code:
                    raise CommandError(f"MATERIAL_CODE_REQUIRED:{inquiry.inquiry_no}:{line_index}")
                # Deterministic development acceptance price. It is entered through
                # SupplierQuotation, never copied from SupplierPriceFact/history.
                unit_price = Decimal("100") + Decimal(request_id) + Decimal(line_index)
                quotation, quotation_created = save_supplier_quotation(
                    inquiry.pk,
                    supplier_id,
                    material_code,
                    unit_price,
                    remark="V1.14.2.8.4.27.2.45.5 governed SupplierQuotation acceptance data",
                    currency="CNY",
                )
                quotation_create_count += int(quotation_created)
                quotation_line_write_count += 1

            if quotation is None:
                raise CommandError(f"SUPPLIER_QUOTATION_LINES_REQUIRED:{inquiry.inquiry_no}")
            if quotation.quotation_status != "received":
                quotation = submit_supplier_quotation(quotation.pk)
                quotation_submit_count += 1
            quotation_numbers.append(quotation.quotation_no)

        business_write_count = (
            inquiry_create_count
            + quotation_line_write_count
            + quotation_submit_count
        )
        self.stdout.write(self.style.SUCCESS("SUPPLIER_QUOTATION_BATCH_PREPARED"))
        self.stdout.write(f"quotationNumbers={','.join(quotation_numbers)}")
        self.stdout.write(f"inquiryCreateCount={inquiry_create_count}")
        self.stdout.write(f"quotationCreateCount={quotation_create_count}")
        self.stdout.write(f"quotationLineWriteCount={quotation_line_write_count}")
        self.stdout.write(f"quotationSubmitCount={quotation_submit_count}")
        self.stdout.write(f"businessWriteCount={business_write_count}")
        self.stdout.write("supplierPriceFactWriteCount=0")
        self.stdout.write("supplierMaterialPriceDirectWriteCount=0")
