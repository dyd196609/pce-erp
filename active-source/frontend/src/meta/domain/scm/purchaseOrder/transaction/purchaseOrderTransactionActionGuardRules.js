export const PURCHASE_ORDER_TRANSACTION_ACTION_GUARD_VERSION = 'V1.14.2.8.5.7'
export const PURCHASE_ORDER_TRANSACTION_ACTION_GUARD_CODE = 'SCM_PURCHASE_ORDER_TRANSACTION_ACTION_GUARD'

export const PURCHASE_ORDER_TRANSACTION_ALLOWED_ACTIONS = Object.freeze(['viewTransactionBoundary', 'viewCreationRequest', 'viewApprovalPreparation'])
export const PURCHASE_ORDER_TRANSACTION_FORBIDDEN_ACTIONS = Object.freeze([
  'createPurchaseOrder',
  'submitPurchaseOrder',
  'approvePurchaseOrder',
  'issuePurchaseOrder',
  'sendSupplier',
  'receiveGoods',
  'generateInvoice',
  'generatePayment',
])

const defineGuard = status => Object.freeze({ guardCode: PURCHASE_ORDER_TRANSACTION_ACTION_GUARD_CODE, status, allowedActions: PURCHASE_ORDER_TRANSACTION_ALLOWED_ACTIONS, forbiddenActions: PURCHASE_ORDER_TRANSACTION_FORBIDDEN_ACTIONS, policy: 'explicit_whitelist_default_deny', executionMode: 'read_only' })

export const PURCHASE_ORDER_TRANSACTION_ACTION_GUARD_RULES = Object.freeze([
  defineGuard('definition'),
  defineGuard('evaluated'),
  defineGuard('ready_for_future_transaction'),
  defineGuard('blocked'),
])

export function evaluatePurchaseOrderTransactionAction({ status, action } = {}) {
  if (!status || !action) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'action_guard_fact_missing' })
  if (PURCHASE_ORDER_TRANSACTION_FORBIDDEN_ACTIONS.includes(action)) return Object.freeze({ result: 'FAIL', decision: 'deny', reason: 'transaction_execution_action_forbidden' })
  const guard = PURCHASE_ORDER_TRANSACTION_ACTION_GUARD_RULES.find(item => item.status === status)
  if (!guard) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'boundary_status_not_registered' })
  const allowed = guard.allowedActions.includes(action)
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow' : 'deny', reason: allowed ? '' : 'action_not_whitelisted', businessWriteCount: 0, productionUserDataWritten: false })
}
