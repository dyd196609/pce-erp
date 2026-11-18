import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {verifyServerCheckpointIntegrity,assertServerStage} from './serverGoldenCheckpoint.js'
const ready=await verifyServerCheckpointIntegrity('qualified_inbound_ready')
const completed=await verifyServerCheckpointIntegrity('qualified_inbound_completed')
const read=async c=>JSON.parse(await fs.readFile(path.join(c.directory,'application-state.json'),'utf8')).serverSnapshot
const before=await read(ready),after=await read(completed)
test('real native ready and completed source evidence passes authority/integrity checks',()=>{assertServerStage(before,ready.entities,'ready');assertServerStage(after,completed.entities,'completed')})
test('wrong source order relation rejected',()=>{const wrong=structuredClone(after);wrong.receipt.sourceOrderId=-1;assert.throws(()=>assertServerStage(wrong,completed.entities,'completed'),/relation mismatch/)})
test('missing native inbound rejected',()=>{const wrong=structuredClone(after);wrong.inbounds=[];assert.throws(()=>assertServerStage(wrong,completed.entities,'completed'),/cardinality mismatch/)})
test('wrong downstream inventory source rejected',()=>{const wrong=structuredClone(after);wrong.transactions[0].sourceInboundId=-1;assert.throws(()=>assertServerStage(wrong,completed.entities,'completed'),/source relation mismatch/)})
test('wrong quantity rejected',()=>{const wrong=structuredClone(after);wrong.balances[0].quantity='0';assert.throws(()=>assertServerStage(wrong,completed.entities,'completed'),/balance mismatch/)})
test('posted state cannot masquerade as ready',()=>{assert.throws(()=>assertServerStage(after,completed.entities,'ready'),/already posted/)})
test('wrong browser origin rejected',async()=>{await assert.rejects(()=>verifyServerCheckpointIntegrity('qualified_inbound_completed',{expectedOrigin:'http://127.0.0.1:1'}),/origin mismatch/)})
