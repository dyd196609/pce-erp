import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationBatchStoreV11428165 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationBatchContextV11428165.js'
import { createSupplierRecommendationTaskStoreV11428167 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js'
import { createSupplierRecommendationDecisionBatchStoreV11428169,
  executeSupplierRecommendationDecisionBatchEntryV11428169 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'
import { createSupplierRecommendationDataHandoffProviderV1142818 } from '../../src/meta/providers/supplierRecommendationDataHandoffProviderV1142818.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const memoryStorage = () => { const values = new Map(); return {
  getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) } }
const supplier = index => ({ supplierCode: `SUP-GRAIN-${index}`, supplierName: `粒度供应商${index}`,
  supplierStatus: 'active' })
const qualificationProvider = { source: 'Supplier Master', load: () => ({ options: [1, 2, 3]
  .map(supplier) }) }

const makeSourceRow = ({ material = 1, supplierIndex = 1, approval = material,
  comparison = material } = {}) => ({
  priceApprovalId: `PA-GRAIN-${approval}`,
  priceApprovalNo: `PAP-GRAIN-${approval}`,
  sourceInquiryNo: 'PI-GRAIN-REAL',
  sourceRequestNo: 'PR-GRAIN-REAL',
  quoteComparisonId: `QC-GRAIN-${comparison}`,
  materialCode: `MAT-GRAIN-${material}`,
  materialName: `粒度物料${material}`,
  supplierCandidates: [{ ...supplier(supplierIndex), quotePrice: 100 + material + supplierIndex,
    priceRank: supplierIndex }],
  priceEvidence: [{ supplierCode: supplier(supplierIndex).supplierCode,
    currentPrice: 100 + material + supplierIndex, priceRank: supplierIndex,
    evidenceSource: 'QuoteComparison' }],
  historicalPriceEvidence: [{ supplierCode: supplier(supplierIndex).supplierCode,
    historyPrice: 98 + material, currentPrice: 100 + material + supplierIndex,
    changeRate: 0.02, evidenceSource: 'PurchaseOrderHistory' }],
  priceReferenceRecords: [{ materialCode: `MAT-GRAIN-${material}`, materialName: `粒度物料${material}`,
    supplierCode: supplier(supplierIndex).supplierCode, supplierName: supplier(supplierIndex).supplierName,
    historicalPurchasePrice: 98 + material, currentQuote: 100 + material + supplierIndex,
    priceChangeRatio: 0.02, evidenceSource: 'PriceReferenceContext' }],
})

function createCanary(inputs) {
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const batchStore = createSupplierRecommendationBatchStoreV11428165({ storage: memoryStorage() })
  const taskStore = createSupplierRecommendationTaskStoreV11428167({ storage: memoryStorage() })
  const decisionBatchStore = createSupplierRecommendationDecisionBatchStoreV11428169({ storage: memoryStorage() })
  const entry = executeSupplierRecommendationDecisionBatchEntryV11428169(inputs,
    { handoffStore, batchStore, taskStore, decisionBatchStore, qualificationProvider })
  const provider = createSupplierRecommendationDataHandoffProviderV1142818({
    taskStore, decisionBatchStore, priceApprovalHandoffStore: handoffStore })
  return { entry, facts: provider.load({ taskId: entry.activeBatch?.batchId }) }
}

test('Canary A keeps one source material as one DecisionItem', () => {
  const canary = createCanary([makeSourceRow()])
  assert.equal(canary.entry.result, 'PASS')
  assert.equal(canary.entry.sourceRowCount, 1)
  assert.equal(canary.entry.materialCount, 1)
  assert.equal(canary.entry.decisionItemCount, 1)
  assert.equal(canary.facts.items.length, 1)
})

test('Canary B converts 19 PriceApproval rows into 13 material DecisionItems without loss', () => {
  const rows = Array.from({ length: 13 }, (_, index) => makeSourceRow({ material: index + 1 }))
  rows.push(...Array.from({ length: 6 }, (_, index) => makeSourceRow({
    material: index + 1, supplierIndex: 2,
  })))
  const canary = createCanary(rows)
  assert.equal(canary.entry.result, 'PASS')
  assert.equal(canary.entry.sourceRowCount, 19)
  assert.equal(canary.entry.materialCount, 13)
  assert.equal(canary.entry.decisionItemCount, 13)
  assert.equal(canary.facts.result, 'PASS')
  assert.equal(canary.facts.items.length, 13)
  assert.equal(new Set(canary.facts.items.map(item => item.materialCode)).size, 13)
  assert.equal(canary.facts.items.reduce((count, item) => count + item.supplierCandidates.length, 0), 19)
  for (const item of canary.facts.items) {
    const material = Number(item.materialCode.replace('MAT-GRAIN-', ''))
    assert.equal(item.supplierCandidates.length, material <= 6 ? 2 : 1)
  }
})

test('Canary C groups multiple suppliers and QuoteComparisons under one material item', () => {
  const rows = [1, 2, 3].map(index => makeSourceRow({ material: 7, supplierIndex: index,
    approval: index, comparison: index }))
  const canary = createCanary(rows)
  assert.equal(canary.entry.result, 'PASS')
  assert.equal(canary.entry.sourceRowCount, 3)
  assert.equal(canary.entry.decisionItemCount, 1)
  assert.equal(canary.facts.result, 'PASS')
  assert.equal(canary.facts.items.length, 1)
  assert.equal(canary.facts.items[0].supplierCandidates.length, 3)
  assert.deepEqual(canary.facts.items[0].quoteComparisonIds,
    ['QC-GRAIN-1', 'QC-GRAIN-2', 'QC-GRAIN-3'])
})

test('workbench renders material items and all supplier quotes without truncation', () => {
  const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
  const model = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
  assert.match(page, /batch\?\.items/)
  assert.match(page, /item\.supplierCandidates/)
  assert.match(model, /aggregateInputsBy\(inputs, input => text\(input\.materialCode\)\)/)
  assert.doesNotMatch(model, /\.slice\(0\s*,\s*13\)/)
})
