export const PRICE_CHANGE_EVIDENCE_VERSION = 'V1.14.2.8.18.15'

const finiteOrNull = value => Number.isFinite(Number(value)) ? Number(value) : null

export function createPriceChangeEvidence(input = {}) {
  const historyPrice = finiteOrNull(input.historyPrice)
  const currentPrice = finiteOrNull(input.currentPrice)
  const changeRate = historyPrice > 0 && currentPrice != null
    ? Number(((currentPrice - historyPrice) / historyPrice).toFixed(4)) : null
  return Object.freeze({
    objectType: 'PriceChangeEvidence',
    historyPrice,
    currentPrice,
    changeRate,
    referenceDate: input.referenceDate || '',
    evidenceSource: input.evidenceSource || 'PurchaseOrderHistory',
    reasonablenessDecision: null,
    approvalDecision: null,
    supplierRecommendation: null,
    readOnly: true,
  })
}
