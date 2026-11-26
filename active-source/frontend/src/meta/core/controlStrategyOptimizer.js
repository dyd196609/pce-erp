import { analyzeControlPatterns } from './controlPatternEngine.js'

export function optimizeControlStrategy() {
  const analysis = analyzeControlPatterns()
  const total = analysis.total || 1
  const execRate = analysis.patterns.EXECUTION / total
  const govRate = analysis.patterns.GOVERNANCE / total
  const healRate = analysis.patterns.SELF_HEALING / total

  const strategy = {
    EXECUTION: 0.4,
    GOVERNANCE: 0.4,
    SELF_HEALING: 0.2,
  }

  if (govRate > 0.5) {
    strategy.GOVERNANCE = 0.3
    strategy.EXECUTION = 0.5
  }

  if (execRate > 0.6) {
    strategy.GOVERNANCE = 0.5
    strategy.EXECUTION = 0.3
  }

  if (healRate > 0.3) {
    strategy.SELF_HEALING = 0.1
  }

  return {
    strategy,
    analysis,
  }
}
