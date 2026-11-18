from datetime import date, timedelta
import unittest

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice

from .models import PriceApprovalPreparation, PurchaseOrder, PurchaseOrderItem, Supplier
from .scm_runtime_services import PurchaseOrderCreationService, ScmRuntimeActionError


@unittest.skip("Batch2.2 automatic evidence retained; creation contract superseded by Batch2.2-R1 DIRECT workbench")
class PurchaseOrderManualCreationV11428427246Batch22Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="batch22-buyer", password="test", real_name="Batch2.2采购员", company_id=1,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.supplier = Supplier.objects.create(
            code="SUP-B22", name="Batch2.2正式供应商", contact_person="王经理",
            contact_phone="13800138000", address="上海市正式地址",
            delivery_address="上海市一号仓", company_id=1, is_active=True,
        )
        self.other_supplier = Supplier.objects.create(
            code="SUP-B22-X", name="Batch2.2其他供应商", company_id=1, is_active=True,
        )
        self.material = Material.objects.create(
            code="MAT-B22", name="Batch2.2正式物料", specification="B22-100",
            unit="件", company_id=1, is_active=True, is_purchased=True,
        )
        self.other_material = Material.objects.create(
            code="MAT-B22-X", name="Batch2.2其他物料", specification="B22-X",
            unit="件", company_id=1, is_active=True, is_purchased=True,
        )
        self.preparation = PriceApprovalPreparation.objects.create(
            approval_prepare_no="PAP-B22", source_projection_id="LQCP-B22",
            source_projection_snapshot={"sourceInquiryNo": "PI-B22"},
            source_legacy_comparison_no="QC-B22", source_trace_alias_id="BTA-B22",
            fact_origin="legacy_verified_fact", source_quotation_evidence=[{"quotationNo": "SQ-B22"}],
            supplier_candidates=[{"supplierCode": self.supplier.code}],
            material_lines=[{"materialId": self.material.pk, "materialCode": self.material.code,
                             "materialName": self.material.name}],
            selected_supplier={"supplierId": self.supplier.pk, "supplierCode": self.supplier.code,
                               "supplierName": self.supplier.name},
            status="completed", review_result="pass", review_opinion="通过",
            approval_opinion="通过", reviewer="采购员",
        )
        earlier = timezone.now() - timedelta(minutes=1)
        later = timezone.now()
        self.historical_result = PriceApprovalResult.objects.create(
            result_no="PAR-B22-H", preparation=self.preparation, preparation_identity="PAP-B22-H",
            original_source_type="SupplierQuotation", original_source_reference="SQ-B22:H",
            supplier=self.supplier, material=self.material, approved_price="132", currency="CNY",
            tax_rate="13", tax_rate_source="enterprise_config", approved_by="采购员",
            approved_at=earlier, confirmed_by="采购员", confirmed_at=earlier,
        )
        self.historical_price = SupplierMaterialPrice.objects.create(
            price_no="SMP-B22-H", supplier=self.supplier, material=self.material,
            approved_price="132", currency="CNY", tax_rate="13",
            tax_rate_source="enterprise_config", effective_date=date.today() - timedelta(days=1),
            expiry_date=date.today() + timedelta(days=365),
            price_approval_result=self.historical_result, original_source_type="SupplierQuotation",
            original_source_reference="SQ-B22:H", approved_by="采购员", approved_at=earlier,
            confirmed_by="采购员", confirmed_at=earlier,
        )
        self.current_result = PriceApprovalResult.objects.create(
            result_no="PAR-B22-C", preparation=self.preparation, preparation_identity="PAP-B22-C",
            original_source_type="SupplierQuotation", original_source_reference="SQ-B22:C",
            supplier=self.supplier, material=self.material, approved_price="120", currency="CNY",
            tax_rate="13", tax_rate_source="enterprise_config", approved_by="采购员",
            approved_at=later, confirmed_by="采购员", confirmed_at=later,
        )
        self.current_price = SupplierMaterialPrice.objects.create(
            price_no="SMP-B22-C", supplier=self.supplier, material=self.material,
            approved_price="120", currency="CNY", tax_rate="13",
            tax_rate_source="enterprise_config", effective_date=date.today() - timedelta(days=1),
            expiry_date=date.today() + timedelta(days=365),
            price_approval_result=self.current_result, original_source_type="SupplierQuotation",
            original_source_reference="SQ-B22:C", approved_by="采购员", approved_at=later,
            confirmed_by="采购员", confirmed_at=later,
        )

    def payload(self, key="PO-MANUAL-B22-001"):
        return {
            "creationMode": "MANUAL_SELECTION", "purchaseMode": "STANDARD",
            "idempotencyKey": key, "supplierId": self.supplier.pk,
            "materialId": self.material.pk, "quantity": "3",
            "supplierMaterialPriceId": self.current_price.pk,
            "supplierMaterialPriceNo": self.current_price.price_no,
            "orderDate": date.today().isoformat(),
            "expectedDate": (date.today() + timedelta(days=7)).isoformat(),
            "buyer": "Batch2.2采购员", "paymentTerms": "月结30天",
            "deliveryAddress": "上海市一号仓", "deliveryRequirements": "按期交付",
            "remark": "Batch2.2人工创建验收",
        }

    def preview(self, payload=None):
        contexts, count = PurchaseOrderCreationService.create_from_manual_request(
            payload or self.payload(), self.user.pk, preview=True,
        )
        self.assertEqual(count, 0)
        return contexts[0]

    def test_preview_checks_real_master_relation_price_and_writes_nothing(self):
        before = (PurchaseOrder.objects.count(), PurchaseOrderItem.objects.count())
        context = self.preview()
        self.assertEqual(context["gateStatus"], "PASS")
        self.assertEqual(context["supplierMaterialPriceId"], self.current_price.pk)
        self.assertEqual(context["unitPrice"], "120.0000")
        self.assertTrue(all(row["result"] == "PASS" for row in context["checks"]))
        self.assertEqual(before, (PurchaseOrder.objects.count(), PurchaseOrderItem.objects.count()))

    def test_explicit_confirm_creates_canonical_order_and_snapshots(self):
        payload = self.payload()
        payload.update({"admissionToken": self.preview(payload)["admissionToken"], "humanConfirmed": True})
        orders, created = PurchaseOrderCreationService.create_from_manual_request(payload, self.user.pk)
        self.assertEqual(created, 1)
        order = orders[0]
        item = order.items.get()
        self.assertEqual(order.purchase_mode, "STANDARD")
        self.assertEqual(order.source_type, "MANUAL_STANDARD_PURCHASE_ORDER_CREATION")
        self.assertEqual(order.supplier_id, self.supplier.pk)
        self.assertEqual(order.supplier_name_snapshot, self.supplier.name)
        self.assertEqual(item.material_id, self.material.pk)
        self.assertEqual(item.supplier_material_price_id, self.current_price.pk)
        self.assertEqual(item.price_approval_result_id, self.current_result.pk)
        self.assertEqual(str(item.unit_price_snapshot), "120.0000")
        self.assertEqual(str(item.tax_rate_snapshot), "13.00")
        self.assertEqual(item.currency_snapshot, "CNY")
        self.assertEqual(str(order.total_amount), "360.00")

    def test_same_idempotency_key_returns_existing_order(self):
        payload = self.payload("PO-MANUAL-B22-IDEMPOTENT")
        payload.update({"admissionToken": self.preview(payload)["admissionToken"], "humanConfirmed": True})
        first, first_count = PurchaseOrderCreationService.create_from_manual_request(payload, self.user.pk)
        second, second_count = PurchaseOrderCreationService.create_from_manual_request(payload, self.user.pk)
        self.assertEqual((first_count, second_count), (1, 0))
        self.assertEqual(first[0].pk, second[0].pk)
        self.assertEqual(PurchaseOrder.objects.count(), 1)

    def test_missing_supplier_is_blocked(self):
        payload = self.payload()
        payload["supplierId"] = ""
        with self.assertRaises(ScmRuntimeActionError) as raised:
            self.preview(payload)
        self.assertEqual(raised.exception.code, "SUPPLIER_REQUIRED")

    def test_missing_material_is_blocked(self):
        payload = self.payload()
        payload["materialId"] = ""
        with self.assertRaises(ScmRuntimeActionError) as raised:
            self.preview(payload)
        self.assertEqual(raised.exception.code, "MATERIAL_REQUIRED")

    def test_zero_quantity_is_blocked(self):
        payload = self.payload()
        payload["quantity"] = "0"
        with self.assertRaises(ScmRuntimeActionError) as raised:
            self.preview(payload)
        self.assertEqual(raised.exception.code, "INVALID_QUANTITY")

    def test_missing_price_is_blocked(self):
        payload = self.payload()
        payload["supplierMaterialPriceId"] = ""
        payload["supplierMaterialPriceNo"] = ""
        with self.assertRaises(ScmRuntimeActionError) as raised:
            self.preview(payload)
        self.assertEqual(raised.exception.code, "SUPPLIER_MATERIAL_PRICE_REQUIRED")

    def test_price_supplier_or_material_mismatch_is_blocked(self):
        payload = self.payload()
        payload["supplierId"] = self.other_supplier.pk
        with self.assertRaises(ScmRuntimeActionError) as raised:
            self.preview(payload)
        self.assertIn(raised.exception.code, {
            "MATERIAL_SUPPLIER_RELATION_REQUIRED", "SUPPLIER_MATERIAL_PRICE_MASTER_MISMATCH",
        })

    def test_historical_price_is_blocked(self):
        payload = self.payload()
        payload["supplierMaterialPriceId"] = self.historical_price.pk
        payload["supplierMaterialPriceNo"] = self.historical_price.price_no
        with self.assertRaises(ScmRuntimeActionError) as raised:
            self.preview(payload)
        self.assertEqual(raised.exception.code, "HISTORICAL_SUPPLIER_MATERIAL_PRICE_BLOCKED")

    def test_page_prepare_get_and_preview_do_not_create_order(self):
        before = (PurchaseOrder.objects.count(), PurchaseOrderItem.objects.count())
        prepare = self.client.get("/api/procurement/purchase-order-gate-creation/")
        preview_payload = {**self.payload(), "previewOnly": True}
        preview = self.client.post(
            "/api/procurement/purchase-order-gate-creation/", preview_payload, format="json",
        )
        self.assertEqual(prepare.status_code, 200)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data["data"]["gateStatus"], "PASS")
        self.assertEqual(before, (PurchaseOrder.objects.count(), PurchaseOrderItem.objects.count()))

    def test_api_creation_reports_two_authorized_business_rows(self):
        payload = self.payload("PO-MANUAL-B22-API")
        preview = self.client.post(
            "/api/procurement/purchase-order-gate-creation/",
            {**payload, "previewOnly": True}, format="json",
        )
        payload.update({"admissionToken": preview.data["data"]["admissionToken"],
                        "humanConfirmed": True})
        response = self.client.post(
            "/api/procurement/purchase-order-gate-creation/", payload, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["created"])
        self.assertEqual(response.data["meta"]["businessWriteCount"], 2)
        self.assertEqual((PurchaseOrder.objects.count(), PurchaseOrderItem.objects.count()), (1, 1))

    def test_gate_token_rejects_changed_context_and_missing_confirmation(self):
        payload = self.payload("PO-MANUAL-B22-TOKEN")
        token = self.preview(payload)["admissionToken"]
        with self.assertRaises(ScmRuntimeActionError) as missing:
            PurchaseOrderCreationService.create_from_manual_request(
                {**payload, "admissionToken": token}, self.user.pk,
            )
        self.assertEqual(missing.exception.code, "PURCHASE_ORDER_HUMAN_CONFIRMATION_REQUIRED")
        with self.assertRaises(ScmRuntimeActionError) as changed:
            PurchaseOrderCreationService.create_from_manual_request(
                {**payload, "quantity": "4", "admissionToken": token, "humanConfirmed": True},
                self.user.pk,
            )
        self.assertEqual(changed.exception.code, "PURCHASE_ORDER_CONTEXT_CHANGED_AFTER_GATE")
        self.assertEqual(PurchaseOrder.objects.count(), 0)
