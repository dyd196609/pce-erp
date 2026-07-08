import { analyzeConflicts } from './decisionConflictEngine.js'

export function optimizeDecisionWeights() {
  const analysis = analyzeConflicts()

  let executionWeight = 0.5
  let governanceWeight = 0.5

  if (analysis.conflictRate > 0.3) {
    governanceWeight = 0.7
    executionWeight = 0.3
  }

  if (analysis.conflictRate < 0.1) {
    governanceWeight = 0.4
    executionWeight = 0.6
  }

  return {
    executionWeight,
    governanceWeight,
    conflictRate: analysis.conflictRate,
  }
}
