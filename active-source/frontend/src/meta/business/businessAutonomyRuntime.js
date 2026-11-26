import { optimizeRevenue } from './autonomousRevenueEngine.js'
import { runAutonomousBusinessDecision } from './autonomousDecisionEngine.js'
import { evolveProduct } from './productEvolutionEngine.js'
import { runMarketControl } from './marketControlEngine.js'

export function runAutonomousBusiness(context = {}) {
  const revenue = optimizeRevenue(context)
  const decision = runAutonomousBusinessDecision(context)
  const productEvolution = evolveProduct(context)
  const marketControl = runMarketControl(context)

  return {
    mode: 'V23_FULLY_AUTONOMOUS_BUSINESS',
    autonomousBusinessMode: 'ON',
    revenueOptimization: 'ACTIVE',
    productEvolution: 'ENABLED',
    marketControl: 'ACTIVE',
    revenue,
    decision,
    productEvolution,
    marketControl,
    metrics: {
      autonomousRevenue: revenue.revenueModel.prices[revenue.usage.plan] || 0,
      pricingAdjustment: revenue.revenueModel.multiplier,
      productEvolutionSteps: productEvolution.timeline.length,
      marketHeat: marketControl.popularity.filter((item) => item.heat === 'HOT').length,
    },
  }
}
