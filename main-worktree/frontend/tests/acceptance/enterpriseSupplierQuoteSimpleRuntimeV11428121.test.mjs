import test from 'node:test'
import assert from 'node:assert/strict'
import { createQuotePreparationProvider } from '../../src/meta/providers/quotePreparationProvider.js'
import { createSupplierQuotePreparationRuntimeAdapter } from '../../src/meta/runtime/supplierQuotePreparationRuntimeAdapterV1142812.js'
import { createSupplierQuoteProvider } from '../../src/meta/providers/supplierQuoteProviderV114289.js'
import { createSupplierQuoteRuntimeStore } from '../../src/meta/runtime/supplierQuoteRuntimeStoreV114289.js'
import { saveSupplierQuoteSimple, completeSupplierQuoteSimple } from '../../src/meta/runtime/supplierQuoteSimpleRuntimeV11428121.js'
import { SUPPLIER_QUOTE_SIMPLE_FIELDS } from '../../src/meta/process/scm/supplierQuote/supplierQuoteSimpleModelV11428121.js'
import { createQuoteComparisonSimpleProvider } from '../../src/meta/providers/quoteComparisonSimpleProviderV11428121.js'
import { createPriceApprovalFromQuoteComparisonProvider } from '../../src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js'

const memoryStorage = () => { const values = new Map(); return { getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value) } }
const preparation = Object.freeze({ objectType: 'QuotePreparationContext', quotePreparationNo: 'QPC-PI-SIMPLE-001',
  inquiryNo: 'PI-SIMPLE-001', sourceRequestNo: 'PR-SIMPLE-001', preparationStatus: 'quote_preparation_ready',
  materialLines: Object.freeze([{ materialCode: 'MAT-A', materialName: '物料A', quantity: 10 },
    { materialCode: 'MAT-B', materialName: '物料B', quantity: 5 }]),
  supplierCandidates: Object.freeze([{ supplierCode: 'SUP-A', supplierName: '供应商A' },
    { supplierCode: 'SUP-B', supplierName: '供应商B' }]),
  materialSupplierCandidates: Object.freeze([
    { materialCode: 'MAT-A', materialName: '物料A', quantity: 10, supplierCode: 'SUP-A', supplierName: '供应商A' },
    { materialCode: 'MAT-A', materialName: '物料A', quantity: 10, supplierCode: 'SUP-B', supplierName: '供应商B' },
    { materialCode: 'MAT-B', materialName: '物料B', quantity: 5, supplierCode: 'SUP-A', supplierName: '供应商A' },
    { materialCode: 'MAT-B', materialName: '物料B', quantity: 5, supplierCode: 'SUP-B', supplierName: '供应商B' },
  ]), supplierQuoteCreated: false, purchaseOrderCreated: false, productionDataWritten: false })

function setup() {
  const preparationProvider = createQuotePreparationProvider({ contextLoader: () => [preparation] })
  const adapter = createSupplierQuotePreparationRuntimeAdapter({ preparationProvider })
  const store = createSupplierQuoteRuntimeStore({ storage: memoryStorage(), storageKey: 'simple-runtime' })
  const provider = createSupplierQuoteProvider({ store, preparationAdapter: adapter })
  return { adapter, store, provider }
}

test('所有 SupplierQuotePreparation 明细完整进入 SupplierQuote 列表', () => {
  const { adapter, provider } = setup()
  const preparationFacts = adapter.load()
  const quoteFacts = provider.load()
  assert.equal(preparationFacts.quoteFactCount, 4)
  assert.equal(quoteFacts.recordCount, preparationFacts.quoteFactCount)
  assert.equal(quoteFacts.preparationRecordCount, quoteFacts.recordCount)
  assert.equal(quoteFacts.dataAligned, true)
})

test('报价录入仅要求金额和备注并保持简化业务字段', () => {
  const { store, provider } = setup()
  let facts = provider.load()
  for (const [index, row] of facts.records.entries()) {
    const result = saveSupplierQuoteSimple(row, { quotePrice: 100 + index, remark: `报价${index + 1}` }, store)
    assert.equal(result.result, 'PASS')
    assert.deepEqual(Object.keys(result.simpleQuote), SUPPLIER_QUOTE_SIMPLE_FIELDS)
    for (const field of ['deliveryDate', 'validUntil', 'validityDate', 'taxRate', 'complexScore']) {
      assert.equal(Object.hasOwn(result.simpleQuote, field), false)
    }
    assert.equal(result.businessWriteCount, 0)
    assert.equal(result.productionDataWritten, 0)
  }
  facts = provider.load()
  assert.equal(facts.quoteCount, 4)
  assert.equal(facts.records.every(row => row.simpleQuote && row.quoted), true)
})

test('SupplierQuote 经简化比较承接到 PriceApprovalPreparation', () => {
  const { store, provider } = setup()
  let facts = provider.load()
  facts.records.forEach((row, index) => assert.equal(
    saveSupplierQuoteSimple(row, { quotePrice: [105, 99, 62, 65][index], remark: '' }, store).result, 'PASS'))
  facts = provider.load()
  const complete = completeSupplierQuoteSimple(facts.contexts[0], store)
  assert.equal(complete.result, 'PASS')
  const comparisonProvider = createQuoteComparisonSimpleProvider({ sourceProvider: provider })
  const comparisons = comparisonProvider.load()
  assert.equal(comparisons.recordCount, 2)
  assert.deepEqual(comparisons.records.map(item => item.lowestQuote), [99, 62])
  assert.equal(comparisons.records.every(item => !item.automaticRecommendationCreated
    && !item.aiAnalysisCreated && !item.complexScoreCreated), true)
  const priceProvider = createPriceApprovalFromQuoteComparisonProvider({ sourceProvider: comparisonProvider })
  const priceFacts = priceProvider.load()
  assert.equal(priceFacts.resultCount, 2)
  assert.equal(priceFacts.contexts.every(item => item.sourceObjectType === 'QuoteComparison'
    && item.preparationStatus === 'price_approval_preparation_ready'), true)
  assert.equal(priceFacts.businessWriteCount, 0)
  assert.equal(priceFacts.productionDataWritten, 0)
})
