import { buildEconomicGraph } from './economicGraphEngine.js'
import { simulateIndustrySupply } from './industrySupplyEngine.js'
import { simulateCrossEnterprisePricing } from './crossEnterprisePricingEngine.js'

export function optimizeIndustryProfit(context = {}) {
  const graph = buildEconomicGraph(context.tenants)
  const totalScore = graph.nodes.reduce((sum, node) => sum + node.economicScore, 0)
  const averageScore = graph.nodes.length ? totalScore / graph.nodes.length : 0

  return {
    averageScore: Math.round(averageScore),
    action: averageScore >= 80 ? 'EXPAND_INDUSTRY_CAPACITY' : 'REBALANCE_MARGIN_AND_DEMAND',
  }
}

export function balanceCrossTenantRevenue(context = {}) {
  const graph = buildEconomicGraph(context.tenants)
  const scores = graph.nodes.map((node) => node.economicScore)
  const min = scores.length ? Math.min(...scores) : 0
  const max = scores.length ? Math.max(...scores) : 0

  return {
    spread: max - min,
    action: max - min > 25 ? 'REDISTRIBUTE_DEMAND_TO_WEAKER_TENANTS' : 'KEEP_CURRENT_REVENUE_FLOW',
  }
}

export function improveEcosystemEfficiency(context = {}) {
  const industry = simulateIndustrySupply(context)
  const pricing = simulateCrossEnterprisePricing(context)
  const pressurePenalty = industry.supplyPressure.pressureScore * 20
  const ripplePenalty = pricing.rippleEffects.filter((item) => item.impactLevel === 'HIGH').length * 5

  return {
    efficiencyScore: Math.max(0, Math.round(92 - pressurePenalty - ripplePenalty)),
    pressurePenalty,
    ripplePenalty,
    action: pressurePenalty + ripplePenalty > 20 ? 'OPTIMIZE_CROSS_TENANT_FLOW' : 'MAINTAIN_NETWORK',
  }
}

export function optimizeMacroProfit(context = {}) {
  const industryProfit = optimizeIndustryProfit(context)
  const revenueBalance = balanceCrossTenantRevenue(context)
  const ecosystemEfficiency = improveEcosystemEfficiency(context)

  return {
    mode: 'V25_MACRO_PROFIT_OPTIMIZATION',
    industryProfit,
    revenueBalance,
    ecosystemEfficiency,
    macroProfitEfficiencyScore: Math.round((industryProfit.averageScore + ecosystemEfficiency.efficiencyScore) / 2),
  }
}
