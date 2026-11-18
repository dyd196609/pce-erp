import test from 'node:test'
import assert from 'node:assert/strict'
import { SUPPLIER_RECOMMENDATION_READ_ONLY_QUOTE_COMPARISON_FACTS_V1142811 } from '../../src/meta/acceptance/supplierRecommendationQuoteComparisonTestFactsV1142811.js'
import { createSupplierRecommendationQuoteComparisonFactSourceV1142811 } from '../../src/meta/providers/supplierRecommendationQuoteComparisonFactSourceV1142811.js'
import { createSupplierRecommendationProviderV1142811 } from '../../src/meta/providers/supplierRecommendationProviderV1142811.js'
import { createSupplierRecommendationRuntimeStoreV1142811 } from '../../src/meta/runtime/supplierRecommendationRuntimeStoreV1142811.js'

const memoryStorage = () => { const values = new Map(); return { getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value) } }
const emptyRuntimeSource = Object.freeze({ listRecommendationPreparations: () => Object.freeze([]) })

test('只读 QuoteComparison 验收事实满足推荐页面全部字段', () => {
  const [preparation] = SUPPLIER_RECOMMENDATION_READ_ONLY_QUOTE_COMPARISON_FACTS_V1142811
  assert.equal(Object.isFrozen(preparation), true)
  assert.equal(preparation.readOnly, true)
  assert.equal(preparation.factScope, 'acceptance_read_only')
  assert.equal(preparation.sourceQuoteComparisonId, 'QCP-PI-TEST-SR-001')
  assert.equal(preparation.comparisons.length, 4)
  for (const fact of preparation.comparisons) {
    assert.equal(fact.objectType, 'QuoteComparison')
    assert.ok(fact.supplierCode && fact.supplierName && fact.materialCode && fact.materialName)
    assert.ok(fact.unitPrice > 0 && fact.totalPrice > 0)
    assert.ok(fact.comparisonResult.priceRank > 0 && fact.comparisonResult.deliveryRank > 0)
  }
  assert.equal(preparation.supplierQualificationFacts.every(item => item.qualificationStatus === 'qualified'), true)
  assert.equal(preparation.businessWriteCount, 0)
  assert.equal(preparation.productionDataWritten, 0)
})

test('只读事实仅在 Demo/验收模式加入且不会写入 QuoteComparison Runtime Store', () => {
  let runtimeReadCount = 0
  const runtimeStore = { listRecommendationPreparations() { runtimeReadCount += 1; return Object.freeze([]) } }
  const demoSource = createSupplierRecommendationQuoteComparisonFactSourceV1142811({ runtimeStore,
    acceptanceModeResolver: () => true })
  assert.equal(demoSource.listRecommendationPreparations().length, 1)
  assert.equal(runtimeReadCount, 1)
  assert.equal(demoSource.productionWriteAllowed, false)
  const productionSource = createSupplierRecommendationQuoteComparisonFactSourceV1142811({ runtimeStore,
    acceptanceModeResolver: () => false })
  assert.equal(productionSource.listRecommendationPreparations().length, 0)
})

test('SupplierRecommendation Provider 可直接读取测试事实并投影页面记录', () => {
  const sourceStore = createSupplierRecommendationQuoteComparisonFactSourceV1142811({
    runtimeStore: emptyRuntimeSource, acceptanceModeResolver: () => true })
  const store = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage(),
    storageKey: 'supplier-recommendation-data-binding' })
  const facts = createSupplierRecommendationProviderV1142811({ sourceStore, store }).load()
  assert.equal(facts.recordCount, 1)
  assert.equal(facts.current.sourceQuoteComparisonId, 'QCP-PI-TEST-SR-001')
  assert.equal(facts.current.supplierCount, 3)
  assert.equal(facts.current.materialCount, 2)
  assert.equal(facts.current.readOnly, true)
  assert.equal(facts.current.preparation.comparisons[0].comparisonResult.priceRank, 1)
  assert.equal(store.listContexts().length, 0)
  assert.equal(store.listDecisions().length, 0)
})
