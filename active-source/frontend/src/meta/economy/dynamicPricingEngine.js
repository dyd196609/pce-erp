import { optimizeRevenue } from '../business/autonomousRevenueEngine.js'

export function adjustRealTimePrice(context = {}) {
  const revenue = optimizeRevenue(context)
  const basePrice = revenue.revenueModel.prices[revenue.usage.plan] || 0
  const usageFactor = revenue.usage.intensity === 'HIGH' ? 1.12 : revenue.usage.intensity === 'MEDIUM' ? 1.05 : 0.98

  return {
    basePrice,
    adjustedPrice: Math.round(basePrice * usageFactor),
    usageFactor,
    reason: revenue.usage.intensity,
  }
}

export function priceByUserBehavior(context = {}) {
  const revenue = optimizeRevenue(context)
  const activation = revenue.usage.growth.activation?.completed || 0
  const retention = revenue.usage.growth.retention?.workflowRecurrenceRate || 0
  const behaviorScore = Math.min(100, activation * 20 + retention * 100)

  return {
    behaviorScore,
    incentive: behaviorScore < 50 ? 'DISCOUNT_TO_ACTIVATE' : 'VALUE_BASED_PRICING',
    adjustment: behaviorScore < 50 ? -0.08 : 0.05,
  }
}

export function evolveEnterpriseTierPricing(context = {}) {
  const revenue = optimizeRevenue(context)

  return revenue.upgradePaths.map((path) => ({
    from: path.from,
    to: path.to,
    trigger: path.reason,
    pricingAction: 'GRADUAL_TIER_UPSELL',
  }))
}

export function dynamicPricing(context = {}) {
  const realtime = adjustRealTimePrice(context)
  const behavior = priceByUserBehavior(context)
  const tierEvolution = evolveEnterpriseTierPricing(context)
  const finalPrice = Math.max(0, Math.round(realtime.adjustedPrice * (1 + behavior.adjustment)))

  return {
    mode: 'V24_DYNAMIC_PRICING',
    realtime,
    behavior,
    tierEvolution,
    finalPrice,
    volatility: realtime.basePrice === 0 ? 0 : Math.abs(finalPrice - realtime.basePrice) / realtime.basePrice,
  }
}
