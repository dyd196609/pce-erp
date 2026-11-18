from datetime import date, timedelta

from django.test import TestCase

from masterdata.models import Material
from pfm.models import Employee
from system.models import (
    Company,
    Department,
    Position,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Responsibility,
    User,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition

from .models import Customer, SalesOrder
from .services import create_order


class SalesOrderBusinessPurposeCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            code="BP-CREATE", name="Business Purpose创建测试公司",
        )
        cls.department = Department.objects.create(
            code="BP-CREATE-SALES", name="销售部", company=cls.company,
        )
        cls.user = User.objects.create_superuser(
            username="bp_create_user",
            password="unused",
            real_name="Business Purpose创建测试人",
            company_id=cls.company.pk,
        )
        cls.position = Position.objects.create(
            code="BP-CREATE-POS",
            name="销售订单岗",
            company=cls.company,
            department=cls.department,
        )
        responsibility, _ = Responsibility.objects.update_or_create(
            code="RESP_SALES_ORDER_002",
            defaults={
                "name": "销售需求与订单协调",
                "status": "ACTIVE",
                "is_active": True,
            },
        )
        PositionResponsibility.objects.create(
            position=cls.position,
            responsibility=responsibility,
            is_primary=True,
            active=True,
        )
        Employee.objects.create(
            user=cls.user,
            employee_no="BP-CREATE-E001",
            full_name="Business Purpose创建测试人",
            department_ref=cls.department,
            position_ref=cls.position,
            status="active",
        )
        process, _ = ProcessDefinition.objects.update_or_create(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
            defaults={
                "definition_name": "销售订单创建",
                "business_domain": "SALES",
                "document_type": "SalesOrder",
                "version": 1,
                "active": True,
                "definition_hash": "business-purpose-create-test",
            },
        )
        node, _ = WorkflowNodeDefinition.objects.update_or_create(
            process_definition=process,
            node_code="CREATE",
            defaults={
                "node_name": "创建订单",
                "sequence": 1,
                "business_action_code": "sales.order.create",
                "active": True,
            },
        )
        PositionWorkflowResponsibility.objects.update_or_create(
            position=cls.position,
            workflow_code="SALES_ORDER_TO_SUPPLY_PLAN",
            node_code="CREATE",
            ownership_type="OWNER",
            defaults={
                "responsibility": responsibility,
                "workflow_node": node,
                "active": True,
            },
        )
        cls.customer = Customer.objects.create(
            company=cls.company,
            code="BP-CREATE-CUSTOMER",
            name="Business Purpose测试客户",
        )
        cls.material = Material.objects.create(
            company_id=cls.company.pk,
            code="BP-CREATE-MATERIAL",
            name="Business Purpose测试产品",
            unit="件",
            material_type="finished",
            is_active=True,
        )

    def _create_and_read_back(self, purpose, marker=""):
        order, _, _ = create_order(
            user=self.user,
            authorization={"allowed": True},
            business_purpose=purpose,
            payload={
                "customerId": self.customer.pk,
                "departmentId": self.department.pk,
                "requiredDate": (date.today() + timedelta(days=10)).isoformat(),
                "orderSource": "manual",
                "acceptanceMarker": marker,
                "items": [{
                    "materialId": self.material.pk,
                    "quantity": "1",
                }],
            },
        )
        return SalesOrder.objects.get(pk=order.pk)

    def test_formal_sale_is_persisted_at_creation(self):
        persisted = self._create_and_read_back(SalesOrder.BusinessPurpose.FORMAL_SALE)
        self.assertEqual(
            persisted.business_purpose,
            SalesOrder.BusinessPurpose.FORMAL_SALE,
        )

    def test_development_validation_is_persisted_at_creation(self):
        persisted = self._create_and_read_back(
            SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION,
            marker="DEVELOPMENT_ONLY",
        )
        self.assertEqual(
            persisted.business_purpose,
            SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION,
        )

    def test_system_test_is_persisted_at_creation(self):
        persisted = self._create_and_read_back(
            SalesOrder.BusinessPurpose.SYSTEM_TEST,
            marker="SYSTEM_TEST",
        )
        self.assertEqual(
            persisted.business_purpose,
            SalesOrder.BusinessPurpose.SYSTEM_TEST,
        )

