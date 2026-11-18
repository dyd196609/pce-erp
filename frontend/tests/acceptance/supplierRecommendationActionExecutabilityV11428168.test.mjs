import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationTaskStoreV11428167,
  executeSupplierRecommendationTaskEntryV11428167 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js'
import { createSupplierRecommendationTaskProcessCenterProviderV11428167 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskProcessCenterContextV11428167.js'
import { evaluateSupplierRecommendationActionExecutabilityV11428168,
  SUPPLIER_RECOMMENDATION_ACTION_EXECUTABILITY_RULES_V11428168,
  validateSupplierRecommendationActionResultV11428168 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationActionExecutabilityV11428168.js'
import { createSupplierRecommendationCurrentSelectionV11428166 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationCurrentSelectionV11428166.js'
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
  { supplierCode: 'SUP-168-A', supplierName: '供应商168A', supplierStatus: 'active', source: 'Supplier Master' },
  { supplierCode: 'SUP-168-B', supplierName: '供应商168B', supplierStatus: 'active', source: 'Supplier Master' },
] }) }
const input = {
  priceApprovalId: 'PA-EXEC-168', priceApprovalNo: 'PAP-EXEC-168',
  sourceInquiryNo: 'PI-EXEC-168', sourceRequestNo: 'PR-EXEC-168',
  quoteComparisonId: 'QC-EXEC-168', materialCode: 'MAT-EXEC-168', materialName: '动作验收物料',
  supplierCandidates: [
    { supplierCode: 'SUP-168-A', supplierName: '供应商168A', quotePrice: 100, priceRank: 1 },
    { supplierCode: 'SUP-168-B', supplierName: '供应商168B', quotePrice: 108, priceRank: 2 },
  ],
  priceEvidence: [
    { supplierCode: 'SUP-168-A', currentPrice: 100, priceRank: 1, evidenceSource: 'QuoteComparison' },
    { supplierCode: 'SUP-168-B', currentPrice: 108, priceRank: 2, evidenceSource: 'QuoteComparison' },
  ],
  historicalPriceEvidence: [{ supplierCode: 'SUP-168-A', historyPrice: 96,
    currentPrice: 100, evidenceSource: 'PurchaseOrderHistory' }],
}

function bootstrap() {
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const taskStore = createSupplierRecommendationTaskStoreV11428167({ storage: memoryStorage() })
  const entry = executeSupplierRecommendationTaskEntryV11428167(input,
    { handoffStore, taskStore, qualificationProvider: supplierProvider })
  const source = createSupplierRecommendationRealFactSourceV11428161({ priceApprovalHandoffStore: handoffStore,
    quoteComparisonStore: { listRecommendationPreparations: () => [] }, acceptanceModeResolver: () => false })
  const runtimeStore = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() })
  const provider = createSupplierRecommendationDecisionProviderV1142816({ realFactSource: source,
    quoteComparisonProvider: createSupplierRecommendationProviderV1142811({ sourceStore: source, store: runtimeStore }),
    supplierQualificationProvider: supplierProvider,
    priceReferenceContextProvider: { load: () => ({ records: [] }) } })
  const record = resolveSupplierRecommendationRuntimeContextIdV11428164(
    provider.load().records, entry.task.runtimeContextId).record
  return { entry, record, taskStore, runtimeStore }
}

const evaluation = (actionCode, state, fixture, facts = {}) =>
  evaluateSupplierRecommendationActionExecutabilityV11428168({ actionCode, state,
    permissionContext: { role: 'manager' }, facts: { task: fixture.entry.task,
      runtimeContext: fixture.record.runtimeContext, preparation: fixture.record.preparation, ...facts } })

test('V16.7 taskId entry and process-center identity remain unchanged', () => {
  const fixture = bootstrap()
  const processProvider = createSupplierRecommendationTaskProcessCenterProviderV11428167({
    storage: memoryStorage(), taskStore: fixture.taskStore })
  processProvider.markActive(fixture.entry.task.taskId)
  assert.equal(processProvider.buildPageUrl(),
    `/scm/supplier-recommendations?taskId=${encodeURIComponent(fixture.entry.task.taskId)}`)
  assert.equal(processProvider.resolveTask().runtimeContextId, fixture.entry.task.runtimeContextId)
})

test('all governed actions exist and the page binds visibility to executability', () => {
  assert.deepEqual(Object.keys(SUPPLIER_RECOMMENDATION_ACTION_EXECUTABILITY_RULES_V11428168), [
    'CREATE_RECOMMENDATION_DECISION_CONTEXT', 'START_RECOMMENDATION_EVALUATION',
    'PREPARE_RECOMMENDATION_DECISION', 'START_MANUAL_REVIEW',
    'SELECT_RECOMMENDATION_SUPPLIER', 'CONFIRM_RECOMMENDATION_DECISION',
    'PREPARE_PURCHASE_ORDER_GATE_HANDOFF',
  ])
  const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
  assert.match(page, /actionExecutable\('SELECT_RECOMMENDATION_SUPPLIER'/)
  assert.match(page, /@change="selectCandidateByCode\(material, \$event\)"/)
  assert.match(page, /executeAllowed\('START_RECOMMENDATION_EVALUATION'/)
})

test('state, data and permission guards reject disabled or incomplete actions', () => {
  const fixture = bootstrap()
  const created = executeCreateRecommendationDecisionContext(fixture.record.preparation,
    fixture.runtimeStore, supplierProvider)
  assert.equal(evaluation('START_RECOMMENDATION_EVALUATION', 'created', fixture,
    { context: created.context }).executable, true)
  assert.equal(evaluation('START_RECOMMENDATION_EVALUATION', 'evaluating', fixture,
    { context: created.context }).reason, 'ACTION_STATE_NOT_ALLOWED')
  const denied = evaluateSupplierRecommendationActionExecutabilityV11428168({
    actionCode: 'START_RECOMMENDATION_EVALUATION', state: 'created',
    permissionContext: { role: 'viewer' }, facts: { task: fixture.entry.task,
      runtimeContext: fixture.record.runtimeContext, context: created.context } })
  assert.equal(denied.reason, 'ACTION_PERMISSION_DENIED')
  assert.equal(evaluation('START_RECOMMENDATION_EVALUATION', 'created', fixture,
    { context: null }).reason, 'ACTION_DATA_INCOMPLETE')
  assert.equal(executePrepareRecommendationDecision(created.context, fixture.runtimeStore).result, 'FAIL')
})

test('candidate selection, manual confirmation and Gate follow every declared state', () => {
  const fixture = bootstrap()
  const created = executeCreateRecommendationDecisionContext(fixture.record.preparation,
    fixture.runtimeStore, supplierProvider)
  const startCheck = evaluation('START_RECOMMENDATION_EVALUATION', 'created', fixture,
    { context: created.context })
  const evaluating = executeStartRecommendationEvaluation(created.context, fixture.runtimeStore)
  assert.equal(validateSupplierRecommendationActionResultV11428168(startCheck, evaluating).result, 'PASS')
  const prepareCheck = evaluation('PREPARE_RECOMMENDATION_DECISION', 'evaluating', fixture,
    { context: evaluating.context })
  const prepared = executePrepareRecommendationDecision(evaluating.context, fixture.runtimeStore)
  assert.equal(validateSupplierRecommendationActionResultV11428168(prepareCheck, prepared).result, 'PASS')
  const reviewCheck = evaluation('START_MANUAL_REVIEW', 'decision_prepared', fixture,
    { context: prepared.context })
  const reviewing = executeStartManualReview(prepared.context, fixture.runtimeStore)
  assert.equal(validateSupplierRecommendationActionResultV11428168(reviewCheck, reviewing).result, 'PASS')
  const candidate = reviewing.context.supplierCandidates[1]
  const selectCheck = evaluation('SELECT_RECOMMENDATION_SUPPLIER', 'manual_review', fixture,
    { context: reviewing.context, candidate })
  assert.equal(selectCheck.executable, true)
  const currentSelection = createSupplierRecommendationCurrentSelectionV11428166({
    runtimeContext: fixture.record.runtimeContext, candidate })
  assert.equal(currentSelection.supplierCode, 'SUP-168-B')
  const confirmInput = { selections: [{ materialCode: 'MAT-EXEC-168', supplierCode: 'SUP-168-B' }],
    reason: '根据报价、历史价格及资格证据人工确认。', confirmedBy: '采购员验收168' }
  assert.equal(evaluation('CONFIRM_RECOMMENDATION_DECISION', 'manual_review', fixture,
    { context: reviewing.context, approvalContext: reviewing.approvalContext,
      input: { ...confirmInput, reason: '' } }).reason, 'ACTION_DATA_INCOMPLETE')
  const confirmCheck = evaluation('CONFIRM_RECOMMENDATION_DECISION', 'manual_review', fixture,
    { context: reviewing.context, approvalContext: reviewing.approvalContext, input: confirmInput })
  const confirmed = executeConfirmRecommendationDecision(reviewing.context, reviewing.approvalContext,
    confirmInput, fixture.runtimeStore)
  assert.equal(validateSupplierRecommendationActionResultV11428168(confirmCheck, confirmed).result, 'PASS')
  const gateCheck = evaluation('PREPARE_PURCHASE_ORDER_GATE_HANDOFF', 'confirmed', fixture,
    { context: confirmed.context, decision: confirmed.decision })
  const gate = executePreparePurchaseOrderGateHandoff(confirmed.decision, fixture.runtimeStore)
  assert.equal(validateSupplierRecommendationActionResultV11428168(gateCheck, gate).result, 'PASS')
  assert.equal(gate.handoff.purchaseOrderCreated, false)
})
