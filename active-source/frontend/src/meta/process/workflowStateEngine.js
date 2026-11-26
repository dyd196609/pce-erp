import { defineProcess } from './processDefinitionEngine.js'

export function getInitialState(type = 'purchase') {
  return defineProcess(type).steps[0]?.key || 'draft'
}

export function getAvailableTransitions(type = 'purchase', currentState = getInitialState(type)) {
  return defineProcess(type).transitions.filter((transition) => transition.from === currentState)
}

export function validateTransition(type = 'purchase', currentState = getInitialState(type), actionOrTarget = '') {
  const process = defineProcess(type)
  const knownStates = process.steps.map((step) => step.key)
  if (!knownStates.includes(currentState)) {
    return {
      valid: false,
      blocked: true,
      from: currentState,
      to: currentState,
      action: actionOrTarget,
      transition: null,
      reason: 'UNKNOWN_WORKFLOW_STATE',
      strict: true,
    }
  }

  const transitions = getAvailableTransitions(type, currentState)
  const transition = transitions.find((item) =>
    item.action === actionOrTarget || item.to === actionOrTarget
  )

  return {
    valid: Boolean(transition),
    blocked: !transition,
    from: currentState,
    to: transition?.to || currentState,
    action: transition?.action || actionOrTarget,
    transition: transition || null,
    reason: transition ? null : 'INVALID_STATE_TRANSITION',
    strict: true,
  }
}

export function enforceConsistency(type = 'purchase', history = []) {
  const inconsistent = history.find((entry, index) => {
    if (index === 0) return entry.from !== getInitialState(type)
    return history[index - 1].to !== entry.from
  })

  return {
    consistent: !inconsistent,
    reason: inconsistent ? 'WORKFLOW_HISTORY_INCONSISTENT' : null,
    checkedTransitions: history.length,
  }
}

export function protectRollback(type = 'purchase', currentState = getInitialState(type), targetState = '') {
  const stateOrder = defineProcess(type).steps.map((step) => step.key)
  const currentIndex = stateOrder.indexOf(currentState)
  const targetIndex = stateOrder.indexOf(targetState)
  const rollback = targetIndex >= 0 && currentIndex >= 0 && targetIndex < currentIndex

  return {
    protected: true,
    rollback,
    allowed: !rollback,
    reason: rollback ? 'ROLLBACK_PROTECTED' : null,
  }
}

export function executeTransition(type = 'purchase', state = getInitialState(type), actionOrTarget = '') {
  const validation = validateTransition(type, state, actionOrTarget)
  const rollback = protectRollback(type, state, validation.to)

  if (!validation.valid || !rollback.allowed) {
    return {
      ...validation,
      rollback,
      state,
      executed: false,
      blocked: true,
      reason: validation.reason || rollback.reason,
    }
  }

  return {
    ...validation,
    rollback,
    state: validation.to,
    executed: true,
  }
}

export function runWorkflow(type = 'purchase', actions = ['SUBMIT', 'APPROVE'], initialState = getInitialState(type)) {
  const runtime = actions.reduce((runtime, action) => {
    const result = executeTransition(type, runtime.currentState, action)
    return {
      currentState: result.state,
      history: [
        ...runtime.history,
        result,
      ],
      blocked: runtime.blocked || result.blocked,
    }
  }, {
    currentState: initialState,
    history: [],
    blocked: false,
  })

  return {
    ...runtime,
    consistency: enforceConsistency(type, runtime.history),
    strictValidation: true,
    rollbackProtection: 'ENABLED',
  }
}
