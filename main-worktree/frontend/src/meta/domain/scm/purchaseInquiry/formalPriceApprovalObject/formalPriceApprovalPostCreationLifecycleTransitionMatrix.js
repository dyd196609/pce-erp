export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_TRANSITION_MATRIX_VERSION = 'V1.14.2.8.6.17'

export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_TRANSITIONS = Object.freeze([
  Object.freeze({ from: 'created', to: 'pending_approval', defined: true, enabled: false, mode: 'frozen' }),
  Object.freeze({ from: 'created', to: 'cancelled', defined: true, enabled: false, mode: 'frozen' }),
  Object.freeze({ from: 'pending_approval', to: 'approved', defined: true, enabled: false, mode: 'frozen' }),
  Object.freeze({ from: 'pending_approval', to: 'rejected', defined: true, enabled: false, mode: 'frozen' }),
])

export function inspectFormalPriceApprovalPostCreationLifecycleTransition({ fromState = '', toState = '' } = {}) {
  const transition = FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_TRANSITIONS.find((item) => item.from === fromState && item.to === toState)
  return Object.freeze({
    result: transition ? 'PASS' : 'FAIL',
    decision: 'deny',
    defined: Boolean(transition),
    enabled: false,
    fromState,
    toState,
    currentState: fromState,
    stateChanged: false,
    persistencePerformed: false,
  })
}

export function validateFormalPriceApprovalPostCreationLifecycleTransitionMatrix(matrix = FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_TRANSITIONS) {
  const valid = matrix.length === 4
    && matrix.every((item) => item.defined === true && item.enabled === false && item.mode === 'frozen')
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
