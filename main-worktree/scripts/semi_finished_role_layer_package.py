"""Deliver exact tested isolated files and verify frozen production boundaries."""
import argparse
import difflib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from semi_finished_role_layer import ROOT, OUT, BACKEND, read, save, sha

PACKAGE=ROOT/'tools/semi-finished-model-closure/20260909-role-layer'
PATHS=['pde/models.py','pde/material_configuration_models.py','pde/material_configuration_service.py',
    'pde/material_configuration_serializers.py','pde/order_engineered_product_service.py',
    'pde/migrations/0024_restore_material_contract_state.py',
    'pde/migrations/0025_material_configuration_applicability_quantity.py',
    'pde/migrations/0026_material_role_layer_correction.py']

def package():
    baseline=read('BASELINE.json')
    model=ROOT/'backend/pde/models.py'
    assert sha(model)==baseline['files'][str(model)]
    manifest={'status':'ISOLATED_TESTED_NOT_PRODUCTION_APPLIED','productionApplied':False,
        'instructionSha256':baseline['instructionSha'],'productionModelSha256':sha(model),
        'productionDatabaseSha256':sha(ROOT/'backend/db.sqlite3'),
        'replaySha256':sha(OUT/'ISOLATED_REPLAY.json'),'files':[],
        'noProductionApplyRunner':True,'previousPackagePreserved':True}
    for path in PATHS:
        src=BACKEND/path;dest=PACKAGE/'candidate/backend'/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest)
        assert sha(src)==sha(dest)
        manifest['files'].append({'canonicalPath':'backend/'+path,'packagePath':str(dest.relative_to(PACKAGE)),
            'testedSha256':sha(src),'deliveredSha256':sha(dest)})
    patch=''.join(difflib.unified_diff(model.read_text(encoding='utf-8').splitlines(keepends=True),
        (BACKEND/'pde/models.py').read_text(encoding='utf-8').splitlines(keepends=True),
        fromfile='a/backend/pde/models.py',tofile='b/backend/pde/models.py'))
    patchpath=PACKAGE/'canonical-models.patch';patchpath.write_bytes(patch.encode('utf-8'))
    result=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','apply','--check',str(patchpath)],
        cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    manifest['readOnlyPatchCheck']='PASS'
    (PACKAGE/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save('PACKAGE_VERIFICATION.json',manifest)
    print('8 candidate files tested == delivered; read-only patch check PASS')

def nonregression():
    from engineering_material_configuration_audit import snapshot
    baseline=read('BASELINE.json')
    allowed={str(ROOT/p) for p in ('backend/pde/semi_finished_configuration_validation.py',
        'backend/pde/semi_finished_configuration_preview.py',
        'frontend/src/meta/components/SemiFinishedConfigurationPreview.vue',
        'frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue',
        'docs/governance/MANUFACTURING_DEFINITION_APPLICABILITY_CONTRACT_V1.0.md')}
    changed=[{'path':p,'before':expected,'after':sha(p) if Path(p).exists() else None}
        for p,expected in baseline['files'].items() if not Path(p).exists() or sha(p)!=expected]
    unexpected=[r for r in changed if r['path'] not in allowed]
    assert not unexpected,unexpected
    native_roots=[ROOT/'scripts/excel_parity',ROOT/'tools/excel-golden-runner',
        ROOT/'docs/evidence/excel_formula_parity/closure-20260909']
    current={str(p) for folder in native_roots for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    frozen={p for p in baseline['files'] if any(Path(p).is_relative_to(folder) for folder in native_roots)}
    assert current==frozen,{'added':sorted(current-frozen),'removed':sorted(frozen-current)}
    formal=snapshot();assert formal==read('FORMAL_BEFORE.json')
    save('FORMAL_AFTER.json',formal)
    for file in read('PACKAGE_VERIFICATION.json')['files']:
        assert sha(PACKAGE/file['packagePath'])==file['testedSha256']
        assert sha(BACKEND/file['canonicalPath'].removeprefix('backend/'))==file['testedSha256']
    api=read('API_READONLY_EVIDENCE.json');ui=read('UI_DIAGNOSTIC.json')
    assert ui['semiFinishedConfiguration']==api['semiFinishedConfiguration']
    assert ui['strictFacts']==ui['strictServerFacts']
    assert all(ui['strictFacts'][k]==v for k,v in api['strictFacts'].items() if k!='loadedAt')
    for name in ('apiFacts','strictFacts','pageFacts','diagnosticFacts'):
        assert api[name]==api['strictFacts']
    save('FIVE_SURFACE_CONSISTENCY.json',{'status':'PASS',
        'surfaces':['API','page server payload','strict facts','copied diagnostic','new layer summary'],
        'fullProjectionExactEquality':True,'ignoredFactFields':['loadedAt'],
        'diagnosticGeneratedAt':ui['diagnosticGeneratedAt'],
        'diagnosticSha256':sha(OUT/'UI_DIAGNOSTIC.json'),'productionBusinessWrite':0})
    report={'status':'PASS','capturedAt':datetime.now(timezone.utc).isoformat(),
        'baselineFiles':len(baseline['files']),'unchangedFiles':len(baseline['files'])-len(changed),
        'authorizedChanges':changed,'unexpectedChanges':unexpected,'frozenNativeFiles':len(frozen),
        'nativeAdded':0,'nativeRemoved':0,'nativeRerun':False,'productionBusinessWrite':0,
        'productionMigrationApplied':False,'productionSha256':formal['sha256'],
        'formalCounts':{t:s['count'] for t,s in formal['tables'].items()},
        'testedCandidateEqualsDelivered':True,'oldPackageAndEvidenceUnchanged':True,
        'frontend':read('FRONTEND_TEST_RESULTS.json'),'api':read('API_TEST_RESULTS.json')}
    save('FINAL_NON_REGRESSION.json',report)
    print(json.dumps({k:report[k] for k in ('status','baselineFiles','unchangedFiles','frozenNativeFiles','productionSha256')},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['package','nonregression'])
    {'package':package,'nonregression':nonregression}[parser.parse_args().action]()
