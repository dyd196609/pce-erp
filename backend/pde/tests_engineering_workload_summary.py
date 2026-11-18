"""SIMULATED_FOR_TEST: fixed-source workload summary, never real-order mapping.

The ORM fixture deliberately uses abstract processes and an explicit published
rule. Source previews, saved facts and per-basis EOR quantities remain distinct.
"""

from contextlib import ExitStack
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import CodeRule
from planning.models import ProductionPlan
from sales.models import SalesOrderItemEngineeringAttribute
from system.models import Company, OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition

from . import operation_requirement_service as requirements
from . import tests_operation_requirement as fixtures
from .engineering_workload_summary import (
    FACT_SURFACES, build_engineering_workload_summary,
    engineering_workload_summary_read_failure, stamp_engineering_workload_summary,
)
from .models import (
    EngineeringCalculationDetail, EngineeringCalculationRecord,
    EngineeringDerivedFact, EngineeringOperationRequirement,
    EngineeringRuleDefinition, EngineeringSourceRecord, ProductDesignItem,
    ProductionPlanOperationRequirementAllocation, RoutingStep,
)


class EngineeringWorkloadSummaryTests(TestCase):
    # Reuse the isolated, uniform-state fixture without inheriting its tests.
    initial = fixtures.OperationRequirementTests.initial
    advance = fixtures.OperationRequirementTests.advance
    make_rule = fixtures.OperationRequirementTests.make_rule
    make_source_fact = fixtures.OperationRequirementTests.make_source_fact
    generate = fixtures.OperationRequirementTests.generate
    allocate = fixtures.OperationRequirementTests.allocate

    def setUp(self):
        fixtures.OperationRequirementTests.setUp(self)

    def protected_snapshot(self):
        return {
            model._meta.label: list(model.objects.order_by("pk").values())
            for model in (
                EngineeringSourceRecord, EngineeringCalculationRecord,
                EngineeringCalculationDetail, EngineeringDerivedFact,
                EngineeringOperationRequirement, EngineeringRuleDefinition,
                ProductionPlanOperationRequirementAllocation, RoutingStep,
                ProductionPlan, BusinessStateTransition,
                OrganizationOperatingAuditRecord, CodeRule,
            )
        }

    def readonly_call(self, call):
        before = self.protected_snapshot()
        with ExitStack() as stack:
            for target in (
                "pde.operation_requirement_service.evaluate_specification",
                "pde.operation_requirement_service.OperationRequirementService.generate",
                "pde.engineering_calculation_service.EngineeringCalculationService.execute",
            ):
                stack.enter_context(patch(target, side_effect=AssertionError("Read projection must not execute or generate")))
            queries = stack.enter_context(CaptureQueriesContext(connection))
            result = call()
        writes = [row["sql"] for row in queries if row["sql"].lstrip().split(" ", 1)[0].upper() in
                  {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"}]
        self.assertEqual(writes, [])
        self.assertEqual(self.protected_snapshot(), before)
        self.assertEqual(result["businessWriteCount"], 0)
        return result

    def conversion(self, facts=None):
        return self.readonly_call(lambda: requirements.OperationRequirementService.read_source_conversion(
            user=self.user, source_calculation_id=self.source_calc.pk,
            source_fact_ids=facts if facts is not None else [self.fact_area.pk]))

    @staticmethod
    def blocker_codes(row):
        return {item["code"] for item in row["blockers"]}

    def assert_same_fact_surfaces(self, summary):
        surface = {key: value for key, value in summary.items() if key not in FACT_SURFACES}
        for key in FACT_SURFACES:
            self.assertEqual(summary[key], surface, f"{key} must use the identical stamped server facts")

    def test_saved_fact_with_exact_rule_is_pending_and_read_does_not_generate(self):
        data = self.conversion()
        row = data["facts"][0]
        self.assertEqual(row["sourceFactId"], self.fact_area.pk)
        self.assertEqual(row["sourceDetailId"], self.fact_area.source_detail_id)
        self.assertEqual(row["conversionStatusCode"], "NOT_CONVERTED")
        self.assertIn("OPERATION_REQUIREMENT_NOT_GENERATED", self.blocker_codes(row))
        self.assertEqual(row["operationRequirementIds"], [])
        self.assertTrue(row["ruleCandidates"][0]["ready"])
        self.assertEqual(EngineeringOperationRequirement.objects.count(), 0)

    def test_converted_requires_real_validated_fk_not_preview_names_or_units(self):
        generated = self.generate()
        row = self.conversion()["facts"][0]
        self.assertEqual(row["conversionStatusCode"], "CONVERTED")
        self.assertEqual(row["operationRequirementIds"], [generated["operationRequirementId"]])
        proof = row["requirements"][0]
        self.assertEqual(proof["sourceCalculationId"], self.source_calc.pk)
        self.assertEqual(proof["sourceFactId"], self.fact_area.pk)
        self.assertEqual(proof["operationId"], self.op_area.pk)
        self.assertEqual(Decimal(proof["workloadQuantity"]), Decimal("20"))
        self.assertEqual(proof["uomId"], self.area.pk)

    def test_one_saved_requirement_with_another_exact_mapping_is_partial(self):
        generated = self.generate()
        another = self.make_rule(self.op_area, self.area, "source_area")
        row = self.conversion()["facts"][0]
        self.assertEqual(row["conversionStatusCode"], "PARTIAL")
        self.assertEqual(row["operationRequirementIds"], [generated["operationRequirementId"]])
        self.assertIn("OPERATION_REQUIREMENT_PARTIAL", self.blocker_codes(row))
        self.assertIn(another.pk, {item["ruleId"] for item in row["ruleCandidates"]})

    def test_invalid_saved_eor_is_blocked_instead_of_zero_or_not_converted(self):
        generated = self.generate()
        # A deliberate storage fault in the disposable database tests read validation.
        EngineeringCalculationRecord.objects.filter(pk=generated["calculationId"]).update(result_hash="0" * 64)
        row = self.conversion()["facts"][0]
        self.assertEqual(row["conversionStatusCode"], "BLOCKED")
        self.assertEqual(row["requirements"], [])
        self.assertIn("OPERATION_FACT_CHANGED", self.blocker_codes(row))

    def test_no_native_rule_reports_missing_mapping_and_preserves_source(self):
        EngineeringRuleDefinition.objects.filter(pk__in=[self.rule_area.pk, self.rule_count.pk]).update(status="archived")
        row = self.conversion()["facts"][0]
        self.assertEqual(row["conversionStatusCode"], "NOT_CONVERTED")
        self.assertIn("OPERATION_RULE_MAPPING_MISSING", self.blocker_codes(row))
        self.assertEqual(row["ruleCandidates"], [])
        self.fact_area.refresh_from_db()
        self.assertEqual(self.fact_area.value, {"decimal": "20"})

    def test_same_unit_without_exact_rule_input_is_not_a_mapping(self):
        EngineeringRuleDefinition.objects.filter(pk=self.rule_area.pk).update(status="archived")
        self.make_rule(self.op_area, self.area, "another_abstract_source")
        row = self.conversion()["facts"][0]
        self.assertEqual(row["conversionStatusCode"], "NOT_CONVERTED")
        self.assertIn("OPERATION_INPUT_MAPPING_MISSING", self.blocker_codes(row))
        self.assertEqual(row["ruleCandidates"], [])

    def test_source_version_drift_invalidates_generated_proof_without_repair(self):
        self.generate()
        EngineeringSourceRecord.objects.filter(pk=self.source.pk).update(source_version="SIMULATED_FOR_TEST-V2")
        row = self.conversion()["facts"][0]
        self.assertEqual(row["conversionStatusCode"], "BLOCKED")
        self.assertIn("OPERATION_FACT_CHANGED", self.blocker_codes(row))

    def test_foreign_company_calculation_or_wrong_fact_id_cannot_be_read_as_local(self):
        foreign = Company.objects.create(code="SIM-FOREIGN-SUMMARY", name="SIMULATED_FOR_TEST foreign company")
        EngineeringCalculationRecord.objects.filter(pk=self.source_calc.pk).update(company=foreign)
        with self.assertRaises(requirements.OperationRequirementError) as caught:
            self.conversion()
        self.assertEqual(caught.exception.code, "SOURCE_CALCULATION_MISSING")
        EngineeringCalculationRecord.objects.filter(pk=self.source_calc.pk).update(company=self.company)
        with self.assertRaises(requirements.OperationRequirementError) as caught:
            self.conversion([self.fact_area.pk, 999999])
        self.assertEqual(caught.exception.code, "SOURCE_FACT_MISMATCH")

    def preview_draft(self, results, *, totals=None):
        source_rows = []
        for result in results:
            source_rows.append({"sourceSheet": result["sheet"], "sourceRow": result["row"],
                "sourceType": "房门单" if result["sheet"] == "房门单" else "三合一单",
                "materialProcessCode": "SIM-MATERIAL-CODE", "routingProcessCode": "SIM-ROUTING-CODE"})
        return {"id": self.source.pk, "rows": source_rows, "workOrderRows": deepcopy(source_rows),
            "currentInputCalculation": {"rows": deepcopy(results), "totals": deepcopy(totals or []),
                "resultNature": "CURRENT_PRODUCT_DESIGN_CALCULATION_PREVIEW"}}

    @staticmethod
    def preview_result(index, unit, value, *, project="Abstract source quantity", sheet="房门单"):
        return {"id": f"sim-result-{index}", "sourceKey": f"{sheet}:{index}", "sheet": sheet, "row": index,
            "column": "SIM", "project": project, "value": value, "unit": unit,
            "resultScope": "SIMULATED_FOR_TEST", "ruleVersion": "SIM-V1", "statusLabel": "SIMULATED_FOR_TEST"}

    def summary(self, draft=None, *, explicit=True):
        return self.readonly_call(lambda: build_engineering_workload_summary(user=self.user, draft=draft,
            source_calculation_ids=[self.source_calc.pk] if explicit else None))

    def test_preview_retains_every_unit_missing_value_zero_and_missing_group_code(self):
        units = ["m", "m2", "套", "扇", "块", "支", "条", "mm", None]
        results = [self.preview_result(index + 1, unit, "0" if index == 2 else None if index == 8 else str(index + 1))
                   for index, unit in enumerate(units)]
        draft = self.preview_draft(results)
        draft["rows"][5]["routingProcessCode"] = ""
        draft["workOrderRows"][5]["routingProcessCode"] = ""
        before = deepcopy(draft)
        summary = self.summary(draft, explicit=False)
        for view in summary["workshopViews"].values():
            self.assertEqual(len(view["rows"]), len(results))
            by_id = {item["id"]: row for row in view["rows"] for item in row["contributions"]["items"]}
            self.assertEqual(set(by_id), {row["id"] for row in results})
            for result in results:
                row = by_id[result["id"]]
                self.assertEqual(row["quantity"], result["value"])
                self.assertEqual(row["uomCode"], result["unit"])
                self.assertEqual(row["statusCode"], "PREVIEW_UNBOUND")
                self.assertEqual(row["operationRequirementIds"], [])
        self.assertEqual(summary["workshopViews"]["wood"]["rows"][5]["sourceCode"], "")
        self.assertEqual(draft, before)

    def test_existing_additive_contract_keeps_contributions_and_does_not_mix_units(self):
        results = [self.preview_result(1, "m2", "1.1"),
                   self.preview_result(2, "m2", "2.2", sheet="三合一生产单"),
                   self.preview_result(3, "套", "7")]
        draft = self.preview_draft(results, totals=[{"ids": [row["id"] for row in results], "net": "10.3"}])
        rows = self.summary(draft, explicit=False)["workshopViews"]["wood"]["rows"]
        self.assertEqual(len(rows), 2)
        area = next(row for row in rows if row["uomCode"] == "m2")
        count = next(row for row in rows if row["uomCode"] == "套")
        self.assertEqual(area["quantity"], "3.3")
        self.assertEqual(area["contributions"]["door"], "1.1")
        self.assertEqual(area["contributions"]["threeInOne"], "2.2")
        self.assertEqual(count["quantity"], "7")
        self.assertEqual(len(area["contributions"]["items"]), 2)

    def test_dimensions_without_additive_contract_remain_individual_source_results(self):
        draft = self.preview_draft([self.preview_result(1, "mm", "800"), self.preview_result(2, "mm", "900")])
        rows = self.summary(draft, explicit=False)["workshopViews"]["wood"]["rows"]
        self.assertEqual([row["quantity"] for row in rows], ["800", "900"])
        self.assertTrue(all(row["aggregationBasis"] == "INDIVIDUAL_SOURCE_RESULT" for row in rows))

    def test_current_and_historical_preview_scopes_are_not_added_or_overwritten(self):
        draft = self.preview_draft([self.preview_result(1, "m2", "99")])
        draft["sourceCalculation"] = {"rows": [self.preview_result(1, "m2", "20")],
            "totals": [{"ids": ["sim-result-1"], "net": "20"}],
            "resultNature": "HISTORICAL_APPROVED_SOURCE_PREVIEW"}
        draft["currentInputCalculation"]["totals"] = [{"ids": ["sim-result-1"], "net": "99"}]
        rows = self.summary(draft, explicit=False)["workshopViews"]["wood"]["rows"]
        self.assertEqual(len(rows), 2)
        self.assertEqual({(row["sourceNatureCode"], row["quantity"]) for row in rows}, {
            ("CURRENT_PRODUCT_DESIGN_CALCULATION_PREVIEW", "99"), ("HISTORICAL_APPROVED_SOURCE_PREVIEW", "20")})

    def test_preview_cannot_claim_saved_fact_identity_and_does_not_hide_converted_facts(self):
        generated = self.generate()
        result = self.preview_result(1, "m2", "20")
        result.update(sourceFactId=self.fact_area.pk, sourceCalculationId=self.source_calc.pk,
                      operationRequirementIds=[generated["operationRequirementId"]], statusCode="CONVERTED")
        summary = self.summary(self.preview_draft([result]))
        preview = summary["workshopViews"]["wood"]["rows"][0]
        self.assertEqual(preview["statusCode"], "PREVIEW_UNBOUND")
        self.assertEqual(preview["operationRequirementIds"], [])
        self.assertIsNone(preview["UOM"]["id"])
        formal = next(row for row in summary["formalSavedFacts"] if row["sourceFactId"] == self.fact_area.pk)
        self.assertEqual(formal["statusCode"], "CONVERTED")
        self.assertEqual(formal["operationRequirementIds"], [generated["operationRequirementId"]])
        self.assertEqual(formal["UOM"]["id"], self.area.pk)
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            self.assertEqual(summary[key]["formalSavedFacts"], summary["formalSavedFacts"])
            self.assertEqual(summary[key]["workshopViews"], summary["workshopViews"])

    def test_source_quantity_eor_quantity_and_plan_allocation_are_separate_scopes(self):
        spec = deepcopy(self.rule_area.specification)
        spec["expression"] = "source_area * 2"
        rule = self.initial(EngineeringRuleDefinition, "draft", company=self.company,
            rule_code="SIM-EOR-DOUBLE", rule_name="SIMULATED_FOR_TEST explicit workload scale", version="V1",
            rule_kind="formula", specification=spec)
        self.advance(rule, "reviewed")
        self.advance(rule, "released")
        EngineeringRuleDefinition.objects.filter(pk=self.rule_area.pk).update(status="archived")
        generated = self.generate(rule=rule)
        allocated = self.allocate(generated)
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.get(pk=allocated["allocationId"]).allocated_quantity,
                         Decimal("120"))
        summary = self.summary()
        formal = next(row for row in summary["formalSavedFacts"] if row["sourceFactId"] == self.fact_area.pk)
        self.assertEqual(formal["quantity"], "20")
        self.assertEqual(formal["contributions"]["items"][0]["quantity"], "20")
        self.assertEqual(Decimal(formal["conversion"]["requirements"][0]["workloadQuantity"]), Decimal("40"))
        self.assertEqual(formal["conversion"]["requirements"][0]["quantityBasis"], "PER_BASIS_QUANTITY")

    def test_conversion_read_failure_keeps_saved_source_quantity_and_unknown_reason(self):
        with patch.object(requirements.OperationRequirementService, "read_source_conversion",
                          side_effect=requirements.OperationRequirementError("SOURCE_CONVERSION_READ_FAILED", "SIMULATED_FOR_TEST load failure")):
            summary = self.summary()
        formal = next(row for row in summary["formalSavedFacts"] if row["sourceFactId"] == self.fact_area.pk)
        self.assertEqual(formal["quantity"], "20")
        self.assertEqual(formal["operationRequirementIds"], [])
        self.assertEqual(formal["statusCode"], "BLOCKED")
        self.assertIn("SOURCE_CONVERSION_READ_FAILED", {row["code"] for row in formal["missingReasons"]})

    def test_failed_preview_read_reports_unknown_count_and_keeps_failure_evidence(self):
        draft = {"id": self.source.pk, "rows": [], "sourceCalculation": {
            "rows": [], "totals": [], "readStatusLabel": "SIMULATED_FOR_TEST source unavailable",
            "detail": "SIMULATED_FOR_TEST unreadable source", "formalResultsCreated": False}}
        summary = self.summary(draft, explicit=False)
        snapshot = summary["sourceSnapshots"][0]
        self.assertEqual(snapshot["readStatus"], "unknown")
        self.assertIsNone(snapshot["resultCount"])
        self.assertEqual(snapshot["detail"], draft["sourceCalculation"]["detail"])
        self.assertIsNone(summary["counts"]["previewResultCount"])
        self.assertIn("SOURCE_PREVIEW_READ_FAILED", {row["code"] for row in summary["missingReasons"]})
        self.assertEqual(summary["formalSavedFacts"], [])

    def test_default_formal_source_is_manufacturing_output_pin_and_never_latest_run(self):
        attribute = SalesOrderItemEngineeringAttribute.objects.create(sales_order_item=self.item,
            raw_source="SIMULATED_FOR_TEST", raw_sheet="Abstract source", raw_field="quantity",
            raw_value={"decimal": "5"}, canonical_field="sim_quantity", normalized_value={"decimal": "5"},
            value_type="decimal", unit=self.pcs, source_type="ENGINEERING_INPUT", created_by=self.user)
        ProductDesignItem.objects.create(company=self.company, sales_order_item=self.item, source_record=self.source,
            source_attribute=attribute, item_no="SIM-SUMMARY-DESIGN", item_name="Abstract source item",
            design_data_nature="SIMULATED_FOR_TEST", source_version=self.source.source_version,
            source_content_hash=self.source.content_hash)
        generated = self.generate()
        summary = self.summary({"id": self.source.pk}, explicit=False)
        self.assertEqual(summary["fixedSourcePins"], [{"manufacturingOutputId": self.output.pk,
            "sourceCalculationId": self.source_calc.pk, "sourceRecordId": self.source.pk,
            "salesOrderItemId": self.item.pk, "authority": "MANUFACTURING_OUTPUT_FIXED_CALCULATION_FK"}])
        self.assertEqual({row["sourceCalculationId"] for row in summary["formalSavedFacts"]}, {self.source_calc.pk})
        self.assertNotEqual(summary["fixedSourcePins"][0]["sourceCalculationId"], generated["calculationId"])

    def test_foreign_company_draft_is_rejected_before_preview_projection(self):
        foreign = Company.objects.create(code="SIM-FOREIGN-PREVIEW", name="SIMULATED_FOR_TEST foreign source")
        EngineeringSourceRecord.objects.filter(pk=self.source.pk).update(company=foreign)
        draft = self.preview_draft([self.preview_result(1, "套", "7")])
        with self.assertRaises(requirements.OperationRequirementError) as caught:
            self.summary(draft, explicit=False)
        self.assertEqual(caught.exception.code, "SOURCE_FACT_MISMATCH")

    def test_get_summary_failure_appends_unknown_facts_without_replacing_original_payload(self):
        from .calculation_batch_views import EngineeringCalculationBatchView

        draft = self.preview_draft([self.preview_result(1, "套", "7")])
        draft.update(sourceVersion="SIM-V1", originalField={"source": "SIMULATED_FOR_TEST", "quantity": "7"})
        response_holder = []
        request = APIRequestFactory().get("/api/pde/a1-engineering/calculations/batch-reuse/",
            {"action": "draftCatalog", "orderEngineeringInstanceId": self.instance.pk})
        force_authenticate(request, user=self.user)

        def read_view():
            response = EngineeringCalculationBatchView.as_view()(request)
            response_holder.append(response)
            return response.data["drafts"][0]["engineeringWorkloadSummary"]

        with patch("pde.calculation_batch_views.service.verify_read_isolation", return_value={"nonProduction": True}), \
             patch("pde.calculation_batch_views.service.authorize_read"), \
             patch("pde.calculation_batch_views.service.draft_catalog", return_value={"drafts": [deepcopy(draft)]}), \
             patch("pde.calculation_batch_views.build_engineering_workload_summary",
                   side_effect=requirements.OperationRequirementError("SIMULATED_SUMMARY_READ_FAILED", "SIMULATED_FOR_TEST failure")):
            summary = self.readonly_call(read_view)
        self.assertEqual(response_holder[0].status_code, 200)
        returned = response_holder[0].data["drafts"][0]
        self.assertEqual({key: value for key, value in returned.items() if key != "engineeringWorkloadSummary"}, draft)
        self.assertEqual(summary["readStatus"], "read_failed")
        self.assertIsNone(summary["counts"]["formalFactCount"])
        self.assertIsNone(summary["counts"]["previewResultCount"])
        self.assertEqual(summary["formalSavedFacts"], [])
        self.assertEqual(summary["httpStatus"], 200)
        self.assertEqual(summary["apiUrl"], request.path)
        self.assertEqual(summary["tenantId"], self.company.pk)
        self.assertEqual(summary["factLoadStatus"], "read_failed")
        self.assertEqual(summary["errorCode"], "SIMULATED_SUMMARY_READ_FAILED")
        self.assertTrue(summary["loadedAt"])
        self.assertTrue(summary["batchId"])
        self.assert_same_fact_surfaces(summary)

    def test_data_type_retains_project_declaration_or_formal_dimension_without_eor_eligibility(self):
        EngineeringRuleDefinition.objects.filter(pk__in=[self.rule_area.pk, self.rule_count.pk]).update(status="archived")
        first = self.preview_result(1, "m2", "20", project="Abstract source declaration")
        unknown = self.preview_result(2, "m2", "9", project="")
        summary = self.summary(self.preview_draft([first, unknown]))
        preview = summary["workshopViews"]["wood"]["rows"]
        self.assertEqual(preview[0]["dataTypeCode"], "SOURCE_PROJECT_DECLARATION")
        self.assertEqual(preview[0]["dataTypeLabel"], first["project"])
        self.assertNotEqual(preview[0]["dataTypeLabel"], preview[0]["sourceNatureLabel"])
        self.assertEqual(preview[1]["dataTypeCode"], "UNKNOWN")
        self.assertEqual(preview[1]["statusCode"], "PREVIEW_UNBOUND")
        formal = {row["sourceFactId"]: row for row in summary["formalSavedFacts"]}
        self.assertEqual((formal[self.fact_area.pk]["dataTypeCode"], formal[self.fact_area.pk]["dataTypeLabel"]), ("AREA", "面积"))
        self.assertEqual((formal[self.fact_count.pk]["dataTypeCode"], formal[self.fact_count.pk]["dataTypeLabel"]), ("QUANTITY", "数量"))
        for row in formal.values():
            self.assertEqual(row["dataTypeAuthority"], "FORMAL_UOM_DIMENSION")
            self.assertEqual(row["statusCode"], "NOT_CONVERTED")
            self.assertEqual(row["operationRequirementIds"], [])

    def test_domain_and_stamped_success_or_failure_preserve_one_five_surface_transport_context(self):
        domain = self.summary()
        self.assertIsNone(domain["apiUrl"])
        self.assertIsNone(domain["httpStatus"])
        self.assertEqual(domain["tenantId"], self.company.pk)
        self.assert_same_fact_surfaces(domain)
        before = deepcopy(domain)
        stamped = self.readonly_call(lambda: stamp_engineering_workload_summary(domain,
            tenant_id=self.company.pk, api_url="/api/SIMULATED_FOR_TEST/summary/", http_status=200,
            batch_id="SIMULATED_FOR_TEST-STAMP", loaded_at="2026-10-13T09:01:02Z"))
        self.assertEqual(domain, before)
        self.assertEqual(stamped["httpStatus"], 200)
        self.assertEqual(stamped["batchId"], "SIMULATED_FOR_TEST-STAMP")
        self.assertEqual(stamped["loadedAt"], "2026-10-13T09:01:02Z")
        self.assert_same_fact_surfaces(stamped)
        failure = self.readonly_call(lambda: engineering_workload_summary_read_failure(
            OSError("SIMULATED_FOR_TEST unavailable"), source_record_id=self.source.pk))
        self.assertIsNone(failure["httpStatus"])
        self.assertEqual(failure["factLoadStatus"], "read_failed")
        self.assertTrue(all(value is None for value in failure["counts"].values()))
        self.assert_same_fact_surfaces(failure)

    def detail_view_readback(self, *, projection_failure=None):
        from .engineering_calculation_service import EngineeringCalculationService
        from .engineering_workload_summary_views import EngineeringWorkloadCalculationTraceView

        original = EngineeringCalculationService.get(user=self.user, object_id=self.source_calc.pk)
        request = APIRequestFactory().get(f"/api/pde/a1-engineering/calculations/{self.source_calc.pk}/")
        force_authenticate(request, user=self.user)
        response_holder = []

        def read_view():
            response = EngineeringWorkloadCalculationTraceView.as_view()(request, object_id=self.source_calc.pk)
            response_holder.append(response)
            return response.data["calculation"]["engineeringWorkloadSummary"]

        with ExitStack() as stack:
            if projection_failure is not None:
                stack.enter_context(patch("pde.engineering_workload_summary_views.build_engineering_workload_summary",
                    side_effect=projection_failure))
            summary = self.readonly_call(read_view)
        response = response_holder[0]
        self.assertEqual(response.status_code, 200)
        self.assertEqual({key: value for key, value in response.data["calculation"].items()
                          if key != "engineeringWorkloadSummary"}, original)
        self.assertEqual(response.data["factSource"], "server")
        self.assertEqual(response.data["localStorageFormalFactCount"], 0)
        self.assertEqual(summary["httpStatus"], response.status_code)
        self.assertEqual(summary["apiUrl"], request.path)
        self.assertEqual(summary["tenantId"], self.company.pk)
        self.assert_same_fact_surfaces(summary)
        return summary

    def test_detail_get_success_preserves_original_fields_and_stamps_all_facts(self):
        summary = self.detail_view_readback()
        self.assertEqual(summary["factLoadStatus"], "loaded")
        self.assertEqual(summary["counts"]["formalFactCount"], 2)
        self.assertEqual(summary["errorCode"], "")
        self.assertEqual(summary["errorMessage"], "")
        self.assertEqual({row["sourceFactId"] for row in summary["formalSavedFacts"]}, {self.fact_area.pk, self.fact_count.pk})

    def test_detail_get_projection_failure_keeps_original_200_and_unknown_counts(self):
        summary = self.detail_view_readback(projection_failure=OSError("SIMULATED_FOR_TEST unavailable summary"))
        self.assertEqual(summary["factLoadStatus"], "read_failed")
        self.assertEqual(summary["errorCode"], "ENGINEERING_SUMMARY_READ_FAILED")
        self.assertEqual(summary["errorMessage"], "SIMULATED_FOR_TEST unavailable summary")
        self.assertTrue(all(value is None for value in summary["counts"].values()))
        self.assertEqual(summary["formalSavedFacts"], [])
