"""SIMULATED_FOR_TEST: native correction partitions in shared consumers.

Only the parent runner's disposable database may execute these tests. Setup
uses the real source/plan/decision/correction services. Read phases deny all
business writers and all duration/calendar calculations; no formal date or
whole-route production evaluation is performed by this test module.
"""
from contextlib import ExitStack
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord

from . import daily_capacity_service as capacity
from . import daily_capacity_views as date_consumer
from . import operation_requirement_service as operation
from . import routing_object_applicability_service as original
from . import routing_object_applicability_correction_service as correction
from . import tests_calc4_routing_correction as source_fixtures
from . import tests_no_date_allocated_capacity as saved_fixtures
from . import tests_routing_object_applicability_correction_service as correction_fixtures
from .engineering_fact_extension_service import EngineeringFactExtensionService
from .models import (
    EngineeringDerivedFact, EngineeringOperationRequirement, EngineeringRuleDefinition,
    ProductionPlanOperationRequirementAllocation, Routing, RoutingStep, RoutingVersion,
    RoutingStepObjectApplicability, RoutingStepObjectApplicabilityCorrection,
)
from .routing_step_applicability_service import RoutingStepApplicabilityResolver


REASON = 'SIMULATED_FOR_TEST correction consumer'


class RoutingObjectCorrectionConsumerTests(TestCase):
    def setUp(self):
        original_advance = source_fixtures.Calc4RoutingCorrectionTests.advance

        def add_sibling_before_review(fixture, obj, target, *, status_field='status'):
            # Add this fixture-only neighbor while the route is still draft.
            # No released step, source hash or proof is repaired to make tests
            # pass. The original factory then publishes the complete route.
            if isinstance(obj, RoutingVersion) and obj.routing_version == 'SIM-V1' and target == 'reviewed':
                first = RoutingStep.objects.get(routing_version=obj, sequence=1)
                RoutingStep.objects.create(routing_version=obj, sequence=2,
                    operation=first.operation, predecessor_sequences=[1],
                    operation_parameters=deepcopy(first.operation_parameters))
            return original_advance(fixture, obj, target, status_field=status_field)

        self.saved_fixture = saved_fixtures.NoDateAllocatedCapacityPersistenceTests(methodName='runTest')
        with patch.object(source_fixtures.Calc4RoutingCorrectionTests, 'advance', add_sibling_before_review):
            self.saved_fixture.setUp()
        self.f, self.plan = self.saved_fixture.f, self.saved_fixture.plan
        self.fixture = correction_fixtures.make_correction_fixture(f=self.f, plan=self.plan)
        self.roots = list(RoutingStepObjectApplicability.objects.filter(
            production_plan=self.plan, routing_step=self.f.step).order_by('baseline_item_id'))
        self.assertEqual(len(self.roots), 3)
        self.sibling = RoutingStep.objects.get(routing_version=self.f.version, sequence=2)
        sibling_contributions = []
        for item in self.fixture.contributions:
            context = original.build_context(self.plan.pk, self.sibling.pk, item['baselineItemId'])
            sibling_contributions.append({**deepcopy(item), 'contextHash': context['contextHash'],
                'idempotencyKey': context['suggestedIdempotencyKey'], 'decision': original.NOT_APPLICABLE})
        original.confirm_group(self.f.user, self.plan.pk, self.sibling.pk, sibling_contributions, REASON)
        self.sibling_before = self.resolve_step(self.sibling)
        self.old_support_ids = {model: list(model.objects.values_list('pk', flat=True)) for model in (
            ExternalIdentity, MasterDataWriteRequest, OrganizationOperatingAuditRecord)}
        self.protected_before = self.protected_snapshot()

    def protected_snapshot(self):
        result = {model._meta.label: list(model.objects.order_by('pk').values()) for model in (
            Routing, RoutingVersion, RoutingStep, RoutingStepObjectApplicability,
            EngineeringDerivedFact, EngineeringOperationRequirement, EngineeringRuleDefinition,
            ProductionPlanOperationRequirementAllocation,
        )}
        for model, ids in self.old_support_ids.items():
            result[model._meta.label] = list(model.objects.filter(pk__in=ids).order_by('pk').values())
        return result

    def read_snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values()) for model in (
            RoutingStepObjectApplicability, RoutingStepObjectApplicabilityCorrection,
            EngineeringDerivedFact, EngineeringOperationRequirement,
            ProductionPlanOperationRequirementAllocation, ExternalIdentity,
            MasterDataWriteRequest, OrganizationOperatingAuditRecord,
        )}

    def context_kwargs(self):
        return {'production_plan': self.plan, 'manufacturing_output': self.f.output,
            'engineering_calculation': self.f.source_calc,
            'engineering_document_version': self.f.output.engineering_document_version,
            'order_engineering_instance': self.f.instance,
            'order_engineering_baseline': self.f.baseline, 'bom_version': self.f.bom_version}

    def resolve_step(self, step):
        return RoutingStepApplicabilityResolver.resolve(step, **self.context_kwargs())

    def guarded_read(self, action):
        before = self.read_snapshot()
        forbidden_write = AssertionError('read consumer must not call a business writer')
        forbidden_calculation = AssertionError('partition/demand gate test must not calculate duration or calendar')
        with ExitStack() as stack:
            for owner, name in ((operation.OperationRequirementService, 'generate'),
                    (operation.OperationRequirementService, 'allocate'),
                    (operation.OperationRequirementService, 'allocate_group'),
                    (EngineeringFactExtensionService, 'configure'), (EngineeringFactExtensionService, 'derive'),
                    (original, 'confirm_group'), (correction, 'correct_group')):
                stack.enter_context(patch.object(owner, name, side_effect=forbidden_write))
            for owner in (capacity, date_consumer):
                for name in ('_allocated_capacity_duration', 'duration_days', 'working_date_window'):
                    stack.enter_context(patch.object(owner, name, side_effect=forbidden_calculation))
            with CaptureQueriesContext(connection) as queries:
                result = action()
        writes = [row['sql'] for row in queries if row['sql'].lstrip().split()[0].upper()
            in {'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'}]
        self.assertEqual(writes, [])
        self.assertFalse(any('password' in row['sql'].lower() for row in queries))
        self.assertEqual(self.read_snapshot(), before)
        if 'businessWriteCount' in result:
            self.assertEqual(result['businessWriteCount'], 0)
        return result

    def read_both(self):
        no_date = self.guarded_read(lambda: capacity.AllocatedLoadCapacityReadinessService.assess(
            user=self.f.user, production_plan_id=self.plan.pk, on_date=date.today()))
        # This disposable-DB consumer entry must return at the demand or
        # applicability gate. The guards above reject any date calculation.
        date_result = self.guarded_read(lambda: date_consumer.production_plan_date_preview(
            self.plan, start_date=date.today(), company_id=self.f.company.pk))
        self.assertFalse(date_result['previewReady'])
        self.assertEqual(date_result['dates'], [])
        return no_date, date_result

    def target_rows(self, no_date, date_result):
        return (next(row for row in no_date['steps'] if row['stepId'] == self.f.step.pk),
            next(row for row in date_result['readiness']['steps'] if row['stepId'] == self.f.step.pk))

    def correct(self, *, first_only=False):
        items = correction_fixtures.build_correction_contributions(self.fixture)
        if first_only:
            items = items[:1]
        return correction.correct_group(self.f.user, self.plan.pk, self.f.step.pk, items, REASON)

    def assert_missing_saved_gate(self, no_date, date_result):
        no_date_row, date_row = self.target_rows(no_date, date_result)
        self.assertEqual(no_date_row['applicability'], date_row['applicability'])
        self.assertEqual(no_date_row['applicability']['result'], original.REQUIRED)
        self.assertEqual(no_date_row['statusCode'], 'LOAD_UNPROVEN')
        self.assertIsNone(no_date_row['processDemand'])
        self.assertEqual(no_date_row['capacityMatches'], [])
        self.assertFalse(no_date_row['noDateMatchPassed'])
        self.assertIn('PROCESS_DEMAND_PLAN_ALLOCATION_MISSING', {
            row['code'] for row in no_date['processDemandBlockers'] if row['stepId'] == self.f.step.pk})
        self.assertTrue(any(row['stepId'] == self.f.step.pk for row in date_result['processDemandBlockers']))
        self.assertFalse(no_date['noDateReady'])

    def test_no_correction_keeps_the_full_v1_payload_and_native_consumers_equal(self):
        scope = original._load_scope(self.plan.pk, self.f.step.pk)
        by_object = {row.baseline_item_id: row for row in self.roots}
        expected_objects = []
        for obj in scope['objects']:
            row = by_object[obj.pk]
            expected_objects.append({**original._committed_proof(row, scope),
                'basis': deepcopy(row.basis), 'reason': row.reason})
        expected = {'contractVersion': original.CONTRACT_VERSION, 'factSource': 'server',
            'scope': {'productionPlanId': self.plan.pk, 'manufacturingOutputId': self.f.output.pk,
                'baselineId': self.f.baseline.pk}, 'result': original.NOT_APPLICABLE, 'complete': True,
            'fullBaselineItemIds': sorted(row.baseline_item_id for row in self.roots),
            'fullDesignItemIds': sorted(row.design_item_id for row in self.roots),
            'requiredBaselineItemIds': [], 'requiredDesignItemIds': [],
            'excludedBaselineItemIds': sorted(row.baseline_item_id for row in self.roots),
            'excludedDesignItemIds': sorted(row.design_item_id for row in self.roots),
            'unknownBaselineItemIds': [], 'unknownDesignItemIds': [],
            'objects': expected_objects, 'reasons': []}
        actual = self.guarded_read(lambda: self.resolve_step(self.f.step))
        self.assertEqual(actual['objectApplicability'], expected)
        self.assertEqual(RoutingStepObjectApplicabilityCorrection.objects.count(), 0)
        no_date, date_result = self.read_both()
        for row in self.target_rows(no_date, date_result):
            self.assertEqual(row['applicability'], actual)
        self.assertEqual(no_date['processDemandBlockers'], [])
        self.assertEqual(date_result['processDemandBlockers'], [])
        self.assertEqual(self.protected_snapshot(), self.protected_before)

    def test_real_three_object_correction_reaches_both_required_demand_gates_without_zero_or_duration(self):
        committed = self.correct()
        self.assertEqual(committed['createdCount'], 3)
        no_date, date_result = self.read_both()
        self.assert_missing_saved_gate(no_date, date_result)
        proof = self.target_rows(no_date, date_result)[0]['applicability']['objectApplicability']
        self.assertTrue(proof['complete'])
        self.assertEqual(proof['requiredBaselineItemIds'], sorted(row.baseline_item_id for row in self.roots))
        self.assertEqual(proof['excludedBaselineItemIds'], [])
        self.assertEqual(proof['unknownBaselineItemIds'], [])
        roots_by_object = {row.baseline_item_id: row for row in self.roots}
        original_audits = {item['rootRecordProof']['auditId'] for item in proof['objects']}
        correction_audits = {item['currentCorrectionProof']['auditId'] for item in proof['objects']}
        self.assertTrue(original_audits.isdisjoint(correction_audits))
        for item in proof['objects']:
            root = roots_by_object[item['baselineItemId']]
            self.assertEqual(item['effectiveDecision'], original.REQUIRED)
            self.assertEqual(item['rootRecordProof']['recordId'], root.pk)
            self.assertEqual(item['rootRecordProof']['decision'], original.NOT_APPLICABLE)
            self.assertEqual(item['currentCorrectionProof']['rootRecordId'], root.pk)
            self.assertEqual(item['currentCorrectionProof']['decision'], original.REQUIRED)
            self.assertEqual(item['currentCorrectionProof']['recordType'], 'RoutingStepObjectApplicabilityCorrection')
        self.assertEqual(self.protected_snapshot(), self.protected_before)

    def test_target_correction_preserves_other_step_original_exclusions_and_all_old_provenance(self):
        self.correct()
        sibling = self.guarded_read(lambda: self.resolve_step(self.sibling))
        self.assertEqual(sibling, self.sibling_before)
        self.assertEqual(sibling['result'], original.NOT_APPLICABLE)
        self.assertTrue(sibling['objectApplicability']['complete'])
        self.assertEqual(RoutingStepObjectApplicabilityCorrection.objects.filter(
            root_record__routing_step=self.sibling).count(), 0)
        self.assertEqual(self.protected_snapshot(), self.protected_before)

    def test_partial_real_correction_keeps_complete_mixed_scope_and_does_not_skip_the_required_object(self):
        committed = self.correct(first_only=True)
        self.assertEqual(committed['createdCount'], 1)
        corrected_root = RoutingStepObjectApplicabilityCorrection.objects.get().root_record
        no_date, date_result = self.read_both()
        self.assert_missing_saved_gate(no_date, date_result)
        proof = self.target_rows(no_date, date_result)[0]['applicability']['objectApplicability']
        self.assertTrue(proof['complete'])
        self.assertEqual(proof['requiredBaselineItemIds'], [corrected_root.baseline_item_id])
        self.assertEqual(proof['excludedBaselineItemIds'], sorted(
            row.baseline_item_id for row in self.roots if row.pk != corrected_root.pk))
        self.assertEqual(proof['unknownBaselineItemIds'], [])
        self.assertEqual(self.protected_snapshot(), self.protected_before)

    def test_corrupt_current_correction_audit_stays_pending_in_both_consumers_without_old_na_fallback(self):
        committed = self.correct()
        audit = OrganizationOperatingAuditRecord.objects.get(pk=committed['objects'][0]['auditId'])
        damaged = deepcopy(audit.after_snapshot)
        damaged['state']['newDecision'] = original.NOT_APPLICABLE
        # Explicit corruption is restricted to this runner's disposable DB.
        self.saved_fixture.fixture.raw(audit, 'after_snapshot', damaged)
        with patch.object(operation, 'process_demand_for_plan',
                side_effect=AssertionError('pending correction must not read independent demand')), patch.object(
                date_consumer, 'process_demand_for_plan',
                side_effect=AssertionError('pending correction must not read date demand')):
            no_date, date_result = self.read_both()
        no_date_row, date_row = self.target_rows(no_date, date_result)
        self.assertEqual(no_date_row['applicability'], date_row['applicability'])
        self.assertEqual(no_date_row['applicability']['result'], original.PENDING)
        proof = no_date_row['applicability']['objectApplicability']
        self.assertFalse(proof['complete'])
        self.assertEqual(proof['excludedBaselineItemIds'], [])
        self.assertEqual(len(proof['unknownBaselineItemIds']), 1)
        self.assertIn('OBJECT_CORRECTION_AUDIT_MISMATCH', {row['code'] for row in proof['reasons']})
        self.assertIsNone(no_date_row['processDemand'])
        self.assertEqual(no_date_row['capacityMatches'], [])
        self.assertEqual(no_date['matchedAllocationCount'], 0)
        self.assertFalse(no_date['noDateReady'])
        self.assertEqual(self.protected_snapshot(), self.protected_before)
