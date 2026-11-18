"""No-database tests for the existing account-association range contract."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .organization_operating import (
    OrganizationOperatingError,
    OrganizationOperatingService,
    employee_account_association_context,
)


class EmployeeAccountAssociationContextTests(SimpleTestCase):
    def employee(self, *, company_id=1, linked_user=None, status="active"):
        company = SimpleNamespace(pk=company_id, name=f"公司{company_id}")
        return SimpleNamespace(
            pk=45,
            department_ref=SimpleNamespace(company=company) if company_id else None,
            position_ref=None,
            status=status,
            user_id=linked_user.pk if linked_user else None,
            user=linked_user,
        )

    def test_missing_archive_preserves_not_found_contract(self):
        facts = employee_account_association_context(None, company_id=1)
        self.assertFalse(facts["eligible"])
        self.assertEqual(facts["code"], "OBJECT_NOT_FOUND")
        self.assertEqual(facts["message"], "员工不存在。")

    def test_archive_without_department_remains_visible_with_specific_reason(self):
        facts = employee_account_association_context(self.employee(company_id=None), company_id=1)
        self.assertFalse(facts["eligible"])
        self.assertEqual(facts["code"], "EMPLOYEE_COMPANY_REQUIRED")
        self.assertEqual(facts["currentCompanyId"], 1)
        self.assertIsNone(facts["employeeCompanyId"])
        self.assertIn("正式部门", facts["message"])

    def test_different_formal_company_is_rejected(self):
        facts = employee_account_association_context(self.employee(company_id=2), company_id=1)
        self.assertFalse(facts["eligible"])
        self.assertEqual(facts["code"], "CROSS_COMPANY_WRITE_FORBIDDEN")
        self.assertEqual(facts["currentCompanyId"], 1)
        self.assertEqual(facts["employeeCompanyId"], 2)
        self.assertEqual(facts["employeeCompanyName"], "公司2")

    def test_missing_position_and_inactive_status_do_not_add_association_constraints(self):
        employee = self.employee(status="inactive")
        facts = employee_account_association_context(employee, company_id=1)
        self.assertTrue(facts["eligible"])
        self.assertEqual(facts["code"], "EMPLOYEE_ACCOUNT_ASSOCIATION_READY")
        self.assertIsNone(employee.position_ref)
        self.assertEqual(employee.status, "inactive")

    def test_existing_account_binding_is_projected_without_reassignment(self):
        account = SimpleNamespace(pk=7, username="existing_account", is_active=False)
        employee = self.employee(linked_user=account)
        facts = employee_account_association_context(employee, company_id=1)
        self.assertTrue(facts["eligible"])
        self.assertTrue(facts["hasLinkedAccount"])
        self.assertEqual(facts["linkedUserId"], 7)
        self.assertEqual(facts["linkedUsername"], "existing_account")
        self.assertFalse(facts["linkedUserActive"])
        self.assertIs(employee.user, account)
        self.assertEqual(employee.user_id, 7)

    def test_unbound_archive_is_projected_without_new_account(self):
        employee = self.employee()
        facts = employee_account_association_context(employee, company_id=1)
        self.assertFalse(facts["hasLinkedAccount"])
        self.assertIsNone(facts["linkedUserId"])
        self.assertEqual(facts["linkedUsername"], "")
        self.assertIsNone(facts["linkedUserActive"])
        self.assertIsNone(employee.user)

    def assert_native_scope_rejection(self, employee, expected_code, expected_status):
        actor = SimpleNamespace(company_id=1)
        with patch("system.organization_operating.Employee.objects.select_for_update") as locked:
            locked.return_value.select_related.return_value.filter.return_value.first.return_value = employee
            with patch("system.organization_operating.User.objects.filter") as accounts:
                with self.assertRaises(OrganizationOperatingError) as raised:
                    OrganizationOperatingService._save_employee_account(
                        user=actor,
                        payload={"employeeId": 45, "userId": 10},
                        reason="隔离范围验证",
                    )
                accounts.assert_not_called()
        self.assertEqual(raised.exception.code, expected_code)
        self.assertEqual(raised.exception.http_status, expected_status)
        facts = employee_account_association_context(employee, company_id=1)
        self.assertEqual(raised.exception.message, facts["message"])

    def test_native_action_reuses_missing_archive_reason_before_any_account_write(self):
        self.assert_native_scope_rejection(None, "OBJECT_NOT_FOUND", 400)

    def test_native_action_reuses_missing_company_reason_before_any_account_write(self):
        self.assert_native_scope_rejection(
            self.employee(company_id=None), "EMPLOYEE_COMPANY_REQUIRED", 400,
        )

    def test_native_action_reuses_cross_company_reason_before_any_account_write(self):
        self.assert_native_scope_rejection(
            self.employee(company_id=2), "CROSS_COMPANY_WRITE_FORBIDDEN", 403,
        )
