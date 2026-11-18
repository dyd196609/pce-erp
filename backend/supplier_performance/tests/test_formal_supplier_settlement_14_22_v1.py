from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import Material
from pfm.models import Employee
from procurement.models import (
    InventoryBalance,
    InventoryTransaction,
    PurchaseInspection,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    Supplier,
    Warehouse,
    WarehouseInbound,
)
from system.models import (
    Company,
    Department,
    Permission,
    Position,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition

from supplier_performance.formal_services import (
    ACTION_ANALYZE_DIFFERENCES,
    ACTION_APPROVE_PAYMENT_REQUEST,
    ACTION_CALCULATE_BUYER_PERFORMANCE,
    ACTION_CALCULATE_SUPPLIER_PERFORMANCE,
    ACTION_COMPLETE_SETTLEMENT,
    ACTION_CONFIRM_PAYABLE,
    ACTION_CONFIRM_RECONCILIATION,
    ACTION_CREATE_PAYMENT_REQUEST,
    ACTION_CREATE_RECONCILIATION,
    ACTION_RECORD_PAYMENT_STATUS,
    ACTION_RELEASE_PAYMENT_REQUEST,
    ACTION_SUBMIT_PAYMENT_REQUEST,
    BATCH_ID,
    PROCESS_CODE,
)
from supplier_performance.models import (
    BuyerPerformanceMetric,
    SupplierPayableConfirmation,
    SupplierPaymentRequest,
    SupplierPaymentStatusRecord,
    SupplierPerformanceMetric,
    SupplierReconciliation,
    SupplierReconciliationDifference,
    SupplierSettlementActionAudit,
    SupplierSettlementCompletion,
)


PURCHASE_ACTIONS = (
    ACTION_CREATE_RECONCILIATION,
    ACTION_ANALYZE_DIFFERENCES,
    ACTION_CONFIRM_RECONCILIATION,
    ACTION_CALCULATE_SUPPLIER_PERFORMANCE,
    ACTION_CALCULATE_BUYER_PERFORMANCE,
)
FINANCE_ACTIONS = (
    ACTION_CONFIRM_PAYABLE,
    ACTION_CREATE_PAYMENT_REQUEST,
    ACTION_SUBMIT_PAYMENT_REQUEST,
    ACTION_APPROVE_PAYMENT_REQUEST,
    ACTION_RELEASE_PAYMENT_REQUEST,
    ACTION_RECORD_PAYMENT_STATUS,
    ACTION_COMPLETE_SETTLEMENT,
)


class FormalSupplierSettlement1422V1Tests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="SS1422", name="14—22正式链测试组织")
        self.department = Department.objects.create(
            company=self.company, code="SCM1422", name="采购结算测试部"
        )
        self.process, _ = ProcessDefinition.objects.get_or_create(
            definition_code=PROCESS_CODE,
            defaults={
                "definition_name": "采购入库后供应商结算与绩效闭环",
                "business_domain": "SCM",
                "document_type": "SupplierReconciliation",
                "version": 1,
                "active": True,
                "definition_hash": "formal-14-22-test",
            },
        )
        self.purchase_user = self._actor(
            username="purchase1422",
            role_code="purchase_manager_1422",
            position_code="CGB-MGR-1422",
            title="采购经理",
            responsibility_code="RESP-PUR-1422",
            actions=PURCHASE_ACTIONS,
        )
        self.finance_user = self._actor(
            username="finance1422",
            role_code="supplier_settlement_finance_1422",
            position_code="FIN-ACCOUNT-1422",
            title="会计",
            responsibility_code="RESP-FIN-1422",
            actions=FINANCE_ACTIONS,
        )
        self.material = Material.objects.create(
            code="MT-1422", name="结算验收原材料", unit="件",
            company_id=self.company.pk, is_purchased=True,
        )
        self.supplier = Supplier.objects.create(
            code="SUP-1422", name="结算验收供应商",
            company_id=self.company.pk, is_active=True,
        )
        self.warehouse = Warehouse.objects.create(
            code="WH-1422", name="结算验收仓", company_id=self.company.pk,
        )
        self.order = PurchaseOrder.objects.create(
            po_no="PO-SYSTEM-ACCEPTANCE-1422",
            supplier=self.supplier,
            order_date=date.today(),
            expected_date=date.today(),
            status="closed",
            total_amount=Decimal("100.00"),
            buyer="采购经理",
            buyer_employee=self.purchase_user.employee_profile,
            purchase_mode="AGREED_PRICE",
            price_trace_status="CURRENT_LINKED",
            supplier_code_snapshot=self.supplier.code,
            supplier_name_snapshot=self.supplier.name,
            company_id=self.company.pk,
            created_by=self.purchase_user.pk,
            department=self.department,
            purchase_department=self.department,
        )
        PurchaseOrderItem.objects.create(
            po=self.order,
            material=self.material,
            material_code_snapshot=self.material.code,
            material_name_snapshot=self.material.name,
            unit_snapshot="件",
            currency_snapshot="CNY",
            quantity=Decimal("2"),
            unit_price=Decimal("50"),
            unit_price_snapshot=Decimal("50"),
            amount=Decimal("100"),
        )
        receipt = PurchaseReceipt.objects.create(
            receipt_no="RC-SYSTEM-ACCEPTANCE-1422",
            source_purchase_order=self.order,
            status="closed",
            quantity=Decimal("2"),
            amount=Decimal("100"),
            operator_employee=self.purchase_user.employee_profile,
            operator_account_id=self.purchase_user.pk,
        )
        inspection = PurchaseInspection.objects.create(
            inspection_no="IQC-SYSTEM-ACCEPTANCE-1422",
            source_receipt=receipt,
            status="qualified",
            quantity=Decimal("2"),
            qualified_quantity=Decimal("2"),
            rejected_quantity=Decimal("0"),
            inspection_date=date.today(),
            inspector_employee=self.purchase_user.employee_profile,
            inspector_account_id=self.purchase_user.pk,
        )
        inbound = WarehouseInbound.objects.create(
            inbound_no="IN-SYSTEM-ACCEPTANCE-1422",
            source_inspection=inspection,
            warehouse=self.warehouse,
            status="completed",
            quantity=Decimal("2"),
            amount=Decimal("100"),
            operator_employee=self.purchase_user.employee_profile,
            operator_account_id=self.purchase_user.pk,
        )
        self.balance = InventoryBalance.objects.create(
            warehouse=self.warehouse, material=self.material, quantity=Decimal("2")
        )
        InventoryTransaction.objects.create(
            transaction_no="IT-SYSTEM-ACCEPTANCE-1422",
            source_inbound=inbound,
            warehouse=self.warehouse,
            material=self.material,
            direction="IN",
            quantity=Decimal("2"),
            before_quantity=Decimal("0"),
            after_quantity=Decimal("2"),
            operator_employee=self.purchase_user.employee_profile,
            operator_account_id=self.purchase_user.pk,
        )
        self.client = APIClient()

    def _actor(self, *, username, role_code, position_code, title,
               responsibility_code, actions):
        role = Role.objects.create(
            code=role_code, name=f"{title}-{role_code}", description="14—22测试角色"
        )
        position = Position.objects.create(
            company=self.company,
            department=self.department,
            code=position_code,
            name=f"{title}-14—22",
            is_active=True,
        )
        responsibility = Responsibility.objects.create(
            code=responsibility_code,
            name=f"{title}结算职责",
            status="ACTIVE",
            is_active=True,
        )
        user = User.objects.create_user(
            username=username,
            password="test-only",
            real_name=f"系统流程验收{title}",
            company_id=self.company.pk,
        )
        Employee.objects.create(
            user=user,
            employee_no=f"EMP-{position_code}",
            full_name=f"系统流程验收{title}",
            status="active",
            department_ref=self.department,
            position_ref=position,
        )
        UserRoleScopeAssignment.objects.create(
            user=user,
            role=role,
            organization=self.company,
            scope_code="ORGANIZATION",
            business_hash=f"14-22-{username}",
        )
        for sequence, action_code in enumerate(actions, start=1):
            permission, _ = Permission.objects.get_or_create(
                code=action_code,
                defaults={"name": action_code, "module": "SCM"},
            )
            RolePermission.objects.create(role=role, permission=permission)
            node = WorkflowNodeDefinition.objects.filter(
                process_definition=self.process,
                business_action_code=action_code,
            ).first()
            if not node:
                node = WorkflowNodeDefinition.objects.create(
                    process_definition=self.process,
                    node_code=f"TEST-{username}-{sequence}",
                    node_name=action_code,
                    sequence=900 + (100 if username.startswith("finance") else 0) + sequence,
                    business_action_code=action_code,
                    active=True,
                )
            PositionWorkflowResponsibility.objects.create(
                position=position,
                responsibility=responsibility,
                workflow_node=node,
                workflow_code=PROCESS_CODE,
                node_code=node.node_code,
                ownership_type="OWNER",
                active=True,
            )
        return user

    def _action(self, user, action_code, source_id, expected=200):
        self.client.force_authenticate(user=user)
        response = self.client.post(
            "/api/scm/supplier-settlement-formal-actions/",
            {
                "actionCode": action_code,
                "sourceId": source_id,
                "reason": "系统流程验收数据 / 14—22正式链后端测试",
            },
            format="json",
        )
        self.assertEqual(response.status_code, expected, response.data)
        return response.data

    def test_full_chain_is_authorized_audited_idempotent_and_inventory_neutral(self):
        before_inventory = self.balance.quantity

        denied = self._action(
            self.finance_user, ACTION_CREATE_RECONCILIATION, self.order.pk, expected=403
        )
        self.assertEqual(denied["error"]["code"], "FORMAL_ACTION_AUTHORIZATION_DENIED")

        recon_result = self._action(
            self.purchase_user, ACTION_CREATE_RECONCILIATION, self.order.pk
        )["data"]
        reconciliation = SupplierReconciliation.objects.get(pk=recon_result["targetId"])
        self.assertEqual(reconciliation.batch_id, BATCH_ID)
        replay = self._action(
            self.purchase_user, ACTION_CREATE_RECONCILIATION, self.order.pk
        )["data"]
        self.assertTrue(replay["idempotentReplay"])

        difference_result = self._action(
            self.purchase_user, ACTION_ANALYZE_DIFFERENCES, reconciliation.pk
        )["data"]
        self.assertEqual(difference_result["quantityDifference"], "0.0000")
        self.assertEqual(difference_result["priceDifference"], "0.00")
        self.assertEqual(difference_result["amountDifference"], "0.00")
        self.assertEqual(
            set(SupplierReconciliationDifference.objects.values_list("difference_type", flat=True)),
            {"quantity_difference", "price_difference", "amount_difference"},
        )
        self.assertFalse(
            SupplierReconciliationDifference.objects.exclude(status="closed").exists()
        )

        self._action(
            self.purchase_user, ACTION_CONFIRM_RECONCILIATION, reconciliation.pk
        )
        reconciliation.refresh_from_db()
        self.assertEqual(reconciliation.status, "completed")

        payable_result = self._action(
            self.finance_user, ACTION_CONFIRM_PAYABLE, reconciliation.pk
        )["data"]
        payable = SupplierPayableConfirmation.objects.get(pk=payable_result["targetId"])
        self.assertEqual(payable.final_payable_amount, Decimal("100.00"))

        request_result = self._action(
            self.finance_user, ACTION_CREATE_PAYMENT_REQUEST, payable.pk
        )["data"]
        payment_request = SupplierPaymentRequest.objects.get(pk=request_result["targetId"])
        for action_code, expected_status in (
            (ACTION_SUBMIT_PAYMENT_REQUEST, "submitted"),
            (ACTION_APPROVE_PAYMENT_REQUEST, "approved"),
            (ACTION_RELEASE_PAYMENT_REQUEST, "payment_pending"),
        ):
            self._action(self.finance_user, action_code, payment_request.pk)
            payment_request.refresh_from_db()
            self.assertEqual(payment_request.status, expected_status)

        payment_result = self._action(
            self.finance_user, ACTION_RECORD_PAYMENT_STATUS, payment_request.pk
        )["data"]
        payment = SupplierPaymentStatusRecord.objects.get(pk=payment_result["targetId"])
        self.assertEqual(payment.status, "payment_completed")
        self.assertEqual(payment_result["remainingAmount"], "0.00")
        self.assertTrue(payment_result["businessStatusOnly"])

        settlement_result = self._action(
            self.finance_user, ACTION_COMPLETE_SETTLEMENT, payment.pk
        )["data"]
        settlement = SupplierSettlementCompletion.objects.get(
            pk=settlement_result["targetId"]
        )
        self.assertEqual(settlement.status, "completed")

        self._action(
            self.purchase_user, ACTION_CALCULATE_SUPPLIER_PERFORMANCE, settlement.pk
        )
        self._action(
            self.purchase_user, ACTION_CALCULATE_BUYER_PERFORMANCE, settlement.pk
        )
        self.assertEqual(SupplierPerformanceMetric.objects.count(), 1)
        self.assertEqual(BuyerPerformanceMetric.objects.count(), 1)

        self.balance.refresh_from_db()
        self.assertEqual(self.balance.quantity, before_inventory)
        self.assertEqual(InventoryTransaction.objects.count(), 1)
        self.assertGreaterEqual(SupplierSettlementActionAudit.objects.count(), 13)
        self.assertFalse(
            SupplierSettlementActionAudit.objects.exclude(
                evidence__safety__paymentExecutionWriteCount=0,
                evidence__safety__bankSendWriteCount=0,
                evidence__safety__fundDeductionCount=0,
                evidence__safety__generalLedgerWriteCount=0,
            ).exists()
        )

        self.client.force_authenticate(user=self.purchase_user)
        readback = self.client.get(
            f"/api/scm/supplier-settlement-formal-chain/{self.order.pk}/"
        )
        self.assertEqual(readback.status_code, 200, readback.data)
        facts = readback.data["data"]
        self.assertEqual(facts["purchaseOrder"]["no"], self.order.po_no)
        self.assertEqual(facts["reconciliation"]["status"], "completed")
        self.assertEqual(facts["payable"]["amount"], "100.00")
        self.assertEqual(facts["paymentRequest"]["amount"], "100.00")
        self.assertEqual(facts["paymentStatus"]["remainingAmount"], "0.00")
        self.assertEqual(facts["settlement"]["status"], "completed")
        self.assertEqual(facts["safety"]["paymentExecutionWriteCount"], 0)
        self.assertEqual(facts["safety"]["bankSendWriteCount"], 0)
        self.assertEqual(facts["safety"]["fundDeductionCount"], 0)
        self.assertEqual(facts["safety"]["generalLedgerWriteCount"], 0)

