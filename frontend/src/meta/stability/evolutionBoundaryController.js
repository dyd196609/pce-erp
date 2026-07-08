import { calculateChangeRisk } from './changeRiskEngine.js'
import { assessStability } from './stabilityScoringEngine.js'
import { detectSystemDrift } from './systemDriftDetector.js'
import { runSafeEvolutionGate } from './safeEvolutionGate.js'

const boundaryHistory = []

export function calculateRisk(change = {}) {
  return calculateChangeRisk(change)
}

export function evaluateSafety(change = {}, options = {}) {
  const risk = calculateRisk(change)
  const drift = detectSystemDrift(change)
  const stability = assessStability(change)
  const combinedRisk = Math.max(
    risk.score,
    drift.driftScore,
    Math.max(0, 100 - stability.systemStabilityIndex)
  )
  const gate = runSafeEvolutionGate(combinedRisk, options)

  return {
    ...gate,
    combinedRisk,
    risk,
    drift,
    stability,
  }
}

export function checkEvolutionSafety(change = {}, options = {}) {
  const safety = evaluateSafety(change, options)
  const result = {
    allowed: safety.allowed,
    riskScore: safety.combinedRisk,
    stabilityImpact: safety.stability.impact,
    evolutionControl: 'ACTIVE',
    safeEvolutionGate: 'ENABLED',
    driftProtection: 'ACTIVE',
    safety,
    timestamp: Date.now(),
  }

  boundaryHistory.unshift(result)
  if (boundaryHistory.length > 100) boundaryHistory.length = 100

  return result
}

export function getStabilityBoundarySnapshot() {
  const latest = boundaryHistory[0] || null
  const total = boundaryHistory.length || 1
  const allowed = boundaryHistory.filter((item) => item.allowed).length

  return {
    stabilityMode: 'ON',
    evolutionControl: 'ACTIVE',
    safeEvolutionGate: 'ENABLED',
    driftProtection: 'ACTIVE',
    latest,
    history: [...boundaryHistory],
    metrics: {
      systemStabilityIndex: latest?.safety?.stability?.systemStabilityIndex ?? 100,
      evolutionRiskScore: latest?.riskScore ?? 0,
      driftLevel: latest?.safety?.drift?.driftLevel || 'LOW',
      safeEvolutionStatus: latest?.allowed === false ? 'BLOCKED' : 'ALLOWED',
      allowedEvolutionRate: Math.round((allowed / total) * 100),
    },
  }
}
