from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .enterprise_master_data import ENTITY_DEFINITIONS
from .models import Material, MaterialCategory
from .views import EnterpriseMasterDataFactsView
from procurement.models import Supplier


class EnterpriseMasterDataFactsV85Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Supplier.objects.create(
            code="SUP-MASTER-V85", name="主数据验收供应商",
            contact_person="张经理", contact_phone="13712345486",
            address="浙江省验收地址", credit_rating="A", company_id=1,
        )
        category = MaterialCategory.objects.create(
            code="TEST-MATERIAL-CATEGORY", name="测试分类", company_id=1,
        )
        for index, material_type in enumerate(("raw", "semi", "finished", "auxiliary"), start=1):
            Material.objects.create(
                code=f"TEST-MATERIAL-{index:03d}", name=f"测试物料{index}",
                specification=f"SPEC-{index}", unit="件", category=category,
                material_type=material_type, company_id=1, is_active=True,
                is_purchased=True,
            )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = EnterpriseMasterDataFactsView.as_view()

    def get_payload(self, entity_code):
        request = self.factory.get(
            f"/api/masterdata/enterprise/{entity_code}/facts/"
        )
        response = self.view(request, entity_code=entity_code)
        response.render()
        return response.status_code, response.data

    def test_all_seven_master_data_domains_are_registered(self):
        self.assertEqual(len(ENTITY_DEFINITIONS), 7)

    def test_all_domains_return_server_facts(self):
        for entity_code in ENTITY_DEFINITIONS:
            with self.subTest(entity_code=entity_code):
                status_code, payload = self.get_payload(entity_code)
                self.assertEqual(status_code, 200)
                self.assertEqual(payload["factSource"], "server")

    def test_fact_load_contract_is_complete(self):
        _, payload = self.get_payload("suppliers")
        required = {
            "factLoadContractVersion",
            "factLoadStatus",
            "apiUrl",
            "httpStatus",
            "loadedAt",
            "tenantId",
            "batchId",
        }
        self.assertTrue(required.issubset(payload["factLoadFacts"]))
        self.assertEqual(payload["factLoadFacts"]["factLoadStatus"], "success")

    def test_api_strict_and_acceptance_facts_are_equal(self):
        _, payload = self.get_payload("materials")
        api_facts = {
            key: payload[key]
            for key in payload["strictFacts"]
        }
        self.assertEqual(api_facts, payload["strictFacts"])
        self.assertEqual(payload["strictFacts"], payload["acceptanceFacts"])

    def test_record_count_matches_server_rows(self):
        for entity_code in ENTITY_DEFINITIONS:
            with self.subTest(entity_code=entity_code):
                _, payload = self.get_payload(entity_code)
                self.assertEqual(payload["recordCount"], len(payload["rows"]))

    def test_supplier_fields_cover_settlement_and_performance_links(self):
        _, payload = self.get_payload("suppliers")
        row = payload["rows"][0]
        self.assertIn("settlementReference", row)
        self.assertIn("performanceReference", row)
        self.assertEqual(payload["dataSource"], "procurement.Supplier")
        self.assertEqual(payload["databaseTable"], "supplier")
        self.assertEqual(row["supplierSourceTrace"]["source"], "SupplierMaster")

    def test_material_types_cover_required_catalog(self):
        _, payload = self.get_payload("materials")
        self.assertEqual(
            {row["materialType"] for row in payload["rows"]},
            {"原材料", "半成品", "成品", "辅料"},
        )
        self.assertEqual(payload["runtimeModelType"], "MaterialRuntimeModel")
        self.assertEqual(payload["runtimeAdapterCode"], "MaterialMasterRuntimeAdapter")
        self.assertEqual(payload["databaseTable"], "material")
        self.assertTrue(all(row["materialSourceTrace"]["source"] == "MaterialMaster" for row in payload["rows"]))

    def test_bom_is_structure_only(self):
        _, payload = self.get_payload("boms")
        self.assertTrue(payload["rows"])
        for row in payload["rows"]:
            self.assertNotIn("mrpStatus", row)
            self.assertNotIn("plannedOrder", row)

    def test_transaction_and_downstream_writes_are_zero(self):
        for entity_code in ENTITY_DEFINITIONS:
            with self.subTest(entity_code=entity_code):
                _, payload = self.get_payload(entity_code)
                self.assertEqual(payload["businessProgressWriteCount"], 0)
                self.assertEqual(payload["dangerActionCount"], 0)
                self.assertEqual(payload["downstreamObjectCount"], 0)

    def test_unknown_domain_returns_read_failed_contract(self):
        status_code, payload = self.get_payload("unknown")
        self.assertEqual(status_code, 404)
        self.assertEqual(payload["factLoadFacts"]["factLoadStatus"], "read_failed")
        self.assertNotIn("recordCount", payload["strictFacts"])
