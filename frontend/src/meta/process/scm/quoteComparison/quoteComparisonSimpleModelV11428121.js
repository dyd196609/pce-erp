export const QUOTE_COMPARISON_SIMPLE_MODEL_VERSION = 'V1.14.2.8.4.23'

const priceOf = quote => Number(quote.quotePrice ?? quote.unitPrice)

export function createQuoteComparisonSimpleRows(records = []) {
  const groups = new Map()
  for (const record of records.filter(item => item.quoted && Number.isFinite(priceOf(item.quote)))) {
    const key = `${record.inquiryNo}::${record.materialCode}`
    if (!groups.has(key)) groups.set(key, { sourceInquiryId: record.inquiryNo,
      sourceRequestNo: record.sourceRequestNo, materialCode: record.materialCode,
      materialName: record.materialName, quantity: record.quantity, supplierQuotes: [] })
    groups.get(key).supplierQuotes.push(Object.freeze({ supplierCode: record.supplierCode,
      supplierName: record.supplierName, quotationNo: record.quoteId || record.quote?.quoteNo || '',
      quotePrice: priceOf(record.quote), currency: record.quote?.currency || 'CNY',
      remark: record.quote?.remark || '' }))
  }
  return Object.freeze([...groups.values()].map(group => {
    const quotes = [...group.supplierQuotes].sort((a, b) => a.supplierCode.localeCompare(b.supplierCode))
    const minimum = quotes.length ? Math.min(...quotes.map(item => item.quotePrice)) : null
    const rankedPrices = [...new Set(quotes.map(item => item.quotePrice))].sort((a, b) => a - b)
    const supplierQuotes = quotes.map(item => Object.freeze({ ...item,
      priceRank: rankedPrices.indexOf(item.quotePrice) + 1,
      comparisonResult: Object.freeze({ priceRank: rankedPrices.indexOf(item.quotePrice) + 1,
        deliveryRank: 0, validityStatus: 'unknown' }) }))
    const quoteComparisonId = `QC-${group.sourceInquiryId}-${group.materialCode}`
    return Object.freeze({ objectType: 'QuoteComparison', ...group, quoteComparisonId,
      supplierQuotes: Object.freeze(supplierQuotes), lowestQuote: minimum,
      comparisonStatus: 'comparison_completed', automaticRecommendationCreated: false,
      aiAnalysisCreated: false, complexScoreCreated: false })
  }))
}
