export const QUOTE_COMPARISON_RULES_VERSION = 'V1.14.2.8.12'

export const QUOTE_COMPARISON_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'QC-PRICE-FACT', field: 'unitPrice', mode: 'fact_only' }),
  Object.freeze({ ruleCode: 'QC-DELIVERY-FACT', field: 'deliveryDate', mode: 'fact_only' }),
  Object.freeze({ ruleCode: 'QC-VALIDITY-FACT', field: 'validUntil', mode: 'fact_only' }),
])

const text = value => String(value ?? '').trim()

export function generateQuoteComparisonFacts(context = {}) {
  if (context.objectType !== 'QuoteComparisonContext' || context.status !== 'comparison_context_created') {
    throw new Error('QUOTE_COMPARISON_CONTEXT_NOT_READY')
  }
  const facts = context.quotes.flatMap(quote => quote.materials.map(line => Object.freeze({
    supplierId: quote.supplierId,
    supplierName: quote.supplierName,
    quoteNo: quote.quoteNo,
    materialCode: line.materialCode,
    materialName: line.materialName,
    quantity: line.quantity,
    unit: line.unit,
    currency: quote.currency,
    unitPrice: line.unitPrice,
    deliveryDate: line.deliveryDate,
    validUntil: line.validUntil,
  })))
  if (!facts.length || facts.some(item => !text(item.supplierId) || !text(item.quoteNo)
    || !text(item.materialCode) || item.quantity <= 0 || item.unitPrice <= 0
    || !text(item.deliveryDate) || !text(item.validUntil))) {
    throw new Error('QUOTE_COMPARISON_FACTS_INCOMPLETE')
  }
  return Object.freeze(facts)
}

export function summarizeQuoteComparisonFacts(facts = []) {
  const prices = facts.map(item => item.unitPrice)
  return Object.freeze({
    quoteCount: new Set(facts.map(item => item.quoteNo)).size,
    supplierCount: new Set(facts.map(item => item.supplierId)).size,
    materialCount: new Set(facts.map(item => item.materialCode)).size,
    lowestUnitPrice: Math.min(...prices),
    highestUnitPrice: Math.max(...prices),
    priceSpread: Math.max(...prices) - Math.min(...prices),
    supplierRecommendationCreated: false,
  })
}
