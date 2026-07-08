export function reduceProcurementCost(executionData = {}) {
  const confirmedTasks = (executionData.tasks || []).filter((item) => item.confirmation?.confirmed).length
  return {
    area: 'procurement',
    currentCost: 100000,
    optimizedCost: 100000 - confirmedTasks * 1800,
    saving: confirmedTasks * 1800,
    recommendation: 'Batch supplier approval and automate purchase confirmation',
  }
}

export function optimizeInventoryCost(executionData = {}) {
  const timelineCount = executionData.timeline?.timeline?.length || 0
  return {
    area: 'inventory',
    currentCost: 62000,
    optimizedCost: 62000 - timelineCount * 1200,
    saving: timelineCount * 1200,
    recommendation: 'Sync approved purchase demand with warehouse replenishment',
  }
}

export function optimizeProductionCost(executionData = {}) {
  const consistent = executionData.workflow?.consistency?.consistent === true
  const saving = consistent ? 5200 : 1800
  return {
    area: 'production',
    currentCost: 88000,
    optimizedCost: 88000 - saving,
    saving,
    recommendation: 'Align production schedule with approved procurement state',
  }
}

export function optimizeCost(executionData = {}) {
  const procurement = reduceProcurementCost(executionData)
  const inventory = optimizeInventoryCost(executionData)
  const production = optimizeProductionCost(executionData)
  const totalSaving = procurement.saving + inventory.saving + production.saving

  return {
    costOptimization: 'ENABLED',
    procurement,
    inventory,
    production,
    totalSaving,
    savingRate: totalSaving / (procurement.currentCost + inventory.currentCost + production.currentCost),
  }
}
