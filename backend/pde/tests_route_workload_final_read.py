"""SIMULATED_FOR_TEST: current route workload reads in a named isolated DB.

Native fixtures save their own sources/EORs/allocations. No successful reader,
proof or authorization is mocked. Pure state-format tests do not invent native
success; they only verify the final Chinese presentation mapping.
"""
from copy import deepcopy
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.db import connection, transaction
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from system.models import Company, OrganizationOperatingAuditRecord, Permission, RolePermission, User
from . import operation_requirement_service as native
from . import operation_workload_source_service as service
from . import tests_operation_workload_source_service as fixtures
from . import tests_plan_legal_extension_admission as legal
from .models import EngineeringOperationRequirement, ProductionPlanOperationRequirementAllocation


if os.environ.get('PCE_ROUTE_WORKLOAD_ISOLATED_TESTS') != '1':
    raise RuntimeError('Route workload tests require the reviewed named isolated runner')
_allowed = {Path(os.environ[key]).resolve() for key in ('PCE_DATABASE_PATH', 'PCE_ISOLATED_TEST_DATABASE')}
if Path(settings.DATABASES['default']['NAME']).resolve() not in _allowed:
    raise RuntimeError('Route workload tests are outside the explicit isolated database allowlist')


class RouteWorkloadFinalNativeTests(TestCase):
    def setUp(self):
        self.case = fixtures.OperationWorkloadSourceTests(methodName='runTest')
        self.case.setUp()
        self.f, self.plan = self.case.f, self.case.plan
        self.case.configure()
        self.case.fixture.save_contributions(list(reversed(self.case.fixture.requirements)))

    def overview(self, **kwargs):
        before = self.f.full_database_snapshot()
        with CaptureQueriesContext(connection) as queries:
            value = service.read_route_overview(user=self.f.user,
                production_plan_id=self.plan.pk, **kwargs)
        self.assertEqual(before, self.f.full_database_snapshot())
        self.assertFalse(any(row['sql'].lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE', 'REPLACE'}
            for row in queries))
        return value, list(queries)

    def test_opt_in_reads_exact_native_identity_quantity_and_compact_proofs_once(self):
        with patch.object(native.OperationRequirementService, 'read', wraps=native.OperationRequirementService.read) as spy:
            value, _ = self.overview(include_workloads=True)
        self.assertEqual(spy.call_count, 1)
        self.assertTrue(value['workloadReviewIncluded'])
        self.assertEqual(value['workloadReviewContract'], service.WORKLOAD_REVIEW_CONTRACT)
        self.assertEqual(value['summary']['stepCount'], len(value['rows']))
        self.assertEqual(len({row['routingStepId'] for row in value['rows']}), len(value['rows']))
        target = next(row for row in value['rows'] if row['routingStepId'] == self.f.step.pk)
        self.assertEqual(target['scope']['mainCalculationId'], self.f.source_calc.pk)
        self.assertEqual(target['predecessorSequences'], self.f.step.predecessor_sequences)
        self.assertEqual(target['savedAllocations']['quantity'], '4.000000')
        self.assertEqual(target['workloadReview']['savedQuantity'], target['savedAllocations']['quantity'])
        self.assertEqual(target['workloadReview']['allocationCount'], 3)
        # The reused fixture legitimately retains three effective main-source
        # EORs as well as three independently generated extension EORs. The
        # final reader must report all six, not deduplicate by equal quantities.
        expected_requirements = set(self.f.old_ids) | {req.pk for req in self.case.fixture.requirements}
        self.assertEqual({row['operationRequirementId'] for row in target['formalRequirements']['items']},
            expected_requirements)
        self.assertEqual(target['workloadReview']['formalRequirementCount'], len(expected_requirements))
        self.assertEqual(target['objectCoverage']['statusCode'], 'PROVEN')
        self.assertEqual(set(target['objectCoverage']['baselineItemIds']), {row.pk for row in self.f.baseline_items})
        self.assertEqual({row['sourceFactId'] for row in target['savedAllocations']['items']},
            {req.source_fact_id for req in self.case.fixture.requirements})
        self.assertTrue(all('sourceSnapshot' not in row and 'inputSnapshot' not in row
            for row in target['formalRequirements']['items']))
        self.assertTrue(value['readComplete'])
        self.assertFalse(value['businessComplete'])  # second operation is truly unallocated
        self.assertFalse(value['wholeRouteReady'])
        self.assertNotIn('noDateReady', value)
        self.assertNotEqual(self.f.step.pk, 803)
        self.assertEqual(len(value['workloadResultHash']), 64)

    def test_real_multi_contribution_read_batches_plan_relations_without_lazy_queries(self):
        saved_contribution = native._saved_contribution
        reads = []

        def observe_saved_contribution(row, *args, **kwargs):
            with CaptureQueriesContext(connection) as queries:
                result = saved_contribution(row, *args, **kwargs)
            reads.append((row.pk, list(queries)))
            return result

        with patch.object(native, '_saved_contribution', side_effect=observe_saved_contribution):
            value, _ = self.overview(include_workloads=True)
        target = next(row for row in value['rows'] if row['routingStepId'] == self.f.step.pk)
        expected = set(ProductionPlanOperationRequirementAllocation.objects.filter(
            production_plan=self.plan, routing_step=self.f.step).values_list('pk', flat=True))
        self.assertEqual(len(expected), 3)
        self.assertEqual({allocation_id for allocation_id, _ in reads}, expected)
        # The full-plan read and the individual-step read both consume every
        # real saved contribution. Neither may issue a per-row plan/source FK
        # lookup after the original native proof has passed in this call.
        self.assertGreaterEqual(len(reads), 2 * len(expected))
        for allocation_id, queries in reads:
            self.assertEqual(queries, [], f'Allocation {allocation_id} performed lazy SQL: {queries}')
        self.assertEqual({row['allocationId'] for row in target['savedAllocations']['items']}, expected)
        self.assertEqual(target['savedAllocations']['quantity'], '4.000000')
        self.assertEqual(target['workloadReview']['allocationCount'], len(expected))
        self.assertTrue(value['readComplete'])

    def test_detail_prefetch_preserves_complete_native_rows_order_and_separate_sources(self):
        from django.db.models import QuerySet
        from .models import EngineeringDerivedFact, EngineeringRuleDefinition
        old_select = QuerySet.select_related
        validate = native._validate_requirement
        matches = service._candidate_matches

        def run(restore_old_joins):
            requirements, facts = {}, {}

            def select(query, *fields):
                if restore_old_joins:
                    if query.model is EngineeringOperationRequirement and fields in (
                            ('calculation', 'source_fact', 'source_detail__rule', 'audit_record', 'uom'),
                            ('calculation', 'source_fact', 'source_detail', 'audit_record', 'uom')):
                        fields = ('calculation', 'source_calculation', 'source_fact', 'source_detail__rule', 'audit_record', 'uom')
                    elif query.model is EngineeringDerivedFact and fields in (
                            ('source_detail__rule', 'rule', 'uom'), ('source_detail', 'uom')):
                        fields = ('calculation__origin_calculation', 'source_detail__rule', 'rule', 'uom')
                return old_select(query, *fields)

            def observe_requirement(req, *args, **kwargs):
                requirements.setdefault(req.pk, req)
                return validate(req, *args, **kwargs)

            def observe_fact(fact, source):
                facts.setdefault(fact.pk, fact)
                return matches(fact, source)

            before, changes = self.f.full_database_snapshot(), connection.connection.total_changes
            with patch.object(QuerySet, 'select_related', select), \
                    patch.object(native, '_validate_requirement', side_effect=observe_requirement), \
                    patch.object(service, '_candidate_matches', side_effect=observe_fact):
                result = service.read_for_plan(user=self.f.user, production_plan_id=self.plan.pk,
                    routing_step_id=self.case.step.pk)
            self.assertEqual((self.f.full_database_snapshot(), connection.connection.total_changes), (before, changes))
            self.assertTrue(result['sourceConfiguration']['hasValidSourceConfiguration'], result)
            self.assertEqual(result['sourceCandidates']['statusCode'], 'AVAILABLE', result)
            self.assertEqual(result['formalRequirements']['statusCode'], 'EXISTS', result)
            req_rows, fact_rows = [], []
            for req in requirements.values():
                self.assertEqual(req.source_calculation.pk, req.source_calculation_id)
                req_rows.append((req.pk, tuple(native._proof_record_hash(row) for row in (
                    req, req.calculation, req.source_calculation, req.source_fact,
                    req.source_detail, req.source_detail.rule, req.audit_record, req.uom))))
            for fact in facts.values():
                self.assertEqual(fact.calculation.pk, fact.calculation_id)
                fact_rows.append((fact.pk, tuple(native._proof_record_hash(row) for row in (
                    fact, fact.calculation, fact.calculation.origin_calculation, fact.source_detail,
                    fact.source_detail.rule, fact.rule, fact.uom))))
            return result, req_rows, fact_rows, (
                len({id(req.source_calculation) for req in requirements.values()}),
                len({id(fact.calculation) for fact in facts.values()}))

        configured = EngineeringRuleDefinition.objects.get(company=self.f.company,
            rule_code='SIM-OPERATION-SOURCE', version='V1')
        source_ids, nullable_origins = set(), set()
        for direct in (False, True):
            with self.subTest(source='main' if direct else 'extension'), transaction.atomic():
                if direct:
                    self.f.advance(configured, 'obsolete')
                    config = self.case.configure(ruleCode='SIM-PREFETCH-DIRECT',
                        producerRuleId=self.f.producer.pk, traceEquals={'sourceKind': 'SIMULATED_FOR_TEST'})
                    rule_id = config['nativeResult']['rules'][0]['id']
                    source_facts = self.f.facts
                else:
                    rule_id = configured.pk
                    source_facts = self.case.fixture.fixture.facts
                for fact in source_facts:
                    native.OperationRequirementService.generate(user=self.f.user,
                        source_calculation_id=fact.calculation_id, source_fact_id=fact.pk, rule_id=rule_id,
                        idempotency_key=f'sim-prefetch-query-{rule_id}-{fact.pk}', reason='SIMULATED_FOR_TEST')
                    source_ids.add(fact.calculation_id)
                    nullable_origins.add(fact.calculation.origin_calculation_id is None)
                original, old_requirements, old_facts, old_objects = run(True)
                candidate, new_requirements, new_facts, new_objects = run(False)
                self.assertEqual(candidate, original)
                self.assertEqual(new_requirements, old_requirements)
                self.assertEqual(new_facts, old_facts)
                self.assertTrue(new_requirements and new_facts)
                self.assertLess(new_objects[0], old_objects[0])
                self.assertLess(new_objects[1], old_objects[1])
                transaction.set_rollback(True)
        self.assertEqual(len(source_ids), 2)
        self.assertEqual(nullable_origins, {False, True})

    def test_metadata_default_stays_unread_and_does_not_deep_read(self):
        with patch.object(service, 'read_for_plan', side_effect=AssertionError('metadata must not deep read')):
            value, _ = self.overview()
        self.assertNotIn('workloadReviewIncluded', value)
        self.assertTrue(all(row['formalRequirements']['statusCode'] == 'NOT_READ'
            and row['savedAllocations']['quantity'] is None for row in value['rows']))

    def test_missing_native_contributions_remain_unknown_not_zero_or_source_quantity(self):
        value, _ = self.overview(include_workloads=True)
        target = next(row for row in value['rows'] if row['routingStepId'] == self.case.step.pk)
        self.assertEqual(target['formalRequirements']['statusCode'], 'MISSING')
        self.assertEqual(target['savedAllocations']['statusCode'], 'MISSING')
        self.assertIsNone(target['workloadReview']['savedQuantity'])
        self.assertEqual(target['workloadReview']['allocationCount'], 0)
        self.assertEqual(target['workloadReview']['statusCode'], 'BLOCKED')

    def test_hash_change_and_new_request_cannot_reuse_successful_cached_proof(self):
        self.overview(include_workloads=True)
        req = self.case.fixture.requirements[0]
        legal.PlanLegalExtensionAdmissionTests.raw(self, req, 'source_hash', '0' * 64)
        value, _ = self.overview(include_workloads=True)
        target = next(row for row in value['rows'] if row['routingStepId'] == self.f.step.pk)
        self.assertEqual(target['savedAllocations']['statusCode'], 'INVALID')
        self.assertIsNone(target['workloadReview']['savedQuantity'])
        self.assertFalse(value['businessComplete'])

    def test_successful_budget_reuse_is_atomic_actor_bound_and_never_applies_to_proposal(self):
        req = EngineeringOperationRequirement.objects.select_related('source_calculation__sales_order_item').get(
            pk=self.case.fixture.requirements[0].pk)
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            native.OperationRequirementService.read(user=self.f.user, production_plan_id=self.plan.pk, _read_cache=cache)
            self.assertTrue(cache.budget_proofs)
            source_scope = native._allocation_budget_scope(req, self.f.company.pk, plan=self.plan)
            with CaptureQueriesContext(connection) as queries:
                native._scope_budget(req, self.f.company.pk, source_scope=source_scope, read_cache=cache,
                    validation_cache=native._allocation_read_cache(cache, self.f.company.pk))
            self.assertEqual(len(queries), 0)
            with self.assertRaises(native.OperationRequirementError) as caught:
                native._scope_budget(req, self.f.company.pk, proposed_plan=self.plan,
                    proposed_quantity=self.f.item.quantity + 1, read_cache=cache,
                    validation_cache=native._allocation_read_cache(cache, self.f.company.pk))
            self.assertEqual(caught.exception.code, 'ALLOCATION_SCOPE_EXCEEDED')
        with transaction.atomic():
            fresh = native._source_read_cache(self.f.user, cache)
            self.assertIsNot(fresh, cache)
            self.assertEqual(fresh.budget_proofs, {})
            changed_actor = User(pk=self.f.user.pk + 10000, company_id=self.f.company.pk)
            native._bind_current_actor(fresh, changed_actor)
            self.assertEqual(native._allocation_read_cache(fresh, self.f.company.pk), {})

    def test_current_permission_and_company_scope_remain_required(self):
        foreign = Company.objects.create(code='SIM-FINAL-FOREIGN', name='SIM foreign')
        viewer = User.objects.create_user(username='sim-final-foreign', company_id=foreign.pk,
            is_active=True, is_staff=True, is_superuser=True)
        with self.assertRaises(service.OperationWorkloadSourceError):
            service.read_route_overview(user=viewer, production_plan_id=self.plan.pk, include_workloads=True)
        permission = Permission.objects.get(code=native.PLAN_VIEW)
        RolePermission.objects.filter(role=self.f.role, permission=permission).delete()
        with self.assertRaises(service.OperationWorkloadSourceError):
            service.read_route_overview(user=self.f.user, production_plan_id=self.plan.pk, include_workloads=True)

    def test_complete_requirement_proof_reuses_success_only_and_returns_an_independent_copy(self):
        req = EngineeringOperationRequirement.objects.select_related(
            'calculation', 'source_detail__rule', 'audit_record').get(pk=self.case.fixture.requirements[0].pk)
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            with patch.object(native, '_generation_context', wraps=native._generation_context) as spy:
                first = native._validate_requirement(req, self.f.company.pk, read_cache=cache)
                second = native._validate_requirement(req, self.f.company.pk, read_cache=cache)
                self.assertEqual(spy.call_count, 1)
                self.assertEqual(first['source_hash'], second['source_hash'])
                second['source_snapshot']['simulated_caller_change'] = True
                third = native._validate_requirement(req, self.f.company.pk, read_cache=cache)
                self.assertNotIn('simulated_caller_change', third['source_snapshot'])
                original_hash = req.source_hash
                req.source_hash = '0' * 64
                for expected_count in (2, 3):
                    with self.assertRaises(native.OperationRequirementError) as caught:
                        native._validate_requirement(req, self.f.company.pk, read_cache=cache)
                    self.assertEqual(caught.exception.code, 'OPERATION_FACT_CHANGED')
                    self.assertEqual(spy.call_count, expected_count)  # failed proofs never enter the cache
                req.source_hash = original_hash
                native._validate_requirement(req, self.f.company.pk, read_cache=cache)
                self.assertEqual(spy.call_count, 3)

    def test_same_connection_write_invalidates_source_scope_and_requirement_proofs(self):
        req = EngineeringOperationRequirement.objects.get(pk=self.case.fixture.requirements[0].pk)
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            native.OperationRequirementService.read(user=self.f.user,
                production_plan_id=self.plan.pk, _read_cache=cache)
            service._scope_context(self.f.user, self.plan.pk, self.f.step.pk, _read_cache=cache)
            cache['simulated_old_proof'] = True
            self.assertTrue(cache.budget_proofs)
            self.assertTrue(cache.allocation_validation_cache)
            legal.PlanLegalExtensionAdmissionTests.raw(self, req, 'source_hash', '0' * 64)
            self.assertTrue(cache.is_current(self.f.company.pk))
            self.assertNotIn('simulated_old_proof', cache)
            self.assertFalse(cache.budget_proofs)
            self.assertFalse(cache.allocation_validation_cache)
            self.assertFalse(any(isinstance(key, tuple) and key[0] == 'verified_workload_step_scope'
                for key in cache))
            req.refresh_from_db()
            with self.assertRaises(native.OperationRequirementError):
                native._validate_requirement(req, self.f.company.pk, read_cache=cache)

    def test_native_scope_is_verified_once_and_changed_step_cannot_reuse_it(self):
        from .routing_step_applicability_service import RoutingStepApplicabilityResolver
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            with patch.object(RoutingStepApplicabilityResolver, 'resolve',
                    wraps=RoutingStepApplicabilityResolver.resolve) as spy:
                first = service._scope_context(self.f.user, self.plan.pk, self.f.step.pk, _read_cache=cache)
                verified_calls = spy.call_count
                self.assertGreater(verified_calls, 0)
                with CaptureQueriesContext(connection) as queries:
                    second = service._scope_context(self.f.user, self.plan.pk, self.f.step.pk, _read_cache=cache)
                self.assertEqual(spy.call_count, verified_calls)
                self.assertEqual(len(queries), 0)
                self.assertEqual(second[-1], first[-1])
                second[-1]['result'] = 'SIMULATED_CALLER_CHANGE'
                self.assertEqual(service._scope_context(self.f.user, self.plan.pk,
                    self.f.step.pk, _read_cache=cache)[-1], first[-1])
                # The normal ORM correctly freezes released route steps. Inject
                # this deliberate invalid fixture state with the existing raw
                # test helper, never by weakening that production write guard.
                legal.PlanLegalExtensionAdmissionTests.raw(self, self.f.step, 'is_active', False)
                with self.assertRaises(service.OperationWorkloadSourceError) as caught:
                    service._scope_context(self.f.user, self.plan.pk, self.f.step.pk, _read_cache=cache)
                self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_STEP_MISMATCH')

    def test_plain_write_caches_and_foreign_actor_never_reuse_read_requirement_approval(self):
        req = self.case.fixture.requirements[0]
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            native._validate_requirement(req, self.f.company.pk, read_cache=cache)
            actor = User(pk=self.f.user.pk + 10000, company_id=self.f.company.pk)
            native._bind_current_actor(cache, actor)
            self.assertFalse(cache.is_current(self.f.company.pk))
            self.assertIsNot(native._source_read_cache(actor, cache), cache)
            with patch.object(native, '_generation_context', wraps=native._generation_context) as spy:
                native._validate_requirement(req, self.f.company.pk, read_cache={})
                native._validate_requirement(req, self.f.company.pk, read_cache={})
                self.assertEqual(spy.call_count, 2)

    def test_polluted_read_only_models_discard_dependent_proofs_and_revalidate(self):
        req = self.case.fixture.requirements[0]
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            with patch.object(native, '_generation_context', wraps=native._generation_context) as spy:
                first = native._validate_requirement(req, self.f.company.pk, read_cache=cache)
                original = first['origin'].input_hash
                cache['simulated_dependent_proof'] = True
                # Existing request-local ORM objects are read-only references.
                # Deliberate caller pollution must never preserve an approval.
                first['origin'].input_hash = '0' * 64
                second = native._validate_requirement(req, self.f.company.pk, read_cache=cache)
                self.assertEqual(spy.call_count, 2)
                self.assertEqual(second['origin'].input_hash, original)
                self.assertNotIn('simulated_dependent_proof', cache)
            scope = service._scope_context(self.f.user, self.plan.pk, self.f.step.pk, _read_cache=cache)
            original = scope[3].input_hash
            cache['simulated_dependent_proof'] = True
            scope[3].input_hash = '0' * 64
            fresh = service._scope_context(self.f.user, self.plan.pk, self.f.step.pk, _read_cache=cache)
            self.assertEqual(fresh[3].input_hash, original)
            self.assertNotIn('simulated_dependent_proof', cache)


class RouteFixedSourceHashMathTests(TestCase):
    def test_fixed_route_hash_memo_matches_original_sha_and_never_hides_source_or_model_drift(self):
        import sys
        from . import tests_workload_read_source_scope_performance as scope_fixtures
        from .production_foundation_service import _snapshot
        fixture = scope_fixtures.WorkloadReadSourceScopePerformanceTests(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        ordinary, ordinary_counts = fixture.readonly(lambda: fixture.measured_proofs(False))
        original_hash, observed = native._proof_record_hash, []

        def inspect_hash(row, *, read_cache=None):
            value = original_hash(row, read_cache=read_cache)
            frame = sys._getframe(1)
            while frame is not None and frame.f_code.co_filename != native.__file__:
                frame = frame.f_back
            if frame is not None and frame.f_code.co_name == '_plan_source_consistency':
                self.assertIsInstance(read_cache, native._ReadOnlyProofCache)
                self.assertEqual(value, native._digest(_snapshot(row)))
                observed.append(row._meta.label_lower)
            return value

        with patch.object(native, '_proof_record_hash', side_effect=inspect_hash):
            typed, typed_counts = fixture.readonly(lambda: fixture.measured_proofs(True))
        self.assertEqual(typed, ordinary)
        self.assertEqual(typed_counts, (1, 1, 1, 1))
        self.assertEqual(ordinary_counts, (3, 6, 6, 6))
        self.assertGreaterEqual(len(observed), 8 * len(fixture.req_ids) * 2)
        self.assertIn('pde.routingstep', observed)
        self.assertIn('pde.engineeringcalculationrecord', observed)

        def reject_changed_values():
            with transaction.atomic():
                cache = native._ReadOnlyProofCache(fixture.user)
                plan, reqs, step = fixture.loaded()
                context = native._validate_requirement(reqs[0], fixture.user.company_id, read_cache=cache)
                args = {'native_context': context, 'routing_step': step, 'read_cache': cache}
                native._plan_source_consistency(fixture.user.company_id, plan, reqs[0], **args)
                output = plan.planning_requirement.demand.manufacturing_output
                status = output.bom_version.status
                output.bom_version.status = 'draft'
                with patch.object(output, 'clean', wraps=output.clean) as clean:
                    with self.assertRaises(native.OperationRequirementError) as caught:
                        native._plan_source_consistency(fixture.user.company_id, plan, reqs[0], **args)
                    self.assertEqual(caught.exception.code, 'ALLOCATION_SOURCE_MISMATCH')
                    self.assertEqual(clean.call_count, 1)
                output.bom_version.status = status
                reqs[0].source_hash = '0' * 64
                with self.assertRaises(native.OperationRequirementError) as caught:
                    native._plan_source_consistency(fixture.user.company_id, plan, reqs[0], **args)
                self.assertEqual(caught.exception.code, 'ALLOCATION_SOURCE_MISMATCH')
        fixture.readonly(reject_changed_values)


class RouteWorkloadNonQuantifiedInvalidationTests(TestCase):
    def test_changed_precise_preparation_rejects_a_previously_valid_same_request_requirement(self):
        from . import tests_nonquantified_manufacturing_source as nonquantified_fixtures
        from .models import OperationInputPreparationDraft
        case = nonquantified_fixtures.NonQuantifiedManufacturingSourceTests(methodName='runTest')
        case.setUp()
        case.confirm_zero()
        case.configure()
        saved = case.generate(key='sim-route-workload-current-preparation-proof')
        self.assertNotEqual(case.step.pk, 804)
        req = EngineeringOperationRequirement.objects.select_related(
            'calculation', 'source_detail__rule', 'audit_record').get(pk=saved['operationRequirementId'])
        frozen = EngineeringOperationRequirement.objects.filter(pk=req.pk).values().get()
        record = OperationInputPreparationDraft.objects.get(production_plan=case.plan, routing_step=case.step)
        with transaction.atomic():
            cache = native._source_read_cache(case.user, None)
            with patch.object(native, '_generation_context', wraps=native._generation_context) as spy:
                first = native._validate_requirement(req, case.f.company.pk, read_cache=cache, user=case.user)
                second = native._validate_requirement(req, case.f.company.pk, read_cache=cache, user=case.user)
                self.assertEqual(first['source_hash'], second['source_hash'])
                self.assertEqual(spy.call_count, 1)
                # Disposable invalid-state injection only: current revision no
                # longer matches the real saved ruling/audit. No proof is mocked.
                case.raw(record, revision=record.revision + 1)
                for expected_count in (2, 3):
                    with self.assertRaises(native.OperationRequirementError) as caught:
                        native._validate_requirement(req, case.f.company.pk, read_cache=cache, user=case.user)
                    self.assertEqual(caught.exception.code, 'PREPARATION_CONTEXT_DRIFT')
                    self.assertEqual(spy.call_count, expected_count)
            self.assertEqual(EngineeringOperationRequirement.objects.filter(pk=req.pk).values().get(), frozen)


class RouteWorkloadLifecycleProofTests(TestCase):
    """Real append-only correction fixtures; successful evidence is never mocked."""

    def setUp(self):
        from . import tests_calc4_routing_correction as correction_fixtures
        from . import operation_requirement_correction_service as correction
        self.correction = correction
        self.f = correction_fixtures.Calc4RoutingCorrectionTests(methodName='runTest')
        self.f.setUp()
        saved = self.f.correct(replacements=[{'operationRequirementId': pk,
            'ruleId': self.f.correct_rule.pk} for pk in reversed(self.f.old_ids)],
            key='sim-lifecycle-read-pair-proof')
        self.pairs = saved['replacements']

    def req(self, pk):
        return EngineeringOperationRequirement.objects.select_related(
            'calculation', 'source_detail__rule').get(pk=pk)

    def read(self, req, cache=None):
        return self.correction.requirement_lifecycle(req, self.f.company.pk, read_cache=cache)

    def lifecycle_keys(self, cache):
        return [key for key in cache if isinstance(key, tuple) and key[0] == 'requirement_lifecycle']

    def pair_rows(self, index=0):
        pair = self.pairs[index]
        return self.req(pair['operationRequirementId']), self.req(pair['replacementRequirementId'])

    def test_complete_native_pair_reuses_both_endpoints_with_independent_json_and_unordered_identities(self):
        frozen = self.f.full_database_snapshot()
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            with patch.object(self.correction, '_relationship', wraps=self.correction._relationship) as spy:
                for index in (2, 0, 1):
                    old, new = self.pair_rows(index)
                    expected_old, expected_new = self.read(old), self.read(new)
                    count = spy.call_count
                    current_new = self.read(new, cache)
                    self.assertEqual(spy.call_count, count + 1)
                    with CaptureQueriesContext(connection) as queries:
                        current_old = self.read(old, cache)
                    self.assertEqual(len(queries), 0)
                    self.assertEqual(spy.call_count, count + 1)
                    self.assertEqual(current_old, expected_old)
                    self.assertEqual(current_new, expected_new)
                    current_new['history'][0]['relationship']['requirementQuantity'] = '999'
                    self.assertEqual(self.read(new, cache), expected_new)
                    self.assertNotEqual(old.pk, 804)
                self.assertEqual(len(self.lifecycle_keys(cache)), 6)
        self.assertEqual(self.f.full_database_snapshot(), frozen)

    def test_invalid_relationship_audit_and_missing_counterpart_never_publish_partial_pair(self):
        from system.models import OrganizationOperatingAuditRecord
        from workflow_runtime.models import BusinessStateTransition
        for index, fault in enumerate(('hash', 'counterpart', 'audit')):
            old, new = self.pair_rows(index)
            transition = BusinessStateTransition.objects.get(object_type=self.correction.OBJECT_TYPE,
                object_id=new.pk)
            audit = OrganizationOperatingAuditRecord.objects.get(pk=int(transition.audit_reference.split(':')[1]))
            if fault == 'counterpart':
                # Deliberate invalid isolated fixture: the new endpoint no longer
                # has the required first transition. Production guards stay intact.
                legal.PlanLegalExtensionAdmissionTests.raw(self, transition, 'version', 2)
            else:
                after = deepcopy(audit.after_snapshot)
                if fault == 'hash':
                    after['state']['relationship']['old']['recordHash'] = '0' * 64
                else:
                    after['authorization']['allowed'] = False
                legal.PlanLegalExtensionAdmissionTests.raw(self, audit, 'after_snapshot', after)
            with transaction.atomic():
                cache = native._source_read_cache(self.f.user, None)
                for _ in range(2):
                    with self.assertRaises(native.OperationRequirementError) as caught:
                        self.read(old, cache)
                    self.assertIn(caught.exception.code, {
                        'CORRECTION_HISTORY_UNPROVEN', 'CORRECTION_RELATIONSHIP_UNPROVEN'})
                    self.assertEqual(self.lifecycle_keys(cache), [])

    def test_same_connection_audit_change_invalidates_cached_pair_and_still_rejects(self):
        from system.models import OrganizationOperatingAuditRecord
        from workflow_runtime.models import BusinessStateTransition
        old, new = self.pair_rows()
        transition = BusinessStateTransition.objects.get(object_type=self.correction.OBJECT_TYPE,
            object_id=new.pk)
        audit = OrganizationOperatingAuditRecord.objects.get(pk=int(transition.audit_reference.split(':')[1]))
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            self.read(old, cache)
            self.assertEqual(len(self.lifecycle_keys(cache)), 2)
            after = deepcopy(audit.after_snapshot)
            after['executionChain']['account'] = 'SIM-CONFLICTING-ACTOR'
            legal.PlanLegalExtensionAdmissionTests.raw(self, audit, 'after_snapshot', after)
            for _ in range(2):
                with self.assertRaises(native.OperationRequirementError) as caught:
                    self.read(new, cache)
                self.assertEqual(caught.exception.code, 'CORRECTION_HISTORY_UNPROVEN')
                self.assertEqual(self.lifecycle_keys(cache), [])

    def test_actor_company_atomic_and_plain_write_cache_do_not_share_lifecycle_approval(self):
        old, new = self.pair_rows()
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            expected = self.read(new, cache)
            native._bind_current_actor(cache, User(pk=self.f.user.pk + 173,
                company_id=self.f.company.pk))
            with patch.object(self.correction, '_relationship', wraps=self.correction._relationship) as spy:
                self.assertEqual(self.read(new, cache), expected)
                self.assertGreater(spy.call_count, 1)  # native uncached contract, not a forged permission gate
            with self.assertRaises(native.OperationRequirementError) as caught:
                self.correction.requirement_lifecycle(old, self.f.company.pk + 173, read_cache=cache)
            self.assertEqual(caught.exception.code, 'CORRECTION_SOURCE_MISMATCH')
            plain = {}
            for _ in range(2):
                with patch.object(self.correction, '_relationship', wraps=self.correction._relationship) as spy:
                    self.assertEqual(self.read(new, plain), expected)
                    self.assertGreater(spy.call_count, 1)
                self.assertEqual(plain, {})
            current = native._source_read_cache(self.f.user, None)
            self.read(old, current)
        with transaction.atomic():
            self.assertIsNone(native._requirement_read_cache(current, self.f.company.pk))
            with patch.object(self.correction, '_relationship', wraps=self.correction._relationship) as spy:
                self.assertEqual(self.read(new, current), expected)
                self.assertGreater(spy.call_count, 1)

    def test_polluted_internal_models_clear_all_proofs_and_credentials_remain_deferred(self):
        old, new = self.pair_rows()
        frozen = self.f.full_database_snapshot()
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            with CaptureQueriesContext(connection) as queries:
                expected = self.read(new, cache)
            self.assertTrue(queries)
            self.assertFalse(any('"password"' in row['sql'] for row in queries))
            saved = cache[self.lifecycle_keys(cache)[0]]
            models = [row for row, actor in saved['proof'].models.values() if not actor]
            internal = next(row for row in models
                if isinstance(row, EngineeringOperationRequirement) and row.pk == new.pk)
            internal.calculation.trace['simulated_caller_pollution'] = True
            cache['simulated_dependent_approval'] = True
            with patch.object(self.correction, '_relationship', wraps=self.correction._relationship) as spy:
                self.assertEqual(self.read(new, cache), expected)
                self.assertEqual(spy.call_count, 1)
            self.assertNotIn('simulated_dependent_approval', cache)
        self.assertEqual(self.f.full_database_snapshot(), frozen)


class RouteCompositionReadCacheTests(TestCase):
    def setUp(self):
        # Borrow only the native fixture helpers inside this already isolated
        # route runner; no successful proof or service result is substituted.
        with patch.dict(os.environ, {'PCE_CONTRIBUTION_COMPOSITION_ISOLATED_TESTS': '1'}):
            from .tests_operation_contribution_composition import OperationContributionCompositionTests
        self.case = OperationContributionCompositionTests(methodName='runTest')
        self.case.setUp()
        self.f, self.plan = self.case.f, self.case.plan
        permission, _ = Permission.objects.get_or_create(code=service.RULE_VIEW,
            defaults={'name': service.RULE_VIEW, 'module': 'PRODUCTION'})
        RolePermission.objects.get_or_create(role=self.f.role, permission=permission)
        self.declaration = self.case.configure()
        self.case.save_group()
        self.step = {'stepId': self.f.step.pk, 'operationId': self.f.op_area.pk}

    def test_saved_workload_is_not_counted_twice_and_new_contribution_excess_is_rejected(self):
        row = ProductionPlanOperationRequirementAllocation.objects.filter(
            production_plan=self.plan).select_related('operation_requirement', 'production_plan', 'routing_step').first()
        self.assertEqual(row.operation_requirement.quantity_basis, 'SOURCE_SCOPE_TOTAL')
        self.assertEqual(row.allocated_quantity, row.operation_requirement.workload_quantity)
        entry = {'req': row.operation_requirement, 'plan': row.production_plan,
            'step': row.routing_step, 'workload': row.allocated_quantity}
        before = self.f.full_database_snapshot()
        native._contribution_workload_budget(entry, self.f.company.pk)
        proposed_step = deepcopy(row.routing_step)
        proposed_step.pk += 100000  # A distinct simulated proposal, never persisted.
        with self.assertRaises(native.OperationRequirementError) as caught:
            native._contribution_workload_budget({**entry, 'step': proposed_step}, self.f.company.pk)
        self.assertEqual(caught.exception.code, 'ALLOCATION_REQUIREMENT_WORKLOAD_EXCEEDED')
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_route_coverage_reuses_only_same_call_member_publication_and_keeps_the_native_result(self):
        from . import daily_capacity_service as daily
        from . import manufacturing_rule_configuration as manufacturing
        original = daily._validated_demand_object_coverage
        received = []

        def observe(*args, **kwargs):
            received.append(kwargs.get('read_cache'))
            return original(*args, **kwargs)

        def without_forwarded_cache(*args, **kwargs):
            kwargs.pop('read_cache', None)
            return original(*args, **kwargs)

        before = self.f.full_database_snapshot()
        with patch.object(daily, '_validated_demand_object_coverage', side_effect=observe), \
                patch.object(manufacturing, 'publication_config_validation',
                    wraps=manufacturing.publication_config_validation) as publication:
            actual = service.read_route_overview(user=self.f.user,
                production_plan_id=self.plan.pk, include_workloads=True)
        self.assertTrue(received)
        self.assertTrue(all(isinstance(cache, native._ReadOnlyProofCache) for cache in received))
        self.assertEqual(len({id(cache) for cache in received}), 1)
        cached_calls = publication.call_count
        self.assertEqual(cached_calls, len(self.declaration.specification['allocationComposition']['memberRules']))
        with patch.object(daily, '_validated_demand_object_coverage', side_effect=without_forwarded_cache), \
                patch.object(manufacturing, 'publication_config_validation',
                    wraps=manufacturing.publication_config_validation) as publication:
            uncached = service.read_route_overview(user=self.f.user,
                production_plan_id=self.plan.pk, include_workloads=True)
        self.assertGreater(publication.call_count, cached_calls)
        self.assertEqual(actual, uncached)
        target = next(row for row in actual['rows'] if row['routingStepId'] == self.f.step.pk)
        self.assertEqual(target['savedAllocations']['quantity'], '4.500000')
        self.assertEqual(target['workloadReview']['allocationCount'], 2)
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_shared_member_metadata_never_replaces_per_allocation_scope_or_changed_audit(self):
        from . import daily_capacity_service as daily
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            demand = native.process_demand_for_plan(self.plan, self.f.output, self.f.item,
                self.step, company_id=self.f.company.pk, user=self.f.user, read_cache=cache)
            found = daily._validated_demand_object_coverage(self.plan, self.f.output, self.f.item,
                self.step, demand, company_id=self.f.company.pk, read_cache=cache)
            self.assertTrue(found['inputFactIds'])
            for field in ('productionPlanId', 'mainCalculationId', 'baselineId'):
                changed = deepcopy(demand)
                changed['contributions'][0]['objectCoverageProof']['scope'][field] += 100000
                with self.subTest(scope=field), self.assertRaises(daily.DailyCapacityError):
                    daily._validated_demand_object_coverage(self.plan, self.f.output, self.f.item,
                        self.step, changed, company_id=self.f.company.pk, read_cache=cache)
            changed = deepcopy(demand)
            changed['contributions'][0]['objectCoverageProof']['sourceHash'] = '0' * 64
            with self.assertRaises(daily.DailyCapacityError):
                daily._validated_demand_object_coverage(self.plan, self.f.output, self.f.item,
                    self.step, changed, company_id=self.f.company.pk, read_cache=cache)
            with self.assertRaises(daily.DailyCapacityError):
                daily._validated_demand_object_coverage(self.plan, self.f.output, self.f.item,
                    self.step, demand, company_id=self.f.company.pk + 100000, read_cache=cache)
            audit = OrganizationOperatingAuditRecord.objects.filter(target_type='EngineeringRuleDefinition',
                target_id=self.declaration.pk).order_by('pk').last()
            legal.PlanLegalExtensionAdmissionTests.raw(self, audit, 'after_snapshot', {})
            with self.assertRaises(daily.DailyCapacityError) as caught:
                daily._validated_demand_object_coverage(self.plan, self.f.output, self.f.item,
                    self.step, demand, company_id=self.f.company.pk, read_cache=cache)
            self.assertEqual(caught.exception.code, 'ALLOCATION_COMPOSITION_AUDIT_UNPROVEN')


class RouteWorkloadPresentationTests(SimpleTestCase):
    def row(self, *, quantity=None, formal='EXISTS', saved='SAVED', result='REQUIRED', **changes):
        value = {'sequence': 7, 'operationName': '模拟工序', 'applicability': {'result': result},
            'sourceConfiguration': {'sources': [{'ruleName': '模拟产品表面面积'}]},
            'formalRequirements': {'statusCode': formal, 'statusLabel': '原生需求状态',
                'items': [{'operationRequirementId': 8}], 'blockers': []},
            'savedAllocations': {'statusCode': saved, 'statusLabel': '原生保存状态',
                'items': [{'allocationId': 9}], 'quantity': quantity, 'uomLabel': '平方米', 'blockers': []},
            'capacitySemantics': {}, 'blockers': []}
        value.update(changes)
        return value

    def test_zero_null_unread_and_non_applicability_are_distinct_without_calculation(self):
        proof = {'statusCode': 'PROVEN', 'statusLabel': '已证明'}
        explicit = service._workload_row_review(self.row(quantity='0'), coverage=proof)
        self.assertEqual(explicit['savedQuantity'], '0')
        missing = service._workload_row_review(self.row(saved='MISSING'), coverage=proof)
        self.assertIsNone(missing['savedQuantity'])
        unread = service._workload_row_review(self.row(formal='NOT_READ', saved='NOT_READ'), coverage=proof)
        self.assertIsNone(unread['formalRequirementCount'])
        self.assertIsNone(unread['allocationCount'])
        excluded = service._workload_row_review(self.row(formal='NOT_APPLICABLE', saved='NOT_APPLICABLE',
            result='NOT_APPLICABLE'), coverage=proof)
        self.assertEqual(excluded['statusCode'], 'NOT_APPLICABLE')
        self.assertIsNone(excluded['allocationCount'])
        pending = service._workload_row_review(self.row(result='PENDING', formal='PENDING', saved='PENDING'), coverage=proof)
        self.assertEqual(pending['statusCode'], 'PENDING')

    def test_auxiliary_and_engineering_only_never_erase_native_missing_requirements(self):
        proof = {'statusCode': 'NOT_OBTAINED', 'statusLabel': '未取得'}
        row = self.row(formal='MISSING', saved='MISSING', capacityRole='AUXILIARY')
        before = deepcopy(row)
        value = service._workload_row_review(row, coverage=proof)
        self.assertEqual(row, before)
        self.assertEqual(value['statusCode'], 'BLOCKED')
        self.assertIn('配套', value['processingLabel'])
        row['engineeringOnly'] = True
        value = service._workload_row_review(row, coverage=proof)
        self.assertEqual(value['statusCode'], 'BLOCKED')
        self.assertEqual(value['blockers'], row['blockers'])
        self.assertIn('排除旧APS', value['processingLabel'])
        self.assertNotIn('未确认', value['processingLabel'])
        row.update(engineeringOnly=False, capacitySemantics={'valid': True, 'meaningCode': 'NON_QUANTIFIED'})
        value = service._workload_row_review(row, coverage=proof)
        self.assertIn('经过', value['processingLabel'])
        self.assertIn('不可定量', value['processingLabel'])
        self.assertEqual(value['statusCode'], 'BLOCKED')
        row.update(engineeringOnly=False, capacitySemantics={'preparationRulingOnly': True})
        value = service._workload_row_review(row, coverage=proof)
        self.assertIn('投产数量仍独立核验', value['processingLabel'])
        self.assertEqual(value['statusCode'], 'BLOCKED')
