import { distributeRevenue, getRevenueDistribution } from '../revenueSharingEngine.js'

export function calculatePlatformCut(amount = 0, platformRate = 0.3) {
  return Number((Number(amount || 0) * platformRate).toFixed(2))
}

export function calculateDeveloperShare(amount = 0, platformRate = 0.3) {
  return Number((Number(amount || 0) - calculatePlatformCut(amount, platformRate)).toFixed(2))
}

export function splitUsageBilling(event = {}) {
  return distributeRevenue({
    pluginId: event.pluginId,
    moduleKey: event.moduleKey || event.pluginId,
    developerId: event.developerId,
    tenantId: event.tenantId,
    amount: event.amount || Number(event.usageUnits || 1) * Number(event.unitPrice || 1),
    usageUnits: event.usageUnits || 1,
    platformRate: event.platformRate ?? 0.3,
  })
}

export function getRevenueSharingSnapshot() {
  const distribution = getRevenueDistribution()
  return {
    revenueSharing: 'ACTIVE',
    platformRevenueCut: distribution.platformRevenue,
    developerRevenueShare: distribution.developerRevenue,
    usageBasedBillingSplit: 'ACTIVE',
    distribution,
  }
}
