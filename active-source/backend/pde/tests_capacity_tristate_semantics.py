"""Capacity meanings and read projections; disposable fixtures only."""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from .production_foundation_service import ProductionFoundationError, ProductionFoundationService

from . import daily_capacity_service as capacity
from . import operation_workload_source_service as workload
from . import tests_daily_capacity_date_preview as dates
from . import tests_daily_capacity_source_rules as sources
from . import tests_operation_workload_source_service as native_fixtures
from . import tests_operation_input_preparation as preparation_fixtures


class CapacityTristateSemanticsTests(SimpleTestCase):
    def semantic(self, value, **changes):
        return capacity.capacity_tristate_semantics(source_value=value,
            **{'source_scope_proven': True, 'record_present': True, **changes})

    def test_only_positive_zero_and_proven_blank_are_valid_business_meanings(self):
        for value, status, code, passes in (('12.5', 'measured', 'QUANTIFIED', True),
                ('0', 'zero_capacity', 'NON_QUANTIFIED', True), (None, None, 'NOT_APPLICABLE', False)):
            with self.subTest(value=value):
                result = self.semantic(value, measurement_status=status)
                self.assertTrue(result['valid'])
                self.assertEqual(result['meaningCode'], code)
                self.assertIs(result['passesOperation'], passes)
                self.assertFalse(result['grantsScheduling'])
                self.assertFalse(result['grantsRequirementGeneration'])

    def test_missing_record_does_not_prove_source_blank_or_non_applicability(self):
        unknown = self.semantic(None, source_scope_proven=False, record_present=False)
        blank = self.semantic(None, source_scope_proven=True, record_present=False)
        self.assertFalse(unknown['valid'])
        self.assertIsNone(unknown['meaningCode'])
        self.assertIsNone(unknown['passesOperation'])
        self.assertEqual(blank['meaningCode'], 'NOT_APPLICABLE')
        self.assertIn('缺记录不等于', unknown['recordPresenceStatusLabel'])

    def test_legacy_not_determinable_is_a_conflict_not_a_fourth_valid_kind(self):
        result = self.semantic(None, measurement_status='not_determinable')
        self.assertFalse(result['valid'])
        self.assertIsNone(result['meaningCode'])
        self.assertEqual(result['conflictCode'], 'LEGACY_CAPACITY_SEMANTICS_CONFLICT')
        self.assertIn('不能作为有效第四类', result['sourceStatusLabel'])

    def test_invalid_numbers_and_mismatched_statuses_do_not_gain_a_meaning(self):
        for value in (True, False, '-1', 'NaN', 'Infinity', 'invalid'):
            with self.subTest(value=value):
                self.assertFalse(self.semantic(value)['valid'])
        for value, status in (('0', 'measured'), ('1', 'zero_capacity'), (None, 'measured'), (None, 'zero_capacity')):
            self.assertFalse(self.semantic(value, measurement_status=status)['valid'])
        self.assertFalse(self.semantic('1', record_present=False)['valid'])

    def test_unproved_positive_or_zero_cannot_grant_quantitative_occupancy(self):
        for value in ('12', '0'):
            result = self.semantic(value, source_scope_proven=False, quantitative_occupancy_allowed=True)
            self.assertFalse(result['valid'])
            self.assertFalse(result['quantitativeOccupancyAllowed'])

    def test_positive_fact_preserves_original_day_formula(self):
        row = dates.capacity_fixture()
        fact = capacity.capacity_fact(row, dates.START)
        self.assertTrue(fact['available'])
        self.assertEqual(fact['capacitySemantics']['meaningCode'], 'QUANTIFIED')
        result = capacity.duration_days(demand_quantity=300, capacity_quantity=100,
            demand_uom_id=1, capacity_uom_id=1, preparation_days='.1', transfer_days='.1')
        self.assertEqual(Decimal(result['durationDays']), Decimal('3.2'))

    def test_zero_without_formal_manifest_stays_unproven_without_querying_a_database(self):
        row = dates.capacity_fixture(quantity='0')
        row.measurement_status = 'zero_capacity'
        fact = capacity.capacity_fact(row, dates.START)
        self.assertFalse(fact['available'])
        self.assertFalse(fact['capacitySemantics']['valid'])
        self.assertIsNone(fact['capacitySemantics']['meaningCode'])

    def test_formal_zero_preserves_raw_times_without_a_duration_or_booking_permission(self):
        product, _, _, rows = sources.source_fixture()
        row = rows[1]
        proof = {'status': 'VALID', 'manifest': sources.source_manifest(), 'capacityRows': rows}
        fact = capacity.capacity_fact(row, sources.START, source_rules=proof)
        semantics = fact['capacitySemantics']
        self.assertEqual(semantics['meaningCode'], 'NON_QUANTIFIED')
        self.assertTrue(semantics['passesOperation'])
        self.assertFalse(fact['available'])
        self.assertFalse(semantics['quantitativeOccupancyAllowed'])
        self.assertFalse(semantics['independentDurationAllowed'])
        self.assertEqual((semantics['preparationDays'], semantics['transferDays']), ('0.1', '0.1'))
        self.assertIn('不形成准确总加工时长', semantics['preparationTransferPolicyLabel'])
        self.assertIn('不删除步骤', semantics['dependencyPolicyLabel'])

    def test_required_objects_cannot_be_replaced_by_a_source_blank(self):
        result = capacity.scoped_capacity_semantics(scope={'operationId': 2},
            applicability={'result': 'REQUIRED'}, source_rules={'status': 'VALID', 'manifest': sources.source_manifest()},
            capacity_facts=[])
        self.assertFalse(result['valid'])
        self.assertIsNone(result['meaningCode'])
        self.assertEqual(result['conflictCode'], 'CAPACITY_OBJECT_SCOPE_CONFLICT')

    def test_pending_object_scope_cannot_be_resolved_by_a_zero_manifest(self):
        result = capacity.scoped_capacity_semantics(scope={'operationId': 3},
            applicability={'result': 'PENDING'}, source_rules={'status': 'VALID', 'manifest': sources.source_manifest()},
            capacity_facts=[])
        self.assertFalse(result['valid'])
        self.assertIsNone(result['passesOperation'])

    def test_multiple_positive_resources_are_not_collapsed_to_a_first_quantity(self):
        facts = [capacity.capacity_fact(dates.capacity_fixture(index, quantity=value), dates.START)
            for index, value in ((1, '10'), (2, '20'))]
        result = capacity.scoped_capacity_semantics(scope={'operationId': 15}, applicability={'result': 'REQUIRED'},
            source_rules={'status': 'MISSING'}, capacity_facts=facts)
        self.assertFalse(result['valid'])
        self.assertIsNone(result['sourceValue'])
        self.assertEqual(result['sourceValues'], ['10', '20'])

    def test_verified_zero_ruling_is_exact_scope_qualitative_evidence_without_an_sc_substitute(self):
        scope = dict(companyId=1, productionPlanId=2, manufacturingOutputId=2, mainCalculationId=4,
            salesOrderItemId=4, baselineId=2, routingVersionId=31, routingStepId=804, operationId=3, productTypeId=11)
        ruling = self.semantic('0', measurement_status='zero_capacity', scope=scope, record_present=False)
        prep = {'exactScope': deepcopy(scope), 'capacitySemantics': ruling,
            'capacityResolution': {'sourceProof': {'rawValue': None, 'rawValueKind': 'BLANK'}}}
        result, facts = workload._step_capacity_semantics(user=SimpleNamespace(company_id=1), scope=scope,
            applicability={'result': 'REQUIRED'}, source_rules={'status': 'MISSING'}, capacities=[], preparation=prep)
        self.assertEqual(facts, [])
        self.assertEqual(result['meaningCode'], 'NON_QUANTIFIED')
        self.assertFalse(result['recordPresent'])
        self.assertFalse(result['formalStandardCapacitySubstituted'])
        self.assertFalse(result['quantitativeOccupancyAllowed'])
        self.assertIsNone(result['originalSourceValue'])
        self.assertEqual(result['originalSourceValueKind'], 'BLANK')
        self.assertIn('原始来源矩阵为空白', result['sourceStatusLabel'])
        for field in ('companyId', 'productionPlanId', 'routingStepId', 'productTypeId'):
            other = {**scope, field: scope[field] + 1000}
            result, _ = workload._step_capacity_semantics(user=SimpleNamespace(company_id=other['companyId']),
                scope=other, applicability={'result': 'REQUIRED'}, source_rules={'status': 'MISSING'},
                capacities=[], preparation=prep)
            self.assertFalse(result['valid'], field)
            self.assertIsNone(result['meaningCode'])

    def test_zero_node_keeps_original_dependency_bridge_without_independent_demand_or_dates(self):
        case = dates.DailyCapacityDatePreviewTests(methodName='runTest')
        case.setUp()
        try:
            case.test_auxiliary_zero_step_creates_no_independent_demand_or_date_and_preserves_dependency()
        finally:
            case.doCleanups()

    def test_all_zero_route_does_not_fabricate_an_end_date_or_load(self):
        case = dates.DailyCapacityDatePreviewTests(methodName='runTest')
        case.setUp()
        try:
            case.test_all_auxiliary_route_does_not_fabricate_a_date_or_independent_workload()
        finally:
            case.doCleanups()


class CapacityTristateNativeProjectionTests(TestCase):
    def setUp(self):
        self.case = native_fixtures.OperationWorkloadSourceTests(methodName='runTest')
        self.case.setUp()
        self.f, self.plan = self.case.f, self.case.plan

    def test_route_and_step_projection_reuse_server_meanings_without_publishing_or_writes(self):
        before = self.f.full_database_snapshot()
        overview = workload.read_route_overview(user=self.f.user, production_plan_id=self.plan.pk)
        step = next(row for row in overview['rows'] if row['routingStepId'] == self.case.step.pk)
        read = workload.read_for_plan(user=self.f.user, production_plan_id=self.plan.pk, routing_step_id=self.case.step.pk)
        self.assertEqual(step['capacitySemantics'], read['capacitySemantics'])
        self.assertEqual(step['capacitySemantics']['scope']['operationName'], self.case.operation.name)
        self.assertEqual(step['capacitySemantics']['scope']['sequence'], self.case.step.sequence)
        self.assertEqual(step['capacitySemantics']['scope']['productTypeCode'], self.f.product_type.code)
        self.assertFalse(read['sourceConfiguration']['hasValidSourceConfiguration'])
        self.assertEqual(read['formalRequirements']['items'], [])
        self.assertIsNone(read['savedAllocations']['quantity'])
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_missing_sc_is_not_projected_as_a_source_blank_or_zero(self):
        self.f.source_capacity.delete()
        before = self.f.full_database_snapshot()
        read = workload.read_for_plan(user=self.f.user, production_plan_id=self.plan.pk, routing_step_id=self.case.step.pk)
        result = read['capacitySemantics']
        self.assertFalse(result['valid'])
        self.assertIsNone(result['meaningCode'])
        self.assertFalse(result['recordPresent'])
        self.assertIn('缺记录不等于', result['recordPresenceStatusLabel'])
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_native_create_rejects_legacy_null_category_and_rolls_back_support_writes(self):
        row = self.f.source_capacity
        before = self.f.full_database_snapshot()
        with self.assertRaises(ProductionFoundationError) as raised:
            ProductionFoundationService.write('standard-capacities', user=self.f.user,
                payload={'company_id': self.f.company.pk, 'code': 'SIM-LEGACY-REJECT', 'name': 'SIMULATED_FOR_TEST',
                    'measurement_status': 'not_determinable', 'quantity': None,
                    'product_type_id': row.product_type_id, 'operation_id': row.operation_id,
                    'work_center_id': row.work_center_id, 'resource_scope': row.resource_scope,
                    'uom_id': row.uom_id, 'time_basis': 'day', 'time_basis_quantity': '1',
                    'effective_from': row.effective_from.isoformat(), 'reason': 'SIMULATED_FOR_TEST native rejection'},
                idempotency_key='sim-legacy-create-reject', source_identity={
                    'sourceSystem': 'SIMULATED_FOR_TEST', 'sourceType': 'CAPACITY_TRISTATE_TEST',
                    'sourceObjectType': 'StandardCapacity', 'externalId': 'sim-legacy-create-reject'})
        self.assertEqual(raised.exception.code, 'CAPACITY_LEGACY_STATUS_NOT_ALLOWED')
        self.assertEqual(self.f.full_database_snapshot(), before)


    def test_native_update_cannot_turn_a_positive_record_into_legacy_null_category(self):
        row = self.f.source_capacity
        before = self.f.full_database_snapshot()
        with self.assertRaises(ProductionFoundationError) as raised:
            ProductionFoundationService.write('standard-capacities', user=self.f.user, object_id=row.pk,
                payload={'measurement_status': 'not_determinable', 'quantity': None,
                    'reason': 'SIMULATED_FOR_TEST native legacy update rejection'},
                idempotency_key='sim-legacy-update-reject', source_identity=None)
        self.assertEqual(raised.exception.code, 'CAPACITY_LEGACY_STATUS_NOT_ALLOWED')
        self.assertEqual(self.f.full_database_snapshot(), before)


class CapacityTristateRulingOverviewTests(TestCase):
    def test_zero_ruling_keeps_route_machine_fields_and_summary_consistent_with_current_meaning(self):
        case = preparation_fixtures.OperationInputPreparationTests(methodName='runTest')
        case.setUp()
        case.save_no_capacity_preparation()
        case.correct_capacity()
        before = case.snapshot()
        proof = {'status': 'VALID', 'manifest': {
            'contractVersion': capacity.SOURCE_RULES_CONTRACT,
            'applicableOperationIds': [case.f.op_area.pk],
            'auxiliaryOperationIds': [], 'nonApplicableOperationIds': [case.operation.pk]},
            'fact': {'statusLabel': 'SIMULATED_FOR_TEST original blank matrix'},
            'capacityRows': [case.f.capacity]}
        with patch.object(capacity, 'capacity_source_rules', return_value=proof):
            overview = workload.read_route_overview(user=case.user, production_plan_id=case.plan.pk)
            current = workload.read_for_plan(user=case.user, production_plan_id=case.plan.pk, routing_step_id=case.step.pk)
        row = next(item for item in overview['rows'] if item['routingStepId'] == case.step.pk)
        self.assertEqual(row['capacityRole'], 'AUXILIARY')
        self.assertEqual(row['currentRole'], 'AUXILIARY')
        self.assertEqual(row['originalSourceRole'], 'NON_APPLICABLE')
        self.assertEqual(row['capacityApplicability']['result'], 'REQUIRED')
        self.assertEqual(row['applicability']['result'], 'REQUIRED')
        self.assertEqual(row['capacitySemantics']['meaningCode'], 'NON_QUANTIFIED')
        self.assertEqual(row['capacitySemantics'], current['capacitySemantics'])
        self.assertTrue(row['needsSourceConfiguration'])
        self.assertIn('OPERATION_RULE_MAPPING_MISSING', {item['code'] for item in row['blockers']})
        self.assertEqual(overview['summary']['capacityNonApplicableCount'], 0)
        self.assertEqual(overview['summary']['auxiliaryCount'], 1)
        self.assertGreaterEqual(overview['summary']['missingCount'], 1)
        self.assertEqual(row['resourceReferences']['standardCapacityCandidates'], [])
        self.assertFalse(row['capacitySemantics']['quantitativeOccupancyAllowed'])
        self.assertEqual(current['formalRequirements']['items'], [])
        self.assertIsNone(current['savedAllocations']['quantity'])
        self.assertEqual(case.snapshot(), before)

