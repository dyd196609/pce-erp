import { runExecutionIntelligence } from './executionIntelligenceEngine.js'
import { recordExecution } from './executionMemoryEngine.js'
import { policyDecide } from './executionPolicyEngine.js'
import { generateRollback } from './rollbackEngine.js'
import { adjustRiskScore } from './riskLearningEngine.js'
import { semanticDiff } from './semanticDiffEngine.js'

export function executePatchSet(patchSet = {}) {
  const intelligence = runExecutionIntelligence(patchSet)
  const patch = patchSet.patch || patchSet
  const semantic = semanticDiff(patch)
  const learnedRisk = adjustRiskScore(patch)
  const decision = policyDecide(learnedRisk.adjustedRisk, intelligence.anomaly)
  const rollback = generateRollback(intelligence.diff)

  const result = {
    patch,
    intelligence,
    shadow: intelligence.shadow,
    diff: intelligence.diff,
    anomaly: intelligence.anomaly,
    semantic,
    learnedRisk,
    rollback,
    decision,
  }

  recordExecution(result)

  return result
}
