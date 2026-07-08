const decisionMemory = []

export function recordDecision(entry) {
  decisionMemory.push({
    ...entry,
    timestamp: Date.now(),
  })
}

export function getDecisionMemory() {
  return decisionMemory
}
