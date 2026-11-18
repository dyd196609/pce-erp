export const QUOTATION_COMPARISON_STATE_MODEL_VERSION = 'V1.14.2.8.6.2'

export const QUOTATION_COMPARISON_STATES = Object.freeze([
  'not_created',
  'collecting',
  'comparison_ready',
  'review_required',
  'blocked',
])

export const QUOTATION_COMPARISON_TRANSITIONS = Object.freeze([
  Object.freeze({ from: 'not_created', to: 'collecting' }),
  Object.freeze({ from: 'collecting', to: 'comparison_ready' }),
  Object.freeze({ from: 'collecting', to: 'review_required' }),
  Object.freeze({ from: 'collecting', to: 'blocked' }),
  Object.freeze({ from: 'comparison_ready', to: 'review_required' }),
  Object.freeze({ from: 'comparison_ready', to: 'blocked' }),
  Object.freeze({ from: 'review_required', to: 'blocked' }),
])

export function evaluateQuotationComparisonTransition({ fromStatus, toStatus } = {}) {
  if (!QUOTATION_COMPARISON_STATES.includes(fromStatus) || !QUOTATION_COMPARISON_STATES.includes(toStatus)) {
    return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'comparison_state_unknown' })
  }
  const allowed = QUOTATION_COMPARISON_TRANSITIONS.some((item) => item.from === fromStatus && item.to === toStatus)
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow' : 'deny', reason: allowed ? '' : 'comparison_transition_forbidden' })
}
