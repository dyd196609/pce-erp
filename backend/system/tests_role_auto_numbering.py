from rest_framework.test import APIClient, APITestCase

from masterdata.models import CodeRule

from .models import Company, OrganizationOperatingAuditRecord, Role, User


class RoleAutoNumberingTests(APITestCase):
    endpoint = "/api/access-control/foundation/"

    def setUp(self):
        self.company = Company.objects.create(code="AUTO01", name="角色编号隔离公司")
        self.admin = User.objects.create_user(
            username="role_auto_admin", password="isolated-secret", real_name="编号管理员",
            company_id=self.company.pk, is_superuser=True, is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def save(self, payload):
        return self.client.post(self.endpoint, {"action": "SAVE_ROLE", "payload": payload}, format="json")

    def test_create_without_code_allocates_audits_and_is_idempotent(self):
        payload = {"name": "订单生产物料可行性评审", "description": "物料结构、配置能力等"}
        first = self.save(payload)
        self.assertEqual(first.status_code, 200)
        result = first.data["data"]["result"]
        self.assertRegex(result["code"], r"^ROLE-AUTO01-\d{4}$")
        self.assertTrue(result["created"])
        self.assertEqual(Role.objects.filter(name=payload["name"]).count(), 1)
        self.assertEqual(CodeRule.objects.get(company_id=self.company.pk, entity_type="system_role").current_seq, 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code="CREATE_ROLE").count(), 1)

        replay = self.save(payload)
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.data["data"]["result"]["idempotentReplay"])
        self.assertEqual(Role.objects.filter(name=payload["name"]).count(), 1)
        self.assertEqual(CodeRule.objects.get(company_id=self.company.pk, entity_type="system_role").current_seq, 1)

    def test_edit_preserves_existing_code(self):
        role = Role.objects.create(code="BUILTIN-STABLE", name="既有角色")
        response = self.save({"id": role.pk, "code": "SHOULD-NOT-REPLACE", "name": "既有角色更新", "description": "更新说明"})
        self.assertEqual(response.status_code, 200)
        role.refresh_from_db()
        self.assertEqual(role.code, "BUILTIN-STABLE")
