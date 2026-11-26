const controlMemory = []

export function recordControlDecision(entry) {
  controlMemory.push({
    ...entry,
    timestamp: Date.now(),
  })
}

export function getControlMemory() {
  return controlMemory
}
