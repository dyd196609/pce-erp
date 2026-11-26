"""One scoped reload, retaining the already verified non-production runtime identity."""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
import organizationImportRuntimeRecovery as evidence

ROOT=Path(__file__).resolve().parents[1]
evidence.OUT=ROOT/'docs/evidence/pce-organization-import-reference-20260914'
EXPECTED_PID=107744

def idle():
    lines=[line for line in subprocess.check_output(['netstat','-ano'],text=True).splitlines() if '127.0.0.1:8000' in line]
    if not any('LISTENING' in line and line.split()[-1]==str(EXPECTED_PID) for line in lines):
        raise RuntimeError('Runtime identity changed; no stop performed')
    if any('ESTABLISHED' in line for line in lines):
        raise RuntimeError('Active HTTP connection; no stop performed')
    return lines

def reload_once():
    raw=subprocess.check_output([str(evidence.PYTHON),str(ROOT/'scripts/inspectOrganizationImportRuntime.py'),str(EXPECTED_PID)],text=True,encoding='utf-8')
    identity=json.loads(raw)[0]
    actual=identity['allowlistedEnvironment']
    if Path(identity['cwd']).resolve()!=(ROOT/'backend').resolve(): raise RuntimeError('Working directory differs')
    for key,value in evidence.ENV.items():
        equal=Path(actual.get(key,'')).resolve()==Path(value).resolve() if key=='PCE_DATABASE_PATH' else actual.get(key)==value
        if not equal: raise RuntimeError('Allowlisted setting differs: '+key)
    if 'runserver 127.0.0.1:8000 --noreload' not in identity['commandLine']: raise RuntimeError('Command differs')
    environment=os.environ.copy();environment.update(evidence.ENV)
    subprocess.run([str(evidence.PYTHON),'manage.py','check'],cwd=ROOT/'backend',env=environment,check=True)
    observations=[]
    for _ in range(3): observations.append(idle());time.sleep(1)
    connection=sqlite3.connect(evidence.DB,timeout=0)
    connection.execute('BEGIN EXCLUSIVE')
    try:
        observations.append(idle())
        evidence.save('REFERENCE_RELOAD_PLAN_'+str(EXPECTED_PID)+'.json',{'identity':identity,'idle':observations,'exclusiveDatabaseLock':'acquired without data changes','command':[str(evidence.PYTHON),'manage.py','runserver','127.0.0.1:8000','--noreload'],'migration':False})
        subprocess.run(['powershell.exe','-NoProfile','-Command',f'Stop-Process -Id {EXPECTED_PID} -ErrorAction Stop'],check=True)
    finally: connection.rollback();connection.close()
    with (evidence.OUT/'reference-backend.stdout.log').open('ab') as stdout,(evidence.OUT/'reference-backend.stderr.log').open('ab') as stderr:
        process=subprocess.Popen([str(evidence.PYTHON),'manage.py','runserver','127.0.0.1:8000','--noreload'],cwd=ROOT/'backend',env=environment,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    evidence.save('REFERENCE_RELOAD_STARTED_'+str(EXPECTED_PID)+'.json',{'launcherPid':process.pid,'originalPid':EXPECTED_PID,'database':str(evidence.DB),'automaticReload':False})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['reload','after','engineering']);parser.add_argument('--expected-pid',type=int,default=107744);args=parser.parse_args()
    EXPECTED_PID=args.expected_pid
    if args.mode=='reload': reload_once()
    elif args.mode=='engineering': evidence.engineering_readback()
    else: evidence.snapshot('reference_after');evidence.probe('reference_after')
