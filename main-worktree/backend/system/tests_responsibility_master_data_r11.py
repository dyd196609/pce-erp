from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Position,
    PositionResponsibility,
    Responsibility,
    User,
)


class ResponsibilityMasterDataR11RectificationTests(TestCase):
    endpoint = "/api/access-control/enterprise-organization-model/"

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="RM-R11", name="R1.1 隔离测试公司")
        cls.department = Department.objects.create(
            code="RM-R11-DEPT", name="R1.1 测试部门", company=cls.company,
        )
        cls.position = Position.objects.create(
            code="RM-R11-POS", name="R1.1 测试岗位", company=cls.company,
            department=cls.department,
        )
        cls.admin = User.objects.create_superuser(
            username="rm_r11_admin", password=None, company_id=cls.company.pk,
        )
        cls.denied = User.objects.create_user(
            username="rm_r11_denied", password=None, company_id=cls.company.pk,
        )

    def setUp(self):
        self.client = APIClient()

    def _post(self, action, payload, user=None):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.post(
            self.endpoint,
            {"action": action, "payload": {"reason": "R1.1 自动测试维护", **payload}},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )

    def _create_draft(self):
        response = self._post("SAVE_RESPONSIBILITY", {
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "description": "仅存在于事务隔离测试数据库",
            "businessDomain": "PROCUREMENT",
            "status": "DRAFT",
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]["target"]["id"]

    def test_rm_r11_01_catalog_creates_responsibility_independently(self):
        responsibility_id = self._create_draft()
        self.assertTrue(Responsibility.objects.filter(pk=responsibility_id).exists())
        self.assertEqual(PositionResponsibility.objects.count(), 0)

        page = (
            Path(settings.BASE_DIR).parent
            / "frontend/src/meta/pages/AccessControlFoundationPage.vue"
        ).read_text(encoding="utf-8")
        self.assertIn("{key:'responsibilities',label:'责任管理'", page)

    def test_rm_r11_02_position_only_selects_existing_responsibility(self):
        response = self._post("SAVE_POSITION_RESPONSIBILITY", {
            "positionId": self.position.pk,
            "responsibilityId": 999999,
            "isPrimary": True,
            "active": True,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Responsibility.objects.count(), 0)

        responsibility_id = self._create_draft()
        activation = self._post("SAVE_RESPONSIBILITY", {
            "id": responsibility_id,
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "description": "仅存在于事务隔离测试数据库",
            "businessDomain": "PROCUREMENT",
            "status": "ACTIVE",
            "effectiveFrom": "2026-08-17",
        })
        self.assertEqual(activation.status_code, 200, activation.content)
        response = self._post("SAVE_POSITION_RESPONSIBILITY", {
            "positionId": self.position.pk,
            "responsibilityId": responsibility_id,
            "isPrimary": True,
            "active": True,
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(PositionResponsibility.objects.filter(
            position=self.position, responsibility_id=responsibility_id,
        ).exists())

        dialog = (
            Path(settings.BASE_DIR).parent
            / "frontend/src/meta/components/OrganizationOperatingAdminDialog.vue"
        ).read_text(encoding="utf-8")
        position_region = dialog.split(
            '<el-tabs v-else-if="section===\'positions\'"', 1
        )[1].split('<section v-else-if="section===\'responsibilities\'"', 1)[0]
        self.assertNotIn('kind="responsibility"', position_region)
        self.assertNotIn("SAVE_RESPONSIBILITY", position_region)
        self.assertIn("岗位只能从责任目录选择已有责任", position_region)

    def test_rm_r11_03_lifecycle_remains_effective(self):
        responsibility_id = self._create_draft()
        common = {
            "id": responsibility_id,
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "description": "仅存在于事务隔离测试数据库",
            "businessDomain": "PROCUREMENT",
            "effectiveFrom": "2026-08-17",
        }
        for status in ("ACTIVE", "SUSPENDED", "EXPIRED"):
            response = self._post("SAVE_RESPONSIBILITY", {**common, "status": status})
            self.assertEqual(response.status_code, 200, response.content)
        response = self._post("SAVE_RESPONSIBILITY", {**common, "status": "ACTIVE"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"],
            "INVALID_RESPONSIBILITY_STATUS_TRANSITION",
        )

    def test_rm_r11_04_unauthorized_create_returns_403(self):
        response = self._post("SAVE_RESPONSIBILITY", {
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "status": "DRAFT",
        }, user=self.denied)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Responsibility.objects.count(), 0)

    def test_rm_r11_05_audit_is_complete(self):
        responsibility_id = self._create_draft()
        audit = OrganizationOperatingAuditRecord.objects.get(
            action_code="SAVE_RESPONSIBILITY", target_id=responsibility_id,
        )
        self.assertEqual(audit.before_snapshot, {})
        self.assertEqual(audit.after_snapshot["status"], "DRAFT")
        self.assertEqual(audit.actor_id, self.admin.pk)
        self.assertEqual(audit.reason, "R1.1 自动测试维护")
        self.assertIsNotNone(audit.created_at)

    def test_rm_r11_06_refresh_reads_same_server_fact(self):
        responsibility_id = self._create_draft()
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200, response.content)
        refreshed = next(
            row for row in response.json()["data"]["responsibilities"]
            if row["id"] == responsibility_id
        )
        self.assertEqual(refreshed["code"], "PURCHASE_REQUEST_APPROVAL")
        self.assertEqual(refreshed["status"], "DRAFT")
        self.assertEqual(refreshed["businessDomain"], "PROCUREMENT")
