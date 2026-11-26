const moduleGroups = {
  commerce: ['crm', 'purchase'],
  operations: ['inventory', 'scm'],
  finance: ['finance'],
}

export function splitModules(systemState = {}) {
  const graph = systemState.orchestration?.dependencyGraph || { edges: [] }
  const denseModules = graph.edges
    .reduce((map, edge) => ({
      ...map,
      [edge.from]: (map[edge.from] || 0) + 1,
      [edge.to]: (map[edge.to] || 0) + 1,
    }), {})

  return Object.entries(denseModules)
    .filter(([, count]) => count > 3)
    .map(([module]) => ({
      module,
      proposal: `${module}_control_plane`,
      reason: 'high_cross_module_connectivity',
    }))
}

export function mergeModules(systemState = {}) {
  const graph = systemState.orchestration?.dependencyGraph || { edges: [] }
  const proposals = []

  Object.entries(moduleGroups).forEach(([group, modules]) => {
    const connected = graph.edges.some((edge) => modules.includes(edge.from) && modules.includes(edge.to))
    if (connected) {
      proposals.push({
        group,
        modules,
        proposal: `${group}_execution_cluster`,
        reason: 'shared_business_flow',
      })
    }
  })

  return proposals
}

export function reassignResponsibilities(systemState = {}) {
  const latestExecution = systemState.execution?.latest || {}
  const actions = latestExecution.executionResult?.actions || []

  return actions.map((action) => ({
    module: action.module,
    responsibility: action.module === 'finance'
      ? 'financial_closure'
      : action.module === 'purchase'
        ? 'procurement_orchestration'
        : 'operational_execution',
    sourceAction: action.action,
  }))
}

export function recombineModules(systemState = {}) {
  return {
    moduleRecomposition: 'ACTIVE',
    splits: splitModules(systemState),
    merges: mergeModules(systemState),
    responsibilities: reassignResponsibilities(systemState),
    timestamp: Date.now(),
  }
}
