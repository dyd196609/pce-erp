"""SIMULATED_FOR_TEST: native plan-step reads, proof reuse and fresh validation.

Run only through the reviewed, named disposable SQLite runner which denies the
formal database before importing Django. Existing native writers construct the
fixture only; every measured read section forbids writers, evaluation and DML.
No successful permission, source, preparation or requirement proof is mocked.
This module composes fixture helpers and does not inherit their test suites.
"""

from contextlib import ExitStack
from decimal import Decimal
import json
import re
from time import perf_counter_ns
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from system.models import Company, RolePermission, User, UserRoleScopeAssignment
from . import operation_input_preparation_service as preparation
from . import operation_non_quantified_context as nonquantified
from . import operation_requirement_service as native
from . import operation_workload_source_service as workload
from . import tests_nonquantified_manufacturing_source as fixtures
from .models import EngineeringFactInput, EngineeringOperationRequirement, OperationInputPreparationDraft


class NonQuantifiedSourceReadPerformanceTests(TestCase):
    def setUp(self):
        self.case = fixtures.NonQuantifiedManufacturingSourceTests(methodName='runTest')
        self.case.setUp()
        self.f, self.user = self.case.f, self.case.user
        self.plan, self.step = self.case.plan, self.case.step
        self.case.confirm_zero()
        self.case.configure()
        # These are native fixture writes in the disposable database, not
        # repeated formal-order execution or generation test cases.
        self.generated = {fact.pk: self.case.generate(fact,
            key=f'sim-read-performance-fixture-{fact.pk}') for fact in self.case.facts}
        self.requirement_ids = {row['operationRequirementId'] for row in self.generated.values()}
        self.last_profile = None

    def guarded_read(self, *, user=None, plan=None, step=None, action=None, label='native-plan-step'):
        """Measure native work alone; fixture snapshots sit outside its timer."""
        before = self.f.full_database_snapshot()
        before_changes = connection.connection.total_changes
        denied_sql = []
        queries = None
        elapsed_ns = None

        def only_reads(execute, sql, params, many, context):
            match = re.match(r'\s*([A-Za-z]+)', sql)
            verb = match.group(1).upper() if match else 'UNKNOWN'
            if verb not in {'SELECT', 'PRAGMA', 'BEGIN', 'COMMIT', 'SAVEPOINT', 'RELEASE', 'ROLLBACK'}:
                denied_sql.append(verb)
                raise AssertionError('Measured native read attempted a non-read SQL statement')
            if re.search(r'\bpassword\b', sql, flags=re.IGNORECASE):
                raise AssertionError('Native read must not select password fields')
            return execute(sql, params, many, context)

        try:
            with ExitStack() as stack:
                for target in (
                    'pde.operation_requirement_service.evaluate_specification',
                    'pde.operation_workload_source_service.evaluate_specification',
                    'pde.operation_workload_source_service.configure',
                    'pde.operation_requirement_service.OperationRequirementService.generate_readiness',
                    'pde.operation_requirement_service.OperationRequirementService.generate',
                    'pde.operation_requirement_service.OperationRequirementService.allocate',
                    'pde.operation_requirement_service.OperationRequirementService.allocate_group',
                    'pde.operation_requirement_correction_service.OperationRequirementCorrectionService.correct',
                    'pde.engineering_calculation_service.EngineeringCalculationService.execute',
                    'pde.engineering_fact_extension_service.EngineeringFactExtensionService.configure',
                    'pde.engineering_fact_extension_service.EngineeringFactExtensionService.derive',
                ):
                    stack.enter_context(patch(target, side_effect=AssertionError(
                        'A measured native read must not evaluate, configure or write')))
                queries = stack.enter_context(CaptureQueriesContext(connection))
                stack.enter_context(connection.execute_wrapper(only_reads))
                started = perf_counter_ns()
                try:
                    return (action() if action else workload.read_for_plan(
                        user=user or self.user, production_plan_id=(plan or self.plan).pk,
                        routing_step_id=(step or self.step).pk))
                finally:
                    elapsed_ns = perf_counter_ns() - started
        finally:
            statements = [row['sql'] for row in queries] if queries is not None else []
            self.last_profile = {'label': label, 'elapsedNanoseconds': elapsed_ns,
                'queryCount': len(statements),
                'selectCount': sum(sql.lstrip().upper().startswith('SELECT') for sql in statements),
                'connectionChanges': connection.connection.total_changes - before_changes,
                'deniedSqlVerbs': denied_sql}
            print('NONQUANTIFIED_NATIVE_SOURCE_READ_PROFILE=' + json.dumps(self.last_profile, sort_keys=True))
            self.assertEqual(denied_sql, [])
            self.assertEqual(self.last_profile['connectionChanges'], 0)
            self.assertEqual(self.f.full_database_snapshot(), before)

    def assert_complete_read(self, value):
        self.assertEqual(value['scope'], self.case.prep_case.scope)
        self.assertEqual(value['applicability']['result'], 'REQUIRED')
        self.assertEqual(value['sourceCandidates']['statusCode'], 'AVAILABLE', value)
        self.assertEqual(value['formalRequirements']['statusCode'], 'EXISTS', value)
        self.assertEqual({row['id'] for row in value['formalRequirements']['items']}, self.requirement_ids)
        self.assertEqual({row['sourceFactId'] for row in value['sourceCandidates']['items']}, set(self.generated))
        self.assertEqual(value['capacitySemantics']['meaningCode'], 'NON_QUANTIFIED')
        self.assertEqual(value['savedAllocations']['statusCode'], 'MISSING')
        self.assertEqual(value['savedAllocations']['items'], [])
        self.assertIsNone(value['savedAllocations']['quantity'])
        self.assertEqual({row['code'] for row in value['blockers']}, {'PROCESS_DEMAND_PLAN_ALLOCATION_MISSING'})
        self.assertEqual(value['businessWriteCount'], 0)
        self.assertEqual(value['auditWriteCount'], 0)
        self.assertFalse(value['newEorRuleEvaluated'])
        self.assertFalse(value['generated'])
        self.assertFalse(value['allocationSaved'])
        candidates = {row['sourceFactId']: row for row in value['sourceCandidates']['items']}
        for row in value['formalRequirements']['items']:
            expected = self.generated[row['sourceFactId']]['operationRequirement']
            self.assertEqual({key: row[key] for key in expected}, expected)
            proof = row['manufacturingPreparationContext']
            self.assertEqual(row['manufacturingReferenceType'], fixtures.MODE)
            self.assertEqual((row['manufacturingModeId'], row['workCenterId'], row['standardCapacityId']),
                (self.f.mode.pk, self.f.center.pk, None))
            self.assertEqual(proof['exactScope'], value['scope'])
            self.assertEqual(proof['revision'], value['inputPreparation']['revision'])
            self.assertEqual(proof['recordId'], value['inputPreparation']['recordId'])
            self.assertEqual(proof['capacityRuling'], {
                'code': 'CONFIRMED_ZERO', 'meaningCode': 'NON_QUANTIFIED', 'sourceValue': '0'})
            source = candidates[row['sourceFactId']]
            self.assertEqual(source['nativeGenerationContext'], self.case.context)
            self.assertEqual(source['objectCoverage'], proof['sourceObjectCoverage'])
            for key in ('sourceHash', 'inputHash', 'generationKey'):
                self.assertEqual(source[key], row[key])
            self.assertEqual(Decimal(source['quantity']), Decimal(row['workloadQuantity']))

    def test_native_read_preserves_complete_result_and_unknown_saved_load(self):
        self.assertNotEqual(self.step.pk, 804)
        first = self.guarded_read(label='first-native-request')
        self.assert_complete_read(first)
        first_profile = self.last_profile
        second = self.guarded_read(label='independent-native-request')
        self.assert_complete_read(second)
        self.assertEqual(second, first)
        self.assertGreater(first_profile['selectCount'], 0)
        self.assertGreater(self.last_profile['selectCount'], 0)

    def test_each_requirement_reuses_its_actual_validated_context_for_plan_consistency(self):
        validated = {}
        original = native._validate_requirement

        def observed(requirement, *args, **kwargs):
            result = original(requirement, *args, **kwargs)
            validated.setdefault(requirement.pk, []).append(result)
            return result

        with patch.object(native, '_validate_requirement', side_effect=observed) as validation, \
             patch.object(native, '_plan_source_consistency', wraps=native._plan_source_consistency) as plan_proof, \
             patch.object(nonquantified, '_plan_preparation', wraps=nonquantified._plan_preparation) as plan_preparation, \
             patch.object(preparation, 'read_preparation', wraps=preparation.read_preparation) as preparation_read:
            value = self.guarded_read(label='request-local-requirement-proof-reuse')
        self.assert_complete_read(value)
        self.assertEqual(validation.call_count, len(self.requirement_ids))
        self.assertEqual(set(validated), self.requirement_ids)
        self.assertTrue(all(len(results) == 1 for results in validated.values()))
        self.assertEqual(plan_proof.call_count, len(self.requirement_ids))
        self.assertEqual(plan_preparation.call_count, 1)
        self.assertEqual(preparation_read.call_count, 2,
            'One top-level preparation read and one complete shared plan proof must remain')
        for call in plan_proof.call_args_list:
            requirement = call.args[2]
            self.assertIs(call.kwargs.get('native_context'), validated[requirement.pk][0])
            self.assertEqual(call.kwargs['routing_step'].pk, self.step.pk)
        print('NONQUANTIFIED_NATIVE_PROOF_CALLS=' + json.dumps({
            'requirements': len(self.requirement_ids), 'requirementValidations': validation.call_count,
            'planConsistencyChecks': plan_proof.call_count, 'planPreparationProofs': plan_preparation.call_count,
            'preparationReads': preparation_read.call_count}, sort_keys=True))

    def test_typed_cache_versions_copies_and_same_connection_changes_cannot_hide_invalid_preparation(self):
        record = OperationInputPreparationDraft.objects.get(production_plan=self.plan, routing_step=self.step)

        def complete_keys(cache):
            return [key for key in cache if isinstance(key, tuple)
                and key[0] == 'non_quantified_plan_preparation']

        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)

            def read():
                return nonquantified.plan_preparation(user=self.user,
                    generation_context=self.case.context, operation=self.case.operation,
                    product_type=self.f.product_type, work_center=self.f.center, read_cache=cache)

            with patch.object(nonquantified, '_plan_preparation', wraps=nonquantified._plan_preparation) as loader:
                first = self.guarded_read(action=read, label='typed-cache-first-complete-proof')
                revision = first['preparation']['revision']
                base_hash = first['base'].input_hash
                first['scope']['productionPlanId'] += 1000000
                first['preparation']['revision'] += 1000000
                first['applicability']['result'] = 'PENDING'
                first['base'].input_hash = '0' * 64
                with patch.object(native, '_authorize', wraps=native._authorize) as authorization:
                    second = self.guarded_read(action=read, label='typed-cache-hit-is-copy')
                self.assertEqual(loader.call_count, 1)
                self.assertEqual([call.args[1] for call in authorization.call_args_list],
                    [native.VIEW, native.PLAN_VIEW, preparation.VIEW])
                self.assertEqual(second['scope'], self.case.prep_case.scope)
                self.assertEqual(second['preparation']['revision'], revision)
                self.assertEqual(second['applicability']['result'], 'REQUIRED')
                self.assertEqual(second['base'].input_hash, base_hash)
                self.assertEqual(len(complete_keys(cache)), 1)
                original_key = complete_keys(cache)[0]
                record_before = OperationInputPreparationDraft.objects.filter(pk=record.pk).values().get()
                changes_before = connection.connection.total_changes
                # Deliberate isolated fixture DML outside the guarded reader.
                # The company name changes neither preparation nor
                # the fresh permission decisions. Only total_changes differs.
                self.case.raw(self.f.company, name=f'SIMULATED_READ_COUNTER_CHANGE_{self.f.company.pk}')
                self.assertGreater(connection.connection.total_changes, changes_before)
                self.assertEqual(OperationInputPreparationDraft.objects.filter(pk=record.pk).values().get(),
                    record_before)
                reloaded = self.guarded_read(action=read, label='typed-cache-miss-after-unrelated-dml')
                self.assertEqual(loader.call_count, 2)
                self.assertEqual(reloaded['preparation'], second['preparation'])
                keys = complete_keys(cache)
                self.assertEqual(len(keys), 1)
                self.assertNotIn(original_key, cache)
                self.assertEqual(original_key[:-1], keys[0][:-1])
                self.assertNotEqual(original_key[-1], keys[0][-1])
                # Corrupt only the disposable fixture between guarded reads.
                # The complete native loader must reject, not return its prior
                # successful proof or cache the failed replacement.
                self.case.raw(record, revision=revision + 1)
                with self.assertRaises(native.OperationRequirementError) as caught:
                    self.guarded_read(action=read, label='typed-cache-invalid-revision-must-reprove')
                self.assertEqual(caught.exception.code, 'PREPARATION_CONTEXT_DRIFT')
                self.assertEqual(loader.call_count, 3)
                self.assertEqual(len(complete_keys(cache)), 0)
        self.assertFalse(cache.is_current(self.f.company.pk))

    def test_new_request_rejects_changed_requirement_and_source_input_proofs(self):
        self.assert_complete_read(self.guarded_read(label='proof-before-isolated-drift'))
        requirement = EngineeringOperationRequirement.objects.select_related('calculation').get(
            pk=next(iter(self.requirement_ids)))
        link = EngineeringFactInput.objects.filter(fact_id=self.case.facts[0].pk).order_by('pk').first()
        self.assertIsNotNone(link)
        faults = [('requirement-result', requirement.calculation, 'result_hash', 'OPERATION_FACT_CHANGED'),
            ('source-input-link', link, 'source_hash', 'FACT_EXTENSION_UNPROVEN')]
        for label, obj, field, code in faults:
            with self.subTest(proof=label), transaction.atomic():
                self.case.raw(obj, **{field: '0' * 64})
                value = self.guarded_read(label='new-request-after-' + label)
                self.assertEqual(value['formalRequirements']['statusCode'], 'INVALID', value)
                codes = {row['code'] for row in value['formalRequirements']['blockers']}
                self.assertIn(code, codes, value)
                self.assertIsNone(value['savedAllocations']['quantity'])
                if label == 'source-input-link':
                    self.assertEqual(value['sourceCandidates']['statusCode'], 'INVALID')
                    self.assertIn(code, {row['code'] for row in value['sourceCandidates']['blockers']})
                transaction.set_rollback(True)

    def test_new_formal_preparation_revision_invalidates_old_proof_without_rebinding(self):
        first = self.guarded_read(label='before-formal-preparation-revision')
        self.assert_complete_read(first)
        frozen = list(EngineeringOperationRequirement.objects.filter(pk__in=self.requirement_ids)
            .order_by('pk').values('id', 'trace', 'source_hash', 'input_hash', 'generation_key'))
        template = self.case.prep_case.ruling_basis()
        basis = preparation.build_capacity_ruling_basis(current_preparation=self.case.prep_case.read(),
            reference='SIMULATED_FOR_TEST/read-performance-later-confirmation', reference_sha256='e' * 64,
            exact_statement='Confirm the precise zero with a new explicitly appended preparation revision',
            reason='SIMULATED_FOR_TEST fresh source read must reject the old saved proof',
            source_proof=template['entries'][-1]['capacityRuling']['sourceProof'])
        self.case.prep_case.correct_capacity(basis=basis, revision=first['inputPreparation']['revision'],
            key='sim-read-performance-new-preparation-revision')
        value = self.guarded_read(label='after-formal-preparation-revision')
        self.assertGreater(value['inputPreparation']['revision'], first['inputPreparation']['revision'])
        self.assertEqual(value['formalRequirements']['statusCode'], 'INVALID', value)
        self.assertEqual(value['formalRequirements']['items'], [])
        self.assertIn('NON_QUANTIFIED_PREPARATION_CHANGED',
            {row['code'] for row in value['formalRequirements']['blockers']})
        self.assertIsNone(value['savedAllocations']['quantity'])
        self.assertEqual(list(EngineeringOperationRequirement.objects.filter(pk__in=self.requirement_ids)
            .order_by('pk').values('id', 'trace', 'source_hash', 'input_hash', 'generation_key')), frozen)

    def test_actual_reader_permissions_and_request_cache_ownership_are_fresh(self):
        self.assert_complete_read(self.guarded_read(label='before-permission-checks'))
        for permission in (native.VIEW, native.PLAN_VIEW, preparation.VIEW):
            with self.subTest(permission=permission), transaction.atomic():
                RolePermission.objects.filter(role=self.f.role, permission__code=permission).delete()
                with self.assertRaises((workload.OperationWorkloadSourceError,
                        preparation.OperationInputPreparationError)) as caught:
                    self.guarded_read(label='after-real-permission-removal')
                self.assertEqual(caught.exception.code, 'PERMISSION_DENIED')
                transaction.set_rollback(True)
        peer = User.objects.create_user(username='sim_nonquant_read_peer', company_id=self.f.company.pk)
        UserRoleScopeAssignment.objects.create(user=peer, role=self.f.role, organization=self.f.company,
            scope_code='ORGANIZATION', active=True, business_hash='SIMULATED_FOR_TEST actual read peer')
        caches = []
        original = native._source_read_cache

        def observed(user, read_cache):
            result = original(user, read_cache)
            caches.append((user.pk, result))
            self.assertEqual(result.user_id, user.pk)
            self.assertEqual(result.company_id, user.company_id)
            return result

        with patch.object(native, '_source_read_cache', side_effect=observed):
            first = self.guarded_read(label='first-actual-reader')
            boundary = len(caches)
            other = self.guarded_read(user=peer, label='different-actual-reader')
        self.assert_complete_read(first)
        self.assert_complete_read(other)
        self.assertTrue(caches[:boundary])
        self.assertTrue(caches[boundary:])
        self.assertEqual({user_id for user_id, _ in caches[:boundary]}, {self.user.pk})
        self.assertEqual({user_id for user_id, _ in caches[boundary:]}, {peer.pk})
        self.assertTrue({id(cache) for _, cache in caches[:boundary]}.isdisjoint(
            {id(cache) for _, cache in caches[boundary:]}))
        self.assertTrue(all(not cache.is_current(self.f.company.pk) for _, cache in caches))

    def test_company_plan_and_step_scope_cannot_reuse_current_saved_proofs(self):
        self.assert_complete_read(self.guarded_read(label='before-scope-isolation'))
        company = Company.objects.create(code='SIM-NQ-READ-FOREIGN', name='SIMULATED_FOR_TEST foreign source reader')
        foreign = User.objects.create_user(username='sim_nonquant_read_foreign', company_id=company.pk)
        UserRoleScopeAssignment.objects.create(user=foreign, role=self.f.role, organization=company,
            scope_code='ORGANIZATION', active=True, business_hash='SIMULATED_FOR_TEST foreign reader scope')
        denied = self.guarded_read(user=foreign, label='authorized-reader-in-foreign-company')
        self.assertEqual(denied['scope'], {})
        self.assertIn('WORKLOAD_SOURCE_PLAN_MISSING', {row['code'] for row in denied['blockers']})
        wrong = self.guarded_read(step=self.f.wrong_step, label='wrong-fixed-route-version-step')
        self.assertEqual(wrong['scope'], {})
        self.assertIn('WORKLOAD_SOURCE_STEP_MISMATCH', {row['code'] for row in wrong['blockers']})
        another = self.guarded_read(step=self.f.step, label='other-step-in-current-route')
        self.assertNotEqual(another['scope'].get('routingStepId'), self.step.pk)
        self.assertTrue(self.requirement_ids.isdisjoint(
            {row['id'] for row in another['formalRequirements']['items']}))
        # This second legitimate plan lacks a fixed output. The public reader
        # rejects its missing source contract; do not call it a second valid
        # same-object plan. The existing exact-scope proof is checked directly.
        other_plan = self.case.other_plan()
        no_context = self.guarded_read(plan=other_plan, label='other-plan-without-fixed-output')
        self.assertEqual(no_context['scope'], {})
        self.assertTrue(no_context['blockers'])
        req = EngineeringOperationRequirement.objects.select_related(
            'calculation', 'source_calculation', 'source_detail__rule', 'audit_record', 'uom').get(
                pk=next(iter(self.requirement_ids)))
        with self.assertRaises(native.OperationRequirementError) as caught:
            self.guarded_read(label='native-exact-scope-cross-plan-rejection', action=lambda:
                native._plan_source_consistency(self.f.company.pk, other_plan, req,
                    routing_step=self.step))
        self.assertEqual(caught.exception.code, 'NON_QUANTIFIED_CONTEXT_MISMATCH')
