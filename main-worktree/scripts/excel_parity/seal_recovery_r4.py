"""Seal the exact uncommitted suffix; preserve the executed 1.4 package."""
import sys
from pathlib import Path
from recovery_native_r4 import OUT, ARCHIVE, p, REPO


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    old = p.read(ARCHIVE/'RUNNER_MANIFEST.json')
    p.verify_hashes(old['files'], ARCHIVE)
    p.verify_hashes(old['frozen_files'])
    allowed = {'package_support.py','native_excel_runner.ps1','test_native_contract.ps1','README_FOR_USER.txt'}
    for n, sha in old['files'].items():
        p.require(n in allowed or p.digest(p.ROOT/n)==sha,'UNAUTHORIZED PACKAGE CHANGE: '+n)
    run=p.ROOT/'runs/20260909T040440577Z-a6fb1daa'
    rm=p.read(run/'RUN_MANIFEST.json')
    p.verify_hashes(rm['files'],run)
    integrity=p.read(OUT/'RUN_INTEGRITY.json')
    p.require(p.digest(run/'RUN_MANIFEST.json')==integrity['run_manifest_sha'],'PARENT RUN DRIFT')
    diff=p.read(OUT/'NATIVE_DIFFERENTIAL.json')
    p.require(diff['counts']=={'PARITY_PASS':8907,'BROKEN_SOURCE':98,'NATIVE_CAPTURE_REQUIRED':9741},'PREFIX NOT VALIDATED')
    frozen=dict(old['frozen_files'])
    for name in ('recovery_native_r4.py','test_recovery_native_r4.py','seal_recovery_r4.py'):
        path=REPO/'scripts/excel_parity'/name
        frozen[str(path)]=p.digest(path)
    for name in ('MISSING_NATIVE_CASES.json','RUN_INTEGRITY.json','NATIVE_DIFFERENTIAL.json','FROZEN_NATIVE_REGRESSION.json'):
        frozen[str(OUT/name)]=p.digest(OUT/name)
    for name in ('RUN_MANIFEST.json','RUN_CASE_PLAN.json','EXCEL_NATIVE_GOLDEN.json'):
        frozen[str(run/name)]=p.digest(run/name)
    current=old|{'package_version':'1.5-u03-native-resume-r4','created_at':p.now(),
        'files':{n:p.digest(p.ROOT/n) for n in p.PACKAGE_FILES},'frozen_files':frozen,
        'native_resume':{'parent_run':run.name,'parent_run_manifest_sha':p.digest(run/'RUN_MANIFEST.json'),
            'plan_path':str(run/'RUN_CASE_PLAN.json'),'plan_sha':p.digest(run/'RUN_CASE_PLAN.json'),
            'missing_path':str(OUT/'MISSING_NATIVE_CASES.json'),'missing_sha':p.digest(OUT/'MISSING_NATIVE_CASES.json'),
            'verified_prefix_cases':1537,'verified_prefix_outputs':9005,'missing_cases':191,'missing_outputs':9741},
        'native_execution':'NOT_EXECUTED_FOR_TYPED_RESTORE_REPAIR',
        'revision':{'executed_manifest':str(ARCHIVE/'RUNNER_MANIFEST.json'),'executed_manifest_sha':p.digest(ARCHIVE/'RUNNER_MANIFEST.json'),
            'reason':'0x80004002 saved-value COM restoration; explicit primitive types; single plan builder; only missing Native suffix',
            'source_formula_changes':0,'production_write':0,'old_runs_immutable':True}}
    plan=p.build_supplement(current)
    current['batch_counts']={'cases':len(plan['cases']),'outputs':plan['selected_output_count'],'probe_cells':len(plan['probe_sheet']['cells'])}
    p.write(p.ROOT/'RUNNER_MANIFEST.json',current)
    p.load_manifest()
    print(__import__('json').dumps({'manifest_sha':p.digest(p.ROOT/'RUNNER_MANIFEST.json'),'batch_counts':current['batch_counts']},indent=2))


if __name__=='__main__': main()
