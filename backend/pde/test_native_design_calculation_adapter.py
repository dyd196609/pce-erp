from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace as N
from unittest.mock import patch
from django.test import SimpleTestCase
from . import native_design_calculation_adapter as adapter
from .engineering_calculation_service import EngineeringCalculationError


class NativeDesignCalculationAdapterTests(SimpleTestCase):
    def setUp(self):
        base=N(pk=10,code='m',company_id=7,dimension='length',conversion_base_id=None,
               conversion_factor=Decimal('1'),is_active=True)
        mm=N(pk=11,code='mm',company_id=7,dimension='length',conversion_base_id=10,
             conversion_base=base,conversion_factor=Decimal('0.001'),is_active=True)
        count=N(pk=12,code='EA',company_id=7,dimension='count',conversion_base_id=None,
                conversion_factor=Decimal('1'),is_active=True)
        self.units=[base,mm,count]
        manager=self.enterContext(patch.object(adapter.UnitOfMeasure,'objects'))
        manager.select_related.return_value.filter.return_value=self.units
        self.contract={'contractVersion':adapter.CONTRACT,'ruleFamily':'ROOM_DOOR','dimensionBasis':'OPENING',
            'structure':'SINGLE_LEAF','paintBranch':'PAINTED','paintProcessTypeId':44,
            'casingDepth':{'value':'150','uomId':11},'horizontalAdd':{'value':'0','uomId':11},
            'verticalAdd':{'value':'0','uomId':11},'lineMode':'SINGLE','quantityBasis':'ORDER_OBJECT_TOTAL',
            'provenance':{'classification':'DEVELOPMENT_TEST_ASSUMPTION','reason':'explicit fixture',
                          'references':['test design revision']},
            'unitProofs':{'targetMmId':11,'units':{str(u.pk):adapter._unit_proof(u) for u in self.units}}}
        self.item={'sourceKey':'pce:native:fixture','sourceIdentity':{'type':'NATIVE_DESIGN_REVISION',
            'companyId':7,'designRevisionId':60},'nativeCalculationInputs':self.contract,
            'baselineItemId':70,'baselineContentHash':'digest','designLength':'2100','designWidth':'900',
            'designThickness':'45','designUomId':11,'physicalQuantity':'5','physicalUomId':12,
            'paintProcessTypeId':44}

    def error(self,code):
        with self.assertRaises(EngineeringCalculationError) as caught: adapter.map_native_input(self.item)
        self.assertEqual(caught.exception.code,code)

    def results(self):
        result=adapter.preview_native_inputs([self.item]);self.assertEqual(result['blockers'],[])
        return {r['column']:r for r in result['rows']}

    def test_independent_room_door_expected_values_and_no_fake_coordinates(self):
        # Independently tabulated arithmetic for opening 2100x900, depth150,
        # painted single leaf: casing2090x880, leaf2057x828; five objects.
        expected={'N':'2090','O':'880','P':'150','Q':'5','R':'2057','S':'828','U':'5',
                  'W':'20.826960','X':'3.795000','Z':'50.600000','AA':'29.700000',
                  'AT':'2100','AU':'1800','AV':'2440','AX':'2440','AW':'10','AY':'5'}
        rows=self.results();self.assertEqual(len(rows),17)
        for key,value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(Decimal(rows[key]['value']),Decimal(value))
                self.assertIsNone(rows[key]['sheet']);self.assertIsNone(rows[key]['row'])
                self.assertIsNone(rows[key]['sourceCell']);self.assertIsNone(rows[key]['expected'])

    def test_quantity_once_dimensions_and_unit_lengths_unchanged(self):
        five=self.results();self.item['physicalQuantity']='1';one=self.results()
        for key in ('N','O','P','R','S','AT','AU','AV','AX'):
            self.assertEqual(five[key]['value'],one[key]['value'])
        for key in ('Q','U','W','X','Z','AA','AW','AY'):
            self.assertEqual(Decimal(five[key]['value']),Decimal(one[key]['value'])*5)

    def test_meter_conversion_is_equivalent_and_repeatable(self):
        initial=adapter.preview_native_inputs([self.item])
        self.item.update(designUomId=10,designLength='2.1',designWidth='0.9')
        self.contract['casingDepth']={'value':'0.15','uomId':10}
        changed=adapter.preview_native_inputs([self.item])
        self.assertEqual([(r['column'],r['value']) for r in initial['rows']],
                         [(r['column'],r['value']) for r in changed['rows']])
        self.assertEqual(changed,adapter.preview_native_inputs([self.item]))

    def test_missing_add_not_defaulted_to_zero(self):
        del self.contract['horizontalAdd'];self.error('NATIVE_CALCULATION_INPUT_REQUIRED')

    def test_unsupported_structure_not_inferred_from_name(self):
        self.contract['structure']='DOUBLE_LEAF';self.error('NATIVE_CALCULATION_STRUCTURE_UNSUPPORTED')

    def test_thickness_is_not_casing_depth(self):
        self.item['designThickness']='99999'
        self.assertEqual(Decimal(self.results()['P']['value']),Decimal('150'))

    def test_unknown_paint_branch_and_wrong_reference_rejected(self):
        self.contract['paintBranch']='QSKF';self.error('NATIVE_CALCULATION_PAINT_BRANCH_REQUIRED')
        self.contract['paintBranch']='PAINTED';self.contract['paintProcessTypeId']=99
        self.error('NATIVE_CALCULATION_PAINT_REFERENCE_MISMATCH')

    def test_unit_scope_drift_and_precision_rejected(self):
        self.units[0].company_id=8;self.error('NATIVE_CALCULATION_UNIT_INVALID')
        self.units[0].company_id=7
        self.item.update(designUomId=10,designLength='2.1000000001')
        self.error('NATIVE_CALCULATION_UNIT_PRECISION_REQUIRED')

    def test_null_boolean_nonfinite_negative_and_fractional_count_rejected(self):
        for value in (None,True,'NaN','Infinity','-1','1.5'):
            with self.subTest(value=value):
                self.item['physicalQuantity']=value
                with self.assertRaises(EngineeringCalculationError):adapter.map_native_input(self.item)

    def test_missing_provenance_and_untrusted_unit_proofs_rejected(self):
        self.contract['provenance']={};self.error('NATIVE_CALCULATION_PROVENANCE_REQUIRED')
        with self.assertRaises(EngineeringCalculationError):adapter.normalize_contract(self.contract)

    def test_paint_free_and_casing_use_existing_rule_branches(self):
        self.contract['paintBranch']='PAINT_FREE';rows=self.results()
        self.assertEqual(Decimal(rows['R']['value']),Decimal('2062'))
        self.assertEqual(Decimal(rows['S']['value']),Decimal('838'))
        self.contract.update(structure='SINGLE_CASING',dimensionBasis='CASING')
        rows=self.results();self.assertEqual(Decimal(rows['R']['value']),0)
        self.assertEqual(Decimal(rows['AA']['value']),0)

    def test_exceeding_governed_cut_tier_is_a_missing_result(self):
        self.item['designLength']='3700'
        rows=self.results();self.assertEqual(rows['AV']['state'],'missing')
        self.assertIsNone(rows['AV']['value'])

    def test_mixed_scope_counts_native_and_imported_positions(self):
        from . import formal_engineering_continuation_service as service
        imported={'sourceKey':'real-sheet:2','sourceIdentity':{'type':'EXCEL_SOURCE_ROW'}}
        with patch.object(service,'run_batch',return_value={'rows':[{'state':'calculated','value':'1'}],
                'batchFingerprint':'legacy','inputRevisionHash':'legacy-input'}):
            result=service._preview_baseline_inputs([self.item['sourceKey'],'real-sheet:2'],[self.item,imported],None)
        self.assertEqual(result['resultPositionCount'],18)
