import io
import json
from unittest.mock import patch

from django.test import TestCase
from openpyxl import load_workbook
from rest_framework.test import APIClient

from pfm.models import Employee

from .models import Company, Department, OrganizationOperatingAuditRecord, Position, User
from .organization_import_service import OrganizationImportError, OrganizationImportService
from .organization_operating import OrganizationOperatingError, OrganizationOperatingService


class NamedBytesIO(io.BytesIO):
    def __init__(self, content, name):
        super().__init__(content)
        self.name = name
        self.content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class OrganizationImportV1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="ORG-IMP", name="组织导入隔离公司")
        cls.other_company = Company.objects.create(code="ORG-OTHER", name="其他隔离公司")
        cls.admin = User.objects.create_superuser(username="org_import_admin", password=None, real_name="导入管理员", company_id=cls.company.pk)
        cls.readonly = User.objects.create_user(username="org_import_readonly", password=None, real_name="只读人员", company_id=cls.company.pk)

    def setUp(self):
        self.client = APIClient()

    def workbook(self, entity, rows):
        content = OrganizationImportService.template_bytes(entity, user=self.admin)
        workbook = load_workbook(io.BytesIO(content))
        sheet = workbook[OrganizationImportService.schema(entity)["sheet"]]
        for row in rows:
            sheet.append(row)
        stream = io.BytesIO(); workbook.save(stream)
        return stream.getvalue()

    def preview(self, entity, content):
        result, _ = OrganizationImportService.preview(entity, uploaded_file=NamedBytesIO(content, f"{entity}.xlsx"), user=self.admin)
        return result

    def commit(self, entity, content, preview):
        return OrganizationImportService.commit(
            entity, uploaded_file=NamedBytesIO(content, f"{entity}.xlsx"), user=self.admin,
            preview_fingerprint=preview["previewFingerprint"], preview_actor_binding=preview["previewActorBinding"],
            idempotency_key=f"test-{entity}",
        )

    def test_templates_have_blank_input_and_separate_instructions(self):
        for entity in ("departments", "positions", "employees"):
            workbook = load_workbook(io.BytesIO(OrganizationImportService.template_bytes(entity, user=self.admin)), data_only=False)
            self.assertEqual(set(workbook.sheetnames), {OrganizationImportService.schema(entity)["sheet"], "填写说明", "引用资料"})
            input_sheet = workbook[OrganizationImportService.schema(entity)["sheet"]]
            self.assertEqual(input_sheet.max_row, 1)
            self.assertEqual(workbook["填写说明"]["B1"].value, OrganizationImportService.VERSION)
            self.assertEqual(workbook["引用资料"]["B2"].value, self.company.code)

    def test_department_position_employee_chain_and_replay(self):
        department_file = self.workbook("departments", [["IMP-DEPT", "导入部门", self.company.code, "生产部门", "", "", "", "2026-09-14", "", "启用"]])
        department_preview = self.preview("departments", department_file)
        self.assertTrue(department_preview["canCommit"])
        self.assertEqual(self.commit("departments", department_file, department_preview)["created"], 1)

        position_file = self.workbook("positions", [["IMP-POS", "隔离导入岗位", self.company.code, "IMP-DEPT", "", "", "", "", "", "", "2026-09-14", "", "启用"]])
        position_preview = self.preview("positions", position_file)
        self.assertTrue(position_preview["canCommit"])
        self.assertEqual(self.commit("positions", position_file, position_preview)["created"], 1)

        employee_file = self.workbook("employees", [["IMP-EMP", "隔离导入员工", self.company.code, "IMP-DEPT", "IMP-POS", "在职", "", "", "", ""]])
        employee_preview = self.preview("employees", employee_file)
        self.assertTrue(employee_preview["canCommit"])
        self.assertEqual(self.commit("employees", employee_file, employee_preview)["created"], 1)
        employee = Employee.objects.get(employee_no="IMP-EMP")
        self.assertIsNone(employee.user_id)
        self.assertEqual(employee.position_ref.code, "IMP-POS")
        replay = self.preview("employees", employee_file)
        self.assertEqual(replay["counts"]["create"], 0)
        self.assertEqual(replay["counts"]["match"], 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(target_label__icontains="IMP-").count(), 3)

    def test_file_duplicates_invalid_reference_cycle_and_cross_scope_are_blocked(self):
        duplicate = self.workbook("departments", [
            ["DUP", "重复一", self.company.code, "职能部门", "", "", "", "", "", "启用"],
            ["DUP", "重复二", self.company.code, "职能部门", "", "", "", "", "", "启用"],
        ])
        self.assertFalse(self.preview("departments", duplicate)["canCommit"])
        cycle = self.workbook("departments", [
            ["C-A", "循环A", self.company.code, "职能部门", "C-B", "", "", "", "", "启用"],
            ["C-B", "循环B", self.company.code, "职能部门", "C-A", "", "", "", "", "启用"],
        ])
        self.assertTrue(any(error["errorType"] == "HIERARCHY_CYCLE" for error in self.preview("departments", cycle)["errors"]))
        invalid = self.workbook("employees", [["BAD-E", "错误员工", self.company.code, "NO-DEPT", "NO-POS", "在职", "", "", "", ""]])
        self.assertFalse(self.preview("employees", invalid)["canCommit"])
        cross = self.workbook("departments", [["CROSS", "跨公司部门", self.other_company.code, "职能部门", "", "", "", "", "", "启用"]])
        self.assertFalse(self.preview("departments", cross)["canCommit"])

    def test_same_file_parent_child_are_written_in_dependency_order(self):
        content = self.workbook("departments", [
            ["TREE-CHILD", "树形子部门", self.company.code, "职能部门", "TREE-PARENT", "", "", "", "", "启用"],
            ["TREE-PARENT", "树形上级部门", self.company.code, "职能部门", "", "", "", "", "", "启用"],
        ])
        preview = self.preview("departments", content)
        self.assertTrue(preview["canCommit"])
        result = self.commit("departments", content, preview)
        self.assertEqual(result["created"], 2)
        self.assertEqual(Department.objects.get(code="TREE-CHILD").parent.code, "TREE-PARENT")

    def test_confirmed_batch_rolls_back_when_second_canonical_write_fails(self):
        content = self.workbook("departments", [
            ["ROLL-1", "回滚一", self.company.code, "职能部门", "", "", "", "", "", "启用"],
            ["ROLL-2", "回滚二", self.company.code, "职能部门", "", "", "", "", "", "启用"],
        ])
        preview = self.preview("departments", content)
        original = OrganizationOperatingService.execute
        calls = {"count": 0}
        def fail_second(**kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise OrganizationOperatingError("INJECTED_FAILURE", "隔离测试注入失败")
            return original(**kwargs)
        with patch("system.organization_import_service.OrganizationOperatingService.execute", side_effect=fail_second):
            with self.assertRaises(OrganizationImportError):
                self.commit("departments", content, preview)
        self.assertFalse(Department.objects.filter(code__startswith="ROLL-").exists())

    def test_readonly_account_cannot_download_preview_or_commit(self):
        self.client.force_authenticate(user=self.readonly)
        for suffix, method in (("template/", self.client.get), ("preview/", self.client.post), ("commit/", self.client.post)):
            response = method(f"/api/access-control/organization-import/departments/{suffix}")
            self.assertEqual(response.status_code, 403)
