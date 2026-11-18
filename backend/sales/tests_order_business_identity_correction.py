from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from masterdata.models import Material
from pde.models import (
    BOMVersion,
    EngineeringCalculationDetail,
    EngineeringDerivedFact,
    OrderCrossFunctionalReview,
    OrderEngineeringInstance,
    OrderReviewSalesOrderRelation,
    PDEEngineeringPreparationAuthorization,
    ProductBOM,
    ProductDesignCompletionRecord,
    ProductDesignItem,
    Routing,
    RoutingVersion,
)
from pfm.models import Employee
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import BusinessStateTransition, ProcessDefinition, WorkflowNodeDefinition

from .models import Customer, SalesOrder, SalesOrderActionRequest, SalesOrderItem
from .order_business_identity_correction import (
    ACTION_CODE,
    SalesOrderBusinessIdentityCorrectionError,
    correct_sales_order_business_identity,
)


class SalesOrderBusinessIdentityCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="IDENTITY-CORR", name="身份纠正测试公司")
        cls.department = Department.objects.create(
            company=cls.company, code="IDENTITY-SALES", name="营销部",
        )
        cls.position = Position.objects.create(
            company=cls.company, department=cls.department,
            code="IDENTITY-SALES-POS", name="销售订单岗",
        )
        cls.user = User.objects.create_user(
            username="identity_sales", password="unused", real_name="正式销售员工",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.user, employee_no="IDENTITY-E001", full_name="正式销售员工",
            status="active", department_ref=cls.department, position_ref=cls.position,
        )
        permission, _ = Permission.objects.get_or_create(
            code="sales.order.update",
            defaults={"name": "更新销售订单", "module": "SALES"},
        )
        role, _ = Role.objects.get_or_create(
            code="identity_sales_editor", defaults={"name": "身份纠正测试销售岗"},
        )
        RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=cls.user, role=role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, version=1,
            business_hash="identity-correction-test",
        )
        responsibility, _ = Responsibility.objects.update_or_create(
            code="RESP_SALES_ORDER_002",
            defaults={"name": "销售需求与订单协调", "is_active": True, "status": "ACTIVE"},
        )
        PositionResponsibility.objects.create(
            position=cls.position, responsibility=responsibility, active=True, is_primary=True,
        )
        process, _ = ProcessDefinition.objects.update_or_create(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
            defaults={
                "definition_name": "销售订单至供应计划主链", "business_domain": "SALES",
                "document_type": "SalesOrder", "version": 1, "active": True,
                "definition_hash": "identity-correction-test",
            },
        )
        node, _ = WorkflowNodeDefinition.objects.update_or_create(
            process_definition=process, node_code="IDENTITY_CORRECTION_UPDATE",
            defaults={
                "node_name": "更新销售订单", "sequence": 901,
                "business_action_code": "sales.order.update", "active": True,
            },
        )
        PositionWorkflowResponsibility.objects.update_or_create(
            position=cls.position, workflow_code=process.definition_code,
            node_code=node.node_code, ownership_type="OWNER",
            defaults={
                "responsibility": responsibility, "workflow_node": node, "active": True,
            },
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="IDENTITY-CUSTOMER", name="真实客户",
        )
        cls.material = Material.objects.create(
            company_id=cls.company.pk, code="IDENTITY-MATERIAL", name="真实产品",
            unit="件", material_type="finished", is_active=True,
        )

    def setUp(self):
        self.delivery_before = {
            "developmentOnly": True,
            "externalCommunicationAllowed": False,
            "developmentContract": {
                "contractNo": "PCE-DEV-SC-20260915-001",
                "purpose": "DEVELOPMENT_ONLY",
            },
            "businessPurpose": "DEVELOPMENT_VALIDATION",
            "committedDeliveryDate": "2026-10-31",
            "sourceRecordId": 11,
            "sourceVersion": "R20260915144257758338",
        }
        self.order = SalesOrder(
            company=self.company, department=self.department, customer=self.customer,
            order_no="SO202609180003", order_date=date.today(),
            required_delivery_date=date.today() + timedelta(days=20),
            order_type="project", order_source="crm",
            business_purpose=SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION,
            project_reference="上海 大居苑",
            contract_reference="PCE-DEV-SC-20260915-001",
            delivery_information=deepcopy(self.delivery_before),
            external_source_no="1-4-正", status="draft", version=1,
            acceptance_marker="DEVELOPMENT_ONLY",
            remark="开发验证样本，不得进入正式业务主线。", created_by=self.user,
        )
        self.order._business_state_initialization_authorized = True
        try:
            self.order.save(force_insert=True)
        finally:
            self.order._business_state_initialization_authorized = False
        for line_no in range(1, 5):
            SalesOrderItem.objects.create(
                sales_order=self.order, line_no=line_no, material=self.material,
                engineering_mode="ORDER_ENGINEERED", quantity=Decimal(line_no),
                unit_price=Decimal("10.00"), tax_rate=Decimal("0.13"),
                required_date=self.order.required_delivery_date,
                customer_product_name=f"真实产品{line_no}",
                external_line_no=f"DEV-L0{line_no}",
            )

    def _call(self, **overrides):
        values = {
            "actor": self.user,
            "order_id": self.order.pk,
            "expected_order_no": self.order.order_no,
            "expected_customer_id": self.customer.pk,
            "expected_project_reference": "上海 大居苑",
            "expected_external_source_no": "1-4-正",
            "expected_contract_reference": "PCE-DEV-SC-20260915-001",
            "expected_remark": "开发验证样本，不得进入正式业务主线。",
            "expected_item_count": 4,
            "target_business_purpose": "FORMAL_SALE",
            "idempotency_key": "SO202609180003-FORMAL-IDENTITY-CORRECTION-20261005",
            "request_id": "SO202609180003-FORMAL-IDENTITY-CORRECTION-REQ-1",
            "reason": "真实订单业务身份纠正",
            "source": "test",
        }
        values.update(overrides)
        return correct_sales_order_business_identity(**values)

    def _set_status(self, status):
        self.order.status = status
        self.order._business_state_transition_authorized = True
        try:
            self.order.save(update_fields=["status"])
        finally:
            self.order._business_state_transition_authorized = False

    def test_success_changes_only_current_business_identity(self):
        item_facts = list(self.order.items.values())
        result = self._call()
        self.order.refresh_from_db()
        self.assertFalse(result["idempotent"])
        self.assertEqual(self.order.business_purpose, "FORMAL_SALE")
        self.assertEqual(self.order.acceptance_marker, "")
        self.assertEqual(self.order.contract_reference, "")
        self.assertEqual(self.order.remark, "")
        self.assertEqual(self.order.version, 2)
        self.assertEqual(
            self.order.delivery_information,
            {
                "committedDeliveryDate": "2026-10-31",
                "sourceRecordId": 11,
                "sourceVersion": "R20260915144257758338",
            },
        )
        self.assertEqual(self.order.order_no, "SO202609180003")
        self.assertEqual(self.order.customer_id, self.customer.pk)
        self.assertEqual(self.order.project_reference, "上海 大居苑")
        self.assertEqual(self.order.external_source_no, "1-4-正")
        self.assertEqual(self.order.status, "draft")
        self.assertEqual(list(self.order.items.values()), item_facts)

    def test_audit_and_action_request_capture_formal_actor_and_idempotency(self):
        result = self._call()
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["organizationAuditId"])
        action = SalesOrderActionRequest.objects.get(pk=result["actionRequestId"])
        self.assertEqual(audit.action_code, ACTION_CODE)
        self.assertEqual(audit.actor, self.user)
        self.assertEqual(audit.before_snapshot["actor"]["employeeNo"], "IDENTITY-E001")
        self.assertEqual(audit.before_snapshot["actor"]["departmentId"], self.department.pk)
        self.assertEqual(audit.before_snapshot["actor"]["positionId"], self.position.pk)
        self.assertEqual(audit.before_snapshot["actor"]["companyId"], self.company.pk)
        self.assertEqual(audit.after_snapshot["idempotencyKey"], result["idempotencyKey"])
        self.assertTrue(audit.created_at)
        self.assertEqual(action.audit_record, audit)
        self.assertEqual(action.source_state, "draft")
        self.assertEqual(action.target_state, "draft")

    def test_identical_replay_is_write_free_and_version_stable(self):
        first = self._call()
        audit_count = OrganizationOperatingAuditRecord.objects.count()
        action_count = SalesOrderActionRequest.objects.count()
        second = self._call()
        self.order.refresh_from_db()
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["organizationAuditId"], first["organizationAuditId"])
        self.assertEqual(self.order.version, 2)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), audit_count)
        self.assertEqual(SalesOrderActionRequest.objects.count(), action_count)

    def test_same_key_with_different_request_is_rejected(self):
        self._call()
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "其他请求号"):
            self._call(request_id="DIFFERENT-REQUEST")

    def test_second_idempotency_key_is_rejected(self):
        self._call()
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "其他幂等键"):
            self._call(idempotency_key="DIFFERENT-KEY", request_id="DIFFERENT-REQUEST")

    def test_unauthorized_employee_is_rejected(self):
        user = User.objects.create_user(
            username="identity_denied", password="unused", company_id=self.company.pk,
        )
        Employee.objects.create(
            user=user, employee_no="IDENTITY-DENIED", full_name="无授权员工",
            status="active", department_ref=self.department, position_ref=self.position,
        )
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "没有销售订单更新权限"):
            self._call(actor=user)

    def test_superuser_is_rejected(self):
        admin = User.objects.create_superuser(
            username="identity_admin", password="unused", company_id=self.company.pk,
        )
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "管理员"):
            self._call(actor=admin)

    def test_cancelled_order_is_rejected_without_writes(self):
        self._set_status("cancelled")
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "已取消订单"):
            self._call()
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_non_draft_order_is_rejected(self):
        self._set_status("submitted")
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "草稿订单"):
            self._call()

    def test_invalid_target_purpose_is_rejected(self):
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "FORMAL_SALE"):
            self._call(target_business_purpose="SYSTEM_TEST")

    def test_source_identity_mismatch_is_rejected(self):
        self.order.acceptance_marker = ""
        self.order.save(update_fields=["acceptance_marker"])
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "开发验证身份"):
            self._call()

    def test_commercial_identity_mismatch_is_rejected(self):
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "商业身份"):
            self._call(expected_external_source_no="WRONG")

    def test_development_contract_mismatch_is_rejected(self):
        delivery = deepcopy(self.order.delivery_information)
        delivery["developmentContract"]["contractNo"] = "OTHER"
        self.order.delivery_information = delivery
        self.order.save(update_fields=["delivery_information"])
        with self.assertRaisesRegex(SalesOrderBusinessIdentityCorrectionError, "开发合同事实"):
            self._call()

    def test_missing_idempotency_reason_and_request_are_rejected(self):
        for field in ("idempotency_key", "request_id", "reason"):
            with self.subTest(field=field):
                with self.assertRaises(SalesOrderBusinessIdentityCorrectionError):
                    self._call(**{field: ""})

    def test_no_pde_admission_engineering_or_state_transition_writes(self):
        tracked = (
            OrderCrossFunctionalReview,
            OrderReviewSalesOrderRelation,
            PDEEngineeringPreparationAuthorization,
            OrderEngineeringInstance,
            ProductDesignItem,
            ProductDesignCompletionRecord,
            EngineeringCalculationDetail,
            EngineeringDerivedFact,
            ProductBOM,
            BOMVersion,
            Routing,
            RoutingVersion,
            BusinessStateTransition,
        )
        before = {model: model.objects.count() for model in tracked}
        self._call()
        self.assertEqual({model: model.objects.count() for model in tracked}, before)
