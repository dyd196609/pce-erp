import test from 'node:test'
import assert from 'node:assert/strict'
import {MES_TEST_NODES,mesReadContext,mesNodeUrl} from './mesTestProcessNavigation.js'
const fg=MES_TEST_NODES[5]
test('selected transfer retains typed transfer and real parent work order in current/end links',()=>{const c=mesReadContext({selectedTransfer:{id:2,workOrderId:3,workOrderNo:'NEW'}});assert.equal(c.transferId,2);assert.equal(c.workOrderId,3);assert.equal(mesNodeUrl(fg,c),'/planning/finished-goods-handovers?transferId=2&workOrderId=3')})
test('old workOrderId 2 never becomes transferId 2',()=>assert.equal(mesNodeUrl(fg,{workOrderId:2}),'/planning/finished-goods-handovers?workOrderId=2'))
test('unselected directory never defaults to a business object',()=>assert.equal(mesNodeUrl(fg,mesReadContext({workOrderOptions:[{id:2},{id:3}]})),'/planning/finished-goods-handovers'))
test('selected transfer id does not leak into review task locator',()=>{const u=mesNodeUrl(MES_TEST_NODES[4],{transferId:2,workOrderId:3,taskId:29});assert.equal(u,'/planning/operation-completions?taskId=29&workOrderId=3')})
