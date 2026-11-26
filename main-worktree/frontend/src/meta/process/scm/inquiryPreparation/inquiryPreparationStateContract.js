export const INQUIRY_PREPARATION_STATE_CONTRACT_VERSION = 'V1.14.2.8.18.3'
export const INQUIRY_PREPARATION_STATE_CONTRACT_CODE = 'SCM_INQUIRY_PREPARATION_STATE_CONTRACT'

export const INQUIRY_PREPARATION_STATES = Object.freeze(['created', 'prepared', 'ready_for_inquiry'])
export const INQUIRY_PREPARATION_FORBIDDEN_STATES = Object.freeze([
  'inquiry_created', 'quotation_created', 'purchase_order_created',
])

export function transitionInquiryPreparationState(context = {}, targetState = '') {
  const transitions = { created: 'prepared', prepared: 'ready_for_inquiry' }
  if (INQUIRY_PREPARATION_FORBIDDEN_STATES.includes(targetState)) throw new Error('INQUIRY_PREPARATION_DOWNSTREAM_STATE_FORBIDDEN')
  if (transitions[context.preparationStatus] !== targetState) {
    throw new Error(`INQUIRY_PREPARATION_STATE_TRANSITION_DENIED:${context.preparationStatus}->${targetState}`)
  }
  return Object.freeze({ ...context, preparationStatus: targetState,
    stateHistory: Object.freeze([...(context.stateHistory || []), targetState]) })
}

export function validateInquiryPreparationStateContract() {
  const created = { preparationStatus: 'created', stateHistory: ['created'] }
  const prepared = transitionInquiryPreparationState(created, 'prepared')
  const ready = transitionInquiryPreparationState(prepared, 'ready_for_inquiry')
  const valid = ready.stateHistory.join('>') === 'created>prepared>ready_for_inquiry'
    && INQUIRY_PREPARATION_FORBIDDEN_STATES.length === 3
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

