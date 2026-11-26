import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import {
  PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
  SUPPLIER_RECOMMENDATION_HANDOFF_SOURCE_NODE_CODE,
} from './purchaseOrderCreationGateNodeRuntimeContract.js'

export const SUPPLIER_RECOMMENDATION_PURCHASE_ORDER_GATE_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'SUPPLIER_RECOMMENDATION_TO_PURCHASE_ORDER_CREATION_GATE',
  fromNode: SUPPLIER_RECOMMENDATION_HANDOFF_SOURCE_NODE_CODE,
  toNode: PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
  outputObject: 'SupplierRecommendationDecision',
  inputObject: 'PurchaseOrderCreationGateContext',
  mappingCode: 'MAP_SUPPLIER_RECOMMENDATION_TO_PURCHASE_ORDER_GATE_CONTEXT',
  actionCode: 'CREATE_PURCHASE_ORDER_GATE_CONTEXT',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validateSupplierRecommendationPurchaseOrderGateHandoff(recommendation = {}, context = {}) {
  const valid = recommendation.objectType === 'SupplierRecommendationDecision'
    && ['recommendation_completed', 'approval_ready'].includes(recommendation.status)
    && context.objectType === 'PurchaseOrderCreationGateContext'
    && context.recommendationDecisionNo === recommendation.decisionNo
    && context.recommendedSupplier?.supplierId === recommendation.recommendedSupplierId
    && context.recommendationEvidence?.length > 0
    && context.comparisonEvidence?.priceEvidence?.length > 0
    && context.comparisonEvidence?.deliveryEvidence?.length > 0
    && context.costReference?.totalCost > 0
    && context.sourceChain?.decisionNo === recommendation.decisionNo
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL', valid,
    transferredFields: Object.freeze([
      'recommendedSupplier', 'recommendationEvidence', 'comparisonEvidence', 'costReference', 'sourceChain',
    ]),
    mappingCode: SUPPLIER_RECOMMENDATION_PURCHASE_ORDER_GATE_HANDOFF_CONTRACT.mappingCode,
  })
}
