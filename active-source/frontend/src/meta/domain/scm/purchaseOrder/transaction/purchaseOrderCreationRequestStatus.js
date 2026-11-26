export const PURCHASE_ORDER_CREATION_REQUEST_STATUS_VERSION = 'V1.14.2.8.5.7'
export const PURCHASE_ORDER_CREATION_REQUEST_STATUS_CODE = 'SCM_PURCHASE_ORDER_CREATION_REQUEST_STATUS'

export const PURCHASE_ORDER_CREATION_REQUEST_STATUS = Object.freeze({
  definitionCode: PURCHASE_ORDER_CREATION_REQUEST_STATUS_CODE,
  statusField: 'requestStatus',
  knownStatuses: Object.freeze(['draft', 'prepared', 'ready_for_approval', 'blocked', 'closed']),
  allowedTransitions: Object.freeze([]),
  definitionOnly: true,
  transitionExecutionAllowed: false,
  workflowSubmissionAllowed: false,
})

export function validatePurchaseOrderCreationRequestStatus(status) {
  if (!status) return Object.freeze({ result: 'UNKNOWN', reason: 'request_status_fact_missing' })
  const known = PURCHASE_ORDER_CREATION_REQUEST_STATUS.knownStatuses.includes(status)
  return Object.freeze({ result: known ? 'PASS' : 'FAIL', reason: known ? '' : 'request_status_not_defined' })
}
