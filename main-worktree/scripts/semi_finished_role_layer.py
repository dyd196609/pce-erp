"""Role-layer correction orchestration. Only guarded isolated SQLite may be written."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/evidence/semi_finished_role_layer_20260909'
ISO = ROOT / '.runtime/semi-finished-role-layer-20260909'
BACKEND = ISO / 'backend'
OLD = ROOT / 'docs/evidence/semi_finished_model_closure_20260909'
PACKAGE = ROOT / 'tools/semi-finished-model-closure/20260909/candidate/backend'
INSTRUCTION = Path('C:/Users/DAODA/.codex/attachments/65975ebd-f447-473f-aaed-27c4d48053b4/pasted-text.txt')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()

def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')

def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))

def bootstrap(database='isolated.sqlite3'):
    target = (ISO/database).resolve()
    assert target.parent == ISO.resolve() and target.suffix == '.sqlite3', 'ISOLATION_PATH_GUARD'
    assert target != (ROOT/'backend/db.sqlite3').resolve()
    sys.path.insert(0, str(ROOT/'backend/venv/Lib/site-packages'))
    sys.path.insert(0, str(BACKEND))
    import os
    os.environ['DJANGO_SETTINGS_MODULE'] = 'pce_backend.settings'
    from django.conf import settings
    settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(target)}}
    settings.PCE_CONFIGURATION_ISOLATED_REPLAY = True
    import django
    django.setup()
    from django.db import connection
    assert Path(connection.settings_dict['NAME']).resolve() == target
    return target

def baseline():
    assert not (OUT/'BASELINE.json').exists(), 'Refuse to replace baseline'
    from engineering_material_configuration_audit import snapshot
    previous = json.loads((OLD/'BASELINE.json').read_text(encoding='utf-8'))
    files = {Path(p) for p in previous['files']}
    for directory in (OLD, ROOT/'tools/semi-finished-model-closure/20260909'):
        files.update(p for p in directory.rglob('*') if p.is_file())
    files.update(ROOT/p for p in ('backend/pde/semi_finished_configuration_validation.py',
        'docs/evidence/SEMI_FINISHED_MODEL_CLOSURE_FINAL_CONSOLIDATED_20260909.md',
        'docs/governance/MANUFACTURING_DEFINITION_APPLICABILITY_CONTRACT_V1.0.md'))
    save('BASELINE.json', {'capturedAt': datetime.now(timezone.utc).isoformat(),
        'files': {str(p): sha(p) for p in sorted(files)}, 'instructionPath': str(INSTRUCTION), 'instructionSha': sha(INSTRUCTION)})
    save('FORMAL_BEFORE.json', snapshot())
    print(json.dumps({'baselineFiles': len(files), 'productionSha': sha(ROOT/'backend/db.sqlite3'), 'instructionSha': sha(INSTRUCTION)}))

def prepare():
    assert not BACKEND.exists(), 'Refuse to overwrite isolated candidate'
    files = []
    for source in (ROOT/'backend').rglob('*'):
        rel = source.relative_to(ROOT/'backend')
        if set(rel.parts) & {'venv','.venv','__pycache__','backups','logs','media','node_modules','.git'}:
            continue
        if not source.is_file() or source.suffix not in {'.py','.json'} or any(p.startswith('.') for p in rel.parts):
            continue
        target = BACKEND/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append(str(rel))
    for source in PACKAGE.rglob('*'):
        if source.is_file():
            target = BACKEND/source.relative_to(PACKAGE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source,target)
    (BACKEND/'static').mkdir(exist_ok=True)
    shutil.copy2(ROOT/'backend/db.sqlite3',ISO/'isolated.sqlite3')
    save('ISOLATED_ENVIRONMENT.json', {'backend': str(BACKEND), 'database': str(ISO/'isolated.sqlite3'),
        'copiedFiles': files, 'productionApplied': False, 'previousPackage': str(PACKAGE)})
    print('Isolated canonical backend and production-copy DB prepared; no production write')

def migrate_initial():
    bootstrap()
    from django.core.management import call_command
    call_command('migrate','pde','0025_material_configuration_applicability_quantity',interactive=False,verbosity=1)
    call_command('check',verbosity=1)

def migrate_correction():
    bootstrap()
    from django.apps import apps
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
    from django.db.migrations.state import ProjectState
    from django.db.migrations.writer import MigrationWriter
    from django.db.migrations.loader import MigrationLoader
    allowed={'materialconfigurationsourcebinding','templatematerialrequirementslot','engineeringbreakdownitem','componentmaterialrequirement'}
    baseline=MigrationLoader(connection).project_state([('pde','0025_material_configuration_applicability_quantity')])
    after=ProjectState.from_apps(apps)
    before=after.clone()
    for name in allowed:
        before.models[('pde',name)]=baseline.models[('pde',name)].clone()
    changes=MigrationAutodetector(before,after,NonInteractiveMigrationQuestioner())._detect_changes()
    assert set(changes)=={'pde'} and len(changes['pde'])==1
    migration=changes['pde'][0]
    migration.name='0026_material_role_layer_correction'
    migration.dependencies=[('pde','0025_material_configuration_applicability_quantity')]
    descriptions=[]
    for op in migration.operations:
        assert (getattr(op,'model_name',None) or getattr(op,'name','')).lower() in allowed
        descriptions.append(op.describe())
    writer=MigrationWriter(migration)
    target=BACKEND/'pde/migrations'/writer.filename
    assert not target.exists(), 'Refuse to replace migration'
    target.write_text(writer.as_string(),encoding='utf-8')
    call_command('migrate','pde',migration.name,interactive=False,verbosity=1)
    call_command('check',verbosity=1)
    with connection.cursor() as cur:
        cur.execute('PRAGMA foreign_key_check')
        assert not cur.fetchall()
    save('ISOLATED_MIGRATION.json',{'status':'PASS','database':str(ISO/'isolated.sqlite3'),
        'migration':migration.name,'operations':descriptions,'operationCount':len(descriptions),
        'productionMigration':0,'legacyColumnsPreserved':True,
        'strategy':'0024/0025 original package retained; new isolated-only correction 0026. Legacy component owners and computed origins unchanged. New source rows have separate unique origin. Old populated quantity_mode becomes UNKNOWN, not guessed.'})
    print('Isolated role correction migration PASS: '+str(len(descriptions))+' operations')

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action', choices=('baseline','prepare','migrate-initial','migrate-correction'))
    args=parser.parse_args()
    {'baseline':baseline,'prepare':prepare,'migrate-initial':migrate_initial,'migrate-correction':migrate_correction}[args.action]()
