from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.master_data_statistics_runtime import SupplierMaterialPriceRuntime
from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice
from procurement.models import Supplier


class SupplierMaterialPriceEditPersistenceV4512Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="price-maintainer", password="test", real_name="价格维护员", company_id=1,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        supplier = Supplier.objects.create(code="SUP912", name="V45.12供应商", company_id=1)
        material = Material.objects.create(code="MAT912", name="V45.12物料", unit="件", company_id=1)
        result = PriceApprovalResult.objects.create(
            result_no="PAR-912", preparation_identity="PAP-912", original_source_type="SupplierQuotation",
            original_source_reference="SQ-912", supplier=supplier, material=material, approved_price="12.00",
            currency="CNY", tax_rate="13", tax_rate_source="PCE_ENTERPRISE_PROCUREMENT_DEFAULT_TAX_RATE",
            approved_by="buyer", approved_at=datetime(2026, 8, 13),
            confirmed_by="buyer", confirmed_at=datetime(2026, 8, 13),
        )
        self.price = SupplierMaterialPrice.objects.create(
            price_no="SMP-912", supplier=supplier, material=material, approved_price="12.00",
            currency="CNY", tax_rate="13", tax_rate_source="PCE_ENTERPRISE_PROCUREMENT_DEFAULT_TAX_RATE",
            effective_date=date(2026, 8, 13), price_approval_result=result,
            original_source_type="SupplierQuotation", original_source_reference="SQ-912",
            approved_by="buyer", approved_at=result.approved_at,
            confirmed_by="buyer", confirmed_at=result.confirmed_at,
        )

    def test_patch_persists_expiry_tax_reason_and_runtime_reread(self):
        response = self.client.patch(
            "/api/masterdata/prices/supplier-material-prices/runtime/SMP-912/maintenance/",
            {"taxRate": "9", "effectiveDate": "2026-08-13", "expiryDate": "2028-08-13",
             "modifyReason": "V45.12持久化验收"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.price.refresh_from_db()
        self.assertEqual(self.price.expiry_date.isoformat(), "2028-08-13")
        self.assertEqual(str(self.price.tax_rate), "9.00")
        self.assertEqual(str(self.price.approved_price), "12.0000")
        self.assertEqual(self.price.modification_reason, "V45.12持久化验收")
        row = next(item for item in SupplierMaterialPriceRuntime.list_runtime_models()
                   if item.priceNo == "SMP-912")
        self.assertEqual(row.expiryDate, "2028-08-13")
        self.assertEqual(row.taxRate, "9")
        self.assertEqual(row.unitPrice, "12.0000")

    def test_patch_rejects_missing_reason_and_invalid_period(self):
        url = "/api/masterdata/prices/supplier-material-prices/runtime/SMP-912/maintenance/"
        missing = self.client.patch(url, {"taxRate": "13", "effectiveDate": "2026-08-13",
                                          "expiryDate": "2028-08-13"}, format="json")
        self.assertEqual(missing.status_code, 400)
        invalid = self.client.patch(url, {"taxRate": "13", "effectiveDate": "2026-08-13",
                                          "expiryDate": "2026-08-12", "modifyReason": "错误日期"}, format="json")
        self.assertEqual(invalid.status_code, 400)

    def test_patch_rejects_direct_formal_unit_price_overwrite(self):
        response = self.client.patch(
            "/api/masterdata/prices/supplier-material-prices/runtime/SMP-912/maintenance/",
            {"unitPrice": "12.01", "taxRate": "13", "effectiveDate": "2026-08-13",
             "expiryDate": "", "modifyReason": "不允许覆盖正式价格"}, format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["errorCode"], "SUPPLIER_MATERIAL_PRICE_UNIT_PRICE_READ_ONLY")
        self.price.refresh_from_db()
        self.assertEqual(str(self.price.approved_price), "12.0000")
        self.assertEqual(self.price.modification_audit, [])
