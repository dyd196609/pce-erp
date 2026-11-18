import { resolveScmAcceptanceObject } from './scmAcceptanceObjectModel.js'

export const SCM_ACTION_ACCEPTANCE_VERSION = 'V1.14.2.8.4.23'
export const SCM_FINANCIAL_ACTIONS = Object.freeze(['createPayment', 'executePayment', 'bankTransfer', 'postLedger', 'reconcile'])

const rules = [
  ['SCM_PURCHASE_REQUEST', 'draft', ['edit', 'submit', 'cancel'], ['createPurchaseOrder', 'pay', 'post', 'release']],
  ['SCM_PURCHASE_REQUEST', 'submitted', ['approve', 'cancel'], ['edit', 'release', 'createPurchaseOrder']],
  ['SCM_PURCHASE_REQUEST', 'approved', ['release'], ['edit', 'modify', 'createPurchaseOrder']],
  ['SCM_PURCHASE_REQUEST', 'released', ['close'], ['edit', 'modify', 'submit']],
  ['SCM_PURCHASE_REQUEST', 'closed', [], ['edit', 'modify', 'submit', 'release']],
  ['SCM_PURCHASE_INQUIRY', 'draft', ['edit', 'issue', 'cancel'], ['createPurchaseOrder', 'pay', 'post']],
  ['SCM_PURCHASE_INQUIRY', 'issued', ['recordQuote', 'cancel'], ['edit', 'createPurchaseOrder']],
  ['SCM_PURCHASE_INQUIRY', 'quoted', ['evaluate'], ['edit', 'issue', 'createPurchaseOrder']],
  ['SCM_PURCHASE_INQUIRY', 'evaluated', ['close'], ['edit', 'issue', 'modify']],
  ['SCM_PURCHASE_INQUIRY', 'closed', [], ['edit', 'issue', 'evaluate']],
  ['SCM_PURCHASE_ORDER', 'draft', ['edit', 'approve', 'cancel'], ['receive', 'pay', 'post']],
  ['SCM_PURCHASE_ORDER', 'approved', ['issue'], ['edit', 'modify', 'receive']],
  ['SCM_PURCHASE_ORDER', 'issued', ['receive'], ['edit', 'modify', 'approve']],
  ['SCM_PURCHASE_ORDER', 'received', ['close'], ['edit', 'modify', 'issue']],
  ['SCM_PURCHASE_ORDER', 'closed', [], ['edit', 'modify', 'issue', 'receive']],
]

export const SCM_ACTION_ACCEPTANCE_RULES = Object.freeze(rules.map(([objectCode, status, allowedActions, forbiddenActions]) => Object.freeze({
  objectCode,
  status,
  allowedActions: Object.freeze([...allowedActions]),
  forbiddenActions: Object.freeze([...new Set([...forbiddenActions, ...SCM_FINANCIAL_ACTIONS])]),
  policy: 'explicit_whitelist_default_deny',
})))

export function evaluateScmAction({ objectCode, status, action } = {}) {
  if (!resolveScmAcceptanceObject(objectCode) || !status || !action) return Object.freeze({ result: 'UNKNOWN', reason: 'ACTION_FACT_MISSING_OR_OBJECT_UNKNOWN' })
  const rule = SCM_ACTION_ACCEPTANCE_RULES.find(item => item.objectCode === objectCode && item.status === status)
  if (!rule) return Object.freeze({ result: 'UNKNOWN', reason: 'ACTION_STATUS_NOT_MODELLED' })
  if (rule.allowedActions.includes(action)) return Object.freeze({ result: 'PASS', reason: '', decision: 'allow' })
  return Object.freeze({ result: 'FAIL', reason: rule.forbiddenActions.includes(action) ? 'ACTION_EXPLICITLY_FORBIDDEN' : 'ACTION_NOT_WHITELISTED', decision: 'deny' })
}
