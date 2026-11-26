from django.test import TestCase

from pfm.models import Employee

from .models import Company, Department, OrganizationOperatingAuditRecord, Position, User
from .organization_operating import OrganizationOperatingError, OrganizationOperatingService


class EmployeeArchiveMaintenanceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="EMP-MAINT", name="员工维护测试公司", is_active=True,
        )
        self.admin = User.objects.create_user(
            username="employee_maint_admin",
            password=None,
            real_name="员工维护管理员",
            company_id=self.company.pk,
            is_superuser=True,
        )
        self.department = Department.objects.create(
            company=self.company, code="HR", name="人力行政部", is_active=True,
        )
        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="HR-SPECIALIST",
            name="人事专员",
            is_active=True,
        )

    def test_orphan_archive_employee_can_be_attached_to_current_company(self):
        employee = Employee.objects.create(
            employee_no="EMP-ARCHIVE",
            full_name="历史身份待确认",
            status="active",
            department_name="历史人事部",
            position="历史人事专员",
        )
        count_before = Employee.objects.count()

        result = OrganizationOperatingService.execute(
            user=self.admin,
            action="SAVE_EMPLOYEE",
            payload={
                "id": employee.pk,
                "fullName": employee.full_name,
                "phone": "",
                "status": "active",
                "departmentId": self.department.pk,
                "positionId": self.position.pk,
                "reason": "隔离测试：维护既有历史档案的正式组织关系",
            },
        )

        employee.refresh_from_db()
        self.assertEqual(Employee.objects.count(), count_before)
        self.assertEqual(employee.department_ref_id, self.department.pk)
        self.assertEqual(employee.position_ref_id, self.position.pk)
        self.assertEqual(result["target"]["id"], employee.pk)
        self.assertTrue(
            OrganizationOperatingAuditRecord.objects.filter(
                action_code="SAVE_EMPLOYEE", target_id=employee.pk,
            ).exists()
        )

    def test_existing_other_company_employee_remains_blocked(self):
        other_company = Company.objects.create(
            code="OTHER-COMPANY", name="其他公司", is_active=True,
        )
        other_department = Department.objects.create(
            company=other_company, code="OTHER-HR", name="其他公司人事部",
        )
        other_position = Position.objects.create(
            company=other_company,
            department=other_department,
            code="OTHER-HR-SPECIALIST",
            name="其他公司人事专员",
        )
        employee = Employee.objects.create(
            employee_no="EMP-OTHER",
            full_name="其他公司员工",
            status="active",
            department_ref=other_department,
            position_ref=other_position,
        )

        with self.assertRaises(OrganizationOperatingError) as captured:
            OrganizationOperatingService.execute(
                user=self.admin,
                action="SAVE_EMPLOYEE",
                payload={
                    "id": employee.pk,
                    "fullName": employee.full_name,
                    "status": "active",
                    "departmentId": self.department.pk,
                    "positionId": self.position.pk,
                    "reason": "隔离测试：跨公司维护必须拒绝",
                },
            )

        self.assertEqual(captured.exception.code, "CROSS_COMPANY_WRITE_FORBIDDEN")
        employee.refresh_from_db()
        self.assertEqual(employee.department_ref_id, other_department.pk)
        self.assertEqual(employee.position_ref_id, other_position.pk)

