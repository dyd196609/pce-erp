"""Rehearse exact-ID recovery in named copies, never production or sealed prior DB."""
import hashlib,json,shutil,sqlite3,sys
from room_door_edge import ROOT,ISO,OUT,bootstrap,read,save
from semi_finished_model_closure_serialization import encoder
mode=sys.argv[1];assert mode in {'roundtrip','rollback'}
target=(ISO/(mode+'.sqlite3')).resolve();assert target.parent==ISO.resolve() and not target.exists()
shutil.copy2(ISO/'isolated.sqlite3',target);bootstrap(target.name)
from django.apps import apps
from django.core import serializers
from django.core.management import call_command
from django.db import connection,transaction
def hashes(path):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as con:
        con.execute('PRAGMA query_only=ON')
        tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if r[0] not in {'sqlite_sequence','django_migrations'}]
        return {t:hashlib.sha256(json.dumps(sorted(con.execute(f'SELECT * FROM "{t}"').fetchall(),key=repr),default=str).encode()).hexdigest() for t in tables}
fixture=read('TARGET_REQUIREMENT_FIXTURE.json');before=hashes(target)
if mode=='roundtrip':
    with transaction.atomic(),connection.cursor() as cur:
        for item in reversed(fixture):
            model=apps.get_model(item['model']);assert model._meta.model_name in {'materiallosspolicy','componentmaterialrequirement'}
            cur.execute(f'DELETE FROM "{model._meta.db_table}" WHERE id=%s',[item['pk']]);assert cur.rowcount==1
        for obj in serializers.deserialize('json',json.dumps(fixture),ignorenonexistent=False):obj.object.full_clean();obj.save()
    assert hashes(target)==before
    actual=json.loads(serializers.serialize('json',[apps.get_model(r['model']).objects.get(pk=r['pk']) for r in fixture],cls=encoder()))
    assert actual==fixture
    checks=['78 exact-ID objects round-tripped','all table contents identical','original 71 component owners unchanged']
else:
    ids=[r['requirementId'] for r in read('ISOLATED_REPLAY.json')['roomDoorRequirements']]
    with transaction.atomic(),connection.cursor() as cur:
        for pk in ids:
            cur.execute("DELETE FROM pde_component_material_requirement WHERE id=%s AND requirement_source_mode='DIRECT_CALCULATED'",[pk]);assert cur.rowcount==1
    call_command('migrate','pde','0026_material_role_layer_correction',interactive=False,verbosity=1)
    # Only metadata created for the new isolated model may be removed in this rehearsal.
    with transaction.atomic(),connection.cursor() as cur:
        cur.execute("SELECT id FROM django_content_type WHERE app_label='pde' AND model='materiallosspolicy'")
        ids=[r[0] for r in cur.fetchall()];assert len(ids)==1
        cur.execute('DELETE FROM auth_permission WHERE content_type_id=%s',[ids[0]])
        cur.execute('DELETE FROM django_content_type WHERE id=%s',[ids[0]])
    previous=ROOT/'.runtime/semi-finished-role-layer-20260909/isolated.sqlite3'
    assert hashes(target)==hashes(previous)
    checks=['only 16 new room-door requirements removed from rollback copy','0027 reversed','all prior-isolated table contents exactly restored']
with connection.cursor() as cur:cur.execute('PRAGMA foreign_key_check');assert not cur.fetchall()
save(mode.upper()+'_RESULTS.json',{'status':'PASS','database':str(target),'checks':checks,'productionBusinessWrite':0,'mainReplayPreserved':True})
print(mode,'PASS')
