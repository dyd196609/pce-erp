import { buildEconomicGraph } from './economicGraphEngine.js'
import { simulateIndustrySupply } from './industrySupplyEngine.js'
import { simulateCrossEnterprisePricing } from './crossEnterprisePricingEngine.js'
import { optimizeMacroProfit } from './macroProfitEngine.js'

export function runGlobalEconomicSystem(context = {}) {
  const graph = buildEconomicGraph(context.tenants)
  const industrySupply = simulateIndustrySupply(context)
  const crossEnterprisePricing = simulateCrossEnterprisePricing(context)
  const macroProfit = optimizeMacroProfit(context)

  return {
    mode: 'V25_GLOBAL_ECONOMIC_OPERATING_SYSTEM',
    globalEconomicMode: 'ON',
    multiEnterpriseGraph: 'ACTIVE',
    industrySimulation: 'ENABLED',
    macroOptimization: 'ACTIVE',
    graph,
    industrySupply,
    crossEnterprisePricing,
    macroProfit,
    metrics: {
      industryStability: industrySupply.supplyPressure.status === 'BALANCED' ? 92 : 68,
      crossEnterpriseInfluence: graph.interactions.filter((item) => item.impactLevel === 'HIGH').length,
      globalDemand: industrySupply.demandForecast.totalDemand,
      macroProfitEfficiency: macroProfit.macroProfitEfficiencyScore,
    },
  }
}
