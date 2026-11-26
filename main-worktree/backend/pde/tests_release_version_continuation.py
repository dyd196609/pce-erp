"""Version admission tests; no publication, employee or source facts are invented."""
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from . import bom_version_release_preflight as bom
from . import engineering_document_version_review_service as document
from .engineering_calculation_continuation_service import EngineeringCalculationContinuationError


class ReleaseVersionContinuationTests(SimpleTestCase):
    def setUp(self):
        self.previous = NS(pk=40, company_id=1, sales_order_item_id=3,
            engineering_instance_id=2, supersedes_id=None,
            trace={"baselineReference": {"id": 20, "snapshotHash": "old-baseline"}})
        self.current = NS(pk=41, company_id=1, sales_order_item_id=3,
            engineering_instance_id=2, supersedes_id=40)
        self.version = NS(pk=61, bom_id=5, bom_scope="order_specific",
            source_calculation_id=41, source_calculation=self.current,
            order_engineering_instance_id=2,
            order_engineering_instance=NS(sales_order_item=NS(sales_order_id=3)))
        self.row = NS(previous_calculation=self.previous)
        self.proof = {"continuationId": 9, "newCalculationId": 41,
            "predecessorCalculationId": 40, "salesOrderItemId": 3,
            "orderEngineeringInstanceId": 2}
        self.baseline = NS(pk=20, snapshot_hash="old-baseline")

    def _candidate(self, *, identity=60, calculation=40, instance=2, status="released"):
        return NS(id=identity, bom_version=f"CALC-{calculation}", revision=1,
            status=status, effective_date=None, expire_date=None,
            source_calculation_id=calculation, order_engineering_instance_id=instance,
            bom_scope="order_specific")

    def _partition(self, candidates, *, proof_error=None, proof=None, baseline=True):
        with patch("pde.models.EngineeringCalculationContinuation.objects") as records, \
                patch("pde.engineering_calculation_continuation_service.continuation_proof") as validate, \
                patch.object(bom.OrderEngineeringBaseline, "objects") as baselines, \
                patch.object(bom.BOMVersion, "objects") as versions:
            records.filter.return_value.select_related.return_value.first.side_effect = [self.row, None]
            if proof_error:
                validate.side_effect = proof_error
            else:
                validate.return_value = proof or self.proof
            baselines.filter.return_value.first.return_value = self.baseline if baseline else None
            versions.filter.return_value.exclude.return_value.order_by.return_value = candidates
            result = bom._partition_bom_version_conflicts(self.version)
            records.filter.assert_any_call(new_calculation_id=41, status="committed")
            validate.assert_called_once_with(self.row)
            return result

    def test_proven_released_ancestor_can_coexist_but_same_source_remains_competing(self):
        historical, competing, blockers = self._partition([
            self._candidate(), self._candidate(identity=62, calculation=41)])
        self.assertEqual([row["id"] for row in historical], [60])
        self.assertEqual(historical[0]["baselineId"], 20)
        self.assertEqual(historical[0]["continuationProofs"], [self.proof])
        self.assertEqual([row["id"] for row in competing], [62])
        self.assertEqual(blockers, [])

    def test_uncommitted_or_unproven_lineage_does_not_exempt_old_release(self):
        error = EngineeringCalculationContinuationError("CONTINUATION_COMMIT_UNPROVEN", "unproven")
        historical, competing, blockers = self._partition([self._candidate()], proof_error=error)
        self.assertEqual(historical, [])
        self.assertEqual([row["id"] for row in competing], [60])
        self.assertEqual(blockers[0]["code"], "CONTINUATION_COMMIT_UNPROVEN")

    def test_missing_continuation_never_uses_supersedes_alone(self):
        with patch("pde.models.EngineeringCalculationContinuation.objects") as records:
            records.filter.return_value.select_related.return_value.first.return_value = None
            ancestors, blockers = bom._proven_predecessor_calculations(self.version)
        self.assertEqual(ancestors, {})
        self.assertEqual(blockers, [])

    def test_tampered_native_proof_cannot_release_competing_version(self):
        error = EngineeringCalculationContinuationError("CONTINUATION_NEW_MAIN_CHANGED", "changed")
        historical, competing, blockers = self._partition([self._candidate()], proof_error=error)
        self.assertFalse(historical)
        self.assertEqual(len(competing), 1)
        self.assertEqual(blockers[0]["code"], "CONTINUATION_NEW_MAIN_CHANGED")

    def test_cross_instance_or_nonterminal_bom_is_still_competing(self):
        historical, competing, blockers = self._partition([
            self._candidate(instance=7), self._candidate(identity=63, status="draft")])
        self.assertEqual(historical, [])
        self.assertEqual({row["id"] for row in competing}, {60, 63})
        self.assertEqual(blockers, [])

    def test_baseline_hash_or_exact_lineage_scope_mismatch_is_rejected(self):
        for overrides, baseline in [({"orderEngineeringInstanceId": 7}, True), ({}, False)]:
            with self.subTest(overrides=overrides, baseline=baseline):
                historical, competing, blockers = self._partition([self._candidate()],
                    proof={**self.proof, **overrides}, baseline=baseline)
                self.assertFalse(historical)
                self.assertEqual(len(competing), 1)
                self.assertEqual(blockers[0]["code"], "BOM_ANCESTOR_SCOPE_UNPROVEN")

    def test_predecessor_of_other_company_is_not_historical(self):
        self.previous.company_id = 8
        historical, competing, blockers = self._partition([self._candidate()])
        self.assertFalse(historical)
        self.assertEqual(len(competing), 1)
        self.assertEqual(blockers[0]["code"], "BOM_ANCESTOR_SCOPE_UNPROVEN")


class DocumentFixedVersionSourceTests(SimpleTestCase):
    def _project(self, *, resolved_calculation=41):
        item = NS(line_no=1, sales_order=NS(order_no="FIXTURE-ORDER"))
        version = NS(pk=71, document_id=70, document_version="V2", status="draft",
            release_subject_type="ORDER_ENGINEERED_PRODUCT",
            order_engineering_instance_id=2, order_engineering_instance=NS(sales_order_item=item),
            order_engineering_baseline_id=21, order_engineering_baseline=NS(status="confirmed"),
            engineering_calculation_id=41, engineering_calculation=NS(status="completed"),
            related_bom_id=61, related_bom=NS(status="released"),
            related_routing_id=81, related_routing=NS(status="released", routing_version="V2", revision=2,
                steps=NS(count=lambda: 1)),
            full_clean=lambda: None)
        chain = NS(instance=NS(pk=2), baseline=NS(pk=21), calculation=NS(pk=resolved_calculation),
            bom_version=NS(pk=61), routing=NS(pk=8), routing_version=NS(pk=81),
            as_dict=lambda: {"calculationId": resolved_calculation})
        version.related_routing.routing_id = 8
        user = NS(pk=9)
        with patch.object(document, "_company_id", return_value=1), \
                patch.object(document.OrderEngineeringDocumentRegistrationService, "resolve_chain", return_value=chain) as resolve, \
                patch.object(document.ProductManufacturingOutput, "objects") as outputs:
            outputs.filter.return_value.count.return_value = 0
            result = document.project_source_completeness(version, user)
        resolve.assert_called_once_with(user=user, order_no="FIXTURE-ORDER", line_no=1,
            baseline_id=21, calculation_id=41, bom_version_id=61, routing_version_id=81)
        return result

    def test_exact_four_version_ids_are_forwarded_for_multi_version_source(self):
        result = self._project()
        self.assertTrue(result["complete"])

    def test_source_resolver_result_must_still_equal_fixed_document_identity(self):
        result = self._project(resolved_calculation=40)
        self.assertFalse(result["complete"])
        gate = next(row for row in result["gates"] if row["code"] == "EXACT_FORMAL_SOURCE_CHAIN")
        self.assertEqual(gate["statusCode"], "BLOCKED")
