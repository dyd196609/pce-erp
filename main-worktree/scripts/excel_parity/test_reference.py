"""Technical tests only, not Microsoft Excel parity certification."""
import json
import unittest
from types import SimpleNamespace
from workbook_source import SourceBook, OUT, digest, SOURCE, EXPECTED_SHA
from formula_ast import Parser, normalize, functions, Unsupported, BrokenSource, shift_reference
from reference_runtime import Context, Range, BLANK, OMITTED, ExcelError, serialized, compare
from generated_reference import FUNCTIONS
from differential import compare_result


class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book=SourceBook()
        cls.mapping=json.loads((OUT/'FORMULA_FAMILY_INVENTORY.json').read_text(encoding='utf-8'))['cell_to_family']

    def setUp(self):
        self.ctx=Context(self.book,self.mapping,FUNCTIONS)

    def call(self,name,*args):
        return self.ctx.call(name,[lambda a=a:a for a in args],row=11,col=14)

    def test_source_sha(self):self.assertEqual(digest(SOURCE),EXPECTED_SHA)
    def test_normalized_row_family(self):
        p=Parser()
        self.assertEqual(normalize(p.parse('=IF(J11="","",J11-10)'),'N11'),normalize(p.parse('=IF(J12="","",J12-10)'),'N12'))
    def test_absolute_anchors_distinct(self):
        p=Parser()
        self.assertNotEqual(normalize(p.parse('=$J$11'),'N11'),normalize(p.parse('=$J$12'),'N12'))
    def test_quoted_and_absolute_shift(self):self.assertEqual(shift_reference("'油漆目录'!$A1:B$2",2,3),"'油漆目录'!A3:E2")
    def test_broken_not_translated(self):
        with self.assertRaises(BrokenSource):Parser().parse('=IFERROR(#REF!,0)')
    def test_unsafe_rejected(self):
        with self.assertRaises(Unsupported):Parser().parse('=__import__("os").system("whoami")')
    def test_actual_generated_four_fields(self):
        self.assertEqual([self.ctx.cell('房门单',x) for x in ['N11','O11','R11','S11']],[2035,918,2002,866])
    def test_actual_area_extended(self):self.assertEqual(self.ctx.cell('三合一生产单','Q7'),0.1098)
    def test_actual_edge_extended(self):self.assertEqual(self.ctx.cell('三合一生产单','R7'),1.764)
    def test_shifted_same_family(self):self.assertEqual(self.ctx.cell('房门单','O12'),840)
    def test_all_data_types_distinct(self):self.assertEqual(len({serialized(v)['type'] for v in [BLANK,0,False,'']}),4)
    def test_omitted_if_is_zero(self):self.assertIs(self.call('IF',False,1,OMITTED),0)
    def test_missing_if_is_false(self):self.assertIs(self.call('IF',False,1),False)
    def test_if_lazy(self):self.assertEqual(self.ctx.call('IF',[lambda:True,lambda:7,lambda:self.ctx.error('#DIV/0!')],row=1,col=1),7)
    def test_iferror_catches_cell_error(self):self.assertEqual(self.ctx.call('IFERROR',[lambda:self.ctx.error('#N/A'),lambda:'missing'],row=1,col=1),'missing')
    def test_iferror_not_hide_unsupported(self):
        def fail():raise Unsupported('adapter')
        with self.assertRaises(Unsupported):self.ctx.call('IFERROR',[fail,lambda:0],row=1,col=1)
    def test_iferror_not_hide_broken(self):
        def fail():raise BrokenSource('source')
        with self.assertRaises(BrokenSource):self.ctx.call('IFERROR',[fail,lambda:0],row=1,col=1)
    def test_ifs_no_match(self):
        with self.assertRaises(ExcelError):self.call('IFS',False,1,False,2)
    def test_logical_functions(self):self.assertEqual((self.call('AND',True,1),self.call('OR',False,0)),(True,False))
    def test_compare_text_number_boolean(self):self.assertEqual((compare('1',1),compare(True,1),compare(BLANK,0),compare(BLANK,'')),(1,1,0,0))
    def test_comparison_case_insensitive(self):self.assertEqual(compare('abc','ABC'),0)
    def test_arithmetic_text_numeric(self):self.assertEqual(self.ctx.binary('*','2',3),6)
    def test_arithmetic_empty_string_error(self):
        with self.assertRaises(ExcelError):self.ctx.binary('*','',3)
    def test_concat_boolean_blank(self):self.assertEqual(self.ctx.binary('&',True,BLANK),'TRUE')
    def test_round_halves(self):self.assertEqual((self.call('ROUND',2.5,0),self.call('ROUND',-2.5,0)),(3,-3))
    def test_trim_ascii_spaces(self):self.assertEqual(self.call('TRIM','  a   b\u00a0 '),'a b\u00a0')
    def test_left_find(self):self.assertEqual((self.call('LEFT','60*18',2),self.call('FIND','*','60*18')),('60',3))
    def test_concat_char_row(self):self.assertEqual(self.call('CONCAT',self.call('CHAR',10),self.call('ROW')), '\n11')
    def test_text_zero_padding(self):self.assertEqual(self.call('TEXT',7,'000'),'007')
    def test_unknown_text_format_rejected(self):
        with self.assertRaises(Unsupported):self.call('TEXT',7,'[locale]')
    def toy(self):
        cells={a:{'value':v,'type':'n','formula':None} for a,v in {'A1':'x','A2':'y','A3':'x','B1':2,'B2':4,'B3':6}.items()}
        ctx=Context(SimpleNamespace(sheets={'s':cells},names=[]),{}, {})
        return ctx,Range(ctx,'s',1,1,3,1),Range(ctx,'s',1,2,3,2),Range(ctx,'s',1,1,3,2)
    def test_exact_lookup_first_duplicate(self):
        ctx,a,b,table=self.toy()
        self.assertEqual(self.call('VLOOKUP','x',table,2,False),2)
        self.assertEqual(self.call('MATCH','x',a,0),1)
    def test_lookup_no_text_number_coercion(self):
        ctx,a,b,table=self.toy()
        with self.assertRaises(ExcelError):self.call('MATCH','2',b,0)
    def test_index_sum_countif(self):
        ctx,a,b,table=self.toy()
        self.assertEqual((self.call('INDEX',table,3,2),self.call('SUM',b),self.call('COUNTIF',a,'x')),(6,12,2))
    def test_sumif_sumifs(self):
        ctx,a,b,table=self.toy()
        self.assertEqual((self.call('SUMIF',a,'x',b),self.call('SUMIFS',b,a,'x')),(8,8))
    def test_full_column_retains_shape(self):
        rng=self.ctx.reference('J:J','房门单')
        self.assertEqual(rng.shape,(1048576,1))
    def test_integer_diff_not_tolerated(self):self.assertEqual(compare_result({'type':'number','value':10.1},{'type':'number','value':10},{'comparison':'TYPED_INTEGER_EXACT'})['status'],'FAIL')
    def test_typed_bool_not_number(self):self.assertEqual(compare_result({'type':'boolean','value':False},{'type':'number','value':0},{})['status'],'FAIL')
    def test_decimal_contract_preserves_delta(self):
        result=compare_result({'type':'number','value':1.23400000001},{'type':'number','value':1.234},{'comparison':'TYPED_SOURCE_DISPLAY_EXACT_WITH_RAW_DELTA','precision':3})
        self.assertEqual((result['status'],result['raw_numeric_delta']),('PASS','1E-11'))
    def test_generated_has_no_broken_function(self):
        data=json.loads((OUT/'FORMULA_FAMILY_INVENTORY.json').read_text(encoding='utf-8'))
        self.assertTrue(all(f['family_id'] not in FUNCTIONS for f in data['families'] if f['broken']))
    def test_reconstruction_not_applied(self):
        candidates=json.loads((OUT/'CANDIDATE_FORMULA_RECONSTRUCTION.json').read_text(encoding='utf-8'))
        self.assertEqual(len(candidates),36)
        self.assertTrue(all(not x['candidate_applied'] and not x['verified'] for x in candidates))


if __name__=='__main__':unittest.main(verbosity=2)
