"""Partial evidence and continuation contracts. No Excel instantiation."""
import copy
import unittest
from recovery_native_r4 import p, ARCHIVE, OUT, verify_prefix


class PrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_dir=p.ROOT/'runs/20260909T040440577Z-a6fb1daa'
        cls.native_run=p.read(cls.run_dir/'NATIVE_EXCEL_RUN.json')
        cls.golden=p.read(cls.run_dir/'EXCEL_NATIVE_GOLDEN.json')
        cls.plan=p.read(cls.run_dir/'RUN_CASE_PLAN.json')

    def fixture(self):
        g=copy.deepcopy(self.golden)
        g['results']=g['results'][:1]
        r=copy.deepcopy(self.native_run)
        r['result_count']=1
        return r,g,self.plan

    def test_partial_run_never_whole_pass(self):
        with self.assertRaises(ValueError):
            p.validate_native(self.native_run,self.golden,self.plan,p.digest(self.run_dir/'RUN_CASE_PLAN.json'))

    def test_valid_committed_prefix(self):
        self.assertEqual(len(verify_prefix(*self.fixture())[0]),1)

    def test_missing_restore_rejected(self):
        r,g,plan=self.fixture(); g['results'][0]['restored']=False
        with self.assertRaises(ValueError): verify_prefix(r,g,plan)

    def test_formula_drift_rejected(self):
        r,g,plan=self.fixture(); g['results'][0]['outputs'][0]['formula']='=12345'
        with self.assertRaises(ValueError): verify_prefix(r,g,plan)

    def test_nonprefix_capture_rejected(self):
        r,g,plan=self.fixture(); g['results'][0]=copy.deepcopy(self.golden['results'][1])
        with self.assertRaises(ValueError): verify_prefix(r,g,plan)

    def test_corrupt_source_rejected(self):
        r,g,plan=self.fixture(); r['source_sha_after']='changed'
        with self.assertRaises(ValueError): verify_prefix(r,g,plan)

    def test_wrong_case_timestamp_rejected(self):
        r,g,plan=self.fixture(); g['results'][0]['calculation_end']='2099-01-01T00:00:00+00:00'
        with self.assertRaises(ValueError): verify_prefix(r,g,plan)

    def test_resume_same_formula_and_only_missing_cases(self):
        m=p.read(p.ROOT/'RUNNER_MANIFEST.json')
        result=p.build_supplement(m)
        self.assertEqual(result['cases'],self.plan['cases'][1537:])
        self.assertEqual(result['probe_sheet'],self.plan['probe_sheet'])
        self.assertEqual(len(result['cases']),191)
        self.assertEqual(result['selected_output_count'],9741)

    def test_resume_tampered_prefix_rejected(self):
        m=copy.deepcopy(p.read(p.ROOT/'RUNNER_MANIFEST.json'))
        m['native_resume']['verified_prefix_cases']=1536
        with self.assertRaises(ValueError): p.build_supplement(m)

    def test_compare_uses_same_plan_authority(self):
        text=(p.ROOT/'package_support.py').read_text('utf-8')
        self.assertIn('expected = build_supplement(m)', text)
        self.assertIn('supplement = build_supplement(m)', text)


if __name__=='__main__': unittest.main()
