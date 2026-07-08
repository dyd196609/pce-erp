import { buildCivilizationState } from './unifiedCivilizationEngine.js'
import { runCrossLayerEconomy } from './crossLayerEconomicEngine.js'
import { simulateGlobalPolicy } from './globalPolicySimulationEngine.js'
import { runWorldStateSync } from './worldStateSyncEngine.js'
import { evaluateCivilizationStability } from './stabilityEngine.js'

export function runDigitalCivilization(context = {}) {
  const state = buildCivilizationState(context)
  const sharedContext = {
    ...context,
    civilizationState: state,
  }
  const crossLayer = runCrossLayerEconomy(sharedContext)
  const policy = simulateGlobalPolicy(sharedContext)
  const sync = runWorldStateSync(sharedContext)
  const stability = evaluateCivilizationStability({
    ...sharedContext,
    crossLayer,
    policy,
    sync,
  })

  return {
    mode: 'V27_DIGITAL_CIVILIZATION_OPERATING_SYSTEM',
    civilizationMode: 'ON',
    unifiedCivilizationModel: 'ACTIVE',
    crossLayerSync: 'ENABLED',
    stabilityMonitoring: 'ACTIVE',
    state,
    crossLayer,
    policy,
    sync,
    stability,
    metrics: {
      civilizationStability: stability.stabilityScore,
      dependencyEdges: crossLayer.dependencyGraph.edges.length,
      policyImpact: policy.policyImpactScore,
      globalSystemHealth: state.globalLayer.health,
    },
  }
}
