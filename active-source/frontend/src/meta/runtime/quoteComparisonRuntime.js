import {
  generateQuoteComparisonFacts,
  summarizeQuoteComparisonFacts,
} from '../process/scm/quoteComparison/quoteComparisonRules.js'

export const QUOTE_COMPARISON_RUNTIME_VERSION = 'V1.14.2.8.12'

const contexts = []
const comparisons = []
const text = value => String(value ?? '').trim()

function normalizeQuote(quote = {}) {
  const materials = Object.freeze((quote.lines || []).map((line, index) => Object.freeze({
    lineNo: line.lineNo ?? index + 1,
    materialCode: text(line.materialCode),
    materialName: text(line.materialName),
    quantity: Number(line.quantity || 0),
    unit: text(line.unit),
    unitPrice: Number(line.unitPrice || 0),
    deliveryDate: text(line.deliveryDate),
    validUntil: text(quote.validUntil),
  })))
  return Object.freeze({
    supplierId: text(quote.supplierId),
    supplierName: text(quote.supplierName || quote.supplierId),
    quoteNo: text(quote.quoteNo),
    inquiryNo: text(quote.inquiryNo),
    currency: text(quote.currency),
    materials,
  })
}

export function createQuoteComparisonContext(supplierQuotes = []) {
  const quotes = Object.freeze(supplierQuotes.map(normalizeQuote))
  if (!quotes.length || quotes.some(quote => !quote.supplierId || !quote.quoteNo || !quote.inquiryNo
    || !quote.currency || !quote.materials.length || quote.materials.some(line => !line.materialCode
      || line.quantity <= 0 || line.unitPrice <= 0 || !line.deliveryDate || !line.validUntil))) {
    throw new Error('SUPPLIER_QUOTES_INCOMPLETE')
  }
  const inquiryNos = new Set(quotes.map(item => item.inquiryNo))
  const currencies = new Set(quotes.map(item => item.currency))
  if (inquiryNos.size !== 1) throw new Error('SUPPLIER_QUOTES_INQUIRY_MISMATCH')
  if (currencies.size !== 1) throw new Error('SUPPLIER_QUOTES_CURRENCY_MISMATCH')
  const inquiryNo = quotes[0].inquiryNo
  const existing = contexts.find(item => item.inquiryNo === inquiryNo)
  if (existing) return existing
  const context = Object.freeze({
    objectType: 'QuoteComparisonContext',
    contextCode: `QCC-${inquiryNo}`,
    inquiryNo,
    quotes,
    status: 'comparison_context_created',
    supplierRecommendationCreated: false,
    purchaseOrderCreated: false,
    financeActionExecuted: false,
    productionDataWritten: false,
  })
  contexts.push(context)
  return context
}

export function generateQuoteComparisonFact(context = {}) {
  const facts = generateQuoteComparisonFacts(context)
  const comparison = Object.freeze({
    objectType: 'QuoteComparison',
    comparisonNo: `QC-${context.inquiryNo}`,
    contextCode: context.contextCode,
    inquiryNo: context.inquiryNo,
    facts,
    summary: summarizeQuoteComparisonFacts(facts),
    status: 'comparing',
    resultMode: 'fact_only',
    recommendedSupplierId: null,
    supplierRecommendationCreated: false,
    purchaseOrderCreated: false,
    financeActionExecuted: false,
    productionDataWritten: false,
  })
  comparisons.push(comparison)
  return comparison
}

export function saveQuoteComparison(comparison = {}) {
  if (comparison.objectType !== 'QuoteComparison' || comparison.status !== 'comparing' || !comparison.facts?.length) {
    throw new Error('QUOTE_COMPARISON_NOT_READY_TO_SAVE')
  }
  const completed = Object.freeze({
    ...comparison,
    status: 'comparison_completed',
    recommendationReadinessStatus: 'recommendation_ready',
    recommendedSupplierId: null,
    supplierRecommendationCreated: false,
    purchaseOrderCreated: false,
    financeActionExecuted: false,
    productionDataWritten: false,
    persistenceMode: 'session_runtime',
  })
  const index = comparisons.findIndex(item => item.comparisonNo === comparison.comparisonNo)
  if (index >= 0) comparisons.splice(index, 1, completed)
  return Object.freeze({ result: 'PASS', saved: true, object: completed, productionDataWritten: false })
}

export function markQuoteComparisonRecommendationReady(comparison = {}) {
  if (comparison.status !== 'comparison_completed') throw new Error('QUOTE_COMPARISON_NOT_COMPLETED')
  const ready = Object.freeze({
    ...comparison,
    status: 'recommendation_ready',
    recommendedSupplierId: null,
    supplierRecommendationCreated: false,
    purchaseOrderCreated: false,
    financeActionExecuted: false,
  })
  const index = comparisons.findIndex(item => item.comparisonNo === comparison.comparisonNo)
  if (index >= 0) comparisons.splice(index, 1, ready)
  return ready
}

export function listQuoteComparisonContexts() {
  return Object.freeze([...contexts])
}

export function listQuoteComparisons() {
  return Object.freeze([...comparisons])
}
