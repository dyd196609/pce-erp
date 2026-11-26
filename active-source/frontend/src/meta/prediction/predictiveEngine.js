import { calculateApproval } from './approvalPredictionEngine.js'
import { estimateCost } from './costPredictionEngine.js'
import { evaluateRisk } from './riskPredictionEngine.js'
import { predictTime } from './timePredictionEngine.js'

export function predictAction(context = {}) {
  const approvalProbability = calculateApproval(context)
  const costImpact = estimateCost(context)
  const riskLevel = evaluateRisk({
    ...context,
    costImpact,
  })
  const executionTime = predictTime({
    ...context,
    approvalProbability,
  })

  return {
    predictionMode: 'ON',
    predictiveEngine: 'ACTIVE',
    decisionPreview: 'ENABLED',
    approvalProbability,
    costImpact,
    riskLevel,
    executionTime,
  }
}
