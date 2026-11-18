from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from system.models import Company, User


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TabAuthenticationHandoffTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(
            code="TAB-AUTH", name="标签身份衔接隔离公司", is_active=True,
        )
        self.user = User.objects.create_user(
            username="tab-auth-user", password="test-password",
            real_name="标签用户", company_id=self.company.pk,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def issue(self, target="/pde/product-definitions?sourceRecord=11"):
        return self.client.post(
            "/api/auth/tab-handoff/issue/", {"targetPath": target}, format="json",
        )

    def test_authenticated_tab_issues_opaque_code_and_receiving_tab_exchanges_once(self):
        target = "/pde/product-definitions?sourceRecord=11"
        issued = self.issue(target)
        self.assertEqual(issued.status_code, 200)
        code = issued.data["handoffCode"]
        self.assertNotIn(".", code)
        self.assertNotIn(self.user.username, code)

        receiving_tab = APIClient()
        exchanged = receiving_tab.post(
            "/api/auth/tab-handoff/exchange/",
            {"handoffCode": code, "targetPath": target}, format="json",
        )
        self.assertEqual(exchanged.status_code, 200)
        self.assertEqual(exchanged.data["user"]["id"], self.user.pk)
        self.assertEqual(exchanged.data["user"]["company_id"], self.company.pk)
        self.assertTrue(exchanged.data["token"])

        replay = receiving_tab.post(
            "/api/auth/tab-handoff/exchange/",
            {"handoffCode": code, "targetPath": target}, format="json",
        )
        self.assertEqual(replay.status_code, 401)

    def test_code_is_bound_to_exact_internal_target(self):
        issued = self.issue("/sales/orders")
        exchanged = APIClient().post(
            "/api/auth/tab-handoff/exchange/",
            {"handoffCode": issued.data["handoffCode"], "targetPath": "/pde/product-definitions"},
            format="json",
        )
        self.assertEqual(exchanged.status_code, 401)

    def test_external_or_protocol_relative_target_is_rejected(self):
        for target in ("https://example.com", "//example.com", "javascript:alert(1)"):
            response = self.issue(target)
            self.assertEqual(response.status_code, 400)

    def test_unauthenticated_tab_cannot_issue(self):
        response = APIClient().post(
            "/api/auth/tab-handoff/issue/", {"targetPath": "/pde/product-definitions"}, format="json",
        )
        self.assertEqual(response.status_code, 401)
