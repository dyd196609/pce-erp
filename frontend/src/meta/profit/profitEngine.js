export function calculateOrderProfit(order = {}) {
  const revenue = order.revenue || 0
  const materialCost = order.materialCost || 0
  const laborCost = order.laborCost || 0
  const overhead = order.overhead || 0

  const profit = revenue - materialCost - laborCost - overhead
  const margin = revenue === 0 ? 0 : profit / revenue

  return {
    orderId: order.id,
    profit,
    margin,
    breakdown: {
      revenue,
      materialCost,
      laborCost,
      overhead,
    },
  }
}
