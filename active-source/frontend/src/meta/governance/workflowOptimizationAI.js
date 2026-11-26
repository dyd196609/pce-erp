function getWorkflow(context = {}) {
  return context.workflow || context.schema?.workflow || {
    states: ['DRAFT', 'SUBMITTED', 'APPROVED', 'CLOSED'],
    transitions: [
      { from: 'DRAFT', to: 'SUBMITTED' },
      { from: 'SUBMITTED', to: 'APPROVED' },
      { from: 'APPROVED', to: 'CLOSED' },
    ],
  }
}

export function reduceWorkflowComplexity(context = {}) {
  const workflow = getWorkflow(context)
  const states = workflow.states || []
  const redundantStates = states.filter((state) =>
    ['REVIEWED', 'AUDITED', 'CHECKED'].includes(String(state).toUpperCase())
  )

  return {
    originalDepth: states.length,
    optimizedDepth: Math.max(2, states.length - redundantStates.length),
    redundantStates,
    complexityReduced: redundantStates.length > 0,
  }
}

export function removeRedundantApprovals(context = {}) {
  const workflow = getWorkflow(context)
  const transitions = workflow.transitions || []
  const redundantApprovals = transitions.filter((transition) =>
    String(transition.from).toUpperCase().includes('REVIEW')
    || String(transition.to).toUpperCase().includes('AUDIT')
  )

  return {
    removed: redundantApprovals.length,
    retained: Math.max(0, transitions.length - redundantApprovals.length),
    recommendation: redundantApprovals.length > 0 ? 'MERGE_APPROVAL_STEPS' : 'KEEP_APPROVAL_PATH',
  }
}

export function optimizeExecutionPath(context = {}) {
  const feedback = context.feedback || {}
  const urgent = feedback.urgent === true || Number(feedback.workflowBacklog || 0) > 5

  return {
    path: urgent ? 'FAST_TRACK_WORKFLOW' : 'STANDARD_WORKFLOW',
    priority: urgent ? 'HIGH' : 'NORMAL',
    expectedCycleTimeReduction: urgent ? 0.28 : 0.08,
  }
}

export function optimizeWorkflow(context = {}) {
  const complexity = reduceWorkflowComplexity(context)
  const approvals = removeRedundantApprovals(context)
  const path = optimizeExecutionPath(context)

  return {
    mode: 'V29_WORKFLOW_OPTIMIZATION_AI',
    complexity,
    approvals,
    path,
    score: Math.min(100, 70 + approvals.removed * 6 + Math.round(path.expectedCycleTimeReduction * 50)),
  }
}
