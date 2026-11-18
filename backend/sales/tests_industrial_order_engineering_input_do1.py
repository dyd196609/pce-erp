from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import Material, UnitOfMeasure
from pfm.models import Employee
from planning.models import Demand, PlanningRequirement, PurchasePlan
from pde.models import ProductCategory, ProductConfiguration, ProductTemplate
from procurement.models import InventoryBalance, InventoryTransaction
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionWorkflowResponsibility, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition

from .models import Customer, SalesOrder, SalesOrderItem, SalesOrderItemEngineeringAttribute
from .services import create_order, engineering_readiness_facts
from .views import SalesOrderEngineeringAttributeCreateView, order_row


class IndustrialOrderEngineeringInputDO1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="DO1", name="DO-1工业订单测试公司")
        cls.department = Department.objects.create(
            company=cls.company, code="SALES-DO1", name="销售组织DO1", is_active=True,
        )
        cls.position = Position.objects.create(
            company=cls.company, department=cls.department,
            code="SALES-POS-DO1", name="销售工程输入测试岗", is_active=True,
        )
        cls.responsibility, _ = Responsibility.objects.update_or_create(
            code="RESP_SALES_ORDER_002",
            defaults={"name": "销售需求与订单协调", "is_active": True, "status": "ACTIVE"},
        )
        cls.user = User.objects.create_user(
            username="sales_do1_allowed", password="test-only", real_name="DO1销售员",
            company_id=cls.company.pk, is_active=True,
        )
        cls.employee = Employee.objects.create(
            user=cls.user, employee_no="EMP-SALES-DO1", full_name="DO1销售员",
            status="active", department_ref=cls.department, position_ref=cls.position,
        )
        cls.denied_user = User.objects.create_user(
            username="sales_do1_denied", password="test-only", real_name="无权限用户",
            company_id=cls.company.pk, is_active=True,
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="CUST-DO1", name="工业订单客户",
        )
        cls.uom = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="EA-DO1", name="件", is_active=True,
        )
        cls.material = Material.objects.create(
            code="MAT-SALES-DO1", name="工业订单测试物料", unit="件",
            base_uom=cls.uom, company_id=cls.company.pk, is_active=True,
            material_type="finished", is_purchased=False, is_produced=True,
        )
        cls.product_category = ProductCategory.objects.create(
            company=cls.company, code="WHOLE-HOUSE-DO1", name="全屋定制测试分类",
        )
        cls.product_template = ProductTemplate.objects.create(
            company=cls.company, category=cls.product_category,
            template_code="TPL-DO1", name="柜体配置模板", status="released",
        )
        cls.product_configuration = ProductConfiguration.objects.create(
            template=cls.product_template, configuration_no="CFG-DO1",
            parameters={"width": "1200"}, design_specification={},
            delivery_context={"spaceCode": "ROOM-01"}, input_hash="cfg-hash",
            idempotency_key="cfg-do1", status="resolved",
        )
        role = Role.objects.create(code="SALES_DO1_TEST", name="销售DO1测试角色")
        for code in (
            "sales.order.view", "sales.order.create",
            "sales.order.engineering_input.maintain",
        ):
            permission, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"name": f"测试权限 {code}", "module": "SALES"},
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=cls.user, role=role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, version=1, business_hash="do1-test",
        )
        process, _ = ProcessDefinition.objects.update_or_create(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
            defaults={
                "definition_name": "销售订单至供应计划主链", "business_domain": "SALES/PLAN",
                "document_type": "SalesOrder", "version": 1, "active": True,
                "definition_hash": "do1-test",
            },
        )
        for sequence, (node_code, action_code) in enumerate((
            ("CREATE_DO1", "sales.order.create"),
            ("ENGINEERING_INPUT_DO1", "sales.order.engineering_input.maintain"),
        ), 1):
            node, _ = WorkflowNodeDefinition.objects.update_or_create(
                process_definition=process, node_code=node_code,
                defaults={
                    "node_name": node_code, "sequence": sequence + 200,
                    "business_action_code": action_code, "active": True,
                },
            )
            PositionWorkflowResponsibility.objects.update_or_create(
                position=cls.position, workflow_code=process.definition_code,
                node_code=node_code, ownership_type="OWNER",
                defaults={
                    "responsibility": cls.responsibility,
                    "workflow_node": node, "active": True,
                },
            )

    def setUp(self):
        self.factory = APIRequestFactory()

    def payload(self, *, with_attributes=True):
        attributes = [{
            "sequence": 1,
            "rawSource": "customer-engineering-sheet.xlsx",
            "rawSheet": "Sheet-A",
            "externalSource": "CUSTOMER-PORTAL-01",
            "rawField": "Customer dimension A",
            "rawValue": "2045.0",
            "canonicalField": "component_height",
            "normalizedValue": "2045.000",
            "valueType": "decimal",
            "unitId": self.uom.pk,
            "sourceType": "SITE_MEASUREMENT",
        }, {
            "sequence": 1,
            "rawSource": "customer-engineering-sheet.xlsx",
            "rawSheet": "Sheet-A",
            "rawField": "Finish option",
            "rawValue": "A-01",
            "canonicalField": "finish_option",
            "normalizedValue": "FINISH-A-01",
            "valueType": "code",
            "sourceType": "DESIGN",
        }] if with_attributes else []
        return {
            "customerId": self.customer.pk,
            "departmentId": self.department.pk,
            "salesOwnerId": self.employee.pk,
            "orderDate": date.today().isoformat(),
            "requiredDate": (date.today() + timedelta(days=20)).isoformat(),
            "currency": "USD",
            "projectReference": "PROJECT-DO1",
            "contractReference": "CONTRACT-DO1",
            "deliveryInformation": {"address": "Customer Site A", "method": "scheduled"},
            "externalSourceNo": "EXT-SO-DO1",
            "remark": "工业订单与工程输入DO-1",
            "items": [{
                "lineNo": 10,
                "externalLineNo": "EXT-LINE-10",
                "materialId": self.material.pk,
                "quantity": "2.5000",
                "uomId": self.uom.pk,
                "requiredDate": (date.today() + timedelta(days=18)).isoformat(),
                "customerProductName": "Configurable Product",
                "customerProductDescription": "Customer-defined industrial item",
                "specification": "SPEC-DO1",
                "configurationReference": "CFG-DO1",
                "engineeringRequirements": "Use controlled engineering source facts",
                "qualityRequirements": "Q-DO1",
                "remark": "Line remark",
                "engineeringAttributes": attributes,
            }],
        }

    def test_header_item_and_multi_type_engineering_attributes_are_saved(self):
        before = {
            "demand": Demand.objects.count(),
            "requirement": PlanningRequirement.objects.count(),
            "purchase_plan": PurchasePlan.objects.count(),
            "inventory_balance": InventoryBalance.objects.count(),
            "inventory_transaction": InventoryTransaction.objects.count(),
        }
        order, item, audit = create_order(
            user=self.user, payload=self.payload(), authorization={"allowed": True, "decisionCode": "ALLOW"},
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )
        order.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(order.project_reference, "PROJECT-DO1")
        self.assertEqual(order.contract_reference, "CONTRACT-DO1")
        self.assertEqual(order.currency, "USD")
        self.assertEqual(order.sales_owner, self.employee)
        self.assertEqual(order.delivery_information["address"], "Customer Site A")
        self.assertEqual(item.line_no, 10)
        self.assertEqual(item.uom, self.uom)
        self.assertEqual(item.customer_product_name, "Configurable Product")
        self.assertEqual(item.configuration_reference, "CFG-DO1")
        self.assertEqual(item.engineering_attributes.count(), 2)
        self.assertSetEqual(
            set(item.engineering_attributes.values_list("value_type", flat=True)),
            {"decimal", "code"},
        )
        height = item.engineering_attributes.get(canonical_field="component_height")
        self.assertEqual(height.raw_value, "2045.0")
        self.assertEqual(height.normalized_value, "2045.000")
        self.assertEqual(height.source_type, "SITE_MEASUREMENT")
        self.assertEqual(audit.action_code, "sales.order.create")
        after = {
            "demand": Demand.objects.count(),
            "requirement": PlanningRequirement.objects.count(),
            "purchase_plan": PurchasePlan.objects.count(),
            "inventory_balance": InventoryBalance.objects.count(),
            "inventory_transaction": InventoryTransaction.objects.count(),
        }
        self.assertEqual(after, before)

    def test_raw_fact_is_immutable_and_normalized_value_does_not_overwrite_it(self):
        _, item, _ = create_order(
            user=self.user, payload=self.payload(), authorization={"allowed": True},
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )
        attribute = item.engineering_attributes.get(canonical_field="component_height")
        original_raw = attribute.raw_value
        attribute.normalized_value = "2046.000"
        attribute.save()
        attribute.refresh_from_db()
        self.assertEqual(attribute.raw_value, original_raw)
        attribute.raw_value = "changed"
        with self.assertRaises(ValidationError):
            attribute.save()

    def test_template_engineering_mode_and_space_structure_are_formal_order_item_facts(self):
        payload = self.payload(with_attributes=False)
        payload["items"][0].update({
            "engineeringMode": "TEMPLATE_ASSISTED",
            "productConfigurationId": self.product_configuration.pk,
            "spaceCode": "ROOM-01", "spaceName": "主卧",
            "installationArea": "北墙", "componentCategory": "柜体",
            "unitPrice": "880.5000",
        })
        order, item, _ = create_order(
            user=self.user, payload=payload, authorization={"allowed": True},
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )
        item.refresh_from_db()
        self.assertEqual(item.engineering_mode, "TEMPLATE_ASSISTED")
        self.assertEqual(item.product_configuration, self.product_configuration)
        self.assertEqual(item.space_code, "ROOM-01")
        self.assertEqual(item.space_name, "主卧")
        self.assertEqual(item.installation_area, "北墙")
        self.assertEqual(item.component_category, "柜体")
        self.assertEqual(item.amount, item.quantity * item.unit_price)
        self.assertEqual(order_row(order)["items"][0]["engineeringMode"], "TEMPLATE_ASSISTED")
        readiness = engineering_readiness_facts(order)
        self.assertFalse(readiness["ready"])
        self.assertIn("配置尚未解析为正式产品定义", readiness["lines"][0]["blockers"])

    def test_nullable_document_reference_and_old_order_compatibility(self):
        order, item, _ = create_order(
            user=self.user, payload=self.payload(with_attributes=False),
            authorization={"allowed": True},
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )
        row = order_row(order)
        self.assertIsNone(order.engineering_document_version_id)
        self.assertIsNone(item.engineering_document_version_id)
        self.assertEqual(row["engineeringDocumentReference"], "")
        self.assertEqual(row["items"][0]["engineeringAttributes"], [])
        self.assertEqual(row["items"][0]["engineeringDocumentReference"], "")

    def test_formal_endpoint_authorization_allow_deny_and_audit(self):
        order, item, _ = create_order(
            user=self.user, payload=self.payload(with_attributes=False),
            authorization={"allowed": True},
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )
        payload = {
            "rawSource": "manual-confirmed-form", "rawField": "hardness",
            "rawValue": "HRC 40", "canonicalField": "material_hardness",
            "normalizedValue": "40", "valueType": "decimal", "sourceType": "ENGINEERING_INPUT",
        }
        request = self.factory.post("/api/sales/engineering-attributes/", payload, format="json")
        force_authenticate(request, user=self.user)
        response = SalesOrderEngineeringAttributeCreateView.as_view()(
            request, order_id=order.pk, item_id=item.pk,
        )
        self.assertEqual(response.status_code, 201)
        audit_id = response.data["data"]["auditId"]
        audit = OrganizationOperatingAuditRecord.objects.get(pk=audit_id)
        self.assertEqual(audit.action_code, "sales.order.engineering_input.maintain")
        self.assertTrue(audit.after_snapshot["authorization"]["allowed"])

        denied_request = self.factory.post("/api/sales/engineering-attributes/", {
            **payload, "canonicalField": "material_tolerance",
        }, format="json")
        force_authenticate(denied_request, user=self.denied_user)
        denied = SalesOrderEngineeringAttributeCreateView.as_view()(
            denied_request, order_id=order.pk, item_id=item.pk,
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(
            SalesOrderItemEngineeringAttribute.objects.filter(
                canonical_field="material_tolerance",
            ).count(), 0,
        )

    def test_frozen_source_types_and_industry_neutral_schema(self):
        self.assertEqual(
            {value for value, _ in SalesOrderItemEngineeringAttribute.SOURCE_TYPE_CHOICES},
            {"CUSTOMER", "SITE_MEASUREMENT", "SALES", "DESIGN", "ENGINEERING_INPUT", "ENGINEERING_DERIVED", "MASTER_DATA", "RULE_PARAMETER", "AGGREGATED"},
        )
        field_names = {field.name.lower() for field in SalesOrderItem._meta.fields}
        field_names |= {field.name.lower() for field in SalesOrderItemEngineeringAttribute._meta.fields}
        for forbidden in ("door", "wall_panel", "cabinet", "wood_type", "洞高", "洞宽", "墙厚"):
            self.assertFalse(any(forbidden in name for name in field_names))

    def test_sales_page_has_no_localstorage_formal_fact(self):
        page = Path(settings.BASE_DIR).parent / "frontend" / "src" / "meta" / "pages" / "SalesOrderPage.vue"
        self.assertNotIn("localStorage", page.read_text(encoding="utf-8"))
