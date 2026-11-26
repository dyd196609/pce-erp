from django.test import TestCase

from pfm.models import Employee

from .models import Company, Department, JobFamily, JobLevel, OrganizationUnit, Position, User
from .organization_operating import OrganizationOperatingService


class OrganizationAutoNumberingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="AUTONUM", name="组织编号隔离测试公司")
        cls.admin = User.objects.create_superuser(
            username="organization_autonum_admin",
            password=None,
            real_name="组织编号隔离测试管理员",
            company_id=cls.company.pk,
        )

    def execute(self, action, **payload):
        return OrganizationOperatingService.execute(
            user=self.admin,
            action=action,
            payload={"reason": "自动编号隔离验证", **payload},
        )

    def test_create_without_manual_codes_and_edit_preserves_identifiers(self):
        unit_result = self.execute(
            "SAVE_ORGANIZATION_UNIT", name="自动编号组织单元", unitType="CENTER", active=True
        )
        unit = OrganizationUnit.objects.get(pk=unit_result["target"]["id"])
        self.assertRegex(unit.code, r"^OU-AUTONUM-\d{4}$")

        department_result = self.execute(
            "SAVE_DEPARTMENT",
            name="自动编号部门",
            departmentType="FUNCTIONAL",
            organizationUnitId=unit.pk,
            active=True,
        )
        department = Department.objects.get(pk=department_result["target"]["id"])
        self.assertRegex(department.code, r"^DEPT-AUTONUM-\d{4}$")

        family_result = self.execute("SAVE_JOB_FAMILY", name="自动编号岗位族", active=True)
        family = JobFamily.objects.get(pk=family_result["target"]["id"])
        self.assertRegex(family.code, r"^JF-AUTONUM-\d{4}$")

        level_result = self.execute(
            "SAVE_JOB_LEVEL", name="自动编号岗位等级", rank=1, active=True
        )
        level = JobLevel.objects.get(pk=level_result["target"]["id"])
        self.assertRegex(level.code, r"^JL-AUTONUM-\d{4}$")

        position_result = self.execute(
            "SAVE_POSITION",
            name="自动编号岗位",
            departmentId=department.pk,
            jobFamilyId=family.pk,
            jobLevelId=level.pk,
            active=True,
        )
        position = Position.objects.get(pk=position_result["target"]["id"])
        self.assertRegex(position.code, r"^POS-AUTONUM-\d{4}$")

        employee_result = self.execute(
            "SAVE_EMPLOYEE",
            fullName="自动编号员工",
            departmentId=department.pk,
            positionId=position.pk,
            status="active",
        )
        employee = Employee.objects.get(pk=employee_result["target"]["id"])
        self.assertRegex(employee.employee_no, r"^EMP-AUTONUM-\d{4}$")

        original_codes = {
            "unit": unit.code,
            "department": department.code,
            "family": family.code,
            "level": level.code,
            "position": position.code,
            "employee": employee.employee_no,
        }
        self.execute(
            "SAVE_ORGANIZATION_UNIT", id=unit.pk, code="CLIENT-RENUMBER",
            name=unit.name, unitType=unit.unit_type, active=True,
        )
        self.execute(
            "SAVE_DEPARTMENT", departmentId=department.pk, code="CLIENT-RENUMBER",
            name=department.name, departmentType=department.department_type, active=True,
        )
        self.execute(
            "SAVE_JOB_FAMILY", id=family.pk, code="CLIENT-RENUMBER",
            name=family.name, active=True,
        )
        self.execute(
            "SAVE_JOB_LEVEL", id=level.pk, code="CLIENT-RENUMBER",
            name=level.name, rank=level.rank, active=True,
        )
        self.execute(
            "SAVE_POSITION", positionId=position.pk, code="CLIENT-RENUMBER",
            name=position.name, departmentId=department.pk, active=True,
        )
        self.execute(
            "SAVE_EMPLOYEE", employeeId=employee.pk, employeeNo="CLIENT-RENUMBER",
            fullName=employee.full_name, departmentId=department.pk,
            positionId=position.pk, status="active",
        )

        unit.refresh_from_db(); department.refresh_from_db(); family.refresh_from_db()
        level.refresh_from_db(); position.refresh_from_db(); employee.refresh_from_db()
        self.assertEqual(unit.code, original_codes["unit"])
        self.assertEqual(department.code, original_codes["department"])
        self.assertEqual(family.code, original_codes["family"])
        self.assertEqual(level.code, original_codes["level"])
        self.assertEqual(position.code, original_codes["position"])
        self.assertEqual(employee.employee_no, original_codes["employee"])

