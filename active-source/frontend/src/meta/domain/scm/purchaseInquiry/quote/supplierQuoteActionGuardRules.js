export const SUPPLIER_QUOTE_ACTION_GUARD_VERSION = 'V1.14.2.8.5.3'
export const SUPPLIER_QUOTE_ACTION_GUARD_CODE = 'SCM_SUPPLIER_QUOTE_ACTION_GUARD'

export const SUPPLIER_QUOTE_FORBIDDEN_ACTIONS = Object.freeze([
  'createPurchaseOrder',
  'payment',
  'bankTransfer',
  'ledgerPost',
  'reconcile',
])

const defineGuard = (status, allowedActions) => Object.freeze({
  guardCode: SUPPLIER_QUOTE_ACTION_GUARD_CODE,
  status,
  allowedActions: Object.freeze(allowedActions),
  forbiddenActions: SUPPLIER_QUOTE_FORBIDDEN_ACTIONS,
  policy: 'explicit_whitelist_default_deny',
  executionMode: 'read_only',
})

export const SUPPLIER_QUOTE_ACTION_GUARD_RULES = Object.freeze([
  defineGuard('draft', ['editQuote']),
  defineGuard('received', ['validateQuote']),
  defineGuard('valid', ['compareQuote']),
  defineGuard('validated', ['compareQuote']),
  defineGuard('quoted', ['compareQuote']),
  defineGuard('compared', ['compareQuote', 'sendToPriceApproval']),
  defineGuard('evaluated', ['sendToPriceApproval']),
  defineGuard('closed', []),
])

export function evaluateSupplierQuoteActionGuard({ status, action } = {}) {
  if (!status || !action) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'action_guard_fact_missing' })
  if (SUPPLIER_QUOTE_FORBIDDEN_ACTIONS.includes(action)) return Object.freeze({ result: 'FAIL', decision: 'deny', reason: 'dangerous_action_forbidden' })
  const guard = SUPPLIER_QUOTE_ACTION_GUARD_RULES.find(item => item.status === status)
  if (!guard) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'status_not_registered' })
  const allowed = guard.allowedActions.includes(action)
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow' : 'deny', reason: allowed ? '' : 'action_not_whitelisted', businessWriteCount: 0, productionUserDataWritten: false })
}
