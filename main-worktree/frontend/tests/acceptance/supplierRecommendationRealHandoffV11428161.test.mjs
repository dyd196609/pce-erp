import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161,
  executePriceApprovalSupplierRecommendationHandoffV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationRealFactSourceV11428161,
  createSupplierRecommendationDecisionProviderV1142816 } from '../../src/meta/providers/supplierRecommendationDecisionProviderV1142816.js'
import { createPurchaseOrderGateHandoffProviderV11428161 } from '../../src/meta/providers/purchaseOrderGateHandoffProviderV11428161.js'
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
  { supplierCode: 'SUP-A', supplierName: '甲供应商', supplierStatus: 'active', supplierCategory: 'A', source: 'Supplier Master' },
  { supplierCode: 'SUP-B', supplierName: '乙供应商', supplierStatus: 'enabled', supplierCategory: 'B', source: 'Supplier Master' },
] }) }
const input = {
  priceApprovalId: 'PA-REAL-001', priceApprovalNo: 'PA-NO-REAL-001', quoteComparisonId: 'QC-REAL-001',
  sourceInquiryNo: 'PI-REAL-001', sourceRequestNo: 'PR-REAL-001',
  materialCode: 'MAT-001', materialName: '工业铝型材',
  supplierCandidates: [
    { supplierCode: 'SUP-A', supplierName: '甲供应商', quotePrice: 120, priceRank: 2 },
    { supplierCode: 'SUP-B', supplierName: '乙供应商', quotePrice: 100, priceRank: 1 },
  ],
  priceEvidence: [
    { supplierCode: 'SUP-A', currentPrice: 120, priceRank: 2 },
    { supplierCode: 'SUP-B', currentPrice: 100, priceRank: 1 },
  ],
  historicalPriceEvidence: [{ historyPrice: 90, currentPrice: 120, changeRate: 0.3333,
    referenceDate: '2026-07-01', evidenceSource: 'Purchase History' }],
  priceReferenceRecords: [{ materialCode: 'MAT-001', supplierCode: 'SUP-A',
    materialPriceContextType: 'existing_material', priceReferenceContext: { latestPurchasePrice: 90 } }],
}

function createRealHandoff() {
  const store = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const result = executePriceApprovalSupplierRecommendationHandoffV11428161(input, store, supplierProvider)
  assert.equal(result.result, 'PASS')
  return { store, result }
}

test('PriceApproval action persists a complete real recommendation handoff before navigation', () => {
  const { store, result } = createRealHandoff()
  assert.equal(result.handoff.sourceObjectType, 'PriceApproval')
  assert.equal(result.handoff.priceApprovalId, input.priceApprovalId)
  assert.equal(result.handoff.priceApprovalNo, input.priceApprovalNo)
  assert.equal(result.handoff.quoteComparisonId, input.quoteComparisonId)
  assert.equal(result.handoff.preparation.supplierCandidates.length, 2)
  assert.equal(result.handoff.preparation.priceEvidence.length, 2)
  assert.equal(result.handoff.preparation.historicalPriceEvidence.length, 1)
  assert.equal(result.handoff.preparation.supplierQualificationFacts.every(item =>
    item.qualificationStatus === 'qualified'), true)
  assert.equal(store.listPreparations()[0].factScope, 'real_price_approval_handoff')
  assert.equal(result.navigationTarget, '/scm/supplier-recommendations')
})

test('production provider prioritizes real PriceApproval and QuoteComparison facts and never defaults to demo facts', () => {
  const { store } = createRealHandoff()
  const source = createSupplierRecommendationRealFactSourceV11428161({
    priceApprovalHandoffStore: store,
    quoteComparisonStore: { listRecommendationPreparations: () => [] },
    acceptanceFacts: [{ recommendationPreparationNo: 'DEMO-ONLY' }],
    acceptanceModeResolver: () => false,
  })
  assert.deepEqual(source.listRecommendationPreparations().map(item => item.priceApprovalId), ['PA-REAL-001'])
  const emptyProduction = createSupplierRecommendationRealFactSourceV11428161({
    priceApprovalHandoffStore: { listPreparations: () => [] },
    quoteComparisonStore: { listRecommendationPreparations: () => [] },
    acceptanceFacts: [{ recommendationPreparationNo: 'DEMO-ONLY' }],
    acceptanceModeResolver: () => false,
  })
  assert.deepEqual(emptyProduction.listRecommendationPreparations(), [])
  const baseProvider = createSupplierRecommendationProviderV1142811({ sourceStore: source,
    runtimeStore: createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() }) })
  const provider = createSupplierRecommendationDecisionProviderV1142816({
    realFactSource: source, quoteComparisonProvider: baseProvider,
    priceReferenceContextProvider: { load: () => ({ records: [] }) },
    supplierQualificationProvider: supplierProvider,
  })
  const facts = provider.load()
  assert.equal(facts.records[0].priceApprovalId, 'PA-REAL-001')
  assert.equal(facts.records[0].quoteComparisonId, 'QC-REAL-001')
  assert.equal(facts.records[0].recommendationContext.materialCode, 'MAT-001')
  assert.equal(facts.businessWriteCount, 0)
})

test('candidate selection and manual reason create a real Decision then only a PurchaseOrderGate handoff', () => {
  const { result } = createRealHandoff()
  const store = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() })
  const created = executeCreateRecommendationDecisionContext(result.handoff.preparation, store, supplierProvider)
  assert.equal(created.result, 'PASS')
  assert.equal(created.context.priceApprovalId, 'PA-REAL-001')
  assert.equal(created.context.supplierCandidates.every(item => item.qualificationStatus === 'qualified'), true)
  const evaluating = executeStartRecommendationEvaluation(created.context, store)
  const prepared = executePrepareRecommendationDecision(evaluating.context, store)
  const reviewing = executeStartManualReview(prepared.context, store)
  const confirmed = executeConfirmRecommendationDecision(reviewing.context, reviewing.approvalContext, {
    selections: [{ materialCode: 'MAT-001', supplierCode: 'SUP-B' }],
    reason: '综合当前报价、历史价格证据与交期，由采购员人工确认。', confirmedBy: '采购员张三',
  }, store)
  assert.equal(confirmed.result, 'PASS')
  assert.equal(confirmed.decision.objectType, 'SupplierRecommendationDecision')
  assert.equal(confirmed.decision.priceApprovalId, 'PA-REAL-001')
  assert.equal(confirmed.decision.priceApprovalNo, 'PA-NO-REAL-001')
  assert.equal(confirmed.decision.quoteComparisonId, 'QC-REAL-001')
  assert.equal(confirmed.decision.manualConfirmationStatus, 'confirmed')
  const gate = executePreparePurchaseOrderGateHandoff(confirmed.decision, store)
  assert.equal(gate.result, 'PASS')
  assert.equal(gate.decision.recommendationStatus, 'handoff_ready')
  assert.equal(gate.handoff.targetObjectType, 'PurchaseOrderCreationGateContext')
  assert.equal(gate.handoff.purchaseOrderCreated, false)
  assert.equal(gate.handoff.businessWriteCount, 0)
  assert.equal(gate.productionDataWritten, undefined)
  const gateProvider = createPurchaseOrderGateHandoffProviderV11428161({
    gateContextLoader: () => [], gateDecisionLoader: () => [], recommendationStore: store,
  })
  const gateFacts = gateProvider.load()
  assert.equal(gateFacts.recordCount, 1)
  assert.equal(gateFacts.current.statusCode, 'handoff_ready')
  assert.equal(gateFacts.current.priceApprovalId, 'PA-REAL-001')
  assert.equal(gateFacts.current.priceApprovalNo, 'PA-NO-REAL-001')
  assert.equal(gateFacts.current.recommendationBasis,
    '综合当前报价、历史价格证据与交期，由采购员人工确认。')
  assert.equal(gateFacts.current.confirmedBy, '采购员张三')
  assert.ok(gateFacts.current.confirmedAt)
  assert.equal(gateFacts.current.purchaseOrderCreated, false)
})

test('qualification is evidence and an unverified quote candidate remains an explicit manual choice', () => {
  const unverifiedProvider = { source: 'Supplier Master', load: () => ({ options: [] }) }
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const handoff = executePriceApprovalSupplierRecommendationHandoffV11428161(input, handoffStore, unverifiedProvider)
  const store = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() })
  const created = executeCreateRecommendationDecisionContext(handoff.handoff.preparation, store, unverifiedProvider)
  assert.equal(created.context.supplierCandidates[0].qualificationStatus, 'unverified')
  const evaluating = executeStartRecommendationEvaluation(created.context, store)
  const prepared = executePrepareRecommendationDecision(evaluating.context, store)
  const reviewing = executeStartManualReview(prepared.context, store)
  const confirmed = executeConfirmRecommendationDecision(reviewing.context, reviewing.approvalContext, {
    selections: [{ materialCode: 'MAT-001', supplierCode: 'SUP-A' }],
    reason: '资格证据待核验，采购人员基于当前报价事实显式确认并保留复核说明。', confirmedBy: '采购员李四',
  }, store)
  assert.equal(confirmed.result, 'PASS')
  assert.equal(confirmed.decision.selectedRecommendations[0].qualificationStatus, 'unverified')
  assert.equal(confirmed.decision.manualConfirmationStatus, 'confirmed')
})

test('page wiring binds the real handoff before route navigation and preserves platform isolation', () => {
  const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  const recommendationPage = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
  const gatePage = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
  const actionStart = pricePage.indexOf("if(action.actionCode==='OPEN_SUPPLIER_RECOMMENDATION')")
  const persistAt = pricePage.indexOf('executePriceApprovalSupplierRecommendationHandoffV11428161', actionStart)
  const routeAt = pricePage.indexOf('router.push', actionStart)
  assert.ok(actionStart >= 0 && persistAt > actionStart && routeAt > persistAt)
  for (const field of ['priceApprovalId', 'quoteComparisonId', 'materialCode', 'supplierCandidates',
    'priceEvidence', 'historicalPriceEvidence']) assert.match(pricePage, new RegExp(field))
  assert.match(recommendationPage, /route\.query\.taskId/)
  assert.doesNotMatch(recommendationPage, /route\.query\.priceApprovalId/)
  assert.match(recommendationPage, /当前核价物料/)
  assert.match(recommendationPage, /当前报价比较/)
  assert.doesNotMatch(recommendationPage, /:disabled="candidate\.qualificationStatus !== 'qualified'"/)
  assert.match(gatePage, /purchaseOrderGateHandoffProviderV11428161/)
  assert.doesNotMatch(pricePage + recommendationPage, /data-process-action="CREATE_PURCHASE_ORDER"/)
  for (const publicFile of ['src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceEnterpriseListTable.vue', 'src/router/index.js']) {
    assert.doesNotMatch(read(publicFile), /V11428161/)
  }
})
