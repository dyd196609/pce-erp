"""SIMULATED_FOR_TEST: native operation source configuration and exact-plan reads.

Only the parent's guarded disposable test database may execute these fixtures.
Sources, route release, EORs and audits are real native fixtures, not proof mocks.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from system.models import Company, Permission, Process, RolePermission, User
from workflow_runtime.models import BusinessStateTransition
from . import operation_requirement_service as native
from . import operation_workload_source_service as service
from . import tests_calc4_routing_correction as correction
from . import tests_no_date_allocated_capacity as fixture_module
from .engineering_fact_extension_service import CONTRACT as EXTENSION_CONTRACT
from .models import (EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringOperationRequirement,
    EngineeringRuleDefinition, ProductionPlanOperationRequirementAllocation, RoutingStep, RoutingVersion)


class OperationSourceSelectorTests(SimpleTestCase):
    def test_explicit_conditions_accept_only_authored_scalar_predicates(self):
        trace = {'类型': 'SIM_NEW', 'Count': 2, 'Flag': True, 'Optional': None, 'EmptyText': ''}
        validated = service._explicit_source_conditions(trace)
        self.assertEqual(validated, trace)
        self.assertIsNot(validated, trace)
        invalid = ({}, [], {'': 'x'}, {' key': 'x'}, {'key ': 'x'}, {'key\n': 'x'},
            {'key': []}, {'key': {}}, {'key': 1.5}, {'key': float('nan')})
        for trace in invalid:
            with self.subTest(trace=trace), self.assertRaises(service.OperationWorkloadSourceError) as caught:
                service._explicit_source_conditions(trace)
            self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_EXPLICIT_CONDITIONS_INVALID')

    def test_engineering_only_is_explicit_uniform_and_never_repairs_invalid_configuration(self):
        source = {'capacityUsageScope': {'usageScope': 'ENGINEERING_EOR_ONLY'}}
        valid = {'hasValidSourceConfiguration': True, 'sources': [source, deepcopy(source)]}
        self.assertTrue(service._engineering_only_configuration(valid))
        for config in ({'hasValidSourceConfiguration': False, 'sources': [source]},
                {'hasValidSourceConfiguration': True, 'sources': []},
                {'hasValidSourceConfiguration': True, 'sources': [source, {}]},
                {'hasValidSourceConfiguration': True, 'sources': [source,
                    {'capacityUsageScope': {'usageScope': 'PRODUCTION'}}]}):
            with self.subTest(config=config):
                self.assertFalse(service._engineering_only_configuration(config))

    def test_distinct_product_or_trace_or_step_scopes_do_not_conflict(self):
        first = {'ruleId': 1, 'productTypeId': 9, 'sourceSelector': {'canonicalField': 'A',
            'producerRuleId': 3, 'producerRuleVersion': 'V1', 'traceEquals': {'AreaType': 'one'}}}
        second = deepcopy(first)
        second['ruleId'] = 2
        self.assertTrue(service._overlap(first, second))
        second['sourceSelector']['traceEquals']['AreaType'] = 'two'
        self.assertFalse(service._overlap(first, second))
        second = deepcopy(first)
        second['productTypeId'] = 10
        self.assertFalse(service._overlap(first, second))
        second = deepcopy(first)
        first['routingContext'] = {'routingStepId': 12}
        second['routingContext'] = {'routingStepId': 13}
        self.assertFalse(service._overlap(first, second))

    def test_scope_restriction_is_pure_and_drops_only_provably_foreign_blockers(self):
        current = {'routingId': 10, 'routingVersionId': 20, 'routingStepId': 30}
        other = {'routingId': 10, 'routingVersionId': 21, 'routingStepId': 31}
        source = {'ruleId': 1, 'productTypeId': 9, 'sourceSelector': {'canonicalField': 'A'},
            'routingContext': current}
        projection = {'sources': [source, {**deepcopy(source), 'ruleId': 2, 'routingContext': other}],
            'legacyQuantityDriver': '', 'blockers': [{'code': 'OLD_INVALID', 'routingContext': other},
                {'code': 'WORKLOAD_SOURCE_RULE_AMBIGUOUS', 'rulePairs': [(1, 2)]}],
            'hasValidSourceConfiguration': False, 'statusCode': 'AMBIGUOUS'}
        restricted = service.restrict_operation_projection(projection, current)
        self.assertEqual(restricted['statusCode'], 'CONFIGURED')
        self.assertEqual([row['ruleId'] for row in restricted['sources']], [1])
        self.assertEqual(restricted['blockers'], [])
        self.assertEqual(len(projection['sources']), 2)
        projection['blockers'].append({'code': 'CURRENT_INVALID', 'routingContext': current})
        self.assertEqual(service.restrict_operation_projection(projection, current)['statusCode'], 'INVALID')


class RouteSourcePrecedenceTests(SimpleTestCase):
    scope = {'routingId': 11, 'routingVersionId': 21, 'routingStepId': 31}

    def source(self, rule_id, **changes):
        row = {'ruleId': rule_id, 'ruleCode': 'SIM-ONE-FAMILY', 'ruleVersion': 'V99',
            'operationId': 41, 'productTypeId': 51, 'uomId': 61,
            'quantityBasis': 'SOURCE_SCOPE_TOTAL', 'sourceScope': 'SALES_ORDER_ITEM',
            'quantityBasisContract': {'quantityBasis': 'SOURCE_SCOPE_TOTAL', 'sourceScope': 'SALES_ORDER_ITEM',
                'basisQuantitySource': 'SALES_ORDER_ITEM', 'basisUomSource': 'SALES_ORDER_ITEM'},
            'sourceSelector': {'canonicalField': 'SIM_AREA', 'producerRuleId': 71,
                'producerRuleVersion': 'V2', 'traceEquals': {'AreaType': 'VISIBLE'}},
            'manufacturingModeId': 81, 'manufacturingModeVersion': 'V1',
            'workCenterId': 91, 'standardCapacityId': 101, 'sourceExpression': 'area_quantity',
            'evaluationSemanticsHash': service._evaluation_semantics_hash({'expression': 'area_quantity'})}
        row.update(changes)
        return row

    def projection(self, *sources):
        return {'sources': list(sources), 'legacyQuantityDriver': '', 'blockers': []}

    def test_exact_step_overrides_only_identical_family_and_retains_fallback(self):
        fallback = self.source(1, sourceEvidence={'formalRouting': {'routingVersionId': 999}})
        exact = self.source(2, ruleVersion='V1', routingContext=self.scope)
        original = self.projection(fallback, exact)
        # SimpleTestCase itself forbids database queries; this pure projection
        # must remain usable without opening a connection.
        result = service.restrict_operation_projection(original, self.scope)
        repeated = service.restrict_operation_projection(result, self.scope)
        self.assertEqual(result['statusCode'], 'CONFIGURED')
        self.assertEqual([row['ruleId'] for row in result['sources']], [2])
        self.assertEqual([row['ruleId'] for row in result['overriddenSources']], [1])
        self.assertEqual(result['overriddenSources'][0]['overriddenByRuleIds'], [2])
        self.assertEqual([row['ruleId'] for row in repeated['overriddenSources']], [1])
        self.assertEqual(len(original['sources']), 2)
        other = {**self.scope, 'routingVersionId': 22, 'routingStepId': 32}
        inherited = service.restrict_operation_projection(original, other)
        self.assertEqual([row['ruleId'] for row in inherited['sources']], [1])
        self.assertEqual([row['ruleId'] for row in inherited['inheritedSources']], [1])

    def test_changed_contract_and_equal_precision_remain_ambiguous(self):
        fallback = self.source(1)
        faults = [{'workCenterId': 92}, {'standardCapacityId': 102}, {'uomId': 62},
            {'quantityBasis': 'PER_OBJECT'}, {'sourceExpression': 'area_quantity * 2'},
            {'capacityUsageScope': {'usageScope': 'ENGINEERING_EOR_ONLY'}},
            {'sourceSelector': {'canonicalField': 'ANOTHER_AREA'}}]
        for fault in faults:
            with self.subTest(fault=fault):
                exact = self.source(2, routingContext=self.scope, **fault)
                result = service.restrict_operation_projection(self.projection(fallback, exact), self.scope)
                self.assertEqual(result['statusCode'], 'AMBIGUOUS')
                self.assertEqual(len(result['sources']), 2)
                self.assertEqual(result['overriddenSources'], [])
        first = self.source(2, routingContext=self.scope)
        second = self.source(3, routingContext=self.scope)
        result = service.restrict_operation_projection(self.projection(first, second), self.scope)
        self.assertEqual(result['statusCode'], 'AMBIGUOUS')

    def test_other_families_and_different_fields_are_not_silently_deduplicated(self):
        original = self.source(1)
        other = self.source(2, ruleCode='SIM-ANOTHER-FAMILY', routingContext=self.scope)
        result = service.restrict_operation_projection(self.projection(original, other), self.scope)
        self.assertEqual(result['statusCode'], 'AMBIGUOUS')
        self.assertEqual(len(result['sources']), 2)
        other['sourceSelector']['canonicalField'] = 'ANOTHER_COMPONENT'
        result = service.restrict_operation_projection(self.projection(original, other), self.scope)
        self.assertEqual(len(result['sources']), 2)
        self.assertEqual(result['overriddenSources'], [])
        # Selector JSON equality must not accept bool in place of number.
        original['sourceSelector']['traceEquals'] = {'Flag': True}
        exact = deepcopy(original)
        exact.update(ruleId=3, routingContext=self.scope)
        exact['sourceSelector']['traceEquals'] = {'Flag': 1}
        result = service.restrict_operation_projection(self.projection(original, exact), self.scope)
        self.assertEqual(result['statusCode'], 'AMBIGUOUS')

    def test_new_write_guard_requires_independence_without_changing_legacy_projection(self):
        existing = self.source(1, routingContext=self.scope)
        candidate = self.source(None, ruleCode='SIM-NEW-FAMILY', routingContext=self.scope)
        for key, value in (('canonicalField', 'ANOTHER_AREA'), ('producerRuleId', 72),
                           ('producerRuleVersion', 'V3')):
            with self.subTest(selector=key):
                changed = deepcopy(candidate)
                changed['sourceSelector'][key] = value
                # Historical readers retain their original multi-source
                # behavior; only a new adapter write gets the stricter guard.
                self.assertFalse(service._overlap(changed, existing))
                result = service._new_source_independence_conflicts(changed, [existing, changed])
                self.assertEqual([row['code'] for row in result], ['WORKLOAD_SOURCE_INDEPENDENCE_UNPROVEN'])
                self.assertEqual(result[0]['ruleId'], existing['ruleId'])
                other_type = {**existing, 'productTypeId': 52}
                self.assertEqual(service._new_source_independence_conflicts(changed, [other_type, changed]), [])
                other_step = {**existing, 'routingContext': {**self.scope, 'routingStepId': 32}}
                self.assertEqual(service._new_source_independence_conflicts(changed, [other_step, changed]), [])
        # Native same-input mutually exclusive trace conditions are unchanged.
        candidate['sourceSelector']['traceEquals'] = {'AreaType': 'NON_VISIBLE'}
        self.assertFalse(service._overlap(candidate, existing))
        self.assertEqual(service._new_source_independence_conflicts(candidate, [existing, candidate]), [])
        exact = self.source(None, routingContext=self.scope)
        fallback = self.source(1)
        retained = service.restrict_operation_projection(self.projection(fallback, exact), self.scope)
        self.assertEqual([row['ruleId'] for row in retained['sources']], [None])
        self.assertEqual(service._new_source_independence_conflicts(retained['sources'][0], retained['sources']), [])

    def test_full_evaluation_semantics_differences_cannot_hide_a_fallback(self):
        spec = {'expression': 'area_quantity', 'decimalPrecision': 28, 'outputScale': 6,
            'roundingMode': 'ROUND_HALF_UP', 'inputs': [{'canonicalName': 'area_quantity'}],
            'outputs': [{'canonicalName': 'load'}], 'dependencies': [],
            'rulePackage': {'code': 'SIM-PACKAGE', 'version': 'V1'},
            'manufacturing': {'modeId': 81}}
        exact_spec = deepcopy(spec)
        exact_spec['rulePackage']['version'] = 'V2'
        exact_spec['sourceEvidence'] = {'reference': 'document only'}
        exact_spec['manufacturing']['routingContext'] = self.scope
        signature = service._evaluation_semantics_hash(spec)
        self.assertEqual(signature, service._evaluation_semantics_hash(exact_spec))
        fallback = self.source(1, evaluationSemanticsHash=signature)
        faults = {'decimalPrecision': 12, 'outputScale': 2, 'roundingMode': 'ROUND_DOWN',
            'dependencies': ['SIM-OTHER'], 'inputs': [{'canonicalName': 'different_input'}],
            'outputs': [{'canonicalName': 'different_output'}], 'newEvaluationOption': True}
        for key, value in faults.items():
            with self.subTest(field=key):
                changed = deepcopy(exact_spec)
                changed[key] = value
                exact = self.source(2, routingContext=self.scope,
                    evaluationSemanticsHash=service._evaluation_semantics_hash(changed))
                result = service.restrict_operation_projection(self.projection(fallback, exact), self.scope)
                self.assertEqual(result['statusCode'], 'AMBIGUOUS')
                self.assertEqual(result['overriddenSources'], [])
        exact = self.source(2, routingContext=self.scope)
        exact.pop('evaluationSemanticsHash')
        result = service.restrict_operation_projection(self.projection(fallback, exact), self.scope)
        self.assertEqual(result['statusCode'], 'AMBIGUOUS')
        self.assertEqual(result['overriddenSources'], [])


class OperationWorkloadSourceTests(TestCase):
    def setUp(self):
        original = correction.Calc4RoutingCorrectionTests.advance

        def add_target_before_release(fixture, obj, target, *, status_field='status'):
            if isinstance(obj, RoutingVersion) and target == 'reviewed':
                if not hasattr(fixture, 'source_target'):
                    fixture.source_target = Process.objects.create(company=fixture.company,
                        code='SIM-SOURCE-TARGET', name='Abstract separately configured operation',
                        workshop=fixture.workshop, work_center=fixture.center,
                        calculation_basis='area', calculation_uom=fixture.area, quantity_driver='legacy wording only')
                    fixture.source_capacity = fixture.make_capacity(fixture.source_target, fixture.area, 'SIM-SOURCE-CAP')
                step = RoutingStep.objects.create(routing_version=obj, sequence=2,
                    operation=fixture.source_target, operation_parameters={'applicability': {
                        'contractVersion': 'PCE-ROUTING-STEP-APPLICABILITY-V1.0', 'mode': 'MANDATORY'}})
                if obj.routing_version == 'SIM-V1':
                    fixture.source_step = step
                else:
                    fixture.source_other_step = step
            return original(fixture, obj, target, status_field=status_field)

        self.fixture = fixture_module.NoDateAllocatedCapacityPersistenceTests(methodName='runTest')
        with patch.object(correction.Calc4RoutingCorrectionTests, 'advance', add_target_before_release):
            self.fixture.setUp()
        self.f, self.plan = self.fixture.f, self.fixture.plan
        self.operation, self.step = self.f.source_target, self.f.source_step
        self.producer = self.fixture.fixture.facts[0].rule
        for code in (service.RULE_VIEW,):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code, 'module': 'PRODUCTION'})
            RolePermission.objects.get_or_create(role=self.f.role, permission=permission)

    def payload(self, **changes):
        payload = {'ruleCode': 'SIM-OPERATION-SOURCE', 'ruleName': 'Abstract formal operation source',
            'version': 'V1', 'effectiveFrom': date.today().isoformat(),
            'producerRuleId': self.producer.pk, 'modeId': self.f.mode.pk,
            'productTypeId': self.f.product_type.pk, 'workCenterId': self.f.center.pk,
            'standardCapacityId': self.f.source_capacity.pk,
            'traceEquals': {'contractVersion': EXTENSION_CONTRACT}}
        payload.update(changes)
        return payload

    def configure(self, **changes):
        return service.configure(user=self.f.user, operation_id=self.operation.pk,
            payload=self.payload(**changes), reason='SIMULATED_FOR_TEST source configuration')

    def read(self, *, user=None, step=None):
        before = self.f.full_database_snapshot()
        with (patch.object(native.OperationRequirementService, 'generate', side_effect=AssertionError('read must not generate')),
                patch.object(native.OperationRequirementService, 'generate_readiness', side_effect=AssertionError('read must not evaluate new EOR')),
                patch.object(native.OperationRequirementService, 'allocate', side_effect=AssertionError('read must not allocate'))):
            try:
                return service.read_for_plan(user=user or self.f.user, production_plan_id=self.plan.pk,
                    routing_step_id=(step or self.step).pk)
            finally:
                self.assertEqual(before, self.f.full_database_snapshot())

    def test_legacy_text_is_unbound_and_batch_projection_is_constant_query_count(self):
        before = self.f.full_database_snapshot()
        rows = [self.operation] * 33
        with CaptureQueriesContext(connection) as queries:
            projected = service.project_operation_sources(rows, self.f.company.pk)
        self.assertLessEqual(len(queries), 12)
        row = projected[self.operation.pk]
        self.assertEqual(row['statusCode'], 'LEGACY_UNBOUND')
        self.assertFalse(row['hasValidSourceConfiguration'])
        self.assertEqual(row['sources'], [])
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_native_configure_publishes_only_rule_and_audits_then_replays_without_writes(self):
        counts = tuple(model.objects.count() for model in (EngineeringOperationRequirement,
            ProductionPlanOperationRequirementAllocation, EngineeringCalculationRecord))
        result = self.configure()
        self.assertEqual(result['configuration']['statusCode'], 'CONFIGURED', result)
        rule_id = result['nativeResult']['rules'][0]['id']
        rule = EngineeringRuleDefinition.objects.get(pk=rule_id)
        self.assertEqual(rule.status, 'released')
        self.assertEqual(rule.specification['manufacturing']['modeId'], self.f.mode.pk)
        self.assertNotIn('modeCode', rule.specification['manufacturing'])
        self.assertEqual(BusinessStateTransition.objects.filter(object_type='EngineeringRuleDefinition', object_id=rule_id).count(), 3)
        self.assertEqual(counts, tuple(model.objects.count() for model in (EngineeringOperationRequirement,
            ProductionPlanOperationRequirementAllocation, EngineeringCalculationRecord)))
        before = self.f.full_database_snapshot()
        self.configure()
        self.assertEqual(before, self.f.full_database_snapshot())
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            self.configure(ruleName='Changed definition must not overwrite')
        self.assertEqual(caught.exception.code, 'MANUFACTURING_VERSION_CONFLICT')
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_catalog_has_formal_options_plan_steps_and_no_sensitive_user_select(self):
        before = self.f.full_database_snapshot()
        with CaptureQueriesContext(connection) as queries:
            result = service.catalog(user=self.f.user)
        self.assertTrue(result['configureAuthorization']['allowed'], result)
        self.assertIn(self.producer.pk, [row['id'] for row in result['producers']])
        plan = next(row for row in result['productionPlans'] if row['id'] == self.plan.pk)
        self.assertIn(self.step.pk, [row['id'] for row in plan['routingSteps']])
        self.assertFalse(any('password' in row['sql'].lower() for row in queries))
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_catalog_preserves_all_step_identities_and_formal_trace_options(self):
        configured = self.configure()
        result = service.catalog(user=self.f.user)
        plan = next(row for row in result['productionPlans'] if row['id'] == self.plan.pk)
        self.assertEqual({row['id'] for row in plan['allRoutingSteps'] if row['isActive']},
            {row['id'] for row in plan['routingSteps']})
        producer = next(row for row in result['producers'] if row['id'] == self.producer.pk)
        option, = [row for row in producer['traceOptions'] if row['productTypeId'] == self.f.product_type.pk]
        self.assertEqual(option['traceEquals'], self.payload()['traceEquals'])
        self.assertIn(configured['nativeResult']['rules'][0]['id'], option['sourceRuleIds'])
        self.assertTrue(option['key'].startswith('trace:'))
        # An omitted historical trace is resolved only because this exact
        # producer/version/product has one current formal condition.
        before = self.f.full_database_snapshot()
        same = self.configure(traceEquals={})
        self.assertEqual(same['nativeResult']['rules'], configured['nativeResult']['rules'])
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_explicit_conditions_publish_new_authored_selection_without_changing_catalog_defaults(self):
        original = self.configure()
        trace = {'contractVersion': 'SIM_NEW_CONDITION', 'Count': 2, 'Flag': True, 'Optional': None}
        before = self.f.full_database_snapshot()
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            self.configure(ruleCode='SIM-EXPLICIT-SOURCE', traceEquals=trace)
        self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_TRACE_SELECTION_REQUIRED')
        self.assertEqual(before, self.f.full_database_snapshot())
        result = self.configure(ruleCode='SIM-EXPLICIT-SOURCE', sourceSelectorMode='EXPLICIT_CONDITIONS',
            traceEquals=trace)
        rule = EngineeringRuleDefinition.objects.get(pk=result['nativeResult']['rules'][0]['id'])
        self.assertEqual(rule.specification['manufacturing']['sourceSelector']['traceEquals'], trace)
        self.assertNotIn('sourceSelectorMode', rule.specification['manufacturing'])
        baseline = EngineeringRuleDefinition.objects.get(pk=original['nativeResult']['rules'][0]['id'])
        self.assertEqual(baseline.specification['manufacturing']['sourceSelector']['traceEquals'],
            self.payload()['traceEquals'])
        before = self.f.full_database_snapshot()
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            self.configure(ruleCode='SIM-EXPLICIT-MIXED', sourceSelectorMode='EXPLICIT_CONDITIONS',
                sourceSelectorKey='trace:existing', traceEquals=trace)
        self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_TRACE_SCOPE_MISMATCH')
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_multiple_formal_trace_conditions_require_exact_selection(self):
        first = self.configure()
        original = EngineeringRuleDefinition.objects.get(pk=first['nativeResult']['rules'][0]['id'])
        spec = deepcopy(original.specification)
        spec['manufacturing']['sourceSelector']['traceEquals'] = {'AreaType': 'SIM_ANOTHER_CONDITION'}
        spec['manufacturing']['modeCode'] = self.f.mode.code
        spec['manufacturing'].pop('modeId')
        service.ManufacturingConfigurationService.configure(user=self.f.user, reason='SIMULATED_FOR_TEST',
            package={'contractVersion': service.MANUFACTURING_CONTRACT, 'companyId': self.f.company.pk,
                'modes': [], 'rules': [{'ruleCode': 'SIM-TRACE-ALTERNATIVE', 'ruleName': 'Formal alternative condition',
                    'version': 'V1', 'effectiveFrom': date.today().isoformat(), 'specification': spec}]})
        catalog = service.catalog(user=self.f.user)
        producer = next(row for row in catalog['producers'] if row['id'] == self.producer.pk)
        options = [row for row in producer['traceOptions'] if row['productTypeId'] == self.f.product_type.pk]
        self.assertEqual(len(options), 2)
        before = self.f.full_database_snapshot()
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            self.configure(ruleCode='SIM-TRACE-UNSELECTED', traceEquals={})
        self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_TRACE_SELECTION_REQUIRED')
        with self.assertRaises(service.OperationWorkloadSourceError):
            self.configure(ruleCode='SIM-TRACE-WRONG', sourceSelectorKey='trace:wrong')
        self.assertEqual(before, self.f.full_database_snapshot())
        selected = next(row for row in options if row['traceEquals'] == self.payload()['traceEquals'])
        replay = self.configure(traceEquals={}, sourceSelectorKey=selected['key'])
        self.assertEqual(replay['nativeResult']['rules'], first['nativeResult']['rules'])
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_source_candidates_requirements_and_saved_load_are_independent(self):
        self.configure()
        result = self.read()
        self.assertEqual(result['sourceCandidates']['statusCode'], 'AVAILABLE', result)
        self.assertEqual(len(result['sourceCandidates']['items']), 3)
        self.assertEqual(result['formalRequirements']['statusCode'], 'MISSING', result)
        self.assertEqual(result['savedAllocations']['statusCode'], 'MISSING', result)
        self.assertIsNone(result['savedAllocations']['quantity'])
        self.assertNotIn('quantity', result['sourceCandidates'])
        quantities = [Decimal(row['quantity']) for row in result['sourceCandidates']['items']]
        self.assertEqual(sum(quantities), Decimal('4'))
        self.assertTrue(all(row['objectCoverage']['baselineId'] == self.f.baseline.pk
            for row in result['sourceCandidates']['items']))
        self.assertFalse(result['newEorRuleEvaluated'])
        self.assertFalse(result['generated'])

    def test_same_scope_multiple_rules_are_ambiguous_never_first_selected(self):
        first = self.configure()
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            self.configure(ruleCode='SIM-OPERATION-SOURCE-SECOND')
        self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_RULE_AMBIGUOUS')
        # Existing formally published conflicts must still be visible; fixture
        # construction uses the original writer, not a mocked read result.
        rule = EngineeringRuleDefinition.objects.get(pk=first['nativeResult']['rules'][0]['id'])
        spec = deepcopy(rule.specification)
        spec['manufacturing']['modeCode'] = self.f.mode.code
        spec['manufacturing'].pop('modeId')
        service.ManufacturingConfigurationService.configure(user=self.f.user, reason='SIMULATED_FOR_TEST',
            package={'contractVersion': service.MANUFACTURING_CONTRACT, 'companyId': self.f.company.pk,
                'modes': [], 'rules': [{'ruleCode': 'SIM-OPERATION-SOURCE-SECOND', 'ruleName': 'Existing formal conflict',
                    'version': 'V1', 'effectiveFrom': date.today().isoformat(), 'specification': spec}]})
        result = self.read()
        self.assertEqual(result['sourceCandidates']['statusCode'], 'AMBIGUOUS', result)
        self.assertEqual(result['sourceCandidates']['items'], [])
        self.assertIsNone(result['savedAllocations']['quantity'])

    def test_native_saved_load_is_read_only_after_real_eor_generation_and_allocation(self):
        configured = self.configure()
        rule_id = configured['nativeResult']['rules'][0]['id']
        ids = []
        for fact in self.fixture.fixture.facts:
            result = native.OperationRequirementService.generate(user=self.f.user,
                source_calculation_id=fact.calculation_id, source_fact_id=fact.pk, rule_id=rule_id,
                idempotency_key=f'sim-workload-eor-{fact.pk}', reason='SIMULATED_FOR_TEST')
            ids.append(result['operationRequirementId'])
        native.OperationRequirementService.allocate_group(user=self.f.user, production_plan_id=self.plan.pk,
            contributions=[{'operationRequirementId': pk, 'routingStepId': self.step.pk,
                'idempotencyKey': f'sim-workload-allocation-{pk}'} for pk in ids], reason='SIMULATED_FOR_TEST')
        result = self.read()
        self.assertEqual(result['sourceCandidates']['statusCode'], 'AVAILABLE', result)
        self.assertEqual(result['formalRequirements']['statusCode'], 'EXISTS', result)
        self.assertEqual({row['id'] for row in result['formalRequirements']['items']}, set(ids))
        self.assertEqual(result['savedAllocations']['statusCode'], 'SAVED', result)
        self.assertEqual(Decimal(result['savedAllocations']['quantity']), Decimal('4'))
        self.assertEqual(len(result['savedAllocations']['items']), 3)
        self.assertEqual(result['savedAllocations']['uomLabel'], self.f.area.name)
        self.assertTrue(all(row['uomLabel'] == self.f.area.name for row in result['formalRequirements']['items']))
        self.assertFalse(result['allocationSaved'])  # This read performed no save.

    def test_new_request_revalidates_native_source_object_hash(self):
        self.configure()
        self.assertEqual(self.read()['sourceCandidates']['statusCode'], 'AVAILABLE')
        fact = self.fixture.fixture.facts[0]
        trace = deepcopy(fact.trace)
        trace['group']['baselineItemId'] = self.f.baseline_items[0].pk + 99999
        self.f.corrupt_json(fact, 'trace', trace)
        invalid = self.read()
        self.assertEqual(invalid['sourceCandidates']['statusCode'], 'INVALID', invalid)
        self.assertTrue(invalid['sourceCandidates']['blockers'])

    def test_company_uom_and_released_state_do_not_create_invalid_configuration(self):
        foreign = Company.objects.create(code='SIM-SOURCE-FOREIGN', name='SIM source foreign company')
        foreign_user = User.objects.create_user(username='sim_source_foreign', company_id=foreign.pk,
            is_staff=True, is_superuser=True)
        before = self.f.full_database_snapshot()
        with self.assertRaises(service.OperationWorkloadSourceError):
            service.configure(user=foreign_user, operation_id=self.operation.pk,
                payload=self.payload(), reason='SIMULATED_FOR_TEST')
        self.assertEqual(before, self.f.full_database_snapshot())
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            self.configure(producerRuleId=self.f.rule_area.pk)
        self.assertEqual(caught.exception.code, 'OPERATION_UOM_MISMATCH')
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            self.configure(canonicalField='not-the-formal-output')
        self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_PRODUCER_INVALID')
        source = service.read_for_plan(user=foreign_user, production_plan_id=self.plan.pk, routing_step_id=self.step.pk)
        self.assertEqual(source['scope'], {})
        self.assertTrue(source['blockers'])

    def test_superuser_permission_does_not_replace_employee_execution_chain(self):
        account = User.objects.create_user(username='sim_source_super_without_chain', company_id=self.f.company.pk,
            is_active=True, is_staff=True, is_superuser=True)
        result = service.catalog(user=account)
        self.assertTrue(result['configureAuthorization']['permissionAllowed'])
        self.assertFalse(result['configureAuthorization']['allowed'])
        self.assertEqual(result['configureAuthorization']['decisionCode'], 'FORMAL_EXECUTION_CHAIN_REQUIRED')
        before = self.f.full_database_snapshot()
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            service.configure(user=account, operation_id=self.operation.pk, payload=self.payload(), reason='SIMULATED_FOR_TEST')
        self.assertEqual(caught.exception.code, 'FORMAL_EXECUTION_CHAIN_REQUIRED')
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_original_legacy_eor_mapping_is_still_formal_without_manufacturing(self):
        legacy_op = Process.objects.create(company=self.f.company, code='SIM-SOURCE-LEGACY',
            name='Abstract unchanged legacy operation', calculation_basis='area', calculation_uom=self.f.area)
        legacy = self.f.make_rule(legacy_op, self.f.area, 'opaque_area')
        projected = service.operation_source_configuration(legacy_op, self.f.product_type.pk)
        self.assertTrue(projected['hasValidSourceConfiguration'], projected)
        self.assertEqual(projected['sources'][0]['ruleId'], legacy.pk)
        self.assertEqual(projected['sources'][0]['contractKind'], 'FORMAL_LEGACY_RULE')
        self.assertFalse(projected['sources'][0]['structuredMaintenanceSupported'])

    def test_future_or_expired_rule_is_not_a_current_source(self):
        with self.assertRaises(service.OperationWorkloadSourceError):
            self.configure(effectiveFrom=(date.today() + timedelta(days=1)).isoformat())
        configured = self.configure()
        rule = EngineeringRuleDefinition.objects.get(pk=configured['nativeResult']['rules'][0]['id'])
        self.f.advance(rule, 'obsolete')
        result = self.read()
        self.assertEqual(result['sourceConfiguration']['statusCode'], 'LEGACY_UNBOUND', result)
        self.assertEqual(result['sourceCandidates']['items'], [])
        self.assertIsNone(result['savedAllocations']['quantity'])

    def test_overlapping_extra_extension_output_is_rejected_without_selecting_a_first_fact(self):
        self.configure()
        fact = self.fixture.fixture.facts[0]
        values = {field.attname: deepcopy(getattr(fact, field.attname))
            for field in fact._meta.concrete_fields if not field.primary_key and field.name != 'created_at'}
        values.update(fact_code='SIM-DUPLICATE-OVERLAP', sequence=fact.sequence + 1000)
        # Deliberate disposable-fixture corruption: a fourth output is not in
        # the original native extension result/input/audit snapshot.
        EngineeringDerivedFact.objects.create(**values)
        result = self.read()
        self.assertEqual(result['sourceCandidates']['statusCode'], 'INVALID', result)
        self.assertTrue(result['sourceCandidates']['blockers'])
        self.assertIsNone(result['savedAllocations']['quantity'])

    def test_wrong_version_step_cannot_be_used_and_all_read_sql_avoids_password(self):
        self.configure()
        wrong = self.read(step=self.f.wrong_step)
        self.assertEqual(wrong['scope'], {})
        self.assertTrue(wrong['blockers'])
        with CaptureQueriesContext(connection) as queries:
            result = self.read()
        self.assertEqual(result['sourceCandidates']['statusCode'], 'AVAILABLE', result)
        self.assertFalse(any('password' in row['sql'].lower() for row in queries))

    def test_native_capacity_metadata_failure_does_not_count_as_configured(self):
        configured = self.configure()
        rule = EngineeringRuleDefinition.objects.get(pk=configured['nativeResult']['rules'][0]['id'])
        refs = service._references([rule], [self.operation], self.f.company.pk)
        capacity = refs['capacity'][self.f.source_capacity.pk]
        faults = [{'measurement_status': 'not_determinable', 'quantity': None},
            {'time_basis': 'week'}, {'time_basis_quantity': Decimal('7')},
            {'effective_from': None}, {'effective_to': date.today() - timedelta(days=1)}]
        for fault in faults:
            with self.subTest(fault=fault), patch.multiple(capacity, **fault):
                with self.assertRaises(service.OperationWorkloadSourceError):
                    service._summary(rule, self.operation, refs)
        with patch.object(refs['kind'][self.f.product_type.pk].product_category, 'is_active', False):
            with self.assertRaises(service.OperationWorkloadSourceError):
                service._summary(rule, self.operation, refs)
        with patch.object(refs['center'][self.f.center.pk].workshop, 'is_active', False):
            with self.assertRaises(service.OperationWorkloadSourceError):
                service._summary(rule, self.operation, refs)
        # A valid historical DB state can be active yet have no measured value.
        type(capacity).objects.filter(pk=capacity.pk).update(measurement_status='not_determinable', quantity=None)
        projected = service.operation_source_configuration(self.operation, self.f.product_type.pk)
        self.assertEqual(projected['statusCode'], 'INVALID', projected)
        self.assertFalse(projected['hasValidSourceConfiguration'])

    def test_other_route_rule_and_its_invalid_blocker_cannot_make_current_step_ready(self):
        configured = self.configure()
        rule = EngineeringRuleDefinition.objects.get(pk=configured['nativeResult']['rules'][0]['id'])
        spec = deepcopy(rule.specification)
        spec['manufacturing']['routingContext'] = {'contractVersion': correction.ROUTE_CONTRACT,
            'routingId': self.f.route.pk, 'routingVersionId': self.f.wrong_version.pk,
            'routingStepId': self.f.source_other_step.pk}
        spec['manufacturing']['modeCode'] = self.f.mode.code
        spec['manufacturing'].pop('modeId')
        published = service.ManufacturingConfigurationService.configure(user=self.f.user, reason='SIMULATED_FOR_TEST',
            package={'contractVersion': service.MANUFACTURING_CONTRACT, 'companyId': self.f.company.pk,
                'modes': [], 'rules': [{'ruleCode': 'SIM-OTHER-ROUTE-SOURCE', 'ruleName': 'Other exact route source',
                    'version': 'V1', 'effectiveFrom': date.today().isoformat(), 'specification': spec}]})
        other_rule = EngineeringRuleDefinition.objects.get(pk=published['rules'][0]['id'])
        context = {'routingId': self.f.route.pk, 'routingVersionId': self.f.version.pk, 'routingStepId': self.step.pk}
        all_scopes = service.operation_source_configuration(self.operation, self.f.product_type.pk)
        self.assertEqual(all_scopes['statusCode'], 'AMBIGUOUS', all_scopes)
        with self.assertNumQueries(0):
            restricted = service.restrict_operation_projection(all_scopes, context)
        self.assertTrue(restricted['hasValidSourceConfiguration'], restricted)
        self.assertEqual([row['ruleId'] for row in restricted['sources']], [rule.pk])
        # Deliberate isolated historical corruption in the other scope must not
        # retain its blocker after a pure current-step restriction.
        bad = deepcopy(other_rule.specification)
        bad['manufacturing']['standardCapacityId'] = self.f.capacity.pk
        self.f.corrupt_json(other_rule, 'specification', bad)
        all_scopes = service.operation_source_configuration(self.operation, self.f.product_type.pk)
        self.assertEqual(all_scopes['statusCode'], 'INVALID', all_scopes)
        with self.assertNumQueries(0):
            restricted = service.restrict_operation_projection(all_scopes, context)
        self.assertEqual(restricted['statusCode'], 'CONFIGURED', restricted)
        self.assertEqual(restricted['blockers'], [])
        result = self.read()
        self.assertEqual(result['sourceCandidates']['statusCode'], 'AVAILABLE', result)
        self.f.advance(rule, 'obsolete')
        scoped = service.operation_source_configuration(self.operation, self.f.product_type.pk, routing_context=context)
        self.assertFalse(scoped['hasValidSourceConfiguration'], scoped)


class RouteWorkloadOverviewTests(TestCase):
    """Real released route and object proofs; no business reader is mocked."""

    def setUp(self):
        original = correction.Calc4RoutingCorrectionTests.advance
        def add_repeated_steps(fixture, obj, target, *, status_field='status'):
            if isinstance(obj, RoutingVersion) and target == 'reviewed':
                for sequence in range(3, 9):
                    RoutingStep.objects.create(routing_version=obj, sequence=sequence,
                        operation=fixture.source_target, operation_parameters={'applicability': {
                            'contractVersion': 'PCE-ROUTING-STEP-APPLICABILITY-V1.0', 'mode': 'MANDATORY'}})
            return original(fixture, obj, target, status_field=status_field)
        self.case = OperationWorkloadSourceTests(methodName='runTest')
        with patch.object(correction.Calc4RoutingCorrectionTests, 'advance', add_repeated_steps):
            self.case.setUp()
        self.f, self.plan = self.case.f, self.case.plan

    def read(self):
        before = self.f.full_database_snapshot()
        with (patch.object(service, 'read_for_plan', side_effect=AssertionError('overview must not deep-read steps')),
                patch.object(native.OperationRequirementService, 'generate', side_effect=AssertionError('no generation')),
                patch.object(native.OperationRequirementService, 'generate_readiness', side_effect=AssertionError('no EOR evaluation')),
                patch.object(native.OperationRequirementService, 'allocate', side_effect=AssertionError('no allocation')),
                CaptureQueriesContext(connection) as queries):
            result = service.read_route_overview(user=self.f.user, production_plan_id=self.plan.pk)
        self.assertEqual(before, self.f.full_database_snapshot())
        self.assertFalse(any('password' in row['sql'].lower() for row in queries))
        return result, list(queries)

    def test_batch_is_step_keyed_metadata_with_constant_rule_and_absence_queries(self):
        self.case.configure()
        result, queries = self.read()
        self.assertEqual(result['summary']['stepCount'], 8)
        self.assertEqual(len({row['routingStepId'] for row in result['rows']}), 8)
        repeated = [row for row in result['rows'] if row['operationId'] == self.case.operation.pk]
        self.assertEqual(len(repeated), 7)
        self.assertTrue(all(row['sourceConfiguration']['hasValidSourceConfiguration'] for row in repeated))
        sql = [row['sql'].lower() for row in queries]
        self.assertLessEqual(sum('pde_engineering_rule_definition' in row for row in sql), 3)
        self.assertEqual(sum('pde_routing_step_object_applicability' in row for row in sql), 2)
        self.assertFalse(any('pde_engineering_derived_fact' in row for row in sql))
        self.assertFalse(any('pde_engineering_operation_requirement' in row for row in sql))
        for row in result['rows']:
            self.assertEqual(row['formalRequirements']['statusCode'], 'NOT_READ')
            self.assertEqual(row['savedAllocations']['statusCode'], 'NOT_READ')
            self.assertIsNone(row['savedAllocations']['quantity'])
        self.assertFalse(result['newEorRuleEvaluated'])
        self.assertFalse(result['generated'])
        self.assertFalse(result['allocationSaved'])
        self.assertFalse(result['wholeRouteReady'])

    def test_native_object_exclusion_is_plan_step_specific(self):
        from .tests_routing_object_applicability_service import make_object_applicability_fixture
        from . import routing_object_applicability_service as objects
        fixture = make_object_applicability_fixture(f=self.f, plan=self.plan)
        objects.confirm_group(self.f.user, self.plan.pk, self.f.step.pk, fixture.contributions,
            'SIMULATED_FOR_TEST route metadata object exclusions')
        result, _ = self.read()
        target = next(row for row in result['rows'] if row['routingStepId'] == self.f.step.pk)
        self.assertEqual(target['applicability']['result'], 'NOT_APPLICABLE')
        self.assertTrue(target['applicability']['formalApplicabilityValidated'])
        self.assertEqual(target['statusCode'], 'NOT_APPLICABLE')
        self.assertEqual(result['summary']['notApplicableCount'], 1)
        self.assertTrue(all(row['applicability']['result'] == 'REQUIRED' for row in result['rows']
            if row['routingStepId'] != self.f.step.pk))

    def test_ambiguous_configuration_stays_visible_and_foreign_plan_is_denied(self):
        first = self.case.configure()
        before = self.f.full_database_snapshot()
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            self.case.configure(ruleCode='SIM-ANOTHER-SOURCE')
        self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_RULE_AMBIGUOUS')
        self.assertEqual(before, self.f.full_database_snapshot())
        rule = EngineeringRuleDefinition.objects.get(pk=first['nativeResult']['rules'][0]['id'])
        spec = deepcopy(rule.specification)
        spec['manufacturing']['modeCode'] = self.f.mode.code
        spec['manufacturing'].pop('modeId')
        service.ManufacturingConfigurationService.configure(user=self.f.user, reason='SIMULATED_FOR_TEST existing conflict',
            package={'contractVersion': service.MANUFACTURING_CONTRACT, 'companyId': self.f.company.pk,
                'modes': [], 'rules': [{'ruleCode': 'SIM-ANOTHER-SOURCE', 'ruleName': 'Existing formal ambiguous source',
                    'version': 'V1', 'effectiveFrom': date.today().isoformat(), 'specification': spec}]})
        result, _ = self.read()
        target = next(row for row in result['rows'] if row['routingStepId'] == self.case.step.pk)
        self.assertEqual(target['sourceConfiguration']['statusCode'], 'AMBIGUOUS')
        self.assertEqual(target['resourceReferences']['selectionStatusCode'], 'AMBIGUOUS')
        foreign = Company.objects.create(code='SIM-ROUTE-FOREIGN', name='SIM route foreign company')
        viewer = User.objects.create_user(username='sim-foreign-route-viewer', company_id=foreign.pk,
            is_active=True, is_staff=True, is_superuser=True)
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            service.read_route_overview(user=viewer, production_plan_id=self.plan.pk)
        self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_PLAN_MISSING')


class OptionalWorkloadScenarioTests(TestCase):
    """Native published rules and exact source proofs in disposable scenarios."""

    def make_case(self, scope='PRODUCT_CATEGORY', namespace=''):
        from .models import Routing, ProductDefinition, ProductVersion, OrderEngineeringInstance
        original = correction.Calc4RoutingCorrectionTests.initial
        def initial(fixture, model, state, **fields):
            if namespace:
                for key in ('code', 'order_no', 'source_no', 'instance_no', 'baseline_no', 'document_no',
                    'calculation_no', 'bom_code', 'routing_code', 'plan_no', 'demand_no', 'requirement_no', 'rule_code'):
                    if isinstance(fields.get(key), str) and not fields[key].startswith(namespace):
                        fields[key] = namespace + fields[key]
            if model is OrderEngineeringInstance and scope == 'PRODUCT_DEFINITION':
                product = original(fixture, ProductDefinition, 'draft', company=fixture.company,
                    product_code='SIM-OPTIONAL-PRODUCT', product_name='Synthetic formal product',
                    category=fixture.category, material=fixture.item.material, emd_material_code=fixture.item.material.code,
                    manufacturing_definition_mode='order_engineered')
                fixture.advance(product, 'designed')
                fixture.advance(product, 'released')
                product_version = original(fixture, ProductVersion, 'draft', status_field='version_status',
                    product=product, version_no='SIM-PRODUCT-V1')
                fixture.advance(product_version, 'reviewed', status_field='version_status')
                fixture.advance(product_version, 'released', status_field='version_status')
                fields.update(product=product, baseline_product_version=product_version)
            if model is Routing and scope == 'ORDER_ENGINEERING':
                fields.pop('product_category', None)
                fields.update(applicability_scope='ORDER_ENGINEERING', order_engineering_instance=fixture.instance)
            if model is Routing and scope == 'PRODUCT_DEFINITION':
                fields.pop('product_category', None)
                fields.update(applicability_scope='PRODUCT_DEFINITION', product=fixture.instance.product)
            return original(fixture, model, state, **fields)
        case = OperationWorkloadSourceTests(methodName='runTest')
        with patch.object(correction.Calc4RoutingCorrectionTests, 'initial', initial):
            case.setUp()
        return case

    def preview(self, case, **changes):
        before = case.f.full_database_snapshot()
        with (patch.object(native.OperationRequirementService, 'generate', side_effect=AssertionError('no generation')),
              patch.object(native.OperationRequirementService, 'generate_readiness', side_effect=AssertionError('no generation readiness')),
              patch.object(native.OperationRequirementService, 'allocate', side_effect=AssertionError('no allocation')),
              patch.object(service.ManufacturingConfigurationService, 'configure', side_effect=AssertionError('no configuration save')),
              CaptureQueriesContext(connection) as queries):
            result = service.preview_configuration(user=case.f.user, company_id=case.f.company.pk,
                operation_id=case.operation.pk, payload=case.payload(**changes), plan_id=case.plan.pk,
                routing_step_id=case.step.pk)
        self.assertEqual(before, case.f.full_database_snapshot())
        self.assertFalse(any('password' in row['sql'].lower() for row in queries))
        self.assertEqual(result['businessWriteCount'], 0)
        self.assertFalse(result['generated'])
        return result

    def test_native_total_category_scenario_preserves_default_spec_and_four_states(self):
        case = self.make_case()
        result = self.preview(case)
        self.assertTrue(result['configurationPreview']['passed'], result)
        self.assertEqual(result['sourceQuantities']['statusCode'], 'AVAILABLE', result)
        self.assertEqual(result['expressionOutputs']['statusCode'], 'EVALUATED', result)
        self.assertEqual(sum(Decimal(r['sourceQuantity']) for r in result['sourceQuantities']['items']), Decimal(4))
        self.assertEqual([r['sourceQuantity'] for r in result['expressionOutputs']['items']],
            [r['outputQuantity'] for r in result['expressionOutputs']['items']])
        saved = case.configure()
        rule = EngineeringRuleDefinition.objects.get(pk=saved['nativeResult']['rules'][0]['id'])
        self.assertEqual(rule.status, 'released')
        self.assertEqual(rule.specification['expression'], 'source_quantity')
        self.assertEqual(rule.specification['outputs'][0]['quantityBasis'], 'SOURCE_SCOPE_TOTAL')
        self.assertEqual(rule.specification['outputs'][0]['basisQuantitySource'], 'SALES_ORDER_ITEM')
        read = case.read()
        self.assertEqual(read['sourceCandidates']['statusCode'], 'AVAILABLE', read)
        self.assertEqual(read['formalRequirements']['statusCode'], 'MISSING')
        self.assertIsNone(read['savedAllocations']['quantity'])

    def test_native_per_basis_order_route_scenario_has_formal_pct_and_expression(self):
        case = self.make_case('ORDER_ENGINEERING')
        self.assertIsNone(case.f.route.product_category_id)
        self.assertEqual(case.f.route.order_engineering_instance_id, case.f.instance.pk)
        context = {'contractVersion': correction.ROUTE_CONTRACT, 'routingId': case.f.route.pk,
            'routingVersionId': case.f.version.pk, 'routingStepId': case.step.pk}
        payload = {'quantityBasis': 'PER_BASIS_QUANTITY', 'basisQuantity': '1.000000',
            'basisUomId': case.f.item.uom_id, 'expression': 'source_quantity * 2', 'routingContext': context}
        result = self.preview(case, **payload)
        self.assertTrue(result['configurationPreview']['passed'], result)
        self.assertEqual(sum(Decimal(r['outputQuantity']) for r in result['expressionOutputs']['items']), Decimal(8))
        self.assertEqual(sum(Decimal(r['quantity']) for r in result['sourceQuantities']['items']), Decimal(4))
        saved = case.configure(**payload)
        rule = EngineeringRuleDefinition.objects.get(pk=saved['nativeResult']['rules'][0]['id'])
        output = rule.specification['outputs'][0]
        self.assertEqual(output['productTypeId'], case.f.product_type.pk)
        self.assertNotIn('basisQuantitySource', output)
        self.assertEqual(output['basisQuantity'], '1.000000')
        self.assertEqual(rule.specification['manufacturing']['routingContext'], context)
        read = case.read()
        self.assertEqual(read['sourceCandidates']['statusCode'], 'AVAILABLE', read)
        self.assertTrue(all(r['quantityBasis'] == 'PER_BASIS_QUANTITY' for r in result['expressionOutputs']['items']))
        self.assertEqual(read['sourceConfiguration']['sources'][0]['routingContext'], context)

    def test_product_definition_route_resolves_formal_type_and_auto_matches(self):
        case = self.make_case('PRODUCT_DEFINITION')
        self.assertIsNone(case.f.route.product_category_id)
        self.assertEqual(case.f.route.product_id, case.f.instance.product_id)
        result = self.preview(case)
        self.assertTrue(result['configurationPreview']['passed'], result)
        case.configure()
        read = case.read()
        self.assertEqual(read['scope']['productTypeId'], case.f.product_type.pk)
        self.assertEqual(read['sourceCandidates']['statusCode'], 'AVAILABLE', read)

    def test_catalog_reports_capabilities_semantics_and_formal_scope_options(self):
        case = self.make_case()
        before = case.f.full_database_snapshot()
        result = service.catalog(user=case.f.user)
        self.assertEqual(before, case.f.full_database_snapshot())
        self.assertEqual({r['code'] for r in result['quantityContracts']}, native.KNOWN_BASES)
        self.assertEqual(result['expressionContract']['inputAlias'], 'source_quantity')
        self.assertFalse(result['expressionContract']['multipleInputsAllowed'])
        self.assertEqual(result['capacitySemanticVerification']['statusCode'], 'NOT_SUPPORTED')
        option, = [r for r in result['routingContexts'] if r['routingStepId'] == case.step.pk]
        self.assertIn(case.f.product_type.pk, option['productTypeIds'])
        producer, = [r for r in result['producers'] if r['id'] == case.producer.pk]
        self.assertIn(producer['sourceSemantics']['strategy'], {'OBJECT_FORMULA', 'SCOPE_SUM', 'GROUP_SUM', 'DIRECT_FACT'})

    def test_safe_expression_unit_basis_and_wrong_scope_fail_closed_without_writes(self):
        case = self.make_case()
        faults = [{'expression': '__import__("os")'}, {'expression': 'source_quantity.value'},
            {'expression': 'unknown_input'}, {'expression': 'source_quantity * source_quantity'},
            {'expression': 'source_quantity / 0'}, {'expression': '-source_quantity'},
            {'basisQuantity': '1'}, {'quantityBasis': 'PER_BASIS_QUANTITY', 'basisQuantity': '1', 'basisUomId': case.f.area.pk},
            {'routingContext': {'contractVersion': correction.ROUTE_CONTRACT, 'routingId': case.f.route.pk,
                'routingVersionId': case.f.wrong_version.pk, 'routingStepId': case.f.source_other_step.pk}}]
        for fault in faults:
            with self.subTest(fault=fault):
                result = self.preview(case, **fault)
                self.assertFalse(result['configurationPreview']['passed'], result)
                self.assertTrue(result['blockers'])

    def test_conflicting_version_preserves_source_feedback_and_cannot_save(self):
        case = self.make_case()
        case.configure()
        before = case.f.full_database_snapshot()
        result = self.preview(case, version='V2', expression='source_quantity * 2')
        self.assertFalse(result['configurationPreview']['passed'], result)
        self.assertTrue(result['configurationPreview']['conflicts'])
        self.assertEqual(result['sourceQuantities']['statusCode'], 'AVAILABLE', result)
        self.assertEqual(result['expressionOutputs']['statusCode'], 'EVALUATED', result)
        with self.assertRaises(service.OperationWorkloadSourceError) as caught:
            case.configure(version='V2', expression='source_quantity * 2')
        self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_RULE_AMBIGUOUS')
        self.assertEqual(before, case.f.full_database_snapshot())

    def test_new_same_scope_field_producer_and_version_need_independence_before_native_save(self):
        from .engineering_fact_extension_service import EngineeringFactExtensionService
        case = self.make_case()
        configured = case.configure()
        current_id = configured['nativeResult']['rules'][0]['id']
        original = case.producer
        original_field = original.specification['outputs'][0]['canonicalName']
        variants = [('PRODUCER', original.rule_code + '-OTHER', original.version, original_field),
                    ('FIELD', original.rule_code + '-FIELD', original.version, original_field + '_other'),
                    ('VERSION', original.rule_code, original.version + '-NEXT', original_field)]
        for label, code, version, field in variants:
            with self.subTest(selector=label):
                specification = deepcopy(original.specification)
                specification['outputs'][0]['canonicalName'] = field
                producer_id, = EngineeringFactExtensionService.configure(user=case.f.user,
                    reason='SIMULATED_FOR_TEST exact alternative producer',
                    package={'contractVersion': EXTENSION_CONTRACT, 'companyId': case.f.company.pk,
                        'rules': [{'ruleCode': code, 'ruleName': 'Synthetic alternative producer',
                            'version': version, 'specification': specification}]})['ruleIds']
                changes = {'ruleCode': 'SIM-UNPROVEN-' + label, 'producerRuleId': producer_id,
                    'producerVersion': version, 'canonicalField': field}
                before = case.f.full_database_snapshot()
                result = self.preview(case, **changes)
                self.assertFalse(result['configurationPreview']['passed'], result)
                conflict, = result['configurationPreview']['conflicts']
                self.assertEqual(conflict['code'], 'WORKLOAD_SOURCE_INDEPENDENCE_UNPROVEN')
                self.assertEqual(conflict['ruleId'], current_id)
                self.assertTrue(result['nativeValidation']['publicationReferencesValid'], result)
                with patch.object(service.ManufacturingConfigurationService, 'configure',
                                  side_effect=AssertionError('unproved contribution must not reach native writer')):
                    with self.assertRaises(service.OperationWorkloadSourceError) as caught:
                        case.configure(**changes)
                self.assertEqual(caught.exception.code, 'WORKLOAD_SOURCE_INDEPENDENCE_UNPROVEN')
                self.assertEqual(before, case.f.full_database_snapshot())

    def test_viewer_can_preview_without_create_release_or_execution_chain(self):
        case = self.make_case()
        RolePermission.objects.filter(role=case.f.role, permission__code__in=(service.CREATE, service.RELEASE)).delete()
        result = self.preview(case)
        self.assertTrue(result['configurationPreview']['passed'], result)
        self.assertFalse(result['configureAuthorization']['allowed'])

    def test_same_company_same_operation_two_native_product_scenarios_never_cross(self):
        """Namespace a second full native fixture, sharing physical resources.

        Only synthetic fixture identities are adapted before creation. Every
        configure/derive/generate call below delegates to its original service;
        no source proof, runtime reader or persistence result is mocked.
        """
        from django.db.models.query import QuerySet
        from .models import CapacityProductType
        from .engineering_fact_extension_service import EngineeringFactExtensionService
        first = self.make_case()
        original_create, original_user = QuerySet.create, User.objects.create_user
        original_type_save = CapacityProductType.save
        original_extension_configure = EngineeringFactExtensionService.configure
        original_derive, original_generate = EngineeringFactExtensionService.derive, native.OperationRequirementService.generate
        prefix = 'S2-'
        def prefixed(value):
            return value if value.startswith(prefix) else prefix + value
        def create(query, **values):
            model = query.model
            if model is Company:
                return first.f.company
            if model.__name__ in {'UnitOfMeasure', 'Workshop', 'WorkCenter', 'Process'} and 'code' in values:
                old = model.objects.filter(company_id=first.f.company.pk, code=values['code']).first()
                if old is not None:
                    return old
            if model.__name__ == 'WorkCenterOperationCapability':
                old = model.objects.filter(work_center=values['work_center'], operation=values['operation']).first()
                if old is not None:
                    return old
            if model.__name__ == 'CodeRule':
                old = model.objects.filter(company_id=values['company_id'], entity_type=values['entity_type']).first()
                if old is not None:
                    return old
            # Permission codes are real action identities and must not change.
            if model is not Permission:
                identity_fields = {'code', 'name', 'product_name', 'employee_no', 'order_no', 'source_no', 'instance_no', 'baseline_no',
                    'design_no', 'document_no', 'calculation_no', 'bom_code', 'routing_code', 'plan_no',
                    'demand_no', 'requirement_no', 'rule_code', 'product_code', 'fact_code'}
                identity_fields.update(key for key in values if key.endswith('_no'))
                for key in identity_fields:
                    if isinstance(values.get(key), str):
                        values[key] = prefixed(values[key])
            return original_create(query, **values)
        def type_save(row, *args, **kwargs):
            if row.pk != first.f.product_type.pk and row.code == first.f.product_type.code:
                row.code = prefixed(row.code)
            return original_type_save(row, *args, **kwargs)
        def extension_configure(**kwargs):
            kwargs = deepcopy(kwargs)
            for row in kwargs['package']['rules']:
                row['ruleCode'] = prefixed(row['ruleCode'])
            return original_extension_configure(**kwargs)
        def derive(**kwargs):
            kwargs['idempotency_key'] = prefixed(kwargs['idempotency_key'])
            return original_derive(**kwargs)
        def generate(**kwargs):
            kwargs['idempotency_key'] = prefixed(kwargs['idempotency_key'])
            return original_generate(**kwargs)
        with (patch.object(QuerySet, 'create', create),
              patch.object(User.objects, 'create_user', side_effect=lambda **kw: original_user(**{**kw, 'username': prefixed(kw['username'])})),
              patch.object(CapacityProductType, 'save', type_save),
              patch.object(EngineeringFactExtensionService, 'configure', side_effect=extension_configure),
              patch.object(EngineeringFactExtensionService, 'derive', side_effect=derive),
              patch.object(native.OperationRequirementService, 'generate', side_effect=generate)):
            second = self.make_case('ORDER_ENGINEERING', namespace=prefix)
        self.assertEqual(first.f.company.pk, second.f.company.pk)
        self.assertEqual(first.operation.pk, second.operation.pk)
        self.assertNotEqual(first.f.product_type.pk, second.f.product_type.pk)
        self.assertNotEqual(first.producer.pk, second.producer.pk)
        a = first.configure(ruleCode='SIM-SCENARIO-A')
        b = second.configure(ruleCode='SIM-SCENARIO-B', quantityBasis='PER_BASIS_QUANTITY', basisQuantity='1',
            basisUomId=second.f.item.uom_id, expression='source_quantity * 2')
        self.assertNotEqual(a['nativeResult']['rules'][0]['id'], b['nativeResult']['rules'][0]['id'])
        for case, code, basis in ((first, 'SIM-SCENARIO-A', 'SOURCE_SCOPE_TOTAL'),
                                 (second, 'SIM-SCENARIO-B', 'PER_BASIS_QUANTITY')):
            read = case.read()
            self.assertEqual(read['sourceCandidates']['statusCode'], 'AVAILABLE', read)
            selected, = read['sourceConfiguration']['sources']
            self.assertEqual((selected['ruleCode'], selected['productTypeId'], selected['quantityBasis']),
                (code, case.f.product_type.pk, basis))
            self.assertTrue(all(row['sourceCalculationId'] == case.fixture.fixture.extension.pk
                for row in read['sourceCandidates']['items']))
        selected = self.preview(second, ruleCode='SIM-SCENARIO-B-NEXT', quantityBasis='PER_BASIS_QUANTITY',
            basisQuantity='1', basisUomId=second.f.item.uom_id, expression='source_quantity * 2')
        self.assertEqual(selected['sourceQuantities']['statusCode'], 'AVAILABLE', selected)
        self.assertEqual({r['sourceCalculationId'] for r in selected['expressionOutputs']['items']},
            {second.fixture.fixture.extension.pk})


class ScopeSummaryRoutingContextTests(TestCase):
    """Real immutable three-object SCOPE_SUM; no fabricated top-level trace."""
    make_case = OptionalWorkloadScenarioTests.make_case
    preview = OptionalWorkloadScenarioTests.preview

    def setUp(self):
        from .engineering_fact_extension_service import EngineeringFactExtensionService
        self.case = case = self.make_case()
        self.context = {'contractVersion': correction.ROUTE_CONTRACT, 'routingId': case.f.route.pk,
            'routingVersionId': case.f.version.pk, 'routingStepId': case.step.pk}
        self.old_origin = case.fixture.fixture.extension
        self.old_fact = case.fixture.fixture.facts[0]
        self.old_candidate = service._prepare_configuration(user=case.f.user, operation_id=case.operation.pk,
            payload=case.payload(routingContext=self.context), reason='SIMULATED_FOR_TEST old explicit baseline')['candidate']
        specification = deepcopy(case.producer.specification)
        specification['outputs'][0]['canonicalName'] = 'SIM_SCOPE_BOARD_TOTAL'
        original = specification['factExtension']
        specification['factExtension'] = {key: deepcopy(original[key]) for key in
            ('contractVersion', 'outputUomId', 'bindings')}
        specification['factExtension']['strategy'] = 'SCOPE_SUM'
        producer_id, = EngineeringFactExtensionService.configure(user=case.f.user,
            reason='SIMULATED_FOR_TEST native scope summary', package={'contractVersion': EXTENSION_CONTRACT,
                'companyId': case.f.company.pk, 'rules': [{'ruleCode': 'SIM-SCOPE-ROUTE-PRODUCER',
                    'ruleName': 'Synthetic three-object scope summary', 'version': 'V1',
                    'specification': specification}]})['ruleIds']
        result = EngineeringFactExtensionService.derive(user=case.f.user,
            source_calculation_id=case.f.source_calc.pk, rule_ids=[producer_id],
            idempotency_key='sim-scope-summary-route', reason='SIMULATED_FOR_TEST')
        self.origin = EngineeringCalculationRecord.objects.get(pk=result['calculationId'])
        self.fact, = list(self.origin.derived_facts.all())
        self.assertNotIn('baselineId', self.fact.trace)
        self.assertNotIn('baselineId', self.fact.trace.get('group', {}))
        self.assertEqual(self.fact.inputs.count(), 3)
        case.producer = EngineeringRuleDefinition.objects.get(pk=producer_id)
        self.candidate = service._prepare_configuration(user=case.f.user, operation_id=case.operation.pk,
            payload=case.payload(routingContext=self.context), reason='SIMULATED_FOR_TEST scope route')['candidate']

    def proof(self, *, origin=None, fact=None, rule=None):
        from .manufacturing_rule_configuration import validate_manufacturing_rule_context
        origin = EngineeringCalculationRecord.objects.get(pk=(origin or self.origin).pk)
        fact = EngineeringDerivedFact.objects.select_related('source_detail__rule', 'rule', 'uom').get(
            pk=(fact or self.fact).pk)
        before = self.case.f.full_database_snapshot()
        try:
            return validate_manufacturing_rule_context(rule=rule or self.candidate, origin=origin, fact=fact,
                operation=self.case.operation, uom=self.case.f.area, product_type=self.case.f.product_type)
        finally:
            self.assertEqual(before, self.case.f.full_database_snapshot())

    def raw(self, target, field, value):
        self.case.fixture.fixture.raw(target, field, value)

    def test_native_scope_summary_exact_route_preview_publish_and_runtime_preserve_source(self):
        case = self.case
        result = self.preview(case, routingContext=self.context)
        self.assertTrue(result['configurationPreview']['passed'], result)
        self.assertEqual(result['sourceQuantities']['statusCode'], 'AVAILABLE', result)
        self.assertEqual(result['expressionOutputs']['statusCode'], 'EVALUATED', result)
        source, = result['sourceQuantities']['items']
        self.assertEqual((source['sourceFactId'], Decimal(source['sourceQuantity'])), (self.fact.pk, Decimal(4)))
        routing = source['nativeManufacturingProof']['routingContext']
        coverage = routing['baselineProvenance']['objectCoverage']
        self.assertEqual(routing['baselineProvenance']['proofKind'], 'FORMAL_EXTENSION_OBJECT_COVERAGE')
        self.assertEqual(coverage['baselineId'], case.f.baseline.pk)
        self.assertEqual(coverage['baselineItemIds'], sorted(row.pk for row in case.f.baseline_items))
        self.assertEqual(coverage['designItemIds'], sorted(row.design_item_id for row in case.f.baseline_items))
        self.assertEqual(routing['manufacturingOutputId'], case.f.output.pk)
        self.assertEqual(routing['routingStepId'], case.step.pk)
        saved = case.configure(routingContext=self.context)
        self.assertEqual(saved['configuration']['statusCode'], 'CONFIGURED', saved)
        read = case.read()
        self.assertEqual(read['sourceCandidates']['statusCode'], 'AVAILABLE', read)
        self.assertEqual([row['sourceFactId'] for row in read['sourceCandidates']['items']], [self.fact.pk])
        self.fact.refresh_from_db()
        self.assertNotIn('baselineId', self.fact.trace)
        self.assertEqual(read['formalRequirements']['statusCode'], 'MISSING')
        self.assertIsNone(read['savedAllocations']['quantity'])

    def test_scope_summary_input_object_and_baseline_hash_drift_remain_rejected(self):
        case = self.case
        leaf = self.fact.inputs.order_by('sequence').first().source_fact
        wrong = next(row for row in case.f.baseline_items if row.pk != leaf.trace['baselineItemId'])
        wrong_trace = {**leaf.trace, 'baselineItemId': wrong.pk}
        faults = [(self.origin, 'input_hash', '0' * 64), (leaf, 'trace', wrong_trace),
                  (case.f.baseline_items[0], 'content_hash', '0' * 64),
                  (case.f.baseline, 'snapshot_hash', '0' * 64)]
        for target, field, value in faults:
            with self.subTest(model=type(target).__name__, field=field):
                original = deepcopy(getattr(target, field))
                self.raw(target, field, value)
                try:
                    with self.assertRaises(native.OperationRequirementError):
                        self.proof()
                    rejected = self.preview(case, routingContext=self.context)
                    self.assertFalse(rejected['configurationPreview']['passed'], rejected)
                    self.assertTrue(rejected['blockers'])
                finally:
                    self.raw(target, field, original)
        self.assertIn('baselineProvenance', self.proof()['routingContext'])

    def test_old_explicit_baseline_serialization_and_missing_direct_identity_stay_unchanged(self):
        from . import manufacturing_rule_configuration as manufacturing
        from . import manufacturing_routing_context as routing
        old = self.proof(origin=self.old_origin, fact=self.old_fact, rule=self.old_candidate)['routingContext']
        self.assertNotIn('baselineProvenance', old)
        self.assertEqual(set(old), {'contractVersion', 'factSource', 'sourceEngineeringCalculationId',
            'sourceFactCalculationId', 'sourceFactId', 'manufacturingOutputId', 'context', 'routingId',
            'routingCode', 'routingVersionId', 'routingVersion', 'routingStepId', 'sequence', 'operationId',
            'workCenterId', 'standardCapacityId', 'productTypeId', 'uomId', 'resolvedScope',
            'stepApplicability', 'formalSourceHashes'})
        spec, config, selector = manufacturing._configuration(self.candidate, require_released=True)
        rows = manufacturing._formal_references(self.candidate, spec, config, selector)
        direct = self.fact.inputs.order_by('sequence').first().source_fact
        missing = deepcopy(direct.trace)
        missing.pop('baselineId')
        faults = [(self.origin, self.fact, {**self.fact.trace, 'baselineId': None}),
                  (self.origin, self.fact, {**self.fact.trace, 'baselineId': 0}),
                  (self.origin, self.fact, {**self.fact.trace, 'baselineId': True}),
                  (self.case.f.source_calc, direct, missing)]
        for origin, fact, trace in faults:
            with self.subTest(scope=origin.scope, baseline=trace.get('baselineId')):
                original = deepcopy(fact.trace)
                self.raw(fact, 'trace', trace)
                try:
                    fact.refresh_from_db()
                    before = self.case.f.full_database_snapshot()
                    with (patch('pde.engineering_fact_extension_service.validate_extension_fact',
                                side_effect=AssertionError('explicit/direct old path must not use fallback')),
                          patch.object(native, '_extension_object_coverage',
                                side_effect=AssertionError('explicit/direct old path must not use fallback'))):
                        with self.assertRaises(native.OperationRequirementError) as caught:
                            routing.validate_routing_context(rule=self.candidate, spec=spec, config=config,
                                rows=rows, origin=origin, fact=fact)
                    self.assertEqual(caught.exception.code, 'MANUFACTURING_ROUTING_SOURCE_INVALID')
                    self.assertEqual(before, self.case.f.full_database_snapshot())
                finally:
                    self.raw(fact, 'trace', original)
                    fact.refresh_from_db()

    def test_missing_formal_output_and_invalid_bom_remain_blocked(self):
        for target, field, value in ((self.case.f.output, 'release_status', 'draft'),
                                     (self.case.f.bom_version, 'status', 'draft')):
            with self.subTest(model=type(target).__name__):
                original = getattr(target, field)
                self.raw(target, field, value)
                try:
                    with self.assertRaises(native.OperationRequirementError) as caught:
                        self.proof()
                    self.assertEqual(caught.exception.code, 'MANUFACTURING_ROUTING_OUTPUT_INVALID')
                finally:
                    self.raw(target, field, original)

