export const PURCHASE_ORDER_LIFECYCLE_STATE_VERSION = 'V1.14.2.8.5.9'
export const PURCHASE_ORDER_LIFECYCLE_STATE_CODE = 'SCM_PURCHASE_ORDER_LIFECYCLE_STATE'

export const PURCHASE_ORDER_LIFECYCLE_STATES = Object.freeze([
  'draft',
  'pending_approval',
  'approved',
  'issued',
  'partially_received',
  'completed',
  'cancelled',
])

export const PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION = Object.freeze({
  definitionCode: PURCHASE_ORDER_LIFECYCLE_STATE_CODE,
  statusField: 'lifecycleStatus',
  knownStatuses: PURCHASE_ORDER_LIFECYCLE_STATES,
  definitionOnly: true,
  automaticTransitionAllowed: false,
  transitionExecutionAllowed: false,
  executesTransaction: false,
})

export function validatePurchaseOrderLifecycleState(status) {
  if (!status) return Object.freeze({ result: 'UNKNOWN', reason: 'purchase_order_lifecycle_status_missing' })
  const known = PURCHASE_ORDER_LIFECYCLE_STATES.includes(status)
  return Object.freeze({ result: known ? 'PASS' : 'FAIL', reason: known ? '' : 'purchase_order_lifecycle_status_not_defined' })
}
