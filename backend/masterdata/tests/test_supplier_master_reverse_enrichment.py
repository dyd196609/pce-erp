from datetime import datetime

from django.test import TestCase

from masterdata.master_data_statistics_runtime import SupplierMaterialPriceRuntime
from masterdata.models import Material
from masterdata.supplier_master_runtime import SupplierBusinessMapping
from procurement.models import (
    PriceApprovalPreparation, Supplier, SupplierBusinessReferenceMapping,
)
from procurement.price_approval_preparation_service import (
    build_supplier_recommendation_context,
    resolve_supplier_recommendation_blocked_reason,
)


class SupplierMasterReverseEnrichmentTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            code="SUP901", name="业务事实供应商", company_id=1,
            category="测试供应商", address="广东省深圳市测试地址",
            delivery_address="广东省深圳市测试收货地址",
            contact_person="测试联系人", contact_phone="13900000901",
            data_origin="BUSINESS_FACT+DEVELOPMENT_ENRICHED",
        )
        self.material = Material.objects.create(
            code="MAT901", name="测试物料", unit="件", company_id=1,
            is_active=True, is_purchased=True,
        )
        SupplierBusinessReferenceMapping.objects.create(
            legacy_supplier_code="SUP-LEGACY-901",
            legacy_supplier_name=self.supplier.name,
            supplier=self.supplier,
            evidence=[{"sourceModule": "PriceApprovalPreparation", "sourceObjectId": "PAP-901"}],
            evidence_status="UNIQUE_CONFIRMED", source_version="V45.11", created_by="test",
        )
        candidate = {
            "supplierCode": "SUP-LEGACY-901", "supplierName": self.supplier.name,
            "quotationNo": "SQ-901", "quotationStatusCode": "quotation_received",
        }
        self.preparation = PriceApprovalPreparation.objects.create(
            approval_prepare_no="PAP-901", fact_origin="legacy_verified_fact",
            source_projection_id="PROJECTION-901", source_legacy_comparison_no="QC-901",
            source_trace_alias_id="TRACE-901", supplier_candidates=[candidate],
            selected_supplier=candidate,
            material_lines=[{"materialCode": self.material.code, "materialName": self.material.name}],
            source_quotation_evidence=[{
                **candidate, "quotationAmount": "88", "currency": "CNY",
            }],
            status="completed", review_result="pass", reviewer="buyer",
            reviewed_at=datetime(2026, 8, 13, 9, 0),
            review_opinion="人工核价通过", approval_opinion="同意",
        )

    def test_explicit_business_reference_resolves_without_string_guess(self):
        resolved = SupplierBusinessMapping._resolve(
            supplier_code="SUP-LEGACY-901", supplier_name=self.supplier.name,
        )
        self.assertEqual(resolved.pk, self.supplier.pk)
        self.assertIsNone(SupplierBusinessMapping._resolve(supplier_code="SUP901-copy"))

    def test_archive_and_recommendation_share_supplier_master_reference(self):
        diagnostic = SupplierMaterialPriceRuntime.diagnose_price_approval_preparation(self.preparation)
        self.assertTrue(diagnostic["canArchive"])
        self.assertEqual(resolve_supplier_recommendation_blocked_reason(self.preparation), "")
        context = build_supplier_recommendation_context(self.preparation)
        self.assertEqual(context["selectedSupplier"]["supplierMasterId"], self.supplier.pk)
        self.assertEqual(context["supplierCandidates"][0]["supplierMasterCode"], "SUP901")

    def test_unmapped_candidate_blocks_formal_recommendation(self):
        self.preparation.supplier_candidates.append({
            "supplierCode": "SUP-NOT-MASTERED", "supplierName": "未建档候选",
        })
        self.preparation.save(update_fields=["supplier_candidates"])
        self.assertIn("SupplierMaster", resolve_supplier_recommendation_blocked_reason(self.preparation))
