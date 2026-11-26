from django.test import TestCase
from rest_framework.test import APIClient

from pfm.models import Employee, EmployeeReportingRelation

from .models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Position,
    User,
)


class EmployeeReportingRelationClosureV1Tests(TestCase):
    endpoint = "/api/access-control/enterprise-organization-model/"

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="ERR-C1", name="员工汇报闭环公司")
        cls.department = Department.objects.create(
            code="ERR-D1", name="员工汇报闭环部门", company=cls.company
        )
        cls.manager_position = Position.objects.create(
            code="ERR-MGR", name="采购经理", company=cls.company,
            department=cls.department,
        )
        cls.employee_position = Position.objects.create(
            code="ERR-EMP", name="采购员", company=cls.company,
            department=cls.department,
        )
        cls.employee = Employee.objects.create(
            employee_no="ERR-E1", full_name="张三",
            department_ref=cls.department, position_ref=cls.employee_position,
        )
        cls.manager = Employee.objects.create(
            employee_no="ERR-M1", full_name="李四",
            department_ref=cls.department, position_ref=cls.manager_position,
        )
        cls.second_manager = Employee.objects.create(
            employee_no="ERR-M2", full_name="王五",
            department_ref=cls.department, position_ref=cls.manager_position,
        )
        cls.admin = User.objects.create_superuser(
            username="employee_reporting_admin", password=None,
            real_name="员工汇报管理员", company_id=cls.company.pk,
        )
        cls.denied_user = User.objects.create_user(
            username="employee_reporting_denied", password=None,
            real_name="无维护权限用户", company_id=cls.company.pk,
        )

        cls.other_company = Company.objects.create(code="ERR-C2", name="跨公司")
        cls.other_department = Department.objects.create(
            code="ERR-D2", name="跨公司部门", company=cls.other_company
        )
        cls.other_position = Position.objects.create(
            code="ERR-P2", name="跨公司经理", company=cls.other_company,
            department=cls.other_department,
        )
        cls.other_manager = Employee.objects.create(
            employee_no="ERR-X1", full_name="赵六",
            department_ref=cls.other_department, position_ref=cls.other_position,
        )

    def setUp(self):
        self.client = APIClient()

    def _employee_payload(self, employee=None, **overrides):
        employee = employee or self.employee
        payload = {
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "fullName": employee.full_name,
            "departmentId": employee.department_ref_id,
            "positionId": employee.position_ref_id,
            "phone": employee.phone or "",
            "status": employee.status,
            "reason": "H10 员工直属主管维护闭环测试",
        }
        payload.update(overrides)
        return payload

    def _save_employee(self, *, user=None, employee=None, **overrides):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.post(
            self.endpoint,
            {
                "action": "SAVE_EMPLOYEE",
                "payload": self._employee_payload(employee=employee, **overrides),
            },
            format="json",
        )

    def test_t01_normal_direct_manager_save_and_audit_pass(self):
        response = self._save_employee(
            directManagerId=self.manager.pk,
            directManagerEffectiveFrom="2026-08-17",
            directManagerEffectiveTo="2026-12-31",
        )

        self.assertEqual(response.status_code, 200)
        relation = EmployeeReportingRelation.objects.get(
            employee=self.employee,
            relation_type=EmployeeReportingRelation.RelationType.DIRECT,
            active=True,
            is_primary=True,
        )
        self.assertEqual(relation.manager_id, self.manager.pk)
        self.assertEqual(relation.effective_from.isoformat(), "2026-08-17")
        self.assertEqual(relation.effective_to.isoformat(), "2026-12-31")
        audit = OrganizationOperatingAuditRecord.objects.get(
            action_code="SAVE_EMPLOYEE", target_id=str(self.employee.pk)
        )
        self.assertIsNone(audit.before_snapshot["directManager"]["managerId"])
        self.assertEqual(
            audit.after_snapshot["directManager"]["managerId"], self.manager.pk
        )
        self.assertEqual(audit.reason, "H10 员工直属主管维护闭环测试")

    def test_t02_self_manager_is_rejected(self):
        response = self._save_employee(directManagerId=self.employee.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "SELF_MANAGER_FORBIDDEN")
        self.assertFalse(EmployeeReportingRelation.objects.exists())
        self.assertFalse(OrganizationOperatingAuditRecord.objects.exists())

    def test_t03_reporting_cycle_is_rejected(self):
        first = self._save_employee(directManagerId=self.manager.pk)
        self.assertEqual(first.status_code, 200)

        cycle = self._save_employee(
            employee=self.manager, directManagerId=self.employee.pk
        )
        self.assertEqual(cycle.status_code, 400)
        self.assertEqual(
            cycle.json()["error"]["code"], "REPORTING_CYCLE_FORBIDDEN"
        )
        self.assertFalse(
            EmployeeReportingRelation.objects.filter(employee=self.manager).exists()
        )

    def test_t04_user_without_permission_receives_403(self):
        response = self._save_employee(
            user=self.denied_user, directManagerId=self.manager.pk
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(EmployeeReportingRelation.objects.exists())
        self.assertFalse(OrganizationOperatingAuditRecord.objects.exists())

    def test_t05_save_then_server_readback_is_consistent(self):
        saved = self._save_employee(directManagerId=self.second_manager.pk)
        self.assertEqual(saved.status_code, 200)

        self.client.force_authenticate(user=self.admin)
        readback = self.client.get("/api/access-control/foundation/")
        self.assertEqual(readback.status_code, 200)
        employee_row = next(
            row for row in readback.json()["data"]["employees"]
            if row["id"] == self.employee.pk
        )
        self.assertEqual(employee_row["directManagerId"], self.second_manager.pk)
        self.assertEqual(employee_row["directManagerName"], self.second_manager.full_name)
        self.assertEqual(
            employee_row["directManagerDisplay"], "王五（采购经理）"
        )

    def test_t06_cross_company_direct_manager_is_rejected(self):
        response = self._save_employee(directManagerId=self.other_manager.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"], "CROSS_COMPANY_MANAGER_FORBIDDEN"
        )
        self.assertFalse(EmployeeReportingRelation.objects.exists())
        self.assertFalse(OrganizationOperatingAuditRecord.objects.exists())

    def test_t07_existing_direct_manager_is_updated_with_before_after(self):
        EmployeeReportingRelation.objects.create(
            employee=self.employee,
            manager=self.manager,
            relation_type=EmployeeReportingRelation.RelationType.DIRECT,
            is_primary=True,
            active=True,
        )

        response = self._save_employee(directManagerId=self.second_manager.pk)

        self.assertEqual(response.status_code, 200)
        relation = EmployeeReportingRelation.objects.get(employee=self.employee)
        self.assertEqual(relation.manager_id, self.second_manager.pk)
        self.assertEqual(EmployeeReportingRelation.objects.count(), 1)
        audit = OrganizationOperatingAuditRecord.objects.get(action_code="SAVE_EMPLOYEE")
        self.assertEqual(
            audit.before_snapshot["directManager"]["managerId"], self.manager.pk
        )
        self.assertEqual(
            audit.after_snapshot["directManager"]["managerId"], self.second_manager.pk
        )

    def test_t08_clearing_direct_manager_deactivates_relation_and_reads_back(self):
        relation = EmployeeReportingRelation.objects.create(
            employee=self.employee,
            manager=self.manager,
            relation_type=EmployeeReportingRelation.RelationType.DIRECT,
            is_primary=True,
            active=True,
        )

        response = self._save_employee(directManagerId=None)

        self.assertEqual(response.status_code, 200)
        relation.refresh_from_db()
        self.assertFalse(relation.active)
        self.client.force_authenticate(user=self.admin)
        readback = self.client.get("/api/access-control/foundation/")
        employee_row = next(
            row for row in readback.json()["data"]["employees"]
            if row["id"] == self.employee.pk
        )
        self.assertIsNone(employee_row["directManagerId"])
        self.assertEqual(employee_row["directManagerDisplay"], "待维护")
