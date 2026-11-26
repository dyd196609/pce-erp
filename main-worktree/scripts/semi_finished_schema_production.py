"""Explicitly authorized, allowlisted schema-only deployment. No business replay."""
import ast, hashlib, json, os, shutil, sqlite3, sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/evidence/semi_finished_schema_production_20260909'
PACKAGE = ROOT / 'tools/semi-finished-model-closure/20260909-room-door'
TESTED = ROOT / '.runtime/room-door-edge-20260909/backend'
DB = ROOT / 'backend/db.sqlite3'
WORK = ROOT / '.runtime/semi-finished-schema-production-20260909'
INSTRUCTION = Path('C:/Users/DAODA/.codex/attachments/4e1bbdf5-9e92-40fe-933f-9011b64e9e0f/pasted-text.txt')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
def digest(v): return hashlib.sha256(json.dumps(v, ensure_ascii=False, default=str, sort_keys=True).encode()).hexdigest().upper()
def now(): return datetime.now(timezone.utc).isoformat()
def read(n): return json.loads((OUT/n).read_text(encoding='utf-8'))
def save(n, v):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/n).write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
def snapshot(path):
    path=Path(path).resolve(); before=sha(path)
    with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        tables={}
        for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
            cols=[r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]
            rows=sorted(c.execute(f'SELECT * FROM "{t}"').fetchall(),key=repr)
            tables[t]={'count':len(rows),'columns':cols,'contentSha':digest(rows),
                'schema':c.execute('SELECT sql FROM sqlite_master WHERE type=\'table\' AND name=?',(t,)).fetchone()[0],
                'foreignKeys':c.execute(f'PRAGMA foreign_key_list("{t}")').fetchall(),
                'indexes':c.execute('SELECT name,sql FROM sqlite_master WHERE type=\'index\' AND tbl_name=? ORDER BY name',(t,)).fetchall()}
        result={'path':str(path),'sha256':before,'size':path.stat().st_size,'capturedAt':now(),
            'integrity':c.execute('PRAGMA integrity_check').fetchall(), 'foreignKeys':c.execute('PRAGMA foreign_key_check').fetchall(),
            'journalMode':c.execute('PRAGMA journal_mode').fetchone()[0],
            'recorder':c.execute('SELECT app,name,applied FROM django_migrations ORDER BY app,name').fetchall(), 'tables':tables}
    assert sha(path)==before, 'CONCURRENT_DATABASE_DRIFT'
    assert result['integrity']==[('ok',)] and not result['foreignKeys'], 'DATABASE_INTEGRITY_OR_FK_FAILED'
    return json.loads(json.dumps(result, default=str))
def bootstrap(backend, path, readonly=True):
    sys.path.insert(0,str(ROOT/'backend/venv/Lib/site-packages'))
    sys.path.insert(0,str(backend))
    os.environ['DJANGO_SETTINGS_MODULE']='pce_backend.settings'
    from django.conf import settings
    if backend==ROOT/'backend':
        assert Path(settings.DATABASES['default']['NAME']).resolve()==DB.resolve(), 'PRODUCTION_SETTING_PATH_MISMATCH'
    settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3',
        'NAME':Path(path).resolve().as_uri()+'?mode=ro' if readonly else str(Path(path).resolve()),
        'OPTIONS':{'uri':True} if readonly else {'timeout':30}}}
    import django
    django.setup()
    from django.db import connection
    if readonly:
        connection.ensure_connection();connection.connection.execute('PRAGMA query_only=ON')
    return connection
def package_check():
    manifest=json.loads((PACKAGE/'MANIFEST.json').read_text(encoding='utf-8'))
    for f in manifest['files']:
        assert sha(PACKAGE/f['packagePath'])==f['testedSha']==f['deliveredSha']==sha(TESTED/Path(f['path']).relative_to('backend')), f['path']
    evidence=ROOT/'docs/evidence/room_door_edge_20260909'
    for name in ('ISOLATED_TEST_RESULTS.json','ROUNDTRIP_RESULTS.json','ROLLBACK_RESULTS.json','FINAL_NON_REGRESSION.json'):
        assert json.loads((evidence/name).read_text(encoding='utf-8'))['status']=='PASS',name
    return manifest
def discover_plan(connection):
    from django.db.migrations.executor import MigrationExecutor
    manifest=package_check()
    names=[Path(f['path']).stem for f in manifest['files'] if '/migrations/' in f['path']]
    executor=MigrationExecutor(connection)
    candidates=[('pde',n) for n in names]
    leaves=[k for k in candidates if not any(k in executor.loader.get_migration(*other).dependencies for other in candidates)]
    assert len(leaves)==1
    targets=leaves
    pending=executor.migration_plan(targets)
    assert [(m.app_label,m.name) for m,back in pending]==candidates and not any(b for m,b in pending), 'UNREVIEWED_DEPENDENCY_OR_ALREADY_APPLIED'
    rows=[]
    for m,back in pending:
        f=next(f for f in manifest['files'] if Path(f['path']).stem==m.name)
        operations=[]
        for op in m.operations:
            kind=type(op).__name__
            assert kind not in ('RunPython','RunSQL'), 'DATA_MIGRATION_FORBIDDEN'
            if kind=='SeparateDatabaseAndState':assert not op.database_operations
            operations.append({'type':kind,'description':op.describe()})
        rows.append({'app':m.app_label,'name':m.name,'dependency':m.dependencies,'fileSha256':f['testedSha'],
            'testedPackageManifestSha256':sha(PACKAGE/'MANIFEST.json'),'packageFile':str(PACKAGE/f['packagePath']),
            'productionCandidateFile':str(ROOT/f['path']),'operations':operations})
    return json.loads(json.dumps({'targets':targets,'migrations':rows,'unreviewedDependencyCount':0,
        'allPendingNotExecuted':[list(k) for k in sorted(set(executor.loader.disk_migrations)-set(executor.loader.applied_migrations)-set(candidates))]}))
def preflight():
    assert not (OUT/'PREFLIGHT.json').exists(), 'DO_NOT_OVERWRITE_PREFLIGHT'
    manifest=package_check(); conn=bootstrap(TESTED,DB)
    plan=discover_plan(conn); conn.close()
    snap=snapshot(DB)
    previous=json.loads((ROOT/'docs/evidence/room_door_edge_20260909/FINAL_NON_REGRESSION.json').read_text(encoding='utf-8'))
    assert snap['sha256']==previous['productionSHA'],'PRODUCTION_DRIFT_FROM_FROZEN_BASELINE'
    assert snap['journalMode']=='delete','NON_DELETE_JOURNAL_REQUIRES_NEW_BACKUP_AUDIT'
    files={str(ROOT/f['path']):sha(ROOT/f['path']) if (ROOT/f['path']).exists() else None for f in manifest['files']}
    for directory in (ROOT/'frontend/src',ROOT/'backend/pde',ROOT/'backend/masterdata',ROOT/'backend/system'):
        for p in directory.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts: files.setdefault(str(p),sha(p))
    save('CODE_BASELINE.json',files);save('PREFLIGHT.json',snap);save('PLAN_AUDIT.json',plan)
    save('INPUTS.json',{'instruction':str(INSTRUCTION),'instructionSHA':sha(INSTRUCTION),'packageManifestSHA':sha(PACKAGE/'MANIFEST.json')})
    print(json.dumps({'preflightSHA':snap['sha256'],'dbSize':snap['size'],'integrity':snap['integrity'],'fk':snap['foreignKeys'],
        'tables':len(snap['tables']),'plan':plan},ensure_ascii=False,indent=2))
def backup():
    assert not (OUT/'BACKUP.json').exists()
    pre=read('PREFLIGHT.json');assert sha(DB)==pre['sha256']
    target=ROOT/'backups'/('PRE-SEMI-FINISHED-SCHEMA-MIGRATION-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))/'db.sqlite3'
    assert target.resolve().is_relative_to((ROOT/'backups').resolve()) and not target.exists()
    target.parent.mkdir(parents=True);shutil.copy2(DB,target)
    assert sha(target)==sha(DB)==pre['sha256']
    back=snapshot(target)
    assert back['tables']==pre['tables'] and back['recorder']==pre['recorder']
    code=[]
    for f in package_check()['files']:
        p=ROOT/f['path']; dest=target.parent/'code'/f['path']
        if p.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        code.append({'path':str(p),'backup':str(dest) if p.exists() else None,'sha256':sha(p) if p.exists() else None})
    save('BACKUP.json',{'source':str(DB),'backup':str(target),'sourceSHA':sha(DB),'backupSHA':sha(target),
        'size':target.stat().st_size,'timestamp':now(),'readVerified':True,'integrity':back['integrity'],'foreignKeys':back['foreignKeys'],'code':code})
    plan=read('PLAN_AUDIT.json');plan.update({'frozenAt':now(),'backupSha':sha(target),'instructionSHA':sha(INSTRUCTION)})
    save('FROZEN_MIGRATION_PLAN.json',plan)
    print(json.dumps({'backup':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'frozenPlanSHA':sha(OUT/'FROZEN_MIGRATION_PLAN.json')},indent=2))

def business_compare(path, before):
    after=snapshot(path);checked=[]
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        for t,old in before['tables'].items():
            if t in ('sqlite_sequence','django_migrations'):continue
            assert t in after['tables'] and after['tables'][t]['count']==old['count'],('BUSINESS_COUNT_DRIFT',t)
            columns=','.join('"'+n+'"' for n in old['columns'])
            data=sorted(c.execute(f'SELECT {columns} FROM "{t}"').fetchall(),key=repr)
            assert digest(data)==old['contentSha'],('BUSINESS_CONTENT_DRIFT',t)
            checked.append(t)
    new=set(after['tables'])-set(before['tables'])
    assert len(new)==5 and all(after['tables'][t]['count']==0 for t in new),('NEW_BUSINESS_DATA',new)
    return after,{'status':'PASS','originalTablesCompared':len(checked),'newEmptyTables':sorted(new),'businessFactCreate':0,'existingRowChanges':0}

def apply_exact(backend,path,production=False):
    from io import StringIO
    conn=bootstrap(backend,path,readonly=False)
    plan=discover_plan(conn);frozen=read('FROZEN_MIGRATION_PLAN.json')
    assert plan['migrations']==frozen['migrations'] and plan['targets']==frozen['targets']
    from django.core.management import call_command
    from django.db.migrations.executor import MigrationExecutor
    before=read('PREFLIGHT.json');assert sha(path)==before['sha256']
    # One connection holds an exclusive SQLite lock across the explicit DDL chain.
    conn.ensure_connection();conn.connection.execute('PRAGMA locking_mode=EXCLUSIVE')
    conn.connection.execute('BEGIN EXCLUSIVE');conn.connection.execute('COMMIT')
    statements=[]
    def audit(execute,sql,params,many,context):
        statements.append(sql)
        token=sql.lstrip().split()[0].upper()
        if token in ('UPDATE','DELETE','REPLACE'):raise RuntimeError('BUSINESS_DML_FORBIDDEN: '+sql[:100])
        if token=='INSERT':
            target=sql.split('INTO',1)[1].strip().split()[0].strip('"')
            assert target=='django_migrations' or target.startswith('new__pde_'),('INSERT_TARGET_FORBIDDEN',target)
        return execute(sql,params,many,context)
    try:
        with conn.execute_wrapper(audit):
            executor=MigrationExecutor(conn)
            executor.migrate([tuple(t) for t in frozen['targets']],plan=executor.migration_plan([tuple(t) for t in frozen['targets']]))
        recorder=list(conn.connection.execute('SELECT app,name,CAST(applied AS TEXT) FROM django_migrations ORDER BY app,name'))
        prior={(r[0],r[1]):str(r[2]) for r in before['recorder']}; current={(r[0],r[1]):str(r[2]) for r in recorder}
        assert {k:v for k,v in current.items() if k in prior}==prior,[(k,v,current.get(k)) for k,v in prior.items() if current.get(k)!=v]
        assert set(current)-set(prior)=={(r['app'],r['name']) for r in frozen['migrations']}
        # Read live schemas, indexes and constraints before system and integrity checks.
        schema=list(conn.connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
        check=StringIO();call_command('check',stdout=check,stderr=check,verbosity=1)
        assert list(conn.connection.execute('PRAGMA integrity_check'))==[('ok',)]
        assert not list(conn.connection.execute('PRAGMA foreign_key_check'))
    finally:
        conn.close()
        save('PRODUCTION_SQL.json' if production else 'REHEARSAL_SQL.json',statements)
    after,business=business_compare(path,before)
    result={'status':'PASS','production':production,'database':str(path),'recorderAdded':[list(k) for k in set(current)-set(prior)],
        'schemaReadbackCount':len(schema),'systemCheck':check.getvalue(),'business':business,
        'postMigrateSignalsExecuted':False,'permissionOrContentTypeWrites':0,'unrelatedMigrationsExecuted':0}
    save('POSTFLIGHT.json' if production else 'REHEARSAL_POSTFLIGHT.json',after)
    save('APPLY_RESULT.json' if production else 'REHEARSAL_RESULT.json',result)
    return result

def rehearse():
    WORK.mkdir(parents=True,exist_ok=True)
    b=read('BACKUP.json');target=WORK/('rehearsal-'+datetime.now(timezone.utc).strftime('%H%M%S%f')+'.sqlite3')
    assert not target.exists();shutil.copy2(b['backup'],target)
    result=apply_exact(TESTED,target)
    after=sha(target);assert after!=b['backupSHA']
    # Restore exact database bytes on this named rehearsal copy, not backwards migrations.
    assert target.resolve().parent==WORK.resolve()
    shutil.copy2(b['backup'],target)
    restored=snapshot(target)
    assert restored['sha256']==b['backupSHA'] and restored['tables']==read('PREFLIGHT.json')['tables'] and restored['recorder']==read('PREFLIGHT.json')['recorder']
    save('BACKUP_RESTORE_REHEARSAL.json',{'status':'PASS','copy':str(target),'migratedSHA':after,'restoredSHA':sha(target),'integrity':restored['integrity'],'fk':restored['foreignKeys']})
    print(json.dumps(result,ensure_ascii=False,indent=2))

def production():
    assert not (OUT/'APPLY_RESULT.json').exists(), 'ALREADY_EXECUTED_DO_NOT_REPEAT'
    assert read('BACKUP_RESTORE_REHEARSAL.json')['status']=='PASS'
    b=read('BACKUP.json');assert sha(b['backup'])==b['backupSHA']==sha(DB)
    for f in package_check()['files']:assert sha(ROOT/f['path'])==f['testedSha'],('PRODUCTION_CANDIDATE_MISMATCH',f['path'])
    save('EXECUTION_STARTED.json',{'timestamp':now(),'planSHA':sha(OUT/'FROZEN_MIGRATION_PLAN.json'),'backupSHA':sha(b['backup'])})
    try:
        result=apply_exact(ROOT/'backend',DB,production=True)
        expected=read('REHEARSAL_POSTFLIGHT.json')['tables'];actual=read('POSTFLIGHT.json')['tables']
        assert set(expected)==set(actual)
        for t in actual:
            assert all(actual[t][k]==expected[t][k] for k in ('schema','foreignKeys','indexes','columns')),('SCHEMA_REHEARSAL_MISMATCH',t)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except BaseException as error:
        from django.db import connections
        connections.close_all()
        # User explicitly authorized exact backup restoration if any apply/readback step fails.
        assert DB.resolve()==(ROOT/'backend/db.sqlite3').resolve() and sha(b['backup'])==b['backupSHA']
        shutil.copy2(DB,WORK/'failed-production.sqlite3')
        shutil.copy2(b['backup'],DB)
        restored=snapshot(DB);pre=read('PREFLIGHT.json')
        assert restored['sha256']==pre['sha256'] and restored['tables']==pre['tables'] and restored['recorder']==pre['recorder']
        save('PRODUCTION_RESTORED_AFTER_FAILURE.json',{'error':repr(error),'restoredSHA':sha(DB),'integrity':restored['integrity'],'fk':restored['foreignKeys'],'codeRestoreRequired':True})
        raise

def recover():
    b=read('BACKUP.json');pre=read('PREFLIGHT.json')
    assert DB.resolve()==(ROOT/'backend/db.sqlite3').resolve()
    assert sha(DB)==read('POSTFLIGHT.json')['sha256'], 'CONCURRENT_DRIFT_STOP_RECOVERY'
    assert sha(b['backup'])==b['backupSHA']==pre['sha256']
    preserved=WORK/'post-migration-before-api-failure-restore.sqlite3'
    assert not preserved.exists();shutil.copy2(DB,preserved)
    shutil.copy2(b['backup'],DB)
    after=snapshot(DB)
    assert after['sha256']==pre['sha256'] and after['tables']==pre['tables'] and after['recorder']==pre['recorder']
    save('PRODUCTION_BACKUP_RECOVERY.json',{'status':'PASS','reason':'post-migration read-only API returned 503; user mandates stop and backup restore',
        'preservedMigratedCopy':str(preserved),'restoredSHA':sha(DB),'recorderRestored':True,'schemaRestored':True,'businessTablesRestored':True,
        'integrity':after['integrity'],'foreignKeys':after['foreignKeys'],'productionSchemaReady':False,'productionBusinessFactCreate':0})
    print('BACKUP RESTORE PASS; production SHA '+sha(DB))

if __name__=='__main__': {'preflight':preflight,'backup':backup,'rehearse':rehearse,'production':production,'recover':recover}[sys.argv[1]]()
