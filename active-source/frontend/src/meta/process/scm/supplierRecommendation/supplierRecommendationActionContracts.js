import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { SUPPLIER_RECOMMENDATION_NODE_CODE } from './supplierRecommendationNodeRuntimeContract.js'

const base = {
  nodeCode: SUPPLIER_RECOMMENDATION_NODE_CODE,
  objectType: 'SupplierRecommendationDecision',
  stateModel: 'SUPPLIER_RECOMMENDATION_RUNTIME_STATE',
}

export const SUPPLIER_RECOMMENDATION_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'CREATE_RECOMMENDATION_CONTEXT',
    actionName: 'Create Recommendation Context',
    buttonCode: 'create-recommendation-context',
    allowedFromStates: ['quote_comparison_ready'],
    resultState: 'recommendation_context_created',
  }),
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'GENERATE_RECOMMENDATION_DECISION',
    actionName: 'Generate Recommendation Decision',
    buttonCode: 'generate-recommendation-decision',
    allowedFromStates: ['recommendation_context_created'],
    resultState: 'evaluating',
  }),
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'SAVE_RECOMMENDATION_DECISION',
    actionName: 'Save Recommendation Decision',
    buttonCode: 'save-recommendation-decision',
    allowedFromStates: ['evaluating'],
    resultState: 'recommendation_completed',
  }),
])

export const SUPPLIER_RECOMMENDATION_UI_ACTION_CODES = Object.freeze({
  createContext: 'CREATE_RECOMMENDATION_CONTEXT',
  generateDecision: 'GENERATE_RECOMMENDATION_DECISION',
  saveDecision: 'SAVE_RECOMMENDATION_DECISION',
})
