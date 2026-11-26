import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRecommendationConfirmationContextV1142816,
  createSupplierRecommendationDecisionContextV1142816,
  createSupplierRecommendationDecisionV1142816 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionDomainV1142816.js'
import { createSupplierRecommendationDecisionProviderV1142816 } from '../../src/meta/providers/supplierRecommendationDecisionProviderV1142816.js'
import { createSupplierRecommendationPurchaseOrderGateHandoffV1142816,
  validateSupplierRecommendationPurchaseOrderGateHandoffV1142816 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationPurchaseOrderGateHandoffV1142816.js'
import { SUPPLIER_RECOMMENDATION_STATES_V1142811 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationStateContractV1142811.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const comparisons = Object.freeze([
  Object.freeze({ comparisonNo: 'QC-001-A', materialCode: 'MAT-001', materialName: '工业铝型材',
    supplierCode: 'SUP-A', supplierName: '甲供应商', unitPrice: 120, totalPrice: 12000,
    deliveryDate: '2026-08-20', comparisonResult: Object.freeze({ priceRank: 2, deliveryRank: 1, validityStatus: 'valid' }) }),
  Object.freeze({ comparisonNo: 'QC-001-B', materialCode: 'MAT-001', materialName: '工业铝型材',
    supplierCode: 'SUP-B', supplierName: '乙供应商', unitPrice: 100, totalPrice: 10000,
    deliveryDate: '2026-08-25', comparisonResult: Object.freeze({ priceRank: 1, deliveryRank: 2, validityStatus: 'valid' }) }),
])
const preparation = Object.freeze({ objectType: 'SupplierRecommendationDecisionPreparationContext',
  recommendationPreparationNo: 'SRDP-001', comparisonPreparationNo: 'QC-001',
  sourceQuoteComparisonId: 'QC-001', sourceInquiryNo: 'PI-001', sourceRequestNo: 'PR-001',
  comparisons, preparationStatus: 'comparison_ready', supplierQualificationFacts: Object.freeze([
    Object.freeze({ supplierCode: 'SUP-A', supplierStatus: 'enabled', supplierCategory: 'A', qualificationStatus: 'qualified' }),
    Object.freeze({ supplierCode: 'SUP-B', supplierStatus: 'enabled', supplierCategory: 'B', qualificationStatus: 'qualified' }),
  ]) })
const priceRecords = comparisons.map(item => Object.freeze({ materialCode: item.materialCode,
  supplierCode: item.supplierCode, priceReferenceContext: Object.freeze({ latestPurchasePrice: 90,
    historicalLowestPurchasePrice: 85, historicalPurchaseCount: 3 }), materialPriceContextType: 'existing_material' }))

test('QuoteComparison, PriceReferenceContext and qualification facts form recommendation context', () => {
  const context = createSupplierRecommendationDecisionContextV1142816({ preparation,
    priceReferenceRecords: priceRecords })
  assert.equal(context.objectType, 'SupplierRecommendationDecisionContext')
  assert.equal(context.sourceQuoteComparisonId, 'QC-001')
  assert.equal(context.materialCode, 'MAT-001')
  assert.equal(context.supplierCandidates.length, 2)
  assert.equal(context.priceEvidence.length, 2)
  assert.equal(context.deliveryEvidence.length, 2)
  assert.equal(context.qualificationEvidence.length, 2)
  assert.equal(context.recommendationEvidence[0].historicalPriceEvidence.latestPurchasePrice, 90)
  assert.equal(context.manualDecisionStatus, 'created')
  assert.equal(context.automaticLowestPriceSelection, false)
  assert.equal(context.aiRecommendation, false)
})

test('SupplierRecommendationDecision is created only by explicit manual confirmation', () => {
  const created = createSupplierRecommendationDecisionContextV1142816({ preparation,
    priceReferenceRecords: priceRecords })
  const context = Object.freeze({ ...created, manualDecisionStatus: 'manual_review' })
  const confirmation = createRecommendationConfirmationContextV1142816({ reviewStatus: 'pending',
    reviewer: '采购员张三', reviewComment: '综合交期与价格人工确认' })
  const decision = createSupplierRecommendationDecisionV1142816(context, confirmation, {
    materialCode: 'MAT-001', supplierCode: 'SUP-A',
    decisionReason: '交期满足项目节点，价格证据已复核', manualReviewer: '采购员张三',
  }, '2026-08-06T10:00:00.000Z')
  assert.deepEqual(Object.keys(decision).filter(key => ['decisionId', 'supplierCode', 'supplierName',
    'materialCode', 'decisionStatus', 'decisionReason', 'manualReviewer', 'manualReviewedAt'].includes(key)),
  ['decisionId', 'supplierCode', 'supplierName', 'materialCode', 'decisionStatus', 'decisionReason',
    'manualReviewer', 'manualReviewedAt'])
  assert.equal(decision.supplierCode, 'SUP-A')
  assert.equal(decision.decisionStatus, 'confirmed')
  assert.equal(decision.purchaseOrderCreated, false)
  assert.throws(() => createSupplierRecommendationDecisionV1142816(context, confirmation, {
    materialCode: 'MAT-001', supplierCode: 'SUP-B', decisionReason: '', manualReviewer: '采购员张三',
  }), /MANUAL_RECOMMENDATION_CONFIRMATION_INCOMPLETE/)
})

test('confirmed decision only creates PurchaseOrderGate handoff', () => {
  const context = Object.freeze({ ...createSupplierRecommendationDecisionContextV1142816({ preparation,
    priceReferenceRecords: priceRecords }), manualDecisionStatus: 'manual_review' })
  const confirmation = createRecommendationConfirmationContextV1142816({ reviewer: '采购员张三' })
  const decision = createSupplierRecommendationDecisionV1142816(context, confirmation, {
    materialCode: 'MAT-001', supplierCode: 'SUP-A', decisionReason: '人工综合确认', manualReviewer: '采购员张三',
  })
  const handoff = createSupplierRecommendationPurchaseOrderGateHandoffV1142816(decision)
  assert.equal(validateSupplierRecommendationPurchaseOrderGateHandoffV1142816(handoff).result, 'PASS')
  assert.equal(handoff.targetObjectType, 'PurchaseOrderCreationGateContext')
  assert.equal(handoff.payload.sourceQuoteComparisonId, 'QC-001')
  assert.equal(handoff.payload.manualConfirmationStatus, 'confirmed')
  assert.equal(handoff.purchaseOrderCreated, false)
  assert.equal(handoff.workflowExecuted, false)
  assert.equal(handoff.businessWriteCount, 0)
})

test('SupplierRecommendationDecisionProvider projects three governed inputs without writes', () => {
  const baseProvider = { load: () => ({ providerCode: 'BASE', records: [{ recommendationPreparationNo: 'SRDP-001',
    sourceInquiryNo: 'PI-001', sourceRequestNo: 'PR-001', recommendationStatus: 'comparison_ready',
    preparation, context: null, decision: null }], approvalContexts: [], contexts: [], decisions: [], handoffs: [] }) }
  const provider = createSupplierRecommendationDecisionProviderV1142816({
    quoteComparisonProvider: baseProvider,
    priceReferenceContextProvider: { load: () => ({ records: priceRecords }) },
    supplierQualificationProvider: { load: () => ({ options: preparation.supplierQualificationFacts }) },
  })
  const facts = provider.load()
  assert.equal(facts.providerCode, 'SupplierRecommendationDecisionProvider')
  assert.deepEqual(facts.inputObjects, ['QuoteComparison', 'PriceReferenceContext', 'SupplierQualificationContext'])
  assert.equal(facts.records[0].recommendationContext.sourceQuoteComparisonId, 'QC-001')
  assert.equal(facts.records[0].recommendationConfirmationContext.objectType, 'RecommendationConfirmationContext')
  assert.equal(facts.businessWriteCount, 0)
  assert.equal(facts.productionDataWritten, false)
})

test('state path and page preserve manual decision and isolation boundaries', () => {
  assert.deepEqual(SUPPLIER_RECOMMENDATION_STATES_V1142811,
    ['created', 'evaluating', 'decision_prepared', 'manual_review', 'confirmed', 'handoff_ready'])
  const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
  for (const region of ['business-context', 'comparison-evidence', 'historical-price-reference',
    'recommendation-candidates', 'manual-confirmation', 'next-action']) {
    assert.match(page, new RegExp(`data-acceptance-region="${region}"`))
  }
  assert.match(page, /supplierRecommendationDecisionProviderV1142816/)
  assert.match(page, /填写人工推荐理由/)
  assert.match(page, /确认人/)
  assert.match(page, /确认时间/)
  assert.match(page, /router\.push\('\/scm\/purchase-order-gate'\)/)
  assert.doesNotMatch(page, /data-process-action="CREATE_PURCHASE_ORDER"/)
  assert.doesNotMatch(page, /data-process-action="AUTO_RECOMMEND_SUPPLIER"/)
})

test('business enhancement does not enter public platform layers', () => {
  for (const file of ['src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceEnterpriseListTable.vue', 'src/meta/pages/EnterpriseOSPage.vue', 'src/router/index.js']) {
    assert.doesNotMatch(read(file), /supplierRecommendationDecisionDomainV1142816|supplierRecommendationDecisionProviderV1142816/, file)
  }
})
