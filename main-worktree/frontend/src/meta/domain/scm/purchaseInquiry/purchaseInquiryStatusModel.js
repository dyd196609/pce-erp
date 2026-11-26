export const PURCHASE_INQUIRY_STATUS_MODEL_VERSION = 'V1.14.2.8.5.1'
export const PURCHASE_INQUIRY_STATUS_RULE_CODE = 'SCM_PURCHASE_INQUIRY_STATUS'

export const PURCHASE_INQUIRY_LIFECYCLE = Object.freeze([
  'draft',
  'issued',
  'quoted',
  'evaluating',
  'approved',
  'closed',
])

export const PURCHASE_INQUIRY_ALLOWED_TRANSITIONS = Object.freeze(PURCHASE_INQUIRY_LIFECYCLE.slice(0, -1).map((from, index) => Object.freeze({
  from,
  to: PURCHASE_INQUIRY_LIFECYCLE[index + 1],
})))

export const PURCHASE_INQUIRY_STATUS_MODEL = Object.freeze({
  ruleCode: PURCHASE_INQUIRY_STATUS_RULE_CODE,
  objectCode: 'SCM_PURCHASE_INQUIRY',
  statusField: 'status',
  lifecycle: PURCHASE_INQUIRY_LIFECYCLE,
  allowedTransitions: PURCHASE_INQUIRY_ALLOWED_TRANSITIONS,
  transitionPolicy: 'adjacent_forward_only',
  reverseTransitionForbidden: true,
  skipTransitionForbidden: true,
})

export function evaluatePurchaseInquiryStatusTransition({ fromStatus, toStatus } = {}) {
  if (!fromStatus || !toStatus) return Object.freeze({ result: 'UNKNOWN', reason: 'STATUS_FACT_MISSING' })
  const fromIndex = PURCHASE_INQUIRY_LIFECYCLE.indexOf(fromStatus)
  const toIndex = PURCHASE_INQUIRY_LIFECYCLE.indexOf(toStatus)
  if (fromIndex < 0 || toIndex < 0) return Object.freeze({ result: 'UNKNOWN', reason: 'STATUS_NOT_IN_DOMAIN_MODEL' })
  const pass = toIndex === fromIndex + 1
  return Object.freeze({ result: pass ? 'PASS' : 'FAIL', reason: pass ? '' : toIndex <= fromIndex ? 'REVERSE_OR_STAGNANT_TRANSITION_FORBIDDEN' : 'SKIP_TRANSITION_FORBIDDEN' })
}

