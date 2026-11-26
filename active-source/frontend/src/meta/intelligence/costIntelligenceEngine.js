export function selectCheapestExecutionPath(context = {}) {
  const cost = context.optimizationRuntime?.cost || context.costOptimization || {}
  const candidates = [
    { path: 'standard_purchase', cost: cost.procurement?.currentCost || 100000 },
    { path: 'optimized_purchase', cost: cost.procurement?.optimizedCost || 94600 },
    { path: 'batch_approval_purchase', cost: (cost.procurement?.optimizedCost || 94600) - 1600 },
  ]
  const selected = candidates.sort((a, b) => a.cost - b.cost)[0]

  return {
    selected,
    candidates,
  }
}

export function optimizeProcurementStrategy(context = {}) {
  const cheapest = selectCheapestExecutionPath(context)

  return {
    strategy: 'BATCH_APPROVAL_AND_SUPPLIER_COST_RECHECK',
    executionPath: cheapest.selected.path,
    estimatedCost: cheapest.selected.cost,
    recommendation: 'Use optimized purchase path before finance posting',
  }
}

export function reduceOperationalCostDynamically(context = {}) {
  const cost = context.optimizationRuntime?.cost || context.costOptimization || {}
  const cheapest = selectCheapestExecutionPath(context)
  const baseline = cost.procurement?.currentCost || 100000

  return {
    baseline,
    optimized: cheapest.selected.cost,
    dynamicSaving: Math.max(0, baseline - cheapest.selected.cost),
    savingRate: baseline ? Math.max(0, baseline - cheapest.selected.cost) / baseline : 0,
  }
}

export function optimizeCosts(context = {}) {
  return {
    costIntelligence: 'ACTIVE',
    cheapestExecutionPath: selectCheapestExecutionPath(context),
    procurementStrategy: optimizeProcurementStrategy(context),
    operationalCost: reduceOperationalCostDynamically(context),
  }
}
