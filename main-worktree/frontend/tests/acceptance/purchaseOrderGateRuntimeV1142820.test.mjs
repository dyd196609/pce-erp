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

const makeItem = (index, confirmed = true) => ({
  decisionItemId: `SRDI-GATE-${index}`,
  materialCode: `MAT-GATE-${index}`,
  materialName: `准入物料${index}`,
  selectedSupplierCode: confirmed ? `SUP-${index}` : '',
  selectedSupplierName: confirmed ? `供应商${index}` : '',
  selectionReason: confirmed ? `基于物料${index}报价比较、历史价格与资格证据人工确认。` : '',
  reviewStatus: confirmed ? 'confirmed' : 'manual_review',
  reviewer: confirmed ? '采购员Gate20' : '',
  reviewedAt: confirmed ? '2026-08-06T20:00:00.000Z' : '',
  status: confirmed ? 'confirmed' : 'selected',
  supplierCandidates: [{ supplierCode: `SUP-${index}`, supplierName: `供应商${index}`,
    quotePrice: 100 + index, priceRank: 1 }],
  priceEvidence: [
    { supplierCode: `SUP-${index}`, currentPrice: 100 + index, priceRank: 1,
      evidenceSource: 'QuoteComparison' },
    { supplierCode: `SUP-${index}`, historyPrice: 96 + index, currentPrice: 100 + index,
      evidenceSource: 'PurchaseOrderHistory' },
  ],
  quoteComparisonIds: [`QC-GATE-${index}`],
})
const makeSourceItem = index => ({
  materialCode: `MAT-GATE-${index}`,
  quoteComparisonIds: [`QC-GATE-${index}`],
  supplierCandidates: [{ supplierCode: `SUP-${index}`, supplierName: `供应商${index}`,
    quotePrice: 100 + index, priceRank: 1 }],
  priceEvidence: [
    { supplierCode: `SUP-${index}`, currentPrice: 100 + index, priceRank: 1,
      evidenceSource: 'QuoteComparison' },
    { supplierCode: `SUP-${index}`, historyPrice: 96 + index, currentPrice: 100 + index,
      evidenceSource: 'PurchaseOrderHistory' },
  ],
  priceReferenceContexts: [{ supplierCode: `SUP-${index}`, historicalPurchasePrice: 96 + index,
    evidenceSource: 'PriceReferenceContext' }],
})
const makeInput = (count, incompleteIndex = 0) => ({
  decisionBatchResult: {
    objectType: 'SupplierRecommendationDecisionBatchResult',
    batchId: `SRDB-GATE-${count}-${incompleteIndex}`,
    decisionRevision: 1,
    status: 'confirmed',
    confirmedBy: '采购员Gate20',
    confirmedAt: '2026-08-06T20:00:00.000Z',
    items: Array.from({ length: count }, (_, offset) =>
      makeItem(offset + 1, incompleteIndex !== offset + 1)),
    purchaseOrderCreated: false,
  },
  purchaseContext: { sourceRequestNos: ['PR-GATE-20'],
    sourceInquiryNos: ['PI-GATE-20'], priceApprovalNos: ['PAP-GATE-20'] },
  sourceItems: Array.from({ length: count }, (_, offset) => makeSourceItem(offset + 1)),
})

test('Canary A: one confirmed material creates a ready gate decision', () => {
  const pending = createPurchaseOrderCreationGateDecisionV1142820(makeInput(1))
  assert.equal(pending.objectType, 'PurchaseOrderCreationGateDecision')
  assert.equal(pending.status, 'pending_review')
  assert.deepEqual(pending.batchCompleteness, { totalItemCount: 1,
    completedItemCount: 1, pendingItemCount: 0, actionDisabled: false })
  const decision = evaluatePurchaseOrderCreationGateDecisionV1142820(pending,
    '2026-08-06T20:01:00.000Z')
  assert.equal(decision.status, 'ready_for_purchase_order')
  assert.equal(decision.checks.every(check => check.passed), true)
  assert.equal(decision.purchaseOrderCreated, false)
})

test('Canary B: all 13 confirmed materials retain evidence and create one ready decision', () => {
  const decision = evaluatePurchaseOrderCreationGateDecisionV1142820(
    createPurchaseOrderCreationGateDecisionV1142820(makeInput(13)))
  assert.equal(decision.items.length, 13)
  assert.equal(decision.batchCompleteness.completedItemCount, 13)
  assert.equal(decision.batchCompleteness.pendingItemCount, 0)
  assert.equal(decision.items.every(item => item.quoteComparisonEvidence.length > 0
    && item.supplierQuoteEvidence.length > 0 && item.historicalPriceEvidence.length > 0), true)
  assert.equal(decision.status, 'ready_for_purchase_order')
})

test('Canary C: one unconfirmed material creates a blocked decision with explicit reasons', () => {
  const decision = evaluatePurchaseOrderCreationGateDecisionV1142820(
    createPurchaseOrderCreationGateDecisionV1142820(makeInput(13, 7)))
  assert.equal(decision.batchCompleteness.totalItemCount, 13)
  assert.equal(decision.batchCompleteness.completedItemCount, 12)
  assert.equal(decision.batchCompleteness.pendingItemCount, 1)
  assert.equal(decision.status, 'blocked')
  assert.equal(decision.purchaseOrderCreationAllowed, false)
  assert.ok(decision.blockedReasons.includes('当前推荐批次仍有未完成物料决策'))
  assert.ok(decision.blockedReasons.includes('存在未确认的DecisionItem'))
})

test('Gate Provider binds the active real DecisionBatch result and evaluates latest revision on load', () => {
  const input = makeInput(1)
  const gateStore = createPurchaseOrderCreationGateDecisionStoreV1142820({ storage: memoryStorage() })
  const decisionBatchStore = {
    activeBatchId: () => input.decisionBatchResult.batchId,
    findResult: () => input.decisionBatchResult,
    findHandoff: () => ({ objectType: 'SupplierRecommendationDecisionBatchGateHandoff',
      batchId: input.decisionBatchResult.batchId, status: 'handoff_ready', purchaseOrderCreated: false }),
  }
  const dataHandoffProvider = { load: () => ({ result: 'PASS',
    purchaseContext: input.purchaseContext, items: input.sourceItems,
    factScope: 'real_price_approval_handoff', purchaseOrderCreated: false }) }
  const provider = createPurchaseOrderGateRuntimeProviderV1142820({ decisionBatchStore,
    dataHandoffProvider, gateDecisionStore: gateStore })
  assert.equal(provider.load().current.status, 'ready_for_purchase_order')
  assert.equal(provider.evaluateActive({ permissionContext: { role: 'viewer' } }).error,
    'ACTION_PERMISSION_DENIED')
  const evaluated = provider.evaluateActive({ permissionContext: { role: 'manager' },
    now: '2026-08-06T20:02:00.000Z' })
  assert.equal(evaluated.result, 'PASS')
  assert.equal(evaluated.decision.status, 'ready_for_purchase_order')
  assert.equal(provider.load().current.status, 'ready_for_purchase_order')
  assert.equal(provider.evaluateActive({ permissionContext: { role: 'manager' } }).refreshed, true)
})

test('Gate page preserves stable route identity, nine-layer regions and purchase order isolation', () => {
  const page = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
  const router = read('src/router/index.js')
  for (const region of ['gate-purchase-context', 'decision-batch-gate-handoff',
    'batch-completeness', 'gate-check-results', 'gate-human-audit', 'next-action']) {
    assert.match(page, new RegExp(`data-acceptance-region="${region}"`))
  }
  for (const label of ['采购申请编号', '推荐批次编号', '物料编码', '物料名称', '推荐供应商',
    '确认状态', '检查项目', '阻断原因', '确认人', '确认时间']) assert.match(page, new RegExp(label))
  assert.match(page, /EVALUATE_PURCHASE_ORDER_CREATION_GATE/)
  assert.match(page, /purchaseOrderGateRuntimeProviderV1142820/)
  assert.match(router, /path: 'scm\/purchase-order-gate'/)
  assert.doesNotMatch(page, /route\.query\.(?:batchId|taskId|runtimeContextId)/)
  assert.doesNotMatch(page, /data-process-action="(?:CREATE|SUBMIT|APPROVE)_PURCHASE_ORDER"/)
})
