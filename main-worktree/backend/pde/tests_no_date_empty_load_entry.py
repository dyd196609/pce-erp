"""SIMULATED_FOR_TEST: legal empty load is not quantitative matching.

Native cases use real existing sources/object decisions and the full zero-write
guard. Pure projection cases do not substitute for native policy proof; the
parent separately exercises persisted WAITING/NSE policies in a guarded copy.
Only the parent's unique disposable runner may execute this module.
"""
from copy import deepcopy
from decimal import Decimal
import json
from unittest.mock import patch

from django.db import connection, transaction
from django.test import SimpleTestCase, TestCase

from masterdata.models import MasterDataWriteRequest
from planning.models import ProductionPlan
from system.models import RolePermission
from . import daily_capacity_service as capacity
from . import operation_workload_source_service as source
from . import routing_object_applicability_service as objects
from . import tests_conditional_workload_review as waiting_projection
from . import tests_quantity_policy_workload_review as quantity_projection
from . import tests_routing_object_applicability_service as object_fixtures
from . import tests_single_step_no_date_capacity as native_fixtures
from . import tests_no_date_read_context as saved_context_fixtures
from .models import RoutingStep


class NativeEmptyLoadEntryTests(TestCase):
    def setUp(self):
        self.case = native_fixtures.SingleStepNoDateCapacityTests(methodName='runTest')
        self.case.setUp()
        self.f, self.plan, self.step = self.case.f, self.case.plan, self.case.other_step

    def exclude(self, step=None):
        step = self.step if step is None else step
        original = self.f.step
        self.f.step = step
        try:
            fixture = object_fixtures.make_object_applicability_fixture(f=self.f, plan=self.plan)
        finally:
            self.f.step = original
        return objects.confirm_group(self.f.user, self.plan.pk, step.pk, fixture.contributions,
            'SIMULATED_FOR_TEST exact native all-object exclusion')

    def read(self, step=None):
        return self.case.read(routing_step_id=(self.step if step is None else step).pk, allow_error=True)

    def assert_no_quantitative_claim(self, result):
        for key in ('scopeNoDateReady', 'allocatedLoadReadPassed', 'noDateReady', 'planningReady', 'noDateMatchPassed'):
            self.assertIs(result[key], False)
        self.assertEqual((result['matchedStepCount'], result['matchedAllocationCount']), (0, 0))
        self.assertEqual(result['businessWriteCount'], 0)
        self.assertEqual(result['dateOccupationCount'], 0)
        self.assertEqual(result['productionScheduleCreatedCount'], 0)
        row, = result['steps']
        self.assertIs(row['noDateMatchPassed'], False)
        self.assertIsNone(row['processDemand'])
        self.assertEqual(row['capacityMatches'], [])
        self.assertIsNone(row['objectCoverage']['complete'])
        for value in (result, row):
            for key in ('durationDays', 'productionDays', 'startDate', 'finishDate'):
                self.assertNotIn(key, value)
        return row

    def test_native_all_excluded_empty_step_retains_dependency_and_raw_time_references(self):
        self.exclude()
        with patch.object(capacity.DailyCapacityReadinessService, 'assess',
                side_effect=AssertionError('Legal empty policy must retain its native applicability')), \
                patch.object(capacity, '_allocated_capacity_duration', side_effect=AssertionError('No independent load')):
            result = self.read()
        self.assertIsInstance(result, dict)
        self.assertTrue(result['legalEmptyLoadVerified'], result)
        self.assertIs(result['independentAllocationRequired'], False)
        self.assertEqual(result['statusCode'], 'NOT_APPLICABLE_VERIFIED')
        row = self.assert_no_quantitative_claim(result)
        self.assertEqual(row['predecessorSequences'], self.step.predecessor_sequences)
        self.assertEqual(row['applicability'], result['allocationRead']['sourceRead']['applicability'])
        self.assertEqual(row['timeReferences']['step'], {'preparationDays': None, 'transferDays': None, 'timeUnit': 'DAY'})
        self.assertEqual(result['blockers'], [])
        for name in ('formalRequirements', 'savedAllocations'):
            persisted = result['allocationRead']['sourceRead'][name]['persistence']
            self.assertEqual((persisted['readStatus'], persisted['recordCount'], persisted['recordIds']), ('loaded', 0, []))

    def test_ordinary_required_empty_step_still_requires_actual_saved_allocation(self):
        result = self.read()
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get('legalEmptyLoadVerified', False))
        self.assertFalse(result['allocatedLoadReadPassed'])
        self.assertIn('PROCESS_DEMAND_PLAN_ALLOCATION_MISSING', saved_context_fixtures.codes(result))

    def test_formal_exclusion_never_conceals_existing_native_requirements(self):
        before_ids = list(source._workload_requirement_rows(company_id=self.f.company.pk,
            base=self.f.source_calc, item=self.f.item, step=self.f.step).order_by('pk').values_list('pk', flat=True))
        self.assertTrue(before_ids)
        self.exclude(self.f.step)
        result = self.read(self.f.step)
        self.assertIsInstance(result, dict)
        self.assertFalse(result['legalEmptyLoadVerified'])
        self.assertEqual(result['statusCode'], 'LEGAL_EMPTY_LOAD_CONFLICT')
        persisted = result['allocationRead']['sourceRead']['formalRequirements']['persistence']
        self.assertEqual(persisted['recordIds'], before_ids)
        self.assertEqual(persisted['recordCount'], len(before_ids))
        self.assertIn('OBJECT_APPLICABILITY_SCOPE_UNPROVEN', saved_context_fixtures.codes(result))
        self.assert_no_quantitative_claim(result)

    def test_native_policy_ledger_plan_state_dependency_and_permission_remain_current(self):
        confirmed = self.exclude()

        def damage_dependency():
            # Exact corruption of this disposable row only; preserve the real
            # published-step ORM write guard and measure the native read as RO.
            with connection.cursor() as cursor:
                cursor.execute('UPDATE ' + connection.ops.quote_name(RoutingStep._meta.db_table)
                    + ' SET predecessor_sequences = %s WHERE id = %s', [json.dumps([99999]), self.step.pk])
                self.assertEqual(cursor.rowcount, 1)

        corruptions = (
            ('OBJECT_APPLICABILITY_COMMIT_INVALID', lambda: MasterDataWriteRequest.objects.filter(
                pk=confirmed['objects'][0]['writeRequestId']).update(status='RESERVED')),
            ('OBJECT_APPLICABILITY_PLAN_INVALID', lambda: ProductionPlan.objects.filter(pk=self.plan.pk).update(status='draft')),
            ('DEPENDENCY_REFERENCE_MISSING', damage_dependency),
            ('PERMISSION_DENIED', lambda: RolePermission.objects.filter(role=self.f.role, permission__code=source.native.PLAN_VIEW).delete()),
        )
        for expected, corrupt in corruptions:
            with self.subTest(expected=expected), transaction.atomic():
                corrupt()  # Deliberate disposable-fixture fault; measured read still forbids DML.
                result = self.read()
                if isinstance(result, Exception):
                    self.assertEqual(result.code, expected)
                else:
                    self.assertFalse(result.get('legalEmptyLoadVerified', False), result)
                    self.assertIn(expected, saved_context_fixtures.codes(result))
                transaction.set_rollback(True)


class SavedNonQuantifiedIsNotEmptyTests(TestCase):
    def test_real_positive_saved_quantity_with_zero_capacity_keeps_all_native_load_proof(self):
        case = saved_context_fixtures.NoDateReadContextTests(methodName='runTest')
        case.setUp()
        result = case.readonly(lambda: capacity.AllocatedLoadCapacityReadinessService.assess(
            user=case.user, production_plan_id=case.plan.pk, routing_step_id=case.nq_step.pk))
        self.assertTrue(result['allocatedLoadReadPassed'], result)
        self.assertFalse(result.get('legalEmptyLoadVerified', False))
        self.assertEqual(result['allocationRead']['resultCount'], 3)
        saved = result['allocationRead']['sourceRead']['savedAllocations']
        self.assertEqual(saved['statusCode'], 'SAVED')
        self.assertEqual(len(saved['items']), 3)
        self.assertGreater(Decimal(saved['quantity']), 0)
        row, = result['steps']
        self.assertEqual(row['capacitySemantics']['meaningCode'], 'NON_QUANTIFIED')
        self.assertEqual(row['capacityMatches'], [])
        self.assertFalse(result['scopeNoDateReady'])


class EmptyLoadProjectionGuardTests(SimpleTestCase):
    """Pure returned-contract guards; no successful native proof is mocked."""
    def row(self, kind):
        if kind == 'NOT_SEPARATELY_MEASURED':
            row = quantity_projection.QuantityPolicyWorkloadReviewTests(methodName='runTest').row()
        else:
            row = waiting_projection.ConditionalWorkloadReviewTests(methodName='runTest').row()
            row['scope'] = dict(zip(('companyId', 'productionPlanId', 'manufacturingOutputId', 'mainCalculationId',
                'salesOrderItemId', 'baselineId', 'routingVersionId', 'routingStepId', 'operationId', 'productTypeId'), range(21, 31)))
            if kind == 'NOT_APPLICABLE':
                row['applicability'] = {'result': 'NOT_APPLICABLE'}
        row['factSource'] = 'server'
        for name in ('formalRequirements', 'savedAllocations'):
            row[name].update(statusCode=kind, blockers=[], quantity=None, uomId=None, uomLabel=None)
            row[name]['persistence'].update(factSource='server', recordIds=[], operationMismatchRecordIds=[])
        return row

    def test_three_verified_returned_contracts_stay_distinct_and_input_is_unchanged(self):
        for original, expected in (('NOT_APPLICABLE', 'NOT_APPLICABLE_VERIFIED'),
                ('WAITING_TRIGGER', 'WAITING_TRIGGER'), ('NOT_SEPARATELY_MEASURED', 'NOT_SEPARATELY_MEASURED_VERIFIED')):
            row = self.row(original)
            before = deepcopy(row)
            result = capacity._empty_load_policy(row)
            self.assertEqual((result['statusCode'], result['blockers']), (expected, []))
            self.assertEqual(row, before)

    def test_current_persistence_failure_nonempty_or_wrong_operation_is_not_empty(self):
        for kind in ('NOT_APPLICABLE', 'WAITING_TRIGGER', 'NOT_SEPARATELY_MEASURED'):
            for name in ('formalRequirements', 'savedAllocations'):
                for changed in ({'readStatus': 'read_failed', 'recordCount': None, 'recordIds': None},
                        {'recordCount': 1, 'recordIds': [501]}, {'operationMismatchRecordIds': [502]}, {'recordCount': False}):
                    with self.subTest(kind=kind, bucket=name, changed=changed):
                        row = self.row(kind)
                        row[name]['persistence'].update(changed)
                        self.assertTrue(capacity._empty_load_policy(row)['blockers'])

    def test_exact_scope_null_quantity_and_native_blockers_cannot_be_discarded(self):
        for kind in ('NOT_APPLICABLE', 'WAITING_TRIGGER', 'NOT_SEPARATELY_MEASURED'):
            for key in self.row(kind)['scope']:
                row = self.row(kind)
                row['scope'][key] = None
                result = capacity._empty_load_policy(row)
                self.assertTrue(result is None or result['blockers'])
            row = self.row(kind)
            row['savedAllocations']['quantity'] = 0
            self.assertTrue(capacity._empty_load_policy(row)['blockers'])
            row = self.row(kind)
            row['blockers'] = [{'code': 'NATIVE_SOURCE_PROOF_INVALID', 'statusLabel': '原生证明失效'}]
            self.assertIn(row['blockers'][0], capacity._empty_load_policy(row)['blockers'])

    def test_unknown_object_partition_is_never_an_all_excluded_empty_policy(self):
        row = self.row('NOT_APPLICABLE')
        row['applicability']['objectApplicability'] = {'complete': False, 'result': 'PENDING'}
        self.assertIn('OBJECT_APPLICABILITY_SCOPE_UNPROVEN',
            {item['code'] for item in capacity._empty_load_policy(row)['blockers']})

    def test_zero_capacity_unverified_or_triggered_policy_never_selects_empty_branch(self):
        for changes in ({'formalPolicyValidated': False}, {'triggerStatus': 'TRIGGERED'}):
            row = self.row('WAITING_TRIGGER')
            row['applicability']['conditionalExecution'].update(changes)
            self.assertIsNone(capacity._empty_load_policy(row))
        row = self.row('NOT_SEPARATELY_MEASURED')
        row['inputPreparation']['quantityPolicy']['plannedQuantity'] = 0
        self.assertIsNone(capacity._empty_load_policy(row))
        row['inputPreparation'] = None
        self.assertEqual(row['capacitySemantics']['sourceValue'], '0')
        self.assertIsNone(capacity._empty_load_policy(row))
