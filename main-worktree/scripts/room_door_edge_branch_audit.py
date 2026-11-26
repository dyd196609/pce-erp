"""Additional frozen Native branch evidence; no Runner or workbook writes."""
import sys,json
from collections import Counter
from room_door_edge import ROOT,OUT,read,save,sha
sys.path.insert(0,str(ROOT/'scripts/excel_parity'))
from room_door_edge_sources import RUN,selected_branch,segments
from workbook_source import SourceBook
from reference_runtime import Context,ExcelError,serialized,BLANK
from generated_reference import FUNCTIONS
from formula_ast import Parser
from differential import compare_result
native=read('EXCEL_NATIVE_GOLDEN.json',RUN);plan=read('RUN_CASE_PLAN.json',RUN)
cases={r['case_id']:r for r in plan['cases']}
inventory=read('FORMULA_FAMILY_INVENTORY.json',ROOT/'docs/evidence/excel_formula_parity')
families={inventory['cell_to_family']['房门单!'+a] for a in ('Z11','AA11')}
book=SourceBook();headers=read('SOURCE_NATIVE_AUDIT.json')['headers'];results=[]
for capture in native['results']:
    outputs=[o for o in capture['outputs'] if o['formula_family'] in families]
    if not outputs:continue
    planned=cases[capture['case_id']]
    expected={(o['sheet'],o['cell']):o for o in planned['overrides']}
    overrides={}
    for o in capture['overrides']:
        wanted=expected[(o['sheet'],o['cell'])]
        assert o['requested_value']==wanted['value'] and o['actual']['value']==wanted['value']
        assert o['actual']['type']==wanted['type']
        overrides[(o['sheet'],o['cell'])]=BLANK if o['actual']['type']=='blank' else o['actual']['value']
    ctx=Context(book,inventory['cell_to_family'],FUNCTIONS,overrides)
    for o in outputs:
        sheet,address=o['cell'].split('!');row=int(''.join(c for c in address if c.isdigit()))
        assert o['formula']==book.sheets[sheet][address]['formula']
        try:value=ctx.cell(sheet,address)
        except ExcelError as exc:value=exc
        source=serialized(value)
        spec=next(s for s in planned['derived_outputs'] if s['cell']==o['cell'])
        comparison=compare_result(source,o['excel_raw_value'],spec['contract'])
        item={'caseId':capture['case_id'],'cell':o['cell'],'family':o['formula_family'],'reference':source,
            'native':o['excel_raw_value'],'comparison':comparison,'provenance':'FROZEN_NATIVE_NOT_REAL_PARAMETER'}
        if source['type']=='number':
            branch,path=selected_branch(Parser().parse(o['formula']),ctx,sheet,address)
            try:
                traces=segments(branch,ctx,row,headers)
                item.update(segmentStatus='PARSED',segments=traces,branchTrace=path)
            except ValueError as exc:item.update(segmentStatus='OUTSIDE_8_ROW_INPUT_GAP',detail=str(exc))
        else:item.update(segmentStatus='SOURCE_NONNUMERIC_NOT_SENT_TO_LOSS')
        results.append(item)
save('FROZEN_NATIVE_BRANCH_AUDIT.json',{'status':'PASS' if all(r['comparison']['status']=='PASS' for r in results) else 'FAIL',
    'outputs':len(results),'types':dict(Counter(r['reference']['type'] for r in results)),
    'segmentStatuses':dict(Counter(r['segmentStatus'] for r in results)),'results':results,'nativeRerun':False})
print(json.dumps({k:v for k,v in read('FROZEN_NATIVE_BRANCH_AUDIT.json').items() if k!='results'}))
assert all(r['comparison']['status']=='PASS' for r in results)
# Inspect all type predicates of the frozen formulas using the unchanged reference.
# These are synthetic technical probes, NOT additional Native captures or real order rows.
type_rows=[]
for kind in ('单开门','双开门','子母门','单面套','双面套','未列出的类型'):
    ctx=Context(book,inventory['cell_to_family'],FUNCTIONS,{('房门单','H11'):kind})
    for address in ('Z11','AA11'):
        try:value=ctx.cell('房门单',address)
        except ExcelError as exc:value=exc
        typed=serialized(value)
        item={'doorType':kind,'cell':address,'reference':typed,'provenance':'SIMULATED_FOR_TEST_SOURCE_BRANCH',
            'nativeClaim':False,'promotedToRealRow':False}
        if typed['type']=='number':
            branch,path=selected_branch(Parser().parse(book.sheets['房门单'][address]['formula']),ctx,'房门单',address)
            item.update(selectedBranchAst=branch,segments=segments(branch,ctx,11,headers))
        else:item['lossEligibility']='BLOCKED_NONNUMERIC_SOURCE_RESULT'
        type_rows.append(item)
save('SOURCE_TYPE_BRANCH_AUDIT.json',{'status':'SOURCE_PRESERVED','rows':type_rows,
    'current8RowsAffected':0,'note':'双面套AA原分支E11*0在E11为房门文本时为#VALUE!；未知类型为FALSE。均不属于当前8行，不改源、不把它们视为零净量，不触发本轮U03。'})
