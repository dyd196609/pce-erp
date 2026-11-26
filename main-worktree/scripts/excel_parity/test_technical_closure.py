"""Technical regression tests. Native microprobe certification is separate."""
import unittest
from types import SimpleNamespace
from formula_ast import Parser, BrokenSource, Unsupported
from reference_runtime import Context, BLANK, ExcelError, exact_lookup, compare


class ClosureTests(unittest.TestCase):
    def context(self, values=None, formulas=None):
        cells = {a: {'formula': None, 'value': v, 'type': 'e' if isinstance(v, str) and v.startswith('#') else 'n'} for a, v in (values or {}).items()}
        cells.update({a: {'formula': f, 'value': None, 'type': 'n'} for a, f in (formulas or {}).items()})
        ctx = Context(SimpleNamespace(sheets={'s': cells}, names=[]), {}, {})
        return ctx

    def evaluate(self, formula, values=None):
        ctx = self.context(values)
        return ctx.source_ast(Parser().parse(formula, allow_broken=True), 's', 1, 1)

    def test_lookup_range_blank_not_zero(self):
        for key in (BLANK, '', 0, False):
            self.assertFalse(exact_lookup(key, BLANK))

    def test_blank_lookup_key_numeric_only(self):
        self.assertTrue(exact_lookup(BLANK, 0))
        self.assertFalse(exact_lookup(BLANK, ''))
        self.assertFalse(exact_lookup(BLANK, False))

    def test_lookup_empty_text_distinct(self):
        self.assertTrue(exact_lookup('', ''))
        self.assertFalse(exact_lookup('', 0))

    def test_lookup_boolean_distinct(self):
        self.assertTrue(exact_lookup(False, False))
        self.assertFalse(exact_lookup(False, 0))

    def test_ordinary_comparison_unchanged(self):
        self.assertEqual(compare(BLANK, 0), 0)
        self.assertEqual(compare(BLANK, ''), 0)

    def test_match_preserves_offset(self):
        self.assertEqual(self.evaluate('=MATCH(D1,A1:A3,0)', {'A3': 0}), 3)

    def test_vlookup_blank_return_still_zero(self):
        self.assertEqual(self.evaluate('=VLOOKUP("key",A1:B1,2,FALSE)', {'A1': 'key'}), 0)

    def test_empty_key_no_fabricated_blank_record(self):
        self.assertEqual(self.evaluate('=IFERROR(MATCH(D1,A1:A3,0),"missing")', {'A1': 'key'}), 'missing')

    def test_unvisited_broken_if_branch(self):
        ctx = self.context(formulas={'A1': '=IF(FALSE,#REF!,7)'})
        self.assertEqual(ctx.cell('s', 'A1'), 7)

    def test_visited_broken_if_branch(self):
        ctx = self.context(formulas={'A1': '=IF(TRUE,#REF!,7)'})
        with self.assertRaises(BrokenSource):
            ctx.cell('s', 'A1')

    def test_unvisited_later_index_argument(self):
        self.assertEqual(self.evaluate('=IFERROR(INDEX(A1:B3,MATCH(D1,A1:A3,0),MATCH(#REF!,A1:B1,0)),"")', {'A1': 'key'}), '')

    def test_visited_later_index_argument_not_hidden(self):
        with self.assertRaises(BrokenSource):
            self.evaluate('=IFERROR(INDEX(A1:B3,MATCH(D1,A1:A3,0),MATCH(#REF!,A1:B1,0)),"")', {'A1': 'key', 'D1': 'key'})

    def test_and_is_not_short_circuit(self):
        with self.assertRaises(BrokenSource):
            self.evaluate('=AND(FALSE,#REF!)')

    def test_or_is_not_short_circuit(self):
        with self.assertRaises(BrokenSource):
            self.evaluate('=OR(TRUE,#REF!)')

    def test_sumifs_criteria_cell_error_nonmatch(self):
        self.assertEqual(self.evaluate('=SUMIFS(B1:B2,A1:A2,"x")', {'A1': '#VALUE!', 'A2': 'x', 'B1': 71, 'B2': 9}), 9)

    def test_sumifs_unmatched_sum_error_not_read(self):
        self.assertEqual(self.evaluate('=SUMIFS(B1:B2,A1:A2,"x")', {'A1': 'y', 'A2': 'x', 'B1': '#DIV/0!', 'B2': 9}), 9)

    def test_sumifs_matched_sum_error_propagates(self):
        with self.assertRaises(ExcelError):
            self.evaluate('=SUMIFS(B1:B2,A1:A2,"x")', {'A1': 'x', 'A2': 'x', 'B1': '#DIV/0!', 'B2': 9})

    def test_sumifs_criteria_argument_error_nonmatch_native_r2(self):
        self.assertEqual(self.evaluate('=SUMIFS(B1:B2,A1:A2,D1)', {'D1': '#DIV/0!', 'A1': 'y', 'A2': 'x', 'B1': 71, 'B2': 9}), 0)

    def test_sumifs_uncaptured_error_to_error_semantics_fail_closed(self):
        with self.assertRaises(Unsupported):
            self.evaluate('=SUMIFS(B1:B2,A1:A2,D1)', {'D1': '#DIV/0!', 'A1': '#DIV/0!', 'B1': 71})

    def test_sumif_error_argument_not_silently_changed(self):
        with self.assertRaises(ExcelError):
            self.evaluate('=SUMIF(A1:A2,D1,B1:B2)', {'D1': '#DIV/0!', 'A1': 'x', 'B1': 71})

    def test_sumifs_shape_still_fail_closed(self):
        with self.assertRaises(Unsupported):
            self.evaluate('=SUMIFS(B1:B2,A1:A3,"x")')

    def test_sumif_reuses_criteria_cell_semantics(self):
        self.assertEqual(self.evaluate('=SUMIF(A1:A2,"x",B1:B2)', {'A1': '#VALUE!', 'A2': 'x', 'B1': 71, 'B2': 9}), 9)


if __name__ == '__main__':
    unittest.main(verbosity=2)
