from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import BusinessStateTransitionError

from supplier_performance.models import BuyerPerformanceMetric, SupplierPerformanceMetric, SupplierReconciliation
from supplier_performance.services import ensure_demo_data, transition_reconciliation


class SupplierPerformanceV81Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="v81-test", real_name="V81 Test", company_id=1,
        )
        ensure_demo_data(self.user)
        self.client = APIClient()

    def test_demo_reconciliation_count(self):
        self.assertEqual(SupplierReconciliation.objects.count(), 4)

    def test_status_distribution(self):
        self.assertEqual(set(SupplierReconciliation.objects.values_list("status", flat=True)),
                         {"draft", "internal_review", "supplier_confirming", "completed"})

    def test_state_history_uses_governed_service(self):
        completed = SupplierReconciliation.objects.get(status="completed")
        self.assertEqual(BusinessStateTransition.objects.filter(
            object_type="SupplierReconciliation", object_id=completed.pk).count(), 3)

    def test_direct_status_write_blocked(self):
        obj = SupplierReconciliation.objects.get(status="draft")
        obj.status = "completed"
        with self.assertRaises(ValidationError):
            obj.save()

    def test_jump_transition_blocked(self):
        obj = SupplierReconciliation.objects.get(status="draft")
        with transaction.atomic(), self.assertRaises(BusinessStateTransitionError):
            transition_reconciliation(obj, "completed", self.user, "jump")

    def test_reconciliation_api(self):
        response = self.client.get("/api/scm/supplier-reconciliations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["recordCount"], 4)

    def test_reconciliation_empty_filter(self):
        response = self.client.get("/api/scm/supplier-reconciliations/?q=NOT-FOUND")
        self.assertEqual(response.data["data"]["recordCount"], 0)
        self.assertEqual(response.data["data"]["acceptanceFacts"]["acceptanceStatus"], "PASS")

    def test_reconciliation_chinese_status(self):
        response = self.client.get("/api/scm/supplier-reconciliations/")
        self.assertTrue(all(row["statusLabel"] for row in response.data["data"]["results"]))

    def test_reconciliation_sources(self):
        row = self.client.get("/api/scm/supplier-reconciliations/").data["data"]["results"][0]
        self.assertEqual(row["sourceCounts"], {"purchaseOrder": 2, "receipt": 1, "inspection": 1, "warehouseReceipt": 1})

    def test_buyer_metric_count(self):
        self.assertEqual(BuyerPerformanceMetric.objects.count(), 3)

    def test_buyer_api_score(self):
        rows = self.client.get("/api/scm/buyer-performance/").data["data"]["results"]
        self.assertTrue(all(0 <= float(row["overallScore"]) <= 100 for row in rows))

    def test_buyer_source_consistency(self):
        rows = self.client.get("/api/scm/buyer-performance/").data["data"]["results"]
        self.assertTrue(all(len(row["sourcePurchaseOrderIds"]) == row["purchaseOrderCount"] for row in rows))

    def test_supplier_metric_count(self):
        self.assertEqual(SupplierPerformanceMetric.objects.count(), 4)

    def test_supplier_score_calculation(self):
        row = SupplierPerformanceMetric.objects.get(supplier_id="SUP-001")
        expected = sum([row.delivery_on_time_rate, row.quality_pass_rate, row.price_trend_score,
                        row.service_score, row.reconciliation_accuracy_rate]) / 5
        self.assertEqual(row.overall_score, expected)

    def test_supplier_api_fact_source(self):
        facts = self.client.get("/api/scm/supplier-performance/").data["data"]["performanceFacts"]
        self.assertEqual(facts["factSource"], "server")

    def test_five_surface_counts(self):
        data = self.client.get("/api/scm/supplier-performance/").data["data"]
        self.assertEqual([data["recordCount"], data["performanceFacts"]["recordCount"],
                          data["diagnosticFacts"]["recordCount"], data["strictFacts"]["recordCount"],
                          data["acceptanceFacts"]["recordCount"]], [4, 4, 4, 4, 4])

    def test_acceptance_has_required_fields(self):
        facts = self.client.get("/api/scm/buyer-performance/").data["data"]["acceptanceFacts"]
        for key in ["recordCount", "actionCount", "dangerActionCount", "businessProgressWriteCount",
                    "downstreamObjectCount", "factSource"]:
            self.assertIn(key, facts)

    def test_forbidden_writes_zero(self):
        facts = self.client.get("/api/scm/supplier-reconciliations/").data["data"]["reconciliationFacts"]
        self.assertEqual((facts["paymentExecutionWriteCount"], facts["bankSendWriteCount"],
                          facts["financialImpactWriteCount"]), (0, 0, 0))

    def test_metric_unique_period(self):
        obj = BuyerPerformanceMetric.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BuyerPerformanceMetric.objects.create(
                metric_no="DUP", buyer_id=obj.buyer_id, buyer_name=obj.buyer_name, period=obj.period,
                purchase_order_count=1, on_time_purchase_rate=1, price_optimization_rate=1,
                supplier_issue_response_time=1, process_compliance_rate=1, overall_score=1,
                tenant_id=obj.tenant_id, batch_id=obj.batch_id,
            )

    def test_demo_seed_idempotent(self):
        ensure_demo_data(self.user)
        self.assertEqual((SupplierReconciliation.objects.count(), BuyerPerformanceMetric.objects.count(),
                          SupplierPerformanceMetric.objects.count()), (4, 3, 4))

    def test_reconciliation_typed_select_filter(self):
        response = self.client.get("/api/scm/supplier-reconciliations/?statusCode=completed")
        rows = response.data["data"]["results"]
        self.assertEqual(len(rows), 1)
        self.assertTrue(all(row["statusCode"] == "completed" for row in rows))

    def test_supplier_typed_select_filter(self):
        name = SupplierPerformanceMetric.objects.order_by("supplier_id").first().supplier_name
        response = self.client.get("/api/scm/supplier-performance/", {"supplierName": name})
        self.assertEqual(response.data["data"]["recordCount"], 1)
        self.assertEqual(response.data["data"]["results"][0]["supplierName"], name)

    def test_buyer_period_range_filter(self):
        period = BuyerPerformanceMetric.objects.order_by("buyer_id").first().period
        response = self.client.get("/api/scm/buyer-performance/", {
            "periodFrom": f"{period}-01",
            "periodTo": f"{period}-28",
        })
        self.assertEqual(response.data["data"]["recordCount"], 3)
