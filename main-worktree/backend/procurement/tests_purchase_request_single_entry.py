from datetime import date

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from masterdata.models import Material
from procurement.models import PurchaseRequest, PurchaseRequestItem
from procurement.scm_page_facts import ScmStandardPageFactsView


class PurchaseRequestFormalFactsContractTests(TestCase):
    def test_formal_facts_report_header_and_item_counts_with_server_identities(self):
        material = Material.objects.create(
            code="PR-SINGLE-ENTRY-MAT", name="采购申请入口验证物料",
            specification="验证规格", unit="件", company_id=1, is_purchased=True,
        )
        purchase_request = PurchaseRequest.objects.create(
            request_no="PR-SINGLE-ENTRY-001",
            request_date=date(2026, 9, 10),
            requester="隔离测试",
            department="采购部",
            quantity=2,
            amount=0,
            source_type="ManualRequest",
        )
        PurchaseRequestItem.objects.create(
            purchase_request=purchase_request,
            material=material,
            material_code=material.code,
            material_name=material.name,
            line_no=1,
            quantity=2,
            unit="件",
            required_date=date(2026, 9, 30),
        )

        request = APIRequestFactory().get("/api/procurement/scm-page-facts/purchase-request/")
        response = ScmStandardPageFactsView.as_view()(request, page_code="purchase-request")
        response.render()

        self.assertEqual(response.status_code, 200)
        facts = response.data["data"]
        self.assertEqual(facts["recordCount"], 1)
        self.assertEqual(facts["itemCount"], 1)
        self.assertEqual(facts["objects"][0]["requestNo"], "PR-SINGLE-ENTRY-001")
        self.assertEqual(facts["objects"][0]["sourceType"], "ManualRequest")
        self.assertFalse(facts["productionUserDataWritten"])
