import {
  PURCHASE_INQUIRY_ACTION_RULES,
  PURCHASE_INQUIRY_FORBIDDEN_DOWNSTREAM_ACTIONS,
} from '../purchaseInquiryActionRules.js'

export const PURCHASE_INQUIRY_ACTION_GUARD_VERSION = 'V1.14.2.8.5.2'
export const PURCHASE_INQUIRY_ACTION_GUARD_RULE_CODE = 'SCM_PURCHASE_INQUIRY_ACTION_GUARDS'
export const PURCHASE_INQUIRY_DANGEROUS_ACTIONS = Object.freeze([
  'createPurchaseOrder',
  'payment',
  'bankTransfer',
  'ledgerPost',
  'reconcile',
])

export const PURCHASE_INQUIRY_ACTION_GUARD_RULES = Object.freeze(PURCHASE_INQUIRY_ACTION_RULES.map(rule => Object.freeze({
  guardCode: PURCHASE_INQUIRY_ACTION_GUARD_RULE_CODE,
  objectCode: rule.objectCode,
  status: rule.status,
  allowedActions: rule.allowedActions,
  forbiddenActions: rule.forbiddenActions,
  policy: 'explicit_whitelist_default_deny',
  executionMode: 'read_only',
})))

export function evaluatePurchaseInquiryActionGuard({ status, action } = {}) {
  if (!status || !action) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'action_guard_fact_missing' })
  if (PURCHASE_INQUIRY_DANGEROUS_ACTIONS.includes(action) || PURCHASE_INQUIRY_FORBIDDEN_DOWNSTREAM_ACTIONS.includes(action)) {
    return Object.freeze({ result: 'FAIL', decision: 'deny', reason: 'dangerous_action_forbidden' })
  }
  const guard = PURCHASE_INQUIRY_ACTION_GUARD_RULES.find(rule => rule.status === status)
  if (!guard) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'action_guard_status_not_registered' })
  const allowed = guard.allowedActions.includes(action)
  return Object.freeze({
    result: allowed ? 'PASS' : 'FAIL',
    decision: allowed ? 'allow' : 'deny',
    reason: allowed ? '' : guard.forbiddenActions.includes(action) ? 'action_explicitly_forbidden' : 'action_not_whitelisted',
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}
