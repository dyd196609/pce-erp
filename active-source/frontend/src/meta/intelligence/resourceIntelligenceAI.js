export function dynamicResourceAllocation(context = {}) {
  const resources = context.optimizationRuntime?.resources || context.resourceAllocation || {}
  const humanResources = resources.humanResources || []

  return humanResources.map((resource) => ({
    role: resource.role,
    allocation: resource.allocation,
    dynamicAllocation: resource.workload > 1 ? 'ASSIGN_BACKUP_OWNER' : 'KEEP_PRIMARY_OWNER',
    confidence: resource.workload > 1 ? 82 : 94,
  }))
}

export function balanceWorkload(context = {}) {
  const allocation = dynamicResourceAllocation(context)
  const rebalanced = allocation.filter((item) => item.dynamicAllocation === 'ASSIGN_BACKUP_OWNER')

  return {
    balanced: rebalanced.length === 0,
    rebalancedRoles: rebalanced,
    policy: 'ROLE_LOAD_BALANCING',
  }
}

export function assignByEfficiency(context = {}) {
  const performance = context.optimizationRuntime?.performance || context.performance || {}
  const departments = performance.departmentPerformance || []

  return departments.map((department) => ({
    role: department.role,
    assignment: department.performance === 'GOOD' ? 'PRIMARY_OWNER' : 'BACKUP_REQUIRED',
    efficiency: department.completionRate,
  }))
}

export function optimizeResources(context = {}) {
  return {
    resourceIntelligence: 'ACTIVE',
    dynamicAllocation: dynamicResourceAllocation(context),
    workloadBalancing: balanceWorkload(context),
    efficiencyAssignment: assignByEfficiency(context),
  }
}
