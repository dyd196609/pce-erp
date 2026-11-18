from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase

from supplier_performance.models import (
    BuyerPerformanceMetric,
    SupplierPaymentRequest,
    SupplierPaymentStatusRecord,
    SupplierPerformanceMetric,
    SupplierSettlementCompletion,
)
from supplier_performance.services import (
    ensure_v84_demo_data,
    transition_payment_status_record,
)
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import BusinessStateTransitionError


class SupplierSettlementV84Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_v84_demo_data()

    def test_payment_requests_are_not_modified_or_recreated(self):
        self.assertEqual(SupplierPaymentRequest.objects.count(), 4)

    def test_payment_status_records_exist(self):
        self.assertEqual(SupplierPaymentStatusRecord.objects.count(), 4)

    def test_settlement_completion_records_exist(self):
        self.assertEqual(SupplierSettlementCompletion.objects.count(), 2)

    def test_payment_status_uses_business_state_transition(self):
        obj = SupplierPaymentStatusRecord.objects.get(status="settlement_completed")
        self.assertEqual(
            BusinessStateTransition.objects.filter(
                object_type="SupplierPaymentStatusRecord", object_id=obj.pk
            ).count(),
            5,
        )

    def test_settlement_completion_uses_business_state_transition(self):
        obj = SupplierSettlementCompletion.objects.get(status="completed")
        self.assertEqual(
            BusinessStateTransition.objects.filter(
                object_type="SupplierSettlementCompletion", object_id=obj.pk
            ).count(),
            1,
        )

    def test_direct_status_assignment_is_blocked(self):
        obj = SupplierPaymentStatusRecord.objects.get(status="approved")
        obj.status = "settlement_completed"
        with self.assertRaises(ValidationError):
            obj.save()

    def test_jump_transition_is_blocked(self):
        obj = SupplierPaymentStatusRecord.objects.get(status="approved")
        operator = BusinessStateTransition.objects.filter(
            object_type="SupplierPaymentStatusRecord", object_id=obj.pk
        ).first().operator
        with transaction.atomic(), self.assertRaises(BusinessStateTransitionError):
            transition_payment_status_record(
                obj, "settlement_completed", operator, "jump must fail"
            )

    def test_payment_status_api_uses_server_facts(self):
        data = self.client.get("/api/scm/supplier-payment-status/").data["data"]
        self.assertEqual(data["recordCount"], 4)
        self.assertEqual(data["paymentStatusFacts"]["factSource"], "server")
        self.assertEqual(data["strictFacts"]["recordCount"], 4)
        self.assertEqual(data["paymentStatusFacts"]["dangerActionCount"], 0)

    def test_completion_api_uses_server_facts(self):
        data = self.client.get("/api/scm/supplier-settlement-completions/").data["data"]
        self.assertEqual(data["recordCount"], 2)
        self.assertEqual(data["settlementCompletionFacts"]["factSource"], "server")
        self.assertEqual(data["diagnosticFacts"]["recordCount"], 2)
        self.assertEqual(data["acceptanceFacts"]["recordCount"], 2)

    def test_api_never_reports_financial_writes(self):
        for url, key in [
            ("/api/scm/supplier-payment-status/", "paymentStatusFacts"),
            ("/api/scm/supplier-settlement-completions/", "settlementCompletionFacts"),
        ]:
            facts = self.client.get(url).data["data"][key]
            self.assertEqual(facts["paymentExecutionWriteCount"], 0)
            self.assertEqual(facts["bankSendWriteCount"], 0)
            self.assertEqual(facts["financialImpactWriteCount"], 0)

    def test_supplier_performance_sources_are_linked(self):
        self.assertTrue(
            SupplierPerformanceMetric.objects.filter(
                source_settlement_completion_nos__isnull=False
            ).exists()
        )

    def test_buyer_performance_sources_are_linked(self):
        self.assertTrue(
            BuyerPerformanceMetric.objects.filter(
                source_settlement_completion_nos__isnull=False
            ).exists()
        )
