function severityFromDuration(durationMs = 0) {
  if (durationMs >= 1400) return 'HIGH'
  if (durationMs >= 1100) return 'MEDIUM'
  return 'LOW'
}

export function detectSlowWorkflows(executionData = {}) {
  const timeline = executionData.timeline?.timeline || executionData.timeline || []

  return timeline
    .filter((item) => Number(item.durationMs || 0) >= 1100)
    .map((item) => ({
      type: 'SLOW_WORKFLOW',
      step: item.to,
      role: item.role,
      durationMs: item.durationMs,
      severity: severityFromDuration(item.durationMs),
      recommendation: `Reduce handoff time around ${item.to}`,
    }))
}

export function detectBlockedProcesses(executionData = {}) {
  const timeline = executionData.timeline?.timeline || executionData.timeline || []
  const breakpoints = executionData.breakpoints || []

  return [
    ...timeline
      .filter((item) => item.status === 'BLOCKED')
      .map((item) => ({
        type: 'BLOCKED_PROCESS',
        step: item.to,
        role: item.role,
        severity: 'HIGH',
        recommendation: item.reason || 'Review blocked transition',
      })),
    ...breakpoints.map((breakpoint) => ({
      type: 'PROCESS_BREAKPOINT',
      step: breakpoint,
      role: 'Process Owner',
      severity: 'HIGH',
      recommendation: 'Close execution breakpoint before release',
    })),
  ]
}

export function detectInefficientRoles(executionData = {}) {
  const tasks = executionData.tasks || []

  return tasks
    .filter((item) => item.completion?.task?.status !== 'COMPLETED' || item.assigned?.dependencyStatus?.missing?.length)
    .map((item) => ({
      type: 'INEFFICIENT_ROLE',
      step: item.assigned.step,
      role: item.assigned.role,
      severity: 'MEDIUM',
      recommendation: `Rebalance workload for ${item.assigned.role}`,
    }))
}

export function detectBottlenecks(executionData = {}) {
  const bottlenecks = [
    ...detectSlowWorkflows(executionData),
    ...detectBlockedProcesses(executionData),
    ...detectInefficientRoles(executionData),
  ]

  return bottlenecks.length
    ? bottlenecks
    : [{
        type: 'OPTIMIZATION_CANDIDATE',
        step: 'approved',
        role: 'Finance Controller',
        severity: 'LOW',
        recommendation: 'Automate approval notification to preserve speed',
      }]
}
