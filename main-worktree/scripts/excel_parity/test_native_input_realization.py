"""No Excel activation; rejects arbitrary drift and preserves the strict gate."""
import copy
import unittest
from u03_recovery_audit import p, OUT
from native_input_realization import realize, verify_output_invariance


class RealizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d=p.ROOT/'runs/20260909T044309108Z-9c8a8727'
        cls.plan=p.read(d/'RUN_CASE_PLAN.json')
        cls.golden=p.read(d/'EXCEL_NATIVE_GOLDEN.json')
        cls.run_meta=p.read(d/'NATIVE_EXCEL_RUN.json')
        cls.plan_sha=p.digest(d/'RUN_CASE_PLAN.json')
        cls.stocks=p.read(OUT/'BOARD_STOCK_AND_REAL_ROW_AUDIT.json')['stocks']

    def fixture(self):
        idx=next(i for i,c in enumerate(self.plan['cases']) if c['case_id']=='U03_SYNTHETIC_194_F_0.1')
        pl=copy.deepcopy(self.plan); pl['cases']=[pl['cases'][idx]]
        g=copy.deepcopy(self.golden); g['results']=[g['results'][idx]]
        return pl,g

    def test_exact_decimal_realization(self):
        pl,g=self.fixture(); before=copy.deepcopy(pl)
        view,e=realize(pl,g,self.stocks)
        self.assertEqual((e['exact_input_count'],e['realized_input_count']),(7,1))
        self.assertEqual(view['cases'][0]['overrides'][2]['value'],1.9)
        self.assertEqual(pl,before)

    def test_full_real_input_count(self):
        _,e=realize(self.plan,self.golden,self.stocks)
        self.assertEqual((e['exact_input_count'],e['realized_input_count']),(1526,2))

    def test_strict_original_plan_still_rejected(self):
        with self.assertRaises(ValueError): p.validate_native(self.run_meta,self.golden,self.plan,self.plan_sha)

    def test_real_business_input_rejected(self):
        pl,g=self.fixture(); pl['cases'][0]['cohort']='REAL_ROWS'
        with self.assertRaises(ValueError): realize(pl,g,self.stocks)

    def test_wrong_decimal_even_one_ulp_rejected(self):
        pl,g=self.fixture(); g['results'][0]['overrides'][2]['actual']['value']=1.9000000000000004
        with self.assertRaises(ValueError): realize(pl,g,self.stocks)

    def test_other_value_rejected(self):
        pl,g=self.fixture(); g['results'][0]['overrides'][2]['actual']['value']=1.8
        with self.assertRaises(ValueError): realize(pl,g,self.stocks)

    def test_requested_metadata_drift_rejected(self):
        pl,g=self.fixture(); g['results'][0]['overrides'][2]['requested_value']=1.9
        with self.assertRaises(ValueError): realize(pl,g,self.stocks)

    def test_boolean_cannot_be_number(self):
        pl,g=self.fixture(); g['results'][0]['overrides'][4]['actual']={'type':'number','value':0}
        with self.assertRaises(ValueError): realize(pl,g,self.stocks)

    def test_missing_provenance_rejected(self):
        pl,g=self.fixture(); pl['cases'][0].pop('data_provenance')
        with self.assertRaises(ValueError): realize(pl,g,self.stocks)

    def test_incomplete_capture_rejected(self):
        pl,g=self.fixture(); g['results']=[]
        with self.assertRaises(ValueError): realize(pl,g,self.stocks)

    def test_output_branch_change_rejected(self):
        a={'case_id':'x','cell':'b','formula_family':'f','semantic_name':'branch','contract':{},'reference_status':'EVALUATED_NOT_NATIVE_VERIFIED','code_result':{'type':'number','value':1}}
        b=copy.deepcopy(a); b['code_result']['value']=0
        with self.assertRaises(ValueError): verify_output_invariance([a],[b],{'changes':[]})

    def test_blank_zero_text_outputs_not_equivalent(self):
        a={'case_id':'x','cell':'b','formula_family':'f','semantic_name':'branch','contract':{},'reference_status':'EVALUATED_NOT_NATIVE_VERIFIED','code_result':{'type':'blank','value':None}}
        b=copy.deepcopy(a); b['code_result']={'type':'number','value':0}
        with self.assertRaises(ValueError): verify_output_invariance([a],[b],{'changes':[]})


if __name__=='__main__': unittest.main()
