function simplifyTransitions(workflow = {}) {
  const states = workflow.states || []
  if (states.length <= 3) return workflow.transitions || []

  return states.slice(0, -1).map((state, index) => ({
    from: state,
    to: states[index + 1],
  }))
}

export function optimizeWorkflow(feedback = {}) {
  const schema = feedback.schema || {}
  const workflow = schema.workflow || {}
  const slowWorkflow = feedback.workflowCompletionRate > 0 && feedback.workflowCompletionRate < 0.6
  const safeBypass = feedback.errorRate < 0.05 && feedback.blockingRate < 0.05
  const approvalStates = (workflow.states || []).filter((state) => String(state).includes('APPROV'))

  return {
    version: Number(workflow.version || 1) + 1,
    reduceStates: slowWorkflow,
    mergeTransitions: slowWorkflow ? simplifyTransitions(workflow) : [],
    bypassCandidates: safeBypass ? approvalStates : [],
    workflow: {
      ...workflow,
      version: Number(workflow.version || 1) + 1,
      optimization: {
        slowWorkflow,
        safeBypass,
      },
    },
  }
}
