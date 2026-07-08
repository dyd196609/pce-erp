const coreBusinessModules = ['finance', 'crm', 'scm', 'inventory', 'purchase']

export function detectBusinessCoreDeviation(change = {}) {
  const moduleChanges = change.moduleChanges || {}
  const touchedModules = [
    ...(moduleChanges.splits || []).map((item) => item.module),
    ...(moduleChanges.merges || []).flatMap((item) => item.modules || []),
  ]
  const outsideCore = touchedModules.filter((module) => module && !coreBusinessModules.includes(module))

  return {
    deviated: outsideCore.length > 0,
    outsideCore,
  }
}

export function detectOverComplexityGrowth(change = {}) {
  const moduleChanges = change.moduleChanges || {}
  const workflowChanges = change.workflowChanges || {}
  const complexity = (moduleChanges.splits?.length || 0) * 2 +
    (moduleChanges.merges?.length || 0) +
    (workflowChanges.pathOptimization?.changes?.length || 0)

  return {
    overComplex: complexity > 8,
    complexity,
  }
}

export function detectUnnecessaryEvolution(change = {}) {
  const proposals = change.performance?.proposals || []
  const stablePerformance = (change.performance?.score ?? 0) >= 92

  return {
    unnecessary: stablePerformance && proposals.includes('preserve_current_structure'),
    reason: stablePerformance ? 'performance_already_stable' : 'optimization_needed',
  }
}

export function detectSystemDrift(change = {}) {
  const coreDeviation = detectBusinessCoreDeviation(change)
  const complexityGrowth = detectOverComplexityGrowth(change)
  const unnecessaryEvolution = detectUnnecessaryEvolution(change)
  const driftScore = [
    coreDeviation.deviated ? 35 : 0,
    complexityGrowth.overComplex ? 35 : Math.min(20, complexityGrowth.complexity * 2),
    unnecessaryEvolution.unnecessary ? 20 : 0,
  ].reduce((sum, score) => sum + score, 0)

  return {
    driftProtection: 'ACTIVE',
    driftScore,
    driftLevel: driftScore >= 70 ? 'HIGH' : driftScore >= 35 ? 'MEDIUM' : 'LOW',
    coreDeviation,
    complexityGrowth,
    unnecessaryEvolution,
  }
}
