const agents = {}

export function registerAgent(name, agent) {
  agents[name] = agent
}

export function getAgent(name) {
  return agents[name]
}

export function getAllAgents() {
  return Object.keys(agents)
}
