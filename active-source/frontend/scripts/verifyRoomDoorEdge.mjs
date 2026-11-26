import assert from 'node:assert/strict'
import {readFileSync,writeFileSync} from 'node:fs'
import {createHash} from 'node:crypto'
import {spawnSync} from 'node:child_process'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {parse,compileScript,compileTemplate} from '@vue/compiler-sfc'
import {foundationCanonicalModules,resolveFoundationPageState} from '../src/meta/master-data/foundationEntryUnificationRegistry.js'
import {assertPceFactLoadFacts,PCE_FACT_LOAD_CONTRACT_VERSION} from '../src/meta/runtime/pceFactLoadContract.js'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),out=path.resolve(root,'../docs/evidence/room_door_edge_20260909')
const files=['src/meta/pages/PdeOrderEngineeringCalculationPage.vue','src/meta/components/SemiFinishedConfigurationPreview.vue','src/meta/components/RoomDoorEdgeRequirementPreview.vue']
const hash=s=>createHash('sha256').update(s).digest('hex');const checks=[],served=[]
assert.equal(foundationCanonicalModules.length,27)
for(const m of foundationCanonicalModules)assert.equal(resolveFoundationPageState({path:m.routePath}).moduleId,m.moduleId)
checks.push('27 existing modules and canonical routes preserved')
for(const file of files){
  const source=readFileSync(path.join(root,file),'utf8');const {descriptor,errors}=parse(source,{filename:file});assert.deepEqual(errors,[])
  const script=compileScript(descriptor,{id:'door-edge'}),template=compileTemplate({source:descriptor.template.content,filename:file,id:'door-edge',compilerOptions:{bindingMetadata:script.bindings}})
  assert.deepEqual(template.errors,[]);checks.push(`Vue compiled: ${file}`)
  const response=await fetch(`http://localhost:5173/${file}?raw`,{headers:{'cache-control':'no-cache'}});assert.ok(response.ok)
  const match=(await response.text()).match(/^export default ("(?:[^"\\]|\\.)*")/s);assert.ok(match);assert.equal(JSON.parse(match[1]),source)
  served.push({file,sourceSha256:hash(source),servedSha256:hash(JSON.parse(match[1]))})
  if(file.includes('/components/'))assert.doesNotMatch(source,/localStorage|sessionStorage|fetch\(|axios|\.post\(|\.put\(|\.delete\(/)
}
const child=readFileSync(path.join(root,files[1]),'utf8'),edge=readFileSync(path.join(root,files[2]),'utf8')
for(const phrase of ['visibleAreaFact.visibleAreaM2','roomDoorRequirements','roomDoorSummary','三层模型已人工确认','房门六项'])assert.ok(child.includes(phrase),phrase)
for(const phrase of ['requirement.netLengthM','requirement.edgeCount','每边预留','毛需求：待定','待企业参数','25/50不擅自解释为宽度'])assert.ok(edge.includes(phrase),phrase)
checks.push('read-only source facts; net/gross/identity/parameter separated')
const parent=readFileSync(path.join(root,files[0]),'utf8'),body=parent.match(/function diagnostics\(\) \{([^\n]+)\}/)[1]
const payload={value:JSON.parse(readFileSync(path.join(out,'API_READONLY_EVIDENCE.json'),'utf8'))},facts={value:payload.value.strictFacts}
const diagnostic=new Function('payload','facts','ruleDefinition','PCE_FACT_LOAD_CONTRACT_VERSION',body)(payload,facts,{value:{}},PCE_FACT_LOAD_CONTRACT_VERSION)
assert.deepEqual(diagnostic.strictServerFacts,facts.value);assert.equal(assertPceFactLoadFacts(diagnostic.factLoadFacts).resultCount,61)
assert.equal(diagnostic.strictServerFacts.roomDoorEdge25NetTotalM,'76.300');checks.push('same server facts in diagnostic adapter')
const commands=[['canonical identity',['scripts/verifyFrontendPageIdentityConvergence.mjs']],['system config',['scripts/verifySystemConfigNonRegression.mjs']],
 ['operation route',['scripts/verifyOperationRouteRecoveryP0.mjs']],['tested served',['scripts/verifyTestedServedFrontendIdentity.mjs']],
 ['foundation preview',['src/meta/runtime/foundationWave1ImportPreview.test.mjs']],
 ['isolated build',['node_modules/vite/bin/vite.js','build','.','--outDir','../.runtime/room-door-edge-build']]]
const results=[]
for(const [name,args] of commands){
 const r=spawnSync(process.execPath,args,{cwd:root,encoding:'utf8',windowsHide:true,maxBuffer:20*1024*1024})
 writeFileSync(path.join(out,`frontend-${results.length+1}.log`),`${r.stdout||''}\n${r.stderr||''}`)
 results.push({name,exitCode:r.status,status:r.status===0?'PASS':'FAIL'});console.log(name,results.at(-1).status)
}
writeFileSync(path.join(out,'FRONTEND_TEST_RESULTS.json'),JSON.stringify({checks,served,commands:results,canonicalModules:27,productionBusinessWrite:0},null,2))
assert.ok(results.every(r=>r.status==='PASS'))
