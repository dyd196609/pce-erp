from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory

from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft
from purchase_accounts_payable_draft.views import DraftListView
from payable_confirmation_prepare.models import PayableConfirmationPrepare
from purchase_invoice_prepare.models import PurchaseInvoicePrepare
from purchase_canary.catalog import BATCH_ID, MODULES, SCENARIOS
from purchase_canary.models import PurchaseCanaryBatch, PurchaseCanaryLineage
from reconciliation.models import (
    PayableCheckAuthorityRecord,
    PurchaseReconciliation,
    SupplierSettlementAuthorityRecord,
)


class PurchaseCanaryTests(TestCase):
    def setUp(self):
        call_command("ensure_purchase_canary_group")

    def test_ensure_is_idempotent_and_complete(self):
        call_command("ensure_purchase_canary_group")
        batch = PurchaseCanaryBatch.objects.get(batch_id=BATCH_ID)
        self.assertEqual(batch.scenarios.count(), len(SCENARIOS))
        for scenario in batch.scenarios.all():
            self.assertEqual(scenario.module_objects.count(), len(MODULES))
            self.assertEqual(scenario.relations.count(), len(MODULES) - 1)

    def test_context_is_server_read_only_and_scenarios_are_distinct(self):
        client = APIClient()
        response = client.get("/api/pce/purchase-canary/context", {
            "batchId": BATCH_ID, "scenarioCode": "AMOUNT_DIFFERENCE",
            "moduleCode": "purchase-reconciliation",
        })
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["currentStateSource"], "server")
        self.assertEqual(data["current"]["status"], "difference_found")
        self.assertFalse(data["current"]["nextStepAllowed"])
        self.assertEqual(client.post("/api/pce/purchase-canary/context", {}).status_code, 405)

    def test_existing_target_and_happy_path_boundaries(self):
        client = APIClient()
        existing = client.get("/api/pce/purchase-canary/context", {
            "scenarioCode": "EXISTING_TARGET", "moduleCode": "account-payable-draft",
        }).data["data"]
        self.assertEqual(existing["current"]["status"], "draft_existing_target")
        self.assertFalse(existing["current"]["nextStepAllowed"])
        happy = client.get("/api/pce/purchase-canary/context", {
            "scenarioCode": "HAPPY_PATH", "moduleCode": "account-payable-draft",
        }).data["data"]
        self.assertEqual(happy["current"]["status"], "draft")


@override_settings(
    PCE_CANARY_DEMO_MODE=True,
    PCE_CANARY_TENANT_ID="tenant-canary-demo",
    PCE_CANARY_BATCH_ID="PURCHASE-FLOW-DEMO-V1",
    PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_VALIDATION_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS={"tenant-canary-demo"},
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FEATURE_ENABLED=True,
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_TEST_TENANTS={"tenant-canary-demo"},
)
class PurchaseCanaryFormalDomainTests(TestCase):
    def setUp(self):
        call_command("ensure_purchase_canary_formal_domain", verbosity=0)

    def test_persistent_demo_contains_formal_domain_chain(self):
        self.assertEqual(SupplierSettlementAuthorityRecord.objects.count(), 8)
        self.assertEqual(PayableCheckAuthorityRecord.objects.count(), 8)
        self.assertEqual(PurchaseReconciliation.objects.count(), 8)
        self.assertEqual(PurchaseInvoicePrepare.objects.count(), 8)
        draft = PurchaseAccountsPayableDraft.objects.order_by("draft_no").first()
        self.assertEqual(draft.draft_no, "APD20260700000001")
        self.assertEqual(draft.source_purchase_invoice_prepare_no, "PIP20260700000001")
        self.assertEqual(draft.tenant_id, "tenant-canary-demo")

    def test_plain_and_blocked_scenarios_use_formal_server_read_model(self):
        factory = APIRequestFactory()
        plain = DraftListView.as_view()(
            factory.get("/api/scm/purchase-accounts-payable-drafts/")
        )
        self.assertEqual(plain.status_code, 200)
        self.assertEqual(plain.data["data"]["count"], 8)
        self.assertIn(
            "APD20260700000001",
            {row["draftNo"] for row in plain.data["data"]["results"]},
        )
        blocked = DraftListView.as_view()(
            factory.get(
                "/api/scm/purchase-accounts-payable-drafts/",
                {"scenarioCode": "AMOUNT_DIFFERENCE"},
            )
        )
        self.assertEqual(blocked.status_code, 200)
        self.assertEqual(blocked.data["data"]["count"], 0)

    def test_downstream_canary_capacity_minimum_is_met(self):
        response = DraftListView.as_view()(APIRequestFactory().get("/api/scm/purchase-accounts-payable-drafts/"))
        self.assertGreaterEqual(response.data["data"]["capacity"]["downstreamEligibleLineageCount"], 8)

    def test_pass_through_lineage_count_is_at_least_eight(self):
        self.assertGreaterEqual(PurchaseCanaryLineage.objects.filter(scenario_class="pass_through").count(), 8)

    def test_blocked_scenarios_not_counted_as_pass_through(self):
        codes = set(PurchaseCanaryLineage.objects.values_list("scenario_code", flat=True))
        self.assertFalse(codes.intersection({"AMOUNT_DIFFERENCE", "QUANTITY_DIFFERENCE", "SOURCE_MISSING", "INVOICE_VALIDATION_FAILED", "DUPLICATE_INVOICE", "SOURCE_STALE"}))

    def test_existing_target_not_counted_as_new_lineage(self):
        self.assertFalse(PurchaseCanaryLineage.objects.filter(scenario_code="EXISTING_TARGET").exists())

    def test_idempotent_retry_not_counted_as_new_lineage(self):
        before = (PurchaseCanaryLineage.objects.count(), PurchaseAccountsPayableDraft.objects.count())
        call_command("ensure_purchase_canary_formal_domain", verbosity=0)
        self.assertEqual(before, (PurchaseCanaryLineage.objects.count(), PurchaseAccountsPayableDraft.objects.count()))

    def test_each_pass_through_has_unique_source_chain(self):
        rows = list(PurchaseCanaryLineage.objects.all())
        self.assertEqual(len({row.source_relation_hash for row in rows}), len(rows))
        self.assertEqual(len({row.canary_lineage_id for row in rows}), len(rows))
        self.assertEqual(len({tuple(row.upstream_object_nos) for row in rows}), len(rows))

    def test_each_pass_through_has_formal_domain_objects(self):
        for lineage in PurchaseCanaryLineage.objects.all():
            draft = PurchaseAccountsPayableDraft.objects.get(pk=lineage.current_object_id)
            self.assertEqual(draft.draft_no, lineage.current_object_no)
            reconciliation = draft.source_purchase_reconciliation
            self.assertTrue(SupplierSettlementAuthorityRecord.objects.filter(
                settlement_no=reconciliation.source_supplier_settlement_no
            ).exists())
            self.assertTrue(PayableCheckAuthorityRecord.objects.filter(
                payable_check_no=reconciliation.source_payable_check_no
            ).exists())
            evidence = list(reconciliation.evidence_records.values_list(
                "provider_code", "repository_code"
            ))
            self.assertEqual(len(evidence), 2)
            self.assertEqual(len({provider for provider, _ in evidence}), 2)
            self.assertEqual(len({repository for _, repository in evidence}), 2)
            self.assertIsNotNone(draft.source_snapshot)
            self.assertIsNotNone(draft.audit_record)

    def test_normal_ap_draft_page_shows_all_pass_through_objects(self):
        response = DraftListView.as_view()(APIRequestFactory().get("/api/scm/purchase-accounts-payable-drafts/"))
        self.assertEqual(response.data["data"]["count"], PurchaseCanaryLineage.objects.count())
        self.assertGreaterEqual(len(response.data["data"]["results"]), 8)

    def test_scenario_overview_shows_blocked_and_success_cases(self):
        response = DraftListView.as_view()(APIRequestFactory().get("/api/scm/purchase-accounts-payable-drafts/"))
        overview = response.data["data"]["scenarioOverview"]
        self.assertGreaterEqual(sum(row["scenarioClass"] == "pass_through" for row in overview), 8)
        self.assertGreaterEqual(sum(row["scenarioClass"] == "blocked" for row in overview), 6)

    def test_blocked_scenario_does_not_create_ap_draft(self):
        factory = APIRequestFactory()
        for code in ("AMOUNT_DIFFERENCE", "QUANTITY_DIFFERENCE", "SOURCE_MISSING", "INVOICE_VALIDATION_FAILED", "DUPLICATE_INVOICE", "SOURCE_STALE"):
            response = DraftListView.as_view()(factory.get("/api/scm/purchase-accounts-payable-drafts/", {"scenarioCode": code}))
            self.assertEqual(response.data["data"]["count"], 0)

    def test_next_module_sources_are_reserved_not_consumed(self):
        rows = PurchaseCanaryLineage.objects.all()
        self.assertFalse(rows.filter(next_stage_consumed=True).exists())
        self.assertEqual(rows.exclude(reserved_for_next_module="payable_confirmation_prepare").count(), 0)

    def test_persistent_canary_numbers_are_stable(self):
        before = list(PurchaseAccountsPayableDraft.objects.order_by("id").values_list("draft_no", flat=True))
        call_command("ensure_purchase_canary_formal_domain", verbosity=0)
        after = list(PurchaseAccountsPayableDraft.objects.order_by("id").values_list("draft_no", flat=True))
        self.assertEqual(before, after)
        self.assertEqual(before[0], "APD20260700000001")

    def test_regression_clone_does_not_modify_demo_database(self):
        from django.db import connection
        self.assertIn("test", str(connection.settings_dict["NAME"]).lower())
        self.assertNotEqual(str(connection.settings_dict["NAME"]).lower().replace("\\", "/"), "d:/dev-pce/source/backend/canary-data/purchase-flow-demo.sqlite3")

    def test_development_database_remains_unchanged(self):
        from django.db import connection
        self.assertNotEqual(str(connection.settings_dict["NAME"]).lower().replace("\\", "/"), "d:/dev-pce/source/backend/db.sqlite3")

    def test_confirmation_prepare_is_not_created(self):
        self.assertEqual(PayableConfirmationPrepare.objects.count(), 0)
        self.assertEqual(PurchaseCanaryLineage.objects.filter(next_stage_consumed=True).count(), 0)

    def test_module_navigation_unchanged(self):
        self.assertEqual(MODULES[-1][0], "account-payable-draft")
        self.assertNotIn("payable-confirmation-prepare", {row[0] for row in MODULES})
