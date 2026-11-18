"""SIMULATED_FOR_TEST: shared saved-load capacity assessment, no business DB.

The guarded parent runner owns the disposable test database.  Existing fixture
builders create real formal sources and saved allocations; their test methods
are not inherited or rediscovered.  Date comparisons use the archived original
consumer with explicit in-memory fixtures, never the acceptance plan.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.db import transaction
from django.test import SimpleTestCase, TestCase

from system.models import Company, User
from planning.models import Demand, PlanningRequirement, ProductionPlan
from sales.models import SalesOrderItem
from . import daily_capacity_service as capacity_service
from . import daily_capacity_views as capacity_views
from . import operation_requirement_service as operation
from . import tests_calc4_routing_correction as correction_fixtures
from . import tests_plan_legal_extension_admission as legal_fixtures
from . import tests_daily_capacity_date_preview as date_fixtures
from .models import EngineeringOperationRequirement, ProductionPlanOperationRequirementAllocation, WorkCenter
from .operation_requirement_correction_service import require_effective_requirement


CALENDAR = deepcopy(date_fixtures.CALENDAR)
BEFORE_VIEWS = Path(__file__).resolve().parents[2] / (
    'docs/evidence/PCE_ALLOCATED_LOAD_NO_DATE_CAPACITY_20261015/'
    'source-before/backend/pde/daily_capacity_views.py')


def codes(value):
    if isinstance(value, dict):
        return ({str(value['code'])} if value.get('code') else set()).union(
            *(codes(child) for child in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(codes(child) for child in value))
    return set()


class NoDateAllocatedCapacityPersistenceTests(TestCase):
    def setUp(self):
        original_factory = correction_fixtures.Calc4RoutingCorrectionTests.make_capacity

        def declared_capacity(fixture, operation_row, uom, code, **overrides):
            # Declare compatible test facts before any manufacturing EOR or
            # allocation snapshot exists. Never repair a saved snapshot to pass.
            fixture.product_type.code = 'SIM-FULL/CTX'
            fixture.product_type.save(update_fields=('code',))
            fixture.center.capacity_policy = {'calendar': deepcopy(CALENDAR)}
            fixture.center.save(update_fields=('capacity_policy',))
            return original_factory(fixture, operation_row, uom, code,
                preparation_days=Decimal('.1'), transfer_days=Decimal('.1'), **overrides)

        self.fixture = legal_fixtures.PlanLegalExtensionAdmissionTests(methodName='runTest')
        with patch.object(correction_fixtures.Calc4RoutingCorrectionTests, 'make_capacity', declared_capacity):
            self.fixture.setUp()
        self.f = self.fixture.f
        self.plan = self.fixture.plan
        self.requirements = self.fixture.requirements
        self.assertEqual(len(self.requirements), 3)

    def save_contributions(self, requirements=None):
        requirements = self.requirements if requirements is None else requirements
        return operation.OperationRequirementService.allocate_group(user=self.f.user,
            production_plan_id=self.plan.pk, contributions=[{
                'operationRequirementId': row.pk, 'routingStepId': self.f.step.pk,
                'idempotencyKey': f'sim-no-date-{row.pk}'} for row in requirements],
            reason='SIMULATED_FOR_TEST no-date assessment fixture')

    def assess(self, *, user=None, plan_id=None):
        before = self.f.full_database_snapshot()
        try:
            return capacity_service.AllocatedLoadCapacityReadinessService.assess(
                user=user or self.f.user, production_plan_id=plan_id or self.plan.pk)
        finally:
            self.assertEqual(self.f.full_database_snapshot(), before,
                'assessment must not persist facts, audits, state transitions or allocations')

    def target(self, result):
        return next(row for row in result['steps'] if row['stepId'] == self.f.step.pk)

    def assert_blocked(self, *, expected_code=None, user=None, plan_id=None):
        try:
            result = self.assess(user=user, plan_id=plan_id)
        except capacity_service.DailyCapacityError as error:
            if expected_code:
                self.assertEqual(error.code, expected_code)
            return error
        self.assertFalse(result['noDateReady'], result)
        self.assertFalse(result['planningReady'], result)
        self.assertEqual(result['businessWriteCount'], 0)
        if expected_code:
            self.assertIn(expected_code, codes(result), result)
        return result

    def test_three_real_saved_objects_are_consumed_without_dates_or_writes(self):
        self.save_contributions()
        result = self.assess()
        self.assertTrue(result['allocatedLoadReadPassed'], result)
        self.assertTrue(result['allRequiredStepsCovered'], result)
        self.assertTrue(result['noDateReady'], result)
        self.assertFalse(result['planningReady'])
        self.assertFalse(result['planExecutionWindowEvaluated'])
        self.assertEqual(result['matchedStepCount'], 1)
        self.assertEqual(result['matchedAllocationCount'], 3)
        step = self.target(result)
        self.assertEqual(Decimal(step['processDemand']['quantity']), Decimal(4))
        self.assertEqual(set(step['processDemand']['operationRequirementIds']),
            {row.pk for row in self.requirements})
        self.assertEqual(len(step['processDemand']['contributions']), 3)
        self.assertTrue(step['objectCoverage']['complete'])
        self.assertEqual(step['objectCoverage']['designItemIds'],
            step['objectCoverage']['expectedDesignItemIds'])
        self.assertNotIn('dates', result)
        self.assertNotIn('startDateInput', result)

    def test_preparation_and_transfer_are_applied_once_per_step_not_per_object(self):
        self.save_contributions()
        step = self.target(self.assess())
        match = step['capacityMatches'][0]
        self.assertEqual(Decimal(match['productionDays']), Decimal('.008'))
        self.assertEqual(Decimal(match['preparationDays']), Decimal('.1'))
        self.assertEqual(Decimal(match['transferDays']), Decimal('.1'))
        self.assertEqual(Decimal(match['durationDays']), Decimal('.208'))
        self.assertNotEqual(Decimal(match['durationDays']), Decimal('.624'))

    def test_no_saved_allocation_is_missing_not_a_candidate_or_zero_demand(self):
        result = self.assert_blocked(expected_code='PROCESS_DEMAND_PLAN_ALLOCATION_MISSING')
        self.assertIsInstance(result, dict)
        step = self.target(result)
        self.assertIsNone(step.get('processDemand'))
        self.assertEqual(step['capacityMatches'], [])
        self.assertEqual(result['matchedAllocationCount'], 0)
        self.assertFalse(result['allRequiredStepsCovered'])

    def test_one_saved_object_preserves_its_load_but_is_not_complete_coverage(self):
        self.save_contributions(self.requirements[:1])
        result = self.assert_blocked(expected_code='OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN')
        self.assertTrue(result['allocatedLoadReadPassed'])
        step = self.target(result)
        self.assertEqual(Decimal(step['processDemand']['quantity']),
            self.requirements[0].workload_quantity)
        self.assertFalse(step['objectCoverage']['complete'])
        self.assertFalse(result['allRequiredStepsCovered'])

    def test_two_saved_objects_are_not_completed_from_the_unsaved_effective_eor(self):
        self.save_contributions(self.requirements[:2])
        result = self.assert_blocked(expected_code='OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN')
        step = self.target(result)
        self.assertEqual(len(step['processDemand']['contributions']), 2)
        self.assertEqual(Decimal(step['processDemand']['quantity']),
            sum((row.workload_quantity for row in self.requirements[:2]), Decimal(0)))
        self.assertNotIn(self.requirements[2].pk, step['processDemand']['operationRequirementIds'])

    def test_pending_full_route_step_blocks_overall_even_when_saved_target_matches(self):
        self.save_contributions()
        readiness = self.assess()['readiness']
        pending = deepcopy(readiness['steps'][0])
        pending.update(stepId=pending['stepId'] + 10000, sequence=10000,
            applicability={'result': 'PENDING', 'resultLabel': '适用性待确认'},
            blockerCodes=['SIM_APPLICABILITY_PENDING'], blockerLabels=['SIMULATED_FOR_TEST'],
            dailyCapacity=[])
        readiness['steps'].append(pending)
        readiness['blockers'].append({'code': 'SIM_APPLICABILITY_PENDING', 'statusLabel': 'SIMULATED_FOR_TEST'})
        with patch.object(capacity_service.DailyCapacityReadinessService, 'assess', return_value=readiness):
            result = self.assess()
        self.assertEqual(result['matchedStepCount'], 1)
        self.assertTrue(self.target(result)['noDateMatchPassed'])
        self.assertFalse(result['allRequiredStepsCovered'])
        self.assertFalse(result['noDateReady'])
        self.assertEqual(len(result['steps']), 2)
        self.assertIn('SIM_APPLICABILITY_PENDING', codes(result))

    def test_not_applicable_and_auxiliary_steps_are_retained_without_independent_load(self):
        self.save_contributions()
        readiness = self.assess()['readiness']
        for sequence, state, mode in [(10000, 'NOT_APPLICABLE', None),
                (20000, 'REQUIRED', capacity_service.AUXILIARY_DATE_MODE)]:
            skipped = deepcopy(readiness['steps'][0])
            skipped.update(stepId=sequence, sequence=sequence,
                applicability={'result': state, 'resultLabel': 'SIMULATED_FOR_TEST'},
                capacityDateMode=mode, blockerCodes=[], blockerLabels=[], dailyCapacity=[])
            readiness['steps'].append(skipped)
        with patch.object(capacity_service.DailyCapacityReadinessService, 'assess', return_value=readiness):
            result = self.assess()
        self.assertTrue(result['noDateReady'], result)
        self.assertEqual(result['matchedAllocationCount'], 3)
        self.assertEqual(len(result['steps']), 3)
        self.assertEqual([row['statusCode'] for row in result['steps'][1:]], ['NOT_APPLICABLE', 'AUXILIARY'])
        self.assertTrue(all(row['processDemand'] is None for row in result['steps'][1:]))

    def test_missing_calendar_does_not_erase_matched_load_or_grant_date_readiness(self):
        self.save_contributions()
        self.f.center.capacity_policy = {}
        self.f.center.save(update_fields=('capacity_policy',))
        result = self.assess()
        self.assertEqual(result['matchedAllocationCount'], 3, result)
        self.assertTrue(result['allocatedLoadReadPassed'])
        self.assertFalse(result['planningReady'])
        self.assertFalse(result['planExecutionWindowEvaluated'])
        self.assertIn('MANUFACTURING_CALENDAR_MISSING', codes(result))
        self.assertTrue(self.target(result)['capacityMatches'])

    def test_no_date_entry_never_calls_the_date_consumer_or_working_window(self):
        self.save_contributions()
        with patch.object(capacity_views, 'production_plan_date_preview',
                side_effect=AssertionError('No-date assessment must not preview dates')), patch.object(
                capacity_service, 'working_date_window',
                side_effect=AssertionError('No-date assessment must not allocate calendar slots')):
            result = self.assess()
        self.assertTrue(result['noDateReady'])

    def test_saved_source_and_extension_hash_drift_remain_rejected(self):
        self.save_contributions()
        self.fixture.raw(self.fixture.extension, 'input_hash', '0' * 64)
        self.assert_blocked()

    def test_saved_source_different_order_line_or_baseline_remains_rejected(self):
        self.save_contributions()
        other = SalesOrderItem.objects.create(sales_order=self.f.order, line_no=2,
            material=self.f.item.material, quantity=37, uom=self.f.pcs,
            required_date=date.today(), engineering_mode='ORDER_ENGINEERED')
        for target, field, value in [(self.fixture.extension, 'sales_order_item', other.pk),
                (self.fixture.facts[0], 'trace', {**self.fixture.facts[0].trace,
                    'baselineId': self.f.baseline.pk + 10000})]:
            with self.subTest(field=field), transaction.atomic():
                self.fixture.raw(target, field, value)
                self.assert_blocked()
                transaction.set_rollback(True)

    def test_saved_contribution_moved_to_another_plan_cannot_leak_into_either_scope(self):
        self.save_contributions()
        f = self.f
        other_item = SalesOrderItem.objects.create(sales_order=f.order, line_no=2,
            material=f.item.material, quantity=37, uom=f.pcs,
            required_date=date.today(), engineering_mode='ORDER_ENGINEERED')
        demand = f.initial(Demand, 'draft', demand_no='SIM-NO-DATE-OTHER-DEMAND',
            source_type='sales_order', source_document_type='SalesOrder',
            source_document_id=str(f.order.pk), source_document_no=f.order.order_no,
            sales_order_item=other_item, material=f.item.material,
            required_qty=37, required_date=date.today(), department=f.department,
            reason='SIMULATED_FOR_TEST', acceptance_marker='SIMULATED_FOR_TEST', created_by=f.user)
        f.advance(demand, 'confirmed')
        requirement = f.initial(PlanningRequirement, 'draft', requirement_no='SIM-NO-DATE-OTHER-REQ',
            demand=demand, material=f.item.material, demand_qty=37, available_qty=0, net_required_qty=37,
            required_date=date.today(), supply_type='production',
            calculation_facts={'sourceKind': 'SIMULATED_FOR_TEST'}, created_by=f.user)
        f.advance(requirement, 'calculated')
        f.advance(requirement, 'confirmed')
        other = f.initial(ProductionPlan, 'draft', plan_no='SIM-NO-DATE-OTHER-PLAN',
            planning_requirement=requirement, material=f.item.material, planned_qty=37,
            required_date=date.today(), source_id=str(requirement.pk), confirmed_by=f.user)
        f.advance(other, 'confirmed')
        moved = ProductionPlanOperationRequirementAllocation.objects.order_by('pk').first()
        self.fixture.raw(moved, 'production_plan', other.pk)
        result = self.assert_blocked()
        self.assertIsInstance(result, dict)
        self.assertNotIn(moved.pk, [row['allocationId'] for row in result['allocationRead']['allocations']])
        self.assert_blocked(plan_id=other.pk)

    def test_saved_source_fact_drift_is_not_hidden_by_a_previous_success(self):
        self.save_contributions()
        self.assertTrue(self.assess()['noDateReady'])
        self.fixture.raw(self.fixture.facts[0], 'value', {'decimal': '900'})
        self.assert_blocked()

    def test_history_replacement_does_not_remain_an_effective_saved_load(self):
        self.f.correct()  # Supersede the separate legacy group before any save.
        self.save_contributions()
        # The original fixture's correction used the real immutable replacement
        # service. Corrupt only this disposable allocation to reference its old
        # requirement: production cannot perform this substitution through save.
        row = ProductionPlanOperationRequirementAllocation.objects.order_by('pk').first()
        historical = EngineeringOperationRequirement.objects.get(pk=self.f.old_ids[0])
        with self.assertRaises(operation.OperationRequirementError) as rejected:
            require_effective_requirement(historical, self.f.company.pk)
        self.assertEqual(rejected.exception.code, 'OPERATION_REQUIREMENT_SUPERSEDED')
        self.fixture.raw(row, 'operation_requirement', historical.pk)
        result = self.assert_blocked(expected_code='OPERATION_REQUIREMENT_SUPERSEDED')
        self.assertFalse(result['allocatedLoadReadPassed'])
        self.assertEqual(result['matchedAllocationCount'], 0)

    def test_wrong_saved_unit_is_rejected_without_conversion(self):
        self.save_contributions()
        row = ProductionPlanOperationRequirementAllocation.objects.first()
        self.fixture.raw(row, 'uom', self.f.pcs.pk)
        self.assert_blocked()

    def test_wrong_saved_step_is_rejected_instead_of_falling_back_to_another_occurrence(self):
        self.save_contributions()
        row = ProductionPlanOperationRequirementAllocation.objects.first()
        self.fixture.raw(row, 'routing_step', self.f.wrong_step.pk)
        self.assert_blocked()

    def test_wrong_current_resource_does_not_use_a_same_named_capacity(self):
        self.save_contributions()
        other = WorkCenter.objects.create(company=self.f.company, workshop=self.f.workshop,
            department=self.f.department, code='SIM-NO-DATE-FOREIGN-RESOURCE',
            name=self.f.center.name, capacity_policy={'calendar': deepcopy(CALENDAR)})
        self.fixture.raw(self.f.capacity, 'work_center', other.pk)
        self.assert_blocked()

    def test_changed_capacity_quantity_or_usage_declaration_does_not_bypass_native_proof(self):
        self.save_contributions()
        for field, value in [('quantity', Decimal('999')), ('conditions', {
            'capacityUsageScope': {'usageScope': 'ENGINEERING_EOR_ONLY'}})]:
            with self.subTest(field=field), transaction.atomic():
                self.fixture.raw(self.f.capacity, field, value)
                self.assert_blocked()
                transaction.set_rollback(True)

    def test_changed_plan_budget_does_not_scale_area_or_accept_overallocation(self):
        self.save_contributions()
        self.fixture.raw(self.plan, 'planned_qty', Decimal(38))
        self.fixture.raw(self.plan.planning_requirement, 'net_required_qty', Decimal(38))
        self.assert_blocked()

    def test_duplicate_contribution_snapshot_is_rejected_not_silently_deduplicated(self):
        self.save_contributions()
        rows = list(ProductionPlanOperationRequirementAllocation.objects.order_by('pk'))
        self.fixture.raw(rows[1], 'source_snapshot', rows[0].source_snapshot)
        self.fixture.raw(rows[1], 'input_hash', rows[0].input_hash)
        self.assert_blocked()

    def test_foreign_company_or_missing_permission_cannot_read_the_plan(self):
        self.save_contributions()
        company = Company.objects.create(code='SIM-NO-DATE-OTHER', name='SIMULATED_FOR_TEST other company')
        for user in [User.objects.create_user(username='sim_no_date_denied', company_id=self.f.company.pk),
                User.objects.create_user(username='sim_no_date_foreign', company_id=company.pk)]:
            with self.subTest(user=user.username):
                self.assert_blocked(user=user)

    def test_unconfirmed_plan_is_not_treated_as_valid_saved_source(self):
        self.save_contributions()
        self.fixture.raw(self.plan, 'status', 'draft')
        self.assert_blocked()


class NoDateCapacityOriginalDateEquivalenceTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not BEFORE_VIEWS.is_file():
            raise AssertionError(f'Original date consumer baseline is required: {BEFORE_VIEWS}')
        spec = importlib.util.spec_from_file_location('pde._original_no_date_capacity_view_test', BEFORE_VIEWS)
        cls.old_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.old_module)

    def compare_original(self, readiness, *, quantity='100', start=date_fixtures.START,
            process_error=None, plan_status=None, capacity_rows=None, expected_error=None):
        outputs = []
        for module in (self.old_module, capacity_views):
            plan = date_fixtures.plan_fixture()
            if plan_status is not None:
                plan.status = plan_status
            query = MagicMock()
            query.get.side_effect = lambda *, pk: deepcopy(capacity_rows[pk]) if capacity_rows else date_fixtures.capacity_fixture(pk)
            process = lambda plan, output, item, step, **kw: {
                'allocationIds': [901, 902, 903], 'operationRequirementIds': [801, 802, 803],
                'quantity': Decimal(quantity), 'uomId': 1, 'productTypeId': 31,
                'routingStepId': step['stepId'], 'contributions': [
                    {'allocationId': index, 'quantity': 'SIMULATED_FOR_TEST'} for index in (901, 902, 903)]}
            with patch.object(module.DailyCapacityReadinessService, 'assess', return_value=deepcopy(readiness)), \
                    patch.object(module, 'process_demand_for_plan', side_effect=process_error or process), \
                    patch.object(module.StandardCapacity.objects, 'select_related', return_value=query):
                try:
                    output = module.production_plan_date_preview.__wrapped__(plan, start_date=start)
                except capacity_service.DailyCapacityError as error:
                    if expected_error is None:
                        raise
                    output = {'raisedCode': error.code, 'raisedMessage': str(error)}
                else:
                    self.assertIsNone(expected_error, output)
                outputs.append(output)
        self.assertEqual(outputs[1], outputs[0])
        if expected_error is not None:
            self.assertEqual(outputs[1]['raisedCode'], expected_error)
        return outputs[1]

    def test_original_process_demand_blocker_precedes_calendar_blocker(self):
        readiness = date_fixtures.readiness_fixture(date_fixtures.step_fixture(10), ready=False)
        readiness['blockers'] = [{'code': 'MANUFACTURING_CALENDAR_MISSING'}]
        result = self.compare_original(readiness, process_error=capacity_service.DailyCapacityError(
            'PROCESS_DEMAND_PLAN_ALLOCATION_MISSING', 'SIMULATED_FOR_TEST no saved load'))
        self.assertEqual(result['processDemandBlockers'][0]['code'], 'PROCESS_DEMAND_PLAN_ALLOCATION_MISSING')
        self.assertEqual(result['statusLabel'], '工序需求、步骤分配或产能来源受阻，日期预览受阻')

    def test_original_source_status_early_return_keys_remain_identical(self):
        result = self.compare_original(date_fixtures.readiness_fixture(date_fixtures.step_fixture(10)),
            plan_status='draft', process_error=AssertionError('No demand before source status gate'))
        self.assertIn('sourceStatusBlocker', result)
        self.assertNotIn('processDemandBlockers', result)
        self.assertNotIn('processDemandFacts', result)

    def test_original_changed_first_candidate_raises_before_trying_valid_alternative(self):
        step = date_fixtures.step_fixture(10)
        second = date_fixtures.capacity_fixture(2, center_id=20)
        step['candidateWorkCenters'].append({'id': 20, 'source': 'Process.work_center', 'role': 'default'})
        step['dailyCapacity'].append(capacity_service.capacity_fact(second, date_fixtures.START))
        self.compare_original(date_fixtures.readiness_fixture(step),
            capacity_rows={1: date_fixtures.capacity_fixture(quantity='50'), 2: second},
            expected_error='CAPACITY_FACT_CHANGED')

    def test_original_successful_date_and_allocation_output_is_identical(self):
        result = self.compare_original(date_fixtures.readiness_fixture(date_fixtures.step_fixture(10)))
        self.assertTrue(result['previewReady'])
        self.assertEqual(len(result['dates']), 1)

    def test_original_blocked_calendar_readiness_never_generates_dates(self):
        readiness = date_fixtures.readiness_fixture(date_fixtures.step_fixture(10), ready=False)
        readiness['blockers'] = [{'code': 'MANUFACTURING_CALENDAR_MISSING'}]
        result = self.compare_original(readiness)
        self.assertFalse(result['previewReady'])
        self.assertEqual(result['dates'], [])

    def test_original_auxiliary_and_skipped_dependency_behavior_is_identical(self):
        auxiliary = date_fixtures.step_fixture(20, predecessors=(10,))
        auxiliary['capacityDateMode'] = 'AUXILIARY_NO_INDEPENDENT_DATE'
        result = self.compare_original(date_fixtures.readiness_fixture(
            date_fixtures.step_fixture(10), auxiliary,
            date_fixtures.step_fixture(30, predecessors=(20,))))
        self.assertTrue(result['previewReady'])
        self.assertEqual([row['sequence'] for row in result['dates']], [10, 30])

    def test_original_parallel_resource_booking_behavior_is_identical(self):
        result = self.compare_original(date_fixtures.readiness_fixture(
            date_fixtures.step_fixture(10), date_fixtures.step_fixture(20)))
        self.assertTrue(result['previewReady'])
        self.assertNotEqual(result['dates'][0]['startDate'], result['dates'][1]['startDate'])
