"""Technical token-identity and native-oracle regressions (not synthetic Golden)."""
import unittest
import package_support as p
from pathlib import Path


class FormulaIdentityTests(unittest.TestCase):
    def test_optional_sheet_quotes(self):
        self.assertIsNotNone(p.formula_identity("=SUM('房门单'!$AW:$AW)", '=SUM(房门单!$AW:$AW)'))

    def test_escaped_sheet_apostrophe(self):
        self.assertIsNotNone(p.formula_identity("='a''b'!A1", "='a''b'!A1"))

    def test_function_prefix(self):
        self.assertIsNotNone(p.formula_identity('=_xlfn.IFS(A1,1)', '=IFS(A1,1)'))

    def test_literal_prefix_not_normalized(self):
        self.assertIsNone(p.formula_identity('="_xlfn.IFS"', '="IFS"'))

    def test_literal_quotes_not_normalized(self):
        self.assertIsNone(p.formula_identity('="\'sheet\'!A1"', '="sheet!A1"'))

    def test_cell_drift_rejected(self):
        self.assertIsNone(p.formula_identity("='s'!A1", '=s!A2'))

    def test_anchor_drift_rejected(self):
        self.assertIsNone(p.formula_identity("='s'!$A$1", '=s!A1'))

    def test_operator_drift_rejected(self):
        self.assertIsNone(p.formula_identity("='s'!A1<=1", '=s!A1<1'))

    def test_sheet_drift_rejected(self):
        self.assertIsNone(p.formula_identity("='s'!A1", '=t!A1'))

    def test_argument_order_rejected(self):
        self.assertIsNone(p.formula_identity('=IF(A1,2,3)', '=IF(A1,3,2)'))

    def test_numeric_formula_not_evaluated_to_compare(self):
        self.assertIsNone(p.formula_identity('=1+1', '=2'))


class FrozenNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from native_supplement_closure import RUN, RUN_SHA, ARCHIVE
        p.require(p.digest(RUN / 'RUN_MANIFEST.json') == RUN_SHA, 'FROZEN NATIVE DRIFT')
        p.verify_hashes(p.read(RUN / 'RUN_MANIFEST.json')['files'], RUN)
        cls.plan = p.read(RUN / 'RUN_CASE_PLAN.json')
        cls.m = p.read(ARCHIVE / 'RUNNER_MANIFEST.json')
        cls.native = p.validate_native(p.read(RUN / 'NATIVE_EXCEL_RUN.json'), p.read(RUN / 'EXCEL_NATIVE_GOLDEN.json'), cls.plan, p.digest(RUN / 'RUN_CASE_PLAN.json'))

    def test_all_54_actual_native_micro_outputs(self):
        from native_supplement_closure import compare
        case = next(c for c in self.plan['cases'] if c['cohort'] == 'MICRO_SEMANTICS')
        rows = compare(p.evaluate_reference(self.m, self.plan | {'cases': [case]}), self.native)
        self.assertEqual(len(rows), 54)
        self.assertTrue(all(r['classification'] == 'PARITY_PASS' for r in rows))

    def test_display_hash_error_not_silently_certified(self):
        from native_supplement_closure import compare
        key = next(k for k, v in self.native.items() if v['excel_raw_value']['type'] == 'error' and set(v['excel_raw_value']['value']) == {'#'})
        row = {'case_id': key[0], 'cell': key[1], 'reference_status': 'EVALUATED_NOT_NATIVE_VERIFIED', 'code_result': {'type':'error','value':'#VALUE!'}, 'contract':{}}
        result = compare([row], self.native)[0]
        self.assertEqual(result['classification'], 'NATIVE_ERROR_CODE_UNAVAILABLE')
        self.assertNotEqual(result['excel_raw_value'], result['code_result'])

    def test_missing_capture_not_pass(self):
        from native_supplement_closure import compare
        row = {'case_id':'absent','cell':'s!A1','reference_status':'EVALUATED_NOT_NATIVE_VERIFIED','code_result':{'type':'number','value':1},'contract':{}}
        self.assertEqual(compare([row], {})[0]['classification'], 'NATIVE_CAPTURE_REQUIRED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
