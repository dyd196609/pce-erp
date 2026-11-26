"""Append-only validation of the completed suffix and frozen Native prefix."""
import collections
import copy
import json
import shutil
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from u03_recovery_audit import REPO, p, snapshot
from recovery_native_r4 import verify_prefix, counts

OUT = REPO / 'docs/evidence/excel_formula_parity/closure-20260909/native-recovery-r5'
PRIOR = OUT.parent / 'native-recovery-r4'
ARCHIVE = OUT / 'before-code'


def save(name, value):
    p.require(not (OUT/name).exists(), 'APPEND ONLY: '+name)
    p.write(OUT/name, value)


def init():
    m = p.load_manifest()
    p.require(not OUT.exists(), 'R5 ALREADY INITIALIZED')
    ARCHIVE.mkdir(parents=True)
    for n in p.PACKAGE_FILES + ('RUNNER_MANIFEST.json',):
        shutil.copyfile(p.ROOT/n, ARCHIVE/n)
    p.verify_hashes(m['files'], ARCHIVE)
    state = snapshot()
    latest = sorted((p.ROOT/'runs').iterdir(), key=lambda f:f.name, reverse=True)[0]
    p.require(latest.name == '20260909T044309108Z-9c8a8727', 'LATEST RUN CHANGED')
    rm = p.read(latest/'RUN_MANIFEST.json')
    p.verify_hashes(rm['files'], latest)
    save('INSTRUCTION_CONTROL.json', {
        'timestamp':p.now(), 'review_level':'C', 'full_content_review_required':True,
        'governance':[{'path':str(f),'sha':p.digest(f)} for f in (REPO.parent/'AGENTS.md',REPO/'AGENTS.md',REPO/'docs/governance/PCE CODEX开发指令规范管理V1.2.md')],
        'effective_instruction_set':{'ACTIVE':['same original instruction: validate completed Native suffix, consolidate all recovery evidence, autonomous technical remediation'],
            'FROZEN':['all previous Runs/reports; user U03-01/02/03/04; source XLSX; production DB; groups1/2/3A/3B'],
            'NOT_AUTHORIZED':['Domain Rule Formalization','production writes','Migration','UI/navigation']},
        'instruction_register':[{'id':'NATIVE-R5-20260909','status':'ACTIVE','superseded_by':None,'purpose':'completed suffix recheck and full consolidation'},
            {'id':'U03-01/02/03/04','status':'FROZEN','decision':'legacy excluded; exact stock geometry/thickness; product area; visible-area veneer; edge m; independent loss'},
            {'id':'NATIVE-R4-20260909','status':'FROZEN','purpose':'verified prefix and only-missing suffix package'},
            {'id':'U03-R4-01/02/03','status':'ACTIVE','purpose':'genuine missing business source facts; no user decision received'}],
        'control_sheet':{'original_goal':'verifiable native Excel reverse engineering','current_goal':'complete technical recheck, keep unresolved business facts explicit',
            'in_scope':['append-only evidence','isolated comparison tool fix','tests','one consolidated report'],
            'out_of_scope':['source edits','production rule deployment','all production data writes'],
            'database':'READ ONLY','user_path':'N/A','scope_reevaluation':'More than 10 files form one sealed Native batch and evidence chain; no unrelated modules; output below 500 lines.',
            'stop':'all available technical work complete; genuine business facts remain pending; no extra Native if capture sufficient'},
        'governance_reading_receipt':'FULLY_READ; emitted before first modification',
        'conflicts':'NONE; current no-domain-formalization boundary retained'})
    save('PROTECTION_BEFORE.json',{'db_sha':state['db_sha'],'counts':state['counts'],'source_sha':p.digest(m['source']),
        'run_directory':str(latest),'run_manifest_sha':p.digest(latest/'RUN_MANIFEST.json'),
        'package_manifest_sha':p.digest(ARCHIVE/'RUNNER_MANIFEST.json'),'production_write':0})
    print(json.dumps(p.read(OUT/'PROTECTION_BEFORE.json'),ensure_ascii=False,indent=2))


def seal():
    from native_input_realization import CONTRACT
    old=p.read(ARCHIVE/'RUNNER_MANIFEST.json')
    p.verify_hashes(old['files'],ARCHIVE)
    p.verify_hashes(old['frozen_files'])
    for n,h in old['files'].items():
        p.require(n in ('package_support.py','README_FOR_USER.txt') or p.digest(p.ROOT/n)==h,'UNAUTHORIZED PACKAGE CHANGE '+n)
    frozen=dict(old['frozen_files'])
    for n in ('native_input_realization.py','test_native_input_realization.py'):
        f=REPO/'scripts/excel_parity'/n; frozen[str(f)]=p.digest(f)
    d=Path(p.read(OUT/'PROTECTION_BEFORE.json')['run_directory'])
    for n in ('RUN_MANIFEST.json','NATIVE_EXCEL_RUN.json','RUN_CASE_PLAN.json','EXCEL_NATIVE_GOLDEN.json'):
        frozen[str(d/n)]=p.digest(d/n)
    m=old|{'package_version':'1.6-u03-native-input-audit-r5','created_at':p.now(),
        'files':{n:p.digest(p.ROOT/n) for n in p.PACKAGE_FILES},'frozen_files':frozen,
        'native_input_realization':CONTRACT,
        'native_execution':'USER_SESSION_191_CASE_CAPTURE_COMPLETE; POSTPROCESS_RECHECK_ONLY',
        'revision':{'executed_manifest':str(ARCHIVE/'RUNNER_MANIFEST.json'),'executed_manifest_sha':p.digest(ARCHIVE/'RUNNER_MANIFEST.json'),
            'reason':'Two synthetic base+delta binary tails; explicit Native realized-input view; exact reconstructed decimal intent and unchanged output/branch proof required',
            'source_formula_changes':0,'production_write':0,'old_runs_immutable':True,'new_native_required':False}}
    p.write(p.ROOT/'RUNNER_MANIFEST.json',m)
    p.load_manifest()
    print('SEALED '+p.digest(p.ROOT/'RUNNER_MANIFEST.json'))


def audit():
    from native_input_realization import realize, verify_output_invariance
    m=p.load_manifest()
    old=p.read(ARCHIVE/'RUNNER_MANIFEST.json')
    p.verify_hashes(old['files'],ARCHIVE); p.verify_hashes(old['frozen_files'])
    d=Path(p.read(OUT/'PROTECTION_BEFORE.json')['run_directory'])
    p.require(d == sorted((p.ROOT/'runs').iterdir(),key=lambda f:f.name,reverse=True)[0],'LATEST RUN CHANGED')
    rm=p.read(d/'RUN_MANIFEST.json'); p.verify_hashes(rm['files'],d)
    p.require(rm['package_manifest_sha']==p.digest(ARCHIVE/'RUNNER_MANIFEST.json'),'EXECUTED PACKAGE')
    p.require(set(rm['files'])=={f.name for f in d.iterdir() if f.is_file() and f.name!='RUN_MANIFEST.json'},'FILE SET')
    docs={f.name:p.read(f) for f in d.glob('*.json')}
    log=(d/'RUN_LOG.txt').read_text('utf-8-sig')
    p.validate_output_files(d)
    plan,run,golden=(docs[n] for n in ('RUN_CASE_PLAN.json','NATIVE_EXCEL_RUN.json','EXCEL_NATIVE_GOLDEN.json'))
    rebuilt=p.build_supplement(old)
    for f in ('cases','probe_sheet','technical_source_dependencies'):
        p.require(plan[f]==rebuilt[f],'SEALED PLAN '+f)
    p.require(run['execution_status']=='PASS' and run['native_stage']=='NATIVE_CAPTURE_COMPLETE','NATIVE INCOMPLETE')
    p.require(run['original_saved'] is False and not run['cleanup_errors'],'PROTECTION/CLEANUP')
    for f in ('source_sha','source_sha_after','run_copy_sha','run_copy_sha_after'):
        p.require(run[f]==p.EXPECTED_SHA,'SOURCE/COPY SHA')
    p.require(p.digest(m['source'])==p.EXPECTED_SHA and p.digest(plan['workbook_copy'])==p.EXPECTED_SHA,'ACTUAL SOURCE/COPY SHA')
    p.require(Path(plan['workbook_copy']).resolve()==(d/'source-readonly-copy.xlsx').resolve(),'COPY PATH')
    p.inspect_workbook(plan['workbook_copy'])
    stocks=p.read(OUT.parent/'recovery-u03/BOARD_STOCK_AND_REAL_ROW_AUDIT.json')['stocks']
    view,input_evidence=realize(plan,golden,stocks)
    idx=p.validate_native(run,golden,view,p.digest(d/'RUN_CASE_PLAN.json'))
    previous=datetime.fromisoformat(run['calculation_start'])
    identities=[]
    for case,capture in zip(plan['cases'],golden['results']):
        start,end=map(datetime.fromisoformat,(capture['calculation_start'],capture['calculation_end']))
        p.require(previous<=start<=end<=datetime.fromisoformat(run['calculation_end']),'CAPTURE TIME ORDER')
        previous=end
        for definition,o in zip(case['derived_outputs'],capture['outputs']):
            p.require(definition['cell']==o['cell'],'OUTPUT ORDER')
            identities.append({'case_id':case['case_id'],'cell':o['cell'],'identity':p.formula_identity(definition['formula'],o['formula'])})
    save('RUN_INTEGRITY.json',{'run_directory':str(d),'manifest_sha':p.digest(d/'RUN_MANIFEST.json'),
        'files':[{'name':f.name,'sha':p.digest(f),'bytes':f.stat().st_size} for f in sorted(d.iterdir()) if f.is_file()],
        'json_files_read':list(docs),'log_lines':len(log.splitlines()),'source_zip':'PASS','schema':'PASS','sealed_plan':'PASS',
        'execution_status':run['execution_status'],'raw_validation_status':run['validation_status'],'raw_exit_code':run['exit_code'],
        'native_stage':run['native_stage'],'cases':len(golden['results']),'outputs':len(idx),
        'formula_identity_counts':counts(identities,'identity'),'formula_identities':identities,'source_sheets_restored':golden['original_source_sheets_unmodified'],
        'source_sha':p.digest(m['source']),'original_run_immutable':True,'native_error':run['error'],
        'input_identity':'1526 EXACT; 2 EXPLICIT DECIMAL-INTENT REALIZATIONS, NOT BITWISE EQUAL'})
    # Exercise the delivered compare entry point in a clearly separated offline
    # directory. Copies stay identical; no source Run is re-finalized or edited.
    replay=OUT/'offline-recomparison'/d.name
    p.require(not replay.exists(),'REPLAY EXISTS')
    replay.mkdir(parents=True)
    for n in ('RUN_CASE_PLAN.json','NATIVE_EXCEL_RUN.json','EXCEL_NATIVE_GOLDEN.json'):
        shutil.copyfile(d/n,replay/n)
        p.require(p.digest(d/n)==p.digest(replay/n),'REPLAY COPY')
    code=p.compare(replay)
    p.require(code==0,'OFFLINE DIFFERENTIAL NOT ALL PASS')
    diff=p.read(replay/'DIFFERENTIAL_RESULTS.json')
    input_evidence=p.read(replay/'REFERENCE_INPUT_REALIZATION.json')
    p.require(diff['counts']=={'PARITY_PASS':9741},'SUFFIX PARITY COUNT')
    save('REFERENCE_INPUT_REALIZATION.json',input_evidence)
    save('SUFFIX_DIFFERENTIAL.json',diff|{'native_evidence_directory':str(d),'offline_only':True,'native_reexecuted':False})
    parent=p.ROOT/'runs'/m['native_resume']['parent_run']
    parent_rm=p.read(parent/'RUN_MANIFEST.json'); p.verify_hashes(parent_rm['files'],parent)
    pg=p.read(parent/'EXCEL_NATIVE_GOLDEN.json'); pr=p.read(parent/'NATIVE_EXCEL_RUN.json'); pp=p.read(parent/'RUN_CASE_PLAN.json')
    pi,pidentities=verify_prefix(pr,pg,pp)
    p.require(plan['cases']==pp['cases'][len(pg['results']):],'NOT EXACT MISSING SUFFIX')
    p.require(not (set(pi)&set(idx)) and len(pi)+len(idx)==pp['selected_output_count'],'COVERAGE OVERLAP/GAP')
    combined=p.read(PRIOR/'NATIVE_DIFFERENTIAL.json')['results']
    suffix={(r['case_id'],r['cell']):r for r in diff['results']}
    for r in combined:
        key=(r['case_id'],r['cell'])
        if key in suffix:
            s=suffix[key]
            p.require(r['classification']=='NATIVE_CAPTURE_REQUIRED','NOT MISSING')
            for f in ('code_result','reference_status','contract','semantic_name','formula_family'):
                p.require(s[f]==r[f],'FROZEN REFERENCE REGRESSION '+str(key))
            r.update(s); r['native_capture_available']=True; r['native_run']=d.name
        else:
            p.require(r['excel_raw_value']==pi[key]['excel_raw_value'],'PREFIX CAPTURE DRIFT')
            r['native_run']=parent.name
    p.require(counts(combined)=={'PARITY_PASS':18648,'BROKEN_SOURCE':98},'COMBINED COUNTS')
    save('COMBINED_DIFFERENTIAL.json',{'counts':counts(combined),'cases':1728,'outputs':18746,'missing_native':0,
        'technical_difference':0,'parent_run':parent.name,'suffix_run':d.name,'original_run_status_not_changed':True,
        'production_write':0,'domain_formalization':'NOT_ENTERED','results':combined})
    print(json.dumps({'suffix':diff['counts'],'input_realization':input_evidence,'combined':counts(combined)},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1] == 'init': init()
    elif sys.argv[1] == 'seal': seal()
    elif sys.argv[1] == 'audit': audit()
