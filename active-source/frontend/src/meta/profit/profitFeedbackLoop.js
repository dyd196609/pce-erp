import { updateAgentScore } from '../core/agentScoreEngine.js'

export function applyProfitFeedback(agent, profitResult) {
  if (profitResult.decision === 'REPRICE') {
    updateAgentScore(agent, -0.1)
  }

  if (profitResult.decision === 'EXPAND') {
    updateAgentScore(agent, 0.2)
  }
}
