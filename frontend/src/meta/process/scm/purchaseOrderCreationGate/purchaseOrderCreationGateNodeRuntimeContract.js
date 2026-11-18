import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const PURCHASE_ORDER_CREATION_GATE_NODE_CODE = 'SCM_PURCHASE_ORDER_CREATION_GATE'
export const SUPPLIER_RECOMMENDATION_HANDOFF_SOURCE_NODE_CODE = 'SCM_SUPPLIER_RECOMMENDATION_HANDOFF'

export const PURCHASE_ORDER_CREATION_GATE_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
  nodeName: 'Purchase Order Creation Gate',
  inputObject: 'PurchaseOrderCreationGateContext',
  outputObject: 'PurchaseOrderCreationGateDecision',
  actions: [
    'CREATE_PURCHASE_ORDER_GATE_CONTEXT',
    'EVALUATE_PURCHASE_ORDER_CREATION_ELIGIBILITY',
    'SAVE_PURCHASE_ORDER_GATE_DECISION',
  ],
  stateModel: 'PURCHASE_ORDER_CREATION_GATE_STATE',
  nextNode: null,
})

export const SUPPLIER_RECOMMENDATION_HANDOFF_SOURCE = Object.freeze({
  nodeCode: SUPPLIER_RECOMMENDATION_HANDOFF_SOURCE_NODE_CODE,
  nodeName: 'Supplier Recommendation Handoff',
  inputObject: 'SupplierRecommendationContext',
  outputObject: 'SupplierRecommendationDecision',
  nextNode: PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
  handoffActionOwner: 'target',
})
