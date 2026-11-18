export const SUPPLIER_QUOTATION_STATE_MODEL_VERSION = 'V1.14.2.8.6.1'

export const SUPPLIER_QUOTATION_LIFECYCLE = Object.freeze([
  'draft',
  'created',
  'sent',
  'waiting_quote',
  'quote_received',
  'closed',
  'cancelled',
])

export const SUPPLIER_QUOTATION_STATE_TRANSITIONS = Object.freeze([
  Object.freeze({ from: 'draft', to: 'created' }),
  Object.freeze({ from: 'created', to: 'sent' }),
  Object.freeze({ from: 'sent', to: 'waiting_quote' }),
  Object.freeze({ from: 'waiting_quote', to: 'quote_received' }),
  Object.freeze({ from: 'quote_received', to: 'closed' }),
  Object.freeze({ from: 'draft', to: 'cancelled' }),
  Object.freeze({ from: 'created', to: 'cancelled' }),
  Object.freeze({ from: 'sent', to: 'cancelled' }),
  Object.freeze({ from: 'waiting_quote', to: 'cancelled' }),
])

export function evaluateSupplierQuotationTransition({ fromStatus, toStatus } = {}) {
  if (!SUPPLIER_QUOTATION_LIFECYCLE.includes(fromStatus) || !SUPPLIER_QUOTATION_LIFECYCLE.includes(toStatus)) {
    return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'state_fact_missing_or_unknown' })
  }
  const allowed = SUPPLIER_QUOTATION_STATE_TRANSITIONS.some((transition) => transition.from === fromStatus && transition.to === toStatus)
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow' : 'deny', reason: allowed ? '' : 'transition_not_allowed' })
}
