function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value))
}

function getEconomy(state = {}) {
  return state.economy || state.globalEconomy || state.global || {}
}

export function simulateConsumerBehavior(state = {}) {
  const economy = getEconomy(state)
  const demandBalance = economy.market?.demandSupplyBalance ?? 1
  const inflation = economy.macro?.inflationPressure ?? 0
  const confidence = clamp(0.72 + demandBalance * 0.18 - inflation * 0.35)

  return {
    confidence,
    consumptionTrend: confidence > 0.75 ? 'EXPANDING' : confidence > 0.55 ? 'STABLE' : 'DEFENSIVE',
    priceSensitivity: inflation > 0.25 ? 'HIGH' : 'NORMAL',
  }
}

export function simulateLaborMigration(state = {}) {
  const enterprises = getEconomy(state).market?.enterprises || []
  const target = [...enterprises].sort((a, b) => (b.regionalDemand || 0) - (a.regionalDemand || 0))[0]
  const source = [...enterprises].sort((a, b) => (a.regionalDemand || 0) - (b.regionalDemand || 0))[0]

  return {
    from: source?.country || 'LOCAL',
    to: target?.country || 'LOCAL',
    flowIntensity: target && source ? Math.min(100, Math.max(5, (target.regionalDemand - source.regionalDemand) / 5)) : 0,
    reason: target ? 'demand-driven labor migration' : 'stable labor market',
  }
}

export function simulateEnterpriseDecisionBehavior(state = {}) {
  const economy = getEconomy(state)
  const policy = economy.policy || {}
  const networkEfficiency = economy.market?.network?.globalOptimization?.networkEfficiency || 0

  return {
    decisionBias: networkEfficiency > 75 ? 'EXPAND_CAPACITY' : 'CONTROL_RISK',
    policyResponse: policy.riskControls?.[0] || 'monitor policy signals',
    investmentAppetite: networkEfficiency > 80 ? 'HIGH' : networkEfficiency > 65 ? 'MEDIUM' : 'LOW',
  }
}

export function simulatePolicyResponseModel(state = {}) {
  const economy = getEconomy(state)
  const inflation = economy.macro?.inflationPressure || 0
  const gdpTrend = economy.macro?.gdpTrend || 0

  return {
    expectedResponse: inflation > 0.25 ? 'TIGHTEN_MONETARY_POLICY' : 'SUPPORT_PRODUCTIVITY',
    socialResponse: gdpTrend > 3.5 ? 'OPTIMISTIC' : 'CAUTIOUS',
    stabilityPressure: clamp(inflation * 1.8 - gdpTrend / 20),
  }
}

export function simulateHumanBehavior(state = {}) {
  return {
    mode: 'HUMAN_BEHAVIOR_SIMULATION',
    consumer: simulateConsumerBehavior(state),
    laborMigration: simulateLaborMigration(state),
    enterpriseDecision: simulateEnterpriseDecisionBehavior(state),
    policyResponse: simulatePolicyResponseModel(state),
  }
}
