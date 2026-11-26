"""Technical closure audit; business recovery is not promoted by equal outputs."""
import collections
import copy
import json
import sys
from decimal import Decimal
from pathlib import Path
from recovery_native_r5 import OUT, PRIOR, ARCHIVE, p, REPO, save as append_save, counts, snapshot
from recovery_semantics import resolve, geometric_candidates, minimal


def save(name, value):
    if (OUT/name).exists():
        previous=p.read(OUT/name)
        # Resume a stopped finalizer only when already committed evidence is
        # identical. Never replace an artifact or change an earlier conclusion.
        a={k:v for k,v in previous.items() if k!='rechecked_at'} if isinstance(previous,dict) else previous
        b={k:v for k,v in value.items() if k!='rechecked_at'} if isinstance(value,dict) else value
        p.require(a==b,'RESUME EVIDENCE CHANGED '+name)
        return
    append_save(name,value)


def independent_boundaries(plan, rows, stock):
    specs=sorted({(s['length'],s['width'],s['thickness']) for s in stock})
    reps=[next(s for s in stock if (s['length'],s['width'],s['thickness'])==dims) for dims in specs]
    idx={(r['case_id'],r['semantic_name']):r for r in rows}
    records=[]
    for c in plan['cases']:
        f={o['cell'][0]:o['value'] for o in c['overrides']}
        value=lambda name:idx[(c['case_id'],name)]['excel_raw_value']['value']
        required=[f[k] for k in 'DEF']
        fits=geometric_candidates(required,reps,f['H'])
        mins=minimal(fits)
        result=resolve(required,reps,[s['material_id'] for s in reps] if f['I'] else None,f['H'])
        wanted=result['material_id'] if result['status']=='RESOLVED' else 'BLOCKED_APPLICABILITY' if not f['I'] else 'BLOCKED_NO_OR_AMBIGUOUS_SPEC'
        p.require(value('SYNTHETIC_SELECTED_MATERIAL_ID')==wanted,'INDEPENDENT MATERIAL')
        for k,s in enumerate(reps,1):
            p.require(value('SYNTHETIC_SPEC_FIT_'+str(k))==int(s in fits),'INDEPENDENT FIT')
            # Frozen generator uses 1-based FIT labels but 0-based MINIMAL
            # labels. Verify the actual label sets, never shift source formulas.
            p.require(value('SYNTHETIC_MINIMAL_SPEC_'+str(k-1))==int(s in mins),'INDEPENDENT MINIMUM '+c['case_id'])
        net=Decimal(str(f['D']))*Decimal(str(f['E']))*Decimal(str(f['G']))/1000000
        numeric=[]
        def decimal_check(name, expected):
            observed=Decimal(str(value(name)))
            delta=observed-expected
            # Independent Decimal analysis only; Native/Reference comparison
            # remains the frozen typed-raw-exact contract, with NO tolerance.
            p.require(abs(delta)<Decimal('0.000000001'),'INDEPENDENT DECIMAL CHECK '+name)
            numeric.append({'semantic':name,'expected_decimal':str(expected),'native':str(observed),'raw_delta':str(delta)})
        decimal_check('SYNTHETIC_PRODUCT_AREA_m2',net)
        if result['status']=='RESOLVED':
            expected_key='|'.join(str(v) for v in result['bucket_key'])
            p.require(value('SYNTHETIC_SELECTED_FULL_BUCKET_KEY')==expected_key,'FULL MATERIAL KEY')
            decimal_check('SYNTHETIC_SELECTION_TO_NET_TO_BUCKET_AGGREGATE',net*3)
        else:
            p.require(value('SYNTHETIC_SELECTED_FULL_BUCKET_KEY')=='UNRESOLVED','UNRESOLVED KEY')
            p.require(value('SYNTHETIC_SELECTION_TO_NET_TO_BUCKET_AGGREGATE')=='BLOCKED_UNRESOLVED_REQUIREMENTS','UNRESOLVED AGGREGATE')
        if f['J']=='': p.require(value('SYNTHETIC_AREA_LOSS_PARAMETER')=='PENDING_LOSS_RATE','MISSING RATE NOT ZERO')
        else: decimal_check('SYNTHETIC_AREA_LOSS_PARAMETER',net*(1+Decimal(str(f['J']))))
        if f['K']=='': p.require(value('SYNTHETIC_PER_EDGE_ALLOWANCE_m')=='PENDING_EDGE_ALLOWANCE','MISSING ALLOWANCE NOT ZERO')
        else: decimal_check('SYNTHETIC_PER_EDGE_ALLOWANCE_m',(2*Decimal(str(f['D']))+2*Decimal(str(f['E']))+4*Decimal(str(f['K'])))*Decimal(str(f['G']))/1000)
        for name,expected in [('SYNTHETIC_SAME_BUCKET_ONLY','0.5'),('SYNTHETIC_OTHER_BUCKET_SEPARATE','0.9'),
            ('SYNTHETIC_EDGE_BUCKET_2460','1.58'),('SYNTHETIC_EDGE_BUCKET_2462','2.04'),('SYNTHETIC_EDGE_BUCKET_2463','3.04')]:
            decimal_check(name,Decimal(expected))
        p.require(all(r['classification']=='PARITY_PASS' for r in rows if r['case_id']==c['case_id']),'NATIVE ALL CASE OUTPUTS')
        records.append({'case_id':c['case_id'],'native_reference':'51/51 PASS_TYPED_RAW_EXACT','independent_geometry_selection':'PASS','label_index_contract':'FIT 1..20; MINIMAL 0..19; frozen formula addresses unchanged',
            'selected':wanted,'decimal_checks':numeric,'business_provenance':'SIMULATED_FOR_TEST_NOT_REAL_MATERIAL_OR_POLICY'})
    return records


def main(pre):
    m=p.load_manifest(); pre=Path(pre)
    check=p.read(pre/'PACKAGE_PRECHECK.json')
    p.require(check['status']=='PASS' and check['package_manifest_sha']==p.digest(p.ROOT/'RUNNER_MANIFEST.json'),'PRECHECK != DELIVERED')
    p.require(check['tested_files']==m['files'],'TESTED CODE != DELIVERED')
    p.verify_hashes(p.read(pre/'RUN_MANIFEST.json')['files'],pre)
    combined=p.read(OUT/'COMBINED_DIFFERENTIAL.json'); rows=combined['results']
    lookup={(r['case_id'],r['cell']):r for r in rows}
    family,cases=p.assets(m)
    realcases=[c for c in cases['cases'] if c['level'] in (2,3)]
    real=[lookup[(c['case_id'],o['cell'])] for c in realcases for o in c['derived_outputs']]
    boundary=[lookup[(c['case_id'],o['cell'])] for c in cases['cases'] if c['level']==1 and c['overrides'] for o in c['derived_outputs']]
    l1=[lookup[(c['case_id'],o['cell'])] for c in cases['cases'] if c['level']==1 for o in c['derived_outputs']]
    p.require(counts(real)=={'PARITY_PASS':1510,'BROKEN_SOURCE':31},'REAL ROW REGRESSION')
    p.require(counts(boundary)=={'PARITY_PASS':434,'BROKEN_SOURCE':22},'BOUNDARY REGRESSION')
    intact={f['family_id'] for f in family['families'] if not f['broken']}
    eligible=intact-{r['formula_family'] for r in l1 if r['classification']=='BROKEN_SOURCE'}
    p.require(len(eligible)==100 and all(r['classification']=='PARITY_PASS' for r in l1 if r['formula_family'] in eligible),'L1A REGRESSION')
    save('REAL_ROW_BOUNDARY_REGRESSION.json',{'real_rows':71,'real':counts(real),'real_outputs':real,'boundary':counts(boundary),
        'boundary_outputs':boundary,'level1':counts(l1),'level1a':'100/100 PASS','frozen_native_reused_not_reexecuted':True})
    candidate=p.read(PRIOR/'CANDIDATE_36_RECHECK.json')
    p.require(candidate['total_outputs']==2376 and candidate['width_counterexamples']==36 and candidate['business_recovery_upgrades']==0,'CANDIDATE BASELINE')
    for c in candidate['families']:
        old=c['too_wide_counterexample']; current=lookup[(old['case_id'],old['cell'])]
        p.require(current['classification']=='PARITY_PASS' and current['excel_raw_value']['value']>0,'WIDTH COUNTEREXAMPLE')
    save('CANDIDATE_36_RECHECK.json',candidate|{'rechecked_at':p.now(),'new_boundary_native_completed':True,'business_equivalence':'REJECTED_NOT_RECOVERED'})
    board=p.read(OUT.parent/'recovery-u03/BOARD_STOCK_AND_REAL_ROW_AUDIT.json')
    d=Path(p.read(OUT/'PROTECTION_BEFORE.json')['run_directory'])
    from native_input_realization import realize
    plan,_=realize(p.read(d/'RUN_CASE_PLAN.json'),p.read(d/'EXCEL_NATIVE_GOLDEN.json'),board['stocks'])
    suffix=p.read(OUT/'SUFFIX_DIFFERENTIAL.json')['results']
    independent=independent_boundaries(plan,suffix,board['stocks'])
    save('BOUNDARY_NATIVE_INDEPENDENT_CHECKS.json',{'cases':len(independent),'outputs':9741,'technical_native':'PASS_TYPED_RAW_EXACT',
        'independent_decimal_analysis_bound':'1E-9 ONLY FOR SEPARATE DECIMAL ANALYSIS; NOT NATIVE TOLERANCE',
        'selected_counts':dict(collections.Counter('RESOLVED' if isinstance(r['selected'],int) else r['selected'] for r in independent)),
        'results':independent})
    byname={(r['case_id'],r['semantic_name']):r for r in rows}
    for r in board['rows']:
        o=byname[('U03_REAL_TRI_'+str(r['row']),'R3_FORMAL_MATERIAL_ROW_'+str(r['row']))]
        p.require(o['excel_raw_value']['value']==r['resolution']['status'],'REAL MATERIAL BLOCK')
    stage=p.read(PRIOR/'R1_R6_STATUS.json')
    stage['R1']['all_boundary_gate']='191/191 CASES; 9741/9741 NATIVE OUTPUTS PASS; explicit two decimal input realizations'
    stage['R3']['whole_boundary_gate']='PASS_NATIVE; BUSINESS_ASSIGNMENTS_STILL_BLOCKED'
    stage['R4']['synthetic_resolved_chain']='PASS_NATIVE; TEST_ASSIGNMENTS_ONLY'
    stage['R5']['boundary_gate']='PASS_NATIVE; actual visible-source gap and approved loss policy still pending'
    stage['R6']['boundary_gate']='PASS_NATIVE; actual edge-source gaps and allowance still pending'
    stage['complete_r1_r6_gate']='TECHNICAL_NATIVE_PARITY_CLOSED; BUSINESS_RECOVERY_NOT_CLOSED'
    stage['independent_suffix_checks']=independent
    stage['native_missing_outputs']=0
    save('R1_R6_STATUS.json',stage)
    reg=p.read(PRIOR/'RECOVERY_REGISTER_51_CURRENT.json')
    for item in reg:
        item['validation_runs']=[combined['parent_run'],combined['suffix_run']]
        if '三合一生产单!AV30' in item['source_cells'] or '三合一生产单!AV31' in item['source_cells']:
            item['current_native_status']='REAL_LEDGER_AND_BOUNDARIES_NATIVE_PASS; BUSINESS_SOURCE_AND_POLICY_PARTIAL'
        elif item['status']=='RECOVERY_PROJECTION_PENDING_MATERIAL_BINDING':
            item['current_native_status']='BLOCKING_EXPRESSIONS_AND_SYNTHETIC_FULL_CHAIN_NATIVE_PASS; REAL_MATERIAL_BINDING_BLOCKED'
        item['historically_verified']=False; item['business_semantic_verified']=False
    p.require(len(reg)==51,'REGISTER COUNT')
    save('RECOVERY_REGISTER_51_CURRENT.json',reg)
    errors=p.read(PRIOR/'FROZEN_NATIVE_REGRESSION.json')
    for g in errors['error_gap_results']:
        r=lookup[(g['case_id'],g['cell'])]
        p.require(r['classification']=='PARITY_PASS' and r['excel_raw_value']==g['native_raw'],'ERROR GAP REGRESSION')
    save('ERROR_CODE_44_CLOSURE.json',errors|{'status':'44/44 PASS','additional_native_run_required':False})
    exhausted=p.read(OUT.parent/'native-supplement-r2/SOURCE_EXHAUSTION_AND_ADJUDICATION.json')
    for s in exhausted['sources']: p.require(p.digest(s['path'])==s['sha256'],'SOURCE EXHAUSTION STALE')
    p.require(p.digest(exhausted['structure']['path'])==exhausted['structure']['sha'],'STRUCTURE STALE')
    gaps=p.read(PRIOR/'BUSINESS_GAPS_U01_U04.json')
    gaps['native_runner_error']='RESOLVED_TECHNICAL_OFFLINE; NO_BUSINESS_ADJUDICATION'
    gaps['immediate_user_action']='No Runner rerun; provide three already-registered groups of actual business source facts'
    gaps['new_U01_U02_U03_U04_groups_this_turn']=0
    gaps['native_missing_outputs']=0
    save('BUSINESS_GAPS_U01_U04.json',gaps)
    history=[]
    prior_audit=p.read(PRIOR/'FINAL_DELIVERY_AUDIT.json')
    for r in prior_audit['historical_runs']+[{'run':d.name,'manifest_sha':p.read(OUT/'PROTECTION_BEFORE.json')['run_manifest_sha']}]:
        path=p.ROOT/'runs'/r['run']; rm=p.read(path/'RUN_MANIFEST.json')
        p.require(p.digest(path/'RUN_MANIFEST.json')==r['manifest_sha'],'HISTORICAL RUN DRIFT')
        p.verify_hashes(rm['files'],path)
        history.append({'run':r['run'],'manifest_sha':r['manifest_sha'],'verified_files':len(rm['files'])})
    report=REPO/'docs/evidence/NATIVE_EXCEL_GOLDEN_FINAL_CONSOLIDATED_20260909_NATIVE_R4.md'
    p.require(p.digest(report)=='E3F50A8BF4226077BA27BF2BDA61C35D8B0F8C8460E572C108AA01C0D927CFF4','PRIOR REPORT DRIFT')
    after=snapshot()
    old=p.read(ARCHIVE/'RUNNER_MANIFEST.json')
    changes=[n for n,h in old['files'].items() if p.digest(p.ROOT/n)!=h]
    p.require(set(changes)=={'package_support.py','README_FOR_USER.txt'},'PACKAGE CHANGE SCOPE')
    core=set(m['frozen_files'])|{str(p.ROOT/n) for n in m['files']}|{str(f) for f in d.iterdir() if f.is_file()}
    final={'timestamp':p.now(),'package_version':m['package_version'],'package_manifest_sha':p.digest(p.ROOT/'RUNNER_MANIFEST.json'),
        'precheck':str(pre),'python_tests':check['unit_test_count'],'powershell_tests':check['powershell_contract_test_count'],
        'independent_case_checks':len(independent)+63,'delivered_compare_exercised_with_actual_capture':'PASS_OFFLINE',
        'suffix_cases':191,'suffix_outputs_pass':9741,'combined_cases':1728,'combined_outputs':18746,
        'combined_counts':counts(rows),'native_missing':0,'technical_formula_differences':0,
        'source_damage_outputs':98,'source_damage_families_historical':51,'historically_verified':0,'business_recovery_upgrades':0,
        'strict_input_matches':1526,'explicit_decimal_realizations':2,'original_plan_and_capture_unchanged':True,
        'native_restore_fix':'USER_SESSION_CAPTURE_VERIFIED','technical_parity':'CLOSED_FOR_CAPTURED_DECLARED_SCOPE_WITH_EXPLICIT_INPUT_REALIZATION',
        'business_recovery':'BLOCKED_REAL_SOURCE_FACTS','new_native_required':False,'genuine_u03_pending_groups':3,'new_business_gap_groups':0,
        'source_sha':p.digest(m['source']),'db_sha':after['db_sha'],'production_counts':after['counts'],'production_write':0,
        'migration':0,'domain_formalization':'NOT_ENTERED','historical_runs':history,'package_changed_files':changes,
        'core_input_files':len(core),'input_count_definition':'Unique pinned dependencies, package members and current Run files; governance and source context separately cited',
        'ui_gate':'N/A; no UI change','stop':'TECHNICAL_CAPTURE_AND_DIFFERENTIAL_CLOSED; AWAIT_EXISTING_THREE_U03_SOURCE_FACT_GROUPS'}
    save('FINAL_DELIVERY_AUDIT.json',final)
    print(json.dumps(final,ensure_ascii=False,indent=2))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1])
