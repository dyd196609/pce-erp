export function resolveAgentConflicts(results) {
  const conflicts = []

  results.forEach((result) => {
    if (result.agent === 'FINANCE' && result.result.includes('error')) {
      conflicts.push(result)
    }
  })

  return {
    resolved: true,
    conflicts,
  }
}
