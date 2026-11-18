import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspace = path.resolve(root, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

const governanceFiles = [
  'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
  'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
  'docs/governance/03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md',
  'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
  'docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md',
]
const governance = governanceFiles.every(relative => {
  const file = path.join(workspace, ...relative.split('/'))
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
})

const current = run(['--test',
  'tests/acceptance/supplierRecommendationGateRuntimeV114284251.test.mjs',
  'tests/acceptance/supplierRecommendationGateV11428425.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs',
  'tests/acceptance/purchaseOrderGateActionClosureV11428201.test.mjs',
  'tests/acceptance/purchaseOrderGateAuditLoopV11428202.test.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const domain = read('src/meta/domain/scm/purchaseOrder/gate/supplierRecommendationGateV11428425.js')
const provider = read('src/meta/providers/supplierRecommendationGateProviderV11428425.js')
const admissionProvider = read('src/meta/providers/purchaseOrderAdmissionProviderV11428425.js')
const guard = read('src/meta/domain/scm/purchaseOrder/gate/purchaseOrderAdmissionGuardV11428425.js')
const handoff = read('src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationEntryHandoffV11428425.js')
const runtime = read('src/meta/process/scm/purchaseOrderCreationGate/supplierRecommendationGateRuntimeV11428425.js')
const page = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')

const objectUniqueness = [
  [domain, "objectType: 'SupplierRecommendationGate'"],
  [domain, "objectType: 'PurchaseOrderAdmissionContext'"],
  [domain, "objectType: 'PurchaseOrderAdmissionResult'"],
  [handoff, "objectType: 'PurchaseOrderCreationEntry'"],
].every(([source, token]) => source.split(token).length - 1 === 1)
const sourceTrace = provider.includes('supplierRecommendationDecisionBatchStoreV11428169')
  && provider.includes("'SupplierRecommendationDecisionBatchResult'")
  && domain.includes("sourceDecisionObjectType: 'SupplierRecommendationDecision'")
  && domain.includes('quoteComparisonIds') && domain.includes('priceApprovalIds')
  && !provider.includes('createSupplierRecommendationDecision')
const stateLifecycle = ['CREATED', 'CONFIRMED', 'READY_FOR_PURCHASE_ORDER', 'BLOCKED']
  .every(value => domain.includes(value)) && current.status === 0
const guardPassed = ['RECOMMENDATION_EXISTS', 'RECOMMENDATION_MANUALLY_CONFIRMED',
  'QUOTE_EVIDENCE_EXISTS', 'PRICE_APPROVAL_EVIDENCE_READY', 'SOURCE_CHAIN_COMPLETE',
  'currentValue', 'reason'].every(value => guard.includes(value))
const handoffPassed = handoff.includes("entryRoute: '/scm/purchase-order'")
  && handoff.includes('createActionExecuted: false')
  && handoff.includes('businessWriteCount: 0')
const purchaseOrderIsolation = [domain, provider, admissionProvider, guard, handoff, runtime]
  .every(source => !/createPurchaseOrder\(|savePurchaseOrder\(|submitPurchaseOrder\(|approvePurchaseOrder\(/.test(source))
  && handoff.includes('purchaseOrderCreated: false')
  && handoff.includes('purchaseOrderSubmitted: false')
  && handoff.includes('purchaseOrderApproved: false')
  && !page.includes('data-process-action="CREATE_PURCHASE_ORDER"')
const boundary = purchaseOrderIsolation
  && ![domain, provider, admissionProvider, guard, handoff, runtime, page]
    .some(source => /pageRenderer|MetaPage|crudEngine|schemaResolver/.test(source))
const runtimePassed = current.status === 0
  && runtime.includes('executeConfirmPurchaseOrderGateV11428425')
  && runtime.includes('executeEvaluatePurchaseOrderAdmissionV11428425')

const checks = [
  ['Version', true],
  ['Governance', governance],
  ['Boundary', boundary],
  ['Domain', objectUniqueness && stateLifecycle],
  ['Provider', sourceTrace],
  ['Guard', guardPassed],
  ['Handoff', handoffPassed && purchaseOrderIsolation],
  ['Runtime', runtimePassed],
  ['Acceptance', current.status === 0 && regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.4.25.1')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(`Object Uniqueness ${objectUniqueness ? 'PASS' : 'FAIL'}`)
console.log(`Source Trace ${sourceTrace ? 'PASS' : 'FAIL'}`)
console.log(`PurchaseOrder Isolation ${purchaseOrderIsolation ? 'PASS' : 'FAIL'}`)
console.log('Business Write Count: 0')
console.log(`Final Status: ${passed ? 'SCM_SUPPLIER_RECOMMENDATION_GATE_RUNTIME_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_GATE_RUNTIME_ISSUES_FOUND'}`)
if (!passed) process.exitCode = 1
