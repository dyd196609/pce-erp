import { calculateCustomerProfit } from '../profit/customerProfitEngine.js'
import { calculateOrderProfit } from '../profit/profitEngine.js'
import { applyProfitFeedback } from '../profit/profitFeedbackLoop.js'
import { buildProfitMatrix } from '../profit/profitMatrixEngine.js'
import { generateProfitDecision } from '../profit/profitDecisionEngine.js'

function calculateProfit(data = {}) {
  if (Array.isArray(data.orders)) {
    return calculateCustomerProfit(data.orders)
  }

  return calculateOrderProfit(data.order || data)
}

function buildMatrix(data = {}) {
  return buildProfitMatrix(data.matrix || data)
}

function generateDecision(data = {}) {
  return generateProfitDecision(data.order || data)
}

function applyFeedback(data = {}, decision) {
  const agent = data.agent || 'PROFITOS'
  applyProfitFeedback(agent, decision)

  return {
    agent,
    decision: decision.decision,
  }
}

export function runBusinessCore(data = {}) {
  const profit = calculateProfit(data)
  const matrix = buildMatrix(data)
  const decision = generateDecision(data)
  const feedback = applyFeedback(data, decision)

  return {
    mode: 'PROFITOS_BUSINESS_CORE',
    profit,
    matrix,
    decision,
    feedback,
  }
}
