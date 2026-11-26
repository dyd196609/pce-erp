import { calculateOrderProfit } from './profitEngine.js'

export function calculateCustomerProfit(orders = []) {
  let total = 0

  const breakdown = orders.map((order) => {
    const profit = calculateOrderProfit(order)
    total += profit.profit
    return profit
  })

  return {
    totalProfit: total,
    orders: breakdown,
  }
}
