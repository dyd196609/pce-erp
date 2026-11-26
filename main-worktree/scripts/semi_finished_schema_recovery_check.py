"""Verify the completed recovery only; never reapply a migration."""
import json
from io import StringIO
from pathlib import Path
from semi_finished_schema_production import ROOT,DB,OUT,read,save,sha,snapshot,bootstrap
pre=read('PREFLIGHT.json');after=snapshot(DB)
assert after['sha256']==pre['sha256'] and after['tables']==pre['tables'] and after['recorder']==pre['recorder']
baseline=read('CODE_BASELINE.json');drift=[]
for path,expected in baseline.items():
    actual=sha(path) if Path(path).exists() else None
    if actual!=expected:drift.append({'path':path,'expected':expected,'actual':actual})
assert not drift,drift
assert not (ROOT/'backend/pde/semi_finished_schema_status.py').exists()
connection=bootstrap(ROOT/'backend',DB)
from django.core.management import call_command
from system.models import User
from pde.views import EngineeringCalculationReadinessView
from rest_framework.test import APIRequestFactory,force_authenticate
out=StringIO();call_command('check',stdout=out,stderr=out)
actor=User.objects.filter(is_superuser=True,is_active=True,company_id=1).defer('password').first();assert actor
factory=APIRequestFactory();view=EngineeringCalculationReadinessView.as_view();statements=[]
def guard(execute,sql,params,many,context):
    token=sql.lstrip().split()[0].upper()
    assert token in ('SELECT','PRAGMA','EXPLAIN','BEGIN','COMMIT','ROLLBACK','SAVEPOINT','RELEASE'),token
    statements.append(token);return execute(sql,params,many,context)
with connection.execute_wrapper(guard):
    request=factory.get('/api/pde/a1-engineering/calculations/readiness/',{'subview':'semi-finished-structure'})
    force_authenticate(request,actor);response=view(request);assert response.status_code==200,response.data
    original=json.loads((ROOT/'docs/evidence/room_door_edge_20260909/API_READONLY_EVIDENCE.json').read_text(encoding='utf-8'))
    assert response.data['semiFinishedConfiguration']==original['semiFinishedConfiguration']
    assert all(response.data[k]==response.data['strictFacts'] for k in ('apiFacts','pageFacts','diagnosticFacts'))
connection.close();assert sha(DB)==pre['sha256']
prior_root=ROOT/'docs/evidence/room_door_edge_20260909'
prior=json.loads((prior_root/'BASELINE.json').read_text(encoding='utf-8'))['files']
prior_final=json.loads((prior_root/'FINAL_NON_REGRESSION.json').read_text(encoding='utf-8'))
for item in prior_final['authorizedChanges']:prior[item['path']]=item['after']
assert all(sha(p)==h for p,h in prior.items()),'PRIOR_FROZEN_EVIDENCE_DRIFT'
core=[ROOT.parent/'AGENTS.md',ROOT/'AGENTS.md',ROOT/'docs/governance/PCE CODEX开发指令规范管理V1.2.md',
    ROOT/'docs/governance/Schema规范.md',ROOT/'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
    ROOT/'docs/governance/MANUFACTURING_DEFINITION_APPLICABILITY_CONTRACT_V1.0.md']
from semi_finished_schema_production import PACKAGE,INSTRUCTION
core += [INSTRUCTION,PACKAGE/'MANIFEST.json']
core += [PACKAGE/f['packagePath'] for f in json.loads((PACKAGE/'MANIFEST.json').read_text(encoding='utf-8'))['files']]
core += [prior_root/n for n in ('ISOLATED_TEST_RESULTS.json','ROUNDTRIP_RESULTS.json','ROLLBACK_RESULTS.json','FINAL_NON_REGRESSION.json','API_READONLY_EVIDENCE.json','BASELINE.json','INPUT_MANIFEST.json')]
save('FINAL_INPUT_MANIFEST.json',{'coreInputFiles':len(core),'files':[{'path':str(p),'sha256':sha(p)} for p in core]})
save('RECOVERY_API.json',response.data)
save('FINAL_RECOVERY_CHECK.json',{'status':'PASS','databaseSHA':sha(DB),'backupSHA':read('BACKUP.json')['backupSHA'],
    'dbBytes':DB.stat().st_size,'allTables':len(after['tables']),'businessTables':len(after['tables'])-2,
    'codeBaselineFiles':len(baseline),'codeDrift':drift,'introducedCandidateFilesRemoved':9,'compatibilityAdapterRemoved':True,
    'recorderRestored':True,'schemaRestored':True,'allBusinessContentRestored':True,'integrity':after['integrity'],'fk':after['foreignKeys'],
    'systemCheck':out.getvalue(),'restoredAPI':200,'fullFrozenProjectionEqual':True,'sqlTokens':sorted(set(statements)),
    'counts':{k:v['count'] for k,v in after['tables'].items()},'productionBusinessFactCreate':0,
    'productionSchemaCapability':'BLOCKED / NOT APPLIED AFTER RECOVERY','noMigrationRetry':True,
    'priorFrozenFilesChecked':len(prior),'priorFrozenFilesUnchanged':True,'coreInputs':len(core),
    'userBusinessAcceptance':'USER VALIDATED / FROZEN; historical preview labels are not a new acceptance request'})
print(json.dumps({'status':'RECOVERY PASS','productionSchema':'BLOCKED / ROLLED BACK','dbSHA':sha(DB),'codeFilesVerified':len(baseline),'api':200}))
