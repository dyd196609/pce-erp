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
const qualificationProvider = { source: 'Supplier Master', load: () => ({ options: [
  { supplierCode: 'SUP-CAN-A', supplierName: '金丝雀供应商A', supplierStatus: 'active' },
  { supplierCode: 'SUP-CAN-B', supplierName: '金丝雀供应商B', supplierStatus: 'active' },
] }) }
const makeInput = index => ({
  priceApprovalId: `PA-CAN-${index}`, priceApprovalNo: `PAP-CAN-${index}`,
  sourceInquiryNo: 'PI-CAN-REAL', sourceRequestNo: 'PR-CAN-REAL',
  quoteComparisonId: `QC-CAN-${index}`, materialCode: `MAT-CAN-${index}`,
  materialName: `金丝雀物料${index}`,
  supplierCandidates: [
    { supplierCode: 'SUP-CAN-A', supplierName: '金丝雀供应商A', quotePrice: 100 + index, priceRank: 1 },
    { supplierCode: 'SUP-CAN-B', supplierName: '金丝雀供应商B', quotePrice: 105 + index, priceRank: 2 },
  ],
  priceEvidence: [
    { supplierCode: 'SUP-CAN-A', currentPrice: 100 + index, priceRank: 1, evidenceSource: 'QuoteComparison' },
    { supplierCode: 'SUP-CAN-B', currentPrice: 105 + index, priceRank: 2, evidenceSource: 'QuoteComparison' },
  ],
  historicalPriceEvidence: [{ supplierCode: 'SUP-CAN-A', historyPrice: 98 + index,
    currentPrice: 100 + index, changeRate: 0.02, evidenceSource: 'PurchaseOrderHistory' }],
  priceReferenceRecords: [{ materialCode: `MAT-CAN-${index}`, materialName: `金丝雀物料${index}`,
    supplierCode: 'SUP-CAN-A', supplierName: '金丝雀供应商A', historicalPurchasePrice: 98 + index,
    currentQuote: 100 + index, priceChangeRatio: 0.02, evidenceSource: 'PriceReferenceContext' }],
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
  return { entry, provider, handoffStore, taskStore, decisionBatchStore,
    facts: provider.load({ taskId: entry.activeBatch?.batchId }) }
}

test('Canary A records one real PriceApproval through Task and DecisionBatch', () => {
  const canary = createCanary([makeInput(1)])
  assert.equal(canary.facts.result, 'PASS')
  assert.equal(canary.facts.factScope, 'real_price_approval_handoff')
  assert.equal(canary.facts.items.length, 1)
  const item = canary.facts.items[0]
  assert.equal(item.priceApprovalId, 'PA-CAN-1')
  assert.equal(item.quoteComparisonId, 'QC-CAN-1')
  assert.equal(item.materialCode, 'MAT-CAN-1')
  assert.ok(item.taskId && canary.facts.batch.batchId)
  assert.deepEqual(item.supplierCandidates.map(value => value.supplierCode), ['SUP-CAN-A', 'SUP-CAN-B'])
})

test('Canary B keeps multiple materials as independent DecisionItems', () => {
  const canary = createCanary([makeInput(1), makeInput(2), makeInput(3)])
  assert.equal(canary.facts.result, 'PASS')
  assert.equal(canary.facts.items.length, 3)
  assert.equal(new Set(canary.facts.items.map(item => item.materialCode)).size, 3)
  assert.equal(new Set(canary.facts.items.map(item => item.quoteComparisonId)).size, 3)
  for (const item of canary.facts.items) {
    assert.equal(item.supplierCandidates.length, 2)
    assert.equal(item.priceReferenceContexts[0].evidenceSource, 'PriceReferenceContext')
    assert.equal(item.factScope, 'real_price_approval_handoff')
  }
})

test('Canary C blocks a missing or mismatched Task instead of falling through to demo facts', () => {
  const canary = createCanary([makeInput(9)])
  const blockedProvider = createSupplierRecommendationDataHandoffProviderV1142818({
    taskStore: { findById: () => null }, decisionBatchStore: canary.decisionBatchStore,
    priceApprovalHandoffStore: canary.handoffStore })
  const blocked = blockedProvider.load({ taskId: canary.entry.activeBatch.batchId })
  assert.equal(blocked.result, 'FAIL')
  assert.match(blocked.error, /TASK_DATA_MISMATCH/)
  assert.equal(blocked.items.length, 0)
  assert.equal(JSON.stringify(blocked).includes('PI-TEST-SR'), false)
})

test('page business areas consume the handoff provider and display governed source fields', () => {
  const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
  assert.match(page, /supplierRecommendationDataHandoffProviderV1142818\.load/)
  assert.match(page, /采购申请编号/)
  assert.match(page, /核价编号/)
  assert.match(page, /quoteComparisonId/)
  assert.match(page, /priceReferenceContexts/)
  assert.doesNotMatch(page, /PI-TEST-SR|supplierRecommendationQuoteComparisonTestFacts/)
})
