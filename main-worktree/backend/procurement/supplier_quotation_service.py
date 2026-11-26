from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import PurchaseInquiry, SupplierQuotation


def _source_candidates(inquiry):
    quotation = inquiry.quotation if isinstance(inquiry.quotation, dict) else {}
    return list(quotation.get("supplierCandidates") or quotation.get("suppliers") or [])


def _supplier_identity(candidate):
    return str(candidate.get("supplierId") or candidate.get("supplierCode") or "").strip()


def _quotation_number(inquiry, supplier_id):
    base = inquiry.inquiry_no[3:] if inquiry.inquiry_no.startswith("PI-") else inquiry.inquiry_no
    candidates = _source_candidates(inquiry)
    index = next((i for i, item in enumerate(candidates) if _supplier_identity(item) == supplier_id), 0)
    return f"SQ-{base}" if index == 0 else f"SQ-{base}-{index + 1:02d}"


def supplier_quotation_source_rows():
    rows = []
    inquiries = PurchaseInquiry.objects.prefetch_related("supplier_quotations").order_by("-id")[:100]
    for inquiry in inquiries:
        quotations = {item.supplier_id: item for item in inquiry.supplier_quotations.all()}
        for candidate in _source_candidates(inquiry):
            supplier_id = _supplier_identity(candidate)
            if not supplier_id:
                continue
            current = quotations.get(supplier_id)
            quoted_lines = {
                str(item.get("materialCode") or ""): item
                for item in (current.items if current else []) if isinstance(item, dict)
            }
            for line in inquiry.items if isinstance(inquiry.items, list) else []:
                material_code = str(line.get("materialCode") or "")
                quoted_line = quoted_lines.get(material_code, {})
                rows.append({
                    "rowId": f"{inquiry.pk}:{supplier_id}:{material_code}",
                    "sourceInquiryId": inquiry.pk,
                    "sourceInquiryNo": inquiry.inquiry_no,
                    "quotationId": current.pk if current else None,
                    "quotationNo": current.quotation_no if current else "",
                    "supplierId": supplier_id,
                    "supplierCode": candidate.get("supplierCode") or supplier_id,
                    "supplierName": candidate.get("supplierName") or supplier_id,
                    "materialCode": material_code,
                    "materialName": line.get("materialName") or material_code,
                    "quantity": line.get("quantity") or "0",
                    "unit": line.get("unit") or "",
                    "quotePrice": quoted_line.get("unitPrice"),
                    "remark": quoted_line.get("remark") or "",
                    "currency": current.currency if current else "CNY",
                    "quotationStatus": current.quotation_status if current else "awaiting_entry",
                    "quotationStatusLabel": current.get_quotation_status_display() if current else "待录入",
                    "receivedAt": current.received_at.isoformat() if current and current.received_at else None,
                    "quoted": bool(quoted_line.get("unitPrice")),
                    "readOnly": False,
                })
    return rows


@transaction.atomic
def save_supplier_quotation(source_inquiry_id, supplier_id, material_code, unit_price, remark="", currency="CNY"):
    inquiry = PurchaseInquiry.objects.select_for_update().get(pk=source_inquiry_id)
    candidate = next((item for item in _source_candidates(inquiry) if _supplier_identity(item) == str(supplier_id)), None)
    if candidate is None:
        raise ValueError("SUPPLIER_NOT_IN_INQUIRY_CANDIDATES")
    try:
        price_value = Decimal(str(unit_price))
    except (InvalidOperation, TypeError):
        raise ValueError("QUOTATION_PRICE_INVALID")
    if price_value <= 0:
        raise ValueError("QUOTATION_PRICE_MUST_BE_POSITIVE")
    source_line = next((item for item in inquiry.items if str(item.get("materialCode") or "") == str(material_code)), None)
    if source_line is None:
        raise ValueError("MATERIAL_NOT_IN_SOURCE_INQUIRY")

    quotation, created = SupplierQuotation.objects.get_or_create(
        source_inquiry=inquiry,
        supplier_id=str(supplier_id),
        defaults={
            "quotation_no": _quotation_number(inquiry, str(supplier_id)),
            "supplier_name": candidate.get("supplierName") or str(supplier_id),
            "currency": currency or "CNY",
            "quotation_status": "draft",
        },
    )
    if quotation.quotation_status in {"received", "closed", "cancelled"}:
        raise ValueError("SUPPLIER_QUOTATION_LOCKED")
    items = [dict(item) for item in quotation.items if isinstance(item, dict)]
    line = dict(source_line)
    line.update({"unitPrice": str(price_value), "remark": str(remark or "")})
    index = next((i for i, item in enumerate(items) if str(item.get("materialCode") or "") == str(material_code)), -1)
    if index < 0:
        items.append(line)
    else:
        items[index] = line
    total = sum(Decimal(str(item.get("quantity") or 0)) * Decimal(str(item.get("unitPrice") or 0)) for item in items)
    quotation.items = items
    quotation.quantity = sum(Decimal(str(item.get("quantity") or 0)) for item in items)
    quotation.price = total
    quotation.amount = total
    quotation.currency = currency or "CNY"
    quotation.quotation_status = "saved"
    quotation.save()
    return quotation, created


@transaction.atomic
def submit_supplier_quotation(quotation_id):
    quotation = SupplierQuotation.objects.select_for_update().get(pk=quotation_id)
    source_codes = {str(item.get("materialCode") or "") for item in quotation.source_inquiry.items}
    quoted_codes = {str(item.get("materialCode") or "") for item in quotation.items if Decimal(str(item.get("unitPrice") or 0)) > 0}
    if quotation.quotation_status not in {"saved", "submitted"} or not source_codes or quoted_codes != source_codes:
        raise ValueError("SUPPLIER_QUOTATION_INCOMPLETE")
    quotation.quotation_status = "received"
    quotation.received_at = timezone.now()
    quotation.save(update_fields=["quotation_status", "received_at", "updated_at"])
    return quotation
