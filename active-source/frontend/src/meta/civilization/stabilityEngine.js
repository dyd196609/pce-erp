import { runCrossLayerEconomy } from './crossLayerEconomicEngine.js'
import { simulateGlobalPolicy } from './globalPolicySimulationEngine.js'
import { runWorldStateSync } from './worldStateSyncEngine.js'

export function calculateCivilizationStability(context = {}) {
  const crossLayer = context.crossLayer || runCrossLayerEconomy(context)
  const policy = context.policy || simulateGlobalPolicy(context)
  const sync = context.sync || runWorldStateSync(context)
  const cascadePenalty = crossLayer.cascadingEffects.length * 8
  const syncPenalty = 100 - sync.consistency.consistencyScore

  return Math.max(0, Math.min(100, Math.round(policy.policyImpactScore - cascadePenalty - syncPenalty * 0.3)))
}

export function detectCascadeFailure(context = {}) {
  const crossLayer = context.crossLayer || runCrossLayerEconomy(context)

  return crossLayer.cascadingEffects
    .filter((effect) => effect.severity === 'HIGH')
    .map((effect) => ({
      ...effect,
      risk: 'CASCADE_FAILURE_RISK',
    }))
}

export function predictEconomicCollapse(context = {}) {
  const stability = calculateCivilizationStability(context)
  const cascadeFailures = detectCascadeFailure(context)

  return {
    probability: Math.max(0, Math.min(0.95, (70 - stability) / 100 + cascadeFailures.length * 0.12)),
    level: stability < 45 ? 'HIGH' : stability < 65 ? 'MEDIUM' : 'LOW',
    cascadeFailures,
  }
}

export function evaluateCivilizationStability(context = {}) {
  const stabilityScore = calculateCivilizationStability(context)
  const collapsePrediction = predictEconomicCollapse(context)

  return {
    mode: 'V27_CIVILIZATION_STABILITY',
    stabilityScore,
    cascadeFailures: collapsePrediction.cascadeFailures,
    collapsePrediction,
    status: collapsePrediction.level === 'HIGH' ? 'CRITICAL' : collapsePrediction.level === 'MEDIUM' ? 'WATCH' : 'STABLE',
  }
}
