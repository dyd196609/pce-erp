"""Append-only targeted evidence; all ORM writes guarded to a fresh isolated DB."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/evidence/room_door_edge_20260909'
OLD=ROOT/'docs/evidence/semi_finished_role_layer_20260909'
ISO=ROOT/'.runtime/room-door-edge-20260909'
BACKEND=ISO/'backend'
PACKAGE=ROOT/'tools/semi-finished-model-closure/20260909-room-door'
PREVIOUS=ROOT/'tools/semi-finished-model-closure/20260909-role-layer'
INSTRUCTION=Path('C:/Users/DAODA/.codex/attachments/850a4d95-d82a-4270-acbb-e94110e403c5/pasted-text.txt')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
def read(n,folder=OUT): return json.loads((folder/n).read_text(encoding='utf-8-sig'))
def save(n,v):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
def bootstrap(database='isolated.sqlite3'):
    target=(ISO/database).resolve()
    assert target.parent==ISO.resolve() and target.suffix=='.sqlite3'
    sys.path.insert(0,str(ROOT/'backend/venv/Lib/site-packages'))
    sys.path.insert(0,str(BACKEND))
    import os
    os.environ['DJANGO_SETTINGS_MODULE']='pce_backend.settings'
    from django.conf import settings
    settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':str(target)}}
    settings.PCE_CONFIGURATION_ISOLATED_REPLAY=True
    import django
    django.setup()
    from django.db import connection
    assert Path(connection.settings_dict['NAME']).resolve()==target
    return target
def baseline():
    assert not (OUT/'BASELINE.json').exists()
    from engineering_material_configuration_audit import snapshot
    files={Path(p) for p in read('BASELINE.json',OLD)['files']}
    for folder in (OLD,PREVIOUS): files.update(p for p in folder.rglob('*') if p.is_file())
    files.add(ROOT/'docs/evidence/SEMI_FINISHED_ROLE_LAYER_FINAL_CONSOLIDATED_20260909.md')
    save('BASELINE.json',{'capturedAt':datetime.now(timezone.utc).isoformat(),'files':{str(p):sha(p) for p in sorted(files)},'instructionSha':sha(INSTRUCTION)})
    save('FORMAL_BEFORE.json',snapshot())
    print('Frozen files:',len(files),'Production SHA:',sha(ROOT/'backend/db.sqlite3'))
def prepare():
    assert not ISO.exists()
    shutil.copytree(ROOT/'.runtime/semi-finished-role-layer-20260909/backend',BACKEND,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT/'.runtime/semi-finished-role-layer-20260909/isolated.sqlite3',ISO/'isolated.sqlite3')
    print('New isolated backend/database copied; previous copy unchanged')
if __name__=='__main__':
    {'baseline':baseline,'prepare':prepare}[sys.argv[1]]()
