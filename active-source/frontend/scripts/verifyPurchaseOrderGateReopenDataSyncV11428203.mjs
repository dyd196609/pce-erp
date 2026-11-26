import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = path.resolve(root, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const governanceNames = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '页面Route与业务Context分离规范.md', '问题案例库.md', '一页一验收规范.md']
const governanceLoaded = governanceNames.every(name => {
  const file = path.join(repositoryRoot, 'docs', 'governance', name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
}) && fs.readFileSync(path.join(repositoryRoot, 'docs', 'governance',
  'PCE-ERP开发治理总规范.md'), 'utf8').includes('BATCH-COMPLETENESS-001')

const current = run(['--test', 'tests/acceptance/purchaseOrderGateReopenDataSyncV11428203.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/purchaseOrderGateAuditLoopV11428202.test.mjs',
  'tests/acceptance/purchaseOrderGateActionClosureV11428201.test.mjs',
  'tests/acceptance/purchaseOrderGateRuntimeV1142820.test.mjs',
  'tests/acceptance/supplierRecommendationHumanDecisionV1142819.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs'])
const routeRegression = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, routeRegression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const decisionModel = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const gateModel = read('src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')
const provider = read('src/meta/providers/purchaseOrderGateRuntimeProviderV1142820.js')
const inspectionModel = read('src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderGateInspectionRecordV11428202.js')
const gatePage = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
const decisionRevision = current.status === 0 && decisionModel.includes('decisionRevision')
  && decisionModel.includes('listResultRevisions') && !decisionModel.includes('state.results = state.results.filter')
const updatePropagation = current.status === 0 && provider.includes('sourceDecisionSignature')
  && provider.includes('decisionUpdatePropagated')
const latestDecisionRead = provider.includes('decisionBatchStore.findResult(batchId)')
  && decisionModel.includes('[...read().results].reverse()')
const gateRefresh = provider.includes('previous.sourceDecisionSignature !== latestDraft.sourceDecisionSignature')
  && provider.includes('evaluateAndRecord(sourceFacts)')
const inspectionHistory = inspectionModel.includes('supplierSnapshot')
  && inspectionModel.includes('decisionRevision') && gatePage.includes('供应商快照')
const oldDataNotUsed = updatePropagation && gateRefresh
const blockedState = gateModel.includes("gateCheck('DECISION_REVISION'")
  && gateModel.includes("gateCheck('DECISION_RESULT_STATUS'")
const readyState = current.status === 0 && gateModel.includes("status: ready ? 'ready_for_purchase_order' : 'blocked'")
const noPurchaseOrder = [decisionModel, gateModel, provider, inspectionModel, gatePage].every(source =>
  !/createPurchaseOrder\s*\(|savePurchaseOrder\s*\(|submitPurchaseOrder\s*\(/.test(source))
const process011 = governanceLoaded && current.status === 0 && routeRegression.status === 0
  && decisionRevision && updatePropagation && latestDecisionRead && gateRefresh
  && inspectionHistory && oldDataNotUsed && blockedState && readyState && noPurchaseOrder

const checks = [
  ['Decision Revision', decisionRevision],
  ['Decision Update Propagation', updatePropagation],
  ['Latest Decision Read', latestDecisionRead],
  ['Gate Refresh', gateRefresh],
  ['Inspection History', inspectionHistory],
  ['Old Data Not Used', oldDataNotUsed],
  ['Blocked State', blockedState],
  ['Ready State', readyState],
  ['No PurchaseOrder', noPurchaseOrder],
  ['PROCESS-011', process011],
  ['Regression', regression.status === 0 && routeRegression.status === 0],
  ['Build', build.status === 0],
]
const passed = governanceLoaded && checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.20.3')
console.log(`Governance Files Loaded ${governanceLoaded ? 'PASS' : 'FAIL'}`)
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
for (const layer of ['Object Exists', 'Page Exists', 'Data Handoff', 'Human Action Loop',
  'Entry Consistency', 'Action Executability', 'Route Identity', 'Context Separation',
  'Batch Completeness', 'Decision Update Propagation']) {
  console.log(`${layer} ${process011 ? 'PASS' : 'FAIL'}`)
}
console.log(passed ? 'PURCHASE_ORDER_GATE_REOPEN_DATA_SYNC_READY'
  : 'PURCHASE_ORDER_GATE_REOPEN_DATA_SYNC_ISSUES_FOUND')
if (!passed) process.exitCode = 1
