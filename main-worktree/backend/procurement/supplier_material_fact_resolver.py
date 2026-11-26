"""Canonical supplier/material fact resolution for purchase-order creation.

The resolver is the only place allowed to join SupplierMaster, MaterialMaster,
the persisted material-supplier relation projection and its price fact.  It
never rewrites business codes and never consumes Gate/page prices.
"""

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils.dateparse import parse_date

from .models import SupplierQuotation


def _code(value):
    """Normalize transport noise only; business prefixes and digits are preserved."""
    return str(value or "").strip().upper()


def _positive_decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result > 0 else None


@dataclass(frozen=True)
class SupplierMaterialFact:
    supplier_id: int
    supplier_code: str
    supplier_name: str
    material_id: int
    material_code: str
    unit_price: Decimal
    delivery_period: int
    delivery_date: object
    relation_source: str
    price_source: str
    delivery_source: str
    source_quotation_id: int
    source_quotation_no: str

    @property
    def supplier_master_id(self):
        return self.supplier_id

    @property
    def material_master_id(self):
        return self.material_id

    @property
    def material_supplier_relation_source(self):
        return self.relation_source

    @property
    def supplier_material_price_source(self):
        return self.price_source

    def to_dict(self):
        value = asdict(self)
        value["unit_price"] = str(self.unit_price)
        value["delivery_date"] = self.delivery_date.isoformat()
        return value


class SupplierMaterialFactResolver:
    """Resolve a strict, server-owned Supplier+Material+Price fact."""

    runtime_code = "SupplierMaterialFactResolver"
    relation_source = "SupplierQuotation.SupplierQuoteItem"
    price_source = "SupplierQuoteItem.unitPrice"

    @staticmethod
    def _master_matches(*, master_id, master_code, fact_id=None, fact_code=None):
        provided = False
        if fact_id not in (None, ""):
            provided = True
            if str(fact_id).strip() != str(master_id):
                return False
        if fact_code not in (None, ""):
            provided = True
            if _code(fact_code) != _code(master_code):
                return False
        return provided

    @classmethod
    def resolve_fact(
        cls, *, supplier_master, material_master, supplier_material_price,
        material_supplier_relation, source_required_date=None,
    ):
        """Validate four input objects and output one canonical fact.

        ``supplier_material_price`` and ``material_supplier_relation`` are
        server projections.  In the current frozen schema they are projected
        from a persisted SupplierQuotation line rather than a page Store.
        """
        relation_ok = (
            cls._master_matches(
                master_id=supplier_master.pk, master_code=supplier_master.code,
                fact_id=material_supplier_relation.get("supplierId"),
                fact_code=material_supplier_relation.get("supplierCode"),
            )
            and cls._master_matches(
                master_id=material_master.pk, master_code=material_master.code,
                fact_id=material_supplier_relation.get("materialId"),
                fact_code=material_supplier_relation.get("materialCode"),
            )
        )
        price_ok = (
            cls._master_matches(
                master_id=supplier_master.pk, master_code=supplier_master.code,
                fact_id=supplier_material_price.get("supplierId"),
                fact_code=supplier_material_price.get("supplierCode"),
            )
            and cls._master_matches(
                master_id=material_master.pk, master_code=material_master.code,
                fact_id=supplier_material_price.get("materialId"),
                fact_code=supplier_material_price.get("materialCode"),
            )
        )
        unit_price = _positive_decimal(supplier_material_price.get("unitPrice"))
        if not relation_ok or not price_ok or unit_price is None:
            return None

        delivery_period = 0
        try:
            delivery_period = int(supplier_material_price.get("deliveryPeriod") or 0)
        except (TypeError, ValueError):
            pass
        delivery_date = parse_date(str(supplier_material_price.get("deliveryDate") or ""))
        delivery_source = "SupplierQuote.deliveryDate" if delivery_date else ""
        if not delivery_date and delivery_period > 0:
            delivery_date = date.today() + timedelta(days=delivery_period)
            delivery_source = "SupplierMaterialPrice.deliveryPeriod"
        if not delivery_date and source_required_date:
            delivery_date = source_required_date
            delivery_source = "PurchaseRequest.requiredDate"
        if not delivery_date:
            return None

        return SupplierMaterialFact(
            supplier_id=supplier_master.pk,
            supplier_code=supplier_master.code,
            supplier_name=supplier_master.name,
            material_id=material_master.pk,
            material_code=material_master.code,
            unit_price=unit_price,
            delivery_period=max(delivery_period, 0),
            delivery_date=delivery_date,
            relation_source=str(material_supplier_relation.get("source") or cls.relation_source),
            price_source=str(supplier_material_price.get("source") or cls.price_source),
            delivery_source=delivery_source,
            source_quotation_id=int(supplier_material_price.get("sourceQuotationId") or 0),
            source_quotation_no=str(supplier_material_price.get("sourceQuotationNo") or ""),
        )

    @classmethod
    def _quotation_queryset(cls, supplier, source_item, inquiry_ids=()):
        inquiry_values = [str(value or "").strip() for value in inquiry_ids if str(value or "").strip()]
        inquiry_query = Q(source_inquiry__source_purchase_request=source_item.purchase_request)
        numeric_ids = [int(value) for value in inquiry_values if value.isdigit()]
        business_nos = [value for value in inquiry_values if not value.isdigit()]
        if numeric_ids:
            inquiry_query |= Q(source_inquiry_id__in=numeric_ids)
        if business_nos:
            inquiry_query |= Q(source_inquiry__inquiry_no__in=business_nos)
        return SupplierQuotation.objects.filter(
            inquiry_query,
            Q(supplier_id=str(supplier.pk)) | Q(supplier_id__iexact=supplier.code),
            quotation_status__in=("received", "submitted", "saved"),
        ).select_related("source_inquiry").order_by("-received_at", "-id")

    @classmethod
    def resolve(cls, *, supplier, material, source_item, inquiry_ids=()):
        for quotation in cls._quotation_queryset(supplier, source_item, inquiry_ids):
            supplier_code = quotation.supplier_id if not str(quotation.supplier_id).isdigit() else ""
            supplier_id = quotation.supplier_id if str(quotation.supplier_id).isdigit() else None
            for line in quotation.items or []:
                relation = {
                    "supplierId": supplier_id,
                    "supplierCode": supplier_code,
                    "materialId": line.get("materialId"),
                    "materialCode": line.get("materialCode"),
                    "source": cls.relation_source,
                }
                price = {
                    **relation,
                    "unitPrice": line.get("unitPrice"),
                    "deliveryDate": line.get("deliveryDate"),
                    "deliveryPeriod": line.get("deliveryPeriod"),
                    "source": cls.price_source,
                    "sourceQuotationId": quotation.pk,
                    "sourceQuotationNo": quotation.quotation_no,
                }
                fact = cls.resolve_fact(
                    supplier_master=supplier,
                    material_master=material,
                    supplier_material_price=price,
                    material_supplier_relation=relation,
                    source_required_date=source_item.required_date,
                )
                if fact is not None:
                    return fact
        return None
