"""Reuse existing pure/API suite without overwriting previous phase evidence."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'backend/venv/Lib/site-packages'))
import test_semi_finished_configuration as previous
from semi_finished_role_layer import OUT, save
previous.OUT=OUT
from pde.semi_finished_configuration_validation import apply_validation,load_evidence,formal_fingerprint

class LayerProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        previous.ConfigurationProjectionTests.setUpClass()
        cls.base=previous.ConfigurationProjectionTests.result
        cls.formal=previous.ConfigurationProjectionTests.formal
    def test_current_correction_and_pending_ui(self):
        p=apply_validation(self.base,formal=self.formal)
        self.assertEqual(p['summary']['isolatedRoleCount'],6)
        self.assertEqual(p['roleLayerSummary']['userManualValidation'],'PENDING')
        self.assertTrue(all(not c['roleLayerUserValidated'] for c in p['configurations']))
    def test_no_stale_composition_role(self):
        p=apply_validation(self.base)
        self.assertTrue(all(c['role'] not in {'封边材料','其它固定组成'} for c in p['compositionTrace']))
    def test_thickness_gate_replaced(self):
        p=apply_validation(self.base)
        self.assertEqual(p['summary']['thicknessSemantics'],'BOARD_MATCH_INPUT_COLUMN_L')
        self.assertTrue(all(r['semantic']=='BOARD_MATCH_INPUT' and r['rawBoardExactMatchAllowed'] for r in p['thicknessAnalysis']))
    def test_frozen_only_two_configs(self):
        p=apply_validation(self.base)
        self.assertEqual(sum(c['userValidated'] for c in p['configurations']),2)
        self.assertEqual(p['summary']['otherValidNotUserValidatedCount'],56)
    def test_source_drift_rejected(self):
        b=copy.deepcopy(self.base)
        next(c for c in b['configurations'] if c['sourceCode']=='BTKF2601001')['attributes'][0]['sourceValue']='drift'
        with self.assertRaises(ValueError):apply_validation(b)
    def test_formal_spec_drift_rejected(self):
        formal=copy.deepcopy(self.formal);formal['materials'][0]['specification']='changed'
        with self.assertRaisesRegex(ValueError,'FORMAL_INPUT_DRIFT'):apply_validation(self.base,formal=formal)
    def test_seal_drift_rejected(self):
        with patch('pde.semi_finished_configuration_validation.EVIDENCE_SHA','wrong'):
            with self.assertRaisesRegex(ValueError,'INTEGRITY_FAILED'):load_evidence()
    def test_identity_case_drift(self):
        evidence=load_evidence();evidence['cases'][0]['formalMaterialId']=999
        with self.assertRaises(ValueError):apply_validation(self.base,evidence=evidence)
    def test_trace_attribute_state_consistency(self):
        p=apply_validation(self.base)
        self.assertEqual(p['attributeTrace'],[a for c in p['configurations'] for a in c['attributes']])
    def test_source_projection_is_not_mutated(self):
        before=copy.deepcopy(self.base);apply_validation(self.base)
        self.assertEqual(before,self.base)
    def test_new_counts_use_existing_server_fact_contract(self):
        p=apply_validation(self.base)
        self.assertEqual([p['summary'][k] for k in ('sourceComponentCount','pendingEdgeRequirementCount',
            'boardExactThicknessMatch','boardExactMatch','boardBlocked','veneerNetPass','veneerNetBlocked')],
            [71,59,31,0,63,70,1])

if __name__=='__main__':
    before=previous.sha(previous.DB)
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(previous.ConfigurationProjectionTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(LayerProjectionTests)])
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    assert result.wasSuccessful()
    api=previous.api_checks()
    assert before==previous.sha(previous.DB)
    save('API_TEST_RESULTS.json',{'unitTests':result.testsRun,'status':'PASS','api':api,'productionBusinessWrite':0,
        'databaseSha256':before,'oldEvidenceOutputsTouched':False})
    print('Projection '+str(result.testsRun)+' tests + API '+str(api['caseCount'])+' cases PASS')
