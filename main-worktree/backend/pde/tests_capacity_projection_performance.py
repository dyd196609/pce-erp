"""Native read profiling in disposable SQLite, never the formal runtime."""
from copy import deepcopy
from datetime import date
import json
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from . import daily_capacity_service as capacity
from . import tests_operation_workload_source_service as fixtures
from .production_foundation_service import ProductionFoundationService


class CapacityProjectionPerformanceTests(TestCase):
    def setUp(self):
        case = fixtures.OperationWorkloadSourceTests(methodName='runTest')
        case.setUp()
        self.f, self.operation = case.f, case.operation
        effective = self.f.capacity.effective_from
        self.manifest = {'contractVersion': capacity.SOURCE_RULES_CONTRACT, 'sourceSha256': 'a1' * 32,
            'productTypeCode': self.f.product_type.code, 'effectiveDate': effective.isoformat(),
            'applicableOperationIds': sorted([self.f.op_area.pk, self.operation.pk]),
            'nonApplicableOperationIds': [], 'auxiliaryOperationIds': [self.operation.pk],
            'preparationDays': '0.1', 'transferDays': '0.1', 'businessFactReference': 'SIMULATED_FOR_TEST profiling'}
        self.conditions = {'sourceSha256': 'a1' * 32, 'sourceProductTypeCode': self.f.product_type.code,
            'apsSourceRules': self.manifest}
        self.f.source_capacity.quantity, self.f.source_capacity.measurement_status = 0, 'zero_capacity'
        for row in (self.f.capacity, self.f.source_capacity):
            row.conditions = deepcopy(self.conditions)
            row.save(update_fields=('conditions', 'quantity', 'measurement_status'))
        for index in range(18):
            self.f.make_capacity(self.operation, self.f.area, f'SIM-PERFORMANCE-ZERO-{index}',
                measurement_status='zero_capacity', quantity=0, conditions=deepcopy(self.conditions),
                preparation_days='.1', transfer_days='.1')

    def profile(self, entity):
        before = self.f.full_database_snapshot()
        with patch.object(capacity, 'capacity_source_rules', wraps=capacity.capacity_source_rules) as proof:
            with CaptureQueriesContext(connection) as queries:
                rows = ProductionFoundationService.list(entity, organization_id=self.f.company.pk)
        counts = {'entity': entity, 'rows': len(rows), 'queryCount': len(queries), 'sourceProofCalls': proof.call_count}
        print('CAPACITY_NATIVE_PROFILE=' + json.dumps(counts, sort_keys=True))
        self.assertEqual(self.f.full_database_snapshot(), before)
        return rows, counts

    def test_standard_capacity_list_verifies_source_once_per_type_with_constant_queries(self):
        rows, counts = self.profile('standard-capacities')
        self.assertEqual(len(rows), 20)
        self.assertLessEqual(counts['sourceProofCalls'], 1)
        self.assertLessEqual(counts['queryCount'], 4)
        zeros = [row for row in rows if row['measurement_status'] == 'zero_capacity']
        self.assertTrue(zeros)
        self.assertTrue(all(row['dailyCapacityFact']['capacitySemantics']['meaningCode'] == 'NON_QUANTIFIED' for row in zeros))

    def test_work_center_list_reuses_the_same_type_proof_for_all_capacity_facts(self):
        rows, counts = self.profile('work-centers')
        facts = [fact for row in rows for fact in row['dailyCapacityFacts']]
        self.assertEqual(len(facts), 20)
        self.assertLessEqual(counts['sourceProofCalls'], 1)
        self.assertLessEqual(counts['queryCount'], 5)
        self.assertTrue(all(fact['capacitySemantics']['valid'] for fact in facts))

    def test_a_new_list_call_revalidates_source_drift_instead_of_reusing_an_old_proof(self):
        first, _ = self.profile('standard-capacities')
        row = self.f.source_capacity
        row.conditions = {**deepcopy(self.conditions), 'sourceSha256': 'b2' * 32}
        row.save(update_fields=('conditions',))
        second, counts = self.profile('standard-capacities')
        self.assertLessEqual(counts['sourceProofCalls'], 1)
        self.assertTrue(all(item['dailyCapacityFact']['capacitySemantics']['valid'] for item in first))
        self.assertTrue(all(not item['dailyCapacityFact']['capacitySemantics']['valid'] for item in second))
