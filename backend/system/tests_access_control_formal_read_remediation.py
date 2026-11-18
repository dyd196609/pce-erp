from rest_framework.test import APIClient, APITestCase

from .models import (
    Company,
    OrganizationOperatingAuditRecord,
    Permission,
    Role,
    RolePermission,
    User,
)


class AccessControlFormalReadRemediationTests(APITestCase):
    endpoint = "/api/access-control/foundation/"

    def setUp(self):
        self.company = Company.objects.create(
            code="READ-GOV",
            name="组织权限读取隔离测试公司",
            is_active=True,
        )
        self.admin = User.objects.create_user(
            username="formal_read_admin",
            password="isolated-admin-secret",
            real_name="读取管理员",
            company_id=self.company.pk,
            is_superuser=True,
            is_staff=True,
        )
        self.employee_unlinked_admin = self.admin
        self.ordinary_user = User.objects.create_user(
            username="formal_read_ordinary",
            password="isolated-user-secret",
            real_name="普通业务人员",
            company_id=self.company.pk,
        )
        self.permission = Permission.objects.create(
            code="system.formal_read.sample",
            name="正式管理读取测试权限",
            module="SYSTEM",
        )
        self.role = Role.objects.create(
            code="formal_read_role",
            name="正式管理读取测试角色",
        )
        RolePermission.objects.create(role=self.role, permission=self.permission)

    def test_superuser_without_employee_link_reads_formal_foundation(self):
        client = APIClient()
        client.force_authenticate(user=self.employee_unlinked_admin)
        audit_count = OrganizationOperatingAuditRecord.objects.count()

        response = client.get(self.endpoint)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["operatingCompany"]["id"], self.company.pk)
        self.assertIn(
            self.permission.code,
            [row["code"] for row in response.data["data"]["permissions"]],
        )
        self.assertEqual(
            OrganizationOperatingAuditRecord.objects.count(),
            audit_count,
            "formal management reads must remain zero-write",
        )

    def test_non_admin_is_denied_without_business_permission_expansion(self):
        client = APIClient()
        client.force_authenticate(user=self.ordinary_user)
        audit_count = OrganizationOperatingAuditRecord.objects.count()

        response = client.get(self.endpoint)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["error"]["code"],
            "ACCESS_CONTROL_ADMIN_REQUIRED",
        )
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), audit_count)

    def test_unauthenticated_read_is_rejected(self):
        response = APIClient().get(self.endpoint)

        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(response.data["factLoadFacts"]["factLoadStatus"], "read_failed")
        self.assertNotEqual(response.data["factLoadFacts"]["httpStatus"], 200)
