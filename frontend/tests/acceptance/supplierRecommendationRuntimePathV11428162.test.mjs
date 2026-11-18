import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161,
  executePriceApprovalSupplierRecommendationHandoffV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationRealFactSourceV11428161,
  createSupplierRecommendationDecisionProviderV1142816 } from '../../src/meta/providers/supplierRecommendationDecisionProviderV1142816.js'
import { createSupplierRecommendationProviderV1142811 } from '../../src/meta/providers/supplierRecommendationProviderV1142811.js'
import { createPurchaseOrderGateHandoffProviderV11428161 } from '../../src/meta/providers/purchaseOrderGateHandoffProviderV11428161.js'
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
  { supplierCode: 'SUP-REAL-A', supplierName: '真实供应商A', supplierStatus: 'active', source: 'Supplier Master' },
  { supplierCode: 'SUP-REAL-B', supplierName: '真实供应商B', supplierStatus: 'active', source: 'Supplier Master' },
] }) }
const input = Object.freeze({
  priceApprovalId: 'PA-RUNTIME-001', priceApprovalNo: 'PAP-RUNTIME-001',
  quoteComparisonId: 'QC-RUNTIME-001', sourceInquiryNo: 'PI-RUNTIME-001',
  sourceRequestNo: 'PR-RUNTIME-001', materialCode: 'MAT-RUNTIME-001', materialName: '精密轴承',
  supplierCandidates: Object.freeze([
    { supplierCode: 'SUP-REAL-A', supplierName: '真实供应商A', quotePrice: 118, priceRank: 2 },
    { supplierCode: 'SUP-REAL-B', supplierName: '真实供应商B', quotePrice: 105, priceRank: 1 },
  ]),
  priceEvidence: Object.freeze([
    { supplierCode: 'SUP-REAL-A', currentPrice: 118, priceRank: 2 },
    { supplierCode: 'SUP-REAL-B', currentPrice: 105, priceRank: 1 },
  ]),
  historicalPriceEvidence: Object.freeze([{ historyPrice: 100, currentPrice: 105, changeRate: 0.05,
    referenceDate: '2026-07-20', evidenceSource: 'Purchase History' }]),
})

function prepareRuntimePath() {
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const handoffResult = executePriceApprovalSupplierRecommendationHandoffV11428161(input, handoffStore, supplierProvider)
  assert.equal(handoffResult.result, 'PASS')
  const runtimeStore = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() })
  const created = executeCreateRecommendationDecisionContext(handoffResult.handoff.preparation,
    runtimeStore, supplierProvider)
  return { handoffStore, handoffResult, runtimeStore, created }
}

test('PriceApproval entry creates the complete real SupplierRecommendationDecisionPreparationContext', () => {
  const { handoffResult } = prepareRuntimePath()
  const context = handoffResult.handoff.preparation
  assert.equal(context.objectType, 'SupplierRecommendationDecisionPreparationContext')
  for (const [field, expected] of Object.entries({ priceApprovalId: 'PA-RUNTIME-001',
    priceApprovalNo: 'PAP-RUNTIME-001', quoteComparisonId: 'QC-RUNTIME-001',
    materialCode: 'MAT-RUNTIME-001', materialName: '精密轴承' })) assert.equal(context[field], expected)
  assert.equal(context.supplierCandidates.length, 2)
  assert.equal(context.priceEvidence.length, 2)
  assert.equal(context.historicalPriceEvidence.length, 1)
  assert.notEqual(context.sourceInquiryNo, 'PI-TEST-SR')
})

test('real handoff has priority and production mode never falls through to demo acceptance facts', () => {
  const { handoffStore } = prepareRuntimePath()
  const source = createSupplierRecommendationRealFactSourceV11428161({
    priceApprovalHandoffStore: handoffStore,
    quoteComparisonStore: { listRecommendationPreparations: () => [{
      recommendationPreparationNo: 'QUOTE-RUNTIME-LOWER-PRIORITY', sourceInquiryNo: 'PI-QUOTE-RUNTIME',
    }] },
    acceptanceFacts: [{ recommendationPreparationNo: 'DEMO', sourceInquiryNo: 'PI-TEST-SR' }],
    acceptanceModeResolver: () => false,
  })
  const facts = source.listRecommendationPreparations()
  assert.equal(facts[0].priceApprovalId, 'PA-RUNTIME-001')
  assert.equal(facts[1].sourceInquiryNo, 'PI-QUOTE-RUNTIME')
  assert.equal(facts.some(item => item.sourceInquiryNo === 'PI-TEST-SR'), false)
  const productionEmpty = createSupplierRecommendationRealFactSourceV11428161({
    priceApprovalHandoffStore: { listPreparations: () => [] },
    quoteComparisonStore: { listRecommendationPreparations: () => [] },
    acceptanceFacts: [{ sourceInquiryNo: 'PI-TEST-SR' }], acceptanceModeResolver: () => false,
  })
  assert.deepEqual(productionEmpty.listRecommendationPreparations(), [])
})

test('provider binds the real PriceApproval, QuoteComparison and material facts', () => {
  const { handoffStore } = prepareRuntimePath()
  const source = createSupplierRecommendationRealFactSourceV11428161({ priceApprovalHandoffStore: handoffStore,
    quoteComparisonStore: { listRecommendationPreparations: () => [] }, acceptanceModeResolver: () => false })
  const base = createSupplierRecommendationProviderV1142811({ sourceStore: source,
    runtimeStore: createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() }) })
  const provider = createSupplierRecommendationDecisionProviderV1142816({ realFactSource: source,
    quoteComparisonProvider: base, supplierQualificationProvider: supplierProvider,
    priceReferenceContextProvider: { load: () => ({ records: [] }) } })
  const current = provider.load().current
  assert.equal(current.priceApprovalNo, 'PAP-RUNTIME-001')
  assert.equal(current.quoteComparisonId, 'QC-RUNTIME-001')
  assert.equal(current.recommendationContext.materials[0].materialCode, 'MAT-RUNTIME-001')
  assert.equal(current.sourceInquiryNo, 'PI-RUNTIME-001')
})

test('manual selection and reason create a confirmed Decision and an auditable Gate handoff only', () => {
  const { runtimeStore, created } = prepareRuntimePath()
  const evaluating = executeStartRecommendationEvaluation(created.context, runtimeStore)
  const prepared = executePrepareRecommendationDecision(evaluating.context, runtimeStore)
  const reviewing = executeStartManualReview(prepared.context, runtimeStore)
  const reason = '基于当前报价比较和历史价格证据，采购员人工确认供应商B。'
  const confirmed = executeConfirmRecommendationDecision(reviewing.context, reviewing.approvalContext, {
    selections: [{ materialCode: 'MAT-RUNTIME-001', supplierCode: 'SUP-REAL-B' }],
    reason, confirmedBy: '采购员王五',
  }, runtimeStore)
  assert.equal(confirmed.result, 'PASS')
  assert.equal(confirmed.decision.objectType, 'SupplierRecommendationDecision')
  assert.equal(confirmed.decision.decisionStatus, 'confirmed')
  assert.equal(confirmed.decision.manualConfirmationStatus, 'confirmed')
  assert.equal(confirmed.decision.selectedRecommendations[0].supplierCode, 'SUP-REAL-B')
  const preparedGate = executePreparePurchaseOrderGateHandoff(confirmed.decision, runtimeStore)
  assert.equal(preparedGate.result, 'PASS')
  assert.equal(preparedGate.handoff.purchaseOrderCreated, false)
  assert.equal(preparedGate.handoff.businessWriteCount, 0)
  const gate = createPurchaseOrderGateHandoffProviderV11428161({ gateContextLoader: () => [],
    gateDecisionLoader: () => [], recommendationStore: runtimeStore }).load().current
  assert.equal(gate.recommendedSupplierName, '真实供应商B')
  assert.equal(gate.recommendationBasis, reason)
  assert.equal(gate.confirmedBy, '采购员王五')
  assert.ok(gate.confirmedAt)
  assert.equal(gate.purchaseOrderCreated, false)
})

test('PROCESS-011 four layers and protected-scope regression remain explicit', () => {
  const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  const recommendationPage = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
  const gatePage = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
  assert.match(pricePage, /priceApprovalNo:row\.priceApprovalNo\|\|row\.priceApprovalId/)
  assert.match(recommendationPage, /CONFIRM_RECOMMENDATION_DECISION/)
  for (const label of ['推荐供应商', '推荐依据', '确认人', '确认时间']) assert.ok(gatePage.includes(label))
  assert.doesNotMatch(pricePage + recommendationPage + gatePage,
    /data-process-action="CREATE_PURCHASE_ORDER"/)
  for (const publicFile of ['src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceEnterpriseListTable.vue', 'src/router/index.js']) {
    assert.doesNotMatch(read(publicFile), /V11428162/)
  }
})
