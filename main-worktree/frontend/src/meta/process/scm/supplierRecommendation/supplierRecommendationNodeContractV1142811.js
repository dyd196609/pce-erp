import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const SUPPLIER_RECOMMENDATION_NODE_VERSION_V1142811 = 'V1.14.2.8.18.11'
export const SUPPLIER_RECOMMENDATION_NODE_CODE_V1142811 = 'SCM_SUPPLIER_RECOMMENDATION_DECISION'

export const SUPPLIER_RECOMMENDATION_NODE_CONTRACT_V1142811 = createProcessNodeRuntimeContract({
  nodeCode: SUPPLIER_RECOMMENDATION_NODE_CODE_V1142811,
  nodeName: 'Supplier Recommendation Decision',
  inputObject: 'SupplierRecommendationDecisionPreparationContext',
  outputObject: 'SupplierRecommendationDecision',
  actions: [
    'CREATE_RECOMMENDATION_DECISION_CONTEXT',
    'START_RECOMMENDATION_EVALUATION',
    'PREPARE_RECOMMENDATION_DECISION',
    'START_MANUAL_REVIEW',
    'CONFIRM_RECOMMENDATION_DECISION',
    'PREPARE_PURCHASE_ORDER_GATE_HANDOFF',
  ],
  stateModel: 'SUPPLIER_RECOMMENDATION_DECISION_STATE_V1142811',
  nextNode: 'SCM_PURCHASE_ORDER_CREATION_GATE',
})

export function validateSupplierRecommendationNodeContractV1142811() {
  const value = SUPPLIER_RECOMMENDATION_NODE_CONTRACT_V1142811
  const valid = value.nodeCode === SUPPLIER_RECOMMENDATION_NODE_CODE_V1142811
    && value.inputObject === 'SupplierRecommendationDecisionPreparationContext'
    && value.outputObject === 'SupplierRecommendationDecision'
    && value.actions.length === 6 && value.nextNode === 'SCM_PURCHASE_ORDER_CREATION_GATE'
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', contract: value })
}
