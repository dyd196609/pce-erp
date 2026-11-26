from datetime import date

from django.test import TestCase

from masterdata.models import Material

from .models import (PurchaseInquiry, PurchaseOrder, PurchaseOrderItem, PurchaseRequest,
                     PurchaseRequestItem, Supplier, SupplierQuotation)
from .scm_page_facts import _normalized_object
from .scm_runtime_services import PurchaseOrderCreationService


class PurchaseOrderSupplierSplitRuntimeV11428427220Tests(TestCase):
    def setUp(self):
        self.suppliers = [
            Supplier.objects.create(
                code=f"SUP-SPLIT-{index}", name=f"拆单供应商{index}", company_id=1
            )
            for index in range(1, 5)
        ]
        self.purchase_request = PurchaseRequest.objects.create(
            request_no="PR-V11428427220-001", request_date=date(2026, 8, 10),
            requester="验收员", department="采购部", status="approved",
        )
        self.inquiry = PurchaseInquiry.objects.create(
            inquiry_no="PI-V11428427220-001",
            source_purchase_request=self.purchase_request,
            status="quoted",
        )
        for index in range(1, 5):
            material = Material.objects.create(
                code=f"MAT-SPLIT-{index}", name=f"拆单物料{index}",
                specification="V2.20", unit="件", company_id=1, is_purchased=True,
            )
            PurchaseRequestItem.objects.create(
                purchase_request=self.purchase_request, material=material,
                material_code=material.code, material_name=material.name,
                specification=material.specification, unit=material.unit,
                quantity=index, required_date=date(2026, 8, 20 + index), line_no=index,
            )
            SupplierQuotation.objects.create(
                quotation_no=f"SQ-V11428427220-{index:03d}",
                source_inquiry=self.inquiry,
                supplier_id=str(self.suppliers[index - 1].pk),
                supplier_name=self.suppliers[index - 1].name,
                quotation_status="received",
                price=index * (10 + index),
                items=[{
                    "materialCode": material.code,
                    "quantity": index,
                    "unitPrice": 10 + index,
                }],
            )

    def payload(self):
        return {
            "requestId": "POCR-V11428427220-001",
            "gateId": "POG-V11428427220-001",
            "admissionResultId": "POAR-V11428427220-001",
            "status": "PENDING_CONFIRMATION",
            "confirmedBy": "采购验收员",
            "purchaseRequestIds": [self.purchase_request.request_no],
            "inquiryIds": [self.inquiry.inquiry_no],
            "supplierGroups": [
                {
                    "supplierId": supplier.pk,
                    "supplierCode": supplier.code,
                    "supplierName": supplier.name,
                    "materialLines": [{
                        "materialCode": f"MAT-SPLIT-{index}",
                        "materialName": f"拆单物料{index}",
                        "specification": "V2.20",
                        "quantity": index,
                        "unitPrice": 10 + index,
                        "expectedDate": f"2026-08-{20 + index:02d}",
                    }],
                }
                for index, supplier in enumerate(self.suppliers, start=1)
            ],
        }

    def test_four_suppliers_create_four_orders_with_items_and_fields(self):
        orders, created_count = PurchaseOrderCreationService.create_from_gate_request(
            self.payload(), actor_id=1
        )

        self.assertEqual(created_count, 4)
        self.assertEqual(len(orders), 4)
        self.assertEqual(PurchaseOrder.objects.count(), 4)
        self.assertEqual(PurchaseOrderItem.objects.count(), 4)
        self.assertEqual({order.supplier_id for order in orders},
                         {supplier.pk for supplier in self.suppliers})

        for order in orders:
            self.assertTrue(order.object_no.startswith("PO"))
            self.assertIsNotNone(order.order_date)
            self.assertIsNotNone(order.expected_date)
            self.assertNotEqual(order.urgency_level, "unscheduled")
            self.assertIn("Gate:POG-V11428427220-001", order.remark)
            self.assertEqual(order.items.count(), 1)
            item = order.items.get()
            self.assertEqual(item.po_id, order.pk)
            fact = _normalized_object(order)
            self.assertEqual(fact["supplierId"], order.supplier_id)
            self.assertEqual(fact["supplierCode"], order.supplier.code)
            self.assertEqual(fact["supplierName"], order.supplier.name)
            self.assertTrue(fact["purchaseDate"])
            self.assertTrue(fact["deliveryDate"])
            self.assertTrue(fact["deliveryUrgencyLabel"])
            self.assertEqual(fact["sourceGateId"], "POG-V11428427220-001")
            self.assertEqual(len(fact["items"]), 1)
            self.assertEqual(fact["items"][0]["purchaseOrderId"], order.pk)

        repeated, repeated_count = PurchaseOrderCreationService.create_from_gate_request(
            self.payload(), actor_id=1
        )
        self.assertEqual(repeated_count, 0)
        self.assertEqual(len(repeated), 4)
        self.assertEqual(PurchaseOrder.objects.count(), 4)
        self.assertEqual(PurchaseOrderItem.objects.count(), 4)
