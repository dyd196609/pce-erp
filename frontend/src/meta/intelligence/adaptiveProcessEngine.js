export function removeInefficientSteps(context = {}) {
  const optimizedFlow = context.optimizationRuntime?.process?.optimizedFlow
    || context.processOptimization?.optimizedFlow
    || {}
  const reducedSteps = Number(optimizedFlow.reducedSteps || 0)

  return {
    removedSteps: reducedSteps,
    retainedSteps: Math.max(1, Number(optimizedFlow.optimizedStepCount || 3)),
    rule: reducedSteps > 0 ? 'REMOVE_LOW_VALUE_HANDOFF' : 'KEEP_CURRENT_STRUCTURE',
  }
}

export function autoRestructureWorkflow(context = {}) {
  const removed = removeInefficientSteps(context)

  return {
    adaptiveProcess: 'ENABLED',
    restructureMode: removed.removedSteps > 0 ? 'AUTO_RESTRUCTURED' : 'MONITORING',
    workflowPath: removed.removedSteps > 0
      ? ['draft', 'approved']
      : ['draft', 'submitted', 'approved'],
    removed,
  }
}

export function optimizeProcessPathDynamically(context = {}) {
  const restructure = autoRestructureWorkflow(context)

  return {
    ...restructure,
    dynamicPath: restructure.workflowPath,
    pathPolicy: 'EFFICIENCY_FIRST_WITH_ROLLBACK_PROTECTION',
  }
}
