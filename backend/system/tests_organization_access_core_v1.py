from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from pfm.models import Employee
from procurement.models import PurchaseOrder

from .authorization import (
    AUTHORIZATION_CONTRACT_VERSION,
    AuthorizationService,
)
from .authorization_views import ORGANIZATION_DIRECTORY_VIEW
from .models import (
    Company,
    Department,
    Permission,
    Position,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)


class OrganizationAccessCoreV1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="PCE-V1", name="PCE V1 测试公司")
        cls.department = Department.objects.create(
            code="PCE-V1-PUR", name="V1采购部", company=cls.company,
        )
        cls.other_department = Department.objects.create(
            code="PCE-V1-FIN", name="V1财务部", company=cls.company,
        )
        cls.position = Position.objects.create(
            code="PCE-V1-BUYER", name="V1组织目录测试岗位",
            company=cls.company, department=cls.department,
        )
        cls.action, _ = Permission.objects.get_or_create(
            code=ORGANIZATION_DIRECTORY_VIEW,
            defaults={"name": "组织目录查看", "module": "SYSTEM"},
        )
        cls.viewer_role = Role.objects.create(
            code="pce_v1_org_viewer", name="V1组织目录查看角色",
        )
        cls.denied_role = Role.objects.create(
            code="pce_v1_denied", name="V1无目录权限角色",
        )
        RolePermission.objects.create(role=cls.viewer_role, permission=cls.action)
        cls.allowed_user = User.objects.create_user(
            username="pce-v1-allowed", password="test", real_name="V1允许用户",
            company_id=cls.company.pk,
        )
        cls.denied_user = User.objects.create_user(
            username="pce-v1-denied", password="test", real_name="V1拒绝用户",
            company_id=cls.company.pk,
        )
        cls.admin = User.objects.create_superuser(
            username="pce-v1-admin", password="test", real_name="V1管理员",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.allowed_user, employee_no="PCE-V1-E01", full_name="V1允许用户",
            department_ref=cls.department, position_ref=cls.position,
            department_id=cls.department.pk, department_name=cls.department.name,
            position=cls.position.name, status="active",
        )
        UserRoleScopeAssignment.objects.create(
            user=cls.allowed_user, role=cls.viewer_role,
            organization=cls.company, department=cls.department,
            scope_code=UserRoleScopeAssignment.ScopeCode.DEPARTMENT,
            active=True, version=1, business_hash="allowed",
        )
        UserRoleScopeAssignment.objects.create(
            user=cls.denied_user, role=cls.denied_role,
            organization=cls.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True, version=1, business_hash="denied",
        )

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_v1_position_and_role_are_independent_models(self):
        self.assertNotEqual(self.position.code, self.viewer_role.code)
        self.assertEqual(self.allowed_user.employee_profile.position_ref, self.position)
        self.assertEqual(
            self.allowed_user.role_scope_assignments.get().role,
            self.viewer_role,
        )

    def test_v1_department_scope_requires_a_real_department(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            UserRoleScopeAssignment.objects.create(
                user=self.denied_user,
                role=self.viewer_role,
                organization=self.company,
                scope_code=UserRoleScopeAssignment.ScopeCode.DEPARTMENT,
                business_hash="invalid",
            )

    def test_v1_authorization_service_returns_allow_and_deny(self):
        allowed = AuthorizationService.decide(
            user=self.allowed_user,
            action_code=ORGANIZATION_DIRECTORY_VIEW,
            organization_id=self.company.pk,
            business_object={"departmentId": self.department.pk},
        )
        denied = AuthorizationService.decide(
            user=self.denied_user,
            action_code=ORGANIZATION_DIRECTORY_VIEW,
            organization_id=self.company.pk,
        )
        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["decisionCode"], "ALLOWED")
        self.assertEqual(allowed["scope"]["codes"], ["DEPARTMENT"])
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["decisionCode"], "PERMISSION_DENIED")

    def test_v1_permission_profile_uses_formal_server_facts(self):
        response = self.client_for(self.allowed_user).get(
            "/api/access-control/profile/"
        )
        self.assertEqual(response.status_code, 200)
        profile = response.data["data"]
        self.assertEqual(profile["contractVersion"], AUTHORIZATION_CONTRACT_VERSION)
        self.assertEqual(profile["identity"]["employee"]["id"], self.allowed_user.employee_profile.pk)
        self.assertEqual(profile["organization"], {
            "id": self.company.pk,
            "code": self.company.code,
            "name": self.company.name,
        })
        self.assertIn(self.viewer_role.code, profile["roles"])
        self.assertIn(ORGANIZATION_DIRECTORY_VIEW, profile["permissionCodes"])
        self.assertEqual(profile["scopeCodes"], ["DEPARTMENT"])
        self.assertEqual(profile["authoritySource"], "system.UserRoleScopeAssignment")

    def test_v1_decision_api_is_server_authoritative(self):
        allow_response = self.client_for(self.allowed_user).post(
            "/api/access-control/decisions/",
            {
                "actionCode": ORGANIZATION_DIRECTORY_VIEW,
                "organizationId": self.company.pk,
                "businessObject": {"departmentId": self.department.pk},
            },
            format="json",
        )
        deny_response = self.client_for(self.denied_user).post(
            "/api/access-control/decisions/",
            {"actionCode": ORGANIZATION_DIRECTORY_VIEW},
            format="json",
        )
        self.assertTrue(allow_response.data["data"]["allowed"])
        self.assertFalse(deny_response.data["data"]["allowed"])

    def test_v1_read_only_pilot_applies_department_scope_and_zero_purchase_writes(self):
        before = PurchaseOrder.objects.count()
        response = self.client_for(self.allowed_user).get(
            "/api/access-control/organization-directory/"
        )
        after = PurchaseOrder.objects.count()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [row["id"] for row in response.data["data"]["rows"]],
            [self.department.pk],
        )
        self.assertEqual(response.data["data"]["strictFacts"]["businessWriteCount"], 0)
        self.assertEqual(before, after)

    def test_v1_read_only_pilot_rejects_user_without_action(self):
        response = self.client_for(self.denied_user).get(
            "/api/access-control/organization-directory/"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "PERMISSION_DENIED")

    def test_v1_admin_management_writes_only_formal_scope_assignment(self):
        response = self.client_for(self.admin).post(
            "/api/access-control/foundation/",
            {
                "action": "SET_USER_AUTHORITIES",
                "payload": {
                    "userId": self.denied_user.pk,
                    "reason": "组织权限正式范围调整",
                    "authorities": [{
                        "roleCode": self.viewer_role.code,
                        "legalEntityId": str(self.company.pk),
                        "scopeCode": "DEPARTMENT",
                        "departmentId": self.department.pk,
                    }],
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        assignment = UserRoleScopeAssignment.objects.get(user=self.denied_user)
        self.assertEqual(assignment.department_id, self.department.pk)
        self.assertEqual(assignment.scope_code, "DEPARTMENT")

    def test_v1_action_catalog_reuses_system_permission(self):
        response = self.client_for(self.allowed_user).get(
            "/api/access-control/actions/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["registryOwner"], "system.Permission")
        self.assertIn(
            ORGANIZATION_DIRECTORY_VIEW,
            {row["code"] for row in response.data["data"]["actions"]},
        )
