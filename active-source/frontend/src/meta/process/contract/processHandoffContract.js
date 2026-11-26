import {
  assertValid,
  freezeContract,
  isNonEmptyString,
  isStringList,
  PROCESS_RUNTIME_CONTRACT_VERSION,
  validationResult,
} from './contractValidation.js'

export const PROCESS_HANDOFF_CONTRACT = 'ProcessHandoffContract'

export function validateProcessHandoffContract(handoff = {}) {
  const errors = []
  if (!isNonEmptyString(handoff.handoffCode)) errors.push('HANDOFF_CODE_REQUIRED')
  if (!isNonEmptyString(handoff.fromNode)) errors.push('FROM_NODE_REQUIRED')
  if (!isNonEmptyString(handoff.toNode)) errors.push('TO_NODE_REQUIRED')
  if (handoff.fromNode === handoff.toNode) errors.push('DISTINCT_NODES_REQUIRED')
  if (!isNonEmptyString(handoff.outputObject)) errors.push('OUTPUT_OBJECT_REQUIRED')
  if (!isNonEmptyString(handoff.inputObject)) errors.push('INPUT_OBJECT_REQUIRED')
  if (handoff.outputObject !== handoff.inputObject && !isNonEmptyString(handoff.mappingCode)) errors.push('OBJECT_TYPE_MAPPING_REQUIRED')
  if (handoff.mappingCode != null && !isNonEmptyString(handoff.mappingCode)) errors.push('MAPPING_CODE_INVALID')
  if (!isNonEmptyString(handoff.actionCode)) errors.push('ACTION_CODE_REQUIRED')
  if (!isStringList(handoff.requiredContextKeys)) errors.push('CONTEXT_KEYS_REQUIRED')
  return validationResult(PROCESS_HANDOFF_CONTRACT, errors)
}

export function createProcessHandoffContract(input = {}) {
  const contract = {
    contractVersion: PROCESS_RUNTIME_CONTRACT_VERSION,
    handoffCode: input.handoffCode,
    fromNode: input.fromNode,
    toNode: input.toNode,
    outputObject: input.outputObject,
    inputObject: input.inputObject,
    actionCode: input.actionCode,
    mappingCode: input.mappingCode ?? null,
    requiredContextKeys: Object.freeze([...(input.requiredContextKeys || [])]),
  }
  assertValid(validateProcessHandoffContract(contract))
  return freezeContract(contract)
}

export function buildProcessHandoff(handoff, context) {
  assertValid(validateProcessHandoffContract(handoff))
  const missingKeys = handoff.requiredContextKeys.filter(key => context?.[key] === undefined || context?.[key] === null)
  if (missingKeys.length) throw new Error(`HANDOFF_CONTEXT_MISSING:${missingKeys.join(',')}`)
  return Object.freeze({
    handoffCode: handoff.handoffCode,
    fromNode: handoff.fromNode,
    toNode: handoff.toNode,
    objectType: handoff.outputObject,
    targetObjectType: handoff.inputObject,
    mappingCode: handoff.mappingCode,
    context: Object.freeze(Object.fromEntries(handoff.requiredContextKeys.map(key => [key, context[key]]))),
  })
}
