import { getDecisionMemory } from './decisionMemoryEngine.js'

export function analyzeConflicts() {
  const memory = getDecisionMemory()

  const conflicts = memory.filter((entry) => {
    return (
      entry.executionDecision &&
      entry.governanceDecision &&
      entry.executionDecision !== entry.governanceDecision
    )
  })

  return {
    total: memory.length,
    conflicts: conflicts.length,
    conflictRate: memory.length ? conflicts.length / memory.length : 0,
  }
}
