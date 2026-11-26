function countBottlenecks(context = {}) {
  return context.optimizationRuntime?.process?.bottlenecks?.length
    || context.processOptimization?.bottlenecks?.length
    || 0
}

export function evaluateWorkflowRisk(context = {}) {
  const executionData = context.executionClosedLoop || context.executionData || context
  const consistent = executionData.workflow?.consistency?.consistent !== false
  const breakpoints = executionData.breakpoints?.length || 0
  const bottlenecks = countBottlenecks(context)
  const score = Math.min(100, (consistent ? 18 : 55) + breakpoints * 18 + bottlenecks * 12)

  return {
    area: 'workflow',
    score,
    level: score >= 70 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW',
    signal: consistent ? 'STATE_MACHINE_CONSISTENT' : 'STATE_MACHINE_REVIEW_REQUIRED',
  }
}

export function evaluateFinancialRisk(context = {}) {
  const totalImpact = Math.abs(context.costImpact?.totalImpact || context.costOptimization?.totalSaving || 0)
  const score = totalImpact > 15000 ? 42 : totalImpact > 5000 ? 30 : 18

  return {
    area: 'financial',
    score,
    level: score >= 70 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW',
    signal: totalImpact > 15000 ? 'HIGH_COST_VARIANCE' : 'COST_IMPACT_CONTROLLED',
  }
}

export function evaluateSupplyChainRisk(context = {}) {
  const predictedBottlenecks = context.intelligenceOptimizationRuntime?.predictedImprovements?.predictedBottlenecks?.length
    || context.globalOptimization?.predictedImprovements?.predictedBottlenecks?.length
    || 0
  const score = Math.min(100, 22 + predictedBottlenecks * 16)

  return {
    area: 'supply_chain',
    score,
    level: score >= 70 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW',
    signal: predictedBottlenecks ? 'PREDICTED_BOTTLENECKS_PRESENT' : 'SUPPLY_CHAIN_STABLE',
  }
}

export function evaluateRisk(context = {}) {
  const workflow = evaluateWorkflowRisk(context)
  const financial = evaluateFinancialRisk(context)
  const supplyChain = evaluateSupplyChainRisk(context)
  const score = Math.round((workflow.score + financial.score + supplyChain.score) / 3)

  return {
    riskPrediction: 'ACTIVE',
    score,
    level: score >= 70 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW',
    workflow,
    financial,
    supplyChain,
  }
}
