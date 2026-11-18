export const SUPPLIER_RECOMMENDATION_RULES_VERSION = 'V1.14.2.8.13'

export const SUPPLIER_RECOMMENDATION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'SR-PRICE-EVIDENCE', weight: 60, direction: 'lower_is_better' }),
  Object.freeze({ ruleCode: 'SR-DELIVERY-EVIDENCE', weight: 25, direction: 'earlier_is_better' }),
  Object.freeze({ ruleCode: 'SR-VALIDITY-EVIDENCE', weight: 15, direction: 'later_is_better' }),
])

function rankScore(value, values, direction) {
  const sorted = [...new Set(values)].sort((left, right) => direction === 'asc' ? left - right : right - left)
  const rank = sorted.indexOf(value)
  return sorted.length === 1 ? 1 : 1 - rank / (sorted.length - 1)
}

export function evaluateSupplierRecommendation(context = {}) {
  if (context.objectType !== 'SupplierRecommendationContext' || context.status !== 'recommendation_context_created') {
    throw new Error('SUPPLIER_RECOMMENDATION_CONTEXT_NOT_READY')
  }
  const supplierEvidence = context.suppliers.map(supplier => {
    const priceRows = context.priceEvidence.filter(item => item.supplierId === supplier.supplierId)
    const deliveryRows = context.deliveryEvidence.filter(item => item.supplierId === supplier.supplierId)
    const totalPrice = priceRows.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0)
    const latestDelivery = Math.max(...deliveryRows.map(item => Date.parse(item.deliveryDate)))
    const earliestValidity = Math.min(...deliveryRows.map(item => Date.parse(item.validUntil)))
    return { supplierId: supplier.supplierId, supplierName: supplier.supplierName,
      totalPrice, latestDelivery, earliestValidity }
  })
  if (!supplierEvidence.length || supplierEvidence.some(item => !Number.isFinite(item.totalPrice)
    || item.totalPrice <= 0 || !Number.isFinite(item.latestDelivery) || !Number.isFinite(item.earliestValidity))) {
    throw new Error('SUPPLIER_RECOMMENDATION_EVIDENCE_INCOMPLETE')
  }
  const prices = supplierEvidence.map(item => item.totalPrice)
  const deliveries = supplierEvidence.map(item => item.latestDelivery)
  const validities = supplierEvidence.map(item => item.earliestValidity)
  const evaluations = supplierEvidence.map(item => {
    const priceScore = rankScore(item.totalPrice, prices, 'asc') * 60
    const deliveryScore = rankScore(item.latestDelivery, deliveries, 'asc') * 25
    const validityScore = rankScore(item.earliestValidity, validities, 'desc') * 15
    return Object.freeze({ ...item, priceScore, deliveryScore, validityScore,
      totalScore: priceScore + deliveryScore + validityScore,
      risks: Object.freeze(context.riskEvidence.filter(risk => risk.supplierId === item.supplierId)) })
  }).sort((left, right) => right.totalScore - left.totalScore || left.supplierId.localeCompare(right.supplierId))
  return Object.freeze({
    recommendedSupplierId: evaluations[0].supplierId,
    recommendedSupplierName: evaluations[0].supplierName,
    evaluations: Object.freeze(evaluations),
    decisionBasis: Object.freeze(SUPPLIER_RECOMMENDATION_RULES.map(item => item.ruleCode)),
  })
}
