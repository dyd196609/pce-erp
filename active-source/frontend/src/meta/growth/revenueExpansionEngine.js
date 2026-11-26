import { getCommercialBillingSnapshot } from '../saas/billing/billingEngine.js'
import { getUsage } from '../saas/billing/billingEngine.js'
import { getRevenueGrowth, trackSubscriptionUpgrade, trackModulePurchase } from './revenueEngine.js'

export function recommendUpgrade(context = {}) {
  const plan = context.plan || context.tenant?.plan || 'basic'
  const usage = getUsage(context.tenantId || context.tenant?.id)
  const highUsage = usage.length > 10

  if (plan !== 'enterprise' && highUsage) {
    return {
      recommendedPlan: 'enterprise',
      reason: 'usage_above_team_threshold',
      confidence: 88,
    }
  }

  if (plan === 'basic') {
    return {
      recommendedPlan: 'pro',
      reason: 'standard_growth_path',
      confidence: 74,
    }
  }

  return {
    recommendedPlan: plan,
    reason: 'current_plan_fit',
    confidence: 68,
  }
}

export function calculateUsageExpansion(context = {}) {
  const tenantId = context.tenantId || context.tenant?.id || 'demo_company'
  const usage = getUsage(tenantId)
  const expansionValue = usage.reduce((sum, item) => sum + Number(item.units || 0), 0) * 0.08

  return {
    tenantId,
    usageRecords: usage.length,
    expansionValue: Number(expansionValue.toFixed(2)),
  }
}

export function evaluateEnterpriseUpsell(context = {}) {
  const billing = getCommercialBillingSnapshot(context)
  const usageExpansion = calculateUsageExpansion(context)
  const recommendation = recommendUpgrade(context)
  const shouldUpsell = recommendation.recommendedPlan === 'enterprise' || billing.bill.total > 500

  if (shouldUpsell && context.track !== false) {
    trackSubscriptionUpgrade({
      tenantId: context.tenantId,
      fromPlan: context.plan || 'basic',
      toPlan: recommendation.recommendedPlan,
    })
  }

  if (usageExpansion.expansionValue > 0 && context.track !== false) {
    trackModulePurchase({
      tenantId: context.tenantId,
      module: 'usage_expansion',
      amount: usageExpansion.expansionValue,
    })
  }

  return {
    revenueExpansion: 'ACTIVE',
    recommendation,
    usageExpansion,
    enterpriseUpsell: {
      eligible: shouldUpsell,
      targetPlan: recommendation.recommendedPlan,
    },
    revenue: getRevenueGrowth(),
    score: Math.min(100, Math.round(70 + usageExpansion.usageRecords * 3 + (shouldUpsell ? 10 : 0))),
  }
}
