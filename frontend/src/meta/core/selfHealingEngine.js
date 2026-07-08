import { runContractGovernance } from './contractGovernanceEngine.js'
import { runExecutionIntelligence } from './executionIntelligenceEngine.js'
import { recordEvent } from './monitoringLayer.js'

export function runSelfHealing(patchSet) {
  const execution = runExecutionIntelligence(patchSet)
  const governance = runContractGovernance()
  const issues = []

  if (governance.drift?.driftScore > 0.3) {
    issues.push({
      type: 'CONTRACT_DRIFT',
      severity: 'HIGH',
    })
  }

  if (execution.anomaly?.risky) {
    issues.push({
      type: 'EXECUTION_ANOMALY',
      severity: 'HIGH',
    })
  }

  if (governance.suggestions?.length > 0) {
    issues.push({
      type: 'STRUCTURE_ISSUE',
      severity: 'MEDIUM',
    })
  }

  const actions = issues.map((issue) => ({
    issue: issue.type,
    action: issue.severity === 'HIGH' ? 'REQUIRE_MANUAL_FIX' : 'AUTO_SUGGEST_FIX',
  }))

  const result = {
    mode: 'V7_SELF_HEALING',
    execution,
    governance,
    issues,
    actions,
    status: issues.some((issue) => issue.severity === 'HIGH') ? 'NEEDS_ATTENTION' : 'HEALTHY',
  }

  recordEvent({
    type: issues.length > 0 ? 'SELF_HEALING' : 'EXECUTION',
    module: 'system',
    status: result.status,
    issues: issues.length,
  })

  return result
}
