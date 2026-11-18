import assert from 'node:assert/strict'
import { createGovernedHandoverController, createOperationHandoverState } from '../src/meta/runtime/operationHandover.js'
import { resolvePceOperationRangeReceiptAction } from '../src/meta/runtime/pceBusinessActionRegistry.js'
import { OPERATION_HANDOVER_ACTION_CONTRACTS, OPERATION_RANGE_RECEIVE_API } from '../src/meta/runtime/operationHandoverContract.js'
import { createHandoverIntentJournal } from '../src/meta/runtime/operationHandoverIntent.js'
const values = new Map(), storage = { getItem: k => values.get(k) ?? null, setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) }
const action = { ...OPERATION_HANDOVER_ACTION_CONTRACTS.receive, apiPath: OPERATION_RANGE_RECEIVE_API,
  requestObjectId: 99, sourceTaskId: 4, targetTaskId: 5, enabled: true, disabledReason: '' }
const facts = { selectedTask: { taskId: 4, workOrderId: 2 }, rangeReleases: [{ id: 99, receiptAction: action }] }
assert.equal(resolvePceOperationRangeReceiptAction(facts,99).objectId,99)
assert.throws(() => resolvePceOperationRangeReceiptAction({ ...facts, rangeReleases: [{ id: 99, receiptAction: {...action,requestObjectId:98} }] },99))
const state = createOperationHandoverState();state.params={taskId:4};let calls=0, verified=false, storedIntent
const controller=createGovernedHandoverController({state,identity:()=>({userId:38,companyId:1}),owner:()=> 'actor38-db1',
  apiUrl:'/api/planning/operation-handovers/',journal:createHandoverIntentJournal(storage),
  resolveAction:(current,key)=>{assert.equal(key,'range.receive');return resolvePceOperationRangeReceiptAction(current,99)},
  validator:r=>({facts:r.facts}),api:{
    read:async params=>({facts:{...facts,...(params.recoveryAction?{resultRecovery:{status:verified?'verified':'unknown',actionCode:params.recoveryAction,
      requestHash:params.requestHash,requestKeyHash:params.requestKeyHash,objectId:99,resultObjectId:100,proofReference:verified?'OperationCustodyEvent:100':null}}:{})}}),
    execute:async (command,payload)=>{calls++;assert.equal(command.apiPath,OPERATION_RANGE_RECEIVE_API);assert.equal(payload.releaseEventId,99)
      storedIntent=JSON.parse([...values.values()][0]);assert.equal(storedIntent.handoverId,null);assert.equal(storedIntent.objectId,99)
      assert.ok(!Object.hasOwn(storedIntent,'reason')&&!Object.hasOwn(storedIntent,'quantity')&&!Object.hasOwn(storedIntent,'idempotencyKey'))
      return {transportAcknowledged:true}}
  }})
await controller.load()
await controller.execute('range.receive',{taskId:4,targetTaskId:5,releaseEventId:99,reason:'明确实际收讫测试'})
assert.equal(calls,1);assert.ok(state.pendingIntent);assert.equal(state.writeState,'readback_pending')
await controller.execute('range.receive',{taskId:4,targetTaskId:5,releaseEventId:99,reason:'不能重发'})
assert.equal(calls,1)
verified=true;await controller.load();assert.equal(state.pendingIntent,null);assert.equal(state.verifiedRecovery.objectId,99);assert.equal(values.size,0)
console.log(JSON.stringify({result:'PASS',sameReceivePermission:true,exactReleaseBinding:true,unknownResultBlocksReplay:true,
  independentReadbackRequired:true,noRawPayloadOrKeyPersisted:true,newPermissionStructure:false,executeCalls:calls}))
