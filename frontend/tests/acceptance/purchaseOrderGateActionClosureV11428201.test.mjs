import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPurchaseOrderCreationGateDecisionStoreV1142820,
  createPurchaseOrderCreationGateDecisionV1142820,
  evaluatePurchaseOrderCreationGateDecisionV1142820 } from '../../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js'
import { createPurchaseOrderGateRuntimeProviderV1142820 } from '../../src/meta/providers/purchaseOrderGateRuntimeProviderV1142820.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const memoryStorage = () => { const values = new Map(); return {
  getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value),
} }
const item = (materialCode, confirmed = true) => ({
  decisionItemId: `SRDI-${materialCode}`, materialCode, materialName: `物料${materialCode}`,
  selectedSupplierCode: confirmed ? 'SUP-CURRENT' : '',
  selectedSupplierName: confirmed ? '当前推荐供应商' : '',
  selectionReason: confirmed ? '人工复核当前批次报价后确认。' : '',
  reviewStatus: confirmed ? 'confirmed' : 'manual_review',
  reviewer: confirmed ? '采购员201' : '',
  reviewedAt: confirmed ? '2026-08-06T20:10:00.000Z' : '',
  status: confirmed ? 'confirmed' : 'selected',
  supplierCandidates: [{ supplierCode: 'SUP-CURRENT', supplierName: '当前推荐供应商',
    quotePrice: 128 }],
  priceEvidence: [{ supplierCode: 'SUP-CURRENT', currentPrice: 128,
    evidenceSource: 'QuoteComparison' }],
  quoteComparisonIds: [`QC-${materialCode}`],
})
const result = (items, batchId = 'SRDB-ACTION-201') => ({
  objectType: 'SupplierRecommendationDecisionBatchResult', batchId, decisionRevision: 1, status: 'confirmed',
  items, confirmedBy: '采购员201', confirmedAt: '2026-08-06T20:10:00.000Z',
  purchaseOrderCreated: false,
})

test('Gate action always re-reads Provider and refreshes checkedBy/lastCheckedAt', () => {
  let currentResult = result([item('MAT-A'), item('MAT-B')])
  let providerLoadCount = 0
  const decisionBatchStore = { activeBatchId: () => currentResult.batchId,
    findResult: () => currentResult,
    findHandoff: () => ({ status: 'handoff_ready', batchId: currentResult.batchId }) }
  const dataHandoffProvider = { load: () => { providerLoadCount += 1; return {
    result: 'PASS', purchaseContext: { sourceRequestNos: ['PR-201'] }, items: currentResult.items,
  } } }
  const gateDecisionStore = createPurchaseOrderCreationGateDecisionStoreV1142820({
    storage: memoryStorage() })
  const provider = createPurchaseOrderGateRuntimeProviderV1142820({ decisionBatchStore,
    dataHandoffProvider, gateDecisionStore })
  const first = provider.evaluateActive({ permissionContext: { role: 'manager',
    userName: 'Gate检查员甲' }, now: '2026-08-06T20:11:00.000Z' })
  assert.equal(first.decision.status, 'ready_for_purchase_order')
  assert.equal(first.decision.checkedBy, 'Gate检查员甲')
  assert.equal(first.decision.lastCheckedAt, '2026-08-06T20:11:00.000Z')
  currentResult = result([item('MAT-A'), item('MAT-B', false)])
  const refreshed = provider.evaluateActive({ permissionContext: { role: 'manager',
    userName: 'Gate检查员乙' }, now: '2026-08-06T20:12:00.000Z' })
  assert.equal(refreshed.refreshed, true)
  assert.equal(refreshed.decision.status, 'blocked')
  assert.equal(refreshed.decision.checkedBy, 'Gate检查员乙')
  assert.equal(refreshed.decision.lastCheckedAt, '2026-08-06T20:12:00.000Z')
  assert.ok(providerLoadCount >= 2)
})

test('material exception exposes exact material, blocked reason and handling entry', () => {
  const decision = evaluatePurchaseOrderCreationGateDecisionV1142820(
    createPurchaseOrderCreationGateDecisionV1142820({
      decisionBatchResult: result([item('MAT-A'), item('MAT-EXCEPTION', false)]),
      purchaseContext: { sourceRequestNos: ['PR-201'] },
    }), { checkedBy: 'Gate检查员', now: '2026-08-06T20:13:00.000Z' })
  const exception = decision.items.find(value => value.materialCode === 'MAT-EXCEPTION')
  assert.equal(decision.status, 'blocked')
  assert.equal(exception.gateStatus, 'blocked')
  assert.ok(exception.blockedReasons.includes('物料推荐尚未确认'))
  const page = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
  for (const action of ['查看推荐依据', '查看供应商选择', '返回供应商推荐修改']) {
    assert.match(page, new RegExp(action))
  }
  assert.match(page, /\(row\.blockedReasons \|\| \[\]\)\.join/)
  assert.match(page, /router\.push\('\/scm\/supplier-recommendation'\)/)
  assert.doesNotMatch(page, /删除物料/)
})

test('historical PurchaseOrder list is ignored by the current DecisionBatch gate', () => {
  const decision = evaluatePurchaseOrderCreationGateDecisionV1142820(
    createPurchaseOrderCreationGateDecisionV1142820({
      decisionBatchResult: result([item('MAT-CURRENT')]),
      purchaseContext: { sourceRequestNos: ['PR-201'] },
      historicalPurchaseOrders: [{ purchaseOrderNo: 'PO-HISTORY-BLOCKED', status: 'cancelled',
        supplierCode: 'SUP-OLD' }],
    }), { checkedBy: 'Gate检查员' })
  assert.equal(decision.status, 'ready_for_purchase_order')
  assert.equal(decision.gateFactSource, 'SupplierRecommendationDecisionBatchResult')
  assert.equal(decision.historicalPurchaseOrderReadCount, 0)
  assert.equal(decision.checks.find(check =>
    check.checkCode === 'HISTORICAL_PO_ISOLATION').result, 'PASS')
  const provider = read('src/meta/providers/purchaseOrderGateRuntimeProviderV1142820.js')
  assert.doesNotMatch(provider, /listPurchaseOrders|purchaseOrderList|historicalPurchaseOrderLoader/)
})

test('Gate page keeps recheck executable and displays check audit fields', () => {
  const page = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
  assert.match(page, /重新执行准入检查/)
  assert.match(page, /lastCheckedAt/)
  assert.match(page, /checkedBy/)
  assert.match(page, /purchaseOrderGateRuntimeProviderV1142820\.evaluateActive/)
  assert.doesNotMatch(page, /current\.value\?\.status === 'pending_review'/)
  assert.doesNotMatch(page, /data-process-action="CREATE_PURCHASE_ORDER"/)
})
