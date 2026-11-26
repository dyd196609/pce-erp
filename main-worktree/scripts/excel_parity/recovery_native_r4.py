"""Read-only partial Native evidence audit. Never upgrades a failed Run to PASS."""
import collections
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime
from u03_recovery_audit import REPO, DB, DB_SHA, p, snapshot
from recovery_batch import build

OUT = REPO / 'docs/evidence/excel_formula_parity/closure-20260909/native-recovery-r4'
ARCHIVE = OUT / 'before-code'


def save(name, data):
    target = OUT / name
    p.require(not target.exists(), 'APPEND ONLY: ' + str(target))
    p.write(target, data)


def counts(rows, key='classification'):
    return dict(collections.Counter(r[key] for r in rows))


def verify_prefix(run, golden, plan):
    """Validate only committed, restored cases before the failed case; no fake metadata."""
    p.require(run['execution_status'] == 'BLOCKED' and golden['status'] == 'BLOCKED', 'EXPECTED FROZEN PARTIAL RUN')
    p.require(run['mode'] == 'USER_SESSION_NATIVE' and golden['engine'] == 'Microsoft Excel Calculation Engine', 'NATIVE ENGINE REQUIRED')
    p.require(run['run_id'] == golden['run_id'] == plan['run_id'], 'RUN ID')
    p.require(run['original_unchanged'] is True and run['original_saved'] is False, 'SOURCE PROTECTION')
    for k in ('source_sha', 'source_sha_after', 'run_copy_sha', 'run_copy_sha_after'):
        p.require(run[k] == p.EXPECTED_SHA, 'SOURCE/COPY SHA ' + k)
    p.require(run['excel_pid'] and run['excel_version'] and run['session_id'] > 0 and run['calculation_start'], 'NATIVE IDENTITY')
    p.require(not run['cleanup_errors'], 'CLEANUP FAILURE')
    p.require(golden['technical_sheet_initialized'] == plan['probe_sheet']['name'], 'PROBE INITIALIZATION')
    captures = golden['results']
    p.require(0 < len(captures) < len(plan['cases']) and run['result_count'] == len(captures), 'PARTIAL COVERAGE')
    p.require([c['case_id'] for c in captures] == [c['case_id'] for c in plan['cases'][:len(captures)]], 'MUST BE CONTIGUOUS COMMITTED PREFIX')
    indexed, identities = {}, []
    previous_end = datetime.fromisoformat(run['calculation_start'])
    for case, capture in zip(plan['cases'], captures):
        p.require(capture['restored'] is True, 'UNRESTORED CAPTURE')
        start, end = map(datetime.fromisoformat, (capture['calculation_start'], capture['calculation_end']))
        p.require(previous_end <= start <= end <= datetime.fromisoformat(run['error']['time']), 'CAPTURE ORDER')
        previous_end = end
        changes = {(o['sheet'], o['cell']): o for o in case['overrides']}
        p.require(len(capture['overrides']) == len(changes), 'INPUT COUNT')
        p.require({(o['sheet'], o['cell']) for o in capture['overrides']} == set(changes), 'INPUT KEYS')
        for applied in capture['overrides']:
            change = changes[(applied['sheet'], applied['cell'])]
            p.require(applied['requested_type'] == change['type'] and applied['requested_value'] == change['value'], 'REQUESTED INPUT')
            p.require(applied['actual'] == {'type': change['type'], 'value': change['value']}, 'NATIVE INPUT')
            p.require(p.type_matches(applied['actual']['value'], {'number':'number','text':'string','boolean':'boolean','blank':'null'}[change['type']]), 'INPUT VARIANT')
        expected = {o['cell']: o for o in case['derived_outputs']}
        p.require(len(capture['outputs']) == len(expected) and {o['cell'] for o in capture['outputs']} == set(expected), 'OUTPUT SET')
        for output in capture['outputs']:
            definition = expected[output['cell']]
            p.require(output['has_formula'] is True and output['formula_family'] == definition['formula_family'], 'FORMULA/FAMILY')
            identity = p.formula_identity(definition['formula'], output['formula'])
            p.require(identity is not None, 'FORMULA DRIFT ' + case['case_id'] + ' ' + output['cell'])
            raw = output['excel_raw_value']
            typ = {'blank':'null','error':'string','text':'string','number':'number','boolean':'boolean'}.get(raw['type'])
            p.require(typ and p.type_matches(raw['value'], typ), 'OUTPUT VARIANT')
            if raw['type'] == 'error':
                errors = {2000:'#NULL!',2007:'#DIV/0!',2015:'#VALUE!',2023:'#REF!',2029:'#NAME?',2036:'#NUM!',2042:'#N/A',2045:'#SPILL!'}
                p.require(type(output['native_variant_value']) is int and errors.get(output['native_variant_value'] & 65535) == raw['value'], 'CVERROR IDENTITY')
            key = (case['case_id'], output['cell'])
            p.require(key not in indexed, 'DUPLICATE CAPTURE')
            indexed[key] = output
            identities.append({'case_id': key[0], 'cell': key[1], 'identity': identity, 'expected': definition['formula'], 'actual': output['formula']})
        obs = case.get('observations', [])
        actual = capture.get('observations', [])
        p.require(len(obs) == len(actual) and {(o['sheet'],o['cell']) for o in obs} == {(o['sheet'],o['cell']) for o in actual}, 'OBSERVATION COVERAGE')
    return indexed, identities


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(parents=True, exist_ok=True)
    if not ARCHIVE.exists():
        m = p.load_manifest()
        ARCHIVE.mkdir()
        for name in p.PACKAGE_FILES + ('RUNNER_MANIFEST.json',):
            shutil.copyfile(p.ROOT/name, ARCHIVE/name)
        save('INSTRUCTION_CONTROL.json', {
            'created_at':p.now(), 'review_level':'C', 'full_content_review_required':True,
            'governance':[{'path':str(f),'sha':p.digest(f)} for f in (REPO.parent/'AGENTS.md',REPO/'AGENTS.md',REPO/'docs/governance/PCE CODEX开发指令规范管理V1.2.md')],
            'effective_instruction_set':{'ACTIVE':['20260909 user: latest Native Run integrity + R1-R6 + autonomous technical correction + consolidated report'],
                'FROZEN':['all three Native Runs; 100/100 Level1A; 1510/31 real; 434/22 boundary; 2376 candidate; U03 decisions; source XLSX; production DB; Groups1/2/3A/3B'],
                'NOT_AUTHORIZED':['Domain Rule Formalization','production writes','Migration','UI/navigation']},
            'instruction_register':[{'id':'NATIVE-R4-20260909','status':'ACTIVE','purpose':'Validate the user-completed recovery Native batch; salvage verified prefix without changing failed Run'},
                {'id':'U03-01/02/03/04','status':'FROZEN','decision':'legacy excluded; exact geometry and thickness; product net area; veneer visible area; edge length m; loss separate'}],
            'control_sheet':{'original_goal':'Verifiable Excel reverse engineering','current_goal':'Validate latest Native + minimal runner remediation',
                'in_scope':['read all Native evidence','append-only differential','isolated technical fixes/tests/package'],
                'out_of_scope':['source workbook modification','domain production rules','all production business writes'],
                'database':'READ ONLY','user_path':'N/A; no UI change',
                'stop':'validated available evidence and all technical fixes; missing Native evidence or genuine business data adjudication',
                'scope_reevaluation':'More than 10 dependency/evidence files: one user-requested batch, one report, no unrelated modules or delegation.'}})
        save('PROTECTION_BEFORE.json', snapshot())
    m = p.read(ARCHIVE/'RUNNER_MANIFEST.json')
    p.verify_hashes(m['files'], ARCHIVE)
    p.verify_hashes(m['frozen_files'])
    runs = sorted((p.ROOT/'runs').iterdir(), key=lambda f:f.name, reverse=True)
    run_dir = next(f for f in runs if f.is_dir())
    p.require(run_dir.name == '20260909T040440577Z-a6fb1daa', 'LATEST RUN CHANGED; REVIEW NEW RUN')
    rm = p.read(run_dir/'RUN_MANIFEST.json')
    p.verify_hashes(rm['files'], run_dir)
    p.require(set(rm['files']) == {f.name for f in run_dir.iterdir() if f.is_file() and f.name != 'RUN_MANIFEST.json'}, 'RUN FILE SET')
    p.require(rm['package_manifest_sha'] == p.digest(ARCHIVE/'RUNNER_MANIFEST.json'), 'EXECUTED PACKAGE')
    documents = {f.name:p.read(f) for f in run_dir.glob('*.json')}
    log = (run_dir/'RUN_LOG.txt').read_text(encoding='utf-8-sig')
    p.validate_output_files(run_dir)
    plan, run, golden = (documents[n] for n in ('RUN_CASE_PLAN.json','NATIVE_EXCEL_RUN.json','EXCEL_NATIVE_GOLDEN.json'))
    p.require(run['plan_sha'] == golden['plan_sha'] == p.digest(run_dir/'RUN_CASE_PLAN.json'), 'PLAN SHA')
    p.require(golden['source_sha'] == p.EXPECTED_SHA and p.digest(m['source']) == p.EXPECTED_SHA, 'SOURCE SHA')
    p.require(Path(plan['workbook_copy']).resolve() == (run_dir/'source-readonly-copy.xlsx').resolve(), 'COPY PATH')
    p.inspect_workbook(plan['workbook_copy'])
    rebuilt = build(m)
    for field in ('cases','probe_sheet','technical_source_dependencies'):
        p.require(plan[field] == rebuilt[field], 'SEALED PLAN REBUILD: ' + field)
    indexed, identities = verify_prefix(run, golden, plan)
    save('RUN_INTEGRITY.json', {'run_directory':str(run_dir),'run_manifest_sha':p.digest(run_dir/'RUN_MANIFEST.json'),
        'files':[{'name':f.name,'sha':p.digest(f),'bytes':f.stat().st_size} for f in sorted(run_dir.iterdir()) if f.is_file()],
        'all_json_parsed':list(documents),'log_lines':len(log.splitlines()),'source_zip_checked':True,'output_schema':'PASS','sealed_plan_identity':'PASS',
        'execution_status':'BLOCKED','complete_run_acceptance':'FAIL','prefix_usable':'VERIFIED_COMPLETED_RESTORED_CASES_ONLY',
        'captured_cases':len(golden['results']),'captured_outputs':len(indexed),'missing_cases':len(plan['cases'])-len(golden['results']),
        'formula_identity_counts':counts(identities,'identity'),'identities':identities,'failed_case':plan['cases'][len(golden['results'])],
        'native_error':run['error'],'global_source_sheet_restore_flag':golden['original_source_sheets_unmodified'],
        'source_copy_bytes_unchanged':True,'run_immutable':True})
    rows = p.evaluate_reference(m, plan, progress=True)
    comparator = p.reference(m)['differential'].compare_result
    for row in rows:
        capture = indexed.get((row['case_id'],row['cell']))
        row['native_capture_available'] = capture is not None
        row['excel_raw_value'] = capture['excel_raw_value'] if capture else None
        if capture is None:
            row['classification'] = 'NATIVE_CAPTURE_REQUIRED'
        elif row['reference_status'] == 'BROKEN_DEPENDENCY':
            row['classification'] = 'BROKEN_SOURCE'
        elif row['reference_status'] != 'EVALUATED_NOT_NATIVE_VERIFIED':
            row['classification'] = 'TECHNICAL_FAIL'
        else:
            row['comparison'] = comparator(row['code_result'], capture['excel_raw_value'], row['contract'])
            row['classification'] = 'PARITY_PASS' if row['comparison']['status'] == 'PASS' else 'TECHNICAL_FAIL'
    summary = {'counts':counts(rows),'cohorts':{co:counts([r for r in rows if r['cohort']==co]) for co in sorted({r['cohort'] for r in rows})},
        'captured_cases':len(golden['results']),'captured_outputs':len(indexed),'planned_outputs':len(rows),
        'production_write':0,'domain_formalization':'NOT_ENTERED','whole_run_pass':False}
    save('NATIVE_DIFFERENTIAL.json',summary | {'results':rows})
    save('MISSING_NATIVE_CASES.json',{'run_directory':str(run_dir),'cases':plan['cases'][len(golden['results']):],
        'reason':'Not committed after input restoration failure; never substitute reference values'})
    save('TECHNICAL_DIFFERENCES.json',[r for r in rows if r['classification']=='TECHNICAL_FAIL'])
    old = p.read(p.ROOT/'runs/20260909T010756709Z-772c0971/EXCEL_NATIVE_GOLDEN.json')
    old_idx = {(c['case_id'],o['cell']):o for c in old['results'] for o in c['outputs']}
    gap = []
    regression = []
    for key, old_o in old_idx.items():
        p.require(key in indexed,'FROZEN OUTPUT NO REGRESSION CAPTURE')
        new_o=indexed[key]
        if old_o['excel_raw_value']['type']=='error' and str(old_o['excel_raw_value']['value']).startswith('##'):
            gap.append({'case_id':key[0],'cell':key[1],'old_display':old_o['excel_raw_value']['value'],
                'native_raw':new_o['excel_raw_value'],'native_variant_value':new_o['native_variant_value']})
        else:
            p.require(old_o['excel_raw_value']==new_o['excel_raw_value'],'OLD NATIVE OUTPUT REGRESSION '+str(key))
            regression.append(key)
    p.require(len(gap)==44,'EXPECTED 44 ERROR GAPS')
    save('FROZEN_NATIVE_REGRESSION.json',{'unchanged_outputs':len(regression),'error_gap_count':44,'error_gap_results':gap,
        'error_codes':counts([{'code':r['native_raw']['value']} for r in gap],'code'),'old_run_not_modified':True})
    after = snapshot()
    save('PROTECTION_AFTER_AUDIT.json',{'db_sha':after['db_sha'],'counts':after['counts'],'source_sha':p.digest(m['source']),'production_write':0})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('AUDIT_DIRECTORY='+str(OUT))


if __name__ == '__main__':
    main()
