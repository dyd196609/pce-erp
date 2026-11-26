export const PURCHASE_INQUIRY_ACTION_RULE_VERSION = 'V1.14.2.8.5.1'
export const PURCHASE_INQUIRY_ACTION_RULE_CODE = 'SCM_PURCHASE_INQUIRY_ACTION_RULE'

export const PURCHASE_INQUIRY_FORBIDDEN_DOWNSTREAM_ACTIONS = Object.freeze([
  'createPurchaseOrder',
  'payment',
  'createPayment',
  'bankTransfer',
  'ledgerPost',
  'reconcile',
])

const defineRule = (status, allowedActions, forbiddenActions = []) => Object.freeze({
  objectCode: 'SCM_PURCHASE_INQUIRY',
  ruleCode: PURCHASE_INQUIRY_ACTION_RULE_CODE,
  status,
  allowedActions: Object.freeze(allowedActions),
  forbiddenActions: Object.freeze([...new Set([...forbiddenActions, ...PURCHASE_INQUIRY_FORBIDDEN_DOWNSTREAM_ACTIONS])]),
  policy: 'explicit_whitelist_default_deny',
})

export const PURCHASE_INQUIRY_ACTION_RULES = Object.freeze([
  defineRule('draft', ['edit', 'addSupplier', 'deleteLine', 'issue', 'cancel']),
  defineRule('issued', ['receiveQuote', 'cancel'], ['modifyRequirement']),
  defineRule('quoted', ['viewQuote', 'compare'], ['modifyRequirement']),
  defineRule('evaluating', ['viewQuote', 'createComparisonResult', 'approveInquiry'], ['modifyRequirement']),
  defineRule('approved', ['sendToPriceApproval'], ['modifyQuote', 'modifyRequirement']),
  defineRule('closed', [], ['edit', 'addSupplier', 'deleteLine', 'receiveQuote', 'modifyQuote', 'requote']),
])

export function evaluatePurchaseInquiryAction({ status, action } = {}) {
  if (!status || !action) return Object.freeze({ result: 'UNKNOWN', reason: 'ACTION_FACT_MISSING' })
  const rule = PURCHASE_INQUIRY_ACTION_RULES.find(item => item.status === status)
  if (!rule) return Object.freeze({ result: 'UNKNOWN', reason: 'ACTION_STATUS_NOT_MODELLED' })
  if (rule.allowedActions.includes(action)) return Object.freeze({ result: 'PASS', decision: 'allow', reason: '' })
  return Object.freeze({ result: 'FAIL', decision: 'deny', reason: rule.forbiddenActions.includes(action) ? 'ACTION_EXPLICITLY_FORBIDDEN' : 'ACTION_NOT_WHITELISTED' })
}

