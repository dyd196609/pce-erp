const defaultThreshold = 70

export function blockEvolution(reason = 'risk_above_threshold') {
  return {
    allowed: false,
    status: 'BLOCKED',
    reason,
    timestamp: Date.now(),
  }
}

export function allowEvolution(reason = 'risk_within_threshold') {
  return {
    allowed: true,
    status: 'ALLOWED',
    reason,
    timestamp: Date.now(),
  }
}

export function runSafeEvolutionGate(riskScore = 0, options = {}) {
  const threshold = Number(options.threshold || defaultThreshold)

  if (riskScore > threshold) {
    return blockEvolution('evolution_risk_above_threshold')
  }

  return allowEvolution('evolution_risk_within_threshold')
}
