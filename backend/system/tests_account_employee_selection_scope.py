from django.test import TestCase
from rest_framework.test import APIClient

from pfm.formal_employee import (
    account_link_employee_queryset,
    formal_employee_queryset,
)
from pfm.models import Employee

from .models import Company, Department, Position, User


class AccountEmployeeSelectionScopeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="ACCOUNT-LINK", name="账户关联测试公司")
        self.admin = User.objects.create_user(
            username="account_link_admin",
            password="unused",
            real_name="账户关联管理员",
            company_id=self.company.pk,
            is_superuser=True,
        )
        self.department = Department.objects.create(
            company=self.company, code="HR", name="人事部",
        )
        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="HR-ADMIN",
            name="行政专员",
        )
        self.complete = Employee.objects.create(
            employee_no="EMP-COMPLETE",
            full_name="完整组织员工",
            status="active",
            department_ref=self.department,
            position_ref=self.position,
        )
        self.emp054 = Employee.objects.create(
            employee_no="EMP054",
            full_name="李婷",
            status="active",
            department_name="人事部",
            position="人事专员",
        )
        self.emp073 = Employee.objects.create(
            employee_no="EMP073",
            full_name="沈涛",
            status="active",
            department_name="人事部",
            position="行政专员",
            position_ref=self.position,
        )
        self.inactive = Employee.objects.create(
            employee_no="EMP-INACTIVE",
            full_name="历史员工",
            status="inactive",
        )
        linked_user = User.objects.create_user(
            username="already_linked",
            password=None,
            real_name="已开户员工",
            company_id=self.company.pk,
        )
        self.linked = Employee.objects.create(
            employee_no="EMP-LINKED",
            full_name="已开户员工",
            status="active",
            department_ref=self.department,
            position_ref=self.position,
            user=linked_user,
        )

    def test_account_link_query_is_archive_based_and_not_formal_candidate_based(self):
        account_link_ids = set(account_link_employee_queryset().values_list("pk", flat=True))
        formal_ids = set(formal_employee_queryset().values_list("pk", flat=True))

        self.assertEqual(
            account_link_ids,
            {self.complete.pk, self.emp054.pk, self.emp073.pk},
        )
        self.assertIn(self.complete.pk, formal_ids)
        self.assertNotIn(self.emp054.pk, formal_ids)
        self.assertNotIn(self.emp073.pk, formal_ids)
        self.assertNotIn(self.inactive.pk, account_link_ids)
        self.assertNotIn(self.linked.pk, account_link_ids)

    def test_foundation_api_separates_visibility_from_save_eligibility(self):
        client = APIClient()
        client.force_authenticate(self.admin)

        response = client.get("/api/access-control/foundation/")

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        rows = {row["employeeNo"]: row for row in data["accountLinkEmployees"]}
        self.assertEqual(
            set(rows),
            {"EMP-COMPLETE", "EMP054", "EMP073"},
        )
        self.assertEqual(
            data["employeeArchiveSummary"]["accountLinkQuerySource"],
            "Employee Archive",
        )
        self.assertFalse(rows["EMP054"]["organizationComplete"])
        self.assertFalse(rows["EMP054"]["accountProvisioningEligible"])
        self.assertEqual(
            rows["EMP054"]["accountProvisioningCode"],
            "ACCOUNT_COMPANY_UNRESOLVED",
        )
        self.assertFalse(rows["EMP073"]["organizationComplete"])
        self.assertTrue(rows["EMP073"]["accountProvisioningEligible"])
        self.assertEqual(
            rows["EMP073"]["accountProvisioningCode"],
            "ACCOUNT_PROVISIONING_READY",
        )
        self.assertNotIn("EMP-LINKED", rows)
        self.assertNotIn("EMP-INACTIVE", rows)

