const agentScores = {}

export function updateAgentScore(agent, delta = 0) {
  const key = agent || 'UNKNOWN'
  agentScores[key] = (agentScores[key] || 0) + delta

  return {
    agent: key,
    score: agentScores[key],
  }
}

export function getAgentScores() {
  return agentScores
}
