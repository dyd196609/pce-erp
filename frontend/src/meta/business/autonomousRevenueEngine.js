import { getUsage, listSaasPlans } from '../saas/billing/billingEngine.js'
import { runGrowthRuntime } from '../growth/growthRuntime.js'

export function analyzeUsagePatterns(context = {}) {
  const tenantId = context.tenantId || context.runtimeState?.tenant?.id || 'demo_company'
  const usage = getUsage(tenantId)
  const totals = usage.reduce((acc, item) => {
    acc[item.type] = (acc[item.type] || 0) + item.units
    acc.total += item.units
    acc.modules[item.module] = (acc.modules[item.module] || 0) + item.units
    return acc
  }, {
    total: 0,
    modules: {},
  })
  const growth = runGrowthRuntime({
    ...context,
    tenantId,
  })

  return {
    tenantId,
    plan: context.plan || context.runtimeState?.plan || context.tenant?.plan || 'free',
    usage,
    totals,
    growth,
    intensity: totals.total > 50 ? 'HIGH' : totals.total > 10 ? 'MEDIUM' : 'LOW',
  }
}

export function adjustPricingStrategy(usage = {}) {
  const plans = listSaasPlans()
  const multiplier = usage.intensity === 'HIGH' ? 1.15 : usage.intensity === 'MEDIUM' ? 1.05 : 1

  return {
    mode: 'AUTONOMOUS_PRICING',
    multiplier,
    prices: Object.fromEntries(
      Object.entries(plans).map(([plan, price]) => [plan, Math.round(price * multiplier)])
    ),
    reason: usage.intensity === 'HIGH'
      ? 'HIGH_USAGE_VALUE_CAPTURE'
      : usage.intensity === 'MEDIUM'
      ? 'MODERATE_USAGE_OPTIMIZATION'
      : 'MAINTAIN_ENTRY_PRICING',
  }
}

export function suggestUpgrades(usage = {}) {
  const current = usage.plan || 'free'
  const hasAiUsage = (usage.totals.aiDecision || 0) > 0
  const highUsage = usage.intensity === 'HIGH'

  if (current === 'free') {
    return [{ from: 'free', to: highUsage ? 'pro' : 'basic', reason: 'ACTIVATION_TO_PAID' }]
  }

  if (current === 'basic' && (highUsage || hasAiUsage)) {
    return [{ from: 'basic', to: 'pro', reason: 'SIMULATION_AND_USAGE_EXPANSION' }]
  }

  if (current === 'pro' && hasAiUsage) {
    return [{ from: 'pro', to: 'enterprise', reason: 'AI_FEATURE_MONETIZATION' }]
  }

  return []
}

export function optimizeRevenue(context = {}) {
  const usage = analyzeUsagePatterns(context)
  const pricing = adjustPricingStrategy(usage)
  const upgrades = suggestUpgrades(usage)

  return {
    mode: 'V23_AUTONOMOUS_REVENUE',
    usage,
    revenueModel: pricing,
    upgradePaths: upgrades,
  }
}
