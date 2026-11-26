"""Native batch isolation and coverage tests; never native result evidence."""
import copy
import unittest
from pathlib import Path
import package_support as p
from closure_batch import build, context_assets, qualified, SHEET
from technical_closure import ARCHIVE, frozen


class BatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = p.read(ARCHIVE / 'RUNNER_MANIFEST.json')
        cls.plan = build(cls.m)
        cls.family, cls.cases = p.assets(cls.m)

    def test_historical_native_unchanged(self):
        frozen()

    def test_all_real_rows_and_outputs(self):
        expected = [c for c in self.cases['cases'] if c['level'] in (2, 3)]
        actual = [c for c in self.plan['cases'] if c['cohort'] == 'ORIGINAL_SOURCE_REAL_ROW']
        self.assertEqual({(c['source_sheet'], c['source_row']) for c in expected}, {(c['source_sheet'], c['source_row']) for c in actual})
        self.assertEqual({(c['case_id'], o['cell'], o['formula']) for c in expected for o in c['derived_outputs']}, {(c['case_id'], o['cell'], o['formula']) for c in actual for o in c['derived_outputs']})

    def test_existing_source_cases_not_rewritten(self):
        definitions = {c['case_id']: c for c in self.cases['cases']}
        for case in self.plan['cases']:
            if case['cohort'].startswith('ORIGINAL_SOURCE_'):
                self.assertEqual({k: case[k] for k in definitions[case['case_id']]}, definitions[case['case_id']])

    def test_candidates_only_on_new_sheet(self):
        for case in self.plan['cases']:
            if case['cohort'].startswith('RECOVERY_'):
                self.assertTrue(all(o['cell'].startswith(SHEET + '!') for o in case['derived_outputs']))
        self.assertEqual(self.plan['original_formula_changes'], 0)
        self.assertFalse(self.plan['formula_recovery_applied'])

    def test_no_formula_override_type(self):
        for case in self.plan['cases']:
            for change in case['overrides']:
                self.assertIn(change['type'], ('number', 'text', 'boolean', 'blank'))
                self.assertNotEqual(change['sheet'], SHEET)

    def test_all_candidates_get_native_plan(self):
        expected = {c['family_id'] for c in p.read(Path(self.m['evidence_directory']) / 'CANDIDATE_FORMULA_RECONSTRUCTION.json')}
        actual = {o['candidate_family'] for c in self.plan['cases'] for o in c['derived_outputs'] if 'candidate_family' in o}
        self.assertEqual(actual, expected)

    def test_micro_four_by_four_both_lookups(self):
        case = next(c for c in self.plan['cases'] if c['cohort'] == 'MICRO_SEMANTICS')
        for fn in ('MATCH', 'VLOOKUP'):
            for a in ('BLANK_CELL', 'EMPTY_STRING', 'ZERO', 'FALSE'):
                for b in ('BLANK_CELL', 'EMPTY_STRING', 'ZERO', 'FALSE'):
                    self.assertIn(fn + '_' + a + '_TO_' + b, {o['semantic_name'] for o in case['derived_outputs']})

    def test_blank_is_physically_absent(self):
        cells = {c['cell']: c for c in self.plan['probe_sheet']['cells']}
        self.assertNotIn('D1', cells)
        self.assertNotIn('G1', cells)
        self.assertEqual(cells['D2']['formula'], '=""')
        self.assertEqual(type(cells['D3']['value']), int)
        self.assertEqual(type(cells['D4']['value']), bool)

    def test_qualify_only_local_reference(self):
        self.assertEqual(qualified('=IF(A1="A1",\'other\'!B1,C1)', 'source'), '=IF(\'source\'!A1="A1",\'other\'!B1,\'source\'!C1)')

    def test_identity_unique(self):
        self.assertEqual(len(self.plan['cases']), len({c['case_id'] for c in self.plan['cases']}))
        for c in self.plan['cases']:
            self.assertEqual(len(c['derived_outputs']), len({o['cell'] for o in c['derived_outputs']}))
            self.assertEqual(len(c['overrides']), len({(o['sheet'], o['cell']) for o in c['overrides']}))

    def test_no_expected_results_used_as_oracle(self):
        for c in self.plan['cases']:
            if c['cohort'] not in ('ORIGINAL_SOURCE_REAL_ROW', 'ORIGINAL_SOURCE_REMAINING_LEVEL1', 'NATIVE_SOURCE_INTERMEDIATES'):
                self.assertNotIn('expected_result', c)
        self.assertFalse(self.plan['cached_values_are_oracle'])

    def test_probe_context_source_unchanged(self):
        plan = self.plan | {'workbook_copy': self.m['source']}
        book, mapping, functions = context_assets(self.m, plan)
        self.assertEqual(book.sheets['三合一生产单']['AA7']['formula'], '=IF(AND(J7<=2440,L7=40),#REF!)')
        self.assertIn(SHEET, book.sheets)
        from generated_reference import FUNCTIONS
        self.assertEqual(len(FUNCTIONS), 112)

    def test_micro_context_executable_not_native_certified(self):
        micro = next(c for c in self.plan['cases'] if c['cohort'] == 'MICRO_SEMANTICS')
        rows = p.evaluate_reference(self.m, self.plan | {'workbook_copy': self.m['source'], 'cases': [micro]})
        self.assertTrue(rows)
        self.assertTrue(all(r['reference_status'] == 'EVALUATED_NOT_NATIVE_VERIFIED' for r in rows))

    def test_homologous_readonly_dependencies_executable(self):
        case = next(c for c in self.plan['cases'] if c['cohort'] == 'RECOVERY_AREA_GUARD')
        rows = p.evaluate_reference(self.m, self.plan | {'workbook_copy': self.m['source'], 'cases': [case]})
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r['reference_status'] == 'EVALUATED_NOT_NATIVE_VERIFIED' for r in rows))

    def test_native_missing_probe_proof_rejected(self):
        from test_package import PackageTests
        run, golden, plan = PackageTests().sample()
        plan['probe_sheet'] = {'name': SHEET}
        with self.assertRaises(ValueError):
            p.validate_native(run, golden, plan, 'fixture')


if __name__ == '__main__':
    unittest.main(verbosity=2)
