"""A native quantity policy is separate from zero, unknown and pre-trigger work."""
from copy import deepcopy
from unittest.mock import patch

from django.test import SimpleTestCase

from . import operation_workload_source_service as service


class QuantityPolicyWorkloadReviewTests(SimpleTestCase):
    def row(self):
        scope = dict(zip(('companyId', 'productionPlanId', 'manufacturingOutputId', 'mainCalculationId',
            'salesOrderItemId', 'baselineId', 'routingVersionId', 'routingStepId', 'operationId', 'productTypeId'), range(21,31)))
        policy = {'contractVersion': 'PCE-OPERATION-QUANTITY-POLICY-V1',
            'measurementMode': 'NOT_SEPARATELY_MEASURED', 'formalPolicyValidated': True,
            'nullReason': 'NOT_SEPARATELY_MEASURED', 'scopeDetermination': 'DRAWING_AND_SITE',
            'objectCoverageClaimed': False, 'exactScope': deepcopy(scope),
            'plannedQuantity': None, 'actualQuantity': None, 'statusLabel': '常规必经配套，不单独计量',
            'plannedQuantityReasonLabel': '计划投产量不单独计量',
            'actualQuantityReasonLabel': '实际产量不单独计量',
            'capacityIndependenceLabel': '数量政策与正式0产能分别表达',
            'statisticalUomReference': {'uomId': 71, 'uomLabel': '测试长度单位',
                'sourceCompanyId': scope['companyId'], 'sourceProductionPlanId': scope['productionPlanId'],
                'sourceRoutingVersionId': scope['routingVersionId'], 'sourceRoutingStepId': 39,
                'sourceOperationId': 40, 'proofHash': 'a' * 64}}
        preparation = {'factSource': 'server', 'recordStatus': 'RECORDED', 'recordId': 91,
            'exactScope': deepcopy(scope), 'quantityPolicy': policy,
            **{key: False for key in ('formalRulePublished', 'readyForGeneration', 'readyForAllocation', 'readyForScheduling')}}
        bucket = {'statusCode': 'NOT_SEPARATELY_MEASURED', 'statusLabel': '不单独计量',
            'items': [], 'quantity': None, 'uomId': None, 'uomLabel': None,
            'persistence': {'readStatus': 'loaded', 'recordCount': 0, 'statusLabel': '本次正式查询0条'}}
        return {'scope': scope, 'inputPreparation': preparation,
            'sequence': 88, 'operationName': '任意配套工序',
            'applicability': {'result': 'REQUIRED'}, 'capacityRole': 'AUXILIARY',
            'capacitySemantics': {'valid': True, 'meaningCode': 'NON_QUANTIFIED', 'sourceValue': '0'},
            'sourceConfiguration': {'sources': []}, 'formalRequirements': deepcopy(bucket),
            'savedAllocations': deepcopy(bucket), 'blockers': []}

    def review(self, row):
        return service._workload_row_review(row,
            coverage={'statusCode': 'NOT_SEPARATELY_MEASURED', 'statusLabel': '依图纸或现场确定范围'})

    def test_policy_nulls_and_statistical_reference_remain_distinct_from_saved_quantity(self):
        row = self.row()
        original = deepcopy(row)
        result = self.review(row)
        self.assertEqual(result['statusCode'], 'NOT_SEPARATELY_MEASURED')
        self.assertIsNone(result['savedQuantity'])
        self.assertIsNone(result['uomLabel'])
        self.assertIn('测试长度单位', result['savedQuantityDisplayLabel'])
        self.assertNotIn('待触发', str(result))
        self.assertEqual(row, original)

    def test_zero_capacity_and_auxiliary_role_alone_never_exempt_required_quantity(self):
        row = self.row()
        row['inputPreparation'] = None
        row['formalRequirements']['statusCode'] = 'MISSING'
        row['savedAllocations']['statusCode'] = 'MISSING'
        self.assertEqual(self.review(row)['statusCode'], 'BLOCKED')
        self.assertNotIn('savedQuantityDisplayLabel', self.review(row))

    def test_every_exact_scope_identity_is_required(self):
        for key in self.row()['scope']:
            with self.subTest(key=key):
                row = self.row()
                row['inputPreparation']['quantityPolicy']['exactScope'][key] += 1
                self.assertEqual(self.review(row)['statusCode'], 'BLOCKED')

    def test_unit_reference_cannot_cross_company_plan_route_or_lose_proof(self):
        for key, value in [('sourceCompanyId', 99), ('sourceProductionPlanId', 99),
                ('sourceRoutingVersionId', 99), ('uomId', None), ('proofHash', '')]:
            with self.subTest(key=key):
                row = self.row()
                row['inputPreparation']['quantityPolicy']['statisticalUomReference'][key] = value
                self.assertEqual(self.review(row)['statusCode'], 'BLOCKED')

    def test_numeric_zero_or_actual_quantity_or_execution_grant_cannot_enter_policy_branch(self):
        for key in ('plannedQuantity', 'actualQuantity'):
            row = self.row()
            row['inputPreparation']['quantityPolicy'][key] = 0
            self.assertEqual(self.review(row)['statusCode'], 'BLOCKED')
        for key in ('formalRulePublished', 'readyForGeneration', 'readyForAllocation', 'readyForScheduling'):
            row = self.row()
            row['inputPreparation'][key] = True
            self.assertEqual(self.review(row)['statusCode'], 'BLOCKED')

    def test_read_failure_existing_record_and_other_blocker_are_never_hidden(self):
        row = self.row()
        row['formalRequirements']['persistence'].update(readStatus='read_failed', recordCount=None)
        result = self.review(row)
        self.assertEqual(result['statusCode'], 'BLOCKED')
        self.assertIsNone(result['formalRequirementCount'])
        row = self.row()
        row['savedAllocations']['persistence']['recordCount'] = 1
        self.assertEqual(self.review(row)['allocationCount'], 1)
        self.assertEqual(self.review(row)['statusCode'], 'BLOCKED')
        row = self.row()
        row['blockers'] = [{'code': 'SOURCE_PROOF_INVALID', 'statusLabel': '证明失效'}]
        self.assertEqual(self.review(row)['blockers'], row['blockers'])

    def test_quantity_policy_does_not_replace_standard_capacity_units_or_time_references(self):
        row = self.row()
        source = {**row['capacitySemantics'], 'preparationDays': '0.1000',
            'transferDays': '0.1000', 'capacityUomId': 72}
        original = deepcopy(source)
        with patch('pde.daily_capacity_service.scoped_capacity_semantics', return_value=source):
            result, facts = service._step_capacity_semantics(user=None, scope=row['scope'],
                applicability=row['applicability'], source_rules={'status': 'VALID'},
                capacities=[], preparation=row['inputPreparation'])
        self.assertEqual(facts, [])
        self.assertEqual(result, original)
        self.assertNotIn('preparationRulingOnly', result)
        self.assertEqual(result['capacityUomId'], 72)
        self.assertNotEqual(result['capacityUomId'],
            row['inputPreparation']['quantityPolicy']['statisticalUomReference']['uomId'])
