import { buildCivilizationState } from './unifiedCivilizationEngine.js'

function resolveState(context = {}) {
  return context.civilizationState || buildCivilizationState(context)
}

export function simulateTaxPolicy(context = {}) {
  const state = resolveState(context)
  const taxRate = Number(context.policy?.taxRate ?? 0.18)
  const enterpriseImpact = state.enterpriseLayer.map((enterprise) => ({
    tenantId: enterprise.tenantId,
    marginImpact: Number((-taxRate * 0.35).toFixed(3)),
    action: taxRate > 0.22 ? 'OPTIMIZE_COST_STRUCTURE' : 'MAINTAIN_OPERATIONS',
  }))

  return {
    taxRate,
    enterpriseImpact,
  }
}

export function simulateTradeRegulation(context = {}) {
  const state = resolveState(context)
  const strict = context.policy?.tradeRestriction === true

  return {
    strict,
    countryImpact: state.countryLayer.map((country) => ({
      country: country.country,
      tradeImpact: strict ? 'RESTRICTED_FLOW' : 'OPEN_FLOW',
      stabilityImpact: strict ? -8 : 2,
    })),
  }
}

export function modelMacroPolicyImpact(context = {}) {
  const state = resolveState(context)
  const stimulus = Number(context.policy?.stimulus ?? 0.08)

  return {
    stimulus,
    globalHealthImpact: Math.round(stimulus * 100 - (100 - state.globalLayer.health) * 0.2),
    recommendedPolicy: state.globalLayer.health < 75 ? 'TARGETED_STIMULUS' : 'BALANCED_POLICY',
  }
}

export function simulateGlobalPolicy(context = {}) {
  const tax = simulateTaxPolicy(context)
  const trade = simulateTradeRegulation(context)
  const macro = modelMacroPolicyImpact(context)

  return {
    mode: 'V27_GLOBAL_POLICY_SIMULATION',
    tax,
    trade,
    macro,
    policyImpactScore: Math.max(0, Math.min(100, 75 + macro.globalHealthImpact + (trade.strict ? -10 : 4))),
  }
}
