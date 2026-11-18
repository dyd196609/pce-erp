from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from masterdata.models import Material
from procurement.models import (
    PurchaseInquiry, PurchaseOrder, PurchaseOrderItem, PurchaseRequest,
    PurchaseRequestItem, Supplier, SupplierQuotation,
)

from .supplier_master_runtime import SupplierBusinessMapping, SupplierMasterRuntimeAdapter
from .views import EnterpriseMasterDataFactsView


class SupplierMasterMappingV11428427226Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.supplier = Supplier.objects.create(
            code="SUP026", name="供应商映射验收",
            contact_person="张经理", contact_phone="13712345486",
            address="浙江省验收地址", credit_rating="A", company_id=1,
        )
        cls.material = Material.objects.create(
            code="MT026", name="映射验收物料", specification="V2.26",
            unit="件", company_id=1, is_purchased=True,
        )
        cls.request = PurchaseRequest.objects.create(
            request_no="PR-MAP-26", request_date=date(2026, 8, 10),
            requester="测试采购员", department="采购部", status="approved",
        )
        cls.request_item = PurchaseRequestItem.objects.create(
            purchase_request=cls.request, material=cls.material,
            material_code=cls.material.code, material_name=cls.material.name,
            specification=cls.material.specification, unit=cls.material.unit,
            suggested_supplier=cls.supplier,
            suggested_supplier_code=cls.supplier.code,
            suggested_supplier_name=cls.supplier.name,
            quantity=Decimal("2"), required_date=date(2026, 9, 10), line_no=1,
        )
        cls.inquiry = PurchaseInquiry.objects.create(
            inquiry_no="PI-MAP-26", source_purchase_request=cls.request,
            supplier=cls.supplier.code,
            quotation={"supplierCandidates": [{
                "supplierId": cls.supplier.pk,
                "supplierCode": cls.supplier.code,
                "supplierName": cls.supplier.name,
            }]},
        )
        SupplierQuotation.objects.create(
            quotation_no="SQ-MAP-26", source_inquiry=cls.inquiry,
            supplier_id=str(cls.supplier.pk), supplier_name=cls.supplier.name,
            quotation_status="received", price=Decimal("20"),
            items=[{"materialCode": cls.material.code, "unitPrice": "10"}],
        )
        cls.order = PurchaseOrder.objects.create(
            po_no="PO-MAP-26", supplier=cls.supplier,
            order_date=date(2026, 8, 10), expected_date=date(2026, 9, 10),
            total_amount=Decimal("20"), company_id=1,
        )
        PurchaseOrderItem.objects.create(
            po=cls.order, material=cls.material, product_name=cls.material.name,
            specification=cls.material.specification, quantity=Decimal("2"),
            unit_price=Decimal("10"), amount=Decimal("20"),
            expected_date=date(2026, 9, 10),
        )

    def test_business_usage_maps_to_one_supplier_master(self):
        facts = SupplierMasterRuntimeAdapter.facts()
        row = next(item for item in facts["models"] if item.supplierCode == "SUP026")
        self.assertGreaterEqual(row.usageCount, 5)
        self.assertIn("PurchaseRequest", row.usageModules)
        self.assertIn("PurchaseInquiry", row.usageModules)
        self.assertIn("SupplierQuote", row.usageModules)
        self.assertIn("PurchaseOrder", row.usageModules)
        self.assertEqual(row.mappingStatus, "已映射")
        self.assertEqual(facts["unresolved"], [])

    def test_code_mapping_is_exact_and_does_not_guess(self):
        self.assertIsNotNone(SupplierBusinessMapping._resolve(supplier_code="SUP026"))
        self.assertIsNone(SupplierBusinessMapping._resolve(supplier_code="sup026"))
        self.assertIsNone(SupplierBusinessMapping._resolve(supplier_code="SUP-026"))

    def test_duplicate_supplier_name_requires_identity(self):
        Supplier.objects.create(code="SUP026-B", name=self.supplier.name, company_id=1)
        self.assertIsNone(SupplierBusinessMapping._resolve(supplier_name=self.supplier.name))
        self.assertEqual(
            SupplierBusinessMapping._resolve(
                supplier_id=self.supplier.pk,
                supplier_code=self.supplier.code,
                supplier_name=self.supplier.name,
            ).pk,
            self.supplier.pk,
        )

    def test_supplier_page_reads_supplier_master_only(self):
        factory = APIRequestFactory()
        request = factory.get("/api/masterdata/enterprise/suppliers/facts/")
        response = EnterpriseMasterDataFactsView.as_view()(request, entity_code="suppliers")
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["dataSource"], "procurement.Supplier")
        self.assertEqual(response.data["databaseTable"], "supplier")
        self.assertEqual(response.data["recordCount"], Supplier.objects.count())
        self.assertTrue(all(
            row["supplierSourceTrace"]["source"] == "SupplierMaster"
            for row in response.data["rows"]
        ))
        self.assertEqual(response.data["businessProgressWriteCount"], 0)

