export function analyzeSystemMetrics(systemState = {}) {
  const execution = systemState.execution?.metrics || {}
  const autopilot = systemState.autopilot?.metrics || {}
  const intelligence = systemState.intelligence?.metrics || {}

  return {
    executionSuccessRate: execution.executionSuccessRate ?? 0,
    autopilotStabilityIndex: autopilot.autopilotStabilityIndex ?? 100,
    continuousExecutionRate: autopilot.continuousExecutionRate ?? 0,
    riskExposureMeter: intelligence.riskExposureMeter ?? 0,
    financialAutonomyScore: autopilot.financialAutonomyScore ?? execution.financialAutomationScore ?? 75,
  }
}

export function proposeStructuralChanges(metrics = {}) {
  const proposals = []

  if (metrics.executionSuccessRate < 80) proposals.push('strengthen_risk_gate_and_repair_loop')
  if (metrics.riskExposureMeter > 30) proposals.push('shorten_high_risk_workflow_path')
  if (metrics.continuousExecutionRate < 100) proposals.push('increase_continuous_execution_tick')
  if (metrics.financialAutonomyScore < 85) proposals.push('prioritize_financial_reconciliation_panel')
  if (!proposals.length) proposals.push('preserve_current_structure')

  return proposals
}

export function optimizeEnterprisePerformance(systemState = {}) {
  const metrics = analyzeSystemMetrics(systemState)
  const proposals = proposeStructuralChanges(metrics)
  const score = Math.round((
    metrics.executionSuccessRate +
    metrics.autopilotStabilityIndex +
    metrics.continuousExecutionRate +
    metrics.financialAutonomyScore +
    Math.max(0, 100 - metrics.riskExposureMeter)
  ) / 5)

  return {
    performanceEvolution: 'ACTIVE',
    metrics,
    proposals,
    score,
    timestamp: Date.now(),
  }
}
