import { getRevenueEvents } from '../revenueSharingEngine.js'

function calculateFairnessIndex(events) {
  if (events.length === 0) return 100

  const averageDeveloperShare = events.reduce((sum, event) => {
    const ratio = event.amount === 0 ? 0 : event.developerShare / event.amount
    return sum + ratio
  }, 0) / events.length

  return Math.round(Math.min(100, averageDeveloperShare * 140))
}

export function calculateFairRevenueSplit(event = {}) {
  const usageUnits = Number(event.usageUnits || 1)
  const basePlatformRate = event.platformRate == null ? 0.3 : Number(event.platformRate)
  const usageReward = usageUnits > 10 ? 0.05 : 0
  const adjustedPlatformRate = Math.max(0.15, basePlatformRate - usageReward)
  const amount = Number(event.amount || 0)
  const platformShare = Number((amount * adjustedPlatformRate).toFixed(2))

  return {
    amount,
    adjustedPlatformRate,
    platformShare,
    developerShare: Number((amount - platformShare).toFixed(2)),
    usageReward,
  }
}

export function evaluateRevenueFairness() {
  const events = getRevenueEvents()
  const fairnessIndex = calculateFairnessIndex(events)

  return {
    mode: 'V21_REVENUE_FAIRNESS',
    fairnessIndex,
    status: fairnessIndex >= 70 ? 'FAIR' : 'REVIEW',
    events: events.map((event) => ({
      pluginId: event.pluginId,
      moduleKey: event.moduleKey,
      developerId: event.developerId,
      amount: event.amount,
      platformShare: event.platformShare,
      developerShare: event.developerShare,
      fairSplit: calculateFairRevenueSplit(event),
    })),
  }
}
