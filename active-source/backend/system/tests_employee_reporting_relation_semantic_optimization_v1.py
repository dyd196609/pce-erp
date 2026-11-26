from pathlib import Path

from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import SupplierMaterialPrice
from pfm.models import Employee
from procurement.models import PurchaseOrder

from .models import Company, Department, Position, User


class EmployeeReportingRelationSemanticOptimizationV1Tests(TestCase):
    endpoint = "/api/access-control/enterprise-organization-model/"
    source_root = Path(__file__).resolve().parents[2]
    page_files = (
        source_root / "frontend/src/meta/components/OrganizationOperatingAdminDialog.vue",
        source_root / "frontend/src/meta/pages/AccessControlFoundationPage.vue",
        source_root / "frontend/src/meta/components/EnterpriseOrganizationModelView.vue",
    )

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="ERR-UX", name="汇报关系语义验收公司")
        cls.department = Department.objects.create(
            code="ERR-UX-D", name="采购部", company=cls.company
        )
        cls.employee_position = Position.objects.create(
            code="ERR-UX-E", name="采购员", company=cls.company,
            department=cls.department,
        )
        cls.direct_position = Position.objects.create(
            code="ERR-UX-DM", name="采购经理", company=cls.company,
            department=cls.department,
        )
        cls.functional_position = Position.objects.create(
            code="ERR-UX-FM", name="供应链总监", company=cls.company,
            department=cls.department,
        )
        cls.employee = Employee.objects.create(
            employee_no="EMP001", full_name="张三",
            department_ref=cls.department, position_ref=cls.employee_position,
        )
        cls.direct_manager = Employee.objects.create(
            employee_no="EMP006", full_name="李四",
            department_ref=cls.department, position_ref=cls.direct_position,
        )
        cls.functional_manager = Employee.objects.create(
            employee_no="EMP008", full_name="王五",
            department_ref=cls.department, position_ref=cls.functional_position,
        )
        cls.admin = User.objects.create_superuser(
            username="reporting_semantic_admin", password=None,
            real_name="汇报关系语义管理员", company_id=cls.company.pk,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _source(self, path):
        return path.read_text(encoding="utf-8")

    def _save_relation(self, relation_type, manager):
        return self.client.post(
            self.endpoint,
            {
                "action": "SAVE_REPORTING_RELATION",
                "payload": {
                    "employeeId": self.employee.pk,
                    "managerId": manager.pk,
                    "relationType": relation_type,
                    "active": True,
                    "reason": "员工汇报关系中文语义验收",
                },
            },
            format="json",
        )

    def _employee_readback(self):
        response = self.client.get("/api/access-control/foundation/")
        self.assertEqual(response.status_code, 200)
        return next(
            row for row in response.json()["data"]["employees"]
            if row["id"] == self.employee.pk
        )

    def test_t01_ambiguous_or_parenthesized_english_labels_do_not_exist(self):
        for page_file in self.page_files:
            source = self._source(page_file)
            self.assertNotIn('label="主管"', source)
            self.assertNotIn('label="直属/职能主管"', source)
            self.assertNotIn("Direct Manager", source)
            self.assertNotIn("Functional Manager", source)

    def test_t02_chinese_labels_explanations_and_employee_option_format_exist(self):
        editor = self._source(self.page_files[0])
        model_view = self._source(self.page_files[2])
        self.assertIn('label="直属主管"', editor)
        self.assertIn('label="职能主管"', editor)
        self.assertIn("员工日常汇报对象，负责日常工作安排和管理。", editor)
        self.assertIn("员工专业领域负责人，负责专业指导和业务规范管理。", editor)
        self.assertIn("`${row.fullName}（${row.positionName||'岗位待维护'}）· ${row.employeeNo}`", editor)
        self.assertIn("直属主管：{{ employee.directManagerDisplay }}", model_view)
        self.assertIn("职能主管：{{ employee.functionalManagerDisplay }}", model_view)

    def test_t03_direct_manager_save_and_readback(self):
        response = self._save_relation("DIRECT", self.direct_manager)
        self.assertEqual(response.status_code, 200)
        employee = self._employee_readback()
        self.assertEqual(employee["directManagerId"], self.direct_manager.pk)
        self.assertEqual(employee["directManagerDisplay"], "李四（采购经理）")

    def test_t04_functional_manager_save_and_readback(self):
        response = self._save_relation("FUNCTIONAL", self.functional_manager)
        self.assertEqual(response.status_code, 200)
        employee = self._employee_readback()
        self.assertEqual(employee["functionalManagerId"], self.functional_manager.pk)
        self.assertEqual(employee["functionalManagerDisplay"], "王五（供应链总监）")

    def test_t05_reporting_relation_writes_do_not_change_procurement_counts(self):
        purchase_order_before = PurchaseOrder.objects.count()
        supplier_price_before = SupplierMaterialPrice.objects.count()

        self.assertEqual(self._save_relation("DIRECT", self.direct_manager).status_code, 200)
        self.assertEqual(
            self._save_relation("FUNCTIONAL", self.functional_manager).status_code, 200
        )

        self.assertEqual(PurchaseOrder.objects.count(), purchase_order_before)
        self.assertEqual(SupplierMaterialPrice.objects.count(), supplier_price_before)
