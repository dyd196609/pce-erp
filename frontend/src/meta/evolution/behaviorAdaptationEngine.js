export function adaptUIByUsage(systemState = {}) {
  const intelligence = systemState.intelligence || {}
  const latestStrategy = intelligence.latest?.strategy?.primary?.type || 'operational_monitoring'

  return {
    type: 'ADAPT_UI_BY_USAGE',
    focusPanel: latestStrategy.includes('supply_chain')
      ? 'Risk Analysis View'
      : latestStrategy.includes('cost')
        ? 'Financial Autonomy View'
        : 'Enterprise Autopilot Dashboard',
    changes: ['promote_relevant_status_panel', 'keep_list_detail_edit_consistency'],
  }
}

export function adjustWorkflowByBehavior(systemState = {}) {
  const autopilot = systemState.autopilot || {}
  const stability = autopilot.metrics?.autopilotStabilityIndex ?? 100

  return {
    type: 'ADJUST_WORKFLOW_BY_BEHAVIOR',
    behaviorMode: stability < 70 ? 'CONTROLLED_EXPLORATION' : 'STABLE_AUTONOMY',
    changes: stability < 70
      ? ['increase_self_repair_visibility', 'prefer_short_workflow_path']
      : ['keep_zero_human_flow', 'continue_goal_based_execution'],
  }
}

export function optimizeInteractionPaths(systemState = {}) {
  const executionRate = systemState.execution?.metrics?.executionSuccessRate ?? 0

  return {
    type: 'OPTIMIZE_INTERACTION_PATHS',
    interactionPath: executionRate >= 80 ? 'direct_autopilot_path' : 'diagnostic_first_path',
    changes: executionRate >= 80
      ? ['reduce_operator_steps', 'surface_execution_summary']
      : ['surface_error_context', 'show_repair_trace_first'],
  }
}

export function adjustBehavior(systemState = {}) {
  return {
    behavioralAdaptation: 'ACTIVE',
    uiAdaptation: adaptUIByUsage(systemState),
    workflowBehavior: adjustWorkflowByBehavior(systemState),
    interactionOptimization: optimizeInteractionPaths(systemState),
    timestamp: Date.now(),
  }
}
