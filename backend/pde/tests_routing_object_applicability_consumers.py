"""SIMULATED_FOR_TEST: exact object decisions in shared capacity consumers.

The parent runner owns an isolated test database.  Memory tests inspect only
the consumer boundary; persisted-source tests below use the original native
fixtures and never replace the resolver's formal-source proof.
"""
from contextlib import ExitStack
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from . import daily_capacity_service as capacity
from . import daily_capacity_views as date_views
from . import tests_daily_capacity_date_preview as date_fixtures
from . import tests_daily_capacity_source_rules as source_fixtures
from . import tests_no_date_allocated_capacity as saved_fixtures
from . import tests_routing_object_applicability_service as object_fixtures
from . import operation_requirement_service as operation
from . import routing_object_applicability_service as object_service
from .engineering_fact_extension_service import EngineeringFactExtensionService
from .models import (
    EngineeringDerivedFact, EngineeringOperationRequirement,
    ProductionPlanOperationRequirementAllocation, RoutingStepObjectApplicability,
)
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord


def object_payload(*, required=(11,), excluded=(12, 13), unknown=(), complete=True):
    mapping = {11: 21, 12: 22, 13: 23}
    result = 'PENDING' if unknown or not complete else 'REQUIRED' if required else 'NOT_APPLICABLE'
    return {'result': result, 'resultLabel': result,
        'objectApplicability': {
            'scope': {'productionPlanId': 41, 'manufacturingOutputId': 51, 'baselineId': 61},
            'fullDesignItemIds': list(mapping), 'fullBaselineItemIds': list(mapping.values()),
            'requiredDesignItemIds': list(required), 'requiredBaselineItemIds': [mapping[i] for i in required],
            'excludedDesignItemIds': list(excluded), 'excludedBaselineItemIds': [mapping[i] for i in excluded],
            'unknownDesignItemIds': list(unknown), 'unknownBaselineItemIds': [mapping[i] for i in unknown],
            'complete': complete, 'result': result, 'objects': [], 'reasons': [],
        }}


class ObjectApplicabilityConsumerContractTests(SimpleTestCase):
    def setUp(self):
        self.plan = SimpleNamespace(pk=41)
        self.output = SimpleNamespace(pk=51, order_engineering_baseline_id=61)

    def scope(self, applicability):
        return capacity._object_applicability_scope(self.plan, self.output, applicability)

    def test_legacy_without_object_record_keeps_its_original_contract(self):
        self.assertIsNone(self.scope({'result': 'REQUIRED'}))

    def test_complete_mixed_partition_preserves_required_and_excluded_identities(self):
        scope = self.scope(object_payload())
        self.assertEqual(scope['fullDesignItemIds'], {11, 12, 13})
        self.assertEqual(scope['requiredDesignItemIds'], {11})
        self.assertEqual(scope['excludedDesignItemIds'], {12, 13})
        self.assertEqual(scope['requiredBaselineItemIds'], {21})
        self.assertEqual(scope['excludedBaselineItemIds'], {22, 23})

    def test_context_partial_unknown_overlap_or_duplicate_cannot_become_complete(self):
        valid = object_payload()
        variants = []
        for key in ('productionPlanId', 'manufacturingOutputId', 'baselineId'):
            changed = deepcopy(valid)
            changed['objectApplicability']['scope'][key] += 100
            variants.append(changed)
        for key, value in (
                ('complete', False), ('unknownDesignItemIds', [13]),
                ('excludedDesignItemIds', [11, 12, 13]), ('requiredDesignItemIds', []),
                ('fullDesignItemIds', [11, 12, 13, 13]),
                ('excludedBaselineItemIds', [22]), ('requiredBaselineItemIds', [True])):
            changed = deepcopy(valid)
            changed['objectApplicability'][key] = value
            variants.append(changed)
        for changed in variants:
            with self.subTest(proof=changed), self.assertRaises(capacity.DailyCapacityError) as caught:
                self.scope(changed)
            self.assertEqual(caught.exception.code, 'OBJECT_APPLICABILITY_SCOPE_UNPROVEN')

    def test_not_applicable_pending_and_auxiliary_never_read_independent_demand(self):
        reader = MagicMock(side_effect=AssertionError('skipped step must not read EOR or allocation'))
        for state, mode in (('NOT_APPLICABLE', 'NOT_APPLICABLE'),
                ('PENDING', 'APPLICABILITY_PENDING'), ('REQUIRED', capacity.AUXILIARY_DATE_MODE)):
            readiness = {'steps': [{'applicability': {'result': state}, 'capacityDateMode': mode}]}
            self.assertEqual(capacity._read_plan_step_demands(self.plan, self.output, None,
                readiness, company_id=7, demand_reader=reader), ({}, [], []))
        reader.assert_not_called()

    def test_date_entry_forwards_fixed_plan_output_and_all_excluded_creates_no_dates(self):
        plan = date_fixtures.plan_fixture()
        output = plan.planning_requirement.demand.manufacturing_output
        skipped = date_fixtures.step_fixture(10, state='NOT_APPLICABLE')
        readiness = date_fixtures.readiness_fixture(skipped)
        with patch.object(date_views.DailyCapacityReadinessService, 'assess', return_value=readiness) as assess, patch.object(
                date_views, 'process_demand_for_plan', side_effect=AssertionError('excluded demand read')), patch.object(
                date_views, '_allocated_capacity_duration', side_effect=AssertionError('excluded duration')), patch.object(
                date_views, 'working_date_window', side_effect=AssertionError('excluded calendar work')):
            result = date_views.production_plan_date_preview.__wrapped__(
                plan, start_date=date_fixtures.START, company_id=21)
        self.assertIs(assess.call_args.kwargs['production_plan'], plan)
        self.assertIs(assess.call_args.kwargs['manufacturing_output'], output)
        self.assertFalse(result['previewReady'])
        self.assertEqual(result['dates'], [])
        self.assertEqual(result['businessWriteCount'], 0)


class ObjectApplicabilitySourcePriorityTests(SimpleTestCase):
    def assess(self, applicability, *, source_mode):
        kind, operations, centers, _ = source_fixtures.source_fixture()
        operation = operations[2]
        step = SimpleNamespace(pk=71, sequence=1, operation=operation, is_active=True,
            predecessor_sequences=[], work_center=centers[2], preparation_days=None, transfer_days=None)
        steps = MagicMock()
        steps.select_related.return_value = [step]
        route = SimpleNamespace(company_id=7, routing_code='READY/SEMI',
            product_category_id=11, manufacturing_process_type_id=12)
        version = SimpleNamespace(pk=81, routing=route, routing_id=80, routing_version='V1', steps=steps)
        manifest = source_fixtures.source_manifest()
        manifest['nonApplicableOperationIds'] = [2] if source_mode == 'excluded' else []
        manifest['auxiliaryOperationIds'] = [2] if source_mode == 'auxiliary' else []
        source = {'status': 'VALID', 'manifest': manifest, 'fact': {'source': 'SIMULATED_FOR_TEST'}}
        with patch.object(capacity.CapacityProductType.objects, 'filter', return_value=[kind]), patch.object(
                capacity, 'capacity_source_rules', return_value=source), patch(
                'pde.routing_step_applicability_service.RoutingStepApplicabilityResolver.resolve',
                return_value=applicability), patch.object(capacity.StandardCapacity.objects, 'filter',
                side_effect=AssertionError('excluded/pending must not read capacity')):
            return capacity.DailyCapacityReadinessService.assess(version, on_date=source_fixtures.START)

    def test_object_pending_cannot_be_overridden_by_blank_or_auxiliary_source(self):
        for mode in ('excluded', 'auxiliary'):
            with self.subTest(mode=mode):
                row = self.assess(object_payload(required=(11,), excluded=(12,), unknown=(13,), complete=False),
                    source_mode=mode)['steps'][0]
                self.assertEqual(row['applicability']['result'], 'PENDING')
                self.assertEqual(row['capacityDateMode'], 'APPLICABILITY_PENDING')
                self.assertIn('ROUTING_STEP_APPLICABILITY_PENDING', row['blockerCodes'])
                self.assertFalse(row['capacityDemandEvaluated'])

    def test_required_objects_conflicting_with_source_blank_remain_blocked(self):
        row = self.assess(object_payload(), source_mode='excluded')['steps'][0]
        self.assertEqual(row['applicability']['result'], 'PENDING')
        self.assertEqual(row['routingApplicability']['result'], 'REQUIRED')
        self.assertIn('SOURCE_OBJECT_APPLICABILITY_CONFLICT', row['blockerCodes'])
        self.assertEqual(row['dailyCapacity'], [])

    def test_all_excluded_objects_do_not_become_required_from_auxiliary_source(self):
        row = self.assess(object_payload(required=(), excluded=(11, 12, 13)),
            source_mode='auxiliary')['steps'][0]
        self.assertEqual(row['applicability']['result'], 'NOT_APPLICABLE')
        self.assertEqual(row['capacityDateMode'], 'NOT_APPLICABLE')
        self.assertEqual(row['dailyCapacity'], [])
        self.assertFalse(row['capacityDemandEvaluated'])
        self.assertEqual(row['blockerCodes'], [])


class ObjectApplicabilitySavedConsumerTests(TestCase):
    """Real original facts, immutable legal-extension allocations and decisions."""

    def setUp(self):
        # Compose the existing builder; importing/inheriting its TestCase would
        # discover its unrelated regression methods a second time.
        self.saved = saved_fixtures.NoDateAllocatedCapacityPersistenceTests(methodName='runTest')
        self.saved.setUp()
        self.f = self.saved.f
        self.plan = self.saved.plan
        self.object_fixture = object_fixtures.make_object_applicability_fixture(f=self.f, plan=self.plan)

    def decide(self, states):
        contributions = []
        for index, state in enumerate(states):
            if state is None:
                continue
            contribution = deepcopy(self.object_fixture.contributions[index])
            contribution['decision'] = state
            contributions.append(contribution)
        return object_service.confirm_group(self.f.user, self.plan.pk, self.f.step.pk,
            contributions, 'SIMULATED_FOR_TEST object applicability consumer fixture')

    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values()) for model in (
            RoutingStepObjectApplicability, ProductionPlanOperationRequirementAllocation,
            EngineeringDerivedFact, EngineeringOperationRequirement,
            OrganizationOperatingAuditRecord, MasterDataWriteRequest, ExternalIdentity,
        )}

    def read(self, *, date_preview=False):
        before = self.snapshot()
        forbidden = AssertionError('capacity consumer must not call a business writer')
        with ExitStack() as stack:
            for owner, name in ((operation.OperationRequirementService, 'generate'),
                    (operation.OperationRequirementService, 'allocate'),
                    (operation.OperationRequirementService, 'allocate_group'),
                    (EngineeringFactExtensionService, 'derive'),
                    (EngineeringFactExtensionService, 'configure'), (object_service, 'confirm_group')):
                stack.enter_context(patch.object(owner, name, side_effect=forbidden))
            with CaptureQueriesContext(connection) as queries:
                if date_preview:
                    result = date_views.production_plan_date_preview(self.plan,
                        start_date=date_fixtures.START, company_id=self.f.company.pk)
                else:
                    result = capacity.AllocatedLoadCapacityReadinessService.assess(
                        user=self.f.user, production_plan_id=self.plan.pk)
        writes = [row['sql'] for row in queries if row['sql'].lstrip().split()[0].upper()
            in {'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'}]
        self.assertEqual(writes, [])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(result['businessWriteCount'], 0)
        return result

    def target(self, result):
        return next(row for row in result['steps'] if row['stepId'] == self.f.step.pk)

    def test_all_native_exclusions_skip_demand_capacity_duration_and_keep_saved_rows(self):
        self.saved.save_contributions()
        self.decide(['NOT_APPLICABLE'] * 3)
        before_ids = list(ProductionPlanOperationRequirementAllocation.objects.order_by('pk').values_list('pk', flat=True))
        with patch.object(operation, 'process_demand_for_plan',
                side_effect=AssertionError('excluded step must not read demand')), patch.object(
                capacity, '_allocated_capacity_duration', side_effect=AssertionError('excluded step duration')), patch.object(
                capacity, 'working_date_window', side_effect=AssertionError('no-date calendar work')):
            result = self.read()
        row = self.target(result)
        self.assertEqual(row['statusCode'], 'NOT_APPLICABLE')
        self.assertIsNone(row['processDemand'])
        self.assertEqual(row['capacityMatches'], [])
        self.assertEqual(row['applicability']['objectApplicability']['excludedDesignItemIds'],
            sorted(obj.design_item_id for obj in self.f.baseline_items))
        self.assertEqual(list(ProductionPlanOperationRequirementAllocation.objects.order_by('pk')
            .values_list('pk', flat=True)), before_ids)
        self.assertEqual(result['matchedAllocationCount'], 0)
        self.assertNotIn('PROCESS_DEMAND_PLAN_ALLOCATION_MISSING', saved_fixtures.codes(result))

    def test_mixed_native_scope_matches_only_required_saved_object_without_scaling_quantity(self):
        required_object = self.f.baseline_items[0]
        # GROUP_SUM output sequence follows the canonical group hash, not the
        # baseline item order. Select the exact formal object, never list[0].
        matching = [req for req in self.saved.requirements
            if req.source_fact.trace.get('baselineItemId') == required_object.pk
            and req.source_fact.trace.get('designItemId') == required_object.design_item_id]
        self.assertEqual(len(matching), 1)
        required_requirement = matching[0]
        self.saved.save_contributions(matching)
        saved = ProductionPlanOperationRequirementAllocation.objects.get(
            production_plan=self.plan, operation_requirement=required_requirement)
        object_proof = saved.source_snapshot['planEngineeringSource']
        self.assertEqual(object_proof['baselineItemIds'], [required_object.pk])
        self.assertEqual(object_proof['designItemIds'], [required_object.design_item_id])
        self.decide(['REQUIRED', 'NOT_APPLICABLE', 'NOT_APPLICABLE'])
        result = self.read()
        row = self.target(result)
        self.assertEqual(row['applicability']['result'], 'REQUIRED')
        self.assertTrue(row['noDateMatchPassed'], row)
        self.assertTrue(row['objectCoverage']['complete'])
        self.assertEqual(row['objectCoverage']['expectedDesignItemIds'], [self.f.baseline_items[0].design_item_id])
        self.assertEqual(row['objectCoverage']['excludedDesignItemIds'],
            sorted(obj.design_item_id for obj in self.f.baseline_items[1:]))
        self.assertEqual(Decimal(row['processDemand']['quantity']), required_requirement.workload_quantity)
        self.assertEqual(result['matchedAllocationCount'], 1)
        self.assertEqual(len(row['processDemand']['savedContributions']), 1)
        self.assertEqual(Decimal(row['capacityMatches'][0]['preparationDays']), Decimal('.1'))
        self.assertEqual(Decimal(row['capacityMatches'][0]['transferDays']), Decimal('.1'))

    def test_mixed_scope_never_filters_saved_excluded_objects_or_their_load(self):
        self.saved.save_contributions()
        self.decide(['REQUIRED', 'NOT_APPLICABLE', 'NOT_APPLICABLE'])
        with patch.object(capacity, '_allocated_capacity_duration',
                side_effect=AssertionError('unproved object scope must not calculate duration')):
            result = self.read()
        row = self.target(result)
        self.assertFalse(row['noDateMatchPassed'])
        self.assertIsNone(row['processDemand'])
        self.assertEqual(result['matchedAllocationCount'], 0)
        self.assertEqual(len(result['allocationRead']['allocations']), 3)
        self.assertIn('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN', saved_fixtures.codes(result))

    def test_partial_native_object_decision_remains_pending_and_does_not_query_step_demand(self):
        self.decide(['NOT_APPLICABLE', None, None])
        with patch.object(operation, 'process_demand_for_plan', side_effect=AssertionError('unknown scope demand')):
            result = self.read()
        row = self.target(result)
        self.assertEqual(row['statusCode'], 'PENDING')
        proof = row['applicability']['objectApplicability']
        self.assertFalse(proof['complete'])
        self.assertEqual(proof['unknownDesignItemIds'], sorted(obj.design_item_id for obj in self.f.baseline_items[1:]))
        self.assertFalse(result['allRequiredStepsCovered'])
        self.assertFalse(result['noDateReady'])

    def test_no_records_keeps_the_original_capacity_readback_equal_with_optional_context(self):
        f = self.f
        kwargs = {'bom_version': f.output.bom_version, 'engineering_calculation': f.output.engineering_calculation,
            'engineering_document_version': f.output.engineering_document_version,
            'order_engineering_instance': f.output.order_engineering_instance,
            'order_engineering_baseline': f.output.order_engineering_baseline}
        original = capacity.DailyCapacityReadinessService.assess(f.output.routing_version, **kwargs)
        scoped = capacity.DailyCapacityReadinessService.assess(f.output.routing_version,
            production_plan=self.plan, manufacturing_output=f.output, **kwargs)
        self.assertEqual(scoped, original)
        self.assertNotIn('objectApplicability', scoped['steps'][0]['applicability'])

    def test_date_entry_uses_native_all_exclusions_without_demand_duration_or_calendar(self):
        self.decide(['NOT_APPLICABLE'] * 3)
        with patch.object(date_views, 'process_demand_for_plan', side_effect=AssertionError('excluded demand')), patch.object(
                date_views, '_allocated_capacity_duration', side_effect=AssertionError('excluded duration')), patch.object(
                date_views, 'working_date_window', side_effect=AssertionError('excluded calendar')):
            result = self.read(date_preview=True)
        self.assertEqual(result['readiness']['steps'][0]['applicability']['result'], 'NOT_APPLICABLE')
        self.assertEqual(result['dates'], [])
        self.assertFalse(result['previewReady'])

    def test_date_entry_rejects_saved_excluded_objects_before_calendar_work(self):
        self.saved.save_contributions()
        self.decide(['REQUIRED', 'NOT_APPLICABLE', 'NOT_APPLICABLE'])
        with patch.object(date_views, '_allocated_capacity_duration', side_effect=AssertionError('scope mismatch duration')), patch.object(
                date_views, 'working_date_window', side_effect=AssertionError('scope mismatch calendar')):
            result = self.read(date_preview=True)
        self.assertFalse(result['previewReady'])
        self.assertEqual(result['dates'], [])
        self.assertIn('OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN', saved_fixtures.codes(result))

    def test_fixed_output_mismatch_stays_pending_in_shared_capacity_service(self):
        self.decide(['NOT_APPLICABLE'] * 3)
        result = capacity.DailyCapacityReadinessService.assess(self.f.version,
            production_plan=self.plan, manufacturing_output=SimpleNamespace(pk=self.f.output.pk + 10000))
        row = result['steps'][0]
        self.assertEqual(row['applicability']['result'], 'PENDING')
        self.assertIn('ROUTING_STEP_APPLICABILITY_PENDING', row['blockerCodes'])
        self.assertFalse(row['capacityDemandEvaluated'])
