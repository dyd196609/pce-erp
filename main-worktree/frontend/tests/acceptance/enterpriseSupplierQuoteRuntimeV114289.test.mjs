import test from 'node:test'
import assert from 'node:assert/strict'

import { createSupplierQuoteRuntimeStore } from '../../src/meta/runtime/supplierQuoteRuntimeStoreV114289.js'
import { executeCompleteSupplierQuote, executeCreateSupplierQuoteContext,
  executeSaveSupplierQuote } from '../../src/meta/runtime/supplierQuoteActionRuntimeV114289.js'
import { createSupplierQuoteProvider } from '../../src/meta/providers/supplierQuoteProviderV114289.js'
import { evaluateSupplierQuoteActionGuard } from '../../src/meta/process/scm/supplierQuote/supplierQuoteActionContractsV114289.js'
import { runSupplierQuoteBusinessWalkthrough,
  validateSupplierQuoteAcceptance } from '../../src/meta/process/scm/supplierQuote/supplierQuoteAcceptanceProfileV114289.js'

const preparation = Object.freeze({
  objectType: 'QuotePreparationContext',
  quotePreparationNo: 'QPC-PI-SQ-114289',
  inquiryNo: 'PI-SQ-114289',
  sourceRequestNo: 'PR-SQ-114289',
  quotationDeadline: '2026-08-31',
  materialLines: Object.freeze([
    Object.freeze({ materialCode: 'MAT-A', materialName: '材料A', specification: 'A-01', quantity: 10, requiredDate: '2026-08-25' }),
    Object.freeze({ materialCode: 'MAT-B', materialName: '材料B', specification: 'B-01', quantity: 20, requiredDate: '2026-08-26' }),
  ]),
  supplierCandidates: Object.freeze([
    Object.freeze({ supplierCode: 'SUP-A', supplierName: '供应商A' }),
    Object.freeze({ supplierCode: 'SUP-B', supplierName: '供应商B' }),
  ]),
  materialSupplierCandidates: Object.freeze([
    Object.freeze({ materialCode: 'MAT-A', materialName: '材料A', supplierCode: 'SUP-A', supplierName: '供应商A' }),
    Object.freeze({ materialCode: 'MAT-B', materialName: '材料B', supplierCode: 'SUP-B', supplierName: '供应商B' }),
  ]),
})

const quoteInputs = preparation.materialSupplierCandidates.map((pair, index) => ({
  ...preparation.materialLines.find(line => line.materialCode === pair.materialCode), ...pair,
  unitPrice: index === 0 ? 18.5 : 31.2, taxRate: 13,
  deliveryDate: index === 0 ? '2026-08-20' : '2026-08-21', validityDate: '2026-08-31', remark: '人工录入',
}))

function storageFixture() {
  const values = new Map()
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, String(value)) }
}

test('QuotePreparationContext hands off complete source fields without creating a quote', () => {
  const store = createSupplierQuoteRuntimeStore({ storage: storageFixture(), storageKey: 'handoff' })
  const result = executeCreateSupplierQuoteContext(preparation, store)
  assert.equal(result.result, 'PASS')
  assert.equal(result.context.quotePreparationNo, preparation.quotePreparationNo)
  assert.equal(result.context.inquiryNo, preparation.inquiryNo)
  assert.equal(result.context.sourceRequestNo, preparation.sourceRequestNo)
  assert.equal(result.context.materialSupplierCandidates.length, 2)
  assert.equal(store.listQuotes().length, 0)
  assert.equal(result.supplierApiCalled, false)
})

test('SupplierQuote is saved per material and supplier combination', () => {
  const store = createSupplierQuoteRuntimeStore({ storage: storageFixture(), storageKey: 'domain' })
  const context = executeCreateSupplierQuoteContext(preparation, store).context
  for (const input of quoteInputs) assert.equal(executeSaveSupplierQuote(context, input, store).result, 'PASS')
  const quotes = store.listQuotes()
  assert.equal(quotes.length, 2)
  assert.deepEqual(quotes.map(item => `${item.materialCode}:${item.supplierCode}`), ['MAT-A:SUP-A', 'MAT-B:SUP-B'])
  assert.equal(executeSaveSupplierQuote(context,
    { ...quoteInputs[0], supplierCode: 'SUP-X' }, store).result, 'FAIL')
})

test('completion is blocked until every combination has a saved quote', () => {
  const store = createSupplierQuoteRuntimeStore({ storage: storageFixture(), storageKey: 'guard' })
  const context = executeCreateSupplierQuoteContext(preparation, store).context
  executeSaveSupplierQuote(context, quoteInputs[0], store)
  const result = executeCompleteSupplierQuote(context, store)
  assert.equal(result.result, 'FAIL')
  assert.equal(result.reason, 'SUPPLIER_QUOTE_COLLECTION_INCOMPLETE')
  assert.equal(store.listComparisonPreparations().length, 0)
})

test('complete collection creates preparation only and reaches comparison_ready', async () => {
  const storage = storageFixture()
  const store = createSupplierQuoteRuntimeStore({ storage, storageKey: 'walkthrough' })
  const walkthrough = await runSupplierQuoteBusinessWalkthrough({ preparation, quotes: quoteInputs, store })
  const acceptance = validateSupplierQuoteAcceptance({ preparation, walkthrough, store })
  assert.equal(walkthrough.context.quoteStatus, 'comparison_ready')
  assert.equal(walkthrough.comparisonPreparation.objectType, 'QuoteComparisonPreparationContext')
  assert.equal(walkthrough.comparisonPreparation.quoteComparisonCreated, false)
  assert.equal(acceptance.status, 'SCM_SUPPLIER_QUOTE_RUNTIME_READY')
  assert.equal(acceptance.result, 'PASS')
})

test('Provider first load, refresh and reopen use the same runtime facts', () => {
  const storage = storageFixture()
  const store = createSupplierQuoteRuntimeStore({ storage, storageKey: 'reload' })
  const context = executeCreateSupplierQuoteContext(preparation, store).context
  quoteInputs.forEach(input => executeSaveSupplierQuote(context, input, store))
  const first = createSupplierQuoteProvider({ store }).load()
  const refresh = createSupplierQuoteProvider({ store }).load()
  const reopenedStore = createSupplierQuoteRuntimeStore({ storage, storageKey: 'reload' })
  const reopened = createSupplierQuoteProvider({ store: reopenedStore }).load()
  assert.equal(first.contextCount, refresh.contextCount)
  assert.equal(first.recordCount, reopened.recordCount)
  assert.equal(first.quoteCount, reopened.quoteCount)
  assert.equal(reopened.factSource, 'supplier_quote_runtime_store')
})

test('forbidden supplier send, external API, order and formal comparison actions stay closed', () => {
  for (const action of ['SEND_SUPPLIER', 'CALL_SUPPLIER_API', 'CREATE_PURCHASE_ORDER', 'CREATE_QUOTE_COMPARISON']) {
    assert.equal(evaluateSupplierQuoteActionGuard(action, 'supplier_quote_collecting').allowed, false)
  }
})
