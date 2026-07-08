function clampScore(value) {
  return Math.max(0, Math.min(100, Math.round(value)))
}

export function simulateTaxImpact(state = {}) {
  const macro = state.economy?.macro || state.globalEconomy?.macro || {}
  const gdpTrend = Number(macro.gdpTrend || 0)
  const inflationPressure = Number(macro.inflationPressure || 0)

  return {
    recommendedTaxMode: gdpTrend > 3.5 && inflationPressure < 0.25 ? 'GROWTH_NEUTRAL' : 'TARGETED_RELIEF',
    enterpriseBurden: clampScore(42 + inflationPressure * 70 - gdpTrend * 3),
    consumerReliefNeed: inflationPressure > 0.25 ? 'HIGH' : 'NORMAL',
  }
}

export function predictRegulationEffect(state = {}) {
  const behavior = state.behavior || {}
  const enterpriseDecision = behavior.enterpriseDecision || {}
  const consumer = behavior.consumer || {}

  return {
    regulationMode: enterpriseDecision.investmentAppetite === 'LOW' ? 'LIGHT_TOUCH' : 'BALANCED',
    complianceLoad: enterpriseDecision.decisionBias === 'CONTROL_RISK' ? 'MEDIUM' : 'LOW',
    consumerProtection: consumer.priceSensitivity === 'HIGH' ? 'ENHANCED' : 'STANDARD',
  }
}

export function simulatePolicyImpact(state = {}) {
  const taxImpact = simulateTaxImpact(state)
  const regulationEffect = predictRegulationEffect(state)
  const socialStability = state.society?.stabilityIndex ?? 80
  const populationPressure = state.population?.migrationPressure ?? 20
  const stabilityControl = clampScore(socialStability - populationPressure * 0.25 - taxImpact.enterpriseBurden * 0.1 + 12)

  return {
    mode: 'GOVERNANCE_AI',
    policySimulation: {
      recommendedPolicy: stabilityControl > 75 ? 'ENABLE_GROWTH_POLICY' : 'STABILIZE_SOCIAL_SYSTEM',
      priority: stabilityControl > 75 ? 'PRODUCTIVITY' : 'STABILITY',
    },
    taxImpact,
    regulationEffect,
    stabilityControl,
  }
}

export function runGovernanceAI(state = {}) {
  return simulatePolicyImpact(state)
}
