import fs from 'node:fs/promises'
import path from 'node:path'
import {test,expect} from '@playwright/test'
import {verifyServerCheckpointIntegrity,restoreServerAuthentication,readServerSnapshot,assertServerStage} from '../helpers/serverGoldenCheckpoint.js'
test('native checkpoint restores only auth/context and rereads original authoritative facts',async({context,page,baseURL})=>{
 test.setTimeout(120000)
 const id=process.env.PCE_CHECKPOINT_ID,checkpoint=await verifyServerCheckpointIntegrity(id)
 await restoreServerAuthentication(context,page,baseURL,checkpoint.entities.readerId)
 const snapshot=await readServerSnapshot(page,checkpoint.entities)
 // Advancing the server never gets undone to make a historical ready checkpoint current again.
 assertServerStage(snapshot,checkpoint.entities,checkpoint.manifest.phase)
 const original=JSON.parse(await fs.readFile(path.join(checkpoint.directory,'application-state.json'),'utf8')).serverSnapshot
 const view=s=>({receipt:s.receipt,inspection:s.inspection,inbounds:s.inbounds,transactions:s.transactions,balances:s.balances})
 expect(view(snapshot)).toEqual(view(original))
 const report={checkpointId:id,authority:'django',passed:true,businessStateRestoredFromBrowser:false,freshAuthentication:true,currentServerReadback:snapshot,url:page.url(),uiVersion:'PCE-ENTERPRISE-UI-20261111-V3'}
 const dir=path.resolve('test-results/purchase-payment-golden-flow/native-restores');await fs.mkdir(dir,{recursive:true});await fs.writeFile(path.join(dir,id+'-'+Date.now()+'.json'),JSON.stringify(report,null,2))
})
