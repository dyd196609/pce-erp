export const QUOTE_COMPARISON_DOMAIN_VERSION = 'V1.14.2.8.18.10'

const text = value => String(value ?? '').trim()
const number = value => Number(value || 0)
const freezeList = values => Object.freeze(values.map(item => Object.freeze({ ...item })))

export function createQuoteComparisonPreparationContext(source = {}, now = new Date().toISOString()) {
  const supplierQuotes = freezeList(source.supplierQuotes || [])
  const materialLines = freezeList(source.materialLines || [])
  if (!text(source.inquiryNo) || !text(source.sourceRequestNo) || !supplierQuotes.length || !materialLines.length) {
    throw new Error('QUOTE_COMPARISON_SOURCE_INCOMPLETE')
  }
  if (supplierQuotes.some(item => !text(item.supplierCode) || !text(item.materialCode)
    || number(item.unitPrice) <= 0 || !text(item.deliveryDate) || !text(item.validityDate))) {
    throw new Error('SUPPLIER_QUOTE_FACT_INCOMPLETE')
  }
  return Object.freeze({
    objectType: 'QuoteComparisonPreparationContext',
    comparisonPreparationNo: `QCP-${text(source.inquiryNo)}`,
    sourceInquiryNo: text(source.inquiryNo),
    sourceRequestNo: text(source.sourceRequestNo),
    supplierQuotes,
    materialLines,
    comparisonStatus: 'supplier_quote_completed',
    createdAt: now,
    updatedAt: now,
    supplierRecommendationCreated: false,
    purchaseOrderCreated: false,
    financeCreated: false,
  })
}

export function createQuoteComparisonModel(quote = {}, ranks = {}, now = new Date().toISOString()) {
  const quantity = number(quote.quantity)
  const unitPrice = number(quote.unitPrice)
  const comparison = {
    objectType: 'QuoteComparison',
    comparisonNo: `QC-${text(quote.inquiryNo)}-${text(quote.materialCode)}-${text(quote.supplierCode)}`,
    materialCode: text(quote.materialCode),
    materialName: text(quote.materialName),
    supplierCode: text(quote.supplierCode),
    supplierName: text(quote.supplierName),
    unitPrice,
    totalPrice: Number((unitPrice * quantity).toFixed(2)),
    deliveryDate: text(quote.deliveryDate),
    validityDate: text(quote.validityDate),
    comparisonResult: Object.freeze({
      priceRank: number(ranks.priceRank),
      deliveryRank: number(ranks.deliveryRank),
      validityStatus: text(ranks.validityStatus),
    }),
    createdAt: now,
  }
  if (!comparison.materialCode || !comparison.materialName || !comparison.supplierCode
    || !comparison.supplierName || comparison.unitPrice <= 0 || !comparison.deliveryDate
    || !comparison.validityDate || comparison.comparisonResult.priceRank <= 0
    || comparison.comparisonResult.deliveryRank <= 0 || !comparison.comparisonResult.validityStatus) {
    throw new Error('QUOTE_COMPARISON_FACT_INCOMPLETE')
  }
  return Object.freeze(comparison)
}

export function validateQuoteComparisonDomain(context = {}, comparisons = []) {
  const contextValid = context.objectType === 'QuoteComparisonPreparationContext'
    && Boolean(context.comparisonPreparationNo && context.sourceInquiryNo && context.sourceRequestNo)
    && Array.isArray(context.supplierQuotes) && context.supplierQuotes.length > 0
    && Array.isArray(context.materialLines) && context.materialLines.length > 0
  const factsValid = comparisons.length > 0 && comparisons.every(item => item.objectType === 'QuoteComparison'
    && item.materialCode && item.supplierCode && item.unitPrice > 0 && item.totalPrice > 0
    && item.deliveryDate && item.validityDate && item.comparisonResult?.priceRank > 0
    && item.comparisonResult?.deliveryRank > 0)
  return Object.freeze({ valid: contextValid && factsValid, result: contextValid && factsValid ? 'PASS' : 'FAIL' })
}
