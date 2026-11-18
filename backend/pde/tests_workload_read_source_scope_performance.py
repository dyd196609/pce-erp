"""SIMULATED_FOR_TEST: common source-scope proofs in one native atomic read.

All fixture writes and explicit faults use Django's disposable test database.
The measured readers run native source, object, output and routing validators.
"""

from contextlib import ExitStack
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from planning.models import ProductionPlan
from system.models import Company, OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition
from . import formal_engineering_continuation_service as continuation
from . import operation_requirement_service as operation
from . import tests_plan_legal_extension_admission as legal
from .engineering_calculation_service import EngineeringCalculationService
from .engineering_fact_extension_service import CONTRACT, EngineeringFactExtensionService
from .manufacturing_structure_service import ManufacturingStructureService
from .operation_requirement_correction_service import OperationRequirementCorrectionService
from .routing_step_applicability_service import RoutingStepApplicabilityResolver
from .models import (
    BOMVersion, EngineeringCalculationDetail, EngineeringCalculationRecord,
    EngineeringDerivedFact, EngineeringFactInput, EngineeringOperationRequirement,
    EngineeringRuleDefinition, OrderEngineeringBaseline, OrderEngineeringBaselineItem,
    ProductManufacturingOutput, ProductionPlanOperationRequirementAllocation,
    Routing, RoutingStep, RoutingVersion,
)


class WorkloadReadSourceScopePerformanceTests(TestCase):
    def setUp(self):
        self.fixture = legal.PlanLegalExtensionAdmissionTests(methodName='runTest')
        self.fixture.setUp()
        self.f, self.user = self.fixture.f, self.fixture.f.user
        # A real historical contract without routingContext exercises the
        # native fallback clean/resolver, rather than supplying a mock proof.
        rule = self.f.make_mapping(self.fixture.facts[0], self.f.op_area, self.f.area,
            mode=self.f.mode, capacity=self.f.capacity, dynamic_source_basis=True, release=False)
        rule.specification['manufacturing']['sourceSelector']['traceEquals'] = {'contractVersion': CONTRACT}
        rule.save(update_fields=('specification',))
        self.f.advance(rule, 'reviewed')
        self.f.advance(rule, 'released')
        self.req_ids = []
        for fact in self.fixture.facts:
            generated = operation.OperationRequirementService.generate(user=self.user,
                source_calculation_id=self.fixture.extension.pk, source_fact_id=fact.pk,
                rule_id=rule.pk, idempotency_key=f'sim-source-scope-{fact.pk}', reason='SIMULATED_FOR_TEST')
            self.req_ids.append(generated['operationRequirementId'])

    def snapshot(self):
        models = (ProductionPlan, EngineeringCalculationRecord, EngineeringCalculationDetail,
            EngineeringDerivedFact, EngineeringFactInput, EngineeringOperationRequirement,
            EngineeringRuleDefinition, OrderEngineeringBaseline, OrderEngineeringBaselineItem,
            ProductManufacturingOutput, ProductionPlanOperationRequirementAllocation,
            Routing, RoutingStep, RoutingVersion, BOMVersion, OrganizationOperatingAuditRecord,
            BusinessStateTransition)
        return {model._meta.label: list(model.objects.order_by('pk').values()) for model in models}

    def readonly(self, action):
        before = self.snapshot()
        with ExitStack() as stack:
            for owner, name in ((operation.OperationRequirementService, 'generate'),
                    (operation.OperationRequirementService, 'allocate'),
                    (operation.OperationRequirementService, 'allocate_group'),
                    (OperationRequirementCorrectionService, 'correct'),
                    (EngineeringCalculationService, 'execute'),
                    (EngineeringFactExtensionService, 'derive'),
                    (EngineeringFactExtensionService, 'configure')):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError('Read invoked a business writer')))
            stack.enter_context(patch.object(operation, 'evaluate_specification',
                side_effect=AssertionError('Read reevaluated a formal result')))
            with CaptureQueriesContext(connection) as queries:
                result = action()
        self.assertEqual([row['sql'] for row in queries if row['sql'].lstrip().split()[0].upper()
            in {'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'}], [])
        self.assertEqual(self.snapshot(), before)
        return result

    def loaded(self):
        plan = ProductionPlan.objects.select_related(
            'planning_requirement__demand__sales_order_item__sales_order',
            'planning_requirement__demand__manufacturing_output__routing_version__routing',
            'planning_requirement__demand__manufacturing_output__order_engineering_baseline',
            'planning_requirement__demand__manufacturing_output__order_engineering_instance',
            'planning_requirement__demand__manufacturing_output__engineering_document_version',
            'planning_requirement__demand__manufacturing_output__bom_version').get(pk=self.fixture.plan.pk)
        reqs = list(EngineeringOperationRequirement.objects.filter(pk__in=self.req_ids).select_related(
            'calculation', 'source_detail__rule', 'audit_record').order_by('source_fact_id'))
        step = RoutingStep.objects.select_related('routing_version', 'operation').get(pk=self.f.step.pk)
        return plan, reqs, step

    def measured_proofs(self, typed):
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.user) if typed else {}
            plan, reqs, step = self.loaded()
            contexts = [operation._validate_requirement(req, self.user.company_id, read_cache=cache) for req in reqs]
            self.assertTrue(all('routingContext' not in context['source_snapshot']['manufacturing']
                for context in contexts))
            output = plan.planning_requirement.demand.manufacturing_output
            with patch.object(continuation, '_baseline_reference', wraps=continuation._baseline_reference) as baseline, \
                 patch.object(output, 'clean', wraps=output.clean) as clean, \
                 patch.object(ManufacturingStructureService, 'resolve_effective_routing',
                    wraps=ManufacturingStructureService.resolve_effective_routing) as routing, \
                 patch.object(RoutingStepApplicabilityResolver, 'resolve',
                    wraps=RoutingStepApplicabilityResolver.resolve) as applicability:
                rounds = [[operation._plan_source_consistency(self.user.company_id, plan, req,
                    native_context=context, routing_step=step, read_cache=cache)
                    for req, context in zip(reqs, contexts)] for _ in range(2)]
                counts = (baseline.call_count, clean.call_count, routing.call_count, applicability.call_count)
            return rounds, counts

    def test_three_objects_share_only_successful_common_scope_proofs(self):
        uncached, ordinary_counts = self.readonly(lambda: self.measured_proofs(False))
        cached, typed_counts = self.readonly(lambda: self.measured_proofs(True))
        self.assertEqual(cached, uncached)
        self.assertEqual(cached[0], cached[1])
        self.assertEqual(typed_counts, (1, 1, 1, 1))
        self.assertEqual(ordinary_counts, (3, 6, 6, 6))
        self.assertEqual(len({tuple(row['designItemIds']) for row in cached[0]}), 3)
        self.assertTrue(all(len(row['baselineItemIds']) == 1 for row in cached[0]))

    def test_object_source_hash_and_step_checks_remain_after_common_cache_hit(self):
        def read():
            with transaction.atomic():
                cache = operation._ReadOnlyProofCache(self.user)
                plan, reqs, step = self.loaded()
                contexts = [operation._validate_requirement(req, self.user.company_id, read_cache=cache) for req in reqs]
                operation._plan_source_consistency(self.user.company_id, plan, reqs[0],
                    native_context=contexts[0], routing_step=step, read_cache=cache)
                fact = contexts[1]['fact']
                trace = fact.trace
                group = trace.get('group') if isinstance(trace.get('group'), dict) else {}
                design_ids = {value for value in (trace.get('designItemId'), group.get('designItemId'))
                    if value is not None}
                self.assertEqual(len(design_ids), 1, 'Fixture must declare one exact current object')
                wrong_design_id = next(item.design_item_id for item in self.f.baseline_items
                    if item.design_item_id not in design_ids)
                self.assertNotIn(wrong_design_id, design_ids)
                fact.trace = {**trace, 'designItemId': wrong_design_id}
                self.assertNotEqual(fact.trace['designItemId'], next(iter(design_ids)))
                with self.assertRaises(operation.OperationRequirementError):
                    operation._plan_source_consistency(self.user.company_id, plan, reqs[1],
                        native_context=contexts[1], routing_step=step, read_cache=cache)
                fact.trace = trace
                original_hash = reqs[0].source_hash
                reqs[0].source_hash = '0' * 64
                with self.assertRaises(operation.OperationRequirementError) as error:
                    operation._plan_source_consistency(self.user.company_id, plan, reqs[0],
                        native_context=contexts[0], routing_step=step, read_cache=cache)
                self.assertEqual(error.exception.code, 'ALLOCATION_SOURCE_MISMATCH')
                reqs[0].source_hash = original_hash
                wrong_step = RoutingStep.objects.get(pk=self.f.wrong_step.pk)
                with self.assertRaises(operation.OperationRequirementError) as error:
                    operation._plan_source_consistency(self.user.company_id, plan, reqs[0],
                        native_context=contexts[0], routing_step=wrong_step, read_cache=cache)
                self.assertEqual(error.exception.code, 'ALLOCATION_STEP_MISMATCH')
        self.readonly(read)

    def new_scope_proof(self):
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.user)
            plan, reqs, step = self.loaded()
            return operation._plan_source_consistency(self.user.company_id, plan, reqs[0],
                routing_step=step, read_cache=cache)

    def test_new_atomic_read_rechecks_baseline_route_bom_source_and_inputs(self):
        self.readonly(self.new_scope_proof)
        source_link = EngineeringFactInput.objects.filter(fact=self.fixture.facts[0]).first()
        faults = ((self.f.baseline, 'snapshot_hash', '0' * 64),
            (self.f.version, 'status', 'draft'), (self.f.bom_version, 'status', 'draft'),
            (self.f.source_calc, 'result_hash', '0' * 64),
            (self.fixture.facts[0], 'trace', {**self.fixture.facts[0].trace,
                'designItemId': self.f.baseline_items[1].design_item_id}),
            (source_link, 'source_hash', '0' * 64))
        for obj, field, value in faults:
            with self.subTest(model=type(obj).__name__, field=field), transaction.atomic():
                self.fixture.raw(obj, field, value)
                def rejected():
                    with self.assertRaises(operation.OperationRequirementError):
                        self.new_scope_proof()
                self.readonly(rejected)
                transaction.set_rollback(True)

    def test_failed_baseline_and_route_loaders_are_never_memoized(self):
        def read():
            with transaction.atomic():
                plan, reqs, step = self.loaded()
                cache = operation._ReadOnlyProofCache(self.user)
                context = operation._validate_requirement(reqs[0], self.user.company_id, read_cache=cache)
                output = plan.planning_requirement.demand.manufacturing_output
                baseline = output.order_engineering_baseline
                original_hash = baseline.snapshot_hash
                baseline.snapshot_hash = '0' * 64
                with patch.object(continuation, '_baseline_reference', wraps=continuation._baseline_reference) as proof:
                    for _ in range(2):
                        with self.assertRaises(operation.OperationRequirementError):
                            operation._extension_object_coverage(self.user.company_id, context['origin'].origin_calculation,
                                context['origin'], context['fact'], output, read_cache=cache)
                    self.assertEqual(proof.call_count, 2)
                self.assertFalse(any(key[0] == 'coverage_baseline_objects' for key in cache))
                baseline.snapshot_hash = original_hash
                output.bom_version.status = 'draft'
                with patch.object(output, 'clean', wraps=output.clean) as clean:
                    for _ in range(2):
                        with self.assertRaises(operation.OperationRequirementError):
                            operation._plan_source_consistency(self.user.company_id, plan, reqs[0],
                                native_context=context, routing_step=step, read_cache=cache)
                    self.assertEqual(clean.call_count, 2)
                self.assertFalse(any(key[0] == 'plan_source_route' for key in cache))
        self.readonly(read)


    def test_scope_key_reuses_only_full_value_hash_math_without_sql(self):
        from . import operation_workload_source_service as workload
        with transaction.atomic():
            cache = operation._ReadOnlyProofCache(self.user)
            context = workload._scope_context(self.user, self.fixture.plan.pk, self.f.step.pk,
                _read_cache=cache)
            expected = workload._scope_proof_key(self.user, context)
            workload._scope_proof_key(self.user, context, read_cache=cache)
            with CaptureQueriesContext(connection) as queries, patch.object(operation, '_digest',
                    wraps=operation._digest) as digest:
                actual = workload._scope_proof_key(self.user, context, read_cache=cache)
            self.assertEqual(actual, expected)
            self.assertEqual(digest.call_count, 2)  # Applicability and source JSON still rechecked.
            self.assertEqual(len(queries), 0)


class CompleteModelHashMemoTests(TestCase):
    """SIMULATED_FOR_TEST: pure hash math, never a business eligibility proof."""

    def setUp(self):
        self.company = Company.objects.create(code='SIM-HASH-MEMO', name='SIMULATED_FOR_TEST hash scope')
        self.user = User(pk=900001, username='sim-hash-memo', company_id=self.company.pk, is_active=True)
        self.row = EngineeringCalculationRecord(pk=900002, company_id=self.company.pk,
            calculation_no='SIM-HASH-ROW', revision=1, input_hash='a' * 64,
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
            trace={'nested': {'number': 1, 'flag': True, 'decimal': 1.0, 'zero': -0.0},
                'list': [1, {'value': 'unchanged'}], 'keys': {'keep': 'value', 'remove': 'value'}})

    def test_same_full_values_and_independent_same_pk_instances_share_only_original_sha(self):
        cache = operation._ReadOnlyProofCache(self.user)
        same = deepcopy(self.row)
        shared = {'values': [1, 2, 3]}
        self.row.trace['aliases'] = [shared, shared]
        same.trace['aliases'] = [deepcopy(shared), deepcopy(shared)]
        expected = operation._proof_record_hash(self.row)
        changes = connection.connection.total_changes
        with CaptureQueriesContext(connection) as queries, patch.object(operation, '_digest',
                wraps=operation._digest) as digest:
            self.assertEqual(operation._proof_record_hash(self.row, read_cache=cache), expected)
            self.assertEqual(operation._proof_record_hash(self.row, read_cache=cache), expected)
            self.assertEqual(operation._proof_record_hash(same, read_cache=cache), expected)
            self.assertEqual(digest.call_count, 1)
            self.assertIsNone(operation._proof_record_hash(None, read_cache=cache))
        self.assertEqual(len(queries), 0)
        self.assertEqual(connection.connection.total_changes, changes)

    def test_all_nested_types_and_concrete_fields_recompute_original_sha_after_mutation(self):
        cases = {
            'nested_number': lambda row: row.trace['nested'].update(number=2),
            'list_append': lambda row: row.trace['list'].append(3),
            'list_remove': lambda row: row.trace['list'].pop(),
            'list_nested_value': lambda row: row.trace['list'][1].update(value='changed'),
            'int_to_bool': lambda row: row.trace['nested'].update(number=True),
            'int_to_float': lambda row: row.trace['nested'].update(number=1.0),
            'bool_to_int': lambda row: row.trace['nested'].update(flag=1),
            'float_to_int': lambda row: row.trace['nested'].update(decimal=1),
            'signed_float_zero': lambda row: row.trace['nested'].update(zero=0.0),
            'dict_key_remove': lambda row: row.trace['keys'].pop('remove'),
            'concrete_text': lambda row: setattr(row, 'calculation_no', 'SIM-CHANGED'),
            'concrete_integer': lambda row: setattr(row, 'revision', row.revision + 1),
            'concrete_none': lambda row: setattr(row, 'input_hash', None),
            'concrete_datetime': lambda row: setattr(row, 'updated_at', row.updated_at + timedelta(seconds=1)),
        }
        changes = connection.connection.total_changes
        for name, edit in cases.items():
            with self.subTest(case=name):
                row, altered = deepcopy(self.row), deepcopy(self.row)
                original = operation._proof_record_hash(row)
                edit(altered)
                expected = operation._proof_record_hash(altered)
                self.assertNotEqual(original, expected)
                cache = operation._ReadOnlyProofCache(self.user)
                with CaptureQueriesContext(connection) as queries, patch.object(operation, '_digest',
                        wraps=operation._digest) as digest:
                    self.assertEqual(operation._proof_record_hash(row, read_cache=cache), original)
                    self.assertEqual(operation._proof_record_hash(row, read_cache=cache), original)
                    self.assertEqual(digest.call_count, 1)
                    edit(row)
                    self.assertEqual(operation._proof_record_hash(row, read_cache=cache), expected)
                    self.assertEqual(digest.call_count, 2)
                    self.assertEqual(operation._proof_record_hash(row, read_cache=cache), expected)
                    self.assertEqual(digest.call_count, 2)
                self.assertEqual(len(queries), 0)
        self.assertEqual(connection.connection.total_changes, changes)

    def test_unsupported_raw_value_preserves_native_canonical_exception_without_memo(self):
        row = deepcopy(self.row)
        row.trace['unsupported'] = Decimal('2')
        cache = operation._ReadOnlyProofCache(self.user)
        with CaptureQueriesContext(connection) as queries, patch.object(operation, '_digest',
                wraps=operation._digest) as digest:
            for supplied_cache in (None, {}, cache):
                for _ in range(2):
                    with self.assertRaises(TypeError):
                        operation._proof_record_hash(row, read_cache=supplied_cache)
            self.assertEqual(digest.call_count, 6)
        self.assertEqual(len(queries), 0)
        self.assertFalse(any(key[0] == 'concrete_record_hash' for key in cache))

    def test_dict_order_and_decimal_datetime_normalization_preserve_native_hash(self):
        cache = operation._ReadOnlyProofCache(self.user)
        original = operation._proof_record_hash(self.row)
        self.assertEqual(operation._proof_record_hash(self.row, read_cache=cache), original)
        self.row.trace = dict(reversed(list(self.row.trace.items())))
        self.assertEqual(operation._proof_record_hash(self.row, read_cache=cache), original)
        plan = ProductionPlan(pk=900003, plan_no='SIM-HASH-PLAN', planned_qty=Decimal('1.230000'),
            updated_at=datetime(2026, 10, 2, tzinfo=timezone.utc))
        for row in (self.row, plan):
            expected = operation._proof_record_hash(row)
            self.assertEqual(operation._proof_record_hash(row, read_cache=cache), expected)
            self.assertEqual(operation._proof_record_hash(deepcopy(row), read_cache=cache), expected)
        plan.planned_qty = Decimal('1.23')
        self.assertEqual(operation._proof_record_hash(plan, read_cache=cache), operation._proof_record_hash(plan))

    def test_plain_foreign_actor_company_and_connection_never_reuse_read_hash_memo(self):
        expected = operation._proof_record_hash(self.row)
        cache = operation._ReadOnlyProofCache(self.user)
        operation._proof_record_hash(self.row, read_cache=cache)
        for plain in (None, {}):
            with self.subTest(cache=type(plain).__name__), patch.object(operation, '_digest',
                    wraps=operation._digest) as digest:
                for _ in range(2):
                    self.assertEqual(operation._proof_record_hash(self.row, read_cache=plain), expected)
                self.assertEqual(digest.call_count, 2)
        other = User(pk=self.user.pk + 1, company_id=self.company.pk, is_active=True)
        operation._bind_current_actor(cache, other)
        with patch.object(operation, '_digest', wraps=operation._digest) as digest:
            for _ in range(2):
                self.assertEqual(operation._proof_record_hash(self.row, read_cache=cache), expected)
            self.assertEqual(digest.call_count, 2)
        foreign = User(pk=self.user.pk, company_id=self.company.pk + 1, is_active=True)
        foreign_cache = operation._ReadOnlyProofCache(foreign)
        with patch.object(operation, '_digest', wraps=operation._digest) as digest:
            for _ in range(2):
                self.assertEqual(operation._proof_record_hash(self.row, read_cache=foreign_cache), expected)
            self.assertEqual(digest.call_count, 2)
        local = operation._ReadOnlyProofCache(self.user)
        operation._proof_record_hash(self.row, read_cache=local)
        with patch.object(operation.transaction, 'get_connection', return_value=object()), \
                patch.object(operation, '_digest', wraps=operation._digest) as digest:
            self.assertEqual(operation._proof_record_hash(self.row, read_cache=local), expected)
            self.assertEqual(digest.call_count, 1)

    def test_atomic_write_epoch_and_business_date_changes_do_not_reuse_previous_math_memo(self):
        expected = operation._proof_record_hash(self.row)
        with transaction.atomic():
            ended = operation._ReadOnlyProofCache(self.user)
            operation._proof_record_hash(self.row, read_cache=ended)
        with patch.object(operation, '_digest', wraps=operation._digest) as digest:
            self.assertEqual(operation._proof_record_hash(self.row, read_cache=ended), expected)
            self.assertEqual(digest.call_count, 1)
        cache = operation._ReadOnlyProofCache(self.user)
        operation._proof_record_hash(self.row, read_cache=cache)
        Company.objects.create(code='SIM-HASH-EPOCH', name='SIMULATED_FOR_TEST same connection write')
        with patch.object(operation, '_digest', wraps=operation._digest) as digest:
            self.assertEqual(operation._proof_record_hash(self.row, read_cache=cache), expected)
            self.assertEqual(digest.call_count, 1)
        dated = operation._ReadOnlyProofCache(self.user)
        with patch.object(operation, '_digest', wraps=operation._digest) as digest:
            with patch.object(operation, '_today', return_value=date(2026, 10, 1)):
                self.assertEqual(operation._proof_record_hash(self.row, read_cache=dated), expected)
                self.assertEqual(operation._proof_record_hash(self.row, read_cache=dated), expected)
                self.assertEqual(digest.call_count, 1)
            with patch.object(operation, '_today', return_value=date(2026, 10, 2)):
                self.assertEqual(operation._proof_record_hash(self.row, read_cache=dated), expected)
                self.assertEqual(digest.call_count, 2)


class CapacityScopeRawReadCacheTests(TestCase):
    """Real governed capacity creation; only raw reads share the atomic cache."""

    def setUp(self):
        from . import tests_edge_banding_eor as fixtures
        self.fixture = fixtures.EdgeBandingEorTests(methodName='runTest')
        self.fixture.setUp()
        _, self.capacity = self.fixture.configure_resources()
        self.user = self.fixture.user

    def loaded_capacity(self):
        from .models import StandardCapacity
        return StandardCapacity.objects.select_related('operation', 'work_center', 'uom',
            'product_type__product_category', 'product_type__manufacturing_process_type').get(pk=self.capacity.pk)

    def raw_rows(self, cache):
        from .manufacturing_capacity_scope import CONTRACT
        entries = {key[7]: value for key, value in cache.items()
            if isinstance(key, tuple) and len(key) > 7 and key[0] == CONTRACT}
        return entries['ledgers'][0], entries['audit']

    @staticmethod
    def ledger_query_count(queries):
        return sum('FROM "masterdata_write_request"' in row['sql'] for row in queries)

    def test_native_scope_reuses_raw_ledger_and_audit_but_rechecks_both_physical_snapshots(self):
        from . import manufacturing_capacity_scope as scope
        capacity = self.loaded_capacity()
        expected = scope.capacity_usage_scope_proof(capacity)
        before, changes = self.fixture.all_snapshot(), connection.connection.total_changes
        cache = operation._ReadOnlyProofCache(self.user)
        with CaptureQueriesContext(connection) as queries, patch.object(scope, '_state_matches',
                wraps=scope._state_matches) as state:
            first = scope.capacity_usage_scope_proof(capacity, read_cache=cache)
            second = scope.capacity_usage_scope_proof(capacity, read_cache=cache)
        self.assertEqual(first, expected)
        self.assertEqual(second, expected)
        self.assertEqual(self.ledger_query_count(queries), 1)
        self.assertEqual(sum('FROM "system_organization_operating_audits"' in row['sql'] for row in queries), 1)
        self.assertEqual(state.call_count, 4)
        self.assertEqual(self.fixture.all_snapshot(), before)
        self.assertEqual(connection.connection.total_changes, changes)

    def test_cached_filter_identity_physical_and_authorization_pollution_is_rejected(self):
        from masterdata.models import MasterDataWriteRequest
        from . import manufacturing_capacity_scope as scope
        cases = {
            'ledger_status': lambda cap, ledger, audit: setattr(ledger, 'status', MasterDataWriteRequest.Status.RESERVED),
            'ledger_organization': lambda cap, ledger, audit: setattr(ledger, 'organization_id', cap.company_id + 1),
            'ledger_entity': lambda cap, ledger, audit: setattr(ledger, 'entity_type', 'wrong'),
            'ledger_action': lambda cap, ledger, audit: setattr(ledger, 'action_code', 'wrong'),
            'ledger_target': lambda cap, ledger, audit: setattr(ledger, 'target_entity_id', str(cap.pk + 1)),
            'audit_organization': lambda cap, ledger, audit: setattr(audit, 'organization_id', cap.company_id + 1),
            'audit_action': lambda cap, ledger, audit: setattr(audit, 'action_code', 'wrong'),
            'audit_target_type': lambda cap, ledger, audit: setattr(audit, 'target_type', 'wrong'),
            'audit_target_id': lambda cap, ledger, audit: setattr(audit, 'target_id', cap.pk + 1),
            'identity_mapping': lambda cap, ledger, audit: setattr(ledger.source_identity, 'mapping_status', 'wrong'),
            'identity_source_hash': lambda cap, ledger, audit: setattr(ledger.source_identity, 'source_fingerprint', 'f' * 64),
            'physical_quantity': lambda cap, ledger, audit: setattr(cap, 'quantity', cap.quantity + 1),
            'authorization': lambda cap, ledger, audit: audit.after_snapshot['authorization'].update(allowed=False),
            'actor_company': lambda cap, ledger, audit: setattr(audit.actor, 'company_id', cap.company_id + 1),
        }
        before, changes = self.fixture.all_snapshot(), connection.connection.total_changes
        for name, edit in cases.items():
            with self.subTest(case=name):
                capacity = self.loaded_capacity()
                cache = operation._ReadOnlyProofCache(self.user)
                self.assertTrue(scope.capacity_usage_scope_proof(capacity, read_cache=cache))
                ledger, audit = self.raw_rows(cache)
                edit(capacity, ledger, audit)
                with self.assertRaises(operation.OperationRequirementError) as caught:
                    scope.capacity_usage_scope_proof(capacity, read_cache=cache)
                self.assertEqual(caught.exception.code, scope.ERROR)
        self.assertEqual(self.fixture.all_snapshot(), before)
        self.assertEqual(connection.connection.total_changes, changes)

    def test_plain_actor_atomic_date_and_same_connection_write_do_not_reuse_raw_reads(self):
        from masterdata.models import MasterDataWriteRequest
        from . import manufacturing_capacity_scope as scope
        capacity = self.loaded_capacity()
        expected = scope.capacity_usage_scope_proof(capacity)
        for supplied in (None, {}):
            with self.subTest(cache=type(supplied).__name__), CaptureQueriesContext(connection) as queries:
                for _ in range(2):
                    self.assertEqual(scope.capacity_usage_scope_proof(capacity, read_cache=supplied), expected)
            self.assertEqual(self.ledger_query_count(queries), 2)
        cache = operation._ReadOnlyProofCache(self.user)
        scope.capacity_usage_scope_proof(capacity, read_cache=cache)
        operation._bind_current_actor(cache, User(pk=self.user.pk + 1000, company_id=self.user.company_id))
        with CaptureQueriesContext(connection) as queries:
            for _ in range(2):
                self.assertEqual(scope.capacity_usage_scope_proof(capacity, read_cache=cache), expected)
        self.assertEqual(self.ledger_query_count(queries), 2)
        with transaction.atomic():
            ended = operation._ReadOnlyProofCache(self.user)
            scope.capacity_usage_scope_proof(capacity, read_cache=ended)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(scope.capacity_usage_scope_proof(capacity, read_cache=ended), expected)
        self.assertEqual(self.ledger_query_count(queries), 1)
        dated = operation._ReadOnlyProofCache(self.user)
        with CaptureQueriesContext(connection) as queries:
            with patch.object(operation, '_today', return_value=date(2026, 10, 1)):
                self.assertEqual(scope.capacity_usage_scope_proof(capacity, read_cache=dated), expected)
            with patch.object(operation, '_today', return_value=date(2026, 10, 2)):
                self.assertEqual(scope.capacity_usage_scope_proof(capacity, read_cache=dated), expected)
        self.assertEqual(self.ledger_query_count(queries), 2)
        written = operation._ReadOnlyProofCache(self.user)
        proof = scope.capacity_usage_scope_proof(capacity, read_cache=written)
        MasterDataWriteRequest.objects.filter(pk=proof['writeRequestId']).update(status=MasterDataWriteRequest.Status.RESERVED)
        with self.assertRaises(operation.OperationRequirementError) as caught:
            scope.capacity_usage_scope_proof(capacity, read_cache=written)
        self.assertEqual(caught.exception.code, scope.ERROR)

