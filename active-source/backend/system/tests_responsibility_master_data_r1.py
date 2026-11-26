from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import SupplierMaterialPrice
from procurement.models import PurchaseOrder

from .models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Position,
    PositionResponsibility,
    Responsibility,
    User,
)


class ResponsibilityMasterDataR1Tests(TestCase):
    endpoint = "/api/access-control/enterprise-organization-model/"

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="RM-R1", name="责任主数据隔离测试公司")
        cls.department = Department.objects.create(
            code="RM-R1-DEPT", name="责任测试部门", company=cls.company,
        )
        cls.position = Position.objects.create(
            code="RM-R1-POS", name="责任测试岗位", company=cls.company,
            department=cls.department,
        )
        cls.admin = User.objects.create_superuser(
            username="rm_r1_admin", password=None, company_id=cls.company.pk,
        )
        cls.denied_user = User.objects.create_user(
            username="rm_r1_denied", password=None, company_id=cls.company.pk,
        )

    def setUp(self):
        self.client = APIClient()

    def _post(self, payload, *, action="SAVE_RESPONSIBILITY", user=None):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.post(
            self.endpoint,
            {"action": action, "payload": {"reason": "R1 自动测试维护", **payload}},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )

    def _create_draft(self, code="PURCHASE_REQUEST_APPROVAL"):
        response = self._post({
            "code": code,
            "name": "采购申请审批责任",
            "description": "仅存在于事务隔离自动测试数据库",
            "businessDomain": "PROCUREMENT",
            "status": "DRAFT",
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]["target"]["id"]

    def test_rm_r1_01_responsibility_create(self):
        responsibility_id = self._create_draft()
        row = Responsibility.objects.get(pk=responsibility_id)
        self.assertEqual(row.status, Responsibility.Status.DRAFT)
        self.assertFalse(row.is_active)

    def test_rm_r1_02_code_unique(self):
        self._create_draft()
        response = self._post({
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "重复编码责任",
            "status": "DRAFT",
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Responsibility.objects.count(), 1)

    def test_rm_r1_03_lifecycle_transitions(self):
        responsibility_id = self._create_draft()
        common = {
            "id": responsibility_id,
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "description": "仅存在于事务隔离自动测试数据库",
            "businessDomain": "PROCUREMENT",
            "effectiveFrom": "2026-08-17",
        }
        for status in ("ACTIVE", "SUSPENDED", "EXPIRED"):
            response = self._post({**common, "status": status})
            self.assertEqual(response.status_code, 200, response.content)
        response = self._post({**common, "status": "ACTIVE"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"],
            "INVALID_RESPONSIBILITY_STATUS_TRANSITION",
        )

    def test_rm_r1_04_effective_period_validation(self):
        responsibility_id = self._create_draft()
        response = self._post({
            "id": responsibility_id,
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "description": "仅存在于事务隔离自动测试数据库",
            "businessDomain": "PROCUREMENT",
            "status": "ACTIVE",
            "effectiveFrom": "2026-08-18",
            "effectiveTo": "2026-08-17",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_EFFECTIVE_PERIOD")

    def test_rm_r1_05_permission_isolation_returns_403(self):
        response = self._post({
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "status": "DRAFT",
        }, user=self.denied_user)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Responsibility.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_rm_r1_06_audit_before_after(self):
        responsibility_id = self._create_draft()
        response = self._post({
            "id": responsibility_id,
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "description": "仅存在于事务隔离自动测试数据库",
            "businessDomain": "PROCUREMENT",
            "status": "ACTIVE",
            "effectiveFrom": "2026-08-17",
        })
        self.assertEqual(response.status_code, 200, response.content)
        audit = OrganizationOperatingAuditRecord.objects.filter(
            action_code="SAVE_RESPONSIBILITY", target_id=responsibility_id,
        ).order_by("-pk").first()
        self.assertEqual(audit.before_snapshot["status"], "DRAFT")
        self.assertEqual(audit.after_snapshot["status"], "ACTIVE")
        self.assertEqual(audit.actor_id, self.admin.pk)
        self.assertEqual(audit.reason, "R1 自动测试维护")

    def test_rm_r1_07_assignment_and_refresh_readback_with_purchase_protection(self):
        po_before = PurchaseOrder.objects.count()
        price_before = SupplierMaterialPrice.objects.count()
        responsibility_id = self._create_draft()
        activation = self._post({
            "id": responsibility_id,
            "code": "PURCHASE_REQUEST_APPROVAL",
            "name": "采购申请审批责任",
            "description": "仅存在于事务隔离自动测试数据库",
            "businessDomain": "PROCUREMENT",
            "status": "ACTIVE",
            "effectiveFrom": "2026-08-17",
        })
        self.assertEqual(activation.status_code, 200, activation.content)
        response = self._post(
            {
                "positionId": self.position.pk,
                "responsibilityId": responsibility_id,
                "isPrimary": True,
                "active": True,
            },
            action="SAVE_POSITION_RESPONSIBILITY",
        )
        self.assertEqual(response.status_code, 200, response.content)
        mapping = PositionResponsibility.objects.get(
            position=self.position, responsibility_id=responsibility_id,
        )
        self.assertTrue(mapping.is_primary)

        self.client.force_authenticate(user=self.admin)
        payload = self.client.get(self.endpoint).json()["data"]
        refreshed = next(row for row in payload["responsibilities"] if row["id"] == responsibility_id)
        self.assertEqual(refreshed["status"], "ACTIVE")
        self.assertEqual(refreshed["businessDomain"], "PROCUREMENT")
        self.assertEqual(PurchaseOrder.objects.count(), po_before)
        self.assertEqual(SupplierMaterialPrice.objects.count(), price_before)
