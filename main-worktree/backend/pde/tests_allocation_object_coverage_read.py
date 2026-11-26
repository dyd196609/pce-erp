"""SIMULATED_FOR_TEST: current native coverage reads, never production data.

Existing native fixture services create saved inputs in an explicitly named
isolated database. The tested behavior is read proof and consumer binding;
capacity assessments, duration, date windows and full-route entry points are
forbidden by the runner. No successful proof or authorization is mocked.
"""
from copy import deepcopy
from decimal import Decimal
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from system.models import Company, Permission, RolePermission, User
from . import daily_capacity_service as daily
from . import operation_requirement_service as operation
from . import tests_calc4_routing_correction as correction
from . import tests_classified_fact_eor as classified
from . import tests_plan_legal_extension_admission as legal
from .models import (EngineeringCalculationRecord, EngineeringOperationRequirement,
    ProductionPlanOperationRequirementAllocation)


if os.environ.get('PCE_COVERAGE_ISOLATED_TESTS') != '1':
    raise RuntimeError('Coverage read tests require the reviewed named isolated runner')
allowed = {Path(os.environ[key]).resolve() for key in ('PCE_DATABASE_PATH', 'PCE_ISOLATED_TEST_DATABASE')}
if Path(settings.DATABASES['default']['NAME']).resolve() not in allowed:
    raise RuntimeError('Coverage read test database is outside its explicit two-file allowlist')


class AllocationObjectCoverageReadTests(TestCase):
    def setUp(self):
        missing_pair = self._testMethodName == 'test_missing_direct_object_relation_stays_unproven_without_guessing'

        class Fixture(correction.Calc4RoutingCorrectionTests):
            def advance(self, obj, target, *, status_field='status'):
                if isinstance(obj, EngineeringCalculationRecord) and obj.scope == 'order_engineering' and target == 'completed':
                    classified.ClassifiedFactEorTests.finish_source_hashes(self, obj,
                        list(obj.derived_facts.order_by('sequence')))
                return super().advance(obj, target, status_field=status_field)

            def make_fact(self, value, sequence):
                fact = super().make_fact(value, sequence)
                if missing_pair and sequence == 1:
                    # Construct a legacy source without a recorded object pair
                    # before its calculation is completed or any EOR is saved.
                    trace = deepcopy(fact.trace)
                    trace.pop('designItemId')
                    trace.pop('baselineItemId')
                    self.corrupt_json(fact, 'trace', trace)
                    fact.refresh_from_db()
                return fact

        self.f = Fixture(methodName='runTest')
        self.f.setUp()
        permission, _ = Permission.objects.get_or_create(code=operation.PLAN_VIEW,
            defaults={'name': operation.PLAN_VIEW, 'module': 'PRODUCTION'})
        RolePermission.objects.get_or_create(role=self.f.role, permission=permission)
        self.plan = legal.PlanLegalExtensionAdmissionTests.make_plan(SimpleNamespace(f=self.f))
        # Change generation order independently of source sequence and quantity.
        self.requirements = []
        for index in (2, 0, 1):
            saved = self.f.generate(fact=self.f.facts[index], key=f'sim-read-direct-{index}')
            self.requirements.append(EngineeringOperationRequirement.objects.get(pk=saved['operationRequirementId']))
        self.by_fact = {req.source_fact_id: req for req in self.requirements}
        self.step = {'stepId': self.f.step.pk, 'operationId': self.f.op_area.pk}

    def allocate(self, indices=(2, 0, 1)):
        requirements = [self.by_fact[self.f.facts[index].pk] for index in indices]
        return operation.OperationRequirementService.allocate_group(user=self.f.user,
            production_plan_id=self.plan.pk, contributions=[{
                'operationRequirementId': req.pk, 'routingStepId': self.f.step.pk,
                'idempotencyKey': f'sim-coverage-direct-{req.pk}'} for req in requirements],
            reason='SIMULATED_FOR_TEST current read coverage')

    def demand(self, *, user=None):
        return operation.process_demand_for_plan(self.plan, self.f.output, self.f.item,
            self.step, company_id=self.f.company.pk, user=user or self.f.user)

    def consume(self, value, *, plan=None, output=None, company_id=None, step=None):
        return daily._validated_demand_object_coverage(plan or self.plan, output or self.f.output,
            self.f.item, step or self.step, value,
            company_id=company_id if company_id is not None else self.f.company.pk)

    def reject_coverage(self, value, **kwargs):
        with self.assertRaises(daily.DailyCapacityError) as caught:
            self.consume(value, **kwargs)
        self.assertEqual(caught.exception.code, 'OBJECT_COVERAGE_INCOMPLETE_OR_UNPROVEN')

    def test_direct_single_current_read_proves_objects_and_preserves_scalar_snapshot_and_five_surfaces(self):
        saved = self.allocate((1,))
        allocation = ProductionPlanOperationRequirementAllocation.objects.get(pk=saved['allocations'][0]['allocationId'])
        before = deepcopy(allocation.source_snapshot), allocation.input_hash
        self.assertNotIn('planEngineeringSource', before[0])
        with CaptureQueriesContext(connection) as queries:
            value = self.demand()
            read = operation.OperationRequirementService.read(user=self.f.user, production_plan_id=self.plan.pk)
            found = self.consume(value)
        self.assertFalse(any(item['sql'].lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE', 'REPLACE'}
            for item in queries.captured_queries))
        self.assertEqual(value['allocationId'], allocation.pk)
        self.assertEqual(value['quantity'], Decimal('0.5'))
        self.assertEqual(len(value['contributions']), 1)
        proof = value['objectCoverageProof']
        self.assertEqual(proof['status'], 'PROVEN')
        self.assertFalse(proof['snapshotHasPlanEngineeringSource'])
        self.assertEqual(proof['proofSource'], 'CURRENT_READ_VALIDATED_SOURCE_CHAIN')
        self.assertEqual(proof['scope']['mainCalculationId'], self.f.source_calc.pk)
        self.assertEqual(found['designItemIds'], {self.f.baseline_items[1].design_item_id})
        self.assertEqual(found['baselineItemIds'], {self.f.baseline_items[1].pk})
        self.assertEqual(found['inputFactIds'], {self.f.facts[1].pk})
        self.assertTrue(read['passed'], read)
        self.assertEqual(read['allocations'][0]['objectCoverageProof'], proof)
        for name in ('apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts'):
            self.assertEqual(read[name]['allocations'], read['allocations'])
        allocation.refresh_from_db()
        self.assertEqual((allocation.source_snapshot, allocation.input_hash), before)

    def test_direct_multi_different_quantities_and_reordered_contributions_bind_by_identity(self):
        self.allocate()
        demand = self.demand()
        self.assertEqual(demand['quantity'], Decimal('4'))
        self.assertEqual({Decimal(row['quantity']) for row in demand['contributions']},
            {Decimal('1.5'), Decimal('0.5'), Decimal('2')})
        demand['contributions'].reverse()
        found = self.consume(demand)
        self.assertEqual(found['designItemIds'], {row.design_item_id for row in self.f.baseline_items})
        self.assertEqual(found['baselineItemIds'], {row.pk for row in self.f.baseline_items})
        self.assertEqual(found['inputFactIds'], {row.pk for row in self.f.facts})
        self.assertNotEqual(self.f.step.pk, 803)
        for contribution in demand['contributions']:
            proof = contribution['objectCoverageProof']
            item = next(row for row in self.f.baseline_items if row.pk in proof['coverage']['baselineItemIds'])
            fact = next(row for row in self.f.facts if row.pk == proof['sourceFactId'])
            self.assertEqual(item.design_item_id, fact.trace['designItemId'])
        swapped = deepcopy(demand)
        swapped['contributions'][0]['objectCoverageProof'], swapped['contributions'][1]['objectCoverageProof'] = (
            swapped['contributions'][1]['objectCoverageProof'], swapped['contributions'][0]['objectCoverageProof'])
        self.reject_coverage(swapped)

    def test_missing_direct_object_relation_stays_unproven_without_guessing(self):
        self.allocate((0,))
        demand = self.demand()
        self.assertEqual(demand['quantity'], Decimal('1.5'))
        self.assertEqual(demand['objectCoverageProof']['status'], 'UNPROVEN')
        self.assertIsNone(demand['objectCoverageProof']['coverage'])
        self.assertNotIn('planEngineeringSource', demand['contributions'][0]['sourceSnapshot'])
        self.reject_coverage(demand)

    def test_saved_requirement_hash_drift_still_rejects_native_read(self):
        self.allocate((0,))
        req = self.by_fact[self.f.facts[0].pk]
        legal.PlanLegalExtensionAdmissionTests.raw(self, req, 'source_hash', '0' * 64)
        with self.assertRaises(operation.OperationRequirementError):
            self.demand()
        value = operation.OperationRequirementService.read(user=self.f.user, production_plan_id=self.plan.pk)
        self.assertFalse(value['passed'])
        self.assertTrue(value['blockers'])

    def test_explicit_conflicting_saved_declaration_cannot_fall_back_to_direct(self):
        saved = self.allocate((0,))
        row = ProductionPlanOperationRequirementAllocation.objects.get(pk=saved['allocations'][0]['allocationId'])
        snapshot = deepcopy(row.source_snapshot)
        snapshot['planEngineeringSource'] = {'sourceType': 'DIRECT', 'designItemIds': []}
        legal.PlanLegalExtensionAdmissionTests.raw(self, row, 'source_snapshot', snapshot)
        with self.assertRaises(operation.OperationRequirementError) as caught:
            self.demand()
        self.assertEqual(caught.exception.code, 'ALLOCATION_FACT_CHANGED')

    def test_consumer_rejects_scope_hash_and_identity_changes_including_boolean_ids(self):
        self.allocate((0,))
        original = self.demand()
        modifications = []
        proof = original['contributions'][0]['objectCoverageProof']
        for name in proof['scope']:
            modifications.append(('scope-' + name, ('scope', name), proof['scope'][name] + 999))
            modifications.append(('scope-bool-' + name, ('scope', name), True))
        for name in ('allocationId', 'operationRequirementId', 'sourceFactId', 'sourceCalculationId'):
            modifications.append(('identity-' + name, (name,), proof[name] + 999))
            modifications.append(('identity-bool-' + name, (name,), True))
        for name in ('sourceHash', 'inputHash', 'operationRequirementInputHash', 'generationKey'):
            modifications.append(('hash-' + name, (name,), '0' * 64))
        for label, path, value in modifications:
            with self.subTest(label=label):
                changed = deepcopy(original)
                target = changed['contributions'][0]['objectCoverageProof']
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.reject_coverage(changed)
        for key, value in (('allocationId', True), ('allocationId', None), ('allocationIds', [True]),
                ('allocationIds', []), ('allocationIds', [original['allocationId'], original['allocationId']])):
            with self.subTest(demandIdentity=key, value=value):
                changed = deepcopy(original)
                changed[key] = value
                self.reject_coverage(changed)

    def test_consumer_rejects_missing_proof_baseline_pairs_hashes_and_overlap(self):
        self.allocate()
        original = self.demand()
        edits = (
            ('missing', lambda row: row.pop('objectCoverageProof')),
            ('unproven', lambda row: row['objectCoverageProof'].update(status='UNPROVEN')),
            ('baselineHash', lambda row: row['objectCoverageProof']['coverage'].update(baselineSnapshotHash='0' * 64)),
            ('selectedHash', lambda row: row['objectCoverageProof']['coverage'].update(selectedItemHash='0' * 64)),
            ('baselineBool', lambda row: row['objectCoverageProof']['coverage'].update(baselineId=True)),
            ('objectPair', lambda row: row['objectCoverageProof']['coverage'].update(designItemIds=[999999])),
            ('inputMissing', lambda row: row['objectCoverageProof']['coverage'].update(inputFactIds=[])),
            ('inputUnrelated', lambda row: row['objectCoverageProof']['coverage'].update(inputFactIds=[999999])),
        )
        for label, edit in edits:
            with self.subTest(label=label):
                changed = deepcopy(original)
                edit(changed['contributions'][0])
                self.reject_coverage(changed)
        overlap = deepcopy(original)
        left = overlap['contributions'][0]['objectCoverageProof']['coverage']
        right = overlap['contributions'][1]['objectCoverageProof']['coverage']
        right.update(designItemIds=left['designItemIds'], baselineItemIds=left['baselineItemIds'])
        self.reject_coverage(overlap)

    def test_current_permission_company_plan_and_version_scope_are_not_reused(self):
        self.allocate((0,))
        demand = self.demand()
        outsider = User.objects.create_user(username='sim-coverage-no-permission', company_id=self.f.company.pk)
        with self.assertRaises(operation.OperationRequirementError):
            operation.OperationRequirementService.read(user=outsider, production_plan_id=self.plan.pk)
        foreign = Company.objects.create(code='SIM-COVERAGE-FOREIGN', name='SIMULATED_FOR_TEST foreign')
        self.reject_coverage(demand, company_id=foreign.pk)
        self.reject_coverage(demand, plan=SimpleNamespace(pk=self.plan.pk + 10000))
        changed_output = deepcopy(self.f.output)
        changed_output.routing_version = self.f.wrong_version
        self.reject_coverage(demand, output=changed_output)
        self.reject_coverage(demand, step={'stepId': self.f.wrong_step.pk, 'operationId': self.f.op_area.pk})
        self.f.assignment.active = False
        self.f.assignment.save(update_fields=('active',))
        with self.assertRaises(operation.OperationRequirementError):
            operation.OperationRequirementService.read(user=self.f.user, production_plan_id=self.plan.pk)


class LegalExtensionCoverageReadTests(TestCase):
    def test_existing_legal_extension_native_proofs_and_saved_snapshots_are_preserved(self):
        fixture = legal.PlanLegalExtensionAdmissionTests(methodName='runTest')
        fixture.setUp()
        f = fixture.f
        saved = operation.OperationRequirementService.allocate_group(user=f.user,
            production_plan_id=fixture.plan.pk, contributions=[{
                'operationRequirementId': req.pk, 'routingStepId': f.step.pk,
                'idempotencyKey': f'sim-coverage-extension-{req.pk}'} for req in fixture.requirements],
            reason='SIMULATED_FOR_TEST legal extension read')
        rows = list(ProductionPlanOperationRequirementAllocation.objects.order_by('pk'))
        old = {row.pk: (deepcopy(row.source_snapshot), row.input_hash) for row in rows}
        self.assertEqual(saved['businessWriteCount'], 3)
        step = {'stepId': f.step.pk, 'operationId': f.op_area.pk}
        demand = operation.process_demand_for_plan(fixture.plan, f.output, f.item, step,
            company_id=f.company.pk, user=f.user)
        found = daily._validated_demand_object_coverage(fixture.plan, f.output, f.item, step,
            demand, company_id=f.company.pk)
        self.assertEqual(found['designItemIds'], {item.design_item_id for item in f.baseline_items})
        self.assertEqual(demand['quantity'], Decimal('4'))
        for row in rows:
            row.refresh_from_db()
            self.assertEqual((row.source_snapshot, row.input_hash), old[row.pk])
            proof = next(item['objectCoverageProof'] for item in demand['contributions']
                if item['allocationId'] == row.pk)
            self.assertEqual(proof['status'], 'PROVEN')
            self.assertTrue(proof['snapshotHasPlanEngineeringSource'])
            for key, value in proof['coverage'].items():
                self.assertEqual(row.source_snapshot['planEngineeringSource'][key], value)
