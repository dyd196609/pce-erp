import { getExecutionMemory } from './executionMemoryEngine.js'

export function adjustRiskScore(patch) {
  const history = getExecutionMemory()
  const similar = history.filter((entry) => entry.patch?.type === patch?.type)
  const failureRate =
    similar.filter((entry) => entry.anomaly?.risky).length / (similar.length || 1)

  return {
    adjustedRisk: failureRate > 0.5 ? 'HIGH' : 'LOW',
    failureRate,
    sampleSize: similar.length,
  }
}
