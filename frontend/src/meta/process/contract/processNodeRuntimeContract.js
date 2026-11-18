import {
  assertValid,
  freezeContract,
  isNonEmptyString,
  isStringList,
  PROCESS_RUNTIME_CONTRACT_VERSION,
  validationResult,
} from './contractValidation.js'

export const PROCESS_NODE_RUNTIME_CONTRACT = 'ProcessNodeRuntimeContract'

export function validateProcessNodeRuntimeContract(node = {}) {
  const errors = []
  if (!isNonEmptyString(node.nodeCode)) errors.push('NODE_CODE_REQUIRED')
  if (!isNonEmptyString(node.nodeName)) errors.push('NODE_NAME_REQUIRED')
  if (!isNonEmptyString(node.inputObject)) errors.push('INPUT_OBJECT_REQUIRED')
  if (!isNonEmptyString(node.outputObject)) errors.push('OUTPUT_OBJECT_REQUIRED')
  if (!isStringList(node.actions)) errors.push('ACTIONS_REQUIRED')
  if (!isNonEmptyString(node.stateModel)) errors.push('STATE_MODEL_REQUIRED')
  if (node.nextNode !== null && !isNonEmptyString(node.nextNode)) errors.push('NEXT_NODE_REQUIRED_OR_NULL')
  return validationResult(PROCESS_NODE_RUNTIME_CONTRACT, errors)
}

export function createProcessNodeRuntimeContract(input = {}) {
  const contract = {
    contractVersion: PROCESS_RUNTIME_CONTRACT_VERSION,
    nodeCode: input.nodeCode,
    nodeName: input.nodeName,
    inputObject: input.inputObject,
    outputObject: input.outputObject,
    actions: Object.freeze([...(input.actions || [])]),
    stateModel: input.stateModel,
    nextNode: input.nextNode ?? null,
  }
  assertValid(validateProcessNodeRuntimeContract(contract))
  return freezeContract(contract)
}

