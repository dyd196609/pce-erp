import test from 'node:test'
import assert from 'node:assert/strict'
import { createQuotePreparationProvider } from '../../src/meta/providers/quotePreparationProvider.js'
import { createSupplierQuotePreparationRuntimeAdapter } from '../../src/meta/runtime/supplierQuotePreparationRuntimeAdapterV1142812.js'
import { createSupplierQuoteProvider } from '../../src/meta/providers/supplierQuoteProviderV114289.js'
import { createSupplierQuoteRuntimeStore } from '../../src/meta/runtime/supplierQuoteRuntimeStoreV114289.js'
import { executeCompleteSupplierQuote, executeSaveSupplierQuote } from '../../src/meta/runtime/supplierQuoteActionRuntimeV114289.js'
import { createSupplierQuoteQuoteComparisonRuntimeAdapter } from '../../src/meta/runtime/supplierQuoteQuoteComparisonRuntimeAdapterV1142812.js'
import { createQuoteComparisonProvider } from '../../src/meta/providers/quoteComparisonProviderV1142810.js'
import { createQuoteComparisonRuntimeStore } from '../../src/meta/runtime/quoteComparisonRuntimeStoreV1142810.js'
import { executeCreateQuoteComparisonContext, executeGenerateQuoteComparison,
  executeSaveQuoteComparison } from '../../src/meta/runtime/quoteComparisonActionRuntimeV1142810.js'
import { createSupplierRecommendationDecisionContext } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationDomainModelV1142811.js'

const memoryStorage = () => { const values = new Map(); return { getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value) } }
const preparation = Object.freeze({
  objectType: 'QuotePreparationContext', quotePreparationNo: 'QPC-PI-BIND-001',
  inquiryNo: 'PI-BIND-001', sourceRequestNo: 'PR-BIND-001', preparationStatus: 'quote_preparation_ready',
  materialLines: Object.freeze([{ materialCode: 'MAT-BIND', materialName: '绑定测试物料',
    specification: 'B-01', quantity: 10, requiredDate: '2026-08-28' }]),
  supplierCandidates: Object.freeze([
    { supplierCode: 'SUP-BIND-A', supplierName: '绑定供应商A' },
    { supplierCode: 'SUP-BIND-B', supplierName: '绑定供应商B' },
  ]),
  materialSupplierCandidates: Object.freeze([
    { materialCode: 'MAT-BIND', materialName: '绑定测试物料', quantity: 10,
      requiredDate: '2026-08-28', supplierCode: 'SUP-BIND-A', supplierName: '绑定供应商A' },
    { materialCode: 'MAT-BIND', materialName: '绑定测试物料', quantity: 10,
      requiredDate: '2026-08-28', supplierCode: 'SUP-BIND-B', supplierName: '绑定供应商B' },
  ]), supplierQuoteCreated: false, purchaseOrderCreated: false, productionDataWritten: false,
})
const preparationProvider = createQuotePreparationProvider({ contextLoader: () => [preparation] })

test('PurchaseInquiry 报价准备经只读 Adapter 投影 SupplierQuote 待录入事实', () => {
  const adapter = createSupplierQuotePreparationRuntimeAdapter({ preparationProvider })
  const facts = adapter.load({ inquiryNo: 'PI-BIND-001' })
  assert.equal(facts.contextCount, 1)
  assert.equal(facts.quoteFactCount, 2)
  assert.equal(facts.contexts[0].sourceInquiryId, 'PI-BIND-001')
  assert.equal(facts.contexts[0].quoteStatus, 'supplier_quote_collecting')
  assert.equal(facts.supplierQuotes.every(item => item.objectType === 'SupplierQuote'
    && item.quotePrice === null && item.readOnly), true)
  assert.equal(facts.businessWriteCount, 0)
  assert.equal(facts.productionDataWritten, 0)
})

test('SupplierQuote Provider 无需页面临时状态即可显示询价准备', () => {
  const adapter = createSupplierQuotePreparationRuntimeAdapter({ preparationProvider })
  const store = createSupplierQuoteRuntimeStore({ storage: memoryStorage(), storageKey: 'supplier-binding' })
  const provider = createSupplierQuoteProvider({ store, preparationAdapter: adapter })
  const facts = provider.load({ inquiryNo: 'PI-BIND-001' })
  assert.equal(facts.contextCount, 1)
  assert.equal(facts.recordCount, 2)
  assert.equal(facts.bindingCount, 2)
  assert.equal(facts.records.every(item => item.bindingFact?.objectType === 'SupplierQuote'), true)
  assert.equal(store.listContexts().length, 0)
  assert.equal(store.listQuotes().length, 0)
})

test('人工报价完成后 QuoteComparison Provider 与 SupplierRecommendation 真实兼容', () => {
  const adapter = createSupplierQuotePreparationRuntimeAdapter({ preparationProvider })
  const supplierStore = createSupplierQuoteRuntimeStore({ storage: memoryStorage(), storageKey: 'supplier-complete' })
  const supplierProvider = createSupplierQuoteProvider({ store: supplierStore, preparationAdapter: adapter })
  let context = supplierProvider.load({ inquiryNo: 'PI-BIND-001' }).current
  for (const input of [
    { supplierCode: 'SUP-BIND-A', supplierName: '绑定供应商A', materialCode: 'MAT-BIND',
      materialName: '绑定测试物料', quantity: 10, unitPrice: 88, taxRate: 13,
      deliveryDate: '2026-08-25', validityDate: '2026-09-30' },
    { supplierCode: 'SUP-BIND-B', supplierName: '绑定供应商B', materialCode: 'MAT-BIND',
      materialName: '绑定测试物料', quantity: 10, unitPrice: 91, taxRate: 13,
      deliveryDate: '2026-08-23', validityDate: '2026-10-15' },
  ]) {
    const saved = executeSaveSupplierQuote(context, input, supplierStore)
    assert.equal(saved.result, 'PASS')
    context = saved.context
  }
  const completed = executeCompleteSupplierQuote(context, supplierStore)
  assert.equal(completed.result, 'PASS')
  const bindingAdapter = createSupplierQuoteQuoteComparisonRuntimeAdapter({ sourceProvider: supplierProvider })
  const bindingFacts = bindingAdapter.load({ inquiryNo: 'PI-BIND-001' })
  assert.equal(bindingFacts.contexts[0].sourceReady, true)
  assert.deepEqual(bindingFacts.contexts[0].quotePrice.map(item => item.quotePrice), [88, 91])
  assert.equal(bindingFacts.contexts[0].deliveryDate.length, 2)
  assert.equal(bindingFacts.contexts[0].validityStatus.every(item => item.validityStatus === 'valid'), true)

  const comparisonStore = createQuoteComparisonRuntimeStore({ storage: memoryStorage(), storageKey: 'comparison-binding' })
  const comparisonProvider = createQuoteComparisonProvider({ sourceProvider: supplierProvider,
    store: comparisonStore, runtimeAdapter: bindingAdapter })
  const providerFacts = comparisonProvider.load({ inquiryNo: 'PI-BIND-001' })
  assert.equal(providerFacts.recordCount, 1)
  assert.equal(providerFacts.current.sourceReady, true)
  const created = executeCreateQuoteComparisonContext(providerFacts.current.sourceFacts, comparisonStore)
  const generated = executeGenerateQuoteComparison(created.context, comparisonStore, '2026-08-05')
  const savedComparison = executeSaveQuoteComparison(generated.context, comparisonStore)
  assert.equal(savedComparison.result, 'PASS')
  const supplierMaster = { load: () => ({ options: [
    { supplierCode: 'SUP-BIND-A', supplierStatus: 'active', supplierCategory: 'A', source: 'Supplier Master' },
    { supplierCode: 'SUP-BIND-B', supplierStatus: 'active', supplierCategory: 'B', source: 'Supplier Master' },
  ] }) }
  const recommendationContext = createSupplierRecommendationDecisionContext(savedComparison.nextPreparation, supplierMaster)
  assert.equal(recommendationContext.objectType, 'SupplierRecommendationDecisionContext')
  assert.equal(recommendationContext.sourceQuoteComparisonId, 'QCP-PI-BIND-001')
  assert.equal(recommendationContext.purchaseOrderCreated, false)
})
