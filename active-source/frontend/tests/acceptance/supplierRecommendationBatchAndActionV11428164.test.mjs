import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationBatchStoreV11428164,
  executeSupplierRecommendationBatchHandoffV11428164 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationBatchContextV11428164.js'
import { resolveSupplierRecommendationRuntimeContextIdV11428164 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationRuntimeContextV11428163.js'
import { createSupplierRecommendationRealFactSourceV11428161,
  createSupplierRecommendationDecisionProviderV1142816 } from '../../src/meta/providers/supplierRecommendationDecisionProviderV1142816.js'
import { createSupplierRecommendationProviderV1142811 } from '../../src/meta/providers/supplierRecommendationProviderV1142811.js'
import { createSupplierRecommendationRuntimeStoreV1142811 } from '../../src/meta/runtime/supplierRecommendationRuntimeStoreV1142811.js'
import { executeConfirmRecommendationDecision, executeCreateRecommendationDecisionContext,
  executePreparePurchaseOrderGateHandoff, executePrepareRecommendationDecision,
  executeStartManualReview, executeStartRecommendationEvaluation } from '../../src/meta/runtime/supplierRecommendationActionRuntimeV1142811.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const memoryStorage = () => {
  const values = new Map()
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
}
const supplierProvider = { source: 'Supplier Master', load: () => ({ options: [
  { supplierCode: 'SUP-A', supplierName: '供应商A', supplierStatus: 'active', source: 'Supplier Master' },
  { supplierCode: 'SUP-B', supplierName: '供应商B', supplierStatus: 'active', source: 'Supplier Master' },
] }) }
const input = (inquiryNo, priceApprovalId, quoteComparisonId, materialCode, supplierCode, price) => ({
  priceApprovalId, priceApprovalNo: `PAP-${priceApprovalId}`, sourceInquiryNo: inquiryNo,
  sourceRequestNo: `PR-${inquiryNo}`, quoteComparisonId, materialCode, materialName: `物料${materialCode}`,
  supplierCandidates: [{ supplierCode, supplierName: `供应商${supplierCode}`, quotePrice: price, priceRank: 1 }],
  priceEvidence: [{ supplierCode, currentPrice: price, priceRank: 1, evidenceSource: 'QuoteComparison' }],
  historicalPriceEvidence: [{ supplierCode, historyPrice: price - 10, currentPrice: price,
    changeRate: 10 / (price - 10), evidenceSource: 'PurchaseOrderHistory' }],
})
const inputs = [
  input('PI-BATCH-001', 'PA-BATCH-001', 'QC-BATCH-A', 'MAT-A', 'SUP-A', 110),
  input('PI-BATCH-001', 'PA-BATCH-001', 'QC-BATCH-B', 'MAT-B', 'SUP-B', 220),
  input('PI-BATCH-002', 'PA-BATCH-002', 'QC-BATCH-C', 'MAT-C', 'SUP-A', 330),
]

function executeBatch(selected = inputs) {
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const batchStore = createSupplierRecommendationBatchStoreV11428164({ storage: memoryStorage() })
  const result = executeSupplierRecommendationBatchHandoffV11428164(selected,
    { handoffStore, batchStore, qualificationProvider: supplierProvider })
  return { result, handoffStore, batchStore }
}

function buildProvider(handoffStore) {
  const realFactSource = createSupplierRecommendationRealFactSourceV11428161({
    priceApprovalHandoffStore: handoffStore,
    quoteComparisonStore: { listRecommendationPreparations: () => [] },
    acceptanceModeResolver: () => false,
  })
  const runtimeStore = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() })
  const baseProvider = createSupplierRecommendationProviderV1142811({ sourceStore: realFactSource,
    store: runtimeStore })
  const provider = createSupplierRecommendationDecisionProviderV1142816({ realFactSource,
    quoteComparisonProvider: baseProvider, supplierQualificationProvider: supplierProvider,
    priceReferenceContextProvider: { load: () => ({ records: [] }) } })
  return { runtimeStore, records: provider.load().records }
}

test('single and same-inquiry batch entries create independent runtime contexts', () => {
  const single = executeBatch([inputs[0]])
  assert.equal(single.result.result, 'PASS')
  assert.equal(single.result.batches.length, 1)
  assert.equal(single.result.batches[0].recommendationContextCount, 1)
  const sameInquiry = executeBatch(inputs.slice(0, 2))
  assert.equal(sameInquiry.result.batches.length, 1)
  const batch = sameInquiry.result.batches[0]
  assert.equal(batch.objectType, 'SupplierRecommendationBatchContext')
  for (const field of ['batchId', 'priceApprovalIds', 'quoteComparisonIds', 'materialCodes',
    'supplierCandidates']) assert.ok(batch[field])
  assert.deepEqual(batch.materialCodes, ['MAT-A', 'MAT-B'])
  assert.equal(new Set(batch.runtimeContextIds).size, 2)
  assert.equal(sameInquiry.handoffStore.listRuntimeContexts().length, 2)
})

test('different inquiries are split into separate Recommendation batch contexts', () => {
  const { result } = executeBatch()
  assert.equal(result.result, 'PASS')
  assert.equal(result.batches.length, 2)
  assert.deepEqual(result.batches.map(item => item.sourceInquiryNo), ['PI-BATCH-001', 'PI-BATCH-002'])
  assert.deepEqual(result.batches.map(item => item.recommendationContextCount), [2, 1])
  assert.equal(result.batches.flatMap(item => item.runtimeContextIds).length, 3)
  assert.equal(result.purchaseOrderCreated, false)
})

test('RuntimeContextId restores exactly one real PriceApproval task and rejects Demo identity', () => {
  const { result, handoffStore } = executeBatch(inputs.slice(0, 2))
  const { records } = buildProvider(handoffStore)
  const runtimeContextId = result.batches[0].runtimeContextIds[1]
  const restored = resolveSupplierRecommendationRuntimeContextIdV11428164(records, runtimeContextId)
  assert.equal(restored.result, 'PASS')
  assert.equal(restored.record.runtimeContext.materialCode, 'MAT-B')
  assert.equal(restored.record.runtimeContext.factScope, 'real_price_approval_handoff')
  assert.notEqual(restored.record.sourceInquiryNo, 'PI-TEST-SR')
  assert.equal(resolveSupplierRecommendationRuntimeContextIdV11428164(records, '').result, 'FAIL')
})

test('restored task completes candidate selection, manual confirmation and Gate handoff only', () => {
  const { result, handoffStore } = executeBatch([inputs[0]])
  const { records, runtimeStore } = buildProvider(handoffStore)
  const current = resolveSupplierRecommendationRuntimeContextIdV11428164(
    records, result.batches[0].runtimeContextIds[0]).record
  const created = executeCreateRecommendationDecisionContext(current.preparation, runtimeStore, supplierProvider)
  const evaluating = executeStartRecommendationEvaluation(created.context, runtimeStore)
  const prepared = executePrepareRecommendationDecision(evaluating.context, runtimeStore)
  const reviewing = executeStartManualReview(prepared.context, runtimeStore)
  const confirmed = executeConfirmRecommendationDecision(reviewing.context, reviewing.approvalContext, {
    selections: [{ materialCode: 'MAT-A', supplierCode: 'SUP-A' }],
    reason: '依据价格、历史价格与资格证据，由采购人员人工确认。', confirmedBy: '采购员王一',
  }, runtimeStore)
  assert.equal(confirmed.result, 'PASS')
  assert.equal(confirmed.decision.decisionStatus, 'confirmed')
  assert.equal(confirmed.decision.manualReviewer, '采购员王一')
  assert.ok(confirmed.decision.manualReviewedAt || confirmed.decision.manualConfirmedAt)
  const gate = executePreparePurchaseOrderGateHandoff(confirmed.decision, runtimeStore)
  assert.equal(gate.result, 'PASS')
  assert.equal(gate.handoff.purchaseOrderCreated, false)
})

test('page business areas expose batch entry, context restore, evidence and manual action contracts', () => {
  const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
  for (const marker of ['BATCH_OPEN_SUPPLIER_RECOMMENDATION',
    'executeSupplierRecommendationBatchHandoffV11428164', 'runtimeContextId:firstBatch.runtimeContextIds[0]',
    'row.quoteComparisonId}::${row.materialCode}::${row.supplierCode}']) {
    assert.ok(pricePage.includes(marker))
  }
  for (const marker of ['supplier-recommendation-batch-context',
    'resolveSupplierRecommendationRuntimeContextIdV11428164', 'router.replace',
    'recommendation-candidates', 'recommendation-evidence', 'CONFIRM_RECOMMENDATION_DECISION',
    'PREPARE_PURCHASE_ORDER_GATE_HANDOFF']) assert.ok(page.includes(marker))
  for (const publicFile of ['src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceEnterpriseListTable.vue', 'src/meta/pages/ProcessCenter.vue',
    'src/router/index.js']) {
    if (fs.existsSync(path.join(root, publicFile))) assert.doesNotMatch(read(publicFile), /V11428164/)
  }
})
