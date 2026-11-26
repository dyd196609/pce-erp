"""Scoped readback and idle-only recovery of the already identified B runtime."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import urllib.request
import urllib.error
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
DB = Path('D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3')
OUT = ROOT / 'docs/evidence/pce-dual-entry-template-runtime-20260915'
PYTHON = ROOT / 'backend/venv/Scripts/python.exe'
ENV = {'DJANGO_SETTINGS_MODULE':'pce_backend.settings', 'PCE_DATABASE_PATH':str(DB),
       'PCE_DATABASE_IDENTITY':'PDE-OPERABLE-ACCEPTANCE-20260912', 'PCE_NON_PRODUCTION_ACCEPTANCE':'1'}

def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(value, ensure_ascii=False, default=str), flush=True)

def snapshot(label):
    con = sqlite3.connect(DB.as_uri()+'?mode=ro', uri=True)
    con.execute('PRAGMA query_only=ON')
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    names = ['system_company','system_department','system_position','employee','pde_engineering_source_record',
             'system_organization_operating_audits','pde_engineering_calculation_record','pde_engineering_calculation_detail']
    counts = {t: con.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in names if t in tables}
    sources = con.execute('SELECT id,company_id,source_version,content_hash,source_payload FROM pde_engineering_source_record WHERE id IN (7,8)').fetchall()
    source_rows = [{'id':r[0],'company':r[1],'version':r[2],'hash':r[3], 'payloadHash':hashlib.sha256(r[4].encode()).hexdigest(), 'payloadKeys':list(json.loads(r[4]))} for r in sources]
    companies = con.execute('SELECT id,code,name FROM system_company').fetchall()
    employees = con.execute('SELECT e.employee_no,e.full_name,d.company_id,e.status FROM employee e LEFT JOIN system_department d ON e.department_ref_id=d.id WHERE e.full_name IN (?,?,?)',('冯美','吕锋中','张宏达')).fetchall()
    groups = {}
    for t in ('system_department','system_position'):
        groups[t] = con.execute('SELECT company_id,is_active,count(*) FROM '+t+' GROUP BY company_id,is_active').fetchall()
    groups['employee'] = con.execute('SELECT d.company_id,e.status,count(*) FROM employee e LEFT JOIN system_department d ON e.department_ref_id=d.id GROUP BY d.company_id,e.status').fetchall()
    con.close()
    save('DATABASE_'+label+'.json', {'time':datetime.now().astimezone().isoformat(),'database':str(DB),'sha256':hashlib.file_digest(DB.open('rb'),'sha256').hexdigest(),'counts':counts,'sources':source_rows,'companies':companies,'confirmedEmployees':employees,'companyCounts':groups})

def probe(label):
    rows=[]
    for base in ('http://localhost:5173','http://127.0.0.1:5176','http://127.0.0.1:8000'):
        for entity in ('departments','positions','employees'):
            for action in ('template','preview','commit'):
                url=base+'/api/access-control/organization-import/'+entity+'/'+action+'/'
                request=urllib.request.Request(url,method='GET' if action=='template' else 'POST')
                try: response=urllib.request.urlopen(request,timeout=10)
                except urllib.error.HTTPError as error: response=error
                body=response.read().decode('utf-8')
                try:
                    parsed=json.loads(body)
                    detail={k:parsed[k] for k in ('errorCode','detail','errorMessage') if k in parsed}
                except json.JSONDecodeError:
                    detail={'nonJson':True,'length':len(body),'sha256':hashlib.sha256(body.encode()).hexdigest()}
                rows.append({'url':url,'status':response.status,'type':response.headers.get('Content-Type'),'body':detail})
    save('HTTP_'+label+'.json', rows)

def idle():
    output=subprocess.check_output(['netstat','-ano'],text=True)
    lines=[s for s in output.splitlines() if '127.0.0.1:8000' in s]
    if not any('LISTENING' in s and s.split()[-1]=='59996' for s in lines):
        raise RuntimeError('Original listener identity changed; refusing stop')
    if any('ESTABLISHED' in s for s in lines):
        raise RuntimeError('Active HTTP connection; refusing stop')
    return lines

def reload_runtime():
    if not PYTHON.is_file() or not (ROOT/'backend/manage.py').is_file():
        raise RuntimeError('Startup dependency missing')
    observations=[]
    for _ in range(3):
        observations.append(idle()); time.sleep(1)
    con=sqlite3.connect(DB,timeout=0)
    con.execute('BEGIN EXCLUSIVE')
    try:
        observations.append(idle())
        save('RECOVERY_PLAN.json', {'originalPid':59996,'command':[str(PYTHON),'manage.py','runserver','127.0.0.1:8000','--noreload'],'cwd':str(ROOT/'backend'),'environment':ENV,'idleObservations':observations,'databaseExclusiveLock':'acquired; no active database transaction','migration':False})
        subprocess.run(['powershell.exe','-NoProfile','-Command','Stop-Process -Id 59996 -ErrorAction Stop'],check=True)
    finally:
        con.rollback(); con.close()
    runtime_env=os.environ.copy(); runtime_env.update(ENV)
    with (OUT/'backend.stdout.log').open('ab') as stdout, (OUT/'backend.stderr.log').open('ab') as stderr:
        proc=subprocess.Popen([str(PYTHON),'manage.py','runserver','127.0.0.1:8000','--noreload'],cwd=ROOT/'backend',env=runtime_env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    save('RECOVERY_STARTED.json', {'launcherPid':proc.pid,'time':datetime.now().astimezone().isoformat(),'database':str(DB),'automaticReload':False})

def engineering_readback():
    os.environ.update(ENV)
    sys.path.insert(0,str(ROOT/'backend'))
    import django
    django.setup()
    from django.db import connection
    from django.db.models import Count
    from pde.models import EngineeringSourceRecord, EngineeringBreakdownOption
    from pde.calculation_batch_reuse import _draft_snapshot
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA query_only=ON')
        cursor.execute('PRAGMA database_list')
        actual=cursor.fetchall()
    row=EngineeringSourceRecord.objects.get(pk=8)
    data=_draft_snapshot(row)
    calculation=data['sourceCalculation']
    result={'actualConnection':actual,'sourceId':row.pk,'revision':row.source_version,'rowCount':len(data['rows']),
            'sourceCount':calculation.get('sourceCount'),'resultCount':len(calculation['rows']),
            'counts':calculation.get('counts'),'segments':calculation.get('segments'),
            'readStatusLabel':calculation.get('readStatusLabel'),
            'formalResultsCreated':calculation.get('formalResultsCreated'),
            'businessWriteSideEffectCount':calculation.get('businessWriteSideEffectCount'),
            'businessOrderReference':data['businessOrderReference'],'confirmedResponsibilityFacts':data['confirmedResponsibilityFacts'],
            'calculationRequired':data['calculationRequired'],'calculationImpact':data['calculationImpact'],
            'optionCounts':list(EngineeringBreakdownOption.objects.values('company_id','option_type','is_active').annotate(count=Count('id'))),
            'drawingRows':[r for r in data['rows'] if '图7' in json.dumps(r,ensure_ascii=False)]}
    save('ENGINEERING_READBACK.json',result)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=['before','after','reload','engineering']); args=parser.parse_args()
    if args.mode=='reload': reload_runtime()
    elif args.mode=='engineering': engineering_readback()
    else: snapshot(args.mode); probe(args.mode)
