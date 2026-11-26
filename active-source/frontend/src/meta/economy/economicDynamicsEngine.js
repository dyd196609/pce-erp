import { dynamicPricing } from './dynamicPricingEngine.js'
import { analyzeDemand, analyzeSupply } from './supplyDemandEngine.js'
import { influenceBehavior } from './behaviorInfluenceEngine.js'
import { optimizeProfit } from './profitOptimizationEngine.js'

export function computeEconomicState(context = {}) {
  const pricingModel = dynamicPricing(context)
  const demandCurve = analyzeDemand(context)
  const supplyCurve = analyzeSupply(context)
  const behaviorInfluence = influenceBehavior(context)
  const profitOptimization = optimizeProfit(context)

  return {
    mode: 'V24_AUTONOMOUS_ECONOMIC_SYSTEM',
    economicMode: 'ON',
    dynamicPricing: 'ACTIVE',
    supplyDemandControl: 'ENABLED',
    behaviorInfluence: 'ACTIVE',
    profitOptimization: 'ACTIVE',
    pricingModel,
    demandCurve,
    supplyCurve,
    behaviorInfluence,
    profitOptimization,
    metrics: {
      economicStability: supplyCurve.balance === 'BALANCED' ? 92 : 72,
      pricingVolatility: pricingModel.volatility,
      demandPressure: demandCurve.pressure,
      profitMaximizationScore: profitOptimization.score,
    },
  }
}
