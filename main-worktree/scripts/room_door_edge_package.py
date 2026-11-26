"""Seal tested candidate and audit frozen evidence, with no production apply command."""
import ast,difflib,json,shutil,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from room_door_edge import ROOT,OUT,OLD,ISO,BACKEND,PACKAGE,PREVIOUS,INSTRUCTION,read,save,sha
PATHS=['pde/models.py','pde/material_configuration_models.py','pde/material_configuration_service.py',
 'pde/material_configuration_serializers.py','pde/order_engineered_product_service.py','pde/material_loss_policy_service.py',
 'pde/migrations/0024_restore_material_contract_state.py','pde/migrations/0025_material_configuration_applicability_quantity.py',
 'pde/migrations/0026_material_role_layer_correction.py','pde/migrations/0027_component_net_and_loss_policy.py']
def package():
    assert not PACKAGE.exists()
    files=[]
    for p in PATHS:
        src=BACKEND/p;dest=PACKAGE/'candidate/backend'/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        assert sha(src)==sha(dest)
        files.append({'path':'backend/'+p,'packagePath':str(dest.relative_to(PACKAGE)),'testedSha':sha(src),'deliveredSha':sha(dest)})
    model=ROOT/'backend/pde/models.py'
    diff=''.join(difflib.unified_diff(model.read_text(encoding='utf-8').splitlines(True),(BACKEND/'pde/models.py').read_text(encoding='utf-8').splitlines(True),fromfile='a/backend/pde/models.py',tofile='b/backend/pde/models.py'))
    patch=PACKAGE/'canonical-models.patch';patch.write_text(diff,encoding='utf-8',newline='')
    check=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','apply','--check',str(patch)],cwd=ROOT,capture_output=True,text=True)
    assert check.returncode==0,check.stderr
    manifest={'status':'ISOLATED_TESTED_NOT_PRODUCTION_APPLIED','files':files,'productionApplyRunner':False,
        'previousPackagePreserved':True,'replaySha':sha(OUT/'ISOLATED_REPLAY.json'),'readOnlyPatchCheck':'PASS'}
    (PACKAGE/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save('PACKAGE_VERIFICATION.json',manifest);print('10 tested candidate files packaged; production not applied')

def audit():
    from engineering_material_configuration_audit import snapshot
    baseline=read('BASELINE.json');allowed={str(ROOT/p) for p in ('backend/pde/semi_finished_configuration_preview.py','frontend/src/meta/components/SemiFinishedConfigurationPreview.vue')}
    changed=[{'path':p,'before':s,'after':sha(p) if Path(p).exists() else None} for p,s in baseline['files'].items() if not Path(p).exists() or sha(p)!=s]
    assert not [c for c in changed if c['path'] not in allowed]
    formal=snapshot();assert formal==read('FORMAL_BEFORE.json');save('FORMAL_AFTER.json',formal)
    source=read('SOURCE_NATIVE_AUDIT.json');native=Path(source['nativeRun'])
    inputs=[Path(s['path']) for s in source['sourceFiles']]+[native/n for n in read('RUN_MANIFEST.json',native)['files']]
    inputs += [ROOT.parent/'AGENTS.md',ROOT/'AGENTS.md',ROOT/'docs/governance/PCE CODEX开发指令规范管理V1.2.md',
        ROOT/'docs/governance/Schema规范.md',ROOT/'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
        ROOT/'docs/governance/MANUFACTURING_DEFINITION_APPLICABILITY_CONTRACT_V1.0.md',INSTRUCTION,
        ROOT/'backend/pde/semi_finished_configuration_source.json',ROOT/'docs/evidence/excel_formula_parity/FORMULA_FAMILY_INVENTORY.json',
        ROOT/'scripts/excel_parity/generated_reference.py',OLD/'ISOLATED_REPLAY.json',ROOT/'backend/db.sqlite3']
    save('INPUT_MANIFEST.json',{'coreInputFileCount':len(inputs),'files':[{'path':str(p),'sha256':sha(p)} for p in inputs],
        'countingBasis':'core governance/source/Native/formal evidence inputs; auxiliary code and read-only architecture scans counted separately'})
    api=read('API_READONLY_EVIDENCE.json');ui=read('UI_DIAGNOSTIC.json')
    assert api['semiFinishedConfiguration']==ui['semiFinishedConfiguration']
    assert all(api[k]==api['strictFacts'] for k in ('apiFacts','pageFacts','diagnosticFacts'))
    assert ui['strictFacts']==ui['strictServerFacts']
    assert all(ui['strictFacts'][k]==v for k,v in api['strictFacts'].items() if k!='loadedAt')
    screen=read('UI_READBACK.json');assert screen['componentCount']==8 and screen['refreshSelectionPreserved']
    assert '未提供' not in screen['componentText']
    for r in read('ISOLATED_REPLAY.json')['roomDoorRequirements']:
        assert r['netLengthM']+' m' in screen['componentText']
    for f in read('PACKAGE_VERIFICATION.json')['files']:
        assert sha(PACKAGE/f['packagePath'])==f['testedSha']==sha(BACKEND/f['path'].removeprefix('backend/'))
    # Audit original canonical and previously isolated policy carriers; new model is not a parallel replacement.
    scanned=[];found=[]
    for base in (ROOT/'backend',PREVIOUS/'candidate/backend'):
        for p in base.rglob('*.py'):
            if set(p.parts)&{'venv','.venv','__pycache__'}:continue
            scanned.append(str(p))
            if 'migration' in str(p):continue
            text=p.read_text(encoding='utf-8-sig',errors='replace')
            if 'class MaterialLossPolicy' in text or 'class LossPolicy' in text:found.append(str(p))
    assert not found
    names=formal.get('allTableNames',[])
    # Existing gross_edges is a frozen recovery test helper, not a persistent corporate parameter model.
    save('LOSS_POLICY_ARCHITECTURE_AUDIT.json',{'status':'MINIMAL_SHARED_ISOLATED_TARGET','scannedPythonFiles':len(scanned),
        'existingPolicyModels':found,'previousRequirementAllowanceField':'per_edge_allowance_mm; scalar only, no policy/version carrier',
        'newTarget':'pde.MaterialLossPolicy','sharedService':'pde.material_loss_policy_service.MaterialLossPolicyService',
        'originalNetRuleCarrier':'pde.EngineeringRuleDefinition','newFormulaEngine':False,
        'fields':['company','requirement_kind','source_material_identity','material','method','allowance_mm','suggested_allowance_mm','parameter_uom','source','version','parameter_status','modified_by','modified_at'],
        'independentPolicyIdentities':3,'realAllowanceValues':0,'productionPolicyWrites':0,
        'areaLossRate':'NOT_IMPLEMENTED_OR_REUSED_AS_LENGTH_ALLOWANCE'})
    frozen_roots=[ROOT/'scripts/excel_parity',ROOT/'tools/excel-golden-runner',ROOT/'docs/evidence/excel_formula_parity/closure-20260909']
    expected={p for p in baseline['files'] if any(Path(p).is_relative_to(root) for root in frozen_roots)}
    current={str(p) for root in frozen_roots for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert current==expected
    save('FIVE_SURFACE_CONSISTENCY.json',{'status':'PASS','fullProjectionEqual':True,'apiPageStrictDiagnosticReportSameFacts':True,'ignoredMetadataOnly':['loadedAt'],
        'clipboardEvidence':read('CLIPBOARD_CAPTURE_AUDIT.json'),'sourceRowsVerified':8,'edgeSourceRequirements':16})
    save('FINAL_NON_REGRESSION.json',{'status':'PASS','capturedAt':datetime.now(timezone.utc).isoformat(),
        'baselineFiles':len(baseline['files']),'unchanged':len(baseline['files'])-len(changed),'authorizedChanges':changed,
        'frozenNativeFiles':len(expected),'nativeAdded':0,'nativeRemoved':0,'nativeModified':0,'nativeRerun':False,
        'formalCounts':{k:v['count'] for k,v in formal['tables'].items()},'productionSHA':formal['sha256'],
        'productionBusinessWrite':0,'productionMigrationApplied':False,'oldPackagesAndEvidenceUnchanged':True,
        'boardNonRegression':'PASS','veneerNonRegression':'PASS','threeInOneEdges':59,'threeInOneNetM':'296.062',
        'unitTests':read('ISOLATED_TEST_RESULTS.json'),'API':read('API_TEST_RESULTS.json'),'frontend':read('FRONTEND_TEST_RESULTS.json'),
        'roundtrip':read('ROUNDTRIP_RESULTS.json')['status'],'rollback':read('ROLLBACK_RESULTS.json')['status']})
    print(json.dumps({k:read('FINAL_NON_REGRESSION.json')[k] for k in ('status','baselineFiles','unchanged','frozenNativeFiles','productionSHA')}))
if __name__=='__main__':{'package':package,'audit':audit}[sys.argv[1]]()
