"""Read-only failure localization on the preserved migrated copy after recovery."""
from semi_finished_schema_production import ROOT,WORK,OUT,bootstrap,save,sha
target=WORK/'post-migration-before-api-failure-restore.sqlite3'
before=sha(target);conn=bootstrap(ROOT/'backend',target)
from system.models import User
from pde.semi_finished_configuration_preview import build_for_user
actor=User.objects.filter(is_superuser=True,company_id=1,is_active=True).defer('password').first()
events=[]
def guard(execute,sql,params,many,context):
    token=sql.lstrip().split()[0].upper()
    if token not in ('SELECT','PRAGMA','EXPLAIN'):
        events.append({'firstToken':token,'statement':sql});raise AssertionError('READ_GUARD_REJECTED_'+token)
    return execute(sql,params,many,context)
try:
    with conn.execute_wrapper(guard):build_for_user(actor)
except Exception as e:
    events.append({'error':repr(e)})
conn.close();assert sha(target)==before
save('API_FAILURE_DIAGNOSTIC.json',{'database':'preserved migrated copy ONLY','readOnly':True,'events':events,
    'productionRestored':True,'unrestrictedReadOnlyDirectProjectionHadSucceeded':True})
print(events)
