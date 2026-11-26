"""Production requests use read-only SQLite and reject every non-read SQL statement."""
import json, sys
from unittest.mock import patch
from semi_finished_schema_production import ROOT, DB, OUT, sha, save, bootstrap
from copy import deepcopy
expected_ready=sys.argv[1]=='after'
before=sha(DB);connection=bootstrap(ROOT/'backend',DB)
from system.models import User
from pde.views import EngineeringCalculationReadinessView
from pde.engineering_calculation_service import EngineeringCalculationError
from pde.semi_finished_schema_status import apply_status
from rest_framework.test import APIRequestFactory,force_authenticate
actor=User.objects.filter(is_superuser=True,company_id=1,is_active=True).defer('password').first();assert actor
factory=APIRequestFactory();view=EngineeringCalculationReadinessView.as_view();queries=[]
def guard(execute,sql,params,many,context):
    token=sql.lstrip().split()[0].upper();assert token in ('SELECT','PRAGMA','EXPLAIN'),sql[:60]
    queries.append(token);return execute(sql,params,many,context)
def request(mode='semi-finished-structure',user=actor,method='get'):
    r=getattr(factory,method)('/api/pde/a1-engineering/calculations/readiness/',{'subview':mode})
    if user:force_authenticate(r,user)
    return view(r)
checks=[]
with connection.execute_wrapper(guard):
    r=request();assert r.status_code==200,r.data
    p=r.data['semiFinishedConfiguration'];assert p['schemaCapability']['ready']==expected_ready
    assert p['summary']['productionMigrationApplied']==expected_ready
    assert p['summary']['roomDoorManualRevalidation']=='USER_VALIDATED_FROZEN'
    old=json.loads((ROOT/'docs/evidence/room_door_edge_20260909/API_READONLY_EVIDENCE.json').read_text(encoding='utf-8'))['semiFinishedConfiguration']
    expected=apply_status(deepcopy(old),p['schemaCapability']);assert p==expected,'NON_STATUS_PROJECTION_DRIFT'
    assert p['roleLayerSummary']['board']==old['roleLayerSummary']['board']
    assert all(r.data[k]==r.data['strictFacts'] for k in ('apiFacts','pageFacts','diagnosticFacts'))
    checks+=['full frozen projection unchanged except audited deployment/manual-status adapter','same server facts across API/page/diagnostic/strict','live schema state correct; no business formalization']
    assert request(user=None).status_code in (401,403);checks.append('anonymous denied')
    with patch('pde.engineering_calculation_service.EngineeringCalculationService._authorize',side_effect=EngineeringCalculationError('PERMISSION_DENIED','denied')):
        denied=request();assert denied.status_code==403 and denied.data['resultCount'] is None
    checks.append('unauthorized denied')
    for code in ('PARTIAL_PRODUCTION_SCHEMA_RECHECK_REQUIRED','PRODUCTION_BUSINESS_FORMALIZATION_REBIND_REQUIRED'):
        with patch('pde.semi_finished_schema_status.read_capability',side_effect=ValueError(code)):
            failed=request();assert failed.status_code==503 and failed.data['factLoadStatus']=='read_failed' and failed.data['resultCount'] is None
        checks.append(code+' fails closed')
    with patch('pde.room_door_edge_preview.EVIDENCE_SHA','wrong'):
        failed=request();assert failed.status_code==503 and failed.data['factLoadStatus']=='read_failed'
    checks.append('frozen evidence drift fails closed')
    assert request(mode='wrong').status_code==400;checks.append('bad subview denied')
    assert request(method='post').status_code==405;checks.append('POST denied')
    previous=request(mode='');assert previous.status_code==200 and len(previous.data['formalRules'])==4 and previous.data['materialRuleDefinition']['sourceRowCount']==71
    checks.append('four formal rules and 71 source rows unchanged')
connection.close();assert sha(DB)==before
save('API_AFTER.json' if expected_ready else 'API_BEFORE.json',r.data)
save('API_AFTER_CHECKS.json' if expected_ready else 'API_BEFORE_CHECKS.json',{'status':'PASS','checks':checks,'sqlStatements':len(queries),'productionBusinessWrite':0,'databaseSHA':before,'readOnly':True})
print(json.dumps({'status':'PASS','checks':len(checks),'schemaReady':expected_ready,'productionBusinessWrite':0}))
