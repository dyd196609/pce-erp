import { applyBusinessRules } from './approvalEngine.js'
import { evaluateState, getNextSteps, progressState } from './stateMachineEngine.js'
import { triggerExecution } from './executionTriggerEngine.js'

function normalizeAction(action) {
  if (action === 'create' || action === 'update') return action
  return String(action || '').trim()
}

export function executeWorkflow(module, action, context = {}) {
  const normalizedAction = normalizeAction(action)
  const state = evaluateState(module, context)
  const transitions = getNextSteps(module, context)
  const rules = applyBusinessRules(module, normalizedAction, context)

  if (normalizedAction === 'create' || normalizedAction === 'update') {
    const result = triggerExecution(module, normalizedAction, {
      ...context,
      transition: { allowed: true, from: state, to: context.payload?.workflow_state || context.record?.workflow_state || state },
    })

    return {
      state,
      transitions,
      rules,
      result,
    }
  }

  const transition = progressState(module, normalizedAction, context)
  const blocked = !transition.allowed || rules.rejected
  const result = blocked
    ? {
        module,
        action: normalizedAction,
        trigger: 'blocked',
        executed: false,
        record: context.record || {},
        message: transition.reason || rules.reason,
      }
    : triggerExecution(module, normalizedAction, {
        ...context,
        transition,
        stateField: transition.stateField,
      })

  return {
    state,
    transitions,
    rules,
    result,
  }
}
