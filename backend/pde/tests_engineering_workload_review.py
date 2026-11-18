"""SIMULATED_FOR_TEST: purpose/read boundaries in a disposable Django database."""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from . import engineering_workload_review as review
from . import tests_operation_requirement as fixtures
from .engineering_workload_summary import build_engineering_workload_summary, FACT_SURFACES
from .models import EngineeringCalculationRecord
from .operation_requirement_service import _read_once, OperationRequirementError
from .operation_requirement_service import OperationRequirementService
from . import tests_manufacturing_eor_configuration as manufacturing_fixtures
from . import tests_engineering_fact_extension as extension_fixtures
from .engineering_fact_extension_service import EngineeringFactExtensionService, CONTRACT as EXTENSION_CONTRACT
from .manufacturing_configuration_service import CREATE, RELEASE
from . import tests_calc4_routing_correction as correction_fixtures


class PurposeQuantityUnitTests(SimpleTestCase):
    def group(self, **overrides):
        dimensions = dict(companyId=1, sourceRecordId=2, salesOrderItemId=4, baselineId=2,
            purposeCode='PAINTING', productionGroupId=2, routingId=31, routingVersionId=31,
            manufacturingModeId=1, manufacturingModeVersion='V1', productTypeId=11,
            quantityBasis='SOURCE_SCOPE_TOTAL', uomId=18, uomCode='m2', uomLabel='平方米',
            sourceScopeLabel='SIMULATED_FOR_TEST 第2行')
        dimensions.update(overrides)
        return review._group(dimensions, 'SIMULATED_FOR_TEST')

    def test_route_mode_unit_and_purpose_are_real_group_dimensions(self):
        original = self.group()
        for change in ({'routingVersionId': 43}, {'manufacturingModeId': 3},
                       {'manufacturingModeVersion': 'V2'}, {'uomId': 13}, {'purposeCode': 'CUTTING'},
                       {'productionGroupId': 1}, {'productTypeId': 28}, {'baselineId': 3}):
            self.assertNotEqual(original['key'], self.group(**change)['key'])

    def test_distinct_equal_object_values_add_once_not_distinct_value(self):
        group = self.group()
        group['contributions'] = [{'contributionIdentity': 'object:1', 'quantity': '1'},
                                  {'contributionIdentity': 'object:2', 'quantity': '1'}]
        review._finish_candidate(group)
        self.assertEqual(group['engineeringCandidate']['quantity'], '2')

    def test_same_object_duplicate_is_unknown_instead_of_double_count(self):
        group = self.group()
        group['contributions'] = [{'contributionIdentity': 'object:1', 'quantity': '5'},
                                  {'contributionIdentity': 'object:1', 'quantity': '5'}]
        review._finish_candidate(group)
        self.assertIsNone(group['engineeringCandidate']['quantity'])
        self.assertIn('CONTRIBUTION_IDENTITY_UNPROVEN', {row['code'] for row in group['missingReasons']})

    def test_ambiguous_extension_versions_cannot_be_chosen_by_highest_id(self):
        group = self.group()
        group['candidateAmbiguous'] = True
        group['contributions'] = [{'contributionIdentity': 'same-scope', 'quantity': '3'}]
        review._finish_candidate(group)
        self.assertIsNone(group['engineeringCandidate']['quantity'])

    def test_unknown_and_formal_zero_are_distinct(self):
        for quantity, expected in ((None, None), ('0', '0')):
            group = self.group()
            group['contributions'] = [{'contributionIdentity': 'object:1', 'quantity': quantity}]
            review._finish_candidate(group)
            self.assertEqual(group['engineeringCandidate']['quantity'], expected)

    def test_source_quantity_without_group_or_mode_does_not_become_candidate(self):
        group = self.group(manufacturingModeId=None)
        group['missingReasons'].append(review._reason('PURPOSE_DIMENSIONS_UNKNOWN', '缺少映射'))
        group['contributions'] = [{'contributionIdentity': 'source:1', 'quantity': '3'}]
        review._finish_candidate(group)
        self.assertIsNone(group['engineeringCandidate']['quantity'])
        self.assertEqual(group['engineeringCandidate']['sourceQuantity'], '3')

    def test_physical_three_sets_is_known_source_with_unknown_production_candidate(self):
        group = self.group(purposeCode='PHYSICAL_SOURCE', manufacturingModeId=None, productionGroupId=None, uomId=13, uomLabel='套')
        group['contributions'] = [{'contributionIdentity': f'object:{number}', 'quantity': '1'} for number in range(3)]
        review._finish_candidate(group)
        self.assertEqual(group['engineeringCandidate']['sourceQuantity'], '3')
        self.assertIsNone(group['engineeringCandidate']['quantity'])
        self.assertIn('候选量未知', group['engineeringCandidate']['statusLabel'])

    def test_plan_sets_never_automatically_convert_to_painting_area(self):
        group = self.group()
        plans = [{'id': 1, 'quantity': '3', 'uomId': 13, 'uomLabel': '套'}]
        review._plan_column(group, plans, True)
        self.assertIsNone(group['confirmedPlan']['quantity'])
        self.assertEqual(group['confirmedPlan']['plans'][0]['uomLabel'], '套')
        self.assertFalse(group['comparison']['allowed'])

    def test_permission_denied_is_not_zero_or_empty_plan_contract(self):
        group = self.group()
        review._plan_column(group, [], False)
        self.assertIsNone(group['confirmedPlan']['quantity'])
        self.assertIn('受限', group['confirmedPlan']['statusLabel'])

    def test_request_cache_reuses_success_but_not_failure_or_changed_hash(self):
        cache, calls = {}, []
        def loader():
            calls.append(1)
            return {'proof': True}
        identity = ('fact_extension_proof', 1, 4, 423, 'input', 'result')
        self.assertEqual(_read_once(cache, identity, loader), _read_once(cache, identity, loader))
        self.assertEqual(len(calls), 1)
        _read_once(cache, (*identity[:-1], 'changed-result'), loader)
        _read_once(None, identity, loader)
        _read_once(None, identity, loader)
        self.assertEqual(len(calls), 4)
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                _read_once(cache, 'failure', lambda: (_ for _ in ()).throw(RuntimeError('failure')))
        self.assertNotIn('failure', cache)

    def test_capacity_exact_sets_fraction_and_mismatched_units(self):
        capacity = SimpleNamespace(pk=230, effective_from=None, effective_to=None, conditions={},
            is_active=True, company_id=1, uom_id=13, operation_id=8, work_center_id=9,
            product_type_id=11, measurement_status='measured', time_basis='day', time_unit='DAY',
            time_basis_quantity=Decimal(1), quantity=Decimal(12))
        req = SimpleNamespace(standard_capacity=capacity, calculation=SimpleNamespace(company_id=1),
            uom_id=13, operation_id=8, work_center_id=9)
        with patch.object(review, 'capacity_usage_scope_proof', return_value=None):
            result = review._capacity(req, Decimal(5), {'uomLabel': '套', 'productTypeId': 11})
            self.assertEqual(result['quantity'], '12')
            self.assertEqual(result['theoreticalResourceDaysLabel'], '5/12 资源天')
            req.uom_id = 18
            self.assertIsNone(review._capacity(req, Decimal(5), {'uomLabel': '平方米', 'productTypeId': 11})['theoreticalResourceDays'])

    def test_eor_only_scope_never_claims_aps_release(self):
        capacity = SimpleNamespace(pk=1009, effective_from=None, effective_to=None, is_active=True,
            company_id=1, uom_id=18, operation_id=16, work_center_id=17, product_type_id=11,
            measurement_status='measured', time_basis='day', time_unit='DAY', time_basis_quantity=Decimal(1), quantity=Decimal(200))
        req = SimpleNamespace(standard_capacity=capacity, calculation=SimpleNamespace(company_id=1),
            uom_id=18, operation_id=16, work_center_id=17)
        with patch.object(review, 'capacity_usage_scope_proof', return_value={'usageScope': 'ENGINEERING_EOR_ONLY'}):
            result = review._capacity(req, Decimal('1.939650'), {'uomLabel': '平方米', 'productTypeId': 11})
        self.assertIn('禁止APS放行', result['admissionStatusLabel'])


class PurposeReadIsolationTests(TestCase):
    initial = fixtures.OperationRequirementTests.initial
    advance = fixtures.OperationRequirementTests.advance
    make_rule = fixtures.OperationRequirementTests.make_rule
    make_source_fact = fixtures.OperationRequirementTests.make_source_fact

    def setUp(self):
        fixtures.OperationRequirementTests.setUp(self)

    def call(self, **overrides):
        before = list(EngineeringCalculationRecord.objects.order_by('pk').values())
        with (patch('pde.operation_requirement_service.OperationRequirementService.generate', side_effect=AssertionError('reader cannot generate')),
              patch('pde.engineering_calculation_service.EngineeringCalculationService.execute', side_effect=AssertionError('reader cannot recalculate'))):
            with CaptureQueriesContext(connection) as queries:
                result = review.build_purpose_review(user=self.user, calculations=[self.source_calc], **overrides)
        writes = [row['sql'] for row in queries if row['sql'].lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'REPLACE'}]
        self.assertEqual(writes, [])
        self.assertEqual(list(EngineeringCalculationRecord.objects.order_by('pk').values()), before)
        return result

    def test_original_plan_quantity_service_unit_scope_and_empty_allocations_are_preserved(self):
        result = self.call()
        self.assertTrue(result['planningAccess']['allowed'])
        self.assertEqual(result['counts']['effectiveRequirementCount'], 0)
        for group in result['groups']:
            self.assertEqual(group['confirmedPlan']['plans'][0]['quantity'], '3.0000')
            self.assertEqual(group['confirmedPlan']['plans'][0]['uomId'], self.pcs.pk)
            self.assertIsNone(group['confirmedPlan']['quantity'])
        self.assertEqual(result['operationLoads'], [])

    def test_missing_planning_permission_does_not_call_plan_read_or_change_engineering_permission(self):
        real_decide = review.AuthorizationService.decide
        def decide(**kwargs):
            if kwargs['action_code'] == 'planning.view':
                return {'allowed': False, 'decisionCode': 'TEST_DENIED', 'reason': 'SIMULATED_FOR_TEST'}
            return real_decide(**kwargs)
        with patch.object(review.AuthorizationService, 'decide', side_effect=decide), patch.object(review.OperationRequirementService, 'read', side_effect=AssertionError('restricted plan must not be read')):
            result = self.call()
        self.assertFalse(result['planningAccess']['allowed'])
        self.assertTrue(all(group['confirmedPlan']['quantity'] is None for group in result['groups']))

    def test_foreign_company_or_non_selected_calculation_is_excluded(self):
        foreign = SimpleNamespace(pk=999999)
        result = review.build_purpose_review(user=self.user, calculations=[foreign])
        self.assertEqual(result['groups'], [])
        self.assertEqual(result['operationLoads'], [])

    def test_additive_summary_keeps_old_rows_and_identical_fact_surfaces(self):
        result = build_engineering_workload_summary(user=self.user, source_calculation_ids=[self.source_calc.pk])
        self.assertEqual(result['counts']['formalFactCount'], 2)
        self.assertEqual(len(result['formalSavedFacts']), 2)
        self.assertEqual(result['purposeReview']['contractVersion'], review.CONTRACT)
        surface = {key: value for key, value in result.items() if key not in FACT_SURFACES}
        for key in FACT_SURFACES:
            self.assertEqual(result[key], surface)

    def test_native_source_proof_marker_reports_failed_source_instead_of_success(self):
        positive = OperationRequirementService.read_source_conversion(user=self.user,
            source_calculation_id=self.source_calc.pk, source_fact_ids=[self.fact_area.pk])
        self.assertTrue(positive['facts'][0]['sourceProofPassed'])
        # Explicit storage corruption exists only in this disposable fixture.
        self.fact_area.value = {'decimal': '999'}
        self.fact_area.save(update_fields=['value'])
        rejected = OperationRequirementService.read_source_conversion(user=self.user,
            source_calculation_id=self.source_calc.pk, source_fact_ids=[self.fact_area.pk])
        self.assertFalse(rejected['facts'][0]['sourceProofPassed'])
        self.assertTrue(rejected['facts'][0]['blockers'])


class PurposeFormalExtensionTests(TestCase):
    """Saved final extensions are built only while arranging isolated fixtures."""
    initial = fixtures.OperationRequirementTests.initial
    advance = fixtures.OperationRequirementTests.advance
    make_rule = fixtures.OperationRequirementTests.make_rule
    make_source_fact = fixtures.OperationRequirementTests.make_source_fact
    call = PurposeReadIsolationTests.call
    make_mode = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_mode
    make_capacity = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_capacity
    make_mapping = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_mapping
    grant_configuration_permissions = manufacturing_fixtures.ManufacturingEorConfigurationTests.grant_configuration_permissions
    binding = extension_fixtures.EngineeringFactExtensionTests.binding
    spec = extension_fixtures.EngineeringFactExtensionTests.spec

    def setUp(self):
        manufacturing_fixtures.ManufacturingEorConfigurationTests.setUp(self)
        self.grant_configuration_permissions(CREATE, RELEASE)
        self.extension_spec = self.spec([{'canonicalName': 'area_quantity', 'valueType': 'decimal',
            'unit': self.area.code, 'unitDimension': 'area', 'sourceType': 'AGGREGATED',
            'required': True, 'unitRequired': True}], 'BoardNetAreaSummary', 'area_quantity',
            {'strategy': 'SCOPE_SUM', 'bindings': [self.binding('area_quantity', 'source_area',
                self.fact_area.rule, self.area, self.area)]})
        self.extension = self.make_extension('SIM-REVIEW-FINAL', 'V1')
        from .models import EngineeringDerivedFact
        self.final_fact = EngineeringDerivedFact.objects.get(pk=self.extension['factIds'][0])
        self.final_mapping = self.make_mapping(self.final_fact, self.op_area, self.area,
            mode=self.mode, capacity=self.capacity, dynamic_source_basis=True,
            manufacturing_overrides={'sourceSelector': {'canonicalField': self.final_fact.canonical_field,
                'producerRuleId': self.final_fact.rule_id, 'producerRuleVersion': 'V1',
                'traceEquals': {'contractVersion': EXTENSION_CONTRACT}}})
        self.final_requirement = OperationRequirementService.generate(user=self.user,
            source_calculation_id=self.final_fact.calculation_id, source_fact_id=self.final_fact.pk,
            rule_id=self.final_mapping.pk, idempotency_key='sim-review-eor', reason='SIMULATED_FOR_TEST fixture')

    def make_extension(self, code, version):
        package = {'contractVersion': EXTENSION_CONTRACT, 'companyId': self.company.pk, 'rules': [
            {'ruleCode': code, 'ruleName': 'SIMULATED_FOR_TEST', 'version': version,
             'specification': deepcopy(self.extension_spec)}]}
        configured = EngineeringFactExtensionService.configure(user=self.user, package=package, reason='SIMULATED_FOR_TEST fixture')
        return EngineeringFactExtensionService.derive(user=self.user, source_calculation_id=self.source_calc.pk,
            rule_ids=configured['ruleIds'], idempotency_key=f'sim-review-{code}-{version}', reason='SIMULATED_FOR_TEST fixture')

    def test_legal_extension_final_fact_and_effective_load_read_without_generation(self):
        result = self.call()
        candidate = next(row for row in result['groups'] if row['purposeCode'] == 'CUTTING')
        self.assertEqual(candidate['engineeringCandidate']['quantity'], '20')
        self.assertEqual(len(candidate['contributions']), 1)
        self.assertEqual(candidate['contributions'][0]['sourceCalculationId'], self.final_fact.calculation_id)
        self.assertEqual(candidate['contributions'][0]['originCalculationId'], self.source_calc.pk)
        load = result['operationLoads'][0]
        self.assertEqual(load['effectiveQuantity'], '20')
        self.assertIsNone(load['allocatedQuantity'])
        self.assertEqual(load['allocationStatusLabel'], '未分配')
        reasons = {row['code'] for row in load['missingReasons']}
        # This abstract extension has no frozen base baseline reference.
        # It is unknown for that reason, not merely because its run ID differs.
        self.assertNotIn('ALLOCATION_SOURCE_MISMATCH', reasons)
        self.assertIn('ALLOCATION_EXTENSION_BASELINE_UNPROVEN', reasons)
        self.assertIsNone(load['capacity']['theoreticalResourceDays'])  # repeated operation lacks exact step
        contribution = load['contributions'][0]
        self.assertEqual(contribution['operationRequirementId'], self.final_requirement['operationRequirementId'])
        self.assertEqual(contribution['sourceCalculationId'], self.final_fact.calculation_id)
        self.assertEqual(contribution['originCalculationId'], self.source_calc.pk)
        self.assertEqual(contribution['sourceFactId'], self.final_fact.pk)
        self.assertEqual(contribution['ruleCode'], self.final_fact.rule.rule_code)
        self.assertEqual(contribution['operationRuleCode'], self.final_mapping.rule_code)

    def test_duplicate_completed_extension_of_same_formal_inputs_keeps_candidate_unknown(self):
        self.make_extension('SIM-REVIEW-FINAL-VARIANT', 'V2')
        result = self.call()
        candidates = [row for row in result['groups'] if row['purposeCode'] == 'CUTTING']
        self.assertTrue(candidates)
        self.assertTrue(all(row['engineeringCandidate']['quantity'] is None for row in candidates))
        self.assertTrue(all(any(reason['code'] == 'CONTRIBUTION_IDENTITY_UNPROVEN' for reason in row['missingReasons']) for row in candidates))

    def test_extension_with_wrong_order_line_identity_is_excluded(self):
        EngineeringCalculationRecord.objects.filter(pk=self.final_fact.calculation_id).update(engineering_instance_id=None)
        result = self.call()
        self.assertFalse(any(row['purposeCode'] == 'CUTTING' for row in result['groups']))

    def test_invalid_source_proof_cannot_become_formal_candidate(self):
        self.final_fact.value = {'decimal': '999'}
        self.final_fact.save(update_fields=['value'])
        result = self.call()
        self.assertFalse(any(row['engineeringCandidate']['quantity'] is not None
            for row in result['groups'] if row['purposeCode'] == 'CUTTING'))
        self.assertTrue(result['missingReasons'])

    def test_formal_plan_cache_reuses_only_success_and_still_checks_saved_fact_values(self):
        from . import engineering_fact_extension_service as service
        cache = {}
        origin = self.final_fact.calculation
        with patch.object(service, '_plan', wraps=service._plan) as planner:
            service.validate_extension_fact(origin, self.final_fact, read_cache=cache)
            service.validate_extension_fact(origin, self.final_fact, read_cache=cache)
            self.assertEqual(planner.call_count, 1)
            # Current persisted value must still be checked with a cached plan.
            self.final_fact.value = {'decimal': '999'}
            self.final_fact.save(update_fields=['value'])
            with self.assertRaises(OperationRequirementError):
                service.validate_extension_fact(origin, self.final_fact, read_cache=cache)
            self.assertEqual(planner.call_count, 1)

    def test_formal_plan_cache_default_none_rebuilds_and_failed_loader_is_not_cached(self):
        from . import engineering_fact_extension_service as service
        origin = self.final_fact.calculation
        with patch.object(service, '_plan', wraps=service._plan) as planner:
            service.validate_extension_fact(origin, self.final_fact)
            service.validate_extension_fact(origin, self.final_fact)
            self.assertEqual(planner.call_count, 2)
        cache = {}
        with patch.object(service, '_plan', side_effect=RuntimeError('SIMULATED_FOR_TEST failed proof')) as planner:
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    service.validate_extension_fact(origin, self.final_fact, read_cache=cache)
            self.assertEqual(planner.call_count, 2)
        self.assertEqual(cache, {})


class PurposeHistoryIsolationTests(TestCase):
    initial = correction_fixtures.Calc4RoutingCorrectionTests.initial
    advance = correction_fixtures.Calc4RoutingCorrectionTests.advance
    make_rule = correction_fixtures.Calc4RoutingCorrectionTests.make_rule
    make_mode = correction_fixtures.Calc4RoutingCorrectionTests.make_mode
    make_capacity = correction_fixtures.Calc4RoutingCorrectionTests.make_capacity
    make_mapping = correction_fixtures.Calc4RoutingCorrectionTests.make_mapping
    make_fact = correction_fixtures.Calc4RoutingCorrectionTests.make_fact
    make_version = correction_fixtures.Calc4RoutingCorrectionTests.make_version
    new_rule = correction_fixtures.Calc4RoutingCorrectionTests.new_rule
    route_evidence = correction_fixtures.Calc4RoutingCorrectionTests.route_evidence
    generate = correction_fixtures.Calc4RoutingCorrectionTests.generate
    correct = correction_fixtures.Calc4RoutingCorrectionTests.correct
    protected_snapshot = correction_fixtures.Calc4RoutingCorrectionTests.protected_snapshot
    call = PurposeReadIsolationTests.call

    def setUp(self):
        correction_fixtures.Calc4RoutingCorrectionTests.setUp(self)
        self.correct()

    def test_formal_history_is_trace_only_and_cannot_double_effective_load(self):
        # An abstract canonical quantity contract exercises the same reader;
        # no customer rule, product name or source identity is copied.
        with patch.dict(review.PURPOSES, {'opaque_area': ('PAINTING', 'SIMULATED_FOR_TEST')}, clear=True):
            result = self.call()
        self.assertEqual(result['counts'], {'effectiveRequirementCount': 3, 'historicalRequirementCount': 3})
        self.assertEqual({row['id'] for row in result['historyRequirements']}, set(self.old_ids))
        self.assertTrue(all(row['supersededById'] for row in result['historyRequirements']))
        self.assertEqual(len(result['operationLoads']), 1)
        load = result['operationLoads'][0]
        self.assertEqual(load['effectiveQuantity'], '4')
        self.assertFalse(set(load['requirementIds']) & set(self.old_ids))
        candidate = next(row for row in result['groups'] if row['purposeCode'] == 'PAINTING')
        self.assertEqual(candidate['engineeringCandidate']['quantity'], '4')

    def test_effective_and_history_traces_keep_object_and_each_original_rule_version(self):
        with patch.dict(review.PURPOSES, {'opaque_area': ('PAINTING', 'SIMULATED_FOR_TEST')}, clear=True):
            result = self.call()
        active = [row for load in result['operationLoads'] for row in load['contributions']]
        historical = [row for history in result['historyRequirements'] for row in history['contributions']]
        self.assertEqual(len(active), 3)
        self.assertEqual(len(historical), 3)
        self.assertEqual({row['operationRequirementId'] for row in historical}, set(self.old_ids))
        for row in active + historical:
            self.assertIsNotNone(row['designItemId'])
            self.assertIsNotNone(row['baselineItemId'])
            self.assertEqual(row['salesOrderItemId'], self.item.pk)
            self.assertEqual(row['ruleCode'], self.producer.rule_code)
            self.assertEqual(row['ruleVersion'], self.producer.version)
            self.assertEqual(row['sourceCalculationId'], self.source_calc.pk)
            self.assertEqual(row['originCalculationId'], self.source_calc.pk)
        self.assertEqual({row['operationRuleVersion'] for row in active}, {self.correct_rule.version})
        self.assertEqual({row['operationRuleVersion'] for row in historical}, {self.mapping.version})
        self.assertNotEqual(self.correct_rule.version, self.mapping.version)
