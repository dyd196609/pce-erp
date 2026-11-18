from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from masterdata.material_supplier_relation_runtime import MaterialSupplierRelationRuntime
from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice
from pfm.models import Employee
from system.models import Permission, Role, RolePermission
from workflow_runtime.models import UserOrganizationRoleAuthority

from .models import PriceApprovalPreparation, PurchaseOrder, Supplier


class PurchaseOrderGateR51RegressionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.authorized = User.objects.create_user(username="r51-buyer", password="x", company_id=1)
        self.unauthorized = User.objects.create_user(username="r51-viewer", password="x", company_id=1)
        permission, _ = Permission.objects.get_or_create(
            code="procurement.direct_purchase_order.create",
            defaults={"name": "直接采购订单创建", "module": "SCM"},
        )
        manual_permission, _ = Permission.objects.get_or_create(
            code="masterdata.supplier_material_price.manual_maintain",
            defaults={"name": "人工维护供应商物料价格", "module": "MASTERDATA"},
        )
        role = Role.objects.create(code="r51_direct_buyer", name="R5.1直接采购员")
        RolePermission.objects.create(role=role, permission=permission)
        RolePermission.objects.create(role=role, permission=manual_permission)
        UserOrganizationRoleAuthority.objects.create(
            user=self.authorized, role_code=role.code, legal_entity_id="1", active=True,
            business_hash="r51",
        )
        self.supplier = Supplier.objects.create(
            code="SUP-R51", name="R5.1供应商", company_id=1, is_active=True,
        )
        self.buyer = Employee.objects.create(
            employee_no="EMP-R51", full_name="R5.1采购员", position="采购员", status="active",
        )
        self.material = Material.objects.create(
            code="MT-R51-APPROVED", name="已审批物料", specification="R51", unit="件",
            company_id=1, is_active=True, is_purchased=True,
        )
        self.manual_material = Material.objects.create(
            code="MT-R51-MANUAL", name="人工维护物料", specification="R51-M", unit="件",
            company_id=1, is_active=True, is_purchased=True,
        )
        self.no_price_material = Material.objects.create(
            code="MT-R51-NO-PRICE", name="无价格物料", specification="R51-N", unit="件",
            company_id=1, is_active=True, is_purchased=True,
        )
        preparation = PriceApprovalPreparation.objects.create(
            approval_prepare_no="PAP-R51", source_projection_id="LQCP-R51",
            source_projection_snapshot={}, source_legacy_comparison_no="QC-R51",
            source_trace_alias_id="BTA-R51", fact_origin="legacy_verified_fact",
            source_quotation_evidence=[], supplier_candidates=[], material_lines=[],
            selected_supplier={}, status="draft", review_result="pending",
            approval_opinion="", reviewer="R5.1",
        )
        now = timezone.now()
        result = PriceApprovalResult.objects.create(
            result_no="PAR-R51", preparation=preparation, preparation_identity="PAP-R51",
            original_source_type="SupplierQuotation", original_source_reference="SQ-R51",
            supplier=self.supplier, material=self.material, approved_price="6.8", currency="CNY",
            tax_rate="6", tax_rate_source="enterprise_config", approval_conclusion="pass",
            approved_by="R5.1", approved_at=now, confirmed_by="R5.1", confirmed_at=now,
        )
        self.price = SupplierMaterialPrice.objects.create(
            price_no="SMP-R51", supplier=self.supplier, material=self.material,
            approved_price="6.8", currency="CNY", tax_rate="6",
            tax_rate_source="enterprise_config", effective_date=date.today() - timedelta(days=1),
            expiry_date=date.today() + timedelta(days=30), price_approval_result=result,
            original_source_type="SupplierQuotation", original_source_reference="SQ-R51",
            approved_by="R5.1", approved_at=now, confirmed_by="R5.1", confirmed_at=now,
        )

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def direct_payload(self, material, price_id="", price_no=""):
        return {
            "creationMode": "DIRECT_SELECTION", "purchaseMode": "DIRECT",
            "idempotencyKey": "PO-DIRECT-R51-NO-WRITE", "supplierId": self.supplier.pk,
            "orderDate": date.today().isoformat(), "buyerEmployeeId": self.buyer.pk,
            "previewOnly": True,
            "items": [{
                "lineNo": 1, "materialId": material.pk, "quantity": "2",
                "supplierMaterialPriceId": price_id, "supplierMaterialPriceNo": price_no,
                "expectedDate": (date.today() + timedelta(days=7)).isoformat(),
            }],
        }

    def test_approved_price_result_is_formal_relation_and_gate_passes_without_order_write(self):
        relation = next(
            row for row in MaterialSupplierRelationRuntime.list_runtime_models()
            if row.supplierId == self.supplier.pk and row.materialId == self.material.pk
        )
        self.assertIn("PriceApproval", relation.sourceModules)
        before = PurchaseOrder.objects.count()
        response = self.client_for(self.authorized).post(
            "/api/procurement/purchase-order-gate-creation/",
            self.direct_payload(self.material, self.price.pk, self.price.price_no), format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["gateStatus"], "PASS")
        self.assertEqual(PurchaseOrder.objects.count(), before)

    def test_missing_price_returns_specific_row_reason_before_relation_check(self):
        response = self.client_for(self.authorized).post(
            "/api/procurement/purchase-order-gate-creation/",
            self.direct_payload(self.no_price_material), format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "SUPPLIER_MATERIAL_PRICE_REQUIRED")
        self.assertIn("第1行", response.data["error"]["message"])

    def test_manual_maintenance_establishes_audited_relation_in_same_transaction(self):
        payload = {
            "supplierId": self.supplier.pk, "materialId": self.manual_material.pk,
            "unitPrice": "45.5", "taxRate": "13", "currency": "CNY",
            "effectiveDate": date.today().isoformat(),
            "expiryDate": (date.today() + timedelta(days=60)).isoformat(),
            "maintenanceReason": "R5.1 缺关系人工价格闭环",
        }
        response = self.client_for(self.authorized).post(
            "/api/masterdata/prices/supplier-material-prices/runtime/manual-maintenance/",
            payload, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        result = response.data["manualMaintenanceResult"]
        self.assertEqual(result["relationAction"], "ESTABLISHED_FORMAL_RELATION")
        price = SupplierMaterialPrice.objects.get(pk=result["priceId"])
        self.assertTrue(price.modification_audit[0]["relationConfirmed"])
        self.assertTrue(any(
            row.supplierId == self.supplier.pk and row.materialId == self.manual_material.pk
            for row in MaterialSupplierRelationRuntime.list_runtime_models()
        ))

    def test_unauthorized_manual_maintenance_is_rejected_by_backend(self):
        response = self.client_for(self.unauthorized).post(
            "/api/masterdata/prices/supplier-material-prices/runtime/manual-maintenance/",
            {"supplierId": self.supplier.pk, "materialId": self.manual_material.pk}, format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["errorCode"], "SUPPLIER_MATERIAL_PRICE_MANUAL_NOT_AUTHORIZED")
