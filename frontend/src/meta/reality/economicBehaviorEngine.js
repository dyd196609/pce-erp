import { computeEconomicState } from '../economy/economicDynamicsEngine.js'

export function influenceCashflow(context = {}) {
  const feedback = context.feedback || {}
  const paymentDelay = Number(feedback.paymentDelayDays ?? 12)

  return {
    paymentDelay,
    influence: paymentDelay > 20 ? 'TIGHTEN_COLLECTION_PRIORITY' : 'NORMAL_COLLECTION',
    cashflowImpact: paymentDelay > 20 ? 'NEGATIVE' : 'STABLE',
  }
}

export function simulateSupplyChainReaction(context = {}) {
  const feedback = context.feedback || {}
  const supplierDelay = Number(feedback.supplierDelayRate ?? 0.15)

  return {
    supplierDelay,
    reaction: supplierDelay > 0.25 ? 'REROUTE_OR_BUFFER_STOCK' : 'MONITOR_SUPPLIER_FLOW',
    supplyChainImpact: supplierDelay > 0.25 ? 'PRESSURE' : 'NORMAL',
  }
}

export function analyzePricingBehaviorImpact(context = {}) {
  const economy = computeEconomicState(context)
  const volatility = economy.metrics.pricingVolatility

  return {
    volatility,
    pricingBehavior: volatility > 0.1 ? 'PRICE_SENSITIVITY_WARNING' : 'PRICE_STABLE',
    recommendedNudge: volatility > 0.1 ? 'EXPLAIN_VALUE_AND_PHASE_PRICE_CHANGE' : 'NO_PRICE_NUDGE',
  }
}

export function computeEconomicBehaviorImpact(context = {}) {
  return {
    mode: 'V28_ECONOMIC_BEHAVIOR_IMPACT',
    cashflow: influenceCashflow(context),
    supplyChain: simulateSupplyChainReaction(context),
    pricing: analyzePricingBehaviorImpact(context),
  }
}
