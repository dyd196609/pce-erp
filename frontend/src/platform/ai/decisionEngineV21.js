// ======================================
// Meta Runtime V21 - Decision Engine
// AI企业决策核心
// ======================================

import { evaluateSystem } from './goalEngineV21'
import { optimizeSystem } from './aiBrainV20'

/**
 * AI自动决策
 */
export const makeDecision = (state, meta) => {
  const evaluation = evaluateSystem(state)

  if (evaluation.profitGap > 0) {
    return {
      action: 'OPTIMIZE_COST',
      reason: 'profit low',
    }
  }

  if (evaluation.riskGap > 0) {
    return {
      action: 'REDUCE_RISK',
      reason: 'risk high',
    }
  }

  return {
    action: 'MAINTAIN',
    reason: 'stable system',
  }
}

/**
 * 执行自治行为
 */
export const executeAutonomy = (decision, meta) => {
  switch (decision.action) {
    case 'OPTIMIZE_COST':
      meta = optimizeSystem(meta)
      break

    case 'REDUCE_RISK':
      meta = optimizeSystem(meta)
      break

    default:
      break
  }

  return meta
}
