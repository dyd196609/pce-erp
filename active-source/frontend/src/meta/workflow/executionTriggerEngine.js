function actionType(action) {
  if (action === 'create') return 'onCreate'
  if (action === 'update') return 'onUpdate'
  if (['APPROVE', 'POST', 'CLOSE_DEAL', 'DELIVER'].includes(action)) return 'onApprove'
  if (['CLOSE', 'close', 'SETTLE', 'DELIVER'].includes(action)) return 'onComplete'
  return 'onUpdate'
}

export function triggerExecution(module, action, context = {}) {
  const trigger = actionType(action)
  const transition = context.transition || {}
  const stateField = context.stateField || 'workflow_state'
  const record = {
    ...(context.record || {}),
    ...(context.payload || {}),
  }

  if (transition.allowed) {
    record[stateField] = transition.to
  }

  return {
    module,
    action,
    trigger,
    executed: transition.allowed !== false,
    record,
    message: transition.allowed === false ? transition.reason : 'WORKFLOW_TRIGGER_EXECUTED',
  }
}
