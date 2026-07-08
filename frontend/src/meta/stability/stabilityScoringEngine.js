export function calculateModuleStabilityScore(change = {}) {
  const moduleChanges = change.moduleChanges || {}
  const changeCount = (moduleChanges.splits?.length || 0) + (moduleChanges.merges?.length || 0)
  return Math.max(0, 100 - changeCount * 14)
}

export function calculateWorkflowStabilityScore(change = {}) {
  const workflowChanges = change.workflowChanges || {}
  const approvalMode = workflowChanges.approvalRestructure?.approvalMode || 'ZERO_HUMAN_AUTONOMY'
  const redundant = workflowChanges.redundantStepRemoval?.redundantSteps?.length || 0
  const base = approvalMode === 'CONTROLLED_AUTONOMY' ? 82 : 94

  return Math.max(0, base - redundant * 8)
}

export function calculateUIStabilityScore(change = {}) {
  const uiChanges = change.uiChanges || {}
  const changeCount = uiChanges.changes?.length || 0
  return Math.max(0, 96 - changeCount * 4)
}

export function calculateSystemStabilityIndex(change = {}) {
  const moduleScore = calculateModuleStabilityScore(change)
  const workflowScore = calculateWorkflowStabilityScore(change)
  const uiScore = calculateUIStabilityScore(change)
  const performanceScore = change.performance?.score ?? 85
  const systemScore = Math.round((moduleScore + workflowScore + uiScore + performanceScore) / 4)

  return {
    systemStabilityIndex: systemScore,
    moduleStabilityScore: moduleScore,
    workflowStabilityScore: workflowScore,
    uiStabilityScore: uiScore,
  }
}

export function assessStability(change = {}) {
  const scores = calculateSystemStabilityIndex(change)

  return {
    ...scores,
    impact: scores.systemStabilityIndex >= 85
      ? 'LOW_IMPACT'
      : scores.systemStabilityIndex >= 70
        ? 'CONTROLLED_IMPACT'
        : 'HIGH_IMPACT',
  }
}
