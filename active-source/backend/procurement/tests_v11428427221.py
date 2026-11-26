from datetime import date

from django.test import TestCase

from masterdata.models import Material

from .models import (PurchaseInquiry, PurchaseOrder, PurchaseRequest, PurchaseRequestItem,
                     Supplier, SupplierQuotation)
from .scm_page_facts import _normalized_object
from .scm_runtime_services import (PurchaseOrderCreationService,
                                   ScmRuntimeActionError)


class PurchaseOrderMaterialSourceRuntimeV11428427221Tests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            code="SUP-MATERIAL-21", name="物料来源验收供应商", company_id=1
        )
        self.material = Material.objects.create(
            code="MAT-MATERIAL-21", name="受治理物料",
            specification="主数据规格", unit="台", company_id=1, is_purchased=True,
        )
        self.request = PurchaseRequest.objects.create(
            request_no="PR-MATERIAL-21", request_date=date(2026, 8, 10),
            requester="采购员", department="需求部门", status="approved",
        )
        self.request_item = PurchaseRequestItem.objects.create(
            purchase_request=self.request, material=self.material,
            material_code=self.material.code, material_name="采购申请物料名称",
            specification="采购申请规格", unit="套", quantity=5,
            required_date=date(2026, 8, 28), line_no=1,
        )
        self.inquiry = PurchaseInquiry.objects.create(
            inquiry_no="PI-MATERIAL-21", source_purchase_request=self.request,
            status="quoted",
        )
        SupplierQuotation.objects.create(
            quotation_no="SQ-MATERIAL-21", source_inquiry=self.inquiry,
            supplier_id=str(self.supplier.pk), supplier_name=self.supplier.name,
            quotation_status="received", price=100,
            items=[{"materialCode": self.material.code, "quantity": 5, "unitPrice": 20}],
        )

    def payload(self, *, request_id="POCR-MATERIAL-21", material_code=None):
        return {
            "requestId": request_id,
            "gateId": "POG-MATERIAL-21",
            "admissionResultId": "POAR-MATERIAL-21",
            "status": "PENDING_CONFIRMATION",
            "confirmedBy": "采购员",
            "purchaseRequestIds": [self.request.request_no],
            "inquiryIds": [self.inquiry.inquiry_no],
            "supplierGroups": [{
                "supplierId": self.supplier.pk,
                "supplierCode": self.supplier.code,
                "supplierName": self.supplier.name,
                "materialLines": [{
                    "materialCode": material_code or self.material.code,
                    "materialName": "Gate临时名称不得使用",
                    "specification": "",
                    "unit": "",
                    "quantity": 999,
                    "unitPrice": 20,
                    "expectedDate": "2099-01-01",
                }],
            }],
        }

    def test_item_reads_purchase_request_item_and_material_master(self):
        orders, created_count = PurchaseOrderCreationService.create_from_gate_request(
            self.payload(), actor_id=1
        )
        self.assertEqual(created_count, 1)
        order = orders[0]
        item = order.items.get()

        self.assertEqual(item.material_id, self.material.pk)
        self.assertEqual(item.product_name, self.request_item.material_name)
        self.assertEqual(item.specification, self.request_item.specification)
        self.assertEqual(item.quantity, self.request_item.quantity)
        self.assertEqual(item.expected_date, self.request_item.required_date)
        self.assertEqual(item.amount, 100)
        self.assertIn(f"[PurchaseRequestItem:{self.request_item.pk}]", item.remark)
        self.assertIn(f"[MaterialMaster:{self.material.pk}]", item.remark)
        self.assertIn("[Unit:台]", item.remark)

        fact = _normalized_object(order)["items"][0]
        self.assertEqual(fact["purchaseRequestItemId"], self.request_item.pk)
        self.assertEqual(fact["sourcePurchaseRequestNo"], self.request.request_no)
        self.assertEqual(fact["materialMasterId"], self.material.pk)
        self.assertTrue(fact["materialMasterBound"])
        self.assertEqual(fact["specification"], "采购申请规格")
        self.assertEqual(fact["unit"], "台")
        self.assertEqual(fact["amount"], "100.00")

    def test_material_master_identity_mismatch_blocks_whole_write(self):
        self.request_item.material_code = "MAT-NOT-MAINTAINED"
        self.request_item.save(update_fields=["material_code"])
        with self.assertRaisesMessage(ScmRuntimeActionError, "主数据未维护"):
            PurchaseOrderCreationService.create_from_gate_request(
                self.payload(request_id="POCR-MATERIAL-MISSING-21",
                             material_code="MAT-NOT-MAINTAINED"), actor_id=1
            )
        self.assertEqual(PurchaseOrder.objects.count(), 0)
