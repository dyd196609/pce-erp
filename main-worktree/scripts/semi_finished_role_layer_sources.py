"""Read all original evidence; build scoped previews, not formal rules/requirements."""
import json
import re
import sys
from collections import Counter
from decimal import Decimal
from semi_finished_role_layer import ROOT, OUT, save, read, sha, INSTRUCTION
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'scripts/excel_parity'))
from workbook_source import SourceBook
from recovery_semantics import net_area, gross_edges
from pde.semi_finished_configuration_preview import build_projection, resolve_code, value, cell_value


def analyze():
    source=json.loads((ROOT/'backend/pde/semi_finished_configuration_source.json').read_text(encoding='utf-8'))
    formal=read('FORMAL_BEFORE.json')['formal']
    books={}
    for info in source['sourceFiles']:
        assert sha(info['path'])==info['sha256'],info['file']
        books[info['file']]=SourceBook(info['path'])
    # Verify every stored source/catalog value and formula against original files.
    checked=0
    for key, rows in source['catalogs'].items():
        filename,sheet=key.split('|')
        for row in rows:
            for field in row['fields'].values():
                raw=books[filename].sheets[sheet].get(field['cell'],{})
                assert raw.get('value')==field['value'] and raw.get('formula')==field['formula'],(key,field['cell'])
                checked+=1
    for row in source['sourceRows']:
        for field in row['fields'].values():
            raw=books[row['file']].sheets[row['sheet']].get(field['cell'],{})
            assert raw.get('value')==field['value'] and raw.get('formula')==field['formula']
            checked+=1
    main=books[source['sourceFiles'][0]['file']]
    for row in source['realRows']:
        for address,cell in row['cells'].items():
            current=main.sheets[row['sheet']][address]
            assert all(current.get(k)==cell[k] for k in ('value','formula','type')),(row['sheet'],address)
            checked+=1
    projection=build_projection(source,formal,1)
    cases={c['sourceCode']:c for c in projection['configurations'] if c['realRowCount']}
    purchase_sha=next(f['sha256'] for f in source['sourceFiles'] if f['file']=='10采购物料.xlsx')
    stocks=[]
    for row in source['catalogs']['10采购物料.xlsx|采购物料']:
        if value(row,'物料品类')!='板材':
            continue
        identity=resolve_code(value(row,'物料编码'),'10采购物料.xlsx','采购物料',purchase_sha,formal)
        spec=value(row,'规格/型号')
        target=identity.get('formal')
        actual=next((m for m in formal['materials'] if target and m['id']==target['id']),None)
        matched=bool(actual and actual['specification']==spec and actual['is_purchased']
            and actual['is_active'] and actual['material_type'] in {'raw','auxiliary'})
        parsed=re.fullmatch(r'(\d+(?:\.\d+)?)\*(\d+(?:\.\d+)?)\*(\d+(?:\.\d+)?)',spec or '')
        dims=dict(zip(('length','width','thickness'),(str(Decimal(v)) for v in parsed.groups()))) if parsed else None
        # Source D is 通用/brand, E is 板材. Neither proves membership in 实木多层板.
        family_confirmed=bool(actual and any(c['id']==actual['category_id'] and c['name']=='实木多层板' for c in formal['categories']))
        stocks.append({'sourceRow':row['row'],'sourceCode':value(row,'物料编码'),'name':value(row,'物料名称'),
            'sourceCategory':value(row,'物料分类'),'sourceKind':value(row,'物料品类'),'specification':spec,
            'dimensions':dims,'formal':target,'formalSpecificationMatched':matched,'materialFamilyMatch':family_confirmed,
            'identityEvidence':identity['evidence'],'sourceSha256':purchase_sha,'uom':value(row,'单位')})
    valid=[s for s in stocks if s['formalSpecificationMatched'] and s['dimensions']]
    boards=[]; veneers=[]; edges=[]; components=[]
    for row in source['realRows']:
        sheet,n=row['sheet'],row['row']
        v=lambda col:cell_value(row,col)
        config=cases[v('B')]
        tri=sheet=='三合一生产单'
        base={'sheet':sheet,'row':n,'configurationCode':v('B'),'role':v('G') if tri else v('H'),
            'space':v('F'),'productCategory':v('E'),'sourceSha256':source['sourceFiles'][0]['sha256']}
        component={**base,'length':v('J'),'width':v('K'),'thickness':v('L') if tri else None,
            'dimensionSemantics':'BOARD_COMPONENT' if tri else 'DOOR_OPENING_NOT_PANEL',
            'quantity':v('M'),'visibleCondition':v('O') if tri else None,'edgeMode':v('P') if tri else None,
            'columnLRaw':v('L'),'sourceCells':row['cells']}
        components.append(component)
        if tri:
            t=Decimal(str(v('L')))
            exact=[s for s in valid if Decimal(s['dimensions']['thickness'])==t]
            family=[s for s in exact if s['materialFamilyMatch']]
            fits=[s for s in family if Decimal(s['dimensions']['length'])>=Decimal(str(v('J'))) and Decimal(s['dimensions']['width'])>=Decimal(str(v('K')))]
            blockers=[]
            if not exact:
                blockers.append('PROCUREMENT_MATERIAL_MASTER_DATA_GAP')
            if not family:
                blockers.append('ALLOWED_FAMILY_MEMBERS_UNRESOLVED')
            if family and not fits:
                blockers.append('NO_EXACT_GEOMETRY_SPEC')
            boards.append({**base,'length':v('J'),'width':v('K'),'thickness':v('L'),'thicknessCell':f'L{n}',
                'thicknessSemantic':'BOARD_MATCH_INPUT','userDecisionSha256':sha(INSTRUCTION),
                'exactThicknessMaterialIds':[s['formal']['id'] for s in exact],
                'materialFamilyMatchIds':[s['formal']['id'] for s in family], 'specMatchIds':[s['formal']['id'] for s in fits],
                'materialId':None,'quantity':None,'status':'BLOCKED' if blockers else 'PENDING_MINIMUM_SPEC_SELECTION',
                'blockers':blockers,'nearestThicknessUsed':False,'compositionGapProven':False,
                'note':'来源与正式采购规格均无精确厚度' if not exact else '厚度诊断有候选，但未证明属于实木多层板允许集；不是已选板材'})
            visible=v('O')
            area=net_area(v('J'),v('K'),v('M')) if visible=='单' else net_area(v('J'),v('K'),v('M'))*2 if visible=='双' else Decimal(0) if visible=='白坯' else None
            formula=row['cells'].get(f'Q{n}',{}).get('formula')
            if area is not None:
                assert abs(area-Decimal(str(v('Q'))))<Decimal('0.000000000001')
            edge_mode=v('P')
            # Exact modes are the unchanged original R-column branch meanings.
            branches={'一长':(1,0),'一宽':(0,1),'两长':(2,0),'两宽':(0,2),'一长一宽':(1,1),
                '一长两宽':(1,2),'两长一宽':(2,1),'四边':(2,2),'白坯':(0,0)}
            if edge_mode in branches:
                nl,nw=branches[edge_mode]
                dimensions=[v('J')]*nl+[v('K')]*nw
                net=sum(Decimal(str(d))*Decimal(str(v('M')))/1000 for d in dimensions)
                assert abs(net-Decimal(str(v('R'))))<Decimal('0.000000000001')
                edges.append({**base,'edgeMode':edge_mode,'edgeModeCell':f'P{n}',
                    'edgeDimensionsMm':dimensions,'edgeLabels':[f'长边{i+1}' for i in range(nl)]+[f'宽边{i+1}' for i in range(nw)],
                    'componentQuantity':v('M'),'netLengthM':str(net),'grossLengthM':gross_edges(dimensions,v('M'),None),
                    'perEdgeAllowanceMm':None,'materialId':None,'materialSpecification':None,'quantity':None,
                    'quantityMode':'CALCULATED','baseUom':'m','owner':'ENGINEERING_COMPONENT',
                    'sourceFormula':row['cells'][f'R{n}']['formula'],'roleApplicability':'SOURCE_EXPLICIT',
                    'status':'BLOCKED','blockers':['EDGE_MATERIAL_IDENTITY_UNRESOLVED','PER_EDGE_ALLOWANCE_PENDING','RULE_NOT_RELEASED']})
        else:
            # Preserve the already verified door surface expression and dimensions; no new door rule.
            inputs=[v(c) for c in ('R','S','U','N','P','Q','O')]
            area=(net_area(v('R'),v('S'),v('U'))*2+net_area(v('N'),v('P'),v('Q'))*2+net_area(v('O'),v('P'),v('Q'))) if all(isinstance(x,(int,float)) for x in inputs) else None
            formula=row['cells'].get(f'W{n}',{}).get('formula')
            if area is not None:
                assert abs(area-Decimal(str(v('W'))))<Decimal('0.000000000001')
        veneer=next(a for a in config['attributes'] if a['key']=='veneer')
        veneers.append({**base,'veneerSourceIdentity':veneer['sourceValue'],'visibleAreaM2':str(area) if area is not None else None,
            'netRequirementM2':str(area) if area is not None else None,'netStatus':'PASS' if area is not None else 'BLOCKED_VISIBLE_CONDITION_MISSING',
            'basis':'VISIBLE_AREA','basisCell':f'Q{n}' if tri else f'W{n}','basisFormula':formula,
            'veneerThicknessAttribute':{'sourceText':veneer['sourceValue'],'formalThickness':None,'calculationInput':False},
            'procurementMaterialId':None,'procurementStatus':'BLOCKED_IDENTITY_UNRESOLVED','formalQuantity':None,
            'lossRate':None,'grossQuantity':None,'missingVeneerDimensionsBlocksArea':False})
    counts={'rowCount':len(boards),'exactThicknessMatch':sum(bool(r['exactThicknessMaterialIds']) for r in boards),
        'materialFamilyMatch':sum(bool(r['materialFamilyMatchIds']) for r in boards),'specMatch':sum(bool(r['specMatchIds']) for r in boards),
        'boardExactMatch':sum(r['materialId'] is not None for r in boards),'blocked':sum(r['status']=='BLOCKED' for r in boards),
        'noExactThickness':sum(not r['exactThicknessMaterialIds'] for r in boards),'compositionGapProven':0,
        'thicknessUnknown':0,'countingBasis':'engineering source rows; thickness-only matches are diagnostic, not approved family matches'}
    save('SOURCE_RECHECK.json',{'sourceFiles':source['sourceFiles'],'checkedCells':checked,'sourceBundleSha':sha(ROOT/'backend/pde/semi_finished_configuration_source.json'),
        'nativeRerun':False,'components':components,'procurementBoards':stocks,
        'familyEvidence':'13坯板第2行仅给出族名；10的分类/品类没有逐编码的实木多层板允许成员关系；名称相似不代替该关系',
        'roughStructure':{'path':str(ROOT/'backend/masterdata/group3_comparison_source.json'),'sha256':sha(ROOT/'backend/masterdata/group3_comparison_source.json'),
            'structuralReference':True,'numericAuthority':False,'formulaAuthority':False}})
    save('BOARD_MATCH_PREVIEW.json',{'summary':counts,'rows':boards,'formalStocks':stocks})
    save('VENEER_NET_PREVIEW.json',{'summary':{'rows':len(veneers),'netPass':sum(v['netStatus']=='PASS' for v in veneers),
        'netBlocked':sum(v['netStatus']!='PASS' for v in veneers),'procurementBlocked':len(veneers),
        'knownSubtotalM2':str(sum(Decimal(v['netRequirementM2']) for v in veneers if v['netRequirementM2'] is not None)),
        'completeTotalM2':None if any(v['netRequirementM2'] is None for v in veneers) else str(sum(Decimal(v['netRequirementM2']) for v in veneers)),
        'byConfiguration':{code:{'knownSubtotalM2':str(sum(Decimal(v['netRequirementM2']) for v in veneers if v['configurationCode']==code and v['netRequirementM2'] is not None)),
            'rows':sum(v['configurationCode']==code for v in veneers),'blockedRows':[v['row'] for v in veneers if v['configurationCode']==code and v['netRequirementM2'] is None]} for code in cases}},'rows':veneers})
    save('EDGE_COMPONENT_PREVIEW.json',{'summary':{'examinedSourceRows':71,'explicitEdgeRows':len(edges),'unknownEdgeRows':4,
        'doorRowsNotAssignedEdgeMode':8,'knownNetSubtotalM':str(sum(Decimal(e['netLengthM']) for e in edges)),
        'completeGrossM':None,'formalQuantityGenerated':0},'rows':edges})
    print(json.dumps({'sources':len(books),'verifiedCells':checked,'boards':counts,'veneer':read('VENEER_NET_PREVIEW.json')['summary'],
        'edge':read('EDGE_COMPONENT_PREVIEW.json')['summary']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    analyze()
