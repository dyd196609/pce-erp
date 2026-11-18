export const SUPPLIER_RECOMMENDATION_GATE_HANDOFF_VERSION_V1142816 = 'V1.14.2.8.18.16'

export function createSupplierRecommendationPurchaseOrderGateHandoffV1142816(decision = {}) {
  const legacyReady = decision.recommendationStatus === 'handoff_ready'
    && decision.manualConfirmationStatus === 'confirmed'
  const confirmedDecision = decision.decisionStatus === 'confirmed' && decision.manualReviewer
  if (decision.objectType !== 'SupplierRecommendationDecision' || (!legacyReady && !confirmedDecision)) {
    throw new Error('CONFIRMED_RECOMMENDATION_NOT_READY_FOR_PURCHASE_ORDER_GATE')
  }
  const recommendedSuppliers = decision.selectedRecommendations || Object.freeze([Object.freeze({
    materialCode: decision.materialCode,
    supplierCode: decision.supplierCode,
    supplierName: decision.supplierName,
  })])
  return Object.freeze({
    objectType: 'SupplierRecommendationPurchaseOrderGateHandoff',
    handoffCode: 'SUPPLIER_RECOMMENDATION_TO_PURCHASE_ORDER_GATE',
    sourceObjectType: decision.objectType,
    sourceObjectId: decision.decisionId || decision.decisionNo,
    targetObjectType: 'PurchaseOrderCreationGateContext',
    payload: Object.freeze({
      sourceQuoteComparisonId: decision.sourceQuoteComparisonId,
      priceApprovalId: decision.priceApprovalId,
      priceApprovalNo: decision.priceApprovalNo || decision.priceApprovalId,
      quoteComparisonId: decision.quoteComparisonId || decision.sourceQuoteComparisonId,
      sourceInquiryNo: decision.sourceInquiryNo,
      recommendedSuppliers,
      recommendationEvidence: decision.recommendationEvidence,
      decisionReason: decision.decisionReason || decision.recommendationReason,
      manualDecisionStatus: decision.decisionStatus || decision.recommendationStatus,
      manualConfirmationStatus: decision.manualConfirmationStatus || 'confirmed',
      manualReviewer: decision.manualReviewer,
      manualReviewedAt: decision.manualReviewedAt || decision.manualConfirmedAt,
    }),
    handoffReady: true,
    purchaseOrderGateCreated: false,
    purchaseOrderCreated: false,
    workflowExecuted: false,
    supplierContacted: false,
    financeWritten: false,
    wmsWritten: false,
    mesWritten: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function validateSupplierRecommendationPurchaseOrderGateHandoffV1142816(handoff = {}) {
  const valid = handoff.objectType === 'SupplierRecommendationPurchaseOrderGateHandoff'
    && handoff.targetObjectType === 'PurchaseOrderCreationGateContext'
    && handoff.payload?.sourceQuoteComparisonId
    && handoff.payload?.recommendedSuppliers?.length > 0
    && handoff.payload?.recommendationEvidence?.length > 0
    && handoff.payload?.manualConfirmationStatus === 'confirmed'
    && handoff.payload?.manualReviewer
    && handoff.payload?.manualReviewedAt
    && handoff.handoffReady === true
    && handoff.purchaseOrderCreated === false
    && handoff.businessWriteCount === 0
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL' })
}
