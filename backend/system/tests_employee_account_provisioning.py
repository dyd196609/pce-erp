from django.test import TestCase
from rest_framework.test import APIClient

from pfm.models import Employee

from .employee_account_provisioning import provision_missing_management_accounts
from .models import Company, Department, OrganizationOperatingAuditRecord, Position, User, UserRoleScopeAssignment


class EmployeeAccountProvisioningTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="ACCOUNT-NO", name="账户编号隔离测试公司")
        self.admin = User.objects.create_user(
            username="admin", password="unused", real_name="管理员",
            company_id=self.company.pk, is_superuser=True,
        )
        department = Department.objects.create(company=self.company, code="MGT", name="管理部")
        position = Position.objects.create(
            company=self.company, department=department, code="MGT-MGR", name="管理部经理",
        )
        self.employee = Employee.objects.create(
            employee_no="EMP-MGT-001", full_name="待开户经理", status="active",
            department_ref=department, position_ref=position,
        )

    def test_dry_run_then_apply_is_numbered_password_safe_and_idempotent(self):
        preview = provision_missing_management_accounts(
            actor=self.admin, reason="隔离测试", apply=False,
        )
        self.assertEqual(preview["missingAccountCount"], 1)
        self.assertEqual(preview["rows"][0]["username"], "pce_emp_mgt_001")
        self.assertEqual(User.objects.count(), 1)

        applied = provision_missing_management_accounts(
            actor=self.admin, reason="隔离测试", apply=True,
        )
        self.employee.refresh_from_db()
        self.assertEqual(applied["passwordWrites"], 0)
        self.assertEqual(applied["roleAssignmentWrites"], 0)
        self.assertEqual(self.employee.user.username, "pce_emp_mgt_001")
        self.assertFalse(self.employee.user.has_usable_password())
        self.assertEqual(UserRoleScopeAssignment.objects.filter(user=self.employee.user).count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(
            action_code="CREATE_MANAGEMENT_EMPLOYEE_ACCOUNT",
        ).count(), 1)

        replay = provision_missing_management_accounts(
            actor=self.admin, reason="隔离测试重放", apply=True,
        )
        self.assertEqual(replay["created"], [])
        self.assertEqual(User.objects.count(), 2)

    def test_normal_add_user_generates_account_without_client_username_or_password(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        payload = {
            "action": "SAVE_USER",
            "payload": {
                "employeeId": self.employee.pk,
                "companyId": self.company.pk,
                "realName": self.employee.full_name,
                "reason": "隔离验证普通新增账户自动生成",
            },
        }
        response = client.post("/api/access-control/foundation/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        result = response.data["data"]["result"]
        self.assertEqual(result["username"], "pce_emp_mgt_001")
        self.assertEqual(result["credentialState"], "PENDING_SECURE_INITIALIZATION")
        self.assertFalse(result["passwordChanged"])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.user_id, result["id"])
        self.assertFalse(self.employee.user.has_usable_password())

        readback = client.get("/api/access-control/foundation/")
        self.assertEqual(readback.status_code, 200)
        foundation = readback.data["data"]
        employee_row = next(row for row in foundation["employees"] if row["id"] == self.employee.pk)
        user_row = next(row for row in foundation["users"] if row["id"] == result["id"])
        self.assertEqual(employee_row["suggestedUsername"], result["username"])
        self.assertEqual(employee_row["credentialState"], "PENDING_SECURE_INITIALIZATION")
        self.assertEqual(user_row["credentialState"], "PENDING_SECURE_INITIALIZATION")

        replay = client.post("/api/access-control/foundation/", payload, format="json")
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.data["data"]["result"]["id"], result["id"])
        self.assertTrue(replay.data["data"]["result"]["idempotentReplay"])
        self.assertEqual(User.objects.filter(username="pce_emp_mgt_001").count(), 1)

        password_before = self.employee.user.password
        edit = client.post("/api/access-control/foundation/", {
            "action": "SAVE_USER",
            "payload": {
                "id": result["id"],
                "username": result["username"],
                "realName": self.employee.full_name,
                "companyId": self.company.pk,
                "employeeId": self.employee.pk,
                "isActive": True,
                "passwordChangeRequested": False,
                "reason": "隔离验证普通资料编辑不改密码",
            },
        }, format="json")
        self.assertEqual(edit.status_code, 200)
        self.employee.user.refresh_from_db()
        self.assertEqual(self.employee.user.password, password_before)
