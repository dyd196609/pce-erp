import test from 'node:test'
import assert from 'node:assert/strict'
import { createSupplierRecommendationRuntimeStoreV1142811 } from '../../src/meta/runtime/supplierRecommendationRuntimeStoreV1142811.js'
import { createSupplierRecommendationProviderV1142811 } from '../../src/meta/providers/supplierRecommendationProviderV1142811.js'
import { evaluateSupplierRecommendationActionGuardV1142811 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationActionContractsV1142811.js'
import { runSupplierRecommendationBusinessWalkthroughV1142811,
  validateSupplierRecommendationAcceptanceV1142811 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationAcceptanceProfileV1142811.js'

const memoryStorage = () => { const values = new Map(); return { getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value) } }
const preparation = Object.freeze({
  objectType: 'SupplierRecommendationDecisionPreparationContext',
  recommendationPreparationNo: 'SRDP-PI-SR-1142811', comparisonPreparationNo: 'QCP-PI-SR-1142811',
  sourceInquiryNo: 'PI-SR-1142811', sourceRequestNo: 'PR-SR-1142811', preparationStatus: 'comparison_ready',
  comparisons: Object.freeze([
    Object.freeze({ objectType: 'QuoteComparison', comparisonNo: 'QC-A-S1', materialCode: 'MAT-A',
      materialName: '材料A', supplierCode: 'SUP-A', supplierName: '供应商A', unitPrice: 10, totalPrice: 100,
      deliveryDate: '2026-08-20', validityDate: '2026-10-01', comparisonResult: { priceRank: 1, deliveryRank: 2, validityStatus: 'valid' } }),
    Object.freeze({ objectType: 'QuoteComparison', comparisonNo: 'QC-A-S2', materialCode: 'MAT-A',
      materialName: '材料A', supplierCode: 'SUP-B', supplierName: '供应商B', unitPrice: 11, totalPrice: 110,
      deliveryDate: '2026-08-18', validityDate: '2026-09-30', comparisonResult: { priceRank: 2, deliveryRank: 1, validityStatus: 'valid' } }),
    Object.freeze({ objectType: 'QuoteComparison', comparisonNo: 'QC-B-S1', materialCode: 'MAT-B',
      materialName: '材料B', supplierCode: 'SUP-A', supplierName: '供应商A', unitPrice: 20, totalPrice: 100,
      deliveryDate: '2026-08-25', validityDate: '2026-10-01', comparisonResult: { priceRank: 1, deliveryRank: 1, validityStatus: 'valid' } }),
  ]), supplierRecommendationCreated: false, purchaseOrderCreated: false, financeCreated: false,
})
const sourceStore = { listRecommendationPreparations: () => [preparation] }
const supplierProvider = { load: () => ({ options: [
  { supplierCode: 'SUP-A', supplierName: '供应商A', supplierStatus: 'active', supplierCategory: 'strategic', source: 'Supplier Master' },
  { supplierCode: 'SUP-B', supplierName: '供应商B', supplierStatus: 'enabled', supplierCategory: 'standard', source: 'Supplier Master' },
] }) }
const manualSelections = [
  { materialCode: 'MAT-A', supplierCode: 'SUP-B' },
  { materialCode: 'MAT-B', supplierCode: 'SUP-A' },
]

test('报价比较事实经人工逐物料确认形成推荐结果和准入交接准备', () => {
  const store = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage(), storageKey: 'sr-flow' })
  const walkthrough = runSupplierRecommendationBusinessWalkthroughV1142811({ preparation, supplierProvider,
    store, sourceStore, manualSelections, recommendationReason: '综合价格、交期与履约资格后人工确认',
    confirmedBy: 'PURCHASER-001' })
  assert.equal(walkthrough.result, 'PASS')
  assert.equal(walkthrough.decision.recommendationStatus, 'handoff_ready')
  assert.equal(walkthrough.decision.manualConfirmationStatus, 'confirmed')
  assert.equal(walkthrough.decision.selectedRecommendations.length, 2)
  assert.equal(walkthrough.decision.decisionId, walkthrough.decision.decisionNo)
  assert.equal(walkthrough.decision.decisionStatus, 'confirmed')
  assert.equal(walkthrough.decision.manualReviewer, 'PURCHASER-001')
  assert.ok(walkthrough.decision.manualConfirmedAt)
  assert.ok(walkthrough.decision.comparisonEvidence.length > 0)
  assert.ok(walkthrough.handoff.payload.recommendationEvidence.length > 0)
  assert.equal(walkthrough.decision.decisionMode, 'manual_only')
  assert.equal(walkthrough.handoff.purchaseOrderGateCreated, false)
  assert.equal(walkthrough.purchaseOrderCreated, false)
  const acceptance = validateSupplierRecommendationAcceptanceV1142811({ walkthrough, preparation,
    supplierProvider, store, sourceStore })
  assert.equal(acceptance.result, 'PASS')
  for (const key of ['process006A', 'process006B', 'process006C', 'process006D', 'process008']) {
    assert.equal(acceptance[key], true, key)
  }
})

test('缺少物料选择、理由或人工身份时禁止确认', () => {
  const store = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage(), storageKey: 'sr-incomplete' })
  const result = runSupplierRecommendationBusinessWalkthroughV1142811({ preparation, supplierProvider, store,
    sourceStore, manualSelections: [{ materialCode: 'MAT-A', supplierCode: 'SUP-A' }],
    recommendationReason: '', confirmedBy: '' })
  assert.equal(result.result, 'FAIL')
  assert.equal(result.steps.at(-1).stepCode, 'PREPARE_GATE_HANDOFF')
  assert.equal(result.steps.find(item => item.stepCode === 'CONFIRM_RECOMMENDATION').result, 'FAIL')
  assert.equal(store.listDecisions().length, 0)
})

test('自动推荐、AI决策和采购订单创建动作始终被阻断', () => {
  for (const action of ['AUTO_RECOMMEND_SUPPLIER', 'AI_DECIDE_SUPPLIER', 'CREATE_PURCHASE_ORDER',
    'SEND_SUPPLIER', 'FINANCE_WRITE', 'WMS_WRITE', 'MES_WRITE']) {
    assert.deepEqual(evaluateSupplierRecommendationActionGuardV1142811(action, 'manual_review'), {
      allowed: false, reason: 'ACTION_OUTSIDE_SUPPLIER_RECOMMENDATION_BOUNDARY',
    })
  }
})

test('Provider 首次、刷新和重开读取相同持久化事实', () => {
  const storage = memoryStorage()
  const store = createSupplierRecommendationRuntimeStoreV1142811({ storage, storageKey: 'sr-reload' })
  runSupplierRecommendationBusinessWalkthroughV1142811({ preparation, supplierProvider, store, sourceStore,
    manualSelections, recommendationReason: '人工确认', confirmedBy: 'PURCHASER-002' })
  const first = createSupplierRecommendationProviderV1142811({ sourceStore, store }).load()
  const reopenedStore = createSupplierRecommendationRuntimeStoreV1142811({ storage, storageKey: 'sr-reload' })
  const reopened = createSupplierRecommendationProviderV1142811({ sourceStore, store: reopenedStore }).load()
  assert.equal(first.recordCount, reopened.recordCount)
  assert.equal(first.contexts.length, reopened.contexts.length)
  assert.equal(first.decisions.length, reopened.decisions.length)
  assert.equal(reopened.current.statusLabel, '采购订单准入交接已就绪')
  assert.equal(reopened.factSource, 'SupplierRecommendationRuntimeStore')
})
