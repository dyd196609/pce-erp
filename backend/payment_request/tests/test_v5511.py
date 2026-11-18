import io

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from payment_instruction_prepare.models import PaymentInstructionPrepare
from payment_request.models import PaymentRequest
from payment_request.views import EligibilityView, PaymentRequestListView


@override_settings(
    PCE_CANARY_DEMO_MODE=True,
    PCE_CANARY_TENANT_ID="tenant-canary-demo",
    PCE_CANARY_BATCH_ID="PURCHASE-FLOW-DEMO-V1",
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
    PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PAYMENT_REQUEST_FEATURE_ENABLED=True,
    PCE_PAYMENT_REQUEST_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PAYMENT_REQUEST_TEST_TENANTS={"tenant-canary-demo"},
)
class PaymentRequestRealDataAcceptanceV5511Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        output = io.StringIO()
        call_command("ensure_purchase_canary_formal_domain", stdout=output)
        call_command("ensure_payable_confirmation_prepare_canary", stdout=output)
        call_command("ensure_payment_request_prepare_canary", stdout=output)
        call_command("ensure_payment_request_canary", stdout=output)

    def test_server_list_returns_eight_approved_formal_objects(self):
        response = PaymentRequestListView.as_view()(
            APIRequestFactory().get("/api/finance/payment-requests/")
        )
        rows = response.data["data"]["results"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["currentStateSource"], "server")
        self.assertEqual(response.data["sourceDocumentType"], "paymentRequestPrepare")
        self.assertEqual(response.data["data"]["count"], 8)
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["status"] == "approved" for row in rows))
        self.assertTrue(all(
            row["sourcePaymentRequestPrepareNo"].startswith("PRP")
            for row in rows
        ))

    def test_single_and_batch_sources_are_server_eligible(self):
        factory = APIRequestFactory()
        requests = list(PaymentRequest.objects.order_by("request_no")[:2])
        self.assertEqual(len(requests), 2)
        for obj in requests:
            response = EligibilityView.as_view()(
                factory.get(
                    f"/api/finance/payment-requests/{obj.pk}/"
                    "payment-instruction-prepare-eligibility"
                ),
                request_id=obj.pk,
            )
            eligibility = response.data["data"]
            self.assertEqual(response.status_code, 200)
            self.assertTrue(eligibility["serverDerived"])
            self.assertTrue(eligibility["eligible"])
            self.assertEqual(
                eligibility["nextStepReadiness"],
                "ready_for_payment_instruction_prepare",
            )

    def test_navigation_acceptance_creates_no_instruction_prepare(self):
        self.assertEqual(PaymentInstructionPrepare.objects.count(), 0)
