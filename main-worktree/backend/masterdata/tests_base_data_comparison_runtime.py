from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import UnitOfMeasure
from procurement.models import Supplier
from sales.models import Customer
from system.models import Company, User

from .views import BaseDataComparisonPreviewView


class BaseDataComparisonRuntimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="BDC", name="基础数据对照测试公司")
        cls.user = User.objects.create_user(username="bdc-user", real_name="对照用户", company_id=cls.company.pk)
        Customer.objects.create(company=cls.company, code="C-001", name="上海李保华")
        Supplier.objects.create(code="BDC-S-001", name="阿哩阿哆", company_id=cls.company.pk)
        UnitOfMeasure.objects.update_or_create(
            code="kg", company_id=cls.company.pk,
            defaults={"name": "千克", "symbol": "kg", "dimension": "mass"},
        )
        UnitOfMeasure.objects.update_or_create(
            code="m2", company_id=cls.company.pk,
            defaults={"name": "平方米", "symbol": "m²", "dimension": "area"},
        )

    def payload(self, entity):
        request = APIRequestFactory().get(f"/api/masterdata/base-data-comparison/{entity}/")
        force_authenticate(request, user=self.user)
        response = BaseDataComparisonPreviewView.as_view()(request, entity_code=entity)
        response.render()
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_customer_preview_lists_all_88_source_names_and_exact_match(self):
        payload = self.payload("customers")
        self.assertEqual(payload["summary"]["sourceRecordCount"], 88)
        self.assertEqual(payload["summary"]["exactMatchCount"], 1)
        self.assertEqual(payload["productionBusinessMasterDataWriteCount"], 0)

    def test_supplier_preview_preserves_18_valid_and_2_blank_names(self):
        payload = self.payload("suppliers")
        self.assertEqual(payload["summary"]["sourceRecordCount"], 20)
        self.assertEqual(payload["summary"]["validSourceCount"], 18)
        self.assertEqual(payload["summary"]["invalidSourceCount"], 2)

    def test_uom_preview_does_not_auto_map_square_or_area(self):
        payload = self.payload("uoms")
        self.assertEqual(payload["summary"]["sourceRecordCount"], 12)
        pending = {row["sourceValue"]: row for row in payload["rows"] if row["sourceValue"] in {"平方", "面积"}}
        self.assertEqual(set(pending), {"平方", "面积"})
        self.assertTrue(all(row["matchStatus"] == "MANUAL_DECISION_REQUIRED" for row in pending.values()))
        self.assertTrue(all(row["proposedAction"] == "NO_AUTOMATIC_MAPPING" for row in pending.values()))
