const revenueEvents = []

export function distributeRevenue(event = {}) {
  const amount = Number(event.amount || 0)
  const platformRate = event.platformRate == null ? 0.3 : Number(event.platformRate)
  const safeRate = Math.min(Math.max(platformRate, 0), 1)
  const platformShare = Number((amount * safeRate).toFixed(2))
  const developerShare = Number((amount - platformShare).toFixed(2))

  const distribution = {
    mode: 'V20_REVENUE_DISTRIBUTION',
    pluginId: event.pluginId || event.moduleKey || 'unknownPlugin',
    moduleKey: event.moduleKey || event.pluginId || 'unknownModule',
    developerId: event.developerId || 'unknownDeveloper',
    tenantId: event.tenantId || 'demo_company',
    amount,
    usageUnits: event.usageUnits || 1,
    platformRate: safeRate,
    platformShare,
    developerShare,
    timestamp: Date.now(),
  }

  revenueEvents.push(distribution)
  return distribution
}

export function getRevenueEvents() {
  return revenueEvents
}

export function getRevenueDistribution() {
  const totalRevenue = revenueEvents.reduce((sum, event) => sum + event.amount, 0)
  const platformRevenue = revenueEvents.reduce((sum, event) => sum + event.platformShare, 0)
  const developerRevenue = revenueEvents.reduce((sum, event) => sum + event.developerShare, 0)

  return {
    mode: 'V20_REVENUE_FLOW',
    totalRevenue,
    platformRevenue,
    developerRevenue,
    events: revenueEvents.length,
  }
}

export function clearRevenueEvents() {
  revenueEvents.length = 0
}
