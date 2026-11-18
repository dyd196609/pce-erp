from django.test import TestCase
from rest_framework.test import APIRequestFactory

from procurement.models import Supplier, SupplierDuplicateReview

from .supplier_master_runtime import SupplierMasterRuntimeAdapter
from .views import EnterpriseMasterDataFactsView


class SupplierMasterCompletenessV11428427227Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.first = Supplier.objects.create(
            code="SUP016", name="中兴通讯", category="电子元器件供应商",
            address="广东省深圳市中兴通讯有限公司", contact_person="张经理",
            delivery_address="江苏省苏州市中兴通讯有限公司",
            contact_phone="13700005486", credit_rating="A", company_id=1,
        )
        cls.second = Supplier.objects.create(
            code="SUP051", name="中兴通讯", category="电子元器件供应商",
            address="浙江省杭州市中兴通讯有限公司", contact_person="张经理",
            delivery_address="山东省济南市中兴通讯有限公司",
            contact_phone="13700005486", credit_rating="B", company_id=1,
        )
        for supplier in (cls.first, cls.second):
            SupplierDuplicateReview.objects.create(
                supplier=supplier,
                supplier_code=supplier.code,
                supplier_name=supplier.name,
                duplicate_reason="同名SupplierMaster共2条，禁止自动合并",
            )

    def test_supplier_field_complete_002(self):
        facts = SupplierMasterRuntimeAdapter.facts()
        self.assertEqual(facts["fieldIncompleteCount"], 0)
        self.assertEqual(facts["supplierFieldCompleteGate"], "PASS")
        self.assertTrue(all(row.category for row in facts["models"]))
        self.assertTrue(all(row.address for row in facts["models"]))
        self.assertTrue(all(row.contactName for row in facts["models"]))

    def test_supplier_duplicate_review_001(self):
        facts = SupplierMasterRuntimeAdapter.facts()
        self.assertEqual(facts["duplicateReviewMissingSupplierIds"], [])
        self.assertEqual(facts["supplierDuplicateReviewGate"], "PASS")
        self.assertEqual(len(facts["duplicateReviews"]), 2)
        self.assertTrue(all(
            review["status"] == "待人工确认"
            for review in facts["duplicateReviews"]
        ))
        self.assertEqual(Supplier.objects.filter(name="中兴通讯").count(), 2)

    def test_supplier_page_uses_same_server_facts(self):
        request = APIRequestFactory().get(
            "/api/masterdata/enterprise/suppliers/facts/"
        )
        response = EnterpriseMasterDataFactsView.as_view()(
            request, entity_code="suppliers"
        )
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pageVersion"], "V1.14.2.8.4.27.2.28")
        self.assertEqual(response.data["supplierFieldCompleteGate"], "PASS")
        self.assertEqual(response.data["supplierDuplicateReviewGate"], "PASS")
        self.assertEqual(response.data["businessProgressWriteCount"], 0)
        self.assertEqual(response.data["recordCount"], len(response.data["rows"]))
        self.assertEqual(
            response.data["strictFacts"]["supplierFieldCompleteGate"], "PASS"
        )
        self.assertTrue(all(
            row["address"] and row["category"] and row["contactName"]
            for row in response.data["rows"]
        ))
