"""Stage meaning regression: pending quantities are never numeric zero."""
from copy import deepcopy

from django.test import SimpleTestCase

from . import operation_workload_source_service as service


class ConditionalWorkloadReviewTests(SimpleTestCase):
    def row(self):
        policy = {'formalPolicyValidated': True, 'triggerStatus': 'WAITING_TRIGGER',
            'triggerPolicyLabel': '品质异常触发时执行，当前待触发',
            'pendingScopeLabel': '异常触发后确定实际处理对象、数量及单位',
            'capacityIndependenceLabel': '0产能与未定处理数量分别表达',
            'conditionalCapacityPolicy': {'appliesWhen': 'TRIGGERED',
                'meaningCode': 'NON_QUANTIFIED', 'sourceValue': '0',
                'quantitativeOccupancyAllowed': False}}
        empty = {'statusCode': 'WAITING_TRIGGER', 'statusLabel': policy['pendingScopeLabel'],
            'items': [], 'quantity': None, 'uomLabel': None,
            'persistence': {'readStatus': 'loaded', 'recordCount': 0, 'statusLabel': '未保存'}}
        return {'sequence': 71, 'operationName': '任意正式工序',
            'applicability': {'result': 'PENDING', 'conditionalExecution': policy},
            'formalRequirements': deepcopy(empty), 'savedAllocations': deepcopy(empty),
            'sourceConfiguration': {'sources': []}, 'blockers': [],
            'capacitySemantics': {'valid': True, 'meaningCode': 'NON_QUANTIFIED', 'sourceValue': '0'}}

    def review(self, row):
        return service._workload_row_review(row,
            coverage={'statusCode': 'NOT_OBTAINED', 'statusLabel': '对象尚未确定'})

    def test_verified_waiting_stage_defers_quantity_without_saving_zero(self):
        row = self.row()
        before = deepcopy(row)
        result = self.review(row)
        self.assertEqual(result['statusCode'], 'WAITING_TRIGGER')
        self.assertEqual(result['formalRequirementCount'], 0)
        self.assertEqual(result['allocationCount'], 0)
        self.assertIsNone(result['savedQuantity'])
        self.assertIsNone(result['uomLabel'])
        self.assertIn('无需预置', result['formalRequirementDisplayLabel'])
        self.assertEqual(row, before)

    def test_capacity_zero_alone_does_not_defer_required_operation_quantity(self):
        row = self.row()
        row['applicability'] = {'result': 'REQUIRED'}
        row['formalRequirements']['statusCode'] = 'MISSING'
        row['savedAllocations']['statusCode'] = 'MISSING'
        self.assertEqual(self.review(row)['statusCode'], 'BLOCKED')
        self.assertNotIn('formalRequirementDisplayLabel', self.review(row))

    def test_pending_without_verified_policy_is_not_waiting_trigger(self):
        row = self.row()
        row['applicability']['conditionalExecution']['formalPolicyValidated'] = False
        self.assertEqual(self.review(row)['statusCode'], 'PENDING')
        self.assertIsNone(service._waiting_trigger(row['applicability']))

    def test_read_failure_or_saved_row_cannot_be_hidden_by_waiting_policy(self):
        for status, count in [('read_failed', None), ('loaded', 1)]:
            with self.subTest(status=status, count=count):
                row = self.row()
                row['formalRequirements']['persistence'].update(readStatus=status, recordCount=count)
                result = self.review(row)
                self.assertEqual(result['statusCode'], 'BLOCKED')
                self.assertEqual(result['formalRequirementCount'], count)

    def test_existing_native_blockers_remain_blockers(self):
        row = self.row()
        row['blockers'] = [{'code': 'SOURCE_PROOF_INVALID', 'statusLabel': '来源校验失败'}]
        result = self.review(row)
        self.assertEqual(result['statusCode'], 'BLOCKED')
        self.assertEqual(result['blockers'], row['blockers'])

    def test_conditional_capacity_preserves_zero_policy_without_claiming_execution(self):
        row = self.row()
        semantics, facts = service._step_capacity_semantics(user=None, scope={'operationId': 71},
            applicability=row['applicability'], source_rules={'status': 'VALID', 'manifest': {}},
            capacities=[])
        self.assertEqual(facts, [])
        self.assertEqual(semantics['meaningCode'], 'NON_QUANTIFIED')
        self.assertEqual(semantics['sourceValue'], '0')
        self.assertEqual(semantics['appliesWhen'], 'TRIGGERED')
        self.assertIsNone(semantics['passesOperation'])
        self.assertTrue(semantics['passesWhenTriggered'])
        for flag in ('grantsRulePublication', 'grantsRequirementGeneration', 'grantsAllocation',
                'grantsScheduling', 'quantitativeOccupancyAllowed', 'independentDurationAllowed'):
            self.assertFalse(semantics[flag])
