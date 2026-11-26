import { detectBusinessSignals } from './businessSignalEngine.js'

export function generateGoals(context = {}) {
  const signals = detectBusinessSignals(context)
  const goals = signals
    .map((signal) => {
      switch (signal.type) {
        case 'LOW_STOCK':
          return {
            goal: 'Auto replenish inventory',
            type: 'INVENTORY',
            priority: 'HIGH',
            source: 'auto',
            signal,
          }

        case 'PURCHASE_DELAY':
          return {
            goal: 'Optimize procurement workflow',
            type: 'PROCUREMENT',
            priority: 'MEDIUM',
            source: 'auto',
            signal,
          }

        case 'FINANCE_ANOMALY':
          return {
            goal: 'Review finance anomaly',
            type: 'FINANCE',
            priority: 'HIGH',
            source: 'auto',
            signal,
          }

        default:
          return null
      }
    })
    .filter(Boolean)

  return {
    mode: 'AUTO_GOAL_GENERATION',
    goals,
  }
}