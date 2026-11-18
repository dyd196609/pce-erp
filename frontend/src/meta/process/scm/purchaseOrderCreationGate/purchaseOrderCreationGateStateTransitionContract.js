import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const PURCHASE_ORDER_CREATION_GATE_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'PURCHASE_ORDER_CREATION_GATE_STATE',
  objectType: 'PurchaseOrderCreationGateDecision',
  initialState: 'supplier_recommendation_ready',
  states: ['supplier_recommendation_ready', 'gate_context_created', 'evaluating', 'eligible', 'blocked'],
  transitions: [
    { actionCode: 'CREATE_PURCHASE_ORDER_GATE_CONTEXT', from: 'supplier_recommendation_ready', to: 'gate_context_created' },
    { actionCode: 'EVALUATE_PURCHASE_ORDER_CREATION_ELIGIBILITY', from: 'gate_context_created', to: 'evaluating' },
    { actionCode: 'SAVE_PURCHASE_ORDER_GATE_DECISION', from: 'evaluating', to: 'eligible' },
    { actionCode: 'BLOCK_PURCHASE_ORDER_CREATION', from: 'evaluating', to: 'blocked' },
  ],
})

export const PURCHASE_ORDER_CREATION_GATE_STATE_BOUNDARIES = Object.freeze({
  gate_context_created: Object.freeze({ objectType: 'PurchaseOrderCreationGateContext', purchaseOrderCreated: false }),
  evaluating: Object.freeze({ decisionOnly: true, supplierPublished: false }),
  eligible: Object.freeze({ eligibilityOnly: true, purchaseOrderCreated: false, paymentCreated: false }),
  blocked: Object.freeze({ terminalGateResult: true, purchaseOrderCreated: false, paymentCreated: false }),
})

export function validatePurchaseOrderCreationGateStateBoundaries() {
  const values = Object.values(PURCHASE_ORDER_CREATION_GATE_STATE_BOUNDARIES)
  const valid = values.every(item => item.purchaseOrderCreated !== true
    && item.supplierPublished !== true && item.paymentCreated !== true)
    && PURCHASE_ORDER_CREATION_GATE_STATE_BOUNDARIES.eligible.eligibilityOnly === true
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
