import test from 'node:test'
import assert from 'node:assert/strict'
import { evaluateScmPageGovernanceCompliance, SCM_PAGE_GOVERNANCE_TARGETS } from '../../src/meta/process/scmPageGovernanceComplianceV114281031.js'

const completeEvidence=Object.fromEntries(SCM_PAGE_GOVERNANCE_TARGETS.map(page=>[page.pageCode,{
  identity:true,pageTemplate:true,businessRegions:true,listTemplate:true,actionTemplate:true,stateTemplate:true,
  uniqueMapping:true,routeMapping:true,acceptanceRecord:true,
}]))

test('治理证据完整时九页通过',()=>assert.equal(evaluateScmPageGovernanceCompliance(completeEvidence).result,'PASS'))
test('任一页面证据缺失时必须失败，禁止自动 PASS',()=>{
  const broken={...completeEvidence,'supplier-quote-workbench':{...completeEvidence['supplier-quote-workbench'],listTemplate:false}}
  const result=evaluateScmPageGovernanceCompliance(broken)
  assert.equal(result.result,'FAIL')
  assert.equal(result.pageResults.find(page=>page.pageCode==='supplier-quote-workbench').result,'FAIL')
})
