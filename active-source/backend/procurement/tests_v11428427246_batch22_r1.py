from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice
from pfm.models import Employee
from system.models import Permission, Role, RolePermission
from workflow_runtime.models import UserOrganizationRoleAuthority

from .models import PriceApprovalPreparation, PurchaseOrder, PurchaseOrderItem, PurchaseRequest, PurchaseRequestItem, Supplier
from .procurement_mode_router import ProcurementModeRouter


class DirectPurchaseWorkbenchR1Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.authorized = User.objects.create_user(username="r1-buyer", password="x", company_id=1)
        self.unauthorized = User.objects.create_user(username="r1-viewer", password="x", company_id=1)
        permission = Permission.objects.create(code="procurement.direct_purchase_order.create", name="直接采购订单创建", module="SCM")
        role = Role.objects.create(code="r1_direct_buyer", name="R1直接采购员")
        RolePermission.objects.create(role=role, permission=permission)
        UserOrganizationRoleAuthority.objects.create(user=self.authorized, role_code=role.code,
            legal_entity_id="1", active=True, business_hash="r1")
        self.supplier = Supplier.objects.create(code="SUP-R1", name="R1供应商", company_id=1, is_active=True)
        self.buyer = Employee.objects.create(employee_no="EMP-R1-BUYER", full_name="R1采购员", position="采购员", status="active")
        self.preparation = PriceApprovalPreparation.objects.create(
            approval_prepare_no="PAP-R1", source_projection_id="LQCP-R1",
            source_projection_snapshot={}, source_legacy_comparison_no="QC-R1", source_trace_alias_id="BTA-R1",
            fact_origin="legacy_verified_fact", source_quotation_evidence=[], supplier_candidates=[],
            material_lines=[], selected_supplier={"supplierId": self.supplier.pk}, status="completed",
            review_result="pass", approval_opinion="通过", reviewer="R1")
        self.materials, self.prices = [], []
        for index in range(1, 4):
            material = Material.objects.create(code=f"MAT-R1-{index}", name=f"R1物料{index}", specification=f"R1-{index}",
                unit="件", company_id=1, is_active=True, is_purchased=True)
            now = timezone.now() + timedelta(seconds=index)
            result = PriceApprovalResult.objects.create(result_no=f"PAR-R1-{index}", preparation=self.preparation,
                preparation_identity=f"PAP-R1-{index}", original_source_type="SupplierQuotation",
                original_source_reference=f"SQ-R1-{index}", supplier=self.supplier, material=material,
                approved_price=str(10 * index), currency="CNY", tax_rate="13", tax_rate_source="enterprise_config",
                approval_conclusion="pass", approved_by="R1", approved_at=now, confirmed_by="R1", confirmed_at=now)
            price = SupplierMaterialPrice.objects.create(price_no=f"SMP-R1-{index}", supplier=self.supplier,
                material=material, approved_price=str(10 * index), currency="CNY", tax_rate="13",
                tax_rate_source="enterprise_config", effective_date=date.today()-timedelta(days=1),
                expiry_date=date.today()+timedelta(days=30), price_approval_result=result,
                original_source_type="SupplierQuotation", original_source_reference=f"SQ-R1-{index}",
                approved_by="R1", approved_at=now, confirmed_by="R1", confirmed_at=now)
            self.materials.append(material); self.prices.append(price)
        self.manual_material = Material.objects.create(
            code="MAT-R1-MANUAL", name="R1人工维护物料", specification="R1-MANUAL",
            unit="件", company_id=1, is_active=True, is_purchased=True,
        )
        self.preparation.material_lines = [{"materialId": value.pk, "materialCode": value.code,
                                            "materialName": value.name} for value in [*self.materials, self.manual_material]]
        self.preparation.selected_supplier = {"supplierId": self.supplier.pk, "supplierCode": self.supplier.code,
                                              "supplierName": self.supplier.name}
        self.preparation.save(update_fields=["material_lines", "selected_supplier"])

    def client_for(self, user):
        client=APIClient(); client.force_authenticate(user); return client

    def payload(self):
        return {"creationMode":"DIRECT_SELECTION","purchaseMode":"DIRECT","idempotencyKey":"PO-DIRECT-R1-TEST",
            "supplierId":self.supplier.pk,"orderDate":date.today().isoformat(),"buyerEmployeeId":self.buyer.pk,
            "items":[{"materialId":material.pk,"quantity":str(index+1),
                      "supplierMaterialPriceId":price.pk,"supplierMaterialPriceNo":price.price_no,
                      "expectedDate":(date.today()+timedelta(days=index+2)).isoformat()}
                     for index,(material,price) in enumerate(zip(self.materials,self.prices))]}

    def test_standard_and_agreed_routes_are_available_without_direct_permission(self):
        self.assertTrue(ProcurementModeRouter.resolve("STANDARD", self.unauthorized)["allowed"])
        agreed=ProcurementModeRouter.resolve("AGREED_PRICE", self.unauthorized)
        self.assertTrue(agreed["allowed"]); self.assertEqual(agreed["status"],"PURCHASE_REQUEST_CREATION_READY")
        self.assertEqual(agreed["targetPath"],"/scm/purchase-request/agreed-price")

    def test_unauthorized_user_cannot_enter_or_create_direct(self):
        self.assertFalse(ProcurementModeRouter.resolve("DIRECT", self.unauthorized, 1)["allowed"])
        response=self.client_for(self.unauthorized).post("/api/procurement/purchase-order-gate-creation/",
            {**self.payload(),"previewOnly":True},format="json")
        self.assertEqual(response.status_code,403); self.assertEqual(PurchaseOrder.objects.count(),0)

    def test_authorized_user_can_enter_direct(self):
        self.assertTrue(ProcurementModeRouter.resolve("DIRECT", self.authorized, 1)["allowed"])
        response=self.client_for(self.authorized).get("/api/procurement/purchase-order-gate-creation/")
        self.assertTrue(response.data["data"]["authorization"]["allowed"])

    def test_manual_price_maintenance_requires_direct_permission_and_persists_audited_source(self):
        data = {"supplierId": self.supplier.pk, "materialId": self.manual_material.pk,
                "unitPrice": "88.5000", "taxRate": "13", "currency": "CNY",
                "effectiveDate": date.today().isoformat(),
                "expiryDate": (date.today() + timedelta(days=90)).isoformat(),
                "maintenanceReason": "R1受控人工价格维护测试"}
        denied = self.client_for(self.unauthorized).post(
            "/api/masterdata/prices/supplier-material-prices/runtime/manual-maintenance/", data, format="json")
        self.assertEqual(denied.status_code, 403)
        created = self.client_for(self.authorized).post(
            "/api/masterdata/prices/supplier-material-prices/runtime/manual-maintenance/", data, format="json")
        self.assertEqual(created.status_code, 200, created.data)
        price = SupplierMaterialPrice.objects.get(supplier=self.supplier, material=self.manual_material)
        self.assertEqual(price.price_source_type, "MANUAL_MAINTENANCE")
        self.assertIsNone(price.price_approval_result_id)
        self.assertEqual(price.modification_audit[0]["action"], "CREATE")

    def test_gate_then_one_order_three_items_with_exact_snapshots_and_idempotency(self):
        client=self.client_for(self.authorized); payload=self.payload()
        before=(PurchaseOrder.objects.count(),PurchaseOrderItem.objects.count(),PurchaseRequest.objects.count(),PurchaseRequestItem.objects.count())
        preview=client.post("/api/procurement/purchase-order-gate-creation/",{**payload,"previewOnly":True},format="json")
        self.assertEqual(preview.status_code,200); self.assertEqual(preview.data["data"]["gateStatus"],"PASS")
        self.assertEqual(before,(PurchaseOrder.objects.count(),PurchaseOrderItem.objects.count(),PurchaseRequest.objects.count(),PurchaseRequestItem.objects.count()))
        payload.update(admissionToken=preview.data["data"]["admissionToken"],humanConfirmed=True)
        created=client.post("/api/procurement/purchase-order-gate-creation/",payload,format="json")
        self.assertEqual(created.status_code,200); self.assertEqual(created.data["data"]["itemCount"],3)
        self.assertEqual((PurchaseOrder.objects.count(),PurchaseOrderItem.objects.count(),PurchaseRequest.objects.count(),PurchaseRequestItem.objects.count()),
                         (before[0]+1,before[1]+3,before[2]+1,before[3]+3))
        order=PurchaseOrder.objects.get(pk=created.data["data"]["objectId"])
        self.assertEqual(order.purchase_mode,"DIRECT"); self.assertEqual(order.source_type,"DIRECT_PURCHASE_ORDER_CREATION")
        self.assertIsNotNone(order.source_purchase_request_id)
        self.assertEqual(order.source_purchase_request.purchase_mode,"DIRECT")
        self.assertEqual(order.source_reference,order.source_purchase_request.request_no)
        self.assertEqual(str(order.total_amount),"140.00")
        for item,price in zip(order.items.order_by("id"),self.prices):
            self.assertEqual(item.supplier_material_price_id,price.pk)
            self.assertEqual(item.price_approval_result_id,price.price_approval_result_id)
            self.assertEqual(item.unit_price_snapshot,Decimal(str(price.approved_price)))
            self.assertEqual(item.source_purchase_request_item.supplier_material_price_id,price.pk)
            self.assertEqual(item.source_purchase_request_item.price_record_code,price.price_no)
            self.assertEqual(item.source_purchase_request_item.required_date,item.expected_date)
        repeated=client.post("/api/procurement/purchase-order-gate-creation/",payload,format="json")
        self.assertFalse(repeated.data["data"]["created"]); self.assertEqual(PurchaseOrder.objects.count(),before[0]+1)
        self.assertEqual(PurchaseRequest.objects.count(),before[2]+1)

    def test_cross_material_price_is_blocked_with_row_reason(self):
        payload=self.payload(); payload["items"][1]["supplierMaterialPriceId"]=self.prices[0].pk
        payload["items"][1]["supplierMaterialPriceNo"]=self.prices[0].price_no
        response=self.client_for(self.authorized).post("/api/procurement/purchase-order-gate-creation/",
            {**payload,"previewOnly":True},format="json")
        self.assertEqual(response.status_code,400); self.assertIn("第2行",response.data["error"]["message"])

    def test_old_manual_standard_api_is_retired(self):
        response=self.client_for(self.authorized).post("/api/procurement/purchase-order-gate-creation/",
            {"creationMode":"MANUAL_SELECTION","purchaseMode":"STANDARD","previewOnly":True},format="json")
        self.assertEqual(response.status_code,400); self.assertEqual(response.data["error"]["code"],"MANUAL_STANDARD_CREATION_RETIRED")
