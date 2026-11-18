"""SIMULATED_FOR_TEST: real positive/NQ saved loads share the current reader.

Run only in the parent's guarded disposable database. Fixture writes use native
services before the measured read. Spies record calls and invoke the original
validators; no successful source, actor, budget or capacity proof is mocked.
"""
from contextlib import ExitStack
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase

from masterdata.models import MasterDataWriteRequest
from system.models import RolePermission
from . import daily_capacity_service as capacity
from . import operation_non_quantified_context as nonquantified
from . import operation_requirement_service as native
from . import operation_workload_source_service as workload
from . import tests_nonquantified_manufacturing_source as fixtures


def codes(value):
    if isinstance(value, dict):
        return ({value['code']} if value.get('code') else set()).union(*(codes(v) for v in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(codes(v) for v in value))
    return set()


class NoDateReadContextTests(TestCase):
    def setUp(self):
        self.case = fixtures.NonQuantifiedManufacturingSourceTests(methodName='runTest')
        self.case.setUp()
        self.f, self.plan, self.user = self.case.f, self.case.plan, self.case.user
        self.positive_step, self.nq_step = self.f.step, self.case.step
        self.assertNotEqual(self.positive_step.pk, self.nq_step.pk)
        # Both sets belong to the same real plan/order line. The positive
        # target's budget must continue validating the other step's NQ rows.
        self.case.source_case.fixture.save_contributions()
        self.preparation = self.case.confirm_zero()
        self.case.configure()
        ids = [self.case.generate(fact)['operationRequirementId'] for fact in self.case.facts]
        self.nq_saved = native.OperationRequirementService.allocate_group(user=self.user,
            production_plan_id=self.plan.pk, contributions=[{'operationRequirementId': ident,
                'routingStepId': self.nq_step.pk, 'idempotencyKey': f'sim-context-nq-{ident}'} for ident in ids],
            reason='SIMULATED_FOR_TEST cross-step no-date read regression')
        self.nq_ids = set(ids)

    def read(self, *, whole=False, user=None):
        args = {'user': self.user if user is None else user, 'production_plan_id': self.plan.pk}
        if not whole:
            args['routing_step_id'] = self.positive_step.pk
        return capacity.AllocatedLoadCapacityReadinessService.assess(**args)

    def readonly(self, callback):
        before = self.f.full_database_snapshot()
        changes = connection.connection.total_changes

        def no_writes(execute, sql, params, many, context):
            verb = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ''
            if verb not in {'SELECT', 'PRAGMA', 'SAVEPOINT', 'RELEASE', 'ROLLBACK', 'BEGIN', 'COMMIT'}:
                raise AssertionError('No-date read attempted ' + verb)
            return execute(sql, params, many, context)

        with ExitStack() as stack:
            for target in ('pde.daily_capacity_service.working_date_window',
                    'pde.daily_capacity_views.production_plan_date_preview',
                    'pde.operation_requirement_service.OperationRequirementService.generate',
                    'pde.operation_requirement_service.OperationRequirementService.allocate',
                    'pde.operation_requirement_service.OperationRequirementService.allocate_group'):
                stack.enter_context(patch(target, side_effect=AssertionError('Read must not schedule or write')))
            stack.enter_context(connection.execute_wrapper(no_writes))
            try:
                return callback()
            finally:
                self.assertEqual(connection.connection.total_changes, changes)
                self.assertEqual(self.f.full_database_snapshot(), before)

    def traced_read(self, *, whole=False):
        source_calls, demand_calls, preparation_calls, step_calls, budget_calls = [], [], [], [], []
        real_source, real_demand = workload.read_for_plan, native.process_demand_for_plan
        real_preparation, real_step = nonquantified._plan_preparation, native.resolve_step_context
        real_budget = native._scope_budget
        real_readiness = capacity.DailyCapacityReadinessService.assess
        phase = {'lower_readiness': False}

        def source(**kwargs):
            source_calls.append(kwargs)
            return real_source(**kwargs)

        def demand(*args, **kwargs):
            demand_calls.append({**kwargs, 'observedLowerReadiness': phase['lower_readiness']})
            return real_demand(*args, **kwargs)

        def preparation(**kwargs):
            preparation_calls.append({**kwargs, 'observedLowerReadiness': phase['lower_readiness']})
            return real_preparation(**kwargs)

        def readiness(*args, **kwargs):
            previous = phase['lower_readiness']
            phase['lower_readiness'] = True
            try:
                return real_readiness(*args, **kwargs)
            finally:
                phase['lower_readiness'] = previous

        def step(plan, step_id, **kwargs):
            result = real_step(plan, step_id, **kwargs)
            step_calls.append((step_id, kwargs, result['step'].pk))
            return result

        def budget(req, company_id, **kwargs):
            result = real_budget(req, company_id, **kwargs)
            budget_calls.append((req.pk, dict(result)))
            return result

        with patch.object(workload, 'read_for_plan', side_effect=source), \
                patch.object(native, 'process_demand_for_plan', side_effect=demand), \
                patch.object(nonquantified, '_plan_preparation', side_effect=preparation), \
                patch.object(native, 'resolve_step_context', side_effect=step), \
                patch.object(native, '_scope_budget', side_effect=budget), \
                patch.object(capacity.DailyCapacityReadinessService, 'assess', side_effect=readiness):
            result = self.readonly(lambda: self.read(whole=whole))
        return result, source_calls, demand_calls, preparation_calls, step_calls, budget_calls

    def test_positive_target_keeps_actor_shared_cache_and_other_step_budget_proof(self):
        result, source, demand, preparation, steps, budgets = self.traced_read()
        self.assertTrue(result['scopeNoDateReady'], result)
        self.assertNotIn('NON_QUANTIFIED_CONTEXT_REQUIRED', codes(result))
        cache = source[0]['_read_cache']
        self.assertIsInstance(cache, native._ReadOnlyProofCache)
        self.assertIs(source[0]['user'], self.user)
        self.assertTrue(demand)
        self.assertTrue(preparation)
        for call in demand + preparation:
            self.assertIs(call['user'], self.user)
            self.assertIs(call['read_cache'], cache)
        self.assertTrue(all(call['generation_context']['routingStepId'] == self.nq_step.pk
            for call in preparation))
        historical = [(requested, actual) for requested, kwargs, actual in steps if kwargs.get('historical')]
        self.assertIn((self.positive_step.pk, self.positive_step.pk), historical)
        self.assertIn((self.nq_step.pk, self.nq_step.pk), historical)
        self.assertTrue(budgets)
        self.assertTrue(all(budget == {self.plan.pk: self.plan.planned_qty} for _, budget in budgets))
        self.assertEqual(sum(budgets[0][1].values()), self.f.item.quantity)
        row, = result['steps']
        self.assertEqual(row['stepId'], self.positive_step.pk)
        self.assertEqual(Decimal(row['processDemand']['quantity']), Decimal('4'))
        self.assertEqual(result['matchedAllocationCount'], 3)
        self.assertEqual(Decimal(row['capacityMatches'][0]['durationDays']), Decimal('.208'))
        self.assertEqual(len(native.ProductionPlanOperationRequirementAllocation.objects.filter(
            production_plan=self.plan)), 6)
        for name in ('businessWriteCount', 'dateOccupationCount', 'productionScheduleCreatedCount'):
            self.assertEqual(result[name], 0)

    def test_whole_initial_read_and_second_demands_use_one_current_cache(self):
        calls = []
        real_read = native.OperationRequirementService.read

        def read(**kwargs):
            calls.append(kwargs)
            return real_read(**kwargs)

        with patch.object(native.OperationRequirementService, 'read', side_effect=read):
            result, _, demand, preparation, _, _ = self.traced_read(whole=True)
        self.assertTrue(result['allocatedLoadReadPassed'], result)
        self.assertEqual(result['allocationRead']['resultCount'], 6)
        self.assertTrue(calls and demand and preparation)
        cache = calls[0]['_read_cache']
        self.assertIs(calls[0]['user'], self.user)
        self.assertIsInstance(cache, native._ReadOnlyProofCache)
        self.assertTrue(any(not call['observedLowerReadiness'] for call in demand))
        self.assertTrue(any(not call['observedLowerReadiness'] for call in preparation))
        self.assertTrue(any(call['observedLowerReadiness'] for call in preparation))
        for call in demand + preparation:
            self.assertIs(call['user'], self.user)
            if call['observedLowerReadiness']:
                # This existing lower-level reader owns a separate authorized
                # read. Its signature and proof pipeline are not extended.
                self.assertIsInstance(call['read_cache'], native._ReadOnlyProofCache)
                self.assertEqual(call['read_cache'].user_id, self.user.pk)
                self.assertEqual(call['read_cache'].company_id, self.user.company_id)
            else:
                self.assertIs(call['read_cache'], cache)
        self.assertNotIn('NON_QUANTIFIED_CONTEXT_REQUIRED', codes(result))

    def test_missing_actor_or_plan_permission_reject_before_cache_construction(self):
        with patch.object(native, '_source_read_cache', side_effect=AssertionError('Unauthorized cache construction')):
            with self.assertRaises(native.OperationRequirementError) as caught:
                self.readonly(lambda: capacity.AllocatedLoadCapacityReadinessService.assess(
                    user=None, production_plan_id=self.plan.pk, routing_step_id=self.positive_step.pk))
            self.assertEqual(caught.exception.code, 'ORGANIZATION_REQUIRED')
            RolePermission.objects.filter(role=self.f.role, permission__code=native.PLAN_VIEW).delete()
            with self.assertRaises(native.OperationRequirementError) as caught:
                self.readonly(self.read)
            self.assertEqual(caught.exception.code, 'PERMISSION_DENIED')

    def test_fresh_call_rechecks_current_preparation_permission(self):
        first = self.readonly(self.read)
        self.assertTrue(first['scopeNoDateReady'], first)
        RolePermission.objects.filter(role=self.f.role, permission__code=preparation_view()).delete()
        result = self.readonly(self.read)
        self.assertFalse(result['allocatedLoadReadPassed'], result)
        self.assertIn('PERMISSION_DENIED', codes(result))
        self.assertEqual(result['matchedAllocationCount'], 0)

    def test_other_step_bad_native_preparation_proof_still_blocks_target(self):
        MasterDataWriteRequest.objects.filter(pk=self.preparation['writeRequestId']).update(status='RESERVED')
        result = self.readonly(self.read)
        self.assertFalse(result['allocatedLoadReadPassed'], result)
        self.assertIn('PREPARATION_HISTORY_INVALID', codes(result))
        self.assertEqual(result['matchedAllocationCount'], 0)


def preparation_view():
    from .operation_input_preparation_service import VIEW
    return VIEW
