export const PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS_VERSION = 'V1.14.2.8.5.8'
export const PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS_CODE = 'SCM_PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS'

export const PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS = Object.freeze({
  definitionCode: PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS_CODE,
  statusField: 'preparationStatus',
  knownStatuses: Object.freeze(['definition', 'ready', 'blocked']),
  allowedTransitions: Object.freeze([]),
  definitionOnly: true,
  transitionExecutionAllowed: false,
  createsWorkflowInstance: false,
  submitsApproval: false,
})

export function validatePurchaseOrderApprovalPreparationStatus(status) {
  if (!status) return Object.freeze({ result: 'UNKNOWN', reason: 'approval_preparation_status_missing' })
  const known = PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS.knownStatuses.includes(status)
  return Object.freeze({ result: known ? 'PASS' : 'FAIL', reason: known ? '' : 'approval_preparation_status_not_defined' })
}
