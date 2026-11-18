"""SIMULATED_FOR_TEST: native effective-step date-read source boundaries.

Only disposable fixtures are written.  The composed 0046 fixture retains its
synthetic numeric workbook adapter and its two established upstream document
release-readback/content stubs.  Those stubs do not certify formal releases.
No step resolver, continuation/binding proof, saved-demand reader or date
readiness result is replaced.  The extra ordinary step is created before the
fixture's original manufacturing output is frozen.  Missing calendar/capacity
facts remain real blockers; these tests do not manufacture successful dates.
"""
from contextlib import contextmanager
from copy import copy, deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings

from . import tests_plan_step_source_continuation as source_fixture
from . import operation_requirement_service as requirements
from .daily_capacity_service import DailyCapacityError, DailyCapacityReadinessService
from .daily_capacity_views import production_plan_date_preview, process_demand_for_plan
from .models import PlanStepVersionBinding, RoutingStep
from .plan_step_context_service import (
    effective_baseline, effective_calculation, source_selection,
)


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE={
    'companyCode': 'LIA', 'orderNo': 'SO-LIA-001', 'lineNo': 1,
})
class EffectiveStepDatePreviewTests(TestCase):
    """Compose the native fixture without inheriting its test methods."""

    def setUp(self):
        case = source_fixture.PlanStepSourceContinuationTests(methodName='runTest')
        # This class is not itself run as a test case here.  Build its isolated
        # class data inside this test's transaction and clean its own patches.
        case.setUpTestData()
        self.case = case
        self.addCleanup(case.doCleanups)
        manager = RoutingStep.objects
        real_create = manager.create
        ordinary = []

        def create_fixture_step(*args, **kwargs):
            step = real_create(*args, **kwargs)
            if (step.sequence == 1
                    and step.routing_version.routing.routing_code == 'SOURCE-ANCHOR-ROUTE'):
                ordinary.append(real_create(
                    routing_version=step.routing_version, sequence=2,
                    operation=step.operation, predecessor_sequences=[step.sequence],
                    operation_parameters=deepcopy(step.operation_parameters),
                ))
            return step

        # Fixture assembly only: both calls execute the real model manager.
        # This runs before native output generation/release freezes the route.
        with patch.object(manager, 'create', side_effect=create_fixture_step):
            case.setUp()
        self.assertEqual(len(ordinary), 1)
        self.ordinary_step = ordinary[0]
        self.binding_id = (None if self._testMethodName == 'test_unbound_plan_keeps_complete_original_readiness'
                           else case.activate()['bindingId'])
        self.on_date = date.today()

    def corrupt_isolated_fixture(self, model, pk, column, value):
        """Negative fixtures only, never a way around a production guard."""
        allowed = {
            (PlanStepVersionBinding, 'status'),
            (source_fixture.OrganizationOperatingAuditRecord, 'action_code'),
        }
        self.assertIn((model, column), allowed)
        self.assertEqual(connection.vendor, 'sqlite')
        configured = str(connection.settings_dict['NAME'])
        self.assertIn('native-test.sqlite3', configured.lower())
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA database_list')
            actual = next(row[2] for row in cursor.fetchall() if row[1] == 'main')
            self.assertIn('native-test.sqlite3', actual.lower())
            self.assertEqual(Path(actual).resolve(), Path(configured).resolve())
            table = connection.ops.quote_name(model._meta.db_table)
            field = connection.ops.quote_name(column)
            cursor.execute(f'UPDATE {table} SET {field}=%s WHERE id=%s', [value, pk])
            self.assertEqual(cursor.rowcount, 1)

    def assert_exact_tree(self, actual, expected):
        """Require complete values, sequence, concrete types and dict key order."""
        self.assertIs(type(actual), type(expected))
        if isinstance(expected, dict):
            self.assertEqual(list(actual), list(expected))
            for key in expected:
                self.assert_exact_tree(actual[key], expected[key])
        elif isinstance(expected, (list, tuple)):
            self.assertEqual(len(actual), len(expected))
            for left, right in zip(actual, expected):
                self.assert_exact_tree(left, right)
        else:
            self.assertEqual(actual, expected)

    def snapshot(self):
        models = (
            source_fixture.ProductionPlan, source_fixture.Demand,
            source_fixture.ProductManufacturingOutput,
            source_fixture.EngineeringCalculationRecord,
            source_fixture.EngineeringDerivedFact,
            source_fixture.PlanStepVersionBinding,
            source_fixture.ProductionPlanOperationRequirementAllocation,
            source_fixture.OrganizationOperatingAuditRecord,
            source_fixture.MasterDataWriteRequest, source_fixture.ExternalIdentity,
            source_fixture.BusinessStateTransition,
        )
        # Explicit business/proof tables only; no credential/session columns.
        return {model._meta.label: list(model.objects.order_by('pk').values())
                for model in models}

    @contextmanager
    def read_only(self):
        before = self.snapshot()
        changes = connection.connection.total_changes

        def forbid_writes(execute, sql, params, many, context):
            verb = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ''
            if verb not in {'SELECT', 'PRAGMA', 'BEGIN', 'COMMIT', 'SAVEPOINT',
                            'RELEASE', 'ROLLBACK'}:
                raise AssertionError('Effective-step date read attempted ' + verb)
            return execute(sql, params, many, context)

        try:
            with connection.execute_wrapper(forbid_writes):
                yield
        finally:
            self.assertEqual(connection.connection.total_changes, changes)
            self.assertEqual(self.snapshot(), before)

    def assess(self, *, user=None):
        return DailyCapacityReadinessService.assess_plan_date_scope(
            self.case.plan, company_id=self.case.company.pk,
            on_date=self.on_date, user=self.case.actor if user is None else user)

    def test_bound_and_ordinary_steps_keep_distinct_native_main_and_baseline(self):
        case = self.case
        with self.read_only():
            readiness, scopes = self.assess()
            self.assertTrue(readiness['effectiveStepSourcesValidated'])
            self.assertEqual(set(scopes), {1, 2})
            bound, output, _, context = scopes[1]
            ordinary, ordinary_output, _, ordinary_context = scopes[2]
            self.assertEqual(output.pk, case.anchor.pk)
            self.assertEqual(ordinary_output.pk, case.anchor.pk)
            self.assertEqual(effective_calculation(bound).pk, case.main.pk)
            self.assertEqual(effective_baseline(bound).pk, case.new_baseline.pk)
            self.assertEqual(source_selection(bound)['mainCalculationId'], case.main.pk)
            self.assertEqual(effective_calculation(ordinary).pk, case.calculations[0].pk)
            self.assertEqual(effective_baseline(ordinary).pk, case.baseline.pk)
            self.assertIsNone(source_selection(ordinary))
            self.assertEqual(context['step'].pk, case.step.pk)
            self.assertEqual(ordinary_context['step'].pk, self.ordinary_step.pk)
            rows = {row['sequence']: row for row in readiness['steps']}
            self.assertEqual(rows[1]['engineeringVersion']['mainCalculationId'], case.main.pk)
            self.assertEqual(rows[2]['engineeringVersion']['mainCalculationId'], case.calculations[0].pk)
            self.assertEqual(rows[2]['predecessorSequences'], [1])
            self.assertEqual(rows[2]['rootStepId'], self.ordinary_step.pk)
            self.assertFalse(readiness['planningReady'])
            self.assertEqual(readiness['businessWriteCount'], 0)
            self.assertEqual(readiness['productionScheduleCreatedCount'], 0)

    def test_date_reader_consumes_real_bound_allocation_and_refuses_plain_step_fallback(self):
        case = self.case
        original_type = case._consumer_type

        def exact_route_type():
            manager = source_fixture.CapacityProductType.objects
            real_create = manager.create

            def create_exact_type(*args, **kwargs):
                # Set this fixture's exact type at creation, before native
                # rules, requirements and immutable allocations reference it.
                kwargs['code'] = case.anchor.routing_version.routing.routing_code
                return real_create(*args, **kwargs)

            with patch.object(manager, 'create', side_effect=create_exact_type):
                return original_type()

        case._consumer_type = exact_route_type
        _, _, _, requirement = case._direct_requirement()
        saved = requirements.OperationRequirementService.allocate(
            user=case.actor, production_plan_id=case.plan.pk,
            operation_requirement_id=requirement.pk, routing_step_id=case.step.pk,
            idempotency_key='effective-date-bound-allocation',
            reason='SIMULATED_FOR_TEST native effective-step date source')
        # A separate, unversioned same-company plan is intentionally missing
        # a fixed output and every allocation. It is not admitted as date-ready;
        # the exact allocation reader must not borrow the first plan's rows.
        other_demand = source_fixture.create_business_object_with_initial_state(
            model=source_fixture.Demand, initial_state='draft',
            demand_no='SOURCE-DATE-OTHER-DEMAND', source_type='sales_order',
            source_document_type='SalesOrder', source_document_id=str(case.order.pk),
            source_document_no=case.order.order_no, sales_order_item=case.items[0],
            manufacturing_output=None, material=case.material, required_qty=1,
            required_date=self.on_date, department=case.department,
            reason='SIMULATED_FOR_TEST separate plan without saved allocations',
            created_by=case.actor)
        other_requirement = source_fixture.PlanningRequirement.objects.create(
            requirement_no='SOURCE-DATE-OTHER-REQUIREMENT', demand=other_demand,
            material=case.material, demand_qty=1, available_qty=0, net_required_qty=1,
            required_date=self.on_date, supply_type='production', status='confirmed',
            created_by=case.actor)
        other_plan = source_fixture.ProductionPlan.objects.create(
            plan_no='SOURCE-DATE-OTHER-PLAN', planning_requirement=other_requirement,
            material=case.material, planned_qty=1, required_date=self.on_date,
            source_id=str(other_requirement.pk), confirmed_by=case.actor, status='confirmed')
        self.assertNotEqual(other_plan.pk, case.plan.pk)
        with self.read_only():
            readiness, scopes = self.assess()
            bound, output, item, _ = scopes[1]
            row = next(row for row in readiness['steps'] if row['sequence'] == 1)
            demand = process_demand_for_plan(bound, output, item, row,
                company_id=case.company.pk, user=case.actor, require_saved=True)
            self.assertEqual(demand['allocationId'], saved['allocationId'])
            proof = demand['objectCoverageProof']
            self.assertEqual(proof['scope']['mainCalculationId'], case.main.pk)
            self.assertEqual(proof['scope']['baselineId'], case.new_baseline.pk)
            self.assertEqual(proof['scope']['manufacturingOutputId'], case.anchor.pk)
            with self.assertRaises(DailyCapacityError) as cross_plan:
                process_demand_for_plan(other_plan, output, item, row,
                    company_id=case.company.pk, user=case.actor, require_saved=True)
            self.assertEqual(cross_plan.exception.code, 'PROCESS_DEMAND_PLAN_ALLOCATION_MISSING')
            wrong_output = copy(output)
            wrong_output.pk = output.pk + 100000
            with self.assertRaises(requirements.OperationRequirementError) as wrong_source:
                process_demand_for_plan(bound, wrong_output, item, row,
                    company_id=case.company.pk, user=case.actor, require_saved=True)
            self.assertEqual(wrong_source.exception.code, 'ALLOCATION_SOURCE_MISMATCH')
            result = production_plan_date_preview(case.plan, start_date=self.on_date,
                company_id=case.company.pk, user=case.actor)
            self.assertFalse(result['previewReady'])
            self.assertEqual(result['dates'], [])
            self.assertTrue(any(row['stepId'] == self.ordinary_step.pk
                and row['code'] == 'PROCESS_DEMAND_PLAN_ALLOCATION_MISSING'
                for row in result['processDemandBlockers']))
            actual = next(row for row in result['processDemandFacts']
                if row['stepId'] == case.step.pk)
            self.assertEqual(actual['allocationId'], saved['allocationId'])
            self.assertEqual(actual['objectCoverageProof']['scope']['mainCalculationId'], case.main.pk)
            for key in ('businessWriteCount', 'productionScheduleCreatedCount', 'mrpRunCount'):
                self.assertEqual(result[key], 0)

    def test_direct_whole_route_readiness_still_refuses_mixed_sources(self):
        case = self.case
        with self.read_only(), self.assertRaises(DailyCapacityError) as caught:
            DailyCapacityReadinessService.assess(case.anchor.routing_version,
                production_plan=case.plan, manufacturing_output=case.anchor,
                user=case.actor, on_date=self.on_date)
        self.assertEqual(caught.exception.code, 'PLAN_MIXED_VERSION_DATE_SCOPE_REQUIRED')

    def test_revoked_binding_cannot_fall_back_to_original_source(self):
        # Deliberate isolated corruption precedes the read-only boundary.
        binding = PlanStepVersionBinding.objects.get(pk=self.binding_id)
        audit = source_fixture.OrganizationOperatingAuditRecord.objects.get(pk=binding.audit_record_id)
        self.corrupt_isolated_fixture(type(audit), audit.pk, 'action_code', 'isolated.wrong.binding.action')
        with self.read_only(), self.assertRaises(DailyCapacityError) as unproven:
            self.assess()
        self.assertEqual(unproven.exception.code, 'STEP_VERSION_BINDING_UNPROVEN')
        self.corrupt_isolated_fixture(type(audit), audit.pk, 'action_code', audit.action_code)
        self.corrupt_isolated_fixture(PlanStepVersionBinding, self.binding_id, 'status', 'revoked')
        with self.read_only(), self.assertRaises(DailyCapacityError) as caught:
            self.assess()
        self.assertEqual(caught.exception.code, 'STEP_VERSION_NOT_ACTIVE')

    def test_unbound_plan_keeps_complete_original_readiness(self):
        case = self.case
        self.assertFalse(PlanStepVersionBinding.objects.filter(production_plan_id=case.plan.pk).exists())
        with self.read_only():
            actual, contexts = DailyCapacityReadinessService.assess_plan_date_scope(
                case.plan, company_id=case.company.pk, on_date=self.on_date, user=case.actor)
            # Same fixed-output arguments as the established unbound date
            # path, which did not pass user to the old whole-route assess.
            output = case.anchor
            expected = DailyCapacityReadinessService.assess(output.routing_version,
                bom_version=output.bom_version, engineering_calculation=output.engineering_calculation,
                engineering_document_version=output.engineering_document_version,
                order_engineering_instance=output.order_engineering_instance,
                order_engineering_baseline=output.order_engineering_baseline,
                production_plan=case.plan, manufacturing_output=output, on_date=self.on_date)
            self.assertEqual(contexts, {})
            self.assert_exact_tree(actual, expected)

    def test_missing_or_foreign_actor_cannot_resolve_mixed_date_sources(self):
        foreign = copy(self.case.actor)
        foreign.company_id = self.case.company.pk + 100000
        for actor in (None, foreign):
            with self.subTest(actor='missing' if actor is None else 'foreign'):
                with self.read_only(), self.assertRaises(DailyCapacityError) as caught:
                    DailyCapacityReadinessService.assess_plan_date_scope(
                        self.case.plan, company_id=self.case.company.pk,
                        on_date=self.on_date, user=actor)
                self.assertEqual(caught.exception.code, 'PLAN_MIXED_VERSION_DATE_SCOPE_REQUIRED')
