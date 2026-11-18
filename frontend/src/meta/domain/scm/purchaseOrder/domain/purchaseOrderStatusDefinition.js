export const PURCHASE_ORDER_STATUS_DEFINITION_VERSION = 'V1.14.2.8.5.6'
export const PURCHASE_ORDER_STATUS_DEFINITION_CODE = 'SCM_PURCHASE_ORDER_STATUS_DEFINITION'

export const PURCHASE_ORDER_STATUS_DEFINITION = Object.freeze({
  definitionCode: PURCHASE_ORDER_STATUS_DEFINITION_CODE,
  statusField: 'orderStatus',
  knownStatuses: Object.freeze(['draft', 'submitted', 'approved', 'issued', 'received', 'closed']),
  allowedTransitions: Object.freeze([]),
  definitionOnly: true,
  transitionExecutionAllowed: false,
  stateMutationAllowed: false,
})

export function validatePurchaseOrderStatusDefinition(status) {
  if (!status) return Object.freeze({ result: 'UNKNOWN', reason: 'status_fact_missing' })
  const known = PURCHASE_ORDER_STATUS_DEFINITION.knownStatuses.includes(status)
  return Object.freeze({ result: known ? 'PASS' : 'FAIL', reason: known ? '' : 'status_not_defined' })
}
