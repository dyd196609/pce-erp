"""Append-only R1-R6 consolidation and tested-package delivery audit."""
import collections
import re
import sys
from decimal import Decimal
from pathlib import Path
from recovery_native_r4 import OUT, ARCHIVE, p, REPO, counts, save, snapshot
from recovery_semantics import resolve


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    pre=Path(sys.argv[1])
    m=p.load_manifest()
    check=p.read(pre/'PACKAGE_PRECHECK.json')
    p.require(check['status']=='PASS' and check['package_manifest_sha']==p.digest(p.ROOT/'RUNNER_MANIFEST.json'),'FINAL PRECHECK MUST MATCH DELIVERY')
    p.require(check['tested_files']==m['files'],'TESTED CODE != DELIVERED')
    p.verify_hashes(p.read(pre/'RUN_MANIFEST.json')['files'],pre)
    prefix=p.read(OUT/'NATIVE_DIFFERENTIAL.json')
    rows=prefix['results']
    lookup={(r['case_id'],r['cell']):r for r in rows}
    byname={(r['case_id'],r['semantic_name']):r for r in rows}
    plan=p.read(p.ROOT/'runs/20260909T040440577Z-a6fb1daa/RUN_CASE_PLAN.json')
    families,cases=p.assets(m)
    realcases=[c for c in cases['cases'] if c['level'] in (2,3)]
    real=[lookup[(c['case_id'],o['cell'])] for c in realcases for o in c['derived_outputs']]
    boundary=[lookup[(c['case_id'],o['cell'])] for c in cases['cases'] if c['level']==1 and c['overrides'] for o in c['derived_outputs']]
    l1=[lookup[(c['case_id'],o['cell'])] for c in cases['cases'] if c['level']==1 for o in c['derived_outputs']]
    p.require(counts(real)=={'PARITY_PASS':1510,'BROKEN_SOURCE':31},'REAL REGRESSION')
    p.require(counts(boundary)=={'PARITY_PASS':434,'BROKEN_SOURCE':22},'BOUNDARY REGRESSION')
    intact={f['family_id'] for f in families['families'] if not f['broken']}
    eligible=intact-{r['formula_family'] for r in l1 if r['classification']=='BROKEN_SOURCE'}
    p.require(len(eligible)==100 and all(r['classification']=='PARITY_PASS' for r in l1 if r['formula_family'] in eligible),'L1A REGRESSION')
    save('REAL_ROW_BOUNDARY_REGRESSION.json',{'real_rows':len(realcases),'real_counts':counts(real),'real_outputs':real,
        'boundary_counts':counts(boundary),'boundary_outputs':boundary,'level1_counts':counts(l1),'eligible_families':len(eligible),'source_broken_not_overwritten':True})
    candidates=[]
    for fid in sorted({r['candidate_family'] for r in rows if r['candidate_family']}):
        members=[r for r in rows if r['cohort'] in ('RECOVERY_CANDIDATE_ONLY','RECOVERY_AREA_GUARD') and (r['candidate_family']==fid or fid in r['case_id'])]
        counter=[r for r in rows if r['cohort']=='R1_OLD_CANDIDATE_SEMANTIC_COUNTEREXAMPLE' and fid in r['case_id']]
        p.require(len(counter)==1 and counter[0]['excel_raw_value']['type']=='number' and counter[0]['excel_raw_value']['value']>0,'WIDTH COUNTEREXAMPLE REQUIRED')
        p.require(all(r['classification']=='PARITY_PASS' for r in members+counter),'CANDIDATE PARITY')
        candidates.append({'family_id':fid,'native_reference_output_count':len(members),'counts':counts(members),
            'too_wide_counterexample':counter[0],'technical_parity':'PASS','whole_business_semantics':'NOT_EQUIVALENT_TO_USER_STOCK_SELECTION',
            'business_semantic_verified':False,'historically_verified':False})
    p.require(len(candidates)==36 and sum(c['native_reference_output_count'] for c in candidates)==2376,'36 CANDIDATE COVERAGE')
    save('CANDIDATE_36_RECHECK.json',{'families':candidates,'output_counts_per_family':dict(collections.Counter(c['native_reference_output_count'] for c in candidates)),
        'total_outputs':2376,'width_counterexamples':36,'business_recovery_upgrades':0,'historically_verified':0})
    business=p.read(OUT.parent/'recovery-u03/BOARD_STOCK_AND_REAL_ROW_AUDIT.json')
    pre_rows=p.read(pre/'REFERENCE_PRECHECK.json')['results']
    p.require(len(pre_rows)==9741,'SUFFIX OUTPUTS')
    for row in pre_rows:
        parent=lookup[(row['case_id'],row['cell'])]
        p.require(parent['classification']=='NATIVE_CAPTURE_REQUIRED','SUFFIX OVERLAPS VALIDATED PREFIX')
        for field in ('code_result','contract','reference_status','semantic_name'):
            p.require(row[field]==parent[field],'REFERENCE CHANGED WHILE FIXING RUNNER')
    spec=sorted({(s['length'],s['width'],s['thickness']) for s in business['stocks']})
    reps=[next(s for s in business['stocks'] if (s['length'],s['width'],s['thickness'])==dims) for dims in spec]
    values={(r['case_id'],r['semantic_name']):r['code_result']['value'] for r in pre_rows}
    independent=[]
    for c in p.read(pre/'RUN_CASE_PLAN.json')['cases']:
        facts={o['cell'][0]:o['value'] for o in c['overrides']}
        result=resolve([facts[k] for k in 'DEF'],reps,[s['material_id'] for s in reps] if facts['I'] else None,facts['H'])
        wanted=result['material_id'] if result['status']=='RESOLVED' else 'BLOCKED_APPLICABILITY' if not facts['I'] else 'BLOCKED_NO_OR_AMBIGUOUS_SPEC'
        p.require(values[(c['case_id'],'SYNTHETIC_SELECTED_MATERIAL_ID')]==wanted,'INDEPENDENT SELECTION')
        chain=values[(c['case_id'],'SYNTHETIC_SELECTION_TO_NET_TO_BUCKET_AGGREGATE')]
        if result['status']=='RESOLVED':
            expected=Decimal(str(facts['D']))*Decimal(str(facts['E']))*Decimal(str(facts['G']))*3/1000000
            p.require(abs(Decimal(str(chain))-expected)<Decimal('0.000000001'),'INDEPENDENT CHAIN; NOT NATIVE TOLERANCE')
        else: p.require(chain=='BLOCKED_UNRESOLVED_REQUIREMENTS','UNRESOLVED CHAIN')
        independent.append({'case_id':c['case_id'],'technical_crosscheck':'PASS','native':'PENDING'})
    for r in business['rows']:
        output=byname[('U03_REAL_TRI_'+str(r['row']),'R3_FORMAL_MATERIAL_ROW_'+str(r['row']))]
        p.require(output['classification']=='PARITY_PASS' and output['excel_raw_value']['value']==r['resolution']['status'],'REAL RESOLVER INDEPENDENT')
    ledger=[r for r in rows if r['cohort']=='R4_R5_R6_AGGREGATE_LEDGER']
    buckets=[r for r in rows if r['cohort']=='R4_BOARD_AGGREGATION_WITH_BLOCKING']
    p.require(len(buckets)==66 and all(r['excel_raw_value']['value']=='BLOCKED_UNRESOLVED_REQUIREMENTS' for r in buckets),'BUCKET BLOCK NOT ZERO')
    stage={'R1':{'candidate_outputs':'2376 PASS','too_wide_counterexamples':'36 PASS; business equivalence rejected','all_boundary_gate':'PENDING'},
        'R2':{'source_real_rows':71,'source_outputs':counts(real),'added_real_recovery_outputs':'4032 PASS including geometry and blocking; not 4032 resolved requirements'},
        'R3':{'real_rows':63,'formal_specs':20,'native_geometry_and_status_outputs':3843,'technical_parity':'PASS_FOR_CAPTURED_REAL_INPUTS','whole_boundary_gate':'PENDING','business_status':'BLOCKED'},
        'R4':{'projection_families':12,'formal_buckets':66,'native':'66 BLOCKED expressions match Reference; not 66 quantities recovered','synthetic_resolved_chain':'PENDING_NATIVE'},
        'R5':{'AV30':byname[('U03_AGGREGATE_AREA_LEDGER','AV30_RECOVERY_SOURCE_LOSS_FACTOR_1_20')],'business':'PARTIAL_VISIBLE_AREA; source factor only','boundary_gate':'PENDING'},
        'R6':{'AV31':byname[('U03_AGGREGATE_AREA_LEDGER','AV31_RECOVERY_NET_EDGE_LENGTH_m')],'business':'PARTIAL_EDGE_APPLICABILITY; allowance NULL; UOM m','boundary_gate':'PENDING'},
        'aggregate_ledger':ledger,'complete_r1_r6_gate':'NOT_CLOSED','independent_suffix_checks':independent,'native_missing_outputs':9741}
    save('R1_R6_STATUS.json',stage)
    register=p.read(OUT.parent/'recovery-u03/RECOVERY_REGISTER_U03.json')
    for item in register:
        src=item['source_cells']
        item['native_run']=plan['run_id']
        if item['family_id'] in {c['family_id'] for c in candidates}:
            item['current_native_status']='CANDIDATE_TECHNICAL_PARITY_PASS; BUSINESS_COUNTEREXAMPLE_CONFIRMED'
        elif '三合一生产单!AV30' in src or '三合一生产单!AV31' in src:
            item['current_native_status']='REAL_LEDGER_CANDIDATE_NATIVE_PASS; ALL_BOUNDARIES_PENDING; BUSINESS_DATA_PARTIAL'
        elif item['status']=='RECOVERY_PROJECTION_PENDING_MATERIAL_BINDING':
            item['current_native_status']='BLOCKING_EXPRESSIONS_NATIVE_PASS; NO_RESOLVED_MATERIAL_AGGREGATE'
        else: item['current_native_status']='EXCLUDED_HISTORICAL_ONLY'
        item['historically_verified']=False
        item['business_semantic_verified']=False
    save('RECOVERY_REGISTER_51_CURRENT.json',register)
    run_integrity=[]
    for name, expected in [('20260908T144733317Z-4c7dd106','38CF2AC205DDB077E97F1EA68B534103DC6D3208A7957F996DEE0C3C41433697'),
        ('20260909T010756709Z-772c0971','9A0AF062D4E8F6ACC64A57BF452F36935110783D238DA830FF76E2AC795E88E3'),
        (plan['run_id'],p.read(OUT/'RUN_INTEGRITY.json')['run_manifest_sha'])]:
        d=p.ROOT/'runs'/name
        p.require(p.digest(d/'RUN_MANIFEST.json')==expected,'HISTORICAL RUN SHA')
        rm=p.read(d/'RUN_MANIFEST.json'); p.verify_hashes(rm['files'],d)
        run_integrity.append({'run':name,'manifest_sha':expected,'verified_files':len(rm['files']),'writes':0})
    old_report=REPO/'docs/evidence/NATIVE_EXCEL_GOLDEN_FINAL_CONSOLIDATED_20260909_U03_R3.md'
    p.require(p.digest(old_report)=='9C28DC6FD5D4240E9DF0370A667935FF5079C86303E2CF8EB14FD5A2DE766759','R3 REPORT DRIFT')
    after=snapshot()
    code_changes=[n for n,h in p.read(ARCHIVE/'RUNNER_MANIFEST.json')['files'].items() if p.digest(p.ROOT/n)!=h]
    core_inputs=set(m['frozen_files'])|{str(p.ROOT/n) for n in m['files']}|{str(f) for f in (p.ROOT/'runs'/plan['run_id']).iterdir() if f.is_file()}
    save('FINAL_DELIVERY_AUDIT.json',{'timestamp':p.now(),'package_version':m['package_version'],'package_manifest_sha':p.digest(p.ROOT/'RUNNER_MANIFEST.json'),
        'precheck':str(pre),'python_tests':check['unit_test_count'],'powershell_tests':check['powershell_contract_test_count'],
        'independent_checks':len(independent)+63,'reference_suffix_outputs_unchanged':len(pre_rows),'source_formula_changes':0,
        'source_sha':p.digest(m['source']),'db_sha':after['db_sha'],'production_counts':after['counts'],'production_write':0,
        'historical_runs':run_integrity,'package_changed_files':code_changes,'domain_formalization':'NOT_ENTERED',
        'whole_run_acceptance':'FAIL_INCOMPLETE_NATIVE','partial_captured_outputs':9005,'native_comparable_pass':8907,'source_broken_outputs':98,
        'uncaptured_cases':191,'uncaptured_outputs':9741,'resume_package_precheck':'PASS','native_restore_fix':'PENDING_USER_SESSION_RECHECK',
        'input_files':len(core_inputs),'input_count_definition':'Unique core pinned dependencies, package members and current Run files; governance/source context listed separately',
        'source_archives_unchanged':True,'ui_gate':'N/A','stop':'ALL_AVAILABLE_EVIDENCE_VALIDATED; ONLY_MISSING_NATIVE_SUFFIX_PREPARED'})
    print(__import__('json').dumps(p.read(OUT/'FINAL_DELIVERY_AUDIT.json'),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
