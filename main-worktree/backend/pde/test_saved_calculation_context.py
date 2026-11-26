import copy
import unittest
from .saved_calculation_context import project_saved_context, _hash


class SavedCalculationContextTests(unittest.TestCase):
    def fixture(self):
        contract={'dimensionBasis':'OPENING','structure':'SINGLE_LEAF','paintBranch':'PAINTED','casingDepth':{'value':'150','uomId':15},
                  'unitProofs':{'units':{'15':{'code':'mm'}}}}
        design={'id':70,'itemName':'受控测试门','physicalQuantity':'5','physicalUom':'扇'}
        revision={'id':90,'revision':2,'designLength':'2100','designWidth':'900','designThickness':'45','designUomId':15,
                  'paintProcessTypeId':12,'designData':{'calculationInputs':contract}}
        source={'recordId':40,'sourceVersion':'SOURCE-A','rawValue':{'product':'房门','designUomLabel':'mm'}}
        snapshot={'designItem':design,'revision':revision,'source':source};h=_hash(snapshot)
        identity={'type':'NATIVE_DESIGN_REVISION','companyId':3,'salesOrderId':10,'salesOrderItemId':20,'sourceRecordId':40,
                  'designItemId':70,'designRevisionId':90,'designRevision':2,'baselineId':50,'baselineItemId':60}
        inp={**{k:v for k,v in revision.items() if k not in ('id','designData')},'baselineContentHash':h,'sourceIdentity':identity,
             'sourceRecordId':40,'physicalQuantity':'5','physicalUom':'扇','productCategoryId':1,'nativeCalculationInputs':contract}
        obj={'baselineItemId':60,'designItemId':70,'designItemNo':'DES-A','sourceKey':'native-key','sourceVersion':'SOURCE-A','contentHash':h,'input':inp}
        record={'id':100,'calculationNo':'CALC-A','revision':1,'companyId':3,'salesOrderItemId':20,'orderEngineeringInstanceId':30,'sourceRecordId':40,
                'trace':{'baselineReference':{'id':50,'orderId':10,'orderNo':'ORDER-A','baselineNo':'BASE-A'},'sourceReference':{'id':40,'sourceVersion':'SOURCE-A'},
                         'salesOrderItemId':20,'orderEngineeringInstanceId':30,'objectInputSnapshot':[obj],
                         'resultSnapshot':[{'sourceKey':'native-key','canonicalField':'R','value':{'decimal':'2057'},'unit':'mm'}]}}
        item={'id':60,'companyId':3,'baselineId':50,'salesOrderId':10,'sourceRecordId':40,'designItemId':70,'contentHash':h,'snapshot':snapshot,'designRevisionId':90}
        return record,[item]

    def test_frozen_input_and_saved_output_have_separate_semantics_and_no_expansion(self):
        record,items=self.fixture();before=copy.deepcopy((record,items));context=project_saved_context(record,items);row=context['rows'][0]
        values={d['key']:(d['value'],d['unit']) for d in row['dimensionSemantics']}
        self.assertEqual(values['inputHeight'],('2100','mm'));self.assertEqual(values['resultR'],('2057','mm'))
        self.assertEqual(values['actualThickness'],('45','mm'));self.assertEqual(values['inputCasingDepth'],('150','mm'))
        self.assertEqual(row['quantity'],'5');self.assertEqual(row['revision'],2);self.assertEqual(context['calculationRevision'],1)
        self.assertEqual(row['sourceLocationLabel'],'不适用／原生设计来源');self.assertIn('ID 12',row['paintProcess'])
        self.assertEqual((record,items),before)

    def test_repeat_reads_identical_and_current_data_cannot_substitute(self):
        record,items=self.fixture();a=project_saved_context(record,items)
        record['currentDesign']={'revision':999,'designLength':'99999'}
        self.assertEqual(a,project_saved_context(record,items))

    def test_company_line_source_revision_and_fingerprint_conflicts_reject(self):
        for key,value in [('companyId',99),('baselineId',99),('salesOrderId',99),('sourceRecordId',99),('designRevisionId',99),('contentHash','bad')]:
            with self.subTest(key=key):
                record,items=self.fixture();items[0][key]=value
                with self.assertRaises(ValueError):project_saved_context(record,items)
        record,items=self.fixture();record['trace']['salesOrderItemId']=999
        with self.assertRaises(ValueError):project_saved_context(record,items)

    def test_missing_or_changed_frozen_input_does_not_guess(self):
        for mutate in [lambda r,i:i.clear(),lambda r,i:i[0]['snapshot']['revision'].update(designThickness='150'),
                       lambda r,i:r['trace']['objectInputSnapshot'][0]['input'].update(designLength='0')]:
            record,items=self.fixture();mutate(record,items)
            with self.assertRaises(ValueError):project_saved_context(record,items)

    def test_imported_source_preserves_real_locator_and_does_not_become_native(self):
        record,items=self.fixture();inp=record['trace']['objectInputSnapshot'][0]['input']
        inp.update(sourceIdentity={'type':'EXCEL_SOURCE_ROW'},sourceSheet='房门单',sourceRow=11)
        context=project_saved_context(record,items);row=context['rows'][0]
        self.assertEqual(row['sourceLocationLabel'],'房门单 第11行');self.assertEqual(row['sourceRow'],11)
        inp['sourceRow']=None
        with self.assertRaisesRegex(ValueError,'IMPORTED_LOCATOR_REQUIRED'):project_saved_context(record,items)

    def test_historical_record_without_object_snapshot_is_explicit_unavailable(self):
        record,items=self.fixture();record['trace']={}
        context=project_saved_context(record,[])
        self.assertEqual(context['readStatus'],'unavailable');self.assertEqual(context['rows'],[])

    def test_unproduced_requirements_not_zero_consumption_and_missing_facts_remain(self):
        record,items=self.fixture();context=project_saved_context(record,items)
        self.assertEqual(context['materialStatusLabel'],'本次核算未生成');self.assertEqual(context['operationStatusLabel'],'本次核算未生成')
        self.assertIn('正式材料身份',context['rows'][0]['remainingConfirmations'])
        self.assertIsNone(context['rows'][0]['materialId'])


if __name__=='__main__':unittest.main()
