import assert from 'node:assert/strict'
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { foundationCanonicalModules, getFoundationCanonicalModule, foundationSubviewLocation, resolveFoundationPageState } from '../src/meta/master-data/foundationEntryUnificationRegistry.js'
import { assertPceFactLoadFacts, PCE_FACT_LOAD_CONTRACT_VERSION } from '../src/meta/runtime/pceFactLoadContract.js'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const out=path.resolve(root,'../docs/evidence/semi_finished_role_layer_20260909')
const checks=[]
const check=(name,fn)=>{fn();checks.push({name,result:'PASS'})}
const files=['src/meta/pages/PdeOrderEngineeringCalculationPage.vue','src/meta/components/SemiFinishedConfigurationPreview.vue']
const hash=data=>createHash('sha256').update(data).digest('hex')
const module=getFoundationCanonicalModule('engineering-calculation')
check('Existing canonical engineering subview and all 27 modules retained',()=>{
  const target=foundationSubviewLocation(module.moduleId,'semi-finished-structure')
  assert.equal(target.name,module.routeName)
  assert.equal(resolveFoundationPageState({path:module.routePath,query:target.query}).subview,'semi-finished-structure')
  assert.equal(foundationCanonicalModules.length,27)
  for(const m of foundationCanonicalModules) assert.equal(resolveFoundationPageState({path:m.routePath}).moduleId,m.moduleId)
})
for(const file of files)check(`Vue compile ${file}`,()=>{
  const {descriptor,errors}=parse(readFileSync(path.join(root,file),'utf8'),{filename:file});assert.deepEqual(errors,[])
  const script=compileScript(descriptor,{id:'role-layer'})
  const template=compileTemplate({source:descriptor.template.content,filename:file,id:'role-layer',compilerOptions:{bindingMetadata:script.bindings}})
  assert.deepEqual(template.errors,[])
})
check('Three distinct layer views and no persistence/network/auth access in child',()=>{
  const text=readFileSync(path.join(root,files[1]),'utf8')
  for(const label of ['A. 制造配置','B. 工程组件','C. 材料需求','封边属于组件，不是半成品板材组成','三合一 L 列','木皮净面积','每边预留','工程结构 / 粗略 BOM'])assert.ok(text.includes(label),label)
  assert.doesNotMatch(text,/localStorage|sessionStorage|fetch\(|axios|\.post\(|\.put\(|\.delete\(/)
  assert.doesNotMatch(text,/全部UNKNOWN|厚.*仍为.*UNKNOWN|OTHER FIXED COMPOSITION/)
})
const served=[]
check('Diagnostic provider binds existing strict server facts without local recomputation',()=>{
  const text=readFileSync(path.join(root,files[0]),'utf8')
  const body=text.match(/function diagnostics\(\) \{([^\n]+)\}/)?.[1] || ''
  for(const binding of ['strictFacts: facts.value','strictServerFacts: facts.value','pageFacts: facts.value','apiFacts: payload.value.apiFacts'])assert.ok(body.includes(binding),binding)
  const payload={value:JSON.parse(readFileSync(path.join(out,'API_READONLY_EVIDENCE.json'),'utf8'))}
  const facts={value:payload.value.strictFacts}
  const diagnostic=new Function('payload','facts','ruleDefinition','PCE_FACT_LOAD_CONTRACT_VERSION',body)(payload,facts,{value:{}},PCE_FACT_LOAD_CONTRACT_VERSION)
  assert.deepEqual(diagnostic.strictServerFacts,facts.value)
  assert.equal(assertPceFactLoadFacts(diagnostic.factLoadFacts).resultCount,61)
})
for(const file of files){
  const response=await fetch(`http://localhost:5173/${file}?raw`,{headers:{'cache-control':'no-cache'}});assert.ok(response.ok)
  const match=(await response.text()).match(/^export default ("(?:[^"\\]|\\.)*")/s);assert.ok(match)
  const source=readFileSync(path.join(root,file),'utf8');assert.equal(JSON.parse(match[1]),source)
  served.push({file,sourceSha256:hash(source),servedSha256:hash(JSON.parse(match[1]))})
}
const commands=[
  ['page identity',['scripts/verifyFrontendPageIdentityConvergence.mjs']],
  ['system config non-regression',['scripts/verifySystemConfigNonRegression.mjs']],
  ['operation route preservation',['scripts/verifyOperationRouteRecoveryP0.mjs']],
  ['tested served runtime identity',['scripts/verifyTestedServedFrontendIdentity.mjs']],
  ['existing foundation preview',['src/meta/runtime/foundationWave1ImportPreview.test.mjs']],
]
if(process.argv.includes('--build'))commands.push(['isolated Vite build',['node_modules/vite/bin/vite.js','build','.','--outDir','../.runtime/semi-finished-role-layer-build']])
const results=[]
for(const [name,args] of commands){
  const r=spawnSync(process.execPath,args,{cwd:root,encoding:'utf8',windowsHide:true,maxBuffer:20*1024*1024})
  writeFileSync(path.join(out,`frontend-${results.length+1}.log`),`${r.stdout||''}\n${r.stderr||''}`)
  results.push({name,exitCode:r.status,status:r.status===0?'PASS':'FAIL'});console.log(`${name}: ${results.at(-1).status}`)
}
writeFileSync(path.join(out,'FRONTEND_TEST_RESULTS.json'),JSON.stringify({checks,served,commands:results,canonicalModules:foundationCanonicalModules.length,productionBusinessWrite:0},null,2))
assert.ok(results.every(r=>r.status==='PASS'))
