from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice
from pfm.models import Employee
from system.models import (
    Company, OrganizationOperatingAuditRecord, Permission, Role, RolePermission,
    UserRoleScopeAssignment,
)

from .models import (
    PriceApprovalPreparation,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
    Supplier,
)
from .scm_page_facts import _normalized_object


class AgreedPriceClosureR5Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="r5-buyer", password="x", company_id=1)
        company, _ = Company.objects.get_or_create(
            pk=1, defaults={"name": "R5测试公司", "code": "R5-COMPANY"}
        )
        role = Role.objects.create(name="R5采购订单创建角色", code="r5-po-creator")
        permission, _ = Permission.objects.get_or_create(
            code="procurement.purchase_order.create",
            defaults={"name": "创建采购订单", "module": "SCM"},
        )
        RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.user,
            role=role,
            organization=company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.buyer = Employee.objects.create(employee_no="EMP-R5-BUYER", full_name="R5采购员", position="采购员", status="active")
        self.suppliers = [
            Supplier.objects.create(code=f"SUP-R5-{index}", name=f"R5供应商{index}", company_id=1, is_active=True)
            for index in (1, 2)
        ]
        self.materials = [
            Material.objects.create(code=f"MAT-R5-{index}", name=f"R5物料{index}", specification=f"R5-{index}",
                                    unit="件", purchase_unit="件", company_id=1,
                                    is_active=True, is_purchased=True)
            for index in (1, 2, 3)
        ]
        self.prices = []
        for supplier_index, (supplier, materials) in enumerate((
                (self.suppliers[0], self.materials[:2]), (self.suppliers[1], self.materials[2:])), start=1):
            preparation = PriceApprovalPreparation.objects.create(
                approval_prepare_no=f"PAP-R5-{supplier_index}", source_projection_id=f"LQCP-R5-{supplier_index}",
                source_projection_snapshot={}, source_legacy_comparison_no=f"QC-R5-{supplier_index}",
                source_trace_alias_id=f"BTA-R5-{supplier_index}", fact_origin="legacy_verified_fact",
                source_quotation_evidence=[], supplier_candidates=[],
                material_lines=[{"materialId": row.pk, "materialCode": row.code, "materialName": row.name}
                                for row in materials],
                selected_supplier={"supplierId": supplier.pk, "supplierCode": supplier.code,
                                   "supplierName": supplier.name},
                status="completed", review_result="pass", approval_opinion="通过", reviewer="R5",
            )
            for material in materials:
                now = timezone.now()
                result = PriceApprovalResult.objects.create(
                    result_no=f"PAR-R5-{material.pk}", preparation=preparation,
                    preparation_identity=f"PAP-R5-{material.pk}", original_source_type="SupplierQuotation",
                    original_source_reference=f"SQ-R5-{material.pk}", supplier=supplier, material=material,
                    approved_price=Decimal("10.00") + material.pk, currency="CNY", tax_rate="13",
                    tax_rate_source="enterprise_config", approval_conclusion="pass", approved_by="R5",
                    approved_at=now, confirmed_by="R5", confirmed_at=now,
                )
                self.prices.append(SupplierMaterialPrice.objects.create(
                    price_no=f"SMP-R5-{material.pk}", supplier=supplier, material=material,
                    approved_price=result.approved_price, currency="CNY", tax_rate="13",
                    tax_rate_source="enterprise_config", effective_date=date.today() - timedelta(days=1),
                    expiry_date=date.today() + timedelta(days=90), price_approval_result=result,
                    original_source_type="SupplierQuotation", original_source_reference=f"SQ-R5-{material.pk}",
                    approved_by="R5", approved_at=now, confirmed_by="R5", confirmed_at=now,
                ))
        self.request_value = PurchaseRequest.objects.create(
            request_no="PR-R5-AGREED-001", request_date=date.today(), requester="R5申请人",
            department="申请部", purchase_department="采购部", usage_department="使用部",
            purchase_mode="AGREED_PRICE", status="approved", approval_status="completed",
            approval_current_node="审批完成", approval_result="通过",
            required_date=date.today() + timedelta(days=10), quantity=Decimal("6"), amount=0,
        )
        for index, material in enumerate(self.materials, start=1):
            PurchaseRequestItem.objects.create(
                purchase_request=self.request_value, material=material, material_code=material.code,
                material_name=material.name, specification=material.specification, unit=material.unit,
                purchase_attribute="可采购", quantity=index,
                required_date=date.today() + timedelta(days=7 + index), line_no=index,
            )

    def payload(self):
        request_items = list(self.request_value.request_items.order_by("line_no"))
        return {
            "creationMode": "AGREED_PRICE_CONFIRMATION", "purchaseMode": "AGREED_PRICE",
            "purchaseRequestId": self.request_value.pk, "idempotencyKey": "PO-AGREED-R5-TEST",
            "orderDate": date.today().isoformat(),
            "buyerEmployeeId": self.buyer.pk,
            "items": [{"purchaseRequestItemId": item.pk, "supplierMaterialPriceId": price.pk,
                       "supplierMaterialPriceNo": price.price_no}
                      for item, price in zip(request_items, self.prices)],
        }

    def test_gate_is_read_only_and_requires_human_confirmation(self):
        before = (PurchaseOrder.objects.count(), PurchaseOrderItem.objects.count())
        preview = self.client.post("/api/procurement/purchase-order-gate-creation/",
                                   {**self.payload(), "previewOnly": True}, format="json")
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data["data"]["gateStatus"], "PASS")
        self.assertEqual(before, (PurchaseOrder.objects.count(), PurchaseOrderItem.objects.count()))
        blocked = self.client.post("/api/procurement/purchase-order-gate-creation/", {
            **self.payload(), "admissionToken": preview.data["data"]["admissionToken"]}, format="json")
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(blocked.data["error"]["code"], "PURCHASE_ORDER_HUMAN_CONFIRMATION_REQUIRED")

    def test_three_inherited_items_split_into_two_orders_with_trace_and_idempotency(self):
        payload = self.payload()
        price_before = list(SupplierMaterialPrice.objects.values_list("pk", "approved_price", "updated_at"))
        preview = self.client.post("/api/procurement/purchase-order-gate-creation/",
                                   {**payload, "previewOnly": True}, format="json")
        payload.update(admissionToken=preview.data["data"]["admissionToken"], humanConfirmed=True)
        created = self.client.post("/api/procurement/purchase-order-gate-creation/", payload, format="json")
        self.assertEqual(created.status_code, 200, created.data)
        self.assertEqual(created.data["data"]["createdCount"], 2)
        self.assertEqual(created.data["data"]["purchaseOrderCount"], 2)
        self.assertEqual(PurchaseOrder.objects.filter(source_purchase_request=self.request_value,
                                                      purchase_mode="AGREED_PRICE").count(), 2)
        self.assertEqual(PurchaseOrderItem.objects.filter(
            po__source_purchase_request=self.request_value).count(), 3)
        self.assertEqual(
            OrganizationOperatingAuditRecord.objects.filter(
                action_code="procurement.purchase_order.create",
                target_type="PurchaseOrder",
            ).count(),
            2,
        )
        self.assertEqual(set(PurchaseOrder.objects.filter(source_purchase_request=self.request_value)
                             .values_list("supplier_id", flat=True)), set(row.pk for row in self.suppliers))
        for item, price in zip(self.request_value.request_items.order_by("line_no"), self.prices):
            item.refresh_from_db()
            order_item = PurchaseOrderItem.objects.get(source_purchase_request_item=item)
            self.assertEqual(item.supplier_material_price_id, price.pk)
            self.assertEqual(item.price_record_code, price.price_no)
            self.assertEqual(order_item.supplier_material_price_id, price.pk)
            self.assertEqual(order_item.quantity, item.quantity)
            self.assertEqual(order_item.expected_date, item.required_date)
            self.assertEqual(order_item.unit_price_snapshot, price.approved_price)
            self.assertEqual(order_item.tax_rate_snapshot, Decimal(str(price.tax_rate)))
            self.assertEqual(order_item.currency_snapshot, price.currency)
        lifecycle = _normalized_object(self.request_value)
        self.assertEqual(lifecycle["businessLifecycleStatus"], "purchase_order_created")
        self.assertEqual(len(lifecycle["purchaseOrders"]), 2)
        self.assertEqual(lifecycle["targetObject"]["objectType"], "PurchaseOrder")
        first_order = PurchaseOrder.objects.filter(
            source_purchase_request=self.request_value,
        ).order_by("id").first()
        order_fact = _normalized_object(first_order)
        self.assertEqual(order_fact["sourceObject"]["objectType"], "PurchaseRequest")
        self.assertEqual(order_fact["sourceObject"]["objectNo"], self.request_value.request_no)
        repeated = self.client.post("/api/procurement/purchase-order-gate-creation/", payload, format="json")
        self.assertEqual(repeated.status_code, 200)
        self.assertFalse(repeated.data["data"]["created"])
        self.assertEqual(PurchaseOrder.objects.filter(source_purchase_request=self.request_value).count(), 2)
        self.assertEqual(price_before, list(SupplierMaterialPrice.objects.values_list("pk", "approved_price", "updated_at")))

    def test_gate_token_cannot_be_reused_after_price_selection_change(self):
        payload = self.payload()
        preview = self.client.post("/api/procurement/purchase-order-gate-creation/",
                                   {**payload, "previewOnly": True}, format="json")
        payload["items"] = list(payload["items"])
        payload["items"][0] = {**payload["items"][0], "supplierMaterialPriceNo": "CHANGED"}
        response = self.client.post("/api/procurement/purchase-order-gate-creation/", {
            **payload, "admissionToken": preview.data["data"]["admissionToken"], "humanConfirmed": True},
            format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PurchaseOrder.objects.count(), 0)
