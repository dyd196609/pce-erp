"""Supplemental diagnostics do not bypass the failing full-build gate."""
import json, subprocess, sys
from semi_finished_schema_retry import ROOT, ISO, OUT, sha, save, load, manifest

commands=[('canonical',['scripts/verifyFrontendPageIdentityConvergence.mjs']),
 ('system-config',['scripts/verifySystemConfigNonRegression.mjs']),
 ('operation-route',['scripts/verifyOperationRouteRecoveryP0.mjs']),
 ('foundation-preview',['src/meta/runtime/foundationWave1ImportPreview.test.mjs']),
 ('vite-compilation-only',['node_modules/vite/bin/vite.js','build','.'])]
results=[]
for name,args in commands:
    with open(OUT/('OFFLINE_'+name+'.log'),'w',encoding='utf-8') as f:
        r=subprocess.run(['D:/nodejs/node.exe',*args],cwd=ISO/'frontend',stdout=f,stderr=subprocess.STDOUT)
    results.append({'name':name,'exitCode':r.returncode})
    print(name,r.returncode,flush=True)
save('OFFLINE_FRONTEND_DIAGNOSTICS.json',{'commands':results,
    'fullBuildGate':'FAIL; npm prebuild 7 existing SCM assertions. These diagnostics do not authorize deployment.'})
report=json.loads((ISO/'frontend/test-results/pce-web-acceptance-v1-1/static-gate-report.json').read_text(encoding='utf-8'))
save('FULL_BUILD_BLOCKERS.json',report)
code=[]
for item in manifest()['files']:
    code.append({'path':item['path'],'sha256':sha(ISO/item['path']),'scope':'unchanged frozen model package'})
compat=[
 ('backend/pde/semi_finished_schema_status.py','Read recorder/table fields/counts and expose Schema Ready separately from zero business data; no write method.'),
 ('backend/pde/semi_finished_configuration_preview.py','Replace blanket migrated-table refusal with audited readonly capability binding; frozen source projection unchanged.'),
 ('frontend/src/meta/components/SemiFinishedConfigurationPreview.vue','Render server status/actual zero counts and frozen user decision; no calculation/save endpoint.')]
for path,why in compat:
    code.append({'path':path,'sha256':sha(ISO/path),'scope':'minimal readonly compatibility','whyRequired':why})
save('DRAFT_CANDIDATE_MANIFEST.json',{'status':'DRAFT / NOT PACKAGE READY','files':code,'businessWrite':0,
    'guard':{'path':'scripts/semi_finished_readonly_guard.py','sha256':sha(ROOT/'scripts/semi_finished_readonly_guard.py'),
    'scope':'harness only, no business dependency'},'unpassedGates':['full frontend build','real HTTP','real menu','tested==served','complete rollout rollback']})
