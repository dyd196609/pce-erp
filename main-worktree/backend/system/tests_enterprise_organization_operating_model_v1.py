from django.apps import apps
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import SupplierMaterialPrice
from pfm.models import Employee
from procurement.models import PurchaseOrder
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition

from .models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    OrganizationUnit,
    Permission,
    Position,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)


class EnterpriseOrganizationOperatingModelV1Tests(TestCase):
    endpoint = "/api/access-control/enterprise-organization-model/"

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="EOM-OPS", name="组织运作验收公司")
        cls.root = OrganizationUnit.objects.create(
            code="EOM-ROOT", name="验收公司", unit_type="COMPANY", company=cls.company
        )
        cls.center = OrganizationUnit.objects.create(
            code="EOM-CENTER", name="验收中心", unit_type="CENTER", company=cls.company,
            parent=cls.root,
        )
        cls.parent_department = Department.objects.create(
            code="EOM-PARENT", name="验收上级部门", company=cls.company,
            organization_unit=cls.center,
        )
        cls.department = Department.objects.create(
            code="EOM-DEPT", name="验收部门", company=cls.company
        )
        cls.manager_position = Position.objects.create(
            code="EOM-MGR", name="组织运作验收经理", company=cls.company,
            department=cls.department,
        )
        cls.employee_position = Position.objects.create(
            code="EOM-EMP", name="组织运作验收专员", company=cls.company,
            department=cls.department,
        )
        cls.manager = Employee.objects.create(
            employee_no="EOM-MANAGER", full_name="验收主管",
            department_ref=cls.department, position_ref=cls.manager_position,
        )
        cls.employee = Employee.objects.create(
            employee_no="EOM-EMPLOYEE", full_name="验收员工",
            department_ref=cls.department, position_ref=cls.employee_position,
        )
        cls.role = Role.objects.create(code="eom_default_role", name="组织运作默认角色")
        cls.view_permission = Permission.objects.get(code="system.organization_directory.view")
        RolePermission.objects.create(role=cls.role, permission=cls.view_permission)
        cls.admin = User.objects.create_superuser(
            username="eom_ops_admin", password=None, real_name="组织运作管理员",
            company_id=cls.company.pk,
        )
        cls.denied_user = User.objects.create_user(
            username="eom_ops_denied", password=None, real_name="组织运作只读人员",
            company_id=cls.company.pk,
        )
        cls.employee_account = User.objects.create_user(
            username="eom_employee_account", password=None, real_name="验收员工账户",
            company_id=cls.company.pk,
        )
        UserRoleScopeAssignment.objects.create(
            user=cls.denied_user, role=cls.role, organization=cls.company,
            scope_code="ORGANIZATION", business_hash="eom-read-only",
        )

    def setUp(self):
        self.client = APIClient()

    def _post(self, action, payload, user=None):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.post(
            self.endpoint,
            {"action": action, "payload": {"reason": "EOM V1 验收维护", **payload}},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )

    def _get(self):
        self.client.force_authenticate(user=self.admin)
        return self.client.get(self.endpoint)

    def test_complete_maintenance_roundtrip_and_audit_without_procurement_writes(self):
        po_before = PurchaseOrder.objects.count()
        price_before = SupplierMaterialPrice.objects.count()

        response = self._post("SAVE_ORGANIZATION_UNIT", {
            "id": self.center.pk, "code": self.center.code, "name": self.center.name,
            "unitType": "CENTER", "parentId": self.root.pk, "active": True,
            "effectiveFrom": "2026-08-16",
        })
        self.assertEqual(response.status_code, 200)

        response = self._post("SAVE_DEPARTMENT", {
            "departmentId": self.department.pk, "code": self.department.code,
            "name": self.department.name, "parentId": self.parent_department.pk,
            "departmentType": "FUNCTIONAL", "organizationUnitId": self.center.pk,
            "responsiblePositionId": self.manager_position.pk, "active": True,
        })
        self.assertEqual(response.status_code, 200)
        response = self._post("SAVE_DEPARTMENT_LEADER", {
            "departmentId": self.department.pk, "leaderEmployeeId": self.manager.pk,
        })
        self.assertEqual(response.status_code, 200)

        family_response = self._post("SAVE_JOB_FAMILY", {
            "code": "EOM-FAMILY", "name": "验收岗位族", "active": True,
        })
        self.assertEqual(family_response.status_code, 200)
        family_id = family_response.json()["data"]["target"]["id"]
        level_response = self._post("SAVE_JOB_LEVEL", {
            "code": "EOM-L2", "name": "验收等级", "rank": 2, "active": True,
        })
        self.assertEqual(level_response.status_code, 200)
        level_id = level_response.json()["data"]["target"]["id"]

        response = self._post("SAVE_POSITION", {
            "positionId": self.employee_position.pk,
            "code": self.employee_position.code, "name": self.employee_position.name,
            "jobFamilyId": family_id, "jobLevelId": level_id,
            "parentPositionId": self.manager_position.pk,
            "defaultRoleId": self.role.pk, "departmentId": self.department.pk,
            "effectiveFrom": "2026-08-16", "active": True,
        })
        self.assertEqual(response.status_code, 200)

        responsibility_response = self._post("SAVE_RESPONSIBILITY", {
            "code": "EOM_ACCEPTANCE_RESPONSIBILITY", "name": "验收职责",
            "businessDomain": "ACCEPTANCE", "description": "仅用于隔离自动测试",
            "status": "DRAFT",
        })
        self.assertEqual(responsibility_response.status_code, 200)
        responsibility_id = responsibility_response.json()["data"]["target"]["id"]
        responsibility_response = self._post("SAVE_RESPONSIBILITY", {
            "id": responsibility_id, "code": "EOM_ACCEPTANCE_RESPONSIBILITY",
            "name": "验收职责", "businessDomain": "ACCEPTANCE",
            "description": "仅用于隔离自动测试", "status": "ACTIVE",
            "effectiveFrom": "2026-08-16",
        })
        self.assertEqual(responsibility_response.status_code, 200)
        response = self._post("SAVE_POSITION_RESPONSIBILITY", {
            "positionId": self.employee_position.pk,
            "responsibilityId": responsibility_id, "isPrimary": True, "active": True,
        })
        self.assertEqual(response.status_code, 200)

        response = self._post("SAVE_REPORTING_RELATION", {
            "employeeId": self.employee.pk, "managerId": self.manager.pk,
            "relationType": "DIRECT", "active": True,
        })
        self.assertEqual(response.status_code, 200)
        response = self._post("SAVE_EMPLOYEE", {
            "employeeId": self.employee.pk, "employeeNo": self.employee.employee_no,
            "fullName": self.employee.full_name, "departmentId": self.department.pk,
            "positionId": self.employee_position.pk, "phone": "TEST-ONLY",
            "status": "active",
        })
        self.assertEqual(response.status_code, 200)
        response = self._post("SAVE_EMPLOYEE_ACCOUNT", {
            "employeeId": self.employee.pk, "userId": self.employee_account.pk,
        })
        self.assertEqual(response.status_code, 200)
        action_permission = Permission.objects.create(
            code="eom.acceptance.manager_check", name="验收经理检查", module="SYSTEM",
        )
        process = ProcessDefinition.objects.create(
            definition_code="EOM-ACCEPTANCE-FLOW", definition_name="组织运作验收流程",
            business_domain="ACCEPTANCE", document_type="EOM_ACCEPTANCE",
            version=1, active=True, definition_hash="eom-acceptance-definition",
        )
        workflow_node = WorkflowNodeDefinition.objects.create(
            process_definition=process, node_code="MANAGER-CHECK", node_name="经理检查",
            sequence=1, business_action_code=action_permission.code, active=True,
        )
        response = self._post("SAVE_WORKFLOW_RESPONSIBILITY", {
            "positionId": self.employee_position.pk,
            "responsibilityId": responsibility_id,
            "workflowNodeId": workflow_node.pk,
            "workflowCode": "CLIENT-MUST-NOT-CONTROL", "nodeCode": "CLIENT-MUST-NOT-CONTROL",
            "ownershipType": "APPROVER", "active": True,
        })
        self.assertEqual(response.status_code, 200)

        payload = self._get().json()["data"]
        department = next(row for row in payload["departments"] if row["id"] == self.department.pk)
        position = next(row for row in payload["positions"] if row["id"] == self.employee_position.pk)
        employee = next(row for row in payload["employees"] if row["id"] == self.employee.pk)
        self.assertEqual(department["parentId"], self.parent_department.pk)
        self.assertEqual(department["responsiblePositionId"], self.manager_position.pk)
        self.assertEqual(department["leaderEmployeeId"], self.manager.pk)
        self.assertEqual(position["jobFamilyId"], family_id)
        self.assertEqual(position["jobLevelId"], level_id)
        self.assertEqual(position["parentPositionId"], self.manager_position.pk)
        self.assertEqual(position["defaultRoleId"], self.role.pk)
        self.assertEqual(position["effectiveFrom"], "2026-08-16")
        self.assertIn("验收职责", position["responsibilityText"])
        self.assertEqual(employee["managerText"], self.manager.full_name)
        self.assertEqual(employee["username"], self.employee_account.username)
        self.assertEqual(payload["workflowResponsibilities"][0]["ownershipType"], "APPROVER")
        self.assertEqual(payload["workflowResponsibilities"][0]["workflowNodeId"], workflow_node.pk)
        self.assertEqual(payload["workflowResponsibilities"][0]["workflowCode"], process.definition_code)
        self.assertEqual(payload["workflowResponsibilities"][0]["nodeCode"], workflow_node.node_code)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 13)
        self.assertEqual(PurchaseOrder.objects.count(), po_before)
        self.assertEqual(SupplierMaterialPrice.objects.count(), price_before)

    def test_read_only_user_is_denied_by_backend(self):
        response = self._post("SAVE_DEPARTMENT", {
            "departmentId": self.department.pk, "code": self.department.code,
            "name": self.department.name, "departmentType": "FUNCTIONAL",
            "active": True,
        }, user=self.denied_user)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

        foundation_response = self.client.post(
            "/api/access-control/foundation/",
            {"action": "SAVE_DEPARTMENT", "payload": {"reason": "拒绝验证"}},
            format="json",
        )
        self.assertEqual(foundation_response.status_code, 403)

    def test_formal_admin_foundation_reuses_projection_and_operating_service(self):
        self.client.force_authenticate(user=self.admin)
        read_response = self.client.get("/api/access-control/foundation/")
        self.assertEqual(read_response.status_code, 200)
        row = next(item for item in read_response.json()["data"]["departments"] if item["id"] == self.department.pk)
        self.assertIn("responsiblePositionName", row)
        self.assertIn("leaderEmployeeName", row)

        missing_reason = self.client.post(
            "/api/access-control/foundation/",
            {"action": "SAVE_DEPARTMENT", "payload": {
                "departmentId": self.department.pk, "code": self.department.code,
                "name": self.department.name, "departmentType": "FUNCTIONAL",
            }}, format="json",
        )
        self.assertEqual(missing_reason.status_code, 400)
        self.assertEqual(missing_reason.json()["error"]["code"], "REASON_REQUIRED")

        saved = self.client.post(
            "/api/access-control/foundation/",
            {"action": "SAVE_DEPARTMENT", "payload": {
                "departmentId": self.department.pk, "code": self.department.code,
                "name": self.department.name, "departmentType": "FUNCTIONAL",
                "active": True, "reason": "正式管理员入口统一测试",
            }}, format="json",
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["data"]["actionCode"], "SAVE_DEPARTMENT")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)

    def test_hierarchy_cycles_and_self_manager_are_blocked(self):
        cycle = self._post("SAVE_DEPARTMENT", {
            "departmentId": self.parent_department.pk,
            "code": self.parent_department.code, "name": self.parent_department.name,
            "parentId": self.parent_department.pk, "departmentType": "FUNCTIONAL",
            "active": True,
        })
        self.assertEqual(cycle.status_code, 400)
        self.assertEqual(cycle.json()["error"]["code"], "HIERARCHY_CYCLE")
        self_manager = self._post("SAVE_REPORTING_RELATION", {
            "employeeId": self.employee.pk, "managerId": self.employee.pk,
            "relationType": "DIRECT", "active": True,
        })
        self.assertEqual(self_manager.status_code, 400)
        self.assertEqual(self_manager.json()["error"]["code"], "SELF_MANAGER_FORBIDDEN")

    def test_cancelled_operating_centers_are_not_active_system_models(self):
        self.assertNotIn("costcenter", apps.all_models["system"])
        self.assertNotIn("profitcenter", apps.all_models["system"])
        payload = self._get().json()["data"]
        self.assertNotIn("costCenters", payload)
        self.assertNotIn("profitCenterName", payload["organizationUnits"][0])
