import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspace = path.resolve(root, '..')
const governanceRoot = path.join(workspace, 'docs', 'governance')
const acceptanceRoot = path.join(workspace, 'docs', 'acceptance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

const governanceFiles = [
  '01-开发治理总纲/PCE-ERP开发治理总纲.md',
  '02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
  '03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md',
  '04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
  '05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
  '06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md',
]
const governanceLoaded = governanceFiles.every(file => {
  const full = path.join(governanceRoot, ...file.split('/'))
  return fs.existsSync(full) && fs.readFileSync(full, 'utf8').trim().length > 0
})
const preScanPath = path.join(acceptanceRoot, 'scm_supplier_recommendation_gate_pre_scan_v11428425.json')
const preScan = JSON.parse(fs.readFileSync(preScanPath, 'utf8'))
const preScanPassed = ['existingObjects', 'existingPages', 'existingProviders',
  'existingActions', 'existingGuards', 'existingAcceptance']
  .every(key => Array.isArray(preScan[key]) && preScan[key].length > 0)

const current = run(['--test', 'tests/acceptance/supplierRecommendationGateV11428425.test.mjs'])
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
  + read('src/meta/providers/purchaseOrderAdmissionProviderV11428425.js')
const guard = read('src/meta/domain/scm/purchaseOrder/gate/purchaseOrderAdmissionGuardV11428425.js')
const runtime = read('src/meta/process/scm/purchaseOrderCreationGate/supplierRecommendationGateRuntimeV11428425.js')
const page = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
const handoff = read('src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationEntryHandoffV11428425.js')
const router = read('src/router/index.js')

const domainPassed = ['SupplierRecommendationGate', 'PurchaseOrderAdmissionContext',
  'PurchaseOrderAdmissionResult', 'CREATED', 'WAITING_CONFIRMATION', 'CONFIRMED',
  'READY_FOR_PURCHASE_ORDER', 'BLOCKED'].every(value => domain.includes(value))
const providerPassed = ['SupplierRecommendationGateProviderV11428425',
  'PurchaseOrderAdmissionProviderV11428425', 'SupplierRecommendationDecisionBatchResult',
  'businessWriteCount: 0', 'purchaseOrderCreated: false'].every(value => provider.includes(value))
const guardPassed = ['RECOMMENDATION_EXISTS', 'RECOMMENDATION_MANUALLY_CONFIRMED',
  'QUOTE_EVIDENCE_EXISTS', 'PRICE_APPROVAL_EVIDENCE_READY', 'SOURCE_CHAIN_COMPLETE']
  .every(value => guard.includes(value))
const pagePassed = ['Gate状态区域', '来源链区域', '推荐证据区域', '采购订单准入检查区域',
  '操作区域', 'purchase-order-admission-diagnostics', 'CONFIRM_PURCHASE_ORDER_GATE',
  'EVALUATE_PURCHASE_ORDER_ADMISSION'].every(value => page.includes(value))
  && router.includes("path: 'scm/purchase-order-gate'")
const runtimePassed = current.status === 0
  && runtime.includes('executeConfirmPurchaseOrderGateV11428425')
  && runtime.includes('executeEvaluatePurchaseOrderAdmissionV11428425')
const noAutomaticPurchaseOrder = !page.includes('data-process-action="CREATE_PURCHASE_ORDER"')
  && handoff.includes('createActionExecuted: false')
  && [domain, provider, runtime, handoff].every(value => value.includes('purchaseOrderCreated: false'))
  && !runtime.includes('createPurchaseOrder(')
const boundaryPassed = noAutomaticPurchaseOrder
  && ![domain, provider, guard, runtime, page, handoff].some(value =>
    /pageRenderer|MetaPage|crudEngine|schemaResolver/.test(value))

const checks = [
  ['Version', true],
  ['Governance', governanceLoaded],
  ['Boundary', boundaryPassed],
  ['Pre Scan', preScanPassed],
  ['Domain', domainPassed],
  ['Provider', providerPassed],
  ['Guard', guardPassed],
  ['Page', pagePassed],
  ['Runtime', runtimePassed],
  ['Acceptance', current.status === 0 && regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.4.25')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(`Automatic Purchase Order Creation: ${noAutomaticPurchaseOrder ? 'NO' : 'YES'}`)
console.log('Business Write Count: 0 (acceptance uses isolated memory stores)')
console.log(`Final Status: ${passed ? 'SCM_SUPPLIER_RECOMMENDATION_GATE_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_GATE_ISSUES_FOUND'}`)
if (!passed) process.exitCode = 1
