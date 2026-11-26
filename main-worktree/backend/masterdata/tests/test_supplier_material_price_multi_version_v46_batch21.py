from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice
from procurement.models import Supplier


class SupplierMaterialPriceMultiVersionV46Batch21Tests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.supplier = Supplier.objects.create(
            code="SUP-B21", name="多版本供应商", company_id=1,
        )
        self.material = Material.objects.create(
            code="MAT-B21", name="多版本物料", unit="件", company_id=1,
        )
        now = timezone.now()
        today = date.today()
        for index, amount in enumerate(("120", "132"), start=1):
            confirmed_at = now + timedelta(seconds=index)
            result = PriceApprovalResult.objects.create(
                result_no=f"PAR-B21-{index}", preparation_identity=f"PAP-B21-{index}",
                original_source_type="SupplierQuotation",
                original_source_reference=f"SupplierQuotation:SQ-B21:line:{index}",
                supplier=self.supplier, material=self.material, approved_price=amount,
                currency="CNY", tax_rate="13", tax_rate_source="enterprise_config",
                approved_by="buyer", approved_at=confirmed_at,
                confirmed_by="buyer", confirmed_at=confirmed_at,
            )
            SupplierMaterialPrice.objects.create(
                price_no=f"SMP-B21-{index}", supplier=self.supplier, material=self.material,
                approved_price=amount, currency="CNY", tax_rate="13",
                tax_rate_source="enterprise_config", effective_date=today,
                expiry_date=today + timedelta(days=365), price_approval_result=result,
                original_source_type="SupplierQuotation",
                original_source_reference=f"SupplierQuotation:SQ-B21:line:{index}",
                approved_by="buyer", approved_at=confirmed_at,
                confirmed_by="buyer", confirmed_at=confirmed_at,
            )

    def test_same_scope_versions_preserve_history_and_choose_latest_confirmation(self):
        response = self.client.get(
            "/api/masterdata/prices/supplier-material-prices/runtime/facts/",
            {"supplierCode": "SUP-B21", "materialCode": "MAT-B21"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["formalPriceCount"], 2)
        rows = {row["priceNo"]: row for row in response.data["rows"]}
        self.assertEqual(set(rows), {"SMP-B21-1", "SMP-B21-2"})
        self.assertEqual(rows["SMP-B21-1"]["versionStatus"], "HISTORICAL")
        self.assertEqual(rows["SMP-B21-2"]["versionStatus"], "CURRENT")
        self.assertFalse(rows["SMP-B21-1"]["isCurrentApplicable"])
        self.assertTrue(rows["SMP-B21-2"]["isCurrentApplicable"])
        self.assertEqual(rows["SMP-B21-1"]["nextPriceNo"], "SMP-B21-2")
        self.assertEqual(rows["SMP-B21-2"]["previousPriceNo"], "SMP-B21-1")
        self.assertEqual(rows["SMP-B21-1"]["overlapClassification"],
                         "B_HISTORICAL_VERSION_RELATION")
        self.assertEqual(rows["SMP-B21-2"]["scopeStatus"],
                         "DEFAULT_SCOPE_NO_DIMENSIONS")
        self.assertTrue(rows["SMP-B21-1"]["createdAt"])
        self.assertEqual(SupplierMaterialPrice.objects.count(), 2)

    def test_exact_batch_query_does_not_guess_another_material(self):
        response = self.client.get(
            "/api/masterdata/prices/supplier-material-prices/runtime/facts/",
            {"supplierCode": "SUP-B21", "materialCode": "UNKNOWN"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["formalPriceCount"], 0)
        self.assertEqual(response.data["rows"], [])
        self.assertEqual(response.data["unfilteredFormalPriceCount"], 2)
