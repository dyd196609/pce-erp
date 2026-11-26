import io

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from payment_request.models import PaymentRequest
from payment_request.views import PaymentRequestListView
from system.models import User
from workflow_runtime.action_permissions import (
    CONTRACT_VERSION,
    MODULE_ACTIONS,
    OBJECT_FACT_SOURCES,
    POLICIES,
    ActionPermissionValidator,
)
from workflow_runtime.views import (
    ActionPermissionContractView,
    ActionPermissionMatrixView,
    ActionPermissionValidationView,
    CanaryActorSessionView,
)


@override_settings(
    PCE_CANARY_DEMO_MODE=True,
    PCE_CANARY_TENANT_ID="tenant-canary-demo",
    PCE_CANARY_BATCH_ID="PURCHASE-FLOW-DEMO-V1",
    PCE_ACTION_PERMISSION_ENFORCED=True,
    PCE_ACTION_PERMISSION_CANARY_AUTH_ENABLED=True,
    PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED=True,
    PCE_PURCHASE_RECONCILIATION_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FEATURE_ENABLED=True,
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED=True,
    PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED=True,
    PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PAYMENT_REQUEST_FEATURE_ENABLED=True,
    PCE_PAYMENT_REQUEST_TEST_TENANTS={"tenant-canary-demo"},
)
class BusinessActionPermissionV552Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        output = io.StringIO()
        call_command("ensure_purchase_canary_formal_domain", stdout=output)
        call_command("ensure_payable_confirmation_prepare_canary", stdout=output)
        call_command("ensure_payment_request_prepare_canary", stdout=output)
        call_command("ensure_payment_request_canary", stdout=output)
        call_command(
            "ensure_business_action_permission_canary_v552", stdout=output
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.viewer = User.objects.get(username="v552-viewer")
        self.operator = User.objects.get(username="v552-operator")
        self.batch_operator = User.objects.get(
            username="v552-batch-operator"
        )
        self.outscope = User.objects.get(username="v552-outscope")
        self.requests = list(PaymentRequest.objects.order_by("request_no")[:2])

    def test_contract_covers_thirteen_modules_and_every_registry_action(self):
        request = self.factory.get(
            "/api/workflow/action-permissions/contract"
        )
        force_authenticate(request, user=self.viewer)
        response = ActionPermissionContractView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(response.data["data"]["moduleCount"], 14)
        self.assertEqual(response.data["data"]["actionCount"], 58)
        self.assertIn("bank-send-preparation", MODULE_ACTIONS)
        self.assertTrue(
            all(
                policy.requiredPermission
                and policy.role
                and policy.organizationScope == "legal_entity"
                and policy.serverValidator
                for policy in POLICIES.values()
            )
        )

    def test_all_thirteen_modules_have_real_server_fact_sources(self):
        self.assertEqual(set(MODULE_ACTIONS), set(OBJECT_FACT_SOURCES))
        for module_code, source in OBJECT_FACT_SOURCES.items():
            app_label, model_name, status_field = source
            model = apps.get_model(app_label, model_name)
            self.assertIsNotNone(model, module_code)
            self.assertIsNotNone(
                model._meta.get_field(status_field),
                f"{module_code}.{status_field}",
            )

    def test_viewer_can_view_server_rows_but_cannot_execute_single_action(self):
        list_request = self.factory.get("/api/finance/payment-requests/")
        force_authenticate(list_request, user=self.viewer)
        list_response = PaymentRequestListView.as_view()(list_request)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["data"]["count"], 8)

        obj = self.requests[0]
        decision = ActionPermissionValidator().evaluate(
            user=self.viewer,
            module_code="payment-request",
            action_code="enter-payment-instruction-prepare",
            object_ids=[obj.pk],
            selection_count=1,
        )
        self.assertFalse(decision["granted"])
        self.assertIn(
            decision["decisionCode"], {"role_denied", "permission_denied"}
        )
        self.assertEqual(decision["currentStateSource"], "server")

    def test_operator_single_action_is_allowed_and_batch_is_server_rejected(self):
        single = self._validate(
            self.operator,
            "enter-payment-instruction-prepare",
            [self.requests[0].pk],
        )
        self.assertEqual(single.status_code, 200)
        self.assertTrue(single.data["data"]["granted"])
        self.assertEqual(
            single.data["data"]["serverFacts"]["statuses"], ["approved"]
        )

        batch = self._validate(
            self.operator,
            "batch-enter-payment-instruction-prepare",
            [obj.pk for obj in self.requests],
        )
        self.assertEqual(batch.status_code, 403)
        self.assertFalse(batch.data["data"]["granted"])
        self.assertIn(
            batch.data["data"]["decisionCode"],
            {"role_denied", "permission_denied"},
        )

    def test_batch_operator_batch_action_is_allowed(self):
        response = self._validate(
            self.batch_operator,
            "batch-enter-payment-instruction-prepare",
            [obj.pk for obj in self.requests],
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["granted"])
        self.assertEqual(
            response.data["data"]["serverFacts"]["statuses"],
            ["approved", "approved"],
        )
        self.assertTrue(
            all(
                evidence["serverDerived"]
                for evidence in response.data["data"]["authorityEvidence"]
            )
        )

    def test_out_of_scope_role_cannot_view_or_execute_object(self):
        list_request = self.factory.get("/api/finance/payment-requests/")
        force_authenticate(list_request, user=self.outscope)
        list_response = PaymentRequestListView.as_view()(list_request)
        self.assertEqual(list_response.data["data"]["count"], 0)

        response = self._validate(
            self.outscope,
            "enter-payment-instruction-prepare",
            [self.requests[0].pk],
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data["data"]["decisionCode"], "role_denied"
        )

    def test_frontend_status_cannot_override_server_business_state(self):
        obj = self.requests[0]
        request = self.factory.post(
            "/api/workflow/action-permissions/validate",
            {
                "moduleCode": "payment-request",
                "actionCode": "enter-payment-instruction-prepare",
                "objectIds": [obj.pk],
                "selectionCount": 1,
                "businessStatus": "draft",
            },
            format="json",
        )
        force_authenticate(request, user=self.operator)
        response = ActionPermissionValidationView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["data"]["serverFacts"]["statuses"], ["approved"]
        )
        self.assertEqual(
            response.data["data"]["currentStateSource"], "server"
        )

    def test_matrix_returns_only_server_granted_permission_codes(self):
        obj = self.requests[0]
        request = self.factory.get(
            "/api/workflow/action-permissions/",
            {
                "moduleCode": "payment-request",
                "objectIds": str(obj.pk),
                "selectionCount": 1,
                "legalEntityId": obj.legal_entity_id,
            },
        )
        force_authenticate(request, user=self.operator)
        response = ActionPermissionMatrixView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        codes = response.data["data"]["grantedPermissionCodes"]
        self.assertIn(
            "pce.action.payment-request.enter-payment-instruction-prepare",
            codes,
        )
        self.assertNotIn(
            "pce.action.payment-request.batch-enter-payment-instruction-prepare",
            codes,
        )
        self.assertFalse(response.data["frontendVisibilityIsAuthority"])

    def test_canary_actor_session_is_server_allowlisted_and_http_only(self):
        request = self.factory.get(
            "/api/workflow/action-permissions/canary-session",
            {"actor": "v552-operator"},
        )
        response = CanaryActorSessionView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies["pce_v552_actor"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(response.data["serverResolved"], True)

    def _validate(self, user, action_code, object_ids):
        request = self.factory.post(
            "/api/workflow/action-permissions/validate",
            {
                "moduleCode": "payment-request",
                "actionCode": action_code,
                "objectIds": object_ids,
                "selectionCount": len(object_ids),
            },
            format="json",
        )
        force_authenticate(request, user=user)
        return ActionPermissionValidationView.as_view()(request)
