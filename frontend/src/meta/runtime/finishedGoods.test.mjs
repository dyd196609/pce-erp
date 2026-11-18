import fs from 'node:fs'
import assert from 'node:assert/strict'
import { validateFinishedGoods,createFinishedGoodsController,createFinishedGoodsState } from './finishedGoods.js'
import { createHandoverIntentJournal } from './operationHandoverIntent.js'
const evidence=new URL('./fixtures/',import.meta.url)
const source=JSON.parse(fs.readFileSync(new URL('FRONTEND_SOURCE_ENVELOPE.json',evidence),'utf8'))
const received=JSON.parse(fs.readFileSync(new URL('FRONTEND_RECEIVED_ENVELOPE.json',evidence),'utf8'))
const facts=x=>x.data.finishedGoodsFacts
for(const response of [source,received]){
 const f=facts(response);const result=validateFinishedGoods(response,{actorId:f.currentActorEvidence.userId,companyId:f.companyId})
 assert.equal(result.facts,f);const corrupt=structuredClone(response);corrupt.data.strictFacts.finishedGoodsFacts.companyId+=1
 assert.throws(()=>validateFinishedGoods(corrupt,{actorId:f.currentActorEvidence.userId,companyId:f.companyId}))
}
const memory=new Map(),storage={getItem:k=>memory.get(k)??null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)},journal=createHandoverIntentJournal(storage)
const state=createFinishedGoodsState(),f=facts(received),who={userId:f.currentActorEvidence.userId,companyId:f.companyId}
let posts=0
const fake=structuredClone(received);for(const s of ['finishedGoodsFacts'])fake.data[s].availableActions.receive.enabled=true
// Keep all five surfaces identical for this transport-only scenario.
for(const key of ['apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'])fake.data[key].finishedGoodsFacts=structuredClone(fake.data.finishedGoodsFacts)
const controller=createFinishedGoodsController({state,identity:()=>who,owner:()=>JSON.stringify(who),journal,api:{read:async()=>fake,execute:async()=>{posts++;throw new Error('NETWORK_RESULT_UNKNOWN')}}})
await controller.select({transferId:f.selectedTransfer.id})
assert.equal(controller.submission('receive').enabled,true)
await controller.execute('receive',{expectedVersion:f.selectedTransfer.version,expectedSourceSnapshotHash:f.selectedTransfer.sourceSnapshotHash,reason:'CODEX transport uncertainty test'})
assert.equal(posts,1);assert.ok(state.pendingIntent);assert.equal(controller.submission('receive').enabled,false)
await controller.execute('receive',{reason:'must never submit twice'})
assert.equal(posts,1)
const saved=[...memory.values()].join('');assert.ok(!saved.includes('transport uncertainty test'));assert.ok(!saved.includes('idempotencyKey'))
// A legacy non-terminal journal entry stays readable after adding transfer locators.
const entry={domain:'handover',actorId:7,companyId:1,actionKey:'dispatch',actionCode:'production.operation.handover.dispatch',objectId:1,taskId:1,workOrderId:1,handoverId:1,outputId:null,exceptionId:null,custodyWorkCenterId:null,scopeId:null,workCenterId:null,expectedVersion:1,generationId:null,requestHash:'a'.repeat(64),requestKeyHash:'b'.repeat(64)}
storage.setItem('pce_operation_handover_intent_v1:1:7:handover',JSON.stringify(entry));assert.equal(journal.read(7,1,'handover').transferId,null)
console.log(JSON.stringify({passed:true,serverEnvelopeContracts:2,surfaceMismatchRejected:true,unknownResultNoDuplicatePost:true,payloadNotPersisted:true,legacyIntentCompatible:true}))
