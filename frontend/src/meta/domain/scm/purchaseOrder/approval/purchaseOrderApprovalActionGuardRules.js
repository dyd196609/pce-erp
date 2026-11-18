export const PURCHASE_ORDER_APPROVAL_ACTION_GUARD_VERSION = 'V1.14.2.8.5.8'
export const PURCHASE_ORDER_APPROVAL_ACTION_GUARD_CODE = 'SCM_PURCHASE_ORDER_APPROVAL_ACTION_GUARD'

export const PURCHASE_ORDER_APPROVAL_ALLOWED_ACTIONS = Object.freeze([
  'viewApprovalPreparation',
  'viewApprovalContext',
  'viewEvidence',
  'viewRiskSummary',
])

export const PURCHASE_ORDER_APPROVAL_FORBIDDEN_ACTIONS = Object.freeze([
  'createWorkflowInstance',
  'submitApproval',
  'approveApproval',
  'rejectApproval',
  'createPurchaseOrder',
  'issuePurchaseOrder',
  'generatePayment',
])

export const PURCHASE_ORDER_APPROVAL_ACTION_GUARD_RULES = Object.freeze(['definition', 'ready', 'blocked'].map(status => Object.freeze({
  guardCode: PURCHASE_ORDER_APPROVAL_ACTION_GUARD_CODE,
  status,
  allowedActions: PURCHASE_ORDER_APPROVAL_ALLOWED_ACTIONS,
  forbiddenActions: PURCHASE_ORDER_APPROVAL_FORBIDDEN_ACTIONS,
  policy: 'explicit_whitelist_default_deny',
  executionMode: 'read_only',
})))

export function evaluatePurchaseOrderApprovalAction({ status, action } = {}) {
  if (!status || !action) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'approval_action_guard_fact_missing' })
  if (PURCHASE_ORDER_APPROVAL_FORBIDDEN_ACTIONS.includes(action)) return Object.freeze({ result: 'FAIL', decision: 'deny', reason: 'approval_execution_action_forbidden', businessWriteCount: 0, productionDataWritten: false })
  const guard = PURCHASE_ORDER_APPROVAL_ACTION_GUARD_RULES.find(item => item.status === status)
  if (!guard) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'approval_preparation_status_not_registered' })
  const allowed = guard.allowedActions.includes(action)
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow' : 'deny', reason: allowed ? '' : 'action_not_whitelisted', businessWriteCount: 0, productionDataWritten: false })
}
