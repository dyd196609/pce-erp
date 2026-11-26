import { evaluatePurchaseOrderCreationEligibility } from '../process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateRules.js'

export const PURCHASE_ORDER_CREATION_GATE_RUNTIME_VERSION = 'V1.14.2.8.14'

const contexts = []
const decisions = []

export function createPurchaseOrderCreationGateContext(recommendation = {}) {
  if (recommendation.objectType !== 'SupplierRecommendationDecision'
    || !['recommendation_completed', 'approval_ready'].includes(recommendation.status)
    || !recommendation.recommendedSupplierId || !recommendation.evaluations?.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_NOT_READY_FOR_PURCHASE_ORDER_GATE')
  }
  const recommendedEvaluation = recommendation.evaluations.find(item => item.supplierId === recommendation.recommendedSupplierId)
  const currency = recommendation.priceEvidence?.find(item => item.supplierId === recommendation.recommendedSupplierId)?.currency
  const purchaseDetails = Object.freeze((recommendation.priceEvidence || [])
    .filter(item => item.supplierId === recommendation.recommendedSupplierId)
    .map(item => {
      const delivery = recommendation.deliveryEvidence?.find(evidence => evidence.supplierId === item.supplierId
        && evidence.quoteNo === item.quoteNo && evidence.materialCode === item.materialCode)
      return Object.freeze({ quoteNo: item.quoteNo, materialCode: item.materialCode,
        quantity: item.quantity, currency: item.currency, unitPrice: item.unitPrice,
        lineAmount: item.quantity * item.unitPrice,
        deliveryDate: delivery?.deliveryDate, validUntil: delivery?.validUntil })
    }))
  if (!recommendedEvaluation || !currency || !recommendation.comparisonResult?.comparisonNo) {
    throw new Error('SUPPLIER_RECOMMENDATION_GATE_EVIDENCE_INCOMPLETE')
  }
  const existing = contexts.find(item => item.recommendationDecisionNo === recommendation.decisionNo)
  if (existing) return existing
  const context = Object.freeze({
    objectType: 'PurchaseOrderCreationGateContext',
    contextCode: `POGC-${recommendation.decisionNo}`,
    recommendationDecisionNo: recommendation.decisionNo,
    recommendationStatus: recommendation.status,
    recommendedSupplier: Object.freeze({ supplierId: recommendation.recommendedSupplierId,
      supplierName: recommendation.recommendedSupplierName }),
    recommendationEvidence: Object.freeze(recommendation.evaluations),
    comparisonEvidence: Object.freeze({
      comparisonResult: recommendation.comparisonResult,
      priceEvidence: recommendation.priceEvidence,
      deliveryEvidence: recommendation.deliveryEvidence,
    }),
    costReference: Object.freeze({ currency, totalCost: recommendedEvaluation.totalPrice,
      source: 'supplier_recommendation_evaluation' }),
    purchaseDetails,
    totalQuantity: purchaseDetails.reduce((sum, item) => sum + item.quantity, 0),
    sourceChain: Object.freeze({ inquiryNo: recommendation.inquiryNo,
      comparisonNo: recommendation.comparisonNo, decisionNo: recommendation.decisionNo }),
    status: 'gate_context_created',
    purchaseOrderCreated: false,
    supplierPublished: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  contexts.push(context)
  return context
}

export function evaluatePurchaseOrderGateDecision(context = {}) {
  const evaluation = evaluatePurchaseOrderCreationEligibility(context)
  const decision = Object.freeze({
    objectType: 'PurchaseOrderCreationGateDecision',
    gateDecisionNo: `POGD-${context.recommendationDecisionNo}`,
    contextCode: context.contextCode,
    recommendationDecisionNo: context.recommendationDecisionNo,
    recommendedSupplier: context.recommendedSupplier,
    costReference: context.costReference,
    purchaseDetails: context.purchaseDetails,
    totalQuantity: context.totalQuantity,
    sourceChain: context.sourceChain,
    eligible: evaluation.eligible,
    checks: evaluation.checks,
    blockedReasons: evaluation.blockedReasons,
    status: 'evaluating',
    decisionOnly: true,
    purchaseOrderCreated: false,
    supplierPublished: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  decisions.push(decision)
  return decision
}

export function savePurchaseOrderGateDecision(decision = {}) {
  if (decision.objectType !== 'PurchaseOrderCreationGateDecision' || decision.status !== 'evaluating'
    || !Array.isArray(decision.checks) || !decision.checks.length) {
    throw new Error('PURCHASE_ORDER_GATE_DECISION_NOT_READY_TO_SAVE')
  }
  const saved = Object.freeze({
    ...decision,
    status: decision.eligible ? 'eligible' : 'blocked',
    purchaseOrderCreationAllowed: decision.eligible,
    purchaseOrderCreated: false,
    supplierPublished: false,
    paymentCreated: false,
    productionDataWritten: false,
    persistenceMode: 'session_runtime',
  })
  const index = decisions.findIndex(item => item.gateDecisionNo === decision.gateDecisionNo)
  if (index >= 0) decisions.splice(index, 1, saved)
  return Object.freeze({ result: 'PASS', saved: true, object: saved, productionDataWritten: false })
}

export function listPurchaseOrderCreationGateContexts() {
  return Object.freeze([...contexts])
}

export function listPurchaseOrderCreationGateDecisions() {
  return Object.freeze([...decisions])
}
