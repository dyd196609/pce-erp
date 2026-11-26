"""RAM fixtures for exact saved-version rows; no publication is performed."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from system.models import Company

from . import tests_order_engineering_document_registration as registration_fixture
from .models import (
    BOMVersion, EngineeringCalculationRecord, EngineeringDocument,
    EngineeringDocumentVersion, ManufacturingProcessType, OrderEngineeringBaseline,
    ProductBOM, ProductCategory, ProductManufacturingOutput, Routing, RoutingStep, RoutingVersion,
)
from .views import EngineeringDocumentListView


class EngineeringDocumentVersionProjectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        registration_fixture.OrderEngineeringDocumentRegistrationTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.reviewed_ids = []
        self.release_ids = []
        self._patch("pde.views.require_current_order_admission", return_value=SimpleNamespace(
            as_dict=lambda: {"status": "valid"}))
        self._patch("pde.views.FormalManufacturingEligibilityService.resolve", return_value={
            "formalManufacturingEligible": True, "message": "",
            "businessPurposeLabel": "正式销售订单", "statusLabel": "正式制造资格已具备"})
        self._patch("pde.views.project_engineering_document_version_review_preflight",
            side_effect=self._review)
        self._patch("pde.views.project_engineering_document_version_release_preflight",
            side_effect=self._release)

    def _patch(self, target, **kwargs):
        patcher = patch(target, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _review(self, version, user):
        self.reviewed_ids.append(version.pk)
        return {"readyForHumanReview": version.status == "draft", "versionId": version.pk,
            "reviewAllowed": version.status == "draft", "databaseBusinessWriteCount": 0}

    def _release(self, version, user):
        self.release_ids.append(version.pk)
        return {"readyForHumanRelease": version.status == "reviewed", "versionId": version.pk,
            "releaseAllowed": version.status == "reviewed",
            "releaseReadback": {"completed": version.status == "released"},
            "databaseBusinessWriteCount": 0}

    def _old(self):
        BOMVersion.objects.filter(pk=self.bom_version.pk).update(status="released")
        self.bom_version.refresh_from_db()
        self.document = EngineeringDocument.objects.create(
            release_subject_type="ORDER_ENGINEERED_PRODUCT",
            order_engineering_instance=self.instance, document_no="ED-PROJECTION-001",
            document_name="已确认的技术资料", document_type="technical",
            product_bom=self.bom, routing=self.routing, version="V1.0")
        old = EngineeringDocumentVersion.objects.create(document=self.document,
            document_name=self.document.document_name, document_version="V1.0",
            release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=self.instance,
            order_engineering_baseline=self.baseline, engineering_calculation=self.calculation,
            related_bom=self.bom_version, related_routing=self.routing_version, status="released")
        output = ProductManufacturingOutput.objects.create(
            release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=self.instance,
            order_engineering_baseline=self.baseline, engineering_calculation=self.calculation,
            bom_version=self.bom_version, routing_version=self.routing_version,
            engineering_document_version=old, definition_mode="order_specific",
            engineering_status="ready", release_status="released_to_manufacturing")
        return old, output

    def _new(self, status="draft"):
        baseline = OrderEngineeringBaseline(
            company=self.company, sales_order=self.order, baseline_no="EDREG-BASELINE-002",
            sequence=2, status="draft", reason="独立新来源投影测试", candidate_hash="1" * 64,
            snapshot_hash="2" * 64, scope_item_count=1, confirmable_item_count=1,
            blocker_count=0, blocker_summary={}, created_by=self.user)
        baseline._business_state_initialization_authorized = True
        baseline.save()
        OrderEngineeringBaseline.objects.filter(pk=baseline.pk).update(status="confirmed")
        baseline.refresh_from_db()
        calculation = EngineeringCalculationRecord.objects.create(
            company=self.company, source_record=self.source, sales_order_item=self.order_item,
            engineering_instance=self.instance, calculation_no="EDREG-CALC-002",
            rule_set_version="EDREG-RULE-V1", revision=2, scope="order_engineering",
            result_hash="3" * 64, status="completed")
        bom = BOMVersion.objects.create(bom=self.bom, bom_version="CALC-NEW", revision=2,
            bom_scope="order_specific", order_engineering_instance=self.instance,
            source_calculation=calculation, status="released")
        route = RoutingVersion.objects.create(routing=self.routing, routing_version="V2.0",
            revision=2, status="draft")
        RoutingStep.objects.create(routing_version=route, sequence=20, operation=self.operation,
            operation_parameters={"applicability": {"mode": "MANDATORY"}})
        RoutingVersion.objects.filter(pk=route.pk).update(status="released")
        route.refresh_from_db()
        version = EngineeringDocumentVersion.objects.create(document=self.document,
            document_name=self.document.document_name, document_version="V2.0",
            release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=self.instance,
            order_engineering_baseline=baseline, engineering_calculation=calculation,
            related_bom=bom, related_routing=route, status=status)
        return version

    def _get(self, **params):
        request = APIRequestFactory().get("/api/pde/engineering-documents/", params)
        force_authenticate(request, user=self.user)
        response = EngineeringDocumentListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        return response.data

    def _rows(self, payload):
        return [row for row in payload["rows"]
            if row.get("sourceObjectTypeLabel") == "订单工程发布候选"]

    def _assert_source(self, row, version, output_id):
        self.assertEqual((row["engineeringDocumentVersionId"], row["engineeringBaselineId"],
            row["sourceCalculationId"], row["bomVersionId"], row["routingVersionId"],
            row["manufacturingOutputId"]), (version.pk, version.order_engineering_baseline_id,
            version.engineering_calculation_id, version.related_bom_id, version.related_routing_id,
            output_id))
        self.assertEqual(row["reviewPreflight"]["versionId"], version.pk)
        self.assertEqual(row["documentReleasePreflight"]["versionId"], version.pk)

    def test_01_old_and_new_rows_keep_their_exact_sources_and_action_versions(self):
        old, output = self._old()
        new = self._new()
        payload = self._get()
        rows = self._rows(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["id"] for row in rows], [f"OEI-{self.instance.pk}",
            f"OEI-{self.instance.pk}-DOCUMENT-VERSION-{new.pk}"])
        self._assert_source(rows[0], old, output.pk)
        self._assert_source(rows[1], new, None)
        self.assertEqual(rows[1]["version"], "V2.0")
        self.assertEqual(self.reviewed_ids, [old.pk, new.pk])
        self.assertEqual(self.release_ids, [old.pk, new.pk])
        self.assertEqual(payload["strictFacts"]["engineeringDocumentVersionCount"], 2)
        self.assertEqual(payload["strictFacts"]["releasedEngineeringDocumentCount"], 1)
        self.assertEqual(payload["strictFacts"]["publishableEngineeringDocumentCount"], 0)
        self.assertTrue(any(row["id"] == f"DOCUMENT-{self.document.pk}" for row in payload["rows"]))

    def test_02_single_legacy_version_retains_oei_identity_and_output(self):
        old, output = self._old()
        rows = self._rows(self._get())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], f"OEI-{self.instance.pk}")
        self._assert_source(rows[0], old, output.pk)

    def test_03_empty_scope_retains_one_oei_candidate_without_actions(self):
        rows = self._rows(self._get())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], f"OEI-{self.instance.pk}")
        self.assertIsNone(rows[0]["engineeringDocumentVersionId"])
        self.assertEqual(rows[0]["engineeringDocumentCount"], 0)
        self.assertFalse(rows[0]["reviewPreflight"]["reviewAllowed"])
        self.assertFalse(rows[0]["documentReleasePreflight"]["releaseAllowed"])

    def test_04_unselected_multiple_versions_require_explicit_selection(self):
        self._old()
        self._new()
        row = EngineeringDocumentListView._serialize_release_candidate(self.instance,
            release_subject_schema_available=True, admission={"status": "valid"}, user=self.user)
        self.assertTrue(row["documentVersionSelectionRequired"])
        self.assertIsNone(row["engineeringDocumentVersionId"])
        self.assertIsNone(row["manufacturingOutputId"])
        self.assertFalse(row["reviewPreflight"]["reviewAllowed"])
        self.assertFalse(row["documentReleasePreflight"]["releaseAllowed"])
        self.assertEqual(self.reviewed_ids, [])
        self.assertEqual(self.release_ids, [])

    def test_05_lifecycle_refresh_preserves_row_identity_and_counts_once(self):
        old, output = self._old()
        new = self._new("reviewed")
        before = self._get()
        rows = self._rows(before)
        self.assertEqual(before["strictFacts"]["publishableEngineeringDocumentCount"], 1)
        EngineeringDocumentVersion.objects.filter(pk=new.pk).update(status="released")
        after = self._get()
        self.assertEqual([row["id"] for row in self._rows(after)], [row["id"] for row in rows])
        self.assertEqual(after["strictFacts"]["releasedEngineeringDocumentCount"], 2)
        self.assertEqual(after["strictFacts"]["publishableEngineeringDocumentCount"], 0)
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            self.assertEqual(after[key]["releasedEngineeringDocumentCount"], 2)
            self.assertEqual(after[key]["engineeringDocumentVersionCount"], 2)
        self._assert_source(self._rows(after)[0], old, output.pk)

    def test_06_query_can_select_new_version_without_selecting_old_output(self):
        self._old()
        new = self._new()
        rows = self._rows(self._get(q="V2.0"))
        self.assertEqual(len(rows), 1)
        self._assert_source(rows[0], new, None)

    def test_07_output_with_mixed_upstream_cannot_attach_to_new_version(self):
        self._old()
        new = self._new()
        ProductManufacturingOutput.objects.filter(order_engineering_instance=self.instance).update(
            engineering_document_version_id=new.pk)
        rows = self._rows(self._get())
        self.assertIsNone(rows[0]["manufacturingOutputId"])
        self._assert_source(rows[1], new, None)

    def test_08_untraceable_old_row_remains_blocked_and_new_identity_does_not_move(self):
        old, _ = self._old()
        new = self._new()
        other_header = ProductBOM.objects.create(
            applicability_scope=self.bom.applicability_scope,
            order_engineering_instance=self.instance, company=self.company,
            bom_code="EDREG-OTHER-OBOM", name="其他BOM主表", bom_type="packaging")
        other_bom = BOMVersion.objects.create(bom=other_header, bom_version="OTHER-CALC",
            revision=1, bom_scope="order_specific", order_engineering_instance=self.instance,
            status="released")
        EngineeringDocumentVersion.objects.filter(pk=old.pk).update(
            related_bom_id=other_bom.pk)
        # Corrupt synthetic history stays visible, blocked and cannot dispatch an action.
        rows = self._rows(self._get())
        self.assertEqual([row["id"] for row in rows],
            [f"OEI-{self.instance.pk}", f"OEI-{self.instance.pk}-DOCUMENT-VERSION-{new.pk}"])
        self.assertEqual(rows[0]["engineeringDocumentVersionId"], old.pk)
        self.assertGreater(rows[0]["documentOwnershipConflictCount"], 0)
        self.assertIn("归属冲突", rows[0]["reviewPreflight"]["decisionLabel"])
        self.assertFalse(rows[0]["reviewPreflight"]["reviewAllowed"])
        self.assertFalse(rows[0]["documentReleasePreflight"]["releaseAllowed"])
        self.assertEqual(rows[0]["traceableEngineeringDocumentVersionCount"], 0)
        self.assertEqual(rows[0]["documentNo"], self.document.document_no)
        self.assertIsNone(rows[0]["bomVersionId"])
        self.assertIsNone(rows[0]["sourceCalculationId"])
        self.assertIsNone(rows[0]["routingVersionId"])
        self.assertIsNone(rows[0]["engineeringBaselineId"])
        self.assertNotIn(other_header.bom_code, str(rows[0]))
        self.assertEqual(self.reviewed_ids, [new.pk])
        self.assertEqual(self.release_ids, [new.pk])
        self._assert_source(rows[1], new, None)

    def test_09_foreign_upstream_names_are_not_projected_on_blocked_history(self):
        old, _ = self._old()
        new = self._new()
        foreign_company = Company.objects.create(code="FOREIGN-PROJECTION", name="其他公司")
        foreign_category = ProductCategory.objects.create(company=foreign_company,
            code="FOREIGN-CATEGORY", name="其他公司产品分类")
        foreign_process = ManufacturingProcessType.objects.create(company=foreign_company,
            code="FOREIGN-PROCESS", name="其他公司工艺类型")
        foreign_route = Routing.objects.create(company=foreign_company,
            applicability_scope="PRODUCT_CATEGORY", product_category=foreign_category,
            manufacturing_process_type=foreign_process,
            routing_code="FOREIGN-SECRET-ROUTE", name="其他公司保密路线", status="released")
        foreign_version = RoutingVersion.objects.create(routing=foreign_route,
            routing_version="FOREIGN-SECRET-VERSION", revision=1, status="released")
        EngineeringDocumentVersion.objects.filter(pk=old.pk).update(related_routing=foreign_version)
        rows = self._rows(self._get())
        self.assertEqual(rows[0]["id"], f"OEI-{self.instance.pk}")
        self.assertEqual(rows[0]["engineeringDocumentVersionId"], old.pk)
        self.assertEqual(rows[0]["documentNo"], self.document.document_no)
        self.assertIsNone(rows[0]["routingVersionId"])
        for protected_value in (foreign_route.routing_code, foreign_route.name,
                foreign_version.routing_version):
            self.assertNotIn(protected_value, str(rows[0]))
        self.assertEqual(self.reviewed_ids, [new.pk])
        self.assertEqual(self.release_ids, [new.pk])
