import { getControlMemory } from './controlDecisionMemoryEngine.js'

export function analyzeControlPatterns() {
  const memory = getControlMemory()
  const patterns = {
    EXECUTION: 0,
    GOVERNANCE: 0,
    SELF_HEALING: 0,
  }
  const transitions = []

  memory.forEach((entry, index) => {
    patterns[entry.authority] = (patterns[entry.authority] || 0) + 1

    if (index > 0) {
      transitions.push({
        from: memory[index - 1].authority,
        to: entry.authority,
      })
    }
  })

  return {
    patterns,
    transitions,
    total: memory.length,
  }
}
