"""SIMULATED_FOR_TEST: raw manufacturing reads do not memoize failure verdicts.

Twelve real released mappings share formal fixture resources in Django's
disposable database. Native configuration/reference/source checks run for every
mapping. Only fixture construction and explicit fault injection may write.
"""

from contextlib import ExitStack
import json
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from masterdata.models import UnitOfMeasure
from system.models import Company, OrganizationOperatingAuditRecord, Process, Workshop
from workflow_runtime.models import BusinessStateTransition
from . import manufacturing_rule_configuration as manufacturing
from . import operation_requirement_service as operation
from . import tests_manufacturing_eor_configuration as fixtures
from .engineering_calculation_service import EngineeringCalculationService
from .engineering_fact_extension_service import EngineeringFactExtensionService
from .models import (
    CapacityProductType, EngineeringCalculationDetail, EngineeringCalculationRecord,
    EngineeringDerivedFact, EngineeringOperationRequirement, EngineeringRuleDefinition,
    ManufacturingMode, ProductionPlanOperationRequirementAllocation,
    StandardCapacity, WorkCenter, WorkCenterOperationCapability,
)
from .operation_requirement_correction_service import OperationRequirementCorrectionService


class WorkloadManufacturingReadPerformanceTests(TestCase):
    def setUp(self):
        # Construct existing fixtures without inheriting or rediscovering tests.
        self.f = fixtures.ManufacturingEorConfigurationTests(methodName="runTest")
        self.f.setUp()
        rules = [self.f.mapping]
        for _ in range(11):
            rules.append(self.f.make_mapping(
                self.f.fact_area, self.f.op_area, self.f.area,
                mode=self.f.mode, capacity=self.f.capacity))
        self.rule_ids = [rule.pk for rule in rules]
        self.assertEqual(len(set(self.rule_ids)), 12)
        self.producer_id = self.f.fact_area.source_detail.rule_id

    def rules(self):
        return list(EngineeringRuleDefinition.objects.filter(pk__in=self.rule_ids).order_by("pk"))

    def snapshot(self):
        # Deliberately excludes account credentials and session values.
        models = (
            Company, Workshop, Process, UnitOfMeasure, ManufacturingMode, WorkCenter,
            WorkCenterOperationCapability, CapacityProductType, StandardCapacity,
            EngineeringRuleDefinition, EngineeringCalculationRecord, EngineeringCalculationDetail,
            EngineeringDerivedFact, EngineeringOperationRequirement,
            ProductionPlanOperationRequirementAllocation, OrganizationOperatingAuditRecord,
            BusinessStateTransition,
        )
        return {model._meta.label: list(model.objects.order_by("pk").values()) for model in models}

    def readonly(self, action):
        before, queries = self.snapshot(), None
        try:
            with ExitStack() as stack:
                for owner, name in (
                    (operation.OperationRequirementService, "generate"),
                    (operation.OperationRequirementService, "allocate"),
                    (operation.OperationRequirementService, "allocate_group"),
                    (OperationRequirementCorrectionService, "correct"),
                    (EngineeringCalculationService, "execute"),
                    (EngineeringFactExtensionService, "derive"),
                    (EngineeringFactExtensionService, "configure"),
                ):
                    stack.enter_context(patch.object(owner, name, side_effect=AssertionError(
                        "Manufacturing reference reads must not execute business writers")))
                stack.enter_context(patch.object(operation, "evaluate_specification", side_effect=AssertionError(
                    "Manufacturing reference reads must not regenerate workload")))
                queries = stack.enter_context(CaptureQueriesContext(connection))
                return action()
        finally:
            self.last_sql = [row["sql"] for row in queries] if queries is not None else []
            self.assertEqual([sql for sql in self.last_sql if sql.lstrip().split()[0].upper()
                              in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE"}], [])
            self.assertEqual(self.snapshot(), before)

    def batch(self, cache, *, count=12):
        # Read current rule rows outside the measured section, just as the
        # conversion reader first materializes its candidate query.
        rules = self.rules()[:count]

        def action():
            results = []
            for rule in rules:
                try:
                    proof = manufacturing.validate_manufacturing_rule_context(
                        rule=rule, origin=self.f.source_calc, fact=self.f.fact_area,
                        operation=self.f.op_area, uom=self.f.area,
                        product_type=self.f.product_type, read_cache=cache)
                except operation.OperationRequirementError as exc:
                    results.append({"ruleId": rule.pk, "code": exc.code, "statusLabel": exc.message})
                else:
                    results.append({"ruleId": rule.pk, "proof": proof})
            return results

        with patch.object(manufacturing, "_formal_references", wraps=manufacturing._formal_references) as references:
            results = self.readonly(action)
        self.last_reference_calls = references.call_count
        return results

    def from_counts(self):
        # Count the query's owning table, not every joined table name. This
        # keeps select_related(mode.uom/product-type references) unambiguous.
        models = (Company, Workshop, ManufacturingMode, Process, WorkCenter,
                  WorkCenterOperationCapability, CapacityProductType, UnitOfMeasure,
                  EngineeringRuleDefinition, StandardCapacity)
        return {model._meta.db_table: sum(
            bool(re.search(rf'\bFROM\s+["`]?{re.escape(model._meta.db_table)}["`]?(?:\s|$)',
                           sql, flags=re.IGNORECASE))
            for sql in self.last_sql if sql.lstrip().upper().startswith("SELECT")) for model in models}

    def assert_all_failed(self, results, code, *, count=12):
        self.assertEqual(len(results), count)
        self.assertEqual({row["ruleId"] for row in results}, set(self.rule_ids[:count]))
        self.assertTrue(all(row.get("code") == code for row in results), results)
        self.assertTrue(all("proof" not in row for row in results), results)
        self.assertEqual(self.last_reference_calls, count)

    def assert_raw_only(self, cache):
        self.assertTrue(any(isinstance(key, tuple) and key[0] == "manufacturing_raw" for key in cache))
        self.assertFalse(any(isinstance(key, tuple) and key[0] == "manufacturing_references" for key in cache),
                         "A failed verdict must not be stored as a successful reference proof")

    def raw_fixture_fault(self, obj, field, value):
        """A deliberate isolated fixture fault, before the guarded read."""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {quote(obj._meta.db_table)} SET {quote(obj._meta.get_field(field).column)} = %s "
                f"WHERE {quote(obj._meta.pk.column)} = %s", [value, obj.pk])

    def compare_failed_raw_reuse(self, code):
        plain = {}
        expected = self.batch(plain)
        self.assert_all_failed(expected, code)
        old_counts = self.from_counts()
        self.assertFalse(any(isinstance(key, tuple) and key[0] == "manufacturing_raw" for key in plain))
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.f.user)
            actual = self.batch(cache)
            self.assert_all_failed(actual, code)
            self.assertEqual(actual, expected)
            current_counts = self.from_counts()
            self.assert_raw_only(cache)
        reached = {table: queries for table, queries in current_counts.items() if queries}
        self.assertGreaterEqual(len(reached), 8)
        self.assertEqual(set(reached.values()), {1}, current_counts)
        self.assertEqual({table: old_counts[table] for table in reached},
                         {table: 12 for table in reached}, old_counts)
        self.assertEqual(sum(old_counts.values()), 12 * sum(current_counts.values()))

    def test_twelve_inactive_capacity_failures_keep_every_blocker_with_bounded_raw_queries(self):
        self.raw_fixture_fault(self.f.capacity, "is_active", False)
        self.compare_failed_raw_reuse("MANUFACTURING_CAPACITY_INVALID")

    def test_twelve_producer_version_failures_keep_every_blocker_with_bounded_raw_queries(self):
        producer = EngineeringRuleDefinition.objects.get(pk=self.producer_id)
        self.raw_fixture_fault(producer, "version", "SIM-UNRECORDED-VERSION")
        self.compare_failed_raw_reuse("MANUFACTURING_SOURCE_SELECTOR_MISMATCH")

    def test_three_six_twelve_failures_have_constant_raw_resource_select_counts(self):
        self.raw_fixture_fault(self.f.capacity, "is_active", False)
        totals = []
        for count in (3, 6, 12):
            with self.subTest(candidateCount=count), transaction.atomic():
                cache = operation._ReadOnlyProofCache(self.f.user)
                results = self.batch(cache, count=count)
                self.assert_all_failed(results, "MANUFACTURING_CAPACITY_INVALID", count=count)
                totals.append(self.from_counts())
                self.assert_raw_only(cache)
        self.assertEqual(totals[0], totals[1])
        self.assertEqual(totals[1], totals[2])
        self.assertGreater(sum(totals[0].values()), 0)

    def test_successful_contexts_are_equal_for_plain_and_typed_read_caches(self):
        expected = self.batch({})
        self.assertTrue(all("proof" in row for row in expected), expected)
        with transaction.atomic():
            actual = self.batch(operation._ReadOnlyProofCache(self.f.user))
        self.assertEqual(actual, expected)
        self.assertEqual(self.last_reference_calls, 12)

    def test_wrong_company_cache_cannot_reuse_failed_raw_resource_rows(self):
        self.raw_fixture_fault(self.f.capacity, "is_active", False)
        with transaction.atomic():
            valid = operation._ReadOnlyProofCache(self.f.user)
            self.assert_all_failed(self.batch(valid), "MANUFACTURING_CAPACITY_INVALID")
            self.assert_raw_only(valid)
            wrong = operation._ReadOnlyProofCache(SimpleNamespace(
                pk=self.f.user.pk, company_id=self.f.company.pk + 1000000))
            wrong.update(valid)
            self.assertFalse(wrong.is_current(self.f.company.pk))
            results = self.batch(wrong)
            self.assert_all_failed(results, "MANUFACTURING_CAPACITY_INVALID")
            counts = self.from_counts()
        self.assertEqual({count for count in counts.values() if count}, {12}, counts)

    def test_expired_atomic_cache_cannot_reuse_failed_raw_resource_rows(self):
        self.raw_fixture_fault(self.f.capacity, "is_active", False)
        with transaction.atomic():
            expired = operation._ReadOnlyProofCache(self.f.user)
            self.assert_all_failed(self.batch(expired), "MANUFACTURING_CAPACITY_INVALID")
            self.assert_raw_only(expired)
        self.assertFalse(expired.is_current(self.f.company.pk))
        results = self.batch(expired)
        self.assert_all_failed(results, "MANUFACTURING_CAPACITY_INVALID")
        counts = self.from_counts()
        self.assertEqual({count for count in counts.values() if count}, {12}, counts)

    def test_a_new_request_rejects_changed_capacity_after_a_successful_read(self):
        with transaction.atomic():
            first = self.batch(operation._ReadOnlyProofCache(self.f.user))
        self.assertTrue(all("proof" in row for row in first), first)
        self.raw_fixture_fault(self.f.capacity, "is_active", False)
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.f.user)
            self.assert_all_failed(self.batch(cache), "MANUFACTURING_CAPACITY_INVALID")
            self.assert_raw_only(cache)

    def test_a_new_request_rejects_changed_producer_version_after_a_successful_read(self):
        with transaction.atomic():
            first = self.batch(operation._ReadOnlyProofCache(self.f.user))
        self.assertTrue(all("proof" in row for row in first), first)
        producer = EngineeringRuleDefinition.objects.get(pk=self.producer_id)
        self.raw_fixture_fault(producer, "version", "SIM-UNRECORDED-VERSION")
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.f.user)
            self.assert_all_failed(self.batch(cache), "MANUFACTURING_SOURCE_SELECTOR_MISMATCH")
            self.assert_raw_only(cache)

    def test_a_new_request_rechecks_mapping_publication_before_reusing_resource_rows(self):
        with transaction.atomic():
            first = self.batch(operation._ReadOnlyProofCache(self.f.user))
        self.assertTrue(all("proof" in row for row in first), first)
        for rule in self.rules():
            self.raw_fixture_fault(rule, "status", "obsolete")
        with transaction.atomic():
            results = self.batch(operation._ReadOnlyProofCache(self.f.user))
        self.assertEqual({row.get("code") for row in results}, {"MANUFACTURING_RULE_NOT_RELEASED"})
        self.assertEqual({row["ruleId"] for row in results}, set(self.rule_ids))
        self.assertEqual(self.last_reference_calls, 0)
