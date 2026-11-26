import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const PURCHASE_ORDER_ISSUE_PREPARATION_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'PURCHASE_ORDER_ISSUE_PREPARATION_STATE',
  objectType: 'PurchaseOrderIssuePreparation',
  initialState: 'purchase_order_transaction_draft',
  states: ['purchase_order_transaction_draft', 'issue_context_created', 'checking', 'ready_for_issue', 'blocked'],
  transitions: [
    { actionCode: 'CREATE_ISSUE_PREPARATION_CONTEXT', from: 'purchase_order_transaction_draft', to: 'issue_context_created' },
    { actionCode: 'CHECK_ISSUE_REQUIREMENTS', from: 'issue_context_created', to: 'checking' },
    { actionCode: 'SAVE_ISSUE_PREPARATION', from: 'checking', to: 'ready_for_issue' },
    { actionCode: 'BLOCK_ISSUE_PREPARATION', from: 'checking', to: 'blocked' },
  ],
})

export const PURCHASE_ORDER_ISSUE_PREPARATION_STATE_BOUNDARIES = Object.freeze({
  issue_context_created: Object.freeze({ contextOnly: true, purchaseOrderIssued: false }),
  checking: Object.freeze({ preparationOnly: true, supplierSent: false }),
  ready_for_issue: Object.freeze({ readinessOnly: true, purchaseOrderIssued: false, supplierSent: false }),
  blocked: Object.freeze({ terminalPreparationResult: true, purchaseOrderIssued: false, supplierSent: false }),
})

export function validatePurchaseOrderIssuePreparationStateBoundaries() {
  const values = Object.values(PURCHASE_ORDER_ISSUE_PREPARATION_STATE_BOUNDARIES)
  const valid = values.every(item => item.purchaseOrderIssued !== true && item.supplierSent !== true)
    && PURCHASE_ORDER_ISSUE_PREPARATION_STATE_BOUNDARIES.ready_for_issue.readinessOnly === true
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
