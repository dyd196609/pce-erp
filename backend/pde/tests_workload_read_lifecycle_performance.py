"""SIMULATED_FOR_TEST: lifecycle proofs belong to one immutable atomic read.

Fixture writes and deliberate faults use only Django's disposable test database.
Measured reads retain all native source/history checks and reject business writes.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase

from workflow_runtime.models import BusinessStateTransition
from . import operation_requirement_correction_service as correction
from . import operation_requirement_service as operation
from . import tests_workload_read_budget_performance as fixtures
from .models import EngineeringOperationRequirement


class WorkloadReadLifecyclePerformanceTests(TestCase):
    def setUp(self):
        self.fixture = fixtures.WorkloadReadBudgetPerformanceTests(methodName='runTest')
        self.fixture.setUp()
        self.fixture.save_through(3)
        self.user = self.fixture.f.user
        self.req = EngineeringOperationRequirement.objects.select_related(
            'calculation', 'source_detail__rule').get(
                pk=self.fixture.requirements_for_step(self.fixture.f.step)[0].pk)

    def test_three_original_effective_gates_share_one_successful_lifecycle(self):
        with patch.object(correction, '_requirement_read_cache', return_value=None), \
             patch.object(correction, '_history', wraps=correction._history) as history:
            uncached = self.fixture.read()
            uncached_calls, uncached_queries = history.call_count, len(self.fixture.last_sql)
        with patch.object(correction, '_history', wraps=correction._history) as history:
            cached = self.fixture.read()
            cached_calls, cached_queries = history.call_count, len(self.fixture.last_sql)
        self.fixture.assert_passed(cached, 3)
        self.assertEqual(cached, uncached)
        self.assertEqual(cached_calls, 3 * 3)  # Three EORs; current/old/new history once each.
        self.assertEqual(uncached_calls, cached_calls * 3)
        self.assertLess(cached_queries, uncached_queries)

    def test_complete_snapshot_identity_and_independent_return_values(self):
        def read():
            with transaction.atomic():
                cache = operation._ReadOnlyProofCache(self.user)
                with patch.object(correction, '_history', wraps=correction._history) as history:
                    first = correction.requirement_lifecycle(self.req, self.user.company_id, read_cache=cache)
                    expected_calls = history.call_count
                    repeated = correction.requirement_lifecycle(self.req, self.user.company_id, read_cache=cache)
                    self.assertEqual(first, repeated)
                    self.assertEqual(history.call_count, expected_calls)
                    first['history'][0]['reason'] = 'SIMULATED_FOR_TEST returned-object mutation'
                    self.assertNotEqual(first, correction.requirement_lifecycle(
                        self.req, self.user.company_id, read_cache=cache))
                    for obj, field in ((self.req, 'trace'), (self.req.calculation, 'trace'),
                                       (self.req.source_detail, 'input_snapshot'),
                                       (self.req.source_detail.rule, 'specification')):
                        original = getattr(obj, field)
                        setattr(obj, field, {**original, 'SIMULATED_FOR_TEST_identity': True})
                        correction.requirement_lifecycle(self.req, self.user.company_id, read_cache=cache)
                        self.assertGreater(history.call_count, expected_calls)
                        expected_calls = history.call_count
                        setattr(obj, field, original)
        self.fixture.readonly(read)

    def test_invalid_history_is_rechecked_and_failed_proof_is_never_cached(self):
        self.fixture.assert_passed(self.fixture.read(), 3)
        state = BusinessStateTransition.objects.filter(
            object_type='EngineeringOperationRequirement', object_id=self.req.pk).first()
        self.fixture.raw_fixture_fault(state, 'audit_reference',
            f'SIMULATED_FOR_TEST_INVALID_AUDIT_REFERENCE:{state.pk}')
        current = self.fixture.read()
        self.assertFalse(current['passed'])
        self.assertIn('CORRECTION_HISTORY_UNPROVEN', {row['code'] for row in current['blockers']})

        def read():
            with transaction.atomic():
                cache = operation._ReadOnlyProofCache(self.user)
                with patch.object(correction, '_history', wraps=correction._history) as history:
                    for _ in range(2):
                        with self.assertRaises(operation.OperationRequirementError) as caught:
                            correction.require_effective_requirement(self.req, self.user.company_id, read_cache=cache)
                        self.assertEqual(caught.exception.code, 'CORRECTION_HISTORY_UNPROVEN')
                    self.assertEqual(history.call_count, 2)
                    self.assertFalse(any(key[0] == 'requirement_lifecycle' for key in cache))
        self.fixture.readonly(read)

    def test_scope_requires_same_user_company_connection_and_original_atomic(self):
        with transaction.atomic():
            scope = operation._ReadOnlyProofCache(self.user)
            self.assertTrue(scope.is_current(self.user.company_id))
            self.assertIs(operation._source_read_cache(self.user, scope), scope)
            other_user = SimpleNamespace(pk=self.user.pk + 100000, company_id=self.user.company_id)
            self.assertIsNot(operation._source_read_cache(other_user, scope), scope)
            self.assertFalse(scope.is_current(self.user.company_id + 100000))
        self.assertFalse(scope.is_current(self.user.company_id))
        with transaction.atomic():
            replacement = operation._source_read_cache(self.user, scope)
            self.assertIsNot(replacement, scope)
            self.assertTrue(replacement.is_current(self.user.company_id))

