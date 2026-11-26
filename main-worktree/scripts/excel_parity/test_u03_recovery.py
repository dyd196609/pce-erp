"""Technical tests for the isolated recovery package; not Native certification."""
import collections
import unittest
from decimal import Decimal
from pathlib import Path
import package_support as p
from recovery_semantics import resolve, net_area, gross_area, gross_edges
from recovery_batch import build, SHEET
from u03_recovery_audit import OUT, DB, DB_SHA


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.s = [{'material_id': 1, 'length': 2440, 'width': 1220, 'thickness': 18}, {'material_id': 2, 'length': 2800, 'width': 1220, 'thickness': 18}, {'material_id': 3, 'length': 3050, 'width': 1220, 'thickness': 9}]

    def test_minimal_geometry(self):
        self.assertEqual(resolve([100, 100, 18], self.s, [1, 2])['material_id'], 1)

    def test_bigger_only_when_required(self):
        self.assertEqual(resolve([2600, 100, 18], self.s, [1, 2])['material_id'], 2)

    def test_thickness_exact(self):
        self.assertEqual(resolve([100, 100, 17.9], self.s, [1, 2])['status'], 'BLOCKED_NO_GEOMETRIC_SPEC')

    def test_area_is_not_geometric_fit(self):
        self.assertEqual(resolve([100, 1300, 18], self.s, [1, 2], False)['status'], 'BLOCKED_NO_COMPATIBLE_SPEC')

    def test_rotation_unknown_only_if_affecting(self):
        self.assertEqual(resolve([100, 1300, 18], self.s, [1, 2])['status'], 'U03_DIRECTION_AFFECTS_RESOLUTION')

    def test_rotation_explicit_true(self):
        self.assertEqual(resolve([100, 1300, 18], self.s, [1, 2], True)['material_id'], 1)

    def test_missing_compatibility_not_true(self):
        self.assertEqual(resolve([100, 100, 18], self.s)['status'], 'BLOCKED_MATERIAL_APPLICABILITY')

    def test_duplicate_material_not_arbitrary_id(self):
        self.s.append(self.s[0] | {'material_id': 4})
        self.assertEqual(resolve([100, 100, 18], self.s, [1, 4])['status'], 'BLOCKED_AMBIGUOUS_MATERIAL')

    def test_incomparable_minima_not_area_ranked(self):
        self.s.append({'material_id': 5, 'length': 1800, 'width': 1400, 'thickness': 18})
        self.assertEqual(resolve([100, 100, 18], self.s, [1, 5])['status'], 'BLOCKED_AMBIGUOUS_MATERIAL')

    def test_no_nearest_fit(self):
        self.assertEqual(resolve([10000, 100, 18], self.s, [1, 2])['status'], 'BLOCKED_NO_GEOMETRIC_SPEC')

    def test_invalid_dimensions(self):
        self.assertEqual(resolve([0, 100, 18], self.s, [1, 2])['status'], 'BLOCKED_NO_GEOMETRIC_SPEC')

    def test_area_not_sheet_count(self):
        self.assertEqual(net_area(732, 150, 1), Decimal('0.1098'))

    def test_area_zero_quantity(self):
        self.assertEqual(net_area(732, 150, 0), 0)

    def test_area_loss_is_separate_parameter(self):
        self.assertEqual(gross_area(10, '.20'), 12)
        self.assertEqual(gross_area(10, '.05'), Decimal('10.50'))

    def test_area_loss_missing_is_not_zero(self):
        self.assertIsNone(gross_area(10, None))
        self.assertEqual(gross_area(10, 0), 10)

    def test_invalid_area_loss(self):
        with self.assertRaises(ValueError):
            gross_area(10, -1)

    def test_edge_allowance_per_edge_not_percentage(self):
        self.assertEqual(gross_edges([1000, 500], 2, 20), Decimal('3.08'))

    def test_edge_missing_not_zero(self):
        self.assertIsNone(gross_edges([1000], 1, None))
        self.assertEqual(gross_edges([1000], 1, 0), 1)

    def test_negative_edge_allowance(self):
        with self.assertRaises(ValueError):
            gross_edges([1000], 1, -1)


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = p.read(p.ROOT / 'RUNNER_MANIFEST.json')
        cls.plan = build(cls.m)

    def test_all_real_rows_unchanged(self):
        original = [c for c in p.assets(self.m)[1]['cases'] if c['level'] in (2, 3)]
        present = {c['case_id']: c for c in self.plan['cases']}
        self.assertEqual(len(original), 71)
        for c in original:
            self.assertEqual(c['derived_outputs'], present[c['case_id']]['derived_outputs'])

    def test_all_existing_boundaries(self):
        original = [c for c in p.assets(self.m)[1]['cases'] if c['level'] == 1]
        present = {c['case_id'] for c in self.plan['cases']}
        self.assertTrue(all(c['case_id'] in present for c in original))

    def test_all_36_controls(self):
        self.assertEqual(sum(c['cohort'] == 'R1_OLD_CANDIDATE_SEMANTIC_COUNTEREXAMPLE' for c in self.plan['cases']), 36)

    def test_all_12_summary_families(self):
        self.assertEqual(len(self.plan['summary_family_projections']), 12)

    def test_error_capture_gap_included(self):
        traces = [c for c in self.plan['cases'] if c['cohort'] == 'NATIVE_SOURCE_INTERMEDIATES']
        self.assertEqual(len(traces), 11)
        self.assertEqual(sum(o['cell'] in ['房门单!' + a for a in ('AT30', 'AV30', 'AW30', 'AY30')] for c in traces for o in c['derived_outputs']), 44)

    def test_actual_dynamic_formal_universe(self):
        a = p.read(OUT / 'BOARD_STOCK_AND_REAL_ROW_AUDIT.json')
        self.assertEqual(a['summary']['formal_stock_candidates'], 66)
        self.assertIn(3050, a['summary']['formal_stock_lengths'])
        self.assertIn(4100, a['summary']['formal_stock_lengths'])

    def test_production_hash_unchanged(self):
        self.assertEqual(p.digest(DB), DB_SHA)

    def test_source_formula_write_zero(self):
        self.assertFalse(self.plan['formula_recovery_applied'])
        self.assertEqual(self.plan['original_formula_changes'], 0)

    def test_unique_and_excel_limits(self):
        ids = [c['case_id'] for c in self.plan['cases']]
        self.assertEqual(len(ids), len(set(ids)))
        for d in self.plan['probe_sheet']['cells']:
            if d['type'] == 'formula':
                self.assertLess(len(d['formula']), 8192)

    def test_no_guessed_formal_material_assignment(self):
        self.assertEqual(self.plan['board_business_status'], 'BLOCKED_FORMAL_MATERIAL_APPLICABILITY_AND_SPEC_GAPS')
        self.assertEqual(p.read(OUT / 'BOARD_STOCK_AND_REAL_ROW_AUDIT.json')['summary']['direction_affected_real_rows'], 0)

    def test_ledger_reference_not_cache(self):
        plan = self.plan | {'workbook_copy': self.m['source'], 'cases': [c for c in self.plan['cases'] if c['cohort'] == 'R4_R5_R6_AGGREGATE_LEDGER']}
        results = p.evaluate_reference(self.m, plan)
        self.assertTrue(all(r['reference_status'] == 'EVALUATED_NOT_NATIVE_VERIFIED' for r in results))
        self.assertEqual(len(results), 6)
        self.assertTrue(all(r['code_result']['type'] != 'error' for r in results))
        by_name = {r['semantic_name']: r['code_result']['value'] for r in results}
        self.assertEqual(by_name['VISIBLE_AREA_EMPTY_SOURCE_COUNT'], 1)
        self.assertEqual(by_name['EDGE_APPLICABILITY_MISSING_SOURCE_COUNT'], 4)

    def test_whole_selection_to_aggregation_chain(self):
        selected = [c for c in self.plan['cases'] if c['case_id'] in ('U03_SYNTHETIC_ROTATED_ONLY', 'U03_SYNTHETIC_UNKNOWN_APPLICABILITY')]
        results = p.evaluate_reference(self.m, self.plan | {'workbook_copy': self.m['source'], 'cases': selected})
        lookup = {(r['case_id'], r['semantic_name']): r['code_result']['value'] for r in results}
        self.assertEqual(lookup[('U03_SYNTHETIC_ROTATED_ONLY', 'SYNTHETIC_SELECTION_TO_NET_TO_BUCKET_AGGREGATE')], 14.399999999999999)
        self.assertEqual(lookup[('U03_SYNTHETIC_UNKNOWN_APPLICABILITY', 'SYNTHETIC_SELECTION_TO_NET_TO_BUCKET_AGGREGATE')], 'BLOCKED_UNRESOLVED_REQUIREMENTS')

    def test_width_counterexample_neither_direction_fits(self):
        stock = p.read(OUT / 'BOARD_STOCK_AND_REAL_ROW_AUDIT.json')['stocks']
        for c in self.plan['cases']:
            if c['cohort'] == 'R1_OLD_CANDIDATE_SEMANTIC_COUNTEREXAMPLE':
                width = next(o['value'] for o in c['overrides'] if o['sheet'] == '三合一生产单' and o['cell'].startswith('K'))
                self.assertGreater(width, max(max(s['length'], s['width']) for s in stock))

    def test_snapshot_before_code_integrity(self):
        for row in p.read(OUT / 'BEFORE_CODE_MANIFEST.json'):
            self.assertEqual(p.digest(row['archive']), row['sha256'])


if __name__ == '__main__':
    unittest.main()
