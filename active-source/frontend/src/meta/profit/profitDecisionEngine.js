import { calculateOrderProfit } from './profitEngine.js'

export function generateProfitDecision(order = {}) {
  const result = calculateOrderProfit(order)

  let decision = 'HOLD'

  if (result.profit < 0) {
    decision = 'REPRICE'
  }

  if (result.margin < 0.05) {
    decision = 'OPTIMIZE_COST'
  }

  if (result.margin > 0.2) {
    decision = 'EXPAND'
  }

  return {
    orderId: order.id,
    profit: result,
    decision,
  }
}
