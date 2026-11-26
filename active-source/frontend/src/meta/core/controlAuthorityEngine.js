import { calculateDriftScore } from './contractDriftEngine.js'
import { recordControlDecision } from './controlDecisionMemoryEngine.js'
import { optimizeControlStrategy } from './controlStrategyOptimizer.js'
import { analyzeConflicts } from './decisionConflictEngine.js'

export function resolveControlAuthority(context = {}) {
  const conflict = analyzeConflicts()
  const drift = calculateDriftScore()
  let authority = 'EXECUTION'

  if (drift.driftScore > 0.5) {
    authority = 'GOVERNANCE'
  }

  if (conflict.conflictRate > 0.3) {
    authority = 'GOVERNANCE'
  }

  if (context.systemError === true) {
    authority = 'SELF_HEALING'
  }

  if (drift.driftScore < 0.1 && conflict.conflictRate < 0.1 && context.systemError !== true) {
    authority = 'EXECUTION'
  }

  const strategy = optimizeControlStrategy()
  const result = {
    authority,
    drift: drift.driftScore,
    conflict: conflict.conflictRate,
    strategy: strategy.strategy,
  }

  recordControlDecision({
    authority,
    strategy: strategy.strategy,
    drift: drift.driftScore,
    conflict: conflict.conflictRate,
  })

  return result
}
