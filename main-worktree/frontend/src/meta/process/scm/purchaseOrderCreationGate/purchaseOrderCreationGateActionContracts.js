import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { PURCHASE_ORDER_CREATION_GATE_NODE_CODE } from './purchaseOrderCreationGateNodeRuntimeContract.js'

const base = {
  nodeCode: PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
  objectType: 'PurchaseOrderCreationGateDecision',
  stateModel: 'PURCHASE_ORDER_CREATION_GATE_STATE',
}

export const PURCHASE_ORDER_CREATION_GATE_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'CREATE_PURCHASE_ORDER_GATE_CONTEXT', actionName: 'Create Purchase Order Gate Context',
    buttonCode: 'create-purchase-order-gate-context', allowedFromStates: ['supplier_recommendation_ready'],
    resultState: 'gate_context_created' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'EVALUATE_PURCHASE_ORDER_CREATION_ELIGIBILITY', actionName: 'Evaluate Purchase Order Creation Eligibility',
    buttonCode: 'evaluate-purchase-order-creation-eligibility', allowedFromStates: ['gate_context_created'],
    resultState: 'evaluating' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'SAVE_PURCHASE_ORDER_GATE_DECISION', actionName: 'Save Purchase Order Gate Decision',
    buttonCode: 'save-purchase-order-gate-decision', allowedFromStates: ['evaluating'],
    resultState: 'eligible' }),
])

export const PURCHASE_ORDER_CREATION_GATE_UI_ACTION_CODES = Object.freeze({
  createContext: 'CREATE_PURCHASE_ORDER_GATE_CONTEXT',
  evaluateEligibility: 'EVALUATE_PURCHASE_ORDER_CREATION_ELIGIBILITY',
  saveDecision: 'SAVE_PURCHASE_ORDER_GATE_DECISION',
})
