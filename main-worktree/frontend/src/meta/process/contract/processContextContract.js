import {
  assertValid,
  freezeContract,
  isNonEmptyString,
  PROCESS_RUNTIME_CONTRACT_VERSION,
  validationResult,
} from './contractValidation.js'

export const PROCESS_CONTEXT_CONTRACT = 'ProcessContextContract'

export function validateProcessContextContract(context = {}) {
  const errors = []
  if (!isNonEmptyString(context.processInstanceId)) errors.push('PROCESS_INSTANCE_ID_REQUIRED')
  if (!isNonEmptyString(context.processCode)) errors.push('PROCESS_CODE_REQUIRED')
  if (!isNonEmptyString(context.objectType)) errors.push('OBJECT_TYPE_REQUIRED')
  if (!isNonEmptyString(context.objectId)) errors.push('OBJECT_ID_REQUIRED')
  if (!isNonEmptyString(context.nodeCode)) errors.push('NODE_CODE_REQUIRED')
  if (!isNonEmptyString(context.state)) errors.push('STATE_REQUIRED')
  if (!isNonEmptyString(context.actorId)) errors.push('ACTOR_ID_REQUIRED')
  if (!isNonEmptyString(context.actorRole)) errors.push('ACTOR_ROLE_REQUIRED')
  if (!isNonEmptyString(context.correlationId)) errors.push('CORRELATION_ID_REQUIRED')
  if (context.attributes === null || typeof context.attributes !== 'object' || Array.isArray(context.attributes)) {
    errors.push('ATTRIBUTES_OBJECT_REQUIRED')
  }
  return validationResult(PROCESS_CONTEXT_CONTRACT, errors)
}

export function createProcessContextContract(input = {}) {
  const contract = {
    contractVersion: PROCESS_RUNTIME_CONTRACT_VERSION,
    processInstanceId: input.processInstanceId,
    processCode: input.processCode,
    objectType: input.objectType,
    objectId: input.objectId,
    nodeCode: input.nodeCode,
    state: input.state,
    actorId: input.actorId,
    actorRole: input.actorRole,
    correlationId: input.correlationId,
    attributes: Object.freeze({ ...(input.attributes || {}) }),
  }
  assertValid(validateProcessContextContract(contract))
  return freezeContract(contract)
}

