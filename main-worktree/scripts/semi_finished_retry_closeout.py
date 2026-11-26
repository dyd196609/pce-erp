"""Read-only closeout of blocked rehearsal; production retry is NOT authorized by partial gates."""
import json, sys
from pathlib import Path
from io import StringIO
from semi_finished_schema_retry import ROOT, ISO, OUT, OLD, DB, sha, save, load, manifest, snapshot
from semi_finished_schema_production import bootstrap, business_compare

stage=sys.argv[1]
if stage=='schema':
    connection=bootstrap(ISO/'backend',ISO/'rehearsal.sqlite3')
    from semi_finished_readonly_guard import ReadOnlyGuard
    from pde.models import MaterialConfigurationAttribute, ComponentMaterialRequirement, BOMItem, TemplateMaterialRequirementSlot
    from pde.material_loss_policy_service import MaterialLossPolicyService
    rows=[]
    with connection.execute_wrapper(ReadOnlyGuard()):
        for model,names in [(ComponentMaterialRequirement,['net_quantity','gross_quantity','quantity','per_edge_allowance_mm']),
                            (BOMItem,['quantity']),(TemplateMaterialRequirementSlot,['fixed_quantity'])]:
            with connection.cursor() as c:
                c.execute('PRAGMA table_info("'+model._meta.db_table+'")')
                fields={r[1]:r for r in c.fetchall()}
            for name in names:
                f=model._meta.get_field(name)
                assert f.null and fields[f.column][3]==0 and fields[f.column][4] is None
                rows.append({'table':model._meta.db_table,'column':name,'nullable':True,'dbDefault':None})
        attr=MaterialConfigurationAttribute()
        assert attr.knowledge_state=='UNKNOWN' and attr.canonical_value is None
        assert 'KNOWN_FALSE' in dict(MaterialConfigurationAttribute.Knowledge.choices)
        req=ComponentMaterialRequirement()
        assert req.net_quantity is None and req.gross_quantity is None and req.quantity is None
        for qty,segs in [('1',[{'netSegmentLengthMm':'1000','quantityMultiplier':'1'}]),('0',[])]:
            result=MaterialLossPolicyService.per_edge_preview(qty,segs,None)
            assert result['grossLengthM'] is None and result['totalAllowanceM'] is None
        with connection.cursor() as c:
            c.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name IN ('pde_component_material_requirement','pde_bom_item','pde_material_configuration_attribute','pde_material_loss_policy')")
            schemas=dict(c.fetchall())
        assert 'pde_requirement_gross_guard' in schemas['pde_component_material_requirement']
        assert all(v in schemas['pde_material_configuration_attribute'] for v in ['UNKNOWN','KNOWN_FALSE','KNOWN_TRUE','NOT_APPLICABLE'])
    connection.close()
    after,check=business_compare(ISO/'rehearsal.sqlite3',load('START_BASELINE.json'))
    save('OFFLINE_SCHEMA_PROTECTION.json',{'status':'PASS','nullableFields':rows,'unknownNotFalse':True,
        'netKnownParameterPendingGrossNull':True,'zeroNetParameterPendingGrossStillNull':True,
        'business':check,'schemas':schemas,'productionScope':'NOT APPLIED'})
    print('OFFLINE SCHEMA NULL/UNKNOWN PROTECTION PASS')
else:
    start=load('START_BASELINE.json');after=snapshot(DB)
    assert all(after[k]==start[k] for k in ['sha256','tables','recorder','size'])
    baseline=load('CODE_BASELINE.json')
    assert all((sha(p) if Path(p).exists() else None)==h for p,h in baseline.items())
    oldfiles={str(p):sha(p) for p in OLD.rglob('*') if p.is_file()}
    frozen_root=ROOT/'docs/evidence/room_door_edge_20260909'
    frozen=json.loads((frozen_root/'BASELINE.json').read_text(encoding='utf-8'))['files']
    for item in json.loads((frozen_root/'FINAL_NON_REGRESSION.json').read_text(encoding='utf-8'))['authorizedChanges']:
        frozen[item['path']]=item['after']
    assert all(sha(p)==h for p,h in frozen.items())
    assert not (OUT/'EXECUTION_STARTED.json').exists()
    assert not (OUT/'BACKUP.json').exists()
    assert not (ROOT/'backend/pde/semi_finished_schema_status.py').exists()
    for f in manifest()['files']:
        assert sha(ISO/f['path'])==f['testedSha']
    conn=bootstrap(ROOT/'backend',DB)
    from semi_finished_readonly_guard import ReadOnlyGuard
    from django.core.management import call_command
    from system.models import User
    from pde.views import EngineeringCalculationReadinessView
    from rest_framework.test import APIRequestFactory,force_authenticate
    check=StringIO();call_command('check',stdout=check,stderr=check)
    actor=User.objects.filter(is_superuser=True,is_active=True,company_id=1).defer('password').first();assert actor
    with conn.execute_wrapper(ReadOnlyGuard()):
        request=APIRequestFactory().get('/api/pde/a1-engineering/calculations/readiness/',{'subview':'semi-finished-structure'})
        force_authenticate(request,actor);response=EngineeringCalculationReadinessView.as_view()(request)
        assert response.status_code==200,response.data
        original=json.loads((frozen_root/'API_READONLY_EVIDENCE.json').read_text(encoding='utf-8'))
        assert response.data['semiFinishedConfiguration']==original['semiFinishedConfiguration']
    conn.close();assert sha(DB)==start['sha256']
    failure=load('FULL_BUILD_BLOCKERS.json')
    failures=failure['failures']
    # Every frontend source except the one isolated compatibility component is
    # byte-identical to current production. This establishes no SCM code change.
    changed=[];same=0
    for p in (ISO/'frontend/src').rglob('*'):
        if p.is_file():
            rel=p.relative_to(ISO)
            if sha(p)!=sha(ROOT/rel):changed.append(str(rel))
            else:same+=1
    assert changed==['frontend\\src\\meta\\components\\SemiFinishedConfigurationPreview.vue'],changed
    save('PRODUCTION_UNCHANGED_FINAL.json',{'status':'PASS','databaseSHA':sha(DB),'size':after['size'],
        'allTables':len(after['tables']),'businessTables':len(after['tables'])-2,
        'recorderUnchanged':True,'schemaUnchanged':True,'allOriginalRowsUnchanged':True,
        'codeBaselineFiles':len(baseline),'runtimeCodeChanges':0,'priorFrozenFiles':len(frozen),
        'priorFrozenUnchanged':True,'originalAPI':200,'originalProjectionUnchanged':True,
        'systemCheck':check.getvalue(),'integrity':after['integrity'],'fk':after['foreignKeys'],
        'counts':{k:v['count'] for k,v in after['tables'].items()},
        'targetMigrationApplied':0,'productionRetryExecuted':False,'newRetryBackupCreated':False,
        'productionBusinessFactCreate':0,'domainRuleFormalization':'NOT ENTERED',
        'productionSchemaCapability':'BLOCKED / NOT APPLIED'})
    save('NON_REGRESSION_SCOPE.json',{'status':'PARTIAL / LIVE UI NOT VERIFIED','productionCodeDrift':0,
        'unchangedFrontendSourceFiles':same,'isolatedChangedFrontendFiles':changed,
        'fullBuildFailedAssertions':len(failures),'failures':[{'page':f['canonicalName'],'check':f['fieldOrControl']} for f in failures],
        'scmSourceModified':False,'globalGateNotBypassed':True})
    save('PRIOR_FAILURE_ARCHIVE_SHA.json',oldfiles)
    print(json.dumps({'productionUnchanged':True,'dbSHA':sha(DB),'codeBaseline':len(baseline),'frozen':len(frozen),
        'globalBuildFailures':len(failures),'retryExecuted':False,'businessWrites':0}))
