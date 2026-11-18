import test from 'node:test'
import assert from 'node:assert/strict'

const storage=new Map()
globalThis.localStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,String(value)),removeItem:key=>storage.delete(key)}

const names=await import('../../src/meta/governance/businessNameRegistry.js')
const processRegistry=await import('../../src/meta/process/businessProcessRegistry.js')
const identityRegistry=await import('../../src/meta/schema/scm/scmPageIdentityRegistry.js')
const standardPages=await import('../../src/meta/schema/scm/scmStandardPageContract.js')
const titles=await import('../../src/meta/runtime/pageTitleManager.js')
const configStore=await import('../../src/meta/workflow/approvalFlowConfigStore.js')
const approvalBinding=await import('../../src/meta/workflow/approvalRuntimeBinding.js')

test('NAME-GOV-001 keeps process, page identity, page contract and browser title aligned',()=>{
  assert.equal(names.validateBusinessNameRegistry().result,'PASS')
  const nodes=processRegistry.listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT').slice(0,13)
  for(const node of nodes){const name=names.resolveBusinessName(node.nodeCode);assert.ok(name,node.nodeCode);assert.equal(node.nodeName,name.processName)
    const identity=identityRegistry.resolveScmPageIdentity(name.route);if(identity)assert.equal(identity.pageName,name.pageTitle)
    const contract=standardPages.resolveScmStandardPageContract(name.pageCode);if(contract)assert.equal(contract.pageName,name.pageTitle)
    assert.equal(titles.buildPageDocumentTitle(name.route),name.pageTitle)}
  assert.equal(names.resolveBusinessName('quality-inspection').displayName,'来料检验')
  assert.equal(names.resolveBusinessName('warehouse-receipt').displayName,'入库')
})

for(const gateCount of [1,2,3])test(`APPROVAL-RUNTIME-001 binds ${gateCount}-gate configuration to policy, tasks, result and writeback`,()=>{
  configStore.saveApprovalFlowConfig('purchaseRequest',{enabled:true,stepCount:gateCount})
  let binding=approvalBinding.createBoundApprovalRuntime({moduleName:'purchaseRequest',businessObjectId:`PR-BIND-${gateCount}`,submittedBy:'requester'})
  assert.equal(binding.configuration.gateCount,gateCount);assert.equal(binding.policy.gateCount,gateCount);assert.equal(binding.tasks.length,gateCount)
  for(let level=1;level<=gateCount;level+=1)binding=approvalBinding.executeBoundApprovalTask(binding,{actorId:`approver-${level}`,actorRole:binding.policy.gates[level-1].approverRole})
  assert.equal(binding.result.code,'approved')
  const written=approvalBinding.writeBoundApprovalResult(binding,{requestNo:`PR-BIND-${gateCount}`,approvalStatus:'submitted'})
  assert.equal(written.businessObject.approvalStatus,'approved');assert.equal(written.writeback.written,true)
})

test('approval business node is isolated from approval configuration page',()=>{
  const approvalNode=processRegistry.listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT').find(node=>node.nodeCode==='purchase-approval')
  assert.equal(approvalNode.pageUrl,'/scm/purchase-approvals')
  assert.notEqual(approvalNode.pageUrl,'/admin/approval-flow-config')
  assert.equal(identityRegistry.resolveScmPageIdentity(approvalNode.pageUrl).businessObject,'PurchaseRequestApproval')
})
