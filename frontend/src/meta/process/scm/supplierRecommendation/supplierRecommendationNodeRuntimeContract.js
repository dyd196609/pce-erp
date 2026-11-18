import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const SUPPLIER_RECOMMENDATION_NODE_CODE = 'SCM_SUPPLIER_RECOMMENDATION_DECISION'
export const QUOTE_COMPARISON_HANDOFF_SOURCE_NODE_CODE = 'SCM_QUOTE_COMPARISON_HANDOFF'

export const SUPPLIER_RECOMMENDATION_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: SUPPLIER_RECOMMENDATION_NODE_CODE,
  nodeName: 'Supplier Recommendation Decision',
  inputObject: 'SupplierRecommendationContext',
  outputObject: 'SupplierRecommendationDecision',
  actions: [
    'CREATE_RECOMMENDATION_CONTEXT',
    'GENERATE_RECOMMENDATION_DECISION',
    'SAVE_RECOMMENDATION_DECISION',
  ],
  stateModel: 'SUPPLIER_RECOMMENDATION_RUNTIME_STATE',
  nextNode: null,
})

export const QUOTE_COMPARISON_HANDOFF_SOURCE = Object.freeze({
  nodeCode: QUOTE_COMPARISON_HANDOFF_SOURCE_NODE_CODE,
  nodeName: 'Quote Comparison Handoff',
  inputObject: 'QuoteComparisonContext',
  outputObject: 'QuoteComparison',
  nextNode: SUPPLIER_RECOMMENDATION_NODE_CODE,
  handoffActionOwner: 'target',
})
