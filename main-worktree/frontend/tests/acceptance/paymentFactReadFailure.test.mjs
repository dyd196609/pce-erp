import assert from 'node:assert/strict'
import test from 'node:test'
import {createPaymentOrderDraftPageFacts} from '../../src/meta/runtime/paymentOrderDraftRuntime.js'
import {createFormalPaymentOrderPageFacts} from '../../src/meta/runtime/formalPaymentOrderRuntime.js'
import {createReadFailedFactLoad} from '../../src/meta/runtime/pceFactLoadContract.js'

for(const [name,create,url] of [
  ['draft',createPaymentOrderDraftPageFacts,'/api/finance/payment-order-drafts/'],
  ['formal',createFormalPaymentOrderPageFacts,'/api/finance/formal-payment-orders/'],
]) {
  for(const status of [401,500,0]) test(`${name}: HTTP ${status} failure stays unknown and cannot pass`,()=>{
    const failure=createReadFailedFactLoad({apiUrl:url,httpStatus:status,errorCode:'READ_REJECTED',errorMessage:'Read rejected',tenantId:'server-company',batchId:'server-batch'})
    const facts=create({data:{factLoadFacts:failure}})
    assert.equal(facts.factLoadStatus,'read_failed')
    assert.equal(facts.httpStatus,status)
    assert.equal(facts.resultCount,null)
    assert.equal(facts.passed,false)
    assert.equal(facts.strictServerFacts.passed,false)
    assert.ok(Object.values(facts.capacity).every(x=>x===null))
    assert.deepEqual(facts.rows,[])
    assert.equal(facts.currentObject,null)
    assert.deepEqual(facts.factLoadFacts,failure)
  })
  test(`${name}: loaded response still rejects missing authoritative counts`,()=>{
    const factLoadFacts={factLoadContractVersion:'PCE-FACT-LOAD-CONTRACT-V1.0',factLoadStatus:'loaded',apiUrl:url,httpStatus:200,errorCode:'',errorMessage:'',loadedAt:new Date().toISOString(),tenantId:'server-company',batchId:'server-batch'}
    assert.throws(()=>create({data:{factLoadFacts,results:[],capacity:{}}}),/server-derived non-negative integer/)
  })
  test(`${name}: authoritative empty success retains server zero counts`,()=>{
    const factLoadFacts={factLoadContractVersion:'PCE-FACT-LOAD-CONTRACT-V1.0',factLoadStatus:'empty_valid',apiUrl:url,httpStatus:200,errorCode:'',errorMessage:'',loadedAt:new Date().toISOString(),tenantId:'server-company',batchId:'server-batch'}
    const capacity={sourceRiskReviewCount:0,formalPaymentOrderCount:0,preparedCount:0,approvedCount:0,frozenCount:0,bankSendEligibleCount:0,blockedScenarioCount:0,nextStageConsumedCount:0,passed:true}
    const facts=create({data:{factLoadFacts,results:[],capacity}})
    assert.equal(facts.resultCount,0)
    assert.equal(facts.passed,true)
    assert.equal(facts.capacity.nextStageConsumedCount,0)
  })
}
