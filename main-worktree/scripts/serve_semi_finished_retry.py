"""Local HTTP validation harness; same application, protected DB, no business fork."""
import os, sys
from semi_finished_schema_retry import ROOT, ISO, OUT, DB, sha, save
from semi_finished_schema_production import bootstrap

stage=sys.argv[1]
port=int(sys.argv[2]) if len(sys.argv)>2 else 8000
backend=ISO/'backend' if stage=='rehearsal' else ROOT/'backend'
path=ISO/'rehearsal.sqlite3' if stage=='rehearsal' else DB
conn=bootstrap(backend,path)
from django.conf import settings
from django.db.backends.signals import connection_created

def protect(sender,connection,**kwargs):
    connection.connection.execute('PRAGMA query_only=ON')

connection_created.connect(protect,weak=False)
os.environ['PCE_RETRY_STAGE']=stage
os.environ['PCE_RETRY_HTTP_LOG']=str(OUT/(stage.upper()+'_HTTP.jsonl'))
settings.MIDDLEWARE=['semi_finished_readonly_guard.ReadOnlyEvidenceMiddleware',*settings.MIDDLEWARE]
conn.close()
save(stage.upper()+'_HTTP_RUNTIME.json',{'stage':stage,'backend':str(backend),'database':str(path),
    'databaseSHA':sha(path),'python':sys.executable,'pythonVersion':sys.version,
    'guardSHA':sha(ROOT/'scripts/semi_finished_readonly_guard.py'),
    'endpoint':'http://127.0.0.1:'+str(port),'mode':'same application; SQLite mode=ro; per-request SQL guard'})
from django.core.management import call_command
call_command('runserver','127.0.0.1:'+str(port),use_reloader=False,verbosity=1)
