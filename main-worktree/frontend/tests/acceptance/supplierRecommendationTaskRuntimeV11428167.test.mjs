import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationBatchStoreV11428165 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationBatchContextV11428165.js'
import { createSupplierRecommendationTaskStoreV11428167,
  executeSupplierRecommendationBatchTaskEntryV11428167,
  executeSupplierRecommendationTaskEntryV11428167 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js'
import { createSupplierRecommendationTaskProcessCenterProviderV11428167 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskProcessCenterContextV11428167.js'
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
const makeInput = index => ({
  priceApprovalId: `PA-TASK-${index}`, priceApprovalNo: `PAP-TASK-${index}`,
  sourceInquiryNo: 'PI-TASK-001', sourceRequestNo: 'PR-TASK-001',
  quoteComparisonId: `QC-TASK-${index}`, materialCode: `MAT-TASK-${index}`,
  materialName: `任务物料${index}`,
  supplierCandidates: [
    { supplierCode: 'SUP-A', supplierName: '供应商A', quotePrice: 100 + index, priceRank: 1 },
    { supplierCode: 'SUP-B', supplierName: '供应商B', quotePrice: 105 + index, priceRank: 2 },
  ],
  priceEvidence: [
    { supplierCode: 'SUP-A', currentPrice: 100 + index, priceRank: 1, evidenceSource: 'QuoteComparison' },
    { supplierCode: 'SUP-B', currentPrice: 105 + index, priceRank: 2, evidenceSource: 'QuoteComparison' },
  ],
  historicalPriceEvidence: [{ supplierCode: 'SUP-A', historyPrice: 90 + index,
    currentPrice: 100 + index, evidenceSource: 'PurchaseOrderHistory' }],
})

function runtimeFixtures() {
  return { handoffStore: createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() }),
    batchStore: createSupplierRecommendationBatchStoreV11428165({ storage: memoryStorage() }),
    taskStore: createSupplierRecommendationTaskStoreV11428167({ storage: memoryStorage() }) }
}

function buildProvider(handoffStore) {
  const source = createSupplierRecommendationRealFactSourceV11428161({ priceApprovalHandoffStore: handoffStore,
    quoteComparisonStore: { listRecommendationPreparations: () => [] }, acceptanceModeResolver: () => false })
  const runtimeStore = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() })
  const baseProvider = createSupplierRecommendationProviderV1142811({ sourceStore: source, store: runtimeStore })
  const provider = createSupplierRecommendationDecisionProviderV1142816({ realFactSource: source,
    quoteComparisonProvider: baseProvider, supplierQualificationProvider: supplierProvider,
    priceReferenceContextProvider: { load: () => ({ records: [] }) } })
  return { runtimeStore, records: provider.load().records }
}

test('Task model has the exact governed identity fields and single PriceApproval enters by taskId', () => {
  const stores = runtimeFixtures()
  const result = executeSupplierRecommendationTaskEntryV11428167(makeInput(1),
    { ...stores, qualificationProvider: supplierProvider })
  assert.equal(result.result, 'PASS')
  assert.deepEqual(Object.keys(result.task).sort(),
    ['taskId', 'sourcePriceApprovalIds', 'runtimeContextId', 'status', 'currentAssignee'].sort())
  assert.deepEqual(result.task.sourcePriceApprovalIds, ['PA-TASK-1'])
  assert.equal(result.task.status, 'pending_manual_decision')
  assert.equal(result.task.currentAssignee, 'unassigned')
  assert.equal(stores.taskStore.findById(result.task.taskId).runtimeContextId,
    result.handoff.runtimeContext.runtimeContextNo)
})

test('batch PriceApproval creates one SupplierRecommendationTask per material and QuoteComparison', () => {
  const stores = runtimeFixtures()
  const inputs = [makeInput(1), makeInput(2), makeInput(3)]
  const result = executeSupplierRecommendationBatchTaskEntryV11428167(inputs,
    { ...stores, qualificationProvider: supplierProvider })
  assert.equal(result.result, 'PASS')
  assert.equal(result.recommendationTasks.length, 3)
  assert.equal(stores.taskStore.list().length, 3)
  assert.equal(new Set(result.recommendationTasks.map(item => item.taskId)).size, 3)
  assert.equal(new Set(result.recommendationTasks.map(item => item.runtimeContextId)).size, 3)
  assert.equal(stores.handoffStore.listRuntimeContexts().length, 3)
})

test('PriceApproval and Process Center entry resolve the same Task and RuntimeContext', () => {
  const stores = runtimeFixtures()
  const entry = executeSupplierRecommendationTaskEntryV11428167(makeInput(7),
    { ...stores, qualificationProvider: supplierProvider })
  const processProvider = createSupplierRecommendationTaskProcessCenterProviderV11428167({
    storage: memoryStorage(), taskStore: stores.taskStore,
  })
  assert.equal(processProvider.markActive(entry.task.taskId).result, 'PASS')
  assert.equal(processProvider.buildPageUrl(),
    `/scm/supplier-recommendations?taskId=${encodeURIComponent(entry.task.taskId)}`)
  const restoredTask = processProvider.resolveTask()
  assert.equal(restoredTask.taskId, entry.task.taskId)
  assert.equal(restoredTask.runtimeContextId, entry.task.runtimeContextId)
  const { records } = buildProvider(stores.handoffStore)
  const restoredRecord = resolveSupplierRecommendationRuntimeContextIdV11428164(
    records, restoredTask.runtimeContextId).record
  assert.equal(restoredRecord.priceApprovalId, 'PA-TASK-7')
  assert.equal(restoredRecord.runtimeContext.materialCode, 'MAT-TASK-7')
  assert.equal(restoredRecord.runtimeContext.quoteComparisonId, 'QC-TASK-7')
})

test('task-bound candidate Decision confirms and advances the same task to Gate handoff', () => {
  const stores = runtimeFixtures()
  const entry = executeSupplierRecommendationTaskEntryV11428167(makeInput(9),
    { ...stores, qualificationProvider: supplierProvider })
  const { records, runtimeStore } = buildProvider(stores.handoffStore)
  const record = resolveSupplierRecommendationRuntimeContextIdV11428164(
    records, entry.task.runtimeContextId).record
  const created = executeCreateRecommendationDecisionContext(record.preparation, runtimeStore, supplierProvider)
  const evaluating = executeStartRecommendationEvaluation(created.context, runtimeStore)
  const prepared = executePrepareRecommendationDecision(evaluating.context, runtimeStore)
  const reviewing = executeStartManualReview(prepared.context, runtimeStore)
  stores.taskStore.update(entry.task.taskId, { status: 'manual_review' })
  const confirmed = executeConfirmRecommendationDecision(reviewing.context, reviewing.approvalContext, {
    selections: [{ materialCode: 'MAT-TASK-9', supplierCode: 'SUP-B' }],
    reason: '人工比较供应商报价后确认。', confirmedBy: '采购员验收167',
  }, runtimeStore)
  stores.taskStore.update(entry.task.taskId,
    { status: 'confirmed', currentAssignee: '采购员验收167' })
  assert.equal(confirmed.decision.decisionStatus, 'confirmed')
  const gate = executePreparePurchaseOrderGateHandoff(confirmed.decision, runtimeStore)
  stores.taskStore.update(entry.task.taskId, { status: 'handoff_ready' })
  assert.equal(gate.result, 'PASS')
  assert.equal(gate.handoff.purchaseOrderCreated, false)
  const finished = stores.taskStore.findById(entry.task.taskId)
  assert.equal(finished.status, 'handoff_ready')
  assert.equal(finished.currentAssignee, '采购员验收167')
  assert.equal(finished.runtimeContextId, entry.task.runtimeContextId)
})

test('all page entries and process-center projection use TaskId only', () => {
  const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
  const scmRegistry = read('src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js')
  const processRegistry = read('src/meta/process/businessProcessRegistry.js')
  assert.ok(pricePage.includes('taskId:result.task.taskId'))
  assert.ok(pricePage.includes('taskId:result.recommendationTasks[0].taskId'))
  assert.ok(page.includes('route.query.taskId'))
  assert.ok(page.includes('currentTask.value?.runtimeContextId'))
  assert.ok(page.includes('SUPPLIER_RECOMMENDATION_TASK_ENTRY_REQUIRED'))
  assert.ok(!page.includes('route.query.runtimeContextId'))
  assert.ok(!page.includes('route.query.priceApprovalId'))
  assert.ok(scmRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428167'))
  assert.ok(processRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428167'))
  for (const publicFile of ['src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceEnterpriseListTable.vue', 'src/meta/components/ProcessNodeNavigation.vue']) {
    assert.doesNotMatch(read(publicFile), /V11428167/)
  }
})
