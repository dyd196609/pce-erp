import { createSupplierQuoteSimpleModel } from '../process/scm/supplierQuote/supplierQuoteSimpleModelV11428121.js'
import { supplierQuoteRuntimeStore } from './supplierQuoteRuntimeStoreV114289.js'

export const SUPPLIER_QUOTE_SIMPLE_RUNTIME_VERSION = 'V1.14.2.8.18.12.1'
const boundary = Object.freeze({ businessWriteCount: 0, productionDataWritten: 0,
  supplierApiCalled: false, supplierSent: false, purchaseOrderCreated: false,
  financeCreated: false, wmsCreated: false, mesCreated: false })

export function saveSupplierQuoteSimple(row = {}, input = {}, store = supplierQuoteRuntimeStore) {
  try {
    const simpleQuote = createSupplierQuoteSimpleModel(row, input)
    const context = store.listContexts().find(item => item.supplierQuoteContextNo === row.supplierQuoteContextNo)
      || row.runtimeContext || null
    if (!context) return Object.freeze({ result: 'FAIL', reason: 'SUPPLIER_QUOTE_CONTEXT_NOT_FOUND', ...boundary })
    const now = new Date().toISOString()
    const quote = store.saveQuote({ ...simpleQuote, objectType: 'SupplierQuote', quoteNo: simpleQuote.quoteId,
      inquiryNo: simpleQuote.sourceInquiryId, supplierQuoteContextNo: row.supplierQuoteContextNo,
      quotePreparationNo: row.quotePreparationNo, sourceRequestNo: row.sourceRequestNo,
      unitPrice: simpleQuote.quotePrice, quoteStatus: 'quotation_received', createdAt: row.quote?.createdAt || now,
      updatedAt: now, simplifiedModel: true })
    const savedContext = store.saveContext({ ...context, quoteStatus: 'supplier_quote_collecting', updatedAt: now })
    return Object.freeze({ result: 'PASS', quote, simpleQuote, context: savedContext, ...boundary })
  } catch (error) {
    return Object.freeze({ result: 'FAIL', reason: error.message, ...boundary })
  }
}

export function completeSupplierQuoteSimple(context = {}, store = supplierQuoteRuntimeStore) {
  if (!context?.supplierQuoteContextNo) return Object.freeze({ result: 'FAIL', reason: 'CONTEXT_REQUIRED', ...boundary })
  const quotes = store.listQuotes().filter(item => item.supplierQuoteContextNo === context.supplierQuoteContextNo)
  const expected = context.materialSupplierCandidates || []
  const allCollected = expected.length > 0 && expected.every(pair => quotes.some(quote =>
    quote.materialCode === pair.materialCode && quote.supplierCode === pair.supplierCode
      && Number(quote.quotePrice ?? quote.unitPrice) > 0))
  if (!allCollected) return Object.freeze({ result: 'FAIL', reason: 'SUPPLIER_QUOTE_COLLECTION_INCOMPLETE', ...boundary })
  const now = new Date().toISOString()
  const readyContext = store.saveContext({ ...context, quoteStatus: 'comparison_ready', updatedAt: now })
  const comparisonPreparation = store.saveComparisonPreparation({ objectType: 'QuoteComparisonPreparationContext',
    comparisonPreparationNo: `QCP-${context.inquiryNo}`, supplierQuoteContextNo: context.supplierQuoteContextNo,
    quotePreparationNo: context.quotePreparationNo, inquiryNo: context.inquiryNo,
    sourceRequestNo: context.sourceRequestNo, quotes, preparationStatus: 'comparison_ready',
    quoteComparisonCreated: false, simplifiedModel: true, createdAt: now })
  return Object.freeze({ result: 'PASS', context: readyContext, comparisonPreparation,
    allCollected: true, ...boundary })
}
