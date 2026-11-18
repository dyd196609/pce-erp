import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'

export const QUOTE_COMPARISON_RECOMMENDATION_HANDOFF_V1142811 = createProcessHandoffContract({
  handoffCode: 'QUOTE_COMPARISON_TO_RECOMMENDATION_DECISION_PREPARATION',
  fromNode: 'SCM_QUOTE_COMPARISON', toNode: 'SCM_SUPPLIER_RECOMMENDATION_DECISION',
  outputObject: 'SupplierRecommendationDecisionPreparationContext',
  inputObject: 'SupplierRecommendationDecisionContext',
  mappingCode: 'MAP_COMPARISON_FACTS_TO_MANUAL_RECOMMENDATION_CONTEXT',
  actionCode: 'CREATE_RECOMMENDATION_DECISION_CONTEXT',
  requiredContextKeys: ['recommendationPreparationNo', 'comparisonPreparationNo', 'sourceInquiryNo',
    'sourceRequestNo', 'comparisons', 'preparationStatus'],
})

export const SUPPLIER_RECOMMENDATION_GATE_HANDOFF_V1142811 = createProcessHandoffContract({
  handoffCode: 'SUPPLIER_RECOMMENDATION_TO_PURCHASE_ORDER_GATE',
  fromNode: 'SCM_SUPPLIER_RECOMMENDATION_DECISION', toNode: 'SCM_PURCHASE_ORDER_CREATION_GATE',
  outputObject: 'SupplierRecommendationDecision', inputObject: 'PurchaseOrderCreationGateContext',
  mappingCode: 'MAP_CONFIRMED_RECOMMENDATION_TO_PURCHASE_ORDER_GATE',
  actionCode: 'PREPARE_PURCHASE_ORDER_GATE_HANDOFF',
  requiredContextKeys: ['decisionNo', 'sourceObjectType', 'sourceObjectId', 'sourceInquiryNo',
    'sourceRequestNo', 'selectedRecommendations', 'recommendationReason', 'manualConfirmationStatus'],
})

export function validateQuoteComparisonRecommendationHandoffV1142811(preparation = {}, context = {}) {
  const valid = preparation.objectType === 'SupplierRecommendationDecisionPreparationContext'
    && preparation.preparationStatus === 'comparison_ready'
    && context.objectType === 'SupplierRecommendationDecisionContext'
    && context.sourceObjectId === preparation.recommendationPreparationNo
    && context.sourceInquiryNo === preparation.sourceInquiryNo
    && context.evidence.length === preparation.comparisons.length
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL' })
}

export function createPurchaseOrderGateHandoffV1142811(decision = {}) {
  if (decision.objectType !== 'SupplierRecommendationDecision'
    || decision.recommendationStatus !== 'handoff_ready'
    || decision.manualConfirmationStatus !== 'confirmed') {
    throw new Error('CONFIRMED_RECOMMENDATION_NOT_READY_FOR_GATE_HANDOFF')
  }
  return Object.freeze({
    handoffCode: SUPPLIER_RECOMMENDATION_GATE_HANDOFF_V1142811.handoffCode,
    sourceObjectType: decision.objectType,
    sourceObjectId: decision.decisionNo,
    targetObjectType: 'PurchaseOrderCreationGateContext',
    payload: Object.freeze({ decisionNo: decision.decisionNo, sourceObjectType: decision.sourceObjectType,
      sourceObjectId: decision.sourceObjectId, sourceInquiryNo: decision.sourceInquiryNo,
      sourceRequestNo: decision.sourceRequestNo, selectedRecommendations: decision.selectedRecommendations,
      comparisonEvidence: decision.comparisonEvidence,
      recommendationEvidence: decision.recommendationEvidence,
      recommendationReason: decision.recommendationReason,
      manualConfirmationStatus: decision.manualConfirmationStatus }),
    purchaseOrderGateCreated: false, purchaseOrderCreated: false, supplierContacted: false, financeCreated: false,
  })
}
