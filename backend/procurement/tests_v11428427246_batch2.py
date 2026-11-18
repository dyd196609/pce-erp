from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice

from .models import (
    PriceApprovalPreparation, PurchaseInquiry, PurchaseOrder, PurchaseRequest,
    PurchaseRequestItem, Supplier,
)
from .scm_page_facts import _normalized_object
from .scm_runtime_services import PurchaseOrderCreationService, ScmRuntimeActionError


class StandardPurchasePriceLinkV11428427246Batch2Tests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            code="SUP-B2", name="Batch2标准采购供应商", contact_person="王经理",
            contact_phone="13800138000", address="上海市正式地址",
            delivery_address="上海市一号仓", company_id=1,
        )
        self.material = Material.objects.create(
            code="MAT-B2", name="Batch2标准采购物料", specification="B2-100",
            unit="件", company_id=1, is_purchased=True,
        )
        self.request = PurchaseRequest.objects.create(
            request_no="PR-B2-001", request_date=date(2026, 8, 14), requester="采购员",
            department="采购部", status="approved",
        )
        self.request_item = PurchaseRequestItem.objects.create(
            purchase_request=self.request, material=self.material, material_code=self.material.code,
            material_name=self.material.name, specification=self.material.specification,
            unit=self.material.unit, quantity="2", required_date=date(2026, 9, 1), line_no=1,
        )
        self.inquiry = PurchaseInquiry.objects.create(
            inquiry_no="PI-B2-001", source_purchase_request=self.request, status="quoted",
        )
        self.preparation = PriceApprovalPreparation.objects.create(
            approval_prepare_no="PAP-B2-001", source_projection_id="LQCP-B2-001",
            source_projection_snapshot={"sourceInquiryNo": self.inquiry.inquiry_no},
            source_legacy_comparison_no="QC-B2-001", source_trace_alias_id="BTA-B2-001",
            fact_origin="legacy_verified_fact", source_quotation_evidence=[{"quotationNo": "SQ-B2"}],
            supplier_candidates=[{"supplierCode": self.supplier.code}],
            material_lines=[{"materialCode": self.material.code}],
            selected_supplier={"supplierCode": self.supplier.code}, status="completed",
            review_result="pass", review_opinion="通过", approval_opinion="通过", reviewer="采购员",
        )
        now = timezone.now()
        self.result = PriceApprovalResult.objects.create(
            result_no="PAR-B2-001", preparation=self.preparation,
            preparation_identity=str(self.preparation.pk), original_source_type="legacy_verified_fact",
            original_source_reference="QC-B2-001", supplier=self.supplier, material=self.material,
            approved_price="100", currency="CNY", tax_rate="13", tax_rate_source="enterprise_config",
            approved_by="采购员", approved_at=now, confirmed_by="采购员", confirmed_at=now,
        )
        self.price = SupplierMaterialPrice.objects.create(
            price_no="SMP-B2-001", supplier=self.supplier, material=self.material,
            approved_price="100", currency="CNY", tax_rate="13", tax_rate_source="enterprise_config",
            effective_date=date(2026, 8, 13), expiry_date=date(2027, 8, 13),
            price_approval_result=self.result, original_source_type="legacy_verified_fact",
            original_source_reference="QC-B2-001", approved_by="采购员", approved_at=now,
            confirmed_by="采购员", confirmed_at=now,
        )

    def payload(self, request_id="POCR-B2-001"):
        return {
            "requestId": request_id, "gateId": "POG-B2-001",
            "admissionResultId": "POAR-B2-001", "status": "PENDING_CONFIRMATION",
            "confirmedBy": "采购员", "purchaseRequestIds": [self.request.request_no],
            "inquiryIds": [self.inquiry.inquiry_no],
            "supplierGroups": [{
                "supplierId": self.supplier.pk, "supplierCode": self.supplier.code,
                "supplierName": self.supplier.name,
                "materialLines": [{
                    "materialCode": self.material.code,
                    "priceApprovalResultNo": self.result.result_no,
                    "supplierMaterialPriceNo": self.price.price_no,
                    "unitPrice": "100", "taxRate": "13", "currency": "CNY",
                    "effectiveDate": "2026-08-13",
                }],
            }],
        }

    def test_exact_effective_price_master_references_and_snapshots_are_persisted(self):
        orders, created = PurchaseOrderCreationService.create_from_gate_request(self.payload(), actor_id=1)
        self.assertEqual(created, 1)
        order = orders[0]
        item = order.items.get()
        self.assertEqual(order.purchase_mode, "STANDARD")
        self.assertEqual(order.price_trace_status, "CURRENT_LINKED")
        self.assertEqual(order.supplier_id, self.supplier.pk)
        self.assertEqual(order.supplier_name_snapshot, self.supplier.name)
        self.assertEqual(item.material_id, self.material.pk)
        self.assertEqual(item.source_purchase_request_item_id, self.request_item.pk)
        self.assertEqual(item.price_approval_result_id, self.result.pk)
        self.assertEqual(item.supplier_material_price_id, self.price.pk)
        self.assertEqual(item.unit_price, Decimal("100"))
        self.assertEqual(item.unit_price_snapshot, Decimal("100"))
        self.assertEqual(item.tax_rate_snapshot, Decimal("13"))
        self.assertEqual(item.currency_snapshot, "CNY")
        self.assertEqual(item.amount, Decimal("200"))
        fact = _normalized_object(order)
        self.assertEqual(fact["purchaseModeLabel"], "标准采购")
        self.assertEqual(fact["items"][0]["supplierMaterialPriceNo"], "SMP-B2-001")
        self.assertEqual(fact["items"][0]["priceApprovalResultNo"], "PAR-B2-001")

    def test_snapshot_is_protected_when_effective_price_changes_and_is_restored(self):
        order = PurchaseOrderCreationService.create_from_gate_request(self.payload(), actor_id=1)[0][0]
        self.price.approved_price = Decimal("110")
        self.price.save(update_fields=["approved_price", "updated_at"])
        order.refresh_from_db()
        self.assertEqual(order.items.get().unit_price_snapshot, Decimal("100"))
        self.assertEqual(_normalized_object(order)["items"][0]["unitPrice"], "100.0000")
        self.price.approved_price = Decimal("100")
        self.price.save(update_fields=["approved_price", "updated_at"])
        self.assertEqual(order.items.get().unit_price_snapshot, Decimal("100"))

    def test_idempotency_returns_same_order_without_second_write(self):
        first, first_count = PurchaseOrderCreationService.create_from_gate_request(self.payload(), actor_id=1)
        second, second_count = PurchaseOrderCreationService.create_from_gate_request(self.payload(), actor_id=1)
        third, third_count = PurchaseOrderCreationService.create_from_gate_request(
            self.payload("POCR-B2-SAME-GATE-NEW-REQUEST"), actor_id=1,
        )
        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)
        self.assertEqual(third_count, 0)
        self.assertEqual(first[0].pk, second[0].pk)
        self.assertEqual(first[0].pk, third[0].pk)
        self.assertEqual(PurchaseOrder.objects.count(), 1)

    def test_invalid_effective_period_rolls_back_whole_order(self):
        self.price.expiry_date = date(2026, 8, 13)
        self.price.save(update_fields=["expiry_date", "updated_at"])
        with self.assertRaises(ScmRuntimeActionError) as raised:
            PurchaseOrderCreationService.create_from_gate_request(self.payload("POCR-B2-INVALID"), actor_id=1)
        self.assertEqual(raised.exception.code, "SUPPLIER_MATERIAL_PRICE_DATE_INVALID")
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_visible_context_value_mismatch_rolls_back_whole_order(self):
        payload = self.payload("POCR-B2-VALUE-MISMATCH")
        payload["supplierGroups"][0]["materialLines"][0]["unitPrice"] = "1"
        with self.assertRaises(ScmRuntimeActionError) as raised:
            PurchaseOrderCreationService.create_from_gate_request(payload, actor_id=1)
        self.assertEqual(raised.exception.code, "STANDARD_PRICE_VALUE_CONSISTENCY_FAILED")
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_preview_returns_complete_server_context_without_write(self):
        contexts, created = PurchaseOrderCreationService.create_from_gate_request(
            self.payload("POCR-B2-PREVIEW"), actor_id=1, preview=True,
        )
        self.assertEqual(created, 0)
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(contexts[0]["purchaseMode"], "STANDARD")
        self.assertEqual(contexts[0]["priceApprovalResultNo"], self.result.result_no)
        self.assertEqual(contexts[0]["supplierMaterialPriceNo"], self.price.price_no)
        self.assertTrue(contexts[0]["priceValueConsistent"])
