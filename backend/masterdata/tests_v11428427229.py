from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from procurement.models import PurchaseInquiry, PurchaseRequest, Supplier, SupplierQuotation

from .master_data_statistics_runtime import (
    MasterDataStatisticsRuntime,
    MaterialSupplierRelationRuntime,
    SupplierMaterialPriceRuntime,
)
from .models import Material
from .views import MasterDataStatisticsFactsView


class MasterDataStatisticsRuntimeV11428427229Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.supplier = Supplier.objects.create(
            code="SUP-STAT-001", name="统计验收供应商", company_id=1,
            category="综合供应商", address="浙江省杭州市统计验收有限公司",
            delivery_address="江苏省苏州市统计验收有限公司",
            contact_person="张经理", contact_phone="13700005486",
        )
        cls.material_a = Material.objects.create(
            code="MAT-STAT-001", name="统计验收物料A", unit="件",
            company_id=1, is_active=True, is_purchased=True,
        )
        cls.material_b = Material.objects.create(
            code="MAT-STAT-002", name="统计验收物料B", unit="件",
            company_id=1, is_active=True, is_purchased=True,
        )
        request = PurchaseRequest.objects.create(
            request_no="PR-STAT-001", request_date=date(2026, 8, 11),
            requester="统计验收员", department="采购部", status="approved",
        )
        inquiry = PurchaseInquiry.objects.create(
            inquiry_no="PI-STAT-001", source_purchase_request=request, status="quoted",
        )
        SupplierQuotation.objects.create(
            quotation_no="SQ-STAT-001", source_inquiry=inquiry,
            supplier_id=cls.supplier.code, supplier_name=cls.supplier.name,
            quotation_status="received", price=Decimal("25"),
            items=[
                {"materialCode": cls.material_a.code, "unitPrice": "25"},
                {"materialId": cls.material_b.pk, "unitPrice": "0"},
            ],
        )

    def test_four_counts_come_from_governed_runtimes(self):
        before = {
            "materials": Material.objects.count(),
            "suppliers": Supplier.objects.count(),
            "quotations": SupplierQuotation.objects.count(),
        }
        facts = MasterDataStatisticsRuntime.facts()
        self.assertEqual(facts["materialCount"], 2)
        self.assertEqual(facts["supplierCount"], 1)
        self.assertEqual(facts["supplierMaterialRelationCount"], 2)
        self.assertEqual(facts["supplierPriceCount"], 1)
        self.assertEqual(
            facts["supplierMaterialRelationCount"],
            len(MaterialSupplierRelationRuntime.list_runtime_models()),
        )
        self.assertEqual(
            facts["supplierPriceCount"],
            len(SupplierMaterialPriceRuntime.list_runtime_models()),
        )
        self.assertEqual(facts["businessProgressWriteCount"], 0)
        self.assertEqual(before, {
            "materials": Material.objects.count(),
            "suppliers": Supplier.objects.count(),
            "quotations": SupplierQuotation.objects.count(),
        })

    def test_statistics_api_reuses_runtime_facts(self):
        request = APIRequestFactory().get(
            "/api/masterdata/statistics/runtime/facts/"
        )
        response = MasterDataStatisticsFactsView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["runtimeCode"], "MasterDataStatisticsRuntime")
        self.assertEqual(response.data["pageVersion"], "V1.14.2.8.4.27.2.30")
        self.assertEqual(response.data["materialCount"], 2)
        self.assertEqual(response.data["supplierCount"], 1)
        self.assertEqual(response.data["strictFacts"]["materialCount"], 2)
        self.assertEqual(response.data["businessProgressWriteCount"], 0)
        self.assertFalse(response.data["strictFacts"]["databaseChanged"])
