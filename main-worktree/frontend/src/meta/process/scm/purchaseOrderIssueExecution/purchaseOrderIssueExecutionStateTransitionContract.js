import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const PURCHASE_ORDER_ISSUE_EXECUTION_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'PURCHASE_ORDER_ISSUE_EXECUTION_STATE',
  objectType: 'PurchaseOrderIssueAuthorization',
  initialState: 'issue_boundary_decided',
  states: ['issue_boundary_decided', 'execution_context_created', 'authorization_checking', 'authorized', 'blocked'],
  transitions: [
    { actionCode: 'CREATE_ISSUE_EXECUTION_CONTEXT', from: 'issue_boundary_decided', to: 'execution_context_created' },
    { actionCode: 'CHECK_EXECUTION_AUTHORIZATION', from: 'execution_context_created', to: 'authorization_checking' },
    { actionCode: 'SAVE_EXECUTION_PREPARATION', from: 'authorization_checking', to: 'authorized' },
    { actionCode: 'BLOCK_ISSUE_EXECUTION', from: 'authorization_checking', to: 'blocked' },
  ],
})

export const PURCHASE_ORDER_ISSUE_EXECUTION_STATE_BOUNDARIES = Object.freeze({
  execution_context_created: Object.freeze({ contextOnly: true, purchaseOrderIssued: false, supplierApiCalled: false }),
  authorization_checking: Object.freeze({ authorizationPreparationOnly: true, supplierSent: false }),
  authorized: Object.freeze({ authorizationOnly: true, purchaseOrderIssued: false, supplierApiCalled: false }),
  blocked: Object.freeze({ terminalAuthorizationResult: true, purchaseOrderIssued: false, supplierApiCalled: false }),
})

export function validatePurchaseOrderIssueExecutionStateBoundaries() {
  const values = Object.values(PURCHASE_ORDER_ISSUE_EXECUTION_STATE_BOUNDARIES)
  const valid = values.every(item => item.purchaseOrderIssued !== true
    && item.supplierApiCalled !== true && item.supplierSent !== true)
    && PURCHASE_ORDER_ISSUE_EXECUTION_STATE_BOUNDARIES.authorized.authorizationOnly === true
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
