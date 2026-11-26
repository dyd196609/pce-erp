import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const PURCHASE_ORDER_TRANSACTION_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'PURCHASE_ORDER_TRANSACTION_STATE',
  objectType: 'PurchaseOrderTransaction',
  initialState: 'purchase_order_gate_eligible',
  states: ['purchase_order_gate_eligible', 'transaction_context_created', 'draft', 'pending_issue', 'issued'],
  transitions: [
    { actionCode: 'CREATE_PURCHASE_ORDER_TRANSACTION_CONTEXT', from: 'purchase_order_gate_eligible', to: 'transaction_context_created' },
    { actionCode: 'CREATE_PURCHASE_ORDER_TRANSACTION', from: 'transaction_context_created', to: 'draft' },
    { actionCode: 'SAVE_PURCHASE_ORDER_TRANSACTION', from: 'draft', to: 'pending_issue', enabled: false, minimumVersion: 'future' },
    { actionCode: 'ISSUE_PURCHASE_ORDER_TRANSACTION', from: 'pending_issue', to: 'issued', enabled: false, minimumVersion: 'future' },
  ],
})

export const PURCHASE_ORDER_TRANSACTION_OPERATIONAL_STATES = Object.freeze([
  'transaction_context_created', 'draft',
])

export const PURCHASE_ORDER_TRANSACTION_STATE_BOUNDARIES = Object.freeze({
  transaction_context_created: Object.freeze({ contextOnly: true, purchaseOrderExecutionCreated: false }),
  draft: Object.freeze({ sessionDraftOnly: true, purchaseOrderExecutionCreated: false }),
  pending_issue: Object.freeze({ enabled: false, supplierPublished: false }),
  issued: Object.freeze({ enabled: false, supplierPublished: false }),
})

export function validatePurchaseOrderTransactionStateBoundaries() {
  const values = Object.values(PURCHASE_ORDER_TRANSACTION_STATE_BOUNDARIES)
  const valid = values.every(item => item.purchaseOrderExecutionCreated !== true && item.supplierPublished !== true)
    && PURCHASE_ORDER_TRANSACTION_STATE_BOUNDARIES.pending_issue.enabled === false
    && PURCHASE_ORDER_TRANSACTION_STATE_BOUNDARIES.issued.enabled === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid,
    operationalStates: PURCHASE_ORDER_TRANSACTION_OPERATIONAL_STATES })
}
