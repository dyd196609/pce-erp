import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from openpyxl import load_workbook

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from pfm.models import Employee
from sales.models import Customer
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment,
)

from .formal_import_service import FORMAL_IMPORT_SCHEMAS


class Wave1FormalImportBackendTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.company = Company.objects.create(code="W1IMP", name="Wave1 Import隔离公司")
        self.department = Department.objects.create(code="MFG", name="制造部", company=self.company)
        self.user = self._user("wave1_importer", ("production.master_data.view", "masterdata.customer.maintain"), with_chain=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _user(self, username, permissions, *, with_chain=False):
        user = User.objects.create_user(username=username, password="test-only", company_id=self.company.pk)
        role = Role.objects.create(code=f"R-{username}", name=f"Role {username}")
        for code in permissions:
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(user=user, role=role, organization=self.company, scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION, business_hash=f"isolated-{username}")
        if with_chain:
            responsibility = Responsibility.objects.create(code=f"RESP-{username}", name="正式主数据导入", status=Responsibility.Status.ACTIVE, is_active=True)
            position = Position.objects.create(code=f"POS-{username}", name=f"Position {username}", company=self.company, department=self.department, default_role=role)
            PositionResponsibility.objects.create(position=position, responsibility=responsibility, is_primary=True, active=True)
            Employee.objects.create(user=user, employee_no=f"E-{username}", full_name=username, department_ref=self.department, position_ref=position, status="active")
        return user

    @staticmethod
    def upload(body, name="customers.csv"):
        return SimpleUploadedFile(name, body.encode("utf-8"), content_type="text/csv")

    def preview(self, body):
        return self.client.post("/api/pde/formal-import/customers/preview/", {"file": self.upload(body)}, format="multipart")

    def commit(self, body, fingerprint, key="BATCH-1"):
        return self.client.post("/api/pde/formal-import/customers/commit/", {
            "file": self.upload(body), "previewFingerprint": fingerprint,
            "idempotencyKey": key, "confirmed": "true",
        }, format="multipart")

    def test_all_nine_wave1_objects_share_a_registered_schema(self):
        self.assertEqual(set(FORMAL_IMPORT_SCHEMAS), {
            "customers", "suppliers", "materials", "products", "workshops",
            "operations", "work-centers", "equipment", "standard-capacities",
        })
        for schema in FORMAL_IMPORT_SCHEMAS.values():
            self.assertTrue(schema["identity"])
            self.assertTrue(any(field["required"] for field in schema["fields"]))

    def test_template_preview_is_read_only_and_reports_structured_errors(self):
        template = self.client.get("/api/pde/formal-import/customers/template/")
        self.assertEqual(template.status_code, 200)
        workbook = load_workbook(io.BytesIO(template.content))
        self.assertEqual(workbook.sheetnames, ["客户／经销商"])
        self.assertEqual([cell.value for cell in workbook.active[1]], ["编码", "名称", "启用状态"])
        self.assertEqual([cell.value for cell in workbook.active[2]], ["请填写编码", "请填写名称", "是"])
        invalid = self.preview("code,name,is_active\nC-1,,maybe\n")
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(invalid.data["canCommit"])
        self.assertEqual(invalid.data["writeCount"], 0)
        self.assertEqual(invalid.data["counts"]["blocked"], 1)
        self.assertIn("rowNumber", invalid.data["errors"][0])
        self.assertIn("suggestedAction", invalid.data["errors"][0])
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_duplicate_and_identity_conflict_are_not_committable(self):
        duplicate = self.preview("code,name,is_active\nC-1,客户一,true\nC-1,客户二,true\n")
        self.assertFalse(duplicate.data["canCommit"])
        self.assertEqual(duplicate.data["counts"]["blocked"], 1)
        Customer.objects.create(company=self.company, code="C-2", name="正式名称")
        conflict = self.preview("code,name,is_active\nC-2,变更名称,true\n")
        self.assertFalse(conflict.data["canCommit"])
        self.assertEqual(conflict.data["counts"]["review"], 1)
        self.assertEqual(conflict.data["errors"][0]["errorType"], "IDENTITY_CONFLICT")

    def test_confirmed_commit_uses_formal_write_audit_and_readback_then_replays(self):
        body = "code,name,is_active\nC-101,隔离导入客户,true\n"
        preview = self.preview(body)
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.data["canCommit"])
        self.assertEqual(Customer.objects.count(), 0)
        committed = self.commit(body, preview.data["previewFingerprint"])
        self.assertEqual(committed.status_code, 201)
        self.assertEqual(committed.data["created"], 1)
        self.assertEqual(committed.data["formalReadbackCount"], 1)
        self.assertEqual(Customer.objects.get().name, "隔离导入客户")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.assertEqual(ExternalIdentity.objects.count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 1)
        replay_preview = self.preview(body)
        self.assertEqual(replay_preview.data["counts"]["match"], 1)
        replay = self.commit(body, replay_preview.data["previewFingerprint"], key="BATCH-2")
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.data["created"], 0)
        self.assertEqual(replay.data["matched"], 1)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)

    def test_commit_rejects_changed_file_missing_confirmation_and_read_only_user(self):
        body = "code,name,is_active\nC-201,客户二〇一,true\n"
        preview = self.preview(body)
        changed = self.commit("code,name,is_active\nC-202,客户二〇二,true\n", preview.data["previewFingerprint"])
        self.assertEqual(changed.status_code, 400)
        self.assertEqual(changed.data["code"], "PREVIEW_FINGERPRINT_MISMATCH")
        unconfirmed = self.client.post("/api/pde/formal-import/customers/commit/", {
            "file": self.upload(body), "previewFingerprint": preview.data["previewFingerprint"],
            "idempotencyKey": "NO-CONFIRM", "confirmed": "false",
        }, format="multipart")
        self.assertEqual(unconfirmed.data["code"], "EXPLICIT_CONFIRMATION_REQUIRED")
        readonly = self._user("wave1_readonly", ("production.master_data.view",))
        self.client.force_authenticate(readonly)
        denied = self.commit(body, preview.data["previewFingerprint"], key="DENIED")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(ExternalIdentity.objects.count(), 0)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 0)

    def test_invalid_second_row_causes_zero_batch_writes(self):
        body = "code,name,is_active\nC-301,合法客户,true\nC-302,,true\n"
        preview = self.preview(body)
        self.assertFalse(preview.data["canCommit"])
        rejected = self.commit(body, preview.data["previewFingerprint"], key="ROLLBACK")
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.data["code"], "IMPORT_NOT_COMMITTABLE")
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)
