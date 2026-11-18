from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import BusinessStateTransitionError

from supplier_performance.models import (
    BuyerPerformanceMetric,
    SupplierPayableConfirmation,
    SupplierPaymentRequest,
)
from supplier_performance.services import (
    ensure_v83_demo_data,
    transition_payable_confirmation,
    transition_payment_request,
)


class SupplierPayablePaymentRequestV83Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="v83-test", real_name="V83 Test", company_id=1,
        )
        ensure_v83_demo_data(self.user)
        self.client = APIClient()

    def test_payable_count(self):
        self.assertEqual(SupplierPayableConfirmation.objects.count(), 4)

    def test_payment_request_count(self):
        self.assertEqual(SupplierPaymentRequest.objects.count(), 3)

    def test_payable_status_distribution(self):
        self.assertEqual(
            list(SupplierPayableConfirmation.objects.values_list("status", flat=True)).count(
                "ready_for_payment_request"
            ), 3,
        )

    def test_payment_request_status_distribution(self):
        self.assertEqual(
            set(SupplierPaymentRequest.objects.values_list("status", flat=True)),
            {"submitted", "approved", "payment_pending"},
        )

    def test_payable_state_history(self):
        obj = SupplierPayableConfirmation.objects.filter(status="ready_for_payment_request").first()
        self.assertEqual(BusinessStateTransition.objects.filter(
            object_type="SupplierPayableConfirmation", object_id=obj.pk
        ).count(), 3)

    def test_request_state_history(self):
        obj = SupplierPaymentRequest.objects.get(status="payment_pending")
        self.assertEqual(BusinessStateTransition.objects.filter(
            object_type="SupplierPaymentRequest", object_id=obj.pk
        ).count(), 3)

    def test_payable_direct_status_write_blocked(self):
        obj = SupplierPayableConfirmation.objects.get(status="internal_review")
        obj.status = "ready_for_payment_request"
        with self.assertRaises(ValidationError):
            obj.save()

    def test_request_direct_status_write_blocked(self):
        obj = SupplierPaymentRequest.objects.get(status="submitted")
        obj.status = "payment_pending"
        with self.assertRaises(ValidationError):
            obj.save()

    def test_payable_jump_blocked(self):
        obj = SupplierPayableConfirmation.objects.get(status="internal_review")
        with transaction.atomic(), self.assertRaises(BusinessStateTransitionError):
            transition_payable_confirmation(obj, "ready_for_payment_request", self.user, "jump")

    def test_request_jump_blocked(self):
        obj = SupplierPaymentRequest.objects.get(status="submitted")
        with transaction.atomic(), self.assertRaises(BusinessStateTransitionError):
            transition_payment_request(obj, "payment_pending", self.user, "jump")

    def test_payable_api_count(self):
        self.assertEqual(
            self.client.get("/api/scm/supplier-payable-confirmations/").data["data"]["recordCount"], 4
        )

    def test_request_api_count(self):
        self.assertEqual(
            self.client.get("/api/scm/supplier-payment-requests/").data["data"]["recordCount"], 3
        )

    def test_payable_five_surfaces(self):
        data = self.client.get("/api/scm/supplier-payable-confirmations/").data["data"]
        self.assertEqual([
            data["recordCount"], data["payableConfirmationFacts"]["recordCount"],
            data["diagnosticFacts"]["recordCount"], data["strictFacts"]["recordCount"],
            data["acceptanceFacts"]["recordCount"],
        ], [4, 4, 4, 4, 4])

    def test_request_five_surfaces(self):
        data = self.client.get("/api/scm/supplier-payment-requests/").data["data"]
        self.assertEqual([
            data["recordCount"], data["paymentRequestFacts"]["recordCount"],
            data["diagnosticFacts"]["recordCount"], data["strictFacts"]["recordCount"],
            data["acceptanceFacts"]["recordCount"],
        ], [3, 3, 3, 3, 3])

    def test_payable_chinese_status(self):
        rows = self.client.get("/api/scm/supplier-payable-confirmations/").data["data"]["results"]
        self.assertTrue(all(row["statusLabel"] and row["statusLabel"] != row["statusCode"] for row in rows))

    def test_request_chinese_status(self):
        rows = self.client.get("/api/scm/supplier-payment-requests/").data["data"]["results"]
        self.assertTrue(all(row["statusLabel"] and row["statusLabel"] != row["statusCode"] for row in rows))

    def test_payable_status_filter(self):
        data = self.client.get(
            "/api/scm/supplier-payable-confirmations/?statusCode=ready_for_payment_request"
        ).data["data"]
        self.assertEqual(data["recordCount"], 3)

    def test_request_status_filter(self):
        data = self.client.get(
            "/api/scm/supplier-payment-requests/?statusCode=approved"
        ).data["data"]
        self.assertEqual(data["recordCount"], 1)

    def test_empty_contract(self):
        data = self.client.get(
            "/api/scm/supplier-payment-requests/?q=NOT-FOUND"
        ).data["data"]
        self.assertEqual(data["recordCount"], 0)
        self.assertEqual(data["acceptanceFacts"]["acceptanceStatus"], "PASS")

    def test_forbidden_writes_zero(self):
        for endpoint, key in [
            ("/api/scm/supplier-payable-confirmations/", "payableConfirmationFacts"),
            ("/api/scm/supplier-payment-requests/", "paymentRequestFacts"),
        ]:
            facts = self.client.get(endpoint).data["data"][key]
            self.assertEqual((
                facts["paymentExecutionWriteCount"], facts["bankSendWriteCount"],
                facts["financialImpactWriteCount"], facts["businessProgressWriteCount"],
            ), (0, 0, 0, 0))

    def test_unique_payment_request_source(self):
        obj = SupplierPaymentRequest.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate = SupplierPaymentRequest(
                payment_request_no="DUP-V83",
                payable_confirmation_no=obj.payable_confirmation_no,
                supplier_id=obj.supplier_id,
                supplier_name=obj.supplier_name,
                period=obj.period,
                request_amount=obj.request_amount,
                request_reason="duplicate",
                requested_by="tester",
                tenant_id=obj.tenant_id,
                batch_id=obj.batch_id,
                status=obj.status,
            )
            duplicate._business_state_initialization_authorized = True
            duplicate.save()

    def test_seed_idempotent(self):
        ensure_v83_demo_data(self.user)
        self.assertEqual((
            SupplierPayableConfirmation.objects.count(),
            SupplierPaymentRequest.objects.count(),
        ), (4, 3))

    def test_buyer_metrics_extended(self):
        self.assertTrue(all(
            metric.payment_request_accuracy > 0
            for metric in BuyerPerformanceMetric.objects.all()
        ))

    def test_audit_references_complete(self):
        transitions = BusinessStateTransition.objects.filter(
            object_type__in=["SupplierPayableConfirmation", "SupplierPaymentRequest"]
        )
        self.assertTrue(transitions.exists())
        self.assertTrue(all(item.audit_reference for item in transitions))
