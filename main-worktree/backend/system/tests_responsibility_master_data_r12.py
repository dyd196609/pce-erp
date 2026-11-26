from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    Company,
    Department,
    Permission,
    Position,
    PositionResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)


class ResponsibilityMasterDataR12RectificationTests(TestCase):
    catalog_endpoint = "/api/access-control/responsibilities/"
    operating_endpoint = "/api/access-control/enterprise-organization-model/"

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="RM-R12", name="R1.2 隔离测试公司")
        cls.department = Department.objects.create(
            code="RM-R12-DEPT", name="R1.2 测试部门", company=cls.company,
        )
        cls.position = Position.objects.create(
            code="RM-R12-POS", name="采购经理", company=cls.company,
            department=cls.department,
        )
        cls.admin = User.objects.create_superuser(
            username="rm_r12_admin", password=None, real_name="R1.2 管理员",
            company_id=cls.company.pk,
        )
        cls.denied = User.objects.create_user(
            username="rm_r12_denied", password=None, company_id=cls.company.pk,
        )
        cls.permission, _ = Permission.objects.get_or_create(
            code="system.organization.responsibility.manage",
            defaults={"name": "岗位职责维护", "module": "SYSTEM"},
        )
        cls.manager_role = Role.objects.create(
            code="RM_R12_RESPONSIBILITY_MANAGER", name="R1.2 责任管理员",
        )
        RolePermission.objects.create(
            role=cls.manager_role, permission=cls.permission,
        )
        cls.manager = User.objects.create_user(
            username="rm_r12_manager", password=None, company_id=cls.company.pk,
        )
        UserRoleScopeAssignment.objects.create(
            user=cls.manager, role=cls.manager_role, organization=cls.company,
            scope_code="ORGANIZATION", active=True,
            business_hash="rm-r12-responsibility-manager",
        )

    def setUp(self):
        self.client = APIClient()

    def _post(self, action, payload, user=None):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.post(
            self.operating_endpoint,
            {"action": action, "payload": {"reason": "R1.2 自动测试维护", **payload}},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )

    def _catalog(self, params=None, user=None):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.get(self.catalog_endpoint, params or {})

    def _create_draft(self, code="PURCHASE_REQUEST_APPROVAL", name="采购申请审批责任"):
        response = self._post("SAVE_RESPONSIBILITY", {
            "code": code,
            "name": name,
            "description": "仅存在于事务隔离测试数据库",
            "businessDomain": "PROCUREMENT",
            "status": "DRAFT",
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]["target"]["id"]

    def _activate(self, responsibility_id, code="PURCHASE_REQUEST_APPROVAL", name="采购申请审批责任"):
        response = self._post("SAVE_RESPONSIBILITY", {
            "id": responsibility_id,
            "code": code,
            "name": name,
            "description": "仅存在于事务隔离测试数据库",
            "businessDomain": "PROCUREMENT",
            "status": "ACTIVE",
            "effectiveFrom": "2026-08-17",
        })
        self.assertEqual(response.status_code, 200, response.content)

    def test_rm_r12_01_position_selector_source_is_responsibility_api(self):
        first_id = self._create_draft()
        second_id = self._create_draft(
            "SUPPLIER_MASTER_REVIEW", "供应商主数据审核责任"
        )
        self._activate(first_id)
        self._post("SAVE_POSITION_RESPONSIBILITY", {
            "positionId": self.position.pk,
            "responsibilityId": first_id,
            "isPrimary": True,
            "active": True,
        })
        response = self._catalog()
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["factSource"], "system.Responsibility")
        self.assertEqual(
            {row["id"] for row in data["items"]}, {first_id, second_id}
        )
        self.assertEqual(len(data["items"]), Responsibility.objects.count())

        dialog = (
            Path(settings.BASE_DIR).parent
            / "frontend/src/meta/components/OrganizationOperatingAdminDialog.vue"
        ).read_text(encoding="utf-8")
        self.assertIn('v-for="row in responsibilityOptions"', dialog)
        self.assertIn("Responsibility API · system.Responsibility", dialog)

    def test_rm_r12_02_position_cannot_create_responsibility(self):
        response = self._post("SAVE_POSITION_RESPONSIBILITY", {
            "positionId": self.position.pk,
            "responsibilityId": 999999,
            "isPrimary": True,
            "active": True,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Responsibility.objects.count(), 0)
        self.assertEqual(PositionResponsibility.objects.count(), 0)

        dialog = (
            Path(settings.BASE_DIR).parent
            / "frontend/src/meta/components/OrganizationOperatingAdminDialog.vue"
        ).read_text(encoding="utf-8")
        position_region = dialog.split(
            '<el-tabs v-else-if="section===\'positions\'"', 1
        )[1].split('<section v-else-if="section===\'responsibilities\'"', 1)[0]
        self.assertNotIn("SAVE_RESPONSIBILITY", position_region)
        self.assertNotIn('kind="responsibility"', position_region)

    def test_rm_r12_03_responsibility_detail_reads_base_lifecycle_relationship_and_audit(self):
        responsibility_id = self._create_draft()
        self._activate(responsibility_id)
        mapping_response = self._post("SAVE_POSITION_RESPONSIBILITY", {
            "positionId": self.position.pk,
            "responsibilityId": responsibility_id,
            "isPrimary": True,
            "active": True,
        })
        self.assertEqual(mapping_response.status_code, 200, mapping_response.content)

        response = self._catalog({"id": responsibility_id})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        item = data["item"]
        self.assertEqual(data["factSource"], "system.Responsibility")
        self.assertEqual(data["relationshipSource"], "system.PositionResponsibility")
        self.assertEqual(
            data["auditSource"], "system.OrganizationOperatingAuditRecord"
        )
        self.assertEqual(item["code"], "PURCHASE_REQUEST_APPROVAL")
        self.assertEqual(item["businessDomain"], "PROCUREMENT")
        self.assertEqual(item["status"], "ACTIVE")
        self.assertEqual(item["positionCount"], 1)
        self.assertEqual(item["positions"][0]["positionName"], "采购经理")
        self.assertEqual(item["positions"][0]["responsibilityType"], "PRIMARY")
        self.assertEqual(item["audit"]["createdBy"], "R1.2 管理员")
        self.assertEqual(item["audit"]["reason"], "R1.2 自动测试维护")
        self.assertTrue(item["audit"]["createdTime"])

    def test_rm_r12_04_list_fields_are_complete_and_concise(self):
        self._create_draft()
        item = self._catalog().json()["data"]["items"][0]
        required = {
            "id", "code", "name", "businessDomain", "status", "statusLabel",
            "effectiveFrom", "effectiveTo", "positionCount", "lastModifiedAt",
        }
        self.assertTrue(required.issubset(item.keys()))
        self.assertNotIn("before", item)
        self.assertNotIn("after", item)
        self.assertNotIn("audit", item)

    def test_rm_r12_05_refresh_reads_identical_server_fact(self):
        responsibility_id = self._create_draft()
        first = self._catalog().json()["data"]
        second = self._catalog().json()["data"]
        self.assertEqual(first["factSource"], "system.Responsibility")
        self.assertEqual(first["items"], second["items"])
        self.assertEqual(first["items"][0]["id"], responsibility_id)

    def test_rm_r12_06_unauthorized_write_returns_403(self):
        response = self._post("SAVE_RESPONSIBILITY", {
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "status": "DRAFT",
        }, user=self.denied)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Responsibility.objects.count(), 0)

    def test_rm_r12_07_non_superuser_manager_reads_scoped_assignment_positions(self):
        other_company = Company.objects.create(
            code="RM-R12-OTHER", name="R1.2 其他公司",
        )
        other_department = Department.objects.create(
            code="RM-R12-OTHER-DEPT", name="R1.2 其他部门",
            company=other_company,
        )
        other_position = Position.objects.create(
            code="RM-R12-OTHER-POS", name="R1.2 其他岗位",
            company=other_company, department=other_department,
        )

        response = self._catalog(
            {"assignmentContext": "1"}, user=self.manager,
        )
        self.assertEqual(response.status_code, 200, response.content)
        context = response.json()["data"]["assignmentContext"]
        self.assertEqual(context["factSource"], "system.Position")
        self.assertEqual(
            context["relationshipSource"], "system.PositionResponsibility",
        )
        self.assertEqual(context["companyId"], self.company.pk)
        self.assertEqual(
            [row["id"] for row in context["positions"]], [self.position.pk],
        )
        self.assertNotIn(
            other_position.pk, {row["id"] for row in context["positions"]},
        )
