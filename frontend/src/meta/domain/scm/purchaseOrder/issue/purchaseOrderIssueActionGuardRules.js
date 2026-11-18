export const PURCHASE_ORDER_ISSUE_ACTION_GUARD_VERSION = 'V1.14.2.8.5.10'
export const PURCHASE_ORDER_ISSUE_ACTION_GUARD_CODE = 'SCM_PURCHASE_ORDER_ISSUE_ACTION_GUARD'

export const PURCHASE_ORDER_ISSUE_ALLOWED_ACTIONS = Object.freeze([
  'viewIssueBoundary',
  'viewSupplierReleaseContext',
  'viewIssueEvidence',
])

export const PURCHASE_ORDER_ISSUE_FORBIDDEN_ACTIONS = Object.freeze([
  'issuePurchaseOrder',
  'sendSupplier',
  'sendSupplierNotification',
  'createDeliveryTask',
  'receiveGoods',
  'generateInvoice',
  'generatePayment',
])

export const PURCHASE_ORDER_ISSUE_ACTION_GUARD_RULES = Object.freeze(['definition', 'ready_for_future_issue', 'blocked'].map(status => Object.freeze({
  guardCode: PURCHASE_ORDER_ISSUE_ACTION_GUARD_CODE,
  status,
  allowedActions: PURCHASE_ORDER_ISSUE_ALLOWED_ACTIONS,
  forbiddenActions: PURCHASE_ORDER_ISSUE_FORBIDDEN_ACTIONS,
  policy: 'explicit_whitelist_default_deny',
  executionMode: 'read_only',
})))

export function evaluatePurchaseOrderIssueAction({ status, action } = {}) {
  if (!status || !action) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'issue_action_guard_fact_missing' })
  if (PURCHASE_ORDER_ISSUE_FORBIDDEN_ACTIONS.includes(action)) return Object.freeze({ result: 'FAIL', decision: 'deny', reason: 'purchase_order_issue_action_forbidden', businessWriteCount: 0, productionDataWritten: false })
  const guard = PURCHASE_ORDER_ISSUE_ACTION_GUARD_RULES.find(item => item.status === status)
  if (!guard) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'issue_status_not_registered' })
  const allowed = guard.allowedActions.includes(action)
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow' : 'deny', reason: allowed ? '' : 'action_not_whitelisted', businessWriteCount: 0, productionDataWritten: false })
}
