from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from pfm.models import Employee

from .models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    OrganizationUnit,
    Process,
    ProcessTeamCapability,
    Team,
    TeamMembership,
    User,
    Workshop,
)
from .organization_operating import OrganizationOperatingError, OrganizationOperatingService


ALLOW = {
    "allowed": True,
    "decisionCode": "ALLOW",
    "reason": "test",
    "scope": {"codes": ["ALL"], "departmentIds": []},
}


class CompanyNameCorrectionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="COMP001", name="掌去智造科技有限公司", is_active=True,
        )
        self.root_unit = OrganizationUnit.objects.create(
            company=self.company,
            code="COMP-COMP001",
            name=self.company.name,
            unit_type=OrganizationUnit.UnitType.COMPANY,
        )
        self.department = Department.objects.create(
            company=self.company, code="MGC", name="木工车间",
            effective_from=date(2026, 9, 14), effective_to=date(2027, 9, 14),
        )
        self.user = User.objects.create_superuser(
            username="company_correction_admin", password=None, company_id=self.company.pk,
        )

    @patch("system.organization_operating.AuthorizationService.decide", return_value=ALLOW)
    def test_name_correction_preserves_identity_and_records_audit(self, _decide):
        result = OrganizationOperatingService.execute(
            user=self.user,
            action="SAVE_COMPANY_NAME_CORRECTION",
            payload={
                "companyId": self.company.pk,
                "companyCode": "COMP001",
                "expectedCurrentName": "掌去智造科技有限公司",
                "correctedName": "掌云智造科技有限公司",
                "decisionBasis": "用户确认掌去为录入错误，掌去与掌云为同一家公司。",
                "reason": "用户明确纠正公司名称，不改变稳定身份与业务关联。",
            },
        )
        self.company.refresh_from_db()
        self.root_unit.refresh_from_db()
        self.department.refresh_from_db()
        self.assertEqual(self.company.pk, result["target"]["id"])
        self.assertEqual(self.company.code, "COMP001")
        self.assertEqual(self.company.name, "掌云智造科技有限公司")
        self.assertEqual(self.root_unit.name, self.company.name)
        self.assertEqual(self.department.code, "MGC")
        self.assertEqual(self.department.effective_to, date(2027, 9, 14))
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        self.assertEqual(audit.action_code, "SAVE_COMPANY_NAME_CORRECTION")
        self.assertEqual(audit.before_snapshot["company"]["name"], "掌去智造科技有限公司")
        self.assertEqual(audit.after_snapshot["company"]["name"], "掌云智造科技有限公司")

    @patch("system.organization_operating.AuthorizationService.decide", return_value=ALLOW)
    def test_stale_or_cross_company_correction_is_blocked(self, _decide):
        other = Company.objects.create(code="OTHER", name="其他公司")
        for payload in (
            {
                "companyId": other.pk, "companyCode": "OTHER",
                "expectedCurrentName": other.name, "correctedName": "错误写入",
            },
            {
                "companyId": self.company.pk, "companyCode": "COMP001",
                "expectedCurrentName": "过期名称", "correctedName": "错误写入",
            },
        ):
            payload.update(decisionBasis="test", reason="测试阻断")
            with self.assertRaises(OrganizationOperatingError):
                OrganizationOperatingService.execute(
                    user=self.user, action="SAVE_COMPANY_NAME_CORRECTION", payload=payload,
                )


class TeamOperationSeparationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="TEAM-C", name="班组测试公司")
        self.department = Department.objects.create(
            company=self.company, code="MGC", name="木工车间",
        )
        self.workshop = Workshop.objects.create(
            company=self.company, department=self.department, code="WOOD", name="木工",
        )
        self.opening = Process.objects.create(
            company=self.company, workshop=self.workshop, code="CUT", name="开料",
        )
        self.splicing = Process.objects.create(
            company=self.company, workshop=self.workshop, code="SPLICE", name="拼皮",
        )
        self.team_a = Team.objects.create(
            company=self.company, workshop=self.workshop, department=self.department,
            code="WOOD-A", name="木工一班",
        )
        self.team_b = Team.objects.create(
            company=self.company, workshop=self.workshop, department=self.department,
            code="WOOD-B", name="木工二班",
        )

    def test_one_operation_can_have_multiple_teams_and_team_can_have_multiple_operations(self):
        ProcessTeamCapability.objects.create(operation=self.opening, team=self.team_a)
        ProcessTeamCapability.objects.create(operation=self.opening, team=self.team_b)
        ProcessTeamCapability.objects.create(operation=self.splicing, team=self.team_a)
        self.assertEqual(self.opening.team_capabilities.count(), 2)
        self.assertEqual(self.team_a.operation_capabilities.count(), 2)
        self.assertIsNone(self.opening.team_id)

    def test_team_membership_and_period_are_independent_from_employee_department(self):
        employee = Employee.objects.create(
            employee_no="TEAM-E1", full_name="班组成员", department_ref=self.department,
        )
        membership = TeamMembership(
            team=self.team_a, employee=employee,
            effective_from=date(2026, 9, 1), effective_to=date(2026, 12, 31),
        )
        membership.full_clean()
        membership.save()
        self.assertEqual(employee.department_ref_id, self.department.pk)
        self.assertEqual(self.team_a.memberships.count(), 1)

    def test_cross_company_capability_is_rejected(self):
        other = Company.objects.create(code="TEAM-O", name="其他班组公司")
        other_workshop = Workshop.objects.create(company=other, code="OTHER-W", name="其他车间")
        other_team = Team.objects.create(company=other, workshop=other_workshop, code="OTHER-T", name="其他班组")
        relation = ProcessTeamCapability(operation=self.opening, team=other_team)
        with self.assertRaises(ValidationError):
            relation.full_clean()
