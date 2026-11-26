"""Focused contract tests; native isolated execution supplies integration proof."""
from copy import deepcopy
from types import SimpleNamespace as Obj
from unittest.mock import patch

from django.test import SimpleTestCase

from .engineering_rule_foundation import specification_hash
from .material_requirement_version_continuation_service import (
    MaterialRequirementVersionContinuationService, _bind_fact_pairs, _contract_for, _material_contract,
)
from .saved_fact_material_requirement_service import SERVICE_CODE, SavedFactMaterialRequirementError


def fact(pk, *, design=8, code='N', unit=3, unit_code='mm'):
    return Obj(pk=pk, canonical_field=code, fact_code=f'DES-8:{code}',
        trace={'designItemId': design, 'designItemNo': 'DES-8'},
        uom_id=unit, uom=Obj(code=unit_code) if unit else None)


class MaterialVersionContinuationTests(SimpleTestCase):
    inputs = [{'canonicalName': 'N', 'unit': 'mm'}]

    def bind(self, previous, current):
        return _bind_fact_pairs(previous=previous, current=current,
            design_item_id=8, design_item_no='DES-8', inputs=self.inputs)

    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(SavedFactMaterialRequirementError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_match_uses_identity_and_field_not_position(self):
        previous = [fact(2, code='S'), fact(1)]
        current = [fact(12), fact(13, code='S')]
        pairs = self.bind(previous, current)
        self.assertEqual([(a.pk, b.pk) for _, a, b in pairs], [(1, 12)])

    def test_same_name_other_design_is_rejected(self):
        self.assert_code('MATERIAL_CONTINUATION_FACT_NOT_UNIQUE',
            self.bind, [fact(1)], [fact(12, design=9)])

    def test_duplicate_canonical_fact_is_rejected(self):
        self.assert_code('MATERIAL_CONTINUATION_FACT_NOT_UNIQUE',
            self.bind, [fact(1)], [fact(12), fact(13)])

    def test_same_unit_label_other_fk_is_rejected(self):
        self.assert_code('MATERIAL_CONTINUATION_FACT_MISMATCH',
            self.bind, [fact(1)], [fact(12, unit=4)])

    def test_changed_unit_label_is_rejected(self):
        self.assert_code('MATERIAL_CONTINUATION_FACT_MISMATCH',
            self.bind, [fact(1)], [fact(12, unit_code='m')])

    def test_same_id_changed_design_number_is_rejected(self):
        changed = fact(12)
        changed.trace['designItemNo'] = 'DES-OTHER'
        self.assert_code('MATERIAL_CONTINUATION_FACT_MISMATCH', self.bind, [fact(1)], [changed])

    def material(self):
        material = Obj(pk=9, code='MAT-9', specification='25 mm', is_active=True,
            base_uom_id=3, base_uom=Obj(code='m', is_active=True))
        requirement = Obj(pk=41, material_id=9, uom_id=3, quantity_basis='ORDER_TOTAL',
            item_role='material', requirement_type='manufacturing', supply_type='BUY',
            order_specification={'materialCode': 'MAT-9', 'materialSpecification': '25 mm'})
        output = {'resultDomain': 'MATERIAL_REQUIREMENT', 'materialId': 9,
            'materialCode': 'MAT-9', 'outputUom': 'm', 'quantityBasis': 'ORDER_TOTAL',
            'itemRole': 'material', 'requirementType': 'manufacturing', 'supplyType': 'BUY',
            'orderSpecification': deepcopy(requirement.order_specification)}
        rule = Obj(specification={'outputs': [output]})
        requirement.trace = {'serviceCode': SERVICE_CODE,
            'mappingSpecificationHash': specification_hash(rule.specification)}
        return requirement, rule, material

    def test_frozen_material_contract_is_reused(self):
        requirement, rule, material = self.material()
        self.assertEqual(_material_contract(requirement, rule, material), rule.specification['outputs'][0])

    def test_changed_material_specification_is_rejected(self):
        requirement, rule, material = self.material()
        material.specification = '50 mm'
        self.assert_code('MATERIAL_CONTINUATION_MATERIAL_MISMATCH',
            _material_contract, requirement, rule, material)

    def test_changed_material_identity_is_rejected(self):
        requirement, rule, material = self.material()
        material.pk = 10
        self.assert_code('MATERIAL_CONTINUATION_MATERIAL_MISMATCH',
            _material_contract, requirement, rule, material)

    def test_changed_frozen_mapping_hash_is_rejected(self):
        requirement, rule, material = self.material()
        rule.specification['outputs'][0]['supplyType'] = 'MAKE'
        self.assert_code('MATERIAL_CONTINUATION_MAPPING_UNPROVEN',
            _material_contract, requirement, rule, material)

    @patch('pde.material_requirement_version_continuation_service._source_snapshot', return_value={})
    @patch('pde.material_requirement_version_continuation_service.evaluate_specification', return_value={'value': '1'})
    def test_structural_policy_survives_two_source_continuations(self, evaluate, snapshot):
        policy = 'STRUCTURE_REQUIREMENT_DOES_NOT_REPLACE_DESIGN_PRIMARY_MATERIAL'
        provenance = {'designMaterialReferencePolicy': policy, 'sourceFactCodes': ['N']}
        requirement = Obj(pk=41, material_id=9, material=Obj(code='MAT-9'), uom=Obj(code='m'),
            quantity_basis='ORDER_TOTAL', item_role='material', requirement_type='manufacturing',
            supply_type='BUY', scrap_rate=None, order_specification={},
            trace={'mappingNo': 'MRC-9', 'designItemId': 8, 'designItemNo': 'DES-8'},
            _meta=Obj(concrete_fields=[]))
        rule = Obj(pk=61, rule_code='MRC-9', rule_name='structural material', version='V1',
            specification={'expression': 'N', 'provenance': provenance})
        continuation = Obj(company_id=1, sales_order_item_id=7, engineering_instance_id=2,
            previous_calculation_id=3, new_calculation_id=4, baseline_id=5,
            previous_calculation=Obj(), new_calculation=Obj(),
            sales_order_item=Obj(sales_order=Obj(order_no='SO-9')))
        old, new = fact(1), fact(12)
        new.value = {'decimal': '1'}
        output = {'canonicalName': 'material_quantity', 'sourceFactCode': 'N',
            'structureRole': 'STRUCTURAL_MATERIAL', 'unitDimension': 'length'}
        def continued():
            return _contract_for(requirement=requirement, rule=rule, output=output,
                pairs=[({'canonicalName': 'N', 'unit': 'mm', 'unitDimension': 'length'}, old, new)],
                continuation=continuation, proof={}, authorization_reference='USER', idempotency_key='REQ')
        first = continued()
        self.assertFalse(first.require_design_material_reference)
        self.assertEqual(first.provenance['designMaterialReferencePolicy'], policy)
        # The next version reads the first version's actual provenance, rather
        # than relying on the original rule still being passed by the caller.
        rule.version, rule.specification['provenance'] = first.mapping_version, first.provenance
        continuation.previous_calculation_id, continuation.new_calculation_id = 4, 6
        second = continued()
        self.assertFalse(second.require_design_material_reference)
        self.assertEqual(second.provenance['designMaterialReferencePolicy'], policy)
        second.provenance['sourceFactCodes'].append('S')
        self.assertEqual(first.provenance['sourceFactCodes'], ['N'])
        self.assertEqual(provenance['sourceFactCodes'], ['N'])

    @patch('pde.material_requirement_version_continuation_service.apply_saved_fact_material_requirement')
    @patch('pde.material_requirement_version_continuation_service._prepare')
    def test_complete_batch_delegates_and_native_replay_is_preserved(self, prepare, apply):
        contracts = [Obj(key=1), Obj(key=2)]
        prepare.return_value = (contracts, {'contextHash': 'frozen', 'requirementCount': 2})
        apply.return_value = {'idempotent': True, 'businessWriteCount': 0}
        result = MaterialRequirementVersionContinuationService.apply.__wrapped__(
            user=Obj(company_id=1), continuation_id=1, authorization_reference='USER',
            idempotency_key='REQ', expected_context_hash='frozen')
        self.assertEqual(apply.call_count, 2)
        self.assertEqual([call.kwargs['contract'] for call in apply.call_args_list], contracts)
        self.assertTrue(result['idempotentReplay'])
        self.assertEqual(result['businessWriteCount'], 0)

    @patch('pde.material_requirement_version_continuation_service.apply_saved_fact_material_requirement')
    @patch('pde.material_requirement_version_continuation_service._prepare')
    def test_stale_batch_writes_nothing(self, prepare, apply):
        prepare.return_value = ([Obj()], {'contextHash': 'changed'})
        self.assert_code('MATERIAL_CONTINUATION_STALE_PREVIEW',
            MaterialRequirementVersionContinuationService.apply.__wrapped__,
            user=Obj(company_id=1), continuation_id=1, authorization_reference='USER',
            idempotency_key='REQ', expected_context_hash='old')
        apply.assert_not_called()
