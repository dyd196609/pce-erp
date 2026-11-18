"""Source-rule acceptance entirely in memory; no database alias is opened."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .daily_capacity_service import (
    AUXILIARY_DATE_MODE, DailyCapacityReadinessService, SOURCE_RULES_CONTRACT, capacity_source_rules,
)

START = date(2026, 10, 13)
HASH = 'a1' * 32


def source_manifest():
    return {'contractVersion': SOURCE_RULES_CONTRACT, 'sourceSha256': HASH,
        'productTypeCode': 'READY/SEMI', 'effectiveDate': START.isoformat(),
        'applicableOperationIds': [1, 3], 'nonApplicableOperationIds': [2], 'auxiliaryOperationIds': [3],
        'preparationDays': '0.1', 'transferDays': '0.1', 'businessFactReference': 'USER-CONFIRMED-SOURCE-RULES'}


def source_fixture():
    product_type = SimpleNamespace(pk=41, company_id=7, code='READY/SEMI', name='memory product type',
        is_active=True, effective_from=None, effective_to=None)
    uom = SimpleNamespace(pk=21, company_id=7, code='M2', name='平方米', is_active=True)
    operations, centers, rows = {}, {}, []
    manifest = source_manifest()
    for operation_id in (1, 2, 3):
        operation = operations[operation_id] = SimpleNamespace(pk=operation_id, company_id=7,
            name=f'工序{operation_id}', code=f'OP{operation_id}', is_active=True, effective_from=None,
            effective_to=None, work_center=None, calculation_uom_id=21, calculation_uom=uom,
            calculation_basis='area', quantity_driver='PERSISTED_OPERATION_REQUIREMENT')
        center = centers[operation_id] = SimpleNamespace(pk=operation_id * 10, company_id=7,
            code=f'WC{operation_id:03}', name=f'工作中心{operation_id}', workshop_id=9,
            is_active=True, effective_from=None, effective_to=None, capacity_policy={})
        if operation_id == 2:
            continue
        rows.append(SimpleNamespace(pk=100 + operation_id, code=f'SC{operation_id}', name='memory capacity',
            company_id=7, product_type_id=41, product_type=product_type,
            operation_id=operation_id, operation=operation, work_center_id=center.pk, work_center=center,
            uom_id=21, uom=uom, is_active=True, effective_from=START, effective_to=None,
            time_basis='day', time_basis_quantity=Decimal('1'), time_unit='DAY',
            quantity=Decimal('99') if operation_id == 1 else Decimal('0'),
            measurement_status='measured' if operation_id == 1 else 'zero_capacity',
            preparation_days=Decimal('0.1'), transfer_days=Decimal('0.1'),
            conditions={'sourceSha256': HASH, 'sourceProductTypeCode': 'READY/SEMI',
                        'apsSourceRules': deepcopy(manifest)}))
    return product_type, operations, centers, rows


def query_rows(rows):
    query = MagicMock()
    query.select_related.return_value = rows
    return query


class DailyCapacitySourceRulesMemoryTests(SimpleTestCase):
    def setUp(self):
        self.product_type, self.operations, self.centers, self.rows = source_fixture()

    def rules(self, *, on_date=START):
        process_query = MagicMock()
        process_query.values_list.return_value = [1, 2, 3]
        with patch('pde.daily_capacity_service.StandardCapacity.objects.filter', return_value=query_rows(self.rows)), patch(
            'system.models.Process.objects.filter', return_value=process_query,
        ):
            return capacity_source_rules(self.product_type, company_id=7, on_date=on_date)

    def assess(self, *, pending_operation=None, preparation_override=None):
        route = SimpleNamespace(company_id=7, routing_code='READY/SEMI', product_category_id=11,
                                manufacturing_process_type_id=12)
        steps = [SimpleNamespace(pk=200 + operation_id, sequence=operation_id * 10,
            operation=operation, is_active=True, predecessor_sequences=[] if operation_id == 1 else [(operation_id - 1) * 10],
            work_center=self.centers[operation_id], preparation_days=None, transfer_days=None)
            for operation_id, operation in self.operations.items()]
        steps[0].preparation_days = preparation_override
        step_manager = MagicMock()
        step_manager.select_related.return_value = steps
        version = SimpleNamespace(pk=61, routing=route, routing_id=51, routing_version='V1', steps=step_manager)
        relation_query = query_rows([])
        process_query = MagicMock()
        process_query.values_list.return_value = [1, 2, 3]

        def capacities(**kwargs):
            if 'product_type_id' in kwargs:
                return query_rows(self.rows)
            return query_rows([row for row in self.rows if row.operation_id == kwargs['operation'].pk])

        def applicability(step, **kwargs):
            state = 'PENDING' if step.operation.pk == pending_operation else 'REQUIRED'
            return {'result': state, 'resultLabel': '待正式判断' if state == 'PENDING' else '路线要求经过'}

        with patch('pde.daily_capacity_service.CapacityProductType.objects.filter', return_value=[self.product_type]), patch(
            'pde.daily_capacity_service.StandardCapacity.objects.filter', side_effect=capacities,
        ), patch('pde.daily_capacity_service.WorkCenterOperationCapability.objects.filter', return_value=relation_query), patch(
            'system.models.Process.objects.filter', return_value=process_query,
        ), patch('pde.routing_step_applicability_service.RoutingStepApplicabilityResolver.resolve', side_effect=applicability):
            return DailyCapacityReadinessService.assess(version, on_date=START)

    def test_consistent_current_formal_manifest_preserves_approved_partition_and_raw_zero(self):
        result = self.rules()
        self.assertEqual(result['status'], 'VALID')
        self.assertEqual(result['manifest'], source_manifest())
        self.assertEqual(result['capacityRows'][1].quantity, Decimal('0'))

    def test_formal_manifest_day_values_are_consumed_without_rewriting_the_source(self):
        for preparation, transfer in (('0.25', '0'), (0, '1.75'), (None, '0.3'), (None, None)):
            with self.subTest(preparation=preparation, transfer=transfer):
                for row in self.rows:
                    row.conditions['apsSourceRules'].update(preparationDays=preparation, transferDays=transfer)
                    row.preparation_days = Decimal(str(preparation)) if preparation is not None else None
                    row.transfer_days = Decimal(str(transfer)) if transfer is not None else None
                original = deepcopy(self.rows[0].conditions['apsSourceRules'])
                result = self.rules()
                self.assertEqual(result['status'], 'VALID', result)
                self.assertEqual(result['manifest'], original)
                self.assertEqual(result['fact']['manifest'], original)

    def test_invalid_or_missing_manifest_day_values_fail_closed(self):
        for key in ('preparationDays', 'transferDays'):
            for value in ('', 'not-a-number', '-0.1', 'NaN', 'Infinity', True, [], {}):
                with self.subTest(key=key, value=value):
                    for row in self.rows:
                        row.conditions['apsSourceRules'] = {**source_manifest(), key: value}
                    self.assertEqual(self.rules()['status'], 'INVALID')
            for row in self.rows:
                row.conditions['apsSourceRules'] = source_manifest()
                row.conditions['apsSourceRules'].pop(key)
            self.assertEqual(self.rules()['status'], 'INVALID')

    def test_each_capacity_day_value_must_match_the_manifest_including_null(self):
        for key, field in (('preparationDays', 'preparation_days'), ('transferDays', 'transfer_days')):
            for value in ('0.25', None):
                with self.subTest(key=key, value=value):
                    self.product_type, self.operations, self.centers, self.rows = source_fixture()
                    for row in self.rows:
                        row.conditions['apsSourceRules'][key] = value
                        setattr(row, field, Decimal(value) if value is not None else None)
                    self.assertEqual(self.rules()['status'], 'VALID')
                    setattr(self.rows[1], field, Decimal('0.1'))
                    self.assertEqual(self.rules()['status'], 'INVALID')

    def catalog_capacities(self):
        from .operation_workload_source_service import _catalog_capacity_options
        process_query = MagicMock()
        process_query.values_list.return_value = [1, 2, 3]
        with patch('pde.daily_capacity_service.StandardCapacity.objects.filter', return_value=query_rows(self.rows)), patch(
            'system.models.Process.objects.filter', return_value=process_query,
        ):
            return _catalog_capacity_options(self.rows, kinds=[self.product_type],
                centers=[{'id': row.pk} for row in self.centers.values()],
                units=[self.operations[1].calculation_uom])

    def test_catalog_preserves_measured_options_and_admits_proved_zero(self):
        original = deepcopy(self.rows[1].conditions)
        options = self.catalog_capacities()
        self.assertEqual([(row['id'], row['quantity']) for row in options], [(101, '99'), (103, '0')])
        self.assertEqual(self.rows[1].conditions, original)

    def test_catalog_rejects_unproved_zero_and_invalid_scope_without_hiding_measured_options(self):
        for mutation in ('missing_manifest', 'wrong_hash', 'wrong_company', 'wrong_operation_company',
                         'wrong_uom', 'positive_zero', 'not_auxiliary'):
            with self.subTest(mutation=mutation):
                self.product_type, self.operations, self.centers, self.rows = source_fixture()
                row = self.rows[1]
                if mutation == 'missing_manifest':
                    row.conditions.pop('apsSourceRules')
                elif mutation == 'wrong_hash':
                    row.conditions['sourceSha256'] = 'bb' * 32
                elif mutation == 'wrong_company':
                    row.company_id = 8
                elif mutation == 'wrong_operation_company':
                    row.operation.company_id = 8
                elif mutation == 'wrong_uom':
                    row.uom_id = 22
                elif mutation == 'positive_zero':
                    row.quantity = Decimal('1')
                else:
                    for capacity in self.rows:
                        capacity.conditions['apsSourceRules']['auxiliaryOperationIds'] = []
                self.assertEqual([option['id'] for option in self.catalog_capacities()], [101])

    def test_blank_becomes_not_applicable_and_zero_auxiliary_never_reports_capacity_or_time_missing(self):
        result = self.assess()
        positive, blank, auxiliary = result['steps']
        self.assertEqual(blank['applicability']['result'], 'NOT_APPLICABLE')
        self.assertEqual(blank['routingApplicability']['result'], 'REQUIRED')
        self.assertEqual(blank['dailyCapacity'], [])
        self.assertEqual(blank['blockerCodes'], [])
        self.assertEqual(auxiliary['applicability']['result'], 'REQUIRED')
        self.assertEqual(auxiliary['capacityDateMode'], AUXILIARY_DATE_MODE)
        self.assertEqual(auxiliary['dailyCapacity'][0]['quantity'], '0')
        self.assertFalse(auxiliary['dailyCapacity'][0]['available'])
        self.assertEqual(auxiliary['preparationDays'], '0.1')
        self.assertEqual(auxiliary['transferDays'], '0.1')
        self.assertEqual(auxiliary['blockerCodes'], [])
        self.assertEqual(result['auxiliaryStepCount'], 1)
        self.assertEqual(result['independentDateStepCount'], 1)
        self.assertIn('MANUFACTURING_CALENDAR_MISSING', positive['blockerCodes'])
        self.assertFalse(result['planningReady'])

    def test_confirmed_blank_overrides_pending_for_aps_but_preserves_original_routing_fact(self):
        row = self.assess(pending_operation=2)['steps'][1]
        self.assertEqual(row['applicability']['result'], 'NOT_APPLICABLE')
        self.assertEqual(row['routingApplicability']['result'], 'PENDING')
        self.assertEqual(row['capacityDateMode'], 'NOT_APPLICABLE')
        self.assertEqual(row['blockerCodes'], [])
        self.assertIn('排产跳过', row['sourceRulesConflictLabel'])

    def test_auxiliary_pending_condition_remains_blocked_without_an_independent_date_mode(self):
        row = self.assess(pending_operation=3)['steps'][2]
        self.assertEqual(row['applicability']['result'], 'PENDING')
        self.assertEqual(row['capacityDateMode'], AUXILIARY_DATE_MODE)
        self.assertIn('ROUTING_STEP_APPLICABILITY_PENDING', row['blockerCodes'])
        self.assertIn('保留阻断', row['sourceRulesConflictLabel'])

    def test_real_formal_import_json_reference_is_consumed_unchanged_by_readiness(self):
        evidence = (Path(__file__).resolve().parents[2] / 'outputs' /
            '01a132f9-5adc-7540-88c1-061133d95e3f' / 'formal-capacity-import-20261013' /
            'confirmed-business-field-facts.json')
        reference = json.loads(evidence.read_text(encoding='utf-8'))['businessFactReference']
        self.assertIsInstance(reference, dict)
        self.assertEqual(reference['blankMeaning'], '产品不经过该工序，不生成StandardCapacity，不参与排产')
        for row in self.rows:
            row.conditions['apsSourceRules']['businessFactReference'] = deepcopy(reference)
        result = self.assess(pending_operation=2)
        self.assertEqual(result['sourceRulesFact']['status'], 'VALID')
        self.assertEqual(result['sourceRulesFact']['manifest']['businessFactReference'], reference)
        self.assertEqual(result['steps'][1]['applicability']['result'], 'NOT_APPLICABLE')
        self.assertEqual(result['steps'][1]['routingApplicability']['result'], 'PENDING')
        self.assertEqual(result['steps'][2]['capacityDateMode'], AUXILIARY_DATE_MODE)

    def test_empty_or_illegal_structured_reference_cannot_validate_a_manifest(self):
        for reference in ({}, [], '   ', 1, {'evidence': float('nan')}, {'evidence': {'not-json'}}):
            for row in self.rows:
                row.conditions['apsSourceRules']['businessFactReference'] = reference
            self.assertEqual(self.rules()['status'], 'INVALID')

    def test_conflicting_step_day_override_blocks_without_rewriting_the_route_fact(self):
        result = self.assess(preparation_override=Decimal('0.2'))
        self.assertIn('APS_SOURCE_RULES_INVALID', result['steps'][0]['blockerCodes'])
        self.assertIn('未修改路线', result['steps'][0]['sourceRulesConflictLabel'])

    def test_no_manifest_does_not_infer_non_applicability_from_absent_capacity(self):
        for row in self.rows:
            row.conditions.pop('apsSourceRules')
        result = self.assess()
        self.assertEqual(result['sourceRulesFact']['status'], 'MISSING')
        self.assertEqual(result['steps'][1]['applicability']['result'], 'REQUIRED')
        self.assertIn('DAILY_CAPACITY_MISSING', result['steps'][1]['blockerCodes'])

    def test_conflicting_manifests_block_instead_of_silently_skipping_steps(self):
        self.rows[1].conditions['apsSourceRules']['businessFactReference'] = 'DIFFERENT-DECISION'
        result = self.assess()
        self.assertEqual(result['sourceRulesFact']['status'], 'INVALID')
        self.assertEqual(result['steps'][1]['applicability']['result'], 'REQUIRED')
        self.assertTrue(all('APS_SOURCE_RULES_INVALID' in row['blockerCodes'] for row in result['steps']))

    def test_illegal_identity_partition_and_wrong_source_hash_fail_closed(self):
        for mutation in (
            {'auxiliaryOperationIds': [2]}, {'applicableOperationIds': [1, 1, 3]},
            {'nonApplicableOperationIds': [1, 2]}, {'auxiliaryOperationIds': [True]}, {'sourceSha256': 'bad'},
        ):
            for row in self.rows:
                row.conditions['apsSourceRules'] = {**source_manifest(), **mutation}
            self.assertEqual(self.rules()['status'], 'INVALID')

    def test_positive_or_missing_formal_quantity_cannot_be_declared_auxiliary_zero(self):
        for quantity, status in ((Decimal('60'), 'measured'), (None, 'not_determinable')):
            self.rows[1].quantity, self.rows[1].measurement_status = quantity, status
            self.assertEqual(self.rules()['status'], 'INVALID')

    def test_future_manifest_and_incomplete_formal_partition_cannot_prove_a_blank(self):
        self.assertEqual(self.rules(on_date=date(2026, 10, 12))['status'], 'MISSING')
        self.rows.pop()
        self.assertEqual(self.rules()['status'], 'INVALID')
