import fs from 'node:fs/promises'
import {serverBinding,sourceIdentity} from '../tests/helpers/serverGoldenCheckpoint.js'
const assert=(ok,message)=>{if(!ok)throw Error(message)}
const binding=await serverBinding(),source=await sourceIdentity()
const helper=await fs.readFile('tests/helpers/serverGoldenCheckpoint.js','utf8')
for(const suffix of ['Ready','Completion']){
 const spec=await fs.readFile(`tests/e2e/qualifiedInbound${suffix}GoldenFlow.spec.js`,'utf8')
 for(const token of ['restoreServerAuthentication','readServerSnapshot','assertServerStage','browser.newContext','captureServerCheckpoint','serverReadbackMatched','apiProxyTarget'])assert(spec.includes(token),`${suffix}: native proof contract missing ${token}`)
 assert(!/localStorage\.(setItem|clear)|from .*([sS]tore|businessFlowTransaction)|context\.tracing\.(start|stop)/.test(spec),`${suffix}: browser business ledger/manual trace forbidden`)
}
for(const token of ['/api/auth/login/','/api/procurement/formal-purchase-receipt-facts/','/api/procurement/formal-quality-facts/','/api/procurement/formal-inventory-facts/','sourceInboundId===inbound.id','preparationEvidenceSha256','traceSha256','businessStateRestoredFromBrowser:false'])assert(helper.includes(token),'native authority/trace/source guard missing '+token)
const complete=await fs.readFile('tests/e2e/qualifiedInboundCompletionGoldenFlow.spec.js','utf8')
for(const token of ['scm-runtime-actions/confirm-inbound/','warehouseActorId','INBOUND_QUANTITY_EXCEEDED','expect(view(unchanged)).toEqual(view(snapshot))'])assert(complete.includes(token),'native completion guard missing '+token)
console.log(JSON.stringify({contract:'PCE-DJANGO-GOLDEN-CHECKPOINT-V1',sourceFingerprint:source.fingerprint,database:binding.database,backendOrigin:binding.backendOrigin,legacyLedgerRestored:false,guard:'native authority, source relations, duplicate rejection, fresh authenticated recovery and owned trace required'}))
