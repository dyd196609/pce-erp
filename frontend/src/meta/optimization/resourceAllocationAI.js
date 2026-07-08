export function allocateHumanResources(executionData = {}) {
  const roles = (executionData.tasks || []).map((item) => item.assigned?.role).filter(Boolean)
  const uniqueRoles = [...new Set(roles)]

  return uniqueRoles.map((role) => ({
    role,
    allocation: role.includes('Manager') ? 'review_lane' : 'execution_lane',
    workload: roles.filter((item) => item === role).length,
    recommendation: `Keep ${role} focused on ${role.includes('Manager') ? 'approval' : 'execution'} work`,
  }))
}

export function allocateSystemResources(executionData = {}) {
  const replayCount = executionData.timeline?.replay?.length || 0

  return {
    workflowWorkers: Math.max(1, replayCount),
    timelineWorkers: 1,
    auditWorkers: 1,
    recommendation: 'Reserve workflow worker capacity for replay and audit generation',
  }
}

export function optimizeWorkloadDistribution(executionData = {}) {
  const human = allocateHumanResources(executionData)
  const overloaded = human.filter((item) => item.workload > 1)

  return {
    balanced: overloaded.length === 0,
    overloadedRoles: overloaded,
    recommendation: overloaded.length
      ? 'Split repeated role tasks across backup owners'
      : 'Current role workload is balanced',
  }
}

export function allocateResources(executionData = {}) {
  return {
    resourceAI: 'ACTIVE',
    humanResources: allocateHumanResources(executionData),
    systemResources: allocateSystemResources(executionData),
    workloadDistribution: optimizeWorkloadDistribution(executionData),
  }
}
