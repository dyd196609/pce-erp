import { buildProcessHandoff } from '../contract/processHandoffContract.js'
import { resolveStateTransition } from '../contract/processStateTransitionContract.js'
import { validateProcessContextContract } from '../contract/processContextContract.js'

export const PROCESS_RUNTIME_ENGINE_VERSION = 'PCE-PROCESS-RUNTIME-ENGINE-V1.0'

function requireItem(items, predicate, errorCode) {
  const item = items.find(predicate)
  if (!item) throw new Error(errorCode)
  return item
}

export function executeProcessAction(definition, context, actionCode) {
  const contextValidation = validateProcessContextContract(context)
  if (!contextValidation.valid) throw new Error(`PROCESS_CONTEXT_INVALID:${contextValidation.errors.join(',')}`)

  const node = requireItem(definition.nodes || [], item => item.nodeCode === context.nodeCode, 'PROCESS_NODE_NOT_FOUND')
  const action = requireItem(definition.actions || [], item => item.actionCode === actionCode, 'PROCESS_ACTION_NOT_FOUND')
  if (action.nodeCode !== node.nodeCode || !node.actions.includes(actionCode)) throw new Error('ACTION_NODE_MISMATCH')
  if (!action.allowedFromStates.includes(context.state)) throw new Error(`ACTION_STATE_NOT_ALLOWED:${context.state}`)
  if (action.objectType !== context.objectType) throw new Error('ACTION_OBJECT_TYPE_MISMATCH')

  const stateModel = requireItem(definition.stateModels || [], item => item.modelCode === node.stateModel, 'STATE_MODEL_NOT_FOUND')
  const transition = resolveStateTransition(stateModel, context.state, actionCode)
  if (transition.to !== action.resultState) throw new Error('ACTION_TRANSITION_RESULT_MISMATCH')

  const updatedContext = Object.freeze({ ...context, state: transition.to })
  const handoffContract = action.handoffCode
    ? requireItem(definition.handoffs || [], item => item.handoffCode === action.handoffCode, 'HANDOFF_NOT_FOUND')
    : null
  const handoff = handoffContract ? buildProcessHandoff(handoffContract, updatedContext) : null

  return Object.freeze({
    runtimeVersion: PROCESS_RUNTIME_ENGINE_VERSION,
    actionCode,
    nodeCode: node.nodeCode,
    outputObject: node.outputObject,
    transition,
    context: updatedContext,
    handoff,
  })
}

