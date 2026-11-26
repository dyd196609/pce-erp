import { getAcquisitionFunnel, trackAcquisition } from './acquisitionEngine.js'
import { getActivationFunnel, recordActivation } from './activationEngine.js'
import { calculateRetentionMetrics, getRetentionHeatmap, recordRetentionActivity } from './retentionEngine.js'
import { getRevenueGrowth, trackRevenueEvent } from './revenueEngine.js'
import { getReferralNetwork, trackReferral } from './referralEngine.js'
import { evaluateEnterpriseUpsell } from './revenueExpansionEngine.js'
import { getViralGrowthSnapshot } from './viralGrowthEngine.js'

export function runGrowthRuntime(context = {}) {
  const tenantId = context.tenantId || context.tenant?.id || context.runtimeState?.tenant?.id || 'demo_company'

  if (context.trackAcquisition) {
    trackAcquisition({
      ...context.trackAcquisition,
      tenantId,
    })
  }

  if (context.activationStep) {
    recordActivation({
      tenantId,
      step: context.activationStep,
      module: context.module,
    })
  }

  if (context.retentionActivity) {
    recordRetentionActivity({
      ...context.retentionActivity,
      tenantId,
    })
  }

  if (context.revenueEvent) {
    trackRevenueEvent({
      ...context.revenueEvent,
      tenantId,
    })
  }

  if (context.referralEvent) {
    trackReferral({
      ...context.referralEvent,
      fromTenant: tenantId,
    })
  }

  const retention = calculateRetentionMetrics()
  const revenueExpansion = evaluateEnterpriseUpsell({
    tenantId,
    tenant: context.tenant,
    plan: context.plan || context.runtimeState?.plan,
    track: context.trackRevenueExpansion === true,
  })
  const revenue = getRevenueGrowth()
  const viral = getViralGrowthSnapshot(context)
  const referral = viral.network
  const activation = getActivationFunnel(tenantId)
  const acquisition = getAcquisitionFunnel()
  const funnelConversionRate = acquisition.length
    ? acquisition.reduce((sum, item) => sum + item.conversionRate, 0) / acquisition.length
    : 0
  const viralCoefficient = viral.viralCoefficient

  return {
    mode: 'V17_SAAS_GROWTH_OS',
    growthMode: 'ACTIVE',
    acquisitionTracking: 'ON',
    activationTracking: 'ON',
    retentionTracking: 'ON',
    revenueExpansion: 'ACTIVE',
    viralGrowth: 'ENABLED',
    tenantId,
    acquisition,
    activation,
    retention,
    retentionHeatmap: getRetentionHeatmap(),
    revenue,
    revenueExpansionSnapshot: revenueExpansion,
    referral,
    viral,
    growthRate: revenue.expansionRevenue > 0 ? Math.min(1, revenue.expansionRevenue / 1000) : 0,
    churnRate: retention.mau === 0 ? 0 : Math.max(0, 1 - retention.wau / retention.mau),
    metrics: {
      growthRateIndex: Math.round(Math.min(100, (revenue.expansionRevenue / 10) + activation.activationScore + viralCoefficient * 10)),
      funnelConversionRate: Math.round(funnelConversionRate * 100),
      retentionCurve: retention.engagementScore,
      revenueExpansionScore: revenueExpansion.score,
      viralCoefficient,
    },
  }
}
