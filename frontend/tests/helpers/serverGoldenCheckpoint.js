import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { request as playwrightRequest } from '@playwright/test'

export const SERVER_CHECKPOINT_CONTRACT = 'PCE-DJANGO-GOLDEN-CHECKPOINT-V1'
const root=path.resolve(process.cwd()), checkpointRoot=path.join(root,'test-results/purchase-payment-golden-flow/checkpoints')
const core=['storage-state.json','application-state.json','business-entities.json','relationship-graph.json']
const sourceFiles=['backend/procurement/scm_runtime_services.py','backend/procurement/scm_runtime_actions.py','backend/procurement/inventory_facts_api.py','backend/procurement/business_action_control.py','backend/procurement/models.py','backend/procurement/inventory_purpose.py','backend/system/authorization.py','frontend/src/api/formalExecution.js','frontend/src/meta/pages/FormalExecutionPage.vue','frontend/src/router/index.js','frontend/vite.config.js']
const hash=b=>crypto.createHash('sha256').update(b).digest('hex')
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'))
const write=async(p,v)=>fs.writeFile(p,JSON.stringify(v,null,2)+'\n','utf8')
function assert(ok,message){if(!ok)throw Error(message)}
export async function serverBinding(){
 assert(process.env.PCE_SERVER_CHECKPOINT_BINDING,'PCE_SERVER_CHECKPOINT_BINDING required; no legacy local-state fallback')
 const b=await read(process.env.PCE_SERVER_CHECKPOINT_BINDING)
 assert(b.contract===SERVER_CHECKPOINT_CONTRACT&&b.isolated===true,'explicit native isolated binding required')
 assert(path.resolve(b.sourceRoot)===path.resolve(root,'..'),'native service source differs from frontend source')
 assert(path.resolve(b.database)!==path.resolve(b.protectedDatabase),'native fixture must not write the protected database')
 return b
}
export async function sourceIdentity(){
 const base=path.resolve(root,'..'),files=[]
 for(const name of sourceFiles)files.push({path:name,sha256:hash(await fs.readFile(path.join(base,name)))})
 return {sourceRoot:base,files,fingerprint:hash(JSON.stringify(files))}
}
export async function seedAuthentication(){
 const b=await serverBinding()
 const r=spawnSync(b.python,[b.authenticationFixture],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'},windowsHide:true})
 assert(r.status===0,r.stderr||'native authentication fixture failed')
 // Random passwords live in this process environment only, never in checkpoint artifacts.
 process.env.PCE_NATIVE_AUTH_JSON=r.stdout.trim()
 return JSON.parse(r.stdout)
}
export async function authenticateNative(baseURL,actorId){
 const credentials=JSON.parse(process.env.PCE_NATIVE_AUTH_JSON||'[]').find(x=>x.id===actorId)
 assert(credentials,'native account credential context absent; run original checkpoint runner')
 const api=await playwrightRequest.newContext({baseURL})
 try{const r=await api.post('/api/auth/login/',{data:{username:credentials.username,password:credentials.password}});const body=await r.json();assert(r.ok()&&body.token&&body.user,'native login failed');return body}finally{await api.dispose()}
}
export async function restoreServerAuthentication(context,page,baseURL,actorId){
 const login=await authenticateNative(baseURL,actorId)
 // The token is returned by the original login endpoint. No business object or status is restored.
 await context.addInitScript(({token,user})=>{
   sessionStorage.setItem('pce_tab_auth_token_v1',token)
   sessionStorage.setItem('pce_current_identity_v1',JSON.stringify({userId:user.id,username:user.username,realName:user.real_name,companyId:user.company_id}))
 },{token:login.token,user:login.user})
 await page.goto(baseURL+'/#/qms',{waitUntil:'networkidle'})
 return login
}
export async function readServerSnapshot(page,entities){
 const result={observedAt:new Date().toISOString(),authority:'django',endpoints:{}}
 for(const [key,url] of Object.entries({receipts:'/api/procurement/formal-purchase-receipt-facts/',quality:'/api/procurement/formal-quality-facts/',inventory:'/api/procurement/formal-inventory-facts/'})){
  const response=await page.evaluate(async url=>{const token=sessionStorage.getItem('pce_tab_auth_token_v1');const r=await fetch(url,{headers:{Authorization:'Bearer '+token},credentials:'include'});return {status:r.status,body:await r.json()}},url)
  assert(response.status===200&&response.body.success===true&&response.body.factSource==='server',key+' native fact read failed')
  result.endpoints[key]={url,httpStatus:response.status,authoritySource:response.body.authoritySource,responseHash:hash(JSON.stringify(response.body))}
  if(key==='receipts'){
   const rows=response.body.receipts||response.body.rows||[];result.receipt=rows.find(x=>x.id===entities.receiptId)
  }
  if(key==='quality'){
   result.inspection=response.body.inspections.find(x=>x.id===entities.inspectionId)
   result.inbounds=response.body.inbounds.filter(x=>x.inspectionNo===entities.inspectionNo)
  }
  if(key==='inventory'){
   result.transactions=response.body.transactions.filter(x=>x.lotNo===entities.lotNo&&x.materialCode===entities.materialCode)
   result.balances=response.body.balances.filter(x=>x.lotNo===entities.lotNo&&x.materialCode===entities.materialCode&&x.warehouseCode===entities.warehouseCode)
  }
 }
 assert(result.inspection&&result.receipt,'bound source objects missing from current server scope')
 return result
}
export function assertServerStage(snapshot,e,phase){
 assert(snapshot.receipt.id===e.receiptId&&snapshot.receipt.sourceOrderId===e.purchaseOrderId,'receipt/order relation mismatch')
 assert(snapshot.inspection.receiptNo===e.receiptNo&&snapshot.inspection.purchaseOrderNo===e.purchaseOrderNo,'inspection/receipt/order relation mismatch')
 assert(snapshot.inspection.status==='qualified'&&Number(snapshot.inspection.qualifiedQuantity)===Number(e.quantity),'native qualified inspection missing')
 if(phase==='ready'){
  assert(snapshot.inbounds.length===0&&snapshot.transactions.length===0&&snapshot.balances.length===0,'ready checkpoint already posted to native inventory')
 }else{
  assert(snapshot.inbounds.length===1&&snapshot.transactions.length===1&&snapshot.balances.length===1,'native receipt/transaction/balance cardinality mismatch')
  const inbound=snapshot.inbounds[0],transaction=snapshot.transactions[0],balance=snapshot.balances[0]
  assert(inbound.status==='completed'&&Number(inbound.quantity)===Number(e.quantity),'native inbound completion mismatch')
  assert(transaction.sourceInboundId===inbound.id&&transaction.sourceInboundNo===inbound.inboundNo,'native inventory source relation mismatch')
  assert(transaction.direction==='IN'&&Number(transaction.quantity)===Number(e.quantity),'native transaction quantity/direction mismatch')
  assert(Number(balance.quantity)===Number(e.quantity)&&balance.materialId===e.materialId,'native balance mismatch')
 }
 return {phase,orderReceiptInspectionMatched:true,inboundTransactionBalanceMatched:phase==='completed',factSource:'server'}
}
async function integrity(directory){const h=crypto.createHash('sha256');for(const f of core){h.update(f);h.update(await fs.readFile(path.join(directory,f)))}return h.digest('hex')}
export async function captureServerCheckpoint({context,page,checkpointId,runId,phase,entities,snapshot,restoreProof,testInfo}){
 const binding=await serverBinding(),source=await sourceIdentity(),directory=path.join(checkpointRoot,'.staging',checkpointId+'-'+runId)
 await fs.mkdir(directory,{recursive:true})
 // Native authentication and presentation descriptors only. No WMS/QMS/SCM ledger is written to browser storage.
 const storage=await context.storageState();storage.origins=storage.origins.map(x=>({...x,localStorage:x.localStorage.filter(y=>['pce_current_identity_v1','pce_account_shortcuts_v1'].includes(y.name))}))
 await write(path.join(directory,'storage-state.json'),storage)
 await write(path.join(directory,'application-state.json'),{contract:SERVER_CHECKPOINT_CONTRACT,authority:'django',phase,presentation:{route:'/#/qms',companyId:entities.companyId,actorId:entities.readerId},authentication:{restore:'fresh native login; saved cookies are not an authorization bypass'},businessStateRestoredFromBrowser:false,serverSnapshot:snapshot,binding:{source,database:binding.database,backendOrigin:binding.backendOrigin,preparationEvidenceSha256:hash(await fs.readFile(binding.preparationEvidence))}})
 await write(path.join(directory,'business-entities.json'),{...entities,nativePhase:phase,inventoryTransactionNo:snapshot.transactions[0]?.transactionNo||'',inboundId:snapshot.inbounds[0]?.id||null,inboundNo:snapshot.inbounds[0]?.inboundNo||''})
 const graph=[{fromType:'PurchaseOrder',fromId:entities.purchaseOrderId,toType:'PurchaseReceipt',toId:entities.receiptId},{fromType:'PurchaseReceipt',fromId:entities.receiptId,toType:'PurchaseInspection',toId:entities.inspectionId}]
 if(phase==='completed')graph.push({fromType:'PurchaseInspection',fromId:entities.inspectionId,toType:'WarehouseInbound',toId:snapshot.inbounds[0].id},{fromType:'WarehouseInbound',fromId:snapshot.inbounds[0].id,toType:'InventoryTransaction',toId:snapshot.transactions[0].id})
 await write(path.join(directory,'relationship-graph.json'),{authority:'django',relations:graph,verifiedFromCurrentServer:true})
 await write(path.join(directory,'restore-verification.json'),{contract:SERVER_CHECKPOINT_CONTRACT,...restoreProof,verifiedAt:new Date().toISOString()})
 await page.screenshot({path:path.join(directory,'checkpoint-screenshot.png'),fullPage:true})
 const metadata={contract:SERVER_CHECKPOINT_CONTRACT,authority:'django',checkpointVersion:'1.0.0',checkpointId,runId,createdAt:new Date().toISOString(),origin:new URL(page.url()).origin,baseUrl:new URL(page.url()).origin,phase,source,binding:{database:binding.database,backendOrigin:binding.backendOrigin,preparationEvidenceSha256:hash(await fs.readFile(binding.preparationEvidence))},entityIds:[entities.purchaseOrderNo,entities.receiptNo,entities.inspectionNo,snapshot.inbounds[0]?.inboundNo,snapshot.transactions[0]?.transactionNo].filter(Boolean),nextStageId:phase==='ready'?'native-warehouse-putaway':'native-inventory-readback',sourceCheckpointId:phase==='completed'?'qualified_inbound_ready':'native-qualified-inspection',restorable:false,businessStateRestoredFromBrowser:false,integrityFiles:core,integrityHash:await integrity(directory),generatorHashes:await Promise.all(['tests/e2e/qualifiedInboundReadyGoldenFlow.spec.js','tests/e2e/qualifiedInboundCompletionGoldenFlow.spec.js','tests/helpers/serverGoldenCheckpoint.js'].map(async p=>({path:p,sha256:hash(await fs.readFile(path.join(root,p)))})))}
 await write(path.join(directory,'manifest.json'),metadata)
 return {directory,checkpointId,runId,tracePath:testInfo.outputPath('trace.zip')}
}
export async function finalizeServerCheckpoint(report){
 const metadata=await read(path.join(report.directory,'manifest.json')),restore=await read(path.join(report.directory,'restore-verification.json'))
 assert(restore.freshBrowserContext===true&&restore.serverReadbackMatched===true,'fresh authenticated server readback proof required')
 const trace=await fs.readFile(report.tracePath);assert(trace.length>0,'current Playwright-owned trace missing')
 await fs.writeFile(path.join(report.directory,'trace.zip'),trace)
 metadata.restorable=true;metadata.traceSha256=hash(trace);metadata.restoreProofSha256=hash(await fs.readFile(path.join(report.directory,'restore-verification.json')))
 await write(path.join(report.directory,'manifest.json'),metadata)
 const destination=path.join(checkpointRoot,report.checkpointId)
 try{await fs.access(destination);throw Error('checkpoint already exists; preserve history rather than overwrite '+destination)}catch(e){if(e.code!=='ENOENT')throw e}
 await fs.rename(report.directory,destination)
 return verifyServerCheckpointIntegrity(report.checkpointId)
}
export async function verifyServerCheckpointIntegrity(checkpointId,{expectedOrigin='',requireRestorable=true}={}){
 const directory=path.join(checkpointRoot,checkpointId),manifest=await read(path.join(directory,'manifest.json'))
 assert(manifest.contract===SERVER_CHECKPOINT_CONTRACT&&manifest.authority==='django','native checkpoint authority mismatch')
 assert(manifest.checkpointId===checkpointId&&manifest.businessStateRestoredFromBrowser===false,'checkpoint identity/business boundary mismatch')
 if(expectedOrigin)assert(manifest.origin===expectedOrigin,'checkpoint origin mismatch')
 if(requireRestorable)assert(manifest.restorable===true,'checkpoint fresh-context recovery not verified')
 assert((await sourceIdentity()).fingerprint===manifest.source.fingerprint,'checkpoint production source fingerprint stale')
 const binding=await serverBinding();assert(path.resolve(binding.database)===path.resolve(manifest.binding.database)&&binding.backendOrigin===manifest.binding.backendOrigin,'native checkpoint service/database mismatch')
 assert(hash(await fs.readFile(binding.preparationEvidence))===manifest.binding.preparationEvidenceSha256,'native source preparation evidence changed')
 assert(await integrity(directory)===manifest.integrityHash,'native checkpoint integrity mismatch')
 assert(hash(await fs.readFile(path.join(directory,'trace.zip')))===manifest.traceSha256,'native runner trace mismatch')
 assert(hash(await fs.readFile(path.join(directory,'restore-verification.json')))===manifest.restoreProofSha256,'native restore proof mismatch')
 const storage=await read(path.join(directory,'storage-state.json'))
 assert(storage.origins.every(x=>x.localStorage.every(y=>['pce_current_identity_v1','pce_account_shortcuts_v1'].includes(y.name))),'business storage restored by native checkpoint')
 return {directory,manifest,entities:await read(path.join(directory,'business-entities.json')),graph:await read(path.join(directory,'relationship-graph.json')),actualHash:manifest.integrityHash,missingFiles:[]}
}
export async function runServerCheckpointStage(stage){
 const b=await serverBinding();await seedAuthentication()
 const {runPlaywrightWithDevServer}=await import('../../scripts/pcePlaywrightRunner.mjs')
 const runId='native-'+stage+'-'+Date.now()+'-'+process.pid
 process.env.PCE_GOLDEN_RUN_ID=runId;process.env.PCE_GOLDEN_RUNNER_TRACE='1';process.env.PCE_API_PROXY_TARGET=b.backendOrigin
 const result=await runPlaywrightWithDevServer(['test','-c','playwright.runtime.config.js','tests/e2e/qualifiedInbound'+(stage==='ready'?'Ready':'Completion')+'GoldenFlow.spec.js'])
 if(result.stdout)process.stdout.write(result.stdout);if(result.stderr)process.stderr.write(result.stderr)
 assert(result.status===0,'native checkpoint stage failed; no checkpoint promoted')
 const report=await read(path.join(root,'test-results/purchase-payment-golden-flow/native-'+stage+'-report.json'))
 assert(report.runId===runId,'native checkpoint runner identity mismatch')
 await finalizeServerCheckpoint(report)
 console.log('NATIVE_CHECKPOINT_GENERATED',stage)
}
