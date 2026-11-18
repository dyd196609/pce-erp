from datetime import date
from decimal import Decimal

from django.test import TestCase

from masterdata.models import Material

from .models import (
    PurchaseInquiry,
    PurchaseOrder,
    PurchaseRequest,
    PurchaseRequestItem,
    Supplier,
    SupplierQuotation,
)
from .scm_page_facts import _normalized_object
from .scm_runtime_services import PurchaseOrderCreationService, ScmRuntimeActionError


class PurchaseOrderSupplierFactRuntimeV11428427224Tests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            code="SUP-FACT-24",
            name="供应商事实验收",
            contact_person="张经理",
            contact_phone="13712345486",
            address="浙江省验收供应商有限公司",
            company_id=1,
        )
        self.material = Material.objects.create(
            code="MAT-FACT-24", name="供应价格验收物料",
            specification="V2.24", unit="件", company_id=1, is_purchased=True,
        )
        self.request = PurchaseRequest.objects.create(
            request_no="PR-FACT-24", request_date=date(2026, 8, 10),
            requester="采购验收员", department="采购部", status="approved",
        )
        self.request_item = PurchaseRequestItem.objects.create(
            purchase_request=self.request, material=self.material,
            material_code=self.material.code, material_name=self.material.name,
            specification=self.material.specification, unit=self.material.unit,
            quantity=Decimal("6"), required_date=date(2026, 9, 5), line_no=1,
        )
        self.inquiry = PurchaseInquiry.objects.create(
            inquiry_no="PI-FACT-24", source_purchase_request=self.request, status="quoted",
        )
        self.quotation = SupplierQuotation.objects.create(
            quotation_no="SQ-FACT-24", source_inquiry=self.inquiry,
            supplier_id=str(self.supplier.pk), supplier_name=self.supplier.name,
            quotation_status="received", price=Decimal("75"),
            items=[{
                "materialCode": self.material.code,
                "quantity": 6,
                "unitPrice": "12.5",
            }],
        )

    def payload(self, request_id="POCR-FACT-24"):
        return {
            "requestId": request_id,
            "gateId": "POG-FACT-24",
            "admissionResultId": "POAR-FACT-24",
            "status": "PENDING_CONFIRMATION",
            "confirmedBy": "采购验收员",
            "purchaseRequestIds": [self.request.request_no],
            "inquiryIds": [self.inquiry.inquiry_no],
            "supplierGroups": [{
                "supplierId": self.supplier.pk,
                "supplierCode": self.supplier.code,
                "supplierName": self.supplier.name,
                "materialLines": [{
                    "materialCode": self.material.code,
                    "quantity": 999,
                    "unitPrice": 0,
                    "expectedDate": "2099-01-01",
                }],
            }],
        }

    def test_supplier_quote_price_amount_and_delivery_are_server_owned(self):
        orders, created_count = PurchaseOrderCreationService.create_from_gate_request(
            self.payload(), actor_id=1
        )
        self.assertEqual(created_count, 1)
        order = orders[0]
        item = order.items.get()
        self.assertEqual(order.supplier_id, self.supplier.pk)
        self.assertEqual(item.quantity, Decimal("6"))
        self.assertEqual(item.unit_price, Decimal("12.5"))
        self.assertEqual(item.amount, Decimal("75"))
        self.assertEqual(order.total_amount, Decimal("75"))
        self.assertEqual(item.expected_date, self.request_item.required_date)
        self.assertEqual(order.expected_date, self.request_item.required_date)

        fact = _normalized_object(order)
        line = fact["items"][0]
        self.assertEqual(fact["supplierCode"], self.supplier.code)
        self.assertEqual(fact["supplierContact"], "张经理")
        self.assertEqual(fact["supplierPhone"], "137****5486")
        self.assertEqual(line["sourceQuotationNo"], self.quotation.quotation_no)
        self.assertEqual(line["priceSource"], "SupplierQuoteItem.unitPrice")
        self.assertEqual(line["deliverySource"], "PurchaseRequest.requiredDate")
        self.assertTrue(line["materialSupplierRelationSource"])

    def test_missing_supplier_price_fact_blocks_whole_transaction(self):
        self.quotation.delete()
        with self.assertRaises(ScmRuntimeActionError) as raised:
            PurchaseOrderCreationService.create_from_gate_request(
                self.payload("POCR-FACT-MISSING-24"), actor_id=1
            )
        self.assertEqual(raised.exception.code, "PURCHASE_PRICE_SOURCE_REQUIRED")
        self.assertEqual(PurchaseOrder.objects.count(), 0)

