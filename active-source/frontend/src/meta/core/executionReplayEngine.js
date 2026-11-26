export function replayExecution(memoryEntry) {
  return {
    original: memoryEntry,
    replay: memoryEntry?.shadow,
    diff: memoryEntry?.diff,
  }
}
