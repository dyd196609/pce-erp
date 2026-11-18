from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from procurement.models import (
    PriceApproval,
    PurchaseInquiry,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
    Supplier,
    SupplierQuotation,
)

from .material_supplier_relation_runtime import MaterialSupplierRelationRuntime
from .master_data_statistics_runtime import MasterDataStatisticsRuntime
from .models import Material
from .views import MaterialSupplierRelationFactsView


class MaterialSupplierRelationRuntimeV11428427230Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.material = Material.objects.create(
            code="MT-REL-001", name="关系验收物料", unit="件",
            company_id=1, is_active=True, is_purchased=True,
        )
        cls.supplier = Supplier.objects.create(
            code="SUP-REL-001", name="关系验收供应商", company_id=1,
            category="综合供应商", address="浙江省杭州市关系验收有限公司",
            delivery_address="江苏省苏州市关系验收有限公司",
            contact_person="张经理", contact_phone="13700005486",
        )
        cls.other_supplier = Supplier.objects.create(
            code="SUP-REL-002", name="采购历史供应商", company_id=1,
            category="综合供应商", address="浙江省宁波市采购历史有限公司",
            delivery_address="江苏省南京市采购历史有限公司",
            contact_person="张经理", contact_phone="13700005486",
        )
        request = PurchaseRequest.objects.create(
            request_no="PR-REL-001", request_date=date(2026, 8, 11),
            requester="关系验收员", department="采购部", status="approved",
        )
        cls.request_item = PurchaseRequestItem.objects.create(
            purchase_request=request, material=cls.material,
            material_code=cls.material.code, material_name=cls.material.name,
            specification="R30", unit="件", quantity=Decimal("2"),
            required_date=date(2026, 9, 11), line_no=1,
            suggested_supplier=cls.supplier,
            suggested_supplier_code="sup-rel-001",
            suggested_supplier_name=cls.supplier.name,
        )
        inquiry = PurchaseInquiry.objects.create(
            inquiry_no="PI-REL-001", source_purchase_request=request, status="quoted",
        )
        SupplierQuotation.objects.create(
            quotation_no="SQ-REL-001", source_inquiry=inquiry,
            supplier_id=cls.supplier.code, supplier_name=cls.supplier.name,
            quotation_status="received", price=Decimal("50"),
            items=[{
                "materialCode": cls.material.code,
                "materialName": cls.material.name,
                "unitPrice": "25",
                "deliveryPeriod": 6,
            }],
        )
        PriceApproval.objects.create(
            approval_no="PA-REL-001", source_inquiry=inquiry,
            supplier=cls.supplier.code, price=Decimal("25"), status="approved",
            items=[{"materialCode": cls.material.code, "materialName": cls.material.name}],
        )
        order = PurchaseOrder.objects.create(
            po_no="PO-REL-001", supplier=cls.other_supplier,
            order_date=date(2026, 8, 11), expected_date=date(2026, 8, 20),
            company_id=1,
        )
        PurchaseOrderItem.objects.create(
            po=order, material=cls.material, product_name=cls.material.name,
            quantity=Decimal("1"), unit_price=Decimal("20"), amount=Decimal("20"),
        )

    def test_usage_mapping_builds_unique_relation_without_guessing_codes(self):
        counts_before = (
            Material.objects.count(), Supplier.objects.count(),
            PurchaseOrder.objects.count(), PriceApproval.objects.count(),
        )
        facts = MaterialSupplierRelationRuntime.facts()
        self.assertEqual(facts["relationCount"], 2)
        self.assertEqual(facts["duplicateRelationCount"], 0)
        relation = next(
            row for row in facts["models"]
            if row.supplierCode == self.supplier.code
        )
        self.assertEqual(relation.materialCode, "MT-REL-001")
        self.assertEqual(relation.supplierCode, "SUP-REL-001")
        self.assertTrue(relation.isMainSupplier)
        self.assertEqual(relation.priority, 2)
        self.assertEqual(relation.deliveryPeriod, 6)
        self.assertIn("SupplierQuotation:SQ-REL-001", relation.deliveryPeriodSource)
        self.assertTrue(any(
            row["supplierCode"] == "sup-rel-001"
            and row["mappingStatus"] == "待人工确认"
            for row in facts["unresolvedMappings"]
        ))
        self.assertEqual(counts_before, (
            Material.objects.count(), Supplier.objects.count(),
            PurchaseOrder.objects.count(), PriceApproval.objects.count(),
        ))

    def test_api_and_statistics_reuse_same_relation_runtime(self):
        request = APIRequestFactory().get(
            "/api/masterdata/relations/material-suppliers/runtime/facts/"
        )
        response = MaterialSupplierRelationFactsView.as_view()(request)
        response.render()
        statistics = MasterDataStatisticsRuntime.facts()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["runtimeCode"], "MaterialSupplierRelationRuntime")
        self.assertEqual(response.data["pageVersion"], "V1.14.2.8.4.27.2.30")
        self.assertEqual(response.data["relationCount"], 2)
        self.assertEqual(
            response.data["relationCount"],
            statistics["supplierMaterialRelationCount"],
        )
        self.assertEqual(response.data["businessProgressWriteCount"], 0)
        self.assertFalse(response.data["databaseStructureChanged"])
