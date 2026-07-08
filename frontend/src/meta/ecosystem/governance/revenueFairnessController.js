import { calculateFairRevenueSplit, evaluateRevenueFairness } from './revenueFairnessEngine.js'

export function adjustPlatformDeveloperSplit(event = {}) {
  return calculateFairRevenueSplit(event)
}

export function applyUsageBasedFairnessRules(events = []) {
  return events.map((event) => ({
    pluginId: event.pluginId,
    developerId: event.developerId,
    fairSplit: adjustPlatformDeveloperSplit(event),
  }))
}

export function applyAntiMonopolyControl(events = []) {
  const revenueByDeveloper = events.reduce((map, event) => {
    map[event.developerId] = (map[event.developerId] || 0) + Number(event.developerShare || 0)
    return map
  }, {})
  const total = Object.values(revenueByDeveloper).reduce((sum, value) => sum + value, 0)
  const dominant = Object.entries(revenueByDeveloper).filter(([, value]) => total > 0 && value / total > 0.6)

  return {
    antiMonopoly: dominant.length ? 'WATCH' : 'BALANCED',
    dominantDevelopers: dominant.map(([developerId, revenue]) => ({ developerId, revenue })),
  }
}

export function governRevenueFairness() {
  const fairness = evaluateRevenueFairness()

  return {
    revenueGovernance: 'ACTIVE',
    fairness,
    usageRules: applyUsageBasedFairnessRules(fairness.events),
    monopolyControl: applyAntiMonopolyControl(fairness.events),
  }
}
