import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationBatchStoreV11428165,
  executeSupplierRecommendationBatchSplitV11428165 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationBatchContextV11428165.js'
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
  { supplierCode: 'SUP-REAL', supplierName: '真实供应商', supplierStatus: 'active', source: 'Supplier Master' },
] }) }
const inputs = Array.from({ length: 19 }, (_, index) => {
  const number = String(index + 1).padStart(2, '0')
  return { priceApprovalId: `PA-SPLIT-${number}`, priceApprovalNo: `PAP-SPLIT-${number}`,
    sourceInquiryNo: 'PI-SPLIT-019', sourceRequestNo: 'PR-SPLIT-019',
    quoteComparisonId: `QC-SPLIT-${number}`, materialCode: `MAT-SPLIT-${number}`,
    materialName: `拆分物料${number}`,
    supplierCandidates: [{ supplierCode: 'SUP-REAL', supplierName: '真实供应商',
      quotePrice: 100 + index, priceRank: 1 }],
    priceEvidence: [{ supplierCode: 'SUP-REAL', currentPrice: 100 + index,
      priceRank: 1, evidenceSource: 'QuoteComparison' }],
    historicalPriceEvidence: [{ supplierCode: 'SUP-REAL', historyPrice: 90 + index,
      currentPrice: 100 + index, evidenceSource: 'PurchaseOrderHistory' }],
  }
})

function execute19() {
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const batchStore = createSupplierRecommendationBatchStoreV11428165({ storage: memoryStorage() })
  const result = executeSupplierRecommendationBatchSplitV11428165(inputs,
    { handoffStore, batchStore, qualificationProvider: supplierProvider })
  return { result, handoffStore, batchStore }
}

function buildProvider(handoffStore) {
  const source = createSupplierRecommendationRealFactSourceV11428161({
    priceApprovalHandoffStore: handoffStore,
    quoteComparisonStore: { listRecommendationPreparations: () => [] }, acceptanceModeResolver: () => false,
  })
  const runtimeStore = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() })
  const baseProvider = createSupplierRecommendationProviderV1142811({ sourceStore: source, store: runtimeStore })
  const provider = createSupplierRecommendationDecisionProviderV1142816({ realFactSource: source,
    quoteComparisonProvider: baseProvider, supplierQualificationProvider: supplierProvider,
    priceReferenceContextProvider: { load: () => ({ records: [] }) } })
  return { runtimeStore, records: provider.load().records }
}

test('batch context is task management only and nineteen records split into nineteen tasks', () => {
  const { result, handoffStore, batchStore } = execute19()
  assert.equal(result.result, 'PASS')
  assert.equal(result.batches.length, 1)
  assert.equal(result.taskCount, 19)
  const { batchContext, tasks } = result.batches[0]
  assert.deepEqual(Object.keys(batchContext).sort(),
    ['batchId', 'objectType', 'sourcePriceApprovalIds', 'taskCount'].sort())
  assert.equal(batchContext.taskCount, 19)
  assert.equal(batchContext.sourcePriceApprovalIds.length, 19)
  assert.equal(tasks.length, 19)
  assert.equal(batchStore.listTasks(batchContext.batchId).length, 19)
  assert.equal(handoffStore.listRuntimeContexts().length, 19)
  assert.equal(new Set(tasks.map(item => item.runtimeContextId)).size, 19)
  for (const forbidden of ['supplierCandidates', 'materialCodes', 'quoteComparisonIds',
    'runtimeContextIds']) assert.equal(batchContext[forbidden], undefined)
})

test('every task resolves one material and one QuoteComparison without cross-task facts', () => {
  const { result, handoffStore } = execute19()
  const { records } = buildProvider(handoffStore)
  assert.equal(records.length, 19)
  for (const task of result.batches[0].tasks) {
    const resolved = resolveSupplierRecommendationRuntimeContextIdV11428164(records, task.runtimeContextId)
    assert.equal(resolved.result, 'PASS')
    assert.equal(resolved.record.runtimeContext.materialCode, task.materialCode)
    assert.equal(resolved.record.runtimeContext.quoteComparisonId, task.quoteComparisonId)
    assert.equal(resolved.record.materialCount, 1)
    assert.ok(resolved.record.preparation.comparisons.every(item => item.materialCode === task.materialCode
      && item.comparisonNo === task.quoteComparisonId))
  }
})

test('one split task completes explicit manual Decision and Gate handoff only', () => {
  const { result, handoffStore } = execute19()
  const { records, runtimeStore } = buildProvider(handoffStore)
  const task = result.batches[0].tasks[18]
  const record = resolveSupplierRecommendationRuntimeContextIdV11428164(records, task.runtimeContextId).record
  const created = executeCreateRecommendationDecisionContext(record.preparation, runtimeStore, supplierProvider)
  const evaluating = executeStartRecommendationEvaluation(created.context, runtimeStore)
  const prepared = executePrepareRecommendationDecision(evaluating.context, runtimeStore)
  const reviewing = executeStartManualReview(prepared.context, runtimeStore)
  const confirmed = executeConfirmRecommendationDecision(reviewing.context, reviewing.approvalContext, {
    selections: [{ materialCode: task.materialCode, supplierCode: 'SUP-REAL' }],
    reason: '采购人员根据当前报价、历史价格和资格证据人工确认。', confirmedBy: '采购员验收165',
  }, runtimeStore)
  assert.equal(confirmed.decision.decisionStatus, 'confirmed')
  assert.equal(confirmed.decision.material.length, 1)
  assert.equal(confirmed.decision.material[0].materialCode, task.materialCode)
  assert.ok(confirmed.decision.manualReviewedAt || confirmed.decision.manualConfirmedAt)
  const gate = executePreparePurchaseOrderGateHandoff(confirmed.decision, runtimeStore)
  assert.equal(gate.result, 'PASS')
  assert.equal(gate.handoff.purchaseOrderCreated, false)
})

test('page binds task list separately and enforces one runtime material with explicit candidate action', () => {
  const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
  const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  for (const marker of ['currentBatchTasks', 'findContextById', 'listTasks', 'singleInstanceValid',
    'SELECT_RECOMMENDATION_CANDIDATE', 'CONFIRM_RECOMMENDATION_DECISION', 'quotePriceLabel',
    'currentRecord.runtimeContext?.materialName']) assert.ok(page.includes(marker))
  assert.ok(pricePage.includes('executeSupplierRecommendationBatchSplitV11428165'))
  assert.ok(pricePage.includes('firstBatch.tasks[0].runtimeContextId'))
  for (const publicFile of ['src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceEnterpriseListTable.vue', 'src/router/index.js']) {
    assert.doesNotMatch(read(publicFile), /V11428165/)
  }
})
