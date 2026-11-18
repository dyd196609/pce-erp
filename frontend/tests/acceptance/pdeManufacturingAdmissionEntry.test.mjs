import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { businessProcessRegistry, listBusinessProcesses } from '../../src/meta/process/businessProcessRegistry.js'
import { PDE_MAIN_FLOW, findPdePageDefinition } from '../../src/meta/pages/pdePageDefinitions.js'
import { resolveBusinessName, validateBusinessNameRegistry } from '../../src/meta/governance/businessNameRegistry.js'
import { pdeWorkbenchEntries } from '../../src/meta/process/pdeWorkbenchRegistry.js'
import { buildPageAcceptanceRegistry } from '../../src/meta/runtime/pcePageAcceptanceRegistry.js'

const nodes = listBusinessProcesses().find(p => p.moduleCode === 'PDE').nodes
assert.equal(nodes[14].nodeName, '工程输出确认')
assert.equal(nodes[14].nodeCode, 'manufacturing-output-confirmation')
assert.equal(nodes[14].pageCode, 'pde-manufacturing-outputs')
assert.equal(nodes[14].pageUrl, '/pde/manufacturing-outputs')
assert.equal(nodes[15].nodeName, '制造承接确认')
assert.equal(nodes[15].pageUrl, '/pde/manufacturing-admissions')
assert.equal(nodes[15].workflowBinding.processDefinitionId, 10)
assert.equal(nodes[15].workflowBinding.workflowNodeId, 48)
assert.equal(nodes[16].nodeName, '生产需求准入')
const mrp = nodes.find(n => n.nodeCode === 'mrp-input-preparation')
assert.equal(mrp.sequence, 18)
assert.equal(mrp.nodeName, 'MRP输入准备')
assert.equal(mrp.pageUrl, '/pde/mrp-input-preparation')
assert.equal(pdeWorkbenchEntries.find(n => n.code === mrp.nodeCode).route, mrp.pageUrl)
assert.deepEqual(PDE_MAIN_FLOW.slice(14), ['工程输出确认', '制造承接确认', '生产需求准入', 'MRP输入准备'])
assert.deepEqual(nodes.slice(10, 14).map(n => n.nodeCode), ['engineering-data-release', 'engineering-change-ecn', 'trial-production-validation', 'mass-production-introduction'])
assert.equal(validateBusinessNameRegistry().result, 'PASS')
for (const kind of ['manufacturingAdmissions', 'mrpInputPreparation']) {
  const page = findPdePageDefinition(kind)
  assert.equal(resolveBusinessName({pageCode: page.pageCode}).pageName, page.title)
  assert.ok(buildPageAcceptanceRegistry().some(c => c.pageCode === page.pageCode))
  assert.ok(page.filterSchema.every(f => f.filterType))
}
const router = readFileSync(new URL('../../src/router/index.js', import.meta.url), 'utf8')
assert.ok(router.includes("wrapPdeGovernedPage('manufacturingAdmissions')"))
assert.ok(router.includes("wrapPdeGovernedPage('mrpInputPreparation')"))
const unchangedOtherModules = businessProcessRegistry.filter(p => p.moduleCode !== 'PDE').map(p => p.processCode)
assert.deepEqual(listBusinessProcesses().filter(p => p.moduleCode !== 'PDE').map(p => p.processCode), unchangedOtherModules)
// An old saved directory must not shadow the official correction. No storage writes.
let writes = 0
globalThis.localStorage = {getItem: () => JSON.stringify([{processCode: 'PDE_PRODUCT_ENGINEERING', moduleCode: 'PDE', nodes: [nodes[14], {...mrp, sequence:16, pageUrl:'/pde/manufacturing-outputs'}, {nodeCode:'custom-preserved', sequence:99}]}]), setItem: () => writes++}
const replay = await import('../../src/meta/process/businessProcessRegistry.js?old-directory')
const upgraded = replay.listBusinessProcesses()[0].nodes
assert.equal(upgraded.find(n => n.sequence === 16).nodeCode, 'manufacturing-admission-confirmation')
assert.ok(upgraded.some(n => n.nodeCode === 'custom-preserved'))
assert.equal(writes, 0)
delete globalThis.localStorage
console.log('PDE manufacturing admission entry mapping: PASS')
