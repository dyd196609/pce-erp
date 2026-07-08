function collectWorkflowPressure(systemState = {}) {
  const executionHistory = systemState.execution?.history || []
  const blocked = executionHistory.filter((item) => item.status === 'BLOCKED').length
  const repeatedActions = executionHistory
    .flatMap((item) => item.executionResult?.actions || [])
    .map((action) => `${action.module}.${action.action}`)

  return {
    blocked,
    repeatedActions,
    totalExecutions: executionHistory.length,
  }
}

export function optimizeWorkflowPaths(systemState = {}) {
  const pressure = collectWorkflowPressure(systemState)

  return {
    type: 'OPTIMIZE_PATHS',
    target: pressure.blocked ? 'risk_control_path' : 'standard_execution_path',
    changes: pressure.blocked
      ? ['insert_risk_review_before_execution', 'route_blocked_flow_to_self_repair']
      : ['keep_direct_action_plan_execution', 'prioritize_shortest_successful_path'],
    impact: pressure.blocked ? 'reduce_blocked_execution' : 'maintain_fast_execution',
  }
}

export function removeRedundantSteps(systemState = {}) {
  const pressure = collectWorkflowPressure(systemState)
  const duplicates = pressure.repeatedActions.filter((item, index, list) => list.indexOf(item) !== index)

  return {
    type: 'REMOVE_REDUNDANT_STEPS',
    redundantSteps: [...new Set(duplicates)],
    changes: duplicates.length ? ['deduplicate_repeated_module_action'] : ['no_redundant_step_detected'],
  }
}

export function restructureApprovals(systemState = {}) {
  const repairState = systemState.autopilot?.repair?.latest?.consistency?.state || 'STABLE'

  return {
    type: 'RESTRUCTURE_APPROVALS',
    approvalMode: repairState === 'RESTORED' ? 'CONTROLLED_AUTONOMY' : 'ZERO_HUMAN_AUTONOMY',
    changes: repairState === 'RESTORED'
      ? ['keep_zero_human_policy', 'add_risk_gate_checkpoint']
      : ['auto_approve_low_risk_flow', 'skip_manual_approval'],
  }
}

export function mutateWorkflows(systemState = {}) {
  return {
    workflowMutation: 'ENABLED',
    pathOptimization: optimizeWorkflowPaths(systemState),
    redundantStepRemoval: removeRedundantSteps(systemState),
    approvalRestructure: restructureApprovals(systemState),
    timestamp: Date.now(),
  }
}
