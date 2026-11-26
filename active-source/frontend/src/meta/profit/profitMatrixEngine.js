function decideProfitCore(revenue = 0, cost = 0) {
  const totalProfit = revenue - cost
  const margin = revenue === 0 ? 0 : totalProfit / revenue

  let decision = 'HOLD'

  if (totalProfit < 0) {
    decision = 'REPRICE'
  }

  if (margin < 0.05) {
    decision = 'OPTIMIZE_COST'
  }

  if (margin > 0.2) {
    decision = 'EXPAND'
  }

  return {
    totalRevenue: revenue,
    totalCost: cost,
    totalProfit,
    margin,
    decision,
  }
}

export function buildProfitMatrix(data = {}) {
  return {
    customerMatrix: data.customers || [],
    productMatrix: data.products || [],
    materialMatrix: data.materials || [],
    productionMatrix: data.production || [],
    inventoryMatrix: data.inventory || [],

    profitCore: decideProfitCore(data.revenue || 0, data.cost || 0),
  }
}
