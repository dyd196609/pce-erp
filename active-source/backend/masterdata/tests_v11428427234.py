from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from procurement.models import (
    PurchaseInquiry,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    Supplier,
    SupplierQuotation,
)

from .master_data_statistics_runtime import SupplierPriceFactRuntime
from .models import Material
from .views import SupplierPriceFactFactsView


class SupplierPriceFactRuntimeV11428427234Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.supplier = Supplier.objects.create(
            code="SUP-PRICE-001", name="价格事实测试供应商", company_id=1,
            category="综合供应商", address="浙江省杭州市价格事实测试有限公司",
            delivery_address="浙江省杭州市价格事实测试有限公司",
        )
        cls.material = Material.objects.create(
            code="MT-PRICE-001", name="价格事实测试物料", unit="件",
            company_id=1, is_active=True, is_purchased=True,
        )
        request = PurchaseRequest.objects.create(
            request_no="PR-PRICE-001", request_date=date(2026, 8, 10),
            requester="价格事实测试员", department="采购部", status="approved",
        )
        inquiry = PurchaseInquiry.objects.create(
            inquiry_no="PI-PRICE-001", source_purchase_request=request,
            supplier=cls.supplier.code, status="quoted",
        )
        SupplierQuotation.objects.create(
            quotation_no="SQ-PRICE-001", source_inquiry=inquiry,
            supplier_id=cls.supplier.code, supplier_name=cls.supplier.name,
            quotation_status="received", price=Decimal("66"), currency="CNY",
            items=[{
                "materialCode": cls.material.code,
                "unitPrice": "66",
                "currency": "CNY",
                "unit": "件",
                "taxRate": "13",
                "deliveryPeriod": 7,
                "effectiveDate": "2026-08-11",
                "expiryDate": "2026-09-10",
            }],
        )
        same_day_order = PurchaseOrder.objects.create(
            po_no="PO-PRICE-001", supplier=cls.supplier,
            order_date=date(2026, 8, 11), expected_date=date(2026, 8, 18),
            company_id=1, total_amount=Decimal("90"), status="draft",
        )
        PurchaseOrderItem.objects.create(
            po=same_day_order, material=cls.material, product_name=cls.material.name,
            quantity=Decimal("1"), unit_price=Decimal("90"), amount=Decimal("90"),
            expected_date=date(2026, 8, 18),
        )
        historical_order = PurchaseOrder.objects.create(
            po_no="PO-PRICE-002", supplier=cls.supplier,
            order_date=date(2026, 7, 1), expected_date=date(2026, 7, 8),
            company_id=1, total_amount=Decimal("80"), status="closed",
        )
        PurchaseOrderItem.objects.create(
            po=historical_order, material=cls.material, product_name=cls.material.name,
            quantity=Decimal("1"), unit_price=Decimal("80"), amount=Decimal("80"),
            expected_date=date(2026, 7, 8),
        )

    def test_model_has_required_fields_and_strict_master_binding(self):
        facts = SupplierPriceFactRuntime.facts()
        quote = next(item for item in facts["models"] if item.sourceType == "SupplierQuotation")
        self.assertEqual(quote.supplierId, self.supplier.pk)
        self.assertEqual(quote.supplierCode, self.supplier.code)
        self.assertEqual(quote.materialId, self.material.pk)
        self.assertEqual(quote.materialCode, self.material.code)
        self.assertEqual(quote.unitPrice, "66")
        self.assertEqual(quote.currency, "CNY")
        self.assertEqual(quote.unit, "件")
        self.assertEqual(quote.taxRate, "13")
        self.assertEqual(quote.deliveryPeriod, 7)
        self.assertEqual(quote.effectiveDate, "2026-08-11")
        self.assertEqual(quote.expiryDate, "2026-09-10")
        self.assertEqual(quote.sourceReference, "SupplierQuotation:SQ-PRICE-001:line:1")

    def test_source_priority_uniqueness_and_history_protection(self):
        facts = SupplierPriceFactRuntime.facts()
        keys = [item.uniqueness_key for item in facts["models"]]
        self.assertEqual(len(keys), len(set(keys)))
        same_day = [
            item for item in facts["models"]
            if item.effectiveDate == "2026-08-11"
        ]
        self.assertEqual(len(same_day), 1)
        self.assertEqual(same_day[0].sourceType, "SupplierQuotation")
        self.assertEqual(facts["sourcePriority"], [
            "SupplierQuotation", "SupplierMaterialPrice", "PurchaseOrderHistory",
        ])
        self.assertEqual(facts["historyFactCount"], 3)
        self.assertEqual(facts["priceFactCount"], 2)
        self.assertEqual(facts["duplicateEffectivePeriodCount"], 1)
        self.assertEqual(
            facts["duplicateEffectivePeriodCandidates"][0].sourceType,
            "PurchaseOrderHistory",
        )
        with self.assertRaises(FrozenInstanceError):
            same_day[0].unitPrice = "1"

    def test_runtime_exposes_only_intelligence_extension_points(self):
        facts = SupplierPriceFactRuntime.facts()
        self.assertFalse(facts["autoDecisionEnabled"])
        self.assertEqual(facts["businessProgressWriteCount"], 0)
        self.assertEqual(facts["intelligenceExtensionPoints"], [
            "PRICE_HISTORY_ANALYSIS",
            "PRICE_TREND_ANALYSIS",
            "PRICE_ANOMALY_DETECTION",
            "SUPPLIER_PRICE_COMPARISON",
        ])

    def test_read_only_api_reuses_runtime_facts(self):
        request = APIRequestFactory().get(
            "/api/masterdata/prices/supplier-price-facts/runtime/facts/"
        )
        response = SupplierPriceFactFactsView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["runtimeCode"], "SupplierPriceFactRuntime")
        self.assertEqual(response.data["runtimeModelType"], "SupplierPriceFactModel")
        self.assertEqual(response.data["priceFactCount"], len(response.data["rows"]))
        self.assertEqual(response.data["historyFactCount"], len(response.data["historyRows"]))
        self.assertFalse(response.data["autoDecisionEnabled"])
        self.assertEqual(response.data["businessProgressWriteCount"], 0)
        self.assertFalse(response.data["databaseStructureChanged"])
