import { evaluatePluginQuality } from './qualityEngine.js'
import { detectMaliciousPlugins } from './securityEngine.js'

export function decidePluginSurvival(pluginScore = {}) {
  if (pluginScore.sandboxRisk === 'HIGH' || pluginScore.riskLevel === 'HIGH') return 'ISOLATE'
  if (pluginScore.score < 50) return 'DEPRECATE'
  if (pluginScore.score < 70) return 'DOWNRANK'
  return 'KEEP'
}

export function promoteHighValueModules(ranking = evaluatePluginQuality().ranking) {
  return ranking.filter((plugin) => plugin.score >= 85).map((plugin) => ({
    pluginId: plugin.pluginId,
    action: 'PROMOTE',
    reason: 'HIGH_VALUE_PLUGIN',
  }))
}

export function deprecateLowValuePlugins(ranking = evaluatePluginQuality().ranking) {
  return ranking.filter((plugin) => plugin.score < 50).map((plugin) => ({
    pluginId: plugin.pluginId,
    action: 'DEPRECATE',
    reason: 'LOW_VALUE_OR_HIGH_RISK',
  }))
}

export function runEvolutionPolicyAI() {
  const quality = evaluatePluginQuality()
  const threats = new Set(detectMaliciousPlugins().map((plugin) => plugin.pluginId))
  const survival = quality.ranking.map((plugin) => ({
    pluginId: plugin.pluginId,
    decision: threats.has(plugin.pluginId) ? 'ISOLATE' : decidePluginSurvival(plugin),
  }))

  return {
    evolutionPolicyAI: 'ACTIVE',
    survival,
    promoted: promoteHighValueModules(quality.ranking),
    deprecated: deprecateLowValuePlugins(quality.ranking),
  }
}
