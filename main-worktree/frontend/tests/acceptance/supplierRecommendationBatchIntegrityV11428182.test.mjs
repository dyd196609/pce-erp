import test from 'node:test'
import assert from 'node:assert/strict'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationBatchStoreV11428165 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationBatchContextV11428165.js'
import { createSupplierRecommendationTaskStoreV11428167 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js'
import { createSupplierRecommendationDecisionBatchStoreV11428169,
  executeSupplierRecommendationDecisionBatchEntryV11428169 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'
import { createSupplierRecommendationDataHandoffProviderV1142818 } from '../../src/meta/providers/supplierRecommendationDataHandoffProviderV1142818.js'
import { createSupplierRecommendationRouteContextResolverV11428171 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationRouteContextResolverV11428171.js'

const memoryStorage = () => { const values = new Map(); return {
  getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) } }
const supplier = index => ({ supplierCode: `SUP-INTEGRITY-${index}`,
  supplierName: `完整性供应商${index}`, supplierStatus: 'active' })
const qualificationProvider = { source: 'Supplier Master', load: () => ({
  options: [1, 2, 3].map(supplier) }) }
const makeRow = ({ material = 1, supplierIndex = 1, approval = material,
  comparison = approval, inquiry = ((material - 1) % 4) + 1 } = {}) => ({
  priceApprovalId: `PA-INTEGRITY-${approval}`, priceApprovalNo: `PAP-INTEGRITY-${approval}`,
  sourceInquiryNo: `PI-INTEGRITY-${inquiry}`, sourceRequestNo: `PR-INTEGRITY-${inquiry}`,
  quoteComparisonId: `QC-INTEGRITY-${comparison}`,
  materialCode: `MAT-INTEGRITY-${String(material).padStart(3, '0')}`,
  materialName: `完整性物料${material}`,
  supplierCandidates: [{ ...supplier(supplierIndex), quotePrice: 100 + material + supplierIndex,
    priceRank: supplierIndex }],
  priceEvidence: [{ supplierCode: supplier(supplierIndex).supplierCode,
    currentPrice: 100 + material + supplierIndex, priceRank: supplierIndex,
    evidenceSource: 'QuoteComparison' }],
  historicalPriceEvidence: [{ supplierCode: supplier(supplierIndex).supplierCode,
    historyPrice: 98 + material, currentPrice: 100 + material + supplierIndex,
    evidenceSource: 'PurchaseOrderHistory' }],
})

function executeCanary(rows) {
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const batchStore = createSupplierRecommendationBatchStoreV11428165({ storage: memoryStorage() })
  const taskStore = createSupplierRecommendationTaskStoreV11428167({ storage: memoryStorage() })
  const decisionBatchStore = createSupplierRecommendationDecisionBatchStoreV11428169({ storage: memoryStorage() })
  const entry = executeSupplierRecommendationDecisionBatchEntryV11428169(rows,
    { handoffStore, batchStore, taskStore, decisionBatchStore, qualificationProvider })
  const provider = createSupplierRecommendationDataHandoffProviderV1142818({
    taskStore, decisionBatchStore, priceApprovalHandoffStore: handoffStore })
  const resolver = createSupplierRecommendationRouteContextResolverV11428171({
    storage: memoryStorage(), decisionBatchStore, taskStore })
  return { entry, taskStore, decisionBatchStore, provider, resolver,
    facts: provider.load({ taskId: entry.activeBatch?.batchId }) }
}

test('Canary A carries one selected PriceApproval row into one DecisionItem', () => {
  const canary = executeCanary([makeRow()])
  assert.equal(canary.entry.result, 'PASS')
  assert.equal(canary.entry.diagnostics.selectedRowsCount, 1)
  assert.equal(canary.entry.diagnostics.taskCreationCount, 1)
  assert.equal(canary.entry.decisionBatches.length, 1)
  assert.equal(canary.entry.activeBatch.items.length, 1)
  assert.deepEqual(canary.entry.activeBatch.items[0].sourcePriceApprovalIds, ['PA-INTEGRITY-1'])
})

test('Canary B carries 19 cross-inquiry rows into one batch and 13 material items', () => {
  const rows = Array.from({ length: 13 }, (_, index) => makeRow({ material: index + 1 }))
  rows.push(...Array.from({ length: 6 }, (_, index) => makeRow({ material: index + 1,
    supplierIndex: 2, approval: 14 + index, comparison: 14 + index,
    inquiry: ((index + 1) % 4) + 1 })))
  const canary = executeCanary(rows)
  assert.equal(canary.entry.result, 'PASS')
  assert.deepEqual(canary.entry.diagnostics, {
    selectedRowsCount: 19, taskCreationCount: 19, batchSourceTaskCount: 19, decisionItemCount: 13 })
  assert.equal(canary.entry.decisionBatches.length, 1)
  assert.equal(canary.entry.activeBatch.sourcePriceApprovalBatch.length, 19)
  assert.equal(canary.decisionBatchStore.listBindings(canary.entry.activeBatch.batchId).length, 19)
  assert.equal(canary.entry.activeBatch.items.length, 13)
  assert.equal(new Set(canary.entry.activeBatch.items.map(item => item.materialCode)).size, 13)
  assert.equal(canary.entry.activeBatch.items.reduce(
    (count, item) => count + item.sourcePriceApprovalIds.length, 0), 19)
  assert.equal(canary.entry.activeBatch.items.reduce(
    (count, item) => count + item.supplierCandidates.length, 0), 19)
  assert.equal(canary.facts.result, 'PASS')
  assert.equal(canary.facts.items.length, 13)
  assert.equal(canary.provider.load({ taskId: canary.entry.activeBatch.batchId }).items.length, 13)
  assert.equal(canary.resolver.activate(canary.entry.activeBatch.batchId).result, 'PASS')
  assert.equal(canary.resolver.resolve().decisionBatch.batchId, canary.entry.activeBatch.batchId)
})

test('Canary C groups MT006 supplier A B C into one item with three candidates', () => {
  const rows = [1, 2, 3].map(supplierIndex => makeRow({ material: 6, supplierIndex,
    approval: 6, comparison: 6, inquiry: 2 }))
  const canary = executeCanary(rows)
  assert.equal(canary.entry.result, 'PASS')
  assert.equal(canary.entry.sourceRowCount, 3)
  assert.equal(canary.entry.taskCount, 1)
  assert.equal(canary.entry.activeBatch.items.length, 1)
  assert.equal(canary.entry.activeBatch.items[0].supplierCandidates.length, 3)
  assert.deepEqual(canary.entry.activeBatch.items[0].supplierCandidates.map(item => item.supplierCode),
    ['SUP-INTEGRITY-1', 'SUP-INTEGRITY-2', 'SUP-INTEGRITY-3'])
  assert.equal(canary.facts.items[0].supplierCandidates.length, 3)
})
