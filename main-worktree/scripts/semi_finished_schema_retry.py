"""Controlled retry artifact preparation; old failure evidence is immutable."""
import json, shutil, sys
from pathlib import Path
import semi_finished_schema_production as prior

ROOT = prior.ROOT
OUT = ROOT/'docs/evidence/semi_finished_schema_retry_20260909'
WORK = ROOT/'.runtime/semi-finished-schema-retry-20260909'
ISO = WORK/'rehearsal'
DB = ROOT/'backend/db.sqlite3'
PACKAGE = ROOT/'tools/semi-finished-model-closure/20260909-room-door'
OLD = ROOT/'docs/evidence/semi_finished_schema_production_20260909'
sha, snapshot, digest, now = prior.sha, prior.snapshot, prior.digest, prior.now

def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')

def load(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))

def manifest():
    return prior.package_check()

def tree(root):
    return {str(p.relative_to(root)).replace('\\','/'): sha(p) for p in root.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.sqlite3')}

def prepare():
    assert not ISO.exists(), 'REHEARSAL_ALREADY_PREPARED'
    current = snapshot(DB)
    previous = json.loads((OLD/'PREFLIGHT.json').read_text(encoding='utf-8'))
    assert current['sha256'] == previous['sha256']
    assert current['tables'] == previous['tables'] and current['recorder'] == previous['recorder']
    previous_code=json.loads((OLD/'CODE_BASELINE.json').read_text(encoding='utf-8'))
    for f,h in previous_code.items():
        assert (sha(f) if Path(f).exists() else None)==h, ('RUNTIME_DRIFT',f)
    save('START_BASELINE.json',current)
    save('CODE_BASELINE.json',previous_code)
    backup=json.loads((OLD/'BACKUP.json').read_text(encoding='utf-8'))
    assert sha(backup['backup'])==current['sha256']
    # Exact directory copies are rehearsal inputs, never hardlinked writable source.
    shutil.copytree(ROOT/'backend',ISO/'backend',ignore=shutil.ignore_patterns('venv','__pycache__','*.sqlite3','*.sqlite3-*','logs','media','.pytest_cache'))
    shutil.copytree(ROOT/'frontend',ISO/'frontend',ignore=shutil.ignore_patterns('node_modules','dist','test-results','playwright-report','.vite'))
    shutil.copytree(ROOT/'docs/evidence',ISO/'docs/evidence',ignore=shutil.ignore_patterns('semi_finished_schema_retry_20260909'))
    shutil.copytree(ROOT/'docs/governance',ISO/'docs/governance')
    shutil.copy2(backup['backup'],ISO/'rehearsal.sqlite3')
    originals=WORK/'original-runtime'
    originals.mkdir(parents=True)
    files=[f['path'] for f in manifest()['files']]+[
        'backend/pde/semi_finished_schema_status.py','backend/pde/semi_finished_configuration_preview.py',
        'frontend/src/meta/components/SemiFinishedConfigurationPreview.vue']
    code=[]
    for f in files:
        src=ROOT/f;dst=originals/f
        if src.exists():
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        code.append({'path':f,'sha':sha(src) if src.exists() else None})
    save('RUNTIME_RESTORE_MANIFEST.json',code)
    for f in manifest()['files']:
        dest=ISO/f['path'];dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(PACKAGE/f['packagePath'],dest)
        assert sha(dest)==f['testedSha']
    save('PREPARED.json',{'time':now(),'status':'PASS','productionSHA':sha(DB),
        'originalBackup':backup['backup'],'rehearsal':str(ISO),'frozenFiles':manifest()['files'],
        'priorCodeBaselineVerified':len(previous_code),'businessWrite':0})
    print('PREPARE PASS; production unchanged; isolated copy '+str(ISO))

def migrate(stage):
    isprod=stage=='production'
    backend=ROOT/'backend' if isprod else ISO/'backend'
    path=DB if isprod else ISO/'rehearsal.sqlite3'
    # Reuse reviewed executor with this run's isolated evidence namespace only.
    prior.OUT=OUT
    prior.WORK=WORK
    if isprod:
        assert not (OUT/'EXECUTION_STARTED.json').exists(), 'NO_THIRD_AUTOMATIC_ATTEMPT'
        assert load('PACKAGE_READY.json')['status']=='PASS'
        assert sha(path)==load('BACKUP.json')['backupSHA']
        save('EXECUTION_STARTED.json',{'time':now(),'stage':stage,'backupSHA':sha(path)})
    else:
        save('PREFLIGHT.json',load('START_BASELINE.json'))
        import subprocess
        # discover_plan needs a fresh Django process; this process has not bootstrapped yet.
        conn=prior.bootstrap(backend,path)
        plan=prior.discover_plan(conn);conn.close()
        save('FROZEN_MIGRATION_PLAN.json',plan)
        # Reopen same alias read/write before migration.
        from django.db import connections
        connections.close_all()
        connections['default'].settings_dict.update(NAME=str(path),OPTIONS={'timeout':30})
    result=prior.apply_exact(backend,path,production=isprod)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='migrate':migrate(sys.argv[2])
