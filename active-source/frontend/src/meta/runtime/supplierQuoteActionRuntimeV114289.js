import { createSupplierQuoteModel } from '../process/scm/supplierQuote/supplierQuoteDomainModelV114289.js'
import { createQuotePreparationToSupplierQuoteHandoff } from '../process/scm/supplierQuote/quotePreparationToSupplierQuoteHandoffContract.js'
import { evaluateSupplierQuoteActionGuard } from '../process/scm/supplierQuote/supplierQuoteActionContractsV114289.js'
import { resolveSupplierQuoteStateTransition } from '../process/scm/supplierQuote/supplierQuoteStateContractV114289.js'
import { supplierQuoteRuntimeStore } from './supplierQuoteRuntimeStoreV114289.js'

export const SUPPLIER_QUOTE_ACTION_RUNTIME_VERSION = 'V1.14.2.8.18.9'

const protectedBoundary = Object.freeze({ supplierApiCalled: false, supplierSent: false,
  quoteComparisonCreated: false, purchaseOrderCreated: false, financeCreated: false })

export function executeCreateSupplierQuoteContext(preparation = {}, store = supplierQuoteRuntimeStore) {
  const existing = store.findContextByPreparationNo(preparation.quotePreparationNo)
  if (existing) return Object.freeze({ result: 'PASS', idempotent: true, context: existing, ...protectedBoundary })
  const handoff = createQuotePreparationToSupplierQuoteHandoff(preparation)
  if (!handoff.valid) return Object.freeze({ result: 'FAIL', idempotent: false, handoff, ...protectedBoundary })
  const guard = evaluateSupplierQuoteActionGuard('CREATE_SUPPLIER_QUOTE_CONTEXT', handoff.context.quoteStatus)
  const transition = resolveSupplierQuoteStateTransition(handoff.context.quoteStatus, 'CREATE_SUPPLIER_QUOTE_CONTEXT')
  if (!guard.allowed || !transition.allowed) return Object.freeze({ result: 'FAIL', guard, transition, ...protectedBoundary })
  const now = new Date().toISOString()
  const context = store.saveContext({ ...handoff.context, quoteStatus: transition.to, updatedAt: now })
  return Object.freeze({ result: 'PASS', idempotent: false, context, handoff, ...protectedBoundary })
}

export function executeSaveSupplierQuote(context = {}, input = {}, store = supplierQuoteRuntimeStore) {
  const guard = evaluateSupplierQuoteActionGuard('SAVE_SUPPLIER_QUOTE', context.quoteStatus)
  const transition = resolveSupplierQuoteStateTransition(context.quoteStatus, 'SAVE_SUPPLIER_QUOTE')
  if (!guard.allowed || !transition.allowed) return Object.freeze({ result: 'FAIL', guard, transition, ...protectedBoundary })
  try {
    const quote = createSupplierQuoteModel(input, context)
    const saved = store.saveQuote(quote)
    const updatedContext = store.saveContext({ ...context, quoteStatus: transition.to, updatedAt: new Date().toISOString() })
    return Object.freeze({ result: 'PASS', quote: saved, context: updatedContext, ...protectedBoundary })
  } catch (error) {
    return Object.freeze({ result: 'FAIL', error: error.message, context, ...protectedBoundary })
  }
}

export function executeCompleteSupplierQuote(context = {}, store = supplierQuoteRuntimeStore) {
  if (context.quoteStatus === 'comparison_ready') {
    const preparation = store.listComparisonPreparations().find(item =>
      item.supplierQuoteContextNo === context.supplierQuoteContextNo) || null
    return Object.freeze({ result: 'PASS', idempotent: true, context, comparisonPreparation: preparation,
      ...protectedBoundary })
  }
  const guard = evaluateSupplierQuoteActionGuard('COMPLETE_SUPPLIER_QUOTE', context.quoteStatus)
  const completion = resolveSupplierQuoteStateTransition(context.quoteStatus, 'COMPLETE_SUPPLIER_QUOTE')
  const quotes = store.listQuotes().filter(item => item.supplierQuoteContextNo === context.supplierQuoteContextNo)
  const expected = context.materialSupplierCandidates || []
  const allCollected = expected.length > 0 && expected.every(pair => quotes.some(quote =>
    quote.materialCode === pair.materialCode && quote.supplierCode === pair.supplierCode
    && quote.unitPrice > 0 && quote.deliveryDate && quote.validityDate))
  if (!guard.allowed || !completion.allowed || !allCollected) {
    return Object.freeze({ result: 'FAIL', guard, transition: completion, allCollected,
      reason: allCollected ? 'COMPLETE_SUPPLIER_QUOTE_NOT_ALLOWED' : 'SUPPLIER_QUOTE_COLLECTION_INCOMPLETE',
      context, ...protectedBoundary })
  }
  const completed = store.saveContext({ ...context, quoteStatus: completion.to, updatedAt: new Date().toISOString() })
  const readiness = resolveSupplierQuoteStateTransition(completed.quoteStatus, 'MARK_COMPARISON_READY')
  const readyContext = store.saveContext({ ...completed, quoteStatus: readiness.to, updatedAt: new Date().toISOString() })
  const comparisonPreparation = store.saveComparisonPreparation({
    objectType: 'QuoteComparisonPreparationContext',
    comparisonPreparationNo: `QCP-${context.inquiryNo}`,
    supplierQuoteContextNo: context.supplierQuoteContextNo,
    quotePreparationNo: context.quotePreparationNo,
    inquiryNo: context.inquiryNo,
    sourceRequestNo: context.sourceRequestNo,
    quotes,
    preparationStatus: 'comparison_ready',
    quoteComparisonCreated: false,
    createdAt: new Date().toISOString(),
  })
  return Object.freeze({ result: 'PASS', idempotent: false, context: readyContext,
    comparisonPreparation, allCollected: true, ...protectedBoundary })
}
