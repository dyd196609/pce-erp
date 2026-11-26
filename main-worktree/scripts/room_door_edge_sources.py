"""Read frozen AST/Native, decompose selected linear source expressions, never repair Excel."""
import json
import re
import sys
from decimal import Decimal as D
from room_door_edge import ROOT,OUT,OLD,read,save,sha,INSTRUCTION
sys.path.insert(0,str(ROOT/'scripts/excel_parity'))
from workbook_source import SourceBook,coord
from formula_ast import Parser,normalize
from reference_runtime import Context,truth,ExcelError
from generated_reference import FUNCTIONS

RUN=ROOT/'tools/excel-golden-runner/runs/20260909T010756709Z-772c0971'

def selected_branch(tree,ctx,sheet,address):
    row,col=coord(address);path=[]
    while tree['kind']=='call' and tree['name']=='IF':
        args=tree['arguments'];yes=truth(ctx.source_ast(args[0],sheet,row,col))
        path.append({'conditionAst':args[0],'result':yes})
        if not yes and len(args)<3: raise ValueError('U03_NO_SELECTED_NUMERIC_BRANCH')
        tree=args[1 if yes else 2]
    return tree,path

def monomials(tree):
    """Auditor only: positive sum/products/division by scalar, not a new evaluator."""
    k=tree['kind']
    if k=='number':return [(D(str(tree['value'])),[])]
    if k=='reference':return [(D(1),[tree['value']])]
    if k!='binary':raise ValueError('U03_UNSUPPORTED_SEGMENT_EXPRESSION')
    a,b=monomials(tree['left']),monomials(tree['right']);op=tree['operator']
    if op=='+':return a+b
    if op=='*':return [(x*y,rx+ry) for x,rx in a for y,ry in b]
    if op=='/' and len(b)==1 and not b[0][1] and b[0][0]!=0:
        return [(x/b[0][0],rx) for x,rx in a]
    raise ValueError('U03_NONLINEAR_OR_NEGATIVE_SEGMENT_EXPRESSION')

def segments(tree,ctx,row,headers):
    result=[]
    for coefficient,refs in monomials(tree):
        if coefficient==0:continue # Context has already evaluated this branch, so text*0 cannot be concealed.
        length_refs=[r for r in refs if r in (f'N{row}',f'O{row}')]
        qty_refs=[r for r in refs if r==f'Q{row}']
        if len(length_refs)!=1 or len(qty_refs)!=1 or len(refs)!=2:
            raise ValueError('U03_SEGMENT_DIMENSION_OR_MULTIPLIER_NOT_UNIQUE')
        count=coefficient*1000
        if count<=0 or count!=int(count):raise ValueError('U03_NONINTEGER_EDGE_COUNT')
        length=D(str(ctx.cell('房门单',length_refs[0])));qty=D(str(ctx.cell('房门单',qty_refs[0])))
        if length<0 or qty<0 or qty!=int(qty):raise ValueError('U03_INVALID_GEOMETRY')
        for i in range(int(count)):
            result.append({'segmentNo':len(result)+1,'semantic':headers[length_refs[0][0]],
                'dimensionCell':length_refs[0],'netSegmentLengthMm':str(length),'netSegmentLengthM':str(length/1000),
                'quantityCell':qty_refs[0],'quantityMultiplier':int(qty),
                'netTotalM':str(length*qty/1000),'orientation':'SOURCE_DIMENSION_NOT_ASSUMED_DOOR_LEAF'})
    return result

def analyze():
    source=json.loads((ROOT/'backend/pde/semi_finished_configuration_source.json').read_text(encoding='utf-8'))
    books={}
    for s in source['sourceFiles']:
        assert sha(s['path'])==s['sha256'];books[s['file']]=SourceBook(s['path'])
    book=books[source['sourceFiles'][0]['file']];sheet=book.sheets['房门单']
    headers={c:sheet.get(c+'10',{}).get('value') for c in ('N','O','P','Q','R','S','U','W','Z','AA')}
    assert headers['Z']=='封边皮25' and headers['AA']=='封边皮50',headers
    inventory=read('FORMULA_FAMILY_INVENTORY.json',ROOT/'docs/evidence/excel_formula_parity')
    mapping=inventory['cell_to_family'];families={f['family_id']:f for f in inventory['families']}
    ctx=Context(book,mapping,FUNCTIONS)
    manifest=read('RUN_MANIFEST.json',RUN)
    for n,h in manifest['files'].items():assert sha(RUN/n)==h,n
    native=read('EXCEL_NATIVE_GOLDEN.json',RUN)
    assert native['source_sha']==manifest['source_sha']==source['sourceFiles'][0]['sha256']
    assert native['plan_sha']==sha(RUN/'RUN_CASE_PLAN.json')
    captures={}
    for case in native['results']:
        if case['overrides']:continue
        for o in case['outputs']:
            if o['cell'].startswith('房门单!'):captures.setdefault(o['cell'],[]).append({'caseId':case['case_id'],**o})
    veneer={v['row']:v for v in read('VENEER_NET_PREVIEW.json',OLD)['rows'] if v['sheet']=='房门单'}
    rows=[];native_checks=[];family_evidence={}
    for raw in [r for r in source['realRows'] if r['sheet']=='房门单']:
        row=raw['row'];v=lambda c:ctx.cell('房门单',c+str(row))
        for a,cell in raw['cells'].items():assert all(sheet[a].get(k)==cell[k] for k in ('value','formula','type'))
        visible=veneer[row] # The one frozen visible fact, shared with veneer, not a second formula.
        for col in ('W','Z','AA'):
            address=col+str(row);key='房门单!'+address;family=families[mapping[key]]
            tree=Parser().parse(sheet[address]['formula'])
            assert normalize(tree,address)==family['normalized_formula']
            ns=captures.get(key,[]);assert ns,key
            for capture in ns:
                assert capture['formula']==sheet[address]['formula'] and capture['formula_family']==family['family_id']
                assert capture['excel_raw_value']['type']=='number'
                assert abs(D(str(v(col)))-D(str(capture['excel_raw_value']['value'])))<D('1e-11')
            native_checks.append({'cell':key,'family':family['family_id'],'captures':ns,'reference':v(col),'status':'PASS'})
            family_evidence[family['family_id']]=family
            if col=='W':
                assert abs(D(visible['visibleAreaM2'])-D(str(v(col))))<D('1e-11');continue
            branch,path=selected_branch(tree,ctx,'房门单',address)
            trace=segments(branch,ctx,row,headers);net=sum((D(t['netTotalM']) for t in trace),D(0))
            assert abs(net-D(str(v(col))))<D('1e-11')
            kind='EDGE_BANDING_25_SOURCE' if col=='Z' else 'EDGE_BANDING_50_SOURCE'
            rows.append({'sheet':'房门单','row':row,'configurationCode':'QSFB4601001','role':v('H'),'space':v('F'),
                'sourceType':kind,'sourceName':headers[col],'sourceCell':address,'sourceFormula':sheet[address]['formula'],
                'formulaFamily':family['family_id'],'sourceSha256':native['source_sha'],'netLengthM':str(net),
                'sourceRawValue':raw['cells'][address]['value'],'sourceRawType':raw['cells'][address]['type'],
                'nativeRawValue':ns[0]['excel_raw_value'],'nativeStatus':'PASS','sourceQuantityStatus':'READY',
                'requirementSourceMode':'DIRECT_CALCULATED','baseUom':'m','baseQuantityType':'LENGTH',
                'segments':trace,'edgeCount':sum(t['quantityMultiplier'] for t in trace),'segmentTemplateCount':len(trace),
                'selectedBranchAst':branch,'branchTrace':path,'formulaBranch':v('H'),
                'materialId':None,'materialSpecification':None,'materialStatus':'UNRESOLVED',
                'lossMethod':'PER_EDGE_ALLOWANCE','perEdgeAllowanceMm':None,'totalAllowanceM':None,
                'lossParameterStatus':'PENDING','grossLengthM':None,'grossStatus':'BLOCKED_PARAMETER_PENDING',
                'quantity':None,'quantityMode':'CALCULATED','owner':'ENGINEERING_COMPONENT',
                'blockers':['EDGE_MATERIAL_IDENTITY_UNRESOLVED','PER_EDGE_ALLOWANCE_PENDING','RULE_NOT_RELEASED']})
    # Exhaust source identities, not only names in a selected material page.
    formal=read('FORMAL_BEFORE.json')['formal'];pattern=re.compile('封边|封邊|edge.?band',re.I)
    catalogs=[{'catalog':key,**r} for key,rs in source['catalogs'].items() for r in rs if pattern.search(json.dumps(r,ensure_ascii=False))]
    materials=[m for m in formal['materials'] if pattern.search(json.dumps(m,ensure_ascii=False))]
    exact={name:[m for m in formal['materials'] if m['name']==name] for name in ('封边皮25','封边皮50')}
    assert not any(exact.values()),'Review exact formal identities rather than silently retaining unresolved'
    save('MATERIAL_IDENTITY_AUDIT.json',{'status':'UNRESOLVED','formalMaterialCount':len(formal['materials']),
        'sourceMatches':catalogs,'formalMatches':materials,'exactNameMatches':exact,'specificationInferred':False,
        'reason':'来源封边材料与正式条材没有唯一身份关系；25/50不推断宽度；净长不因选料未决而隐藏'})
    save('SOURCE_NATIVE_AUDIT.json',{'status':'PASS','sourceFiles':source['sourceFiles'],'headers':headers,
        'nativeRun':str(RUN),'manifestSha256':sha(RUN/'RUN_MANIFEST.json'),'nativeSha256':sha(RUN/'EXCEL_NATIVE_GOLDEN.json'),
        'manifestFilesVerified':len(manifest['files']),'checks':native_checks,'familyEvidence':list(family_evidence.values()),
        'referencePath':str(ROOT/'scripts/excel_parity/generated_reference.py'),'referenceSha':sha(ROOT/'scripts/excel_parity/generated_reference.py'),
        'nativeRerun':False,'sourceWorkbookWrite':0,'sourceFormulaWrite':0})
    summary={'visibleAreaPass':8,'visibleAreaTotalM2':str(sum(D(v['visibleAreaM2']) for v in veneer.values())),
        'edge25NetPass':8,'edge25NetTotalM':str(sum(D(r['netLengthM']) for r in rows if r['sourceType']=='EDGE_BANDING_25_SOURCE')),
        'edge50NetPass':8,'edge50NetTotalM':str(sum(D(r['netLengthM']) for r in rows if r['sourceType']=='EDGE_BANDING_50_SOURCE')),
        'edgeSegmentTrace':'PASS','traceRecordCount':sum(len(r['segments']) for r in rows),'physicalEdgeCount':sum(r['edgeCount'] for r in rows),
        'lossMethod':'PER_EDGE_ALLOWANCE','allowanceParameter':None,'gross25':None,'gross50':None,
        'material25':'UNRESOLVED','material50':'UNRESOLVED','veneerVisibleConsistency':'PASS','u03Required':False}
    save('ROOM_DOOR_EDGE_SEGMENT_TRACE.json',{'summary':summary,'rows':rows,'visibleFacts':list(veneer.values()),'userDecisionSha256':sha(INSTRUCTION)})
    print(json.dumps({'headers':headers,'summary':summary,'rows':[{'row':r['row'],'source':r['sourceName'],'net':r['netLengthM'],'edges':r['edgeCount']} for r in rows]},ensure_ascii=False,indent=2))
if __name__=='__main__':analyze()
