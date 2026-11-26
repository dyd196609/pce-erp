import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createPurchaseOrderCreationGateDecisionV1142820,
  evaluatePurchaseOrderCreationGateDecisionV1142820,
  HistoricalPurchaseOrderIsolationCheck } from '../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const makeItem = (code, confirmed = true) => ({ decisionItemId: `SRDI-${code}`,
  materialCode: code, materialName: `物料${code}`,
  selectedSupplierCode: confirmed ? 'SUP-201' : '',
  selectedSupplierName: confirmed ? '当前推荐供应商' : '',
  selectionReason: confirmed ? '采购人员基于当前批次报价事实人工确认。' : '',
  reviewStatus: confirmed ? 'confirmed' : 'manual_review',
  reviewer: confirmed ? '采购员201' : '',
  reviewedAt: confirmed ? '2026-08-06T20:10:00.000Z' : '',
  status: confirmed ? 'confirmed' : 'selected',
  supplierCandidates: [{ supplierCode: 'SUP-201', supplierName: '当前推荐供应商', quotePrice: 128 }],
  priceEvidence: [{ supplierCode: 'SUP-201', currentPrice: 128,
    evidenceSource: 'QuoteComparison' }], quoteComparisonIds: [`QC-${code}`] })
const evaluate = items => evaluatePurchaseOrderCreationGateDecisionV1142820(
  createPurchaseOrderCreationGateDecisionV1142820({ decisionBatchResult: {
    objectType: 'SupplierRecommendationDecisionBatchResult', batchId: 'SRDB-201', decisionRevision: 1,
    status: 'confirmed', items, purchaseOrderCreated: false },
  purchaseContext: { sourceRequestNos: ['PR-201'] },
  historicalPurchaseOrders: [{ purchaseOrderNo: 'PO-HISTORY', status: 'cancelled' }] }),
  { checkedBy: 'Gate检查员201', now: '2026-08-06T20:20:00.000Z' })

const ready = evaluate([makeItem('MAT-A'), makeItem('MAT-B')])
const blocked = evaluate([makeItem('MAT-A'), makeItem('MAT-EXCEPTION', false)])
const current = run(['--test', 'tests/acceptance/purchaseOrderGateActionClosureV11428201.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/purchaseOrderGateRuntimeV1142820.test.mjs',
  'tests/acceptance/enterprisePurchaseOrderCreationGateRuntimeV1142814.test.mjs',
  'tests/acceptance/supplierRecommendationHumanDecisionV1142819.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs'])
const routeRegression = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, routeRegression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const page = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
const provider = read('src/meta/providers/purchaseOrderGateRuntimeProviderV1142820.js')
const model = read('src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')
const gateAction = current.status === 0 && page.includes('重新执行准入检查')
  && provider.includes('evaluatePurchaseOrderCreationGateDecisionV1142820(draft(sourceFacts)')
  && !provider.includes('idempotent: true')
const materialExceptionAction = ['查看推荐依据', '查看供应商选择', '返回供应商推荐修改',
  "router.push('/scm/supplier-recommendation')"].every(value => page.includes(value))
  && !page.includes('删除物料')
const gateRefresh = ready.lastCheckedAt === '2026-08-06T20:20:00.000Z'
  && ready.checkedBy === 'Gate检查员201' && provider.includes('refreshed: Boolean(previous)')
const historicalIsolation = HistoricalPurchaseOrderIsolationCheck(ready).passed
  && ready.historicalPurchaseOrderReadCount === 0
  && model.includes('HistoricalPurchaseOrderIsolationCheck')
  && !/listPurchaseOrders|purchaseOrderList|historicalPurchaseOrderLoader/.test(provider)
const exceptionItem = blocked.items.find(item => item.materialCode === 'MAT-EXCEPTION')
const blockedReason = blocked.status === 'blocked' && exceptionItem?.gateStatus === 'blocked'
  && exceptionItem.blockedReasons.includes('物料推荐尚未确认')
  && page.includes("(row.blockedReasons || []).join('；')")
const readyState = ready.status === 'ready_for_purchase_order'
  && ready.checks.every(check => check.result === 'PASS')
const noPurchaseOrder = [ready, blocked].every(value => value.purchaseOrderCreated === false
  && value.purchaseOrderSubmitted === false && value.purchaseOrderApproved === false)
  && !page.includes('data-process-action="CREATE_PURCHASE_ORDER"')
const process011 = current.status === 0 && routeRegression.status === 0 && gateAction
  && materialExceptionAction && gateRefresh && historicalIsolation && blockedReason
  && readyState && noPurchaseOrder

const checks = [
  ['Gate Action', gateAction],
  ['Material Exception Action', materialExceptionAction],
  ['Gate Refresh', gateRefresh],
  ['Historical PO Isolation', historicalIsolation],
  ['Blocked Reason', blockedReason],
  ['Ready State', readyState],
  ['No PurchaseOrder Creation', noPurchaseOrder],
  ['PROCESS-011', process011],
  ['Regression', regression.status === 0 && routeRegression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.20.1')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
for (const layer of ['Object Exists', 'Page Exists', 'Data Handoff', 'Human Action Loop',
  'Action Executability', 'Batch Completeness', 'Historical Data Isolation']) {
  console.log(`${layer} ${process011 ? 'PASS' : 'FAIL'}`)
}
console.log(passed ? 'PURCHASE_ORDER_GATE_ACTION_READY'
  : 'PURCHASE_ORDER_GATE_ACTION_ISSUES_FOUND')
if (!passed) process.exitCode = 1
