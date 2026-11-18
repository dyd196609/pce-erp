from django.test import TestCase

from masterdata.models import Material, UnitOfMeasure
from pfm.models import Employee
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionResponsibility,
    Responsibility,
    Role,
    RolePermission,
    Process,
    Team,
    User,
    UserRoleScopeAssignment,
    Workshop,
)

from .models import (
    BOMItem,
    BOMVersion,
    ProductBOM,
    ProductCategory,
    ProductDefinition,
    ProductVersion,
    Routing,
    RoutingStep,
    RoutingVersion,
    WorkCenter,
    WorkCenterOperationCapability,
    WorkCenterTeamAssignment,
)
from .production_foundation_service import ProductionFoundationError, ProductionFoundationService


class ProductionFoundationA1Tests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="A1", name="A1验收公司")
        self.department = Department.objects.create(
            code="TECH", name="工艺部", company=self.company,
            department_type=Department.DepartmentType.FUNCTIONAL,
        )
        self.user = User.objects.create_user(
            username="a1_engineer", password="test-only", real_name="A1工艺工程师",
            company_id=self.company.pk,
        )
        self.role = Role.objects.create(code="A1_ENGINEER", name="A1工艺工程师角色")
        for code in (
            "production.master_data.product.maintain",
            "production.master_data.resource.maintain",
            "production.master_data.bom.maintain",
            "production.master_data.routing.maintain",
        ):
            permission, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"name": code, "module": "PRODUCTION"},
            )
            RolePermission.objects.create(role=self.role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.user, role=self.role, organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            business_hash="a1-test-authority",
        )
        responsibility = Responsibility.objects.create(
            code="A1-PROCESS", name="工艺文件与技术标准维护",
            status=Responsibility.Status.ACTIVE, is_active=True,
        )
        position = Position.objects.create(
            code="A1-TECH", name="A1工艺工程师", company=self.company,
            department=self.department, default_role=self.role,
        )
        PositionResponsibility.objects.create(
            position=position, responsibility=responsibility, is_primary=True, active=True,
        )
        Employee.objects.create(
            user=self.user, employee_no="A1-E001", full_name="A1工艺工程师",
            department_ref=self.department, position_ref=position, status="active",
        )
        self.uom = UnitOfMeasure.objects.create(
            company_id=self.company.pk, code="PCS", name="件",
        )
        self.finished = Material.objects.create(
            code="A1-FG", name="A1成品", unit="件", base_uom=self.uom,
            material_type="finished", company_id=self.company.pk,
            is_produced=True, is_purchased=False,
        )
        self.component = Material.objects.create(
            code="A1-RM", name="A1组件", unit="件", base_uom=self.uom,
            material_type="raw", company_id=self.company.pk,
            is_produced=False, is_purchased=True,
        )

    def test_full_formal_chain_can_write_product_category_and_audit(self):
        result = ProductionFoundationService.save(
            "product-categories", user=self.user,
            payload={
                "company_id": self.company.pk,
                "code": "A1-CAT",
                "name": "A1结构验收分类",
                "industry_type": "general",
                "reason": "A1自动测试",
            },
        )
        self.assertTrue(result["authorization"]["allowed"])
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.assertEqual(result["auditId"], OrganizationOperatingAuditRecord.objects.get().pk)

    def test_product_material_requires_finished_or_semi_material(self):
        category = ProductCategory.objects.create(
            company=self.company, code="A1-CAT", name="A1分类",
        )
        with self.assertRaises(ProductionFoundationError) as raised:
            ProductionFoundationService.save(
                "products", user=self.user,
                payload={
                    "company_id": self.company.pk,
                    "category_id": category.pk,
                    "material_id": self.component.pk,
                    "product_code": "A1-P001",
                    "product_name": "A1产品",
                    "version": "V1",
                    "emd_material_code": self.component.code,
                },
            )
        self.assertEqual(raised.exception.code, "VALIDATION_FAILED")

    def test_bom_and_routing_are_normalized_and_versioned(self):
        category = ProductCategory.objects.create(company=self.company, code="A1-CAT", name="A1分类")
        product = ProductDefinition.objects.create(
            company=self.company, category=category, material=self.finished,
            product_code="A1-P001", product_name="A1产品", version="V1",
            emd_material_code=self.finished.code,
        )
        product_version = ProductVersion.objects.create(product=product, version_no="V1")
        bom = ProductBOM.objects.create(company=self.company, product=product, bom_code="A1-BOM", name="A1 BOM")
        bom_version = BOMVersion.objects.create(
            bom=bom, product=product, product_version=product_version, bom_version="V1",
        )
        BOMItem.objects.create(
            bom_version=bom_version, line_no=10, material=self.component,
            quantity=1, uom=self.uom,
        )
        work_center = WorkCenter.objects.create(
            company=self.company, department=self.department, code="A1-WC", name="A1工作中心",
        )
        operation = ProductionFoundationService.save(
            "operations", user=self.user,
            payload={
                "company_id": self.company.pk, "work_center_id": work_center.pk,
                "code": "A1-OP", "name": "A1工序", "standard_hours": "1.0000",
            },
        )["row"]
        routing = Routing.objects.create(
            company=self.company, product=product, routing_code="A1-ROUTE", name="A1路线",
        )
        routing_version = RoutingVersion.objects.create(
            routing=routing, product=product, product_version=product_version, routing_version="V1",
        )
        RoutingStep.objects.create(
            routing_version=routing_version, sequence=10,
            operation_id=operation["id"], work_center=work_center, standard_hours=1,
        )
        self.assertEqual(bom_version.items.count(), 1)
        self.assertEqual(routing_version.steps.count(), 1)
        self.assertFalse(hasattr(bom_version, "material_list"))
        self.assertFalse(hasattr(routing_version, "operation_list"))

    def test_inactive_reference_is_rejected_for_new_default_selection(self):
        category = ProductCategory.objects.create(
            company=self.company, code="A1-OFF", name="停用分类", is_active=False,
        )
        with self.assertRaises(ProductionFoundationError) as raised:
            ProductionFoundationService.save(
                "products", user=self.user,
                payload={
                    "company_id": self.company.pk,
                    "category_id": category.pk,
                    "material_id": self.finished.pk,
                    "product_code": "A1-P002", "product_name": "A1产品2",
                    "version": "V1", "emd_material_code": self.finished.code,
                },
            )
        self.assertEqual(raised.exception.code, "INACTIVE_REFERENCE")

    def test_unprivileged_account_is_denied_without_audit_or_write(self):
        user = User.objects.create_user(
            username="a1_denied", password="test-only", real_name="无权限用户",
            company_id=self.company.pk,
        )
        with self.assertRaises(ProductionFoundationError):
            ProductionFoundationService.save(
                "product-categories", user=user,
                payload={"company_id": self.company.pk, "code": "DENIED", "name": "禁止写入"},
            )
        self.assertFalse(ProductCategory.objects.filter(code="DENIED").exists())
        self.assertFalse(OrganizationOperatingAuditRecord.objects.exists())

    def test_maintenance_authorization_reuses_permission_and_execution_chain(self):
        allowed = ProductionFoundationService.maintenance_authorization(
            "work-centers", user=self.user,
        )
        self.assertTrue(allowed["allowed"])
        self.assertEqual(
            allowed["actionCode"], "production.master_data.resource.maintain",
        )
        self.assertTrue(allowed["executionChainComplete"])
        self.assertEqual(allowed["executionChain"]["employeeNo"], "A1-E001")

        technical_admin = User.objects.create_superuser(
            username="a1_admin_without_employee",
            password="test-only",
            real_name="仅技术管理员",
            company_id=self.company.pk,
        )
        denied = ProductionFoundationService.maintenance_authorization(
            "work-center-operation-capabilities", user=technical_admin,
        )
        self.assertTrue(denied["permissionAllowed"])
        self.assertFalse(denied["allowed"])
        self.assertFalse(denied["executionChainComplete"])
        self.assertEqual(denied["decisionCode"], "FORMAL_EXECUTION_CHAIN_REQUIRED")
        self.assertIn("在职员工", denied["reason"])

    def test_work_center_candidate_and_team_relations_use_formal_service(self):
        workshop = Workshop.objects.create(
            company=self.company, department=self.department,
            code="A1-WS", name="A1车间",
        )
        team = Team.objects.create(
            company=self.company, department=self.department, workshop=workshop,
            code="A1-T", name="A1班组",
        )
        work_center = WorkCenter.objects.create(
            company=self.company, department=self.department, workshop=workshop,
            code="A1-WC-R", name="A1关系工作中心",
        )
        operation = Process.objects.create(
            company=self.company, workshop=workshop,
            code="A1-OP-R", name="A1关系工序",
        )
        capability = ProductionFoundationService.save(
            "work-center-operation-capabilities", user=self.user,
            payload={
                "work_center_id": work_center.pk,
                "operation_id": operation.pk,
                "assignment_role": "alternative",
                "capability_code": "A1-CAP",
                "capability_parameters": {"fixture": "formal"},
                "is_active": True,
                "reason": "验证工序候选工作中心正式关系",
            },
        )
        assignment = ProductionFoundationService.save(
            "work-center-team-assignments", user=self.user,
            payload={
                "work_center_id": work_center.pk,
                "team_id": team.pk,
                "is_primary": True,
                "is_active": True,
                "reason": "验证工作中心班组正式关系",
            },
        )
        self.assertTrue(capability["authorization"]["allowed"])
        self.assertTrue(assignment["authorization"]["allowed"])
        self.assertEqual(WorkCenterOperationCapability.objects.count(), 1)
        self.assertEqual(WorkCenterTeamAssignment.objects.count(), 1)
        self.assertEqual(
            len(ProductionFoundationService.list(
                "work-center-operation-capabilities",
                organization_id=self.company.pk,
            )),
            1,
        )
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 2)
