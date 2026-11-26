import {
  assertValid,
  freezeContract,
  isNonEmptyString,
  isStringList,
  PROCESS_RUNTIME_CONTRACT_VERSION,
  validationResult,
} from './contractValidation.js'

export const PROCESS_STATE_TRANSITION_CONTRACT = 'ProcessStateTransitionContract'

function validateTransition(transition, states, index, errors) {
  const prefix = `TRANSITION_${index}`
  if (!isNonEmptyString(transition?.actionCode)) errors.push(`${prefix}_ACTION_REQUIRED`)
  if (!states.includes(transition?.from)) errors.push(`${prefix}_FROM_UNKNOWN`)
  if (!states.includes(transition?.to)) errors.push(`${prefix}_TO_UNKNOWN`)
  if (transition?.from === transition?.to) errors.push(`${prefix}_STATE_CHANGE_REQUIRED`)
}

export function validateProcessStateTransitionContract(model = {}) {
  const errors = []
  if (!isNonEmptyString(model.modelCode)) errors.push('MODEL_CODE_REQUIRED')
  if (!isNonEmptyString(model.objectType)) errors.push('OBJECT_TYPE_REQUIRED')
  if (!isStringList(model.states)) errors.push('STATES_REQUIRED')
  const states = Array.isArray(model.states) ? model.states : []
  if (!states.includes(model.initialState)) errors.push('INITIAL_STATE_UNKNOWN')
  if (!Array.isArray(model.transitions) || model.transitions.length === 0) errors.push('TRANSITIONS_REQUIRED')
  else model.transitions.forEach((transition, index) => validateTransition(transition, states, index, errors))
  return validationResult(PROCESS_STATE_TRANSITION_CONTRACT, errors)
}

export function createProcessStateTransitionContract(input = {}) {
  const contract = {
    contractVersion: PROCESS_RUNTIME_CONTRACT_VERSION,
    modelCode: input.modelCode,
    objectType: input.objectType,
    initialState: input.initialState,
    states: Object.freeze([...(input.states || [])]),
    transitions: Object.freeze((input.transitions || []).map(item => Object.freeze({ ...item }))),
  }
  assertValid(validateProcessStateTransitionContract(contract))
  return freezeContract(contract)
}

export function resolveStateTransition(model, currentState, actionCode) {
  assertValid(validateProcessStateTransitionContract(model))
  const transition = model.transitions.find(item => item.from === currentState && item.actionCode === actionCode)
  if (!transition) throw new Error(`STATE_TRANSITION_NOT_ALLOWED:${currentState}:${actionCode}`)
  return Object.freeze({ from: transition.from, to: transition.to, actionCode: transition.actionCode })
}

