import { evaluateSupplierRecommendation } from '../process/scm/supplierRecommendation/supplierRecommendationRules.js'

export const SUPPLIER_RECOMMENDATION_RUNTIME_VERSION = 'V1.14.2.8.13'

const contexts = []
const decisions = []
const text = value => String(value ?? '').trim()

export function createSupplierRecommendationContext(comparison = {}) {
  if (comparison.objectType !== 'QuoteComparison'
    || !['comparison_completed', 'recommendation_ready'].includes(comparison.status)
    || !comparison.facts?.length) {
    throw new Error('QUOTE_COMPARISON_NOT_READY_FOR_RECOMMENDATION')
  }
  const supplierMap = new Map()
  for (const fact of comparison.facts) {
    if (!text(fact.supplierId) || !text(fact.quoteNo) || !text(fact.materialCode)
      || Number(fact.quantity) <= 0 || Number(fact.unitPrice) <= 0
      || !text(fact.deliveryDate) || !text(fact.validUntil)) {
      throw new Error('QUOTE_COMPARISON_EVIDENCE_INCOMPLETE')
    }
    supplierMap.set(fact.supplierId, Object.freeze({ supplierId: fact.supplierId, supplierName: fact.supplierName }))
  }
  const suppliers = Object.freeze([...supplierMap.values()])
  const priceEvidence = Object.freeze(comparison.facts.map(item => Object.freeze({
    supplierId: item.supplierId,
    quoteNo: item.quoteNo,
    materialCode: item.materialCode,
    quantity: item.quantity,
    currency: item.currency,
    unitPrice: item.unitPrice,
  })))
  const deliveryEvidence = Object.freeze(comparison.facts.map(item => Object.freeze({
    supplierId: item.supplierId,
    quoteNo: item.quoteNo,
    materialCode: item.materialCode,
    deliveryDate: item.deliveryDate,
    validUntil: item.validUntil,
  })))
  const riskEvidence = Object.freeze(suppliers.map(supplier => {
    const rows = deliveryEvidence.filter(item => item.supplierId === supplier.supplierId)
    const validityBeforeDelivery = rows.some(item => Date.parse(item.validUntil) < Date.parse(item.deliveryDate))
    return Object.freeze({ supplierId: supplier.supplierId,
      riskCode: validityBeforeDelivery ? 'VALIDITY_BEFORE_DELIVERY' : 'NO_BLOCKING_RISK',
      severity: validityBeforeDelivery ? 'high' : 'none', source: 'quote_comparison_evidence' })
  }))
  const existing = contexts.find(item => item.comparisonNo === comparison.comparisonNo)
  if (existing) return existing
  const context = Object.freeze({
    objectType: 'SupplierRecommendationContext',
    contextCode: `SRC-${comparison.comparisonNo}`,
    comparisonNo: comparison.comparisonNo,
    inquiryNo: comparison.inquiryNo,
    comparisonResult: Object.freeze({ comparisonNo: comparison.comparisonNo,
      inquiryNo: comparison.inquiryNo, status: comparison.status, summary: comparison.summary }),
    suppliers,
    priceEvidence,
    deliveryEvidence,
    riskEvidence,
    status: 'recommendation_context_created',
    purchaseOrderCreated: false,
    approvalSubmitted: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  contexts.push(context)
  return context
}

export function generateSupplierRecommendationDecision(context = {}) {
  const evaluation = evaluateSupplierRecommendation(context)
  const decision = Object.freeze({
    objectType: 'SupplierRecommendationDecision',
    decisionNo: `SRD-${context.comparisonNo}`,
    contextCode: context.contextCode,
    comparisonNo: context.comparisonNo,
    inquiryNo: context.inquiryNo,
    recommendedSupplierId: evaluation.recommendedSupplierId,
    recommendedSupplierName: evaluation.recommendedSupplierName,
    evaluations: evaluation.evaluations,
    decisionBasis: evaluation.decisionBasis,
    riskEvidence: context.riskEvidence,
    suppliers: context.suppliers,
    comparisonResult: context.comparisonResult,
    priceEvidence: context.priceEvidence,
    deliveryEvidence: context.deliveryEvidence,
    status: 'evaluating',
    decisionMode: 'explainable_rule_based',
    purchaseOrderCreated: false,
    approvalSubmitted: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  decisions.push(decision)
  return decision
}

export function saveSupplierRecommendationDecision(decision = {}) {
  if (decision.objectType !== 'SupplierRecommendationDecision' || decision.status !== 'evaluating'
    || !decision.recommendedSupplierId || !decision.evaluations?.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_DECISION_NOT_READY_TO_SAVE')
  }
  const completed = Object.freeze({
    ...decision,
    status: 'recommendation_completed',
    approvalReadinessStatus: 'approval_ready',
    purchaseOrderCreated: false,
    approvalSubmitted: false,
    paymentCreated: false,
    productionDataWritten: false,
    persistenceMode: 'session_runtime',
  })
  const index = decisions.findIndex(item => item.decisionNo === decision.decisionNo)
  if (index >= 0) decisions.splice(index, 1, completed)
  return Object.freeze({ result: 'PASS', saved: true, object: completed, productionDataWritten: false })
}

export function markSupplierRecommendationApprovalReady(decision = {}) {
  if (decision.status !== 'recommendation_completed') throw new Error('SUPPLIER_RECOMMENDATION_NOT_COMPLETED')
  const ready = Object.freeze({ ...decision, status: 'approval_ready',
    purchaseOrderCreated: false, approvalSubmitted: false, paymentCreated: false })
  const index = decisions.findIndex(item => item.decisionNo === decision.decisionNo)
  if (index >= 0) decisions.splice(index, 1, ready)
  return ready
}

export function listSupplierRecommendationContexts() {
  return Object.freeze([...contexts])
}

export function listSupplierRecommendationDecisions() {
  return Object.freeze([...decisions])
}
