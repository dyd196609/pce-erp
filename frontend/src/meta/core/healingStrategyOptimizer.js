import { analyzeHealingPatterns } from './healingPatternEngine.js'

export function optimizeHealingStrategy() {
  const patterns = analyzeHealingPatterns()
  const strategy = {}

  Object.keys(patterns).forEach((type) => {
    const pattern = patterns[type]
    const successRate = pattern.success / (pattern.count || 1)

    strategy[type] = {
      recommendedAction:
        successRate > 0.7
          ? 'AUTO_HEAL_ENABLE'
          : successRate > 0.4
            ? 'LIMITED_AUTO_HEAL'
            : 'MANUAL_ONLY',
      successRate,
    }
  })

  return strategy
}
