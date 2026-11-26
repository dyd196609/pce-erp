export const SUPPLIER_RECOMMENDATION_ACTION_GUARD_VERSION = 'V1.14.2.8.5.4'
export const SUPPLIER_RECOMMENDATION_ACTION_GUARD_CODE = 'SCM_SUPPLIER_RECOMMENDATION_DECISION_ACTION_GUARD'

export const SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS = Object.freeze([
  'createPurchaseOrder',
  'createContract',
  'submitPayment',
  'generateFinanceDocument',
  'reserveInventory',
])

const defineGuard = (status, allowedActions) => Object.freeze({
  guardCode: SUPPLIER_RECOMMENDATION_ACTION_GUARD_CODE,
  status,
  allowedActions: Object.freeze(allowedActions),
  forbiddenActions: SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS,
  policy: 'explicit_whitelist_default_deny',
  executionMode: 'read_only',
})

export const SUPPLIER_RECOMMENDATION_ACTION_GUARD_RULES = Object.freeze([
  defineGuard('draft', ['viewEvidence', 'compareQuote']),
  defineGuard('recommended', ['viewEvidence', 'compareQuote', 'viewRecommendation']),
  defineGuard('ready_for_approval', ['viewEvidence', 'viewRecommendation']),
  defineGuard('closed', ['viewEvidence', 'viewRecommendation']),
])

export function evaluateSupplierRecommendationActionGuard({ status, action } = {}) {
  if (!status || !action) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'action_guard_fact_missing' })
  if (SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS.includes(action)) return Object.freeze({ result: 'FAIL', decision: 'deny', reason: 'business_execution_action_forbidden' })
  const guard = SUPPLIER_RECOMMENDATION_ACTION_GUARD_RULES.find(item => item.status === status)
  if (!guard) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'status_not_registered' })
  const allowed = guard.allowedActions.includes(action)
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow' : 'deny', reason: allowed ? '' : 'action_not_whitelisted', businessWriteCount: 0, productionUserDataWritten: false })
}
