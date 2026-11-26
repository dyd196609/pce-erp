import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationBatchStoreV11428165 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationBatchContextV11428165.js'
import { createSupplierRecommendationTaskStoreV11428167 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js'
import { createSupplierRecommendationDecisionBatchStoreV11428169,
  executeConfirmSupplierRecommendationDecisionBatchV11428169,
  executeSelectDecisionBatchSupplierV11428169,
  executeSupplierRecommendationDecisionBatchEntryV11428169 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const memoryStorage = () => { const values = new Map(); return {
  getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) } }
const qualificationProvider = { source: 'Supplier Master', load: () => ({ options: [
  { supplierCode: 'SUP-LOW', supplierName: '最低价供应商', supplierStatus: 'active' },
  { supplierCode: 'SUP-NONLOW', supplierName: '非最低价供应商', supplierStatus: 'active' },
] }) }
const input = index => ({
  priceApprovalId: `PA-HUMAN-${index}`, priceApprovalNo: `PAP-HUMAN-${index}`,
  sourceInquiryNo: 'PI-HUMAN-19', sourceRequestNo: 'PR-HUMAN-19',
  quoteComparisonId: `QC-HUMAN-${index}`, materialCode: `MAT-HUMAN-${index}`,
  materialName: `人工决策物料${index}`,
  supplierCandidates: [
    { supplierCode: 'SUP-LOW', supplierName: '最低价供应商', quotePrice: 100 + index, priceRank: 1,
      supplierStatus: 'active' },
    { supplierCode: 'SUP-NONLOW', supplierName: '非最低价供应商', quotePrice: 110 + index, priceRank: 2,
      supplierStatus: 'active' },
  ],
  priceEvidence: [
    { supplierCode: 'SUP-LOW', currentPrice: 100 + index, priceRank: 1, evidenceSource: 'QuoteComparison' },
    { supplierCode: 'SUP-NONLOW', currentPrice: 110 + index, priceRank: 2, evidenceSource: 'QuoteComparison' },
  ],
  historicalPriceEvidence: [{ supplierCode: 'SUP-NONLOW', historyPrice: 106 + index,
    currentPrice: 110 + index, evidenceSource: 'PurchaseOrderHistory' }],
})

function fixture(count = 1) {
  const stores = {
    handoffStore: createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() }),
    batchStore: createSupplierRecommendationBatchStoreV11428165({ storage: memoryStorage() }),
    taskStore: createSupplierRecommendationTaskStoreV11428167({ storage: memoryStorage() }),
    decisionBatchStore: createSupplierRecommendationDecisionBatchStoreV11428169({ storage: memoryStorage() }),
  }
  const entry = executeSupplierRecommendationDecisionBatchEntryV11428169(
    Array.from({ length: count }, (_, index) => input(index + 1)), { ...stores, qualificationProvider })
  return { ...stores, entry }
}

test('Canary A exposes governed manual decision fields and candidate evidence', () => {
  const { entry } = fixture()
  const item = entry.activeBatch.items[0]
  assert.equal(item.reviewStatus, 'manual_review')
  for (const field of ['decisionItemId', 'selectedSupplierCode', 'selectedSupplierName',
    'selectionReason', 'reviewStatus', 'reviewer', 'reviewedAt']) assert.equal(field in item, true)
  const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
  for (const label of ['报价金额', '报价比较', '历史价格', '资格状态']) assert.match(page, new RegExp(label))
})

test('Canary C permits an explicit non-lowest-price manual decision', () => {
  const fixtureValue = fixture()
  const batchId = fixtureValue.entry.activeBatch.batchId
  const selected = executeSelectDecisionBatchSupplierV11428169(batchId, 'MAT-HUMAN-1',
    'SUP-NONLOW', '基于交付与质量因素，人工选择非最低价供应商。',
    { store: fixtureValue.decisionBatchStore, permissionContext: { role: 'manager' } })
  assert.equal(selected.result, 'PASS')
  assert.equal(selected.item.selectedSupplierCode, 'SUP-NONLOW')
  assert.equal(selected.item.selectionReason, '基于交付与质量因素，人工选择非最低价供应商。')
  assert.equal(selected.item.reviewStatus, 'manual_review')
  const confirmed = executeConfirmSupplierRecommendationDecisionBatchV11428169(batchId,
    { confirmedBy: '采购员V19' }, { store: fixtureValue.decisionBatchStore,
      taskStore: fixtureValue.taskStore, permissionContext: { role: 'manager' }, now: '2026-08-06T19:30:00.000Z' })
  assert.equal(confirmed.result, 'PASS')
  assert.equal(confirmed.decisionBatchResult.items[0].reviewStatus, 'confirmed')
  assert.equal(confirmed.decisionBatchResult.items[0].reviewer, '采购员V19')
  assert.equal(confirmed.decisionBatchResult.items[0].reviewedAt, '2026-08-06T19:30:00.000Z')
  assert.equal(confirmed.handoff.purchaseOrderCreated, false)
})

test('Canary B requires all 13 material decisions before batch confirmation', () => {
  const fixtureValue = fixture(13)
  const batchId = fixtureValue.entry.activeBatch.batchId
  assert.equal(fixtureValue.entry.activeBatch.items.length, 13)
  const premature = executeConfirmSupplierRecommendationDecisionBatchV11428169(batchId,
    { confirmedBy: '采购员V19' }, { store: fixtureValue.decisionBatchStore,
      taskStore: fixtureValue.taskStore, permissionContext: { role: 'manager' } })
  assert.equal(premature.error, 'DECISION_BATCH_CONFIRMATION_INCOMPLETE')
  for (const item of fixtureValue.entry.activeBatch.items) {
    const selected = executeSelectDecisionBatchSupplierV11428169(batchId, item.materialCode,
      'SUP-NONLOW', `人工复核${item.materialName}的价格、交付、合作及质量证据。`,
      { store: fixtureValue.decisionBatchStore, permissionContext: { role: 'manager' } })
    assert.equal(selected.result, 'PASS')
  }
  const confirmed = executeConfirmSupplierRecommendationDecisionBatchV11428169(batchId,
    { confirmedBy: '采购员V19' }, { store: fixtureValue.decisionBatchStore,
      taskStore: fixtureValue.taskStore, permissionContext: { role: 'manager' } })
  assert.equal(confirmed.result, 'PASS')
  assert.equal(confirmed.decisionBatchResult.items.length, 13)
  assert.equal(confirmed.decisionBatchResult.items.every(item => item.reviewStatus === 'confirmed'), true)
  assert.equal(confirmed.handoff.items.length, 13)
  assert.equal(confirmed.handoff.status, 'handoff_ready')
  assert.equal(confirmed.handoff.purchaseOrderCreated, false)
})
