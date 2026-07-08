import { getPluginRegistry } from '../pluginSDK.js'
import { getSandboxLog } from '../sandboxRuntime.js'

function getPluginSandboxEvents(pluginId) {
  return getSandboxLog().filter((item) => item.pluginId === pluginId)
}

export function scorePlugin(plugin = {}) {
  const events = getPluginSandboxEvents(plugin.id)
  const blocked = events.filter((item) => item.status === 'BLOCKED').length
  const violations = events.reduce((sum, item) => sum + (item.violations?.length || 0), 0)
  const apiScore = plugin.api?.list && plugin.api?.detail ? 10 : 0
  const sandboxScore = plugin.sandbox ? 10 : -20
  const penalty = blocked * 20 + violations * 8
  const score = Math.max(0, Math.min(100, 80 + apiScore + sandboxScore - penalty))

  return {
    pluginId: plugin.id,
    name: plugin.name,
    developerId: plugin.developerId,
    score,
    sandboxRisk: score >= 80 ? 'LOW' : score >= 60 ? 'MEDIUM' : 'HIGH',
    status: score < 50 ? 'DEPRECATION_CANDIDATE' : 'ACTIVE',
  }
}

export function rankPlugins() {
  return getPluginRegistry()
    .map(scorePlugin)
    .sort((a, b) => b.score - a.score)
}

export function getDeprecatedPlugins() {
  return rankPlugins().filter((plugin) => plugin.score < 50)
}

export function evaluatePluginQuality() {
  const ranking = rankPlugins()
  const averageScore = ranking.length === 0
    ? 100
    : Math.round(ranking.reduce((sum, plugin) => sum + plugin.score, 0) / ranking.length)

  return {
    mode: 'V21_PLUGIN_QUALITY',
    averageScore,
    ranking,
    deprecated: ranking.filter((plugin) => plugin.status === 'DEPRECATION_CANDIDATE'),
  }
}
