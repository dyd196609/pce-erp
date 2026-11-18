import io
import json
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase
from openpyxl import load_workbook
from rest_framework.test import APIClient

from pfm.models import Employee
from sales.models import Customer
from system.models import (
    Company, OrganizationOperatingAuditRecord, PositionResponsibility,
    RolePermission, User, UserRoleScopeAssignment,
)

from .formal_import_actor_context import (
    FormalImportActorContextError,
    bootstrap_rehearsal_actors,
    resolve_formal_import_actor,
)
from .formal_import_service import FormalImportService


class Wave1FormalImportActorContextTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.company = Company.objects.create(code="COMP001", name="Wave1 Actor隔离公司")
        actors = bootstrap_rehearsal_actors(
            company=self.company,
            run_id="ACTOR-TEST",
            maintenance_username="actor_maintenance",
            maintenance_password="test-only",
            readonly_username="actor_readonly",
            readonly_password="test-only",
        )
        self.user = actors["maintenance"]
        self.readonly = actors["readonly"]
        self.employee = Employee.objects.get(user=self.user)
        self.position = self.employee.position_ref
        self.mapping = PositionResponsibility.objects.get(position=self.position)
        self.role = self.position.default_role
        self.client = APIClient()
        self.content = self._customer_xlsx("ACTOR-CUST-001")

    @staticmethod
    def _file(content, name="A3-客户人工导入样例.xlsx"):
        return SimpleUploadedFile(
            name, content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @staticmethod
    def _customer_xlsx(code):
        content = FormalImportService.template_bytes("customers")
        workbook = load_workbook(io.BytesIO(content))
        worksheet = workbook.active
        worksheet.cell(2, 1, code)
        worksheet.cell(2, 2, "Actor Context隔离客户")
        worksheet.cell(2, 3, "是")
        stream = io.BytesIO()
        workbook.save(stream)
        return stream.getvalue()

    def _preview(self, user=None):
        self.client.force_authenticate(user or self.user)
        return self.client.post(
            "/api/pde/formal-import/customers/preview/",
            {"file": self._file(self.content)}, format="multipart",
        )

    def _commit(self, preview, user=None, key="ACTOR-TEST-BATCH"):
        self.client.force_authenticate(user or self.user)
        return self.client.post(
            "/api/pde/formal-import/customers/commit/",
            {
                "file": self._file(self.content),
                "previewFingerprint": preview.data["previewFingerprint"],
                "previewActorBinding": json.dumps(preview.data["previewActorBinding"]),
                "idempotencyKey": key,
                "confirmed": "true",
            },
            format="multipart",
        )

    def test_01_user_only_without_employee_is_denied(self):
        orphan = User.objects.create_user(
            username="actor_orphan", password="test-only",
            real_name="孤立账号", company_id=self.company.pk,
        )
        UserRoleScopeAssignment.objects.create(
            user=orphan, role=self.role, organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            business_hash="actor-orphan",
        )
        preview = self._preview(orphan)
        response = self._commit(preview, orphan)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_EMPLOYEE_REQUIRED")

    def test_02_inactive_employee_is_denied(self):
        self.employee.status = "inactive"
        self.employee.save(update_fields=("status", "updated_at"))
        response = self._commit(self._preview())
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_EMPLOYEE_INACTIVE")

    def test_03_employee_without_position_is_denied(self):
        self.employee.position_ref = None
        self.employee.save(update_fields=("position_ref", "updated_at"))
        response = self._commit(self._preview())
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_POSITION_REQUIRED")

    def test_04_disabled_position_is_denied(self):
        self.position.is_active = False
        self.position.save(update_fields=("is_active",))
        response = self._commit(self._preview())
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_POSITION_DISABLED")

    def test_05_position_outside_effective_term_is_denied(self):
        self.position.effective_to = date.today() - timedelta(days=1)
        self.position.save(update_fields=("effective_to",))
        response = self._commit(self._preview())
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_POSITION_OUT_OF_TERM")

    def test_06_missing_responsibility_is_denied(self):
        self.mapping.delete()
        response = self._commit(self._preview())
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_RESPONSIBILITY_REQUIRED")

    def test_07_expired_responsibility_is_denied(self):
        responsibility = self.mapping.responsibility
        responsibility.effective_to = date.today() - timedelta(days=1)
        responsibility.save(update_fields=("effective_to",))
        response = self._commit(self._preview())
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_RESPONSIBILITY_EXPIRED")

    def test_08_missing_import_permission_is_denied(self):
        RolePermission.objects.filter(
            role=self.role, permission__code="masterdata.customer.maintain",
        ).delete()
        response = self._commit(self._preview())
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_PERMISSION_DENIED")

    def test_09_readonly_can_preview_but_cannot_commit(self):
        preview = self._preview(self.readonly)
        self.assertEqual(preview.status_code, 200)
        response = self._commit(preview, self.readonly)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_PERMISSION_DENIED")

    def test_10_valid_maintenance_actor_can_commit(self):
        preview = self._preview()
        response = self._commit(preview)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(Customer.objects.filter(code="ACTOR-CUST-001").count(), 1)

    def test_11_valid_actor_wrong_organization_is_denied(self):
        other = Company.objects.create(code="OTHER", name="其它隔离公司")
        with self.assertRaises(FormalImportActorContextError) as caught:
            resolve_formal_import_actor(
                user=self.user, organization_id=other.pk,
                action_code="masterdata.customer.maintain",
            )
        self.assertEqual(caught.exception.code, "FORMAL_IMPORT_ACTOR_ORGANIZATION_MISMATCH")

    def test_12_actor_invalidated_after_preview_is_denied(self):
        preview = self._preview()
        self.employee.status = "inactive"
        self.employee.save(update_fields=("status", "updated_at"))
        response = self._commit(preview)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "FORMAL_IMPORT_ACTOR_EMPLOYEE_INACTIVE")
        self.assertEqual(Customer.objects.count(), 0)

    def test_13_import_audit_contains_complete_actor_and_source_context(self):
        preview = self._preview()
        response = self._commit(preview, key="ACTOR-AUDIT-BATCH")
        self.assertEqual(response.status_code, 201)
        audit = OrganizationOperatingAuditRecord.objects.filter(
            action_code="masterdata.customer.maintain"
        ).latest("pk")
        context = audit.after_snapshot["importContext"]
        actor = context["actorContext"]
        self.assertEqual(actor["userId"], self.user.pk)
        self.assertEqual(actor["employeeId"], self.employee.pk)
        self.assertEqual(actor["positionId"], self.position.pk)
        self.assertEqual(actor["responsibilityId"], self.mapping.responsibility_id)
        self.assertEqual(actor["organizationId"], self.company.pk)
        self.assertEqual(context["importRunId"], "ACTOR-AUDIT-BATCH")
        self.assertEqual(context["sourceFile"], "A3-客户人工导入样例.xlsx")
        self.assertEqual(context["objectType"], "customers")
        self.assertEqual(context["previewFingerprint"], preview.data["previewFingerprint"])

    def test_14_preview_actor_identity_change_is_denied(self):
        preview = self._preview()
        self.user.username = "actor_maintenance_changed"
        self.user.save(update_fields=("username", "updated_at"))
        response = self._commit(preview)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "PREVIEW_ACTOR_CONTEXT_CHANGED")
        self.assertEqual(Customer.objects.count(), 0)
