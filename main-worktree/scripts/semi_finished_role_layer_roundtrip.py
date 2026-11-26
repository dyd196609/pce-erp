"""Exact-ID round-trip and rollback only in independently named rehearsal copies."""
import hashlib
import json
import shutil
import sqlite3
import sys
from semi_finished_role_layer import ROOT, ISO, OUT, bootstrap, read, save
from semi_finished_model_closure_serialization import encoder
mode=sys.argv[1]
assert mode in {'roundtrip','rollback'}
name=f'{mode}.sqlite3'
target=(ISO/name).resolve()
assert target.parent==ISO.resolve() and not target.exists()
shutil.copy2(ISO/'isolated.sqlite3',target)
bootstrap(name)
from django.apps import apps
from django.core import serializers
from django.core.management import call_command
from django.db import connection,transaction

def hashes(path):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as con:
        con.execute('PRAGMA query_only=ON')
        tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if r[0] not in {'sqlite_sequence','django_migrations'}]
        return {t:hashlib.sha256(json.dumps(sorted(con.execute(f'SELECT * FROM "{t}"').fetchall(),key=repr),default=str).encode()).hexdigest() for t in tables}

owned=read('ISOLATED_CREATED_OBJECTS.json')
fixture=(OUT/'REAL_CASE_ROUNDTRIP_FIXTURE.json').read_text(encoding='utf-8')
before=hashes(target)
assert len(owned)==232 and len(json.loads(fixture))==232
with transaction.atomic():
    for item in reversed(owned):
        model=apps.get_model(item['model'])
        assert model._meta.db_table==item['table']
        model.objects.get(pk=item['pk'])
        with connection.cursor() as cur:
            cur.execute(f'DELETE FROM "{model._meta.db_table}" WHERE id=%s',[item['pk']])
            assert cur.rowcount==1
checks=[]
if mode=='roundtrip':
    with transaction.atomic():
        objects=list(serializers.deserialize('json',fixture,ignorenonexistent=False))
        for obj in objects:
            obj.object.full_clean();obj.save()
    assert hashes(target)==before
    roundtripped=serializers.serialize('json',[apps.get_model(i['model']).objects.get(pk=i['pk']) for i in owned],indent=2,cls=encoder())
    assert json.loads(roundtripped)==json.loads(fixture)
    checks=['232 exact-ID objects removed and restored from complete serialized fixture',
        'all table content hashes identical before/after', 'typed relationships and timestamp microseconds exact',
        '2 configurations / 71 bindings / 71 components / 59 pending edge requirements preserved']
else:
    call_command('migrate','pde','0022_manufacturing_definition_applicability',interactive=False,verbosity=1)
    new_models={'materialconfiguration','materialconfigurationattribute','materialfamilyallowedmaterial','materialconfigurationsourcebinding'}
    with sqlite3.connect((ROOT/'backend/db.sqlite3').as_uri()+'?mode=ro',uri=True) as con:
        original_content={r[0] for r in con.execute('SELECT id FROM django_content_type')}
        original_permissions={r[0] for r in con.execute('SELECT id FROM auth_permission')}
    removed=[]
    with transaction.atomic(),connection.cursor() as cur:
        cur.execute("SELECT id,model FROM django_content_type WHERE app_label='pde'")
        for content_id,model in cur.fetchall():
            if model not in new_models:continue
            assert content_id not in original_content
            cur.execute('SELECT id FROM auth_permission WHERE content_type_id=%s',[content_id]);ids=[r[0] for r in cur.fetchall()]
            assert not (set(ids)&original_permissions)
            removed.append({'model':model,'contentTypeId':content_id,'permissionIds':ids})
            cur.execute('DELETE FROM auth_permission WHERE content_type_id=%s',[content_id])
            cur.execute('DELETE FROM django_content_type WHERE id=%s',[content_id])
    save('ROLLBACK_METADATA_CLEANUP.json',removed)
    assert len(removed)==4
    assert hashes(target)==hashes(ROOT/'backend/db.sqlite3')
    checks=['232 owned isolated rows removed by exact PK in rehearsal copy only','0026 / 0025 / 0024 reversed',
        'original business table hashes all equal production baseline','only 4 candidate content types /16 default permissions removed']
with connection.cursor() as cur:cur.execute('PRAGMA foreign_key_check');assert not cur.fetchall()
checks.append('foreign keys valid')
save(mode.upper()+'_RESULTS.json',{'status':'PASS','database':str(target),'checks':checks,'productionBusinessWrite':0,
    'recoveryFixture':str(OUT/'REAL_CASE_ROUNDTRIP_FIXTURE.json'),'mainReplayRetained':True})
print(json.dumps({'mode':mode,'status':'PASS','checks':len(checks),'originalBusinessTables':len(hashes(ROOT/'backend/db.sqlite3'))}))
