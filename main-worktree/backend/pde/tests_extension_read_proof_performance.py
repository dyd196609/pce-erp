"""SIMULATED_FOR_TEST: complete extension proofs in an atomic pure read.

The disposable Django database contains three real grouped object outputs and
their original details, links, state transitions and audits. No proof, rule or
authorization verdict is replaced. Deliberate evidence faults occur only in
fixture setup between guarded reads, never through a production connection.
"""

from contextlib import ExitStack
from copy import deepcopy
import json
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection, transaction
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from . import engineering_fact_extension_service as extension
from . import operation_requirement_service as operation
from . import tests_plan_legal_extension_admission as fixtures
from .engineering_calculation_service import EngineeringCalculationService
from .models import (
    EngineeringCalculationDetail, EngineeringCalculationRecord,
    EngineeringDerivedFact, EngineeringFactInput, EngineeringOperationRequirement,
    EngineeringRuleDefinition, EngineeringSourceRecord,
    ProductionPlanOperationRequirementAllocation,
)
from .operation_requirement_correction_service import OperationRequirementCorrectionService


class ReadOnlyProofCacheConstructionTests(SimpleTestCase):
    def test_a_complete_proof_cache_requires_an_active_atomic_block(self):
        self.assertFalse(connection.in_atomic_block)
        with self.assertRaisesRegex(RuntimeError, "active atomic read"):
            operation._ReadOnlyProofCache(SimpleNamespace(company_id=1, pk=1))


class ExtensionReadProofPerformanceTests(TestCase):
    def setUp(self):
        # Use fixture construction without inheriting/discovering its tests.
        fixture = fixtures.PlanLegalExtensionAdmissionTests(methodName="runTest")
        fixture.setUp()
        self.fixture, self.f = fixture, fixture.f
        self.origin_id = fixture.extension.pk
        self.fact_ids = [fact.pk for fact in fixture.facts]
        self.assertEqual(len(self.fact_ids), 3)
        self.assertEqual(len({fact.trace["group"]["designItemId"] for fact in fixture.facts}), 3)
        self.assertEqual([fact.inputs.count() for fact in fixture.facts], [1, 1, 1])

    def origin(self):
        return EngineeringCalculationRecord.objects.get(pk=self.origin_id)

    def facts(self):
        return list(EngineeringDerivedFact.objects.filter(pk__in=self.fact_ids).order_by("sequence"))

    def snapshot(self):
        # Never collect User, password or session fields.
        return {model._meta.label: list(model.objects.order_by("pk").values()) for model in (
            EngineeringSourceRecord, EngineeringCalculationRecord, EngineeringCalculationDetail,
            EngineeringDerivedFact, EngineeringFactInput, EngineeringOperationRequirement,
            EngineeringRuleDefinition, ProductionPlanOperationRequirementAllocation,
            OrganizationOperatingAuditRecord, BusinessStateTransition,
        )}

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
                    (extension.EngineeringFactExtensionService, "configure"),
                    (extension.EngineeringFactExtensionService, "derive"),
                ):
                    stack.enter_context(patch.object(owner, name, side_effect=AssertionError(
                        "Extension evidence reads must not execute a business writer")))
                queries = stack.enter_context(CaptureQueriesContext(connection))
                return action()
        finally:
            self.last_sql = [row["sql"] for row in queries] if queries is not None else []
            self.assertEqual([sql for sql in self.last_sql if sql.lstrip().split()[0].upper()
                              in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE"}], [])
            self.assertEqual(self.snapshot(), before)

    def prove_all(self, read_cache):
        origin, facts = self.origin(), self.facts()
        return self.readonly(lambda: [extension.validate_extension_fact(
            origin, fact, read_cache=read_cache) for fact in facts])

    def complete_entries(self, cache):
        return {key: value for key, value in cache.items()
                if isinstance(key, tuple) and key[0] == "complete_extension_read"}

    def full_output_selects(self):
        table = EngineeringDerivedFact._meta.db_table.lower()
        predicate = rf'["`]?calculation_id["`]?\s*=\s*{self.origin_id}(?!\d)'
        return [sql for sql in self.last_sql if sql.lstrip().upper().startswith("SELECT")
                and table in sql.lower() and re.search(predicate, sql, flags=re.IGNORECASE)]

    def input_link_selects(self):
        table = EngineeringFactInput._meta.db_table.lower()
        return [sql for sql in self.last_sql if sql.lstrip().upper().startswith("SELECT")
                and table in sql.lower()]

    def raw_fixture_fault(self, obj, field, value):
        """Isolated fault injection outside the guarded read section."""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {quote(obj._meta.db_table)} SET {quote(obj._meta.get_field(field).column)} = %s "
                f"WHERE {quote(obj._meta.pk.column)} = %s", [value, obj.pk])

    def assert_new_request_rejects(self, *, code=None):
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.f.user)
            origin, fact = self.origin(), self.facts()[0]
            with self.assertRaises(operation.OperationRequirementError) as caught:
                self.readonly(lambda: extension.validate_extension_fact(origin, fact, read_cache=cache))
            if code is not None:
                self.assertEqual(caught.exception.code, code)
            self.assertEqual(self.complete_entries(cache), {})

    def test_three_members_reuse_one_complete_output_link_history_proof_with_equal_results(self):
        plain = {}
        expected = self.prove_all(plain)
        plain_selects = sum(sql.lstrip().upper().startswith("SELECT") for sql in self.last_sql)
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.f.user)
            with patch.object(extension, "_plan", wraps=extension._plan) as plan, \
                 patch.object(extension, "_history_cache", wraps=extension._history_cache) as history, \
                 patch.object(extension, "_prove_history", wraps=extension._prove_history) as prove_history:
                actual = self.prove_all(cache)
            self.assertEqual(actual, expected)
            self.assertEqual(plan.call_count, 1)
            self.assertEqual(history.call_count, 1)
            self.assertEqual(prove_history.call_count, 7)
            self.assertEqual(len(self.full_output_selects()), 1)
            self.assertEqual(len(self.input_link_selects()), 1)
            observed = {(type(obj).__name__, obj.pk) for obj in history.call_args.args[0]}
            details = set(EngineeringDerivedFact.objects.filter(pk__in=self.fact_ids)
                          .values_list("source_detail_id", flat=True))
            self.assertEqual(observed, {
                ("EngineeringCalculationRecord", self.origin_id),
                *[("EngineeringDerivedFact", pk) for pk in self.fact_ids],
                *[("EngineeringCalculationDetail", pk) for pk in details],
            })
            complete = self.complete_entries(cache)
            self.assertEqual(len(complete), 1)
            self.assertEqual(set(next(iter(complete.values()))["members"]), set(self.fact_ids))
            self.assertLess(sum(sql.lstrip().upper().startswith("SELECT") for sql in self.last_sql), plain_selects)
            # A returned dictionary must not let its consumer modify the saved proof.
            actual[1]["resultHash"] = "SIMULATED_CONSUMER_CHANGE"
            repeated = self.readonly(lambda: extension.validate_extension_fact(
                self.origin(), self.facts()[1], read_cache=cache))
            self.assertEqual(repeated, expected[1])

    def test_plain_dictionary_keeps_all_original_output_link_and_history_checks(self):
        cache = {}
        with patch.object(extension, "_plan", wraps=extension._plan) as plan, \
             patch.object(extension, "_history_cache", wraps=extension._history_cache) as history, \
             patch.object(extension, "_prove_history", wraps=extension._prove_history) as prove_history:
            proofs = self.prove_all(cache)
        self.assertEqual(len(proofs), 3)
        self.assertEqual(plan.call_count, 1, "The preexisting pure plan memo may still be reused")
        self.assertEqual(history.call_count, 3)
        self.assertEqual(prove_history.call_count, 21)
        self.assertEqual(len(self.full_output_selects()), 3)
        self.assertEqual(len(self.input_link_selects()), 3)
        self.assertEqual(self.complete_entries(cache), {})

    def test_failure_in_an_unselected_output_is_retried_and_never_saved_as_complete_proof(self):
        bad = self.facts()[-1]
        self.raw_fixture_fault(bad, "value", {"decimal": "99"})
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.f.user)
            with patch.object(extension, "_history_cache", wraps=extension._history_cache) as history:
                for _ in range(2):
                    with self.assertRaises(operation.OperationRequirementError) as caught:
                        self.readonly(lambda: extension.validate_extension_fact(
                            self.origin(), self.facts()[0], read_cache=cache))
                    self.assertEqual(caught.exception.code, "FACT_EXTENSION_UNPROVEN")
                    self.assertEqual(self.complete_entries(cache), {})
            self.assertEqual(history.call_count, 2)

    def test_changed_member_snapshot_cannot_hit_the_previous_complete_proof(self):
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.f.user)
            with patch.object(extension, "_history_cache", wraps=extension._history_cache) as history:
                self.prove_all(cache)
                self.assertEqual(history.call_count, 1)
                bad = self.facts()[1]
                self.raw_fixture_fault(bad, "value", {"decimal": "99"})
                changed = EngineeringDerivedFact.objects.get(pk=bad.pk)
                with self.assertRaises(operation.OperationRequirementError) as caught:
                    self.readonly(lambda: extension.validate_extension_fact(
                        self.origin(), changed, read_cache=cache))
                self.assertEqual(caught.exception.code, "FACT_EXTENSION_UNPROVEN")
                self.assertEqual(history.call_count, 2)

    def test_changed_origin_trace_cannot_hit_the_previous_complete_proof(self):
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.f.user)
            self.prove_all(cache)
            origin = self.origin()
            changed = {**origin.trace, "simulatedUnrecordedChange": True}
            self.raw_fixture_fault(origin, "trace", changed)
            with patch.object(extension, "_history_cache", wraps=extension._history_cache) as history:
                with self.assertRaises(operation.OperationRequirementError) as caught:
                    self.readonly(lambda: extension.validate_extension_fact(
                        self.origin(), self.facts()[0], read_cache=cache))
            self.assertEqual(caught.exception.code, "FACT_EXTENSION_AUDIT_MISSING")
            self.assertEqual(history.call_count, 1)

    def test_a_new_request_rejects_a_changed_unselected_output(self):
        with transaction.atomic():
            self.prove_all(operation._ReadOnlyProofCache(self.f.user))
        self.raw_fixture_fault(self.facts()[-1], "value", {"decimal": "99"})
        self.assert_new_request_rejects(code="FACT_EXTENSION_UNPROVEN")

    def test_a_new_request_rejects_an_input_link_with_unchanged_output_numbers(self):
        with transaction.atomic():
            self.prove_all(operation._ReadOnlyProofCache(self.f.user))
        link = EngineeringFactInput.objects.filter(fact_id=self.fact_ids[-1]).first()
        self.assertIsNotNone(link)
        self.raw_fixture_fault(link, "source_hash", "0" * 64)
        self.assert_new_request_rejects(code="FACT_EXTENSION_UNPROVEN")

    def test_a_new_request_rejects_missing_authoritative_history_audit(self):
        with transaction.atomic():
            self.prove_all(operation._ReadOnlyProofCache(self.f.user))
        transition = BusinessStateTransition.objects.get(
            object_type="EngineeringDerivedFact", object_id=str(self.fact_ids[-1]), version=1)
        self.raw_fixture_fault(transition, "audit_reference", "OrganizationOperatingAuditRecord:0")
        self.assert_new_request_rejects(code="FACT_EXTENSION_AUDIT_MISSING")

    def test_new_requests_recheck_origin_base_source_and_rule_versions_and_hashes(self):
        origin = self.origin()
        base = EngineeringCalculationRecord.objects.get(pk=origin.origin_calculation_id)
        source = EngineeringSourceRecord.objects.get(pk=base.source_record_id)
        rule = EngineeringRuleDefinition.objects.get(pk=origin.trace["ruleIds"][0])
        changed_spec = deepcopy(rule.specification)
        changed_spec["expression"] = "area_quantity + 1"
        faults = [
            (origin, "input_hash", "0" * 64),
            (origin, "result_hash", "0" * 64),
            (origin, "rule_graph_hash", "0" * 64),
            (base, "input_hash", "0" * 64),
            (base, "result_hash", "0" * 64),
            (base, "rule_graph_hash", "0" * 64),
            (source, "source_version", "SIMULATED_UNRECORDED_VERSION"),
            (source, "content_hash", "0" * 64),
            (rule, "version", "SIMULATED_UNRECORDED_VERSION"),
            (rule, "specification", changed_spec),
        ]
        for obj, field, value in faults:
            with self.subTest(model=type(obj).__name__, field=field):
                with transaction.atomic():
                    self.prove_all(operation._ReadOnlyProofCache(self.f.user))
                previous = deepcopy(getattr(obj, field))
                self.raw_fixture_fault(obj, field, value)
                try:
                    self.assert_new_request_rejects()
                finally:
                    self.raw_fixture_fault(obj, field, previous)

    def test_complete_proof_cannot_override_changed_origin_scope_foreign_keys(self):
        for field in ("source_record", "sales_order_item", "engineering_instance"):
            with self.subTest(field=field), transaction.atomic():
                cache = operation._ReadOnlyProofCache(self.f.user)
                self.prove_all(cache)
                origin = self.origin()
                previous = getattr(origin, f"{field}_id")
                self.raw_fixture_fault(origin, field, previous + 1000000)
                try:
                    with self.assertRaises(operation.OperationRequirementError) as caught:
                        self.readonly(lambda: extension.validate_extension_fact(
                            self.origin(), self.facts()[0], read_cache=cache))
                    self.assertEqual(caught.exception.code, "FACT_EXTENSION_UNPROVEN")
                finally:
                    self.raw_fixture_fault(origin, field, previous)

    def test_complete_proof_is_not_reused_under_another_company_or_connection_binding(self):
        with transaction.atomic():
            valid = operation._ReadOnlyProofCache(self.f.user)
            self.prove_all(valid)
            wrong_company = operation._ReadOnlyProofCache(SimpleNamespace(
                company_id=self.f.company.pk + 1000000, pk=self.f.user.pk))
            wrong_company.update(valid)
            wrong_connection = operation._ReadOnlyProofCache(self.f.user)
            wrong_connection.update(valid)
            # This changes only the in-memory cache fixture, not any DB handle.
            wrong_connection._connection = object()
            for cache in (wrong_company, wrong_connection):
                with self.subTest(binding="company" if cache is wrong_company else "connection"):
                    self.assertFalse(cache.is_current(self.f.company.pk))
                    with patch.object(extension, "_history_cache", wraps=extension._history_cache) as history:
                        self.prove_all(cache)
                    self.assertEqual(history.call_count, 3)

    def test_complete_proof_expires_when_its_original_atomic_block_has_ended(self):
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.f.user)
            self.prove_all(cache)
            self.assertTrue(cache.is_current(self.f.company.pk))
        # TestCase still owns its outer transaction. Ending the specifically
        # bound inner atomic block must nevertheless invalidate this proof.
        self.assertTrue(connection.in_atomic_block)
        self.assertFalse(cache.is_current(self.f.company.pk))
        with patch.object(extension, "_history_cache", wraps=extension._history_cache) as history:
            self.prove_all(cache)
        self.assertEqual(history.call_count, 3)
