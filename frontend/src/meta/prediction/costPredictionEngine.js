function getCostOptimization(context = {}) {
  return context.optimizationRuntime?.cost || context.costOptimization || {}
}

export function estimateProcurementCost(context = {}) {
  const costOptimization = getCostOptimization(context)
  const procurement = costOptimization.procurement || {}
  const expectedSaving = procurement.saving || 0

  return {
    area: 'procurement',
    baselineCost: procurement.currentCost || 100000,
    predictedCost: procurement.optimizedCost || 100000 - expectedSaving,
    expectedSaving,
    impact: expectedSaving > 0 ? 'SAVING' : 'NEUTRAL',
  }
}

export function estimateProductionCost(context = {}) {
  const costOptimization = getCostOptimization(context)
  const production = costOptimization.production || {}
  const expectedSaving = production.saving || 0

  return {
    area: 'production',
    baselineCost: production.currentCost || 88000,
    predictedCost: production.optimizedCost || 88000 - expectedSaving,
    expectedSaving,
    impact: expectedSaving > 0 ? 'SAVING' : 'NEUTRAL',
  }
}

export function estimateInventoryCost(context = {}) {
  const costOptimization = getCostOptimization(context)
  const inventory = costOptimization.inventory || {}
  const expectedSaving = inventory.saving || 0

  return {
    area: 'inventory',
    baselineCost: inventory.currentCost || 62000,
    predictedCost: inventory.optimizedCost || 62000 - expectedSaving,
    expectedSaving,
    impact: expectedSaving > 0 ? 'SAVING' : 'NEUTRAL',
  }
}

export function estimateCost(context = {}) {
  const procurement = estimateProcurementCost(context)
  const production = estimateProductionCost(context)
  const inventory = estimateInventoryCost(context)
  const totalBaseline = procurement.baselineCost + production.baselineCost + inventory.baselineCost
  const predictedTotal = procurement.predictedCost + production.predictedCost + inventory.predictedCost
  const totalImpact = predictedTotal - totalBaseline

  return {
    costPrediction: 'ACTIVE',
    procurement,
    production,
    inventory,
    totalBaseline,
    predictedTotal,
    totalImpact,
    impactDirection: totalImpact <= 0 ? 'SAVING' : 'INCREASE',
  }
}
