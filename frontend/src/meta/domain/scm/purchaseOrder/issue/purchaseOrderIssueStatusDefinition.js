export const PURCHASE_ORDER_ISSUE_STATUS_VERSION = 'V1.14.2.8.5.10'
export const PURCHASE_ORDER_ISSUE_STATUS_CODE = 'SCM_PURCHASE_ORDER_ISSUE_STATUS'

export const PURCHASE_ORDER_ISSUE_STATUS_DEFINITION = Object.freeze({
  definitionCode: PURCHASE_ORDER_ISSUE_STATUS_CODE,
  statusField: 'issueStatus',
  knownStatuses: Object.freeze(['definition', 'ready_for_future_issue', 'blocked']),
  allowedTransitions: Object.freeze([]),
  definitionOnly: true,
  automaticTransitionAllowed: false,
  transitionExecutionAllowed: false,
  executesIssue: false,
  sendsSupplier: false,
})

export function validatePurchaseOrderIssueStatus(status) {
  if (!status) return Object.freeze({ result: 'UNKNOWN', reason: 'purchase_order_issue_status_missing' })
  const known = PURCHASE_ORDER_ISSUE_STATUS_DEFINITION.knownStatuses.includes(status)
  return Object.freeze({ result: known ? 'PASS' : 'FAIL', reason: known ? '' : 'purchase_order_issue_status_not_defined' })
}
