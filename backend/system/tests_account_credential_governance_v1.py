from rest_framework.test import APIClient, APITestCase

from pfm.models import Employee

from .models import (
    Company, Department, OrganizationOperatingAuditRecord, Position, Role,
    User, UserRoleScopeAssignment,
)


class AccountCredentialGovernanceV1Tests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(code="LOGIN-GOV", name="账户治理隔离测试公司")
        self.department = Department.objects.create(
            company=self.company, code="LOGIN", name="账户治理部",
        )
        self.position = Position.objects.create(
            company=self.company, department=self.department,
            code="LOGIN-POS", name="账户治理岗",
        )
        self.admin = User.objects.create_user(
            username="login_admin", password="admin-known-secret", real_name="账户管理员",
            company_id=self.company.pk, is_superuser=True, is_staff=True,
        )
        self.user = User.objects.create_user(
            username="login_subject", password="known-secret", real_name="账户本人",
            company_id=self.company.pk,
        )
        self.other = User.objects.create_user(
            username="login_other", password="other-known-secret", real_name="其他账户",
            company_id=self.company.pk,
        )
        self.employee = Employee.objects.create(
            user=self.user, employee_no="LOGIN-001", full_name="账户本人", status="active",
            department_ref=self.department, position_ref=self.position,
        )
        self.role = Role.objects.create(code="login_test_role", name="账户测试角色")
        self.client.force_authenticate(user=self.admin)

    def save_user(self, **overrides):
        payload = {
            "id": self.user.pk,
            "username": self.user.username,
            "realName": "账户本人（资料更新）",
            "employeeId": self.employee.pk,
            "companyId": self.company.pk,
            "isActive": True,
            "password": "",
            "passwordConfirm": "",
            "passwordChangeRequested": False,
            "reason": "隔离回归验证账户写入边界",
        }
        payload.update(overrides)
        return self.client.post(
            "/api/access-control/foundation/",
            {"action": "SAVE_USER", "payload": payload}, format="json",
        )

    def test_profile_update_preserves_all_passwords_and_employee_company_links(self):
        subject_hash = self.user.password
        other_hash = self.other.password
        response = self.save_user()
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(self.user.password, subject_hash)
        self.assertEqual(self.other.password, other_hash)
        self.assertEqual(self.user.company_id, self.company.pk)
        self.assertEqual(self.employee.user_id, self.user.pk)
        audit = OrganizationOperatingAuditRecord.objects.get(action_code="UPDATE_USER")
        self.assertFalse(audit.after_snapshot["passwordChanged"])
        self.assertNotIn("password", audit.before_snapshot)
        self.assertNotIn("password", audit.after_snapshot)

    def test_password_text_without_explicit_intent_is_rejected_without_writes(self):
        subject_hash = self.user.password
        response = self.save_user(password="browser-autofill-secret")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, subject_hash)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_explicit_reset_requires_confirmation_and_changes_only_target(self):
        subject_hash = self.user.password
        other_hash = self.other.password
        mismatch = self.save_user(
            passwordChangeRequested=True, password="new-known-secret",
            passwordConfirm="different-secret",
        )
        self.assertEqual(mismatch.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, subject_hash)

        saved = self.save_user(
            passwordChangeRequested=True, password="new-known-secret",
            passwordConfirm="new-known-secret",
        )
        self.assertEqual(saved.status_code, 200)
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertTrue(self.user.check_password("new-known-secret"))
        self.assertFalse(self.user.check_password("known-secret"))
        self.assertEqual(self.other.password, other_hash)
        self.assertTrue(saved.json()["data"]["result"]["passwordChanged"])
        self.assertEqual(
            saved.json()["data"]["result"]["credentialVerification"],
            "PERSISTED_AND_VERIFIED",
        )

        new_login = APIClient().post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "new-known-secret"},
            format="json",
        )
        self.assertEqual(new_login.status_code, 200)
        old_login = APIClient().post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "known-secret"},
            format="json",
        )
        self.assertEqual(old_login.status_code, 401)

    def test_post_save_credential_verification_failure_rolls_back_every_write(self):
        subject_hash = self.user.password
        subject_name = self.user.real_name
        with self.settings(PASSWORD_HASHERS=[
            "django.contrib.auth.hashers.PBKDF2PasswordHasher",
        ]):
            from unittest.mock import patch
            with patch("system.access_control_views.User.check_password", return_value=False):
                response = self.save_user(
                    realName="不应提交的姓名",
                    passwordChangeRequested=True,
                    password="new-known-secret",
                    passwordConfirm="new-known-secret",
                )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, subject_hash)
        self.assertEqual(self.user.real_name, subject_name)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_non_admin_cannot_reset_another_account(self):
        subject_hash = self.user.password
        self.client.force_authenticate(user=self.other)
        response = self.save_user(
            passwordChangeRequested=True,
            password="new-known-secret",
            passwordConfirm="new-known-secret",
        )
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, subject_hash)

    def test_shared_tab_actor_change_is_reported_before_admin_guard_and_writes_nothing(self):
        subject_hash = self.user.password
        self.client.force_authenticate(user=self.other)
        response = self.save_user(
            expectedActorId=self.admin.pk,
            passwordChangeRequested=True,
            password="must-not-be-written",
            passwordConfirm="must-not-be-written",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "AUTHENTICATED_ACTOR_CHANGED")
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, subject_hash)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_role_assignment_does_not_touch_credentials(self):
        subject_hash = self.user.password
        other_hash = self.other.password
        response = self.client.post(
            "/api/access-control/foundation/",
            {"action": "SET_USER_AUTHORITIES", "payload": {
                "userId": self.user.pk,
                "authorities": [{
                    "roleCode": self.role.code,
                    "legalEntityId": str(self.company.pk),
                    "scopeCode": "ORGANIZATION",
                }],
                "reason": "隔离回归验证角色分配不触碰密码",
            }}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.user.password, subject_hash)
        self.assertEqual(self.other.password, other_hash)
        self.assertTrue(UserRoleScopeAssignment.objects.filter(
            user=self.user, role=self.role, active=True,
        ).exists())

    def test_normal_login_accepts_correct_password_and_rejects_wrong_password(self):
        success = APIClient().post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "known-secret"}, format="json",
        )
        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.json()["user"]["username"], self.user.username)
        wrong = APIClient().post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "wrong-secret"}, format="json",
        )
        self.assertEqual(wrong.status_code, 401)

    def test_logout_terminates_server_session_and_relogin_switches_identity(self):
        browser = APIClient()
        first = browser.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "known-secret"}, format="json",
        )
        self.assertEqual(first.status_code, 200)
        first_token = first.json()["token"]
        current = browser.get(
            "/api/access-control/profile/", HTTP_AUTHORIZATION=f"Bearer {first_token}",
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["data"]["identity"]["username"], self.user.username)

        ended = browser.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(ended.status_code, 200)
        self.assertTrue(ended.json()["success"])
        denied = browser.get("/api/access-control/profile/")
        self.assertIn(denied.status_code, (401, 403))

        second = browser.post(
            "/api/auth/login/",
            {"username": self.other.username, "password": "other-known-secret"}, format="json",
        )
        self.assertEqual(second.status_code, 200)
        second_token = second.json()["token"]
        switched = browser.get(
            "/api/access-control/profile/", HTTP_AUTHORIZATION=f"Bearer {second_token}",
        )
        self.assertEqual(switched.status_code, 200)
        self.assertEqual(switched.json()["data"]["identity"]["username"], self.other.username)

    def test_password_change_invalidates_previously_issued_jwt(self):
        login_response = APIClient().post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "known-secret"}, format="json",
        )
        token = login_response.json()["token"]
        self.assertEqual(APIClient().get(
            "/api/access-control/profile/", HTTP_AUTHORIZATION=f"Bearer {token}",
        ).status_code, 200)
        self.user.set_password("changed-secret")
        self.user.save(update_fields=["password"])
        denied = APIClient().get(
            "/api/access-control/profile/", HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertIn(denied.status_code, (401, 403))
