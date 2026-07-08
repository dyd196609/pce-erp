const executionMemory = []

export function recordExecution(entry) {
  executionMemory.push({
    ...entry,
    timestamp: Date.now(),
  })
}

export function getExecutionMemory() {
  return executionMemory
}
