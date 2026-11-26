import {
  assertValid,
  freezeContract,
  isNonEmptyString,
  isStringList,
  PROCESS_RUNTIME_CONTRACT_VERSION,
  validationResult,
} from './contractValidation.js'

export const PROCESS_ACTION_RUNTIME_CONTRACT = 'ProcessActionRuntimeContract'

export function validateProcessActionRuntimeContract(action = {}) {
  const errors = []
  if (!isNonEmptyString(action.actionCode)) errors.push('ACTION_CODE_REQUIRED')
  if (!isNonEmptyString(action.actionName)) errors.push('ACTION_NAME_REQUIRED')
  if (!isNonEmptyString(action.buttonCode)) errors.push('BUTTON_CODE_REQUIRED')
  if (!isNonEmptyString(action.nodeCode)) errors.push('NODE_CODE_REQUIRED')
  if (!isNonEmptyString(action.objectType)) errors.push('OBJECT_TYPE_REQUIRED')
  if (!isNonEmptyString(action.stateModel)) errors.push('STATE_MODEL_REQUIRED')
  if (!isStringList(action.allowedFromStates)) errors.push('ALLOWED_FROM_STATES_REQUIRED')
  if (!isNonEmptyString(action.resultState)) errors.push('RESULT_STATE_REQUIRED')
  if (action.handoffCode !== null && !isNonEmptyString(action.handoffCode)) errors.push('HANDOFF_CODE_INVALID')
  return validationResult(PROCESS_ACTION_RUNTIME_CONTRACT, errors)
}

export function createProcessActionRuntimeContract(input = {}) {
  const contract = {
    contractVersion: PROCESS_RUNTIME_CONTRACT_VERSION,
    actionCode: input.actionCode,
    actionName: input.actionName,
    buttonCode: input.buttonCode,
    nodeCode: input.nodeCode,
    objectType: input.objectType,
    stateModel: input.stateModel,
    allowedFromStates: Object.freeze([...(input.allowedFromStates || [])]),
    resultState: input.resultState,
    handoffCode: input.handoffCode ?? null,
  }
  assertValid(validateProcessActionRuntimeContract(contract))
  return freezeContract(contract)
}
