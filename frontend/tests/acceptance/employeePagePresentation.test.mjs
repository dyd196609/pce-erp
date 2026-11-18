import test from 'node:test'
import assert from 'node:assert/strict'
import {learningPreference,handoverListQuery,readableCondition} from '../../src/meta/runtime/employeePagePresentation.js'
test('learning is closed by default and remembers both choices per person/page',()=>{const data=new Map(),storage={getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)};let identity={companyId:1,userId:2};const p=learningPreference('handover',()=>identity,storage);assert.equal(p.read(),false);p.write(true);assert.equal(p.read(),true);identity={companyId:1,userId:3};assert.equal(p.read(),false);identity={companyId:1,userId:2};assert.equal(learningPreference('report',()=>identity,storage).read(),false);p.write(false);assert.equal(p.read(),false)})
test('storage failure never blocks the page',()=>{const p=learningPreference('handover',()=>({companyId:1,userId:2}),{getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}});assert.equal(p.read(),false);assert.doesNotThrow(()=>p.write(true))})
test('direct detail return retains task/work order scope and selects list',()=>{assert.deepEqual(handoverListQuery({taskId:'6',workOrderId:'1',direction:'incoming',handoverId:'1',businessNo:'JJ1',outputId:'2'}),{taskId:'6',workOrderId:'1',direction:'incoming',screen:'list'})})
test('UI retains confirmed server explanation and hides raw internal marker only',()=>{assert.equal(readableCondition('当前无权限（NO_PERMISSION）'), '当前无权限（（标识见技术详情））');assert.equal(readableCondition('请先重新读取正式数量。'),'请先重新读取正式数量。')})

import {resolveOperationHandoverPageState,OPERATION_HANDOVER_ROUTE_META} from '../../src/meta/runtime/operationHandoverContract.js'
test('actual return query passes the existing page identity contract and keeps view guard',()=>{
 const route={path:'/planning/operation-handovers',name:'OperationHandover',meta:OPERATION_HANDOVER_ROUTE_META,query:handoverListQuery({taskId:'41',handoverId:'8',view:'maintain'})}
 assert.equal(resolveOperationHandoverPageState(route).mode,'maintain')
 assert.equal(route.query.screen,'list');assert.equal(route.query.handoverId,undefined)
 assert.throws(()=>resolveOperationHandoverPageState({...route,query:{...route.query,view:'list'}}),/mode differs/)
 assert.throws(()=>resolveOperationHandoverPageState({...route,query:{...route.query,screen:'unknown'}}),/screen differs/)
})
