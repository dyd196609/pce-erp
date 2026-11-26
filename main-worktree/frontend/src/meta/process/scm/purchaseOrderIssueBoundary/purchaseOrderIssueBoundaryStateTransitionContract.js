import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const PURCHASE_ORDER_ISSUE_BOUNDARY_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'PURCHASE_ORDER_ISSUE_BOUNDARY_STATE',
  objectType: 'PurchaseOrderIssueDecision',
  initialState: 'issue_preparation_ready',
  states: ['issue_preparation_ready', 'issue_boundary_context_created', 'evaluating', 'allowed', 'blocked'],
  transitions: [
    { actionCode: 'CREATE_ISSUE_BOUNDARY_CONTEXT', from: 'issue_preparation_ready', to: 'issue_boundary_context_created' },
    { actionCode: 'EVALUATE_ISSUE_PERMISSION', from: 'issue_boundary_context_created', to: 'evaluating' },
    { actionCode: 'SAVE_ISSUE_DECISION', from: 'evaluating', to: 'allowed' },
    { actionCode: 'BLOCK_PURCHASE_ORDER_ISSUE', from: 'evaluating', to: 'blocked' },
  ],
})

export const PURCHASE_ORDER_ISSUE_BOUNDARY_STATE_BOUNDARIES = Object.freeze({
  issue_boundary_context_created: Object.freeze({ contextOnly: true, purchaseOrderIssued: false }),
  evaluating: Object.freeze({ permissionDecisionOnly: true, supplierSent: false }),
  allowed: Object.freeze({ permissionOnly: true, purchaseOrderIssued: false, supplierSent: false }),
  blocked: Object.freeze({ terminalBoundaryResult: true, purchaseOrderIssued: false, supplierSent: false }),
})

export function validatePurchaseOrderIssueBoundaryStateBoundaries() {
  const values = Object.values(PURCHASE_ORDER_ISSUE_BOUNDARY_STATE_BOUNDARIES)
  const valid = values.every(item => item.purchaseOrderIssued !== true && item.supplierSent !== true)
    && PURCHASE_ORDER_ISSUE_BOUNDARY_STATE_BOUNDARIES.allowed.permissionOnly === true
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
