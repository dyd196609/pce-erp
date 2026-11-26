import hashlib
import json

from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import SupplierMaterialPrice
from pfm.models import (
    Employee,
    EmployeeReportingRelation,
    OrganizationLeadershipAssignment,
)
from procurement.models import PurchaseOrder

from .models import (
    Company,
    Department,
    JobFamily,
    JobLevel,
    OrganizationUnit,
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


class EnterpriseOrganizationModelV1Tests(TestCase):
    endpoint = "/api/access-control/enterprise-organization-model/"

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            code="ORG-V1-COMP", name="组织模型测试公司", is_active=True
        )
        cls.other_company = Company.objects.create(
            code="ORG-V1-OTHER", name="组织模型隔离公司", is_active=True
        )
        cls.company_unit = OrganizationUnit.objects.create(
            code="ORG-V1-ROOT", name="组织模型测试公司",
            unit_type=OrganizationUnit.UnitType.COMPANY, company=cls.company,
        )
        cls.center_unit = OrganizationUnit.objects.create(
            code="ORG-V1-SUPPLY", name="供应链中心",
            unit_type=OrganizationUnit.UnitType.CENTER,
            parent=cls.company_unit, company=cls.company,
        )
        cls.purchase_unit = OrganizationUnit.objects.create(
            code="ORG-V1-PURCHASE", name="采购部",
            unit_type=OrganizationUnit.UnitType.DEPARTMENT,
            parent=cls.center_unit, company=cls.company,
        )
        cls.team_unit = OrganizationUnit.objects.create(
            code="ORG-V1-RAW", name="原材料采购组",
            unit_type=OrganizationUnit.UnitType.TEAM,
            parent=cls.purchase_unit, company=cls.company,
        )
        cls.center_department = Department.objects.create(
            code="ORG-V1-SC", name="供应链中心", company=cls.company,
            department_type=Department.DepartmentType.BUSINESS,
            organization_unit=cls.center_unit,
        )
        cls.purchase_department = Department.objects.create(
            code="ORG-V1-PD", name="采购部", company=cls.company,
            parent=cls.center_department,
            department_type=Department.DepartmentType.FUNCTIONAL,
            organization_unit=cls.purchase_unit,
        )
        cls.raw_team = Department.objects.create(
            code="ORG-V1-RAW", name="原材料采购组", company=cls.company,
            parent=cls.purchase_department,
            department_type=Department.DepartmentType.TEAM,
            organization_unit=cls.team_unit,
        )
        cls.other_department = Department.objects.create(
            code="ORG-V1-OTHER", name="其他部门", company=cls.company
        )

        cls.job_family = JobFamily.objects.create(
            code="ORG-V1-JF", name="供应链岗位族", company=cls.company
        )
        cls.level_manager = JobLevel.objects.create(
            code="ORG-V1-L3", name="经理级", rank=3, company=cls.company
        )
        cls.level_specialist = JobLevel.objects.create(
            code="ORG-V1-L1", name="专员级", rank=1, company=cls.company
        )
        cls.default_role = Role.objects.create(
            code="organization_model_test_approver", name="组织模型测试审批角色"
        )
        cls.manager_position = Position.objects.create(
            code="ORG-V1-PM", name="组织模型采购经理", company=cls.company,
            department=cls.purchase_department, job_family=cls.job_family,
            job_level=cls.level_manager, default_role=cls.default_role,
        )
        cls.buyer_position = Position.objects.create(
            code="ORG-V1-BUYER", name="组织模型采购员", company=cls.company,
            department=cls.raw_team, job_family=cls.job_family,
            job_level=cls.level_specialist, parent_position=cls.manager_position,
        )
        cls.purchase_department.responsible_position = cls.manager_position
        cls.purchase_department.save(update_fields=["responsible_position"])
        cls.other_position = Position.objects.create(
            code="ORG-V1-OTHER", name="组织模型其他岗位", company=cls.company,
            department=cls.other_department,
        )
        cls.responsibility = Responsibility.objects.create(
            code="ORG-V1-SUPPLIER-MGMT", name="供应商管理", category="SCM"
        )
        PositionResponsibility.objects.create(
            position=cls.manager_position,
            responsibility=cls.responsibility,
            is_primary=True,
        )
        PositionWorkflowResponsibility.objects.create(
            position=cls.manager_position,
            responsibility=cls.responsibility,
            workflow_code="purchase-request",
            node_code="manager-review",
            ownership_type=PositionWorkflowResponsibility.OwnershipType.APPROVER,
        )

        cls.manager_employee = Employee.objects.create(
            employee_no="ORG-V1-E-MGR", full_name="组织模型主管",
            department_ref=cls.purchase_department,
            position_ref=cls.manager_position,
            department_id=cls.purchase_department.pk,
            department_name=cls.purchase_department.name,
            position=cls.manager_position.name,
        )
        cls.buyer_employee = Employee.objects.create(
            employee_no="ORG-V1-E-BUYER", full_name="组织模型采购员",
            department_ref=cls.raw_team,
            position_ref=cls.buyer_position,
            department_id=cls.raw_team.pk,
            department_name=cls.raw_team.name,
            position=cls.buyer_position.name,
        )
        EmployeeReportingRelation.objects.create(
            employee=cls.buyer_employee,
            manager=cls.manager_employee,
            relation_type=EmployeeReportingRelation.RelationType.DIRECT,
        )
        OrganizationLeadershipAssignment.objects.create(
            employee=cls.manager_employee, department=cls.purchase_department
        )
        OrganizationLeadershipAssignment.objects.create(
            employee=cls.manager_employee, organization_unit=cls.center_unit
        )

        cls.directory_permission = Permission.objects.filter(
            code="system.organization_directory.view"
        ).first() or Permission.objects.create(
            code="system.organization_directory.view",
            name="组织目录查看", module="SYSTEM",
        )
        RolePermission.objects.create(
            role=cls.default_role, permission=cls.directory_permission
        )

        cls.admin = User.objects.create_superuser(
            username="org_v1_admin", password=None,
            real_name="组织模型管理员", company_id=cls.company.pk,
        )
        cls.department_user = User.objects.create_user(
            username="org_v1_department", password=None,
            real_name="组织模型部门用户", company_id=cls.company.pk,
        )
        cls.buyer_employee.user = cls.department_user
        cls.buyer_employee.save(update_fields=["user"])
        authority_payload = {
            "userId": cls.department_user.pk,
            "roleCode": cls.default_role.code,
            "legalEntityId": str(cls.company.pk),
            "departmentId": cls.raw_team.pk,
            "scopeCode": "DEPARTMENT",
            "version": 1,
        }
        UserRoleScopeAssignment.objects.create(
            user=cls.department_user,
            role=cls.default_role,
            organization=cls.company,
            department=cls.raw_team,
            scope_code=UserRoleScopeAssignment.ScopeCode.DEPARTMENT,
            business_hash=hashlib.sha256(
                json.dumps(authority_payload, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        )

    def _get(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.get(self.endpoint)

    def test_admin_reads_complete_operating_model_without_business_writes(self):
        purchase_orders_before = PurchaseOrder.objects.count()
        prices_before = SupplierMaterialPrice.objects.count()
        response = self._get(self.admin)

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["contractVersion"], "PCE-ENTERPRISE-ORGANIZATION-MODEL-V1")
        self.assertTrue(payload["authorization"]["allowed"])
        self.assertEqual(payload["strictFacts"]["authorizedBusinessWriteCount"], 0)
        self.assertEqual(payload["strictFacts"]["workflowExecutionCount"], 0)
        self.assertEqual(PurchaseOrder.objects.count(), purchase_orders_before)
        self.assertEqual(SupplierMaterialPrice.objects.count(), prices_before)

        unit_by_code = {row["code"]: row for row in payload["organizationUnits"]}
        self.assertEqual(unit_by_code["ORG-V1-RAW"]["depth"], 3)
        self.assertEqual(
            unit_by_code["ORG-V1-RAW"]["pathText"],
            "组织模型测试公司 / 供应链中心 / 采购部 / 原材料采购组",
        )
        department_by_code = {row["code"]: row for row in payload["departments"]}
        self.assertEqual(
            department_by_code["ORG-V1-PD"]["responsiblePositionCode"],
            "ORG-V1-PM",
        )
        position_by_code = {row["code"]: row for row in payload["positions"]}
        self.assertEqual(position_by_code["ORG-V1-BUYER"]["parentPositionName"], "组织模型采购经理")
        self.assertEqual(position_by_code["ORG-V1-PM"]["defaultRoleCode"], self.default_role.code)
        self.assertIn("供应商管理", position_by_code["ORG-V1-PM"]["responsibilityText"])
        self.assertIn("purchase-request/manager-review", position_by_code["ORG-V1-PM"]["workflowResponsibilityText"])
        employee_by_no = {row["employeeNo"]: row for row in payload["employees"]}
        self.assertEqual(employee_by_no["ORG-V1-E-BUYER"]["managerText"], "组织模型主管")

    def test_department_scope_returns_only_authorized_department_operating_facts(self):
        response = self._get(self.department_user)
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["authorization"]["scope"]["codes"], ["DEPARTMENT"])
        self.assertEqual([row["code"] for row in payload["departments"]], ["ORG-V1-RAW"])
        self.assertEqual([row["code"] for row in payload["positions"]], ["ORG-V1-BUYER"])
        self.assertEqual([row["employeeNo"] for row in payload["employees"]], ["ORG-V1-E-BUYER"])
        self.assertNotIn("ORG-V1-OTHER", {row["code"] for row in payload["departments"]})

    def test_position_role_and_responsibility_remain_separate_objects(self):
        self.assertNotEqual(Position._meta.db_table, Role._meta.db_table)
        self.assertEqual(self.manager_position.default_role, self.default_role)
        mapping = PositionResponsibility.objects.get(position=self.manager_position)
        self.assertEqual(mapping.responsibility, self.responsibility)
        self.assertIsInstance(mapping.responsibility, Responsibility)
        self.assertIsInstance(self.manager_position.default_role, Role)
