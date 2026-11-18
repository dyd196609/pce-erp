"""SIMULATED_FOR_TEST: request-local reads preserve the complete EOR proof.

Only Django's disposable test database receives fixture writes. These tests do
not use the acceptance database, real order identities, or timing thresholds.
"""

from contextlib import ExitStack
from unittest.mock import Mock, patch

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from . import manufacturing_rule_configuration as manufacturing
from . import operation_requirement_service as requirements
from . import tests_engineering_workload_summary as summary_fixtures
from . import tests_manufacturing_eor_configuration as manufacturing_fixtures
from .models import EngineeringCalculationRecord, ManufacturingMode, StandardCapacity


class RequestLocalReadHelperTests(SimpleTestCase):
    def test_reuse_requires_the_same_explicit_scope_and_identity(self):
        loader = Mock(side_effect=[object(), object(), object(), object()])
        scope = {}
        first = requirements._read_once(scope, ("company", 1), loader)
        self.assertIs(requirements._read_once(scope, ("company", 1), loader), first)
        self.assertIsNot(requirements._read_once({}, ("company", 1), loader), first)
        requirements._read_once(None, ("company", 1), loader)
        requirements._read_once(None, ("company", 1), loader)
        self.assertEqual(loader.call_count, 4)

    def test_loader_failure_is_retried_and_never_becomes_a_saved_proof(self):
        failure = requirements.OperationRequirementError("SIM_READ_FAILED", "SIMULATED_FOR_TEST")
        recovered = object()
        loader = Mock(side_effect=[failure, recovered])
        scope = {}
        with self.assertRaises(requirements.OperationRequirementError):
            requirements._read_once(scope, "proof", loader)
        self.assertNotIn("proof", scope)
        self.assertIs(requirements._read_once(scope, "proof", loader), recovered)
        self.assertEqual(loader.call_count, 2)


class EngineeringSourceReadPerformanceTests(TestCase):
    # Reuse only isolated fixture builders, without inheriting unrelated tests.
    initial = manufacturing_fixtures.ManufacturingEorConfigurationTests.initial
    advance = manufacturing_fixtures.ManufacturingEorConfigurationTests.advance
    make_rule = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_rule
    make_source_fact = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_source_fact
    generate = manufacturing_fixtures.ManufacturingEorConfigurationTests.generate
    allocate = manufacturing_fixtures.ManufacturingEorConfigurationTests.allocate
    make_mode = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_mode
    make_capacity = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_capacity
    make_mapping = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_mapping

    def setUp(self):
        manufacturing_fixtures.ManufacturingEorConfigurationTests.setUp(self)

    def protected_snapshot(self):
        result = summary_fixtures.EngineeringWorkloadSummaryTests.protected_snapshot(self)
        for model in (ManufacturingMode, StandardCapacity):
            result[model._meta.label] = list(model.objects.order_by("pk").values())
        return result

    def readonly_call(self, action):
        before = self.protected_snapshot()
        with ExitStack() as stack:
            for target in (
                "pde.operation_requirement_service.evaluate_specification",
                "pde.operation_requirement_service.OperationRequirementService.generate",
                "pde.engineering_calculation_service.EngineeringCalculationService.execute",
            ):
                stack.enter_context(patch(target, side_effect=AssertionError("A read must not execute or generate")))
            queries = stack.enter_context(CaptureQueriesContext(connection))
            result = action()
        writes = [row["sql"] for row in queries if row["sql"].lstrip().split(" ", 1)[0].upper() in
                  {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"}]
        self.assertEqual(writes, [])
        self.assertEqual(self.protected_snapshot(), before)
        return result, sum(row["sql"].lstrip().upper().startswith("SELECT") for row in queries)

    def context(self, *, read_cache=None):
        return requirements._generation_context(self.company.pk, self.source_calc.pk,
            self.fact_area.pk, self.mapping.pk, evaluate=False, read_cache=read_cache)

    def conversion(self):
        return requirements.OperationRequirementService.read_source_conversion(
            user=self.user, source_calculation_id=self.source_calc.pk,
            source_fact_ids=[self.fact_area.pk])

    def test_repeated_context_reuses_reads_but_reruns_validation(self):
        baseline, baseline_queries = self.readonly_call(self.context)
        scope = {}
        with patch.object(requirements, "_source_output_proof", wraps=requirements._source_output_proof) as source_proof, \
             patch.object(requirements, "validate_specification", wraps=requirements.validate_specification) as specification, \
             patch.object(manufacturing, "_configuration", wraps=manufacturing._configuration) as configuration, \
             patch.object(manufacturing, "_formal_references", wraps=manufacturing._formal_references) as references:
            first, first_queries = self.readonly_call(lambda: self.context(read_cache=scope))
            repeated, repeated_queries = self.readonly_call(lambda: self.context(read_cache=scope))
        self.assertEqual(first, baseline)
        self.assertEqual(repeated, baseline)
        self.assertGreater(baseline_queries, 0)
        self.assertLess(repeated_queries, first_queries)
        self.assertEqual(source_proof.call_count, 2)
        self.assertEqual(specification.call_count, 2)
        self.assertEqual(configuration.call_count, 2)
        self.assertEqual(references.call_count, 1)

    def test_source_specific_selector_is_checked_after_a_resource_cache_hit(self):
        scope = {}
        context, _ = self.readonly_call(lambda: self.context(read_cache=scope))
        # An in-memory source fault must not be hidden by a cached resource proof.
        context["fact"].trace = {**context["fact"].trace, "sourceKind": "SIM_WRONG_SOURCE"}

        def rejected():
            with self.assertRaises(requirements.OperationRequirementError) as caught:
                self.context(read_cache=scope)
            self.assertEqual(caught.exception.code, "MANUFACTURING_SOURCE_SELECTOR_MISMATCH")

        self.readonly_call(rejected)
        recovered, _ = self.readonly_call(self.context)
        self.assertEqual(recovered["fact"].trace["sourceKind"], "SIMULATED_FOR_TEST")

    def test_failed_formal_resource_proof_is_not_cached(self):
        # Deliberate fault only in the disposable fixture database.
        StandardCapacity.objects.filter(pk=self.capacity.pk).update(is_active=False)
        scope = {}

        def rejected_twice():
            for _ in range(2):
                with self.assertRaises(requirements.OperationRequirementError) as caught:
                    self.context(read_cache=scope)
                self.assertEqual(caught.exception.code, "MANUFACTURING_CAPACITY_INVALID")

        with patch.object(manufacturing, "_formal_references", wraps=manufacturing._formal_references) as references:
            self.readonly_call(rejected_twice)
        self.assertEqual(references.call_count, 2)
        self.assertFalse(any(key[0] == "manufacturing_references" for key in scope))

    def test_unit_cache_does_not_cross_company_or_cache_a_failure_verdict(self):
        scope = {}

        def read_units():
            self.assertEqual(requirements._unit(self.area.pk, self.company.pk, read_cache=scope).pk, self.area.pk)
            for code in ("SIM_SCOPE_A", "SIM_SCOPE_B"):
                with self.assertRaises(requirements.OperationRequirementError) as caught:
                    requirements._unit(self.area.pk, self.company.pk + 100000, code, read_cache=scope)
                self.assertEqual(caught.exception.code, code)

        self.readonly_call(read_units)

    def test_cached_and_uncached_conversion_have_identical_complete_output(self):
        generated = self.generate(rule=self.mapping)
        for _ in range(3):
            self.make_mapping(self.fact_area, self.op_area, self.area,
                mode=self.mode, capacity=self.capacity)
        original_context = requirements._generation_context

        def uncached_context(*args, **kwargs):
            kwargs["read_cache"] = None
            return original_context(*args, **kwargs)

        with patch.object(requirements, "_generation_context", side_effect=uncached_context):
            uncached, uncached_queries = self.readonly_call(self.conversion)
        with patch.object(requirements, "_validate_requirement", wraps=requirements._validate_requirement) as validate:
            cached, cached_queries = self.readonly_call(self.conversion)
        self.assertEqual(cached, uncached)
        self.assertEqual(cached["businessWriteCount"], 0)
        self.assertEqual(cached["facts"][0]["operationRequirementIds"], [generated["operationRequirementId"]])
        self.assertEqual(validate.call_count, 1)
        self.assertLess(cached_queries, uncached_queries)

    def test_a_new_source_read_rechecks_persisted_requirement_hashes(self):
        generated = self.generate(rule=self.mapping)
        before, _ = self.readonly_call(self.conversion)
        self.assertIn(generated["operationRequirementId"], before["facts"][0]["operationRequirementIds"])
        EngineeringCalculationRecord.objects.filter(pk=generated["calculationId"]).update(result_hash="0" * 64)
        after, _ = self.readonly_call(self.conversion)
        fact = after["facts"][0]
        self.assertEqual(fact["conversionStatusCode"], "BLOCKED")
        self.assertEqual(fact["requirements"], [])
        self.assertIn("OPERATION_FACT_CHANGED", {item["code"] for item in fact["blockers"]})

    def test_new_read_reloads_resource_state_instead_of_reusing_previous_success(self):
        first, _ = self.readonly_call(self.conversion)
        candidate = next(item for item in first["facts"][0]["ruleCandidates"] if item["ruleId"] == self.mapping.pk)
        self.assertTrue(candidate["ready"])
        StandardCapacity.objects.filter(pk=self.capacity.pk).update(is_active=False)
        second, _ = self.readonly_call(self.conversion)
        candidate = next(item for item in second["facts"][0]["ruleCandidates"] if item["ruleId"] == self.mapping.pk)
        self.assertFalse(candidate["ready"])
        self.assertEqual(candidate["blockers"][0]["code"], "MANUFACTURING_CAPACITY_INVALID")

    def test_source_read_still_requires_formal_view_permission(self):
        denied = requirements.OperationRequirementError("PERMISSION_DENIED", "SIMULATED_FOR_TEST denied")
        with patch.object(requirements, "_authorize", side_effect=denied), \
             patch.object(requirements, "_generation_context", wraps=requirements._generation_context) as context:
            def rejected():
                with self.assertRaises(requirements.OperationRequirementError) as caught:
                    self.conversion()
                self.assertEqual(caught.exception.code, "PERMISSION_DENIED")
            self.readonly_call(rejected)
        context.assert_not_called()
