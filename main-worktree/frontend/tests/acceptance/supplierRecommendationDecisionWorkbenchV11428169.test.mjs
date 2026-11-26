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
import { createSupplierRecommendationRouteContextResolverV11428171 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationRouteContextResolverV11428171.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const memoryStorage = () => { const values = new Map(); return {
  getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) } }
const qualificationProvider = { source: 'Supplier Master', load: () => ({ options: [
  { supplierCode: 'SUP-A', supplierName: '供应商A', supplierStatus: 'active' },
  { supplierCode: 'SUP-B', supplierName: '供应商B', supplierStatus: 'active' },
] }) }
const makeInput = index => ({
  priceApprovalId: `PA-BATCH-${index}`, priceApprovalNo: `PAP-BATCH-${index}`,
  sourceInquiryNo: 'PI-BATCH-169', sourceRequestNo: 'PR-BATCH-169',
  quoteComparisonId: `QC-BATCH-${index}`, materialCode: `MAT-BATCH-${index}`,
  materialName: `批次物料${index}`,
  supplierCandidates: [
    { supplierCode: 'SUP-A', supplierName: '供应商A', quotePrice: 100 + index, priceRank: 1 },
    { supplierCode: 'SUP-B', supplierName: '供应商B', quotePrice: 105 + index, priceRank: 2 },
  ],
  priceEvidence: [
    { supplierCode: 'SUP-A', currentPrice: 100 + index, priceRank: 1, evidenceSource: 'QuoteComparison' },
    { supplierCode: 'SUP-B', currentPrice: 105 + index, priceRank: 2, evidenceSource: 'QuoteComparison' },
  ],
  historicalPriceEvidence: [{ supplierCode: 'SUP-A', historyPrice: 96 + index,
    currentPrice: 100 + index, evidenceSource: 'PurchaseOrderHistory' }],
})

function fixtures() {
  const stores = {
    handoffStore: createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() }),
    batchStore: createSupplierRecommendationBatchStoreV11428165({ storage: memoryStorage() }),
    taskStore: createSupplierRecommendationTaskStoreV11428167({ storage: memoryStorage() }),
    decisionBatchStore: createSupplierRecommendationDecisionBatchStoreV11428169({ storage: memoryStorage() }),
  }
  const entry = executeSupplierRecommendationDecisionBatchEntryV11428169(
    [makeInput(1), makeInput(2), makeInput(3)], { ...stores, qualificationProvider })
  return { ...stores, entry }
}

test('Decision Batch and Item models have the governed fields and multiple materials', () => {
  const { entry } = fixtures()
  assert.equal(entry.result, 'PASS')
  assert.equal(entry.decisionBatches.length, 1)
  const batch = entry.activeBatch
  assert.deepEqual(Object.keys(batch).sort(),
    ['batchId', 'sourcePriceApprovalBatch', 'sourceQuoteComparisonBatch', 'items'].sort())
  assert.equal(batch.items.length, 3)
  assert.equal(new Set(batch.items.map(item => item.materialCode)).size, 3)
  for (const item of batch.items) assert.deepEqual(Object.keys(item).sort(), [
    'decisionItemId', 'materialCode', 'materialName', 'sourcePriceApprovalIds', 'supplierCandidates',
    'priceEvidence', 'quoteComparisonIds', 'decisionSupplier', 'decisionReason',
    'selectedSupplierCode', 'selectedSupplierName', 'selectionReason', 'reviewStatus',
    'reviewer', 'reviewedAt', 'status'].sort())
})

test('supplier comparison and evidence remain isolated per material', () => {
  const { entry } = fixtures()
  for (const [index, item] of entry.activeBatch.items.entries()) {
    assert.equal(item.supplierCandidates.length, 2)
    assert.equal(item.supplierCandidates[0].quotePrice, 101 + index)
    assert.equal(item.priceEvidence.some(value => value.evidenceSource === 'QuoteComparison'), true)
    assert.equal(item.priceEvidence.some(value => value.evidenceSource === 'PurchaseOrderHistory'), true)
  }
})

test('all material decisions are required before batch confirmation and Gate handoff', () => {
  const fixture = fixtures()
  const batchId = fixture.entry.activeBatch.batchId
  const permissionContext = { role: 'manager' }
  const premature = executeConfirmSupplierRecommendationDecisionBatchV11428169(batchId,
    { confirmedBy: '采购员169' }, { store: fixture.decisionBatchStore,
      taskStore: fixture.taskStore, permissionContext })
  assert.equal(premature.result, 'FAIL')
  for (const item of fixture.entry.activeBatch.items) {
    const selected = executeSelectDecisionBatchSupplierV11428169(batchId, item.materialCode,
      'SUP-B', `基于${item.materialName}报价与历史价格证据人工选择。`,
      { store: fixture.decisionBatchStore, permissionContext })
    assert.equal(selected.result, 'PASS')
    assert.equal(selected.item.status, 'selected')
    assert.equal(selected.item.reviewStatus, 'manual_review')
    assert.equal(selected.item.selectedSupplierCode, 'SUP-B')
  }
  const denied = executeConfirmSupplierRecommendationDecisionBatchV11428169(batchId,
    { confirmedBy: '无权限用户' }, { store: fixture.decisionBatchStore,
      taskStore: fixture.taskStore, permissionContext: { role: 'viewer' } })
  assert.equal(denied.error, 'ACTION_PERMISSION_DENIED')
  const confirmed = executeConfirmSupplierRecommendationDecisionBatchV11428169(batchId,
    { confirmedBy: '采购员169' }, { store: fixture.decisionBatchStore,
      taskStore: fixture.taskStore, permissionContext })
  assert.equal(confirmed.result, 'PASS')
  assert.equal(confirmed.decisionBatchResult.objectType, 'SupplierRecommendationDecisionBatchResult')
  assert.equal(confirmed.decisionBatchResult.items.every(item => item.status === 'confirmed'), true)
  assert.equal(confirmed.decisionBatchResult.items.every(item => item.reviewStatus === 'confirmed'), true)
  assert.equal(confirmed.decisionBatchResult.items.every(item => item.objectType === 'SupplierRecommendationDecision'), true)
  assert.equal(confirmed.decisionBatchResult.items.every(item => item.reviewer === '采购员169'), true)
  assert.equal(confirmed.handoff.status, 'handoff_ready')
  assert.equal(confirmed.handoff.purchaseOrderCreated, false)
})

test('PriceApproval and Process Center enter the same DecisionBatch workbench only', () => {
  const fixture = fixtures()
  const batchId = fixture.entry.activeBatch.batchId
  const resolver = createSupplierRecommendationRouteContextResolverV11428171({ storage: memoryStorage(),
    decisionBatchStore: fixture.decisionBatchStore, taskStore: fixture.taskStore })
  assert.equal(resolver.activate(batchId).pageRoute, '/scm/supplier-recommendation')
  const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  const workbench = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
  const router = read('src/router/index.js')
  assert.match(pricePage, /supplierRecommendationRouteContextResolverV11428171\.activate\(result\.activeBatch\.batchId\)/)
  assert.match(pricePage, /supplierRecommendationRouteContextResolverV11428171\.activate\(firstBatch\.batchId\)/)
  assert.match(workbench, /supplierRecommendationRouteContextResolverV11428171\.resolve\(\)/)
  assert.doesNotMatch(workbench, /route\.query\.(?:taskId|batchId|decisionBatchId|runtimeContextId|priceApprovalId|quoteComparisonId)/)
  assert.match(router, /ScmSupplierRecommendationDecisionWorkbenchPage\.vue/)
})

test('workbench exposes six business areas and executable manual batch actions', () => {
  const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
  for (const region of ['purchase-context', 'material-recommendation-list', 'supplier-comparison',
    'historical-price-reference', 'manual-recommendation-decision', 'batch-confirmation']) {
    assert.match(page, new RegExp(`data-acceptance-region="${region}"`))
  }
  assert.match(page, /SELECT_DECISION_BATCH_SUPPLIER/)
  assert.match(page, /CONFIRM_RECOMMENDATION_DECISION_BATCH/)
  assert.match(page, /batchConfirmExecutable/)
  assert.match(read('src/meta/pages/ScmPurchaseOrderGatePage.vue'), /decision-batch-gate-handoff/)
})
