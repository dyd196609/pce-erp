from datetime import date
from decimal import Decimal

from django.test import TestCase

from masterdata.models import Material

from .models import (
    PurchaseInquiry, PurchaseOrder, PurchaseRequest, PurchaseRequestItem,
    Supplier, SupplierQuotation,
)
from .scm_page_facts import _normalized_object
from .scm_runtime_services import PurchaseOrderCreationService, ScmRuntimeActionError
from .supplier_material_fact_resolver import SupplierMaterialFactResolver


class SupplierMaterialFactMappingV11428427225Tests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            code="SUP025", name="统一编码供应商", contact_person="张经理",
            contact_phone="13712345486", address="浙江省验收供应商有限公司",
            company_id=1,
        )
        self.material = Material.objects.create(
            code="MT025", name="统一编码物料", specification="V2.25",
            unit="件", company_id=1, is_purchased=True,
        )
        self.request = PurchaseRequest.objects.create(
            request_no="PR-FACT-25", request_date=date(2026, 8, 10),
            requester="采购验收员", department="采购部", status="approved",
        )
        self.request_item = PurchaseRequestItem.objects.create(
            purchase_request=self.request, material=self.material,
            material_code=self.material.code, material_name=self.material.name,
            specification=self.material.specification, unit=self.material.unit,
            quantity=Decimal("4"), required_date=date(2026, 9, 10), line_no=1,
        )
        self.inquiry = PurchaseInquiry.objects.create(
            inquiry_no="PI-FACT-25", source_purchase_request=self.request, status="quoted",
        )
        self.quotation = SupplierQuotation.objects.create(
            quotation_no="SQ-FACT-25", source_inquiry=self.inquiry,
            supplier_id=self.supplier.code.lower(), supplier_name=self.supplier.name,
            quotation_status="received", price=Decimal("352"),
            items=[{
                "supplierCode": self.supplier.code,
                "materialId": self.material.pk,
                "materialCode": self.material.code.lower(),
                "quantity": "4",
                "unitPrice": "88",
                "deliveryPeriod": 6,
            }],
        )

    def payload(self, request_id="POCR-FACT-25"):
        return {
            "requestId": request_id,
            "gateId": "POG-FACT-25",
            "admissionResultId": "POAR-FACT-25",
            "status": "PENDING_CONFIRMATION",
            "confirmedBy": "采购验收员",
            "purchaseRequestIds": [self.request.request_no],
            "inquiryIds": [self.inquiry.inquiry_no],
            "supplierGroups": [{
                "supplierId": self.supplier.pk,
                "supplierCode": "WRONG-GATE-CODE",
                "supplierName": "错误页面名称",
                "materialLines": [{
                    "materialCode": self.material.code,
                    "unitPrice": 0,
                    "expectedDate": "2099-01-01",
                }],
            }],
        }

    def test_canonical_codes_and_fact_are_inherited(self):
        orders, count = PurchaseOrderCreationService.create_from_gate_request(
            self.payload(), actor_id=1,
        )
        self.assertEqual(count, 1)
        order = orders[0]
        item = order.items.get()
        self.assertEqual(order.supplier.code, "SUP025")
        self.assertEqual(item.material.code, "MT025")
        self.assertEqual(item.unit_price, Decimal("88"))
        self.assertEqual(item.amount, Decimal("352"))
        self.assertEqual(order.total_amount, Decimal("352"))
        self.assertIsNotNone(item.expected_date)
        fact = _normalized_object(order)
        self.assertEqual(fact["supplierCode"], "SUP025")
        self.assertEqual(fact["items"][0]["materialCode"], "MT025")
        self.assertEqual(fact["items"][0]["priceSource"], "SupplierQuoteItem.unitPrice")

    def test_conflicting_material_code_is_rejected_without_write(self):
        self.quotation.items = [{
            "materialId": self.material.pk,
            "materialCode": "MT999",
            "unitPrice": "88",
            "deliveryPeriod": 6,
        }]
        self.quotation.save(update_fields=["items", "updated_at"])
        with self.assertRaises(ScmRuntimeActionError) as raised:
            PurchaseOrderCreationService.create_from_gate_request(
                self.payload("POCR-FACT-MISMATCH-25"), actor_id=1,
            )
        self.assertEqual(raised.exception.code, "PURCHASE_PRICE_SOURCE_REQUIRED")
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_page_private_codes_cannot_be_rewritten_into_master_codes(self):
        relation = {
            "supplierCode": "SUP-000025",
            "materialCode": "MAT-000025",
            "source": "PagePrivateStore",
        }
        price = {**relation, "unitPrice": "88", "deliveryPeriod": 6}
        fact = SupplierMaterialFactResolver.resolve_fact(
            supplier_master=self.supplier,
            material_master=self.material,
            supplier_material_price=price,
            material_supplier_relation=relation,
            source_required_date=self.request_item.required_date,
        )
        self.assertIsNone(fact)

