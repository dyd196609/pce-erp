import { scorePlugin } from './qualityEngine.js'

export function calculateQuality(plugin = {}) {
  return scorePlugin(plugin).score
}

export function analyzePerformance(plugin = {}) {
  const score = calculateQuality(plugin)

  return {
    latencyClass: score >= 80 ? 'FAST' : score >= 60 ? 'NORMAL' : 'SLOW',
    reliability: score >= 80 ? 0.99 : score >= 60 ? 0.9 : 0.75,
    sandboxEfficiency: plugin.sandbox ? 'ISOLATED' : 'UNSAFE',
  }
}

export function assessRisk(plugin = {}) {
  const score = calculateQuality(plugin)

  return score >= 80 ? 'LOW' : score >= 60 ? 'MEDIUM' : 'HIGH'
}

export function generateDecision(plugin = {}) {
  const riskLevel = assessRisk(plugin)
  if (riskLevel === 'HIGH') return 'ISOLATE_PLUGIN'
  if (riskLevel === 'MEDIUM') return 'DOWNRANK_PLUGIN'
  return 'PROMOTE_PLUGIN'
}

export function evaluatePlugin(plugin = {}) {
  return {
    pluginId: plugin.id,
    score: calculateQuality(plugin),
    performance: analyzePerformance(plugin),
    riskLevel: assessRisk(plugin),
    recommendation: generateDecision(plugin),
  }
}
