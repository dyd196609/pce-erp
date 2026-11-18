"""SIMULATED_FOR_TEST: equivalent, bounded, call-owned route raw reads.

The existing named isolated runner owns fixture construction and deliberate
fault injections. No successful source, permission, frozen proof or business
service result is substituted. The daily and original isolated databases are
not test targets; importing the borrowed fixture retains its runner guard.
"""
from copy import deepcopy
from unittest.mock import patch

from django.db import connection, transaction
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from system.models import Permission, RolePermission, User
from . import operation_requirement_service as native
from . import operation_workload_source_service as service
from . import tests_plan_legal_extension_admission as legal
from . import tests_route_workload_final_read as fixtures
from .models import (
    EngineeringDerivedFact, EngineeringOperationRequirement,
    EngineeringRuleDefinition, ProductionPlanOperationRequirementAllocation,
    RoutingStep,
)


class RouteReadBatchStabilityTests(TestCase):
    def setUp(self):
        # Borrow only construction; do not inherit or rediscover another suite.
        self.case = fixtures.RouteWorkloadFinalNativeTests(methodName='runTest')
        self.case.setUp()
        self.f, self.plan = self.case.f, self.case.plan
        self.company_id = self.f.company.pk
        self.expected_ids = list(ProductionPlanOperationRequirementAllocation.objects.filter(
            company_id=self.company_id, production_plan=self.plan).values_list('pk', flat=True))
        self.assertGreaterEqual(len(self.expected_ids), 3)
        self.requirement = EngineeringOperationRequirement.objects.select_related(
            'source_detail__rule', 'source_calculation').get(pk=self.case.case.fixture.requirements[0].pk)

    def raw_rows(self, cache, *, company_id=None, step_id=None):
        return native._read_allocation_rows(company_id or self.company_id,
            production_plan_id=self.plan.pk, routing_step_id=step_id, read_cache=cache)

    def readonly(self, action):
        before = self.f.full_database_snapshot()
        epoch = connection.connection.total_changes
        with CaptureQueriesContext(connection) as queries:
            value = action()
        self.assertEqual(before, self.f.full_database_snapshot())
        self.assertEqual(connection.connection.total_changes, epoch)
        self.assertFalse(any(row['sql'].lstrip().split()[0].upper() in {
            'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'
        } for row in queries), list(queries))
        return value, list(queries)

    def overview(self):
        return self.readonly(lambda: service.read_route_overview(user=self.f.user,
            production_plan_id=self.plan.pk, include_workloads=True))

    def normalized_read_times(self, result):
        """Normalize only declared assessment timestamps and their exact hashes.

        Validate each original digest before recomputing its timestamp-derived
        counterpart. Source/input/record/freeze/reference hashes are untouched;
        recursive equality below compares every other field and ordering.
        """
        value = deepcopy(result)
        no_date_rows = []
        for row in value['rows']:
            proof = row['noDateCapacity']
            original_hash = proof.pop('resultHash')
            self.assertEqual(original_hash, native._digest(proof))
            self.assertTrue(proof['assessedAt'])
            proof['assessedAt'] = '<same-request-assessment-time>'
            proof['resultHash'] = native._digest(proof)
            no_date_rows.append(proof)
        summary = value['noDateCapacitySummary']
        self.assertEqual(result['noDateCapacitySummary']['resultHash'],
            native._digest([row['noDateCapacity']['resultHash'] for row in result['rows']]))
        self.assertTrue(summary['assessedAt'])
        summary['assessedAt'] = '<same-request-assessment-time>'
        summary['resultHash'] = native._digest([row['resultHash'] for row in no_date_rows])
        self.assertEqual(result['workloadResultHash'], native._digest({
            'scope': result['scope'], 'rows': result['rows'],
            'planAllocationRead': result['planAllocationRead'],
            'readComplete': result['readComplete'], 'businessComplete': result['businessComplete']}))
        value['workloadResultHash'] = native._digest({
            'scope': value['scope'], 'rows': value['rows'],
            'planAllocationRead': value['planAllocationRead'],
            'readComplete': value['readComplete'], 'businessComplete': value['businessComplete']})
        return value

    def assert_complete_fixture_scope(self, result):
        version_id = self.plan.planning_requirement.demand.manufacturing_output.routing_version_id
        step_ids = list(RoutingStep.objects.filter(routing_version_id=version_id)
            .order_by('sequence', 'pk').values_list('pk', flat=True))
        self.assertEqual([row['routingStepId'] for row in result['rows']], step_ids)
        self.assertEqual(result['summary']['stepCount'], len(step_ids))
        self.assertEqual(result['summary']['allocationRecordCount'], len(self.expected_ids))
        self.assertEqual({item['allocationId'] for row in result['rows']
            for item in row['savedAllocations']['items']}, set(self.expected_ids))
        self.assertEqual(len(result['planAllocationRead']['allocations']), len(self.expected_ids))
        self.assertTrue(result['readComplete'])

    def test_typed_raw_plan_and_every_step_preserve_all_rows_without_repeat_sql(self):
        step_ids = list(RoutingStep.objects.filter(routing_version=self.f.version)
            .values_list('pk', flat=True))
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.f.user)
            first, queries = self.readonly(lambda: self.raw_rows(cache))
            self.assertTrue(queries)
            self.assertEqual([row.pk for row in first], self.expected_ids)
            with CaptureQueriesContext(connection) as repeated:
                second = self.raw_rows(cache)
                partitions = {pk: self.raw_rows(cache, step_id=pk) for pk in step_ids}
            self.assertEqual(list(repeated), [])
            self.assertEqual([id(row) for row in second], [id(row) for row in first])
            self.assertEqual({row.pk for rows in partitions.values() for row in rows}, set(self.expected_ids))
            for step_id, rows in partitions.items():
                self.assertEqual([row.pk for row in rows],
                    [row.pk for row in first if row.routing_step_id == step_id])
            # Raw FK/history reads are not a cached successful validation.
            self.assertFalse(any(isinstance(key, tuple) and key[0] == 'validated_requirement'
                for key in cache))
            self.assertFalse(cache.budget_proofs)
            self.assertFalse(cache.allocation_validation_cache)






    def test_source_context_private_protocol_guard_keeps_alias_equivalence_and_full_pollution_detection(self):
        from . import plan_step_context_service as step_context

        context = step_context._resolve_step_context(self.plan, self.f.step.pk,
            user=self.f.user, historical=True)
        # This tests only private full-value serialization on real ORM models;
        # the synthetic JSON is not a source-selection or publication proof.
        shared = {'values': [True, 1, 1.0], 'nested': {'unchanged': 'value'}}
        context['sourceProof'] = {'guardOnlyFixture': [shared, shared]}
        context['_sourceIntegrity'] = step_context._source_context_fingerprint(context)
        guard = step_context._SourceIntegrityFastGuard(context)
        self.assertTrue(guard.matches(context))
        self.assertIs(deepcopy(guard), guard)
        alias = deepcopy(context)
        alias['sourceProof']['guardOnlyFixture'][1] = deepcopy(alias['sourceProof']['guardOnlyFixture'][0])
        # Protocol2 compares values and must remain stable when equal JSON
        # projections have different alias/refcount layouts.
        self.assertEqual(step_context._source_context_fingerprint(alias), context['_sourceIntegrity'])
        self.assertTrue(guard.matches(alias))
        self.assertEqual(alias['sourceProof'], context['sourceProof'])
        mutations = (
            lambda value: value['sourceProof']['guardOnlyFixture'][0]['values'].__setitem__(0, 1),
            lambda value: value['sourceProof']['guardOnlyFixture'][0]['values'].__setitem__(1, 1.0),
            lambda value: value['sourceProof']['guardOnlyFixture'][0]['nested'].update(unchanged='changed'),
            lambda value: setattr(value['base'], 'input_hash', 'caller-model-pollution'),
        )
        for mutation in mutations:
            changed = deepcopy(context)
            mutation(changed)
            self.assertFalse(guard.matches(changed))
            self.assertNotEqual(step_context._source_context_fingerprint(changed), context['_sourceIntegrity'])

    def test_output_source_raw_fk_reuses_only_unloaded_relations_and_keeps_explicit_models(self):
        from . import plan_step_context_service as step_context
        from .models import ProductManufacturingOutput

        output_id = self.plan.planning_requirement.demand.manufacturing_output_id
        cache = native._ReadOnlyProofCache(self.f.user)
        output = ProductManufacturingOutput.objects.get(pk=output_id)
        first, _ = self.readonly(lambda: step_context._read_context_output_source(
            self.plan, output, 'engineering_calculation', read_cache=cache))
        self.assertNotIn('engineering_calculation', output._state.fields_cache)
        second_output = ProductManufacturingOutput.objects.get(pk=output_id)
        second, queries = self.readonly(lambda: step_context._read_context_output_source(
            self.plan, second_output, 'engineering_calculation', read_cache=cache))
        self.assertIs(first, second)
        self.assertEqual(queries, [])
        explicit = ProductManufacturingOutput.objects.select_related('engineering_calculation').get(pk=output_id)
        explicit_base = explicit.engineering_calculation
        explicit_base.input_hash = 'simulated-explicit-model-pollution'
        actual, queries = self.readonly(lambda: step_context._read_context_output_source(
            self.plan, explicit, 'engineering_calculation', read_cache=cache))
        self.assertIs(actual, explicit_base)
        self.assertEqual(actual.input_hash, 'simulated-explicit-model-pollution')
        self.assertEqual(queries, [])
        original = first.input_hash
        first.input_hash = 'simulated-cached-model-pollution'
        cache['simulated_dependent_approval'] = True
        clean, queries = self.readonly(lambda: step_context._read_context_output_source(
            self.plan, second_output, 'engineering_calculation', read_cache=cache))
        self.assertIsNot(clean, first)
        self.assertEqual(clean.input_hash, original)
        self.assertTrue(queries)
        self.assertNotIn('simulated_dependent_approval', cache)

    def test_step_raw_batch_keeps_all_current_historical_contexts_and_reads_each_set_once(self):
        from . import plan_step_context_service as step_context

        steps = list(RoutingStep.objects.filter(routing_version=self.f.version).order_by('sequence', 'pk'))
        self.assertGreaterEqual(len(steps), 2)

        def projected(cache):
            result = []
            for historical in (False, True):
                for step in steps:
                    context = step_context._resolve_step_context(self.plan, step.pk,
                        user=self.f.user, historical=historical, read_cache=cache)
                    result.append({'version': step_context.version_fact(context),
                        'models': {name: native._proof_record_hash(context[name]) for name in (
                            'plan', 'originalOutput', 'output', 'root_step', 'step', 'base', 'baseline', 'routing_version')},
                        'bindingProof': context['bindingProof'], 'sourceProof': context['sourceProof']})
            return result

        expected, old_queries = self.readonly(lambda: projected(None))
        cache = native._ReadOnlyProofCache(self.f.user)
        actual, new_queries = self.readonly(lambda: projected(cache))
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 2 * len(steps))
        for table in ('pde_routing_step', 'pde_plan_step_version_binding'):
            marker = 'FROM "' + table + '"'
            self.assertEqual(sum(marker in row['sql'] for row in new_queries), 1, table)
            self.assertGreater(sum(marker in row['sql'] for row in old_queries), 1, table)
        repeated, queries = self.readonly(lambda: projected(cache))
        self.assertEqual(repeated, expected)
        self.assertEqual(queries, [])

    def test_step_raw_batch_owner_boundaries_model_pollution_and_write_epoch(self):
        from . import plan_step_context_service as step_context

        def raw(cache):
            step = step_context._read_context_step(self.plan, self.f.step.pk, read_cache=cache)
            return step, step_context._read_context_bindings(self.plan, step, read_cache=cache)

        def unshared(cache):
            before = dict(cache)
            first, queries = self.readonly(lambda: raw(cache))
            second, repeated = self.readonly(lambda: raw(cache))
            self.assertEqual(first[0].pk, self.f.step.pk)
            self.assertEqual(second[0].pk, self.f.step.pk)
            self.assertEqual(first[1], second[1])
            self.assertIsNot(first[0], second[0])
            self.assertGreaterEqual(len(queries), 2)
            self.assertGreaterEqual(len(repeated), 2)
            self.assertEqual(dict(cache), before)

        unshared({'ordinary_write_cache': True})
        with transaction.atomic():
            foreign = native._ReadOnlyProofCache(User(pk=self.f.user.pk, company_id=self.company_id + 10000))
            unshared(foreign)
            actor = native._ReadOnlyProofCache(self.f.user)
            raw(actor)
            native._bind_current_actor(actor, User(pk=self.f.user.pk + 10000, company_id=self.company_id))
            unshared(actor)
            expired = native._ReadOnlyProofCache(self.f.user)
            raw(expired)
        unshared(expired)

        cache = native._ReadOnlyProofCache(self.f.user)
        (step, _), _ = self.readonly(lambda: raw(cache))
        original = deepcopy(step.operation_parameters)
        step.operation_parameters['simulatedCallerPollution'] = [True, 1, 1.0]
        cache['simulated_dependent_approval'] = True
        (clean, _), queries = self.readonly(lambda: raw(cache))
        self.assertIsNot(clean, step)
        self.assertEqual(clean.operation_parameters, original)
        self.assertGreaterEqual(len(queries), 2)
        self.assertNotIn('simulated_dependent_approval', cache)
        legal.PlanLegalExtensionAdmissionTests.raw(self, clean, 'is_active', False)
        (changed, _), queries = self.readonly(lambda: raw(cache))
        self.assertIsNot(changed, clean)
        self.assertFalse(changed.is_active)
        self.assertGreaterEqual(len(queries), 2)
        # Keep the existing consumer rejection; a raw route read cannot make
        # this deliberately invalid legacy step applicable or usable.
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            self.readonly(lambda: service._scope_context(self.f.user, self.plan.pk,
                self.f.step.pk, _read_cache=cache))
        self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_STEP_MISMATCH')

    def test_object_context_batch_is_field_and_hash_equivalent_to_each_native_projection(self):
        from . import routing_object_applicability_service as objects
        from . import operation_input_preparation_service as preparation

        cache = native._ReadOnlyProofCache(self.f.user)
        scope = objects._load_scope(self.plan.pk, self.f.step.pk, read_cache=cache)
        self.assertGreaterEqual(len(scope['objects']), 3)
        selection = objects.source_selection
        with patch.object(objects, 'source_selection', wraps=selection) as single_guard:
            expected, _ = self.readonly(lambda: [objects._context(scope, row) for row in scope['objects']])
        self.assertEqual(single_guard.call_count, len(scope['objects']))
        with patch.object(objects, 'source_selection', wraps=selection) as batch_guard:
            actual, _ = self.readonly(lambda: objects._contexts(scope, scope['objects']))
        self.assertEqual(batch_guard.call_count, 1)
        self.assertEqual(actual, expected)
        self.assertEqual(objects._hash(actual), objects._hash(expected))
        self.assertEqual({row['baselineItemId'] for row in actual}, {row.pk for row in scope['objects']})

        exact = {'companyId': self.company_id, 'productionPlanId': self.plan.pk,
            'manufacturingOutputId': scope['output'].pk, 'mainCalculationId': scope['base'].pk,
            'salesOrderItemId': scope['item'].pk, 'baselineId': scope['baseline'].pk,
            'routingVersionId': scope['output'].routing_version_id, 'routingStepId': scope['step'].pk,
            'operationId': scope['step'].operation_id, 'productTypeId': self.f.product_type.pk}
        # Compare the complete preparation context, complete coverage and their
        # original hashes; only the pure context projection changes shape.
        with patch.object(objects, '_contexts',
                side_effect=lambda context, rows: [objects._context(context, row) for row in rows]):
            old, _ = self.readonly(lambda: preparation._scope_impl(self.f.user, exact, read_cache=cache))
        current, _ = self.readonly(lambda: preparation._scope_impl(self.f.user, exact, read_cache=cache))
        for key in ('scope', 'coverage', 'context', 'context_hash', 'objects_hash'):
            self.assertEqual(current[key], old[key], key)

    def test_object_context_batch_has_no_cross_call_or_owner_cache(self):
        from . import routing_object_applicability_service as objects

        scope = objects._load_scope(self.plan.pk, self.f.step.pk)
        selection = objects.source_selection
        expected = objects._contexts(scope, scope['objects'])
        # This helper accepts no actor/cache and stores no scope. A new call
        # always rereads the current model values and runs its source guard.
        with patch.object(objects, 'source_selection', wraps=selection) as guard:
            self.assertEqual(objects._contexts(scope, scope['objects']), expected)
            previous = scope['base'].input_hash
            scope['base'].input_hash = 'f' * 64
            changed = objects._contexts(scope, scope['objects'])
            self.assertTrue(all(row['calculationInputHash'] == 'f' * 64 for row in changed))
            scope['base'].input_hash = previous
            self.assertEqual(objects._contexts(scope, scope['objects']), expected)
        self.assertEqual(guard.call_count, 3)
        self.assertNotEqual(changed, expected)
        changed[0]['objectContentHash'] = 'caller-only-change'
        self.assertEqual(objects._contexts(scope, scope['objects']), expected)

    def test_full_native_overview_equals_unshared_raw_reads_without_reducing_scope(self):
        original = native._read_allocation_rows

        def unshared(*args, **kwargs):
            # Change only raw reuse, never a validator or a successful result.
            kwargs['read_cache'] = None
            return original(*args, **kwargs)

        with patch.object(native, '_read_allocation_rows', side_effect=unshared), \
                patch.object(service, '_scope_row_batch', return_value=(None, None)):
            expected, old_queries = self.overview()
        actual, new_queries = self.overview()
        self.assert_complete_fixture_scope(expected)
        self.assert_complete_fixture_scope(actual)
        self.assertEqual(self.normalized_read_times(actual), self.normalized_read_times(expected))
        self.assertLess(len(new_queries), len(old_queries))
        self.assertEqual(actual['planAllocationRead']['blockers'], [])
        # The fixture's second operation really lacks allocation: equivalence
        # must retain this blocker instead of manufacturing whole-route PASS.
        self.assertFalse(actual['businessComplete'])
        self.assertFalse(actual['wholeRouteReady'])

    def source_row_scope(self):
        base, item = self.f.source_calc, self.f.item
        steps = list(RoutingStep.objects.filter(routing_version=self.f.version)
            .order_by('sequence', 'pk'))
        fields = {self.requirement.source_fact.canonical_field, self.f.facts[0].canonical_field}
        marker = ('route_requested_source_rows', self.company_id, self.plan.pk, base.pk, item.pk)
        requested = {'operations': tuple(sorted({row.operation_id for row in steps})),
            'fields': tuple(sorted(fields))}
        return base, item, steps, fields, marker, requested

    def test_route_scope_batches_all_requested_rows_and_partitions_without_repeat_sql(self):
        base, item, steps, fields, marker, requested = self.source_row_scope()
        expected_requirements = {step.pk: service._read_requirement_rows(
            self.company_id, self.plan, base, item, step, None) for step in steps}
        expected_candidates = {field: service._read_candidate_rows(
            self.company_id, self.plan, base, item, {field}, None) for field in fields}
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.f.user)
            cache[marker] = requested
            first, queries = self.readonly(lambda: (
                service._read_requirement_rows(self.company_id, self.plan, base, item, steps[0], cache),
                service._read_candidate_rows(self.company_id, self.plan, base, item, fields, cache)))
            self.assertTrue(queries)
            with CaptureQueriesContext(connection) as repeated:
                requirements = {step.pk: service._read_requirement_rows(
                    self.company_id, self.plan, base, item, step, cache) for step in steps}
                candidates = {field: service._read_candidate_rows(
                    self.company_id, self.plan, base, item, {field}, cache) for field in fields}
            self.assertEqual(list(repeated), [])
            for step_id, rows in requirements.items():
                self.assertEqual([native._proof_record_hash(row) for row in rows],
                    [native._proof_record_hash(row) for row in expected_requirements[step_id]])
            for field, rows in candidates.items():
                self.assertEqual([native._proof_record_hash(row) for row in rows],
                    [native._proof_record_hash(row) for row in expected_candidates[field]])
            self.assertEqual({row.pk for row in first[1]},
                {row.pk for rows in expected_candidates.values() for row in rows})
            self.assertGreaterEqual(sum(len(rows) for rows in requirements.values()), len(self.expected_ids))

    def test_route_scope_batch_rejects_foreign_plain_expired_owners_and_write_stale_rows(self):
        base, item, steps, fields, marker, requested = self.source_row_scope()

        def assert_no_reuse(cache):
            before = dict(cache)
            self.assertEqual(service._scope_row_batch(cache, self.company_id, self.plan, base, item),
                (None, None))
            with CaptureQueriesContext(connection) as queries:
                first = service._read_candidate_rows(self.company_id, self.plan, base, item, fields, cache)
                second = service._read_candidate_rows(self.company_id, self.plan, base, item, fields, cache)
            self.assertTrue(queries)
            self.assertEqual([row.pk for row in first], [row.pk for row in second])
            self.assertTrue(first)
            self.assertIsNot(first[0], second[0])
            self.assertEqual(dict(cache), before)

        assert_no_reuse({marker: requested})
        with transaction.atomic():
            foreign = native._ReadOnlyProofCache(User(pk=self.f.user.pk,
                company_id=self.company_id + 10000))
            foreign[marker] = requested
            assert_no_reuse(foreign)
            actor = native._ReadOnlyProofCache(self.f.user)
            actor[marker] = requested
            native._bind_current_actor(actor, User(pk=self.f.user.pk + 10000, company_id=self.company_id))
            assert_no_reuse(actor)
            expired = native._ReadOnlyProofCache(self.f.user)
            expired[marker] = requested
        assert_no_reuse(expired)

        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.f.user)
            cache[marker] = requested
            old_rows = service._read_candidate_rows(self.company_id, self.plan, base, item, fields, cache)
            target = next(row for row in old_rows if row.pk == self.requirement.source_fact_id)
            legal.PlanLegalExtensionAdmissionTests.raw(self, target, 'status', 'inactive')
            current, queries = self.readonly(lambda: service._read_candidate_rows(
                self.company_id, self.plan, base, item, fields, cache))
            self.assertTrue(queries)
            self.assertNotIn(marker, cache)
            self.assertEqual({row.pk for row in current}, {row.pk for row in old_rows} - {target.pk})
            self.assertTrue(all(row.status == 'active' for row in current))

    def assert_uncached(self, cache, *, company_id=None, expected_ids=None):
        before = dict(cache)
        with CaptureQueriesContext(connection) as queries:
            first = self.raw_rows(cache, company_id=company_id)
            second = self.raw_rows(cache, company_id=company_id)
        self.assertTrue(queries)
        expected_ids = self.expected_ids if expected_ids is None else expected_ids
        self.assertEqual([row.pk for row in first], expected_ids)
        self.assertEqual([row.pk for row in second], expected_ids)
        if first:
            self.assertIsNot(first[0], second[0])
        self.assertEqual(dict(cache), before)
        with CaptureQueriesContext(connection) as prefetch:
            native._prefetch_generation_references(
                [self.requirement], company_id or self.company_id, cache)
        self.assertEqual(list(prefetch), [])
        self.assertEqual(dict(cache), before)

    def test_raw_helpers_refuse_plain_foreign_actor_company_and_expired_cache_reuse(self):
        self.assert_uncached({'simulated_write_cache': True})
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.f.user)
            self.raw_rows(cache)
            native._bind_current_actor(cache, User(pk=self.f.user.pk + 10000,
                company_id=self.company_id))
            self.assert_uncached(cache)
        with transaction.atomic():
            wrong_company = native._ReadOnlyProofCache(User(pk=self.f.user.pk,
                company_id=self.company_id + 10000))
            self.assert_uncached(wrong_company)
            valid = native._ReadOnlyProofCache(self.f.user)
            self.raw_rows(valid)
            self.assert_uncached(valid, company_id=self.company_id + 10000, expected_ids=[])
        with transaction.atomic():
            expired = native._ReadOnlyProofCache(self.f.user)
            self.raw_rows(expired)
        self.assertFalse(expired.is_current(self.company_id))
        self.assert_uncached(expired)

    def test_same_connection_write_discards_raw_rows_and_native_read_rejects_changed_allocation(self):
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.f.user)
            old_rows = self.raw_rows(cache)
            old = old_rows[0]
            legal.PlanLegalExtensionAdmissionTests.raw(self, old, 'input_hash', '0' * 64)
            fresh_rows, queries = self.readonly(lambda: self.raw_rows(cache))
            self.assertTrue(queries)
            self.assertEqual([row.pk for row in fresh_rows], self.expected_ids)
            fresh = next(row for row in fresh_rows if row.pk == old.pk)
            self.assertIsNot(fresh, old)
            self.assertEqual(fresh.input_hash, '0' * 64)
            self.assertNotEqual(old.input_hash, fresh.input_hash)
            result, _ = self.readonly(lambda: native.OperationRequirementService.read(user=self.f.user,
                production_plan_id=self.plan.pk, _read_cache=cache))
            self.assertFalse(result['passed'])
            self.assertTrue(any(row.get('allocationId') == old.pk
                and row['code'] == 'ALLOCATION_FACT_CHANGED' for row in result['blockers']), result)

    def test_raw_generation_prefetch_keeps_bad_fact_status_rule_and_old_allocation_rejections(self):
        target_id = ProductionPlanOperationRequirementAllocation.objects.get(
            production_plan=self.plan, operation_requirement=self.requirement).pk
        faults = (
            ('fact_value', {'FACT_EXTENSION_UNPROVEN'}),
            ('fact_status', {'SOURCE_FACT_MISMATCH'}),
            ('rule_status', {'OPERATION_RULE_MAPPING_MISSING'}),
            ('old_allocation_hash', {'ALLOCATION_FACT_CHANGED'}),
        )
        for fault, codes in faults:
            with self.subTest(fault=fault), transaction.atomic():
                req = EngineeringOperationRequirement.objects.select_related('source_detail').get(
                    pk=self.requirement.pk)
                if fault.startswith('fact_'):
                    obj = EngineeringDerivedFact.objects.get(pk=req.source_fact_id)
                    field, value = (('status', 'inactive') if fault == 'fact_status'
                        else ('value', {'decimal': '999999'}))
                elif fault == 'rule_status':
                    obj = EngineeringRuleDefinition.objects.get(pk=req.source_detail.rule_id)
                    field, value = 'status', 'draft'
                else:
                    obj = ProductionPlanOperationRequirementAllocation.objects.get(pk=target_id)
                    field, value = 'input_hash', '0' * 64
                # Deliberately invalid isolated fixture; never a product write.
                legal.PlanLegalExtensionAdmissionTests.raw(self, obj, field, value)
                cache = native._ReadOnlyProofCache(self.f.user)
                self.raw_rows(cache)
                result, _ = self.readonly(lambda: native.OperationRequirementService.read(user=self.f.user,
                    production_plan_id=self.plan.pk, _read_cache=cache))
                self.assertFalse(result['passed'])
                self.assertEqual(result['resultCount'], len(self.expected_ids))
                self.assertTrue(any(row.get('allocationId') == target_id and row['code'] in codes
                    for row in result['blockers']), result)
                transaction.set_rollback(True)



class ConditionalRouteReadCacheTests(TestCase):
    def setUp(self):
        from . import conditional_execution_preparation as conditional
        from . import manufacturing_output_generation_service as output_service
        from . import operation_input_preparation_service as preparation
        from . import tests_conditional_execution_preparation as conditional_fixtures
        from . import tests_engineering_version_handoff_upstream as published_fixtures
        from .routing_step_applicability_service import RoutingStepApplicabilityResolver

        # The borrowed fixture's class override is not applied by a manual
        # setUp call, so establish exactly its existing scope and cleanups.
        self.enterContext(override_settings(
            PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=published_fixtures.SCOPE))
        self.case = conditional_fixtures.ConditionalExecutionPreparationTests(methodName='runTest')
        self.addCleanup(self.case.doCleanups)
        self.case.setUp()
        self.case.save()
        self.conditional, self.output_service, self.preparation = conditional, output_service, preparation
        self.resolver = RoutingStepApplicabilityResolver

    def resolve(self, cache=None):
        case = self.case
        return self.resolver.resolve(case.step, production_plan=case.plan,
            manufacturing_output=case.f.output, engineering_calculation=case.f.source_calc,
            engineering_document_version=case.f.output.engineering_document_version,
            order_engineering_instance=case.f.source_calc.engineering_instance,
            order_engineering_baseline=case.f.baseline, bom_version=case.f.output.bom_version,
            read_cache=cache)

    def readonly(self, callback):
        before = self.case.f.full_database_snapshot()
        epoch = connection.connection.total_changes
        with CaptureQueriesContext(connection) as queries:
            try:
                return callback()
            finally:
                self.assertEqual(connection.connection.total_changes, epoch)
                self.assertEqual(before, self.case.f.full_database_snapshot())
                self.assertFalse(any(row['sql'].lstrip().split()[0].upper() in {
                    'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'
                } for row in queries), list(queries))

    def test_conditional_resolver_matches_native_uncached_facts_and_reuses_only_saved_content(self):
        integrity = self.output_service._saved_output_content_integrity
        validate = self.output_service.validate_selected_output
        with patch.object(self.output_service, '_saved_output_content_integrity', wraps=integrity) as uncached:
            expected = self.readonly(lambda: [self.resolve(), self.resolve()])
        self.assertGreaterEqual(uncached.call_count, 2)
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.case.user)
            with patch.object(self.output_service, '_saved_output_content_integrity', wraps=integrity) as cached, \
                    patch.object(self.output_service, 'validate_selected_output', wraps=validate) as validation, \
                    patch.object(self.preparation, '_authorize', wraps=self.preparation._authorize) as authorization:
                actual = self.readonly(lambda: [self.resolve(cache), self.resolve(cache)])
            self.assertEqual(actual, expected)
            self.assertGreaterEqual(cached.call_count, 1)
            self.assertLess(cached.call_count, uncached.call_count)
            # Full native output validation and current preparation permission
            # still run on both calls; no whole conditional verdict is cached.
            self.assertGreaterEqual(validation.call_count, 2)
            self.assertGreaterEqual(sum(call.args[1] == self.preparation.VIEW
                for call in authorization.call_args_list), 2)
        for result in actual:
            self.assertTrue(result['formalPolicyValidated'])
            self.assertEqual(result['result'], 'PENDING')
            self.assertEqual(result['conditionalExecution']['triggerStatus'], 'WAITING_TRIGGER')

    def test_conditional_cache_keeps_current_permission_and_write_epoch_content_rejection(self):
        from .models import OrderEngineeringBaselineItem
        from .production_foundation_service import ProductionFoundationError

        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.case.user)
            self.readonly(lambda: self.resolve(cache))
            permission = Permission.objects.get(code=self.preparation.VIEW)
            deleted, _ = RolePermission.objects.filter(role=self.case.role, permission=permission).delete()
            self.assertGreater(deleted, 0)
            with self.assertRaises(self.preparation.OperationInputPreparationError):
                self.readonly(lambda: self.resolve(cache))
            self.assertFalse(any(isinstance(key, tuple) and key[0] == 'fixed_saved_output_content'
                for key in cache))
            transaction.set_rollback(True)

        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.case.user)
            integrity = self.output_service._saved_output_content_integrity
            with patch.object(self.output_service, '_saved_output_content_integrity', wraps=integrity) as validation:
                self.readonly(lambda: self.resolve(cache))
                before_calls = validation.call_count
                self.assertGreaterEqual(before_calls, 1)
                item = OrderEngineeringBaselineItem.objects.filter(baseline=self.case.f.baseline,
                    design_item__sales_order_item=self.case.f.item).first()
                self.assertIsNotNone(item)
                # Deliberate isolated corruption of a lower frozen dependency,
                # whose header anchor fields remain unchanged. The DB epoch
                # must evict the prior saved-content proof before revalidation.
                legal.PlanLegalExtensionAdmissionTests.raw(self, item, 'content_hash', '0' * 64)
                with self.assertRaises((ValidationError, ProductionFoundationError,
                        self.output_service.ManufacturingOutputError)):
                    self.readonly(lambda: self.resolve(cache))
                self.assertGreater(validation.call_count, before_calls)
                self.assertFalse(any(isinstance(key, tuple) and key[0] == 'fixed_saved_output_content'
                    for key in cache))


class StepBindingRawBatchTests(TestCase):
    """Existing binding fixture; its upstream/impact stubs remain explicit.

    The fixture's two document proof stubs and declared zero-allocation impact
    are unchanged. Native output/release, binding ledger/audit/state and every
    read-time binding proof run normally. This is not a business admission.
    """

    def setUp(self):
        from . import tests_plan_step_version_handoff as handoff
        from . import plan_step_context_service as step_context
        from .tests_classified_fact_eor import ClassifiedFactEorTests

        self.enterContext(override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=handoff.SCOPE))
        self.case = handoff.PlanStepVersionHandoffTests(methodName='runTest')
        self.addCleanup(self.case.doCleanups)
        self.case.setUp()
        self.step_context = step_context
        self.full_database_snapshot = lambda: ClassifiedFactEorTests.full_database_snapshot(self)
        with patch('pde.plan_step_version_handoff_service._impact', side_effect=self.case.impact):
            self.saved = self.case.activate()

    def readonly(self, callback):
        before, epoch = self.full_database_snapshot(), connection.connection.total_changes
        try:
            with CaptureQueriesContext(connection) as queries:
                result = callback()
        finally:
            self.assertEqual(epoch, connection.connection.total_changes)
            self.assertEqual(before, self.full_database_snapshot())
            self.assertFalse(any(row['sql'].lstrip().split()[0].upper() in {
                'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'
            } for row in queries), list(queries))
        return result, list(queries)

    def resolve(self, cache=None, **changes):
        return self.step_context._resolve_step_context(self.case.plan, self.case.old_step.pk,
            user=self.case.executor, read_cache=cache, **changes)

    def test_raw_binding_batch_keeps_fresh_native_proof_history_and_frozen_mismatch(self):
        old, _ = self.readonly(lambda: self.resolve())
        frozen = deepcopy(old['bindingProof'])
        cache = native._ReadOnlyProofCache(self.case.executor)
        binding_proof = self.step_context.binding_proof
        with patch.object(self.step_context, 'binding_proof', wraps=binding_proof) as proof:
            current, _ = self.readonly(lambda: self.resolve(cache))
            history, _ = self.readonly(lambda: self.resolve(cache, historical=True, frozen_proof=frozen))
            self.assertEqual(proof.call_count, 2)
            for result in (current, history):
                self.assertEqual(self.step_context.version_fact(result), self.step_context.version_fact(old))
                self.assertEqual(result['bindingProof'], frozen)
                self.assertEqual(result['sourceProof'], old['sourceProof'])
                self.assertEqual(result['binding'].pk, self.saved['bindingId'])
                self.assertEqual(result['step'].pk, self.case.target.pk)
                self.assertEqual(result['output'].pk, self.case.successor.pk)
            wrong = {**frozen, 'manufacturingOutputId': frozen['manufacturingOutputId'] + 10000}
            with self.assertRaises(self.step_context.PlanStepContextError) as caught:
                self.readonly(lambda: self.resolve(cache, historical=True, frozen_proof=wrong))
            self.assertEqual(caught.exception.code, 'STEP_VERSION_BINDING_CHANGED')
            self.assertEqual(proof.call_count, 3)
            # Historical reads without any frozen binding retain the original
            # plan output and must not consume or grant current binding proof.
            original, _ = self.readonly(lambda: self.resolve(cache, historical=True))
            self.assertIsNone(original['binding'])
            self.assertEqual(original['output'].pk, self.case.original.pk)
            self.assertEqual(proof.call_count, 3)

    def test_raw_binding_fk_pollution_cannot_hide_binding_and_bad_audit_or_tombstone_still_reject(self):
        from .models import PlanStepVersionBinding

        cache = native._ReadOnlyProofCache(self.case.executor)
        rows = self.step_context._read_context_bindings(self.case.plan, self.case.old_step, read_cache=cache)
        self.assertEqual([row.pk for row in rows], [self.saved['bindingId']])
        rows[0].root_step_id = self.case.target.pk
        cache['simulated_dependent_approval'] = True
        current, _ = self.readonly(lambda: self.resolve(cache))
        self.assertEqual(current['binding'].pk, self.saved['bindingId'])
        self.assertEqual(current['root_step'].pk, self.case.old_step.pk)
        self.assertNotIn('simulated_dependent_approval', cache)
        row = PlanStepVersionBinding.objects.get(pk=self.saved['bindingId'])
        legal.PlanLegalExtensionAdmissionTests.raw(self, row.audit_record, 'action_code', 'simulated.bad.audit')
        with self.assertRaises(self.step_context.PlanStepContextError) as caught:
            self.readonly(lambda: self.resolve(cache))
        self.assertEqual(caught.exception.code, 'STEP_VERSION_BINDING_UNPROVEN')
        # A non-active head is a tombstone even if a predecessor/original
        # output exists. Never convert it into absence or silently fall back.
        legal.PlanLegalExtensionAdmissionTests.raw(self, row, 'status', 'revoked')
        with self.assertRaises(self.step_context.PlanStepContextError) as caught:
            self.readonly(lambda: self.resolve(cache))
        self.assertEqual(caught.exception.code, 'STEP_VERSION_NOT_ACTIVE')


class MainProofRawRowsTests(TestCase):
    """Borrow only the small persisted-main fixture, never its RAM executor."""

    @classmethod
    def setUpTestData(cls):
        from .tests_engineering_calculation_continuation import EngineeringCalculationContinuationTests
        EngineeringCalculationContinuationTests.setUpTestData.__func__(cls)

    def setUp(self):
        from . import engineering_calculation_continuation_service as continuation
        from .models import EngineeringCalculationRecord
        from .tests_classified_fact_eor import ClassifiedFactEorTests
        self.continuation = continuation
        self.calc = EngineeringCalculationRecord.objects.get(pk=self.calculations[0].pk)
        self.full_database_snapshot = lambda: ClassifiedFactEorTests.full_database_snapshot(self)

    def readonly(self, callback):
        before, epoch = self.full_database_snapshot(), connection.connection.total_changes
        try:
            with CaptureQueriesContext(connection) as queries:
                result = callback()
        finally:
            self.assertEqual(epoch, connection.connection.total_changes)
            self.assertEqual(before, self.full_database_snapshot())
            self.assertFalse(any(row['sql'].lstrip().split()[0].upper() in {
                'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'
            } for row in queries), list(queries))
        return result, list(queries)

    def test_raw_main_rows_match_original_values_hashes_and_repeat_no_queries(self):
        expected, old = self.readonly(lambda: [self.continuation._main_proof(self.calc),
            self.continuation._main_proof(self.calc)])
        self.assertGreaterEqual(len(old), 8)
        cache = native._ReadOnlyProofCache(self.actor)
        first, queries = self.readonly(lambda: self.continuation._main_proof(self.calc, read_cache=cache))
        self.assertEqual(first, expected[0])
        self.assertLess(len(queries), len(old))
        second, repeated = self.readonly(lambda: self.continuation._main_proof(self.calc, read_cache=cache))
        self.assertEqual(second, expected[1])
        self.assertEqual(repeated, [])
        facts, details, typed = self.continuation._main_proof_rows(self.calc, read_cache=cache)
        self.assertTrue(typed)
        self.assertGreaterEqual(len(facts), 1)
        self.assertEqual([self.continuation._main_row_values(row) for row in sorted(facts, key=lambda row: row.pk)],
            list(self.calc.derived_facts.order_by('pk').values()))
        self.assertEqual([self.continuation._main_row_values(row) for row in sorted(details, key=lambda row: row.pk)],
            list(self.calc.details.order_by('pk').values()))
        self.assertEqual(first['factsHash'], self.continuation.digest(list(self.calc.derived_facts.order_by('pk').values())))
        self.assertEqual(first['detailsHash'], self.continuation.digest(list(self.calc.details.order_by('pk').values())))

    def test_raw_main_rows_refuse_plain_foreign_company_actor_and_expired_cache(self):
        expected = self.continuation._main_proof(self.calc)

        def unshared(cache):
            before = dict(cache)
            result, queries = self.readonly(lambda: [self.continuation._main_proof(self.calc, read_cache=cache),
                self.continuation._main_proof(self.calc, read_cache=cache)])
            self.assertEqual(result, [expected, expected])
            self.assertGreaterEqual(len(queries), 8)
            self.assertEqual(dict(cache), before)

        unshared({'ordinary_write_cache': True})
        with transaction.atomic():
            foreign = native._ReadOnlyProofCache(User(pk=self.actor.pk, company_id=self.company.pk + 10000))
            unshared(foreign)
            actor = native._ReadOnlyProofCache(self.actor)
            self.continuation._main_proof(self.calc, read_cache=actor)
            native._bind_current_actor(actor, User(pk=self.actor.pk + 10000, company_id=self.company.pk))
            unshared(actor)
            expired = native._ReadOnlyProofCache(self.actor)
            self.continuation._main_proof(self.calc, read_cache=expired)
        self.assertFalse(expired.is_current(self.company.pk))
        unshared(expired)

    def test_raw_main_rows_in_memory_pollution_reloads_and_write_epoch_rejects_bad_fact(self):
        expected = self.continuation._main_proof(self.calc)
        cache = native._ReadOnlyProofCache(self.actor)
        faults = (
            lambda facts, details: facts[0].trace.update(unitSnapshot='wrong'),
            lambda facts, details: facts[0].value.update(decimal='99999'),
            lambda facts, details: setattr(facts[0].uom, 'is_active', False),
            lambda facts, details: setattr(facts[0].source_detail.rule, 'rule_code', 'caller-change'),
            lambda facts, details: details[0].input_snapshot.update(callerChange=[True, 1, 1.0]),
        )
        for edit in faults:
            self.continuation._main_proof(self.calc, read_cache=cache)
            facts, details, typed = self.continuation._main_proof_rows(self.calc, read_cache=cache)
            self.assertTrue(typed)
            cache['simulated_dependent_approval'] = True
            edit(facts, details)
            actual, queries = self.readonly(lambda: self.continuation._main_proof(self.calc, read_cache=cache))
            self.assertEqual(actual, expected)
            self.assertGreaterEqual(len(queries), 2)
            self.assertNotIn('simulated_dependent_approval', cache)
        # The calc itself is an explicit native argument and must be checked
        # afresh rather than hidden by a raw-row cache or whole proof memo.
        self.calc.status = 'failed'
        with self.assertRaises(self.continuation.EngineeringCalculationContinuationError) as caught:
            self.readonly(lambda: self.continuation._main_proof(self.calc, read_cache=cache))
        self.assertEqual(caught.exception.code, 'CONTINUATION_PREVIOUS_MAIN_UNPROVEN')
        self.calc.refresh_from_db()
        self.continuation._main_proof(self.calc, read_cache=cache)
        fact = self.calc.derived_facts.first()
        legal.PlanLegalExtensionAdmissionTests.raw(self, fact, 'status', 'inactive')
        with self.assertRaises(self.continuation.EngineeringCalculationContinuationError) as caught:
            self.readonly(lambda: self.continuation._main_proof(self.calc, read_cache=cache))
        self.assertEqual(caught.exception.code, 'CONTINUATION_PREVIOUS_FACT_CHANGED')


class ReadValueEqualityTests(SimpleTestCase):

    def test_nested_comparison_keeps_boolean_integer_float_and_key_types_distinct(self):
        for left, right in ((True, 1), (1, 1.0), (False, 0), ({True: 'value'}, {1: 'value'})):
            with self.subTest(left=left, right=right):
                self.assertFalse(native._same_concrete_values({'nested': [left]}, {'nested': [right]}))
                self.assertFalse(native._same_concrete_values({'nested': [right]}, {'nested': [left]}))
        original = {'nested': [{'values': [True, 1, 1.0]}, {'same': None}]}
        copied = deepcopy(original)
        self.assertTrue(native._same_concrete_values(original, copied))
        copied['nested'][0]['values'][0] = 1
        self.assertFalse(native._same_concrete_values(original, copied))
        copied['nested'][0]['values'][0] = True
        self.assertTrue(native._same_concrete_values(original, copied))
        copied['nested'][0]['values'].append('changed')
        self.assertFalse(native._same_concrete_values(original, copied))
        # A reordered dictionary may conservatively miss; it cannot turn a
        # changed concrete fact into equality or change the canonical digest.
        reordered = {'b': 2, 'a': 1}
        self.assertFalse(native._same_concrete_values({'a': 1, 'b': 2}, reordered))
        self.assertEqual(native._digest({'a': 1, 'b': 2}), native._digest(reordered))
