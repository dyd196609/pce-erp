from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from pde.models import EngineeringSourceRecord, OrderEngineeringInstance
from sales.models import SalesOrder
from system.models import Company


class EngineeringSourceFormalizationPreviewTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            id=1, code="COMP001", name="掌云智造科技有限公司", is_active=True,
        )
        self.user = get_user_model().objects.create_user(
            username="formalization-viewer", password="test-only",
            real_name="只读验收", company_id=self.company.pk,
            is_active=True, is_superuser=True,
        )
        self.source = EngineeringSourceRecord.objects.create(
            company=self.company,
            source_no="SRC-11",
            source_name="71行工程来源",
            source_type="controlled_import",
            source_version="R1",
            content_hash="a" * 64,
            source_payload={
                "engineeringRows": [
                    {"id": "ROW-1", "sourceSheet": "房门单", "sourceRow": 11, "product": "房门", "component": "单开门", "quantity": 1, "unit": "扇"},
                    {"id": "ROW-2", "sourceSheet": "三合一生产单", "sourceRow": 7, "product": "柜体", "component": "见光板", "quantity": 2, "unit": "块"},
                ],
                "businessOrderReference": {"sourceOrderNo": "1-4-正", "customerName": "上海王燕", "projectName": "上海 大居苑"},
            },
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_preview_is_source_complete_and_zero_write(self):
        before = (SalesOrder.objects.count(), OrderEngineeringInstance.objects.count())
        response = self.client.get(f"/api/sales/orders/source-intake/engineering-sources/{self.source.pk}/")
        self.assertEqual(response.status_code, 200)
        preview = response.data["data"]["preview"]
        self.assertEqual(preview["previewCode"], "ENGINEERING_SOURCE_SALES_FORMALIZATION_DO1")
        self.assertEqual([row["sourceRowId"] for row in preview["sourceRows"]], ["ROW-1", "ROW-2"])
        self.assertTrue(preview["readOnly"])
        self.assertFalse(preview["formalApplicationAllowed"])
        self.assertEqual(preview["strictFacts"]["businessWriteCount"], 0)
        self.assertEqual(before, (SalesOrder.objects.count(), OrderEngineeringInstance.objects.count()))

    def test_cross_company_source_is_not_visible(self):
        other = Company.objects.create(code="OTHER", name="其他公司", is_active=True)
        source = EngineeringSourceRecord.objects.create(
            company=other, source_no="OTHER-SRC", source_name="其他来源",
            source_type="controlled_import", source_version="R1",
            content_hash="b" * 64, source_payload={"engineeringRows": []},
        )
        response = self.client.get(f"/api/sales/orders/source-intake/engineering-sources/{source.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "ENGINEERING_SOURCE_NOT_FOUND")
