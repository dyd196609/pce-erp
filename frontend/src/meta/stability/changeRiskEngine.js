function countChangeItems(change = {}) {
  const moduleChanges = change.moduleChanges || {}
  const workflowChanges = change.workflowChanges || {}
  const uiChanges = change.uiChanges || {}

  return {
    moduleCount: (moduleChanges.splits?.length || 0) + (moduleChanges.merges?.length || 0),
    workflowCount: [
      ...(workflowChanges.pathOptimization?.changes || []),
      ...(workflowChanges.redundantStepRemoval?.changes || []),
      ...(workflowChanges.approvalRestructure?.changes || []),
    ].length,
    uiCount: uiChanges.changes?.length || 0,
  }
}

export function evaluateWorkflowMutationRisk(change = {}) {
  const workflowChanges = change.workflowChanges || {}
  const redundantSteps = workflowChanges.redundantStepRemoval?.redundantSteps?.length || 0
  const approvalMode = workflowChanges.approvalRestructure?.approvalMode || 'ZERO_HUMAN_AUTONOMY'
  let score = 12 + redundantSteps * 8

  if (approvalMode === 'CONTROLLED_AUTONOMY') score += 18
  if ((workflowChanges.pathOptimization?.changes || []).length > 3) score += 12

  return {
    score: Math.min(score, 100),
    level: score >= 70 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW',
    reason: approvalMode,
  }
}

export function evaluateModuleRecompositionRisk(change = {}) {
  const counts = countChangeItems(change)
  let score = 10 + counts.moduleCount * 18

  if ((change.moduleChanges?.splits?.length || 0) > 1) score += 16
  if ((change.moduleChanges?.merges?.length || 0) > 2) score += 14

  return {
    score: Math.min(score, 100),
    level: score >= 70 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW',
    reason: `${counts.moduleCount}_module_changes`,
  }
}

export function evaluateUIAdaptationRisk(change = {}) {
  const counts = countChangeItems(change)
  const preferredPanel = change.uiChanges?.preferredPanel || ''
  let score = 8 + counts.uiCount * 6

  if (!preferredPanel) score += 10
  if (preferredPanel.includes('Debug')) score += 12

  return {
    score: Math.min(score, 100),
    level: score >= 70 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW',
    reason: preferredPanel || 'no_preferred_panel',
  }
}

export function calculateChangeRisk(change = {}) {
  const workflow = evaluateWorkflowMutationRisk(change)
  const module = evaluateModuleRecompositionRisk(change)
  const ui = evaluateUIAdaptationRisk(change)
  const score = Math.max(workflow.score, module.score, ui.score)

  return {
    score,
    level: score >= 70 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW',
    workflow,
    module,
    ui,
  }
}
