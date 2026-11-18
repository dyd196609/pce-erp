from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from masterdata.master_data_statistics_runtime import SupplierMaterialPriceRuntime
from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice
from procurement.models import PriceApprovalPreparation, Supplier


class PriceApprovalDecisionArchiveTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            code="SUP-91", name="供应商91", company_id=1,
            category="综合供应商", address="测试地址", delivery_address="测试交付地址",
            contact_person="测试人", contact_phone="13800000000",
        )
        self.material = Material.objects.create(
            code="MAT-91", name="物料91", unit="件", company_id=1,
            is_active=True, is_purchased=True,
        )

    def session_preparation(self, source_type="SupplierQuotation"):
        return {
            "id": "SESSION-PAP-91-1",
            "approvalPrepareNo": "PAP-REAL-SQ-REAL-91-L1",
            "status": "completed", "reviewResult": "pass",
            "reviewer": "真实报价链验收员",
            "reviewedAt": datetime(2026, 8, 12, 9, 30, tzinfo=timezone.utc).isoformat(),
            "reviewOpinion": "人工核价通过",
            "selectedSupplier": {"supplierCode": self.supplier.code, "quotationNo": "SQ-REAL-91"},
            "materialLines": [{"materialCode": self.material.code}],
            "sourceType": source_type, "sourceObjectId": 91,
            "sourceQuotationEvidence": [{
                "supplierCode": self.supplier.code, "quotationNo": "SQ-REAL-91",
                "unitPrice": "910", "currency": "CNY",
                "sourceFactReference": "SupplierQuotation:SQ-REAL-91:line:1",
            }],
        }

    def quotation_row(self):
        quotation = SimpleNamespace(pk=91, quotation_no="SQ-REAL-91", currency="CNY")
        line = {"unitPrice": "910", "currency": "CNY"}
        return quotation, 0, line, self.supplier, self.material

    def test_supplier_quotation_confirmation_persists_and_is_idempotent(self):
        preparation = self.session_preparation()
        with patch.object(SupplierMaterialPriceRuntime, "_source_matched_acceptance_preparations",
                          return_value=[preparation]), patch(
            "masterdata.master_data_statistics_runtime._quotation_runtime_lines",
            side_effect=lambda: iter([self.quotation_row()]),
        ):
            first = SupplierMaterialPriceRuntime.archive_price_approval_preparation(preparation["id"], {})
            second = SupplierMaterialPriceRuntime.archive_price_approval_preparation(preparation["id"], {})

        self.assertEqual(first["priceNo"], second["priceNo"])
        self.assertEqual(PriceApprovalResult.objects.count(), 1)
        self.assertEqual(SupplierMaterialPrice.objects.count(), 1)
        price = SupplierMaterialPrice.objects.get()
        self.assertEqual(price.effective_date.isoformat(), first["effectiveDate"])
        self.assertIsNone(price.expiry_date)
        self.assertEqual(str(price.tax_rate), "13.00")
        self.assertTrue(SupplierMaterialPriceRuntime.list_runtime_models()[0].persisted)

    def test_legacy_source_remains_traceable_after_new_confirmation(self):
        preparation = self.session_preparation("legacy_verified_fact")
        preparation["sourceQuotationEvidence"][0]["sourceFactReference"] = "legacy_verified_fact:91"
        with patch.object(SupplierMaterialPriceRuntime, "_source_matched_acceptance_preparations",
                          return_value=[preparation]):
            result = SupplierMaterialPriceRuntime.archive_price_approval_preparation(preparation["id"], {})
        price = SupplierMaterialPrice.objects.get(price_no=result["priceNo"])
        self.assertEqual(price.original_source_type, "legacy_verified_fact")
        self.assertEqual(price.price_source_type, "PriceApprovalResult")

    def test_persistent_preparation_reports_precise_supplier_mapping_failure(self):
        preparation = PriceApprovalPreparation.objects.create(
            approval_prepare_no="PAP-MAPPING-FAIL",
            fact_origin="legacy_verified_fact",
            source_projection_id="LEGACY-1",
            source_legacy_comparison_no="QC-LEGACY-1",
            source_trace_alias_id="TRACE-1",
            material_lines=[{"materialCode": self.material.code, "materialName": self.material.name}],
            source_quotation_evidence=[{
                "supplierCode": "SUP-NOT-FOUND", "quotationAmount": "10", "currency": "CNY",
            }],
            selected_supplier={"supplierCode": "SUP-NOT-FOUND", "supplierName": "不存在供应商"},
            status="approved", reviewer="admin", reviewed_at=datetime(2026, 8, 7, 12, 0),
            review_opinion="通过", approval_opinion="同意",
        )
        diagnostic = SupplierMaterialPriceRuntime.diagnose_price_approval_preparation(preparation)
        self.assertFalse(diagnostic["canArchive"])
        self.assertEqual(diagnostic["blockReasonCode"], "SUPPLIER_MAPPING_FAILED")
        with self.assertRaisesMessage(ValueError, "SUPPLIER_MAPPING_FAILED"):
            SupplierMaterialPriceRuntime.archive_price_approval_preparation(preparation.pk, {})

    def test_manual_expiry_and_tax_maintenance_are_audited(self):
        preparation = self.session_preparation()
        with patch.object(SupplierMaterialPriceRuntime, "_source_matched_acceptance_preparations",
                          return_value=[preparation]), patch(
            "masterdata.master_data_statistics_runtime._quotation_runtime_lines",
            side_effect=lambda: iter([self.quotation_row()]),
        ):
            archived = SupplierMaterialPriceRuntime.archive_price_approval_preparation(preparation["id"], {})
        updated = SupplierMaterialPriceRuntime.update_session_price(archived["priceNo"], {
            "taxRate": "9", "effectiveDate": archived["effectiveDate"],
            "expiryDate": "2027-08-12", "modifyReason": "合同有效期调整",
        }, actor="tax-maintainer")
        self.assertEqual(updated.taxRate, "9")
        self.assertEqual(updated.expiryDate, "2027-08-12")
        self.assertEqual(updated.taxModifiedBy, "tax-maintainer")
        self.assertEqual(len(SupplierMaterialPrice.objects.get().modification_audit), 1)
