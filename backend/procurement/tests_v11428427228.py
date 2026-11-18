from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from procurement.models import PurchaseOrder, Supplier
from procurement.scm_page_facts import ScmStandardPageFactsView, _normalized_object


class SupplierDeliveryPurchaseOrderViewV11428427228Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.supplier = Supplier.objects.create(
            code="SUP028", name="交付信息验收供应商", category="综合供应商",
            address="浙江省杭州市交付信息验收供应商有限公司",
            delivery_address="江苏省苏州市交付信息验收供应商有限公司",
            contact_person="张经理", contact_phone="13700005486",
            credit_rating="A", company_id=1,
        )
        cls.order = PurchaseOrder.objects.create(
            po_no="PO-SUPPLIER-VIEW-028", supplier=cls.supplier,
            order_date=date(2026, 8, 11), expected_date=date(2026, 9, 11),
            total_amount=Decimal("100.00"), buyer="测试采购员", company_id=1,
        )

    def test_purchase_order_supplier_view_001(self):
        fact = _normalized_object(self.order)
        self.assertEqual(fact["supplierName"], self.supplier.name)
        self.assertEqual(fact["supplierContact"], self.supplier.contact_person)
        self.assertEqual(fact["supplierPhone"], "137****5486")
        self.assertEqual(fact["supplierAddress"], self.supplier.address)
        self.assertEqual(
            fact["supplierDeliveryAddress"], self.supplier.delivery_address
        )
        self.assertEqual(fact["supplierInformationSource"], "SupplierMaster")

    def test_purchase_order_page_api_reuses_supplier_master(self):
        request = APIRequestFactory().get(
            "/api/procurement/scm-page-facts/purchase-order/"
        )
        response = ScmStandardPageFactsView.as_view()(
            request, page_code="purchase-order"
        )
        response.render()
        self.assertEqual(response.status_code, 200)
        row = response.data["data"]["objects"][0]
        self.assertEqual(row["supplierDeliveryAddress"], self.supplier.delivery_address)
        self.assertEqual(row["supplierInformationSource"], "SupplierMaster")
        self.assertEqual(response.data["data"]["businessProgressWriteCount"], 0)
        self.assertEqual(PurchaseOrder.objects.count(), 1)
