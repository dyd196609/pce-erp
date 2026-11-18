from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from masterdata.models import Material
from pfm.models import Employee
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionWorkflowResponsibility, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition
from reconciliation.models import PayableCheckAuthorityRecord

from .models import (
    InventoryBalance, InventoryTransaction, PurchaseOrder, PurchaseOrderItem,
    Supplier, Warehouse,
)


class PurchaseFulfillmentV1Tests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="T01", name="测试组织")
        self.department = Department.objects.create(
            company=self.company, code="SCM", name="供应链部"
        )
        self.process = ProcessDefinition.objects.create(
            definition_code="PROCUREMENT_PURCHASE_REQUEST_TO_ORDER",
            definition_name="采购申请至采购订单执行", business_domain="SCM",
            document_type="PURCHASE_REQUEST", version=1, active=True,
            definition_hash="test-definition",
        )
        self.manager = self._actor(
            "manager", "采购经理", "CGB-MGR", "purchase_manager",
            (("procurement.purchase_order.submit", 5, "SUBMIT", "OWNER"),
             ("procurement.purchase_order.approve", 6, "APPROVE", "APPROVER"),
             ("procurement.purchase_order.review", 7, "REVIEW", "REVIEWER"),
             ("procurement.purchase_order.release", 8, "RELEASE", "APPROVER"),
             ("procurement.purchase_order.complete", 12, "COMPLETE", "OWNER")),
        )
        self.warehouse_user = self._actor(
            "warehouse", "仓管员", "CCB-CLERK", "warehouse",
            (("procurement.receipt.receive", 9, "RECEIVE", "EXECUTOR"),
             ("warehouse.purchase.putaway", 11, "PUTAWAY", "EXECUTOR")),
        )
        self.quality_user = self._actor(
            "quality", "质检员", "PBB-QC", "quality_inspector",
            (("quality.purchase.inspect", 10, "INSPECT", "EXECUTOR"),),
        )
        self.material = Material.objects.create(
            code="MT-T01", name="测试原材料", unit="件", company_id=self.company.pk,
            is_purchased=True,
        )
        self.supplier = Supplier.objects.create(
            code="SUP-T01", name="测试供应商", company_id=self.company.pk
        )
        self.warehouse = Warehouse.objects.create(
            code="WH-RM-001", name="原材料仓", location_code="RM-A-01",
            company_id=self.company.pk,
        )
        self.order = PurchaseOrder.objects.create(
            po_no="PO-T01", supplier=self.supplier, order_date=date.today(),
            expected_date=date.today(), status="draft", total_amount=Decimal("100"),
            buyer_employee=self.manager.employee_profile, buyer="采购经理",
            purchase_mode="AGREED_PRICE", price_trace_status="CURRENT_LINKED",
            supplier_code_snapshot=self.supplier.code,
            supplier_name_snapshot=self.supplier.name,
            company_id=self.company.pk, created_by=self.manager.pk,
            department=self.department, purchase_department=self.department,
        )
        PurchaseOrderItem.objects.create(
            po=self.order, material=self.material, material_code_snapshot=self.material.code,
            material_name_snapshot=self.material.name, unit_snapshot="件",
            quantity=Decimal("2"), unit_price=Decimal("50"),
            unit_price_snapshot=Decimal("50"), amount=Decimal("100"),
        )
        self.client = APIClient()

    def _actor(self, username, title, position_code, role_code, actions):
        role, _ = Role.objects.get_or_create(
            code=role_code, defaults={"name": f"{title}角色"}
        )
        position = Position.objects.create(
            code=position_code, name=title, company=self.company,
            department=self.department, is_active=True,
        )
        responsibility = Responsibility.objects.create(
            code=f"RESP-{position_code}", name=f"{title}职责", is_active=True,
            status="ACTIVE",
        )
        user = User.objects.create_user(
            username=username, password="test-only", real_name=title,
            company_id=self.company.pk,
        )
        Employee.objects.create(
            user=user, employee_no=f"EMP-{position_code}", full_name=title,
            status="active", department_ref=self.department, position_ref=position,
        )
        UserRoleScopeAssignment.objects.create(
            user=user, role=role, organization=self.company,
            scope_code="ORGANIZATION", business_hash=f"hash-{username}",
        )
        for action_code, sequence, node_code, ownership in actions:
            permission, _ = Permission.objects.get_or_create(
                code=action_code, defaults={"name": action_code, "module": "SCM"}
            )
            RolePermission.objects.get_or_create(role=role, permission=permission)
            node = WorkflowNodeDefinition.objects.create(
                process_definition=self.process, node_code=node_code,
                node_name=node_code, sequence=sequence,
                business_action_code=action_code, active=True,
            )
            PositionWorkflowResponsibility.objects.create(
                position=position, responsibility=responsibility, workflow_node=node,
                workflow_code=self.process.definition_code, node_code=node_code,
                ownership_type=ownership, active=True,
            )
        return user

    def _post(self, user, action, object_id, data=None, expected=200):
        self.client.force_authenticate(user=user)
        response = self.client.post(
            f"/api/procurement/scm-runtime-actions/{action}/{object_id}/",
            data or {}, format="json",
        )
        self.assertEqual(response.status_code, expected, response.data)
        return response.data

    def _read_only_user(self):
        role = Role.objects.create(code="completed_module_reader", name="完成模块只读验收")
        user = User.objects.create_user(
            username="rehearsal_reader", password="read-only-test",
            real_name="演练只读身份", company_id=self.company.pk,
        )
        UserRoleScopeAssignment.objects.create(
            user=user, role=role, organization=self.company,
            scope_code="ORGANIZATION", business_hash="completed-module-reader",
        )
        for code in (
            "warehouse.inventory.read",
            "warehouse.inventory_transaction.read",
            "procurement.receipt.read",
            "quality.purchase_inspection.read",
            "navigation.supplier_procurement.read",
            "finance.payable_check.read",
        ):
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "module": "SCM"},
            )
            RolePermission.objects.create(role=role, permission=permission)
        return user

    def test_complete_formal_chain_changes_inventory_and_audits(self):
        for action in ("submit", "approve", "review", "release"):
            self._post(self.manager, f"{action}-purchase-order", self.order.pk)
        denied = self._post(
            self.manager, "confirm-receipt", self.order.pk, {"quantity": "2"}, 403
        )
        self.assertEqual(denied["error"]["code"], "PERMISSION_DENIED")

        receipt_id = self._post(
            self.warehouse_user, "confirm-receipt", self.order.pk, {"quantity": "2"}
        )["data"]["objectId"]
        over = self._post(
            self.warehouse_user, "confirm-receipt", self.order.pk, {"quantity": "0.1"}, 400
        )
        self.assertEqual(over["error"]["code"], "RECEIPT_QUANTITY_EXCEEDED")

        inspection_id = self._post(
            self.quality_user, "create-inspection", receipt_id
        )["data"]["objectId"]
        self._post(self.quality_user, "transition-inspection", inspection_id,
                   {"targetStatus": "inspecting"})
        self._post(self.quality_user, "transition-inspection", inspection_id,
                   {"targetStatus": "qualified", "qualifiedQuantity": "2"})
        inbound_id = self._post(
            self.warehouse_user, "confirm-inbound", inspection_id,
            {"quantity": "2", "warehouseCode": self.warehouse.code},
        )["data"]["objectId"]
        self._post(self.manager, "complete-purchase-order", self.order.pk)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "closed")
        balance = InventoryBalance.objects.get(
            warehouse=self.warehouse, material=self.material
        )
        self.assertEqual(balance.quantity, Decimal("2"))
        transaction = InventoryTransaction.objects.get(source_inbound_id=inbound_id)
        self.assertEqual(transaction.before_quantity, Decimal("0"))
        self.assertEqual(transaction.after_quantity, Decimal("2"))
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 10)

        self.client.force_authenticate(user=self.manager)
        facts = self.client.get(
            f"/api/procurement/purchase-order-fulfillment/{self.order.pk}/"
        )
        self.assertEqual(facts.status_code, 200, facts.data)
        self.assertEqual(facts.data["data"]["order"]["inboundQuantity"], "2.0000")
        self.assertEqual(facts.data["data"]["inventoryTransactions"][0]["beforeQuantity"], "0.0000")
        self.assertEqual(facts.data["data"]["inventoryTransactions"][0]["afterQuantity"], "2.0000")

        read_only = self._read_only_user()
        self.client.force_authenticate(user=read_only)
        inventory = self.client.get("/api/procurement/formal-inventory-facts/")
        self.assertEqual(inventory.status_code, 200, inventory.data)
        self.assertEqual(inventory.data["balances"][0]["materialCode"], self.material.code)
        self.assertEqual(inventory.data["transactions"][0]["transactionNo"], transaction.transaction_no)
        receipts = self.client.get("/api/procurement/formal-purchase-receipt-facts/")
        self.assertEqual(receipts.status_code, 200, receipts.data)
        self.assertEqual(receipts.data["receipts"][0]["sourceOrderNo"], self.order.po_no)
        quality = self.client.get("/api/procurement/formal-quality-facts/")
        self.assertEqual(quality.status_code, 200, quality.data)
        self.assertEqual(quality.data["inspections"][0]["purchaseOrderNo"], self.order.po_no)

        payable = PayableCheckAuthorityRecord.objects.create(
            authority_object_id="PAYABLE-AUTH-T01", payable_check_no="PAY-T01",
            tenant_id="test", company_id=self.company.pk,
            supplier_id=str(self.supplier.pk), legal_entity_id=str(self.company.pk),
            ledger_book_id="LEDGER-T01", currency="CNY",
            checked_amount=Decimal("100"), checked_quantity=Decimal("2"),
            business_status="checked", authority_version=1,
            business_hash="payable-check-test-hash", occurred_at=timezone.now(),
        )
        payable_facts = self.client.get("/api/procurement/formal-payable-check-facts/")
        self.assertEqual(payable_facts.status_code, 200, payable_facts.data)
        self.assertEqual(payable_facts.data["payableChecks"][0]["payableCheckNo"], payable.payable_check_no)

        putaway = self._post(
            read_only, "confirm-inbound", inspection_id,
            {"quantity": "2", "warehouseCode": self.warehouse.code}, 403,
        )
        self.assertEqual(putaway["error"]["code"], "PERMISSION_DENIED")

        self.client.force_authenticate(user=None)
        anonymous = self.client.get("/api/procurement/formal-inventory-facts/")
        self.assertIn(anonymous.status_code, (401, 403))
