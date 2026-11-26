import { getHealingMemory } from './healingMemoryEngine.js'

export function analyzeHealingPatterns() {
  const memory = getHealingMemory()
  const patternMap = {}

  memory.forEach((memoryEntry) => {
    const key = memoryEntry.issue?.type || 'UNKNOWN'

    if (!patternMap[key]) {
      patternMap[key] = {
        count: 0,
        success: 0,
        rollback: 0,
      }
    }

    patternMap[key].count += 1

    if (memoryEntry.status === 'SUCCESS') {
      patternMap[key].success += 1
    }

    if (memoryEntry.status === 'ROLLBACK') {
      patternMap[key].rollback += 1
    }
  })

  return patternMap
}
