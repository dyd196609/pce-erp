"""SIMULATED_FOR_TEST: one native aggregate read, compact online facts.

Existing builders establish real sources/allocations/object decisions before
measured reads. Spies invoke native validators; no successful proof is mocked.
The parent exclusively runs this file in its named disposable database.
"""
from copy import deepcopy, copy
from decimal import Decimal
import sys
from unittest.mock import patch

from django.db import transaction
from django.test import SimpleTestCase, TestCase, override_settings

from system.models import OrganizationOperatingAuditRecord, RolePermission
from . import daily_capacity_service as capacity
from . import operation_requirement_service as native
from . import operation_workload_source_service as source
from . import routing_object_applicability_service as objects
from . import tests_single_step_no_date_capacity as fixtures
from . import tests_routing_object_applicability_service as object_fixtures
from . import tests_no_date_read_context as nq_fixtures
from . import tests_conditional_execution_preparation as conditional_fixtures
from . import tests_operation_quantity_policy as quantity_fixtures
from . import operation_input_preparation_service as preparation
from . import conditional_execution_preparation as policy
from . import manufacturing_output_generation_service as outputs
from .production_foundation_service import ProductionFoundationError
from .models import ProductionPlanOperationRequirementAllocation


LABELS = {'capacityLabel', 'productionDaysLabel', 'preparationDaysLabel', 'transferDaysLabel',
    'totalDaysLabel', 'timeSourceLabel', 'scopeBoundaryLabel'}


class NativeNoDateAggregateReadTests(TestCase):
    def setUp(self):
        self.case = fixtures.SingleStepNoDateCapacityTests(methodName='runTest')
        self.case.setUp()
        self.case.save_contributions()
        self.f, self.plan, self.step = self.case.f, self.case.plan, self.case.step

    def overview(self):
        return self.case._readonly(lambda: source.read_route_overview(user=self.f.user,
            production_plan_id=self.plan.pk, include_workloads=True))

    def detail(self, step=None):
        return self.case._readonly(lambda: source.read_for_plan(user=self.f.user,
            production_plan_id=self.plan.pk, routing_step_id=(step or self.step).pk, include_no_date=True))

    def test_one_plan_read_shared_native_scope_not_twenty_eight_public_assessments(self):
        caches, selected_capacities = [], []
        real = capacity.AllocatedLoadCapacityReadinessService._assess_read
        original_capacity = capacity._current_plan_capacity
        def observe(**kwargs):
            self.assertIsNotNone(kwargs['_prepared'])
            self.assertEqual(kwargs['_prepared']['context'][4].pk,
                kwargs['_prepared']['source_read']['scope']['routingStepId'])
            caches.append(kwargs['read_cache'])
            return real(**kwargs)
        def current_capacity(fact, on_date, **kwargs):
            self.assertIs(kwargs['source_rules_cache'], caches[-1])
            self.assertIs(kwargs['read_user'], self.f.user)
            selected_capacities.append(fact['id'])
            return original_capacity(fact, on_date, **kwargs)
        with patch.object(capacity, '_current_plan_capacity', new=current_capacity), \
                patch.object(capacity.AllocatedLoadCapacityReadinessService, 'assess',
                side_effect=AssertionError('Batch must not repeat the complete public assessment')), \
                patch.object(capacity.AllocatedLoadCapacityReadinessService, '_assess_read', side_effect=observe), \
                patch.object(native.OperationRequirementService, 'read', wraps=native.OperationRequirementService.read) as reads:
            result = self.overview()
        self.assertEqual(reads.call_count, 1)
        self.assertEqual(selected_capacities, [self.f.capacity.pk])
        self.assertTrue(result['noDateCapacityIncluded'])
        self.assertEqual(result['noDateCapacitySummary']['readStepCount'], len(result['rows']))
        self.assertEqual(len(caches), len(result['rows']))
        self.assertTrue(all(cache is caches[0] for cache in caches))
        row = next(row for row in result['rows'] if row['routingStepId'] == self.step.pk)
        fact = row['noDateCapacity']
        self.assertEqual(fact['scope'], row['scope'])
        self.assertTrue(fact['noDateMatchPassed'], fact)
        self.assertEqual(fact['matchedAllocationCount'], 3)
        match, = fact['capacityMatches']
        self.assertEqual((Decimal(match['productionDays']), Decimal(match['durationDays'])),
            (Decimal('.008'), Decimal('.208')))
        self.assertEqual((match['preparationIncludedCount'], match['transferIncludedCount']), (1, 1))
        self.assertEqual(set(fact['displayLabels']), LABELS)
        self.assertRegex(fact['resultHash'], r'^[0-9a-f]{64}$')
        self.assertNotIn('sourceRead', fact)
        self.assertNotIn('processDemand', fact)
        self.assertNotIn('allocationRead', fact)
        self.assertFalse(fact['planningReady'])
        self.assertFalse(fact['dateConditions']['calendarOccupationEvaluated'])

    def test_current_detail_and_overview_use_the_same_native_matching_and_time_selection(self):
        overview = self.overview()
        row = next(row for row in overview['rows'] if row['routingStepId'] == self.step.pk)
        detail = self.detail()
        left, right = deepcopy(row['noDateCapacity']), deepcopy(detail['noDateCapacity'])
        self.assertTrue(detail['noDateCapacityIncluded'])
        self.assertEqual(right['scope'], detail['scope'])
        for key in ('assessedAt', 'resultHash'):
            left.pop(key)
            right.pop(key)
        self.assertEqual(left, right)
        original = self.case.read()
        self.assertEqual(original['steps'][0]['capacityMatches'][0]['durationDays'],
            right['capacityMatches'][0]['durationDays'])
        self.assertEqual(original['steps'][0]['capacityMatches'][0]['timeSelection'],
            right['capacityMatches'][0]['timeSelection'])

    def test_native_excluded_empty_scope_retains_policy_and_no_accurate_duration(self):
        other = self.case.other_step
        original = self.f.step
        self.f.step = other
        try:
            fixture = object_fixtures.make_object_applicability_fixture(f=self.f, plan=self.plan)
        finally:
            self.f.step = original
        objects.confirm_group(self.f.user, self.plan.pk, other.pk, fixture.contributions,
            'SIMULATED_FOR_TEST exact native nonapplicable aggregate scope')
        result = self.overview()
        row = next(row for row in result['rows'] if row['routingStepId'] == other.pk)
        fact = row['noDateCapacity']
        self.assertEqual(fact['scope'], row['scope'])
        self.assertEqual(fact['statusCode'], 'NOT_APPLICABLE_VERIFIED')
        self.assertTrue(fact['legalEmptyLoadVerified'], fact)
        self.assertFalse(fact['independentAllocationRequired'])
        self.assertFalse(fact['noDateMatchPassed'])
        self.assertEqual(fact['capacityMatches'], [])
        self.assertEqual((fact['matchedStepCount'], fact['matchedAllocationCount']), (0, 0))
        self.assertNotIn('durationDays', fact)
        self.assertIsNone(fact['timeReferences']['step']['preparationDays'])
        self.assertIsNone(fact['timeReferences']['step']['transferDays'])

    def test_ordinary_missing_load_and_missing_actor_permission_still_reject(self):
        result = self.detail(self.case.other_step)
        fact = result['noDateCapacity']
        self.assertFalse(fact['noDateMatchPassed'])
        self.assertFalse(fact['legalEmptyLoadVerified'])
        self.assertIn('PROCESS_DEMAND_PLAN_ALLOCATION_MISSING', {row['code'] for row in fact['blockers']})
        self.assertEqual(fact['capacityMatches'], [])
        RolePermission.objects.filter(role=self.f.role, permission__code=native.PLAN_VIEW).delete()
        with self.assertRaises(source.OperationWorkloadSourceError) as caught:
            self.detail()
        self.assertEqual(caught.exception.code, 'PERMISSION_DENIED')

    def test_corrupt_saved_audit_never_becomes_a_capacity_match(self):
        cache = native._source_read_cache(self.f.user, None)
        def cached_read():
            return self.case._readonly(lambda: source.read_for_plan(user=self.f.user,
                production_plan_id=self.plan.pk, routing_step_id=self.step.pk,
                include_no_date=True, _read_cache=cache))
        self.assertTrue(cached_read()['noDateCapacity']['noDateMatchPassed'])
        old_epoch = cache._write_epoch
        self.assertTrue(any(isinstance(key, tuple) and key[0] == 'no_date_expected_objects' for key in cache))
        allocation = ProductionPlanOperationRequirementAllocation.objects.filter(
            production_plan_id=self.plan.pk, routing_step=self.step).first()
        audit = OrganizationOperatingAuditRecord.objects.get(pk=allocation.audit_record_id)
        after = deepcopy(audit.after_snapshot)
        after['state']['operationRequirementAllocation']['allocatedQuantity'] = '999999'
        OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(after_snapshot=after)
        result = cached_read()
        self.assertGreater(cache._write_epoch, old_epoch)
        self.assertFalse(any(isinstance(key, tuple) and key[0] == 'no_date_expected_objects' for key in cache))
        fact = result['noDateCapacity']
        self.assertEqual(result['savedAllocations']['statusCode'], 'INVALID')
        self.assertFalse(fact['noDateMatchPassed'])
        self.assertTrue(fact['blockers'])
        self.assertEqual(fact['capacityMatches'], [])
        self.assertFalse(fact['legalEmptyLoadVerified'])


class NativeNonQuantifiedAggregateReadTests(TestCase):
    def test_saved_positive_quantity_zero_capacity_keeps_native_load_without_empty_exemption(self):
        case = nq_fixtures.NoDateReadContextTests(methodName='runTest')
        case.setUp()
        from . import formal_engineering_continuation_service as continuation
        reference_calls, original_reference = [], continuation._baseline_reference
        def reference(*args, **kwargs):
            if sys._getframe(1).f_code.co_name == 'expected_for_plan':
                reference_calls.append(args[0].pk)
            return original_reference(*args, **kwargs)
        with patch.object(continuation, '_baseline_reference', new=reference):
            result = case.readonly(lambda: source.read_route_overview(user=case.user,
                production_plan_id=case.plan.pk, include_workloads=True))
        self.assertEqual(reference_calls, [case.f.baseline.pk],
            'Both native steps share one successful proof of the same unchanged fixed baseline/main')
        row = next(row for row in result['rows'] if row['routingStepId'] == case.nq_step.pk)
        fact = row['noDateCapacity']
        self.assertEqual(row['savedAllocations']['statusCode'], 'SAVED')
        self.assertGreater(Decimal(row['savedAllocations']['quantity']), 0)
        self.assertEqual(len(row['savedAllocations']['items']), 3)
        self.assertEqual(fact['stage'], 'NON_QUANTIFIED_SAVED_LOAD')
        self.assertTrue(fact['allocatedLoadReadPassed'])
        self.assertFalse(fact['legalEmptyLoadVerified'])
        self.assertTrue(fact['independentAllocationRequired'])
        self.assertEqual(fact['capacityMatches'], [])
        self.assertFalse(fact['scopeNoDateReady'])
        self.assertFalse(fact['noDateMatchPassed'])
        self.assertNotIn('durationDays', fact)


class NoDateCapacityPresentationTests(SimpleTestCase):
    def test_candidate_time_is_not_presented_as_matched_when_coverage_is_blocked(self):
        candidate = {'capacityFact': {'capacityQuantity': '500', 'uomLabel': '平方米'},
            'productionDays': '.008', 'preparationDays': '.1', 'transferDays': '.1', 'durationDays': '.208',
            'timeSelection': {'preparation': {'source': 'CAPACITY_SOURCE_RULES_HEADER'},
                'transfer': {'source': 'CAPACITY_SOURCE_RULES_HEADER'}}}
        denied = capacity._no_date_display_labels('QUANTIFIED', [candidate], matched=False)
        self.assertNotIn('.208', denied['totalDaysLabel'])
        self.assertIn('未知', denied['totalDaysLabel'])
        accepted = capacity._no_date_display_labels('QUANTIFIED', [candidate], matched=True)
        self.assertIn('.208', accepted['totalDaysLabel'])
        self.assertIn('正式统一时间来源', accepted['timeSourceLabel'])


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=conditional_fixtures.published_fixtures.SCOPE)
class NativePolicyContentReadCacheTests(TestCase):
    """Reuse declared upstream fixtures; never mock a successful content proof."""
    def assert_content_cache(self, case, builder):
        case.save()
        cache = native._source_read_cache(case.user, None)
        foreign_user = copy(case.user)
        foreign_user.pk += 1000000
        foreign_cache = native._source_read_cache(foreign_user, None)
        original = outputs._saved_output_content_integrity
        with patch.object(outputs, '_saved_output_content_integrity', wraps=original) as content:
            read = lambda proof_cache: case.readonly(lambda: preparation.read_preparation(
                user=case.user, exact_scope=case.scope, read_cache=proof_cache))
            first = read(cache)
            self.assertEqual(content.call_count, 1)
            self.assertEqual(read(cache), first)
            self.assertEqual(content.call_count, 1, 'Only the content body is shared; native readback revalidates')
            read(None)
            self.assertEqual(content.call_count, 2)
            case.readonly(lambda: builder(user=case.user, exact_scope=case.scope, lock=True, read_cache=cache))
            self.assertEqual(content.call_count, 3, 'Locked paths retain the original content proof')
            case.readonly(lambda: builder(user=None, exact_scope=case.scope, read_cache=cache))
            self.assertEqual(content.call_count, 4, 'The resolver without an actor retains its original proof')
            read(foreign_cache)
            self.assertEqual(content.call_count, 5, 'A different actor cache never supplies content proof')
            RolePermission.objects.filter(role=case.role, permission__code=preparation.VIEW).delete()
            before = case.f.full_database_snapshot()
            with self.assertRaises(ProductionFoundationError) as denied:
                preparation.read_preparation(user=case.user, exact_scope=case.scope, read_cache=cache)
            self.assertEqual(denied.exception.code, 'PERMISSION_DENIED')
            self.assertEqual(content.call_count, 5)
            self.assertEqual(case.f.full_database_snapshot(), before)

    def test_conditional_policy_native_read_cache_keeps_original_none_lock_actor_and_permission_guards(self):
        case = conditional_fixtures.ConditionalExecutionPreparationTests(methodName='runTest')
        self.addCleanup(case.doCleanups)
        case.setUp()
        self.assert_content_cache(case, policy.build_conditional_context)

    def test_quantity_policy_native_read_cache_keeps_original_none_lock_actor_and_permission_guards(self):
        case = quantity_fixtures.OperationQuantityPolicyTests(methodName='runTest')
        self.addCleanup(case.doCleanups)
        case.setUp()
        def builder(**kwargs):
            return policy.build_quantity_policy_context(statistical_routing_step_id=case.reference_step.pk,
                standard_capacity_id=case.capacity.pk, **kwargs)
        self.assert_content_cache(case, builder)
