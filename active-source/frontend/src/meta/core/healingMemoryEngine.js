const healingMemory = []

export function recordHealing(entry) {
  healingMemory.push({
    ...entry,
    timestamp: Date.now(),
  })
}

export function getHealingMemory() {
  return healingMemory
}
